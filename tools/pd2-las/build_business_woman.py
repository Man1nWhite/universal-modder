"""Author the Melodic \"Business Woman\" outfit as a PAYDAY 2 LAS model.

Input:  `4.zip` (Skyrim SE meshes) + `1.zip`/`2.zip`/`3.zip` (textures) at the
        repo root, and the 2B LAS reference pack for templates
        (`references/2b.rar` -> `/tmp/2bsrc`, see bootstrap.sh).
Output: `build/skyrim-nif/business_woman.model` (+ previews).

The geometry path is `build_models.py`'s: per-bone similarity retarget onto the
PD2 player skeleton with harmonic weight blending, then Diesel authoring against
the 2B template. Only the source side differs — see `skyrim_source.py`.

    .venv/bin/python tools/pd2-las/build_business_woman.py \\
        --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

Nothing here is installable yet: the pack also needs a head (the Skyrim archives
carry no head/hair mesh), first-person arms, materials and textures. This script
builds and previews the third-person body so the hard part — getting 3BA +
garments onto the PD2 rig without pinching — is verifiable offline.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pd2-port"))

import build_models as bm  # noqa: E402
import skyrim_retarget  # noqa: E402
import skyrim_source as ss  # noqa: E402

BONE_MAP = REPO / "tools" / "skyrim-nif" / "skeleton_map.json"
#: Everything above this height belongs to the neck opening of the 3BA body.
NECK_Z_CM = 155.0
#: Materials the first-person arms keep (skin + the two sleeve layers).
FPS_MATERIALS = ("mtr_body", "mtr_jacket", "mtr_jacket2")
UNIT_BASE = "units/businesswoman/skins/businesswoman"


def model_materials(report: dict) -> list[str]:
    """Logical material keys that actually made it into the built model."""
    return list(report["materials"])

# logical material -> Diesel material slot
MAT_SLOTS = {
    "skin": "mtr_body",
    "jacket": "mtr_jacket",
    "jacket2": "mtr_jacket2",
    "skirt": "mtr_skirt",
    "heels": "mtr_heels",
    "necklace": "mtr_necklace",
}
TPP_GROUPS = {
    "body": {
        "drawables": ["g_body", "g_body_lod1"],
        "materials": list(MAT_SLOTS),
        "out_materials": list(MAT_SLOTS.values()),
        "mat_slots": MAT_SLOTS,
    },
    "shadow": {
        "drawables": ["s_body"],
        "materials": list(MAT_SLOTS),
        "out_materials": ["shadow_caster"],
        "mat_slots": {name: "shadow_caster" for name in MAT_SLOTS},
    },
}


def render_sheet(model_path: Path, out_png: Path) -> None:
    """Four-view flat-shaded sheet of the authored model.

    Uses the skyrim-nif renderer (numpy z-buffer, per-material colours), which
    keeps material slices separable; the pd2-las renderer is for quick checks.
    """
    import importlib.util

    import diesel_model as dm
    import numpy as np
    from PIL import Image

    spec = importlib.util.spec_from_file_location(
        "skyrim_preview", REPO / "tools" / "skyrim-nif" / "preview.py")
    pv = importlib.util.module_from_spec(spec)
    import sys as _sys
    _sys.modules[spec.name] = pv
    spec.loader.exec_module(pv)

    colors = {
        "mtr_body": (214, 176, 150), "mtr_jacket": (52, 48, 50),
        "mtr_jacket2": (150, 150, 156),
        "mtr_skirt": (58, 60, 62), "mtr_heels": (226, 220, 206),
        "mtr_necklace": (206, 170, 80),
        "shadow_caster": (70, 70, 70),
    }
    mf = dm.ModelFile.read_path(model_path)
    meshes = []
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        names = []
        for mid in mg["material_ids"]:
            mat = dm.decode_material(mf.by_id(mid).payload)
            names.append(bm.template_name(mat["name_hash"], mf))
        verts = np.array(geo["verts"], dtype=np.float64)
        idx = np.array(topo["indices"], dtype=np.int64)
        faces = [(int(idx[i]), int(idx[i + 1]), int(idx[i + 2]))
                 for i in range(0, len(idx), 3)]
        if len(names) <= 1:
            continue                       # unshared template drawable
        for atom in md["atoms"]:
            name = names[atom["material_id"]]
            if name == "shadow_caster":
                continue
            t0 = atom["base_index"] // 3
            tris = faces[t0:t0 + atom["tri_count"]]
            used = sorted({v for tri in tris for v in tri})
            remap = {v: i for i, v in enumerate(used)}
            meshes.append({
                "vertices": verts[used],
                "triangles": np.array([(remap[a], remap[b], remap[c]) for a, b, c in tris]),
                "color": colors.get(name, (160, 160, 160)),
            })
        break                              # one drawable is enough for a sheet

    allv = np.concatenate([m["vertices"] for m in meshes])
    lo, hi = allv.min(0), allv.max(0)
    center = (lo + hi) / 2
    w2, _ = pv._project(allv, "front")
    span = float(w2[:, 0].max() - w2[:, 0].min())
    size = 640
    scale = size * 0.88 / max(span, float(hi[2] - lo[2]))
    views = ["front", "side", "back", "three_quarter"]
    sheet = Image.new("RGB", (size * len(views), size), (18, 18, 22))
    for i, view in enumerate(views):
        sheet.paste(pv.render(meshes, view, size, scale, center), (i * size, 0))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    print(f"sheet -> {out_png}")


def mesh_root(root: Path) -> Path:
    """Where the 12 garment NIFs live (4.zip layout, or an extracted tree)."""
    direct = root / "meshes" / "Melodic" / "Business Woman"
    if direct.is_dir():
        return direct
    if (root / "4.zip").exists():
        target = root / "build" / "skyrim-nif" / "meshes"
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(root / "4.zip") as zf:
            for name in zf.namelist():
                if name.lower().endswith(".nif"):
                    (target / Path(name).name).write_bytes(zf.read(name))
        return target
    raise SystemExit(f"no meshes: expected {direct} or 4.zip at {root}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, required=True,
                    help="directory with 2b.model / fps_2b.model")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "skyrim-nif")
    ap.add_argument("--root", type=Path, default=REPO)
    ap.add_argument("--jacket", choices=("both", "blazer", "bustier", "none"),
                    default="both")
    ap.add_argument("--heels", choices=("flatten", "keep"), default="flatten",
                    help="re-fit the stiletto for Diesel's flat-footed skeleton "
                         "(default) or ship the source's heel pose")
    ap.add_argument("--fps", action="store_true", default=True,
                    help="also build the first-person arms unit (default)")
    ap.add_argument("--no-fps", dest="fps", action="store_false")
    ap.add_argument("--no-previews", action="store_true")
    ap.add_argument("--pack", action="store_true",
                    help="also write textures, material configs and the LAS folder")
    ap.add_argument("--tex-res", type=int, default=1024,
                    help="shipped texture size for the garments")
    ap.add_argument("--skin-res", type=int, default=2048,
                    help="bake resolution for the authored skin (box-filtered "
                         "down to --tex-res)")
    ap.add_argument("--no-bake", action="store_true",
                    help="fail instead of baking the skin when it is missing")
    ap.add_argument("--dist", type=Path, default=REPO / "dist")
    args = ap.parse_args(argv)

    src = mesh_root(args.root)
    bone_map = json.loads(BONE_MAP.read_text())
    specs = ss.default_outfit(src, jacket=args.jacket)

    model, report = ss.load_outfit(specs, bone_map, heels=args.heels)
    print(f"source: {report['vertices']} verts / {report['triangles']} tris "
          f"over {len(model.bones)} PD2 bones")
    print(f"  materials: {report['materials']}")
    print(f"  dropped (no PD2 bone): {report['unresolved_bones']}")
    print(f"  feet: {report.get('feet')}")
    (args.out / "source_report.json").write_text(json.dumps(report, indent=2) + "\n")

    template = bm.load_template(args.templates / "2b.model")
    skel_map = ss.identity_skel_map(model)
    fits = skyrim_retarget.retarget_fits(model, template)
    print(f"retarget: {len(fits)} bone transforms")

    groups: dict[str, bm.Group] = {}
    share: dict[str, str] = {}
    for gname, spec in TPP_GROUPS.items():
        g = bm.transfer_group(model, spec, skel_map, template, gname, fits=fits)
        print(f"group {gname}: {len(g.verts)} verts, {len(g.faces)} tris, "
              f"palette {len(g.palette)}, slots {sorted(set(g.mat_slots))}")
        if not g.verts:
            raise SystemExit(f"group {gname} is empty")
        groups[gname] = g
        for drawable in spec["drawables"]:
            share[drawable] = gname

    # The outfit has no head: Skyrim ships heads separately and Melodic's
    # archives carry none. Do two things about it: never keep the *template's*
    # head (it is someone else's character, and shipping her face in this pack
    # would be both wrong and unlicensed), and close the collar hole it would
    # otherwise leave behind.
    body_group = groups["body"]
    skin_vertices: set[int] = set()
    for src_mat, base_v, _base_i, _tris, nverts in body_group.slices:
        if src_mat == "skin":
            skin_vertices.update(range(base_v, base_v + nverts))
    for gname in ("body", "shadow"):
        g = groups[gname]
        slot = "shadow_caster" if gname == "shadow" else "mtr_body"
        capped = bm.cap_holes(g, min_z=NECK_Z_CM, slot=slot,
                              allowed=skin_vertices, max_span=14.0)
        print(f"[{gname}] neck caps: {capped} triangles")

    mf = bm.assemble_model(template, groups, share,
                           drop_drawables=("g_head", "g_head_lod1"))
    out = args.out / "business_woman.model"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(mf.write())
    print(f"wrote {out} ({out.stat().st_size} bytes)")

    sheet_path = args.out / "previews" / "business_woman_pd2.png"
    if not args.no_previews:
        render_sheet(out, sheet_path)

    fps_path = args.out / "fps_business_woman.model"
    if args.fps:
        fps_tpl = bm.load_template(args.templates / "fps_2b.model")
        fps_arms = bm.extract_bones(groups["body"], bm.FPS_BONES, "arms")
        fps_shadow = bm.extract_bones(groups["shadow"], bm.FPS_BONES, "shadow")
        print(f"fps arms: {len(fps_arms.verts)} verts / {len(fps_arms.faces)} tris "
              f"({len(fps_shadow.verts)} shadow)")
        fps = bm.assemble_model(fps_tpl, {"arms": fps_arms, "shadow": fps_shadow},
                                {"g_body": "arms", "g_body_lod1": "arms",
                                 "s_body": "shadow"},
                                drop_drawables=("g_head", "g_head_lod1"))
        fps_path.write_bytes(fps.write())
        print(f"wrote {fps_path} ({fps_path.stat().st_size} bytes)")

    if args.pack:
        import bw_pack
        import skin_texture  # baked below when the textures are missing
        import skyrim_materials as sm

        tex_dir = args.out / "textures"
        tex_dir.mkdir(parents=True, exist_ok=True)
        baked = [n for n in ("bw_body_df", "bw_body_nm")
                 if not (tex_dir / f"{n}.texture").exists()]
        if baked and not args.no_bake:
            # the skin is authored, not sourced: bake it first so a clean
            # checkout goes from 1.zip..5.zip to a zip in one command
            import skin_texture as st

            print(f"baking skin texture ({', '.join(baked)} missing)")
            st.main(["--meshes", str(args.out / "meshes"),
                     "--out", str(tex_dir),
                     "--res", str(args.skin_res),
                     "--out-res", str(args.tex_res),
                     "--cache", str(args.out / "bake.npz")])
        elif baked:
            raise SystemExit(
                f"missing generated skin textures in {tex_dir} "
                f"({', '.join(baked)}); drop --no-bake or run skin_texture.py")

        specs = list(sm.DEFAULT_MATERIALS)
        # a dropped layer must not leave a material pointing at nothing
        keep = {MAT_SLOTS[v] for v in model_materials(report)}
        specs = [s for s in specs if s.name in keep]
        textures = sm.build_textures(
            args.root / "1.zip", specs, args.tex_res,
            generated_dir=args.out / "textures",
        )
        # keep every map on disk too: the icon is cut from a render of them
        for stem, data in textures.items():
            (tex_dir / f"{stem}.texture").write_bytes(data)
        config = sm.render_material_config(UNIT_BASE, specs)
        (args.out / "business_woman.material_config").write_text(config)

        # the menu icon is cut from our own textured render, not from the
        # flat-coloured sheet, so the tile shows the real materials
        import preview_textured as pt

        textured_sheet = args.out / "previews" / "business_woman_textured.png"
        pt.main([str(out), str(tex_dir), "--out", str(textured_sheet)])
        icon = bw_pack.build_icon(textured_sheet.read_bytes())
        fps_config = None
        fps_bytes = None
        if args.fps and fps_path.exists():
            # the viewmodel only carries the materials that survived the cut
            fps_specs = [s for s in specs if s.name in FPS_MATERIALS]
            fps_config = sm.render_fps_material_config(UNIT_BASE, fps_specs)
            fps_bytes = fps_path.read_bytes()
        pack = bw_pack.write_pack(
            args.dist, out.read_bytes(), textures, icon, config, fps_config,
            fps_model=fps_bytes,
            extra={
                "source": "Melodic Business Woman SE 3BA",
                # Melodic's readme asks for permission before republishing
                # outside LoversLab; shipped here at the pack owner's direction.
                "private": False,
                "redistribution": "published at the pack owner's direction",
            },
        )
        print(f"pack  -> {pack}")
        print(f"zip   -> {bw_pack.zip_pack(pack)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
