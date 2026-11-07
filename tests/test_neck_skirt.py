"""Unit tests for the head packs' neck skirt (`extend_neck_skirt`).

The head models are cut off at the neck, and over a body whose neckline is open
the sheet's rim is the front-most surface across the throat — 100 % of its border
edges over the Christie LAS body
(docs/audits/2026-11-07-christie-slim-diagnosis.md §10). The skirt pass extrudes
one ring below that rim so it ends inside the body instead.

The fixture is an open cylinder standing in for the neck: an open bottom rim at
z = 150 is exactly the case the pass exists for, and the arithmetic (drop, tuck,
back) is checkable without any of the nine packs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
sys.path.insert(0, str(REPO / "tools" / "pd2-port"))

bjm = pytest.importorskip("build_joy_head_mods")


def _open_tube(n: int = 16, radius: float = 5.0, centre=(0.0, 2.0),
               z0: float = 150.0, z1: float = 160.0):
    """An open-bottomed tube: two rings, quads, rim at z0.

    The upper ring sits above ``NECK_SKIRT_MAX_Z`` on purpose, so only the bottom
    rim is a candidate - that is what the neck sheet looks like once the scalp
    has been cut away.
    """
    ang = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    cx, cy = centre
    low = np.stack([cx + radius * np.cos(ang), cy + radius * np.sin(ang),
                    np.full(n, z0)], axis=1)
    high = low.copy()
    high[:, 2] = z1
    verts = np.vstack([low, high]).astype(np.float32)
    normals = np.zeros_like(verts)
    normals[:, 0] = np.tile(np.cos(ang), 2)
    normals[:, 1] = np.tile(np.sin(ang), 2)
    uvs = np.zeros((2 * n, 2), dtype=np.float32)
    uvs[:, 0] = np.tile(np.arange(n) / n, 2)
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris.append([i, j, n + j])
        tris.append([i, n + j, n + i])
    return verts, normals, uvs, np.asarray(tris, dtype=np.int32)


def test_skirt_adds_one_ring_below_the_rim_and_keeps_existing_indices():
    verts, normals, uvs, tris = _open_tube()
    p, n, uv, t = bjm.extend_neck_skirt(verts, normals, uvs, tris)
    assert len(p) == len(verts) + 16
    assert len(t) == len(tris) + 32
    np.testing.assert_allclose(p[:len(verts)], verts)      # no vertex moved
    np.testing.assert_allclose(n[:len(verts)], normals)
    np.testing.assert_allclose(uv[:len(verts)], uvs)


def test_new_ring_is_dropped_tucked_and_pushed_forward():
    verts, normals, uvs, tris = _open_tube()
    p, _n, _uv, _t = bjm.extend_neck_skirt(
        verts, normals, uvs, tris, drop=6.0, tuck=0.9, forward=0.5)
    ring = p[len(verts):]
    np.testing.assert_allclose(ring[:, 2], 150.0 - 6.0, atol=1e-4)
    radius_in = np.hypot(ring[:, 0], ring[:, 1] - 2.5)
    np.testing.assert_allclose(radius_in, 5.0 * 0.9, atol=1e-4)
    np.testing.assert_allclose(ring[:, 1].mean(), 2.5, atol=1e-4)


def test_strip_is_a_watertight_band_between_the_rim_and_the_new_ring():
    """Two triangles per rim edge, no stray boundary inside the band."""
    verts, normals, uvs, tris = _open_tube()
    p, _n, _uv, t = bjm.extend_neck_skirt(verts, normals, uvs, tris)
    added = t[len(tris):]
    assert len(added) == 2 * 16
    counts: dict[tuple[int, int], int] = {}
    for a, b, c in added:
        for u, v in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            e = (u, v) if u < v else (v, u)
            counts[e] = counts.get(e, 0) + 1
    rim = set(range(16))
    ring = set(range(len(verts), len(p)))
    open_edges = [e for e, c in counts.items() if c == 1]
    # the band is open only along the old rim and along the new ring
    assert all((e[0] in rim and e[1] in rim) or (e[0] in ring and e[1] in ring)
               for e in open_edges)
    assert len(open_edges) == 32
    # shared vertical edges and the band's interior are manifold
    assert max(counts.values()) == 2
    assert all(v in {1, 2} for v in counts.values())


def test_strip_keeps_the_sheets_facing():
    """The new quads must not be inside-out relative to the tube's normals."""
    verts, normals, uvs, tris = _open_tube()
    p, n, _uv, t = bjm.extend_neck_skirt(verts, normals, uvs, tris)
    added = t[len(tris):]
    tri = p[added]
    face_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    vert_n = n[added].mean(axis=1)
    assert (np.einsum("ij,ij->i", face_n, vert_n) > 0).all()


def test_a_closed_mesh_is_left_alone():
    verts, normals, uvs, tris = _open_tube()
    # cap the bottom so there is no rim below max_z
    cap = len(verts)
    centre = np.array([[0.0, 2.0, 150.0]], dtype=np.float32)
    p = np.vstack([verts, centre])
    n = np.vstack([normals, np.zeros((1, 3), dtype=np.float32)])
    uv = np.vstack([uvs, np.zeros((1, 2), dtype=np.float32)])
    extra = [[i, (i + 1) % 16, cap] for i in range(16)]
    t = np.vstack([tris, np.asarray(extra, dtype=np.int32)])
    out = bjm.extend_neck_skirt(p, n, uv, t)
    assert len(out[0]) == len(p)
    assert len(out[3]) == len(t)


def test_high_rims_are_ignored():
    """A rim above max_z is the scalp cut, not the neck: no skirt there."""
    verts, normals, uvs, tris = _open_tube(z0=170.0, z1=176.0)
    out = bjm.extend_neck_skirt(verts, normals, uvs, tris)
    assert len(out[0]) == len(verts)
