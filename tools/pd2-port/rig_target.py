#!/usr/bin/env python3
"""Map the ME2 Miranda skeleton onto the PD2 LAS rig and rebind the skin.

The PD2 rig contract lives in ``reference/las_rig.json`` (extracted from the
user-supplied ``2b.rar`` reference model by ``extract_las_rig.py``). The ME2
COLLADA rig is a full facial biped; joints that have no PD2 counterpart fold
into their nearest mapped parent.

Two rig facts drive the mapping:

- Both rigs are Z-up centimeters with nearly identical bind heights (hips
  z≈101, head z≈166), so the transfer is close to rigid per limb.
- The ME2 rig labels sides observer-relative: its ``Left*`` chain sits at +X
  where the PD2 rig has ``Right*``. Joints are therefore mapped **by world
  side** (ME2 ``Left*`` → PD2 ``Right*`` and vice versa). Residual risk: if the
  source mesh itself is mirrored (not just labelled), asymmetric surface detail
  will show it — verify in-game.

Skin transfer is the standard bind-pose rebind::

    p_target = sum_i w_i * (W_target_i @ W_source_i^-1) @ p_source

in row-vector form ``p' = p @ mmul(minv(W_s), W_t)``. Vertices then animate on
the PD2 skeleton with ``SkinBones.rotations = inv(W_target)``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from me2_dae import DaeScene, Mesh, SkinBind, mmul, minv

# ME2 joint -> PD2 bone. Sides are swapped: ME2 Left* is world +X = PD2 Right*.
BONE_MAP: dict[str, str] = {
    # center line
    "God": "Hips",
    "root": "Hips",
    "Pelvis": "Hips",
    "LowerBack": "Spine",
    "Chest": "Spine1",
    "Chest1": "Spine2",
    "Chest2": "Spine2",
    "Neck": "Neck",
    "Neck1": "Neck",
    "Head": "Head",
    "headBase": "Head",
    "mouthBase": "Head",
    "jawBone": "Head",
    "Tongue": "Head",
    "Sneer": "Head",
    "eyeLookAtBase": "Head",
    "eyeLookAt": "Head",
    "eye_RightLookat": "Head",
    "eye_LeftLookat": "Head",
    "Camera": "Head",
    # ME2 left arm -> PD2 right arm
    "LeftCollar": "RightShoulder",
    "LeftShoulder": "RightArm",
    "LeftShoulderTwist1": "RightArm",
    "LeftShoulderTwist2": "RightArm",
    "LeftElbow": "RightForeArm",
    "LeftElbowTwist1": "RightForeArm",
    "LeftElbowTwist2": "RightForeArm",
    "LeftWrist": "RightHand",
    "LeftShoulder-Swivel": "RightArm",
    "Prop02": "RightHand",
    # ME2 right arm -> PD2 left arm
    "RightCollar": "LeftShoulder",
    "RightShoulder": "LeftArm",
    "RightShoulderTwist1": "LeftArm",
    "RightShoulderTwist2": "LeftArm",
    "RightElbow": "LeftForeArm",
    "RightElbowTwist1": "LeftForeArm",
    "RightElbowTwist2": "LeftForeArm",
    "RightWrist": "LeftHand",
    "RightShoulder-Swivel": "LeftArm",
    "Prop01": "LeftHand",
    "LHIK": "LeftHand",
    # ME2 left leg -> PD2 right leg
    "LeftHip": "RightUpLeg",
    "LeftHipTwist1": "RightUpLeg",
    "LeftKnee": "RightLeg",
    "LeftAnkle": "RightFoot",
    "LeftToe": "RightToeBase",
    "LeftHip-Swivel": "RightUpLeg",
    # ME2 right leg -> PD2 left leg
    "RightHip": "LeftUpLeg",
    "RightHipTwist1": "LeftUpLeg",
    "RightKnee": "LeftLeg",
    "RightAnkle": "LeftFoot",
    "RightToe": "LeftToeBase",
    "RightHip-Swivel": "LeftUpLeg",
    # IK helpers: fold to hips (unweighted in practice)
    "RHIK": "Hips",
    "LFIK": "Hips",
    "RFIK": "Hips",
}

# Any name containing a finger token folds to its side's hand (after swap).
_FINGER_TOKENS = ("ThumbFinger", "PinkFinger", "IndexFinger",
                  "MiddleFinger", "RingFinger", "Finger")

# ME2's five finger chains (three joints each) map one-to-one onto PD2's five
# three-bone finger chains, so the fingers articulate instead of riding along
# with the hand. Sides swap with the arms: ME2 ``Left*`` is world +X = PD2
# ``Right*``. PD2 spells the little finger "Pinky"; ME2 spells it "Pink".
_FINGER_CHAINS = {
    "Thumb": "Thumb",
    "Index": "Index",
    "Middle": "Middle",
    "Ring": "Ring",
    "Pink": "Pinky",
}
for _me2_side, _pd2_side in (("Left", "Right"), ("Right", "Left")):
    for _me2_finger, _pd2_finger in _FINGER_CHAINS.items():
        for _joint in range(3):
            _me2_name = f"{_me2_side}{_me2_finger}Finger" + (str(_joint) if _joint else "")
            BONE_MAP[_me2_name] = f"{_pd2_side}Hand{_pd2_finger}{_joint + 1}"

# Facial chains fold to Head.
_FACE_TOKENS = ("brow", "Brow", "eye", "Eye", "Lip", "lip", "Cheek", "cheek",
                "Lid", "lid", "Nose", "nose")


def map_joint(name: str) -> str:
    """Map one ME2 joint name to its PD2 bone name. Raises on unknown joints."""
    if name in BONE_MAP:
        return BONE_MAP[name]
    if any(tok in name for tok in _FINGER_TOKENS):
        return "RightHand" if name.startswith("Left") else "LeftHand"
    if any(tok in name for tok in _FACE_TOKENS):
        return "Head"
    raise KeyError(f"unmapped ME2 joint: {name!r}")


@dataclass
class RiggedMesh:
    """Mesh rebound to the PD2 rig."""
    name: str
    material: str
    positions: list[tuple[float, float, float]]   # PD2 root space, cm
    normals: list[tuple[float, float, float]]
    uvs: list[tuple[float, float]]
    triangles: list[tuple[int, int, int]]
    # per vertex, up to 3 (pd2_bone_name, weight), normalized
    weights: list[list[tuple[str, float]]]


@dataclass
class TargetRig:
    names: list[str]                             # named PD2 bones (palette-eligible)
    world: dict[str, list[list[float]]]          # row-vector bind worlds by name
    by_name: dict[str, dict]                     # raw JSON entries by name
    entries: list[dict] = field(default_factory=list)  # full main-tree object3Ds


def load_target_rig(path) -> TargetRig:
    import json
    data = json.load(open(path))
    # main tree only: the reference file also carries a duplicated 10000+ tree
    entries = [b for b in data["bones"] if b["id"] < 10000]
    by_name = {b["name"]: b for b in entries if b["name"]}
    names = [b["name"] for b in entries if b["name"] and b["name"] != "root_point"]
    world = {n: by_name[n]["world"] for n in names}
    return TargetRig(names=names, world=world, by_name=by_name, entries=entries)


def _v3(m):
    return [m[3][0], m[3][1], m[3][2]]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _smul(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _unit(v):
    ln = _dot(v, v) ** 0.5
    return [v[0] / ln, v[1] / ln, v[2] / ln] if ln > 1e-12 else None


def _rot_between(a, b):
    """Minimal rotation matrix (row-vector 3x3) mapping direction a to b."""
    ua, ub = _unit(a), _unit(b)
    if ua is None or ub is None:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    c = max(-1.0, min(1.0, _dot(ua, ub)))
    axis = _cross(ua, ub)
    s = _dot(axis, axis) ** 0.5
    if s < 1e-9:
        if c > 0:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        # antiparallel: rotate pi around any axis orthogonal to ua
        ortho = [1.0, 0.0, 0.0] if abs(ua[0]) < 0.9 else [0.0, 1.0, 0.0]
        axis = _unit(_cross(ua, ortho))
        s = 0.0
        c = -1.0
    kx, ky, kz = _unit(axis)
    # Rodrigues, column-vector convention
    K = [[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]]
    R = [[(1 if i == j else 0) + s * K[i][j] + (1 - c) * sum(K[i][k] * K[k][j]
          for k in range(3)) for j in range(3)] for i in range(3)]
    # return as row-vector matrix = R^T
    return [[R[j][i] for j in range(3)] for i in range(3)]


def _fit_rigid(head_s, tail_s, head_t, tail_t):
    """Row-vector 4x4 rigid map aligning source bone segment onto target."""
    R = _rot_between(_sub(tail_s, head_s), _sub(tail_t, head_t))
    # t = head_t - head_s · R  (row-vector multiply)
    hs = head_s
    th = [sum(hs[i] * R[i][k] for i in range(3)) for k in range(3)]
    t = _sub(head_t, th)
    return [[R[0][0], R[0][1], R[0][2], 0.0],
            [R[1][0], R[1][1], R[1][2], 0.0],
            [R[2][0], R[2][1], R[2][2], 0.0],
            [t[0], t[1], t[2], 1.0]]


def _segments(heads, parents, children_of):
    """Bone segments: head -> mean(children heads), extended at leaves."""
    segs = {}
    for name, head in heads.items():
        kids = children_of.get(name, [])
        if kids:
            acc = [0.0, 0.0, 0.0]
            for k in kids:
                acc = _add(acc, heads[k])
            tail = _smul(acc, 1.0 / len(kids))
        elif parents.get(name) in heads:
            ph = heads[parents[name]]
            tail = _add(head, _sub(head, ph))
        else:
            tail = _add(head, [0.0, 0.0, 1.0])
        segs[name] = (head, tail)
    return segs


def source_segments(scene: DaeScene):
    parents = {n: j.parent for n, j in scene.joints.items()}
    children_of: dict[str, list[str]] = {}
    for n, p in parents.items():
        if p:
            children_of.setdefault(p, []).append(n)
    heads = {n: _v3(j.world) for n, j in scene.joints.items()}
    return _segments(heads, parents, children_of)


def target_segments(rig: TargetRig):
    by_id = {e["id"]: e for e in rig.entries}
    parents = {}
    for e in rig.entries:
        if not e.get("name"):
            continue
        par = by_id.get(e.get("parent_id"))
        if par is not None and par.get("name"):
            parents[e["name"]] = par["name"]
    children_of: dict[str, list[str]] = {}
    for n, p in parents.items():
        children_of.setdefault(p, []).append(n)
    heads = {n: _v3(w) for n, w in rig.world.items()}
    return _segments(heads, parents, children_of)


def target_ops(scene: DaeScene, rig: TargetRig) -> dict[str, list[list[float]]]:
    """One bind operator per TARGET bone (row-vector).

    The naive operator minv(W_s) @ W_t bakes each bone's local frame
    convention into the mesh as a rotation: ME2 and Diesel bones use different
    local axes, so consecutive pieces (upper arm vs forearm) landed at
    mutually wrong angles — the retargeted figure tore apart even though both
    bind poses are the same A-pose. The operator is therefore the rigid fit of
    the source bone SEGMENT (head -> tail) onto the target bone segment:
    orientations of the stored frames never enter.

    Several source joints fold onto the same PD2 bone (fingers -> hand,
    face/brow/eye/jaw -> Head, rolls/twists -> parent). All joints in one fold
    group share the operator of the group's representative — the source joint
    carrying the most skin weight in the scene — so a folded piece moves
    rigidly with its target bone and keeps its shape exactly (per-joint
    operators tore the face apart: median edge distortion 68%).
    """
    used: dict[str, float] = {}
    for m in scene.meshes:
        for binds in m.weights:
            for b in binds:
                used[b.joint] = used.get(b.joint, 0.0) + b.weight
    groups: dict[str, list[str]] = {}
    for joint in used:
        groups.setdefault(map_joint(joint), []).append(joint)
    src_seg = source_segments(scene)
    tgt_seg = target_segments(rig)
    ops: dict[str, list[list[float]]] = {}
    for tgt, joints in groups.items():
        star = max(joints, key=lambda j: used[j])
        h_s, t_s = src_seg[star]
        h_t, t_t = tgt_seg[tgt]
        ops[tgt] = _fit_rigid(h_s, t_s, h_t, t_t)
    return ops


def weld_adjacency(positions, triangles) -> list[list[int]]:
    """Neighbour graph of a possibly corner-split mesh.

    The ME2 DAEs duplicate vertices per corner (separate normals/uvs), so
    triangle-index edges alone form isolated 3-vertex islands: any per-vertex
    processing then pulls coincident twins apart and the surface shreds.
    Twins (identical positions) are therefore wired together too.
    """
    n = len(positions)
    neigh: list[set[int]] = [set() for _ in range(n)]
    for i, j, k in triangles:
        neigh[i].update((j, k)); neigh[j].update((i, k)); neigh[k].update((i, j))
    by_pos: dict[tuple, list[int]] = {}
    for v, p in enumerate(positions):
        by_pos.setdefault((round(p[0], 4), round(p[1], 4), round(p[2], 4),
                           ), []).append(v)
    for group in by_pos.values():
        for v in group:
            neigh[v].update(group)
    return [sorted(s) for s in neigh]


def smooth_weights(weights, positions, triangles, iters: int = 2,
                   alpha: float = 0.5) -> list[list[SkinBind]]:
    """Laplacian-smooth a skin weight field over the WELDED mesh graph (pure).

    Hard weight boundaries (crotch, armpit) make neighbouring vertices take
    different bind operators and tear: single vertices displaced 7-12 cm more
    than their neighbours. Blending each vertex's weights toward the mean of
    its edge neighbours softens those seams; the same smoothed field is what
    the game deforms with at runtime, so animation seams improve too.

    The DAE meshes are corner-split (twins share a position but not an
    index). Smoothing per index pulls twins apart and shreds the surface, so
    weights are averaged per welded position, smoothed on the welded graph,
    and broadcast back to every twin — coincident vertices stay coincident.
    """
    n = len(weights)
    if iters <= 0 or n == 0:
        return weights
    by_pos: dict[tuple, int] = {}
    canon: list[int] = [0] * n           # vertex -> canonical id
    members: dict[int, list[int]] = {}
    for v, p in enumerate(positions):
        key = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
        cid = by_pos.setdefault(key, len(by_pos))
        canon[v] = cid
        members.setdefault(cid, []).append(v)
    # one weight list per welded position (twins averaged — identical in
    # practice, averaging keeps the map total)
    cw: list[dict[str, float]] = []
    for cid in range(len(by_pos)):
        acc: dict[str, float] = {}
        for v in members[cid]:
            for b in weights[v]:
                acc[b.joint] = acc.get(b.joint, 0.0) + b.weight
        total = sum(acc.values()) or 1.0
        cw.append({k: w / total for k, w in acc.items()})
    cneigh: list[set[int]] = [set() for _ in range(len(by_pos))]
    for i, j, k in triangles:
        a, b, c = canon[i], canon[j], canon[k]
        cneigh[a].update((b, c)); cneigh[b].update((a, c)); cneigh[c].update((a, b))
    for _ in range(iters):
        new: list[dict[str, float]] = []
        for v in range(len(cw)):
            acc = {k: alpha * w for k, w in cw[v].items()}
            ns = cneigh[v]
            if ns:
                share = (1.0 - alpha) / len(ns)
                for nb in ns:
                    for k, w in cw[nb].items():
                        acc[k] = acc.get(k, 0.0) + share * w
            total = sum(acc.values()) or 1.0
            new.append({k: w / total for k, w in acc.items()})
        cw = new
    # broadcast back: every twin receives its welded result, top-3
    out: list[list[SkinBind]] = []
    for v in range(n):
        top = sorted(cw[canon[v]].items(), key=lambda kv: -kv[1])[:3]
        total = sum(w for _, w in top) or 1.0
        out.append([SkinBind(name, w / total) for name, w in top])
    return out


def rebind_mesh(mesh: Mesh, scene: DaeScene, rig: TargetRig,
                smooth_iters: int = 0) -> RiggedMesh:
    """Bind-pose skin transfer from the ME2 scene to the PD2 rig (cm, Z-up)."""
    src_weights = (smooth_weights(mesh.weights, mesh.positions, mesh.triangles,
                                 smooth_iters)
                   if smooth_iters else mesh.weights)
    # one operator per target bone; folded joints share it (see target_ops)
    ops = target_ops(scene, rig)

    def root_op():
        root_name = "root" if "root" in scene.joints else "God"
        return mmul(minv(scene.joints[root_name].world), rig.world["Hips"])

    positions = []
    for p in mesh.positions:
        acc = [0.0, 0.0, 0.0]
        binds = src_weights[len(positions)] if src_weights else []
        if not binds:
            binds = []
        for b in binds:
            op = ops[map_joint(b.joint)]
            w = b.weight
            acc[0] += w * (p[0] * op[0][0] + p[1] * op[1][0] + p[2] * op[2][0] + op[3][0])
            acc[1] += w * (p[0] * op[0][1] + p[1] * op[1][1] + p[2] * op[2][1] + op[3][1])
            acc[2] += w * (p[0] * op[0][2] + p[1] * op[1][2] + p[2] * op[2][2] + op[3][2])
        if not binds:
            op = root_op()
            acc = [p[0] * op[0][0] + p[1] * op[1][0] + p[2] * op[2][0] + op[3][0],
                   p[0] * op[0][1] + p[1] * op[1][1] + p[2] * op[2][1] + op[3][1],
                   p[0] * op[0][2] + p[1] * op[1][2] + p[2] * op[2][2] + op[3][2]]
        positions.append((acc[0], acc[1], acc[2]))

    normals = []
    for n in mesh.normals:
        acc = [0.0, 0.0, 0.0]
        for b in (src_weights[len(normals)] if src_weights else []):
            op = ops[map_joint(b.joint)]
            w = b.weight
            acc[0] += w * (n[0] * op[0][0] + n[1] * op[1][0] + n[2] * op[2][0])
            acc[1] += w * (n[0] * op[0][1] + n[1] * op[1][1] + n[2] * op[2][1])
            acc[2] += w * (n[0] * op[0][2] + n[1] * op[1][2] + n[2] * op[2][2])
        ln = (acc[0] ** 2 + acc[1] ** 2 + acc[2] ** 2) ** 0.5 or 1.0
        normals.append((acc[0] / ln, acc[1] / ln, acc[2] / ln))

    weights: list[list[tuple[str, float]]] = []
    for binds in src_weights:
        merged: dict[str, float] = {}
        for b in binds:
            t = map_joint(b.joint)
            merged[t] = merged.get(t, 0.0) + b.weight
        top = sorted(merged.items(), key=lambda kv: -kv[1])[:3]
        total = sum(w for _, w in top) or 1.0
        weights.append([(n, w / total) for n, w in top])
    if not weights:
        weights = [[] for _ in positions]

    return RiggedMesh(
        name=mesh.name,
        material=mesh.material,
        positions=positions,
        normals=normals,
        uvs=mesh.uvs,
        triangles=mesh.triangles,
        weights=weights,
    )


ARM_BONES = {
    "LeftArm", "LeftForeArm", "LeftForeArmRoll", "LeftHand",
    "RightArm", "RightForeArm", "RightForeArmRoll", "RightHand",
}


def dominant_bone(weights: list[tuple[str, float]]) -> str:
    return max(weights, key=lambda bw: bw[1])[0] if weights else "Hips"


def split_arm_verts(mesh: RiggedMesh) -> tuple[set[int], set[int]]:
    """Vertex indices (body, arms) by dominant bone — the FPS cut."""
    body: set[int] = set()
    arms: set[int] = set()
    for i, w in enumerate(mesh.weights):
        (arms if dominant_bone(w) in ARM_BONES else body).add(i)
    return body, arms
