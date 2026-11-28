#!/usr/bin/env python3
"""Render high-resolution PNG preview sheets for every PAYDAY 2 mod package in `dist/`.

By default outputs to `build/previews/` (gitignored scratch). Pass `--unified` to emit into
`docs/renders/<project>/model/...` per `docs/renders/README.md`:
  - `00_all_dist_mods_overview.png` (grid of every pack in `dist/`)
  - `01_Miranda_LAS.png`
  - `11_Geralt_over_Rust.png`
  - `19_Miranda_L4D2_over_Hila.png`
  - `24_OfficeSuite.png` (the 5% slim outfit in the user's third suit & jewelry colourway, palms cut on the line where they begin, no extension past it (D70), the wrist twisting on ForeArmRoll (D75), plus the first-person arms panel)
  - `25_OfficeSuite_over_Bunny.png` (native `mod_overrides` replacement of Hop to It / `bunny`, 6-tile BC3 atlas + FPS arms)
  - `30_Arivus_over_Hoxton.png` (GTA SA Arivus head over Old Hoxton, FPS gloves in TPS)
  - `31`/`35`/`36` `*_fps.png` (first-person `fps_*.model` / `ccmt_acc_fps_bunny_male.model` sheets —
    Miranda_L4D2_LAS, OfficeSuite, and OfficeSuite_over_Bunny — player, three-quarter, side and top-down views, auto-framed)
  - `37_OfficeSuite_wrist.png` (the D75 wrist junction)

The sheets of the retired packs (Joy, Clover, Bonnie, Sydney, Busty, Christie, and the ME2
Romance line — `Miranda_Romance_LAS`, `Miranda_Romance_over_Hila`, `OfficeSuite_Head`, D83) stay
in `docs/renders/` as history; this script no longer renders them because the packs are gone.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import sys as _dist_sys
_dist_sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "pd2-las"))
from dist_paths import dist_path  # noqa: E402

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
sys.path.insert(0, str(ROOT / "tools" / "pd2-port"))

import diesel_model as dm  # noqa: E402

FONT_BOLD_16 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
FONT_BOLD_13 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
FONT_REG_12 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
FONT_REG_11 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)


def view_rotation(deg: float, pitch_deg: float = 0.0) -> np.ndarray:
    """Yaw-then-pitch rotation shared by the rasterizer and the auto-framing helper."""
    rad = np.deg2rad(deg)
    c, s = np.cos(rad), np.sin(rad)
    Rz = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    if abs(pitch_deg) > 1e-4:
        prad = np.deg2rad(pitch_deg)
        cp, sp = np.cos(prad), np.sin(prad)
        Rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        return Rx @ Rz
    return Rz


def fit_view(
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool, bool]],
    W: int,
    H: int,
    deg: float,
    pitch_deg: float = 0.0,
    *,
    margin: float = 0.9,
    pad: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[float, float, float]:
    """Frame `parts` in one view: returns ``(pan_x, z_center, scale)`` for the rasterizer.

    The bounds come from the rotated vertices, so a pitched view of a horizontal
    subject (first-person arms) lands centred instead of drifting out of frame as a
    fixed ``z_center``/``scale`` pair does. ``pad`` is (left, right, top, bottom) in
    output pixels and reserves room for the caption.
    """
    visible = [p for p in parts if len(p[2])]
    if not visible:
        return 0.0, 0.0, 1.0
    verts = np.concatenate([p[0] for p in visible])
    rotated = verts @ view_rotation(deg, pitch_deg).T
    xmin, xmax = float(rotated[:, 0].min()), float(rotated[:, 0].max())
    zmin, zmax = float(rotated[:, 2].min()), float(rotated[:, 2].max())
    left, right, top, bottom = pad
    avail_w = max(1.0, (W - left - right) * margin)
    avail_h = max(1.0, (H - top - bottom) * margin)
    scale = min(avail_w / max(xmax - xmin, 1e-3), avail_h / max(zmax - zmin, 1e-3))
    area_cx = left + (W - left - right) * 0.5
    area_cy = top + (H - top - bottom) * 0.5
    pan_x = (xmin + xmax) * 0.5 - (area_cx - W * 0.5) / scale
    z_center = (zmin + zmax) * 0.5 - (H * 0.5 - area_cy) / scale
    return pan_x, z_center, scale


def rasterize_fitted(
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool, bool]],
    W: int,
    H: int,
    deg: float,
    pitch_deg: float = 0.0,
    *,
    margin: float = 0.9,
    pad: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> Image.Image:
    """`rasterize_parts` with the camera framed on the subject instead of fixed numbers."""
    pan_x, z_center, scale = fit_view(parts, W, H, deg, pitch_deg, margin=margin, pad=pad)
    return rasterize_parts(parts, W, H, deg, z_center, scale, pitch_deg=pitch_deg, pan_x=pan_x)


def rasterize_parts(
    parts: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool, bool]],
    W: int,
    H: int,
    deg: float,
    z_center: float,
    scale: float,
    bg: tuple[int, int, int] = (24, 28, 36),
    z_min_clip: float = -1e9,
    pitch_deg: float = 0.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    center: tuple[float, float, float] | None = None,
) -> Image.Image:
    """Vectorized NumPy Z-buffer rasterizer with 2x SSAA anti-aliasing.

    ``center`` is the model-space point that should land in the middle of the frame; it is
    resolved *after* the rotation, which is what a pitched view needs (pitching about x
    sweeps the region of interest out of the frame in both axes, so a z-only `z_center`
    cannot hold it). ``pan_x`` / ``pan_y`` stay available as raw post-rotation nudges in cm.
    """
    W2, H2 = W * 2, H * 2
    scale2 = scale * 2.0

    R = view_rotation(deg, pitch_deg)

    if center is not None:
        cvec = np.asarray(center, dtype=np.float32) @ R.T
        pan_x += float(cvec[0])
        z_center = float(cvec[2])

    light1 = np.array([0.28, 0.85, 0.44], dtype=np.float32)
    light1 /= np.linalg.norm(light1)
    light2 = np.array([-0.45, 0.55, 0.25], dtype=np.float32)
    light2 /= np.linalg.norm(light2)

    all_px, all_py, all_z, all_col = [], [], [], []

    for pos, nrm, tris, uv, tex, is_cut, v_is_neg in parts:
        if len(tris) == 0:
            continue
        if z_min_clip > -1e8:
            keep_t = (pos[tris[:, 0], 2] >= z_min_clip) | (pos[tris[:, 1], 2] >= z_min_clip) | (pos[tris[:, 2], 2] >= z_min_clip)
            tris = tris[keep_t]
            if len(tris) == 0:
                continue

        pr = pos @ R.T
        nr = nrm @ R.T
        sx = (W2 * 0.5 + (pr[:, 0] - pan_x) * scale2).astype(np.float32)
        sy = (H2 * 0.5 - (pr[:, 2] - z_center - pan_y) * scale2).astype(np.float32)
        depth = pr[:, 1]

        ndotl1 = np.maximum(0.0, nr[:, 0] * light1[0] + nr[:, 1] * light1[1] + nr[:, 2] * light1[2])
        ndotl2 = np.maximum(0.0, nr[:, 0] * light2[0] + nr[:, 1] * light2[1] + nr[:, 2] * light2[2])
        shade = np.clip(0.25 + 0.72 * ndotl1 + 0.16 * ndotl2, 0.16, 1.15)

        a, b, c_i = tris[:, 0], tris[:, 1], tris[:, 2]
        x0, x1, x2 = sx[a], sx[b], sx[c_i]
        y0, y1, y2 = sy[a], sy[b], sy[c_i]

        ix_min = np.maximum(0, np.floor(np.minimum(np.minimum(x0, x1), x2)).astype(np.int32))
        ix_max = np.minimum(W2 - 1, np.ceil(np.maximum(np.maximum(x0, x1), x2)).astype(np.int32))
        iy_min = np.maximum(0, np.floor(np.minimum(np.minimum(y0, y1), y2)).astype(np.int32))
        iy_max = np.minimum(H2 - 1, np.ceil(np.maximum(np.maximum(y0, y1), y2)).astype(np.int32))

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        valid = (denom > 1e-5) & (ix_max >= ix_min) & (iy_max >= iy_min)
        if not valid.any():
            continue

        bw = ix_max - ix_min + 1
        bh = iy_max - iy_min + 1
        max_b = np.maximum(bw, bh)
        th, tw = tex.shape[:2]

        for lo_d, hi_d in ((0, 8), (8, 16), (16, 32), (32, 64), (64, 160), (160, 1024)):
            sel = valid & (max_b > lo_d) & (max_b <= hi_d)
            if not sel.any():
                continue
            idx = np.nonzero(sel)[0]
            chunk = max(1, 260000 // (hi_d * hi_d))
            gx_base = np.arange(hi_d, dtype=np.int32)[None, None, :]
            gy_base = np.arange(hi_d, dtype=np.int32)[None, :, None]
            for start in range(0, len(idx), chunk):
                sub = idx[start : start + chunk]
                ta, tb, tc = a[sub], b[sub], c_i[sub]
                tx0, tx1, tx2 = x0[sub, None, None], x1[sub, None, None], x2[sub, None, None]
                ty0, ty1, ty2 = y0[sub, None, None], y1[sub, None, None], y2[sub, None, None]
                inv_d = (1.0 / denom[sub])[:, None, None]

                gx = ix_min[sub, None, None] + gx_base
                gy = iy_min[sub, None, None] + gy_base

                w0 = ((ty1 - ty2) * (gx - tx2) + (tx2 - tx1) * (gy - ty2)) * inv_d
                w1 = ((ty2 - ty0) * (gx - tx2) + (tx0 - tx2) * (gy - ty2)) * inv_d
                w2 = 1.0 - w0 - w1

                hit = (
                    (w0 >= -1e-4)
                    & (w1 >= -1e-4)
                    & (w2 >= -1e-4)
                    & (gx <= ix_max[sub, None, None])
                    & (gy <= iy_max[sub, None, None])
                )
                ti, yi, xi = np.nonzero(hit)
                if len(ti) == 0:
                    continue

                f_w0, f_w1, f_w2 = w0[ti, yi, xi], w1[ti, yi, xi], w2[ti, yi, xi]
                fa, fb, fc = ta[ti], tb[ti], tc[ti]
                f_px = gx[ti, 0, xi]
                f_py = gy[ti, yi, 0]
                f_z = f_w0 * depth[fa] + f_w1 * depth[fb] + f_w2 * depth[fc]

                u_p = (f_w0 * uv[fa, 0] + f_w1 * uv[fb, 0] + f_w2 * uv[fc, 0]) % 1.0
                v_raw = f_w0 * uv[fa, 1] + f_w1 * uv[fb, 1] + f_w2 * uv[fc, 1]
                v_img_p = ((-v_raw) if v_is_neg else (1.0 - v_raw)) % 1.0

                tx_i = np.clip((u_p * (tw - 1)).astype(np.int32), 0, tw - 1)
                ty_i = np.clip((v_img_p * (th - 1)).astype(np.int32), 0, th - 1)

                samp = tex[ty_i, tx_i]
                if is_cut and tex.shape[2] == 4:
                    keep = samp[:, 3] >= 15
                    if not keep.any():
                        continue
                    f_px, f_py, f_z = f_px[keep], f_py[keep], f_z[keep]
                    f_w0, f_w1, f_w2 = f_w0[keep], f_w1[keep], f_w2[keep]
                    fa, fb, fc = fa[keep], fb[keep], fc[keep]
                    samp = samp[keep]

                sh = f_w0 * shade[fa] + f_w1 * shade[fb] + f_w2 * shade[fc]
                col = np.clip(samp[:, :3] * sh[:, None], 0, 255).astype(np.uint8)

                all_px.append(f_px)
                all_py.append(f_py)
                all_z.append(f_z)
                all_col.append(col)

    yy = np.linspace(0.0, 1.0, H2, dtype=np.float32)[:, None]
    bg_arr = np.zeros((H2, W2, 3), dtype=np.uint8)
    for c_idx in range(3):
        bg_arr[:, :, c_idx] = np.clip(bg[c_idx] * (1.15 - 0.30 * yy), 0, 255).astype(np.uint8)

    if all_px:
        px = np.concatenate(all_px)
        py = np.concatenate(all_py)
        zz = np.concatenate(all_z)
        cc = np.concatenate(all_col)
        order = np.argsort(zz, kind="mergesort")
        bg_arr[py[order], px[order]] = cc[order]

    return Image.fromarray(bg_arr).resize((W, H), Image.Resampling.LANCZOS)


def decode_bgra_icon(raw_bytes: bytes) -> Image.Image:
    """Decode a 128x128 uncompressed BGRA8 DDS icon."""
    arr = np.frombuffer(raw_bytes[128 : 128 + 128 * 128 * 4], dtype=np.uint8).reshape((128, 128, 4))
    rgba = np.zeros_like(arr)
    rgba[:, :, 0] = arr[:, :, 2]
    rgba[:, :, 1] = arr[:, :, 1]
    rgba[:, :, 2] = arr[:, :, 0]
    rgba[:, :, 3] = arr[:, :, 3]
    return Image.fromarray(rgba)


def add_header_and_badges(
    canvas: Image.Image,
    title: str,
    subtitle: str,
    icon_img: Image.Image | None = None,
) -> Image.Image:
    draw = ImageDraw.Draw(canvas)
    W, _ = canvas.size
    draw.rectangle([0, 0, W, 58], fill=(16, 19, 26))
    draw.line([(0, 58), (W, 58)], fill=(65, 130, 210), width=2)
    draw.text((18, 10), title, fill=(245, 248, 255), font=FONT_BOLD_16)
    draw.text((18, 34), subtitle, fill=(165, 180, 205), font=FONT_REG_12)
    if icon_img is not None:
        ic = icon_img.resize((88, 88), Image.Resampling.LANCZOS)
        bx, by = W - 110, 68
        draw.rectangle([bx - 3, by - 3, bx + 90, by + 90], fill=(14, 16, 22), outline=(80, 140, 220), width=2)
        canvas.paste(ic, (bx, by), ic if ic.mode == "RGBA" else None)
        draw.text((bx - 2, by + 94), "HUD / Menu Icon", fill=(190, 205, 225), font=FONT_REG_11)
    return canvas


_KNOWN_DRAWABLE_NAMES = {
    dm.hash64(n): n
    for n in ("g_body", "s_body", "g_arms", "g_head", "g_hands", "co_box")
}


def _drawable_name(mf, name_hash: int) -> str:
    """Resolve a MODEL_DATA drawable hash through the file's own hashlist or known names."""
    hl_secs = mf.by_type(dm.CUSTOM_HASHLIST)
    if hl_secs:
        hl = dm.decode_custom_hashlist(hl_secs[0].payload)
        for n in hl["names"]:
            if dm.hash64(n) == name_hash:
                return n
    return _KNOWN_DRAWABLE_NAMES.get(name_hash, f"#{name_hash:016x}")


def _model_drawables(mf) -> dict:
    """Map drawable name -> (geometry, topology, model_data) for every v3 group."""
    out = {}
    for sec in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(sec.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        out[_drawable_name(mf, md["name_hash"])] = (geo, topo, md)
    return out


def load_las_variant_parts(zip_path: Path, tag: str, prefix: str):
    """Load TPP body + head, FPS arms and the outfit icon from one LAS-line pack.

    ``tag`` is the archive's top-level folder, ``prefix`` the item id used for the file
    names (``miranda`` for the stock LAS outfit, ``miranda_busty`` for the chest variant).
    """
    with zipfile.ZipFile(zip_path) as zf:
        unit = f"{tag}/assets/units/{prefix}/skins/{prefix}/"
        mf_tpp = dm.ModelFile.read(zf.read(unit + f"{prefix}.model"))
        mf_fps = dm.ModelFile.read(zf.read(unit + f"fps_{prefix}.model"))
        body_df = np.asarray(Image.open(io.BytesIO(zf.read(unit + f"{prefix}_body_df.texture"))).convert("RGBA"))
        face_df = np.asarray(Image.open(io.BytesIO(zf.read(unit + f"{prefix}_face_df.texture"))).convert("RGBA"))
        head_df = np.asarray(Image.open(io.BytesIO(zf.read(unit + f"{prefix}_head_df.texture"))).convert("RGBA"))
        eyes_df = np.asarray(Image.open(io.BytesIO(zf.read(unit + f"{prefix}_eyes.texture"))).convert("RGBA"))
        icon_im = Image.open(io.BytesIO(zf.read(
            f"{tag}/assets/guis/dlcs/{prefix}/armor_skins/{prefix}.texture"))).convert("RGBA")

    tpp = _model_drawables(mf_tpp)
    fps = _model_drawables(mf_fps)
    geo_b, topo_b, _md_b = tpp["g_body"]
    geo_h, topo_h, md_h = tpp["g_head"]
    geo_f, topo_f, _md_f = fps["g_body"]

    vh = np.asarray(geo_h["verts"], np.float32)
    nh = np.asarray(geo_h["normals"], np.float32)
    uvh = np.asarray(geo_h["uv0"], np.float32)
    head_tex_map = {0: eyes_df, 1: face_df, 2: head_df, 3: head_df}

    tpp_parts = [
        (
            np.asarray(geo_b["verts"], np.float32),
            np.asarray(geo_b["normals"], np.float32),
            np.array(dm.decode_topology(mf_tpp.by_id(
                dm.decode_passthroughgp(mf_tpp.by_id(_md_b["passthroughgp"]).payload)["topology"]
            ).payload)["indices"], dtype=np.int32).reshape(-1, 3),
            np.asarray(geo_b["uv0"], np.float32),
            body_df,
            False,
            True,
        )
    ]
    head_idx = np.array(topo_h["indices"], dtype=np.int32).reshape(-1, 3)
    for atom in md_h["atoms"]:
        bi, tc, mid = atom["base_index"], atom["tri_count"], atom["material_id"]
        tpp_parts.append(
            (vh, nh, head_idx[bi // 3 : bi // 3 + tc], uvh, head_tex_map[mid], False, False)
        )

    fps_parts = [
        (
            np.asarray(geo_f["verts"], np.float32),
            np.asarray(geo_f["normals"], np.float32),
            np.array(dm.decode_topology(mf_fps.by_id(
                dm.decode_passthroughgp(mf_fps.by_id(_md_f["passthroughgp"]).payload)["topology"]
            ).payload)["indices"], dtype=np.int32).reshape(-1, 3),
            np.asarray(geo_f["uv0"], np.float32),
            body_df,
            False,
            True,
        )
    ]
    return tpp_parts, fps_parts, icon_im


def load_miranda_las_parts() -> tuple[list, list, Image.Image]:
    """Load TPP and FPS parts + icon from dist/Miranda_L4D2/Miranda_L4D2_LAS.zip."""
    return load_las_variant_parts(dist_path(ROOT, "Miranda_LAS.zip"), "Miranda_LAS", "miranda")


def _parse_matcfg_diffuse(xml_bytes: bytes) -> dict[str, str]:
    """Map material name -> diffuse texture asset path from a `.material_config`."""
    root = ET.fromstring(xml_bytes)
    out: dict[str, str] = {}
    for mat in root.findall("material"):
        name = mat.attrib.get("name")
        diff = mat.find("diffuse_texture")
        if name and diff is not None and diff.attrib.get("file"):
            out[name] = diff.attrib["file"]
    return out


def _parts_from_model_with_matcfg(
    zf: zipfile.ZipFile,
    tag: str,
    mf,
    mat_to_asset: dict[str, str],
    tex_cache: dict[str, np.ndarray],
    drawable: str = "g_body",
    cutout_materials: frozenset = frozenset(),
    asset_root: str = "assets",
) -> list:
    # the matcfg's own names fill any gap in the model's hashlist (cooked vanilla units carry none)
    hmap = {dm.hash64(name): name for name in mat_to_asset}
    hl_secs = mf.by_type(dm.CUSTOM_HASHLIST)
    if hl_secs:
        hl = dm.decode_custom_hashlist(hl_secs[0].payload)
        hmap.update({dm.hash64(name): name for name in hl["names"]})
    tpp = _model_drawables(mf)
    geo, topo, md = tpp[drawable]
    mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
    mat_names = [
        hmap.get(dm.decode_material(mf.by_id(mid).payload)["name_hash"], "?")
        for mid in mg["material_ids"]
    ]
    verts = np.asarray(geo["verts"], np.float32)
    norms = np.asarray(geo["normals"], np.float32)
    uvs = np.asarray(geo["uv0"], np.float32)
    tris = np.array(topo["indices"], dtype=np.int32).reshape(-1, 3)

    parts = []
    for atom in md["atoms"]:
        bi, tc, mid = atom["base_index"], atom["tri_count"], atom["material_id"]
        mname = mat_names[mid]
        asset = mat_to_asset[mname]
        if asset not in tex_cache:
            rel = f"{tag}/{asset_root}/{asset}.texture" if asset_root else f"{tag}/{asset}.texture"
            tex_cache[asset] = np.asarray(
                Image.open(io.BytesIO(zf.read(rel))).convert("RGBA")
            )
        parts.append((verts, norms, tris[bi // 3 : bi // 3 + tc], uvs, tex_cache[asset],
                      mname in cutout_materials, True))
    return parts


def load_multi_mat_las_parts(
    zip_path: Path,
    tag: str,
    prefix: str,
    has_fps: bool = True,
    cutout_materials: frozenset = frozenset(),
) -> tuple[list, list, Image.Image]:
    """Load TPP (and optional FPS) multi-material parts + icon from a body-only LAS pack."""
    unit = f"{tag}/assets/units/{prefix}/skins/{prefix}/"
    tex_cache: dict[str, np.ndarray] = {}
    with zipfile.ZipFile(zip_path) as zf:
        mf_tpp = dm.ModelFile.read(zf.read(unit + f"{prefix}.model"))
        tpp_mats = _parse_matcfg_diffuse(zf.read(unit + f"{prefix}.material_config"))
        tpp_parts = _parts_from_model_with_matcfg(zf, tag, mf_tpp, tpp_mats, tex_cache,
                                                   cutout_materials=cutout_materials)
        fps_parts: list = []
        if has_fps:
            mf_fps = dm.ModelFile.read(zf.read(unit + f"fps_{prefix}.model"))
            fps_mats = _parse_matcfg_diffuse(zf.read(unit + f"fps_{prefix}.material_config"))
            fps_parts = _parts_from_model_with_matcfg(zf, tag, mf_fps, fps_mats, tex_cache)
        icon_im = Image.open(
            io.BytesIO(zf.read(f"{tag}/assets/guis/dlcs/{prefix}/armor_skins/{prefix}.texture"))
        ).convert("RGBA")
    return tpp_parts, fps_parts, icon_im


def load_bunny_body_parts(zip_path: Path) -> tuple[list, list, Image.Image]:
    """Load TPP body, FPS arms, and outfit icon from `OfficeSuite_over_Bunny.zip`."""
    tag = "OfficeSuite over Bunny"
    unit_root = f"{tag}/units/pd2_dlc_ccmt/characters/ccmt_acc_bunny"
    tex_cache: dict[str, np.ndarray] = {}
    with zipfile.ZipFile(zip_path) as zf:
        mf_tpp = dm.ModelFile.read(
            zf.read(f"{unit_root}/ccmt_acc_bunny_female_average/ccmt_acc_bunny_female_average.model")
        )
        tpp_mats = _parse_matcfg_diffuse(
            zf.read(f"{unit_root}/shared_materials/ccmt_acc_bunny.material_config")
        )
        tpp_parts = _parts_from_model_with_matcfg(
            zf, tag, mf_tpp, tpp_mats, tex_cache, drawable="g_body", asset_root=""
        )
        mf_fps = dm.ModelFile.read(
            zf.read(f"{unit_root}/ccmt_acc_fps_bunny_male/ccmt_acc_fps_bunny_male.model")
        )
        fps_mats = _parse_matcfg_diffuse(
            zf.read(f"{unit_root}/shared_materials/ccmt_acc_bunny_fps.material_config")
        )
        fps_parts = _parts_from_model_with_matcfg(
            zf, tag, mf_fps, fps_mats, tex_cache, drawable="g_arms", asset_root=""
        )
        icon_im = Image.open(
            io.BytesIO(
                zf.read(f"{tag}/guis/dlcs/ccmt/textures/pd2/blackmarket/icons/player_styles/bunny.texture")
            )
        ).convert("RGBA")
    return tpp_parts, fps_parts, icon_im


def _rot_axis_row(axis: tuple[float, float, float], deg: float) -> np.ndarray:
    a = np.asarray(axis, dtype=np.float64)
    a /= np.linalg.norm(a)
    th = np.deg2rad(deg)
    c, s = float(np.cos(th)), float(np.sin(th))
    x, y, z = float(a[0]), float(a[1]), float(a[2])
    K = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=np.float64)
    R = np.eye(3) * c + (1.0 - c) * np.outer(a, a) + s * K
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = R.T
    return M


def _skin_drawable_posed(
    mf,
    drawable_name: str,
    bone_hash_to_name: dict[int, str],
    local_rots: dict[str, np.ndarray],
    *,
    one_weight_only: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    objs = {s.id: dm.decode_object3d(s.payload) for s in mf.sections if s.type in (dm.OBJECT3D, dm.MODEL_DATA)}
    posed_worlds: dict[int, np.ndarray] = {}

    def get_posed(sid: int) -> np.ndarray:
        if sid not in posed_worlds:
            loc = np.asarray(objs[sid]["matrix"], dtype=np.float64).reshape(4, 4).copy()
            bname = bone_hash_to_name.get(objs[sid]["name_hash"], "")
            if bname in local_rots:
                loc = local_rots[bname] @ loc
            pid = objs[sid]["parent"]
            posed_worlds[sid] = loc @ get_posed(pid) if pid in objs and pid != sid else loc
        return posed_worlds[sid]

    for sid in objs:
        get_posed(sid)

    dhash = dm.hash64(drawable_name)
    md_sec = next(
        s for s in mf.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6
        and dm.decode_model_data(s.payload)["name_hash"] == dhash
    )
    md = dm.decode_model_data(md_sec.payload)
    sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
    pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
    topo = np.array(dm.decode_topology(mf.by_id(pg["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)

    skin_mats = np.stack([
        np.asarray(sb["rotations"][p_idx], dtype=np.float64).reshape(4, 4) @ posed_worlds[sb["objects"][p_idx]]
        for p_idx in sb["maps"][0]
    ], axis=0)

    verts = np.asarray(geo["verts"], dtype=np.float64)
    v4 = np.column_stack([verts, np.ones(len(verts), dtype=np.float64)])
    bi = np.asarray(geo["blendindices"], dtype=np.int64)
    bw = np.asarray(geo["blendweights"], dtype=np.float64)
    w_all = np.column_stack([bw, np.maximum(0.0, 1.0 - bw.sum(axis=1, keepdims=True))])
    if one_weight_only:
        w_all = np.zeros_like(w_all)
        w_all[:, 0] = 1.0

    out_v = np.zeros((len(verts), 3), dtype=np.float64)
    out_n = np.zeros((len(verts), 3), dtype=np.float64)
    has_n = bool(geo.get("normals"))
    norms = np.asarray(geo["normals"], dtype=np.float64) if has_n else np.zeros_like(verts)
    for k in range(w_all.shape[1]):
        wk = w_all[:, k:k + 1]
        if np.all(wk == 0.0):
            continue
        mk = skin_mats[bi[:, k]]
        out_v += wk * np.einsum("vi,vij->vj", v4, mk)[:, :3]
        if has_n:
            out_n += wk * np.einsum("vi,vij->vj", norms, mk[:, :3, :3])
    if not has_n:
        fn = np.cross(out_v[topo[:, 1]] - out_v[topo[:, 0]], out_v[topo[:, 2]] - out_v[topo[:, 0]])
        for c in range(3):
            np.add.at(out_n, topo[:, c], fn)
    out_n /= np.maximum(np.linalg.norm(out_n, axis=1, keepdims=True), 1e-8)
    uv = np.asarray(geo["uv0"], dtype=np.float32) if geo.get("uv0") else np.zeros((len(verts), 2), dtype=np.float32)
    return out_v.astype(np.float32), out_n.astype(np.float32), topo, uv


def render_bunny_posed_audit_sheet(
    bunny_zip: Path,
    office_zip: Path,
    hila_zip: Path,
    tpp_bunny: list,
    fps_bunny: list,
    icon_im: Image.Image,
    out_path: Path,
) -> Image.Image:
    """Six-panel verification sheet: heister collar, posed LBS, 1-weight shadow, normal relief, glove cuff, FPS alignment."""
    from build_bunny_body_mod import FPS_UNIT, MOD_PREFIX, UNIT_ROOT, ensure_bunny_extracted

    with zipfile.ZipFile(office_zip) as zos:
        mf_os = dm.ModelFile.read(zos.read("OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite.model"))
    hl_names = dm.decode_custom_hashlist(mf_os.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    h2name = {dm.hash64(n): n for n in hl_names}

    with zipfile.ZipFile(bunny_zip) as zb:
        df_atlas = np.asarray(Image.open(io.BytesIO(zb.read(f"{MOD_PREFIX}/{UNIT_ROOT}/acc_bunny_df.texture"))).convert("RGBA"))
        nm_atlas = np.asarray(Image.open(io.BytesIO(zb.read(f"{MOD_PREFIX}/{UNIT_ROOT}/acc_bunny_nm.texture"))).convert("RGBA"))
        mf_favg = dm.ModelFile.read(zb.read(f"{MOD_PREFIX}/{UNIT_ROOT}/ccmt_acc_bunny_female_average/ccmt_acc_bunny_female_average.model"))

    with zipfile.ZipFile(hila_zip) as zh:
        hpfx = zh.namelist()[0].split("/")[0]
        mf_hila = dm.ModelFile.read(zh.read(f"{hpfx}/units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female.model"))
        h_df = np.asarray(Image.open(io.BytesIO(zh.read(f"{hpfx}/units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_head_df.texture"))).convert("RGBA"))
        l_df = np.asarray(Image.open(io.BytesIO(zh.read(f"{hpfx}/units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_lashes_df.texture"))).convert("RGBA"))
    md_h = next(
        dm.decode_model_data(s.payload) for s in mf_hila.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6 and dm.decode_model_data(s.payload)["name_hash"] == dm.hash64("g_head")
    )
    pg_h = dm.decode_passthroughgp(mf_hila.by_id(md_h["passthroughgp"]).payload)
    geo_h = dm.decode_geometry(mf_hila.by_id(pg_h["geometry"]).payload)
    topo_h = np.array(dm.decode_topology(mf_hila.by_id(pg_h["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    vh, nh, uvh = np.asarray(geo_h["verts"], np.float32), np.asarray(geo_h["normals"], np.float32), np.asarray(geo_h["uv0"], np.float32)
    a0, a1 = md_h["atoms"][0], md_h["atoms"][1]
    comp_hila = [
        *tpp_bunny,
        (vh, nh, topo_h[a0["base_index"] // 3 : a0["base_index"] // 3 + a0["tri_count"]], uvh, h_df, False, False),
        (vh, nh, topo_h[a1["base_index"] // 3 : a1["base_index"] // 3 + a1["tri_count"]], uvh, l_df, True, False),
    ]

    pose = {
        "LeftShoulder": _rot_axis_row((0.0, 1.0, 0.0), -18.0),
        "RightShoulder": _rot_axis_row((0.0, 1.0, 0.0), 18.0),
        "LeftArm": _rot_axis_row((0.0, 1.0, 0.0), -22.0),
        "RightArm": _rot_axis_row((0.0, 1.0, 0.0), 22.0),
        "LeftForeArm": _rot_axis_row((0.0, 1.0, 0.0), -35.0),
        "RightForeArm": _rot_axis_row((0.0, 1.0, 0.0), -35.0),
        "LeftForeArmRoll": _rot_axis_row((1.0, 0.0, 0.0), 40.0),
        "RightForeArmRoll": _rot_axis_row((1.0, 0.0, 0.0), -40.0),
        "LeftUpLeg": _rot_axis_row((0.0, 1.0, 0.0), 12.0),
        "RightUpLeg": _rot_axis_row((0.0, 1.0, 0.0), -10.0),
        "LeftLeg": _rot_axis_row((0.0, 1.0, 0.0), -18.0),
        "RightLeg": _rot_axis_row((0.0, 1.0, 0.0), -8.0),
    }
    vp, np_, tp, uvp = _skin_drawable_posed(mf_favg, "g_body", h2name, pose)
    vs, ns, ts, uvs = _skin_drawable_posed(mf_favg, "s_body", h2name, pose, one_weight_only=True)
    shadow_tex = np.full((32, 32, 4), [158, 170, 192, 255], dtype=np.uint8)

    md_b = next(
        dm.decode_model_data(s.payload) for s in mf_favg.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6 and dm.decode_model_data(s.payload)["name_hash"] == dm.hash64("g_body")
    )
    geo_b = dm.decode_geometry(mf_favg.by_id(dm.decode_passthroughgp(mf_favg.by_id(md_b["passthroughgp"]).payload)["geometry"]).payload)
    topo_b = np.array(dm.decode_topology(mf_favg.by_id(dm.decode_passthroughgp(mf_favg.by_id(md_b["passthroughgp"]).payload)["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    v0 = np.asarray(geo_b["verts"], np.float32)
    n0 = np.asarray(geo_b["normals"], np.float32)
    u0 = np.asarray(geo_b["uvdir_u"], np.float32)
    b0 = np.asarray(geo_b["uvdir_v"], np.float32)
    uv0 = np.asarray(geo_b["uv0"], np.float32)
    ah, aw = nm_atlas.shape[:2]
    px = np.clip(((uv0[:, 0] % 1.0) * aw).astype(np.int64), 0, aw - 1)
    py = np.clip((((-uv0[:, 1]) % 1.0) * ah).astype(np.int64), 0, ah - 1)
    nsamp = nm_atlas[py, px].astype(np.float32)
    nx, ny = (nsamp[:, 3] / 255.0) * 2.0 - 1.0, (nsamp[:, 1] / 255.0) * 2.0 - 1.0
    nz = np.sqrt(np.maximum(0.0, 1.0 - nx * nx - ny * ny))
    pert_n = nx[:, None] * u0 + ny[:, None] * b0 + nz[:, None] * n0
    pert_n /= np.maximum(np.linalg.norm(pert_n, axis=1, keepdims=True), 1e-8)
    clay_tex = np.full((32, 32, 4), [220, 225, 235, 255], dtype=np.uint8)

    with zipfile.ZipFile(ROOT / "references/templates/Heister - FPS Gloves in TPS 2.zip") as zg:
        sy_name = next(n for n in zg.namelist() if n.endswith("npc_criminal_sydney.model") and "chill" not in n)
        mf_sy = dm.ModelFile.read(zg.read(sy_name))
    md_sy = next(
        dm.decode_model_data(s.payload) for s in mf_sy.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6 and dm.decode_model_data(s.payload)["name_hash"] == dm.hash64("g_hands")
    )
    geo_sy = dm.decode_geometry(mf_sy.by_id(dm.decode_passthroughgp(mf_sy.by_id(md_sy["passthroughgp"]).payload)["geometry"]).payload)
    topo_sy = np.array(dm.decode_topology(mf_sy.by_id(dm.decode_passthroughgp(mf_sy.by_id(md_sy["passthroughgp"]).payload)["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    sy_tex = np.full((32, 32, 4), [175, 78, 96, 255], dtype=np.uint8)
    wrist_parts = []
    for v_w, n_w, t_w, uv_w, tx_w, co_w, ds_w in [
        *tpp_bunny,
        (np.asarray(geo_sy["verts"], np.float32), np.asarray(geo_sy["normals"], np.float32), topo_sy, np.zeros((geo_sy["vert_count"], 2), np.float32), sy_tex, False, True),
    ]:
        keep = (v_w[t_w, 0].mean(axis=1) < -24.0) & (v_w[t_w, 2].mean(axis=1) > 90.0)
        if np.any(keep):
            kt = t_w[keep]
            used = np.unique(kt)
            remap = np.zeros(len(v_w), dtype=np.int32)
            remap[used] = np.arange(len(used), dtype=np.int32)
            wrist_parts.append((v_w[used], n_w[used], remap[kt], uv_w[used], tx_w, co_w, ds_w))

    bdir = ensure_bunny_extracted()
    vmf_fps = dm.ModelFile.read((bdir / FPS_UNIT / f"{FPS_UNIT}.model").read_bytes())
    v_md = next(
        dm.decode_model_data(s.payload) for s in vmf_fps.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6 and dm.decode_model_data(s.payload)["name_hash"] == dm.hash64("g_arms")
    )
    v_geo = dm.decode_geometry(vmf_fps.by_id(dm.decode_passthroughgp(vmf_fps.by_id(v_md["passthroughgp"]).payload)["geometry"]).payload)
    v_topo = np.array(dm.decode_topology(vmf_fps.by_id(dm.decode_passthroughgp(vmf_fps.by_id(v_md["passthroughgp"]).payload)["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    ghost_tex = np.full((32, 32, 4), [90, 155, 245, 255], dtype=np.uint8)
    fps_overlay = [
        (np.asarray(v_geo["verts"], np.float32), np.asarray(v_geo["normals"], np.float32), v_topo, np.zeros((v_geo["vert_count"], 2), np.float32), ghost_tex, False, True),
        *fps_bunny,
    ]

    W_cell, H_cell = 480, 360
    canvas = Image.new("RGB", (W_cell * 3, H_cell * 2 + 58), (18, 22, 30))
    cells = [
        (rasterize_parts(comp_hila, W_cell, H_cell, 18.0, 150.0, 7.2, z_min_clip=120.0), "1. Hila Head + Bunny Override Collar (18°)"),
        (rasterize_parts([(vp, np_, tp, uvp, df_atlas, False, True)], W_cell, H_cell, 20.0, 82.0, 1.95), "2. Posed LBS Deformation + Wrist Roll 40°"),
        (rasterize_parts([(vs, ns, ts, uvs, shadow_tex, False, True)], W_cell, H_cell, 20.0, 82.0, 1.95), "3. s_body Shadow Caster (SKINNED_1WEIGHT)"),
        (rasterize_parts([(v0, pert_n, topo_b, uv0, clay_tex, False, True)], W_cell, H_cell, -24.0, 128.0, 4.3, z_min_clip=92.0), "4. Clay + acc_bunny_nm Tangent Normal Relief"),
        (rasterize_fitted(wrist_parts, W_cell, H_cell, 35.0, -25.0, margin=0.88, pad=(12, 12, 12, 36)), "5. Sydney Glove (g_hands) + Watch Cuff"),
        (rasterize_fitted(fps_overlay, W_cell, H_cell, 0.0, -25.0, margin=0.90, pad=(12, 12, 12, 36)), "6. FPS Arms Overlay vs Vanilla Bunny (Blue)"),
    ]
    for idx, (im, lbl) in enumerate(cells):
        r, c = divmod(idx, 3)
        d = ImageDraw.Draw(im)
        d.rectangle([8, H_cell - 30, 355, H_cell - 8], fill=(14, 17, 24))
        d.text((14, H_cell - 26), lbl, fill=(230, 235, 245), font=FONT_REG_12)
        canvas.paste(im, (c * W_cell, 58 + r * H_cell))
    add_header_and_badges(
        canvas,
        "dist/Miranda/OfficeSuite_over_Bunny.zip — Collar, Posed LBS, Shadow, Normal-Map, Glove & FPS Audit",
        "Hila head seam | Posed 3-weight LBS & 1-weight s_body | DXT5nm tangent relief | Sydney glove cuff | FPS alignment vs vanilla bunny",
        icon_im,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Saved {out_path}")
    return canvas


def render_las_sheet(
    title: str,
    subtitle: str,
    tpp_parts: list,
    fps_parts: list,
    icon_im: Image.Image,
    out_path: Path,
    has_head: bool = True,
    closeup: tuple[float, float, float] = (18.0, 166.5, 11.5),
    full_view: tuple[float, float] | None = None,
) -> Image.Image:
    W_col, H_row = 360, 540
    canvas = Image.new("RGB", (W_col * 4, H_row + 58), (18, 22, 30))

    z_full, s_full = full_view or ((92.0, 2.75) if has_head else (74.0, 2.65))
    p_front = rasterize_parts(tpp_parts, W_col, H_row, 0, z_full, s_full)
    p_34 = rasterize_parts(tpp_parts, W_col, H_row, 34, z_full, s_full)
    p_back = rasterize_parts(tpp_parts, W_col, H_row, 180, z_full, s_full)

    if has_head:
        p_top = rasterize_parts(tpp_parts, W_col, H_row // 2, *closeup, z_min_clip=138.0)
        top_lbl = f"Close-Up Portrait ({closeup[0]:.0f}\u00b0)"
    else:
        p_top = rasterize_parts(tpp_parts, W_col, H_row // 2, 24, 128.0, 4.9, z_min_clip=92.0)
        top_lbl = "Upper Body 3/4 (24°)"

    if fps_parts:
        # Player's-eye view: yaw 0 looks down the arms; the negative pitch looks down
        # from above them, as the in-game camera does. Frame the arms themselves, not a
        # fixed z_center — the unit is as wide as it is tall and auto-fits cleanly.
        p_bot = rasterize_fitted(
            fps_parts, W_col, H_row // 2, 0.0, -25.0, margin=0.88, pad=(12, 12, 10, 44)
        )
        bot_lbl = "First-Person Arms (fps_*.model, player view)"
    else:
        side_center, side_scale = (z_full, s_full / 2) if full_view else (74.0, 1.40)
        p_bot = rasterize_parts(tpp_parts, W_col, H_row // 2, 90, side_center, side_scale)
        bot_lbl = "Full-Body Side (90°, TPP only)"

    for i, (im, lbl) in enumerate([
        (p_front, "Full-Body Front (0°)"),
        (p_34, "Full-Body 3/4 View (34°)"),
        (p_back, "Full-Body Back (180°)"),
    ]):
        d = ImageDraw.Draw(im)
        d.rectangle([8, H_row - 30, 215, H_row - 8], fill=(14, 17, 24))
        d.text((14, H_row - 26), lbl, fill=(230, 235, 245), font=FONT_REG_12)
        canvas.paste(im, (i * W_col, 58))

    d_h = ImageDraw.Draw(p_top)
    d_h.rectangle([8, H_row // 2 - 30, 225, H_row // 2 - 8], fill=(14, 17, 24))
    d_h.text((14, H_row // 2 - 26), top_lbl, fill=(230, 235, 245), font=FONT_REG_12)
    canvas.paste(p_top, (3 * W_col, 58))

    d_f = ImageDraw.Draw(p_bot)
    d_f.rectangle([8, H_row // 2 - 30, 245, H_row // 2 - 8], fill=(14, 17, 24))
    d_f.text((14, H_row // 2 - 26), bot_lbl, fill=(230, 235, 245), font=FONT_REG_12)
    canvas.paste(p_bot, (3 * W_col, 58 + H_row // 2))

    add_header_and_badges(canvas, title, subtitle, icon_im)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Saved {out_path}")
    if has_head:
        return rasterize_parts(tpp_parts, 360, 480, 24, 147.0, 5.8, z_min_clip=105.0)
    return rasterize_parts(tpp_parts, 360, 480, 24, 76.0, 2.50)


#: Views of a `fps_*.model` unit: (caption, yaw, pitch). The arms are authored as the
#: player sees them, so yaw 0 with a downward pitch is the in-game first-person read;
#: the rest show the same unit from the angles the camera never takes.
FPS_VIEWS = (
    ("Player view (0°, 25° down)", 0.0, -25.0),
    ("Three-quarter (35°, 20° down)", 35.0, -20.0),
    ("Side (90° yaw)", 90.0, 0.0),
    ("Top-down (0°, 70° down)", 0.0, -70.0),
)


def render_fps_sheet(
    title: str,
    subtitle: str,
    fps_parts: list,
    out_path: Path,
    W_col: int = 720,
    H_row: int = 280,
) -> Image.Image:
    """A four-view sheet of one pack's `fps_*.model` unit, auto-framed per view.

    The cells are landscape because a first-person unit is: two arms span ~106 cm
    across and ~50 cm deep, so portrait cells leave most of the frame empty.
    `render_las_sheet` keeps a small first-person panel so a pack reads as one page;
    this sheet is the close inspection of the same unit — the seams, cuffs and hands
    that only exist on the arms.
    """
    cols = 2
    rows = (len(FPS_VIEWS) + cols - 1) // cols
    canvas = Image.new("RGB", (W_col * cols, H_row * rows + 58), (18, 22, 30))
    for i, (caption, yaw, pitch) in enumerate(FPS_VIEWS):
        img = rasterize_fitted(
            fps_parts, W_col, H_row, yaw, pitch, margin=0.94, pad=(12, 12, 8, 34)
        )
        d = ImageDraw.Draw(img)
        d.rectangle([8, H_row - 30, 285, H_row - 8], fill=(14, 17, 24))
        d.text((14, H_row - 26), caption, fill=(230, 235, 245), font=FONT_REG_12)
        canvas.paste(img, ((i % cols) * W_col, 58 + (i // cols) * H_row))
    add_header_and_badges(canvas, title, subtitle)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Saved {out_path}")
    return canvas


#: Chest close-up views for the busty sheets: (caption, yaw, pitch, scale, centre).
#: The wider the yaw, the further the camera has to sit back — at 90° the silhouette is
#: edge-on, so the 13 px/cm that frames the 0° view crops the cup to a sliver.
CHEST_VIEWS = (
    ("0°", 0.0, 0.0, 13.0, (0.0, 20.0, 141.0)),
    ("30°", 30.0, 0.0, 12.4, (0.0, 16.0, 141.0)),
    ("45°", 45.0, 0.0, 11.3, (0.0, 12.0, 141.0)),
    ("60°", 60.0, 0.0, 10.2, (0.0, 8.0, 141.0)),
    ("90°", 90.0, 0.0, 8.8, (0.0, 5.0, 141.0)),
)

#: Overhead / underside views: the angles no front sheet can show, and the ones that expose
#: a sculpt's worst habits (a hem that bows, a cup that does not hang, a sternum pinch).
CHEST_POLAR_VIEWS = (
    ("above 58°", 0.0, -58.0),
    ("above 58°, 30° yaw", 30.0, -58.0),
    ("below 58°", 0.0, 58.0),
    ("below 58°, 30° yaw", 30.0, 58.0),
)


def render_heister_head_sheet(
    zip_name: str,
    model_rel: str,
    head_df_rel: str,
    sec_df_rel: str,
    icon_rel: str,
    head_draw_name: str,
    suit_rgb: tuple[int, int, int],
    glove_rgb: tuple[int, int, int],
    title: str,
    subtitle: str,
    out_path: Path,
    portrait: tuple[float, float] | None = None,
    full: tuple[float, float] | None = None,
) -> Image.Image:
    zp = dist_path(ROOT, zip_name)
    with zipfile.ZipFile(zp) as zf:
        prefix = [n.split("/")[0] for n in zf.namelist()][0]
        mbytes = zf.read(f"{prefix}/{model_rel}")
        head_df = np.asarray(Image.open(io.BytesIO(zf.read(f"{prefix}/{head_df_rel}"))).convert("RGBA"))
        sec_df = np.asarray(Image.open(io.BytesIO(zf.read(f"{prefix}/{sec_df_rel}"))).convert("RGBA"))
        icon_im = decode_bgra_icon(zf.read(f"{prefix}/{icon_rel}"))

    mf = dm.ModelFile.read(mbytes)
    md_by_hash = {dm.decode_model_data(s.payload)["name_hash"]: s for s in mf.by_type(dm.MODEL_DATA)}

    suit_tex = np.full((32, 32, 4), [*suit_rgb, 255], dtype=np.uint8)
    glove_tex = np.full((32, 32, 4), [*glove_rgb, 255], dtype=np.uint8)
    skin_tex = np.full((32, 32, 4), [198, 155, 132, 255], dtype=np.uint8)

    parts = []
    for dname, tex in [
        ("g_body", suit_tex),
        ("g_hands", glove_tex),
        ("g_arms", skin_tex),
        ("g_female_forearms", skin_tex),
        ("g_male_forearms", skin_tex),
    ]:
        h = dm.hash64(dname)
        if h not in md_by_hash:
            continue
        md_d = dm.decode_model_data(md_by_hash[h].payload)
        pg_d = dm.decode_passthroughgp(mf.by_id(md_d["passthroughgp"]).payload)
        geo_d = dm.decode_geometry(mf.by_id(pg_d["geometry"]).payload)
        topo_d = np.array(dm.decode_topology(mf.by_id(pg_d["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
        parts.append(
            (
                np.asarray(geo_d["verts"], np.float32),
                np.asarray(geo_d["normals"], np.float32),
                topo_d,
                np.asarray(geo_d["uv0"], np.float32),
                tex,
                False,
                False,
            )
        )

    md_head = dm.decode_model_data(md_by_hash[dm.hash64(head_draw_name)].payload)
    pg_head = dm.decode_passthroughgp(mf.by_id(md_head["passthroughgp"]).payload)
    geo_head = dm.decode_geometry(mf.by_id(pg_head["geometry"]).payload)
    topo_head = np.array(dm.decode_topology(mf.by_id(pg_head["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    vh = np.asarray(geo_head["verts"], np.float32)
    nh = np.asarray(geo_head["normals"], np.float32)
    uvh = np.asarray(geo_head["uv0"], np.float32)
    if len(md_head["atoms"]) == 1:
        a0 = md_head["atoms"][0]
        parts.append((vh, nh, topo_head[a0["base_index"] // 3 : a0["base_index"] // 3 + a0["tri_count"]], uvh, head_df, True, False))
    else:
        a0, a1 = md_head["atoms"][0], md_head["atoms"][1]
        parts.append((vh, nh, topo_head[a0["base_index"] // 3 : a0["base_index"] // 3 + a0["tri_count"]], uvh, head_df, False, False))
        parts.append((vh, nh, topo_head[a1["base_index"] // 3 : a1["base_index"] // 3 + a1["tri_count"]], uvh, sec_df, True, False))

    W_col, H_row = 360, 480
    canvas = Image.new("RGB", (W_col * 4, H_row + 58), (18, 22, 30))

    if "wild" in model_rel:
        z_portrait, s_portrait = 171.8, 11.4
        z_full, s_full = 97.5, 2.40
    else:
        z_portrait, s_portrait = 164.0, 12.2
        z_full, s_full = 92.0, 2.55
    # Per-pack overrides for heads that sit at another height (Old Hoxton's head is
    # the shared suit model's, ~10 cm above Clover's/Bonnie's).
    if portrait is not None:
        z_portrait, s_portrait = portrait
    if full is not None:
        z_full, s_full = full
    p_front = rasterize_parts(parts, W_col, H_row, 0, z_portrait, s_portrait, z_min_clip=135.0)
    p_34 = rasterize_parts(parts, W_col, H_row, 32, z_portrait, s_portrait, z_min_clip=135.0)
    p_back = rasterize_parts(parts, W_col, H_row, 180, z_portrait, s_portrait, z_min_clip=135.0)
    p_full = rasterize_parts(parts, W_col, H_row, 22, z_full, s_full)

    for i, (im, lbl) in enumerate([
        (p_front, "Portrait Front (0°)"),
        (p_34, "Collar & Head 3/4 (32°)"),
        (p_back, "Back Collar & Hair (180°)"),
        (p_full, "Full Heister Rig (22°)"),
    ]):
        d = ImageDraw.Draw(im)
        d.rectangle([8, H_row - 30, 235, H_row - 8], fill=(14, 17, 24))
        d.text((14, H_row - 26), lbl, fill=(230, 235, 245), font=FONT_REG_12)
        canvas.paste(im, (i * W_col, 58))

    add_header_and_badges(canvas, title, subtitle, icon_im)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Saved {out_path}")
    return p_34


def render_hila_posture_sheet(out_path: Path) -> None:
    """Render the 6-panel D86 posture, collar-throat & macro verification sheet for `Miranda_L4D2_over_Hila`."""
    import build_joy_head_mods as bj

    hila_zip = dist_path(ROOT, "Miranda_L4D2_over_Hila.zip")
    mir_zip = dist_path(ROOT, "Miranda_L4D2_LAS.zip")
    os_zip = dist_path(ROOT, "OfficeSuite.zip")

    with zipfile.ZipFile(hila_zip) as zf:
        m_raw = zf.read("Miranda L4D2 over Hila/units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female.model")
        hdf_raw = zf.read("Miranda L4D2 over Hila/units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_head_df.texture")
        ldf_raw = zf.read("Miranda L4D2 over Hila/units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_lashes_df.texture")
    mf_aft = dm.ModelFile.read(m_raw)
    hdf = np.asarray(Image.open(io.BytesIO(hdf_raw)).convert("RGBA"))
    ldf = np.asarray(Image.open(io.BytesIO(ldf_raw)).convert("RGBA"))

    md_aft = next(
        dm.decode_model_data(s.payload)
        for s in mf_aft.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload).get("name_hash") == dm.hash64("g_head")
    )
    pg_aft = dm.decode_passthroughgp(mf_aft.by_id(md_aft["passthroughgp"]).payload)
    geo_aft = dm.decode_geometry(mf_aft.by_id(pg_aft["geometry"]).payload)
    topo_aft = np.asarray(dm.decode_topology(mf_aft.by_id(pg_aft["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    v_aft = np.asarray(geo_aft["verts"], dtype=np.float32)
    n_aft = np.asarray(geo_aft["normals"], dtype=np.float32)
    uv_aft = np.asarray(geo_aft["uv0"], dtype=np.float32)
    a0, a1 = md_aft["atoms"][0], md_aft["atoms"][1]
    t0_aft = topo_aft[a0["base_index"] // 3 : a0["base_index"] // 3 + a0["tri_count"]]
    t1_aft = topo_aft[a1["base_index"] // 3 : a1["base_index"] // 3 + a1["tri_count"]]

    # Reconstruct the pre-D86 upright L4D2 bind head deterministically from Miranda_L4D2_LAS + inverse rigid eyelashes
    c_p, s_p = bj._l4d2_posture_cos_sin()
    src_ey, src_ez = bj.L4D2_SRC_EYE_YZ
    tgt_ey, tgt_ez = bj.L4D2_TGT_EYE_YZ
    lash_v_aft = v_aft[a1["base_vertex"] : a1["base_vertex"] + a1["slice_len"]].astype(np.float64)
    lash_n_aft = n_aft[a1["base_vertex"] : a1["base_vertex"] + a1["slice_len"]].astype(np.float64)
    lash_uv_aft = uv_aft[a1["base_vertex"] : a1["base_vertex"] + a1["slice_len"]]
    lash_t_loc = t1_aft - a1["base_vertex"]
    lash_v_bef = lash_v_aft.copy()
    dy_l, dz_l = lash_v_aft[:, 1] - tgt_ey, lash_v_aft[:, 2] - tgt_ez
    lash_v_bef[:, 1] = src_ey + dy_l * c_p - dz_l * s_p
    lash_v_bef[:, 2] = src_ez + dy_l * s_p + dz_l * c_p
    lash_n_bef = lash_n_aft.copy()
    lash_n_bef[:, 1] = lash_n_aft[:, 1] * c_p - lash_n_aft[:, 2] * s_p
    lash_n_bef[:, 2] = lash_n_aft[:, 1] * s_p + lash_n_aft[:, 2] * c_p

    with zipfile.ZipFile(mir_zip) as zf:
        pm_mir = dm.ModelFile.read(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model"))
    md_h0 = dm.decode_model_data(pm_mir.by_id(94).payload)
    pg_h0 = dm.decode_passthroughgp(pm_mir.by_id(md_h0["passthroughgp"]).payload)
    geo_h0 = dm.decode_geometry(pm_mir.by_id(pg_h0["geometry"]).payload)
    topo_h0 = np.asarray(dm.decode_topology(pm_mir.by_id(pg_h0["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    vh0 = np.asarray(geo_h0["verts"], dtype=np.float64)
    nh0 = np.asarray(geo_h0["normals"], dtype=np.float64)
    uvh0 = np.column_stack([np.asarray(geo_h0["uv0"])[:, 0], 1.0 - np.asarray(geo_h0["uv0"])[:, 1]])

    atoms_bef: dict[int, list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = {}
    for atom in md_h0["atoms"]:
        bv, sl, bi, tc, mid = atom["base_vertex"], atom["slice_len"], atom["base_index"], atom["tri_count"], atom["material_id"]
        ps, ns, uvs = vh0[bv : bv + sl].copy(), nh0[bv : bv + sl].copy(), uvh0[bv : bv + sl].copy()
        ts = topo_h0[bi // 3 : bi // 3 + tc] - bv
        if mid == 3:
            ps_sh = bj.shape_neck_and_hair_for_suit_collar(ps.astype(np.float32), uvs.astype(np.float32), tris=ts)
            ps_sk, ns_sk, uvs_sk, ts_sk = bj.extend_neck_skirt(ps_sh, ns.astype(np.float32), uvs.astype(np.float32), ts)
            ps, ns, uvs, ts = ps_sk.astype(np.float64), ns_sk.astype(np.float64), uvs_sk.astype(np.float64), ts_sk
        elif mid == 0:
            uvs = bj.project_me2_eye_uv_img(ps)
            ns = bj.soften_eyeball_normals(ns.astype(np.float32)).astype(np.float64)
        atoms_bef.setdefault(mid, []).append((ps, ns, uvs, ts))
    fp0, fn0, fuv0, ft0 = atoms_bef[1][0]
    sp0, sn0, suv0, st0 = atoms_bef[3][0]
    fn0, sn0 = bj.repair_skin_and_neck_normals(fp0, fn0, ft0, sp0, sn0, suv0, st0)
    atoms_bef[1][0] = (fp0, fn0.astype(np.float64), fuv0, ft0)
    atoms_bef[3][0] = (sp0, sn0.astype(np.float64), suv0, st0)
    mat_quad = {1: (0, 0), 2: (1, 0), 3: (1, 0), 0: (1, 1)}
    b_v, b_n, b_uv, b_t = [], [], [], []
    for mid in (3, 0, 1, 2):
        qx, qy = mat_quad[mid]
        for ps, ns, uvs, ts in atoms_bef[mid]:
            off = sum(len(x) for x in b_v)
            b_v.append(ps.astype(np.float32))
            b_n.append(ns.astype(np.float32))
            b_uv.append(bj.map_uv_to_quadrant(uvs, qx, qy))
            b_t.append(ts + off)
    v_bef0 = np.vstack(b_v)
    n_bef0 = np.vstack(b_n)
    uv_bef0 = np.vstack(b_uv)
    t0_bef = np.vstack(b_t)

    with zipfile.ZipFile(os_zip) as zf:
        os_mf = dm.ModelFile.read(zf.read("OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite.model"))
    md_os = next(
        dm.decode_model_data(s.payload)
        for s in os_mf.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload).get("name_hash") == dm.hash64("g_body")
    )
    pg_os = dm.decode_passthroughgp(os_mf.by_id(md_os["passthroughgp"]).payload)
    os_geo = dm.decode_geometry(os_mf.by_id(pg_os["geometry"]).payload)
    os_topo = np.asarray(dm.decode_topology(os_mf.by_id(pg_os["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    suit_tex = np.full((32, 32, 4), [24, 27, 34, 255], dtype=np.uint8)
    os_v = np.asarray(os_geo["verts"], dtype=np.float32)
    os_n = np.asarray(os_geo["normals"], dtype=np.float32)
    os_uv = np.asarray(os_geo["uv0"], dtype=np.float32)

    # Menu LBS pose on AFTER (`Neck` +3.5°, `Head` +4.0°)
    vp = v_aft.astype(np.float64)
    np_a = n_aft.astype(np.float64)
    bi_a = np.asarray(geo_aft["blendindices"], dtype=np.int32)
    bw_a = np.asarray(geo_aft["blendweights"], dtype=np.float64)
    p_neck = np.array([0.0, 2.29, 159.33])
    p_head = np.array([0.0, 5.33, 166.76])

    def _rx(deg: float) -> np.ndarray:
        r = np.radians(deg)
        c, s = np.cos(r), np.sin(r)
        return np.array([[1.0, 0.0, 0.0], [0.0, c, s], [0.0, -s, c]])

    rn = _rx(3.5)
    rh = rn @ _rx(4.0)
    ph_p = p_neck + rn @ (p_head - p_neck)
    mp = {1: vp, 2: p_neck + (rn @ (vp - p_neck).T).T, 3: ph_p + (rh @ (vp - p_head).T).T}
    mn = {1: np_a, 2: (rn @ np_a.T).T, 3: (rh @ np_a.T).T}
    vo_a = np.zeros_like(vp)
    no_a = np.zeros_like(np_a)
    for k in range(3):
        ik = bi_a[:, k]
        wk = bw_a[:, k][:, None]
        for bid in (1, 2, 3):
            m = ik == bid
            if m.any():
                vo_a[m] += wk[m] * mp[bid][m]
                no_a[m] += wk[m] * mn[bid][m]
    no_a /= np.maximum(np.linalg.norm(no_a, axis=1, keepdims=True), 1e-8)
    vo_f = vo_a.astype(np.float32)
    no_f = no_a.astype(np.float32)

    def _shift(parts_list: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool, bool]], dy: float):
        out = []
        for vx, nx, tx, uvx, texx, is_l, ds in parts_list:
            vc = vx.copy()
            vc[:, 1] += dy
            out.append((vc, nx, tx, uvx, texx, is_l, ds))
        return out

    bef_parts = [
        (os_v, os_n, os_topo, os_uv, suit_tex, False, False),
        (v_bef0, n_bef0, t0_bef, uv_bef0, hdf, False, False),
        (lash_v_bef.astype(np.float32), lash_n_bef.astype(np.float32), lash_t_loc, lash_uv_aft, ldf, True, False),
    ]
    aft_parts = [
        (os_v, os_n, os_topo, os_uv, suit_tex, False, False),
        (v_aft, n_aft, t0_aft, uv_aft, hdf, False, False),
        (v_aft, n_aft, t1_aft, uv_aft, ldf, True, False),
    ]
    posed_parts = [
        (os_v, os_n, os_topo, os_uv, suit_tex, False, False),
        (vo_f, no_f, t0_aft, uv_aft, hdf, False, False),
        (vo_f, no_f, t1_aft, uv_aft, ldf, True, False),
    ]

    pw, th, bh = 460, 510, 460
    scale_side, zc_side = 12.6, 171.2
    p1 = rasterize_parts(_shift(bef_parts, -7.2), pw, th, -90, zc_side, scale_side, z_min_clip=145.0)
    p2 = rasterize_parts(_shift(aft_parts, -7.2), pw, th, -90, zc_side, scale_side, z_min_clip=145.0)
    p3 = rasterize_parts(_shift(posed_parts, -8.2), pw, th, -90, zc_side, scale_side, z_min_clip=145.0)

    for im, dy_sh, show_before_eye in ((p1, -7.2, True), (p2, -7.2, False)):
        dr = ImageDraw.Draw(im)
        jx = int(round(pw * 0.5 + (tgt_ey + dy_sh) * scale_side))
        jz = int(round(th * 0.5 - (tgt_ez - zc_side) * scale_side))
        dr.ellipse([jx - 5, jz - 5, jx + 5, jz + 5], outline=(90, 230, 255), width=2)
        dr.text((jx + 8, jz - 7), "PD2 Eye Target", fill=(90, 230, 255), font=FONT_REG_11)
        if show_before_eye:
            bx = int(round(pw * 0.5 + (src_ey + dy_sh) * scale_side))
            bz = int(round(th * 0.5 - (src_ez - zc_side) * scale_side))
            dr.ellipse([bx - 5, bz - 5, bx + 5, bz + 5], outline=(255, 120, 120), width=2)
            dr.line([(bx + 5, bz), (jx - 5, jz)], fill=(255, 200, 90), width=2)
            dr.text((bx - 108, bz - 18), "L4D2 Eye (-3.7 cm)", fill=(255, 145, 145), font=FONT_REG_11)

    p4 = rasterize_parts(aft_parts, pw, bh, 0, 168.5, 13.2, z_min_clip=145.0)
    p5 = rasterize_parts(aft_parts, pw, bh, 32, 168.5, 13.2, z_min_clip=145.0)
    p6 = rasterize_parts(aft_parts, pw, bh, 25, 173.8, 24.0, z_min_clip=158.0)

    labels_top = [
        (p1, "BEFORE: Upright L4D2 Bind (-90°)", (255, 160, 160)),
        (p2, "AFTER: +10.5° Heister Posture (-90°)", (135, 255, 175)),
        (p3, "AFTER: Menu Pose + Suit Collar (-90°)", (135, 235, 255)),
    ]
    labels_bot = [
        (p4, "AFTER: Portrait Front (0°)", (235, 240, 250)),
        (p5, "AFTER: 3/4 Jawline & Throat (32°)", (235, 240, 250)),
        (p6, "AFTER: Eye, Lash & Seam Macro (25°)", (235, 240, 250)),
    ]
    for im, txt, col in labels_top + labels_bot:
        dr = ImageDraw.Draw(im)
        dr.rectangle([8, 8, pw - 8, 34], fill=(14, 17, 24))
        dr.text((14, 13), txt, fill=col, font=FONT_BOLD_13)

    gap, hdr = 10, 62
    w_tot = pw * 3 + gap * 4
    h_tot = hdr + th + bh + gap * 3
    sheet = Image.new("RGB", (w_tot, h_tot), (11, 13, 18))
    drs = ImageDraw.Draw(sheet)
    drs.text(
        (gap + 4, 12),
        "dist/Miranda/Miranda_L4D2_over_Hila.zip — Forward Heister Posture & Throat Verification (D86)",
        fill=(242, 245, 252),
        font=FONT_BOLD_16,
    )
    drs.text(
        (gap + 4, 36),
        "+10.5° rational pitch | Eyeball (12.00, 174.72) -> (15.70, 173.80) cm (cornea 17.29 cm) | Orthonormal TBN | 0/114 rim edges exposed",
        fill=(165, 178, 200),
        font=FONT_REG_12,
    )
    drs.line([(0, hdr - 4), (w_tot, hdr - 4)], fill=(58, 128, 220), width=2)
    for i, (im, _, _) in enumerate(labels_top):
        sheet.paste(im, (gap + i * (pw + gap), hdr))
    for i, (im, _, _) in enumerate(labels_bot):
        sheet.paste(im, (gap + i * (pw + gap), hdr + th + gap))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"Saved {out_path}")


UNIFIED_PATHS = {
    "01_Miranda_LAS.png": "miranda/model/las/miranda_las_sheet.png",
    "11_Geralt_over_Rust.png": "geralt/model/over-rust/geralt_over_rust_sheet.png",
    "18_all_dist_mods_overview.png": "overview/model/all_dist_mods_sheet.png",
    "19_Miranda_L4D2_over_Hila.png": "miranda/model/over-hila/miranda_l4d2_over_hila_sheet.png",
    "24_OfficeSuite.png": "honoka/model/dae/officesuite_las_sheet.png",
    "25_OfficeSuite_over_Bunny.png": "honoka/model/over-bunny/officesuite_over_bunny_sheet.png",
    "30_Arivus_over_Hoxton.png": "arivus/model/over-hoxton/arivus_over_hoxton_sheet.png",
    "31_Miranda_LAS_fps.png": "miranda/model/las/miranda_las_fps_sheet.png",
    "35_OfficeSuite_fps.png": "honoka/model/dae/officesuite_las_fps_sheet.png",
    "36_OfficeSuite_over_Bunny_fps.png": "honoka/model/over-bunny/officesuite_over_bunny_fps_sheet.png",
    # not in the numbered overview: the wrist junction D75 changed, before and after the pass
    "37_OfficeSuite_wrist.png": "honoka/model/wrist/officesuite_wrist_ext30_twist.png",
    "38_OfficeSuite_over_Bunny_posed.png": "honoka/model/over-bunny/officesuite_over_bunny_posed_sheet.png",
    # D86 side-profile posture & throat contour comparison for Miranda_L4D2_over_Hila
    "39_Miranda_L4D2_over_Hila_posture.png": "miranda/model/over-hila/miranda_l4d2_over_hila_posture_before-after.png",
}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None,
                    help="output directory (default: build/previews, or docs/renders with --unified)")
    ap.add_argument("--unified", action="store_true",
                    help="write sheets into <out>/<project>/model/... per docs/renders/README.md")
    ap.add_argument("--only-wrist", action="store_true",
                    help="render only the OfficeSuite wrist junction (the D75 comparison)")
    ap.add_argument("--only-hila-posture", action="store_true",
                    help="render only the Miranda_L4D2_over_Hila forward posture before/after sheet (D86)")
    ap.add_argument("--only-officesuite", action="store_true",
                    help="render only the OfficeSuite LAS sheet, with its FPS arms panel")
    args = ap.parse_args(argv)
    out_dir = args.out or (ROOT / "docs" / "renders" if args.unified else ROOT / "build" / "previews")
    out_dir.mkdir(parents=True, exist_ok=True)

    def target_for(name: str) -> Path:
        if args.unified:
            return out_dir / UNIFIED_PATHS[name]
        return out_dir / name

    if args.only_hila_posture:
        render_hila_posture_sheet(target_for("39_Miranda_L4D2_over_Hila_posture.png"))
        return

    if args.only_wrist:
        import wrist_compare

        wrist_compare.render(
            target_for("37_OfficeSuite_wrist.png"),
            before=None,
            body=Path(os.environ["OFFICESUITE_SKIN_MODEL"]) if "OFFICESUITE_SKIN_MODEL" in os.environ
            else ROOT / "build/honoko2/officesuite/officesuite.model",
        )
        return

    if args.only_officesuite:
        tpp_os, fps_os, icon_os = load_multi_mat_las_parts(
            dist_path(ROOT, "OfficeSuite.zip"), "OfficeSuite", "officesuite", has_fps=True
        )
        th_os = render_las_sheet(
            "dist/Miranda/OfficeSuite.zip — Body-Only LAS Outfit, slim, black suit (DOAXVV Honoka Secret Report DAE)",
            "The 5% slim, cleared geometry in the user's revised third suit & jewelry colourway, palms cut on the line where they begin, no extension past it (D70); wrist twisted on ForeArmRoll and its cut ring centred on the glove (D75) | fps_officesuite.model | "
            "Source: Honoka_DOAXVV_Secret_Reportout.dae + Tex_07(L_7)3.dds + Tex_23(L_23)2.dds",
            tpp_os,
            fps_os,
            icon_os,
            target_for("24_OfficeSuite.png"),
            has_head=False,
        )
        render_fps_sheet(
            "dist/Miranda/OfficeSuite.zip — First-Person Arms (fps_officesuite.model)",
            "Player, three-quarter, side and top-down views, auto-framed | sleeves, cuffs and jewelry cuff, ending at the palm line, the bracelet on the forearm's roll",
            fps_os,
            target_for("35_OfficeSuite_fps.png"),
        )
        return

    thumbs: list[tuple[str, Image.Image]] = []

    tpp_mir, fps_mir, icon_mir = load_miranda_las_parts()
    th_mir = render_las_sheet(
        "dist/Miranda_L4D2/Miranda_L4D2_LAS.zip — Full-Body LAS Outfit (L4D2 Port)",
        "Legendary Armour Skins (LAS) full-body outfit + first-person arms | Source: l4d2_miranda_lawson_1.zip",
        tpp_mir,
        fps_mir,
        icon_mir,
        target_for("01_Miranda_LAS.png"),
    )
    render_fps_sheet(
        "dist/Miranda_L4D2/Miranda_L4D2_LAS.zip — First-Person Arms (fps_miranda.model)",
        "Player, three-quarter, side and top-down views, auto-framed | the L4D2 outfit's arms unit, hands only",
        fps_mir,
        target_for("31_Miranda_LAS_fps.png"),
    )

    tpp_os, fps_os, icon_os = load_multi_mat_las_parts(
        dist_path(ROOT, "OfficeSuite.zip"), "OfficeSuite", "officesuite", has_fps=True
    )
    th_os = render_las_sheet(
        "dist/Miranda/OfficeSuite.zip — Body-Only LAS Outfit, slim, black suit (DOAXVV Honoka Secret Report DAE)",
        "The 5% slim, cleared geometry in the user's revised third suit & jewelry colourway, palms cut on the line where they begin, no extension past it (D70); wrist twisted on ForeArmRoll (D75) | First-person arms unit | "
        "Source: Honoka_DOAXVV_Secret_Reportout.dae + Tex_07(L_7)3.dds + Tex_23(L_23)2.dds",
        tpp_os,
        fps_os,
        icon_os,
        target_for("24_OfficeSuite.png"),
        has_head=False,
    )
    render_fps_sheet(
        "dist/Miranda/OfficeSuite.zip — First-Person Arms (fps_officesuite.model)",
        "Player, three-quarter, side and top-down views, auto-framed | sleeves, cuffs and jewelry cuff, ending at the palm line, the bracelet on the forearm's roll",
        fps_os,
        target_for("35_OfficeSuite_fps.png"),
    )

    tpp_bunny, fps_bunny, icon_bunny = load_bunny_body_parts(
        dist_path(ROOT, "OfficeSuite_over_Bunny.zip")
    )
    th_bunny = render_las_sheet(
        "dist/Miranda/OfficeSuite_over_Bunny.zip — Native mod_overrides Outfit over Hop to It (bunny)",
        "Replaces all 5 third-person ccmt_acc_bunny_*.model variants + ccmt_acc_fps_bunny_male.model + bunny.texture icon | 4096x2048 BC3 6-tile atlas (D85), no BeardLib / LAS",
        tpp_bunny,
        fps_bunny,
        icon_bunny,
        target_for("25_OfficeSuite_over_Bunny.png"),
        has_head=False,
    )
    render_fps_sheet(
        "dist/Miranda/OfficeSuite_over_Bunny.zip — First-Person Arms (ccmt_acc_fps_bunny_male.model)",
        "Player, three-quarter, side and top-down views, auto-framed | shifted into the bunny FPS rig frame, inside co_box bounds",
        fps_bunny,
        target_for("36_OfficeSuite_over_Bunny_fps.png"),
    )
    render_bunny_posed_audit_sheet(
        dist_path(ROOT, "OfficeSuite_over_Bunny.zip"),
        dist_path(ROOT, "OfficeSuite.zip"),
        dist_path(ROOT, "Miranda_L4D2_over_Hila.zip"),
        tpp_bunny,
        fps_bunny,
        icon_bunny,
        target_for("38_OfficeSuite_over_Bunny_posed.png"),
    )

    heister_specs = [
        (
            "11_Geralt_over_Rust.png",
            "Geralt_over_Rust.zip",
            "units/pd2_dlc_wild/characters/npc_criminals_wild_1/npc_criminal_wild_1.model",
            "units/pd2_dlc_wild/characters/npc_criminals_wild_1/npc_criminal_wild_1_head_df.texture",
            "units/pd2_dlc_wild/characters/npc_criminals_wild_1/npc_criminal_wild_1_head_df.texture",
            "guis/dlcs/wild/textures/pd2/blackmarket/icons/characters/wild.texture",
            "g_head",
            (64, 58, 52),
            (48, 44, 42),
            "dist/Geralt/Geralt_over_Rust.zip — Rust Head Replacement (Witcher 3 Geralt of Rivia)",
            "Replaces Rust's head, hair & beard (heist, menu & Safe House chill) + FPS gloves in TPS + character icon",
            "Geralt_over_Rust.zip",
        ),
        (
            "19_Miranda_L4D2_over_Hila.png",
            "Miranda_L4D2_over_Hila.zip",
            "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female.model",
            "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_head_df.texture",
            "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_lashes_df.texture",
            "guis/dlcs/ecp/textures/pd2/blackmarket/icons/characters/ecp_female.texture",
            "g_head",
            (66, 60, 56),
            (48, 42, 40),
            "dist/Miranda/Miranda_L4D2_over_Hila.zip — Hila Head Replacement (L4D2)",
            "Replaces Hila's head, hair & eyelashes (heist & menu models) + character icon | eyes: references/textures/EYE_Diff.png",
            "Miranda_L4D2_over_Hila.zip",
        ),
    ]

    for (
        out_name,
        zname,
        mrel,
        hdf,
        sdf,
        irel,
        hdraw,
        suit_c,
        glove_c,
        title,
        sub,
        short_lbl,
    ) in heister_specs:
        th = render_heister_head_sheet(
            zname,
            mrel,
            hdf,
            sdf,
            irel,
            hdraw,
            suit_c,
            glove_c,
            title,
            sub,
            target_for(out_name),
        )
        thumbs.append((short_lbl, th))

    # Arivus replaces a drawable inside the shared suit model, so its frame sits a
    # little higher than the female heisters' heads and needs its own portrait framing.
    th_arivus = render_heister_head_sheet(
        "Arivus_over_Hoxton.zip",
        "units/payday2/characters/npc_criminals_suit_1/npc_criminals_suit_1.model",
        "units/payday2/characters/shared_textures/old_hoxton_head_df.texture",
        "units/payday2/characters/shared_textures/old_hoxton_head_df.texture",
        "guis/textures/pd2/blackmarket/icons/characters/old_hoxton.texture",
        "g_head_old_hoxton",
        (58, 62, 68),
        (42, 44, 48),
        "Arivus over Old Hoxton — supplied diffuse",
        "Arivus mesh and hair; user-supplied old_hoxton_head_df(1).dds | Offline preview",
        target_for("30_Arivus_over_Hoxton.png"),
        portrait=(173.8, 10.8),
        full=(82.0, 2.55),
    )

    # Complete dist/ overview grid: every tracked pack's model sheet
    tw, th_h = 330, 440
    all_dist_cells = [
        ("Miranda_L4D2_LAS.zip", th_mir),
        ("OfficeSuite.zip", th_os),
        ("OfficeSuite_over_Bunny.zip", th_bunny),
        *thumbs,  # Geralt, Hila L4D2
        ("Arivus_over_Hoxton.zip", th_arivus),
    ]
    rows = (len(all_dist_cells) + 5) // 6
    grid = Image.new("RGB", (tw * 6, th_h * rows + 58), (16, 19, 26))
    add_header_and_badges(
        grid,
        f"PAYDAY 2 — All {len(all_dist_cells)} Model Packages in dist/ (Complete Overview)",
        "Miranda L4D2 LAS | OfficeSuite (LAS & Hop to It override) | Geralt, Arivus, Hila | the audio-only pack"
        " (Miranda_Lawson_VO_over_Hila_Stream) has no model sheet"
        " (the Geralt/Arivus VO packs were retired and deleted 2026-11-28, D89)",
    )
    for idx, (lbl, im) in enumerate(all_dist_cells):
        row_i, col_i = divmod(idx, 6)
        cell = im.resize((tw, th_h), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(cell)
        d.rectangle([6, 6, tw - 6, 30], fill=(14, 17, 24))
        d.text((12, 10), lbl, fill=(240, 245, 255), font=FONT_BOLD_13)
        grid.paste(cell, (col_i * tw, 58 + row_i * th_h))

    dist_ov_path = target_for("18_all_dist_mods_overview.png")
    dist_ov_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(dist_ov_path)
    print(f"Saved {dist_ov_path}")

    render_hila_posture_sheet(target_for("39_Miranda_L4D2_over_Hila_posture.png"))


if __name__ == "__main__":
    main()
