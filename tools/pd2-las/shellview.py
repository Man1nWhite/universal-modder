"""Flat-shaded, unlit z-buffer rasteriser for mesh-vs-mesh questions.

`preview_textured.render` answers "does the texture land on the right surface?";
this one answers "which mesh owns this pixel?". It fills triangles with a
per-face colour and no lighting, so two interpenetrating shells show up as two
flat colours meeting on a ragged line instead of being hidden by shading.

    import shellview
    img = shellview.render(verts, faces, colours, origin, target, up)

``colours`` is one RGB triple per face in 0..1; ``origin``/``target`` place a
perspective camera (``up`` is the world up vector). Returns an (h, w, 3) uint8
array. Triangles are never back-face culled, so a shell seen from the wrong side
still fills — pass only the meshes you mean to compare.
"""

from __future__ import annotations

import numpy as np


def render(verts, faces, colours, origin, target, up,
           width: int = 640, height: int = 640, fov: float = 40.0):
    """Rasterise ``faces`` with flat ``colours`` and a nearest-depth buffer."""
    verts = np.asarray(verts, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    colours = np.asarray(colours, dtype=np.float64)

    fwd = np.asarray(target, dtype=np.float64) - np.asarray(origin, dtype=np.float64)
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.asarray(up, dtype=np.float64))
    right /= np.linalg.norm(right)
    camup = np.cross(right, fwd)

    focal = 0.5 * width / np.tan(np.radians(fov) * 0.5)
    rel = verts - np.asarray(origin, dtype=np.float64)
    cam_x, cam_y, cam_z = rel @ right, rel @ camup, rel @ fwd
    sx = width * 0.5 + focal * cam_x / np.maximum(cam_z, 1e-6)
    sy = height * 0.5 - focal * cam_y / np.maximum(cam_z, 1e-6)

    img = np.zeros((height, width, 3))
    zbuf = np.full((height, width), np.inf)

    for t, tri in enumerate(faces):
        depth = cam_z[tri]
        if not (depth > 0.05).all():
            continue
        p = np.stack([sx[tri], sy[tri]], axis=1)
        x0 = max(int(np.floor(p[:, 0].min())), 0)
        x1 = min(int(np.ceil(p[:, 0].max())), width - 1)
        y0 = max(int(np.floor(p[:, 1].min())), 0)
        y1 = min(int(np.ceil(p[:, 1].max())), height - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        det = ((p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0])
               + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1]))
        if abs(det) < 1e-9:
            continue
        w0 = ((p[1, 1] - p[2, 1]) * (xs - p[2, 0])
              + (p[2, 0] - p[1, 0]) * (ys - p[2, 1])) / det
        w1 = ((p[2, 1] - p[0, 1]) * (xs - p[2, 0])
              + (p[0, 0] - p[2, 0]) * (ys - p[2, 1])) / det
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = 1.0 / (w0 / depth[0] + w1 / depth[1] + w2 / depth[2])
        nearer = inside & (z < zbuf[ys, xs])
        if not nearer.any():
            continue
        zbuf[ys[nearer], xs[nearer]] = z[nearer]
        img[ys[nearer], xs[nearer]] = colours[t]

    return (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8)
