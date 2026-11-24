# Packaging & installing the Hila VO mod (PAYDAY 2 · SuperBLT + BeardLib)

This is the packaging contract for `dist/Hila/Miranda_Lawson_VO_over_Hila.zip` — how the folder
must look, what the game/loader actually reads, how to install it, and how to verify it in game.

Everything below was checked against the real loaders, not from memory:

- **BeardLib 5.2.0** (`diesel-modding/PAYDAY-2-BeardLib`, default branch `master`):
  `Core.lua`, `Classes/ModCore.lua`, `Classes/Frameworks.lua`, `Classes/ModuleBase.lua`,
  `Classes/Managers/SoundManager.lua`, `Modules/Utils/SoundsModule.lua`, `main.xml`, `mod.txt`.
- **SuperBLT XAudio manual** (`diesel-modding/PAYDAY2-SuperBLT-Lua`, `XAudio Users Manual.md`).
- **PAYDAY 2 Lua** (`steam-test1/Payday-2-LuaJIT-Complete`): `lib/units/beings/player/playersound.lua`,
  `lib/units/enemies/cop/copsound.lua`, `lib/units/player_team/teamaisound.lua`,
  `lib/tweak_data/tweakdata.lua`, `lib/managers/group_ai_states/groupaistatebase.lua`.

---

## 1. Required layout

```
PAYDAY 2/
└─ mods/
   └─ Miranda Lawson VO over Hila/     ← exactly one folder, this name is free-form
      ├─ mod.txt                      ← optional for the loader, required for the in-game mod list
      ├─ main.xml                     ← REQUIRED: this is what makes BeardLib load the folder
      ├─ README.txt
      └─ sounds/
         ├─ <clip>.ogg                ← 78 clips
         └─ …
```

`main.xml` (root node free-form; `<table name="…">` mirrors BeardLib's own file):

```xml
<table name="Miranda Lawson VO over Hila">
  <Sounds directory="sounds" prefix="rb21" load_on_play="true">
    <sound id="…" path="<clip>.ogg" stop_id="…_stop"/>
    …
  </Sounds>
</table>
```

- `directory` is resolved **relative to the mod folder**; each `path` is resolved relative to that
  `directory` (`SoundsModule:ReadSounds` → `full_path = Path:Combine(dir, v.path)`).
- `path` is optional — it defaults to `<id>.ogg`. We write it explicitly because several ids share
  one clip.
- `stop_id` is optional — it defaults to `<id>_stop`. We write it explicitly for the same reason.
- `prefix` (or a `<prefixes>` list) is inherited by every child `<sound>` and is **load-bearing**, see §4.

## 2. Why this layout (what the loaders actually do)

| Loader step | Behaviour |
| --- | --- |
| `Frameworks.lua` → `FrameworkBase:FindMods()` | Scans **one level** of `BLTModManager.Constants.mods_directory` (`mods/`) for folders, and loads a folder only if `mods/<folder>/main.xml` exists. No recursion, no other search roots. |
| `ModCore:new(main.xml, …)` | `Name = config.name or <folder name>`. Every child element of the root is instantiated as a BeardLib *module* by name (`<Sounds>` → `SoundsModule`, `<Hooks>` → `HooksModule`, …). Unknown element names log `Unable to find module with key`. |
| `SoundsModule:init` | Calls `BeardLib.Utils:SetupXAudio()` and then reads the config **immediately** (`auto_load = false` only skips the generic module loader). If `XAudio` is nil it errors `Sounds module requires the XAudio API!` and replaces nothing. |
| `SoundManager:AddBuffer` | One shared OpenAL/OpenALSoft buffer per OGG (cached and shared between sources). `load_on_play` defers loading until the id is first posted — good default for a 78-file pack. |
| `SoundManager:CheckSoundID` | Called from the `SoundSource:post_event` hook for **every** sound the game posts, with `(event_id, engine_source)`. It resolves the id, compares `id` **and** prefixes, and plays the mod buffer instead of the vanilla event. |
| `FrameworkBase:FindOverrides` | Additionally registers raw override folders inside a mod (`soundbanks/`, `units/`, `gamedata/`, `strings/`, …). Not used by us: our clips are OGG, which only the XAudio route can play. |

Notes:

- `mods/` is the documented and only scanned mod root. `assets/mod_overrides/<folder>/main.xml` also
  works in practice because BeardLib's `AddFramework` walks `mod_overrides` the same way, but it is
  the *legacy overrides* root: mods there do not appear in the BLT mod list, cannot be toggled, and
  the "one folder per mod" rule is easy to get wrong. Ship `mods/`.
- `mod.txt` is **not** what makes BeardLib load the mod (that is `main.xml`), but BLT's own mod
  manager needs it to list/disable the mod in the main menu. Ship it.
- Folder names with spaces are fine (`Path:Combine`-joined everywhere). The classic failure is
  double nesting (`mods/Miranda Lawson VO over Hila/Miranda Lawson VO over Hila/main.xml`).

## 3. Requirements and install steps

Prerequisites (both are hard requirements — the mod is silent without them):

1. **SuperBLT** (any 64-bit build that exposes `blt.xaudio`). The XAudio API is what plays the OGGs;
   vanilla BLT/BLT4 has no `blt.xaudio`, so `SoundsModule` aborts with
   `Sounds module requires the XAudio API!`.
2. **BeardLib 5.x** (5.1.0+ is the Diesel 3.0 / 64-bit line) installed as `mods/BeardLib/`.

Install:

1. Unzip `Miranda_Lawson_VO_over_Hila.zip` **into `PAYDAY 2/mods/`** so that
   `PAYDAY 2/mods/Miranda Lawson VO over Hila/main.xml` exists.
2. Launch the game. Main menu → **Mods**: the mod is listed (from `mod.txt`), BeardLib is listed
   below it. Nothing else to enable.
3. Play any heist as **Hila** (or with Hila as an AI teammate).

Uninstall / disable:

- Remove the `Miranda Lawson VO over Hila` folder (cleanest), or toggle it off in the main-menu mod
  list. Nothing is written outside the mod folder, so both are complete removals.
- Only one mod should claim the same `(id, prefix)` pair. `AddBuffer` drops a previously registered
  matching buffer, so with two Hila packs installed the one that loads later wins.

## 4. How an id is matched (and the one thing to check first)

`SoundSource:post_event(event, …)` is hooked. For a heister line PD2 posts the **bark event name**
(`PlayerSound:say` → `post_event(name)`, e.g. `f11e_plu`, `g18`, `f30x_any`), and PD2 picks the
speaker with the Wwise switch **`robber`**, which `PlayerSound:set_voice` sets from
`tweak_data.criminals.characters[...].static_data.voice`. Hila is `rb21`
(`characters.ecp_female`), so:

- `BeardLibSoundManager:CheckSoundID(id, source)` compares, for each registered `<sound>`:
  `data.id == id` **and** `table.contains_any(data.prefixes, source:get_prefixes())`
  (`ComparePrefixes`), where `get_prefixes()` returns all switch values of that source
  (`robber` = `rb21`, `int_ext` = `first`/`third`, …).
- Therefore: `prefix="rb21"` restricts the replacement to Hila's own sources — other heisters keep
  their vanilla lines even though they post the very same event names.

**Verification recipe (also the fastest way to debug "I hear nothing"):**

1. Main menu → **Mods** → BeardLib options → enable **Log Sounds** (`LogSounds` in BeardLib's
   `main.xml`, default `false`). This turns on the `Incoming sound check: ID %s Prefixes %s` line in
   `SoundManager:CheckSoundID`.
2. Load a heist, let Hila bark a few times, quit, and open the newest
   `payday2_win32_release_*.log`.
3. Every posted event shows up as `Incoming sound check: ID <id> Prefixes <…>`. The prefix list for
   Hila's own barks contains `rb21`; the ids are the ones to key `main.xml` on.

### Known gap: the shipped ids are voice-line ids, not posted event names

The 887 ids in `voice_lines_vox/miranda_lawson/hila_intent_cuts.csv` are **PD2 voice-line / stream
ids** (the numeric names of the audio files, e.g. `712675`, `1149328`). PD2 never posts those
numbers: `PlayerSound:say` and `CopSound:say` pass the bark **event name** (`f11e_plu`, `g18`,
`v15`, `s08x_sin`, …), and the networked `UnitNetworkHandler:say(unit, event_id)` path converts that
name with `SoundDevice:string_to_id(name)` — BeardLib maps the float back through `GetFloat`, which
is keyed on the same registered id string.

Consequences for this build:

- Everything structural is right: layout, module, XAudio, `prefix="rb21"`, OGG paths, stop ids.
- The ids are not: `<sound id="712675" …>` matches only a post_event of `712675`, which the game
  never posts for a Hila bark. Expect the mod to load cleanly and replace **nothing** until the ids
  are re-keyed.
- Fix direction: key on the callout names from the community *Heister Voice IDs* sheet
  (`g01`…`g92`, `p01`…`, `v01`…`, `f11a_sin`/`f11e_plu`/`f30x_any`/`f36x_any`/`f38_any`/`f39_any`,
  `l01x_sin`…, `d01x_sin`…, `s08x_sin`…, `g80x_plu`, `g81x_plu`, …) — i.e. one `<sound>` per real
  event name, still with `prefix="rb21"`. Use Log Sounds to confirm the exact spelling the build
  posts (`_sin`/`_plu`/`_any` suffixes matter).
- Until then `voice_lines_vox/README.md` keeps the "known gaps" note; no other part of the mod needs
  to change to adopt the re-key — `main.xml` is generated from `slot_picks.csv` +
  `hila_intent_cuts.csv`, so the switch is a build-side mapping table, not a new pack.

## 5. Things that do **not** apply to this mod

- No `assets/mod_overrides/` copy: that root only helps raw bundle overrides (`soundbanks/`, `.stream`
  files, textures, units). Our replacement audio is OGG and must go through `SoundsModule`.
- No `.stream`/`.wem`/soundbank conversion: `.stream` replacement is the native route for vanilla
  lines, but it needs Wwise-encoded audio (PD2 Soundbank Editor / Wwise), which cannot be produced
  from the OGG cutter in `tools/build_hila_voice_mod.py`. Sticking to `SoundsModule` keeps the pack
  buildable from source in this repo.
- No load-order/priority requirement: BeardLib loads mods through its own frameworks after its own
  `init`, and our mod has no Lua that must run before/after anything. `mod.txt` priority is only for
  the BLT list's ordering.
- No localization/strings work: the clips are audio only; they do not add subtitles.
