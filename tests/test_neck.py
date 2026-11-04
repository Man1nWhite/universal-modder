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

    rep = bm.slim_neck(g, z_target=None)

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

    bm.slim_neck(g, z_target=None)

    low = 9.0 - g.verts[0][0]
    high = 9.0 - g.verts[1][0]
    assert 0.0 < low < high


def test_slim_neck_leaves_the_garment_alone():
    """Only ``mats`` move: the collar is re-dressed separately, not scaled."""
    g = _group([("skin", [(9.0, 7.0, 162.0)]),
                ("jacket", [(9.0, 7.0, 162.0)])])

    rep = bm.slim_neck(g, z_target=None)

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


def test_slim_neck_ends_the_neck_inside_the_collar():
    """The neck is cut back to the height the collar can actually fit.

    In the Skyrim source the body stops at 157 cm and the head fills the collar's
    opening, so above ~158 cm the garments were never shaped around a neck: the
    port's collar opening is *narrower* than its neck there (z 161: opening
    1.4-3.8 cm from the axis, neck 3.1-4.3), which is why the neck came through
    the collar. The body's neck therefore ends just inside the opening.
    """
    g = _group([("skin", [(0.0, 7.0, 150.0), (3.0, 7.0, 160.0),
                          (3.0, 7.0, 164.0), (3.0, 7.0, 167.0)])])

    rep = bm.slim_neck(g, z_target=160.8, z_ramp=2.0)

    top = max(v[2] for v in g.verts)
    assert top == pytest.approx(160.8, abs=0.05)
    assert rep["dropped"] == pytest.approx(6.2, abs=0.1)
    assert g.verts[0] == (0.0, 7.0, 150.0)      # below the band: untouched
    assert g.verts[1][2] == pytest.approx(159.6125, abs=0.05)  # smooth ramp starts at 159


def test_slim_neck_shortening_only_touches_its_materials():
    """The collar must keep its height: only ``mats`` are cut back."""
    g = _group([("skin", [(3.0, 7.0, 167.0), (20.0, 7.0, 167.0)]),
                ("jacket2", [(3.0, 7.0, 167.0)])])

    bm.slim_neck(g, z_target=160.8)

    assert g.verts[0][2] == pytest.approx(160.8, abs=0.05)
    assert g.verts[1][2] == 167.0          # outer shoulder stays put
    assert g.verts[2][2] == 167.0          # garment remains untouched
