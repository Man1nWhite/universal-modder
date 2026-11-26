"""The supplied Arivus atlas is shipped without recompressing its BC3 base level."""
from __future__ import annotations

import io
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_joy_head_mods as builder  # noqa: E402


def test_pack_uses_supplied_bc3_base_and_complete_cutout_mips():
    source = builder.ARIVUS_DIFFUSE.read_bytes()
    prefix = 'Arivus over Hoxton/units/payday2/characters/shared_textures/'
    with zipfile.ZipFile(ROOT / 'dist/Arivus/Arivus_over_Hoxton.zip') as z:
        diffuse = z.read(prefix + 'old_hoxton_head_df.texture')
        assert z.read(prefix + 'old_hoxton_head_p_df.texture') == diffuse
    assert diffuse[:4] == b'DDS ' and diffuse[84:88] == b'DXT5'
    assert struct.unpack_from('<I', diffuse, 28)[0] == 12
    assert len(diffuse) == 128 + sum(max(1, (2048 >> i) // 4) ** 2 * 16 for i in range(12))
    assert diffuse[128:128 + 2048 * 2048] == source[128:]
    with Image.open(io.BytesIO(diffuse)) as image:
        actual = np.array(image)
    with Image.open(io.BytesIO(source)) as image:
        expected = np.array(image)
    assert np.array_equal(actual, expected)
    assert np.all(actual[:1024, :, 3] >= 15)
    assert set(np.unique(actual[1024:, :, 3])) == {0, 24}


def test_rejects_wrong_atlas_format_and_truncation(tmp_path):
    source = builder.ARIVUS_DIFFUSE.read_bytes()
    bad = tmp_path / 'bad.dds'
    for payload in (source[:-1], source[:84] + b'DXT1' + source[88:]):
        bad.write_bytes(payload)
        with pytest.raises(ValueError, match='single-level'):
            builder.load_arivus_diffuse(bad)


def test_rejects_invalid_base_payload_size():
    with pytest.raises(ValueError, match='base level'):
        builder.encode_cutout_head_df_dds(np.zeros((8, 8, 4), dtype=np.uint8), b'bad')
