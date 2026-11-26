#!/usr/bin/env python3
"""Run the whole LAS pack verification chain and print a one-line verdict.

    python tools/pd2-port/check_all.py             # full Romance pack checks
    python tools/pd2-port/check_all.py --pack ZIP  # common checksum and geometry checks for one ZIP
    make -sC tools/pd2-las green                   # default checks plus the repository suite

The default verifies the shipped Romance pack against its DODB guide rules,
source normal convention, and pack-level mutation tests. The mutations use
scratch copies. An explicitly selected pack gets the cross-pipeline checks
only: it never inherits an audit result from an unrelated source or pack.

``--full`` (``green``) also runs the lint, CLI help, knowledge base, publish
check, suite and skip budget, and an independent rebuild of every tracked ZIP.
Run ``make -sC tools/pd2-las env`` first. The suite runs once; the skip budget
reads its report. No stage writes to the original distribution packs.

"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import sys as _dist_sys
_dist_sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "pd2-las"))
from dist_paths import dist_path  # noqa: E402
from pack_checksum import verify_checksum  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = sys.executable
DEFAULT_PACK = dist_path(ROOT, "Miranda_Romance_LAS.zip")
#: the command groups of `um`; the test workflow asks each for --help
UM_GROUPS = "scan fal comfy sprite render3d video win backup publish kb".split()
#: name of a stage -> the command that shows its whole output
RERUN: dict[str, str] = {}


def stage(name: str, args: list[str], cwd: Path = ROOT, keep: Path | None = None) -> tuple[str, bool, str]:
    """Run one check. `keep` is where its whole output goes, for a later stage to read."""
    RERUN[name] = shlex.join([".venv/bin/python", *(
        str(Path(arg).relative_to(ROOT)) if Path(arg).is_relative_to(ROOT) else arg for arg in args)])
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
    """Check the selected ZIP against its own sidecar, with a usable error."""
    name = "pack matches its checksum"
    try:
        digest = verify_checksum(pack, ROOT, portable=not pack.is_relative_to(ROOT / "dist"))
    except (OSError, ValueError) as error:
        return name, False, str(error)
    return name, True, f"{pack.stat().st_size} bytes, sha256 {digest[:16]}…"


def needs_fetch(pack: Path) -> bool:
    """True when the packs are release assets and this clone has not fetched them.

    Without this the first stage fails with "the Romance pack does not match its checksum", which
    reads like a broken pack rather than a clone that is missing 428 MB on purpose.
    """
    return not pack.is_file() and (ROOT / "assets.json").is_file()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="also run the repository verification stages")
    mode.add_argument("--pack", type=Path, help="run only checksum and geometry on this pack")
    args = ap.parse_args(argv)
    native = args.pack is None
    pack = (args.pack or DEFAULT_PACK).resolve()

    print("Romance LAS pack verification" if native else "Pack checksum and geometry (not a full outfit audit)")
    print(f"  repo: {ROOT}")
    print(f"  pack: {pack}")
    if needs_fetch(pack):
        print("  the packs are release assets and this clone has not fetched them")
        print("next: make -sC tools/pd2-las fetch")
        return 1
    name, ok, detail = check_tracked_pack(pack)
    RERUN[name] = "make -sC tools/pd2-las status" if native else f"inspect the ZIP and sidecar for {pack}"
    print(f"  [{'ok  ' if ok else 'FAIL'}] {name:<34}         {detail}")
    results = [(name, ok, detail)]
    if native:
        results.append(stage("guide compliance audit",
                              [str(HERE / "check_guide_compliance.py"), str(pack)]))
    if pack.is_file():
        results.append(stage("winding and tangent frame",
                              [str(HERE / "check_mesh_geometry.py"), str(pack)]))
    if native:
        results.append(stage("normal-map convention",
                              [str(HERE / "check_nm_convention.py")]))
        results.append(stage("pack-level test mutations",
                              [str(HERE / "check_test_suite_mutations.py")]))
    if args.full:
        results.append(stage("auditor self-test",
                              [str(HERE / "check_guide_compliance_self_test.py")]))
        results.append(stage("original distribution checksums",
                             [str(ROOT / "tools" / "pd2-las" / "pack_checksum.py")]))
        results.append(stage("lint", ["-m", "pyflakes", "um", "tools", "tests"]))
        results.append(um_groups())
        results.append(stage("documentation links", [str(ROOT / "tools" / "pd2-port" / "check_links.py")]))
        results.append(stage("documentation index", [str(ROOT / "tools" / "gen_docs_index.py"), "--check"]))
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
    print("next: make -sC tools/pd2-las green" if native and not args.full else "next: git status --short")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
