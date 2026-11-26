"""No new single file over 25 MB lands in git, because every clone pays for it forever.

The checkout carries ~190 MB of built packs (`dist/`), a ~220 MB source archive set
(`references/`) and ~40 MB of archived renders: 418 MB of `.git` history, no Git LFS. That is a
deliberate trade (the ZIPs are the deliverables; the archives are the only copy of some sources)
recorded in `docs/audits/2026-11-05-repository-mistakes.md`, and it cannot be undone without
rewriting history. What this test stops is the next one: a 60 MB capture or a rebuilt pack
committed without anyone noticing.

If a file really has to be that big, add it to `ALLOWED` with the reason next to it — the point
is that it becomes a decision instead of an accident.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: nothing may exceed this; the largest file today is Clover-Christie.zip at 24 MB
CAP = 25 << 20

#: repo-relative paths allowed past CAP, each with the reason it is there
ALLOWED: dict[str, str] = {}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):  # a tarball checkout: nothing to guard
        return []
    return [ROOT / p for p in out.decode("utf-8", "replace").split("\0") if p]


def test_no_tracked_file_is_over_the_cap():
    files = tracked_files()
    if not files:
        return
    offenders = []
    for path in files:
        if path.as_posix().removeprefix(ROOT.as_posix() + "/") in ALLOWED:
            continue
        try:
            size = os.path.getsize(path)
        except OSError:
            continue  # deleted in the working tree (a restarted sandbox); `status` reports those
        if size > CAP:
            offenders.append(f"{path.relative_to(ROOT).as_posix()} ({size / 2**20:.1f} MB)")
    assert not offenders, (
        f"tracked files over {CAP >> 20} MB: {offenders}\n"
        f"Packs and source archives belong in a release asset or Git LFS, not in the tree; if one "
        f"really must be tracked, add it to ALLOWED in tests/test_repo_weight.py with the reason "
        f"and say so in docs/audits/."
    )


def test_the_allowlist_has_no_stale_entries():
    files = {p.relative_to(ROOT).as_posix() for p in tracked_files()}
    stale = sorted(set(ALLOWED) - files)
    assert not stale, f"ALLOWED names files that are not tracked: {stale}"
