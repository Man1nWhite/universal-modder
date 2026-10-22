"""Shaded preview of the retargeted mesh: stored vertex normals vs. normals
recomputed from the geometry.

The compliance checker only proves that the vertex normals are unit length;
this tool shows what they actually *do*: if the stored normals disagree with
the face orientation, the skin lights up backwards (black patches).

Usage:  python tools/pd2-port/shade_check.py [out_dir]
"""
from __future__ import annotations

import math
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

import rig_target  # noqa: E402
from me2_dae import load_dae  # noqa: E402

SOURCE_ZIP = "models/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip"
DAE = "Miranda Lawson (Romance) - Adjusted Version.dae"
RIG = Path(__file__).parent / "reference" / "las_rig.json"

LIGHT = np.array([0.35, -0.55, 0.76])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def geometric_normals(pos: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """Per-corner normals: the average of the incident face normals."""
    acc = np.zeros_like(pos)
    cnt = np.zeros(len(pos))
    e1 = pos[tris[:, 1]] - pos[tris[:, 0]]
    e2 = pos[tris[:, 2]] - pos[tris[:, 0]]
    fn = np.cross(e1, e2)
    for k in range(3):
        np.add.at(acc, tris[:, k], fn)
        np.add.at(cnt, tris[:, k], 1.0)
    n = np.where(cnt[:, None] > 0, acc, 0.0)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return np.where(ln > 0, n / np.maximum(ln, 1e-12), 0.0)


def render(pos, tris, nrm, width=700, height=1000, yaw=0.0, pitch=8.0):
    """A tiny z-buffered flat-shaded rasteriser."""
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def cam(p):
        # the model is Z-up: the screen x is the lateral axis, the screen y
        # the height, and the depth the Y axis (the camera looks along +Y)
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        x, y = x * cy - y * sy, x * sy + y * cy           # yaw about Z
        y, z = y * cp + z * sp, -y * sp + z * cp          # pitch about X
        return np.stack([x, -z, -y], axis=1)

    cp_ = cam(pos)
    lo, hi = cp_[:, 0].min(), cp_[:, 0].max()
    top, bot = cp_[:, 1].max(), cp_[:, 1].min()
    sx = (width - 1) / max(1e-6, hi - lo)
    sy_ = (height - 1) / max(1e-6, top - bot)
    s = min(sx, sy_)
    px = ((cp_[:, 0] - lo) * s + (width - 1 - (hi - lo) * s) / 2)
    py = ((top - cp_[:, 1]) * s + (height - 1 - (top - bot) * s) / 2)
    depth = cp_[:, 2]

    img = np.full((height, width, 3), 0.08, dtype=np.float64)
    zbuf = np.full((height, width), -1e18)
    for t in tris:
        i, j, k = t
        p0 = np.array([px[i], py[i]])
        p1 = np.array([px[j], py[j]])
        p2 = np.array([px[k], py[k]])
        area = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])
        if abs(area) < 1e-9:
            continue
        minx = max(0, int(math.floor(min(p0[0], p1[0], p2[0]))))
        maxx = min(width - 1, int(math.ceil(max(p0[0], p1[0], p2[0]))))
        miny = max(0, int(math.floor(min(p0[1], p1[1], p2[1]))))
        maxy = min(height - 1, int(math.ceil(max(p0[1], p1[1], p2[1]))))
        fn = nrm[[i, j, k]].mean(axis=0)
        ln = np.linalg.norm(fn)
        if ln < 1e-9:
            continue
        fn = fn / ln
        shade = 0.18 + 0.82 * max(0.0, float(fn @ LIGHT))
        col = np.array([shade, shade * 0.92, shade * 0.86])
        for y in range(miny, maxy + 1):
            for x in range(minx, maxx + 1):
                w0 = ((p1[0] - x) * (p2[1] - y) - (p2[0] - x) * (p1[1] - y)) / area
                w1 = ((p2[0] - x) * (p0[1] - y) - (p0[0] - x) * (p2[1] - y)) / area
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                z = w0 * depth[i] + w1 * depth[j] + w2 * depth[k]
                if z > zbuf[y, x]:
                    zbuf[y, x] = z
                    img[y, x] = col
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else Path("/tmp/las_shade")
    out.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(SOURCE_ZIP)
    scene = load_dae(z.read(DAE))
    rig = rig_target.load_target_rig(str(RIG))
    reb = rig_target.rebind_mesh(
        [m for m in scene.meshes if m.name == "Body 1"][0], scene, rig, smooth_iters=2)
    pos = np.asarray(reb.positions, dtype=np.float64)
    tris = np.asarray(reb.triangles, dtype=np.int64)
    stored = np.asarray(reb.normals, dtype=np.float64)
    geo = geometric_normals(pos, tris)
    for label, nrm in (("stored", stored), ("geometric", geo)):
        for vname, yaw in (("front", 0.0), ("three_quarter", 40.0), ("back", 180.0)):
            img = render(pos, tris, nrm, yaw=yaw)
            img.save(out / f"body_{label}_{vname}.png")
            print(f"  wrote {out / f'body_{label}_{vname}.png'}")
    # how much of the surface lights backwards with the stored normals?
    e1 = pos[tris[:, 1]] - pos[tris[:, 0]]
    e2 = pos[tris[:, 2]] - pos[tris[:, 0]]
    fn = np.cross(e1, e2)
    area = np.linalg.norm(fn, axis=1) / 2
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    avg = stored[tris].mean(axis=1)
    avg = avg / np.maximum(np.linalg.norm(avg, axis=1, keepdims=True), 1e-12)
    d = (fn * avg).sum(axis=1)
    tot = area.sum()
    print(f"  faces {len(tris)}, area {tot:.1f} cm2")
    print(f"  faces whose shading normal opposes the face: {(d < 0).sum()} "
          f"({(d < 0).sum() / len(tris) * 100:.1f}%), area {area[d < 0].sum():.1f} cm2 "
          f"({area[d < 0].sum() / tot * 100:.1f}%)")
    print(f"  faces lit backwards (dot < -0.2): {(d < -0.2).sum()}, "
          f"area {area[d < -0.2].sum():.1f} cm2 ({area[d < -0.2].sum() / tot * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
