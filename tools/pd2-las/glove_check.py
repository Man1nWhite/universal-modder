"""Zoomed render of the sleeve/glove junction with a stand-in glove.

For a pack that ships no hands (the game spawns the heister's gloves at the hand
joint): the junction is judged against a stand-in, a blue capsule centred on the
PD2 hand joint and running down the hand, with the arms posed down.

    .venv/bin/python tools/pd2-las/glove_check.py MODEL OUT.png [deg]
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


def _sphere(center, radius, rings=10, segs=16):
    verts, faces = [], []
    for j in range(rings + 1):
        th = np.pi * j / rings
        for i in range(segs):
            ph = 2 * np.pi * i / segs
            verts.append(center + radius * np.array(
                [np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)]))
    for j in range(rings):
        for i in range(segs):
            a = j * segs + i
            b = j * segs + (i + 1) % segs
            c = (j + 1) * segs + i
            d = (j + 1) * segs + (i + 1) % segs
            faces += [(a, c, b), (b, c, d)]
    return np.array(verts), np.array(faces)


def cuff_proxy(body, deg, radius=3.2, length=7.0):
    """A blue cuff where the heister's glove sits: centred on the hand joints."""
    wrist_l = body["WB"][body["names"].index("LeftHand")][3, :3]
    wrist_r = body["WB"][body["names"].index("RightHand")][3, :3]
    arm_l = body["WB"][body["names"].index("LeftArm")][3, :3]
    arm_r = body["WB"][body["names"].index("RightArm")][3, :3]
    versus = []
    for wrist, arm, sgn in ((wrist_l, arm_l, -deg), (wrist_r, arm_r, deg)):
        d = wrist - arm
        d = d / np.linalg.norm(d)
        v, f = _sphere(wrist, radius)
        v2, f2 = _sphere(wrist + d * length, radius * 0.92)
        versus.append((np.vstack([v, v2]), np.vstack([f, f2 + len(v)])))
    verts = np.vstack([v for v, _ in versus])
    faces = np.vstack([f for _, f in versus])
    # pose with the same arm rotation
    l, r = pp.arm_chains(body["names"])
    piv_l = body["WB"][body["names"].index("LeftArm")][3, :3]
    piv_r = body["WB"][body["names"].index("RightArm")][3, :3]
    out = verts.copy()
    out[verts[:, 0] < 0] = pp._rotate_about(verts[verts[:, 0] < 0], piv_l, pp._rot_y(-deg))
    out[verts[:, 0] >= 0] = pp._rotate_about(verts[verts[:, 0] >= 0], piv_r, pp._rot_y(deg))
    return dict(material="glove", vertices=out, normals=np.tile([0, -1, 0], (len(out), 1)),
                uvs=np.zeros((len(out), 2)), triangles=faces)


def main():
    model = Path(sys.argv[1])
    out = Path(sys.argv[2])
    deg = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    body = pp.load_body(model)
    meshes = pp.meshes_from(body, pp.pose(body, -deg, deg))

    # the glove is represented synthetically: a capsule where the heister's glove
    # sits, i.e. centred on the PD2 hand joint and running 6 cm down the hand.
    meshes = meshes + [cuff_proxy(body, deg)]

    tex = {"glove": np.dstack([np.full((8, 8), c, np.float32)
                               for c in (0.25, 0.45, 0.95, 0.4)])}
    size = 460
    # frame the posed left hand joint: 16 cm across, centred 3 cm above it
    wrist_l = body["WB"][body["names"].index("LeftHand")][3, :3]
    arm_l = body["WB"][body["names"].index("LeftArm")][3, :3]
    posed = pp._rotate_about(wrist_l[None, :], arm_l, pp._rot_y(-deg))[0]
    center = posed + np.array([0.0, 0.0, 4.0])
    lo = center - 9.0
    hi = center + 9.0
    scale = size * 0.95 / float(max(hi[0] - lo[0], hi[2] - lo[2]))
    views = ("front", "threequarter", "side", "back")
    sheet = Image.new("RGB", (size * len(views), size), (12, 12, 14))
    for i, v in enumerate(views):
        im = pt.render(meshes, tex, v, size, scale, center, cull=True)
        ImageDraw.Draw(im).text((6, 4), f"{v} {int(deg)}deg glove=2B", fill=(255, 255, 255))
        sheet.paste(im, (i * size, 0))
    sheet.save(out)
    print("->", out)


if __name__ == "__main__":
    main()
