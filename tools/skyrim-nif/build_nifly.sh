#!/usr/bin/env bash
# Build the nifly cross-check library: ousnius/nifly + nifly_wrap.cpp -> .so
#
# Why: nifly is the reference NIF implementation behind Outfit Studio and
# PyNifly. Its Python bindings ship as a Windows DLL (NiflyDLL.dll) and the
# wrapper is a Blender add-on, so neither runs in a plain Linux Python. nifly
# itself is dependency-free C++17, so we compile it here and expose a tiny C ABI
# (nifly_wrap.cpp) that nifly_bridge.py loads with ctypes.
#
# Idempotent. Needs git and g++ (no cmake, no Python headers).
#
#   bash tools/skyrim-nif/build_nifly.sh
#   .venv/bin/python tools/skyrim-nif/crosscheck.py
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="$HERE/build"
SRC="$BUILD/nifly-src"
NIFLY_REPO="${NIFLY_REPO:-https://github.com/ousnius/nifly.git}"
NIFLY_REF="${NIFLY_REF:-HEAD}"

mkdir -p "$BUILD"

if [ ! -d "$SRC" ]; then
    echo "== fetching nifly =="
    git clone --depth 1 "$NIFLY_REPO" "$SRC"
else
    echo "== nifly source already at $SRC =="
fi

echo "== compiling libniflywrap.so =="
g++ -std=c++17 -O2 -fPIC -shared \
    -I "$SRC/include" -I "$SRC/external" \
    "$SRC"/src/*.cpp "$HERE/nifly_wrap.cpp" \
    -o "$BUILD/libniflywrap.so"

echo "built $BUILD/libniflywrap.so ($(du -h "$BUILD/libniflywrap.so" | cut -f1))"
echo "nifly revision: $(git -C "$SRC" rev-parse --short "$NIFLY_REF" 2>/dev/null || echo unknown)"
