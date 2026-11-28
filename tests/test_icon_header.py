"""The head packs' character icon header: 128 tracked bytes instead of an 11.7 MB archive.

`tools/build_joy_head_mods.py` writes every character icon under one DDS header (128x128
uncompressed BGRA8), and used to take it from the first 128 bytes of
`references/templates/Ada Wong over Joy.7z`'s `joy.texture`. That archive left the tree on
2026-11-27 (D91): `tools/extract_icon_header.py` wrote the header out to
`references/textures/icon_header_128x128_bgra8.dds`, and this holds the tracked bytes to
what the builder needs, and to the archive itself while history can still produce it.
"""
from __future__ import annotations

import re
import struct
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import extract_icon_header as header_tool  # noqa: E402

HEADER = REPO / "references" / "textures" / "icon_header_128x128_bgra8.dds"
GERALT_PACK = REPO / "dist" / "Geralt" / "Geralt_over_Rust.zip"
#: a 128x128 uncompressed BGRA8 DDS: 32 bpp, RGB + alpha masks, one level, 65,536 payload bytes
ICON_PAYLOAD = 128 * 128 * 4


def test_the_tracked_header_is_the_one_the_builder_uses():
    """One file, 128 bytes, and the builder's constant points at it."""
    source = (REPO / "tools" / "build_joy_head_mods.py").read_text(encoding="utf-8")
    assert re.search(r'ICON_HEADER = ROOT / "references" / "textures" / "icon_header_128x128_bgra8\.dds"', source)
    assert "header = ICON_HEADER.read_bytes()" in source
    assert "ensure_ada_reference" not in source and "_ensure_7z(.*Ada" not in source
    assert "references/templates/Ada Wong over Joy.7z" not in source, "the builder must not read the archive"
    assert HEADER.is_file(), "references/textures/icon_header_128x128_bgra8.dds is missing"
    assert len(HEADER.read_bytes()) == 128


def test_the_header_describes_the_icon_the_packs_ship():
    """128x128, uncompressed 32-bit, no mip chain: what `make_character_icon_dds` appends pixels to."""
    raw = HEADER.read_bytes()
    assert raw[:4] == b"DDS "
    magic, size, flags, height, width, pitch, depth, mips = struct.unpack_from("<4s7I", raw, 0)
    assert (size, height, width, depth, mips) == (124, 128, 128, 0, 1)
    # DDS_PIXELFORMAT starts at 76: dwSize, dwFlags, dwFourCC, dwRGBBitCount, then the four masks
    pf_size, pixel_flags, fourcc, bits, rmask, gmask, bmask, amask = struct.unpack_from("<II4s5I", raw, 76)
    assert pf_size == 32 and fourcc == bytes(4), "the icon is uncompressed"
    assert pixel_flags & 0x40, "DDPF_RGB must be set"
    assert bits == 32 and (rmask, gmask, bmask, amask) == (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    assert pitch == 128 * 4, "pitch of one 32-bit row"


@pytest.mark.skipif(not GERALT_PACK.is_file(), reason="the tracked Geralt pack is missing")
def test_the_shipped_icon_reads_as_the_header_plus_its_own_pixels():
    """A shipped icon is exactly this header and 65,536 bytes of portrait."""
    with zipfile.ZipFile(GERALT_PACK) as z:
        name = next(n for n in z.namelist() if n.endswith("icons/characters/wild.texture"))
        icon = z.read(name)
    assert len(icon) == 128 + ICON_PAYLOAD
    assert icon[:128] == HEADER.read_bytes(), "the pack's icon header is not the tracked header"


@pytest.mark.skipif(header_tool.DEFAULT_ARCHIVE.is_file(),
                    reason="the reference archive is still in the tree; the header no longer needs it")
def test_the_tool_still_names_the_archive_it_was_written_from():
    """With the archive gone, the tool's inputs are still written down, not deleted with it."""
    source = (REPO / "tools" / "extract_icon_header.py").read_text(encoding="utf-8")
    assert "references\" / \"templates\" / \"Ada Wong over Joy.7z" in source
    assert "joy.texture" in source
