#!/usr/bin/env bash
# Build the environment of a fresh clone, or rebuild it after a sandbox restart:
# the tracked files the restart deleted, .venv and the 2B template models. Then print
# the state (status.py). Idempotent and safe to re-run. It is the one script that
# does this: `make -sC tools/pd2-las env` runs it, and so does CI.
#
# A restarted sandbox comes back without .venv and without anything under dist/,
# build/ and node_modules/, tracked files included. When that happens:
#   * `git status` lists the packs as deleted,
#   * `pytest tests` cannot collect (no pytest),
#   * every test that needs the 2B template models skips,
#   * the builders and `diagnose_mesh.py --templates` cannot run.
# This script restores all of it. Under dist/, build/ and node_modules/ it only
# puts back tracked files that are missing: a file that is there, changed or not,
# is left as it is. It writes nothing outside the repo: the templates go to
# build/pd2-las/2b/.
#
# Usage:
#   bash tools/pd2-las/recover_env.sh           # venv + templates
#   bash tools/pd2-las/recover_env.sh --extras  # also lupa and sourcepp: the tests that need them skip without
#   bash tools/pd2-las/recover_env.sh --verify  # also run the suite and print counts
set -euo pipefail

EXTRAS=0
VERIFY=0
for arg in "$@"; do
    case "$arg" in
        --extras) EXTRAS=1 ;;
        --verify) VERIFY=1 ;;
        *) echo "recover_env.sh: unknown option $arg (it takes --extras and --verify)" >&2; exit 2 ;;
    esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

PY="$REPO/.venv/bin/python"

# The pinned NumPy and Pillow builds require Python 3.11+. The general CLI still
# supports 3.10 with compatible dependency versions; check the actual interpreter
# used here before restoring files or installing anything.
if [ -x "$PY" ]; then
    CHECK_PY="$PY"
else
    CHECK_PY="$(command -v python3 || true)"
fi
if [ -z "$CHECK_PY" ] || ! "$CHECK_PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    echo "recover_env.sh: the pinned PAYDAY 2 build environment needs Python 3.11 or newer; install it and recreate .venv if needed" >&2
    exit 1
fi

# ------------------------------------------- 0. tracked files that are missing
# `git checkout -- dist node_modules` would also throw away a pack that was
# rebuilt and not committed. This names the deleted files and restores only those.
if git rev-parse --show-toplevel >/dev/null 2>&1; then
    MISSING="$(git ls-files --deleted -- dist node_modules | wc -l | tr -d ' ')"
    if [ "$MISSING" != 0 ]; then
        echo "== restoring $MISSING tracked files missing from dist/ and node_modules/"
        git ls-files -z --deleted -- dist node_modules | xargs -0 git checkout --
    fi
fi

# ---------------------------------------------------------------- 1. the venv
# A .venv counts only if it has pip. `uv run` makes one without (bin/um goes
# through uv when uv is installed, and the CI job installs it), on whichever
# interpreter uv picked: that one is started again from python3.
if [ -x "$PY" ] && "$PY" -m pip --version >/dev/null 2>&1; then
    echo "== .venv present"
else
    echo "== creating .venv"
    python3 -m venv --clear .venv
    "$PY" -m pip install -q --upgrade pip
fi

echo "== installing dependencies"
# The versions of the pinned packages are in pins.txt, the one place they are
# written: the tracked zips only rebuild byte for byte with them. Both CI
# workflows install with the same file, and status.py reads it.
"$PY" -m pip install -q -c tools/pd2-las/pins.txt pytest pytest-cov hypothesis pillow numpy pyyaml ruff mypy py7zr imageio-ffmpeg openpyxl python-docx pypdf
"$PY" -c "import pytest, hypothesis, PIL, numpy, yaml, py7zr" && echo "   deps ok"
if [ "$EXTRAS" = 1 ]; then
    # Not needed to build. lupa runs the Lua of the hook and of the glove adapter
    # in tests/test_glove_behavior_lua.py; sourcepp is a reader of Source files
    # written elsewhere, for the cross-checks of inspect_textures.py. The tests
    # that need them skip without them, here and in CI.
    "$PY" -m pip install -q lupa && "$PY" -c "import lupa" && echo "   lupa ok"
    "$PY" -m pip install -q sourcepp 2>/dev/null \
        && "$PY" -c "from sourcepp import vpkpp, vtfpp" \
        && echo "   sourcepp ok" \
        || echo "   sourcepp unavailable: the tests that cross-check with it skip"
fi

# ------------------------------------------------------------ 2. the templates
# references/templates/2b/{2b,fps_2b}.model are tracked since 2026-11-27 (D88): no unpacking
# step, no node, no npm package between a clone and its first build. extract_2b.py still owns
# the path and checks the models are the archive's bytes; this reports it and restores nothing.
echo "== 2B templates"
"$PY" tools/pd2-las/extract_2b.py --check | sed 's/^/   /'

# ------------------------------------------- 3. optional verification
if [ "$VERIFY" = 1 ]; then
    echo "== suite"
    .venv/bin/python -m pytest tests -q --tb=no 2>&1 | tail -n 2
fi

echo "== done; the state:"
python3 tools/pd2-las/status.py
