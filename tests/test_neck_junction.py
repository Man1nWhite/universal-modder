"""Unit tests for `tools/pd2-las/neck_junction.py` (no packs needed).

The head <-> body neck junction is measured with a front-parallel ray cast per
mesh, and the interesting quantity is *which* mesh a pixel belongs to. The
fixtures here are slabs at known depths, so the answer is arithmetic and the
tool's derivation of "head in front" / "body in front" can be checked without
the nine head packs or the Christie body.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

nj = pytest.importorskip("neck_junction")


def _slab(x0: float, x1: float, z0: float, z1: float, y: float):
    """A single vertical quad at constant y (two triangles, faces +y)."""
    verts = np.array([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], float)
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    return verts, faces


def test_front_depth_reads_the_nearest_quad():
    v, f = _slab(-2, 2, 148, 162, -3.0)
    depth = nj.front_depth(v, f, np.array([0.0]), np.array([155.0]))
    assert depth.shape == (1, 1)
    assert np.isfinite(depth[0, 0])
    assert depth[0, 0] == pytest.approx(-3.0, abs=1e-9)


def test_front_depth_is_nan_where_nothing_is_hit():
    v, f = _slab(-2, 2, 148, 152, -3.0)
    depth = nj.front_depth(v, f, np.array([10.0]), np.array([155.0]))
    assert np.isnan(depth[0, 0])


def test_nearer_surface_wins_the_pixel():
    """Two skins 4 mm apart: the one nearer the front camera owns the cell.

    ``+y`` is the character's front in model space - the face is the head's
    narrow y-maximum, and ``preview_textured``'s "Portrait Front" looks straight
    at it - so the surface nearest the front camera has the *largest* y.
    """
    xs = np.array([0.0])
    zs = np.array([155.0])
    body = nj.front_depth(*_slab(-2, 2, 148, 162, 0.0), xs, zs)
    head = nj.front_depth(*_slab(-2, 2, 148, 162, 0.4), xs, zs)
    assert head[0, 0] > body[0, 0]
    assert head[0, 0] == pytest.approx(0.4, abs=1e-9)


def test_back_depth_reads_the_rear_most_quad():
    v, f = _slab(-2, 2, 148, 162, 0.0)
    back = nj.back_depth(v, f, np.array([0.0]), np.array([155.0]))
    assert back[0, 0] == pytest.approx(0.0, abs=1e-9)


def _rim_ring(n: int = 12, radius: float = 3.0, z: float = 150.0,
              centre=(0.0, 2.0)):
    """A neck tube cut off at ``z`` and closed over the top: one boundary loop."""
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([centre[0] + radius * np.cos(angles),
                     centre[1] + radius * np.sin(angles),
                     np.full(n, z)], axis=1)
    apex = np.array([[centre[0], centre[1], 190.0]])
    verts = np.vstack([ring, apex])
    faces = np.array([[i, (i + 1) % n, n] for i in range(n)])
    return verts, faces


def test_neck_rim_edges_is_the_open_bottom_only():
    verts, faces = _rim_ring()
    edges = nj.neck_rim_edges(verts, faces)
    assert len(edges) == 12
    for a, b in edges:
        assert verts[a][2] == pytest.approx(150.0, abs=1e-9)
        assert verts[b][2] == pytest.approx(150.0, abs=1e-9)


def test_border_exposure_reads_both_sides_the_right_way_round():
    """A slab in front of the rim covers it; the same slab behind does not.

    This is the control the first version of ``border_exposure`` needed: it
    compared the body's depth against the rim the wrong way round and reported
    covered edges as exposed (diagnosis §10).
    """
    verts, faces = _rim_ring()
    front_cover = _slab(-6, 6, 148, 154, 20.0)
    rep = nj.border_exposure(verts, faces, *front_cover)
    assert rep["edges"] == 12
    assert rep["front"] == 0                    # something is in front of it
    assert rep["back"] == rep["edges"]          # nothing is behind it

    back_cover = _slab(-6, 6, 148, 154, -20.0)
    rep = nj.border_exposure(verts, faces, *back_cover)
    assert rep["front"] == rep["edges"]
    assert rep["back"] == 0


def test_neck_border_ignores_the_skull_and_finds_the_neck_ring():
    """The lowest boundary loop near the axis is the neck skirt's edge."""
    n = 12
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.stack([3.0 * np.cos(angles), 1.0 + 3.0 * np.sin(angles),
                     np.full(n, 150.0)], axis=1)
    apex = np.array([[0.0, 1.0, 190.0]])
    verts = np.vstack([ring, apex])
    faces = []
    for i in range(n):
        faces.append([i, (i + 1) % n, n])          # fan up to the apex
    border = nj.neck_border(verts, np.array(faces))
    assert border["n"] == n
    assert border["z"] == pytest.approx((150.0, 150.0), abs=1e-9)
    assert border["radius"] == pytest.approx(3.0, abs=1e-6)


def test_grid_difference_counts_cells_that_change_owner():
    """The A/B for two heads: same owner everywhere means the change is invisible."""
    body = np.array([[True, True], [False, False]])
    head = np.array([[False, False], [True, True]])
    miss = np.zeros_like(body)
    same = {"grid": {"body": body, "head": head, "miss": miss}}
    assert nj.grid_difference(same, same)["changed"] == 0

    moved = np.array([[True, False], [False, False]])
    other = {"grid": {"body": moved, "head": ~moved & ~miss, "miss": miss}}
    diff = nj.grid_difference(same, other)
    assert diff["changed"] == 1
    assert diff["cells"] == 4
    assert diff["by_kind"] == {"body": 1, "head": 1, "miss": 0}
