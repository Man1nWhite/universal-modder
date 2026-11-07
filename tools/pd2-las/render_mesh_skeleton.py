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

#: Which local axis of a PD2 limb bone is *flexion* (the joint angle changes)
#: as opposed to a swing/twist of the whole chain. Measured on the 2B template
#: (`posed_worlds`, joint angle from the bone positions):
#:
#:     ForeArm local X:  Arm-ForeArm angle 72.1 deg at every angle  -> twist
#:     ForeArm local Y:  72.1 -> 0.1 deg at -72                      -> flexion
#:     Hand    local X:  Fore-Hand angle 6.5 deg at every angle     -> twist
#:     Hand    local Y:  6.5 -> 36.8 deg at +40                      -> flexion
#:
#: The 2026-11-06 "hang" pose rotated the ForeArm about X, so it never bent
#: the elbow: it swung the forearm on a cone about the upper arm, i.e. it
#: twisted the sleeve at the weld ring. Everything measured on that pose
#: described a twisted sleeve, not a bent elbow. Keep these constants and use
#: BEND_AXIS for every "does the elbow deform well" question.
BEND_AXIS = 1
BIND_ELBOW_DEG = 72.0      # Arm-ForeArm angle in the PD2 bind/menu pose
IDLE_ELBOW_DEG = 12.0      # the heister's idle: the elbow hangs near straight


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
            mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
            mat_names = [bm.template_name(
                dm.decode_material(mf.by_id(mid).payload)["name_hash"], mf)
                for mid in mg["material_ids"]]
            face_materials = [""] * len(geo["faces"])
            for atom in md["atoms"]:
                first = atom["base_index"] // 3
                material = (mat_names[atom["material_id"]]
                            if atom["material_id"] < len(mat_names) else "")
                face_materials[first:first + atom["tri_count"]] = (
                    [material] * atom["tri_count"])
            geo["face_materials"] = face_materials
            return geo
    raise SystemExit("no g_body drawable in pack")


def _subset_near_polyline(geo, chain, radius: float, pad: float = 6.0):
    """The part of `geo` that wraps a bone chain - a limb tube, on its own.

    Close-ups are cut with this instead of a crop window. A window is a slab
    through an orthographic scene, so it always drags in whatever sits behind
    the limb; picking triangles by their 3D distance to the bones selects the
    sleeve itself and nothing else, from any viewpoint. Distances are in cm.
    """
    v = np.array(geo["verts"], float)
    faces = np.array(geo["faces"], int)
    best = np.full(len(v), np.inf)
    for a, b in zip(chain[:-1], chain[1:]):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        ab = b - a
        t = np.clip((v - a) @ ab / max(float(ab @ ab), 1e-12), 0.0, 1.0)
        d = np.linalg.norm(v - (a + np.outer(t, ab)), axis=1)
        best = np.minimum(best, d)
    near = best <= radius + pad

    keep = near[faces].any(axis=1)
    # a face may only survive if all of its verts are close enough
    keep &= near[faces].all(axis=1)
    if not keep.any():
        return geo
    # collect every vertex of a kept face (so the boundary closes), then drop
    # anything that only got in that way - without this a face spanning from
    # the sleeve to the torso drags distant geometry into a close-up
    used = np.unique(faces[keep])
    remap = {old: new for new, old in enumerate(used)}
    return {"verts": [v[i] for i in used],
            "faces": [tuple(remap[i] for i in f) for f in faces[keep]]}


def _axis_to_camera(verts, pivot, view: str):
    """Rotate the model so a bone axis points at the camera, then re-centre.

    A cuff mouth is a ring seen edge-on in every orthographic view of the body,
    which is why the interesting failure at the end of a sleeve - a torn ring, an
    off-centre wrist, a cut that is not square to the arm - is invisible in
    `front`/`side`. Turning the limb to face the lens shows the opening itself.
    """
    return np.asarray(verts, float) - np.asarray(pivot, float)


def render_cuff_mouth(geo, bones, chain, out_path: Path, radius: float = 7.0):
    """Draw the cuff opening face-on, looking straight down the forearm.

    `chain` is [elbow, wrist]; the view axis is the bone direction, so the ring
    appears as a ring rather than a line.
    """
    elbow = np.asarray(chain[0], float)
    wrist = np.asarray(chain[1], float)
    axis = wrist - elbow
    axis /= max(float(np.linalg.norm(axis)), 1e-9)

    # rotation taking `axis` onto +y, the direction `front` looks along
    target = np.array([0.0, 1.0, 0.0])
    v = np.cross(axis, target)
    s = float(np.linalg.norm(v))
    c = float(axis @ target)
    if s < 1e-8:
        rot = np.eye(3) if c > 0 else -np.eye(3)
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        rot = np.eye(3) + vx + vx @ vx * ((1.0 - c) / s ** 2)

    v = np.array(geo["verts"], float)
    faces = np.array(geo["faces"], int)
    keep = np.linalg.norm(v - wrist, axis=1) <= radius
    keep_f = keep[faces].all(axis=1)
    if not keep_f.any():
        return
    used = np.unique(faces[keep_f])
    remap = {int(old): int(new) for new, old in enumerate(used)}
    local = {"verts": (v[used] - wrist) @ rot.T,
             "faces": [tuple(remap[int(i)] for i in f) for f in faces[keep_f]]}
    # only the limb's own bones: the rest of the rig would define the frame and
    # shrink the cuff to a speck in the corner
    near = _bones_near([elbow, wrist], bones, radius=3.0)
    turned = [(n, (np.asarray(h, float) - wrist) @ rot.T, par)
              for n, h, par in near]
    render(local, turned, "front", out_path)


def _bones_near(chain, bones, radius: float):
    """The bones that belong in a limb close-up - the limb's own subtree.

    A bone is kept when the traced chain is among its ancestors (so the hand and
    fingers come along), plus the chain's immediate parents for context. Two
    things this avoids, both of which showed up in the images:

      * framing uses every bone it is handed, and the full rig shrank the arm
        into a corner with the rest of the skeleton hanging below it;
      * proximity alone is too loose - 50 bones fall within 16 cm of the arm,
        including `LeftShoulder` and a weapon attachment, and their parent lines
        are drawn to joints that are not in the picture, which reads as stray
        bones floating off into the torso.
    """
    names = [n for n, _h, _p in bones]
    parent_of = {n: p for n, _h, p in bones}
    chain_names = {n for n, h, _p in bones
                   if any(np.linalg.norm(np.asarray(h, float)
                                         - np.asarray(c, float)) <= radius
                          for c in chain)}
    keep = set()
    for name in names:
        node = name
        for _ in range(12):                    # walk up to the root
            if node in chain_names:
                keep.add(name)
                break
            node = parent_of.get(node)
            if node is None:
                break
    # No "one level of context above": `render()` already skips the line for a
    # bone whose parent is not drawn, so the limb just ends. Adding the parent
    # instead drew a shoulder-to-chest line running off the sleeve, which reads
    # as a stray bone crossing the crop.
    # attachments, collision capsules and the duplicated `*_locator_end` bones
    # all sit on the limb but are not anatomy - they draw as dots in the middle
    # of the sleeve and as lines to a joint that does not exist
    drop = ("locator", "capsule", "weapon", "_att", "_end")
    keep = {n for n in keep if not any(d in n for d in drop)}
    # No extra ancestor: `render()` skips a bone's line when its parent is not
    # in the list, so the top of the limb simply ends. Adding the context bone
    # instead drew a 40 cm line from the shoulder to a spine joint that is
    # outside the crop, which reads as a bone escaping the arm.
    return [b for b in bones if b[0] in keep]


def _largest_blobs(sub: dict, count: int = 3) -> dict:
    """Drop the little scrap islands a radius cut leaves behind.

    Selecting triangles by proximity to a bone chain always picks up a few
    isolated fragments where a nearby surface (a cuff edge, the far side of a
    sleeve seam) happens to pass within the radius. They read as random chunks
    floating beside the arm, so keep only the biggest connected pieces.
    """
    faces = np.array(sub["faces"], int)
    if len(faces) == 0:
        return sub
    parent = list(range(int(faces.max()) + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for f in faces:
        union(f[0], f[1])
        union(f[1], f[2])
    roots = np.array([find(f[0]) for f in faces])
    order = np.argsort(-np.bincount(roots)[np.bincount(roots) > 0])[:count]
    keep_roots = {int(np.unique(roots)[i]) for i in order}
    keep = np.array([find(f[0]) in keep_roots for f in faces])
    if keep.all() or not keep.any():
        return sub
    used = np.unique(faces[keep])
    remap = {int(old): int(new) for new, old in enumerate(used)}
    return {"verts": [sub["verts"][i] for i in used],
            "faces": [tuple(remap[int(i)] for i in f) for f in faces[keep]]}


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


def rest_skeleton(template: bm.Template, skinbones: dict | None):
    """Animation hierarchy with the geometry's encoded authoring rest worlds.

    Ordinary packs inherit ``template.worlds`` and this is identical to
    :func:`skeleton`. A deliberately rebound group (Christie's idle arms) must
    instead show the inverse-bind worlds shipped in its skinbones; drawing the
    old template elbows over its rest mesh would be a false misalignment.
    """
    bones = skeleton(template)
    if not skinbones:
        return bones
    rest = {sid: np.linalg.inv(np.asarray(rotation, float).reshape(4, 4))
            for sid, rotation in zip(skinbones["objects"], skinbones["rotations"])}
    return [(name, rest[sid][3, :3].copy() if sid in rest else point, parent)
            for name, point, parent in bones
            for sid in (template.name_id[name],)]


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
# The character faces +y with up +z, so its right is +x and its left is -x -
# which is why every `Left*` bone in the rig sits at negative x. A camera at -x
# therefore looks at the character's LEFT side, and `side` is already the
# correct viewpoint for a left-limb close-up (the left arm is the near limb).
CAMERA_DIR = {
    "front": (0.0, 1.0, 0.0),     # +y
    "side": (-1.0, 0.0, 0.0),     # -x: the character's left side
    "top": (0.0, 0.0, 1.0),       # +z
    "bottom": (0.0, 0.0, -1.0),   # -z
    "iso": (0.7, 0.7, 0.0),
}


def _in_window(pt, view: str, window: tuple, pad: float = 0.0) -> bool:
    """Is a model-space point inside a screen-space crop window?"""
    u, vv = project(np.atleast_2d(pt), view)[0]
    u0, u1, v0, v1 = window
    return u0 - pad <= u <= u1 + pad and v0 - pad <= vv <= v1 + pad


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
           verts: np.ndarray | None = None, depth: tuple | None = None):
    """Draw `geo` from `view` with the skeleton on top.

    `zoom` is a window in *screen* coordinates - the same pair `project()`
    returns - and `depth` is a band on the camera axis, which selects the near
    shell. Both are needed for a close-up: an orthographic view projects along
    an infinite slab, so a screen window on its own still catches the far side
    of the body (a "left forearm" crop framed from the character's left found
    the far shoulder inside the same window). When `zoom` is given, the frame is
    exactly the window, so the same window size looks the same on every view.
    """
    v = verts if verts is not None else np.array(geo["verts"], float)
    faces = np.array(geo["faces"], int)
    bone_pts = [b[1] for b in bones]
    all_pts = np.vstack([v, bone_pts]) if bone_pts else v
    drawn = faces
    fixed_frame = None
    if zoom is not None:
        u0, u1, v0, v1 = zoom
        cen = v[faces].mean(axis=1)
        cuv = project(cen, view)
        keep = ((cuv[:, 0] >= u0 - 2) & (cuv[:, 0] <= u1 + 2)
                & (cuv[:, 1] >= v0 - 2) & (cuv[:, 1] <= v1 + 2))
        if depth is not None:
            dmin, dmax = depth
            dc = depth_towards_camera(view, cen)
            keep &= (dc >= dmin) & (dc <= dmax)
        if keep.any():
            # keep every vertex of a kept face, so the boundary closes instead
            # of leaving a ring of holes
            used = np.unique(faces[keep])
            near = [p for p in bone_pts if _in_window(p, view, zoom, pad=6)]
            all_pts = np.vstack([v[used], near]) if near else v[used]
            drawn = faces[keep]
            fixed_frame = (u0, u1, v0, v1)
    p2 = project(all_pts, view)
    W = H = 1000
    margin = 30
    if fixed_frame is not None:
        # the window is the frame: same crop, same scale, any viewpoint
        u0, u1, v0, v1 = fixed_frame
        s = min((W - 2 * margin) / max(u1 - u0, 1e-6),
                (H - 2 * margin) / max(v1 - v0, 1e-6))
        o = np.array([margin - u0 * s, margin + v1 * s])
    else:
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
    order = np.argsort([depth[f].mean() for f in drawn])
    for fi in order:
        a, b, c = drawn[fi]
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
    src_arm = [p for n, p, _ in bones
               if n in ("MOT08_LeftArm", "MOT04_LeftForeArm", "MOT05_LeftHand")]
    if len(src_arm) == 3:
        # The DOA model is ~3.5x smaller in cm, so the tube radius scales off
        # the arm span - then the source crop shows the same *anatomy* as the
        # pack crop and the two can be compared directly.
        span = float(np.linalg.norm(np.array(src_arm[2], float)
                                    - np.array(src_arm[0], float)))
        # The arm hangs close to the torso in the source pose, so the radius has
        # to be tight: 631 verts sit within 2 cm of the chain, 4105 within 8 cm
        # (that one swallows the chest and the whole leg, because the source
        # skeleton's leg bones hang underneath). 2 cm, scaled off the arm span,
        # keeps the sleeve and drops the body.
        tube = _largest_blobs(_subset_near_polyline(geo, src_arm,
                                                    radius=0.095 * span))
        near_bones = _bones_near(src_arm, bones, radius=0.15 * span)
        for view in ("front", "side"):
            render(tube, near_bones, view, out / f"{stem}_forearm_{view}.png")
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
                         "flexed on the joint axes) with the mesh re-skinned "
                         "onto the posed skeleton")
    ap.add_argument("--hang", action="store_true",
                    help="also render the in-game near-idle pose (12 deg elbow "
                         "on the flexion axis); custom-rest packs encode this "
                         "as identity, older packs straighten their 72 deg bind")
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
    bones = rest_skeleton(template, skel)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.item
    # every view is rendered so the committed set is fully reproducible from
    # this CLI - docs/pd2-las/CHRISTIE.md names these files explicitly
    for view in ("front", "side", "iso", "top", "bottom"):
        render(geo, bones, view, args.out / f"{stem}_skel_{view}.png")
    # wrist close-ups (left arm); `side` is the character's left side
    chain = [p for n, p, _ in bones if n in ("LeftForeArm", "LeftHand")]
    if len(chain) == 2:
        hand = _largest_blobs(_subset_near_polyline(geo, chain, radius=7.0))
        near_bones = _bones_near(chain, bones, radius=14.0)
        for view in ("front", "side"):
            render(hand, near_bones, view,
                   args.out / f"{stem}_skel_wrist_{view}.png")
        # the opening itself, looking straight down the forearm
        render_cuff_mouth(geo, bones, chain,
                          args.out / f"{stem}_skel_cuff.png", radius=7.0)
    # forearm close-up framed on the LeftForeArm pivot, the same rule --source
    # uses, so a pack render and a source render line up for comparison
    arm = [p for n, p, _ in bones if n in ("LeftArm", "LeftForeArm", "LeftHand")]
    if len(arm) == 3:
        # the sleeve around those bones, plus a margin so the shoulder and the
        # cuff stay in shot
        tube = _largest_blobs(_subset_near_polyline(geo, arm, radius=8.0))
        near_bones = _bones_near(arm, bones, radius=16.0)
        for view in ("front", "side"):
            render(tube, near_bones, view,
                   args.out / f"{stem}_forearm_{view}.png")
    if args.pose:
        # Elbow and wrist on the FLEXION axis (see BEND_AXIS): the old X pose
        # twisted both joints instead of bending them, so the preview showed a
        # sleeve being wrung out rather than a bent arm.
        pose = {}
        for side in ("Left", "Right"):
            pose[f"{side}Arm"] = (2, 20)       # swing the shoulder in/down
            pose[f"{side}ForeArm"] = (BEND_AXIS, -22)
            pose[f"{side}Hand"] = (BEND_AXIS, -20)
        pw = posed_worlds(template, pose)
        posed_bones = [(template.id_name[sid], np.array(pw[sid][12:15], float),
                        template.id_name.get(template.id_obj[sid]["parent"])
                        if template.id_obj[sid]["parent"] else None)
                       for sid in pw]
        pv = skin_verts(geo, skel, pw)
        for view in ("front", "side"):
            render(geo, posed_bones, view, args.out / f"{stem}_skel_pose_{view}.png",
                   verts=pv)
        # the posed sleeve: select on the *posed* positions, then draw it
        pose_chain = [np.array(pw[sid][12:15], float) for sid in pw
                      if template.id_name.get(sid) in ("LeftForeArm", "LeftHand")]
        if len(pose_chain) == 2:
            hand = _largest_blobs(_subset_near_polyline(
                {"verts": pv, "faces": geo["faces"]}, pose_chain, radius=7.0))
            near_bones = _bones_near(pose_chain, posed_bones, radius=14.0)
            for view in ("front", "side"):
                render(hand, near_bones, view,
                       args.out / f"{stem}_skel_pose_wrist_{view}.png")
    if args.hang:
        # The in-game idle: elbow nearly straight. The bind pose bakes 72 deg
        # into the elbow, so the sleeve has to give back r*dtheta of length on
        # the outside of the bend - the pose where the crease folds (the
        # 2026-11-06 "X-fold" and the 2026-11-07 crumple measurements).
        # Straightening 72 -> 12 deg is -60 deg on the FLEXION axis; the old
        # (0, -80) rotated about a twist axis and left the joint at 72 deg.
        straighten = IDLE_ELBOW_DEG - BIND_ELBOW_DEG    # = -60
        pose = {f"{s}Arm": (2, 22) for s in ("Left", "Right")}
        pose.update({f"{s}ForeArm": (BEND_AXIS, straighten) for s in ("Left", "Right")})
        pose.update({f"{s}Hand": (BEND_AXIS, -8) for s in ("Left", "Right")})
        pw = posed_worlds(template, pose)
        posed_bones = [(template.id_name[sid], np.array(pw[sid][12:15], float),
                        template.id_name.get(template.id_obj[sid]["parent"])
                        if template.id_obj[sid]["parent"] else None)
                       for sid in pw]
        pv = skin_verts(geo, skel, pw)
        for view in ("front", "side"):
            render(geo, posed_bones, view, args.out / f"{stem}_hang_{view}.png",
                   verts=pv)
        chain_p = [np.array(pw[sid][12:15], float) for sid in pw
                   if template.id_name.get(sid) in
                   ("LeftArm", "LeftForeArm", "LeftHand")]
        if len(chain_p) == 3:
            tube = _largest_blobs(_subset_near_polyline(
                {"verts": pv, "faces": geo["faces"]}, chain_p, radius=8.0))
            near_bones = _bones_near(chain_p, posed_bones, radius=16.0)
            for view in ("front", "side"):
                render(tube, near_bones, view,
                       args.out / f"{stem}_hang_elbow_{view}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
