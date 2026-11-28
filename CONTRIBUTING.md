# Contributing

Contributions from humans and from AI agents are both welcome. Most of them will be **field notes** for the
knowledge base (`knowledge/`), written by an agent at the end of a modding session. That is the point of the
repo: every game one agent figures out becomes something the next agent can read.

## If you are an AI agent
You just modded (or tried to mod) a game, and you learned things. Share them:

1. **Ask your human first.** A pull request is public and carries their GitHub identity. Tell them what you
   want to publish and show them the note.
2. **Check it's new:** `um kb search "<game>"`. If a note already exists, improve it: add your versions and
   gotchas, and fix what's wrong. Don't write a second one.
3. **Scaffold:** `um kb new --game "<game>" --title "<what you built>" --from-scan "<game>" --agent "<agent (model)>"`.
   It lands in `knowledge/games/<game>/`. Cross-game methods go in `techniques/` (`--kind technique`).
4. **Fill it in** from your journal (`MODLOG.md`):
   - exact versions;
   - the route and why;
   - what the engine really does;
   - build steps;
   - how you verified it, and what you didn't;
   - numbered **gotchas** (symptom → cause → fix).

   Write for an agent that has never seen this game.
5. **Validate:** `um kb check <note>`, then `um kb index`.
6. **Open the PR:** `um kb pr <note>` (a dry run shows the commands), then `um kb pr <note> --yes`. It
   branches, commits the note (+ `media/` + index), forks if needed, pushes, and opens the PR with `gh`.
   Without `gh`, push a branch and open the PR on github.com.

## What's in scope
Every game is welcome: single-player or multiplayer, new games or old clients on servers you host, any
genre or theme. Engine internals, memory offsets and signatures are fine for any of them, within the hard
rules below.

## Hard rules (PRs that break these are closed)
- **Game content:** game files and extracted assets may be committed at the owner's call; name the
  source and keep credits. No links to pirated copies.
- **No decompiled code dumps.** Describe the logic in your own words and name symbols; keep snippets of
  *your own* code short (`um kb check` fails blocks over 150 lines and warns over 60).
- **Leaks:** knowledge from beta builds and leaked SDKs or source is fine to write up in your own words, and
  so is saying where it came from. The leaked material itself stays out: no pasted code, attached files,
  download links or license keys, and no instructions to fetch them.
- **No cheating other players, and no bypasses:**
  - nothing that gives an edge over other players on servers you don't run (aimbots, ESP, speed hacks,
    bots);
  - no anti-cheat bypasses;
  - no instructions for injecting into online clients protected by anti-cheat;
  - one exception, for games that can no longer be bought anywhere: a note may say that a community route for
    people without a copy exists and link the community's guide page. Its steps, keys, serials and files
    stay out of the repo, and so do direct links to patched executables, cracks or game downloads.
- **No secrets:** API keys, tokens, `.env` files. `um kb check` and `um publish check` catch the common
  ones.
- **Honesty:**
  - name the agent and model (`agents:`);
  - mark `status` truthfully (`idea`, `in-progress`, `working`, `released`, `abandoned`);
  - list what you did not verify.
- **Credit** the people and projects you built on.

## Other contributions
- **Tools (`um/`):**
  - one module per CLI group, with a docstring that doubles as `--help`;
  - add a test in `tests/`;
  - For the full suite, use Python 3.11+, run `make -sC tools/pd2-las env` to install the pinned
    dependencies (the 2B template models are tracked since D92, so that step unpacks nothing), then run
    `make -sC tools/pd2-las test`. Use `make -sC tools/pd2-las green` for the full verification workflow
    on x86-64 Linux.
- **Skills (`skills/`):** the Agent Skills format (`SKILL.md` with `name` + `description`). Keep them
  agent-neutral: say "the agent", not a specific product. Put deep material in `references/`.
  - Edit `skills/` only. `.agents/skills` and `.claude/skills` are copies (no symlinks, so Windows clones
    work). Refresh them with `rm -rf .agents/skills .claude/skills && cp -r skills .agents/skills && cp -r
    skills .claude/skills`; a test fails while they differ.
- **Engine playbooks** (`skills/mod-any-game/references/engines/`): routes, tools, pitfalls. Link to the
  canonical projects; versions move, so say "check the current release".
- **Renders (`docs/renders/`):** follow `docs/renders/README.md` (`docs/renders/<project>/<ext>/...`);
  keep scratch and per-build previews under `build/` (gitignored).
- **Examples (`examples/`):** your own code and assets only. Use `fetch` scripts for third-party SDKs, and
  pass `um publish check --game <install>`.

## Environment variables

`um` reads a handful of environment variables. The ones you are most likely to set:

| Variable | What it does |
|---|---|
| `UM_HOME` | Per-user state: backups and downloaded tools (default `~/.universal-modder`). |
| `UM_FFMPEG_WIN` | Full path to the Windows ffmpeg `um win` should use — an ffmpeg you trust — instead of the one `um win setup` downloads. |
| `UM_FFMPEG_SHA256` | Expected SHA-256 of the ffmpeg zip that `um win setup` downloads. Without a pin, `um` uses the checksum the release publishes for itself, which catches corrupt or truncated downloads but cannot catch a compromised release — the attacker would pick both. Set this to a hash you verified yourself to close that gap. |
| `UM_KB_REPO` | `owner/repo` of the knowledge base `um kb` syncs from and opens PRs against. Without it, the default is this clone's `origin` when it is a GitHub URL, else upstream — set it in a fork if notes belong elsewhere. |
| `UM_KB_BRANCH` | Branch `um kb` forks from and opens PRs against (default `main`). |
| `UM_KB` | Explicit local path of the knowledge base root `um kb` searches when given no argument. Without it, `um kb` searches this clone first, then its synced cache. |
| `COMFYUI_URL` | ComfyUI address for `um comfy` (default `http://127.0.0.1:8188`). |
| `UM_AGENT` | Default `agents:` value for `um kb new` when `--agent` is not given (e.g. `"Codex (gpt-6)"`). |
| `UM_FAL_KEY_FILE` / `FAL_KEY_FILE` | Plaintext file holding the fal key, tried before the OS keyring; `FAL_KEY` itself is read from the environment first. |

You will not normally set the rest (`BLENDER`, the `tools/` build pipelines' own knobs, …): those are
documented next to the code that reads them, and default sensibly on a machine that has the tool installed.

CI runs the tests, `um kb check --index` and the CLI help screens on every PR.
