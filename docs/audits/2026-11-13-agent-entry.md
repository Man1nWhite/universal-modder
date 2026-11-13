# What an agent pays to start here, before and after

Goal: an agent that opens this repository cold reaches the right action in fewer calls and fewer tokens, and
no fact is written in two places. This page gives the numbers and says how each was obtained. Everything it
cites is under [`2026-11-13-agent-entry/`](2026-11-13-agent-entry/).

- **Before:** `19ca55a` (main). **After:** `df3fe8c`. `98defe1` and `68272ba` add this page and its evidence,
  nothing else. The commits after `68272ba` fix what the report left open:
  [Fixed after the report](#fixed-after-the-report). Every figure above that section is of `df3fe8c`.
  After those, the owner corrected one sentence of this audit and had what is stale deleted:
  [Deleted on the owner's word](#deleted-on-the-owners-word).
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
are not counted: this work did not touch them. In Codex the list of skills is 9.1 kB on both commits, and
7,108 B of it are the names and descriptions of this repository's twelve skills: more than `AGENTS.md` is now.

| Harness | Before | After | How known |
| --- | --- | --- | --- |
| Claude Code | `CLAUDE.md`: 13,009 B, 3,863 tokens | `AGENTS.md`: 4,682 B, 1,275 tokens | measured on 2.1.323 |
| Codex | `AGENTS.md`: 13,009 B, 3,863 | 4,682 B, 1,275 | measured on 0.168.0 |
| Gemini CLI | `GEMINI.md`: 13,009 B, 3,863 | `GEMINI.md`, which imports `AGENTS.md`: 4,693 B, 1,280 | measured on 0.68.0 |
| Copilot CLI | the three files as one: 13,009 B, 3,863 | `AGENTS.md` and the 11 bytes of `GEMINI.md`: 4,693 B, 1,280 | measured on 1.0.110 |
| Cursor, CLI | `AGENTS.md` and `CLAUDE.md`: 26,018 B, 7,726 | 4,682 B, 1,275 | its documentation; not run |
| Copilot in VS Code | `AGENTS.md` and `CLAUDE.md`: 26,018 B, 7,726 | 4,682 B, 1,275 | its documentation; not run |
| Cursor, editor; OpenCode | `AGENTS.md`: 13,009 B, 3,863 | 4,682 B, 1,275 | documentation and source; not run |

- "Measured" is which files the harness itself reported to `probe_harness.sh`, with no account, in an empty
  home directory and with nothing of the caller's environment but `PATH`
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

- Of 671 non-blank lines removed, 506 were dropped and 165 moved; 226 of the dropped lines are the two
  copies. Each is in [`ledger.tsv`](2026-11-13-agent-entry/ledger.tsv) with what became of it, and
  `measure.py ledger` stops with an error when a removed line has no entry. The file is the ledger of the
  head: with the fixes it has 982 lines, 664 dropped and 318 moved.
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
| the `test` workflow on GitHub, `df3fe8c` and `98defe1` | every step passed on both; the notice of each: "16 of 16 tracked zips are the tracked bytes after a fresh build", the first on a runner without AVX-512 (EPYC 7763), the second on one with it (EPYC 9V45). The pass counts are in the logs, which this sandbox could not download |
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

- **The probe was not as clean as its header said.** It ran each harness's `--version` in the real home
  directory, where Gemini CLI and Codex left temporary files, and it passed the caller's environment on: in
  this sandbox, with a GitHub token in it. Every call now runs under `env -i` in an empty home. The four
  harnesses answer as they did, so "no account" is now tested for Copilot CLI too.

## Not checked, and who has to

- **A model on the eight tasks.** The walk replays the route the documents give. Whether a model takes that
  route, I could not run. [`TASKS.md`](2026-11-13-agent-entry/TASKS.md) is the protocol: a fresh session per
  task on each commit, calls counted from the transcript. For whoever has a harness with an account; a
  different model is better.
- **Cursor (editor and CLI), Copilot in VS Code, the Copilot cloud agent, OpenCode.** Cited, not run. The
  command for each is in the last table of `harness-loaders.md`.
- **Claude Code before 2.1.277**, and the other cases its documentation lists, load nothing now. Not run.
- **Nothing in game.** Between `19ca55a` and `df3fe8c` no pack changed by a byte. The fixes rebuilt the two
  Christie packs with one line of `BUILD_INFO.json` changed in each; nobody has looked at them in game.

## Left as it was

- **The skills.** Twelve skills in three identical trees (`skills/`, `.claude/skills/`, `.agents/skills/`),
  the layout upstream has. Codex puts their names and descriptions in every session: 7,108 B, where the block
  that holds `AGENTS.md` is 4,763 B ([`after/harness.txt`](2026-11-13-agent-entry/after/harness.txt)). The
  other harnesses were not asked. This work was not to change them.
- The report listed six more points here: the `lawson LAS pack` workflow, `tools/pd2-port/STATUS.md`, two
  READMEs, the suite run twice by `green`, the star chart, and `"runtime_verified": true` in the Christie
  packs. They are fixed: next section.

## Fixed after the report

The owner asked for the open points to be fixed, and decided four of them: a full pass on
`tools/pd2-port/STATUS.md`, the star chart removed, `"runtime_verified": false` with both Christie packs
rebuilt, and the merge with upstream kept out of this branch.

This section is of `2dc7c27`. It speaks of a release, of the `star-chart` branch and of
`tools/skyrim-nif/`: all three are gone since, and what it said about redistribution was wrong. The next
section has both.

| Open point | Fix | How it was checked |
| --- | --- | --- |
| The `lawson LAS pack` workflow fails for want of scipy | `92c9758`: its install line has scipy. `test_a_workflow_that_runs_the_suite_installs_what_the_test_workflow_installs` fails when a workflow that runs the suite installs less than `test.yml` does | started by hand on this branch, the workflow passes: run 43394621347 on `92c9758`, run 43405121829 on `48b26a2`. Its last step, the publish, runs on a tag only and was skipped both times. With `tests` passing, that step can be reached again |
| `"runtime_verified": true` in both Christie packs | `292c5cf`: the builder writes `false`, and both packs are rebuilt | one line of `BUILD_INFO.json` differs in each pack; the names, the order and the zip fields of every member are those of the old zips ([`fixes/christie-packs.txt`](2026-11-13-agent-entry/fixes/christie-packs.txt)); the other 12 packs are untouched. `HANDOFF.md` and `DECISIONS.md` (D31) record it |
| `star-chart.yml` draws a chart no page shows | `38df6d9`: the workflow and its script are removed | no file names either; one journal entry names the branch. The `star-chart` branch on GitHub, where the workflow pushed its chart, is still there |
| `green` runs the suite twice | `d605e4f`: the skip budget judges the report that the suite stage wrote | the verdict from the report is the one from a run of its own: 29 skips across 9 reasons, 2 expected failures. T3 takes 293 s where it took 431 s |
| `STATUS.md` quotes the size and sha256 of `lawson_las`; two READMEs were not gone through | `15c9e7d`, `48b26a2`, `b47635d` | below |
| Two more merge conflicts with upstream | not done: a change of its own, by the owner's choice | the six files are named under "What changed" |

**What the pass on the documents found.**

- **The tracked `lawson_las` is not the released pack.** Release `lawson-las-v2` serves the build of
  `282703f`. Ten commits after that tag rebuilt the tracked pack, all stamped with the same version, and none
  was released. `tools/pd2-port/README.md` said "the tracked `dist/lawson_las.zip` is therefore exactly what
  the release serves" and "build it yourself — the bytes are identical"; `STATUS.md` gave the tracked size
  and sha256 in one table with the release, and a test kept those two figures current. This audit left both
  files as they were, so the claim stood at `df3fe8c`. Found by reading the release (`gh release view`,
  `git log 282703f..HEAD -- dist/lawson_las.zip.sha256`), not by a test.
- **`tools/pd2-port/STATUS.md`** is now the dated record of that port: 244 → 101 lines, 14,456 → 7,530 B.
  It says what the release serves and that the tracked pack is another one, that nothing records the pack in
  game, what was found and settled, which transfers failed, and what the page and the README used to claim.
  It quotes no tracked size or sha256 and no count ([`fixes/facts.tsv`](2026-11-13-agent-entry/fixes/facts.tsv): no document
  quotes one now). It also said "the v1 release stays up": there is a tag and no release.
- **The test that kept the figures current is replaced.**
  `test_the_status_page_says_whether_the_release_serves_the_tracked_pack` compares the newest release notes
  with the tracked `.sha256`. While they differ, `STATUS.md` and the list of open work in
  `tools/pd2-las/README.md` have to say so; once they agree, both have to stop saying it.
- **`tools/pd2-port/README.md`**: 22,109 → 21,810 B. It quotes no version, release number, pinned version
  or count of mutations, and sends the installer to `dist/lawson_las.zip`.
- **A release tag publishes two packs.** The README said the workflow "uploads `lawson_las.zip` +
  `lawson_las.zip.sha256`". Since `637b7a9` its publish step uploads the tracked `dist/Miranda_LAS.zip` and
  its `.sha256` as well, and the artifact of every push to `main` holds four packs. The README says so now.
  `tools/pd2-las/README.md` lists the public release of the Miranda packs as blocked.
- **`tools/skyrim-nif/README.md`**: 5,042 → 4,981 B. Its two commands under "Use" stop at once, because the
  archives they read were removed with the port (`inventory.py` exits 2, `crosscheck.py` exits 1); the page
  says so and keeps the example that needs no archive. It counted "15 mapped joints, 22 helper folds" in
  `skeleton_map.json`, which has 54 and 23 entries and had them when the line was written. The result of the
  nifly cross-check stood twice.
- **`tools/pd2-las/README.md`**, +107 B: its list of open work names the release, because that list is where
  T6 is answered.
- **`AGENTS.md`**: 4,682 → 4,632 B. The exception for `lawson_las` is one clause now.

**The eight tasks on `b47635d`**, the same walk ([`fixes/walk.json`](2026-11-13-agent-entry/fixes/walk.json),
[`fixes/start.json`](2026-11-13-agent-entry/fixes/start.json), [`fixes/key.json`](2026-11-13-agent-entry/fixes/key.json)).
The commits after `b47635d` change `tools/pd2-port/README.md`, `tools/pd2-port/STATUS.md`, one test and this
page with its evidence; no route of the walk reads any of them.

| | `19ca55a` | `df3fe8c` | `b47635d` |
| --- | --- | --- | --- |
| Calls | 26 | 7 | 7 |
| Bytes | 114,895 | 34,658 | 35,437 |
| Tokens | 33,589 | 10,042 | 10,275 |
| Seconds for the eight tasks | 455 | 584 | 448 |
| `AGENTS.md`, loaded at start | 13,009 B, 3,863 tokens | 4,682 B, 1,275 | 4,632 B, 1,260 |
| Tracked sizes and hashes quoted in documents | 14 sizes, 14 hashes | 1 size, 1 hash | none |

- The fixes cost 779 B: `HANDOFF.md` records the rebuild of the Christie packs (T5, +675 B), the list of
  open work names the release (T6, +107 B), and two commands print 3 B less.
- T3 takes 293 s, not 431 s, so the eight tasks take about as long as before the change, where at `df3fe8c`
  they took 129 s more.
- T6's key has a sixth item since `b47635d`: the release. The walk reaches 6 of 6. The walks stored in
  `before/` and `after/` predate the item, and no document of those commits says it.
- The answer key differs from the one of `df3fe8c` in the two Christie packs only: their sizes and sha256,
  `sha256_tracked` of the slim pack, and `no_in_game_flag`, which lists 14 packs where it listed 12.
- The tokens were counted with the same encoding file (sha256 `446a9538…`, the one tiktoken expects):
  `HANDOFF.md` of `df3fe8c` gives 4,582 again.

**Tests of the fixes.** Each fails when its defect is put back, on `b47635d`
([`mutations.sh`](2026-11-13-agent-entry/mutations.sh), [`fixes/mutations.txt`](2026-11-13-agent-entry/fixes/mutations.txt)); the eleven cases
of the table under "What changed" still fail theirs.

| Put back | Fails |
| --- | --- |
| scipy taken out of what the lawson workflow installs | `test_a_workflow_that_runs_the_suite_installs_what_the_test_workflow_installs` |
| `STATUS.md` says the release serves the tracked pack; release notes for a v3 with the tracked sha256 and `STATUS.md` not touched; the release taken out of the open work while it is behind; a release that serves the tracked pack, still listed as open work | `test_the_status_page_says_whether_the_release_serves_the_tracked_pack` |
| the tracked size of `lawson_las`, its sha256, or the audit's result in `STATUS.md`; a count of mutations in `tools/pd2-port/README.md`; a count of checks in `tools/skyrim-nif/README.md` | `test_no_document_quotes_what_status_prints` |
| a script that does not exist, in `tools/skyrim-nif/README.md` | `test_every_path_target_and_test_named_in_an_agent_doc_exists` |

`tests/test_skip_budget.py` is new with `d605e4f` (four tests), `tests/test_christie_las.py` asserts the
flag, and `test_status_tells_a_rebuilt_pack_from_the_tracked_one` now runs in a checkout of its own: it used
to skip while a pack was rebuilt and not committed, and that skip had no budget, so `green` would have failed
in the one state where `status` names it as the next command.

**Checked.**

| Check | Result |
| --- | --- |
| `make -sC tools/pd2-las green` on the tree that became `15c9e7d` | 13 of 13 stages; 805 passed, 29 skipped, 2 xfailed; 16 of 16 zips are the tracked bytes after a fresh build ([`fixes/green.txt`](2026-11-13-agent-entry/fixes/green.txt)) |
| the same with both Christie packs rebuilt and not committed | 13 of 13 stages |
| the `test` workflow on GitHub | every step passed on each of the six pushes from `92c9758` to `b47635d` (`38df6d9` went up with `d605e4f`); the notice each time: "16 of 16 tracked zips are the tracked bytes after a fresh build". Since the Christie rebuild, four times on a runner without AVX-512 (EPYC 7763) and once with it (Xeon Platinum 8573C, `15c9e7d`) |
| `copies.py after` on the tree that became `48b26a2` | 16 of 16 zips; 805 passed; the report on every builder's trace is line for line the one from `19ca55a`, with no function that returns something else; 29 of 30 outputs, the one being `status.py`, which prints the rebuilt packs' sizes and hashes. Its entry in `docs/audits/2026-11-12-tool-merge/reference.json` was recorded again: 30 of 30 ([`fixes/copies-after.txt`](2026-11-13-agent-entry/fixes/copies-after.txt)) |

**Not checked.**

- The publish step of the `lawson LAS pack` workflow. It runs on a tag, and no tag was pushed.
- The two rebuilt Christie packs, or any other pack, in game.
- `probe_harness.sh` was not run again. Of what a harness loads at start, the fixes changed 50 B of
  `AGENTS.md`; the sizes in the table are those of the files.
- No model session has run `TASKS.md` on any commit.

**Left, and whose it is.**

- **A release of `lawson_las`.** The gap closes with a release that has a version of its own, or stays as it
  is now, written down. The repository's `README.md` says of every source that it is not cleared for
  redistribution, and a `lawson-las-v*` tag would publish `Miranda_LAS.zip` too, which no release has
  carried. The owner's decision; nothing was tagged, and the workflow's publish step was not changed.
  *Since: the sentence in `README.md` was this audit's and was wrong, and the stale release is deleted.
  Next section.*
- **The `star-chart` branch on GitHub.** Nothing writes to it any more. The owner's to delete.
  *Since: deleted. "Nothing writes to it" was wrong: the workflow is on `main` until this branch is merged,
  and redrew the branch on every push to `main`. It is switched off now.*
- **The merge with upstream:** six conflicts, as above.
  *Since: it was seven by then. Deleting the star chart workflow in `38df6d9` added one, upstream having
  changed that file, and this line did not count it.*
- **`copies.py after` fails after any pack is rebuilt on purpose**, until `outputs.status` is recorded
  again: `status.py` prints each pack's size and sha256, and the reference holds a checksum of what it
  printed.
- **`tools/skyrim-nif/skeleton_map.json` says of itself "nothing consumes this file yet".**
  `tools/pd2-las/build_skyrim_outfit.py` reads it. A data file of a cancelled route; not edited.
  *Since: deleted with that route.*

## Deleted on the owner's word

On the report of the fixes the owner wrote: "Change README - no mod has that resctriction" and "Delete
stale things". Which things was asked in three questions and answered: all sixteen branches; both tags and
the pre-release with its tag; everything only the cancelled Skyrim outfit uses. The decisions are D32 and
D33 in [`DECISIONS.md`](../pd2-las/DECISIONS.md).

**A sentence of this audit was wrong.** `README.md` said: "The sources are fan rips, so nothing here is
cleared for redistribution." This audit wrote it (`62f919e`) from D4, and D4 had been put together on
2026-11-11 from an audit of 2026-10-18 that listed clearance as "open". It was never the owner's word, and
the section above then gave it as a reason to hesitate over a release.

- `018fc07` takes it out of `README.md` and out of what repeated it: "Blocked: public release" and "Do not
  publish or redistribute the packs or their sources" in `tools/pd2-las/README.md`, "not cleared for
  redistribution" in `tools/pd2-port/README.md`, the release gate of `docs/pd2-las/in-game-checklist.md`,
  the note on asset rights in `docs/pd2-las/CHEST-VARIANT.md`, and the gate in the knowledge note on LAS
  outfits. D4 is marked superseded by D32.
- **Not changed, and it is the owner's to decide:** `CREDITS.txt` inside the tracked `lawson_las.zip` says
  "this is an unlicensed, non-commercial fan derivative and no redistribution permission is claimed", and a
  comment in its builder, `tools/pd2-port/build_las_pack.py`, says "not cleared for commercial
  redistribution". Changing the text is a rebuild of that pack: other bytes, another sha256. The rules under
  "What you ship" in `AGENTS.md` and in the skills are upstream's, about game files an agent extracts; the
  audits of 2026-10-18 are records of their day.

**Two more sentences were wrong**, both found while checking this section.

- From `cf56805` through `b3b6966`, `tools/pd2-port/STATUS.md` said of the tag `lawson-las-v1`: "never a
  release". There had been one. The release workflow ran on that tag six times on 2026-10-19, and its step
  "publish to the GitHub release" succeeded in five (`gh run list --workflow lawson-las.yml`; the steps of
  run 39214619314); the journal of that day says so too. On 2026-11-13 the tag had no release, and nothing
  in the repository records who took it down or when. `STATUS.md` says that now.
- The section above counts six conflicts in a merge with upstream. It was seven from `38df6d9` on: that
  commit deleted the star chart workflow, which upstream has changed since the fork. Tried at `292c5cf`
  (six), `2dc7c27` (seven) and `b3b6966` (seven).

**What was deleted.** Every tip and every path is written down, so each line can be undone.

| Deleted | Why it was stale | How to get it back |
| --- | --- | --- |
| 15 `arena/*` branches on GitHub | each merged by a pull request (#16 to #30) and wholly in `main` | the table of tips in `tools/pd2-port/MODLOG.md`; `git push origin <tip>:refs/heads/<name>` |
| the `star-chart` branch; the `star chart` workflow switched off | the workflow and its script left this branch in `38df6d9`; no page showed this fork's chart (the README of `main` shows upstream's) | tip `556a41912a3d`; `gh workflow enable star-chart.yml` |
| the pre-release `lawson-las-v2` with its tag; the tags `lawson-las-v1`, `lawson-clover-v1` | it served the build of `282703f`, and ten commits rebuilt the tracked pack after it, under the same version, 0.1.2; GitHub counted 0 downloads of each asset; neither older tag had a release that day | the three commits are in `main`; the zip is `git show 282703f:dist/lawson_las.zip` |
| `tools/pd2-port/releases/` (2 files) | the page bodies of releases that do not exist | `git show 19ca55a:tools/pd2-port/releases/lawson-las-v2.md` |
| the code of the cancelled Skyrim outfit: 29 files, 8,302 lines, and the parts of six more modules that only it used | its archive was removed on 2026-11-05 (`eb2a9c5`): the builder ended with exit 2, and 21 of the suite's 29 skips were its tests | `git show 19ca55a:<path>` |
| `docs/audits/2026-11-09-neck-arm/`, 5 renders | the page that showed four of them, a repair plan, was deleted on 2026-11-10 (`0a76215`); no file named any of the five | `git show 19ca55a:docs/audits/2026-11-09-neck-arm/arm_three_view.png` |

GitHub has `main` and this branch now, no tag and no release. The next release of `lawson_las` is numbered
3: a clone made earlier still has the tags of 1 and 2, and a test rejects notes under either number.

**What went with the Skyrim outfit** (`f6264ae`; the entry of the day in `tools/pd2-las/MODLOG.md` lists
it):

- Whole files: `tools/skyrim-nif/` (9), `docs/skyrim-nif/` (5), six modules in `tools/pd2-las/`, nine test
  files.
- `build_models.py`, 3,543 → 1,784 lines: 39 functions that only that builder called, or nothing called,
  and two pieces inside functions that stay, both keyed on the outfit's material names. `las_outfit_pack.py`,
  528 → 380: the outfit's own registration and its `write_pack`. The commands of `preview_textured.py` and
  `pose_preview.py`, which read that outfit's build or its texture names; the modules stay, because
  `glove_check.py` and `pose_zoom.py` render with them.
- **Tests, 836 ids → 705** ([`deleted/tests.txt`](2026-11-13-agent-entry/deleted/tests.txt)): 156 went, 25
  are new. Of the 156, 21 could only skip. What the outfit's test files asserted about functions that
  stay was kept and moved: `tests/test_las_outfit_pack.py` (13 tests of the writer of the registration files
  of the four Christie and Miranda packs), and seven tests of `boundary_loops`, `extract_bones`, the render
  atoms and the sleeve stretch. `tests/test_glove_adapter.py` and `tests/test_glove_behavior_lua.py` tested
  the glove adapter of the cancelled outfit, and their pack-level tests waited for a zip that was not
  coming; they now test `Christie_LAS_Slim`, the one pack that ships the adapter. `b3b6966` adds two
  tests: 707.
- The suite skips 8 tests now, for four reasons that are about the machine. The skip budget lost its four
  reasons about the outfit, and `test_no_budget_is_kept_for_a_reason_nothing_skips_with` fails when a
  budget outlives its tests again (`b3b6966`).

**Checked.**

| Check | Result |
| --- | --- |
| `make -sC tools/pd2-las green` on the tree that became `f6264ae` | 13 of 13 stages; 696 passed, 8 skipped, 2 xfailed; 16 of 16 zips are the tracked bytes after a fresh build ([`deleted/green.txt`](2026-11-13-agent-entry/deleted/green.txt)). No tracked pack changed |
| `copies.py after` on the same tree | no builder function returns something else; 26 of 26 recorded tools give what they gave ([`deleted/copies-after.txt`](2026-11-13-agent-entry/deleted/copies-after.txt)). The four entries that recorded the outfit's tools are out of the reference; three of them recorded a failure ([the tool-merge audit](2026-11-12-tool-merge.md), last section) |
| `pose_zoom.py` and `glove_check.py` on `christie.model` and `miranda.model`, before the edits to the two modules they render with and on `b3b6966` | the same four PNGs, by sha256 (`38ee41e7…`, `13147db1…`, `494c9649…`, `5b85e89e…`) |
| `tests/test_glove_behavior_lua.py`, which runs the hook's Lua through `lupa` | 10 passed in an environment with lupa 2.8, set up aside; its runtime there is Lua 5.5, and the game's is 5.1. The pinned environment and CI have no `lupa`: there the file skips, as it did before |
| the eight tasks on `b3b6966` ([`deleted/walk.json`](2026-11-13-agent-entry/deleted/walk.json)) | 7 calls, 34,887 B, 10,140 tokens, 423 s; every answer reached. T6 reads 387 B less and has five items again: there is no release to be behind. T8 prints 161 B less: `pytest -q` prints a character for each test, and there are fewer. What loads at start is unchanged: 4,632 B |
| sizes and hashes quoted in documents ([`deleted/facts.tsv`](2026-11-13-agent-entry/deleted/facts.tsv)) | none |
| the ledger against `19ca55a` ([`ledger.tsv`](2026-11-13-agent-entry/ledger.tsv)) | 1,053 removed lines, each with where it went: 739 dropped, 314 moved |
| defects put back on `b3b6966` ([`deleted/mutations.txt`](2026-11-13-agent-entry/deleted/mutations.txt)) | 30 cases: 29 fail their test, and the one that is a correct release passes. Six are new: a README row for the deleted tools, a stale skip budget, a glove adapter enabled with a boolean, a unit path without its file stem, a texture pair with its suffix, default sleeve targets for the outfit's materials. Cases 9e and 10 used to write into `tools/skyrim-nif/README.md` and write into two other READMEs now |
| the `test` workflow on GitHub | every step passed on `cf56805`, `f6264ae` and `b3b6966`; "16 of 16 tracked zips are the tracked bytes after a fresh build" each time, twice without AVX-512 (EPYC 7763) and once with it (EPYC 9V45) |
| the `lawson LAS pack` workflow, started by hand on `b3b6966` (run 43423900084) | the pack it builds is the tracked one and its suite passes; the publish step was skipped, as on any run that is not a tag |

**Not checked.**

- Nothing in game, as before. No pack changed.
- `copies.py compare` was not run again. It works in a worktree of `26fce3e`, where the deleted files are.
- That nobody else needs a deleted branch or tag: a fork or a clone of this repository keeps its own.
- The ten functions below were found by name. None was run, and none was removed.

**Found and left, with the reason.**

- **Ten functions in live modules that nothing calls**, none of them the outfit's: `chest_extent` in
  `bust_variant.py`; `attenuate_dxt5_alpha_by_block_mask`, `rgba_to_bgra_dds` and `set_dxt5_constant_alpha`
  in `dds_encode.py`; `mat_apply_vec` and `mat_from_pos_rot_rows` in `diesel_model.py`; `_axis_to_camera` in
  `render_mesh_skeleton.py`; `repair_dxt5_texture` and `_encode_block` in `tools/pd2-port/dds.py`, with
  `_rgb565`, which only `_encode_block` calls. No file under `tools/`, `tests/` or `um/` names one of them
  outside its own module; a call built at run time would escape that search. They came with the Miranda,
  Christie and Lawson work between 2026-10-18 and 2026-11-06, so no answer of the owner covers them.
- **`docs/pd2-las/renders/`, 101 PNGs, is not stale.** No file has the exact name of 79 of them.
  `CHRISTIE.md` names them by pattern, `render_mesh_skeleton.py` and `elbow_before_after.py` write them, and
  `test_render_cli_writes_every_file_the_docs_name` fails when the page names a render the tool cannot make.
- **The label `glove=2B` that `glove_check.py` draws on its sheet.** The stand-in has been a capsule since
  before this change. The label is in the PNG that `copies.py` holds the tool to, so it was left.
- **The merge with upstream** (`3c4ac6c`, as fetched earlier): seven conflicts now, in
  `.github/workflows/star-chart.yml` (deleted here, changed there), `.github/workflows/test.yml`,
  `AGENTS.md`, `README.md`, `knowledge/INDEX.md`, `knowledge/index.json` and `um/scan.py`. Tried in a
  worktree and aborted. Still a change of its own.
- **`CREDITS.txt` in `lawson_las.zip`:** above.

## Run it again

```sh
# for the figures of "Fixed after the report", use b47635d in place of df3fe8c; for the last section, b3b6966
git worktree add --detach ../wt-before 19ca55a && git worktree add --detach ../wt-after df3fe8c
M=docs/audits/2026-11-13-agent-entry/measure.py           # with tiktoken installed it also counts tokens
python3 $M walk --tree ../wt-before --routes before        # about 8 minutes; it builds packs
python3 $M walk --tree ../wt-after --routes after          # about 10 minutes
python3 $M key --tree ../wt-after                          # the answer key, from the artefacts
bash docs/audits/2026-11-13-agent-entry/mutations.sh       # the table of defects put back

mkdir ../harness && (cd ../harness && npm install @anthropic-ai/claude-code @openai/codex @google/gemini-cli @github/copilot)
bash docs/audits/2026-11-13-agent-entry/probe_harness.sh ../wt-after ../harness/node_modules/.bin
```
