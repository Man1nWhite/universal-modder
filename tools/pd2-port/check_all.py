#!/usr/bin/env python3
"""Run the whole LAS pack verification chain and print a one-line verdict.

    python tools/pd2-port/check_all.py           # ~10 s
    python tools/pd2-port/check_all.py --full    # + self-test, pytest, skip budget (~3 min)

Every stage is a separate tool with its own exit code; this only collects
them so that a fresh checkout can be judged in one command.  It never
writes to the repository: the pack is only read, and the mutation stages
restore it.

The chain is the same for any outfit pack; what it is pointed at is the
shipped port. ``--pack`` defaults to ``dist/lawson_las.zip`` and reaches the
checksum, audit and geometry stages; the normal-map, mutation and self-test
stages always use that port's source archive and tracked pack, through the
constants of their own scripts. The last two stages of ``--full`` cover the
whole repository's tests; the skip budget expects the 2B reference templates
under build/pd2-las/2b/ (``bash tools/pd2-las/recover_env.sh``) and fails
without them. It holds expected failures (xfail) to a budget as well.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
PY = sys.executable


def stage(name: str, args: list[str], cwd: Path = ROOT) -> tuple[str, bool, str]:
    t0 = time.time()
    proc = subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True)
    ok = proc.returncode == 0
    lines = [l.strip() for l in (proc.stdout + proc.stderr).strip().splitlines() if l.strip()]
    errs = [l for l in lines if l.startswith("ERROR") or " error" in l.lower()]
    detail = (errs[0] if errs else lines[-1] if lines else "")[:120]
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name:<34} {time.time() - t0:5.1f}s  {detail[:90]}")
    return name, ok, detail


def check_tracked_pack(pack: Path) -> tuple[str, bool, str]:
    """The tracked checksum must match the tracked zip (CI checks the same)."""
    if not pack.exists():
        return "tracked pack", False, f"{pack} is missing - build it first"
    digest = hashlib.sha256(pack.read_bytes()).hexdigest()
    want = (pack.with_suffix(pack.suffix + ".sha256")).read_text().split()[0]
    ok = digest == want
    return "tracked pack matches its checksum", ok, (
        f"{pack.stat().st_size} bytes, sha256 {digest[:16]}…")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--full", action="store_true",
                    help="also run the auditor self-test and the pytest suite")
    ap.add_argument("--pack", default=str(ROOT / "dist" / "lawson_las.zip"),
                    help="the pack to check")
    args = ap.parse_args()

    print("LAS pack verification")
    print(f"  repo: {ROOT}")
    print(f"  pack: {args.pack}")
    results = []

    name, ok, detail = check_tracked_pack(Path(args.pack))
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name:<34}         {detail[:90]}")
    results.append((name, ok, detail))
    results.append(stage("guide compliance audit",
                          [str(HERE / "check_guide_compliance.py"), args.pack]))
    results.append(stage("winding and tangent frame",
                          [str(HERE / "check_mesh_geometry.py"), args.pack]))
    results.append(stage("normal-map convention",
                          [str(HERE / "check_nm_convention.py")]))
    results.append(stage("pack-level test mutations",
                          [str(HERE / "check_test_suite_mutations.py")]))
    if args.full:
        results.append(stage("auditor self-test",
                              [str(HERE / "check_guide_compliance_self_test.py")]))
        results.append(stage("pytest suite", ["-m", "pytest", "-q", "tests"]))
        results.append(stage("skip budget", [str(HERE / "check_skip_budget.py")]))

    bad = [n for n, ok, _ in results if not ok]
    print()
    if bad:
        print(f"FAILED: {len(bad)} of {len(results)} stages: {', '.join(bad)}")
        return 1
    print(f"all {len(results)} stages passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
