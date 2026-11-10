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


def _enforce_c0_ge_c1(blocks: np.ndarray) -> None:
    """In-place enforce c0 >= c1 on DXT5 RGB565 endpoints (bytes 8..16)."""
    c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
    c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
    swap = c0 < c1
    if not np.any(swap):
        return
    c_bits = (
        blocks[:, 12].astype(np.uint32)
        | (blocks[:, 13].astype(np.uint32) << 8)
        | (blocks[:, 14].astype(np.uint32) << 16)
        | (blocks[:, 15].astype(np.uint32) << 24)
    )
    e0 = np.where(swap, c1, c0)
    e1 = np.where(swap, c0, c1)
    new_bits = np.where(swap, c_bits ^ np.uint32(0x55555555), c_bits)
    new_bits[e0 == e1] = 0
    blocks[:, 8] = (e0 & 0xFF).astype(np.uint8)
    blocks[:, 9] = ((e0 >> 8) & 0xFF).astype(np.uint8)
    blocks[:, 10] = (e1 & 0xFF).astype(np.uint8)
    blocks[:, 11] = ((e1 >> 8) & 0xFF).astype(np.uint8)
    for b in range(4):
        blocks[:, 12 + b] = ((new_bits >> np.uint32(8 * b)) & np.uint32(0xFF)).astype(np.uint8)


def attenuate_dxt5_alpha_from_normal(
    df_dds: bytes, nm_dds: bytes, scale: float, max_a: int
) -> bytes:
    """Copy attenuated specular alpha blocks from nm_dds into df_dds across all mips.

    PAYDAY 2's ``DIFFUSE_TEXTURE:NORMALMAP`` shader reads the specular/gloss
    mask from the diffuse texture's alpha channel (0 = matte, 255 = full mirror
    gloss), whereas Source stores the phong mask in the normal map's alpha
    channel and leaves diffuse alpha at 255. Operating directly on the 8-byte
    DXT5 alpha blocks preserves 100% of the original DXT5 RGB colour blocks.
    """
    hdr = df_dds[:128]
    w_df = int.from_bytes(df_dds[16:20], "little")
    w_nm = int.from_bytes(nm_dds[16:20], "little")
    df_blocks = np.frombuffer(df_dds[128:], dtype=np.uint8).reshape(-1, 16).copy()
    nm_blocks = np.frombuffer(nm_dds[128:], dtype=np.uint8).reshape(-1, 16).copy()

    s_int = int(round(scale * 256))
    a0 = np.minimum(max_a, (nm_blocks[:, 0].astype(np.int32) * s_int) >> 8).astype(np.uint8)
    a1 = np.minimum(max_a, (nm_blocks[:, 1].astype(np.int32) * s_int) >> 8).astype(np.uint8)
    nm_blocks[:, 0] = a0
    nm_blocks[:, 1] = a1
    nm_blocks[a0 == a1, 2:8] = 0

    if len(df_blocks) == len(nm_blocks):
        df_blocks[:, :8] = nm_blocks[:, :8]
    elif w_df == 2 * w_nm:
        outfit_nm = w_nm // 4
        n0_nm = outfit_nm * outfit_nm
        n0_df = (2 * outfit_nm) * (2 * outfit_nm)
        mip0_nm = nm_blocks[:n0_nm, :8].reshape(outfit_nm, outfit_nm, 8)
        mip0_df = np.repeat(np.repeat(mip0_nm, 2, axis=0), 2, axis=1).reshape(n0_df, 8)
        df_blocks[:n0_df, :8] = mip0_df
        rem = len(df_blocks) - n0_df
        df_blocks[n0_df:, :8] = nm_blocks[:rem, :8]
    else:
        df_blocks[:, :8] = nm_blocks[-len(df_blocks) :, :8]
    _enforce_c0_ge_c1(df_blocks)
    return hdr + df_blocks.tobytes()


def set_dxt5_constant_alpha(df_dds: bytes, alpha_val: int) -> bytes:
    """Set a constant alpha value across all DXT5 blocks while preserving RGB."""
    hdr = df_dds[:128]
    blocks = np.frombuffer(df_dds[128:], dtype=np.uint8).reshape(-1, 16).copy()
    blocks[:, 0] = alpha_val
    blocks[:, 1] = alpha_val
    blocks[:, 2:8] = 0
    _enforce_c0_ge_c1(blocks)
    return hdr + blocks.tobytes()


def _dxt5_alpha_decode(b8: np.ndarray) -> np.ndarray:
    """Decode one DXT5 alpha block (8 bytes) to a 4x4 float array."""
    a0, a1 = int(b8[0]), int(b8[1])
    if a0 > a1:
        pal = np.array([(a0 * (7 - i) + a1 * i) / 7 for i in range(8)])
    else:
        pal = np.array([(a0 * (5 - i) + a1 * i) / 5 for i in range(6)] + [0, 255])
    bits = int.from_bytes(bytes(b8[2:8]), "little")
    idx = np.array([(bits >> (3 * i)) & 7 for i in range(16)], dtype=np.int64)
    return pal[idx].reshape(4, 4)


def _dxt5_alpha_encode(a44: np.ndarray) -> bytes:
    """Encode a 4x4 alpha array as one DXT5 alpha block (8-value mode)."""
    a = np.clip(np.rint(a44), 0, 255).astype(np.int32).reshape(16)
    a0, a1 = int(a.max()), int(a.min())
    if a0 == a1:
        bits = 0
    else:
        pal = np.array([a0 + (a1 - a0) * i / 7 for i in range(8)])
        idx = np.abs(pal[None, :] - a[:, None].astype(np.float64)).argmin(axis=1)
        bits = 0
        for i in range(16):
            bits |= int(idx[i]) << (3 * i)
    return bytes([a0, a1]) + bits.to_bytes(6, "little")


def attenuate_dxt5_alpha_by_block_mask(
        df_dds: bytes, mask: np.ndarray, atten: float) -> bytes:
    """Scale DXT5 alpha by ``1 - atten * mask`` per 4x4 block, RGB untouched.

    ``mask`` is a (h//4, w//4) float array in 0..1 — one value per BC block.
    PD2's ``DIFFUSE_TEXTURE:NORMALMAP`` shader reads gloss from diffuse alpha,
    so this darkens the specular sheen in the masked regions (sleeves) without
    touching colour blocks or alpha elsewhere.
    """
    hdr = df_dds[:128]
    h = int.from_bytes(df_dds[12:16], "little")
    w = int.from_bytes(df_dds[16:20], "little")
    bh, bw = h // 4, w // 4
    if mask.shape != (bh, bw):
        raise SystemExit(f"alpha mask shape {mask.shape} != block grid {(bh, bw)}")
    blocks = np.frombuffer(df_dds[128:], dtype=np.uint8).reshape(-1, 16).copy()
    flat = mask.reshape(-1)
    touched = 0
    for bi in np.where(flat > 0.004)[0]:
        fac = 1.0 - atten * float(flat[bi])
        alpha = _dxt5_alpha_decode(blocks[bi][:8]) * fac
        blocks[bi][:8] = np.frombuffer(
            _dxt5_alpha_encode(alpha), dtype=np.uint8)
        touched += 1
    return hdr + blocks.tobytes()


def swizzle_source_normal_dxt5_to_pd2(nm_dds: bytes, invert_y: bool = True) -> bytes:
    """Swizzle UE3/ME2-derived Source DXT5 normal map (R=ny_down, G=nx_right, B=nz) to PD2 DXT5nm (R=255, G=255-ny_down, B=0, A=nx_right)."""
    hdr = nm_dds[:128]
    blocks = np.frombuffer(nm_dds[128:], dtype=np.uint8).reshape(-1, 16)
    n = blocks.shape[0]
    out = np.zeros((n, 16), dtype=np.uint8)

    c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
    c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
    c_bits = (
        blocks[:, 12].astype(np.uint32)
        | (blocks[:, 13].astype(np.uint32) << 8)
        | (blocks[:, 14].astype(np.uint32) << 16)
        | (blocks[:, 15].astype(np.uint32) << 24)
    )

    # Source VTFs extracted from UE3/ME2 store horizontal X in Green and vertical Y_down in Red.
    nx0_8 = ((c0 >> 5) & 63) * 255 // 63
    nx1_8 = ((c1 >> 5) & 63) * 255 // 63
    ny0_5 = (c0 >> 11) & 31
    ny1_5 = (c1 >> 11) & 31
    if invert_y:
        ny0_5 = 31 - ny0_5
        ny1_5 = 31 - ny1_5
    g0_6 = (ny0_5 * 63 + 15) // 31
    g1_6 = (ny1_5 * 63 + 15) // 31

    swap_r = nx0_8 < nx1_8
    a0 = np.where(swap_r, nx1_8, nx0_8).astype(np.uint8)
    a1 = np.where(swap_r, nx0_8, nx1_8).astype(np.uint8)
    out[:, 0] = a0
    out[:, 1] = a1

    lut_no_swap = np.array([0, 1, 4, 5], dtype=np.uint64)
    lut_swap = np.array([1, 0, 5, 4], dtype=np.uint64)
    a_bits = np.zeros(n, dtype=np.uint64)
    for px in range(16):
        ci = (c_bits >> np.uint32(2 * px)) & np.uint32(3)
        ai = np.where(swap_r, lut_swap[ci], lut_no_swap[ci])
        a_bits |= ai << np.uint64(3 * px)
    a_bits[a0 == a1] = 0
    for b in range(6):
        out[:, 2 + b] = ((a_bits >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.uint8)

    swap_g = g0_6 < g1_6
    g_hi = np.where(swap_g, g1_6, g0_6)
    g_lo = np.where(swap_g, g0_6, g1_6)
    e0 = (31 << 11) | (g_hi << 5)
    e1 = (31 << 11) | (g_lo << 5)
    new_c_bits = np.where(swap_g, c_bits ^ np.uint32(0x55555555), c_bits)
    new_c_bits[e0 == e1] = 0

    out[:, 8] = (e0 & 0xFF).astype(np.uint8)
    out[:, 9] = ((e0 >> 8) & 0xFF).astype(np.uint8)
    out[:, 10] = (e1 & 0xFF).astype(np.uint8)
    out[:, 11] = ((e1 >> 8) & 0xFF).astype(np.uint8)
    for b in range(4):
        out[:, 12 + b] = ((new_c_bits >> np.uint32(8 * b)) & np.uint32(0xFF)).astype(np.uint8)

    return hdr + out.tobytes()


def swizzle_standard_normal_dxt5_to_pd2(
    nm_dds: bytes, invert_y: bool = True
) -> bytes:
    """Swizzle standard DirectX DXT5 normal map (R=nx_right, G=ny_down, B=nz)
    to PAYDAY 2 DXT5nm (R=255, G=255-ny_down, B=0, A=nx_right) in BC3 block space.

    - Alpha (Nx <- R): expands each block's exact 4-entry BC3 Red palette,
      fits 8-bit endpoints (a0 >= a1) to the 16 block pixels' actual min/max,
      and assigns nearest 8-entry 3-bit alpha indices.
    - Green (Ny): exact 6-bit -> 6-bit endpoint bijection (63 - g when invert_y)
      with lossless 2-bit index permutation (c_bits ^ 0x55555555 when swapped)
      so e0 >= e1 (R5=31, B5=0) holds on every block with zero quantization loss.
    - Red is forced to 255 (R5 = 31) and Blue to 0 (B5 = 0).
    """
    hdr = nm_dds[:128]
    blocks = np.frombuffer(nm_dds[128:], dtype=np.uint8).reshape(-1, 16)
    n = blocks.shape[0]
    out = np.zeros((n, 16), dtype=np.uint8)

    c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
    c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
    c_bits = (
        blocks[:, 12].astype(np.uint32)
        | (blocks[:, 13].astype(np.uint32) << 8)
        | (blocks[:, 14].astype(np.uint32) << 16)
        | (blocks[:, 15].astype(np.uint32) << 24)
    )

    # 1. Alpha <- Source Red (nx_right)
    r0 = ((c0 >> 11) & 31) * 255 // 31
    r1 = ((c1 >> 11) & 31) * 255 // 31
    pal_r = np.stack([r0, r1, (2 * r0 + r1) // 3, (r0 + 2 * r1) // 3], axis=1)
    shifts_c = (2 * np.arange(16, dtype=np.uint32))[None, :]
    ci = (c_bits[:, None] >> shifts_c) & np.uint32(3)
    r_px = np.take_along_axis(pal_r, ci.astype(np.int64), axis=1)

    a0 = r_px.max(axis=1)
    a1 = r_px.min(axis=1)
    out[:, 0] = a0.astype(np.uint8)
    out[:, 1] = a1.astype(np.uint8)

    pal_a = np.empty((n, 8), dtype=np.int32)
    pal_a[:, 0] = a0
    pal_a[:, 1] = a1
    for i in range(1, 7):
        pal_a[:, i + 1] = ((7 - i) * a0 + i * a1) // 7
    idx_a = np.abs(r_px[:, :, None] - pal_a[:, None, :]).argmin(axis=2).astype(np.uint64)
    idx_a[a0 == a1] = 0
    shifts_a = (3 * np.arange(16, dtype=np.uint64))[None, :]
    a_bits = (idx_a << shifts_a).sum(axis=1, dtype=np.uint64)
    for b in range(6):
        out[:, 2 + b] = ((a_bits >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.uint8)

    # 2. Green <- Source Green (ny_down, flipped if invert_y), R=255, B=0
    g0 = (c0 >> 5) & 63
    g1 = (c1 >> 5) & 63
    if invert_y:
        g0 = 63 - g0
        g1 = 63 - g1
    swap_g = g0 < g1
    g_hi = np.where(swap_g, g1, g0)
    g_lo = np.where(swap_g, g0, g1)
    e0 = (31 << 11) | (g_hi << 5)
    e1 = (31 << 11) | (g_lo << 5)
    new_c_bits = np.where(swap_g, c_bits ^ np.uint32(0x55555555), c_bits)
    new_c_bits[e0 == e1] = 0

    out[:, 8] = (e0 & 0xFF).astype(np.uint8)
    out[:, 9] = ((e0 >> 8) & 0xFF).astype(np.uint8)
    out[:, 10] = (e1 & 0xFF).astype(np.uint8)
    out[:, 11] = ((e1 >> 8) & 0xFF).astype(np.uint8)
    for b in range(4):
        out[:, 12 + b] = ((new_c_bits >> np.uint32(8 * b)) & np.uint32(0xFF)).astype(np.uint8)

    return hdr + out.tobytes()
