#!/usr/bin/env python3
"""The 2B reference pack: where its templates live, and how they get there.

    python3 tools/pd2-las/extract_2b.py     # idempotent; recover_env.sh runs it

``references/2b.rar`` is unpacked as it is into ``build/pd2-las/2b/`` (gitignored
with the rest of ``build/``). The two models every builder skins onto end up in
``TEMPLATES``:

    build/pd2-las/2b/2B - LAS/assets/units/2b/skins/2b/{2b.model, fps_2b.model}

``TEMPLATES`` is the one definition of that place. The builders' ``--templates``
default, ``status.py``, the diagnostics and the tests all import it from here, so
nothing else spells the path. ``PD2_2B_TEMPLATES`` overrides it, for a worktree or
a second checkout that should share one extraction.

The archive is RAR5 and is unpacked with node-unrar-js, so ``node`` is needed
when the managed cache is missing or stale. The cache records the archive and
all extracted files by SHA-256; changed inputs and partial extractions are
rebuilt in a clean directory.
The repo carries that package at its root (``node_modules/``, tracked), which a
script anywhere below the root resolves; where that copy is missing it is
installed with ``npm`` next to the script. For a manual extraction with any
other RAR5 extractor, point ``PD2_2B_TEMPLATES`` at the resulting unit folder.
An explicit override is not repaired or checked against the managed archive.
The extractor runs from a script
file because under ``node -e`` the wasm sidecar cannot be found (``__dirname`` is
empty) and the process dies inside emscripten.

Stdlib only, so it also runs, and imports, before the venv exists.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import archive_cache

REPO = Path(__file__).resolve().parents[2]
RAR = REPO / "references" / "2b.rar"
#: where the archive is unpacked
OUT = REPO / "build" / "pd2-las" / "2b"
#: the unit directory inside the archive
UNIT = Path("2B - LAS") / "assets" / "units" / "2b" / "skins" / "2b"
TEMPLATE_FILES = ("2b.model", "fps_2b.model")
ENV = "PD2_2B_TEMPLATES"
#: the directory that holds TEMPLATE_FILES
TEMPLATES = Path(os.environ[ENV]).expanduser().resolve() if os.environ.get(ENV) else OUT / UNIT
#: the command that fills TEMPLATES (it also builds the venv)
RECOVER = "bash tools/pd2-las/recover_env.sh"
#: one wording for "the templates are not there": skip reasons, errors, hints
MISSING = f"2B templates not extracted (run `{RECOVER}`)"

_JS = """\
const { createExtractorFromFile } = require("node-unrar-js");
(async () => {
  // argv[0] is node and argv[1] is this script: the archive is argv[2]
  const ex = await createExtractorFromFile({
    filepath: process.argv[2], targetPath: process.argv[3],
  });
  let n = 0; for (const f of ex.extract().files) n++;
  console.log("extracted entries:", n);
})().catch((e) => { console.error(e); process.exit(1); });
"""


def present(directory: Path | None = None) -> bool:
    """True when ``directory`` (default: TEMPLATES) holds both template models."""
    directory = TEMPLATES if directory is None else Path(directory)
    return all((directory / name).is_file() for name in TEMPLATE_FILES)


REQUIRED = (*TEMPLATE_FILES, "base_df.texture", "base_nm.texture")


def managed(directory: Path) -> bool:
    return directory.resolve() == (OUT / UNIT).resolve()


def ready(directory: Path | None = None) -> bool:
    """Check managed templates against the archive; trust an explicit override."""
    directory = TEMPLATES if directory is None else Path(directory)
    if not present(directory):
        return False
    if not managed(directory):
        return True
    return all((directory / name).is_file() for name in REQUIRED) and archive_cache.current(RAR, OUT)


def shown(path: Path) -> str:
    """``path`` relative to the repo when it is inside it, for messages."""
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    print(f"Or unpack {shown(RAR)} with another RAR5 extractor and set {ENV} to its unit folder",
          file=sys.stderr)
    return 1


def _unpack(node: str, output: Path) -> None:
    # The script is inside the repo so require() finds the root's node_modules.
    # Its npm fallback and WASM loader never become part of the cached payload.
    scratch = output.parent / "unrar-js"
    scratch.mkdir()
    script = scratch / "extract_2b.js"
    script.write_text(_JS, encoding="utf-8")
    if not (REPO / "node_modules" / "node-unrar-js" / "package.json").is_file():
        npm = shutil.which("npm")
        if not npm:
            raise ValueError("node-unrar-js is not in the repo's node_modules/ and npm is unavailable")
        (scratch / "package.json").write_text(
            '{"name": "unrar-js-scratch", "private": true}\n', encoding="utf-8")
        result = subprocess.run([npm, "install", "--no-audit", "--no-fund", "node-unrar-js"],
                                cwd=scratch, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"npm could not install node-unrar-js:\n{result.stderr}")
    result = subprocess.run([node, str(script), str(RAR), str(output)], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"node-unrar-js failed:\n{result.stderr}")
    print(result.stdout.strip())


def main() -> int:
    if ready():
        print(f"templates already extracted: {shown(TEMPLATES)}")
        return 0
    if not managed(TEMPLATES):
        print(f"{ENV} points at {TEMPLATES}, which does not hold "
              f"{' and '.join(TEMPLATE_FILES)}; unset it, or unpack {shown(RAR)} there",
              file=sys.stderr)
        return 1
    if not RAR.is_file():
        print(f"missing {shown(RAR)} (restore the tracked reference archive)", file=sys.stderr)
        return 1
    node = shutil.which("node")
    if not node:
        return _fail("node is needed to unpack the archive with node-unrar-js")
    try:
        archive_cache.refresh(RAR, OUT, lambda output: _unpack(node, output),
                              (UNIT / name for name in REQUIRED))
    except (ValueError, OSError) as error:
        return _fail(str(error))
    print(f"templates ok: {shown(TEMPLATES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
