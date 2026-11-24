# Stale tools, docs and tests — sweep (2026-11-24)

Request 2026-11-24: "search for stale tools, documentations, tests". This is the report: what was
checked, what came back stale, and what the sweep deliberately left alone. Scope is the PAYDAY 2
pipelines in `tools/` and the documents that describe them — the voice pack first, because it is the
newest artifact and the one that actually shipped wrong once.

**Outcome in one line:** no orphan tool, no broken path reference and no unreproducible byte turned
up; the staleness was all *prose and coverage* — three documents still described the pre-re-key pack,
the "what is open" list and the in-game checklist did not know the voice pack exists, and the suite had
no test at all for the invariant whose absence shipped a silent pack.

## What was checked, and how

| Sweep | Method | Result |
| --- | --- | --- |
| Path references | every `tools/…`, `docs/…`, `tests/…`, `voice_lines_vox/…`, `dist/…` string literal in `tests/`, `tools/**/*.py` and `.github/workflows/` resolved on disk | 6 hits, all synthetic: `dist/character/pack.zip` and the `docs/…` prefixes `test_render_rules.py` asserts are *rejected*, plus `.github/skills`/`.github/copilot-instructions.md` in `test_um.py`/`test_agent_docs.py`. No dead reference. |
| Orphan tools | every `tools/**/*.py` searched for by module name across scripts, docs, Makefile, workflows | none unreferenced |
| Tool still runs | `tools/fit_hila_intents.py` re-run against the tracked CSVs | 78/78 slots pinned, **zero diff** in `hila_slot_pieces.csv` — tool and data agree |
| Tracked bytes | `python tools/pd2-las/pack_checksum.py` | 20 distribution ZIPs match their `.sha256` |
| Rebuild | `python tools/build_hila_voice_mod.py` | `613914 B`, sha256 `8e8e47b1…`, unchanged by these edits |
| Skips | `pytest -q -rs`, reasons counted | 35 skips, four reasons, all environment-dependent: 26 × "2B templates not extracted", 4 × "needs ffmpeg", 2 × "lupa not installed", 2 × "sourcepp is an optional extra", 1 × "Git Bash only". None hides a broken test. |
| Suite | `pytest tests -q` | 730 passed (722 + the 8 new ones), pyflakes clean |

## Stale, and fixed here

1. **`tools/build_hila_voice_mod.py` docstring** still described the pack it wrote *before* the
   re-key: "sound id = PD2 ID". It now says the id is the bark event name the game posts, and that
   `slot_picks.csv` beats the stem heuristic (which the docstring also omitted).
2. **`voice_lines_vox/README.md`** — three claims:
   - it called BeardLib's *Log Sounds* the "in-game verification recipe", i.e. a prerequisite. It is
     a coverage check for a bark that was deliberately left vanilla; the install doc §4d says so now
     and the README agrees.
   - "peak-matched to -1.5 dBFS" omitted the two clamps and the dead-band that explain the shipped
     `-1.9..0.0 dBFS` spread (no gain under 0.5 dB, at most +12 / −9 dB).
   - `hila_slot_pieces.csv` was listed as "Generated:" with no author — two tools write it, with the
     same schema, and it also ships inside the zip. Said so.
3. **`docs/pd2-voice-mod-install.md`** — the page promised "how to verify it in game" (it verifies
   *coverage*), and its required layout left out `slot_to_ogg.csv` and `hila_slot_pieces.csv`, which
   ship in the pack folder at its root.
4. **`docs/pd2-las/HANDOFF.md`** — the one pack with no in-game record at all cited "`Log Sounds`
   verification"; it now cites the packaging contract.

## Stale lists, and closed here

5. **`tools/pd2-las/README.md` → "Next"** is, per `AGENTS.md`, where "what is open" lives. It did not
   mention the voice pack, which is the only pack nobody has heard a single bark from. Folded into
   item 1 (still 129 lines: the file has a 130-line budget test).
6. **`docs/pd2-las/in-game-checklist.md`** had no voice section — the canonical "waiting for a human
   with the game" list skipped the one artifact that needs no human skills beyond installing a mod.
   Added six checks: mod list, does it replace at all, do other heisters keep vanilla lines, the
   `Log Sounds` coverage step, which gaps are deliberate, and that subtitles still say Hila.

## Stale by omission: the test suite

7. **No test covered the voice pack's keying contract.** `build_xml` raises on a missing or doubly
   claimed event, but nothing read `slot_event_ids.csv`, so the shipped bug — a `main.xml` keyed on
   numeric voice-line ids — would pass every check again. New `tests/test_hila_voice_pack.py`
   (8 tests, no ffmpeg/py7zr, ~0.05 s) pins: slots ↔ event rows are a bijection; event names are
   unique and spelled like Wwise events; **no id is numeric or a `hila_id`**; `prefix="rb21"`, one
   `<sound>` per event, `stop_id = <id>_stop`; both build-time refusals; every slot has a curated
   pick and no pick's heard text names Shepard/Commander/Commando.

   Verified the way a regression test should be: substituting `712675` for `g81x_plu` in
   `slot_event_ids.csv` fails exactly `test_event_ids_are_wwise_event_names_not_voice_line_ids`,
   and the file was restored.

## Found, judged, not changed

- **`tools/fit_hila_intents.py` writes the same `hila_slot_pieces.csv` as the builder.** It looks
  like a schema collision, but the header is the builder's and the file was written that way on
  purpose (`577339e`), so whichever runs last leaves the same rows — confirmed by the zero-diff run
  above. Its other output, `hila_intent_fit.csv`, is read by nothing; it is a review artifact, and it
  is the only record of the heuristic score per slot. Kept.
- **The numeric ids in `hila_intent_cuts.csv`** are not stale: they are the `.stream` file names of
  the other route (install doc §4a). They stay, labelled as provenance.
- **Two deliberate wording tensions** stay as they are: the `Call <Name>` slot is *intended* to say
  "Hey, you." while the clip actually says "you take point." (the README documents that under known
  gaps), and `slot_picks.csv` notes quote the trimmed names ("trimmed `Commander?`"), which is why the
  new name check reads only `cut_line`/`clip_text`.

## Verification after the edits

`pytest tests -q` → **730 passed, 35 skipped**; `pyflakes um tools tests` clean;
`tools/pd2-las status` → `Miranda_Lawson_VO_over_Hila` `tracked`; rebuild → same `613914 B` /
`8e8e47b1…` — the docstring edit changes no byte, as a reproducible build must not.
