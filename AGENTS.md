# universal-modder

Game-modding toolkit and knowledge base for AI coding agents, forked from `rehan-remade/universal-modder`.
The work in this fork is PAYDAY 2: tracked packs in `dist/`, built by three pipelines under `tools/`.

## PAYDAY 2 packs: one command per question

| Question | Run or read |
|---|---|
| Fresh clone or restarted sandbox (no `.venv`, `dist/` listed deleted) | `make -sC tools/pd2-las env` |
| State of the packs, their sizes and hashes, what to run next | `make -sC tools/pd2-las status` |
| Is everything green? Every check of the `test` workflow | `make -sC tools/pd2-las green` |
| Rebuild a pack and prove its bytes (`"is": "tracked"`) | `make -sC tools/pd2-las <target>`: `build`, `honokodae`, `bunny`, `heads`, `voices_stream`, `voices_geralt`, `voices_arivus`, or `glb` |
| Was a pack seen in game, which bytes? Dead ends | `docs/pd2-las/HANDOFF.md` |
| Why a route or format is so, and if it holds | `docs/pd2-las/DECISIONS.md` (indexed, cited `D<n>`) |
| What is open | "Next" in `tools/pd2-las/README.md` |
| Where a document lives | `docs/README.md` (generated: `python tools/gen_docs_index.py`) |
| Before changing a builder, codec or pack contents | `tools/README.md` (the three pipelines and their shared invariants), then that pipeline's own README |

- Take sizes, hashes and counts from `status` and `green`, not from a document.
- No `make` (native Windows)? `python tools/tasks.py <target>` runs the same targets (a test keeps the lists equal).
- A rebuilt pack needs no document edited: commit the zip with its `.sha256` (`status` prints it if
  the builder writes the sidecar itself; `make -sC tools/pd2-las status` is the check).
- A strange git state (local `HEAD` behind the pushed branch) is not a reason for `git reset --hard` or
  `git checkout -- dist`: both discard work that was never pushed. `git status` and
  `git log origin/<branch>..HEAD` must first show nothing local the remote lacks; then
  `git fetch` + `git reset --hard origin/<branch>` is the way back (a restarted sandbox needs only
  `make -sC tools/pd2-las env`).

## Modding any other game
`skills/mod-any-game/SKILL.md` is the loop: intake → recon → route → lab (backups) → source of truth →
vertical slice → assets → verify in the real game → showcase → publish. Search the knowledge base first
(`bin/um kb search "<game>"`, `knowledge/INDEX.md`); at the end write a field note (`bin/um kb new`) and,
once your human agrees, open a PR (`knowledge/README.md`, `CONTRIBUTING.md`).

## Tools
- `bin/um` is the Python CLI; `bin/um --help` lists its groups and every group has `--help`. It runs
  through `uv`, falling back to `.venv/bin/python` or `python3` when `uv` is absent.
- The fal MCP server needs `FAL_KEY` in the agent's environment; without MCP, `um fal` does the same over
  REST (`skills/fal-assets`).
- Skills: edit `skills/`, then `python tools/sync_skills.py`; a test fails while the copies differ.
- Engine playbooks: `skills/mod-any-game/references/engines/`. Worked examples: `examples/`.

## Rules (full reasoning in `skills/mod-any-game/references/safety.md`)
- **What you can mod:** any game. Never touch online clients protected by anti-cheat and never write
  cheats against other players.
- **Saves:** `um backup` saves before modded launches.
- **What you ship:** game-derived assets and exports may be committed anywhere at the owner's call;
  keep decompiles and secrets out.
- **Renders:** tracked renders go in `docs/renders/<project>/<ext>/...` (`docs/renders/README.md`);
  scratch in `build/`.
- **Processes:** kill by exact PID (`um win kill`), never a name pattern.
- **Ask first** before: driving mouse/keyboard (and never focus a game with an online mode while the user
  types); installing loaders into game folders or changing the registry; publishing anything, PRs included.
- **Keep a journal:** `MODLOG.md` in the mod's folder; it becomes your field note.
- **Keep state in a command:** don't make the next agent rebuild it from a journal (`tools/pd2-las/status.py`).
- **Sequence edits:** parallel edits to one file clobber each other.

## Working on the toolkit itself
- **Python:** 3.11+, deps Pillow, numpy and PyYAML. Code lives in `um/`, one module per CLI group, each
  with `register(sub)` and a docstring that doubles as `--help`.
- **Windows tools:** `um/ps1/*.ps1` embed C# 5 (Windows PowerShell 5.1's compiler): no string
  interpolation, no `out var`, no expression-bodied members.
- **Tests:** `pip install -e '.[dev]'` once, then `make -sC tools/pd2-las test` (the suite) and `green`
  (everything CI checks, docs included). The 2B template models are tracked (`references/templates/2b/`,
  D89); a checkout that has lost them skips those tests with the command that restores them.
- **Wording:** keep skills and docs agent-neutral ("the agent", not a product name) except in sections
  about one specific agent.
