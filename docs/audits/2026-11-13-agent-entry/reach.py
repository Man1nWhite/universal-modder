#!/usr/bin/env python3
"""Which functions of a tool does nothing run?

    .venv/bin/python docs/audits/2026-11-13-agent-entry/reach.py FILE.py [FILE.py ...] [--also FILE.py ...]
    .venv/bin/python docs/audits/2026-11-13-agent-entry/reach.py --report FILE.py [...]   the table again, from the data of the last run

A search by name says that nothing mentions a function. This says that nothing executes it: the
files are put under line coverage (coverage.py, in every Python process a command starts) while

  suite   the whole test suite runs,
  builds  every tracked pack is built again (`fresh.py check`, what `make fresh` and CI run),
  tools   each of the tools `copies.py` holds to a recorded output is started, in a copy of the tree,
  start   each FILE is started on its own, with no argument and with `--help`.

Then every function of each FILE is listed with the phases that ran a line of its body. A function
that is in no phase was not run by anything this repository can start, and its line says which
other code writes its name. A name like `render` is always written somewhere; a function that
nothing ran and no other code names can only be reached from a prompt. About 15 minutes.

Files after `--also` are measured in the first three phases and not started: starting a builder
with no argument builds a pack. For those files "run by nothing" means less. A command that only a
person starts, and no test, is in none of the three phases and is not dead.

Nothing here touches the pinned environment: coverage is installed under build/reach/ and reaches
the measured processes through PYTHONPATH, as in `tools/pd2-las/copies.py`.
"""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PY = REPO / ".venv" / "bin" / "python"
OUT = REPO / "build" / "reach"
SITE = OUT / "site"
PHASES = ("suite", "builds", "tools", "start")
HOOK = "try:\n    import coverage\n    coverage.process_startup()\nexcept Exception:\n    pass\n"


def env_for(phase: str, files: list[str]) -> dict:
    data = OUT / phase
    data.mkdir(parents=True, exist_ok=True)
    rc = data / "coveragerc"
    include = ",".join(f"*/{rel}" for rel in files)
    rc.write_text(f"[run]\nparallel = True\ndata_file = {data / 'cov'}\ninclude = {include}\n"
                  "concurrency = multiprocessing,thread\nsigterm = True\n")
    path = os.pathsep.join(p for p in (str(SITE), os.environ.get("PYTHONPATH", "")) if p)
    return {**os.environ, "PYTHONPATH": path, "COVERAGE_PROCESS_START": str(rc)}


def run(label: str, command: list[str], cwd: Path, env: dict, timeout: int = 1800) -> None:
    try:
        done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, errors="replace", timeout=timeout)
        code, tail = done.returncode, (done.stdout.strip().splitlines() or [""])[-1]
    except subprocess.TimeoutExpired:
        code, tail = "timeout", ""
    print(f"   {label:<34} exit {code}   {tail[:90]}", flush=True)


def functions(path: Path) -> list[tuple[str, int, set]]:
    """(qualified name, line of its def, the lines of the statements in its body)."""
    found = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = child.body[1:] if ast.get_docstring(child) is not None else child.body
                lines = {n.lineno for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.stmt)}
                found.append((prefix + child.name, child.lineno, lines))
                walk(child, prefix + child.name + ".")
            elif isinstance(child, ast.ClassDef):
                walk(child, prefix + child.name + ".")
            else:
                walk(child, prefix)

    walk(ast.parse(path.read_text(encoding="utf-8")), "")
    return found


def executed(phase: str, files: list[str]) -> dict:
    sys.path.insert(0, str(SITE))
    from coverage import CoverageData
    lines = {rel: set() for rel in files}
    for data in sorted((OUT / phase).glob("cov.*")):
        store = CoverageData(basename=str(data))
        store.read()
        for measured in store.measured_files():
            for rel in files:
                if measured.replace(os.sep, "/").endswith("/" + rel):
                    lines[rel] |= set(store.lines(measured) or [])
    return lines


CODE = ("*.py", "*.sh", "*Makefile", "*.yml", "*.toml")


def named_elsewhere(name: str, rel: str, line: int) -> tuple[list[str], int]:
    """Where the name is written as a whole word, apart from its own `def`: the lines of code, and how many lines of anything else.

    docs/audits/ is left out: those are the records of a day, and they list functions like these.
    """
    def grep(*paths):
        done = subprocess.run(["git", "grep", "-n", "-w", "-I", "-F", "-e", name.rsplit(".", 1)[-1], "--", *paths, ":!docs/audits"],
                              cwd=REPO, capture_output=True, text=True, errors="replace")
        hits = [hit.split(":", 2)[:2] for hit in done.stdout.splitlines()]
        return [f"{path}:{number}" for path, number in hits if (path, number) != (rel, str(line))]

    code = grep(*CODE)
    return code, len(grep(".")) - len(code)


def report(files: list[str], started: int | None = None) -> int:
    ran = {phase: executed(phase, files) for phase in PHASES}
    print()
    never = unnamed = 0
    for rel in files:
        rows = functions(REPO / rel)
        counts = {phase: sum(1 for _, _, body in rows if body & ran[phase][rel]) for phase in PHASES}
        idle = [(name, line) for name, line, body in rows if not any(body & ran[phase][rel] for phase in PHASES)]
        print(f"{rel}: {len(rows)} functions; run by " + ", ".join(f"{phase} {counts[phase]}" for phase in PHASES)
              + f"; by none {len(idle)}")
        for name, line in idle:
            code, other = named_elsewhere(name, rel, line)
            print(f"   not run by anything: {name} (line {line}); "
                  + (f"other code names it on {len(code)} lines: {', '.join(code[:3])}" + (" ..." if len(code) > 3 else "") if code
                     else "no other code names it" + (f" ({other} lines of documents do)" if other else "")))
            unnamed += not code
        never += len(idle)
    print(f"\n{never} functions in {len(files)} files were run by no test, no build, no tool and no start of the file; "
          f"no other code names {unnamed} of them"
          + (f"\n(only the first {started} files were started)" if started is not None and started < len(files) else ""))
    return 0


def main(argv: list[str]) -> int:
    only_report = argv[:1] == ["--report"]
    argv = argv[only_report:]
    started = argv.index("--also") if "--also" in argv else len(argv)
    files = [str(Path(arg).resolve().relative_to(REPO)) for arg in argv if arg != "--also"]
    if not files or len(set(files)) != len(files):
        print(__doc__ if not files else "a file is named twice")
        return 2
    if only_report:
        return report(files, started)
    shutil.rmtree(OUT, ignore_errors=True)
    SITE.mkdir(parents=True)
    subprocess.run([str(PY), "-m", "pip", "install", "-q", "--target", str(SITE), "coverage==7.6.10"], check=True)
    (SITE / "sitecustomize.py").write_text(HOOK)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.splitlines()
    print(f"commit: {head}" + ("".join(f"\n   not committed: {line.strip()}" for line in dirty[:8]) if dirty else ""))

    print("suite")
    run("pytest -q tests", [str(PY), "-m", "pytest", "-q", "tests", "-p", "no:cacheprovider"], REPO, env_for("suite", files))
    print("builds")
    run("fresh.py check", [str(PY), "tools/pd2-las/fresh.py", "check"], REPO, env_for("builds", files))

    sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
    import copies
    import fresh
    tree, scratch = OUT / "tree", OUT / "scratch"
    scratch.mkdir()
    fresh.copy_tree(tree)
    for name in ("Miranda_LAS", "Christie_LAS"):
        with zipfile.ZipFile(tree / "dist" / f"{name}.zip") as z:
            z.extractall(scratch / "packs")
    fill = {"{s}": str(scratch), "{m}": str(scratch / "packs/Miranda_LAS/assets/units/miranda/skins/miranda"),
            "{c}": str(scratch / "packs/Christie_LAS/assets/units/christie/skins/christie")}
    print(f"tools ({len(copies.GOLDEN)})")
    env = env_for("tools", files)
    for name, args in copies.GOLDEN:
        for token, value in fill.items():
            args = [arg.replace(token, value) for arg in args]
        run(name, [str(PY), *args], tree, env, timeout=600)
    print("start")
    env = env_for("start", files)
    for rel in files[:started]:
        run(f"{Path(rel).name}", [str(PY), rel], tree, env, timeout=600)
        run(f"{Path(rel).name} --help", [str(PY), rel, "--help"], tree, env, timeout=600)

    return report(files, started)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
