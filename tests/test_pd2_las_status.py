"""`tools/pd2-las/status.py` is the one-call orientation for the pd2-las tree.

The README points at it instead of describing the state in prose, so it has to
stay true: valid JSON, the same checksums as the sidecars, the pins of
pins.txt. The same goes for the rest of the README's command
surface: the Makefile targets, the builders' `--templates` default, and the
tests and paths the README names.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "pd2-las" / "status.py"
HERE = SCRIPT.parent
README = HERE / "README.md"
#: composed, not spelled: two tests below scan this file for that directory as well
TMP = "/" + "tmp"


def _code_files() -> list[Path]:
    """Scripts, tests, workflows and their data under tools/, tests/, um/ and .github/.

    Only what git tracks or would track: a gitignored build tree or a third-party clone
    under tools/ is not this repository's code. Without git (a source archive), every
    file that is not in a build or cache directory.
    """
    roots = ("tools", "tests", "um", ".github")
    git = shutil.which("git")
    if git and (REPO / ".git").exists():
        listed = subprocess.run(
            [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *roots],
            cwd=REPO, capture_output=True, check=True).stdout.decode().split("\0")
        files = [REPO / rel for rel in listed if rel]
    else:
        skip = {"build", "node_modules", "__pycache__", ".venv"}
        files = [p for root in roots for p in (REPO / root).rglob("*")
                 if not skip & set(p.relative_to(REPO).parts)]
    code = [p for p in files
            if p.is_file() and (p.suffix in {".py", ".sh", ".yml", ".json"} or p.name == "Makefile")]
    assert len(code) > 100, "the scan found almost nothing: it is looking in the wrong place"
    return code


def _load():
    spec = importlib.util.spec_from_file_location("pd2_las_status", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_status_cli_prints_one_json_object():
    proc = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert list(data) == ["ready", "hint", "inputs", "env", "templates", "packs"]
    # short enough to read whole: one line per section and per pack
    assert len(proc.stdout.splitlines()) == 9 + len(data["packs"])
    assert data["ready"] is (data["hint"] is None)


def test_status_agrees_with_the_checksum_sidecars():
    status = _load()
    packs = status.collect()["packs"]
    assert set(packs) == set(status.PACKS)
    for name, pack in packs.items():
        assert pack["build"] == status.PACKS[name]
        if not pack["present"]:
            continue    # dist/ can be absent from a sandbox snapshot; test_dist_checksums owns that case
        sidecar = (REPO / (pack["zip"] + ".sha256")).read_text().split()[0]
        assert pack["sha256"] == sidecar and pack["sha256_ok"] is True, name
        assert pack["models_present"] is True, f"{name}: BUILD_INFO.json says the models are missing"
        assert isinstance(pack["runtime_verified"], bool), name


def test_the_pins_are_written_once():
    """One place for the pinned versions: tools/pd2-las/pins.txt.

    The tracked zips only rebuild byte for byte with these pillow/numpy versions. They
    used to be written in four places (two environment scripts, two workflows) that this
    test kept equal. Now every install that names a pinned package takes pins.txt as its
    constraints file, and none writes a version of its own.
    """
    status = _load()
    pins = status.pins()
    assert set(pins) == set(status.PINNED), pins
    named = re.compile(r"\b(%s)\b" % "|".join(pins))
    for rel in ("tools/pd2-las/recover_env.sh", ".github/workflows/test.yml",
                ".github/workflows/lawson-las.yml"):
        text = (REPO / rel).read_text()
        installs = [line.strip() for line in text.splitlines()
                    if "pip install" in line and not line.lstrip().startswith("#") and named.search(line)]
        assert installs, f"{rel} installs none of {sorted(pins)}"
        for line in installs:
            assert "-c tools/pd2-las/pins.txt" in line, f"{rel} installs a pinned package without pins.txt: {line}"
        for name in pins:
            assert f"{name}==" not in text, f"{rel} writes a version of {name} of its own"


def test_status_only_names_inputs_and_builders_that_exist():
    status = _load()
    for rel in status.INPUTS:
        assert (REPO / rel).is_file(), rel
    for command in status.PACKS.values():
        assert (SCRIPT.parent / command.split()[0]).is_file(), command


@pytest.mark.parametrize("builder", ["build_models", "build_busty_variant", "build_christie_las"])
def test_builders_default_to_the_templates_status_reports(builder, tmp_path, monkeypatch):
    """`--templates` is optional: a builder looks where extract_2b.py unpacks the 2B pack.

    The path used to be a required argument that every README spelled out, pointing into a
    /tmp that a fresh session does not have. Now it is one constant, status.py reports
    whether it is populated, and a builder that finds it empty names the command that
    fills it instead of dying on a missing file halfway through.
    """
    pytest.importorskip("numpy")
    monkeypatch.syspath_prepend(str(HERE))
    import build_models as bm
    import extract_2b

    assert bm.DEFAULT_TEMPLATES == _load().TEMPLATES == extract_2b.TEMPLATES

    module = importlib.import_module(builder)
    monkeypatch.setattr(bm, "DEFAULT_TEMPLATES", tmp_path / "no-templates-here")
    # explicit outputs: if the check ever goes missing, nothing tracked is in the way
    argv = ["--out", str(tmp_path / "out")]
    if builder == "build_christie_las":
        argv += ["--dist", str(tmp_path / "dist")]
    with pytest.raises(SystemExit) as stop:
        module.main(argv)
    message = str(stop.value)
    assert "no-templates-here" in message and "recover_env.sh" in message, message
    assert not (tmp_path / "out").exists(), "the builder started work before checking its inputs"


def test_makefile_targets_match_the_readme_and_the_scripts():
    """The README's commands are make targets, and each target runs a script that exists."""
    makefile = (HERE / "Makefile").read_text()
    readme = README.read_text()
    targets = set(re.findall(r"^([a-z]+):", makefile, flags=re.M))

    assert "make -C tools/pd2-las" not in readme.replace("`make -C` wraps", ""), (
        "the README's commands need -s: a bare `make -C` wraps the output in directory lines")
    used = set(re.findall(r"make -sC tools/pd2-las (\w+)", readme))
    used |= set(re.findall(r"^\| `(?:Miranda|Christie)\w*`.*\| `(\w+)` \|$", readme, flags=re.M))
    assert {"env", "status", "build", "busty", "christie", "slim", "test"} <= used, used
    assert used <= targets, f"README names make targets that do not exist: {sorted(used - targets)}"

    scripts = re.findall(r"\$\(HERE\)/([\w.]+)", makefile)
    assert scripts
    for script in scripts:
        assert (HERE / script).is_file(), script
    for command in _load().PACKS.values():
        assert f"$(PY) $(HERE)/{command}\n" in makefile, f"no make target runs `{command}`"

    make = shutil.which("make")
    if make:
        proc = subprocess.run([make, "-C", str(HERE), "-n", *sorted(targets)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        # the form the README gives has to be pipeable: one JSON object, no make chatter
        proc = subprocess.run([make, "-sC", "tools/pd2-las", "status"],
                              capture_output=True, text=True, cwd=REPO)
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["packs"].keys() == _load().PACKS.keys()


def test_readme_keeps_its_contract():
    """The pd2-las README is an entry point, not a journal.

    It grew to 320 lines of dated survey tables and measurements that contradicted each
    other (a status block saying the models were authored above a roadmap saying they
    were not). What keeps it from growing back: stable headers an agent can grep, a
    length budget, no dates or hashes (those live in HANDOFF.md, MODLOG.md and the packs'
    BUILD_INFO.json), and no reference to a test or a file that does not exist.
    """
    text = README.read_text()
    headers = re.findall(r"^## (.+)$", text, flags=re.M)
    assert headers == ["Status", "Commands", "File map", "Invariants", "Do not", "Next",
                       "Further reading"], headers
    assert len(text.splitlines()) <= 130, "over budget: move detail to docs/ or knowledge/"

    prose = re.sub(r"`[^`\n]*`", "", text)     # file names may carry a date; prose may not
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", prose), "dated statements belong in HANDOFF.md"
    assert not re.search(r"\b[0-9a-f]{40,}\b", text), "checksums belong in the .sha256 sidecars"

    sources = "\n".join(p.read_text() for p in sorted((REPO / "tests").glob("test_*.py")))
    for name in sorted(set(re.findall(r"\b(test_\w+)\b(?!\.py)", text))):
        assert f"def {name}(" in sources, f"README cites a test that does not exist: {name}"
    for name in sorted(set(re.findall(r"\b(test_\w+\.py)\b", text))):
        assert (REPO / "tests" / name).is_file(), name
    for path in sorted(set(re.findall(
            r"`((?:docs|knowledge|tools|models|references)/[^`*<> ]+)`", text))):
        assert (REPO / path).exists(), f"README cites a path that does not exist: {path}"
    for row in re.findall(r"^\| (`[^|]+) \| [^|]+ \|$", text, flags=re.M):
        for name in re.findall(r"`([\w.*-]+\.(?:py|json|sh|md)|Makefile)`", row):
            assert list(HERE.glob(name)), f"file map names {name}, which is not in tools/pd2-las"


def test_readme_invariants_are_the_invariant_tests():
    """Each row of the README's Invariants table is one test, named after the row.

    The table used to cite authoring tests by name: `test_geometry_sane_and_winding_positive`
    stood for both "units" and "winding", and none of them ran without the 2B templates, so
    on a fresh clone and in CI the invariants were a list of names. Now each row has a test
    of its own in `tests/test_pd2_las_invariants.py` that reads the tracked packs. This
    keeps the two lists the same list: same tests, same order, the test's name starting
    with the row's name and its docstring opening with it.
    """
    section = README.read_text().split("\n## Invariants\n", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| \*\*([^*:]+):?\*\* .*\| `(test_\w+)` \|$", section, flags=re.M)
    assert len(rows) == section.count("\n| **"), "a row of the table does not end in one test name"
    assert len(rows) >= 10, rows

    source = (REPO / "tests" / "test_pd2_las_invariants.py").read_text()
    defined = re.findall(r"^def (test_\w+)\(", source, flags=re.M)
    assert [test for _, test in rows] == defined, (
        "the README's Invariants table and tests/test_pd2_las_invariants.py differ:\n"
        f"  table: {[test for _, test in rows]}\n  tests: {defined}")
    for name, test in rows:
        slug = re.sub(r"\W+", "_", name.strip().lower())
        assert test.startswith(f"test_{slug}_"), f"{test} is not named after its row, {name!r}"
        assert re.search(rf'^def {test}\([^)]*\):\n    """\*\*{re.escape(name.strip())}\.\*\* ', source,
                         flags=re.M), f"the docstring of {test} does not open with **{name.strip()}.**"


def test_pd2_las_has_one_entry_point():
    """Commands, invariants and open work for this tree are written once, in its README.

    They used to be written three times. `AGENTS.md` had a quickstart of its own;
    `HANDOFF.md` had a quickstart, a recovery guide, a file map, an invariants list and a
    work queue. The three gave three different first commands, one of them a hard reset
    onto a branch that no longer existed, and the copies drifted: the handoff still
    listed a defect the tracked packs do not have and a scale factor that no code applies.

    Now the README is the entry point, the agent files route to it and keep only what
    holds for every pipeline, and the handoff is the dated record. This test keeps the
    second copies from growing back.
    """
    entry = "tools/pd2-las/README.md"
    handoff = (REPO / "docs" / "pd2-las" / "HANDOFF.md").read_text()
    agents = (REPO / "AGENTS.md").read_text()
    for copy in ("CLAUDE.md", "GEMINI.md"):
        assert (REPO / copy).read_text() == agents, f"{copy} is not a copy of AGENTS.md"

    # both send the reader to the README: the handoff before it says anything else
    assert entry in handoff.split("\n## ", 1)[0], "HANDOFF.md does not open by pointing at the README"
    section = agents.split("\n## Active Project: PAYDAY 2", 1)[1]
    assert f"| `{entry}` | `make -sC tools/pd2-las status` |" in section, (
        "AGENTS.md does not route pd2-las to its README and the status command")

    # the handoff is a record: no commands, no rules, no queue
    assert "```" not in handoff, "HANDOFF.md has a command block; commands belong in the README"
    headers = [h.lower() for h in re.findall(r"^#{2,4} (.+)$", handoff, flags=re.M)]
    assert headers, "HANDOFF.md has no sections"
    for word in ("quickstart", "recover", "invariant", "next", "where things live", "worktree",
                 "environment", "command", "status"):
        assert not any(word in h for h in headers), (
            f"HANDOFF.md has a section about {word!r}: that is the README's job")

    # the agent files route; they do not carry a second set of commands for the pipelines
    assert "```" not in section, "AGENTS.md has a command block for the PAYDAY 2 pipelines"
    for script in ("bootstrap.sh", "recover_env.sh", "extract_2b.py"):
        assert script not in section, f"AGENTS.md names {script}; the README's commands are make targets"

    # and whatever targets they do name exist
    targets = set(re.findall(r"^([a-z]+):", (HERE / "Makefile").read_text(), flags=re.M))
    for name, text in (("AGENTS.md", agents), ("HANDOFF.md", handoff)):
        used = set(re.findall(r"make -sC tools/pd2-las (\w+)", text))
        assert used <= targets, f"{name} names make targets that do not exist: {sorted(used - targets)}"

    # the README says so itself, where the next editor will read it
    readme = README.read_text()
    assert "Do not write commands, invariants or open work anywhere else" in readme
    assert "HANDOFF.md" not in readme.split("\n## Next\n", 1)[1].split("\n## ", 1)[0], (
        "the README's Next sends the reader to HANDOFF.md for the work queue again")


def test_the_2b_templates_have_one_home_inside_the_repo():
    """`extract_2b.py` is the one place that says where the 2B templates live.

    They used to be unpacked to a fixed directory under /tmp, and that path was written
    out in thirty files: every builder command, seven test modules, the skip budget.
    /tmp does not outlive a session and does not exist on Windows, so the templates now
    go to build/pd2-las/2b/, which is inside the checkout and gitignored (the pack is
    somebody else's mod: it must never be committed unpacked). Nothing else may spell
    either the old path or the new one; code imports `extract_2b.TEMPLATES`.
    """
    sys.path.insert(0, str(HERE))
    import extract_2b

    assert extract_2b.OUT == REPO / "build" / "pd2-las" / "2b"
    assert (extract_2b.OUT / extract_2b.UNIT).relative_to(extract_2b.OUT)
    assert _load().TEMPLATES == extract_2b.TEMPLATES

    git = shutil.which("git")
    if git and (REPO / ".git").exists():
        unpacked = (extract_2b.OUT / extract_2b.UNIT / "2b.model").relative_to(REPO)
        ignored = subprocess.run([git, "check-ignore", "-q", str(unpacked)], cwd=REPO)
        assert ignored.returncode == 0, "build/pd2-las/2b/ must stay gitignored"

    for script in ("recover_env.sh",):
        assert "tools/pd2-las/extract_2b.py" in (HERE / script).read_text(), script

    old = ("2b" + "src", "tmp" + "src", TMP + "/" + "rarx")        # not spelled out: this file is scanned too
    new = "pd2-las" + "/2b/2B - LAS"
    code = _code_files()
    entry_docs = [REPO / rel for rel in (
        "AGENTS.md", "README.md", "tools/README.md", "tools/pd2-las/README.md",
        "tools/pd2-port/README.md", "references/README.md", "models/README.md")]
    for path in code + entry_docs:
        text = path.read_text(encoding="utf-8", errors="replace")
        for word in old:
            assert word not in text, f"{path.relative_to(REPO)} still names the old location ({word})"
    owner = HERE / "extract_2b.py"
    for path in code:
        if path == owner or path.suffix != ".py":
            continue
        # a usage example in a docstring passes the path to a flag; that is not code
        code_lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                      if new in line and not re.search(r'--[a-z-]+ "build/', line)]
        assert not code_lines, (
            f"{path.relative_to(REPO)} spells the templates path; import extract_2b.TEMPLATES")


def test_no_tool_or_test_depends_on_a_fixed_tmp_path():
    """No script, test or workflow reads or writes a fixed path under the system temp directory.

    The 2B templates were not the only thing that lived there. The head-replacement
    builder kept its three extracted archives in it, one test wrote models to it only to
    read them back, a diagnostic created a folder there that nothing used, and two preview
    tools wrote their renders to it by default. That directory is wiped between sessions
    and is not a path on Windows, so a second run found nothing or wrote somewhere odd.

    Scratch belongs to pytest's `tmp_path` or to `tempfile`; whatever a later run should
    find again belongs under build/, which is inside the checkout and gitignored. Prose
    may still say that the directory gets wiped; what may not come back is a path into it:
    the directory followed by a file name, or the directory as a quoted string.
    """
    path_into_it = re.compile(
        r"(?<![\w.~$}/-])(?:/var)?" + re.escape(TMP) + r"(?:/[\w.$({-]|[\"'])")
    entry_docs = [REPO / rel for rel in (
        "AGENTS.md", "README.md", "tools/README.md", "tools/pd2-las/README.md",
        "tools/pd2-port/README.md", "references/README.md", "models/README.md",
        "docs/pd2-las/HANDOFF.md")]
    offenders = []
    for path in _code_files() + entry_docs:
        for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if path_into_it.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{number}: {line.strip()[:90]}")
    assert not offenders, "a fixed temp path is back:\n" + "\n".join(offenders)

    # the scan itself: it has to see the forms it exists for, and leave prose and
    # paths inside the checkout alone
    for line in (f'Path("{TMP}/cache")', f"--out {TMP}/x", f'tmp = "{TMP}"', f"cd /var{TMP}/x"):
        assert path_into_it.search(line), line
    for line in (f"the sandbox wipes {TMP} between sessions", f"it wipes `{TMP}` and `{TMP}/` as well",
                 f"build{TMP}/x", "tmp_path / 'x'"):
        assert not path_into_it.search(line), line

    # ...and the homes that replaced them stay out of git: two of the three archives
    # the head builder unpacks are other people's mods
    git = shutil.which("git")
    if git and (REPO / ".git").exists():
        for rel in ("build/head-mods/ada_joy/x.model", "build/pd2-port/preview/x.png",
                    "build/pd2-port/shade/x.png"):
            ignored = subprocess.run([git, "check-ignore", "-q", rel], cwd=REPO)
            assert ignored.returncode == 0, f"{rel} must stay gitignored"
    for rel, constant in (("tools/build_joy_head_mods.py", 'EXTRACT_DIR = ROOT / "build" / "head-mods"'),
                          ("tools/pd2-port/preview_check.py",
                           'DEFAULT_RENDER_DIR = REPO / "build" / "pd2-port" / "preview"'),
                          ("tools/pd2-port/shade_check.py", '/ "build" / "pd2-port" / "shade"')):
        assert constant in (REPO / rel).read_text(), f"{rel} no longer keeps its files under build/"


def test_env_scripts_do_not_trust_a_venv_without_pip():
    """A `.venv` is the build's environment only if `python -m pip` works in it.

    `uv run` leaves a `.venv` without pip, on an interpreter of uv's choosing, and
    `bin/um` goes through uv wherever uv is installed: the CI job, for one. Both
    scripts used to take any `.venv/bin/python` for theirs and then call
    `.venv/bin/pip`, which is not there. The first run of the fresh-build step on a
    GitHub runner died of it within a second, with nothing built (2026-11-12).
    """
    for rel in ("tools/pd2-las/recover_env.sh",):
        lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
        code = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
        assert "bin/pip" not in code, f"{rel} calls a pip script; use `python -m pip`"
        assert "-m pip --version" in code, f"{rel} does not ask the venv whether it has pip"
        assert "python3 -m venv --clear .venv" in code, f"{rel} does not start a venv without pip again"
