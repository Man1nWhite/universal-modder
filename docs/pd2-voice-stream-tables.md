# Stream tables for Rust and Old Hoxton (where the VO packs' ids live)

A PAYDAY 2 heister line is a file the game streams: `soundbanks/streamed/<bank>/<id>.stream`.
Wwise strips every name, so **the id is the only handle** and the *bank folder* is the only
thing that says which heister (and which lines) a file belongs to. A **stream table** is
therefore `intent slot -> bank -> id`: one table per target heister. The slot -> bark *event*
name table (`voice_lines_vox/miranda_lawson/slot_event_ids.csv`) is a different thing and is
not what a `.stream` pack needs — keying on it is the route that failed silently in game
(`docs/pd2-las/DECISIONS.md`, D61).

Written by `tools/build_stream_tables.py`; pinned to the tracked zips by
`tests/test_stream_tables.py`.

| Table (`voice_lines_vox/targets/`) | Target | Bank | Rows | Written by the pack |
| --- | --- | --- | --- | --- |
| `rust_shared_regular_vox.csv` | Rust (`npc_criminal_wild_1`, switch `rb16`) | `regular_vox` | 885 ids | 315 (`dist/Geralt/Geralt_VO_over_Rust_Stream.zip`) |
| `old_hoxton_shared_regular_vox.csv` | Old Hoxton (`npc_criminals_suit_1`, switch `rb5`) | `regular_vox` | 885 ids | 324 (`dist/Arivus/Arivus_VO_over_Hoxton_Stream.zip`) |
| `rust_dedicated_char_rust.csv` | Rust | `char_rust` | 1,046 ids **measured** in `references/Marine VO for Rust.7z.001` | none — the packs write the shared bank |

Columns: `slot`, `bank`, `id`, `vanilla_kind` (`adpcm` / `vorbis`), `written`, `target`,
`model`, `dedicated_bank` (the folder a heister's *own* bank would be called, not what the pack
writes), `note`.

## What the two banks mean

| Bank | Folder | Who streams from it | Ids |
| --- | --- | --- | --- |
| shared | `regular_vox` | the original crew (Dallas, Hoxton, Wolf, Chains, Houston, Clover, Wick) and every pack this fork ships | one id set; every pack that writes it replaces the line for **everyone** on the bank, which is why the three packs are alternatives |
| dedicated | `char_<module>` (`char_rust`, `char_sydney`, `char_joy`, …) | newer heisters | their own ids — measured against two reference packs, **0 ids in common** with `regular_vox` |

Consequences a builder must not lose:

- **Never mix the banks.** A file written to a folder the heister does not stream from is inert,
  and it also replaces the wrong heister's line if that other heister does. The `rb` numbers are
  Wwise *switch values*, not folder names: Rust is switch `rb16` in folder `char_rust`, Hoxton is
  switch `rb5` in… `regular_vox` (see the next section).
- **One id, one file.** Two ids in the cut table can answer two slots; the first row wins and the
  manifest records the other (`tools/build_hila_stream_mod.py`, `load_ids`).
- **27 shared ids are Wwise Vorbis** (`vanilla_kind=vorbis`, `written=no`): an ADPCM pack cannot
  write them, so they stay vanilla. A dedicated bank has its own Vorbis files; they show up in a
  measured table and must be filtered the same way.

## Rust: the open question

`D71` records it: whether Rust plays his *heister* barks from `regular_vox` (where the pack writes
315 ids) or from `char_rust` is **not established** — not by the docs, not by a pack, and not in
game yet. Search results for this table:

1. **A reference Rust pack ships `char_rust`** — `references/Marine VO for Rust.7z.001` + `.002`
   (a 7z volume pair) carries 1,046 `char_rust` ids and 220 `robbers_mission_gen` ids, plus a `<Sounds>` module whose only entry is the `g36x_any` bark
   (`prefix="rb16"`) redirected to four `rust_med_kill` OGGs. A pack that replaces the whole voice
   over `char_rust` is evidence the *objective callouts* stream from there; it does not show the
   heister barks do. The author's own page (ModWorkshop, "Houshou Marine VO for Rust") does not
   say either.
2. **The community bank dump has `char_rust` and no `char_hoxton`**
   (`Javgarag/pd2-mods`, `resources/wwise-ids/`) — so a dedicated Hoxton bank is unlikely, and
   Rust's may exist.
3. **The measured table answers "what ids does `char_rust` have":** `rust_dedicated_char_rust.csv`,
   `tools/build_stream_tables.py --bank dedicated --dedicated "references/Marine VO for Rust.7z.001"`
   (`py7zr` joins the `.001`/`.002` pair). It is ids only — the reference pack does not say which
   slot each one answers — and **it shares no id with the 885 shared ones**, so a file cannot be
   written to both banks by mistake; it would simply be a different file.
4. **Deciding answer for the open question, if it is ever wanted:** one in-game install
   (`docs/pd2-las/in-game-checklist.md` 1e) — or an extraction of the game's own
   `soundbanks/streamed/` to see where the ids the Lua posts actually live. Until then the shipped
   pack keeps writing `regular_vox`, which replaces the shared line for every heister on it and
   Rust only if he streams from the shared bank.

### The re-keyed Geralt pack (D74)

`tools/build_character_stream_mod.py --pack geralt-rust --bank char_rust` (make
`voices_char_rust`) writes the *same 29 Geralt takes* into `soundbanks/streamed/char_rust/`, so the
pack changes Rust and no other heister. It reads its ids from
`voice_lines_vox/geralt/char_rust_ids.csv` — a tracked template with **no rows yet** — and refuses
to build while any picked slot is unnamed or an id is outside the measured table. That refusal is
the point: the 1,046 ids above say which files exist, not which line each one is, and the Marine
pack names only the medic-kill *event* (`g36x_any`), never a numeric id. Fill the map from an
extraction of the game's `soundbanks/streamed/char_rust` (decode a file, read its line) and the
next build produces the re-keyed pack.

### The voice-line sheet: what it can and cannot fill (D75)

The community `regular_vox` sheet (20,343 rows of `id | who | what | notes`, 99.88% covered, the
`(?)` rows listed as *need review*) is the first public table that pairs a numeric id with the
**text** of the line. `tools/import_voiceline_sheet.py` (make `voices_sheets SHEET=… [WANT=Rust]`)
turns an export of it into `voice_lines_vox/sheets/<tab>.csv` — the status block stripped, ids as
digits, notes kept, the sheet's own `(?)` carried as `needs_review` — and, with `--keys`,
`<tab>_keys.csv`: `slot, id, score`, where the score is word overlap against the slot's `cut_line`
in `hila_intent_cuts.csv`.

What it does **not** do is fill the re-key. Two independent reasons, and both stay true:

- **It is titled `regular_vox`.** A sheet names its own bank; `regular_vox` is the shared bank, so
  its ids say nothing about `char_rust`. The 29 slots in `voice_lines_vox/geralt/char_rust_ids.csv`
  need `char_rust` ids, and no public sheet of *that* bank is known.
- **A lead is a similarity, not a mapping.** `--keys` finds "On me" (id 236512) for `move.on_me`
  and "I need a medic bag" (986174) for `hurt.medic` at full score, but the same method puts "Help
  me up!" under `downed.need_help` for three different heisters; the id must be the one **Rust**
  says, and it must be checked against the audio. Nothing in `dist/` is built from a lead.

Where it does earn its place: it is the id→line source for the **shared**-bank route, the one the
two shipped packs already write. `voice_lines_vox/targets/rust_shared_regular_vox.csv` says which
id answers which slot for Rust (`slot, bank, id, …`); a sheet row whose id is in that table and
whose `who` is Rust is a *verified* pair for that slot, and a row that contradicts its slot is how
the 27 Vorbis exceptions and the "vanilla line still plays" notes get caught. That reconciliation
is the next step, and it needs the full export (`File -> Download -> CSV`), not 138 pages of it.

## Old Hoxton: the shared-bank heister

The community wiki lists Hoxton's switch as `rb5`; his lines are the shared ones, so the Arivus
pack replaces them for everyone on `regular_vox` — and the mode's own `call_teammate.hey_you`
slot is the borrowed Geralt "Hoxton." callout, not an Arivus take (`docs/pd2-voice-mod-install.md`
§8). A `char_hoxton` folder is **not** a bank the game is known to read; the tables name it only
as the folder a dedicated table would have, and no such table is tracked.

## Regenerate

```bash
python3 tools/build_stream_tables.py                       # both shared tables
python3 tools/build_stream_tables.py --target rust --bank dedicated \
    --dedicated "references/Marine VO for Rust.7z.001"      # the measured char_rust table
.venv/bin/python -m pytest -q tests/test_stream_tables.py
```

`--dedicated` reads an extracted folder, a `.zip` or a `.7z`/`.7z.001` volume (`py7zr`, which is how
the tracked `char_rust` table was measured); it records the ids it finds and nothing it does not: the slot of a measured id stays empty until a source names it.
