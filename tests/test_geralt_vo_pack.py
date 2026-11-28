"""Contract and LuaJIT behavioural tests for `Geralt_VO_over_Rust` (BeardLib <Sounds>).

Executes BeardLib 5.2.0's verbatim `SoundManager.lua`, `MixedSoundSource.lua`, and
`SoundsModule.lua` (vendored in `tests/fixtures/beardlib_sound/`) inside LuaJIT 2.1
against the shipped `dist/Geralt/Geralt_VO_over_Rust.zip` (`main.xml` +
`hooks/beardlib_sound_fix.lua`) to prove:
  1. All 36 MP3 takes from `GERALT VOICE (PAYDAY 2).zip` ship as trimmed mono 44.1 kHz
     Ogg Vorbis clips covering 29 bark slots (<random> on civ.down x4, inspire.faster x2,
     mask.go x2) plus `f21ab_sin` (calling Hila) and `f21d_sin` (calling Old Hoxton).
  2. Uncovered Rust lines stay vanilla (no `.stream` files; unmapped events fall through
     to `SoundSource:_post_event`), and non-Rust (`rb21`, `rb5`, `nil`) sources are untouched.
  3. Without `beardlib_sound_fix.lua`, BeardLib 5.2.0 reproduces all three `<Sounds>` bugs
     (SuperBLT `_G.XAudio = {}` skipping `blt.xaudio.setup()`, `Closed`/`MixedSoundSource`
     boot order, and `Setup:unload_packages` -> `Close()` wiping `self.buffers`); with
     `beardlib_sound_fix.lua`, all three are resolved across repeated heist transitions.
"""
from __future__ import annotations

import csv
import hashlib
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las")]

import build_geralt_vo_mod as geralt_vo  # noqa: E402
from dist_paths import dist_path  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "beardlib_sound"
FIXTURE_HASHES = {
    "SoundManager.lua": "d29989e13f1212a6afb57d8b7e89d9da09ab32efc6a2cdc03e72ecd85544d6f3",
    "MixedSoundSource.lua": "d1150f03aba77a7c1b976e38f0aefe068b5ebeeacab9fe9d349ffed0fc61adb7",
    "SoundsModule.lua": "d23fc7572d1953d13c91e0cfafdfbec8321502946ed23a3ca758e54caeefa708",
}
EVENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _lua_runtime():
    lupa = pytest.importorskip("lupa", reason="lupa (LuaJIT) not installed")
    try:
        from lupa import luajit21  # PD2's exact LuaJIT 2.1 dialect
    except ImportError:
        luajit21 = None
    if luajit21 is not None:
        return luajit21.LuaRuntime(unpack_returned_tuples=True)
    return lupa.LuaRuntime(unpack_returned_tuples=True)


def _xml_to_lua_config(xml_text: str) -> str:
    """Convert BeardLib `main.xml`'s `<Sounds>` node to the Lua table `ScriptSerializer` produces."""
    root = ET.fromstring(xml_text)
    sounds = root.find("Sounds")
    assert sounds is not None

    def elem_to_lua(el: ET.Element) -> str:
        parts = [f"_meta = {el.tag!r}"]
        for k, v in el.attrib.items():
            parts.append(f"{k} = {v!r}")
        for child in el:
            parts.append(elem_to_lua(child))
        return "{" + ", ".join(parts) + "}"

    return elem_to_lua(sounds)


LUA_BEARDLIB_HOST = r"""
-- Minimal PAYDAY 2 + SuperBLT + BeardLib 5.2.0 host environment so BeardLib's
-- verbatim SoundManager.lua, MixedSoundSource.lua, and SoundsModule.lua run unmodified.

function alive(obj)
    return obj ~= nil and not obj._destroyed
end

function NotNil(val, default)
    if val == nil then return default end
    return val
end

function ClassClbk(tbl, func)
    return function(...) return tbl[func](tbl, ...) end
end

function class(super)
    local c = {}
    c.__index = c
    if super then
        c.super = super
        setmetatable(c, { __index = super })
    end
    function c:new(...)
        local inst = setmetatable({}, c)
        if inst.init then inst:init(...) end
        return inst
    end
    return c
end

blt_class = class

function string:split(sep)
    local out = {}
    for piece in (self .. sep):gmatch("(.-)" .. sep) do
        table.insert(out, piece)
    end
    return out
end

function table.contains(t, val)
    if not t then return false end
    for _, v in pairs(t) do
        if v == val then return true end
    end
    return false
end

function table.contains_any(a, b)
    if not a or not b then return false end
    for _, v in pairs(a) do
        if table.contains(b, v) then return true end
    end
    return false
end

function table.contains_all(a, b)
    if not a or not b then return false end
    for _, v in pairs(b) do
        if not table.contains(a, v) then return false end
    end
    return true
end

function table.merge(dst, src)
    dst = dst or {}
    if not src then return dst end
    for k, v in pairs(src) do dst[k] = v end
    return dst
end

function table.map_values(t)
    local out = {}
    if not t then return out end
    for _, v in pairs(t) do table.insert(out, v) end
    return out
end

_RANDOM_IDX = 0
function table.random(t)
    _RANDOM_IDX = (_RANDOM_IDX % #t) + 1
    return t[_RANDOM_IDX]
end

Path = {}
function Path:Combine(a, b)
    if not a or a == "" then return b or "" end
    if not b or b == "" then return a end
    if a:sub(-1) == "/" then return a .. b end
    return a .. "/" .. b
end

VIRTUAL_FILES = {}
FileIO = {}
function FileIO:Exists(p)
    return VIRTUAL_FILES[p] == true
end

Hooks = { _post = {} }
function Hooks:PostHook(cls, method, id, fn)
    assert(cls ~= nil, "PostHook target class is nil for " .. tostring(method))
    local key = tostring(cls) .. ":" .. method
    if not self._post[key] then
        self._post[key] = { order = {}, map = {} }
        local orig = cls[method]
        cls[method] = function(...)
            local ret = orig and orig(...) or nil
            for _, hid in ipairs(self._post[key].order) do
                self._post[key].map[hid](...)
            end
            return ret
        end
    end
    if not self._post[key].map[id] then
        table.insert(self._post[key].order, id)
    end
    self._post[key].map[id] = fn
end

-- Engine classes (SoundDevice, SoundSource, Unit, Setup)
SoundDevice = { _map = {}, _next = 1000.5 }
function SoundDevice:string_to_id(s)
    if not self._map[s] then
        self._map[s] = self._next
        self._next = self._next + 1.0
    end
    return self._map[s]
end

VANILLA_POSTED = {}
SoundSource = class()
function SoundSource:init(unit_pos)
    self._stopped = 0
    self._init_pos = unit_pos
end
function SoundSource:key() return tostring(self) end
function SoundSource:set_position(pos) end
function SoundSource:set_link_object(obj) end
function SoundSource:stop() self._stopped = self._stopped + 1 end
function SoundSource:set_switch(switch, state) end
function SoundSource:post_event(event, clbk, cookie, flags)
    table.insert(VANILLA_POSTED, { event = event, prefixes = self.get_prefixes and self:get_prefixes() or nil })
    return { vanilla = true, event = event }
end

Unit = class()
function Unit:sound_source() return self._ss end

Setup = class()
function Setup:unload_packages() end
function Setup:init_finalize() end

-- SuperBLT XAudio mock matching PAYDAY2-SuperBLT-Lua/req/xaudio/*.lua
function build_xaudio_globals()
    local XA = {
        _sources = {},
        _next_source_id = 1,
        _base_gains = { sfx = 0.2, music = 0.2 },
    }
    local Buffer = class()
    function Buffer:init(path)
        assert(blt.xaudio.issetup(), "OpenAL not initialized: blt.xaudio.setup() was never called!")
        assert(FileIO:Exists(path), "Missing OGG file: " .. tostring(path))
        self._path = path
        self._closed = false
    end
    function Buffer:close(force)
        self._closed = true
    end
    function Buffer:get_length() return 1.25 end
    XA.Buffer = Buffer

    local Source = class()
    Source.PLAYING = 1
    Source.PAUSED = 2
    Source.STOPPED = 3
    Source.INITIAL = 4
    Source.OTHER = 5
    Source.SOUND_EFFECT = "sfx"
    Source.MUSIC = "music"
    function Source:init(buffer)
        assert(blt.xaudio.issetup(), "OpenAL not initialized: blt.xaudio.setup() was never called!")
        self._source_id = XA._next_source_id
        XA._next_source_id = XA._next_source_id + 1
        XA._sources[self._source_id] = self
        self._closed = false
        self._state = Source.INITIAL
        self._gain = 1
        self._relative = false
        self._looping = false
        self._single_sound = false
        if buffer then
            self:set_buffer(buffer)
            self._single_sound = true
        end
    end
    function Source:set_buffer(buf)
        assert(not buf._closed, "Attempted to play a closed XAudio.Buffer: " .. tostring(buf._path))
        self._buffer = buf
        table.insert(PLAYED_BUFFERS, { path = buf._path, source = self })
    end
    function Source:play() self._state = Source.PLAYING end
    function Source:pause() self._state = Source.PAUSED end
    function Source:stop() self._state = Source.STOPPED end
    function Source:close()
        XA._sources[self._source_id] = nil
        self._closed = true
        self._state = Source.STOPPED
    end
    function Source:is_closed() return self._closed end
    function Source:is_active() return self._state == Source.PLAYING or self._state == Source.PAUSED end
    function Source:get_state() return self._state end
    function Source:set_volume(v) self._gain = v end
    function Source:get_volume() return self._gain end
    function Source:set_relative(r) self._relative = r end
    function Source:is_relative() return self._relative end
    function Source:set_auto_pause(a) self._auto_pause = a end
    function Source:set_looping(l) self._looping = l end
    function Source:set_single_sound(s) self._single_sound = s end
    function Source:set_position(p) self._pos = p end
    function Source:update(t, dt, paused)
        if self._closed then error("Cannot update closed source") end
        if self._single_sound then
            if self._state == Source.INITIAL then
                self:play()
            elseif self._state == Source.STOPPED then
                self:close()
            end
        end
    end
    XA.Source = Source
    return XA
end

PLAYED_BUFFERS = {}

function tick_audio(t, dt)
    -- SuperBLT XAudio.lua:39 Base_XAudio_GameSetupUpdate + BeardLibGameSetupUpdate
    if _G.XAudio and _G.XAudio._sources then
        for _, src in pairs(_G.XAudio._sources) do
            if not src:is_closed() then
                src:update(t, dt, false)
            end
        end
    end
    BeardLib.Managers.Sound:Update(t, dt)
end

function setup_superblt(mode)
    -- mode == "modern": _G.XAudio = build_xaudio_globals() exists at boot BEFORE blt.xaudio.setup()
    -- mode == "legacy": _G.XAudio is nil until blt.xaudio.setup() runs
    local is_setup = false
    blt = {
        xaudio = {
            issetup = function() return is_setup end,
            setup = function()
                is_setup = true
                if not _G.XAudio then
                    _G.XAudio = build_xaudio_globals()
                end
            end,
        }
    }
    if mode == "modern" then
        _G.XAudio = build_xaudio_globals()
    else
        _G.XAudio = nil
    end
end

ModuleBase = class()
function ModuleBase:init(mod, config)
    self._mod = mod
    self._config = config
    if self.init_final then self:init_final() end
    return true
end
function ModuleBase:GetPath(directory, prev_dir)
    local base = prev_dir or self._mod:GetPath()
    if directory then
        return Path:Combine(base, directory)
    end
    return base
end
function ModuleBase:Err(...) end

local _bl_managers = {}
BeardLib = {
    ModPath = "mods/BeardLib/",
    Managers = _bl_managers,
    managers = _bl_managers,
    Modules = {},
    Options = { GetValue = function() return false end },
    Utils = {
        SetupXAudio = function(self)
            if blt and blt.xaudio then blt.xaudio.setup() end
        end
    },
    DevLog = function() end,
    log = function() end,
}
function BeardLib:ManagerClass(name)
    local c = class()
    c.type_name = name
    self._pending_manager = c
    return c
end
function BeardLib:ModuleClass(name, super)
    local c = class(super)
    c.type_name = name
    self.Modules[name] = c
    return c
end

function dofile(path)
    local content = FIXTURE_SOURCES[path]
    assert(content, "Unknown dofile path: " .. tostring(path))
    return assert(loadstring(content, "@" .. path))()
end
"""


def test_vendored_beardlib_sound_fixtures_match_pinned_hashes():
    for name, expected in FIXTURE_HASHES.items():
        path = FIXTURE_DIR / name
        assert path.is_file(), f"missing fixture {path}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, f"{name} drifted from pinned BeardLib commit"


def test_takes_csv_covers_all_36_source_mp3s_and_agrees_with_slot_picks():
    takes = geralt_vo.load_takes()
    assert len(takes) == 36

    with zipfile.ZipFile(geralt_vo.GERALT_ZIP, "r", metadata_encoding="cp866") as zf:
        archive_mp3s = set(zf.namelist())
    assert len(archive_mp3s) == 36
    assert {r["source_mp3"] for r in takes} == archive_mp3s

    with geralt_vo.PICKS_CSV.open(newline="", encoding="utf-8") as f:
        picks = {r["slot"]: r for r in csv.DictReader(f)}
    with geralt_vo.EVENTS_CSV.open(newline="", encoding="utf-8") as f:
        slot_events = {r["slot"]: r["event_ids"] for r in csv.DictReader(f)}

    slot_rows = [r for r in takes if r["kind"] == "slot"]
    callout_rows = [r for r in takes if r["kind"] == "callout"]
    assert {r["intent_id"] for r in slot_rows} == set(picks)
    assert len(callout_rows) == 2

    by_intent: dict[str, list[dict[str, str]]] = {}
    for r in takes:
        by_intent.setdefault(r["intent_id"], []).append(r)
        assert r["prefix"] == "rb16"
        assert 0.0 <= float(r["t_start"]) < float(r["t_end"])
        evs = [e for e in r["event_ids"].split("|") if e]
        assert evs
        for ev in evs:
            assert EVENT_RE.fullmatch(ev), f"invalid event name {ev!r}"
            assert not ev.isdigit()

    # Primary take of each of the 29 bark slots matches slot_picks.csv + slot_event_ids.csv
    for slot, pk in picks.items():
        primary = by_intent[slot][0]
        assert primary["source_mp3"] == pk["source_ogg"]
        assert float(primary["t_start"]) == pytest.approx(float(pk["t_start"]))
        assert float(primary["t_end"]) == pytest.approx(float(pk["t_end"]))
        assert primary["event_ids"] == slot_events[slot]

    # Multi-take <random> pools
    assert len(by_intent["civ.down"]) == 4
    assert len(by_intent["inspire.faster"]) == 2
    assert len(by_intent["mask.go"]) == 2

    # Character-specific summon callouts (PlayerStandard voice_type == "come")
    assert by_intent["call_teammate.hila"][0]["event_ids"] == "f21ab_sin"
    assert by_intent["call_teammate.hoxton"][0]["event_ids"] == "f21d_sin"


def test_shipped_pack_contains_36_mono_44k1_vorbis_oggs_and_zero_streams():
    pack_path = dist_path(ROOT, "Geralt_VO_over_Rust.zip")
    assert pack_path.is_file(), f"missing {pack_path}"

    ff = geralt_vo.ffmpeg_bin()
    with zipfile.ZipFile(pack_path) as zf:
        names = set(zf.namelist())
        assert "Geralt VO over Rust/main.xml" in names
        assert "Geralt VO over Rust/mod.txt" in names
        assert "Geralt VO over Rust/README.txt" in names
        assert "Geralt VO over Rust/geralt_rust_vo_map.csv" in names
        assert "Geralt VO over Rust/hooks/beardlib_sound_fix.lua" in names
        assert [n for n in names if n.endswith(".stream")] == []

        oggs = sorted(n for n in names if n.endswith(".ogg"))
        assert len(oggs) == 36

        manifest = list(
            csv.DictReader(zf.read("Geralt VO over Rust/geralt_rust_vo_map.csv").decode("utf-8").splitlines())
        )
        assert len(manifest) == 36

        for row in manifest:
            member = f"Geralt VO over Rust/{row['ogg_path']}"
            assert member in names
            data = zf.read(member)
            assert data[:4] == b"OggS", f"{member} is not an Ogg stream"
            # Verify Vorbis identification header: \x01vorbis, version=0, channels=1, rate=44100
            vorbis_pos = data.find(b"\x01vorbis")
            assert vorbis_pos != -1, f"{member} has no Vorbis ID header"
            ver, channels, rate = struct.unpack_from("<IBI", data, vorbis_pos + 7)
            assert ver == 0
            assert channels == 1, f"{member} must be mono for OpenAL 3D attenuation"
            assert rate == 44100

        # Spot-decode one clip through ffmpeg to confirm clean PCM roundtrip
        sample_ogg = zf.read("Geralt VO over Rust/voicelines/call_hila.ogg")
        pcm = subprocess.run(
            [ff, "-v", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "44100", "-"],
            input=sample_ogg,
            check=True,
            capture_output=True,
        ).stdout
        assert len(pcm) > 44100  # ~0.985 s * 2 bytes/sample


def _boot_beardlib_sound_vm(
    mode: str,
    *,
    with_fix: bool,
) -> tuple[object, str]:
    """Boot LuaJIT with verbatim BeardLib 5.2.0 sound classes and load shipped `main.xml`."""
    pack_path = dist_path(ROOT, "Geralt_VO_over_Rust.zip")
    with zipfile.ZipFile(pack_path) as zf:
        xml_text = zf.read("Geralt VO over Rust/main.xml").decode("utf-8")
        fix_lua = zf.read("Geralt VO over Rust/hooks/beardlib_sound_fix.lua").decode("utf-8")
        ogg_members = [n for n in zf.namelist() if n.endswith(".ogg")]

    lua = _lua_runtime()
    lua.execute(LUA_BEARDLIB_HOST)

    fixture_sources = lua.eval("{}")
    fixture_sources["mods/BeardLib/Classes/Managers/SoundManager.lua"] = (
        FIXTURE_DIR / "SoundManager.lua"
    ).read_text(encoding="utf-8")
    fixture_sources["mods/BeardLib/Classes/MixedSoundSource.lua"] = (
        FIXTURE_DIR / "MixedSoundSource.lua"
    ).read_text(encoding="utf-8")
    fixture_sources["mods/BeardLib/Modules/Utils/SoundsModule.lua"] = (
        FIXTURE_DIR / "SoundsModule.lua"
    ).read_text(encoding="utf-8")
    lua.globals()["FIXTURE_SOURCES"] = fixture_sources

    vfiles = lua.globals()["VIRTUAL_FILES"]
    vfiles["mods/BeardLib/Classes/MixedSoundSource.lua"] = True
    for m in ogg_members:
        vfiles[f"assets/mod_overrides/{m}"] = True

    # 1. SuperBLT boot
    lua.execute(f"setup_superblt({mode!r})")

    # 2. BeardLib Core.lua boot order: MixedSoundSource, SoundManager:new(), SoundsModule, GeneralHooks
    lua.execute('dofile("mods/BeardLib/Classes/MixedSoundSource.lua")')
    lua.execute('dofile("mods/BeardLib/Classes/Managers/SoundManager.lua")')
    lua.execute("BeardLib.Managers.Sound = BeardLib._pending_manager:new()")
    lua.execute('dofile("mods/BeardLib/Modules/Utils/SoundsModule.lua")')
    lua.execute(
        """
        Hooks:PostHook(Setup, "unload_packages", "BeardLibUnloadPackages", function(self)
            BeardLib.Managers.Sound:Close()
        end)
        Hooks:PostHook(Setup, "init_finalize", "BeardLibSetupInitFinalize", function(self)
            BeardLib.Managers.Sound:Open()
        end)
        """
    )

    # 3. ModCore:InitModules() loads core_class before <Sounds>
    if with_fix:
        lua.execute(fix_lua)

    sounds_lua_tbl = _xml_to_lua_config(xml_text)
    lua.execute(
        f"""
        geralt_mod = {{
            Name = "Geralt VO over Rust",
            ModPath = "assets/mod_overrides/Geralt VO over Rust/",
            GetPath = function(self) return self.ModPath end,
        }}
        SoundsModule:new(geralt_mod, {sounds_lua_tbl})
        """
    )
    return lua, fix_lua


def test_without_fix_older_beardlib_or_post_reset_skips_xaudio_setup():
    """Bug 1: If `blt.xaudio` resets on state change (`Open()` never calls `setup()`), XAudio stays unsetup."""
    lua, _ = _boot_beardlib_sound_vm("modern", with_fix=False)
    # Simulate SuperBLT resetting OpenAL state across VM/heist transition before `Open()`
    lua.execute("setup_superblt('modern')")
    assert lua.eval("blt.xaudio.issetup()") is False
    lua.execute("s = Setup:new(); s:init_finalize()")
    assert lua.eval("blt.xaudio.issetup()") is False


def test_without_fix_legacy_boot_drops_all_buffers_and_mixed_sound_source():
    """Bug 2: If `_G.XAudio` is nil when `Core.lua` runs, `Closed == true` and `MixedSoundSource == nil`."""
    lua, _ = _boot_beardlib_sound_vm("legacy", with_fix=False)
    assert lua.eval("MixedSoundSource == nil") is True
    assert lua.eval("BeardLib.Managers.Sound.Closed") is True
    assert lua.eval("#BeardLib.Managers.Sound.buffers") == 0


def test_without_fix_unload_packages_wipes_buffers_before_heist():
    """Bug 3: `Setup:unload_packages` -> `Sound:Close()` wipes `buffers` and blocks `Sound:Open()`."""
    lua, _ = _boot_beardlib_sound_vm("modern", with_fix=False)
    lua.execute(
        """
        menu_setup = Setup:new()
        menu_setup:init_finalize()
        menu_setup:unload_packages()   -- leaving main menu to load heist
        game_setup = Setup:new()
        game_setup:init_finalize()     -- entering heist

        rust_src = SoundSource:new()
        rust_src:set_switch("robber", "rb16")
        rust_src:set_switch("int_ext", "first")
        rust_src:post_event("g30x_any")
        """
    )
    assert lua.eval("BeardLib.Managers.Sound.Closed") is True
    assert lua.eval("#BeardLib.Managers.Sound.buffers") == 0
    assert lua.eval("#PLAYED_BUFFERS") == 0
    assert lua.eval("#VANILLA_POSTED") == 1


@pytest.mark.parametrize("mode", ["modern", "legacy"])
def test_with_fix_geralt_vo_plays_across_heist_transitions_and_scopes_to_rust(mode: str):
    """End-to-end verification of `main.xml` + `beardlib_sound_fix.lua` in both SuperBLT modes."""
    lua, fix_lua = _boot_beardlib_sound_vm(mode, with_fix=True)
    # Re-running the hook (as `<Hooks>` on `lib/setups/setup` does) must be idempotent
    lua.execute(fix_lua)

    assert lua.eval("blt.xaudio.issetup()") is True
    assert lua.eval("MixedSoundSource ~= nil") is True
    assert lua.eval("BeardLib.Managers.Sound.Closed") is False
    assert lua.eval("#BeardLib.Managers.Sound.buffers") == 36
    initial_sound_ids = lua.eval("#BeardLib.Managers.Sound.sound_ids")

    # Simulate Main Menu -> Heist 1 -> Main Menu -> Heist 2 package unload/reopen cycles
    lua.execute(
        """
        s = Setup:new()
        s:init_finalize()
        s:unload_packages()
        s:init_finalize()
        s:unload_packages()
        s:init_finalize()
        """
    )
    assert lua.eval("BeardLib.Managers.Sound.Closed") is False
    assert lua.eval("#BeardLib.Managers.Sound.buffers") == 36
    assert lua.eval("#BeardLib.Managers.Sound.sound_ids") == initial_sound_ids

    # Create SoundSources for Rust (1st & 3rd person), Hila (rb21), Old Hoxton (rb5), and a Cop (nil)
    lua.execute(
        """
        rust_fp = SoundSource:new()
        rust_fp:set_position({ x = 0, y = 0, z = 0 })
        rust_fp:set_switch("robber", "rb16")
        rust_fp:set_switch("int_ext", "first")

        rust_ai = SoundSource:new()
        rust_ai:set_position({ x = 150, y = -200, z = 40 })
        rust_ai:set_switch("robber", "rb16")
        rust_ai:set_switch("int_ext", "third")

        hila_src = SoundSource:new()
        hila_src:set_switch("robber", "rb21")
        hila_src:set_switch("int_ext", "third")

        hoxton_src = SoundSource:new()
        hoxton_src:set_switch("robber", "rb5")
        hoxton_src:set_switch("int_ext", "third")

        cop_src = SoundSource:new()
        """
    )

    # 1. Rust calling Hila (`f21ab_sin`) and Old Hoxton (`f21d_sin`)
    lua.execute(
        """
        PLAYED_BUFFERS = {}
        VANILLA_POSTED = {}
        src1 = rust_fp:post_event("f21ab_sin")
        tick_audio(1.0, 0.016)
        src2 = rust_ai:post_event("f21d_sin")
        tick_audio(1.1, 0.016)
        """
    )
    assert lua.eval("#VANILLA_POSTED") == 0
    assert lua.eval("#PLAYED_BUFFERS") == 2
    assert str(lua.eval("PLAYED_BUFFERS[1].path")).endswith("voicelines/call_hila.ogg")
    assert lua.eval("PLAYED_BUFFERS[1].source:is_relative()") is True  # 1st-person Rust (already on frame 1!)
    assert str(lua.eval("PLAYED_BUFFERS[2].path")).endswith("voicelines/call_hoxton.ogg")
    assert lua.eval("PLAYED_BUFFERS[2].source:is_relative()") is False  # 3rd-person/AI 3D spatialized
    assert lua.eval("PLAYED_BUFFERS[2].source._pos.x") == 150

    # 2. Network-synced float event ID (`UnitNetworkHandler:say` passes `SoundDevice:string_to_id(...)`)
    lua.execute(
        """
        PLAYED_BUFFERS = {}
        net_id = SoundDevice:string_to_id("g30x_any")
        rust_ai:post_event(net_id)
        tick_audio(2.0, 0.016)
        """
    )
    assert lua.eval("#PLAYED_BUFFERS") == 1
    assert str(lua.eval("PLAYED_BUFFERS[1].path")).endswith("voicelines/kill_dozer.ogg")

    # 3. <random> multi-take pools rotate through all takes with zero wait lag
    lua.execute(
        """
        PLAYED_BUFFERS = {}
        for i = 1, 4 do
            rust_fp:post_event("f03a_sin")
            tick_audio(3.0 + i * 0.1, 0.016)
        end
        for i = 1, 2 do
            rust_fp:post_event("g18")
            tick_audio(4.0 + i * 0.1, 0.016)
        end
        for i = 1, 2 do
            rust_fp:post_event("a01x_any")
            tick_audio(5.0 + i * 0.1, 0.016)
        end
        """
    )
    played_paths = [Path(str(lua.eval(f"PLAYED_BUFFERS[{i}].path"))).name for i in range(1, 9)]
    assert set(played_paths[:4]) == {"civ_down_1.ogg", "civ_down_2.ogg", "civ_down_3.ogg", "civ_down_4.ogg"}
    assert set(played_paths[4:6]) == {"inspire_faster_1.ogg", "inspire_faster_2.ogg"}
    assert set(played_paths[6:8]) == {"mask_go_1.ogg", "mask_go_2.ogg"}

    # 4. Uncovered Rust lines remain vanilla
    lua.execute(
        """
        PLAYED_BUFFERS = {}
        VANILLA_POSTED = {}
        rust_fp:post_event("g90")
        rust_fp:post_event("f47x_any")
        rust_fp:post_event("dsp_radio_checking_1")
        tick_audio(6.0, 0.016)
        """
    )
    assert lua.eval("#PLAYED_BUFFERS") == 0
    assert lua.eval("#VANILLA_POSTED") == 3

    # 5. Other heisters (Hila rb21, Old Hoxton rb5) and Cops (nil) are never intercepted
    lua.execute(
        """
        PLAYED_BUFFERS = {}
        VANILLA_POSTED = {}
        hila_src:post_event("g30x_any")
        hila_src:post_event("f21d_sin")
        hoxton_src:post_event("f03a_sin")
        hoxton_src:post_event("f21ab_sin")
        cop_src:post_event("g30x_any")
        tick_audio(7.0, 0.016)
        """
    )
    assert lua.eval("#PLAYED_BUFFERS") == 0
    assert lua.eval("#VANILLA_POSTED") == 5

    # 6. Interrupting speech (`PlayerSound:say` calling `_last_speech:stop()`) closes the source cleanly
    lua.execute(
        """
        PLAYED_BUFFERS = {}
        interrupted = rust_fp:post_event("g24")
        interrupted:stop()
        tick_audio(8.0, 0.016)
        """
    )
    assert lua.eval("interrupted:is_closed()") is True
    assert lua.eval("#PLAYED_BUFFERS") == 0


def test_every_redirected_event_in_main_xml_resolves_to_a_geralt_ogg_in_luajit():
    """Exhaustively fire all 45 redirected bark events on Rust (`rb16`) inside BeardLib LuaJIT."""
    lua, _ = _boot_beardlib_sound_vm("modern", with_fix=True)
    lua.execute(
        """
        s = Setup:new()
        s:init_finalize()
        s:unload_packages()
        s:init_finalize()
        rust_fp = SoundSource:new()
        rust_fp:set_switch("robber", "rb16")
        rust_fp:set_switch("int_ext", "first")
        """
    )
    takes = geralt_vo.load_takes()
    all_events = sorted({ev for r in takes for ev in r["event_ids"].split("|") if ev})
    assert len(all_events) == 45
    for idx, ev in enumerate(all_events, 1):
        lua.execute(
            f"""
            PLAYED_BUFFERS = {{}}
            VANILLA_POSTED = {{}}
            rust_fp:post_event({ev!r})
            tick_audio({10.0 + idx * 0.1}, 0.016)
            """
        )
        assert lua.eval("#VANILLA_POSTED") == 0, f"{ev} fell back to vanilla instead of playing Geralt"
        assert lua.eval("#PLAYED_BUFFERS") == 1, f"{ev} did not play a Geralt OGG buffer"
        assert str(lua.eval("PLAYED_BUFFERS[1].path")).endswith(".ogg")
