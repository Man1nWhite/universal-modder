# sheets

Community voice-line sheets, normalized to `id,who,what,notes,needs_review` by
`tools/import_voiceline_sheet.py` (make `-sC tools/pd2-las voices_sheets SHEET=references/sheets/<file>.csv
TAB=<tab> [WANT=Rust] [LEADS=1]`). One file per tab, `<tab>.csv`; `--who` adds `<tab>_<who>.csv`;
`--keys` adds `<tab>_<who>_keys.csv` (`slot,id,score,what,who`).

**A sheet names its own bank.** `regular_vox` is the shared bank the original crew streams from, so
its ids say nothing about a dedicated `char_<module>` bank — importing it does **not** fill
`voice_lines_vox/geralt/char_rust_ids.csv` (D76). A `_keys.csv` row is a word-overlap *lead*: the id
has to be the right heister's and checked against the line before any table or pack uses it (D77).

The unmodified exports are tracked in `references/sheets/` (D81), so every row below is reproducible
from this checkout: nothing here paged a website, and nothing here needs one.

| File | Rows | Of the tab's | What it is |
| --- | --- | --- | --- |
| `regular_vox.csv` | 20,404 | 20,343 declared | **The tab, in full.** Status block stripped, `(?)` carried as `needs_review` (29 rows), one repeated id (`1052460785`) printed by the importer and kept, not merged. 22 speakers, led by `Cop (static)` (3,159), `Cop` (2,291) and `Chains` (1,911). |
| `regular_vox_keys.csv` | 3,994 | — | The slot leads the whole tab supports, over 65 of the intent slots and 22 speakers. Similarity only, and the loudest lesson of the tab: the same line scores for several heisters. |
| `regular_vox_hoxton.csv` | 1,550 | — | The `--who Hoxton` slice of the tab: one heister, every line, showing what a per-speaker import looks like. |
| `regular_vox_hoxton_keys.csv` | 434 | — | That slice's leads, 50 slots. A per-heister slice is the shape a real mapping would take — after the line is checked against the audio. |
| `robbers_mission_gen.csv` | 5,499 | 4,220 declared | The objective-callout bank: 1,811 rows carry a `who` (1,720 with a line), 3,686 are ids the sheet lists with nothing filled in yet. It names Rust lines by id (`3115131` It's delivered); they are **not** `char_rust` ids (D78). |
| `char_sydney.csv` | 1,037 | 1,037 declared | A dedicated bank, complete: every row is Sydney, none needs review. The importer keeps the first four columns, so the tab's `Type` column lands in `notes` and `Sub-Type`/the second `Notes` are not carried — the export in `references/sheets/` keeps them. |

The importer prints the tab's own coverage beside the file's row count and measures one against the
other (`tab declares 20343 rows … FULL: 20404 of 20343`), and `--require-full` exits 2 unless the
file holds every row the tab declares. Where the two disagree it is the status block that is stale,
not the export: rows were added after the block was last recalculated.

`tests/fixtures/regular_vox_head.csv` is the byte-pinned first 25 data rows (preamble included) the
parser is tested against — a fixture, not a stand-in for the tab.

## The sheets these come from

Two documents, four tabs, all read and all held. **A tab is reached by `gid`, not by name** (`&gid=<number>` from the
tab's URL); `&sheet=<name>` falls back to the first tab.

| Document | Tab (`gid`) | Rows (status block) | In this repo |
| --- | --- | --- | --- |
| `1c3uXGyH5wRb7J1BH…NCv4` | `regular_vox` (`0`) — Hila's line list, `PD2 ID / Speech / Category` | 887 rows, 885 ids | **full**: `voice_lines_vox/hila_regular_vox.csv` (the source of `miranda_lawson/hila_intent_cuts.csv`) |
| `196bzO0M-VAmtjd7V…ZvA` | `regular_vox` (`0`) | 20,293 complete / 50 partial / 32 `(?)` | **full**: `regular_vox.csv` (20,404 rows, 845 KB) + its keys and Hoxton slice |
| `196bzO0M-VAmtjd7V…ZvA` | `robbers_mission_gen` (`1280565535`) | 1,720 complete / 93 partial / 2,407 incomplete | **full**: `robbers_mission_gen.csv` (5,499 rows) — it names Rust lines by id (`3115131` It's delivered) |
| `196bzO0M-VAmtjd7V…ZvA` | `char_sydney` (`1647606386`) | 1,037 complete / 0 / 0 | **full**: `char_sydney.csv` — a *dedicated-bank* sheet, the shape a `char_rust` sheet would have |

`char_rust` is **not** a tab of either document: `&gid=` on a `sheet=char_rust` request returns page
one of `regular_vox`, i.e. the name does not exist. So the re-key's map (D76) is still unfilled.

Which bank a document covers is worth checking before assuming: the `1c3uXGyH…` tab titled
`regular_vox` is *Hila's* 885-line list, and those are exactly the 885 ids in
`targets/rust_shared_regular_vox.csv` and `targets/old_hoxton_shared_regular_vox.csv` — the same id
set for every heister, which is what "shared bank" means (D73) and why a pack that writes it
replaces the line for everyone.
