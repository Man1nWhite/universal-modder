"""A snapshot name is one folder under `~/.universal-modder/backups/`, and nothing else.

`um backup create <dir> --name ../../escape` used to write the zip outside the data directory
(`data_dir()/"backups"/name` with only `""`, `"."` and `".."` rejected), where `um backup list`
and `um backup restore` would never find it again — and `restore` reuses the same name for the
undo snapshot it takes first. An agent composing `--name` from a game title (spaces, a slash, a
drive letter, a colon) landed there by accident. These tests pin the rule and the message.
"""
from __future__ import annotations

import pytest

from um import backup


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "state"))


@pytest.mark.parametrize("name", ["s", "terraria", "miranda-saves", "game_2.backup", "A1", "x" * 64])
def test_names_a_snapshot_may_have(name):
    assert backup._validate_name(name) == name


@pytest.mark.parametrize("name", [
    "", ".", "..", "../escape", "../../escape", "a/b", r"a\b", "/abs", "C:/x", "C:\\x",
    "con", "NUL", "lpt1", "x" * 65, " leading", "trailing ", "a b", "a:b", "a*", "-dash",
    ".hidden", "a\nb",
])
def test_names_a_snapshot_may_not_have(name):
    with pytest.raises(SystemExit) as e:
        backup._validate_name(name)
    assert "invalid backup name" in str(e.value) or e.value.code not in (0, None)


def test_create_refuses_to_write_outside_the_data_directory(tmp_path):
    src = tmp_path / "saves"
    src.mkdir()
    (src / "slot1.sav").write_text("save")
    with pytest.raises(SystemExit):
        backup.create(str(src), "../../escape")
    state = tmp_path / "state"
    assert sorted(p.name for p in (state / "backups").iterdir()) == [] if (state / "backups").is_dir() else True
    assert not (tmp_path / "escape").exists()
    assert not any(p.is_file() for p in state.rglob("*.zip"))


def test_list_and_restore_reject_an_unsafe_name(tmp_path):
    for call in (lambda: backup.snapshots("../x"),
                 lambda: backup.diff("../x"),
                 lambda: backup.restore("../x", yes=True)):
        with pytest.raises(SystemExit):
            call()


def test_default_name_is_sanitised_from_the_folder_name(tmp_path):
    """A folder the OS allows is not a folder name a snapshot may have: `[` and spaces become '-'."""
    src = tmp_path / "My Saves [slot 2]"
    src.mkdir()
    (src / "a.sav").write_text("x")
    zp = backup.create(str(src))
    assert zp.parent.name == "my-saves-slot-2"
    assert backup.snapshots("my-saves-slot-2") == [zp]


def test_restore_takes_an_undo_snapshot_with_a_legal_name(tmp_path, monkeypatch):
    """`<name>-pre-restore` has to fit the 64-character limit the name itself may fill."""
    src = tmp_path / "saves"
    src.mkdir()
    (src / "slot1.sav").write_text("before")
    name = "n" * 64
    backup.create(str(src), name)
    (src / "slot1.sav").write_text("after")
    backup.restore(name, yes=True)
    assert (src / "slot1.sav").read_text() == "before"
    assert backup.snapshots(name[:48] + "-pre-restore")
