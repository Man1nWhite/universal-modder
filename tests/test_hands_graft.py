"""Tests for the grafted PD2 hands and the collar/palette helpers.

The graft has one property worth pinning above all others: it must not move
anything. Both models sit on the stock heister skeleton in its bind pose, so
the donor's vertices have to come across verbatim — a fit would only add error.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b")
needs_templates = pytest.mark.skipif(
    not TEMPLATES.exists(), reason="extracted 2B templates at /tmp/2bsrc not present"
)


# ------------------------------------------------------------------- unit


def test_lower_collar_only_touches_the_collar():
    g = bm.Group(name="g")
    g.verts = [(0.0, 0.0, 150.0), (0.0, 0.0, 158.0), (0.0, 0.0, 168.0)]
    g.slices = [("jacket", 0, 0, 1, 3)]

    touched = bm.lower_collar(g, z0=158.0, k=0.35)

    assert touched == 1                       # only the vertex above the line
    assert g.verts[0][2] == 150.0
    assert g.verts[1][2] == 158.0             # continuous at the boundary
    assert g.verts[2][2] == pytest.approx(158.0 + (168.0 - 158.0) * 0.35)
    assert all(v[0] == 0.0 and v[1] == 0.0 for v in g.verts)


def test_lower_collar_ignores_other_slices():
    g = bm.Group(name="g")
    g.verts = [(0.0, 0.0, 170.0)]
    g.slices = [("skin", 0, 0, 1, 1)]

    assert bm.lower_collar(g) == 0
    assert g.verts[0][2] == 170.0


def test_append_group_reindexes_both_palettes():
    template = bm.Template(
        mf=None, names={}, id_name={}, id_obj={}, worlds={}, name_id={},
        hips_id=0, hips_world=None, drawables={}, drawable_skin={},
    )
    base = bm.Group(name="body")
    base.verts = [(0.0, 0.0, 0.0)]
    base.normals = [(0.0, 0.0, 1.0)]
    base.uvs = [(0.0, 0.0)]
    base.weights = [[(0, 1.0)]]
    base.palette = ["Hips"]
    base.faces = []
    base.slices = [("skin", 0, 0, 0, 1)]
    base.mat_slots = ["mtr_body"]

    extra = bm.Group(name="hands")
    extra.verts = [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    extra.normals = [(0.0, 0.0, 1.0)] * 2
    extra.uvs = [(0.0, 0.0)] * 2
    extra.weights = [[(0, 0.6)], [(0, 0.4)]]
    extra.palette = ["LeftHand"]
    extra.faces = [(0, 1, 0)]
    extra.slices = [("hands", 0, 0, 1, 2)]
    extra.mat_slots = ["mtr_hands"]

    bm.append_group(base, extra, template)

    assert len(base.verts) == 3
    assert base.faces == [(1, 2, 1)]          # offset by the base vertex count
    assert base.slices[-1] == ("hands", 1, 0, 1, 2)
    assert base.mat_slots == ["mtr_body", "mtr_hands"]
    assert set(base.palette) == {"Hips", "LeftHand"}
    # every weight must still index a real palette entry
    for infl in base.weights:
        for idx, w in infl:
            assert 0 <= idx < len(base.palette)
            assert 0.0 < w <= 1.0


# ------------------------------------------------------------ integration


@needs_templates
def test_graft_brings_both_hands_without_moving_them():
    donor = TEMPLATES / "2b.model"
    g = bm.graft_pd2_hands(donor)

    assert len(g.faces) > 1000
    assert len(g.verts) > 1000
    assert all(s == "mtr_hands" for s in g.mat_slots)
    # fingers, not just the palm
    assert sum(1 for n in g.palette if "Hand" in n) == 32

    xs = [v[0] for v in g.verts]
    assert min(xs) < -40.0 and max(xs) > 40.0      # a hand on each side

    # weights are normalised and every index is in range
    for infl in g.weights:
        assert abs(sum(w for _, w in infl) - 1.0) < 1e-5
        for idx, _ in infl:
            assert 0 <= idx < len(g.palette)

    # the donor's own vertices, untouched: no fit, no rescale
    import diesel_model as dm

    mf = dm.ModelFile.read_path(donor)
    positions = set()
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if not md.get("atoms"):
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        try:
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        except ValueError:
            continue
        for v in geo["verts"]:
            positions.add(tuple(round(c, 4) for c in v))
    for v in g.verts:
        assert tuple(round(c, 4) for c in v) in positions
