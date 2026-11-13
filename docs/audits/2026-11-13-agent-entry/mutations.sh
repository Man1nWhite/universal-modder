#!/usr/bin/env bash
# Put each defect back, one at a time, and say which test fails: of tests/test_agent_docs.py, or of
# the file named in the case.
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

run() {  # $1: the defect that was put back; $2...: what to give pytest (default: tests/test_agent_docs.py)
    what=$1; shift
    [ $# -eq 0 ] && set -- tests/test_agent_docs.py
    out=$("$py" -m pytest -q "$@" -p no:cacheprovider 2>&1)
    echo "$what"
    echo "    $(echo "$out" | tail -n 1 | sed 's/ in [0-9.]*s//')"
    echo "$out" | grep -E '^FAILED' | sed 's/^FAILED tests\/test_[a-z0-9_]*\.py::/    fails: /; s/ - .*//'
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

echo
echo "the tests of the fixes of 2026-11-13"

status_test="tests/test_las_pack.py::test_the_status_page_says_whether_the_release_serves_the_tracked_pack"
run "nothing changed" tests/test_agent_docs.py tests/test_pd2_las_status.py "$status_test"

sed -i 's/ pytest scipy$/ pytest/' .github/workflows/lawson-las.yml
git diff --quiet -- .github/workflows/lawson-las.yml && echo "(7 did not apply: the install line of lawson-las.yml reads otherwise now)"
run "7  scipy taken out of what the lawson workflow installs" tests/test_pd2_las_status.py

sed -i 's/^\*\*The tracked pack is not the pack the release serves\.\*\*$/**The tracked pack is what the release serves.**/' tools/pd2-port/STATUS.md
git diff --quiet -- tools/pd2-port/STATUS.md && echo "(8 did not apply: STATUS.md says the release serves the tracked pack, or says it otherwise)"
run "8  STATUS.md says the release serves the tracked pack" "$status_test"

newest=$(ls tools/pd2-port/releases/lawson-las-v*.md | sort -V | tail -n 1)
number=$(echo "$newest" | sed 's/.*-v\([0-9]*\)\.md/\1/')
released=$(grep -o 'sha256:\*\*[^`]*`[0-9a-f]\{64\}' "$newest" | grep -o '[0-9a-f]\{64\}$')
tracked=$(cut -d' ' -f1 dist/lawson_las.zip.sha256)
sed "s/$released/$tracked/" "$newest" > "tools/pd2-port/releases/lawson-las-v$((number + 1)).md"
run "8b release notes for v$((number + 1)) with the tracked sha256, STATUS.md not touched" "$status_test"

sed -i 's/ The last release of `lawson_las` serves an older build than the tracked pack (`tools\/pd2-port\/STATUS.md`)\.//' tools/pd2-las/README.md
git diff --quiet -- tools/pd2-las/README.md && echo "(8c did not apply: the open item in tools/pd2-las/README.md reads otherwise now)"
run "8c the release taken out of the open work in tools/pd2-las/README.md while it is behind" "$status_test"

sed "s/$released/$tracked/" "$newest" > "tools/pd2-port/releases/lawson-las-v$((number + 1)).md"
sed -i "s/^\*\*The tracked pack is not the pack the release serves\.\*\*$/**The tracked pack is what the release serves.** \`lawson-las-v$((number + 1))\`, \`$(echo "$tracked" | cut -c1-8)…\`/" tools/pd2-port/STATUS.md
run "8d a release that serves the tracked pack, recorded in STATUS.md, still listed as open work" "$status_test"

size=$(python3 -c "import os; print(f\"{os.path.getsize('dist/lawson_las.zip'):,}\")")
echo "The tracked pack is $size B." >> tools/pd2-port/STATUS.md
run "9  the tracked size of lawson_las in STATUS.md"

echo "sha256 \`$tracked\`" >> tools/pd2-port/STATUS.md
run "9b the tracked sha256 of lawson_las in STATUS.md"

echo "The audit: 38 pass, 1 warn, 0 fail." >> tools/pd2-port/STATUS.md
run "9c the audit's result in STATUS.md"

echo "16/16 mutations are caught." >> tools/pd2-port/README.md
run "9d a count of mutations in tools/pd2-port/README.md"

echo "91/91 checks." >> tools/skyrim-nif/README.md
run "9e a count of checks in tools/skyrim-nif/README.md"

printf 'Run `retarget_all.py` first.\n' >> tools/skyrim-nif/README.md
run "10 a script that does not exist, in tools/skyrim-nif/README.md"

cd "$repo" && git worktree remove --force "$work"
