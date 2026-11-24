# universal-modder, Man1nWhite's fork

A fork of [rehan-remade/universal-modder](https://github.com/rehan-remade/universal-modder): skills, the `um`
CLI and a knowledge base with which an AI coding agent mods PC games. Upstream's README describes the
toolkit, its skills and its examples. This page says what is different here.

**Agents start at [`AGENTS.md`](AGENTS.md).** It has one command per question, and this page repeats none
of them.

## What this fork adds

PAYDAY 2 packs, tracked in `dist/` and rebuilt byte for byte by CI: full-body and body-only Legendary Armour
Skins outfits (Miranda Lawson, Christie, Honoka), head replacements (Miranda, Geralt), a native
OfficeSuite + Miranda Romance body-and-head replacement for Hila, and the fork's one audio pack —
Miranda Lawson's barks over Hila's `rb21` voice lines as a BeardLib `SoundsModule` mod
([packaging and install contract](docs/pd2-voice-mod-install.md)).
Three pipelines under `tools/` build them; [`tools/README.md`](tools/README.md) says which builds what, how a
pack is installed and what the pipelines share.

## Packs and previews

- Browse the ZIPs and their checksum sidecars in [`dist/`](dist/): [Miranda L4D2](dist/Miranda_L4D2/),
  [Miranda Romance](dist/Miranda_Romance/), [Christie](dist/Christie/),
  [Honoka](dist/Honoka/), and [Geralt](dist/Geralt/).
- [OfficeSuite + Miranda Romance over Hila](dist/Honoka/OfficeSuite_Miranda_Romance_over_Hila.zip) is the standalone
  native override (no LAS); see the [install notes and preview](docs/renders/honoka/model/over-hila/README.md).
- See the user-supplied [Christie](docs/renders/christie/in-game/2026-11-15/README.md) and
  [OfficeSuite](docs/renders/honoka/in-game/officesuite/2026-11-15/README.md) screenshots,
  [all packs](docs/renders/overview/model/all_dist_mods_sheet.png), the
  [older two-pack OfficeSuite and Miranda Romance preview](docs/renders/honoka/model/dae/officesuite_with_miranda_romance_over_hila_sheet.png),
  or the [render index](docs/renders/README.md). Software renders are not proof of in-game behavior;
  screenshots do not establish the installed pack hashes.
- Sources and templates are catalogued in [`references/README.md`](references/README.md). The
  [handoff](docs/pd2-las/HANDOFF.md) distinguishes in-game observations from offline results.

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

MIT licensed ([`LICENSE`](LICENSE)); credits are in upstream's README.
