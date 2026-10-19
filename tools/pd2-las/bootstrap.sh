#!/usr/bin/env bash
# One command from a clean checkout (or after a sandbox wipe) to a built pack
# and a green test suite.
#
#   bash tools/pd2-las/bootstrap.sh
#
# Idempotent: safe to re-run. Recovers from the arena sandbox rollbacks that
# wipe .venv, /tmp and build/ while leaving git history on the remote.
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO="$PWD"

echo "== 1/5 venv =="
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
# pillow/numpy are pinned: the tracked dist/lawson_las.zip bytes depend on
# them (tools/pd2-port/STATUS.md §7) — both routes build in this venv.
.venv/bin/pip install -q pytest pillow==13.0.0 numpy==2.4.6 pyyaml pyflakes
.venv/bin/python -c "import pytest, PIL, numpy, yaml" && echo "venv ok"

echo "== 2/5 extract 2B reference pack (templates) =="
mkdir -p /tmp/rarx /tmp/2bsrc
if [ ! -d "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b" ]; then
    cd /tmp/rarx
    [ -d node_modules/node-unrar-js ] || { npm init -y >/dev/null 2>&1; npm install node-unrar-js >/dev/null 2>&1; }
    node -e '
const { createExtractorFromFile } = require("node-unrar-js");
(async () => {
  const extractor = await createExtractorFromFile({
    filepath: process.argv[1], targetPath: "/tmp/2bsrc",
  });
  const files = [...extractor.extract().files];
  console.log("extracted entries:", files.length);
})().catch((e) => { console.error(e); process.exit(1); });' \
        "$REPO/2b.rar"
    cd "$REPO"
fi
test -f "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b/2b.model" && echo "templates ok"

echo "== 3/5 build models + pack =="
.venv/bin/python tools/pd2-las/build_models.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
sha256sum -c build/pd2-las/Miranda_LAS.zip.sha256
sha256sum -c dist/Miranda_LAS.zip.sha256

echo "== 4/5 tests =="
.venv/bin/python -m pytest -q tests/

echo "== 5/5 lint =="
.venv/bin/python -m pyflakes tools/pd2-las tests/test_pd2_las.py \
    tests/test_build_models.py tests/test_diesel_model.py && echo "pyflakes clean"

echo
echo "bootstrap complete: deliverable at Miranda_LAS.zip, dist/Miranda_LAS.zip, and build/pd2-las/Miranda_LAS.zip"
echo "next: docs/pd2-las/in-game-checklist.md (user side) + HANDOFF.md (context)"
