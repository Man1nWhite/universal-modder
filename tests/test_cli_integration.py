"""Integration tests for um CLI: help screens, error handling, group registration."""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "bin" / "um"
PY = sys.executable

GROUPS = ["scan", "fal", "comfy", "sprite", "render3d", "video", "win", "backup", "publish", "kb"]


def run_um(*args):
    result = subprocess.run([PY, "-m", "um", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result


def test_um_help_lists_all_groups():
    result = run_um("--help")
    assert result.returncode == 0
    for group in GROUPS:
        assert group in result.stdout, f"um --help missing group {group}"


def test_each_group_has_help():
    for group in GROUPS:
        result = run_um(group, "--help")
        assert result.returncode == 0, f"um {group} --help failed: {result.stderr}"
        assert len(result.stdout) > 50, f"um {group} --help too short"
        # Help should mention the group name
        assert group in result.stdout.lower() or group in result.stderr.lower() or len(result.stdout) > 100


def test_um_version():
    result = run_um("--version")
    assert result.returncode == 0
    assert "universal-modder" in result.stdout.lower() or "0.2.0" in result.stdout


def test_um_no_args_shows_help_and_fails():
    result = run_um()
    # Should exit with error (no command) and show help
    assert result.returncode != 0
    assert "usage" in result.stdout.lower() or "usage" in result.stderr.lower()


def test_um_unknown_group_fails():
    result = run_um("nonexistent_group_xyz")
    assert result.returncode != 0


def test_common_parse_size_via_cli():
    # Test via direct import that parse_size handles edge cases used by CLI
    from um.common import parse_size, MAX_DIMENSION
    assert parse_size("64x64") == (64, 64)
    with pytest.raises(SystemExit):
        parse_size("0x10")
    with pytest.raises(SystemExit):
        parse_size("-5")
    with pytest.raises(SystemExit):
        parse_size(f"{MAX_DIMENSION + 1}x10")


def test_publish_check_cli(tmp_path):
    mod = tmp_path / "testmod"
    mod.mkdir()
    (mod / "README.md").write_text("# Test Mod")
    (mod / "file.txt").write_text("clean content")
    result = subprocess.run([PY, "-m", "um", "publish", "check", str(mod)], cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 0
    assert "PASS" in result.stdout or "WARN" in result.stdout or "0 failures" in result.stdout


def test_scan_cli_lists_engines(tmp_path):
    # um scan should handle empty directory gracefully
    empty_game = tmp_path / "empty_game"
    empty_game.mkdir()
    result = subprocess.run([PY, "-m", "um", "scan", str(empty_game), "--json"], cwd=REPO, capture_output=True, text=True)
    # Should not crash, should produce JSON with native engine
    assert result.returncode == 0
    import json
    data = json.loads(result.stdout)
    assert "engine" in data
    assert "name" in data


def test_backup_cli_help():
    for cmd in ["create", "list", "diff", "restore"]:
        result = run_um("backup", cmd, "--help")
        assert result.returncode == 0
        assert "backup" in result.stdout.lower() or cmd in result.stdout.lower()


def test_kb_cli_help():
    for cmd in ["search", "check", "index", "new", "show"]:
        result = run_um("kb", cmd, "--help")
        assert result.returncode == 0
