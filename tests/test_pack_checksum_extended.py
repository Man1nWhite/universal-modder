"""Extended tests for tools/pd2-las/pack_checksum.py improvements."""
import pytest
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

from pack_checksum import distribution_zips, sha256_file, sidecar_path, verify_checksum, read_checksum, write_checksum


def test_sha256_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello world")
    digest = sha256_file(f)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    # Deterministic
    assert sha256_file(f) == digest
    # Different content different digest
    f2 = tmp_path / "test2.txt"
    f2.write_bytes(b"different")
    assert sha256_file(f2) != digest


def test_sidecar_path():
    p = Path("/a/b/c.zip")
    assert sidecar_path(p) == Path("/a/b/c.zip.sha256")
    assert sidecar_path(Path("foo.zip")) == Path("foo.zip.sha256")


def test_read_checksum_handles_crlf(tmp_path):
    pack = tmp_path / "outfit.zip"
    pack.write_bytes(b"pack")
    digest = sha256_file(pack)
    sidecar_path(pack).write_text(f"{digest}  outfit.zip\r\n", encoding="utf-8")
    assert read_checksum(pack, tmp_path, portable=True) == digest


def test_read_checksum_handles_whitespace(tmp_path):
    pack = tmp_path / "outfit.zip"
    pack.write_bytes(b"pack")
    digest = sha256_file(pack)
    sidecar_path(pack).write_text(f"{digest}  outfit.zip \n", encoding="utf-8")
    # Should handle trailing whitespace gracefully
    assert read_checksum(pack, tmp_path, portable=True) == digest.lower()


def test_read_checksum_rejects_multiline(tmp_path):
    pack = tmp_path / "outfit.zip"
    pack.write_bytes(b"pack")
    digest = sha256_file(pack)
    sidecar_path(pack).write_text(f"{digest}  outfit.zip\nextra line\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected one"):
        read_checksum(pack, tmp_path, portable=True)


def test_read_checksum_case_insensitive(tmp_path):
    pack = tmp_path / "outfit.zip"
    pack.write_bytes(b"pack")
    digest = sha256_file(pack).upper()
    sidecar_path(pack).write_text(f"{digest}  outfit.zip\n", encoding="utf-8")
    # Should accept uppercase and return lowercase
    result = read_checksum(pack, tmp_path, portable=True)
    assert result == digest.lower()
    assert result.islower()


def test_read_checksum_portable_vs_relative(tmp_path):
    dist = tmp_path / "dist" / "char"
    dist.mkdir(parents=True)
    pack = dist / "outfit.zip"
    pack.write_bytes(b"pack")
    digest = sha256_file(pack)
    # Relative path sidecar should work
    sidecar_path(pack).write_text(f"{digest}  dist/char/outfit.zip\n")
    assert verify_checksum(pack, tmp_path) == digest
    # Portable (basename only) should also work with portable=True
    sidecar_path(pack).write_text(f"{digest}  outfit.zip\n")
    assert verify_checksum(pack, tmp_path, portable=True) == digest
    # But basename-only should fail without portable flag when relative expected
    with pytest.raises(ValueError, match="does not name"):
        verify_checksum(pack, tmp_path, portable=False)


def test_distribution_zips_deduplication(tmp_path):
    # Create dist structure
    (tmp_path / "dist" / "Char").mkdir(parents=True)
    p = tmp_path / "dist" / "Char" / "outfit.zip"
    p.write_bytes(b"zip content")
    digest = sha256_file(p)
    sidecar_path(p).write_text(f"{digest}  dist/Char/outfit.zip\n")
    # Pass duplicate recorded entries - should deduplicate
    zips = distribution_zips(tmp_path, recorded=["dist/Char/outfit.zip", "dist/Char/outfit.zip"])
    assert zips == ["dist/Char/outfit.zip"]
    assert len(zips) == 1


def test_distribution_zips_missing_sidecar(tmp_path):
    (tmp_path / "dist" / "Char").mkdir(parents=True)
    p = tmp_path / "dist" / "Char" / "outfit.zip"
    p.write_bytes(b"zip")
    # No sidecar - should raise with detailed message
    with pytest.raises(ValueError, match="missing sidecar or ZIP"):
        distribution_zips(tmp_path)


def test_distribution_zips_orphan_sidecar(tmp_path):
    (tmp_path / "dist" / "Char").mkdir(parents=True)
    p = tmp_path / "dist" / "Char" / "orphan.zip.sha256"
    p.write_text("a" * 64 + "  dist/Char/orphan.zip\n")
    with pytest.raises(ValueError, match="orphan sidecar"):
        distribution_zips(tmp_path)


def test_distribution_zips_no_dist(tmp_path):
    # No dist/ folder at all
    with pytest.raises(ValueError, match="no distribution ZIPs"):
        distribution_zips(tmp_path)


def test_write_checksum_portable(tmp_path):
    pack = tmp_path / "scratch" / "outfit.zip"
    pack.parent.mkdir(parents=True)
    pack.write_bytes(b"hello")
    digest = write_checksum(pack, root=None)
    assert sidecar_path(pack).read_text().endswith("  outfit.zip\n")
    assert verify_checksum(pack, tmp_path, portable=True) == digest


def test_write_checksum_relative(tmp_path):
    dist = tmp_path / "dist" / "Char"
    dist.mkdir(parents=True)
    pack = dist / "outfit.zip"
    pack.write_bytes(b"hello")
    digest = write_checksum(pack, root=tmp_path)
    content = sidecar_path(pack).read_text()
    assert "dist/Char/outfit.zip" in content
    assert verify_checksum(pack, tmp_path) == digest


def test_verify_checksum_mismatch(tmp_path):
    pack = tmp_path / "outfit.zip"
    pack.write_bytes(b"pack content")
    digest = sha256_file(pack)
    sidecar_path(pack).write_text(f"{digest}  outfit.zip\n")
    # Corrupt the pack
    pack.write_bytes(b"different content")
    with pytest.raises(ValueError, match="does not match"):
        verify_checksum(pack, tmp_path, portable=True)


def test_real_dist_packs_still_valid():
    # Ensure our changes don't break real dist/ verification
    from pack_checksum import distribution_zips as dz
    root = Path(__file__).resolve().parents[1]
    if not (root / "dist").exists():
        pytest.skip("no dist/")
    zips = dz(root)
    assert len(zips) > 0
    for rel in zips[:3]:  # Spot check first 3
        verify_checksum(root / rel, root)
