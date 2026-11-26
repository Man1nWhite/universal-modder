# universal-modder, Man1nWhite's fork

A fork of [rehan-remade/universal-modder](https://github.com/rehan-remade/universal-modder): skills, the `um`
CLI and a knowledge base with which an AI coding agent mods PC games. Upstream's README describes the
toolkit, its skills and its examples. This page says what is different here.

**Agents start at [`AGENTS.md`](AGENTS.md).** It has one command per question, and this page repeats none
of them.

## What this fork adds

PAYDAY 2 packs, tracked in `dist/` and rebuilt byte for byte by CI: full-body and body-only Legendary Armour
Skins outfits (Miranda Lawson, Christie, Honoka), head replacements (Miranda, Geralt), a native
OfficeSuite + Miranda Romance body-and-head replacement for Hila, and the fork's audio — Miranda
Lawson's barks over Hila's `rb21` voice lines, as one Wwise IMA ADPCM `.stream` per voice-line id
(`Miranda_Lawson_VO_over_Hila_Stream`, no BeardLib: [packaging and install
contract](docs/pd2-voice-mod-install.md), and the route dissected in
[`docs/tokoyami-hila-voice-mod-analysis.md`](docs/tokoyami-hila-voice-mod-analysis.md)). Two more packs
of the same route ship alongside it: `Geralt_VO_over_Rust_Stream` (`dist/Geralt/`) and
`Arivus_VO_over_Hoxton_Stream` (`dist/Arivus/`) — the three are alternatives writing the same shared
ids, so exactly one should be installed.
Three pipelines under `tools/` build them; [`tools/README.md`](tools/README.md) says which builds what, how a
pack is installed and what the pipelines share. The Arivus head also ships as a tracked `.glb` + `.dds`
interchange export ([`Arivus_Head_over_Old_Hoxton_GLB.zip`](dist/Arivus/Arivus_Head_over_Old_Hoxton_GLB.zip)),
rebuilt by `make -sC tools/pd2-las glb`.

## Packs and previews

- Browse the ZIPs and their checksum sidecars in [`dist/`](dist/): [Miranda L4D2](dist/Miranda_L4D2/),
  [Miranda Romance](dist/Miranda_Romance/), [Christie](dist/Christie/),
  [Honoka](dist/Honoka/), [Geralt](dist/Geralt/) and [Arivus](dist/Arivus/).
- [OfficeSuite + Miranda Romance over Hila](dist/Honoka/OfficeSuite_Miranda_Romance_over_Hila.zip) is the standalone
  native override (no LAS); see the [install notes and preview](docs/renders/honoka/model/over-hila/README.md).
- See the user-supplied [Christie](docs/renders/christie/in-game/2026-11-15/README.md) and
  [OfficeSuite](docs/renders/honoka/in-game/officesuite/2026-11-15/README.md) screenshots,
  [all packs](docs/renders/overview/model/all_dist_mods_sheet.png),
  [Arivus over Old Hoxton](docs/renders/arivus/model/over-hoxton/README.md), the
  [older two-pack OfficeSuite and Miranda Romance preview](docs/renders/honoka/model/dae/officesuite_with_miranda_romance_over_hila_sheet.png),
  or the [render index](docs/renders/README.md). Software renders are not proof of in-game behavior;
  screenshots do not establish the installed pack hashes.
- Sources and templates are catalogued in [`references/README.md`](references/README.md). The
  [handoff](docs/pd2-las/HANDOFF.md) distinguishes in-game observations from offline results.

## Cloning

This is a heavy checkout by design: about 190 MB of built packs under `dist/`, ~220 MB of source
archives under `references/` (the only copy of some of them), and ~40 MB of archived renders, so
`.git` is around 420 MB with no Git LFS. Two ways to pay less:

```sh
git clone --filter=blob:none https://github.com/Man1nWhite/universal-modder   # blobs on demand
git clone --depth 1 https://github.com/Man1nWhite/universal-modder            # one commit only
```

Agents that only need the toolkit, the knowledge base and the skills can go further and skip the
packs and archives with a sparse checkout (`git sparse-checkout set --no-cone '/*' '!/dist' '!/references'`),
then read [`tools/pd2-las/README.md`](tools/pd2-las/README.md) before rebuilding anything.
`tests/test_repo_weight.py` stops a new file over 25 MB from being committed unnoticed.

## Installing

Upstream's plugin, marketplace and extension commands install upstream, which has none of the above. To work
on this fork, clone it and start the agent inside the clone.

| In a clone | reads |
|---|---|
| Claude Code 2.1.277 or later, Codex, Cursor, Copilot, OpenCode | `AGENTS.md` |
| Gemini CLI | `GEMINI.md`, which is the one line `@AGENTS.md` |

Skills are in `skills/`, copied to `.agents/skills` and `.claude/skills` where the harnesses look. MCP
config is in `.mcp.json`, `.codex/config.toml`, `.cursor/mcp.json`, `.vscode/mcp.json`,
`gemini-extension.json` and `opencode.json`.

## Licence

The **code, skills, knowledge base and documentation** are MIT licensed ([`LICENSE`](LICENSE));
credits are in upstream's README. That grant covers what this repository authored, not the
third-party material it carries as build input and as deliverables: the archives under
`references/`, the game-derived meshes, textures and voice lines inside the ZIPs under `dist/`,
and the archived captures under `docs/renders/` remain the property of their creators and are
here at the owner's call. [`NOTICE.md`](NOTICE.md) says which is which and points at the
per-archive provenance table in [`references/README.md`](references/README.md).
