"""`um win launch <exe>` must start the game in the exe's own folder (games open their data files relative to
the working directory; Tomb Raider: Legend dies with "Failed to open BIGFILE.000" otherwise) — and must not
go through cmd.exe, which re-parsed `&` and friends as command separators."""
from um import win


class FakePopen:
    made = []

    def __init__(self, cmd, **kw):
        self.cmd = cmd
        self.kw = kw
        FakePopen.made.append((cmd, kw))


def test_launch_exe_starts_in_its_own_folder(monkeypatch):
    FakePopen.made = []
    monkeypatch.setattr(win.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(win, "is_windows", lambda: True)
    monkeypatch.setattr(win, "to_win", lambda p: p)
    win.launch(r"A:\Games\Foo\foo.exe", ["-windowed"])
    assert len(FakePopen.made) == 1
    cmd, kw = FakePopen.made[0]
    assert cmd == [r"A:\Games\Foo\foo.exe", "-windowed"]
    assert kw["cwd"] == r"A:\Games\Foo"


def test_launch_exe_path_with_meta_characters_is_passed_verbatim(monkeypatch):
    """`A&B` used to re-parse as a command separator under cmd /c start."""
    FakePopen.made = []
    monkeypatch.setattr(win.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(win, "is_windows", lambda: True)
    monkeypatch.setattr(win, "to_win", lambda p: p)
    win.launch(r"A:\Games\A&B\game.exe", ["-windowed", "fullscreen & notes.txt"])
    cmd, kw = FakePopen.made[0]
    assert cmd == [r"A:\Games\A&B\game.exe", "-windowed", "fullscreen & notes.txt"]
    assert kw["cwd"] == r"A:\Games\A&B"


def test_launch_exe_reports_a_missing_file(monkeypatch):
    def boom(*a, **kw):
        raise FileNotFoundError(r"A:\Games\Foo\foo.exe")

    monkeypatch.setattr(win.subprocess, "Popen", boom)
    monkeypatch.setattr(win, "is_windows", lambda: True)
    monkeypatch.setattr(win, "to_win", lambda p: p)
    try:
        win.launch(r"A:\Games\Foo\foo.exe", [])
    except SystemExit as e:
        assert "could not launch" in str(e) or e.code == 1
    else:
        raise AssertionError("a missing exe must die with a message, not a traceback")


def test_launch_under_wsl_uses_the_linux_path_and_parent(monkeypatch):
    FakePopen.made = []
    monkeypatch.setattr(win.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(win, "is_windows", lambda: False)
    monkeypatch.setattr(win, "is_wsl", lambda: True)
    monkeypatch.setattr(win, "to_posix", lambda p: "/mnt/c/Games/Foo/foo.exe")
    win.launch(r"C:\Games\Foo\foo.exe", ["-windowed"])
    cmd, kw = FakePopen.made[0]
    assert cmd == ["/mnt/c/Games/Foo/foo.exe", "-windowed"]
    assert kw["cwd"] == "/mnt/c/Games/Foo"


def test_launch_steam_url_has_no_directory(monkeypatch):
    calls = []
    monkeypatch.setattr(win.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(win, "is_wsl", lambda: False)
    win.launch("105600", [], steam=True)
    assert calls and "/D" not in calls[0]
    assert calls[0][-1].startswith("steam://")
