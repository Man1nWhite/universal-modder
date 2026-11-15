#!/usr/bin/env python3
"""Export the DOA5 source model (MDL/VVD/VTX) as OBJ/MTL.

This is the *source* end of the Christie pipeline: the exact bytes in
``references/Christie.zip`` (``models/plasmid/doa5/christie_c2.{mdl,vvd,dx90.vtx}``,
sha256 of the zip is tracked in ``references/README.md``). It is the complement
to the pack-level OBJ question — what the game is *supposed* to be looking at,
straight from the Visual Studio model, with no re-authoring, no retarget and
no pack bytes involved.

The model is read with the one in-repo reader, ``source_model`` — the same
path the previews and the SMD exporter use. ``load_model`` cannot read this
archive (its VVD LOD0 vertex count, 21,979, differs from the MDL's model
numvertices, 18,359 — see ``tools/pd2-las/source_model.py``), so like every
other Christie tool this defaults to ``load_all_bodygroups``.

``--kept`` selects only the four body materials the pipeline ships
(``cri_body_base``, ``cri_02_01_base``, ``cri_02_02_base``, ``cri_02_05_base``;
17,287 tris); the default is every submesh (22 meshes / 36,920 tris, eyes,
face, hair, glasses and all).

Units are the file's own (Source inches) unless ``--unit-scale 2.54`` is given;
the default keeps the bytes as stored. UVs are written as ``(u, 1 - v)`` because
Source stores v top-down and glTF/OBJ read it bottom-up. Winding is exactly as
stored. Bone influences are **not** carried into the OBJ — OBJ has no joints;
``tools/pd2-las/smd.py`` is the rig-preserving interchange.
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
import source_model as sm  # noqa: E402

DEFAULT_SOURCE = REPO / "references" / "Christie.zip"
MEMBERS = ("models/plasmid/doa5/christie_c2.mdl",
           "models/plasmid/doa5/christie_c2.vvd",
           "models/plasmid/doa5/christie_c2.dx90.vtx")
#: kept body materials, identical to the previews and to `render_mesh_skeleton.render_source`
KEEP = ("cri_body_base", "cri_02_01_base", "cri_02_02_base", "cri_02_05_base")

PALETTE = [(178, 102, 102), (102, 146, 178), (102, 178, 124), (178, 165, 102),
           (150, 120, 178), (110, 178, 178), (178, 130, 178), (140, 140, 140)]


def load_source(source_zip: Path, mdl: str, vvd: str, vtx: str):
    with zipfile.ZipFile(source_zip) as zf:
        mdl_b, vvd_b, vtx_b = (zf.read(n) for n in (mdl, vvd, vtx))
    model = sm.load_all_bodygroups(mdl_b, vvd_b, vtx_b)
    return model, mdl_b, vvd_b, vtx_b


def select_meshes(model, kept: bool):
    if kept:
        keep = set(KEEP)
        return [m for m in model.meshes if m.material in keep], list(KEEP)
    order: list[str] = []
    for mesh in model.meshes:
        if mesh.material not in order:
            order.append(mesh.material)
    return list(model.meshes), order


def export_obj(model, out_dir: Path, stem: str, source: str, member_shas: dict, kept: bool,
               unit_scale: float = 1.0) -> tuple[Path, Path, dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    obj_path = out_dir / f"{stem}.obj"
    mtl_path = out_dir / f"{stem}.mtl"
    meshes, materials = select_meshes(model, kept)

    lines = ["# DOA5 source model -> Wavefront OBJ",
             f"# source: {source}",
             *[f"# member {k} sha256: {v}" for k, v in sorted(member_shas.items())],
             f"# materials: {'all' if not kept else 'kept body set only'} ({len(materials)})",
             f"# units: {'centimetres (scaled)' if unit_scale != 1.0 else 'source units as stored (inches)'}; Z-up",
             "# vt v-values written as (1 - v): Source stores v top-down, OBJ reads bottom-up",
             "# winding: exactly as stored; weights: dropped (use smd.py for the rig)",
             f"mtllib {stem}.mtl", ""]
    for v in model.vertices:
        lines.append(f"v {v.pos[0] * unit_scale:.6f} {v.pos[1] * unit_scale:.6f} {v.pos[2] * unit_scale:.6f}")
    for v in model.vertices:
        lines.append(f"vn {v.normal[0]:.6f} {v.normal[1]:.6f} {v.normal[2]:.6f}")
    for v in model.vertices:
        lines.append(f"vt {v.uv[0]:.6f} {1.0 - v.uv[1]:.6f}")
    lines.append("")
    palette = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(materials)}
    for mesh in meshes:
        idx = mesh.triangle_indices
        lines.append(f"o {mesh.material}")
        lines.append(f"usemtl {mesh.material}")
        for k in range(0, len(idx), 3):
            a, b, c = (i + 1 for i in idx[k:k + 3])
            lines.append(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}")
        lines.append("")
    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    mtl = ["# materials as named in the source MDL's texture list (order of first use)"]
    for name in materials:
        r, g, b = palette[name]
        mtl += [f"newmtl {name}", f"Kd {r / 255:.3f} {g / 255:.3f} {b / 255:.3f}", ""]
    mtl_path.write_text("\n".join(mtl) + "\n", encoding="utf-8")

    faces = sum(len(m.triangle_indices) // 3 for m in meshes)
    stats = {"verts": len(model.vertices), "tris": faces, "meshes": len(meshes),
             "materials": materials, "kept": kept}
    return obj_path, mtl_path, stats


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


def render_view(model, meshes, view: str, out_path: Path, palette: dict) -> None:
    v = np.array([p.pos for p in model.vertices], float)
    face_list, face_mats = [], []
    for mesh in meshes:
        idx = np.array(mesh.triangle_indices, int).reshape(-1, 3)
        face_list.append(idx)
        face_mats += [mesh.material] * len(idx)
    faces = np.concatenate(face_list)
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
    for fi in order:
        f = faces[fi]
        a, b, c = f
        n = np.cross(v[b] - v[a], v[c] - v[a])
        nl = np.linalg.norm(n)
        if nl < 1e-9:
            continue
        n /= nl
        light = 0.35 + 0.65 * abs(float(n @ np.array([0.0, 0.35, 0.94])))
        r, g, bcol = palette[face_mats[fi]]
        dr.polygon([scr(v[a]), scr(v[b]), scr(v[c])], fill=(int(r * light), int(g * light), int(bcol * light)))
    img.save(out_path)
    print(f"wrote {out_path} ({view})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(DEFAULT_SOURCE), help="references zip with the MDL/VVD/VTX (default: references/Christie.zip)")
    ap.add_argument("--mdl", default=MEMBERS[0], help="MDL member path inside --source")
    ap.add_argument("--vvd", default=MEMBERS[1], help="VVD member path inside --source")
    ap.add_argument("--vtx", default=MEMBERS[2], help="VTX member path inside --source")
    ap.add_argument("--kept", action="store_true", help="only the four kept body materials (cri_body_base, cri_02_01/02/05_base)")
    ap.add_argument("--unit-scale", type=float, default=1.0, help="multiply positions (2.54 for inches->cm; default 1.0 = bytes as stored)")
    ap.add_argument("--out-dir", default=str(REPO / "build" / "christie-source-obj"), help="where to write the OBJ/MTL (default: build/christie-source-obj/)")
    ap.add_argument("--stem", default=None, help="output file stem (default: christie_source or christie_source_kept)")
    ap.add_argument("--render-dir", default=None, help="also render front/side/iso PNGs into this directory")
    ap.add_argument("--render-stem", default=None, help="render filename stem (default carries the mdl-vvd-vtx source-type token)")
    args = ap.parse_args(argv)

    source_zip = Path(args.source)
    model, mdl_b, vvd_b, vtx_b = load_source(source_zip, args.mdl, args.vvd, args.vtx)
    member_shas = {Path(args.mdl).name: hashlib.sha256(mdl_b).hexdigest(),
                   Path(args.vvd).name: hashlib.sha256(vvd_b).hexdigest(),
                   Path(args.vtx).name: hashlib.sha256(vtx_b).hexdigest()}
    stem = args.stem or ("christie_source_kept" if args.kept else "christie_source")
    obj_path, mtl_path, stats = export_obj(model, Path(args.out_dir), stem,
                                           str(source_zip), member_shas, args.kept, args.unit_scale)
    print(f"wrote {obj_path}")
    print(f"wrote {mtl_path}")
    print(f"  {stats['meshes']} meshes, {stats['verts']} verts, {stats['tris']} tris, "
          f"materials: {', '.join(stats['materials'])}")

    if args.render_dir:
        meshes, materials = select_meshes(model, args.kept)
        palette = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(materials)}
        render_stem = args.render_stem or ("christie_mdl-vvd-vtx_kept_obj" if args.kept else "christie_mdl-vvd-vtx_obj")
        Path(args.render_dir).mkdir(parents=True, exist_ok=True)
        for view in ("front", "side", "iso"):
            render_view(model, meshes, view, Path(args.render_dir) / f"{render_stem}_{view}.png", palette)
    return 0


if __name__ == "__main__":
    sys.exit(main())
