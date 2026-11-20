"""Managed extraction caches are derived inputs, not sources of truth."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path[:0] = [str(TOOLS / "pd2-las"), str(TOOLS)]

import archive_cache  # noqa: E402
import build_joy_head_mods as heads  # noqa: E402
import build_models as bm  # noqa: E402
import extract_2b  # noqa: E402


def test_stale_2b_cache_cannot_be_used_as_a_managed_template(tmp_path, monkeypatch):
    archive = tmp_path / "2b.rar"
    archive.write_bytes(b"first template")
    cache = tmp_path / "cache"
    directory = cache / extract_2b.UNIT
    monkeypatch.setattr(extract_2b, "RAR", archive)
    monkeypatch.setattr(extract_2b, "OUT", cache)
    monkeypatch.setattr(extract_2b, "TEMPLATES", directory)
    monkeypatch.setattr(extract_2b.shutil, "which", lambda _name: "node")
    calls = []

    def unpack(_node, output):
        unit = output / extract_2b.UNIT
        unit.mkdir(parents=True)
        for name in extract_2b.REQUIRED:
            (unit / name).write_bytes(archive.read_bytes())
        calls.append(output)

    monkeypatch.setattr(extract_2b, "_unpack", unpack)
    assert extract_2b.main() == 0
    assert bm.require_templates(directory) == directory
    assert extract_2b.main() == 0 and len(calls) == 1

    archive.write_bytes(b"changed archive")
    assert not extract_2b.ready()
    with pytest.raises(SystemExit, match="cache is stale"):
        bm.require_templates(directory)
    assert extract_2b.main() == 0 and len(calls) == 2
    assert (directory / "2b.model").read_bytes() == b"changed archive"

    (directory / "base_df.texture").write_bytes(b"edited payload")
    assert not extract_2b.ready()
    assert extract_2b.main() == 0 and len(calls) == 3
    assert (directory / "base_df.texture").read_bytes() == b"changed archive"


def test_incomplete_extraction_does_not_replace_a_cache(tmp_path):
    archive = tmp_path / "archive"
    archive.write_bytes(b"input")
    cache = tmp_path / "cache"
    archive_cache.refresh(archive, cache, lambda p: (p / "model").write_bytes(b"old"), ["model"])
    assert archive_cache.current(archive, cache)
    archive.write_bytes(b"input changed")
    with pytest.raises(ValueError, match="did not contain: model"):
        archive_cache.refresh(archive, cache, lambda p: (p / "unrelated").touch(), ["model"])
    assert (cache / "model").read_bytes() == b"old"
    assert not archive_cache.current(archive, cache)


def test_head_cache_replaces_stale_flattened_textures_and_removed_members(tmp_path, monkeypatch):
    monkeypatch.setattr(heads, "ROOT", tmp_path)
    refs = tmp_path / "references"
    refs.mkdir()
    archive = refs / "PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip"
    cache = tmp_path / "cache"
    dae = "Miranda Lawson (Romance) - Adjusted Version.dae"
    prefix = "Miranda Lawson (Romance)/"

    def source(color, old=False):
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(prefix + dae, b"model")
            z.writestr(prefix + "diffuse.png", color)
            if old:
                z.writestr(prefix + "old.png", b"removed")

    source(b"blue", old=True)
    assert heads.ensure_me2_extracted(cache) == cache
    assert (cache / "diffuse.png").read_bytes() == b"blue"
    assert (cache / "old.png").is_file()
    (cache / "diffuse.png").write_bytes(b"stale")
    heads.ensure_me2_extracted(cache)
    assert (cache / "diffuse.png").read_bytes() == b"blue"
    source(b"red")
    heads.ensure_me2_extracted(cache)
    assert (cache / "diffuse.png").read_bytes() == b"red"
    assert not (cache / "old.png").exists()
