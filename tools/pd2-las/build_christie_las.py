#!/usr/bin/env python3
"""Build Christie_LAS.zip — a body-only PAYDAY 2 LAS outfit from the DOA5 model.

Source: `references/Christie.zip` (Dead or Alive 5 Christie, costume c2:
`models/plasmid/doa5/christie_c2.{mdl,vvd,dx90.vtx,phy}` + VMT/VTF materials).
Output: `dist/Christie_LAS.zip` (+ `.sha256`), installable to
`PAYDAY 2\\assets\\mod_overrides\\` with SuperBLT + BeardLib + LAS/Wardrobe.

"Without head, like LAS does with police uniforms": the pack ships **no head
geometry** — the Christie face/lashes/eyes/glasses/hair meshes are all dropped —
and registers `replace_body` (NOT `replace_all`; `replace_all` sets head=true in
LAS and would decapitate the heister). LAS then keeps the heister's own head,
exactly how headless LAS outfits behave. The DOA5 rig is mapped onto the PD2
player skeleton via `christie_skeleton_map.json`; geometry is retargeted with
`build_models.py`'s divergence-filter Umeyama fits and authored with the verified
Diesel codec against the 2B reference templates (references/2b.rar).

Body materials kept: cri_body_base (skin), cri_02_01_base / cri_02_02_base /
cri_02_05_base (costume c2 pieces incl. the bra). Dropped: cri_face_base,
cri_sitamatuge (lashes), Leye/Reye, cri_glasses_base, all cri_hair* and the
helmet (cri_02_03/cri_02_04) — every head-carried mesh.

Usage (from the repo root):
  .venv/bin/python tools/pd2-las/build_christie_las.py \
      --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402
import las_outfit_pack as lop  # noqa: E402
import preview as pv  # noqa: E402
import source_model as sm  # noqa: E402
from dds_encode import swizzle_source_normal_dxt5_to_pd2  # noqa: E402
from vtf import parse_vtf, to_dds  # noqa: E402

SOURCE_ZIP = REPO / "references" / "Christie.zip"
SKEL_MAP = HERE / "christie_skeleton_map.json"

MDL_PATH = "models/plasmid/doa5/christie_c2.mdl"
VVD_PATH = "models/plasmid/doa5/christie_c2.vvd"
VTX_PATH = "models/plasmid/doa5/christie_c2.dx90.vtx"
MAT_DIR = "materials/models/plasmid/doa5/christie/c2/"

# ---------------------------------------------------------------------------
# pack identity
# ---------------------------------------------------------------------------
ITEM_ID = "christie"
CATEGORY = "christie"
PACK_DIR_NAME = "Christie_LAS"
UNIT_BASE = f"units/{ITEM_ID}/skins/{ITEM_ID}"
GUI_BASE = f"guis/dlcs/{ITEM_ID}/armor_skins"
TPP_UNIT = f"{UNIT_BASE}/{ITEM_ID}"
FPS_UNIT = f"{UNIT_BASE}/fps_{ITEM_ID}"
HOOK_SOURCE = "lib/tweak_data/armorskinstweakdata"
DISPLAY_NAME = "Christie (DOA5)"
DESCRIPTION = ("Christie from Dead or Alive 5 joins the Payday Gang. "
               "Body-only Legendary Armour Skins outfit (no head — the heister "
               "keeps their own), built from the DOA5 christie_c2 model.")

# Headless LAS contract: replace_body swaps body/arms/hands but leaves the
# head alone; replace_all would also replace the head and there is no head mesh
# in this pack, so claiming it would decapitate the heister.
FLAG_KEYS = (
    "hide_mask",
    "hide_armor",
    "replace_body",
    "fps_hide_armor",
    "fps_replace_body",
)

# source material -> (Diesel material slot, texture pair role)
KEEP_MATERIALS = {
    "cri_body_base": ("mtr_body", "body"),
    "cri_02_01_base": ("mtr_c02_01", "c02_01"),
    "cri_02_02_base": ("mtr_c02_02", "c02_02"),
    "cri_02_05_base": ("mtr_c02_05", "c02_05"),
}
# every other material in the model is head-carried (face, lashes, eyes,
# glasses, hair, helmet) and is dropped with the g_head drawables

TPP_GROUPS = {
    "body": {
        "drawables": ["g_body", "g_body_lod1"],
        "materials": list(KEEP_MATERIALS),
        "out_materials": [slot for slot, _ in KEEP_MATERIALS.values()],
        "mat_slots": {m: slot for m, (slot, _) in KEEP_MATERIALS.items()},
    },
    "shadow": {
        "drawables": ["s_body"],
        "materials": list(KEEP_MATERIALS),
        "out_materials": ["shadow_caster"],
        "mat_slots": {m: "shadow_caster" for m in KEEP_MATERIALS},
    },
}
DROP_DRAWABLES = ("g_head", "g_head_lod1")

MODEL_STRIDE = 148  # sizeof(mstudiomodel_t) for this MDL 48 build


# ---------------------------------------------------------------------------
# source loading (all bodygroup models, not just each bodypart's first)
# ---------------------------------------------------------------------------
def _read_vtx_meshes_all_models(vtx: bytes) -> list[tuple[int, list[tuple[int, int, int]]]]:
    """Like source_model._read_vtx_meshes but walks EVERY model of every
    bodypart (DOA5 ships body/glasses/bra/head variants this way), matching
    the MDL bodypart->model->mesh order."""
    out: list[tuple[int, list[tuple[int, int, int]]]] = []
    version, = struct.unpack_from("<i", vtx, 0)
    if version != sm.VTX_VERSION:
        raise sm.SourceModelError(f"unsupported VTX version {version}")
    _checksum, _num_lods, _mat_repl_off, num_bodyparts, bodypart_off = (
        struct.unpack_from("<iiiii", vtx, 16))
    mesh_index = 0
    for bi in range(num_bodyparts):
        bp = bodypart_off + bi * 8
        num_models, model_off = struct.unpack_from("<ii", vtx, bp)
        for mi in range(num_models):
            mo = bp + model_off + mi * 8
            num_lods_m, lod_off = struct.unpack_from("<ii", vtx, mo)
            for li in range(min(1, num_lods_m)):
                lo = mo + lod_off + li * 12
                num_meshes, mesh_off, _switch = struct.unpack_from("<iif", vtx, lo)
                for mesh_i in range(num_meshes):
                    me = lo + mesh_off + mesh_i * 9
                    num_groups, group_off, _flags = struct.unpack_from("<iiB", vtx, me)
                    triangles: list[tuple[int, int, int]] = []
                    seen: set[tuple[int, int, int]] = set()
                    for gi in range(num_groups):
                        go = me + group_off + gi * sm.VTX_SGROUP_STRIDE
                        (num_verts, vert_off, num_indices, index_off,
                         num_strips, strip_off) = struct.unpack_from("<iiiiii", vtx, go)
                        orig_ids = []
                        for vi in range(num_verts):
                            vbase = go + vert_off + vi * sm.VTX_VERTEX_STRIDE
                            (orig,) = struct.unpack_from("<H", vtx, vbase + 4)
                            orig_ids.append(orig)
                        indices = struct.unpack_from(f"<{num_indices}H", vtx, go + index_off)

                        def add_tri(a, b, c):
                            key = tuple(sorted((a, b, c)))
                            if key in seen:
                                return
                            seen.add(key)
                            triangles.append((a, b, c))

                        for si in range(num_strips):
                            so = go + strip_off + si * sm.VTX_STRIP_STRIDE
                            s_ni, s_ioff, s_nv, s_voff, _s_nb, s_flags = struct.unpack_from(
                                "<iiiiHB", vtx, so)
                            if s_flags & 0x02:
                                strip_idx = indices[s_ioff:s_ioff + s_ni]
                                for k in range(2, len(strip_idx)):
                                    a, b, c = (orig_ids[strip_idx[k - 2]],
                                               orig_ids[strip_idx[k - 1]],
                                               orig_ids[strip_idx[k]])
                                    if k % 2:
                                        a, b = b, a
                                    if a != b and b != c and a != c:
                                        add_tri(a, b, c)
                            else:
                                for t in range(0, s_ni, 3):
                                    add_tri(*(orig_ids[indices[s_ioff + t + k]]
                                              for k in range(3)))
                    out.append((mesh_index, triangles))
                    mesh_index += 1
    return out


def load_christie(zf: zipfile.ZipFile) -> sm.ModelData:
    """Parse the Christie MDL/VVD/VTX triple, including every bodygroup model."""
    mdl = zf.read(MDL_PATH)
    vvd = zf.read(VVD_PATH)
    vtx = zf.read(VTX_PATH)
    if mdl[:4] != sm.MDL_MAGIC:
        raise sm.SourceModelError("bad MDL magic")
    version, _checksum = struct.unpack_from("<ii", mdl, 4)
    if version not in sm.SUPPORTED_MDL_VERSIONS:
        raise sm.SourceModelError(f"unsupported MDL version {version}")

    base = 76
    base += 4            # length
    base += 12 * 6       # eye/illum/hull/view boxes
    base += 4            # flags
    bone_count, bone_off = struct.unpack_from("<ii", mdl, base); base += 8
    base += 8 * 5        # bonecontroller, hitbox, localanim, localseq, activity/events
    texture_count, texture_off = struct.unpack_from("<ii", mdl, base); base += 8
    base += 8            # texturedir
    base += 12           # skinref/skinfamily
    bodypart_count, bodypart_off = struct.unpack_from("<ii", mdl, base)

    bones = sm._read_bones(mdl, bone_count, bone_off)
    materials = sm._read_textures(mdl, texture_count, texture_off)

    mesh_specs: list[tuple[int, int]] = []  # (material_index, model vertex offset)
    model_numverts = 0
    model_name = sm._cstr(mdl, 12)
    for bi in range(bodypart_count):
        bp = bodypart_off + bi * sm.BODYPART_STRIDE
        _n, num_models, _b, model_index = struct.unpack_from("<iiii", mdl, bp)
        for mi in range(num_models):
            mo = bp + model_index + mi * MODEL_STRIDE
            if mi == 0 and bi == 0:
                model_name = sm._cstr(mdl, mo)
            num_meshes, mesh_index, num_vertices, vertex_index = struct.unpack_from(
                "<iiii", mdl, mo + 72)
            voff = vertex_index // sm.VERTEX_STRIDE_VVD
            model_numverts += num_vertices
            for mesh_i in range(num_meshes):
                me = mo + mesh_index + mesh_i * sm.MESH_STRIDE
                material, _mi, _nv, vertexoffset = struct.unpack_from("<iiii", mdl, me)
                mesh_specs.append((material, voff + vertexoffset))

    vertices = sm._read_vvd(vvd, model_numverts)
    vtx_meshes = _read_vtx_meshes_all_models(vtx)
    if len(vtx_meshes) != len(mesh_specs):
        raise sm.SourceModelError(
            f"VTX has {len(vtx_meshes)} meshes, MDL has {len(mesh_specs)}")

    out = sm.ModelData(name=model_name, bones=bones, materials=materials,
                       vertices=vertices)
    nverts = len(vertices)
    for (material_index, voff), (_mi, triangles) in zip(mesh_specs, vtx_meshes):
        flat: list[int] = []
        for tri in triangles:
            for idx in tri:
                gidx = voff + idx
                if not 0 <= gidx < nverts:
                    raise sm.SourceModelError(f"vertex index {gidx} out of range")
                flat.append(gidx)
        out.meshes.append(sm.SubMesh(material=materials[material_index],
                                     triangle_indices=tuple(flat)))
    return out


# ---------------------------------------------------------------------------
# textures
# ---------------------------------------------------------------------------
def _vmt_texture_path(vmt_text: str, key: str) -> str:
    m = re.search(r'"\$' + key + r'"\s+"([^"]+)"', vmt_text, re.I)
    if not m:
        raise ValueError(f"no ${key} in VMT")
    return "materials/" + m.group(1).replace("\\", "/").lower() + ".vtf"


def convert_textures(zf: zipfile.ZipFile) -> dict[str, bytes]:
    """VTF -> Diesel .texture payloads, keyed by pack stem (christie_<role>_df)."""
    textures: dict[str, bytes] = {}
    for src_mat, (_slot, role) in KEEP_MATERIALS.items():
        vmt = zf.read(MAT_DIR + src_mat + ".vmt").decode("latin1")
        df_path = _vmt_texture_path(vmt, "basetexture")
        nm_path = _vmt_texture_path(vmt, "bumpmap")
        df_dds = to_dds(parse_vtf(zf.read(df_path)))
        nm_dds = swizzle_source_normal_dxt5_to_pd2(
            to_dds(parse_vtf(zf.read(nm_path))), invert_y=True)
        textures[f"{ITEM_ID}_{role}_df.texture"] = df_dds
        textures[f"{ITEM_ID}_{role}_nm.texture"] = nm_dds
    return textures


# ---------------------------------------------------------------------------
# pack XML renderers (same contract as las_pack.py / las_outfit_pack.py)
# ---------------------------------------------------------------------------
def render_hook_lua(with_fps: bool) -> str:
    flags = ",\n".join(f"\t{k} = true" for k in FLAG_KEYS)
    lines = [
        "LegendaryArmours = LegendaryArmours or {}",
        "la = LegendaryArmours",
        "",
        f"la.{ITEM_ID} = {{",
        f'\tcategory = "{CATEGORY}",',
        "",
        f'\tunit = "{TPP_UNIT}",',
    ]
    if with_fps:
        lines.append(f'\tfps_unit = "{FPS_UNIT}",')
    lines += ["", flags, "}", ""]
    return "\n".join(lines)


def render_localization() -> str:
    return json.dumps(
        {
            f"bm_menu_{ITEM_ID}_armor_skins": DISPLAY_NAME,
            f"bm_askn_{ITEM_ID}": DISPLAY_NAME,
            f"bm_askn_{ITEM_ID}_desc": DESCRIPTION,
        },
        indent=2,
    )


def render_main_xml(texture_stems: list[str], with_fps: bool) -> str:
    # df_nm registers the PAIR by base name; the engine appends _df/_nm itself
    def _base(stem: str) -> str:
        return stem[:-len(".texture")] if stem.endswith(".texture") else stem
    pairs = "\n".join(
        f'\t\t\t\t<df_nm path="{UNIT_BASE}/{_base(stem)[:-3]}"/>'
        for stem in sorted(texture_stems) if _base(stem).endswith("_df"))
    units = [TPP_UNIT] + ([FPS_UNIT] if with_fps else [])
    unit_lines = "\n".join(f'\t\t\t\t<unit_mat path="{u}"/>' for u in units)
    return (
        f'<table name="{DISPLAY_NAME}" image="{GUI_BASE}/{ITEM_ID}">\n'
        "\n"
        '\t<Localization directory="localization" default="english.txt"/>\n'
        "\n"
        '\t<Hooks directory="hooks">\n'
        f'\t\t<hook file="{ITEM_ID}_las.lua" source_file="{HOOK_SOURCE}"/>\n'
        "\t</Hooks>\n"
        "\n"
        '\t<AddFiles directory="assets">\n'
        "\n"
        f'\t\t\t\t<texture path="{GUI_BASE}/{ITEM_ID}"/>\n'
        f"{pairs}\n"
        "\n"
        f"{unit_lines}\n"
        "\n"
        '\t\t\t\t</AddFiles>\n'
        "</table>\n"
    )


def render_material_config(fps: bool, slots: list[str] | None = None) -> str:
    """Guide-compliant material config for the kept body materials.

    TPP character materials use CONTOUR + unique + contour variables (wall
    outline); fps materials use the guide's DEPTH_SCALING template. Texture
    paths carry no extension. `slots` limits the declared materials to the
    ones a model actually references (the fps viewmodel has no bra).
    """
    group = ITEM_ID
    if slots is None:
        slots = [slot for slot, _ in KEEP_MATERIALS.values()]
    role_of = {slot: role for slot, role in KEEP_MATERIALS.values()}

    def mat(name: str, role: str) -> str:
        if fps:
            template = ("generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:"
                        "SKINNED_3WEIGHTS")
            return (
                f'    <material name="{name}" render_template="{template}" version="2">\n'
                f'        <diffuse_texture file="{UNIT_BASE}/{ITEM_ID}_{role}_df"/>\n'
                f'        <bump_normal_texture file="{UNIT_BASE}/{ITEM_ID}_{role}_nm"/>\n'
                "    </material>\n"
            )
        return (
            f'    <material name="{name}" unique="true" version="2"\n'
            '              render_template="generic:CONTOUR:DIFFUSE_TEXTURE:'
            'NORMALMAP:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{UNIT_BASE}/{ITEM_ID}_{role}_df"/>\n'
            f'        <bump_normal_texture file="{UNIT_BASE}/{ITEM_ID}_{role}_nm"/>\n'
            '        <variable value="1 1 1" type="vector3" name="contour_color"/>\n'
            '        <variable value="0" type="scalar" name="contour_opacity"/>\n'
            "    </material>\n"
        )

    parts = [f'<materials version="3" group="{group}">\n', "\n"]
    for slot in slots:
        parts.append(mat(slot, role_of[slot]))
        parts.append("\n")
    parts.append(
        '    <material name="shadow_caster" '
        'render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n'
        "</materials>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# icon sheet (4 panels: front, side, back, iso — build_icon reads panel 3)
# ---------------------------------------------------------------------------
def render_icon_sheet(model_path: Path, out_png: Path) -> bytes:
    from PIL import Image

    mf = dm.ModelFile.read_path(model_path)
    names = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    verts_all: list[tuple] = []
    faces_all: list[tuple] = []
    colors: list[tuple] = []
    palette = {
        "mtr_body": (214, 176, 150), "mtr_c02_01": (60, 70, 110),
        "mtr_c02_02": (40, 40, 46), "mtr_c02_05": (120, 60, 70),
    }
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        # pick the visible body drawable, not the shadow caster
        dname = next((n for n in names if dm.hash64(n) == md["name_hash"]), "")
        if dname != "g_body":
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        mat_names = [bm.template_name(dm.decode_material(mf.by_id(mid).payload)["name_hash"], mf)
                     for mid in mg["material_ids"]]
        verts = geo["verts"]
        idx = topo["indices"]
        faces = [(idx[i], idx[i + 1], idx[i + 2]) for i in range(0, len(idx), 3)]
        for atom in md["atoms"]:
            mname = mat_names[atom["material_id"]] if atom["material_id"] < len(mat_names) else "?"
            if mname == "shadow_caster":
                continue
            t0 = atom["base_index"] // 3
            base = len(verts_all)
            used = sorted({v for tri in faces[t0:t0 + atom["tri_count"]] for v in tri})
            remap = {v: base + i for i, v in enumerate(used)}
            verts_all.extend(verts[v] for v in used)
            for tri in faces[t0:t0 + atom["tri_count"]]:
                faces_all.append((remap[tri[0]], remap[tri[1]], remap[tri[2]]))
                colors.append(palette.get(mname, (150, 150, 150)))
        break  # one drawable (g_body) is the whole visible outfit
    size = 640
    sheet = Image.new("RGB", (size * 4, size), (18, 18, 22))
    for i, view in enumerate(("front", "side", "back", "iso")):
        panel = out_png.parent / f"_icon_{view}.png"
        pv.render(verts_all, faces_all, colors, panel, view=view, size=size)
        sheet.paste(Image.open(panel).convert("RGB"), (i * size, 0))
        panel.unlink()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    import io
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# pack assembly
# ---------------------------------------------------------------------------
def write_pack(out_root: Path, tpp_model: bytes, fps_model: bytes | None,
               textures: dict[str, bytes], icon: bytes, source_zip_sha: str,
               extra: dict, fps_model_slots: list[str] | None = None) -> Path:
    import shutil

    pack = Path(out_root) / PACK_DIR_NAME
    if pack.exists():
        shutil.rmtree(pack)
    unit_dir = pack / "assets" / UNIT_BASE
    gui_dir = pack / "assets" / GUI_BASE
    unit_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    (pack / "hooks").mkdir(exist_ok=True)
    (pack / "localization").mkdir(exist_ok=True)

    with_fps = fps_model is not None
    fps_model_slots = fps_model_slots or []
    (unit_dir / f"{ITEM_ID}.model").write_bytes(tpp_model)
    (unit_dir / f"{ITEM_ID}.unit").write_text(lop.render_unit_xml(TPP_UNIT))
    (unit_dir / f"{ITEM_ID}.object").write_text(
        lop.render_object_xml(TPP_UNIT, lop.model_drawables(tpp_model)))
    (unit_dir / f"{ITEM_ID}.material_config").write_text(render_material_config(False))
    if with_fps:
        (unit_dir / f"fps_{ITEM_ID}.model").write_bytes(fps_model)
        (unit_dir / f"fps_{ITEM_ID}.unit").write_text(lop.render_unit_xml(FPS_UNIT))
        (unit_dir / f"fps_{ITEM_ID}.object").write_text(
            lop.render_object_xml(FPS_UNIT, lop.model_drawables(fps_model)))
        fps_slots = sorted({slot for slot in fps_model_slots})
        (unit_dir / f"fps_{ITEM_ID}.material_config").write_text(
            render_material_config(True, fps_slots))
    for stem, data in sorted(textures.items()):
        (unit_dir / stem).write_bytes(data)
    (gui_dir / f"{ITEM_ID}.texture").write_bytes(icon)
    (pack / "main.xml").write_text(render_main_xml(sorted(textures), with_fps))
    (pack / "hooks" / f"{ITEM_ID}_las.lua").write_text(render_hook_lua(with_fps))
    (pack / "localization" / "english.txt").write_text(render_localization())

    payload = {}
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "BUILD_INFO.json":
            payload[path.relative_to(pack).as_posix()] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    info = {
        "pack": PACK_DIR_NAME,
        "item_id": ITEM_ID,
        "display_name": DISPLAY_NAME,
        "source": "references/Christie.zip (DOA5 christie_c2, body-only: face/"
                  "lashes/eyes/glasses/hair/helmet dropped)",
        "source_zip_sha256": source_zip_sha,
        "headless": True,
        "registration": {
            "hook_source": HOOK_SOURCE,
            "table": f"LegendaryArmours.{ITEM_ID}",
            "flags": list(FLAG_KEYS),
            "unit": TPP_UNIT,
            "fps_unit": FPS_UNIT if with_fps else None,
        },
        "models_present": True,
        "fps_available": with_fps,
        "runtime_verified": False,
        "payload_sha256": payload,
    }
    info.update(extra)
    (pack / "BUILD_INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return pack


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, required=True,
                    help="directory with 2b.model / fps_2b.model (from 2b.rar)")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "pd2-las")
    ap.add_argument("--dist", type=Path, default=REPO / "dist")
    ap.add_argument("--no-fps", dest="fps", action="store_false", default=True,
                    help="ship only the third-person unit (no fps viewmodel)")
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args(argv)

    source_sha = hashlib.sha256(SOURCE_ZIP.read_bytes()).hexdigest()
    with zipfile.ZipFile(SOURCE_ZIP) as zf:
        model = load_christie(zf)
        textures = convert_textures(zf)

    kept = {m.material for m in model.meshes if m.material in KEEP_MATERIALS}
    dropped = sorted({m.material for m in model.meshes} - kept)
    print(f"source: {model.name}: {len(model.bones)} bones, {len(model.vertices)} verts, "
          f"{model.triangle_count} tris, {len(model.meshes)} meshes")
    print(f"  kept materials: {sorted(kept)}")
    print(f"  dropped (head) materials: {dropped}")

    skel_map = json.loads(SKEL_MAP.read_text())
    template = bm.load_template(args.templates / "2b.model")
    fits = bm.retarget_maps(model, skel_map, template)
    print(f"retarget: {len(fits)} bone transforms")

    groups: dict[str, bm.Group] = {}
    share: dict[str, str] = {}
    for gname, spec in TPP_GROUPS.items():
        g = bm.transfer_group(model, spec, skel_map, template, gname, fits=fits)
        print(f"group {gname}: {len(g.verts)} verts, {len(g.faces)} tris, "
              f"palette {len(g.palette)}, slots {sorted(set(g.mat_slots))}")
        if not g.verts:
            raise SystemExit(f"group {gname} is empty")
        groups[gname] = g
        for drawable in spec["drawables"]:
            share[drawable] = gname

    tpp = bm.assemble_model(template, groups, share, drop_drawables=DROP_DRAWABLES)
    tpp_path = args.out / "christie.model"
    tpp_path.parent.mkdir(parents=True, exist_ok=True)
    tpp_path.write_bytes(tpp.write())
    print(f"wrote {tpp_path} ({tpp_path.stat().st_size} bytes)")
    problems = bm.audit_model(tpp_path)
    if problems:
        raise SystemExit("tpp render atoms do not tile the mesh:\n  "
                         + "\n  ".join(problems))

    fps_bytes = None
    if args.fps:
        fps_tpl = bm.load_template(args.templates / "fps_2b.model")
        fps_arms = bm.extract_bones(groups["body"], bm.is_fps_arm_bone, "arms")
        fps_shadow = bm.extract_bones(groups["shadow"], bm.is_fps_arm_bone, "shadow")
        print(f"fps arms: {len(fps_arms.verts)} verts / {len(fps_arms.faces)} tris "
              f"({len(fps_shadow.verts)} shadow)")
        fps_mf = bm.assemble_model(
            fps_tpl, {"arms": fps_arms, "shadow": fps_shadow},
            {"g_body": "arms", "g_body_lod1": "arms", "s_body": "shadow"},
            drop_drawables=DROP_DRAWABLES)
        fps_path = args.out / "fps_christie.model"
        fps_path.write_bytes(fps_mf.write())
        print(f"wrote {fps_path} ({fps_path.stat().st_size} bytes)")
        problems = bm.audit_model(fps_path)
        if problems:
            raise SystemExit("fps render atoms do not tile the mesh:\n  "
                             + "\n  ".join(problems))
        fps_bytes = fps_path.read_bytes()

    if not args.no_previews:
        bm.preview_from_model(tpp_path, args.out / "previews", "christie")

    icon_png = render_icon_sheet(tpp_path, args.out / "previews" / "christie_icon_sheet.png")
    icon = lop.build_icon(icon_png)

    report = {
        "source_zip": str(SOURCE_ZIP.relative_to(REPO)),
        "source_zip_sha256": source_sha,
        "model": model.name,
        "bones": len(model.bones),
        "source_vertices": len(model.vertices),
        "source_triangles": model.triangle_count,
        "kept_materials": sorted(kept),
        "dropped_head_materials": dropped,
        "tpp": {"verts": len(groups["body"].verts), "tris": len(groups["body"].faces),
                "palette": len(groups["body"].palette),
                "slots": sorted(set(groups["body"].mat_slots))},
        "headless": True,
        "drop_drawables": list(DROP_DRAWABLES),
    }
    (args.out / "christie_report.json").write_text(json.dumps(report, indent=2) + "\n")

    args.dist.mkdir(parents=True, exist_ok=True)
    fps_slots = sorted(set(fps_arms.mat_slots)) if args.fps else None
    pack = write_pack(args.dist, tpp_path.read_bytes(), fps_bytes, textures, icon,
                      source_sha, extra={"build_report": "build/pd2-las/christie_report.json"},
                      fps_model_slots=fps_slots)
    print(f"pack  -> {pack}")
    zipped = lop.zip_pack(pack)
    zipped = Path(zipped)
    digest = hashlib.sha256(zipped.read_bytes()).hexdigest()
    (args.dist / f"{zipped.name}.sha256").write_text(f"{digest}  dist/{zipped.name}\n")
    print(f"zip   -> {zipped}")
    print(f"sha256 -> {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
