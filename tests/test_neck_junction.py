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
    """Two skins 4 mm apart: the one further forward owns the cell."""
    xs = np.array([0.0])
    zs = np.array([155.0])
    body = nj.front_depth(*_slab(-2, 2, 148, 162, 0.0), xs, zs)
    head = nj.front_depth(*_slab(-2, 2, 148, 162, -0.4), xs, zs)
    assert head[0, 0] < body[0, 0]
    assert head[0, 0] == pytest.approx(-0.4, abs=1e-9)


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
