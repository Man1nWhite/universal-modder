"""Flat-shaded z-buffer mesh renderer for pipeline previews (pure Python + stdlib).

Writes uncompressed RGB PNGs. No camera conventions beyond: look at the mesh
bounding box center, orthographic projection along -Y (front), -X (side),
isometric (iso). Used to visually verify the Source -> Diesel conversion.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


def write_png(path: Path | str, width: int, height: int, rgb: bytes) -> None:
    """Write an 8-bit RGB PNG."""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw += b"\x00" + rgb[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


def _norm(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (0.0, 0.0, 1.0) if l < 1e-12 else (v[0] / l, v[1] / l, v[2] / l)


def render(verts, faces, colors, out_path, view="front", size=640):
    """Render triangles with per-face colors.

    verts: [(x,y,z)] in model space (z up).
    faces: [(a,b,c)] indices.
    colors: per-face (r,g,b) 0..255.
    """
    if not verts:
        return
    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
    cx = (min(xs) + max(xs)) / 2; cy = (min(ys) + max(ys)) / 2; cz = (min(zs) + max(zs)) / 2
    extent = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
    scale = (size * 0.42) / extent

    # camera bases (right, up, toward-viewer)
    if view == "front":
        right, up, fwd = (1, 0, 0), (0, 0, 1), (0, -1, 0)
    elif view == "back":
        right, up, fwd = (-1, 0, 0), (0, 0, 1), (0, 1, 0)
    elif view == "side":
        right, up, fwd = (0, 1, 0), (0, 0, 1), (1, 0, 0)
    elif view == "top":
        right, up, fwd = (1, 0, 0), (0, 1, 0), (0, 0, -1)
    else:  # iso
        right, up, fwd = _norm((1, 1, 0)), None, _norm((-1, -1, 1.2))
        right = _norm((1, 1, 0))
        up = _norm((-0.4, -0.4, 1.2))

    def project(p):
        x, y, z = p[0] - cx, p[1] - cy, p[2] - cz
        sx = x * right[0] + y * right[1] + z * right[2]
        sy = x * up[0] + y * up[1] + z * up[2]
        sz = x * fwd[0] + y * fwd[1] + z * fwd[2]
        return (size / 2 + sx * scale, size / 2 - sy * scale, sz)

    proj = [project(v) for v in verts]
    zb = [1e30] * (size * size)
    img = bytearray(b"\x20\x24\x28" * size * size)

    light = _norm((0.35, -0.6, 0.75))
    for (a, b, c), col in zip(faces, colors):
        (ax, ay, az), (bx, by, bz), (cx2, cy2, cz2) = proj[a], proj[b], proj[c]
        area = (bx - ax) * (cy2 - ay) - (by - ay) * (cx2 - ax)
        if abs(area) < 1e-9:
            continue
        va, vb, vc = verts[a], verts[b], verts[c]
        e1 = (vb[0] - va[0], vb[1] - va[1], vb[2] - va[2])
        e2 = (vc[0] - va[0], vc[1] - va[1], vc[2] - va[2])
        n = _norm((e1[1] * e2[2] - e1[2] * e2[1],
                   e1[2] * e2[0] - e1[0] * e2[2],
                   e1[0] * e2[1] - e1[1] * e2[0]))
        lam = 0.35 + 0.65 * max(0.0, abs(n[0] * light[0] + n[1] * light[1] + n[2] * light[2]))
        r = min(255, int(col[0] * lam)); g = min(255, int(col[1] * lam)); bl = min(255, int(col[2] * lam))
        minx = max(0, int(min(ax, bx, cx2))); maxx = min(size - 1, int(max(ax, bx, cx2)) + 1)
        miny = max(0, int(min(ay, by, cy2))); maxy = min(size - 1, int(max(ay, by, cy2)) + 1)
        for py in range(miny, maxy + 1):
            for px in range(minx, maxx + 1):
                w0 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
                w1 = (cx2 - bx) * (py - by) - (cy2 - by) * (px - bx)
                w2 = (ax - cx2) * (py - cy2) - (ay - cy2) * (px - cx2)
                if (w0 >= 0 and w1 >= 0 and w2 >= 0) or (w0 <= 0 and w1 <= 0 and w2 <= 0):
                    depth = (az + bz + cz2) / 3
                    idx = py * size + px
                    if depth < zb[idx]:
                        zb[idx] = depth
                        img[idx * 3:idx * 3 + 3] = bytes((r, g, bl))
    write_png(out_path, size, size, bytes(img))


VIEW_ORDER = ("front", "side", "iso")
