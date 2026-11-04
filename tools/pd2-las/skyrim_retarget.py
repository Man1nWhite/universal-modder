"""Retarget a Skyrim (XPMSE / 3BA) outfit onto the PAYDAY 2 player skeleton.

`build_models.retarget_maps` solves the same problem for the L4D2 Source rig,
but it leans on Source-only joint names (`HandMiddle1`, `ToeBase`) that the
BodySlide export of a Skyrim outfit does not carry: the garments in `4.zip`
are skinned to 20 deform bones, with **no fingers beyond the first thumb, no
toes, no neck and no head** — BodySlide keeps only the bones the merged mesh
actually weights.

So this module measures the same thing from the joints that *do* exist:

* one **core similarity fit** (Umeyama) over the torso and hip joints, which
  fixes the global orientation, scale and the pelvis placement;
* **axial chains** for the limbs and the spine: each segment gets the rotation
  that points it at its PD2 counterpart and a rank-1 scale along the segment
  (matching the target bone length) while keeping the source's radial
  thickness — the same trick `retarget_maps` uses for the arms;
* every joint therefore lands **exactly** on its PD2 joint, so the mesh's
  elbows, knees, wrists and ankles sit where the animations expect them.

A bone with no joint of its own (a twist bone folded into its parent, or a
thumb stub) inherits its chain's last fit.
"""

from __future__ import annotations

import numpy as np

import build_models as bm  # _umeyama_fit, _rodrigues_arc, _decompose_sim_mat
import diesel_model as dm

# joint order along each chain, root first
SPINE_CHAIN = ("Hips", "Spine", "Spine1", "Spine2")
LEG_CHAIN = ("UpLeg", "Leg", "Foot")
ARM_CHAIN = ("Shoulder", "Arm", "ForeArm", "Hand")

# bones that ride a chain but never define a joint
CHAIN_OF_BONE = {
    "Hips": "spine", "Spine": "spine", "Spine1": "spine", "Spine2": "spine",
    "Neck": "spine", "Head": "spine",
    "LeftUpLeg": "leg.L", "LeftLeg": "leg.L", "LeftFoot": "leg.L",
    "LeftToeBase": "leg.L",
    "RightUpLeg": "leg.R", "RightLeg": "leg.R", "RightFoot": "leg.R",
    "RightToeBase": "leg.R",
    "LeftShoulder": "arm.L", "LeftArm": "arm.L", "LeftForeArm": "arm.L",
    "LeftHand": "arm.L",
    "RightShoulder": "arm.R", "RightArm": "arm.R", "RightForeArm": "arm.R",
    "RightHand": "arm.R",
}

CORE_JOINTS = ("Hips", "Spine", "Spine1", "Spine2",
               "LeftShoulder", "RightShoulder", "LeftUpLeg", "RightUpLeg")

# the fit may stretch a spine/limb segment, but never the whole body
SCALE_CLAMP = (0.5, 2.5)


def row_mat(linear: np.ndarray, p_src: np.ndarray, p_tgt: np.ndarray) -> np.ndarray:
    """4x4 affine in dm.Mat's row-vector convention: p' = p @ M.

    ``linear`` is the column-vector 3x3 (p' = A p), so the row form is A^T with
    the translation in the last row.
    """
    a = np.asarray(linear, dtype=np.float64).T
    m = np.eye(4)
    m[:3, :3] = a
    m[3, :3] = np.asarray(p_tgt, dtype=np.float64) - np.asarray(p_src, dtype=np.float64) @ a
    return m


def _chain(pairs: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
           r_start: np.ndarray, s_radial: float) -> list[np.ndarray]:
    """Walk a joint chain, returning one 3x4 [S·R | t] transform per joint.

    ``pairs`` is ``[(p_src, p_tgt, next_src, next_tgt), ...]`` — for each joint
    in the chain, its position and the position of the next joint (the segment
    that joint governs).
    """
    out: list[np.ndarray] = []
    r_prev = r_start
    for p_src, p_tgt, q_src, q_tgt in pairs:
        d_src = q_src - p_src
        d_tgt = q_tgt - p_tgt
        r_seg = bm._rodrigues_arc(r_prev @ d_src, d_tgt) @ r_prev
        len_src = float(np.linalg.norm(d_src))
        len_tgt = float(np.linalg.norm(d_tgt))
        lam = float(np.clip(len_tgt / max(len_src, 1e-9), *SCALE_CLAMP))
        v = d_tgt / max(len_tgt, 1e-9)
        s_seg = s_radial * np.eye(3) + (lam - s_radial) * np.outer(v, v)
        # row-vector convention, like every dm.Mat in build_models
        m = row_mat(s_seg @ r_seg, p_src, p_tgt)
        out.append(m)
        r_prev = r_seg
    return out


def retarget_fits(model, template) -> dict[int, dm.Mat]:
    """Per source-bone similarity transform: source world (NIF units) -> PD2 cm."""
    pos = {}
    for bone in model.bones:
        pos[bone.name] = np.asarray(bone.pos, dtype=np.float64)

    def has(name: str) -> bool:
        return name in pos and name in template.name_id

    def tgt(name: str) -> np.ndarray:
        return np.asarray(template.worlds[template.name_id[name]][12:15], dtype=np.float64)

    core = [n for n in CORE_JOINTS if has(n)]
    if len(core) < 4:
        core = [n for n in pos if n in template.name_id][:8]
    if len(core) < 3:
        raise SystemExit("cannot fit: fewer than 3 shared joints")
    g_fit = bm._umeyama_fit(
        [tuple(pos[n].tolist()) for n in core],
        [tuple(tgt(n).tolist()) for n in core],
        [1.0] * len(core),
    )
    s_core, r_core, _ = bm._decompose_sim_mat(g_fit)
    s_core = float(np.clip(s_core, *SCALE_CLAMP))

    fits: dict[str, np.ndarray] = {}

    def put(name: str, m: np.ndarray) -> None:
        fits[name] = m

    # --- core: one rigid similarity, root snapped onto PD2's pelvis
    m_root = bm._make_sim_mat(s_core, r_core, pos["Hips"], tgt("Hips")) \
        if "Hips" in pos and has("Hips") else g_fit
    put("Hips", np.asarray(m_root, dtype=np.float64).reshape(4, 4))

    # --- spine chain (Hips -> Spine -> Spine1 -> Spine2), axial per segment
    spine = [n for n in SPINE_CHAIN if n in pos and has(n)]
    if len(spine) >= 2:
        pairs = [(pos[a], tgt(a), pos[b], tgt(b)) for a, b in zip(spine, spine[1:])]
        mats = _chain(pairs, r_core, s_core)
        # Same convention as the limb chains: a bone is governed by the
        # segment running from itself to its child. Taking the segment that
        # *ends* at the bone instead gives the first spine bone the
        # Hips->Spine hop, which in 3BA is a backward sacrum offset rather
        # than a direction — that fit rotated the waist by 38 degrees and
        # arched the torso. The last bone has no child segment of its own
        # and rides its neighbour's.
        for name, m in zip(spine[1:], mats[1:]):
            put(name, m)
        if spine:
            put(spine[-1], mats[-1])
    last_spine = spine[-1] if spine else "Hips"
    for extra in ("Neck", "Head"):
        if has(extra) and last_spine != extra:
            prev = fits.get(last_spine, fits["Hips"])
            put(extra, prev)

    # --- legs: UpLeg -> Leg -> Foot (rooted at the pelvis)
    for side in ("Left", "Right"):
        names = [f"{side}{n}" for n in LEG_CHAIN]
        if not all(n in pos and n in template.name_id for n in names):
            continue
        joints = [pos["Hips"] if not has(f"{side}UpLeg") else pos[f"{side}UpLeg"]]
        joints += [pos[n] for n in names[1:]]
        targets = [tgt(names[0])] + [tgt(n) for n in names[1:]]
        pairs = [(joints[i], targets[i], joints[i + 1], targets[i + 1])
                 for i in range(len(names) - 1)]
        mats = _chain(pairs, r_core, s_core)
        for name, m in zip(names, mats):
            put(name, m)
        toe = f"{side}ToeBase"
        if toe in pos and has(toe):
            put(toe, fits[names[-1]])

    # --- arms: Shoulder -> Arm -> ForeArm -> Hand, rooted at the chest
    for side in ("Left", "Right"):
        names = [f"{side}{n}" for n in ARM_CHAIN]
        if not all(n in pos and n in template.name_id for n in names):
            continue
        pairs = [(pos[a], tgt(a), pos[b], tgt(b)) for a, b in zip(names, names[1:])]
        mats = _chain(pairs, r_core, s_core)
        for name, m in zip(names, mats):
            put(name, m)

    # --- anything else rides the fit of the chain its name belongs to
    chain_anchor = {
        "spine": fits.get("Spine2", fits["Hips"]),
        "arm.L": fits.get("LeftHand", fits.get("LeftForeArm", fits["Hips"])),
        "arm.R": fits.get("RightHand", fits.get("RightForeArm", fits["Hips"])),
        "leg.L": fits.get("LeftFoot", fits.get("LeftLeg", fits["Hips"])),
        "leg.R": fits.get("RightFoot", fits.get("RightLeg", fits["Hips"])),
    }

    out: dict[int, dm.Mat] = {}
    for i, bone in enumerate(model.bones):
        m = fits.get(bone.name)
        if m is None:
            chain = CHAIN_OF_BONE.get(bone.name)
            if chain is None:
                for prefix, key in (("LeftHand", "arm.L"), ("RightHand", "arm.R"),
                                    ("Left", "leg.L"), ("Right", "leg.R"),
                                    ("Spine", "spine"), ("Neck", "spine"),
                                    ("Head", "spine"), ("Hips", "spine")):
                    if bone.name.startswith(prefix):
                        chain = key
                        break
            m = chain_anchor.get(chain, fits["Hips"]) if chain else fits["Hips"]
        out[i] = tuple(float(x) for x in np.asarray(m, dtype=np.float64).reshape(16))
    return out
