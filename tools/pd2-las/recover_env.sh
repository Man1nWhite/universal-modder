#!/usr/bin/env bash
# Build the environment of a fresh clone, or rebuild it after a sandbox wipe:
# .venv and the 2B templates. Idempotent and safe to re-run.
#
# The arena sandbox periodically deletes .venv and build/. When that happens:
#   * `pytest tests` cannot collect (no pytest),
#   * every test that needs the 2B templates skips,
#   * the builders, `glove_check.py` and `diagnose_mesh.py --templates` cannot run.
# This script restores all three. It touches nothing under dist/ or references/,
# and writes nothing outside the repo: the templates go to build/pd2-las/2b/.
#
# Usage:
#   bash tools/pd2-las/recover_env.sh          # venv + templates
#   bash tools/pd2-las/recover_env.sh --verify # also run the suite and print counts
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

PY="$REPO/.venv/bin/python"

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
# pillow/numpy carry the same pins as bootstrap.sh (and CI): the tracked zips
# only rebuild byte for byte with these versions. status.py reads the pins from
# bootstrap.sh, and tests/test_pd2_las_status.py keeps the three in step.
"$PY" -m pip install -q pytest pillow==13.0.0 numpy==2.4.6 pyyaml pyflakes py7zr scipy
"$PY" -c "import pytest, PIL, numpy, yaml, py7zr, scipy" && echo "   deps ok"

# ------------------------------------------------------------ 2. the templates
# references/2b.rar (RAR5) -> build/pd2-las/2b/. extract_2b.py owns both the
# location and the unpacking (node-unrar-js; there is no system unrar/7z/bsdtar
# in the sandbox), and does nothing when the templates are already there.
echo "== 2B templates"
"$PY" tools/pd2-las/extract_2b.py | sed 's/^/   /'

# ------------------------------------------- 3. optional verification
if [ "${1:-}" = "--verify" ]; then
    echo "== suite"
    .venv/bin/python -m pytest tests -q --tb=no 2>&1 | tail -n 2
fi

echo "== done"
