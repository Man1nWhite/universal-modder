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

DISPLAY_NAME = "Miranda Lawson"
DESCRIPTION = ("Miranda Lawson joins the Payday Gang. "
               "Legendary Armour Skins outfit, built from the L4D2 Rochelle model.")


class PackIdentity:
    """Everything that has to differ for a second LAS pack of the same outfit.

    Two LAS entries built from one source (the stock outfit and its bust
    variant) must not share a `LegendaryArmours` id, a category, a unit path or
    a `mod_overrides` folder name, or the game loads one and ignores the other.
    Passing a different identity through the same renderers keeps one verified
    registration contract for both packs.
    """

    def __init__(self, item_id: str, display_name: str, description: str,
                 pack_dir_name: str | None = None, category: str | None = None,
                 unit_base: str | None = None,
                 gui_base: str | None = None):
        self.item_id = item_id
        self.display_name = display_name
        self.description = description
        self.category = category or item_id
        self.pack_dir_name = pack_dir_name or f"{item_id}_LAS"
        self.unit_base = unit_base or f"units/{item_id}/skins/{item_id}"
        self.gui_base = gui_base or f"guis/dlcs/{item_id}/armor_skins"
        self.tpp_unit = f"{self.unit_base}/{item_id}"
        self.fps_unit = f"{self.unit_base}/fps_{item_id}"
        self.texture_prefix = item_id
        self.icon_name = item_id
        self.hook_file = f"{item_id}_las.lua"

    def __repr__(self) -> str:
        return f"PackIdentity({self.item_id!r}, {self.pack_dir_name!r})"


BASE_IDENTITY = PackIdentity(ITEM_ID, DISPLAY_NAME, DESCRIPTION,
                             pack_dir_name=PACK_DIR_NAME, category=CATEGORY,
                             unit_base=UNIT_BASE, gui_base=GUI_BASE)

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


def render_hook_lua(identity: PackIdentity | None = None) -> str:
    identity = identity or BASE_IDENTITY
    flags = ",\n".join(f"\t{k} = true" for k in FLAG_KEYS)
    return (
        "LegendaryArmours = LegendaryArmours or {}\n"
        "la = LegendaryArmours\n"
        "\n"
        f"la.{identity.item_id} = {{\n"
        f"\tcategory = \"{identity.category}\",\n"
        "\n"
        f'\tunit = "{identity.tpp_unit}",\n'
        f'\tfps_unit = "{identity.fps_unit}",\n'
        "\n"
        f"{flags}\n"
        "}\n"
    )


def render_localization(identity: PackIdentity | None = None) -> str:
    identity = identity or BASE_IDENTITY
    return json.dumps(
        {
            f"bm_menu_{identity.item_id}_armor_skins": identity.display_name,
            f"bm_askn_{identity.item_id}": identity.display_name,
            f"bm_askn_{identity.item_id}_desc": identity.description,
        },
        indent=2,
    )


# texture base name (on disk) -> role; the pack prefixes every stem with its id.
# `df_nm` pairs are registered by their BASE name (BeardLib appends `_df`/`_nm`
# itself, so registering `miranda_body_df` would make it look for
# `miranda_body_df_df`); standalone textures are registered by full stem.
DF_NM_PAIRS = ("body", "face", "head")
SINGLE_ROLES = ("eyes",)
TEXTURE_ROLES = tuple(f"{p}_{suffix}" for p in DF_NM_PAIRS
                      for suffix in ("df", "nm")) + SINGLE_ROLES
#: kept for callers that want the explicit file stems per pair
TEXTURE_PAIRS = {
    "body": ("miranda_body_df", "miranda_body_nm"),
    "face": ("miranda_face_df", "miranda_face_nm"),
    "head": ("miranda_head_df", "miranda_head_nm"),
}


def texture_stem(role: str, identity: PackIdentity) -> str:
    """`"body_df"` -> `"miranda_body_df"` (or `"miranda_busty_body_df"`)."""
    return f"{identity.texture_prefix}_{role}"


def df_nm_base(pair: str, identity: PackIdentity) -> str:
    """`"body"` -> `"miranda_body"` — the base name a `df_nm` entry registers."""
    return f"{identity.texture_prefix}_{pair}"


def render_main_xml(identity: PackIdentity | None = None) -> str:
    identity = identity or BASE_IDENTITY
    unit = identity.unit_base
    pairs = "\n".join(
        f'\t\t\t\t<df_nm path="{unit}/{df_nm_base(pair, identity)}"/>'
        for pair in DF_NM_PAIRS
    )
    singles = "\n".join(
        f'\t\t\t\t<texture path="{unit}/{texture_stem(role, identity)}"/>'
        for role in SINGLE_ROLES
    )
    return (
        f'<table name="{identity.display_name}" image="{identity.gui_base}/{identity.icon_name}">\n'
        "\n"
        '\t<Localization directory="localization" default="english.txt"/>\n'
        "\n"
        '\t<Hooks directory="hooks">\n'
        f'\t\t<hook file="{identity.hook_file}" source_file="{HOOK_SOURCE}"/>\n'
        "\t</Hooks>\n"
        "\n"
        '\t<AddFiles directory="assets">\n'
        "\n"
        f'\t\t\t\t<texture path="{identity.gui_base}/{identity.icon_name}"/>\n'
        f"{pairs}\n"
        f"{singles}\n"
        "\n"
        f'\t\t\t\t<unit_mat path="{identity.tpp_unit}"/>\n'
        f'\t\t\t\t<unit_mat path="{identity.fps_unit}"/>\n'
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


def render_material_config(base: str, fps: bool, identity: PackIdentity | None = None) -> str:
    """Material config per the ModWorkshop LAS/MOOG module guide.

    - root header carries ``version="3"`` and a ``group`` name;
    - third-person character materials use the guide's CONTOUR template with
      ``unique="true"`` and the contour variables (wall-outline support);
    - first-person materials match the guide's fps example (DEPTH_SCALING,
      no contour);
    - texture paths carry no file extension.
    """
    identity = identity or BASE_IDENTITY
    group = Path(base).name
    unit = identity.unit_base

    def mat(name: str, role: str, extra: str = "") -> str:
        if fps and name == "mtr_body":
            template = "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
        else:
            template = "generic:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
        return (
            f'    <material name="{name}" render_template="{template}" version="2">\n'
            f'        <diffuse_texture file="{unit}/{texture_stem(role + "_df", identity)}"/>\n'
            f'        <bump_normal_texture file="{unit}/{texture_stem(role + "_nm", identity)}"/>\n'
            f"{extra}"
            "    </material>\n"
        )

    def contour_mat(name: str, role: str) -> str:
        return (
            f'    <material name="{name}" unique="true" version="2"\n'
            '              render_template="generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{unit}/{texture_stem(role + "_df", identity)}"/>\n'
            f'        <bump_normal_texture file="{unit}/{texture_stem(role + "_nm", identity)}"/>\n'
            '        <variable value="1 1 1" type="vector3" name="contour_color"/>\n'
            '        <variable value="0" type="scalar" name="contour_opacity"/>\n'
            "    </material>\n"
        )

    skin_mat = contour_mat if not fps else mat
    parts = [
        f'<materials version="3" group="{group}">\n',
        "\n",
        skin_mat("mtr_body", "body"),
        "\n",
        skin_mat("mtr_face", "face"),
        "\n",
        skin_mat("mtr_head", "head"),
        "\n",
        skin_mat("mtr_hair", "head"),
        "\n",
        (
            '    <material name="mtr_eyes" render_template="generic:DIFFUSE_TEXTURE:'
            'SKINNED_3WEIGHTS" version="2">\n'
            f'        <diffuse_texture file="{unit}/{texture_stem("eyes", identity)}"/>\n'
            "    </material>\n"
        ),
        "\n",
        '    <material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n',
        "</materials>",
    ]
    return "".join(parts)


def retarget_textures(textures: dict[str, bytes],
                      identity: PackIdentity | None = None) -> dict[str, bytes]:
    """Rename base-pack texture files onto ``identity``'s stems.

    The base route stores ``miranda_body_df.texture``; a variant pack registers
    ``<id>_body_df.texture`` so both packs can sit in `mod_overrides/` at once
    without one silently replacing the other's resources.
    """
    identity = identity or BASE_IDENTITY
    out: dict[str, bytes] = {}
    for name, data in textures.items():
        stem = name[:-len(".texture")] if name.endswith(".texture") else name
        role = stem[len(ITEM_ID) + 1:] if stem.startswith(f"{ITEM_ID}_") else stem
        out[f"{texture_stem(role, identity)}.texture"] = data
    return out


def write_pack(
    out_root: Path,
    textures: dict[str, bytes],
    icon: bytes,
    inventory: dict,
    models_present: bool = False,
    identity: PackIdentity | None = None,
) -> Path:
    """Write the pack scaffold under ``out_root/<pack_dir_name>``.

    ``textures`` maps ``<name>.texture`` file names to DDS bytes. Returns the
    pack directory path.
    """
    identity = identity or BASE_IDENTITY
    pack = Path(out_root) / identity.pack_dir_name
    unit_dir = pack / "assets" / identity.unit_base
    gui_dir = pack / "assets" / identity.gui_base
    unit_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    (pack / "hooks").mkdir(exist_ok=True)
    (pack / "localization").mkdir(exist_ok=True)

    (pack / "main.xml").write_bytes(render_main_xml(identity).encode("utf-8"))
    (pack / "hooks" / identity.hook_file).write_bytes(
        render_hook_lua(identity).encode("utf-8"))
    (pack / "localization" / "english.txt").write_bytes(
        render_localization(identity).encode("utf-8"))

    (gui_dir / f"{identity.icon_name}.texture").write_bytes(icon)
    for name, data in sorted(textures.items()):
        if not name.endswith(".texture"):
            raise ValueError(f"texture name must end in .texture: {name}")
        (unit_dir / name).write_bytes(data)

    for unit_base, fps in ((identity.tpp_unit, False), (identity.fps_unit, True)):
        stem = Path(unit_base).name
        (unit_dir / f"{stem}.unit").write_bytes(render_unit_xml(unit_base).encode("utf-8"))
        (unit_dir / f"{stem}.object").write_bytes(render_object_xml(unit_base, fps).encode("utf-8"))
        (unit_dir / f"{stem}.material_config").write_bytes(
            render_material_config(unit_base, fps, identity).encode("utf-8")
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
        "pack": identity.pack_dir_name,
        "item_id": identity.item_id,
        "registration": {
            "hook_source": HOOK_SOURCE,
            "table": f"LegendaryArmours.{identity.item_id}",
            "flags": list(FLAG_KEYS),
            "unit": identity.tpp_unit,
            "fps_unit": identity.fps_unit,
        },
        "models_present": models_present,
        "runtime_verified": False,
        "source_inventory": inventory,
        "payload_sha256": payload,
    }
    (pack / "BUILD_INFO.json").write_text(json.dumps(build_info, indent=2, sort_keys=True) + "\n")
    return pack


def refresh_build_info(pack: Path, identity: PackIdentity | None = None, **overrides) -> None:
    """Re-hash the final pack tree into BUILD_INFO.json (call after adding models).

    ``models_present`` flips true automatically once the unit .model files
    exist; extra keyword overrides are merged into the stored info.
    """
    identity = identity or BASE_IDENTITY
    info_path = pack / "BUILD_INFO.json"
    info = json.loads(info_path.read_text()) if info_path.exists() else {}

    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    payload = {}
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "BUILD_INFO.json":
            payload[path.relative_to(pack).as_posix()] = sha256(path.read_bytes())
    info["payload_sha256"] = payload
    unit_dir = pack / "assets" / identity.unit_base
    models_present = ((unit_dir / f"{identity.item_id}.model").is_file()
                      and (unit_dir / f"fps_{identity.item_id}.model").is_file())
    info["models_present"] = models_present
    info.update(overrides)
    info_path.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")


def zip_pack(pack: Path) -> Path:
    """Zip the pack folder in installable layout (top-level = folder name).

    Reproducible: fixed timestamps and permissions so identical content
    yields an identical archive (release-integrity friendly).
    """
    import zipfile

    out = pack.with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(pack.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(pack.parent).as_posix(),
                                       date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, path.read_bytes())
    return out
