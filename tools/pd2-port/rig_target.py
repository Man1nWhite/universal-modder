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

import re
from dataclasses import dataclass, field

from me2_dae import DaeScene, Mesh, SkinBind, mmul, minv

# ME2 joint -> PD2 bone.
# In the ME2 COLLADA file, Miranda faces -Y with +X = Left and -X = Right.
# A 180-degree rotation around Z (diag(-1, -1, 1)) maps ME2 -Y (forward) to
# PD2 +Y (forward) and ME2 +X (Left*) to PD2 -X (Left*), preserving Left->Left
# and Right->Right without mirroring.
BONE_MAP: dict[str, str] = {
    # center line
    "God": "Hips",
    "root": "Hips",
    "Pelvis": "Hips",
    "LowerBack": "Hips",
    "Chest": "Spine",
    "Chest1": "Spine1",
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
    # ME2 left arm -> PD2 left arm
    "LeftCollar": "LeftShoulder",
    "LeftShoulder": "LeftArm",
    "LeftShoulderTwist1": "LeftArm",
    "LeftShoulderTwist2": "LeftArm",
    "LeftElbow": "LeftForeArm",
    "LeftElbowTwist1": "LeftForeArm",
    "LeftElbowTwist2": "LeftForeArm",
    "LeftWrist": "LeftHand",
    "LeftShoulder-Swivel": "LeftArm",
    "Prop02": "LeftHand",
    "LHIK": "LeftHand",
    # ME2 right arm -> PD2 right arm
    "RightCollar": "RightShoulder",
    "RightShoulder": "RightArm",
    "RightShoulderTwist1": "RightArm",
    "RightShoulderTwist2": "RightArm",
    "RightElbow": "RightForeArm",
    "RightElbowTwist1": "RightForeArm",
    "RightElbowTwist2": "RightForeArm",
    "RightWrist": "RightHand",
    "RightShoulder-Swivel": "RightArm",
    "Prop01": "RightHand",
    "RHIK": "RightHand",
    # ME2 left leg -> PD2 left leg
    "LeftHip": "LeftUpLeg",
    "LeftHipTwist1": "LeftUpLeg",
    "LeftKnee": "LeftLeg",
    "LeftAnkle": "LeftFoot",
    "LeftToe": "LeftToeBase",
    "LeftHip-Swivel": "LeftUpLeg",
    "LFIK": "LeftFoot",
    # ME2 right leg -> PD2 right leg
    "RightHip": "RightUpLeg",
    "RightHipTwist1": "RightUpLeg",
    "RightKnee": "RightLeg",
    "RightAnkle": "RightFoot",
    "RightToe": "RightToeBase",
    "RightHip-Swivel": "RightUpLeg",
    "RFIK": "RightFoot",
}

# Any name containing a finger token folds to its side's hand.
_FINGER_TOKENS = ("ThumbFinger", "PinkFinger", "IndexFinger",
                  "MiddleFinger", "RingFinger", "Finger")

# ME2's five finger chains (three joints each) map one-to-one onto PD2's five
# three-bone finger chains, so the fingers articulate instead of riding along
# with the hand. PD2 spells the little finger "Pinky"; ME2 spells it "Pink".
_FINGER_CHAINS = {
    "Thumb": "Thumb",
    "Index": "Index",
    "Middle": "Middle",
    "Ring": "Ring",
    "Pink": "Pinky",
}
for _side in ("Left", "Right"):
    for _me2_finger, _pd2_finger in _FINGER_CHAINS.items():
        for _joint in range(3):
            _me2_name = f"{_side}{_me2_finger}Finger" + (str(_joint) if _joint else "")
            BONE_MAP[_me2_name] = f"{_side}Hand{_pd2_finger}{_joint + 1}"

# Facial chains fold to Head.
_FACE_TOKENS = ("brow", "Brow", "eye", "Eye", "Lip", "lip", "Cheek", "cheek",
                "Lid", "lid", "Nose", "nose")


def map_joint(name: str) -> str:
    """Map one ME2 joint name to its PD2 bone name. Raises on unknown joints."""
    if name in BONE_MAP:
        return BONE_MAP[name]
    if any(tok in name for tok in _FINGER_TOKENS):
        return "LeftHand" if name.startswith("Left") else "RightHand"
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
    flipped_faces: int = 0                   # triangles repaired by repair_winding()


def repair_winding(positions, normals, triangles):
    """Reverse the triangles that face away from their own vertex normals.

    The bind-pose transfer rotates every bone piece independently (each piece
    is fitted onto the PD2 bone it is bound to), so where the ME2 and the PD2
    rigs disagree -- the hips, the wrists, the ankles -- the neighbouring
    pieces end up rotated against each other and a band of triangles folds
    back on itself.  A folded triangle is wound inside out: the game culls it
    (a hole in the skin) and the skin shades it backwards (a black patch).

    The vertex normals are the smooth normals of the *unfolded* surface, so
    the triangle's own winding is the thing that is wrong: swapping two
    indices puts the triangle back in front of the skin without moving a
    single vertex.  The ME2 meshes are corner-split (no shared edges), so
    flipping a triangle cannot make its neighbours inconsistent.

    Returns the repaired triangles and the number of flips.
    """
    out = []
    flipped = 0
    for a, b, c in triangles:
        p0, p1, p2 = positions[a], positions[b], positions[c]
        e1 = _sub(p1, p0)
        e2 = _sub(p2, p0)
        gn = _cross(e1, e2)
        ln = _dot(gn, gn) ** 0.5
        if ln > 1e-12:
            gn = [gn[0] / ln, gn[1] / ln, gn[2] / ln]
            avg = [normals[a][i] + normals[b][i] + normals[c][i] for i in range(3)]
            if _dot(gn, avg) < 0.0:
                b, c = c, b
                flipped += 1
        out.append((a, b, c))
    return out, flipped


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


def _make_sim_op(scale: float, R, p_src, p_tgt) -> list[list[float]]:
    """Row-vector 4x4 similarity transform mapping p_src -> p_tgt with column-vector rotation R."""
    M = [[scale * R[j][i] for j in range(3)] for i in range(3)]
    t = [p_tgt[k] - sum(p_src[i] * M[i][k] for i in range(3)) for k in range(3)]
    return [
        [M[0][0], M[0][1], M[0][2], 0.0],
        [M[1][0], M[1][1], M[1][2], 0.0],
        [M[2][0], M[2][1], M[2][2], 0.0],
        [t[0], t[1], t[2], 1.0],
    ]


def _apply_op(op: list[list[float]], p) -> list[float]:
    return [
        p[0] * op[0][0] + p[1] * op[1][0] + p[2] * op[2][0] + op[3][0],
        p[0] * op[0][1] + p[1] * op[1][1] + p[2] * op[2][1] + op[3][1],
        p[0] * op[0][2] + p[1] * op[1][2] + p[2] * op[2][2] + op[3][2],
    ]


def _col_rot_between(a, b) -> list[list[float]]:
    """Column-vector 3x3 minimal rotation mapping direction a to b."""
    rt = _rot_between(a, b)
    return [[rt[j][i] for j in range(3)] for i in range(3)]


def _mat3_mul(A, B) -> list[list[float]]:
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mat3_vec(A, v) -> list[float]:
    return [sum(A[i][k] * v[k] for k in range(3)) for i in range(3)]


def _mat3_inv_t(M) -> list[list[float]]:
    """Inverse-transpose (cofactor / det) of a 3x3 matrix."""
    c00 = M[1][1] * M[2][2] - M[1][2] * M[2][1]
    c01 = -(M[1][0] * M[2][2] - M[1][2] * M[2][0])
    c02 = M[1][0] * M[2][1] - M[1][1] * M[2][0]
    c10 = -(M[0][1] * M[2][2] - M[0][2] * M[2][1])
    c11 = M[0][0] * M[2][2] - M[0][2] * M[2][0]
    c12 = -(M[0][0] * M[2][1] - M[0][1] * M[2][0])
    c20 = M[0][1] * M[1][2] - M[0][2] * M[1][1]
    c21 = -(M[0][0] * M[1][2] - M[0][2] * M[1][0])
    c22 = M[0][0] * M[1][1] - M[0][1] * M[1][0]
    det = M[0][0] * c00 + M[0][1] * c01 + M[0][2] * c02
    inv_d = 1.0 / det
    return [
        [c00 * inv_d, c01 * inv_d, c02 * inv_d],
        [c10 * inv_d, c11 * inv_d, c12 * inv_d],
        [c20 * inv_d, c21 * inv_d, c22 * inv_d],
    ]


def _umeyama_sim_op(src_pts, tgt_pts, weights):
    """Weighted Umeyama similarity fit returning (op, R_col, scale)."""
    w_sum = sum(weights)
    w = [wi / w_sum for wi in weights]
    cs = [sum(w[k] * src_pts[k][i] for k in range(len(w))) for i in range(3)]
    ct = [sum(w[k] * tgt_pts[k][i] for k in range(len(w))) for i in range(3)]
    p0 = [[src_pts[k][i] - cs[i] for i in range(3)] for k in range(len(w))]
    q0 = [[tgt_pts[k][i] - ct[i] for i in range(3)] for k in range(len(w))]
    # H_T[i][j] = sum_k w[k] * q0[k][i] * p0[k][j]
    X = [[sum(w[k] * q0[k][i] * p0[k][j] for k in range(len(w))) for j in range(3)] for i in range(3)]
    H_T = [row[:] for row in X]
    for _ in range(12):
        inv_t = _mat3_inv_t(X)
        nx = sum(X[i][j] * X[i][j] for i in range(3) for j in range(3)) ** 0.5
        ni = sum(inv_t[i][j] * inv_t[i][j] for i in range(3) for j in range(3)) ** 0.5
        g = (ni / nx) ** 0.5
        X = [[0.5 * (g * X[i][j] + inv_t[i][j] / g) for j in range(3)] for i in range(3)]
    var_p = sum(w[k] * sum(p0[k][i] * p0[k][i] for i in range(3)) for k in range(len(w)))
    tr = sum(X[i][j] * H_T[i][j] for i in range(3) for j in range(3))
    s = tr / var_p if var_p > 1e-12 else 1.0
    return _make_sim_op(s, X, cs, ct), X, s


_FINGER_CHAINS = (
    ("Thumb", "ThumbFinger"),
    ("Index", "IndexFinger"),
    ("Middle", "MiddleFinger"),
    ("Ring", "RingFinger"),
    ("Pinky", "PinkFinger"),
)


def target_ops(scene: DaeScene, rig: TargetRig) -> dict[str, list[list[float]]]:
    """One bind operator per TARGET bone (row-vector).

    For the full ME2 biped, Miranda faces -Y in the COLLADA file with +X = Left
    and -X = Right at 1:1 cm scale (Pelvis z=101.2 vs PD2 101.8, Head z=166.1
    vs PD2 166.8, boot soles at z=0). A single upright rigid transform
    R_core = diag(-1, -1, 1) aligned at Hips (x, y) and grounded at z=0 maps
    the torso, head, shoulders, and legs without any seam between Body 1 and
    Body 2. The arms, palms, and 5 three-joint finger chains are retargeted so
    each knuckle and phalanx sits directly on its PD2 bone pivot.

    For synthetic minimal fixtures in unit tests, falls back to per-segment
    rigid fits.
    """
    if ("Pelvis" in scene.joints and "LeftShoulder" in scene.joints
            and "RightShoulder" in scene.joints and "LeftArm" in rig.world):
        R_core = [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
        p_hips_s = _v3(scene.joints["Pelvis"].world)
        p_hips_t = _v3(rig.world["Hips"])
        g_op = _make_sim_op(
            1.0, R_core,
            [p_hips_s[0], p_hips_s[1], 0.0],
            [p_hips_t[0], p_hips_t[1], 0.0],
        )
        ops: dict[str, list[list[float]]] = {t: g_op for t in rig.names}

        for side in ("Left", "Right"):
            ps_a = _v3(scene.joints[f"{side}Shoulder"].world)
            ps_f = _v3(scene.joints[f"{side}Elbow"].world)
            ps_h = _v3(scene.joints[f"{side}Wrist"].world)

            pt_a = _apply_op(g_op, ps_a)
            pt_f = _v3(rig.world[f"{side}ForeArm"])

            ds_af = _sub(ps_f, ps_a)
            dt_af = _sub(pt_f, pt_a)
            R_arm = _mat3_mul(_col_rot_between(_mat3_vec(R_core, ds_af), dt_af), R_core)
            s_arm = (_dot(dt_af, dt_af) ** 0.5) / (_dot(ds_af, ds_af) ** 0.5)
            op_arm = _make_sim_op(s_arm, R_arm, ps_a, pt_a)
            ops[f"{side}Arm"] = op_arm

            src_h = [
                _v3(scene.joints[f"{side}IndexFinger"].world),
                _v3(scene.joints[f"{side}MiddleFinger"].world),
                _v3(scene.joints[f"{side}RingFinger"].world),
                _v3(scene.joints[f"{side}PinkFinger"].world),
                _v3(scene.joints[f"{side}ThumbFinger"].world),
                ps_h,
            ]
            tgt_h = [
                _v3(rig.world[f"{side}HandIndex1"]),
                _v3(rig.world[f"{side}HandMiddle1"]),
                _v3(rig.world[f"{side}HandRing1"]),
                _v3(rig.world[f"{side}HandPinky1"]),
                _v3(rig.world[f"{side}HandThumb1"]),
                _v3(rig.world[f"{side}Hand"]),
            ]
            op_hand, R_hand, _ = _umeyama_sim_op(src_h, tgt_h, [1.0, 1.0, 1.0, 1.0, 0.8, 0.2])
            ops[f"{side}Hand"] = op_hand
            pt_wrist = _apply_op(op_hand, ps_h)

            ds_fh = _sub(ps_h, ps_f)
            dt_fh = _sub(pt_wrist, pt_f)
            R_fore = _mat3_mul(_col_rot_between(_mat3_vec(R_arm, ds_fh), dt_fh), R_arm)
            s_fore = (_dot(dt_fh, dt_fh) ** 0.5) / (_dot(ds_fh, ds_fh) ** 0.5)
            op_fore = _make_sim_op(s_fore, R_fore, ps_f, pt_f)
            ops[f"{side}ForeArm"] = op_fore
            ops[f"{side}ForeArmRoll"] = op_fore

            for f_pd2, f_me2 in _FINGER_CHAINS:
                s1 = _v3(scene.joints[f"{side}{f_me2}"].world)
                s2 = _v3(scene.joints[f"{side}{f_me2}1"].world)
                s3 = _v3(scene.joints[f"{side}{f_me2}2"].world)
                tw1 = _v3(rig.world[f"{side}Hand{f_pd2}1"])
                tw2 = _v3(rig.world[f"{side}Hand{f_pd2}2"])
                tw3 = _v3(rig.world[f"{side}Hand{f_pd2}3"])

                t1 = _apply_op(op_hand, s1)
                ds_12 = _sub(s2, s1)
                dt_12 = _sub(tw2, tw1)
                R_f1 = _mat3_mul(_col_rot_between(_mat3_vec(R_hand, ds_12), dt_12), R_hand)
                raw_s1 = (_dot(dt_12, dt_12) ** 0.5) / (_dot(ds_12, ds_12) ** 0.5)
                s_f1 = max(0.85, min(1.35, raw_s1))
                op_f1 = _make_sim_op(s_f1, R_f1, s1, t1)
                ops[f"{side}Hand{f_pd2}1"] = op_f1

                t2 = _apply_op(op_f1, s2)
                ds_23 = _sub(s3, s2)
                dt_23 = _sub(tw3, tw2)
                R_f2 = _mat3_mul(_col_rot_between(_mat3_vec(R_f1, ds_23), dt_23), R_f1)
                raw_s2 = (_dot(dt_23, dt_23) ** 0.5) / (_dot(ds_23, ds_23) ** 0.5)
                s_f2 = max(0.85, min(1.35, raw_s2))
                op_f2 = _make_sim_op(s_f2, R_f2, s2, t2)
                ops[f"{side}Hand{f_pd2}2"] = op_f2

                t3 = _apply_op(op_f2, s3)
                ops[f"{side}Hand{f_pd2}3"] = _make_sim_op(s_f2, R_f2, s3, t3)
        return ops

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
    ops = {}
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

    triangles, flipped = repair_winding(positions, normals, mesh.triangles)

    return RiggedMesh(
        name=mesh.name,
        material=mesh.material,
        positions=positions,
        normals=normals,
        uvs=mesh.uvs,
        triangles=triangles,
        weights=weights,
        flipped_faces=flipped,
    )


ARM_BONES = {
    "LeftArm", "LeftForeArm", "LeftForeArmRoll", "LeftHand",
    "RightArm", "RightForeArm", "RightForeArmRoll", "RightHand",
}

# The hand's finger chains belong to the arm for the FPS cut: without them the
# first-person unit loses the fingers (their vertices are dominated by the
# finger bones, not the wrist).
FINGER_BONE_RE = re.compile(r"^(?:Left|Right)Hand(?:Thumb|Index|Middle|Ring|Pinky)[123]$")


def is_arm_bone(name: str) -> bool:
    """True for the arm bones and the finger chains hanging off the hands."""
    return name in ARM_BONES or bool(FINGER_BONE_RE.match(name))


def dominant_bone(weights: list[tuple[str, float]]) -> str:
    return max(weights, key=lambda bw: bw[1])[0] if weights else "Hips"


def split_arm_verts(mesh: RiggedMesh) -> tuple[set[int], set[int]]:
    """Vertex indices (body, arms) by dominant bone — the FPS cut."""
    body: set[int] = set()
    arms: set[int] = set()
    for i, w in enumerate(mesh.weights):
        (arms if is_arm_bone(dominant_bone(w)) else body).add(i)
    return body, arms
