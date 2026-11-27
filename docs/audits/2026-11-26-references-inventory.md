# `references/` — what it holds, what can go, and how to group it (2026-11-26)

Request 2026-11-26: *"Analyse `/references` — what can be deleted safely? How can they be grouped
in folders?"* This is the report; nothing was deleted or moved to produce it.

**Adopted 2026-11-26.** The owner approved all of it except the PDF: the six folders in §4 are the
layout now (PR #67), the five files in §1 are gone except `Syndey Voicelines.pdf`, which is kept
because a VO mod may need the printed table. The sheets in §2 are imported, in full (D81). Anything below
that quotes a flat path (`references/Geralt.7z`) describes the tree the audit was made against; the
current path is the folder-prefixed one.

**Outcome in one line:** the folder is not full of cruft — of 178.5 MB across 63 files, 161 MB is
read by a tool or is the only copy of a source, and the defensible deletions (5 files, 17.5 MB) change
no pack byte and shrink nobody's clone; the grouping is worth doing but is a 33-file edit that
re-bakes 5 of the 13 packs' `BUILD_INFO`, so it should be done in two passes.

## How this was measured

| Sweep | Method | Result |
| --- | --- | --- |
| Every `references/…` string literal | grep over `tools/`, `tests/`, `voice_lines_vox/`, `um/`, `.github/`, `Makefile`, `*.sh`, then each literal resolved on disk | 33 Python files + 3 shell/Makefile lines; no dead literal |
| Module-level constants | `status.INPUTS` (16 literal paths), `build_honoko2_dae.MAT_TEXTURE_SOURCES` / `PACKS[].tex_override`, `render_honoka.TEX_DIR`, `hila_voice_clips.ARCHIVE`, `build_hila_stream_mod` paths | these, not name-frequencies, are the real "who reads what" |
| Prose | every file name searched in `docs/` and `knowledge/` | 41 of the 63 files are not named in `references/README.md` at all |
| Shipped bytes | all 13 `dist/*/*.zip` unpacked; `references/` strings extracted from every `.json`/`.txt`/`.md`/`.lua` under 3 MB | 5 packs carry them (see the table in §4) |
| Git | `git ls-files -z references`, `git status --porcelain --ignored=matching` | 63 tracked, 0 untracked, 0 ignored, no LFS — the folder **is** in history, 1.8 GB of it |
| Sheets | row counts and status preambles of the 5 CSVs vs `voice_lines_vox/sheets/COVERAGE.md` | see §2, this is the one real discovery |

A name-grep alone misleads here: `L_1.dds`, `location` and `old_hoxton_head_df.dds` all "match" code
and tests that never open them (`location` gets 20–45 hits, all prose words or pack-internal file
names). Every verdict below rests on an explicit path literal, a `BUILD_INFO` string, or a test that
opens the file.

## What is in there

| Group | Files | Size | Verdict |
| --- | --- | --- | --- |
| Character sources | `l4d2_miranda_lawson_1.zip`, `PC _ Computer … (Romance).zip`, `Geralt.7z`, `1581859199_135363.rar` | 30.5 MB | keep — the builders' only source |
| Reference templates | `2b.rar`, `Heister - FPS Gloves in TPS 2.zip`, `Ada Wong over Joy.7z`, `npc_criminals_suit_1.7z`, `npc_criminals_ecp_female.7z`, `Outfit for Honoka-109-1-1-1628020933.zip` | 45.4 MB | keep — read by `build_joy_head_mods.py`, `build_las.py`, `extract_2b.py`, `tmc.py` |
| Arivus / Miranda head | `old_hoxton_head_df(1).dds`, `old_hoxton_head_df.dds`, `EYE_Diff.png`, `Hoxier Hoxton V2.zip` | 16.8 MB | 1 delete, 3 judged in §1d |
| Honoka | `.dae` 3.46 + `.rigged.glb` 2.86 + 27 `L_*.dds` 9.83 + 3 `Tex_*.dds` 2.25 + `location` | 18.4 MB | keep except `Tex_07(L_7) 2.dds` and the `.glb` note in §1d |
| Voice packs | `Tokoyami Hila.7z`, `Marine VO for Rust.7z.001/.002`, `Голос Лоусон.7z`, `LAWSON VOICE (PAYDAY 2).7z`, `ARIVUS VOICE (PAYDAY 2).zip`, `GERALT VOICE (PAYDAY 2).zip` | 65.1 MB | keep — five are container/table sources, and one (`Голос Лоусон.7z`, ~870 whole-line oggs) is the source `tools/hila_voice_clips.py` cuts Miranda's barks from |
| Sheets | 5 CSVs, `Syndey Voicelines.docx`, `Syndey Voicelines.pdf`, `Bodhi Voicelines.zip` | 2.3 MB | delete 1 duplicate + 1 print; keep the rest, see §2 |

## 1. Safe to delete

"Safely" is used in one sense only: **no pack byte changes, no test loses its input, no document
stops being true.** The doc sentences that would stop being true are listed with each item.

### 1a. Nothing else changes (0.05 MB)

| File | Size | Why it is dead |
| --- | --- | --- |
| `Honoka/location` | 9 B | A Windows shell artifact containing `Location$`. No consumer, no mention, no format. |
| `Hila regular_vox - regular_vox.csv` | 40 KB | Content-identical duplicate of the tracked `voice_lines_vox/hila_regular_vox.csv` (885 ids in both, same columns). Not named anywhere in this repository. |

### 1b. Two sentences to reword (1.16 MB)

| File | Size | Blocker |
| --- | --- | --- |
| `Syndey Voicelines.pdf` | 1.16 MB | A 68-page `Microsoft® Word LTSC` print of the `.docx` beside it. Delete the print, keep the editable original; `docs/pd2-voice-mod-install.md` mentions the *community sheet*, not this file, so no doc changes — but say so in `references/README.md` when the sheets get documented (§2). |

### 1c. Three sentences across three files (4.00 MB)

`old_hoxton_head_df.dds` is the first Arivus atlas edit; `old_hoxton_head_df(1).dds` supersedes it and
is the build input. No code reads the first one — `tests/test_arivus_glb_pack.py`'s `DDS` tuple names
files *inside* the shipped pack, and `build_joy_head_mods.py` opens only `(1)`. Deleting it makes
these three true statements false, and they are all deliberate:

- `references/README.md` ("the earlier bytes stay here and in git as provenance")
- `docs/renders/arivus/model/over-hoxton/README.md` ("kept beside it")
- `tools/pd2-las/MODLOG.md:897` ("stays in git and on disk as provenance")

Rewriting them to "in git history at `<sha>`" is honest, since git does keep the blob. That is the
whole cost — but it is a real cost: this repository uses `references/` as its provenance shelf, and
4 MB is a cheap shelf.

### 1d. One code list, or a judgment call (1.00 / 8.70 / 2.41 / 2.86 MB)

| File | Size | What deleting costs |
| --- | --- | --- |
| `Honoka/Tex_07(L_7) 2.dds` | 1.00 MB | The retired `Honoko4` suit diffuse (D44). Read by nothing: the live overrides are `Tex_07(L_7)3.dds` and `Tex_23(L_23)2.dds` (`PACKS[].tex_override`, and `render_honoka.ALT_DIFFUSES` is built from those). Only `status.INPUTS` lists it — drop that one line (16 → 15) and the MODLOG entry stays as history. |
| `Hoxier Hoxton V2.zip` | 8.70 MB | "Reference only" per `references/README.md`: proves the Old Hoxton texture-override paths and the icon DDS format, carries no models. Both facts are now baked into `build_joy_head_mods.build_arivus_hoxton_mod` and written down; deleting loses the ability to re-derive the icon DDS from the original. One README row to remove. |
| 15 unused `L_*.dds` (`0,1,2,5,6,9,10,11,12,13,16,19,22,25,26`) | 2.41 MB | **Not free.** `render_honoka.render_dds_sheet` globs `L_*.dds`, the contact sheet is 6×5 tiles, `tests/test_honoka_dds_render.py` hard-codes `(6*240, 5*278+56)`, and `docs/renders/honoka/dds/honoka_dds_contact_sheet.png` is tracked. Deleting these means a curated list in the renderer, a new expected size, a new test expectation and a regenerated render — for 2.4 MB. Keep. |
| `Honoka/…Secret_Report.rigged.glb` | 2.86 MB | Regenerable by `tmc_export.py` from the TMC inside `Outfit for Honoka…zip` (tracked), but `render_honoka.py` reads it for the tracked glb renders, so deleting it means re-exporting before the next render. Keep; it is the geometry the renders are made from. |

**Total defensible deletion: 5 files, 17.5 MB** — `location`, the duplicate Hila CSV, the Sydney PDF,
the superseded Arivus atlas, the retired Honoka diffuse. Ten lines of edits, no pack rebuilt.

## 2. What must not be deleted — and the one finding that matters

The four sheet exports are **not** dead weight; they are the inputs the repository currently says it
does not have. `voice_lines_vox/sheets/COVERAGE.md` reports:

| Tab | Declared | COVERAGE.md says held | Actually in `references/` |
| --- | --- | --- | --- |
| `regular_vox` | 20,343 (20,293 / 50 / 32) | 25 rows (0.1 %) | `PAYDAY 2 Sound files - regular_vox.csv`, preamble `99.88%,20293 complete / 50 partial / 32 (?)` |
| `robbers_mission_gen` | 4,220 (1,720 / 93 / 2,407 / 14) | page 1 only | `… robbers_mission_gen.csv`, preamble `1720 / 93 / 2407 / 14` |
| `char_sydney` | 1,037 complete | page 1 only | `… char_sydney.csv`, 1,037 rows |
| Hila's `regular_vox` | 887 / 885 ids | full | both the canonical CSV and a duplicate here |

The preambles match the declared counts digit for digit: these are the `File → Download → CSV`
exports COVERAGE.md is still asking for, and it tells the reader to save them in `references/`,
which is where somebody already put them. **Do not delete them; import them** (done 2026-11-26, D81) —
`make -sC tools/pd2-las voices_sheets SHEET="references/sheets/PAYDAY 2 Sound files - regular_vox.csv" WANT=<tab>`
— and then rewrite the coverage table. That is the D76/D77 work, and it is worth more than every
deletion in §1 combined.

Also keep:

- `Syndey Voicelines.docx` — 1,301 distinct ids against the CSV's 1,037. It is **not** a superset of
  the export but a different, fuller one; the document is the original, the CSV is a tab.
- `Bodhi Voicelines.zip` (one `.xlsx`) — the only Bodhi data in the repository. Nothing reads it yet;
  it is research, not dead weight.
- `Payday 2 Voiceline IDs - Heister Voice IDs.csv` — the community callout sheet that
  `docs/pd2-voice-mod-install.md` §"Heister Voice IDs" transcribes by hand.
- Everything in the "keep" rows of the group table: the four character archives, all six templates,
  `2b.rar` (also unpacked by `recover_env.sh`), the `.dae`, the 12 `L_*.dds` and 2 `Tex_*.dds` the
  builder reads, `EYE_Diff.png`, and the six voice archives.

## 3. The deletion arithmetic

Deleting 17.5 MB removes 10 % of the folder and **0 bytes from any clone**: the blobs stay in
history (no LFS, and `docs/audits/2026-11-05-repository-mistakes.md` already decided that rewriting
history is not on the table). So the argument for deleting is not weight, it is that the folder
should not contain files that no longer mean anything. By that argument §1a and §1d's first row are
clear yeses, §1b and §1c are yeses if you accept provenance living only in git, and the other three
are noes.

The folder's real problem is not dead weight — it is that 41 of 63 files are not named anywhere, so
a newcomer cannot tell `2b.rar` (a build input) from `Hoxier Hoxton V2.zip` (a curiosity).

## 4. Grouping

Proposed layout — six folders, grouped by *what reads them*, not by game:

```
references/
├── README.md               (unchanged index, paths updated)
├── characters/             l4d2_miranda_lawson_1.zip, PC _ Computer … (Romance).zip,
│                           Geralt.7z, 1581859199_135363.rar
├── templates/              2b.rar, Heister - FPS Gloves in TPS 2.zip, Ada Wong over Joy.7z,
│                           npc_criminals_suit_1.7z, npc_criminals_ecp_female.7z,
│                           Outfit for Honoka-109-1-1-1628020933.zip
├── textures/               old_hoxton_head_df(1).dds, EYE_Diff.png, Hoxier Hoxton V2.zip
├── honoka/                 Honoka_DOAXVV_Secret_Reportout.dae, .rigged.glb, L_*.dds, Tex_*.dds
├── voice/                  Tokoyami Hila.7z, Marine VO for Rust.7z.001/.002,
│                           LAWSON VOICE (PAYDAY 2).7z, Голос Лоусон.7z,
│                           ARIVUS VOICE (PAYDAY 2).zip, GERALT VOICE (PAYDAY 2).zip
└── sheets/                 the 4 sheet CSVs, Syndey Voicelines.docx, Bodhi Voicelines.zip
```

### What a move actually breaks

| Cost | Detail |
| --- | --- |
| Code | 33 Python files hold `references/…` literals (13 of them a single constant); `status.INPUTS` alone is 16 paths; 3 shell/Makefile lines; `extract_2b.py`, `build_las.py`, `build_models.py`, `rw_dff.py`, `tmc.py`, `source_model.py`, `render_honoka.py`, `build_honoko2_dae.py`, `build_joy_head_mods.py` (10 literals), `build_hila_stream_mod.py`, `hila_voice_clips.py`, `wwise_ima.py`, `build_las_pack.py`, `import_voiceline_sheet.py` |
| Tests | 12 test modules name paths directly, plus `test_dist_layout.test_character_archives_live_in_references` (4 exact names) and `test_repo_weight.ALLOWED` (`references/Marine VO for Rust.7z`, whose reason must stay ≥ 20 chars) |
| Docs | `references/README.md` (every row), `voice_lines_vox/sheets/COVERAGE.md` ("save it in `references/`"), `tools/pd2-las/README.md`, `references` paths in `docs/pd2-*`, `docs/pd2-las/*`, `knowledge/*` |
| **Pack bytes** | 5 of the 13 packs embed `references/` strings of their own, so a move in their folder changes their checksum and needs a rebuild: `dist/Miranda/OfficeSuite.zip` and `OfficeSuite_Head.zip` (13 `references/honoka/…` + the Honoka outfit zip, in `BUILD_INFO.json`), `dist/Miranda/Miranda_Lawson_VO_over_Hila_Stream.zip`, `dist/Arivus/Arivus_VO_over_Hoxton_Stream.zip`, `dist/Geralt/Geralt_VO_over_Rust_Stream.zip` (one "Source archives" line each in `README.txt`). The other 8 packs name no `references/` path and are byte-safe under any move. |

So the move is **not** free anywhere except in the 8 packs, and it is cheapest exactly where the
packaging is already dynamic: `build_honoko2_dae` writes `BUILD_INFO` from `TEX_DIR`/`DAO` constants,
so `honoka/` costs a constants edit plus two rebuilds, while `characters/` and `textures/` cost a
constants edit and zero rebuilds.

### Two passes, in this order

1. **Pass A — the four folders no pack names:** `characters/`, `templates/`, `textures/`, `sheets/`.
   Update literals + tests + `references/README.md` + `COVERAGE.md`, then
   `pytest -q tests`, `check_links.py`, `gen_docs_index.py --check`, `pack_checksum.py` (13 match,
   unchanged), `fresh.py check` (13/13) as the proof that nothing was re-baked by accident.
2. **Pass B — `honoka/` and `voice/`:** the five packs above are rebuilt in the same commit
   (`make -sC tools/pd2-las honokodae honokodae_head`, `make -sC tools/pd2-las voices_stream`,
   `… voices_geralt`, `… voices_arivus`), the five sidecars regenerate, and `fresh.py check` proves
   13/13 again. Review this one as a diff where 5 `.zip` + 5 `.sha256` change and nothing else does.

Lowercase `honoka/` is deliberate: the other folders are lowercase and the tracked
`docs/renders/honoka/` already is. Renaming costs nothing beyond this move because the name only ever
appears inside a path literal.

## 5. Recommendation

1. Delete the five files in §1 (17.5 MB) — but do it as one reviewable commit whose diff is: five
   deletions, one `status.INPUTS` line, three sentences. Keep `Hoxier Hoxton V2.zip`, the 15
   `L_*.dds` and the `.glb`.
2. Then import the three sheets and rewrite `COVERAGE.md` (§2). That closes D76/D77 rather than
   tidying around them.
3. Then Pass A of the grouping, then Pass B. Each pass is one PR, and Pass A is the one that pays:
   it makes `references/` navigable without touching a single shipped byte.

The single highest-value documentation fix found here, independent of any of it: `references/README.md`
names 22 of 63 files. The six folder headings in §4 are also six paragraphs of that README.
