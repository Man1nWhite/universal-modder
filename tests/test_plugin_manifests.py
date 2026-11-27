"""Every plugin manifest that carries a version must agree with `um.__version__`.

The repo ships the same plugin metadata to Claude Code, Codex, Cursor, Gemini CLI and OpenCode.
They used to drift: `.claude-plugin/plugin.json` had no `version` at all, so a Claude install
reported none, while Codex and Cursor reported 0.2.0.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import um

ROOT = Path(__file__).resolve().parent.parent

VERSIONED = [
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    "gemini-extension.json",
    "plugins/opencode/package.json",
]


def _read_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_every_versioned_manifest_matches_um_version():
    for rel in VERSIONED:
        data = _read_json(rel)
        assert "version" in data, f"{rel} declares no version"
        assert data["version"] == um.__version__, f"{rel}: {data['version']} != {um.__version__}"


def test_pyproject_version_matches_um_version():
    toml = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', toml, re.M)
    assert m, "no [project] version in pyproject.toml"
    assert m.group(1) == um.__version__


def test_every_plugin_manifest_is_json_and_named_universal_modder():
    for rel in VERSIONED:
        data = _read_json(rel)
        assert data.get("name") == "universal-modder", rel


def test_package_json_is_private():
    """The npm manifest exists only to pin node-unrar-js; it must never be published."""
    assert _read_json("package.json").get("private") is True
