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

Every stage leaves the same ``<out>/source_inventory.json``: what the source
archive contains (its hash, the VPK entries, both models' bones, meshes and
triangle counts, each texture's format and size). It holds no build result, so
it does not depend on which stage ran last. The copy in git is
``tools/pd2-las/source_inventory.json`` (`RECORD`); ``--stage inventory --out
tools/pd2-las`` rewrites it (the Makefile's ``inventory`` target), and a test
fails while it differs from a fresh one. A pack's ``BUILD_INFO.json`` embeds
the same record plus the hash of every converted texture.

Diesel `.model` authoring is not this script's job: `build_models.py` authors
the two models, runs these stages itself and adds the models to the pack. Run
on its own, this script leaves a scaffold (registration, textures and XMLs
only) marked WIP. See README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
#: The source inventory that is tracked in git, so that what the source archive
#: contains can be read without building anything.
RECORD = HERE / "source_inventory.json"

import numpy as np  # noqa: E402

from dds_encode import (  # noqa: E402
    attenuate_dxt5_alpha_from_normal,
    bc3_dds_from_levels,
    bc3_levels,
    box_reduce,
    decode_bc3_level,
    encode_bc3_texels,
    image_to_texels,
    linear_to_srgb,
    pad_to_blocks,
    srgb_to_linear,
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


#: The L4D2 addon the Miranda packs are built from, and the VPK inside it.
SOURCE_ZIP = HERE.parents[1] / "models" / "l4d2_miranda_lawson_1.zip"
VPK_INNER = "miranda_rochelle.vpk"


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


#: Side of the eye texture, in texels.
EYE_SIZE = 512
#: The iris of the eye texture, as distances from the centre in texture widths:
#: full iris up to the first, fading into the sclera up to the second.
EYE_IRIS_INNER, EYE_IRIS_OUTER = 0.25, 0.28
#: How much more an iris or pupil texel counts than a sclera texel when a block
#: of the eye texture is fitted. Measured on 2026-11-11: without it the iris of
#: the 8x8 level, which is on screen from 4 to 8 m at 1080p, is (44, 59, 87)
#: where the picture has (26, 59, 120); with it, (24, 57, 117).
EYE_IRIS_WEIGHT = 16


def mip_levels(rgba: np.ndarray) -> list[np.ndarray]:
    """A square power-of-two image and every level below it, down to 1x1.

    Each level is the area average of level 0, not of the level above it, so no
    rounding accumulates. Colour is averaged as light (sRGB decoded, averaged,
    encoded again): averaging the stored values instead darkens whatever has
    contrast, and a blue iris beside a black pupil is exactly that. Alpha is
    gloss, which is data, and is averaged as it is.
    """
    side = rgba.shape[0]
    if rgba.shape != (side, side, 4) or side & (side - 1):
        raise ValueError(f"expected a square power-of-two RGBA image, got {rgba.shape}")
    light = srgb_to_linear(rgba[..., :3] / 255.0)
    gloss = rgba[..., 3].astype(np.float64)
    levels = [rgba]
    for level in range(1, side.bit_length()):
        colour = np.rint(linear_to_srgb(box_reduce(light, 1 << level)) * 255.0)
        alpha = np.rint(box_reduce(gloss, 1 << level))
        levels.append(np.dstack([colour, alpha]).astype(np.uint8))
    return levels


def converted_face_diffuse(arc: VpkArchive) -> bytes:
    """The face diffuse as converted from the source, before the repaint.

    The source's colour blocks at every mip level, with the gloss in alpha: what
    the textures stage hands to `repainted_face_texture`. For tools and tests.
    """
    stem = "miranda_face_color"
    nm_stem, scale, max_a = DF_SPECULAR_FROM_NORMAL[stem]
    raw = {name: to_dds(parse_vtf(arc.read(f"materials/models/miranda/{name}.vtf")))
           for name in (stem, nm_stem)}
    return attenuate_dxt5_alpha_from_normal(raw[stem], raw[nm_stem], scale, max_a)


def repaint_face(rgba: np.ndarray) -> np.ndarray:
    """The face diffuse with the eye sockets darkened and the lash lines drawn.

    The Source model has separate eyelash and eye-shadow geometry that the port
    does not carry, so both are painted into the texture. Colour and gloss
    (alpha) change inside the painted areas and nowhere else.
    """
    face_rgba = rgba.copy()
    height, width = face_rgba.shape[:2]
    yy, xx = np.mgrid[0 : height, 0 : width].astype(np.float32)
    u = (xx + 0.5) / width
    v = (yy + 0.5) / height
    for uc, vc in ((0.454, 0.472), (0.559, 0.472)):
        d = np.hypot((u - uc) / 0.020, (v - vc) / 0.025)
        w_n = np.clip(1.0 - (d ** 1.6), 0.0, 1.0) * 0.90
        m = w_n > 0.0
        if m.any():
            rgb = face_rgba[m, :3].astype(np.float32)
            target = np.array([14.0, 7.0, 5.0], dtype=np.float32)
            face_rgba[m, :3] = np.clip(
                rgb * (1.0 - w_n[m, None]) + target * w_n[m, None],
                0.0,
                255.0,
            ).astype(np.uint8)
        m_spec = d < 1.0
        if m_spec.any():
            face_rgba[m_spec, 3] = np.minimum(face_rgba[m_spec, 3], 2)
    # Upper eyelid lash liner + upper waterline (L4D2 mesh has no separate 3D Eyelashes mesh)
    w_lash = np.zeros_like(u)
    for uc, u_min, u_max in ((0.260, 0.190, 0.322), (0.747, 0.684, 0.808)):
        du = (u - uc) / 0.062
        v_center = 0.293 + 0.003 * (du ** 2)
        dv = (v - v_center) / 0.011
        w_eye = np.exp(-(du ** 4) - (dv ** 2) * 1.8) * (
            (u >= u_min) & (u <= u_max) & (v <= 0.3055)
        )
        w_lash = np.maximum(w_lash, w_eye)
    w_wl = np.maximum(
        np.exp(-(((u - 0.068) / 0.042) ** 4) - (((v - 0.926) / 0.010) ** 2)),
        np.exp(-(((u - 0.927) / 0.036) ** 4) - (((v - 0.926) / 0.010) ** 2)),
    )
    w_l = np.clip(np.maximum(w_lash, w_wl) * 0.88, 0.0, 1.0)
    m_l = w_l > 0.02
    if m_l.any():
        rgb = face_rgba[m_l, :3].astype(np.float32)
        target_lash = np.array([18.0, 13.0, 11.0], dtype=np.float32)
        face_rgba[m_l, :3] = np.clip(
            rgb * (1.0 - w_l[m_l, None]) + target_lash * w_l[m_l, None],
            0.0,
            255.0,
        ).astype(np.uint8)
        face_rgba[w_l > 0.35, 3] = np.minimum(face_rgba[w_l > 0.35, 3], 4)
    return face_rgba


def face_levels(dds: bytes) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Every mip level of the face diffuse as the build means it, and where it differs.

    ``dds`` is the converted face diffuse: the source's colour blocks at every
    level, with the gloss in alpha. Returns ``(levels, changed)``, level 0 first:
    the image of each level, and for each texel whether its colour and whether
    its gloss differ from the converted texture, as an (h, w, 2) mask.

    Level 0 is the source's level 0, repainted. A level below it is the source's
    own level plus what the repaint added, averaged over each texel's area: the
    difference is taken as light, so that a texel half covered by a lash gets
    half of the lash's darkening. Outside the painted area the difference is
    zero and the level is the source's, texel for texel: its author's own mip
    levels are kept, not regenerated.

    Gloss is held to the ceiling the conversion was given. The conversion scales
    the two alpha endpoints of every block, and a block in the six-value mode has
    two more values that are constants, 0 and 255: ten texels of the source's
    level 1 come out of it at 255, full gloss.
    """
    ceiling = DF_SPECULAR_FROM_NORMAL["miranda_face_color"][2]
    source = [decode_bc3_level(dds, level) for level in range(len(bc3_levels(dds)))]
    side = source[0].shape[0]
    if [image.shape for image in source] != [(max(1, side >> k), max(1, side >> k), 4)
                                             for k in range(side.bit_length())]:
        raise ValueError("the face diffuse is not a square power-of-two texture with a full mip chain")
    painted = repaint_face(source[0])
    light = srgb_to_linear(painted[..., :3] / 255.0) - srgb_to_linear(source[0][..., :3] / 255.0)
    gloss = painted[..., 3].astype(np.float64) - source[0][..., 3]
    levels, changed = [], []
    for level, converted in enumerate(source):
        if level == 0:
            image = painted.copy()
        else:
            # far down, a texel covers so much that the repaint moves it by less
            # than one step of 255: such a texel comes out as it went in
            factor = 1 << level
            colour = linear_to_srgb(srgb_to_linear(converted[..., :3] / 255.0) + box_reduce(light, factor))
            alpha = converted[..., 3] + box_reduce(gloss, factor)[..., 0]
            image = np.dstack([np.rint(colour * 255.0), np.clip(np.rint(alpha), 0, 255)]).astype(np.uint8)
        image[..., 3] = np.minimum(image[..., 3], ceiling)
        levels.append(image)
        changed.append(np.stack([(image[..., :3] != converted[..., :3]).any(axis=2),
                                 image[..., 3] != converted[..., 3]], axis=-1))
    return levels, changed


def repainted_face_texture(dds: bytes) -> bytes:
    """The converted face diffuse with the repaint in every mip level.

    Only what changed is encoded again (`dds_encode.encode_bc3_texels`): the
    colour half of a block that holds a texel whose colour changed, the alpha
    half of one that holds a texel whose gloss changed. Every other byte of
    every level is the source's. Encoding the whole texture again, as this build
    did until 2026-11-11, costs every block a second lossy pass for the sake of
    the 2 % that changed, and it threw the source's mip levels away.
    """
    out = bytearray(dds)
    levels, changed = face_levels(dds)
    for (offset, _width, _height), image, differs in zip(bc3_levels(dds), levels, changed):
        padded = pad_to_blocks(image)
        across = padded.shape[1] // 4
        mask = pad_to_blocks(differs).reshape(-1, 4, across, 4, 2).any(axis=(1, 3)).reshape(-1, 2)
        blocks = np.flatnonzero(mask.any(axis=1))
        if not len(blocks):
            continue
        payload = np.frombuffer(out, dtype=np.uint8, count=padded.size // 4, offset=offset).reshape(-1, 16)
        encoded = encode_bc3_texels(image_to_texels(padded)[blocks])
        colour, alpha = mask[blocks, 0], mask[blocks, 1]
        payload[blocks[colour], 8:] = encoded[colour, 8:]
        payload[blocks[alpha], :8] = encoded[alpha, :8]
    return bytes(out)


def draw_eye(size: int = EYE_SIZE) -> np.ndarray:
    """The eye texture, level 0: (size, size, 4) uint8, one point per texel.

    Source draws its eyes with a shader of their own (iris, cornea and the
    lid's shadow are projected at run time) and has no texture that could be
    converted, so the eye is drawn here: sclera with the lid's shadow, a blue
    iris with fibres, a dark rim and the pupil. Alpha is gloss.

    The build draws it once, at `EYE_SIZE`, and averages that drawing for the
    levels below (`mip_levels`). Drawing it again at each smaller size, one
    point per texel, is not the same picture: the fibres fall between the
    points. `mip_audit.py` draws it at other sizes to measure both.
    """
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
    iris_outer, iris_inner, pupil_r = EYE_IRIS_OUTER, EYE_IRIS_INNER, 0.115
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
    return eye_rgba


def eye_weights() -> list[np.ndarray]:
    """For every mip level of the eye texture, how much each texel's colour counts.

    One for a texel of sclera, `EYE_IRIS_WEIGHT` for one of iris or pupil, and in
    between for a texel that holds some of both. The sclera fills most of the
    texture and the lids cover most of the sclera: what is seen of an eye is its
    iris. A block of a small level cannot hold both, and has to keep the iris.
    """
    centre = (np.arange(EYE_SIZE) + 0.5) / EYE_SIZE - 0.5
    radius = np.hypot(centre[None, :], centre[:, None])
    iris = np.clip((EYE_IRIS_OUTER - radius) / (EYE_IRIS_OUTER - EYE_IRIS_INNER), 0.0, 1.0)
    return [1 + np.rint((EYE_IRIS_WEIGHT - 1) * box_reduce(iris, 1 << level)[..., 0]).astype(np.int64)
            for level in range(EYE_SIZE.bit_length())]


def eye_texture() -> bytes:
    """The eye texture with its mip levels: drawn, averaged as light, fitted for the iris."""
    return bc3_dds_from_levels(mip_levels(draw_eye()), eye_weights())


def main(argv: list[str] | None = None) -> int:
    repo = HERE.parents[1]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(SOURCE_ZIP),
                    help="the L4D2 source zip (default: models/l4d2_miranda_lawson_1.zip)")
    ap.add_argument("--vpk-inner", default=VPK_INNER,
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

    # `--stage inventory` promises JSON on stdout, so its progress goes to stderr
    def say(text: str) -> None:
        print(text, file=sys.stderr if args.stage == "inventory" else sys.stdout)

    arc = VpkArchive.from_zip(source, args.vpk_inner)
    say(f"vpk: {len(arc.entries)} entries from {source.name}")

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
    say(
        f"models: tpp={tpp.name} ({len(tpp.bones)} bones, {tpp.triangle_count} tris) "
        f"fps={fps.name} ({len(fps.bones)} bones, {fps.triangle_count} tris)"
    )

    # So is what the source says about each texture: the headers are parsed here
    # for every stage, the pixels are converted only by the stages that need them.
    raw_vtf_imgs = {
        stem: parse_vtf(arc.read(f"materials/models/miranda/{stem}.vtf"))
        for stem in sorted(VTF_TO_PACK)
    }
    inventory["textures"] = {
        stem: {
            "format": img.format_name,
            "size": [img.width, img.height],
            "mips": img.mipmap_count,
            "pack_texture": f"{VTF_TO_PACK[stem]}.texture",
        }
        for stem, img in raw_vtf_imgs.items()
    }
    # What a pack embeds in BUILD_INFO.json: the inventory and, once the textures
    # are converted, the hash of each one as shipped. The hashes are build
    # results, so they stay out of the inventory itself, which would otherwise
    # depend on the stage that wrote it.
    build_record = inventory

    textures: dict[str, bytes] = {}
    if args.stage in ("textures", "all"):
        png_dir = out / "previews"
        png_dir.mkdir(parents=True, exist_ok=True)
        tex_dir = out / "textures"
        tex_dir.mkdir(parents=True, exist_ok=True)
        vtf_info = {}
        raw_dds = {stem: to_dds(img) for stem, img in raw_vtf_imgs.items()}
        for stem, pack_name in sorted(VTF_TO_PACK.items()):
            img = raw_vtf_imgs[stem]
            if stem in DF_SPECULAR_FROM_NORMAL:
                nm_stem, scale, max_a = DF_SPECULAR_FROM_NORMAL[stem]
                dds = attenuate_dxt5_alpha_from_normal(
                    raw_dds[stem], raw_dds[nm_stem], scale, max_a
                )
                if stem == "miranda_face_color":
                    dds = repainted_face_texture(dds)
            elif stem.endswith("_normal"):
                dds = swizzle_source_normal_dxt5_to_pd2(raw_dds[stem], invert_y=True)
            elif stem == "miranda_eyes":
                # drawn here, not converted, so it has no source blocks to keep
                dds = eye_texture()
            else:
                dds = raw_dds[stem]
            textures[f"{pack_name}.texture"] = dds
            (tex_dir / f"{pack_name}.texture").write_bytes(dds)
            (png_dir / f"{stem}.png").write_bytes(to_png(img))
            vtf_info[stem] = {
                **inventory["textures"][stem],
                "dds_sha256": hashlib.sha256(dds).hexdigest(),
            }
            print(f"texture: {stem} {img.format_name} {img.width}x{img.height} -> {pack_name}.texture")
        build_record = {**inventory, "textures": vtf_info}

    if args.stage in ("pack", "all"):
        if not textures:
            textures = {
                f"{p}.texture": (out / "textures" / f"{p}.texture").read_bytes()
                for p in list(VTF_TO_PACK.values())
            }
        # Icon: face diffuse resized to 256x256 and BC3-encoded. One level, as the
        # 2B pack's own icon has: the menu draws it at one size.
        import io

        from PIL import Image

        from dds_encode import rgba_to_bc3_dds

        face = Image.open(io.BytesIO(to_png(parse_vtf(arc.read("materials/models/miranda/miranda_face_color.vtf")))))
        icon_img = face.crop((face.width // 8, 0, face.width * 7 // 8, face.height // 2)).resize((256, 256))
        icon = rgba_to_bc3_dds(np.asarray(icon_img.convert("RGBA"), dtype=np.uint8))
        pack = write_pack(out, textures, icon, build_record, models_present=False)
        print(f"pack scaffold: {pack}")
        print("NOTE: Diesel .model files are not generated yet; scaffold is marked WIP.")

    inv_path = out / "source_inventory.json"
    inv_path.write_text(json.dumps(inventory, indent=2) + "\n")
    if args.stage == "inventory":
        # stdout is the JSON and nothing else, for scripting; the file is always persisted
        json.dump(inventory, sys.stdout, indent=2)
        print()
    else:
        print(f"inventory: {inv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
