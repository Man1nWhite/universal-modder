"""`um kb sync` mirrors knowledge/ from GitHub, and must never cache half of it.

The tree API sets `"truncated": true` when a repository outgrows one response. The code read
`tree["tree"]` and nothing else, so a truncated answer was written as the whole cache and stamped
fresh for a day: `um kb search` then quietly answered from part of the knowledge base.
"""
from __future__ import annotations

import json

import pytest

from um import kb


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "state"))


def _tree(paths, truncated=False):
    return json.dumps({"truncated": truncated,
                       "tree": [{"path": f"knowledge/{p}", "type": "blob"} for p in paths]}).encode()


def test_sync_writes_the_notes_and_a_stamp(monkeypatch):
    monkeypatch.setattr(kb, "_fetch", lambda url, **kw: _tree(["README.md", "index.json"]) if "trees" in url
                        else b"body of " + url.rsplit("/", 1)[1].encode())
    root = kb.sync(quiet=True)
    assert (root / "README.md").read_text().startswith("body of README.md")
    assert (root / "index.json").read_text().startswith("body of index.json")
    assert (root / ".synced").exists()


def test_a_truncated_tree_is_an_error_not_a_partial_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(kb, "_fetch", lambda url, **kw: _tree(["a.md"], truncated=True))
    with pytest.raises(OSError) as e:
        kb.sync(quiet=True)
    assert "truncated" in str(e.value)
    assert not kb.cache_root().exists()


def test_an_empty_listing_is_an_error(monkeypatch):
    monkeypatch.setattr(kb, "_fetch", lambda url, **kw: _tree([]))
    with pytest.raises(OSError):
        kb.sync(quiet=True)


def test_a_non_json_answer_is_an_error(monkeypatch):
    monkeypatch.setattr(kb, "_fetch", lambda url, **kw: b"<html>rate limited</html>")
    with pytest.raises(OSError):
        kb.sync(quiet=True)


def test_a_failed_sync_keeps_a_cache_that_is_already_there(monkeypatch):
    """A stale cache beats no knowledge base: resolve_root falls back to it."""
    root = kb.cache_root()
    root.mkdir(parents=True)
    (root / "kept.md").write_text("old note")
    (root / ".synced").write_text("0", encoding="utf-8")   # stale

    def boom(url, **kw):
        raise OSError("network down")

    monkeypatch.setattr(kb, "_fetch", boom)
    assert kb.resolve_root(remote=True) == root
    assert (root / "kept.md").read_text() == "old note"
