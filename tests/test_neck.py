"""Neck fixes: `slim_neck` and `tuck_necklace_chain`.

Both are small, position-only passes aimed at the neck, which the PD2 rig makes
look wrong: the retarget's axial spine stretch turns the 3BA neck stub into an
18.8 cm wide column that no collar can close over, and the necklace's chain loop
then rides over the collar's top edge as a gold hoop.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402

AXIS = (0.0, 7.0)


def _group(rows):
    """A body Group with ``rows`` = [(material, [(x, y, z), ...]), ...]."""
    g = bm.Group(name="body")
    for mat, pts in rows:
        base_v = len(g.verts)
        g.verts.extend(pts)
        g.uvs.extend([(0.0, 0.0)] * len(pts))
        g.normals.extend([(0.0, 0.0, 1.0)] * len(pts))
        g.weights.extend([[(0, 1.0)]] * len(pts))
        g.slices.append((mat, base_v, len(g.faces) * 3, 0, len(pts)))
    return g


def test_slim_neck_narrows_only_the_column():
    """Shoulder-line vertices (r > r_stop) and everything below z_lo stay put."""
    g = _group([("skin", [
        (0.0, 7.0, 150.0),      # below the band
        (0.0, 7.0, 157.0),      # exactly at z_lo: untouched
        (9.0, 7.0, 162.0),      # the neck column: narrowed
        (20.0, 7.0, 162.0),     # trapezius, r = 20 > r_stop: untouched
    ])])

    rep = bm.slim_neck(g)

    assert rep["moved"] == 1
    assert g.verts[0] == (0.0, 7.0, 150.0)
    assert g.verts[1] == (0.0, 7.0, 157.0)
    assert 0.0 < g.verts[2][0] < 9.0            # pulled toward the axis
    assert abs(g.verts[2][1] - 7.0) < 1e-9      # stays on the axis in y
    assert abs(g.verts[2][2] - 162.0) < 1e-9    # heights are never touched
    assert g.verts[3] == (20.0, 7.0, 162.0)


def test_slim_neck_ramps_in_with_height():
    """A vertex at the bottom of the ramp moves less than one at the top."""
    g = _group([("skin", [(9.0, 7.0, 158.0), (9.0, 7.0, 162.0)])])

    bm.slim_neck(g)

    low = 9.0 - g.verts[0][0]
    high = 9.0 - g.verts[1][0]
    assert 0.0 < low < high


def test_slim_neck_leaves_the_garment_alone():
    """Only ``mats`` move: the collar is re-dressed separately, not scaled."""
    g = _group([("skin", [(9.0, 7.0, 162.0)]),
                ("jacket", [(9.0, 7.0, 162.0)])])

    rep = bm.slim_neck(g)

    assert rep["moved"] == 1
    assert g.verts[1] == (9.0, 7.0, 162.0)


def test_tuck_necklace_chain_sinks_only_the_loop():
    """Above ``z_min`` the chain is drawn inside the neck; the pendant is not."""
    g = _group([("necklace", [(6.0, 7.0, 150.0), (6.0, 7.0, 160.0)])])

    n = bm.tuck_necklace_chain(g, scale=0.5)

    assert n == 1
    assert g.verts[0] == (6.0, 7.0, 150.0)          # chest chain: untouched
    assert abs(g.verts[1][0] - 3.0) < 1e-9          # loop half the radius
    assert abs(g.verts[1][2] - 160.0) < 1e-9


def test_tuck_necklace_chain_ignores_other_materials():
    g = _group([("skin", [(6.0, 7.0, 160.0)])])

    assert bm.tuck_necklace_chain(g) == 0
    assert g.verts[0] == (6.0, 7.0, 160.0)



def test_slim_neck_preserves_the_full_neck_height():
    """Keep the neck reaching the head; align the outfit rather than cutting it."""
    g = _group([("skin", [(0.0, 7.0, 150.0), (3.0, 7.0, 160.0),
                          (3.0, 7.0, 164.0), (3.0, 7.0, 167.0)])])

    bm.slim_neck(g)

    assert max(v[2] for v in g.verts) == 167.0
    assert g.verts[0] == (0.0, 7.0, 150.0)
    assert g.verts[2][2] == 164.0
    assert g.verts[3][2] == 167.0


def test_turn_upper_body_aligns_neck_but_leaves_legs_upright():
    """Pitch smoothly from the waist, preserving the neck and lower-body line."""
    g = _group([("skin", [(0.0, 2.5, 90.0),   # lower body: unchanged
                          (0.0, 2.5, 98.0),   # pivot: unchanged
                          (0.0, 7.0, 108.0),  # smooth transition
                          (0.0, 7.0, 160.0)])])
    g.normals = [(0.0, 0.0, 1.0)] * len(g.verts)
    lower, pivot, waist, neck = [tuple(v) for v in g.verts]

    n = bm.turn_upper_body(g, deg=1.8)

    assert n == 2
    assert g.verts[0] == lower
    assert g.verts[1] == pivot
    assert g.verts[2][1] < waist[1]        # eased pitch starts at waist
    assert g.verts[3][1] < neck[1]         # neck moves back toward head axis
    assert g.verts[3][2] == pytest.approx(neck[2], abs=0.2)
    assert g.normals[3] != (0.0, 0.0, 1.0)


def test_turn_upper_body_rejects_a_reversed_ramp():
    g = _group([("skin", [(0.0, 0.0, 100.0)])])

    with pytest.raises(ValueError, match="z_full"):
        bm.turn_upper_body(g, z_start=120.0, z_full=110.0)
