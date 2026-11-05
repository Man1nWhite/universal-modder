"""The Skyrim outfit keeps the heister's gloves changeable, with hands.

The ``adapter`` hand route ships no hands and restores vanilla-suit glove
behaviour that LAS 4.1.9 breaks. These tests pin the registration contract,
because the failure modes are all invisible offline (the first shipped adapter
pack rendered NO HANDS in-game until this contract was fixed):

* LAS's loader reads ``output.default_glove_id`` (a fresh table) instead of
  ``data.default_glove_id``, so every LAS outfit gets ``default_glove_id =
  false``. BeardLib's ``get_glove_value`` then returns ``false`` for "Default"
  gloves — no glove unit spawns while ``body_replacement.hands`` hides the
  stock hands → no hands at all. Vanilla suits set a real default via
  ``suit_default_gloves``; the companion hook must restore one;
* the same fresh-table bug drops ``data.glove_adapter``, so the companion hook
  on ``blackmarkettweakdata`` must re-enable the forearm adapter;
* ``replace_body`` also lands the outfit on
  ``glove_adapter.player_style_exclude_list``, which must be cleared;
* the adapter must be enabled with a *table*, never a boolean ``true``:
  BeardLib's ``table.merge`` calls ``pairs(new_table)`` and would raise
  ``pairs(true)`` when the character's visual state updates;
* ``body_replacement.hands`` stays ``true`` (vanilla
  ``body_replacement_standard``): the spawned gloves supply the hands, so the
  stock hands must remain hidden to avoid doubles.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import las_outfit_pack  # noqa: E402

DIST = REPO / "dist" / "SkyrimOutfit_LAS.zip"
PACK = "SkyrimOutfit_LAS"
KEY = "las_skyrim_outfit"


# --------------------------------------------------------------- generation


def test_adapter_hook_declares_glove_adapter():
    lua = las_outfit_pack.render_hook_lua(with_fps=True, hands="adapter")
    assert "glove_adapter = true" in lua
    # the outfit still replaces the body (it just ships no hands)
    assert "replace_body = true" in lua


def test_graft_hook_does_not_declare_glove_adapter():
    lua = las_outfit_pack.render_hook_lua(with_fps=True, hands="graft")
    assert "glove_adapter" not in lua


def test_compat_hook_enables_adapter_with_a_table_not_a_boolean():
    lua = las_outfit_pack.render_glove_adapter_lua()
    # an empty table keeps the default hnd_forearms adapter; a boolean true
    # would make BeardLib's table.merge call pairs(true) and crash
    assert "ps.glove_adapter = {}" in lua
    assert "ps.glove_adapter = true" not in lua


def test_compat_hook_targets_the_las_player_style():
    lua = las_outfit_pack.render_glove_adapter_lua()
    assert f'player_styles["{KEY}"]' in lua
    assert 'Hooks:PostHook(BlackMarketTweakData, "init"' in lua


def test_compat_hook_restores_a_real_default_glove():
    """LAS's default_glove_id = false means "Default" gloves spawn no hands.

    Vanilla changeable-glove suits resolve "Default" through
    suit_default_gloves -> default_glove_id -> a real glove unit. The hook must
    restore that, or the character has no hands (the in-game bug this pins).
    """
    lua = las_outfit_pack.render_glove_adapter_lua()
    assert 'ps.default_glove_id = "heist_default"' in lua
    assert "ps.default_glove_id = false" not in lua


def test_compat_hook_clears_the_exclude_list_and_keeps_stock_hands_fallback():
    lua = las_outfit_pack.render_glove_adapter_lua()
    assert "player_style_exclude_list" in lua
    assert f'== "{KEY}"' in lua
    # Stock hands stay visible as a guaranteed fallback (nothing is authored);
    # a glove unit that does spawn replaces them via var_hands_replace = 1, so
    # there are no double hands. Hiding them (the old approach) left the suit
    # handless whenever the glove spawn failed in-game.
    assert "ps.body_replacement.hands = false" in lua
    assert "ps.third_body_replacement.hands = false" in lua
    assert "ps.body_replacement.hands = true" not in lua
    assert "ps.third_body_replacement.hands = true" not in lua


def test_main_xml_registers_compat_hook_on_blackmarket_only_for_adapter():
    stems = ["outfit_body_df", "outfit_jacket_df"]
    adapter = las_outfit_pack.render_main_xml(stems, with_fps=True, hands="adapter")
    assert "skyrim_outfit_glove_adapter.lua" in adapter
    assert 'source_file="lib/tweak_data/blackmarkettweakdata"' in adapter
    graft = las_outfit_pack.render_main_xml(stems, with_fps=True, hands="graft")
    assert "skyrim_outfit_glove_adapter.lua" not in graft


def test_lua_braces_balance():
    """Cheap structural sanity: the compat hook's braces/ends line up."""
    for lua in (las_outfit_pack.render_glove_adapter_lua(),
                las_outfit_pack.render_hook_lua(True, "adapter")):
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
        hook = f"{PACK}/hooks/skyrim_outfit_glove_adapter.lua"
        assert hook in names, "adapter pack must ship the glove-adapter compat hook"
        lua = z.read(hook).decode()
        assert "ps.glove_adapter = {}" in lua
        assert 'ps.default_glove_id = "heist_default"' in lua, (
            "shipped hook must restore a real default glove or the outfit "
            "has no hands in-game")
        main = z.read(f"{PACK}/main.xml").decode()
        assert "skyrim_outfit_glove_adapter.lua" in main
        reg = z.read(f"{PACK}/hooks/skyrim_outfit_las.lua").decode()
        assert "glove_adapter = true" in reg


@pytest.mark.skipif(not DIST.exists(), reason="pack not built in this checkout")
def test_shipped_adapter_pack_has_no_hand_material():
    info = _pack_info()
    if info.get("hands", "graft") != "adapter":
        pytest.skip("pack built with the graft route")
    with zipfile.ZipFile(DIST) as z:
        for cfg in ("skyrim_outfit.material_config",
                    "fps_skyrim_outfit.material_config"):
            blob = z.read(f"{PACK}/assets/units/skyrim_outfit/skins/skyrim_outfit/{cfg}")
            assert b'name="mtr_hands"' not in blob, (
                "adapter route must not declare a hand material it never uses")
