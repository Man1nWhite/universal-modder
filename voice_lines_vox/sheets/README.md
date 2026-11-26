# sheets

Community voice-line sheets, normalized to `id,who,what,notes,needs_review` by
`tools/import_voiceline_sheet.py` (make `-sC tools/pd2-las voices_sheets SHEET=… [WANT=Rust]
[LEADS=1]`). One file per tab, `<tab>.csv`; `--who` adds `<tab>_<who>.csv`; `--keys` adds
`<tab>_keys.csv` (`slot,id,score,what,who`).

**A sheet names its own bank.** `regular_vox` is the shared bank the original crew streams from, so
its ids say nothing about a dedicated `char_<module>` bank — importing it does **not** fill
`voice_lines_vox/geralt/char_rust_ids.csv` (D74). A `_keys.csv` row is a word-overlap *lead*: the id
has to be the right heister's and checked against the line before any table or pack uses it (D75).

| File | Rows | What it is |
| --- | --- | --- |
| `regular_vox.csv` | 25 | **Head only** — the first rows of the community `regular_vox` sheet (20,343 in the tab), status block stripped, `(?)` carried as `needs_review`. A worked example and the importer's test fixture source; replace it with a full export when one is available. |
| `regular_vox_keys.csv` | 10 | The slot leads those 25 rows support (`move.on_me` → `On me`, id 236512; `mark.taser` → `Taser!`, 413529). Similarity only. |
| `regular_vox_hoxton.csv` | 4 | The `--who Hoxton` slice of the head, showing what a per-speaker import looks like. |

The unmodified export is a reference input and is not tracked; `tests/fixtures/regular_vox_head.csv`
is the byte-pinned first 25 data rows (preamble included) the parser is tested against.
