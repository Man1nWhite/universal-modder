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
            ps_sh = _v3(scene.joints[f"{side}Collar"].world)
            ps_a = _v3(scene.joints[f"{side}Shoulder"].world)
            ps_f = _v3(scene.joints[f"{side}Elbow"].world)
            ps_h = _v3(scene.joints[f"{side}Wrist"].world)

            pt_sh = _apply_op(g_op, ps_sh)
            pt_a = _v3(rig.world[f"{side}Arm"])
            pt_f = _v3(rig.world[f"{side}ForeArm"])
            pt_h = _v3(rig.world[f"{side}Hand"])

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
                pt_h,
            ]
            op_hand, R_hand, _ = _umeyama_sim_op(src_h, tgt_h, [1.0, 1.0, 1.0, 1.0, 0.8, 0.2])
            ops[f"{side}Hand"] = op_hand
            pt_wrist = _apply_op(op_hand, ps_h)

            # Construct Shoulder, Arm, and ForeArm bind operators via PD2's
            # standing menu pose M_menu = W_posed @ inv(W_bind):
            # 1. In the standing pose, the shoulder sits at a natural feminine
            #    width (+1.2 cm outward from ME2's native Shoulder) so the
            #    bare deltoid cap is round without a pointy overhang or gap
            #    between Body 1 and Body 2.
            # 2. The standing elbow is shifted 2.8 cm inward along the exact
            #    invariant hinge axis of inv(M_menu[Arm]) @ M_menu[ForeArm],
            #    so Arm and ForeArm meet with 0.000 cm gap in BOTH bind pose
            #    and standing pose while eliminating the outward elbow bow.
            # 3. Rank-1 axial scaling along each bone preserves 100% of the
            #    native radial arm thickness.
            sgn = -1.0 if side == "Left" else 1.0
            d_arm_bind = _sub(pt_f, pt_a)
            d_fa_bind = _sub(pt_h, pt_f)
            R_w_arm = _col_rot_between(d_arm_bind, [sgn * 0.17, -0.05, -0.98])
            R_w_fa_rel = _col_rot_between(_mat3_vec(R_w_arm, d_fa_bind), [sgn * 0.05, 0.25, -0.96])
            R_w_fa = _mat3_mul(R_w_fa_rel, R_w_arm)

            pt_f_posed = _add(pt_a, _mat3_vec(R_w_arm, d_arm_bind))
            M_arm_menu = _make_sim_op(1.0, R_w_arm, pt_a, pt_a)
            M_fa_menu = _make_sim_op(1.0, R_w_fa, pt_f, pt_f_posed)
            M_arm_menu_inv = minv(M_arm_menu)
            M_fa_menu_inv = minv(M_fa_menu)

            # Exact invariant hinge axis of R_w_fa_rel in posed space:
            hinge_raw = [
                R_w_fa_rel[2][1] - R_w_fa_rel[1][2],
                R_w_fa_rel[0][2] - R_w_fa_rel[2][0],
                R_w_fa_rel[1][0] - R_w_fa_rel[0][1],
            ]
            len_h = (_dot(hinge_raw, hinge_raw) ** 0.5) or 1.0
            ax_p = [hinge_raw[0] / len_h, hinge_raw[1] / len_h, hinge_raw[2] / len_h]
            if ax_p[0] * (-sgn) < 0.0:
                ax_p = [-ax_p[0], -ax_p[1], -ax_p[2]]

            ps_a_g = _apply_op(g_op, ps_a)
            pt_a_stand = [ps_a_g[0] + sgn * 1.2, ps_a_g[1], ps_a_g[2] - 0.3]
            pt_f_stand = [
                pt_f_posed[0] + 2.8 * ax_p[0],
                pt_f_posed[1] + 2.8 * ax_p[1],
                pt_f_posed[2] + 2.8 * ax_p[2],
            ]
            pt_h_stand = _apply_op(M_fa_menu, pt_wrist)

            def _axial_op(s_start, s_end, t_start, t_end, R_base):
                ds = _sub(s_end, s_start)
                dt = _sub(t_end, t_start)
                R_seg = _mat3_mul(_col_rot_between(_mat3_vec(R_base, ds), dt), R_base)
                len_dt = (_dot(dt, dt) ** 0.5) or 1.0
                lam = len_dt / ((_dot(ds, ds) ** 0.5) or 1.0)
                v = [dt[0] / len_dt, dt[1] / len_dt, dt[2] / len_dt]
                S_seg = [
                    [(1.0 if r == c else 0.0) + (lam - 1.0) * v[r] * v[c] for c in range(3)]
                    for r in range(3)
                ]
                return _make_sim_op(1.0, _mat3_mul(S_seg, R_seg), s_start, t_start), R_seg

            op_sh_menu, _ = _axial_op(ps_sh, ps_a, pt_sh, pt_a_stand, R_core)
            op_arm_menu, R_arm_m = _axial_op(ps_a, ps_f, pt_a_stand, pt_f_stand, R_core)
            op_fa_menu, _ = _axial_op(ps_f, ps_h, pt_f_stand, pt_h_stand, R_arm_m)

            ops[f"{side}Shoulder"] = op_sh_menu
            ops[f"{side}Arm"] = mmul(op_arm_menu, M_arm_menu_inv)
            op_fore = mmul(op_fa_menu, M_fa_menu_inv)
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

    ops_inv = {t: minv(op) for t, op in ops.items()}
    r_op = None
    r_op_inv = None

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
        weights = [[] for _ in mesh.positions]

    positions = []
    normals = []
    for vi, p in enumerate(mesh.positions):
        infl = weights[vi] if vi < len(weights) else []
        if not infl:
            if r_op is None:
                r_op = root_op()
                r_op_inv = minv(r_op)
            op = r_op
            op_inv = r_op_inv
        elif len(infl) == 1:
            t0 = infl[0][0]
            op = ops[t0]
            op_inv = ops_inv[t0]
        else:
            # Harmonic (matrix-inverse) blend so runtime LBS unbending
            # recovers the true unbent joint cross-section without pinching.
            op_inv = [[0.0, 0.0, 0.0, 0.0] for _ in range(4)]
            for tn, w in infl:
                inv_k = ops_inv[tn]
                for r in range(4):
                    for c in range(4):
                        op_inv[r][c] += w * inv_k[r][c]
            op = minv(op_inv)
        px = p[0] * op[0][0] + p[1] * op[1][0] + p[2] * op[2][0] + op[3][0]
        py = p[0] * op[0][1] + p[1] * op[1][1] + p[2] * op[2][1] + op[3][1]
        pz = p[0] * op[0][2] + p[1] * op[1][2] + p[2] * op[2][2] + op[3][2]
        positions.append((px, py, pz))

        if vi < len(mesh.normals):
            n = mesh.normals[vi]
            nx = n[0] * op_inv[0][0] + n[1] * op_inv[0][1] + n[2] * op_inv[0][2]
            ny = n[0] * op_inv[1][0] + n[1] * op_inv[1][1] + n[2] * op_inv[1][2]
            nz = n[0] * op_inv[2][0] + n[1] * op_inv[2][1] + n[2] * op_inv[2][2]
            ln = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
            normals.append((nx / ln, ny / ln, nz / ln))

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
