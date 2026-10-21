#!/usr/bin/env python3
"""Build the Miranda Lawson LAS pack scaffold from the L4D2 source mod.

    python tools/pd2-las/build_las.py                       # everything
    python tools/pd2-las/build_las.py --source ... --out ...
    python tools/pd2-las/build_las.py --stage inventory     # JSON on stdout

Stages:
  extract     unpack the VPK from the source zip into <out>/extracted/
  inventory   parse the Source models (bones, meshes, triangles) and VTFs
  textures    convert every VTF to DDS (.texture) + PNG previews
  pack        write the LAS pack scaffold into <out>/Miranda_LAS/

Diesel `.model` authoring is NOT done here yet — the scaffold is registration,
textures and XMLs only, marked WIP. See README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dds_encode import (  # noqa: E402
    attenuate_dxt5_alpha_from_normal,
    swizzle_source_normal_dxt5_to_pd2,
)
from las_pack import write_pack  # noqa: E402
from source_model import load_model  # noqa: E402
from vpk import VpkArchive  # noqa: E402
from vtf import parse_vtf, to_dds, to_png  # noqa: E402

# VPK paths of the two studio models (third-person body, first-person arms).
TPP_MDLS = (
    "models/survivors/survivor_producer.mdl",
    "models/survivors/survivor_producer.vvd",
    "models/survivors/survivor_producer.dx90.vtx",
)
FPS_MDLS = (
    "models/weapons/arms/v_arms_producer_new.mdl",
    "models/weapons/arms/v_arms_producer_new.vvd",
    "models/weapons/arms/v_arms_producer_new.dx90.vtx",
)
MATERIAL_VMTS = {
    "miranda_body": "miranda_body",
    "miranda_face": "miranda_face",
    "miranda_head": "miranda_head",
    "miranda_hair": "miranda_head",  # hair reuses the head textures
    "eyeball_r": "miranda_eyes",
    "eyeball_l": "miranda_eyes",
}
# Source VTF stem -> pack texture base name.
VTF_TO_PACK = {
    "miranda_body_color": "miranda_body_df",
    "miranda_body_normal": "miranda_body_nm",
    "miranda_face_color": "miranda_face_df",
    "miranda_face_normal": "miranda_face_nm",
    "miranda_head_color": "miranda_head_df",
    "miranda_head_normal": "miranda_head_nm",
    "miranda_eyes": "miranda_eyes",
}
# Specular attenuation parameters for diffuse alpha (normal VTF stem, scale, max_alpha)
DF_SPECULAR_FROM_NORMAL = {
    "miranda_body_color": ("miranda_body_normal", 0.25, 64),
    "miranda_face_color": ("miranda_face_normal", 0.18, 42),
    "miranda_head_color": ("miranda_head_normal", 0.20, 48),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_inventory(model) -> dict:
    return {
        "name": model.name,
        "bones": len(model.bones),
        "bone_names": [b.name for b in model.bones],
        "vertices": len(model.vertices),
        "triangles": model.triangle_count,
        "materials": model.materials,
        "meshes": [
            {
                "material": m.material,
                "triangles": len(m.triangle_indices) // 3,
            }
            for m in model.meshes
        ],
    }


def main(argv: list[str] | None = None) -> int:
    repo = HERE.parents[1]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(repo / "models" / "l4d2_miranda_lawson_1.zip"),
                    help="the L4D2 source zip (default: models/l4d2_miranda_lawson_1.zip)")
    ap.add_argument("--vpk-inner", default="miranda_rochelle.vpk",
                    help="VPK member name inside the zip")
    ap.add_argument("--out", default=str(repo / "build" / "pd2-las"),
                    help="output directory (default: build/pd2-las, gitignored)")
    ap.add_argument("--stage", choices=["extract", "inventory", "textures", "pack", "all"],
                    default="all")
    args = ap.parse_args(argv)

    source = Path(args.source)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        print(f"error: source not found: {source}", file=sys.stderr)
        return 2

    arc = VpkArchive.from_zip(source, args.vpk_inner)
    print(f"vpk: {len(arc.entries)} entries from {source.name}")

    inventory = {
        "source_zip": source.name,
        "source_zip_sha256": sha256_file(source),
        "vpk_inner": args.vpk_inner,
        "vpk_entries": [e.path for e in arc.entries],
    }

    if args.stage in ("extract", "all"):
        ext = out / "extracted"
        written = arc.extract(ext)
        print(f"extract: {len(written)} files -> {ext}")

    # Model inventory is cheap and belongs in every persisted record.
    tpp = load_model(*(arc.read(p) for p in TPP_MDLS))
    fps = load_model(*(arc.read(p) for p in FPS_MDLS))
    inventory["models"] = {"third_person": model_inventory(tpp), "first_person": model_inventory(fps)}
    print(
        f"models: tpp={tpp.name} ({len(tpp.bones)} bones, {tpp.triangle_count} tris) "
        f"fps={fps.name} ({len(fps.bones)} bones, {fps.triangle_count} tris)"
    )

    textures: dict[str, bytes] = {}
    if args.stage in ("textures", "all"):
        png_dir = out / "previews"
        png_dir.mkdir(parents=True, exist_ok=True)
        tex_dir = out / "textures"
        tex_dir.mkdir(parents=True, exist_ok=True)
        vtf_info = {}
        raw_vtf_imgs = {
            stem: parse_vtf(arc.read(f"materials/models/miranda/{stem}.vtf"))
            for stem in sorted(VTF_TO_PACK)
        }
        raw_dds = {stem: to_dds(img) for stem, img in raw_vtf_imgs.items()}
        for stem, pack_name in sorted(VTF_TO_PACK.items()):
            img = raw_vtf_imgs[stem]
            if stem in DF_SPECULAR_FROM_NORMAL:
                nm_stem, scale, max_a = DF_SPECULAR_FROM_NORMAL[stem]
                dds = attenuate_dxt5_alpha_from_normal(
                    raw_dds[stem], raw_dds[nm_stem], scale, max_a
                )
            elif stem.endswith("_normal"):
                dds = swizzle_source_normal_dxt5_to_pd2(raw_dds[stem], invert_y=True)
            elif stem == "miranda_eyes":
                import numpy as np

                from dds_encode import rgba_to_bc3_dds

                size = 512
                yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
                u = (xx + 0.5) / size - 0.5
                v = (yy + 0.5) / size - 0.5
                r = np.hypot(u, v)
                theta = np.arctan2(v, u)
                sclera_t = np.clip((r - 0.25) / 0.25, 0.0, 1.0)
                lid_ao = np.clip(
                    1.0
                    - 0.32 * np.clip((-v - 0.02) / 0.22, 0.0, 1.0)
                    - 0.22 * np.clip((v - 0.06) / 0.22, 0.0, 1.0)
                    - 0.32 * (sclera_t**1.2),
                    0.46,
                    1.0,
                )
                rgb = np.stack([166.0 * lid_ao, 152.0 * lid_ao, 146.0 * lid_ao], axis=-1)
                iris_outer, iris_inner, pupil_r = 0.28, 0.25, 0.115
                iris_mask = np.clip((iris_outer - r) / (iris_outer - iris_inner), 0.0, 1.0)
                rn = np.clip((r - pupil_r) / max(iris_inner - pupil_r, 1e-4), 0.0, 1.0)
                f1 = np.sin(theta * 36.0 + 0.4 * np.sin(theta * 7.0))
                f2 = np.cos(theta * 64.0 - 0.6 * np.cos(theta * 11.0))
                f3 = np.sin(theta * 112.0 + 3.5 * rn)
                fiber_detail = (0.45 * f1 + 0.35 * f2 + 0.20 * f3) * np.sin(rn * np.pi)
                collarette = np.exp(-(((rn - 0.34) / 0.14) ** 2))
                radial = 1.0 - 0.38 * (rn**1.35) + 0.12 * collarette + 0.14 * fiber_detail
                upper_iris_ao = np.clip(1.0 - 0.18 * np.clip((-v - 0.05) / 0.20, 0.0, 1.0), 0.80, 1.0)
                radial = radial * upper_iris_ao
                iris_rgb = np.stack(
                    [
                        np.clip(24.0 * radial + 10.0 * collarette + 10.0 * fiber_detail, 8.0, 78.0),
                        np.clip(68.0 * radial + 18.0 * collarette + 18.0 * fiber_detail, 24.0, 142.0),
                        np.clip(146.0 * radial + 26.0 * collarette + 24.0 * fiber_detail, 52.0, 204.0),
                    ],
                    axis=-1,
                )
                limbus = np.clip((r - (iris_inner - 0.035)) / 0.045, 0.0, 1.0) * np.clip(
                    (iris_outer - r) / 0.025, 0.0, 1.0
                )
                iris_rgb = iris_rgb * (1.0 - 0.78 * limbus[..., None])
                pupil_mask = np.clip((pupil_r + 0.012 - r) / 0.018, 0.0, 1.0)
                iris_rgb = iris_rgb * (1.0 - pupil_mask[..., None]) + np.array([2.0, 3.0, 5.0], dtype=np.float32) * pupil_mask[..., None]
                rgb = rgb * (1.0 - iris_mask[..., None]) + iris_rgb * iris_mask[..., None]
                cornea_mask = np.clip(1.0 - (r - iris_outer) / 0.03, 0.0, 1.0)
                alpha = np.where(r < 0.118, 4.0, 8.0 + 4.0 * cornea_mask)
                eye_rgba = np.clip(np.dstack([rgb, alpha]), 0, 255).astype(np.uint8)
                dds = rgba_to_bc3_dds(eye_rgba)
            else:
                dds = raw_dds[stem]
            textures[f"{pack_name}.texture"] = dds
            (tex_dir / f"{pack_name}.texture").write_bytes(dds)
            (png_dir / f"{stem}.png").write_bytes(to_png(img))
            vtf_info[stem] = {
                "format": img.format_name,
                "size": [img.width, img.height],
                "mips": img.mipmap_count,
                "pack_texture": f"{pack_name}.texture",
                "dds_sha256": hashlib.sha256(dds).hexdigest(),
            }
            print(f"texture: {stem} {img.format_name} {img.width}x{img.height} -> {pack_name}.texture")
        inventory["textures"] = vtf_info

    if args.stage in ("pack", "all"):
        if not textures:
            textures = {
                f"{p}.texture": (out / "textures" / f"{p}.texture").read_bytes()
                for p in list(VTF_TO_PACK.values())
            }
        # Icon: face diffuse resized to 256x256 and BC3-encoded.
        import io

        import numpy as np
        from PIL import Image

        from dds_encode import rgba_to_bc3_dds

        face = Image.open(io.BytesIO(to_png(parse_vtf(arc.read("materials/models/miranda/miranda_face_color.vtf")))))
        icon_img = face.crop((face.width // 8, 0, face.width * 7 // 8, face.height // 2)).resize((256, 256))
        icon = rgba_to_bc3_dds(np.asarray(icon_img.convert("RGBA"), dtype=np.uint8))
        pack = write_pack(out, textures, icon, inventory, models_present=False)
        print(f"pack scaffold: {pack}")
        print("NOTE: Diesel .model files are not generated yet; scaffold is marked WIP.")

    inv_path = out / "source_inventory.json"
    inv_path.write_text(json.dumps(inventory, indent=2) + "\n")
    if args.stage == "inventory":
        # keep stdout pure JSON for scripting; the file is always persisted
        json.dump(inventory, sys.stdout, indent=2)
        print()
    else:
        print(f"inventory: {inv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
