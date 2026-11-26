"""The tracked Arivus head interchange pack: checksum, members and provenance.

D74 lets game-derived exports into Git. This is the first shipped one: a
reproducible ZIP built from the tracked `Arivus_over_Hoxton.zip`, with a
`.sha256`, a make target and a builder, not loose scratch files under `build/`.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
from dist_paths import dist_path  # noqa: E402
from pack_checksum import verify_checksum  # noqa: E402
from status import target as make_target  # noqa: E402

PACK = dist_path(ROOT, "Arivus_Head_over_Old_Hoxton_GLB.zip")
SOURCE = dist_path(ROOT, "Arivus_over_Hoxton.zip")
INTERNAL = "Arivus Head GLB/"
GLB = "arivus_head_over_old_hoxton.glb"
DDS = ("old_hoxton.dds", "old_hoxton_head_df.dds", "old_hoxton_head_nm.dds",
       "old_hoxton_head_p_df.dds", "old_hoxton_head_p_nm.dds")


def _glb_json(data: bytes) -> dict:
    magic, version, length = struct.unpack_from("<4sII", data)
    assert magic == b"glTF" and version == 2 and length == len(data)
    chunk_len, chunk_type = struct.unpack_from("<I4s", data, 12)
    assert chunk_type == b"JSON"
    doc = json.loads(data[20:20 + chunk_len])
    assert doc["buffers"][0]["byteLength"] <= struct.unpack_from("<I4s", data, 20 + chunk_len)[0]
    return doc


def test_pack_is_paired_and_has_a_builder():
    assert PACK.is_file() and SOURCE.is_file()
    assert verify_checksum(PACK, ROOT) == hashlib.sha256(PACK.read_bytes()).hexdigest()
    assert make_target(PACK.stem) == "glb"
    assert (ROOT / "tools/pd2-las/build_arivus_glb_pack.py").is_file()
    assert "\nglb:" in (ROOT / "tools/pd2-las/Makefile").read_text()


def test_members_are_the_head_export_and_nothing_else():
    with zipfile.ZipFile(PACK) as z:
        names = z.namelist()
    assert names == [INTERNAL + name for name in sorted(
        (GLB, *DDS, "README.txt", "manifest.json"))]
    assert all(name.startswith(INTERNAL) for name in names)


def test_dds_are_the_source_packs_texture_bytes():
    def dds_slice(raw: bytes) -> bytes:
        return raw if raw.startswith(b"DDS ") else raw[raw.find(b"DDS "):]

    with zipfile.ZipFile(PACK) as pack, zipfile.ZipFile(SOURCE) as source:
        textures = {Path(name).stem: source.read(name)
                    for name in source.namelist() if name.endswith(".texture")}
        assert len(textures) == len(DDS)
        for name in DDS:
            assert pack.read(INTERNAL + name) == dds_slice(textures[Path(name).stem])


def test_glb_is_a_valid_bind_pose_head_export():
    with zipfile.ZipFile(PACK) as z:
        doc = _glb_json(z.read(INTERNAL + GLB))
    assert doc["scenes"][0]["name"] == Path(GLB).stem
    assert [mesh["name"] for mesh in doc["meshes"]] == ["g_head_old_hoxton"]
    assert doc["materials"][0]["alphaMode"] == "MASK"
    assert len(doc["skins"][0]["joints"]) == 4
    assert len(doc["images"]) >= 2
    assert doc["extras"]["pd2_model"].endswith("npc_criminals_suit_1.model")


def test_manifest_pins_every_member_to_its_digest():
    with zipfile.ZipFile(PACK) as z:
        manifest = json.loads(z.read(INTERNAL + "manifest.json"))
        members = {name.removeprefix(INTERNAL): z.read(name) for name in z.namelist()}
    assert manifest["runtime_verified"] is False
    assert manifest["drawable"] == "g_head_old_hoxton"
    assert manifest["source_pack"] == SOURCE.relative_to(ROOT).as_posix()
    assert set(manifest["files"]) == {GLB, *DDS}
    for name, info in manifest["files"].items():
        assert info["bytes"] == len(members[name])
        assert info["sha256"] == hashlib.sha256(members[name]).hexdigest()
