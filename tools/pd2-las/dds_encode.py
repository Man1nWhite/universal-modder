"""Minimal DDS writers for the LAS pack: RGBA -> BC3 (DXT5) and uncompressed.

A naive block encoder (min/max endpoints) is enough for UI icons and previews;
production material textures should come from `vtf.to_dds()` (the original DXT5
payloads) and never be re-encoded. The DXT5 colour-endpoint order is always
emitted with c0 > c1 — decoders read c0 <= c1 as the 3-colour + transparent
index mode, which renders as holes (this defect bit the retired pipeline).
"""
from __future__ import annotations

import struct

import numpy as np


def _dds_header(width: int, height: int, fourcc: bytes | None, mips: int = 1) -> bytes:
    dds_flags = 0x1 | 0x2 | 0x4 | 0x1000  # CAPS | HEIGHT | WIDTH | PIXELFORMAT
    caps = 0x1000  # TEXTURE
    if fourcc is not None:
        dds_flags |= 0x80000  # LINEARSIZE
        pf_flags = 0x4  # FOURCC
        rgb_bits = 0
        masks = (0, 0, 0, 0)
        pitch = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * 16
    else:
        dds_flags |= 0x8  # PITCH
        pf_flags = 0x1 | 0x40 | 0x41  # ALPHAPIXELS | RGB
        rgb_bits = 32
        masks = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)  # BGRA8888
        pitch = width * 4
    if mips > 1:
        dds_flags |= 0x20000
        caps |= 0x8 | 0x400000
    pf = struct.pack(
        "<II4sIIIII", 32, pf_flags, fourcc or b"\x00" * 4, rgb_bits, *masks
    )
    header = (
        b"DDS "
        + struct.pack("<7I", 124, dds_flags, height, width, pitch, 0, mips)
        + b"\x00" * 44
        + pf
        + struct.pack("<4I", caps, 0, 0, 0)
        + b"\x00" * 4
    )
    assert len(header) == 128
    return header


def _encode_bc3_block(block: np.ndarray) -> bytes:
    """Encode one 4x4 RGBA block (uint8) as DXT5."""
    rgb = block[:, :, :3].astype(np.float64).reshape(-1, 3)
    alpha = block[:, :, 3].reshape(-1)

    a_min = int(alpha.min())
    a_max = int(alpha.max())
    # 8-alpha block: endpoints a_max > a_min with 6 interpolated values.
    a0, a1 = a_max, a_min
    if a0 == a1:
        a_data = bytes([a0, a1]) + b"\x00" * 6
    else:
        levels = np.array(
            [a0] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)] + [a1]
        )
        alpha_bits = 0
        for i, a in enumerate(alpha):
            idx = int(np.argmin(np.abs(levels - a)))
            alpha_bits |= idx << (3 * i)
        a_data = bytes([a0, a1]) + alpha_bits.to_bytes(6, "little")

    lo = rgb.min(axis=0)
    hi = rgb.max(axis=0)

    def to565(c):
        return ((int(c[0]) >> 3) << 11) | ((int(c[1]) >> 2) << 5) | (int(c[2]) >> 3)

    e0, e1 = to565(hi), to565(lo)
    if e0 < e1:
        e0, e1 = e1, e0  # enforce c0 > c1 -> 4-colour mode
    if e0 == e1:
        colors = np.array(
            [
                [(e0 >> 11) << 3, ((e0 >> 5) & 0x3F) << 2, (e0 & 0x1F) << 3],
            ] * 4,
            dtype=np.float64,
        )
    else:
        c0_rgb = np.array([(e0 >> 11) << 3, ((e0 >> 5) & 0x3F) << 2, (e0 & 0x1F) << 3])
        c1_rgb = np.array([(e1 >> 11) << 3, ((e1 >> 5) & 0x3F) << 2, (e1 & 0x1F) << 3])
        colors = np.stack(
            [
                c0_rgb,
                c1_rgb,
                (2 * c0_rgb + c1_rgb) / 3,
                (c0_rgb + 2 * c1_rgb) / 3,
            ]
        )
    color_bits = 0
    for i, px in enumerate(rgb):
        idx = int(np.argmin(((colors - px) ** 2).sum(axis=1)))
        color_bits |= idx << (2 * i)
    return a_data + struct.pack("<HHI", e0, e1, color_bits)


def rgba_to_bc3_dds(rgba: np.ndarray) -> bytes:
    """Encode an (H, W, 4) uint8 RGBA array as a single-mip DXT5 DDS."""
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("expected (H, W, 4) uint8 RGBA")
    height, width = rgba.shape[:2]
    padded = np.zeros(((height + 3) // 4 * 4, (width + 3) // 4 * 4, 4), dtype=np.uint8)
    padded[:height, :width] = rgba
    out = bytearray()
    for by in range(0, padded.shape[0], 4):
        for bx in range(0, padded.shape[1], 4):
            out += _encode_bc3_block(padded[by : by + 4, bx : bx + 4])
    return _dds_header(width, height, b"DXT5") + bytes(out)


def rgba_to_bgra_dds(rgba: np.ndarray) -> bytes:
    """Write an (H, W, 4) uint8 RGBA array as uncompressed BGRA8888 DDS."""
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("expected (H, W, 4) uint8 RGBA")
    height, width = rgba.shape[:2]
    bgra = rgba[:, :, [2, 1, 0, 3]]
    return _dds_header(width, height, None) + bgra.tobytes()
