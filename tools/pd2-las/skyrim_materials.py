"""Skyrim SE shader material -> PAYDAY 2 `.material_config` + `.texture` files.

A Skyrim outfit carries `BSLightingShaderProperty` blocks whose texture sets
hold up to nine slots. This module maps the four that matter onto the two
textures Diesel binds (diffuse + normal) and writes the config that binds them.

The interesting part is the **alpha channels**, because they mean opposite
things in the two engines:

| channel | Skyrim | PAYDAY 2 |
| --- | --- | --- |
| diffuse alpha | opacity (`NiAlphaProperty` tests it) | **gloss**: 0 = matte, 255 = mirror |
| normal alpha | specular strength | unused (`DXT5nm` packing puts X here) |

So a straight copy would turn every garment into a chrome mirror and drop the
real specular map. `build_diffuse` therefore keeps the colour texels, discards
Skyrim's opacity, and writes **gloss = normal-map alpha x material scale x
metal mask**, which is what the `*_metal` texture is for (every fabric in this
outfit ships a 16x16 black one = matte; the necklace ships white = gold).

Nothing is re-encoded from a lossy source twice: DXT5 in, DXT5 out, and every
level of the mip chain is filtered before encoding so distant LODs stay clean.
"""

from __future__ import annotations

import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# what each logical material needs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaterialSpec:
    """One PD2 material: which NIF shape it comes from and how glossy it is."""

    name: str                      # PD2 material name in the model ("mtr_body")
    diffuse: str                   # texture stem inside the archive ("Jacket_diffA")
    normal: str | None             # ("Jacket_norm")
    metal: str | None = None       # ("Jacket_metal") -> multiplies the gloss
    gloss_scale: float = 0.55      # fabric is not chrome
    gloss_floor: int = 24          # DXT5 alpha steps so we never hit "matte black"
    tint: tuple[int, int, int] | None = None   # material albedo tint for our own maps
    generated: bool = False        # produced by skin_texture.py, not from 1.zip

    @property
    def pack_name(self) -> str:
        return self.name.replace("mtr_", "bw_")


# Attested render templates only. These two are copied verbatim from the 2B LAS
# pack (a released, working mod): Diesel silently renders a material black when
# a template names a keyword it does not know, so no experimenting here.
TPL_TPP = "generic:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"
TPL_FPS = "generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS"

DEFAULT_MATERIALS = (
    MaterialSpec("mtr_body", "", "", generated=True),
    MaterialSpec("mtr_jacket", "Jacket_diffA", "Jacket_norm", "Jacket_metal",
                 gloss_scale=0.42),
    MaterialSpec("mtr_jacket2", "Jacket2_diffA", "Jacket2_norm", "Jacket2_metal",
                 gloss_scale=0.38),
    MaterialSpec("mtr_skirt", "Skirt_diffA", "Skirt_norm", "Skirt_metal",
                 gloss_scale=0.40),
    MaterialSpec("mtr_heels", "Heels_diffA", "Heels_norm", "Heels_metal",
                 gloss_scale=0.62, gloss_floor=32),
)


# ---------------------------------------------------------------------------
# reading the archive
# ---------------------------------------------------------------------------
def _open_dds(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGBA"), dtype=np.uint8)


def load_source(path: Path, stem: str) -> np.ndarray:
    """One texture from a zip (`1.zip`) or an extracted directory."""
    if path.is_dir():
        return _open_dds((path / f"{stem}.dds").read_bytes())
    with zipfile.ZipFile(path) as zf:
        for name in (f"{stem}.dds", f"{stem}.DDS"):
            try:
                return _open_dds(zf.read(name))
            except KeyError:
                continue
    raise FileNotFoundError(f"{stem}.dds not found in {path}")


def _resize(img: np.ndarray, size: int) -> np.ndarray:
    """Lanczos resize of an (h, w, c) uint8 array, channels-preserving."""
    if img.shape[0] == size and img.shape[1] == size:
        return img.astype(np.uint8, copy=False)
    if img.ndim == 2:
        img = img[..., None]
    channels = [np.asarray(
        Image.fromarray(np.ascontiguousarray(img[..., i])).resize(
            (size, size), Image.LANCZOS), dtype=np.uint8)
        for i in range(img.shape[2])]
    return np.stack(channels, axis=-1)


# ---------------------------------------------------------------------------
# the two conversions
# ---------------------------------------------------------------------------
def build_diffuse(diffuse: np.ndarray, normal_alpha: np.ndarray | None,
                  metal: np.ndarray | None, spec: MaterialSpec,
                  size: int) -> np.ndarray:
    """Colour from the diffuse map, gloss in alpha (PD2's convention)."""
    rgb = _resize(diffuse, size)[..., :3]

    gloss = np.full((size, size), 255.0 if normal_alpha is None else 1.0, np.float32)
    if normal_alpha is not None:
        gloss = _resize(normal_alpha[..., None], size)[..., 0].astype(np.float32)
    if metal is not None:
        mask = _resize(metal, size)[..., :3].mean(axis=2).astype(np.float32) / 255.0
        # gold makes the whole surface metallic; black leaves fabric as it is
        gloss = gloss * (1.0 + 1.2 * mask)

    alpha = np.clip(gloss * spec.gloss_scale, spec.gloss_floor, 255).astype(np.uint8)
    out = np.empty((size, size, 4), np.uint8)
    out[..., :3] = rgb
    out[..., 3] = alpha
    return out


def build_normal(normal: np.ndarray, size: int, invert_y: bool = True) -> np.ndarray:
    """Skyrim tangent-space RGB normal -> Diesel's packed DXT5nm layout.

    Diesel's normal shader reads only alpha (X) and green (Y), so red goes to
    white, blue to black, X moves into alpha, and Y is inverted when the source
    is DirectX-style (`invert_y`), which Skyrim's are.
    """
    src = _resize(normal, size)[..., :3].astype(np.int16)
    out = np.zeros((size, size, 4), np.uint8)
    out[..., 0] = 255
    y = src[..., 1]
    out[..., 1] = np.clip(255 - y if invert_y else y, 0, 255).astype(np.uint8)
    out[..., 2] = 0
    out[..., 3] = np.clip(src[..., 0], 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------------------
# DDS writing (DXT5 + full mip chain)
# ---------------------------------------------------------------------------
def _encode_level(img: np.ndarray) -> bytes:
    from dds import encode_dxt5

    h, w = img.shape[:2]
    if h < 4 or w < 4:
        pad = np.repeat(np.repeat(img[max(h - 1, 0):h, :, :], 4, 0)[:4], 4, 1)[:4, :4]
        return encode_dxt5(np.ascontiguousarray(pad))
    if h % 4 or w % 4:
        raise ValueError(f"unaligned mip level {w}x{h}")
    return encode_dxt5(img)


def _downsample(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[0] // 2 * 2, img.shape[1] // 2 * 2
    q = img[:h, :w].astype(np.uint16)
    return ((q[0::2, 0::2] + q[1::2, 0::2] + q[0::2, 1::2] + q[1::2, 1::2]) // 4).astype(np.uint8)


def encode_dds(rgba: np.ndarray) -> bytes:
    """DXT5 DDS with every mip level present (PD2 body/garment textures ship them)."""
    levels = [rgba]
    while min(levels[-1].shape[:2]) > 1:
        levels.append(_downsample(levels[-1]))
    payload = b"".join(_encode_level(level) for level in levels)

    size = rgba.shape[0]
    mip0 = max(1, size // 4) ** 2 * 16
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000 | 0x20000)
    struct.pack_into("<II", header, 12, size, size)
    struct.pack_into("<I", header, 20, mip0)
    struct.pack_into("<I", header, 28, len(levels))
    struct.pack_into("<II", header, 76, 32, 0x4)
    header[84:88] = b"DXT5"
    struct.pack_into("<I", header, 108, 0x1000 | 0x8 | 0x400000)
    return bytes(header) + payload


# ---------------------------------------------------------------------------
# material_config
# ---------------------------------------------------------------------------
def render_material_config(unit_base: str, specs: list[MaterialSpec],
                           include_shadow: bool = True) -> str:
    """`<materials version="3">` with one entry per authored material."""
    parts = ['<materials version="3">\n']
    for spec in specs:
        stem = spec.pack_name
        parts.append(
            f'    <material name="{spec.name}" render_template="{TPL_TPP}" version="2">\n'
            f'        <bump_normal_texture file="{unit_base}/{stem}_nm"/>\n'
            f'        <diffuse_texture file="{unit_base}/{stem}_df"/>\n'
            "    </material>\n"
        )
    if include_shadow:
        parts.append(
            '    <material name="shadow_caster" '
            'render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n'
        )
    parts.append("</materials>\n")
    return "".join(parts)


def render_fps_material_config(unit_base: str, specs: list[MaterialSpec]) -> str:
    """First-person materials need DEPTH_SCALING so the viewmodel clips."""
    parts = ['<materials version="3">\n']
    for spec in specs:
        stem = spec.pack_name
        parts.append(
            f'    <material name="{spec.name}" render_template="{TPL_FPS}" version="2">\n'
            f'        <bump_normal_texture file="{unit_base}/{stem}_nm"/>\n'
            f'        <diffuse_texture file="{unit_base}/{stem}_df"/>\n'
            "    </material>\n"
        )
    parts.append(
        '    <material name="shadow_caster" '
        'render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n'
    )
    parts.append("</materials>\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------
def build_textures(source: Path, specs: list[MaterialSpec], size: int,
                   generated_dir: Path | None = None,
                   invert_y: bool = True) -> dict[str, bytes]:
    """stem -> DDS bytes for every material (df + nm)."""
    out: dict[str, bytes] = {}
    for spec in specs:
        stem = spec.pack_name
        if spec.generated:
            if generated_dir is None:
                raise ValueError(f"{spec.name} is generated; pass generated_dir")
            out[f"{stem}_df"] = (generated_dir / f"{stem}_df.texture").read_bytes()
            out[f"{stem}_nm"] = (generated_dir / f"{stem}_nm.texture").read_bytes()
            continue

        diffuse = load_source(source, spec.diffuse)
        normal = load_source(source, spec.normal) if spec.normal else None
        metal = load_source(source, spec.metal) if spec.metal else None
        target = min(size, diffuse.shape[0])

        df_rgba = build_diffuse(diffuse, normal[..., 3] if normal is not None else None,
                               metal, spec, target)
        out[f"{stem}_df"] = encode_dds(df_rgba)
        if normal is not None:
            out[f"{stem}_nm"] = encode_dds(build_normal(normal, target, invert_y))
    return out
