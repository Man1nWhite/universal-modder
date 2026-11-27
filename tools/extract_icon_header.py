#!/usr/bin/env python3
"""Write the character icon's 128-byte DDS header out of the reference pack.

Every head pack in `dist/` ships a 128x128 uncompressed BGRA8 icon, and only the
header of that DDS is shared: the pixels are the portrait the builder draws. The
header used to be read from `references/templates/Ada Wong over Joy.7z`'s
`guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture`, which meant
an 11.7 MB archive was a build input for 128 bytes.

This tool writes those 128 bytes out once:

    references/textures/icon_header_128x128_bgra8.dds

They are a valid DDS header and no pixel payload, which is all the builder reads.
The archive can then go, and `build_joy_head_mods` reads the tracked header -
`tests/test_icon_header.py` holds the two together and proves the three head packs
still rebuild byte for byte without the archive.

    python tools/extract_icon_header.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: the reference archive and the icon inside it
DEFAULT_ARCHIVE = ROOT / "references" / "templates" / "Ada Wong over Joy.7z"
MEMBER = "guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture"
DEFAULT_OUT = ROOT / "references" / "textures" / "icon_header_128x128_bgra8.dds"
#: a DDS header is 128 bytes; anything else is not the file this tool writes
HEADER = 128


def read_icon_header(archive: Path) -> bytes:
    """The first 128 bytes of the reference icon, read straight out of the archive."""
    with tempfile.TemporaryDirectory(prefix="icon-header-") as scratch:
        try:
            import py7zr
        except ImportError:  # not the pinned environment: any 7z CLI will do
            subprocess.run(["7z", "e", "-y", f"-o{scratch}", str(archive), f"*{Path(MEMBER).name}"],
                           check=True, capture_output=True)
            found = next(Path(scratch).rglob(Path(MEMBER).name))
        else:
            with py7zr.SevenZipFile(archive, mode="r") as z:
                names = [n for n in z.getnames() if n.replace("\\", "/").endswith(MEMBER)]
                if not names:
                    raise SystemExit(f"{archive.name}: no {MEMBER} in the archive")
                z.extract(path=scratch, targets=[names[0]])
            found = Path(scratch) / names[0]
        data = found.read_bytes()
    if len(data) < HEADER:
        raise SystemExit(f"{archive.name}/{MEMBER}: {len(data)} bytes, not a DDS")
    return data[:HEADER]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not args.archive.is_file():
        print(f"error: {args.archive} is not there; restore the tracked reference archive", file=sys.stderr)
        return 2
    header = read_icon_header(args.archive)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(header)
    print(f"{args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}  {len(header)} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
