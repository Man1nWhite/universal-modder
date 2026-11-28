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
With `--report` it requires a completed, successful `pytest -q -rsxX tests` report instead:
`check_all.py --full` hands it the report of the suite it has just run, so the
suite runs once there and not twice.

Reasons for fixtures that are present in this checkout (e.g. the extracted 2B
templates) are listed at count 0 so that their reappearance — a regression to
a 59-skip state — fails immediately.

The budget must hold in both environments the suite runs in: a dev checkout
made by `recover_env.sh --extras` (lupa and sourcepp present, so those tests
run) and the CI runner, which installs neither. Each such reason therefore has
room for its CI count, not its dev count.

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
    # CI installs neither lupa nor sourcepp. Without lupa, pytest reports 1 module
    # skip in test_glove_behavior_lua.py (module-level importorskip), 5 in
    # test_las_outfit_pack.py (the shared compile helper) and 6 in
    # test_geralt_vo_pack.py (the BeardLib <Sounds> harness). A dev checkout made
    # with `--extras` reports none; this is the CI count, not the dev count.
    "lupa (LuaJIT) not installed": 12,
    "Git Bash / MSYS only": 1,
    "declared code path requires x86-64 Linux": 1,
    # Regression to watch for: the fixture and tracked packs are present, so these
    # must be 0. Every test that needs the 2B templates skips with
    # tools/pd2-las/extract_2b.MISSING; any other wording is unbudgeted and fails.
    "2B templates not extracted": 0,
    "Tokoyami Hila reference archive is absent": 1,
}

#: Maximum number of expected failures (xfail) per test, by node-id prefix.
#: These are known defects that are recorded where the marker is, not tests
#: that somebody wanted out of the way. Empty since 2026-11-13: there is no
#: expected failure left.
ALLOWED_XFAIL: dict[str, int] = {}

#: Files left out of budget judging (empty: every test file in tests/ is judged).
IGNORED = ()

_SKIP = re.compile(r"^SKIPPED \[(\d+)\] (.*?): (.+)$")
_XFAIL = re.compile(r"^(?:XFAIL|XPASS) (\S+)")


def run_suite() -> subprocess.CompletedProcess[str]:
    """Run pytest once; callers must check its status before judging skips."""
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-rsxX", "tests", "--ignore=examples",
         *(f"--ignore={path}" for path in IGNORED)],
        cwd=REPO, capture_output=True, text=True,
    )


_SUMMARY = re.compile(r"^(?:=+\s+)?(\d+ [a-z]+(?:, \d+ [a-z]+)*) in \d+(?:\.\d+)?s"
                      r"(?: \([0-9:]+\))?(?:\s+=+)?$")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def validate_report(report: str) -> str | None:
    """Reject a missing/failed summary and incomplete skip or xfail details.

    Strips ANSI codes so reports piped through colour output still validate.
    Accepts both old and new pytest summary formats (with or without warnings).
    """
    # Strip ANSI escape codes that pytest may emit with --color
    report = _ANSI.sub("", report)
    lines = report.rstrip().splitlines()
    if not lines:
        return "no completed pytest summary (use pytest -q -rsxX tests)"
    summary = _SUMMARY.fullmatch(lines[-1].strip()) if lines else None
    if not summary:
        # Try without the trailing === markers (some pytest versions)
        alt = lines[-1].strip().strip("= ")
        summary = _SUMMARY.fullmatch(f"== {alt} ==") if alt else None
        if not summary:
            return "no completed pytest summary (use pytest -q -rsxX tests)"
    counts = {label: int(n) for n, label in re.findall(r"(\d+) ([a-z]+)", summary[1])}
    if counts.get("failed") or counts.get("error") or counts.get("errors"):
        return "pytest did not pass"
    results = ("passed", "skipped", "xfailed", "xpassed")
    if counts.keys() - {*results, "warning", "warnings"}:
        return "pytest did not run the full suite"
    if not any(counts.get(label) for label in results):
        return "pytest reported no test results"
    skips = sum(int(m[1]) for line in lines if (m := _SKIP.match(line.strip())))
    xfails = sum(1 for line in lines if _XFAIL.match(line.strip()))
    if (skips != counts.get("skipped", 0)
            or xfails != counts.get("xfailed", 0) + counts.get("xpassed", 0)):
        return "pytest skip/xfail details do not match the summary (use -rsxX)"
    return None


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
    if args.report:
        try:
            report = args.report.read_text(encoding="utf-8")
        except (OSError, ValueError) as error:
            print(f"FAIL: cannot read pytest report: {error}", file=sys.stderr)
            return 1
    else:
        result = run_suite()
        report = result.stdout + result.stderr
        if result.returncode:
            print(report, end="")
            print(f"FAIL: pytest exited with status {result.returncode}", file=sys.stderr)
            return 1
    report = _ANSI.sub("", report)
    if error := validate_report(report):
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    said, failures = judge(report)
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
