#!/usr/bin/env python3
"""One-call state of the PAYDAY 2 packs: the environment and every tracked pack.

    make -sC tools/pd2-las status            # one JSON object on stdout
    python3 tools/pd2-las/status.py          # the same; needs no venv
    python3 tools/pd2-las/status.py build    # only the packs a make target builds, or the packs named
    python3 tools/pd2-las/status.py --sha256 # sha256 in full (default: the first 12 digits)

Read-only and stdlib-only, so it runs before the venv exists. It prints what
an agent otherwise spends its first calls finding out, and what the documents
used to quote and get wrong:

- ``ready``: are the required inputs, pinned environment, and intact ZIP pairs
  present? ``hint`` suggests what to do if not. Use ``fresh`` to prove a rebuild.
- ``env``:   is there a ``.venv`` with the pinned versions of ``pins.txt``,
  are the 2B templates unpacked (``extract_2b.TEMPLATES``), are the source
  archives there, and how many tracked files are missing from the checkout (a
  restarted sandbox deletes ``dist/``, ``build/`` and ``node_modules/``).
- ``packs``: per pack in ``dist/`` its size, its sha256, the make target that
  rebuilds it, and ``is``:
    ``tracked``  the zip is byte for byte what git tracks (``ok`` where there is no git to ask)
    ``changed``  the pair matches locally but is new or differs from HEAD
    ``broken``   the zip does not equal its ``.sha256``
    ``missing``  the zip or its ``.sha256`` is not there
  Every builder but lawson's writes the ``.sha256`` itself, so only the
  comparison with the commit says that a rebuild reproduced the tracked bytes.
- ``next``:  the command to run now.

Whether a pack was seen in game is not in a zip: docs/pd2-las/HANDOFF.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import extract_2b  # noqa: E402
from pack_checksum import read_checksum, sha256_file, sidecar_path  # noqa: E402

#: where references/2b.rar is unpacked: the default of every builder's --templates
TEMPLATES = extract_2b.TEMPLATES

#: archives and inputs the builders read (repo-relative)
INPUTS = (
    "references/l4d2_miranda_lawson_1.zip",
    "references/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip",
    "references/Geralt.7z",
    "references/1581859199_135363.rar",
    "references/npc_criminals_ecp_female.7z",
    "references/EYE_Diff.png",
    "references/2b.rar",
    "references/Christie.zip",
    "references/Clover-Christie.zip",
    "references/Ada Wong over Joy.7z",
    "references/Heister - FPS Gloves in TPS 2.zip",
    "references/Honoka/Honoka_DOAXVV_Secret_Reportout.dae",
    "references/Honoka/Tex_07(L_7) 2.dds",
    "references/Honoka/Tex_07(L_7)3.dds",
    "references/Honoka/Tex_23(L_23)2.dds",
    "references/Outfit for Honoka-109-1-1-1628020933.zip",
)

#: LAS outfit builders (both model dialects), independent of native overrides.
LAS_TARGETS = {
    "Miranda_L4D2_LAS": "build",
    "Miranda_L4D2_Busty_LAS": "busty",
    "Miranda_Romance_LAS": "lawson",
    "Christie_LAS": "christie",
    "Christie_Clover_LAS": "cloverchristie",
    "OfficeSuite": "honokodae",
    "OfficeSuite_Head": "honokodae_head",
}
# Native full replacements go here; other *_over_* packs are head-only.
TARGETS = {**LAS_TARGETS, "OfficeSuite_Miranda_Romance_over_Hila": "hila",
           "Miranda_Lawson_VO_over_Hila": "voices"}
HEADS = "heads"

MAKE = "make -sC tools/pd2-las"
ENV = f"{MAKE} env"
GREEN = f"{MAKE} green"
#: the packages whose versions decide the bytes of the built zips
PINNED = ("pillow", "numpy", "imageio-ffmpeg", "py7zr")
#: tracked directories a restarted sandbox comes back without
WIPED = ("dist", "node_modules")


def target(name: str) -> str | None:
    return TARGETS.get(name) or (HEADS if "_over_" in name else None)


def pack_paths(committed: set[str] | None = None) -> dict[str, str]:
    """Discover both halves of each pack, including pairs missing from disk."""
    if committed is None:
        committed = set(git("ls-tree", "-rz", "--name-only", "HEAD", "--", "dist") or [])
    paths = committed | set(git("ls-files", "-z", "--", "dist") or [])
    paths |= {p.relative_to(REPO).as_posix() for p in (REPO / "dist").rglob("*") if p.is_file()}
    zips = {rel.removesuffix(".sha256") for rel in paths if rel.endswith((".zip", ".zip.sha256"))}
    packs = {Path(rel).stem: rel for rel in sorted(zips)}
    return {name: packs[name] for name in [*TARGETS, *sorted(packs.keys() - TARGETS.keys())] if name in packs}


def pack_names() -> list[str]:
    return list(pack_paths())


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
            name = name.lower().replace("_", "-")   # dist-info spells imageio_ffmpeg
            if name in PINNED:
                found[name] = version
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


def pack_status(name: str, rel: str, committed: set[str] | None,
                differs: set[str], full: bool = False) -> dict:
    path = REPO / rel
    out = {"is": "missing", "make": target(name)}
    if not (path.is_file() and sidecar_path(path).is_file()):
        return out
    digest = sha256_file(path)
    try:
        matches = read_checksum(path, REPO) == digest
    except (OSError, ValueError):
        matches = False
    pair = {rel, rel + ".sha256"}
    if not matches:
        state = "broken"
    elif committed is None:
        state = "ok"
    else:
        state = "tracked" if pair <= committed and not pair & differs else "changed"
    return {"is": state, "bytes": path.stat().st_size, "sha256": digest if full else digest[:12], "make": target(name)}


def collect(only: list[str] | None = None, full: bool = False) -> dict:
    head = git("ls-tree", "-rz", "--name-only", "HEAD", "--", "dist")
    changed = git("diff", "-z", "--name-only", "HEAD", "--", "dist")
    committed = None if head is None or changed is None else set(head)
    differs = set(changed or ())
    packs = {name: pack_status(name, rel, committed, differs, full)
             for name, rel in pack_paths(set(head or ())).items()
             if not only or name in only or target(name) in only}
    states = {pack["is"] for pack in packs.values()}

    hint = "git status --short dist" if states & {"missing", "broken"} else None
    if only:
        status = {"packs": packs}
    else:
        want, have = pins(), venv_versions()
        venv = any((REPO / ".venv" / sub).is_file() for sub in ("bin/python", "Scripts/python.exe"))
        gone = git("ls-files", "-z", "--deleted", "--", *WIPED, "references")
        env = {"venv": venv, "pins_ok": venv and all(have.get(k) == v for k, v in want.items()),
               "templates": extract_2b.ready(), "inputs": all((REPO / rel).is_file() for rel in INPUTS),
               "tracked_files_missing": len(gone or [])}
        if venv and not env["pins_ok"]:
            env.update(pinned=want, installed=have)
        if not all(env[key] for key in ("pins_ok", "templates", "inputs")) or env["tracked_files_missing"]:
            hint = ENV
        status = {"ready": hint is None, "hint": hint, "env": env, "packs": packs}
    if "changed" in states and not hint:
        status["note"] = ("changed: new bytes, not committed. Meant: commit the zip with its .sha256. "
                          "Not meant: git checkout -- dist")
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
    status = collect(only or None, full)
    if only and not status["packs"]:
        print(f"status.py: no distribution ZIPs recorded for {', '.join(only)}", file=sys.stderr)
        return 2
    print(render(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
