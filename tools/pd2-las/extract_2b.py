#!/usr/bin/env python3
"""The 2B reference pack (`references/templates/2b.rar`) and the two models cut out of it.

The 2B archive is a working Legendary Armour Skins pack: it defines the pack shape
and supplies the 136-bone Diesel `.model` skeleton every builder in `tools/pd2-las/`
skins onto. A builder wants two files out of it:

    references/templates/2b/2b.model        the third-person template
    references/templates/2b/fps_2b.model    the first-person template

They are tracked, so a clone needs no unpacking step and no unpacker. (Until
2026-11-27 they were extracted from the RAR5 archive on every fresh clone with
`node-unrar-js`, which meant node, npm and a pinned npm package stood between a
clone and the first build. D89.) The archive is still the provenance record for
the pack shape - `main.xml`, the hook, the material configs, the `ss.model`
sidecar, its two textures - and is kept.

    python3 tools/pd2-las/extract_2b.py          # idempotent; verifies the tracked models
    python3 tools/pd2-las/extract_2b.py --check  # exit 1 when a tracked model is missing or stale

The tracked models are the archive's bytes, verbatim. `recover_env.sh` used to
unpack them into `build/pd2-las/2b/`; if that cache is still there and matches,
nothing is rewritten. The rest of the archive can still be unpacked by hand with
any RAR5 tool: `unrar x references/templates/2b.rar build/pd2-las/2b/`, then point
`PD2_2B_TEMPLATES` at `build/pd2-las/2b/2B - LAS/assets/units/2b/skins/2b` if a
diagnostic wants the textures or the sidecar.

Stdlib only, so it also runs, and imports, before the venv exists.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
#: the reference archive, kept for the pack shape and for provenance
RAR = REPO / "references" / "templates" / "2b.rar"
#: where the two tracked template models live; this is the builders' default --templates
TEMPLATES = REPO / "references" / "templates" / "2b"
#: where a hand unpack of the whole archive goes (gitignored): unit folder, for the
#: diagnostics that want the 2B textures or the `ss.model` sidecar beside the models
OUT = REPO / "build" / "pd2-las" / "2b"
UNIT = Path("2B - LAS") / "assets" / "units" / "2b" / "skins" / "2b"
TEMPLATE_FILES = ("2b.model", "fps_2b.model")
#: the tracked models' sha256, as cut from the archive (2026-11-27). A tracked file that no
#: longer hashes to this is not the archive's model: it was edited or truncated.
SHA256 = {
    "2b.model": "f2d09f97b2075a802b6b43f5673a42f398e40abfce8b83e2bdf0cb48fd4cbaba",
    "fps_2b.model": "7de45adb192221a9c1961ebdd9e43fdb05c5fc313010942f1bcc7cf21d7b6313",
}
#: still honoured by the diagnostics that want the whole unpacked unit (textures, sidecar)
ENV = "PD2_2B_TEMPLATES"
#: the command that restores a checkout's missing files
RECOVER = "bash tools/pd2-las/recover_env.sh"
#: one wording for "the templates are not there": skip reasons, errors, hints
MISSING = (f"2B template models are missing from {TEMPLATES.relative_to(REPO).as_posix()} "
           f"(restore the tracked files: `git checkout -- {TEMPLATES.relative_to(REPO).as_posix()}`)")


def present(directory: Path | None = None) -> bool:
    """True when ``directory`` (default: TEMPLATES) holds both template models."""
    directory = TEMPLATES if directory is None else Path(directory)
    return all((directory / name).is_file() for name in TEMPLATE_FILES)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ready(directory: Path | None = None) -> bool:
    """The tracked models are there and are the archive's models, byte for byte."""
    directory = TEMPLATES if directory is None else Path(directory)
    if not present(directory):
        return False
    if Path(directory).resolve() != TEMPLATES.resolve():
        return True                     # an explicit override is the caller's business
    return all(sha256_file(directory / name) == SHA256[name] for name in TEMPLATE_FILES)


def shown(path: Path) -> str:
    """``path`` relative to the repo when it is inside it, for messages."""
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def describe(directory: Path | None = None) -> str:
    """The state of the tracked templates in one line, for `status` and error messages."""
    directory = TEMPLATES if directory is None else Path(directory)
    missing = [name for name in TEMPLATE_FILES if not (directory / name).is_file()]
    if missing:
        return f"missing: {', '.join(missing)}"
    stale = [name for name in TEMPLATE_FILES if sha256_file(directory / name) != SHA256[name]]
    if stale:
        return f"not the archive's bytes: {', '.join(stale)} (restore them from git)"
    return "ok"


#: the node script that writes one member out of the archive; kept inside the checkout so
#: `require("node-unrar-js")` finds the repo's own `node_modules/` (package.json)
_JS = """\
const { createExtractorFromFile } = require("node-unrar-js");
(async () => {
  // argv[0] is node and argv[1] is this script: the archive is argv[2], the target argv[3],
  // the member's suffix argv[4]
  const ex = await createExtractorFromFile({ filepath: process.argv[2], targetPath: process.argv[3] });
  const wanted = [];
  for (const h of ex.getFileList().fileHeaders) {
    if (h.name.replace(/\\\\/g, "/").endsWith(process.argv[4])) wanted.push(h.name);
  }
  if (!wanted.length) throw new Error(process.argv[4] + " is not in the archive");
  const out = ex.extract({ files: wanted });
  for (const written of out.files) console.log(written.fileHeader.name);   // lazy: this writes it
})().catch((e) => { console.error(String(e)); process.exit(1); });
"""


def read_member(suffix: str) -> bytes:
    """One file out of `references/templates/2b.rar`, by the end of its path.

    The two `.model` templates are tracked, but the rest of the pack - its textures, its
    `ss.model` sidecar, the manifest - is still only in the archive, and a diagnostic
    (`uv_check.py`) reads `base_df.texture` from it. RAR5 needs an unpacker, so this goes
    through node-unrar-js in the repo's `node_modules/`; the scratch folder is under
    `build/`, inside the checkout, because `require()` resolves from the script's own folder.
    """
    if not RAR.is_file():
        raise FileNotFoundError(f"{shown(RAR)} is not in the tree")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is needed to read a member out of the RAR5 archive (node-unrar-js)")
    build = REPO / "build"
    build.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="2b-member-", dir=build))
    script = scratch / "extract_2b_member.js"
    script.write_text(_JS, encoding="utf-8")
    subprocess.run([node, str(script), str(RAR), str(scratch), suffix], check=True,
                   capture_output=True, cwd=REPO)
    found = sorted(p for p in scratch.rglob("*") if p.is_file() and p != script)
    if not found:
        raise FileNotFoundError(f"{suffix} was not written out of {shown(RAR)}")
    return found[0].read_bytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when a tracked model is missing or is not the archive's bytes")
    args = parser.parse_args(argv)
    state = describe()
    if args.check and state != "ok":
        print(f"2B templates: {state}", file=sys.stderr)
        return 1
    print(f"2B templates ({shown(TEMPLATES)}): {state}")
    if not RAR.is_file():
        print(f"note: {shown(RAR)} is not in the tree; it is the pack shape's reference, not a build input",
              file=sys.stderr)
    return 0 if ready() else 1


if __name__ == "__main__":
    raise SystemExit(main())
