#!/usr/bin/env python3
"""Skip budget: every `pytest.skip` reason must be known and within its count.

An unconditional `pytest.skip` inside a helper
turns off many tests with one line. This makes the budget explicit: each known
skip reason has a maximum count, and any new reason or growth fails.

Run from the repo root:
    .venv/bin/python tools/pd2-port/check_skip_budget.py
    .venv/bin/python tools/pd2-port/check_skip_budget.py --report FILE

The tool runs `pytest -rsxX` itself, groups skip reasons by prefix match against
`ALLOWED`, and multiplies by the `[N]` repeat count shown by `-rs`. A reason
not starting with any ALLOWED key, or one exceeding its count, is a failure.
With `--report` it judges a saved `pytest -q -rsxX tests` report instead:
`check_all.py --full` hands it the report of the suite it has just run, so the
suite runs once there and not twice.

Reasons for fixtures that are present in this checkout (e.g. the extracted 2B
templates) are listed at count 0 so that their reappearance — a regression to
a 59-skip state — fails immediately.

Expected failures are budgeted the same way. An `xfail` marker switches off the
verdict of a test that still runs, so one line can hide a defect just as a skip
can: each test allowed to fail is named in `ALLOWED_XFAIL` with a maximum count,
and an expected failure anywhere else fails. A marked test that passes (XPASS)
counts too: its marker is still there.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = sys.executable

#: Maximum acceptable count per skip reason, measured on HEAD with the
#: 2B fixture extracted (P1a). Keys are prefixes of the skip reason text.
#: The 2B reasons are at 0: the fixture is present, so any skip citing them
#: is a regression.
ALLOWED: dict[str, int] = {
    # Present-by-design skips (fixtures absent by design, not regressed):
    "needs ffmpeg": 4,
    "sourcepp is an optional extra": 2,
    "lupa (LuaJIT) not installed": 1,
    "Git Bash / MSYS only": 1,
    # Regression to watch for: the fixture is extracted, so this must be 0. Every
    # test that needs the 2B templates skips with tools/pd2-las/extract_2b.MISSING,
    # which starts with this prefix; any other wording is unbudgeted and fails too.
    "2B templates not extracted": 0,
}

#: Maximum number of expected failures (xfail) per test, by node-id prefix.
#: These are known defects that are recorded where the marker is, not tests
#: that somebody wanted out of the way. Empty since 2026-11-13: the two slim
#: sleeve cases (KNOWN_SLEEVE_LEAK_CM2, once in tests/test_christie_las.py)
#: closed when the slit bridge stopped being dropped by _insert_faces; there
#: is no expected failure left.
ALLOWED_XFAIL: dict[str, int] = {}

#: Not judged. Its one skip reason, a checkout without the Christie pack, has no
#: budget; the tool's own run leaves the file out, and a saved report of the
#: whole suite has its lines dropped.
IGNORED = ("tests/test_render_mesh_skeleton.py",)

_SKIP = re.compile(r"^SKIPPED \[(\d+)\] (.*?): (.+)$")
_XFAIL = re.compile(r"^(?:XFAIL|XPASS) (\S+)")


def run_suite() -> str:
    """What `pytest -rsxX` prints for the suite, without the files of IGNORED."""
    proc = subprocess.run(
        [PY, "-m", "pytest", "-q", "-rsxX", "tests", "--ignore=examples",
         *(f"--ignore={path}" for path in IGNORED)],
        cwd=REPO, capture_output=True, text=True,
    )
    return proc.stdout + proc.stderr


def judge(report: str) -> tuple[list[str], list[str]]:
    """The lines to print and the failures, from a `pytest -rsxX` report."""
    said: list[str] = []
    counts: dict[str, int] = {}
    xfails: dict[str, int] = {}
    for line in report.splitlines():
        x = _XFAIL.match(line.strip())
        if x:
            node = x.group(1)
            if node.startswith(IGNORED):
                continue
            key = next((k for k in ALLOWED_XFAIL if node.startswith(k)), node)
            xfails[key] = xfails.get(key, 0) + 1
            continue
        m = _SKIP.match(line.strip())
        if not m or m.group(2).startswith(IGNORED):
            continue
        repeat = int(m.group(1))
        reason = m.group(3).strip()
        matched = False
        for key in ALLOWED:
            if reason.startswith(key):
                counts[key] = counts.get(key, 0) + repeat
                matched = True
                break
        if not matched:
            counts["__UNBUDGETED__: " + reason] = counts.get(
                "__UNBUDGETED__: " + reason, 0) + repeat

    failures: list[str] = []
    for key in sorted(ALLOWED):
        count = counts.get(key, 0)
        budget = ALLOWED[key]
        flag = "  OK" if count <= budget else "  OVER"
        said.append(f"{flag} {key!r}: {count}x (budget {budget}x)")
        if count > budget:
            failures.append(
                f"skip reason over budget: {key!r} ({count}x, budget {budget}x)")

    unbudgeted = [k for k in counts if k.startswith("__UNBUDGETED__: ")]
    for k in sorted(unbudgeted):
        reason = k[len("__UNBUDGETED__: "):]
        count = counts[k]
        said.append(f"  OVER {reason!r}: {count}x (no budget)")
        failures.append(f"unbudgeted skip reason: {reason!r} ({count}x)")

    for key in sorted(set(ALLOWED_XFAIL) | set(xfails)):
        count = xfails.get(key, 0)
        budget = ALLOWED_XFAIL.get(key)
        if budget is None:
            said.append(f"  OVER xfail {key}: {count}x (no budget)")
            failures.append(f"unbudgeted expected failure (xfail): {key} ({count}x)")
        elif count > budget:
            said.append(f"  OVER xfail {key}: {count}x (budget {budget}x)")
            failures.append(
                f"expected failures over budget: {key} ({count}x, budget {budget}x)")
        else:
            said.append(f"  OK xfail {key}: {count}x (budget {budget}x)")

    if not failures:
        total = sum(v for k, v in counts.items() if not k.startswith("__UNBUDGETED__"))
        said.append(f"\nOK: {total} budgeted skip(s) across {len(ALLOWED)} reason(s), "
                    f"{sum(xfails.values())} expected failure(s) within budget.")
    return said, failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", type=Path,
                    help="a saved `pytest -q -rsxX tests` report to judge, instead of running the suite")
    args = ap.parse_args(argv)
    said, failures = judge(args.report.read_text() if args.report else run_suite())
    print("\n".join(said))
    if failures:
        print()
        print(f"FAIL: {len(failures)} skip budget problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
