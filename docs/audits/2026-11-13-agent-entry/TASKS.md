# Eight tasks, to run on any commit of this repository

A way to count what an agent pays to reach the right action here, that does not depend on who counts. Give
each task to a fresh agent session started in a checkout of the commit, with nothing else in the prompt. Run
it on two commits and compare.

## Protocol

1. One worktree per commit, so that no session sees the other's files:
   `git worktree add --detach ../wt-a <commit>`. Start the agent inside it.
2. One fresh session per task. Paste the task text, nothing more. Do not name a file or a command.
3. T1 starts from a restarted sandbox: before the session, `rm -rf .venv dist build node_modules`. Every other
   task starts from a checkout that is set up (`make -sC tools/pd2-las env` has run).
4. T8 starts from a changed pack. Before the session, from this checkout:
   `python3 docs/audits/2026-11-13-agent-entry/measure.py change --tree ../wt-a`. It changes one member of
   `dist/Christie_LAS_Slim.zip`, writes the zip as the pack writer does and the `.sha256` as the builder
   does: what a rebuild on purpose leaves. (A zip the writer would not give, one with a comment for
   instance, fails `test_that_writer_gives_each_tracked_pack_its_files` on any commit, whatever the documents
   say.) Afterwards, in the worktree, `git checkout -- .`.
5. Count from the session's transcript, not from what the agent says it did: one call per shell command and
   per file read; the bytes of every file read and of every command's output. Record whether the answer
   matches the key.
6. The key: `python3 docs/audits/2026-11-13-agent-entry/measure.py key --tree ../wt-a`, run from this
   checkout before the first session (it reads artefacts only, and works on a commit that predates it). It
   must come out the same on both commits apart from `commit`: no tracked zip differs between them.

## Tasks

| | Task text | The answer is right when |
| --- | --- | --- |
| T1 | This sandbox was restarted. Get this checkout ready to build the PAYDAY 2 packs. | `python3 tools/pd2-las/status.py` prints `"ready": true` |
| T2 | Are the tracked PAYDAY 2 packs intact? Say how many there are and name any whose zip is not the tracked one. | 14 packs in `dist/` (16 tracked zips), none differs: key `packs`, `every_zip_is_its_sidecar` |
| T3 | Is everything green? Run every check the `test` workflow runs and report each. | all six of key `ci_checks` were run and reported |
| T4 | Rebuild `Christie_LAS_Slim` and prove that the result is byte for byte the tracked pack. | the pack was built in this session and its sha256 shown equal to key `packs` |
| T5 | Was `Christie_LAS_Slim` seen in game? When, and were those the bytes that are tracked now? | key `seen_in_game`: the date, and `were_the_tracked_bytes` |
| T6 | What is open on the PAYDAY 2 packs? List every open item, for all 14 packs. | in-game sign-off, the slim sleeve defect, the gloss, and that `lawson_las` and nine head packs have no in-game record of their tracked bytes (key `no_in_game_flag` lists those ten and the two Miranda LAS packs the sign-off is for) |
| T7 | Which command rebuilds `Geralt_over_Rust`? Do not run it. | it names what `tools/pd2-las/fresh.py` runs for `heads`: `tools/build_joy_head_mods.py`, or a make target that runs it |
| T8 | `dist/Christie_LAS_Slim.zip` was changed on purpose and its `.sha256` with it. Make the test suite pass again without changing the zip back. | `.venv/bin/python -m pytest -q tests` passes and `git status --short dist` still lists the zip |

## What `measure.py walk` is, and is not

`measure.py walk` replays, for real, the shortest route the documents of a commit lead to: it starts with
`AGENTS.md` in context and takes a step only when text already read points to it, and it fails when the
pointer is not there. It is a lower bound that a careful agent can reach, and a way to see which steps the
documents do not lead to at all. It is not a session of a model: a model reads more than it must, retries, and
sometimes goes wrong. The protocol above measures that; the walk does not.
