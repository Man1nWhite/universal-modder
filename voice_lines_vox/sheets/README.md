# sheets

Community voice-line sheets, normalized to `id,who,what,notes,needs_review` by
`tools/import_voiceline_sheet.py` (make `-sC tools/pd2-las voices_sheets SHEET=… [WANT=Rust]
[LEADS=1]`). One file per tab, `<tab>.csv`; `--who` adds `<tab>_<who>.csv`; `--keys` adds
`<tab>_keys.csv` (`slot,id,score,what,who`).

**A sheet names its own bank.** `regular_vox` is the shared bank the original crew streams from, so
its ids say nothing about a dedicated `char_<module>` bank — importing it does **not** fill
`voice_lines_vox/geralt/char_rust_ids.csv` (D75). A `_keys.csv` row is a word-overlap *lead*: the id
has to be the right heister's and checked against the line before any table or pack uses it (D76).

| File | Rows | Of the tab's | What it is |
| --- | --- | --- | --- |
| `regular_vox.csv` | 25 | 20,343 | **Head only.** Status block stripped, `(?)` carried as `needs_review`. A worked example, not the tab. |
| `regular_vox_keys.csv` | 10 | — | The slot leads those 25 rows support (`move.on_me` → `On me`, id 236512; `mark.taser` → `Taser!`, 413529). Similarity only. |
| `regular_vox_hoxton.csv` | 4 | — | The `--who Hoxton` slice of the head, showing what a per-speaker import looks like. |

The importer now prints the tab's own coverage and measures the file against it
(`tab declares 20343 rows … INCOMPLETE: this file holds 25 of 20343 rows (0.1%)`), and
`--require-full` exits 2 unless the file holds every row the tab declares. Use it, or check the
printed line, before treating any import as complete.

The unmodified export is a reference input and is not tracked; `tests/fixtures/regular_vox_head.csv`
is the byte-pinned first 25 data rows (preamble included) the parser is tested against.

## The sheets these come from

Two documents have been read. **A tab is reached by `gid`, not by name** (`&gid=<number>` from the
tab's URL); `&sheet=<name>` falls back to the first tab.

| Document | Tab (`gid`) | Rows (status block) | In this repo |
| --- | --- | --- | --- |
| `1c3uXGyH5wRb7J1BH…NCv4` | `regular_vox` (`0`) — Hila's line list, `PD2 ID / Speech / Category` | 887 rows, 885 ids | **full**: `voice_lines_vox/hila_regular_vox.csv` (the source of `miranda_lawson/hila_intent_cuts.csv`) |
| `196bzO0M-VAmtjd7V…ZvA` | `regular_vox` (`0`) | 20,293 complete / 50 partial / 32 `(?)` | **head only** (25 rows) |
| `196bzO0M-VAmtjd7V…ZvA` | `robbers_mission_gen` (`1280565535`) | 1,720 complete / 93 partial / 2,407 incomplete | **no** — the only tab read so far that names Rust lines (`3115131` It's delivered) |
| `196bzO0M-VAmtjd7V…ZvA` | `char_sydney` (`1647606386`) | 1,037 complete / 0 / 0 | **no** — a *dedicated-bank* sheet (`char_sydney`), the shape a `char_rust` sheet would have |

`char_rust` is **not** a tab of either document: `&gid=` on a `sheet=char_rust` request returns page
one of `regular_vox`, i.e. the name does not exist. So the re-key's map (D75) is still unfilled.

Which bank a document covers is worth checking before assuming: the `1c3uXGyH…` tab titled
`regular_vox` is *Hila's* 885-line list, and those are exactly the 885 ids in
`targets/rust_shared_regular_vox.csv` and `targets/old_hoxton_shared_regular_vox.csv` — the same id
set for every heister, which is what "shared bank" means (D73) and why a pack that writes it
replaces the line for everyone.
