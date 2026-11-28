#!/usr/bin/env python3
"""Write Geralt's face maps from the Witcher 3 port's own maps in `references/`.

`references/characters/Geralt.7z` carries the L4D2 port of Geralt and, under
`materials/models/survivors/witcher3/geralt/`, his face's two maps:
`geralt_head_bm.vtf` (the head diffuse, 2048x2048, opaque) and
`geralt_head_nm.vtf` (the head normal, 2048x2048, Source's DirectX layout). The
pack builder had read both straight out of the archive and downsampled them to
1024x1024 on the way into the head atlas. This tool is that read made a file:

    references/textures/geralt_head_df.png   2048x2048 RGBA - the diffuse as the port draws it
    references/textures/geralt_head_nm.png   2048x2048 RGBA - PD2 normal layout, Y flipped
    references/textures/geralt_head_df.dds   the same diffuse as DXT5, full mips
    references/textures/geralt_head_nm.dds   the same normal as DXT5, full mips

Native size on purpose. The VTF is 2048x2048 and the atlas quadrant the pack
holds is 1024x1024, so what this tool writes is the picture *before* the
builder's LANCZOS halving, not a copy of the quadrant: a 1024 file would be the
pack's own pixels re-encoded and would say nothing the pack does not already
say. The normal is converted to Diesel's packed layout by the same helper, with
the same Y flip, the pack builder uses for this VTF - X in alpha, Y in green,
255 in red, 0 in blue - so the PNG and DDS are the picture the pack's normal
atlas holds before downsampling, not a Source-format VTF.

The diffuse keeps the port's alpha as it is (255 everywhere): the head is solid,
and the pack's own `18` in the atlas' specular channel is the builder's, not
this picture's.

`build_joy_head_mods.build_geralt_rust_mod` still reads the archive directly;
these files are the face as a texture of its own, beside the beard pair, for
another mod or another engine. Re-run this tool after the archive changes:

    python tools/extract_face_textures.py
    python tools/extract_face_textures.py --out build/geralt-face   # elsewhere
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
VTFS = {"df": "geralt_head_bm.vtf", "nm": "geralt_head_nm.vtf"}
DEFAULT_OUT = ROOT / "references" / "textures"
#: the size both maps are; the pack's head-atlas quadrant is half this
SIZE = (2048, 2048)


def read_vtf(pack: Path, suffix: str) -> np.ndarray:
    """One of the port's face maps as a (2048, 2048, 4) uint8 array, straight from the archive.

    A `.7z` is read with py7zr when it is installed (the pinned build dependency) and with
    the `7z` binary otherwise. Nothing is extracted to disk: the VTF is decoded in memory
    with the same reader the builder uses.
    """
    member = VTFS[suffix]
    # py7zr extracts to a folder rather than to memory, so the member goes through a
    # scratch directory and is read back; nothing is kept afterwards.
    with tempfile.TemporaryDirectory(prefix="geralt-face-") as scratch:
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
        raise SystemExit(f"{pack.name}/{member}: {arr.shape[1]}x{arr.shape[0]}, expected "
                         f"{SIZE[0]}x{SIZE[1]}")
    return arr


def write_outputs(pack: Path, out: Path) -> list[Path]:
    """Write the four files; return the paths, PNGs first."""
    out.mkdir(parents=True, exist_ok=True)
    df, nm = read_vtf(pack, "df"), read_vtf(pack, "nm")
    # the same Y flip the pack builder applies to this VTF, so the two cannot disagree
    normal = dds.pd2_normal_channels(nm, invert_y=True).copy()
    written: list[Path] = []

    df_png = out / "geralt_head_df.png"
    df_png.write_bytes(_png(df))
    written.append(df_png)

    nm_png = out / "geralt_head_nm.png"
    nm_png.write_bytes(_png(normal))
    written.append(nm_png)

    # DXT5, full mip chain, exactly as the pack encodes its textures
    df_dds = out / "geralt_head_df.dds"
    df_dds.write_bytes(_dds(df))
    written.append(df_dds)

    nm_dds = out / "geralt_head_nm.dds"
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
    """A DXT5 DDS with the full mip chain for a 2048x2048 image.

    `dds.pack_dds` takes one side and assumes a square texture; the header is written here
    for the two dimensions the image has. The levels are the box averages
    `dds.downsample2x2` makes, down to 1x1.
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
