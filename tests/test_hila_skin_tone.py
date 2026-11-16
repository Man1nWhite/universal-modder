"""Romance-over-Hila's tint matches the Honoko body without tinting the eyes or hair."""
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools' / 'pd2-las'))
import build_joy_head_mods as head  # noqa: E402
import render_mod_previews as previews  # noqa: E402
from dist_paths import dist_path  # noqa: E402


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


def test_hila_neck_diffuse_is_closer_to_honoko_than_untinted_romance():
    """Compare RGB medians on the same sampled upper-neck mesh, before and after tint."""
    parts, _ = previews.load_outfit_with_head_parts(
        'Honoko5.zip', 'Honoko5', 'honoko5',
        'Miranda_Romance_over_Hila.zip', 'Miranda Romance over Hila',
        'units/pd2_dlc_ecp/characters/npc_criminals_ecp_female', 'npc_criminal_ecp_female')
    with zipfile.ZipFile(dist_path(ROOT, 'Miranda_Romance_over_Joy.zip')) as z:
        entry = next(n for n in z.namelist() if n.endswith('npc_criminal_joy_1_head_df.texture'))
        untinted = np.asarray(Image.open(io.BytesIO(z.read(entry))).convert('RGBA'))

    def neck_sample(part, tex=None, head_part=False):
        pos, _, tris, uv, texture, _, neg = part
        ids = np.unique(tris)
        pos, uv = pos[ids], uv[ids]
        texture = texture if tex is None else tex
        v = ((-uv[:, 1]) if neg else (1 - uv[:, 1])) % 1
        mask = (pos[:, 2] >= 164) & (pos[:, 2] < 167) & (pos[:, 1] > 2) & (abs(pos[:, 0]) < 3.5)
        if head_part:
            mask &= (uv[:, 0] < .5) | ((uv[:, 0] > .5) & (v > .36) & (v < .5))
        assert mask.sum() >= 10
        colors = texture[(v * (texture.shape[0] - 1)).astype(int),
                         ((uv[:, 0] % 1) * (texture.shape[1] - 1)).astype(int), :3]
        return np.median(colors[mask], axis=0)

    body = neck_sample(parts[0])
    old = neck_sample(parts[-2], untinted, head_part=True)
    new = neck_sample(parts[-2], head_part=True)
    assert np.linalg.norm(body - old) > 20
    assert np.linalg.norm(body - new) < np.linalg.norm(body - old) * .35
    # The compressed hair texture in the upper scalp remains essentially unchanged.
    hair_before = untinted[100:400, 1200:1800, :3].astype(np.int16)
    hair_after = parts[-2][4][100:400, 1200:1800, :3].astype(np.int16)
    assert float(np.abs(hair_before - hair_after).mean()) < 1
