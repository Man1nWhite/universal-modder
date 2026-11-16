"""Sleeve gloss retouch: wrap handling, BC3 isolation and the real build."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools/pd2-las'), str(ROOT / 'tools/pd2-port')]
import christie_sleeve_gloss as gloss  # noqa: E402
import dds as dds  # noqa: E402
import dds_encode as enc  # noqa: E402


def uvs(points):
    return [(u, 1 - v) for u, v in points]


def block_bytes(data, level):
    off, w, h = enc.bc3_levels(data)[level]
    size = ((w + 3) // 4) * ((h + 3) // 4) * 16
    return np.frombuffer(data[off:off + size], dtype=np.uint8).reshape(-1, 16)


def test_raster_wraps_both_u_and_v_edges_without_painting_the_middle():
    tri = uvs([(0.98, 0.98), (0.02, 0.99), (0.99, 0.02)])
    coverage = gloss.rasterize(tri, [(0, 1, 2)], 128, max_span=0.12)
    assert coverage[:4, :4].any()
    assert coverage[-4:, -4:].any()
    assert coverage[:4, -4:].any()
    assert coverage[-4:, :4].any()
    assert not coverage[20:108, 20:108].any()


def test_feather_wraps_across_edges_and_stays_inside_hard_mask():
    hard = np.zeros((32, 32), dtype=np.uint8)
    hard[10:20, :3] = 255
    hard[10:20, -3:] = 255
    wrapped = gloss.feather_coverage(hard)
    assert np.all(wrapped[hard == 0] == 0)
    # Translating the periodic mask across the seam must translate its feather.
    shifted = gloss.feather_coverage(np.roll(hard, 8, axis=1))
    np.testing.assert_array_equal(np.roll(wrapped, 8, axis=1), shifted)


def test_long_uv_spans_are_rejected_for_sleeves_not_for_protection():
    tri = uvs([(0.10, 0.10), (0.40, 0.10), (0.10, 0.40)])
    assert not gloss.rasterize(tri, [(0, 1, 2)], 128, max_span=0.12).any()
    assert gloss.rasterize(tri, [(0, 1, 2)], 128).any()


def test_other_uv_faces_protect_shared_pixels_and_role_isolation():
    triangle = [(0.15, 0.15), (0.22, 0.15), (0.15, 0.22)]
    group = SimpleNamespace(
        palette=['LeftForeArm', 'Hips'],
        uvs=uvs(triangle + triangle + triangle),
        weights=[[(0, 1.0)]] * 3 + [[(1, 1.0)]] * 3 + [[(0, 1.0)]] * 3,
        faces=[(0, 1, 2), (3, 4, 5), (6, 7, 8)],
        slices=[('shared', 0, 0, 2, 6), ('other', 6, 6, 1, 3)],
    )
    masks = gloss.masks(group, {'shared': 'shared', 'other': 'other'}, {'shared': 128, 'other': 128})
    sleeve, protected = masks['shared']
    assert (sleeve > 0).any()
    assert np.all(protected[sleeve > 0])
    assert masks['other'][0].any()
    assert not masks['other'][1].any()


def test_retouch_excludes_shared_bc3_blocks_and_preserves_rgb_at_every_mip():
    size = 32
    y, x = np.indices((size, size))
    rgba = np.stack(((x * 7) % 256, (y * 5) % 256, (x + y) * 3, 100 + (x % 80)), axis=2).astype(np.uint8)
    original = dds.pack_dds(dds.mip_payloads_from_image(rgba), size)
    mask = np.ones((size, size), dtype=np.float64)
    protected = np.zeros((size, size), dtype=bool)
    protected[4:8, 4:8] = True
    maps = {'test_suit_df.texture': original}
    report = gloss.retouch(maps, {'suit': (mask, protected)}, dds, prefix='test')['suit']
    updated = maps['test_suit_df.texture']
    assert report['modified_blocks'] > 0
    assert not dds.validate_dxt5_texture(updated)
    old0, new0 = block_bytes(original, 0), block_bytes(updated, 0)
    assert np.array_equal(old0[9], new0[9])  # block (1,1) intersects protected texels
    assert np.any(old0[0, :8] != new0[0, :8])
    for level in range(size.bit_length()):
        assert np.array_equal(block_bytes(original, level)[:, 8:], block_bytes(updated, level)[:, 8:])
    _, _, mip0 = dds.dds_mip0_slice(updated)
    regenerated = dds.mip_payloads_from_mip0(bytes(mip0), size)
    for level in range(1, len(regenerated)):
        expected = np.frombuffer(regenerated[level], dtype=np.uint8).reshape(-1, 16)
        np.testing.assert_array_equal(block_bytes(updated, level)[:, :8], expected[:, :8])


def test_all_protected_leaves_texture_byte_identical():
    rgba = np.full((16, 16, 4), 100, dtype=np.uint8)
    original = dds.pack_dds(dds.mip_payloads_from_image(rgba), 16)
    maps = {'test_suit_df.texture': original}
    report = gloss.retouch(maps, {'suit': (np.ones((16, 16)), np.ones((16, 16), dtype=bool))},
                           dds, prefix='test')['suit']
    assert report['modified_blocks'] == 0
    assert maps['test_suit_df.texture'] == original


def test_real_pack_changes_only_safe_mip0_blocks_and_matches_its_report():
    archive = ROOT / 'dist/Christie/Christie_LAS.zip'
    source = ROOT / 'references/Christie.zip'
    import build_models as bm
    if not archive.is_file() or not source.is_file() or not (bm.DEFAULT_TEMPLATES / '2b.model').is_file():
        pytest.skip('Christie pack, source and 2B templates are required')
    import build_christie_source as builder
    import christie_fit_probe as fit

    _, _, body, _, _, _, _ = fit.geometry()
    baseline = builder.textures()
    sizes = {role: dds.dds_mip0_slice(baseline[f'christie_{role}_df.texture'])[0]
             for role in builder.ROLES.values()}
    masks = gloss.masks(body, builder.ROLES, sizes)
    with zipfile.ZipFile(archive) as z:
        info = json.loads(z.read('Christie_LAS/BUILD_INFO.json'))
        assert info['runtime_verified'] is False
        actual = info['fit_probe']['sleeve_gloss']
        assert actual['c02_01']['modified_blocks'] > 0
        for role, (mask, protected) in masks.items():
            prefix = 'Christie_LAS/assets/units/christie/skins/christie/'
            original = baseline[f'christie_{role}_df.texture']
            updated = z.read(prefix + f'christie_{role}_df.texture')
            assert hashlib.sha256(z.read(prefix + f'christie_{role}_nm.texture')).digest() == hashlib.sha256(
                baseline[f'christie_{role}_nm.texture']).digest()
            old0, new0 = block_bytes(original, 0), block_bytes(updated, 0)
            changed = np.any(old0[:, :8] != new0[:, :8], axis=1)
            blocks = sizes[role] // 4
            blocked = protected.reshape(blocks, 4, blocks, 4).any(axis=(1, 3)).reshape(-1)
            strength = mask.reshape(blocks, 4, blocks, 4).mean(axis=(1, 3)).reshape(-1)
            assert not (changed & (blocked | (strength <= 0.004))).any()
            assert int(changed.sum()) == actual[role]['modified_blocks']
            for level in range(sizes[role].bit_length()):
                assert np.array_equal(block_bytes(original, level)[:, 8:], block_bytes(updated, level)[:, 8:])
            if changed.any():
                _, _, mip0 = dds.dds_mip0_slice(updated)
                regenerated = dds.mip_payloads_from_mip0(bytes(mip0), sizes[role])
                for level in range(1, len(regenerated)):
                    expected = np.frombuffer(regenerated[level], dtype=np.uint8).reshape(-1, 16)
                    np.testing.assert_array_equal(block_bytes(updated, level)[:, :8], expected[:, :8])
            else:
                assert updated == original
