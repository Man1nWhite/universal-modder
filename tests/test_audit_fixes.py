"""Regression coverage for dotenv, checksum inventory, and build interpreter checks."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from um import publish

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", [".env", ".env.local", ".env.production", "secrets.env", "service.env.local"])
def test_dotenv_variants_are_ignored_and_rejected(tmp_path, capsys, name):
    (tmp_path / "README.md").write_text("mod")
    fake_key = "sk-" + "A" * 40
    (tmp_path / name).write_text(f"API_KEY={fake_key}")
    assert publish.check(str(tmp_path)) == 1
    output = capsys.readouterr().out
    assert "env file" in output
    assert "OpenAI key" in output
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", name], cwd=REPO)
    assert result.returncode == 0


@pytest.fixture
def fresh_checkout(tmp_path, monkeypatch):
    script = REPO / "tools/pd2-las/fresh.py"
    monkeypatch.syspath_prepend(str(script.parent))
    spec = importlib.util.spec_from_file_location("fresh_audit_test", script)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("/build/\n")
    monkeypatch.setattr(fresh, "REPO", tmp_path)
    monkeypatch.setattr(fresh, "PY", Path(sys.executable))
    return fresh, tmp_path


def test_fresh_inventory_fails_for_missing_sidecar_before_build(fresh_checkout):
    fresh, tmp_path = fresh_checkout
    dist = tmp_path / "dist" / "character"
    dist.mkdir(parents=True)
    pack = dist / "pack.zip"
    pack.write_bytes(b"zip")
    with pytest.raises(SystemExit, match="incomplete ZIP/checksum inventory"):
        fresh.tracked_zips()
    Path(str(pack) + ".sha256").write_text("digest")
    assert fresh.tracked_zips() == ["dist/character/pack.zip"]
    subprocess.run(["git", "add", "dist"], cwd=tmp_path, check=True)
    Path(str(pack) + ".sha256").unlink()
    with pytest.raises(SystemExit, match="pack.zip"):
        fresh.tracked_zips()


@pytest.fixture
def fresh_builder(fresh_checkout, tmp_path_factory, monkeypatch):
    from pack_checksum import write_checksum

    fresh, root = fresh_checkout
    built_rel = Path("dist/Christie/Christie_Clover_LAS.zip")
    dep_rel = Path("dist/Miranda_L4D2/Miranda_L4D2_LAS.zip")
    for rel in (built_rel, dep_rel):
        pack = root / rel
        pack.parent.mkdir(parents=True)
        pack.write_bytes(b"zip output from input")
        write_checksum(pack, root=root)
    builder = root / "builder.py"
    monkeypatch.setitem(fresh.BUILDERS, "cloverchristie", [builder.name])
    # Shared unit folder is not inside the checkout and has no managed stamp.
    external = tmp_path_factory.mktemp("shared templates")
    for name in fresh.extract_2b.TEMPLATE_FILES:
        (external / name).touch()
    monkeypatch.setenv(fresh.extract_2b.ENV, str(external))
    monkeypatch.setattr(fresh.extract_2b, "TEMPLATES", external)
    return fresh, root, builder, built_rel, dep_rel, external


def test_fresh_check_will_not_credit_a_noop_builder(fresh_builder, capsys):
    fresh, root, builder, output, _, _ = fresh_builder
    builder.write_text("print('done without making anything')\n")
    assert fresh.main(["check", "--builders", "cloverchristie"]) == 2
    assert f"did not produce: {output.as_posix()}" in capsys.readouterr().out
    assert (root / output).read_bytes() == b"zip output from input"


def test_fresh_checks_original_bytes_before_even_running_the_builder(fresh_builder):
    fresh, root, builder, output, _, _ = fresh_builder
    builder.write_text("raise AssertionError('builder must not run against a corrupt original')\n")
    (root / output).write_bytes(b"corrupt bytes")
    with pytest.raises(SystemExit, match="original distribution: .*ZIP does not match its checksum"):
        fresh.main(["check", "--builders", "cloverchristie"])
    assert not (root / "build/fresh/tree").exists()


def test_fresh_subset_uses_external_templates_and_keeps_other_zips_as_inputs(fresh_builder, capsys):
    fresh, _, builder, output, dependency, shared = fresh_builder
    builder.write_text(f"""\
import hashlib, os
from pathlib import Path
out = Path({output.as_posix()!r})
sidecar = out.with_suffix('.zip.sha256')
assert not out.exists() and not sidecar.exists()
assert Path(os.environ['PD2_2B_TEMPLATES']) == Path({str(shared)!r})
assert (Path(os.environ['PD2_2B_TEMPLATES']) / '2b.model').is_file()
out.parent.mkdir(parents=True, exist_ok=True)
raw = Path({dependency.as_posix()!r}).read_bytes()
out.write_bytes(raw)
sidecar.write_text(f'{{hashlib.sha256(raw).hexdigest()}}  {{out.as_posix()}}\\n')
""")
    assert fresh.main(["check", "--builders", "cloverchristie"]) == 0
    log = capsys.readouterr().out
    assert "1 of 1 tracked zips are the tracked bytes after a fresh build" in log
    assert dependency.as_posix() not in log


@pytest.mark.skipif(os.name != "posix" or not shutil.which("bash"), reason="POSIX shell setup")
def test_environment_rejects_old_existing_interpreter_before_changing_files(tmp_path):
    script = tmp_path / "tools" / "pd2-las" / "recover_env.sh"
    script.parent.mkdir(parents=True)
    shutil.copyfile(REPO / "tools/pd2-las/recover_env.sh", script)
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 1\n")
    python.chmod(0o755)
    result = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "needs Python 3.11 or newer" in result.stderr
    assert not (tmp_path / "build").exists()
