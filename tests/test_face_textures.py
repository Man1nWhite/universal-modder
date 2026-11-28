"""`tools/extract_face_textures.py`: Geralt's face, read out of the Witcher 3 port's own maps.

The source is `references/characters/Geralt.7z`'s `geralt_head_bm.vtf` (the head
diffuse) and `geralt_head_nm.vtf` (the head normal), both 2048x2048. The tool
writes them under `references/textures/` as PNG and DXT5 DDS at that native size:
the diffuse with the port's own (opaque) alpha, the normal map in Diesel's
packed layout (X in alpha, Y in green, 255 in red, 0 in blue) with the same Y
flip the pack builder applies.

These are the face as a texture of its own, beside the beard pair: the pack
builder still reads the archive for its own head atlas, so nothing in `dist/`
reads these back. What this file holds is the other direction - what is tracked
must be exactly what the tool writes from the archive, and the picture must be
the one the shipped pack's head quadrant was built from.
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

import extract_face_textures as face  # noqa: E402

TEXTURES = REPO / "references" / "textures"
GERALT_PACK = REPO / "dist" / "Geralt" / "Geralt_over_Rust.zip"
#: the builder's specular alpha in the head atlas' solid half, `build_geralt_rust_mod`
ATLAS_ALPHA = 18
#: the pack's atlas quadrant is half the tracked map's side
QUADRANT = 1024

pytestmark = pytest.mark.skipif(
    not face.DEFAULT_ARCHIVE.is_file(),
    reason="the tracked Witcher 3 port archive is missing; restore it with `git checkout -- references`")

#: `(name, the VTF it is decoded from)`, in the order the tool writes them
MAPS = (("geralt_head_df", "df"), ("geralt_head_nm", "nm"))


@pytest.fixture(scope="module")
def written(tmp_path_factory) -> Path:
    """The four files, written fresh into a temporary folder once for this module."""
    out = tmp_path_factory.mktemp("face")
    face.write_outputs(face.DEFAULT_ARCHIVE, out)
    return out


@pytest.mark.parametrize("name,suffix", MAPS)
def test_the_png_is_the_ports_map_in_the_layout_the_game_reads(name, suffix, written):
    """Colour unchanged; the normal in Diesel's packed layout with the Y flip."""
    got = np.asarray(Image.open(written / f"{name}.png").convert("RGBA"))
    source = face.read_vtf(face.DEFAULT_ARCHIVE, suffix)
    assert got.shape == (2048, 2048, 4)
    if suffix == "df":
        # the head is solid in the port; the pack's specular alpha is the builder's, not this
        assert np.array_equal(got, source)
        assert set(np.unique(got[..., 3]).tolist()) == {255}
    else:
        # Diesel's packed normal: X in alpha, Y in green, 255 in red, 0 in blue
        assert set(np.unique(got[..., 0]).tolist()) == {255}
        assert set(np.unique(got[..., 2]).tolist()) == {0}
        # Y is the source's green, flipped: DirectX-style Y- into PD2's Y+
        assert np.array_equal(got[..., 1], 255 - source[..., 1])
        # X is the source's red, not its blue (see `pd2_normal_channels`)
        assert np.array_equal(got[..., 3], source[..., 0])


@pytest.mark.parametrize("name,_suffix", MAPS)
def test_the_dds_is_a_full_pyramid_of_the_same_picture(name, _suffix, written):
    """Its own header for 2048x2048, every level there, and level 0 decodes to the PNG."""
    raw = (written / f"{name}.dds").read_bytes()
    assert raw[:4] == b"DDS "
    height, width, pitch = struct.unpack_from("<3I", raw, 12)
    mips = struct.unpack_from("<I", raw, 28)[0]
    assert (height, width, mips) == (2048, 2048, 12)
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
    # DXT5 is lossy: every channel within a few steps of the PNG
    assert np.abs(decoded.astype(int) - png.astype(int)).mean() < 6.0


def test_what_is_tracked_is_what_the_tool_writes(written):
    """The files under `references/textures/` are the port archive's own maps, byte for byte."""
    missing = [f"{name}{suffix}" for name, _ in MAPS for suffix in (".png", ".dds")
               if not (TEXTURES / f"{name}{suffix}").is_file()]
    assert not missing, f"not in the tree: {missing}; run python tools/extract_face_textures.py"
    for name, _ in MAPS:
        for suffix in (".png", ".dds"):
            tracked = (TEXTURES / f"{name}{suffix}").read_bytes()
            assert tracked == (written / f"{name}{suffix}").read_bytes(), (
                f"{name}{suffix} is stale: run python tools/extract_face_textures.py")


@pytest.mark.skipif(not GERALT_PACK.is_file(), reason="the tracked Geralt pack is missing")
def test_the_pack_was_built_from_the_tracked_face():
    """The shipped pack's head quadrant is the tracked diffuse, halved the builder's way.

    The builder reads the VTF and downsamples it to 1024 with LANCZOS, so the shipped
    quadrant is that halving re-encoded as DXT5. If the tracked diffuse were something
    other than the port's map, this would drift; it holds as far as DXT5 allows.
    """
    with zipfile.ZipFile(GERALT_PACK) as z:
        df = np.asarray(Image.open(io.BytesIO(z.read(
            next(n for n in z.namelist() if n.endswith("npc_criminal_wild_1_head_df.texture"))))).convert("RGBA"))
    assert df.shape == (2048, 2048, 4)
    quadrant = df[0:QUADRANT, 0:QUADRANT]          # Geralt_head_BM
    tracked = Image.open(TEXTURES / "geralt_head_df.png").convert("RGB")
    halved = np.asarray(tracked.resize((QUADRANT, QUADRANT), Image.Resampling.LANCZOS))

    assert set(np.unique(quadrant[..., 3]).tolist()) == {ATLAS_ALPHA}
    assert np.abs(quadrant[..., :3].astype(int) - halved.astype(int)).mean() < 6.0


def test_the_tool_reads_the_archive_and_writes_only_references():
    """Its input is the tracked port archive; its output folder is the one that is tracked."""
    source = (REPO / "tools" / "extract_face_textures.py").read_text(encoding="utf-8")
    assert 'DEFAULT_ARCHIVE = ROOT / "references" / "characters" / "Geralt.7z"' in source
    assert 'DEFAULT_OUT = ROOT / "references" / "textures"' in source
    assert (face.DEFAULT_OUT / "geralt_head_df.png").parent == TEXTURES
