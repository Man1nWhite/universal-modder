"""`tools/pd2-las/fresh_check.py`: what counts as the same pack when another machine builds it.

A fresh build is compared with the tracked pack member by member. Everything has
to be the same bytes except a `.model`, which may differ in the last bits of its
floats and in the sign of the V direction of a vertex the UV map gives no
direction: both depend on the CPU that ran the build (measured on 2026-11-11,
`docs/audits/2026-11-11-miranda-mips-and-object.md`). These tests hold the rule
to exactly that, on copies of the tracked pack with one thing changed.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import diesel_model as dm  # noqa: E402
import fresh_check  # noqa: E402

PACK = REPO / "dist" / "Miranda_LAS.zip"
UNIT = "assets/units/miranda/skins/miranda"
MODEL = f"{UNIT}/miranda.model"

pytestmark = pytest.mark.skipif(
    not PACK.is_file(), reason="the tracked Miranda_LAS.zip is missing; restore it with `git checkout -- dist`")


def changed_pack(target: Path, replace: dict | None = None, drop: tuple = (), add: dict | None = None) -> Path:
    """A copy of the tracked pack with some members replaced, dropped or added."""
    replace = replace or {}
    with zipfile.ZipFile(PACK) as source, zipfile.ZipFile(target, "w") as out:
        for info in source.infolist():
            name = info.filename.split("/", 1)[-1]
            if name not in drop:
                out.writestr(info.filename, replace.get(name, source.read(info)))
        for name, data in (add or {}).items():
            out.writestr(f"{PACK.stem}/{name}", data)
    return target


def with_its_hash(model: bytes) -> dict:
    """The model and a BUILD_INFO.json that records its sha256, as a build would write them."""
    info = json.loads(fresh_check.members(PACK)["BUILD_INFO.json"])
    info["payload_sha256"][MODEL] = hashlib.sha256(model).hexdigest()
    return {MODEL: model, "BUILD_INFO.json": json.dumps(info).encode()}


def edited_model(edit) -> bytes:
    """The tracked third-person model after `edit(geometry, free, bound)` changed its head geometry.

    `free` are the vertices whose triangles all have no area in UV, `bound` the
    ones the UV map does give a direction.
    """
    model = dm.ModelFile.read(fresh_check.members(PACK)[MODEL])
    for section in model.sections:
        if section.type != dm.GEOMETRY:
            continue
        geometry = dm.decode_geometry(section.payload)
        assert dm.encode_geometry(geometry) == section.payload           # the codec gives the bytes back
        free = fresh_check._without_uv_area(model.sections, section.id, geometry["uv0"])
        if free:
            edit(geometry, sorted(free), sorted(set(range(geometry["vert_count"])) - free))
            section.payload = dm.encode_geometry(geometry)
            return model.write()
    raise AssertionError("no geometry of the tracked model has a vertex without UV area")


def next_float(value: float) -> float:
    return float(np.nextafter(np.float32(value), np.float32(np.inf)))


def test_a_pack_is_the_same_as_itself(tmp_path):
    result = fresh_check.compare(PACK, changed_pack(tmp_path / "copy.zip"))
    assert result == {"members": 20, "same": 20, "rounding": [], "different": []}
    names = fresh_check.members(PACK)
    assert MODEL in names and "BUILD_INFO.json" in names             # names are relative to the pack's folder


def test_a_member_that_is_not_a_model_has_to_be_the_same_bytes(tmp_path):
    old = fresh_check.members(PACK)
    eyes, unit_object = f"{UNIT}/miranda_eyes.texture", f"{UNIT}/fps_miranda.object"
    texture = bytearray(old[eyes])
    texture[4000] ^= 1                                               # one bit of one block
    fresh = changed_pack(tmp_path / "fresh.zip", replace={eyes: bytes(texture), unit_object: old[unit_object] + b"\n"},
                         drop=(f"{UNIT}/miranda.unit",), add={"extra.txt": b"x"})
    result = fresh_check.compare(PACK, fresh)
    assert result["rounding"] == []
    text = "\n".join(result["different"])
    assert f"{eyes}: 1 bytes differ of 349,680; has to be the same bytes" in text
    assert f"{unit_object}: 1 bytes differ" in text
    assert f"{UNIT}/miranda.unit: not in the fresh build" in text
    assert "extra.txt: not in the tracked pack" in text
    assert len(result["different"]) == 4 and result["same"] == 17


def test_a_model_may_differ_in_the_last_bits_of_its_floats(tmp_path):
    def nudge(geometry, free, bound):
        for channel in ("verts", "normals", "uvdir_u", "uvdir_v", "blendweights"):
            row = list(geometry[channel][bound[0]])
            row[0] = next_float(row[0])
            geometry[channel][bound[0]] = tuple(row)

    model = edited_model(nudge)
    result = fresh_check.compare(PACK, changed_pack(tmp_path / "fresh.zip", replace=with_its_hash(model)))
    assert result["different"] == [] and result["same"] == 18
    assert len(result["rounding"]) == 2
    assert result["rounding"][0].startswith(f"{MODEL}: ") and "the last bits of floats" in result["rounding"][0]
    assert "reversed" not in result["rounding"][0]
    assert result["rounding"][1] == "BUILD_INFO.json: the sha256 it records for the above"


def test_a_v_direction_may_be_reversed_only_where_the_uv_map_gives_none(tmp_path):
    """44 vertices of the hair have no triangle with area in UV; anywhere else a reversed V is a defect."""
    counts = {}

    def reverse(which):
        def edit(geometry, free, bound):
            counts["free"], counts["bound"] = len(free), len(bound)
            for vertex in {"free": free[:3], "bound": bound[:1]}[which]:
                assert any(geometry["uvdir_v"][vertex])
                geometry["uvdir_v"][vertex] = tuple(-value for value in geometry["uvdir_v"][vertex])
        return edit

    allowed = fresh_check.compare(PACK, changed_pack(tmp_path / "a.zip", replace=with_its_hash(edited_model(reverse("free")))))
    assert counts == {"free": 44, "bound": 4185}
    assert allowed["different"] == []
    assert "3 V directions reversed where the UV map gives none" in allowed["rounding"][0]

    refused = fresh_check.compare(PACK, changed_pack(tmp_path / "b.zip", replace=with_its_hash(edited_model(reverse("bound")))))
    assert refused["rounding"] == [] and len(refused["different"]) == 2
    assert "V direction of vertex" in refused["different"][0] and "more than rounding" in refused["different"][0]
    assert refused["different"][1] == "BUILD_INFO.json: differs in payload_sha256"


def test_a_model_may_not_differ_by_more_than_that(tmp_path):
    def move(geometry, free, bound):                                 # a tenth of a millimetre
        x, y, z = geometry["verts"][bound[0]]
        geometry["verts"][bound[0]] = (x + 0.01, y, z)

    def reweight(geometry, free, bound):                             # another bone
        geometry["blendindices"][bound[0]] = tuple(index + 1 for index in geometry["blendindices"][bound[0]])

    for number, edit in enumerate((move, reweight)):
        fresh = changed_pack(tmp_path / f"{number}.zip", replace=with_its_hash(edited_model(edit)))
        different = fresh_check.compare(PACK, fresh)["different"]
        assert len(different) == 2 and "differs by more than rounding" in different[0], different

    # a section without floats: one triangle index
    model = dm.ModelFile.read(fresh_check.members(PACK)[MODEL])
    topology = model.by_type(dm.TOPOLOGY)[0]
    indices = dm.decode_topology(topology.payload)
    indices["indices"][0], indices["indices"][1] = indices["indices"][1], indices["indices"][0]
    topology.payload = dm.encode_topology(indices)
    different = fresh_check.compare(PACK, changed_pack(tmp_path / "t.zip", replace=with_its_hash(model.write())))["different"]
    assert "topology section" in different[0] and "holds no floats and differs" in different[0]

    # not a model at all, and a model with a section missing
    for data, why in ((b"not a model", "does not read as a model"),
                      (dm.ModelFile(model.sections[:-1]).write(), "its sections are not the same list")):
        different = fresh_check.compare(PACK, changed_pack(tmp_path / "x.zip", replace=with_its_hash(data)))["different"]
        assert why in different[0], different


def test_build_info_may_differ_only_in_the_hash_of_a_model_that_differs_as_allowed(tmp_path):
    info = json.loads(fresh_check.members(PACK)["BUILD_INFO.json"])
    info["runtime_verified"] = not info["runtime_verified"]
    result = fresh_check.compare(PACK, changed_pack(tmp_path / "a.zip", replace={"BUILD_INFO.json": json.dumps(info).encode()}))
    assert result["different"] == ["BUILD_INFO.json: differs in runtime_verified"] and result["same"] == 19

    # the hash of a member that did not change, or of a texture, is not excused
    info = json.loads(fresh_check.members(PACK)["BUILD_INFO.json"])
    info["payload_sha256"][f"{UNIT}/miranda_eyes.texture"] = "0" * 64
    result = fresh_check.compare(PACK, changed_pack(tmp_path / "b.zip", replace={"BUILD_INFO.json": json.dumps(info).encode()}))
    assert result["different"] == ["BUILD_INFO.json: differs in payload_sha256"]


def test_the_command_reports_both_packs_and_fails_on_a_difference(tmp_path, capsys):
    tracked, fresh = tmp_path / "tracked", tmp_path / "fresh"
    tracked.mkdir()
    fresh.mkdir()
    assert fresh_check.PACKS == ("Miranda_LAS.zip", "Miranda_Busty_LAS.zip")
    for pack in fresh_check.PACKS:
        shutil.copy(REPO / "dist" / pack, tracked / pack)
    shutil.copy(REPO / "dist" / fresh_check.PACKS[0], fresh / fresh_check.PACKS[0])

    assert fresh_check.main(["--fresh", str(fresh), "--tracked", str(tracked)]) == 1
    out = capsys.readouterr().out
    assert "Miranda_LAS.zip: all 20 members are the same bytes as the tracked pack" in out
    assert "Miranda_Busty_LAS.zip: no fresh build in" in out and "make -sC tools/pd2-las fresh" in out

    shutil.copy(REPO / "dist" / fresh_check.PACKS[1], fresh / fresh_check.PACKS[1])
    assert fresh_check.main(["--fresh", str(fresh), "--tracked", str(tracked)]) == 0
    assert capsys.readouterr().out.count("all 20 members are the same bytes") == 2

    texture = f"{UNIT}/miranda_face_df.texture"
    data = bytearray(fresh_check.members(PACK)[texture])
    data[-1] ^= 0x80
    changed_pack(fresh / fresh_check.PACKS[0], replace={texture: bytes(data)})
    assert fresh_check.main(["--fresh", str(fresh), "--tracked", str(tracked)]) == 1
    out = capsys.readouterr().out
    assert "Miranda_LAS.zip: 19 of 20 members are the same bytes as the tracked pack" in out
    assert f"  DIFFERENT       {texture}: 1 bytes differ of 1,398,256; has to be the same bytes" in out
