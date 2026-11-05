"""Zoomed render of the sleeve/glove junction with a stand-in glove.

The shipped outfit ships no hands, so the junction is judged against a stand-in:
the 2B reference's hand-dominant geometry (which is exactly where PD2's
heister gloves sit -- same skeleton, same hand bone), tinted blue.

    .venv/bin/python build/wrist_zoom.py MODEL OUT.png [deg]
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

TPL = Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b/2b.model")


def load_largest_model(path):
    """pp.load_body, but every drawable of the template is tried.

    The 2B reference's body drawable carries a single material, which
    pp.load_body deliberately skips (it wants the multi-material one), so pick
    the drawable with the most vertices instead.
    """
    import diesel_model as dm
    import build_models as bm

    mf = dm.ModelFile.read_path(path)
    sb = dm.decode_skinbones(mf.by_type(dm.SKINBONES)[0].payload)
    names = [bm.template_name(dm.decode_object3d(mf.by_id(o).payload)["name_hash"], mf)
             for o in sb["objects"]]
    best = None
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        n = len(geo["verts"])
        if best is None or n > best[0]:
            best = (n, md, gp, geo)
    n, md, gp, geo = best
    topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
    mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
    mat_names = [bm.template_name(dm.decode_material(mf.by_id(m).payload)["name_hash"], mf)
                 for m in mg["material_ids"]]
    bw = np.array(geo["blendweights"], np.float64)
    w4 = np.column_stack([bw, np.clip(1.0 - bw.sum(axis=1), 0, 1)])
    WB = [np.linalg.inv(np.array(r, dtype=np.float64).reshape(4, 4))
          for r in sb["rotations"]]
    return dict(mf=mf, sb=sb, names=names, WB=WB, md=md,
                verts=np.array(geo["verts"], np.float64),
                normals=np.array(geo["normals"], np.float64),
                uvs=np.array(geo["uv0"], np.float64),
                faces=np.array(topo["indices"], np.int64).reshape(-1, 3),
                bidx=np.array(geo["blendindices"], np.int64), w4=w4,
                mat_names=mat_names)


def glove_meshes():
    body = load_largest_model(TPL)
    names = body["names"]
    hand = [i for i, n in enumerate(names) if n.startswith(("LeftHand", "RightHand"))
            or n in ("LeftHand", "RightHand")]
    w = np.zeros(len(body["verts"]))
    for k in range(4):
        w += np.where(np.isin(body["bidx"][:, k], hand), body["w4"][:, k], 0.0)
    keep = w > 0.5
    faces = body["faces"]
    faces = faces[keep[faces].all(1)]
    used = np.unique(faces)
    remap = np.full(len(body["verts"]), -1, np.int64)
    remap[used] = np.arange(used.size)
    body["verts"] = body["verts"][used]
    body["normals"] = body["normals"][used]
    body["bidx"] = body["bidx"][used]
    body["w4"] = body["w4"][used]
    body["faces"] = remap[faces]
    return body


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

    # 2B's own "hand" geometry turns out to be her over-long sleeve, so the
    # glove is represented synthetically: a capsule where the heister's glove
    # sits, i.e. centred on the PD2 hand joint and running 6 cm down the hand.
    meshes = meshes + [cuff_proxy(body, deg)]

    tex = {}
    for name in {m["material"] for m in meshes}:
        df = REPO / "build" / "skyrim-nif" / "textures" / f"outfit_{name.replace('mtr_', '')}_df.texture"
        if df.exists():
            tex[name] = pt.load_texture(df)

    tex["glove"] = np.dstack([np.full((8, 8), c, np.float32)
                              for c in (0.25, 0.45, 0.95, 0.4)])
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
