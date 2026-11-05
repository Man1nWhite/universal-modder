"""`redress_from_source`: re-dress the garment on the shipped body.

The pass is what fixes the bare shoulders: the retarget drags the blazer's
neckline out over the trapezius, so the garment is rebuilt on the body we ship
at the *source's* garment-to-body clearance. These tests pin the arithmetic on a
synthetic cylinder body whose correspondence is exact by construction.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402

N = 32                      # vertices per ring
RINGS = 16                  # rings up the body
R_SRC = 10.0                # source body radius
CLEARANCE = 2.0             # source garment clearance along the body normal
GROW = 1.2                  # the shipped body is 20 % larger than the source


def _cyl(radius: float, height: float, z0: float = 0.0):
    """Closed-tube ring stack: positions, triangles (CCW outward)."""
    pos = []
    for r in range(RINGS):
        z = z0 + height * r / (RINGS - 1)
        for i in range(N):
            a = 2.0 * math.pi * i / N
            pos.append((radius * math.cos(a), radius * math.sin(a), z))
    tris = []
    for r in range(RINGS - 1):
        for i in range(N):
            j = (i + 1) % N
            a, b = r * N + i, r * N + j
            c, d = (r + 1) * N + i, (r + 1) * N + j
            tris += [a, d, c, a, b, d]      # outward-facing winding
    return pos, tris


def _radial(pos):
    return [math.hypot(x, y) for x, y, _z in pos]


def _fake_model(body_pos, body_tris, garment_pos, garment_tris):
    """A `ModelData`-shaped stub: meshes + world vertices with normals."""
    verts = []

    def add(p):
        norm = list(p)
        norm[2] = 0.0
        ln = math.hypot(norm[0], norm[1]) or 1.0
        verts.append(SimpleNamespace(pos=tuple(p),
                                     normal=(norm[0] / ln, norm[1] / ln, 0.0),
                                     weights=[], uv=(0.0, 0.0)))
        return len(verts) - 1

    def mesh(material, pos, tris):
        remap = {}
        idx = []
        for k in range(0, len(tris), 3):
            a, b, c = tris[k], tris[k + 2], tris[k + 1]   # the loader's b/c swap
            for g in (a, b, c):
                if g not in remap:
                    remap[g] = add(pos[g])
                idx.append(remap[g])
        return SimpleNamespace(material=material, triangle_indices=idx)

    return SimpleNamespace(meshes=[mesh("skin", body_pos, body_tris),
                                   mesh("jacket", garment_pos, garment_tris)],
                           vertices=verts)


def _first_appearance(tris):
    """The order ``transfer_group``/``_slice_vertex_order`` give a slice."""
    order, seen = [], set()
    for k in range(0, len(tris), 3):
        a, b, c = tris[k], tris[k + 2], tris[k + 1]
        for vi in (a, b, c):
            if vi not in seen:
                seen.add(vi)
                order.append(vi)
    return order


def _fake_group(body_pos, body_tris, garment_pos, garment_tris):
    """A `Group` shaped like the builder's: first-appearance vertex order."""
    g = bm.Group(name="body")
    for mat, pos, tris in (("skin", body_pos, body_tris),
                           ("jacket", garment_pos, garment_tris)):
        order = _first_appearance(tris)
        remap = {vi: i for i, vi in enumerate(order)}
        base_v = len(g.verts)
        base_i = len(g.faces) * 3
        g.verts.extend(tuple(pos[vi]) for vi in order)
        faces = [(remap[tris[k]], remap[tris[k + 1]], remap[tris[k + 2]])
                 for k in range(0, len(tris), 3)]
        g.faces.extend((a + base_v, b + base_v, c + base_v) for a, b, c in faces)
        g.uvs.extend([(0.0, 0.0)] * len(order))
        g.normals.extend([tuple(pos[vi]) for vi in order])
        g.weights.extend([[(0, 1.0)]] * len(order))
        g.slices.append((mat, base_v, base_i, len(faces), len(order)))
    return g


def _scene(built_garment_radius: float):
    body_pos, body_tris = _cyl(R_SRC, 20.0)
    garment_pos, garment_tris = _cyl(R_SRC + CLEARANCE, 20.0)
    model = _fake_model(body_pos, body_tris, garment_pos, garment_tris)

    b_body, _ = _cyl(R_SRC * GROW, 20.0 * GROW)
    b_garment, _ = _cyl(built_garment_radius, 20.0 * GROW)
    return model, _fake_group(b_body, body_tris, b_garment, garment_tris)


def test_redress_restores_the_source_clearance():
    """A garment that drifted out is pulled back to the source's clearance."""
    model, g = _scene(built_garment_radius=R_SRC * GROW + 8.0)   # 8 cm too far out

    rep = bm.redress_from_source(g, model, verbose=False)

    jacket = next(s for s in g.slices if s[0] == "jacket")
    _mat, base_v, _bi, _tris, nv = jacket
    radii = _radial(g.verts[base_v:base_v + nv])
    expect = GROW * (R_SRC + CLEARANCE)
    # the k=6 neighbour blend averages surface points, so a coarse fixture reads
    # a little inside the exact radius; 0.2 cm bounds that on this resolution.
    assert rep["moved"] == nv
    assert rep["scale"] == pytest.approx(GROW, rel=0.02)
    assert max(abs(r - expect) for r in radii) < 0.2


def test_redress_only_touches_garment_positions():
    """Topology, UVs, weights and the body itself must be untouched."""
    model, g = _scene(built_garment_radius=R_SRC * GROW + 8.0)
    faces = list(g.faces)
    uvs = list(g.uvs)
    weights = [list(w) for w in g.weights]
    body_before = list(g.verts[:g.slices[0][4]])

    bm.redress_from_source(g, model, verbose=False)

    assert g.faces == faces
    assert g.uvs == uvs
    assert g.weights == weights
    assert g.verts[:len(body_before)] == body_before


def test_redress_clamps_apparent_displacement():
    """A vertex that would fly more than ``max_move`` stays where it is."""
    model, g = _scene(built_garment_radius=R_SRC * GROW + 8.0)

    rep = bm.redress_from_source(g, model, max_move=1.0, verbose=False)

    assert rep["moved"] == 0
    assert rep["peak"] <= 1.0


def test_redress_refuses_a_body_it_cannot_map():
    """The correspondence is the whole premise: fail loudly when it breaks."""
    model, g = _scene(built_garment_radius=R_SRC * GROW + 8.0)
    g.slices[0] = ("skin", 0, 0, 4, 6)      # half the body

    with pytest.raises(SystemExit):
        bm.redress_from_source(g, model, verbose=False)
