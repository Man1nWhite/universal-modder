"""No single file (or split-archive set) over 25 MB lands in git, because every clone pays forever.

The checkout carries built packs (`dist/`), a source archive set (`references/`) and archived
renders: roughly 1.8 GB of `.git` on GitHub, no Git LFS. That is a deliberate trade (the ZIPs are
the deliverables; the archives are the only copy of some sources) recorded in
`docs/audits/2026-11-05-repository-mistakes.md`, and it cannot be undone without rewriting history.
What this test stops is the next one: a 60 MB capture or a rebuilt pack committed without anyone
noticing. It does not quote the current figures, which move with every pack build — ask git:

    git ls-tree -r -l HEAD | sort -k4 -n | tail

The sizes come from HEAD, not from the working tree, so a restarted sandbox with missing files
still gets the real answer; a file that is merely staged is caught on the next run after it lands.
A multi-volume archive (`x.7z.001`, `x.7z.002`, ...) is one deliverable and counts as its total.

If a file really has to be that big, add it to `ALLOWED` with the reason next to it — the point
is that it becomes a decision instead of an accident.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: nothing may exceed this once split volumes are summed
CAP = 25 << 20

#: repo-relative paths (or their split-archive stem) allowed past CAP, each with the reason
ALLOWED: dict[str, str] = {
    "references/Marine VO for Rust.7z":
        "split 7z set (.001 + .002) holding the Rust voice lines the VO packs are cut from; "
        "the only copy, and git stores each volume compressed already",
}

#: `name.7z.001` / `name.zip.002` — one archive spread over numbered volumes
_SPLIT = re.compile(r"^(?P<stem>.+\.(?:7z|zip|rar))\.\d{3}$")


def committed_sizes() -> dict[str, int]:
    """Path -> blob size in bytes, read from HEAD; empty when git cannot answer."""
    try:
        out = subprocess.run(
            ["git", "ls-tree", "-r", "-l", "-z", "HEAD"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):  # a tarball checkout: nothing to guard
        return {}
    sizes: dict[str, int] = {}
    for entry in out.decode("utf-8", "surrogateescape").split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if len(fields) < 4 or fields[1] != "blob" or not fields[3].isdigit():
            continue  # a submodule or a symlink: no blob behind it
        sizes[path] = int(fields[3])
    return sizes


def merge_split_volumes(sizes: dict[str, int]) -> dict[str, int]:
    """Sum `x.7z.001`, `x.7z.002`, ... into one entry keyed by the stem."""
    merged: dict[str, int] = {}
    for path, size in sizes.items():
        match = _SPLIT.match(path)
        stem = match.group("stem") if match else path
        merged[stem] = merged.get(stem, 0) + size
    return merged


def test_no_committed_file_or_archive_set_is_over_the_cap():
    sizes = committed_sizes()
    if not sizes:
        return
    offenders = [
        f"{path} ({size / 2**20:.1f} MB)"
        for path, size in sorted(merge_split_volumes(sizes).items())
        if size > CAP and path not in ALLOWED
    ]
    assert not offenders, (
        f"committed files over {CAP >> 20} MB: {offenders}\n"
        f"Packs and source archives belong in a release asset or Git LFS, not in the tree; if one "
        f"really must be tracked, add it to ALLOWED in tests/test_repo_weight.py with the reason "
        f"and say so in docs/audits/."
    )


def test_split_volumes_are_counted_as_one_file():
    merged = merge_split_volumes({"a.7z.001": 10, "a.7z.002": 5, "b.zip": 7, "c.7z.0001": 3})
    assert merged == {"a.7z": 15, "b.zip": 7, "c.7z.0001": 3}


def test_the_allowlist_names_files_that_exist():
    sizes = committed_sizes()
    if not sizes:
        return
    known = set(merge_split_volumes(sizes))
    stale = sorted(set(ALLOWED) - known)
    assert not stale, f"ALLOWED names files that are not committed: {stale}"


def test_every_allowlist_entry_states_a_reason():
    missing = sorted(path for path, reason in ALLOWED.items() if len(reason.strip()) < 20)
    assert not missing, f"ALLOWED entries need a real reason: {missing}"
