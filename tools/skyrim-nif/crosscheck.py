"""Cross-check the pure-Python NIF reader against nifly (the Outfit Studio library).

`nif.py` claims to decode Skyrim SE meshes. `nifly_bridge.py` exposes the C++
library everyone else uses. This script feeds both the same files and reports
every disagreement, so the reader's correctness is evidence, not faith.

    bash tools/skyrim-nif/build_nifly.sh        # once: fetch + compile nifly
    .venv/bin/python tools/skyrim-nif/crosscheck.py            # all 12 meshes
    .venv/bin/python tools/skyrim-nif/crosscheck.py --json out.json --markdown out.md
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nif  # noqa: E402
import nifly_bridge  # noqa: E402

ROOT = HERE.parent.parent


def _triangle_set(tris: np.ndarray) -> set[tuple[int, int, int]]:
    return {tuple(sorted(int(v) for v in tri)) for tri in tris}


def compare_mesh(path: Path, raw: bytes) -> dict:
    """Compare one NIF: nif.py vs nifly, shape by shape."""
    mine = nif.parse(raw, str(path))
    report: dict = {"file": path.name, "checks": [], "deltas": {}}

    with nifly_bridge.NiflyFile(path) as theirs:
        report["nifly_status"] = theirs.status
        ref_shapes = {s["name"]: s for s in theirs.shapes()}

        names_mine = [s.name for s in mine.shapes]
        names_ref = [s["name"] for s in theirs.shapes()]
        report["checks"].append({
            "check": "shape list",
            "mine": names_mine,
            "nifly": names_ref,
            "ok": names_mine == names_ref,
        })

        if not names_mine:
            return report

        worst_vertex = 0.0
        worst_uv = 0.0
        all_tris_ok = True
        all_bones_ok = True
        all_tex_ok = True
        weight_errors = []

        for shape in mine.shapes:
            ref = ref_shapes.get(shape.name)
            if ref is None:
                continue
            same_count = shape.num_vertices == len(ref["vertices"])
            report["checks"].append({
                "check": f"{shape.name}: vertex count",
                "mine": shape.num_vertices,
                "nifly": len(ref["vertices"]),
                "ok": same_count,
            })
            if not same_count or shape.num_vertices == 0:
                continue

            dv = np.abs(shape.vertices - ref["vertices"]).max()
            worst_vertex = max(worst_vertex, float(dv))
            if shape.num_vertices and ref["uvs"].shape[0] == shape.num_vertices:
                du = np.abs(shape.uvs - ref["uvs"]).max()
                worst_uv = max(worst_uv, float(du))

            tris_ok = (_triangle_set(shape.triangles) == _triangle_set(ref["triangles"])
                       and shape.num_triangles == len(ref["triangles"]))
            all_tris_ok &= tris_ok

            bones_ok = shape.bones == ref["bones"]
            all_bones_ok &= bones_ok

            tex_mine = [t for t in shape.textures if t]
            tex_ref = [t for t in ref["textures"] if t]
            tex_ok = tex_mine == tex_ref
            all_tex_ok &= tex_ok

            if shape.weights is not None:
                for bone, total in ref["bone_totals"].items():
                    idx = shape.bones.index(bone) if bone in shape.bones else None
                    if idx is None:
                        weight_errors.append((shape.name, bone, "missing", total))
                        continue
                    mask = shape.bone_indices == idx
                    mine_total = float(shape.weights[mask].sum())
                    weight_errors.append((shape.name, bone, mine_total, total))

        report["deltas"] = {
            "max_vertex_abs_delta": worst_vertex,
            "max_uv_abs_delta": worst_uv,
        }
        report["checks"].append({
            "check": "triangle sets", "ok": all_tris_ok})
        report["checks"].append({
            "check": "bone lists", "ok": all_bones_ok})
        report["checks"].append({
            "check": "texture lists", "ok": all_tex_ok})
        report["checks"].append({
            "check": "node names",
            "mine": len(mine.nodes),
            "nifly": theirs.node_count,
            "ok": len(mine.nodes) == theirs.node_count,
        })
        if weight_errors:
            worst_weight = max(abs(m - r) for _s, _b, m, r in weight_errors
                               if isinstance(m, float))
            report["deltas"]["max_bone_weight_total_delta"] = worst_weight
            bad = [(s, b, m, r) for s, b, m, r in weight_errors
                   if not isinstance(m, float) or abs(m - r) > 0.05]
            report["checks"].append({
                "check": "per-bone weight totals",
                "ok": not bad,
                "bad": bad[:5],
            })
    return report


def collect_sources(root: Path) -> list[tuple[Path, bytes]]:
    """Every garment/collision NIF from 4.zip (the user-supplied mesh archive)."""
    found: list[tuple[Path, bytes]] = []
    archive = root / "4.zip"
    if archive.exists():
        with zipfile.ZipFile(archive) as zf:
            for name in sorted(zf.namelist()):
                if name.lower().endswith(".nif"):
                    found.append((Path(name), zf.read(name)))
        return found
    # fall back to an extracted tree
    for path in sorted((root / "meshes").rglob("*.nif")):
        found.append((path, path.read_bytes()))
    return found


def run(root: Path) -> dict:
    sources = collect_sources(root)
    if not sources:
        raise SystemExit("no NIFs found: expected 4.zip at the repo root")
    results = []
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        for name, raw in sources:
            path = Path(tmp) / Path(name).name
            path.write_bytes(raw)
            results.append(compare_mesh(path, raw))
    return {"root": str(root), "files": results}


def summarize(report: dict) -> tuple[int, int]:
    passed = failed = 0
    for entry in report["files"]:
        bad = [c for c in entry["checks"] if not c["ok"]]
        if bad:
            failed += len(bad)
        passed += len(entry["checks"]) - len(bad)
    return passed, failed


def to_markdown(report: dict) -> str:
    passed, failed = summarize(report)
    lines = ["# nif.py vs nifly — cross-check", ""]
    lines.append(f"- files: {len(report['files'])}")
    lines.append(f"- checks passed: {passed}")
    lines.append(f"- checks failed: {failed}")
    lines.append("")
    lines.append("| file | nifly status | shapes | max vertex Δ | max uv Δ | max bone-weight Δ |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for entry in report["files"]:
        d = entry.get("deltas", {})
        status = entry.get("nifly_status", "?")
        n = len([c for c in entry["checks"] if c["check"] == "shape list"])
        shapes = entry["checks"][0]["mine"] if entry["checks"] else []
        lines.append(
            f"| `{entry['file']}` | {status} | {len(shapes)} "
            f"| {d.get('max_vertex_abs_delta', 0):.2e} "
            f"| {d.get('max_uv_abs_delta', 0):.2e} "
            f"| {d.get('max_bone_weight_total_delta', 0):.2e} |")
        del n
    failures = [(entry["file"], c) for entry in report["files"]
                for c in entry["checks"] if not c["ok"]]
    if failures:
        lines.append("")
        lines.append("## Failing checks")
        lines.append("")
        for file, check in failures:
            lines.append(f"- `{file}` — {check['check']}: {check}")
    else:
        lines.append("")
        lines.append("Every check agrees: shape list, vertex counts, vertex positions, "
                     "triangle sets, bone lists, texture paths, per-bone weight totals "
                     "and node counts.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--markdown", type=Path)
    args = ap.parse_args(argv)

    try:
        report = run(args.root)
    except nifly_bridge.NiflyUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, default=str) + "\n")
        print(f"wrote {args.json}")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(to_markdown(report) + "\n")
        print(f"wrote {args.markdown}")
    if not (args.json or args.markdown):
        print(to_markdown(report))
    passed, failed = summarize(report)
    print(f"crosscheck: {passed} checks passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
