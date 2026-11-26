#!/usr/bin/env python3
"""Every relative Markdown link in the repository resolves, or this fails.

    python tools/pd2-port/check_links.py            # one line per broken link, exit 1 if any
    python tools/pd2-port/check_links.py --quiet    # the summary only
    python tools/pd2-port/check_links.py --root docs

Documentation is this repository's product: the audits, the handoffs and the decision log are
what an agent reads before it touches a pack, and a link from a capture set to the decision it
is evidence for is the only path between them. The two links that were broken
(`docs/renders/honoka/in-game/officesuite/2026-11-26/README.md`, each one `../` short) had been
sitting there since the capture was archived, because nothing checked.

What counts as a link: `[text](target)` and `![alt](target)` outside code — fenced blocks and
inline spans are stripped first, because a note about decompiled code legitimately contains
`victim["Get Damage"](...)` and `[...](path)` as syntax examples. Absolute URLs, `mailto:`,
anchors and `<...>` templates are skipped; a target with a `#fragment` is checked on its path.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

#: trees that hold no documentation of ours, or are generated
SKIP_DIRS = {".git", ".venv", "node_modules", "build", "dist", ".pytest_cache", "__pycache__", "scratch"}
#: a link target never contains whitespace; `[x](some words)` is prose, not a link
_FENCE = re.compile(r"^```.*?^```", re.M | re.S)
_SPAN = re.compile(r"`[^`\n]*`")
_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SCHEME = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)")


def markdown_files(root: Path) -> list[Path]:
    """Every Markdown file under `root`, tracked or not, outside the generated trees.

    The walk and not `git ls-files`: a document is wrong as soon as it is written, and the
    commit that adds it is exactly when it should be checked, not after.
    """
    return sorted(p for p in root.rglob("*.md") if not SKIP_DIRS.intersection(p.relative_to(root).parts))


def targets(text: str) -> list[str]:
    """The link targets in `text`, with fenced blocks and inline code spans removed."""
    return _LINK.findall(_SPAN.sub("", _FENCE.sub("", text)))


def broken(root: Path) -> list[tuple[Path, str]]:
    bad = []
    for path in markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for target in targets(text):
            if _SCHEME.match(target) or "<" in target or ">" in target:
                continue
            rel = target.split("#", 1)[0].split("?", 1)[0]
            if not rel:
                continue
            resolved = (root / rel.lstrip("/")) if rel.startswith("/") else (path.parent / rel)
            if not resolved.exists():
                bad.append((path.relative_to(root), target))
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=REPO, help="repository root (default: this checkout)")
    ap.add_argument("--quiet", action="store_true", help="the summary only")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    files = markdown_files(root)
    bad = broken(root)
    for path, target in bad:
        print(f"BROKEN {path} -> {target}")
    print(f"{'FAIL' if bad else 'PASS'}: {len(files)} Markdown files, {len(bad)} broken link(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
