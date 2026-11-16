"""Directory swaps must not redirect a POSIX restore or its verified staging files."""
import os
from pathlib import Path

import pytest

from um import backup


@pytest.mark.skipif(os.name != "posix" or not hasattr(os, "O_NOFOLLOW"), reason="POSIX dir_fd protection")
def test_replaced_parent_directory_cannot_redirect_restore(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "state"))
    target = tmp_path / "save"
    (target / "sub").mkdir(parents=True)
    (target / "sub" / "file").write_text("backup")
    backup.create(str(target), "s")
    (target / "sub" / "file").write_text("current")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file").write_text("outside")
    original = backup._parent_fd

    def swap_then_open(root_fd, parts, create_dirs):
        (target / "sub").rename(target / "real-sub")
        (target / "sub").symlink_to(outside, target_is_directory=True)
        return original(root_fd, parts, create_dirs)

    monkeypatch.setattr(backup, "_parent_fd", swap_then_open)
    with pytest.raises(OSError):
        backup.restore("s", yes=True)
    assert (outside / "file").read_text() == "outside"
    assert (target / "real-sub" / "file").read_text() == "current"
    assert not list(target.glob(".um-restore-*"))
    assert Path(backup.snapshots("s-pre-restore")[-1]).is_file()


@pytest.mark.skipif(os.name != "posix" or not hasattr(os, "O_NOFOLLOW"), reason="POSIX dir_fd protection")
def test_swapped_root_cannot_redirect_destination_or_staged_source(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "state"))
    target, moved, outside = tmp_path / "save", tmp_path / "moved", tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    (target / "file").write_text("backup")
    (outside / "file").write_text("outside")
    backup.create(str(target), "s")
    (target / "file").write_text("current")
    original = backup._parent_fd

    def swap_then_open(root_fd, parts, create_dirs):
        target.rename(moved)
        target.symlink_to(outside, target_is_directory=True)
        return original(root_fd, parts, create_dirs)

    monkeypatch.setattr(backup, "_parent_fd", swap_then_open)
    backup.restore("s", yes=True)
    assert (outside / "file").read_text() == "outside"
    assert (moved / "file").read_text() == "backup"
    assert not list(moved.glob(".um-restore-*"))
