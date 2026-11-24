# Stale tools, docs and tests — second sweep (2026-11-24)

Request 2026-11-24: "search for stale tools, documentations, tests for the whole repo". The
[first sweep](2026-11-24-stale-sweep.md) (merged in PR #43) fixed the voice-pack documents and the
suite's keying coverage. This pass re-ran the whole checkout independently and looked at what the
first sweep sat next to: the **D57 removal** (2026-11-23, `Honoko2`–`Honoko4` zips dropped from
`dist/` and from the builders) had left its own stale documentation behind — the dated in-game
capture record of `Honoko2` still presented the removed pack as the live one.

**Outcome in one line:** every tool runs or is deliberately manual, every gate is green (suite 767
passed, `green` 14/14 stages, 20/20 zips rebuild byte-identical), and the staleness was one decision
old: six texts — the capture record, its manifest, `references/README.md`, one test docstring and two
code comments — still described the pre-D57 world.

## What was checked, and how

| Sweep | Method | Result |
| --- | --- | --- |
| Path literals | every `tools/…`, `docs/…`, `tests/…`, `dist/…`, `references/…` string in live `.md`, `tests/`, `tools/**/*.py`, `um/`, workflows resolved on disk (2,852 literals; `docs/audits/`, `knowledge/`, `examples/` judged separately) | no dead reference in a live document; the unresolved names are in-mod paths (`hooks/outfits/loader.lua` and friends), `git show <rev>:<old-path>` history, or dated records that already say "retired/removed" |
| Markdown links | every relative `](target)` outside `docs/audits/`, `knowledge/`, `examples/` (185 links) | 0 broken |
| Heading anchors | every `](page#anchor)` (3 links) | 0 broken |
| Orphan tools | every `tools/**/*.py`, `*.sh` searched for by filename across the repo | none unreferenced |
| Tool ↔ test map | each `tools/` and `um/` module counted against `tests/` and the docs | 15 tools with no test mention, all authoring/diagnostic scripts (`pose_preview`, `shellview`, `trace_run`, `tmc_export`, `fit_hila_intents`, …) named from docs and run by hand; every test module maps to a live module |
| Suite | `.venv/bin/python -m pytest -q -rsxX tests` | 767 passed, 9 skipped — the 26 "2B templates not extracted" skips **pass** once `tools/pd2-las/extract_2b.py` runs, so no skip hides a broken test; the remaining 9 are lupa (2), ffmpeg (4), sourcepp (2), Git Bash (1) |
| Skip budget | `tools/pd2-port/check_skip_budget.py` | within budget, reasons all environment-dependent |
| Lint | `python -m pyflakes um tools tests` | clean |
| Full gate | `make -sC tools/pd2-las green` | all 14 stages pass, including "every tracked pack built again in a copy of the tree" — 20 of 20 zips byte-identical |
| Tracked bytes | `python tools/pd2-las/pack_checksum.py` | 20 distribution ZIPs match their `.sha256` |
| CLI | `bin/um --help` + `--help` of each group | 10 groups, the same list the CI smoke loop and `AGENTS.md` name |
| Make targets | every `make -sC tools/pd2-las <target>` named in docs and workflows against the Makefile | all exist |
| Skill copies | `skills/` vs `.agents/skills` vs `.claude/skills`, front-matter `name:` vs folder | identical copies, all 12 names match |
| Release state | `tools/pd2-port/STATUS.md` ("There is no release") vs `gh release list` | consistent (empty) |
| Knowledge base / publish | `um kb check --index`, `um publish check .` | PASS (247 notes), PASS (1,065 files) |

## Stale, and fixed here

All six are the D57 blast radius or its immediate neighbors. The model for the fix is the
`officesuite/2026-11-15` capture record, which carries its D54 rename banner.

1. **`docs/renders/honoka/in-game/2026-11-15/README.md`** presented `dist/Honoka/Honoko2.zip` as
   "the Pack" in the present tense and tied it to `make -sC tools/pd2-las honokodae` — which since
   D57 builds only `OfficeSuite`. A reader following it would rebuild the wrong zip and think the
   captures don't match. Added the D57 banner (pack removed 2026-11-23, bytes in git history,
   captures kept as the record of that build) and labelled the `Honoko3`/`Honoko4` sibling bullets
   as removed too.
2. **`docs/renders/honoka/in-game/2026-11-15/manifest.json`** — all eight notes said the capture was
   "from `dist/Honoko2.zip`": the wrong path even at capture time (the pack lived at
   `dist/Honoka/Honoko2.zip`, as D57 and the README say) and no hint it is gone. Notes now carry the
   full path and "(removed 2026-11-23, D57)".
3. **`references/README.md`** — the Honoka source row's outputs read "into `dist/Honoka/Honoko2.zip`
   through `dist/Honoka/OfficeSuite.zip`", naming removed zips as if shippable. Now names the tracked
   Honoka packs with the removal noted.
4. **`tests/test_glove_behavior_lua.py`** — the docstring claimed the `BODY_ONLY` + `glove_adapter`
   contract is "shared by `Christie_LAS` and `Honoko2`..`OfficeSuite`". Since D55 `OfficeSuite`
   ships its own hands (`glove_adapter=not spec.hands` — no adapter hook), and `Honoko2`..`Honoko4`
   are gone; the packs that share the contract today are `Christie_LAS` and `Christie_Clover_LAS`.
   The docstring now names those two and keeps the history.
5. **`tools/pd2-las/fresh.py`** — "`--only` keeps OfficeSuite and Honoko2..4 out of it": `PACKS` is
   `(OFFICE_SUITE,)` since D57, there are no Honoko2..4 to keep out.
6. **`tools/pd2-las/build_honoko2_dae.py`** — "Honoko2 (clearance=False) keeps the old shadow caster
   so its tracked bytes stand": Honoko2 has had no tracked bytes since D57. The comment now says the
   bytes it preserves are in git history and that the `clearance` branch survives for OfficeSuite's
   passes (what D57's "comments now say so" was meant to cover).

## Found, judged, not changed

- **Dated records naming removed things** — `docs/audits/**` (e.g. `bootstrap.sh`, the old
  `dist/lawson_*.zip` names), `tools/*/MODLOG.md` journals, `docs/pd2-las/DECISIONS.md` entries
  ("…are gone from the tree"), `tests/test_pd2_las_status.py`'s note that `Honoko2`..`Honoko4` moved
  the pack count to twenty, and `tests/test_glove_adapter.py`'s "until 2026-11-14 … deleted with
  their builder on 2026-11-14" (true: the pre-rebuild Christie packs and `build_christie_las.py`).
  History, already labelled where a reader could act on it.
- **`knowledge/**` field notes' `tools/…` paths** name scripts in the *other* repos the note is
  about (`tools/import_terraria.py`, `tools/limbo_tex.py`, …), not this tree — same dismissal as
  `2026-11-05-repository-mistakes.md`.
- **`tools/pd2-port/releases/` does not exist** — deliberate: no release is cut
  (`STATUS.md`: "There is no release"; `gh release list` is empty; the README says the next number
  is "3 while there is none").
- **`mcp.json` and `.mcp.json` both at the root, with different `type` values** — deliberate pair:
  `.mcp.json` is the project config (Claude Code et al.), root `mcp.json` is the Cursor *plugin*
  convention (`docs/audits/2026-11-13-agent-entry/harness-loaders.md`); each matches its schema.
  `hooks/hooks.json` (plugin `SessionStart`) and `.claude/settings.json` (clone) intentionally
  duplicate the `add-to-path.sh` call with their own root variables.
- **The 15 untested tools** (authoring probes and preview renderers: `pose_preview`, `pose_zoom`,
  `shellview`, `review_christie_idle`, `segment_fit`, `trace_run`, `tmc_export`, `tmc_las`,
  `diagnose_mesh`, `glove_check`, `las_head`, `fit_hila_intents`, `check_nm_convention`,
  `extract_las_rig`, `resolve_rig_names`, `um/render3d.py`) — named from docs, run interactively,
  and where they touch tracked bytes the byte-identical rebuild stage covers them. Not stale;
  recorded so the next sweep doesn't re-litigate them.
- **`build_honoko2_dae.py`'s `PackSpec` history comment** ("`Honoko2` (base proportions)… were built
  from this same source until D57") and the like are already labelled; left as written.

## Verification of these edits

Comments and documents only — no builder logic changed, so the tracked bytes cannot move (the
`green` run after the edits confirms it: 20/20 fresh rebuilds unchanged). Targeted suites around the
edits (`test_render_rules`, `test_agent_docs`, `test_glove_adapter`, `test_glove_behavior_lua`,
`test_pd2_las_status`, `test_honoka_dds_render`) pass, and `pyflakes` is clean.
