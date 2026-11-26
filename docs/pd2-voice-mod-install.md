# Packaging & installing the Hila VO mod (PAYDAY 2 · any BLT / SuperBLT)

One pack ships Miranda Lawson's clips over Hila, and this page is its contract:

| Pack | Route | Needs | Contract |
|---|---|---|---|
| `dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip` | one Wwise ADPCM `.stream` per voice-line id, in `soundbanks/streamed/regular_vox/` | any BLT / SuperBLT | **§7** |

It is the route the game itself uses — it is how the reference voice pack
`references/Tokoyami Hila.7z` is built, dissected in
[`tokoyami-hila-voice-mod-analysis.md`](tokoyami-hila-voice-mod-analysis.md) — and it is the only
one of the two that was heard working in game (2026-11-25).

> **§1–§6 are the record of the route that was dropped.** A second pack,
> `Miranda_Lawson_VO_over_Hila.zip`, keyed BeardLib `<Sounds>` on the bark *event* name and shipped
> OGG clips. It was installed on 2026-11-24 and vanilla Hila still played; the keying was
> re-verified against the loaders and was right, but the route never produced a line in game. It was
> removed from `dist/` on 2026-11-25 (D61) and its builder with it. What follows is kept because the
> reasoning is the record for that decision, and because a future pack on this route would start
> here — not because anything below ships.

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
      ├─ slot_to_ogg.csv              ← build manifest (slot, clip, event ids, gain, peak)
      ├─ hila_slot_pieces.csv         ← build manifest (cut ranges the clips came from)
      └─ sounds/
         ├─ <clip>.ogg                ← 78 clips, 176 bark events
         └─ …
```

The two CSVs are for whoever has to answer "where did this bark come from": the game reads neither.

`main.xml` (root node free-form; `<table name="…">` mirrors BeardLib's own file):

```xml
<table name="Miranda Lawson VO over Hila">
  <Sounds directory="sounds" prefix="rb21" load_on_play="true">
    <sound id="g18" path="<clip>.ogg" stop_id="g18_stop"/>
    …
  </Sounds>
</table>
```

`id` is a PD2 bark event name (see §4); several `<sound>` entries may point at the same `path`.

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

*Dropped route (D61): nothing below ships — the pack these steps install is no longer built. See the
note at the top of this page.*

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

## 4. What existing PAYDAY 2 voice mods do

Two routes exist. Both are used by published mods; they key on different things, and picking the
wrong one is what made the first build of this pack inert.

### 4a. The standard route: `.stream` overrides (what most voice packs ship)

From the ModWorkshop wiki, *Voice Over Modding* — the canonical guide:

- Path: `<mod>/soundbanks/streamed/<bank>/<id>.stream`, with `<bank>` = `char_<heister>` for the
  newer characters, `robbers_mission_gen` for mission chatter, `safehouse_vo` for the safe house,
  and `regular_vox` for the original crew (Dallas, Hoxton, Wolf, Chains, Houston, Clover, Wick).
  Under `mods/` this works because BeardLib's `FindOverrides` registers `soundbanks/` from any mod
  folder; the classic form is `assets/mod_overrides/<mod>/soundbanks/...`.
- **The file name is only the numeric sound id** — `712675.stream`, not `712675.english`, not
  `712675.1`.
- The audio must be Wwise IMA ADPCM: `wwise_ima_adpcm -e in.wav out.stream` (or the *Convert loose
  files* tool in Hoppip's Soundbank Editor). The guide is emphatic that renaming `.wav`/`.ogg` to
  `.stream` produces silence.
- Known hole, stated on the same page: some lines — AI warcries, special-marking in the control
  phase, "more for characters older than Bodhi" — are **OGG-encoded** streams that
  `wwise_ima_adpcm` cannot produce, so packs cannot replace them this way at all.

Those numeric ids are exactly what `voice_lines_vox/miranda_lawson/hila_intent_cuts.csv` carries
(`712675`, `1149328`, …): they are stream/sound ids, i.e. **file names**. That is why the first build
looked plausible and did nothing.

### 4b. The route this pack uses: BeardLib `<Sounds>` over OGG

`<Sounds prefix="rb21">` registers OGG buffers with SuperBLT's XAudio API and intercepts
`SoundSource:post_event`, i.e. it replaces at the **event** the game posts, before Wwise is
involved. It is the documented heister-voice mechanism — the BeardLib Sounds page describes
`prefix` as "Some sounds in Payday 2 are separated by a prefix, this lets you have multiple voices
for heisters and many more things" — and it is the only route that can play OGG, so it also covers
the OGG-encoded lines §4a cannot touch. Published packs mix the two for exactly that reason: the
2025-26 *PAYDAY 3 Joy Voicelines* ships a `mod_overrides` tree and states that camera marks, guard
marks and special-enemy lines "require Beardlib to function".

This pack is BeardLib-only, for three reasons: no Wwise encoder exists in this repo (a Windows
binary; the pipeline here is ffmpeg on Linux), the clips are OGG, and the BeardLib route needs no
game-file extraction at all.

### 4c. Why the ids here are bark event names (evidence, not a guess)

- PD2's own Lua posts these strings. `playerstandard.lua` builds `f02x_`/`f03a_` + `sin`/`plu`,
  `l01x`–`l03x`, `f21<ssuffix>_sin`, `f36x_any`, `f38_any`, `f40_any`, `f41_*`, `f44x_any`,
  `f39_any`, `f48x_any`, `g18`; `playerarrested.lua` builds `f11<ssuffix>_sin` / `f13<ssuffix>_sin`;
  `playerequipment.lua`, `playerdamage.lua`, `playertased.lua`, `groupaistatebase.lua` post
  `s01x_plu`, `s02x_plu`, `s12`, `s13`, `s05x_sin`, `s07x_sin`, `s08x_sin`, `g43`, `g80x_plu`,
  `g81x_plu`, `g90`, `g40x_any`, `g41x_any`, `g42x_any`.
- The community *Heister Voice IDs* sheet is that same call path: its ids are typed into PocoRose and
  played in game via `sound():say(id)`, the function PD2 itself uses.
- The speaker is a Wwise switch, not part of the name: `tweak_data.criminals.characters[*]
  .static_data.voice`, Hila = `rb21` (`ecp_female`, `PlayerSound:set_voice`). BeardLib's
  `CheckSoundID` compares `data.id == posted_id` **and** `contains_any(data.prefixes,
  source:get_prefixes())`, so `prefix="rb21"` is what keeps other heisters on their vanilla lines.

| Where the 176 ids come from | Ids | Examples of slots they feed |
| --- | --- | --- |
| `playerstandard.lua` `_start_action_intimidate` (the interact commands) | `f02x_sin`/`f02x_plu`/`f02b_sin`, `f03a_sin`/`f03a_plu`/`f03b_any`, `l01x`–`l03x` + `_sin`/`_plu`, `f36x_any`, `f38_any`, `f40_any`, `f41_sin`/`f41_plu`/`f41_any`, `f44x_any`, `f39_any`, `f48x_any`, `g18` | `civ.dontmove`, `civ.down`, `cop.hands`, `cop.kneel`, `cop.cuffs`, `inspire.faster`, `inspire.get_up`, `move.on_me`, `civ.talk`, `move.this_way`, `mark.turret`, `mark.camera`, `caution.wait` |
| `playerstandard.lua` mark shouts (`priority_shout .. "x_any"`, quiet `.. "y_any"`) | `f30x_any`–`f34x_any`, `f47x_any` (+ the `y` variants) | `mark.dozer`, `mark.shield`, `mark.taser`, `mark.cloaker`, `mark.sniper`, `mark.medic` |
| `playerarrested.lua` `call_teammate(line)` → `line .. ssuffix .. "_sin"` | `f21<code>_sin`, `f11<code>_sin`, `f13<code>_sin` for all 22 heister codes (`a c b l m d n o p q r s t u v w x y z ac aa ab`) | `move.follow`, `downed.need_help`, `cuffed.pick` |
| `playerequipment.lua`, `playerdamage.lua`, `playertased.lua`, `playerbleedout.lua`, `groupaistatebase.lua` | `s01x_plu`, `s02x_plu`, `s12`, `s13`, `s05x_sin`, `s05b_sin`, `s07x_sin`, `s08x_sin`, `f11e_plu`, `g43`, `g80x_plu`, `g81x_plu`, `g90`, `g40x_any`, `g41x_any`, `g42x_any` | `drop.*`, `revived.thanks`, `hurt.*`, `revive.*`, `downed.need_help`, `nade.*`, `ammo.low` |
| community *Heister Voice IDs* sheet (the callouts heist scripts post) | `g01`–`g92`, `p01`–`p28`, `v04`/`v08`/`v23`/`v32`, `d01x_sin`…`d05`, `r02a_sin`, `s05a_sin`, `dsp_radio_checking_1`, `dsp_stop_all`, `whistling_attention`, `bri_14`, `bri_29` | `move.left`/`right`/`up`/`in`/`go`, `spot.*`, `tech.*`, `kill.*`, `win.generic`, `mask.go`, `loot.secured`, `pager.*`, `call_teammate.hey_you` |

### 4d. What the *Log Sounds* option is for

Not discovery: it is BeardLib's `LogSounds` option (Mods → BeardLib options), which prints
`Incoming sound check: ID %s Prefixes %s` from `SoundManager:CheckSoundID`. Use it only to see a bark
this pack deliberately leaves alone or spells differently — the heist-scripted callouts that need
heist-specific text (`p33`–`p47`, most of `v01`–`v58`, `g61`–`g68`) and the `_sin`/`_plu`/`_any` or
`x`/`y` variants. Adding one is a line in `voice_lines_vox/miranda_lawson/slot_event_ids.csv` plus
`make -sC tools/pd2-las voices`.

## 5. Things that do **not** apply to this mod

- No `assets/mod_overrides/` copy: that root is for the §4a `.stream` route (and raw bundle
  overrides). Our replacement audio is OGG and must go through `SoundsModule`.
- No `.stream`/`.wem`/soundbank conversion *in this pack*: it needs Wwise IMA ADPCM (§4a), which an
  OGG cutter does not produce. The pack that ships does write it — `tools/pd2-las/wwise_ima.py`, §7.
- No load-order/priority requirement: BeardLib loads mods through its own frameworks after its own
  `init`, and our mod has no Lua that must run before/after anything. `mod.txt` priority is only for
  the BLT list's ordering.
- No localization/strings work: the clips are audio only; they do not add subtitles.

## 6. When nothing is replaced (troubleshooting)

A 2026-11-24 report ("unpacked in mods, still hear Hila") was re-verified against the loaders and
the game Lua, and the dropped pack's keying was right: `tweak_data.criminals.characters.ecp_female`
`static_data.voice = "rb21"` (`tweakdata.lua`) and the AI teammate path agrees
(`CharacterTweakData:_init_team_ai` sets `ecp_female.speech_prefix = "rb21"`,
`TeamAISound:init`/`set_voice` put it in the `robber` switch). BeardLib's
`SoundManager.lua` maps `set_switch` values into `engine_source:get_prefixes()`
(`BeardLibSetSwitch` hook → `mapped_prefixes = table.map_values(data.switch)`) and
`ComparePrefixes` matches `<Sounds prefix="rb21">` against exactly that, so a correct install
replaces barks and a silent one is environmental. Check, in order:

1. **Layout.** `PAYDAY 2/mods/Miranda Lawson VO over Hila/main.xml` must exist exactly one folder
   deep. The zip is named with underscores (`Miranda_Lawson_VO_over_Hila.zip`) but the folder
   inside uses spaces (`Miranda Lawson VO over Hila`); creating a folder after the zip's name and
   extracting into it double-nests, and `FindMods` scans only `mods/*` — one level, no recursion.
2. **The SuperBLT log** (`PAYDAY 2/mods/logs/`). If it says `Sounds module requires the XAudio
   API!`, the BLT build predates XAudio (or BeardLib 5.x is not installed at `mods/BeardLib/`);
   `BeardLibSoundManager.Closed` then short-circuits every check and vanilla audio always plays.
   The log also lists each mod it loaded — the folder must appear there.
3. **Main menu → Mods.** Both this mod (from `mod.txt`) and BeardLib must be listed and enabled.
4. **Log Sounds** (Mods → BeardLib options). With it on, shout as Hila in any heist and read the
   `Incoming sound check: ID … Prefixes …` line. `ID g18 Prefixes rb21` means the pack was asked
   and answered (this pack ships `g18`); `Prefixes none` means the `robber` switch never reached
   the source (report it — that would be a new loader fact); no line at all means step 2 failed.
   The heist-scripted callouts §4d lists are deliberately not covered, so some vanilla lines
   between replaced ones are expected.

## 7. The stream pack (`Miranda_Lawson_VO_over_Hila_Stream.zip`)

The id-keyed route: the game streams `soundbanks/streamed/regular_vox/<voice-line id>.stream`, so the
file *is* the replacement. No event names, no Lua, no BeardLib, no XAudio API.

### 7.1 Layout

```
PAYDAY 2/
└─ mods/
   └─ Miranda Lawson VO over Hila Stream/     ← folder name is free-form
      ├─ main.xml                             ← <mod name="…"> and nothing else to configure
      ├─ mod.txt                              ← BLT mod-list metadata
      ├─ README.txt
      ├─ hila_stream_map.csv                  ← build manifest: id → slot → clip
      └─ soundbanks/streamed/regular_vox/
         ├─ 712675.stream                     ← 699 files, one per written voice-line id
         └─ …
```

`main.xml` carries no `<Sounds>` and no `<Hooks>`: BLT serves the files and the game reads them by id,
so nothing has to be registered. `mod.txt` only makes the folder appear in the main-menu mod list.

### 7.2 The file format

RIFF, 64-byte header, then Wwise IMA ADPCM in 36-byte mono / 72-byte stereo blocks of 64 samples
(4-byte block header: `int16` predictor, `uint8` step index, reserved byte; then 32 bytes of nibbles
= 63 coded samples and one padding nibble). The byte rate is `(rate // 64) * block_align` — 24 804
for mono 44.1 kHz — and the six-byte `fmt` tail is `00 00 04 00 00 00` for mono. Both details are
read off real files and pinned by `tests/test_wwise_ima.py`; the full derivation, and why the encoder
picks a start index per block, is in
[`tokoyami-hila-voice-mod-analysis.md`](tokoyami-hila-voice-mod-analysis.md).

### 7.3 Coverage

| | |
|---|---|
| Voice-line ids in the mapping | 885 (`voice_lines_vox/miranda_lawson/hila_intent_cuts.csv`) |
| `.stream` files written | 699 — 661 s of audio, 14.4 MB zipped |
| Ids left vanilla | 189 — 27 Vorbis (`hila_vorbis_ids.csv`) for the format reason above, plus 162 ids of slots whose best clip scored below 8 on semantic fit with no take in either source archive (`removed_slots.csv`): vanilla Hila plays those lines. 3 of the 162 are also Vorbis. |
| Not covered by design | the `robbers_mission_gen` bank (heist-scripted NPC lines with their own text) and music/radio |

### 7.4 Install and check

1. Unzip into `PAYDAY 2/mods/` so that `mods/Miranda Lawson VO over Hila Stream/main.xml` exists —
   one folder deep, like §3.
2. Start the game, play a heist with Hila (as your heister or as an AI teammate).
3. Nothing in `mods/logs/` is expected: this pack has no Lua and no loader API to fail. If a line
   still sounds like Hila, it is one of the 27 Vorbis ids (§7.3), or another Hila voice pack is
   loaded after this one and writes the same ids.

Rebuild and verify offline:

```bash
make -sC tools/pd2-las voices_stream      # rebuilds the zip + .sha256, prints `tracked`
unzip -p dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip \
  "Miranda Lawson VO over Hila Stream/soundbanks/streamed/regular_vox/712675.stream" > /tmp/712675.stream
python tools/pd2-las/wwise_ima.py /tmp/712675.stream --wav /tmp/712675.wav   # header, duration, audio
.venv/bin/python -m pytest -q tests/test_wwise_ima.py tests/test_hila_stream_pack.py
```

Heard in game on 2026-11-25: the user installed this pack and reported that it works (the BeardLib
route did not, on 2026-11-24). The report also named two clips cut inside a word, `civ.down` and
`call_teammate.hey_you`; both edges were moved onto the gaps around the wanted words and pinned by
`tests/test_hila_cut_edges.py`, so the tracked bytes are newer than what was heard
(`docs/pd2-las/in-game-checklist.md`). Nothing else of it has been listened to line by line.

## 8. The character packs (2026-11-25)

Two more packs of the §7 route exist, one per purpose-authored bark set. Both write the **same shared
`regular_vox` ids** as `Miranda_Lawson_VO_over_Hila_Stream.zip`, so the three are alternatives: install
exactly one. With several installed, the one that loads last wins and the others are inert for the ids
they share.

| Pack (`dist/…`) | Voice of | Covers | Not covered (vanilla) |
| --- | --- | --- | --- |
| `Geralt/Geralt_VO_over_Rust_Stream.zip` | Geralt of Rivia (`references/GERALT VOICE (PAYDAY 2).zip`, CP866 file names) | 29 slots the set carries — 315 `.stream` files, including `kill.taser`/`mark.taser` | 49 slots (546 ids) with no take in the set; 24 covered ids are also Wwise Vorbis |
| `Arivus/Arivus_VO_over_Hoxton_Stream.zip` | Arivus (`references/ARIVUS VOICE (PAYDAY 2).zip`) | 18 slots the set carries, plus the shared `call_teammate.hey_you` slot, which plays the Geralt 'Hoxton.' callout borrowed from the GERALT archive (the set has no Arivus callout) — 324 `.stream` files | 59 slots (540 ids) with no take in the set; 21 covered ids are also Wwise Vorbis |

The ids either pack writes are listed per target in `voice_lines_vox/targets/`
(`rust_shared_regular_vox.csv`, `old_hoxton_shared_regular_vox.csv`, `slot → bank → id`, with
`written=yes` equal to the zip's file names); the shared versus dedicated bank split, and the
open question of which one Rust barks from, are
[`pd2-voice-stream-tables.md`](pd2-voice-stream-tables.md) (D73).

Notes that matter:

- **Rust is on his own bank.** The reference Rust pack (`references/Marine VO for Rust.7z.001`)
  ships `char_rust` and `robbers_mission_gen` only, and its author's changelog says the U247 build
  dropped the `regular_vox` lines — so a working Rust voice pack on the 64-bit build is
  dedicated-bank. The id-keyed re-key of this pack's takes to `char_rust/` is built by
  `make -sC tools/pd2-las voices_char_rust` but **not shipped**: it waits on
  `voice_lines_vox/geralt/char_rust_ids.csv`, the map that names which id is which line (D74,
  [stream tables](pd2-voice-stream-tables.md)).
- **Rust** is the punk heister (`npc_criminal_wild_1`), the target of `dist/Geralt/Geralt_over_Rust.zip`.
  Whether he plays his heister barks from the shared `regular_vox` bank is **not verified**: the original
  crew do, and newer heisters are documented elsewhere as `char_<heister>`. If Geralt-over-Rust installs
  and Rust still barks in his vanilla voice, that is the reason — this pack then replaces the shared bank
  (everyone else) but not Rust.
- **Old Hoxton** (`npc_criminals_suit_1`, the shared-suit heister of `dist/Arivus/Arivus_over_Hoxton.zip`) is
  on the shared bank, so installing the Arivus pack replaces those lines for every heister on it, not for
  Old Hoxton alone. The 'Hoxton.' callout in it is Geralt's voice — it is the callout file the GERALT
  archive carries, borrowed per the user's 2026-11-25 decision; the rest of the pack is Arivus's.
- Uncovered slots stay **vanilla**, the same rule the Hila pack applies to its sub-8 slots
  (`voice_lines_vox/miranda_lawson/removed_slots.csv` records the Hila-specific removals). Nothing was
  scored for these sets; purpose-authored takes are shipped as-is, wording unverified by ear.
- Build: `python tools/build_character_stream_mod.py --pack all` (or `make -sC tools/pd2-las voices_geralt`
  / `voices_arivus`). The tracked bytes are reproducible; the packs have **not** been heard in game.
