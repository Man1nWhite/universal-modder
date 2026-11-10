#!/usr/bin/env python3
"""Skip budget: every `pytest.skip` reason must be known and within its count.

An unconditional `pytest.skip` inside a helper (e.g. test_christie_las.py:539)
turns off 37 tests with one line. This makes the budget explicit: each known
skip reason has a maximum count, and any new reason or growth fails.

Run from the repo root:
    .venv/bin/python tools/pd2-port/check_skip_budget.py

The tool runs `pytest -rs` itself, groups skip reasons by prefix match against
`ALLOWED`, and multiplies by the `[N]` repeat count shown by `-rs`. A reason
not starting with any ALLOWED key, or one exceeding its count, is a failure.

Reasons for fixtures that are present in this checkout (e.g. the extracted 2B
templates) are listed at count 0 so that their reappearance — a regression to
a 59-skip state — fails immediately.
"""

from __future__ import annotations

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
    "nifly not built": 2,
    "pack not built in this checkout": 7,
    "needs ffmpeg": 4,
    "4.zip absent": 10,
    "the Skyrim source archive was intentionally removed after cancellation": 2,
    "build output not present": 1,
    "sourcepp is an optional extra": 2,
    "lupa (LuaJIT) not installed": 1,
    "Git Bash / MSYS only": 1,
    # Regressions to watch for: the fixture is extracted, so these must be 0:
    "2B templates not extracted (run tools/pd2-las/bootstrap.sh)": 0,
    "extracted 2B templates at /tmp/2bsrc not present": 0,
    "2b.rar reference models not extracted to /tmp/2bsrc": 0,
    "2B templates not extracted": 0,
    "templates": 0,
}

_SKIP = re.compile(r"^SKIPPED \[(\d+)\] .*?: (.+)$")


def main() -> int:
    proc = subprocess.run(
        [PY, "-m", "pytest", "-q", "-rs",
         "tests",
         "--ignore=examples",
         "--ignore=tests/test_render_mesh_skeleton.py"],
        cwd=REPO, capture_output=True, text=True,
    )
    counts: dict[str, int] = {}
    for line in (proc.stdout + proc.stderr).splitlines():
        m = _SKIP.match(line.strip())
        if not m:
            continue
        repeat = int(m.group(1))
        reason = m.group(2).strip()
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
        print(f"{flag} {key!r}: {count}x (budget {budget}x)")
        if count > budget:
            failures.append(
                f"skip reason over budget: {key!r} ({count}x, budget {budget}x)")

    unbudgeted = [k for k in counts if k.startswith("__UNBUDGETED__: ")]
    for k in sorted(unbudgeted):
        reason = k[len("__UNBUDGETED__: "):]
        count = counts[k]
        print(f"  OVER {reason!r}: {count}x (no budget)")
        failures.append(f"unbudgeted skip reason: {reason!r} ({count}x)")

    if failures:
        print()
        print(f"FAIL: {len(failures)} skip budget problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1

    total = sum(v for k, v in counts.items() if not k.startswith("__UNBUDGETED__"))
    print(f"\nOK: {total} budgeted skip(s) across {len(ALLOWED)} reason(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
