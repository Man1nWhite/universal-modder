"""`um kb pr` and the repo `um kb` talks to.

`UM_KB_REPO` used to default to the upstream toolkit even inside a fork, so `um kb sync` mirrored
the wrong knowledge base and `um kb pr --yes` forked from and targeted upstream — carrying notes
upstream's rules would close. The default is now the clone's `origin`, falling back to upstream.
"""
from __future__ import annotations

import pytest

from um import kb


@pytest.mark.parametrize("url, expect", [
    ("https://github.com/Man1nWhite/universal-modder", "Man1nWhite/universal-modder"),
    ("https://github.com/Man1nWhite/universal-modder.git", "Man1nWhite/universal-modder"),
    ("git@github.com:Man1nWhite/universal-modder.git", "Man1nWhite/universal-modder"),
    ("ssh://git@github.com/rehan-remade/universal-modder", "rehan-remade/universal-modder"),
    ("https://gitlab.com/someone/repo", None),
    ("not a url", None),
])
def test_default_repo_parses_github_remotes(monkeypatch, url, expect):
    class Out:
        stdout = url + "\n"
        returncode = 0

    monkeypatch.setattr(kb.subprocess, "run", lambda *a, **kw: Out())
    got = kb._default_repo()
    if expect is None:
        assert got == "rehan-remade/universal-modder"
    else:
        assert got == expect


def test_default_repo_falls_back_when_git_is_unavailable(monkeypatch):
    def boom(*a, **kw):
        raise OSError("no git here")

    monkeypatch.setattr(kb.subprocess, "run", boom)
    assert kb._default_repo() == "rehan-remade/universal-modder"


def test_default_repo_falls_back_when_not_a_repo(monkeypatch):
    class Out:
        stdout = "fatal: not a git repository\n"
        returncode = 128

    monkeypatch.setattr(kb.subprocess, "run", lambda *a, **kw: Out())
    assert kb._default_repo() == "rehan-remade/universal-modder"


@pytest.mark.parametrize("branch, fork, expect", [
    ("kb/terraria-note", "https://github.com/someone/universal-modder.git", "someone:kb/terraria-note"),
    ("kb/terraria-note", "git@github.com:someone/universal-modder.git", "someone:kb/terraria-note"),
    ("kb/terraria-note", None, "kb/terraria-note"),
])
def test_pr_head_formats_the_fork_ref(branch, fork, expect):
    assert kb.pr_head(branch, fork) == expect


# --------------------------------------------------------------------------- check_note

VALID = """---
kind: game
title: A working note about Terraria
game: Terraria
engine: xna-fna
route: loader-api
status: working
date: 2026-11-27
agents: ["Codex (gpt-6)"]
---

## Setup

Terraria 1.4.4.9 with tModLoader.

## Route

tModLoader C# mod.

## Verification

Built and ran in game.

## Gotchas

1. It fails. **Cause:** thing. **Fix:** other thing.
"""


def _note(tmp_path, text):
    p = tmp_path / "note.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_check_note_passes_a_valid_note(tmp_path):
    fails, warns = kb.check_note(_note(tmp_path, VALID))
    assert fails == []


def test_check_note_fails_on_missing_front_matter(tmp_path):
    fails, warns = kb.check_note(_note(tmp_path, "no front matter here"))
    assert fails and "front matter" in fails[0]


def test_check_note_fails_on_a_secret(tmp_path):
    secret = "sk-ant-" + "a" * 30
    fails, warns = kb.check_note(_note(tmp_path, VALID + f"\n## Gotchas\n\nhidden {secret}\n"))
    assert any("Anthropic key" in f for f in fails)


def test_check_note_fails_on_a_huge_pasted_code_block(tmp_path):
    fails, warns = kb.check_note(_note(tmp_path, VALID + "\n```\n" + "x = 1\n" * 160 + "```\n"))
    assert any("code block" in f for f in fails)


def test_check_note_fails_on_missing_sections(tmp_path):
    broken = VALID.replace("## Setup", "## Steps")
    fails, warns = kb.check_note(_note(tmp_path, broken))
    assert any("missing section" in f for f in fails)


def test_check_note_fails_on_bad_date(tmp_path):
    bad = VALID.replace("date: 2026-11-27", "date: last Tuesday")
    fails, warns = kb.check_note(_note(tmp_path, bad))
    assert any("date" in f for f in fails)
