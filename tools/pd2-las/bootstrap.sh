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
# pillow/numpy are pinned: the tracked dist/*.zip bytes depend on
# them (tools/pd2-port/STATUS.md §7) — all routes build in this venv.
.venv/bin/pip install -q pytest pillow==13.0.0 numpy==2.4.6 pyyaml pyflakes py7zr lupa scipy
# scipy is a hard dependency of the slim build (_elbow_coverage_correction) and
# of the elbow-depth test, so it belongs here, not in a per-run install.
.venv/bin/python -c "import pytest, PIL, numpy, yaml, py7zr, lupa, scipy" && echo "venv ok"
# Optional: an independent Source-format decoder (GMA/VPK/VTF/MDL). Only used by
# inspect_textures.py's cross-check and by the test that pins it, so a failure
# here is a note, never a broken bootstrap.
.venv/bin/pip install -q sourcepp 2>/dev/null \
    && .venv/bin/python -c "from sourcepp import vpkpp, vtfpp" \
    && echo "sourcepp ok (optional cross-check enabled)" \
    || echo "sourcepp unavailable — inspect_textures.py runs without the cross-check"

echo "== 2/5 extract 2B reference pack (templates) =="
.venv/bin/python tools/pd2-las/extract_2b.py
test -f "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b/2b.model" && echo "templates ok"

echo "== 3/5 build models + packs =="
.venv/bin/python tools/pd2-las/build_models.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
.venv/bin/python tools/pd2-las/build_busty_variant.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
.venv/bin/python tools/pd2-port/build_las_pack.py
sha256sum dist/lawson_las.zip > dist/lawson_las.zip.sha256
.venv/bin/python tools/build_joy_head_mods.py
sha256sum -c build/pd2-las/Miranda_LAS.zip.sha256
sha256sum -c build/pd2-las/Miranda_Busty_LAS.zip.sha256
for sha_file in dist/*.zip.sha256; do
    sha256sum -c "$sha_file"
done

echo "== 4/5 tests =="
.venv/bin/python -m pytest -q tests/

echo "== 5/5 lint =="
.venv/bin/python -m pyflakes tools/pd2-las tools/build_joy_head_mods.py tests/test_pd2_las.py \
    tests/test_build_models.py tests/test_diesel_model.py && echo "pyflakes clean"

echo
echo "bootstrap complete: deliverables in dist/ (lawson_las.zip, Miranda_LAS.zip, Miranda_Busty_LAS.zip, Miranda_L4D2_over_Joy.zip, Miranda_Romance_over_Joy.zip)"
echo "next: docs/pd2-las/in-game-checklist.md (user side) + HANDOFF.md (context)"
