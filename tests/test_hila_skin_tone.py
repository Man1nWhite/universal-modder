"""Romance-over-Hila's tint matches the Honoko body without tinting the eyes or hair."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools' / 'pd2-las'))
import build_joy_head_mods as head  # noqa: E402


def test_skin_tint_preserves_dark_details_other_quadrants_and_gloss():
    atlas = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas[..., 3] = 37
    atlas[10, 10, :3] = [170, 134, 107]       # facial skin
    atlas[10, 1030, :3] = [20, 15, 12]       # dark scalp hair
    atlas[1010, 1030, :3] = [170, 134, 107]  # scalp neck skin
    atlas[1030, 1030, :3] = [170, 134, 107]  # eye quadrant: untouched
    result = head.match_romance_hila_skin_to_honoka(atlas)
    assert result[10, 10, :3].tolist() == [204, 153, 126]
    assert result[1010, 1030, :3].tolist() == [204, 153, 126]
    assert np.array_equal(result[10, 1030], atlas[10, 1030])
    assert np.array_equal(result[1024:], atlas[1024:])
    assert np.array_equal(result[..., 3], atlas[..., 3])
    assert atlas[10, 10, :3].tolist() == [170, 134, 107]  # no mutation
