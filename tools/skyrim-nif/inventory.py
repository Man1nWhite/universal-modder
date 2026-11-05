#!/usr/bin/env python3
"""Inventory the source archives for the Skyrim (3BA) outfit port.

Reads the user-supplied ``1.zip`` .. ``5.zip`` at the repo root, which together
are one Skyrim SE 3BA outfit: textures, meshes, BodySlide
slider data and the plugin. Prints (and optionally writes) a report that answers
the questions a port has to answer before any geometry is authored:

* what each archive actually holds, and which copy is the authoritative one
  (the same texture appears up to 8 times across `1.zip`..`3.zip`);
* which meshes are garments and which are the 3BA nude body / body-part helper
  shapes that must *not* be shipped;
* how big each garment is (vertices, triangles) and which body it is built for;
* which skeleton bones it is weighted to, and how much of the mesh each bone
  drives (this is the retarget contract);
* which textures the NIFs reference, and whether they exist in the archives
  (the NIFs point at `textures\\<author>\\<outfit>\\...`, the archives
  store them flat or in numbered variant folders);
* the variant map: which numbered folder in `2.zip`/`3.zip` is which colourway.

Usage:
    python tools/skyrim-nif/inventory.py                     # summary to stdout
    python tools/skyrim-nif/inventory.py --json out.json     # machine readable
    python tools/skyrim-nif/inventory.py --markdown out.md   # human readable
    python tools/skyrim-nif/inventory.py --previews DIR      # PNG contact sheets
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nif  # noqa: E402
import preview  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent

# Shapes that belong to the body, not to the outfit. "feet" / "3BA*" ship inside
# the garment NIFs (BodySlide merges the body the outfit is fitted to) and must
# be dropped by any porter: the target game supplies its own body.
BODY_SHAPES = {"feet", "3BA", "3BA_Vagina", "3BA_Anus"}

# Which mesh files are garments (lod0 = `_0.nif`; `_1.nif` is the weight-1 /
# never-nude variant BodySlide writes, `_g.nif` the ground/collision model).
GARMENT_FILES = {
    "Jacket": "jacket (open + buttoned variants inside one NIF)",
    "Skirt": "pencil skirt",
    "Heels": "high heels",
    "Necklace": "necklace",
    "Glasses": "glasses (mesh not shipped in 4.zip: the plugin points at it)",
}

# XPMSE / vanilla Skyrim humanoid bone -> target-agnostic joint role. Used to
# judge how portable the skinning is: a fully humanoid rig retargets cleanly;
# anything else (breast/butt/3BA bones) needs a decision.
JOINT_ROLES = [
    (r"^NPC Pelvis", "pelvis"),
    (r"^NPC Spine \[", "spine_low"),
    (r"^NPC Spine1", "spine_mid"),
    (r"^NPC Spine2", "spine_high"),
    (r"^NPC Neck", "neck"),
    (r"^NPC Head", "head"),
    (r"^NPC L Clavicle", "shoulder_l"),
    (r"^NPC L UpperArm", "upperarm_l"),
    (r"^NPC L ForearmTwist", "forearm_twist_l"),
    (r"^NPC L Forearm", "forearm_l"),
    (r"^NPC L Hand", "hand_l"),
    (r"^NPC L Finger", "finger_l"),
    (r"^NPC L Thigh", "thigh_l"),
    (r"^NPC L (Front|Rear)Thigh", "thigh_helper_l"),
    (r"^NPC L Calf", "calf_l"),
    (r"^NPC L (Front|Rear)Calf", "calf_helper_l"),
    (r"^NPC L Foot", "foot_l"),
    (r"^NPC R Clavicle", "shoulder_r"),
    (r"^NPC R UpperArm", "upperarm_r"),
    (r"^NPC R ForearmTwist", "forearm_twist_r"),
    (r"^NPC R Forearm", "forearm_r"),
    (r"^NPC R Hand", "hand_r"),
    (r"^NPC R Finger", "finger_r"),
    (r"^NPC R Thigh", "thigh_r"),
    (r"^NPC R (Front|Rear)Thigh", "thigh_helper_r"),
    (r"^NPC R Calf", "calf_r"),
    (r"^NPC R (Front|Rear)Calf", "calf_helper_r"),
    (r"^NPC R Foot", "foot_r"),
    (r"^NPC Belly", "belly_helper"),
    (r"^NPC L Butt|^NPC R Butt", "butt_helper"),
    (r"Breast", "breast_helper"),
    (r"Pussy|Vagina|Anus|Clitoral", "3ba_helper"),
]


def joint_role(bone: str) -> str:
    for pattern, role in JOINT_ROLES:
        if re.search(pattern, bone):
            return role
    return "other"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan_archives(paths: list[Path]) -> dict:
    out = {"archives": [], "textures": {}, "nifs": {}, "other": []}
    for path in paths:
        entry = {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path.read_bytes()),
                 "members": []}
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                data = zf.read(info)
                ext = info.filename.rsplit(".", 1)[-1].lower()
                member = {"name": info.filename, "bytes": len(data), "sha256": sha256(data)}
                entry["members"].append(member)
                if ext == "dds":
                    key = Path(info.filename).stem.lower()
                    variant = Path(info.filename).parent.name
                    meta = preview.dds_info(data)
                    meta.update({"variant": variant, "member": info.filename,
                                 "archive": path.name, "sha256": member["sha256"],
                                 "bytes": len(data),
                                 "mean_rgb": variant_colour(data) if data[:4] == b"DDS " else None})
                    out["textures"].setdefault(key, []).append(meta)
                elif ext == "nif":
                    out["nifs"].setdefault(Path(info.filename).stem, []).append(
                        {"archive": path.name, "member": info.filename, "data": data})
                else:
                    out["other"].append({"archive": path.name, "member": info.filename,
                                         "bytes": len(data), "sha256": member["sha256"]})
        out["archives"].append(entry)
    return out


def describe_colour(rgb: list[int] | None) -> str:
    """Rough human label for a texture's average colour (colourway naming)."""
    if not rgb:
        return "?"
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    if mx < 45:
        return "black"
    if mx - mn < 18:
        return "white" if mx > 190 else ("grey" if mx > 90 else "charcoal")
    if r > g and r > b:
        return "maroon" if b > g else "red/rust"
    if g >= r and g >= b:
        return "olive/gold"
    return "navy" if r < g else "blue"


def variant_colour(data: bytes) -> list[int]:
    im = Image.open(io.BytesIO(data)).convert("RGB")
    a = np.asarray(im.resize((64, 64)), np.float32)
    return [int(round(v)) for v in a.reshape(-1, 3).mean(0)]


def describe_nif(name: str, raw: bytes) -> dict:
    f = nif.parse(raw, name)
    shapes = []
    for shape in f.shapes:
        if shape.num_vertices == 0 or shape.num_triangles == 0:
            continue
        lo, hi = shape.bounds()
        weights = shape.bone_weights()
        total = sum(weights.values()) or 1.0
        shapes.append({
            "name": shape.name,
            "is_body": shape.name in BODY_SHAPES,
            "vertices": shape.num_vertices,
            "triangles": shape.num_triangles,
            "bounds_cm": [[round(float(v) * 1.428, 1) for v in lo],
                          [round(float(v) * 1.428, 1) for v in hi]],
            "uv_range": [[round(float(v), 3) for v in shape.uvs.min(0)],
                         [round(float(v), 3) for v in shape.uvs.max(0)]],
            "shader_type": shape.shader_type,
            "alpha": {"flags": shape.alpha_flags, "threshold": shape.alpha_threshold},
            "textures": [t for t in shape.textures if t],
            "bones": len(shape.bones),
            "bone_weights": {k: round(100.0 * v / total, 1) for k, v in list(weights.items())[:8]},
            "joint_roles": sorted({joint_role(b) for b in shape.bone_weights()}),
            "body_parts": shape.body_parts,
        })
    garments = [s for s in shapes if not s["is_body"]]
    return {
        "file": name,
        "format": f"{f.version} (stream {f.stream_version}, user {f.user_version})",
        "creator": f.creator,
        "shapes": shapes,
        "garment_shapes": [s["name"] for s in garments],
        "body_shapes": [s["name"] for s in shapes if s["is_body"]],
        "garment_vertices": sum(s["vertices"] for s in garments),
        "garment_triangles": sum(s["triangles"] for s in garments),
        "bones": f.bones(),
        "warnings": f.warnings,
    }


def build_report(zips: list[Path]) -> dict:
    scan = scan_archives(zips)
    meshes = {}
    for stem, entries in sorted(scan["nifs"].items()):
        # prefer the lod0 (`_0`) file; `_1` is the same garment on the weight-1
        # body and `_g` is ground collision
        for entry in entries:
            key = Path(entry["member"]).name
            if key.lower().endswith("_0.nif"):
                meshes[stem.replace("_0", "")] = describe_nif(key, entry["data"])
                break
    missing = []
    for stem, mesh in meshes.items():
        for shape in mesh["shapes"]:
            if shape["is_body"]:
                continue        # body textures are vanilla Skyrim files, not this mod's
            for ref in shape["textures"]:
                norm = preview.normalize_ref(ref)
                if Path(norm).stem.lower() not in scan["textures"]:
                    missing.append({"mesh": stem, "shape": shape["name"], "texture": ref})
    variants = {}
    for key, entries in scan["textures"].items():
        seen = {}
        for entry in entries:
            seen.setdefault(entry["sha256"], []).append(entry)
        variants[key] = {
            "copies": len(entries),
            "distinct": len(seen),
            "variants": [
                {
                    "sha256": digest[:12],
                    "variant_folders": sorted({e["variant"] for e in group}),
                    "size": [group[0]["width"], group[0]["height"]],
                    "format": group[0]["format"],
                    "mean_rgb": group[0]["mean_rgb"],
                    "colorway": describe_colour(group[0]["mean_rgb"]),
                    "apps": sorted({e["archive"] for e in group}),
                }
                for digest, group in seen.items()
            ],
        }
    return {
        "source_archives": [
            {"name": a["name"], "bytes": a["bytes"], "sha256": a["sha256"],
             "members": len(a["members"])}
            for a in scan["archives"]
        ],
        "meshes": meshes,
        "textures": variants,
        "missing_texture_refs": missing,
        "non_mesh_members": scan["other"],
        "rights": rights_note(),
    }


def rights_note() -> dict:
    return {
        "author": "not recorded",
        "source_readme": "5.zip: Please Read.txt - 'do not publish this mod outside "
                         "Loverslab without permission'",
        "requirements": ["XP32 Maximum Skeleton Extended (XPMSE)",
                         "BodySlide and Outfit Studio (3BA body)",
                         "NetImmerse Override (NIO)",
                         "HDT Physics Extensions"],
        "verdict": "private / experimental use only; redistribution needs the author's permission",
    }


def to_markdown(report: dict) -> str:
    lines = ["# Skyrim 3BA outfit source inventory", ""]
    lines.append("Generated by `tools/skyrim-nif/inventory.py` from `1.zip` .. `5.zip`.")
    lines.append("")
    lines.append("## Archives")
    lines.append("")
    lines.append("| archive | size | sha256 | members |")
    lines.append("| --- | --- | --- | --- |")
    for a in report["source_archives"]:
        lines.append(f"| `{a['name']}` | {a['bytes'] / 1e6:.1f} MB | `{a['sha256'][:16]}…` | {a['members']} |")
    lines.append("")
    lines.append("## Meshes (lod0)")
    lines.append("")
    for stem, mesh in report["meshes"].items():
        lines.append(f"### {stem}.nif — {GARMENT_FILES.get(stem, '')}".rstrip(" —"))
        lines.append("")
        lines.append(f"- format: {mesh['format']}; creator: `{mesh['creator']}`")
        lines.append(f"- garment shapes: {', '.join(mesh['garment_shapes']) or '—'}; "
                     f"body shapes to drop: {', '.join(mesh['body_shapes']) or '—'}")
        lines.append(f"- garment geometry: {mesh['garment_vertices']} vertices, "
                     f"{mesh['garment_triangles']} triangles")
        lines.append(f"- skinned to {len(mesh['bones'])} bones")
        lines.append("")
        lines.append("| shape | verts | tris | shader | alpha | textures |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for s in mesh["shapes"]:
            tex = ", ".join(Path(t.replace("\\\\", "/")).name for t in s["textures"][:3]) or "—"
            alpha = "—" if s["alpha"]["flags"] is None else f"{s['alpha']['flags']}/{s['alpha']['threshold']}"
            shader = {0: "default", 1: "environment map", 5: "skin tint"}.get(s["shader_type"], str(s["shader_type"]))
            lines.append(f"| `{s['name']}`{' (body)' if s['is_body'] else ''} | {s['vertices']} | "
                         f"{s['triangles']} | {shader} | {alpha} | {tex} |")
        lines.append("")
    lines.append("## Textures")
    lines.append("")
    lines.append("| texture | size | format | distinct | copies | variant folders |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for key, info in sorted(report["textures"].items()):
        first = info["variants"][0]
        folders = sorted({f for v in info["variants"] for f in v["variant_folders"]})
        lines.append(f"| `{key}` | {first['size'][0]}×{first['size'][1]} | {first['format']} | "
                     f"{info['distinct']} | {info['copies']} | {', '.join(folders) or 'root'} |")
    lines.append("")
    if report["missing_texture_refs"]:
        lines.append("### Texture references with no file in the archives")
        lines.append("")
        for m in report["missing_texture_refs"]:
            lines.append(f"- `{m['mesh']}` → `{m['shape']}` wants `{m['texture']}`")
        lines.append("")
    lines.append("## Rights")
    lines.append("")
    r = report["rights"]
    lines.append(f"- author: {r['author']}")
    lines.append(f"- {r['source_readme']}")
    lines.append(f"- requirements: {', '.join(r['requirements'])}")
    lines.append(f"- verdict: **{r['verdict']}**")
    lines.append("")
    return "\n".join(lines)


def write_previews(report: dict, zips: list[Path], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # 1. garment texture sheet, using the shipped (1.zip) copy of every material
    shipped = []
    with zipfile.ZipFile(zips[0]) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".dds"):
                shipped.append((name, zf.read(name)))
    target = out_dir / "skyrim_outfit_textures.png"
    preview.texture_contact_sheet(sorted(shipped), target, cell=256, cols=5)
    written.append(target)
    # 2. four-view render of the assembled outfit (garments only, no body)
    meshes = []
    for stem, info in report["meshes"].items():
        for entry in scan_cached_nifs(zips, stem):
            f = nif.parse(entry, stem)
            for i, s in enumerate(f.shapes):
                if s.name in BODY_SHAPES or s.num_triangles == 0:
                    continue
                meshes.append({"name": s.name,
                               "vertices": s.vertices.astype(np.float64),
                               "triangles": s.triangles,
                               "color": preview.SHAPE_COLORS[len(meshes) % 8]})
            break
    if meshes:
        allv = np.concatenate([m["vertices"] for m in meshes])
        lo, hi = allv.min(0), allv.max(0)
        center = (lo + hi) / 2
        front, _ = preview._project(allv, "front")
        scale = 420 * 0.88 / max(float(front[:, 0].max() - front[:, 0].min()), float(hi[2] - lo[2]))
        size = 420
        sheet = Image.new("RGB", (size * 4, size), (18, 18, 22))
        for v, view in enumerate(["front", "side", "back", "three_quarter"]):
            sheet.paste(preview.render(meshes, view, size, scale, center), (v * size, 0))
        target = out_dir / "skyrim_outfit_outfit.png"
        sheet.save(target)
        written.append(target)
    return written


_NIF_CACHE: dict[str, bytes] | None = None


def scan_cached_nifs(zips: list[Path], stem: str) -> list[bytes]:
    global _NIF_CACHE
    if _NIF_CACHE is None:
        _NIF_CACHE = {}
        for zpath in zips:
            with zipfile.ZipFile(zpath) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".nif") and Path(name).stem.lower().endswith("_0"):
                        _NIF_CACHE[Path(name).stem.replace("_0", "")] = zf.read(name)
    data = _NIF_CACHE.get(stem)
    return [data] if data else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT, help="repo root holding 1.zip..5.zip")
    ap.add_argument("--json", type=Path, help="write the machine-readable report here")
    ap.add_argument("--markdown", type=Path, help="write the human-readable report here")
    ap.add_argument("--previews", type=Path, help="write PNG contact sheets here")
    args = ap.parse_args(argv)

    zips = [args.root / f"{i}.zip" for i in range(1, 6)]
    missing = [str(p) for p in zips if not p.exists()]
    if missing:
        print(f"missing source archives: {', '.join(missing)}", file=sys.stderr)
        return 2

    report = build_report(zips)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(to_markdown(report) + "\n")
        print(f"wrote {args.markdown}")
    if args.previews:
        for path in write_previews(report, zips, args.previews):
            print(f"wrote {path}")
    if not (args.json or args.markdown or args.previews):
        print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
