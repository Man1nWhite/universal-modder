#!/usr/bin/env python3
"""Build `Honoka_LAS` — the DOAXVV "Secret Report" outfit as a PD2 LAS pack.

The outfit (the Honoka "Secret Report" TMC, `references/Outfit for
Honoka-109-1-1-1628020933.zip`) is converted into a Legendary Armour Skins
pack for PAYDAY 2:

* **Geometry** — the three in-scope meshes (the headless body
  `WGT_new_aya_body_decl0`, the suit jacket `WGT_cap2` and the skirt
  `WGT_headdress2`), retargeted onto the PD2 player skeleton as embedded in
  the 2B reference pack (`2b.model`), exactly the transform pipeline the
  Miranda build uses (`build_models.retarget_maps` / `transfer_group`).
  Source skin palettes are remapped slot→global node index first (the TMC's
  per-mesh palettes, see `tmc.py`); unmapped helper bones (breast helpers,
  skirt physics helpers, twist bones) merge into their nearest mapped
  ancestor via the ancestor walk with `tmc_skeleton_map.json`.
* **No head** — the body has none; `g_head`/`g_head_lod1` are dropped from
  the model as drawables (`assemble_model(..., drop_drawables=...)`), and
  the registration uses `BODY_ONLY` flags (never `replace_all`).
* **No hands** — both arms are cut at the PD2 wrist joints after retarget
  (`ARM_JOINTS`, same joints the Miranda sleeve-bridge pass uses), so the
  heister's own gloves spawn normally; the LAS glove-adapter companion fixes
  LAS's ``default_glove_id`` fresh-table bug (see
  `las_outfit_pack.render_glove_adapter_lua`).
* **Textures** — the source `L_*.dds` (provided in `references/Honoka/`).
  Mapping (provisional, see
  `docs/pd2-las/honoka-las-build.md`; swap the constants below to change it):

  +-------------+------------------------------+------------------------------+
  | role        | diffuse                      | normal                       |
  +-------------+------------------------------+------------------------------+
  | body_df/nm  | L_3.dds (alpha kept, scaled) | L_4.dds                      |
  | jacket_df/nm| L_7.dds (alpha   20, matte)  | L_8.dds                      |
  | skirt_df/nm | L_9.dds (alpha   20, matte)  | L_11.dds                     |
  +-------------+------------------------------+------------------------------+

  All six are re-encoded to BC3/DXT5 with a full mip chain in PD2's layout
  (diffuse alpha = low gloss; normals X in alpha, Y in green, Y inverted for
  the DirectX-style sources — same layout as `tools/pd2-port/dds.py`'s
  `pd2_normal_channels`).
* **Unit** — third person only: `fps_unit` is left out entirely (the pack
  ships no first-person view, which is better than LAS pointing at a missing
  file). The `.object` is regenerated from the built model, so it lists
  exactly `g_body` (on) and `g_body_lod1` (off); `s_body` and colliders are
  engine-owned and stay out.

Outputs (default `build/pd2-las/`, git-ignored; **never** `dist/`):

  build/pd2-las/honoka_las.model            the third-person model
  build/pd2-las/Honoka_LAS/                 the installable pack folder
  build/pd2-las/Honoka_LAS.zip              + .sha256
  build/pd2-las/honoka_las_report.json      build report (runtime_verified: false)

`runtime_verified` stays `false` everywhere; nothing here has been run in
PAYDAY 2.

Usage:
  bash tools/pd2-las/recover_env.sh    # once: .venv + the 2B templates
  .venv/bin/python tools/pd2-las/build_honoka_las.py [--templates DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_TEMPLATES = REPO / "build" / "pd2-las" / "2b" / "2B - LAS" / "assets" / "units" / "2b" / "skins" / "2b"
DEFAULT_OUT = REPO / "build" / "pd2-las"
SOURCE_ZIP = REPO / "references" / "Outfit for Honoka-109-1-1-1628020933.zip"
TMC_NAME = "Honoka_DOAXVV_Secret_Report.TMC"
TEX_DIR = REPO / "references" / "Honoka"

sys.path.insert(0, str(HERE))

import determinism  # noqa: E402

SOURCE_ZIP_SHA256 = "86fc084c7310e9cd78bfb39cd4bb15486a15295f1c233c754492e1c4f572e154"
TMC_SHA256 = "12d4f370ee47a183bfc3ba4792b7fda47b4176b13444a87745c89089cefa129b"

# source mesh group -> out material slot
IN_SCOPE = {
    "WGT_new_aya_body_decl0": "honoka_body",
    "WGT_cap2": "honoka_jacket",
    "WGT_headdress2": "honoka_skirt",
}
EXCLUDED_NOTE = {
    "WGT_new_aya_body_decl1": "debug-like 28-bone uniform-weight mesh; never shipped",
    "WGT_body_feather": "sash slivers; excluded (owner review pending)",
    "WGT_sweat_chest": "chest emblem; excluded (owner decision pending)",
    "WGT_cap": "1-vertex placeholder decl",
    "WGT_headdress": "1-vertex placeholder decl",
}

# texture roles -> source dds file, and how the diffuse alpha (gloss) is set
DF_ALPHA = {"honoka_body": ("const", 20.0),
            "honoka_jacket": ("const", 20.0),
            "honoka_skirt": ("const", 20.0)}
TEX_ROLES = {
    "honoka_body_df": "L_3.dds",
    "honoka_body_nm": "L_4.dds",
    "honoka_jacket_df": "L_7.dds",
    "honoka_jacket_nm": "L_8.dds",
    "honoka_skirt_df": "L_9.dds",
    "honoka_skirt_nm": "L_11.dds",
}

ITEM_ID = "honoka"
PACK_DIR_NAME = "Honoka_LAS"
UNIT_BASE = "units/honoka/skins/honoka"
GUI_BASE = "guis/dlcs/honoka/armor_skins"
TPP_UNIT = f"{UNIT_BASE}/honoka"
DISPLAY_NAME = "Honoka (Secret Report)"
DESCRIPTION = ("Honoka in the DOAXVV 'Secret Report' formal outfit joins the Payday Gang. "
               "Legendary Armour Skins outfit, built from the DOAXVV costume.")


# ------------------------------------------------------------- source side
# A right-handed map from the TMC's Y-up centimetre frame to Diesel's Z-up
# frame. p_d = M p_s with det(M) = +1; the retarget fits absorb the yaw.
_M = ((1.0, 0.0, 0.0),
      (0.0, 0.0, -1.0),
      (0.0, 1.0, 0.0))


def basis_matrix():
    import numpy as np

    M = np.array(_M, dtype=np.float64)
    assert abs(float(np.linalg.det(M)) - 1.0) < 1e-12
    return M


def glbl_to_diesel(glbl_raw) -> list:
    """TMC GlblMtx (metres, Y-up) -> diesel world bind (row-vector dm.Mat, cm)."""
    import numpy as np

    import diesel_model as dm

    M = basis_matrix()
    out = []
    for raw in glbl_raw:
        W = np.array(raw, dtype=np.float64).reshape(4, 4, order="F")  # column-convention 4x4
        R = W[:3, :3]
        t = W[:3, 3]
        R2 = M @ R @ M.T
        t2 = 100.0 * (M @ t)
        Wd = np.eye(4)
        Wd[:3, :3] = R2
        Wd[:3, 3] = t2
        out.append(tuple(float(x) for x in Wd.T.reshape(16)))
    return out


def tmc_to_model_data(tmc):
    """Bone names/parents and the in-scope meshes as a `source_model.ModelData`.

    The TMC stores vertex positions/normals in centimetres, Y-up; they are
    rotated into the Diesel frame here. Bone indices in the vertex stream are
    slots into each mesh's inline palette; they are remapped to global node
    indices here (load_meshes already attached `.palette`).
    """
    import numpy as np

    from source_model import Bone, ModelData, SkinVertex, SubMesh

    M = basis_matrix()
    model = ModelData(name="honoka_secret_report")
    for i, name in enumerate(tmc.node_names):
        model.bones.append(Bone(name=name, parent=int(tmc.hie_parent[i]),
                                pos=(0.0, 0.0, 0.0), quat=(0.0, 0.0, 0.0, 1.0)))
    for mesh in tmc.load_meshes():
        if mesh.group not in IN_SCOPE:
            continue
        pal = np.asarray(mesh.palette, dtype=np.int64) if mesh.palette is not None else None
        pos = np.asarray(mesh.positions, dtype=np.float64) @ M.T
        nrm = np.asarray(mesh.normals, dtype=np.float64) @ M.T
        uvs = np.asarray(mesh.uvs, dtype=np.float64)
        gidx = np.asarray(mesh.bone_indices, dtype=np.int64)
        if pal is not None:
            gidx = pal[gidx]
        wgt = np.asarray(mesh.weights, dtype=np.float64)
        for n in range(mesh.vert_count):
            influences = tuple(
                (int(gidx[n, k]), float(wgt[n, k]))
                for k in range(4) if wgt[n, k] > 1e-6
            )
            model.vertices.append(SkinVertex(
                pos=(float(pos[n][0]), float(pos[n][1]), float(pos[n][2])),
                normal=(float(nrm[n][0]), float(nrm[n][1]), float(nrm[n][2])),
                uv=(float(uvs[n][0]), float(uvs[n][1])),
                weights=influences))
        tris = np.asarray(mesh.indices).reshape(-1).astype(np.int64)
        v0 = len(model.vertices) - mesh.vert_count
        model.meshes.append(SubMesh(material=mesh.group,
                                    triangle_indices=tuple(int(i) + v0 for i in tris)))
    return model


# ------------------------------------------------------------- wrist cut

def cut_group_at_wrists(g, arm_joints, margin: float = 0.5) -> dict:
    """Drop every triangle with a vertex past the PD2 wrist plane.

    After retarget the outfit is in the 2B bind frame, arms straight out;
    the plane runs through the wrist joint along the forearm axis. Everything
    distal to it (the hand) is dropped; anything at or proximal to it is
    kept, so the rim sits exactly under the glove cuff.

    The drop is done slice by slice: each slice keeps its own compact vertex
    block (the Diesel atom invariant requires the slice's triangles to index
    inside its own block), unused vertices are dropped, and the slices'
    ``base_v``/``base_i`` are rebuilt.

    The hand is the region beyond the wrist joint (radial distance < 28 cm
    from the forearm axis); a plain half-space cut at the wrist is wrong for
    the PD2 bind pose (the forearm axis points down-forward, so the plane
    would contain the feet and cut the lower legs off).
    """
    import numpy as np

    wrist_l, elbow_l = (np.array(v, dtype=np.float64) for v in arm_joints[-1])
    wrist_r, elbow_r = (np.array(v, dtype=np.float64) for v in arm_joints[1])
    axis_l = wrist_l - elbow_l
    axis_l /= np.linalg.norm(axis_l)
    axis_r = wrist_r - elbow_r
    axis_r /= np.linalg.norm(axis_r)
    verts = np.asarray(g.verts, dtype=np.float64)

    def hand_side(wrist, axis, r_max=28.0):
        # beyond the wrist along the forearm axis, AND close to it: the hand and
        # the outstretched fingers.  A bare half-space would also swallow the
        # lower legs, because in the PD2 bind pose the forearm axis points
        # steeply down-forward.
        v = verts - wrist
        t = v @ axis
        perp = np.linalg.norm(v - np.outer(t, axis), axis=1)
        return (t > margin) & (perp < r_max)

    distal = hand_side(wrist_l, axis_l) | hand_side(wrist_r, axis_r)

    # slice layout of the incoming faces: transfer_group extends faces slice by
    # slice, in model.meshes order; recover each slice's kept face list from it
    faces = np.asarray(g.faces, dtype=np.int64)
    new_verts = []
    new_normals = []
    new_uvs = []
    new_weights = []
    new_faces = []
    new_slices = []
    report_per_slice = []
    vbase = 0
    fbase = 0
    # faces of the old group are laid out in slice order; walk them with a
    # cursor and match each slice to its (old) vertex block
    cursor = 0
    for (src_mat, base_v, base_i, tri_count, nverts) in g.slices:
        sl_faces = faces[cursor:cursor + tri_count]
        cursor += tri_count
        old_lo, old_hi = base_v, base_v + nverts
        keep_mask = ~distal[sl_faces].any(axis=1)
        kept = sl_faces[keep_mask]
        remap = {}
        for f in kept:
            for vi in f:
                assert old_lo <= vi < old_hi
                if int(vi) not in remap:
                    remap[int(vi)] = len(remap)
        for old_vi in sorted(remap, key=remap.get):
            new_verts.append(g.verts[old_vi])
            new_normals.append(g.normals[old_vi])
            new_uvs.append(g.uvs[old_vi])
            new_weights.append(g.weights[old_vi])
        for f in kept:
            new_faces.append(tuple(remap[int(vi)] + vbase for vi in f))
        report_per_slice.append({
            "src_mat": src_mat,
            "verts_before": nverts,
            "tris_before": tri_count,
            "verts_after": len(remap),
            "tris_after": int(keep_mask.sum()),
            "tris_dropped": int((~keep_mask).sum()),
        })
        new_slices.append((src_mat, vbase, fbase * 3, len(kept), len(remap)))
        vbase += len(remap)
        fbase += len(kept)
    g.verts = new_verts
    g.normals = new_normals
    g.uvs = new_uvs
    g.weights = new_weights
    g.faces = new_faces
    g.slices = new_slices
    return {"slices": report_per_slice,
            "tris_dropped": sum(s["tris_dropped"] for s in report_per_slice),
            "verts_after": vbase}


# ------------------------------------------------------------- textures

def _full_mip_levels(image, colour: bool) -> list:
    """All mip levels of ``image`` (uint8 RGBA), level 0 first, down to 1x1.

    Colour is averaged as light (sRGB -> linear -> box reduce -> sRGB); other
    channels (gloss/alpha, normal components) are averaged as-is.
    """
    import numpy as np

    from dds_encode import box_reduce, linear_to_srgb, srgb_to_linear

    image = np.asarray(image, dtype=np.uint8)
    levels = [image]
    if colour:
        light = srgb_to_linear(image[..., :3] / 255.0)
        alpha = image[..., 3].astype(np.float64)
        while min(light.shape[:2]) > 1:
            light = box_reduce(light, 2)
            alpha = box_reduce(alpha[..., None], 2)[..., 0]
            rgb = np.clip(linear_to_srgb(light) * 255.0, 0.0, 255.0)
            levels.append(np.dstack([np.rint(rgb).astype(np.uint8),
                                     np.rint(np.clip(alpha, 0, 255)).astype(np.uint8)]))
        return levels
    plane = image.astype(np.float64)
    while min(plane.shape[:2]) > 1:
        plane = box_reduce(plane, 2)
        levels.append(np.rint(np.clip(plane, 0, 255)).astype(np.uint8))
    return levels


def build_textures() -> tuple[dict, dict]:
    """Decode the source DDS files, re-encode to BC3 with full mip chains.

    Returns (textures, report) where textures maps `<stem>.texture` to DDS
    bytes ready for the pack.
    """
    import hashlib as _hl

    import numpy as np
    from PIL import Image

    import dds_encode

    def load(name):
        with open(TEX_DIR / name, "rb") as fh:
            return Image.open(fh).convert("RGBA")

    textures = {}
    report = {}
    for stem, dds_name in sorted(TEX_ROLES.items()):
        with open(TEX_DIR / dds_name, "rb") as fh:
            src_bytes = fh.read()
        im = np.asarray(load(dds_name), dtype=np.uint8)
        role = stem.rsplit("_", 1)[1]
        if role == "df":
            mode, value = DF_ALPHA[stem[:-3]]
            if mode == "scale":
                alpha = np.rint(im[..., 3].astype(np.float64) * value).astype(np.uint8)
            else:
                alpha = np.full(im.shape[:2], int(value), dtype=np.uint8)
            img = np.dstack([im[..., :3], alpha]).astype(np.uint8)
            levels = _full_mip_levels(img, colour=True)
        else:
            # Diesel normal layout: X in alpha, Y in green, Y inverted for a
            # DirectX-style source; red 255 / blue 0 (same layout as
            # pd2-port/dds.pd2_normal_channels).
            x = im[..., 0].astype(np.int16)
            y = 255 - im[..., 1].astype(np.int16)  # DirectX-style green down -> Y+
            img = np.dstack([np.full(im.shape[:2], 255, np.uint8),
                             np.clip(y, 0, 255).astype(np.uint8),
                             np.zeros(im.shape[:2], np.uint8),
                             x.astype(np.uint8)])
            levels = _full_mip_levels(img, colour=False)
        textures[f"{stem}.texture"] = dds_encode.bc3_dds_from_levels(levels)
        report[stem] = {
            "source": f"references/Honoka/{dds_name}",
            "source_sha256": _hl.sha256(src_bytes).hexdigest(),
            "size": list(im.shape[:2]),
            "mips": len(levels),
            "alpha_rule": DF_ALPHA.get(stem[:-3]) if role == "df" else "diesel_normal_x_alpha_y_green_invert_y",
            "out_sha256": _hl.sha256(textures[f"{stem}.texture"]).hexdigest(),
        }
    return textures, report


def render_material_config() -> str:
    """TPP material config: the three outfit materials, CONTOUR (the LAS
    wall-outline template), plus shadow_caster."""
    def contour_mat(name, role):
        return (
            f'    <material name="{name}" unique="true" version="2"\n'
            '              render_template="generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{UNIT_BASE}/{role}_df"/>\n'
            f'        <bump_normal_texture file="{UNIT_BASE}/{role}_nm"/>\n'
            '        <variable value="1 1 1" type="vector3" name="contour_color"/>\n'
            '        <variable value="0" type="scalar" name="contour_opacity"/>\n'
            "    </material>\n"
        )

    return "".join([
        '<materials version="3" group="honoka">\n',
        "\n",
        contour_mat("honoka_body", "honoka_body"),
        "\n",
        contour_mat("honoka_jacket", "honoka_jacket"),
        "\n",
        contour_mat("honoka_skirt", "honoka_skirt"),
        "\n",
        '    <material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n',
        "</materials>",
    ])


def registration():
    import las_outfit_pack as lop

    return lop.Registration(
        item_id=ITEM_ID,
        display_name=DISPLAY_NAME,
        description=DESCRIPTION,
        unit=TPP_UNIT,
        flags=lop.BODY_ONLY,          # never replace_all — the pack ships no head
        fps_unit=None,                # no first-person unit: LAS keeps the vanilla FPS arms
        category=ITEM_ID,
        icon=f"{GUI_BASE}/honoka",
        hook_file="honoka_las.lua",
        pairs=tuple(f"{UNIT_BASE}/honoka_{role}" for role in ("body", "jacket", "skirt")),
        textures=(),
        glove_adapter=True,
    )


# ------------------------------------------------------------- the build

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES,
                    help="directory containing 2b.model (default: where extract_2b.py unpacks it)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="output root (default: build/pd2-las)")
    ap.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    ap.add_argument("--no-previews", action="store_true",
                    help="skip the 4-view icon render")
    args = ap.parse_args(argv)
    determinism.enter(__file__)

    import hashlib as _hl

    import numpy as np

    import build_models as bm
    import las_outfit_pack as lop
    import tmc as tmc_mod

    # ---- inputs ----------------------------------------------------------
    zip_sha = _hl.sha256(args.source_zip.read_bytes()).hexdigest()
    if zip_sha != SOURCE_ZIP_SHA256:
        print(f"warning: source zip sha256 {zip_sha} != documented {SOURCE_ZIP_SHA256}",
              file=sys.stderr)
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="honoka_las_"))
    with zipfile.ZipFile(args.source_zip) as z:
        tmc_bytes = z.read(TMC_NAME)
    tmc_sha = _hl.sha256(tmc_bytes).hexdigest()
    if tmc_sha != TMC_SHA256:
        print(f"warning: TMC sha256 {tmc_sha} != documented {TMC_SHA256}", file=sys.stderr)
    tmc_path = work / TMC_NAME
    tmc_path.write_bytes(tmc_bytes)

    require = args.templates / "2b.model"
    if not require.is_file():
        raise SystemExit(f"2B template missing at {require} — run `make -sC tools/pd2-las env`")
    template = bm.load_template(require)
    print(f"template: {require}")

    tmc = tmc_mod.TmcFile(str(tmc_path))
    meshes = tmc.load_meshes()
    print(f"tmc: {tmc.node_count} nodes, "
          f"{sum(m.vert_count for m in meshes)} verts / "
          f"{sum(len(np.asarray(m.indices).reshape(-1, 3)) for m in meshes)} tris total")

    skel_map = json.loads((HERE / "tmc_skeleton_map.json").read_text())
    src_worlds = glbl_to_diesel(tmc.global_raw)
    model = tmc_to_model_data(tmc)
    print(f"source model: {len(model.bones)} bones, {len(model.vertices)} verts, "
          f"{model.triangle_count} tris, {len(model.meshes)} meshes")

    # ---- retarget onto the 2B skeleton ----------------------------------
    # src_worlds are precomputed (the TMC is Y-up centimetres; the fits only
    # need bind positions), so the stock source_bone_worlds is bypassed.
    fits = bm.retarget_maps(model, skel_map, template, src_worlds=src_worlds)
    print(f"retarget: {len(fits)} source bones mapped")

    groups = {}
    share = {}
    specs = {
        "outfit": {"drawables": ["g_body", "g_body_lod1"],
                   "materials": list(IN_SCOPE),
                   "out_materials": ["honoka_body", "honoka_jacket", "honoka_skirt"],
                   "mat_slots": dict(IN_SCOPE)},
        "shadow": {"drawables": ["s_body"],
                   "materials": list(IN_SCOPE),
                   "out_materials": ["shadow_caster"]},
    }
    cut_report = {}
    for gname, spec in specs.items():
        # the TMC reader emits normal-aligned (outward CCW) triangles;
        # do not reverse them like the Source (DirectX CW) meshes
        g = bm.transfer_group(model, spec, skel_map, template, gname,
                              fits=fits, swap_winding=False)
        print(f"[{gname}] {len(g.verts)} verts / {len(g.faces)} tris, "
              f"palette {len(g.palette)}")
        cut = cut_group_at_wrists(g, bm.ARM_JOINTS)
        for s in cut["slices"]:
            print(f"    {s['src_mat']:28s} tris {s['tris_before']:6d} -> {s['tris_after']:6d} "
                  f"(dropped {s['tris_dropped']}), verts {s['verts_before']:6d} -> {s['verts_after']}")
        cut_report[gname] = cut
        groups[gname] = g
        for d in spec["drawables"]:
            share[d] = gname

    tpp_mf = bm.assemble_model(template, groups, share,
                               drop_drawables=("g_head", "g_head_lod1"))
    args.out.mkdir(parents=True, exist_ok=True)
    tpp_path = args.out / "honoka_las.model"
    tpp_path.write_bytes(tpp_mf.write())
    print(f"wrote {tpp_path} ({tpp_path.stat().st_size} bytes)")

    # signed volume sanity (winding orientation)
    vol = 0.0
    for (a, b, c) in groups["shadow"].faces:
        p, q, r = groups["shadow"].verts[a], groups["shadow"].verts[b], groups["shadow"].verts[c]
        vol += (p[0] * (q[1] * r[2] - q[2] * r[1])
                - p[1] * (q[0] * r[2] - q[2] * r[0])
                + p[2] * (q[0] * r[1] - q[1] * r[0]))
    print(f"signed volume (shadow group): {vol / 6:.1f} (cm^3)")

    # ---- textures ---------------------------------------------------------
    textures, tex_report = build_textures()
    for stem, info in sorted(tex_report.items()):
        print(f"texture {stem:14s} src={info['source'].split('/')[-1]:10s} "
              f"{info['size'][0]}x{info['size'][1]} mips={info['mips']}")

    # ---- pack scaffold -----------------------------------------------------
    reg = registration()
    pack = args.out / PACK_DIR_NAME
    import shutil
    if pack.exists():
        shutil.rmtree(pack)
    unit_dir = pack / "assets" / UNIT_BASE
    gui_dir = pack / "assets" / GUI_BASE
    (pack / "hooks").mkdir(parents=True)
    (pack / "localization").mkdir(parents=True)
    unit_dir.mkdir(parents=True)
    gui_dir.mkdir(parents=True)

    (pack / "main.xml").write_bytes(lop.main_xml(reg).encode("utf-8"))
    (pack / "hooks" / "honoka_las.lua").write_bytes(lop.hook_lua(reg).encode("utf-8"))
    (pack / "hooks" / "honoka_glove_adapter.lua").write_bytes(
        lop.render_glove_adapter_lua(ITEM_ID, "Honoka (Secret Report) LAS").encode("utf-8"))
    (pack / "localization" / "english.txt").write_bytes(
        lop.localization(reg).encode("utf-8"))

    # icon: our own render of the built model, four views
    if not args.no_previews:
        sheet = _render_icon_sheet(tpp_path, textures)
        (pack / "previews").mkdir(exist_ok=True)
        (pack / "previews" / "honoka_4views.png").write_bytes(sheet)
        icon = lop.build_icon(sheet, view=3)
    else:
        icon = _fallback_icon()
    (gui_dir / "honoka.texture").write_bytes(icon)
    for name, data in sorted(textures.items()):
        (unit_dir / name).write_bytes(data)

    (unit_dir / "honoka.model").write_bytes(tpp_path.read_bytes())
    (unit_dir / "honoka.unit").write_bytes(lop.render_unit_xml(TPP_UNIT).encode("utf-8"))
    drawables = lop.model_drawables(tpp_path.read_bytes())
    (unit_dir / "honoka.object").write_bytes(
        lop.render_object_xml(TPP_UNIT, drawables).encode("utf-8"))
    (unit_dir / "honoka.material_config").write_bytes(render_material_config().encode("utf-8"))

    # ---- BUILD_INFO + zip -------------------------------------------------
    payload = {}
    for path in sorted(pack.rglob("*")):
        if path.is_file():
            payload[path.relative_to(pack).as_posix()] = _hl.sha256(path.read_bytes()).hexdigest()
    build_info = {
        "pack": PACK_DIR_NAME,
        "item_id": ITEM_ID,
        "registration": {
            "hook_source": lop.HOOK_SOURCE,
            "table": f"LegendaryArmours.{ITEM_ID}",
            "flags": list(lop.BODY_ONLY),
            "unit": TPP_UNIT,
            "fps_unit": None,
            "glove_adapter": True,
        },
        "models_present": True,
        "runtime_verified": False,
        "source": {
            "archive": "references/Outfit for Honoka-109-1-1-1628020933.zip",
            "archive_sha256": zip_sha,
            "tmc_sha256": tmc_sha,
            "meshes": list(IN_SCOPE),
            "excluded": EXCLUDED_NOTE,
            "basis": "TMC Y-up cm -> Diesel Z-up cm, det=+1 basis change; TMC GlblMtx (m) x100",
            "wrist_cut_margin_cm": 0.5,
            "textures": tex_report,
        },
        "payload_sha256": payload,
    }
    (pack / "BUILD_INFO.json").write_text(json.dumps(build_info, indent=2, sort_keys=True) + "\n")

    zip_path = lop.zip_pack(pack)
    zip_sha = _hl.sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.parent / f"{zip_path.name}.sha256").write_text(
        f"{zip_sha}  {zip_path.relative_to(REPO) if zip_path.is_relative_to(REPO) else zip_path.name}\n"
    )

    # ---- report ------------------------------------------------------------
    report = {
        "runtime_verified": False,
        "pack": PACK_DIR_NAME,
        "model": str(tpp_path.relative_to(REPO)) if tpp_path.is_relative_to(REPO) else str(tpp_path),
        "zip": zip_path.name,
        "zip_sha256": zip_sha,
        "drawables": drawables,
        "cut": cut_report,
        "groups": {gname: {"verts": len(g.verts), "tris": len(g.faces),
                           "palette": list(g.palette)} for gname, g in groups.items()},
        "templates": {name: _hl.sha256((args.templates / name).read_bytes()).hexdigest()
                      for name in ("2b.model",)},
        "excluded_meshes": EXCLUDED_NOTE,
        "skinning": "4 weights (TMC) -> palette remap -> ancestor walk -> top-3 renormalised (SKINNED_3WEIGHTS)",
    }
    report_path = args.out / "honoka_las_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"pack: {pack}")
    print(f"zip:  {zip_path} ({zip_path.stat().st_size} bytes) sha256={zip_sha}")
    print(f"report: {report_path}")
    print("runtime_verified: false (nothing in-game yet)")
    return 0


def _render_icon_sheet(model_path: Path, textures: dict):
    """Four-view sheet [front, side, back, three-quarter] of the built model."""
    import numpy as np
    from PIL import Image

    import preview_textured as pt

    mesh_list = pt.material_meshes(model_path)
    tex = {}
    for key, data in textures.items():
        if key.endswith("_df.texture"):
            import io as _io
            tex[key[:-len("_df.texture")]] = (
                np.asarray(Image.open(_io.BytesIO(data)).convert("RGBA"),
                           dtype=np.float32) / 255.0)
    # map material name -> our decoded texture arrays (flip_v=True convention:
    # the built model stores (u, 1 - v))
    tex_by_material = {f"honoka_{role}": tex[f"honoka_{role}"]
                       for role in ("body", "jacket", "skirt")}
    size = 512
    imgs = []
    for view in ("front", "side", "back", "threequarter"):
        imgs.append(pt.render(mesh_list, tex_by_material, view, size, 2.35,
                              np.array([0.0, 2.0, 97.0]), flip_v=True, cull=True))
    sheet = Image.new("RGB", (4 * size, size))
    for i, img in enumerate(imgs):
        sheet.paste(img, (i * size, 0))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


def _fallback_icon() -> bytes:
    """Navy tile with the pack initial — used with --no-previews."""
    import io

    import numpy as np
    from PIL import Image, ImageDraw

    from dds_encode import rgba_to_bc3_dds  # noqa: F401

    img = Image.new("RGB", (256, 256), (24, 28, 52))
    d = ImageDraw.Draw(img)
    d.text((104, 92), "H", fill=(232, 216, 164))
    rgba = np.dstack([np.asarray(img), np.full((256, 256), 255, np.uint8)])
    from dds_encode import rgba_to_bc3_dds as _enc
    return _enc(rgba)


if __name__ == "__main__":
    raise SystemExit(main())
