#!/usr/bin/env python3
"""Render high-resolution PNG preview sheets for all 10 PAYDAY 2 Miranda Lawson mods in `dist/`.

Outputs to `docs/previews/`:
  - `00_all_miranda_mods_overview.png`
  - `01_Miranda_LAS.png`
  - `02_lawson_las.png`
  - `03_Miranda_L4D2_over_Joy.png`
  - `04_Miranda_Romance_over_Joy.png`
  - `05_Miranda_L4D2_over_Clover.png`
  - `06_Miranda_Romance_over_Clover.png`
  - `07_Miranda_L4D2_over_Bonnie.png`
  - `08_Miranda_Romance_over_Bonnie.png`
  - `09_Miranda_L4D2_over_Sydney.png`
  - `10_Miranda_Romance_over_Sydney.png`
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
sys.path.insert(0, str(ROOT / "tools" / "pd2-port"))

import diesel_model as dm  # noqa: E402
import dmodel  # noqa: E402

FONT_BOLD_16 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
FONT_BOLD_13 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
FONT_REG_12 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
FONT_REG_11 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)


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
) -> Image.Image:
    """Vectorized NumPy Z-buffer rasterizer with 2x SSAA anti-aliasing."""
    W2, H2 = W * 2, H * 2
    scale2 = scale * 2.0

    rad = np.deg2rad(deg)
    c, s = np.cos(rad), np.sin(rad)
    Rz = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)

    if abs(pitch_deg) > 1e-4:
        prad = np.deg2rad(pitch_deg)
        cp, sp = np.cos(prad), np.sin(prad)
        Rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
        R = Rx @ Rz
    else:
        R = Rz

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
        sx = (W2 * 0.5 + pr[:, 0] * scale2).astype(np.float32)
        sy = (H2 * 0.5 - (pr[:, 2] - z_center) * scale2).astype(np.float32)
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
        bx, by = W - 104, 68
        draw.rectangle([bx - 3, by - 3, bx + 90, by + 90], fill=(14, 16, 22), outline=(80, 140, 220), width=2)
        canvas.paste(ic, (bx, by), ic if ic.mode == "RGBA" else None)
        draw.text((bx + 2, by + 94), "HUD / Menu Icon", fill=(190, 205, 225), font=FONT_REG_11)
    return canvas


def load_miranda_las_parts() -> tuple[list, list, Image.Image]:
    """Load TPP and FPS parts + icon from dist/Miranda_LAS.zip."""
    with zipfile.ZipFile(ROOT / "dist" / "Miranda_LAS.zip") as zf:
        mf_tpp = dm.ModelFile.read(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model"))
        mf_fps = dm.ModelFile.read(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/fps_miranda.model"))
        body_df = np.asarray(Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_body_df.texture"))).convert("RGBA"))
        face_df = np.asarray(Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_face_df.texture"))).convert("RGBA"))
        head_df = np.asarray(Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_head_df.texture"))).convert("RGBA"))
        eyes_df = np.asarray(Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda_eyes.texture"))).convert("RGBA"))
        icon_im = Image.open(io.BytesIO(zf.read("Miranda_LAS/assets/guis/dlcs/miranda/armor_skins/miranda.texture"))).convert("RGBA")

    # TPP body (md 93)
    md_b = dm.decode_model_data(mf_tpp.by_id(93).payload)
    pg_b = dm.decode_passthroughgp(mf_tpp.by_id(md_b["passthroughgp"]).payload)
    geo_b = dm.decode_geometry(mf_tpp.by_id(pg_b["geometry"]).payload)
    topo_b = np.array(dm.decode_topology(mf_tpp.by_id(pg_b["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)

    # TPP head (md 94)
    md_h = dm.decode_model_data(mf_tpp.by_id(94).payload)
    pg_h = dm.decode_passthroughgp(mf_tpp.by_id(md_h["passthroughgp"]).payload)
    geo_h = dm.decode_geometry(mf_tpp.by_id(pg_h["geometry"]).payload)
    topo_h = np.array(dm.decode_topology(mf_tpp.by_id(pg_h["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)

    vh = np.asarray(geo_h["verts"], np.float32)
    nh = np.asarray(geo_h["normals"], np.float32)
    uvh = np.asarray(geo_h["uv0"], np.float32)

    head_tex_map = {0: eyes_df, 1: face_df, 2: head_df, 3: head_df}
    tpp_parts = [
        (
            np.asarray(geo_b["verts"], np.float32),
            np.asarray(geo_b["normals"], np.float32),
            topo_b,
            np.asarray(geo_b["uv0"], np.float32),
            body_df,
            False,
            True,
        )
    ]
    for atom in md_h["atoms"]:
        bi, tc, mid = atom["base_index"], atom["tri_count"], atom["material_id"]
        tpp_parts.append(
            (vh, nh, topo_h[bi // 3 : bi // 3 + tc], uvh, head_tex_map[mid], False, False)
        )

    # FPS arms (md 93)
    md_f = dm.decode_model_data(mf_fps.by_id(93).payload)
    pg_f = dm.decode_passthroughgp(mf_fps.by_id(md_f["passthroughgp"]).payload)
    geo_f = dm.decode_geometry(mf_fps.by_id(pg_f["geometry"]).payload)
    topo_f = np.array(dm.decode_topology(mf_fps.by_id(pg_f["topology"]).payload)["indices"], dtype=np.int32).reshape(-1, 3)
    fps_parts = [
        (
            np.asarray(geo_f["verts"], np.float32),
            np.asarray(geo_f["normals"], np.float32),
            topo_f,
            np.asarray(geo_f["uv0"], np.float32),
            body_df,
            False,
            True,
        )
    ]
    return tpp_parts, fps_parts, icon_im


def load_lawson_las_parts() -> tuple[list, list, Image.Image]:
    """Load TPP and FPS parts + icon from dist/lawson_las.zip."""
    with zipfile.ZipFile(ROOT / "dist" / "lawson_las.zip") as zf:
        m_tpp = dmodel.DieselModel.from_bytes(zf.read("Lawson_LAS/assets/units/lawson/skins/lawson/lawson.model"))
        m_fps = dmodel.DieselModel.from_bytes(zf.read("Lawson_LAS/assets/units/lawson/skins/lawson/fps_lawson.model"))
        tex = {}
        for stem in ("body1", "body2", "face", "hair", "eyes", "lashes", "teeth", "mouth"):
            tex[stem] = np.asarray(
                Image.open(io.BytesIO(zf.read(f"Lawson_LAS/assets/units/lawson/skins/lawson/{stem}_df.texture"))).convert("RGBA")
            )
        icon_im = Image.open(io.BytesIO(zf.read("Lawson_LAS/assets/guis/dlcs/lawson/armor_skins/lawson.texture"))).convert("RGBA")

    tpp_parts = []
    # Body (id=74, geo=77, topo=78)
    md_b = m_tpp.by_id[74].obj
    geo_b = m_tpp.by_id[77].obj
    topo_b = np.asarray(m_tpp.by_id[78].obj.faces, dtype=np.int32)
    vb = np.asarray(geo_b.positions, np.float32)
    nb = np.asarray(geo_b.normals, np.float32)
    uvb = np.asarray(geo_b.uvs, np.float32)
    body_mats = {0: tex["body1"], 1: tex["body2"]}
    for atom in md_b.render_atoms:
        bi, tc, mid = atom["base_index"], atom["tri_count"], atom["material_id"]
        tpp_parts.append((vb, nb, topo_b[bi // 3 : bi // 3 + tc], uvb, body_mats[mid], False, False))

    # Head (id=75, geo=82, topo=83)
    md_h = m_tpp.by_id[75].obj
    geo_h = m_tpp.by_id[82].obj
    topo_h = np.asarray(m_tpp.by_id[83].obj.faces, dtype=np.int32)
    vh = np.asarray(geo_h.positions, np.float32)
    nh = np.asarray(geo_h.normals, np.float32)
    uvh = np.asarray(geo_h.uvs, np.float32)
    head_mats = {
        0: (tex["face"], False),
        1: (tex["hair"], False),
        2: (tex["eyes"], False),
        3: (tex["lashes"], True),
        4: (tex["teeth"], False),
        5: (tex["mouth"], False),
    }
    for atom in md_h.render_atoms:
        bi, tc, mid = atom["base_index"], atom["tri_count"], atom["material_id"]
        t_img, is_cut = head_mats[mid]
        tpp_parts.append((vh, nh, topo_h[bi // 3 : bi // 3 + tc], uvh, t_img, is_cut, False))

    # FPS arms (id=67, geo=69, topo=70)
    md_f = m_fps.by_id[67].obj
    geo_f = m_fps.by_id[69].obj
    topo_f = np.asarray(m_fps.by_id[70].obj.faces, dtype=np.int32)
    vf = np.asarray(geo_f.positions, np.float32)
    nf = np.asarray(geo_f.normals, np.float32)
    uvf = np.asarray(geo_f.uvs, np.float32)
    fps_parts = []
    for atom in md_f.render_atoms:
        bi, tc, mid = atom["base_index"], atom["tri_count"], atom["material_id"]
        fps_parts.append((vf, nf, topo_f[bi // 3 : bi // 3 + tc], uvf, body_mats[mid], False, False))

    return tpp_parts, fps_parts, icon_im


def render_las_sheet(
    title: str,
    subtitle: str,
    tpp_parts: list,
    fps_parts: list,
    icon_im: Image.Image,
    out_path: Path,
) -> Image.Image:
    W_col, H_row = 360, 540
    canvas = Image.new("RGB", (W_col * 4, H_row + 58), (18, 22, 30))

    p_front = rasterize_parts(tpp_parts, W_col, H_row, 0, 92.0, 2.75)
    p_34 = rasterize_parts(tpp_parts, W_col, H_row, 34, 92.0, 2.75)
    p_back = rasterize_parts(tpp_parts, W_col, H_row, 180, 92.0, 2.75)

    p_head = rasterize_parts(tpp_parts, W_col, H_row // 2, 18, 166.5, 11.5, z_min_clip=138.0)
    p_fps = rasterize_parts(fps_parts, W_col, H_row // 2, 20, 129.0, 3.2, pitch_deg=15.0)

    for i, (im, lbl) in enumerate([
        (p_front, "Full-Body Front (0°)"),
        (p_34, "Full-Body 3/4 View (34°)"),
        (p_back, "Full-Body Back (180°)"),
    ]):
        d = ImageDraw.Draw(im)
        d.rectangle([8, H_row - 30, 215, H_row - 8], fill=(14, 17, 24))
        d.text((14, H_row - 26), lbl, fill=(230, 235, 245), font=FONT_REG_12)
        canvas.paste(im, (i * W_col, 58))

    d_h = ImageDraw.Draw(p_head)
    d_h.rectangle([8, H_row // 2 - 30, 225, H_row // 2 - 8], fill=(14, 17, 24))
    d_h.text((14, H_row // 2 - 26), "Close-Up Portrait (18°)", fill=(230, 235, 245), font=FONT_REG_12)
    canvas.paste(p_head, (3 * W_col, 58))

    d_f = ImageDraw.Draw(p_fps)
    d_f.rectangle([8, H_row // 2 - 30, 240, H_row // 2 - 8], fill=(14, 17, 24))
    d_f.text((14, H_row // 2 - 26), "First-Person Arms (fps_*.model)", fill=(230, 235, 245), font=FONT_REG_12)
    canvas.paste(p_fps, (3 * W_col, 58 + H_row // 2))

    add_header_and_badges(canvas, title, subtitle, icon_im)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Saved {out_path}")
    return rasterize_parts(tpp_parts, 360, 480, 24, 147.0, 5.8, z_min_clip=105.0)


def render_heister_head_sheet(
    zip_name: str,
    model_rel: str,
    head_df_rel: str,
    sec_df_rel: str,
    icon_rel: str,
    head_draw_name: str,
    suit_rgb: tuple[int, int, int],
    glove_rgb: tuple[int, int, int],
    is_rom: bool,
    title: str,
    subtitle: str,
    out_path: Path,
) -> Image.Image:
    zp = ROOT / "dist" / zip_name
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


def main() -> None:
    out_dir = ROOT / "docs" / "previews"
    out_dir.mkdir(parents=True, exist_ok=True)

    thumbs: list[tuple[str, Image.Image]] = []

    tpp_mir, fps_mir, icon_mir = load_miranda_las_parts()
    th_mir = render_las_sheet(
        "dist/Miranda_LAS.zip — Full-Body LAS Outfit (L4D2 Port)",
        "Legendary Armour Skins (LAS) full-body outfit + first-person arms | Source: l4d2_miranda_lawson_1.zip",
        tpp_mir,
        fps_mir,
        icon_mir,
        out_dir / "01_Miranda_LAS.png",
    )
    thumbs.append(("Miranda_LAS.zip (Full-Body L4D2)", th_mir))

    tpp_law, fps_law, icon_law = load_lawson_las_parts()
    th_law = render_las_sheet(
        "dist/lawson_las.zip — Full-Body LAS Outfit (ME2 Romance Port)",
        "Legendary Armour Skins (LAS) full-body outfit + first-person arms | Source: Mass Effect 2 Miranda (Romance)",
        tpp_law,
        fps_law,
        icon_law,
        out_dir / "02_lawson_las.png",
    )
    thumbs.append(("lawson_las.zip (Full-Body ME2)", th_law))

    heister_specs = [
        (
            "03_Miranda_L4D2_over_Joy.png",
            "Miranda_L4D2_over_Joy.zip",
            "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model",
            "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_head_df.texture",
            "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_lashes_df.texture",
            "guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture",
            "g_head",
            (62, 70, 88),
            (45, 48, 55),
            False,
            "dist/Miranda_L4D2_over_Joy.zip — Joy Head Replacement (L4D2)",
            "Replaces Joy's head & hair (npc_criminal_joy_1.model + _menu.model) and character icon",
            "Miranda_L4D2_over_Joy.zip",
        ),
        (
            "04_Miranda_Romance_over_Joy.png",
            "Miranda_Romance_over_Joy.zip",
            "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model",
            "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_head_df.texture",
            "units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1_lashes_df.texture",
            "guis/dlcs/joy/textures/pd2/blackmarket/icons/characters/joy.texture",
            "g_head",
            (62, 70, 88),
            (45, 48, 55),
            True,
            "dist/Miranda_Romance_over_Joy.zip — Joy Head Replacement (ME2 Romance)",
            "Replaces Joy's head & hair with ME2 Romance head + alpha-masked eyelashes and character icon",
            "Miranda_Romance_over_Joy.zip",
        ),
        (
            "05_Miranda_L4D2_over_Clover.png",
            "Miranda_L4D2_over_Clover.zip",
            "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model",
            "units/payday2/characters/shared_textures/clover_head_df.texture",
            "units/payday2/characters/shared_textures/npc_criminal_female_1_hair_df.texture",
            "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture",
            "g_head_fem1",
            (58, 66, 64),
            (70, 125, 185),
            False,
            "dist/Miranda_L4D2_over_Clover.zip — Clover Head Replacement (L4D2)",
            "Replaces Clover's head & hair (heist, menu & Safe House chill) + FPS gloves in TPS + character icon",
            "Miranda_L4D2_over_Clover.zip",
        ),
        (
            "06_Miranda_Romance_over_Clover.png",
            "Miranda_Romance_over_Clover.zip",
            "units/payday2/characters/npc_criminal_female_1/npc_criminal_female_1.model",
            "units/payday2/characters/shared_textures/clover_head_df.texture",
            "units/payday2/characters/shared_textures/npc_criminal_female_1_hair_df.texture",
            "guis/dlcs/character_pack_clover/textures/pd2/blackmarket/icons/characters/female_1.texture",
            "g_head_fem1",
            (58, 66, 64),
            (70, 125, 185),
            True,
            "dist/Miranda_Romance_over_Clover.zip — Clover Head Replacement (ME2 Romance)",
            "Replaces Clover's head & hair (heist, menu & Safe House chill) + FPS gloves in TPS + character icon",
            "Miranda_Romance_over_Clover.zip",
        ),
        (
            "07_Miranda_L4D2_over_Bonnie.png",
            "Miranda_L4D2_over_Bonnie.zip",
            "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model",
            "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie_head_df.texture",
            "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie_hair_df.texture",
            "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture",
            "g_head",
            (64, 72, 86),
            (70, 125, 185),
            False,
            "dist/Miranda_L4D2_over_Bonnie.zip — Bonnie Head Replacement (L4D2)",
            "Replaces Bonnie's head & hair (heist, menu & Safe House chill) + FPS gloves in TPS + character icon",
            "Miranda_L4D2_over_Bonnie.zip",
        ),
        (
            "08_Miranda_Romance_over_Bonnie.png",
            "Miranda_Romance_over_Bonnie.zip",
            "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie.model",
            "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie_head_df.texture",
            "units/pd2_dlc_bonnie/characters/npc_criminal_bonnie/npc_criminal_bonnie_hair_df.texture",
            "guis/dlcs/character_pack_bonnie/textures/pd2/blackmarket/icons/characters/bonnie.texture",
            "g_head",
            (64, 72, 86),
            (70, 125, 185),
            True,
            "dist/Miranda_Romance_over_Bonnie.zip — Bonnie Head Replacement (ME2 Romance)",
            "Replaces Bonnie's head & hair (heist, menu & Safe House chill) + FPS gloves in TPS + character icon",
            "Miranda_Romance_over_Bonnie.zip",
        ),
        (
            "09_Miranda_L4D2_over_Sydney.png",
            "Miranda_L4D2_over_Sydney.zip",
            "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
            "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_fem_3_head_df.texture",
            "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_fem_3_hair_df.texture",
            "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture",
            "g_head",
            (52, 62, 82),
            (70, 125, 185),
            False,
            "dist/Miranda_L4D2_over_Sydney.zip — Sydney Head Replacement (L4D2)",
            "Replaces Sydney's head & hair (heist & menu) + FPS gloves in TPS + character icon",
            "Miranda_L4D2_over_Sydney.zip",
        ),
        (
            "10_Miranda_Romance_over_Sydney.png",
            "Miranda_Romance_over_Sydney.zip",
            "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
            "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_fem_3_head_df.texture",
            "units/pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_fem_3_hair_df.texture",
            "guis/dlcs/opera/textures/pd2/blackmarket/icons/characters/sydney.texture",
            "g_head",
            (52, 62, 82),
            (70, 125, 185),
            True,
            "dist/Miranda_Romance_over_Sydney.zip — Sydney Head Replacement (ME2 Romance)",
            "Replaces Sydney's head & hair (heist & menu) + FPS gloves in TPS + character icon",
            "Miranda_Romance_over_Sydney.zip",
        ),
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
            True,
            "dist/Geralt_over_Rust.zip — Rust Head Replacement (Witcher 3 Geralt of Rivia)",
            "Replaces Rust's head, hair & beard (heist, menu & Safe House chill) + FPS gloves in TPS + character icon",
            "Geralt_over_Rust.zip",
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
        is_rom,
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
            is_rom,
            title,
            sub,
            out_dir / out_name,
        )
        thumbs.append((short_lbl, th))

    # Build master overview grid (5 columns x 2 rows, exact 3:4 aspect ratio)
    tw, th_h = 330, 440
    overview = Image.new("RGB", (tw * 5, th_h * 2 + 58), (16, 19, 26))
    add_header_and_badges(
        overview,
        "PAYDAY 2 — All 10 Miranda Lawson Mod Packages in dist/ (Overview)",
        "Top row: L4D2 variants (Full-Body LAS, Joy, Clover, Bonnie, Sydney) | Bottom row: ME2 Romance variants",
    )
    # Order: L4D2 row (0, 2, 4, 6, 8), Romance row (1, 3, 5, 7, 9)
    l4d2_indices = [0, 2, 4, 6, 8]
    rom_indices = [1, 3, 5, 7, 9]
    for col_i, idx in enumerate(l4d2_indices):
        lbl, im = thumbs[idx]
        cell = im.resize((tw, th_h), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(cell)
        d.rectangle([6, 6, tw - 6, 30], fill=(14, 17, 24))
        d.text((12, 10), lbl, fill=(240, 245, 255), font=FONT_BOLD_13)
        overview.paste(cell, (col_i * tw, 58))
    for col_i, idx in enumerate(rom_indices):
        lbl, im = thumbs[idx]
        cell = im.resize((tw, th_h), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(cell)
        d.rectangle([6, 6, tw - 6, 30], fill=(14, 17, 24))
        d.text((12, 10), lbl, fill=(240, 245, 255), font=FONT_BOLD_13)
        overview.paste(cell, (col_i * tw, 58 + th_h))

    ov_path = out_dir / "00_all_miranda_mods_overview.png"
    overview.save(ov_path)
    print(f"Saved {ov_path}")


if __name__ == "__main__":
    main()
