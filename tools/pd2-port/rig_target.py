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

from me2_dae import DaeScene, Mesh, mmul, minv

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


def rebind_mesh(mesh: Mesh, scene: DaeScene, rig: TargetRig) -> RiggedMesh:
    """Bind-pose skin transfer from the ME2 scene to the PD2 rig (cm, Z-up)."""
    # per source joint: operator = minv(W_s) @ W_t  (row-vector)
    ops: dict[str, list[list[float]]] = {}
    for joint, j in scene.joints.items():
        tgt = map_joint(joint)
        W_t = rig.world[tgt]
        ops[joint] = mmul(minv(j.world), W_t)

    positions = []
    for p in mesh.positions:
        acc = [0.0, 0.0, 0.0]
        binds = mesh.weights[len(positions)] if mesh.weights else []
        if not binds:
            binds = []
        for b in binds:
            op = ops[b.joint]
            w = b.weight
            acc[0] += w * (p[0] * op[0][0] + p[1] * op[1][0] + p[2] * op[2][0] + op[3][0])
            acc[1] += w * (p[0] * op[0][1] + p[1] * op[1][1] + p[2] * op[2][1] + op[3][1])
            acc[2] += w * (p[0] * op[0][2] + p[1] * op[1][2] + p[2] * op[2][2] + op[3][2])
        if not binds:
            op = ops["root"] if "root" in ops else mmul(minv(scene.joints["God"].world), rig.world["Hips"])
            acc = [p[0] * op[0][0] + p[1] * op[1][0] + p[2] * op[2][0] + op[3][0],
                   p[0] * op[0][1] + p[1] * op[1][1] + p[2] * op[2][1] + op[3][1],
                   p[0] * op[0][2] + p[1] * op[1][2] + p[2] * op[2][2] + op[3][2]]
        positions.append((acc[0], acc[1], acc[2]))

    normals = []
    for n in mesh.normals:
        acc = [0.0, 0.0, 0.0]
        for b in (mesh.weights[len(normals)] if mesh.weights else []):
            op = ops[b.joint]
            w = b.weight
            acc[0] += w * (n[0] * op[0][0] + n[1] * op[1][0] + n[2] * op[2][0])
            acc[1] += w * (n[0] * op[0][1] + n[1] * op[1][1] + n[2] * op[2][1])
            acc[2] += w * (n[0] * op[0][2] + n[1] * op[1][2] + n[2] * op[2][2])
        ln = (acc[0] ** 2 + acc[1] ** 2 + acc[2] ** 2) ** 0.5 or 1.0
        normals.append((acc[0] / ln, acc[1] / ln, acc[2] / ln))

    weights: list[list[tuple[str, float]]] = []
    for binds in mesh.weights:
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
