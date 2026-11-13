# Which instruction file each harness loads

For each harness and each way of installing this repository: what the harness's own source, documentation
or changelog says it loads, and, where the harness could be run here, what it printed. Sources were read on
2026-11-13; GitHub sources are pinned to the commit that was the head of the default branch that day.

"Measured" means the harness itself was run in a scratch worktree of the commit, without an account, by
[`probe_harness.sh`](probe_harness.sh). Its output is in [`before/harness.txt`](before/harness.txt) and
[`after/harness.txt`](after/harness.txt).

## In a clone

| Harness | Loads | Source | Measured here |
| --- | --- | --- | --- |
| Claude Code | `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` if one exists in the working directory or above it. Only where none exists: `AGENTS.md`, from v2.1.277 on. | [memory docs, "AGENTS.md"](https://code.claude.com/docs/en/memory#agents-md): "An `AGENTS.md`, and no `CLAUDE.md` or `CLAUDE.local.md` in your working directory or above it → Your `AGENTS.md`"; "An `AGENTS.md` and a `CLAUDE.md` … → Your `CLAUDE.md` files only"; "Reading `AGENTS.md` directly requires Claude Code v2.1.277 or later". [CHANGELOG.md](https://github.com/anthropics/claude-code/blob/d37e4dcbe4dd/CHANGELOG.md#L3401), 2.1.277 (on npm since 2026-09-18): "Added AGENTS.md support: in a project with no CLAUDE.md, Claude Code reads AGENTS.md instead"; [2.1.281](https://github.com/anthropics/claude-code/blob/d37e4dcbe4dd/CHANGELOG.md#L3236) extends it to Bedrock, Vertex AI, Foundry, gateways and sessions with telemetry off. | 2.1.323. Before: `CLAUDE.md`, about 13,008 B, and not `AGENTS.md`. After: `AGENTS.md`, about 4,528 B. |
| Codex | `AGENTS.override.md`, else `AGENTS.md`, in every directory from the project root to the working directory. Other names only through `project_doc_fallback_filenames`, empty by default. It stops at `project_doc_max_bytes`, 32,768 by default. | [`codex-rs/core/src/agents_md.rs`](https://github.com/openai/codex/blob/95e0103a5de6/codex-rs/core/src/agents_md.rs#L1-L18) (the module comment, and `DEFAULT_AGENTS_MD_FILENAME`, `LOCAL_AGENTS_MD_FILENAME` at L43-L45); [`codex-rs/config/defaults.toml`](https://github.com/openai/codex/blob/95e0103a5de6/codex-rs/config/defaults.toml#L9-L10) | 0.168.0. Before and after: one `agents_md.instructions` item that holds all of `AGENTS.md`, and no other instruction file. It also loads a list of the skills (about 9,100 B), which this work did not touch. |
| Gemini CLI | `GEMINI.md`. Another name only through `context.fileName` in `settings.json`. `@file` lines in it are imported. A project's `.gemini/settings.json` is ignored in a folder that is not trusted. | [`docs/cli/gemini-md.md`](https://github.com/google-gemini/gemini-cli/blob/b9776560ea57/docs/cli/gemini-md.md#L96-L98): "While `GEMINI.md` is the default filename, you can configure this in your `settings.json` file … use the `context.fileName` property"; [imports, L71-L75](https://github.com/google-gemini/gemini-cli/blob/b9776560ea57/docs/cli/gemini-md.md#L71-L75); [`docs/cli/trusted-folders.md`](https://github.com/google-gemini/gemini-cli/blob/b9776560ea57/docs/cli/trusted-folders.md#L90-L91): "Workspace settings are ignored: The CLI will **not** load the `.gemini/settings.json` file from the project" | 0.68.0. Before: `GEMINI.md`, 12,959 characters, and not `AGENTS.md`. After: `GEMINI.md` with the import of `AGENTS.md` expanded. |
| Cursor, editor | `AGENTS.md` in the project root and in subdirectories, beside `.cursor/rules/*.mdc`. A file named with `@` inside a rule is not inlined. | [Rules, "AGENTS.md"](https://cursor.com/docs/rules#agentsmd): "Cursor supports AGENTS.md in the project root and subdirectories."; ["Referencing files from a rule"](https://cursor.com/docs/rules#referencing-files-from-a-rule): "The file's contents are not inlined into the prompt" | not run: the editor is not available here |
| Cursor, CLI | `AGENTS.md` and `CLAUDE.md`, both. | [CLI, "Rules"](https://cursor.com/docs/cli/using#rules): "The CLI also reads `AGENTS.md` and `CLAUDE.md` at the project root (if present) and applies them as rules alongside `.cursor/rules`." | not run: it installs with `curl https://cursor.com/install -fsS \| bash` ([installation](https://cursor.com/docs/cli/installation)), and from this sandbox that request fails (curl exit 35) |
| Copilot in VS Code, Local harness | `.github/copilot-instructions.md`, `AGENTS.md` and `CLAUDE.md`, each behind a setting; the settings for `AGENTS.md` and for `CLAUDE.md` are both on by default. | [`custom-instructions-reference.md`](https://github.com/microsoft/vscode-docs/blob/0b40d48a2f0e/docs/agents/reference/custom-instructions-reference.md#L175-L183) (`chat.useAgentsMdFile`, `chat.useClaudeMdFile`; "Local checks the workspace-root `CLAUDE.md`, `.claude/CLAUDE.md` …"); [`ai-settings.md`](https://github.com/microsoft/vscode-docs/blob/0b40d48a2f0e/docs/agents/reference/ai-settings.md#L355-L356), both defaults `true` | not run: needs VS Code and an account |
| Copilot CLI | `AGENTS.md`, `CLAUDE.md` and `GEMINI.md`, all three; identical copies are removed. `@file` is expanded in `AGENTS.md` and `CLAUDE.md`, not in `GEMINI.md`. | [`add-custom-instructions.md`](https://github.com/github/docs/blob/6d56af0c8b62/content/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions.md#L26-L43): the table of locations; "It removes duplicate copies of identical … agent instructions"; [L61-L63](https://github.com/github/docs/blob/6d56af0c8b62/content/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions.md#L61-L63): "File references are not expanded in `GEMINI.md`" | 1.0.110. Before: one source, `AGENTS.md + CLAUDE.md + GEMINI.md`. After: two sources, `AGENTS.md` and `GEMINI.md` (11 bytes, read as text). |
| Copilot cloud agent | `AGENTS.md`, `CLAUDE.md` or `GEMINI.md`. | [`custom-instructions-about.md`](https://github.com/github/docs/blob/6d56af0c8b62/data/reusables/copilot/custom-instructions-about.md#L13): "These are specified in files called `AGENTS.md`, `CLAUDE.md`, or `GEMINI.md`." | not run: runs on GitHub |
| OpenCode | `AGENTS.md`, walking up from the working directory. `CLAUDE.md` only where there is no `AGENTS.md`. | [`rules.mdx`](https://github.com/anomalyco/opencode/blob/c4601e3d1433/services/site/src/docs/v1/content/rules.mdx#L95-L103): "if you have both `AGENTS.md` and `CLAUDE.md`, only `AGENTS.md` is used"; the source on the `dev` branch looks for `AGENTS.md` alone: [`instruction.ts`](https://github.com/anomalyco/opencode/blob/c4601e3d1433/packages/core/src/config/plugin/instruction.ts#L87) | 1.19.5 started, and has no command or log line that names the files it read |

## Installed as a plugin or an extension

No harness loads `CLAUDE.md` from a plugin, and none but Gemini CLI loads an instruction file from one at
all. So the instruction files matter only in a clone. And every install command in upstream's README names
`rehan-remade/universal-modder`: installed that way, a harness gets upstream's files, not this fork's.

| Harness | What a plugin or extension can carry | Source |
| --- | --- | --- |
| Claude Code plugin | skills, commands, agents, hooks, MCP and LSP servers. "Claude Code doesn't load a CLAUDE.md at the plugin root, and `claude plugin validate` warns" | [plugin components](https://code.claude.com/docs/en/plugins/components), [manifest reference](https://code.claude.com/docs/en/plugins-reference) (these two sentences as a search of code.claude.com returned them; the manifest's field table was read on the page) |
| Codex plugin | `skills`, `mcpServers`, `apps`, `hooks`, `commands`, `interface`: no instruction file | [`codex-rs/core-plugins/src/manifest.rs`](https://github.com/openai/codex/blob/95e0103a5de6/codex-rs/core-plugins/src/manifest.rs#L49-L78) |
| Gemini CLI extension | `contextFileName`: "If this property is not used but a `GEMINI.md` file is present in your extension directory, then that file will be loaded." This repository's `gemini-extension.json` sets it to `AGENTS.md`. | [`docs/extensions/reference.md`](https://github.com/google-gemini/gemini-cli/blob/b9776560ea57/docs/extensions/reference.md#L158-L161) |
| Cursor plugin | `skills/`, `rules/` (`.mdc`), `mcp.json`: no `AGENTS.md` | [cursor/plugins README](https://github.com/cursor/plugins/blob/6e359ce0aba9/README.md#L141-L155) |
| VS Code agent plugin (`chat.plugins.enabled`, off by default) | skills, agents, hooks, MCP servers, and "custom instructions … supplied as plugin rules": no `AGENTS.md` | [`agent-plugins.md`](https://github.com/microsoft/vscode-docs/blob/0b40d48a2f0e/docs/agent-customization/agent-plugins.md#L34-L39) |
| OpenCode plugin | "a JavaScript/TypeScript module that exports one or more plugin functions": hooks, no instruction file | [`plugins.mdx`](https://github.com/anomalyco/opencode/blob/c4601e3d1433/services/site/src/docs/v1/content/plugins.mdx#L69-L70) |

## What follows for `CLAUDE.md` and `GEMINI.md`

**`CLAUDE.md` is deleted.** Claude Code reaches `AGENTS.md` without it: documented, in the changelog, and
measured on 2.1.323. Keeping any `CLAUDE.md`, even a one-line import, has a cost in three other harnesses:
Cursor's CLI and VS Code read it in addition to `AGENTS.md` (as copies, that was the whole file twice), and
Copilot CLI expands an `@AGENTS.md` inside it, which would be `AGENTS.md` twice unless its duplicate removal
catches an expanded import, and its documentation does not say it does.

What deleting it costs, from the same page of Claude Code's documentation ("When AGENTS.md support is
unavailable"): nothing is loaded in Claude Code before v2.1.277, before v2.1.281 on Bedrock or with
telemetry off, in a session where the built-in plugin that reads `AGENTS.md` was disabled, and "in some
cases" in the first session after an upgrade from 2.1.276 or earlier. And a contributor's own
`CLAUDE.local.md` now stops `AGENTS.md` from loading for them, unless they set "Project instructions" to
`claude-md-and-agents-md`. The README states the version.

**`GEMINI.md` becomes the one line `@AGENTS.md`.** Gemini CLI does not reach `AGENTS.md` without it, so it
cannot be deleted. Of the two smallest things that work, the import was chosen over a `context.fileName`
line in `.gemini/settings.json` because the settings file is ignored in an untrusted folder, a workspace
`context.fileName` also changes which file Gemini reads from the user's home directory, and the import is
byte for byte upstream's `GEMINI.md`, so this path no longer differs from upstream. Measured on 0.68.0: the
import is expanded. Its cost: Copilot CLI reads those 11 bytes as text.

## The command that makes each harness list what it loaded

| Harness | Command | Needs an account |
| --- | --- | --- |
| Claude Code | in a session, `/context all`, under "Memory files"; a session that reads `AGENTS.md` also opens with `no CLAUDE.md found; AGENTS.md loaded: <path>`. Without a session: `probe_harness.sh` | the slash command yes, the probe no |
| Codex | `codex debug prompt-input "hi"`, and look for the item of kind `agents_md.instructions` | no |
| Gemini CLI | in a session, `/memory show`. Without: `GEMINI_CLI_TRUST_WORKSPACE=true GEMINI_API_KEY=not-a-key timeout 25 gemini -p "say hi" --debug 2>&1 \| grep MemoryDiscovery` (the `timeout` because, with a key that is not one, it does not return by itself) | the slash command yes, the debug log no |
| Copilot CLI | `copilot instruction list`; in a session, `/instructions` | no |
| Copilot in VS Code | the Chat Debug view ("Debug instruction inclusion" in the custom instructions reference) | yes |
| Cursor | Customize → Rules lists the rules and their status. The documentation names no command for the CLI. | yes |
| OpenCode | none found in 1.19.5 (`opencode debug` has `config`, `skill`, `agent`, `info`, none for instructions) | |
