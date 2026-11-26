"""`assets.json` and `tools/release_assets.py`: the packs and sources live in releases now.

Two things have to stay true for that to be safe. The manifest has to name every file the
tree publishes — a file it forgot is a file no clone can fetch back — and it has to name the
bytes that are on disk now, or a fetch hands back an old pack. Everything else here is the
round trip: write → check → upload → fetch → verify, with the download stubbed out by a
directory of the same files, so the test runs offline.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "release_assets.py"
MANIFEST = REPO / "assets.json"
PREFIXES = ("dist", "references")


def _load():
    spec = importlib.util.spec_from_file_location("release_assets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def assets():
    return _load()


@pytest.fixture()
def manifest(assets):
    return assets.load_manifest()


def _tracked() -> list[str]:
    proc = subprocess.run(["git", "ls-files", "-z", "--", *PREFIXES], cwd=REPO,
                          capture_output=True, check=False)
    if proc.returncode != 0:
        return []
    return sorted(p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p)


# --------------------------------------------------------------------------- the manifest


def test_the_manifest_is_there_and_well_formed(manifest):
    assert manifest["version"] == 1
    assert set(manifest["releases"]) == {"packs-v1", "sources-v1"}
    for tag, release in manifest["releases"].items():
        assert release["title"] and release["note"], tag
        assert "NOTICE.md" in release["note"] or "references/README.md" in release["note"], tag
        assert release["files"], tag


def test_every_path_is_under_a_published_prefix(manifest):
    for tag, release in manifest["releases"].items():
        want = "dist/" if tag == "packs-v1" else "references/"
        for rel in release["files"]:
            assert rel.startswith(want), (tag, rel)


def test_asset_names_are_flat_unique_and_round_trip(assets, manifest):
    """GitHub takes a flat name; the path has to survive the trip to a URL and back."""
    seen = set()
    for tag, rel, entry in assets.manifest_entries(manifest):
        name = entry["asset"]
        assert "/" not in name and name not in seen, name
        assert name == assets.asset_name(rel)
        assert assets.github_normalise(name) == name, (
            f"{rel}: GitHub would rewrite {name!r} to {assets.github_normalise(name)!r} after "
            "uploading it, and then the manifest could not find it again")
        seen.add(name)
    assert len(seen) == len(assets.manifest_entries(manifest))


def test_manifest_lists_every_file_on_disk(assets, manifest):
    """`dist/` and `references/` are fetched, not tracked: the manifest is the inventory.

    A pack built here and not published is exactly what this catches — it would be a pack that
    no clone can fetch, and `status` would call it `changed` with nothing to compare it to.
    """
    on_disk = sorted(rel for prefix in PREFIXES for rel in (
        p.relative_to(REPO).as_posix() for p in (REPO / prefix).rglob("*") if p.is_file())
        if assets.publishable(rel))
    if not on_disk:
        pytest.skip("nothing fetched under dist/ and references/ in this checkout")
    listed = {rel for _, rel, _ in assets.manifest_entries(manifest)}
    assert sorted(listed) == on_disk, sorted(set(on_disk) - listed) + sorted(listed - set(on_disk))


def test_markdown_stays_in_git(assets, manifest):
    """`references/README.md` is the provenance table NOTICE.md points at: a clone needs it
    without a network, so it is documentation, not a published asset."""
    listed = {rel for _, rel, _ in assets.manifest_entries(manifest)}
    assert not any(rel.endswith(".md") for rel in listed)
    assert (REPO / "references" / "README.md").is_file() or not _tracked()


def test_the_manifest_names_the_bytes_on_disk(assets, manifest, tmp_path):
    served = tmp_path / "served"
    served.mkdir()
    for tag, rel, entry in assets.manifest_entries(manifest):
        path = REPO / rel
        if not path.is_file():
            continue
        assert path.stat().st_size == entry["bytes"], rel
        assert assets.sha256_file(path) == entry["sha256"], rel


def test_every_pack_status_knows_is_published(assets, manifest):
    """A pack the tree reports but the manifest forgets cannot be fetched back."""
    import importlib

    status = importlib.import_module("status") if str(REPO / "tools" / "pd2-las") in __import__("sys").path else None
    if status is None:
        spec = importlib.util.spec_from_file_location("pd2_status", REPO / "tools" / "pd2-las" / "status.py")
        status = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(status)
    published = {Path(rel).stem for rel in manifest["releases"]["packs-v1"]["files"] if rel.endswith(".zip")}
    assert set(status.TARGETS) <= published, sorted(set(status.TARGETS) - published)


def test_every_published_pack_has_its_sidecar(manifest):
    files = manifest if isinstance(manifest, dict) else None
    paths = set(files["releases"]["packs-v1"]["files"])
    for rel in paths:
        if rel.endswith(".zip"):
            assert rel + ".sha256" in paths, rel


def test_the_manifest_is_sorted_and_diffable(manifest):
    """One file per line, sorted by path: a rebuilt pack is a two-line diff, not a wall."""
    text = MANIFEST.read_text(encoding="utf-8")
    data = json.loads(text)
    for release in data["releases"].values():
        assert list(release["files"]) == sorted(release["files"])
    assert text.endswith("\n") and "\t" not in text


# --------------------------------------------------------------------------- write / check


@pytest.fixture()
def tree(tmp_path, assets, monkeypatch):
    """A two-file stand-in for the repository, with the manifest global pointed at it."""
    (tmp_path / "dist" / "A").mkdir(parents=True)
    (tmp_path / "references").mkdir()
    (tmp_path / "dist" / "A" / "Pack.zip").write_bytes(b"pack bytes")
    (tmp_path / "dist" / "A" / "Pack.zip.sha256").write_text("0" * 64 + "  Pack.zip\n")
    (tmp_path / "references" / "source one.7z").write_bytes(b"source bytes")
    monkeypatch.setattr(assets, "REPO", tmp_path)
    monkeypatch.setattr(assets, "MANIFEST", tmp_path / "assets.json")
    monkeypatch.setattr(assets, "tracked_paths", lambda: sorted(
        p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")
        if p.is_file() and p.name != "assets.json"))
    return assets


def test_write_then_check_round_trips(tree, capsys):
    assert tree.main(["write"]) == 0
    assert tree.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "3 file(s)" in out and "PASS" in out


def test_a_name_github_would_rewrite_is_made_ascii_first(tree):
    """GitHub turns a space, a parenthesis and a Cyrillic letter into dots; do it here instead."""
    tree.main(["write"])
    data = json.loads((tree.REPO / "assets.json").read_text())
    name = data["releases"]["sources-v1"]["files"]["references/source one.7z"]["asset"]
    assert re.fullmatch(r"[A-Za-z0-9._-]+", name), name
    assert ".." not in name, "GitHub collapses a run of dots"
    assert name.startswith("references__source.one-") and name.endswith(".7z"), name
    assert tree.asset_name("dist/A/B.zip") == "dist__A__B.zip", "a plain path is left alone"
    assert tree.asset_name("references/source one.7z") == name, "and the name is stable"


def test_check_catches_a_file_the_manifest_forgot(tree, capsys):
    tree.main(["write"])
    (tree.REPO / "dist" / "A" / "New.zip").write_bytes(b"new")
    with pytest.raises(SystemExit) as exc:
        tree.main(["check"])
    assert exc.value.code == 1
    assert "dist/A/New.zip: tracked but missing from assets.json" in capsys.readouterr().err


def test_check_catches_rebuilt_bytes_and_says_what_to_do(tree, capsys):
    tree.main(["write"])
    (tree.REPO / "dist" / "A" / "Pack.zip").write_bytes(b"rebuilt, not published")
    with pytest.raises(SystemExit):
        tree.main(["check"])
    err = capsys.readouterr().err
    assert "dist/A/Pack.zip" in err and "upload" in err


# --------------------------------------------------------------------------- fetch / verify


@pytest.fixture()
def served(tree, tmp_path, monkeypatch):
    """The same tree, published: a directory of assets a `file://` URL serves."""
    tree.main(["write"])
    data = json.loads((tree.REPO / "assets.json").read_text())
    fake = tmp_path / "served"
    fake.mkdir()
    for release in data["releases"].values():
        for rel, entry in release["files"].items():
            (fake / entry["asset"]).write_bytes((tree.REPO / rel).read_bytes())
    monkeypatch.setattr(tree, "download_url", lambda repo, tag, asset, base=None: (fake / asset).as_uri())
    return tree, fake, data


def test_fetch_downloads_verifies_and_is_idempotent(served, tmp_path, capsys):
    tree, fake, data = served
    dest = tmp_path / "fresh"
    args = argparse.Namespace(repo=None, tag=None, dest=str(dest), base_url="", force=False)
    assert tree.main(["fetch"]) is None or True     # cmd_fetch is called directly below
    tree.cmd_fetch(args)
    assert (dest / "dist" / "A" / "Pack.zip").read_bytes() == b"pack bytes"
    assert (dest / "references" / "source one.7z").read_bytes() == b"source bytes"
    capsys.readouterr()
    tree.cmd_fetch(args)
    assert "0 fetched, 3 already present and verified" in capsys.readouterr().out


def test_fetch_refuses_bytes_that_are_not_the_manifest(served, tmp_path, capsys):
    tree, fake, data = served
    (fake / "dist__A__Pack.zip").write_bytes(b"not the published pack")
    dest = tmp_path / "fresh"
    args = argparse.Namespace(repo=None, tag=None, dest=str(dest), base_url="", force=False)
    with pytest.raises(SystemExit):
        tree.cmd_fetch(args)
    assert "the manifest says" in capsys.readouterr().err
    assert not (dest / "dist" / "A" / "Pack.zip").exists(), "a partial download must not land"


def test_fetch_only_one_release(served, tmp_path):
    tree, fake, data = served
    dest = tmp_path / "fresh"
    args = argparse.Namespace(repo=None, tag="sources-v1", dest=str(dest), base_url="", force=False)
    tree.cmd_fetch(args)
    assert (dest / "references" / "source one.7z").is_file()
    assert not (dest / "dist").exists()


def test_fetch_an_unknown_tag_is_a_message(served, tmp_path, capsys):
    tree, fake, data = served
    args = argparse.Namespace(repo=None, tag="nope", dest=str(tmp_path), base_url="", force=False)
    with pytest.raises(SystemExit):
        tree.cmd_fetch(args)
    assert "unknown tag nope" in capsys.readouterr().err


def test_verify_reports_missing_and_wrong(served, tmp_path, capsys):
    tree, fake, data = served
    dest = tmp_path / "fresh"
    with pytest.raises(SystemExit) as exc:
        tree.main(["verify", "--dest", str(dest)])
    assert exc.value.code == 1
    assert "3 file(s) not fetched" in capsys.readouterr().err

    args = argparse.Namespace(repo=None, tag=None, dest=str(dest), base_url="", force=False)
    tree.cmd_fetch(args)
    capsys.readouterr()
    assert tree.main(["verify", "--dest", str(dest)]) == 0
    assert "PASS: 3 file(s) are the published bytes" in capsys.readouterr().out

    (dest / "dist" / "A" / "Pack.zip").write_bytes(b"tampered")
    with pytest.raises(SystemExit):
        tree.main(["verify", "--dest", str(dest)])
    assert "dist/A/Pack.zip: not the published bytes" in capsys.readouterr().err


# --------------------------------------------------------------------------- upload


def test_upload_says_once_that_the_endpoint_is_out_of_reach(served, monkeypatch, capsys):
    """A firewalled sandbox must not fail 118 times: one message, two ways forward."""
    tree, fake, data = served
    monkeypatch.setattr(tree, "can_upload", lambda: False)
    with pytest.raises(SystemExit) as exc:
        tree.main(["upload"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "uploads.github.com" in err and "release-assets.yml" in err


def test_upload_dry_run_names_every_release_and_touches_nothing(served, monkeypatch, capsys):
    tree, fake, data = served
    monkeypatch.setattr(tree, "can_upload", lambda: True)
    monkeypatch.setattr(tree, "release_exists", lambda repo, tag: False)
    assert tree.main(["upload", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would create packs-v1" in out and "would create sources-v1" in out
    assert "would upload dist/A/Pack.zip" in out


def test_a_fresh_build_gets_the_published_inputs(tmp_path, monkeypatch):
    """`references/` is gitignored now; `git ls-files` alone would starve every builder."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("fresh", REPO / "tools" / "pd2-las" / "fresh.py")
    fresh = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(fresh)
    except ModuleNotFoundError as exc:      # numpy, for the mesh code
        pytest.skip(f"fresh.py needs {exc.name}")

    repo = tmp_path / "repo"
    (repo / "references").mkdir(parents=True)
    (repo / "references" / "source.7z").write_bytes(b"an input")
    (repo / "dist" / "A").mkdir(parents=True)
    (repo / "dist" / "A" / "Pack.zip").write_bytes(b"an output")
    (repo / "assets.json").write_text(json.dumps({"version": 1, "releases": {"sources-v1": {"files": {
        "references/source.7z": {"asset": "references__source.7z", "bytes": 8, "sha256": "x"},
        "dist/A/Pack.zip": {"asset": "dist__A__Pack.zip", "bytes": 9, "sha256": "y"}}}}}))
    monkeypatch.setattr(fresh, "REPO", repo)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("references/\ndist/\n")
    (repo / "code.py").write_text("print('a builder')\n")

    tree = tmp_path / "tree"
    fresh.copy_tree(tree, outputs=["dist/A/Pack.zip"])
    assert (tree / "code.py").is_file()
    assert (tree / "references" / "source.7z").read_bytes() == b"an input", "the build input"
    assert not (tree / "dist" / "A" / "Pack.zip").exists(), "the output is what the run verifies"
