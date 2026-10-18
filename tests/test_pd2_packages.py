"""The asset loader needs the correct install root AND registration of new paths."""
import hashlib
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "pd2_package_metadata", ROOT / "tools/pd2-port/package_metadata.py"
)
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


@pytest.mark.parametrize("character", metadata.CHARACTERS)
def test_shipped_package(character):
    with ZipFile(ROOT / "dist" / f"lawson_{character}.zip") as archive:
        assert archive.testzip() is None
        prefix = f"lawson_{character}/"
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(n.startswith(prefix) for n in names)
        textures = {n[len(prefix):] for n in names if n.endswith(".texture")}
        assert len(textures) == 19
        manifest = ET.fromstring(archive.read(prefix + "main.xml"))
        add = manifest.find("AddFiles")
        assert add is not None
        assert add.attrib == {"directory": ".", "force": "false"}
        registered = {node.attrib["path"] + ".texture" for node in add}
        assert all(node.tag == "texture" for node in add)
        assert len(add) == len(textures)
        assert registered == textures

        # Every custom texture referenced by either material config is registered.
        configs = [n for n in names if n.endswith(".material_config")]
        assert len(configs) == 2
        for name in configs:
            material = ET.fromstring(archive.read(name))
            custom = [node.attrib["file"] for node in material.iter()
                      if node.attrib.get("file", "").startswith(metadata.TEXTURE_DIR + "/")]
            assert custom
            assert all(path + ".texture" in registered for path in custom)
        assert len([n for n in names if n.endswith(".model")]) == 2
        expected = metadata.package_metadata(character, list(textures))
        for name, data in expected.items():
            assert archive.read(prefix + name) == data
        readme = archive.read(prefix + "README.txt").decode()
        assert f"PAYDAY 2\\assets\\mod_overrides\\lawson_{character}\\main.xml" in readme
        assert "BeardLib is REQUIRED" in readme
        assert "NOT been verified" in readme
        assert "BeardLib optional" not in readme


def test_shared_textures_are_identical():
    """force=false is safe only if the three packages supply identical shared maps."""
    packs = []
    for char in metadata.CHARACTERS:
        with ZipFile(ROOT / "dist" / f"lawson_{char}.zip") as archive:
            packs.append({Path(n).name: hashlib.sha256(archive.read(n)).hexdigest()
                          for n in archive.namelist() if n.endswith(".texture")})
    assert packs[0] == packs[1] == packs[2]


def test_repair_preserves_assets_and_is_repeatable(tmp_path):
    archive = tmp_path / "lawson_clover.zip"
    prefix = "lawson_clover/"
    texture = metadata.TEXTURE_DIR + "/test.texture"
    assets = {prefix + texture: b"DDS test", prefix + "units/test.model": b"model bytes"}
    with ZipFile(archive, "w") as z:
        for name, data in assets.items():
            z.writestr(name, data)
        z.writestr(prefix + "README.txt", "wrong old instructions")
    for _ in range(2):
        metadata.repair_archive(archive)
        with ZipFile(archive) as z:
            assert set(z.namelist()) == set(assets) | {prefix + "main.xml", prefix + "README.txt"}
            for name, data in assets.items():
                assert z.read(name) == data
            assert z.read(prefix + "main.xml") == metadata.package_metadata("clover", [texture])["main.xml"]


def test_staged_metadata_matches_archive_metadata(tmp_path):
    texture = tmp_path / metadata.TEXTURE_DIR / "test.texture"
    texture.parent.mkdir(parents=True)
    texture.write_bytes(b"DDS test")
    metadata.write_metadata(tmp_path, "bonnie")
    for name, data in metadata.package_metadata("bonnie", [texture.relative_to(tmp_path).as_posix()]).items():
        assert (tmp_path / name).read_bytes() == data


@pytest.mark.parametrize("paths", [[], ["../bad.texture"], [metadata.TEXTURE_DIR + "/bad.dds"]])
def test_bad_texture_paths_rejected(paths):
    with pytest.raises(ValueError):
        metadata.package_metadata("clover", paths)


def test_wrong_archive_root_left_untouched(tmp_path):
    archive = tmp_path / "lawson_bonnie.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("unexpected/README.txt", "do not change")
    before = archive.read_bytes()
    with pytest.raises(ValueError, match="Unexpected ZIP root"):
        metadata.repair_archive(archive)
    assert archive.read_bytes() == before
    assert list(tmp_path.iterdir()) == [archive]
