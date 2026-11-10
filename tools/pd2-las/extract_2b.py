#!/usr/bin/env python3
"""Extract the 2B reference pack (references/2b.rar) into /tmp/2bsrc.

Used by bootstrap.sh. Written as a file (not `node -e`) because the
node-unrar-js wasm sidecar resolves paths relative to __dirname, which is
empty under `node -e` and the process dies inside emscripten.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAR = REPO / "references" / "2b.rar"
OUT = Path("/tmp/2bsrc")
SCRIPT = Path("/tmp/rarx/extract_2b.js")


def main() -> int:
    if not RAR.is_file():
        print(f"missing {RAR}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    marker = OUT / "2B - LAS" / "assets" / "units" / "2b" / "skins" / "2b" / "2b.model"
    if marker.is_file():
        print("templates already extracted")
        return 0

    SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    SCRIPT.write_text(
        'const { createExtractorFromFile } = require("node-unrar-js");\n'
        "(async () => {\n"
        '  const ex = await createExtractorFromFile({\n'
        '    filepath: process.argv[1], targetPath: "/tmp/2bsrc",\n'
        "  });\n"
        '  let n = 0; for (const f of ex.extract().files) n++;\n'
        '  console.log("extracted entries:", n);\n'
        "})().catch((e) => { console.error(e); process.exit(1); });\n"
    )

    # Ensure node-unrar-js is installed next to the script so __dirname resolves.
    r = subprocess.run(
        ["npm", "init", "-y"],
        cwd=SCRIPT.parent, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return 1
    r = subprocess.run(
        ["npm", "install", "node-unrar-js"],
        cwd=SCRIPT.parent, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return 1

    r = subprocess.run(["node", str(SCRIPT), str(RAR)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return 1
    print(r.stdout.strip())
    if not marker.is_file():
        print("extraction did not produce 2b.model", file=sys.stderr)
        return 1
    print("templates ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
