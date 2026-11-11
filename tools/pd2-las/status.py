#!/usr/bin/env python3
"""One-call status of the pd2-las tree: inputs, environment, tracked packs.

    python3 tools/pd2-las/status.py          # one JSON object on stdout
    make -C tools/pd2-las status             # the same, for reading

Read-only and stdlib-only, so it runs before the venv exists. It answers what
an agent otherwise spends its first tool calls finding out:

- ``inputs``:    are the source and reference archives in the checkout?
- ``env``:       is there a ``.venv``, and does it carry the pillow/numpy
                 versions ``bootstrap.sh`` pins? The tracked zips only rebuild
                 byte for byte with those.
- ``templates``: are the 2B templates unpacked where the builders'
                 ``--templates`` default and the tests look for them
                 (``extract_2b.TEMPLATES``, under ``build/pd2-las/2b/``)?
- ``packs``:     per tracked pack - does the zip match its ``.sha256``
                 sidecar, what does its ``BUILD_INFO.json`` say
                 (``models_present``, ``runtime_verified``), and which script
                 in this directory rebuilds it (no arguments needed).

``ready`` is true when the builders can run and reproduce the tracked bytes;
``hint`` is the command that makes it true (``recover_env.sh`` builds the
pinned venv and extracts the templates). The test suite is not run here: that
is ``.venv/bin/python -m pytest -q tests``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import extract_2b  # noqa: E402  (stdlib-only, like this script)

#: where references/2b.rar is unpacked: the default of every builder's --templates
TEMPLATES = extract_2b.TEMPLATES

#: archives the live builders read (repo-relative)
INPUTS = (
    "models/l4d2_miranda_lawson_1.zip",
    "references/Christie.zip",
    "references/2b.rar",
)

#: tracked pack (dist/<name>.zip) -> the builder that writes it, run as
#: `.venv/bin/python tools/pd2-las/<builder>`; the Makefile has a target for each
PACKS = {
    "Miranda_LAS": "build_models.py",
    "Miranda_Busty_LAS": "build_busty_variant.py",
    "Christie_LAS": "build_christie_las.py",
    "Christie_LAS_Slim": "build_christie_las.py --variant slim",
}

#: the packages whose versions decide the bytes of the built zips
PINNED = ("pillow", "numpy")


def pins() -> dict[str, str]:
    """The versions bootstrap.sh installs - the one place they are written."""
    text = (HERE / "bootstrap.sh").read_text(encoding="utf-8")
    return {name: version for name, version in
            re.findall(r"\b(%s)==([0-9][0-9A-Za-z.]*)" % "|".join(PINNED), text)}


def venv_versions() -> dict[str, str]:
    """Installed versions of the pinned packages, read from the venv's metadata."""
    found: dict[str, str] = {}
    for site in list((REPO / ".venv").glob("lib/python*/site-packages")) + [
            REPO / ".venv" / "Lib" / "site-packages"]:
        for info in site.glob("*.dist-info"):
            name, _, version = info.name[:-len(".dist-info")].partition("-")
            if name.lower() in PINNED:
                found[name.lower()] = version
    return found


def pack_status(name: str) -> dict:
    rel = f"dist/{name}.zip"
    path = REPO / rel
    out: dict = {"zip": rel, "present": path.is_file(), "build": PACKS[name]}
    if not out["present"]:
        return out
    out["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    out["sha256_ok"] = (sidecar.is_file()
                        and sidecar.read_text(encoding="utf-8").split()[:1] == [out["sha256"]])
    try:
        with zipfile.ZipFile(path) as zf:
            info = json.loads(zf.read(f"{name}/BUILD_INFO.json"))
    except (KeyError, ValueError, zipfile.BadZipFile):
        info = {}
    for key in ("models_present", "runtime_verified"):
        out[key] = info.get(key)
    return out


def collect() -> dict:
    inputs = {rel: (REPO / rel).is_file() for rel in INPUTS}
    want, have = pins(), venv_versions()
    venv = any((REPO / ".venv" / sub).is_file()
               for sub in ("bin/python", "Scripts/python.exe"))
    env = {"venv": venv, "pinned": want, "installed": have,
           "pins_ok": venv and all(have.get(k) == v for k, v in want.items())}
    templates = {"dir": extract_2b.shown(TEMPLATES), "present": extract_2b.present()}
    packs = {name: pack_status(name) for name in PACKS}

    if not all(inputs.values()):
        hint = "git checkout -- models references"
    elif not (env["pins_ok"] and templates["present"]):
        hint = extract_2b.RECOVER
    elif not all(p["present"] for p in packs.values()):
        hint = "git checkout -- dist build"
    else:
        hint = None
    return {"ready": hint is None, "hint": hint, "inputs": inputs, "env": env,
            "templates": templates, "packs": packs}


def render(status: dict) -> str:
    """Valid JSON, one line per section and per pack: short enough to read whole."""
    lines = []
    for key, value in status.items():
        if key == "packs":
            rows = ",\n".join(f"  {json.dumps(name)}: {json.dumps(pack)}"
                              for name, pack in value.items())
            lines.append(f' "packs": {{\n{rows}\n }}')
        else:
            lines.append(f" {json.dumps(key)}: {json.dumps(value)}")
    return "{\n" + ",\n".join(lines) + "\n}"


def main() -> int:
    print(render(collect()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
