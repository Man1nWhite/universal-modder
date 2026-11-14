"""The glove companion hook, against the real LAS 4.1.9 loader in LuaJIT.

What runs here:

1. an outfit registration matching the shape of a pack that ships no hands (the hook that fills ``LegendaryArmours``; until 2026-11-14 the one in the tracked ``Christie_LAS_Slim``);
2. the real LAS 4.1.9 init hook, verbatim from
   ``tests/fixtures/las_loader_4.1.9.lua``;
3. the real BeardLib glove code paths — table.merge, get_glove_value,
   GloveBlackMarketFix, the player-style exclude list — ported verbatim;
4. the generated ``*_glove_adapter.lua`` (the companion hook);
5. vanilla suits, to show the adapter restores stock vanilla behaviour
   instead of just "having gloves".

Until 2026-11-14 the same harness ran against the tracked Christie packs; both
Christie builders were deleted on 2026-11-14. The registration below is the same
shape those packs produced: a BODY_ONLY outfit with no hands in the model, with a
synthetic ``nohands`` stand-in pack id.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa", reason="lupa (LuaJIT) not installed")

try:
    from lupa import luajit21
except ImportError:  # pragma: no cover - older lupa wheels
    luajit21 = None

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import las_outfit_pack  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "las_loader_4.1.9.lua"
NO_HANDS = las_outfit_pack.Registration(
    item_id="nohands", display_name="No Hands (test outfit)",
    description="a LAS outfit that ships no hands, cut at the wrist",
    unit="units/nohands/skins/nohands/nohands",
    fps_unit="units/nohands/skins/nohands/fps_nohands",
    flags=las_outfit_pack.BODY_ONLY,
    glove_adapter=True)
KEY = f"las_{NO_HANDS.item_id}"

# --------------------------------------------------------------------------
# Lua host environment + faithful ports of the real game/mod code
# --------------------------------------------------------------------------

LUA_HOST = r"""
-- SuperBLT-style PostHook registry. Hooks fire in registration order after
-- the (empty) base init: BeardLib loads before LAS, the pack loads after its
-- dependency, so this is the in-game order.
Hooks = {_post = {}}
function Hooks:PostHook(cls, func, id, fn)
    table.insert(self._post, {func = func, id = id, fn = fn})
end
function Hooks:run_init(bm)
    for _, h in ipairs(self._post) do
        if h.func == "init" then h.fn(bm) end
    end
end

BlackMarketTweakData = {}

CriminalsManager = {}
-- verbatim: vanilla lib/managers/criminalsmanager.lua:54
function CriminalsManager.convert_old_to_new_character_workname(workname)
    local t = {spanish = "chains", russian = "dallas", german = "wolf", american = "hoxton"}
    return t[workname] or workname
end

-- BeardLib Core table.merge semantics: iterates pairs(other), so merging a
-- boolean raises exactly like the real one (the pairs(true) trap).
function table.merge(t, other)
    for k, v in pairs(other) do t[k] = v end
    return t
end
function deep_clone(t)
    if type(t) ~= "table" then return t end
    local c = {}
    for k, v in pairs(t) do c[k] = deep_clone(v) end
    return c
end

-- verbatim: vanilla playerstyletweakdata.lua:2987
function BlackMarketTweakData:get_player_style_value(player_style, character_name, key)
    if key == nil then return end
    player_style = player_style or "none"
    local data = self.player_styles[player_style]
    if data == nil then return nil end
    character_name = CriminalsManager.convert_old_to_new_character_workname(character_name)
    local character_value = data.characters and data.characters[character_name] and data.characters[character_name][key]
    if character_value ~= nil then return character_value end
    local tweak_value = data and data[key]
    return tweak_value
end

-- verbatim: vanilla playerstyletweakdata.lua:3011
function BlackMarketTweakData:get_suit_variation_value(player_style, material_variation, character_name, key)
    if key == nil then return nil end
    player_style = player_style or "none"
    material_variation = material_variation or "default"
    local data = self.player_styles[player_style]
    local variation_data = data and data.material_variations and data.material_variations[material_variation]
    if variation_data == nil then return nil end
    character_name = CriminalsManager.convert_old_to_new_character_workname(character_name)
    local character_material_variations = data.characters and data.characters[character_name] and data.characters[character_name].material_variations
    local character_value = character_material_variations and character_material_variations[material_variation] and character_material_variations[material_variation][key]
    if character_value ~= nil then return character_value end
    local tweak_value = variation_data and variation_data[key]
    return tweak_value
end

-- BeardLib override, verbatim logic: PlayerStyleGloveHooks.lua "glovestweakdata"
function BlackMarketTweakData:get_glove_value(glove_id, character_name, key, player_style, material_variation)
    if key == nil then return end
    glove_id = glove_id or "default"
    if glove_id == "default" then
        glove_id = tweak_data.blackmarket:get_suit_variation_value(player_style, material_variation, character_name, "default_glove_id")
        if glove_id == nil then
            glove_id = tweak_data.blackmarket:get_player_style_value(player_style, character_name, "default_glove_id")
        end
        if glove_id == false then return false end
    end
    local data = self.gloves[glove_id or "default"]
    if data == nil then return nil end
    character_name = CriminalsManager.convert_old_to_new_character_workname(character_name)
    local character_value = data.characters and data.characters[character_name] and data.characters[character_name][key]
    if character_value ~= nil then return character_value end
    local tweak_value = data and data[key]
    return tweak_value
end

-- BeardLib override, verbatim logic: PlayerStyleGloveHooks.lua
function BlackMarketTweakData:get_glove_variation_value(glove_id, glove_variation, character_name, key, player_style, material_variation)
    if key == nil then return end
    glove_id = glove_id or "default"
    glove_variation = glove_variation or "default"
    if glove_id == "default" then
        glove_id = tweak_data.blackmarket:get_suit_variation_value(player_style, material_variation, character_name, "default_glove_id")
        if glove_id == nil then
            glove_id = tweak_data.blackmarket:get_player_style_value(player_style, character_name, "default_glove_id")
        end
        glove_variation = tweak_data.blackmarket:get_suit_variation_value(player_style, material_variation, character_name, "default_glove_variation")
        if glove_variation == nil then
            glove_variation = tweak_data.blackmarket:get_player_style_value(player_style, character_name, "default_glove_variation") or "default"
        end
        if glove_id == false then return false end
    end
    local data = self.gloves[glove_id or "default"]
    local variation_data = data and data.variations and data.variations[glove_variation]
    if variation_data == nil then return nil end
    character_name = CriminalsManager.convert_old_to_new_character_workname(character_name)
    local character_variations = data.characters and data.characters[character_name] and data.characters[character_name].variations
    local character_value = character_variations and character_variations[glove_variation] and character_variations[glove_variation][key]
    if character_value ~= nil then return character_value end
    local tweak_value = variation_data and variation_data[key]
    return tweak_value
end

function build_blackmarket()
    local bm = {}
    for k, v in pairs(BlackMarketTweakData) do bm[k] = v end
    -- vanilla glovestweakdata.lua: glove_adapter defaults + the glove entries
    -- the scenarios use (verbatim values; heist_default has no `variations`).
    bm.glove_adapter = {
        unit = "units/pd2_dlc_hnd/characters/hnd_forearms/hnd_forearms",
        third_material = "units/pd2_dlc_hnd/characters/hnd_forearms/hnd_forearms_third",
        character_sequence = {female_1 = "set_arms_female", dallas = "set_arms_male"},
        player_style_exclude_list = {"none", "slaughterhouse"},
    }
    bm.suit_default_gloves = {hitman = "heist_default", gentleman = "heist_default"}
    bm.gloves = {
        default = {name_id = "bm_gloves_default", desc_id = "bm_gloves_default_desc",
                   texture_bundle_folder = "hnd", unlocked = true},
        heist_default = {name_id = "bm_gloves_heistwrinkled", desc_id = "bm_gloves_heistwrinkled_desc",
                         texture_bundle_folder = "hnd", gv_sort_number = -1000,
                         unit = "units/pd2_dlc_hnd/characters/hnd_glv_heistwrinkled/hnd_glv_heistwrinkled",
                         third_material = "units/pd2_dlc_hnd/characters/hnd_glv_heistwrinkled/hnd_glv_heistwrinkled_third"},
        bonemittens = {name_id = "bm_gloves_bonemittens", desc_id = "bm_gloves_bonemittens_desc",
                       texture_bundle_folder = "hnd", global_value = "mbs",
                       unit = "units/pd2_dlc_hnd/characters/hnd_glv_bonemittens/hnd_glv_bonemittens",
                       third_material = "units/pd2_dlc_hnd/characters/hnd_glv_bonemittens/hnd_glv_bonemittens_third"},
    }
    -- a vanilla changeable-glove suit as the control group
    bm.player_styles = {
        hitman = {unit = "units/.../hitman", body_replacement = {head=false,armor=true,body=true,hands=true,vest=true,arms=true},
                  third_body_replacement = {head=false,armor=true,body=true,hands=true,vest=true,arms=true}},
    }
    tweak_data = {blackmarket = bm}
    return bm
end

-- BeardLibInitGloves, verbatim logic: PlayerStyleGloveHooks.lua
-- "blackmarkettweakdata" branch (registered first — BeardLib loads first).
function register_beardlib_init_gloves()
    Hooks:PostHook(BlackMarketTweakData, "init", "BeardLibInitGloves", function(self, tweak_data)
        for player_style_id, glove_id in pairs(self.suit_default_gloves) do
            local player_style_td = self.player_styles[player_style_id]
            local glove_td = self.gloves[glove_id]
            if player_style_td and glove_td then
                player_style_td.default_glove_id = player_style_td.default_glove_id or glove_id
            end
        end
        for index, player_style_id in pairs(self.glove_adapter.player_style_exclude_list) do
            local player_style_td = self.player_styles[player_style_id]
            if player_style_td then
                player_style_td.glove_adapter = false
            end
        end
    end)
end

-- Faithful port of the glove/adapter decision block of BeardLib's
-- set_beardlib_character_visual_state (PlayerStyleGloveHooks.lua ~285-470).
-- Returns what the game would spawn/hide instead of touching real units.
function simulate_visual_state(player_style, glove_id, is_local_peer, character_name)
    local glove_variation = "default"
    local suit_variation = "default"

    local function get_value_string(value)
        return is_local_peer and tostring(value) or "third_" .. tostring(value)
    end
    local function get_player_style_value(value, check_third, fallback)
        local value_string = check_third and get_value_string(value) or value
        local output = tweak_data.blackmarket:get_suit_variation_value(player_style, suit_variation, character_name, value_string)
        if output == nil then
            output = tweak_data.blackmarket:get_player_style_value(player_style, character_name, value_string)
            if output == nil then output = fallback end
        end
        return output
    end
    local function get_gloves_value(value, check_third, fallback)
        local value_string = check_third and get_value_string(value) or value
        local output = tweak_data.blackmarket:get_glove_variation_value(glove_id, glove_variation, character_name, value_string, player_style, suit_variation)
        if output == nil then
            output = tweak_data.blackmarket:get_glove_value(glove_id, character_name, value_string, player_style, suit_variation)
            if output == nil then output = fallback end
        end
        return output
    end

    local body_replacement = get_player_style_value("body_replacement", true, {})
    local gloves_unit_name = get_gloves_value("unit", false)
    local replace_character_hands = gloves_unit_name or gloves_unit_name == false and body_replacement.hands

    -- char_gloves spawns iff gloves_unit_name is truthy (line ~403)
    local char_gloves = nil
    if gloves_unit_name then char_gloves = gloves_unit_name end

    -- adapter block (lines ~429-445), verbatim logic
    local default_adapter_data = tweak_data.blackmarket.glove_adapter
    local gloves_adapter_data = get_gloves_value("glove_adapter", false)
    local player_style_adapter_data = get_player_style_value("glove_adapter", false)
    local final_adapter_data = deep_clone(default_adapter_data)
    if gloves_adapter_data == false then
        final_adapter_data = false
    elseif player_style_adapter_data == false then
        final_adapter_data = false
    else
        table.merge(final_adapter_data, gloves_adapter_data or player_style_adapter_data or {})
    end
    local char_glove_adapter = nil
    if final_adapter_data then char_glove_adapter = final_adapter_data.unit end

    return {
        gloves_unit_name = gloves_unit_name,
        char_gloves = char_gloves,
        char_glove_adapter = char_glove_adapter,
        var_hands_replace = replace_character_hands and 1 or 0,
        var_body_replace = body_replacement.body and 1 or 0,
        var_arms_replace = body_replacement.arms and 1 or 0,
    }
end

-- What the player actually sees: hands exist iff a glove unit spawns, or the
-- stock hands survive. The body_replacement flags are INDEPENDENT: hands=false
-- keeps the heister's stock hands visible even when the body mesh itself is
-- replaced, so the stock hands are a guaranteed fallback when no glove unit
-- spawns (nothing is authored). A glove unit that does spawn replaces them.
function visible_hands(state)
    if state.char_gloves then return true end
    return state.var_hands_replace == 0
end
"""

HEIST_UNIT = "units/pd2_dlc_hnd/characters/hnd_glv_heistwrinkled/hnd_glv_heistwrinkled"
BONE_UNIT = "units/pd2_dlc_hnd/characters/hnd_glv_bonemittens/hnd_glv_bonemittens"
ADAPTER_UNIT = "units/pd2_dlc_hnd/characters/hnd_forearms/hnd_forearms"


def _runtime():
    if luajit21 is not None:
        return luajit21.LuaRuntime(unpack_returned_tuples=True)
    return lupa.LuaRuntime(unpack_returned_tuples=True)


def _setup(lua, *, with_compat_hook: bool):
    """Run the real registration chain; return the blackmarket table."""
    lua.execute(LUA_HOST)
    lua.execute("register_beardlib_init_gloves()")
    # the pack's outfit registration (runs at file load, before init)
    lua.execute(las_outfit_pack.hook_lua(NO_HANDS))
    # the REAL LAS 4.1.9 loader, verbatim
    lua.execute(FIXTURE.read_text())
    if with_compat_hook:
        lua.execute(las_outfit_pack.render_glove_adapter_lua(NO_HANDS.item_id, "nohands"))
    # hooks register at file-load time but run at init time against the built
    # table — exactly the game's sequence
    lua.execute("bm = build_blackmarket()")
    lua.execute("Hooks:run_init(bm)")
    return lua.eval("bm")


@pytest.fixture()
def lua():
    return _runtime()


# --------------------------------------------------------------- the bug


def test_without_compat_hook_las_outfit_has_no_hands(lua):
    """Reproduce the shipped bug: LAS alone leaves Default gloves handless.

    This pins the harness's sensitivity — if this ever stops reproducing the
    no-hands state, the harness no longer models the game.
    """
    _setup(lua, with_compat_hook=False)
    for is_local in (True, False):
        state = lua.eval(f"simulate_visual_state('{KEY}', 'default', {str(is_local).lower()}, 'female_1')")
        assert state["gloves_unit_name"] is False
        assert state["char_gloves"] is None
        assert state["var_hands_replace"] == 1  # stock hands hidden ...
        assert lua.eval(f"visible_hands(simulate_visual_state('{KEY}', 'default', {str(is_local).lower()}, 'female_1'))") is False


# --------------------------------------------------------------- the fix


@pytest.mark.parametrize("is_local", [True, False], ids=["fps", "tpp"])
def test_default_gloves_spawn_real_hands(lua, is_local):
    _setup(lua, with_compat_hook=True)
    flag = str(is_local).lower()
    state = lua.eval(f"simulate_visual_state('{KEY}', 'default', {flag}, 'female_1')")
    assert state["gloves_unit_name"] == HEIST_UNIT
    assert state["char_gloves"] == HEIST_UNIT
    assert state["char_glove_adapter"] == ADAPTER_UNIT
    assert state["var_hands_replace"] == 1  # gloves replace stock hands
    assert lua.eval(f"visible_hands(simulate_visual_state('{KEY}', 'default', {flag}, 'female_1'))") is True


@pytest.mark.parametrize("is_local", [True, False], ids=["fps", "tpp"])
def test_stock_hands_fallback_when_glove_spawn_fails(lua, is_local):
    """If the glove unit fails to spawn in-game, the stock hands still show.

    The compat hook keeps body_replacement.hands = false, so even when the
    default glove resolves to nothing (the LAS fresh-table bug, or a glove spawn
    that silently fails in-game — the twice-shipped failure) the heister's own
    stock hands are not hidden and supply the hands. Nothing is authored.
    """
    _setup(lua, with_compat_hook=True)
    flag = str(is_local).lower()
    # Force the glove to resolve to nothing: exactly the in-game failure mode.
    lua.execute(f"bm.player_styles['{KEY}'].default_glove_id = false")
    state = lua.eval(f"simulate_visual_state('{KEY}', 'default', {flag}, 'female_1')")
    assert state["gloves_unit_name"] is False
    assert state["char_gloves"] is None
    assert state["var_hands_replace"] == 0  # stock hands NOT hidden
    assert lua.eval(f"visible_hands(simulate_visual_state('{KEY}', 'default', {flag}, 'female_1'))") is True


@pytest.mark.parametrize("is_local", [True, False], ids=["fps", "tpp"])
def test_gloves_stay_changeable(lua, is_local):
    _setup(lua, with_compat_hook=True)
    flag = str(is_local).lower()
    state = lua.eval(f"simulate_visual_state('{KEY}', 'bonemittens', {flag}, 'female_1')")
    assert state["char_gloves"] == BONE_UNIT
    assert state["char_glove_adapter"] == ADAPTER_UNIT
    assert lua.eval(f"visible_hands(simulate_visual_state('{KEY}', 'bonemittens', {flag}, 'female_1'))") is True


def test_compat_hook_matches_vanilla_suit_behaviour(lua):
    """The vanilla control: a hitman suit resolves Default the same way."""
    _setup(lua, with_compat_hook=True)
    vanilla = lua.eval("simulate_visual_state('hitman', 'default', false, 'female_1')")
    fixed = lua.eval(f"simulate_visual_state('{KEY}', 'default', false, 'female_1')")
    assert vanilla["char_gloves"] == fixed["char_gloves"] == HEIST_UNIT
    assert vanilla["var_hands_replace"] == fixed["var_hands_replace"] == 1


def test_compat_hook_does_not_disturb_other_styles(lua):
    _setup(lua, with_compat_hook=True)
    ps = lua.eval(f"bm.player_styles['{KEY}']")
    assert ps["default_glove_id"] == "heist_default"
    # other LAS outfits / vanilla styles keep their own settings
    def exclude_list():
        return lua.eval(
            "(function() local t = {} "
            "for _, v in ipairs(bm.glove_adapter.player_style_exclude_list) do "
            "table.insert(t, v) end return table.concat(t, ',') end)()")
    assert KEY not in exclude_list()
    assert "none" in exclude_list()


def test_adapter_table_merge_does_not_crash(lua):
    """ps.glove_adapter must be a table — a boolean raises pairs(true)."""
    _setup(lua, with_compat_hook=True)
    # simulate_visual_state already runs table.merge; reaching here means no
    # crash. Belt-and-braces: force a boolean and confirm the harness raises.
    lua.execute(f"bm.player_styles['{KEY}'].glove_adapter = true")
    with pytest.raises(Exception):
        lua.eval(f"simulate_visual_state('{KEY}', 'default', false, 'female_1')")
