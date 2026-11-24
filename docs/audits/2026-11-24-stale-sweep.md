# Stale tools, docs and tests — sweep (2026-11-24)

Request 2026-11-24: "search for stale tools, documentations, tests". This is the report: what was
checked, what came back stale, and what the sweep deliberately left alone. Two passes: the PAYDAY 2
pipelines in `tools/` and the documents that describe them first — the voice pack is the newest artifact
and the one that actually shipped wrong once — then the whole checkout (second half).

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

## Whole repository, same day

The second pass widened the sweep from the PAYDAY 2 pipelines to the whole checkout: 421 Markdown files,
`um/`, `tools/`, `tests/`, `skills/` and its two copies, `.github/workflows/`, and the manifests
(`plugin.json`, `gemini-extension.json`, `mcp.json`, `.mcp.json`, `opencode.json`, `.codex/`,
`.cursor/`, `.vscode/`, `.agents/plugins/marketplace.json`).

| Sweep | Method | Result |
| --- | --- | --- |
| Markdown links | every relative `[..](path)` in 421 files resolved from the linking file | 2 broken, both fixed (below). The 3 remaining hits are a literal `...` and a code token, not links. |
| Anchors | every `#fragment` in a link matched to a heading slug | none broken (the one flag was my slugger collapsing `+`; GitHub keeps `--`) |
| File references | `tools/…`, `um/…`, `tests/…`, `bin/…` paths named in `.md`/`.yml`/`.json`/`.toml` | 39 do not resolve; all are history (audits and `MODLOG.md` naming files that existed when written) or knowledge notes naming the scripts of *the mods they describe*, not this checkout |
| Orphan documents | every `.md` searched for an inbound mention | 6: `SECURITY.md` and `.github/pull_request_template.md` (GitHub reads them), `agents/*.md` (auto-discovered role files), and `docs/pd2-las/christie-fit-probe.md` — the only genuinely unreachable doc, now linked |
| Orphan tools | `tools/**/*.py` searched for by name | none |
| Knowledge base | `um kb check --index` | `PASS: 247 notes checked`, `INDEX.md`/`index.json` current |
| Skill copies | `diff -rq skills .agents/skills` and `.claude/skills` | identical |
| Manifests | every path named in the plugin/extension/MCP configs | all exist; `mcp.json` (plugin schema, `streamable-http`) and `.mcp.json` (Claude Code, `http`) are two formats on purpose |
| Marketplace | `.agents/plugins/marketplace.json` | points at **upstream**; the root README says so explicitly ("installs upstream, which has none of the above") |
| Vacuous tests | AST scan: `test_*` functions with no assert, no `raises`, no `fail()` | 2, both intentional raise-only checks (`test_las_pack.py::test_all_weighted_joints_mapped`, `::test_validation_passes`) |
| Distribution | `pack_checksum.py` | 20 ZIPs match their sidecars |

### Fixed in the whole-repo pass

- **`docs/renders/honoka/model/head/README.md`** linked `../../../pd2-las/in-game-checklist.md`, which
  resolves to `docs/renders/pd2-las/…` and does not exist. Four levels up is right.
- **`docs/audits/2026-11-11-miranda-mips-and-object.md`** embedded
  `../pd2-las/renders/miranda_mips_before_after.png`. No commit of this fork ever carried that PNG — the
  `docs/pd2-las/renders/` dump the render-consolidation removed is where it was meant to live. The section now
  says the figure is missing and gives the command that redraws it (`mip_audit.py --before … --sheet …`).
- **`README.md`** listed every pack except the fork's only audio pack; the voice pack and its install
  contract are in "What this fork adds" now.
- **`docs/pd2-las/christie-fit-probe.md`** had no inbound link from anywhere; it is accurate (its claims
  check out against `Christie_LAS/BUILD_INFO.json`: `runtime_verified: false`, the `sleeve_gloss` block
  counts), so it is linked from the Christie render README rather than deleted.
- **`AGENTS.md`** — the "strange git state" rule said what not to do, not what to do. It now names the
  restart symptom (`dist/` back on the base commit, `status` calling packs `broken`) and the way back.

### Found and left alone

- `tools/pd2-port/releases/` does not exist. That is by design: release notes are written per tag, and
  `lawson-las.yml` fails a tag build with `Missing notes for tag` when they are absent.
- `agents/*.md` are unreferenced by any document because the harness discovers the folder; they are live.
- Two `dist/` packs are named in `tools/pd2-las/README.md` only through group rows ("the eleven head packs"),
  which is why a naive per-file check reports them missing. They are described.

### A trap worth knowing (hit during this sweep)

The sandbox re-cloned the repository mid-session, leaving local `HEAD` at the base commit with the pushed
work only on the remote. The working tree still looked right, so `make -sC tools/pd2-las status` was the
first thing to complain — it called `Miranda_Lawson_VO_over_Hila` `broken`, because a fresh checkout had
written the **base** zip and sidecar (813029 B, `0f00354c…`, sidecar naming the file without `dist/Hila/`)
over the rebuilt ones, and `pack_checksum.py` failed on the sidecar's path. Nothing was wrong with the
repo: after confirming `git log origin/<branch>..HEAD` was empty and that no working-tree file differed
from the remote, `git reset --hard origin/<branch>` restored `8e8e47b1…` and `pack_checksum.py` passed
20/20. Hence the `AGENTS.md` line above.

## Verification after the edits

`pytest tests -q` → **730 passed, 35 skipped**; `pyflakes um tools tests` clean;
`tools/pd2-las status` → `Miranda_Lawson_VO_over_Hila` `tracked`; rebuild → same `613914 B` /
`8e8e47b1…` — the docstring edit changes no byte, as a reproducible build must not.
