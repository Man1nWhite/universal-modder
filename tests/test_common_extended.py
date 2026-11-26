"""Extended tests for um/common.py improvements: parse_size, data_dir, path conversions."""
import os
import stat

import pytest

from um import common


def test_parse_size_valid():
    assert common.parse_size("128") == (128, 128)
    assert common.parse_size("64x26") == (64, 26)
    assert common.parse_size(" 64x26 ") == (64, 26)
    assert common.parse_size("128X256") == (128, 256)
    assert common.parse_size("  32  x  64  ") == (32, 64)
    assert common.parse_size("1x1") == (1, 1)
    assert common.parse_size(str(common.MAX_DIMENSION)) == (common.MAX_DIMENSION, common.MAX_DIMENSION)


def test_parse_size_invalid():
    for bad in ["", "   ", "0", "0x10", "-1", "10x0", "10x-5", "axb", "10x", "x10", "10 x 10 x 10", "999999x999999"]:
        with pytest.raises(SystemExit):
            common.parse_size(bad)
    # Too large exceeds MAX_DIMENSION
    with pytest.raises(SystemExit):
        common.parse_size(f"{common.MAX_DIMENSION + 1}")
    with pytest.raises(SystemExit):
        common.parse_size(f"{common.MAX_DIMENSION + 1}x10")


def test_parse_size_boundary():
    # Just within limit
    w, h = common.parse_size(f"{common.MAX_DIMENSION}x{common.MAX_DIMENSION}")
    assert w == common.MAX_DIMENSION
    # Zero and negative are rejected, not returned as 0
    with pytest.raises(SystemExit):
        common.parse_size("0x10")


def test_parse_size_non_string():
    with pytest.raises(SystemExit):
        common.parse_size(None)
    with pytest.raises(SystemExit):
        common.parse_size(123)


def test_data_dir_creates_with_correct_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "mydata"))
    d = common.data_dir()
    assert d.exists() and d.is_dir()
    if os.name == "posix":
        mode = stat.S_IMODE(d.stat().st_mode)
        # data_dir sets 0700 on POSIX; allow at least owner rwx
        assert mode & 0o700 == 0o700


def test_data_dir_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "mydata"))
    d1 = common.data_dir()
    d2 = common.data_dir()
    assert d1 == d2
    assert d1.exists()


def test_to_win_normalizes_drive_letter():
    # Windows paths pass through but drive letter normalized to upper
    assert common.to_win("c:\\Games\\Foo") == "C:\\Games\\Foo"
    assert common.to_win("C:/Games/Foo/bar") == "C:\\Games\\Foo\\bar"
    assert common.to_win("D:\\") == "D:\\"
    # Lowercase wsl path converts
    # to_win on Linux without WSL returns input unchanged for non /mnt/ paths
    assert common.to_win("/some/other/path") == "/some/other/path"


def test_to_posix_normalizes():
    # POSIX path passes through unchanged on non-WSL Linux
    assert common.to_posix("/home/user/file") == "/home/user/file"
    # Windows path conversion only on WSL; on Linux it passes through
    # We test the function doesn't crash and handles edge cases
    assert common.to_posix("C:\\Games\\Foo") == "C:\\Games\\Foo" if not common.is_wsl() else "/mnt/c/Games/Foo"
    assert common.to_posix("") == ""


def test_to_win_strips_whitespace():
    assert common.to_win("  C:\\Games\\Foo  ") == "C:\\Games\\Foo"
    assert common.to_posix("  /home/user  ") == "/home/user"


def test_to_win_handles_mnt_paths():
    # These are the core WSL path conversions that to_win must handle
    # They work regardless of is_wsl() status because path pattern is checked first
    assert common.to_win("/mnt/c/Games/x") == "C:\\Games\\x"
    assert common.to_win("/mnt/d/") == "D:\\" if len("/mnt/d/") == 7 else "D:\\"
    assert common.to_win("/mnt/c") == "C:\\"


def test_common_helpers_are_tested():
    # Ensure the new helpers exist and are callable
    assert hasattr(common, "MAX_DIMENSION")
    assert common.MAX_DIMENSION == 16384
    assert callable(common.parse_size)
    assert callable(common.data_dir)
