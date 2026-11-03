"""Author the 3BA body's skin texture in its own UV space.

The merged body in `4.zip` points at vanilla Skyrim textures
(`textures\\actors\\character\\female\\femalebody_1.dds`) that are not in the
archives. Shipping them is not an option (Bethesda's, and not ours to
redistribute), and leaving them out leaves 28 % of the body — the whole lower
leg, most of the thigh, half the hips, the V-neck chest and the hands — bare.

So the skin is painted here, in the mesh's own UV layout, from nothing but the
geometry plus a colour sample taken from the reference pack:

* **cavity AO** from the mesh (edge-wise normal divergence, length-weighted):
  armpits, under the breasts, the crotch and the backs of the knees darken;
* **large-scale mottling** (value noise, three octaves) for skin blotchiness;
* **tone** sampled from the 2B pack's face swatch — a PD2-pipeline texture whose
  skin renders correctly in game — reported as statistics, not pixels;
* **normal map** from a pore-scale height field, packed the way Diesel reads it
  (`pd2_normal_channels`: X into alpha, Y+ in green).

Usage:

    .venv/bin/python tools/pd2-las/skin_texture.py \
        --meshes build/skyrim-nif/meshes --out build/skyrim-nif/textures
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "skyrim-nif"))
sys.path.insert(0, str(REPO / "tools" / "pd2-port"))

import dds_encode  # noqa: E402
import nif  # noqa: E402

DEFAULT_RES = 2048
BODY_SHAPE = "3BA"
FEET_SHAPE = "feet"

# skin tone statistics measured from the 2B reference pack's face swatch
# (median 181,155,142 with p10..p90 148..189) — a PD2-pipeline skin that renders
# correctly in game. Body skin runs a little darker and less saturated.
REFERENCE_TONE = np.array([181.0, 155.0, 142.0])
BODY_TONE_GAIN = 1.06


# ---------------------------------------------------------------------------
# value noise
# ---------------------------------------------------------------------------
def _value_noise(shape: tuple[int, int], cells: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth 2D value noise in [0, 1] with the given grid resolution."""
    grid = rng.random((cells + 1, cells + 1)).astype(np.float32)
    ys = np.linspace(0, cells, shape[0], endpoint=False, dtype=np.float32)
    xs = np.linspace(0, cells, shape[1], endpoint=False, dtype=np.float32)
    y0 = ys.astype(np.int32)
    x0 = xs.astype(np.int32)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    # smoothstep
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    g00 = grid[np.ix_(y0, x0)]
    g01 = grid[np.ix_(y0, x0 + 1)]
    g10 = grid[np.ix_(y0 + 1, x0)]
    g11 = grid[np.ix_(y0 + 1, x0 + 1)]
    top = g00 * (1 - fx) + g01 * fx
    bottom = g10 * (1 - fx) + g11 * fx
    return (top * (1 - fy) + bottom * fy).astype(np.float32)


def _fbm(shape, rng, octaves=4, base_cells=4) -> np.ndarray:
    total = np.zeros(shape, np.float32)
    amp, norm, cells = 1.0, 0.0, base_cells
    for _ in range(octaves):
        total += amp * _value_noise(shape, cells, rng)
        norm += amp
        amp *= 0.5
        cells *= 2
    return total / norm


# ---------------------------------------------------------------------------
# mesh sampling
# ---------------------------------------------------------------------------
def load_body(mesh_dir: Path) -> dict:
    """Body + feet geometry in the *stored* UV convention, with cavity shading."""
    jacket = nif.parse((mesh_dir / "Jacket_0.nif").read_bytes(), "Jacket_0.nif")
    heels = nif.parse((mesh_dir / "Heels_0.nif").read_bytes(), "Heels_0.nif")
    parts = []
    for parsed, name in ((jacket, BODY_SHAPE), (heels, FEET_SHAPE)):
        shape = next((s for s in parsed.shapes if s.name == name), None)
        if shape is None:
            raise SystemExit(f"{name} not found in the archive")
        parts.append(shape)

    verts = np.concatenate([p.vertices.astype(np.float64) for p in parts])
    normals = np.concatenate([
        (p.normals if nif.has_normals(p)
         else nif.smooth_normals(p.vertices, p.triangles)).astype(np.float64)
        for p in parts])
    # transfer_group stores (u, 1 - v); the texture is addressed by that pair
    uvs = np.concatenate([np.column_stack([p.uvs[:, 0], 1.0 - p.uvs[:, 1]]) for p in parts])
    tris, offset = [], 0
    for p in parts:
        tris.append(p.triangles.astype(np.int64) + offset)
        offset += p.num_vertices
    tris = np.concatenate(tris)
    return {"verts": verts, "normals": normals, "uvs": uvs, "tris": tris}


def cavity(verts, normals, tris) -> np.ndarray:
    """Length-weighted edge normal convergence: positive = concave (a crease).

    Cheap stand-in for ray-traced AO: across a crease (armpit, under a breast,
    the back of a knee) the normal rotates *with* the direction of travel, so
    dot(edge_direction, normal_a - normal_b) goes positive; on a convex surface
    it goes negative. Verified both ways in `tests/test_skin_texture.py`.
    """
    edges = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    a, b = edges[:, 0], edges[:, 1]
    d = verts[b] - verts[a]
    length = np.linalg.norm(d, axis=1)
    keep = length > 1e-9
    a, b, d, length = a[keep], b[keep], d[keep], length[keep]
    dn = normals[a] - normals[b]
    # positive on a crease, negative on a dome
    concavity = np.einsum("ij,ij->i", d / length[:, None], dn)
    acc = np.zeros(len(verts))
    wsum = np.zeros(len(verts))
    np.add.at(acc, a, concavity * length)
    np.add.at(acc, b, concavity * length)
    np.add.at(wsum, a, length)
    np.add.at(wsum, b, length)
    return np.clip(acc / np.maximum(wsum, 1e-9), -1.0, 1.0)


def rasterize(mesh: dict, res: int) -> dict:
    """Bake position, normal, cavity and coverage into UV space."""
    uvs = mesh["uvs"]
    uv = uvs.copy()
    # a few islands run slightly outside 0..1 (mirrored UVs); clamp into the atlas
    uv = np.clip(uv, 0.0, 1.0) * (res - 1)

    cov = np.zeros((res, res), bool)
    cavg = np.zeros((res, res), np.float32)
    nrm = np.zeros((res, res, 3), np.float32)
    pos = np.zeros((res, res, 3), np.float32)
    cav = cavity(mesh["verts"], mesh["normals"], mesh["tris"])

    tris = mesh["tris"]
    p = uv[tris]                                     # (t, 3, 2) in pixels
    minx = np.floor(p[..., 0].min(1)).astype(int)
    maxx = np.ceil(p[..., 0].max(1)).astype(int)
    miny = np.floor(p[..., 1].min(1)).astype(int)
    maxy = np.ceil(p[..., 1].max(1)).astype(int)

    for i in range(len(tris)):
        x0, x1 = max(minx[i], 0), min(maxx[i], res - 1)
        y0, y1 = max(miny[i], 0), min(maxy[i], res - 1)
        if x1 < x0 or y1 < y0:
            continue
        (ax, ay), (bx, by), (cx, cy) = p[i]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-12:
            continue
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / det
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / det
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        v0, v1, v2 = tris[i]
        w = np.stack([w0, w1, w2], axis=-1)[inside]
        rows = ys.astype(int)[:, None].repeat(len(xs), 1)[inside]
        cols = xs.astype(int)[None, :].repeat(len(ys), 0)[inside]
        ok = (rows >= 0) & (rows < res) & (cols >= 0) & (cols < res)
        rows, cols, w = rows[ok], cols[ok], w[ok]
        pos[rows, cols] = (w[:, 0:1] * mesh["verts"][v0] + w[:, 1:2] * mesh["verts"][v1]
                           + w[:, 2:3] * mesh["verts"][v2])
        nrm[rows, cols] = (w[:, 0:1] * mesh["normals"][v0] + w[:, 1:2] * mesh["normals"][v1]
                           + w[:, 2:3] * mesh["normals"][v2])
        cavg[rows, cols] = w @ cav[[v0, v1, v2]]
        cov[rows, cols] = True
    return {"coverage": cov, "cavity": cavg, "normal": nrm, "position": pos}


# ---------------------------------------------------------------------------
# compositing
# ---------------------------------------------------------------------------
def _dilate(img: np.ndarray, mask: np.ndarray, rounds: int = 12) -> np.ndarray:
    """Push island colours outward so mip-mapping cannot bleed black seams in."""
    out = img.copy()
    filled = mask.copy()
    for _ in range(rounds):
        if filled.all():
            break
        acc = np.zeros_like(out)
        cnt = np.zeros(filled.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(out, (dy, dx), axis=(0, 1))
            shifted_mask = np.roll(filled, (dy, dx), axis=(0, 1))
            acc += shifted * shifted_mask[..., None]
            cnt += shifted_mask
        grow = (~filled) & (cnt > 0)
        out[grow] = acc[grow] / cnt[grow][:, None]
        filled |= grow
    if not filled.all():
        mean = out[mask].mean(0)
        out[~filled] = mean
    return out


def _downsample(img: np.ndarray) -> np.ndarray:
    """2x box downsample of an (h, w, c) uint8 array."""
    h, w = img.shape[0] // 2 * 2, img.shape[1] // 2 * 2
    q = img[:h, :w].astype(np.uint16)
    return ((q[0::2, 0::2] + q[1::2, 0::2] + q[0::2, 1::2] + q[1::2, 1::2]) // 4).astype(np.uint8)


def _box_blur(field: np.ndarray, radius: int) -> np.ndarray:
    """Separable box blur that keeps the input shape (edge-clamped)."""
    out = field.astype(np.float32)
    for axis in (0, 1):
        pad_width = [(0, 0)] * out.ndim
        pad_width[axis] = (radius, radius)
        padded = np.pad(out, pad_width, mode="edge")
        csum = np.cumsum(padded, axis=axis, dtype=np.float64)
        lead = [slice(None)] * out.ndim
        tail = [slice(None)] * out.ndim
        lead[axis] = slice(2 * radius, None)
        tail[axis] = slice(0, -2 * radius)
        out = ((csum[tuple(lead)] - csum[tuple(tail)]) / (2 * radius)).astype(np.float32)
    return out


def _robust_scale(field: np.ndarray) -> np.ndarray:
    """Map a curvature field to roughly [-1, 1] by its own percentiles."""
    lo, mid, hi = np.percentile(field, [5, 50, 95])
    scale = max(float(hi - lo), 1e-6)
    return np.clip((field - mid) / (scale * 0.5), -2.0, 2.0)


def _anatomy_shading(position: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Shade the joints that actually show: knees, shins, ankles, toes, hands.

    Positions are in NIF units (1.428 cm), so height in centimetres is z * 1.428.
    The ranges come from the measured layout of this body: sole at 0, knee at
    ~49 cm, ankle at ~8 cm, and the hands at z ~ 100-106 cm on the sides.
    """
    z = position[..., 2] * 1.428
    side = np.abs(position[..., 0]) * 1.428           # distance from the midline
    out = np.ones(z.shape + (3,), np.float32)

    def band(center, half, depth):
        return depth * np.exp(-0.5 * ((z - center) / half) ** 2)

    # this export faces +Y (measured: `3BA_Vagina` sits at y ~ 0, `3BA_Anus` at
    # y ~ -4.6), so "front" is +normal.y
    front = np.clip(normal[..., 1], 0.0, 1.0)
    out *= (1.0 - 0.10 * band(49.0, 4.0, 1.0) * front)[..., None]
    # shin ridge: a touch lighter down the front of the leg
    out *= (1.0 + 0.05 * np.exp(-0.5 * ((z - 32.0) / 9.0) ** 2) * front)[..., None]
    # ankles: darker, all round
    out *= (1.0 - 0.07 * band(9.0, 3.0, 1.0))[..., None]
    # toes / sole edge: darker
    out *= (1.0 - 0.12 * np.exp(-0.5 * ((z - 2.0) / 2.0) ** 2))[..., None]
    # hands: knuckles slightly redder and darker
    hands = ((z > 96.0) & (z < 110.0) & (side > 25.0)).astype(np.float32)
    out *= (1.0 - 0.10 * hands)[..., None]
    # knees/elbows: warm the red channel slightly (subtle redness at joints)
    out[..., 0] *= 1.0 + 0.05 * band(49.0, 4.0, 1.0) * front
    return np.clip(out, 0.55, 1.15)


#: Diesel reads the diffuse alpha as gloss; skin should sit in the low forties
#: to low hundreds, never pinned at 0 (matte powder) or 255 (wet plastic).
SKIN_GLOSS_BASE = 40
SKIN_GLOSS_RANGE = 85


def build_diffuse(bake: dict, rng: np.random.Generator,
                  tone: np.ndarray = REFERENCE_TONE) -> np.ndarray:
    res = bake["coverage"].shape[0]
    cov = bake["coverage"]
    cav = bake["cavity"]
    nrm = bake["normal"]

    # --- base tone with a gentle large-scale gradient (skin is never flat)
    mottle = _fbm((res, res), rng, octaves=5, base_cells=10)[..., None]
    blotch = _fbm((res, res), rng, octaves=4, base_cells=48)[..., None]
    base = tone * BODY_TONE_GAIN
    color = np.ones((res, res, 3), np.float32) * base
    # subtle mottling: skin blotchiness reads at 2-3 %, not at 8 %
    color *= (1.0 + 0.020 * (mottle - 0.5)) * (1.0 + 0.012 * (blotch - 0.5))
    # warmth: red follows the mottling a little more than green/blue
    color[..., 0] *= 1.0 + 0.03 * (mottle[..., 0] - 0.5)
    color[..., 2] *= 1.0 - 0.02 * (mottle[..., 0] - 0.5)

    # --- occlusion: concavity darkens, convex ridges pick up a touch of light
    # only the *transient* part of the curvature field: a whole limb is gently
    # concave and must not turn into one big smudge, so subtract a blur first
    local = cav - _box_blur(cav, 24)
    norm_cav = _robust_scale(local)
    occlusion = np.clip(1.0 - 0.10 * np.maximum(norm_cav, 0.0), 0.80, 1.0)
    color *= occlusion[..., None]

    # --- anatomy: the exposed half of this body is legs, so shade the joints
    anatomy = _anatomy_shading(bake["position"], nrm)
    color *= anatomy[..., None] if anatomy.ndim == 2 else anatomy

    # --- limbs facing the floor are naturally darker (cheap vertical gradient)
    up = np.clip(nrm[..., 2] * 0.5 + 0.5, 0.0, 1.0)
    color *= (0.94 + 0.08 * up)[..., None]

    # --- palms/knuckles and soles are pinker; judged from the mesh itself
    pink = np.clip(np.maximum(0.0, -nrm[..., 2]) * 0.9, 0.0, 1.0)
    color[..., 0] *= 1.0 + 0.06 * pink
    color[..., 1] *= 1.0 - 0.03 * pink

    # Flatten what is left. Any structure in the albedo shows up as a band
    # wherever two UV islands meet — at heister distance skin is a tone, not a
    # texture — and blurring preserves the mean, so the tone survives intact.
    radius = max(4, res // 96)
    for _ in range(2):
        color = _box_blur(color, radius)

    color = np.clip(color, 0, 255)

    # --- gloss: Diesel reads the diffuse alpha as specular strength. Skin is a
    # soft, low-gloss surface and the gloss must be UNIFORM: the earlier
    # mottle/curvature-driven sheen varied the specular across the legs and,
    # with the normal-map blobs, read as camo-like blotches in-game. A constant
    # low gloss keeps the tone even under the game's lighting.
    alpha = np.full((res, res),
                    int(SKIN_GLOSS_BASE + SKIN_GLOSS_RANGE * 0.55), np.uint8)

    rgba = np.ones((res, res, 4), np.uint8) * 255
    rgba[..., :3] = color.astype(np.uint8)
    rgba[..., 3] = alpha
    flat_rgb = _dilate(rgba[..., :3].astype(np.float32), cov)
    rgba[..., :3] = np.clip(flat_rgb, 0, 255).astype(np.uint8)
    # outside the islands the gloss does not matter visually, but a mip bleed
    # should land on the same mid value the surface uses, not on a hard edge
    rgba[~cov, 3] = int(SKIN_GLOSS_BASE + SKIN_GLOSS_RANGE * 0.55)
    return rgba


def build_normal(bake: dict, rng: np.random.Generator, strength: float = 0.35) -> np.ndarray:
    """Low-frequency tangent-space normal map, already in Diesel's packing.

    Diesel reads X from alpha and Y from green, so any noise here is shading
    noise on the surface. The 2B reference (a PD2-pipeline map that renders
    correctly) sits at ~0.04 per-channel sigma; pore-scale fbm at strength 3.2
    gave 0.15 and read as speckle, worst of all on the legs.
    """
    res = bake["coverage"].shape[0]
    # Neutral (flat) tangent-space normal. The earlier low-frequency fbm height
    # field baked large blobs which, under the game's specular lighting, read as
    # camo-like blotches on the legs and thighs. The offline diffuse preview is
    # smooth — only the in-game normal + specular exposed them. Skin at heister
    # distance is a tone, not a normal-mapped surface, so ship a neutral map and
    # let the geometry normals do the shading. (strength kept in the signature
    # for callers; a flat map is intentionally independent of it.)
    packed = np.empty((res, res, 4), np.uint8)
    packed[...] = np.array([255, 128, 0, 128], np.uint8)
    return packed


# ---------------------------------------------------------------------------
# preview
# ---------------------------------------------------------------------------
def render_preview(bake: dict, diffuse: np.ndarray, out_png: Path, size: int = 720) -> None:
    """Splat the baked texels back into 3D views.

    Every covered texel already carries its world position and colour, so a
    z-buffered point splat is an honest preview of what the texture will look
    like on the mesh — no second UV sampler to disagree with the first.
    """
    from PIL import Image

    cov = bake["coverage"]
    pos = bake["position"][cov]
    col = diffuse[..., :3][cov].astype(np.float32)
    nrm = bake["normal"][cov]
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = nrm / np.where(ln < 1e-9, 1.0, ln)

    light = np.array([0.35, 0.55, 0.75], np.float32)
    light /= np.linalg.norm(light)
    shade = np.clip(nrm @ light, 0, 1) * 0.75 + 0.25
    col = np.clip(col * shade[:, None], 0, 255)

    # (right, up, toward-the-viewer); the outfit faces +Y, so "front" looks from +Y
    views = {
        "front": ((1, 0, 0), (0, 0, 1), (0, 1, 0)),
        "side": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
        "back": ((-1, 0, 0), (0, 0, 1), (0, -1, 0)),
        "three_quarter": ((0.7, 0.7, 0), (-0.25, -0.25, 1), (-0.7, 0.7, 0)),
    }
    lo, hi = pos.min(0), pos.max(0)
    center = (lo + hi) / 2
    p = pos - center
    canvas = Image.new("RGB", (size * len(views), size), (18, 18, 22))
    for i, (right, up, fwd) in enumerate(views.values()):
        right = np.asarray(right, np.float64)
        right /= np.linalg.norm(right)
        up = np.asarray(up, np.float64)
        up = up - right * (up @ right)
        up /= np.linalg.norm(up)
        fwd = np.asarray(fwd, np.float64)
        fwd /= np.linalg.norm(fwd)
        sx = p @ right
        sy = p @ up
        depth = p @ fwd
        span = max(float(sx.max() - sx.min()), float(sy.max() - sy.min()), 1e-6)
        scale = size * 0.9 / span
        px = (size / 2 + sx * scale).astype(np.int32)
        py = (size / 2 - sy * scale).astype(np.int32)
        inside = (px >= 0) & (px < size) & (py >= 0) & (py < size)
        px, py, depth, cols = px[inside], py[inside], depth[inside], col[inside]
        img = np.zeros((size, size, 3), np.float32)
        # `fwd` points at the viewer, so the largest depth is the nearest texel:
        # paint the farthest first and let the nearest overwrite it
        idx = py * size + px
        order = np.argsort(depth)
        img.reshape(-1, 3)[idx[order]] = cols[order]
        canvas.paste(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)), (i * size, 0))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png)
    print(f"preview -> {out_png}")


def mip_pyramid(rgba: np.ndarray, levels: int | None = None) -> list[np.ndarray]:
    """Box-filtered mip chain (a 2x2 average per level)."""
    h, w = rgba.shape[:2]
    if levels is None:
        levels = int(np.floor(np.log2(max(h, w)))) + 1
    out = [rgba]
    for _ in range(1, levels):
        prev = out[-1]
        if prev.shape[0] < 2 or prev.shape[1] < 2:
            break
        r, c = prev.shape[0] // 2 * 2, prev.shape[1] // 2 * 2
        quad = prev[:r, :c].astype(np.uint16)
        down = (quad[0::2, 0::2] + quad[1::2, 0::2] + quad[0::2, 1::2] + quad[1::2, 1::2]) // 4
        out.append(down.astype(np.uint8))
    return out


def hand_tone_from_body(body_df: Path, model: Path | None = None,
                        material: str = "mtr_body") -> np.ndarray:
    """The colour of the *shipped* body skin, as an RGB triple 0..255.

    Measured off the map, not off the mesh: sampling the body albedo at the UVs
    the body geometry actually uses gives the tone a player sees on her legs,
    whereas the atlas-wide median is biased bright by islands the body never
    samples (garment gaps, dilation borders) — using it rendered the hands
    twice as bright as the forearms they join.
    """
    from PIL import Image

    big = np.asarray(Image.open(str(body_df)).convert("RGB"), dtype=np.float32)
    fallback = np.array([150.0, 120.0, 112.0], dtype=np.float32)

    uv = None
    if model is not None and Path(model).exists():
        import diesel_model as dm

        try:
            mf = dm.ModelFile.read_path(model)
            for s in mf.by_type(dm.MODEL_DATA):
                md = dm.decode_model_data(s.payload)
                if not md.get("atoms"):
                    continue
                mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
                names = []
                for i in mg["material_ids"]:
                    h = dm.decode_material(mf.by_id(i).payload)["name_hash"]
                    names.append(_material_name(h, mf))
                if material not in names or len(names) < 2:
                    continue
                gp = dm.decode_passthroughgp(
                    mf.by_id(md["passthroughgp"]).payload)
                geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
                topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
                idx = np.asarray(topo["indices"], dtype=np.int64)
                uvs = np.asarray(geo["uv0"], dtype=np.float64)
                pick = set()
                for atom in md["atoms"]:
                    if names[atom["material_id"]] != material:
                        continue
                    t0 = atom["base_index"]
                    pick.update(int(v) for v in idx[t0:t0 + atom["tri_count"] * 3])
                if pick:
                    uv = uvs[sorted(pick)]
                    break
        except (ValueError, KeyError):
            uv = None

    if uv is None or not len(uv):
        flat = big.reshape(-1, 3)
        warm = (flat[:, 0] > 90) & (flat[:, 0] > flat[:, 2] + 8)
        return (np.percentile(flat[warm], 60, axis=0).astype(np.float32)
                if warm.any() else fallback)

    h, w = big.shape[:2]
    x = np.mod(uv[:, 0], 1.0) * w
    y = (1.0 - np.mod(uv[:, 1], 1.0)) * h
    xs = np.clip(x.astype(np.int64), 0, w - 1)
    ys = np.clip(y.astype(np.int64), 0, h - 1)
    sampled = big[ys, xs]
    keep = sampled.max(axis=1) > 40.0          # skip black gaps in the atlas
    sampled = sampled[keep]
    if not len(sampled):
        return fallback
    return np.median(sampled, axis=0).astype(np.float32)


def _material_name(name_hash: int, mf) -> str:
    """Material name from the model's own custom hashlist."""
    import diesel_model as dm

    try:
        hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)
    except (ValueError, IndexError):
        return ""
    for n in hl["names"]:
        if dm.hash64(n) == name_hash:
            return n
    return ""


def build_hands_texture(donor_dir: Path, out_dir: Path, res: int,
                        tone: np.ndarray | None = None
                        ) -> tuple[np.ndarray, np.ndarray]:
    """Hand maps for the grafted PD2 hands.

    The graft keeps the donor's UVs, so in principle the donor's own maps are
    the ones that sample correctly. In practice a heister's atlas is mostly
    *clothing*, and the UV islands that survive the hand graft land on the
    garment parts of it: 2B's `base_df` samples the hands at a median of
    (0.03, 0.05, 0.03) — near black. Copying it faithfully gives black mittens
    (it did, in every build until this one).

    So the albedo is authored instead: this outfit's own skin tone, measured
    off the body bake, with a little pore-scale variation so the hands do not
    read as flat plastic. The normal map stays neutral — a garment normal would
    emboss fabric weave onto skin.
    """
    tone = (np.asarray(tone, dtype=np.float32) if tone is not None
            else np.array([198.0, 160.0, 136.0], dtype=np.float32))
    rng = np.random.default_rng(20240503)
    # broad mottling plus fine grain, both low amplitude: the defect this
    # replaces was a leopard pattern, so stay well below visible banding
    small = rng.normal(0.0, 1.0, (res // 64, res // 64))
    grain = rng.normal(0.0, 1.0, (res, res))
    from PIL import Image

    small = np.array(Image.fromarray(small.astype(np.float32), mode="F").resize(
        (res, res), Image.BICUBIC), dtype=np.float32)
    small /= max(float(np.abs(small).max()), 1e-6)
    grain /= max(float(np.abs(grain).max()), 1e-6)
    shade = 1.0 + 0.045 * small + 0.02 * grain
    rgb = np.clip(tone[None, None, :] * shade[..., None], 0.0, 255.0)
    rgba = np.dstack([rgb.astype(np.uint8),
                      np.full((res, res), 255, np.uint8)])

    # neutral normal in Diesel's packed layout (X in alpha, Y in green, red
    # white, blue black) — the same packing `build_normal` emits
    nm = np.empty((res, res, 4), dtype=np.uint8)
    nm[..., 0] = 255
    nm[..., 1] = 128
    nm[..., 2] = 0
    nm[..., 3] = 128

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bw_hands_df.texture").write_bytes(encode_bc3_mips(rgba))
    (out_dir / "bw_hands_nm.texture").write_bytes(encode_bc3_mips(nm))
    return rgba, nm


def _load_texture(path: Path) -> np.ndarray:
    """One `.texture` DDS as HxWx4 uint8, without importing the renderer."""
    from PIL import Image

    return np.asarray(Image.open(str(path)).convert("RGBA"), dtype=np.uint8)


def _resize_rgb(img: np.ndarray, size: int) -> np.ndarray:
    from PIL import Image

    if img.shape[0] == size and img.shape[1] == size:
        return img
    chans = [np.asarray(Image.fromarray(img[..., c]).resize(
        (size, size), Image.LANCZOS)) for c in range(img.shape[2])]
    return np.dstack(chans).astype(np.uint8)


def encode_bc3_mips(rgba: np.ndarray, levels: int | None = None) -> bytes:
    """DXT5 DDS with a full mip chain (PD2 body textures ship 10-11 levels)."""
    chain = mip_pyramid(rgba, levels)
    h, w = chain[0].shape[:2]
    payload = bytearray()
    for level in chain:
        payload += dds_encode.rgba_to_bc3_dds(level)[128:]   # strip each header
    return dds_encode._dds_header(w, h, b"DXT5", mips=len(chain)) + bytes(payload)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--meshes", type=Path, default=REPO / "build" / "skyrim-nif" / "meshes")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "skyrim-nif" / "textures")
    ap.add_argument("--res", type=int, default=2048,
                    help="bake resolution (uv islands are small; 2048 keeps them clean)")
    ap.add_argument("--out-res", type=int, default=1024,
                    help="shipped texture size; the bake is box-filtered down to it")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--cache", type=Path, default=None,
                    help="reuse/refresh a baked atlas (.npz) while tuning the shading")
    args = ap.parse_args(argv)

    cache = args.cache
    if cache is not None and cache.exists():
        data = np.load(cache)
        bake = {k: data[k] for k in ("coverage", "cavity", "normal", "position")}
        print(f"bake: loaded {cache}")
    else:
        mesh = load_body(args.meshes)
        print(f"body: {len(mesh['verts'])} verts, {len(mesh['tris'])} tris")
        bake = rasterize(mesh, args.res)
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache, **bake)
            print(f"bake: saved {cache}")
    covered = bake["coverage"].mean()
    print(f"bake: {covered * 100:.1f}% of the {args.res}² atlas is skin")

    rng = np.random.default_rng(args.seed)
    diffuse = build_diffuse(bake, rng)
    normal = build_normal(bake, np.random.default_rng(args.seed + 1))

    if args.out_res and args.out_res != diffuse.shape[0]:
        # box-filter down: keeps distant detail that a smaller bake would alias
        while diffuse.shape[0] > args.out_res:
            diffuse = _downsample(diffuse)
            normal = _downsample(normal)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "bw_body_df.texture").write_bytes(encode_bc3_mips(diffuse))
    (args.out / "bw_body_nm.texture").write_bytes(encode_bc3_mips(normal))
    from PIL import Image
    Image.fromarray(diffuse[..., :3]).resize((768, 768), Image.LANCZOS).save(
        args.out / "bw_body_df_preview.png")
    Image.fromarray(normal[..., :3]).resize((768, 768), Image.LANCZOS).save(
        args.out / "bw_body_nm_preview.png")
    if not args.no_preview:
        # the preview splats texel colours back into 3D, so both sides must
        # describe the same grid; at out-res < res, previews use the full bake
        if diffuse.shape[0] == bake["coverage"].shape[0]:
            render_preview(bake, diffuse, args.out / "bw_body_on_mesh.png")
        else:
            preview_bake = {k: v for k, v in bake.items()}
            render_preview(preview_bake, build_diffuse(bake, np.random.default_rng(args.seed)),
                           args.out / "bw_body_on_mesh.png")
    print(f"wrote {args.out}/bw_body_df.texture and bw_body_nm.texture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


