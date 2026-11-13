"""The documents an agent starts from: one home per fact, nothing quoted that a command prints.

Measured on 2026-11-13 (docs/audits/2026-11-13-agent-entry.md): the instruction file was
written three times (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, 13,009 bytes each), 14 pack sizes
stood in four documents, and two tests required exactly that. The shortest route those
documents led to took 26 calls for eight ordinary questions; the audit has what they cost.
Each test here fails when one of those comes back.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PD2 = REPO / "tools" / "pd2-las"
#: what an agent is sent to; the cut rule and these tests apply to them
AGENT_DOCS = ["AGENTS.md", "GEMINI.md", "README.md", "docs/pd2-las/HANDOFF.md", "tools/README.md",
              "tools/pd2-las/README.md", "tools/pd2-port/README.md", "tools/pd2-port/STATUS.md",
              "tools/skyrim-nif/README.md"]
#: these also name packs and tools
OTHER_DOCS = ["CONTRIBUTING.md", "models/README.md", "references/README.md"]
#: bytes of AGENTS.md, which every harness loads whole at the start of every session
START_BUDGET = 5000
STATUS_BUDGET = 2048


def _status():
    spec = importlib.util.spec_from_file_location("pd2_las_status", PD2 / "status.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tracked() -> set[str]:
    """Tracked paths and the directories that hold them (every file, where there is no git)."""
    git = shutil.which("git")
    if git and (REPO / ".git").exists():
        files = subprocess.run([git, "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout.decode().split("\0")
    else:
        files = [p.relative_to(REPO).as_posix() for p in REPO.rglob("*") if p.is_file() and ".venv" not in p.parts]
    known = {rel for rel in files if rel}
    for rel in list(known):
        parts = rel.split("/")
        known |= {"/".join(parts[:n]) for n in range(1, len(parts))}
    return known


def _targets() -> set[str]:
    return set(re.findall(r"^([a-z]+):", (PD2 / "Makefile").read_text(), flags=re.M))


def test_the_instruction_file_is_written_once():
    """`AGENTS.md` and nothing beside it, except the one line Gemini CLI needs.

    Claude Code (2.1.277 and later), Codex, Cursor, Copilot and OpenCode read `AGENTS.md` in a
    clone. Gemini CLI reads `GEMINI.md` and expands `@AGENTS.md` in it. A `CLAUDE.md` is not
    needed, and it costs: Claude Code then reads it instead of `AGENTS.md`, and Cursor's CLI,
    VS Code and Copilot CLI read it as well as `AGENTS.md`. Sources and what each harness
    printed: docs/audits/2026-11-13-agent-entry/harness-loaders.md.
    """
    for name in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md", "AGENTS.override.md",
                 ".github/copilot-instructions.md", ".cursorrules"):
        assert not (REPO / name).exists(), f"{name} is a second instruction file: AGENTS.md is the one"
    assert (REPO / "GEMINI.md").read_text() == "@AGENTS.md\n", "GEMINI.md is the import of AGENTS.md and nothing else"

    lines = {line.strip() for line in (REPO / "AGENTS.md").read_text().splitlines() if len(line.strip()) > 40}
    for rel in sorted(_tracked()):
        if rel.endswith(".md") and rel != "AGENTS.md" and (REPO / rel).is_file():
            text = (REPO / rel).read_text(errors="replace")
            copied = sum(line in text for line in lines)
            assert copied * 2 < len(lines), f"{rel} repeats {copied} of the {len(lines)} lines of AGENTS.md"


def test_what_loads_at_start_stays_small():
    """A budget, because the file is paid for at the start of every session, by every harness.

    It was 13,009 bytes (3,863 tokens, tiktoken o200k_base), and twice that where a harness also
    read `CLAUDE.md`. Codex stops reading at 32 KiB (`project_doc_max_bytes`), which is not the
    binding limit here. To add a line, move one to the document it is about.
    """
    size = len((REPO / "AGENTS.md").read_bytes())
    assert size <= START_BUDGET, f"AGENTS.md is {size} bytes; the budget is {START_BUDGET}"
    done = subprocess.run([sys.executable, str(PD2 / "status.py")], capture_output=True, text=True, cwd=REPO)
    assert done.returncode == 0, done.stderr
    assert len(done.stdout.encode()) <= STATUS_BUDGET, "status no longer fits in one short read"


def test_no_document_quotes_what_status_prints():
    """A size, a sha256 or a test count in a document is a second copy, and the copy goes stale.

    `HANDOFF.md` and the three instruction files used to quote every pack's size, and a test
    required it, so each rebuild meant editing four documents. `make -sC tools/pd2-las status`
    prints sizes and hashes from the zips; `green` and `check_all.py` print the counts. A record
    of what a person saw in game, or of what a release serves, names bytes that are not the
    tracked ones, which passes here.

    `tools/pd2-port/STATUS.md` was left out until 2026-11-13: it quoted the size and sha256 of
    `lawson_las` beside the release, a test kept them current, and the page read as if the
    release served them. It did not.
    """
    status = _status()
    packs = status.collect(full=True)["packs"]
    if not packs or any(pack["is"] == "missing" for pack in packs.values()):
        pytest.skip("dist/ is absent from this sandbox snapshot")
    for rel in AGENT_DOCS + OTHER_DOCS:
        text = (REPO / rel).read_text()
        for name, pack in packs.items():
            for fact in (f"{pack['bytes']:,}", str(pack["bytes"]), pack["sha256"][:12]):
                assert fact not in text, f"{rel} quotes {fact} of {name}: `status` prints it"
        count = re.search(r"\b\d{2,} (?:tests|passed|skipped)\b|\b\d+ pass, \d+ warn, \d+ fail\b"
                          r"|\b\d+/\d+ (?:mutations|checks)\b", text)
        assert not count, f"{rel} quotes a count ({count.group(0)!r}): name the command that prints it instead"


def test_every_path_target_and_test_named_in_an_agent_doc_exists():
    """A document that names a file, a make target or a test that is not there sends an agent nowhere."""
    known, targets = _tracked(), _targets()
    roots = {rel.split("/")[0] for rel in known if "/" in rel}
    test_text = "\n".join(path.read_text() for path in (REPO / "tests").glob("*.py"))
    missing = []

    def exists(path: str) -> bool:
        if any(mark in path for mark in "*?"):
            return any(True for _ in REPO.glob(path))
        return path.rstrip("/") in known

    for doc in AGENT_DOCS:
        text = (REPO / doc).read_text()
        here = Path(doc).parent
        for span in re.findall(r"`([^`\n]+)`", text):
            if span.rstrip("/") in known:
                continue                                    # a path with spaces in it, whole
            for token in span.split():
                token = re.split(r"#|::", token.strip("()\"',;:"))[0].rstrip(".")
                if not token or re.search(r"[<>{}…$|=\\]", token):
                    continue                                # a pattern, an option or a Windows path
                first = token.split("/")[0]
                if "/" in token and first in roots - {"build"} and not exists(token):
                    missing.append(f"{doc}: `{token}`")
                elif token.startswith("build/") and token.endswith((".zip", ".sha256")) and token not in known:
                    missing.append(f"{doc}: `{token}`")
                elif ("/" not in token and re.fullmatch(r"[\w*-]+\.(py|sh)", token) and not token.startswith("test_")
                      and str(here).startswith("tools/")):
                    beside = any(True for _ in (REPO / here).glob(token))
                    if not beside and not any(True for _ in (REPO / "tools").rglob(token)):
                        missing.append(f"{doc}: `{token}` (no such script under tools/)")
        for link in re.findall(r"\]\(([^)\s]+)\)", text):
            if not link.startswith(("http", "#", "mailto:")):
                target = Path(os.path.normpath(here / link.split("#")[0])).as_posix()
                if target.rstrip("/") not in known and target != ".":
                    missing.append(f"{doc}: link to {link}")
        for target in re.findall(r"make -sC tools/pd2-las (\w+)", text):
            if target not in targets:
                missing.append(f"{doc}: make target `{target}`")
        for name, suffix in re.findall(r"\b(test_[a-z0-9_]+)(\.py)?", text):
            if suffix and not any((REPO / "tests").glob(name + ".py")):
                missing.append(f"{doc}: tests/{name}.py")
            elif not suffix and f"def {name}(" not in test_text:
                missing.append(f"{doc}: test `{name}`")
    assert not missing, "named in an agent document, not in the repository:\n  " + "\n  ".join(missing)


def test_agents_md_answers_each_question_with_one_command():
    """Set up, the state of every pack, everything green: one make target each, and the targets that build."""
    agents = (REPO / "AGENTS.md").read_text()
    for target in ("env", "status", "green"):
        rows = [line for line in agents.splitlines() if line.startswith("|") and f"`make -sC tools/pd2-las {target}`" in line]
        assert len(rows) == 1, f"AGENTS.md should answer one question with `make -sC tools/pd2-las {target}`"
    status = _status()
    row = next(line for line in agents.splitlines() if "make -sC tools/pd2-las <target>" in line)
    named = set(re.findall(r"`([a-z]+)`", row.split("<target>`", 1)[1]))
    assert named == set(status.TARGETS.values()) | {status.HEADS}, (
        f"AGENTS.md names the build targets {sorted(named)}; status.py has {sorted(set(status.TARGETS.values()) | {status.HEADS})}")
    assert named <= _targets()


def test_green_runs_what_the_test_workflow_runs():
    """`make -sC tools/pd2-las green` is `check_all.py --full`; it has to check what CI checks.

    The list of checks is written twice, in the workflow and in check_all.py. This keeps the
    two equal: a `run:` line added to the workflow fails here until `green` has it too.
    """
    workflow = (REPO / ".github" / "workflows" / "test.yml").read_text()
    source = (REPO / "tools" / "pd2-port" / "check_all.py").read_text()
    assert "check_all.py --full" in re.search(r"^green:.*\n\t(.+)$", (PD2 / "Makefile").read_text(), flags=re.M).group(1)

    yaml = pytest.importorskip("yaml")
    commands = [line.strip() for step in yaml.safe_load(workflow)["jobs"]["test"]["steps"]
                for line in str(step.get("run", "")).splitlines() if line.strip()]
    assert len(commands) >= 12, commands

    setup = re.compile(r"^(sudo |python -m pip install --upgrade pip |make -sC tools/pd2-las env$)")
    checks = {      # a command of the workflow -> what in check_all.py runs the same check
        r"pyflakes um tools tests$": '["-m", "pyflakes", "um", "tools", "tests"]',
        # -rsxX adds lines to the report and changes no test: the skip budget reads them, so the suite runs once
        r"^python -m pytest -q tests$": '["-m", "pytest", "-q", "-rsxX", "tests"]',
        r"^\./bin/um kb check --index$": '["-m", "um", "kb", "check", "--index"]',
        r"^\./bin/um publish check \.$": '["-m", "um", "publish", "check", "."]',
        r"fresh\.py check": '"fresh.py"), "check"]',
        # fresh.py builds this pack in a copy and compares all 16 zips with sha256sum -c
        r"^python tools/pd2-port/build_las_pack\.py$": '"fresh.py"), "check"]',
        r"^(for sha_file in dist/\*\.zip\.sha256 .*; do|sha256sum -c \"\$sha_file\"|done)$": '"fresh.py"), "check"]',
    }
    for command in commands:
        groups = re.match(r"^\./bin/um --help && for g in (.+); do \./bin/um \$g --help > /dev/null; done$", command)
        if groups:
            listed = re.search(r'^UM_GROUPS = "(.+)"\.split\(\)$', source, flags=re.M).group(1)
            assert groups.group(1) == listed, "check_all.py and the workflow list other `um` command groups"
            continue
        evidence = [proof for pattern, proof in checks.items() if re.search(pattern, command)]
        if evidence:
            assert evidence[0] in source, f"the workflow runs `{command}`; `green` does not"
        else:
            assert setup.match(command), f"the workflow runs `{command}`: add it to check_all.py --full, or to this test's setup"
