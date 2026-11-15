#!/usr/bin/env python3
"""One-call state of the PAYDAY 2 packs: the environment and all 14 tracked packs.

    make -sC tools/pd2-las status            # one JSON object on stdout
    python3 tools/pd2-las/status.py          # the same; needs no venv
    python3 tools/pd2-las/status.py build    # only the packs a make target builds, or the packs named
    python3 tools/pd2-las/status.py --sha256 # sha256 in full (default: the first 12 digits)

Read-only and stdlib-only, so it runs before the venv exists. It prints what
an agent otherwise spends its first calls finding out, and what the documents
used to quote and get wrong:

- ``ready``: can the builders run and reproduce the tracked bytes? ``hint`` is
  the command that makes it true, ``None`` when it is.
- ``env``:   is there a ``.venv`` with the pillow/numpy versions of ``pins.txt``,
  are the 2B templates unpacked (``extract_2b.TEMPLATES``), are the source
  archives there, and how many tracked files are missing from the checkout (a
  restarted sandbox deletes ``dist/``, ``build/`` and ``node_modules/``).
- ``packs``: per pack in ``dist/`` its size, its sha256, the make target that
  rebuilds it, and ``is``:
    ``tracked``  the zip is byte for byte what git tracks (``ok`` where there is no git to ask)
    ``changed``  the zip equals its ``.sha256`` but not the commit: built anew, not committed
    ``broken``   the zip does not equal its ``.sha256``
    ``missing``  the zip or its ``.sha256`` is not there
  Every builder but lawson's writes the ``.sha256`` itself, so only the
  comparison with the commit says that a rebuild reproduced the tracked bytes.
  The two Miranda packs are also tracked under ``build/pd2-las/``; ``is``
  covers both copies.
- ``next``:  the command to run now.

Whether a pack was seen in game is not in a zip: docs/pd2-las/HANDOFF.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import extract_2b  # noqa: E402  (stdlib-only, like this script)

#: where references/2b.rar is unpacked: the default of every builder's --templates
TEMPLATES = extract_2b.TEMPLATES

#: archives the builders read (repo-relative)
INPUTS = (
    "models/l4d2_miranda_lawson_1.zip",
    "models/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip",
    "models/Geralt.7z",
    "references/2b.rar",
    "references/Christie.zip",
    "references/Ada Wong over Joy.7z",
    "references/Heister - FPS Gloves in TPS 2.zip",
)

#: tracked pack (dist/<name>.zip) -> the make target that rebuilds it. The Makefile
#: is where a target's command is written; a head pack is any `<who>_over_<heister>`.
#: The two Christie packs are tracked but are not rebuilt: their builder was deleted
#: on 2026-11-14, so they have no target and `make` is null for them.
TARGETS = {
    "Miranda_LAS": "build",
    "Miranda_Busty_LAS": "busty",
    "lawson_las": "lawson",
}
HEADS = "heads"

MAKE = "make -sC tools/pd2-las"
ENV = f"{MAKE} env"
GREEN = f"{MAKE} green"
#: the packages whose versions decide the bytes of the built zips
PINNED = ("pillow", "numpy")
#: tracked directories a restarted sandbox comes back without
WIPED = ("dist", "build", "node_modules")


def target(name: str) -> str | None:
    return TARGETS.get(name) or (HEADS if "_over_" in name else None)


def pack_names() -> list[str]:
    """Every pack with a sidecar in dist/, the rebuildable LAS packs first, as the make targets list them."""
    found = {path.name[: -len(".zip.sha256")] for path in (REPO / "dist").glob("*.zip.sha256")}
    return [name for name in TARGETS if name in found] + sorted(found - set(TARGETS))


def pins() -> dict[str, str]:
    """The pinned versions, from pins.txt - the one place they are written."""
    text = (HERE / "pins.txt").read_text(encoding="utf-8")
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


def git(*args: str) -> list[str] | None:
    """Paths git prints for this checkout, or None where REPO is not the top of a git work tree."""
    exe = shutil.which("git")
    if not exe:
        return None
    try:
        top = subprocess.run([exe, "-C", str(REPO), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != REPO.resolve():
            return None
        out = subprocess.run([exe, "-C", str(REPO), *args], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [raw.decode("utf-8", "surrogateescape") for raw in out.split(b"\0") if raw]


def pack_status(name: str, differs: set[str] | None, full: bool = False) -> dict:
    """`differs`: the tracked paths under dist/ and build/ that are not what the commit holds; None without git."""
    zips = [f"dist/{name}.zip"]
    if (REPO / f"build/pd2-las/{name}.zip.sha256").is_file():
        zips.append(f"build/pd2-las/{name}.zip")
    out: dict = {"is": "missing", "make": target(name)}
    digests = []
    for rel in zips:
        path, sidecar = REPO / rel, REPO / (rel + ".sha256")
        if not (path.is_file() and sidecar.is_file()):
            return out
        digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
        if sidecar.read_text(encoding="utf-8").split()[:1] != digests[-1:]:
            out["is"] = "broken"
    if out["is"] != "broken":
        paths = {rel for rel in zips} | {rel + ".sha256" for rel in zips}
        out["is"] = "ok" if differs is None else "changed" if paths & differs else "tracked"
    out["bytes"] = (REPO / zips[0]).stat().st_size
    out["sha256"] = digests[0] if full else digests[0][:12]
    return {key: out[key] for key in ("is", "bytes", "sha256", "make")}


def collect(only: list[str] | None = None, full: bool = False) -> dict:
    want, have = pins(), venv_versions()
    venv = any((REPO / ".venv" / sub).is_file() for sub in ("bin/python", "Scripts/python.exe"))
    gone = git("ls-files", "-z", "--deleted", "--", *WIPED, "models", "references")
    env = {"venv": venv, "pins_ok": venv and all(have.get(k) == v for k, v in want.items()),
           "templates": extract_2b.present(), "inputs": all((REPO / rel).is_file() for rel in INPUTS),
           "tracked_files_missing": len(gone or [])}
    if venv and not env["pins_ok"]:
        env.update(pinned=want, installed=have)
    changed = git("diff", "-z", "--name-only", "HEAD", "--", "dist", "build")
    differs = None if changed is None else set(changed)
    names = pack_names()
    if only:
        names = [name for name in names if name in only or target(name) in only]
    packs = {name: pack_status(name, differs, full) for name in names}
    states = {pack["is"] for pack in packs.values()}

    hint = "git status --short dist build" if states & {"missing", "broken"} else None
    if only:
        status = {"packs": packs}
    else:
        if not all(env[key] for key in ("pins_ok", "templates", "inputs")) or env["tracked_files_missing"]:
            hint = ENV
        status = {"ready": hint is None, "hint": hint, "env": env, "packs": packs}
    if "changed" in states and not hint:
        status["note"] = ("changed: new bytes, not committed. Meant: commit the zip with its .sha256. "
                          "Not meant: git checkout -- dist build")
    status["next"] = hint or GREEN
    return status


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


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    full = "--sha256" in args
    only = [arg for arg in args if arg != "--sha256"]
    known = set(pack_names()) | set(TARGETS.values()) | {HEADS}
    if set(only) - known:
        print(f"status.py: not a pack or a make target that builds one: {sorted(set(only) - known)}", file=sys.stderr)
        return 2
    print(render(collect(only or None, full)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
