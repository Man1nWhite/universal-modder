"""Unit tests for the coincident-normal unification pass (no pack needed).

`unify_coincident_normals` answers the one shading defect the screenshot review
found that survived re-measurement: a PD2 mesh splits a vertex at UV/material
seams, and every copy of one position has to carry the *same* normal or the
seam shades as a hard step. The 2B reference has 22,486 coincident pairs and
none of them diverge; ours had 480 (slim) / 856 (base).

The meshes here are built by hand, so these tests run on a checkout without
`references/Christie.zip`. The shipped-pack counterpart is
`test_christie_las.py::test_interior_coincident_normals_agree`.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

#: one closed triangular prism: 3 bottom + 3 top vertices, 3 side quads split
#: into 6 triangles plus 2 caps. Every edge is shared by two faces, so all six
#: vertices are *interior* - which is exactly the situation two coincident
#: garment layers make in the real mesh.
PRISM = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
         (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0)]
SIDE = [(0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4), (2, 0, 3), (2, 3, 5)]
CAPS = [(0, 2, 1), (3, 4, 5)]


def _layers(caps: bool, tilt: tuple[int, float] | None):
    """Two coincident prisms; `tilt` = (vertex, degrees) on the second copy."""
    import build_models as bm

    faces = SIDE + (CAPS if caps else [])
    verts = [tuple(v) for v in PRISM] + [tuple(v) for v in PRISM]
    all_faces = list(faces) + [tuple(i + 6 for i in f) for f in faces]
    normals = [(0.0, 0.0, 1.0)] * len(verts)
    if tilt is not None:
        vertex, deg = tilt
        a = math.radians(deg)
        normals[vertex + 6] = (0.0, -math.sin(a), math.cos(a))
    # Coincident copies carry *different* UVs - a real UV/material seam,
    # not a redundant split (all copies sharing one UV would be excluded by
    # the "no UV difference" census row).
    uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
           (0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
           (9.0, 9.0), (10.0, 9.0), (9.0, 10.0),
           (9.0, 9.0), (10.0, 9.0), (9.0, 10.0)]
    return bm.Group(name="body", verts=verts, normals=normals,
                    uvs=uvs, faces=all_faces)


def test_the_fixture_is_a_pair_of_closed_layers():
    """Guard the fixture itself: no border edges, six coincident pairs."""
    import build_christie_las as bcl

    g = _layers(caps=True, tilt=None)
    assert len(g.verts) == 12 and len(g.faces) == 16
    assert bcl.coincident_normal_report(g) == {"interior": 0, "border": 0,
                                               "pairs": 0}


def _manifold_seam(tilt=None):
    """Two coincident open triangles sharing all 3 edges: a closed manifold
    UV-seam loop. Each position has exactly two incident faces (one per sheet),
    so no copy sits on a border edge and a diverging stored normal is unified.
    Copy of vertex ``vertex`` (index ``vertex + 3``) is tilted by ``deg``.
    """
    import build_models as bm

    P = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
    verts = [tuple(v) for v in P] + [tuple(v) for v in P]
    faces = [(0, 1, 2), (4, 5, 3)]            # opposite winding on the shared edge
    normals = [(0.0, 0.0, 1.0)] * 6
    if tilt is not None:
        vertex, deg = tilt
        a = math.radians(deg)
        normals[vertex + 3] = (0.0, -math.sin(a), math.cos(a))
    # Coincident copies carry *different* UVs - a real UV seam, not a
    # redundant split (all copies sharing one UV would be excluded by the
    # "no UV difference" census row).
    uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
           (9.0, 9.0), (10.0, 9.0), (9.0, 10.0)]
    return bm.Group(name="body", verts=verts, normals=normals,
                    uvs=uvs, faces=faces)


def test_interior_duplicate_normals_are_unified():
    """A diverging *interior* coincident pair on a manifold UV seam is
    rewritten so both copies agree."""
    import build_christie_las as bcl

    g = _manifold_seam(tilt=(1, 45.0))        # copy of vertex 1 (index 4), 45 deg off
    rep = bcl.unify_coincident_normals(g)
    assert rep["groups"] == 1, rep
    assert bcl.coincident_normal_report(g)["interior"] == 0

    a = np.asarray(g.normals[1]); b = np.asarray(g.normals[4])
    assert abs(float(np.linalg.norm(b)) - 1.0) < 1e-9     # still unit length
    assert float(a @ b) > math.cos(math.radians(30))


def test_manifold_uv_split_seam_is_unified():
    """A smooth UV seam (opposing 3D half-edges, small face angle) unifies to
    < 1e-6 deg while coincident vertices that already agree are left alone."""
    import build_christie_las as bcl

    g = _manifold_seam(tilt=(1, 40.0))
    before = bcl.coincident_normal_report(g)
    assert before["pairs"] == 1                      # one diverging pair
    bcl.unify_coincident_normals(g)
    after = bcl.coincident_normal_report(g)
    assert after["pairs"] == 0, after                # seam pair unified
    a = np.asarray(g.normals[1]); b = np.asarray(g.normals[4])
    assert abs(float(a @ b) - 1.0) < 1e-6            # copies agree to < 1e-6 deg
    # The agreeing pairs were not touched.
    assert float(np.asarray(g.normals[0]) @ np.asarray(g.normals[3])) > 0.999
    assert float(np.asarray(g.normals[2]) @ np.asarray(g.normals[5])) > 0.999


def test_border_duplicates_keep_their_own_normals():
    """Without the caps the prism's rim is a garment edge: a fold, not a seam."""
    import build_christie_las as bcl

    g = _layers(caps=False, tilt=(1, 90.0))
    keep = np.asarray(g.normals[7], float)
    before = bcl.coincident_normal_report(g)
    assert before["border"] == 1 and before["interior"] == 0, before

    assert bcl.unify_coincident_normals(g) == {"groups": 0, "verts": 0}
    assert np.allclose(g.normals[7], keep)


def test_pairs_already_within_tolerance_are_not_touched():
    """<= 1 degree is under the 1 degree bar: leave the stored normal alone.

    The unification band is 1 < spread <= 120 deg (plan §3.4), so a pair that
    already agrees within 1 deg is left alone; anything above 1 deg is unified.
    """
    import build_christie_las as bcl

    g = _layers(caps=True, tilt=(4, 0.5))
    keep = np.asarray(g.normals[10], float)
    assert bcl.unify_coincident_normals(g) == {"groups": 0, "verts": 0}
    assert np.allclose(g.normals[10], keep)


@pytest.mark.parametrize("angle", (130.0, 170.0, 180.0, -180.0))
def test_opposed_copies_have_no_mean_and_are_skipped(angle):
    """Beyond 120 degrees the mean sits >60 deg from both: change neither."""
    import build_christie_las as bcl

    g = _layers(caps=True, tilt=(2, angle))
    keep = np.asarray(g.normals[8], float)
    assert bcl.unify_coincident_normals(g) == {"groups": 0, "verts": 0}
    assert np.allclose(g.normals[8], keep)


@pytest.mark.parametrize("angle", (60.0, 100.0, 120.0))
def test_wide_but_averageable_pairs_are_unified(angle):
    """Up to 120 degrees one normal still stands within 60 deg of both sides.

    The shipped meshes peak at 101 (slim) / 103 (base) degrees, so this is the
    band the real pass works in. A manifold seam (not a closed layer) unifies.
    """
    import build_christie_las as bcl

    g = _manifold_seam(tilt=(2, angle))
    assert bcl.unify_coincident_normals(g)["groups"] == 1
    assert bcl.coincident_normal_report(g)["interior"] == 0
