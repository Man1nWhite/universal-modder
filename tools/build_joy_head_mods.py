#!/usr/bin/env python3
"""Build PAYDAY 2 `mod_overrides` Miranda Lawson head-replacement mods over female heisters:

1. Joy (`npc_criminals_joy_1`):
   - `dist/Miranda_L4D2_over_Joy.zip` (+ `.sha256`)
   - `dist/Miranda_Romance_over_Joy.zip` (+ `.sha256`)
2. Clover (`npc_criminal_female_1` + Safe House `npc_criminal_female_chill`):
   - `dist/Miranda_L4D2_over_Clover.zip` (+ `.sha256`)
   - `dist/Miranda_Romance_over_Clover.zip` (+ `.sha256`)
3. Bonnie (`npc_criminal_bonnie` + Safe House `npc_criminal_bonnie_chill`):
   - `dist/Miranda_L4D2_over_Bonnie.zip` (+ `.sha256`)
   - `dist/Miranda_Romance_over_Bonnie.zip` (+ `.sha256`)
4. Sydney (`npc_criminals_fem_3` / `npc_criminal_sydney`):
   - `dist/Miranda_L4D2_over_Sydney.zip` (+ `.sha256`)
   - `dist/Miranda_Romance_over_Sydney.zip` (+ `.sha256`)

All packages use fixed `2020-01-01 00:00:00` zip timestamps so builds are byte-reproducible.
"""
from __future__ import annotations

import hashlib
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-port"))
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import dds  # noqa: E402
import diesel_model as dm  # noqa: E402
import me2_dae  # noqa: E402


JOY_UNIT_DIR = "units/pd2_dlc_joy/characters/npc_criminals_joy_1"
JOY_ICON_PATH = "guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture"

CLOVER_UNIT_DIR = "units/payday2/characters/npc_criminal_female_1"
CLOVER_TEX_DIR = "units/payday2/characters/shared_textures"
CLOVER_ICON_PATH = "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture"

BONNIE_UNIT_DIR = "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie"
BONNIE_ICON_PATH = "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture"

SYDNEY_UNIT_DIR = "units/pd2_dlc_opera/characters/npc_criminals_fem_3"
SYDNEY_ICON_PATH = "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture"

CHILL_UNIT_DIR = "units/pd2_dlc_chill/characters/shared_character"
FPS_GLOVES_ZIP_PREFIX = "Heister - FPS Gloves in TPS/Heister - FPS Gloves in TPS/"


def ensure_ada_reference(tmp_dir: Path) -> Path:
    """Extract `Ada Wong over Joy.7z` reference package if not already extracted."""
    ada_root = tmp_dir / "Ada Wong over Joy"
    if (ada_root / JOY_UNIT_DIR / "npc_criminal_joy_1.model").exists():
        return ada_root
    archive = ROOT / "references" / "Ada Wong over Joy.7z"
    if not archive.exists():
        raise FileNotFoundError(f"Missing reference archive: {archive}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        import py7zr  # type: ignore

        with py7zr.SevenZipFile(archive, mode="r") as z:
            z.extractall(path=tmp_dir)
    except ImportError:
        subprocess.run(["7z", "x", "-y", f"-o{tmp_dir}", str(archive)], check=True)
    return ada_root


def ensure_me2_extracted(tmp_dir: Path) -> Path:
    """Extract the ME2 Romance zip if not already extracted."""
    dae_file = tmp_dir / "Miranda Lawson (Romance) - Adjusted Version.dae"
    if dae_file.exists():
        return tmp_dir
    archive = ROOT / "models" / "PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip"
    if not archive.exists():
        raise FileNotFoundError(f"Missing ME2 Romance archive: {archive}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(tmp_dir)
    nested = tmp_dir / "Miranda Lawson (Romance)"
    if nested.exists():
        for p in nested.iterdir():
            target = tmp_dir / p.name
            if not target.exists():
                p.rename(target)
    return tmp_dir


def smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def compute_joy_head_weights(
    verts: np.ndarray, bone_offset: int = 0
) -> tuple[list[tuple[int, ...]], list[tuple[float, ...]]]:
    """Compute continuous 3-bone weights on ['Spine2', 'Neck', 'Head'] (+ optional bone_offset).

    - When bone_offset == 0 (Joy): palette is ['Spine2', 'Neck', 'Head'] -> indices (0, 1, 2).
    - When bone_offset == 1 (Clover, Bonnie, Sydney): palette starts with ['Hips', 'Spine2', 'Neck', 'Head', ...]
      -> active indices are (1, 2, 3).
    """
    z = verts[:, 2]
    y = verts[:, 1]
    # Front chin/jaw (y > 9.5) transitions to Head earlier so the jaw is 100% rigid with Head.
    z_eff = z + 3.0 * np.clip((y - 9.5) / 4.5, 0.0, 1.0)

    u1 = smoothstep((z_eff - 156.0) / 5.5)
    u2 = smoothstep((z_eff - 161.5) / 4.5)

    w_spine2 = 1.0 - u1
    w_neck = u1 * (1.0 - u2)
    w_head = u1 * u2

    W = np.stack([w_spine2, w_neck, w_head], axis=1)
    W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-8)

    pal_idx: list[tuple[int, ...]] = []
    pal_w: list[tuple[float, ...]] = []
    for row in W:
        order = np.argsort(-row)
        i0, i1, i2 = int(order[0]) + bone_offset, int(order[1]) + bone_offset, int(order[2]) + bone_offset
        w0, w1, w2 = float(row[order[0]]), float(row[order[1]]), float(row[order[2]])
        s = w0 + w1 + w2
        if s > 0:
            w0, w1, w2 = w0 / s, w1 / s, w2 / s
        else:
            i0, i1, i2 = 2 + bone_offset, 0, 0
            w0, w1, w2 = 1.0, 0.0, 0.0
        if w1 < 1e-5:
            i1 = 0
            w1 = 0.0
        if w2 < 1e-5:
            i2 = 0
            w2 = 0.0
        pal_idx.append((i0, i1, i2, 0))
        pal_w.append((w0, w1, w2))
    return pal_idx, pal_w


def encode_rgba_dds(arr: np.ndarray) -> bytes:
    """Encode a square (N, N, 4) uint8 RGBA array into a mipmapped DXT5 DDS."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    size = int(arr.shape[0])
    assert arr.shape == (size, size, 4), f"Expected square RGBA array, got {arr.shape}"
    return dds.pack_dds(dds.mip_payloads_from_image(arr), size)


def neck_skin_uv_island_mask(uv_img: np.ndarray, tris: np.ndarray | None = None) -> np.ndarray:
    """Select the exact Scalp_Diff neck-skin UV island (u in [0.005, 0.743], v_img in [0.737, 0.995])."""
    if tris is not None and len(tris) > 0:
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
    return (uv_img[:, 0] < 0.75) & (uv_img[:, 1] > 0.82)


def tuck_hair_for_joy_hood(
    p: np.ndarray, uv_img: np.ndarray | None = None, tris: np.ndarray | None = None
) -> np.ndarray:
    """Smoothly tuck lower hair inside Joy's collar while keeping low front locks behind the throat skin."""
    p = p.copy()
    is_hair = np.ones(len(p), dtype=bool)
    if uv_img is not None:
        is_hair = ~neck_skin_uv_island_mask(uv_img, tris)
    if not is_hair.any():
        return p
    zh, yh, xh = p[is_hair, 2], p[is_hair, 1], p[is_hair, 0]
    wz = np.clip((163.8 - zh) / 7.5, 0.0, 1.0)
    if (wz > 0).any():
        dx, dy = xh - 0.0, yh - 2.0
        r = np.hypot(dx, dy) + 1e-6
        r_target = np.minimum(r, 4.8 + (1.0 - wz) * 2.4)
        scale_r = (r * (1.0 - wz) + r_target * wz) / r
        x_new = dx * scale_r
        y_new = 2.0 + dy * scale_r
        w_front_tuck = np.clip((164.0 - zh) / 2.2, 0.0, 1.0)
        y_max_allowed = 4.2 * (1.0 - 0.3 * wz)
        y_new = y_new * (1.0 - w_front_tuck) + np.minimum(y_new, y_max_allowed) * w_front_tuck
        p[is_hair, 0] = x_new
        p[is_hair, 1] = y_new
    return p


def extend_scalp_neck_skin_into_collar(
    p: np.ndarray,
    uv_img: np.ndarray,
    z_drop: float = 3.8,
    y_push: float = 2.2,
    tris: np.ndarray | None = None,
) -> np.ndarray:
    """Smoothly extend the bottom rim of the Scalp_Diff neck-skin cylinder
    down into Joy's collar channel (z ~ 153cm, y ~ 9.2..10.4cm) so the entire throat is a single
    seamless mesh with zero horizontal seam."""
    p = p.copy()
    is_neck_skin = neck_skin_uv_island_mask(uv_img, tris)
    if not is_neck_skin.any():
        return p
    z = p[is_neck_skin, 2]
    y = p[is_neck_skin, 1]
    x = p[is_neck_skin, 0]

    w_bot = np.clip((161.0 - z) / 4.2, 0.0, 1.0)
    w_front = np.clip((y - 3.5) / 3.0, 0.0, 1.0)

    z_new = z - z_drop * (w_bot ** 1.15)
    y_new = y + y_push * w_bot * w_front

    # Keep lower rim strictly inside Joy's outer collar (y <= 10.6, |x| <= 6.2)
    low = z_new < 156.0
    if low.any():
        t_z = np.clip((156.0 - z_new[low]) / 4.5, 0.0, 1.0)
        y_cap = 10.5 + (1.0 - t_z) * 1.5
        y_new[low] = np.minimum(y_new[low], y_cap)
        x_cap = 6.0 + (1.0 - t_z) * 2.2
        x[low] = np.clip(x[low], -x_cap, x_cap)

    p[is_neck_skin, 0] = x
    p[is_neck_skin, 1] = y_new
    p[is_neck_skin, 2] = z_new
    return p


def shape_neck_and_hair_for_suit_collar(
    p: np.ndarray,
    uv_img: np.ndarray,
    z_drop: float = 5.4,
    y_push: float = 3.0,
    x_flare: float = 0.28,
    tris: np.ndarray | None = None,
) -> np.ndarray:
    """Shape the Scalp_Diff neck-skin cylinder and lower hair for Clover, Bonnie, and Sydney's suit collars."""
    p = p.copy()
    is_neck_skin = neck_skin_uv_island_mask(uv_img, tris)
    if is_neck_skin.any():
        z = p[is_neck_skin, 2]
        y = p[is_neck_skin, 1]
        x = p[is_neck_skin, 0]

        w_bot = np.clip((162.0 - z) / 4.5, 0.0, 1.0)
        w_front = np.clip((y - 1.0) / 4.5, 0.0, 1.0)
        w_side = np.clip((np.abs(x) - 1.5) / 3.5, 0.0, 1.0)

        extra_side_drop = 2.0 * w_side * w_bot
        z_new = z - (z_drop * (w_bot ** 1.1) + extra_side_drop)
        y_new = y + y_push * w_bot * w_front
        x_new = x * (1.0 + x_flare * w_bot)

        low = z_new < 157.0
        if low.any():
            t_z = np.clip((157.0 - z_new[low]) / 5.5, 0.0, 1.0)
            y_cap = 10.8 + (1.0 - t_z) * 1.0
            y_new[low] = np.minimum(y_new[low], y_cap)
            y_new[low] = np.maximum(y_new[low], -1.6 - (1.0 - t_z) * 0.6)
            x_cap = 7.2 + (1.0 - t_z) * 0.8
            x_new[low] = np.clip(x_new[low], -x_cap, x_cap)

        p[is_neck_skin, 0] = x_new
        p[is_neck_skin, 1] = y_new
        p[is_neck_skin, 2] = z_new

    is_hair = ~is_neck_skin
    if is_hair.any():
        zh, yh, xh = p[is_hair, 2], p[is_hair, 1], p[is_hair, 0]
        wz = np.clip((163.8 - zh) / 7.5, 0.0, 1.0)
        dx, dy = xh - 0.0, yh - 2.0
        r = np.hypot(dx, dy) + 1e-6
        r_target = np.minimum(r, 4.6 + (1.0 - wz) * 2.4)
        scale_r = (r * (1.0 - wz) + r_target * wz) / r
        x_new = dx * scale_r
        y_new = 2.0 + dy * scale_r
        w_front_tuck = np.clip((164.0 - zh) / 2.2, 0.0, 1.0)
        y_max_allowed = 4.2 * (1.0 - 0.3 * wz)
        y_new = y_new * (1.0 - w_front_tuck) + np.minimum(y_new, y_max_allowed) * w_front_tuck
        p[is_hair, 0] = x_new
        p[is_hair, 1] = y_new
    return p


def repair_skin_and_neck_normals(
    face_p: np.ndarray,
    face_n: np.ndarray,
    face_t: np.ndarray,
    scalp_p: np.ndarray,
    scalp_n: np.ndarray,
    scalp_uv_img: np.ndarray,
    scalp_t: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Repair corrupted cheek/mouth-corner boundary normals and recompute smooth normals on extended neck skin."""
    fn_out = np.asarray(face_n, dtype=np.float64).copy()
    sn_out = np.asarray(scalp_n, dtype=np.float64).copy()
    fp = np.asarray(face_p, dtype=np.float64)
    sp = np.asarray(scalp_p, dtype=np.float64)
    ft = np.asarray(face_t, dtype=np.int32)
    st = np.asarray(scalp_t, dtype=np.int32)

    is_ns = neck_skin_uv_island_mask(scalp_uv_img, st)
    ns_tri_mask = is_ns[st[:, 0]] & is_ns[st[:, 1]] & is_ns[st[:, 2]]
    st_ns = st[ns_tri_mask] + len(fp)

    p_all = np.vstack([fp, sp])
    t_skin = np.vstack([ft, st_ns])
    v0, v1, v2 = p_all[t_skin[:, 0]], p_all[t_skin[:, 1]], p_all[t_skin[:, 2]]
    tri_fn = np.cross(v1 - v0, v2 - v0)
    rounded = np.round(p_all * 100.0).astype(np.int64)
    _, inv = np.unique(rounded, axis=0, return_inverse=True)
    gn_u = np.zeros((inv.max() + 1, 3), dtype=np.float64)
    for k in range(3):
        np.add.at(gn_u, inv[t_skin[:, k]], tri_fn)
    gn_u /= np.maximum(np.linalg.norm(gn_u, axis=1, keepdims=True), 1e-8)
    gn_all = gn_u[inv]
    if float(np.sum(fn_out * gn_all[: len(fp)], axis=1).mean()) < 0.0:
        gn_all = -gn_all

    gn_f = gn_all[: len(fp)]
    gn_s = gn_all[len(fp) :]

    bad_f = np.sum(fn_out * gn_f, axis=1) < 0.75
    fn_out[bad_f] = gn_f[bad_f]

    bad_s = is_ns & (np.sum(sn_out * gn_s, axis=1) < 0.75)
    sn_out[bad_s] = gn_s[bad_s]

    # Smoothly update extended lower neck-skin normals to match the flared collar slope
    if is_ns.any():
        w_ext = np.clip((161.5 - sp[is_ns, 2]) / 2.5, 0.0, 1.0)[:, None]
        blended = sn_out[is_ns] * (1.0 - w_ext) + gn_s[is_ns] * w_ext
        blended /= np.maximum(np.linalg.norm(blended, axis=1, keepdims=True), 1e-8)
        sn_out[is_ns] = blended

    # Weld normals across coincident Face <-> Scalp(neck_skin) seam pairs
    map_f: dict[tuple[int, int, int], list[int]] = {}
    for i, p in enumerate(fp):
        k = (int(round(p[0] * 100.0)), int(round(p[1] * 100.0)), int(round(p[2] * 100.0)))
        map_f.setdefault(k, []).append(i)
    for j in np.nonzero(is_ns)[0]:
        p = sp[j]
        k = (int(round(p[0] * 100.0)), int(round(p[1] * 100.0)), int(round(p[2] * 100.0)))
        if k in map_f:
            f_idxs = map_f[k]
            avg_n = sn_out[j].copy()
            for fi in f_idxs:
                avg_n = avg_n + fn_out[fi]
            avg_n /= max(float(np.linalg.norm(avg_n)), 1e-8)
            sn_out[j] = avg_n
            for fi in f_idxs:
                fn_out[fi] = avg_n

    return fn_out.astype(np.float32), sn_out.astype(np.float32)


def build_crisp_miranda_eye_texture(me2_dir: Path, size: int = 1024) -> np.ndarray:
    """Synthesize a crisp 1024x1024 radially symmetric deep-sapphire Miranda eye texture."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u = (xx + 0.5) / size - 0.5
    v = (yy + 0.5) / size - 0.5
    r = np.hypot(u, v)
    theta = np.arctan2(v, u)

    f1 = np.sin(theta * 58.0 + 0.35 * np.sin(theta * 7.0))
    f2 = np.cos(theta * 94.0 - 0.40 * np.cos(theta * 11.0))
    f3 = np.sin(theta * 142.0 + r * 28.0)
    radial_env = np.clip(1.0 - ((r - 0.142) / 0.072) ** 2, 0.0, 1.0)
    fiber_detail = (0.45 * f1 + 0.35 * f2 + 0.20 * f3) * radial_env

    t_iris = np.clip((r - 0.078) / (0.206 - 0.078), 0.0, 1.0)
    iris_r = 32.0 * (1.0 - t_iris) + 58.0 * t_iris + 22.0 * fiber_detail
    iris_g = 76.0 * (1.0 - t_iris) + 124.0 * t_iris + 34.0 * fiber_detail
    iris_b = 138.0 * (1.0 - t_iris) + 188.0 * t_iris + 44.0 * fiber_detail
    col_ring = np.exp(-((r - 0.116) / 0.020) ** 2)
    iris_r += 18.0 * col_ring * (0.6 + 0.4 * fiber_detail)
    iris_g += 32.0 * col_ring * (0.6 + 0.4 * fiber_detail)
    iris_b += 42.0 * col_ring * (0.6 + 0.4 * fiber_detail)

    lid_ao = (
        np.clip((-v - 0.05) / 0.24, 0.0, 1.0) * 0.22
        + np.clip((v - 0.08) / 0.26, 0.0, 1.0) * 0.18
    )
    iris_rgb = np.stack([iris_r, iris_g, iris_b], axis=-1) * (1.0 - 0.65 * lid_ao[:, :, None])

    limbal_rgb = np.array([12.0, 22.0, 40.0], dtype=np.float32)
    pupil_rgb = np.array([4.0, 5.0, 8.0], dtype=np.float32)

    t_sc = np.clip((r - 0.218) / 0.30, 0.0, 1.0)
    sc_r = (176.0 - 44.0 * t_sc) * (1.0 - lid_ao)
    sc_g = (162.0 - 48.0 * t_sc) * (1.0 - lid_ao)
    sc_b = (156.0 - 50.0 * t_sc) * (1.0 - lid_ao)
    sclera_rgb = np.stack([sc_r, sc_g, sc_b], axis=-1)

    w_pupil = np.clip((0.082 - r) / 0.012, 0.0, 1.0)[:, :, None]
    w_limbal = np.exp(-((r - 0.210) / 0.018) ** 2)[:, :, None]
    w_sclera = np.clip((r - 0.214) / 0.016, 0.0, 1.0)[:, :, None]

    out = iris_rgb * (1.0 - w_limbal) + limbal_rgb * w_limbal
    out = out * (1.0 - w_pupil) + pupil_rgb * w_pupil
    out = out * (1.0 - w_sclera) + sclera_rgb * w_sclera

    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(out, 0.0, 255.0).astype(np.uint8)
    rgba[:, :, 3] = np.where(r < 0.22, 42, 22).astype(np.uint8)
    return rgba


def project_me2_eye_uv_img(positions: np.ndarray) -> np.ndarray:
    """Planar-project eyeball positions into top-down (u_img, v_img) in [0, 1]^2
    centered on the visible eyelid opening (palpebral fissure)."""
    p = np.asarray(positions, dtype=np.float64)
    uv_img = np.full((len(p), 2), 0.5, dtype=np.float32)
    for sign in (-1.0, 1.0):
        mask = (p[:, 0] * sign) > 0.0
        if not mask.any():
            continue
        sub = p[mask]
        cx_bbox = 0.5 * (sub[:, 0].min() + sub[:, 0].max())
        cz_bbox = 0.5 * (sub[:, 2].min() + sub[:, 2].max())
        rx = 0.5 * (sub[:, 0].max() - sub[:, 0].min()) or 1.0
        cx = cx_bbox + sign * 0.14 * rx
        cz = cz_bbox - 0.15 * rx
        scale = 0.45 / rx
        u = np.clip(0.5 - scale * (sub[:, 0] - cx), 0.02, 0.98)
        v_img = np.clip(0.5 - scale * (sub[:, 2] - cz), 0.02, 0.98)
        uv_img[mask, 0] = u.astype(np.float32)
        uv_img[mask, 1] = v_img.astype(np.float32)
    return uv_img


def soften_eyeball_normals(normals: np.ndarray) -> np.ndarray:
    """Soften vertical normal tilt across the recessed 1.5cm eyeball sphere."""
    n = np.asarray(normals, dtype=np.float64).copy()
    n[:, 2] *= 0.45
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-8)
    return n.astype(np.float32)


def map_uv_to_quadrant(uv_img: np.ndarray, qx: int, qy: int) -> np.ndarray:
    """Map top-down image UVs (u_img, v_img) in [0, 1]^2 into quadrant (qx, qy) of a 2x2 atlas,
    returning Diesel Geometry uv0 (u_diesel, v_diesel = 1 - v_img_atlas)."""
    u_clamped = np.clip(uv_img[:, 0], 0.002, 0.998)
    v_clamped = np.clip(uv_img[:, 1], 0.002, 0.998)
    u_atlas = 0.5 * qx + 0.5 * u_clamped
    v_img_atlas = 0.5 * qy + 0.5 * v_clamped
    return np.column_stack([u_atlas, 1.0 - v_img_atlas]).astype(np.float32)


def compute_tangents(
    verts: np.ndarray, normals: np.ndarray, uvs: np.ndarray, tris: np.ndarray
) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Compute orthonormalized tangent (uvdir_u) and bitangent (uvdir_v) per vertex."""
    n_v = len(verts)
    tan_u = np.zeros((n_v, 3), dtype=np.float64)
    tan_v = np.zeros((n_v, 3), dtype=np.float64)

    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    w0 = uvs[tris[:, 0]]
    w1 = uvs[tris[:, 1]]
    w2 = uvs[tris[:, 2]]

    e1 = v1 - v0
    e2 = v2 - v0
    du1 = w1[:, 0] - w0[:, 0]
    dv1 = w1[:, 1] - w0[:, 1]
    du2 = w2[:, 0] - w0[:, 0]
    dv2 = w2[:, 1] - w0[:, 1]

    denom = du1 * dv2 - du2 * dv1
    valid = np.abs(denom) > 1e-8
    r = np.zeros_like(denom)
    r[valid] = 1.0 / denom[valid]

    sdir = (dv2[:, None] * e1 - dv1[:, None] * e2) * r[:, None]
    # Channel 22 (uvdir_v) stores +dP/dv_img = -dP/dv_diesel (p2mt ComputeUvDirections convention)
    tdir = (du2[:, None] * e1 - du1[:, None] * e2) * r[:, None]

    # Weld by (position, uv) when accumulating tangents so shared vertices across
    # corner-split triangles receive smooth area-weighted tangents.
    weld_key = np.hstack([
        np.round(verts * 1000.0).astype(np.int64),
        np.round(uvs * 10000.0).astype(np.int64),
    ])
    _, inv = np.unique(weld_key, axis=0, return_inverse=True)
    n_u = int(inv.max()) + 1
    tu_u = np.zeros((n_u, 3), dtype=np.float64)
    tv_u = np.zeros((n_u, 3), dtype=np.float64)
    for k in range(3):
        np.add.at(tu_u, inv[tris[:, k]], sdir)
        np.add.at(tv_u, inv[tris[:, k]], tdir)
    tan_u = tu_u[inv]
    tan_v = tv_u[inv]

    nrm = np.asarray(normals, dtype=np.float64)
    n_norm = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.where(n_norm > 1e-8, nrm / np.maximum(n_norm, 1e-8), np.array([0.0, 1.0, 0.0]))

    # Gram-Schmidt orthonormalize tan_u and tan_v against nrm
    dot_nu = np.sum(nrm * tan_u, axis=1, keepdims=True)
    tu = tan_u - nrm * dot_nu
    tu_len = np.linalg.norm(tu, axis=1, keepdims=True)
    fallback_u = np.where(np.abs(nrm[:, :1]) < 0.9, np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    fallback_u = fallback_u - nrm * np.sum(nrm * fallback_u, axis=1, keepdims=True)
    fallback_u /= np.maximum(np.linalg.norm(fallback_u, axis=1, keepdims=True), 1e-8)
    tu = np.where(tu_len > 1e-6, tu / np.maximum(tu_len, 1e-6), fallback_u)

    tv = tan_v - nrm * np.sum(nrm * tan_v, axis=1, keepdims=True)
    tv_len = np.linalg.norm(tv, axis=1, keepdims=True)
    fallback_v = np.cross(nrm, tu)
    tv = np.where(tv_len > 1e-6, tv / np.maximum(tv_len, 1e-6), fallback_v)

    return [tuple(map(float, row)) for row in tu], [tuple(map(float, row)) for row in tv]


def deduplicate_mesh(p: np.ndarray, n: np.ndarray, uv: np.ndarray, tris: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Weld identical (position, normal, uv) vertices to avoid 3x triangle-soup vertex bloat."""
    p_f = np.asarray(p, dtype=np.float32)
    n_f = np.asarray(n, dtype=np.float32)
    uv_f = np.asarray(uv, dtype=np.float32)
    t_i = np.asarray(tris, dtype=np.int32)
    key = np.hstack([
        np.round(p_f * 1e4).astype(np.int64),
        np.round(n_f * 1e4).astype(np.int64),
        np.round(uv_f * 1e5).astype(np.int64),
    ])
    _, first_idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    order = np.argsort(first_idx)
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))
    keep = first_idx[order]
    new_tris = remap[inv[t_i]].astype(np.int32)
    return p_f[keep], n_f[keep], uv_f[keep], new_tris


def _prepare_combined_head_arrays(
    atom0_mesh: dict[str, np.ndarray],
    atom1_mesh: dict[str, np.ndarray],
    bone_offset: int,
) -> dict:
    """Deduplicate and pack Atom 0 and Atom 1 into Diesel Geometry/Topology/ModelData arrays."""
    v0, n0, uv0, t0 = deduplicate_mesh(
        atom0_mesh["verts"], atom0_mesh["normals"], atom0_mesh["uvs"], atom0_mesh["tris"]
    )
    v1, n1, uv1, t1 = deduplicate_mesh(
        atom1_mesh["verts"], atom1_mesh["normals"], atom1_mesh["uvs"], atom1_mesh["tris"]
    )

    verts_all = np.vstack([v0, v1])
    norms_all = np.vstack([n0, n1])
    n_len = np.linalg.norm(norms_all, axis=1, keepdims=True)
    norms_all = np.where(n_len > 1e-6, norms_all / np.maximum(n_len, 1e-6), np.array([0.0, 1.0, 0.0], dtype=np.float32))
    uvs_all = np.vstack([uv0, uv1])
    tris_all = np.vstack([t0, t1 + len(v0)])

    pal_idx, pal_w = compute_joy_head_weights(verts_all, bone_offset=bone_offset)
    uvdir_u, uvdir_v = compute_tangents(verts_all, norms_all, uvs_all, tris_all)

    verts_list = [tuple(map(float, row)) for row in verts_all]
    norms_list = [tuple(map(float, row)) for row in norms_all]
    uvs_list = [tuple(map(float, row)) for row in uvs_all]
    flat_indices = [int(i) for tri in tris_all for i in tri]

    atoms = [
        {
            "base_vertex": 0,
            "tri_count": int(len(t0)),
            "base_index": 0,
            "slice_len": int(len(v0)),
            "material_id": 0,
        },
        {
            "base_vertex": int(len(v0)),
            "tri_count": int(len(t1)),
            "base_index": int(len(t0) * 3),
            "slice_len": int(len(v1)),
            "material_id": 1,
        },
    ]
    bmin = tuple(map(float, verts_all.min(axis=0)))
    bmax = tuple(map(float, verts_all.max(axis=0)))
    center = 0.5 * (verts_all.min(axis=0) + verts_all.max(axis=0))
    radius = float(np.linalg.norm(verts_all - center, axis=1).max())
    return {
        "verts": verts_list,
        "normals": norms_list,
        "uv0": uvs_list,
        "blendindices": pal_idx,
        "blendweights": pal_w,
        "uvdir_v": uvdir_v,
        "uvdir_u": uvdir_u,
        "indices": flat_indices,
        "atoms": atoms,
        "bmin": bmin,
        "bmax": bmax,
        "radius": radius,
    }


def patch_joy_model(
    joy_model_path: Path,
    atom0_mesh: dict[str, np.ndarray],
    atom1_mesh: dict[str, np.ndarray],
) -> bytes:
    """Replace `g_head_mask_off` (120 -> 228/229) and `g_head` (121 -> 233/234) in `npc_criminal_joy_1.model`."""
    mf = dm.ModelFile.read(joy_model_path.read_bytes())
    packed = _prepare_combined_head_arrays(atom0_mesh, atom1_mesh, bone_offset=0)

    new_sections: list[dm.Section] = []
    for s in mf.sections:
        if s.id in (228, 233):
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = len(packed["verts"])
            dec["verts"] = packed["verts"]
            dec["normals"] = packed["normals"]
            dec["uv0"] = packed["uv0"]
            dec["blendindices"] = packed["blendindices"]
            dec["blendweights"] = packed["blendweights"]
            dec["uvdir_v"] = packed["uvdir_v"]
            dec["uvdir_u"] = packed["uvdir_u"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id in (229, 234):
            dec = dm.decode_topology(s.payload)
            dec["indices"] = packed["indices"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id in (120, 121):
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = packed["atoms"]
            dec["bounds_min"] = packed["bmin"]
            dec["bounds_max"] = packed["bmax"]
            dec["bounding_radius"] = packed["radius"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        else:
            new_sections.append(s)

    out_mf = dm.ModelFile(new_sections)
    return out_mf.write()


def patch_female_heister_model(
    model_bytes: bytes,
    head_drawables: list[str],
    collapse_drawables: list[str],
    head_mat_name: str,
    hair_mat_name: str,
    packed_head: dict,
) -> bytes:
    """Patch head drawables and collapse legacy hair drawables in Clover, Bonnie, or Sydney `.model`."""
    mf = dm.ModelFile.read(model_bytes)

    mat_by_hash = {
        dm.decode_material(s.payload)["name_hash"]: s.id
        for s in mf.by_type(dm.MATERIAL)
    }
    head_mat_id = mat_by_hash[dm.hash64(head_mat_name)]
    hair_mat_id = mat_by_hash[dm.hash64(hair_mat_name)]

    head_hashes = {dm.hash64(n) for n in head_drawables}
    collapse_hashes = {dm.hash64(n) for n in collapse_drawables}

    head_md_ids: set[int] = set()
    head_geo_ids: set[int] = set()
    head_topo_ids: set[int] = set()
    head_mg_ids: set[int] = set()
    head_sb_ids: set[int] = set()

    col_md_ids: set[int] = set()
    col_geo_ids: set[int] = set()
    col_topo_ids: set[int] = set()
    col_mg_ids: set[int] = set()
    col_sb_ids: set[int] = set()

    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        nh = md.get("name_hash")
        if nh in head_hashes:
            pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            head_md_ids.add(s.id)
            head_geo_ids.add(pg["geometry"])
            head_topo_ids.add(pg["topology"])
            head_mg_ids.add(md["matgroup"])
            head_sb_ids.add(md["skinbones"])
        elif nh in collapse_hashes:
            pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            col_md_ids.add(s.id)
            col_geo_ids.add(pg["geometry"])
            col_topo_ids.add(pg["topology"])
            col_mg_ids.add(md["matgroup"])
            col_sb_ids.add(md["skinbones"])

    # Tiny non-degenerate triangle hidden deep inside the Head bone (0.0, 5.33, 166.76)
    c_verts = [(0.0, 5.33, 166.76), (0.05, 5.33, 166.76), (0.0, 5.38, 166.76)]
    c_norms = [(0.0, 0.0, 1.0)] * 3
    c_uvs = [(0.0, 0.0), (0.01, 0.0), (0.0, 0.01)]
    c_bi = [(1, 0, 0, 0)] * 3
    c_bw = [(1.0, 0.0, 0.0)] * 3
    c_uv_v = [(0.0, 1.0, 0.0)] * 3
    c_uv_u = [(1.0, 0.0, 0.0)] * 3
    c_atoms = [{"base_vertex": 0, "tri_count": 1, "base_index": 0, "slice_len": 3, "material_id": 0}]

    new_sections: list[dm.Section] = []
    for s in mf.sections:
        if s.id in head_geo_ids:
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = len(packed_head["verts"])
            dec["verts"] = packed_head["verts"]
            dec["normals"] = packed_head["normals"]
            dec["uv0"] = packed_head["uv0"]
            dec["blendindices"] = packed_head["blendindices"]
            dec["blendweights"] = packed_head["blendweights"]
            dec["uvdir_v"] = packed_head["uvdir_v"]
            dec["uvdir_u"] = packed_head["uvdir_u"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id in head_topo_ids:
            dec = dm.decode_topology(s.payload)
            dec["indices"] = packed_head["indices"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id in head_md_ids:
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = packed_head["atoms"]
            dec["bounds_min"] = packed_head["bmin"]
            dec["bounds_max"] = packed_head["bmax"]
            dec["bounding_radius"] = packed_head["radius"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        elif s.id in head_mg_ids:
            dec = dm.decode_material_group(s.payload)
            dec["material_ids"] = [head_mat_id, hair_mat_id]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_material_group(dec)))
        elif s.id in head_sb_ids:
            dec = dm.decode_skinbones(s.payload)
            dec["maps"] = [list(range(len(dec["objects"]))) for _ in range(len(packed_head["atoms"]) + 1)]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_skinbones(dec)))
        elif s.id in col_geo_ids:
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = 3
            dec["verts"] = c_verts
            dec["normals"] = c_norms
            dec["uv0"] = c_uvs
            dec["blendindices"] = c_bi
            dec["blendweights"] = c_bw
            dec["uvdir_v"] = c_uv_v
            dec["uvdir_u"] = c_uv_u
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id in col_topo_ids:
            dec = dm.decode_topology(s.payload)
            dec["indices"] = [0, 1, 2]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id in col_md_ids:
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = c_atoms
            dec["bounds_min"] = (0.0, 5.33, 166.76)
            dec["bounds_max"] = (0.05, 5.38, 166.76)
            dec["bounding_radius"] = 0.05
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        elif s.id in col_mg_ids:
            dec = dm.decode_material_group(s.payload)
            dec["material_ids"] = [dec["material_ids"][0]]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_material_group(dec)))
        elif s.id in col_sb_ids:
            dec = dm.decode_skinbones(s.payload)
            dec["maps"] = [list(range(len(dec["objects"]))) for _ in range(2)]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_skinbones(dec)))
        else:
            new_sections.append(s)

    return dm.ModelFile(new_sections).write()


def disable_objects_in_xml(xml_bytes: bytes, obj_names: list[str]) -> bytes:
    """Set enabled=\"false\" on the given <object name=\"...\" .../> entries in a .object XML."""
    text = xml_bytes.decode("utf-8", errors="ignore")
    for name in obj_names:
        pattern = rf'(<object\s+name="{re.escape(name)}"\s+enabled=")true(")'
        text = re.sub(pattern, r"\1false\2", text)
    return text.encode("utf-8")


def patch_clover_material_config(xml_bytes: bytes) -> bytes:
    """Replace mtr_hair_1 in Clover's .material_config with opacity:DIFFUSE_TEXTURE:SKINNED_3WEIGHTS."""
    text = xml_bytes.decode("utf-8", errors="ignore")
    new_hair_1 = (
        '<material name="mtr_hair_1" render_template="opacity:DIFFUSE_TEXTURE:SKINNED_3WEIGHTS" version="2">\n'
        '        <opacity_texture file="units/payday2/characters/shared_textures/npc_female_hair_1_op"/>\n'
        '        <diffuse_texture file="units/payday2/characters/shared_textures/npc_criminal_female_1_hair_df"/>\n'
        "    </material>"
    )
    text = re.sub(
        r'<material\s+[^>]*name="mtr_hair_1"[^>]*>.*?</material>',
        new_hair_1,
        text,
        flags=re.DOTALL,
    )
    return text.encode("utf-8")


def patch_bonnie_material_config(xml_bytes: bytes, alpha_ref: str) -> bytes:
    """Update alpha_ref in Bonnie's mtr_hair material."""
    text = xml_bytes.decode("utf-8", errors="ignore")
    text = text.replace('value="0.050000000745058"', f'value="{alpha_ref}"')
    return text.encode("utf-8")


def patch_sydney_material_config(xml_bytes: bytes, alpha_masked: bool) -> bytes:
    """For ME2 Romance over Sydney, make mtr_hair use ALPHA_MASKED for clean eyelash cutouts."""
    if not alpha_masked:
        return xml_bytes
    text = xml_bytes.decode("utf-8", errors="ignore")
    new_hair = (
        '<material name="mtr_hair" unique="true" version="2" '
        'render_template="generic:ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_3WEIGHTS">\n'
        '        <diffuse_texture file="units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_fem_3_hair_df"/>\n'
        '        <bump_normal_texture file="units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_fem_3_hair_nm"/>\n'
        '        <variable value="0.30" type="scalar" name="alpha_ref"/>\n'
        "    </material>"
    )
    text = re.sub(
        r'<material\s+[^>]*name="mtr_hair"[^>]*>.*?</material>',
        new_hair,
        text,
        flags=re.DOTALL,
    )
    return text.encode("utf-8")


def make_character_icon_dds(ada_icon_path: Path, portrait_rgb: Image.Image) -> bytes:
    """Create a 128x128 uncompressed BGRA8 DDS character icon in PAYDAY 2 high-contrast B&W style."""
    header = ada_icon_path.read_bytes()[:128]
    gray = portrait_rgb.convert("L").resize((128, 128), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.float32)
    bg_mask = arr <= 34.0
    norm = np.clip((arr - 42.0) / 135.0, 0.0, 1.0)
    contrasted = np.power(norm, 0.85) * 255.0
    contrasted[bg_mask] = 0.0
    yy, xx = np.mgrid[0:128, 0:128]
    fade = np.clip((122.0 - yy) / 14.0, 0.0, 1.0)
    val = np.clip(contrasted * fade, 0.0, 255.0).astype(np.uint8)

    bgra = np.zeros((128, 128, 4), dtype=np.uint8)
    bgra[:, :, 0] = val
    bgra[:, :, 1] = val
    bgra[:, :, 2] = val
    bgra[:, :, 3] = 255
    return header + bgra.tobytes()


def render_head_portrait(atom0_mesh: dict, atom1_mesh: dict, atlas_rgb: np.ndarray, atom1_rgba: np.ndarray, alpha_cut: bool) -> Image.Image:
    """Render a front portrait of the head for the character icon."""
    W, H = 256, 256
    img = np.full((H, W, 3), [28, 30, 38], dtype=np.uint8)
    zbuf = np.full((H, W), -1e9, dtype=np.float32)
    light = np.array([0.20, 0.88, 0.42], dtype=np.float32)
    light /= np.linalg.norm(light)
    z_center, scale = 173.5, 9.2

    for m, tex, is_cut in [(atom0_mesh, atlas_rgb, False), (atom1_mesh, atom1_rgba, alpha_cut)]:
        pos = np.asarray(m["verts"], np.float32)
        nrm = np.asarray(m["normals"], np.float32)
        tris = np.asarray(m["tris"], np.int32)
        uv = np.asarray(m["uvs"], np.float32)
        sx = (W * 0.5 + pos[:, 0] * scale).astype(np.float32)
        sy = (H * 0.5 - (pos[:, 2] - z_center) * scale).astype(np.float32)
        py = pos[:, 1]
        shade = np.clip(0.25 + 0.80 * np.maximum(0.0, nrm[:, 0] * light[0] + nrm[:, 1] * light[1] + nrm[:, 2] * light[2]), 0.15, 1.15)
        th, tw = tex.shape[:2]
        for a, b, c in tris:
            x0, x1, x2, y0, y1, y2 = sx[a], sx[b], sx[c], sy[a], sy[b], sy[c]
            ix_min, ix_max = max(0, int(min(x0, x1, x2))), min(W - 1, int(max(x0, x1, x2)) + 1)
            iy_min, iy_max = max(0, int(min(y0, y1, y2))), min(H - 1, int(max(y0, y1, y2)) + 1)
            denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(denom) < 1e-5:
                continue
            inv_d = 1.0 / denom
            for py_i in range(iy_min, iy_max + 1):
                for px_i in range(ix_min, ix_max + 1):
                    w0 = ((y1 - y2) * (px_i - x2) + (x2 - x1) * (py_i - y2)) * inv_d
                    w1 = ((y2 - y0) * (px_i - x2) + (x0 - x2) * (py_i - y2)) * inv_d
                    w2 = 1.0 - w0 - w1
                    if w0 >= -1e-4 and w1 >= -1e-4 and w2 >= -1e-4:
                        z_p = w0 * py[a] + w1 * py[b] + w2 * py[c]
                        if z_p > zbuf[py_i, px_i]:
                            u_p = np.clip(w0 * uv[a, 0] + w1 * uv[b, 0] + w2 * uv[c, 0], 0.0, 1.0)
                            v_img_p = np.clip(1.0 - (w0 * uv[a, 1] + w1 * uv[b, 1] + w2 * uv[c, 1]), 0.0, 1.0)
                            tx_i, ty_i = int(u_p * (tw - 1)), int(v_img_p * (th - 1))
                            if is_cut and tex.shape[2] == 4 and tex[ty_i, tx_i, 3] < 90:
                                continue
                            sh = w0 * shade[a] + w1 * shade[b] + w2 * shade[c]
                            col = np.clip(tex[ty_i, tx_i, :3] * sh, 0, 255).astype(np.uint8)
                            zbuf[py_i, px_i] = z_p
                            img[py_i, px_i] = col
    return Image.fromarray(img)


def prepare_crisp_eyelash_textures(me2_dir: Path) -> tuple[np.ndarray, bytes, bytes]:
    """Load miranda_eyelashes.png and sharpen its alpha mask so semi-transparent strip halos don't smudge the eyelids."""
    lash_rgba = np.asarray(Image.open(me2_dir / "miranda_eyelashes.png").convert("RGBA")).copy()
    a_f = lash_rgba[:, :, 3].astype(np.float32)
    a_sharp = np.clip((a_f - 115.0) / 60.0, 0.0, 1.0) * 255.0
    lash_rgba[:, :, 3] = a_sharp.astype(np.uint8)
    # Soften pure-black (0,0,0) to deep espresso-black (18,14,12) so lashes blend naturally
    lash_rgba[:, :, 0] = 18
    lash_rgba[:, :, 1] = 14
    lash_rgba[:, :, 2] = 12
    lashes_df_dds = encode_rgba_dds(lash_rgba)
    lash_op = np.zeros_like(lash_rgba)
    lash_op[:, :, 0] = lash_rgba[:, :, 3]
    lash_op[:, :, 1] = lash_rgba[:, :, 3]
    lash_op[:, :, 2] = lash_rgba[:, :, 3]
    lash_op[:, :, 3] = 255
    lashes_op_dds = encode_rgba_dds(lash_op)
    return lash_rgba, lashes_df_dds, lashes_op_dds


def find_miranda_las_zip() -> Path:
    for candidate in (
        ROOT / "dist" / "Miranda_LAS.zip",
        ROOT / "build" / "pd2-las" / "Miranda_LAS.zip",
        ROOT / "Miranda_LAS.zip",
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Missing dist/Miranda_LAS.zip (run tools/pd2-las/build_models.py first)")


def write_deterministic_zip(files: dict[str, bytes], out_zip_paths: list[Path]) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for k in sorted(files.keys()):
            zi = zipfile.ZipInfo(filename=k, date_time=(2020, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, files[k], compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    raw = buf.getvalue()
    sha = hashlib.sha256(raw).hexdigest()
    for zp in out_zip_paths:
        zp.parent.mkdir(parents=True, exist_ok=True)
        zp.write_bytes(raw)
        rel = zp.relative_to(ROOT) if zp.is_relative_to(ROOT) else zp
        zp.with_name(f"{zp.name}.sha256").write_text(f"{sha}  {rel.as_posix()}\n", encoding="utf-8")
        print(f"Wrote {zp} ({len(raw):,} bytes, sha256={sha[:16]}…)")


def _emit_female_heister_packages(
    variant_tag: str,
    packed_suit_head: dict,
    head_df_dds: bytes,
    head_nm_dds: bytes,
    sec_df_dds: bytes,
    sec_op_dds: bytes,
    sec_nm_dds: bytes,
    icon_dds: bytes,
    is_romance: bool,
) -> None:
    """Package Clover, Bonnie, and Sydney mod_overrides zips from Heister - FPS Gloves in TPS 2.zip."""
    fps_zip = ROOT / "references" / "Heister - FPS Gloves in TPS 2.zip"
    if not fps_zip.exists():
        return

    with zipfile.ZipFile(fps_zip) as zf:
        # 1. Clover (npc_criminal_female_1 + Safe House chill)
        clover_hair_objs = [
            "g_hair_cloth1",
            "g_hair_cloth2",
            "g_hair_cloth3",
            "g_hair_mask_cloth1",
            "g_hair_mask_cloth2",
            "g_hair_mask_cloth3",
        ]
        clover_heist_model = patch_female_heister_model(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CLOVER_UNIT_DIR}/npc_criminal_female_1.model"),
            head_drawables=["g_head_fem1"],
            collapse_drawables=clover_hair_objs,
            head_mat_name="mtr_head",
            hair_mat_name="mtr_hair_1",
            packed_head=packed_suit_head,
        )
        clover_chill_model = patch_female_heister_model(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/npc_criminal_female_chill.model"),
            head_drawables=["g_head_fem1"],
            collapse_drawables=["g_hair_cloth1", "g_hair_cloth2", "g_hair_cloth3"],
            head_mat_name="mtr_head",
            hair_mat_name="mtr_hair_1",
            packed_head=packed_suit_head,
        )
        clover_obj = disable_objects_in_xml(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CLOVER_UNIT_DIR}/npc_criminal_female_1.object"),
            clover_hair_objs,
        )
        clover_menu_obj = disable_objects_in_xml(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CLOVER_UNIT_DIR}/npc_criminal_female_1_menu.object"),
            clover_hair_objs,
        )
        clover_mtr = patch_clover_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CLOVER_UNIT_DIR}/mtr_fem1.material_config")
        )
        clover_mtr_cc = patch_clover_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CLOVER_UNIT_DIR}/mtr_fem1_cc.material_config")
        )
        clover_chill_mtr = patch_clover_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/mtr_fem1.material_config")
        )
        clover_prefix = f"Miranda {variant_tag} over Clover"
        clover_files = {
            f"{clover_prefix}/{CLOVER_ICON_PATH}": icon_dds,
            f"{clover_prefix}/{CLOVER_UNIT_DIR}/npc_criminal_female_1.model": clover_heist_model,
            f"{clover_prefix}/{CLOVER_UNIT_DIR}/npc_criminal_female_1_menu.model": clover_heist_model,
            f"{clover_prefix}/{CLOVER_UNIT_DIR}/npc_criminal_female_1.object": clover_obj,
            f"{clover_prefix}/{CLOVER_UNIT_DIR}/npc_criminal_female_1_menu.object": clover_menu_obj,
            f"{clover_prefix}/{CLOVER_UNIT_DIR}/mtr_fem1.material_config": clover_mtr,
            f"{clover_prefix}/{CLOVER_UNIT_DIR}/mtr_fem1_cc.material_config": clover_mtr_cc,
            f"{clover_prefix}/{CHILL_UNIT_DIR}/npc_criminal_female_chill.model": clover_chill_model,
            f"{clover_prefix}/{CHILL_UNIT_DIR}/mtr_fem1.material_config": clover_chill_mtr,
            f"{clover_prefix}/{CLOVER_TEX_DIR}/clover_head_df.texture": head_df_dds,
            f"{clover_prefix}/{CLOVER_TEX_DIR}/clover_head_nm.texture": head_nm_dds,
            f"{clover_prefix}/{CLOVER_TEX_DIR}/npc_criminal_female_1_hair_df.texture": sec_df_dds,
            f"{clover_prefix}/{CLOVER_TEX_DIR}/npc_female_hair_1_op.texture": sec_op_dds,
        }
        write_deterministic_zip(clover_files, [ROOT / "dist" / f"Miranda_{variant_tag}_over_Clover.zip"])

        # 2. Bonnie (npc_criminal_bonnie + Safe House chill)
        bonnie_heist_model = patch_female_heister_model(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{BONNIE_UNIT_DIR}/npc_criminal_bonnie.model"),
            head_drawables=["g_head", "g_head_mask_on"],
            collapse_drawables=[],
            head_mat_name="mtr_head",
            hair_mat_name="mtr_hair",
            packed_head=packed_suit_head,
        )
        bonnie_chill_model = patch_female_heister_model(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/npc_criminal_bonnie_chill.model"),
            head_drawables=["g_head"],
            collapse_drawables=[],
            head_mat_name="mtr_head",
            hair_mat_name="mtr_hair",
            packed_head=packed_suit_head,
        )
        bonnie_alpha = "0.30" if is_romance else "0.05"
        bonnie_mtr = patch_bonnie_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{BONNIE_UNIT_DIR}/mtr_bonnie.material_config"), bonnie_alpha
        )
        bonnie_mtr_cc = patch_bonnie_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{BONNIE_UNIT_DIR}/mtr_bonnie_cc.material_config"), bonnie_alpha
        )
        bonnie_chill_mtr = patch_bonnie_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/mtr_bonnie.material_config"), bonnie_alpha
        )
        bonnie_prefix = f"Miranda {variant_tag} over Bonnie"
        bonnie_files = {
            f"{bonnie_prefix}/{BONNIE_ICON_PATH}": icon_dds,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie.model": bonnie_heist_model,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie_menu.model": bonnie_heist_model,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie.object": zf.read(
                f"{FPS_GLOVES_ZIP_PREFIX}{BONNIE_UNIT_DIR}/npc_criminal_bonnie.object"
            ),
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie_menu.object": zf.read(
                f"{FPS_GLOVES_ZIP_PREFIX}{BONNIE_UNIT_DIR}/npc_criminal_bonnie_menu.object"
            ),
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/mtr_bonnie.material_config": bonnie_mtr,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/mtr_bonnie_cc.material_config": bonnie_mtr_cc,
            f"{bonnie_prefix}/{CHILL_UNIT_DIR}/npc_criminal_bonnie_chill.model": bonnie_chill_model,
            f"{bonnie_prefix}/{CHILL_UNIT_DIR}/mtr_bonnie.material_config": bonnie_chill_mtr,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie_head_df.texture": head_df_dds,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie_head_nm.texture": head_nm_dds,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie_hair_df.texture": sec_df_dds,
            f"{bonnie_prefix}/{BONNIE_UNIT_DIR}/npc_criminal_bonnie_hair_nm.texture": sec_nm_dds,
        }
        write_deterministic_zip(bonnie_files, [ROOT / "dist" / f"Miranda_{variant_tag}_over_Bonnie.zip"])

        # 3. Sydney (npc_criminals_fem_3 / npc_criminal_sydney)
        sydney_hair_objs = ["g_hair_mask_off", "g_hair_mask_on"]
        sydney_heist_model = patch_female_heister_model(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{SYDNEY_UNIT_DIR}/npc_criminal_sydney.model"),
            head_drawables=["g_head"],
            collapse_drawables=sydney_hair_objs,
            head_mat_name="mtr_head",
            hair_mat_name="mtr_hair",
            packed_head=packed_suit_head,
        )
        sydney_obj = disable_objects_in_xml(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{SYDNEY_UNIT_DIR}/npc_criminal_sydney.object"),
            sydney_hair_objs,
        )
        sydney_menu_obj = disable_objects_in_xml(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{SYDNEY_UNIT_DIR}/npc_criminal_sydney_menu.object"),
            sydney_hair_objs,
        )
        sydney_mtr = patch_sydney_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{SYDNEY_UNIT_DIR}/mtr_criminal_sydney.material_config"),
            alpha_masked=is_romance,
        )
        sydney_mtr_cc = patch_sydney_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{SYDNEY_UNIT_DIR}/mtr_criminal_sydney_cc.material_config"),
            alpha_masked=is_romance,
        )
        sydney_chill_mtr = patch_sydney_material_config(
            zf.read(f"{FPS_GLOVES_ZIP_PREFIX}{CHILL_UNIT_DIR}/mtr_criminal_sydney.material_config"),
            alpha_masked=is_romance,
        )
        sydney_prefix = f"Miranda {variant_tag} over Sydney"
        sydney_files = {
            f"{sydney_prefix}/{SYDNEY_ICON_PATH}": icon_dds,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_sydney.model": sydney_heist_model,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_sydney_menu.model": sydney_heist_model,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_sydney.object": sydney_obj,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_sydney_menu.object": sydney_menu_obj,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/mtr_criminal_sydney.material_config": sydney_mtr,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/mtr_criminal_sydney_cc.material_config": sydney_mtr_cc,
            f"{sydney_prefix}/{CHILL_UNIT_DIR}/mtr_criminal_sydney.material_config": sydney_chill_mtr,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_fem_3_head_df.texture": head_df_dds,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_fem_3_head_nm.texture": head_nm_dds,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_fem_3_hair_df.texture": sec_df_dds,
            f"{sydney_prefix}/{SYDNEY_UNIT_DIR}/npc_criminal_fem_3_hair_nm.texture": sec_nm_dds,
        }
        write_deterministic_zip(sydney_files, [ROOT / "dist" / f"Miranda_{variant_tag}_over_Sydney.zip"])


def build_l4d2_joy_mod(ada_root: Path, me2_dir: Path, out_zip_paths: list[Path], sec_nm_dds: bytes) -> None:
    """Build Version 1 (L4D2 Miranda) over Joy, Clover, Bonnie, and Sydney."""
    with zipfile.ZipFile(find_miranda_las_zip()) as zf:
        mir_bytes = zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
        face_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_df.texture"))).convert("RGBA")
        face_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_nm.texture"))).convert("RGBA")
        head_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_head_df.texture"))).convert("RGBA")
        head_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_head_nm.texture"))).convert("RGBA")
        body_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_body_df.texture"))).convert("RGBA")
        body_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_body_nm.texture"))).convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)

    body_df_arr = np.asarray(body_df_im).copy()
    by0, by1 = int(0.48 * body_df_arr.shape[0]), int(0.56 * body_df_arr.shape[0])
    bx0, bx1 = int(0.58 * body_df_arr.shape[1]), int(0.75 * body_df_arr.shape[1])
    bpatch = body_df_arr[by0:by1, bx0:bx1, :3]
    bskin_med = np.median(bpatch[bpatch.mean(axis=2) > 135], axis=0).astype(np.uint8)
    bpatch[bpatch.mean(axis=2) < 130] = bskin_med
    body_df_arr[by0:by1, bx0:bx1, :3] = bpatch

    crisp_eye_1024 = build_crisp_miranda_eye_texture(me2_dir, size=1024)

    atlas_df = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_df[0:1024, 0:1024] = np.asarray(face_df_im)
    atlas_df[0:1024, 1024:2048] = np.asarray(head_df_im)
    atlas_df[1024:2048, 0:1024] = body_df_arr
    atlas_df[1024:2048, 1024:2048] = crisp_eye_1024
    atlas_df[0:1024, 0:1024, 3] = np.minimum(atlas_df[0:1024, 0:1024, 3], 18)
    atlas_df[0:1024, 1024:2048, 3] = 16
    atlas_df[1024:2048, 0:1024, 3] = np.minimum(atlas_df[1024:2048, 0:1024, 3], 18)

    atlas_nm = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_nm[:, :] = [255, 128, 0, 128]
    atlas_nm[0:1024, 0:1024] = np.asarray(face_nm_im)
    atlas_nm[0:1024, 1024:2048] = np.asarray(head_nm_im)
    atlas_nm[1024:2048, 0:1024] = np.asarray(body_nm_im)
    atlas_nm[:, :, 0] = 255
    atlas_nm[:, :, 2] = 0

    pm_mir = dm.ModelFile.read(mir_bytes)
    md_head = dm.decode_model_data(pm_mir.by_id(94).payload)
    pg_head = dm.decode_passthroughgp(pm_mir.by_id(md_head["passthroughgp"]).payload)
    geo_head = dm.decode_geometry(pm_mir.by_id(pg_head["geometry"]).payload)
    topo_head = np.array(dm.decode_topology(pm_mir.by_id(pg_head["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)

    vh = np.asarray(geo_head["verts"], dtype=np.float32)
    nh = np.asarray(geo_head["normals"], dtype=np.float32)
    uvh_img = np.column_stack([np.asarray(geo_head["uv0"])[:, 0], 1.0 - np.asarray(geo_head["uv0"])[:, 1]])

    # Fit rigid similarity transform from ME2 Face to L4D2 Face so Atom 1 can carry 3D Eyelashes
    dae_path = me2_dir / "Miranda Lawson (Romance) - Adjusted Version.dae"
    scene = me2_dae.load_dae(dae_path.read_bytes())
    m_me2_face = [m for m in scene.meshes if m.name == "Face"][0]
    m_me2_lashes = [m for m in scene.meshes if m.name == "Eyelashes"][0]
    a3 = md_head["atoms"][3]
    pos_l4d_face = np.asarray(geo_head["verts"], dtype=np.float64)[a3["base_vertex"] : a3["base_vertex"] + a3["slice_len"]]
    uv_l4d_face = np.asarray(geo_head["uv0"], dtype=np.float64)[a3["base_vertex"] : a3["base_vertex"] + a3["slice_len"]]
    pos_me2_face = np.asarray(m_me2_face.positions, dtype=np.float64)
    uv_me2_face = np.asarray(m_me2_face.uvs, dtype=np.float64)

    dists = np.linalg.norm(uv_l4d_face[:, None, :] - uv_me2_face[None, :, :], axis=2)
    nearest = dists.argmin(axis=1)
    P_src, P_tgt = pos_me2_face[nearest], pos_l4d_face
    mu_s, mu_t = P_src.mean(axis=0), P_tgt.mean(axis=0)
    U, S, Vt = np.linalg.svd((P_tgt - mu_t).T @ (P_src - mu_s))
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt
    scale = float(np.sum(S) / np.sum((P_src - mu_s) ** 2))
    t_vec = mu_t - scale * (R @ mu_s)
    lash_p = ((scale * (R @ np.asarray(m_me2_lashes.positions, dtype=np.float64).T)).T + t_vec).astype(np.float32)
    lash_n = (R @ np.asarray(m_me2_lashes.normals, dtype=np.float64).T).T.astype(np.float32)
    lash_uv = np.asarray(m_me2_lashes.uvs, dtype=np.float32)
    lash_tris = np.asarray(m_me2_lashes.triangles, dtype=np.int32)

    def build_l4d2_meshes(for_suit: bool) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        a0_verts, a0_norms, a0_uvs, a0_tris = [], [], [], []

        def append_part(target_v, target_n, target_uv, target_t, p, n, uv, t):
            offset = sum(len(x) for x in target_v)
            target_v.append(p)
            target_n.append(n)
            target_uv.append(uv)
            target_t.append(t + offset)

        # Extract Face (Atom 3, mid==1) and Scalp/Neck (Atom 4, mid==2) first so we can repair seam normals
        atoms_by_mid: dict[int, list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = {}
        for atom in md_head["atoms"]:
            bv, sl, bi, tc, mid = atom["base_vertex"], atom["slice_len"], atom["base_index"], atom["tri_count"], atom["material_id"]
            p_s = vh[bv : bv + sl].copy()
            n_s = nh[bv : bv + sl].copy()
            uv_s = uvh_img[bv : bv + sl].copy()
            t_s = topo_head[bi // 3 : bi // 3 + tc] - bv
            if mid in (2, 3):
                if for_suit:
                    p_s = shape_neck_and_hair_for_suit_collar(p_s, uv_s, z_drop=5.4, y_push=3.0, x_flare=0.28, tris=t_s)
                else:
                    p_s = extend_scalp_neck_skin_into_collar(p_s, uv_s, z_drop=3.2, y_push=2.0, tris=t_s)
                    p_s = tuck_hair_for_joy_hood(p_s, uv_s, tris=t_s)
            elif mid == 0:
                uv_s = project_me2_eye_uv_img(p_s)
                n_s = soften_eyeball_normals(n_s)
            atoms_by_mid.setdefault(mid, []).append((p_s, n_s, uv_s, t_s))

        face_p, face_n, face_uv, face_t = atoms_by_mid[1][0]
        scalp_p, scalp_n, scalp_uv, scalp_t = atoms_by_mid[2][0]
        face_n, scalp_n = repair_skin_and_neck_normals(
            face_p, face_n, face_t, scalp_p, scalp_n, scalp_uv, scalp_t
        )
        atoms_by_mid[1][0] = (face_p, face_n, face_uv, face_t)
        atoms_by_mid[2][0] = (scalp_p, scalp_n, scalp_uv, scalp_t)

        mat_quad = {1: (0, 0), 2: (1, 0), 3: (1, 0), 0: (1, 1)}
        for mid in (3, 0, 1, 2):
            qx, qy = mat_quad[mid]
            for p_s, n_s, uv_s, t_s in atoms_by_mid.get(mid, []):
                uv_q = map_uv_to_quadrant(uv_s, qx, qy)
                append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p_s, n_s, uv_q, t_s)

        return (
            {
                "verts": np.vstack(a0_verts),
                "normals": np.vstack(a0_norms),
                "uvs": np.vstack(a0_uvs),
                "tris": np.vstack(a0_tris),
            },
            {
                "verts": lash_p.copy(),
                "normals": lash_n.copy(),
                "uvs": lash_uv.copy(),
                "tris": lash_tris.copy(),
            },
        )

    atom0_joy, atom1_joy = build_l4d2_meshes(for_suit=False)
    atom0_suit, atom1_suit = build_l4d2_meshes(for_suit=True)
    packed_suit_head = _prepare_combined_head_arrays(atom0_suit, atom1_suit, bone_offset=1)

    joy_model_path = ada_root / JOY_UNIT_DIR / "npc_criminal_joy_1.model"
    model_bytes = patch_joy_model(joy_model_path, atom0_joy, atom1_joy)

    head_df_dds = encode_rgba_dds(atlas_df)
    head_nm_dds = encode_rgba_dds(atlas_nm)

    lash_rgba, lashes_df_dds, lashes_op_dds = prepare_crisp_eyelash_textures(me2_dir)
    eyes_df_dds = lashes_df_dds

    portrait = render_head_portrait(atom0_joy, atom1_joy, atlas_df[:, :, :3], lash_rgba, alpha_cut=True)
    icon_dds = make_character_icon_dds(ada_root / JOY_ICON_PATH, portrait)

    mtr_cfg = (
        (ada_root / JOY_UNIT_DIR / "mtr_criminal_joy_1.material_config")
        .read_text(encoding="utf-8")
        .replace('value="0.042000003159046"', 'value="0.30"')
        .encode("utf-8")
    )
    mtr_cc_cfg = (
        (ada_root / JOY_UNIT_DIR / "mtr_criminal_joy_1_cc.material_config")
        .read_text(encoding="utf-8")
        .replace('value="0.042000003159046"', 'value="0.30"')
        .encode("utf-8")
    )

    prefix = "Miranda L4D2 over Joy"
    files = {
        f"{prefix}/{JOY_ICON_PATH}": icon_dds,
        f"{prefix}/{JOY_UNIT_DIR}/mtr_criminal_joy_1.material_config": mtr_cfg,
        f"{prefix}/{JOY_UNIT_DIR}/mtr_criminal_joy_1_cc.material_config": mtr_cc_cfg,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1.model": model_bytes,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_menu.model": model_bytes,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_head_df.texture": head_df_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_head_nm.texture": head_nm_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_eyes_df.texture": eyes_df_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_lashes_df.texture": lashes_df_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_lashes_op.texture": lashes_op_dds,
    }
    write_deterministic_zip(files, out_zip_paths)

    _emit_female_heister_packages(
        variant_tag="L4D2",
        packed_suit_head=packed_suit_head,
        head_df_dds=head_df_dds,
        head_nm_dds=head_nm_dds,
        sec_df_dds=eyes_df_dds,
        sec_op_dds=lashes_op_dds,
        sec_nm_dds=sec_nm_dds,
        icon_dds=icon_dds,
        is_romance=True,
    )


def build_me2_romance_joy_mod(ada_root: Path, me2_dir: Path, out_zip_paths: list[Path], sec_nm_dds: bytes) -> None:
    """Build Version 2 (ME2 Romance Miranda) over Joy, Clover, Bonnie, and Sydney."""
    with zipfile.ZipFile(find_miranda_las_zip()) as zf:
        mir_bytes = zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
    pm_mir = dm.ModelFile.read(mir_bytes)
    md_head = dm.decode_model_data(pm_mir.by_id(94).payload)
    pg_head = dm.decode_passthroughgp(pm_mir.by_id(md_head["passthroughgp"]).payload)
    geo_mir_head = dm.decode_geometry(pm_mir.by_id(pg_head["geometry"]).payload)

    dae_path = me2_dir / "Miranda Lawson (Romance) - Adjusted Version.dae"
    scene = me2_dae.load_dae(dae_path.read_bytes())

    m_me2_face = [m for m in scene.meshes if m.name == "Face"][0]
    a3 = md_head["atoms"][3]
    pos_l4d_face = np.asarray(geo_mir_head["verts"], dtype=np.float64)[a3["base_vertex"] : a3["base_vertex"] + a3["slice_len"]]
    uv_l4d_face = np.asarray(geo_mir_head["uv0"], dtype=np.float64)[a3["base_vertex"] : a3["base_vertex"] + a3["slice_len"]]
    pos_me2_face = np.asarray(m_me2_face.positions, dtype=np.float64)
    uv_me2_face = np.asarray(m_me2_face.uvs, dtype=np.float64)

    dists = np.linalg.norm(uv_l4d_face[:, None, :] - uv_me2_face[None, :, :], axis=2)
    nearest = dists.argmin(axis=1)
    P_src, P_tgt = pos_me2_face[nearest], pos_l4d_face
    mu_s, mu_t = P_src.mean(axis=0), P_tgt.mean(axis=0)
    U, S, Vt = np.linalg.svd((P_tgt - mu_t).T @ (P_src - mu_s))
    R = U @ Vt
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1
        R = U @ Vt
    scale = float(np.sum(S) / np.sum((P_src - mu_s) ** 2))
    t = mu_t - scale * (R @ mu_s)

    def xform_p(pts: np.ndarray) -> np.ndarray:
        return ((scale * (R @ np.asarray(pts, dtype=np.float64).T)).T + t).astype(np.float32)

    def xform_n(nrm: np.ndarray) -> np.ndarray:
        return (R @ np.asarray(nrm, dtype=np.float64).T).T.astype(np.float32)

    face_df = np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Face_Diff.png").convert("RGBA")).copy()
    scalp_df = np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Scalp_Diff.png").convert("RGBA")).copy()
    nkd_df = np.asarray(Image.open(me2_dir / "HMF_MIR_NKDa_DIFF.png").convert("RGBA")).copy()
    y0, y1 = int(0.60 * nkd_df.shape[0]), int(0.88 * nkd_df.shape[0])
    x0, x1 = int(0.35 * nkd_df.shape[1]), int(0.60 * nkd_df.shape[1])
    patch = nkd_df[y0:y1, x0:x1, :3]
    skin_med = np.median(patch[patch.mean(axis=2) > 120], axis=0).astype(np.uint8)
    dark_mask = patch.mean(axis=2) < 115
    patch[dark_mask] = skin_med
    nkd_df[y0:y1, x0:x1, :3] = patch

    eyes_df = build_crisp_miranda_eye_texture(me2_dir, size=1024)

    atlas_df = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_df[0:1024, 0:1024] = face_df
    atlas_df[0:1024, 1024:2048] = scalp_df
    atlas_df[1024:2048, 0:1024] = nkd_df
    atlas_df[1024:2048, 1024:2048] = eyes_df
    atlas_df[0:1024, 0:1024, 3] = 12
    atlas_df[0:1024, 1024:2048, 3] = 16
    atlas_df[1024:2048, 0:1024, 3] = 12

    # UE3/ME2 extracted normal PNGs store vertical Y_down in Red and horizontal X_right in Green
    face_raw_nm = np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Face_Norm.png").convert("RGBA"))[..., [1, 0, 2, 3]]
    scalp_raw_nm = np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Scalp_Norm.png").convert("RGBA"))[..., [1, 0, 2, 3]]
    face_nm = dds.pd2_normal_channels(face_raw_nm)
    scalp_nm = dds.pd2_normal_channels(scalp_raw_nm)
    nkd_raw_nm = np.asarray(
        Image.open(me2_dir / "HMF_MIR_NKDa_Norm.png").convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
    )[..., [1, 0, 2, 3]].copy()
    nkd_raw_nm[y0:y1, x0:x1, 0] = 128
    nkd_raw_nm[y0:y1, x0:x1, 1] = 128
    nkd_raw_nm[y0:y1, x0:x1, 2] = 255
    nkd_nm = dds.pd2_normal_channels(nkd_raw_nm)

    atlas_nm = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_nm[:, :] = [255, 128, 0, 128]
    atlas_nm[0:1024, 0:1024] = face_nm
    atlas_nm[0:1024, 1024:2048] = scalp_nm
    atlas_nm[1024:2048, 0:1024] = nkd_nm

    def build_romance_meshes(for_suit: bool) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        a0_verts, a0_norms, a0_uvs, a0_tris = [], [], [], []
        a1_verts, a1_norms, a1_uvs, a1_tris = [], [], [], []

        def append_part(target_v, target_n, target_uv, target_t, p, n, uv, t_idx):
            offset = sum(len(x) for x in target_v)
            target_v.append(p)
            target_n.append(n)
            target_uv.append(uv)
            target_t.append(t_idx + offset)

        parts: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        for m in scene.meshes:
            if m.name in ("Body 1", "Body 2"):
                continue
            p = xform_p(m.positions)
            n = xform_n(m.normals)
            uv_dae = np.asarray(m.uvs, dtype=np.float32)
            uv_img = np.column_stack([uv_dae[:, 0], 1.0 - uv_dae[:, 1]])
            tris = np.asarray(m.triangles, dtype=np.int32)
            if m.name == "Hair":
                if for_suit:
                    p = shape_neck_and_hair_for_suit_collar(p, uv_img, z_drop=5.6, y_push=3.0, x_flare=0.28, tris=tris)
                else:
                    p = extend_scalp_neck_skin_into_collar(p, uv_img, z_drop=4.2, y_push=2.2, tris=tris)
                    p = tuck_hair_for_joy_hood(p, uv_img, tris=tris)
            parts[m.name] = (p, n, uv_dae, uv_img, tris)

        fp, fn, f_uv_dae, f_uv_img, ft = parts["Face"]
        hp, hn, h_uv_dae, h_uv_img, ht = parts["Hair"]
        fn, hn = repair_skin_and_neck_normals(fp, fn, ft, hp, hn, h_uv_img, ht)
        parts["Face"] = (fp, fn, f_uv_dae, f_uv_img, ft)
        parts["Hair"] = (hp, hn, h_uv_dae, h_uv_img, ht)

        for name in ("Eyes", "Eyelashes", "Hair", "Face", "Mouth Inside", "Teeth"):
            if name not in parts:
                continue
            p, n, uv_dae, uv_img, tris = parts[name]
            if name == "Face":
                append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p, n, map_uv_to_quadrant(uv_img, 0, 0), tris)
            elif name in ("Hair", "Teeth", "Mouth Inside"):
                append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p, n, map_uv_to_quadrant(uv_img, 1, 0), tris)
            elif name == "Eyes":
                uv_eye_img = project_me2_eye_uv_img(p)
                n_eye = soften_eyeball_normals(n)
                append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p, n_eye, map_uv_to_quadrant(uv_eye_img, 1, 1), tris)
            elif name == "Eyelashes":
                append_part(a1_verts, a1_norms, a1_uvs, a1_tris, p, n, uv_dae, tris)

        return (
            {
                "verts": np.vstack(a0_verts),
                "normals": np.vstack(a0_norms),
                "uvs": np.vstack(a0_uvs),
                "tris": np.vstack(a0_tris),
            },
            {
                "verts": np.vstack(a1_verts),
                "normals": np.vstack(a1_norms),
                "uvs": np.vstack(a1_uvs),
                "tris": np.vstack(a1_tris),
            },
        )

    atom0_joy, atom1_joy = build_romance_meshes(for_suit=False)
    atom0_suit, atom1_suit = build_romance_meshes(for_suit=True)
    packed_suit_head = _prepare_combined_head_arrays(atom0_suit, atom1_suit, bone_offset=1)

    joy_model_path = ada_root / JOY_UNIT_DIR / "npc_criminal_joy_1.model"
    model_bytes = patch_joy_model(joy_model_path, atom0_joy, atom1_joy)

    head_df_dds = encode_rgba_dds(atlas_df)
    head_nm_dds = encode_rgba_dds(atlas_nm)

    lash_rgba, lashes_df_dds, lashes_op_dds = prepare_crisp_eyelash_textures(me2_dir)
    eyes_df_dds = lashes_df_dds

    portrait = render_head_portrait(atom0_joy, atom1_joy, atlas_df[:, :, :3], lash_rgba, alpha_cut=True)
    icon_dds = make_character_icon_dds(ada_root / JOY_ICON_PATH, portrait)

    mtr_cfg = (
        (ada_root / JOY_UNIT_DIR / "mtr_criminal_joy_1.material_config")
        .read_text(encoding="utf-8")
        .replace('value="0.042000003159046"', 'value="0.30"')
        .encode("utf-8")
    )
    mtr_cc_cfg = (
        (ada_root / JOY_UNIT_DIR / "mtr_criminal_joy_1_cc.material_config")
        .read_text(encoding="utf-8")
        .replace('value="0.042000003159046"', 'value="0.30"')
        .encode("utf-8")
    )

    prefix = "Miranda Romance over Joy"
    files = {
        f"{prefix}/{JOY_ICON_PATH}": icon_dds,
        f"{prefix}/{JOY_UNIT_DIR}/mtr_criminal_joy_1.material_config": mtr_cfg,
        f"{prefix}/{JOY_UNIT_DIR}/mtr_criminal_joy_1_cc.material_config": mtr_cc_cfg,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1.model": model_bytes,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_menu.model": model_bytes,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_head_df.texture": head_df_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_head_nm.texture": head_nm_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_eyes_df.texture": eyes_df_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_lashes_df.texture": lashes_df_dds,
        f"{prefix}/{JOY_UNIT_DIR}/npc_criminal_joy_1_lashes_op.texture": lashes_op_dds,
    }
    write_deterministic_zip(files, out_zip_paths)

    _emit_female_heister_packages(
        variant_tag="Romance",
        packed_suit_head=packed_suit_head,
        head_df_dds=head_df_dds,
        head_nm_dds=head_nm_dds,
        sec_df_dds=eyes_df_dds,
        sec_op_dds=lashes_op_dds,
        sec_nm_dds=sec_nm_dds,
        icon_dds=icon_dds,
        is_romance=True,
    )


def main() -> None:
    ada_root = ensure_ada_reference(Path("/tmp/ada_joy"))
    me2_dir = ensure_me2_extracted(Path("/tmp/me2_extract"))
    flat_nm = np.zeros((512, 512, 4), dtype=np.uint8)
    flat_nm[:, :] = [255, 128, 0, 128]
    sec_nm_dds = encode_rgba_dds(flat_nm)

    build_l4d2_joy_mod(
        ada_root,
        me2_dir,
        [ROOT / "dist" / "Miranda_L4D2_over_Joy.zip"],
        sec_nm_dds=sec_nm_dds,
    )
    build_me2_romance_joy_mod(
        ada_root,
        me2_dir,
        [ROOT / "dist" / "Miranda_Romance_over_Joy.zip"],
        sec_nm_dds=sec_nm_dds,
    )


if __name__ == "__main__":
    main()
