#!/usr/bin/env python3
"""Pull Geralt's beard out of the shipped head atlas as textures of its own.

`dist/Geralt/Geralt_over_Rust.zip` ships one 2048x2048 head atlas
(`npc_criminal_wild_1_head_df.texture` and `_nm`), assembled from the Witcher 3
port's own maps by `build_joy_head_mods.build_geralt_rust_mod`. The beard is a
rectangle of it, not a texture of its own:

    1024..1536 rows, 1024..2048 columns   (v 0.50..0.75, u 0.50..1.00)

a 1024x512 native `beard_d` (colour, with the hair's alpha cutout) and the
matching `beard_n` in Diesel's packed normal layout (X in alpha, Y in green).
Anyone reusing Geralt's beard in another mod, or in another engine, needs those
two pictures and nothing else from the atlas, so this writes them out:

    references/textures/geralt_beard_df.png   1024x512 RGBA - colour + cutout
    references/textures/geralt_beard_nm.png   1024x512 RGBA - PD2 normal layout
    references/textures/geralt_beard_df.dds   the same colour as DXT5, full mips
    references/textures/geralt_beard_nm.dds   the same normal as DXT5, full mips

The crops are read back out of the tracked pack, so what they hold is what the
pack ships; the DDS files are encoded with the pack's own encoder. Nothing in
`dist/` changes: this only reads it. Run it again after a `heads` rebuild.

    python tools/extract_beard_textures.py
    python tools/extract_beard_textures.py --out build/geralt-beard   # elsewhere
"""
from __future__ import annotations

import argparse
import io
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las"), str(ROOT / "tools" / "pd2-port")]

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import dds  # noqa: E402  (the pack's DXT5 writer)
import dds_encode  # noqa: E402  (its edge padding, for levels smaller than a block)

DEFAULT_PACK = ROOT / "dist" / "Geralt" / "Geralt_over_Rust.zip"
DEFAULT_OUT = ROOT / "references" / "textures"
UNIT = "units/pd2_dlc_wild/characters/npc_criminals_wild_1"
#: the beard's rectangle in the atlas: 1024..1536 rows, 1024..2048 columns
BEARD = (1024, 1536, 1024, 2048)
#: the atlas is written for a cutout material at this reference alpha
ALPHA_REF = 0.05


def read_atlas(pack: Path, suffix: str) -> np.ndarray:
    """One of the pack's head atlases as an (2048, 2048, 4) uint8 array."""
    with zipfile.ZipFile(pack) as z:
        name = next(n for n in z.namelist() if n.endswith(f"npc_criminal_wild_1_head_{suffix}.texture"))
        with Image.open(io.BytesIO(z.read(name))) as image:
            atlas = np.asarray(image.convert("RGBA")).copy()
    if atlas.shape != (2048, 2048, 4):
        raise SystemExit(f"{pack.name}: the head {suffix} atlas is {atlas.shape}, expected 2048x2048 RGBA")
    return atlas


def beard_cutout(df: np.ndarray) -> np.ndarray:
    """The beard's alpha as a 0/255 cutout: it is 24 under a hair and 0 off one."""
    return np.where(df[..., 3] > int(round(ALPHA_REF * 255)), 255, 0).astype(np.uint8)


def crop(atlas: np.ndarray) -> np.ndarray:
    y0, y1, x0, x1 = BEARD
    return atlas[y0:y1, x0:x1]


def write_outputs(pack: Path, out: Path) -> list[Path]:
    """Write the four files; return the paths, PNGs first."""
    out.mkdir(parents=True, exist_ok=True)
    df, nm = crop(read_atlas(pack, "df")), crop(read_atlas(pack, "nm"))
    written: list[Path] = []

    df_png = out / "geralt_beard_df.png"
    df_png.write_bytes(_png(np.dstack([df[..., :3], beard_cutout(df)])))
    written.append(df_png)

    nm_png = out / "geralt_beard_nm.png"
    nm_png.write_bytes(_png(nm))
    written.append(nm_png)

    # DXT5, full mip chain, exactly as the pack encodes its textures
    df_dds = out / "geralt_beard_df.dds"
    df_dds.write_bytes(_dds(np.dstack([df[..., :3], beard_cutout(df)])))
    written.append(df_dds)

    nm_dds = out / "geralt_beard_nm.dds"
    nm_dds.write_bytes(_dds(nm))
    written.append(nm_dds)
    return written


def _halve(level: np.ndarray) -> np.ndarray:
    """Average a 2x1 (or 1x2) level to 1x1, rounding as `dds.downsample2x2` does."""
    arr = np.asarray(level, dtype=np.float32)
    axis = 0 if arr.shape[0] == 2 else 1
    return (arr.mean(axis=axis, keepdims=True) + 0.5).astype(np.uint8)


def _png(rgba: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(rgba, dtype=np.uint8), mode="RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


def _dds(rgba: np.ndarray) -> bytes:
    """A DXT5 DDS with the full mip chain for a 1024x512 image.

    `dds.pack_dds` takes one side and assumes a square texture, so the header is
    written here for the two dimensions the image has. The levels are the box
    averages `dds.downsample2x2` makes, down to 1x1.
    """
    height, width = rgba.shape[:2]
    levels = [rgba]
    while (levels[-1].shape[0], levels[-1].shape[1]) != (1, 1):
        level = levels[-1]
        if 1 in (level.shape[0], level.shape[1]):
            # 2x1 and 1x1 are a pair of texels, not a block: halve the other side
            half = _halve(level)
        else:
            half = dds.downsample2x2(level)
        levels.append(half)
    # a level smaller than a block still fills one; its edge is repeated, as the build does
    payloads = [dds.encode_dxt5(dds_encode.pad_to_blocks(level)) for level in levels]
    header = bytearray(128)
    header[:4] = b"DDS "
    # flags, height, width, pitch of the top level, depth, mip count: the pack's own header
    struct.pack_into("<7I", header, 4, 124, 0x000A1007, height, width, len(payloads[0]), 0, len(payloads))
    header[76:76 + 32] = struct.pack("<2I4s5I", 32, 0x4, b"DXT5", 0, 0, 0, 0, 0)
    struct.pack_into("<I", header, 108, 0x00401008)
    return bytes(header) + b"".join(payloads)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not args.pack.is_file():
        print(f"error: {args.pack} is not there; restore it with git checkout -- dist", file=sys.stderr)
        return 2
    for path in write_outputs(args.pack, args.out):
        print(f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}  {path.stat().st_size} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
