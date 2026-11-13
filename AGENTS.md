# universal-modder

A game-modding toolkit and knowledge base for AI coding agents, forked from `rehan-remade/universal-modder`.
The work in this fork is PAYDAY 2: 14 tracked packs in `dist/`, built by three pipelines under `tools/`.

## PAYDAY 2 packs: one command per question

| Question | Run or read |
|---|---|
| Fresh clone, or a restarted sandbox (no `.venv`, `git status` lists `dist/` as deleted) | `make -sC tools/pd2-las env` |
| State of the 14 packs, their sizes and hashes, what to run next | `make -sC tools/pd2-las status` |
| Is everything green? Every check of the `test` workflow | `make -sC tools/pd2-las green` |
| Rebuild a pack and prove its bytes (`"is": "tracked"`) | `make -sC tools/pd2-las <target>`: `build` (Miranda_LAS), `busty`, `christie`, `slim`, `lawson` (lawson_las), `heads` (the nine `*_over_*` packs) |
| Was a pack seen in game, and which bytes? Dead ends | `docs/pd2-las/HANDOFF.md` |
| What is open | "Next" in `tools/pd2-las/README.md` |
| Before changing a builder, a codec or what a pack holds | `tools/README.md` (the three pipelines, the invariants they share), then `tools/pd2-las/README.md` or `tools/pd2-port/README.md` |

- Take sizes, hashes and test counts from `status` and `green`, not from a document.
- A rebuilt pack needs no document edited: commit the zip with its `.sha256`. The exception is `lawson_las`,
  whose size and sha256 `tools/pd2-port/STATUS.md` quotes under a test.
- A strange git state (local `HEAD` behind the pushed branch) is not a reason for `git reset --hard` or
  `git checkout -- dist build`: both discard work that was never pushed. First `git status` and
  `git log origin/<branch>..HEAD` must show nothing local that the remote lacks.

## Modding any other game
1. Read `skills/mod-any-game/SKILL.md` and follow its loop: intake → recon → route → lab (backups) →
   source of truth → vertical slice → assets → verify in the real game → showcase → publish.
2. Search the knowledge base first: `bin/um kb search "<game or engine>"` (`knowledge/INDEX.md`).
3. At the end, write a field note (`bin/um kb new ...`) and, once your human agrees, open a PR
   (`bin/um kb pr <note> --yes`). See `knowledge/README.md` and `CONTRIBUTING.md`.

## Tools
- `bin/um` is the Python CLI; `bin/um --help` lists its command groups and every group has `--help`. It runs
  through `uv`. Where there is no `uv`: `.venv/bin/python -m um ...`.
- The fal MCP server is configured for every agent and needs `FAL_KEY` in the agent's environment. Without
  MCP, `um fal` does the same over REST (`skills/fal-assets`).
- Skills: edit `skills/`, then copy it over `.agents/skills` and `.claude/skills`; a test fails while the
  copies differ.
- Engine playbooks: `skills/mod-any-game/references/engines/`. Worked examples: `examples/`.

## Rules (full reasoning in `skills/mod-any-game/references/safety.md`)
- **What you can mod:** any game the user owns: single-player, multiplayer, or servers the user hosts.
  - Never touch online clients protected by anti-cheat.
  - Never write cheats against other players (aimbots, ESP, speed hacks).
  - Never bypass anti-cheat, DRM or ownership checks.
- **Saves:** `um backup` saves before modded launches.
- **What you ship:** never commit or publish game files, extracted assets or decompiled code. Keep
  decompiles outside the repo.
- **Processes:** kill by exact PID (`um win kill`), never by name pattern.
- **Ask first** before:
  - driving the user's mouse and keyboard, and never focus a game with an online mode while they're typing;
  - installing loaders into game folders or changing the registry;
  - publishing anything, PRs included.
- **Keep a journal:** a `MODLOG.md` in the mod's working folder. It becomes your field note at the end.
- **Keep the state in a command:** on a long project the next agent should not have to rebuild the state
  from a journal (`tools/pd2-las/status.py` is the pattern).
- **Sequence your file edits:** parallel edits to the same file race, and the
  loser silently clobbers the winner.

## Working on the toolkit itself
- **Python:** 3.10+, deps Pillow, numpy and PyYAML. Code lives in `um/`, one module per CLI group, each
  with `register(sub)` and a docstring that doubles as `--help`.
- **Windows tools:** `um/ps1/*.ps1` embed C# 5 (Windows PowerShell 5.1's compiler): no string
  interpolation, no `out var`, no expression-bodied members.
- **Tests:** `make -sC tools/pd2-las test` is the suite, `green` everything CI checks.
- **Wording:** keep skills and docs agent-neutral ("the agent", not a product name) except in sections
  about one specific agent.
