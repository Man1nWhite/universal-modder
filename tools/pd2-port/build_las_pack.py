#!/usr/bin/env python3
"""Build the Miranda Lawson Legendary Armour Skins pack from the ME2 source.

Source of truth: ``PC _ Computer - Mass Effect 2 - Non-Playable Characters -
Miranda Lawson (Romance).zip`` (rigged COLLADA + textures) at the repository
root. Output: ``dist/lawson_las.zip``, root ``Lawson_LAS/``, laid out on the
supplied ``2b.rar`` Legendary Armour Skins contract:

- ``main.xml`` BeardLib manifest (Localization + Hooks + AddFiles);
- ``hooks/lawson.lua`` registering ``LegendaryArmours.lawson`` with the 2B flag
  set (``hide_mask``, ``hide_armor``, ``replace_all``, ``fps_hide_armor``,
  ``fps_replace_body``);
- TPP unit ``lawson`` and FPS unit ``fps_lawson`` (unit/object/material_config);
- DXT5 ``.texture`` pairs with full mip pyramids (``dmodel``/``dds``);
- DODB ``.model`` files authored by ``las_model.py`` from the retargeted source
  skin (``rig_target.py``, rig contract in ``reference/las_rig.json``).

Unlike the retired route there is no character swap and no external
``pd2-work`` workspace: everything is derived from the tracked source zip and
the tracked rig contract. Nothing here is game-verified.

Usage:
    python tools/pd2-port/build_las_pack.py            # -> dist/lawson_las.zip
    python tools/pd2-port/build_las_pack.py --check    # validate only

The build is deterministic: same source + same tool code -> same zip bytes.
``dist/lawson_las.zip`` is tracked in git and published as the asset of the
GitHub release tagged ``lawson-las-v1``; ``--version`` stamps the release
version into the pack's ``build_manifest.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import las_model  # noqa: E402
import rig_target  # noqa: E402
from me2_dae import load_dae  # noqa: E402

SOURCE_ZIP = ROOT / "models" / "PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip"
RIG_JSON = HERE / "reference" / "las_rig.json"
DEFAULT_OUT = ROOT / "dist" / "lawson_las.zip"
DAE_NAME = "Miranda Lawson (Romance) - Adjusted Version.dae"

UNIT_DIR = "units/lawson/skins/lawson"
GUI_DIR = "guis/dlcs/lawson/armor_skins"
ASSET_DIR = "assets"
ROOT_DIR = "Lawson_LAS"
VERSION = "0.1.2"
# The pack is an unlicensed fan derivative of ripped ME2 assets: offline
# validated, not game-verified, not cleared for commercial redistribution.
STATUS = "experimental - offline validated, not game-verified"

# Texture Setup.txt slots -> (diffuse png, normal png or None, file base name)
TEXTURE_SLOTS = {
    "Body 1": ("HMF_MIR_NKDa_DIFF.png", "HMF_MIR_NKDa_Norm.png", "body1"),
    "Body 2": ("HMF_MIR_LGTa_Diff.png", "HMF_MIR_LGTa_Norm.png", "body2"),
    "Face": ("HMF_HED_PROMiranda_Face_Diff.png", "HMF_HED_PROMiranda_Face_Norm.png", "face"),
    "Hair": ("HMF_HED_PROMiranda_Scalp_Diff.png", "HMF_HED_PROMiranda_Scalp_Norm.png", "hair"),
    "Eyes": ("EYE_Diff.png", "EYE_Lens_Norm.png", "eyes"),
    "Eyelashes": ("miranda_eyelashes.png", "__flat__", "lashes"),
    "Teeth": ("HMF_HED_PROMiranda_Scalp_Diff.png", "HMF_HED_PROMiranda_Scalp_Norm.png", "teeth"),
    "Mouth Inside": ("HMF_HED_PROMiranda_Scalp_Diff.png", "HMF_HED_PROMiranda_Scalp_Norm.png", "mouth"),
}

# PAYDAY 2's DIFFUSE_TEXTURE:NORMALMAP shader reads the specular/gloss mask
# from the diffuse texture's alpha channel (0 = matte, 255 = full mirror gloss;
# 2B reference has mean ~8, p90 = 28..48, max = 92..96).
# Base name -> (optional ME2 spec PNG, scale, max_alpha, default_alpha)
SPECULAR_SLOTS = {
    "body1": ("HMF_MIR_NKDa_SPEC.png", 0.18, 42, 12),
    "body2": ("HMF_MIR_LGTa_Spec.png", 0.25, 64, 16),
    "face": ("HMF_HED_PROMiranda_Face_Spec.png", 0.16, 32, 8),
    "hair": ("HMF_HED_PROMiranda_Scalp_Spec.png", 0.14, 38, 14),
    "eyes": ("EYE_Spec.png", 0.35, 72, 20),
    "teeth": (None, 0.0, 14, 14),
    "mouth": (None, 0.0, 6, 6),
}

# mesh name -> (drawable, material) for the TPP model
TPP_LAYOUT = {
    "Body 1": ("g_body", "mtr_body1"),
    "Body 2": ("g_body", "mtr_body2"),
    "Face": ("g_head", "mtr_face"),
    "Hair": ("g_head", "mtr_hair"),
    "Eyes": ("g_head", "mtr_eyes"),
    "Eyelashes": ("g_head", "mtr_lashes"),
    "Teeth": ("g_head", "mtr_teeth"),
    "Mouth Inside": ("g_head", "mtr_mouth"),
}
FPS_LAYOUT = {
    "Body 1": ("g_body", "mtr_body1"),
    "Body 2": ("g_body", "mtr_body2"),
}

# material -> (render_template extras, normal map present, alpha masked)
TEMPLATE = {
    "mtr_body1": ("DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS", True, False),
    "mtr_body2": ("DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS", True, False),
    "mtr_face": ("DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS", True, False),
    "mtr_hair": ("DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS", True, False),
    "mtr_eyes": ("DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS", True, False),
    "mtr_lashes": ("ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_1WEIGHT", True, True),
    "mtr_teeth": ("DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS", True, False),
    "mtr_mouth": ("DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS", True, False),
}
MAT_BASE = {
    "mtr_body1": "body1", "mtr_body2": "body2", "mtr_face": "face",
    "mtr_hair": "hair", "mtr_eyes": "eyes", "mtr_lashes": "lashes",
    "mtr_teeth": "teeth", "mtr_mouth": "mouth",
}


def eye_uv_planar(
    positions,
    dx_frac: float = 0.0,
    dz_frac: float = 0.0,
    radius_scale: float = 0.50,
    dx_frac_pos: float | None = None,
) -> list[tuple[float, float]]:
    """Planar-project each eyeball's UVs from its frontal plane.

    ME2's eye shader placed the iris itself (EYE_Iris_Norm / EYE_Lens_Norm /
    four spec maps), so the DAE UVs put the diffuse iris right on the u-seam
    facing the camera — triangles spanning the seam smear the texture and the
    eyes render as blank pink spheres. Projecting each eyeball from its own
    frontal plane centers a round iris on the pupil direction. This is the
    static-mesh approximation of that shader; the sphere sides/back map
    outside the unit square but sit inside the head.
    """
    out = [(0.5, 0.5)] * len(positions)
    for sign, pred in ((-1.0, lambda x: x < 0.0), (1.0, lambda x: x >= 0.0)):
        idx = [i for i, p in enumerate(positions) if pred(p[0])]
        if not idx:
            continue
        cx_bbox = 0.5 * (min(positions[i][0] for i in idx) + max(positions[i][0] for i in idx))
        cz_bbox = 0.5 * (min(positions[i][2] for i in idx) + max(positions[i][2] for i in idx))
        rx = 0.5 * (max(positions[i][0] for i in idx) - min(positions[i][0] for i in idx)) or 1.0
        cur_dx = dx_frac_pos if (sign > 0.0 and dx_frac_pos is not None) else dx_frac
        cx = cx_bbox + sign * cur_dx * rx
        cz = cz_bbox + dz_frac * rx
        scale = radius_scale / rx
        for i in idx:
            u = min(0.98, max(0.02, 0.5 + scale * (positions[i][0] - cx)))
            v = min(0.98, max(0.02, 0.5 + scale * (positions[i][2] - cz)))
            out[i] = (u, v)
    return out


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def subset_mesh(rm: "rig_target.RiggedMesh", keep: set[int]):
    """Keep only listed vertices; remap faces and drop degenerate triangles."""
    remap = {v: i for i, v in enumerate(sorted(keep))}
    positions = [rm.positions[i] for i in sorted(keep)]
    normals = [rm.normals[i] for i in sorted(keep)]
    uvs = [rm.uvs[i] for i in sorted(keep)]
    weights = [rm.weights[i] for i in sorted(keep)]
    faces = []
    for a, b, c in rm.triangles:
        if a in remap and b in remap and c in remap:
            faces.append((remap[a], remap[b], remap[c]))
    return positions, normals, uvs, weights, faces


def atom_for(rm, material: str, keep=None) -> "las_model.Atom":
    if keep is None:
        return las_model.Atom(material=material, positions=rm.positions,
                              normals=rm.normals, uvs=rm.uvs,
                              weights=rm.weights, faces=rm.triangles)
    p, n, u, w, f = subset_mesh(rm, keep)
    return las_model.Atom(material=material, positions=p, normals=n,
                          uvs=u, weights=w, faces=f)


def _neck_skin_uv_island_mask(uv_img, tris):
    """Select the exact Scalp_Diff neck-skin UV island (645 verts) via UV flood-fill."""
    import numpy as np

    rounded = np.round(uv_img * 1000.0).astype(np.int64)
    _, inv = np.unique(rounded, axis=0, return_inverse=True)
    parent = list(range(int(inv.max()) + 1))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in tris:
        ra, rb, rc = find(int(inv[a])), find(int(inv[b])), find(int(inv[c]))
        parent[rb] = ra
        parent[rc] = ra
    roots = np.array([find(int(inv[i])) for i in range(len(uv_img))])
    seed_mask = (uv_img[:, 0] < 0.45) & (uv_img[:, 1] > 0.85)
    seed_roots = set(roots[seed_mask].tolist())
    return np.isin(roots, list(seed_roots))


def repair_rebound_skin_normals(face_rm, hair_rm) -> None:
    """Repair corrupted boundary normals along the face/neck seam and mouth corners.

    In the ME2 source mesh, 7 right-cheek/temple boundary vertices on ``Face``
    (and their 4 matching twins on ``Hair`` neck skin) plus 3 mouth-corner
    vertices have normals corrupted by adjacent hair cards or mouthbag
    geometry (dot with true skin surface normal = 0.017..0.540).
    """
    import numpy as np

    pf = np.asarray(face_rm.positions, dtype=np.float64)
    ph = np.asarray(hair_rm.positions, dtype=np.float64)
    nf = np.asarray(face_rm.normals, dtype=np.float64)
    nh = np.asarray(hair_rm.normals, dtype=np.float64)
    uvh = np.asarray(hair_rm.uvs, dtype=np.float64)
    uvh_img = np.column_stack([uvh[:, 0], 1.0 - uvh[:, 1]])

    tf = np.asarray(face_rm.triangles, dtype=np.int32)
    th = np.asarray(hair_rm.triangles, dtype=np.int32)
    is_ns = _neck_skin_uv_island_mask(uvh_img, th)
    ns_tri_mask = is_ns[th[:, 0]] & is_ns[th[:, 1]] & is_ns[th[:, 2]]
    th_ns = th[ns_tri_mask] + len(pf)

    p_all = np.vstack([pf, ph])
    t_skin = np.vstack([tf, th_ns])
    v0, v1, v2 = p_all[t_skin[:, 0]], p_all[t_skin[:, 1]], p_all[t_skin[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    rounded = np.round(p_all * 100.0).astype(np.int64)
    _, inv = np.unique(rounded, axis=0, return_inverse=True)
    gn_u = np.zeros((inv.max() + 1, 3), dtype=np.float64)
    for k in range(3):
        np.add.at(gn_u, inv[t_skin[:, k]], fn)
    gn_u /= np.maximum(np.linalg.norm(gn_u, axis=1, keepdims=True), 1e-8)
    gn_all = gn_u[inv]
    if float(np.sum(nf * gn_all[: len(pf)], axis=1).mean()) < 0.0:
        gn_all = -gn_all

    gn_f = gn_all[: len(pf)]
    gn_h = gn_all[len(pf) :]
    bad_f = np.sum(nf * gn_f, axis=1) < 0.75
    for vi in np.nonzero(bad_f)[0]:
        nf[vi] = gn_f[vi]
        face_rm.normals[int(vi)] = (float(gn_f[vi, 0]), float(gn_f[vi, 1]), float(gn_f[vi, 2]))
    bad_h = is_ns & (np.sum(nh * gn_h, axis=1) < 0.75)
    for vi in np.nonzero(bad_h)[0]:
        nh[vi] = gn_h[vi]
        hair_rm.normals[int(vi)] = (float(gn_h[vi, 0]), float(gn_h[vi, 1]), float(gn_h[vi, 2]))

    # Weld normals across coincident Face <-> Hair(neck_skin) seam pairs
    map_f: dict[tuple[int, int, int], list[int]] = {}
    for i, p in enumerate(pf):
        k = (int(round(p[0] * 100.0)), int(round(p[1] * 100.0)), int(round(p[2] * 100.0)))
        map_f.setdefault(k, []).append(i)
    for j in np.nonzero(is_ns)[0]:
        p = ph[j]
        k = (int(round(p[0] * 100.0)), int(round(p[1] * 100.0)), int(round(p[2] * 100.0)))
        if k in map_f:
            f_idxs = map_f[k]
            avg_n = nh[j].copy()
            for fi in f_idxs:
                avg_n = avg_n + nf[fi]
            ln = float(np.linalg.norm(avg_n)) or 1.0
            n_tuple = (float(avg_n[0] / ln), float(avg_n[1] / ln), float(avg_n[2] / ln))
            hair_rm.normals[int(j)] = n_tuple
            for fi in f_idxs:
                face_rm.normals[int(fi)] = n_tuple

    face_rm.triangles, _ = rig_target.repair_winding(
        face_rm.positions, face_rm.normals, face_rm.triangles
    )
    hair_rm.triangles, _ = rig_target.repair_winding(
        hair_rm.positions, hair_rm.normals, hair_rm.triangles
    )


def _filter_hair_main_component(hair_rm) -> None:
    """Drop the 33 disconnected 1.5-mm flyaway wire strips (809 tris) from Hair.

    In ME2's Unreal Engine 3 shader, those 33 sub-millimeter ribbons used a
    soft alpha-blended hair wisp mask (Scalp_Spec2), whereas in PAYDAY 2's
    opaque character material they rasterize as 1-pixel jagged black wires
    slicing across the right eye/cheek and floating in front of the forehead.
    Keeping the main 3D edge-connected component (2,753 tris: the solid hair
    cap + neck skin) removes all 33 sub-pixel wire artifacts cleanly.
    """
    from collections import defaultdict
    import numpy as np

    hp = np.asarray(hair_rm.positions, dtype=np.float64)
    ht = list(hair_rm.triangles)
    if not ht:
        return
    pos_key = [tuple(np.round(p, 3)) for p in hp]
    edge_to_tris: dict[tuple, list[int]] = defaultdict(list)
    for ti, (a, b, c) in enumerate(ht):
        ka, kb, kc = pos_key[a], pos_key[b], pos_key[c]
        for u, v in ((ka, kb), (kb, kc), (kc, ka)):
            if u != v:
                edge_to_tris[tuple(sorted((u, v)))].append(ti)
    adj: dict[int, set[int]] = defaultdict(set)
    for tris in edge_to_tris.values():
        for t1 in tris:
            for t2 in tris:
                if t1 != t2:
                    adj[t1].add(t2)
    visited: set[int] = set()
    best_comp: list[int] = []
    for ti in range(len(ht)):
        if ti in visited:
            continue
        comp: list[int] = []
        stack = [ti]
        visited.add(ti)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adj[cur]:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        if len(comp) > len(best_comp):
            best_comp = comp
    if best_comp and len(best_comp) < len(ht):
        keep_verts = {v for ti in best_comp for v in ht[ti]}
        cx, cy, cz = 0.0, 5.5, 169.0
        for vi in range(len(hair_rm.positions)):
            if vi not in keep_verts:
                px, py, pz = hair_rm.positions[vi]
                hair_rm.positions[vi] = (
                    cx + 0.20 * (px - cx),
                    cy + 0.20 * (py - cy),
                    cz + 0.20 * (pz - cz),
                )


def build_models(scene, rig, log=print):
    from dataclasses import replace
    import numpy as np

    # Smooth bone weights across the unified welded scene graph so cross-mesh
    # seams (Face <-> Hair under-chin seam, Body 1 <-> Body 2 catsuit seams)
    # receive identical weights and never crack apart when posed in-game.
    all_pos, all_wts, all_tris = [], [], []
    offsets: dict[str, tuple[int, int]] = {}
    for m in scene.meshes:
        off = len(all_pos)
        offsets[m.name] = (off, len(m.positions))
        all_pos.extend(m.positions)
        all_wts.extend(m.weights)
        for a, b, c in m.triangles:
            all_tris.append((a + off, b + off, c + off))
    smoothed_all = rig_target.smooth_weights(all_wts, all_pos, all_tris, iters=2)

    rigged = {
        m.name: rig_target.rebind_mesh(
            replace(m, weights=smoothed_all[offsets[m.name][0] : offsets[m.name][0] + offsets[m.name][1]]),
            scene,
            rig,
            smooth_iters=0,
        )
        for m in scene.meshes
    }
    if "Hair" in rigged:
        _filter_hair_main_component(rigged["Hair"])
    if "Face" in rigged and "Hair" in rigged:
        repair_rebound_skin_normals(rigged["Face"], rigged["Hair"])
    if "Hair" in rigged and "Body 1" in rigged:
        # Snap the bottom collar rim of Hair neck-skin to Body 1 chest skin
        ph = np.asarray(rigged["Hair"].positions, dtype=np.float64)
        uvh = np.asarray(rigged["Hair"].uvs, dtype=np.float64)
        th = np.asarray(rigged["Hair"].triangles, dtype=np.int32)
        is_ns = _neck_skin_uv_island_mask(np.column_stack([uvh[:, 0], 1.0 - uvh[:, 1]]), th)
        pb = np.asarray(rigged["Body 1"].positions, dtype=np.float64)
        top_b_idx = np.nonzero(pb[:, 2] > 148.0)[0]
        if len(top_b_idx) > 0:
            top_b = pb[top_b_idx]
            for hi in np.nonzero(is_ns & (ph[:, 2] < 156.5))[0]:
                dists = np.linalg.norm(top_b - ph[hi], axis=1)
                best = int(np.argmin(dists))
                if dists[best] < 0.20:
                    bi = int(top_b_idx[best])
                    rigged["Hair"].positions[int(hi)] = rigged["Body 1"].positions[bi]
                    rigged["Hair"].weights[int(hi)] = list(rigged["Body 1"].weights[bi])

    # Center eyeball planar UVs on the visible eyelid opening (palpebral fissure)
    # and soften horizontal/vertical normal tilt across the recessed 1.5cm eyeball sphere.
    rigged["Eyes"].uvs = eye_uv_planar(
        rigged["Eyes"].positions,
        dx_frac=0.13,
        dz_frac=-0.125,
        radius_scale=0.45,
        dx_frac_pos=0.08,
    )
    eye_nrms = []
    for nx, ny, nz in rigged["Eyes"].normals:
        nx_s = nx * 0.35
        nz_s = nz * 0.35
        ln = (nx_s * nx_s + ny * ny + nz_s * nz_s) ** 0.5 or 1.0
        eye_nrms.append((nx_s / ln, ny / ln, nz_s / ln))
    rigged["Eyes"].normals = eye_nrms

    tpp_drawables: dict[str, list] = {}
    for mesh_name, (drawable, material) in TPP_LAYOUT.items():
        tpp_drawables.setdefault(drawable, []).append(atom_for(rigged[mesh_name], material))
    tpp = [las_model.Drawable(name, atoms) for name, atoms in tpp_drawables.items()]

    fps_drawables: dict[str, list] = {}
    for mesh_name, (drawable, material) in FPS_LAYOUT.items():
        rm = rigged[mesh_name]
        _body, arms = rig_target.split_arm_verts(rm)
        if not arms:
            raise ValueError(f"{mesh_name}: no arm vertices found for the FPS cut")
        fps_drawables.setdefault(drawable, []).append(atom_for(rm, material, arms))
    fps = [las_model.Drawable(name, atoms) for name, atoms in fps_drawables.items()]

    extra = ("shadow_caster",)
    tpp_res = las_model.build_model(rig, tpp, extra_materials=extra)
    fps_res = las_model.build_model(rig, fps, extra_materials=extra)
    repaired = sum(m.flipped_faces for m in rigged.values())
    log(f"  winding: {repaired} triangles reversed (they were folded inside out "
        f"by the bind-pose transfer)")
    for label, res in (("TPP", tpp_res), ("FPS", fps_res)):
        log(f"  {label}: {res.section_count} sections, "
            + ", ".join(f"{k}={v['verts']}v/{v['tris']}t/{v['atoms']}a/{v['palette']}b"
                        for k, v in res.drawables.items()))
    return tpp_res, fps_res


def _prepare_diffuse_rgba(base: str, img, source: dict[str, bytes]):
    """Pack PD2 specular/gloss intensity into diffuse alpha and shade eye sclera."""
    import numpy as np
    from PIL import Image

    rgba = np.asarray(img.convert("RGBA"), dtype=np.uint8).copy()
    if base == "eyes":
        # Synthesize the exact full-aperture deep-sapphire iris (iris_outer=0.28,
        # iris_inner=0.25, pupil_r=0.115) matching Miranda_LAS (build_las.py).
        h, w = rgba.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        u = (xx + 0.5) / w - 0.5
        v = (yy + 0.5) / h - 0.5
        r = np.hypot(u, v)
        theta = np.arctan2(v, u)

        iris_outer = 0.28
        iris_inner = 0.25
        pupil_r = 0.115

        f1 = np.sin(theta * 58.0 + 0.35 * np.sin(theta * 7.0))
        f2 = np.cos(theta * 94.0 - 0.40 * np.cos(theta * 11.0))
        f3 = np.sin(theta * 142.0 + r * 28.0)
        fiber_detail = 0.45 * f1 + 0.35 * f2 + 0.20 * f3

        rn = np.clip((r - pupil_r) / max(iris_inner - pupil_r, 1e-4), 0.0, 1.0)
        collarette = np.exp(-(((rn - 0.28) / 0.14) ** 2))
        radial = 1.0 - 0.38 * (rn ** 1.35) + 0.12 * collarette + 0.14 * fiber_detail
        radial = np.clip(radial, 0.22, 1.25)

        upper_iris_ao = np.clip(1.0 - 0.12 * np.clip((-v - 0.04) / 0.22, 0.0, 1.0), 0.85, 1.0)
        iris_r = np.clip((38.0 * radial + 8.0 * collarette) * upper_iris_ao, 6.0, 75.0)
        iris_g = np.clip((102.0 * radial + 16.0 * collarette) * upper_iris_ao, 24.0, 148.0)
        iris_b = np.clip((196.0 * radial + 24.0 * collarette) * upper_iris_ao, 72.0, 228.0)

        limbus_t = np.clip((r - (iris_inner - 0.025)) / (iris_outer - (iris_inner - 0.025)), 0.0, 1.0)
        limbus_dark = 1.0 - 0.78 * (limbus_t ** 1.4)
        iris_r *= limbus_dark
        iris_g *= limbus_dark
        iris_b *= limbus_dark

        pupil_mask = np.clip((pupil_r + 0.012 - r) / 0.018, 0.0, 1.0)
        iris_r = iris_r * (1.0 - pupil_mask) + 2.0 * pupil_mask
        iris_g = iris_g * (1.0 - pupil_mask) + 3.0 * pupil_mask
        iris_b = iris_b * (1.0 - pupil_mask) + 5.0 * pupil_mask

        sclera_ao = np.clip(1.0 - 0.32 * np.clip((r - iris_outer) / 0.22, 0.0, 1.0), 0.62, 1.0)
        eyelid_ao = np.clip(1.0 - 0.22 * np.clip((-v - 0.05) / 0.25, 0.0, 1.0), 0.72, 1.0)
        sc_r = 162.0 * sclera_ao * eyelid_ao
        sc_g = 148.0 * sclera_ao * eyelid_ao
        sc_b = 142.0 * sclera_ao * eyelid_ao

        iris_mask = np.clip((iris_outer + 0.012 - r) / 0.022, 0.0, 1.0)
        rgba[:, :, 0] = np.clip(sc_r * (1.0 - iris_mask) + iris_r * iris_mask, 0.0, 255.0).astype(np.uint8)
        rgba[:, :, 1] = np.clip(sc_g * (1.0 - iris_mask) + iris_g * iris_mask, 0.0, 255.0).astype(np.uint8)
        rgba[:, :, 2] = np.clip(sc_b * (1.0 - iris_mask) + iris_b * iris_mask, 0.0, 255.0).astype(np.uint8)
        cornea_gloss = np.where(r < 0.125, 4, np.where(r < 0.28, 10, 8)).astype(np.uint8)
        rgba[:, :, 3] = cornea_gloss
        return rgba

    if base in SPECULAR_SLOTS:
        spec_png, scale, max_a, default_a = SPECULAR_SLOTS[base]
        if spec_png and spec_png in source:
            s_img = Image.open(io.BytesIO(source[spec_png])).convert("L")
            if s_img.size != (rgba.shape[1], rgba.shape[0]):
                s_img = s_img.resize((rgba.shape[1], rgba.shape[0]))
            s_arr = np.asarray(s_img, dtype=np.float32)
            alpha = np.clip(s_arr * scale, 2.0, float(max_a)).astype(np.uint8)
            if base == "eyes":
                # Keep cornea specular highlight over iris and low wet sheen on sclera
                alpha = np.maximum(alpha, 16)
            rgba[:, :, 3] = alpha
        else:
            rgba[:, :, 3] = default_a
    return rgba


def encode_textures(source: dict[str, bytes], invert_nm_y: bool = True, log=print):
    """PNG bytes -> {texture path: DDS bytes} + the icon.

    Normal maps are repacked into PD2's packed layout (X in alpha) by
    ``dds.pd2_normal_channels``; ``invert_nm_y`` converts DirectX-style green.
    Diffuse textures receive attenuated specular masks in their alpha channel
    per PAYDAY 2's ``DIFFUSE_TEXTURE:NORMALMAP`` shader convention.
    """
    import dds
    import numpy as np
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Pillow is required to build textures") from exc

    out: dict[str, bytes] = {}
    for mesh_name, (df_png, nm_png, base) in TEXTURE_SLOTS.items():
        for suffix, png in (("df", df_png), ("nm", nm_png)):
            if png is None:
                continue
            path = f"{UNIT_DIR}/{base}_{suffix}.texture"
            if path in out:
                continue
            if png == "__flat__":
                from PIL import Image
                img = Image.new("RGBA", (256, 256), (128, 128, 255, 255))
            else:
                img = Image.open(io.BytesIO(source[png])).convert("RGBA")
            if img.width != img.height or img.width & (img.width - 1):
                raise ValueError(f"{png}: expected square power-of-two, got {img.size}")
            if suffix == "nm":
                nm_in = img
                if png != "__flat__":
                    # UE3/ME2 extracted normal PNGs store vertical Y_down in Red and horizontal X_right in Green
                    nm_in = np.asarray(img, dtype=np.uint8)[..., [1, 0, 2, 3]].copy()
                    if base == "eyes":
                        nm_xy = 128.0 + (nm_in[..., :2].astype(np.float32) - 128.0) * 0.22
                        nm_in[..., :2] = np.clip(np.round(nm_xy), 0, 255).astype(np.uint8)
                arr = dds.pd2_normal_channels(nm_in, invert_y=invert_nm_y)
                mip = dds.mip_payloads_from_image(arr)
            else:
                if base == "eyes" and img.width < 512:
                    img = img.resize((512, 512))
                arr = _prepare_diffuse_rgba(base, img, source)
                mip = dds.mip_payloads_from_image(arr)
            out[path] = dds.pack_dds(mip, img.width)
            problems = dds.validate_dxt5_texture(out[path])
            if problems:
                raise ValueError(f"{path}: {problems}")
        log(f"  texture {base}: ok")
    # menu icon: face diffuse, square 256
    from PIL import Image
    face = Image.open(io.BytesIO(source[TEXTURE_SLOTS["Face"][0]])).convert("RGBA")
    icon = face.resize((256, 256))
    out[f"{GUI_DIR}/lawson.texture"] = dds.pack_dds(dds.mip_payloads_from_image(icon), 256)
    log("  icon: ok")
    return out


def material_config(materials: list[str], unit_base: str, fps: bool = False) -> str:
    """material_config per the ModWorkshop LAS/MOOG guide.

    - header ``group`` (free-form name);
    - TPP materials use the guide's standard ported-model template
      ``CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS`` with
      ``unique="true"`` and the contour variables (without them the
      wall-outline does not render);
    - masked materials (lashes) keep the 2B-attested ALPHA_MASKED template —
      combining CONTOUR with ALPHA_MASKED is not attested and invented
      keyword combinations render black;
    - FPS materials use ``DEPTH_SCALING`` (guide: arms draw in front of world
      geometry) and no contour.
    """
    group = "fps_criminals_suit_lawson" if fps else "lawson"
    lines = [f'<materials version="3" group="{group}">']
    for m in materials:
        if m == "shadow_caster":
            lines.append('    <material name="shadow_caster" '
                         'render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>')
            continue
        extras, has_nm, masked = TEMPLATE[m]
        contour = False
        if masked:
            pass                                    # keep the attested combo as-is
        elif fps:
            extras = extras.replace("DIFFUSE_TEXTURE", "DEPTH_SCALING:DIFFUSE_TEXTURE")
        else:
            extras = "CONTOUR:" + extras
            contour = True
        base = MAT_BASE[m]
        unique = ' unique="true"' if contour else ""
        attrs = (f'name="{m}"{unique} render_template="generic:{extras}" version="2"'
                 if not masked else
                 f'name="{m}" decal_material="steel_no_decal" '
                 f'render_template="generic:{extras}" version="2"')
        lines.append(f"    <material {attrs}>")
        lines.append(f'        <diffuse_texture file="{UNIT_DIR}/{base}_df"/>')
        if has_nm:
            lines.append(f'        <bump_normal_texture file="{UNIT_DIR}/{base}_nm"/>')
        if masked:
            lines.append('        <variable value="0.5" type="scalar" name="alpha_ref"/>')
        if contour:
            lines.append('        <variable value="1 1 1" type="vector3" name="contour_color"/>')
            lines.append('        <variable value="0" type="scalar" name="contour_opacity"/>')
        lines.append("    </material>")
    lines.append("</materials>")
    return "\n".join(lines) + "\n"


def unit_xml(unit_base: str) -> str:
    return ('<?xml version="1.0"?>\n'
            '<unit type="dah" slot="1">\n'
            f'\t<object file="{UNIT_DIR}/{unit_base}" />\n'
            '\n\t<extensions>\n'
            '\t\t<extension name="unit_data" class="ScriptUnitData" />\n'
            '\t\t<extension name="contour" class="ContourExt"/>\n'
            '\t</extensions>\n'
            '</unit>\n')


def object_xml(unit_base: str, drawables: list[str]) -> str:
    objs = "\n".join(f'\t\t\t<object name="{d}" enabled="true" />' for d in drawables)
    return ('<?xml version="1.0"?>\n'
            '<dynamic_object>\n'
            f'\t<diesel materials="{UNIT_DIR}/{unit_base}" orientation_object="root_point" />\n'
            '\n\t<graphics>\n'
            '\t\t<graphic_group name="character" enabled="true" culling_object="c_block">\n'
            f'{objs}\n'
            '\t\t</graphic_group>\n'
            '\t</graphics>\n'
            '</dynamic_object>\n')


def hook_lua() -> str:
    return (
        "LegendaryArmours = LegendaryArmours or {}\n"
        "la = LegendaryArmours\n"
        "\n"
        "la.lawson = {\n"
        '\tcategory = "lawson",\n'
        "\n"
        f'\tunit = "{UNIT_DIR}/lawson",\n'
        f'\tfps_unit = "{UNIT_DIR}/fps_lawson",\n'
        "\n"
        "    hide_mask = true,\n"
        "\n"
        "\thide_armor = true,\n"
        "\treplace_all = true,\n"
        "\n"
        "\tfps_hide_armor = true,\n"
        "\tfps_replace_body = true\n"
        "}\n"
    )


def main_xml() -> str:
    df_nms = [b for _m, (_d, _n, b) in TEXTURE_SLOTS.items() if _n]
    seen: list[str] = []
    for b in df_nms:
        if b not in seen:
            seen.append(b)
    adds = [f'        <texture path="{GUI_DIR}/lawson"/>']
    for b in seen:
        adds.append(f'        <df_nm path="{UNIT_DIR}/{b}"/>')
    adds += [
        f'        <unit_mat path="{UNIT_DIR}/lawson"/>',
        f'        <unit_mat path="{UNIT_DIR}/fps_lawson"/>',
    ]
    return ('<table name="Lawson" image="' + GUI_DIR + '/lawson">\n'
            '\n'
            '    <Localization directory="localization" default="english.txt"/>\n'
            '\n'
            '    <Hooks directory="hooks">\n'
            '        <hook file="lawson.lua" source_file="lib/tweak_data/armorskinstweakdata"/>\n'
            '    </Hooks>\n'
            '\n'
            '    <AddFiles directory="assets">\n'
            '\n'
            + "\n".join(adds) + "\n"
            '\n'
            '    </AddFiles>\n'
            '</table>\n')


def localization() -> str:
    return json.dumps({
        "bm_menu_lawson_armor_skins": "Miranda Lawson",
        "bm_askn_lawson": "Miranda Lawson",
        "bm_askn_lawson_desc": "Miranda Lawson joins the Payday Gang. "
                               "Mass Effect 2 outfit, worn as a Legendary Armour skin.",
    }, indent=2) + "\n"


def credits_txt() -> str:
    return (
        "Miranda Lawson LAS outfit (experimental, unlicensed fan derivative)\n"
        "====================================================================\n"
        "\n"
        "3D model and textures: ripped from Mass Effect 2 (BioWare/EA), supplied\n"
        "via The Models Resource as 'PC / Computer - Mass Effect 2 - Non-Playable\n"
        "Characters - Miranda Lawson (Romance)'. Registration/layout follows the\n"
        "user-supplied 2B Legendary Armour Skins reference pack (2b.rar).\n"
        "\n"
        "Not affiliated with or endorsed by BioWare/EA or Supermassive Games.\n"
        "The model, the textures and the reference pack are not ours to license:\n"
        "this is an unlicensed, non-commercial fan derivative and no\n"
        "redistribution permission is claimed. The original artists and\n"
        "publishers keep all rights to their work.\n"
        "\n"
        "Not game-verified. Build: tools/pd2-port/build_las_pack.py\n"
    )


def assemble(scene, rig, source: dict[str, bytes], invert_nm_y: bool = True,
             log=print) -> dict[str, bytes]:
    tpp_res, fps_res = build_models(scene, rig, log)
    textures = encode_textures(source, invert_nm_y=invert_nm_y, log=log)

    tpp_mats = ["mtr_body1", "mtr_body2", "mtr_face", "mtr_hair", "mtr_eyes",
                "mtr_lashes", "mtr_teeth", "mtr_mouth", "shadow_caster"]
    fps_mats = ["mtr_body1", "mtr_body2", "shadow_caster"]

    files: dict[str, bytes] = {}
    files[f"{ROOT_DIR}/main.xml"] = main_xml().encode()
    files[f"{ROOT_DIR}/hooks/lawson.lua"] = hook_lua().encode()
    files[f"{ROOT_DIR}/localization/english.txt"] = localization().encode()
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/lawson.unit"] = unit_xml("lawson").encode()
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/fps_lawson.unit"] = unit_xml("fps_lawson").encode()
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/lawson.object"] = object_xml(
        "lawson", ["g_body", "g_head"]).encode()
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/fps_lawson.object"] = object_xml(
        "fps_lawson", ["g_body"]).encode()
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/lawson.material_config"] = material_config(
        tpp_mats, "lawson").encode()
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/fps_lawson.material_config"] = material_config(
        fps_mats, "fps_lawson", fps=True).encode()
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/lawson.model"] = tpp_res.data
    files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/fps_lawson.model"] = fps_res.data
    for path, data in textures.items():
        files[f"{ROOT_DIR}/{ASSET_DIR}/{path}"] = data
    files[f"{ROOT_DIR}/CREDITS.txt"] = credits_txt().encode()
    return files


def validate(files: dict[str, bytes], log=print) -> None:
    """Offline invariants: LAS contract shape, XML/model agreement."""
    problems: list[str] = []
    required = [
        f"{ROOT_DIR}/main.xml", f"{ROOT_DIR}/hooks/lawson.lua",
        f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/lawson.model",
        f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/fps_lawson.model",
    ]
    for r in required:
        if r not in files:
            problems.append(f"missing {r}")
    main = files.get(f"{ROOT_DIR}/main.xml", b"").decode()
    for needle in ("LegendaryArmours", 'source_file="lib/tweak_data/armorskinstweakdata"',
                   'directory="hooks"', "<unit_mat", "<df_nm"):
        if needle == "LegendaryArmours":
            continue
        if needle not in main:
            problems.append(f"main.xml lacks {needle!r}")
    hook = files.get(f"{ROOT_DIR}/hooks/lawson.lua", b"").decode()
    for needle in ("la.lawson", "hide_mask", "hide_armor", "replace_all",
                   "fps_hide_armor", "fps_replace_body", "fps_unit"):
        if needle not in hook:
            problems.append(f"hook lacks {needle!r}")
    for cfg_name in (f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/lawson.material_config",
                     f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/fps_lawson.material_config"):
        cfg = files.get(cfg_name, b"").decode()
        if 'name="shadow_caster"' not in cfg:
            problems.append(f"{cfg_name}: no shadow_caster")
    for p in files:
        if p.endswith(".cooked_physics"):
            problems.append(f"{p}: empty cooked_physics should not be shipped (auto_cp)")
    # model <-> material_config coverage
    import re as _re
    m_dir = _re.search(r'<AddFiles\b[^>]*\bdirectory="([^"]*)"', main)
    add_prefix = f"{ROOT_DIR}/{m_dir.group(1).strip('/')}/" if (m_dir and m_dir.group(1).strip("/")) else f"{ROOT_DIR}/"
    for kind, rpath in _re.findall(r'<(texture|df_nm|unit_mat) path="([^"]+)"', main):
        if kind == "texture" and f"{add_prefix}{rpath}.texture" not in files:
            problems.append(f"AddFiles texture missing at {add_prefix}{rpath}.texture")
        elif kind == "df_nm":
            for sfx in ("_df.texture", "_nm.texture"):
                if f"{add_prefix}{rpath}{sfx}" not in files:
                    problems.append(f"AddFiles df_nm missing at {add_prefix}{rpath}{sfx}")
        elif kind == "unit_mat":
            for sfx in (".unit", ".object", ".model", ".material_config"):
                if f"{add_prefix}{rpath}{sfx}" not in files:
                    problems.append(f"AddFiles unit_mat missing at {add_prefix}{rpath}{sfx}")
    for base in ("lawson", "fps_lawson"):
        cfg = files.get(f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/{base}.material_config", b"").decode()
        cfg_mats = set(_re.findall(r'<material name="([^"]+)"', cfg))
        from dmodel import DieselModel
        import tempfile, os
        model = files[f"{ROOT_DIR}/{ASSET_DIR}/{UNIT_DIR}/{base}.model"]
        tmp = tempfile.mktemp(suffix=".model")
        Path(tmp).write_bytes(model)
        try:
            m = DieselModel(tmp)
        finally:
            os.unlink(tmp)
        from dmodel import hash_str
        model_mats = {s.obj.name for s in m.sections if s.tag == "material"}
        # names decode via hashes; compare hash sets instead
        cfg_hashes = {hash_str(n) for n in cfg_mats}
        model_hashes = {int.from_bytes(m.data[s.start:s.start + 8], "little")
                        for s in m.sections if s.tag == "material"}
        if cfg_hashes != model_hashes:
            problems.append(f"{base}: material_config {sorted(cfg_mats)} != model materials")
        # contiguous 1..N section ids
        ids = [s.id for s in m.sections]
        if ids != list(range(1, len(ids) + 1)):
            problems.append(f"{base}: section ids not contiguous 1..N")
    if problems:
        for p in problems:
            log(f"  FAIL: {p}")
        raise SystemExit(f"validation failed with {len(problems)} problem(s)")
    log(f"  validation: {len(files)} files, 0 problems")


def write_zip(files: dict[str, bytes], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])
    tmp.replace(out)


def load_source(zip_path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(zip_path) as z:
        return {Path(n).name: z.read(n) for n in z.namelist() if not n.endswith("/")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=SOURCE_ZIP)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="build in memory and validate; do not write the zip")
    ap.add_argument("--keep-nm-green", action="store_true",
                    help="do not invert the normal-map green channel "
                         "(source is OpenGL-style Y+ already)")
    ap.add_argument("--version", default=VERSION,
                    help=f"version stamped into build_manifest.json (default: {VERSION})")
    args = ap.parse_args()

    print(f"source: {args.source}")
    source = load_source(args.source)
    print(f"  {len(source)} source files")
    scene = load_dae(source[DAE_NAME])
    print(f"  DAE: {len(scene.meshes)} meshes, {len(scene.joints)} joints, "
          f"{scene.up_axis}, unit={scene.unit_scale}")
    rig = rig_target.load_target_rig(RIG_JSON)
    print(f"  rig: {len(rig.entries)} object3Ds, {len(rig.names)} named bones")

    files = assemble(scene, rig, source, invert_nm_y=not args.keep_nm_green)
    validate(files)

    manifest = {
        "version": args.version,
        "status": STATUS,
        "runtime_verified": False,
        "source_zip": args.source.name,
        "source_sha256": sha256(args.source.read_bytes()),
        "dae": DAE_NAME,
        "normal_maps": {"layout": "pd2 (X in alpha)", "invert_green": not args.keep_nm_green},
        "files": {p: sha256(d) for p, d in sorted(files.items())},
    }
    files[f"{ROOT_DIR}/build_manifest.json"] = json.dumps(manifest, indent=1).encode()
    validate(files)

    total = sum(len(d) for d in files.values())
    print(f"payload: {len(files)} files, {total:,} uncompressed bytes")
    if args.check:
        print("check only; zip not written")
        return
    write_zip(files, args.out)
    data = args.out.read_bytes()
    print(f"wrote {args.out} ({len(data):,} bytes, sha256 {sha256(data)})")


if __name__ == "__main__":
    main()
