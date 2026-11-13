"""Zoomed posed render of one shoulder / upper arm, for before/after checks.

    .venv/bin/python tools/pd2-las/pose_zoom.py MODEL OUT.png [deg [x_lo z_lo x_hi z_hi]]

Uses pose_preview's arm adduction (the pose that opens the shoulder seam) and
renders the character's left shoulder from four angles, cropped tight.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import pose_preview as pp  # noqa: E402
import preview_textured as pt  # noqa: E402


def main():
    model = Path(sys.argv[1])
    out = Path(sys.argv[2])
    deg = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    body = pp.load_body(model)
    vp = pp.pose(body, -deg, deg)
    meshes = pp.meshes_from(body, vp)
    tex = {}
    views = ("front", "threequarter", "back", "side")
    size = 460
    lo = np.array([float(sys.argv[4]) if len(sys.argv) > 4 else -52.0,
                   -22.0, float(sys.argv[5]) if len(sys.argv) > 5 else 108.0])
    hi = np.array([float(sys.argv[6]) if len(sys.argv) > 6 else -8.0,
                   20.0, float(sys.argv[7]) if len(sys.argv) > 7 else 155.0])
    center = (lo + hi) / 2
    scale = size * 0.95 / float(max(hi[0] - lo[0], hi[2] - lo[2]))
    sheet = Image.new("RGB", (size * len(views), size), (12, 12, 14))
    for i, v in enumerate(views):
        im = pt.render(meshes, tex, v, size, scale, center, cull=True)
        d = ImageDraw.Draw(im)
        d.text((6, 4), f"{v} {int(deg)}deg", fill=(255, 255, 255))
        sheet.paste(im, (i * size, 0))
    sheet.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
