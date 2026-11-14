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
import shlex
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
    assert list(data)[:4] == ["ready", "hint", "env", "packs"] and list(data)[-1] == "next", list(data)
    # short enough to read whole: one line per section and per pack, and the next command last
    lines = proc.stdout.splitlines()
    assert len(lines) == len(data) + 3 + len(data["packs"])
    assert lines[-2].startswith(' "next": "') and lines[-1] == "}"
    assert data["ready"] is (data["hint"] is None)
    assert data["next"] == (data["hint"] or "make -sC tools/pd2-las green")


def test_status_covers_every_tracked_pack_and_agrees_with_the_sidecars():
    """All 14 packs of the three pipelines, not the four of this directory.

    `status` used to report four packs; the state of the other ten took three more commands,
    one of which rebuilt nine packs to find out. `is` compares with the commit, because every
    builder but lawson's writes the `.sha256` itself: a zip that equals its sidecar proves
    nothing about a rebuild.

    It has to pass on a pack that was rebuilt on purpose and is not committed yet (`changed`):
    the suite is what tells an agent that nothing else needs editing.
    """
    status = _load()
    sidecars = sorted(path.name[: -len(".zip.sha256")] for path in (REPO / "dist").glob("*.zip.sha256"))
    if not sidecars:
        pytest.skip("dist/ is absent from this sandbox snapshot")
    short, full = status.collect()["packs"], status.collect(full=True)["packs"]
    assert sorted(short) == sidecars and len(sidecars) >= 14
    for name, pack in full.items():
        assert pack["make"] == status.target(name), name
        if name not in {"Christie_LAS", "Christie_LAS_Slim"}:
            # the two Christie packs are tracked but have no rebuild path: their builder was
            # deleted on 2026-11-14, so `make` is null for them by design
            assert pack["make"], f"{name}: no make target rebuilds it"
        else:
            assert pack["make"] is None, f"{name}: the Christie builder is deleted; make must stay null"
        if pack["is"] == "missing":
            continue    # dist/ can be absent from a sandbox snapshot; test_dist_checksums owns that case
        path = REPO / "dist" / f"{name}.zip"
        assert pack["is"] in {"tracked", "changed", "ok"}, f"{name}: the zip is not its .sha256"
        assert pack["sha256"] == (REPO / "dist" / f"{name}.zip.sha256").read_text().split()[0], name
        assert short[name]["sha256"] == pack["sha256"][:12] and pack["bytes"] == path.stat().st_size, name
    one = status.collect(only=["Christie_LAS_Slim"])
    assert list(one["packs"]) == ["Christie_LAS_Slim"]
    # `note` is there while a pack is `changed`; never the environment, which `only` leaves out
    assert list(one)[0] == "packs" and list(one)[-1] == "next" and set(one) <= {"packs", "note", "next"}, list(one)


def test_status_tells_a_rebuilt_pack_from_the_tracked_one(tmp_path, monkeypatch):
    """`changed` is a zip that equals its sidecar and not the commit; `broken` one that does not equal its sidecar.

    It runs in a checkout of HEAD of its own and reads nothing from this one. It used to skip while this
    checkout's pack was rebuilt and not committed: the skip budget has no room for that reason, so `green`
    failed in the one state where `status` names it as the next command.
    """
    if not (REPO / ".git").exists() or not shutil.which("git"):
        pytest.skip("needs the git checkout")
    status = _load()
    name = "Christie_LAS_Slim"
    clone = tmp_path / "clone"
    subprocess.run(["git", "worktree", "add", "--detach", str(clone), "HEAD"], cwd=REPO, check=True, capture_output=True)
    try:
        monkeypatch.setattr(status, "REPO", clone)
        assert status.collect(only=[name])["packs"][name]["is"] == "tracked"
        with open(clone / "dist" / f"{name}.zip", "ab") as handle:
            handle.write(b"\0")
        assert status.collect(only=[name])["packs"][name]["is"] == "broken"
        digest = __import__("hashlib").sha256((clone / "dist" / f"{name}.zip").read_bytes()).hexdigest()
        (clone / "dist" / f"{name}.zip.sha256").write_text(f"{digest}  dist/{name}.zip\n")
        result = status.collect(only=[name])
        assert result["packs"][name]["is"] == "changed" and list(result) == ["packs", "note", "next"]
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(clone)], cwd=REPO, capture_output=True)


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


def test_a_workflow_that_runs_the_suite_installs_what_the_test_workflow_installs():
    """The suite imports scipy, and the release workflow ran the suite without installing it.

    `lawson LAS pack` failed in its `tests` step on every run from 2026-11-12 on, and would
    have on a release tag: no release could be published. The `test` workflow runs on every
    push, so its install line is known to carry the suite. Any other workflow that runs
    pytest has to install at least those packages.
    """
    yaml = pytest.importorskip("yaml")

    def lines(path: Path) -> list[str]:
        jobs = yaml.safe_load(path.read_text())["jobs"].values()
        return [line.strip() for job in jobs for step in job["steps"] for line in str(step.get("run", "")).splitlines()]

    def installed(line: str) -> set[str]:
        words, names = shlex.split(line.split("pip install", 1)[1].split("&&")[0]), set()
        for before, word in zip([""] + words, words):
            if not word.startswith("-") and before not in ("-c", "-r"):
                names.add(re.split(r"[<>=!~\[]", word, maxsplit=1)[0].lower())
        return names

    workflows = REPO / ".github" / "workflows"
    reference = [installed(line) for line in lines(workflows / "test.yml") if "pip install" in line and "pytest" in line]
    assert len(reference) == 1 and {"pytest", "scipy"} <= reference[0], reference
    runs_the_suite = [path for path in sorted(workflows.glob("*.yml")) if any("-m pytest" in line for line in lines(path))]
    assert [path.name for path in runs_the_suite] == ["lawson-las.yml", "test.yml"], runs_the_suite
    for path in runs_the_suite:
        has = set().union(*(installed(line) for line in lines(path) if "pip install" in line))
        assert reference[0] <= has, f"{path.name} runs the suite without installing {sorted(reference[0] - has)}"


def test_status_only_names_inputs_and_targets_that_exist():
    status = _load()
    for rel in status.INPUTS:
        assert (REPO / rel).is_file(), rel
    targets = set(re.findall(r"^([a-z]+):", (HERE / "Makefile").read_text(), flags=re.M))
    assert set(status.TARGETS.values()) | {status.HEADS} <= targets


@pytest.mark.parametrize("builder", ["build_models", "build_busty_variant"])
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

    assert "make -C tools/pd2-las" not in readme, (
        "the README's commands need -s: a bare `make -C` wraps the output in directory lines")
    used = set(re.findall(r"make -sC tools/pd2-las (\w+)", readme))
    used |= set(re.findall(r"^\| `(?:Miranda|Christie)\w*`.*\| `(\w+)` \|$", readme, flags=re.M))
    assert {"env", "status", "build", "busty", "fresh", "test", "green"} <= used, used
    assert used <= targets, f"README names make targets that do not exist: {sorted(used - targets)}"

    scripts = re.findall(r"\$\(HERE\)/([\w.]+)", makefile)
    assert scripts
    for script in scripts:
        assert (HERE / script).is_file(), script
    for script in re.findall(r"(?<![\w/)])(tools/[\w./-]+\.py)", makefile):
        assert (REPO / script).is_file(), script

    # one build target per builder, and they are the builders `fresh` runs: twelve of the 14 packs, the two Christie packs excepted
    sys.path.insert(0, str(HERE))
    fresh = pytest.importorskip("fresh", reason="fresh.py imports numpy")
    built = {name: command.replace("$(HERE)", "tools/pd2-las")
             for name, command in re.findall(r"^([a-z]+):.*\n\t\$\(call BUILD,(.+)\)$", makefile, flags=re.M)}
    assert sorted(built.values()) == sorted(" ".join(argv) for argv in fresh.BUILDERS.values()), built
    status = _load()
    assert set(built) == set(status.TARGETS.values()) | {status.HEADS}

    make = shutil.which("make")
    if make:
        proc = subprocess.run([make, "-C", str(HERE), "-n", *sorted(targets)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        # the form the README gives has to be pipeable: one JSON object, no make chatter
        proc = subprocess.run([make, "-sC", "tools/pd2-las", "status"],
                              capture_output=True, text=True, cwd=REPO)
        assert proc.returncode == 0, proc.stderr
        assert list(json.loads(proc.stdout)["packs"]) == status.pack_names()


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
    """Commands, invariants and open work are written once: in the README here.

    They used to be written three times. `AGENTS.md` had a quickstart of its own;
    `HANDOFF.md` had a quickstart, a recovery guide, a file map, an invariants list and a
    work queue. The copies drifted from the README and from the tree. This test fails when
    one of them grows back. (What `AGENTS.md` may hold, and that it has no copy of its own,
    is tests/test_agent_docs.py.)
    """
    entry = "tools/pd2-las/README.md"
    handoff = (REPO / "docs" / "pd2-las" / "HANDOFF.md").read_text()
    agents = (REPO / "AGENTS.md").read_text()
    readme = README.read_text()

    assert entry in handoff.split("\n## ", 1)[0], "HANDOFF.md does not open by pointing at the README"
    assert f"`{entry}`" in agents, "AGENTS.md does not route to the README"

    assert "```" not in handoff, "HANDOFF.md has a command block; commands belong in the README"
    headers = re.findall(r"^#{2,4} (.+)$", handoff, flags=re.M)
    assert headers, "HANDOFF.md has no sections"
    for header in headers:
        for word in ("quickstart", "recover", "invariant", "next", "where things live", "worktree",
                     "environment", "command", "status"):
            assert word not in header.lower(), (
                f"HANDOFF.md has a section about {word!r}: that is the README's job")

    assert "```" not in agents, "AGENTS.md has a command block; it names one make target per question"
    for script in ("bootstrap.sh", "recover_env.sh", "extract_2b.py"):
        assert script not in agents, f"AGENTS.md names {script}; the README's commands are make targets"
    assert "Invariant" not in agents, "AGENTS.md has invariants of its own again: tools/README.md and this README hold them"

    targets = set(re.findall(r"^([a-z]+):", (HERE / "Makefile").read_text(), flags=re.M))
    for name, text in (("AGENTS.md", agents), ("HANDOFF.md", handoff)):
        used = set(re.findall(r"make -sC tools/pd2-las (\w+)", text))
        assert used <= targets, f"{name} names make targets that do not exist: {sorted(used - targets)}"

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
