#!/usr/bin/env bash
# Rebuild the sandbox environment after an arena wipe: .venv, the 2B templates
# and the calibration fixture. Idempotent and safe to re-run.
#
# The arena sandbox periodically deletes .venv and /tmp. When that happens:
#   * `pytest tests` cannot collect (no pytest),
#   * every test that needs /tmp/2bsrc skips (68 of them),
#   * `tools/pd2-las/glove_check.py` and `diagnose_mesh.py --templates` cannot run.
# This script restores all three. It touches nothing under dist/ or references/.
#
# Usage:
#   bash tools/pd2-las/recover_env.sh          # venv + templates
#   bash tools/pd2-las/recover_env.sh --verify # also run the suite and print counts
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

TEMPLATES="/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
PY="$REPO/.venv/bin/python"

# ---------------------------------------------------------------- 1. the venv
if [ ! -x "$PY" ]; then
    echo "== creating .venv"
    python3 -m venv .venv
    .venv/bin/pip install -q --upgrade pip
else
    echo "== .venv present"
fi

echo "== installing dependencies"
.venv/bin/pip install -q pytest pillow numpy pyyaml pyflakes py7zr scipy
"$PY" -c "import pytest, PIL, numpy, yaml, py7zr, scipy" && echo "   deps ok"

# ------------------------------------------------------------ 2. the templates
# references/2b.rar is a RAR5 archive. There is no system unrar/7z/bsdtar in the
# sandbox, so bootstrap.sh unpacks it with node-unrar-js. NOTE: the extractor
# must run from a *script file*; `node -e` cannot resolve the emscripten wasm
# sidecar (__dirname is empty) and dies with a long stack trace.
if [ -f "$TEMPLATES/2b.model" ]; then
    echo "== 2B templates present"
else
    echo "== extracting references/2b.rar"
    mkdir -p /tmp/rarx /tmp/2bsrc
    cd /tmp/rarx
    [ -d node_modules/node-unrar-js ] || {
        npm init -y >/dev/null 2>&1
        npm install node-unrar-js >/dev/null 2>&1
    }
    cat > /tmp/rarx/extract.js <<'JS'
const { createExtractorFromFile } = require("node-unrar-js");
(async () => {
  const ex = await createExtractorFromFile({
    filepath: process.argv[2],
    targetPath: "/tmp/2bsrc",
  });
  let n = 0;
  for (const f of ex.extract().files) n++;
  console.log("   entries:", n);      // expect 29
})().catch(e => { console.error("FAIL:", e && e.message); process.exit(1); });
JS
    node /tmp/rarx/extract.js "$REPO/references/2b.rar"
    cd "$REPO"
    test -f "$TEMPLATES/2b.model" && echo "   templates ok"
fi

# ------------------------------------------- 3. optional verification
if [ "${1:-}" = "--verify" ]; then
    echo "== suite (expect: 645 passed, 30 skipped)"
    .venv/bin/python -m pytest tests -q --tb=no 2>&1 | tail -n 2
fi

echo "== done"
