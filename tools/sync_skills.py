#!/usr/bin/env python3
"""Copy `skills/` to the two places the harnesses look, or report that they differ.

    python tools/sync_skills.py            # skills/ -> .agents/skills, .claude/skills
    python tools/sync_skills.py --check    # exit 1 while a copy differs (CI, tests)

Three copies of the same 34 files exist because Claude Code reads `.claude/skills`, the other
harnesses read `.agents/skills`, and neither reads a symlink reliably on Windows (a checkout
without developer mode gets a text file where the link was). `tests/test_agent_docs.py` fails
while they differ; this script is the one command that makes them agree, and `--check` is what the
test calls, so "how do I fix it" has an answer other than `cp -r`.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
COPIES = [ROOT / ".agents" / "skills", ROOT / ".claude" / "skills"]


def files(root: Path) -> dict[Path, Path]:
    return {p.relative_to(root): p for p in sorted(root.rglob("*")) if p.is_file()}


def differences() -> list[str]:
    """Every relative path that is missing from a copy or differs in content."""
    out = []
    src = files(SOURCE)
    for copy in COPIES:
        dst = files(copy) if copy.is_dir() else {}
        for rel, path in src.items():
            other = dst.get(rel)
            if other is None:
                out.append(f"{copy.relative_to(ROOT)}/{rel}: missing")
            elif not filecmp.cmp(path, other, shallow=False):
                out.append(f"{copy.relative_to(ROOT)}/{rel}: differs")
        for rel in dst.keys() - src.keys():
            out.append(f"{copy.relative_to(ROOT)}/{rel}: not in skills/")
    return out


def sync() -> int:
    for copy in COPIES:
        if copy.exists():
            shutil.rmtree(copy)
        shutil.copytree(SOURCE, copy)
        print(f"copied skills/ -> {copy.relative_to(ROOT)} ({len(files(SOURCE))} files)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report drift instead of copying")
    args = ap.parse_args(argv)
    if args.check:
        bad = differences()
        for line in bad:
            print(f"DIFFERS {line}")
        print(f"{'FAIL' if bad else 'PASS'}: skills/ and its {len(COPIES)} copies")
        return 1 if bad else 0
    return sync()


if __name__ == "__main__":
    raise SystemExit(main())
