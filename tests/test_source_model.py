"""The VTX walker, byte-for-byte, without needing a model from any game.

`source_model.load_model` is exercised against real archives elsewhere
(`test_pd2_las.py`, `test_build_models.py`). This file builds the smallest
possible `.vtx` by hand to pin one rule those archives cannot show: a bodypart
may carry several *models* (bodygroups — hats, alternate hair, wear variants),
and the MDL's mesh table only describes the first one, so the VTX walk has to
read the same one. Reading them all is what made such a model fail with
"VTX has N meshes, MDL has M".
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))

import source_model  # noqa: E402


class _Blob:
    """A byte buffer with absolute allocation and struct patching."""

    def __init__(self, header: int = 36):
        self.buf = bytearray(header)

    def alloc(self, size: int) -> int:
        offset = len(self.buf)
        self.buf += b"\x00" * size
        return offset

    def put(self, offset: int, fmt: str, *values) -> None:
        struct.pack_into(f"<{fmt}", self.buf, offset, *values)


def build_vtx(*, models: int = 1, bodyparts: int = 1) -> bytes:
    """A VTX v7 with `models` bodygroup models, each one mesh, one triangle.

    Every vertex of model *i* carries `origMeshVertID` `10 * (i + 1) + n`, so a
    triangle alone says which model it came from.
    """
    blob = _Blob()
    blob.put(0, "i", 7)  # version
    blob.put(16, "i", 0)  # checksum

    bodypart_offs = [blob.alloc(8) for _ in range(bodyparts)]
    blob.put(28, "ii", bodyparts, bodypart_offs[0])

    for bp in bodypart_offs:
        model_offs = [blob.alloc(8) for _ in range(models)]
        blob.put(bp, "ii", models, model_offs[0] - bp)

        for index, mo in enumerate(model_offs):
            lod = blob.alloc(12)
            blob.put(mo, "ii", 1, lod - mo)

            mesh = blob.alloc(9)
            blob.put(lod, "iif", 1, mesh - lod, 0.0)  # one mesh, switch point 0
            group = blob.alloc(25)
            blob.put(mesh, "iiB", 1, group - mesh, 0)  # one strip group

            verts = blob.alloc(3 * 9)
            indices = blob.alloc(3 * 2)
            strip = blob.alloc(27)
            blob.put(
                group,
                "iiiiii",
                3,
                verts - group,
                3,
                indices - group,
                1,
                strip - group,
            )
            for n in range(3):
                base = verts + n * 9
                blob.buf[base : base + 3] = b"\x00\x00\x00"  # bone weights
                blob.buf[base + 3] = 1  # numBones
                struct.pack_into("<H", blob.buf, base + 4, 10 * (index + 1) + n)
                blob.buf[base + 6 : base + 9] = b"\x00\x00\x00"  # bone ids
            struct.pack_into("<3H", blob.buf, indices, 0, 1, 2)
            blob.put(strip, "iiiiHB", 3, 0, 3, 0, 1, 0)  # trilist

    return bytes(blob.buf)


def test_one_model_one_mesh_parses():
    meshes = []
    source_model._read_vtx_meshes(build_vtx(), meshes)
    assert len(meshes) == 1
    assert meshes[0][1] == [(10, 11, 12)]


def test_alternate_bodygroup_models_are_not_walked():
    """A hat is model 1 of the bodypart; the MDL mesh table never mentions it."""
    meshes = []
    source_model._read_vtx_meshes(build_vtx(models=3), meshes)
    assert len(meshes) == 1
    assert meshes[0][1] == [(10, 11, 12)]


def test_every_bodypart_contributes_its_default_model():
    meshes = []
    source_model._read_vtx_meshes(build_vtx(models=2, bodyparts=3), meshes)
    assert len(meshes) == 3
    assert [m[0] for m in meshes] == [0, 1, 2]  # running mesh index
    assert all(tri == [(10, 11, 12)] for _, tri in meshes)


def test_a_vtx_from_another_format_version_is_refused():
    bad = bytearray(build_vtx())
    struct.pack_into("<i", bad, 0, 6)
    with pytest.raises(source_model.SourceModelError, match="unsupported VTX version"):
        source_model._read_vtx_meshes(bytes(bad), [])
