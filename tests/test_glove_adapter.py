"""A pack without hands keeps the heister's gloves changeable, with hands.

`Christie_LAS_Slim` ships no hands: its arms are cut at the wrist and the game
spawns the heister's gloves there. LAS 4.1.9 breaks that for every outfit it
registers, so the pack ships a companion hook that restores vanilla-suit glove
behaviour (`las_outfit_pack.render_glove_adapter_lua`). These tests pin its
contract, because the failure modes are all invisible offline (the first pack
shipped this way rendered NO HANDS in game until the contract was fixed):

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
* the stock hands stay visible as the fallback: a glove unit that does spawn
  replaces them, and where the spawn fails the suit still has hands.

`tests/test_glove_behavior_lua.py` runs the same hook against the real LAS
loader in LuaJIT. Until 2026-11-13 both files tested the hook of the cancelled
Skyrim outfit, and their pack-level tests skipped for a zip that was never
going to be there again.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_christie_las as christie  # noqa: E402
import las_outfit_pack  # noqa: E402

SLIM = christie.IDENTITIES["slim"]            # no hands: ships the adapter
BASE = christie.IDENTITIES["base"]            # authored hands: does not
KEY = f"las_{SLIM.item_id}"


def _adapter_lua() -> str:
    return las_outfit_pack.render_glove_adapter_lua(SLIM.item_id, SLIM.pack_dir_name)


# --------------------------------------------------------------- generation


def test_only_the_pack_without_hands_asks_for_the_adapter():
    assert SLIM.glove_adapter and not BASE.glove_adapter
    assert christie.registration(SLIM).glove_adapter
    assert not christie.registration(BASE).glove_adapter


def test_compat_hook_enables_adapter_with_a_table_not_a_boolean():
    lua = _adapter_lua()
    # an empty table keeps the default hnd_forearms adapter; a boolean true
    # would make BeardLib's table.merge call pairs(true) and crash
    assert "ps.glove_adapter = {}" in lua
    assert "ps.glove_adapter = true" not in lua


def test_compat_hook_targets_the_las_player_style():
    lua = _adapter_lua()
    assert f'player_styles["{KEY}"]' in lua
    assert 'Hooks:PostHook(BlackMarketTweakData, "init"' in lua


def test_compat_hook_restores_a_real_default_glove():
    """LAS's default_glove_id = false means "Default" gloves spawn no hands.

    Vanilla changeable-glove suits resolve "Default" through
    suit_default_gloves -> default_glove_id -> a real glove unit. The hook must
    restore that, or the character has no hands (the in-game bug this pins).
    """
    lua = _adapter_lua()
    assert 'ps.default_glove_id = "heist_default"' in lua
    assert "ps.default_glove_id = false" not in lua


def test_compat_hook_clears_the_exclude_list_and_keeps_stock_hands_fallback():
    lua = _adapter_lua()
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
    slim = las_outfit_pack.main_xml(christie.registration(SLIM))
    assert f"{SLIM.item_id}_glove_adapter.lua" in slim
    assert 'source_file="lib/tweak_data/blackmarkettweakdata"' in slim
    base = las_outfit_pack.main_xml(christie.registration(BASE))
    assert "glove_adapter.lua" not in base


def test_the_outfit_table_does_not_ask_for_the_adapter_itself():
    """`glove_adapter = true` in the outfit's own table does nothing: LAS's loader drops it.

    The hook file is what re-enables the adapter. The table of the cancelled outfit carried the
    line as a statement of intent; no pack does now, so that nothing reads as if it worked.
    """
    for identity in (SLIM, BASE):
        assert "glove_adapter" not in las_outfit_pack.hook_lua(christie.registration(identity))


def test_lua_braces_balance():
    """Cheap structural sanity: the compat hook's braces/ends line up."""
    for lua in (_adapter_lua(), las_outfit_pack.hook_lua(christie.registration(SLIM))):
        assert lua.count("{") == lua.count("}"), lua
        # one PostHook function ... end) plus the outfit table
        assert lua.rstrip().endswith(")") or lua.rstrip().endswith("}")


# --------------------------------------------------------------- the tracked packs


def _zip(identity) -> zipfile.ZipFile:
    path = REPO / "dist" / f"{identity.pack_dir_name}.zip"
    # no skip: the zip is a tracked file, and a test that skips for it is a test that never runs
    assert path.is_file(), f"dist/{path.name} is tracked and is missing: make -sC tools/pd2-las env"
    return zipfile.ZipFile(path)


def test_the_tracked_pack_without_hands_ships_the_compat_hook():
    with _zip(SLIM) as z:
        info = json.loads(z.read(f"{SLIM.pack_dir_name}/BUILD_INFO.json"))
        assert info["hands"] == "glove_adapter"
        hook = f"{SLIM.pack_dir_name}/hooks/{SLIM.item_id}_glove_adapter.lua"
        assert hook in z.namelist(), "a pack without hands must ship the glove-adapter compat hook"
        lua = z.read(hook).decode()
        assert lua == _adapter_lua(), "the tracked hook is not what the generator writes"
        assert "ps.glove_adapter = {}" in lua
        assert 'ps.default_glove_id = "heist_default"' in lua, (
            "the shipped hook must restore a real default glove or the outfit has no hands in game")
        assert f"{SLIM.item_id}_glove_adapter.lua" in z.read(f"{SLIM.pack_dir_name}/main.xml").decode()


def test_the_tracked_pack_with_hands_ships_no_compat_hook():
    with _zip(BASE) as z:
        info = json.loads(z.read(f"{BASE.pack_dir_name}/BUILD_INFO.json"))
        assert info["hands"] == "authored"
        assert not [name for name in z.namelist() if "glove_adapter" in name]
        assert "glove_adapter" not in z.read(f"{BASE.pack_dir_name}/main.xml").decode()


def test_the_tracked_pack_without_hands_declares_no_hand_material():
    with _zip(SLIM) as z:
        for cfg in (f"{SLIM.item_id}.material_config", f"fps_{SLIM.item_id}.material_config"):
            blob = z.read(f"{SLIM.pack_dir_name}/assets/{SLIM.unit_base}/{cfg}")
            assert b'name="mtr_hands"' not in blob, (
                "a pack without hands must not declare a hand material it never uses")
