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

Matrix conventions (read before touching retarget_maps / transfer_group):

- dm.Mat STORAGE is row-vector convention: p' = p . M + t, and
  dm.mat_mul(a, b) satisfies v.(a.b) == (v.a).b (diesel_model.py).
- The numpy blocks inside retarget_maps (_umeyama_fit, _axial_mat, the menu
  pose construction) compute in COLUMN convention (p' = A.p + t) and convert
  at the boundary via `.T.reshape(16)` when storing into a dm.Mat;
  transfer_group converts back with `reshape(4, 4).T` before applying
  `M @ p4`. Both directions are covered by round-trip tests.
- `_axial_mat` is NOT a similarity: its 3x3 is S @ R with
  S = s_core.I + (lam - s_core) v v^T, i.e. singular values {lam, s_core,
  s_core} — an affine with a rank-1 axial stretch along the segment axis v.
  Radial thickness is scaled by s_core, axial length by lam. Do not call it
  a similarity in comments or docs.

Usage (from the repo root):
  bash tools/pd2-las/recover_env.sh        # once: .venv + the 2B templates
  .venv/bin/python tools/pd2-las/build_models.py [--templates DIR] [--out DIR]

--templates is the directory holding 2b.model and fps_2b.model from
references/2b.rar. It defaults to DEFAULT_TEMPLATES, the place extract_2b.py
unpacks them to (build/pd2-las/2b/). With the default --out (build/pd2-las) the finished
zip also replaces the tracked dist/Miranda_LAS.zip; any other --out leaves the
tracked files alone. Previews are written to <out>/previews/.
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
import determinism  # noqa: E402
import extract_2b  # noqa: E402
import tangents  # noqa: E402
from source_model import ModelData, load_model  # noqa: E402
from vpk import VpkArchive  # noqa: E402

REPO = HERE.parents[1]
SOURCE_ZIP = REPO / "models" / "l4d2_miranda_lawson_1.zip"
#: The default of every builder's --templates: where extract_2b.py unpacks
#: references/2b.rar. That module is the one place the path is written.
DEFAULT_TEMPLATES = extract_2b.TEMPLATES

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
    """Per source bone: map source-world -> target-world.

    Anatomically partitioned retargeting that avoids the three
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

    NOTE: torso/leg/hand fits are true similarities; the Arm/ForeArm operators
    built via _axial_mat are affine with a rank-1 axial stretch (singular
    values {lam, s_core, s_core}), NOT similarities — see the module header.
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
            # Anisotropic affine, NOT a similarity: singular values of the
            # 3x3 are {lam along v, s_core radial}. Radial thickness scales by
            # s_core, axial length by lam.
            s_seg = _s_core * np.eye(3, dtype=np.float64) + (lam - _s_core) * np.outer(v, v)
            m_seg = np.eye(4, dtype=np.float64)
            m_seg[:3, :3] = s_seg @ r_seg
            # column-convention pin: s_start -> t_start exactly (s_end ->
            # t_end follows from r_seg/lam). In the TPP arm path this pin
            # does NOT survive composing M_menu^-1 afterwards; fix_arm_fits
            # re-pins the joint by translation.
            m_seg[:3, 3] = t_start - (m_seg[:3, :3] @ s_start)
            return m_seg, r_seg

        if "Hips" in direct_src:
            # Full-body third-person character: construct Shoulder, Arm, and
            # ForeArm bind operators via PD2's standing menu pose.
            # (numpy blocks here are column convention; stored row via .T —
            #  see module header. Column reading: M_menu = W_posed @ inv(W_bind),
            #  row reading: W_bind^-1 . W_posed maps bind -> posed.)
            # 1. In the standing pose, Shoulder and Arm meet at a natural
            #    feminine shoulder width (+1.2 cm outward from L4D2's UpperArm
            #    head) so Spine2, Shoulder, and Arm agree at the shoulder
            #    without a bicep bulge or under-shoulder dent.
            # 2. The standing elbow is shifted 2.8 cm inward along the exact
            #    invariant hinge axis of inv(M_menu[Arm]) @ M_menu[ForeArm], so
            #    Arm and ForeArm meet with 0.000 cm gap in BOTH bind pose and
            #    standing pose while eliminating the outward elbow bow.
            #    The axis is extracted from vee(R - R^T) = 2 sin(th) . axis and
            #    NORMALIZED below (ax_p), so the shift is exactly 2.8 cm.
            #    Trade-off: the shift lengthens the posed upper arm by
            #    sqrt(L^2 + 2.8^2) - L ~= 0.17 cm — deliberate, not a bug.
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
            assert abs(float(np.linalg.norm(ax_p)) - 1.0) < 1e-9, "hinge axis not unit"
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
    # Optional authoring rest worlds. Most groups use template.worlds; a
    # group rebound in another pose supplies the matching absolute world
    # matrix per palette bone so geometry and inverse-bind transforms agree.
    rest_worlds: dict | None = None


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
            # Loaders must hand us CCW like the COLLADA importer does.
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



# PD2 bind-pose arm joints (cm), taken from the 2B template: (wrist, elbow).
ARM_JOINTS = {
    -1: ((-45.99, 18.70, 124.47), (-39.50, -0.99, 133.29)),
    1: ((45.99, 18.70, 124.47), (39.50, -0.99, 133.29)),
}


def extend_sleeves_to_wrist(g: Group, mats: dict,
                            t_knee: float = 13.0, perp_max: float = 7.5) -> dict:
    """Stretch the layers on the arm down the forearm until they overlap the glove.

    For a pack without hands. A source that is worn *with hands* ends every
    layer on the arm short of the wrist, so that its own hand mesh covers the
    junction. PD2 spawns the heister's glove *at* the hand joint, so in game the
    sleeve, the arm and the glove never meet: the glove floats, with a gap of
    empty space between it and the sleeve.

    This pass redistributes the last ``t_knee`` cm of the arm along the forearm
    axis (a pure rank-1 stretch, so the cross-section -- and therefore the cuff
    radius -- is untouched) until the shortest layer reaches its target past the
    hand joint. The sleeve mouth then sits *inside* the glove cuff and the
    glove appears to come out of the sleeve. Weights, UVs and topology are
    unchanged, so the pose, the seam weld and the texture all survive.

    ``mats`` names the layers by source material, each with its target in cm.
    ``t`` is measured from the PD2 hand joint towards the elbow, so a negative
    target ends the layer past the wrist. Give each layer its own: the outer
    sleeve deepest inside the glove, the bare arm just behind it, so that it
    fills the sleeve mouth and leaves no dark ring. A material that is not
    named is not moved.
    """
    targets = dict(mats)
    import numpy as np

    report = {"moved": 0, "materials": {}, "reaches": {}}
    for side in (-1, 1):
        wrist, elbow = (np.array(v, dtype=np.float64) for v in ARM_JOINTS[side])
        d = elbow - wrist
        d /= np.linalg.norm(d)
        for mat, base_v, _bi, _tris, nverts in g.slices:
            if mat not in targets:
                continue
            target = targets[mat]
            idx = []
            ts = []
            for i in range(base_v, base_v + nverts):
                p = np.asarray(g.verts[i], dtype=np.float64)
                if side * p[0] <= 0.0:
                    continue
                rel = p - wrist
                t = float(rel @ d)
                if not (-8.0 <= t <= t_knee):
                    continue
                if float(np.linalg.norm(rel - t * d)) > perp_max:
                    continue
                idx.append(i)
                ts.append(t)
            if len(idx) < 8:
                continue
            t_min = min(ts)
            if t_min <= target:
                continue
            k = (t_knee - target) / max(t_knee - t_min, 1e-6)
            for i, t in zip(idx, ts):
                p = np.asarray(g.verts[i], dtype=np.float64)
                rel = p - wrist
                radial = rel - float(rel @ d) * d
                t2 = t_knee - (t_knee - t) * k
                q = wrist + t2 * d + radial
                g.verts[i] = (float(q[0]), float(q[1]), float(q[2]))
                report["moved"] += 1
            key = f"{mat}.{'L' if side < 0 else 'R'}"
            report["materials"][key] = len(idx)
            report["reaches"][key] = (round(t_min, 2), round(target, 2))
    return report


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

    # The tangent frames come from the float32 values the file will hold, and
    # where the UV map gives a vertex no handedness, from a rule (tangents.py).
    # Made from the float64 working values, as they were until 2026-11-12, they
    # depended on the CPU that ran the build.
    if len(g.normals) == len(g.verts) and len(g.verts) > 0:
        du, dv = tangents.tangent_frames(g.verts, g.normals, g.uvs, g.faces)
    else:
        du, dv = dm.compute_uv_directions(g.verts, g.uvs, g.faces)
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
    rest_worlds = g.rest_worlds or {}
    rotations = [dm.mat_inv(rest_worlds.get(n, template.worlds[template.name_id[n]]))
                 for n in g.palette]
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
    absolute, so a triangle may reach vertices outside its own block (a fan
    that caps an opening does exactly that); what must hold is that the atoms *tile*
    both the vertex array and the triangle stream, with nothing shared and
    nothing left over.

    Get the triangle offset wrong and the atom draws some other part of the
    mesh with this material while the geometry it was meant for is never drawn
    at all — a silent failure: the file stays structurally valid and previews
    that read the mesh directly look perfect. That is exactly what happened to
    the hands grafted onto the outfit that was cancelled later: they were in
    the file and no atom drew them.
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

    # Per-atom containment: a triangle an atom draws must not lie wholly inside
    # another slice's vertex block. Indices are absolute, so a single index may
    # legitimately reach outside its own block (a fan that caps an opening does
    # exactly that); what is not legal is an atom drawing whole triangles whose vertices
    # all belong to a different slice's block, because D3D9 binds the index
    # buffer with the atom's vertex block and those samples are out of range.
    # The atoms still tile the stream, so this is a silent structural failure:
    # the file stays valid and previews that read the mesh directly look fine.
    # Measured across all atomised drawables in both Christie packs, zero clean
    # atoms draw such foreign triangles, so the check is strict: no allowance.
    idx = topo["indices"]
    for k, a in enumerate(atoms):
        bv, sl, tc, bi = a["base_vertex"], a["slice_len"], a["tri_count"], a["base_index"]
        end = bv + sl
        seg = idx[bi:bi + tc * 3]
        foreign = sum(1 for i in range(0, len(seg), 3)
                      if all(v >= end for v in seg[i:i + 3]))
        if foreign:
            problems.append(
                f"atom {k} draws {foreign} whole triangles that lie entirely "
                f"inside another slice's vertex block")
    return problems



def read_drawable(path, drawable: str = "g_body") -> dict | None:
    """Geometry + skin weights of one drawable from a built `.model`.

    Returns ``{"verts", "faces", "blendindices", "blendweights", "palette"}``
    with ``palette`` resolved to bone *names* (the section ids in the file are
    not stable between packs), or ``None`` if the drawable is absent.
    """
    mf = dm.ModelFile.read_path(path) if isinstance(path, (str, Path)) else dm.ModelFile.read(path)
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    hash_name = {dm.hash64(n): n for n in hl}
    objs, _worlds = _resolve_worlds(mf)
    name_of = {sid: hash_name.get(o.get("name_hash"), "") for sid, o in objs.items()}
    for sec in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(sec.payload)
        if name_of.get(sec.id) != drawable or md.get("version") != 3:
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        sk = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
        return {
            "verts": geo["verts"],
            "faces": list(zip(topo["indices"][0::3], topo["indices"][1::3],
                              topo["indices"][2::3])),
            "blendindices": geo["blendindices"],
            "blendweights": geo["blendweights"],
            "palette": [name_of.get(b, str(b)) for b in sk["objects"]],
            "rest_worlds": {
                name_of.get(b, str(b)): dm.mat_inv(rotation)
                for b, rotation in zip(sk["objects"], sk["rotations"])
            },
        }
    return None


def segment_fit_report(path, template: "Template", drawable: str = "g_body") -> dict:
    """Mesh-vs-skeleton fit numbers for a built model (see segment_fit.py).

    ``path`` is a `.model` file or, like `read_drawable`, the file's bytes: a
    model read out of a pack zip needs no copy on disk to be measured.
    """
    import segment_fit as sf

    drawn = read_drawable(path, drawable)
    if drawn is None:
        label = path if isinstance(path, (str, Path)) else f"model ({len(path)} bytes)"
        raise ValueError(f"{label}: no {drawable} drawable")
    weights = [[(pi, w) for pi, w in zip(bi, bw) if w > 0.0]
               for bi, bw in zip(drawn["blendindices"], drawn["blendweights"])]
    # Geometry and inverse binds may intentionally use an authoring rest pose
    # other than the animation template (Christie's near-idle arms). Measure
    # against the rest skeleton encoded in the shipped skinbones, not against
    # a stale template pose that the vertices no longer claim to inhabit.
    from dataclasses import replace
    worlds = dict(template.worlds)
    for name, world in drawn.get("rest_worlds", {}).items():
        if name in template.name_id:
            worlds[template.name_id[name]] = world
    rest_template = replace(template, worlds=worlds)
    rep = sf.measure(drawn["verts"], weights, drawn["palette"], rest_template)
    rep["cuffs"] = {b: sf.cuff_distance(drawn["verts"], weights, drawn["palette"],
                                        rest_template, b)
                    for b in ("LeftHand", "RightHand")}
    return rep


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
    out.rest_worlds = dict(g.rest_worlds) if g.rest_worlds else None
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

def require_templates(path: Path, names=("2b.model", "fps_2b.model")) -> Path:
    """`path` when it holds the 2B template models, else an exit that says how to get them."""
    missing = [n for n in names if not (Path(path) / n).is_file()]
    if missing:
        raise SystemExit(
            f"2B templates not found in {extract_2b.shown(Path(path))} "
            f"(missing: {', '.join(missing)}). Run `{extract_2b.RECOVER}` to unpack "
            "references/2b.rar, or pass --templates DIR.")
    return Path(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES,
                    help="directory containing 2b.model and fps_2b.model "
                         "(default: where recover_env.sh unpacks 2b.rar, "
                         "under build/pd2-las/2b/)")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "pd2-las")
    ap.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args(argv)
    determinism.enter(__file__)
    require_templates(args.templates)

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

    # the two models go in, and each unit's .object is rewritten from its model
    las_pack.install_models(pack_dir, *(out_path for _, out_path in packs))
    las_pack.refresh_build_info(pack_dir, templates={
        name: hashlib.sha256((args.templates / name).read_bytes()).hexdigest()
        for name in ("2b.model", "fps_2b.model")
    })
    import las_outfit_pack
    zip_path = las_outfit_pack.zip_pack(pack_dir)
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
