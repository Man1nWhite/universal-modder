"""A lit software rasteriser for an authored PD2 model, with per-pixel UV sampling.

No command of its own: `glove_check.py` and `pose_zoom.py` render with it, and

    meshes = material_meshes(MODEL)                       # one mesh per material of the body drawable
    image = render(meshes, {}, "front", size, scale, center, cull=True)

`render` takes a texture per material name as an (h, w, 4) float array, or none:
a material without one is drawn grey. `cull=True` drops back faces as the game does.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import diesel_model as dm  # noqa: E402


def _project(points: np.ndarray, view: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (2d points, depth) for an orthographic view. World is Z-up."""
    if view == "front":
        return points[:, [0, 2]], -points[:, 1]
    if view == "back":
        return np.stack([-points[:, 0], points[:, 2]], 1), points[:, 1]
    if view == "side":
        return np.stack([-points[:, 1], points[:, 2]], 1), -points[:, 0]
    # three-quarter: rotate 35 degrees around Z
    a = np.deg2rad(35.0)
    c, s = np.cos(a), np.sin(a)
    x = points[:, 0] * c - points[:, 1] * s
    y = points[:, 0] * s + points[:, 1] * c
    return np.stack([x, points[:, 2]], 1), -y


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
    """Bilinear wrap sample from a top-down ``(H, W, 4)`` texture array.

    ``flip_v=True`` is the convention for UVs authored by
    ``build_models.transfer_group``: they store ``(u_src, 1 - v_src)``, so the
    top-down row fraction is ``mod(-uv_y, 1.0)`` and must not be inverted a
    second time (``1 - mod(-x, 1) == mod(x, 1)``, which silently mirrors the
    model). ``flip_v=False`` reads ``v`` as it is stored.
    """
    h, w = tex.shape[:2]
    u = np.mod(uv[..., 0], 1.0)
    v = np.mod(-uv[..., 1] if flip_v else uv[..., 1], 1.0)
    x = u * w - 0.5
    y = v * h - 0.5
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
           flip_v: bool = True, gloss: float = 0.55, cull: bool = False) -> Image.Image:
    """Z-buffered render with per-pixel UV sampling and a soft key light.

    ``cull=True`` drops back-facing triangles the way the game does, so a
    garment overlap that folds open reads as a real hole instead of being
    filled by the far side of the fabric (the default offline render draws both
    sides and therefore hides such holes).
    """
    _a = np.deg2rad(35.0)
    view_dir = {"front": np.array([0.0, -1.0, 0.0]),
                "back": np.array([0.0, 1.0, 0.0]),
                "side": np.array([-1.0, 0.0, 0.0]),
                "threequarter": np.array([-np.sin(_a), -np.cos(_a), 0.0]),
                }.get(view, np.array([0.0, -1.0, 0.0]))
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
        pts2, depth = _project(verts, view)
        c2, _ = _project(center[None, :], view)
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
        facing = (face @ view_dir) < 0.0

        for t in range(len(tris)):
            if cull and not facing[t]:
                continue
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

