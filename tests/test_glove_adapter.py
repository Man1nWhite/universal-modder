"""The BusinessWoman outfit keeps the heister's gloves changeable.

The ``adapter`` hand route ships no hands and re-enables the vanilla glove
adapter (``char_glove_adapter`` = ``hnd_forearms``) that LAS 4.1.9 forces off.
These tests pin the registration contract that makes that work, because the
failure modes are all invisible offline:

* LAS's loader reads ``output.glove_adapter`` (a fresh table) instead of
  ``data.glove_adapter``, so the outfit's own ``glove_adapter = true`` is dropped
  — a companion hook on ``blackmarkettweakdata`` must re-enable it;
* ``replace_body`` also lands the outfit on
  ``glove_adapter.player_style_exclude_list``, which must be cleared;
* the adapter must be enabled with a *table*, never a boolean ``true``:
  BeardLib's ``table.merge`` calls ``pairs(new_table)`` and would raise
  ``pairs(true)`` when the character's visual state updates;
* ``body_replacement.hands`` must be cleared so the heister's hands/gloves are
  not hidden by an outfit that ships no hands of its own.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import bw_pack  # noqa: E402

DIST = REPO / "dist" / "BusinessWoman_LAS.zip"
PACK = "BusinessWoman_LAS"
KEY = "las_businesswoman"


# --------------------------------------------------------------- generation


def test_adapter_hook_declares_glove_adapter():
    lua = bw_pack.render_hook_lua(with_fps=True, hands="adapter")
    assert "glove_adapter = true" in lua
    # the outfit still replaces the body (it just ships no hands)
    assert "replace_body = true" in lua


def test_graft_hook_does_not_declare_glove_adapter():
    lua = bw_pack.render_hook_lua(with_fps=True, hands="graft")
    assert "glove_adapter" not in lua


def test_compat_hook_enables_adapter_with_a_table_not_a_boolean():
    lua = bw_pack.render_glove_adapter_lua()
    # an empty table keeps the default hnd_forearms adapter; a boolean true
    # would make BeardLib's table.merge call pairs(true) and crash
    assert "ps.glove_adapter = {}" in lua
    assert "ps.glove_adapter = true" not in lua


def test_compat_hook_targets_the_las_player_style():
    lua = bw_pack.render_glove_adapter_lua()
    assert f'player_styles["{KEY}"]' in lua
    assert 'Hooks:PostHook(BlackMarketTweakData, "init"' in lua


def test_compat_hook_clears_the_exclude_list_and_hands():
    lua = bw_pack.render_glove_adapter_lua()
    assert "player_style_exclude_list" in lua
    assert f'== "{KEY}"' in lua
    assert "ps.body_replacement.hands = false" in lua
    assert "ps.third_body_replacement.hands = false" in lua


def test_main_xml_registers_compat_hook_on_blackmarket_only_for_adapter():
    stems = ["bw_body_df", "bw_jacket_df"]
    adapter = bw_pack.render_main_xml(stems, with_fps=True, hands="adapter")
    assert "businesswoman_glove_adapter.lua" in adapter
    assert 'source_file="lib/tweak_data/blackmarkettweakdata"' in adapter
    graft = bw_pack.render_main_xml(stems, with_fps=True, hands="graft")
    assert "businesswoman_glove_adapter.lua" not in graft


def test_lua_braces_balance():
    """Cheap structural sanity: the compat hook's braces/ends line up."""
    for lua in (bw_pack.render_glove_adapter_lua(),
                bw_pack.render_hook_lua(True, "adapter")):
        assert lua.count("{") == lua.count("}"), lua
        # one PostHook function ... end) plus the outfit table
        assert lua.rstrip().endswith(")") or lua.rstrip().endswith("}")


# --------------------------------------------------------------- shipped pack


@pytest.mark.skipif(not DIST.exists(), reason="pack not built in this checkout")
def _pack_info():
    import json
    with zipfile.ZipFile(DIST) as z:
        return json.loads(z.read(f"{PACK}/BUILD_INFO.json"))


@pytest.mark.skipif(not DIST.exists(), reason="pack not built in this checkout")
def test_shipped_adapter_pack_ships_the_compat_hook():
    info = _pack_info()
    if info.get("hands", "graft") != "adapter":
        pytest.skip("pack built with the graft route")
    with zipfile.ZipFile(DIST) as z:
        names = z.namelist()
        hook = f"{PACK}/hooks/businesswoman_glove_adapter.lua"
        assert hook in names, "adapter pack must ship the glove-adapter compat hook"
        lua = z.read(hook).decode()
        assert "ps.glove_adapter = {}" in lua
        main = z.read(f"{PACK}/main.xml").decode()
        assert "businesswoman_glove_adapter.lua" in main
        reg = z.read(f"{PACK}/hooks/businesswoman_las.lua").decode()
        assert "glove_adapter = true" in reg


@pytest.mark.skipif(not DIST.exists(), reason="pack not built in this checkout")
def test_shipped_adapter_pack_has_no_hand_material():
    info = _pack_info()
    if info.get("hands", "graft") != "adapter":
        pytest.skip("pack built with the graft route")
    with zipfile.ZipFile(DIST) as z:
        for cfg in ("businesswoman.material_config",
                    "fps_businesswoman.material_config"):
            blob = z.read(f"{PACK}/assets/units/businesswoman/skins/businesswoman/{cfg}")
            assert b'name="mtr_hands"' not in blob, (
                "adapter route must not declare a hand material it never uses")
