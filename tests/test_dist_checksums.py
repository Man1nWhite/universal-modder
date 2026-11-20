"""Distribution pairs must match both the path and the bytes in their sidecars."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "dist"
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

from pack_checksum import distribution_zips, sha256_file, sidecar_path, verify_checksum, write_pack_checksum  # noqa: E402


def test_every_dist_zip_is_paired_and_every_sidecar_names_a_zip():
    assert distribution_zips(REPO)


@pytest.mark.parametrize("pack", sorted(DIST.rglob("*.zip")), ids=lambda p: p.name)
def test_published_zip_matches_its_checksum(pack):
    assert pack.stat().st_size > 1024, f"{pack.name} is not a real pack"
    verify_checksum(pack, REPO)


@pytest.mark.parametrize("name", ["wrong/folder/outfit.zip", "outfit.zip", "../outfit.zip"])
def test_distribution_checksum_does_not_fall_back_to_the_basename(tmp_path, name):
    pack = tmp_path / "dist" / "character" / "outfit.zip"
    pack.parent.mkdir(parents=True)
    pack.write_bytes(b"pack")
    sidecar_path(pack).write_text(f"{sha256_file(pack)}  {name}\n")
    with pytest.raises(ValueError, match="does not name"):
        verify_checksum(pack, tmp_path)


@pytest.mark.parametrize("content", ["", "not a digest", "0" * 64 + "  outfit.zip\nextra\n"])
def test_malformed_adjacent_sidecar_is_not_accepted(tmp_path, content):
    pack = tmp_path / "outfit.zip"
    pack.write_bytes(b"pack")
    sidecar_path(pack).write_text(content)
    with pytest.raises(ValueError, match="expected one"):
        verify_checksum(pack, tmp_path, portable=True)


def test_custom_pack_checksum_is_portable_but_distribution_checksum_is_relative(tmp_path):
    scratch = tmp_path / "scratch" / "outfit.zip"
    dist = tmp_path / "dist" / "character" / scratch.name
    for pack in (scratch, dist):
        pack.parent.mkdir(parents=True)
        pack.write_bytes(b"pack")
        write_pack_checksum(pack, tmp_path)
    assert sidecar_path(dist).read_text().endswith("  dist/character/outfit.zip\n")
    verify_checksum(dist, tmp_path)
    dest = tmp_path / "downloads"
    dest.mkdir()
    moved = scratch.rename(dest / scratch.name)
    sidecar_path(scratch).rename(sidecar_path(moved))
    assert sidecar_path(moved).read_text().endswith("  outfit.zip\n")
    verify_checksum(moved, tmp_path / "unrelated", portable=True)
