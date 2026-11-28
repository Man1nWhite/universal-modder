"""Geometry-level guardrails for Miranda's unverified accessory-fit trial."""
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
