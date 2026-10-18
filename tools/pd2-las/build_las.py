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

from las_pack import TEXTURE_PAIRS, SINGLE_TEXTURES, write_pack  # noqa: E402
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
    ap.add_argument("--source", default=str(repo / "l4d2_miranda_lawson_1.zip"),
                    help="the L4D2 source zip (default: repo root copy)")
    ap.add_argument("--vpk-inner", default="miranda_rochelle.vpk",
                    help="VPK member name inside the zip")
    ap.add_argument("--out", default=str(repo / "build" / "pd2-las"),
                    help="output directory (default: build/pd2-las, gitignored)")
    ap.add_argument("--stage", choices=["extract", "inventory", "textures", "pack", "all"],
                    default="all")
    args = ap.parse_args(argv)

    source = Path(args.source)
    out = Path(args.out)
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

    if args.stage in ("inventory", "all"):
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
        for stem, pack_name in sorted(VTF_TO_PACK.items()):
            raw = arc.read(f"materials/models/miranda/{stem}.vtf")
            img = parse_vtf(raw)
            dds = to_dds(img)
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

    if args.stage == "inventory":
        json.dump(inventory, sys.stdout, indent=2)
        print()
    else:
        (out / "source_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
        print(f"inventory: {out / 'source_inventory.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
