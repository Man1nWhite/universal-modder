# What an agent pays to start here, before and after

Goal: an agent that opens this repository cold reaches the right action in fewer calls and fewer tokens, and
no fact is written in two places. This page gives the numbers and says how each was obtained. Everything it
cites is under [`2026-11-13-agent-entry/`](2026-11-13-agent-entry/).

- **Before:** `19ca55a` (main). **After:** `df3fe8c`. The commits after `df3fe8c` add this page and its
  evidence, nothing else.
- The baseline was committed as `1dacfc1` before any document, test or tool was touched. Two of its eight
  tasks were measured again later; "Corrected while checking" says which and why.
- A call is one shell command or one file read. Bytes are those of the file or of the command's output.
  Tokens are tiktoken's `o200k_base`.

## Eight tasks, replayed on both commits

`measure.py walk` starts with `AGENTS.md` in context and takes a step only when text already read points to
it; it stops with an error when the pointer is not there. Each step is run for real in a scratch worktree of
the commit. It is the shortest route the documents lead to, not a session of a model: see "Not checked".

| Task | Calls | Bytes | Tokens | Answer reached |
| --- | --- | --- | --- | --- |
| T1 set up after a sandbox restart | 3 → 1 | 1,605 → 1,944 | 619 → 758 | yes → yes |
| T2 state of all 14 packs | 4 → 1 | 3,030 → 1,684 | 1,138 → 680 | yes → yes |
| T3 is everything green | 7 → 1 | 14,649 → 1,407 | 3,972 → 432 | 4 of 6 checks → 6 of 6 |
| T4 rebuild one pack and prove its bytes | 3 → 1 | 20,621 → 161 | 6,606 → 64 | yes → yes |
| T5 was the pack seen in game, and were those the tracked bytes | 2 → 1 | 30,527 → 16,143 | 9,011 → 4,582 | yes → yes |
| T6 what is open | 3 → 1 | 31,262 → 11,845 | 8,720 → 3,266 | 4 of 5 items → 5 of 5 |
| T7 which command rebuilds `Geralt_over_Rust` | 0 → 0 | 0 → 0 | 0 → 0 | yes → yes |
| T8 a pack changed on purpose: make the suite pass again | 4 → 1 | 13,201 → 1,474 | 3,523 → 260 | yes → yes |
| **Total** | **26 → 7** | **114,895 → 34,658** | **33,589 → 10,042** | |

What the table hides:

- **T1 costs more bytes than before** (339 B, 139 tokens): one call instead of three, but `env` now ends
  with the state of all 14 packs.
- **T3 takes longer:** 252 s → 431 s (382 s in an earlier run of the same command). `green` runs what the
  six checks ran and also the auditor's self-test and the skip budget, which runs the suite a second time.
  The eight tasks together took 455 s before and 584 s after: T3 adds 179 s, T2 saves 40 s.
- Before, two of the 26 calls failed in this sandbox: `uv run --with pytest pytest -q tests`, the test
  command `AGENTS.md` gave (there is no `uv`: exit 127), and `bin/um kb check --index`, the launcher for a
  check `AGENTS.md` said CI runs (no PyYAML outside the venv: exit 1). After, none fails.
- Before, two calls were ones no document led to: `git status --short dist build` in T2 and
  `.venv/bin/python -m um kb check --index` in T3. After, there is none.
- Before, T3 never reached `pyflakes` or the `--help` of the `um` groups: only the workflow named them.
  T6 found nothing about the nine head packs.
- T5 and T6 are still one whole file each, 16 kB and 12 kB. They are 81 % of what the eight tasks cost now.

Files: [`before/walk.json`](2026-11-13-agent-entry/before/walk.json),
[`after/walk.json`](2026-11-13-agent-entry/after/walk.json).

## What loads at the start of a session

The instruction files a harness reads in a clone. Skills lists and tool descriptions also load at start and
are not counted: this work did not touch them.

| Harness | Before | After | How known |
| --- | --- | --- | --- |
| Claude Code | `CLAUDE.md`: 13,009 B, 3,863 tokens | `AGENTS.md`: 4,682 B, 1,275 tokens | measured on 2.1.323 |
| Codex | `AGENTS.md`: 13,009 B, 3,863 | 4,682 B, 1,275 | measured on 0.168.0 |
| Gemini CLI | `GEMINI.md`: 13,009 B, 3,863 | `GEMINI.md`, which imports `AGENTS.md`: 4,693 B, 1,280 | measured on 0.68.0 |
| Copilot CLI | the three files as one: 13,009 B, 3,863 | `AGENTS.md` and the 11 bytes of `GEMINI.md`: 4,693 B, 1,280 | measured on 1.0.110 |
| Cursor, CLI | `AGENTS.md` and `CLAUDE.md`: 26,018 B, 7,726 | 4,682 B, 1,275 | its documentation; not run |
| Copilot in VS Code | `AGENTS.md` and `CLAUDE.md`: 26,018 B, 7,726 | 4,682 B, 1,275 | its documentation; not run |
| Cursor, editor; OpenCode | `AGENTS.md`: 13,009 B, 3,863 | 4,682 B, 1,275 | documentation and source; not run |

- "Measured" is which files the harness itself reported, with no account, by `probe_harness.sh`
  ([`before/harness.txt`](2026-11-13-agent-entry/before/harness.txt),
  [`after/harness.txt`](2026-11-13-agent-entry/after/harness.txt)). The bytes and tokens are those of the
  files ([`before/start.json`](2026-11-13-agent-entry/before/start.json),
  [`after/start.json`](2026-11-13-agent-entry/after/start.json)).
- The two 26,018 figures assume the harness does not drop the second, identical file. Neither's
  documentation says it does.
- The source for every row, what a plugin install loads (no instruction file, except in Gemini CLI), the
  decision on `CLAUDE.md` and `GEMINI.md` with what it costs, and the command that makes each harness list
  what it loaded: [`harness-loaders.md`](2026-11-13-agent-entry/harness-loaders.md).

## What changed

**Commands** (`tools/pd2-las/Makefile`). Each merge is one the baseline shows saving calls.

| Question | Before | After |
| --- | --- | --- |
| Set up | `git checkout -- dist build node_modules`, `make … env`, `status.py` | `make -sC tools/pd2-las env`: puts back tracked files that are missing, builds the venv, unpacks the templates, prints the state |
| State of all 14 packs | `status` (4 packs), `check_all.py` (1), `build_joy_head_mods.py` (rebuilds 9 to find out), `git status` | `make -sC tools/pd2-las status`: 14 packs, 1,684 B |
| Everything green | 7 calls for 4 of the 6 checks; no document named the other two | `make -sC tools/pd2-las green` (`check_all.py --full`, 13 stages) |
| Rebuild and prove | read the README, build (9,023 B of builder output), `git status` | `make -sC tools/pd2-las <target>`: 161 B; the builder's output goes to `build/pd2-las/<target>.log` |

- `status` printed `sha256_ok`: the zip against the `.sha256` beside it. Every builder but lawson's writes
  that file itself, so after a build it was true whatever came out. `status` now prints `"is"`, and
  `"tracked"` means the zip is what the commit holds.
- `env` no longer needs `git checkout -- dist build` first, which also discards a pack that was rebuilt and
  not committed. It puts back only files that are missing.
- Targets `lawson` and `heads` are new, so every pack has one. The Makefile names 11 of the 70 scripts under
  `tools/` and reaches 48 (before: 8 and 42; [`after/graph.tsv`](2026-11-13-agent-entry/after/graph.tsv)).
- No entry point that CI or a test calls was removed. `status.PACKS` became `status.TARGETS`, with the one
  test that read it.

**Documents.** The eight documents an agent is sent to: 122,559 → 63,315 B.

| Document | Before | After |
| --- | --- | --- |
| `AGENTS.md` | 13,009 B | 4,682 B |
| `CLAUDE.md` | 13,009 B, a copy | deleted |
| `GEMINI.md` | 13,009 B, a copy | 11 B: `@AGENTS.md` |
| `README.md` | 25,636 B | 1,921 B |
| `docs/pd2-las/HANDOFF.md` | 18,929 B | 16,143 B |
| `tools/README.md` | 5,208 B | 6,604 B: it took the six invariants that hold across pipelines, word for word |
| `tools/pd2-las/README.md` | 11,598 B | 11,845 B |
| `tools/pd2-port/README.md` | 22,161 B | 22,109 B |

- Of 671 non-blank lines removed, 506 were dropped and 165 moved. Each is in
  [`ledger.tsv`](2026-11-13-agent-entry/ledger.tsv) with what became of it, and `measure.py ledger` stops
  with an error when a removed line has no entry. 226 of the dropped lines are the two copies.
- Sizes and hashes of packs in documents: 14 sizes in four documents and 14 hashes in one → none, apart from
  `tools/pd2-port/STATUS.md` (below). [`before/facts.tsv`](2026-11-13-agent-entry/before/facts.tsv),
  [`after/facts.tsv`](2026-11-13-agent-entry/after/facts.tsv).
- Against the merge base with upstream (`23902ef`), `README.md` had 244 of upstream's lines and 61 of this
  fork's; it has 11 and 26. `AGENTS.md`: 68 and 59 → 27 and 41
  ([`after/lines.tsv`](2026-11-13-agent-entry/after/lines.tsv)).
- **That costs two merge conflicts with upstream.** A trial merge of upstream's `main`
  (`rehan-remade/universal-modder` at `3c4ac6c`; `git merge --no-commit` in a scratch worktree) into
  `19ca55a` conflicts in four files: `.github/workflows/test.yml`, `knowledge/INDEX.md`,
  `knowledge/index.json`, `um/scan.py`. Into `df3fe8c` it conflicts in those and in `AGENTS.md` and
  `README.md`, which merged cleanly before. `GEMINI.md` is now upstream's, byte for byte. `CLAUDE.md` stays
  deleted without a conflict, as long as upstream does not change its own.

**Where a document was wrong:**

- The README said the four L4D2 head packs "were tested in game on 2026-11-05". `HANDOFF.md` said the
  tracked zips are later rebuilds, and git agrees: the tracked sha256 of `Miranda_L4D2_over_Joy` changed in
  three commits after that day. The README's sentence was true of the packs of that day, not of the ones
  in `dist/`.
- `tools/README.md` said "No code to deduplicate" and "234 tests" (measured 2026-10-19).
  `docs/audits/2026-11-12-tool-merge.md` found eighteen jobs with more than one implementation, and fourteen
  after its merges; the suite passes 800 tests.
- Every install command in the README installed `rehan-remade/universal-modder`, which has no `tools/` and
  no `dist/`.

**Tests.** Six new ones in `tests/test_agent_docs.py`. In `tests/test_pd2_las_status.py`,
`test_status_tells_a_rebuilt_pack_from_the_tracked_one` is new and five others follow the new `status`, two
of them under a new name. Two tests required the copies: `test_handoff_and_agents_quote_the_tracked_pack_bytes`
is removed, and `test_pd2_las_has_one_entry_point` no longer asserts that `CLAUDE.md` and `GEMINI.md` equal
`AGENTS.md`.

Each new test fails when the defect is put back, and no other test of the file does
([`mutations.sh`](2026-11-13-agent-entry/mutations.sh), [`after/mutations.txt`](2026-11-13-agent-entry/after/mutations.txt)):

| Put back | Fails |
| --- | --- |
| a `CLAUDE.md`, as a copy or as the one line `@AGENTS.md` | `test_the_instruction_file_is_written_once` |
| the size of a pack in the README; a test count in `tools/README.md` | `test_no_document_quotes_what_status_prints` |
| a path, a make target, a test name that do not exist (one run each) | `test_every_path_target_and_test_named_in_an_agent_doc_exists` |
| 700 bytes more in `AGENTS.md` (budget: 5,000 B) | `test_what_loads_at_start_stays_small` |
| a step added to the workflow that `green` does not run | `test_green_runs_what_the_test_workflow_runs` |
| a build target misspelt in `AGENTS.md`; the row for `status` removed | `test_agents_md_answers_each_question_with_one_command` |

## Checked

| Check | Result |
| --- | --- |
| `make -sC tools/pd2-las green` on `df3fe8c` | 13 of 13 stages; 800 passed, 29 skipped, 2 xfailed; 16 of 16 zips are the tracked bytes after a fresh build ([`after/green.txt`](2026-11-13-agent-entry/after/green.txt)) |
| the `test` workflow on GitHub, `df3fe8c` | every step passed; its notice: "16 of 16 tracked zips are the tracked bytes after a fresh build", on a runner without AVX-512. The pass counts are in its log, which this sandbox could not download |
| `copies.py after` on `19ca55a` | exit 0: 16 of 16 zips, 794 passed, 30 of 30 recorded outputs ([`before/copies-after.txt`](2026-11-13-agent-entry/before/copies-after.txt)) |
| `copies.py after` on the tree that became `62f919e` | 16 of 16 zips; the report on every builder's trace is line for line the one from `19ca55a`; 29 of 30 outputs, the one being `status.py`, changed on purpose. Its entry in `docs/audits/2026-11-12-tool-merge/reference.json` was recorded again (two lines), and `copies.py after recheck` gives 30 of 30 ([`after/copies-after.txt`](2026-11-13-agent-entry/after/copies-after.txt)). Not run again on `df3fe8c`, which changes no builder and nothing `status.py` prints |
| T8 against the whole suite | the slim pack changed, nothing edited: at `19ca55a` the suite fails in `test_handoff_and_agents_quote_the_tracked_pack_bytes` and passes once four documents are edited; at `df3fe8c` it passes as it is |
| `env` on a checkout with one pack changed and one deleted | the deleted one is put back, the changed one stays `changed` |
| the answer key on both commits | identical ([`before/key.json`](2026-11-13-agent-entry/before/key.json), [`after/key.json`](2026-11-13-agent-entry/after/key.json)) |
| four harnesses asked what they load, both commits | the table above |

## Corrected while checking

- **T8, and a test of mine.** The first walk ended T8 with one document test; the task is to make the suite
  pass. The whole suite, run on a changed pack at `62a4104` (its tests are those of `62f919e`), failed:
  `tests/test_pd2_las_status.py` asserted that `status.py slim` prints exactly `packs` and `next`, and while
  a pack is `changed` it also prints `note`. So the suite failed in the one situation where it has to say
  that nothing else needs editing. Fixed in `df3fe8c`. The first record gave T8 as 11,839 → 112 B and the
  total as 113,533 → 33,296 B; the table above replaces it.
- **T8's starting point.** It was a zip with a comment. The pack writer never gives one, so
  `test_that_writer_gives_each_tracked_pack_its_files` failed on both commits, whatever the documents said.
  The pack is now changed in one member and written as the writer writes it (`measure.py change`).
- **T4's baseline** first ended with `status`, whose `sha256_ok` proves nothing about a rebuild (above). The
  step is now `git status --short dist build`, which the pd2-las README pointed to: 3 calls either way,
  22,053 → 20,621 B. The commit message of `1dacfc1` still carries the first total, 114,965 B.
- **`AGENTS.md` said no rebuilt pack needs a document edited.** `lawson_las` does: its builder does not write
  the `.sha256`, and `tools/pd2-port/STATUS.md` quotes its size and sha256 under a test. The line now says so
  and points to "Publish a release" in `tools/pd2-port/README.md` (`62a4104`, `df3fe8c`).

## Not checked, and who has to

- **A model on the eight tasks.** The walk replays the route the documents give. Whether a model takes that
  route, I could not run. [`TASKS.md`](2026-11-13-agent-entry/TASKS.md) is the protocol: a fresh session per
  task on each commit, calls counted from the transcript. For whoever has a harness with an account; a
  different model is better.
- **Cursor (editor and CLI), Copilot in VS Code, the Copilot cloud agent, OpenCode.** Cited, not run. The
  command for each is in the last table of `harness-loaders.md`.
- **Claude Code before 2.1.277**, and the other cases its documentation lists, load nothing now. Not run.
- **Nothing in game.** No pack changed by a byte, so there is nothing new to look at.

## Left as it was

- **The `lawson LAS pack` workflow fails on `main`**, in its `tests` step, as
  `docs/audits/2026-11-12-tool-merge.md` said it would ("Reported, not fixed", 4): its install has no scipy.
  Its steps run by hand give the same four failures on `19ca55a` and on `62a4104`, and none on `df3fe8c`
  once scipy is installed. It runs on `main` and on tags, so it will run, and fail the same way, when this
  branch is merged.
- `tools/pd2-port/STATUS.md` still quotes the size and sha256 of `lawson_las.zip`, pinned by
  `test_the_status_page_matches_the_shipped_pack`. It is the dated page of one port.
- `tools/pd2-port/README.md` (356 lines) and `tools/skyrim-nif/README.md` were not gone through line by
  line. In the first, three places that told an agent to copy computed facts into documents were changed.
- `check_all.py --full` runs the suite twice (the suite, then the skip budget). That is time, not calls.
- `.github/workflows/star-chart.yml` still draws a chart of this fork's stars. No page shows it: the old
  README showed upstream's.
- `"runtime_verified": true` in both Christie packs is a constant their builder writes, and no tracked
  Christie bytes have been in game (`HANDOFF.md`). `status` no longer prints the flag. The packs carry it.

## Run it again

```sh
git worktree add --detach ../wt-before 19ca55a && git worktree add --detach ../wt-after df3fe8c
M=docs/audits/2026-11-13-agent-entry/measure.py           # with tiktoken installed it also counts tokens
python3 $M walk --tree ../wt-before --routes before        # about 8 minutes; it builds packs
python3 $M walk --tree ../wt-after --routes after          # about 10 minutes
python3 $M key --tree ../wt-after                          # the answer key, from the artefacts
bash docs/audits/2026-11-13-agent-entry/mutations.sh       # the table of defects put back

mkdir ../harness && (cd ../harness && npm install @anthropic-ai/claude-code @openai/codex @google/gemini-cli @github/copilot)
bash docs/audits/2026-11-13-agent-entry/probe_harness.sh ../wt-after ../harness/node_modules/.bin
```
