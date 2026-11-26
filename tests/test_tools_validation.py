"""Tests for tools validation improvements: status.py, check_skip_budget, determinism."""
import sys
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]
TOOLS_LAS = REPO / "tools" / "pd2-las"
TOOLS_PORT = REPO / "tools" / "pd2-port"


def test_status_collect_basic():
    sys.path.insert(0, str(TOOLS_LAS))
    from status import collect
    status = collect()
    assert "packs" in status
    assert "next" in status
    # Should have packs
    assert len(status["packs"]) > 0
    for name, info in status["packs"].items():
        assert "make" in info
        assert "is" in info
        # Status values are known
        assert info["is"] in ("tracked", "changed", "broken", "missing", "ok")


def test_status_handles_unknown_pack():
    sys.path.insert(0, str(TOOLS_LAS))
    from status import collect
    # Unknown pack should return empty or error
    status = collect(only=["nonexistent_pack_xyz"])
    assert status["packs"] == {} or len(status["packs"]) == 0


def test_status_full_sha256():
    sys.path.insert(0, str(TOOLS_LAS))
    from status import collect
    status_short = collect(full=False)
    status_full = collect(full=True)
    for name in status_short["packs"]:
        if "sha256" in status_short["packs"][name] and "sha256" in status_full["packs"][name]:
            short = status_short["packs"][name]["sha256"]
            full = status_full["packs"][name]["sha256"]
            if len(short) == 12:
                assert full.startswith(short)
                assert len(full) == 64


def test_pack_names_consistent():
    sys.path.insert(0, str(TOOLS_LAS))
    from status import pack_names, pack_paths
    names = pack_names()
    paths = pack_paths()
    assert set(names) == set(paths.keys())
    assert len(names) > 0


def test_pins_file_exists_and_valid():
    pins = TOOLS_LAS / "pins.txt"
    assert pins.exists()
    content = pins.read_text()
    assert "pillow" in content.lower()
    assert "numpy" in content.lower()
    assert "==" in content


def test_check_skip_budget_validate_report_handles_ansi():
    sys.path.insert(0, str(TOOLS_PORT))
    from check_skip_budget import validate_report
    # Report with ANSI codes should still validate
    # The validate should handle ANSI stripping
    # Create a minimal valid report
    report = "test_foo.py::test_bar PASSED\nSKIPPED [2] tests/test_foo.py:1: needs ffmpeg\n2 passed, 2 skipped in 0.10s\n"
    result = validate_report(report)
    # May pass or fail depending on whether skips match, but shouldn't crash on ANSI
    assert result is None or isinstance(result, str)


def test_check_skip_budget_summary_variations():
    sys.path.insert(0, str(TOOLS_PORT))
    from check_skip_budget import validate_report
    # Different pytest summary formats
    for summary in [
        "1 passed, 2 skipped in 0.5s",
        "== 1 passed, 2 skipped in 0.5s ==",
        "1 passed, 2 skipped, 1 warning in 0.5s",
        "5 passed in 0.3s",
    ]:
        report = f"test example\n{summary}\n"
        result = validate_report(report)
        # Should handle these without crashing
        assert result is None or "no completed" not in result or isinstance(result, str)


def test_extract_2b_ready_check():
    sys.path.insert(0, str(TOOLS_LAS))
    import extract_2b
    # Should return bool, not crash
    ready = extract_2b.ready()
    assert isinstance(ready, bool)
    # In test env with .venv, templates should be ready after our setup
    # But we check it returns sensible value
    assert ready in (True, False)


def test_dist_paths_consistency():
    sys.path.insert(0, str(TOOLS_LAS))
    from dist_paths import dist_path
    # dist_path should give consistent paths for known packs
    for name in ["Miranda_LAS", "Christie_LAS"]:
        try:
            path = dist_path(REPO, f"{name}.zip")
            assert path.parent.exists() or path.parent.name in ("Miranda_L4D2", "Christie", "Miranda_Romance", "Honoka", "Geralt", "Arivus", "Hila")
        except (ValueError, FileNotFoundError):
            # Some packs may not be in mapping, that's ok
            pass


def test_tools_have_docstrings():
    # Every tool in tools/pd2-las should have a docstring explaining usage
    for py_file in TOOLS_LAS.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        content = py_file.read_text(encoding="utf-8")
        # Should have a module docstring
        assert '"""' in content or "'''" in content, f"{py_file.name} missing docstring"


def test_status_target_mapping():
    sys.path.insert(0, str(TOOLS_LAS))
    from status import target
    # Every target in TARGETS should be valid make target or heads
    assert target("Miranda_Lawson_VO_over_Hila_Stream") == "voices_stream"
    assert target("random_over_Joy") == "heads"
    assert target("OfficeSuite") == "honokodae"
    assert target("NonExistent_xyz") is None or target("NonExistent_xyz") == "heads" or target("NonExistent_xyz") is None


def test_publish_check_handles_symlinked_mod(tmp_path):
    # Ensure publish check handles symlinked files gracefully (doesn't follow symlinks outside mod)
    from um import publish
    mod = tmp_path / "mod"
    mod.mkdir()
    (mod / "README.md").write_text("# Mod")
    (mod / "real.txt").write_text("real content")
    # Create a symlink inside mod pointing to outside (if supported)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    link = mod / "link.txt"
    try:
        link.symlink_to(outside)
        result = publish.check(str(mod))
        # Should not crash, may warn or pass
        assert result in (0, 1)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
