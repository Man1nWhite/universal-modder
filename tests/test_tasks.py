"""`tools/tasks.py` is the Makefile for machines without make: the two must not drift.

The Makefile hardcodes `.venv/bin/python`, shells out to `bash recover_env.sh` and gets its log
redirection from GNU make, none of which exist on native Windows — where this fork's subjects
(PAYWAY 2 on Windows) actually run. `tools/tasks.py` repeats its targets in Python for that case,
so a target added to one and not the other is a trap; this test reads both files.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "tools" / "pd2-las" / "Makefile"
SOURCE = ROOT / "tools" / "tasks.py"

# `name:  ## help` on one line, the Makefile's convention for a documented target
_DOCUMENTED = re.compile(r"^([a-z][a-z0-9_]*):[^#\n]*##\s", re.M)
_ALL = re.compile(r"^all:\s*([^#\n]+)", re.M)
_BUILD_CALL = re.compile(r"^\t\$\(call BUILD,(.+)\)$", re.M)

pytest.importorskip("pytest")


def tasks_module():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("tools_tasks", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tools_tasks"] = module
    spec.loader.exec_module(module)
    return module


def makefile_targets() -> set[str]:
    return set(_DOCUMENTED.findall(MAKEFILE.read_text(encoding="utf-8")))


#: make's own targets: `help` prints the list, `all` is the builder list below
MAKE_ONLY = {"help", "all"}


def test_every_makefile_target_exists_here():
    tasks = tasks_module()
    missing = sorted(makefile_targets() - set(tasks.TASKS) - MAKE_ONLY)
    assert not missing, f"tools/tasks.py has no entry for: {missing}"


def test_no_target_here_is_unknown_to_the_makefile():
    tasks = tasks_module()
    extra = sorted(set(tasks.TASKS) - makefile_targets())
    # docs/links are this script's own additions: document them, do not hide them
    assert set(extra) <= {"docs", "links"}, f"not Makefile targets: {extra}"
    # the make-only names are answered by this script's default help / `all`, not by TASKS
    tasks.main(["help"])


def test_the_build_targets_are_the_ones_make_logs():
    tasks = tasks_module()
    logged = set()
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        m = _BUILD_CALL.match(line)
        if m:
            logged.add(m.group(1).split(",")[0].strip())
    # a builder's stdout goes to build/pd2-las/<target>.log in both; map script -> target name
    scripts = {tasks.TASKS[t][0][-1].replace("{py}", "").strip(): t for t in tasks.BUILDERS}
    assert set(tasks.BUILDERS) == {
        "build", "honokodae",
        "heads", "voices_stream", "voices_geralt", "voices_arivus", "glb"}
    assert len(scripts) == len(tasks.BUILDERS)


def test_all_matches_the_makefile_all_line():
    tasks = tasks_module()
    line = _ALL.search(MAKEFILE.read_text(encoding="utf-8"))
    assert line, "the Makefile lost its `all:` line"
    assert line.group(1).split() == tasks.ALL


def test_every_script_a_target_runs_exists():
    tasks = tasks_module()
    for name, (argv, _) in tasks.TASKS.items():
        script = next((a for a in argv if a.endswith(".py") or a.endswith(".sh")), None)
        if script is None:
            continue  # `test` runs -m pytest
        assert (ROOT / script).is_file(), f"{name}: {script} does not exist"


def test_the_pinned_interpreter_is_used_when_the_venv_exists(monkeypatch, tmp_path):
    tasks = tasks_module()
    exe = tmp_path / (".venv/Scripts/python.exe" if __import__("os").name == "nt" else ".venv/bin/python")
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr(tasks, "ROOT", tmp_path)
    assert tasks.python() == str(exe)


def test_an_unknown_target_is_a_usage_error(capsys):
    tasks = tasks_module()
    assert tasks.main(["nope"]) == 2
    assert "unknown target" in capsys.readouterr().err
