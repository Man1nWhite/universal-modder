"""The files that register a pack, as `tools/pd2-las/las_outfit_pack.py` writes them.

A mistake here is invisible offline and fatal in game: a unit path without its
file stem loads nothing, a texture pair named with its `_df` suffix leaves every
material black, a hook that fills another table registers no outfit. The tracked
packs are held to the same contract by `tests/test_pd2_las_invariants.py`; these
tests hold the functions, on a made-up registration, so a change shows here
before a pack is built.

Until 2026-11-13 these assertions ran against the registration of the cancelled
Skyrim outfit, in a test file that went with it.
"""

from __future__ import annotations

import io
import json
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import las_outfit_pack as lop  # noqa: E402

UNIT_BASE = "units/sample/skins/sample"
TPP_UNIT = f"{UNIT_BASE}/sample"
FPS_UNIT = f"{UNIT_BASE}/fps_sample"


def _told(**changes) -> lop.Registration:
    fields = dict(item_id="sample", display_name="Sample", description="a made-up outfit.",
                  unit=TPP_UNIT, flags=lop.BODY_ONLY)
    fields.update(changes)
    return lop.Registration(**fields)


# ------------------------------------------------------------------ the hook
def test_hook_registers_the_table_las_reads():
    lua = lop.hook_lua(_told())
    assert "LegendaryArmours = LegendaryArmours or {}" in lua
    assert "la.sample = {" in lua
    # the hook is what LAS actually looks the unit up by, so pin the literal
    assert 'unit = "units/sample/skins/sample/sample"' in lua
    assert "fps_unit" not in lua                 # no first-person unit was registered
    for flag in lop.BODY_ONLY:
        assert f"{flag} = true" in lua
    # replace_all sets third_body_replacement.head, and a body-only unit has no head
    assert "replace_all" not in lua
    assert "\treplace_body = true" in lua       # with the tab: fps_replace_body ends the same way


def test_hook_of_a_pack_with_a_head_replaces_all():
    lua = lop.hook_lua(_told(flags=lop.WHOLE_CHARACTER))
    assert "\treplace_all = true" in lua
    assert "\treplace_body = true" not in lua


def test_hook_declares_fps_unit_only_when_one_is_built():
    assert f'fps_unit = "{FPS_UNIT}"' in lop.hook_lua(_told(fps_unit=FPS_UNIT))


def test_hook_braces_balance():
    lua = lop.hook_lua(_told(fps_unit=FPS_UNIT))
    assert lua.count("{") == lua.count("}"), lua
    assert lua.rstrip().endswith("}")


# ------------------------------------------------------------------ main.xml
def test_main_xml_lists_textures_and_unit_materials():
    root = ET.fromstring(lop.main_xml(_told(pairs=(f"{UNIT_BASE}/sample_body", f"{UNIT_BASE}/sample_jacket"))))
    df_nm = [e.get("path") for e in root.iter("df_nm")]
    # the stem, not the _df file: the engine appends the suffix itself
    assert df_nm == [f"{UNIT_BASE}/sample_body", f"{UNIT_BASE}/sample_jacket"]
    assert not any(p.endswith("_df") for p in df_nm)
    unit_mat = [e.get("path") for e in root.iter("unit_mat")]
    # pinned as a literal: asserting a constant against itself once let a
    # truncated path (the directory, no file stem) pass while loading nothing in game
    assert unit_mat == ["units/sample/skins/sample/sample"]
    assert not unit_mat[0].endswith("skins/sample")
    hook = root.find("Hooks/hook")
    assert hook.get("file") == "sample_las.lua"
    assert hook.get("source_file") == lop.HOOK_SOURCE


def test_main_xml_registers_the_first_person_unit_when_there_is_one():
    root = ET.fromstring(lop.main_xml(_told(fps_unit=FPS_UNIT)))
    assert [e.get("path") for e in root.iter("unit_mat")] == [TPP_UNIT, FPS_UNIT]


def test_main_xml_registers_the_glove_adapter_hook_only_for_a_pack_that_ships_it():
    with_adapter = ET.fromstring(lop.main_xml(_told(glove_adapter=True)))
    hooks = {h.get("file"): h.get("source_file") for h in with_adapter.iter("hook")}
    assert hooks == {"sample_las.lua": lop.HOOK_SOURCE, "sample_glove_adapter.lua": lop.GLOVE_HOOK_SOURCE}
    # after LAS's loader: hooked where the outfit is declared, it would run before it
    assert lop.GLOVE_HOOK_SOURCE == "lib/tweak_data/blackmarkettweakdata"
    without = ET.fromstring(lop.main_xml(_told()))
    assert [h.get("file") for h in without.iter("hook")] == ["sample_las.lua"]


# ------------------------------------------------------------------ unit, object, strings
def test_object_xml_points_diesel_at_the_material_config():
    root = ET.fromstring(lop.render_object_xml(TPP_UNIT, ["s_body", "g_body_lod1", "g_body"]))
    assert root.find("diesel").get("materials") == "units/sample/skins/sample/sample"
    objects = {o.get("name"): o.get("enabled") for o in root.iter("object")}
    assert objects == {"g_body": "true", "g_body_lod1": "false"}


def test_object_xml_only_lists_drawables_that_exist():
    """A name with no drawable behind it is a log error at best."""
    root = ET.fromstring(lop.render_object_xml(TPP_UNIT, ["s_body", "g_body"]))
    names = [o.get("name") for o in root.iter("object")]
    assert "g_head" not in names and "g_head_lod1" not in names
    assert "s_body" not in names                  # engine-owned shadow mesh


def test_unit_xml_declares_the_extensions_las_needs():
    root = ET.fromstring(lop.render_unit_xml(TPP_UNIT))
    assert root.get("type") == "dah"
    assert [e.get("class") for e in root.iter("extension")] == ["ScriptUnitData", "ContourExt"]


def test_localization_covers_all_three_strings():
    strings = json.loads(lop.localization(_told()))
    assert strings == {"bm_menu_sample_armor_skins": "Sample", "bm_askn_sample": "Sample",
                       "bm_askn_sample_desc": "a made-up outfit."}


# ------------------------------------------------------------------ zip, icon
def test_zip_is_reproducible(tmp_path):
    zips = []
    for side in ("a", "b"):
        pack = tmp_path / side / "Sample_LAS"
        pack.mkdir(parents=True)
        (pack / "main.xml").write_text("<table/>")
        zips.append(lop.zip_pack(pack).read_bytes())
    assert zips[0] == zips[1]


def test_icon_crop_stays_inside_the_preview_sheet():
    from PIL import Image

    buf = io.BytesIO()
    sheet = Image.new("RGB", (1600, 400), (15, 15, 18))
    for i in range(4):                            # four views, centred figures
        for x in range(160 + i * 400, 240 + i * 400):
            for y in range(40, 380):
                sheet.putpixel((x, y), (200, 170, 150))
    sheet.save(buf, format="PNG")
    data = lop.build_icon(buf.getvalue(), size=64)
    assert data[:4] == b"DDS "
    assert struct.unpack_from("<II", data, 12) == (64, 64)
