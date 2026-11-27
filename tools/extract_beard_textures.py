#!/usr/bin/env python3
"""Write Geralt's beard from the Witcher 3 port's own maps in `references/`.

`references/characters/Geralt.7z` carries the L4D2 port of Geralt: his VTF
textures under `materials/models/survivors/witcher3/geralt/`, among them
`beard_d.vtf` (colour, with the hair's alpha cutout) and `beard_n.vtf` (the
normal map) at 1024x512. Those two are the beard's source of truth; this tool
reads them straight out of the archive and writes the four files every other
consumer takes:

    references/textures/geralt_beard_df.png   1024x512 RGBA - colour + cutout
    references/textures/geralt_beard_nm.png   1024x512 RGBA - PD2 normal layout
    references/textures/geralt_beard_df.dds   the same colour as DXT5, full mips
    references/textures/geralt_beard_nm.dds   the same normal as DXT5, full mips

The colour keeps the VTF's coverage as a 0/255 cutout at the game's own
`alpha_ref` threshold: the port ships an anti-aliased alpha, and a texel the
material would still draw (12 of 255 and up, against `alpha_ref` 0.05) stays in,
including the thin hair ends a 50 % cut would erase. The pack's atlas stores 24
under a hair and 0 off one; that final quantisation is the builder's. The normal map is converted
to Diesel's packed layout by the same helper, with the same Y flip, that the pack
builder applies to this VTF - X in alpha, Y in green (Source's DirectX Y- flipped
to PD2's Y+), 255 in red, 0 in blue - so the PNG is the picture the pack's atlas
quadrant holds, not a Source-format VTF.

`build_joy_head_mods.build_geralt_rust_mod` reads the DDS pair rather than the
VTFs: the pack's atlas beard, and so `dist/Geralt/Geralt_over_Rust.zip`, is built
from these tracked files. Re-run this tool and then `make -sC tools/pd2-las heads`
after changing anything it reads. Re-encoding is not idempotent through lossy
DXT5, so a byte-for-byte rebuild needs these tracked files, not a fresh run:
`tests/test_beard_textures.py` holds the two together.

    python tools/extract_beard_textures.py
    python tools/extract_beard_textures.py --out build/geralt-beard   # elsewhere
"""
from __future__ import annotations

import argparse
import io
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tools" / "pd2-las"), str(ROOT / "tools" / "pd2-port")]

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import dds  # noqa: E402  (the pack's DXT5 writer and PD2 normal packing)
import dds_encode  # noqa: E402  (its edge padding, for levels smaller than a block)
import vtf  # noqa: E402  (the VTF reader the pack builder also uses)

#: the Witcher 3 port archive, and the two maps inside it
DEFAULT_ARCHIVE = ROOT / "references" / "characters" / "Geralt.7z"
VTFS = {"df": "beard_d.vtf", "nm": "beard_n.vtf"}
DEFAULT_OUT = ROOT / "references" / "textures"
#: the pixel size both maps are; the pack's atlas quadrant is this size too
SIZE = (1024, 512)


def read_vtf(pack: Path, suffix: str) -> np.ndarray:
    """One of the port's beard maps as an (512, 1024, 4) uint8 array, straight from the archive.

    A `.7z` is read with py7zr when it is installed (the pinned build dependency)
    and with the `7z` binary otherwise. Nothing is extracted to disk: the VTF is
    decoded in memory with the same reader the builder uses.
    """
    member = VTFS[suffix]
    # py7zr extracts to a folder rather than to memory, so the member goes through a
    # scratch directory and is read back; nothing is kept afterwards.
    with tempfile.TemporaryDirectory(prefix="geralt-beard-") as scratch:
        try:
            import py7zr
        except ImportError:  # not the pinned environment: any 7z CLI will do
            subprocess.run(["7z", "e", "-y", f"-o{scratch}", str(pack), f"*{member}"], check=True,
                           capture_output=True)
        else:
            with py7zr.SevenZipFile(pack, mode="r") as archive:
                names = [n for n in archive.getnames() if n.replace("\\", "/").endswith(member)]
                if not names:
                    raise SystemExit(f"{pack.name}: no {member} in the archive")
                archive.extract(path=scratch, targets=[names[0]])
            member = names[0]
        written = Path(scratch) / member
        if not written.is_file():  # py7zr keeps the archive's folders; 7z e flattens them
            written = next(Path(scratch).rglob(member), written)
        data = written.read_bytes()
    image = vtf.parse_vtf(data)
    with Image.open(io.BytesIO(vtf.to_dds(image))) as im:
        arr = np.asarray(im.convert("RGBA")).copy()
    if arr.shape[:2] != SIZE[::-1]:
        raise SystemExit(f"{pack.name}/{member}: {arr.shape[1]}x{arr.shape[0]}, expected {SIZE[0]}x{SIZE[1]}")
    return arr


def cutout(alpha: np.ndarray) -> np.ndarray:
    """The port's anti-aliased alpha as a 0/255 cutout, keeping the faint outline wisps.

    The VTF alpha is smooth 0..255. The game's material cuts at `alpha_ref` 0.05 (13 of
    255), so a texel at 12 is still drawn where one at 0 is not: cutting at 128 would erase
    thin, semi-transparent hair ends the pack has always drawn, which is 4.6 % of the beard's
    outside edge. The threshold is the pack builder's own (`>= 12`), written here once.
    """
    return np.where(alpha >= 12, 255, 0).astype(np.uint8)


def write_outputs(pack: Path, out: Path) -> list[Path]:
    """Write the four files; return the paths, PNGs first."""
    out.mkdir(parents=True, exist_ok=True)
    df, nm = read_vtf(pack, "df"), read_vtf(pack, "nm")
    colour = np.dstack([df[..., :3], cutout(df[..., 3])])
    # the same Y flip the pack builder applies to this VTF, so the two cannot disagree
    normal = dds.pd2_normal_channels(nm, invert_y=True).copy()
    written: list[Path] = []

    df_png = out / "geralt_beard_df.png"
    df_png.write_bytes(_png(colour))
    written.append(df_png)

    nm_png = out / "geralt_beard_nm.png"
    nm_png.write_bytes(_png(normal))
    written.append(nm_png)

    # DXT5, full mip chain, exactly as the pack encodes its textures
    df_dds = out / "geralt_beard_df.dds"
    df_dds.write_bytes(_dds(colour))
    written.append(df_dds)

    nm_dds = out / "geralt_beard_nm.dds"
    nm_dds.write_bytes(_dds(normal))
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
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE,
                        help="the Witcher 3 port archive (default: references/characters/Geralt.7z)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not args.archive.is_file():
        print(f"error: {args.archive} is not there; restore the tracked reference archive", file=sys.stderr)
        return 2
    for path in write_outputs(args.archive, args.out):
        print(f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}  {path.stat().st_size} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
