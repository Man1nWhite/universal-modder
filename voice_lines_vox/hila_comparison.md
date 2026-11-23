# Hila — What the three sources actually are (comparison)

> You asked to compare `hila_regular_vox.csv` (887 IDs) vs `https://docs.google.com/spreadsheets/d/1m0LBg2PKpB-bnWfOFj40AglCI1dLmAHLH3ydi3Y7uz8` (generic heister callouts) vs `hila_rb21_quotes.md` (wiki text). They are **three different layers** of Payday 2 voice — not duplicates.

---

## 1 — General sheet `1m0LBg2PKp...` (`heister_voice_ids.md`, gid=0)

**What it is:** Community **keybind table** for `managers.player:local_player():sound():say("xxxx",true,true)` / Pocorose / Basic Voices. ~195 abstract IDs:

- `g01` Downstairs, `g02` Upstairs, `g05` Go Up, `g13` Let's Go ...
- `p01` Alright, Let's do this, `v01` Okay On it!, `f11a_sin` Dallas Help me up! (`x` = character index, `_any/_sin/_plu`)
- **Not Hila audio** — it's the engine trigger string. Every heister re-uses the same `g01` etc with their own wav in `regular_vox/<id>.stream` via switch `robber=rbXX`.

**Overlap with Hila CSV (normalized):** only **18 / 195** lines match verbatim (e.g. generic `Flashbang!` = Hila `166718975 Flashbang!`). Rest are either Dallas/Chains/Wolf-specific or heist-specific `p/v` events that Hila *has* but with different wording.

Example generic NOT in Hila:
- `g70 Cops just got here`, `p05 Cops just got here`, `v01 Okay, On it!`, `f11a_sin Dallas Help me up!`

**Use:** `say("g01")` → Wwise picks `regular_vox/<mapped_ID>.stream` for current heister. To know *which* numeric `<ID>` that is for Hila, you need the Hila sheet below.

---

## 2 — Hila regular_vox `1c3uXGyH...` (`hila_regular_vox.csv/.md`, 887 IDs)

**What it is:** The **actual numeric bank** for Hila (`robber=rb21`) — `soundbanks/streamed/regular_vox/<PD2 ID>.stream` → `.wem` (Wwise 2013.2.10). Each row is a real recorded Hila line with category:

| PD2 ID | Speech | Category |
|---|---|---|
| 712675 | (pained) You, hey! | Request for help while downed |
| 1149328 | On your feet! | Inspire revive |
| 28880249 | Uh… I thought there was something going on… | Pager response |
| 296647770 | Hey, control. My boyfriend uses adult diapers… | Pager response |
| 684759174 | They better fear Hila! | Mask up |
| 221567123 | Hila will save you. | Reviving |

- **887 lines + header**, 20.4 MB if decoded. Categories: `Pager response` (33), `Hostage intimidate` (80+), `Direction` (60+), `Call <Heister>` (120+), `Mark shield/dozer/taser` etc.
- Duplicate IDs exist: `124587299` appears twice (Hang on! / I dropped an ammo bag), `134605380` twice — Wwise picks variation by Context.

**This is what you mod:** replace `<ID>.stream` with Miranda `wwise_ima_adpcm` → Hila says Miranda.

---

## 3 — Wiki `payday.fandom.com/wiki/Hila/Quotes` (`hila_rb21_quotes.md`, ~282 quoted lines)

**What it is:** Human-readable transcript, organized by gameplay *lore* (Masking up, Calling Crewmates, Special Enemies, Pager Responses, Safe House, etc). No IDs, no bank info, includes lore text like First World Bank speech.

Example wiki block:
- *Masking up:* "This should be easy.", "Okay, let's do this.", "Ready to rumble."
- *Pager Responses:* 32 lines including 2× long First World Bank speech (not in game as pager — wiki mistake)

---

## 4 — Overlap analysis (normalized: lower, strip punctuation)

### Hila CSV (887) vs Wiki (282 quoted)

- **Overlap: 180 / 281 wiki lines** are verbatim in CSV (e.g. `I thought I saw something strange, but it was nothing. All good.` ↔ `47568290 I thought I saw something strange, but it was nothing. All good.`)
- **CSV not in Wiki: 393 lines** — mostly numeric combat barks wiki editors omitted: `Taser is dead. (369916102)`, `I got the sniper. (116834972)`, `Careful (478405239)`, `They better fear Hila! (684759174)` etc.
- **Wiki not in CSV: 101 lines** — mostly wiki lore/Safe House/Unofficial categories:
  - Placeholders: `<heistername> follow me!` (wiki uses template, CSV has `Hey, Sokol!` etc per-heister)
  - Safe House stories: `I was in the army I'm not strange to guns.`, `We were gonna steal a tank…`
  - Movement barks wiki lists but CSV skips: `Ohhhh Shiiiiit!` (Birth of Sky parachute), `Listen up, this is a robbery…` (First World Bank speech — 50+ words, stored as one long `regular_vox` but wiki splits)
  - Transcription drift: wiki `Hey, wanna go shoots some bad boys after we get off work?` vs CSV `Hey, wanna go shoot some (?) after we get off work? (83072968)`

### Pager subset

- **CSV: 33 pager lines**, **Wiki: 32**
- Overlap: **13 / 32** (e.g. `Sorry control, I was just dreaming about vacations.` ↔ `51172570 Sorry control, I was just dreaming about vacations.`)
- Wiki-only pager (not in CSV, likely cut or mis-transcribed): `Hey, wanna go shoots some bad boys…`, `Hmm... I wasn't sleeping, honest.`
- CSV-only pager (wiki missed): `Hey, control. My boyfriend uses adult diapers and it's kinda grossing me out. Do you think that's sexist? (296647770)`, `Uh… I thought there was something wrong with my radio. All good now, though. (285562613)`, `There's literally nothing happening here. It's soo boring. (659408216)` — actual in-game Pager is longer than wiki shows.

### Generic sheet (1m0LBg…) vs Hila CSV

- **Generic 195 vs Hila 887: overlap 18** — generic is abstract `g01/p01/v01` system; Hila CSV is concrete numeric `888xxx` etc. They map via `SoundDevice:string_to_id("g01")` → `regular_vox/<ID>`, but text rarely matches 1:1 because Hila re-recorded with personality (e.g. generic `g13 Let's Go` vs Hila's 15 variants `Let's go / Let's go, guys. / Time to go, come on! / Let's get out of here.`)

### Tiny extra: `robbers_mission_gen_hila_ids.csv` (6 IDs, from `196bzO0M…` gid=1280565535)

This is a **different bank** (`robbers_mission_gen/<id>.stream`, heist-specific) — only 6 Hila lines in this repo's extract (e.g. `1867386 Ok we're in`). Not part of the 887 `regular_vox`; keep separate.

---

## 5 — What to use when

| Need | File | Why |
|---|---|---|
| Trigger a line by script `say("g01")` on any heister | `heister_voice_ids.md` (1m0LBg…) | Gives the abstract `g/p/v/f` string |
| Know **which numeric file** to replace for Hila's "On your feet!" | `hila_regular_vox.csv` (1c3uXGy…) | Gives `1149328 → Inspire revive` → `regular_vox/1149328.stream` |
| Know what Hila *says* in lore / pick a line for Miranda dub | `hila_rb21_quotes.md` (wiki) | Human-readable categories, no IDs |
| Map Miranda 866 oggs to Hila IDs | `Голос_Лоусон_manifest.csv` + this comparison | Pick Miranda `norvx_loyalty_01` → match to Hila `Reviving`/`Inspire` ID |

> Bottom line: **Generic sheet ≠ Hila audio**. Hila CSV is the ground truth for `rb21` bank; wiki is a readable subset with 101 extra lore lines not in bank and missing 393 combat barks that *are* in bank. Use CSV for modding, wiki for picking.
