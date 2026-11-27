"""Every `dist/<group>/<pack>.zip` named by a script or a live doc must be the file that is there.

The packs were renamed and regrouped twice (Honoka → Miranda, Christie and the four unused head
variants retired, `dist/Hila/` folded into `dist/Miranda/`). Each time, prose and code kept the old
spelling: a docstring telling the reader to install `dist/Christie/Christie_LAS.zip`, a preview
script naming a pack that no longer renders, a `--zip` example pointing at a deleted folder.
Nothing caught those because nothing read the literals back against the tree.

This test reads them back. It scans every tracked `.py` and `.md` outside the historical records,
resolves each `dist/...zip` literal through `dist_paths.dist_path()` — the one function that knows
which folder a pack lives in — and asserts the path it computes is the path that was written.

`tests/` is skipped on purpose: those literals are `tmp_path` fixtures (`dist/char/outfit.zip`),
not claims about this checkout.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
from dist_paths import dist_path  # noqa: E402

#: dated records and render provenance describe the tree as it was on their date
HISTORICAL = (
    "docs/audits/",
    "docs/renders/",
    "docs/pd2-las/DECISIONS.md",
    "tools/pd2-las/MODLOG.md",
    "tests/",
)

#: `dist/<group>/<name>.zip`
LITERAL = re.compile(r"dist/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+\.zip)")

#: a scan that suddenly sees almost nothing is broken, not green
MIN_LITERALS = 20


def scanned_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout
        names = [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]
    except (OSError, subprocess.CalledProcessError):  # a tarball checkout
        names = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()]
    return [
        ROOT / name
        for name in names
        if name.endswith((".py", ".md"))
        and not name.startswith(HISTORICAL)
        and ".git/" not in name
    ]


def pack_literals() -> list[tuple[str, str, str]]:
    """(file, literal, pack basename) for every `dist/...zip` mention in a live file."""
    found: list[tuple[str, str, str]] = []
    for path in scanned_files():
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError:
            continue
        for match in LITERAL.finditer(text):
            found.append((rel, match.group(0), match.group(2)))
    return found


def test_the_scan_sees_the_packs():
    literals = pack_literals()
    assert len(literals) >= MIN_LITERALS, (
        f"only {len(literals)} `dist/...zip` literals found; the scanner is broken, not the tree"
    )
    assert len({name for _, _, name in literals}) >= 5, "the scan sees fewer than five distinct packs"


def test_every_named_pack_exists():
    missing = sorted({(rel, lit) for rel, lit, _ in pack_literals() if not (ROOT / lit).is_file()})
    assert not missing, "live files name `dist/` packs that do not exist:\n  " + "\n  ".join(
        f"{rel}: {lit}" for rel, lit in missing
    )


def test_the_written_folder_is_the_one_dist_path_computes():
    wrong = []
    for rel, lit, name in pack_literals():
        try:
            expected = dist_path(ROOT, name)
        except ValueError:
            wrong.append(f"{rel}: {lit} (dist_paths does not know pack {name!r})")
            continue
        if expected != ROOT / lit:
            wrong.append(f"{rel}: {lit} (dist_path puts it at {expected.relative_to(ROOT).as_posix()})")
    assert not wrong, "`dist/` paths disagree with dist_paths.py:\n  " + "\n  ".join(wrong)


def test_a_retired_pack_name_is_rejected_not_invented(tmp_path):
    """A name with no group must raise, so a typo cannot silently create a folder."""
    with pytest.raises(ValueError):
        dist_path(tmp_path, "Christie_LAS.zip")
