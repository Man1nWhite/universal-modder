# universal-modder, Man1nWhite's fork

A fork of [rehan-remade/universal-modder](https://github.com/rehan-remade/universal-modder): skills, the `um`
CLI and a knowledge base with which an AI coding agent mods PC games. Upstream's README describes the
toolkit, its skills and its examples. This page says what is different here.

**Agents start at [`AGENTS.md`](AGENTS.md).** It has one command per question, and this page repeats none
of them.

## What this fork adds

PAYDAY 2 packs, tracked in `dist/` and rebuilt byte for byte by CI: full-body and body-only Legendary Armour
Skins outfits (Miranda Lawson, Christie) and head replacements over the vanilla heisters (Miranda, Geralt).
Three pipelines under `tools/` build them; [`tools/README.md`](tools/README.md) says which builds what, how a
pack is installed and what the pipelines share.

## Installing

Upstream's plugin, marketplace and extension commands install upstream, which has none of the above. To work
on this fork, clone it and start the agent inside the clone.

| In a clone | reads |
|---|---|
| Claude Code 2.1.277 or later, Codex, Cursor, Copilot, OpenCode | `AGENTS.md` |
| Gemini CLI | `GEMINI.md`, which is the one line `@AGENTS.md` |

There is no `CLAUDE.md`: Claude Code reads `AGENTS.md` where there is none, and Cursor's CLI, VS Code and
Copilot CLI read a `CLAUDE.md` in addition to `AGENTS.md`. The evidence, and the command that makes each
harness list what it loaded, is in
[`docs/audits/2026-11-13-agent-entry.md`](docs/audits/2026-11-13-agent-entry.md).

Skills are in `skills/`, copied to `.agents/skills` and `.claude/skills` where the harnesses look. MCP
config is in `.mcp.json`, `.codex/config.toml`, `.cursor/mcp.json`, `.vscode/mcp.json`,
`gemini-extension.json` and `opencode.json`.

MIT licensed ([`LICENSE`](LICENSE)); credits are in upstream's README.
