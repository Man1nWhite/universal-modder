# Coverage of the two source sheets

"Does the repo have the sheet?" now has one answer: **all four tabs, in full.** The exports are
tracked in `references/sheets/` and imported into this folder by `tools/import_voiceline_sheet.py`
(`make -sC tools/pd2-las voices_sheets SHEET="references/sheets/<file>.csv" TAB=<tab>`), so the
numbers below can be regenerated from the tree with no network. Decision: D81.

A tab is reached by **`gid`**, never `&sheet=<name>` (that returns tab one) — this is what made the
earlier page-by-page reads look impossible.

| Link (tab) | Declared by the sheet's own status block | Held here | Imported file |
| --- | --- | --- | --- |
| `1c3uXGyH…` `gid=0` — Hila's `regular_vox` line list | 887 rows / 885 ids | **yes, all 885 ids** | `voice_lines_vox/hila_regular_vox.csv` (one level up; it is the source of `miranda_lawson/hila_intent_cuts.csv`) |
| `196bzO0M…` `gid=0` — `regular_vox` | 20,343 (20,293 complete, 50 partial, 0 incomplete, 32 `(?)`) | **the tab: 20,404 rows, 20,403 ids** | `regular_vox.csv` + `regular_vox_keys.csv` |
| `196bzO0M…` `gid=1280565535` — `robbers_mission_gen` | 4,220 (1,720 complete, 93 partial, 2,407 incomplete, 14 `(?)`) | **the tab: 5,499 rows, 5,499 ids** | `robbers_mission_gen.csv` |
| `196bzO0M…` `gid=1647606386` — `char_sydney` | 1,037 (100% complete) | **the tab: 1,037 rows, 1,037 ids** | `char_sydney.csv` |

Three things to read carefully in that table.

1. **The status block is a snapshot, not a count.** `regular_vox` declares 20,343 rows and the export
   holds 20,404; `robbers_mission_gen` declares 4,220 and holds 5,499. Rows were added after whoever
   wrote the block last recalculated it. The importer prints both numbers (`FULL: 20404 of 20343`),
   which is why it prints them instead of trusting one.
2. **`robbers_mission_gen` is mostly ids waiting for text.** 3,686 of its 5,499 rows carry nothing but
   an id — the tab's 2,407 "incomplete" plus ids nobody has typed a line for yet. The 1,811 rows with
   a `who` are the usable part.
3. **`char_sydney` is the shape a `char_rust` sheet would have** — one dedicated bank, 100 % covered.
   No tab of either document is `char_rust` (`&gid=` on it returns page one of `regular_vox`), so the
   re-key's id map (D76) is still unfilled, and D81 leaves that refusal in place.

`regular_vox.csv` carries one repeated id (`1052460785`) — printed by the importer and kept, not
silently merged (D77) — and 29 rows marked `needs_review`. `char_sydney.csv` keeps the tab's first
four columns (`id, who, what, notes`), so its `Type` column lands in `notes` and its `Sub-Type`/extra
`Notes` columns are not carried; the export in `references/sheets/` keeps everything.

**The one-click path, kept for a tab nobody has exported yet.** Open the sheet → the tab →
`File → Download → Comma-separated values (.csv)` → save it in `references/sheets/` →
`make -sC tools/pd2-las voices_sheets SHEET="references/sheets/<file>.csv" TAB=<tab>`. With a full
tab the import finishes in one step and the coverage line reads `FULL: <n> of <n>`.
