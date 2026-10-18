#!/usr/bin/env python3
"""Build the Lawson Legendary Armour Skins add-on: dist/lawson_outfit.zip.

Registers LegendaryArmours.lawson, as in the supplied 2B LAS reference, instead
of pretending a plain BeardLib PlayerStyle is LAS. LAS 4.x maps this entry to
las_lawson in the Outfit selector. Requires SuperBLT, BeardLib and LAS/Wardrobe.

The repair prunes unused drawable chains, supplies every used material (including
shadow_caster), culls against bounded g_body geometry, and cuts FPS arms with an
immutable one-ring selection. It preserves the source skeleton and TPP mesh; it
does NOT repair the user's reported Clover deformation/UV/rigging problems.
No PAYDAY 2 runtime is available: the rebuilt pack is an unverified candidate.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "pd2-port"))

import dmodel  # noqa: E402
import repair_skin_palettes as rp  # noqa: E402
from dmodel import hash_str  # noqa: E402
# Compatibility exports for existing callers and the independent native builder.
from outfit_model import (  # noqa: E402
    ARM_BONE_NAMES, GRAPHICS_ENABLED, GRAPHICS_DISABLED, SHADOW_CASTERS,
    FPS_DRAWABLES, TPP_DRAWABLES, _arm_bone_ids, _chain_ids,
    _model_by_name, _serialize_object_prefix, _vert_bones, rebuild_drawable,
    material_hashes, prepare_model, select_arm_verts, validate_model,
)

SKIN = "lawson"
MOD_NAME = "Lawson_LAS"
VERSION = "1.1.0-rc1"
LAS_STYLE_ID = f"las_{SKIN}"
CATEGORY = "lawson_las"
UNIT_BASE = f"units/wardrobe_mod/armor_skins/{SKIN}/{SKIN}"
UNIT_FPS = f"units/wardrobe_mod/armor_skins/{SKIN}_fps/{SKIN}_fps"
TEX_BASE = "units/wardrobe_mod/armor_skins/textures"
ICON_PATH = f"guis/dlcs/{CATEGORY}/armor_skins/{SKIN}"
STYLE_ICON_PATH = f"guis/dlcs/{CATEGORY}/textures/pd2/blackmarket/icons/player_styles/{LAS_STYLE_ID}"
BASIC_FPS = "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
OLD_TEX_DIR = "units/payday2/characters/shared_textures/lawson/"
BEARDLIB_REF = "95eb1c0c84e3f07d36f28a5e69197ec3b5c59046"
LAS_REF = "b7c38c1d358fe054df51201788126c25a0da1938"
DEFAULT_SOURCE = REPO / "dist/lawson_clover.zip"
DEFAULT_OUT = REPO / "dist/lawson_outfit.zip"
DEFAULT_ICON = REPO / "Lawson model/Miranda_face_d.png"
PROTECTED_INPUTS = tuple(REPO / "dist" / f"lawson_{name}.zip"
                         for name in ("bonnie", "clover", "sydney")) + (
                             REPO / "dist/lawson_outfit_BeardLib.zip", REPO / "2b.rar")


def xml_text(root: ET.Element) -> str:
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def build_fps_model(data: bytes):
    """Return the shared arms-only preparation and its actual material hashes."""
    result = prepare_model(data, first_person=True)
    return result, material_hashes(result)


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


def unit_xml(kind: str) -> str:
    fps = kind == "fps"
    root = ET.Element("unit", slot="1", type=SKIN + ("_fps" if fps else ""))
    ET.SubElement(root, "object", file=UNIT_FPS if fps else UNIT_BASE)
    extensions = ET.SubElement(root, "extensions")
    ET.SubElement(extensions, "extension", name="unit_data", **{"class": "ScriptUnitData"})
    if not fps:
        ET.SubElement(extensions, "extension", name="contour", **{"class": "ContourExt"})
    return xml_text(root)


def object_xml(kind: str) -> str:
    fps = kind == "fps"
    root = ET.Element("dynamic_object")
    ET.SubElement(root, "diesel", materials=UNIT_FPS if fps else UNIT_BASE,
                  orientation_object="root_point")
    group = ET.SubElement(ET.SubElement(root, "graphics"), "graphic_group",
                          name="character", enabled="true", culling_object="g_body")
    for name in sorted(FPS_DRAWABLES if fps else TPP_DRAWABLES):
        obj = ET.SubElement(group, "object", name=name, enabled="true")
        if not fps and name in SHADOW_CASTERS:
            obj.set("shadow_caster", "true")
    return xml_text(root)


def material_config(mtr_xml: str, needed: set[int], *, first_person: bool) -> str:
    """Define precisely the materials referenced by the prepared model.

    Disabled source meshes are removed rather than left referencing undefined
    materials. Missing definitions must fail the build, not the game at spawn.
    """
    original = ET.fromstring(mtr_xml)
    available = {}
    for material in original.findall("material"):
        name = material.get("name")
        if not name:
            raise ValueError("Source material has no name")
        key = hash_str(name)
        if key in available:
            raise ValueError(f"Duplicate source material {name}")
        available[key] = material
    missing = needed - available.keys()
    if missing:
        raise ValueError("Missing source material: " + ", ".join(f"{h:016x}" for h in sorted(missing)))
    root = ET.Element("materials", group=SKIN, version="3")
    for key in sorted(needed, key=lambda h: available[h].get("name")):
        material = copy.deepcopy(available[key])
        for texture in material.iter():
            path = texture.get("file", "")
            if path.startswith(OLD_TEX_DIR):
                texture.set("file", TEX_BASE + "/" + path.removeprefix(OLD_TEX_DIR))
        if first_person:
            material.set("render_template", BASIC_FPS)
            for variable in list(material):
                if variable.tag == "variable" and variable.get("name", "").startswith("contour_"):
                    material.remove(variable)
        root.append(material)
    return xml_text(root)


def main_xml(texture_names: list[str]) -> str:
    root = ET.Element("table", name="Miranda Lawson — LAS", version=VERSION,
                      author="Universal Modder", image=ICON_PATH)
    add = ET.SubElement(root, "AddFiles", directory="assets")
    for path in (ICON_PATH, STYLE_ICON_PATH):
        ET.SubElement(add, "texture", path=path)
    for name in sorted(texture_names):
        ET.SubElement(add, "texture", path=f"{TEX_BASE}/{Path(name).stem}")
    for path in (UNIT_BASE, UNIT_FPS):
        # BeardLib registers its built-in default cooked_physics for this alias;
        # do not invent or ship an empty physics blob or eagerly load physics.
        ET.SubElement(add, "unit_mat", path=path, auto_cp="true")
    loc = ET.SubElement(root, "Localization", directory="localization", default_language="english")
    ET.SubElement(loc, "localization", language="english", file="english.txt")
    hooks = ET.SubElement(root, "Hooks", directory="hooks")
    ET.SubElement(hooks, "hook", file="register_lawson.lua",
                  source_file="lib/tweak_data/armorskinstweakdata")
    return xml_text(root)


def registry_lua() -> str:
    # This is this add-on's own registration, not bundled LAS/framework code.
    return f'''-- Lawson LAS add-on. Requires Legendary Armour Skins / Wardrobe Mod.
-- The framework owns loading, mask hiding and character-visual hooks.
LegendaryArmours = LegendaryArmours or {{}}
LegendaryArmours.{SKIN} = {{
    category = "{CATEGORY}",
    name_id = "bm_askn_{SKIN}",
    desc_id = "bm_askn_{SKIN}_desc",
    unit = "{UNIT_BASE}",
    fps_unit = "{UNIT_FPS}",
    hide_mask = true,
    hide_armor = true,
    replace_all = true,
    fps_hide_armor = true,
    fps_replace_body = true
}}
'''


def localization_txt() -> str:
    return json.dumps({
        f"bm_menu_{CATEGORY}_armor_skins": "Lawson",
        f"bm_askn_{SKIN}": "Miranda Lawson",
        f"bm_askn_{SKIN}_desc": "Experimental Lawson LAS outfit. Source rig is not repaired.",
    }, indent=2) + "\n"


def readme_txt() -> str:
    return f'''Miranda Lawson — Legendary Armour Skins add-on ({VERSION}, experimental)
=======================================================================

Requires PAYDAY 2 on PC, SuperBLT, BeardLib and Legendary Armour Skins /
Wardrobe Mod (ModWorkShop #24006). Loaders/frameworks are NOT bundled.
LAS contract inspected against 4.1.9; your installed version is not known.
This is an actual LegendaryArmours registration, not a plain PlayerStyle
with LAS branding. LAS 4.x exposes it as [LAS] Miranda Lawson in the native
Outfit / Player Styles selector (internal id: {LAS_STYLE_ID}). Older LAS
versions may use their armor-skin menu. The no-LAS BeardLib edition remains
separate and uses a different item/resource namespace.

Install / upgrade (manual, game closed)
--------------------------------------
1. Back up your save/profile and mod_overrides folder. If possible, select a
   vanilla outfit before upgrading/removing an equipped custom outfit.
2. Move the OLD Lawson_LAS folder completely OUT of assets/mod_overrides.
   Do not merely rename it within mod_overrides: BeardLib may still load it.
   Do not overlay this ZIP onto the old folder or keep two copies enabled.
3. Extract to PAYDAY 2/assets/mod_overrides/ so the exact layout is:
   PAYDAY 2/assets/mod_overrides/{MOD_NAME}/main.xml
   PAYDAY 2/assets/mod_overrides/{MOD_NAME}/hooks/register_lawson.lua
4. Restart the game completely. Choose [LAS] Miranda Lawson in Outfits on
   LAS 4.x, with Default gloves. Do not select the obsolete plain 'lawson'
   style from the previous, mislabeled package. For the first test, disable
   other character replacements and the separate BeardLib Lawson edition.
5. Start with the menu preview only. If it crashes, stop and retain fresh
   crash.txt, crashlog.txt and the SuperBLT/BeardLib logs; record the exact
   game, BeardLib and LAS versions. Do not repeat the same crash three times.
   Only if the preview works, continue with a backed-up OFFLINE heist.

What changed
------------
- LAS owns registration, body replacement and hide_mask behavior, as in the
  supplied 2B example. No copied framework code or global visual patches.
- Only outfit drawables remain (TPP: 7, FPS: 2); unused character/collision/
  vest/bag/hair-variant drawable chains and their materials are pruned.
- Every remaining model material is defined, including shadow_caster.
- Real g_body culling geometry with conservative bounds; no empty co_box.
- FPS arm selection uses one immutable adjacency ring, not a face-order flood.
- Standard JSON localization, two menu-icon paths, deterministic/atomic ZIP,
  and source/payload hashes in BUILD_INFO.json.

Limits — NOT a verified game fix
-------------------------------
The original Lawson_LAS was reported to crash during menu unit spawning.
The rebuilt package addresses reproducible resource/registration defects;
no PAYDAY 2 runtime is available here to verify that the crash is gone.
It reuses the supplied Clover-rigged mesh, which the user reports is badly
broken visually. No re-rig, UV seam repair or weapon/hand alignment fix has
been performed. Do not mistake passing offline tests for good rendering.
Mask hiding depends on LAS and is unverified on your installed versions.
VR, other appearance mods, multiplayer and unmodded peers are untested.
This is a private derivative with unresolved asset redistribution rights;
see CREDITS.txt. The unrelated 2B model/textures are not included.

Rollback
--------
Equip a vanilla outfit if possible, close the game, and move only Lawson_LAS
out of assets/mod_overrides. Restore your backup if needed. Do not remove
shared loaders or delete saves. Keep the known-crashing old pack disabled.

Rebuild from repository root:
python tools/pd2-port/build_outfit.py
Output: dist/lawson_outfit.zip (root: Lawson_LAS)
'''


CREDITS = """Private source/provenance notice
===============================
Reuses the model and textures supplied in Man1nWhite/universal-modder's
lawson_clover.zip. Original mesh/texture authorship and redistribution rights
are unresolved; no ownership or permission to publish those assets is claimed.
PAYDAY 2-derived skeleton/mesh data remains subject to its owners' terms.
The supplied 2b.rar is a format reference only; none of its assets are copied.
Packaging code is AI-assisted Universal Modder work. SuperBLT, BeardLib and
Legendary Armour Skins / Wardrobe Mod by Cpone are separate dependencies.
No loader, framework source or game executable is bundled.
"""


def load_source(zip_path: Path):
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Source ZIP contains duplicate entries")
        if archive.testzip() is not None:
            raise ValueError("Source ZIP has a CRC error")
        models = [n for n in names if n.endswith("/npc_criminal_female_1.model")]
        configs = [n for n in names if n.endswith("/mtr_fem1.material_config")]
        if len(models) != 1 or len(configs) != 1:
            raise ValueError("Expected exactly one Clover model and material config")
        model = archive.read(models[0])
        mtr_xml = archive.read(configs[0]).decode("utf-8")
        textures = {}
        for name in names:
            base = name.rsplit("/", 1)[-1]
            if not base.endswith(".texture"):
                continue
            if base in textures:
                raise ValueError(f"Duplicate source texture basename: {base}")
            textures[base] = archive.read(name)
    if len(textures) != 19:
        raise ValueError(f"expected 19 source textures, found {len(textures)}")
    return model, mtr_xml, textures


def build_pack(source_zip: Path = DEFAULT_SOURCE, out_zip: Path = DEFAULT_OUT,
               icon_png: Path = DEFAULT_ICON, root_folder: str = MOD_NAME) -> dict:
    source_zip, out_zip, icon_png = (Path(p).expanduser() for p in (source_zip, out_zip, icon_png))
    protected = {p.resolve() for p in (*PROTECTED_INPUTS, source_zip, icon_png)}
    if out_zip.resolve() in protected:
        raise ValueError("Refusing to overwrite another Lawson pack or build input")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", root_folder):
        raise ValueError("root_folder must be one safe top-level folder name")
    model, mtr_xml, textures = load_source(source_zip)
    tpp_model = prepare_model(model, first_person=False)
    fps_model, fps_used = build_fps_model(model)
    tpp_mtr = material_config(mtr_xml, material_hashes(tpp_model), first_person=False)
    fps_mtr = material_config(mtr_xml, fps_used, first_person=True)
    from PIL import Image

    with Image.open(icon_png) as image:
        icon = pack_icon_dds(image)
    files = {
        "main.xml": main_xml(list(textures)).encode("utf-8"),
        "hooks/register_lawson.lua": registry_lua().encode("utf-8"),
        "localization/english.txt": localization_txt().encode("utf-8"),
        "README.txt": readme_txt().encode("utf-8"),
        "CREDITS.txt": CREDITS.encode("utf-8"),
        f"assets/{ICON_PATH}.texture": icon,
        f"assets/{STYLE_ICON_PATH}.texture": icon,
    }
    for kind, path, data, config in (("tpp", UNIT_BASE, tpp_model, tpp_mtr),
                                      ("fps", UNIT_FPS, fps_model, fps_mtr)):
        files.update({
            f"assets/{path}.model": data,
            f"assets/{path}.material_config": config.encode("utf-8"),
            f"assets/{path}.object": object_xml(kind).encode("utf-8"),
            f"assets/{path}.unit": unit_xml(kind).encode("utf-8"),
        })
    files.update({f"assets/{TEX_BASE}/{name}": data for name, data in sorted(textures.items())})
    info = {
        "format_version": 1,
        "version": VERSION,
        "variant": "legendary-armour-skins",
        "registry_key": SKIN,
        "las4_style_id": LAS_STYLE_ID,
        "runtime_verified": False,
        "repair_scope": "LAS registration and unit resources; NOT a re-rig or verified crash fix",
        "source_zip": source_zip.name,
        "source_sha256": hashlib.sha256(source_zip.read_bytes()).hexdigest(),
        "icon_sha256": hashlib.sha256(icon_png.read_bytes()).hexdigest(),
        "beardlib_api_ref": BEARDLIB_REF,
        "las_api_version": "4.1.9",
        "las_api_ref": LAS_REF,
        "builder": "tools/pd2-port/build_outfit.py",
        "payload_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["BUILD_INFO.json"] = (json.dumps(info, indent=2) + "\n").encode("utf-8")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=out_zip.parent, suffix=".zip", delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, payload in sorted(files.items()):
                entry = zipfile.ZipInfo(f"{root_folder}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, payload, compresslevel=9)
        os.replace(temporary, out_zip)
    finally:
        temporary.unlink(missing_ok=True)
    return {"out": str(out_zip), "files": len(files), "tpp_model": len(tpp_model),
            "fps_model": len(fps_model), "las4_style_id": LAS_STYLE_ID,
            "runtime_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--icon", type=Path, default=DEFAULT_ICON)
    args = parser.parse_args()
    info = build_pack(args.source, args.out, args.icon)
    for key, value in info.items():
        print(f"{key}: {value}")
    print("Requires SuperBLT + BeardLib + LAS. Offline candidate; not game-verified; source rig unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
