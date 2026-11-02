"""Valve Texture File (VTF 7.x) reader and DDS/PNG conversion.

Verified against the seven DXT5 textures inside `l4d2_miranda_lawson_1.zip`
(VTF 7.4, single frame, resource entries at offset 80 with absolute offsets).
PAYDAY 2 `.texture` files are raw DDS buffers, so `to_dds()` is the conversion
path into the Diesel game; `to_png()` (Pillow, via a generated DDS) is for
preview/QA only.

VTF stores the high-res image smallest-mip-first; DDS wants mip 0 first, so
the mip chain is reversed on output. Only single-frame, non-cubemap 2D textures
in DXT1/DXT3/DXT5 or uncompressed RGBA8888/BGR888/RGB888/A8/L8 are supported.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

VTF_SIGNATURE = b"VTF\x00"

# ImageFormat enum (subset)
FMT_I8 = 5
FMT_IA88 = 6
FMT_A8 = 8
FMT_RGB888 = 2
FMT_BGR888 = 3
FMT_BGRX8888 = 16
FMT_BGRA8888 = 12
FMT_RGBA8888 = 0
FMT_DXT1 = 13
FMT_DXT3 = 14
FMT_DXT5 = 15

_FOURCC = {FMT_DXT1: b"DXT1", FMT_DXT3: b"DXT3", FMT_DXT5: b"DXT5"}
_UNCOMPRESSED = {
    FMT_RGBA8888: ("R", "G", "B", "A", 32),
    FMT_BGRA8888: ("B", "G", "R", "A", 32),
    FMT_BGRX8888: ("B", "G", "R", "X", 32),
    FMT_BGR888: ("B", "G", "R", None, 24),
    FMT_RGB888: ("R", "G", "B", None, 24),
    FMT_A8: ("A", None, None, None, 8),
    FMT_I8: ("L", None, None, None, 8),
    FMT_IA88: ("A", "L", None, None, 16),
}
FORMAT_NAMES = {
    0: "RGBA8888", 1: "ABGR8888", 2: "RGB888", 3: "BGR888", 4: "RGB565",
    5: "I8", 6: "IA88", 7: "P8", 8: "A8", 13: "DXT1", 14: "DXT3", 15: "DXT5",
    16: "BGRX8888", 17: "BGR565", 18: "BGRX5551", 19: "BGRA4444",
    20: "DXT1_ONEBITALPHA", 21: "BGRA5551", 25: "RGBA16161616",
}


class VtfError(ValueError):
    pass


def _fmt_name(fmt: int) -> str:
    return FORMAT_NAMES.get(fmt, f"unknown({fmt})")


@dataclass(frozen=True)
class VtfImage:
    data: bytes
    version: tuple[int, int]
    width: int
    height: int
    depth: int
    frames: int
    mipmap_count: int
    highres_format: int
    lowres_format: int
    lowres_width: int
    lowres_height: int
    flags: int
    image_offset: int

    @property
    def format_name(self) -> str:
        return _fmt_name(self.highres_format)


def _mip_size(fmt: int, width: int, height: int, depth: int = 1) -> int:
    if fmt in (FMT_DXT1,):
        block = 8
    elif fmt in (FMT_DXT3, FMT_DXT5):
        block = 16
    elif fmt in _UNCOMPRESSED:
        bits = _UNCOMPRESSED[fmt][4]
        return (width * height * bits + 7) // 8 * depth
    else:
        raise VtfError(f"unsupported VTF format {_fmt_name(fmt)}")
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    return bw * bh * block * depth


def parse_vtf(data: bytes) -> VtfImage:
    if data[:4] != VTF_SIGNATURE:
        raise VtfError(f"bad VTF signature: {data[:4]!r}")
    ver_major, ver_minor = struct.unpack_from("<II", data, 4)
    if ver_major != 7 or ver_minor < 2:
        raise VtfError(f"unsupported VTF version {ver_major}.{ver_minor}")
    header_size, = struct.unpack_from("<I", data, 12)
    width, height = struct.unpack_from("<HH", data, 16)
    flags, = struct.unpack_from("<I", data, 20)
    frames, _first = struct.unpack_from("<HH", data, 24)
    bumpmap, = struct.unpack_from("<f", data, 48)
    highres_format, = struct.unpack_from("<I", data, 52)
    mipmap_count, = struct.unpack_from("<B", data, 56)
    lowres_format, = struct.unpack_from("<I", data, 57)
    # Empirically (VTF 7.4, see tools/pd2-las/README.md): low-res width/height
    # are single bytes at 61/62, followed by a u16 depth at 63.
    lowres_width, lowres_height = data[61], data[62]
    depth, = struct.unpack_from("<H", data, 63)
    if ver_minor < 3:
        depth = 1
    depth = max(depth, 1)
    if frames < 1 or not 1 <= mipmap_count <= 16:
        raise VtfError("implausible frame/mip counts")
    if flags & 0x4000:  # ENVIRONMENT
        raise VtfError("cubemap VTFs are not supported")
    if frames != 1:
        raise VtfError(f"multi-frame VTFs are not supported (frames={frames})")

    # sanity-check the payload size against the declared format
    expected = 0
    for mip in range(mipmap_count):
        expected += _mip_size(
            highres_format,
            max(1, width >> mip),
            max(1, height >> mip),
            depth,
        )

    # Resource entries (7.3+): 8 bytes each, (u24 tag | u8 flags, u32 value),
    # until a zero tag. IMAGE tag = 0x30; LOWRES (0x01) is parsed past and
    # intentionally unused (mip 0 only). In VTF 7.2 there is no resource
    # dictionary; the low-res thumbnail starts at header_size and the high-res
    # mipmap chain immediately follows it.
    image_off = None
    if ver_minor >= 3:
        pos = 80
        while pos + 8 <= header_size:
            tag = int.from_bytes(data[pos : pos + 3], "little")
            flags_r = data[pos + 3]
            value = struct.unpack_from("<I", data, pos + 4)[0]
            if tag == 0:
                break
            if tag == 0x30 and not (flags_r & 0x02):
                image_off = value
            pos += 8
    elif header_size + expected <= len(data):
        lowres_bytes = (
            _mip_size(lowres_format, lowres_width, lowres_height, 1)
            if (lowres_width > 0 and lowres_height > 0 and lowres_format != 0xFFFFFFFF)
            else 0
        )
        if header_size + lowres_bytes + expected == len(data):
            image_off = header_size + lowres_bytes
        else:
            image_off = len(data) - expected
    if image_off is None:
        raise VtfError("VTF has no high-res image resource")
    if image_off + expected > len(data):
        raise VtfError(
            f"high-res data truncated: need {expected} bytes at {image_off}, file is {len(data)}"
        )

    return VtfImage(
        data=data,
        version=(ver_major, ver_minor),
        width=width,
        height=height,
        depth=depth,
        frames=frames,
        mipmap_count=mipmap_count,
        highres_format=highres_format,
        lowres_format=lowres_format,
        lowres_width=lowres_width,
        lowres_height=lowres_height,
        flags=flags,
        image_offset=image_off,
    )


def _highres_slices(img: VtfImage) -> list[bytes]:
    """Return the high-res mip payloads, mip 0 (largest) first."""
    fmt = img.highres_format
    sizes = []
    for mip in range(img.mipmap_count):
        sizes.append(_mip_size(fmt, max(1, img.width >> mip), max(1, img.height >> mip), img.depth))
    # VTF stores the chain smallest-mip-first (verified against
    # l4d2_miranda_lawson_1.zip: the clean mip 0 decodes from the file tail).
    # Slice in file order, then reverse to mip 0 first for DDS.
    out = []
    pos = img.image_offset
    for size in reversed(sizes):
        out.append(img.data[pos : pos + size])
        pos += size
    out.reverse()
    return out


def to_dds(img: VtfImage) -> bytes:
    """Convert a parsed VTF to a DDS container (PAYDAY 2 `.texture` payload)."""
    fmt = img.highres_format
    mips = _highres_slices(img)
    mip0_size = len(mips[0])

    dds_flags = 0x1 | 0x2 | 0x4 | 0x1000  # CAPS | HEIGHT | WIDTH | PIXELFORMAT
    caps = 0x1000  # DDSCAPS_TEXTURE
    if len(mips) > 1:
        dds_flags |= 0x20000  # MIPMAPCOUNT
        caps |= 0x8 | 0x400000  # COMPLEX | MIPMAP
    if fmt in _FOURCC:
        dds_flags |= 0x80000  # LINEARSIZE
        pf_flags = 0x4  # FOURCC
        fourcc = _FOURCC[fmt]
        rgb_bits = 0
        masks = (0, 0, 0, 0)
    elif fmt in _UNCOMPRESSED:
        dds_flags |= 0x8  # PITCH
        names = _UNCOMPRESSED[fmt]
        pf_flags = 0x1 | 0x40  # ALPHAPIXELS | RGB
        fourcc = b"\x00" * 4
        rgb_bits = names[4]
        def mask_for(name):
            return {
                "R": 0x00FF0000, "G": 0x0000FF00, "B": 0x000000FF,
                "A": 0xFF000000, "L": 0x0000FF00,
            }.get(name, 0)
        masks = (
            mask_for(names[0]),
            mask_for(names[1]),
            mask_for(names[2]),
            mask_for(names[3]) if names[3] else 0,
        )
    else:
        raise VtfError(f"unsupported VTF format {_fmt_name(fmt)}")

    pitch_or_linear = mip0_size
    pf = struct.pack(
        "<II4sIII",
        32,
        pf_flags,
        fourcc,
        rgb_bits,
        masks[0],
        masks[1],
    ) + struct.pack("<II", masks[2], masks[3])
    header = b"DDS " + struct.pack(
        "<7I",
        124,
        dds_flags,
        img.height,
        img.width,
        pitch_or_linear,
        0,  # depth
        len(mips),
    ) + b"\x00" * 44 + pf + struct.pack("<4I", caps, 0, 0, 0) + b"\x00" * 4
    assert len(header) == 128
    return header + b"".join(mips)


def to_png(img: VtfImage) -> bytes:
    """Decode to PNG for previews. Needs Pillow (a project dependency)."""
    import io

    from PIL import Image

    dds = to_dds(img)
    with Image.open(io.BytesIO(dds)) as im:
        im.load()
        if img.highres_format in (FMT_DXT1,):
            im = im.convert("RGBA")
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()
