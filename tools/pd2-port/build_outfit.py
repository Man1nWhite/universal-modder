#!/usr/bin/env python3
"""Build a Legendary Armour Skins (LAS) wearable outfit pack for PAYDAY 2.

Replicates the pack layout of working LAS skins (ModWorkShop "Wardrobe Mod"
companion packs such as "Yorha No. 2 Type B (2B) [LAS]" and Vladik268/P2's
"Jack Cooper - Legendary Armour Skin") from the repaired Lawson character
assets in dist/lawson_<character>.zip.

Output: dist/lawson_outfit.zip

    Lawson_LAS/
        main.xml
        localization/english.txt
        README.txt
        assets/guis/dlcs/wardrobe_mod/textures/pd2/blackmarket/icons/player_styles/lawson.texture
        assets/units/wardrobe_mod/armor_skins/lawson/lawson.model
        assets/units/wardrobe_mod/armor_skins/lawson/lawson.unit
        assets/units/wardrobe_mod/armor_skins/lawson/lawson.object
        assets/units/wardrobe_mod/armor_skins/lawson/lawson.material_config
        assets/units/wardrobe_mod/armor_skins/lawson_fps/lawson_fps.model
        assets/units/wardrobe_mod/armor_skins/lawson_fps/lawson_fps.unit
        assets/units/wardrobe_mod/armor_skins/lawson_fps/lawson_fps.object
        assets/units/wardrobe_mod/armor_skins/lawson_fps/lawson_fps.material_config
        assets/units/wardrobe_mod/armor_skins/textures/<19 .texture files>

Model handling
--------------
Third-person (TPP) model: the repaired npc_criminal_female_1.model verbatim,
plus an empty ``co_box`` locator object3D (LAS packs use
``culling_object="co_box"``; vanilla characters cull on ``g_body``).

First-person (FPS) model: same skeleton (LAS FPS rigs use the standard
heister bone names - verified against jack_fps.model from Vladik268/P2), but
only arm geometry.  g_body verts bound to the arm chains (shoulder..fingers,
plus the a_weapon_* attachment locators) are kept, with face closure so the
arm shell stays watertight; g_hands is kept whole.  Everything else (head,
hair, vests, bags, collision proxies) is dropped.

The font of truth for the XML sidecars is Vladik268/P2's Jack Cooper pack and
THOT-PATROLL's payday-2-outfit-helper make_file() templates; divergences from
the helper (it writes </material> instead of </materials>, uses the mod name
for the icon path, and emits a wrong FPS opacity texture path) are corrected
here.
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "pd2-port"))

import dmodel  # noqa: E402
import repair_skin_palettes as rp  # noqa: E402
from dmodel import TAGS_INV, hash_str  # noqa: E402

# ---------------------------------------------------------------------------
# conventions (verified against working LAS packs)
# ---------------------------------------------------------------------------

SKIN = "lawson"
MOD_NAME = "Lawson_LAS"          # no spaces (LAS guide troubleshooting)
UNIT_BASE = f"units/wardrobe_mod/armor_skins/{SKIN}/{SKIN}"
UNIT_FPS = f"units/wardrobe_mod/armor_skins/{SKIN}_fps/{SKIN}_fps"
TEX_BASE = "units/wardrobe_mod/armor_skins/textures"
ICON_PATH = f"guis/dlcs/wardrobe_mod/textures/pd2/blackmarket/icons/player_styles/{SKIN}"

ARM_SUFFIXES = (
    "Shoulder", "Arm", "ForeArm", "ForeArmRoll", "Hand",
    "HandThumb1", "HandThumb2", "HandThumb3",
    "HandIndex1", "HandIndex2", "HandIndex3",
    "HandMiddle1", "HandMiddle2", "HandMiddle3",
    "HandRing1", "HandRing2", "HandRing3",
    "HandPinky1", "HandPinky2", "HandPinky3",
)
ARM_BONE_NAMES = {
    *(s + suf for s in ("Left", "Right") for suf in ARM_SUFFIXES),
    "a_weapon_left_front", "a_weapon_right_front",
}

CHARACTERS = [
    "bodhi", "chains", "dragon", "joy", "ecp_male", "max", "wild", "jacket",
    "jowi", "chico", "jimmy", "sokol", "myh", "sydney", "ecp_female",
    "female_1", "bonnie",
]

# graphics list mirrored from the vanilla npc_criminal_female_1.object
GRAPHICS_ENABLED = [
    "g_head_fem1", "g_hair_cloth1", "g_hair_cloth2", "g_hair_cloth3",
    "g_body", "g_hands", "s_body",
]
GRAPHICS_DISABLED = [
    "g_hair_mask_cloth1", "g_hair_mask_cloth2", "g_hair_mask_cloth3",
    "g_vest_small", "g_vest_thies", "g_vest_neck", "g_vest_shoulder",
    "g_vest_body", "g_vest_leg_arm", "g_toolbag", "g_ammobag", "g_medicbag",
    "g_sentrybag", "g_bodybagsbag", "g_armorbag", "g_firstaidbag",
]
SHADOW_CASTERS = {"g_head_fem1", "g_body", "g_hands", "s_body"}

BASIC_TPP = "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:RL_PLAYERS:SKINNED_3WEIGHTS"
BASIC_FPS = "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _nm(o) -> str:
    """Object name string; parse-time names are hash-only, use .name from hashlist."""
    return o.name if isinstance(o.name, str) else f"#{o.name_hash:016x}"


def _names_map(sections) -> dict[int, str]:
    return {
        s.id: s.obj.name
        for s in sections
        if isinstance(getattr(s, "obj", None), (dmodel.Object3D, dmodel.Model, dmodel.Material))
    }


def _model_by_name(sections, name: str):
    h = hash_str(name)
    for s in sections:
        if s.tag == "model_data" and getattr(s.obj, "name_hash", None) == h:
            return s
    raise KeyError(f"model_data {name!r} not found")


def _object_by_name(sections, name: str):
    h = hash_str(name)
    for s in sections:
        if s.tag == "object3D" and getattr(s.obj, "name_hash", None) == h:
            return s
    return None


def _identity_matrix():
    m = [0.0] * 16
    m[0] = m[5] = m[10] = m[15] = 1.0
    return m


def _object3d_payload(name: str, parent_id: int) -> bytes:
    """Empty locator object3D (matches jack_fps.model's co_box exactly)."""
    w = bytearray()
    w += struct.pack("<Q", hash_str(name))
    w += struct.pack("<I", 0)                    # anim_ids count
    for v in _identity_matrix():
        w += struct.pack("<f", v)
    for v in (0.0, 0.0, 0.0):
        w += struct.pack("<f", v)
    w += struct.pack("<I", parent_id)
    return bytes(w)


def _serialize_object_prefix(o) -> bytes:
    """name_hash + anim_ids + matrix(with pos in row 4) + pos + parent_id."""
    w = bytearray()
    w += struct.pack("<Q", o.name_hash)
    w += struct.pack("<I", len(o.anim_ids))
    for aid, u in o.anim_ids:
        w += struct.pack("<I", aid) + struct.pack("<Q", u)
    rows = list(o.matrix)
    rows[12:15] = [o.pos[0], o.pos[1], o.pos[2]]
    for v in rows:
        w += struct.pack("<f", v)
    for v in o.pos:
        w += struct.pack("<f", v)
    w += struct.pack("<I", o.parent_id)
    return bytes(w)


# ---------------------------------------------------------------------------
# model surgery
# ---------------------------------------------------------------------------

def _chain_ids(md, by_id) -> list[int]:
    if getattr(md, "version", 3) == 6 or not hasattr(md, "passthrough_id"):
        return []  # version-6 (LOD/collision) models carry inline data
    ids = []
    pg = by_id.get(md.passthrough_id)
    if pg is not None:
        ids.append(pg.obj.geometry_id)
        ids.append(pg.obj.topology_id)
        ids.append(pg.id)
    if md.topologyip_id:
        ids.append(md.topologyip_id)
    if md.skinbones_id:
        ids.append(md.skinbones_id)
    return ids


def _arm_bone_ids(sections) -> set[int]:
    want = {hash_str(n) for n in ARM_BONE_NAMES}
    return {
        s.id
        for s in sections
        if s.tag == "object3D" and s.obj.name_hash in want
    }


def _vert_bones(geom, sb, vi) -> set[int]:
    """Bone object3D ids a vertex is bound to (palette-local blend indices)."""
    bones = set()
    mapping = sb.bone_mappings[0]  # identity in our models; per-atom maps match
    for j, w in zip(geom.joints[vi], geom.weights4(vi)):
        if w > 0.0 and j < len(mapping):
            slot = mapping[j]
            if slot < len(sb.object_ids):
                bones.add(sb.object_ids[slot])
    return bones


def select_arm_verts(md, geom, topo, sb, arm_ids: set[int]):
    """Verts touching the arm chains, closed over faces (watertight shell)."""
    selected = set()
    for atom in md.render_atoms:
        for vi in range(atom["base_vertex"], atom["base_vertex"] + atom["geo_len"]):
            if _vert_bones(geom, sb, vi) & arm_ids:
                selected.add(vi)
    for f0, f1, f2 in topo.faces:
        if f0 in selected or f1 in selected or f2 in selected:
            selected.update((f0, f1, f2))
    return selected


def rebuild_drawable(sections, by_id, raw_by_id, md_sec, keep_verts: set[int]):
    """Rewrite one drawable's chain in raw_by_id keeping only keep_verts.

    Face indices are global (verified against _trim_redundant_atoms).  Vertex
    order is preserved so per-atom blocks stay contiguous; atoms with no kept
    verts are dropped.  Geometry channels are sliced bit-exactly.
    """
    md = md_sec.obj
    pg_sec = by_id[md.passthrough_id]
    geom_sec = by_id[pg_sec.obj.geometry_id]
    topo_sec = by_id[pg_sec.obj.topology_id]
    geom, topo = geom_sec.obj, topo_sec.obj

    kept = sorted(v for v in keep_verts if v < geom.vert_count)
    if not kept:
        raise ValueError(f"{_nm(md)}: no vertices kept")
    remap = {old: new for new, old in enumerate(kept)}

    # ---- geometry: per-channel slices of kept vertices ----
    g_raw = bytes(raw_by_id[geom_sec.id])
    hdr_end = 8 + 8 * len(geom.headers)
    sizes = dmodel.DieselGeometry.RAID_SIZES if geom.format == "raid" else dmodel.DieselGeometry.PAYDAY_SIZES
    new_g = bytearray(struct.pack("<II", len(kept), len(geom.headers)))
    new_g += g_raw[8:hdr_end]
    ch_off = hdr_end
    for isz_code, _ity in geom.headers:
        isz = sizes[isz_code]
        for vi in kept:
            new_g += g_raw[ch_off + vi * isz : ch_off + (vi + 1) * isz]
        ch_off += geom.vert_count * isz
    new_g += g_raw[ch_off:]          # name hash + remaining
    raw_by_id[geom_sec.id] = new_g

    # ---- topology + atoms ----
    # kept preserves old order and atom ranges are contiguous, so the new
    # global layout is atom-major and face indices stay global (as in
    # _trim_redundant_atoms).
    new_faces: list[tuple[int, int, int]] = []
    new_atoms: list[dict[str, int]] = []
    new_base_v = 0
    new_base_idx = 0
    for atom in md.render_atoms:
        v0, vlen = atom["base_vertex"], atom["geo_len"]
        f0, fcnt = atom["base_index"] // 3, atom["tri_count"]
        atom_verts = [vi for vi in kept if v0 <= vi < v0 + vlen]
        if not atom_verts:
            continue
        block_map = {vi: new_base_v + i for i, vi in enumerate(atom_verts)}
        faces = [
            tuple(block_map[x] for x in tri)
            for tri in topo.faces[f0 : f0 + fcnt]
            if tri[0] in block_map and tri[1] in block_map and tri[2] in block_map
        ]
        new_faces.extend(faces)
        new_atoms.append(
            {
                "base_vertex": new_base_v,
                "tri_count": len(faces),
                "base_index": new_base_idx,
                "geo_len": len(atom_verts),
                "material_id": atom["material_id"],
            }
        )
        new_base_v += len(atom_verts)
        new_base_idx += len(faces) * 3

    new_t = bytearray(struct.pack("<II", topo.primitive, len(new_faces) * 3))
    for tri in new_faces:
        new_t += struct.pack("<3H", *tri)
    new_t += struct.pack("<I", len(topo.items2)) + topo.items2
    new_t += struct.pack("<Q", topo.name_hash) + topo.remaining
    raw_by_id[topo_sec.id] = new_t

    # ---- model payload ----
    w = bytearray(_serialize_object_prefix(md))
    w += struct.pack("<I", 3)                      # version
    w += struct.pack("<II", md.passthrough_id, md.topologyip_id)
    w += struct.pack("<I", len(new_atoms))
    for a in new_atoms:
        w += struct.pack(
            "<IIIII",
            a["base_vertex"], a["tri_count"], a["base_index"],
            a["geo_len"], a["material_id"],
        )
    w += struct.pack("<I", md.matgroup_id)
    w += struct.pack("<I", md.lightset_id)
    w += struct.pack("<I", md.properties)
    for v in list(md.bounds_min) + list(md.bounds_max):
        w += struct.pack("<f", v)
    w += struct.pack("<f", md.bounding_radius)
    w += struct.pack("<I", md.bounding_int)
    w += struct.pack("<I", md.skinbones_id)
    w += md.remaining
    raw_by_id[md_sec.id] = w

    # ---- skinbones: same palette, one identity mapping per new atom ----
    sb_sec = by_id[md.skinbones_id]
    sb = sb_sec.obj
    sw = bytearray()
    sw += struct.pack("<I", 1 + len(new_atoms))
    for _ in range(1 + len(new_atoms)):
        sw += struct.pack("<I", len(sb.object_ids))
        for i in range(len(sb.object_ids)):
            sw += struct.pack("<I", i)
    sw += struct.pack("<I", sb.root_bone_id)
    sw += struct.pack("<I", sb.count)
    for bid in sb.object_ids:
        sw += struct.pack("<I", bid)
    for rows in sb.rotations:
        for v in rows:
            sw += struct.pack("<f", v)
    for v in sb.global_skin_transform:
        sw += struct.pack("<f", v)
    sw += sb.remaining
    raw_by_id[sb_sec.id] = sw

    return new_atoms


def add_co_box(data: bytes) -> bytes:
    """Append an empty co_box object3D (child of root_point) to a .model."""
    sections, legacy, version, filesize, by_id = rp.parse_model_bytes(data)
    if any(
        s.tag == "object3D" and s.obj.name_hash == hash_str("co_box")
        for s in sections
    ):
        return data
    root = _object_by_name(sections, "root_point")
    if root is None:
        raise ValueError("model has no root_point")
    raw_by_id = {s.id: bytearray(data[s.start : s.end]) for s in sections}
    new_id = max(by_id) + 1
    body = bytearray()
    count = 0
    for s in sections:
        payload = bytes(raw_by_id[s.id])
        body += struct.pack("<III", s.type, s.id, len(payload)) + payload
        count += 1
    payload = _object3d_payload("co_box", root.id)
    body += struct.pack("<III", TAGS_INV["object3D"], new_id, len(payload)) + payload
    count += 1
    out = bytearray(struct.pack("<IIII", 0x42444F44, 1, 16 + len(body), count))
    out += body
    data, _fixed = rp.normalize_model_container(bytes(out))
    errors = rp.validate_model_skinning(data)
    if errors:
        raise ValueError("co_box insertion broke model: " + "; ".join(errors[:5]))
    return data


def build_fps_model(data: bytes, keep_models=("g_body", "g_hands")):
    """Full-body model -> arms-only FPS model on the same skeleton.

    Returns (fps_bytes, used_material_hashes).
    """
    sections, legacy, version, filesize, by_id = rp.parse_model_bytes(data)
    raw_by_id = {s.id: bytearray(data[s.start : s.end]) for s in sections}
    arm_ids = _arm_bone_ids(sections)

    keep_secs = set()
    used_mats: set[int] = set()
    mat_hashes = {
        s.id: s.obj.name_hash
        for s in sections
        if s.tag == "material"
    }
    for name in keep_models:
        md_sec = _model_by_name(sections, name)
        md = md_sec.obj
        pg = by_id[md.passthrough_id].obj
        geom = by_id[pg.geometry_id].obj
        topo = by_id[pg.topology_id].obj
        sb = by_id[md.skinbones_id].obj
        if name == "g_body":
            selected = select_arm_verts(md, geom, topo, sb, arm_ids)
            atoms = rebuild_drawable(sections, by_id, raw_by_id, md_sec, selected)
        else:
            # g_hands is already hands-only: keep the chain bit-exact
            atoms = md.render_atoms
        mg = by_id[md.matgroup_id].obj
        for a in atoms:
            used_mats.add(mat_hashes.get(mg.items[a["material_id"]], 0))
        keep_secs.add(md_sec.id)
        keep_secs.update(_chain_ids(md, by_id))

    # drop every other drawable chain (head/hair/vests/bags/collision)
    drop = set()
    for s in sections:
        if s.tag == "model_data" and s.id not in keep_secs:
            md = s.obj
            drop.add(s.id)
            drop.update(_chain_ids(md, by_id))
    drop.difference_update(keep_secs)

    root = _object_by_name(sections, "root_point")
    co_payload = _object3d_payload("co_box", root.id)
    new_id = max(by_id) + 1

    body = bytearray()
    count = 0
    for s in sections:
        if s.id in drop:
            continue
        payload = bytes(raw_by_id[s.id])
        body += struct.pack("<III", s.type, s.id, len(payload)) + payload
        count += 1
    body += struct.pack("<III", TAGS_INV["object3D"], new_id, len(co_payload)) + co_payload
    count += 1
    out = bytearray(struct.pack("<IIII", 0x42444F44, 1, 16 + len(body), count))
    out += body
    fps, _fixed = rp.normalize_model_container(bytes(out))
    errors = rp.validate_model_skinning(fps, strict_layout=True)
    if errors:
        raise ValueError("fps model invalid: " + "; ".join(errors[:5]))
    return fps, used_mats


# ---------------------------------------------------------------------------
# DDS icon (128x128 DXT5, no mips - matches jack.texture header)
# ---------------------------------------------------------------------------

def pack_icon_dds(image) -> bytes:
    import numpy as np
    from PIL import Image

    import dds

    img = image.convert("RGBA").resize((128, 128), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.uint8)
    payload = dds.encode_dxt5(arr)
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x00081007)   # CAPS|HEIGHT|WIDTH|PITCH|PIXELFORMAT
    struct.pack_into("<II", header, 12, 128, 128)
    struct.pack_into("<I", header, 20, 16384)       # pitch
    struct.pack_into("<I", header, 28, 0)           # no mipmaps
    struct.pack_into("<II", header, 76, 32, 0x4)    # ddspf size, FOURCC
    header[84:88] = b"DXT5"
    struct.pack_into("<I", header, 108, 0x00001000)  # caps: TEXTURE
    return bytes(header) + payload


# ---------------------------------------------------------------------------
# XML sidecars
# ---------------------------------------------------------------------------

def unit_xml(kind: str) -> str:
    path = UNIT_FPS if kind == "fps" else UNIT_BASE
    contour = "" if kind == "fps" else '\n\t\t<extension class="ContourExt" name="contour"/>'
    return (
        '<?xml version="1.0" ?>\n'
        f'<unit slot="1" type="{SKIN if kind != "fps" else SKIN + "_fps"}">\n'
        f'\t<object file="{path}" />\n'
        "\t<extensions>\n"
        '\t\t<extension class="ScriptUnitData" name="unit_data"/>'
        f"{contour}\n"
        "\t</extensions>\n"
        "</unit>\n"
    )


def object_xml(kind: str) -> str:
    materials = UNIT_FPS if kind == "fps" else UNIT_BASE
    if kind == "fps":
        objs = ["g_body", "g_hands"]
    else:
        objs = GRAPHICS_ENABLED + GRAPHICS_DISABLED
    lines = []
    for name in objs:
        if kind == "fps":
            lines.append(f'\t\t\t<object enabled="true" name="{name}"/>')
        else:
            enabled = "true" if name in GRAPHICS_ENABLED else "false"
            shadow = ' shadow_caster="true"' if name in SHADOW_CASTERS else ""
            lines.append(f'\t\t\t<object enabled="{enabled}" name="{name}"{shadow}/>')
    return (
        '<?xml version="1.0"?>\n'
        "<dynamic_object>\n"
        f'\t<diesel materials="{materials}" orientation_object="root_point" />\n'
        "\t<graphics>\n"
        '\t\t<graphic_group name="character" enabled="true" culling_object="co_box">\n'
        + "\n".join(lines)
        + "\n\t\t</graphic_group>\n"
        "\t</graphics>\n"
        "</dynamic_object>\n"
    )


_TEX_RE = re.compile(r'file="units/payday2/characters/shared_textures/lawson/([^"]+)"')


def material_configs(mtr_xml: str, fps_used: list[str]) -> tuple[str, str]:
    """TPP config: lawson_* materials verbatim with pack-local texture paths.

    FPS config: same materials restricted to what the arms use, rendered with
    the DEPTH_SCALING templates from jack_fps.material_config (contour vars
    dropped - first person has no contour).
    """
    blocks = re.findall(r"<material\b.*?</material\s*>", mtr_xml, re.S)
    keep = [b for b in blocks if re.search(r'name="lawson_', b)]
    if not keep:
        raise ValueError("no lawson_* materials in source material_config")

    def localize(block: str) -> str:
        return _TEX_RE.sub(lambda m: f'file="{TEX_BASE}/{m.group(1)}"', block)

    tpp_body = "\n".join(localize(b) for b in keep)
    tpp = (
        '<?xml version="1.0" ?>\n'
        f'<materials group="{SKIN}" version="3">\n'
        f"{tpp_body}\n"
        "</materials>\n"
    )

    fps_mats = []
    for b in keep:
        name = re.search(r'name="([^"]+)"', b).group(1)
        if name not in fps_used:
            continue
        b = localize(b)
        b = re.sub(r'render_template="[^"]*"', f'render_template="{BASIC_FPS}"', b)
        b = re.sub(r'\s*<variable\b[^>]*name="contour_[a-z_]+"[^>]*/>', "", b)
        fps_mats.append(b)
    if not fps_mats:
        raise ValueError("no materials used by fps arms")
    fps = (
        '<?xml version="1.0" ?>\n'
        f'<materials group="{SKIN}" version="3">\n'
        + "\n".join(fps_mats)
        + "\n</materials>\n"
    )
    return tpp, fps


def main_xml(texture_names: list[str]) -> str:
    tex_lines = "\n".join(
        f'\t\t<texture path="{TEX_BASE}/{name.removesuffix(".texture")}"/>'
        for name in sorted(texture_names)
    )
    chars = "\n".join(
        f'\t\t\t<{c}\tthird_unit="{UNIT_BASE}"/>' for c in CHARACTERS
    )
    return (
        f'<table name="Lawson" image="{ICON_PATH}" color="Color(0, 113, 177)">\n'
        '\t<AssetUpdates id="" version="1.0" provider="modworkshop"/>\n'
        '\t<Localization directory="localization" default="english.txt"/>\n'
        f'\t<GlobalValue id="{SKIN}" color="Color(0, 113, 177)"/>\n'
        f'\t<PlayerStyle id="{SKIN}" unit="{UNIT_FPS}" third_unit="{UNIT_BASE}" '
        'default_gloves="false" exclude_glove_adapter="true" '
        f'texture_bundle_folder="wardrobe_mod" global_value="{SKIN}">\n'
        '\t\t<third_body_replacement mask="true"\thead="true" armor="true" '
        'body="true" hands="true" arms="true" vest="true" glove_adapter="false"/>\n'
        '\t\t<body_replacement\t\tmask="true" head="true" armor="true" '
        'body="true" hands="true" arms="true" vest="true" glove_adapter="false"/>\n'
        "\t\t<characters>\n"
        f"{chars}\n"
        "\t\t</characters>\n"
        "\t</PlayerStyle>\n"
        '\n\t<AddFiles directory="assets">\n'
        f'\t\t<texture path="{ICON_PATH}"/>\n'
        f"{tex_lines}\n"
        f'\t\t<unit_mat path="{UNIT_BASE}"/>\n'
        f'\t\t<unit_mat path="{UNIT_FPS}"/>\n'
        "\t</AddFiles>\n"
        "</table>\n"
    )


def localization_txt() -> str:
    return (
        "{\n"
        f'"bm_suit_{SKIN}" : "Lawson"\n'
        f'"menu_l_global_value_{SKIN}" : "Miranda Lawson"\n'
        f'"bm_suit_{SKIN}_desc" : "The Illusive Woman."\n'
        "}\n"
    )


def readme_txt() -> str:
    return (
        "Lawson - Legendary Armour Skins outfit pack\n"
        "============================================\n"
        "\n"
        "Makes the Lawson model wearable as an armor/outfit skin (the same\n"
        "system as ModWorkShop 'Wardrobe Mod' / Legendary Armour Skins packs\n"
        "such as 'Yorha No. 2 Type B (2B) [LAS]').\n"
        "\n"
        "Requirements\n"
        "- SuperBLT\n"
        "- BeardLib\n"
        "- Legendary Armour Skins (Wardrobe Mod) by Cpone\n"
        "  https://modworkshop.net/mod/24006\n"
        "\n"
        "Install\n"
        "1. Install the requirements above.\n"
        "2. Extract this ZIP into PAYDAY 2\\assets\\mod_overrides\\ so that the\n"
        "   final layout is:\n"
        "     PAYDAY 2\\assets\\mod_overrides\\Lawson_LAS\\main.xml\n"
        "     PAYDAY 2\\assets\\mod_overrides\\Lawson_LAS\\assets\\...\n"
        "3. Restart the game, open Customize Armor (armor skin menu) and\n"
        "   equip 'Lawson'.\n"
        "\n"
        "Notes\n"
        "- Replaces body, head, hands, arms and vest in both third and first\n"
        "  person; the heister mask slot is taken by the skin's head.\n"
        "- First-person arms are cut from the rigged body (shoulders to\n"
        "  fingers) and skin to the standard heister FPS skeleton.\n"
        "- Not verified in-game at packaging time; test offline first.\n"
        "\n"
        "Remove\n"
        "With the game closed, move Lawson_LAS out of assets\\mod_overrides\\.\n"
    )


# ---------------------------------------------------------------------------
# source + assembly
# ---------------------------------------------------------------------------

def load_source(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        model_name = next(
            n for n in names if n.endswith("npc_criminal_female_1.model")
            and not n.endswith("_menu.model")
        )
        model = z.read(model_name)
        mtr_name = next(n for n in names if n.endswith("mtr_fem1.material_config"))
        mtr_xml = z.read(mtr_name).decode("utf-8")
        textures = {}
        for n in names:
            base = n.rsplit("/", 1)[-1]
            if base.endswith(".texture"):
                textures[base] = z.read(n)
    if len(textures) != 19:
        raise ValueError(f"expected 19 source textures, found {len(textures)}")
    return model, mtr_xml, textures


def build_pack(
    source_zip: Path,
    out_zip: Path,
    icon_png: Path,
    root_folder: str = MOD_NAME,
) -> dict:
    model, mtr_xml, textures = load_source(source_zip)

    tpp_model = add_co_box(model)
    fps_model, fps_used_hashes = build_fps_model(model)

    hash2name = {
        hash_str(n): n
        for n in re.findall(r'name="(lawson_[^"]+)"', mtr_xml)
    }
    fps_used = sorted({hash2name[h] for h in fps_used_hashes if h in hash2name})
    if not fps_used:
        raise ValueError("fps arms reference no lawson_* materials")
    tpp_mtr, fps_mtr = material_configs(mtr_xml, fps_used)

    from PIL import Image

    icon = pack_icon_dds(Image.open(icon_png))

    tex_names = sorted(textures)
    files = {
        "main.xml": main_xml(tex_names).encode("utf-8"),
        "localization/english.txt": localization_txt().encode("utf-8"),
        "README.txt": readme_txt().encode("utf-8"),
        f"assets/guis/dlcs/wardrobe_mod/textures/pd2/blackmarket/icons/player_styles/{SKIN}.texture": icon,
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}/{SKIN}.model": tpp_model,
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}/{SKIN}.unit": unit_xml("tpp").encode("utf-8"),
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}/{SKIN}.object": object_xml("tpp").encode("utf-8"),
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}/{SKIN}.material_config": tpp_mtr.encode("utf-8"),
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}_fps/{SKIN}_fps.model": fps_model,
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}_fps/{SKIN}_fps.unit": unit_xml("fps").encode("utf-8"),
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}_fps/{SKIN}_fps.object": object_xml("fps").encode("utf-8"),
        f"assets/units/wardrobe_mod/armor_skins/{SKIN}_fps/{SKIN}_fps.material_config": fps_mtr.encode("utf-8"),
    }
    for name in tex_names:
        files[f"assets/{TEX_BASE}/{name}"] = textures[name]

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, blob in sorted(files.items()):
            z.writestr(f"{root_folder}/{rel}", blob)

    return {
        "out": str(out_zip),
        "files": len(files),
        "tpp_model": len(tpp_model),
        "fps_model": len(fps_model),
        "fps_materials": fps_used,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=str(REPO / "dist" / "lawson_clover.zip"))
    ap.add_argument("--out", default=str(REPO / "dist" / "lawson_outfit.zip"))
    ap.add_argument("--icon", default=str(REPO / "Lawson model" / "Miranda_face_d.png"))
    args = ap.parse_args()

    info = build_pack(Path(args.source), Path(args.out), Path(args.icon))
    for k, v in info.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
