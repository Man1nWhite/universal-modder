#!/usr/bin/env python3
"""Measure the mip levels of the two Miranda textures the build writes itself.

    python tools/pd2-las/mip_audit.py                 # the tables, as Markdown
    python tools/pd2-las/mip_audit.py --sheet OUT.png # and the before/after render

Five of the seven Miranda unit textures are converted from the source's VTF and
keep its blocks. The face diffuse is repainted and the eye texture is drawn, so
those two are encoded here, and this script is how that encoding is judged:

1. which mip level is on screen at a given distance (texel density on the mesh);
2. how far each level of a texture is from the image the build meant (colour as
   CIEDE2000, gloss as absolute error), against `LIMITS`;
3. the same figures for other encoders on the same images, among them encoders
   this repository did not write;
4. what a second decoder makes of the same bytes;
5. a render of the head at the pixel sizes of those distances, sampling the mip
   levels the way a GPU does;
6. whether the eye's levels, which are one drawing averaged down, are the
   picture a finer drawing gives.

The limits below were written before anything was measured against them. The
outside encoders and decoders (`quicktex`, `etcpak`, `texture2ddecoder`,
`scikit-image`) are not part of the pinned build environment and nothing that
ships is made with them: without them the script leaves their columns out.
"""
from __future__ import annotations

#: The pass limits, per mip level. "near" is every level that is on screen
#: somewhere between 1 and 8 m at 1080p or 2160p, plus level 0 (the menu shows
#: the character close up); "far" is every other level.
#:
#: colour: CIEDE2000 between a texel of the reference image and the same texel
#:   decoded from the texture (sRGB, D65). About 1 is the smallest difference an
#:   eye can pick out side by side, about 2 is visible on inspection.
#: iris:   the same difference between the mean colour of the iris ring in the
#:   reference and in the decoded level, for the eye texture, wherever the ring
#:   has at least four texel centres. This is "blue stays blue".
#: gloss:  absolute error of alpha, which the skin shader reads as gloss, 0..255.
LIMITS = {
    "near": {"colour_mean": 2.0, "colour_p99": 6.0, "iris": 3.0, "gloss_mean": 1.0, "gloss_max": 4},
    "far": {"colour_mean": 3.0, "colour_p99": 10.0, "iris": 6.0, "gloss_mean": 1.5, "gloss_max": 8},
}

#: The limits the pack is known to miss, and which no encoder that was tried
#: meets on the same image: `quicktex` at its highest setting misses the same
#: levels (2026-11-11). A block holds four colours on one line, and from 64x64
#: down a block of the eye holds pupil, iris, dark rim and sclera. The iris
#: limit, which is what the eye is looked at for, is met at every level.
#: The report fails when the misses are not exactly these.
KNOWN_MISSES = {
    ("eyes", 3): {"colour_p99"},
    ("eyes", 4): {"colour_mean", "colour_p99"},
    ("eyes", 5): {"colour_mean", "colour_p99"},
    ("eyes", 6): {"colour_mean", "colour_p99"},
    ("eyes", 7): {"colour_mean", "colour_p99"},
}

#: The iris ring of the eye texture, as a distance from the centre in texture
#: widths: outside the pupil's soft edge, inside the dark rim (`build_las.draw_eye`).
IRIS_RING = (0.14, 0.24)

#: Distances and screen heights the level-on-screen table is given for.
DISTANCES_M = (1, 2, 4, 8, 16)
SCREENS = (1080, 2160)
NEAR_M = (1, 8)

#: `tweak_data.player.stances.default.standard.FOV` in the game's Lua
#: (lib/tweak_data/playertweakdata.lua). Taken as the vertical field of view; if
#: the engine means it horizontally, a 16:9 screen shows everything 1.78 times
#: larger and every distance in the table reads 1.78 times farther.
GAME_FOV_DEG = 65.0

import argparse  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
import zipfile  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pd2-port"))

import build_las  # noqa: E402
import dds as pd2_dds  # noqa: E402
import dds_encode  # noqa: E402
import diesel_model as dm  # noqa: E402
from vpk import VpkArchive  # noqa: E402

PACK = REPO / "dist" / "Miranda_LAS.zip"
UNIT = "Miranda_LAS/assets/units/miranda/skins/miranda"
#: texture role -> the material of `g_head` that shows it
ROLES = {"face_df": "mtr_face", "eyes": "mtr_eyes"}


# ---------------------------------------------------------------- colour difference


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """(..., 3) sRGB in 0..255 as CIE L*a*b* (D65, 2 degree observer)."""
    linear = dds_encode.srgb_to_linear(np.asarray(rgb, dtype=np.float64) / 255.0)
    xyz = linear @ np.array([[0.4124564, 0.3575761, 0.1804375],
                             [0.2126729, 0.7151522, 0.0721750],
                             [0.0193339, 0.1191920, 0.9503041]]).T
    t = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(t > (6 / 29) ** 3, np.cbrt(t), t / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 colour difference (Sharma, Wu and Dalal 2005), kL = kC = kH = 1."""
    l1, a1, b1 = np.moveaxis(np.asarray(lab1, dtype=np.float64), -1, 0)
    l2, a2, b2 = np.moveaxis(np.asarray(lab2, dtype=np.float64), -1, 0)
    c_bar = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    g = 0.5 * (1 - np.sqrt(c_bar ** 7 / (c_bar ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    grey = c1p * c2p == 0
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(grey, 0.0, dh)
    d_l, d_c = l2 - l1, c2p - c1p
    d_h = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh) / 2)
    l_bar, c_barp = (l1 + l2) / 2, (c1p + c2p) / 2
    total = h1p + h2p
    h_bar = np.where(np.abs(h1p - h2p) <= 180, total / 2, np.where(total < 360, (total + 360) / 2, (total - 360) / 2))
    h_bar = np.where(grey, total, h_bar)
    t = (1 - 0.17 * np.cos(np.radians(h_bar - 30)) + 0.24 * np.cos(np.radians(2 * h_bar))
         + 0.32 * np.cos(np.radians(3 * h_bar + 6)) - 0.20 * np.cos(np.radians(4 * h_bar - 63)))
    s_l = 1 + 0.015 * (l_bar - 50) ** 2 / np.sqrt(20 + (l_bar - 50) ** 2)
    s_c, s_h = 1 + 0.045 * c_barp, 1 + 0.015 * c_barp * t
    r_t = (-np.sin(np.radians(60 * np.exp(-((h_bar - 275) / 25) ** 2)))
           * 2 * np.sqrt(c_barp ** 7 / (c_barp ** 7 + 25.0 ** 7)))
    return np.sqrt((d_l / s_l) ** 2 + (d_c / s_c) ** 2 + (d_h / s_h) ** 2 + r_t * (d_c / s_c) * (d_h / s_h))


def colour_difference(reference: np.ndarray, decoded: np.ndarray) -> np.ndarray:
    """CIEDE2000 per texel between two (h, w, 3+) sRGB images."""
    return delta_e2000(srgb_to_lab(reference[..., :3]), srgb_to_lab(decoded[..., :3]))


# ---------------------------------------------------------------- decoders and encoders


def _outside(name: str):
    try:
        return __import__(name)
    except ImportError:
        return None


def decoders() -> dict:
    """name -> function(dds, level) -> (h, w, 4) uint8. Pillow is always there."""
    out = {"Pillow": dds_encode.decode_bc3_level}

    def blocks(dds, level):
        offset, width, height = dds_encode.bc3_levels(dds)[level]
        across, down = (width + 3) // 4 * 4, (height + 3) // 4 * 4
        return dds[offset : offset + across // 4 * (down // 4) * 16], across, down, width, height

    def this_repo(dds, level):
        payload, across, down, width, height = blocks(dds, level)
        return np.asarray(pd2_dds.decode_dxt5(payload, across, down), dtype=np.uint8)[:height, :width]

    out["tools/pd2-port/dds.py"] = this_repo
    t2d = _outside("texture2ddecoder")
    if t2d:
        def outside(dds, level):
            payload, across, down, width, height = blocks(dds, level)
            bgra = np.frombuffer(t2d.decode_bc3(payload, across, down), dtype=np.uint8).reshape(down, across, 4)
            return bgra[:height, :width, [2, 1, 0, 3]].copy()

        out["texture2ddecoder"] = outside
    return out


def encoders(role: str = "") -> dict:
    """name -> function(level image) -> one single-level DXT5 DDS of it.

    Every encoder gets the same picture: a level smaller than a block is filled
    out by repeating its edge before any of them sees it. For the eyes there is
    one more entry, the encoder with the weights the build gives it.
    """
    def wrap(encode):
        def run(image):
            padded = dds_encode.pad_to_blocks(image)
            return dds_encode._dds_header(padded.shape[1], padded.shape[0], b"DXT5") + encode(padded)
        return run

    out = {
        "dds_encode.rgba_to_bc3_dds (bounding box)": wrap(lambda im: dds_encode.rgba_to_bc3_dds(im)[128:]),
        "tools/pd2-port/dds.py encode_dxt5": wrap(lambda im: pd2_dds.encode_dxt5(im)),
        "dds_encode.encode_bc3_texels (every pair)": wrap(
            lambda im: dds_encode.encode_bc3_texels(dds_encode.image_to_texels(im)).tobytes()),
    }
    if _outside("quicktex"):
        import quicktex
        from quicktex.s3tc.bc3 import BC3Encoder

        def quick(level):
            return lambda im: BC3Encoder(level).encode(
                quicktex.RawTexture.frombytes(im.tobytes(), im.shape[1], im.shape[0])).tobytes()

        out["quicktex 0.3.1, level 5 (outside)"] = wrap(quick(5))
        out["quicktex 0.3.1, level 18 (outside)"] = wrap(quick(18))
    etcpak = _outside("etcpak")
    if etcpak:
        out["etcpak 0.9.15 (outside)"] = wrap(lambda im: etcpak.compress_bc3(im.tobytes(), im.shape[1], im.shape[0]))
    if role == "eyes":
        by_side = {weights.shape[0]: weights for weights in build_las.eye_weights()}

        def weighted(image):
            padded = dds_encode.pad_to_blocks(image)
            count = dds_encode.pad_to_blocks(by_side[image.shape[0]][..., None])
            count = count.reshape(count.shape[0] // 4, 4, count.shape[1] // 4, 4).transpose(0, 2, 1, 3).reshape(-1, 16)
            return (dds_encode._dds_header(padded.shape[1], padded.shape[0], b"DXT5")
                    + dds_encode.encode_bc3_texels(dds_encode.image_to_texels(padded), count).tobytes())

        out = {"dds_encode.encode_bc3_texels, iris weighted (what the build uses)": weighted, **out}
    return out


# ---------------------------------------------------------------- the reference images


def reference_levels() -> dict:
    """role -> the mip levels the build means, level 0 first, uncompressed."""
    arc = VpkArchive.from_zip(build_las.SOURCE_ZIP, build_las.VPK_INNER)
    face, _changed = build_las.face_levels(build_las.converted_face_diffuse(arc))
    return {"face_df": face, "eyes": build_las.mip_levels(build_las.draw_eye())}


#: points per texel of level 0, along each axis, in the finer drawing of the eye
EYE_FINER = 4


def eye_drawn_finer() -> list:
    """The eye's levels from a drawing with `EYE_FINER` squared points per texel of level 0.

    The build draws the eye with one point per texel of level 0 and averages
    that drawing for the levels below. This is the same formula integrated more
    finely, so it is closer to what the eye is at each size than either the
    build's levels or a drawing made again, one point per texel, at each size.
    """
    fine = build_las.mip_levels(build_las.draw_eye(build_las.EYE_SIZE * EYE_FINER))
    return fine[EYE_FINER.bit_length() - 1:]


def iris_ring(side: int) -> np.ndarray:
    """Mask of the texels of a `side` x `side` eye level whose centre lies in the iris ring."""
    centre = (np.arange(side) + 0.5) / side - 0.5
    radius = np.hypot(centre[None, :], centre[:, None])
    return (radius > IRIS_RING[0]) & (radius < IRIS_RING[1])


def mean_colour(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Mean colour under a mask, averaged as light, as sRGB 0..255."""
    light = dds_encode.srgb_to_linear(image[..., :3][mask] / 255.0).mean(axis=0)
    return dds_encode.linear_to_srgb(light) * 255.0


def measure(reference: np.ndarray, decoded: np.ndarray, eye: bool) -> dict:
    """The figures `LIMITS` is about, for one level."""
    colour = colour_difference(reference, decoded)
    gloss = np.abs(decoded[..., 3].astype(int) - reference[..., 3].astype(int))
    out = {"colour_mean": float(colour.mean()), "colour_p99": float(np.percentile(colour, 99)),
           "colour_max": float(colour.max()), "gloss_mean": float(gloss.mean()), "gloss_max": int(gloss.max())}
    ring = iris_ring(reference.shape[0]) if eye else None
    if ring is not None and ring.sum() >= 4:
        want, got = mean_colour(reference, ring), mean_colour(decoded, ring)
        out["iris"] = float(delta_e2000(srgb_to_lab(want), srgb_to_lab(got)))
        out["iris_rgb"] = [int(round(c)) for c in got]
        out["iris_rgb_reference"] = [int(round(c)) for c in want]
    return out


def verdict(figures: dict, near: bool) -> dict:
    """The limits a level misses: name -> text. Empty when it passes."""
    limits = LIMITS["near" if near else "far"]
    return {key: f"{key.replace('_', ' ')} {figures[key]:.2f} > {limit:g}" for key, limit in limits.items()
            if key in figures and figures[key] > limit}


def audit_pack(pack: Path = PACK, decode=None) -> dict:
    """(role, level) -> the figures of that level of the pack, with its class and what it misses."""
    head = Head(pack)
    references = reference_levels()
    decode = decode or dds_encode.decode_bc3_level
    out = {}
    with zipfile.ZipFile(pack) as z:
        for role, material in ROLES.items():
            raw = z.read(f"{UNIT}/miranda_{role}.texture")
            near = near_levels(head.density(material, references[role][0].shape[0])[0], len(references[role]))
            for level in range(len(dds_encode.bc3_levels(raw))):
                figures = measure(references[role][level], decode(raw, level), role == "eyes")
                figures["near"] = level in near
                figures["misses"] = verdict(figures, level in near)
                out[role, level] = figures
    return out


def unexpected(results: dict) -> list[str]:
    """Where the pack and `KNOWN_MISSES` disagree, in either direction."""
    out = []
    for key, figures in sorted(results.items()):
        known = KNOWN_MISSES.get(key, set())
        for name in sorted(set(figures["misses"]) - known):
            out.append(f"{key[0]} level {key[1]}: {figures['misses'][name]}")
        for name in sorted(known - set(figures["misses"])):
            out.append(f"{key[0]} level {key[1]}: {name} is listed in KNOWN_MISSES and is met now")
    return out


# ---------------------------------------------------------------- the model and the screen


class Head:
    """`g_head` of a pack: per material, its triangles with positions (cm) and image-space UVs."""

    def __init__(self, pack: Path = PACK, unit: str = UNIT):
        with zipfile.ZipFile(pack) as z:
            stem = unit.rsplit("/", 1)[1]
            data = z.read(f"{unit}/{stem}.model")
            config = z.read(f"{unit}/{stem}.material_config").decode()
            self.texture_files = {
                name: z.read(f"{pack.stem}/assets/{file}.texture")
                for name, file in re.findall(
                    r'<material\b[^>]*\bname="([^"]+)".*?<diffuse_texture file="([^"]+)"', config, flags=re.S)}
        names = {dm.hash64(name): name for name in self.texture_files}
        mf = dm.ModelFile.read(data)
        self.parts = {}
        for section in mf.by_type(dm.MODEL_DATA):
            node = dm.decode_model_data(section.payload)
            if node.get("version") != 3 or node["name_hash"] != dm.hash64("g_head"):
                continue
            gp = dm.decode_passthroughgp(mf.by_id(node["passthroughgp"]).payload)
            geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
            faces = np.asarray(dm.decode_topology(mf.by_id(gp["topology"]).payload)["indices"], int).reshape(-1, 3)
            verts = np.asarray(geo["verts"], float).reshape(-1, 3)
            uv = np.asarray(geo["uv0"], float).reshape(-1, 2)
            uv = np.stack([uv[:, 0], 1.0 - uv[:, 1]], axis=1)          # the codec returns (u, 1 - v_image)
            group = dm.decode_material_group(mf.by_id(node["matgroup"]).payload)
            materials = [dm.decode_material(mf.by_id(i).payload)["name_hash"] for i in group["material_ids"]]
            for atom in node["atoms"]:
                if isinstance(atom, dict):
                    base_index, tri_count, material = atom["base_index"], atom["tri_count"], atom["material_id"]
                else:
                    _base_vertex, _slice_len, base_index, tri_count, material = atom
                tris = faces[base_index // 3 : base_index // 3 + tri_count]
                name = names[materials[material]]
                xyz, st = self.parts.get(name, (np.zeros((0, 3, 3)), np.zeros((0, 3, 2))))
                self.parts[name] = (np.concatenate([xyz, verts[tris]]), np.concatenate([st, uv[tris]]))
        if not self.parts:
            raise SystemExit(f"{pack}: no g_head in {unit}")

    def density(self, material: str, side: int) -> tuple[float, float, float]:
        """Texels per cm on the surface: the median over the triangles, weighted by area, with the 10th and 90th percentile."""
        xyz, st = self.parts[material]
        area = np.linalg.norm(np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0]), axis=1) / 2
        a, b = st[:, 1] - st[:, 0], st[:, 2] - st[:, 0]
        uv_area = np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) / 2
        keep = area > 1e-9
        each = side * np.sqrt(uv_area[keep] / area[keep])
        order = np.argsort(each)
        cumulative = np.cumsum(area[keep][order]) / area[keep].sum()
        return tuple(float(each[order][np.searchsorted(cumulative, q)]) for q in (0.5, 0.1, 0.9))


def pixels_per_cm(distance_m: float, screen: int, fov_deg: float = GAME_FOV_DEG) -> float:
    """How many screen pixels one centimetre covers at a distance, facing the camera."""
    return screen / (2 * distance_m * 100 * math.tan(math.radians(fov_deg) / 2))


def level_on_screen(density: float, distance_m: float, screen: int) -> float:
    """The mip level a GPU picks: log2 of texels per pixel, no bias, no anisotropy, never below 0."""
    return max(0.0, math.log2(density / pixels_per_cm(distance_m, screen)))


def near_levels(density: float, count: int) -> set:
    """Every level up to the coarsest one on screen at the far end of `NEAR_M`, at the smaller screen."""
    return set(range(min(count, math.ceil(level_on_screen(density, NEAR_M[1], min(SCREENS))) + 1)))


# ---------------------------------------------------------------- the render


def _bilinear(image: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    x, y = u * width - 0.5, v * height - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0, x1, y0, y1 = x0 % width, (x0 + 1) % width, y0 % height, (y0 + 1) % height
    return ((image[y0, x0] * (1 - fx) + image[y0, x1] * fx) * (1 - fy)
            + (image[y1, x0] * (1 - fx) + image[y1, x1] * fx) * fy)


def sample(levels: list, u: np.ndarray, v: np.ndarray, lod: float) -> np.ndarray:
    """Trilinear: the two levels around `lod`, each filtered bilinearly, blended. One level: bilinear."""
    lod = min(max(lod, 0.0), len(levels) - 1)
    low = int(math.floor(lod))
    high, blend = min(low + 1, len(levels) - 1), lod - low
    colour = _bilinear(levels[low], u, v)
    return colour if blend == 0 or high == low else colour * (1 - blend) + _bilinear(levels[high], u, v) * blend


def render(head: Head, textures: dict, ppc: float, window=(-11.0, 11.0, 162.0, 184.0), supersample: int = 4,
           ideal: bool = False) -> np.ndarray:
    """The head from the front, unlit, at `ppc` screen pixels per cm: (n, n, 3) uint8.

    ``textures`` maps a material to its mip levels as float arrays (stored sRGB
    values, which is what a sampler without an sRGB flag filters). The level is
    chosen per triangle from how many texels one screen pixel covers. Edges are
    antialiased by rendering `supersample` times larger and averaging.

    ``ideal`` ignores the mip levels: level 0 is sampled so densely that no
    sample skips a texel, and the samples are averaged as light. That is the
    picture the mip levels exist to approximate.
    """
    x0, x1, z0, z1 = window
    n = max(1, round((x1 - x0) * ppc))
    if ideal:
        finest = max(max(len(levels[0]) for levels in textures.values()) / ((x1 - x0) * 12), 1.0)
        supersample = int(min(max(supersample, math.ceil(finest * 24 / n * 8)), max(4, 2600 // n)))
    size = n * supersample
    scale = size / (x1 - x0)
    image = np.zeros((size, size, 3))
    depth = np.full((size, size), -np.inf)
    for material, (xyz, st) in head.parts.items():
        levels = textures[material]
        side = levels[0].shape[0]
        px = np.stack([(x1 - xyz[..., 0]) * scale, (z1 - xyz[..., 2]) * scale], axis=-1)
        for corner, where, uv in zip(xyz, px, st):
            lo = np.maximum(np.floor(where.min(axis=0)).astype(int), 0)
            hi = np.minimum(np.ceil(where.max(axis=0)).astype(int), size)
            if (hi <= lo).any():
                continue
            edge1, edge2 = where[1] - where[0], where[2] - where[0]
            det = edge1[0] * edge2[1] - edge1[1] * edge2[0]
            if abs(det) < 1e-12:
                continue
            gx, gy = np.meshgrid(np.arange(lo[0], hi[0]) + 0.5, np.arange(lo[1], hi[1]) + 0.5)
            rx, ry = gx - where[0, 0], gy - where[0, 1]
            w1 = (rx * edge2[1] - ry * edge2[0]) / det
            w2 = (ry * edge1[0] - rx * edge1[1]) / det
            inside = (w1 >= 0) & (w2 >= 0) & (w1 + w2 <= 1)
            if not inside.any():
                continue
            w1, w2 = w1[inside], w2[inside]
            w0 = 1 - w1 - w2
            y = w0 * corner[0, 1] + w1 * corner[1, 1] + w2 * corner[2, 1]
            rows, cols = (gy[inside] - 0.5).astype(int), (gx[inside] - 0.5).astype(int)
            front = y > depth[rows, cols]
            if not front.any():
                continue
            u = (w0 * uv[0, 0] + w1 * uv[1, 0] + w2 * uv[2, 0])[front]
            v = (w0 * uv[0, 1] + w1 * uv[1, 1] + w2 * uv[2, 1])[front]
            if ideal:
                colour = dds_encode.srgb_to_linear(_bilinear(levels[0], u, v) / 255.0)
            else:
                # how far the texture moves, in texels, for one step of one final pixel
                jac = np.linalg.solve(np.stack([edge1, edge2]), np.stack([uv[1] - uv[0], uv[2] - uv[0]])) * side
                lod = math.log2(max(np.linalg.norm(jac, axis=1).max() * supersample, 1e-9))
                colour = dds_encode.srgb_to_linear(sample(levels, u, v, lod) / 255.0)
            image[rows[front], cols[front]] = colour
            depth[rows[front], cols[front]] = y[front]
    small = dds_encode.box_reduce(image, supersample)
    return np.rint(dds_encode.linear_to_srgb(small) * 255.0).astype(np.uint8)


def pack_textures(head: Head, decode) -> dict:
    """material -> its mip levels, decoded, as float arrays."""
    return {material: [decode(raw, level).astype(np.float64)[..., :3]
                       for level in range(len(dds_encode.bc3_levels(raw)))]
            for material, raw in head.texture_files.items() if material in head.parts}


def sheet(path: Path, before: Path | None, tile: int = 232) -> None:
    """Rows: the ideal picture, the pack before, the pack now. Columns: `DISTANCES_M` at 1080p.

    Also prints how far each row is from the ideal one. A still cannot show what
    mip levels are for: with one level every screen pixel takes whichever texel
    its centre lands on, which is right on average and crawls when anything
    moves. So a row with one level can sit closer to the ideal than a row with
    the whole pyramid, and still be the one that shimmers in the game.
    """
    from PIL import Image, ImageDraw

    now = Head()
    decode = dds_encode.decode_bc3_level
    rows = [("ideal", now, pack_textures(now, decode), True)]
    if before:
        old = Head(before)
        rows.append(("before", old, pack_textures(old, decode), False))
    rows.append(("now", now, pack_textures(now, decode), False))
    references = reference_levels()
    for role, material in ROLES.items():
        rows[0][2][material] = [references[role][0].astype(np.float64)[..., :3]]
    margin, header = 64, 34
    out = Image.new("RGB", (margin + tile * len(DISTANCES_M), header + tile * len(rows)), "white")
    draw = ImageDraw.Draw(out)
    apart = {label: [] for label, *_rest in rows[1:]}
    for column, distance in enumerate(DISTANCES_M):
        draw.text((margin + column * tile + 6, 4), f"{distance} m at 1080p", fill="black")
        draw.text((margin + column * tile + 6, 18), f"{2 * distance} m at 2160p", fill="black")
        ppc = pixels_per_cm(distance, 1080)
        wanted = None
        for row, (label, head, textures, ideal) in enumerate(rows):
            pixels = render(head, textures, ppc, ideal=ideal)
            if ideal:
                wanted = pixels
            else:
                apart[label].append(float(colour_difference(wanted, pixels).mean()))
            picture = Image.fromarray(pixels)
            scale = max(1, (tile - 4) // picture.width)
            picture = picture.resize((picture.width * scale, picture.height * scale), Image.NEAREST)
            out.paste(picture, (margin + column * tile + (tile - picture.width) // 2,
                                header + row * tile + (tile - picture.height) // 2))
    for row, (label, *_rest) in enumerate(rows):
        draw.text((6, header + row * tile + tile // 2 - 6), label, fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)
    print("\n## The render against the ideal picture\n")
    print("Mean CIEDE2000 over the tile, unlit, trilinear without anisotropic filtering.\n")
    print(_row(["row"] + [f"{d} m" for d in DISTANCES_M]))
    print(_row(["---"] * (1 + len(DISTANCES_M))))
    for label, values in apart.items():
        print(_row([label] + [f"{value:.2f}" for value in values]))


# ---------------------------------------------------------------- the report


def _row(cells) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def report(before: Path | None) -> int:
    head = Head()
    references = reference_levels()
    with zipfile.ZipFile(PACK) as z:
        shipped = {role: z.read(f"{UNIT}/miranda_{role}.texture") for role in ROLES}
    old = {}
    if before:
        with zipfile.ZipFile(before) as z:
            old = {role: z.read(f"{UNIT}/miranda_{role}.texture") for role in ROLES}
    failures = 0

    print("## Which mip level is on screen\n")
    print(f"Vertical field of view {GAME_FOV_DEG:g} degrees; the level is log2 of texels per screen pixel, "
          "facing the camera, no bias, no anisotropic filter. A value between two levels is a blend of both.\n")
    print(_row(["texture", "texels per cm (median; 10th to 90th percentile)", "screen"]
               + [f"{d} m" for d in DISTANCES_M]))
    print(_row(["---"] * (3 + len(DISTANCES_M))))
    near = {}
    for role, material in ROLES.items():
        side = references[role][0].shape[0]
        median, low, high = head.density(material, side)
        near[role] = near_levels(median, len(references[role]))
        for screen in SCREENS:
            print(_row([f"`{role}` ({side}x{side})", f"{median:.0f} ({low:.0f} to {high:.0f})", f"{screen}p"]
                       + [f"{level_on_screen(median, d, screen):.1f}" for d in DISTANCES_M]))
    print()
    for role in ROLES:
        print(f"Near levels of `{role}` (on screen up to {NEAR_M[1]} m at {min(SCREENS)}p): "
              f"0 to {max(near[role])}; the rest are far levels.")

    print("\n## The eye: one drawing averaged, against a drawing at each size\n")
    print(f"Measured against the eye drawn with {EYE_FINER * EYE_FINER} points per texel of level 0 and averaged. "
          "\"The build's level\" is the reference used below: the eye drawn with one point per texel of level 0, "
          "averaged. \"Drawn at this size\" is the eye drawn again with one point per texel of that level.\n")
    print(_row(["level", "size", "the build's level: colour mean", "p99", "worst", "gloss worst", "iris",
                "drawn at this size: colour mean", "p99", "worst", "iris"]))
    print(_row(["---"] * 11))
    for level, (fine, built) in enumerate(zip(eye_drawn_finer(), references["eyes"])):
        side = built.shape[0]
        ours, each = measure(fine, built, True), measure(fine, build_las.draw_eye(side), True)
        print(_row([level, f"{side}x{side}", f"{ours['colour_mean']:.2f}", f"{ours['colour_p99']:.2f}",
                    f"{ours['colour_max']:.2f}", ours["gloss_max"], f"{ours['iris']:.2f}" if "iris" in ours else "-",
                    f"{each['colour_mean']:.2f}", f"{each['colour_p99']:.2f}", f"{each['colour_max']:.2f}",
                    f"{each['iris']:.2f}" if "iris" in each else "-"]))

    available = decoders()
    judge = available.get("texture2ddecoder", available["Pillow"])
    judge_name = "texture2ddecoder" if "texture2ddecoder" in available else "Pillow"

    print("\n## The textures in the pack, level by level\n")
    print(f"Reference: the uncompressed image the build means for that level. Decoded by {judge_name}. "
          "Colour is CIEDE2000, gloss is alpha in steps of 255.\n")
    for role in ROLES:
        eye = role == "eyes"
        columns = ["level", "size", "class", "colour mean", "colour p99", "gloss mean", "gloss max"]
        columns += ["iris (reference -> decoded)", "iris difference"] if eye else []
        for label, raw in (("before", old.get(role)), ("now", shipped[role])):
            if raw is None:
                continue
            count = len(dds_encode.bc3_levels(raw))
            print(f"`{role}`, {label}: {count} level{'s' if count != 1 else ''}, {len(raw):,} B\n")
            print(_row(columns + ["verdict"]))
            print(_row(["---"] * (len(columns) + 1)))
            for level in range(count):
                reference = references[role][level]
                figures = measure(reference, judge(raw, level), eye)
                missed = verdict(figures, level in near[role])
                known = KNOWN_MISSES.get((role, level), set()) if label == "now" else set()
                failures += label == "now" and set(missed) != known
                cells = [level, f"{reference.shape[1]}x{reference.shape[0]}", "near" if level in near[role] else "far",
                         f"{figures['colour_mean']:.2f}", f"{figures['colour_p99']:.2f}",
                         f"{figures['gloss_mean']:.2f}", figures["gloss_max"]]
                if eye:
                    cells += ([f"{tuple(figures['iris_rgb_reference'])} -> {tuple(figures['iris_rgb'])}",
                               f"{figures['iris']:.2f}"] if "iris" in figures else ["-", "-"])
                text = "; ".join(missed.values()) or "pass"
                print(_row(cells + [text + (" (known: the format)" if missed and set(missed) == known else "")]))
            print()

    print("## The same images through each encoder\n")
    print("Every encoder is given the reference image of every level. Worst level of each figure, "
          "and the levels that miss a limit.\n")
    for role in ROLES:
        eye = role == "eyes"
        print(f"`{role}`\n")
        print(_row(["encoder", "colour mean", "colour p99", "gloss mean", "gloss max"]
                   + (["iris difference"] if eye else []) + ["levels that miss a limit"]))
        print(_row(["---"] * (6 + eye)))
        for name, encode in encoders(role).items():
            worst, missed = {}, []
            for level, reference in enumerate(references[role]):
                height, width = reference.shape[:2]         # below 4x4 the block is larger than the level
                figures = measure(reference, judge(encode(reference), 0)[:height, :width], eye)
                for key in ("colour_mean", "colour_p99", "gloss_mean", "gloss_max", "iris"):
                    if key in figures:
                        worst[key] = max(worst.get(key, 0), figures[key])
                if verdict(figures, level in near[role]):
                    missed.append(level)
            print(_row([name, f"{worst['colour_mean']:.2f}", f"{worst['colour_p99']:.2f}", f"{worst['gloss_mean']:.2f}",
                        worst["gloss_max"]] + ([f"{worst['iris']:.2f}"] if eye else [])
                       + [", ".join(map(str, missed)) or "none"]))
        print()

    print("## What other decoders make of the same bytes\n")
    print(_row(["texture", "decoder", "largest difference from " + judge_name + ", any channel, any level"]))
    print(_row(["---"] * 3))
    for role, raw in shipped.items():
        for name, decode in available.items():
            if name == judge_name:
                continue
            worst = max(int(np.abs(decode(raw, level).astype(int) - judge(raw, level).astype(int)).max())
                        for level in range(len(dds_encode.bc3_levels(raw))))
            print(_row([f"`{role}`", name, worst]))
    skimage = _outside("skimage")
    if skimage:
        from skimage.color import deltaE_ciede2000, rgb2lab
        a, b = references["eyes"][0][..., :3], judge(shipped["eyes"], 0)[..., :3]
        formula = np.abs(delta_e2000(srgb_to_lab(a), srgb_to_lab(b)) - deltaE_ciede2000(srgb_to_lab(a), srgb_to_lab(b))).max()
        whole = np.abs(colour_difference(a, b) - deltaE_ciede2000(rgb2lab(a / 255.0), rgb2lab(b / 255.0))).max()
        print(f"\nCIEDE2000 here against scikit-image {skimage.__version__} on level 0 of the eyes: the formula differs "
              f"by at most {formula:.1e}, the whole path from sRGB by at most {whole:.4f}.")
    known = sum(len(names) for names in KNOWN_MISSES.values())
    print(f"\n{'Every level meets its limits' if not failures else f'{failures} level(s) are not as expected'}"
          f"{f', except the {known} misses listed in KNOWN_MISSES' if known and not failures else ''}.")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", type=Path, help="an earlier Miranda_LAS.zip, for the before rows")
    ap.add_argument("--sheet", type=Path, help="also write the before/after render to this PNG")
    args = ap.parse_args(argv)
    status = report(args.before)
    if args.sheet:
        sheet(args.sheet, args.before)
        print(f"\nsheet: {args.sheet}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
