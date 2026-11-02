# universal-modder

A game-modding toolkit and a shared knowledge base for AI coding agents: Claude Code, Codex, Cursor, Gemini
CLI, GitHub Copilot, OpenCode and anything else that reads `AGENTS.md`. When someone opens an agent in this
repo, they almost always want to **mod a game**, or to learn how a game was modded.

## Start here
1. **Read `skills/mod-any-game/SKILL.md` and follow its loop:** intake → recon → route → lab (backups) →
   source of truth → vertical slice → assets → verify in the real game → showcase → publish.
2. **Search the knowledge base first:** `bin/um kb search "<game or engine>"`. Other agents may already have
   written down the exact versions, routes and gotchas (`knowledge/INDEX.md`).
3. **On a long-running project, keep a status page:** the agent that picks
   the work up next should not have to reconstruct the state from a journal.
   The PAYDAY 2 LAS pack keeps one at `tools/pd2-port/STATUS.md` (shipped
   artefacts, measured check results, the open problem, the traps) next to
   its journal — copy that pattern.
4. **At the end, share what you learned:** write a field note (`bin/um kb new ...`) and, once your human
   agrees, open a PR (`bin/um kb pr <note> --yes`). See `knowledge/README.md` and `CONTRIBUTING.md`.

## Tools
- **`bin/um`** is the Python CLI, and it sets itself up with `uv`.
  - Put it on PATH: `export PATH="$PWD/bin:$PATH"` (from Windows cmd or PowerShell, add `bin` to PATH and
    `bin\um.cmd` runs it), or install it anywhere with
    `uv tool install git+https://github.com/rehan-remade/universal-modder`.
  - Every group has `--help`:
    - `scan`: installed games, engine, anti-cheat, loaders, saves, routes
    - `fal`: sprites, textures, PBR, 3D, rigs, SFX, music, voice, video via fal's REST API
    - `comfy`: images from a local ComfyUI server, with no API key
    - `sprite` / `render3d`: art → engine-ready frames (`render3d` needs Blender on PATH or `BLENDER=...`)
    - `win`: launch, screenshot, input, record on Windows (also from WSL)
    - `video`: contact sheets and EDL showcase edits
    - `backup`: snapshot and restore saves
    - `publish`: pre-release lint
    - `kb`: the knowledge base
- **fal MCP server:** `https://mcp.fal.ai/mcp` with header `Authorization: Bearer $FAL_KEY`.
  - It's pre-configured per agent: `.mcp.json` (Claude Code), `.codex/config.toml` (Codex),
    `.cursor/mcp.json` (Cursor), `.vscode/mcp.json` (VS Code / Copilot), `gemini-extension.json`
    (Gemini CLI), `opencode.json` (OpenCode).
  - It needs `FAL_KEY` in the agent's environment; without it the server doesn't connect. fal's OAuth
    endpoint, `https://mcp.fal.ai/mcp-relay`, takes a browser sign-in instead (see `skills/fal-assets`).
  - No MCP? `um fal` does the same over REST. It also finds the key that `um fal key set` stored (the
    desktop keyring on Linux, `~/.secrets/fal-key` elsewhere).
- **Skills** (`skills/*/SKILL.md`, Agent Skills format) are copied where agents look for them in a clone:
  `.agents/skills` (Codex, Gemini CLI, Copilot, Cursor, OpenCode) and `.claude/skills` (Claude Code). Edit
  `skills/`, then copy it over; a test fails while the copies differ.
- **Engine playbooks:** `skills/mod-any-game/references/engines/`.
- **Worked examples:** `examples/terraria-tmodloader`, `examples/aoe2-de-civ`,
  `examples/minecraft-gta5-passthrough`, `examples/outer-wilds-portal-gun`, `examples/mindustry-homing`,
  `examples/cities-skylines-city-dashboard`.

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
- **Sequence your file edits:** parallel edits to the same file race, and the
  loser silently clobbers the winner.

## Working on the toolkit itself
- **Python:** 3.10+, deps Pillow, numpy and PyYAML (`uv` handles them via `bin/um`). Code lives in `um/`,
  one module per CLI group, each with `register(sub)` and a docstring that doubles as `--help`.
- **Windows tools:** `um/ps1/*.ps1` embed C# 5 (Windows PowerShell 5.1's compiler): no string
  interpolation, no `out var`, no expression-bodied members.
- **Tests:** `uv run --with pytest pytest -q tests`. CI also runs `um kb check --index` and
  `um publish check .`.
- **Wording:** keep skills and docs agent-neutral ("the agent", not a product name) except in sections
  about one specific agent.

## Active Project: PAYDAY 2 Miranda Lawson Mods (`dist/`)

All built PAYDAY 2 deliverables live in **`dist/`** (tracked in git with `.sha256` sidecars), while source model archives sit in **`models/`** and reference mod archives sit in **`references/`**:

| Deliverable in `dist/` | Type | Source & Reference Archives | Builder Script |
|---|---|---|---|
| `dist/lawson_las.zip` (`9,107,070` B) | Full-body LAS outfit (ME2 Romance) | `models/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip` + `references/2b.rar` | `tools/pd2-port/build_las_pack.py` |
| `dist/Miranda_LAS.zip` (`5,864,923` B) | Full-body LAS outfit (L4D2 port) | `models/l4d2_miranda_lawson_1.zip` + `references/2b.rar` | `tools/pd2-las/build_models.py` |
| `dist/Miranda_L4D2_over_Joy.zip` (`10,634,831` B) & `dist/Miranda_Romance_over_Joy.zip` (`10,368,473` B) | Joy head-replacement `mod_overrides` (L4D2 & ME2 Romance) | `models/*` + `references/Ada Wong over Joy.7z` | `tools/build_joy_head_mods.py` |
| `dist/Miranda_L4D2_over_Clover.zip` (`7,684,781` B) & `dist/Miranda_Romance_over_Clover.zip` (`7,424,198` B) | Clover + Safe House head-replacement `mod_overrides` | `models/*` + `references/Heister - FPS Gloves in TPS 2.zip` | `tools/build_joy_head_mods.py` |
| `dist/Miranda_L4D2_over_Bonnie.zip` (`8,194,781` B) & `dist/Miranda_Romance_over_Bonnie.zip` (`7,921,882` B) | Bonnie + Safe House head-replacement `mod_overrides` | `models/*` + `references/Heister - FPS Gloves in TPS 2.zip` | `tools/build_joy_head_mods.py` |
| `dist/Miranda_L4D2_over_Sydney.zip` (`7,186,118` B) & `dist/Miranda_Romance_over_Sydney.zip` (`6,931,272` B) | Sydney head-replacement `mod_overrides` | `models/*` + `references/Heister - FPS Gloves in TPS 2.zip` | `tools/build_joy_head_mods.py` |

### Agent Quickstart & Sandbox Recovery
Arena sandboxes do not persist `.venv/`, `/tmp/`, or untracked `dist/`/`build/` files across container restarts, and local `HEAD` may rewind to the branch base on restart. Always run:
```bash
git fetch origin && git reset --hard origin/$(git rev-parse --abbrev-ref HEAD)
bash tools/pd2-las/bootstrap.sh
.venv/bin/python tools/pd2-port/check_all.py
```
`bash tools/pd2-las/bootstrap.sh` sets up `.venv` (pinned `pillow==13.0.0 numpy==2.4.6 pyyaml pytest pyflakes py7zr`), extracts `2b.rar` and `Ada Wong over Joy.7z`, rebuilds `dist/Miranda_LAS.zip`, `dist/Miranda_L4D2_over_Joy.zip`, and `dist/Miranda_Romance_over_Joy.zip`, verifies all four `dist/*.zip.sha256` digests, and runs the full `pytest` and `pyflakes` suites.

### Critical Diesel Engine & PAYDAY 2 Invariants (Do Not Break)
1. **Two Diesel `.model` Parsers**:
   - `tools/pd2-las/diesel_model.py` (`dm.ModelFile.read` + `dm.decode_geometry` / `dm.decode_topology` / `dm.decode_model_data`) decodes any legacy PAYDAY 2 `.model` (`2b.model`, `miranda.model`, `npc_criminal_joy_1.model`).
   - `tools/pd2-port/dmodel.py` (`DieselModel.from_bytes`) only populates `geo.weights3` for `lawson.model`.
2. **Global `Topology` Indices in Multi-Atom Drawables**:
   - In Diesel `.model` files (`npc_criminal_joy_1.model`, `miranda.model`), triangle indices in `Topology` for `RenderAtom` `i` are **global vertex indices** in `[base_vertex, base_vertex + slice_len - 1]`, never local `0 .. slice_len - 1`.
3. **UV Coordinate Convention (`v_diesel = 1.0 - v_img`)**:
   - Diesel `Geometry.uv0` stores OpenGL/COLLADA bottom-up `v` (`v = 1.0` is top row `y_img = 0` of the DDS image; `v = 0.0` is bottom row `y_img = H - 1`).
   - When packing a 2×2 atlas at top-down quadrant `(qx, qy) ∈ {0, 1}²`, map `u_diesel = 0.5 * qx + 0.5 * u_img` and `v_diesel = 1.0 - (0.5 * qy + 0.5 * v_img)`.
4. **DXT5 Diffuse Alpha = Specular/Gloss & DXT5nm Normal Maps**:
   - In `generic:...:DIFFUSE_TEXTURE:NORMALMAP:...` shaders (without `ALPHA_MASKED`), the diffuse texture's alpha channel is **gloss/specular intensity** (`alpha = 255` makes skin/fabric look like wet plastic in-game). Keep diffuse alpha low (`<= 28` or normal-slope attenuated).
   - Diesel normal maps use swizzled **DXT5nm** (`R = G = B = ny`, `A = nx`, DirectX Y− green channel inverted to Y+ via `dds.pd2_normal_channels(arr, invert_y=True)`).
5. **Standing-Pose Shoulder/Arm Alignment & Elbow Hinge Axis (Full-Body LAS)**:
   - PAYDAY 2's in-game standing pose swings `RightShoulder`/`LeftShoulder` ~19° downward from bind pose (`z: 147→142 cm`). Retargeting must align clavicle/upper-arm/forearm directions in the **animated standing pose** and align the source elbow hinge axis (`local +Z`) with PD2's `RightForeArm`/`LeftForeArm` local `+Z` axis so elbows never shear when bending.
6. **Joy Head-Replacement (`mod_overrides`) Collar & Skinning Contract**:
   - `npc_criminal_joy_1.model` (`and identical npc_criminal_joy_1_menu.model`) uses `g_head_mask_off` (`id=120`, `geo=228`, `topo=229`) and `g_head` (`id=121`, `geo=233`, `topo=234`), both bound to `SkinBones 44` (`['Spine2', 'Neck', 'Head']`).
   - Joy's `g_body` hoodie collar (`z ∈ [151, 160]`) is weighted `95.5%` to `Spine2` (`0% Neck`), with an inner collar cone at `y ≈ 7.2–8.5 cm` and outer V-neck lapel at `y ∈ [12.9, 15.5] cm`. Keep lower-throat vertices in the collar channel `y ∈ [9.0, 10.6] cm` and weight `z <= 156 cm` `100%` to `Spine2` so the neck never separates from the collar when `Neck`/`Head` rotate.

