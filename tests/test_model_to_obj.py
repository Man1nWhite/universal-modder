"""OBJ export of a tracked pack's ``.model`` — the standard-viewer escape hatch.

`dist/` ships Diesel ``.model`` bytes only, and the repo's own renderers draw the
stored triangles without any guarantee a human can double-check what they are
looking at. This tool converts the tracked ``christie.model`` to an OBJ with the
one in-repo reader (`diesel_model`), so the geometry stage can be opened in any
viewer rather than trusted to the rasteriser.

The tests are against the tracked pack, measured first:

* ``g_body`` (10,373 v / 17,289 t, materials ``mtr_body``, ``mtr_c02_01``,
  ``mtr_c02_02``, ``mtr_c02_05``),
* the shadow caster ``s_body`` (10,369 v / 17,289 t, one material),
* ``g_body_lod1`` shares its geometry with ``g_body``.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import model_to_obj as m2o  # noqa: E402
import diesel_model as dm  # noqa: E402

PACK = REPO / "dist" / "Christie_LAS.zip"
MEMBER = "Christie_LAS/assets/units/christie/skins/christie/christie.model"

pytestmark = __import__("pytest").mark.skipif(not PACK.is_file(), reason="Christie_LAS.zip is not in dist/ in this checkout")


def _drawables() -> dict:
    with zipfile.ZipFile(PACK) as zf:
        return m2o.collect(dm.ModelFile.read(zf.read(MEMBER)))


def test_collect_finds_the_three_drawables():
    # counts are NOT pinned: the worktree dist/ pack (b65fb27e…, from-scratch
    # build) and the tracked pack (1ec1c95a…, sleeve-bridge build) both ship
    # 10,373 v g_body but differ in triangle-record count (17,289 vs 17,309) and
    # s_body vertex count (10,369 vs 10,373). Self-consistency is pinned instead.
    got = _drawables()
    assert set(got) == {"s_body", "g_body_lod1", "g_body"}
    for name, geo in got.items():
        assert len(geo["verts"]) == len(geo["normals"]) == len(geo["uv0"]) == geo["vert_count"]
        assert len(geo["verts"]) > 10000 and len(geo["faces"]) > 17000
        assert len(geo["face_materials"]) == len(geo["faces"])
    assert got["g_body_lod1"]["verts"] == got["g_body"]["verts"]
    assert [len(f) for f in got["g_body"]["faces"]] == [3] * len(got["g_body"]["faces"])
    assert sorted({m for m in got["g_body"]["face_materials"] if m}) == ["mtr_body", "mtr_c02_01", "mtr_c02_02", "mtr_c02_05"]


def test_obj_round_trips_counts_and_references(tmp_path):
    got = _drawables()
    chosen = {"g_body": got["g_body"]}
    obj_path, mtl_path = m2o.export_obj(chosen, tmp_path, "christie", "test source", "0" * 64)
    lines = obj_path.read_text(encoding="utf-8").splitlines()
    nv = len(got["g_body"]["verts"])
    nf = len(got["g_body"]["faces"])
    assert sum(1 for l in lines if l.startswith("v ")) == nv
    assert sum(1 for l in lines if l.startswith("vn ")) == nv
    assert sum(1 for l in lines if l.startswith("vt ")) == nv
    assert sum(1 for l in lines if l.startswith("f ")) == nf
    assert sum(1 for l in lines if l.startswith("usemtl ")) == 4
    assert "mtllib christie.mtl" in lines
    # every 1-based index must reference a written vertex/uv/normal of g_body
    for line in (l for l in lines if l.startswith("f ")):
        for corner in line.split()[1:]:
            v, vt, vn = (int(part) for part in corner.split("/"))
            assert 1 <= v <= nv and 1 <= vt <= nv and 1 <= vn <= nv
    mtl = mtl_path.read_text(encoding="utf-8")
    assert all(name in mtl for name in ("mtr_body", "mtr_c02_01", "mtr_c02_02", "mtr_c02_05"))


def test_render_writes_one_png_per_view(tmp_path):
    got = _drawables()
    combined = {"verts": got["g_body"]["verts"],
                "faces": got["g_body"]["faces"],
                "face_materials": got["g_body"]["face_materials"]}
    palette = {m: (200, 160, 120) for m in set(got["g_body"]["face_materials"]) if m}
    for view in ("front", "side", "iso"):
        out = tmp_path / f"christie_model-bridge_obj_{view}.png"
        m2o.render_view(combined, view, out, palette)
        assert out.is_file() and out.stat().st_size > 10_000


def test_cli_exports_the_tracked_pack_by_default(tmp_path):
    rc = m2o.main(["--out-dir", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "christie.obj").is_file()
    assert (tmp_path / "christie.mtl").is_file()
