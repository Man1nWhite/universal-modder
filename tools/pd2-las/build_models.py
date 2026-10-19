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
SOURCE_ZIP = REPO / "l4d2_miranda_lawson_1.zip"

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

        if t_sh in primary_src:
            ps_sh = src_pos[primary_src[t_sh]]
            pt_sh = np.array(dm.mat_apply_point(g_fit, tuple(ps_sh.tolist())), dtype=np.float64)
            r_sh = _rodrigues_arc(r_core @ (ps_a - ps_sh), pt_a - pt_sh) @ r_core
            s_sh = float(np.linalg.norm(pt_a - pt_sh) / max(1e-9, np.linalg.norm(ps_a - ps_sh)))
            fit_for_target[t_sh] = _make_sim_mat(s_sh, r_sh, ps_sh, pt_sh)

        r_arm = _rodrigues_arc(r_core @ (ps_f - ps_a), pt_f - pt_a) @ r_core
        s_arm = float(np.linalg.norm(pt_f - pt_a) / max(1e-9, np.linalg.norm(ps_f - ps_a)))
        fit_for_target[t_arm] = _make_sim_mat(s_arm, r_arm, ps_a, pt_a)

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
            r_fore_tmp = _rodrigues_arc(r_arm @ (ps_h - ps_f), pt_h_raw - pt_f) @ r_arm
            s_fore_tmp = float(np.linalg.norm(pt_h_raw - pt_f) / max(1e-9, np.linalg.norm(ps_h - ps_f)))
            r_hand = _rodrigues_arc(r_fore_tmp @ (ps_m - ps_h), pt_m - pt_h_raw) @ r_fore_tmp
            m_hand = _make_sim_mat(s_fore_tmp, r_hand, ps_h, pt_h_raw)

        fit_for_target[t_hand] = m_hand
        pt_wrist = np.array(dm.mat_apply_point(m_hand, tuple(ps_h.tolist())), dtype=np.float64)

        r_fore = _rodrigues_arc(r_arm @ (ps_h - ps_f), pt_wrist - pt_f) @ r_arm
        s_fore = float(np.linalg.norm(pt_wrist - pt_f) / max(1e-9, np.linalg.norm(ps_h - ps_f)))
        fit_for_target[t_fore] = _make_sim_mat(s_fore, r_fore, ps_f, pt_f)

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
                   template: Template, group_name: str) -> Group:
    g = Group(name=group_name)
    wanted = group_spec.get("materials")

    # target-centric similarity retarget (see retarget_maps)
    per_src_T = retarget_maps(model, skel_map, template)

    target_for_src: dict[int, tuple[str, dm.Mat]] = {}
    for i, T in per_src_T.items():
        tname = _map_source_bone(model, i, skel_map)
        target_for_src[i] = (tname, T)

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
            # Source (CW) -> Diesel/GLTF (CCW): swap b/c
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
            by_target: dict[str, tuple[int, float]] = {}
            for bi, w in sv.weights:
                if bi in per_src_T and w > 1e-6:
                    tname, _ = target_for_src[bi]
                    if tname in by_target:
                        rep_bi, prev_w = by_target[tname]
                        by_target[tname] = (rep_bi, prev_w + w)
                    else:
                        by_target[tname] = (bi, w)
            infl = list(by_target.values())
            infl.sort(key=lambda t: -t[1])
            infl = infl[:3]
            total = sum(w for _, w in infl) or 1.0
            infl = [(bi, w / total) for bi, w in infl]
            if not infl:
                # vertices weighted only to unmapped bones: stick to the
                # lowest mapped source bone (pelvis in practice)
                if not per_src_T:
                    raise SystemExit("no mapped source bones at all")
                infl = [(min(per_src_T), 1.0)]
            vx = vy = vz = 0.0
            nx = ny = nz = 0.0
            for bi, w in infl:
                tname, _ = target_for_src[bi]
                used_bones.add(tname)
                vx += w * dm.mat_apply_point(per_src_T[bi], sv.pos)[0]
                vy += w * dm.mat_apply_point(per_src_T[bi], sv.pos)[1]
                vz += w * dm.mat_apply_point(per_src_T[bi], sv.pos)[2]
                n = dm.mat_apply_vec(per_src_T[bi], sv.normal)
                nx += w * n[0]; ny += w * n[1]; nz += w * n[2]
            ln = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
            g.verts.append((vx, vy, vz))
            g.normals.append((nx / ln, ny / ln, nz / ln))
            g.uvs.append((sv.uv[0], 1.0 - sv.uv[1]))  # p2mt GLTF-import convention
            # palette indices assigned after palette is fixed; store bone names
            g.weights.append([(target_for_src[bi][0], w) for bi, w in infl])
        g.faces.extend((a + base_v, b + base_v, c + base_v) for a, b, c in slice_faces)
        g.slices.append((mesh.material, base_v, base_i, len(slice_faces),
                         len(slice_verts)))
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
    breaks = orientation_breaks(g)
    print(f"[{group_name}] orientation breaks: {breaks}")
    return g


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


def group_bounds(g: Group):
    xs = [v[0] for v in g.verts]; ys = [v[1] for v in g.verts]; zs = [v[2] for v in g.verts]
    bmin = (min(xs), min(ys), min(zs))
    bmax = (max(xs), max(ys), max(zs))
    radius = max((v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5 for v in g.verts)
    return bmin, bmax, radius


# ------------------------------------------------------------ assembly

def assemble_model(template: Template, groups: dict[str, Group],
                   share: dict[str, str]) -> dm.ModelFile:
    """Template sections with mesh blocks and materials replaced.

    ``share`` maps drawable name -> group name; drawables not in ``share``
    keep their template geometry blocks untouched (e.g. fps c_block). New
    group blocks are emitted where the template's mesh blocks were; material
    sections go where the template's material sections were.
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
        if s.type in drop_types:
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
        shutil.copy2(zip_path, REPO / zip_path.name)
    print(f"pack updated: {unit_dir} (+ {zip_path.name}, sha256={zip_sha[:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
