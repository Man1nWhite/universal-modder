#!/usr/bin/env python3
"""Render high-resolution PNG preview sheets for every PAYDAY 2 mod package in `dist/`.

By default outputs to `build/previews/` (gitignored scratch). Pass `--unified` to emit into
`docs/renders/<project>/model/...` per `docs/renders/README.md`:
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
  - `11_Geralt_over_Rust.png`
  - `12_Miranda_Busty_LAS.png` (chest-morph variant of 01)
  - `13_Miranda_Busty_vs_LAS_chest.png` (before/after chest close-up)
  - `14_Miranda_Busty_vs_LAS_top_below.png` (overhead/underside chest comparison)
  - `15_Christie_LAS.png` (DOA5 Christie body-only LAS outfit)
  - `16_Christie_LAS_Slim.png` (DOA5 Christie Slim body-only LAS outfit)
  - `17_Honoko2.png` (DOAXVV Honoka Secret Report body-only LAS outfit, built from `.dae`)
  - `18_all_dist_mods_overview.png` (6x4 grid of all 19 packs in `dist/`)
  - `19_Miranda_L4D2_over_Hila.png`
  - `20_Miranda_Romance_over_Hila.png`
  - `21_Honoko3.png` (the same outfit 5% slimmer, scaled about the rig's bones)
  - `22_Honoko4.png` (Honoko3's geometry in the user's alternate suit colourway)
  - `23_Honoko4_with_Miranda_Romance_over_Hila.png` (Honoko4's body under the Miranda Romance
    over Hila head pack, the combination as installed)

`00_all_miranda_mods_overview.png` is the 6x2 grid of the twelve Miranda head/full-body packs.
"""
from __future__ import annotations

import argparse
import io
import sys
import xml.etree.ElementTree as ET
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


def _drawable_name(mf, name_hash: int) -> str:
    """Resolve a MODEL_DATA drawable hash through the file's own hashlist."""
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    for n in hl["names"]:
        if dm.hash64(n) == name_hash:
            return n
    return f"#{name_hash:016x}"


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
    """Load TPP and FPS parts + icon from dist/Miranda_LAS.zip."""
    return load_las_variant_parts(ROOT / "dist" / "Miranda_LAS.zip", "Miranda_LAS", "miranda")


def load_miranda_busty_parts() -> tuple[list, list, Image.Image]:
    """Load TPP and FPS parts + icon from dist/Miranda_Busty_LAS.zip."""
    return load_las_variant_parts(ROOT / "dist" / "Miranda_Busty_LAS.zip",
                                  "Miranda_Busty_LAS", "miranda_busty")


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
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    # the matcfg's own names fill any gap in the model's hashlist (the ecp unit's lists no mtr names)
    hmap = {dm.hash64(name): name for name in mat_to_asset}
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


def load_outfit_with_head_parts(
    outfit_zip: str, outfit_tag: str, outfit_prefix: str,
    head_zip: str, head_tag: str, head_unit: str, head_stem: str,
) -> tuple[list, Image.Image]:
    """One figure from two packs: a body-only LAS outfit plus a head pack's `g_head` drawable.

    The combination the game shows when both are installed (the outfit replaces the body, the head
    pack the head), rendered offline: both packs' models stand in the same character frame - the
    outfit's neck plug nests inside the head unit's neck by design (D44) - so their parts share one
    rasterizer call without any transform between them.
    """
    tpp_parts, _, icon_im = load_multi_mat_las_parts(
        ROOT / "dist" / outfit_zip, outfit_tag, outfit_prefix, has_fps=False
    )
    with zipfile.ZipFile(ROOT / "dist" / head_zip) as zf:
        unit = f"{head_tag}/{head_unit}/"
        mf = dm.ModelFile.read(zf.read(unit + f"{head_stem}.model"))
        mats = _parse_matcfg_diffuse(zf.read(unit + "mtr_criminal_ecp_female.material_config"))
        head_parts = _parts_from_model_with_matcfg(
            zf, head_tag, mf, mats, {}, drawable="g_head",
            cutout_materials=frozenset({"mtr_lashes"}), asset_root="",
        )
    return tpp_parts + head_parts, icon_im


def load_multi_mat_las_parts(
    zip_path: Path,
    tag: str,
    prefix: str,
    has_fps: bool = True,
) -> tuple[list, list, Image.Image]:
    """Load TPP (and optional FPS) multi-material parts + icon from a body-only LAS pack."""
    unit = f"{tag}/assets/units/{prefix}/skins/{prefix}/"
    tex_cache: dict[str, np.ndarray] = {}
    with zipfile.ZipFile(zip_path) as zf:
        mf_tpp = dm.ModelFile.read(zf.read(unit + f"{prefix}.model"))
        tpp_mats = _parse_matcfg_diffuse(zf.read(unit + f"{prefix}.material_config"))
        tpp_parts = _parts_from_model_with_matcfg(zf, tag, mf_tpp, tpp_mats, tex_cache)
        fps_parts: list = []
        if has_fps:
            mf_fps = dm.ModelFile.read(zf.read(unit + f"fps_{prefix}.model"))
            fps_mats = _parse_matcfg_diffuse(zf.read(unit + f"fps_{prefix}.material_config"))
            fps_parts = _parts_from_model_with_matcfg(zf, tag, mf_fps, fps_mats, tex_cache)
        icon_im = Image.open(
            io.BytesIO(zf.read(f"{tag}/assets/guis/dlcs/{prefix}/armor_skins/{prefix}.texture"))
        ).convert("RGBA")
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
    has_head: bool = True,
    closeup: tuple[float, float, float] = (18.0, 166.5, 11.5),
) -> Image.Image:
    W_col, H_row = 360, 540
    canvas = Image.new("RGB", (W_col * 4, H_row + 58), (18, 22, 30))

    z_full = 92.0 if has_head else 74.0
    s_full = 2.75 if has_head else 2.65
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
        p_bot = rasterize_parts(fps_parts, W_col, H_row // 2, 20, 129.0, 3.2, pitch_deg=15.0)
        bot_lbl = "First-Person Arms (fps_*.model)"
    else:
        p_bot = rasterize_parts(tpp_parts, W_col, H_row // 2, 90, 74.0, 1.40)
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


def render_busty_compare_sheet(
    tpp_base: list,
    tpp_variant: list,
    icon_im: Image.Image,
    out_path: Path,
) -> Image.Image:
    """Before/after chest close-up sheet for the `Miranda_Busty_LAS` morph."""
    W, H = 380, 470
    canvas = Image.new("RGB", (W * len(CHEST_VIEWS), (H + 22) * 2 + 58), (18, 22, 30))
    for row, (label, parts) in enumerate((("Miranda_LAS (stock)", tpp_base),
                                          ("Miranda_Busty_LAS", tpp_variant))):
        for col, (caption, yaw, pitch, scale, center) in enumerate(CHEST_VIEWS):
            img = rasterize_parts(parts, W, H, yaw, 141.0, scale,
                                  pitch_deg=pitch, center=center)
            d = ImageDraw.Draw(img)
            d.rectangle([8, H - 30, 250, H - 8], fill=(14, 17, 24))
            d.text((14, H - 26), f"{label} · {caption}", fill=(230, 235, 245),
                   font=FONT_REG_12)
            canvas.paste(img, (col * W, 58 + row * (H + 22)))
    add_header_and_badges(
        canvas,
        "dist/Miranda_Busty_LAS.zip — Chest Morph (Before / After)",
        "Same outfit, rig and textures; the bust pass grows the chest mass"
        " | chest close-up 0°, 30°, 45°, 60°, 90° (framing widens with the yaw)",
        icon_im,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Saved {out_path}")
    return rasterize_parts(tpp_variant, 360, 480, 24, 147.0, 5.8, z_min_clip=105.0)


def render_busty_polar_sheet(
    tpp_base: list,
    tpp_variant: list,
    icon_im: Image.Image,
    out_path: Path,
) -> Image.Image:
    """Overhead and underside chest sheet: the two angles the front views cannot reach.

    Above shows whether the placket hem and the cup rims stay clean from the neck down;
    below shows whether the cups still hang off the ribcage instead of merging into one
    cushion, which is where a `+y`-only chest push always gives itself away.
    """
    W, H = 620, 560
    canvas = Image.new("RGB", (W * len(CHEST_POLAR_VIEWS), (H + 22) * 2 + 58),
                       (18, 22, 30))
    for row, (label, parts) in enumerate((("Miranda_LAS (stock)", tpp_base),
                                          ("Miranda_Busty_LAS", tpp_variant))):
        for col, (caption, yaw, pitch) in enumerate(CHEST_POLAR_VIEWS):
            center = (0.0, 18.0, 146.5) if pitch < 0.0 else (0.0, 20.0, 134.0)
            img = rasterize_parts(parts, W, H, yaw, 0.0, 12.6,
                                  pitch_deg=pitch, center=center)
            d = ImageDraw.Draw(img)
            d.rectangle([8, H - 32, 250, H - 8], fill=(14, 17, 24))
            d.text((14, H - 28), f"{label} · {caption}", fill=(230, 235, 245),
                   font=FONT_REG_12)
            canvas.paste(img, (col * W, 58 + row * (H + 22)))
    add_header_and_badges(
        canvas,
        "dist/Miranda_Busty_LAS.zip — Chest Morph, Overhead & Underside",
        "The same chest read from 58° above and from 58° below — stock above, variant below",
        icon_im,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    print(f"Saved {out_path}")
    return canvas


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


UNIFIED_PATHS = {
    "00_all_miranda_mods_overview.png": "overview/model/all_miranda_mods_sheet.png",
    "01_Miranda_LAS.png": "miranda/model/las/miranda_las_sheet.png",
    "02_lawson_las.png": "lawson/model/lawson_las_sheet.png",
    "03_Miranda_L4D2_over_Joy.png": "miranda/model/over-joy/miranda_l4d2_over_joy_sheet.png",
    "04_Miranda_Romance_over_Joy.png": "miranda/model/over-joy/miranda_romance_over_joy_sheet.png",
    "05_Miranda_L4D2_over_Clover.png": "miranda/model/over-clover/miranda_l4d2_over_clover_sheet.png",
    "06_Miranda_Romance_over_Clover.png": "miranda/model/over-clover/miranda_romance_over_clover_sheet.png",
    "07_Miranda_L4D2_over_Bonnie.png": "miranda/model/over-bonnie/miranda_l4d2_over_bonnie_sheet.png",
    "08_Miranda_Romance_over_Bonnie.png": "miranda/model/over-bonnie/miranda_romance_over_bonnie_sheet.png",
    "09_Miranda_L4D2_over_Sydney.png": "miranda/model/over-sydney/miranda_l4d2_over_sydney_sheet.png",
    "10_Miranda_Romance_over_Sydney.png": "miranda/model/over-sydney/miranda_romance_over_sydney_sheet.png",
    "11_Geralt_over_Rust.png": "geralt/model/over-rust/geralt_over_rust_sheet.png",
    "12_Miranda_Busty_LAS.png": "miranda/model/busty/miranda_busty_las_sheet.png",
    "13_Miranda_Busty_vs_LAS_chest.png": "miranda/model/busty/miranda_busty_vs_las_chest_before-after.png",
    "14_Miranda_Busty_vs_LAS_top_below.png": "miranda/model/busty/miranda_busty_vs_las_top_below_before-after.png",
    "15_Christie_LAS.png": "christie/model/base/christie_las_sheet.png",
    "16_Christie_LAS_Slim.png": "christie/model/slim/christie_las_slim_sheet.png",
    "17_Honoko2.png": "honoka/model/dae/honoko2_las_sheet.png",
    "18_all_dist_mods_overview.png": "overview/model/all_dist_mods_sheet.png",
    "19_Miranda_L4D2_over_Hila.png": "miranda/model/over-hila/miranda_l4d2_over_hila_sheet.png",
    "20_Miranda_Romance_over_Hila.png": "miranda/model/over-hila/miranda_romance_over_hila_sheet.png",
    "21_Honoko3.png": "honoka/model/dae/honoko3_las_sheet.png",
    "22_Honoko4.png": "honoka/model/dae/honoko4_las_sheet.png",
    "23_Honoko4_with_Miranda_Romance_over_Hila.png":
        "honoka/model/dae/honoko4_with_miranda_romance_over_hila_sheet.png",
}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None,
                    help="output directory (default: build/previews, or docs/renders with --unified)")
    ap.add_argument("--unified", action="store_true",
                    help="write sheets into <out>/<project>/model/... per docs/renders/README.md")
    args = ap.parse_args(argv)
    out_dir = args.out or (ROOT / "docs" / "renders" if args.unified else ROOT / "build" / "previews")
    out_dir.mkdir(parents=True, exist_ok=True)

    def target_for(name: str) -> Path:
        if args.unified:
            return out_dir / UNIFIED_PATHS[name]
        return out_dir / name

    thumbs: list[tuple[str, Image.Image]] = []

    tpp_mir, fps_mir, icon_mir = load_miranda_las_parts()
    th_mir = render_las_sheet(
        "dist/Miranda_LAS.zip — Full-Body LAS Outfit (L4D2 Port)",
        "Legendary Armour Skins (LAS) full-body outfit + first-person arms | Source: l4d2_miranda_lawson_1.zip",
        tpp_mir,
        fps_mir,
        icon_mir,
        target_for("01_Miranda_LAS.png"),
    )
    thumbs.append(("Miranda_LAS.zip (Full-Body L4D2)", th_mir))

    tpp_law, fps_law, icon_law = load_lawson_las_parts()
    th_law = render_las_sheet(
        "dist/lawson_las.zip — Full-Body LAS Outfit (ME2 Romance Port)",
        "Legendary Armour Skins (LAS) full-body outfit + first-person arms | Source: Mass Effect 2 Miranda (Romance)",
        tpp_law,
        fps_law,
        icon_law,
        target_for("02_lawson_las.png"),
    )
    thumbs.append(("lawson_las.zip (Full-Body ME2)", th_law))

    tpp_bus, fps_bus, icon_bus = load_miranda_busty_parts()
    th_bus = render_las_sheet(
        "dist/Miranda_Busty_LAS.zip — Full-Body LAS Outfit, chest morph (L4D2 Port)",
        "The 01 outfit with a sculpted chest mass and its own LegendaryArmours.miranda_busty entry"
        " | Source: l4d2_miranda_lawson_1.zip + references/2b.rar",
        tpp_bus,
        fps_bus,
        icon_bus,
        target_for("12_Miranda_Busty_LAS.png"),
    )
    render_busty_compare_sheet(tpp_mir, tpp_bus, icon_bus,
                               target_for("13_Miranda_Busty_vs_LAS_chest.png"))
    render_busty_polar_sheet(tpp_mir, tpp_bus, icon_bus,
                             target_for("14_Miranda_Busty_vs_LAS_top_below.png"))

    tpp_chr, fps_chr, icon_chr = load_multi_mat_las_parts(
        ROOT / "dist" / "Christie_LAS.zip", "Christie_LAS", "christie", has_fps=True
    )
    th_chr = render_las_sheet(
        "dist/Christie_LAS.zip — Body-Only LAS Outfit (DOA5 Christie)",
        "Legendary Armour Skins (LAS) headless body-only outfit + first-person arms | Source: DOA5 Christie",
        tpp_chr,
        fps_chr,
        icon_chr,
        target_for("15_Christie_LAS.png"),
        has_head=False,
    )

    tpp_chr_slim, fps_chr_slim, icon_chr_slim = load_multi_mat_las_parts(
        ROOT / "dist" / "Christie_LAS_Slim.zip", "Christie_LAS_Slim", "christie_slim", has_fps=True
    )
    th_chr_slim = render_las_sheet(
        "dist/Christie_LAS_Slim.zip — Body-Only LAS Outfit, Slim Variant (DOA5 Christie)",
        "Slim-variant headless body-only LAS outfit + first-person arms + glove adapter | Source: DOA5 Christie",
        tpp_chr_slim,
        fps_chr_slim,
        icon_chr_slim,
        target_for("16_Christie_LAS_Slim.png"),
        has_head=False,
    )

    tpp_hon2, fps_hon2, icon_hon2 = load_multi_mat_las_parts(
        ROOT / "dist" / "Honoko2.zip", "Honoko2", "honoko2", has_fps=False
    )
    th_hon2 = render_las_sheet(
        "dist/Honoko2.zip — Body-Only LAS Outfit (DOAXVV Honoka Secret Report DAE)",
        "Headless third-person body-only LAS outfit (no fps_unit) + glove adapter | Source: Honoka_DOAXVV_Secret_Reportout.dae",
        tpp_hon2,
        fps_hon2,
        icon_hon2,
        target_for("17_Honoko2.png"),
        has_head=False,
    )

    tpp_hon3, fps_hon3, icon_hon3 = load_multi_mat_las_parts(
        ROOT / "dist" / "Honoko3.zip", "Honoko3", "honoko3", has_fps=False
    )
    th_hon3 = render_las_sheet(
        "dist/Honoko3.zip — Body-Only LAS Outfit, 5% slimmer (DOAXVV Honoka Secret Report DAE)",
        "The same outfit scaled 5% about the rig's bones: same height and joints, slimmer girth | Source: Honoka_DOAXVV_Secret_Reportout.dae",
        tpp_hon3,
        fps_hon3,
        icon_hon3,
        target_for("21_Honoko3.png"),
        has_head=False,
    )

    tpp_hon4, fps_hon4, icon_hon4 = load_multi_mat_las_parts(
        ROOT / "dist" / "Honoko4.zip", "Honoko4", "honoko4", has_fps=False
    )
    th_hon4 = render_las_sheet(
        "dist/Honoko4.zip — Body-Only LAS Outfit, slim, alternate suit (DOAXVV Honoka Secret Report DAE)",
        "Honoko3's geometry in the user's alternate suit colourway (black jacket, orange shirt) | "
        "Source: Honoka_DOAXVV_Secret_Reportout.dae + Tex_07(L_7) 2.dds",
        tpp_hon4,
        fps_hon4,
        icon_hon4,
        target_for("22_Honoko4.png"),
        has_head=False,
    )

    combo_parts, icon_h4 = load_outfit_with_head_parts(
        "Honoko4.zip", "Honoko4", "honoko4",
        "Miranda_Romance_over_Hila.zip", "Miranda Romance over Hila",
        "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female", "npc_criminal_ecp_female",
    )
    render_las_sheet(
        "Honoko4 + Miranda Romance over Hila — the combination as installed",
        "Honoko4's body-only outfit under the Hila head pack's g_head (head + lashes); one character frame, no transform between the packs",
        combo_parts,
        [],
        icon_h4,
        target_for("23_Honoko4_with_Miranda_Romance_over_Hila.png"),
        has_head=True,
        closeup=(18.0, 170.0, 8.0),  # the Miranda head crowns at z 188, above the LAS-sheet default window
    )

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
            False,
            "dist/Miranda_L4D2_over_Hila.zip — Hila Head Replacement (L4D2)",
            "Replaces Hila's head, hair & eyelashes (heist & menu models) + character icon | eyes: references/EYE_Diff.png",
            "Miranda_L4D2_over_Hila.zip",
        ),
        (
            "20_Miranda_Romance_over_Hila.png",
            "Miranda_Romance_over_Hila.zip",
            "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female.model",
            "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_head_df.texture",
            "units/pd2_dlc_ecp/characters/npc_criminals_ecp_female/npc_criminal_ecp_female_lashes_df.texture",
            "guis/dlcs/ecp/textures/pd2/blackmarket/icons/characters/ecp_female.texture",
            "g_head",
            (66, 60, 56),
            (48, 42, 40),
            True,
            "dist/Miranda_Romance_over_Hila.zip — Hila Head Replacement (ME2 Romance)",
            "Replaces Hila's head, hair & eyelashes (heist & menu models) + character icon | eyes: references/EYE_Diff.png",
            "Miranda_Romance_over_Hila.zip",
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
            target_for(out_name),
        )
        thumbs.append((short_lbl, th))

    # Build master overview grid (6 columns x 2 rows, exact 3:4 aspect ratio)
    tw, th_h = 330, 440
    overview = Image.new("RGB", (tw * 6, th_h * 2 + 58), (16, 19, 26))
    add_header_and_badges(
        overview,
        "PAYDAY 2 — All 12 Miranda Lawson Mod Packages in dist/ (Overview)",
        "Top row: L4D2 variants (Full-Body LAS, Joy, Clover, Bonnie, Sydney, Hila) | Bottom row: ME2 Romance variants",
    )
    # Order: L4D2 row (0, 2, 4, 6, 8, Hila), Romance row (1, 3, 5, 7, 9, Hila)
    l4d2_indices = [0, 2, 4, 6, 8, 11]
    rom_indices = [1, 3, 5, 7, 9, 12]
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

    ov_path = target_for("00_all_miranda_mods_overview.png")
    ov_path.parent.mkdir(parents=True, exist_ok=True)
    overview.save(ov_path)
    print(f"Saved {ov_path}")

    # Build complete dist/ overview grid (6 columns x 4 rows = all 19 dist/*.zip packages)
    all_dist_cells = [
        *[thumbs[i] for i in l4d2_indices],
        *[thumbs[i] for i in rom_indices],
        ("Miranda_Busty_LAS.zip", th_bus),
        ("Christie_LAS.zip", th_chr),
        ("Christie_LAS_Slim.zip", th_chr_slim),
        ("Honoko2.zip", th_hon2),
        ("Honoko3.zip", th_hon3),
        ("Honoko4.zip", th_hon4),
        thumbs[10],  # Geralt_over_Rust.zip
    ]
    dist_overview = Image.new("RGB", (tw * 6, th_h * 4 + 58), (16, 19, 26))
    add_header_and_badges(
        dist_overview,
        "PAYDAY 2 — All 19 Mod Packages in dist/ (Complete Overview)",
        "L4D2 Miranda | ME2 Miranda | Busty, Christie, Christie Slim, Honoko2-4, Geralt",
    )
    for idx, (lbl, im) in enumerate(all_dist_cells):
        row_i, col_i = divmod(idx, 6)
        cell = im.resize((tw, th_h), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(cell)
        d.rectangle([6, 6, tw - 6, 30], fill=(14, 17, 24))
        d.text((12, 10), lbl, fill=(240, 245, 255), font=FONT_BOLD_13)
        dist_overview.paste(cell, (col_i * tw, 58 + row_i * th_h))

    dist_ov_path = target_for("18_all_dist_mods_overview.png")
    dist_ov_path.parent.mkdir(parents=True, exist_ok=True)
    dist_overview.save(dist_ov_path)
    print(f"Saved {dist_ov_path}")


if __name__ == "__main__":
    main()
