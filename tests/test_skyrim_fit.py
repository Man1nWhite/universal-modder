"""Tests for the two source-side re-fits in `skyrim_source.py`.

Both exist because a Skyrim asset is not shaped for Diesel's skeleton, and both
fail silently if they regress: a bead collapses into a dot, or the character
stands knee-deep in the floor. Neither needs the outfit archives.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
sys.path.insert(0, str(ROOT / "tools" / "skyrim-nif"))

import decimate as dc  # noqa: E402
import skyrim_source as ss  # noqa: E402


@pytest.fixture(scope="module")
def nif():
    path = ROOT / "tools" / "skyrim-nif" / "nif.py"
    spec = importlib.util.spec_from_file_location("test_nif_reader", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------- heels
def test_heel_fit_puts_the_sole_on_the_floor():
    """The source shoe stands on z = -12 cm; Diesel's floor is z = 0."""
    shoe = np.array([[0.0, 0.0, -12.0], [2.0, 0.0, -12.0],
                     [0.0, 4.0, -6.0], [0.0, 0.0, 8.7]])
    out, report = ss.fit_feet_to_ground(shoe, ankle_z=8.7, blend_cm=2.5)
    assert report["applied"] is True
    assert out[:, 2].min() == pytest.approx(0.0, abs=1e-9)
    assert out[-1, 2] == pytest.approx(8.7)           # the ankle does not move


def test_heel_fit_only_touches_geometry_below_the_ankle():
    shoe = np.array([[0.0, 0.0, -12.0], [0.0, 0.0, 8.7], [0.0, 0.0, 20.0]])
    out, _ = ss.fit_feet_to_ground(shoe, ankle_z=8.7, blend_cm=2.5)
    assert out[2, 2] == pytest.approx(20.0)           # the shaft is untouched
    assert out[1, 2] == pytest.approx(8.7)            # the joint is the pivot


def test_heel_fit_is_idempotent_on_already_flat_geometry():
    flat = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 8.7]])
    out, report = ss.fit_feet_to_ground(flat, ankle_z=8.7)
    assert report["applied"] is False
    assert np.allclose(out, flat)


def test_heel_fit_compresses_rather_than_translating():
    """A pure translation would float the ankle above the shaft; keep the joint."""
    shoe = np.array([[0.0, 0.0, -12.0], [0.0, 0.0, 8.7]])
    out, report = ss.fit_feet_to_ground(shoe, ankle_z=8.7)
    assert report["compression"] == pytest.approx(8.7 / 20.7, abs=1e-4)
    assert np.all(out[:, 2] >= 0.0)


# ------------------------------------------------------------------ decimate
def _sphere(radius=0.5, n=12):
    """A UV sphere: the shape the necklace beads actually are."""
    u = np.linspace(0, np.pi, n)
    v = np.linspace(0, 2 * np.pi, n, endpoint=False)
    verts = []
    for theta in u:
        for phi in v:
            verts.append([radius * np.sin(theta) * np.cos(phi),
                          radius * np.sin(theta) * np.sin(phi),
                          radius * np.cos(theta)])
    verts = np.array(verts)
    tris = []
    for i in range(n - 1):
        for j in range(n):
            a = i * n + j
            b = i * n + (j + 1) % n
            c = (i + 1) * n + j
            d = (i + 1) * n + (j + 1) % n
            tris += [(a, b, c), (b, d, c)]
    return verts, np.array(tris)


def test_decimate_respects_the_vertex_budget():
    verts, tris = _sphere(0.5, 16)
    out = dc.decimate(verts, tris, max_vertices=60)
    assert out.vertices.shape[0] <= 60
    assert out.triangles.shape[0] > 0


def test_decimate_keeps_every_island():
    """Two beads must stay two beads: clustering never welds across islands."""
    a_v, a_t = _sphere(0.5, 10)
    b_v, b_t = _sphere(0.5, 10)
    verts = np.concatenate([a_v, b_v + np.array([5.0, 0.0, 0.0])])
    tris = np.concatenate([a_t, b_t + a_v.shape[0]])
    out = dc.decimate(verts, tris, max_vertices=80)
    assert out.islands == 2
    # each surviving island still sits around its own centre
    left = out.vertices[out.vertices[:, 0] < 2.5]
    right = out.vertices[out.vertices[:, 0] >= 2.5]
    assert len(left) and len(right)
    assert left[:, 0].mean() == pytest.approx(0.0, abs=0.6)
    assert right[:, 0].mean() == pytest.approx(5.0, abs=0.6)


def test_decimate_stays_on_the_surface():
    verts, tris = _sphere(0.5, 18)
    out = dc.decimate(verts, tris, max_vertices=120)
    radii = np.linalg.norm(out.vertices, axis=1)
    assert radii.min() > 0.35                         # no bead collapsed inward
    assert radii.max() < 0.65
    err = dc.surface_error(verts, tris, out.vertices)
    assert err["max"] < 0.2                            # 20 % of the radius


def test_decimate_carries_uvs_and_normals():
    verts, tris = _sphere(0.5, 10)
    uvs = np.random.default_rng(0).random((verts.shape[0], 2))
    normals = verts / np.linalg.norm(verts, axis=1, keepdims=True)
    out = dc.decimate(verts, tris, uvs=uvs, normals=normals, max_vertices=50)
    assert out.uvs.shape == (out.vertices.shape[0], 2)
    assert np.all((out.uvs >= 0.0) & (out.uvs <= 1.0))
    assert np.allclose(np.linalg.norm(out.normals, axis=1), 1.0, atol=1e-6)


def test_decimate_maps_every_new_vertex_back_to_a_source_vertex():
    """Blend weights are copied, not averaged, so the map has to exist."""
    verts, tris = _sphere(0.5, 10)
    out = dc.decimate(verts, tris, max_vertices=40)
    assert out.source_index.shape == (out.vertices.shape[0],)
    assert out.source_index.min() >= 0
    assert out.source_index.max() < verts.shape[0]


def test_decimate_leaves_a_mesh_already_under_budget_alone():
    """Only exactly-coincident vertices may merge when the budget is generous."""
    verts = np.array([[0.0, 0.0, 0.0], [0.3, 0.0, 0.0], [0.0, 0.3, 0.0],
                      [0.0, 0.0, 0.3], [0.3, 0.3, 0.0]])
    tris = np.array([[0, 1, 2], [0, 2, 3], [1, 4, 2]])
    out = dc.decimate(verts, tris, max_vertices=10_000)
    assert out.vertices.shape[0] == verts.shape[0]
    assert out.triangles.shape[0] == tris.shape[0]


def test_decimate_merges_only_exactly_coincident_vertices():
    """A UV sphere's poles are duplicated per column; those must collapse."""
    verts, tris = _sphere(0.5, 6)
    out = dc.decimate(verts, tris, max_vertices=10_000)
    assert out.vertices.shape[0] < verts.shape[0]      # poles merged
    assert out.vertices.shape[0] > verts.shape[0] * 0.5


def test_decimate_rejects_degenerate_triangles():
    """Clusters that swallow a whole triangle must drop it, not emit zero area."""
    verts = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0],
                      [1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    tris = np.array([[0, 1, 2], [3, 4, 5], [0, 2, 3]])
    out = dc.decimate(verts, tris, max_vertices=8)
    for a, b, c in out.triangles:
        assert len({int(a), int(b), int(c)}) == 3


# ------------------------------------------------------------------ outfit
@pytest.fixture(scope="module")
def source_root():
    from build_skyrim_outfit import mesh_root

    direct = ROOT / "meshes" / "exampleauthor" / "outfit"
    if not direct.is_dir() and not (ROOT / "4.zip").exists():
        pytest.skip("the Skyrim source archive was intentionally removed after cancellation")
    return mesh_root(ROOT)


def test_default_outfit_keeps_both_jacket_layers(source_root):
    specs = ss.default_outfit(source_root)
    materials = [s.material for s in specs]
    assert materials.count("jacket") == 1 and materials.count("jacket2") == 1
    assert "necklace" in materials


def test_necklace_is_the_only_decimated_piece(source_root):
    specs = ss.default_outfit(source_root)
    decimated = {s.material: s.decimate_to for s in specs if s.decimate_to}
    assert decimated == {"necklace": 3000}


def test_decimate_output_has_no_folded_triangles():
    """The pipeline asserts 0 orientation breaks; clustering must not add any."""
    import build_models as bm

    verts, tris = _sphere(0.5, 14)
    out = dc.decimate(verts, tris, max_vertices=200)
    faces = [tuple(int(x) for x in tri) for tri in out.triangles]
    assert bm.orientation_breaks(type("G", (), {"faces": faces})) == 0


def test_drop_flipped_removes_both_members_of_a_bad_pair():
    # only these two faces touch edge (0,1), and both traverse it the same way
    tris = np.array([[0, 1, 2], [0, 1, 3]])
    kept, removed = dc.drop_flipped(tris)
    assert removed == 2
    assert kept.shape[0] == 0


def test_drop_flipped_keeps_a_correctly_wound_pair():
    tris = np.array([[0, 1, 2], [1, 0, 3]])
    kept, removed = dc.drop_flipped(tris)
    assert removed == 0 and kept.shape[0] == 2


# ------------------------------------------------------------- neck cap / fps
def _group(verts, faces, palette, weights):
    import build_models as bm

    g = bm.Group(name="t")
    g.verts = [tuple(map(float, v)) for v in verts]
    g.normals = [(0.0, 0.0, 1.0)] * len(verts)
    g.uvs = [(0.5, 0.5)] * len(verts)
    g.palette = palette
    g.weights = weights
    g.faces = list(faces)
    g.mat_slots = ["mtr_body"]
    g.slices = [("skin", 0, 0, len(faces), len(verts))]
    return g


def test_boundary_loops_finds_the_open_ring_of_a_tube():
    import build_models as bm

    # a square tube: 4 side quads, open at both ends
    faces = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    loops = bm.boundary_loops(faces)
    assert len(loops) == 2
    assert sorted(len(l) for l in loops) == [5, 5]   # closed rings
    assert all(l[0] == l[-1] for l in loops)


def test_cap_holes_closes_only_the_ring_above_the_cut():
    import build_models as bm

    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
             (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
    faces = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    g = _group(verts, faces, ["Hips"], [[(0, 1.0)]] * 8)
    added = bm.cap_holes(g, min_z=0.5, slot="mtr_body", max_span=5.0)
    assert added == 4                       # only the top ring
    assert len(g.slices) == 2               # the cap is its own render atom
    assert g.slices[-1][3] == 4
    assert bm.orientation_breaks(g) == 0


def test_cap_holes_skips_loops_wider_than_a_neck():
    """UV seams and garment openings are boundary loops too, and must be left."""
    import build_models as bm

    verts = [(0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0),
             (0, 0, 1), (20, 0, 1), (20, 20, 1), (0, 20, 1)]
    faces = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    g = _group(verts, faces, ["Hips"], [[(0, 1.0)]] * 8)
    assert bm.cap_holes(g, min_z=0.5, slot="mtr_body", max_span=14.0) == 0


def test_cap_holes_respects_the_allowed_vertex_set():
    import build_models as bm

    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
             (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
    faces = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    g = _group(verts, faces, ["Hips"], [[(0, 1.0)]] * 8)
    assert bm.cap_holes(g, min_z=0.5, slot="mtr_body",
                        allowed={4, 5, 6}, max_span=5.0) == 0


def test_cap_vertex_inherits_the_loop_weights():
    import build_models as bm

    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
             (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
    faces = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    weights = [[(0, 1.0)]] * 4 + [[(1, 1.0)]] * 4
    g = _group(verts, faces, ["Hips", "Neck"], weights)
    bm.cap_holes(g, min_z=0.5, slot="mtr_body", max_span=5.0)
    assert g.weights[-1] == [(1, 1.0)]        # the cap follows the neck
    assert sum(w for _, w in g.weights[-1]) == pytest.approx(1.0)


def test_extract_bones_keeps_only_dominated_geometry():
    import build_models as bm

    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (5, 5, 5), (6, 5, 5), (5, 6, 5)]
    faces = [(0, 1, 2), (3, 4, 5)]
    weights = [[(0, 1.0)]] * 3 + [[(1, 1.0)]] * 3
    g = _group(verts, faces, ["LeftArm", "Hips"], weights)
    out = bm.extract_bones(g, ["LeftArm"], "arms")
    assert len(out.verts) == 3 and len(out.faces) == 1
    assert out.palette == ["LeftArm", "Hips"]
    assert out.slices[0][:2] == ("skin", 0)
    # every vertex still carries its weight row
    assert out.weights[0] == [(0, 1.0)]


def test_extract_bones_refuses_an_empty_selection():
    import build_models as bm

    g = _group([(0, 0, 0)], [(0, 0, 0)], ["Hips"], [[(0, 1.0)]])
    with pytest.raises(SystemExit):
        bm.extract_bones(g, ["LeftArm"], "arms")
