"""Report what a subscribed Garry's Mod / SFM addon actually contains.

Answers the recurring question — "is this the business suit, and is it cheaper
than a `TMC` import?" — from the addon file itself instead of its description:

1. the file list, grouped by extension (so `models/…christie…` names and any
   per-outfit subfolders are visible);
2. every readable model in it, with its vertex/triangle counts, material names
   and **bone names**;
3. whether that skeleton is a `ValveBiped` rig the existing
   `tools/pd2-las/skeleton_map.json` already covers — which is what decides
   whether the GLB→LAS retarget path can be reused unchanged;
4. material/texture presence, so a bodygroup whose textures are missing cannot
   be mistaken for a usable outfit.

Read-only. Nothing is extracted to disk and nothing is rendered: this prints a
report, because the addon itself is licensed content that must never enter the
repository. Resolve a workshop id to a downloaded `.gma` by hand (the
`workshop/content/4000/<id>` folder after subscribing) and pass the path.

    python tools/pd2-las/inspect_gma.py path/to/870161699.gma
    python tools/pd2-las/inspect_gma.py addon.gma --json report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gma import GmaArchive, GmaError  # noqa: E402
from source_model import SourceModelError, load_model  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SKELETON_MAP = REPO / "tools" / "pd2-las" / "skeleton_map.json"


def load_skeleton_map(path: Path = SKELETON_MAP) -> dict:
    blob = json.loads(path.read_text())
    drop = blob.get("drop", {})
    return {
        "map": blob.get("map", {}),
        "drop": tuple(drop.get("patterns", ())),
        "target_only": tuple(blob.get("target_only", {}).get("names", ())),
    }


def classify_bones(bones, skel_map: dict) -> dict:
    """Split a rig into 'already mapped', 'Source-only dead weight', 'unknown'.

    A rig is *ValveBiped* if its names carry the `ValveBiped.Bip01_` prefix; that
    prefix is what `skeleton_map.json` keys on, so a ported DOA ragdoll keeps the
    same dialect the L4D2 Miranda model uses and needs no new mapping work.
    """
    names = [b.name for b in bones]
    mapped = [n for n in names if n in skel_map["map"]]
    dropped = [n for n in names if any(p in n for p in skel_map["drop"])]
    prefix = Counter(n.split(".")[0] for n in names if "." in n)
    dialect = prefix.most_common(1)[0][0] if prefix else "(no namespace prefix)"
    unknown = [n for n in names if n not in mapped and n not in dropped]
    return {
        "dialect": dialect,
        "bone_count": len(names),
        "mapped": mapped,
        "source_only": dropped,
        "unmapped": unknown,
        "mapped_share": (len(mapped) / len(names)) if names else 0.0,
    }


def inspect(path: Path, skel_map: dict | None = None, max_models: int = 0) -> dict:
    skel_map = skel_map or load_skeleton_map()
    arc = GmaArchive(path.read_bytes(), name=str(path))
    report: dict = {
        "file": str(path),
        "version": arc.version,
        "title": arc.title,
        "author": arc.author,
        "description": arc.description,
        "type": arc.addon_type,
        "tags": list(arc.tags),
        "timestamp": arc.timestamp,
        "bytes": sum(e.size for e in arc.entries),
        "file_count": len(arc.entries),
        "by_extension": dict(
            Counter(
                e.path.rsplit(".", 1)[-1].lower() if "." in e.path else "(none)"
                for e in arc.entries
            ).most_common()
        ),
        "models": [],
        "errors": [],
    }

    triples = arc.model_paths()
    if max_models:
        triples = triples[:max_models]
    for mdl, vvd, vtx in triples:
        entry: dict = {"paths": [mdl, vvd, vtx]}
        try:
            model = load_model(arc.read(mdl), arc.read(vvd), arc.read(vtx))
        except (SourceModelError, GmaError) as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            report["errors"].append(entry)
            report["models"].append(entry)
            continue
        rig = classify_bones(model.bones, skel_map)
        entry.update(
            {
                "name": model.name,
                "vertices": len(model.vertices),
                "triangles": model.triangle_count,
                "materials": model.materials,
                "material_count": len(model.materials),
                "bones": rig,
            }
        )
        report["models"].append(entry)
    return report


def _fmt_paths(paths) -> str:
    out = []
    for p in paths:
        name = p.rsplit("/", 1)[-1]
        out.append(name)
    return ", ".join(out)


def render(report: dict) -> str:
    lines = [
        f"addon   : {report['title']!r} by {report['author']!r}",
        f"format  : GMAD v{report['version']}, {report['file_count']} files, "
        f"{report['bytes']:,} B",
        f"type    : {report['type'] or 'unset'}  tags: {report['tags'] or 'none'}",
        f"desc    : {report['description'].strip()[:400]}",
        "",
        "contents: " + ", ".join(f"{k} x{v}" for k, v in report["by_extension"].items()),
        "",
    ]
    if not report["models"]:
        lines.append("no readable model triples (.mdl + .vvd + .vtx) in this addon")
    for i, m in enumerate(report["models"], 1):
        lines.append(f"[{i}] {m['paths'][0]}")
        if "error" in m:
            lines.append(f"    unreadable: {m['error']}")
            continue
        bones = m["bones"]
        lines.append(
            f"    {m['vertices']:,} verts / {m['triangles']:,} tris, "
            f"{m['material_count']} materials"
        )
        lines.append(f"    materials: {_fmt_paths(m['materials'])}")
        lines.append(
            f"    rig: {bones['dialect']}, {bones['bone_count']} bones, "
            f"{len(bones['mapped'])} already in skeleton_map.json "
            f"({bones['mapped_share']:.0%}), "
            f"{len(bones['source_only'])} Source-only, "
            f"{len(bones['unmapped'])} unmapped"
        )
        if bones["unmapped"]:
            preview = ", ".join(bones["unmapped"][:12])
            more = "" if len(bones["unmapped"]) <= 12 else f" … (+{len(bones['unmapped']) - 12})"
            lines.append(f"    unmapped names: {preview}{more}")
        lines.append("")
    verdict = _verdict(report)
    if verdict:
        lines.append("verdict: " + verdict)
    return "\n".join(lines)


def _verdict(report: dict) -> str:
    """The one-line answer this tool exists to give, phrased conservatively."""
    models = [m for m in report["models"] if "error" not in m]
    if not models:
        return "not usable as a source: no readable model in the archive."
    rigs = {m["bones"]["dialect"] for m in models}
    if len(rigs) == 1 and "ValveBiped" in rigs:
        share = min(m["bones"]["mapped_share"] for m in models)
        return (
            f"ValveBiped rig, {share:.0%} of bones already mapped — the "
            "GLB/ValveBiped → LAS retarget path applies as-is. That makes it a "
            "reading aid and a posing reference, not a licence to ship: the mesh "
            "is still a port of someone else's asset, so private build only."
        )
    return (
        f"rig set {sorted(rigs)} — not the ValveBiped dialect skeleton_map.json "
        "covers, so the retarget needs new mapping work before it is usable."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gma", type=Path, help="path to a .gma (compressed or plain)")
    ap.add_argument("--json", type=Path, help="also write the report as JSON here")
    ap.add_argument(
        "--max-models", type=int, default=0, help="stop after N models (0 = all)"
    )
    args = ap.parse_args(argv)

    try:
        report = inspect(args.gma, max_models=args.max_models)
    except (GmaError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render(report))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
