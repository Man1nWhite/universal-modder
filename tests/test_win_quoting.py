"""Values that reach a PowerShell `-Command` string are quoted as PowerShell literals.

PowerShell ends a single-quoted string at the first `'` and escapes one by doubling it, so
`-Name 'Assassin's Creed*'` was a parse error and everything after the quote was parsed as
script. `um win ps`, `um win kill`'s `pid_of` lookup and the Steam launch URL all take a name
straight from the command line — usually composed by an agent — so the escaping has to be here
and not in the caller.
"""
from __future__ import annotations

import os

import pytest

from um import win


@pytest.mark.parametrize("value, literal", [
    ("Game", "'Game'"),
    ("Assassin's Creed", "'Assassin''s Creed'"),
    ("Assassin's Creed*", "'Assassin''s Creed*'"),
    ("''", "''''''"),
    ("a'; Start-Process calc; '", "'a''; Start-Process calc; '''"),
    ("C:\\Games\\O'Brien\\game.exe", "'C:\\Games\\O''Brien\\game.exe'"),
])
def test_ps_literal_doubles_every_quote(value, literal):
    assert win.ps_literal(value) == literal


def test_ps_literal_leaves_no_command_separator(monkeypatch):
    """A quoted name never ends the string early: the whole payload stays one argument."""
    captured = []
    monkeypatch.setattr(win, "powershell", lambda script, **kw: captured.append(script) or "")
    win.pid_of("x'; calc; '")
    script = captured[0]
    assert "'x''; calc; '''" in script
    # the inverted commas in the script are balanced: an unterminated literal would be odd
    assert script.count("'") % 2 == 0


def test_processes_quotes_the_wildcard_name(monkeypatch):
    captured = []
    monkeypatch.setattr(win, "powershell", lambda script, **kw: captured.append(script) or "")
    win.processes("Assassin's Creed")
    assert "-Name 'Assassin''s Creed*'" in captured[0]


def test_processes_without_a_name_filters_nothing(monkeypatch):
    captured = []
    monkeypatch.setattr(win, "powershell", lambda script, **kw: captured.append(script) or "")
    win.processes()
    assert "-Name" not in captured[0]


@pytest.mark.parametrize("args", [["-a", "&", "calc"], ["-x", "|", "y"], ["-q", "%PATH%"], ['-q', '"quoted"']])
def test_steam_launch_refuses_cmd_metacharacters(args, monkeypatch):
    """The URL used to go through `cmd /c start`, which re-parses `&`, `|` and `%...%`."""
    monkeypatch.setattr(win, "is_windows", lambda: False)
    monkeypatch.setattr(win, "is_wsl", lambda: False)
    monkeypatch.setattr(win.subprocess, "run", lambda *a, **kw: pytest.fail("nothing should be launched"))
    with pytest.raises(SystemExit):
        win.launch("105600", args, steam=True)


def test_steam_launch_uses_shellexecute_on_windows(monkeypatch):
    """Native Windows hands the URL to ShellExecute: no cmd.exe, so nothing re-parses it."""
    opened = []
    monkeypatch.setattr(win, "is_windows", lambda: True)
    monkeypatch.setattr(os, "startfile", opened.append, raising=False)
    monkeypatch.setattr(win.subprocess, "run", lambda *a, **kw: pytest.fail("no subprocess on Windows"))
    win.launch("105600", ["-windowed"], steam=True)
    assert opened == ["steam://run/105600//-windowed/"]
