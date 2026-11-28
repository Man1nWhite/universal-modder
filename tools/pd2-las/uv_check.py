"""UV-convention probe: render our authored UVs and the known-good 2B UVs
with the same texture sampler.

The 2B LAS pack renders correctly in game. If our model renders the same way
as 2B under an identical sampler, our stored TEXCOORD0 convention matches the
reference and textures will not appear flipped in game. If ours is mirrored
vertically relative to 2B, flip the v sign in build_models.transfer_group.

Outputs textured PNGs into build/pd2-las/previews/uvcheck_* for side-by-side
comparison.

From the repo root after `make -sC tools/pd2-las env`:
    .venv/bin/python tools/pd2-las/uv_check.py

By default this reads the tracked L4D2 Miranda ZIP and its own textures. To
inspect a loose authored .model, use --ours PATH and, if needed, --textures DIR.
"""

from __future__ import annotations

import argparse
import io
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diesel_model as dm  # noqa: E402
import extract_2b  # noqa: E402
from dist_paths import dist_path  # noqa: E402
import preview  # noqa: E402

# authored material name -> pack diffuse texture file name
MAT_TEX = {
    "mtr_body": "miranda_body_df.texture",
    "mtr_face": "miranda_face_df.texture",
    "mtr_head": "miranda_head_df.texture",
    "mtr_hair": "miranda_head_df.texture",
    "mtr_eyes": "miranda_eyes.texture",
}


def template_atlas(templates: Path) -> Path:
    """The 2B body atlas: beside the templates if the whole unit is unpacked, else out of the archive.

    Only the two `.model` templates are tracked (D92); `base_df.texture` is one of the
    archive's own textures (22 MB), so a clone reads it from `references/templates/2b.rar`
    when it needs it rather than carrying it beside the models.
    """
    beside = Path(templates) / "base_df.texture"
    if beside.is_file():
        return beside
    scratch = Path(tempfile.mkdtemp(prefix="uv-check-2b-", dir=HERE.parents[1] / "build"))
    path = scratch / "base_df.texture"
    path.write_bytes(extract_2b.read_member("base_df.texture"))
    return path


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


def _tex(path: Path | io.BytesIO):
    from PIL import Image

    im = Image.open(path)
    im.load()
    return im


def _ours(path: Path, textures: Path | None):
    names = sorted(set(MAT_TEX.values()))
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as pack:
            models = [PurePosixPath(name) for name in pack.namelist()
                      if PurePosixPath(name).name == "miranda.model"]
            if len(models) != 1:
                raise ValueError(f"{path}: expected one miranda.model")
            raw = pack.read(str(models[0]))
            if textures is None:
                return dm.ModelFile.read(raw), {name: _tex(io.BytesIO(pack.read(str(models[0].parent / name))))
                                                for name in names}
    else:
        raw = path.read_bytes()
    if textures is None:
        textures = path.parent
        if not all((textures / name).is_file() for name in names):
            # build_models.py writes the raw models beside the textures/ stage.
            textures = path.parent / "textures"
    return dm.ModelFile.read(raw), {name: _tex(textures / name) for name in names}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--two-b", type=Path, default=extract_2b.TEMPLATES,
                    help="directory with 2b.model and base_df.texture (default: the tracked 2B templates; "
                         "the textures are in the 2b.rar, unpack it if you need those)")
    ap.add_argument("--ours", type=Path, default=dist_path(HERE.parents[1], "Miranda_L4D2_LAS.zip"),
                    help="a L4D2 Miranda ZIP or a loose miranda.model (default: tracked ZIP)")
    ap.add_argument("--textures", type=Path,
                    help="override our texture directory (otherwise read the ZIP or use the loose model's neighbours)")
    ap.add_argument("--out", type=Path, default=HERE.parents[1] / "build/pd2-las/previews")
    ap.add_argument("--size", type=int, default=640)
    args = ap.parse_args(argv)
    try:
        atlas = _tex(template_atlas(args.two_b))
        mf2 = dm.ModelFile.read_path(args.two_b / "2b.model")
        mf, textures = _ours(args.ours, args.textures)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        ap.exit(1, f"uv_check: {error}\nFor loose models pass --textures DIR; the 2B atlas is read from "
                   f"references/templates/2b.rar.\n")
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"2B atlas: {atlas.size}")

    for dname in ("g_head", "g_body"):
        verts, uvs, faces, _ = drawable_geometry(mf2, dname)
        for view in ("front", "iso"):
            out = args.out / f"uvcheck_2b_{dname}_{view}.png"
            preview.render_textured(verts, faces, uvs, atlas, out, view=view, size=args.size)
            print(f"wrote {out.name} ({dname}: {len(faces)} tris)")

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
            tex = textures[MAT_TEX[mn]]
            for view in ("front", "iso"):
                out = args.out / f"uvcheck_ours_{dname}_{mn}_{view}.png"
                preview.render_textured(verts, mfaces, uvs, tex, out, view=view, size=args.size)
                print(f"wrote {out.name} ({dname}/{mn}: {len(mfaces)} tris, tex {tex.size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
