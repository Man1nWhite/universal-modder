#!/usr/bin/env python3
"""Evidence for merging the tools that do one job in more than one place.

    python tools/pd2-las/copies.py record     what the tools read, write and print before anything is merged
    python tools/pd2-las/copies.py compare    the copies of each job, as they were before the merge, on real files
    python tools/pd2-las/copies.py after      the record again on the tree as it is now, against the first

The record is what a merge is held to (docs/audits/2026-11-12-tool-merge.md). Its parts:

  build    every tracked pack built again (`fresh.py check`), each builder process logging every
           file it opens and the function that opened it, with line coverage of the files that
           hold the copies
  suite    the test suite under the same coverage
  outputs  every tool that uses a copy and whose result no pack hash covers, started in a copy of
           the tree, twice: exit code, what it printed, a sha256 of each file it wrote
  trace    the checkpoint trace of every builder (`trace_run.py`), twice: per function, a checksum
           of everything it returned
  lint     pylint's duplicate-code report over tools/

Two runs of the outputs and of the trace show what is steady; only that is compared later.

None of this touches the pinned environment: coverage and pylint are installed under
build/copies/tools/ and reach the measured processes through PYTHONPATH.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PY = REPO / ".venv" / "bin" / "python"
OUT = REPO / "build" / "copies"
TOOLS = OUT / "tools"
EVIDENCE = REPO / "docs" / "audits" / "2026-11-12-tool-merge"
BASE = "26fce3e03de22d1466636d4b22764601f0541f02"            # the last commit before any merge: the copies are compared as they were there
sys.path.insert(0, str(HERE))
import extract_2b  # noqa: E402  (it owns where the 2B templates are)

TEMPLATES = os.path.relpath(extract_2b.TEMPLATES, REPO)

# the files that hold the copies
COPIES = [
    "tools/pd2-port/dmodel.py", "tools/pd2-las/diesel_model.py", "tools/pd2-port/las_model.py", "tools/pd2-port/me2_dae.py",
    "tools/pd2-port/dds.py", "tools/pd2-las/dds_encode.py",
    "tools/pd2-las/las_pack.py", "tools/pd2-las/las_outfit_pack.py", "tools/pd2-las/build_christie_las.py",
    "tools/pd2-port/build_las_pack.py",
]

# every tool that uses a copy and is not a builder, and what the Makefile and the workflows start
GOLDEN = [
    ("status", ["tools/pd2-las/status.py"]),
    ("extract_2b", ["tools/pd2-las/extract_2b.py"]),
    ("inventory", ["tools/pd2-las/build_las.py", "--stage", "inventory", "--out", "tools/pd2-las"]),
    ("mip_audit", ["tools/pd2-las/mip_audit.py"]),
    ("audit_metrics", ["tools/pd2-las/audit_metrics.py"]),
    ("diagnose_mesh", ["tools/pd2-las/diagnose_mesh.py"]),
    ("elbow_before_after", ["tools/pd2-las/elbow_before_after.py", "--before", "dist/Christie_LAS.zip", "--after", "dist/Christie_LAS.zip",
                            "--templates", TEMPLATES, "--out", "{s}/elbow", "--scratch", "{s}/panels"]),
    ("glove_check", ["tools/pd2-las/glove_check.py", "{c}/christie.model", "{s}/glove.png"]),
    ("neck_junction", ["tools/pd2-las/neck_junction.py"]),
    ("pose_preview", ["tools/pd2-las/pose_preview.py"]),
    ("preview_textured", ["tools/pd2-las/preview_textured.py", "{m}/miranda.model", "{m}", "--out", "{s}/textured.png"]),
    ("render_mesh_skeleton", ["tools/pd2-las/render_mesh_skeleton.py", "--zip", "dist/Christie_LAS.zip", "--pack", "Christie_LAS",
                              "--item", "christie", "--templates", TEMPLATES, "--out", "{s}/skeleton"]),
    ("skin_texture", ["tools/pd2-las/skin_texture.py", "--out", "{s}/skin", "--no-preview"]),
    ("uv_check", ["tools/pd2-las/uv_check.py", "--two-b", TEMPLATES, "--ours", "{m}/miranda.model", "--out", "{s}/uv.png"]),
    ("build_skyrim_outfit", ["tools/pd2-las/build_skyrim_outfit.py"]),
    ("check_guide_compliance", ["tools/pd2-port/check_guide_compliance.py", "dist/lawson_las.zip"]),
    ("check_guide_compliance_miranda", ["tools/pd2-port/check_guide_compliance.py", "dist/Miranda_LAS.zip"]),
    ("check_guide_compliance_christie", ["tools/pd2-port/check_guide_compliance.py", "dist/Christie_LAS.zip"]),
    ("check_mesh_geometry", ["tools/pd2-port/check_mesh_geometry.py", "dist/lawson_las.zip"]),
    ("check_mesh_geometry_miranda", ["tools/pd2-port/check_mesh_geometry.py", "dist/Miranda_LAS.zip"]),
    ("check_mesh_geometry_christie", ["tools/pd2-port/check_mesh_geometry.py", "dist/Christie_LAS.zip"]),
    ("check_nm_convention", ["tools/pd2-port/check_nm_convention.py"]),
    ("check_test_suite_mutations", ["tools/pd2-port/check_test_suite_mutations.py"]),
    ("check_guide_compliance_self_test", ["tools/pd2-port/check_guide_compliance_self_test.py"]),
    ("extract_las_rig", ["tools/pd2-port/extract_las_rig.py", TEMPLATES + "/2b.model", "{s}/rig.json"]),
    ("resolve_rig_names", ["tools/pd2-port/resolve_rig_names.py"]),
    ("preview_check", ["tools/pd2-port/preview_check.py"]),
    ("render_mod_previews", ["tools/render_mod_previews.py"]),
    ("um_kb_check", ["-m", "um", "kb", "check", "--index"]),
    ("um_publish_check", ["-m", "um", "publish", "check", "."]),
]

# these walk every file of the tree and count: a new file changes the numbers they print, not what they find
WHOLE_TREE = {"um_kb_check", "um_publish_check"}

INTEREST = [".model", ".texture", ".dds", ".zip", "main.xml", ".lua", "english.txt", ".unit", ".object", ".material_config",
            "BUILD_INFO.json", ".sha256", ".vtf", ".gma", ".vpk", ".rar", ".dae", ".smd"]

# Runs at the start of every measured Python process (PYTHONPATH -> sitecustomize).
HOOK = r'''
import os, sys
_dir = os.environ.get("COPIES_OPEN_LOG")
if _dir:
    try:
        _fd = os.open(os.path.join(_dir, "%d.log" % os.getpid()), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.write(_fd, ("ARGV\t" + "\t".join(getattr(sys, "orig_argv", None) or sys.argv) + "\n").encode("utf-8", "replace"))
        def _hook(event, args, _fd=_fd, _write=os.write, _frame=sys._getframe, _skip=(".py", ".pyc", ".so", ".pth")):
            if event != "open":
                return
            try:
                path, mode, flags = args
                if isinstance(path, bytes):
                    path = path.decode("utf-8", "replace")
                if not isinstance(path, str) or path.endswith(_skip) or "/lib/python" in path or "__pycache__" in path:
                    return
                who, frame, depth = "", _frame(1), 0
                while frame is not None and depth < 80:
                    name = frame.f_code.co_filename
                    if (("/tools/" in name or "/um/" in name) and "site-packages" not in name and "/copies/tools/" not in name
                            and "/scratch/m/" not in name and not name.endswith("copies.py")):
                        who = os.path.basename(name)[:-3] + "." + frame.f_code.co_name
                        break
                    frame, depth = frame.f_back, depth + 1
                _write(_fd, ("%s\t%s\t%s\t%s\n" % (mode, flags, path, who)).encode("utf-8", "replace"))
            except Exception:
                pass
        sys.addaudithook(_hook)
    except OSError:
        pass
if os.environ.get("COVERAGE_PROCESS_START"):
    try:
        import coverage
        coverage.process_startup()
    except Exception:
        pass
'''


def sha(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    return hashlib.sha256(data).hexdigest()


def save(name: str, value) -> None:
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    (OUT / "parts" / f"{name}.json").write_text(json.dumps(value, indent=1, sort_keys=True))


def part(name: str) -> dict:
    path = OUT / "parts" / f"{name}.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def ensure_tools() -> None:
    """coverage, texture2ddecoder and pylint, outside the pinned environment."""
    pip = [str(PY), "-m", "pip", "install", "-q", "--disable-pip-version-check"]
    if not (TOOLS / "cov" / "coverage").is_dir():
        subprocess.run([*pip, "--target", str(TOOLS / "cov"), "coverage"], check=True)
    if not (TOOLS / "t2d").is_dir():
        subprocess.run([*pip, "--target", str(TOOLS / "t2d"), "texture2ddecoder"], check=True)
    if not (TOOLS / "lint" / "bin" / "python").exists():
        subprocess.run(["python3", "-m", "venv", str(TOOLS / "lint")], check=True)
        subprocess.run([str(TOOLS / "lint" / "bin" / "python"), "-m", "pip", "install", "-q", "--disable-pip-version-check", "pylint"], check=True)


def measured_env(openlog: Path | None = None, coverage_rc: Path | None = None, seed: bool = True) -> dict:
    inject = OUT / "inject"
    inject.mkdir(parents=True, exist_ok=True)
    (inject / "sitecustomize.py").write_text(HOOK)
    env = dict(os.environ)
    paths = [str(inject)]
    if coverage_rc is not None:
        paths.append(str(TOOLS / "cov"))
        env["COVERAGE_PROCESS_START"] = str(coverage_rc)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    if openlog is not None:
        openlog.mkdir(parents=True, exist_ok=True)
        env["COPIES_OPEN_LOG"] = str(openlog)
    if seed:
        env["PYTHONHASHSEED"] = "0"
    return env


# ---------------------------------------------------------------- coverage
def coverage_rc(label: str) -> Path:
    home = OUT / f"cov-{label}"
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True)
    include = "".join(f"    */{rel}\n" for rel in COPIES)
    (home / "coveragerc").write_text(f"[run]\nparallel = True\ndata_file = {home / 'data'}\ninclude =\n{include}\n"
                                     f"[paths]\ntools =\n    {REPO / 'tools'}\n    */tools\n")
    return home / "coveragerc"


def coverage_lines(label: str) -> dict:
    """File -> the lines that ran, with every copy of the tree mapped back onto the repository."""
    home = OUT / f"cov-{label}"
    rc = home / "coveragerc"
    env = {**os.environ, "PYTHONPATH": str(TOOLS / "cov")}
    subprocess.run([str(PY), "-m", "coverage", "combine", f"--rcfile={rc}"], cwd=REPO, env=env, capture_output=True, text=True)
    done = subprocess.run([str(PY), "-m", "coverage", "json", f"--rcfile={rc}", "-o", str(home / "coverage.json")],
                          cwd=REPO, env=env, capture_output=True, text=True)
    if not (home / "coverage.json").is_file():
        return {"error": (done.stdout + done.stderr)[-400:]}
    files = json.loads((home / "coverage.json").read_text())["files"]
    return {(os.path.relpath(name, REPO) if os.path.isabs(name) else name): sorted(entry["executed_lines"]) for name, entry in files.items()}


def functions(rel: str) -> list:
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    found = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines = {sub.lineno for stmt in child.body for sub in ast.walk(stmt) if hasattr(sub, "lineno")}
                found.append((prefix + child.name, lines))
                walk(child, prefix + child.name + ".")
            elif isinstance(child, ast.ClassDef):
                walk(child, prefix + child.name + ".")

    walk(tree, "")
    return found


def reach(build: dict, tests: dict) -> dict:
    table = {}
    for rel in COPIES:
        rows = functions(rel)
        b, t = set(build.get(rel) or []), set(tests.get(rel) or [])
        table[rel] = {"functions": len(rows),
                      "build": sum(1 for _n, lines in rows if lines & b),
                      "tests": sum(1 for _n, lines in rows if lines & t),
                      "tests_only": sorted(n for n, lines in rows if lines & t and not lines & b),
                      "neither": sorted(n for n, lines in rows if not lines & (b | t))}
    return table


# ---------------------------------------------------------------- what a process opened
def read_opens(logdir: Path) -> list:
    out = []
    for log in sorted(logdir.glob("*.log")):
        argv, opens = [], []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("\t")
            if parts[0] == "ARGV":
                argv = argv or parts[1:]
            elif len(parts) >= 4:
                mode, flags, path, who = parts[0], parts[1], parts[2], parts[3]
                if mode != "None":
                    writes = bool(set("wax+") & set(mode))
                else:
                    writes = flags.isdigit() and bool(int(flags) & (os.O_WRONLY | os.O_RDWR))
                opens.append((writes, path, who))
        out.append({"argv": argv, "opens": opens})
    return out


def tool_of(argv: list) -> str:
    for index, arg in enumerate(argv[1:], 1):
        if arg == "-m" and index + 1 < len(argv):
            return "-m " + argv[index + 1]
        if arg == "-c":
            return "-c"
        if not arg.startswith("-"):
            return Path(arg).name
    return "?"


def kind(path: str) -> str:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    if name in ("main.xml", "english.txt", "BUILD_INFO.json"):
        return name
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else "(no suffix)"


def summarise(groups: dict) -> dict:
    out = {}
    for tool, processes in groups.items():
        entry = {"read": {}, "write": {}}
        for process in processes:
            for writes, path, who in process["opens"]:
                by = entry["write" if writes else "read"].setdefault(kind(path), {})
                by[who or "-"] = by.get(who or "-", 0) + 1
        out[tool] = entry
    return out


def written(logdir: Path, tree: Path, scratch: Path) -> dict:
    found = {}
    for process in read_opens(logdir):
        for writes, path, _who in process["opens"]:
            if not writes or "__pycache__" in path or ".pytest_cache" in path:
                continue
            target = Path(path) if os.path.isabs(path) else tree / path
            for root, token in ((scratch, "<scratch>"), (tree, "<tree>")):
                try:
                    rel = target.resolve().relative_to(root.resolve())
                except (ValueError, OSError):
                    continue
                if target.is_file():
                    found[f"{token}/{rel.as_posix()}"] = sha(target.read_bytes())
                break
    return found


def steady_text(text: str, tree: Path, scratch: Path) -> str:
    for path, token in ((scratch, "<scratch>"), (tree, "<tree>"), (REPO, "<repo>")):
        text = text.replace(str(path), token)
    text = re.sub(re.escape(tempfile.gettempdir()) + r"/[\w.\-]+", "<tmp>", text)
    text = re.sub(r'(File "[^"\n]*", line )\d+', r"\1N", text)      # a traceback names lines; a file that lost some keeps its error
    return re.sub(r"\b\d+(?:\.\d+)?\s?(?:s|ms|sec|secs|seconds)\b", "<time>", text)


# ---------------------------------------------------------------- the parts of the record
def part_build() -> None:
    rc = coverage_rc("build")
    logdir = OUT / "open-build"
    shutil.rmtree(logdir, ignore_errors=True)
    done = subprocess.run([str(PY), "tools/pd2-las/fresh.py", "check"], cwd=REPO, env=measured_env(logdir, rc, seed=False),
                          capture_output=True, text=True)
    lines = done.stdout.strip().splitlines()
    groups = {}
    for process in read_opens(logdir):
        groups.setdefault(tool_of(process["argv"]), []).append(process)
    for name in ("fresh.py", "determinism.py", "?", "-c"):
        groups.pop(name, None)                        # fresh.py copies the whole tree: not a tool's own reading
    save("build", {"rc": done.returncode, "summary": lines[-1] if lines else done.stderr[-300:],
                   "coverage": coverage_lines("build"), "opens": summarise(groups)})


def part_suite() -> None:
    rc = coverage_rc("tests")
    done = subprocess.run([str(PY), "-m", "pytest", "-q", "tests", "-rs"], cwd=REPO, env=measured_env(None, rc, seed=False),
                          capture_output=True, text=True)
    (OUT / "suite.txt").write_text(done.stdout + done.stderr)
    skips = re.findall(r"^SKIPPED \[(\d+)\] (.*)$", done.stdout, flags=re.M)
    last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else done.stderr[-300:]
    save("suite", {"rc": done.returncode, "summary": last, "skips": [[int(n), reason[:220]] for n, reason in skips],
                   "coverage": coverage_lines("tests")})


def part_lint() -> None:
    files = subprocess.run(["git", "ls-files", "tools"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split("\n")
    files = [name for name in files if name.endswith(".py") and not name.endswith("copies.py")]
    python = str(TOOLS / "lint" / "bin" / "python")
    done = subprocess.run([python, "-m", "pylint", "--disable=all", "--enable=duplicate-code", "--min-similarity-lines=6",
                           "--score=n", *files], cwd=REPO, capture_output=True, text=True)
    (OUT / "lint.txt").write_text(done.stdout + done.stderr)
    blocks = []
    for chunk in done.stdout.split("R0801: Similar lines in ")[1:]:
        spans = re.findall(r"^==([^:\n]+):\[(\d+):(\d+)\]", chunk, flags=re.M)
        if spans:
            blocks.append({"files": [name for name, _a, _b in spans], "lines": int(spans[0][2]) - int(spans[0][1])})
    version = subprocess.run([python, "-m", "pylint", "--version"], capture_output=True, text=True).stdout.split("\n")[0]
    save("lint", {"tool": version, "files": len(files), "blocks": len(blocks), "lines": sum(b["lines"] for b in blocks),
                  "largest": sorted(blocks, key=lambda b: -b["lines"])[:12]})


def part_golden(run: int) -> None:
    sys.path.insert(0, str(HERE))
    import fresh
    base = OUT / f"run{run}"
    shutil.rmtree(base, ignore_errors=True)
    tree, scratch = base / "tree", base / "scratch"
    scratch.mkdir(parents=True)
    fresh.copy_tree(tree)
    for name in ("Miranda_LAS", "Christie_LAS"):
        with zipfile.ZipFile(tree / "dist" / f"{name}.zip") as z:
            z.extractall(scratch / "packs")
    fill = {"{s}": str(scratch), "{m}": str(scratch / "packs/Miranda_LAS/assets/units/miranda/skins/miranda"),
            "{c}": str(scratch / "packs/Christie_LAS/assets/units/christie/skins/christie")}
    commands, groups = {}, {}
    for name, argv in GOLDEN:
        args = []
        for arg in argv:
            for token, value in fill.items():
                arg = arg.replace(token, value)
            args.append(arg)
        logdir = base / "open" / name
        started = time.time()
        try:
            done = subprocess.run([str(PY), *args], cwd=tree, env=measured_env(logdir), capture_output=True, text=True,
                                  errors="replace", timeout=600)
            rc, text = done.returncode, done.stdout + "\n--stderr--\n" + done.stderr
        except subprocess.TimeoutExpired:
            rc, text = "timeout", ""
        text = steady_text(text, tree, scratch)
        if name in WHOLE_TREE:
            text = re.sub(r"\d+", "N", text)
        (base / f"{name}.txt").write_text(text)
        commands[name] = {"rc": rc, "seconds": round(time.time() - started, 1), "lines": text.count("\n"), "printed": sha(text),
                          "written": written(logdir, tree, scratch)}
        groups[name] = read_opens(logdir) if logdir.is_dir() else []
    save(f"golden{run}", {"commands": commands, "opens": summarise(groups)})


def s_lines(path: Path) -> dict:
    """Function -> (calls, checksum of everything it returned, the same without float64)."""
    out = {}
    if path.is_file():
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith("S "):
                parts = line.split()
                out[parts[1]] = parts[2:5]
    return out


def r_values(path: Path) -> dict:
    """Function -> the distinct checksums of what its first 40 calls returned."""
    out = {}
    if path.is_file():
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith("R "):
                parts = line.split()
                out.setdefault(parts[1].rsplit("#", 1)[0], set()).add(parts[2])
    return out


def set_mark(values) -> list:
    """How many different values, and one checksum of them all: enough to tell the same set again."""
    return [str(len(values)), sha(",".join(sorted(values)))[:16]]


def part_trace(label: str) -> None:
    sys.path.insert(0, str(HERE))
    os.environ["PYTHONHASHSEED"] = "0"
    import fresh
    result = fresh.one_config("declared", list(fresh.BUILDERS), True)
    target = OUT / f"trace-{label}"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(REPO / "build" / "vary" / "declared" / "trace", target)
    want = {rel: (REPO / (rel + ".sha256")).read_text().split()[0] for rel in fresh.tracked_zips()}
    same = sum(1 for rel, digest in (result.get("sha256") or {}).items() if want.get(rel) == digest)
    save(f"trace-{label}", {"same": same, "of": len(want), "failed": result.get("failed"), "seconds": result.get("seconds")})


# ---------------------------------------------------------------- putting it together
def lane(steps: list, log: Path, lock) -> None:
    for step in steps:
        started = time.time()
        done = subprocess.run([str(PY), str(Path(__file__).resolve()), *step], cwd=REPO, capture_output=True, text=True)
        line = f"   {' '.join(step)}: exit {done.returncode} after {time.time() - started:.0f} s"
        with lock, open(log, "a") as out:
            out.write(line + "\n" + ((done.stdout + done.stderr)[-2500:] + "\n" if done.returncode else ""))
        print(line + ("\n" + (done.stdout + done.stderr)[-1200:] if done.returncode else ""), flush=True)


def record() -> int:
    ensure_tools()
    shutil.rmtree(OUT / "parts", ignore_errors=True)
    log = OUT / "record.log"
    log.write_text("")
    lock = threading.Lock()
    lanes = [[["_build"], ["_suite"], ["_lint"]], [["_golden", "1"], ["_trace", "a"], ["_trace", "b"], ["_golden", "2"]]]
    threads = [threading.Thread(target=lane, args=(steps, log, lock)) for steps in lanes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return assemble()


def assemble() -> int:
    build, suite, lint = part("build"), part("suite"), part("lint")
    golden, traces = [part("golden1"), part("golden2")], [part("trace-a"), part("trace-b")]
    outputs = {}
    for name, first in (golden[0].get("commands") or {}).items():
        second = (golden[1].get("commands") or {}).get(name) or {}
        again = second.get("written") or {}
        files = {path: digest for path, digest in first["written"].items() if again.get(path) == digest}
        outputs[name] = {"rc": first["rc"], "lines": first["lines"],
                         "printed": first["printed"] if (first["rc"], first["printed"]) == (second.get("rc"), second.get("printed")) else None,
                         "written": files, "unsteady_files": sorted((set(first["written"]) | set(again)) - set(files))}
    steady, unsteady = {}, {}
    for log in sorted((OUT / "trace-a").glob("*.log")):
        a, b = s_lines(log), s_lines(OUT / "trace-b" / log.name)
        va, vb = r_values(log), r_values(OUT / "trace-b" / log.name)
        steady[log.stem] = {name: value + (set_mark(va[name]) if name in va and va[name] == vb.get(name) else ["-", "-"])
                            for name, value in sorted(a.items()) if b.get(name) == value}
        unsteady[log.stem] = sorted((set(a) | set(b)) - set(steady[log.stem]))
    jobs = {"read": {}, "write": {}}
    for source in (build.get("opens") or {}, golden[0].get("opens") or {}):
        for tool, entry in source.items():
            for mode in ("read", "write"):
                for k, by in entry[mode].items():
                    for who in by:
                        jobs[mode].setdefault(k, {}).setdefault(who, set()).add(tool)
    jobs = {mode: {k: {who: sorted(tools) for who, tools in sorted(by.items())} for k, by in sorted(kinds.items())}
            for mode, kinds in jobs.items()}
    cover = reach(build.get("coverage") or {}, suite.get("coverage") or {})
    reference = {"base": BASE, "build": build.get("summary"), "suite": {k: suite.get(k) for k in ("rc", "summary", "skips")},
                 "lint": lint, "outputs": outputs,
                 "trace": {"runs": [{k: t.get(k) for k in ("same", "of", "failed")} for t in traces],
                           "functions": {k: len(v) for k, v in steady.items()}, "unsteady": unsteady},
                 "reach": cover, "jobs": {mode: {k: v for k, v in kinds.items() if k in INTEREST} for mode, kinds in jobs.items()}}
    (EVIDENCE / "trace").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "reference.json").write_text(json.dumps(reference, indent=1, sort_keys=True) + "\n")
    for builder, rows in steady.items():
        (EVIDENCE / "trace" / f"{builder}.txt").write_text("".join(f"{name} {' '.join(value)}\n" for name, value in rows.items()))

    say = [f"build: {build.get('summary')} (exit {build.get('rc')})", f"suite: {suite.get('summary')} (exit {suite.get('rc')})"]
    reasons = {}
    for count, reason in suite.get("skips") or []:
        key = re.sub(r"^\S+:\d+: ", "", reason)[:110]
        reasons[key] = reasons.get(key, 0) + count
    say += [f"   skipped {n}: {key}" for key, n in sorted(reasons.items(), key=lambda kv: -kv[1])[:14]]
    say.append("trace: " + "; ".join(f"{t.get('same')} of {t.get('of')} zips the tracked bytes" + (f", FAILED {t.get('failed')}" if t.get("failed") else "") for t in traces))
    say += [f"   {builder}: {len(rows)} functions steady, {len(unsteady[builder])} not: {', '.join(unsteady[builder][:6])}" for builder, rows in steady.items()]
    say.append(f"lint: {lint.get('tool')}: {lint.get('blocks')} duplicate blocks, {lint.get('lines')} lines, in {lint.get('files')} files")
    say += [f"   {b['lines']:3d} lines: {' | '.join(b['files'])}" for b in (lint.get("largest") or [])[:10]]
    say.append("outputs (exit, lines printed, files written, steady text, unsteady files):")
    say += [f"   {name:34s} {str(o['rc']):>7s} {o['lines']:5d} {len(o['written']):3d} {'yes' if o['printed'] else 'NO ':3s} {len(o['unsteady_files'])}"
            for name, o in outputs.items()]
    say.append("reach (functions, reached by a build, by a test; then those reached by neither):")
    for rel, row in cover.items():
        say.append(f"   {rel}: {row['functions']} / {row['build']} / {row['tests']}; neither: {', '.join(row['neither'][:18])}"
                   + (f" (+{len(row['neither']) - 18})" if len(row['neither']) > 18 else ""))
    say.append("who opens what (function <- tools):")
    for mode in ("write", "read"):
        for k in INTEREST:
            by = jobs[mode].get(k)
            if by:
                say.append(f"   {mode} {k}: " + "; ".join(f"{who} <- {','.join(t.replace('.py', '') for t in tools)[:70]}" for who, tools in by.items())[:520])
    text = "\n".join(say)
    (EVIDENCE / "record.txt").write_text(text + "\n")
    print(text)
    ok = build.get("rc") == 0 and all(t.get("same") == t.get("of") and t.get("of") for t in traces) and bool(outputs)
    return 0 if ok else 1


# ================================================================ compare: the copies, on real files
MISSING = object()

OBJECT = [("name_hash", "name_hash"), ("anim_ids", "anims"), ("matrix", "matrix"), ("pos", "pos"), ("parent_id", "parent")]
PAIRS = {   # what dmodel calls a value, what diesel_model calls it
    "object3D": OBJECT + [("remaining", "tail")],
    "model_data": OBJECT + [("version", "version"), ("passthrough_id", "passthroughgp"), ("topologyip_id", "topologyip"),
                            ("render_atoms", "atoms"), ("matgroup_id", "matgroup"), ("lightset_id", "lightset"), ("properties", "props"),
                            ("bounds_min", "bounds_min"), ("bounds_max", "bounds_max"), ("bounding_radius", "bounding_radius"),
                            ("bounding_int", "bounding_int"), ("skinbones_id", "skinbones"), ("remaining", "remaining")],
    "topology": [("primitive", "primitive"), ("faces", "indices"), ("items2", "items2"), ("name_hash", "name_hash"), ("remaining", "remaining")],
    "material": [("name_hash", "name_hash"), ("skipped", "skipped"), ("items", "items"), ("remaining", "remaining")],
    "material_group": [("items", "material_ids"), ("remaining", "remaining")],
    "skinbones": [("bone_mappings", "maps"), ("root_bone_id", "root"), ("object_ids", "objects"), ("rotations", "rotations"),
                  ("global_skin_transform", "global"), ("remaining", "remaining")],
    "geometry": [("vert_count", "vert_count"), ("header sizes", "header sizes"), ("header types", "header types"), ("positions", "verts"),
                 ("normals", "normals"), ("uvs", "uv0"), ("joints", "blendindices"), ("weights3", "blendweights"), ("packed_vu", "uvdir_v"),
                 ("name_hash", "name_hash"), ("remaining", "remaining")],
    "passthroughGP": [("geometry_id", "geometry"), ("topology_id", "topology")],
    "topologyIP": [("topology_id", "topology")],
}

SWAP_HEAD = '''

# -- appended for one test run: functions of this copy are replaced by the other copy's --
import importlib.util as _swap_util
import pathlib as _swap_path
import sys as _swap_sys


def _other_copy(rel):
    path = _swap_path.Path(__file__).resolve().parent / rel
    spec = _swap_util.spec_from_file_location("_other_copy_" + path.stem, str(path))
    module = _swap_util.module_from_spec(spec)
    _swap_sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


'''
MODEL_TESTS = ["tests/test_build_models.py", "tests/test_bust_variant.py", "tests/test_christie_las.py", "tests/test_determinism.py",
               "tests/test_diesel_model.py", "tests/test_fps_hands.py", "tests/test_hands_graft.py", "tests/test_pd2_las.py",
               "tests/test_pd2_las_invariants.py", "tests/test_render_mesh_skeleton.py"]
SWAPS = [
    ("dmodel with the hash of diesel_model", "tools/pd2-port/dmodel.py",
     '_o = _other_copy("../pd2-las/diesel_model.py")\n\n\ndef hash64(k, level=0):\n    return _o.hash64(k, level)\n\n\ndef hash_str(s):\n    return _o.hash64(s)\n',
     ["tests/test_las_pack.py", "tests/test_christie_las.py", "tests/test_pd2_las.py"]),
    ("diesel_model with the hash of dmodel", "tools/pd2-las/diesel_model.py",
     '_o = _other_copy("../pd2-port/dmodel.py")\n\n\ndef hash64(data, level=0):\n    return _o.hash64(data.encode("utf-8") if isinstance(data, str) else data, level)\n',
     MODEL_TESTS),
    ("las_pack with render_unit_xml and zip_pack of las_outfit_pack", "tools/pd2-las/las_pack.py",
     '_o = _other_copy("las_outfit_pack.py")\nrender_unit_xml = _o.render_unit_xml\nzip_pack = _o.zip_pack\n',
     ["tests/test_pd2_las.py", "tests/test_bust_variant.py"]),
    ("las_outfit_pack with render_unit_xml and zip_pack of las_pack", "tools/pd2-las/las_outfit_pack.py",
     '_o = _other_copy("las_pack.py")\nrender_unit_xml = _o.render_unit_xml\nzip_pack = _o.zip_pack\n',
     ["tests/test_skyrim_materials.py", "tests/test_glove_adapter.py", "tests/test_glove_behavior_lua.py", "tests/test_christie_las.py"]),
]


def bump(table: dict, key: str, n: int = 1) -> None:
    table[key] = table.get(key, 0) + n


def flat(value) -> list:
    out = []

    def walk(item):
        if isinstance(item, (list, tuple)):
            for inner in item:
                walk(inner)
        elif isinstance(item, dict):
            for key in sorted(item):
                walk(item[key])
        else:
            out.append(item)

    walk(value)
    return out


def differ(a, b):
    """None when both hold the same values in the same order; else where they part."""
    fa, fb = flat(a), flat(b)
    if fa == fb:
        return None
    for index, (x, y) in enumerate(zip(fa, fb)):
        if x != y and not (x != x and y != y):
            return f"item {index} of {len(fa)}/{len(fb)}: {str(x)[:40]} / {str(y)[:40]}"
    return None if len(fa) == len(fb) else f"{len(fa)} items / {len(fb)} items"


def base_modules() -> dict:
    """The copies as they were at BASE, imported from an export of that commit."""
    import importlib
    root = OUT / "base"
    if not (root / "tools" / "pd2-las" / "las_pack.py").is_file():
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        archive = subprocess.run(["git", "archive", BASE, "tools"], cwd=REPO, capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(root)], input=archive, check=True)
    sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != HERE]
    sys.path[:0] = [str(root / "tools" / "pd2-las"), str(root / "tools" / "pd2-port"), str(root / "tools")]
    sys.path.append(str(TOOLS / "t2d"))
    found = {"errors": {}}
    for name in ("dmodel", "diesel_model", "me2_dae", "dds", "dds_encode", "las_pack", "las_outfit_pack", "build_christie_las", "build_las_pack"):
        try:
            found[name] = importlib.import_module(name)
        except Exception as error:
            found[name] = None
            found["errors"][name] = f"{type(error).__name__}: {error}"[:200]
    return found


def group_of(pack: str) -> str:
    for prefix, group in (("Miranda_L4D2", "heads L4D2"), ("Miranda_Romance", "heads Romance"), ("Geralt", "head Geralt"),
                          ("Christie", "Christie"), ("Miranda", "Miranda")):
        if pack.startswith(prefix):
            return group
    return pack


def las_models() -> Path:
    """The LAS mod as Vladik268/P2 has it at b7c38c1d: 34 models and their textures, made by other people."""
    root = REPO / "build" / "merge" / "p2"
    if not any(root.rglob("*.model")):
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        for command in (["git", "init", "-q"], ["git", "remote", "add", "origin", "https://github.com/Vladik268/P2"],
                        ["git", "sparse-checkout", "set", "--no-cone", "/mod/Legendary Armour Skins/"],
                        ["git", "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", "b7c38c1d358fe054df51201788126c25a0da1938"],
                        ["git", "checkout", "-q", "FETCH_HEAD"]):
            subprocess.run(command, cwd=root, check=True)
    return root


def corpus() -> tuple:
    models, textures = {}, {}

    def add(table, data, label, group):
        entry = table.setdefault(sha(data), {"data": data, "where": [], "groups": []})
        entry["where"].append(label)
        if group not in entry["groups"]:
            entry["groups"].append(group)

    for path in sorted((REPO / "dist").glob("*.zip")) + sorted((REPO / "build" / "pd2-las").glob("*.zip")):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                table = models if name.endswith(".model") else textures if name.endswith(".texture") else None
                if table is not None:
                    add(table, z.read(name), f"{path.stem}:{name.rsplit('/', 1)[-1]}", group_of(path.stem))
    for root, group in ((REPO / "build" / "pd2-las" / "2b", "2B"), (las_models(), "LAS mod")):
        for path in sorted(root.rglob("*")):
            if ".git" in path.parts or not path.is_file():
                continue
            table = models if path.suffix == ".model" else textures if path.suffix in (".texture", ".dds") else None
            if table is not None:
                add(table, path.read_bytes(), f"{group}:{path.name}", group)
    return models, textures


def compare_models(mods: dict, models: dict) -> dict:
    import inspect
    import random
    import struct
    dm, ds = mods["dmodel"], mods["diesel_model"]
    hashlist = dm.Hashlist()
    decoders = {"object3D": ds.decode_object3d, "model_data": ds.decode_model_data, "skinbones": ds.decode_skinbones,
                "geometry": ds.decode_geometry, "topology": ds.decode_topology, "material": ds.decode_material,
                "material_group": ds.decode_material_group, "custom_hashlist": ds.decode_custom_hashlist,
                "passthroughGP": ds.decode_passthroughgp, "topologyIP": ds.decode_topologyip}
    encoders = {"object3D": lambda d, p: ds.encode_object3d(d) + p[d["tail_off"]:], "model_data": lambda d, p: ds.encode_model_data(d),
                "skinbones": lambda d, p: ds.encode_skinbones(d), "geometry": lambda d, p: ds.encode_geometry(d),
                "topology": lambda d, p: ds.encode_topology(d), "material": lambda d, p: ds.encode_material(d),
                "material_group": lambda d, p: ds.encode_material_group(d), "custom_hashlist": lambda d, p: ds.encode_custom_hashlist(d),
                "passthroughGP": lambda d, p: ds.encode_passthroughgp(d), "topologyIP": lambda d, p: ds.encode_topologyip(d)}
    out = {"containers": {}, "whole": {}, "sections": {}, "tags": {}, "reads": {}, "fields": {}, "examples": {}, "channels": {},
           "roundtrip": {}, "roundtrip_examples": {}, "names": {}}
    names, matrices = set(), []
    for entry in models.values():
        data, group, label = entry["data"], entry["groups"][0], entry["where"][0]
        try:
            sections, legacy, version, _size = dm.read_container(data)
        except Exception as error:
            bump(out["containers"], f"{group} | unreadable: {type(error).__name__}")
            continue
        kind_ = "legacy" if legacy else f"DODB v{version}"
        if legacy and struct.unpack_from("<I", data)[0] != 0xFFFFFFFF:
            kind_ = "legacy without the marker"
        bump(out["containers"], f"{group} | {kind_}")
        try:
            dm.DieselModel.from_bytes(data)
            bump(out["whole"], f"{kind_} | dmodel reads the file")
        except Exception as error:
            bump(out["whole"], f"{kind_} | dmodel stops: {type(error).__name__}")
        try:
            whole = ds.ModelFile.read(data)
            bump(out["whole"], f"{kind_} | diesel_model reads the file")
            same_list = [(s.type, s.id, len(s.payload)) for s in whole.sections] == [(s.type, s.id, s.size) for s in sections]
            bump(out["sections"], f"{kind_} | section lists " + ("the same" if same_list else "DIFFERENT"))
            bump(out["roundtrip"], f"{group} | whole file | " + ("same bytes" if whole.write() == data else "OTHER BYTES"))
        except Exception as error:
            bump(out["whole"], f"{kind_} | diesel_model stops: {type(error).__name__}: {str(error)[:50]}")
        listed, hashes = set(), []
        for sec in sections:
            payload = data[sec.start:sec.end]
            in_a, in_b = dm.TAGS.get(sec.type), ds.TAG_NAMES.get(sec.type)
            bump(out["tags"], "both name it the same" if in_a and in_a == in_b else "only dmodel names it" if in_a and not in_b
                 else "only diesel_model names it" if in_b and not in_a else "they name it differently" if in_a else "neither names it")
            tag, obj, d = sec.tag, None, None
            state_a = state_b = "has no reader"
            if tag in dm.PARSERS:
                try:
                    reader = dm.BR(data)
                    reader.p = sec.start
                    obj = dm.PARSERS[tag]()
                    obj.parse(reader, sec, hashlist)
                    state_a = "reads"
                except Exception as error:
                    obj, state_a = None, f"stops ({type(error).__name__})"
            if tag in decoders:
                try:
                    d = decoders[tag](payload)
                    state_b = "reads"
                except Exception as error:
                    d, state_b = None, f"stops ({type(error).__name__}: {str(error)[:40]})"
            bump(out["reads"], f"{kind_} | {tag} | dmodel {state_a} | diesel_model {state_b}")
            if tag == "geometry" and len(payload) >= 8:
                for index in range(min(struct.unpack_from("<I", payload, 4)[0], 40)):
                    size, typ = struct.unpack_from("<II", payload, 8 + 8 * index)
                    bump(out["channels"], f"{kind_} | type {typ:2d} size {size}")
            if d is not None:
                try:
                    back = encoders[tag](d, payload) == payload
                    bump(out["roundtrip"], f"{group} | {tag} | " + ("same bytes" if back else "OTHER BYTES"))
                    if not back:
                        out["roundtrip_examples"].setdefault(f"{group} | {tag}", f"{label} section {sec.id}")
                except Exception as error:
                    bump(out["roundtrip"], f"{group} | {tag} | encoder stops ({type(error).__name__})")
                if tag == "custom_hashlist":
                    listed.update(d["names"])
                if "name_hash" in d:
                    hashes.append(d["name_hash"])
                if tag == "skinbones" and len(matrices) < 3000:
                    matrices.extend(d["rotations"][:40])
            if obj is None or d is None:
                continue
            for attr, key in PAIRS.get(tag, []):
                if attr == "header sizes":
                    a, b = [h[0] for h in obj.headers], [h["item_size"] for h in d["headers"]]
                elif attr == "header types":
                    a, b = [h[1] for h in obj.headers], [ds.to_disk_type(h["enum_type"]) for h in d["headers"]]
                else:
                    a = getattr(obj, attr, MISSING)
                    b = payload[d["tail_off"]:] if key == "tail" else d.get(key, MISSING)
                    if attr == "weights3" and a is not MISSING:
                        a = [tuple(w) + (0.0,) * (3 - len(w)) for w in a]
                if a is MISSING and b is MISSING:
                    continue
                name = f"{kind_} | {tag} | {attr}"
                row = out["fields"].setdefault(name, [0, 0])
                if a is MISSING or b is MISSING:
                    where = "only diesel_model gives it" if a is MISSING else "only dmodel gives it"
                else:
                    where = differ(a, b)
                row[1 if where else 0] += 1
                if where and len(out["examples"].setdefault(name, [])) < 2:
                    out["examples"][name].append(f"{label} section {sec.id}: {where}")
        names.update(listed)
        if listed:
            known = {ds.hash64(name) for name in listed}
            bump(out["names"], f"{group} | name hashes that are the hash of a name the file lists", sum(1 for h in hashes if h in known))
            bump(out["names"], f"{group} | name hashes that are not", sum(1 for h in hashes if h not in known))
    rng = random.Random(1)
    probes = [name.encode("utf-8") for name in sorted(names)]
    probes += [bytes(rng.randrange(256) for _ in range(rng.randrange(0, 49))) for _ in range(20000)]
    out["hash"] = {"names from the files": len(names), "probes": len(probes),
                   "different values": sum(1 for k in probes if dm.hash64(k) != ds.hash64(k)),
                   "different with a level": sum(1 for k in probes[:3000] for level in (1, 0xDEADBEEF) if dm.hash64(k, level) != ds.hash64(k, level)),
                   "different for a name given as text": sum(1 for name in names if dm.hash_str(name) != ds.hash64(name))}
    other, worst, unlike, failed = mods.get("me2_dae"), 0.0, 0, 0
    for m in matrices:
        try:
            a = [x for row in dm.minv([list(m[i * 4:(i + 1) * 4]) for i in range(4)]) for x in row]
            b = list(ds.mat_inv(tuple(m)))
            worst = max(worst, max(abs(x - y) for x, y in zip(a, b)))
            unlike += struct.pack("<16f", *a) != struct.pack("<16f", *b)
        except Exception:
            failed += 1
    out["inverse"] = {"dmodel.minv and me2_dae.minv are the same text": bool(other) and inspect.getsource(dm.minv) == inspect.getsource(other.minv),
                      "matrices": len(matrices), "largest difference to diesel_model.mat_inv": worst,
                      "different once packed as float32": unlike, "could not be inverted": failed}
    out["tag tables"] = {"dmodel": len(dm.TAGS), "diesel_model": len(ds.TAG_NAMES),
                         "same number for the same name": sum(1 for t, n in ds.TAG_NAMES.items() if dm.TAGS.get(t) == n),
                         "only in dmodel": sorted(n for t, n in dm.TAGS.items() if t not in ds.TAG_NAMES)}
    return out


def compare_textures(mods: dict, textures: dict) -> dict:
    import struct
    import numpy as np
    da, db = mods["dds"], mods["dds_encode"]
    try:
        import texture2ddecoder
    except ImportError:
        texture2ddecoder = None
    out = {"fourcc": {}, "header": {}, "header_examples": {}, "levels": {}, "decode": {}, "order": {}, "fix": {}, "encode": [], "downsample": {}}
    tried, sample = {}, []

    def outside(payload, across, down):
        return np.frombuffer(texture2ddecoder.decode_bc3(bytes(payload), across, down), dtype=np.uint8).reshape(down, across, 4)[..., [2, 1, 0, 3]]

    for entry in textures.values():
        raw, group = entry["data"], entry["groups"][0]
        if raw[:4] != b"DDS " or len(raw) < 128:
            bump(out["fourcc"], f"{group} | not a DDS file")
            continue
        height, width, _pitch, _depth, mips = struct.unpack_from("<5I", raw, 12)
        fourcc = raw[84:88]
        bump(out["fourcc"], f"{group} | {fourcc.decode('ascii', 'replace') if any(fourcc) else 'no fourcc'}")
        if fourcc != b"DXT5" or not width or not height or max(width, height) > 4096:
            continue
        count, table, offset = max(1, mips), [], 128
        for level in range(count):
            w, h = max(1, width >> level), max(1, height >> level)
            size = ((w + 3) // 4) * ((h + 3) // 4) * 16
            if offset + size > len(raw):
                break
            table.append((offset, w, h, size))
            offset += size
        if not table:
            continue
        complete = len(table) == count and offset == len(raw)
        full = width == height and width & (width - 1) == 0 and count == width.bit_length()
        general = db._dds_header(width, height, b"DXT5", mips=count)
        by_b, by_a = raw[:128] == general, "cannot write it"
        if full and complete:
            try:
                by_a = raw[:128] == da.pack_dds([raw[o:o + s] for o, _w, _h, s in table], width)[:128]
            except Exception as error:
                by_a = f"stops ({type(error).__name__})"
        bump(out["header"], f"{group} | {'full chain' if full else 'one level' if count == 1 else 'other'} | pack_dds: {by_a} | _dds_header: {by_b}")
        if not by_b:
            out["header_examples"].setdefault(group, f"{entry['where'][0]}: bytes {[i for i in range(128) if raw[i] != general[i]][:10]} are not what _dds_header writes")
        try:
            size_a, mips_a, view = da.dds_mip0_slice(raw)
            table_a = "agrees" if (size_a, mips_a, bytes(view)) == (width, mips, raw[128:128 + table[0][3]]) else "DISAGREES"
        except Exception as error:
            table_a = f"refuses ({str(error)[:40]})"
        try:
            table_b = "agrees" if db.bc3_levels(raw) == [(o, w, h) for o, w, h, _s in table] else "DISAGREES"
        except Exception as error:
            table_b = f"refuses ({str(error)[:40]})"
        bump(out["levels"], f"{group} | dds_mip0_slice {table_a} | bc3_levels {table_b}")
        for level, (start, w, h, size) in enumerate(table):
            across, down = (w + 3) // 4 * 4, (h + 3) // 4 * 4
            payload = raw[start:start + size]
            a = da.decode_dxt5(payload, across, down)[:h, :w].astype(np.int16)
            b = db.decode_bc3_level(raw, level).astype(np.int16) if table_b == "agrees" else None
            c = outside(payload, across, down)[:h, :w].astype(np.int16) if texture2ddecoder else None
            for name, x, y in (("dds.py against Pillow", a, b), ("Pillow against texture2ddecoder", b, c), ("dds.py against texture2ddecoder", a, c)):
                if x is None or y is None:
                    continue
                gap = np.abs(x - y)
                row = out["decode"].setdefault(f"{group} | {name}", {"texels": 0, "colour differs": 0, "colour by at most": 0, "alpha differs": 0, "alpha by at most": 0})
                row["texels"] += w * h
                row["colour differs"] += int((gap[..., :3].max(axis=2) > 0).sum())
                row["colour by at most"] = max(row["colour by at most"], int(gap[..., :3].max()))
                row["alpha differs"] += int((gap[..., 3] > 0).sum())
                row["alpha by at most"] = max(row["alpha by at most"], int(gap[..., 3].max()))
        blocks = np.frombuffer(raw, dtype=np.uint8, count=(offset - 128) // 16 * 16, offset=128).reshape(-1, 16)
        c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
        c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
        bits = (blocks[:, 12].astype(np.uint32) | (blocks[:, 13].astype(np.uint32) << 8)
                | (blocks[:, 14].astype(np.uint32) << 16) | (blocks[:, 15].astype(np.uint32) << 24))
        low, equal = c0 < c1, (c0 == c1) & (bits != 0)
        row = out["order"].setdefault(group, {"textures": 0, "blocks": 0, "c0 < c1": 0, "c0 = c1 with indices": 0,
                                              "textures with c0 < c1": 0, "textures with c0 = c1 and indices": 0})
        row["textures"] += 1
        row["blocks"] += len(blocks)
        row["c0 < c1"] += int(low.sum())
        row["c0 = c1 with indices"] += int(equal.sum())
        row["textures with c0 < c1"] += bool(low.any())
        row["textures with c0 = c1 and indices"] += bool(equal.any())
        first = table[0][3] // 16
        if full and width <= 2048 and (low[:first].any() or equal[:first].any()) and tried.get(group, 0) < 8:
            tried[group] = tried.get(group, 0) + 1
            mip0 = raw[128:128 + table[0][3]]
            fixed = np.frombuffer(da.fix_misordered_blocks(mip0, width)[0], dtype=np.uint8).reshape(-1, 16)
            other = np.frombuffer(mip0, dtype=np.uint8).reshape(-1, 16).copy()
            db._enforce_c0_ge_c1(other)
            unlike = (fixed != other).any(axis=1)
            row = out["fix"].setdefault(group, {"textures": 0, "blocks with c0 < c1": 0, "of those, fixed to other bytes by the two": 0,
                                                "blocks with c0 = c1 and indices": 0, "of those, left by one and cleared by the other": 0,
                                                "other blocks the two leave different": 0,
                                                "texels texture2ddecoder shows changed by fix_misordered_blocks": 0,
                                                "texels texture2ddecoder shows changed by _enforce_c0_ge_c1": 0})
            row["textures"] += 1
            row["blocks with c0 < c1"] += int(low[:first].sum())
            row["of those, fixed to other bytes by the two"] += int((unlike & low[:first]).sum())
            row["blocks with c0 = c1 and indices"] += int(equal[:first].sum())
            row["of those, left by one and cleared by the other"] += int((unlike & equal[:first]).sum())
            row["other blocks the two leave different"] += int((unlike & ~low[:first] & ~equal[:first]).sum())
            if texture2ddecoder:
                before = outside(mip0, width, width)
                row["texels texture2ddecoder shows changed by fix_misordered_blocks"] += int((outside(fixed.tobytes(), width, width) != before).any(axis=2).sum())
                row["texels texture2ddecoder shows changed by _enforce_c0_ge_c1"] += int((outside(other.tobytes(), width, width) != before).any(axis=2).sum())
        if full and width >= 256 and group not in ("2B", "LAS mod") and len(sample) < 12 and texture2ddecoder:
            start, w, h, size = table[width.bit_length() - 8]
            sample.append((entry["where"][0], np.ascontiguousarray(outside(raw[start:start + size], w, h))))
    for label, image in sample:
        try:
            made = {"dds.encode_dxt5": bytes(da.encode_dxt5(image)), "dds_encode.rgba_to_bc3_dds": bytes(db.rgba_to_bc3_dds(image)[128:]),
                    "dds_encode.encode_bc3_texels": db.encode_bc3_texels(db.image_to_texels(image)).tobytes()}
            row = {"texture": label, "blocks": len(made["dds.encode_dxt5"]) // 16}
            keys = list(made)
            for i, x in enumerate(keys):
                got = outside(made[x], 128, 128).astype(np.float64)
                row[f"error of {x} (colour, alpha)"] = [round(float(((got[..., :3] - image[..., :3]) ** 2).mean()), 2),
                                                        round(float(((got[..., 3] - image[..., 3]) ** 2).mean()), 2)]
                for y in keys[i + 1:]:
                    same = (np.frombuffer(made[x], dtype=np.uint8).reshape(-1, 16) == np.frombuffer(made[y], dtype=np.uint8).reshape(-1, 16)).all(axis=1)
                    row[f"same blocks: {x} and {y}"] = int(same.sum())
            out["encode"].append(row)
            small, other = da.downsample2x2(image), np.floor(db.box_reduce(image, 2) + 0.5).astype(np.uint8)
            bump(out["downsample"], "values", int(small.size))
            bump(out["downsample"], "different between downsample2x2 and box_reduce rounded", int((small != other).sum()))
        except Exception as error:
            out["encode"].append({"texture": label, "FAILED": f"{type(error).__name__}: {error}"[:200]})
    return out


def pack_text(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        top = names[0].split("/")[0]

        def text(name):
            return z.read(name).decode("utf-8", "replace")

        return {"top": top, "main": text(f"{top}/main.xml") if f"{top}/main.xml" in names else "",
                "hooks": {n.rsplit("/", 1)[-1]: text(n) for n in names if n.endswith(".lua")},
                "loc": next((text(n) for n in names if n.endswith("english.txt")), ""),
                "units": {n: text(n) for n in names if n.endswith(".unit")},
                "textures": sorted(n.rsplit("/", 1)[-1][:-len(".texture")] for n in names if n.endswith(".texture") and "/units/" in n),
                "other": {n: text(n) for n in names if n.endswith((".object", ".material_config"))}}


def verdict(made: str, tracked: str):
    import difflib
    if made == tracked:
        return "the tracked bytes"
    if made.rstrip("\n") == tracked.rstrip("\n"):
        return "the tracked bytes but for the last newline"
    lines = [line for line in difflib.unified_diff(tracked.splitlines(), made.splitlines(), lineterm="", n=0)
             if line[:1] in "+-" and line[:3] not in ("+++", "---")]
    return [line.replace("\t", "\\t")[:150] for line in lines[:14]] + ([f"... {len(lines) - 14} more"] if len(lines) > 14 else [])


def lua_code(text: str) -> list:
    text = re.sub(r"--\[\[.*?\]\]", "", text, flags=re.S)
    return [line.strip() for line in (re.sub(r"--.*$", "", raw) for raw in text.splitlines()) if line.strip()]


def render_with(mods: dict, writer: str, data: dict, files: dict) -> dict:
    item, stems = data["item"], files["textures"]
    if writer == "las_pack":
        m = mods["las_pack"]
        ident = m.PackIdentity(item, data["display"], data["description"], pack_dir_name=files["top"])
        return {"hook": m.render_hook_lua(ident), "loc": m.render_localization(ident), "main": m.render_main_xml(ident)}
    if writer == "build_christie_las":
        m = mods["build_christie_las"]
        ident = m.Identity(item_id=item, pack_dir_name=files["top"], display_name=data["display"], description=data["description"],
                           glove_adapter=data["glove"])
        made = {"hook": m.render_hook_lua(ident, data["fps"]), "loc": m.render_localization(ident), "main": m.render_main_xml(ident, stems, data["fps"])}
        if data["glove"]:
            made["glove"] = m.render_glove_adapter_lua(ident)
        return made
    if writer == "las_outfit_pack":
        m = mods["las_outfit_pack"]
        base = f"units/{item}/skins/{item}"
        patch = {"ITEM_ID": item, "CATEGORY": data["category"], "UNIT_BASE": base, "GUI_BASE": f"guis/dlcs/{item}/armor_skins",
                 "TPP_UNIT": f"{base}/{item}", "FPS_UNIT": f"{base}/fps_{item}", "DISPLAY_NAME": data["display"]}
        saved = {key: getattr(m, key) for key in patch}
        for key, value in patch.items():
            setattr(m, key, value)
        try:
            hands = "adapter" if data["glove"] else "authored"
            made = {"hook": m.render_hook_lua(data["fps"], hands), "loc": m.render_localization(), "main": m.render_main_xml(stems, data["fps"], hands)}
            if data["glove"]:
                made["glove"] = m.render_glove_adapter_lua()
        finally:
            for key, value in saved.items():
                setattr(m, key, value)
        return made
    if files["top"].lower().startswith("lawson"):
        m = mods["build_las_pack"]
        return {"hook": m.hook_lua(), "loc": m.localization(), "main": m.main_xml()}
    raise ValueError("it writes one pack only, lawson_las")


def compare_writers(mods: dict) -> dict:
    import difflib
    lp, lop, chris, law = mods["las_pack"], mods["las_outfit_pack"], mods.get("build_christie_las"), mods.get("build_las_pack")
    out = {"flags in the code": {"las_pack": list(lp.FLAG_KEYS), "las_outfit_pack": list(lop.FLAG_KEYS),
                                 "build_christie_las": list(chris.FLAG_KEYS) if chris else None},
           "packs": {}, "unit": {}, "zip": {}, "glove": {}, "shape": {}}
    texts = {name: pack_text(REPO / "dist" / f"{name}.zip") for name in ("Miranda_LAS", "Miranda_Busty_LAS", "Christie_LAS", "Christie_LAS_Slim", "lawson_las")}
    for name, files in texts.items():
        hook_name = next(n for n in files["hooks"] if "glove" not in n)
        glove_name = next((n for n in files["hooks"] if "glove" in n), None)
        hook = files["hooks"][hook_name]
        item = re.search(r"^la\.(\w+) = \{", hook, flags=re.M).group(1)
        loc = json.loads(files["loc"])
        data = {"item": item, "category": re.search(r'category = "([^"]*)"', hook).group(1), "fps": "fps_unit" in hook,
                "display": loc.get(f"bm_askn_{item}"), "description": loc.get(f"bm_askn_{item}_desc"), "glove": glove_name is not None}
        tracked = {"hook": hook, "loc": files["loc"], "main": files["main"], "glove": files["hooks"].get(glove_name, "")}
        row = {"hook file": hook_name, "flags": re.findall(r"^\s*(\w+) = true", hook, flags=re.M), "first-person unit": data["fps"],
               "glove adapter": data["glove"], "textures": files["textures"], "writers": {}}
        for writer in ("las_pack", "build_christie_las", "las_outfit_pack", "build_las_pack"):
            try:
                made = render_with(mods, writer, data, files)
                row["writers"][writer] = {piece: verdict(text, tracked[piece]) for piece, text in made.items()}
            except Exception as error:
                row["writers"][writer] = f"cannot: {type(error).__name__}: {str(error)[:90]}"
        out["packs"][name] = row
        for member, text in files["units"].items():
            base = re.search(r'<object file="([^"]+)"', text).group(1)
            out["unit"][f"{name}:{member.rsplit('/', 1)[-1]}"] = {
                "las_pack": verdict(lp.render_unit_xml(base), text), "las_outfit_pack": verdict(lop.render_unit_xml(base), text),
                "build_las_pack": verdict(law.unit_xml(base.rsplit("/", 1)[-1]), text) if law else "not imported"}
        if glove_name and chris:
            ident = chris.Identity(item_id=item, pack_dir_name=files["top"], display_name=data["display"], description=data["description"], glove_adapter=True)
            a = chris.render_glove_adapter_lua(ident)
            saved, lop.ITEM_ID = lop.ITEM_ID, item
            try:
                b = lop.render_glove_adapter_lua()
            finally:
                lop.ITEM_ID = saved
            code_a, code_b = lua_code(a), lua_code(b)
            out["glove"][name] = {"build_christie_las": verdict(a, tracked["glove"]), "las_outfit_pack": verdict(b, tracked["glove"]),
                                  "lines": [len(a.splitlines()), len(b.splitlines())], "lines of Lua without comments": [len(code_a), len(code_b)],
                                  "same Lua without comments": code_a == code_b,
                                  "where the Lua differs": [line[:150] for line in difflib.unified_diff(code_a, code_b, lineterm="", n=0)
                                                            if line[:1] in "+-" and line[:3] not in ("+++", "---")][:16]}
    for suffix in (".object", ".material_config"):
        for fps in (False, True):
            pair = []
            for name, item in (("Miranda_LAS", "miranda"), ("Christie_LAS", "christie")):
                pair.append(next((text.replace(item, "ID") for member, text in texts[name]["other"].items()
                                  if member.endswith(suffix) and member.rsplit("/", 1)[-1].startswith("fps_") == fps), None))
            if pair[0] and pair[1]:
                out["shape"][f"{'first-person ' if fps else ''}{suffix}, Christie_LAS against Miranda_LAS with the names taken out"] = verdict(pair[1], pair[0])
    for path in sorted((REPO / "dist").glob("*.zip")):
        work = Path(tempfile.mkdtemp(prefix="zip-", dir=OUT))
        try:
            with zipfile.ZipFile(path) as z:
                z.extractall(work)
                members = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
                stamps = sorted({info.date_time[0] for info in z.infolist()})
            want, row, tops = sha(path.read_bytes()), {"year stamped": stamps}, [p for p in work.iterdir()]
            if len(tops) == 1 and tops[0].is_dir():
                for label, module in (("las_pack.zip_pack", lp), ("las_outfit_pack.zip_pack", lop)):
                    made = module.zip_pack(tops[0])
                    row[label] = "the tracked bytes" if sha(made.read_bytes()) == want else "other bytes"
                    made.unlink()
            else:
                row["zip_pack"] = f"cannot: {len(tops)} entries at the top"
            if law:
                law.write_zip(members, work / "again.zip")
                row["build_las_pack.write_zip"] = "the tracked bytes" if sha((work / "again.zip").read_bytes()) == want else "other bytes"
            out["zip"][path.stem] = row
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return out


def part_files() -> None:
    import traceback
    mods = base_modules()
    models, textures = corpus()
    groups = {}
    for table, what in ((models, "models"), (textures, "textures")):
        for entry in table.values():
            bump(groups, f"{entry['groups'][0]} | {what}, different files")
            bump(groups, f"{entry['groups'][0]} | {what}, places they are in", len(entry["where"]))
    result = {"copies that could not be imported": mods["errors"], "corpus": groups}
    for name, run in (("writers", lambda: compare_writers(mods)), ("models", lambda: compare_models(mods, models)),
                      ("textures", lambda: compare_textures(mods, textures))):
        try:
            result[name] = run()
        except Exception:
            result[name] = {"FAILED": traceback.format_exc()[-1800:]}
        save("cmp-files", result)


def worktree(path: Path) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(path)], cwd=REPO, capture_output=True)
    shutil.rmtree(path, ignore_errors=True)
    subprocess.run(["git", "worktree", "add", "--detach", "-f", str(path), BASE], cwd=REPO, check=True, capture_output=True)


def part_env() -> None:
    shown = {rel: subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=REPO, capture_output=True, text=True, check=True).stdout
             for rel in ("tools/pd2-las/bootstrap.sh", "tools/pd2-las/recover_env.sh", ".github/workflows/test.yml", ".github/workflows/lawson-las.yml")}
    out = {"pins": {rel: sorted({f"{a}=={b}" for a, b in re.findall(r"\b(pillow|numpy)==([0-9][0-9A-Za-z.]*)", text)}) for rel, text in shown.items()},
           "install lines": {rel: [" ".join(line.split())[:260] for line in text.splitlines() if "pip install" in line and not line.lstrip().startswith("#")]
                             for rel, text in shown.items()}}
    boot = shown["tools/pd2-las/bootstrap.sh"]
    venv_part = boot[boot.index('echo "== 1/5'):boot.index('echo "== 2/5')]
    listing = subprocess.run(["git", "grep", "-l", "-e", "lupa", "-e", "sourcepp", BASE, "--", "tests"], cwd=REPO, capture_output=True, text=True).stdout
    tests = sorted(line.split(":", 1)[1] for line in listing.splitlines() if ":" in line)
    made = {}
    for label in ("bootstrap", "recover"):
        tree = OUT / "env" / label
        worktree(tree)
        if label == "bootstrap":
            done = subprocess.run(["bash", "-c", "set -euo pipefail\n" + venv_part], cwd=tree, capture_output=True, text=True)
        else:
            done = subprocess.run(["bash", "tools/pd2-las/recover_env.sh"], cwd=tree, capture_output=True, text=True)
        python = str(tree / ".venv" / "bin" / "python")
        frozen = subprocess.run([python, "-m", "pip", "freeze"], capture_output=True, text=True).stdout.split()
        pip = subprocess.run([python, "-m", "pip", "--version"], capture_output=True, text=True).stdout.split(" from ")[0]
        ran = subprocess.run([python, "-m", "pytest", "-q", *tests, "-rs", "-p", "no:cacheprovider"], cwd=tree, capture_output=True, text=True)
        made[label] = {"exit": done.returncode, "last lines": (done.stdout + done.stderr).strip().splitlines()[-2:], "freeze": sorted(frozen), "pip": pip,
                       "tests that name lupa or sourcepp": {"files": tests, "result": (ran.stdout.strip().splitlines() or ["?"])[-1],
                                                            "skipped": [f"{n}: {why[:150]}" for n, why in re.findall(r"^SKIPPED \[(\d+)\] (.*)$", ran.stdout, flags=re.M)]}}
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=REPO, capture_output=True)
    a, b = set(made["bootstrap"]["freeze"]), set(made["recover"]["freeze"])
    out.update({"in both, same version": len(a & b), "only after the venv part of bootstrap.sh": sorted(a - b), "only after recover_env.sh": sorted(b - a),
                "bootstrap.sh": {k: v for k, v in made["bootstrap"].items() if k != "freeze"},
                "recover_env.sh": {k: v for k, v in made["recover"].items() if k != "freeze"}, "freeze after recover_env.sh": sorted(b)})
    save("cmp-env", out)


def part_tests() -> None:
    tree = OUT / "swap"
    worktree(tree)
    link = tree / "build" / "pd2-las" / "2b"
    if not link.exists():
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(REPO / "build" / "pd2-las" / "2b", link)
    out = {}

    def run(names):
        done = subprocess.run([str(PY), "-m", "pytest", "-q", *names, "-rf", "-p", "no:cacheprovider"], cwd=tree, capture_output=True, text=True)
        return (done.stdout.strip().splitlines() or ["?"])[-1], re.findall(r"^FAILED (\S+)", done.stdout, flags=re.M)

    for title, rel, patch, tests in SWAPS:
        target = tree / rel
        original = target.read_text(encoding="utf-8")
        target.write_text(original + SWAP_HEAD + patch, encoding="utf-8")
        try:
            result, failed = run(tests)
        finally:
            target.write_text(original, encoding="utf-8")
        row = {"tests": [name.rsplit("/", 1)[-1] for name in tests], "result": result, "failed": failed}
        if failed:
            row["of those, also failing with nothing swapped"] = run(failed)[1]
        out[title] = row
        save("cmp-tests", out)
    subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=REPO, capture_output=True)


def lines_of(value, indent: int = 0) -> list:
    pad = "  " * indent
    if isinstance(value, dict):
        out = []
        for key, inner in value.items():
            plain = not isinstance(inner, (dict, list)) or not inner or (
                isinstance(inner, list) and all(not isinstance(item, (dict, list)) for item in inner) and len(str(inner)) < 150)
            if plain:
                out.append(f"{pad}{key}: {inner}")
            else:
                out.append(f"{pad}{key}:")
                out += lines_of(inner, indent + 1)
        return out
    if isinstance(value, list):
        return [line for item in value for line in (lines_of(item, indent) if isinstance(item, (dict, list)) else [f"{pad}{item}"])]
    return [f"{pad}{value}"]


def compare_report() -> int:
    files, env, tests = part("cmp-files"), part("cmp-env"), part("cmp-tests")
    (EVIDENCE / "compare.json").write_text(json.dumps({"base": BASE, "files": files, "environment": env, "tests": tests}, indent=1) + "\n")
    say = ["THE COPIES AS THEY WERE AT " + BASE[:7] + ", ON REAL FILES", ""]
    say += ["corpus (different files; a file in several packs counts once, under the first):"] + lines_of(files.get("corpus") or {}, 1)
    say += ["copies that could not be imported:"] + lines_of(files.get("copies that could not be imported") or {"none": ""}, 1)
    models = files.get("models") or {}
    say += ["", "== .model: dmodel (tools/pd2-port) and diesel_model (tools/pd2-las)"]
    for key in ("FAILED", "containers", "whole", "sections", "tags", "tag tables", "reads"):
        if key in models:
            say += [f" {key}:"] + lines_of(models[key], 2)
    by = {}
    for name, (same_n, other_n) in (models.get("fields") or {}).items():
        kind_, tag, attr = name.split(" | ")
        by.setdefault(f"{kind_} | {tag}", []).append((attr, same_n, other_n, name))
    say.append(" fields, section by section (where both copies read the section):")
    for key, rows in by.items():
        say.append(f"    {key}: the same in all {max(s + o for _a, s, o, _n in rows)} sections: {', '.join(a for a, _s, o, _n in rows if not o) or '-'}")
        for attr, same_n, other_n, name in rows:
            if other_n:
                say.append(f"        DIFFERENT {attr}: in {other_n} of {same_n + other_n} sections; " + " ;; ".join(models["examples"].get(name, [])[:2]))
    for key in ("channels", "roundtrip", "roundtrip_examples", "names", "hash", "inverse"):
        if key in models:
            say += [f" {key}:"] + lines_of(models[key], 2)
    say += ["", "== DDS: dds (tools/pd2-port) and dds_encode (tools/pd2-las)"] + lines_of(files.get("textures") or {}, 1)
    say += ["", "== the files that register a pack (- is the tracked line, + what the writer gives for the same pack)"] + lines_of(files.get("writers") or {}, 1)
    say += ["", "== the environment"] + lines_of(env, 1)
    say += ["", "== the tests written for one copy, run against the other"] + lines_of(tests, 1)
    text = "\n".join(say) + "\n"
    (EVIDENCE / "compare.txt").write_text(text)
    print(f"compare.txt: {len(text.splitlines())} lines, {len(text)} bytes")
    return 0 if files.get("models") and env and tests else 1


def compare() -> int:
    ensure_tools()
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    for name in ("cmp-files", "cmp-env", "cmp-tests"):
        (OUT / "parts" / f"{name}.json").unlink(missing_ok=True)
    log = OUT / "compare.log"
    log.write_text("")
    lock = threading.Lock()
    threads = [threading.Thread(target=lane, args=(steps, log, lock)) for steps in ([["_cmp_files"], ["_cmp_env"]], [["_cmp_tests"]])]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return compare_report()


# ================================================================ after a merge: the record again, against the reference
def part_fresh() -> None:
    done = subprocess.run([str(PY), "tools/pd2-las/fresh.py", "check"], cwd=REPO, capture_output=True, text=True)
    lines = done.stdout.strip().splitlines()
    save("fresh-now", {"rc": done.returncode, "summary": lines[-1] if lines else done.stderr[-300:]})


def part_suite_plain() -> None:
    done = subprocess.run([str(PY), "-m", "pytest", "-q", "tests", "-rf"], cwd=REPO, capture_output=True, text=True)
    (OUT / "suite-now.txt").write_text(done.stdout + done.stderr)
    save("suite-now", {"rc": done.returncode, "summary": (done.stdout.strip().splitlines() or [done.stderr[-300:]])[-1],
                       "failed": re.findall(r"^FAILED (\S+)", done.stdout, flags=re.M)})


def run_after(quick: bool) -> None:
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    for name in ("fresh-now", "suite-now", "golden9", "trace-now"):
        (OUT / "parts" / f"{name}.json").unlink(missing_ok=True)
    log = OUT / "after.log"
    log.write_text("")
    lock = threading.Lock()
    lanes = [[["_trace", "now"], ["_golden", "9"]]] + ([] if quick else [[["_fresh"], ["_suite_plain"]]])
    threads = [threading.Thread(target=lane, args=(steps, log, lock)) for steps in lanes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def first_difference(name: str) -> str:
    before, now = OUT / "run1" / f"{name}.txt", OUT / "run9" / f"{name}.txt"
    if not (before.is_file() and now.is_file()):
        return ""
    for x, y in zip(before.read_text().splitlines(), now.read_text().splitlines()):
        if x != y:
            return f"was `{x.strip()[:90]}`, is `{y.strip()[:90]}`"
    return "one prints more lines than the other"


def rehash() -> int:
    """The rules of `steady_text` as they are now, applied to the saved texts of the reference runs and of the last run."""
    for run in (1, 2, 9):
        base, data = OUT / f"run{run}", part(f"golden{run}")
        for name, row in (data.get("commands") or {}).items():
            path = base / f"{name}.txt"
            if path.is_file():
                text = steady_text(path.read_text(), base / "tree", base / "scratch")
                if name in WHOLE_TREE:
                    text = re.sub(r"\d+", "N", text)
                path.write_text(text)
                row["printed"] = sha(text)
        if data:
            save(f"golden{run}", data)
    return 0


def after(mode) -> int:
    """What the tree gives now, against the reference: packs, suite, every builder's trace, every recorded output."""
    reference = json.loads((EVIDENCE / "reference.json").read_text())
    quick = mode == "quick"
    if mode != "recheck":
        run_after(quick)
    say, bad = [], 0
    if not quick:
        fresh_now, suite_now = part("fresh-now"), part("suite-now")
        say.append(f"fresh: {fresh_now.get('summary')} (exit {fresh_now.get('rc')})")
        say.append(f"suite: {suite_now.get('summary')} (exit {suite_now.get('rc')}); failed: {suite_now.get('failed')}")
        bad += fresh_now.get("rc") != 0 or suite_now.get("rc") != 0
    trace_now = part("trace-now")
    say.append(f"trace: {trace_now.get('same')} of {trace_now.get('of')} zips the tracked bytes")
    bad += trace_now.get("same") != trace_now.get("of") or not trace_now.get("of")
    for builder in sorted(reference["trace"]["functions"]):
        before = {}
        for line in (EVIDENCE / "trace" / f"{builder}.txt").read_text().splitlines():
            parts = line.split()
            before[parts[0]] = parts[1:]
        now, values = s_lines(OUT / "trace-now" / f"{builder}.log"), r_values(OUT / "trace-now" / f"{builder}.log")
        changed, recalled = [], []
        for name in sorted(before):
            if name in now and now[name] != before[name][:3]:
                # a function that is called another number of times has another chained checksum; what
                # counts is whether each call still returns a value it returned before (first 40 calls)
                was = before[name]
                same = (len(was) >= 5 and was[4] != "-" and int(was[0]) <= 40 and int(now[name][0]) <= 40
                        and set_mark(values.get(name, set()))[1] == was[4])
                (recalled if same else changed).append(name)
        gone = sorted(name for name in before if name not in now)
        new = sorted(name for name in now if name not in before)
        moved = {name: [other for other in new if now[other] == before[name][:3]] for name in gone}
        say.append(f"   {builder}: {len(before) - len(changed) - len(recalled) - len(gone)} of {len(before)} functions return what they returned; "
                   f"{len(recalled)} are called another number of times and return the same values; "
                   f"{len(changed)} return something else; {len(gone)} are gone; {len(new)} are new")
        say += [f"      RETURNS SOMETHING ELSE {name}: was {' '.join(before[name][:3])}, is {' '.join(now[name])}" for name in changed[:12]]
        say += [f"      called {now[name][0]} times, was {before[name][0]}, the same values: {name}" for name in recalled[:12]]
        say += [f"      gone {name}" + (f" (the same values now come from {', '.join(moved[name])})" if moved[name] else "") for name in gone[:20]]
        say += [f"      new {name}" for name in new[:20]]
        bad += bool(changed)
    outputs, unlike = part("golden9").get("commands") or {}, []
    for name, want in reference["outputs"].items():
        got = outputs.get(name)
        if got is None:
            unlike.append(f"{name}: was not run")
            continue
        if got["rc"] != want["rc"]:
            unlike.append(f"{name}: exit {got['rc']}, was {want['rc']}")
        if want["printed"] and got["printed"] != want["printed"]:
            unlike.append(f"{name}: prints something else: {first_difference(name)}")
        unlike += [f"{name}: wrote another {path}" for path, digest in want["written"].items() if got["written"].get(path) != digest]
    tools = len(reference["outputs"])
    say.append(f"outputs: {tools - len({line.split(':')[0] for line in unlike})} of {tools} tools give what they gave")
    say += ["      " + line for line in unlike]
    bad += bool(unlike)
    text = "\n".join(say)
    (OUT / "after.txt").write_text(text + "\n")
    print(text)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["record", "assemble", "compare", "report", "rehash", "after", "_build", "_suite", "_lint", "_golden", "_trace",
                                        "_cmp_files", "_cmp_env", "_cmp_tests", "_fresh", "_suite_plain"])
    ap.add_argument("arg", nargs="?")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    whole = {"record": record, "assemble": assemble, "compare": compare, "report": compare_report, "rehash": rehash}
    if args.command in whole:
        return whole[args.command]()
    if args.command == "after":
        return after(args.arg)
    if args.command == "_golden":
        part_golden(int(args.arg))
    elif args.command == "_trace":
        part_trace(args.arg)
    else:
        {"_build": part_build, "_suite": part_suite, "_lint": part_lint, "_cmp_files": part_files, "_cmp_env": part_env,
         "_cmp_tests": part_tests, "_fresh": part_fresh, "_suite_plain": part_suite_plain}[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
