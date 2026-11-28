"""Managed extraction caches are derived inputs, not sources of truth."""
from __future__ import annotations

import hashlib
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


def test_a_tracked_template_that_is_not_the_archives_bytes_is_refused(tmp_path, monkeypatch):
    """The two 2B models are tracked (D92); a checkout whose copy was edited is not trusted.

    `require_templates` used to fight a stale extraction cache. There is no extraction any
    more, so what it guards is the tracked file itself: a byte that is not the archive's
    model is a repair, not a template, and `extract_2b --check` says so.
    """
    templates = tmp_path / "2b"
    templates.mkdir()
    for name in extract_2b.TEMPLATE_FILES:
        (templates / name).write_bytes(b"model")
    monkeypatch.setattr(extract_2b, "TEMPLATES", templates)
    monkeypatch.setattr(extract_2b, "SHA256", {name: hashlib.sha256(b"model").hexdigest()
                                               for name in extract_2b.TEMPLATE_FILES})
    assert extract_2b.ready(templates)
    assert bm.require_templates(templates) == templates

    (templates / "2b.model").write_bytes(b"edited payload")
    assert not extract_2b.ready(templates)
    assert "2b.model" in extract_2b.describe(templates)
    with pytest.raises(SystemExit, match="not the archive's bytes"):
        bm.require_templates(templates)
    assert extract_2b.main(["--check"]) == 1     # the default path is still the tracked one


def test_the_tracked_models_are_what_the_archive_holds():
    """The tracked 2b.model / fps_2b.model hash to the values extract_2b records for them."""
    if not extract_2b.RAR.is_file():
        pytest.skip("the 2B reference archive is not in this checkout")
    assert extract_2b.ready(), extract_2b.describe()
    for name, digest in extract_2b.SHA256.items():
        assert extract_2b.sha256_file(extract_2b.TEMPLATES / name) == digest, name


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
    refs = tmp_path / "references" / "characters"
    refs.mkdir(parents=True)
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
