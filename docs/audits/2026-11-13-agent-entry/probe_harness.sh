#!/usr/bin/env bash
# What each harness puts in context for a session started in TREE, asked of the harness itself.
#
#   npm install @anthropic-ai/claude-code @openai/codex @google/gemini-cli @github/copilot   # in any directory
#   bash probe_harness.sh TREE [that directory]/node_modules/.bin
#
# No account is needed. Claude Code and Gemini CLI are given a key that is not one: the model call fails, and
# the loader has run by then. Codex and Copilot CLI have a command for it and make no model call. Each harness
# gets an empty home directory, so nothing of yours is read or written. Cursor and OpenCode are not here:
# Cursor's CLI installs from cursor.com (`curl https://cursor.com/install -fsS | bash`), which the sandbox this
# was written in could not reach, and OpenCode 1.19.5 has no command or log line that names the files it read.
set -u
tree=$(cd "$1" && pwd)
bin=$(cd "${2:-node_modules/.bin}" && pwd)
scratch=$(mktemp -d)
cd "$tree" || exit 1
echo "tree: $(git rev-parse --short HEAD) $(git status --short -- AGENTS.md CLAUDE.md GEMINI.md | tr '\n' ' ')"

echo "== Claude Code $("$bin/claude" --version 2>/dev/null | head -1): the session transcript's \"Contents of\" headers"
HOME="$scratch/claude" ANTHROPIC_API_KEY=sk-ant-not-a-key DISABLE_AUTOUPDATER=1 \
    timeout 30 "$bin/claude" -p "say hi" --debug >/dev/null 2>&1
python3 - "$scratch/claude" "$tree" <<'EOF'
import json, re, sys
from pathlib import Path
home, tree = Path(sys.argv[1]), sys.argv[2]
found = {}
for path in home.rglob("*.jsonl"):
    for line in path.read_text(errors="replace").splitlines():
        for block in re.findall(r"Contents of (\S+) \(([^)]*)\):\\n\\n(.*?)(?=\\n\\nContents of |</system-reminder>|\"\}|$)", line):
            found[block[0].replace(tree + "/", "")] = (block[1], len(json.loads('"' + block[2] + '"').encode()) if block[2] else 0)
for name, (label, size) in found.items():
    print(f"   {name}  ({label})  about {size} B")
if not found:
    print("   no instruction file in the transcript")
EOF

echo "== Codex $("$bin/codex" --version 2>/dev/null): codex debug prompt-input"
CODEX_HOME="$scratch/codex" && mkdir -p "$CODEX_HOME" && export CODEX_HOME
timeout 60 "$bin/codex" debug prompt-input "say hi" 2>/dev/null | python3 -c '
import json, sys
from pathlib import Path
files = {n: Path(n).read_text().strip() for n in ("AGENTS.md", "CLAUDE.md", "GEMINI.md") if Path(n).is_file()}
for item in json.load(sys.stdin):
    kinds = (item.get("internal_chat_message_metadata_passthrough") or {}).get("content_item_kinds") or []
    for kind, part in zip(kinds, item.get("content") or []):
        text = part.get("text", "")
        if kind.startswith(("agents_md", "host_skills")):
            whole = [n for n, body in files.items() if body in text]
            print(f"   {kind}: {len(text.encode())} B" + (f", holds all of {whole[0]}" if whole else ""))
'

echo "== Gemini CLI $("$bin/gemini" --version 2>/dev/null | tail -1): the MemoryDiscovery lines of --debug"
HOME="$scratch/gemini" GEMINI_API_KEY=not-a-key GEMINI_CLI_TRUST_WORKSPACE=true \
    timeout 25 "$bin/gemini" -p "say hi" --debug 2>&1 | grep -a "MemoryDiscovery\]" | grep -a -v "deduplication\|Starting upward\|Loading environment" \
    | sed "s#$tree/##g; s/^\[DEBUG\] \[MemoryDiscovery\]/  /" | sort -u

echo "== Copilot CLI $("$bin/copilot" --version 2>/dev/null | head -1): copilot instruction list"
HOME="$scratch/copilot" timeout 40 "$bin/copilot" instruction list 2>&1 | sed 's/^/   /'
rm -rf "$scratch"
