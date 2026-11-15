"""A pack without hands keeps the heister's gloves changeable, with hands.

An LAS pack can ship no hands — its arms are cut at the wrist and the game
spawns the heister's gloves there. LAS 4.1.9 breaks that for every outfit it
registers, so such a pack ships a companion hook that restores vanilla-suit
glove behaviour (`las_outfit_pack.render_glove_adapter_lua`). These tests pin
its contract, because the failure modes are all invisible offline (the first
pack shipped this way rendered NO HANDS in game until the contract was fixed):

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
loader in LuaJIT. The two outfits below are synthetic stand-ins for a pack
with and without hands; until 2026-11-14 both files also ran against the
tracked Christie packs (deleted with their builder on 2026-11-14).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import las_outfit_pack  # noqa: E402

NO_HANDS = las_outfit_pack.Registration(
    item_id="nohands", display_name="No Hands (test outfit)",
    description="a LAS outfit that ships no hands, cut at the wrist",
    unit="units/nohands/skins/nohands/nohands",
    fps_unit="units/nohands/skins/nohands/fps_nohands",
    flags=las_outfit_pack.BODY_ONLY,
    glove_adapter=True)
WITH_HANDS = las_outfit_pack.Registration(
    item_id="withhands", display_name="With Hands (test outfit)",
    description="a LAS outfit that ships its own hands",
    unit="units/withhands/skins/withhands/withhands",
    fps_unit="units/withhands/skins/withhands/fps_withhands",
    flags=las_outfit_pack.BODY_ONLY,
    glove_adapter=False)
KEY = f"las_{NO_HANDS.item_id}"


def _adapter_lua() -> str:
    return las_outfit_pack.render_glove_adapter_lua(NO_HANDS.item_id, NO_HANDS.item_id)


# --------------------------------------------------------------- generation


def test_only_the_pack_without_hands_asks_for_the_adapter():
    assert NO_HANDS.glove_adapter and not WITH_HANDS.glove_adapter


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
    slim = las_outfit_pack.main_xml(NO_HANDS)
    assert f"{NO_HANDS.item_id}_glove_adapter.lua" in slim
    assert 'source_file="lib/tweak_data/blackmarkettweakdata"' in slim
    base = las_outfit_pack.main_xml(WITH_HANDS)
    assert "glove_adapter.lua" not in base


def test_the_outfit_table_does_not_ask_for_the_adapter_itself():
    """`glove_adapter = true` in the outfit's own table does nothing: LAS's loader drops it.

    The hook file is what re-enables the adapter. The table of the cancelled outfit carried the
    line as a statement of intent; no pack does now, so that nothing reads as if it worked.
    """
    for identity in (NO_HANDS, WITH_HANDS):
        assert "glove_adapter" not in las_outfit_pack.hook_lua(identity)


def test_lua_braces_balance():
    """Cheap structural sanity: the compat hook's braces/ends line up."""
    for lua in (_adapter_lua(), las_outfit_pack.hook_lua(NO_HANDS)):
        assert lua.count("{") == lua.count("}"), lua
        # one PostHook function ... end) plus the outfit table
        assert lua.rstrip().endswith(")") or lua.rstrip().endswith("}")


