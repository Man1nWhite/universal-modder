"""Pose a built model offline: adduct the arms to approximate the in-game idle.

A hole at the armhole or the wrist only opens when the arms rotate down from the
bind pose (the shoulder fabric follows the arm bone and pulls away from the
torso), so a bind-pose render cannot show it. `pose` re-skins the body drawable
with the arms adducted ~60 deg. No command of its own: `glove_check.py` and
`pose_zoom.py` render what it returns.

Diesel skinning (row-major storage, translation in row 3):
    Rotations[k] = inverse(WorldBind_k);  v_posed = sum w_k * WorldPosed_k @ Rot_k @ v
Rigidly rotating an arm chain about its shoulder pivot makes WorldPosed_k =
R_pivot @ WorldBind_k, so the per-bone delta collapses to R_pivot for every bone
in that chain. A vertex therefore moves by its total weight on each chain:
    v_posed = wL * (R_L @ v) + wR * (R_R @ v) + wOther * v
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diesel_model as dm  # noqa: E402
import build_models as bm  # noqa: E402


def _rot_y(deg):
    t = np.radians(deg)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rotate_about(v, pivot, R):
    """Row-vector rigid rotation of points v about pivot (R column-convention)."""
    return (v - pivot) @ R.T + pivot


def load_body(model_path: Path):
    mf = dm.ModelFile.read_path(model_path)
    sb = dm.decode_skinbones(mf.by_type(dm.SKINBONES)[0].payload)
    names = [bm.template_name(dm.decode_object3d(mf.by_id(o).payload)["name_hash"], mf)
             for o in sb["objects"]]
    # Diesel stores row-vector matrices: translation lives in row 3, and a
    # point transforms as p' = p @ M[:3,:3] + M[3,:3]. Do NOT transpose.
    # sb["rotations"] are the INVERSE-bind transforms; invert to world bind.
    WB = [np.linalg.inv(np.array(r).reshape(4, 4)) for r in sb["rotations"]]
    best = None
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        if len(mg["material_ids"]) > 1:
            best = (md, mg)
            break
    md, mg = best
    gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
    verts = np.array(geo["verts"], np.float64)
    normals = np.array(geo["normals"], np.float64)
    uvs = np.array(geo["uv0"], np.float64)
    faces = np.array(topo["indices"], np.int64).reshape(-1, 3)
    bidx = np.array(geo["blendindices"], np.int64)
    bw = np.array(geo["blendweights"], np.float64)
    w4 = np.column_stack([bw, np.clip(1.0 - bw.sum(axis=1), 0, 1)])
    mat_names = [bm.template_name(dm.decode_material(mf.by_id(m).payload)["name_hash"], mf)
                 for m in mg["material_ids"]]
    return dict(mf=mf, sb=sb, names=names, WB=WB, md=md, verts=verts,
                normals=normals, uvs=uvs, faces=faces, bidx=bidx, w4=w4,
                mat_names=mat_names)


def arm_chains(names):
    left, right = set(), set()
    for i, n in enumerate(names):
        if n in ("LeftArm", "LeftForeArm", "LeftHand") or n.startswith("LeftHand"):
            left.add(i)
        if n in ("RightArm", "RightForeArm", "RightHand") or n.startswith("RightHand"):
            right.add(i)
    return left, right


def pose(body, deg_left=-60.0, deg_right=60.0):
    names, WB = body["names"], body["WB"]
    left, right = arm_chains(names)
    li = names.index("LeftArm"); ri = names.index("RightArm")
    piv_l = WB[li][3, :3]; piv_r = WB[ri][3, :3]
    bidx, w4 = body["bidx"], body["w4"]
    wl = np.zeros(len(bidx)); wr = np.zeros(len(bidx))
    for k in range(4):
        col = bidx[:, k]
        wl += np.where(np.isin(col, list(left)), w4[:, k], 0.0)
        wr += np.where(np.isin(col, list(right)), w4[:, k], 0.0)
    wo = np.clip(1.0 - wl - wr, 0, 1)
    v = body["verts"]
    vl = _rotate_about(v, piv_l, _rot_y(deg_left))
    vr = _rotate_about(v, piv_r, _rot_y(deg_right))
    vp = wl[:, None] * vl + wr[:, None] * vr + wo[:, None] * v
    return vp


def meshes_from(body, vp):
    meshes = []
    verts, faces = vp, body["faces"]
    for atom in body["md"]["atoms"]:
        start = atom["base_index"] // 3
        tris = faces[start:start + atom["tri_count"]]
        if not len(tris):
            continue
        used = np.unique(tris)
        remap = np.full(verts.shape[0], -1, np.int64)
        remap[used] = np.arange(used.size)
        meshes.append(dict(material=body["mat_names"][atom["material_id"]],
                           vertices=verts[used], normals=body["normals"][used],
                           uvs=body["uvs"][used], triangles=remap[tris]))
    return meshes

