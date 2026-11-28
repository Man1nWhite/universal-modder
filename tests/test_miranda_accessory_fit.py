"""Geometry-level guardrails for Miranda's measured accessory fit (D100)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_joy_head_mods as heads  # noqa: E402


def test_clearance_warp_preserves_collar_and_moves_upper_head_together():
    # Duplicate positions stand for a face/scalp seam; both must stay welded.
    p = np.array([[1., 10., 156.], [3., 17., 174.], [3., 17., 174.],
                  [0., 18., 186.]], dtype=np.float64)
    n = np.tile([0., 1., 0.], (len(p), 1))
    result, normals = heads.fit_l4d2_accessory_clearance(p, n)
    np.testing.assert_array_equal(result[0], p[0])
    np.testing.assert_array_equal(result[1], result[2])
    assert 0.35 < p[1, 1] - result[1, 1] < 0.45
    assert p[3, 1] - result[3, 1] > 1.0
    assert 0.7 < p[3, 2] - result[3, 2] < 0.8
    np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1.0, atol=1e-6)


def test_warp_normals_match_the_inverse_transpose_of_local_surface():
    # Independently differentiate the position warp, at the neck and crown ramps.
    for point in ([2., 11., 161.], [3., 17., 174.], [2., 16., 181.5]):
        p = np.array([point], dtype=np.float64)
        normal = np.array([[0.3, 0.4, 0.866025403784]])
        _, transformed = heads.fit_l4d2_accessory_clearance(p, normal)
        eps = 0.01  # outputs are float32
        columns = []
        for axis in range(3):
            step = np.zeros((1, 3)); step[0, axis] = eps
            plus, _ = heads.fit_l4d2_accessory_clearance(p + step, normal)
            minus, _ = heads.fit_l4d2_accessory_clearance(p - step, normal)
            columns.append((plus[0] - minus[0]) / (2 * eps))
        jacobian = np.column_stack(columns)
        expected = np.linalg.solve(jacobian.T, normal[0])
        expected /= np.linalg.norm(expected)
        np.testing.assert_allclose(transformed[0], expected, atol=0.001)


def test_face_front_tuck_clamps_to_hila_envelope_but_never_moves_the_face_shell():
    # The brow sat 0.3-0.9 cm in front of vanilla Hila's forehead, where the
    # eyewear frames were authored to sit: it is clamped to her envelope + 5 mm.
    # The face shell ends at |x| 6.68; past the tuck corridor only the base
    # setback may act on it (a stretched temple skin pokes through the hair).
    p = np.array([[1.5, 18.3, 176.5], [6.68, 8.91, 172.41]], dtype=np.float64)
    n = np.tile([0.0, 1.0, 0.0], (len(p), 1))
    result, _ = heads.fit_l4d2_accessory_clearance(p, n)
    assert 17.55 < result[0, 1] < 17.85, f"brow clamped to {result[0, 1]:.2f}"
    assert abs(result[0, 0] - 0.96 * 1.5) < 1e-3, "x sees only the base -4%"
    assert abs(result[1, 0] - 0.96 * 6.68) < 1e-3, "face shell was x-warped"
    assert abs(result[1, 1] - (8.91 - 0.35 - 0.03 * (8.91 - 15.70))) < 1e-3


def test_side_floors_put_the_hair_outside_the_eyewear_arm_corridor():
    # The arm rides outside Hila's ear (outer edge |x| <= 10.55) and crosses the
    # temple sweep at |x| ~7-8.6; the floors clamp the hair sheets outside it.
    p = np.array([[7.9, 13.5, 175.5], [9.0, 2.5, 168.0], [6.4, 16.8, 177.0]],
                 dtype=np.float64)
    n = np.tile([0.0, 1.0, 0.0], (len(p), 1))
    result, _ = heads.fit_l4d2_accessory_clearance(p, n)
    assert abs(result[0, 0]) >= 9.4, f"temple sweep at {result[0, 0]:.2f}"
    assert 10.55 < abs(result[1, 0]) < 10.65, f"jaw curtain at {abs(result[1, 0]):.2f}"
    assert abs(result[2, 0] - 0.96 * 6.4) < 1e-3, "fringe edge below the gate was moved"


def test_eye_bundle_rides_the_base_setback_only():
    # Eyeballs, teeth and lashes skip the envelope clamps: clamping a lash to
    # the same sheet as the tucked lid sinks it into the lid.
    p = np.array([[4.07, 17.65, 174.24]], dtype=np.float64)
    n = np.tile([0.0, 1.0, 0.0], (len(p), 1))
    base, _ = heads.fit_l4d2_accessory_clearance(p, n, fit_envelope=False)
    fitted, _ = heads.fit_l4d2_accessory_clearance(p, n)
    assert abs((p[0, 1] - base[0, 1]) - (0.35 + 0.03 * (17.65 - 15.70))) < 1e-3
    assert abs(base[0, 0] - 0.96 * 4.07) < 1e-3
    assert fitted[0, 1] < base[0, 1] - 0.1, "the lash point must differ from the tucked one"
