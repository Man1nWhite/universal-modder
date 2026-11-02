"""Tests for the Skyrim -> PAYDAY 2 material pipeline.

`skyrim_materials.py` and `bw_pack.py` are the two places where a mistake is
invisible offline but fatal on a Windows machine: a swapped normal channel, a
missing mip level, a material name that no model references, or a Lua hook that
registers under the wrong table. Everything here is synthetic so the suite runs
without the outfit archives.
"""

from __future__ import annotations

import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
sys.path.insert(0, str(ROOT / "tools" / "pd2-port"))

import bw_pack  # noqa: E402
import skyrim_materials as sm  # noqa: E402


# --------------------------------------------------------------- fixtures
def flat(size: int, rgb: tuple[int, int, int], alpha: int = 255) -> np.ndarray:
    img = np.empty((size, size, 4), np.uint8)
    img[..., :3] = rgb
    img[..., 3] = alpha
    return img


def test_diffuse_keeps_colour_and_replaces_alpha_with_gloss():
    """Skyrim puts opacity in diffuse alpha; PD2 puts gloss there."""
    diffuse = flat(8, (17, 34, 51), alpha=0)      # fully "transparent" source
    normal = flat(8, (128, 128, 255), alpha=200)  # strong specular
    spec = sm.MaterialSpec("mtr_x", "d", "n", gloss_scale=0.5, gloss_floor=10)

    out = sm.build_diffuse(diffuse, normal[..., 3], None, spec, 8)

    assert tuple(out[0, 0, :3]) == (17, 34, 51)
    assert int(out[0, 0, 3]) == 100               # 200 * 0.5, not the source 0
    assert out.shape == (8, 8, 4) and out.dtype == np.uint8


def test_gloss_floor_stops_fabric_going_flat_black():
    """A DXT5 alpha of 0 reads as 'matte', which kills the sheen completely."""
    spec = sm.MaterialSpec("mtr_x", "d", "n", gloss_scale=0.5, gloss_floor=24)
    out = sm.build_diffuse(flat(8, (10, 10, 10)), np.zeros((8, 8), np.uint8),
                           None, spec, 8)
    assert int(out[0, 0, 3]) == 24


def test_metal_mask_lifts_gloss():
    spec = sm.MaterialSpec("mtr_x", "d", "n", "m", gloss_scale=0.5, gloss_floor=1)
    base = flat(8, (10, 10, 10))
    normal = flat(8, (128, 128, 255), alpha=100)[..., 3]
    matte = sm.build_diffuse(base, normal, flat(8, (0, 0, 0)), spec, 8)
    gold = sm.build_diffuse(base, normal, flat(8, (255, 255, 255)), spec, 8)
    assert int(matte[0, 0, 3]) == 50              # 100 * 0.5, no metal
    assert int(gold[0, 0, 3]) == 110              # 100 * 0.5 * 2.2


def test_missing_normal_leaves_the_surface_polished():
    """No normal map means no specular mask: the gloss comes from the scale only."""
    spec = sm.MaterialSpec("mtr_x", "d", None, gloss_scale=1.0)
    out = sm.build_diffuse(flat(8, (10, 20, 30)), None, None, spec, 8)
    assert int(out[0, 0, 3]) == 255


def test_normal_moves_x_to_alpha_and_flips_y_for_pd2():
    src = flat(8, (64, 200, 255))                 # +X, +Y (DirectX tangent space)
    out = sm.build_normal(src, 8, invert_y=True)
    assert out[0, 0, 0] == 255                    # R is unused by the shader
    assert out[0, 0, 2] == 0                      # B is unused
    assert int(out[0, 0, 3]) == 64                # X -> alpha
    assert int(out[0, 0, 1]) == 55                # 255 - 200


def test_normal_can_keep_y_when_the_source_is_opengl_like():
    out = sm.build_normal(flat(8, (64, 200, 255)), 8, invert_y=False)
    assert int(out[0, 0, 1]) == 200


def test_resize_handles_single_channel_masks():
    """The metal masks are 16x16 and must scale up to the diffuse size."""
    mask = np.full((16, 16, 1), 128, np.uint8)
    out = sm._resize(mask, 64)
    assert out.shape == (64, 64, 1)
    assert int(out[30, 30, 0]) == pytest.approx(128, abs=2)


# ------------------------------------------------------------------- DDS
def test_dds_has_every_mip_level_and_dxt5_fourcc():
    img = flat(64, (90, 90, 90))
    data = sm.encode_dds(img)
    assert data[:4] == b"DDS "
    assert data[84:88] == b"DXT5"
    width, height = struct.unpack_from("<II", data, 12)
    mips = struct.unpack_from("<I", data, 28)[0]
    assert (width, height, mips) == (64, 64, 7)   # 64..1
    expected = sum(max(1, (64 >> i) // 4) ** 2 * 16 for i in range(7))
    assert len(data) - 128 == expected


def test_dds_downsampling_halves_until_one_texel():
    levels = [flat(16, (1, 2, 3))]
    while min(levels[-1].shape[:2]) > 1:
        levels.append(sm._downsample(levels[-1]))
    assert [lv.shape[0] for lv in levels] == [16, 8, 4, 2, 1]


def test_dds_round_trips_through_the_decoder():
    from dds import decode_dxt5

    img = flat(16, (200, 40, 60), alpha=128)
    data = sm.encode_dds(img)
    decoded = decode_dxt5(data[128:], 16, 16)
    assert decoded.shape[:2] == (16, 16)
    for got, want in zip(decoded[8, 8, :4], (200, 40, 60, 128)):
        assert abs(int(got) - want) <= 8          # DXT5 is lossy


# ------------------------------------------------------- material_config
def test_material_config_is_valid_xml_with_one_entry_per_spec():
    specs = [sm.MaterialSpec("mtr_body", "", "", generated=True),
             sm.MaterialSpec("mtr_jacket", "Jacket_diffA", "Jacket_norm")]
    text = sm.render_material_config("units/x/skins/x", specs)
    root = ET.fromstring(text)
    assert root.tag == "materials" and root.get("version") == "3"
    names = [m.get("name") for m in root.findall("material")]
    assert names == ["mtr_body", "mtr_jacket", "shadow_caster"]


def test_material_config_paths_point_at_the_pack_rename():
    specs = [sm.MaterialSpec("mtr_jacket2", "Jacket2_diffA", "Jacket2_norm")]
    root = ET.fromstring(sm.render_material_config("units/x/skins/x", specs))
    mat = root.find("material")
    assert mat.find("diffuse_texture").get("file") == "units/x/skins/x/bw_jacket2_df"
    assert mat.find("bump_normal_texture").get("file") == "units/x/skins/x/bw_jacket2_nm"


def test_every_material_uses_a_known_render_template():
    """An unknown keyword combination renders the material black."""
    specs = [sm.MaterialSpec("mtr_body", "", "", generated=True)]
    for text in (sm.render_material_config("units/x/skins/x", specs),
                 sm.render_fps_material_config("units/x/skins/x", specs)):
        root = ET.fromstring(text)
        for mat in root.findall("material"):
            template = mat.get("render_template")
            if mat.get("name") == "shadow_caster":
                continue
            assert "DIFFUSE_TEXTURE" in template
            assert "SKINNED_3WEIGHTS" in template
            assert template.count(":") == template.count(":")  # shape check below
            keywords = template.split(":")[1:]
            assert set(keywords) <= {
                "CONTOUR", "DIFFUSE_TEXTURE", "NORMALMAP", "SKINNED_3WEIGHTS",
                "DEPTH_SCALING", "ALPHA_MASKED", "EXTERNAL_ALPHA_REF",
            }


def test_templates_follow_the_guide():
    """The LAS guide's contract; a typo here renders the material black."""
    assert sm.TPL_TPP == "generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
    assert sm.TPL_FPS == (
        "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS")


def test_contour_materials_are_unique_and_carry_their_variables():
    """Without `unique` + both variables the wall outline bugs out in game."""
    specs = [sm.MaterialSpec("mtr_body", "", "", generated=True)]
    root = ET.fromstring(sm.render_material_config("units/x/skins/x", specs))
    mat = root.find("material")
    assert root.get("group") == "x"
    assert mat.get("unique") == "true"
    variables = {v.get("name"): v.get("type") for v in mat.findall("variable")}
    assert variables == {"contour_color": "vector3", "contour_opacity": "scalar"}


def test_fps_template_scales_depth_and_drops_contour():
    specs = [sm.MaterialSpec("mtr_body", "", "", generated=True)]
    root = ET.fromstring(sm.render_fps_material_config("units/x/skins/x", specs))
    template = root.find("material").get("render_template")
    assert "DEPTH_SCALING" in template and "CONTOUR" not in template
    assert sm.TPL_FPS.split(":")[0] == "generic"


# ------------------------------------------------------------------ pack
def test_hook_registers_the_table_las_reads():
    lua = bw_pack.render_hook_lua()
    assert "LegendaryArmours = LegendaryArmours or {}" in lua
    assert f"la.{bw_pack.ITEM_ID} = {{" in lua
    assert f'unit = "{bw_pack.TPP_UNIT}"' in lua
    # the hook is what LAS actually looks the unit up by, so pin the literal
    assert 'unit = "units/businesswoman/skins/businesswoman/businesswoman"' in lua
    assert "fps_unit" not in lua                 # no FPS arms yet
    for flag in bw_pack.FLAG_KEYS:
        assert f"{flag} = true" in lua
    # replace_all sets third_body_replacement.head, and this unit has no head
    assert "replace_all" not in lua
    assert "replace_body = true" in lua


def test_hook_declares_fps_unit_only_when_one_is_built():
    with_fps = bw_pack.render_hook_lua(with_fps=True)
    assert f'fps_unit = "{bw_pack.FPS_UNIT}"' in with_fps


def test_main_xml_lists_textures_and_unit_materials():
    root = ET.fromstring(bw_pack.render_main_xml(
        ["bw_body_df", "bw_body_nm", "bw_jacket_df", "bw_jacket_nm"]))
    df_nm = [e.get("path") for e in root.iter("df_nm")]
    # the stem, not the _df file: the engine appends the suffix itself
    assert df_nm == [f"{bw_pack.UNIT_BASE}/bw_body",
                     f"{bw_pack.UNIT_BASE}/bw_jacket"]
    assert not any(p.endswith("_df") for p in df_nm)
    unit_mat = [e.get("path") for e in root.iter("unit_mat")]
    assert unit_mat == [bw_pack.TPP_UNIT]
    # pinned as a literal: asserting the constant against itself let a
    # truncated path (units/businesswoman/skins/businesswoman, no file stem)
    # pass the suite while loading nothing in game
    assert unit_mat == ["units/businesswoman/skins/businesswoman/businesswoman"]
    assert not unit_mat[0].endswith("skins/businesswoman")
    hook = root.find("Hooks/hook")
    assert hook.get("file") == f"{bw_pack.ITEM_ID}_las.lua"
    assert hook.get("source_file") == bw_pack.HOOK_SOURCE


def test_object_xml_points_diesel_at_the_material_config():
    root = ET.fromstring(bw_pack.render_object_xml(
        bw_pack.TPP_UNIT, ["s_body", "g_body_lod1", "g_body"]))
    diesel = root.find("diesel")
    assert diesel.get("materials") == bw_pack.TPP_UNIT
    assert diesel.get("materials") == "units/businesswoman/skins/businesswoman/businesswoman"
    objects = {o.get("name"): o.get("enabled") for o in root.iter("object")}
    assert objects == {"g_body": "true", "g_body_lod1": "false"}


def test_object_xml_only_lists_drawables_that_exist():
    """A name with no drawable behind it is a log error at best."""
    root = ET.fromstring(bw_pack.render_object_xml(
        bw_pack.TPP_UNIT, ["s_body", "g_body"]))
    names = [o.get("name") for o in root.iter("object")]
    assert "g_head" not in names and "g_head_lod1" not in names
    assert "s_body" not in names                  # engine-owned shadow mesh


def test_unit_xml_declares_the_extensions_las_needs():
    root = ET.fromstring(bw_pack.render_unit_xml(bw_pack.TPP_UNIT))
    assert root.get("type") == "dah"
    assert [e.get("class") for e in root.iter("extension")] == [
        "ScriptUnitData", "ContourExt"]


def test_localization_covers_all_three_strings():
    strings = json.loads(bw_pack.render_localization())
    assert set(strings) == {
        f"bm_menu_{bw_pack.ITEM_ID}_armor_skins",
        f"bm_askn_{bw_pack.ITEM_ID}",
        f"bm_askn_{bw_pack.ITEM_ID}_desc",
    }


# ------------------------------------------------------------- end to end
def _dummy_icon() -> bytes:
    import io

    from PIL import Image

    from dds_encode import rgba_to_bc3_dds

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 20, 24)).save(buf, format="PNG")
    return rgba_to_bc3_dds(np.asarray(
        Image.new("RGBA", (32, 32), (200, 180, 160))).astype(np.uint8))


def test_write_pack_is_self_consistent(tmp_path):
    specs = [sm.MaterialSpec("mtr_body", "", "", generated=True)]
    textures = {"bw_body_df": b"\0" * 16, "bw_body_nm": b"\0" * 16}
    pack = bw_pack.write_pack(
        tmp_path, b"MODEL", textures, _dummy_icon(),
        sm.render_material_config(bw_pack.TPP_UNIT, specs), None,
        extra={"private": True}, drawables=["s_body", "g_body"],
    )
    unit = pack / "assets" / bw_pack.UNIT_BASE

    assert (unit / f"{bw_pack.ITEM_ID}.model").read_bytes() == b"MODEL"
    assert (unit / "bw_body_df.texture").exists()
    assert not (unit / f"fps_{bw_pack.ITEM_ID}.model").exists()

    info = json.loads((pack / "BUILD_INFO.json").read_text())
    assert info["fps_available"] is False
    assert info["runtime_verified"] is False      # nothing ships without a PC run
    assert info["private"] is True
    # the manifest cannot hash itself
    assert "BUILD_INFO.json" not in info["payload_sha256"]
    import hashlib
    for rel, want in info["payload_sha256"].items():
        assert hashlib.sha256((pack / rel).read_bytes()).hexdigest() == want, rel
    assert set(info["payload_sha256"]) == {
        "main.xml",
        "hooks/businesswoman_las.lua", "localization/english.txt",
        f"assets/{bw_pack.UNIT_BASE}/{bw_pack.ITEM_ID}.model",
        f"assets/{bw_pack.UNIT_BASE}/{bw_pack.ITEM_ID}.unit",
        f"assets/{bw_pack.UNIT_BASE}/{bw_pack.ITEM_ID}.object",
        f"assets/{bw_pack.UNIT_BASE}/{bw_pack.ITEM_ID}.material_config",
        f"assets/{bw_pack.UNIT_BASE}/bw_body_df.texture",
        f"assets/{bw_pack.UNIT_BASE}/bw_body_nm.texture",
        f"assets/{bw_pack.GUI_BASE}/{bw_pack.ITEM_ID}.texture",
    }


def test_rebuild_drops_files_from_the_previous_build(tmp_path):
    """A pack that shrank must not keep the old build's textures in the zip."""
    specs = [sm.MaterialSpec("mtr_body", "", "", generated=True)]
    config = sm.render_material_config(bw_pack.TPP_UNIT, specs)
    textures = {"bw_body_df": b"\0" * 16, "bw_body_nm": b"\0" * 16,
                "bw_jacket_df": b"\0" * 16}
    pack = bw_pack.write_pack(tmp_path, b"MODEL", textures, _dummy_icon(),
                              config, None, drawables=["g_body"])
    assert (pack / "assets" / bw_pack.UNIT_BASE / "bw_jacket_df.texture").exists()

    # drop the jacket and rebuild into the same folder
    pack = bw_pack.write_pack(tmp_path, b"MODEL",
                              {"bw_body_df": b"\0" * 16, "bw_body_nm": b"\0" * 16},
                              _dummy_icon(), config, None, drawables=["g_body"])
    assert not (pack / "assets" / bw_pack.UNIT_BASE / "bw_jacket_df.texture").exists()


def test_zip_is_reproducible(tmp_path):
    pack_a = tmp_path / "a" / bw_pack.PACK_DIR_NAME
    pack_a.mkdir(parents=True)
    (pack_a / "main.xml").write_text("<table/>")
    zip_a = bw_pack.zip_pack(pack_a)

    pack_b = tmp_path / "b" / bw_pack.PACK_DIR_NAME
    pack_b.mkdir(parents=True)
    (pack_b / "main.xml").write_text("<table/>")
    zip_b = bw_pack.zip_pack(pack_b)

    assert zip_a.read_bytes() == zip_b.read_bytes()


def test_icon_crop_stays_inside_the_preview_sheet():
    import io

    from PIL import Image

    buf = io.BytesIO()
    sheet = Image.new("RGB", (1600, 400), (15, 15, 18))
    for i in range(4):                            # four views, centred figures
        for x in range(160 + i * 400, 240 + i * 400):
            for y in range(40, 380):
                sheet.putpixel((x, y), (200, 170, 150))
    sheet.save(buf, format="PNG")
    data = bw_pack.build_icon(buf.getvalue(), size=64)
    assert data[:4] == b"DDS "
    assert struct.unpack_from("<II", data, 12) == (64, 64)


def test_every_path_the_pack_references_exists(tmp_path):
    """A truncated path is invisible offline and renders nothing in game.

    The suite passed while main.xml, the hook and the object file all pointed
    at `units/businesswoman/skins/businesswoman` — a directory, not a unit.
    """
    pack = bw_pack.write_pack(
        tmp_path, b"MODEL", {"bw_body_df": b"df", "bw_body_nm": b"nm"},
        b"ICON", "config", "fpsconfig", fps_model=b"FPS", extra={},
        drawables=["g_body"], fps_drawables=["g_body"])
    assets = pack / "assets"
    missing = []

    def need(path: str, suffix: str):
        if not (assets / f"{path}{suffix}").exists():
            missing.append(f"{path}{suffix}")

    for e in ET.parse(pack / "main.xml").getroot().iter("unit_mat"):
        need(e.get("path"), ".unit")
    for e in ET.parse(pack / "main.xml").getroot().iter("df_nm"):
        # <df_nm path=".../bw_body"/> names the pair: bw_body_df + bw_body_nm
        stem = e.get("path")
        assert not stem.endswith(("_df", "_nm")), stem
        need(stem + "_df", ".texture")
        need(stem + "_nm", ".texture")
    for e in ET.parse(pack / "main.xml").getroot().iter("texture"):
        need(e.get("path"), ".texture")

    lua = (pack / "hooks" / f"{bw_pack.ITEM_ID}_las.lua").read_text()
    for key in ("unit", "fps_unit"):
        m = re.search(rf'\b{key} = "([^"]+)"', lua)
        if m:
            need(m.group(1), ".unit")

    for obj in pack.rglob("*.object"):
        root = ET.parse(obj).getroot()
        need(root.find("diesel").get("materials"), ".material_config")
        unit = obj.with_suffix(".unit")
        ref = ET.parse(unit).getroot().find("object").get("file")
        if f"{ref}.object" != f"{bw_pack.TPP_UNIT if obj.stem == bw_pack.ITEM_ID else bw_pack.FPS_UNIT}.object":
            missing.append(f"{obj.name}: object file mismatch ({ref})")
        need(ref, ".object")

    assert missing == []
