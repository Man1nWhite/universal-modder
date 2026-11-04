#!/usr/bin/env python3
"""Author Diesel .model files for the Miranda LAS outfit from the L4D2 source.

This is the model-authoring stage of tools/pd2-las. It converts the compiled
Source meshes (MDL/VVD/VTX inside l4d2_miranda_lawson_1.zip) into PAYDAY 2
Diesel .model units, skinned to the standard player skeleton as embedded in the
2B reference pack (2b.rar).

Conversion conventions (all mirrored from 2b.model, which is a known-good
in-game LAS outfit):

- geometry vertices/normals in world-at-bind space (z-up, cm, feet at z=0);
  transfer per influence bone: v' = sum w_j * v_src * inv(S_j) * W_map(j)
  with S = Source bind world (model units) and W = template bind world (cm).
- SkinBones.Rotations[i] = inv(bone world), root = Hips, Global = Hips world;
  drawable objects keep the template's own transform (= inv(Hips world)).
- BLENDINDICES0 = 4x u16 palette indices (0-based into the skin palette),
  BLENDWEIGHT0 = 3 floats. SKINNED_3WEIGHTS render template matches.
- UVs follow the payday2-model-tool GLTF import convention: internal
  (u, 1 - v_smd); the codec writes disk (u, -internal_v).
- triangle winding reversed from the Source (DirectX CW) to Diesel/GLTF CCW.

Usage (from the repo root):
  .venv/bin/python tools/pd2-las/build_models.py \
      --templates /path/to/dir/with/2b.model \
      --out build/pd2-las

The template directory must contain 2b.model and fps_2b.model (extracted from
2b.rar: 7z x 2b.rar). Previews are written to <out>/previews/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diesel_model as dm  # noqa: E402
from source_model import ModelData, load_model  # noqa: E402
from vpk import VpkArchive  # noqa: E402

REPO = HERE.parents[1]
SOURCE_ZIP = REPO / "models" / "l4d2_miranda_lawson_1.zip"

TPP_MDLS = (
    "models/survivors/survivor_producer.mdl",
    "models/survivors/survivor_producer.vvd",
    "models/survivors/survivor_producer.dx90.vtx",
)
FPS_MDLS = (
    "models/weapons/arms/v_arms_producer_new.mdl",
    "models/weapons/arms/v_arms_producer_new.vvd",
    "models/weapons/arms/v_arms_producer_new.dx90.vtx",
)

# output drawable -> source material names (Source material = texture basename)
TPP_GROUPS = {
    "body": {"drawables": ["g_body", "g_body_lod1"], "materials": ["miranda_body"],
             "out_materials": ["mtr_body"]},
    "head": {"drawables": ["g_head", "g_head_lod1"],
             "materials": ["miranda_face", "miranda_head", "miranda_hair",
                           "eyeball_l", "eyeball_r"],
             "out_materials": ["mtr_face", "mtr_head", "mtr_hair", "mtr_eyes"]},
    "shadow": {"drawables": ["s_body"],
               "materials": ["miranda_body", "miranda_face", "miranda_head",
                             "miranda_hair", "eyeball_l", "eyeball_r"],
               "out_materials": ["shadow_caster"]},
}
FPS_GROUPS = {
    "arms": {"drawables": ["g_body", "g_body_lod1", "g_head", "g_head_lod1"],
             "materials": None,  # all non-phy materials
             "out_materials": ["mtr_body"]},
    "shadow": {"drawables": ["s_body"], "materials": None,
               "out_materials": ["shadow_caster"]},
}

# source material -> slot in the head group's out_materials
HEAD_MAT_SLOT = {"miranda_face": "mtr_face", "miranda_head": "mtr_head",
                 "miranda_hair": "mtr_hair", "eyeball_l": "mtr_eyes",
                 "eyeball_r": "mtr_eyes"}

# 48-byte material defaults, copied verbatim from the 2B LAS materials
# (six little-endian qwords: 0, 0, (0.0, 1.0), 0, (0.0, 1.0), 0)
MAT_SKIPPED_DEFAULT = bytes.fromhex(
    "0000000000000000"
    "0000000000000000"
    "000000000000803f"
    "0000000000000000"
    "000000000000803f"
    "0000000000000000"
)

FACE_COLORS = {
    "mtr_body": (196, 158, 132), "mtr_face": (224, 184, 162),
    "mtr_head": (210, 168, 144), "mtr_hair": (86, 58, 40),
    "mtr_eyes": (70, 110, 160), "shadow_caster": (90, 90, 100),
}


# ------------------------------------------------------------ source side

# uniform scale clamp for target-registration fits (inch->cm is ~2.54; the
# clamp only guards against degenerate neighborhoods)
FIT_SCALE_CLAMP = (0.5, 6.0)

# a local fit whose rotation deviates more than this from the global
# registration is treated as a rogue frame (noisy 2-pair neighborhoods) and
# inherits the nearest ancestor's fit instead
FIT_MAX_DIVERGENCE_DEG = 30.0


def quat_to_mat(q) -> dm.Mat:
    """Source bone quat (x,y,z,w) -> row-vector rotation matrix."""
    x, y, z, w = q
    # column-vector rotation R (v' = R v), then transpose for row-vector use
    r00 = 1 - 2 * (y * y + z * z)
    r01 = 2 * (x * y - w * z)
    r02 = 2 * (x * z + w * y)
    r10 = 2 * (x * y + w * z)
    r11 = 1 - 2 * (x * x + z * z)
    r12 = 2 * (y * z - w * x)
    r20 = 2 * (x * z - w * y)
    r21 = 2 * (y * z + w * x)
    r22 = 1 - 2 * (x * x + y * y)
    return (r00, r10, r20, 0.0,
            r01, r11, r21, 0.0,
            r02, r12, r22, 0.0,
            0.0, 0.0, 0.0, 1.0)


def source_bone_worlds(model: ModelData) -> list[dm.Mat]:
    worlds: list[dm.Mat | None] = [None] * len(model.bones)

    def resolve(i: int) -> dm.Mat:
        if worlds[i] is not None:
            return worlds[i]
        b = model.bones[i]
        rot = quat_to_mat(b.quat)
        loc = (rot[0], rot[1], rot[2], rot[3],
               rot[4], rot[5], rot[6], rot[7],
               rot[8], rot[9], rot[10], rot[11],
               b.pos[0], b.pos[1], b.pos[2], 1.0)
        if b.parent < 0:
            worlds[i] = loc
        else:
            worlds[i] = dm.mat_mul(loc, resolve(b.parent))
        return worlds[i]

    return [resolve(i) for i in range(len(model.bones))]


def _umeyama_fit(src_pts, tgt_pts, weights):
    """Similarity (rotation + uniform scale + translation) fitting src->tgt.

    Returns a row-vector 4x4 (dm.Mat). Uses numpy SVD; proper rotation only.
    """
    import numpy as np
    P = np.asarray(src_pts, dtype=np.float64)
    Q = np.asarray(tgt_pts, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()
    cs = (P * w[:, None]).sum(axis=0)
    ct = (Q * w[:, None]).sum(axis=0)
    P0 = P - cs
    Q0 = Q - ct
    H = (P0 * w[:, None]).T @ Q0
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d if d != 0 else 1.0])
    R = Vt.T @ D @ U.T  # column convention: p' = R @ (p - cs) * s + ct
    var_p = (w[:, None] * P0 * P0).sum()
    s = float((S[0] + S[1] + d * S[2]) / var_p) if var_p > 1e-12 else 1.0
    s = min(FIT_SCALE_CLAMP[1], max(FIT_SCALE_CLAMP[0], s))
    # row-convention matrix: rows = R^T * s, translation ct - cs*M
    M = (s * R.T).tolist()
    m = (M[0][0], M[0][1], M[0][2], 0.0,
         M[1][0], M[1][1], M[1][2], 0.0,
         M[2][0], M[2][1], M[2][2], 0.0,
         0.0, 0.0, 0.0, 1.0)
    tmp = dm.mat_apply_point(m, tuple(cs))
    m = (m[0], m[1], m[2], m[3],
         m[4], m[5], m[6], m[7],
         m[8], m[9], m[10], m[11],
         ct[0] - tmp[0], ct[1] - tmp[1], ct[2] - tmp[2], 1.0)
    return m


def _unit_vec(v):
    import numpy as np

    arr = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(arr))
    return arr / n if n > 1e-12 else arr


def _rodrigues_arc(u, w):
    """Shortest-arc 3x3 rotation matrix mapping unit(u) -> unit(w) without axial twist."""
    import numpy as np

    u = _unit_vec(u)
    w = _unit_vec(w)
    c = float(np.dot(u, w))
    if c > 1.0 - 1e-9:
        return np.eye(3, dtype=np.float64)
    if c < -1.0 + 1e-9:
        axis = _unit_vec(
            np.cross(u, [1.0, 0.0, 0.0])
            if abs(float(u[0])) < 0.9
            else np.cross(u, [0.0, 1.0, 0.0])
        )
        return -np.eye(3, dtype=np.float64) + 2.0 * np.outer(axis, axis)
    v = np.cross(u, w)
    s = float(np.linalg.norm(v))
    k = np.array(
        [[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]],
        dtype=np.float64,
    )
    return np.eye(3, dtype=np.float64) + k + (k @ k) * ((1.0 - c) / (s * s))


def _make_sim_mat(scale: float, rot, p_src, p_tgt) -> dm.Mat:
    """Row-convention similarity matrix (v' = v*M + t) with column-vector rotation ``rot``."""
    import numpy as np

    s = min(FIT_SCALE_CLAMP[1], max(FIT_SCALE_CLAMP[0], float(scale)))
    rot = np.asarray(rot, dtype=np.float64)
    p_s = np.asarray(p_src, dtype=np.float64)
    p_t = np.asarray(p_tgt, dtype=np.float64)
    t = p_t - s * (rot @ p_s)
    m = s * rot
    return (
        float(m[0, 0]), float(m[1, 0]), float(m[2, 0]), 0.0,
        float(m[0, 1]), float(m[1, 1]), float(m[2, 1]), 0.0,
        float(m[0, 2]), float(m[1, 2]), float(m[2, 2]), 0.0,
        float(t[0]),    float(t[1]),    float(t[2]),    1.0,
    )


def _decompose_sim_mat(m: dm.Mat):
    """Extract (scale, col_vec_R, t) from a row-convention similarity matrix."""
    import numpy as np

    sc = math.sqrt(m[0] * m[0] + m[1] * m[1] + m[2] * m[2]) or 1.0
    rot = np.array(
        [
            [m[0] / sc, m[4] / sc, m[8] / sc],
            [m[1] / sc, m[5] / sc, m[9] / sc],
            [m[2] / sc, m[6] / sc, m[10] / sc],
        ],
        dtype=np.float64,
    )
    t = np.array([m[12], m[13], m[14]], dtype=np.float64)
    return sc, rot, t


def retarget_maps(model: ModelData, skel_map: dict, template: Template) -> dict[int, dm.Mat]:
    """Per source bone: similarity map source-world -> target-world.

    Anatomically partitioned similarity retargeting that avoids the three
    failure modes of unconstrained per-subtree Procrustes fits:
    1. Core torso + neck + head (`Hips`, `Spine`, `Spine1`, `Spine2`, `Neck`,
       `Head`) share one upright Umeyama fit over the torso/shoulder/hip core
       (excluding the bent forearms and 30 finger bones so the spine is not
       pitched backward, and keeping `Head`/face/hair in the same rigid frame).
    2. Each leg (`UpLeg`, `Leg`, `Foot`, `ToeBase`) shares a 4-joint Umeyama
       fit (avoiding rank-1 2-point SVD roll on `Foot -> ToeBase`).
    3. Each arm + hand (`Shoulder`, `Arm`, `ForeArm`, `Hand` + 15 fingers)
       uses chained shortest-arc (Rodrigues) segment alignment from the core
       frame with zero axial twist, and all 15 finger bones share their parent
       `Hand` similarity transform at forearm scale.
    """
    import numpy as np

    src_worlds = source_bone_worlds(model)
    src_pos = [np.array(w[12:15], dtype=np.float64) for w in src_worlds]

    direct_src: dict[str, list[int]] = {}
    primary_src: dict[str, int] = {}
    for i, bone in enumerate(model.bones):
        tname = skel_map["map"].get(bone.name)
        if tname is not None and tname in template.name_id:
            direct_src.setdefault(tname, []).append(i)
            if bone.name != "ValveBiped.Bip01_Spine4":
                primary_src.setdefault(tname, i)

    if not direct_src:
        return {}

    def src_centroid(tname: str):
        return np.mean([src_pos[i] for i in direct_src[tname]], axis=0)

    def tgt_pos(tname: str):
        w = template.worlds[template.name_id[tname]]
        return np.array(w[12:15], dtype=np.float64)

    core_candidates = (
        "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
        "LeftShoulder", "RightShoulder", "LeftUpLeg", "RightUpLeg",
    )
    core_present = [t for t in core_candidates if t in direct_src]
    if len(core_present) < 4:
        core_present = [
            t for t in (
                "Spine", "Spine1", "Spine2",
                "LeftShoulder", "RightShoulder", "LeftArm", "RightArm",
            )
            if t in direct_src
        ]
    if len(core_present) < 3:
        core_present = list(direct_src.keys())

    g_fit = _umeyama_fit(
        [tuple(src_centroid(t).tolist()) for t in core_present],
        [tuple(tgt_pos(t).tolist()) for t in core_present],
        [1.0] * len(core_present),
    )
    _s_core, r_core, _ = _decompose_sim_mat(g_fit)

    fit_for_target: dict[str, dm.Mat] = {}
    for tname in ("Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
                  "LeftShoulder", "RightShoulder"):
        if tname in direct_src:
            fit_for_target[tname] = g_fit

    # Legs: 4-joint Umeyama fit per leg so thigh/calf/foot/toe move coherently
    for side in ("Left", "Right"):
        leg_targets = (f"{side}UpLeg", f"{side}Leg", f"{side}Foot", f"{side}ToeBase")
        if all(t in primary_src for t in leg_targets):
            leg_fit = _umeyama_fit(
                [tuple(src_pos[primary_src[t]].tolist()) for t in leg_targets],
                [tuple(tgt_pos(t).tolist()) for t in leg_targets],
                [1.0] * len(leg_targets),
            )
            for t in leg_targets:
                fit_for_target[t] = leg_fit

    # Arms + Hands + Fingers: chained alignment with knuckle-fitted palm
    # and per-phalanx placement onto PD2's finger bone pivots
    for side in ("Left", "Right"):
        t_sh = f"{side}Shoulder"
        t_arm = f"{side}Arm"
        t_fore = f"{side}ForeArm"
        t_hand = f"{side}Hand"
        t_mid1 = f"{side}HandMiddle1"
        if not all(t in primary_src for t in (t_arm, t_fore, t_hand, t_mid1)):
            continue
        ps_a = src_pos[primary_src[t_arm]]
        ps_f = src_pos[primary_src[t_fore]]
        ps_h = src_pos[primary_src[t_hand]]

        pt_a = tgt_pos(t_arm)
        pt_f = tgt_pos(t_fore)
        pt_h = tgt_pos(t_hand)

        hand_landmarks = [
            (f"{side}HandIndex1", 1.0),
            (f"{side}HandMiddle1", 1.0),
            (f"{side}HandRing1", 1.0),
            (f"{side}HandPinky1", 1.0),
            (f"{side}HandThumb1", 0.8),
            (t_hand, 0.2),
        ]
        present_hl = [(t, w) for t, w in hand_landmarks if t in primary_src]
        if len(present_hl) >= 3:
            m_hand = _umeyama_fit(
                [tuple(src_pos[primary_src[t]].tolist()) for t, _ in present_hl],
                [tuple(tgt_pos(t).tolist()) for t, _ in present_hl],
                [w for _, w in present_hl],
            )
            _, r_hand, _ = _decompose_sim_mat(m_hand)
        else:
            ps_m = src_pos[primary_src[t_mid1]]
            pt_h_raw = tgt_pos(t_hand)
            pt_m = tgt_pos(t_mid1)
            r_arm_tmp = _rodrigues_arc(r_core @ (ps_f - ps_a), pt_f - pt_a) @ r_core
            r_fore_tmp = _rodrigues_arc(r_arm_tmp @ (ps_h - ps_f), pt_h_raw - pt_f) @ r_arm_tmp
            s_fore_tmp = float(np.linalg.norm(pt_h_raw - pt_f) / max(1e-9, np.linalg.norm(ps_h - ps_f)))
            r_hand = _rodrigues_arc(r_fore_tmp @ (ps_m - ps_h), pt_m - pt_h_raw) @ r_fore_tmp
            m_hand = _make_sim_mat(s_fore_tmp, r_hand, ps_h, pt_h_raw)

        fit_for_target[t_hand] = m_hand
        pt_wrist = np.array(dm.mat_apply_point(m_hand, tuple(ps_h.tolist())), dtype=np.float64)

        def _axial_mat(s_start: np.ndarray, s_end: np.ndarray,
                       t_start: np.ndarray, t_end: np.ndarray,
                       r_base: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            ds = s_end - s_start
            dt = t_end - t_start
            r_seg = _rodrigues_arc(r_base @ ds, dt) @ r_base
            len_dt = max(1e-9, float(np.linalg.norm(dt)))
            lam = len_dt / max(1e-9, float(np.linalg.norm(ds)))
            v = dt / len_dt
            s_seg = _s_core * np.eye(3, dtype=np.float64) + (lam - _s_core) * np.outer(v, v)
            m_seg = np.eye(4, dtype=np.float64)
            m_seg[:3, :3] = s_seg @ r_seg
            m_seg[:3, 3] = t_start - (m_seg[:3, :3] @ s_start)
            return m_seg, r_seg

        if "Hips" in direct_src:
            # Full-body third-person character: construct Shoulder, Arm, and
            # ForeArm bind operators via PD2's standing menu pose
            # M_menu = W_posed @ inv(W_bind):
            # 1. In the standing pose, Shoulder and Arm meet at a natural
            #    feminine shoulder width (+1.2 cm outward from L4D2's UpperArm
            #    head) so Spine2, Shoulder, and Arm agree at the shoulder
            #    without a bicep bulge or under-shoulder dent.
            # 2. The standing elbow is shifted 2.8 cm inward along the exact
            #    invariant hinge axis of inv(M_menu[Arm]) @ M_menu[ForeArm], so
            #    Arm and ForeArm meet with 0.000 cm gap in BOTH bind pose and
            #    standing pose while eliminating the outward elbow bow.
            # 3. Rank-1 axial scaling along each segment preserves 100% of the
            #    native radial arm thickness.
            sgn = -1.0 if side == "Left" else 1.0
            d_arm_bind = pt_f - pt_a
            d_fa_bind = pt_h - pt_f
            r_w_arm = _rodrigues_arc(d_arm_bind, np.array([sgn * 0.17, -0.05, -0.98], dtype=np.float64))
            r_w_fa_rel = _rodrigues_arc(r_w_arm @ d_fa_bind, np.array([sgn * 0.05, 0.25, -0.96], dtype=np.float64))
            r_w_fa = r_w_fa_rel @ r_w_arm

            pt_f_posed = pt_a + (r_w_arm @ d_arm_bind)
            m_arm_menu = np.eye(4, dtype=np.float64)
            m_arm_menu[:3, :3] = r_w_arm
            m_arm_menu[:3, 3] = pt_a - (r_w_arm @ pt_a)
            m_fa_menu = np.eye(4, dtype=np.float64)
            m_fa_menu[:3, :3] = r_w_fa
            m_fa_menu[:3, 3] = pt_f_posed - (r_w_fa @ pt_f)
            m_arm_menu_inv = np.linalg.inv(m_arm_menu)
            m_fa_menu_inv = np.linalg.inv(m_fa_menu)

            hinge_raw = np.array([
                r_w_fa_rel[2, 1] - r_w_fa_rel[1, 2],
                r_w_fa_rel[0, 2] - r_w_fa_rel[2, 0],
                r_w_fa_rel[1, 0] - r_w_fa_rel[0, 1],
            ], dtype=np.float64)
            ax_p = hinge_raw / max(1e-9, float(np.linalg.norm(hinge_raw)))
            if float(ax_p[0]) * (-sgn) < 0.0:
                ax_p = -ax_p

            ps_a_g = np.array(dm.mat_apply_point(g_fit, tuple(ps_a.tolist())), dtype=np.float64)
            pt_a_stand = ps_a_g + np.array([0.0, 0.0, -0.3], dtype=np.float64)
            pt_f_stand = pt_f_posed + 2.8 * ax_p
            pt_h_stand = (m_fa_menu @ np.append(pt_wrist, 1.0))[:3]

            if t_sh in primary_src:
                ps_sh = src_pos[primary_src[t_sh]]
                pt_sh_stand = np.array(dm.mat_apply_point(g_fit, tuple(ps_sh.tolist())), dtype=np.float64)
                m_sh_menu, _ = _axial_mat(ps_sh, ps_a, pt_sh_stand, pt_a_stand, r_core)
                fit_for_target[t_sh] = tuple(float(x) for x in m_sh_menu.T.reshape(16))

            m_arm_stand, r_arm_m = _axial_mat(ps_a, ps_f, pt_a_stand, pt_f_stand, r_core)
            m_fa_stand, _ = _axial_mat(ps_f, ps_h, pt_f_stand, pt_h_stand, r_arm_m)

            m_arm_bind = m_arm_menu_inv @ m_arm_stand
            m_fa_bind = m_fa_menu_inv @ m_fa_stand
            fit_for_target[t_arm] = tuple(float(x) for x in m_arm_bind.T.reshape(16))
            fit_for_target[t_fore] = tuple(float(x) for x in m_fa_bind.T.reshape(16))
        else:
            # First-person arms-only viewmodel: align directly to PD2's
            # viewmodel Arm -> ForeArm -> Wrist pivots with rank-1 axial scaling.
            if t_sh in primary_src:
                ps_sh = src_pos[primary_src[t_sh]]
                pt_sh = tgt_pos(t_sh)
                m_sh_bind, _ = _axial_mat(ps_sh, ps_a, pt_sh, pt_a, r_core)
                fit_for_target[t_sh] = tuple(float(x) for x in m_sh_bind.T.reshape(16))
            m_arm_bind, r_arm_b = _axial_mat(ps_a, ps_f, pt_a, pt_f, r_core)
            m_fa_bind, _ = _axial_mat(ps_f, ps_h, pt_f, pt_wrist, r_arm_b)
            fit_for_target[t_arm] = tuple(float(x) for x in m_arm_bind.T.reshape(16))
            fit_for_target[t_fore] = tuple(float(x) for x in m_fa_bind.T.reshape(16))

        s_min_f = 0.85 * _s_core
        s_max_f = 1.35 * _s_core
        for fname in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
            f1 = f"{side}Hand{fname}1"
            f2 = f"{side}Hand{fname}2"
            f3 = f"{side}Hand{fname}3"
            if not all(t in primary_src for t in (f1, f2, f3)):
                for t in (f1, f2, f3):
                    if t in direct_src:
                        fit_for_target[t] = m_hand
                continue
            s1 = src_pos[primary_src[f1]]
            s2 = src_pos[primary_src[f2]]
            s3 = src_pos[primary_src[f3]]
            tw1 = tgt_pos(f1)
            tw2 = tgt_pos(f2)
            tw3 = tgt_pos(f3)

            t1 = np.array(dm.mat_apply_point(m_hand, tuple(s1.tolist())), dtype=np.float64)
            r_f1 = _rodrigues_arc(r_hand @ (s2 - s1), tw2 - tw1) @ r_hand
            raw_s1 = float(np.linalg.norm(tw2 - tw1) / max(1e-9, np.linalg.norm(s2 - s1)))
            s_f1 = float(np.clip(raw_s1, s_min_f, s_max_f))
            m_f1 = _make_sim_mat(s_f1, r_f1, s1, t1)
            fit_for_target[f1] = m_f1

            t2 = np.array(dm.mat_apply_point(m_f1, tuple(s2.tolist())), dtype=np.float64)
            r_f2 = _rodrigues_arc(r_f1 @ (s3 - s2), tw3 - tw2) @ r_f1
            raw_s2 = float(np.linalg.norm(tw3 - tw2) / max(1e-9, np.linalg.norm(s3 - s2)))
            s_f2 = float(np.clip(raw_s2, s_min_f, s_max_f))
            m_f2 = _make_sim_mat(s_f2, r_f2, s2, t2)
            fit_for_target[f2] = m_f2

            t3 = np.array(dm.mat_apply_point(m_f2, tuple(s3.tolist())), dtype=np.float64)
            fit_for_target[f3] = _make_sim_mat(s_f2, r_f2, s3, t3)

    maps: dict[int, dm.Mat] = {}
    for i in range(len(model.bones)):
        tname = _map_source_bone(model, i, skel_map)
        if tname is None or tname not in template.name_id:
            continue
        maps[i] = fit_for_target.get(tname, g_fit)
    return maps


# ------------------------------------------------------------ template side

@dataclass
class Template:
    mf: dm.ModelFile
    names: dict[int, str]                 # hash -> name
    id_name: dict[int, str]               # section id -> object name
    id_obj: dict[int, dict]               # section id -> decoded object3d/model
    worlds: dict[int, dm.Mat]
    name_id: dict[str, int]               # canonical section id per name
    hips_id: int
    hips_world: dm.Mat
    drawables: dict[str, dict]            # name -> decoded v3 model_data
    drawable_skin: dict[str, dict]        # name -> decoded template skinbones


def _resolve_worlds(mf: dm.ModelFile) -> tuple[dict[int, dict], dict[int, dm.Mat]]:
    objs = {}
    for s in mf.sections:
        if s.type == dm.OBJECT3D:
            objs[s.id] = dm.decode_object3d(s.payload)
        elif s.type == dm.MODEL_DATA:
            objs[s.id] = dm.decode_model_data(s.payload)
    worlds: dict[int, dm.Mat] = {}
    pending = dict(objs)
    for _ in range(len(objs) + 1):
        progress = False
        for sid in list(pending):
            obj = pending[sid]
            loc = list(obj["matrix"])
            loc[12], loc[13], loc[14] = obj["pos"]
            loc = tuple(loc)
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
    return objs, worlds


def load_template(path: Path) -> Template:
    mf = dm.ModelFile.read_path(path)
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    names = {dm.hash64(n): n for n in hl["names"]}
    objs, worlds = _resolve_worlds(mf)
    id_name = {sid: names.get(o["name_hash"], f"#{o['name_hash']:016x}")
               for sid, o in objs.items()}
    name_id: dict[str, int] = {}
    for sid, n in id_name.items():
        name_id.setdefault(n, sid)

    drawables: dict[str, dict] = {}
    drawable_skin: dict[str, dict] = {}
    skins = {s.id: dm.decode_skinbones(s.payload) for s in mf.by_type(dm.SKINBONES)}
    for sid, o in objs.items():
        if o.get("version") == 3:
            drawables[id_name[sid]] = o
            drawable_skin[id_name[sid]] = skins.get(o["skinbones"], {})

    hips_id = name_id["Hips"]
    return Template(mf=mf, names=names, id_name=id_name, id_obj=objs,
                    worlds=worlds, name_id=name_id, hips_id=hips_id,
                    hips_world=worlds[hips_id], drawables=drawables,
                    drawable_skin=drawable_skin)


# ------------------------------------------------------------ transfer

@dataclass
class Group:
    """One geometry/topology/skinbones block."""
    name: str
    verts: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    uvs: list = field(default_factory=list)          # internal (u, 1-v)
    faces: list = field(default_factory=list)        # (a,b,c) global, CCW
    slices: list = field(default_factory=list)       # (src_mat, base_v, base_i, tris, nverts)
    palette: list[str] = field(default_factory=list)  # target bone names
    weights: list = field(default_factory=list)       # per vert [(pal_idx, w), ...]
    mat_slots: list[str] = field(default_factory=list)  # out material per slice


def _map_source_bone(model: ModelData, idx: int, skel_map: dict) -> str | None:
    """Resolve a source bone (or its nearest mapped ancestor) to a target name."""
    mapping = skel_map["map"]
    drop = skel_map.get("drop", {}).get("patterns", [])
    seen = set()
    while idx >= 0 and idx not in seen:
        seen.add(idx)
        name = model.bones[idx].name
        if name in mapping:
            return mapping[name]
        if any(name.startswith(p) or name == p for p in drop):
            idx = model.bones[idx].parent
            continue
        idx = model.bones[idx].parent
    return None


def transfer_group(model: ModelData, group_spec: dict, skel_map: dict,
                   template: Template, group_name: str,
                   fits: dict | None = None) -> Group:
    import numpy as np

    g = Group(name=group_name)
    wanted = group_spec.get("materials")

    # target-centric similarity retarget (see retarget_maps); callers with a
    # source rig this module's heuristics do not cover can pass their own
    per_src_T = retarget_maps(model, skel_map, template) if fits is None else fits

    target_for_src: dict[int, tuple[str, dm.Mat]] = {}
    t_mat_by_name: dict[str, dm.Mat] = {}
    for i, T in per_src_T.items():
        tname = _map_source_bone(model, i, skel_map)
        target_for_src[i] = (tname, T)
        if tname is not None and tname not in t_mat_by_name:
            t_mat_by_name[tname] = T

    T_col: dict[str, np.ndarray] = {
        tn: np.array(m, dtype=np.float64).reshape(4, 4).T
        for tn, m in t_mat_by_name.items()
    }
    T_inv: dict[str, np.ndarray] = {
        tn: np.linalg.inv(m) for tn, m in T_col.items()
    }

    used_bones: set[str] = set()
    # material -> slice plan: gather triangles per source material
    for mesh in model.meshes:
        if wanted is not None and mesh.material not in wanted:
            continue
        if wanted is None and mesh.material in ("phy",):
            continue
        tris = mesh.triangle_indices
        # local vertex order: first appearance in this slice
        remap: dict[int, int] = {}
        slice_verts: list[int] = []
        slice_faces: list[tuple[int, int, int]] = []
        for k in range(0, len(tris), 3):
            tri = tris[k:k + 3]
            # COLLADA-style (CCW, right-handed) -> Diesel/GLTF: swap b/c.
            # Loaders must hand us CCW like the COLLADA importer does; the
            # Skyrim reader reverses its NIF winding to match.
            a, b, c = tri[0], tri[2], tri[1]
            for vi in (a, b, c):
                if vi not in remap:
                    remap[vi] = len(slice_verts)
                    slice_verts.append(vi)
            slice_faces.append((remap[a], remap[b], remap[c]))
        if not slice_verts:
            continue

        base_v = len(g.verts)
        base_i = len(g.faces) * 3
        for vi in slice_verts:
            sv = model.vertices[vi]
            by_target: dict[str, float] = {}
            for bi, w in sv.weights:
                if bi in per_src_T and w > 1e-6:
                    bname = model.bones[bi].name
                    if bname == "hlp_l_shoulder" and "LeftShoulder" in t_mat_by_name and "LeftArm" in t_mat_by_name:
                        by_target["LeftShoulder"] = by_target.get("LeftShoulder", 0.0) + 0.65 * w
                        by_target["LeftArm"] = by_target.get("LeftArm", 0.0) + 0.35 * w
                    elif bname == "hlp_r_shoulder" and "RightShoulder" in t_mat_by_name and "RightArm" in t_mat_by_name:
                        by_target["RightShoulder"] = by_target.get("RightShoulder", 0.0) + 0.65 * w
                        by_target["RightArm"] = by_target.get("RightArm", 0.0) + 0.35 * w
                    else:
                        tname, _ = target_for_src[bi]
                        by_target[tname] = by_target.get(tname, 0.0) + w
            # --- shoulder overlap stay (jacket only) ---
            # The blazer armhole is an *overlap*, not a sewn seam. Under the
            # arms-down idle the Arm-weighted sleeve shoulder rotates away from
            # the torso-weighted armhole edge and the overlap opens into a hole
            # (backface-culled in game). Blend part of the upper-arm weight into
            # the clavicle at the shoulder so the sleeve top stays with the
            # torso and the overlap remains closed. Jacket only: the skin below
            # keeps its own weights. Smooth height falloff avoids a weight seam.
            if mesh.material in ("jacket", "jacket2"):
                sx, _sy, sz = sv.pos
                if 93.0 <= sz <= 113.0 and abs(sx) >= 6.0:
                    t = (sz - 93.0) / 20.0
                    fall = t * t * (3.0 - 2.0 * t)      # smoothstep 0..1
                    for arm, clav in (("LeftArm", "LeftShoulder"),
                                      ("RightArm", "RightShoulder")):
                        aw = by_target.get(arm, 0.0)
                        if aw > 1e-4:
                            move = aw * 0.45 * fall
                            by_target[arm] = aw - move
                            by_target[clav] = by_target.get(clav, 0.0) + move
            infl = [(tn, w) for tn, w in by_target.items() if w > 1e-6]
            infl.sort(key=lambda t: -t[1])
            infl = infl[:3]
            total = sum(w for _, w in infl) or 1.0
            infl = [(tn, w / total) for tn, w in infl]
            if not infl:
                # vertices weighted only to unmapped bones: stick to the
                # lowest mapped source bone (pelvis in practice)
                if not per_src_T:
                    raise SystemExit("no mapped source bones at all")
                first_tn = target_for_src[min(per_src_T)][0]
                infl = [(first_tn, 1.0)]
            for tn, _ in infl:
                used_bones.add(tn)
            p4 = np.array([sv.pos[0], sv.pos[1], sv.pos[2], 1.0], dtype=np.float64)
            n3 = np.array([sv.normal[0], sv.normal[1], sv.normal[2]], dtype=np.float64)
            if len(infl) == 1:
                tn0 = infl[0][0]
                M = T_col[tn0]
                M_inv3 = T_inv[tn0][:3, :3]
            else:
                # Harmonic (matrix-inverse) blend: v_bind = (sum w_k T_k^-1)^-1 v_src
                # so runtime linear-blend skinning (sum w_k T_k^-1) v_bind recovers
                # the exact unbent joint cross-section without elbow/shoulder pinch.
                M_inv = sum(w * T_inv[tn] for tn, w in infl)
                M = np.linalg.inv(M_inv)
                M_inv3 = M_inv[:3, :3]
            vb = M @ p4
            nb = M_inv3.T @ n3
            ln = float(np.linalg.norm(nb)) or 1.0
            g.verts.append((float(vb[0]), float(vb[1]), float(vb[2])))
            g.normals.append((float(nb[0] / ln), float(nb[1] / ln), float(nb[2] / ln)))
            g.uvs.append((sv.uv[0], 1.0 - sv.uv[1]))  # p2mt GLTF-import convention
            # palette indices assigned after palette is fixed; store bone names
            g.weights.append(infl)
        g.faces.extend((a + base_v, b + base_v, c + base_v) for a, b, c in slice_faces)
        g.slices.append((mesh.material, base_v, base_i, len(slice_faces),
                         len(slice_verts)))
        slot = group_spec.get("mat_slots", {}).get(mesh.material)
        if slot is None:
            slot = (HEAD_MAT_SLOT.get(mesh.material)
                    if group_spec.get("out_materials") != ["shadow_caster"]
                    else "shadow_caster")
        if slot is None:
            slot = group_spec["out_materials"][0]
        g.mat_slots.append(slot)

    # palette: template 53-order first (root-first starting with Hips), then any extras by name
    order_ref = []
    preferred_skin = template.drawable_skin.get("g_body", {})
    if preferred_skin.get("objects"):
        order_ref = [template.id_name.get(o, "") for o in preferred_skin["objects"]]
    else:
        for skin in template.drawable_skin.values():
            objs = skin.get("objects", [])
            if len(objs) > len(order_ref) or (
                len(objs) == len(order_ref) and objs and objs[0] == template.hips_id
            ):
                order_ref = [template.id_name.get(o, "") for o in objs]
    named = sorted(used_bones)
    ordered = [n for n in order_ref if n in used_bones]
    ordered += [n for n in named if n not in ordered]
    g.palette = ordered
    pal_index = {n: i for i, n in enumerate(ordered)}

    g.weights = [[(pal_index[n], w) for n, w in infl] for infl in g.weights]
    if group_name == "head":
        repair_skin_boundary_normals(g)
    breaks = orientation_breaks(g)
    agree = winding_agreement(g.verts, g.faces, g.normals)
    print(f"[{group_name}] orientation breaks: {breaks}, "
          f"normals agree with winding: {agree:.1%}")
    if agree < 0.9:
        raise SystemExit(
            f"[{group_name}] normals disagree with the winding ({agree:.1%} agree); "
            "the model would light inside-out"
        )
    return g


def _palette_order(template: Template, used: set[str]) -> list[str]:
    """Template 53-order first (root-first from Hips), then extras by name."""
    order_ref: list[str] = []
    preferred_skin = template.drawable_skin.get("g_body", {})
    if preferred_skin.get("objects"):
        order_ref = [template.id_name.get(o, "") for o in preferred_skin["objects"]]
    else:
        for skin in template.drawable_skin.values():
            objs = skin.get("objects", [])
            if len(objs) > len(order_ref) or (
                len(objs) == len(order_ref) and objs and objs[0] == template.hips_id
            ):
                order_ref = [template.id_name.get(o, "") for o in objs]
    ordered = [n for n in order_ref if n in used]
    return ordered + [n for n in sorted(used) if n not in ordered]


#: bones whose vertices make up a hand, for graft_pd2_hands
HAND_BONES = ("Hand", "Thumb", "Index", "Middle", "Ring", "Pinky")


def _is_hand_bone(name: str) -> bool:
    return any(part in name for part in HAND_BONES)


def graft_pd2_hands(src_path: Path, slot: str = "mtr_hands") -> Group:
    """Copy hand geometry and skin weights out of a PD2 heister model.

    Both this mod's model and the donor sit on the stock heister skeleton in
    its bind pose, so the vertices already land where the destination rig
    wants them — there is no retargeting to do, and a similarity fit would
    only introduce error. UVs are taken verbatim from the donor so the donor's
    own texture (taken with it) samples correctly.

    The Melodic 3BA body stops at the wrist, so without this the outfit ends in
    a sleeve cuff and the heister's hands are simply missing.
    """
    import numpy as np

    mf = dm.ModelFile.read_path(src_path)
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    names = {dm.hash64(n): n for n in hl["names"]}
    objs = {}
    for s in mf.sections:
        if s.type == dm.OBJECT3D:
            objs[s.id] = dm.decode_object3d(s.payload)
        elif s.type == dm.MODEL_DATA:
            objs[s.id] = dm.decode_model_data(s.payload)
    id_name = {sid: names.get(o["name_hash"], "") for sid, o in objs.items()}

    g = Group(name="hands")
    used: set[str] = set()
    # A donor ships the hand three times (`s_body`, `g_body_lod1`, `g_body`).
    # Grafting all of them stacks a coarse shell on top of the detailed one,
    # and because the LOD is not *inside* the full mesh it shows as a spray of
    # flat blades off the wrist. Only the highest-detail hand is grafted.
    candidates = []
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if not md.get("atoms"):
            continue
        gp0 = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        try:
            dm.decode_geometry(mf.by_id(gp0["geometry"]).payload)
            topo0 = dm.decode_topology(mf.by_id(gp0["topology"]).payload)
        except ValueError:
            continue
        name = id_name.get(s.id, "")
        if "lod" in name.lower():
            continue                       # a decimated copy of a fuller mesh
        candidates.append((len(topo0["indices"]) // 3, s))
    best = max((c[0] for c in candidates), default=0)
    keep = {s.id for tris, s in candidates if tris >= 0.25 * best}

    for s in mf.by_type(dm.MODEL_DATA):
        if s.id not in keep:
            continue
        md = dm.decode_model_data(s.payload)
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        try:
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        except ValueError:
            continue                       # collision node, not a mesh
        if not geo["blendindices"] or len(geo["uv0"]) != len(geo["verts"]):
            continue                       # no skinning or no UVs: not graftable
        pal = [id_name.get(i, "") for i in
               dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)["objects"]]
        V = np.array(geo["verts"], dtype=np.float64)

        # one dominant bone per vertex decides whether it is part of a hand
        is_hand = np.zeros(len(V), bool)
        for vi, (bi, bw) in enumerate(zip(geo["blendindices"], geo["blendweights"])):
            k = int(np.argmax(bw))
            if bi[k] < len(pal) and _is_hand_bone(pal[bi[k]]):
                is_hand[vi] = True
        if not is_hand.any():
            continue

        donor_normals = (list(geo["normals"])
                         if len(geo["normals"]) == len(V) else None)
        idx = topo["indices"]
        tris = []
        for t in range(0, len(idx) - 2, 3):
            a, b, c = idx[t], idx[t + 1], idx[t + 2]
            if is_hand[a] and is_hand[b] and is_hand[c]:
                tris.append((a, c, b))     # Diesel winding: swap b/c
        if not tris:
            continue

        remap: dict[int, int] = {}
        order: list[int] = []
        for tri in tris:
            for vi in tri:
                if vi not in remap:
                    remap[vi] = len(order)
                    order.append(vi)
        base_v = len(g.verts)
        base_i = len(g.faces) * 3        # captured *before* the tris are added
        for vi in order:
            x, y, z = V[vi]
            g.verts.append((float(x), float(y), float(z)))
            g.normals.append(donor_normals[vi] if donor_normals else (0.0, 0.0, 0.0))
            u, v = geo["uv0"][vi]
            # Group UVs are the *internal* (u, 1 - v) convention every other
            # slice in this mesh uses. Storing the donor's raw v here flipped
            # the hands into the wrong half of the atlas, where the donor's
            # texture is black bodysuit: the grafted hands rendered as dark
            # grey-brown mittens. One convention per geometry block.
            g.uvs.append((float(u), float(1.0 - v)))
            infl = []
            for bi, w in zip(geo["blendindices"][vi], geo["blendweights"][vi]):
                nm = pal[bi] if bi < len(pal) else ""
                if w > 1e-6 and _is_hand_bone(nm):
                    infl.append((nm, float(w)))
            infl = [t for t in sorted(infl, key=lambda t: -t[1])[:3] if t[1] > 0]
            total = sum(w for _, w in infl) or 1.0
            g.weights.append([(nm, w / total) for nm, w in infl])
            used.update(nm for nm, _ in infl)
        g.faces.extend(tuple(remap[i] + base_v for i in tri) for tri in tris)
        g.slices.append(("hands", base_v, base_i, len(tris), len(order)))
        g.mat_slots.append(slot)

    if not g.verts:
        raise SystemExit(f"no hand geometry found in {src_path}")

    # donors may ship no normals at all; accumulate from the winding instead
    if not any(any(c != 0.0 for c in n) for n in g.normals):
        acc = np.zeros((len(g.verts), 3), dtype=np.float64)
        P = np.array(g.verts, dtype=np.float64)
        for a, b, c in g.faces:
            n = np.cross(P[b] - P[a], P[c] - P[a])
            ln = float(np.linalg.norm(n))
            if ln > 0:
                acc[a] += n / ln
                acc[b] += n / ln
                acc[c] += n / ln
        ln = np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-9)
        g.normals = [tuple(map(float, row)) for row in acc / ln]

    g.palette = sorted(used)
    pal_index = {n: i for i, n in enumerate(g.palette)}
    g.weights = [[(pal_index[n], w) for n, w in infl] for infl in g.weights]
    return g


def append_group(base: Group, extra: Group, template: Template) -> None:
    """Merge ``extra`` into ``base`` as further slices on one drawable."""
    if not extra.verts:
        return
    # everything gets re-indexed against the union palette, in template order
    names_old = list(base.palette)
    named_weights = [[(names_old[i], w) for i, w in infl] for infl in base.weights]
    extra_weights = [[(extra.palette[i], w) for i, w in infl] for infl in extra.weights]
    used = {n for infl in named_weights for n, _ in infl}
    used |= {n for infl in extra_weights for n, _ in infl}

    offset = len(base.verts)
    # a slice carries *both* offsets: where its vertices start (bv) and where
    # its triangles start in the index stream (bi). Both have to be rebased, or
    # the render atom points at someone else's triangles -- the geometry is
    # silently not drawn and whatever lives at the stale offset is drawn with
    # the wrong material instead. Missing the index offset here cost us the
    # grafted hands: they sat in the model, unwatched by any atom.
    toffset = len(base.faces) * 3
    base.verts.extend(extra.verts)
    base.normals.extend(extra.normals)
    base.uvs.extend(extra.uvs)
    base.faces.extend(tuple(i + offset for i in f) for f in extra.faces)
    base.slices.extend((mat, bv + offset, bi + toffset, nt, nv)
                       for mat, bv, bi, nt, nv in extra.slices)
    base.mat_slots.extend(extra.mat_slots)

    base.palette = _palette_order(template, used)
    index = {n: i for i, n in enumerate(base.palette)}
    base.weights = [[(index[n], w) for n, w in infl]
                    for infl in named_weights + extra_weights]


def _ring_angles(ring, centre, axis):
    import numpy as np

    """Angle of every ring vertex around `axis`, plus the ring's in-plane basis."""
    axis = np.asarray(axis, dtype=np.float64)
    axis = axis / (np.linalg.norm(axis) or 1.0)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(helper, axis))) > 0.9:
        helper = np.array([0.0, 1.0, 0.0])
    e1 = np.cross(axis, helper)
    e1 /= np.linalg.norm(e1) or 1.0
    e2 = np.cross(axis, e1)
    rel = np.asarray(ring, dtype=np.float64) - centre
    return np.arctan2(rel @ e2, rel @ e1), e1, e2


def _ordered_ring(indices, g: Group, centre, axis):
    """Ring vertices sorted by angle round ``axis``, plus their 0..1 fractions.

    Both the stitch and the sleeve pull need the two rings in the *same*
    angular order: `boundary_loops` walks a loop in whatever direction its
    owner faces, so half the rings arrive reversed, and an unwrap of a
    reversed ring runs 0 -> -2pi (normalising by its end turns the whole
    mapping into noise).
    """
    import numpy as np

    angles, _e1, _e2 = _ring_angles([g.verts[i] for i in indices], centre, axis)
    order = np.argsort(angles)
    angles = angles[order]
    frac = (angles - angles[0]) / max(float(angles[-1] - angles[0]), 1e-9)
    return [indices[i] for i in order], frac


def _wrist_loops(faces, verts, side_sign, min_r=1.0, max_r=6.0, min_n=8,
                 min_x=30.0):
    """Boundary loops that look like a wrist opening on one side of the body."""
    import numpy as np

    out = []
    for loop in boundary_loops(faces):
        ring = loop[:-1] if len(loop) > 3 and loop[0] == loop[-1] else loop
        if len(ring) < min_n:
            continue
        pts = np.asarray([verts[i] for i in ring], dtype=np.float64)
        centre = pts.mean(axis=0)
        if abs(centre[0]) < min_x or np.sign(centre[0]) != side_sign:
            continue
        radius = float(np.linalg.norm(pts - centre, axis=1).mean())
        if not min_r <= radius <= max_r:
            continue
        out.append((ring, centre, radius))
    return out


def _face_slots(g: Group) -> list[str]:
    """Out material of every face, in face order."""
    out: list[str] = [""] * len(g.faces)
    for (_mat, _bv, base_i, tris, _nv), slot in zip(g.slices, g.mat_slots):
        for f in range(base_i // 3, min(base_i // 3 + tris, len(out))):
            out[f] = slot
    return out


def weld_wrist(g: Group, vert_range, face_range, radius: float = 7.0,
               slot: str = "mtr_body", hand_slot: str = "mtr_hands",
               pull: float = 1.0) -> dict:
    """Close the gap between a retargeted arm and a grafted PD2 hand.

    A grafted hand sits where PD2's `Hand` bone is, and it has to: weapons are
    parented to that bone, so moving the hand to suit the sleeve would move the
    gun. PD2's bind pose, though, has the palm hanging well forward of the
    forearm it belongs to, so the retargeted Skyrim sleeve ends a hand's width
    away from the hand it should cover — and the offset is *rigid*: both ends
    follow their own bones, so no animation ever closes it. The sleeve is what
    has to move.

    Two steps per opening: pull the sleeve's mouth onto the hand's (a taper up
    the cuff, so the join is a cone and not a tear), then stitch the two
    openings with a band of quads whose material is the mouth's own — a skin
    wrist closes with skin, a blazer cuff closes with the blazer.

    `vert_range`/`face_range` are the half-open ranges the graft occupies.
    """
    import numpy as np

    v_lo, v_hi = vert_range
    f_lo, f_hi = face_range
    hand_verts = set(range(v_lo, v_hi))
    hand_faces = g.faces[f_lo:f_hi]
    body_faces = [f for i, f in enumerate(g.faces) if not f_lo <= i < f_hi]

    report = {"pairs": [], "moved": 0, "triangles": 0}
    new_faces: list[tuple[int, int, int]] = []
    bands: list[tuple] = []                    # (slot, v0, i0, tris, nverts)

    for sign in (1.0, -1.0):
        body_rings = _wrist_loops(body_faces, g.verts, sign)
        # outermost opening first: the blazer cuff has to reach the hand, the
        # skin ring inside it then follows the same target
        body_rings.sort(key=lambda t: -t[2])
        hand_rings = []
        for loop in boundary_loops(hand_faces):
            ring = loop[:-1] if len(loop) > 3 and loop[0] == loop[-1] else loop
            pts = np.asarray([g.verts[i] for i in ring])
            c = pts.mean(axis=0)
            if np.sign(c[0]) != sign:
                continue
            hand_rings.append((ring, c, float(np.linalg.norm(pts - c, axis=1).mean())))
        if not body_rings or not hand_rings:
            continue

        # The shift is computed from the outermost opening and applied to the
        # whole neighbourhood *once*: every layer there (blazer, lace top, skin)
        # has to move by the same field, or the sleeve drags off the arm inside
        # it and the skin pokes through as a flap.
        mouth = body_rings[0]
        bring, bcentre, bradius = mouth
        hring, hcentre = _match_hand_ring(hand_rings, bcentre, bradius)
        if hring is None:
            continue
        axis = hcentre - bcentre
        if float(np.linalg.norm(axis)) < 1e-6:
            axis = np.array([0.0, 1.0, 0.0])
        core = np.asarray([g.verts[i] for i in bring]).mean(axis=0)

        bring, t_b = _ordered_ring(bring, g, core, axis)
        hring, t_h = _ordered_ring(hring, g, hcentre, axis)
        hand_pts = np.asarray([g.verts[i] for i in hring])
        target = np.stack([np.interp(t_b, t_h, hand_pts[:, k])
                           for k in range(3)], axis=1)
        ring_shift = (target - np.asarray([g.verts[i] for i in bring])) * pull
        mean_shift = ring_shift.mean(axis=0)
        to_hand = mean_shift / (np.linalg.norm(mean_shift) or 1.0)
        # Only the rigid part of the shift is applied. Warping the mouth onto
        # the hand's ring vertex-by-vertex needs a 76 -> 94 correspondence that
        # does not exist: the interpolated target wobbles round the circle and
        # turns a round cuff into a jagged star. The cuff keeps its own seam and
        # simply travels to the hand; the two openings are capped separately.
        for i, v in enumerate(g.verts):
            if i in hand_verts:
                continue
            p = np.asarray(v, dtype=np.float64)
            rel = p - core
            along = float(np.dot(rel, to_hand))          # + is towards the hand
            lateral = rel - along * to_hand
            # stay inside the sleeve's own tube: the falloff must not reach
            # round the arm into the torso or the other cuff
            if float(np.linalg.norm(lateral)) > 2.5 * bradius:
                continue
            if along < -2.5 or along > radius:
                continue
            w = (1.0 - max(along, 0.0) / radius) ** 2
            shift = w * mean_shift
            g.verts[i] = (v[0] + shift[0], v[1] + shift[1], v[2] + shift[2])
            report["moved"] += 1

        # Close the cuff with *skin*, sampled from the hand it closes onto.
        # Painting it with the mouth's own cloth is what a stitched seam would
        # do, but PD2 does not stitch these: a heister carries `g_body`
        # (clothes) and `g_arms` (a bare skin wrist) as separate models, and the
        # sleeve simply overlaps the arm. A skin cap reproduces what that looks
        # like from outside -- sleeve, a ring of wrist, then the hand -- and it
        # cannot go wrong on a garment whose inner layer is white lace, which is
        # what a cloth-coloured cap showed instead.
        for ring in [r for r, _c, _r in body_rings]:

            # `boundary_loops` returns loops in face order, which on a bent
            # cuff zig-zags round the opening; fanning that order connects
            # vertices that are not neighbours and throws a star of blades out
            # of the sleeve. Sort by angle first.
            rc = np.asarray([g.verts[i] for i in ring]).mean(axis=0)
            ring, _f = _ordered_ring(list(ring), g, rc, axis)
            v0 = len(g.verts)
            i0 = len(g.faces) * 3 + len(new_faces) * 3
            fan = _fan_cap(g, ring, body_faces, uv_ring=hring)
            new_faces.extend(fan)
            bands.append((hand_slot, v0, i0, len(fan), len(g.verts) - v0))
        # The hand's own opening is *not* capped. Its boundary is a single
        # loop only in the donor's topology: walked on the grafted hand it
        # jumps by up to 10 cm between neighbours, so any fan across it throws
        # long blades well outside the cuff. Nothing can see into it anyway —
        # the sleeve's own cap sits between the viewer and the hole.

        bcentre2 = np.asarray([g.verts[i] for i in bring]).mean(axis=0)
        report["pairs"].append({
            "side": "left" if sign > 0 else "right",
            "sleeve": int(len(bring)), "hand": int(len(hring)),
            "rings": len(body_rings),
            "gap_cm": round(float(np.linalg.norm(hcentre - bcentre2)), 2),
            "triangles": sum(b[3] for b in bands)})

    if new_faces:
        g.faces.extend(new_faces)
        for band_slot, bv, bi, tris, nverts in bands:
            g.slices.append(("skin", bv, bi, tris, nverts))
            g.mat_slots.append(band_slot)
        report["triangles"] = len(new_faces)
    return report


def _fan_cap(g: Group, ring, faces, depth: float = 1.0, uv_ring=None) -> list[tuple]:
    """Close one opening with a shallow cone pointing back into the surface.

    `cap_holes` fans to the centroid, which is fine for a flat hole but wrong
    for a cuff mouth that has just been dragged onto a hand: the opening is
    elliptical and sags, so a flat fan pokes out of the sleeve as a pale
    flange. The apex is instead pushed *inside* along the surface's own inside
    direction — measured from the faces that border the ring, not from the
    vertex normals, which on a garment edge can point either way — so the cone
    always ends up hidden behind the opening it closes.

    The apex carries the ring's average skin weights, so the cap deforms with
    the wrist instead of tearing off it.
    """
    import numpy as np

    pts = np.asarray([g.verts[i] for i in ring], dtype=np.float64)
    centre = pts.mean(axis=0)
    normal = np.zeros(3)
    for i in ring:
        normal += np.asarray(g.normals[i], dtype=np.float64)
    ln = float(np.linalg.norm(normal)) or 1.0
    normal /= ln

    # inside = towards the surface the ring belongs to
    inside = np.zeros(3)
    ring_set = set(ring)
    for f in faces:
        if len(ring_set.intersection(f)) >= 2:
            inside += (np.asarray([g.verts[i] for i in f],
                                  dtype=np.float64).mean(axis=0) - centre)
    if float(np.linalg.norm(inside)) < 1e-6:
        inside = -normal              # no bordering face: fall back on normals
    else:
        inside /= float(np.linalg.norm(inside))
    radius = float(np.linalg.norm(pts - centre, axis=1).mean())

    uv_ring = list(ring) if uv_ring is None else list(uv_ring)
    uv = np.asarray([g.uvs[i] for i in uv_ring], dtype=np.float64).mean(axis=0)
    weight_sum: dict[int, float] = {}
    for i in ring:
        for pal, w in g.weights[i]:
            weight_sum[pal] = weight_sum.get(pal, 0.0) + w / len(ring)
    total = sum(weight_sum.values()) or 1.0
    infl = sorted(((k, w / total) for k, w in weight_sum.items()),
                  key=lambda t: -t[1])[:3]
    renorm = sum(w for _, w in infl) or 1.0
    infl = [(k, w / renorm) for k, w in infl]

    apex = centre + inside * (radius * depth)
    new_index = len(g.verts)
    g.verts.append(tuple(float(x) for x in apex))
    g.normals.append(tuple(float(x) for x in normal))
    g.uvs.append((float(uv[0]), float(uv[1])))
    g.weights.append(infl)

    # wind the fan so it faces the way the ring's own surface does
    order = list(ring)
    a, b, c = (np.asarray(g.verts[i], dtype=np.float64)
               for i in (order[0], order[1], new_index))
    n = np.cross(b - a, c - a)
    want = sum(np.asarray(g.normals[i], dtype=np.float64) for i in order[:3])
    flip = float(np.dot(n, want)) < 0
    faces_out = []
    for k in range(len(order)):
        i, j = order[k], order[(k + 1) % len(order)]
        faces_out.append((j, i, new_index) if flip else (i, j, new_index))
    return faces_out


def _tuck_ring(g: Group, ring, centre, toward) -> None:
    """Shrink an inner opening and push it back, so it hides inside the cuff."""
    import numpy as np

    centre = np.asarray(centre, dtype=np.float64)
    toward = np.asarray(toward, dtype=np.float64)
    back = centre - toward
    back = back / (np.linalg.norm(back) or 1.0)
    for i in ring:
        p = np.asarray(g.verts[i], dtype=np.float64)
        g.verts[i] = tuple(float(x) for x in
                           centre + (p - centre) * 0.35 + back * 3.5)


def _match_hand_ring(hand_rings, bcentre, bradius):
    """The hand opening that belongs to this sleeve opening, or (None, None)."""
    import numpy as np

    cand = [(ring, c) for ring, c, r in hand_rings
            if len(ring) >= 8 and 0.35 * bradius <= r <= 2.5 * bradius]
    if not cand:
        return None, None
    ring, c = min(cand, key=lambda t: float(np.linalg.norm(t[1] - bcentre)))
    return ring, c


def _band_faces(bring, bang, hring, hang, g: Group, axis) -> list[tuple]:
    """Quads between two rings, matched by their angular fractions.

    Walking the two rings together in angle gives a band with no twist even
    when the counts differ (76 sleeve vertices against 94 hand ones here).
    Winding is chosen against the vertex normals, so the band cannot come out
    inside out.
    """
    import numpy as np

    if len(hang) > 1 and _band_cost(bang, hang) > _band_cost(bang, 1.0 - hang[::-1]):
        hring, hang = hring[::-1], 1.0 - hang[::-1]
    faces = []
    i = j = 0
    nb, nh = len(bring), len(hring)
    while i + 1 < nb or j + 1 < nh:
        next_b = bang[i + 1] if i + 1 < nb else float("inf")
        next_h = hang[j + 1] if j + 1 < nh else float("inf")
        if next_b <= next_h:
            faces.append((bring[i], bring[i + 1], hring[j % nh]))
            i += 1
        else:
            faces.append((bring[i % nb], hring[(j + 1) % nh], hring[j % nh]))
            j += 1
    out = []
    for a, b, c in faces:
        p, q, r = (np.asarray(g.verts[k], dtype=np.float64) for k in (a, b, c))
        n = np.cross(q - p, r - p)
        ln = float(np.linalg.norm(n))
        if ln < 1e-12:
            continue
        want = sum(np.asarray(g.normals[k], dtype=np.float64) for k in (a, b, c))
        out.append((a, b, c) if float(np.dot(n / ln, want)) >= 0 else (a, c, b))
    return out


def _band_cost(bang, hang) -> float:
    """How much a band would twist: the two seams resampled and compared.

    The rings rarely have the same vertex count (76 sleeve vertices against 88
    hand ones here), so the comparison happens on a common angular grid rather
    than vertex to vertex.
    """
    import numpy as np

    if len(hang) < 3 or bang[-1] < 1e-9 or hang[-1] < 1e-9:
        return 0.0
    grid = np.linspace(0.0, 1.0, 33)
    a = np.interp(grid, bang / bang[-1], np.linspace(0.0, 1.0, len(bang)))
    b = np.interp(grid, hang / hang[-1], np.linspace(0.0, 1.0, len(hang)))
    return float(np.sum(np.abs(a - b)))


def lower_collar(g: Group, mats=("jacket", "jacket2", "necklace"),
                 z0: float = 158.0, k: float = 0.35) -> int:
    """Compress the standing collar so it clears the jaw.

    The 3BA blazer and the lace top both stand up to ~169 cm, while the heister
    head hangs off a Head bone at 166.8 cm: the collar ends up around the chin
    and swallows the jaw in profile. Squashing everything above ``z0`` toward
    it is continuous at the boundary, so the garment cannot tear — it just
    reads as a collar that is folded down rather than popped.
    """
    touched = 0
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat not in mats:
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if z > z0:
                g.verts[i] = (x, y, z0 + (z - z0) * k)
                touched += 1
    return touched


def align_neck(g: Group, mats=("skin",), z_lo: float = 154.0,
               z_seam: float = 158.0, src_y: float = 9.5, dst_y: float = 7.6,
               r_shoulder: float = 6.5, r_seam: float = 2.1,
               r_neck: float = 9.0, r_fade: float = 3.0) -> int:
    """Recenter and taper the outfit's neck column onto the PD2 head-neck axis.

    Measured on the retargeted 3BA body, the skin neck is a wide tube whose axis
    sits at y≈9.5 cm and whose diagonally-cut opening rim centroids at y≈13.6 cm.
    The PD2 heister head (template ``g_head``) carries its own neck: a thin tube
    centered at y≈7.5 cm with radius ~2.5 cm at z158 and ~3.1 cm at z159, starting
    at z≈157. Folding the wide 3BA stub down without recentering it leaves a
    forward-offset skin "shelf" in front of the neck and a notch behind it.

    This pass blends every skin vertex above ``z_lo`` from its source neck axis
    (``src_y``) onto the PD2 axis (``dst_y``) while tapering its radial extent
    from the shoulder flare (``r_shoulder``) down to ``r_seam`` at ``z_seam`` and
    above. ``r_seam`` is deliberately *inside* the head neck radius so the tapered
    column, the folded stub and the neck cap all hide within the heister's own
    neck; the visible seam is where the two surfaces cross (~z157.6). The blend is
    a smoothstep that is exactly 0 at ``z_lo``, multiplied by a radial gate that
    is 1 inside ``r_neck`` of the source neck axis and fades to 0 by
    ``r_neck + r_fade``, so the outer shoulder / upper-arm skin stays exactly as
    the sleeve and underarm tucks shipped it and the mesh cannot tear.
    """
    touched = 0
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat not in mats:
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if z <= z_lo:
                continue
            t = min(1.0, (z - z_lo) / max(z_seam - z_lo, 1e-6))
            w = t * t * (3.0 - 2.0 * t)
            r_src = math.hypot(x, y - src_y)
            # radial gate: only the neck column and the trapezius that forms its
            # base; the outer shoulder / upper-arm skin is left exactly as the
            # sleeve / underarm tucks shipped it
            gate = min(1.0, max(0.0, 1.0 - (r_src - r_neck) / max(r_fade, 1e-6)))
            w *= gate * gate * (3.0 - 2.0 * gate)
            if w <= 0.0:
                continue
            cy = src_y + (dst_y - src_y) * w
            r_cap = r_shoulder + (r_seam - r_shoulder) * min(
                1.0, max(0.0, (z - (z_seam - 2.0)) / 2.0))
            r_new = r_src + (min(r_src, r_cap) - r_src) * w
            if r_src > 1e-6:
                nx = x * (r_new / r_src)
                ny = cy + (y - src_y) * (r_new / r_src)
            else:
                nx, ny = x, cy
            g.verts[i] = (nx, ny, z)
            touched += 1
    return touched


def trim_neck(g: Group, mats=("skin",), z0: float = 159.0, k: float = 0.05) -> int:
    """Fold the body's leftover neck stub down into the collar.

    Run *after* :func:`align_neck`, which has already recentered the neck column
    onto the PD2 head-neck axis and tapered it to inside the heister's own neck.
    What remains above the collar line is a thin duplicate of the head neck; the
    outfit ships no head (LAS keeps the heister's own), so squash it toward the
    collar line ``z0`` — continuous at the boundary so it cannot tear. Because the
    stub is now thinner than the head neck, the fold and the neck cap that
    :func:`cap_holes` adds sit hidden inside the heister's neck instead of
    jutting out in front of the chin.
    """
    touched = 0
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat not in mats:
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if z > z0:
                g.verts[i] = (x, y, z0 + (z - z0) * k)
                touched += 1
    return touched


def restore_bust(g: Group, mats=("skin", "jacket", "jacket2"),
                 spine_y: float = 5.3, factor: float = 1.32,
                 z_lo: float = 122.0, z_hi: float = 154.0,
                 x_full: float = 10.0, x_zero: float = 15.0) -> int:
    """Restore the source bust proportion lost to axial spine scaling.

    The retarget stretches the spine *axially* to reach PD2's longer torso, but
    the bust is *radial* and only receives the smaller global similarity scale,
    so it lands ~24% flatter than the 3BA source (measured bust/torso 0.485 vs
    0.640). Scale the front chest's forward protrusion back up by ``factor``,
    with a smooth height falloff so it blends into the waist and collar without
    tearing. Only the front (``y > spine_y``) moves; the back is kept, and the
    displacement is proportional to how far forward a vertex already sits, so
    the bust peaks gain the most.

    A *lateral* falloff (full for ``|x| <= x_full``, fading to zero by
    ``|x| = x_zero``) confines the push to the centre bust. Without it the whole
    front width — including the chest panel beside the sleeve — is pulled
    forward, which opens a visible gap at the underarm where the jacket's front
    meets the sleeve (the bust sits at |x| < 12, the underarm seam at ~12–16).
    """
    touched = 0
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat not in mats:
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if y <= spine_y or not (z_lo <= z <= z_hi):
                continue
            t = (z - z_lo) / (z_hi - z_lo)
            # smoothstep ramp over the first/last quarter, full in the middle
            if t < 0.25:
                u = t / 0.25
            elif t > 0.75:
                u = (1.0 - t) / 0.25
            else:
                u = 1.0
            fall = u * u * (3.0 - 2.0 * u)
            # lateral smoothstep: keep the underarm/sleeve seam in place
            ux = (x_zero - abs(x)) / (x_zero - x_full)
            if ux <= 0.0:
                continue
            ux = min(1.0, ux)
            fall *= ux * ux * (3.0 - 2.0 * ux)
            dy = (factor - 1.0) * (y - spine_y) * fall
            g.verts[i] = (x, y + dy, z)
            touched += 1
    return touched


def tuck_underarm_skin(g: Group, mats=("skin",), amount: float = 0.7,
                       near: float = 1.6, z_lo: float = 125.0, z_hi: float = 154.0,
                       x_min: float = 11.0) -> int:
    """Tuck the arm/underarm skin behind the blazer so it stops poking through.

    The blazer armhole is an *overlap* construction, not a sewn seam, and after
    the retarget body skin renders in front of the jacket at the underarm AND down
    the upper-arm sleeve (in-game white patches; a skin=green render confirms they
    are ``mtr_body``, not the shirt). Welding the jacket's overlap edges shut
    distorts the sleeve (see MODLOG dead end), so instead move only the *skin*: any
    skin vertex in the band within ``near`` cm of the jacket is pushed inward along
    its own normal by up to ``amount`` cm, with a smooth proximity falloff (full at
    the jacket, zero at ``near``). The jacket is untouched and the tuck is confined
    to the hidden arm under the sleeve. ``z_lo`` reaches down over the upper-arm
    sleeve (the armpit-only band left the sleeve poke-through untouched).

    This removes the bulk of the poke-through. A thin residue remains that is a
    genuine *gap* in the jacket's overlap (skin behind it), which no skin tuck
    can close; pushing harder or along the jacket normal instead distorts the
    skin and worsens it (both measured, see MODLOG).
    """
    import numpy as np
    jverts = []
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat not in ("jacket", "jacket2"):
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if z_lo <= z <= z_hi and abs(x) >= x_min:
                jverts.append((x, y, z))
    if not jverts:
        return 0
    jv = np.asarray(jverts, dtype=np.float64)
    touched = 0
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat not in mats:
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if not (z_lo <= z <= z_hi and abs(x) >= x_min):
                continue
            d = float(np.linalg.norm(jv - np.array([x, y, z]), axis=1).min())
            if d >= near:
                continue
            t = 1.0 - d / near
            fall = t * t * (3.0 - 2.0 * t)
            nx, ny, nz = g.normals[i]
            push = amount * fall
            g.verts[i] = (x - nx * push, y - ny * push, z - nz * push)
            touched += 1
    return touched


def tuck_shirt_sleeves(g: Group, amount: float = 1.6, near: float = 3.5,
                       z_lo: float = 116.0, z_hi: float = 138.0,
                       x_min: float = 20.0) -> int:
    """Tuck the white shirt's sleeves (``jacket2``) behind the blazer's sleeves.

    The shirt sleeves are 100 % arm-weighted and sit *below* the shoulder-stay
    band, so under the in-game arms-down / elbow-bent pose they poke through the
    blazer sleeve as white patches on the upper arm (confirmed in-game; the rigid
    offline arm rotation does not reproduce the elbow bend). Push them inward
    along their own normal — toward the arm — where they lie within ``near`` cm of
    the blazer, with a smooth proximity falloff. The blazer is untouched and the
    shirt sleeve is hidden under it anyway, so this only removes the poke-through.
    Confined to the upper-arm band (``x_min`` keeps the visible collar/lapel out).
    """
    import numpy as np
    jverts = []
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat != "jacket":
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if z_lo <= z <= z_hi and abs(x) >= x_min:
                jverts.append((x, y, z))
    if not jverts:
        return 0
    jv = np.asarray(jverts, dtype=np.float64)
    touched = 0
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat != "jacket2":
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if not (z_lo <= z <= z_hi and abs(x) >= x_min):
                continue
            d = float(np.linalg.norm(jv - np.array([x, y, z]), axis=1).min())
            if d >= near:
                continue
            t = 1.0 - d / near
            fall = t * t * (3.0 - 2.0 * t)
            nx, ny, nz = g.normals[i]
            push = amount * fall
            g.verts[i] = (x - nx * push, y - ny * push, z - nz * push)
            touched += 1
    return touched


def tuck_shirt_cuffs(g: Group, amount: float = 6.0, z_lo: float = 124.0,
                     z_hi: float = 128.0, x_min: float = 30.0) -> int:
    """Retract the white shirt's wrist cuffs (``jacket2``) up into the sleeve.

    The radial ``tuck_shirt_sleeves`` pass hides the shirt along the upper arm but
    not at the wrist: the cuff is a ring of 100 %-``ForeArm``-weighted verts sitting
    right at the sleeve *opening* (z~125), so it still shows as a white ring between
    the blazer cuff and the game glove (confirmed in-game). Pushing it inward does
    not help because there is no blazer beyond the opening to hide behind — it has
    to slide *up the forearm*, into the sleeve. Move the cuff verts along the
    wrist->elbow axis (measured from the rig: [+-0.288, -0.874, 0.392]) with a
    smooth height falloff (full at the cuff edge, zero by ``z_hi``). The blazer and
    the visible collar/lapel are untouched; the retracted cuff hides under the
    blazer sleeve. This removes the white ring without authoring any hand geometry.
    """
    import numpy as np
    # Forearm axis (wrist -> elbow) measured from the rig, per side. Retracting
    # along it slides the cuff up the sleeve; projecting onto it and pulling the
    # vert toward the axis tucks it inside the blazer tube (otherwise it stays on
    # the tube's edge and still peeks out of the opening).
    axes = {
        -1.0: (np.array([-45.99, 18.70, 124.47]), np.array([-39.50, -0.99, 133.29])),
        1.0: (np.array([45.99, 18.70, 124.47]), np.array([39.50, -0.99, 133.29])),
    }
    inward = 1.6      # cm pulled toward the forearm axis
    touched = 0
    span = max(z_hi - z_lo, 1e-6)
    for mat, base_v, _bi, _nt, nverts in g.slices:
        if mat != "jacket2":
            continue
        for i in range(base_v, base_v + nverts):
            x, y, z = g.verts[i]
            if abs(x) < x_min or not (z_lo <= z <= z_hi):
                continue
            t = (z_hi - z) / span
            t = max(0.0, min(1.0, t))
            fall = t * t * (3.0 - 2.0 * t)
            sx = -1.0 if x < 0 else 1.0
            W, E = axes[sx]
            D = E - W
            D = D / np.linalg.norm(D)
            p = np.array([x, y, z])
            # slide up the forearm (toward the elbow) ...
            push = amount * fall
            p = p + D * push
            # ... then pull toward the forearm axis so it sits inside the sleeve
            tt = float(np.dot(p - W, D))
            closest = W + D * tt
            radial = closest - p
            rn = float(np.linalg.norm(radial))
            if rn > 1e-6:
                p = p + radial / rn * min(inward * fall, rn)
            g.verts[i] = (float(p[0]), float(p[1]), float(p[2]))
            touched += 1
    return touched


def repair_skin_boundary_normals(g: Group) -> None:
    """Repair corrupted boundary normals along the face/neck seam and mouth corners,
    and recenter eyeball planar UVs on the visible eyelid opening (palpebral fissure).

    In the ME2/L4D2 source mesh, 7 right-cheek/temple boundary vertices on
    ``miranda_face`` (and their 4 matching twins on ``miranda_head`` neck skin)
    plus 3 mouth-corner vertices have normals corrupted by adjacent hair cards
    or mouthbag geometry (dot with true skin surface normal = 0.017..0.540),
    which produces a bright vertical shading streak on the right cheek in-game.
    """
    import numpy as np

    if not g.verts or not g.faces:
        return
    p = np.asarray(g.verts, dtype=np.float64)
    n = np.asarray(g.normals, dtype=np.float64)
    uv = np.asarray(g.uvs, dtype=np.float64)
    uv_img = np.column_stack([uv[:, 0], 1.0 - uv[:, 1]])
    skin_vert_mask = np.zeros(len(p), dtype=bool)
    skin_tris: list[tuple[int, int, int]] = []
    for mat_name, base_v, base_i, tri_count, slice_len in g.slices:
        if mat_name == "miranda_face":
            skin_vert_mask[base_v : base_v + slice_len] = True
            skin_tris.extend(g.faces[base_i // 3 : base_i // 3 + tri_count])
        elif mat_name == "miranda_head":
            sub_uv = uv_img[base_v : base_v + slice_len]
            sub_tris = [
                (a - base_v, b - base_v, c - base_v)
                for a, b, c in g.faces[base_i // 3 : base_i // 3 + tri_count]
            ]
            rounded_uv = np.round(sub_uv * 1000.0).astype(np.int64)
            _, inv_uv = np.unique(rounded_uv, axis=0, return_inverse=True)
            parent = list(range(int(inv_uv.max()) + 1))

            def find_uv(x: int) -> int:
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for a, b, c in sub_tris:
                ra, rb, rc = find_uv(int(inv_uv[a])), find_uv(int(inv_uv[b])), find_uv(int(inv_uv[c]))
                parent[rb] = ra
                parent[rc] = ra
            roots = np.array([find_uv(int(inv_uv[i])) for i in range(len(sub_uv))])
            seed_mask = (sub_uv[:, 0] < 0.45) & (sub_uv[:, 1] > 0.85)
            seed_roots = set(roots[seed_mask].tolist())
            is_ns = np.isin(roots, list(seed_roots))
            for f in g.faces[base_i // 3 : base_i // 3 + tri_count]:
                a, b, c = f
                if is_ns[a - base_v] and is_ns[b - base_v] and is_ns[c - base_v]:
                    skin_vert_mask[a] = skin_vert_mask[b] = skin_vert_mask[c] = True
                    skin_tris.append(f)
        elif mat_name == "miranda_hair":
            # Tuck the 33 sub-millimeter (1.5 mm) flyaway wire strips inside the
            # solid cranial volume so they do not rasterize as 1-pixel jagged
            # black wires across the right eye/cheek or floating in front of the
            # forehead under PAYDAY 2's opaque character shader, while preserving
            # vertex/triangle counts, UVs, and edge orientation.
            center = np.array([0.0, 6.0, 175.0], dtype=np.float64)
            for k in range(slice_len):
                vi = base_v + k
                pt = center + 0.20 * (p[vi] - center)
                p[vi] = pt
                g.verts[vi] = (float(pt[0]), float(pt[1]), float(pt[2]))
        elif mat_name in ("eyeball_r", "eyeball_l"):
            # Center eyeball planar UVs on the visible eyelid opening (palpebral fissure)
            # and soften horizontal/vertical normal tilt across the recessed 1.5cm eyeball sphere.
            sub_p = p[base_v : base_v + slice_len]
            if len(sub_p) > 0:
                cx_bbox = 0.5 * (float(sub_p[:, 0].min()) + float(sub_p[:, 0].max()))
                cz_bbox = 0.5 * (float(sub_p[:, 2].min()) + float(sub_p[:, 2].max()))
                rx = 0.5 * (float(sub_p[:, 0].max()) - float(sub_p[:, 0].min())) or 1.0
                sign = -1.0 if cx_bbox < 0.0 else 1.0
                dx_frac = 0.08 if sign > 0.0 else 0.13
                cx = cx_bbox + sign * dx_frac * rx
                cz = cz_bbox - 0.125 * rx
                scale = 0.45 / rx
                for k in range(slice_len):
                    vi = base_v + k
                    u_new = min(0.98, max(0.02, 0.5 - scale * (float(p[vi, 0]) - cx)))
                    v_img_new = min(0.98, max(0.02, 0.5 - scale * (float(p[vi, 2]) - cz)))
                    g.uvs[vi] = (float(u_new), float(1.0 - v_img_new))
                    nx, ny, nz = g.normals[vi]
                    nx_s = nx * 0.35
                    nz_s = nz * 0.35
                    ln = (nx_s * nx_s + ny * ny + nz_s * nz_s) ** 0.5 or 1.0
                    g.normals[vi] = (float(nx_s / ln), float(ny / ln), float(nz_s / ln))
    if not skin_tris:
        return
    t = np.asarray(skin_tris, dtype=np.int32)
    v0, v1, v2 = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    rounded = np.round(p * 100.0).astype(np.int64)
    _, inv = np.unique(rounded, axis=0, return_inverse=True)
    gn_u = np.zeros((inv.max() + 1, 3), dtype=np.float64)
    for k in range(3):
        np.add.at(gn_u, inv[t[:, k]], fn)
    gn_u /= np.maximum(np.linalg.norm(gn_u, axis=1, keepdims=True), 1e-8)
    gn = gn_u[inv]
    if float(np.sum(n[skin_vert_mask] * gn[skin_vert_mask], axis=1).mean()) < 0.0:
        gn = -gn
    dots = np.sum(n * gn, axis=1)
    bad = skin_vert_mask & (dots < 0.75)
    for vi in np.nonzero(bad)[0]:
        n[vi] = gn[vi]
        g.normals[int(vi)] = (float(gn[vi, 0]), float(gn[vi, 1]), float(gn[vi, 2]))
    # Weld normals across coincident skin seam vertices (miranda_face <-> miranda_head neck skin)
    by_pos: dict[tuple[int, int, int], list[int]] = {}
    for vi in np.nonzero(skin_vert_mask)[0]:
        k = (int(round(p[vi, 0] * 100.0)), int(round(p[vi, 1] * 100.0)), int(round(p[vi, 2] * 100.0)))
        by_pos.setdefault(k, []).append(int(vi))
    for v_list in by_pos.values():
        if len(v_list) > 1:
            avg_n = n[v_list].mean(axis=0)
            ln = float(np.linalg.norm(avg_n)) or 1.0
            nt = (float(avg_n[0] / ln), float(avg_n[1] / ln), float(avg_n[2] / ln))
            for vi in v_list:
                g.normals[vi] = nt
    # Tilt inner nostril cavity vertex normals downward/backward so frontal/overhead
    # lobby lights in PAYDAY 2 do not produce bright diffuse/specular spots inside the nostrils.
    for mat_name, base_v, _base_i, _tri_count, slice_len in g.slices:
        if mat_name == "miranda_face":
            sub_uv = uv_img[base_v : base_v + slice_len]
            d_nost = np.minimum(
                np.hypot((sub_uv[:, 0] - 0.454) / 0.022, (sub_uv[:, 1] - 0.472) / 0.026),
                np.hypot((sub_uv[:, 0] - 0.559) / 0.022, (sub_uv[:, 1] - 0.472) / 0.026),
            )
            n_shadow = np.array([0.0, -0.55, -0.83516465], dtype=np.float64)
            for k in np.nonzero(d_nost < 1.0)[0]:
                vi = int(base_v + k)
                w_t = float(np.clip(1.0 - d_nost[k], 0.0, 1.0)) * 0.90
                cur_n = np.asarray(g.normals[vi], dtype=np.float64)
                blended_n = cur_n * (1.0 - w_t) + n_shadow * w_t
                ln = float(np.linalg.norm(blended_n)) or 1.0
                g.normals[vi] = (
                    float(blended_n[0] / ln),
                    float(blended_n[1] / ln),
                    float(blended_n[2] / ln),
                )


def boundary_loops(faces) -> list[list[int]]:
    """Directed loops of edges used by exactly one face, largest first.

    Direction matters: the cap that closes a loop has to traverse each edge the
    opposite way its single owner does, or the cap is inside-out relative to the
    surface around it. Each loop repeats its first index at the end.
    """
    counts: dict[tuple[int, int], int] = {}
    directed: dict[tuple[int, int], int] = {}
    for a, b, c in faces:
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            counts[key] = counts.get(key, 0) + 1
            directed[(x, y)] = directed.get((x, y), 0) + 1
    boundary = [(x, y) for (x, y) in directed
                if counts[(x, y) if x < y else (y, x)] == 1]
    if not boundary:
        return []
    nxt: dict[int, list[int]] = {}
    for x, y in boundary:
        nxt.setdefault(x, []).append(y)
    seen: set[tuple[int, int]] = set()
    loops: list[list[int]] = []
    for x, y in boundary:
        if (x, y) in seen:
            continue
        loop = [x]
        cur = (x, y)
        while cur not in seen:
            seen.add(cur)
            loop.append(cur[1])
            candidates = [v for v in nxt.get(cur[1], []) if (cur[1], v) not in seen]
            if not candidates:
                break
            cur = (cur[1], candidates[0])
        if len(loop) >= 4 and loop[0] == loop[-1]:
            loops.append(loop)
    loops.sort(key=len, reverse=True)
    return loops


def cap_holes(g: Group, min_z: float, slot: str,
              source_material: str = "skin", allowed: set[int] | None = None,
              max_span: float = 14.0) -> int:
    """Close boundary loops of the group that lie entirely above `min_z`.

    The 3BA body is authored to wear a *separate* Skyrim head, so it ends in an
    open collar. Without a head the player sees the inside of her own torso
    through it, and the shadow mesh is not closed either. Each loop above
    `min_z` gets a fan to its centroid, with the centroid weighted like the loop
    it closes so the cap deforms with the neck instead of tearing off.
    Returns the number of triangles added, and registers them as their own
    render atom so the engine actually draws the cap.
    """
    import numpy as np

    if not g.faces:
        return 0
    p = np.asarray(g.verts, dtype=np.float64)
    z = p[:, 2]
    base_v = len(g.verts)
    base_i = len(g.faces) * 3
    added = 0
    for loop in boundary_loops(g.faces):
        idx = [i for i in loop if i < len(g.verts)]
        if len(idx) < 3:
            continue
        if float(z[idx].min()) < min_z:
            continue
        if allowed is not None and any(i not in allowed for i in idx):
            continue
        # a seam between two UV shells is a boundary loop too; only the real
        # opening is small and roundish
        span = float(np.linalg.norm(p[idx].max(axis=0) - p[idx].min(axis=0)))
        if span > max_span:
            continue
        ring = idx[:-1] if len(idx) > 3 and idx[0] == idx[-1] else idx
        if len(ring) < 3:
            continue
        # centroid vertex, weighted and normalised like its neighbours
        centre = np.array([g.verts[i] for i in ring], dtype=np.float64).mean(axis=0)
        normal = np.zeros(3)
        for i in ring:
            normal += np.asarray(g.normals[i], dtype=np.float64)
        length = float(np.linalg.norm(normal)) or 1.0
        normal /= length
        weight_sum: dict[int, float] = {}
        for i in ring:
            for pal, w in g.weights[i]:
                weight_sum[pal] = weight_sum.get(pal, 0.0) + w / len(ring)
        total = sum(weight_sum.values()) or 1.0
        infl = sorted(((p, w / total) for p, w in weight_sum.items()),
                      key=lambda t: -t[1])[:3]
        renorm = sum(w for _, w in infl) or 1.0
        infl = [(p, w / renorm) for p, w in infl]
        uv = np.array([g.uvs[i] for i in ring], dtype=np.float64).mean(axis=0)
        new_index = len(g.verts)
        g.verts.append(tuple(float(x) for x in centre))
        g.normals.append(tuple(float(x) for x in normal))
        g.uvs.append((float(uv[0]), float(uv[1])))
        g.weights.append(infl)
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]
            # reversed relative to the boundary walk so the fan faces outward,
            # matching the winding of the surface it closes
            g.faces.append((b, a, new_index))
            added += 1
    if added:
        g.slices.append((source_material, base_v, base_i, added,
                         len(g.verts) - base_v))
        g.mat_slots.append(slot)
    return added


def winding_agreement(verts, faces, normals) -> float:
    """Fraction of faces whose vertex normals agree with the winding.

    The companion check to `orientation_breaks`: that one asks "are the faces
    consistently wound", this one asks "do the normals point the same way the
    winding says they do". A shipped reference model scores ~0.99; a model that
    is uniformly inside-out scores ~0.01 and renders lit from behind.
    """
    import numpy as np

    v = np.asarray(verts, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    n = np.asarray(normals, dtype=np.float64)
    if not len(f):
        return 1.0
    face = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    face /= np.maximum(np.linalg.norm(face, axis=1, keepdims=True), 1e-12)
    vn = n[f[:, 0]] + n[f[:, 1]] + n[f[:, 2]]
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    return float(((face * vn).sum(axis=1) > 0).mean())


def orientation_breaks(g: Group) -> int:
    """Count shared edges whose two faces traverse it in the same direction.

    On a welded mesh this is the exact hole test: an orientation break is a
    triangle wound inside-out relative to its neighbours, which the engine
    back-face-culls into a hole. (A vertex-normal disagreement is NOT that:
    skinned meshes blend normals at joints and can shade slightly off while
    the winding stays correct — flipping those creates real breaks. Corner-
    split meshes such as the ME2 source have no shared edges and must use
    the vertex-normal heuristic instead; see
    tools/pd2-port/check_mesh_geometry.py.)
    """
    edge_dir: dict[tuple[int, int], list[int]] = {}
    for a, b, c in g.faces:
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            edge_dir.setdefault(key, []).append(1 if x < y else -1)
    return sum(1 for dirs in edge_dir.values()
               if len(dirs) == 2 and dirs[0] == dirs[1])


# ------------------------------------------------------------ authoring

def author_group_sections(g: Group, template: Template, ids: list[int]) -> list[dm.Section]:
    """Build [skinbones, geometry, topology, passthroughGP, topologyIP, materials, matgroup]."""
    skin_id, geo_id, topo_id, gp_id, ip_id = ids[0], ids[1], ids[2], ids[3], ids[4]
    out_mats = sorted(set(g.mat_slots))
    mat_ids = ids[5:5 + len(out_mats)]

    # -- geometry --
    pal_idx = []
    pal_w = []
    for infl in g.weights:
        idxs = [i for i, _ in infl] + [0] * (4 - len(infl))
        ws = [w for _, w in infl]
        ws = (ws + [0.0, 0.0, 0.0])[:3]
        # renormalize (3-weight template)
        s = sum(ws) or 1.0
        pal_idx.append(tuple(idxs[:4]))
        pal_w.append((ws[0] / s, ws[1] / s, ws[2] / s))

    du, dv = dm.compute_uv_directions(g.verts, g.uvs, g.faces)
    if len(g.normals) == len(g.verts) and len(g.verts) > 0:
        import numpy as np

        n_arr = np.asarray(g.normals, dtype=np.float64)
        u_arr = np.asarray(du, dtype=np.float64)
        v_arr = np.asarray(dv, dtype=np.float64)
        u_arr = u_arr - np.sum(u_arr * n_arr, axis=1, keepdims=True) * n_arr
        v_arr = v_arr - np.sum(v_arr * n_arr, axis=1, keepdims=True) * n_arr
        u_arr /= np.maximum(np.linalg.norm(u_arr, axis=1, keepdims=True), 1e-8)
        v_arr /= np.maximum(np.linalg.norm(v_arr, axis=1, keepdims=True), 1e-8)
        du = [tuple(map(float, row)) for row in u_arr]
        dv = [tuple(map(float, row)) for row in v_arr]
    geo = {
        "vert_count": len(g.verts),
        "headers": [
            {"item_size": 3, "enum_type": dm.POSITION0},
            {"item_size": 2, "enum_type": dm.TEXCOORD0},
            {"item_size": 7, "enum_type": dm.BLENDINDICES0},
            {"item_size": 3, "enum_type": dm.BLENDWEIGHT0},
            {"item_size": 3, "enum_type": dm.NORMAL0},
            {"item_size": 3, "enum_type": dm.UV_DIRECTION_V0},
            {"item_size": 3, "enum_type": dm.UV_DIRECTION_U0},
        ],
        "verts": g.verts, "uv0": g.uvs, "blendindices": pal_idx,
        "blendweights": pal_w, "normals": g.normals,
        "uvdir_v": dv, "uvdir_u": du,
        "name_hash": dm.hash64(f"{g.name}.DieselGeometry"),
        "remaining": b"",
    }
    topo = {"primitive": 3, "indices": [i for f in g.faces for i in f],
            "items2": b"", "name_hash": dm.hash64(f"{g.name}.Topology"),
            "remaining": b""}

    # -- skinbones --
    palette_ids = [template.name_id[n] for n in g.palette]
    rotations = [dm.mat_inv(template.worlds[template.name_id[n]]) for n in g.palette]
    maps = [list(range(len(palette_ids)))]
    maps += [list(range(len(palette_ids))) for _ in g.slices]
    skin = {"maps": maps, "root": template.hips_id, "objects": palette_ids,
            "rotations": rotations, "global": template.hips_world, "remaining": b""}

    sections = [
        dm.Section(dm.SKINBONES, skin_id, dm.encode_skinbones(skin)),
        dm.Section(dm.GEOMETRY, geo_id, dm.encode_geometry(geo)),
        dm.Section(dm.TOPOLOGY, topo_id, dm.encode_topology(topo)),
        dm.Section(dm.PASSTHROUGH_GP, gp_id,
                   dm.encode_passthroughgp({"geometry": geo_id, "topology": topo_id,
                                            "remaining": b""})),
        dm.Section(dm.TOPOLOGY_IP, ip_id,
                   dm.encode_topologyip({"topology": topo_id, "remaining": b""})),
    ]

    # -- materials + group --
    mat_secs = []
    for name, mid in zip(out_mats, mat_ids):
        mat_secs.append(dm.Section(dm.MATERIAL, mid, dm.encode_material(
            {"name_hash": dm.hash64(name), "skipped": MAT_SKIPPED_DEFAULT, "items": [],
             "remaining": b""})))
    mg_id = ids[5 + len(out_mats)]
    sections += mat_secs
    sections.append(dm.Section(dm.MATERIAL_GROUP, mg_id, dm.encode_material_group(
        {"material_ids": mat_ids[:len(out_mats)], "remaining": b""})))
    return sections


def group_atom_plan(g: Group, out_mats_sorted: list[str]) -> list[dict]:
    """RenderAtoms for the group's slices (material_id = index into sorted group mats)."""
    atoms = []
    for (src_mat, base_v, base_i, tris, nverts), slot in zip(g.slices, g.mat_slots):
        atoms.append({"base_vertex": base_v, "tri_count": tris,
                      "base_index": base_i, "slice_len": nverts,
                      "material_id": out_mats_sorted.index(slot)})
    return atoms


def atom_problems(geo: dict, topo: dict, atoms: list[dict]) -> list[str]:
    """Reasons the render atoms do not describe this geometry.

    A Diesel render atom is a *range*: `base_vertex`/`slice_len` select a block
    of vertices, `base_index`/`tri_count` a run of triangles in the index
    stream (`base_index` is three times a triangle number). Indices are
    absolute, so a triangle may reach vertices outside its own block (the
    neck-cap fan does exactly that); what must hold is that the atoms *tile*
    both the vertex array and the triangle stream, with nothing shared and
    nothing left over.

    Get the triangle offset wrong and the atom draws some other part of the
    mesh with this material while the geometry it was meant for is never drawn
    at all — a silent failure: the file stays structurally valid and previews
    that read the mesh directly look perfect. That is exactly what happened to
    the grafted hands.
    """
    problems: list[str] = []
    want_v = 0
    for k, a in sorted(enumerate(atoms), key=lambda kv: kv[1]["base_vertex"]):
        if a["base_vertex"] != want_v:
            problems.append(f"atom {k} ({a['base_vertex']}) does not follow the "
                            f"vertex block ending at {want_v}")
        want_v = a["base_vertex"] + a["slice_len"]
    if want_v != len(geo["verts"]):
        problems.append(f"vertex blocks cover {want_v} of {len(geo['verts'])}")

    ntri = len(topo["indices"]) // 3
    want_t = 0
    for k, a in sorted(enumerate(atoms), key=lambda kv: kv[1]["base_index"]):
        if a["base_index"] != want_t * 3:
            problems.append(f"atom {k} draws from triangle {a['base_index'] // 3}"
                            f", not {want_t} — it would draw another part of "
                            f"the mesh")
        want_t += a["tri_count"]
    if want_t != ntri:
        problems.append(f"atoms draw {want_t} of {ntri} triangles")
    return problems


def audit_model(src) -> list[str]:
    """`atom_problems` over every mesh node of a built model."""
    mf = dm.ModelFile.read_path(src) if isinstance(src, (str, Path)) else src
    out: list[str] = []
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if not md.get("atoms"):
            continue
        try:
            gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        except (ValueError, KeyError):
            continue
        out.extend(atom_problems(geo, topo, md["atoms"]))
    return out


def group_bounds(g: Group):
    xs = [v[0] for v in g.verts]; ys = [v[1] for v in g.verts]; zs = [v[2] for v in g.verts]
    bmin = (min(xs), min(ys), min(zs))
    bmax = (max(xs), max(ys), max(zs))
    radius = max((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5 for v in g.verts)
    return bmin, bmax, radius


# ------------------------------------------------------------ assembly

#: Parts of the rig that make up a first-person viewmodel. Anything shaded
#: mostly by these belongs in the fps unit; everything else (torso, legs) is
#: stripped.
_FPS_PARTS = ("Shoulder", "Arm", "ForeArm", "Hand")


def is_fps_arm_bone(name: str) -> bool:
    """True for the arm chain *and every finger chain hanging off it*.

    The viewmodel cut has to be a rule, not a fixed bone list: a hand whose
    fingers carry their own weights is dominated by ``LeftHandPinky3``, not by
    ``LeftHand``, so a list that stops at the wrist (or at the thumb) drops
    ~500 finger vertices from the fps unit while the third-person unit keeps
    them — the heister then holds her gun with two mitten stumps in first
    person only.  This is item 16 of `knowledge/games/payday-2/
    las-moog-outfit-porting.md`; keep the cut in step with the rig.
    """
    return (name.startswith(("Left", "Right"))
            and any(part in name for part in _FPS_PARTS))


#: Explicit name list for routes whose source binds no finger weights (the
#: Miranda line). New code should cut with :func:`is_fps_arm_bone`.
FPS_BONES = tuple(
    f"{side}{part}" for side in ("Left", "Right") for part in _FPS_PARTS
)


def extract_bones(g: Group, bones, name: str, min_weight: float = 0.5) -> Group:
    """A new group with only the geometry dominated by ``bones``.

    ``bones`` is either a container of names or a predicate on the group's own
    palette; pass :func:`is_fps_arm_bone` when the rig has finger chains.

    The fps unit is arms-only — the guide is explicit that a viewmodel shows
    nothing else. Rather than retarget a second time, this slices the already
    posed third-person geometry: both templates share the same PD2 bind pose,
    so the arm vertices land exactly where the viewmodel skeleton expects them.

    Slices are rebuilt per source material, with one contiguous vertex block
    each, because a Diesel render atom addresses a vertex range.
    """
    wanted = ({p for p in g.palette if bones(p)} if callable(bones)
              else set(bones))
    keep = [i for i, infl in enumerate(g.weights)
            if sum(w for p, w in infl if g.palette[p] in wanted) >= min_weight]
    keep_set = set(keep)
    face_to_slice = {}
    for si, (_mat, _bv, base_i, tris, _nv) in enumerate(g.slices):
        for f in range(base_i // 3, base_i // 3 + tris):
            face_to_slice[f] = si

    # surviving faces grouped by the source material they came from, kept in
    # source order (linear: the previous version rebuilt a set and searched the
    # face list per triangle, which cost minutes on a 100k-triangle body)
    by_slice: dict[int, list[tuple]] = {}
    for f, tri in enumerate(g.faces):
        a, b, c = tri
        if a in keep_set and b in keep_set and c in keep_set:
            by_slice.setdefault(face_to_slice.get(f, 0), []).append(tri)
    if not by_slice:
        raise SystemExit(f"{name}: no geometry dominated by {sorted(wanted)}")

    out = Group(name=name)
    out.palette = list(g.palette)
    # vertices are emitted per slice, in first-use order, so each slice owns a
    # contiguous block: skin arms first, then the sleeve that covers them
    for si in sorted(by_slice):
        tri_ids = by_slice[si]
        used: list[int] = []
        seen: dict[int, int] = {}
        local_faces = []
        for a, b, c in tri_ids:
            row = []
            for v in (a, b, c):
                if v not in seen:
                    seen[v] = len(used)
                    used.append(v)
                row.append(seen[v])
            local_faces.append(tuple(row))
        base_v = len(out.verts)
        for v in used:
            out.verts.append(g.verts[v])
            out.normals.append(g.normals[v])
            out.uvs.append(g.uvs[v])
            out.weights.append(g.weights[v])
        out.slices.append((g.slices[si][0], base_v, len(out.faces) * 3,
                           len(local_faces), len(used)))
        out.mat_slots.append(g.mat_slots[si])
        out.faces.extend((a + base_v, b + base_v, c + base_v)
                         for a, b, c in local_faces)
    return out


def assemble_model(template: Template, groups: dict[str, Group],
                   share: dict[str, str],
                   drop_drawables: tuple[str, ...] = ()) -> dm.ModelFile:
    """Template sections with mesh blocks and materials replaced.

    ``share`` maps drawable name -> group name; drawables not in ``share``
    keep their template geometry blocks untouched (e.g. fps c_block). New
    group blocks are emitted where the template's mesh blocks were; material
    sections go where the template's material sections were.

    ``drop_drawables`` removes named drawables entirely — geometry, topology,
    skin palette, object-tree nodes and their children. Used to strip a
    template's own head when the outfit does not ship one: a drawable that is
    present but disabled would still carry someone else's character in the
    pack.
    """
    old = template.mf

    # template section ids belonging to re-authored mesh blocks
    block_ids: set[int] = set()
    for dname in share:
        md = template.drawables[dname]
        block_ids.add(md["skinbones"])
        block_ids.add(md["passthroughgp"])
        block_ids.add(md["topologyip"])
        for s in old.sections:
            if s.type == dm.PASSTHROUGH_GP and s.id == md["passthroughgp"]:
                gp = dm.decode_passthroughgp(s.payload)
                block_ids |= {gp["geometry"], gp["topology"]}
            if s.type == dm.TOPOLOGY_IP and s.id == md["topologyip"]:
                ip = dm.decode_topologyip(s.payload)
                block_ids.add(ip["topology"])

    drop_ids: set[int] = set()
    for dname in drop_drawables:
        if dname not in template.drawables:
            raise KeyError(f"template has no drawable {dname!r}")
        md = template.drawables[dname]
        drop_ids.add(template.name_id[dname])
        drop_ids.add(md["skinbones"])
        drop_ids.add(md["passthroughgp"])
        drop_ids.add(md["topologyip"])
        for s in old.sections:
            if s.type == dm.PASSTHROUGH_GP and s.id == md["passthroughgp"]:
                gp = dm.decode_passthroughgp(s.payload)
                drop_ids |= {gp["geometry"], gp["topology"]}
            if s.type == dm.TOPOLOGY_IP and s.id == md["topologyip"]:
                ip = dm.decode_topologyip(s.payload)
                drop_ids.add(ip["topology"])
    # anything parented to a dropped node has to go with it, or the object tree
    # keeps a dangling child id
    changed = True
    while changed:
        changed = False
        for s in old.sections:
            if s.type in (dm.OBJECT3D, dm.MODEL_DATA) and s.id not in drop_ids:
                obj = (dm.decode_object3d(s.payload) if s.type == dm.OBJECT3D
                       else dm.decode_model_data(s.payload))
                if obj.get("parent") in drop_ids:
                    drop_ids.add(s.id)
                    changed = True

    # template materials stay (fps c_block keeps referencing them); author
    # metadata is dropped. New materials are inserted before the object tree.
    drop_types = {dm.AUTHOR}

    # id allocation for new sections
    next_id = max(s.id for s in old.sections) + 1

    def take_id() -> int:
        nonlocal next_id
        v = next_id
        next_id += 1
        return v

    group_secs: dict[str, list[dm.Section]] = {}
    group_refs: dict[str, dict] = {}
    for gname, g in groups.items():
        out_mats = sorted(set(g.mat_slots))
        ids = [take_id() for _ in range(5)] + [take_id() for _ in out_mats] + [take_id()]
        group_secs[gname] = author_group_sections(g, template, ids)
        group_refs[gname] = {
            "skin": ids[0], "gp": ids[3], "ip": ids[4],
            "mg": ids[5 + len(out_mats)],
            "atoms": group_atom_plan(g, out_mats),
            "bounds": group_bounds(g),
        }

    new_mat_secs: list[dm.Section] = []
    for secs in group_secs.values():
        new_mat_secs += [s for s in secs if s.type in (dm.MATERIAL, dm.MATERIAL_GROUP)]

    def rewrite_model_data(payload: bytes, dname: str) -> bytes:
        md = dm.decode_model_data(payload)
        refs = group_refs[share[dname]]
        md["passthroughgp"] = refs["gp"]
        md["topologyip"] = refs["ip"]
        md["skinbones"] = refs["skin"]
        md["matgroup"] = refs["mg"]
        md["atoms"] = refs["atoms"]
        bmin, bmax, radius = refs["bounds"]
        md["bounds_min"] = bmin
        md["bounds_max"] = bmax
        md["bounding_radius"] = radius
        return dm.encode_model_data(md)

    out_sections: list[dm.Section] = []
    groups_emitted = False
    mats_inserted = False

    def flush_groups():
        nonlocal groups_emitted
        if groups_emitted:
            return
        groups_emitted = True
        for gname in groups:
            out_sections.extend(group_secs[gname])

    for s in old.sections:
        if s.type in drop_types or s.id in drop_ids:
            continue
        if s.type == dm.OBJECT3D and not mats_inserted:
            out_sections.extend(new_mat_secs)
            mats_inserted = True
        if s.id in block_ids:
            flush_groups()
            continue
        if s.type == dm.MODEL_DATA and template.id_name.get(s.id) in share:
            s = dm.Section(dm.MODEL_DATA, s.id,
                           rewrite_model_data(s.payload, template.id_name[s.id]))
        out_sections.append(s)

    if not mats_inserted:
        out_sections.extend(new_mat_secs)
    flush_groups()

    # custom hashlist: union of template names + authored names (kept last)
    names = list(template.names.values())
    for g in groups.values():
        for n in sorted(set(g.mat_slots)):
            if n not in names:
                names.append(n)
        for n in (f"{g.name}.DieselGeometry", f"{g.name}.Topology"):
            if n not in names:
                names.append(n)
    for s in out_sections:
        if s.type == dm.CUSTOM_HASHLIST:
            s.payload = dm.encode_custom_hashlist({"names": names, "remaining": b""})

    return dm.ModelFile(out_sections)


# ------------------------------------------------------------ previews

def preview_from_model(path: Path, out_dir: Path, prefix: str) -> None:
    import preview as pv
    mf = dm.ModelFile.read_path(path)
    faces_by_mat: dict[str, tuple] = {}
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if md.get("version") != 3:
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        mat_names = []
        for mid in mg["material_ids"]:
            mat = dm.decode_material(mf.by_id(mid).payload)
            mat_names.append(template_name(mat["name_hash"], mf))
        verts = geo["verts"]
        idx = topo["indices"]
        all_faces = [(idx[i], idx[i + 1], idx[i + 2]) for i in range(0, len(idx), 3)]
        for atom in md["atoms"]:
            t0 = atom["base_index"] // 3
            tris = all_faces[t0:t0 + atom["tri_count"]]
            mname = mat_names[atom["material_id"]] if atom["material_id"] < len(mat_names) else "mat"
            faces_by_mat.setdefault(mname, ([], [], []))
            bucket = faces_by_mat[mname]
            base = len(bucket[0])
            # collect verts per face (no welding — simple)
            for (a, b, c) in tris:
                for vi in (a, b, c):
                    bucket[0].append(verts[vi])
                    bucket[1].append(geo["normals"][vi] if vi < len(geo["normals"]) else (0, 0, 1))
                bucket[2].append((base, base + 1, base + 2))
                base += 3
    out_dir.mkdir(parents=True, exist_ok=True)
    for mname, (fv, _fn, ff) in faces_by_mat.items():
        color = (150, 150, 150)
        for key, col in FACE_COLORS.items():
            if key in mname or mname.endswith(key):
                color = col
        for view in ("front", "side", "iso"):
            out = out_dir / f"{prefix}_{mname}_{view}.png"
            pv.render(fv, ff, [color] * len(ff), out, view=view)


def template_name(h: int, mf: dm.ModelFile) -> str:
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    for n in hl["names"]:
        if dm.hash64(n) == h:
            return n
    return f"#{h:016x}"


# ------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, required=True,
                    help="directory containing 2b.model and fps_2b.model")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "pd2-las")
    ap.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args(argv)

    skel_map = json.loads((HERE / "skeleton_map.json").read_text())
    tpp_template = load_template(args.templates / "2b.model")
    fps_template = load_template(args.templates / "fps_2b.model")

    arc = VpkArchive.from_zip(args.source_zip, "miranda_rochelle.vpk")
    tpp_model = load_model(*(arc.read(p) for p in TPP_MDLS))
    fps_model = load_model(*(arc.read(p) for p in FPS_MDLS))
    print(f"source: tpp {len(tpp_model.vertices)} verts / {tpp_model.triangle_count} tris, "
          f"fps {len(fps_model.vertices)} verts / {fps_model.triangle_count} tris")

    packs = []
    for label, template, model, group_specs in (
            ("tpp", tpp_template, tpp_model, TPP_GROUPS),
            ("fps", fps_template, fps_model, FPS_GROUPS)):
        groups: dict[str, Group] = {}
        share: dict[str, str] = {}
        for gname, spec in group_specs.items():
            g = transfer_group(model, spec, skel_map, template, gname)
            print(f"[{label}] group {gname}: {len(g.verts)} verts, "
                  f"{len(g.faces)} tris, palette {len(g.palette)}")
            if not g.verts:
                raise SystemExit(f"group {gname} is empty — check material names")
            groups[gname] = g
            for d in spec["drawables"]:
                share[d] = gname
        mf = assemble_model(template, groups, share)
        out_name = "miranda.model" if label == "tpp" else "fps_miranda.model"
        out_path = args.out / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(mf.write())
        print(f"[{label}] wrote {out_path} ({out_path.stat().st_size} bytes)")
        packs.append((label, out_path))

        # signed volume sanity (winding orientation)
        vol = 0.0
        for (a, b, c) in groups["shadow"].faces:
            p, q, r = groups["shadow"].verts[a], groups["shadow"].verts[b], groups["shadow"].verts[c]
            vol += (p[0] * (q[1] * r[2] - q[2] * r[1])
                    - p[1] * (q[0] * r[2] - q[2] * r[0])
                    + p[2] * (q[0] * r[1] - q[1] * r[0]))
        print(f"[{label}] signed volume (shadow group): {vol / 6:.1f}")

        if not args.no_previews:
            preview_from_model(out_path, args.out / "previews", f"{label}_authored")
            print(f"[{label}] previews -> {args.out / 'previews'}")

    # update pack scaffold and textures (build_las --stage all)
    pack_dir = args.out / "Miranda_LAS"
    unit_dir = pack_dir / "assets" / "units" / "miranda" / "skins" / "miranda"
    import build_las

    rc = build_las.main(
        ["--stage", "all", "--source", str(args.source_zip), "--out", str(args.out)]
    )
    if rc != 0:
        raise SystemExit(f"build_las failed with exit code {rc}")
    if not unit_dir.is_dir():
        raise SystemExit(f"pack scaffold still missing at {unit_dir}")
    import shutil

    import las_pack

    for label, out_path in packs:
        shutil.copy2(out_path, unit_dir / out_path.name)
    wip = pack_dir / "WIP_DO_NOT_INSTALL.txt"
    if wip.exists():
        wip.unlink()
    las_pack.refresh_build_info(pack_dir, templates={
        name: hashlib.sha256((args.templates / name).read_bytes()).hexdigest()
        for name in ("2b.model", "fps_2b.model")
    })
    zip_path = las_pack.zip_pack(pack_dir)
    zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.parent / f"{zip_path.name}.sha256").write_text(
        f"{zip_sha}  build/pd2-las/{zip_path.name}\n"
    )
    if args.out.resolve() == (REPO / "build" / "pd2-las").resolve():
        dist_dir = REPO / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        dist_zip = dist_dir / zip_path.name
        shutil.copy2(zip_path, dist_zip)
        (dist_dir / f"{zip_path.name}.sha256").write_text(
            f"{zip_sha}  dist/{zip_path.name}\n"
        )
    print(f"pack updated: {unit_dir} (+ dist/{zip_path.name}, sha256={zip_sha[:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
