"""Nostril repair must not forcibly darken the visible nose wings."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_joy_head_mods import repair_skin_and_neck_normals  # noqa: E402


def test_nose_wing_keeps_valid_source_normals():
    # This otherwise healthy triangle falls inside the old broad nostril mask.
    # The separate tip point sets its reference position, as on the real mesh.
    face = np.array([[0, 10, 175], [.5, 9, 174.5], [.7, 9, 174.5],
                     [.5, 9, 174.8]], dtype=np.float32)
    face_normals = np.tile([0., 1., 0.], (4, 1))
    face_tris = np.array([[1, 3, 2]], dtype=np.int32)
    scalp = np.array([[10, 0, 160], [11, 0, 160], [10, 0, 161]], dtype=np.float32)
    scalp_normals = np.tile([0., 1., 0.], (3, 1))
    scalp_uv = np.array([[.8, .2], [.9, .2], [.8, .3]], dtype=np.float32)
    scalp_tris = np.array([[0, 2, 1]], dtype=np.int32)
    result, _ = repair_skin_and_neck_normals(face, face_normals, face_tris,
                                              scalp, scalp_normals, scalp_uv, scalp_tris)
    np.testing.assert_allclose(result[1:], face_normals[1:], atol=1e-6)
