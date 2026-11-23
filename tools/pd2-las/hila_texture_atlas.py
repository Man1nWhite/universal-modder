"""Fit OfficeSuite's six BC3 texture pairs into Hila's existing suit texture slots.

Native mod_overrides can replace existing resources; it cannot register twelve
new texture names. Both atlases have the same layout, and the diffuse tiles
keep their original resolution, compressed pixels and gloss alpha.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

import dds_encode as dds

WIDTH, HEIGHT = 4096, 2048
GUTTER = 128
# Left, top and side length of the content, in DDS texels. The gutters wrap
# the tile's edges, so interpolation near a UV seam still reads its own tile.
TILES = {
    "body": (128, 128, 1024),
    "suit": (1408, 128, 1024),
    "panties": (2688, 128, 1024),
    "bra": (128, 1408, 512),
    "shoes": (896, 1408, 512),
    "jewelry": (1664, 1408, 512),
}
BLOCK_LEVELS = GUTTER.bit_length() - 2  # last usable gutter is one 4x4 block


def _double_blocks(tile: np.ndarray) -> np.ndarray:
    """Nearest-neighbor 2x upscale of a BC3 tile without changing any endpoints.

    The four child blocks share the parent colors/alphas. Copy each parent
    selector to its four texels in the expanded 8x8 square, preserving even
    the swizzled X normal stored in the BC3 alpha channel.
    """
    by, bx, _ = tile.shape
    blocks = tile.reshape(-1, 16)
    children = np.repeat(blocks[:, None, :], 4, axis=1)
    parent = np.arange(16, dtype=np.uint64).reshape(4, 4).repeat(2, 0).repeat(2, 1)
    parent = parent.reshape(2, 4, 2, 4).transpose(0, 2, 1, 3).reshape(4, 16)
    for bits, offset, start, end in ((3, 2, 0, 8), (2, 12, 12, 16)):
        raw = blocks[:, start:end].copy().view(f"<u{end-start}").ravel().astype(np.uint64)
        selectors = (raw[:, None, None] >> (bits * parent + 8 * (offset-start))) & ((1 << bits) - 1)
        packed = np.sum(selectors << (bits * np.arange(16, dtype=np.uint64)), axis=2, dtype=np.uint64)
        children[:, :, offset:end] = packed.astype("<u8").view(np.uint8).reshape(-1, 4, 8)[:, :, :end-offset]
    return children.reshape(by, bx, 2, 2, 16).transpose(0, 2, 1, 3, 4).reshape(2*by, 2*bx, 16)


def make_atlas(textures: dict[str, bytes], *, normal: bool) -> bytes:
    if textures.keys() != TILES.keys():
        raise ValueError("atlas needs one texture for each OfficeSuite material")
    # Empty space is neutral; none of it falls in a mapped UV island.
    empty = (255, 128, 0, 128) if normal else (0, 0, 0, 0)
    bg = dds.encode_bc3_texels(np.full((1, 16, 4), empty, dtype=np.uint8))[0]
    levels = [np.full((HEIGHT >> (k + 2), WIDTH >> (k + 2), 16), bg, dtype=np.uint8)
              for k in range(BLOCK_LEVELS)]
    for slot, (x, y, side) in TILES.items():
        source = textures[slot]
        src = dds.bc3_levels(source)
        _, w, h = src[0]
        if not (w == h and 4 <= w <= side and (w & (w - 1)) == 0 and len(src) == w.bit_length()):
            raise ValueError(f"{slot}: expected square, full-mip BC3 at up to {side}px")
        shift = side.bit_length() - w.bit_length()
        for level, grid in enumerate(levels):
            b = side >> (level + 2)
            offset, dim, _ = src[max(0, level - shift)]
            n = dim // 4
            tile = np.frombuffer(source, np.uint8, count=n * n * 16, offset=offset).reshape(n, n, 16)
            for _ in range(max(0, shift - level)):
                tile = _double_blocks(tile)
            pad = GUTTER >> (level + 2)
            bx, by = x >> (level + 2), y >> (level + 2)
            grid[by-pad:by+b+pad, bx-pad:bx+b+pad] = np.pad(tile, ((pad, pad), (pad, pad), (0, 0)), mode="wrap")

    # Once the gutters are sub-block sized, filter the last aligned mip as an
    # image rather than copying overlapping blocks. Write a complete pyramid.
    s = BLOCK_LEVELS - 1
    last = dds._dds_header(WIDTH >> s, HEIGHT >> s, b"DXT5") + levels[-1].tobytes()
    image = Image.fromarray(dds.decode_bc3_level(last))
    tail = []
    while image.size != (1, 1):
        image = image.resize(tuple(max(1, dim // 2) for dim in image.size), Image.Resampling.BOX)
        tail.append(np.asarray(image))
    return (dds._dds_header(WIDTH, HEIGHT, b"DXT5", mips=WIDTH.bit_length())
            + b"".join(level.tobytes() for level in levels) + dds.bc3_dds_from_levels(tail)[128:])


def atlas_uvs(uv: np.ndarray, faces: np.ndarray, slot: str) -> np.ndarray:
    """Affinely map a donor atom's UV islands into one atlas tile.

    OfficeSuite's V can be outside [0, 1], but each triangle stays inside one
    repeat. Reject a donor that straddles repeats: applying modulo to *that*
    triangle's vertices would paint a stripe across it instead of wrapping.
    The codec negates V on disk; tile placement is in disk/sampler coordinates.
    """
    disk = uv * (1, -1)
    offsets = np.floor(disk)
    if not (offsets[faces] == offsets[faces[:, :1]]).all():
        raise ValueError(f"{slot}: triangle crosses a texture repeat")
    x, y, side = TILES[slot]
    return (((disk - offsets) * side + (x, y)) / (WIDTH, HEIGHT)) * (1, -1)
