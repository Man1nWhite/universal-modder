# What an agent pays to start here, before and after

Goal: an agent that opens this repository cold reaches the right action in fewer calls and fewer tokens, and
no fact is written in two places. This page gives the numbers and says how each was obtained. Everything it
cites is under [`2026-11-13-agent-entry/`](2026-11-13-agent-entry/).

- Before: `19ca55a` (main). After: `62f919e`. The baseline was committed first, as `1dacfc1`, before any
  document, test or tool was touched.
- One line of `AGENTS.md` was corrected after `62f919e` was measured: it said that no rebuilt pack needs a
  document edited, and `lawson_las` does (`tools/pd2-port/STATUS.md`, below). The file is 4,630 B (1256 tokens) with it;
  every figure on this page is the one measured on `62f919e`, 4,528 B (1,229 tokens).
- A call is one shell command or one file read. Bytes are those of the file or of the command's output.
  Tokens are tiktoken's `o200k_base`.

## Eight tasks, replayed on both commits

`measure.py walk` starts with `AGENTS.md` in context and takes a step only when text already read points to
it; it fails when the pointer is not there. Each step is run for real in a scratch worktree of the commit.
It is the shortest route the documents lead to, not a session of a model: see "Not checked" below.

| Task | Calls | Bytes | Tokens | Answer reached |
| --- | --- | --- | --- | --- |
| T1 set up after a sandbox restart | 3 → 1 | 1,605 → 1,944 | 619 → 758 | yes → yes |
| T2 state of all 14 packs | 4 → 1 | 3,030 → 1,684 | 1,138 → 680 | yes → yes |
| T3 is everything green | 7 → 1 | 14,649 → 1,407 | 3,972 → 432 | 4 of 6 checks → 6 of 6 |
| T4 rebuild one pack and prove its bytes | 3 → 1 | 20,621 → 161 | 6,606 → 64 | yes → yes |
| T5 was the pack seen in game, and were those the tracked bytes | 2 → 1 | 30,527 → 16,143 | 9,011 → 4,582 | yes → yes |
| T6 what is open | 3 → 1 | 31,262 → 11,845 | 8,720 → 3,266 | 4 of 5 items → 5 of 5 |
| T7 which command rebuilds `Geralt_over_Rust` | 0 → 0 | 0 → 0 | 0 → 0 | yes → yes |
| T8 a pack changed on purpose: make the suite pass again | 4 → 1 | 11,839 → 112 | 3,279 → 20 | yes → yes |
| **Total** | **26 → 7** | **113,533 → 33,296** | **33,345 → 9,802** | |

What the table hides:

- **T1 costs more bytes than before** (339 B, 139 tokens): one call instead of three, but `env` now ends
  with the state of all 14 packs.
- **T3 takes longer**: 252 s → 382 s. `green` runs what the six commands ran and also the auditor's
  self-test and the skip budget, which runs the suite a second time.
- Before, two of the 26 calls failed in this sandbox: `uv run --with pytest pytest -q tests` (there is no
  `uv`: exit 127) and `bin/um kb check --index` (no PyYAML outside the venv: exit 1). Both were what
  `AGENTS.md` told an agent to run. Two calls were ones no document led to; after, one is (the test run that
  confirms T8 needs no edit).
- Before, T3 never reached `pyflakes` or the `--help` of the `um` groups: no document named them, only the
  workflow. T6 found nothing about the nine head packs.
- T4's first baseline ended with `status`, whose `sha256_ok` compared the zip with a sidecar the builder had
  just rewritten. That proves nothing about a rebuild. The step was replaced by `git status --short dist
  build`, which the README pointed to, and T4 measured again: 3 calls either way, 22,053 → 20,621 B. The
  commit message of `1dacfc1` still carries the first total (114,965 B).

Files: [`before/walk.json`](2026-11-13-agent-entry/before/walk.json),
[`after/walk.json`](2026-11-13-agent-entry/after/walk.json).

## What loads at the start of a session

Per harness, the instruction files it reads in a clone
([`harness-loaders.md`](2026-11-13-agent-entry/harness-loaders.md) has the source for every row).
Skills lists and tool descriptions also load at start and are not counted: they are outside the scope set.

| Harness | Before | After | How known |
| --- | --- | --- | --- |
| Claude Code | `CLAUDE.md`: 13,009 B, 3,863 tokens | `AGENTS.md`: 4,528 B, 1,229 tokens | measured on 2.1.323 |
| Codex | `AGENTS.md`: 13,009 B, 3,863 | 4,528 B, 1,229 | measured on 0.168.0 |
| Gemini CLI | `GEMINI.md`: 13,009 B, 3,863 | `GEMINI.md` importing `AGENTS.md`: 4,539 B, 1,234 | measured on 0.68.0 |
| Copilot CLI | the three files as one: 13,009 B, 3,863 | `AGENTS.md` and the 11 bytes of `GEMINI.md`: 4,539 B, 1,234 | measured on 1.0.110 |
| Cursor, CLI | `AGENTS.md` and `CLAUDE.md`: 26,018 B, 7,726 | 4,528 B, 1,229 | its documentation; not run |
| Copilot in VS Code | `AGENTS.md` and `CLAUDE.md`: 26,018 B, 7,726 | 4,528 B, 1,229 | its documentation; not run |
| Cursor, editor; OpenCode | `AGENTS.md`: 13,009 B, 3,863 | 4,528 B, 1,229 | documentation and source; not run |

The two 26,018 figures assume the harness does not drop the second, identical file. Neither's documentation
says it does.

## What changed

**Commands** (`tools/pd2-las/Makefile`; each merge is one the baseline shows saving calls):

| Question | Before | After |
| --- | --- | --- |
| Set up | `git checkout -- dist build node_modules`, `make … env`, `status.py` | `make -sC tools/pd2-las env`: restores only tracked files that are missing, builds the venv, unpacks the templates, prints the state |
| State of all 14 packs | `status` (4 packs), `check_all.py` (1), `build_joy_head_mods.py` (rebuilds 9 to find out), `git status` | `make -sC tools/pd2-las status`: 14 packs, 1,684 B |
| Everything green | six commands, two of them named by no document | `make -sC tools/pd2-las green` (`check_all.py --full`, 13 stages) |
| Rebuild and prove | read the README, build (9,023 B of builder output), `git status` | `make -sC tools/pd2-las <target>`: 161 B; the builder's output goes to `build/pd2-las/<target>.log` |

`status` now says `"is": "tracked"` only when the zip is what the commit holds. Targets `lawson` and `heads`
are new, so every pack has one. No entry point that CI or a test calls was removed; `status.PACKS` became
`status.TARGETS`, with the one test that read it.

**Documents.** `AGENTS.md` 13,009 → 4,528 B. `CLAUDE.md` deleted, `GEMINI.md` is `@AGENTS.md`
(why: `harness-loaders.md`, last section). `README.md` 25,636 → 1,921 B. `HANDOFF.md` 18,929 → 16,143 B.
Of 671 non-blank lines removed from the eight documents, 506 were dropped and 165 moved; each is in
[`ledger.tsv`](2026-11-13-agent-entry/ledger.tsv) with what became of it, and `measure.py ledger` fails if a
removed line has no entry.

Sizes and hashes quoted in documents: 14 sizes in four documents and 14 hashes in one → none, apart from
`tools/pd2-port/STATUS.md` (see below). [`before/facts.tsv`](2026-11-13-agent-entry/before/facts.tsv),
[`after/facts.tsv`](2026-11-13-agent-entry/after/facts.tsv).

**Where two documents disagreed, which was wrong:**

- The README said the four L4D2 head packs "were tested in game on 2026-11-05". `HANDOFF.md` says the
  tracked zips are later rebuilds, and git agrees: the tracked sha256 of `Miranda_L4D2_over_Joy` changed in
  three commits after that day. The README was wrong.
- `tools/README.md` said "No code to deduplicate" and "234 tests" (measured 2026-10-19).
  `docs/audits/2026-11-12-tool-merge.md` found jobs done in more than one place and merged some; the suite
  passes 800 tests. `tools/README.md` was wrong.
- `AGENTS.md` and the pd2-las README offered `sha256_ok` as the check after a build. Every builder writes its
  own `.sha256`, so it could not fail. Both were wrong; `"is"` replaces it.

**Tests** (`tests/test_agent_docs.py`, and three rewritten in `tests/test_pd2_las_status.py`). The two tests
that required the copies are gone. Each new test was made to fail by putting the defect back:

| Put back | Fails |
| --- | --- |
| a `CLAUDE.md` copy | `test_the_instruction_file_is_written_once` |
| a pack's size in the README | `test_no_document_quotes_what_status_prints` |
| a path, a make target and a test name that do not exist | `test_every_path_target_and_test_named_in_an_agent_doc_exists` |
| 700 bytes of filler in `AGENTS.md` | `test_what_loads_at_start_stays_small` (budget: 5,000 B) |
| a new `run:` step in the workflow | `test_green_runs_what_the_test_workflow_runs` |
| a build target misspelt in `AGENTS.md` | `test_agents_md_answers_each_question_with_one_command` |

The fifth did not fail at first: the test read the workflow with a regular expression that skipped two
steps. It reads it with PyYAML now.

## Checked

| Check | Result |
| --- | --- |
| `make -sC tools/pd2-las green`, changed tree | 13 of 13 stages; 800 passed, 29 skipped, 2 xfailed; 16 of 16 zips ([`after/green.txt`](2026-11-13-agent-entry/after/green.txt)) |
| `copies.py after`, `19ca55a` | exit 0: 16 of 16 zips, 794 passed, 30 of 30 outputs ([`before/copies-after.txt`](2026-11-13-agent-entry/before/copies-after.txt)) |
| `copies.py after`, changed tree | 16 of 16 zips; every builder's trace line identical to the run on `19ca55a`; 29 of 30 outputs, the one being `status.py`, changed on purpose ([`after/copies-after.txt`](2026-11-13-agent-entry/after/copies-after.txt)). Its entry in `docs/audits/2026-11-12-tool-merge/reference.json` was recorded again (two lines); `copies.py after recheck` then gives 30 of 30 |
| answer key on both commits | identical ([`before/key.json`](2026-11-13-agent-entry/before/key.json), [`after/key.json`](2026-11-13-agent-entry/after/key.json)) |
| four harnesses asked what they load, both commits | [`before/harness.txt`](2026-11-13-agent-entry/before/harness.txt), [`after/harness.txt`](2026-11-13-agent-entry/after/harness.txt) |
| the `test` workflow on GitHub | on `62f919e`: every step passed. The run on the commit that adds this page is reported where this work is handed over |

## Not checked, and who has to

- **A model on the eight tasks.** The walk is a replay of the route the documents give. Whether a model
  takes that route, I could not run. [`TASKS.md`](2026-11-13-agent-entry/TASKS.md) is the protocol: a fresh
  session per task on each commit, calls counted from the transcript. For whoever has a harness with an
  account; a different model is better.
- **Cursor (editor and CLI), Copilot in VS Code, the Copilot cloud agent, OpenCode.** Cited, not run. The
  command for each is in the last table of `harness-loaders.md`.
- **Claude Code before 2.1.277**, and the other cases its documentation lists, load nothing now. Not run.
- **The `lawson LAS pack` workflow** runs on tags and on main, not on this branch. It runs the suite with
  its own install.
- **Nothing in game.** No pack changed by a byte, so there is nothing new to look at.

## Left as it was

- `tools/pd2-port/README.md` (356 lines) and `tools/skyrim-nif/README.md` (99) were not put through the cut
  rule line by line. In the first, three places that told an agent to copy computed facts into documents
  were changed.
- `tools/pd2-port/STATUS.md` still quotes the size and sha256 of `lawson_las.zip`, pinned by
  `test_the_status_page_matches_the_shipped_pack`. It is outside the scope set.
- `check_all.py --full` runs the suite twice (the suite, then the skip budget). That is time, not calls.
- `.github/workflows/star-chart.yml` still draws a chart that the README no longer shows.
- `"runtime_verified": true` in both Christie packs is a constant their builder writes, and no tracked
  Christie bytes have been in game (`HANDOFF.md`). `status` no longer prints the flag. The packs still carry it.
- Upstream: `GEMINI.md` is now identical to upstream's. `CLAUDE.md` exists upstream and not here, and
  `README.md` and `AGENTS.md` share 11 and 27 lines with the merge base (`23902ef`), so a merge from upstream
  will conflict in all three ([`after/lines.tsv`](2026-11-13-agent-entry/after/lines.tsv)).

## Run it again

```sh
git worktree add --detach ../wt-before 19ca55a && git worktree add --detach ../wt-after 62f919e
M=docs/audits/2026-11-13-agent-entry/measure.py           # pip install tiktoken for the token columns
python3 $M walk --tree ../wt-before --routes before        # about 6 minutes; it builds packs
python3 $M walk --tree ../wt-after --routes after          # about 7 minutes
python3 $M key --tree ../wt-after                          # the answer key, from the artefacts
bash docs/audits/2026-11-13-agent-entry/probe_harness.sh ../wt-after   # after: npm install the four CLIs
```
