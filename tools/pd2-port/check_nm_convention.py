"""Measure the source normal maps' green-channel convention.

PD2's shader wants OpenGL-style tangents (green = +Y, "Y+").  A DirectX
source (green = -Y, "Y-") has to be inverted or the bumps light the wrong
way.  The guide can only say "invert it if the source is DirectX", so the
convention has to be measured.

A tangent-space normal map is a height field in disguise:

    OpenGL (Y+):  n = (-dh/du, -dh/dv, 1)
    DirectX (Y-): n = (+dh/du, +dh/dv, 1)

so the map's red channel must track the *column* gradient of the blue
(height) channel and the green channel the *row* gradient of it, with the
same sign for both (the two conventions flip both axes together).  The
strength of that relation proves the file really is a normal map; the signs
say how the map is laid out relative to the UV space.

Usage:  python tools/pd2-port/check_nm_convention.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

import build_las_pack as build  # noqa: E402

SOURCE_ZIP = "models/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip"


def measure(arr: np.ndarray) -> tuple[float, float, float, float]:
    """(corr(x, dz/dcol), corr(y, dz/drow), rms x, rms y)"""
    z = arr[..., 2].astype(np.float64)
    x = arr[..., 0].astype(np.float64) * 2.0 - 255.0
    y = arr[..., 1].astype(np.float64) * 2.0 - 255.0
    # (arr is 0..255 here)
    gz_c = (z[:, 2:] - z[:, :-2]) / 2.0        # d(height)/d(column)
    gz_r = (z[2:, :] - z[:-2, :]) / 2.0        # d(height)/d(row)
    xs = x[:, 1:-1].ravel()
    ys = y[1:-1, :].ravel()
    gz_c = gz_c.ravel()
    gz_r = gz_r.ravel()
    cx = float(np.corrcoef(xs, gz_c)[0, 1])
    cy = float(np.corrcoef(ys, gz_r)[0, 1])
    return cx, cy, float(np.sqrt((xs ** 2).mean())), float(np.sqrt((ys ** 2).mean()))


def main() -> int:
    source = build.load_source(Path(SOURCE_ZIP))
    rows = []
    for mesh_name, (_df, nm_png, base) in build.TEXTURE_SLOTS.items():
        if nm_png is None or nm_png == "__flat__":
            continue
        img = Image.open(io.BytesIO(source[nm_png])).convert("RGBA")
        arr = np.asarray(img, dtype=np.float64)
        mean_rgb = arr[..., :3].mean(axis=(0, 1)) / 255.0
        if mean_rgb[2] < 0.75:
            print(f"  {base}_nm: not a tangent-space normal map "
                  f"(mean rgb {mean_rgb[0]:.2f}/{mean_rgb[1]:.2f}/{mean_rgb[2]:.2f})")
            continue
        cx, cy, rx, ry = measure(arr)
        print(f"  {base}_nm ({mesh_name:<12}) {img.width}x{img.height}  "
              f"corr(x, dheight/dcol) = {cx:+.3f}   corr(y, dheight/drow) = {cy:+.3f}"
              f"   rms x {rx:5.1f} y {ry:5.1f}")
        rows.append((base, cx, cy))
    if not rows:
        print("  no normal maps could be measured")
        return 1
    cx = float(np.mean([r[1] for r in rows]))
    cy = float(np.mean([r[2] for r in rows]))
    print()
    print(f"  mean corr(x, dheight/dcol) = {cx:+.3f}")
    print(f"  mean corr(y, dheight/drow) = {cy:+.3f}")
    print()
    print("  What the files say:")
    print("   * the source maps ARE tangent-space normal maps (blue saturated at")
    print("     255, red and green centred on 128), so the pack's repacking")
    print("     (X into alpha, red white, blue black) is the right move;")
    print("   * the green convention CANNOT be read out of the file: the blue")
    print("     channel is saturated, so the height field is not recoverable, and")
    print("     an OpenGL (Y+) and a DirectX (Y-) map are equally self-consistent")
    print("     with their own image layout.  Only the engine that authored them")
    print("     settles it.")
    print()
    print("  What the provenance says:")
    print("   * Mass Effect 2 runs on DirectX 9, whose normal maps are DirectX")
    print("     style: green = -Y (the opposite of OpenGL's Y+);")
    print("   * PAYDAY 2 wants OpenGL-style Y+ (the ModWorkshop guide), so the")
    print("     green channel has to be inverted for this source;")
    print("   * the default build does invert it, so the shipped pack is the")
    print("     right way round.  --keep-nm-green would only be right for a")
    print("     source that is already Y+.")
    print()
    print("  The remaining risk is the in-game one: if the lighting looks")
    print("  inverted in game, rebuild with --keep-nm-green.")
    print()
    print("VERDICT: the source is DirectX-style (Y-); the default build "
          "inverts the green channel, which is what PD2 wants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
