# Coverage of the two source sheets

"Does the repo have the sheet?" has one answer per link. Regenerate the numbers with the importer;
it prints them itself. A tab is reached by **`gid`**, never `&sheet=<name>` (that returns tab one).
Google's `tq=` query parameter is ignored by the same endpoint, so **paging is the only way to read
a tab in bulk** from this environment.

| Link (tab) | Declared | Held here | Brought to full by |
| --- | --- | --- | --- |
| `1c3uXGyH…` `gid=0` — Hila's `regular_vox` line list | 887 rows / 885 ids | **yes, all 885 ids** (`voice_lines_vox/hila_regular_vox.csv`) | already complete |
| `196bzO0M…` `gid=0` — `regular_vox` | 20,343 (20,293 complete, 50 partial, 32 `(?)`) | **25 rows (0.1%)** | 138 pages, or one `File → Download → CSV` |
| `196bzO0M…` `gid=1280565535` — `robbers_mission_gen` | 4,220 (1,720 complete, 93 partial, 2,407 incomplete, 14 `(?)`) | **page 1 only** | 24 pages, or the export |
| `196bzO0M…` `gid=1647606386` — `char_sydney` | 1,037 (100% complete) | **page 1 only** | 8 pages, or the export |

The local `voice_lines_vox/hila_regular_vox.csv` is the first row of this table in full — it is where
`miranda_lawson/hila_intent_cuts.csv` comes from — and that is the only one of the four the repo can
call complete.

**No tab of either document is `char_rust`.** Requesting `gid`/`sheet` for it returns page one of
`regular_vox`, so the re-key's id map (D75) is still unfilled; `char_sydney` shows what such a tab
looks like when a dedicated bank does get written up.

**The one-click path.** Open the sheet → the tab → `File → Download → Comma-separated values (.csv)`
→ save it in `references/` → `make -sC tools/pd2-las voices_sheets SHEET=references/<file>.csv
TAB=<tab> LEADS=1`. With a full tab the import finishes in one step and the coverage line reads
`FULL: <n> of <n>`.
