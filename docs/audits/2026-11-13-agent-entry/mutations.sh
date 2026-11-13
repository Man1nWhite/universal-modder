#!/usr/bin/env bash
# Put each defect back, one at a time, and say which test of tests/test_agent_docs.py fails.
#
#   bash docs/audits/2026-11-13-agent-entry/mutations.sh        # from the repository root; needs .venv
#
# It works in a scratch worktree of HEAD, which it removes; this checkout is not touched.
set -u
repo=$(git rev-parse --show-toplevel)
work=$(mktemp -d)/tree
py="$repo/.venv/bin/python"
git -C "$repo" worktree add --detach "$work" HEAD >/dev/null 2>&1 || { echo "git worktree add failed"; exit 1; }
cd "$work" || exit 1
echo "commit: $(git rev-parse --short HEAD)"

run() {  # $1: the defect that was put back
    out=$("$py" -m pytest -q tests/test_agent_docs.py -p no:cacheprovider 2>&1)
    echo "$1"
    echo "    $(echo "$out" | tail -n 1 | sed 's/ in [0-9.]*s//')"
    echo "$out" | grep -E '^FAILED' | sed 's/^FAILED tests\/test_agent_docs.py::/    fails: /; s/ - .*//'
    git checkout -q -- . && git clean -fdq
}

run "nothing changed"

cp AGENTS.md CLAUDE.md
run "1  a CLAUDE.md that is a copy of AGENTS.md"

printf '@AGENTS.md\n' > CLAUDE.md
run "1b a CLAUDE.md that is the one line @AGENTS.md"

size=$(python3 -c "import os; print(f\"{os.path.getsize('dist/Christie_LAS_Slim.zip'):,}\")")
echo "\`dist/Christie_LAS_Slim.zip\` is $size B." >> README.md
run "2  the size of a pack in README.md"

echo "The suite has 800 tests." >> tools/README.md
run "2b a test count in tools/README.md"

printf 'See `tools/pd2-las/no_such_tool.py`.\n' >> tools/pd2-las/README.md
run "3  a path that does not exist, in tools/pd2-las/README.md"

printf 'Run `make -sC tools/pd2-las nosuch`.\n' >> docs/pd2-las/HANDOFF.md
run "3b a make target that does not exist, in HANDOFF.md"

printf 'Kept by `test_that_was_never_written`.\n' >> tools/README.md
run "3c a test that does not exist, in tools/README.md"

python3 -c "open('AGENTS.md', 'a').write('- ' + 'filler ' * 100 + '\n')"
run "4  700 bytes more in AGENTS.md"

printf '      - run: python tools/some_new_check.py\n' >> .github/workflows/test.yml
run "5  a step added to the test workflow that green does not run"

sed -i 's/`slim`, `lawson` (lawson_las)/`slimm`, `lawson` (lawson_las)/' AGENTS.md
git diff --quiet -- AGENTS.md && echo "(6 did not apply: the row of build targets in AGENTS.md reads otherwise now)"
run "6  a build target misspelt in AGENTS.md"

sed -i '/^| State of the 14 packs/d' AGENTS.md
git diff --quiet -- AGENTS.md && echo "(6b did not apply: the status row in AGENTS.md reads otherwise now)"
run "6b the row for status removed from AGENTS.md"

cd "$repo" && git worktree remove --force "$work"
