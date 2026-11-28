"""`tools/extract_beard_textures.py`: Geralt's beard, read out of the Witcher 3 port's own maps.

The source is `references/characters/Geralt.7z`'s `beard_d.vtf` (colour, with a
smooth alpha) and `beard_n.vtf` (the normal map), both 1024x512. The tool writes
them under `references/textures/` as PNG and DXT5 DDS: the colour's alpha as the
0/255 cutout the game's `alpha_ref` 0.05 material cuts on, the normal map in
Diesel's packed layout (X in alpha, Y in green, 255 in red, 0 in blue).

Those tracked files are build inputs now, not an export: `build_joy_head_mods`
builds `Geralt_over_Rust.zip`'s beard quadrant from the DDS pair. So this file
holds the two together - the tracked textures must be what the tool writes, and
the pack's quadrant must be what the tracked textures say.
"""
from __future__ import annotations

import io
import struct
import sys
import zipfile
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
GERALT_PACK = REPO / "dist" / "Geralt" / "Geralt_over_Rust.zip"
#: the builder's colour factor and its atlas alpha, `build_geralt_rust_mod`
BEARD_GAIN = 0.90
ATLAS_ALPHA = 24

pytestmark = pytest.mark.skipif(
    not beard.DEFAULT_ARCHIVE.is_file(),
    reason="the tracked Witcher 3 port archive is missing; restore it with `git checkout -- references`")

#: `(name, the VTF it is decoded from)`, in the order the tool writes them
MAPS = (("geralt_beard_df", "df"), ("geralt_beard_nm", "nm"))


@pytest.fixture(scope="module")
def written(tmp_path_factory) -> Path:
    """The four files, written fresh into a temporary folder once for this module."""
    out = tmp_path_factory.mktemp("beard")
    beard.write_outputs(beard.DEFAULT_ARCHIVE, out)
    return out


@pytest.mark.parametrize("name,suffix", MAPS)
def test_the_png_is_the_ports_map_in_the_layout_the_game_reads(name, suffix, written):
    """Colour from the VTF; alpha as the cutout at the material's own threshold."""
    got = np.asarray(Image.open(written / f"{name}.png").convert("RGBA"))
    source = beard.read_vtf(beard.DEFAULT_ARCHIVE, suffix)
    assert got.shape == (512, 1024, 4)
    if suffix == "df":
        assert np.array_equal(got[..., :3], source[..., :3])
        # the port's smooth alpha, cut where alpha_ref 0.05 stops drawing (12 of 255)
        assert set(np.unique(got[..., 3]).tolist()) == {0, 255}
        assert np.array_equal(got[..., 3] == 255, source[..., 3] >= 12)
        # the faint ends a 50 % cut would have dropped are still there
        assert (got[..., 3] > 0).sum() > (source[..., 3] >= 128).sum()
    else:
        # Diesel's packed normal: X in alpha, Y in green, 255 in red, 0 in blue,
        # as the pack writes it (`tests/test_pd2_las_invariants.py` holds the packs to it)
        assert set(np.unique(got[..., 0]).tolist()) == {255}
        assert set(np.unique(got[..., 2]).tolist()) == {0}
        # Y is the source's green, flipped: DirectX-style Y- into PD2's Y+
        assert np.array_equal(got[..., 1], 255 - source[..., 1])
        assert not np.array_equal(got[..., 3], source[..., 2])  # X comes from red, not blue


@pytest.mark.parametrize("name,_suffix", MAPS)
def test_the_dds_is_a_full_pyramid_of_the_same_picture(name, _suffix, written):
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
    """The files under `references/textures/` are the port archive's own maps, byte for byte.

    They are build inputs for the Geralt pack and hand-outs for other work, so they
    are committed; this is what keeps a re-run of the tool from leaving them silently
    behind, or the tracked copy from being something no command writes. The DDS files
    were user-supplied edits on `main` (`f54c41a`); since the extractor writes them from
    the archive they are held to it exactly, like the PNGs.
    """
    missing = [f"{name}{suffix}" for name, _ in MAPS for suffix in (".png", ".dds")
               if not (TEXTURES / f"{name}{suffix}").is_file()]
    assert not missing, f"not in the tree: {missing}; run python tools/extract_beard_textures.py"
    for name, _ in MAPS:
        for suffix in (".png", ".dds"):
            tracked = (TEXTURES / f"{name}{suffix}").read_bytes()
            assert tracked == (written / f"{name}{suffix}").read_bytes(), (
                f"{name}{suffix} is stale: run python tools/extract_beard_textures.py")


@pytest.mark.skipif(not GERALT_PACK.is_file(), reason="the tracked Geralt pack is missing")
def test_the_pack_ships_the_tracked_beard():
    """The pack's beard quadrant is the tracked diffuse, darkened by the builder's own gain.

    The builder reads `references/textures/geralt_beard_{df,nm}.dds`; this reads the
    shipped zip and says the same picture is inside it, as far as DXT5 re-encoding
    allows. A rebuild that shipped some other beard would pass every other test here.
    """
    with zipfile.ZipFile(GERALT_PACK) as z:
        df = np.asarray(Image.open(io.BytesIO(z.read(
            next(n for n in z.namelist() if n.endswith("npc_criminal_wild_1_head_df.texture"))))).convert("RGBA"))
        nm = np.asarray(Image.open(io.BytesIO(z.read(
            next(n for n in z.namelist() if n.endswith("npc_criminal_wild_1_head_nm.texture"))))).convert("RGBA"))
    assert df.shape == (2048, 2048, 4) and nm.shape == (2048, 2048, 4)
    quadrant_df, quadrant_nm = df[1024:1536, 1024:2048], nm[1024:1536, 1024:2048]

    tracked_df = np.asarray(Image.open(TEXTURES / "geralt_beard_df.dds").convert("RGBA"))
    tracked_nm = np.asarray(Image.open(TEXTURES / "geralt_beard_nm.dds").convert("RGBA"))
    expected = np.clip(tracked_df[..., :3].astype(np.float32) * BEARD_GAIN, 0, 255)

    assert set(np.unique(quadrant_df[..., 3]).tolist()) == {0, ATLAS_ALPHA}
    # every texel the tracked texture draws is drawn by the pack too: the builder feathers a
    # ring outside the cutout, and never drops one from inside it
    drawn, packed = tracked_df[..., 3] > 0, quadrant_df[..., 3] > 0
    assert not (drawn & ~packed).any()
    assert np.abs(quadrant_df[..., :3].astype(int) - expected).mean() < 6.0

    assert set(np.unique(quadrant_nm[..., 0]).tolist()) == {255}
    assert set(np.unique(quadrant_nm[..., 2]).tolist()) == {0}
    assert np.abs(quadrant_nm[..., 1].astype(int) - tracked_nm[..., 1]).mean() < 1.0
    assert np.abs(quadrant_nm[..., 3].astype(int) - tracked_nm[..., 3]).mean() < 1.0


def test_the_tool_reads_the_archive_and_writes_only_references():
    """Its input is the tracked port archive; its output folder is the one that is tracked."""
    source = (REPO / "tools" / "extract_beard_textures.py").read_text(encoding="utf-8")
    assert 'DEFAULT_ARCHIVE = ROOT / "references" / "characters" / "Geralt.7z"' in source
    assert 'DEFAULT_OUT = ROOT / "references" / "textures"' in source
    assert "dist/" not in source.replace('`dist/Geralt/Geralt_over_Rust.zip`', ""), \
        "the tool's source is the archive; the pack is downstream of it"
    assert (beard.DEFAULT_OUT / "geralt_beard_df.png").parent == TEXTURES
