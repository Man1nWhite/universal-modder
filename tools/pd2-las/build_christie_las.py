#!/usr/bin/env python3
"""Build Christie LAS packs — body-only PAYDAY 2 LAS outfits from the DOA5 model.

Source: `references/Christie.zip` (Dead or Alive 5 Christie, costume c2:
`models/plasmid/doa5/christie_c2.{mdl,vvd,dx90.vtx,phy}` + VMT/VTF materials).
Outputs (in `dist/`):

- `Christie_LAS.zip`           — full body incl. Christie's own hands
- `Christie_LAS_Slim.zip`      — 10% thinner in width/depth (arms an extra 25%),
  height unchanged, hands cut at the wrist so the in-game gloves (changeable,
  via the glove adapter compat hook) show through the sleeves; `--variant slim`
  (the separate no-hands pack was removed — slim supersedes it)

Both are installable to `PAYDAY 2\\assets\\mod_overrides\\` with SuperBLT +
BeardLib + LAS/Wardrobe.

"Without head, like LAS does with police uniforms": both packs ship **no head
geometry** — the Christie face/lashes/eyes/glasses/hair meshes are all dropped —
and register `replace_body` (NOT `replace_all`; `replace_all` sets head=true in
LAS and would decapitate the heister). LAS then keeps the heister's own head.
The DOA5 rig is mapped onto the PD2 player skeleton via
`christie_skeleton_map.json`; geometry is retargeted with `build_models.py`'s
divergence-filter Umeyama fits and authored with the verified Diesel codec
against the 2B reference templates (references/2b.rar).

Textures: VTF -> DDS via `vtf.to_dds` (original DXT5 payloads, never
re-encoded); normal maps swizzled `invert_y=True`; the diffuse alpha channel is
rebuilt from the normal map's alpha (Source stores the phong mask there and
leaves diffuse alpha at 255, which PD2 reads as full mirror gloss — the washed
out look) via `dds_encode.attenuate_dxt5_alpha_from_normal`.

Usage (from the repo root):
  .venv/bin/python tools/pd2-las/build_christie_las.py \
      --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"            # base
  .venv/bin/python tools/pd2-las/build_christie_las.py --variant slim \
      --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"            # slim
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402
import dds_encode as dds  # noqa: E402
import segment_fit as sf  # noqa: E402
import las_outfit_pack as lop  # noqa: E402
import preview as pv  # noqa: E402
import source_model as sm  # noqa: E402
from dds_encode import (  # noqa: E402
    attenuate_dxt5_alpha_from_normal,
    swizzle_source_normal_dxt5_to_pd2,
)
from vtf import parse_vtf, to_dds  # noqa: E402

sys.path.insert(0, str(HERE.parent / "pd2-port"))
import dds as pd2_dds  # noqa: E402  (vanilla-shaped DXT5 DDS writer with full mip chain)

SOURCE_ZIP = REPO / "references" / "Christie.zip"
SKEL_MAP = HERE / "christie_skeleton_map.json"

MDL_PATH = "models/plasmid/doa5/christie_c2.mdl"
VVD_PATH = "models/plasmid/doa5/christie_c2.vvd"
VTX_PATH = "models/plasmid/doa5/christie_c2.dx90.vtx"
MAT_DIR = "materials/models/plasmid/doa5/christie/c2/"

HOOK_SOURCE = "lib/tweak_data/armorskinstweakdata"
GLOVE_HOOK_SOURCE = "lib/tweak_data/blackmarkettweakdata"

#: Horizontal (X/Y) scale for the slim variant; Z (height) is left untouched.
SLIM_SCALE = 0.9


@dataclass(frozen=True)
class Identity:
    """Everything that differs between the two Christie packs."""
    item_id: str
    pack_dir_name: str
    display_name: str
    description: str
    glove_adapter: bool          # no authored hands -> re-enable vanilla gloves

    @property
    def unit_base(self) -> str:
        return f"units/{self.item_id}/skins/{self.item_id}"

    @property
    def gui_base(self) -> str:
        return f"guis/dlcs/{self.item_id}/armor_skins"

    @property
    def tpp_unit(self) -> str:
        return f"{self.unit_base}/{self.item_id}"

    @property
    def fps_unit(self) -> str:
        return f"{self.unit_base}/fps_{self.item_id}"

    @property
    def texture_prefix(self) -> str:
        return self.item_id


IDENTITIES = {
    "base": Identity(
        item_id="christie",
        pack_dir_name="Christie_LAS",
        display_name="Christie (DOA5)",
        description=("Christie from Dead or Alive 5 joins the Payday Gang. "
                     "Body-only Legendary Armour Skins outfit (no head — the "
                     "heister keeps their own), built from the DOA5 christie_c2 "
                     "model."),
        glove_adapter=False,
    ),
    "slim": Identity(
        item_id="christie_slim",
        pack_dir_name="Christie_LAS_Slim",
        display_name="Christie (DOA5, slim, no hands)",
        description=("Christie from Dead or Alive 5, body-only LAS outfit scaled "
                     f"{(1 - SLIM_SCALE):.0%} thinner in width and depth (height "
                     "unchanged), hands cut at the wrist so the in-game gloves "
                     "show. No head — the heister keeps their own."),
        glove_adapter=True,
    ),
}

# Headless LAS contract: replace_body swaps body/arms/hands but leaves the
# head alone; replace_all would also replace the head and there is no head mesh
# in this pack, so claiming it would decapitate the heister.
FLAG_KEYS = (
    "hide_mask",
    "hide_armor",
    "replace_body",
    "fps_hide_armor",
    "fps_replace_body",
)

# source material -> (Diesel material slot, texture pair role)
KEEP_MATERIALS = {
    "cri_body_base": ("mtr_body", "body"),
    "cri_02_01_base": ("mtr_c02_01", "c02_01"),
    "cri_02_02_base": ("mtr_c02_02", "c02_02"),
    "cri_02_05_base": ("mtr_c02_05", "c02_05"),
}
# Specular attenuation for the diffuse alpha (normal VTF stem, scale, max_a),
# mirroring the Miranda route: Source keeps the phong mask in the normal map's
# alpha and leaves diffuse alpha at 255 = full mirror gloss in PD2.
DF_SPECULAR_FROM_NORMAL = {
    "cri_body_base": (0.25, 64),
    "cri_02_01_base": (0.20, 56),
    "cri_02_02_base": (0.18, 48),
    "cri_02_05_base": (0.15, 40),
}
# every other material in the model is head-carried (face, lashes, eyes,
# glasses, hair, helmet) and is dropped with the g_head drawables

TPP_GROUPS = {
    "body": {
        "drawables": ["g_body", "g_body_lod1"],
        "materials": list(KEEP_MATERIALS),
        "out_materials": [slot for slot, _ in KEEP_MATERIALS.values()],
        "mat_slots": {m: slot for m, (slot, _) in KEEP_MATERIALS.items()},
    },
    "shadow": {
        "drawables": ["s_body"],
        "materials": list(KEEP_MATERIALS),
        "out_materials": ["shadow_caster"],
        "mat_slots": {m: "shadow_caster" for m in KEEP_MATERIALS},
    },
}
DROP_DRAWABLES = ("g_head", "g_head_lod1")

MODEL_STRIDE = 148  # sizeof(mstudiomodel_t) for this MDL 48 build


# ---------------------------------------------------------------------------
# source loading (all bodygroup models, not just each bodypart's first)
# ---------------------------------------------------------------------------
def _read_vtx_meshes_all_models(vtx: bytes) -> list[tuple[int, list[tuple[int, int, int]]]]:
    """Like source_model._read_vtx_meshes but walks EVERY model of every
    bodypart (DOA5 ships body/glasses/bra/head variants this way), matching
    the MDL bodypart->model->mesh order."""
    out: list[tuple[int, list[tuple[int, int, int]]]] = []
    version, = struct.unpack_from("<i", vtx, 0)
    if version != sm.VTX_VERSION:
        raise sm.SourceModelError(f"unsupported VTX version {version}")
    _checksum, _num_lods, _mat_repl_off, num_bodyparts, bodypart_off = (
        struct.unpack_from("<iiiii", vtx, 16))
    mesh_index = 0
    for bi in range(num_bodyparts):
        bp = bodypart_off + bi * 8
        num_models, model_off = struct.unpack_from("<ii", vtx, bp)
        for mi in range(num_models):
            mo = bp + model_off + mi * 8
            num_lods_m, lod_off = struct.unpack_from("<ii", vtx, mo)
            for li in range(min(1, num_lods_m)):
                lo = mo + lod_off + li * 12
                num_meshes, mesh_off, _switch = struct.unpack_from("<iif", vtx, lo)
                for mesh_i in range(num_meshes):
                    me = lo + mesh_off + mesh_i * 9
                    num_groups, group_off, _flags = struct.unpack_from("<iiB", vtx, me)
                    triangles: list[tuple[int, int, int]] = []
                    seen: set[tuple[int, int, int]] = set()
                    for gi in range(num_groups):
                        go = me + group_off + gi * sm.VTX_SGROUP_STRIDE
                        (num_verts, vert_off, num_indices, index_off,
                         num_strips, strip_off) = struct.unpack_from("<iiiiii", vtx, go)
                        orig_ids = []
                        for vi in range(num_verts):
                            vbase = go + vert_off + vi * sm.VTX_VERTEX_STRIDE
                            (orig,) = struct.unpack_from("<H", vtx, vbase + 4)
                            orig_ids.append(orig)
                        indices = struct.unpack_from(f"<{num_indices}H", vtx, go + index_off)

                        def add_tri(a, b, c):
                            key = tuple(sorted((a, b, c)))
                            if key in seen:
                                return
                            seen.add(key)
                            triangles.append((a, b, c))

                        for si in range(num_strips):
                            so = go + strip_off + si * sm.VTX_STRIP_STRIDE
                            s_ni, s_ioff, s_nv, s_voff, _s_nb, s_flags = struct.unpack_from(
                                "<iiiiHB", vtx, so)
                            if s_flags & 0x02:
                                strip_idx = indices[s_ioff:s_ioff + s_ni]
                                for k in range(2, len(strip_idx)):
                                    a, b, c = (orig_ids[strip_idx[k - 2]],
                                               orig_ids[strip_idx[k - 1]],
                                               orig_ids[strip_idx[k]])
                                    if k % 2:
                                        a, b = b, a
                                    if a != b and b != c and a != c:
                                        add_tri(a, b, c)
                            else:
                                for t in range(0, s_ni, 3):
                                    add_tri(*(orig_ids[indices[s_ioff + t + k]]
                                              for k in range(3)))
                    out.append((mesh_index, triangles))
                    mesh_index += 1
    return out


def load_christie(zf: zipfile.ZipFile) -> sm.ModelData:
    """Parse the Christie MDL/VVD/VTX triple, including every bodygroup model."""
    mdl = zf.read(MDL_PATH)
    vvd = zf.read(VVD_PATH)
    vtx = zf.read(VTX_PATH)
    if mdl[:4] != sm.MDL_MAGIC:
        raise sm.SourceModelError("bad MDL magic")
    version, _checksum = struct.unpack_from("<ii", mdl, 4)
    if version not in sm.SUPPORTED_MDL_VERSIONS:
        raise sm.SourceModelError(f"unsupported MDL version {version}")

    base = 76
    base += 4            # length
    base += 12 * 6       # eye/illum/hull/view boxes
    base += 4            # flags
    bone_count, bone_off = struct.unpack_from("<ii", mdl, base); base += 8
    base += 8 * 5        # bonecontroller, hitbox, localanim, localseq, activity/events
    texture_count, texture_off = struct.unpack_from("<ii", mdl, base); base += 8
    base += 8            # texturedir
    base += 12           # skinref/skinfamily
    bodypart_count, bodypart_off = struct.unpack_from("<ii", mdl, base)

    bones = sm._read_bones(mdl, bone_count, bone_off)
    materials = sm._read_textures(mdl, texture_count, texture_off)

    mesh_specs: list[tuple[int, int]] = []  # (material_index, model vertex offset)
    model_numverts = 0
    model_name = sm._cstr(mdl, 12)
    for bi in range(bodypart_count):
        bp = bodypart_off + bi * sm.BODYPART_STRIDE
        _n, num_models, _b, model_index = struct.unpack_from("<iiii", mdl, bp)
        for mi in range(num_models):
            mo = bp + model_index + mi * MODEL_STRIDE
            if mi == 0 and bi == 0:
                model_name = sm._cstr(mdl, mo)
            num_meshes, mesh_index, num_vertices, vertex_index = struct.unpack_from(
                "<iiii", mdl, mo + 72)
            voff = vertex_index // sm.VERTEX_STRIDE_VVD
            model_numverts += num_vertices
            for mesh_i in range(num_meshes):
                me = mo + mesh_index + mesh_i * sm.MESH_STRIDE
                material, _mi, _nv, vertexoffset = struct.unpack_from("<iiii", mdl, me)
                mesh_specs.append((material, voff + vertexoffset))

    vertices = sm._read_vvd(vvd, model_numverts)
    vtx_meshes = _read_vtx_meshes_all_models(vtx)
    if len(vtx_meshes) != len(mesh_specs):
        raise sm.SourceModelError(
            f"VTX has {len(vtx_meshes)} meshes, MDL has {len(mesh_specs)}")

    out = sm.ModelData(name=model_name, bones=bones, materials=materials,
                       vertices=vertices)
    nverts = len(vertices)
    for (material_index, voff), (_mi, triangles) in zip(mesh_specs, vtx_meshes):
        flat: list[int] = []
        for tri in triangles:
            for idx in tri:
                gidx = voff + idx
                if not 0 <= gidx < nverts:
                    raise sm.SourceModelError(f"vertex index {gidx} out of range")
                flat.append(gidx)
        out.meshes.append(sm.SubMesh(material=materials[material_index],
                                     triangle_indices=tuple(flat)))
    return out


# ---------------------------------------------------------------------------
# textures
# ---------------------------------------------------------------------------
def _vmt_texture_path(vmt_text: str, key: str) -> str:
    m = re.search(r'"\$' + key + r'"\s+"([^"]+)"', vmt_text, re.I)
    if not m:
        raise ValueError(f"no ${key} in VMT")
    return "materials/" + m.group(1).replace("\\", "/").lower() + ".vtf"


def _with_full_mip_chain(dds_mip0: bytes) -> bytes:
    """Expand a 1-mip DXT5 .texture to vanilla PD2's full mipmap pyramid.

    The Christie VTFs ship a single mip, so `vtf.to_dds` emits a 1-mip DDS.
    Vanilla PAYDAY 2 DXT5 textures carry log2(size)+1 levels (see
    tools/pd2-port/dds.py: a mip-0-only file was a known defect that renders
    wrong in game). Mip 0 is decoded with Pillow (independent, correct DXT5
    decoder — pd2-port's decode_dxt5 mis-handles some blocks), the chain is
    box-filtered down to 1x1, and `pack_dds` writes the vanilla header shape
    (flags 0x000A1007, caps 0x00401008, c0 > c1 endpoints).
    """
    import io

    import numpy as np
    from PIL import Image

    size, _mips, mip0 = pd2_dds.dds_mip0_slice(dds_mip0)
    im = Image.open(io.BytesIO(dds_mip0))
    im.load()
    rgba = np.asarray(im.convert("RGBA"), dtype=np.uint8)
    payloads = pd2_dds.mip_payloads_from_image(rgba)
    return pd2_dds.pack_dds(payloads, size)


def convert_textures(zf: zipfile.ZipFile, identity: Identity) -> dict[str, bytes]:
    """VTF -> Diesel .texture payloads, keyed by pack stem (<id>_<role>_df.texture).

    Diffuse alpha is attenuated from the normal map's alpha (Source phong mask)
    so PD2 doesn't read full mirror gloss; the normal map itself is swizzled
    for Diesel (Y flipped). Every map gets a full mipmap pyramid (vanilla PD2
    shape) — the source VTFs carry only mip 0.
    """
    textures: dict[str, bytes] = {}
    for src_mat, (_slot, role) in KEEP_MATERIALS.items():
        vmt = zf.read(MAT_DIR + src_mat + ".vmt").decode("latin1")
        df_path = _vmt_texture_path(vmt, "basetexture")
        nm_path = _vmt_texture_path(vmt, "bumpmap")
        raw_df = to_dds(parse_vtf(zf.read(df_path)))
        raw_nm = to_dds(parse_vtf(zf.read(nm_path)))
        scale, max_a = DF_SPECULAR_FROM_NORMAL[src_mat]
        df_dds = attenuate_dxt5_alpha_from_normal(raw_df, raw_nm, scale, max_a)
        nm_dds = swizzle_source_normal_dxt5_to_pd2(raw_nm, invert_y=True)
        textures[f"{identity.texture_prefix}_{role}_df.texture"] = _with_full_mip_chain(df_dds)
        textures[f"{identity.texture_prefix}_{role}_nm.texture"] = _with_full_mip_chain(nm_dds)
    return textures


# --- sleeve gloss attenuation ------------------------------------------------
# The diffuse alpha IS the specular mask for PD2's DIFFUSE_TEXTURE:NORMALMAP
# shader. The sleeves' UV islands carry a stronger phong mask than the torso,
# which read as plastic sheen on the arms in game (2026-11-06 screenshots).
# Extra alpha attenuation inside the sleeve UV regions only:
SLEEVE_GLOSS_ATTEN = 0.55
SLEEVE_BONE_SHARE = 0.40    # vert counts as sleeve above this arm-chain share
SLEEVE_SPLAT_TEXELS = 24    # splat radius around each sleeve vert's UV (mip0 texels)


def sleeve_uv_masks(group: bm.Group) -> dict:
    """Per-material-role texel masks (1024x1024 working res) of sleeve UV regions.

    A vertex counts as sleeve when more than ``SLEEVE_BONE_SHARE`` of its skin
    weight sits on the arm chain (Arm/ForeArm/Hand/fingers). Each sleeve
    vertex's UV is splatted with a disc; the mask is box-blurred for
    feathering. Row convention matches ``preview_textured._sample`` with
    ``flip_v=True``: row 0 is internal v = 1.
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    armish = {n for n in group.palette
              if n.endswith("Arm") or n.endswith("ForeArm")
              or n.endswith("Hand") or "Finger" in n}
    roles = {KEEP_MATERIALS[src_mat][1]
             for src_mat, *_ in group.slices}
    WORK = 1024
    canvases = {role: Image.new("L", (WORK, WORK), 0) for role in roles}
    r = max(2, SLEEVE_SPLAT_TEXELS * WORK // 1024)
    for src_mat, base_v, _base_i, _tris, nverts in group.slices:
        role = KEEP_MATERIALS[src_mat][1]
        d = ImageDraw.Draw(canvases[role])
        for i in range(base_v, base_v + nverts):
            share = sum(w for pi, w in group.weights[i]
                        if group.palette[pi] in armish)
            if share <= SLEEVE_BONE_SHARE:
                continue
            u, v = group.uvs[i]
            # stored UVs are internal (u, -v_source): row 0 of the texture is
            # sampled at internal v = -1, so y = (1 + v) * size — this is the
            # same mapping preview_textured._sample(flip_v=True) applies.
            x, y = u * WORK, (1.0 + v) * WORK
            d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    out = {}
    for role, im in canvases.items():
        im = im.filter(ImageFilter.BoxBlur(max(1, r // 2)))
        out[role] = np.asarray(im, dtype=np.float64) / 255.0
    return out


def retouch_sleeve_gloss(textures: dict[str, bytes], group: bm.Group,
                         texture_prefix: str, texel_masks: dict) -> int:
    """Darken diffuse alpha (gloss) inside the sleeve UV regions, every mip.

    The .texture payloads carry a full mipmap pyramid with mip 0 first, so the
    per-level block grids all start at the payload front; each level's mask is
    the previous level's 2x2-block mean. Returns the number of blocks touched
    at mip 0.
    """
    import numpy as np

    total = 0
    for src_mat, (_slot, role) in KEEP_MATERIALS.items():
        key = f"{texture_prefix}_{role}_df.texture"
        if key not in textures:
            continue
        payload = bytearray(textures[key])
        h = int.from_bytes(payload[12:16], "little")
        w = int.from_bytes(payload[16:20], "little")
        # mip0 texel mask -> block grid, then halve per level
        from PIL import Image

        im = Image.fromarray((np.clip(texel_masks[role], 0, 1) * 255).astype(np.uint8))
        im = im.resize((w, h), Image.BILINEAR)
        block_mask = (np.asarray(im, dtype=np.float64) / 255.0)[:h // 4 * 4, :w // 4 * 4] \
            .reshape(h // 4, 4, w // 4, 4).mean(axis=(1, 3))
        off = 128
        level_mask = block_mask          # (h//4, w//4) for the current level
        while off < len(payload):
            bh, bw = level_mask.shape
            flat = level_mask.reshape(-1)
            for bi in np.where(flat > 0.004)[0]:
                fac = 1.0 - SLEEVE_GLOSS_ATTEN * float(flat[bi])
                blk = np.frombuffer(bytes(payload[off + 16 * bi:off + 16 * bi + 8]),
                                    dtype=np.uint8)
                alpha = dds._dxt5_alpha_decode(blk) * fac
                payload[off + 16 * bi: off + 16 * bi + 8] = dds._dxt5_alpha_encode(alpha)
            total += int((flat > 0.004).sum())
            off += 16 * bh * bw
            if h % 8 or w % 8 or bh < 2 or bw < 2:
                break                    # can't halve further cleanly
            h, w = h // 2, w // 2
            level_mask = level_mask.reshape(bh // 2, 2, bw // 2, 2).mean(axis=(1, 3))
        textures[key] = bytes(payload)
    return total


# ---------------------------------------------------------------------------
# no-hands cut: drop vertices dominated by hand/finger bones, then stretch the
# sleeves over the wrist gap so the glove spawn has no hole to float in
# ---------------------------------------------------------------------------
def cut_hands(g: bm.Group, min_weight: float = 0.5) -> bm.Group:
    """Complement of bm.extract_bones: remove geometry dominated by hand bones."""
    hand_pal = {i for i, n in enumerate(g.palette) if "Hand" in n}
    keep = [i for i, infl in enumerate(g.weights)
            if sum(w for p, w in infl if p in hand_pal) < min_weight]
    keep_set = set(keep)
    face_to_slice = {}
    for si, (_mat, _bv, base_i, tris, _nv) in enumerate(g.slices):
        for f in range(base_i // 3, base_i // 3 + tris):
            face_to_slice[f] = si

    by_slice: dict[int, list[tuple]] = {}
    for f, tri in enumerate(g.faces):
        a, b, c = tri
        if a in keep_set and b in keep_set and c in keep_set:
            by_slice.setdefault(face_to_slice.get(f, 0), []).append(tri)
    if not by_slice:
        raise SystemExit("cut_hands: no geometry left")

    out = bm.Group(name=g.name)
    out.palette = list(g.palette)
    removed = len(g.verts) - len(keep)
    for si in sorted(by_slice):
        tri_ids = by_slice[si]
        used: list[int] = []
        seen: dict[int, int] = {}
        local_faces = []
        for a, b, c in tri_ids:
            row = []
            for v in (a, b, c):
                if v not in seen:
                    seen[v] = len(used)
                    used.append(v)
                row.append(seen[v])
            local_faces.append(tuple(row))
        base_v = len(out.verts)
        for v in used:
            out.verts.append(g.verts[v])
            out.normals.append(g.normals[v])
            out.uvs.append(g.uvs[v])
            out.weights.append(g.weights[v])
        out.slices.append((g.slices[si][0], base_v, len(out.faces) * 3,
                           len(local_faces), len(used)))
        out.mat_slots.append(g.mat_slots[si])
        out.faces.extend((a + base_v, b + base_v, c + base_v)
                         for a, b, c in local_faces)
    print(f"[{g.name}] hands cut: {removed} verts removed, "
          f"{len(out.verts)} verts / {len(out.faces)} tris remain")
    return out


# ---------------------------------------------------------------------------
# arm-chain fit fix: align Arm/ForeArm/Shoulder segments directly onto the
# PD2 bind-pose pivots instead of build_models' Miranda-tuned menu pose
# ---------------------------------------------------------------------------
def fix_arm_fits(model: sm.ModelData, skel_map: dict, template: bm.Template,
                 fits: dict) -> dict:
    """Nudge the Arm/ForeArm fits so the elbow/wrist land on the PD2 pivots.

    `retarget_maps` builds the Arm/ForeArm bind operators through a
    standing-menu pose tuned for the L4D2 Miranda mesh (+1.2 cm shoulder
    width, elbow shifted 2.8 cm along the hinge axis). On the DOA5 rig that
    leaves the elbows ~5 cm inboard of PD2's Arm joints (measured x ±15.7 vs
    ±20.9), so the arms angle wrong in game.

    Why the pin from the menu-pose construction doesn't survive: _axial_mat
    pins the joint in the STANDING frame, but the TPP operator then composes
    M_menu^-1 (posed -> bind, target side) after it, which moves the pivot —
    hence the ~5.3 cm inboard elbows. This pass is the actual pin for the
    forearm: it KEEPS the rotation content of the composed operator and
    REPLACES only the translation, delta = target pivot - current mapped
    source joint, added to the matrix translation row.

    Re-fitting with a fresh rotation instead makes the shoulder-top verts
    (blended Spine1+Shoulder+Arm) overshoot to z≈190 — the harmonic blend of
    two very different rotations spikes. A translation cannot spike (blended
    translation error is bounded by max||delta||, a convex combination), and
    the joint deviation drops to 0 by construction.
    """
    import numpy as np

    src_worlds = bm.source_bone_worlds(model)

    def src_index_for_target(tname: str) -> int | None:
        for i, b in enumerate(model.bones):
            if skel_map["map"].get(b.name) == tname:
                return i
        return None

    def tgt_pos(tname: str) -> np.ndarray:
        w = template.worlds[template.name_id[tname]]
        return np.array(w[12:15], dtype=np.float64)

    fixed = 0
    for side in ("Left", "Right"):
        i_arm, i_fore, i_hand = (src_index_for_target(t) for t in
                                 (f"{side}Arm", f"{side}ForeArm", f"{side}Hand"))
        if i_arm is None or i_fore is None:
            continue
        # each source bone joint maps onto its same-named PD2 pivot:
        # Arm joint -> LeftArm pivot, ForeArm joint -> ForeArm pivot
        ps_a = np.array(src_worlds[i_arm][12:15], dtype=np.float64)
        pt_a = tgt_pos(f"{side}Arm")
        t = fits[i_arm]
        delta = pt_a - np.array(dm.mat_apply_point(t, tuple(ps_a)), dtype=np.float64)
        fits[i_arm] = tuple(t[k] + (float(delta[k - 12]) if 12 <= k <= 14 else 0.0)
                            for k in range(16))
        fixed += 1
        ps_f = np.array(src_worlds[i_fore][12:15], dtype=np.float64)
        pt_f = tgt_pos(f"{side}ForeArm")
        t = fits[i_fore]
        delta = pt_f - np.array(dm.mat_apply_point(t, tuple(ps_f)), dtype=np.float64)
        fits[i_fore] = tuple(t[k] + (float(delta[k - 12]) if 12 <= k <= 14 else 0.0)
                             for k in range(16))
        fixed += 1
        # wrist too: the glove spawns at the PD2 Hand joint, so the Hand fit
        # must land there as well or the spawned glove sits off the sleeve end
        if i_hand is not None:
            ps_h = np.array(src_worlds[i_hand][12:15], dtype=np.float64)
            pt_h = tgt_pos(f"{side}Hand")
            t = fits[i_hand]
            delta = pt_h - np.array(dm.mat_apply_point(t, tuple(ps_h)), dtype=np.float64)
            fits[i_hand] = tuple(t[k] + (float(delta[k - 12]) if 12 <= k <= 14 else 0.0)
                                 for k in range(16))
            fixed += 1
    print(f"arm chain re-fit: {fixed} fits translated onto the PD2 arm pivots")
    return fits


def weld_elbows(model: sm.ModelData, skel_map: dict,
                lo_cm: float = 4.0, hi_cm: float = 3.0) -> int:
    """Weld the inner elbow: split Arm/ForeArm skin weights across the joint.

    Near the elbow the source mesh has PURE Arm (w=1.0) and PURE ForeArm
    verts interleaved right at the crease. After the retarget the two bones'
    fits differ by the full elbow bend angle, so pure-weight neighbours get
    discontinuous transforms and the crease folds into a visible spike
    ("doesn't weld to a bone"). Fix: for every vertex whose axial position
    along the source Arm axis falls in [L - zone, L + zone], replace its
    Arm/ForeArm weights by a smoothstep split of their total:
    w_fa' = total * s, w_arm' = total * (1 - s),
    s = smoothstep((t - (L - lo_cm)) / (lo_cm + hi_cm)).
    The zone is asymmetric (lo_cm on the arm side, hi_cm past the joint)
    because the source arm is short (10.5 cm) while the target arm is
    23.3 cm — a symmetric 6 cm zone would spill ~13 cm into the target
    forearm and destroy the unblended acceptance slices.
    Weight sum is preserved (the split is of the total), so downstream
    consumers (harmonic transfer, slim _route_weights) are unaffected
    structurally; the packed blendweights carry the weld into the game.
    Returns the number of re-weighted vertices.
    """
    import numpy as np

    src_worlds = bm.source_bone_worlds(model)
    rev = {}
    for i, b in enumerate(model.bones):
        t = skel_map["map"].get(b.name)
        if t:
            rev[t] = i
    n_fixed = 0
    for side in ("Left", "Right"):
        i_arm, i_fore = rev.get(f"{side}Arm"), rev.get(f"{side}ForeArm")
        if i_arm is None or i_fore is None:
            continue
        a = np.array(src_worlds[i_arm][12:15], dtype=np.float64)
        b = np.array(src_worlds[i_fore][12:15], dtype=np.float64)
        d = b - a
        L = float(np.linalg.norm(d))
        u = d / L
        for vi, sv in enumerate(model.vertices):
            t = float(u @ (np.array(sv.pos, dtype=np.float64) - a))
            if not (L - lo_cm < t < L + hi_cm):
                continue
            w_arm = sum(w for bi, w in sv.weights if bi == i_arm)
            w_fa = sum(w for bi, w in sv.weights if bi == i_fore)
            total = w_arm + w_fa
            if total < 1e-6:
                continue
            s = _smoothstep((t - (L - lo_cm)) / (lo_cm + hi_cm))
            new = [(bi, w) for bi, w in sv.weights if bi not in (i_arm, i_fore)]
            new.append((i_arm, total * (1.0 - s)))
            new.append((i_fore, total * s))
            model.vertices[vi] = sm.SkinVertex(
                pos=sv.pos, normal=sv.normal, uv=sv.uv, weights=tuple(new))
            n_fixed += 1
    print(f"weld_elbows: {n_fixed} vertices re-weighted across the elbow crease "
          f"(zone {lo_cm}+{hi_cm} cm)")
    return n_fixed


# ---------------------------------------------------------------------------
# slim variant: cross-sectional thinning about each limb segment (v4)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# slim variant: cross-sectional thinning about each limb segment (v4 spec)
# ---------------------------------------------------------------------------
# Segment bone -> (child joint bone, cross-section scale). Each segment axis
# starts at its OWN joint and runs to the child joint (never the parent's).
SEGMENT_SPECS = {
    # 0.75 -> 0.80 (2026-11-06): at 25% the sleeves read stick-thin in game
    # next to the 0.90 torso/legs; 20% keeps the slim identity.
    "LeftArm": ("LeftForeArm", 0.80),
    "LeftForeArm": ("LeftHand", 0.80),
    "RightArm": ("RightForeArm", 0.80),
    "RightForeArm": ("RightHand", 0.80),
    "LeftUpLeg": ("LeftLeg", 0.90),
    "LeftLeg": ("LeftFoot", 0.90),
    "RightUpLeg": ("RightLeg", 0.90),
    "RightLeg": ("RightFoot", 0.90),
}
TORSO_BONES = ("Hips", "Spine", "Spine1")     # allowlist — nothing else is torso
SHOULDER_BONES = ("LeftShoulder", "RightShoulder")  # routed chest<->upper-arm
# everything else (Head, Neck, Hand*, fingers, Foot, ToeBase, ...) is protected

WRIST_RING_CM = 3.0    # surviving cuff ring = forearm verts within this of wrist
ANKLE_RING_CM = 3.0
NECK_FADE_CM = 4.0     # ~one neck radius below the Neck joint
ELBOW_CREASE_CM = 8.0  # verts within this euclidean distance of the elbow joint are protected from slim    # slim alpha fades to 0 this close to the Arm/ForeArm joint

# widen_elbow_blend: reach of the widened Arm/ForeArm weight window, in cm
# either side of the elbow pivot on the TARGET arm (23.3 cm). Calibrated on
# the hang-pose probe 2026-11-06: the shipped 4+3 cm weld left a braid of
# pleats at the in-game hang; 7+9 cm with a monotone material coordinate
# removes it (edge compression at 22 deg straightening: min ratio 0.70 ->
# 0.86) without touching the crease's bind-pose geometry.
ELBOW_WIDEN_A_CM = 7.0   # proximal (upper-arm) reach
ELBOW_WIDEN_B_CM = 9.0   # distal (forearm) reach

# slim bicep tuck: extra radial reduction of the upper-arm belly, on top of
# the segment scale (0.80). A smooth bump over the middle 45% of the Arm
# segment; the shoulder and the protected elbow crease are untouched.
BICEP_TUCK = 0.10
BICEP_BAND = (0.28, 0.72)   # normalized t/L where the bump rises and falls


def _smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def widen_elbow_blend(g: bm.Group, template: bm.Template,
                      a_cm: float = ELBOW_WIDEN_A_CM,
                      b_cm: float = ELBOW_WIDEN_B_CM) -> int:
    """Re-split Arm/ForeArm skin weights over a wider, monotone window.

    ``weld_elbows`` blends across a 4+3 cm window in *source* coordinates;
    on the 23.3 cm target arm that is a narrow, steep weight step. At the
    in-game idle the elbow hangs near straight while the bind pose bakes a
    ~72 deg bend, so the crease must unfold ~50 deg through that step — and
    the snug sleeve buckles into a braid of pleats (the X-fold seen in game
    2026-11-06, outer elbow, worst when the arm hangs). The 2B reference body
    blends over 16.2 cm with 331 mixed verts; Christie shipped 9.4 cm / 64.

    The fix re-splits each affected vertex's (Arm + ForeArm) mass by
    ``s = smoothstep((x + a) / (a + b))`` where ``x`` is a MONOTONE material
    coordinate: signed cm from the elbow measured along the vertex's own
    dominant-side bone axis (proximal verts on the Arm axis, distal verts on
    the ForeArm axis). The two axes meet at ~72 deg, so a single axial
    coordinate is discontinuous across the crease — exactly the mistake that
    makes a naive arc-length re-split fold *harder* (measured: opposed-normal
    pairs at the hang go 5 -> 12; the monotone split brings the braid down).

    A vertex carrying only one of the two bones gets the other bone ADDED in
    a free slot (blendindices is 4 wide; the encoder zero-pads). Weight sums
    are preserved exactly; positions, normals, UVs, palette and skeleton are
    untouched. Runs on the transferred groups (target space, both body and
    shadow, every variant) straight after ``transfer_group``, so the shipped
    weights are the measured ones.
    """
    import numpy as np

    if not g.verts:
        return 0
    moved = 0
    for side in ("Left", "Right"):
        A = _joint(template, f"{side}Arm")
        E = _joint(template, f"{side}ForeArm")
        H = _joint(template, f"{side}Hand")
        u_arm = E - A
        u_arm /= np.linalg.norm(u_arm)
        u_fa = H - E
        u_fa /= np.linalg.norm(u_fa)
        L_arm = float(np.linalg.norm(E - A))
        t_arm = (np.array(g.verts) - A) @ u_arm
        t_fa = (np.array(g.verts) - E) @ u_fa
        try:
            arm_i = g.palette.index(f"{side}Arm")
            fa_i = g.palette.index(f"{side}ForeArm")
        except ValueError:
            continue
        for i in range(len(g.weights)):
            infl = g.weights[i]
            w_arm = sum(w for pi, w in infl if pi == arm_i)
            w_fa = sum(w for pi, w in infl if pi == fa_i)
            tot = w_arm + w_fa
            if tot <= 0.02:
                continue
            if w_fa > w_arm:
                x = float(t_fa[i])
                if x > b_cm:
                    continue
            else:
                x = float(t_arm[i]) - L_arm
                if x < -a_cm:
                    continue
            s = _smoothstep((x + a_cm) / (a_cm + b_cm))
            new_fa, new_arm = tot * s, tot * (1.0 - s)
            if abs(new_fa - w_fa) < 1e-9 and abs(new_arm - w_arm) < 1e-9:
                continue
            out = [(pi, w) for pi, w in infl
                   if pi not in (arm_i, fa_i) and w > 1e-12]
            free = 4 - len(out)
            if w_arm <= 1e-12 and new_arm > 1e-9:
                if free <= 0:
                    continue
                free -= 1
            if w_fa <= 1e-12 and new_fa > 1e-9:
                if free <= 0:
                    continue
                free -= 1
            if new_arm > 1e-9:
                out.append((arm_i, new_arm))
            if new_fa > 1e-9:
                out.append((fa_i, new_fa))
            total = sum(w for _pi, w in out)
            g.weights[i] = [(pi, w / total) for pi, w in out]
            moved += 1
    return moved


def _joint(template: bm.Template, name: str):
    import numpy as np
    w = template.worlds[template.name_id[name]]
    return np.array(w[12:15], dtype=np.float64)


def _classify_palette(palette: list[str]) -> dict[str, str]:
    """Every palette bone must land in exactly one class; abort otherwise."""
    cls: dict[str, str] = {}
    for name in palette:
        if name in SEGMENT_SPECS:
            cls[name] = "segment"
        elif name in TORSO_BONES:
            cls[name] = "torso"
        elif name in SHOULDER_BONES:
            cls[name] = "shoulder"
        else:
            cls[name] = "protected"
    return cls


def _route_weights(g: bm.Group, template: bm.Template) -> list[dict[str, float]]:
    """Routed weights w~ per vertex over {segment bones..., 'torso'}.

    Only two weight edits (v4 §2):
      * Shoulder/clavicle splits along Shoulder->Arm: g = smoothstep of the
        axial fraction; (1-g) goes to torso, g to the upper arm.
      * Crotch: rho = min(wL,wR)/max(wL,wR) of the two UpLeg weights,
        m = smoothstep(rho); m*(wL+wR) goes to torso, (1-m) stays on the legs.
    Protected influences are NOT removed here — they simply never receive a
    deforming weight, so the identity remainder alpha_0 = 1 - sum(alpha_j)
    carries them (v4 §1).
    """
    import numpy as np

    sh = {s: (_joint(template, s), _joint(template, s.replace("Shoulder", "Arm")))
          for s in SHOULDER_BONES}
    routed: list[dict[str, float]] = []
    for i, weights in enumerate(g.weights):
        wsum = sum(w for _p, w in weights)
        if not (1.0 - 1e-4 <= wsum <= 1.0 + 1e-4):
            raise SystemExit(f"slim: vertex {i} skin weights sum to {wsum}, not 1")
        p = np.array(g.verts[i], dtype=np.float64)
        out: dict[str, float] = {}
        w_up = {"LeftUpLeg": 0.0, "RightUpLeg": 0.0}
        for pi, w in weights:
            name = g.palette[pi]
            if name in TORSO_BONES:
                out["torso"] = out.get("torso", 0.0) + w
            elif name in SEGMENT_SPECS:
                out[name] = out.get(name, 0.0) + w
            elif name in SHOULDER_BONES:
                a, b = sh[name]
                u = (b - a) / np.linalg.norm(b - a)
                L = float(np.linalg.norm(b - a))
                gfrac = _smoothstep(float(u @ (p - a)) / L)
                arm = name.replace("Shoulder", "Arm")
                out["torso"] = out.get("torso", 0.0) + (1.0 - gfrac) * w
                out[arm] = out.get(arm, 0.0) + gfrac * w
            elif name in ("LeftUpLeg", "RightUpLeg"):
                w_up[name] = w
            # protected: contributes alpha = 0 (identity), no bookkeeping
        # crotch rule on the thigh pair
        wl, wr = w_up["LeftUpLeg"], w_up["RightUpLeg"]
        if wl > 0.0 or wr > 0.0:
            hi = max(wl, wr)
            rho = min(wl, wr) / hi if hi > 0 else 0.0
            m = _smoothstep(rho)
            out["torso"] = out.get("torso", 0.0) + m * (wl + wr)
            if wl > 0:
                out["LeftUpLeg"] = out.get("LeftUpLeg", 0.0) + (1.0 - m) * wl
            if wr > 0:
                out["RightUpLeg"] = out.get("RightUpLeg", 0.0) + (1.0 - m) * wr
        routed.append(out)
    return routed


def _segment_geom(template: bm.Template) -> dict[str, tuple]:
    """segment bone -> (a, u, L, s, child) with a = own joint, u toward child."""
    import numpy as np

    geom = {}
    for bone, (child, s) in SEGMENT_SPECS.items():
        a = _joint(template, bone)
        b = _joint(template, child)
        d = b - a
        L = float(np.linalg.norm(d))
        geom[bone] = (a, d / L, L, s, child)
    return geom


def _torso_centerline(template: bm.Template) -> tuple:
    """Z-monotonic polyline c(z) through Hips/Spine/Spine1/Neck (+ vertical
    extension below Hips and above Neck). Aborts if not Z-monotonic."""
    import numpy as np

    pts = [_joint(template, n) for n in ("Hips", "Spine", "Spine1", "Neck")]
    zs = [p[2] for p in pts]
    if any(zs[i + 1] <= zs[i] for i in range(len(zs) - 1)):
        raise SystemExit(f"slim: torso polyline not Z-monotonic: {zs}")
    z = np.array(zs)
    cx = np.array([p[0] for p in pts])
    cy = np.array([p[1] for p in pts])

    def c(zz: float):
        zz = min(max(zz, z[0]), z[-1])   # vertical extension holds ends constant
        return float(np.interp(zz, z, cx)), float(np.interp(zz, z, cy))

    return c, z[-1]


def _ring_fade(geom_seg, ring_min_t: float, ring_radius: float, min_len_cm: float = 5.0):
    """Axial fade f(t): 1 below t0, smoothstep to 0 at t1=ring_min_t, with
    t1-t0 >= max(2R, min_len). Returns f(t) and t0."""
    t1 = ring_min_t
    fade_len = max(2.0 * ring_radius, min_len_cm)
    t0 = t1 - fade_len

    def f(t: float) -> float:
        if t <= t0:
            return 1.0
        if t >= t1:
            return 0.0
        return 1.0 - _smoothstep((t - t0) / (t1 - t0))

    return f, t0, t1


def _recompute_normals(g: bm.Group, n_old) -> None:
    """Area-weighted vertex normals from the final triangles; authored normal
    kept at hard edges (where recompute disagrees strongly)."""
    import numpy as np

    v = np.array(g.verts, dtype=np.float64)
    faces = np.array(g.faces, dtype=np.int64)
    acc = np.zeros_like(v)
    for f in faces:
        a, b, c = f
        fn = np.cross(v[b] - v[a], v[c] - v[a])
        acc[a] += fn
        acc[b] += fn
        acc[c] += fn
    n_new = acc / np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-12)
    hard = np.sum(n_new * n_old, axis=1) < 0.5
    n_new[hard] = n_old[hard]
    n_new /= np.maximum(np.linalg.norm(n_new, axis=1, keepdims=True), 1e-12)
    g.normals = [tuple(row) for row in n_new]


def _check_flips(g: bm.Group, v_old, tag: str) -> None:
    import numpy as np

    v = np.array(g.verts, dtype=np.float64)
    faces = np.array(g.faces, dtype=np.int64)
    to, tn = v_old[faces], v[faces]
    no = np.cross(to[:, 1] - to[:, 0], to[:, 2] - to[:, 0])
    nn = np.cross(tn[:, 1] - tn[:, 0], tn[:, 2] - tn[:, 0])
    dot = np.sum(no * nn, axis=1) / np.maximum(
        np.linalg.norm(no, axis=1) * np.linalg.norm(nn, axis=1), 1e-18)
    flips = int((dot <= 0.0).sum())
    if flips:
        bad = np.where(dot <= 0.0)[0]
        worst = bad[int(np.argmin(dot[bad]))]
        cen = tn[worst].mean(axis=0)
        area = 0.5 * float(np.linalg.norm(no[worst]))
        raise SystemExit(
            f"{tag}: {flips} triangles flipped (n'.n <= 0); worst at "
            f"({cen[0]:.1f}, {cen[1]:.1f}, {cen[2]:.1f}) cm, "
            f"{area:.3f} cm^2 before, edge stretch "
            f"{np.linalg.norm(tn[worst] - to[worst], axis=1).max():.2f} cm")


def straighten_segments(g: bm.Group, template: bm.Template,
                        bones=("LeftArm", "RightArm", "LeftForeArm", "RightForeArm"),
                        bin_cm: float = 2.0, perp_max: float = 4.5,
                        w_min: float = 0.85, edge_fade_cm: float = 6.0,
                        cap_cm: float = 3.5, min_slice: int = 6) -> bm.Group:
    """Straighten limb segments in bind pose (mesh-only, weights untouched).

    The source rig is straight but the menu-pose retarget leaves a mid-segment
    kink (visible as a second "bend" past the elbow in the forearm renders).
    For each segment, fit a deg-2 centerline offset c_hat(t) to the per-slice
    perpendicular MEDIANS of its pure high-weight verts, then displace
    p' = p - sum_j w_j * g_j(t) * c_hat_j(t).

    Robustness notes (v3 of this pass):
      * slice medians instead of centroids, tight radius mask (only verts
        actually inside the limb), slices from the segment interior only —
        the elbow/wrist blend zones at the ends are contaminated and
        previously poisoned the global deg-2 fit, warping the whole segment;
      * the centerline is fitted in a 2D orthonormal basis (e1, e2) perp to
        the segment axis u. A component-wise median of the 3D offsets r does
        NOT preserve u^T c = 0 (u is not axis-aligned), which leaked a small
        axial component and made t' = t only approximate. In the (e1, e2)
        basis the correction is exactly perpendicular, so the axial
        coordinate is preserved exactly (t' = t) and each slice translates
        rigidly — injectivity within a slice is then guaranteed;
      * the polynomial is fitted in the normalized variable
        xn = (t - L/2) / (L/2) in [-1, 1] — raw t up to ~22 makes the
        Vandermonde matrix (1, t, t^2) ill-conditioned;
      * cap_cm is a LOUD ASSERT, not a silent clip: if the fitted correction
        exceeds it the build fails, instead of introducing a shading kink at
        the clip boundary. 3.5 cm is still well under the 4.5 cm limb radius
        mask, so a fit that large is a real kink, not noise;
      * 6 cm end fades (the elbow/wrist blend verts then barely move, so
        the later slim pass cannot flip them); flip check still runs.
    """
    import numpy as np

    routed = _route_weights(g, template)
    geom = _segment_geom(template)
    v = np.array(g.verts, dtype=np.float64)
    n_old = np.array(g.normals, dtype=np.float64)
    new = v.copy()
    for bone in bones:
        if bone not in geom:
            continue
        a, u, L, s, child = geom[bone]
        u = u / np.linalg.norm(u)
        # orthonormal basis (e1, e2) perpendicular to the segment axis
        tmp = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1 = np.cross(u, tmp)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(u, e1)
        ts = (v - a) @ u
        r = (v - a) - np.outer(ts, u)
        perp = np.linalg.norm(r, axis=1)
        wgt = np.array([rw.get(bone, 0.0) for rw in routed])
        core = (wgt > w_min) & (perp < perp_max) & (ts >= 0.0) & (ts <= L)
        if core.sum() < 40:
            continue
        # per-slice median of the 2D (perp-plane) offsets, interior slices only
        tks, cks, nks = [], [], []
        for t0 in np.arange(edge_fade_cm, L - edge_fade_cm, bin_cm):
            m = core & (ts >= t0) & (ts < t0 + bin_cm)
            if m.sum() < min_slice:
                continue
            r2 = r[m] @ np.stack([e1, e2], axis=1)          # (n, 2), exactly perp u
            c2 = np.median(r2, axis=0)
            tks.append(float(ts[m].mean()))
            cks.append(c2)
            nks.append(int(m.sum()))
        if len(tks) < 4:
            continue
        tks = np.array(tks)
        cks = np.array(cks)                                  # (k, 2)
        nks = np.array(nks, dtype=np.float64)
        xn = (tks - L / 2.0) / (L / 2.0)                      # in [-1, 1]
        A = np.stack([np.ones_like(xn), xn, xn * xn], axis=1)
        coef, *_ = np.linalg.lstsq(A * nks[:, None], cks * nks[:, None], rcond=None)

        def chat2(x):                                        # -> 2D perp offset
            return coef[0] + coef[1] * x + coef[2] * x * x

        # loud cap over the FITTED interior range only (the polynomial may
        # extrapolate larger values into the faded ends, where it is never
        # applied with full weight): the correction that actually gets applied
        # must stay under cap_cm, else fail instead of silently clipping.
        xs = np.linspace(float(xn.min()), float(xn.max()), 200)
        cmax = float(np.linalg.norm(np.array([chat2(x) for x in xs]), axis=1).max())
        if cmax > cap_cm:
            raise SystemExit(
                f"straighten {bone}: fitted correction {cmax:.2f} cm exceeds "
                f"cap {cap_cm} cm — refusing to silently clip (shading kink)")

        def chat(t):                                         # -> 3D, perp u exactly
            c2 = chat2((t - L / 2.0) / (L / 2.0))
            return c2[0] * e1 + c2[1] * e2

        gfade = np.array([_smoothstep(t / edge_fade_cm)
                          * _smoothstep((L - t) / edge_fade_cm) for t in ts])
        disp = -(wgt * gfade)[:, None] * np.array([chat(t) for t in ts])
        # axial leak must be exactly zero by construction; verify numerically
        leak = float(np.abs((np.array([chat(t) for t in ts]) @ u)).max())
        new = new + disp
        print(f"  straighten {bone}: {int(core.sum())} core verts, "
              f"{len(tks)} slices, max correction {cmax:.2f} cm, "
              f"axial leak {leak:.2e} cm")
    g.verts = [tuple(row) for row in new]
    _check_flips(g, v, f"straighten {g.name}")
    _recompute_normals(g, n_old)
    return g


# ---------------------------------------------------------------------------
# centring: put the limb tubes back on the bones that drive them
# ---------------------------------------------------------------------------
#: Which limbs to centre - forearms only, and deliberately so.
#:
#: Measured on the shipped pack against PD2's own fitted 2B body (see
#: segment_fit.py, cross-section circle centres): the forearm is the only
#: segment whose tube really leaves its bone - its centre walks from 1.6 cm off
#: the ForeArm axis at the elbow to 3.3 cm at the wrist (slim: 3.8-4.0),
#: against a flat 0.4-1.2 cm for 2B. Everything else that looks like a big
#: number is not a defect:
#:   * thigh 10 cm at the hip  - that is the blazer hem flaring out, and it is
#:     weighted to UpLeg on purpose (a coat has to swing with the leg);
#:   * upper arm 5-7 cm        - 6-14 verts per slab around the deltoid mass,
#:     so the slab medians scatter by several cm (2B: 3.7 cm). Sampling noise.
#: Centring those would fold the coat into the leg and nudge a shoulder that is
#: not measurably wrong, so this pass stays on the one segment with evidence.
CENTRE_SEGMENTS = ("LeftForeArm", "RightForeArm")
CENTRE_SLICES = 14        # axial slabs per segment
CENTRE_W_MIN = 0.05       # vert must carry *any* real weight on this bone
#: weight at which a vertex moves with its slab at full strength. Below it the
#: displacement ramps to zero so the correction can never step across a seam
#: (the mouth ring is 0.8 ForeArm / 0.2 Hand; the layers of one cross-section
#: agree to within ~0.1, so they move together), and a vertex that carries no
#: ForeArm weight at all - the other arm, the legs, the hand beyond the mouth -
#: does not move at all.
CENTRE_W_SAT = 0.85
#: cm of axial taper at the wrist end of the correction (0 = none: the mouth
#: ring moves with the sleeve). Sized to the seam it has to absorb: the mouth
#: ring and the glove ring behind it are a couple of cm apart, and a 3 cm
#: translation spread over no distance folds the seam's triangles flat.
CENTRE_TAIL_FADE = 2.5
CENTRE_EDGE_FADE = 6.0    # cm of axial fade at the elbow end
#: 3D fade radius around each end of the segment, (r0, r1): 0 inside r0, 1
#: outside r1. Asymmetric on purpose.
#:
#: Head (elbow/knee/hip): wide. The elbow crease has PURE ForeArm verts next to
#: 20%-ForeArm ones a couple of cm away; an axial-only fade moved those
#: neighbours by 1.3 cm vs 0.3 cm and folded two 3 cm^2 crease triangles. The
#: joint-radius zone (the same idea as slim's ELBOW_CREASE_CM protection) cannot
#: fold anything, because nothing inside it moves at all.
#:
#: Tail (wrist): tight. The drift being corrected is *largest* at the wrist, so
#: a wide fade would leave the sleeve end - the ring the in-game glove spawns
#: inside - uncorrected. There is no crease there to fold (the weights go
#: smoothly ForeArm -> Hand, and the Hand fit is aligned with the forearm), and
#: the flip check is the arbiter.
CENTRE_JOINT_FADE_HEAD = (6.0, 10.0)
CENTRE_JOINT_FADE_TAIL = (0.0, 3.0)
CENTRE_CAP_CM = 4.0       # loud assert, not a silent clip (measured 2.1-3.1)


def _centre_line(slices, L: float):  # noqa: ARG001  (L documents the segment)
    """Linear mesh-centreline of one limb segment: c(t) = c0 + c1 * t.


    The low-frequency shape that can be corrected without inventing geometry.
    The forearm is the motivating case: its cross-section centres walk from
    1.6 cm off the ``ForeArm`` axis at the elbow to 3.3 cm at the wrist (2B
    reference: flat, <= 1.2 cm), i.e. a *drift*, so a rigid shift fixes the
    middle of the sleeve and leaves both ends wrong. Higher-order terms are
    deliberately not fitted: the circle-centre residuals are ~0.3-0.9 cm and a
    quadratic through them passes exactly that noise variance straight into the
    mesh.
    """
    import numpy as np

    if len(slices) < 3:
        return None
    ts = np.array([sl[0] for sl in slices])
    cs = np.array([sl[1] for sl in slices])
    wts = np.array([sl[2] for sl in slices], float)
    # vertex-count weighting, not sqrt: the proximal slabs are thin (11 verts
    # against 70 two cm lower) and would otherwise set the intercept, which is
    # then extrapolated 7 cm up the arm.
    A = np.stack([np.ones_like(ts), ts], axis=1) * wts[:, None]
    coef, *_ = np.linalg.lstsq(A, cs * wts[:, None], rcond=None)
    c0, c1 = coef[0], coef[1]
    resid = float(np.average(np.linalg.norm(cs - (c0 + np.outer(ts, c1)), axis=1),
                             weights=wts))
    t_lo, t_hi = float(ts.min()), float(ts.max())

    def chat(t: float):
        """Line inside the measured slab range, held constant outside it.

        Extrapolating is what turns a 0.7 cm intercept error into a 4 cm
        correction at the wrist; outside the slabs the tube is measured
        nowhere, so the end value is carried flat (same idiom as
        ``_torso_centerline``'s vertical extension).
        """
        return c0 + c1 * min(max(t, t_lo), t_hi)

    return chat, c0, c1, resid, (t_lo, t_hi)


def centre_segments(g: bm.Group, template: bm.Template,
                    bones=CENTRE_SEGMENTS) -> list[dict]:
    """Slide each limb tube sideways so its axis lies on its bone's axis.

    The retarget is a similarity/affine fit, so limb geometry that sits a
    couple of cm off its *source* bone keeps that offset in PD2 space - and the
    offsets do not cancel: in the shipped Christie pack the thigh is 10.3 cm
    off the ``UpLeg`` axis at the hip (2B reference: 4.7 cm) and the upper arm
    5-7 cm off the ``Arm`` axis near the shoulder (2B: 3.7 cm). Visually the
    bone runs along the edge of the sleeve and the elbow dot sits on the
    silhouette.

    ``straighten_segments`` cannot fix this: its radial mask (``perp_max``
    4.5 cm) is an *absolute* distance from the bone axis, so the verts that are
    wrong are exactly the ones it excludes - it re-centres what is already
    close and ignores the offenders.

    A vertex moves by ``ramp(w) * fade(t) * chat(t)``, with
    ``ramp(w) = smoothstep(w / CENTRE_W_SAT)`` **saturated**: within one
    cross-section the sleeve's layers (weights 0.8-1.0) all move by the same
    vector, so the section keeps its shape and only translates; the hand beyond
    the mouth (weight 0) does not move at all, and neither does anything else
    in the body. Two neighbouring ways of doing this were both tried on the
    shipped pack and both are wrong:

      * ``w * fade * chat`` - what this pass used to do. A cross-section is a
        *stack* (outer sleeve, mid layer, bare arm, plus the blazer's cuff
        flap), so scaling each layer by its own weight slides the layers
        through each other and leaves the flap behind: measured, the section
        then *spreads* until its fitted radius is 3.9 cm instead of 2.2;
      * ``fade * chat`` with no weight factor at all - translates every vertex
        on that side of the body, including the hand and the leg. The leg
        crease number is what catches it (5.91 -> 4.56 cm).

    ``chat`` is the segment's measured mesh-centreline (``_centre_line``: a
    vertex-weighted line through the slab centres). Measured profile on the
    shipped base pack, slab centre off the bone axis:

        t (cm)      5.6   8.0  13.6  16.4  18.9  20.5  21.8
        offset      1.24   2.2  0.27  0.41  1.23  1.95  2.15

    i.e. a bow: about a cm at the elbow, small mid-segment, and 2 cm at the
    mouth. Two consequences encoded below:

      * the fade is **elbow-only**. The old tail fade ``smoothstep((L-t)/6)``
        is 0.36 at t=20 and 0.12 at the mouth - it deleted the correction
        exactly where the sleeve is furthest off the bone, which is why the
        shipped cuff ring sat 2.2 cm off the ``Hand`` pivot;
      * the weight threshold is 0.05, not 0.5. The mouth ring is 0.8
        ForeArm / 0.2 Hand, and the verts that hold the cuff's shape are the
        partial-weight ones.

    The elbow keeps a wide 3D fade (``CENTRE_JOINT_FADE_HEAD``): its crease has
    PURE ``ForeArm`` verts next to 20 %-ones a couple of cm away, and a
    translation that is smooth in ``t`` is still a step across that seam. The
    axial coordinate ``t`` is preserved exactly (the correction is perpendicular
    by construction) and skin weights are untouched, so the skeleton, bind
    matrices and bone lengths all stay as they are. ``_check_flips`` is the
    gate.

    Returns one record per re-centred segment for the build report.
    """
    import numpy as np

    import segment_fit as sf

    routed = _route_weights(g, template)
    geom = _segment_geom(template)
    v = np.array(g.verts, dtype=np.float64)
    n_old = np.array(g.normals, dtype=np.float64)
    new = v.copy()
    records: list[dict] = []
    for bone in bones:
        if bone not in geom:
            continue
        a, u, L, _s, child = geom[bone]
        wgt = np.array([rw.get(bone, 0.0) for rw in routed])
        slices = [sl for sl in sf.slice_offsets(v, wgt, (a, u, L, child),
                                               slices=CENTRE_SLICES,
                                               min_w=CENTRE_W_MIN)
                  if CENTRE_EDGE_FADE <= sl[0] <= L]
        if len(slices) < 3:
            print(f"  centre {bone}: only {len(slices)} usable slabs, skipped")
            continue
        fit = _centre_line(slices, L)
        if fit is None:
            print(f"  centre {bone}: too few usable slabs, skipped")
            continue
        chat, c0, c1, residual, (t_lo, t_hi) = fit

        # loud cap over the range the field is actually applied to (the line is
        # held flat outside the slab range, so the endpoints bound it)
        xs = np.array([0.0, L])
        cmax = float(np.linalg.norm(np.array([chat(x) for x in xs]), axis=1).max())
        if cmax > CENTRE_CAP_CM:
            raise SystemExit(
                f"centre {bone}: centreline reaches {cmax:.2f} cm off the bone "
                f"(cap {CENTRE_CAP_CM} cm) - refusing to silently clip")
        ts = (v - a) @ u
        d_head = np.linalg.norm(v - a, axis=1)

        def _jfade(d, band):
            r0, r1 = band
            if r1 <= r0:
                return 0.0 if d <= r0 else 1.0
            return _smoothstep((d - r0) / (r1 - r0))

        fade = np.array([_smoothstep(t / CENTRE_EDGE_FADE)
                         * _smoothstep((L - t) / CENTRE_TAIL_FADE)
                         if CENTRE_TAIL_FADE > 0 else
                         _smoothstep(t / CENTRE_EDGE_FADE)
                         for t in ts]) * np.array(
            [_jfade(dh, CENTRE_JOINT_FADE_HEAD) for dh in d_head])
        corr = np.array([chat(t) for t in ts])
        leak = float(np.abs(corr @ u).max())
        if leak > 1e-9:
            raise SystemExit(f"centre {bone}: axial leak {leak:.2e} cm")
        # saturated-weight ramp: ~1 everywhere the sleeve lives, 0 off the bone
        ramp = np.array([_smoothstep(w / CENTRE_W_SAT) for w in wgt])
        new = new - (ramp * fade)[:, None] * corr
        records.append({"bone": bone,
                        "joint_offset_cm": round(float(np.linalg.norm(chat(0.0))), 2),
                        "wrist_offset_cm": round(float(np.linalg.norm(chat(L))), 2),
                        "residual_cm": round(residual, 2),
                        "slabs": len(slices),
                        "slab_span_cm": [round(t_lo, 1), round(t_hi, 1)],
                        "moved_verts": int((wgt > 0.0).sum()),
                        "verts": int((wgt >= 0.5).sum())})
        print(f"  centre {bone}: {int((wgt > 0.0).sum())} weighted verts, "
              f"{len(slices)} slabs over t={t_lo:.1f}-{t_hi:.1f} cm of "
              f"L={L:.1f}, centreline "
              f"{np.linalg.norm(chat(0.0)):.2f} cm at the elbow -> "
              f"{np.linalg.norm(chat(L)):.2f} cm at the mouth, residual wobble "
              f"{residual:.2f} cm, axial leak {leak:.2e} cm")
    moved = float(np.linalg.norm(new - v, axis=1).max()) if len(new) else 0.0
    print(f"centre_segments: {len(records)} segments re-centred onto their bones "
          f"(largest displacement {moved:.2f} cm)")
    g.verts = [tuple(row) for row in new]
    _check_flips(g, v, f"centre {g.name}")
    _recompute_normals(g, n_old)
    return records


# ---------------------------------------------------------------------------
# elbow trim: the arm is thickest exactly at the joint
# ---------------------------------------------------------------------------
#: Thickness (p90 radius over a 2 cm band about the Arm->ForeArm->Hand polyline)
#: along the arm, arc length from the shoulder:
#:
#:     arc (cm)   18     22     26
#:     Christie  7.34   8.16   6.83
#:     2B ref    6.72   7.03   6.02
#:
#: Both meshes thicken at the elbow, but Christie bulges 0.8 cm *more* than the
#: reference does relative to its own arm, and that is what reads as a puffy
#: elbow. Two measurement traps worth remembering, both of which produced
#: nonsense here first:
#:
#:   * the segments meet at 72 degrees, so a window that selects by *axial*
#:     coordinate about one axis catches the other segment's cross-section -
#:     the profile only means anything along the chain (arc length);
#:   * the outer surface of the elbow is ~8 cm from the joint, i.e. further
#:     away than chunks of the arm that are 8 cm up the bone, so "distance to
#:     the joint" is not a usable locality either. Arc length along the chain
#:     is the only unambiguous one.
ELBOW_TRIM = 0.88            # radial scale at the joint
ELBOW_TRIM_FLAT_CM = 2.0     # full strength this close (arc) to the joint
ELBOW_TRIM_FADE_CM = 6.0     # ... zero by this far, for a C1 blend
ELBOW_TRIM_W_MIN = 0.5       # sleeve verts only (Arm+ForeArm weight)

#: Outer-elbow de-puff (2026-11-07). The trim above is a uniform radial
#: squeeze. The side that actually suffers when the elbow straightens in game
#: is the *outside* of the bend: the bind pose bakes 72 deg, the idle hangs at
#: ~12 deg (see ``ELBOW_BEND_AXIS``), and the outer surface therefore has to
#: give back ~r*dtheta of length. Measured on the shipped pack, the worst edge
#: in the elbow window shortens 3.12 cm at that angle (PD2's own 2B body: 0.98
#: cm) and the surface crumples to absorb it. Squeezing only the outer side,
#: over a wider window, removes part of the excess where it is generated:
#: max edge shortening 3.12 -> 2.28 cm and the worst compression 0.19 -> 0.27
#: of bind length, with 0 inverted faces before and after and the crook of the
#: elbow untouched. Numbers and the axis bug that hid this are in
#: docs/pd2-las/CHRISTIE.md ("The elbow, measured on the elbow's own axis").
ELBOW_OUTER_TRIM = 0.65      # extra radial scale on the outer elbow
ELBOW_OUTER_FLAT_CM = 3.0    # full strength this close (arc) to the joint
ELBOW_OUTER_FADE_CM = 9.0    # ... zero by this far
ELBOW_OUTER_FLOOR = 0.15     # residual share applied all round the ring
ELBOW_OUTER_SPAN_CM = 6.0    # |offset| that counts as "fully on the outer side"

#: Which local axis of the PD2 ``ForeArm`` bone is elbow *flexion*. Verified on
#: the 2B template: rotating about local X leaves the Arm-ForeArm angle at its
#: bind 72.1 deg for every angle (it swings the forearm on a cone - a twist of
#: the sleeve about the upper arm), while local Y moves the joint angle 1:1
#: (bind 72.1 deg -> 0.1 deg at -72). Every posed elbow probe must use Y; the
#: 2026-11-06 round used X and therefore measured a twisted sleeve, not a bent
#: one.
ELBOW_BEND_AXIS = 1
ELBOW_BIND_DEG = 72.0
ELBOW_IDLE_DEG = 12.0        # in-game idle: the elbow hangs nearly straight


def _chain_param(v, chain):
    """Arc length along `chain` of each point's nearest point, plus the offset."""
    import numpy as np

    best = np.full(len(v), np.inf)
    off = np.zeros_like(v)
    arc = np.zeros(len(v))
    acc = 0.0
    for a, b in zip(chain[:-1], chain[1:]):
        ab = b - a
        L = float(np.linalg.norm(ab))
        u = ab / L
        t = np.clip((v - a) @ u, 0.0, L)
        p = a + np.outer(t, u)
        d = np.linalg.norm(v - p, axis=1)
        better = d < best
        best = np.where(better, d, best)
        off = np.where(better[:, None], v - p, off)
        arc = np.where(better, t + acc, arc)
        acc += L
    return arc, off


def trim_elbows(g: bm.Group, template: bm.Template,
                bones=(("LeftArm", "LeftForeArm", "LeftHand"),
                       ("RightArm", "RightForeArm", "RightHand")),
                scale: float = ELBOW_TRIM) -> list[dict]:
    """Squeeze the elbow bulge radially about the arm chain, mesh-only.

    ``p' = p + a(p) * (scale - 1) * r(p)`` where ``r`` is the offset from the
    nearest point on ``Shoulder->Elbow->Wrist`` (so each vertex moves toward the
    arm's own centreline, not toward a bone axis that only describes one of the
    two segments) and ``a`` is 1 within ``ELBOW_TRIM_FLAT_CM`` of the joint in
    *arc length*, fading to 0 at ``ELBOW_TRIM_FADE_CM``.

    Locality has to be arc length. The two segments meet at 72 degrees and the
    outer surface of the elbow is about 8 cm from the joint, so both "axial
    coordinate about a segment" and "distance to the joint" select the wrong
    set: measured, an axial blend moved the bulge by 0.01 cm out of the 0.66 cm
    it should move, and a spherical one moved 20 vertices by 0.06 cm.

    Vertices need at least ``ELBOW_TRIM_W_MIN`` on ``Arm+ForeArm`` and are
    additionally scaled by ``1 - w(hand)``, so the hand and its cuff are not
    moved out from under it. Skeleton, bind matrices, bone lengths and skin
    weights are untouched; ``_check_flips`` gates the build and the crease
    metric in the fit report catches a crease that followed the shrink.
    """
    import numpy as np

    routed = _route_weights(g, template)
    v = np.array(g.verts, dtype=np.float64)
    n_old = np.array(g.normals, dtype=np.float64)
    new = v.copy()
    records: list[dict] = []
    for parent, child, hand in bones:
        if parent not in template.name_id or child not in template.name_id:
            continue
        chain = [_joint(template, parent), _joint(template, child),
                 _joint(template, hand)]
        s_joint = float(np.linalg.norm(chain[1] - chain[0]))
        arc, off = _chain_param(v, chain)
        d_arc = np.abs(arc - s_joint)
        blend = np.array([_smoothstep((ELBOW_TRIM_FADE_CM - d) /
                                      (ELBOW_TRIM_FADE_CM - ELBOW_TRIM_FLAT_CM))
                          for d in d_arc])
        w_pair = np.array([rw.get(parent, 0.0) + rw.get(child, 0.0) for rw in routed])
        w_hand = np.array([rw.get(hand, 0.0) for rw in routed])
        alpha = blend * np.array([_smoothstep(w / ELBOW_TRIM_W_MIN) for w in w_pair]) \
            * (1.0 - np.clip(w_hand, 0.0, 1.0))
        disp = (alpha * (scale - 1.0))[:, None] * off
        # --- outer-side de-puff (see ELBOW_OUTER_TRIM) --------------------
        # The bend-plane bisector points into the crook, so the outer elbow is
        # the side with a NEGATIVE projection on it. Its extent is taken from
        # the offset about the chain, not from the distance to the joint.
        u_arm = chain[1] - chain[0]
        u_arm /= np.linalg.norm(u_arm)
        u_fore = chain[2] - chain[1]
        u_fore /= np.linalg.norm(u_fore)
        crook = u_arm + u_fore
        crook /= np.linalg.norm(crook)
        outer = np.clip(-(v - chain[1]) @ crook / ELBOW_OUTER_SPAN_CM, 0.0, 1.0)
        outer_blend = np.array([_smoothstep((ELBOW_OUTER_FADE_CM - d) /
                                           (ELBOW_OUTER_FADE_CM - ELBOW_OUTER_FLAT_CM))
                                for d in d_arc])
        alpha_out = outer_blend * alpha * (ELBOW_OUTER_FLOOR
                                          + (1.0 - ELBOW_OUTER_FLOOR) * outer)
        disp = disp + (alpha_out * (ELBOW_OUTER_TRIM - 1.0))[:, None] * off
        mov = np.linalg.norm(disp, axis=1) > 1e-6
        if not mov.any():
            continue
        new = new + disp
        records.append({"joint": child, "scale": scale, "outer_scale": ELBOW_OUTER_TRIM,
                        "verts": int(mov.sum()),
                        "max_shift_cm": round(float(np.linalg.norm(disp, axis=1).max()), 2)})
        print(f"  trim {child}: {records[-1]['verts']} verts, radial scale "
              f"{scale} (outer {ELBOW_OUTER_TRIM}) about the arm chain, largest "
              f"shift {records[-1]['max_shift_cm']} cm")
    g.verts = [tuple(row) for row in new]
    _check_flips(g, v, f"elbow trim {g.name}")
    _recompute_normals(g, n_old)
    return records


def slim_group(g: bm.Group, template: bm.Template, scale: float = SLIM_SCALE,
               arm_scale: float = 0.75) -> bm.Group:
    """v4 cross-sectional slimming, bind pose, mesh-only (skeleton, bone
    lengths, bind matrices and skin weights untouched).

    p' = p + sum_j alpha_j * D_j(p), all D_j from the original p,
    alpha_j = w~_j * f_j(t) >= 0, alpha_0 = 1 - sum(alpha_j) (identity).
    Protected verts (head/neck/hands/fingers/feet/toes dominant) and the
    surviving wrist/ankle cuff rings are enforced p' = p bitwise.
    Normals are recomputed from the final triangles (hard edges kept).
    """
    import numpy as np

    cls = _classify_palette(g.palette)
    unclassified = [n for n in g.palette if n not in cls]
    if unclassified:
        raise SystemExit(f"slim: unclassified palette bones: {sorted(set(unclassified))}")
    routed = _route_weights(g, template)
    geom = _segment_geom(template)
    center, z_neck = _torso_centerline(template)

    v = np.array(g.verts, dtype=np.float64)
    n_old = np.array(g.normals, dtype=np.float64)
    nv = len(v)

    # -- per-segment centroid check (signed offsets; bone axis trusted only
    #    if the mid-segment centroid sits within 10% of the radius) --------
    seg_axis = {}
    for bone, (a, u, L, s, child) in geom.items():
        idx = [i for i in range(nv)
               if routed[i].get(bone, 0.0) > 0.9
               and 0.3 * L <= float(u @ (v[i] - a)) <= 0.7 * L]
        if len(idx) < 8:
            seg_axis[bone] = ("bone", None)
            continue
        ts = np.array([float(u @ (v[i] - a)) for i in idx])
        rs = np.array([(v[i] - a) - float(u @ (v[i] - a)) * u for i in idx])
        mean_r = rs.mean(axis=0)
        radius = float(np.linalg.norm(rs, axis=1).mean())
        if radius > 1e-6 and np.linalg.norm(mean_r) > 0.10 * radius:
            # centroid mode: smoothed (linear-in-t) fit of the slice centroids
            A = np.stack([np.ones_like(ts), ts], axis=1)
            coef, *_ = np.linalg.lstsq(A, rs, rcond=None)
            seg_axis[bone] = ("centroid", (coef, a, u))
            print(f"  [{bone}] bone off-center "
                  f"({np.linalg.norm(mean_r):.2f} cm > 10% of {radius:.2f}); "
                  f"centroid mode")
        else:
            seg_axis[bone] = ("bone", None)

    # -- cuff / ankle rings and fades ---------------------------------------
    # surviving ring: segment verts within RING_CM proximal of the wrist/ankle
    def ring_of(bone: str, ring_cm: float) -> tuple[set[int], float, float]:
        a, u, L, s, child = geom[bone]
        t_end = L  # child joint axial coordinate
        idx = {i for i in range(nv)
               if routed[i].get(bone, 0.0) > 0.0 and float(u @ (v[i] - a)) >= t_end - ring_cm}
        if not idx:
            return set(), t_end, 0.0
        rad = float(np.mean([np.linalg.norm((v[i] - a) - float(u @ (v[i] - a)) * u)
                             for i in idx]))
        return idx, t_end - ring_cm, rad

    fades = {}
    protected = set()
    for side in ("Left", "Right"):
        ring, t1, R = ring_of(f"{side}ForeArm", WRIST_RING_CM)
        f, t0, _ = _ring_fade(geom[f"{side}ForeArm"], t1, R)
        protected |= ring
        # Forearm wrist fade (2026-11-06): the slim scale used to run at full
        # strength up to the bitwise-protected 3 cm cuff ring, pinching the
        # mid-forearm against an untouched mouth (flare 2.27x vs the 2B
        # reference's 1.63x — the "trumpet" step at the wrist in game). Ease
        # the slim alpha out over the last ~8 cm so the sleeve opens
        # gradually; the mouth itself keeps base volume for the spawned glove.
        fades[f"{side}ForeArm"] = f
        # elbow crease ring: the Arm/ForeArm axes meet at ~100 deg and the
        # welded crease weights vary across it, so ANY per-vertex blend of the
        # two segment deforms folds thin crease triangles (hard flip fail).
        # Verts within ELBOW_CREASE_CM of the elbow JOINT (euclidean, either
        # side) are protected (p' = p, bitwise) — the crease keeps base
        # thickness. NB: test distance to the joint, not axial t per segment
        # (every upper-arm vert has t_fa < 0 and vice versa).
        elbow = geom[f"{side}ForeArm"][0]
        for i in range(nv):
            rw = routed[i]
            if rw.get(f"{side}Arm", 0.0) + rw.get(f"{side}ForeArm", 0.0) < 0.05:
                continue
            if float(np.linalg.norm(v[i] - elbow)) < ELBOW_CREASE_CM:
                protected.add(i)
        ring, t1, R = ring_of(f"{side}Leg", ANKLE_RING_CM)
        f, t0, _ = _ring_fade(geom[f"{side}Leg"], t1, R)
        fades[f"{side}Leg"] = f
        protected |= ring
    # protected-dominant verts (hand/finger/foot/toe/head/neck) enforced p'=p
    for i, weights in enumerate(g.weights):
        pi, _w = max(weights, key=lambda t: t[1])
        if cls[g.palette[pi]] == "protected":
            protected.add(i)

    # -- apply ---------------------------------------------------------------
    new_v = v.copy()
    for i in range(nv):
        p = v[i]
        disp = np.zeros(3)
        rw = routed[i]
        for bone, w in rw.items():
            if w <= 0.0:
                continue
            if bone == "torso":
                cx, cy = center(p[2])
                s_eff = scale + (1.0 - scale) * _smoothstep(
                    (p[2] - (z_neck - NECK_FADE_CM)) / NECK_FADE_CM)
                disp += w * (s_eff - 1.0) * np.array([p[0] - cx, p[1] - cy, 0.0])
                continue
            a, u, L, s, child = geom[bone]
            t = float(u @ (p - a))
            r = (p - a) - t * u
            mode, fit = seg_axis[bone]
            if mode == "centroid":
                coef, _a, _u = fit
                r = r - (coef[0] + coef[1] * t)
            f = fades.get(bone)
            alpha = w * (f(t) if f is not None else 1.0)
            if bone in ("LeftArm", "RightArm"):
                # bicep tuck: extra radial reduction of the upper-arm belly
                # (exact match: "LeftForeArm" also endswith("Arm")!)
                # The segment scale moves verts (1-s) of the way to the axis;
                # to land the FINAL belly radius at s*(1 - TUCK*bump) the
                # displacement must be amplified by 1 + s*TUCK*bump/(1-s),
                # not dimmed (dimming moves verts LESS, i.e. a fatter belly).
                xn = t / L
                lo, hi = BICEP_BAND
                half = 0.5 * (hi - lo)
                bump = (_smoothstep((xn - lo) / half)
                        * _smoothstep((hi - xn) / half)) if lo < xn < hi else 0.0
                alpha *= 1.0 + s * BICEP_TUCK * bump / (1.0 - s)
            disp += alpha * (s - 1.0) * r
        new_v[i] = p + disp
    # enforced identity on protected verts and cuff/ankle rings (bitwise)
    for i in protected:
        new_v[i] = v[i]

    # -- integrity: flips are hard failures; area/edge shrinkage is flagged --
    g.verts = [tuple(row) for row in new_v]
    _check_flips(g, v, f"slim {g.name}")
    faces = np.array(g.faces, dtype=np.int64)
    tri_old = v[faces]
    tri_new = new_v[faces]
    ao = np.linalg.norm(np.cross(tri_old[:, 1] - tri_old[:, 0],
                                 tri_old[:, 2] - tri_old[:, 0]), axis=1)
    an = np.linalg.norm(np.cross(tri_new[:, 1] - tri_new[:, 0],
                                 tri_new[:, 2] - tri_new[:, 0]), axis=1)
    area_ratio = an / np.maximum(ao, 1e-18)
    flagged = int(((area_ratio < 0.45) | (area_ratio > 1.1)).sum())
    print(f"[{g.name}] slim v4: flips 0, area-flagged {flagged} tris, "
          f"protected verts {len(protected)}")

    # -- normals from the final triangles (hard edges keep authored normal) --
    _recompute_normals(g, n_old)
    print(f"[{g.name}] slim v4 done: x {np.ptp(new_v[:, 0]):.1f} cm, "
          f"y {np.ptp(new_v[:, 1]):.1f} cm, z {np.ptp(new_v[:, 2]):.1f} cm "
          f"(z [{new_v[:, 2].min():.2f}, {new_v[:, 2].max():.2f}])")
    return g

# ---------------------------------------------------------------------------
# pack XML renderers (same contract as las_pack.py / las_outfit_pack.py)
# ---------------------------------------------------------------------------
def render_hook_lua(identity: Identity, with_fps: bool) -> str:
    flags = ",\n".join(f"\t{k} = true" for k in FLAG_KEYS)
    lines = [
        "LegendaryArmours = LegendaryArmours or {}",
        "la = LegendaryArmours",
        "",
        f"la.{identity.item_id} = {{",
        f'\tcategory = "{identity.item_id}",',
        "",
        f'\tunit = "{identity.tpp_unit}",',
    ]
    if with_fps:
        lines.append(f'\tfps_unit = "{identity.fps_unit}",')
    lines += ["", flags, "}", ""]
    return "\n".join(lines)


def render_glove_adapter_lua(identity: Identity) -> str:
    """Compat hook restoring vanilla glove behaviour for the no-hands pack.

    Same rationale as las_outfit_pack.render_glove_adapter_lua (LAS 4.1.9's
    loader forces default_glove_id = false and disables the glove adapter for
    replace_body outfits): with no authored hands the heister needs a real
    default glove so "Default" gloves spawn hands, and the adapter must be an
    empty *table* (BeardLib table.merge would call pairs(true) on a boolean).
    """
    key = f"las_{identity.item_id}"
    return f"""-- {identity.pack_dir_name} LAS: vanilla-suit glove behaviour for {key}.
-- This outfit ships NO hands (cut at the wrist), so the heister's own gloves
-- must spawn: LAS forces default_glove_id = false (no hands at all) and
-- disables the glove adapter. Restore a real default glove, re-enable the
-- adapter, and keep the stock hands visible as fallback.
-- See las_outfit_pack.render_glove_adapter_lua for the full rationale.
Hooks:PostHook(BlackMarketTweakData, "init", "{identity.item_id}_GloveAdapter", function(self)
\tlocal ps = self.player_styles and self.player_styles["{key}"]
\tif not ps then return end

\t-- A real default glove, exactly like the vanilla/DLC suits (LAS's
\t-- fresh-table read drops this, leaving "Default" gloves with no unit).
\tps.default_glove_id = "heist_default"

\t-- Enable the adapter with a table (NOT a boolean: BeardLib's table.merge
\t-- would call pairs(true)). An empty table keeps the default hnd_forearms.
\tps.glove_adapter = {{}}

\t-- Drop the exclude-list entry LAS added for replace_body.
\tlocal list = self.glove_adapter and self.glove_adapter.player_style_exclude_list
\tif list then
\t\tfor i = #list, 1, -1 do
\t\t\tif list[i] == "{key}" then table.remove(list, i) end
\t\tend
\tend

\t-- Keep the stock hands visible as a guaranteed fallback.
\tif ps.body_replacement then ps.body_replacement.hands = false end
\tif ps.third_body_replacement then ps.third_body_replacement.hands = false end
end)
"""


def render_localization(identity: Identity) -> str:
    return json.dumps(
        {
            f"bm_menu_{identity.item_id}_armor_skins": identity.display_name,
            f"bm_askn_{identity.item_id}": identity.display_name,
            f"bm_askn_{identity.item_id}_desc": identity.description,
        },
        indent=2,
    )


def render_main_xml(identity: Identity, texture_stems: list[str],
                    with_fps: bool) -> str:
    # df_nm registers the PAIR by base name; the engine appends _df/_nm itself
    def _base(stem: str) -> str:
        return stem[:-len(".texture")] if stem.endswith(".texture") else stem
    pairs = "\n".join(
        f'\t\t\t\t<df_nm path="{identity.unit_base}/{_base(stem)[:-3]}"/>'
        for stem in sorted(texture_stems) if _base(stem).endswith("_df"))
    units = [identity.tpp_unit] + ([identity.fps_unit] if with_fps else [])
    unit_lines = "\n".join(f'\t\t\t\t<unit_mat path="{u}"/>' for u in units)
    hooks = [f'\t\t<hook file="{identity.item_id}_las.lua" source_file="{HOOK_SOURCE}"/>']
    if identity.glove_adapter:
        hooks.append(f'\t\t<hook file="{identity.item_id}_glove_adapter.lua" '
                     f'source_file="{GLOVE_HOOK_SOURCE}"/>')
    hook_lines = "\n".join(hooks)
    return (
        f'<table name="{identity.display_name}" image="{identity.gui_base}/{identity.item_id}">\n'
        "\n"
        '\t<Localization directory="localization" default="english.txt"/>\n'
        "\n"
        '\t<Hooks directory="hooks">\n'
        f"{hook_lines}\n"
        "\t</Hooks>\n"
        "\n"
        '\t<AddFiles directory="assets">\n'
        "\n"
        f'\t\t\t\t<texture path="{identity.gui_base}/{identity.item_id}"/>\n'
        f"{pairs}\n"
        "\n"
        f"{unit_lines}\n"
        "\n"
        '\t\t\t\t</AddFiles>\n'
        "</table>\n"
    )


def render_material_config(identity: Identity, fps: bool,
                           slots: list[str] | None = None) -> str:
    """Guide-compliant material config for the kept body materials.

    TPP character materials use CONTOUR + unique + contour variables (wall
    outline); fps materials use the guide's DEPTH_SCALING template. Texture
    paths carry no extension. `slots` limits the declared materials to the
    ones a model actually references (the fps viewmodel has no bra).
    """
    group = identity.item_id
    if slots is None:
        slots = [slot for slot, _ in KEEP_MATERIALS.values()]
    role_of = {slot: role for slot, role in KEEP_MATERIALS.values()}

    def mat(name: str, role: str) -> str:
        if fps:
            template = ("generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:"
                        "SKINNED_3WEIGHTS")
            return (
                f'    <material name="{name}" render_template="{template}" version="2">\n'
                f'        <diffuse_texture file="{identity.unit_base}/{identity.texture_prefix}_{role}_df"/>\n'
                f'        <bump_normal_texture file="{identity.unit_base}/{identity.texture_prefix}_{role}_nm"/>\n'
                "    </material>\n"
            )
        return (
            f'    <material name="{name}" unique="true" version="2"\n'
            '              render_template="generic:CONTOUR:DIFFUSE_TEXTURE:'
            'NORMALMAP:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{identity.unit_base}/{identity.texture_prefix}_{role}_df"/>\n'
            f'        <bump_normal_texture file="{identity.unit_base}/{identity.texture_prefix}_{role}_nm"/>\n'
            '        <variable value="1 1 1" type="vector3" name="contour_color"/>\n'
            '        <variable value="0" type="scalar" name="contour_opacity"/>\n'
            "    </material>\n"
        )

    parts = [f'<materials version="3" group="{group}">\n', "\n"]
    for slot in slots:
        parts.append(mat(slot, role_of[slot]))
        parts.append("\n")
    parts.append(
        '    <material name="shadow_caster" '
        'render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n'
        "</materials>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# icon sheet (4 panels: front, side, back, iso — build_icon reads panel 3)
# ---------------------------------------------------------------------------
def render_icon_sheet(model_path: Path, out_png: Path) -> bytes:
    from PIL import Image

    mf = dm.ModelFile.read_path(model_path)
    names = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    verts_all: list[tuple] = []
    faces_all: list[tuple] = []
    colors: list[tuple] = []
    palette = {
        "mtr_body": (214, 176, 150), "mtr_c02_01": (60, 70, 110),
        "mtr_c02_02": (40, 40, 46), "mtr_c02_05": (120, 60, 70),
    }
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if md.get("version") != 3 or not md.get("atoms"):
            continue
        # pick the visible body drawable, not the shadow caster
        dname = next((n for n in names if dm.hash64(n) == md["name_hash"]), "")
        if dname != "g_body":
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
        mat_names = [bm.template_name(dm.decode_material(mf.by_id(mid).payload)["name_hash"], mf)
                     for mid in mg["material_ids"]]
        verts = geo["verts"]
        idx = topo["indices"]
        faces = [(idx[i], idx[i + 1], idx[i + 2]) for i in range(0, len(idx), 3)]
        for atom in md["atoms"]:
            mname = mat_names[atom["material_id"]] if atom["material_id"] < len(mat_names) else "?"
            if mname == "shadow_caster":
                continue
            t0 = atom["base_index"] // 3
            base = len(verts_all)
            used = sorted({v for tri in faces[t0:t0 + atom["tri_count"]] for v in tri})
            remap = {v: base + i for i, v in enumerate(used)}
            verts_all.extend(verts[v] for v in used)
            for tri in faces[t0:t0 + atom["tri_count"]]:
                faces_all.append((remap[tri[0]], remap[tri[1]], remap[tri[2]]))
                colors.append(palette.get(mname, (150, 150, 150)))
        break  # one drawable (g_body) is the whole visible outfit
    size = 640
    sheet = Image.new("RGB", (size * 4, size), (18, 18, 22))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    for i, view in enumerate(("front", "side", "back", "iso")):
        panel = out_png.parent / f"_icon_{view}.png"
        pv.render(verts_all, faces_all, colors, panel, view=view, size=size)
        sheet.paste(Image.open(panel).convert("RGB"), (i * size, 0))
        panel.unlink()
    sheet.save(out_png)
    import io
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# pack assembly
# ---------------------------------------------------------------------------
def write_pack(out_root: Path, identity: Identity, tpp_model: bytes,
               fps_model: bytes | None, textures: dict[str, bytes], icon: bytes,
               source_zip_sha: str, extra: dict,
               fps_model_slots: list[str] | None = None) -> Path:
    import shutil

    pack = Path(out_root) / identity.pack_dir_name
    if pack.exists():
        shutil.rmtree(pack)
    unit_dir = pack / "assets" / identity.unit_base
    gui_dir = pack / "assets" / identity.gui_base
    unit_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    (pack / "hooks").mkdir(exist_ok=True)
    (pack / "localization").mkdir(exist_ok=True)

    with_fps = fps_model is not None
    fps_model_slots = fps_model_slots or []
    (unit_dir / f"{identity.item_id}.model").write_bytes(tpp_model)
    (unit_dir / f"{identity.item_id}.unit").write_text(
        lop.render_unit_xml(identity.tpp_unit))
    (unit_dir / f"{identity.item_id}.object").write_text(
        lop.render_object_xml(identity.tpp_unit, lop.model_drawables(tpp_model)))
    (unit_dir / f"{identity.item_id}.material_config").write_text(
        render_material_config(identity, False))
    if with_fps:
        (unit_dir / f"fps_{identity.item_id}.model").write_bytes(fps_model)
        (unit_dir / f"fps_{identity.item_id}.unit").write_text(
            lop.render_unit_xml(identity.fps_unit))
        (unit_dir / f"fps_{identity.item_id}.object").write_text(
            lop.render_object_xml(identity.fps_unit, lop.model_drawables(fps_model)))
        (unit_dir / f"fps_{identity.item_id}.material_config").write_text(
            render_material_config(identity, True, sorted(set(fps_model_slots))))
    for stem, data in sorted(textures.items()):
        (unit_dir / stem).write_bytes(data)
    (gui_dir / f"{identity.item_id}.texture").write_bytes(icon)
    (pack / "main.xml").write_text(
        render_main_xml(identity, sorted(textures), with_fps))
    (pack / "hooks" / f"{identity.item_id}_las.lua").write_text(
        render_hook_lua(identity, with_fps))
    if identity.glove_adapter:
        (pack / "hooks" / f"{identity.item_id}_glove_adapter.lua").write_text(
            render_glove_adapter_lua(identity))
    (pack / "localization" / "english.txt").write_text(
        render_localization(identity))

    payload = {}
    for path in sorted(pack.rglob("*")):
        if path.is_file() and path.name != "BUILD_INFO.json":
            payload[path.relative_to(pack).as_posix()] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    info = {
        "pack": identity.pack_dir_name,
        "item_id": identity.item_id,
        "display_name": identity.display_name,
        "source": "references/Christie.zip (DOA5 christie_c2, body-only: face/"
                  "lashes/eyes/glasses/hair/helmet dropped)",
        "source_zip_sha256": source_zip_sha,
        "headless": True,
        "hands": "glove_adapter" if identity.glove_adapter else "authored",
        "registration": {
            "hook_source": HOOK_SOURCE,
            "table": f"LegendaryArmours.{identity.item_id}",
            "flags": list(FLAG_KEYS),
            "unit": identity.tpp_unit,
            "fps_unit": identity.fps_unit if with_fps else None,
        },
        "models_present": True,
        "fps_available": with_fps,
        "runtime_verified": True,   # base pack checked in game 2026-11-05
        "payload_sha256": payload,
    }
    info.update(extra)
    (pack / "BUILD_INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return pack


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, required=True,
                    help="directory with 2b.model / fps_2b.model (from 2b.rar)")
    ap.add_argument("--variant", choices=sorted(IDENTITIES), default="base",
                    help="base = full body with hands; "
                         f"slim = {(1 - SLIM_SCALE):.0%} thinner in x/y (arms an "
                         "extra 20%), height unchanged, hands cut at the wrist "
                         "for in-game gloves (glove adapter hook shipped)")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "pd2-las")
    ap.add_argument("--dist", type=Path, default=REPO / "dist")
    ap.add_argument("--no-fps", dest="fps", action="store_false", default=True,
                    help="ship only the third-person unit (no fps viewmodel)")
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args(argv)

    identity = IDENTITIES[args.variant]
    source_sha = hashlib.sha256(SOURCE_ZIP.read_bytes()).hexdigest()
    with zipfile.ZipFile(SOURCE_ZIP) as zf:
        model = load_christie(zf)
        textures = convert_textures(zf, identity)

    skel_map = json.loads(SKEL_MAP.read_text())
    weld_elbows(model, skel_map)

    kept = {m.material for m in model.meshes if m.material in KEEP_MATERIALS}
    dropped = sorted({m.material for m in model.meshes} - kept)
    print(f"[{identity.pack_dir_name}] source: {model.name}: {len(model.bones)} bones, "
          f"{len(model.vertices)} verts, {model.triangle_count} tris, "
          f"{len(model.meshes)} meshes")
    print(f"  kept materials: {sorted(kept)}")
    print(f"  dropped (head) materials: {dropped}")

    template = bm.load_template(args.templates / "2b.model")
    fits = bm.retarget_maps(model, skel_map, template)
    fits = fix_arm_fits(model, skel_map, template, fits)
    print(f"retarget: {len(fits)} bone transforms")

    groups: dict[str, bm.Group] = {}
    share: dict[str, str] = {}
    for gname, spec in TPP_GROUPS.items():
        g = bm.transfer_group(model, spec, skel_map, template, gname, fits=fits)
        # Widen the welded elbow blend BEFORE anything else consumes the
        # weights (straighten's medians, slim's routing, the fps extraction
        # all read g.weights). See widen_elbow_blend: without this the
        # in-game hang folds the crease into pleats.
        widened = widen_elbow_blend(g, template)
        print(f"group {gname}: {len(g.verts)} verts, {len(g.faces)} tris, "
              f"palette {len(g.palette)}, slots {sorted(set(g.mat_slots))}, "
              f"elbow blend widened on {widened} verts")
        if not g.verts:
            raise SystemExit(f"group {gname} is empty")
        groups[gname] = g
        for drawable in spec["drawables"]:
            share[drawable] = gname

    # The menu-pose retarget leaves a mid-forearm kink (the source rig is
    # straight, the PD2 forearm axis is straight — the warp comes from the
    # retarget). Straighten arm segments in bind pose for EVERY variant
    # before any slim pass, so the base pack is clean too.
    centring: list[dict] = []
    elbow_report: list[dict] = []
    for gname in ("body", "shadow"):
        straighten_segments(groups[gname], template)
        # straighten only fixes the kink it can see (its 4.5 cm radial mask
        # excludes the far-offset verts); put the tubes on the bones after it.
        centring = centre_segments(groups[gname], template) or centring
        # the arm is thickest exactly at the elbow (8.16 cm p90 over the joint
        # band against the 2B reference's 7.03); squeeze the cross-section
        # about the joint bisector so the crease does not move
        elbows = trim_elbows(groups[gname], template)
        if gname == "body":
            elbow_report = elbows
        breaks = bm.orientation_breaks(groups[gname])
        agree = bm.winding_agreement(groups[gname].verts, groups[gname].faces,
                                     groups[gname].normals)
        print(f"[{gname}] after straighten: orientation breaks {breaks}, "
              f"winding agreement {agree:.1%}")
        if breaks or agree < 0.9:
            raise SystemExit(f"[{gname}] straighten broke the mesh")

    if args.variant == "slim":
        # Thinner in width/depth only; height (z) and the skeleton untouched.
        # Applied before the fps extraction so the viewmodel arms match.
        for gname in ("body", "shadow"):
            slim_group(groups[gname], template)
            breaks = bm.orientation_breaks(groups[gname])
            agree = bm.winding_agreement(groups[gname].verts, groups[gname].faces,
                                         groups[gname].normals)
            print(f"[{gname}] after slim: orientation breaks {breaks}, "
                  f"winding agreement {agree:.1%}")
            if breaks or agree < 0.9:
                raise SystemExit(f"[{gname}] slim scale broke the mesh")

    if identity.glove_adapter:
        # Cut the hands at the wrist (both the visible mesh and the shadow),
        # then stretch the sleeve + bare-arm layers over the wrist gap so the
        # spawned glove sits inside the cuff instead of floating.
        for gname in ("body", "shadow"):
            groups[gname] = cut_hands(groups[gname])
            rep = bm.extend_sleeves_to_wrist(
                groups[gname],
                mats={"cri_body_base": -3.5, "cri_02_01_base": -4.5,
                      "cri_02_02_base": -3.0})
            print(f"[{gname}] sleeves reach the glove: {rep['moved']} verts "
                  f"{rep['materials']} (was -> target: {rep['reaches']})")
            breaks = bm.orientation_breaks(groups[gname])
            agree = bm.winding_agreement(groups[gname].verts, groups[gname].faces,
                                         groups[gname].normals)
            print(f"[{gname}] after cut: orientation breaks {breaks}, "
                  f"winding agreement {agree:.1%}")
            if breaks or agree < 0.9:
                raise SystemExit(f"[{gname}] hand cut broke the mesh")

    # Sleeve gloss: darken diffuse alpha (the specular mask) in the sleeve UV
    # regions only, every mip. In game the sleeves read glossier than the
    # torso because their normal-map phong mask is stronger there.
    texel_masks = sleeve_uv_masks(groups["body"])
    touched = retouch_sleeve_gloss(textures, groups["body"],
                                   identity.texture_prefix, texel_masks)
    print(f"sleeve gloss: attenuated alpha in {touched} blocks "
          f"(atten {SLEEVE_GLOSS_ATTEN:.2f})")

    tpp = bm.assemble_model(template, groups, share, drop_drawables=DROP_DRAWABLES)
    tpp_path = args.out / f"{identity.item_id}.model"
    tpp_path.parent.mkdir(parents=True, exist_ok=True)
    tpp_path.write_bytes(tpp.write())
    print(f"wrote {tpp_path} ({tpp_path.stat().st_size} bytes)")
    problems = bm.audit_model(tpp_path)
    if problems:
        raise SystemExit("tpp render atoms do not tile the mesh:\n  "
                         + "\n  ".join(problems))

    fit = bm.segment_fit_report(tpp_path, template)
    print(sf.format_report(f"{identity.item_id} tpp", fit, fit.get("cuffs")))

    fps_bytes = None
    fps_slots: list[str] | None = None
    fps_fit: dict | None = None
    if args.fps:
        fps_tpl = bm.load_template(args.templates / "fps_2b.model")
        fps_arms = bm.extract_bones(groups["body"], bm.is_fps_arm_bone, "arms")
        fps_shadow = bm.extract_bones(groups["shadow"], bm.is_fps_arm_bone, "shadow")
        if identity.glove_adapter:
            fps_arms = cut_hands(fps_arms)
            fps_shadow = cut_hands(fps_shadow)
        print(f"fps arms: {len(fps_arms.verts)} verts / {len(fps_arms.faces)} tris "
              f"({len(fps_shadow.verts)} shadow)")
        fps_mf = bm.assemble_model(
            fps_tpl, {"arms": fps_arms, "shadow": fps_shadow},
            {"g_body": "arms", "g_body_lod1": "arms", "s_body": "shadow"},
            drop_drawables=DROP_DRAWABLES)
        fps_path = args.out / f"fps_{identity.item_id}.model"
        fps_path.write_bytes(fps_mf.write())
        print(f"wrote {fps_path} ({fps_path.stat().st_size} bytes)")
        problems = bm.audit_model(fps_path)
        if problems:
            raise SystemExit("fps render atoms do not tile the mesh:\n  "
                             + "\n  ".join(problems))
        fps_bytes = fps_path.read_bytes()
        fps_slots = sorted(set(fps_arms.mat_slots))
        fps_fit = bm.segment_fit_report(fps_path, fps_tpl)
        print(sf.format_report(f"{identity.item_id} fps", fps_fit))

    if not args.no_previews:
        bm.preview_from_model(tpp_path, args.out / "previews", identity.item_id)

    icon_png = render_icon_sheet(tpp_path,
                                 args.out / "previews" / f"{identity.item_id}_icon_sheet.png")
    icon = lop.build_icon(icon_png)

    report = {
        "variant": args.variant,
        "source_zip": str(SOURCE_ZIP.relative_to(REPO)),
        "source_zip_sha256": source_sha,
        "model": model.name,
        "bones": len(model.bones),
        "source_vertices": len(model.vertices),
        "source_triangles": model.triangle_count,
        "kept_materials": sorted(kept),
        "dropped_head_materials": dropped,
        "tpp": {"verts": len(groups["body"].verts), "tris": len(groups["body"].faces),
                "palette": len(groups["body"].palette),
                "slots": sorted(set(groups["body"].mat_slots))},
        "headless": True,
        "glove_adapter": identity.glove_adapter,
        "drop_drawables": list(DROP_DRAWABLES),
        # mesh-vs-skeleton numbers (tools/pd2-las/segment_fit.py); the CI test
        # asserts on the same fields, so a regression shows up there too
        "centring": centring,
        "elbow_trim": elbow_report,
        "fit_tpp": fit,
        "fit_fps": fps_fit if fps_bytes is not None else None,
    }
    (args.out / f"{identity.item_id}_report.json").write_text(
        json.dumps(report, indent=2) + "\n")

    args.dist.mkdir(parents=True, exist_ok=True)
    pack = write_pack(args.dist, identity, tpp_path.read_bytes(), fps_bytes,
                      textures, icon, source_sha,
                      extra={"build_report": f"build/pd2-las/{identity.item_id}_report.json",
                             # the mesh-vs-skeleton numbers travel inside the
                             # pack so tests/test_christie_las.py can compare the
                             # build's own measurement with the shipped bytes
                             "fit_tpp": fit,
                             "fit_fps": fps_fit,
                             "centring": centring,
                             "elbow_trim": elbow_report},
                      fps_model_slots=fps_slots)
    print(f"pack  -> {pack}")
    zipped = lop.zip_pack(pack)
    zipped = Path(zipped)
    digest = hashlib.sha256(zipped.read_bytes()).hexdigest()
    (args.dist / f"{zipped.name}.sha256").write_text(f"{digest}  dist/{zipped.name}\n")
    print(f"zip   -> {zipped}")
    print(f"sha256 -> {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
