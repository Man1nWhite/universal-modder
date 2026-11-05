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


def test_trim_neck_folds_only_the_skin_above_the_line():
    g = bm.Group(name="g")
    g.verts = [(0.0, 9.0, 150.0), (0.0, 9.0, 159.0), (0.0, 9.0, 167.0)]
    g.slices = [("skin", 0, 0, 1, 3)]

    touched = bm.trim_neck(g, z0=159.0, k=0.05)

    assert touched == 1                        # only the vertex above the line
    assert g.verts[0][2] == 150.0
    assert g.verts[1][2] == 159.0              # continuous at the boundary
    assert g.verts[2][2] == pytest.approx(159.0 + (167.0 - 159.0) * 0.05)
    # the fold is vertical only: the forward (y) offset is left to the collar
    assert all(v[1] == 9.0 for v in g.verts)


def test_trim_neck_ignores_garment_slices():
    g = bm.Group(name="g")
    g.verts = [(0.0, 0.0, 170.0)]
    g.slices = [("jacket", 0, 0, 1, 1)]

    assert bm.trim_neck(g) == 0
    assert g.verts[0][2] == 170.0


def test_turn_body_is_rigid_and_plants_the_feet():
    import math

    g = bm.Group(name="g")
    # a neck vertex high up, a foot vertex at the ground pivot
    g.verts = [(0.0, 10.0, 160.0), (0.0, 5.0, 0.0)]
    g.normals = [(0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    before = [tuple(v) for v in g.verts]

    n = bm.turn_body(g, deg=0.8)

    assert n == 2
    # rigid: distance between the two verts unchanged
    d0 = math.dist(before[0], before[1])
    d1 = math.dist(g.verts[0], g.verts[1])
    assert d1 == pytest.approx(d0, abs=1e-6)
    # foot at the ground pivot barely moves; neck swings back (-y)
    assert abs(g.verts[1][1] - before[1][1]) < 0.1
    assert g.verts[0][1] < before[0][1]


def test_follow_layer_weights_can_match_only_lateral_shoulder_skin():
    """Skin hidden under the shell follows its shoulder weights; chest does not."""
    g = bm.Group(name="g")
    g.verts = [(20.0, 0.0, 145.0), (20.0, 0.0, 145.0), (5.0, 0.0, 145.0)]
    g.weights = [[(0, 1.0)], [(1, 1.0)], [(1, 1.0)]]
    g.slices = [("jacket", 0, 0, 0, 1), ("skin", 1, 0, 0, 2)]

    touched = bm.follow_layer_weights(g, dst_mats=("skin",), z_lo=136,
                                      z_hi=160, max_dist=6,
                                      x_min=12, x_max=38)

    assert touched == 1
    assert g.weights[1] == [(0, 1.0)]   # covered shoulder skin follows shell
    assert g.weights[2] == [(1, 1.0)]   # exposed centre chest is unchanged


def test_count_hand_verts_flags_only_hand_dominated_verts():
    g = bm.Group(name="g")
    g.palette = ["LeftForeArm", "LeftHand", "LeftHandIndex1"]
    # forearm vert blending a little hand weight (below threshold) -> not counted;
    # two hand/finger-dominated verts -> counted
    g.weights = [[(0, 0.8), (1, 0.2)], [(1, 0.9), (0, 0.1)], [(2, 1.0)]]

    assert bm.count_hand_verts(g) == 2


def test_count_hand_verts_zero_without_hand_bones():
    g = bm.Group(name="g")
    g.palette = ["LeftForeArm", "Spine2"]
    g.weights = [[(0, 1.0)], [(1, 1.0)]]

    assert bm.count_hand_verts(g) == 0


def test_align_neck_recenters_and_tapers_the_neck_column():
    g = bm.Group(name="g")
    # a neck-column vertex (front wall), an outer-shoulder vertex, and one below
    # the blend band
    g.verts = [(0.0, 16.0, 160.0), (20.0, 5.0, 160.0), (0.0, 16.0, 150.0)]
    g.slices = [("skin", 0, 0, 1, 3)]

    touched = bm.align_neck(g)

    assert touched == 1                        # only the in-band neck vertex
    x, y, z = g.verts[0]
    assert x == pytest.approx(0.0)
    assert z == 160.0                          # height untouched
    # tapered to r_seam about the PD2 axis: r_src=6.5 -> 2.1, cy=7.6
    assert y == pytest.approx(7.6 + 6.5 * (2.1 / 6.5))
    assert g.verts[1] == (20.0, 5.0, 160.0)    # radial gate: shoulder untouched
    assert g.verts[2] == (0.0, 16.0, 150.0)    # below z_lo untouched


def test_align_neck_is_continuous_at_the_band_edge():
    g = bm.Group(name="g")
    g.verts = [(0.0, 16.0, 154.0)]
    g.slices = [("skin", 0, 0, 1, 1)]

    assert bm.align_neck(g) == 0               # smoothstep is 0 at z_lo
    assert g.verts[0] == (0.0, 16.0, 154.0)


def test_align_neck_ignores_garment_slices():
    g = bm.Group(name="g")
    g.verts = [(0.0, 16.0, 165.0)]
    g.slices = [("jacket", 0, 0, 1, 1)]

    assert bm.align_neck(g) == 0
    assert g.verts[0] == (0.0, 16.0, 165.0)


def test_restore_bust_scales_only_the_front_chest():
    g = bm.Group(name="g")
    # front bust peak, a back vertex, and a front vertex below the band
    g.verts = [(0.0, 20.0, 138.0), (0.0, 0.0, 138.0), (0.0, 20.0, 110.0)]
    g.slices = [("skin", 0, 0, 1, 3)]

    touched = bm.restore_bust(g, spine_y=5.3, factor=1.32, z_lo=122.0, z_hi=154.0)

    assert touched == 1                        # only the front, in-band vertex
    # z=138 is mid-band (full falloff): protrusion 14.7 scaled by 1.32
    assert g.verts[0][1] == pytest.approx(5.3 + (20.0 - 5.3) * 1.32)
    assert g.verts[0][2] == 138.0              # height unchanged
    assert g.verts[1][1] == 0.0                # back untouched
    assert g.verts[2][1] == 20.0               # below the band untouched


def test_restore_bust_falloff_is_zero_at_the_band_edges():
    g = bm.Group(name="g")
    g.verts = [(0.0, 20.0, 122.0), (0.0, 20.0, 154.0)]
    g.slices = [("jacket", 0, 0, 1, 2)]

    touched = bm.restore_bust(g, spine_y=5.3, factor=1.32, z_lo=122.0, z_hi=154.0)

    assert touched == 2                        # both in-band, but falloff = 0
    assert g.verts[0][1] == pytest.approx(20.0)
    assert g.verts[1][1] == pytest.approx(20.0)


def test_restore_bust_leaves_the_underarm_seam_in_place():
    g = bm.Group(name="g")
    # centre bust peak vs a vertex out at the underarm (|x| beyond x_zero=15)
    g.verts = [(0.0, 20.0, 138.0), (16.0, 20.0, 138.0)]
    g.slices = [("jacket", 0, 0, 1, 2)]

    touched = bm.restore_bust(g, spine_y=5.3, factor=1.32, z_lo=122.0, z_hi=154.0)

    assert touched == 1                        # only the centre vertex moves
    assert g.verts[0][1] == pytest.approx(5.3 + (20.0 - 5.3) * 1.32)
    assert g.verts[1][1] == pytest.approx(20.0)  # underarm seam untouched


def test_tuck_underarm_skin_tucks_only_skin_touching_the_jacket():
    g = bm.Group(name="g")
    # skin right on the jacket, skin below the band, and the jacket vertex itself
    g.verts = [(15.0, 5.0, 145.0), (15.0, 5.0, 110.0), (15.0, 5.0, 145.0)]
    g.normals = [(1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    g.slices = [("skin", 0, 0, 1, 2), ("jacket", 2, 0, 1, 1)]

    touched = bm.tuck_underarm_skin(g, amount=0.7, near=1.6)

    assert touched == 1                        # only the near-jacket skin vertex
    # d=0 -> full falloff: pushed inward along its +x normal by amount
    assert g.verts[0][0] == pytest.approx(15.0 - 0.7)
    assert g.verts[0][1] == pytest.approx(5.0)
    assert g.verts[1][0] == pytest.approx(15.0)  # below the band untouched
    assert g.verts[2][0] == pytest.approx(15.0)  # the jacket is never moved


def test_tuck_underarm_skin_leaves_far_skin_alone():
    g = bm.Group(name="g")
    # skin in the band but far from any jacket vertex (> near)
    g.verts = [(15.0, 5.0, 145.0), (15.0, 40.0, 145.0)]
    g.normals = [(1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    g.slices = [("skin", 0, 0, 1, 1), ("jacket", 1, 0, 1, 1)]

    touched = bm.tuck_underarm_skin(g, amount=0.7, near=1.6)

    assert touched == 0
    assert g.verts[0][0] == pytest.approx(15.0)


def test_tuck_underarm_skin_covers_upper_arm_sleeve():
    """The band reaches down over the upper-arm sleeve (z~130), not just the
    armpit: the in-game white patches are skin poking through the sleeve there,
    below the old armpit-only band (z_lo=137)."""
    g = bm.Group(name="g")
    g.verts = [(25.0, 5.0, 130.0), (25.0, 5.0, 130.0)]
    g.normals = [(1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    g.slices = [("skin", 0, 0, 1, 1), ("jacket", 1, 0, 1, 1)]

    touched = bm.tuck_underarm_skin(g, amount=0.7, near=1.6)

    assert touched == 1
    assert g.verts[0][0] == pytest.approx(25.0 - 0.7)   # skin tucked inward
    assert g.verts[1][0] == pytest.approx(25.0)          # jacket untouched


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


# ------------------------------------------------- render atoms must tile

def _two_slice_group() -> bm.Group:
    g = bm.Group(name="hands")
    g.palette = ["LeftHand"]
    g.verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
               (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (2.0, 1.0, 0.0)]
    g.normals = [(0.0, 0.0, 1.0)] * 6
    g.uvs = [(0.0, 0.0)] * 6
    g.weights = [[(0, 1.0)]] * 6
    g.faces = [(0, 1, 2), (3, 4, 5)]
    # a slice per donor node, with the *local* triangle offsets a graft produces
    g.slices = [("hands", 0, 0, 1, 3), ("hands", 3, 3, 1, 3)]
    g.mat_slots = ["mtr_hands", "mtr_hands"]
    return g


def test_append_group_rebases_the_triangle_offset_too():
    """A merged slice must carry both the vertex *and* the index offset.

    Only the vertex offset used to be rebased, so the appended slice's render
    atom pointed at the first triangles of the body: the grafted hands were in
    the file but no atom ever drew them, and two torso patches were drawn with
    the hand material instead. Structurally valid, invisible to every preview.
    """
    base = bm.Group(name="body")
    base.palette = ["Spine2"]
    base.verts = [(0.0, 0.0, 100.0)] * 3
    base.normals = [(0.0, 1.0, 0.0)] * 3
    base.uvs = [(0.0, 0.0)] * 3
    base.weights = [[(0, 1.0)]] * 3
    base.faces = [(0, 1, 2), (0, 1, 2)]          # 2 triangles before the merge
    base.slices = [("skin", 0, 0, 2, 3)]
    base.mat_slots = ["mtr_body"]

    bm.append_group(base, _two_slice_group(), _fake_template(["Spine2", "LeftHand"]))

    assert [s[2] for s in base.slices] == [0, 6, 9]     # index offsets, not 0/3
    assert [s[1] for s in base.slices] == [0, 3, 6]     # vertex offsets
    atoms = bm.group_atom_plan(base, sorted(set(base.mat_slots)))
    assert [a["base_index"] for a in atoms] == [0, 6, 9]
    assert [a["base_vertex"] for a in atoms] == [0, 3, 6]


def _fake_template(palette):
    from types import SimpleNamespace
    ids = {n: i + 1 for i, n in enumerate(palette)}
    worlds = {i: (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
                  0.0, 0.0, 1.0, 0.0, float(i), 0.0, 0.0, 1.0)
              for i in ids.values()}
    return SimpleNamespace(name_id=ids, worlds=worlds, hips_id=ids[palette[0]],
                           hips_world=worlds[ids[palette[0]]],
                           drawable_skin={}, drawables={})


def test_atom_problems_catches_a_stale_index_offset():
    geo = {"verts": [(0.0, 0.0, 0.0)] * 6}
    topo = {"indices": [0, 1, 2, 3, 4, 5]}
    good = [{"base_vertex": 0, "slice_len": 3, "base_index": 0, "tri_count": 1},
            {"base_vertex": 3, "slice_len": 3, "base_index": 3, "tri_count": 1}]
    assert bm.atom_problems(geo, topo, good) == []
    stale = [dict(good[0]), {**good[1], "base_index": 0}]
    problems = bm.atom_problems(geo, topo, stale)
    assert any("not 1" in p or "draw" in p for p in problems), problems


@needs_templates
def test_graft_slices_start_where_their_triangles_start():
    """Each graft slice must record its triangle offset *before* adding them.

    The slice's `base_i` is what becomes the render atom's `base_index`. It was
    taken from `len(faces)` *after* the faces were appended, so every slice
    claimed to start one slice late — together with the missing offset in
    `append_group`, the hands ended up referenced by nobody.
    """
    hands = bm.graft_pd2_hands(TEMPLATES / "2b.model")
    want = 0
    for _mat, _bv, base_i, tris, _nv in hands.slices:
        assert base_i == want * 3, f"slice starts at {base_i // 3}, want {want}"
        want += tris
    assert want == len(hands.faces)


# ------------------------------------------------------ wrist weld / caps

def _arm_with_hand(offset=(0.0, 12.0, 0.0), n=12):
    """A sleeve tube and a hand tube whose opening sits `offset` away."""
    import numpy as np

    g = bm.Group(name="body")
    g.palette = ["LeftForeArm", "LeftHand"]
    sleeve_a, sleeve_b, hand_a, hand_b = [], [], [], []
    for k in range(n):
        a = 2 * np.pi * k / n
        x, y = 3 * np.cos(a), 3 * np.sin(a)
        sleeve_a.append((-40.0 + x, 10.0 + y, 130.0))
        sleeve_b.append((-40.0 + x, 10.0 + y, 124.0))
        hand_a.append((-40.0 + x + offset[0], 10.0 + y + offset[1],
                       120.0 + offset[2]))
        hand_b.append((-40.0 + x + offset[0], 10.0 + y + offset[1],
                       114.0 + offset[2]))
    g.verts = sleeve_a + sleeve_b + hand_a + hand_b
    g.normals = [(0.0, 0.0, 1.0)] * len(g.verts)
    g.uvs = [(0.1, 0.1)] * len(g.verts)
    g.weights = ([[(0, 1.0)]] * (2 * n)) + ([[(1, 1.0)]] * (2 * n))
    faces = []
    for k in range(n):                       # sleeve wall first, then the hand
        j = (k + 1) % n
        faces.append((k, j, n + j))
        faces.append((k, n + j, n + k))
    for k in range(n):
        j = (k + 1) % n
        faces.append((2 * n + k, 2 * n + j, 3 * n + j))
        faces.append((2 * n + k, 3 * n + j, 3 * n + k))
    g.faces = faces
    g.slices = [("skin", 0, 0, len(faces), len(g.verts))]
    g.mat_slots = ["mtr_body"]
    return g, len(faces), n


def test_weld_wrist_pulls_the_sleeve_onto_the_hand_and_caps_the_cuff():
    g, nfaces, n = _arm_with_hand()
    verts_before = len(g.verts)
    report = bm.weld_wrist(g, (2 * n, 4 * n), (2 * n, 4 * n))

    assert report["pairs"], "no wrist opening was found"
    pair = report["pairs"][0]
    assert pair["sleeve"] == n and pair["hand"] == n
    # the sleeve mouth followed the hand: what is left of the offset is
    # small enough for the two caps to overlap inside the cuff
    assert pair["gap_cm"] < 4.0, pair
    # ...because the sleeve mouth was moved, not left where it was
    assert len(g.verts) > verts_before
    # the cuff itself is closed: no boundary loop is left at the sleeve mouth
    import numpy as np

    mouth = np.mean([g.verts[i] for i in range(n, 2 * n)], axis=0)
    left = [lp for lp in bm.boundary_loops(g.faces)
            if len(lp) <= 40 and np.linalg.norm(
                np.mean([g.verts[i] for i in lp], axis=0) - mouth) < 3.0]
    assert not left, left


def test_weld_wrist_keeps_the_hand_where_the_weapon_bone_is():
    """The hand is the thing the gun follows: it may not move at all."""
    g, nfaces, n = _arm_with_hand()
    before = [g.verts[i] for i in range(2 * n, 4 * n)]
    bm.weld_wrist(g, (2 * n, 4 * n), (2 * n, 4 * n))
    after = [g.verts[i] for i in range(2 * n, 4 * n)]
    assert before == after


def test_weld_wrist_reports_atoms_that_tile():
    geo = {"verts": None}
    g, nfaces, n = _arm_with_hand()
    bm.weld_wrist(g, (2 * n, 4 * n), (2 * n, 4 * n))
    atoms = bm.group_atom_plan(g, sorted(set(g.mat_slots)))
    geo["verts"] = g.verts
    topo = {"indices": [i for f in g.faces for i in f]}
    assert bm.atom_problems(geo, topo, atoms) == []


@needs_templates
def test_graft_uvs_use_the_internal_v_convention():
    """Graft UVs must be (u, 1 - v), like every other slice in the block.

    Storing the donor's raw v put the hands in the wrong half of the atlas —
    the region that holds the donor's black bodysuit — and the grafted hands
    rendered as dark grey-brown mittens in every build until this was found.
    """
    hands = bm.graft_pd2_hands(TEMPLATES / "2b.model")
    assert hands.uvs, "no UVs grafted"
    v = [uv[1] for uv in hands.uvs]
    assert min(v) >= -1.5 and max(v) <= 1.5
    # the donor's hands sit in the lower half of its atlas; the internal
    # convention therefore puts them in the upper half
    assert sum(1 for x in v if 0.0 <= x <= 1.0) > 0.5 * len(v)


def test_weld_wrist_caps_the_cuff_in_skin_not_cloth():
    """The cap that closes a sleeve mouth is skin, like LAS's own outfits.

    A Legendary Armour Skins outfit keeps its hands as a skin slice in the same
    model as the clothes (`mtr_hands`, plus `mtr_arms` for a bare wrist in the
    first-person units), and the sleeve simply overlaps the arm. Capping the
    cuff with the mouth's own material instead painted the opening with the
    garment's *inner* layer -- for this outfit the white lace of the bustier,
    which showed up as a pale ring at each wrist.
    """
    g, _nfaces, n = _arm_with_hand()
    bm.weld_wrist(g, (2 * n, 4 * n), (2 * n, 4 * n),
                  slot="mtr_jacket", hand_slot="mtr_hands")
    caps = [slot for slot in g.mat_slots if slot == "mtr_hands"]
    assert caps, g.mat_slots
    assert "mtr_jacket" not in g.mat_slots, (
        "the cuff cap took the sleeve's material")


def test_tuck_shirt_sleeves_pushes_jacket2_inward():
    """The white shirt sleeve (jacket2) near the blazer is pushed inward along
    its normal so it stops poking through the blazer sleeve; blazer untouched."""
    g = bm.Group(name="g")
    g.verts = [(30.0, 0.0, 128.0), (30.0, 1.0, 128.0)]
    g.normals = [(0.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    g.slices = [("jacket", 0, 0, 1, 1), ("jacket2", 1, 0, 1, 1)]

    touched = bm.tuck_shirt_sleeves(g)

    assert touched == 1
    assert g.verts[0] == (30.0, 0.0, 128.0)      # blazer reference untouched
    assert g.verts[1][1] < 1.0                    # shirt moved inward (-normal)
    assert g.verts[1][0] == 30.0 and g.verts[1][2] == 128.0


def test_tuck_shirt_sleeves_leaves_collar_and_blazer():
    """Only the upper-arm band is tucked: the visible collar/lapel (small |x|,
    high z) and any non-jacket2 material are left alone."""
    g = bm.Group(name="g")
    g.verts = [(30.0, 0.0, 128.0), (5.0, 1.0, 150.0), (30.0, 1.0, 100.0)]
    g.normals = [(0.0, 1.0, 0.0)] * 3
    g.slices = [("jacket", 0, 0, 1, 1), ("jacket2", 1, 0, 1, 2)]

    touched = bm.tuck_shirt_sleeves(g)

    assert touched == 0
    assert g.verts[1] == (5.0, 1.0, 150.0)       # collar: |x|<20 and z>138
    assert g.verts[2] == (30.0, 1.0, 100.0)      # below the band (z<116)


def test_tuck_shirt_cuffs_retracts_jacket2_up_the_forearm():
    """The wrist cuff slides up the forearm (z increases) and toward the arm axis,
    into the blazer sleeve, instead of sitting at the opening as a white ring."""
    g = bm.Group(name="g")
    g.verts = [(-42.0, 14.0, 125.0)]
    g.normals = [(0.0, 1.0, 0.0)]
    g.slices = [("jacket2", 0, 0, 1, 1)]

    touched = bm.tuck_shirt_cuffs(g)

    assert touched == 1
    x, y, z = g.verts[0]
    assert z > 125.0                              # retracted toward the elbow
    assert (x, y, z) != (-42.0, 14.0, 125.0)


def test_extend_blazer_sleeves_lengthens_jacket_toward_wrist():
    """The blazer sleeve opening slides down the forearm (z decreases) so it
    overlaps the game glove and closes the wrist junction; shirt/collar untouched."""
    g = bm.Group(name="g")
    g.verts = [(-42.0, 14.0, 118.0), (-42.0, 14.0, 140.0), (5.0, 10.0, 118.0)]
    g.normals = [(0.0, 1.0, 0.0)] * 3
    g.slices = [("jacket", 0, 0, 1, 2), ("jacket2", 2, 0, 1, 1)]

    touched = bm.extend_blazer_sleeves(g)

    assert touched == 1                          # only the low blazer sleeve vert
    assert g.verts[0][2] < 118.0                 # lengthened toward the wrist
    assert g.verts[1] == (-42.0, 14.0, 140.0)    # above the falloff band
    assert g.verts[2] == (5.0, 10.0, 118.0)      # shirt / collar not jacket


def test_tuck_shirt_cuffs_ignores_collar_and_blazer():
    g = bm.Group(name="g")
    g.verts = [(5.0, 10.0, 125.0), (-42.0, 14.0, 125.0)]
    g.normals = [(0.0, 1.0, 0.0)] * 2
    g.slices = [("jacket2", 0, 0, 1, 1), ("jacket", 1, 0, 1, 1)]

    touched = bm.tuck_shirt_cuffs(g)

    assert touched == 0
    assert g.verts[0] == (5.0, 10.0, 125.0)      # collar: |x|<30
    assert g.verts[1] == (-42.0, 14.0, 125.0)    # blazer is not jacket2


# ------------------------------------------------- seams and sleeve reach
#
# Two defects the in-game screenshots pinned down: the blazer's sleeve seam is a
# pair of coincident vertex rows whose influence lists disagree (so the seam
# tears open at the shoulder as soon as the arm moves), and every arm layer stops
# short of the PD2 hand joint (so the heister's glove floats in front of the
# sleeve). These pin the two passes that fix them.


def _two_row_seam(wa, wb):
    """Two coincident vertex rows, each row owning its own quad.

    Vertex 0/1 are row A, 2/3 row B, at the same positions; the quads are
    deliberately *not* stitched, exactly like a BodySlide UV seam.
    """
    g = bm.Group(name="g")
    g.verts = [(0.0, 0.0, 0.0), (0.0, 20.0, 0.0),
               (0.0, 0.0, 0.0), (0.0, 20.0, 0.0),
               (4.0, 0.0, 0.0), (4.0, 20.0, 0.0),
               (-4.0, 0.0, 0.0), (-4.0, 20.0, 0.0)]
    g.normals = [(1.0, 0.0, 0.0)] * len(g.verts)
    g.faces = [(0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3)]
    g.slices = [("jacket", 0, 0, 4, len(g.verts))]
    g.weights = [wa, wa, wb, wb, wa, wa, wb, wb]
    return g


def test_weld_open_seams_averages_the_two_rows_of_a_gap_seam():
    g = _two_row_seam([(0, 1.0)], [(1, 1.0)])       # 100 % arm vs 100 % torso

    report = bm.weld_open_seams(g)

    assert report["pairs"] >= 1
    assert dict(g.weights[0]) == dict(g.weights[2]) == {0: 0.5, 1: 0.5}
    assert sum(w for _, w in g.weights[0]) == pytest.approx(1.0)


def test_weld_open_seams_keeps_three_influences_and_drops_the_rest():
    g = _two_row_seam([(0, 1.0)], [(1, 0.6), (2, 0.4)])

    bm.weld_open_seams(g)

    merged = dict(g.weights[0])
    assert len(g.weights[0]) <= 3
    assert sum(w for _, w in g.weights[0]) == pytest.approx(1.0)
    assert merged[0] == pytest.approx(0.5)


def test_weld_open_seams_ignores_a_real_opening():
    g = _two_row_seam([(0, 1.0)], [(1, 1.0)])
    for i in (0, 1):
        g.verts[i] = (0.0, g.verts[i][1], 3.0)      # 3 cm apart: a placket, not a seam

    report = bm.weld_open_seams(g)

    assert report["pairs"] == 0
    assert dict(g.weights[0]) == {0: 1.0}


def _arm_ring(wrist, d, t, radius, n=8):
    """``n`` vertices on a circle of ``radius`` around the arm axis at ``t``."""
    import math

    # any pair of unit vectors perpendicular to d
    a = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = [a[1] * d[2] - a[2] * d[1], a[2] * d[0] - a[0] * d[2], a[0] * d[1] - a[1] * d[0]]
    ln = sum(c * c for c in u) ** 0.5
    u = [c / ln for c in u]
    v = [d[1] * u[2] - d[2] * u[1], d[2] * u[0] - d[0] * u[2], d[0] * u[1] - d[1] * u[0]]
    out = []
    for i in range(n):
        th = 2.0 * math.pi * i / n
        c, s_ = math.cos(th), math.sin(th)
        out.append(tuple(wrist[j] + t * d[j] + radius * (c * u[j] + s_ * v[j])
                         for j in range(3)))
    return out


def test_extend_sleeves_to_wrist_reaches_past_the_hand_joint():
    wrist, elbow = bm.ARM_JOINTS[-1]
    raw = [e - w for w, e in zip(wrist, elbow)]
    ln = sum(c * c for c in raw) ** 0.5
    d = [c / ln for c in raw]                      # wrist -> elbow, unit
    g = bm.Group(name="g")
    g.verts = _arm_ring(wrist, d, 9.0, 3.5) + _arm_ring(wrist, d, 20.0, 3.5)
    g.slices = [("jacket", 0, 0, 1, len(g.verts))]
    before_elbow = list(g.verts[8:])

    report = bm.extend_sleeves_to_wrist(g, mats={"jacket": -2.5}, t_knee=13.0)

    assert report["moved"] == 8
    # the mouth ring (t=9) lands 2.5 cm past the hand joint, along the axis
    for p, q in zip(g.verts[:8], _arm_ring(wrist, d, -2.5, 3.5)):
        for a, b in zip(p, q):
            assert a == pytest.approx(b, abs=1e-6)
    # the ring near the elbow is untouched (past the blend)
    assert g.verts[8:] == before_elbow


def test_extend_sleeves_leaves_a_sleeve_that_already_reaches_alone():
    g = bm.Group(name="g")
    wrist, elbow = bm.ARM_JOINTS[-1]
    for ux, uy in ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0),
                   (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)):
        g.verts.append((wrist[0] + 3.0 * ux, wrist[1] + 3.0 * uy, wrist[2]))
    g.slices = [("jacket", 0, 0, 1, len(g.verts))]
    before = list(g.verts)

    report = bm.extend_sleeves_to_wrist(g, mats={"jacket": -2.5})

    assert report["moved"] == 0
    assert g.verts == before
