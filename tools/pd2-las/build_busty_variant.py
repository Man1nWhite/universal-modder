#!/usr/bin/env python3
"""Build `Miranda_Busty_LAS` — the Miranda outfit with a larger chest.

Same source, same retarget, same Diesel authoring as `tools/pd2-las`; the only
difference is a chest-mass morph (`bust_variant.ChestMorph`) applied to the
authored third-person groups between `build_models.transfer_group` and
`build_models.assemble_model`. The result is a *separate* LAS pack with its own
`LegendaryArmours.miranda_busty` id, unit paths and `mod_overrides` folder name,
so it installs side by side with `dist/Miranda_LAS.zip` instead of replacing it.

Usage (from the repo root):

    bash tools/pd2-las/bootstrap.sh          # textures + 2B templates + .venv
    .venv/bin/python tools/pd2-las/build_busty_variant.py \\
        --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

Outputs:
  build/pd2-las/Miranda_Busty_LAS/         pack folder (installable)
  build/pd2-las/Miranda_Busty_LAS.zip      + .sha256
  dist/Miranda_Busty_LAS.zip               + .sha256 (when --out is default)
  build/pd2-las/busty_variant_report.json  morph parameters + measured gains
  build/pd2-las/previews/busty_*.png       before/after preview sheets
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_OUT = (REPO / "build" / "pd2-las").resolve()
sys.path.insert(0, str(HERE))

import build_las  # noqa: E402
import build_models as bm  # noqa: E402
import bust_variant as bv  # noqa: E402
import las_pack  # noqa: E402
from source_model import load_model  # noqa: E402
from vpk import VpkArchive  # noqa: E402

IDENTITY = las_pack.PackIdentity(
    "miranda_busty",
    "Miranda Lawson (Busty)",
    ("Miranda Lawson joins the Payday Gang - Legendary Armour Skins outfit "
     "with a larger chest, built from the L4D2 Rochelle model."),
    pack_dir_name="Miranda_Busty_LAS",
)

CHEST_Z = (133.5, 150.5)


def _chest_indices(verts, morph: bv.ChestMorph) -> list[int]:
    idxs = []
    for idx, (x, y, z) in enumerate(verts):
        if CHEST_Z[0] <= z <= CHEST_Z[1] and morph.weight_at(x, y, z) > 0.02:
            idxs.append(idx)
    return idxs


def _measure(before, after, morph: bv.ChestMorph) -> dict:
    """Front reach / width / volume of the chest band, before and after."""
    base_idxs = _chest_indices(before, morph)
    if not base_idxs:
        return {}
    ba = np.asarray([before[i] for i in base_idxs], dtype=np.float64)
    # `after` keeps all original vertices as a prefix and appends subdivision
    # midpoints after `len(before)`. Measure peak reach over the full chest
    # band, and `volume_proxy` strictly over the identical `base_idxs` set.
    after_band = [
        p for p in after
        if CHEST_Z[0] <= p[2] <= CHEST_Z[1] and p[1] > bv.GATE_LO and abs(p[0]) <= bv.X_ZERO
    ]
    aa_full = np.asarray(after_band if after_band else [after[i] for i in base_idxs],
                         dtype=np.float64)
    aa_same = np.asarray([after[i] for i in base_idxs], dtype=np.float64)
    wall = bv.WALL_Y
    return {
        "front_y_max_cm": [round(float(ba[:, 1].max()), 2),
                           round(float(aa_full[:, 1].max()), 2)],
        "depth_over_wall_cm": [round(float(ba[:, 1].max() - wall), 2),
                               round(float(aa_full[:, 1].max() - wall), 2)],
        "depth_gain_cm": round(float(aa_full[:, 1].max() - ba[:, 1].max()), 2),
        "width_cm": [round(float(ba[:, 0].max() - ba[:, 0].min()), 2),
                     round(float(aa_same[:, 0].max() - aa_same[:, 0].min()), 2)],
        "volume_proxy": [
            round(float(np.sum(np.maximum(0.0, ba[:, 1] - wall))), 1),
            round(float(np.sum(np.maximum(0.0, aa_same[:, 1] - wall))), 1),
        ],
    }


def _rasterizer():
    """The repo's presentation rasterizer (tools/render_mod_previews.py)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "render_mod_previews", REPO / "tools" / "render_mod_previews.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_base_model_bytes(base_model_path: Path | None) -> bytes:
    """Read the base Miranda `.model` from disk or `dist/Miranda_LAS.zip`."""
    if base_model_path is not None and Path(base_model_path).is_file():
        return Path(base_model_path).read_bytes()
    dist_base = REPO / "dist" / "Miranda_LAS.zip"
    if dist_base.is_file():
        with zipfile.ZipFile(dist_base) as zf:
            return zf.read("Miranda_LAS/assets/units/miranda/skins/miranda/miranda.model")
    raise FileNotFoundError(
        f"Base miranda.model not found at {base_model_path} or in {dist_base}"
    )


def _extract_render_parts(model_bytes: bytes, textures: dict[str, np.ndarray],
                          include_head: bool = False,
                          clay_rgb: tuple[int, int, int] | None = None):
    """Build rasterizer part tuples using the `.model`'s actual vertex normals."""
    mf = bm.dm.ModelFile.read(model_bytes)
    clay_tex = None
    if clay_rgb is not None:
        clay_tex = np.full((16, 16, 4), (*clay_rgb, 255), dtype=np.uint8)

    parts = []
    for s in mf.by_type(bm.dm.MODEL_DATA):
        md = bm.dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        dname = bm.template_name(md["name_hash"], mf)
        if dname == "g_body":
            gp = bm.dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            topo = bm.dm.decode_topology(mf.by_id(gp["topology"]).payload)
            geo = bm.dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            v = np.asarray(geo["verts"], np.float32)
            n = np.asarray(geo["normals"], np.float32)
            tris = np.asarray(topo["indices"], np.int32).reshape(-1, 3)
            uv = np.asarray(geo["uv0"], np.float32)
            tex = clay_tex if clay_tex is not None else textures["body"]
            parts.append((v, n, tris, uv, tex, False, True))
        elif include_head and dname == "g_head":
            gp = bm.dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
            topo = bm.dm.decode_topology(mf.by_id(gp["topology"]).payload)
            geo = bm.dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            vh = np.asarray(geo["verts"], np.float32)
            nh = np.asarray(geo["normals"], np.float32)
            trish = np.asarray(topo["indices"], np.int32).reshape(-1, 3)
            uvh = np.asarray(geo["uv0"], np.float32)
            head_map = {
                0: textures["eyes"],
                1: textures["face"],
                2: textures["head"],
                3: textures["hair"],
            }
            for atom in md["atoms"]:
                bi, tc, mid = atom["base_index"], atom["tri_count"], atom["material_id"]
                tex = clay_tex if clay_tex is not None else head_map.get(mid, textures["head"])
                parts.append((vh, nh, trish[bi // 3 : bi // 3 + tc], uvh, tex, False, False))
    if not parts:
        raise SystemExit("g_body drawable not found in model")
    return parts


def _shift_y(part, dy: float):
    """Shift a part's positions along y to centre side-profile framing."""
    moved = part[0].copy()
    moved[:, 1] -= dy
    return moved


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO))
    except ValueError:
        return str(resolved)


def _render_variant_icon(model_bytes: bytes, textures_dds: dict[str, bytes],
                         preview_path: Path | None = None) -> bytes:
    """Render a distinct 256x256 3/4 bust-portrait icon for `Miranda_Busty_LAS`."""
    from PIL import Image, ImageDraw

    from dds_encode import rgba_to_bc3_dds

    rmp = _rasterizer()
    p = IDENTITY.item_id
    head_rgba = np.asarray(
        Image.open(io.BytesIO(textures_dds[f"{p}_head_df.texture"])).convert("RGBA")
    )
    hair_key = f"{p}_hair_df.texture"
    tex_rgba = {
        "body": np.asarray(
            Image.open(io.BytesIO(textures_dds[f"{p}_body_df.texture"])).convert("RGBA")
        ),
        "face": np.asarray(
            Image.open(io.BytesIO(textures_dds[f"{p}_face_df.texture"])).convert("RGBA")
        ),
        "head": head_rgba,
        "hair": (
            np.asarray(Image.open(io.BytesIO(textures_dds[hair_key])).convert("RGBA"))
            if hair_key in textures_dds
            else head_rgba
        ),
        "eyes": np.asarray(
            Image.open(io.BytesIO(textures_dds[f"{p}_eyes.texture"])).convert("RGBA")
        ),
    }
    parts = _extract_render_parts(model_bytes, tex_rgba, include_head=True)
    shifted = [(_shift_y(pt, 3.0),) + pt[1:] for pt in parts]
    hi = rmp.rasterize_parts(shifted, 512, 512, 26.0, 154.0, 8.4, z_min_clip=126.0)
    card = hi.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    draw = ImageDraw.Draw(card)
    # Subtle Cerberus-orange bottom accent bar + crisp border to distinguish
    # the Busty variant from the base Miranda face-crop icon in PD2's grid.
    draw.rectangle((0, 252, 255, 255), fill=(232, 108, 24, 255))
    draw.rectangle((0, 0, 255, 255), outline=(58, 66, 82, 255), width=1)
    if preview_path is not None:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        card.save(preview_path)
    return rgba_to_bc3_dds(np.asarray(card, dtype=np.uint8))


def _pivot_parts(parts, y_piv: float, z_piv: float,
                 z_lo: float = -1e9, z_hi: float = 1e9,
                 x_max: float = 1e9):
    """Recenter and clip part geometry around ``(0, y_piv, z_piv)`` for pitched views."""
    out = []
    for pos, nrm, tris, uv, tex, is_cut, v_neg in parts:
        p0, p1, p2 = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
        keep = (
            ((p0[:, 2] >= z_lo) & (p0[:, 2] <= z_hi))
            | ((p1[:, 2] >= z_lo) & (p1[:, 2] <= z_hi))
            | ((p2[:, 2] >= z_lo) & (p2[:, 2] <= z_hi))
        ) & (
            (np.abs(p0[:, 0]) <= x_max)
            & (np.abs(p1[:, 0]) <= x_max)
            & (np.abs(p2[:, 0]) <= x_max)
        )
        moved = pos.copy()
        moved[:, 1] -= y_piv
        moved[:, 2] -= z_piv
        out.append((moved, nrm, tris[keep], uv, tex, is_cut, v_neg))
    return out


def _render_sheets(before_verts, model_path: Path, unit_dir: Path,
                   preview_dir: Path, base_model_path: Path | None = None) -> list[str]:
    """Render before/after comparison sheets (full, chest, top/bottom, clay)."""
    from PIL import Image, ImageDraw

    rmp = _rasterizer()
    p = IDENTITY.item_id
    head_img = np.asarray(Image.open(unit_dir / f"{p}_head_df.texture").convert("RGBA"))
    hair_path = unit_dir / f"{p}_hair_df.texture"
    textures = {
        "body": np.asarray(Image.open(unit_dir / f"{p}_body_df.texture").convert("RGBA")),
        "face": np.asarray(Image.open(unit_dir / f"{p}_face_df.texture").convert("RGBA")),
        "head": head_img,
        "hair": np.asarray(Image.open(hair_path).convert("RGBA")) if hair_path.is_file() else head_img,
        "eyes": np.asarray(Image.open(unit_dir / f"{p}_eyes.texture").convert("RGBA")),
    }
    variant_bytes = Path(model_path).read_bytes()
    base_bytes = _load_base_model_bytes(base_model_path)

    before_full = _extract_render_parts(base_bytes, textures, include_head=True)
    after_full = _extract_render_parts(variant_bytes, textures, include_head=True)
    before_chest = _extract_render_parts(base_bytes, textures, include_head=False)
    after_chest = _extract_render_parts(variant_bytes, textures, include_head=False)
    before_clay = _extract_render_parts(base_bytes, textures, include_head=False,
                                        clay_rgb=(196, 202, 212))
    after_clay = _extract_render_parts(variant_bytes, textures, include_head=False,
                                       clay_rgb=(196, 202, 212))
    before_full_clay = _extract_render_parts(base_bytes, textures, include_head=True,
                                             clay_rgb=(196, 202, 212))
    after_full_clay = _extract_render_parts(variant_bytes, textures, include_head=True,
                                            clay_rgb=(196, 202, 212))

    written: list[str] = []
    preview_dir.mkdir(parents=True, exist_ok=True)
    title_font = rmp.FONT_REG_12

    sheets = (
        ("busty_compare_full", before_full, after_full,
         340, 560, 92.0, 2.65, (0.0, 34.0, 90.0), -1e9, {90.0: (2.65, 5.0)}),
        ("busty_compare_chest", before_chest, after_chest,
         360, 460, 140.0, 13.0, (0.0, 30.0, 60.0, 90.0), 124.0,
         {60.0: (11.5, 8.0), 90.0: (10.5, 11.0)}),
        ("busty_sculpt_clay", before_clay, after_clay,
         360, 460, 140.0, 13.0, (0.0, 30.0, 60.0, 90.0), 124.0,
         {60.0: (11.5, 8.0), 90.0: (10.5, 11.0)}),
    )
    for (name, b_parts, a_parts, w, h, zc, scale, angles, clip, views) in sheets:
        cells = []
        for label, parts in (("base Miranda_LAS", b_parts),
                             ("Miranda_Busty_LAS", a_parts)):
            for deg in angles:
                s_deg, shift = (views or {}).get(deg, (scale, 0.0))
                shifted = [(_shift_y(pt, shift),) + pt[1:] if shift else pt
                           for pt in parts]
                img = rmp.rasterize_parts(shifted, w, h, deg, zc, s_deg,
                                          z_min_clip=clip)
                cells.append((label, deg, img))
        canvas = Image.new("RGB", (w * len(angles), (h + 22) * 2), (16, 19, 26))
        draw = ImageDraw.Draw(canvas)
        for i, (label, deg, img) in enumerate(cells):
            row, col = divmod(i, len(angles))
            canvas.paste(img, (col * w, row * (h + 22) + 22))
            draw.text((col * w + 8, row * (h + 22) + 4), f"{label} · {int(deg)}°",
                      fill=(235, 240, 250), font=title_font)
        out = preview_dir / f"{name}.png"
        canvas.save(out)
        written.append(_display_path(out))

    # Dedicated whole-character top & bottom comparison sheets (textured + clay):
    # keep head & torso intact so there are no severed neck/abdomen holes.
    tb_specs = (
        ("Top 68° · 0° (above front)", 0.0, -68.0, True, 10.5, 141.0, 60.0, 190.0, 24.0, 10.2),
        ("Top 48° · 26° (3/4 above)", 26.0, -48.0, True, 9.5, 143.0, 60.0, 190.0, 24.0, 9.8),
        ("Bottom 48° · 26° (3/4 below)", 26.0, +48.0, True, 9.5, 138.0, 60.0, 190.0, 24.0, 9.8),
        ("Bottom 68° · 0° (below front)", 0.0, +68.0, True, 10.5, 138.5, 60.0, 190.0, 24.0, 10.2),
    )
    tw, th = 360, 400
    for tb_name, b_no_head, a_no_head, b_with_head, a_with_head in (
        ("busty_compare_top_bottom", before_chest, after_chest, before_full, after_full),
        ("busty_sculpt_top_bottom_clay", before_clay, after_clay, before_full_clay, after_full_clay),
    ):
        tb_canvas = Image.new("RGB", (tw * len(tb_specs), (th + 22) * 2), (16, 19, 26))
        tb_draw = ImageDraw.Draw(tb_canvas)
        for row, (label, p_body, p_head) in enumerate((
            ("base Miranda_LAS", b_no_head, b_with_head),
            ("Miranda_Busty_LAS", a_no_head, a_with_head),
        )):
            for col, (vtitle, yaw, pitch, use_head, yp, zp, zlo, zhi, xmax, sc) in enumerate(tb_specs):
                src = p_head if use_head else p_body
                piv = _pivot_parts(src, yp, zp, z_lo=zlo, z_hi=zhi, x_max=xmax)
                img = rmp.rasterize_parts(piv, tw, th, yaw, 0.0, sc, pitch_deg=pitch)
                tb_canvas.paste(img, (col * tw, row * (th + 22) + 22))
                tb_draw.text((col * tw + 8, row * (th + 22) + 4),
                             f"{label} · {vtitle}", fill=(235, 240, 250),
                             font=title_font)
        tb_out = preview_dir / f"{tb_name}.png"
        tb_canvas.save(tb_out)
        written.append(_display_path(tb_out))

    return written


def build(args) -> int:
    morph = bv.ChestMorph(cup_gain=args.cup_gain, round_gain=args.round_gain,
                          lift=args.lift, spread=args.spread,
                          valley=args.valley)
    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    skel_map = json.loads((HERE / "skeleton_map.json").read_text())
    tpp_template = bm.load_template(args.templates / "2b.model")
    fps_template = bm.load_template(args.templates / "fps_2b.model")

    arc = VpkArchive.from_zip(args.source_zip, "miranda_rochelle.vpk")
    tpp_model = load_model(*(arc.read(p) for p in bm.TPP_MDLS))
    fps_model = load_model(*(arc.read(p) for p in bm.FPS_MDLS))
    print(f"source: tpp {len(tpp_model.vertices)} verts, fps {len(fps_model.vertices)} verts")

    # --- third person: retarget, then morph, then author ------------------
    tpp_groups = {}
    share = {}
    for gname, spec in bm.TPP_GROUPS.items():
        tpp_groups[gname] = bm.transfer_group(tpp_model, spec, skel_map,
                                              tpp_template, gname)
        for d in spec["drawables"]:
            share[d] = gname

    before = {name: list(g.verts) for name, g in tpp_groups.items()}
    report = bv.morph_groups(tpp_groups, morph)

    tpp_mf = bm.assemble_model(tpp_template, tpp_groups, share)
    tpp_path = out_root / f"{IDENTITY.item_id}.model"
    tpp_path.write_bytes(tpp_mf.write())
    print(f"[tpp] wrote {tpp_path} ({tpp_path.stat().st_size} bytes)")

    # --- first person: untouched arms -------------------------------------
    fps_groups = {}
    fps_share = {}
    for gname, spec in bm.FPS_GROUPS.items():
        fps_groups[gname] = bm.transfer_group(fps_model, spec, skel_map,
                                             fps_template, gname)
        for d in spec["drawables"]:
            fps_share[d] = gname
    fps_mf = bm.assemble_model(fps_template, fps_groups, fps_share,
                               drop_drawables=("g_head", "g_head_lod1"))
    fps_path = out_root / f"fps_{IDENTITY.item_id}.model"
    fps_path.write_bytes(fps_mf.write())
    print(f"[fps] wrote {fps_path} ({fps_path.stat().st_size} bytes)")

    # --- measurements ------------------------------------------------------
    body_after = tpp_groups["body"].verts
    measured = _measure(before["body"], body_after, morph)
    report["measured"] = measured
    report["reference"] = {"base_pack": "dist/Miranda_LAS.zip",
                           "base_chest": _measure(before["body"], before["body"], morph)}
    print(f"[bust] front reach {measured.get('front_y_max_cm')} cm, "
          f"depth gain {measured.get('depth_gain_cm')} cm")

    # --- pack scaffold (textures, icon, registration) ----------------------
    rc = build_las.main(["--stage", "textures", "--source", str(args.source_zip),
                         "--out", str(out_root)])
    if rc != 0:
        raise SystemExit(f"build_las (textures) failed with exit code {rc}")
    textures = las_pack.retarget_textures(
        {f"{p}.texture": (out_root / "textures" / f"{p}.texture").read_bytes()
         for p in build_las.VTF_TO_PACK.values()},
        IDENTITY,
    )
    icon_preview = None if args.no_previews else (out_root / "previews" / "miranda_busty_icon.png")
    icon = _render_variant_icon(tpp_path.read_bytes(), textures, preview_path=icon_preview)

    pack = las_pack.write_pack(out_root, textures, icon, {"note": "bust variant"},
                              models_present=False, identity=IDENTITY)
    unit_dir = pack / "assets" / IDENTITY.unit_base
    shutil.copy2(tpp_path, unit_dir / tpp_path.name)
    shutil.copy2(fps_path, unit_dir / fps_path.name)
    wip = pack / "WIP_DO_NOT_INSTALL.txt"
    if wip.exists():
        wip.unlink()
    las_pack.refresh_build_info(
        pack, IDENTITY,
        variant={
            "kind": "chest_mass_morph",
            "base_pack": "Miranda_LAS",
            "base_item_id": las_pack.ITEM_ID,
            "morph": morph.describe(),
            "measured": measured,
        },
        templates={name: hashlib.sha256((args.templates / name).read_bytes()).hexdigest()
                   for name in ("2b.model", "fps_2b.model")},
        source_zip_sha256=hashlib.sha256(args.source_zip.read_bytes()).hexdigest(),
    )
    zip_path = las_pack.zip_pack(pack)
    zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.parent / f"{zip_path.name}.sha256").write_text(
        f"{zip_sha}  {_display_path(zip_path)}\n")

    if out_root == DEFAULT_OUT or args.update_dist:
        dist_dir = REPO / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)
        dist_zip = dist_dir / zip_path.name
        shutil.copy2(zip_path, dist_zip)
        (dist_dir / f"{zip_path.name}.sha256").write_text(
            f"{zip_sha}  dist/{zip_path.name}\n")
        print(f"dist: {dist_zip} (sha256={zip_sha[:16]}…)")

    # --- previews + report -------------------------------------------------
    if not args.no_previews:
        report["previews"] = _render_sheets(
            before["body"], tpp_path, unit_dir, out_root / "previews",
            base_model_path=out_root / "miranda.model")
    (out_root / "busty_variant_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"pack updated: {unit_dir}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, required=True,
                    help="directory containing 2b.model and fps_2b.model")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="build directory (also holds the base pack's outputs)")
    ap.add_argument("--source-zip", type=Path, default=bm.SOURCE_ZIP)
    ap.add_argument("--cup-gain", type=float, default=bv.DEFAULT_CUP_GAIN,
                    help="forward growth factor of the existing cup mass")
    ap.add_argument("--round-gain", type=float, default=bv.DEFAULT_ROUND_GAIN,
                    help="extra growth near the apex (fullness)")
    ap.add_argument("--lift", type=float, default=bv.DEFAULT_LIFT,
                    help="upward shift of the bust mass, cm")
    ap.add_argument("--spread", type=float, default=bv.DEFAULT_SPREAD,
                    help="outward shift of each breast, cm")
    ap.add_argument("--valley", type=float, default=bv.DEFAULT_VALLEY,
                    help="fraction of the added push removed at the sternum")
    ap.add_argument("--update-dist", action="store_true",
                    help="copy built zip to dist/ even when --out is custom")
    ap.add_argument("--no-previews", action="store_true")
    return build(ap.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
