"""Textured, lit preview of an authored PD2 model.

`build_business_woman.py` renders flat per-material colours, which answers
"is the silhouette right?" but not "do the textures land on the right
surfaces?". This rasteriser interpolates UVs per pixel and samples the packed
`.texture` files, so a swapped or flipped map is obvious immediately.

    .venv/bin/python tools/pd2-las/preview_textured.py \\
        build/skyrim-nif/business_woman.model \\
        dist/BusinessWoman_LAS/assets/units/businesswoman/skins/businesswoman \\
        --out build/skyrim-nif/previews/business_woman_textured.png

Material name -> file stem: `mtr_jacket` reads `bw_jacket_df.texture`, i.e. the
`mtr_` -> `bw_` rename the pack uses. Pass `--flip-v` if the result looks
mirrored top-to-bottom; the default matches what the game samples.
"""

from __future__ import annotations

import argparse
import importlib.util
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pd2-port"))

import diesel_model as dm  # noqa: E402

VIEWS = ("front", "side", "back", "threequarter")


def _load_preview():
    spec = importlib.util.spec_from_file_location(
        "skyrim_preview", REPO / "tools" / "skyrim-nif" / "preview.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_texture(path: Path) -> np.ndarray:
    """Decode the mip 0 of a DXT5 `.texture` to (h, w, 4) float in 0..1."""
    from dds import decode_dxt5

    data = path.read_bytes()
    if data[:4] != b"DDS ":
        raise ValueError(f"{path} is not a DDS")
    height, width = struct.unpack_from("<II", data, 12)
    rgba = decode_dxt5(data[128:], width, height)
    return rgba.astype(np.float32) / 255.0


def material_meshes(model_path: Path) -> list[dict]:
    """One entry per (material, atom-group): verts, tris, uvs, normals."""
    mf = dm.ModelFile.read_path(model_path)
    best = None
    for shape in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(shape.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        group = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        if len(group["material_ids"]) > 1:
            best = (shape, md)
            break
    if best is None:
        raise SystemExit("no multi-material MODEL_DATA in the model")

    _, md = best
    gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
    mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)

    import build_models as bm

    names = [bm.template_name(dm.decode_material(mf.by_id(m).payload)["name_hash"], mf)
             for m in mg["material_ids"]]

    verts = np.array(geo["verts"], dtype=np.float64)
    normals = np.array(geo["normals"], dtype=np.float64)
    uvs = np.array(geo["uv0"], dtype=np.float64)
    idx = np.array(topo["indices"], dtype=np.int64)
    faces = idx.reshape(-1, 3)

    meshes = []
    for atom in md["atoms"]:
        start = atom["base_index"] // 3
        tris = faces[start:start + atom["tri_count"]]
        if not len(tris):
            continue
        used = np.unique(tris)
        remap = np.full(verts.shape[0], -1, np.int64)
        remap[used] = np.arange(used.size)
        meshes.append({
            "material": names[atom["material_id"]],
            "vertices": verts[used],
            "normals": normals[used],
            "uvs": uvs[used],
            "triangles": remap[tris],
        })
    return meshes


def _sample(tex: np.ndarray, uv: np.ndarray, flip_v: bool) -> np.ndarray:
    """Bilinear texture lookup for (..., 2) UVs in 0..1 (wrapping)."""
    h, w = tex.shape[:2]
    u = np.mod(uv[..., 0], 1.0)
    v = np.mod(-uv[..., 1] if flip_v else uv[..., 1], 1.0)
    x = u * w - 0.5
    y = (1.0 - v) * h - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    x0m, x1m = np.mod(x0, w), np.mod(x0 + 1, w)
    y0m, y1m = np.mod(y0, h), np.mod(y0 + 1, h)
    c00 = tex[y0m, x0m]
    c10 = tex[y0m, x1m]
    c01 = tex[y1m, x0m]
    c11 = tex[y1m, x1m]
    return (c00 * (1 - fx) * (1 - fy) + c10 * fx * (1 - fy)
            + c01 * (1 - fx) * fy + c11 * fx * fy)


def render(meshes: list[dict], textures: dict[str, Image.Image], view: str,
           size: int, scale: float, center: np.ndarray,
           flip_v: bool = True, gloss: float = 0.55) -> Image.Image:
    """Z-buffered render with per-pixel UV sampling and a soft key light."""
    pv = _load_preview()
    light = np.array([0.35, -0.55, 0.75])
    light /= np.linalg.norm(light)
    fill = np.array([-0.6, -0.3, 0.1])
    fill /= np.linalg.norm(fill)
    half = np.array([0.35, -0.55, 0.75])
    half = half / np.linalg.norm(half)

    img = np.full((size, size, 3), 0.06, np.float32)
    zbuf = np.full((size, size), np.inf, np.float32)

    for mesh in meshes:
        verts, tris = mesh["vertices"], mesh["triangles"]
        if not len(tris):
            continue
        pts2, depth = pv._project(verts, view)
        c2, _ = pv._project(center[None, :], view)
        pts2 = (pts2 - c2[0]) * scale
        pts2[:, 1] *= -1.0
        pts2 += size / 2.0

        nor = mesh["normals"]
        tex = textures.get(mesh["material"])

        tri2 = pts2[tris]
        tri_z = depth[tris]
        v0, v1, v2 = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
        face = np.cross(v1 - v0, v2 - v0)
        ln = np.linalg.norm(face, axis=1, keepdims=True)
        face = face / np.where(ln == 0, 1, ln)

        for t in range(len(tris)):
            p = tri2[t]
            x0 = max(int(np.floor(p[:, 0].min())), 0)
            x1 = min(int(np.ceil(p[:, 0].max())) + 1, size)
            y0 = max(int(np.floor(p[:, 1].min())), 0)
            y1 = min(int(np.ceil(p[:, 1].max())) + 1, size)
            if x1 <= x0 or y1 <= y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1, dtype=np.float32) + 0.5,
                                 np.arange(y0, y1, dtype=np.float32) + 0.5)
            ax, ay = p[0]
            bx, by = p[1]
            cx, cy = p[2]
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-9:
                continue
            w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
            w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
            if not inside.any():
                continue
            z = w0 * tri_z[t][0] + w1 * tri_z[t][1] + w2 * tri_z[t][2]
            sub_z = zbuf[y0:y1, x0:x1]
            keep = inside & (z < sub_z)
            if not keep.any():
                continue

            n = (nor[tris[t][0]] * w0[..., None] + nor[tris[t][1]] * w1[..., None]
                 + nor[tris[t][2]] * w2[..., None])[keep]
            n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
            ndl = np.clip(n @ light, 0.0, 1.0)
            ndf = np.clip(n @ fill, 0.0, 1.0)
            spec = np.clip(n @ half, 0.0, 1.0) ** 24
            # a fill light keeps a black outfit from collapsing into the backdrop
            shade = 0.34 + 0.72 * ndl + 0.22 * ndf

            if tex is None:
                colour = np.full((keep.sum(), 3), 0.55, np.float32)
                sheen = np.ones(keep.sum(), np.float32)
            else:
                uv_t = (mesh["uvs"][tris[t][0]] * w0[..., None]
                        + mesh["uvs"][tris[t][1]] * w1[..., None]
                        + mesh["uvs"][tris[t][2]] * w2[..., None])[keep]
                sampled = _sample(tex, uv_t, flip_v)
                colour = sampled[:, :3]
                # PD2 keeps the specular strength in the diffuse alpha; using it
                # here means a broken gloss channel shows up in the preview
                sheen = sampled[:, 3]

            out = colour * shade[:, None] + spec[:, None] * (gloss * sheen)[:, None]
            canvas = img[y0:y1, x0:x1]
            canvas[keep] = np.clip(out, 0.0, 1.0)
            sub_z[keep] = z[keep]

    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


def texture_sheet(texture_dir: Path, out: Path, names: list[str],
                  tile: int = 220) -> Path:
    """Contact sheet: every map, plus the channels PD2 actually reads.

    The columns are: diffuse colour, diffuse alpha (gloss), and the normal map
    reassembled from Diesel's X-in-alpha / Y-in-green packing with Z rebuilt, so
    a wrong swizzle shows up as an obviously non-normal-looking normal.
    """
    rows = []
    for name in names:
        stem = name.replace("mtr_", "bw_")
        df_path = texture_dir / f"{stem}_df.texture"
        nm_path = texture_dir / f"{stem}_nm.texture"
        df = load_texture(df_path)
        nm = load_texture(nm_path) if nm_path.exists() else np.zeros_like(df)
        colour = (df[..., :3] * 255).astype(np.uint8)
        gloss = np.repeat((df[..., 3:4] * 255).astype(np.uint8), 3, axis=2)
        nx = nm[..., 3] * 2.0 - 1.0
        ny = nm[..., 1] * 2.0 - 1.0
        nz = np.sqrt(np.clip(1.0 - nx * nx - ny * ny, 0.0, 1.0))
        rebuilt = ((np.stack([nx, -ny, nz], axis=-1) * 0.5 + 0.5) * 255).astype(np.uint8)
        rows.append((name, [colour, gloss, rebuilt]))

    sheet = Image.new("RGB", (tile * 3 + 8, (tile + 18) * len(rows)), (18, 18, 22))
    for r, (name, tiles) in enumerate(rows):
        for c, img in enumerate(tiles):
            sheet.paste(Image.fromarray(img).resize((tile - 8, tile - 8), Image.LANCZOS),
                        (c * tile + 4, r * (tile + 18) + 16))
        ImageDraw.Draw(sheet).text((4, r * (tile + 18) + 3), name, fill=(255, 255, 255))
    for c, label in enumerate(("diffuse", "gloss (alpha)", "normal rebuilt")):
        ImageDraw.Draw(sheet).text((c * tile + 4, (tile + 18) * len(rows) - 14),
                                   label, fill=(170, 190, 220))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model", type=Path)
    ap.add_argument("texture_dir", type=Path,
                    help="folder holding bw_*_df.texture")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--size", type=int, default=520)
    ap.add_argument("--views", default=",".join(VIEWS))
    ap.add_argument("--flip-v", action="store_true", default=True)
    ap.add_argument("--no-flip-v", dest="flip_v", action="store_false")
    args = ap.parse_args(argv)

    meshes = material_meshes(args.model)
    names = sorted({m["material"] for m in meshes})
    textures = {}
    for name in names:
        stem = name.replace("mtr_", "bw_")
        path = args.texture_dir / f"{stem}_df.texture"
        if path.exists():
            textures[name] = load_texture(path)
        else:
            print(f"  no texture for {name} ({path.name})")
    print(f"materials: {[n for n in names]}")
    print(f"loaded:    {sorted(textures)}")

    allv = np.concatenate([m["vertices"] for m in meshes])
    lo, hi = allv.min(0), allv.max(0)
    center = (lo + hi) / 2
    pv = _load_preview()
    w2, _ = pv._project(allv, "front")
    span = float(w2[:, 0].max() - w2[:, 0].min())
    scale = args.size * 0.88 / max(span, float(hi[2] - lo[2]))

    views = [v for v in args.views.split(",") if v]
    sheet = Image.new("RGB", (args.size * len(views), args.size), (15, 15, 18))
    for i, view in enumerate(views):
        img = render(meshes, textures, view, args.size, scale, center,
                     flip_v=args.flip_v)
        ImageDraw.Draw(img).text((8, 8), view, fill=(255, 255, 255))
        sheet.paste(img, (i * args.size, 0))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"sheet -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
