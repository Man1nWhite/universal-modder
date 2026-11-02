"""UV-convention probe: render our authored UVs and the known-good 2B UVs
with the same texture sampler.

The 2B LAS pack renders correctly in game. If our model renders the same way
as 2B under an identical sampler, our stored TEXCOORD0 convention matches the
reference and textures will not appear flipped in game. If ours is mirrored
vertically relative to 2B, flip the v sign in build_models.transfer_group.

Outputs textured PNGs into build/pd2-las/previews/uvcheck_* for side-by-side
comparison.

Usage:
    python tools/pd2-las/uv_check.py \
        --two-b /tmp/2bsrc/2B\ -\ LAS/assets/units/2b/skins/2b \
        --ours build/pd2-las/miranda.model \
        --out build/pd2-las/previews
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diesel_model as dm  # noqa: E402
import preview  # noqa: E402

# authored material name -> pack diffuse texture file name
MAT_TEX = {
    "mtr_body": "miranda_body_df.texture",
    "mtr_face": "miranda_face_df.texture",
    "mtr_head": "miranda_head_df.texture",
    "mtr_hair": "miranda_head_df.texture",
    "mtr_eyes": "miranda_eyes.texture",
}


def _names(mf: dm.ModelFile) -> dict[int, str]:
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    return {dm.hash64(n): n for n in hl["names"]}


def drawable_geometry(mf: dm.ModelFile, name: str):
    """Return (verts, uvs, faces) for one drawable, per-material ranges too."""
    names = _names(mf)
    by_name = {}
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        by_name[names.get(md["name_hash"], "?")] = md
    if name not in by_name:
        raise SystemExit(f"drawable {name!r} not found (have: {sorted(by_name)})")
    md = by_name[name]
    gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
    idx = topo["indices"]
    verts, uvs = geo["verts"], geo["uv0"]
    faces = [(idx[i], idx[i + 1], idx[i + 2]) for i in range(0, len(idx), 3)]

    mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
    mat_names = []
    for mid in mg["material_ids"]:
        mat = dm.decode_material(mf.by_id(mid).payload)
        mat_names.append(names.get(mat["name_hash"], hex(mat["name_hash"])))
    per_mat: dict[str, list] = {}
    for atom in md["atoms"]:
        mn = mat_names[atom["material_id"]]
        i0 = atom["base_index"]
        n = atom["tri_count"]
        per_mat.setdefault(mn, []).extend(faces[i0 // 3:i0 // 3 + n])
    return verts, uvs, faces, per_mat


def _tex(path: Path):
    from PIL import Image

    im = Image.open(path)
    im.load()
    return im


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--two-b", type=Path, required=True,
                    help="directory with the 2B templates (2b.model + base_df.texture)")
    ap.add_argument("--ours", type=Path, required=True, help="our miranda.model")
    ap.add_argument("--textures", type=Path,
                    default=HERE.parents[1] / "build/pd2-las/Miranda_LAS/assets/units/miranda/skins/miranda",
                    help="directory with our .texture files")
    ap.add_argument("--out", type=Path,
                    default=HERE.parents[1] / "build/pd2-las/previews")
    ap.add_argument("--size", type=int, default=640)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    atlas = _tex(args.two_b / "base_df.texture")
    print(f"2B atlas: {atlas.size}")

    mf2 = dm.ModelFile.read_path(args.two_b / "2b.model")
    for dname in ("g_head", "g_body"):
        verts, uvs, faces, _ = drawable_geometry(mf2, dname)
        for view in ("front", "iso"):
            out = args.out / f"uvcheck_2b_{dname}_{view}.png"
            preview.render_textured(verts, faces, uvs, atlas, out, view=view, size=args.size)
            print(f"wrote {out.name} ({dname}: {len(faces)} tris)")

    mf = dm.ModelFile.read_path(args.ours)
    ours = {
        "g_body": ["mtr_body"],
        "g_head": ["mtr_face", "mtr_head", "mtr_hair", "mtr_eyes"],
    }
    for dname, mats in ours.items():
        verts, uvs, faces, per_mat = drawable_geometry(mf, dname)
        for mn in mats:
            mfaces = per_mat.get(mn, [])
            if not mfaces:
                print(f"  (skip {dname}/{mn}: no faces)")
                continue
            tex = _tex(args.textures / MAT_TEX[mn])
            for view in ("front", "iso"):
                out = args.out / f"uvcheck_ours_{dname}_{mn}_{view}.png"
                preview.render_textured(verts, mfaces, uvs, tex, out, view=view, size=args.size)
                print(f"wrote {out.name} ({dname}/{mn}: {len(mfaces)} tris, tex {tex.size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
