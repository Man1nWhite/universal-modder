#!/usr/bin/env python3
"""Build two PAYDAY 2 `mod_overrides` head-replacement mods over Joy:

1. `Miranda_L4D2_over_Joy.zip` (and `dist/Miranda_L4D2_over_Joy.zip`):
   Built from the L4D2 Miranda Lawson mod (`l4d2_miranda_lawson_1.zip` / `Miranda_LAS.zip`).
2. `Miranda_Romance_over_Joy.zip` (and `dist/Miranda_Romance_over_Joy.zip`):
   Built from the Mass Effect 2 Romance Miranda Lawson archive
   (`PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip`).

Both packages follow the exact `mod_overrides` structure and Diesel `.model` /
`.material_config` / `.texture` conventions of `Ada Wong over Joy.7z`.
"""
from __future__ import annotations

import io
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-port"))
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402
import dds  # noqa: E402
import diesel_model as dm  # noqa: E402
import me2_dae  # noqa: E402


JOY_UNIT_DIR = "units/pd2_dlc_joy/characters/npc_criminals_joy_1"
JOY_ICON_PATH = "guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture"


def ensure_ada_reference(tmp_dir: Path) -> Path:
    """Extract `Ada Wong over Joy.7z` reference package if not already extracted."""
    ada_root = tmp_dir / "Ada Wong over Joy"
    if (ada_root / JOY_UNIT_DIR / "npc_criminal_joy_1.model").exists():
        return ada_root
    archive = ROOT / "Ada Wong over Joy.7z"
    if not archive.exists():
        raise FileNotFoundError(f"Missing reference archive: {archive}")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["7z", "x", "-y", f"-o{tmp_dir}", str(archive)], check=True)
    return ada_root


def ensure_me2_extracted(tmp_dir: Path) -> Path:
    """Extract the ME2 Romance zip if not already extracted."""
    dae_file = tmp_dir / "Miranda Lawson (Romance) - Adjusted Version.dae"
    if dae_file.exists():
        return tmp_dir
    archive = ROOT / "PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip"
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


def compute_joy_head_weights(verts: np.ndarray) -> tuple[list[tuple[int, ...]], list[tuple[float, ...]]]:
    """Compute continuous 3-bone weights on SkinBones 44 palette ['Spine2', 'Neck', 'Head'].

    - z_eff <= 156.0: 100% Spine2 (slot 0), locking the base of the neck and lower hair tips
      to Joy's hoodie collar (which is weighted to Spine2).
    - z_eff in [156.0, 161.5]: smooth transition from Spine2 (slot 0) to Neck (slot 1).
    - z_eff in [161.5, 166.0]: smooth transition from Neck (slot 1) to Head (slot 2).
    - z_eff >= 166.0: 100% Head (slot 2), keeping the chin, jaw, face, eyes, and eyelashes rigid.
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
        i0, i1, i2 = int(order[0]), int(order[1]), int(order[2])
        w0, w1, w2 = float(row[i0]), float(row[i1]), float(row[i2])
        s = w0 + w1 + w2
        if s > 0:
            w0, w1, w2 = w0 / s, w1 / s, w2 / s
        else:
            i0, i1, i2 = 2, 0, 0
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


def tuck_hair_for_joy_hood(p: np.ndarray) -> np.ndarray:
    """Smoothly tuck lower back/side hair inside Joy's raised hood collar while preserving front locks."""
    p = p.copy()
    z, y, x = p[:, 2], p[:, 1], p[:, 0]
    wz = np.clip((162.5 - z) / 7.5, 0.0, 1.0)
    wy = np.clip((8.5 - y) / 4.5, 0.0, 1.0)
    w = wz * wy
    if (w > 0).any():
        dx, dy = x - 0.0, y - 3.8
        r = np.hypot(dx, dy) + 1e-6
        r_target = np.minimum(r, 5.8 + (1.0 - wz) * 2.5)
        scale_r = (r * (1.0 - w) + r_target * w) / r
        p[:, 0] = dx * scale_r
        p[:, 1] = 3.8 + dy * scale_r
    return p


def extend_scalp_neck_skin_into_collar(
    p: np.ndarray, uv_img: np.ndarray, z_drop: float = 3.8, y_push: float = 2.2
) -> np.ndarray:
    """Smoothly extend the bottom rim of the Scalp_Diff neck-skin cylinder (u < 0.46, v_img > 0.70)
    down into Joy's collar channel (z ~ 153cm, y ~ 9.2..10.4cm) so the entire throat is a single
    seamless mesh with zero horizontal seam."""
    p = p.copy()
    is_neck_skin = (uv_img[:, 0] < 0.46) & (uv_img[:, 1] > 0.70)
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


def map_uv_to_quadrant(uv_img: np.ndarray, qx: int, qy: int) -> np.ndarray:
    """Map top-down image UVs (u_img, v_img) in [0, 1]^2 into quadrant (qx, qy) of a 2x2 atlas,
    returning Diesel Geometry uv0 (u_diesel, v_diesel = 1 - v_img_atlas)."""
    u_clamped = np.clip(uv_img[:, 0] % 1.0, 0.002, 0.998)
    v_clamped = np.clip(uv_img[:, 1] % 1.0, 0.002, 0.998)
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
    tdir = (du1[:, None] * e2 - du2[:, None] * e1) * r[:, None]

    for k in range(3):
        np.add.at(tan_u, tris[:, k], sdir)
        np.add.at(tan_v, tris[:, k], tdir)

    nrm = np.asarray(normals, dtype=np.float64)
    n_norm = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.where(n_norm > 1e-8, nrm / np.maximum(n_norm, 1e-8), np.array([0.0, 1.0, 0.0]))

    # Gram-Schmidt orthonormalize tan_u against nrm
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

    return [tuple(map(float, row)) for row in tv], [tuple(map(float, row)) for row in tu]


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


def patch_joy_model(
    joy_model_path: Path,
    atom0_mesh: dict[str, np.ndarray],
    atom1_mesh: dict[str, np.ndarray],
) -> bytes:
    """Replace `g_head_mask_off` (120 -> 228/229) and `g_head` (121 -> 233/234) in `npc_criminal_joy_1.model`."""
    mf = dm.ModelFile.read(joy_model_path.read_bytes())

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

    pal_idx, pal_w = compute_joy_head_weights(verts_all)
    uvdir_v, uvdir_u = compute_tangents(verts_all, norms_all, uvs_all, tris_all)

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

    new_sections: list[dm.Section] = []
    for s in mf.sections:
        if s.id in (228, 233):
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = len(verts_list)
            dec["verts"] = verts_list
            dec["normals"] = norms_list
            dec["uv0"] = uvs_list
            dec["blendindices"] = pal_idx
            dec["blendweights"] = pal_w
            dec["uvdir_v"] = uvdir_v
            dec["uvdir_u"] = uvdir_u
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id in (229, 234):
            dec = dm.decode_topology(s.payload)
            dec["indices"] = flat_indices
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id in (120, 121):
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = atoms
            dec["bounds_min"] = bmin
            dec["bounds_max"] = bmax
            dec["bounding_radius"] = radius
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        else:
            new_sections.append(s)

    out_mf = dm.ModelFile(new_sections)
    return out_mf.write()


def make_character_icon_dds(ada_icon_path: Path, portrait_rgb: Image.Image) -> bytes:
    """Create a 128x128 uncompressed BGRA8 DDS character icon in PAYDAY 2 high-contrast B&W style."""
    header = ada_icon_path.read_bytes()[:128]
    gray = portrait_rgb.convert("L").resize((128, 128), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.float32)
    # Mask background (very dark pixels in our render [28,30,38] have luminance ~30)
    bg_mask = arr <= 34.0
    # Contrast curve matching Ada Wong over Joy icon
    norm = np.clip((arr - 42.0) / 135.0, 0.0, 1.0)
    contrasted = np.power(norm, 0.85) * 255.0
    contrasted[bg_mask] = 0.0
    # Vignette fade at bottom neck edge
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


def build_l4d2_joy_mod(ada_root: Path, out_zip_paths: list[Path]) -> None:
    """Build Version 1: L4D2 Miranda over Joy (`Miranda_L4D2_over_Joy.zip`)."""
    with zipfile.ZipFile(ROOT / "Miranda_LAS.zip") as zf:
        mir_bytes = zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
        face_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_df.texture"))).convert("RGBA")
        face_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_nm.texture"))).convert("RGBA")
        head_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_head_df.texture"))).convert("RGBA")
        head_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_head_nm.texture"))).convert("RGBA")
        body_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_body_df.texture"))).convert("RGBA")
        body_nm_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_body_nm.texture"))).convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
        eyes_df_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_eyes.texture"))).convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)

    body_df_arr = np.asarray(body_df_im).copy()
    # Inpaint choker shadow on front neck patch of miranda_body_df (u in [0.58, 0.75], v_img in [0.48, 0.56])
    by0, by1 = int(0.48 * body_df_arr.shape[0]), int(0.56 * body_df_arr.shape[0])
    bx0, bx1 = int(0.58 * body_df_arr.shape[1]), int(0.75 * body_df_arr.shape[1])
    bpatch = body_df_arr[by0:by1, bx0:bx1, :3]
    bskin_med = np.median(bpatch[bpatch.mean(axis=2) > 135], axis=0).astype(np.uint8)
    bpatch[bpatch.mean(axis=2) < 130] = bskin_med
    body_df_arr[by0:by1, bx0:bx1, :3] = bpatch

    # Assemble 2048x2048 diffuse & normal atlases:
    # Q00 (top-left): Face, Q10 (top-right): Scalp/Hair/Mouth, Q01 (bottom-left): Neck (body), Q11 (bottom-right): Eyes
    atlas_df = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_df[0:1024, 0:1024] = np.asarray(face_df_im)
    atlas_df[0:1024, 1024:2048] = np.asarray(head_df_im)
    atlas_df[1024:2048, 0:1024] = body_df_arr
    atlas_df[1024:2048, 1024:2048] = np.asarray(eyes_df_im)
    # Keep diffuse alpha low (matte skin/hair specular in Diesel generic:DIFFUSE_TEXTURE:NORMALMAP shader)
    atlas_df[0:1024, 0:1024, 3] = np.minimum(atlas_df[0:1024, 0:1024, 3], 18)
    atlas_df[0:1024, 1024:2048, 3] = 16
    atlas_df[1024:2048, 0:1024, 3] = np.minimum(atlas_df[1024:2048, 0:1024, 3], 18)
    atlas_df[1024:2048, 1024:2048, 3] = 28

    atlas_nm = np.full((2048, 2048, 4), 128, dtype=np.uint8)
    atlas_nm[0:1024, 0:1024] = np.asarray(face_nm_im)
    atlas_nm[0:1024, 1024:2048] = np.asarray(head_nm_im)
    atlas_nm[1024:2048, 0:1024] = np.asarray(body_nm_im)
    # Q11 (eyes): neutral flat DXT5nm normal (128, 128, 128, 128)

    pm_mir = dm.ModelFile.read(mir_bytes)
    md_head = dm.decode_model_data(pm_mir.by_id(94).payload)
    pg_head = dm.decode_passthroughgp(pm_mir.by_id(md_head["passthroughgp"]).payload)
    geo_head = dm.decode_geometry(pm_mir.by_id(pg_head["geometry"]).payload)
    topo_head = np.array(dm.decode_topology(pm_mir.by_id(pg_head["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)

    md_body = dm.decode_model_data(pm_mir.by_id(93).payload)
    pg_body = dm.decode_passthroughgp(pm_mir.by_id(md_body["passthroughgp"]).payload)
    geo_body = dm.decode_geometry(pm_mir.by_id(pg_body["geometry"]).payload)
    topo_body = np.array(dm.decode_topology(pm_mir.by_id(pg_body["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)

    vh = np.asarray(geo_head["verts"], dtype=np.float32)
    nh = np.asarray(geo_head["normals"], dtype=np.float32)
    uvh_img = np.column_stack([np.asarray(geo_head["uv0"])[:, 0], 1.0 - np.asarray(geo_head["uv0"])[:, 1]])

    # Build Atom 0 (Face + Scalp/Mouth + Hair + Neck + Eyes) and Atom 1 (Eyes copy with native [0,1] UVs)
    a0_verts, a0_norms, a0_uvs, a0_tris = [], [], [], []
    a1_verts, a1_norms, a1_uvs, a1_tris = [], [], [], []

    def append_part(target_v, target_n, target_uv, target_t, p, n, uv, t):
        offset = sum(len(x) for x in target_v)
        target_v.append(p)
        target_n.append(n)
        target_uv.append(uv)
        target_t.append(t + offset)

    # Map material_id -> atlas quadrant (qx, qy):
    # mat_id 1 (Face) -> (0, 0)
    # mat_id 2, 3 (Scalp/Mouth, Hair) -> (1, 0)
    # mat_id 0 (Eyes) -> (1, 1) AND Atom 1
    mat_quad = {1: (0, 0), 2: (1, 0), 3: (1, 0), 0: (1, 1)}
    for atom in md_head["atoms"]:
        bv, sl, bi, tc, mid = atom["base_vertex"], atom["slice_len"], atom["base_index"], atom["tri_count"], atom["material_id"]
        p_s = vh[bv : bv + sl].copy()
        n_s = nh[bv : bv + sl].copy()
        uv_s = uvh_img[bv : bv + sl].copy()
        t_s = topo_head[bi // 3 : bi // 3 + tc] - bv
        if mid in (2, 3):
            p_s = extend_scalp_neck_skin_into_collar(p_s, uv_s, z_drop=3.2, y_push=2.0)
            p_s = tuck_hair_for_joy_hood(p_s)
        qx, qy = mat_quad[mid]
        uv_q = map_uv_to_quadrant(uv_s, qx, qy)
        append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p_s, n_s, uv_q, t_s)
        if mid == 0:
            uv_native = np.column_stack([uv_s[:, 0], 1.0 - uv_s[:, 1]]).astype(np.float32)
            append_part(a1_verts, a1_norms, a1_uvs, a1_tris, p_s, n_s, uv_native, t_s)

    atom0_mesh = {
        "verts": np.vstack(a0_verts),
        "normals": np.vstack(a0_norms),
        "uvs": np.vstack(a0_uvs),
        "tris": np.vstack(a0_tris),
    }
    atom1_mesh = {
        "verts": np.vstack(a1_verts),
        "normals": np.vstack(a1_norms),
        "uvs": np.vstack(a1_uvs),
        "tris": np.vstack(a1_tris),
    }

    joy_model_path = ada_root / JOY_UNIT_DIR / "npc_criminal_joy_1.model"
    model_bytes = patch_joy_model(joy_model_path, atom0_mesh, atom1_mesh)

    head_df_dds = encode_rgba_dds(atlas_df)
    head_nm_dds = encode_rgba_dds(atlas_nm)

    eye_512 = eyes_df_im.resize((512, 512), Image.Resampling.LANCZOS)
    eye_512_arr = np.asarray(eye_512).copy()
    eye_512_arr[:, :, 3] = 255
    eyes_df_dds = encode_rgba_dds(eye_512_arr)
    lashes_df_dds = eyes_df_dds
    lashes_op_arr = np.full((512, 512, 4), 255, dtype=np.uint8)
    lashes_op_dds = encode_rgba_dds(lashes_op_arr)

    portrait = render_head_portrait(atom0_mesh, atom1_mesh, atlas_df[:, :, :3], eye_512_arr, alpha_cut=False)
    icon_dds = make_character_icon_dds(ada_root / JOY_ICON_PATH, portrait)

    mtr_cfg = (ada_root / JOY_UNIT_DIR / "mtr_criminal_joy_1.material_config").read_bytes()
    mtr_cc_cfg = (ada_root / JOY_UNIT_DIR / "mtr_criminal_joy_1_cc.material_config").read_bytes()

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
    for zp in out_zip_paths:
        zp.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for k, v in files.items():
                zf.writestr(k, v)
        print(f"Wrote {zp} ({zp.stat().st_size:,} bytes)")


def build_me2_romance_joy_mod(ada_root: Path, me2_dir: Path, out_zip_paths: list[Path]) -> None:
    """Build Version 2: ME2 Romance Miranda over Joy (`Miranda_Romance_over_Joy.zip`)."""
    with zipfile.ZipFile(ROOT / "Miranda_LAS.zip") as zf:
        mir_bytes = zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
    pm_mir = dm.ModelFile.read(mir_bytes)
    md_head = dm.decode_model_data(pm_mir.by_id(94).payload)
    pg_head = dm.decode_passthroughgp(pm_mir.by_id(md_head["passthroughgp"]).payload)
    geo_mir_head = dm.decode_geometry(pm_mir.by_id(pg_head["geometry"]).payload)

    dae_path = me2_dir / "Miranda Lawson (Romance) - Adjusted Version.dae"
    scene = me2_dae.load_dae(dae_path.read_bytes())

    # Compute exact 3D similarity transform from ME2 Face to PD2 Joy/Miranda head space
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

    # Load and prepare ME2 Romance textures
    face_df = np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Face_Diff.png").convert("RGBA")).copy()
    scalp_df = np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Scalp_Diff.png").convert("RGBA")).copy()
    nkd_df = np.asarray(Image.open(me2_dir / "HMF_MIR_NKDa_DIFF.png").convert("RGBA")).copy()
    # Inpaint baked choker shadow on front neck region of NKDa_DIFF
    y0, y1 = int(0.60 * nkd_df.shape[0]), int(0.88 * nkd_df.shape[0])
    x0, x1 = int(0.35 * nkd_df.shape[1]), int(0.60 * nkd_df.shape[1])
    patch = nkd_df[y0:y1, x0:x1, :3]
    skin_med = np.median(patch[patch.mean(axis=2) > 120], axis=0).astype(np.uint8)
    dark_mask = patch.mean(axis=2) < 115
    patch[dark_mask] = skin_med
    nkd_df[y0:y1, x0:x1, :3] = patch

    eyes_df = np.asarray(
        Image.open(me2_dir / "EYE_Diff.png").convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
    ).copy()

    atlas_df = np.zeros((2048, 2048, 4), dtype=np.uint8)
    atlas_df[0:1024, 0:1024] = face_df
    atlas_df[0:1024, 1024:2048] = scalp_df
    atlas_df[1024:2048, 0:1024] = nkd_df
    atlas_df[1024:2048, 1024:2048] = eyes_df
    # Low diffuse alpha for natural matte skin/hair specular in Diesel
    atlas_df[0:1024, 0:1024, 3] = 12
    atlas_df[0:1024, 1024:2048, 3] = 16
    atlas_df[1024:2048, 0:1024, 3] = 12
    atlas_df[1024:2048, 1024:2048, 3] = 28

    face_nm = dds.pd2_normal_channels(np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Face_Norm.png").convert("RGBA")))
    scalp_nm = dds.pd2_normal_channels(np.asarray(Image.open(me2_dir / "HMF_HED_PROMiranda_Scalp_Norm.png").convert("RGBA")))
    nkd_raw_nm = np.asarray(
        Image.open(me2_dir / "HMF_MIR_NKDa_Norm.png").convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
    ).copy()
    # Smooth out the choker groove in the normal map over the front throat patch
    nkd_raw_nm[y0:y1, x0:x1, 0] = 128
    nkd_raw_nm[y0:y1, x0:x1, 1] = 128
    nkd_raw_nm[y0:y1, x0:x1, 2] = 255
    nkd_nm = dds.pd2_normal_channels(nkd_raw_nm)
    eyes_nm = dds.pd2_normal_channels(
        np.asarray(Image.open(me2_dir / "EYE_Lens_Norm.png").convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS))
    )

    atlas_nm = np.full((2048, 2048, 4), 128, dtype=np.uint8)
    atlas_nm[0:1024, 0:1024] = face_nm
    atlas_nm[0:1024, 1024:2048] = scalp_nm
    atlas_nm[1024:2048, 0:1024] = nkd_nm
    atlas_nm[1024:2048, 1024:2048] = eyes_nm

    a0_verts, a0_norms, a0_uvs, a0_tris = [], [], [], []
    a1_verts, a1_norms, a1_uvs, a1_tris = [], [], [], []

    def append_part(target_v, target_n, target_uv, target_t, p, n, uv, t_idx):
        offset = sum(len(x) for x in target_v)
        target_v.append(p)
        target_n.append(n)
        target_uv.append(uv)
        target_t.append(t_idx + offset)

    for m in scene.meshes:
        if m.name == "Body 2":
            continue
        p = xform_p(m.positions)
        n = xform_n(m.normals)
        uv_dae = np.asarray(m.uvs, dtype=np.float32)
        uv_img = np.column_stack([uv_dae[:, 0], 1.0 - uv_dae[:, 1]])
        tris = np.asarray(m.triangles, dtype=np.int32)

        if m.name == "Face":
            append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p, n, map_uv_to_quadrant(uv_img, 0, 0), tris)
        elif m.name in ("Hair", "Teeth", "Mouth Inside"):
            if m.name == "Hair":
                p = extend_scalp_neck_skin_into_collar(p, uv_img, z_drop=4.2, y_push=2.2)
                p = tuck_hair_for_joy_hood(p)
            append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p, n, map_uv_to_quadrant(uv_img, 1, 0), tris)
        elif m.name == "Eyes":
            append_part(a0_verts, a0_norms, a0_uvs, a0_tris, p, n, map_uv_to_quadrant(uv_img, 1, 1), tris)
        elif m.name == "Eyelashes":
            append_part(a1_verts, a1_norms, a1_uvs, a1_tris, p, n, uv_dae, tris)

    atom0_mesh = {
        "verts": np.vstack(a0_verts),
        "normals": np.vstack(a0_norms),
        "uvs": np.vstack(a0_uvs),
        "tris": np.vstack(a0_tris),
    }
    atom1_mesh = {
        "verts": np.vstack(a1_verts),
        "normals": np.vstack(a1_norms),
        "uvs": np.vstack(a1_uvs),
        "tris": np.vstack(a1_tris),
    }

    joy_model_path = ada_root / JOY_UNIT_DIR / "npc_criminal_joy_1.model"
    model_bytes = patch_joy_model(joy_model_path, atom0_mesh, atom1_mesh)

    head_df_dds = encode_rgba_dds(atlas_df)
    head_nm_dds = encode_rgba_dds(atlas_nm)

    lash_rgba = np.asarray(Image.open(me2_dir / "miranda_eyelashes.png").convert("RGBA")).copy()
    eyes_df_dds = encode_rgba_dds(lash_rgba)
    lashes_df_dds = eyes_df_dds
    lash_op = np.zeros_like(lash_rgba)
    lash_op[:, :, 0] = lash_rgba[:, :, 3]
    lash_op[:, :, 1] = lash_rgba[:, :, 3]
    lash_op[:, :, 2] = lash_rgba[:, :, 3]
    lash_op[:, :, 3] = 255
    lashes_op_dds = encode_rgba_dds(lash_op)

    portrait = render_head_portrait(atom0_mesh, atom1_mesh, atlas_df[:, :, :3], lash_rgba, alpha_cut=True)
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
    for zp in out_zip_paths:
        zp.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for k, v in files.items():
                zf.writestr(k, v)
        print(f"Wrote {zp} ({zp.stat().st_size:,} bytes)")


def main() -> None:
    ada_root = ensure_ada_reference(Path("/tmp/ada_joy"))
    me2_dir = ensure_me2_extracted(Path("/tmp/me2_extract"))

    build_l4d2_joy_mod(
        ada_root,
        [
            ROOT / "Miranda_L4D2_over_Joy.zip",
            ROOT / "dist" / "Miranda_L4D2_over_Joy.zip",
        ],
    )
    build_me2_romance_joy_mod(
        ada_root,
        me2_dir,
        [
            ROOT / "Miranda_Romance_over_Joy.zip",
            ROOT / "dist" / "Miranda_Romance_over_Joy.zip",
        ],
    )


if __name__ == "__main__":
    main()
