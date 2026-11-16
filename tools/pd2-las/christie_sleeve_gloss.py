"""Conservative sleeve-only gloss retouch for the Christie source build.

Diffuse alpha is a specular mask in the PD2 shader. Faces are classified by
arm-bone weights and rasterised in their own material's wrapped UV space.
Blocks shared with non-sleeve faces are excluded, since BC3 edits a whole
4x4 block at once. The initial mip's RGB bytes are never changed; all lower
mip alpha levels are filtered from the retouched mip 0. This is an offline
approximation, not evidence of how the shader looks in game.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import dds_encode as enc

ARM_SHARE = 0.40
MAX_UV_SPAN = 0.12
ATTENUATION = 0.55
FEATHER_TEXELS = 3.0


def rasterize(uvs, faces, size: int, max_span: float | None = None):
    """Top-down UV triangle coverage, repeating wrapped fragments at all edges.

    Geometry UVs are (u, 1 - source_v); the sampler uses mod(-v, 1).
    Vertices 1 and 2 are unwrapped to the nearest tile of vertex 0. Large
    sleeve triangles are omitted as a guard against UV-spanning stitch faces.
    """
    image = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(image)
    uv = np.asarray(uvs, dtype=np.float64)
    for face in faces:
        tri = uv[list(face)].copy()
        tri[:, 0] = np.mod(tri[:, 0], 1.0)
        tri[:, 1] = np.mod(-tri[:, 1], 1.0)
        tri[1:] = tri[0] + np.mod(tri[1:] - tri[0] + 0.5, 1.0) - 0.5
        if max_span is not None and np.ptp(tri, axis=0).max() > max_span:
            continue
        tri -= np.floor(tri.mean(axis=0))
        for du in (-1, 0, 1):
            for dv in (-1, 0, 1):
                points = tri + (du, dv)
                if (points.max(axis=0) < 0).any() or (points.min(axis=0) > 1).any():
                    continue
                draw.polygon([(float(u * size), float(v * size)) for u, v in points], fill=255)
    return np.asarray(image, dtype=np.uint8)


def feather_coverage(hard, radius: float = FEATHER_TEXELS):
    """Blur across repeat boundaries, then clip the result to the hard mask."""
    height, width = hard.shape
    tiled = np.tile(hard, (3, 3))
    blurred = Image.fromarray(tiled).filter(ImageFilter.GaussianBlur(radius))
    center = np.asarray(blurred, dtype=np.float64)[height:2 * height, width:2 * width] / 255.0
    return np.where(hard > 0, center, 0.0)


def masks(group, role_by_material, sizes):
    """Per-role sleeve coverage and protection for non-sleeve faces."""
    share = np.array([sum(w for i, w in weights
                          if group.palette[i].endswith(('Arm', 'Hand'))
                          or 'Finger' in group.palette[i]) for weights in group.weights])
    classified = {role: ([], []) for role in sizes}
    covered = 0
    for material, _base_v, base_i, count, _n in group.slices:
        role = role_by_material[material]
        if base_i != covered * 3:
            raise ValueError('Christie face slices are not contiguous')
        for face in group.faces[covered:covered + count]:
            classified[role][0 if float(share[list(face)].mean()) > ARM_SHARE else 1].append(face)
        covered += count
    if covered != len(group.faces):
        raise ValueError('Christie face slices do not cover the mesh')
    result = {}
    for role, size in sizes.items():
        sleeve_faces, other_faces = classified[role]
        hard = rasterize(group.uvs, sleeve_faces, size, MAX_UV_SPAN)
        other = rasterize(group.uvs, other_faces, size)
        # Include a one-texel wrap-aware border for bilinear sampling.
        protected = other > 0
        protected = protected | np.roll(protected, 1, 0) | np.roll(protected, -1, 0)
        protected = protected | np.roll(protected, 1, 1) | np.roll(protected, -1, 1)
        result[role] = (feather_coverage(hard), protected)
    return result


def retouch(textures, masks_by_role, dds, prefix='christie'):
    """Attenuate safe mip-0 alpha blocks, then regenerate filtered submip alpha.

    Non-sleeve UVs and a one-texel sampling border are protected at mip 0.
    Shared BC3 blocks are skipped entirely. RGB block bytes at every level are
    retained. Lower-mip alpha is filtered, so it can mix adjacent UV islands;
    runtime appearance and cross-island filtering still need in-game testing.
    """
    report = {}
    for role, (strength, protected) in masks_by_role.items():
        key = f'{prefix}_{role}_df.texture'
        original = textures[key]
        size, _, mip0 = dds.dds_mip0_slice(original)
        if strength.shape != (size, size) or protected.shape != (size, size) or size < 4:
            raise ValueError(f'invalid mip-0 mask dimensions for {key}')
        blocks = size // 4
        block_strength = strength.reshape(blocks, 4, blocks, 4).mean(axis=(1, 3)).reshape(-1)
        block_protected = protected.reshape(blocks, 4, blocks, 4).any(axis=(1, 3)).reshape(-1)
        candidates = np.flatnonzero((block_strength > 0.004) & ~block_protected)
        payload = bytearray(mip0)
        modified = 0
        for i in candidates:
            start = int(i) * 16
            old = bytes(payload[start:start + 8])
            alpha = enc._dxt5_alpha_decode(np.frombuffer(old, dtype=np.uint8))
            replacement = enc._dxt5_alpha_encode(alpha * (1.0 - ATTENUATION * block_strength[i]))
            if replacement != old:
                payload[start:start + 8] = replacement
                modified += 1
        report[role] = {'candidate_blocks': int(len(candidates)), 'modified_blocks': modified,
                        'protected_blocks': int(block_protected.sum())}
        if not modified:
            continue
        levels = dds.mip_payloads_from_mip0(bytes(payload), size)
        # Filtering affects alpha alone: retain the original RGB blocks in
        # every lower level, including those outside the sleeve footprint.
        old_levels = enc.bc3_levels(original)
        for level in range(1, len(levels)):
            offset, _width, _height = old_levels[level]
            old_data = original[offset:offset + len(levels[level])]
            new_blocks = np.frombuffer(levels[level], dtype=np.uint8).reshape(-1, 16).copy()
            old_blocks = np.frombuffer(old_data, dtype=np.uint8).reshape(-1, 16)
            new_blocks[:, 8:] = old_blocks[:, 8:]
            levels[level] = new_blocks.tobytes()
        textures[key] = dds.pack_dds(levels, size)
        problems = dds.validate_dxt5_texture(textures[key])
        if problems:
            raise ValueError(f'{key}: {problems}')
    return report
