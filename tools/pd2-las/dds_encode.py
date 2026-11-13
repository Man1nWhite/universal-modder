"""Minimal DDS writers for the LAS pack: RGBA -> BC3 (DXT5) and uncompressed.

Two encoders live here.

`rgba_to_bc3_dds` is the naive one (the two colour endpoints are the corners of
the block's bounding box). It writes one level and is enough for UI icons and
previews.

`encode_bc3_blocks` is for texels that end up on a model: it tries every pair of
a block's own colours as the endpoints and keeps the pair with the least error.
`bc3_dds_from_levels` writes a whole mip pyramid with it.

Production material textures should come from `vtf.to_dds()` (the original DXT5
payloads) and not be re-encoded. Where the build has to change a texture, it
re-encodes the blocks it changed and keeps the rest (`build_las.py`).

The layout of a block is Microsoft's ("Block compression (Direct3D 10)", BC3):
alpha_0, alpha_1 and sixteen 3-bit codes, where code 0 is alpha_0, code 1 is
alpha_1 and codes 2 to 7 run from alpha_0 towards alpha_1; then two RGB565
colours and sixteen 2-bit codes. The colour endpoints are always written with
c0 >= c1: some decoders read c0 < c1 as the three-colour mode with a transparent
code, which renders as holes (this defect bit the retired pipeline).
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
        # in code order: 0 is alpha_0, 1 is alpha_1, 2..7 run from the one to the
        # other. (This list used to be in ramp order, alpha_1 last, with the
        # position written as the code: a texel meant to be the minimum then
        # decoded one step above it, and one meant for the step below the
        # maximum decoded as the minimum.)
        levels = np.array(
            [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
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


def srgb_to_linear(value: np.ndarray) -> np.ndarray:
    """sRGB-encoded values in 0..1 as linear light (IEC 61966-2-1)."""
    value = np.asarray(value, dtype=np.float64)
    return np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(value: np.ndarray) -> np.ndarray:
    """Linear light in 0..1 as sRGB-encoded values; out-of-range input is clipped."""
    value = np.clip(np.asarray(value, dtype=np.float64), 0.0, 1.0)
    return np.where(value <= 0.0031308, value * 12.92, 1.055 * value ** (1.0 / 2.4) - 0.055)


def box_reduce(image: np.ndarray, factor: int) -> np.ndarray:
    """Every `factor` x `factor` texels averaged into one, as float64.

    This is what a mip level is: each of its texels stands for the area the
    texels above it covered. Colour has to be averaged as light, so convert with
    `srgb_to_linear` first; data such as gloss is averaged as it is.
    """
    height, width = image.shape[:2]
    if height % factor or width % factor:
        raise ValueError(f"{width}x{height} does not divide by {factor}")
    image = np.asarray(image, dtype=np.float64)
    return image.reshape(height // factor, factor, width // factor, factor, -1).mean(axis=(1, 3))


#: every pair of the 16 texels of a block: the candidates for its two colour endpoints
_TEXEL_PAIRS = np.array([(i, j) for i in range(16) for j in range(i + 1, 16)])


def _expand_565(value: np.ndarray) -> np.ndarray:
    """RGB565 as 8 bits per channel, the way a decoder widens it (bit replication)."""
    r, g, b = (value >> 11) & 31, (value >> 5) & 63, value & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=-1)


def encode_bc3_texels(texels: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """DXT5 blocks for (n, 16, 4) RGBA texels, each block row by row: (n, 16) uint8.

    Colour. A block holds four colours on one line between its two endpoints, so
    the choice of that line is the whole encoding. Here the endpoints are two of
    the block's own colours: all 120 pairs are tried and the pair that reproduces
    the 16 texels with the least squared error is kept. The corners of the
    bounding box (`rgba_to_bc3_dds`), or the brightest texel and the one farthest
    from it, put a grey line through a block that is mostly blue iris with some
    black pupil and some grey sclera, and the iris comes out grey; the search
    keeps the iris and gives up the few sclera texels. Ties go to the first pair
    and the arithmetic is integer, so the bytes do not depend on the machine.

    ``weights`` is an (n, 16) array of whole numbers: how much the colour error
    of each texel counts when the pair is chosen. Without it every texel counts
    the same. Where a block cannot hold everything, the weights say what it has
    to hold: in an 8x8 level of the eye texture a block has three iris texels and
    thirteen of sclera, most of which the lids cover.

    Alpha. The eight-value mode with the block's maximum and minimum as alpha_0
    and alpha_1, and each texel on the nearest of the eight values.
    """
    texels = np.asarray(texels)
    if texels.ndim != 3 or texels.shape[1:] != (16, 4):
        raise ValueError("expected (n, 16, 4) RGBA texels")
    texels = texels.astype(np.int32)
    count = len(texels)
    if weights is None:
        weights = np.ones((count, 16), dtype=np.int64)
    else:
        weights = np.asarray(weights)
        if weights.shape != (count, 16) or not np.issubdtype(weights.dtype, np.integer) or (weights < 0).any():
            raise ValueError("weights have to be (n, 16) whole numbers, none below zero")
        weights = weights.astype(np.int64)
    out = np.zeros((count, 16), dtype=np.uint8)

    alpha = texels[:, :, 3]
    a0, a1 = alpha.max(axis=1), alpha.min(axis=1)
    # code k of 2..7 stands for ((8 - k) * alpha_0 + (k - 1) * alpha_1) / 7. A GPU
    # interpolates that as a real number, so the nearest value is found without
    # rounding it: everything is compared in sevenths.
    sevenths = np.stack([7 * a0, 7 * a1] + [(8 - k) * a0 + (k - 1) * a1 for k in range(2, 8)], axis=1)
    code = np.abs(7 * alpha[:, :, None] - sevenths[:, None, :]).argmin(axis=2).astype(np.uint64)
    code[a0 == a1] = 0
    bits = (code << (3 * np.arange(16, dtype=np.uint64))[None, :]).sum(axis=1, dtype=np.uint64)
    out[:, 0], out[:, 1] = a0, a1
    for k in range(6):
        out[:, 2 + k] = (bits >> np.uint64(8 * k)) & np.uint64(0xFF)

    rgb = texels[:, :, :3]
    # each texel's colour as the nearest RGB565 (dropping the low bits instead
    # would leave 200 at 206 where 198 is on offer)
    packed = ((((rgb[:, :, 0] * 31 + 127) // 255) << 11) | (((rgb[:, :, 1] * 63 + 127) // 255) << 5)
              | ((rgb[:, :, 2] * 31 + 127) // 255))
    first, second = _TEXEL_PAIRS[:, 0], _TEXEL_PAIRS[:, 1]
    for start in range(0, count, 512):                  # 512 blocks at a time: about 50 MB
        block = slice(start, start + 512)
        one, other = packed[block][:, first], packed[block][:, second]
        c0, c1 = np.maximum(one, other), np.minimum(one, other)
        p0, p1 = _expand_565(c0), _expand_565(c1)
        colours = np.stack([p0, p1, (2 * p0 + p1 + 1) // 3, (p0 + 2 * p1 + 1) // 3], axis=2)
        distance = ((rgb[block][:, None, :, None, :] - colours[:, :, None, :, :]) ** 2).sum(axis=4)
        best = (distance.min(axis=3) * weights[block][:, None, :]).sum(axis=2).argmin(axis=1)
        rows = np.arange(len(best))
        c0, c1 = c0[rows, best], c1[rows, best]
        code = distance[rows, best].argmin(axis=2).astype(np.uint32)
        code[c0 == c1] = 0
        bits = (code << (2 * np.arange(16, dtype=np.uint32))[None, :]).sum(axis=1, dtype=np.uint32)
        target = out[block]
        target[:, 8], target[:, 9] = c0 & 0xFF, c0 >> 8
        target[:, 10], target[:, 11] = c1 & 0xFF, c1 >> 8
        for k in range(4):
            target[:, 12 + k] = (bits >> np.uint32(8 * k)) & np.uint32(0xFF)
    return out


def pad_to_blocks(rgba: np.ndarray) -> np.ndarray:
    """The image with each side brought up to a multiple of four by repeating its edge.

    A level smaller than a block still fills a block. What fills the rest decides
    the block's endpoints, and zeros would pull one of them to black.
    """
    height, width = rgba.shape[:2]
    return np.pad(rgba, ((0, -height % 4), (0, -width % 4), (0, 0)), mode="edge")


def image_to_texels(rgba: np.ndarray) -> np.ndarray:
    """An (H, W, 4) image whose sides are multiples of four as (n, 16, 4) blocks, row by row."""
    height, width = rgba.shape[:2]
    if rgba.ndim != 3 or rgba.shape[2] != 4 or height % 4 or width % 4:
        raise ValueError("expected (H, W, 4) RGBA with sides that are multiples of 4")
    return rgba.reshape(height // 4, 4, width // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)


def bc3_levels(dds: bytes) -> list[tuple[int, int, int]]:
    """(byte offset, width, height) of every mip level a DXT5 DDS declares."""
    if dds[:4] != b"DDS " or dds[84:88] != b"DXT5":
        raise ValueError("not a DXT5 DDS")
    height, width = struct.unpack_from("<2I", dds, 12)
    count = max(1, struct.unpack_from("<I", dds, 28)[0])
    levels, offset = [], 128
    for level in range(count):
        w, h = max(1, width >> level), max(1, height >> level)
        levels.append((offset, w, h))
        offset += ((w + 3) // 4) * ((h + 3) // 4) * 16
    if offset != len(dds):
        raise ValueError(f"the header declares {count} levels ({offset} bytes), the file has {len(dds)}")
    return levels


def decode_bc3_level(dds: bytes, level: int = 0) -> np.ndarray:
    """One mip level of a DXT5 DDS as (h, w, 4) uint8 RGBA, decoded by Pillow."""
    import io

    from PIL import Image

    offset, width, height = bc3_levels(dds)[level]
    across, down = (width + 3) // 4 * 4, (height + 3) // 4 * 4
    payload = dds[offset : offset + across // 4 * (down // 4) * 16]
    image = Image.open(io.BytesIO(_dds_header(across, down, b"DXT5") + payload))
    image.load()
    return np.asarray(image.convert("RGBA"), dtype=np.uint8)[:height, :width].copy()


def bc3_dds_from_levels(levels: list[np.ndarray], weights: list[np.ndarray] | None = None) -> bytes:
    """A DXT5 DDS with the given mip levels, level 0 first, in the game's header shape.

    The caller decides what each level shows (see `box_reduce`); every level is
    encoded with `encode_bc3_texels`. The chain has to be complete: each side
    halves, never below one texel, down to 1x1. ``weights`` gives, for each
    level, an (h, w) array of whole numbers: how much each texel's colour counts.
    """
    height, width = levels[0].shape[:2]
    expected = [(max(1, height >> k), max(1, width >> k)) for k in range(max(height, width).bit_length())]
    if [level.shape[:2] for level in levels] != expected:
        raise ValueError(f"levels {[level.shape[:2] for level in levels]} are not the full chain {expected}")
    if weights is not None and [w.shape for w in weights] != expected:
        raise ValueError("weights have to match the levels, texel for texel")
    payload = b""
    for index, level in enumerate(levels):
        texels = image_to_texels(pad_to_blocks(np.asarray(level, dtype=np.uint8)))
        count = None
        if weights is not None:
            padded = pad_to_blocks(np.asarray(weights[index])[..., None])
            count = padded.reshape(padded.shape[0] // 4, 4, padded.shape[1] // 4, 4).transpose(0, 2, 1, 3).reshape(-1, 16)
        payload += encode_bc3_texels(texels, count).tobytes()
    return _dds_header(width, height, b"DXT5", mips=len(levels)) + payload


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
