"""LAS (Legendary Armour Skins) pack scaffolding for the Miranda Lawson outfit.

Implements the registration contract of the reference pack `2b.rar` — a BeardLib
mod table with a hook on `lib/tweak_data/armorskinstweakdata` that creates a
`LegendaryArmours.<id>` entry with `unit` / `fps_unit` and full-body replacement
flags — with fresh IDs and paths:

    LegendaryArmours.miranda    units/miranda/skins/miranda/{miranda,fps_miranda}

The scaffold contains converted textures, the icon, registration and the
unit/object/material_config XMLs. Diesel `.model` authoring is the remaining
step (see README.md); until the two model files exist the scaffold ships a
WIP_DO_NOT_INSTALL.txt and `models_present` is false in BUILD_INFO.json.

Registration and packaging facts verified against the 2B reference and the
BeardLib/LAS sources listed in knowledge/games/payday-2/las-armor-skin-outfit.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ITEM_ID = "miranda"
CATEGORY = "miranda"
PACK_DIR_NAME = "Miranda_LAS"
UNIT_BASE = "units/miranda/skins/miranda"
GUI_BASE = "guis/dlcs/miranda/armor_skins"
TPP_UNIT = f"{UNIT_BASE}/miranda"
FPS_UNIT = f"{UNIT_BASE}/fps_miranda"
HOOK_SOURCE = "lib/tweak_data/armorskinstweakdata"

# Source material -> pack texture bases (df/nm pairs, BeardLib `df_nm` naming).
# The L4D2 `miranda_hair` material reuses the head textures; eyeballs use the
# iris map `miranda_eyes` (EyeRefract in Source; plain DIFFUSE here).
TEXTURE_PAIRS = {
    "body": ("miranda_body_df", "miranda_body_nm"),
    "face": ("miranda_face_df", "miranda_face_nm"),
    "head": ("miranda_head_df", "miranda_head_nm"),
}
SINGLE_TEXTURES = {
    "eyes": "miranda_eyes",
}

FLAG_KEYS = (
    "hide_mask",
    "hide_armor",
    "replace_all",
    "fps_hide_armor",
    "fps_replace_body",
)


def render_hook_lua() -> str:
    flags = ",\n".join(f"\t{k} = true" for k in FLAG_KEYS)
    return (
        "LegendaryArmours = LegendaryArmours or {}\n"
        "la = LegendaryArmours\n"
        "\n"
        f"la.{ITEM_ID} = {{\n"
        f"\tcategory = \"{CATEGORY}\",\n"
        "\n"
        f'\tunit = "{TPP_UNIT}",\n'
        f'\tfps_unit = "{FPS_UNIT}",\n'
        "\n"
        f"{flags}\n"
        "}\n"
    )


def render_localization() -> str:
    return json.dumps(
        {
            f"bm_menu_{ITEM_ID}_armor_skins": "Miranda Lawson",
            f"bm_askn_{ITEM_ID}": "Miranda Lawson",
            f"bm_askn_{ITEM_ID}_desc": (
                "Miranda Lawson joins the Payday Gang. "
                "Legendary Armour Skins outfit, built from the L4D2 Rochelle model."
            ),
        },
        indent=2,
    )


def render_main_xml() -> str:
    pairs = "\n".join(
        f'\t\t\t\t<df_nm path="{UNIT_BASE}/{base}"/>'
        for base, (_df, _nm) in (
            (f"miranda_{name}", pair) for name, pair in TEXTURE_PAIRS.items()
        )
    )
    singles = "\n".join(
        f'\t\t\t\t<texture path="{UNIT_BASE}/{tex}"/>'
        for tex in SINGLE_TEXTURES.values()
    )
    return (
        f'<table name="Miranda Lawson" image="{GUI_BASE}/miranda">\n'
        "\n"
        '\t<Localization directory="localization" default="english.txt"/>\n'
        "\n"
        '\t<Hooks directory="hooks">\n'
        f'\t\t<hook file="{ITEM_ID}_las.lua" source_file="{HOOK_SOURCE}"/>\n'
        "\t</Hooks>\n"
        "\n"
        '\t<AddFiles directory="assets">\n'
        "\n"
        f'\t\t\t\t<texture path="{GUI_BASE}/miranda"/>\n'
        f"{pairs}\n"
        f"{singles}\n"
        "\n"
        f'\t\t\t\t<unit_mat path="{TPP_UNIT}"/>\n'
        f'\t\t\t\t<unit_mat path="{FPS_UNIT}"/>\n'
        "\n"
        "\t\t\t\t</AddFiles>\n"
        "</table>\n"
    )


def render_unit_xml(unit_base: str) -> str:
    return (
        '<?xml version="1.0"?>\n'
        '<unit type="dah" slot="1">\n'
        f'\t<object file="{unit_base}" />\n'
        "\n"
        "\t<extensions>\n"
        '\t\t<extension name="unit_data" class="ScriptUnitData" />\n'
        '\t\t<extension name="contour" class="ContourExt"/>\n'
        "\t</extensions>\n"
        "</unit>"
    )


def render_object_xml(base: str, fps: bool) -> str:
    if fps:
        graphics = (
            '<graphic_group name="character" enabled="true" culling_object="c_block">\n'
            '\t\t\t<object name="g_body" enabled="true" />\n'
            '\t\t\t<object name="g_head" enabled="false" />\n'
            '\t\t\t<object name="g_head_lod1" enabled="false" />\n'
            '\t\t\t<object name="g_body_lod1" enabled="false" />\n'
            "\t\t"
        )
    else:
        graphics = (
            '<graphic_group name="character" enabled="true" culling_object="c_block">\n'
            '\t\t\t<object name="g_body_lod1" enabled="false" />\n'
            '\t\t\t<object name="g_body" enabled="true" />\n'
            '\t\t\t<object name="g_head_lod1" enabled="false" />\n'
            '\t\t\t<object name="g_head" enabled="true" />\n'
            "\t\t"
        )
    return (
        '<?xml version="1.0"?>\n'
        "<dynamic_object>\n"
        f'\t<diesel materials="{base}" orientation_object="root_point" />\n'
        "\n"
        "\t<graphics>\n"
        f"\t\t{graphics}\n"
        "\t</graphic_group>\n"
        "\t</graphics>\n"
        "</dynamic_object>\n"
    )


def render_material_config(base: str, fps: bool) -> str:
    def mat(name: str, pair: tuple[str, str], extra: str = "") -> str:
        df, nm = pair
        template = "generic:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
        if fps and name == "mtr_body":
            template = "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
        return (
            f'    <material name="{name}" render_template="{template}" version="2">\n'
            f'        <diffuse_texture file="{UNIT_BASE}/{df}"/>\n'
            f'        <bump_normal_texture file="{UNIT_BASE}/{nm}"/>\n'
            f"{extra}"
            "    </material>\n"
        )

    body_pair = TEXTURE_PAIRS["body"]
    face_pair = TEXTURE_PAIRS["face"]
    head_pair = TEXTURE_PAIRS["head"]
    eye_tex = SINGLE_TEXTURES["eyes"]
    parts = [
        '<materials version="3">\n',
        "\n",
        mat("mtr_body", body_pair),
        "\n",
        mat("mtr_face", face_pair),
        "\n",
        mat("mtr_head", head_pair),
        "\n",
        (
            '    <material name="mtr_hair" render_template="generic:DIFFUSE_TEXTURE:'
            'NORMALMAP:SKINNED_3WEIGHTS" version="2">\n'
            f'        <diffuse_texture file="{UNIT_BASE}/{head_pair[0]}"/>\n'
            f'        <bump_normal_texture file="{UNIT_BASE}/{head_pair[1]}"/>\n'
            "    </material>\n"
        ),
        "\n",
        (
            '    <material name="mtr_eyes" render_template="generic:DIFFUSE_TEXTURE:'
            'SKINNED_1WEIGHT" version="2">\n'
            f'        <diffuse_texture file="{UNIT_BASE}/{eye_tex}"/>\n'
            "    </material>\n"
        ),
        "\n",
        '    <material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n',
        "</materials>",
    ]
    return "".join(parts)


def write_pack(
    out_root: Path,
    textures: dict[str, bytes],
    icon: bytes,
    inventory: dict,
    models_present: bool = False,
) -> Path:
    """Write the pack scaffold under ``out_root/PACK_DIR_NAME``.

    ``textures`` maps ``<name>.texture`` file names to DDS bytes. Returns the
    pack directory path.
    """
    pack = Path(out_root) / PACK_DIR_NAME
    unit_dir = pack / "assets" / UNIT_BASE
    gui_dir = pack / "assets" / GUI_BASE
    unit_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    (pack / "hooks").mkdir(exist_ok=True)
    (pack / "localization").mkdir(exist_ok=True)

    (pack / "main.xml").write_bytes(render_main_xml().encode("utf-8"))
    (pack / "hooks" / f"{ITEM_ID}_las.lua").write_bytes(render_hook_lua().encode("utf-8"))
    (pack / "localization" / "english.txt").write_bytes(render_localization().encode("utf-8"))

    (gui_dir / "miranda.texture").write_bytes(icon)
    for name, data in sorted(textures.items()):
        if not name.endswith(".texture"):
            raise ValueError(f"texture name must end in .texture: {name}")
        (unit_dir / name).write_bytes(data)

    for unit_base, fps in ((TPP_UNIT, False), (FPS_UNIT, True)):
        stem = Path(unit_base).name
        (unit_dir / f"{stem}.unit").write_bytes(render_unit_xml(unit_base).encode("utf-8"))
        (unit_dir / f"{stem}.object").write_bytes(render_object_xml(unit_base, fps).encode("utf-8"))
        (unit_dir / f"{stem}.material_config").write_bytes(
            render_material_config(unit_base, fps).encode("utf-8")
        )

    if not models_present:
        (pack / "WIP_DO_NOT_INSTALL.txt").write_text(
            "Work in progress: the Diesel .model files (miranda.model / fps_miranda.model)\n"
            "are not generated yet. This scaffold validates registration and converted\n"
            "textures only. Installing it in PAYDAY 2 without the models will break the\n"
            "outfit selection. See tools/pd2-las/README.md for the remaining work.\n"
        )

    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    payload = {}
    for path in sorted(pack.rglob("*")):
        if path.is_file():
            payload[path.relative_to(pack).as_posix()] = sha256(path.read_bytes())
    build_info = {
        "pack": PACK_DIR_NAME,
        "item_id": ITEM_ID,
        "registration": {
            "hook_source": HOOK_SOURCE,
            "table": f"LegendaryArmours.{ITEM_ID}",
            "flags": list(FLAG_KEYS),
            "unit": TPP_UNIT,
            "fps_unit": FPS_UNIT,
        },
        "models_present": models_present,
        "runtime_verified": False,
        "source_inventory": inventory,
        "payload_sha256": payload,
    }
    (pack / "BUILD_INFO.json").write_text(json.dumps(build_info, indent=2, sort_keys=True) + "\n")
    return pack
