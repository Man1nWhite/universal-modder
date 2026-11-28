"""Geralt's face textures: 2048x2048 archive PNG extracts and 1024x1024 supplied DDS build inputs.

`references/characters/Geralt.7z` carries `geralt_head_bm.vtf` and `geralt_head_nm.vtf`
at 2048x2048, which `tools/extract_face_textures.py` writes out as
`references/textures/geralt_head_{df,nm}.png` (and `.dds` when asked for a full
four-file dump outside `references/textures/`).

Beside those archive PNGs, `references/textures/geralt_head_{df,nm}.dds` are the
user's supplied 1024x1024 DXT5 face textures (D96) carrying painted beard and
moustache hair strands plus matching PAYDAY 2 normal relief (`R=255, G=Y+, B=0, A=X`).
`build_joy_head_mods.build_geralt_rust_mod` reads the supplied `.dds` pair directly
into `[0:1024, 0:1024]` of `npc_criminal_wild_1_head_{df,nm}.texture`, preserving
the supplied BC1 colour blocks on level 0 of the diffuse quadrant.
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

import build_joy_head_mods as heads  # noqa: E402
import extract_face_textures as face  # noqa: E402

TEXTURES = REPO / "references" / "textures"
GERALT_PACK = REPO / "dist" / "Geralt" / "Geralt_over_Rust.zip"
#: the builder's specular alpha in the head atlas' solid half, `build_geralt_rust_mod`
ATLAS_ALPHA = 18
#: the pack's atlas quadrant matches the supplied 1024x1024 DDS face maps
QUADRANT = 1024

pytestmark = pytest.mark.skipif(
    not face.DEFAULT_ARCHIVE.is_file(),
    reason="the tracked Witcher 3 port archive is missing; restore it with `git checkout -- references`")

#: `(name, the VTF it is decoded from)`, in the order the tool writes them
MAPS = (("geralt_head_df", "df"), ("geralt_head_nm", "nm"))


@pytest.fixture(scope="module")
def written(tmp_path_factory) -> Path:
    """The four archive-extracted files, written fresh into a temporary folder once."""
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
        assert np.array_equal(got, source)
        assert set(np.unique(got[..., 3]).tolist()) == {255}
    else:
        assert set(np.unique(got[..., 0]).tolist()) == {255}
        assert set(np.unique(got[..., 2]).tolist()) == {0}
        assert np.array_equal(got[..., 1], 255 - source[..., 1])
        assert np.array_equal(got[..., 3], source[..., 0])


@pytest.mark.parametrize("name,_suffix", MAPS)
def test_the_extracted_dds_is_a_full_pyramid_of_the_same_picture(name, _suffix, written):
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
    assert np.abs(decoded.astype(int) - png.astype(int)).mean() < 6.0


def test_tracked_pngs_match_the_archive_extractor(written, tmp_path, monkeypatch):
    """Tracked `.png` files match the archive byte-for-byte; default run preserves `.dds`."""
    for name, _ in MAPS:
        png_path = TEXTURES / f"{name}.png"
        assert png_path.is_file(), f"missing {png_path.relative_to(REPO)}"
        assert png_path.read_bytes() == (written / f"{name}.png").read_bytes(), (
            f"{name}.png is stale: run python tools/extract_face_textures.py")

    # Running `main()` against DEFAULT_OUT without `--dds` leaves pre-existing `.dds` untouched.
    fake_refs = tmp_path / "textures"
    fake_refs.mkdir()
    sentinel_df = fake_refs / "geralt_head_df.dds"
    sentinel_nm = fake_refs / "geralt_head_nm.dds"
    sentinel_df.write_bytes(b"keep-df")
    sentinel_nm.write_bytes(b"keep-nm")
    monkeypatch.setattr(face, "DEFAULT_OUT", fake_refs)
    assert face.main(["--out", str(fake_refs)]) == 0
    assert sentinel_df.read_bytes() == b"keep-df"
    assert sentinel_nm.read_bytes() == b"keep-nm"
    assert (fake_refs / "geralt_head_df.png").is_file()
    assert (fake_refs / "geralt_head_nm.png").is_file()


def test_supplied_face_dds_pair_and_loaders(tmp_path):
    """`geralt_head_{df,nm}.dds` are 1024x1024 BC3 build inputs with painted beard relief."""
    for path in (heads.GERALT_HEAD_DF, heads.GERALT_HEAD_NM):
        assert path.is_file(), f"missing {path.relative_to(REPO)}"
        raw = path.read_bytes()
        assert len(raw) == 128 + QUADRANT * QUADRANT
        assert raw[:4] == b"DDS " and raw[84:88] == b"DXT5"
        assert struct.unpack_from("<II", raw, 12) == (QUADRANT, QUADRANT)

    df_px, df_bc3 = heads.load_geralt_face_diffuse()
    nm_px = heads.load_geralt_face_normal()
    assert df_px.shape == (QUADRANT, QUADRANT, 4) and len(df_bc3) == QUADRANT * QUADRANT
    assert set(np.unique(df_px[..., 3]).tolist()) == {ATLAS_ALPHA}
    assert nm_px.shape == (QUADRANT, QUADRANT, 4)
    assert set(np.unique(nm_px[..., 0]).tolist()) == {255}
    assert set(np.unique(nm_px[..., 2]).tolist()) == {0}

    # Upper face matches the downsampled VTF maps; lower-face beard zone carries the edit.
    vtf_df = np.asarray(
        Image.open(TEXTURES / "geralt_head_df.png").convert("RGB").resize(
            (QUADRANT, QUADRANT), Image.Resampling.LANCZOS
        )
    )
    assert np.abs(df_px[:350, :, :3].astype(int) - vtf_df[:350].astype(int)).mean() < 3.0
    assert np.abs(df_px[560:760, 380:640, :3].astype(int) - vtf_df[560:760, 380:640].astype(int)).mean() > 8.0

    bad = tmp_path / "bad.dds"
    bad.write_bytes(b"not a dds")
    with pytest.raises(ValueError, match="1024x1024 DXT5"):
        heads.load_geralt_face_diffuse(bad)
    # Diffuse RGB cannot pass the PD2 normal-layout check (`R~255, B~0`).
    with pytest.raises(ValueError, match="PAYDAY 2 normal layout"):
        heads.load_geralt_face_normal(heads.GERALT_HEAD_DF)


@pytest.mark.skipif(not GERALT_PACK.is_file(), reason="the tracked Geralt pack is missing")
def test_the_pack_was_built_from_the_supplied_face_dds():
    """The shipped pack's `[0:1024, 0:1024]` face quadrants come from `geralt_head_{df,nm}.dds`."""
    with zipfile.ZipFile(GERALT_PACK) as z:
        df_raw = z.read(next(n for n in z.namelist() if n.endswith("npc_criminal_wild_1_head_df.texture")))
        nm_raw = z.read(next(n for n in z.namelist() if n.endswith("npc_criminal_wild_1_head_nm.texture")))
    df = np.asarray(Image.open(io.BytesIO(df_raw)).convert("RGBA"))
    nm = np.asarray(Image.open(io.BytesIO(nm_raw)).convert("RGBA"))
    assert df.shape == (2048, 2048, 4) and nm.shape == (2048, 2048, 4)

    supplied_df, supplied_bc3 = heads.load_geralt_face_diffuse()
    supplied_nm = heads.load_geralt_face_normal()

    # Level-0 BC1 colour halves are spliced verbatim from `geralt_head_df.dds`.
    quad_df = df[0:QUADRANT, 0:QUADRANT]
    assert np.array_equal(quad_df, supplied_df)
    atlas_blocks = np.frombuffer(df_raw[128 : 128 + 512 * 512 * 16], dtype=np.uint8).reshape(512, 512, 16)
    face_blocks = np.frombuffer(supplied_bc3, dtype=np.uint8).reshape(256, 256, 16)
    assert np.array_equal(atlas_blocks[:256, :256, 8:16], face_blocks[:, :, 8:16])

    quad_nm = nm[0:QUADRANT, 0:QUADRANT]
    assert set(np.unique(quad_nm[..., 0]).tolist()) == {255}
    assert set(np.unique(quad_nm[..., 2]).tolist()) == {0}
    assert np.abs(quad_nm.astype(int) - supplied_nm.astype(int)).mean() < 1.0


def test_the_tool_reads_the_archive_and_writes_only_references():
    """Its input is the tracked port archive; its output folder is the one that is tracked."""
    source = (REPO / "tools" / "extract_face_textures.py").read_text(encoding="utf-8")
    assert 'DEFAULT_ARCHIVE = ROOT / "references" / "characters" / "Geralt.7z"' in source
    assert 'DEFAULT_OUT = ROOT / "references" / "textures"' in source
    assert (face.DEFAULT_OUT / "geralt_head_df.png").parent == TEXTURES
