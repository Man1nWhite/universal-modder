"""OBJ export of the DOA5 source triple — the *source* end of the pipeline.

`references/Christie.zip` carries the visual studio model the Christie LAS
pack was authored from. `load_model` cannot read it (its VVD LOD0 count,
21,979, is the interleaved whole-body index space, not the MDL's model
numvertices, 18,359), so the tool defaults to `load_all_bodygroups` like every
other Christie tool.

Measured on the tracked archive: 98 bones, 21,979 verts, 22 meshes, 36,920
triangles, 17 materials; the kept body set (cri_body_base, cri_02_01/02/05_base)
is 17,287 triangles over 4 materials. Counts are asserted, because references/
is a tracked, checksummed input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import source_to_obj as s2o  # noqa: E402

SOURCE = REPO / "references" / "Christie.zip"
pytestmark = pytest.mark.skipif(not SOURCE.is_file(), reason="references/Christie.zip is not in this checkout")


@pytest.fixture(scope="module")
def full():
    return s2o.load_source(SOURCE, s2o.MEMBERS[0], s2o.MEMBERS[1], s2o.MEMBERS[2])


def test_load_measures_the_tracked_archive(full):
    model, *_ = full
    assert len(model.bones) == 98
    assert len(model.vertices) == 21979
    assert len(model.meshes) == 22
    assert model.triangle_count == 36920


def test_kept_selection_is_the_four_body_materials(full):
    model, *_ = full
    meshes, materials = s2o.select_meshes(model, True)
    assert materials == list(s2o.KEEP)
    assert sum(len(m.triangle_indices) // 3 for m in meshes) == 17287


def test_obj_round_trips_counts_and_references(full, tmp_path):
    model, mdl_b, vvd_b, vtx_b = full
    shas = {"christie_c2.mdl": "0" * 64, "christie_c2.vvd": "0" * 64, "christie_c2.dx90.vtx": "0" * 64}
    obj_path, mtl_path, stats = s2o.export_obj(model, tmp_path, "christie_source",
                                               "test source", shas, kept=False)
    assert stats["tris"] == 36920
    lines = obj_path.read_text(encoding="utf-8").splitlines()
    nv = 21979
    assert sum(1 for l in lines if l.startswith("v ")) == nv
    assert sum(1 for l in lines if l.startswith("vn ")) == nv
    assert sum(1 for l in lines if l.startswith("vt ")) == nv
    assert sum(1 for l in lines if l.startswith("f ")) == 36920
    for line in (l for l in lines if l.startswith("f ")):
        for corner in line.split()[1:]:
            v, vt, vn = (int(part) for part in corner.split("/"))
            assert 1 <= v <= nv and 1 <= vt <= nv and 1 <= vn <= nv
    mtl = mtl_path.read_text(encoding="utf-8")
    assert all(name in mtl for name in ("cri_body_base", "cri_02_01_base", "cri_hair1_base", "Leye"))


def test_kept_export_excludes_head_materials(full, tmp_path):
    model, *_ = full
    obj_path, mtl_path, stats = s2o.export_obj(model, tmp_path, "christie_source_kept",
                                               "test source", {"christie_c2.mdl": "0" * 64}, kept=True)
    text = obj_path.read_text(encoding="utf-8")
    assert "cri_face_base" not in text and "Leye" not in text and "cri_hair1_base" not in text
    assert stats["tris"] == 17287 and stats["materials"] == list(s2o.KEEP)


def test_render_writes_one_png_per_view(full, tmp_path):
    model, *_ = full
    meshes, materials = s2o.select_meshes(model, False)
    palette = {name: (200, 160, 120) for name in materials}
    for view in ("front", "side", "iso"):
        out = tmp_path / f"christie_mdl-vvd-vtx_obj_{view}.png"
        s2o.render_view(model, meshes, view, out, palette)
        assert out.is_file() and out.stat().st_size > 10_000


def test_cli_kept_export(tmp_path):
    rc = s2o.main(["--kept", "--out-dir", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "christie_source_kept.obj").is_file()
    assert sum(1 for l in (tmp_path / "christie_source_kept.obj").read_text().splitlines()
               if l.startswith("f ")) == 17287
