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

# The release of lawson_las was deleted on 2026-11-13 with its notes: the tree says "There is no release".
tracked=$(cut -d' ' -f1 dist/lawson_las.zip.sha256)
notes() {  # $1: the release number; $2: the sha256 the notes give
    mkdir -p tools/pd2-port/releases
    printf '<!-- pack_version: 0.1.2 -->\n\n**sha256:** `%s`\n' "$2" > "tools/pd2-port/releases/lawson-las-v$1.md"
}
record() {  # what STATUS.md says in place of "There is no release."
    sed -i "s/^\*\*There is no release\.\*\*/$1/" tools/pd2-port/STATUS.md
}

sed -i 's/^\*\*There is no release\.\*\* /The pack is tracked. /' tools/pd2-port/STATUS.md
git diff --quiet -- tools/pd2-port/STATUS.md && echo "(8 did not apply: STATUS.md says otherwise that there is no release)"
run "8  no release notes, and STATUS.md does not say that there is no release" "$status_test"

notes 3 "$tracked"
run "8b release notes for v3 with the tracked sha256, STATUS.md not touched" "$status_test"

notes 3 0000000000000000000000000000000000000000000000000000000000000000
record '**The tracked pack is not the pack the release serves.** `lawson-las-v3`, `00000000…`.'
run "8c a release of another build, recorded in STATUS.md, not in the open work of tools/pd2-las/README.md" "$status_test"

notes 3 "$tracked"
record "\`lawson-las-v3\` serves the tracked pack, \`$(echo "$tracked" | cut -c1-8)…\`."
sed -i 's/^   the head packs have no checklist\.$/   the head packs have no checklist. The last release of `lawson_las` serves an older build than the tracked pack./' tools/pd2-las/README.md
git diff --quiet -- tools/pd2-las/README.md && echo "(8d did not apply: the open item in tools/pd2-las/README.md reads otherwise now)"
run "8d a release that serves the tracked pack, recorded in STATUS.md, still listed as open work" "$status_test"

notes 2 "$tracked"
run "8e release notes under a number that was used, v2" "tests/test_las_pack.py::test_a_release_number_is_not_used_twice"

notes 3 "$tracked"
record "\`lawson-las-v3\` serves the tracked pack, \`$(echo "$tracked" | cut -c1-8)…\`."
run "8f the same release recorded as it should be: this one passes" "$status_test" \
    "tests/test_las_pack.py::test_a_release_number_is_not_used_twice" \
    "tests/test_las_pack.py::test_the_builder_version_matches_the_latest_release_notes"

size=$(python3 -c "import os; print(f\"{os.path.getsize('dist/lawson_las.zip'):,}\")")
echo "The tracked pack is $size B." >> tools/pd2-port/STATUS.md
run "9  the tracked size of lawson_las in STATUS.md"

echo "sha256 \`$tracked\`" >> tools/pd2-port/STATUS.md
run "9b the tracked sha256 of lawson_las in STATUS.md"

echo "The audit: 38 pass, 1 warn, 0 fail." >> tools/pd2-port/STATUS.md
run "9c the audit's result in STATUS.md"

echo "16/16 mutations are caught." >> tools/pd2-port/README.md
run "9d a count of mutations in tools/pd2-port/README.md"

echo "91/91 checks." >> tools/README.md
run "9e a count of checks in tools/README.md"

printf 'Run `retarget_all.py` first.\n' >> tools/pd2-port/README.md
run "10 a script that does not exist, in tools/pd2-port/README.md"

echo
echo "what was deleted on 2026-11-13 stays out, and the tests that were kept still catch their defect"

sleeves="tests/test_build_models.py::test_extend_sleeves_moves_no_material_that_is_not_named"
run "nothing changed" tests/test_agent_docs.py tests/test_pd2_las_status.py tests/test_skip_budget.py \
    tests/test_las_outfit_pack.py tests/test_glove_adapter.py "$sleeves"

printf '| `build_skyrim_outfit.py`, `skin_texture.py` | Skyrim outfit route: cancelled |\n' >> tools/pd2-las/README.md
run "11 a row for the deleted Skyrim tools in tools/pd2-las/README.md" tests/test_agent_docs.py tests/test_pd2_las_status.py

sed -i 's/^    "needs ffmpeg": 4,$/    "needs ffmpeg": 4,\n    "nifly not built": 2,/' tools/pd2-port/check_skip_budget.py
git diff --quiet -- tools/pd2-port/check_skip_budget.py && echo "(12 did not apply: the budget in check_skip_budget.py reads otherwise now)"
run "12 a skip budget for a reason no test skips with" tests/test_skip_budget.py

sed -i 's/^\\tps.glove_adapter = {{}}$/\\tps.glove_adapter = true/' tools/pd2-las/las_outfit_pack.py
git diff --quiet -- tools/pd2-las/las_outfit_pack.py && echo "(13 did not apply: the adapter line in las_outfit_pack.py reads otherwise now)"
run "13 the glove adapter enabled with a boolean, in the generator" tests/test_glove_adapter.py

sed -i 's|<unit_mat path="{u}"/>|<unit_mat path="{u.rsplit(\"/\", 1)[0]}"/>|' tools/pd2-las/las_outfit_pack.py
git diff --quiet -- tools/pd2-las/las_outfit_pack.py && echo "(13b did not apply: the unit_mat line in las_outfit_pack.py reads otherwise now)"
run "13b a unit path without its file stem in main.xml" tests/test_las_outfit_pack.py

sed -i 's|<df_nm path="{base}"/>|<df_nm path="{base}_df"/>|' tools/pd2-las/las_outfit_pack.py
git diff --quiet -- tools/pd2-las/las_outfit_pack.py && echo "(13c did not apply: the df_nm line in las_outfit_pack.py reads otherwise now)"
run "13c a texture pair named with its _df suffix in main.xml" tests/test_las_outfit_pack.py

sed -i 's/^    targets = dict(mats)$/    targets = {"jacket": -2.5, "skin": -2.2, **mats}/' tools/pd2-las/build_models.py
git diff --quiet -- tools/pd2-las/build_models.py && echo "(14 did not apply: extend_sleeves_to_wrist reads otherwise now)"
run "14 default sleeve targets for the materials of the cancelled outfit, back in extend_sleeves_to_wrist" "$sleeves"

sed -i 's|^    files\[f"{ROOT_DIR}/main.xml"\] = main_xml().encode()$|&\n    files[f"{ROOT_DIR}/CREDITS.txt"] = b"credits"|' tools/pd2-port/build_las_pack.py
git diff --quiet -- tools/pd2-port/build_las_pack.py && echo "(15 did not apply: assemble in build_las_pack.py reads otherwise now)"
run "15 a credits file written into lawson_las again" "tests/test_las_pack.py::TestSourceIntegration::test_pack_layout_matches_2b_contract"

cd "$repo" && git worktree remove --force "$work"
