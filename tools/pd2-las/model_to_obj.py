#!/usr/bin/env python3
"""Export a Diesel ``.model`` (the one inside a tracked LAS pack) as OBJ/MTL.

Why this exists: the packs in ``dist/`` ship Diesel ``.model`` files only. When a
question is about the *geometry* (is the sleeve bridge closed? are the elbows
spiked?) it is fastest to look at the mesh in a standard viewer. This tool does
the conversion with the one in-repo ``.model`` reader, ``diesel_model`` — it
does not parse anything itself.

Default selection is ``g_body``: the LOD0 body drawable the game draws.
``g_body_lod1`` shares the same geometry; ``s_body`` is the shadow caster
(same triangle count, no UVs needed downstream); ``--drawable all`` exports
every version-3 drawable of the model.

Usage:

    .venv/bin/python tools/pd2-las/model_to_obj.py                # -> build/christie-obj/
    .venv/bin/python tools/pd2-las/model_to_obj.py --render-dir docs/renders/christie-2026-11-14

Units are the pack's own centimetres (GL
bottom-left ``vt`` values are the decoded internal ones, which is what glTF and
OBJ both expect). Triangle winding is exactly as stored; nothing is repaired.

The renderer behind ``--render-dir`` is a flat, per-material-colour orthographic
software raster (front/side/iso, Z-up) — it is deliberately *not* the
skeleton-overlay painter in ``render_mesh_skeleton.py`` so the two cannot drift
into two slightly-different views of the same geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
import diesel_model as dm  # noqa: E402

DEFAULT_PACK = REPO / "dist" / "Christie_LAS.zip"
DEFAULT_MEMBER = "Christie_LAS/assets/units/christie/skins/christie/christie.model"
DEFAULT_FPS_MEMBER = "Christie_LAS/assets/units/christie/skins/christie/fps_christie.model"
DEFAULT_OUT = REPO / "build" / "christie-obj"

#: muted, distinct per-material fills for the flat render (never derived from
#: the name hash, so the colours stay stable across releases)
PALETTE = [(178, 102, 102), (102, 146, 178), (102, 178, 124), (178, 165, 102),
           (150, 120, 178), (110, 178, 178), (178, 130, 178), (140, 140, 140)]


def _model_bytes(args) -> tuple[bytes, str, str]:
    if args.model:
        return Path(args.model).read_bytes(), str(args.model), ""
    member = DEFAULT_FPS_MEMBER if args.fps else DEFAULT_MEMBER
    pack_sha = hashlib.sha256(Path(args.zip).read_bytes()).hexdigest()
    with zipfile.ZipFile(args.zip) as zf:
        return zf.read(member), f"{args.zip}#{member}", pack_sha


def _name(mf) -> dict:
    if not mf.by_type(dm.CUSTOM_HASHLIST):
        return {}
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    return {dm.hash64(n): n for n in hl}


def collect(mf) -> dict[str, dict]:
    """drawable name -> geometry/topology/materials for version-3 drawables."""
    names = _name(mf)
    out = {}
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if md.get("version") != 3:
            continue
        name = names.get(md["name_hash"], f"drawable_{s.id}")
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        geo["faces"] = list(zip(topo["indices"][0::3], topo["indices"][1::3], topo["indices"][2::3]))
        mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        mat_names = []
        for mid in mg["material_ids"]:
            try:
                mat_names.append(names.get(dm.decode_material(mf.by_id(mid).payload)["name_hash"],
                                           f"material_{mid}"))
            except Exception:
                mat_names.append(f"material_{mid}")
        face_materials = [None] * len(geo["faces"])
        for atom in md["atoms"]:
            first = atom["base_index"] // 3
            material = mat_names[atom["material_id"]] if atom["material_id"] < len(mat_names) else None
            face_materials[first:first + atom["tri_count"]] = [material] * atom["tri_count"]
        geo["face_materials"] = face_materials
        geo["atom_materials"] = mat_names
        out[name] = geo
    return out


def export_obj(drawables: dict[str, dict], out_dir: Path, stem: str, source: str, model_sha: str, pack_sha: str = "") -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    obj_path = out_dir / f"{stem}.obj"
    mtl_path = out_dir / f"{stem}.mtl"

    materials = sorted({m for geo in drawables.values() for m in geo["face_materials"] if m})
    palette = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(materials)}

    lines = ["# Diesel .model -> Wavefront OBJ",
             f"# source: {source}",
             f"# source pack sha256: {pack_sha or '(direct .model file)'}",
             f"# source model sha256: {model_sha}",
             "# units: centimetres (pack-native); vt v-values are glTF/OBJ bottom-up, Z-up",
             "# winding: exactly as stored in the .model, nothing repaired",
             f"mtllib {stem}.mtl", ""]
    v_off = vn_off = vt_off = 0
    anchors: dict[str, int] = {}      # drawable name -> (v0, vn0, vt0)
    for name, geo in drawables.items():
        anchors[name] = (v_off, vn_off, vt_off)
        for x, y, z in geo["verts"]:
            lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
        v_off += len(geo["verts"])
        for x, y, z in geo["normals"]:
            lines.append(f"vn {x:.6f} {y:.6f} {z:.6f}")
        vn_off += len(geo["normals"])
        for u, v in geo["uv0"]:
            lines.append(f"vt {u:.6f} {v:.6f}")
        vt_off += len(geo["uv0"])
        lines.append("")

    for name, geo in drawables.items():
        v0, vn0, vt0 = anchors[name]
        lines.append(f"o {name}")
        current_mtl = None
        for face, material in zip(geo["faces"], geo["face_materials"]):
            if material != current_mtl:
                lines.append(f"usemtl {material or 'unassigned'}")
                current_mtl = material
            a, b, c = (i + 1 + v0 for i in face)
            na, nb, nc = (i + 1 + vn0 for i in face)
            ta, tb, tc = (i + 1 + vt0 for i in face)
            lines.append(f"f {a}/{ta}/{na} {b}/{tb}/{nb} {c}/{tc}/{nc}")
        lines.append("")
    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    mtl = ["# per-drawable materials as found in the .model's material hashlist"]
    for name in materials:
        r, g, b = palette[name]
        mtl += [f"newmtl {name}", f"Kd {r / 255:.3f} {g / 255:.3f} {b / 255:.3f}", ""]
    mtl_path.write_text("\n".join(mtl) + "\n", encoding="utf-8")
    return obj_path, mtl_path


def _project(pts: np.ndarray, view: str):
    if view == "front":   # looking along -y: screen = (x, z)
        return pts[:, [0, 2]], pts[:, 1]
    if view == "side":    # looking along +x: screen = (y, z)
        return pts[:, [1, 2]], pts[:, 0]
    if view == "iso":     # 3/4 view
        a = np.deg2rad(35.0)
        u = pts[:, 0] * np.cos(a) - pts[:, 1] * np.sin(a)
        depth = pts[:, 0] * np.sin(a) + pts[:, 1] * np.cos(a)
        return np.stack([u, pts[:, 2]], axis=1), depth
    raise ValueError(view)


def render_view(geo: dict, view: str, out_path: Path, palette: dict[str, tuple]) -> None:
    v = np.array(geo["verts"], float)
    faces = np.array(geo["faces"], int)
    mats = geo["face_materials"]
    p2, depth = _project(v, view)
    W = H = 1000
    margin = 30
    s = min((W - 2 * margin) / max(np.ptp(p2[:, 0]), 1e-6),
            (H - 2 * margin) / max(np.ptp(p2[:, 1]), 1e-6))
    o = np.array([margin - p2[:, 0].min() * s, margin + p2[:, 1].max() * s])

    def scr(pt3):
        q, _ = _project(np.atleast_2d(pt3), view)
        q = q[0]
        return (q[0] * s + o[0], q[1] * s * -1 + o[1])

    img = Image.new("RGB", (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(img)
    order = np.argsort([depth[f].mean() for f in faces])
    colors = {m: palette.get(m, (160, 160, 160)) if m else (160, 160, 160) for m in set(mats)}
    for fi in order:
        f = faces[fi]
        a, b, c = f
        n = np.cross(v[b] - v[a], v[c] - v[a])
        nl = np.linalg.norm(n)
        if nl < 1e-9:
            continue
        n /= nl
        light = 0.35 + 0.65 * abs(float(n @ np.array([0.0, 0.35, 0.94])))
        r, g, bcol = colors[mats[fi]]
        shade = (int(r * light), int(g * light), int(bcol * light))
        dr.polygon([scr(v[a]), scr(v[b]), scr(v[c])], fill=shade)
    img.save(out_path)
    print(f"wrote {out_path} ({view})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", default=str(DEFAULT_PACK), help="pack zip to read .model from (default: tracked Christie_LAS.zip)")
    ap.add_argument("--model", default=None, help="a .model file directly (overrides --zip)")
    ap.add_argument("--fps", action="store_true", help="export fps_christie.model instead of christie.model")
    ap.add_argument("--drawable", default="g_body", help="drawable to export, or 'all' (default: g_body)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT), help="where to write the OBJ/MTL (default: build/christie-obj/)")
    ap.add_argument("--stem", default=None, help="output file stem (default: christie- or fps_christie-)")
    ap.add_argument("--render-dir", default=None, help="also render front/side/iso PNGs into this directory")
    ap.add_argument("--render-stem", default=None, help="render filename stem (default: <stem>_obj -> christie_model-bridge_obj)")
    args = ap.parse_args(argv)

    data, source, pack_sha = _model_bytes(args)
    sha = hashlib.sha256(data).hexdigest()
    mf = dm.ModelFile.read(data)
    drawables = collect(mf)
    if args.drawable == "all":
        chosen = drawables
    elif args.drawable in drawables:
        chosen = {args.drawable: drawables[args.drawable]}
    else:
        print(f"unknown drawable {args.drawable!r}; available: {', '.join(sorted(drawables)) or 'none'}", file=sys.stderr)
        return 2

    stem = args.stem or (("fps_christie" if args.fps else "christie"))
    obj_path, mtl_path = export_obj(chosen, Path(args.out_dir), stem, source, sha, pack_sha)
    print(f"wrote {obj_path}")
    print(f"wrote {mtl_path}")
    for name, geo in chosen.items():
        mats = sorted({m for m in geo["face_materials"] if m})
        print(f"  {name}: {len(geo['verts'])} verts, {len(geo['faces'])} tris, materials: {', '.join(mats)}")

    if args.render_dir:
        materials = sorted({m for geo in chosen.values() for m in geo["face_materials"] if m})
        palette = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(materials)}
        render_stem = args.render_stem or ("christie_model-bridge-fps_obj" if args.fps else "christie_model-bridge_obj")
        combined = {"verts": [], "faces": [], "face_materials": []}
        offset = 0
        for geo in chosen.values():
            combined["verts"] += geo["verts"]
            combined["faces"] += [(a + offset, b + offset, c + offset) for a, b, c in geo["faces"]]
            combined["face_materials"] += geo["face_materials"]
            offset += len(geo["verts"])
        Path(args.render_dir).mkdir(parents=True, exist_ok=True)
        for view in ("front", "side", "iso"):
            out = Path(args.render_dir) / f"{render_stem}_{view}.png"
            render_view(combined, view, out, palette)
    return 0


if __name__ == "__main__":
    sys.exit(main())
