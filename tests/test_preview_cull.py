"""Regression tests for backface culling in the textured pose preview.

The offline preview used to draw *both* sides of every triangle, so a garment
overlap that folds open under an arms-down pose was silently filled by the far
side of the fabric and the hole never showed. `render(..., cull=True)` now drops
back-facing triangles the way the game does, which is what lets the shoulder
stay be verified offline (see the knowledge note on the overlap armhole).

These tests pin the culling *direction*: a triangle whose geometric normal
points at the camera must survive, and one pointing away must be dropped only
when culling is on. An inverted sign here would cull the whole outfit and read
as a blank/gray figure, which is exactly the failure this guards against.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import preview_textured as pt  # noqa: E402


def _tri(front: bool) -> list[dict]:
    """One triangle in the XZ plane; ``front`` faces the +Y (front) camera."""
    if front:
        verts = np.array([[0, 0, 0], [0, 0, 1], [1, 0, 0]], float)
        n = np.array([0.0, 1.0, 0.0])
    else:
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 0, 1]], float)
        n = np.array([0.0, -1.0, 0.0])
    return [{"vertices": verts, "triangles": np.array([[0, 1, 2]]),
             "normals": np.tile(n, (3, 1)), "material": "mtr_test"}]


def _bright_pixels(img) -> int:
    a = np.asarray(img, float) / 255.0
    # Ambient floor is 0.34 * 0.55 ~= 0.19; the backdrop is 0.06.
    return int((a.max(axis=2) > 0.12).sum())


CENTER = np.array([0.33, 0.0, 0.33])


def test_front_face_survives_culling():
    m = _tri(front=True)
    on = pt.render(m, {}, "front", 64, 40.0, CENTER, cull=True)
    off = pt.render(m, {}, "front", 64, 40.0, CENTER, cull=False)
    assert _bright_pixels(on) > 50
    assert _bright_pixels(off) > 50


def test_back_face_dropped_only_when_culling():
    m = _tri(front=False)
    on = pt.render(m, {}, "front", 64, 40.0, CENTER, cull=True)
    off = pt.render(m, {}, "front", 64, 40.0, CENTER, cull=False)
    assert _bright_pixels(on) == 0      # culled -> backdrop only
    assert _bright_pixels(off) > 50     # both sides drawn -> visible


def test_culling_is_view_relative():
    # The same front-facing triangle must be culled from the *back* view,
    # proving the sign is tied to the camera, not a fixed world axis.
    m = _tri(front=True)
    back = pt.render(m, {}, "back", 64, 40.0, CENTER, cull=True)
    assert _bright_pixels(back) == 0
