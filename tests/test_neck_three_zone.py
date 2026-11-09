"""Three-zone neck artifact: unslimmed rim, rejected opening, mis-normalled cap.

Every fixture here is synthetic. The real geometry came from the deleted Skyrim
3BA sources (``docs/skyrim-nif/STATUS.md``), so these regressions must be
reproducible from code alone. The fixtures are built at the measurements the
pass docstrings record, so a change that breaks the geometry contract breaks
these tests.

Each test guards exactly one mechanism:

* zone 1 — ``slim_neck``'s radial mask must reach the rim, and must be centred
  on the rim, not on the PD2 axis;
* zone 2 — ``cap_holes`` must admit a real opening (centroid z gate, in-plane
  diameter) and must not mistake a UV seam for one;
* zone 3 — the cap's stored vertex normal must be the fan's own plane normal;
  the old ``sum(normals) / ||sum||`` produces a vector 90 degrees off its own
  facets on every round rim, which is what shades as a shelf.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402

AXIS = (0.0, 9.5)          # documented 3BA neck axis (align_neck docstring)
SEG = 32


def _tube(half_width, zs, tilt=0.0, axis=AXIS, seg=SEG):
    """An open-topped neck tube, bottom fan-closed so only the top is open."""
    verts, rows = [], []
    for z in zs:
        row = []
        for k in range(seg):
            th = 2.0 * math.pi * k / seg
            r = half_width(z)
            verts.append((axis[0] + r * math.sin(th),
                          axis[1] + r * math.cos(th),
                          z + tilt * math.cos(th)))
            row.append(len(verts) - 1)
        rows.append(row)
    faces = []
    for zi in range(len(rows) - 1):
        a, b = rows[zi], rows[zi + 1]
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((a[k], a[k2], b[k2]))
            faces.append((a[k], b[k2], b[k]))
    cb = len(verts)
    verts.append((axis[0], axis[1], zs[0] - 0.01))
    for k in range(seg):
        faces.append((rows[0][(k + 1) % seg], rows[0][k], cb))
    return np.asarray(verts, float), faces


def _group(verts, faces, normal=(0.0, 0.0, 1.0)):
    g = bm.Group(name="body")
    g.verts = [tuple(map(float, p)) for p in verts]
    g.uvs = [(0.0, 0.0)] * len(verts)
    g.normals = [tuple(normal)] * len(verts)
    g.weights = [[(0, 1.0)]] * len(verts)
    g.faces = [tuple(map(int, t)) for t in faces]
    g.slices = [("skin", 0, 0, len(faces), len(verts))]
    g.mat_slots = ["mtr_body"]
    return g


def retargeted_3ba():
    """18.8 cm diameter at 167 (slim_neck docstring), 12 cm half-width at the 157
    stop, and the source's diagonal opening cut."""
    zs = [150, 153, 156, 157, 159, 161, 163, 165, 167]

    def hw(z):
        if z <= 157.0:
            return 12.0
        return 12.0 + (9.4 - 12.0) * (z - 157.0) / 10.0

    return _tube(hw, zs, tilt=1.5)


def top_ring(g):
    """(ring, P) of the highest boundary loop."""
    best = None
    for loop in bm.boundary_loops(g.faces):
        idx = [i for i in loop if i < len(g.verts)]
        if len(idx) < 3:
            continue
        ring = idx[:-1] if len(idx) > 3 and idx[0] == idx[-1] else idx
        P = np.asarray([g.verts[i] for i in ring], float)
        if best is None or P[:, 2].max() > best[0]:
            best = (P[:, 2].max(), ring, P)
    return best[1], best[2]


def rim_half_width(P):
    return float(np.hypot(P[:, 0] - P[:, 0].mean(), P[:, 1] - P[:, 1].mean()).mean())


def bbox_span(P):
    return float(np.linalg.norm(P.max(axis=0) - P.min(axis=0)))


def planar_diameter(P):
    c = P.mean(axis=0)
    Q = P - c
    _, _, vt = np.linalg.svd(Q, full_matrices=False)
    n = vt[2]
    Q = Q - np.outer(Q @ n, n)
    return float(np.sqrt(((Q[:, None, :] - Q[None, :, :]) ** 2).sum(-1).max()))


def plane_normal(P):
    c = P.mean(axis=0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    n = vt[2]
    return n / (np.linalg.norm(n) or 1.0)


# ------------------------------------------------------------------ zone 1
def test_slim_neck_actually_shrinks_the_rim_to_the_reference():
    """The mask used to be zero at the rim; after the fix the rim lands on 4.70."""
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    _, P = top_ring(g)
    hw = rim_half_width(P)
    assert abs(hw - 4.70) < 0.25, f"rim half-width {hw:.2f} cm, target 4.70"


def test_slim_neck_keeps_the_rim_circular():
    """Measuring about the wrong centre turns the round opening into an ellipse.

    The rim is a circle centred at y=9.5. A radial mask about y=7.0 is stronger
    on the back of the neck than on the front, so the opening comes out
    egg-shaped: 8.39 cm at the front against 7.33 at the back, circularity
    (std(r)/mean(r) about the rim's own centroid) 0.116 against 0.000.
    A shading-visible rim over the collar is exactly this asymmetry.
    """
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    _, P = top_ring(g)
    r = np.hypot(P[:, 0] - P[:, 0].mean(), P[:, 1] - P[:, 1].mean())
    circularity = float(r.std() / r.mean())
    assert circularity < 0.02, (
        f"rim circularity {circularity:.4f}: the opening is not a circle "
        f"(radius {r.min():.2f}-{r.max():.2f} cm)")


def test_bbox_diagonal_inflates_a_circular_opening():
    """The old span gate measured the bbox diagonal, which is sqrt(2) too big."""
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    _, P = top_ring(g)
    assert planar_diameter(P) < 12.0
    assert planar_diameter(P) < bbox_span(P)          # the inflation is real


def test_cap_holes_closes_the_neck_after_slimming():
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    ring, P = top_ring(g)
    added = bm.cap_holes(g, min_z=155.0, slot="mtr_body", max_span=14.0)
    assert added == len(ring), f"cap added {added} tris for a {len(ring)}-vertex ring"


def test_cap_holes_z_gate_uses_the_loop_centre_not_its_lowest_vertex():
    """A diagonally cut opening straddles min_z; its centre must decide."""
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=2.0)
    g = _group(v, f)
    ring, P = top_ring(g)
    centre_z = float(P[:, 2].mean())
    lowest = float(P[:, 2].min())
    assert lowest < centre_z - 1.0                # the fixture really straddles
    added = bm.cap_holes(g, min_z=centre_z - 0.1, slot="mtr_body", max_span=30.0)
    assert added == len(ring), (
        f"a ring centred at {centre_z:.2f} with a low side at {lowest:.2f} "
        f"was rejected against min_z={centre_z - 0.1:.2f}")


def test_cap_vertex_normal_is_the_fan_plane_not_cancelled_rim_normals():
    """The rim's own vertex normals cancel, so the old sum/||sum|| is 90 degrees off."""
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=0.0)
    g = _group(v, f)
    P = np.asarray(g.verts, float)
    # radial (horizontal) vertex normals: they cancel exactly around a round rim
    rad = P - np.array([AXIS[0], AXIS[1], 0.0])
    rad[:, 2] = 0.0
    ln = np.linalg.norm(rad, axis=1, keepdims=True)
    rad = np.divide(rad, np.maximum(ln, 1e-12),
                    out=np.tile([0.0, 0.0, 1.0], (len(P), 1)), where=ln > 1e-9)
    g.normals = [tuple(rad[i]) for i in range(len(g.verts))]

    # capture the ring BEFORE capping: afterwards it is no longer a boundary
    _, Pr = top_ring(g)
    expected = plane_normal(Pr)

    before = len(g.verts)
    added = bm.cap_holes(g, min_z=150.0, slot="mtr_body", max_span=30.0)
    assert added > 0
    stored = np.asarray(g.normals[before], float)

    cos = abs(float(stored @ expected))
    assert cos > 0.99, (
        f"cap normal {np.round(stored, 3)} is {math.degrees(math.acos(min(1, cos))):.1f} "
        f"degrees off the fan plane {np.round(expected, 3)}")


def test_cap_never_ships_a_zero_normal():
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=0.0)
    g = _group(v, f)
    P = np.asarray(g.verts, float)
    rad = P - np.array([AXIS[0], AXIS[1], 0.0])
    rad[:, 2] = 0.0
    ln = np.linalg.norm(rad, axis=1, keepdims=True)
    rad = np.divide(rad, np.maximum(ln, 1e-12),
                    out=np.tile([0.0, 0.0, 1.0], (len(P), 1)), where=ln > 1e-9)
    g.normals = [tuple(rad[i]) for i in range(len(g.verts))]
    before = len(g.verts)
    bm.cap_holes(g, min_z=150.0, slot="mtr_body", max_span=30.0)
    for i in range(before, len(g.normals)):
        assert np.linalg.norm(g.normals[i]) > 0.5, f"cap vertex {i} normal is degenerate"


def test_cap_facets_are_all_wound_the_same_way():
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=2.0)
    g = _group(v, f)
    before = len(g.faces)
    bm.cap_holes(g, min_z=150.0, slot="mtr_body", max_span=30.0)
    V = np.asarray(g.verts, float)
    signs = []
    for t in g.faces[before:]:
        n = np.cross(V[t[1]] - V[t[0]], V[t[2]] - V[t[0]])
        L = np.linalg.norm(n)
        if L > 0:
            signs.append(n[2] / L)
    signs = np.asarray(signs)
    assert (signs > 0).all() or (signs < 0).all(), f"mixed winding {signs}"
    assert np.abs(signs).min() > 0.95, "a facet is nearly edge-on: the fan is a skirt"


