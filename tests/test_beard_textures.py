"""`tools/extract_beard_textures.py`: Geralt's beard, cut out of the tracked head atlas.

The beard is a rectangle of `Geralt_over_Rust.zip`'s 2048x2048 head atlas, not a
texture of its own: rows 1024..1536, columns 1024..2048 of
`npc_criminal_wild_1_head_df.texture` (colour, with the hair's cutout in alpha) and
of `_nm` (Diesel's packed normal layout). The tool writes those two rectangles out
as PNG and DXT5 DDS under `references/textures/`, so another mod or another engine
can use Geralt's beard without the rest of his head.

The files are read back against the pack they came from, not against a stored
copy: if the atlas is rebuilt the crops must be regenerated, and this says so.
"""
from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
sys.path.insert(0, str(REPO / "tools" / "pd2-port"))

import extract_beard_textures as beard  # noqa: E402

TEXTURES = REPO / "references" / "textures"

pytestmark = pytest.mark.skipif(
    not beard.DEFAULT_PACK.is_file(),
    reason="the tracked Geralt pack is missing; restore it with `git checkout -- dist`")

#: `(name, the atlas it is cut from)`, in the order the tool writes them
CROPS = (("geralt_beard_df", "df"), ("geralt_beard_nm", "nm"))


@pytest.fixture(scope="module")
def written(tmp_path_factory) -> Path:
    """The four files, written fresh into a temporary folder once for this module."""
    out = tmp_path_factory.mktemp("beard")
    beard.write_outputs(beard.DEFAULT_PACK, out)
    return out


@pytest.mark.parametrize("name,atlas", CROPS)
def test_the_png_is_the_rectangle_of_the_atlas(name, atlas, written):
    """Colour pixel for pixel, and the alpha as the 0/255 cutout the atlas expresses as 24."""
    got = np.asarray(Image.open(written / f"{name}.png").convert("RGBA"))
    source = beard.crop(beard.read_atlas(beard.DEFAULT_PACK, atlas))
    assert got.shape == (512, 1024, 4)
    assert np.array_equal(got[..., :3], source[..., :3])
    if atlas == "df":
        # the atlas' alpha is the material's cutout: 24 under a hair, 0 off one
        assert set(np.unique(source[..., 3]).tolist()) == {0, 24}
        assert np.array_equal(got[..., 3] == 255, source[..., 3] > 12)
        assert set(np.unique(got[..., 3]).tolist()) == {0, 255}
    else:
        # a normal map keeps X in alpha and Y in green, red 255 and blue 0, as the pack
        # writes it (`tests/test_pd2_las_invariants.py` holds the packs to the same rule)
        assert np.array_equal(got, source)
        assert set(np.unique(got[..., 0]).tolist()) == {255}
        assert set(np.unique(got[..., 2]).tolist()) == {0}


@pytest.mark.parametrize("name,_atlas", CROPS)
def test_the_dds_is_a_full_pyramid_of_the_same_picture(name, _atlas, written):
    """Its own header for 1024x512, every level there, and level 0 decodes to the PNG.

    `dds.pack_dds` assumes a square texture, so the tool writes this header itself;
    a wrong pitch or mip count shows here as a payload that does not add up, and a
    wrong block order as a level 0 that is not the picture.
    """
    raw = (written / f"{name}.dds").read_bytes()
    assert raw[:4] == b"DDS "
    height, width, pitch = struct.unpack_from("<3I", raw, 12)
    mips = struct.unpack_from("<I", raw, 28)[0]
    assert (height, width, mips) == (512, 1024, 11)
    assert struct.unpack_from("<4s", raw, 84)[0] == b"DXT5"
    expected = 0
    level = (height, width)
    for _ in range(mips):
        expected += max(1, level[0] // 4) * max(1, level[1] // 4) * 16
        level = (max(1, level[0] // 2), max(1, level[1] // 2))
    assert pitch == max(1, height // 4) * max(1, width // 4) * 16
    assert len(raw) - 128 == expected
    decoded = np.asarray(Image.open(io.BytesIO(raw)).convert("RGBA"))
    png = np.asarray(Image.open(written / f"{name}.png").convert("RGBA"))
    # DXT5 is lossy: the colour of every texel within a few steps, and the cutout the same
    assert np.abs(decoded[..., :3].astype(int) - png[..., :3].astype(int)).mean() < 6.0
    if name.endswith("_df"):
        assert np.array_equal(decoded[..., 3] > 128, png[..., 3] > 128)


def test_what_is_tracked_is_what_the_tool_writes(written):
    """The files under `references/textures/` are the tracked pack's crops, byte for byte.

    They are inputs for other work, so they are committed; this is what keeps a
    rebuild of the Geralt pack from leaving them describing an atlas that is gone.
    """
    missing = [f"{name}{suffix}" for name, _ in CROPS for suffix in (".png", ".dds")
               if not (TEXTURES / f"{name}{suffix}").is_file()]
    assert not missing, f"not in the tree: {missing}; run python tools/extract_beard_textures.py"
    for name, _ in CROPS:
        for suffix in (".png", ".dds"):
            tracked = (TEXTURES / f"{name}{suffix}").read_bytes()
            assert tracked == (written / f"{name}{suffix}").read_bytes(), (
                f"{name}{suffix} is stale: run python tools/extract_beard_textures.py")


def test_the_tool_only_reads_the_pack():
    """It writes into references/textures/ and touches nothing in dist/."""
    source = (REPO / "tools" / "extract_beard_textures.py").read_text(encoding="utf-8")
    assert "zipfile.ZipFile(pack)" in source and 'write("' not in source
    assert "dist/" in source and "DEFAULT_OUT = ROOT / \"references\" / \"textures\"" in source
    assert (beard.DEFAULT_OUT / "geralt_beard_df.png").parent == TEXTURES
