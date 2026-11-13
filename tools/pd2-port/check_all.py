#!/usr/bin/env python3
"""Run the whole LAS pack verification chain and print a one-line verdict.

    python tools/pd2-port/check_all.py           # ~10 s
    python tools/pd2-port/check_all.py --full    # + everything the test workflow checks (~5 min)
    make -sC tools/pd2-las green                 # the same as --full

Every stage is a separate tool with its own exit code; this only collects
them so that a fresh checkout can be judged in one command.  It never
writes to the repository: the pack is only read, and the mutation stages
restore it.

The chain is the same for any outfit pack; what it is pointed at is the
shipped port. ``--pack`` defaults to ``dist/lawson_las.zip`` and reaches the
checksum, audit and geometry stages; the normal-map, mutation and self-test
stages always use that port's source archive and tracked pack, through the
constants of their own scripts.

``--full`` judges the whole repository. It adds what .github/workflows/test.yml
runs, so "is everything green?" is one command here and not six: the lint, the
``um`` command groups, the knowledge base, the publish check, the suite, and
every tracked pack built again and compared with its sha256
(tools/pd2-las/fresh.py; 16 zips). The skip budget expects the 2B reference
templates under build/pd2-las/2b/ (``make -sC tools/pd2-las env``) and fails
without them. It holds expected failures (xfail) to a budget as well, and it
judges the report of the suite stage: the suite runs once. The last line
printed is the next command to run.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = sys.executable
#: the command groups of `um`; the test workflow asks each for --help
UM_GROUPS = "scan fal comfy sprite render3d video win backup publish kb".split()
#: name of a stage -> the command that shows its whole output
RERUN: dict[str, str] = {}


def stage(name: str, args: list[str], cwd: Path = ROOT, keep: Path | None = None) -> tuple[str, bool, str]:
    """Run one check. `keep` is where its whole output goes, for a later stage to read."""
    RERUN[name] = ".venv/bin/python " + " ".join(
        arg if not arg.startswith(str(ROOT)) else str(Path(arg).relative_to(ROOT)) for arg in args)
    t0 = time.time()
    proc = subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True)
    if keep:
        keep.write_text(proc.stdout + proc.stderr)
    ok = proc.returncode == 0
    lines = [l.strip() for l in (proc.stdout + proc.stderr).strip().splitlines() if l.strip()]
    errs = [l for l in lines if l.startswith("ERROR") or " error" in l.lower()]
    detail = (errs[0] if errs else lines[-1] if lines else "")[:120]
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name:<34} {time.time() - t0:5.1f}s  {detail[:90]}")
    return name, ok, detail


def um_groups() -> tuple[str, bool, str]:
    """`um --help` and the --help of every command group: an import error in one group fails here."""
    name, t0, bad = "um and its command groups", time.time(), []
    RERUN[name] = ".venv/bin/python -m um --help"
    for group in [None, *UM_GROUPS]:
        argv = [PY, "-m", "um", *([group] if group else []), "--help"]
        if subprocess.run(argv, cwd=ROOT, capture_output=True).returncode != 0:
            bad.append(group or "um")
    detail = f"--help fails for: {', '.join(bad)}" if bad else f"--help of um and of {len(UM_GROUPS)} groups"
    print(f"  [{'FAIL' if bad else 'ok  '}] {name:<34} {time.time() - t0:5.1f}s  {detail}")
    return name, not bad, detail


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
                    help="also run everything the test workflow checks: lint, um, knowledge base, "
                         "publish check, the suite, the skip budget, all 16 zips rebuilt")
    ap.add_argument("--pack", default=str(ROOT / "dist" / "lawson_las.zip"),
                    help="the pack to check")
    args = ap.parse_args()

    print("LAS pack verification")
    print(f"  repo: {ROOT}")
    print(f"  pack: {args.pack}")
    results = []

    name, ok, detail = check_tracked_pack(Path(args.pack))
    RERUN[name] = "make -sC tools/pd2-las status"
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
        results.append(stage("lint", ["-m", "pyflakes", "um", "tools", "tests"]))
        results.append(um_groups())
        results.append(stage("knowledge base", ["-m", "um", "kb", "check", "--index"]))
        results.append(stage("nothing that shouldn't ship", ["-m", "um", "publish", "check", "."]))
        # One run of the suite serves both stages: -rsxX adds the skip and xfail lines that the budget
        # reads. Until 2026-11-13 the budget ran the suite a second time, two minutes of the seven.
        with tempfile.TemporaryDirectory() as scratch:
            report = Path(scratch) / "pytest-rsxX.txt"
            results.append(stage("pytest suite", ["-m", "pytest", "-q", "-rsxX", "tests"], keep=report))
            results.append(stage("skip budget", [str(HERE / "check_skip_budget.py"), "--report", str(report)]))
        RERUN["skip budget"] = ".venv/bin/python tools/pd2-port/check_skip_budget.py"
        results.append(stage("every tracked zip, built again",
                              [str(ROOT / "tools" / "pd2-las" / "fresh.py"), "check"]))

    bad = [n for n, ok, _ in results if not ok]
    print()
    if bad:
        print(f"FAILED: {len(bad)} of {len(results)} stages: {', '.join(bad)}")
        print(f"next: {RERUN.get(bad[0], 'git status --short')}")
        return 1
    print(f"all {len(results)} stages passed")
    print("next: git status --short" if args.full else "next: make -sC tools/pd2-las green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
