#!/usr/bin/env python3
"""DXT5 DDS helpers for PAYDAY 2 .texture files (raw DDS buffers).

Vanilla PAYDAY 2 DXT5 textures carry a complete mipmap pyramid:

- flags   = 0x000A1007  (CAPS | HEIGHT | WIDTH | PIXELFORMAT | LINEARSIZE |
                         MIPMAPCOUNT) with dwMipMapCount = log2(size) + 1
- caps    = 0x00401008  (TEXTURE | COMPLEX | MIPMAP)
- dwPitchOrLinearSize = byte size of mip 0
- one payload per level down to 1x1; below 4x4 each level is one DXT block

build_package2.py once wrote mip 0 only (flags 0x00081007, dwMipMapCount 0,
caps 0x00001000) and its block encoder could emit DXT5 colour endpoints in the
wrong order (c0 < c1). Decoders read such blocks as the 3-colour mode with a
transparent index, so those blocks render as holes. These helpers always emit
c0 > c1, build full chains from an RGBA image or from an existing mip-0
payload, and repair textures that lack the pyramid or contain mis-ordered
endpoints.

Encoding needs numpy; validation is pure stdlib.
"""
from __future__ import annotations

import struct

DDS_HEADER_SIZE = 128
MIP_FLAGS = 0x000A1007
MIP_CAPS = 0x00401008


def _np():
    import numpy as np

    return np


def mip_count_for(size: int) -> int:
    """Mip levels for a power-of-two dimension, down to 1x1."""
    return size.bit_length()


def _rgb565(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def _expand565(v):
    return (
        ((v >> 11) & 31) * 255 // 31,
        ((v >> 5) & 63) * 255 // 63,
        (v & 31) * 255 // 31,
    )


def _decode_block(block: bytes, force_4color: bool = True) -> list[tuple[int, int, int, int]]:
    """Decode one DXT5 block to 16 RGBA tuples (row-major 4x4).

    DXT5 (BC3) has a separate alpha block and its RGB part is **always** the
    4-colour palette — unlike BC1 there is no 3-colour + transparent mode, so
    c0 < c1 is not a corrupt block. ``force_4color`` is kept for call
    compatibility and ignored.
    """
    a0, a1 = block[0], block[1]
    a_bits = int.from_bytes(block[2:8], "little")
    if a0 > a1:
        pal_a = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        pal_a = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    c0, c1 = struct.unpack_from("<HH", block, 8)
    c_bits = int.from_bytes(block[12:16], "little")
    e0 = _expand565(c0)
    e1 = _expand565(c1)
    pal_c = [
        e0,
        e1,
        tuple((2 * e0[i] + e1[i]) // 3 for i in range(3)),
        tuple((e0[i] + 2 * e1[i]) // 3 for i in range(3)),
    ]
    out = []
    for px in range(16):
        ai = (a_bits >> (3 * px)) & 7
        ci = (c_bits >> (2 * px)) & 3
        col = pal_c[ci]
        alpha = pal_a[ai]
        out.append((col[0], col[1], col[2], alpha))
    return out


def _encode_block(pixels) -> bytes:
    """Encode 16 RGBA tuples (row-major 4x4) to a DXT5 block with c0 >= c1."""
    alpha = [p[3] for p in pixels]
    rgb = [p[:3] for p in pixels]
    a0 = max(alpha)
    a1 = min(alpha)
    if a0 == a1:
        ab = bytes([a0, a1]) + b"\x00" * 6
    else:
        pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
        bits = 0
        for px, a in enumerate(alpha):
            best = min(range(8), key=lambda k: abs(a - pal[k]))
            bits |= best << (3 * px)
        ab = bytes([a0, a1]) + bits.to_bytes(6, "little")
    sums = [c[0] + c[1] + c[2] for c in rgb]
    i0 = sums.index(max(sums))
    i1 = max(range(16), key=lambda k: sum((rgb[k][i] - rgb[i0][i]) ** 2 for i in range(3)))
    e0 = _rgb565(rgb[i0])
    e1 = _rgb565(rgb[i1])
    if e0 < e1:
        e0, e1 = e1, e0
    if e0 == e1:
        cb = struct.pack("<HH", e0, e1) + b"\x00" * 4
    else:
        c0 = _expand565(e0)
        c1 = _expand565(e1)
        pal = [
            c0,
            c1,
            tuple((2 * c0[i] + c1[i]) // 3 for i in range(3)),
            tuple((c0[i] + 2 * c1[i]) // 3 for i in range(3)),
        ]
        bits = 0
        for px, c in enumerate(rgb):
            best = min(range(4), key=lambda k: sum((c[i] - pal[k][i]) ** 2 for i in range(3)))
            bits |= best << (2 * px)
        cb = struct.pack("<HH", e0, e1) + bits.to_bytes(4, "little")
    return ab + cb


def pd2_normal_channels(arr, invert_y: bool = True):
    """Repack a standard RGB normal map into PAYDAY 2's packed layout.

    Per the ModWorkshop LAS/MOOG porting guide: Diesel's normal shader reads
    only alpha (X) and green (Y). Move the source red (X) into alpha, set red
    to white and blue to black (unused channels), and keep green as Y —
    ``invert_y`` converts DirectX-style (Y-) sources to the OpenGL-style (Y+)
    convention PD2's shaders expect. Compress the result with DXT5 (every PD2
    normal map uses an alpha channel).
    """
    np = _np()
    src = np.asarray(arr, dtype=np.uint8)
    if src.ndim != 3 or src.shape[2] < 3:
        raise ValueError(f"expected HxWx3/4 array, got {src.shape}")
    out = np.zeros((src.shape[0], src.shape[1], 4), dtype=np.uint8)
    x = src[..., 0].astype(np.int16)
    y = src[..., 1].astype(np.int16)
    out[..., 0] = 255                       # red: unused, kept white
    if invert_y:
        y = 255 - y
    out[..., 1] = np.clip(y, 0, 255).astype(np.uint8)   # green: Y+
    out[..., 2] = 0                         # blue: unused, kept black
    out[..., 3] = x.astype(np.uint8)        # alpha: X
    return out


def encode_dxt5(img) -> bytes:
    """Encode an (h, w, 4) uint8 RGBA array; h and w must be multiples of 4."""
    np = _np()
    arr = np.asarray(img, dtype=np.uint8)
    h, w = arr.shape[:2]
    if h % 4 or w % 4:
        raise ValueError(f"encode_dxt5 needs multiples of 4, got {w}x{h}")
    bh, bw = h // 4, w // 4
    blocks = arr.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    n = blocks.shape[0]

    alpha = blocks[:, :, 3].astype(np.int32)
    a0 = alpha.max(axis=1)
    a1 = alpha.min(axis=1)
    pal_a = np.empty((n, 8), dtype=np.int32)
    pal_a[:, 0] = a0
    pal_a[:, 1] = a1
    for i in range(1, 7):
        pal_a[:, i + 1] = ((7 - i) * a0 + i * a1) // 7
    idx_a = np.abs(alpha[:, :, None] - pal_a[:, None, :]).argmin(axis=2).astype(np.uint64)
    idx_a[a0 == a1] = 0
    shifts_a = (3 * np.arange(16, dtype=np.uint64))[None, :]
    bits_a = (idx_a << shifts_a).sum(axis=1, dtype=np.uint64)
    ab = np.empty((n, 8), dtype=np.uint8)
    ab[:, 0] = a0.astype(np.uint8)
    ab[:, 1] = a1.astype(np.uint8)
    for b in range(6):
        ab[:, 2 + b] = ((bits_a >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.uint8)

    rgb = blocks[:, :, :3].astype(np.int32)
    sums = rgb.sum(axis=2)
    i0 = sums.argmax(axis=1)
    c_max = rgb[np.arange(n), i0]
    dist = ((rgb - c_max[:, None, :]) ** 2).sum(axis=2)
    i1 = dist.argmax(axis=1)
    c_min = rgb[np.arange(n), i1]

    e0 = ((c_max[:, 0] >> 3) << 11) | ((c_max[:, 1] >> 2) << 5) | (c_max[:, 2] >> 3)
    e1 = ((c_min[:, 0] >> 3) << 11) | ((c_min[:, 1] >> 2) << 5) | (c_min[:, 2] >> 3)
    swap = e0 < e1
    e0_s = np.where(swap, e1, e0)
    e1_s = np.where(swap, e0, e1)

    def _exp565_vec(v):
        r = ((v >> 11) & 31) * 255 // 31
        g = ((v >> 5) & 63) * 255 // 63
        b = (v & 31) * 255 // 31
        return np.stack([r, g, b], axis=-1)

    p0 = _exp565_vec(e0_s)
    p1 = _exp565_vec(e1_s)
    p2 = (2 * p0 + p1) // 3
    p3 = (p0 + 2 * p1) // 3
    pal_c = np.stack([p0, p1, p2, p3], axis=1)
    idx_c = ((rgb[:, :, None, :] - pal_c[:, None, :, :]) ** 2).sum(axis=3).argmin(axis=2).astype(np.uint32)
    idx_c[e0_s == e1_s] = 0
    shifts_c = (2 * np.arange(16, dtype=np.uint32))[None, :]
    bits_c = (idx_c << shifts_c).sum(axis=1, dtype=np.uint32)

    cb = np.empty((n, 8), dtype=np.uint8)
    cb[:, 0] = (e0_s & 0xFF).astype(np.uint8)
    cb[:, 1] = ((e0_s >> 8) & 0xFF).astype(np.uint8)
    cb[:, 2] = (e1_s & 0xFF).astype(np.uint8)
    cb[:, 3] = ((e1_s >> 8) & 0xFF).astype(np.uint8)
    for b in range(4):
        cb[:, 4 + b] = ((bits_c >> np.uint32(8 * b)) & np.uint32(0xFF)).astype(np.uint8)

    return np.concatenate([ab, cb], axis=1).tobytes()


def decode_dxt5(data: bytes, w: int, h: int):
    """Decode a DXT5 mip payload to an (h, w, 4) uint8 RGBA array."""
    np = _np()
    bw, bh = w // 4, h // 4
    if w % 4 or h % 4:
        raise ValueError(f"decode_dxt5 needs multiples of 4, got {w}x{h}")
    n = bh * bw
    if len(data) < n * 16:
        raise ValueError(f"DXT5 payload too short: {len(data)} < {n * 16}")
    blocks = np.frombuffer(data, dtype=np.uint8, count=n * 16).reshape(n, 16)

    a0 = blocks[:, 0].astype(np.int32)
    a1 = blocks[:, 1].astype(np.int32)
    a_bits = np.zeros(n, dtype=np.uint64)
    for b in range(6):
        a_bits |= blocks[:, 2 + b].astype(np.uint64) << np.uint64(8 * b)
    pal_a8 = np.empty((n, 8), dtype=np.int32)
    pal_a8[:, 0] = a0
    pal_a8[:, 1] = a1
    for i in range(1, 7):
        pal_a8[:, i + 1] = ((7 - i) * a0 + i * a1) // 7
    pal_a6 = np.empty((n, 8), dtype=np.int32)
    pal_a6[:, 0] = a0
    pal_a6[:, 1] = a1
    for i in range(1, 5):
        pal_a6[:, i + 1] = ((5 - i) * a0 + i * a1) // 5
    pal_a6[:, 6] = 0
    pal_a6[:, 7] = 255
    pal_a = np.where((a0 > a1)[:, None], pal_a8, pal_a6)

    c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
    c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
    c_bits = (
        blocks[:, 12].astype(np.uint32)
        | (blocks[:, 13].astype(np.uint32) << 8)
        | (blocks[:, 14].astype(np.uint32) << 16)
        | (blocks[:, 15].astype(np.uint32) << 24)
    )

    def _exp565_v(v):
        r = ((v >> 11) & 31) * 255 // 31
        g = ((v >> 5) & 63) * 255 // 63
        b = (v & 31) * 255 // 31
        return np.stack([r, g, b], axis=-1)

    e0 = _exp565_v(c0)
    e1 = _exp565_v(c1)
    pal_c = np.stack([e0, e1, (2 * e0 + e1) // 3, (e0 + 2 * e1) // 3], axis=1)

    out = np.empty((n, 16, 4), dtype=np.uint8)
    ar_n = np.arange(n)
    for px in range(16):
        ai = (a_bits >> np.uint64(3 * px)) & np.uint64(7)
        ci = (c_bits >> np.uint32(2 * px)) & np.uint32(3)
        out[:, px, :3] = pal_c[ar_n, ci]
        out[:, px, 3] = pal_a[ar_n, ai]
    return out.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(h, w, 4)


def downsample2x2(img):
    """Box-filter an RGBA image to half size."""
    np = _np()
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    return (arr.reshape(h // 2, 2, w // 2, 2, 4).mean(axis=(1, 3)) + 0.5).astype(np.uint8)


def _level_payload(img) -> bytes:
    """Encode one mip level, padding sub-4x4 levels to a single block."""
    np = _np()
    arr = np.asarray(img, dtype=np.uint8)
    h, w = arr.shape[:2]
    if h < 4 or w < 4:
        padded = np.empty((max(4, h), max(4, w), 4), dtype=np.uint8)
        padded[:h, :w] = arr
        padded[h:, :w] = arr[h - 1 : h, :w]
        padded[:, w:] = padded[:, w - 1 : w]
        return encode_dxt5(padded[:4, :4])
    if h % 4 or w % 4:
        raise ValueError(f"unexpected non-block-aligned level {w}x{h}")
    return encode_dxt5(arr)


def mip_payloads_from_image(img) -> list[bytes]:
    """Full mip chain from an RGBA image (power-of-two, square)."""
    np = _np()
    arr = np.asarray(img, dtype=np.uint8)
    h, w = arr.shape[:2]
    if h != w or h == 0 or (h & (h - 1)):
        raise ValueError(f"texture must be square power-of-two, got {w}x{h}")
    payloads = [_level_payload(arr)]
    level = arr
    while level.shape[0] > 1:
        level = downsample2x2(level)
        payloads.append(_level_payload(level))
    return payloads


def mip_payloads_from_mip0(mip0: bytes, size: int) -> list[bytes]:
    """Full mip chain by box-filtering an existing DXT5 mip-0 payload."""
    img = decode_dxt5(mip0, size, size)
    return mip_payloads_from_image(img)


def pack_dds(mip_payloads: list[bytes], size: int) -> bytes:
    """Pack payloads into a vanilla-shaped DXT5 DDS buffer."""
    num_mips = mip_count_for(size)
    if len(mip_payloads) != num_mips:
        raise ValueError(f"expected {num_mips} mip payloads, got {len(mip_payloads)}")
    mip0_len = len(mip_payloads[0])
    expected0 = max(1, size // 4) ** 2 * 16
    if mip0_len != expected0:
        raise ValueError(f"mip 0 is {mip0_len} bytes, expected {expected0}")
    header = bytearray(DDS_HEADER_SIZE)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, MIP_FLAGS)
    struct.pack_into("<II", header, 12, size, size)
    struct.pack_into("<I", header, 20, mip0_len)
    struct.pack_into("<I", header, 28, num_mips)
    struct.pack_into("<II", header, 76, 32, 0x4)
    header[84:88] = b"DXT5"
    struct.pack_into("<I", header, 108, MIP_CAPS)
    return bytes(header) + b"".join(mip_payloads)


def dds_mip0_slice(dds_bytes: bytes) -> tuple[int, int, memoryview]:
    """Return (size, num_mips, view of mip-0 payload) from a DDS buffer."""
    if len(dds_bytes) < DDS_HEADER_SIZE or dds_bytes[:4] != b"DDS ":
        raise ValueError("not a DDS buffer")
    magic, hdr_size, flags, h, w, pitch, depth, mips = struct.unpack_from("<4s7I", dds_bytes, 0)
    if hdr_size != 124 or h != w or w == 0 or (w & (w - 1)):
        raise ValueError(f"unexpected DDS header: size={hdr_size} {w}x{h}")
    fourcc = dds_bytes[84:88]
    if fourcc != b"DXT5":
        raise ValueError(f"unexpected fourcc {fourcc!r}")
    mip0_len = max(1, w // 4) ** 2 * 16
    if len(dds_bytes) < DDS_HEADER_SIZE + mip0_len:
        raise ValueError("DDS buffer shorter than mip 0")
    return w, mips, memoryview(dds_bytes)[DDS_HEADER_SIZE : DDS_HEADER_SIZE + mip0_len]


def misordered_blocks(mip0: bytes, size: int) -> list[int]:
    """Block offsets whose colour endpoints have c0 < c1.

    Valid in DXT5 (always 4-colour RGB) but non-canonical for the old encoder's
    assumptions; kept as a normalization aid, not a corruption detector.
    """
    bad = []
    nblocks = max(1, size // 4) ** 2
    for b in range(nblocks):
        off = b * 16
        c0, c1 = struct.unpack_from("<HH", mip0, off + 8)
        if c0 < c1:
            bad.append(off)
    return bad


def fix_misordered_blocks(mip0: bytes, size: int) -> tuple[bytes, int]:
    """Fix blocks with c0 < c1 by swapping endpoints and remapping indices.

    The old encoder always fitted the 4-colour palette [expand(c0), expand(c1),
    (2c0+c1)/3, (c0+2c1)/3] but could write c0 < c1, which spec decoders read
    as the 3-colour mode with a transparent index. Swapping the endpoints makes
    the spec palette [expand(c1), expand(c0), (2c1+c0)/3, (c1+2c0)/3], i.e.
    entries 0<->1 and 2<->3 of the intended palette — remapping the 2-bit
    indices accordingly restores the intended colours exactly.
    """
    bad = misordered_blocks(mip0, size)
    if not bad:
        return mip0, 0
    buf = bytearray(mip0)
    remap = (1, 0, 3, 2)
    for off in bad:
        c0, c1 = struct.unpack_from("<HH", buf, off + 8)
        struct.pack_into("<HH", buf, off + 8, c1, c0)
        bits = int.from_bytes(buf[off + 12 : off + 16], "little")
        new_bits = 0
        for px in range(16):
            new_bits |= remap[(bits >> (2 * px)) & 3] << (2 * px)
        buf[off + 12 : off + 16] = new_bits.to_bytes(4, "little")
    return bytes(buf), len(bad)


def validate_dxt5_texture(dds_bytes: bytes) -> list[str]:
    """Validate a .texture DDS buffer: header, full mip chain, block ordering."""
    if len(dds_bytes) < DDS_HEADER_SIZE:
        return [f"DDS too short ({len(dds_bytes)} bytes)"]
    magic, hdr_size, flags, h, w, pitch, depth, mips = struct.unpack_from("<4s7I", dds_bytes, 0)
    caps = struct.unpack_from("<I", dds_bytes, 108)[0]
    if magic != b"DDS " or hdr_size != 124:
        return [f"Invalid DDS magic/size ({magic!r}, {hdr_size})"]
    if dds_bytes[84:88] != b"DXT5":
        return [f"unexpected fourcc {dds_bytes[84:88]!r}"]
    errors: list[str] = []
    if h != w or w == 0 or (w & (w - 1)):
        errors.append(f"texture is not square power-of-two ({w}x{h})")
        return errors
    num_mips = mip_count_for(w)
    mip0_len = max(1, w // 4) ** 2 * 16
    expected_total = DDS_HEADER_SIZE + sum(
        max(1, (w >> i) // 4) ** 2 * 16 for i in range(num_mips)
    )
    if mips != num_mips:
        errors.append(f"dwMipMapCount={mips} != expected {num_mips}")
    if flags != MIP_FLAGS:
        errors.append(f"DDS flags=0x{flags:08X} != 0x{MIP_FLAGS:08X}")
    if caps != MIP_CAPS:
        errors.append(f"DDS caps=0x{caps:08X} != 0x{MIP_CAPS:08X}")
    if pitch != mip0_len:
        errors.append(f"dwPitchOrLinearSize={pitch} != mip0 size {mip0_len}")
    if len(dds_bytes) != expected_total:
        errors.append(f"DDS byte length {len(dds_bytes)} != expected {expected_total}")
    # NOTE: c0 < c1 colour endpoints are valid DXT5 (always 4-colour RGB) and
    # are not flagged as corruption here (audit A07).
    return errors


def repair_dxt5_texture(dds_bytes: bytes) -> tuple[bytes, bool]:
    """Return (dds, changed): full mip pyramid, correct flags/caps, ordered endpoints."""
    try:
        size, mips, mip0_view = dds_mip0_slice(dds_bytes)
    except ValueError as exc:
        raise ValueError(f"cannot repair texture: {exc}")
    mip0, fixed_blocks = fix_misordered_blocks(bytes(mip0_view), size)
    num_mips = mip_count_for(size)
    expected_total = DDS_HEADER_SIZE + sum(
        max(1, (size >> i) // 4) ** 2 * 16 for i in range(num_mips)
    )
    struct_ok = (
        mips == num_mips
        and len(dds_bytes) == expected_total
        and struct.unpack_from("<I", dds_bytes, 8)[0] == MIP_FLAGS
        and struct.unpack_from("<I", dds_bytes, 108)[0] == MIP_CAPS
    )
    if struct_ok and fixed_blocks == 0:
        return dds_bytes, False
    payloads = [mip0] + mip_payloads_from_mip0(mip0, size)[1:]
    # keep the original reserved bytes; rewrite the fields that matter
    header = bytearray(dds_bytes[:DDS_HEADER_SIZE])
    struct.pack_into("<I", header, 8, MIP_FLAGS)
    struct.pack_into("<I", header, 20, len(mip0))
    struct.pack_into("<I", header, 28, num_mips)
    struct.pack_into("<I", header, 108, MIP_CAPS)
    return bytes(header) + b"".join(payloads), True
