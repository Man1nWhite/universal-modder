"""Regression coverage for dotenv, checksum inventory, and build interpreter checks."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
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


def test_fresh_inventory_fails_for_missing_sidecar_before_build(tmp_path, monkeypatch):
    script = REPO / "tools/pd2-las/fresh.py"
    monkeypatch.syspath_prepend(str(script.parent))
    spec = importlib.util.spec_from_file_location("fresh_audit_test", script)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    dist = tmp_path / "dist" / "character"
    dist.mkdir(parents=True)
    pack = dist / "pack.zip"
    pack.write_bytes(b"zip")
    monkeypatch.setattr(fresh, "REPO", tmp_path)
    with pytest.raises(SystemExit, match="incomplete ZIP/checksum inventory"):
        fresh.tracked_zips()
    Path(str(pack) + ".sha256").write_text("digest")
    assert fresh.tracked_zips() == ["dist/character/pack.zip"]
    subprocess.run(["git", "add", "dist"], cwd=tmp_path, check=True)
    Path(str(pack) + ".sha256").unlink()
    with pytest.raises(SystemExit, match="pack.zip"):
        fresh.tracked_zips()


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
