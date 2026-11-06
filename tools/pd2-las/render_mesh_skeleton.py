#!/usr/bin/env python3
"""Render a built pack's g_body mesh together with the PD2 skeleton.

Orthographic painter's-algorithm render: the mesh is shaded per-face, bones
are drawn as lines between world joints (arm chain highlighted), and the PD2
arm pivots are marked. Usage:

  .venv/bin/python tools/pd2-las/render_mesh_skeleton.py \
      --zip dist/Christie_LAS_Slim.zip --pack Christie_LAS_Slim \
      --item christie_slim --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b" \
      --out build/pd2-las/previews
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
import diesel_model as dm  # noqa: E402
import build_models as bm  # noqa: E402

ARM_CHAIN = ("Arm", "ForeArm", "Hand", "Shoulder")


def g_body_geo(zf: zipfile.ZipFile, pack_dir: str, item: str):
    mf = dm.ModelFile.read(
        zf.read(f"{pack_dir}/assets/units/{item}/skins/{item}/{item}.model"))
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        name = next((n for n in hl if dm.hash64(n) == md["name_hash"]), "")
        if name == "g_body" and md.get("version") == 3:
            gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
            geo["faces"] = list(zip(topo["indices"][0::3],
                                    topo["indices"][1::3],
                                    topo["indices"][2::3]))
            return geo
    raise SystemExit("no g_body drawable in pack")


def skeleton(template: bm.Template):
    """[(name, world_pos, parent_name_or_None)] for every bone."""
    bones = []
    for sid, obj in template.id_obj.items():
        name = template.id_name[sid]
        if sid not in template.worlds:
            continue
        w = template.worlds[sid]
        parent = template.id_name.get(obj["parent"]) if obj["parent"] else None
        bones.append((name, np.array(w[12:15], float), parent))
    return bones


def rot_mat(axis: int, deg: float) -> tuple:
    a = np.deg2rad(deg)
    c, s = np.cos(a), np.sin(a)
    if axis == 0:
        r = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    elif axis == 1:
        r = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    else:
        r = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    m = np.eye(4)
    m[:3, :3] = r
    return tuple(m.flatten())


def posed_worlds(template: bm.Template, pose: dict) -> dict[int, tuple]:
    """Compose world matrices with extra local rotations, e.g.
    pose={'LeftForeArm': (0, -20)} rotates the bone -20 deg about local X."""
    worlds: dict[int, tuple] = {}
    pending = dict(template.id_obj)
    for _ in range(len(pending) + 1):
        progress = False
        for sid in list(pending):
            obj = pending[sid]
            loc = list(obj["matrix"])
            loc[12], loc[13], loc[14] = obj["pos"]
            loc = tuple(loc)
            name = template.id_name[sid]
            if name in pose:
                # Rotate the bone about ITS OWN HEAD, in its parent's frame.
                # The pose must not move the joint itself: PD2 pivots the child
                # about this point. Pre-multiplying the local matrix instead
                # (``mat_mul(rot, loc)``) rotates the joint offset, i.e. it
                # swings the whole bone through an arc around its parent's
                # origin - the elbow dot then lands somewhere the skeleton can
                # never put it, and the re-skinned mesh grows a spike.
                axis, deg = pose[name]
                rot = rot_mat(axis, deg)
                head = (loc[12], loc[13], loc[14])
                moved = dm.mat_apply_point(rot, head)
                rot = list(rot)
                rot[12] = head[0] - moved[0]
                rot[13] = head[1] - moved[1]
                rot[14] = head[2] - moved[2]
                loc = dm.mat_mul(loc, tuple(rot))
            if obj["parent"] == 0:
                worlds[sid] = loc
            elif obj["parent"] in worlds:
                worlds[sid] = dm.mat_mul(loc, worlds[obj["parent"]])
            else:
                continue
            del pending[sid]
            progress = True
        if not pending or not progress:
            break
    return worlds


def skin_verts(geo, skinbones: dict, pose_worlds: dict) -> np.ndarray:
    """Re-skin bind-pose verts into a posed skeleton (linear blend skinning).

    Diesel matrices are System.Numerics style and *row-vector*: a point is
    transformed with ``mat_apply_point(M, p)`` and composition is
    ``mat_mul(a, b)`` meaning "apply a, then b". Vertices are stored in model
    space and ``skinbones['rotations']`` holds each palette entry's inverse
    bind world ``R_i = W_i^-1`` (verified: ``W_i @ R_i == I``), so the
    deforming matrix is

        M = inv_bind_world @ pose_world        # bind -> model -> posed

    and the bind pose round-trips exactly because ``W @ W^-1 == I``.

    Two ways this went wrong here, both of which the identity pose hides
    completely:
      * building a numpy 4x4 and applying ``M @ p`` (column convention)
        transposes every matrix - a transposed identity is still an identity,
        so only real poses broke;
      * swapping the multiplication order to ``pose @ inv_bind``. That is
        *also* an identity in the bind pose, and it looks superficially right
        because ``pose`` is first, but it applies the pose about the model
        origin: every vertex is flung radially (a hand ended up 45 cm from
        where it belongs) and the mesh turns into long spikes. Keep the order,
        and keep ``tests/test_render_mesh_skeleton.py`` green - it bends an
        elbow and fails if any triangle edge stretches.
    """
    v = np.array(geo["verts"], float)
    bi = geo["blendindices"]
    bw = geo["blendweights"]
    pal = skinbones["objects"]
    inv_bind = [tuple(np.array(r, float).reshape(16)) for r in skinbones["rotations"]]
    out = np.zeros_like(v)
    mats: dict[int, tuple] = {}
    for i in range(len(v)):
        p = (float(v[i, 0]), float(v[i, 1]), float(v[i, 2]))
        acc = np.zeros(3)
        wsum = 0.0
        for k in range(len(bw[i])):
            w = float(bw[i][k])
            if w <= 0.0:
                continue
            pi = int(bi[i][k])
            if pi >= len(pal):
                continue
            bid = pal[pi]
            if bid not in pose_worlds:
                continue
            m = mats.get(pi)
            if m is None:
                # bind -> model (inv bind), then model -> posed: this order
                m = dm.mat_mul(inv_bind[pi], pose_worlds[bid])
                mats[pi] = m
            q = dm.mat_apply_point(m, p)
            acc[0] += w * q[0]
            acc[1] += w * q[1]
            acc[2] += w * q[2]
            wsum += w
        out[i] = acc / (wsum if wsum > 1e-9 else 1.0)
    return out


# where each camera sits, as a unit vector from the model towards the viewer
CAMERA_DIR = {
    "front": (0.0, 1.0, 0.0),     # +y
    "side": (-1.0, 0.0, 0.0),     # -x
    "top": (0.0, 0.0, 1.0),       # +z
    "bottom": (0.0, 0.0, -1.0),   # -z
    "iso": (0.7, 0.7, 0.0),
}


def depth_towards_camera(view: str, v: np.ndarray) -> np.ndarray:
    """Per-face depth key that increases as a face gets nearer the camera.

    Getting this backwards does not look broken - it silently draws the far
    side over the near side. That is what made the `bottom` view a copy of the
    `top`: a camera below the model needs ``-z`` here, not ``+z``.
    """
    c = np.array(CAMERA_DIR[view], float)
    return v[:, 0] * c[0] + v[:, 1] * c[1] + v[:, 2] * c[2]


def project(pts: np.ndarray, view: str) -> np.ndarray:
    if view == "front":      # looking along -y: screen = (x, z)
        return pts[:, [0, 2]]
    if view == "side":       # looking along +x: screen = (y, z)
        return pts[:, [1, 2]]
    if view == "iso":        # 3/4 view
        a = np.deg2rad(35.0)
        u = pts[:, 0] * np.cos(a) - pts[:, 1] * np.sin(a)
        return np.stack([u, pts[:, 2]], axis=1)
    if view == "top":        # looking down -z: screen = (x, y)
        return pts[:, [0, 1]]
    if view == "bottom":     # looking up +z, keeping model +x on the right
        # only y flips: negating both axes would be a 180 deg rotation, which
        # is a *valid view of the top* and tells you nothing about the
        # underside (it produced a bottom image that was pixel-identical to the
        # top apart from the bones).
        return np.stack([pts[:, 0], -pts[:, 1]], axis=1)
    raise ValueError(view)


def render(geo, bones, view: str, out_path: Path, zoom: tuple | None = None,
           verts: np.ndarray | None = None):
    v = verts if verts is not None else np.array(geo["verts"], float)
    faces = np.array(geo["faces"], int)
    bone_pts = [b[1] for b in bones]
    all_pts = np.vstack([v, bone_pts]) if bone_pts else v
    if zoom is not None:
        (x0, x1, z0, z1) = zoom
        m = ((v[:, 0] >= x0) & (v[:, 0] <= x1) & (v[:, 2] >= z0) & (v[:, 2] <= z1))
        near = [p for p in bone_pts
                if x0 - 5 <= p[0] <= x1 + 5 and z0 - 5 <= p[2] <= z1 + 5]
        all_pts = np.vstack([v[m], near]) if near else v[m]
    p2 = project(all_pts, view)
    W = H = 1000
    margin = 30
    s = min((W - 2 * margin) / max(np.ptp(p2[:, 0]), 1e-6),
            (H - 2 * margin) / max(np.ptp(p2[:, 1]), 1e-6))
    o = np.array([margin - p2[:, 0].min() * s, margin + p2[:, 1].max() * s])

    def scr(pt3):
        q = project(np.atleast_2d(pt3), view)[0]
        return (q[0] * s + o[0], q[1] * s * -1 + o[1])

    img = Image.new("RGB", (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(img)
    # mesh faces, painter's algorithm: `depth` grows towards the camera, so the
    # last face drawn is the nearest one
    depth = depth_towards_camera(view, v)
    order = np.argsort([depth[f].mean() for f in faces])
    for fi in order:
        a, b, c = faces[fi]
        n = np.cross(v[b] - v[a], v[c] - v[a])
        nl = np.linalg.norm(n)
        if nl < 1e-9:
            continue
        n /= nl
        light = max(0.0, abs(n[2]) * 0.7 + abs(n[0]) * 0.2 + 0.25)
        g = int(120 + 100 * light)
        dr.polygon([scr(v[a]), scr(v[b]), scr(v[c])],
                   fill=(g // 2, g // 2 + 10, min(g, 235)))
    # skeleton
    pos = {name: p for name, p, _ in bones}
    parent_of = {name: par for name, _, par in bones}
    for name, p, _ in bones:
        par = parent_of[name]
        if par is None or par not in pos:
            continue
        arm = any(k in name for k in ARM_CHAIN)
        col = (255, 90, 60) if arm else (90, 160, 255)
        wdt = 4 if arm else 2
        dr.line([scr(pos[par]), scr(p)], fill=col, width=wdt)
    for name, p, _ in bones:
        arm = any(k in name for k in ARM_CHAIN)
        r = 6 if arm else 3
        col = (255, 60, 40) if arm else (140, 190, 255)
        x, y = scr(p)
        dr.ellipse([x - r, y - r, x + r, y + r], fill=col)
    # legend
    dr.rectangle([10, 10, 330, 64], fill=(10, 10, 14))
    dr.line([20, 26, 60, 26], fill=(255, 90, 60), width=4)
    dr.text((70, 18), "arm chain (Arm/ForeArm/Hand/Shoulder)", fill=(255, 255, 255))
    dr.line([20, 48, 60, 48], fill=(90, 160, 255), width=2)
    dr.text((70, 40), "other bones", fill=(255, 255, 255))
    img.save(out_path)
    print(f"wrote {out_path} ({view})")


def render_source(source_zip: Path, out: Path, stem: str = "christie_source"):
    """Render the ORIGINAL DOA5 model (kept body materials) + its own skeleton."""
    import numpy as np
    import build_christie_las as bc

    with zipfile.ZipFile(source_zip) as zf:
        model = bc.load_christie(zf)
    worlds = bm.source_bone_worlds(model)
    bones = [(b.name, np.array(worlds[i][12:15], float),
              model.bones[b.parent].name if b.parent >= 0 else None)
             for i, b in enumerate(model.bones)]
    verts = [v.pos for v in model.vertices]
    faces = []
    for m in model.meshes:
        if m.material not in bc.KEEP_MATERIALS:
            continue
        idx = m.triangle_indices
        faces.extend(zip(idx[0::3], idx[1::3], idx[2::3]))
    geo = {"verts": verts, "faces": faces}
    out.mkdir(parents=True, exist_ok=True)
    for view in ("front", "side", "iso"):
        render(geo, bones, view, out / f"{stem}_{view}.png")
    # left forearm close-up: find source LeftForeArm joint and zoom around it
    fw = next((b for b in bones if "ForeArm" in b[0] and "Left" in b[0]), None)
    if fw is not None:
        c = fw[1]
        zoom = (c[0] - 14, c[0] + 14, c[2] - 22, c[2] + 10)
        for view in ("front", "side"):
            render(geo, bones, view, out / f"{stem}_forearm_{view}.png", zoom=zoom)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=None,
                    help="render the original model from this zip instead of a pack")
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--item", required=True)
    ap.add_argument("--templates", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=REPO / "build/pd2-las/previews")
    ap.add_argument("--pose", action="store_true",
                    help="also render a menu-like flexed pose (Arm/ForeArm/Hand "
                         "bent) with the mesh re-skinned onto the posed skeleton")
    args = ap.parse_args(argv)
    if args.source is not None:
        render_source(args.source, args.out)
        return 0
    with zipfile.ZipFile(args.zip) as zf:
        geo = g_body_geo(zf, args.pack, args.item)
        mf = dm.ModelFile.read(
            zf.read(f"{args.pack}/assets/units/{args.item}/skins/{args.item}/{args.item}.model"))
        hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
        skel = None
        for s in mf.by_type(dm.MODEL_DATA):
            md = dm.decode_model_data(s.payload)
            name = next((n for n in hl if dm.hash64(n) == md["name_hash"]), "")
            if name == "g_body" and md.get("version") == 3:
                skel = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
                break
    template = bm.load_template(args.templates / "2b.model")
    bones = skeleton(template)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.item
    # every view is rendered so the committed set is fully reproducible from
    # this CLI - docs/pd2-las/CHRISTIE.md names these files explicitly
    for view in ("front", "side", "iso", "top", "bottom"):
        render(geo, bones, view, args.out / f"{stem}_skel_{view}.png")
    # wrist close-ups (left arm, x negative)
    for view in ("front", "side"):
        render(geo, bones, view, args.out / f"{stem}_skel_wrist_{view}.png",
               zoom=(-56, -30, 108, 142))
    # forearm close-up framed on the LeftForeArm pivot, the same rule --source
    # uses, so a pack render and a source render line up for comparison
    fw = next((b for b in bones if b[0] == "LeftForeArm"), None)
    if fw is not None:
        c = fw[1]
        zoom = (c[0] - 14, c[0] + 14, c[2] - 22, c[2] + 10)
        for view in ("front", "side"):
            render(geo, bones, view, args.out / f"{stem}_forearm_{view}.png",
                   zoom=zoom)
    if args.pose:
        pose = {}
        for side in ("Left", "Right"):
            pose[f"{side}Arm"] = (0, 6)
            pose[f"{side}ForeArm"] = (0, -22)
            pose[f"{side}Hand"] = (0, -38)
        pw = posed_worlds(template, pose)
        posed_bones = [(template.id_name[sid], np.array(pw[sid][12:15], float),
                        template.id_name.get(template.id_obj[sid]["parent"])
                        if template.id_obj[sid]["parent"] else None)
                       for sid in pw]
        pv = skin_verts(geo, skel, pw)
        for view in ("front", "side"):
            render(geo, posed_bones, view, args.out / f"{stem}_skel_pose_{view}.png",
                   verts=pv)
        for view in ("front", "side"):
            render(geo, posed_bones, view, args.out / f"{stem}_skel_pose_wrist_{view}.png",
                   zoom=(-60, -25, 100, 145), verts=pv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
