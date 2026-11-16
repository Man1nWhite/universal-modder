"""Restore must validate untrusted snapshots and preserve save data."""
from __future__ import annotations

import hashlib
import json
import zipfile

import pytest

from um import backup


def meta(data: bytes) -> dict:
    return {"size": len(data), "sha1": hashlib.sha1(data).hexdigest()}


def snapshot(path, target, files, *, version=None, metadata=None):
    manifest = {"source": str(target), "files": metadata or {name: meta(data) for name, data in files.items()}}
    if version is not None:
        manifest["version"] = version
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(("files/" if version == 2 else "") + name, data)
        z.writestr(backup.MANIFEST, json.dumps(manifest))
    return path


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("UM_HOME", str(tmp_path / "state"))


@pytest.mark.parametrize("bad", ["../outside.txt", "/outside.txt", "nested/../../outside", "C:/outside.txt", "a\\..\\outside", "a//b", "a/./b"])
def test_rejects_unsafe_manifest_paths(tmp_path, bad):
    target = tmp_path / "target"
    target.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("safe")
    zp = snapshot(tmp_path / "bad.zip", target, {bad: b"overwrite"})
    with pytest.raises(SystemExit):
        backup.restore("s", snapshot=str(zp), yes=True)
    assert outside.read_text() == "safe"
    assert not list(target.iterdir())


def test_rejects_symlink_file_and_directory_in_destination(tmp_path):
    target, outside = tmp_path / "target", tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    (outside / "save").write_text("outside")
    zp = snapshot(tmp_path / "good.zip", target, {"dir/save": b"snapshot"})
    try:
        (target / "dir").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(SystemExit):
        backup.restore("s", snapshot=str(zp), yes=True)
    assert (outside / "save").read_text() == "outside"
    (target / "dir").unlink()
    (target / "dir").mkdir()
    (target / "dir" / "save").symlink_to(outside / "save")
    with pytest.raises(SystemExit):
        backup.restore("s", snapshot=str(zp), yes=True)
    assert (outside / "save").read_text() == "outside"


def test_restore_verifies_all_staged_content_before_any_overwrite_or_clean(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "first").write_text("old")
    (target / "extra").write_text("keep")
    data = {"first": b"new", "second": b"wrong"}
    manifest = {"first": meta(b"new"), "second": meta(b"right")}
    zp = snapshot(tmp_path / "corrupt.zip", target, data, version=2, metadata=manifest)
    with pytest.raises(SystemExit):
        backup.restore("s", snapshot=str(zp), clean=True, yes=True)
    assert (target / "first").read_text() == "old"
    assert (target / "extra").read_text() == "keep"
    assert not (target / "second").exists()
    assert sorted(p.name for p in target.iterdir()) == ["extra", "first"]


def test_reserved_manifest_filename_round_trip(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    file = target / backup.MANIFEST
    file.write_text("real save contents")
    zp = backup.create(str(target), "s")
    file.write_text("changed")
    backup.restore("s", snapshot=str(zp), yes=True)
    assert file.read_text() == "real save contents"


def test_relative_source_restores_to_original_location(tmp_path, monkeypatch):
    work, other = tmp_path / "work", tmp_path / "other"
    work.mkdir()
    other.mkdir()
    target = work / "save"
    target.mkdir()
    (target / "file").write_text("snapshot")
    monkeypatch.chdir(work)
    backup.create("save", "s")
    (target / "file").write_text("changed")
    monkeypatch.chdir(other)
    backup.restore("s", yes=True)
    assert (target / "file").read_text() == "snapshot"
    assert not (other / "save").exists()


def test_legacy_snapshot_still_restores(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    zp = snapshot(tmp_path / "legacy.zip", target, {"sub/save": b"legacy"})
    backup.restore("s", snapshot=str(zp), yes=True)
    assert (target / "sub" / "save").read_bytes() == b"legacy"


def test_legacy_relative_source_requires_explicit_destination(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    zp = snapshot(tmp_path / "relative.zip", "save", {"file": b"legacy"})
    with pytest.raises(SystemExit):
        backup.restore("s", snapshot=str(zp), yes=True)
    assert not (tmp_path / "save").exists()
    target = tmp_path / "known-target"
    backup.restore("s", to=str(target), snapshot=str(zp), yes=True)
    assert (target / "file").read_bytes() == b"legacy"


def test_duplicate_manifest_legacy_snapshot_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / backup.MANIFEST).write_text("unchanged")
    zp = tmp_path / "ambiguous.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr(backup.MANIFEST, "original data")
        with pytest.warns(UserWarning, match="Duplicate name"):
            z.writestr(backup.MANIFEST, json.dumps({"source": str(target), "files": {backup.MANIFEST: meta(b"original data")}}))
    with pytest.raises(SystemExit):
        backup.restore("s", snapshot=str(zp), yes=True)
    assert (target / backup.MANIFEST).read_text() == "unchanged"
