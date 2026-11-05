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
  dist/Miranda_Busty_LAS.zip               + .sha256
  build/pd2-las/busty_variant_report.json  morph parameters + measured gains
  build/pd2-las/previews/busty_*.png       before/after preview sheets

The pack is offline-verified only (geometry, materials, registration), exactly
like the base pack: it still needs the user-side in-game checklist, and the
source assets' redistribution rights remain unresolved, so it is private
experimental use only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
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
    ("Miranda Lawson joins the Payday Gang — Legendary Armour Skins outfit "
     "with a larger chest, built from the L4D2 Rochelle model."),
    pack_dir_name="Miranda_Busty_LAS",
)

#: Dust off the chest band for the report: the numbers a cup preset is judged on.
CHEST_Z = (130.0, 150.0)


def _chest_verts(verts, morph: bv.ChestMorph):
    xs = []
    for x, y, z in verts:
        if CHEST_Z[0] <= z <= CHEST_Z[1] and morph.weight_at(x, y, z) > 0.05:
            xs.append((x, y, z))
    return xs


def _measure(before, after, morph: bv.ChestMorph) -> dict:
    """Front reach / width / volume of the chest band, before and after."""
    b = _chest_verts(before, morph)
    a = _chest_verts(after, morph)
    if not b or not a:
        return {}
    ba = np.asarray(b, dtype=np.float64)
    aa = np.asarray(a, dtype=np.float64)
    wall = bv.WALL_Y
    return {
        "front_y_max_cm": [round(float(ba[:, 1].max()), 2),
                           round(float(aa[:, 1].max()), 2)],
        "depth_over_wall_cm": [round(float(ba[:, 1].max() - wall), 2),
                               round(float(aa[:, 1].max() - wall), 2)],
        "depth_gain_cm": round(float(aa[:, 1].max() - ba[:, 1].max()), 2),
        "width_cm": [round(float(ba[:, 0].max() - ba[:, 0].min()), 2),
                     round(float(aa[:, 0].max() - aa[:, 0].min()), 2)],
        # crude but stable proportional-volume proxy over the same vertex set
        "volume_proxy": [
            round(float(np.sum(ba[:, 1] - wall)), 1),
            round(float(np.sum(aa[:, 1] - wall)), 1),
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


def _model_parts(model_path: Path, texture, positions=None):
    """A rasterizer part tuple for the g_body drawable of one .model.

    Topology, UVs and (by default) positions come from the model file itself.
    ``positions`` overrides the positions — used for the "before" side, where the
    base pack's *own* model supplies the topology and no subdivision exists.

    Passing the variant's triangle list with the base's shorter vertex array
    does not work: the subdivided panels reference vertices the base does not
    have, and drawing them against a padded array collapses them onto the
    origin (the previews came out as barcodes).
    """
    import build_models as bm

    mf = bm.dm.ModelFile.read_path(Path(model_path))
    for s in mf.by_type(bm.dm.MODEL_DATA):
        md = bm.dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        if bm.template_name(md["name_hash"], mf) != "g_body":
            continue
        gp = bm.dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        topo = bm.dm.decode_topology(mf.by_id(gp["topology"]).payload)
        geo = bm.dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        v = np.asarray(positions if positions is not None else geo["verts"], np.float32)
        tris = np.asarray(topo["indices"], np.int32).reshape(-1, 3)
        n = np.zeros_like(v)
        fn = np.cross(v[tris[:, 1]] - v[tris[:, 0]], v[tris[:, 2]] - v[tris[:, 0]])
        for k in range(3):
            np.add.at(n, tris[:, k], fn)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        n = n / np.maximum(ln, 1e-9)
        return [(v, n, tris, np.asarray(geo["uv0"], np.float32), texture, False, True)]
    raise SystemExit(f"g_body drawable not found in {model_path}")


def _shift_y(part, dy: float):
    """Shift a part's positions along y (drawn space: use -dy to move the bust
    toward the middle of the frame at 90°)."""
    pos = part[0]
    moved = pos.copy()
    moved[:, 1] -= dy
    return moved


def _render_sheets(before_verts, model_path: Path, unit_dir: Path,
                   preview_dir: Path, base_model_path: Path | None = None) -> list[str]:
    """Before/after sheets: full body and close-up chest, same camera both sides."""
    from PIL import Image, ImageDraw

    rmp = _rasterizer()
    texture = np.asarray(
        Image.open(unit_dir / f"{IDENTITY.item_id}_body_df.texture").convert("RGBA"))
    after_parts = _model_parts(model_path, texture)
    before_parts = _model_parts(base_model_path, texture, positions=before_verts)
    written: list[str] = []
    preview_dir.mkdir(parents=True, exist_ok=True)

    title_font = rmp.FONT_REG_12
    sheets = (
        # (name, width, height, z_center, scale, angles, z_min_clip, views)
        # `views` overrides (scale, y_shift) per angle. The 90° cell is pulled
        # back and shifted because the bust sits a long way in front of the body
        # centre: at the front view's zoom the chest ran off the left edge, which
        # is why the side cell used to show the shoulder instead of the profile.
        ("busty_compare_full", 360, 560, 92.0, 2.6, (0.0, 34.0), -1e9, None),
        ("busty_compare_chest", 430, 470, 138.0, 13.5, (0.0, 30.0, 90.0), 124.0,
         {90.0: (8.5, 14.0)}),
    )
    for name, w, h, zc, scale, angles, clip, views in sheets:
        cells = []
        for label, parts in (("base Miranda_LAS", before_parts),
                             ("Miranda_Busty_LAS", after_parts)):
            for deg in angles:
                s_deg, shift = (views or {}).get(deg, (scale, 0.0))
                shifted = [(_shift_y(p, shift),) + p[1:] if shift else p
                           for p in parts]
                img = rmp.rasterize_parts(shifted, w, h, deg, zc, s_deg,
                                          z_min_clip=clip)
                cells.append((label, deg, img))
        canvas = Image.new("RGB", (w * len(angles), (h + 20) * 2), (16, 19, 26))
        draw = ImageDraw.Draw(canvas)
        for i, (label, deg, img) in enumerate(cells):
            row, col = divmod(i, len(angles))
            canvas.paste(img, (col * w, row * (h + 20) + 20))
            draw.text((col * w + 8, row * (h + 20) + 4), f"{label} · {int(deg)}°",
                      fill=(235, 240, 250), font=title_font)
        out = preview_dir / f"{name}.png"
        canvas.save(out)
        written.append(str(out.relative_to(REPO)))
    return written


def _body_parts(model_path: Path, texture):
    """The `g_body` drawable of an authored model as a rasterizer part."""
    import build_models as bm

    mf = bm.dm.ModelFile.read_path(model_path)
    for s in mf.by_type(bm.dm.MODEL_DATA):
        md = bm.dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        if bm.template_name(md["name_hash"], mf) != "g_body":
            continue
        gp = bm.dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = bm.dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = bm.dm.decode_topology(mf.by_id(gp["topology"]).payload)
        return [(np.asarray(geo["verts"], np.float32),
                 np.asarray(geo["normals"], np.float32),
                 np.asarray(topo["indices"], np.int32).reshape(-1, 3),
                 np.asarray(geo["uv0"], np.float32), texture, False, True)]
    raise SystemExit(f"{model_path}: g_body drawable not found")


def build(args) -> int:
    morph = bv.ChestMorph(cup_gain=args.cup_gain, round_gain=args.round_gain,
                          lift=args.lift, spread=args.spread,
                          valley=args.valley)
    out_root = args.out
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

    # --- first person: untouched arms (no chest geometry in the viewmodel) --
    # The variant must ship the *same* viewmodel as the base pack, so this call
    # repeats build_models' FPS assembly exactly (same share map, same
    # drop list). Any divergence here would silently change the hands.
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
    icon = next(iter(textures.values()))  # placeholder, replaced below
    import io

    from PIL import Image

    from dds_encode import rgba_to_bc3_dds
    from vtf import parse_vtf, to_png

    face = Image.open(io.BytesIO(to_png(parse_vtf(
        arc.read("materials/models/miranda/miranda_face_color.vtf")))))
    icon_img = face.crop((face.width // 8, 0, face.width * 7 // 8, face.height // 2))
    icon = rgba_to_bc3_dds(np.asarray(icon_img.resize((256, 256)).convert("RGBA"),
                                      dtype=np.uint8))

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
        f"{zip_sha}  build/pd2-las/{zip_path.name}\n")

    dist_dir = REPO / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    dist_zip = dist_dir / zip_path.name
    shutil.copy2(zip_path, dist_zip)
    (dist_dir / f"{zip_path.name}.sha256").write_text(
        f"{zip_sha}  dist/{zip_path.name}\n")

    # --- previews + report -------------------------------------------------
    if not args.no_previews:
        report["previews"] = _render_sheets(
            before["body"], tpp_path, unit_dir, out_root / "previews",
            base_model_path=out_root / "miranda.model")
    (out_root / "busty_variant_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"pack updated: {unit_dir}")
    print(f"dist: {dist_zip} (sha256={zip_sha[:16]}…)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, required=True,
                    help="directory containing 2b.model and fps_2b.model")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "pd2-las",
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
    ap.add_argument("--no-previews", action="store_true")
    return build(ap.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
