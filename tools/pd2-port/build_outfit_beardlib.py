#!/usr/bin/env python3
"""Build the additive BeardLib-native Lawson PlayerStyle (no LAS dependency).

Reuses the supplied repaired Clover pack; this does not re-rig the original OBJ.
The legacy outfit builder and its shipped ZIP remain byte-for-byte untouched.
Game compatibility still needs a real PAYDAY 2 test. See README.md and MODLOG.md.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from PIL import Image

import build_outfit as base
import dds
import dmodel
import repair_skin_palettes as rp

REPO = Path(__file__).resolve().parents[2]
MOD_NAME = "Lawson_Outfit_BeardLib"
STYLE_ID = "lawson_beardlib"
UNIT_DIR = f"units/mods/{STYLE_ID}"
TEX_DIR = f"{UNIT_DIR}/textures"
TPP_PATH = f"{UNIT_DIR}/lawson"
FPS_PATH = f"{UNIT_DIR}/lawson_fps"
ICON_PATH = f"guis/dlcs/{STYLE_ID}/textures/pd2/blackmarket/icons/player_styles/{STYLE_ID}"
DEFAULT_SOURCE = REPO / "dist/lawson_clover.zip"
DEFAULT_ICON = REPO / "Lawson model/Miranda_face_d.png"
DEFAULT_OUT = REPO / "dist/lawson_outfit_BeardLib.zip"
BEARDLIB_REF = "95eb1c0c84e3f07d36f28a5e69197ec3b5c59046"
GAME_LUA_REF = "e3a8b6168a8dca75ebe741cd77babd1080904032"
OLD_TEX_DIR = "units/payday2/characters/shared_textures/lawson/"
TPP_DRAWABLES = frozenset(base.GRAPHICS_ENABLED)
FPS_DRAWABLES = frozenset({"g_body", "g_hands"})
REPLACEMENTS = ("head", "body", "hands", "arms", "vest", "armor")
PROTECTED_ARCHIVES = tuple(REPO / "dist" / f"lawson_{name}.zip"
                           for name in ("bonnie", "clover", "sydney", "outfit")) + (REPO / "2b.rar",)


def xml_bytes(root: ET.Element) -> bytes:
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def validate_model(data: bytes) -> None:
    """Additional range checks, independent of the old validator's blind spots.

    This builder intentionally accepts only modern DODB input. Vertex references
    are UInt16; the topology's *index count* is UInt32, not limited to 65,535.
    This is structural validation, not proof the engine can animate the model.
    """
    if data[:8] != b"DODB\x01\x00\x00\x00":
        raise ValueError("Expected a repaired modern DODB version-1 model")
    sections, _, _, filesize, by_id = rp.parse_model_bytes(data)
    if filesize != len(data) or not sections or sections[-1].end != len(data):
        raise ValueError("Model container length mismatch")
    if len(by_id) != len(sections):
        raise ValueError("Duplicate model section IDs")
    errors = rp._check_section_refs(sections, by_id)
    if errors:
        raise ValueError("; ".join(errors))
    for sec in sections:
        if sec.tag != "model_data" or sec.obj.version == 6:
            continue
        md = sec.obj
        gp = by_id[md.passthrough_id].obj
        geo = by_id[gp.geometry_id].obj
        topo_sec = by_id[gp.topology_id]
        topo = topo_sec.obj
        vertex_count = len(geo.positions)
        index_count = struct.unpack_from("<I", data, topo_sec.start + 4)[0]
        if index_count != len(topo.faces) * 3:
            raise ValueError(f"Model {sec.id}: topology index count is not a triangle list")
        if any(not math.isfinite(v) for p in geo.positions for v in p):
            raise ValueError(f"Model {sec.id}: non-finite vertex position")
        if any(v >= vertex_count for face in topo.faces for v in face):
            raise ValueError(f"Model {sec.id}: vertex reference outside geometry")
        materials = by_id[md.matgroup_id].obj.items
        for atom in md.render_atoms:
            v0, v1 = atom["base_vertex"], atom["base_vertex"] + atom["geo_len"]
            i0, i1 = atom["base_index"], atom["base_index"] + atom["tri_count"] * 3
            if not (0 <= v0 <= v1 <= vertex_count):
                raise ValueError(f"Model {sec.id}: render-atom vertex range outside geometry")
            if i0 % 3 or not (0 <= i0 <= i1 <= index_count):
                raise ValueError(f"Model {sec.id}: render-atom index range outside topology")
            if atom["material_id"] >= len(materials):
                raise ValueError(f"Model {sec.id}: render-atom material outside material group")
            if any(not v0 <= v < v1 for face in topo.faces[i0 // 3:i1 // 3] for v in face):
                raise ValueError(f"Model {sec.id}: vertex reference outside render-atom range")
        if md.skinbones_id:
            if len(geo.joints) != vertex_count or len(geo.weights3) != vertex_count:
                raise ValueError(f"Model {sec.id}: missing skin channels")
            if any(not math.isfinite(w) for weights in geo.weights3 for w in weights):
                raise ValueError(f"Model {sec.id}: non-finite skin weight")
    errors = rp.validate_model_skinning(data, strict_layout=False)
    if errors:
        raise ValueError("; ".join(errors))


def select_arm_verts(md, geo, topo, skin, arm_ids: set[int]) -> set[int]:
    """Select arm-bound vertices plus ONE ring, never flood-fill in face order."""
    seeds = frozenset(
        i for atom in md.render_atoms
        for i in range(atom["base_vertex"], atom["base_vertex"] + atom["geo_len"])
        if base._vert_bones(geo, skin, i) & arm_ids
    )
    selected = set(seeds)
    for face in topo.faces:
        if any(v in seeds for v in face):
            selected.update(face)
    return selected


def material_hashes(data: bytes) -> set[int]:
    sections, _, _, _, by_id = rp.parse_model_bytes(data)
    used = set()
    for sec in sections:
        if sec.tag != "model_data" or sec.obj.version == 6:
            continue
        md = sec.obj
        group = by_id[md.matgroup_id].obj.items
        used.update(by_id[group[a["material_id"]]].obj.name_hash for a in md.render_atoms)
    return used


def prepare_model(data: bytes, *, first_person: bool) -> bytes:
    """Keep the heister skeleton, but remove unused mesh chains and materials."""
    validate_model(data)
    sections, _, _, _, by_id = rp.parse_model_bytes(data)
    names = FPS_DRAWABLES if first_person else TPP_DRAWABLES
    wanted = {base._model_by_name(sections, n).id for n in names}
    payloads = {s.id: bytearray(data[s.start:s.end]) for s in sections}
    keep_chain, keep_groups = set(), set()
    culling_positions = []
    for sid in wanted:
        md = by_id[sid].obj
        keep_chain.update(base._chain_ids(md, by_id))
        keep_groups.add(md.matgroup_id)
        gp = by_id[md.passthrough_id].obj
        geo, topo = by_id[gp.geometry_id].obj, by_id[gp.topology_id].obj
        if first_person and sid == base._model_by_name(sections, "g_body").id:
            selected = select_arm_verts(md, geo, topo, by_id[md.skinbones_id].obj, base._arm_bone_ids(sections))
            if not selected:
                raise ValueError("Arm selection is empty")
            base.rebuild_drawable(sections, by_id, payloads, by_id[sid], selected)
            culling_positions.extend(geo.positions[i] for i in sorted(selected))
        else:
            culling_positions.extend(geo.positions)

    drop = set()
    for sec in sections:
        if sec.tag == "model_data" and sec.id not in wanted:
            drop.add(sec.id)
            if sec.obj.version != 6:
                drop.update(set(base._chain_ids(sec.obj, by_id)) - keep_chain)
    keep_materials = {mid for gid in keep_groups for mid in by_id[gid].obj.items}
    drop.update(s.id for s in sections if s.tag == "material_group" and s.id not in keep_groups)
    drop.update(s.id for s in sections if s.tag == "material" and s.id not in keep_materials)

    # Use a real bounded drawable for culling, not an empty co_box locator.
    # Conservatively expand g_body's bounds to include every retained mesh.
    body = base._model_by_name(sections, "g_body")
    raw = bytearray(payloads[body.id])
    prefix_len = len(base._serialize_object_prefix(body.obj))
    atom_count = struct.unpack_from("<I", raw, prefix_len + 12)[0]
    bounds_off = prefix_len + 16 + 20 * atom_count + 12
    lo = [min(p[i] for p in culling_positions) for i in range(3)]
    hi = [max(p[i] for p in culling_positions) for i in range(3)]
    radius = math.sqrt(sum(max(abs(a), abs(b)) ** 2 for a, b in zip(lo, hi)))
    struct.pack_into("<7f", raw, bounds_off, *lo, *hi, radius)
    payloads[body.id] = bytes(raw)

    kept = [s for s in sections if s.id not in drop]
    result = bytearray(b"DODB" + struct.pack("<III", 1, 0, len(kept)))
    for sec in kept:
        payload = payloads[sec.id]
        result += struct.pack("<III", sec.type, sec.id, len(payload)) + payload
    struct.pack_into("<I", result, 8, len(result))
    normalized, _ = rp.normalize_model_container(bytes(result))
    validate_model(normalized)
    return normalized


def encode_texture(rgba: np.ndarray) -> bytes:
    h, w = rgba.shape[:2]
    if h != w:
        raise ValueError("Texture must be square")
    return dds.pack_dds(dds.mip_payloads_from_image(rgba), w)


def add_opacity_texture(textures: dict[str, bytes], source: str, target: str) -> None:
    # Pillow's BC3 decoder, not the legacy local BC1/BC3 shared color decoder.
    with Image.open(io.BytesIO(textures[source])) as image:
        alpha = np.array(image.convert("RGBA").getchannel("A"), dtype=np.uint8)
    rgba = np.stack((alpha, alpha, alpha, np.full_like(alpha, 255)), axis=-1)
    textures[target] = encode_texture(rgba)


def material_config(source: bytes | str, needed: set[int], textures: dict[str, bytes],
                    *, first_person: bool) -> bytes:
    original = ET.fromstring(source)
    available = {dmodel.hash_str(m.attrib["name"]): m for m in original.findall("material")}
    missing = needed - available.keys()
    if missing:
        raise ValueError(f"Missing source material definitions: {sorted(missing)}")
    root = ET.Element("materials", version="3", group=f"{STYLE_ID}{'_fps' if first_person else ''}")
    for name_hash in sorted(needed):
        material = copy.deepcopy(available[name_hash])
        name = material.attrib["name"]
        if name == "lawson_hair":
            add_opacity_texture(textures, "miranda_hair_d.texture", "lawson_hair_op.texture")
            material.find("opacity_texture").set("file", f"{TEX_DIR}/lawson_hair_op")
        if name == "lawson_lashes":
            # Use the game's existing alpha-masked Clover-hair shader permutation.
            # The supplied lashes carry transparency; an opaque body shader loses it.
            material = copy.deepcopy(next(m for m in original.findall("material")
                                          if m.attrib["name"] == "mtr_hair_2"))
            material.set("name", name)
            add_opacity_texture(textures, "hmf_hed_promiranda_lashes.texture", "lawson_lashes_op.texture")
            flat = np.full((4, 4, 4), (128, 128, 255, 255), dtype=np.uint8)
            textures["flat_normal.texture"] = encode_texture(flat)
            material.find("diffuse_texture").set("file", f"{TEX_DIR}/hmf_hed_promiranda_lashes")
            material.find("bump_normal_texture").set("file", f"{TEX_DIR}/flat_normal")
            material.find("opacity_texture").set("file", f"{TEX_DIR}/lawson_lashes_op")
            for var in material.findall("variable"):
                if var.get("name") == "alpha_ref":
                    var.set("value", "0.05")
                elif var.get("name") == "tint_color":
                    var.set("value", "1 1 1")
        for element in material.iter():
            path = element.get("file")
            if path and path.startswith(OLD_TEX_DIR):
                element.set("file", f"{TEX_DIR}/{path.removeprefix(OLD_TEX_DIR)}")
        if first_person:
            material.set("render_template", base.BASIC_FPS)
            for var in list(material.findall("variable")):
                if var.get("name", "").startswith("contour_"):
                    material.remove(var)
        root.append(material)
    for element in root.iter():
        path = element.get("file")
        if path and path.startswith(TEX_DIR + "/"):
            if path.removeprefix(TEX_DIR + "/") + ".texture" not in textures:
                raise ValueError(f"Missing material texture: {path}")
        elif path and not path.startswith("environments/cubemaps/"):
            raise ValueError(f"Unexpected external material resource: {path}")
    return xml_bytes(root)


def unit_xml(path: str, *, first_person: bool) -> bytes:
    root = ET.Element("unit", type=STYLE_ID + ("_fps" if first_person else ""), slot="1")
    ET.SubElement(root, "object", file=path)
    extensions = ET.SubElement(root, "extensions")
    ET.SubElement(extensions, "extension", name="unit_data", **{"class": "ScriptUnitData"})
    if not first_person:
        ET.SubElement(extensions, "extension", name="contour", **{"class": "ContourExt"})
    return xml_bytes(root)


def object_xml(path: str, *, first_person: bool) -> bytes:
    root = ET.Element("dynamic_object")
    ET.SubElement(root, "diesel", materials=path, orientation_object="root_point")
    graphics = ET.SubElement(root, "graphics")
    group = ET.SubElement(graphics, "graphic_group", name="character", enabled="true", culling_object="g_body")
    names = FPS_DRAWABLES if first_person else TPP_DRAWABLES
    for name in sorted(names):
        obj = ET.SubElement(group, "object", name=name, enabled="true")
        if name in base.SHADOW_CASTERS:
            obj.set("shadow_caster", "true")
    return xml_bytes(root)


def main_xml(texture_names: list[str]) -> bytes:
    root = ET.Element("table", name="Miranda Lawson Outfit — BeardLib", author="Universal Modder",
                      version="1.0.0", image=ICON_PATH)
    add = ET.SubElement(root, "AddFiles", directory="assets")
    for name in sorted(texture_names):
        ET.SubElement(add, "texture", path=f"{TEX_DIR}/{Path(name).stem}")
    ET.SubElement(add, "texture", path=ICON_PATH)
    for extension in ("model", "object", "material_config", "unit"):
        for path in (TPP_PATH, FPS_PATH):
            ET.SubElement(add, extension, path=path)
    loc = ET.SubElement(root, "Localization", directory="loc", default_language="english")
    ET.SubElement(loc, "localization", language="english", file="english.txt")
    ET.SubElement(root, "GlobalValue", id=STYLE_ID, name_id=f"bm_global_value_{STYLE_ID}",
                  desc_id=f"menu_l_global_value_{STYLE_ID}", dlc="false")
    style = ET.SubElement(root, "PlayerStyle", id=STYLE_ID, global_value=STYLE_ID,
                          texture_bundle_folder=STYLE_ID, unlocked="true", custom="true",
                          unit=FPS_PATH, third_unit=TPP_PATH, default_gloves="false",
                          exclude_glove_adapter="true")
    for field in ("body_replacement", "third_body_replacement"):
        ET.SubElement(style, field, {part: "true" for part in REPLACEMENTS})
    return xml_bytes(root)


def localization() -> bytes:
    return (json.dumps({
        f"bm_suit_{STYLE_ID}": "Miranda Lawson (BeardLib)",
        f"bm_suit_{STYLE_ID}_desc": "A standalone Lawson player style. Requires BeardLib, not Legendary Armour Skins.",
        f"bm_global_value_{STYLE_ID}": "Lawson Outfit — BeardLib",
        f"menu_l_global_value_{STYLE_ID}": "Custom Lawson outfit; offline validation only.",
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


PACK_README = """Miranda Lawson Outfit — BeardLib-native edition (experimental)
==============================================================

Requirements: PAYDAY 2 on PC, SuperBLT, and BeardLib with PlayerStyle support
(API checked against BeardLib 5.2.0). Legendary Armour Skins / Wardrobe Mod is
NOT required. This is a native outfit/player style, not an armor-skin texture.

Installation (manual; game closed)
---------------------------------
1. Back up the existing mod_overrides folder and your save/profile first.
2. Extract this ZIP into PAYDAY 2/assets/mod_overrides/.
   The resulting path must be:
   PAYDAY 2/assets/mod_overrides/Lawson_Outfit_BeardLib/main.xml
   Do not put it in mods/mod_overrides or add another enclosing ZIP-name folder.
3. Launch the game and open the Outfit / Player Styles list in Inventory.
   Select "Miranda Lawson (BeardLib)". For the supplied hands, use Default gloves.
4. First test in the inventory and an OFFLINE heist, including movement, weapon
   switching/reload, mask-on, outfit switching and several heisters/armors.

What is included
----------------
- Independent lawson_beardlib style ID, icons and resources. No vanilla heister
  asset paths are overridden; the old Lawson packs need not be installed.
- Third-person body/head/hair/hands/shadow and a separate first-person arm mesh.
- Both native first- and third-person body replacement maps. No runtime Lua
  hooks, LAS registration, updater, downloads, save edits or gameplay changes.
- Complete material coverage including shadow_caster; alpha-derived hair/lash
  opacity maps; a triangle-order-independent one-ring arm selection.

Important limits
----------------
- Structurally tested, NOT tested in PAYDAY 2. Rig, UV seams, hand/weapon alignment,
  culling, materials, VR, armor clipping and animations still need visual checks.
- This reuses the supplied Clover-rigged Lawson mesh. It is NOT a fresh rig or
  proof of an exact visual/behavioral match to the supplied 2B reference.
- Native PlayerStyle body replacement does NOT hide the separate equipped mask.
  Mask clipping is possible; there is deliberately no global mask-hiding hook.
- Non-default gloves may replace/overlap the supplied hands. Choose Default.
- Global unit fallback is configured for every heister, but individual skeletons
  and body proportions are unverified. VR and online synchronization are untested.
- Unique IDs avoid the old outfit's registration collision; simultaneous legacy
  character replacements or other appearance mods can still conflict. Start with
  those disabled for the offline test. Do not rely on unmodded peers seeing it.
- Asset authorship/redistribution permissions are not documented in the input.
  This private derivative is NOT a cleared public release; see CREDITS.txt.

Removal / rollback
------------------
Equip a vanilla outfit before removing this pack. Close the game, then remove
only assets/mod_overrides/Lawson_Outfit_BeardLib/. Do not remove shared loaders
or other Lawson folders. Restore your backup if necessary.

Rebuild: tools/pd2-port/build_outfit_beardlib.py in Man1nWhite/universal-modder.
BUILD_INFO.json records source hashes and generated payload hashes.
"""

PACK_CREDITS = """Source/provenance notice
========================
This is a private, experimental repack of the model and textures supplied in
Man1nWhite/universal-modder (repaired lawson_clover.zip / Lawson model assets).
The original Lawson mesh/texture author, extraction source and redistribution
license are not established by this repository. No ownership of those assets
is claimed; obtain the necessary permissions and attribution before publishing.
PAYDAY 2-derived skeleton/mesh data also remains subject to its owners' terms.
The unrelated 2b.rar example is not copied into this package.

Packaging/generation code: Universal Modder, with AI-assisted changes.
Runtime loaders are separate: SuperBLT and PAYDAY 2 BeardLib; neither is bundled.
No Legendary Armour Skins code, Wardrobe resources or game executable is bundled.
"""


def build_pack(source_zip: Path = DEFAULT_SOURCE, out_zip: Path = DEFAULT_OUT,
               icon_png: Path = DEFAULT_ICON) -> Path:
    source_zip, out_zip, icon_png = (Path(p).expanduser() for p in (source_zip, out_zip, icon_png))
    if out_zip.resolve() in {p.resolve() for p in (*PROTECTED_ARCHIVES, source_zip, icon_png)}:
        raise ValueError("Refusing to overwrite an existing Lawson pack or build input")
    with zipfile.ZipFile(source_zip) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Source ZIP contains duplicate entries")
        if archive.testzip() is not None:
            raise ValueError("Source ZIP has a CRC error")
    source_model, source_materials, textures = base.load_source(source_zip)
    tpp = prepare_model(source_model, first_person=False)
    fps = prepare_model(source_model, first_person=True)
    tpp_materials = material_config(source_materials, material_hashes(tpp), textures, first_person=False)
    fps_materials = material_config(source_materials, material_hashes(fps), textures, first_person=True)
    files = {
        "main.xml": main_xml(list(textures)),
        "loc/english.txt": localization(),
        "README.txt": PACK_README.encode("utf-8"),
        "CREDITS.txt": PACK_CREDITS.encode("utf-8"),
        f"assets/{TPP_PATH}.model": tpp,
        f"assets/{FPS_PATH}.model": fps,
        f"assets/{TPP_PATH}.material_config": tpp_materials,
        f"assets/{FPS_PATH}.material_config": fps_materials,
        f"assets/{TPP_PATH}.object": object_xml(TPP_PATH, first_person=False),
        f"assets/{FPS_PATH}.object": object_xml(FPS_PATH, first_person=True),
        f"assets/{TPP_PATH}.unit": unit_xml(TPP_PATH, first_person=False),
        f"assets/{FPS_PATH}.unit": unit_xml(FPS_PATH, first_person=True),
    }
    with Image.open(icon_png) as image:
        files[f"assets/{ICON_PATH}.texture"] = base.pack_icon_dds(image)
    files.update({f"assets/{TEX_DIR}/{name}": data for name, data in sorted(textures.items())})
    info = {
        "format_version": 1,
        "variant": "beardlib-native-player-style",
        "style_id": STYLE_ID,
        "runtime_verified": False,
        "builder": "tools/pd2-port/build_outfit_beardlib.py",
        "source_zip": source_zip.name,
        "source_sha256": hashlib.sha256(source_zip.read_bytes()).hexdigest(),
        "icon_sha256": hashlib.sha256(icon_png.read_bytes()).hexdigest(),
        "beardlib_api_ref": BEARDLIB_REF,
        "game_lua_ref": GAME_LUA_REF,
        "payload_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["BUILD_INFO.json"] = (json.dumps(info, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic content/order/timestamps; replace only after a complete write.
    with tempfile.NamedTemporaryFile(dir=out_zip.parent, suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, payload in sorted(files.items()):
                entry = zipfile.ZipInfo(f"{MOD_NAME}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, payload, compresslevel=9)
        os.replace(tmp_path, out_zip)
    finally:
        tmp_path.unlink(missing_ok=True)
    return out_zip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Repaired lawson_clover.zip")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Separate BeardLib ZIP output")
    parser.add_argument("--icon", type=Path, default=DEFAULT_ICON, help="PNG for the native outfit icon")
    args = parser.parse_args()
    path = build_pack(args.source, args.out, args.icon)
    print(f"Built {path} ({path.stat().st_size:,} bytes)")
    print("SuperBLT + BeardLib; no LAS. Offline structural validation only; game test required.")


if __name__ == "__main__":
    main()
