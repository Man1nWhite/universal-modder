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

Usage (from the repo root; run `bash tools/pd2-las/recover_env.sh` once for
the .venv and the 2B templates that `--templates` defaults to):
  .venv/bin/python tools/pd2-las/build_christie_las.py                  # base
  .venv/bin/python tools/pd2-las/build_christie_las.py --variant slim   # slim

Both write the tracked zips in `dist/`; add `--out DIR --dist DIR` to build
somewhere else and leave them alone.
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
import determinism  # noqa: E402
import diesel_model as dm  # noqa: E402
import dds_encode as dds  # noqa: E402
import segment_fit as sf  # noqa: E402
import las_outfit_pack as lop  # noqa: E402
import preview as pv  # noqa: E402
import source_model as sm  # noqa: E402
from dds_encode import (  # noqa: E402
    attenuate_dxt5_alpha_from_normal,
    swizzle_standard_normal_dxt5_to_pd2,
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

HOOK_SOURCE = lop.HOOK_SOURCE

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
FLAG_KEYS = lop.BODY_ONLY

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
    wrong in game). Mip 0 is preserved losslessly (canonicalised to c0 >= c1
    endpoint order); mips 1..n are box-filtered from a Pillow decode of mip 0
    so the authored RGB blocks reach the engine bit-identical. `pack_dds`
    writes the vanilla header shape (flags 0x000A1007, caps 0x00401008).
    """
    import io

    import numpy as np
    from PIL import Image

    size, _mips, mip0 = pd2_dds.dds_mip0_slice(dds_mip0)
    mip0_fixed, _ = pd2_dds.fix_misordered_blocks(bytes(mip0), size)
    if size == 1:
        return pd2_dds.pack_dds([mip0_fixed], size)
    im = Image.open(io.BytesIO(dds_mip0))
    im.load()
    rgba = np.asarray(im.convert("RGBA"), dtype=np.uint8)
    payloads = [mip0_fixed] + pd2_dds._submip_payloads_from_image(rgba)
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
        nm_dds = swizzle_standard_normal_dxt5_to_pd2(raw_nm, invert_y=True)
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
SLEEVE_FEATHER_TEXELS = 3.0  # edge feather of the sleeve footprint (mip0 texels)
MAX_SLEEVE_TRI_UV_SPAN = 0.12  # seam-stitch bridges jump islands; skip them


def uv_to_texel_frac(uv):
    """Stored Diesel ``.model`` ``uv0`` -> top-down ``[0, 1)`` texel fractions.

    ``build_models.transfer_group`` authored ``(u_src, 1.0 - v_src)`` where
    ``v_src = 0`` is image row 0, so under D3D9 ``Wrap`` the GPU samples
    ``(mod(u, 1), mod(-v, 1))`` for every UDIM tile, negative ``v`` included.
    """
    import numpy as np

    arr = np.asarray(uv, dtype=np.float64)
    out = np.empty_like(arr, dtype=np.float64)
    out[..., 0] = np.mod(arr[..., 0], 1.0)
    out[..., 1] = np.mod(-arr[..., 1], 1.0)
    return out


def sleeve_uv_mask(uvs, faces, *, work: int = 1024, feather_texels: float = 3.0,
                   max_uv_span: float = MAX_SLEEVE_TRI_UV_SPAN):
    """Texel coverage of a set of UV triangles (the sleeve's own islands).

    Rasterising the *faces* rather than splatting a disc around each vertex is
    what keeps the sleeve gloss mask off the rest of the suit: the mask is then
    exactly the UV footprint of the sleeve, so a texel that belongs to the
    trousers or the shoes cannot pick it up no matter how close the islands sit
    in the atlas. The blur is applied **inside** that footprint only (the
    blurred mask is clipped to the unblurred one), so the feather softens the
    edge of the change without ever reaching a texel the sleeve does not own.

    Each triangle is unwrapped as a unit -- ``u - floor(mean(u))`` and
    ``row - floor(mean(row))`` with ``row = mod(-v, 1)`` -- so a triangle that
    straddles an integer tile boundary is never torn across the canvas, and the
    positive-``v`` atlas (``c02_05``, stored ``v in [0.043, 0.980]``) lands
    inside the canvas instead of at ``y ~ 1.04 * work``. Triangles spanning more
    than ``max_uv_span`` on either axis are skipped: those are the seam-stitch
    bridges, whose UVs jump between two islands and would otherwise streak
    across unrelated texels.
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    im = Image.new("L", (work, work), 0)
    pen = ImageDraw.Draw(im)
    if faces:
        uv_arr = np.asarray(uvs, dtype=np.float64)
        frac = uv_to_texel_frac(uv_arr)
        for a, b, c in faces:
            tri = frac[[int(a), int(b), int(c)]]
            if float(np.ptp(tri, axis=0).max()) > max_uv_span:
                continue
            pts = [((float(u) - np.floor(tri[:, 0].mean())) * work,
                    (float(v) - np.floor(tri[:, 1].mean())) * work)
                   for u, v in tri]
            pen.polygon(pts, fill=255)
    hard = np.asarray(im, dtype=np.float64) / 255.0
    if feather_texels > 0 and faces:
        soft = np.asarray(im.filter(ImageFilter.GaussianBlur(feather_texels)),
                          dtype=np.float64) / 255.0
        return np.where(hard > 0.0, soft, 0.0)
    return hard


def sleeve_uv_masks(group: bm.Group) -> dict:
    """Per-material-role texel masks (1024x1024 working res) of sleeve UV regions.

    A face counts as sleeve when the *mean* arm-chain share (Arm/ForeArm/Hand/
    fingers) of its three vertices is above ``SLEEVE_BONE_SHARE``; only those
    faces are rasterised into the role's canvas. The sleeve and the trousers
    share material `c02_01`, which is exactly why the mask has to be limited to
    the faces the arm chain actually drives.
    """
    import numpy as np

    armish = {n for n in group.palette
              if n.endswith("Arm") or n.endswith("ForeArm")
              or n.endswith("Hand") or "Finger" in n}
    share = np.array([sum(w for pi, w in infl if group.palette[pi] in armish)
                      for infl in group.weights])
    face_role: list[str] = []
    for src_mat, _bv, _base_i, tris, _nv in group.slices:
        face_role.extend([KEEP_MATERIALS[src_mat][1]] * tris)
    if len(face_role) != len(group.faces):
        raise SystemExit(
            f"sleeve_uv_masks: {len(face_role)} slice faces against "
            f"{len(group.faces)} triangles")
    out: dict = {}
    roles = sorted(set(face_role))
    for role in roles:
        sel = [(group.faces[f], face_role[f]) for f in range(len(group.faces))
               if face_role[f] == role
               and float(share[list(group.faces[f])].mean()) > SLEEVE_BONE_SHARE]
        if not sel:
            out[role] = np.zeros((1024, 1024), dtype=np.float64)
            continue
        out[role] = sleeve_uv_mask(group.uvs, [faces for faces, _r in sel],
                                   feather_texels=SLEEVE_FEATHER_TEXELS)
    return out


def retouch_sleeve_gloss(textures: dict[str, bytes], group: bm.Group,
                         texture_prefix: str, texel_masks: dict) -> int:
    """Darken diffuse alpha (gloss) inside the sleeve UV regions.

    Only **mip 0** is attenuated, block by block, and the rest of the pyramid is
    regenerated from the attenuated mip 0. Attenuating every level separately
    (the 2026-11-06 shape of this pass) quantises the mask edge to whatever the
    block grid is at that level — ~0.7 cm per block at mip 0 on the suit but
    ~5 cm at mip 3 — which is the stair-stepped sheen patch the screenshots
    show on the trousers. Regenerating instead means the coarse mips inherit a
    *filtered* version of the same mask, so the only edge in the texture is the
    one drawn at full resolution.

    Returns the number of mip-0 blocks touched.
    """
    import numpy as np
    from PIL import Image

    total = 0
    for _src_mat, (_slot, role) in KEEP_MATERIALS.items():
        key = f"{texture_prefix}_{role}_df.texture"
        if key not in textures:
            continue
        payload = bytearray(textures[key])
        size, _mips, mip0 = pd2_dds.dds_mip0_slice(bytes(payload))
        blocks = max(1, size // 4)
        # mip0 texel mask -> one value per 4x4 block
        im = Image.fromarray((np.clip(texel_masks[role], 0, 1) * 255).astype(np.uint8))
        im = im.resize((size, size), Image.BILINEAR)
        block_mask = (np.asarray(im, dtype=np.float64) / 255.0)[:blocks * 4, :blocks * 4] \
            .reshape(blocks, 4, blocks, 4).mean(axis=(1, 3))
        flat = block_mask.reshape(-1)
        role_touched = int((flat > 0.004).sum())
        # Roles whose sleeve mask touches no blocks are left byte-identical:
        # skip the decode/re-encode entirely (e.g. body_df and c02_05_df).
        if role_touched == 0:
            continue
        mip0 = bytearray(mip0)
        for bi in np.where(flat > 0.004)[0]:
            fac = 1.0 - SLEEVE_GLOSS_ATTEN * float(flat[bi])
            blk = np.frombuffer(bytes(mip0[16 * bi:16 * bi + 8]), dtype=np.uint8)
            alpha = dds._dxt5_alpha_decode(blk) * fac
            mip0[16 * bi: 16 * bi + 8] = dds._dxt5_alpha_encode(alpha)
        total += role_touched
        # mip-0 alpha blocks are attenuated in place (RGB bytes 8..16 stay
        # bit-identical to the VTF); mips 1..n are regenerated from mip 0.
        textures[key] = pd2_dds.pack_dds(
            pd2_dds.mip_payloads_from_mip0(bytes(mip0), size), size
        )
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
    out.rest_worlds = dict(g.rest_worlds) if g.rest_worlds else None
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


def drop_bare_arm_rings(g: bm.Group, mats=("cri_body_base",), x_gate: float = 33.0) -> bm.Group:
    """Delete the bare-arm skin ring cut_hands leaves around the wrist.

    The adapter pack's contract is *no arm skin visible*: the vanilla
    ``hnd_forearms`` adapter supplies the forearm. ``cut_hands`` removes the
    hand geometry but leaves the source's bare-arm ring tagged as skin
    (``cri_body_base``), which then pokes out of the sleeve as a tan flap
    (§3.2 of the arm-skin-stub plan). ``extend_sleeves_to_wrist`` cannot reach
    that ring - its joint table is authored for the pre-rebind rest pose - so
    instead of stretching it we drop it.

    Only faces whose slice material is in ``mats`` (the skin slices) and whose
    centroid lies beyond ``x_gate`` in |x| (the arm region) are removed; torso
    skin (|x| <= x_gate) and every garment slice are untouched.

    Returns a new Group with the ring faces removed, vertices compacted and
    slices re-laid so each slice's faces stay contiguous - the same shape
    ``cut_hands`` produces.
    """
    # Map each face index -> slice index.
    face_to_slice = {}
    for si, (_mat, _bv, base_i, tris, _nv) in enumerate(g.slices):
        for f in range(base_i // 3, base_i // 3 + tris):
            face_to_slice[f] = si

    kept: list[tuple[int, tuple[int, int, int]]] = []
    dropped = 0
    for f, tri in enumerate(g.faces):
        si = face_to_slice.get(f)
        if si is None or g.slices[si][0] not in mats:
            kept.append((si, tri))
            continue
        cen_x = sum(g.verts[v][0] for v in tri) / 3.0
        if abs(cen_x) > x_gate:
            dropped += 1
            continue
        kept.append((si, tri))

    if dropped == 0:
        return g

    # Rebuild per slice (disjoint vertex blocks, contiguous face runs), in
    # ascending slice order, compacting to the verts each kept face references.
    out = bm.Group(name=g.name)
    out.palette = list(g.palette)
    out.rest_worlds = dict(g.rest_worlds) if g.rest_worlds else None
    cursor = 0
    for si in sorted({si for si, _ in kept}):
        tris = [tri for s, tri in kept if s == si]
        mat = g.slices[si][0]
        used: list[int] = []
        seen: dict[int, int] = {}
        local_faces = []
        for tri in tris:
            row = []
            for v in tri:
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
        out.slices.append((mat, base_v, cursor * 3, len(local_faces), len(used)))
        out.mat_slots.append(g.mat_slots[si])
        out.faces.extend((a + base_v, b + base_v, c + base_v)
                         for a, b, c in local_faces)
        cursor += len(local_faces)

    print(f"[{g.name}] bare-arm ring: {dropped} skin faces dropped, "
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
# either side of the elbow pivot on the TARGET arm (23.3 cm). A monotone
# material coordinate (see the function) keeps the re-split continuous across
# the crease; the width is a measured trade between crumple and rubber.
#
# Sweep on the flexion axis, base pack with the outer-elbow trim in place
# (worst edge in the +-12 cm elbow window at the in-game idle = 12 deg;
# "rubber" = displacement vs a rigid skin 8+ cm down the forearm):
#
#   ramp    min ratio  worst shortening   rubber    first cut 2026-11-06
#   4+3      0.249        2.88 cm         0.06      (weld, pre-widen)
#   7+9      0.295        2.08 cm         0.07      2026-11-06 .. 11-07
#   9+10     0.333        1.83 cm         0.24      ** current **
#   10+12    0.408        1.69 cm         0.76
#   12+12    0.400        1.55 cm         0.65
#
# 9+10 is the last ramp that is effectively rigid away from the joint; past it
# the forearm starts to bend like rubber (10+12 drags a vertex 0.76 cm at
# 16 cm from the elbow, which is visible as a soft wrist). No ramp restores a
# crisp crease - the fold amplitude is r*dtheta of geometry, not weights - so
# the elbow is de-puffed geometrically below (ELBOW_OUTER_TRIM) instead.
ELBOW_WIDEN_A_CM = 9.0    # proximal (upper-arm) reach
ELBOW_WIDEN_B_CM = 10.0   # distal (forearm) reach

#: Cuff taper (2026-11-07). The sleeve mouth flares to ~5.1 cm median / 6.2 cm
#: p90 radius at the wrist against a ~4.4 cm forearm and PD2's 2B body, whose
#: sleeve *narrows* to 2.4-2.7 cm there - in game the cuff reads as a cone, and
#: it is the widest thing on the arm (see docs/pd2-las/CHRISTIE.md). A smooth
#: radial taper over the last 9 cm of the forearm pulls it in without touching
#: the mouth's axial position (the glove still spawns at the Hand pivot) and
#: without shrinking Christie's own hand: hand-weighted verts are held still,
#: and the taper stops short of the hand surface by CUFF_HAND_CLEAR_CM.
CUFF_TAPER = 0.28        # radial scale removed at the mouth (1 - k)
CUFF_TAPER_CM = 9.0      # axial window, measured back from the wrist
CUFF_FLOOR_CM = 3.0      # never narrower than this (room for the in-game glove)
CUFF_HAND_CLEAR_CM = 0.5  # keep this much air between sleeve and hand surface
CUFF_INNER_CM = 4.0      # verts deeper than this are the cuff's hidden lining

# slim bicep tuck: extra radial reduction of the upper-arm belly, on top of
# the segment scale (0.80). A smooth bump over the middle 45% of the Arm
# segment; the shoulder and the protected elbow crease are untouched.
BICEP_TUCK = 0.10
BICEP_BAND = (0.28, 0.72)   # normalized t/L where the bump rises and falls


def _diffuse(faces, values, iterations: int, lam: float = 0.5):
    """Diffuse a per-vertex scalar field over the mesh graph.

    ``values`` is smoothed with ``x <- (1-lam) x + lam * mean(neighbours)``
    ``iterations`` times, so a discontinuity in the input (a weight class
    boundary, a layer seam) becomes a ramp a few edges wide. Used by
    ``taper_cuff`` to keep the sleeve->hand transition from tearing bridge
    triangles.
    """
    import numpy as np

    tri = np.asarray(faces, dtype=np.int64)
    if tri.ndim != 2 or tri.shape[1] != 3:
        return values
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    n = len(values)
    deg = np.bincount(e[:, 0], minlength=n).astype(np.float64)
    deg[deg == 0.0] = 1.0
    x = np.asarray(values, dtype=np.float64).copy()
    for _ in range(iterations):
        acc = np.bincount(e[:, 0], weights=x[e[:, 1]], minlength=n)
        x = (1.0 - lam) * x + lam * (acc / deg)
    return x


def _damp_flips(faces, verts, disp, passes: int = 24, shrink: float = 0.5):
    """Shrink the displacement of inverting slivers until none invert.

    ``disp`` is a per-vertex offset; the loop halves the offset of the
    largest-moving vertex of every triangle whose normal would reverse, and is
    a no-op when nothing inverts. Returns the corrected offsets.
    """
    import numpy as np

    tri = np.asarray(faces, dtype=np.int64)
    d = np.array(disp, dtype=np.float64, copy=True)
    mag = np.linalg.norm(d, axis=1)
    if tri.ndim != 2 or tri.shape[1] != 3 or not (mag > 1e-9).any():
        return d
    for _ in range(passes):
        p = verts + d
        n0 = np.cross(verts[tri[:, 1]] - verts[tri[:, 0]],
                      verts[tri[:, 2]] - verts[tri[:, 0]])
        n1 = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
        bad = np.einsum("ij,ij->i", n0, n1) <= 0.
        bad &= mag[tri].max(axis=1) > 1e-6
        if not bad.any():
            break
        for row in np.where(bad)[0]:
            idx = tri[row]
            i = int(idx[np.argmax(mag[idx])])
            d[i] *= shrink
            mag[i] *= shrink
    return d


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


#: De-spike (2026-11-10). The retargeted elbow keeps a handful of vertices
#: that stand 1.3-2.2 cm proud of the ring they belong to, and they sit on the
#: *crease* side of the joint - the front of the arm - so at 45-50 degrees of
#: flexion they read as a beak on the inner elbow in the material-isolated
#: review sheets. They are authored geometry, not a bake error: the pose only
#: transforms them, and every earlier pass misses them because
#: ``straighten_segments``/``centre_segments`` mask at 4.5 cm radius and
#: ``trim_elbows`` scales whatever survives uniformly.
#:
#: This pass runs *after* ``rebind_arms_at_idle`` - the shipped geometry is the
#: idle pose - so the elbow chain is already at its 12-degree rest and a vertex
#: is judged in the pose the game displays. It is not a smoother: a vertex only
#: moves when it beats the median radius of its own one-ring by
#: ``ELBOW_SPIKE_CM``, and it moves radially, onto that median, so it keeps its
#: direction, UVs, weights and the ring's topology. The move is tested against
#: the vertex's own triangle fan and backed off until nothing inverts.
ELBOW_SPIKE_CM = 0.75        # own radius minus neighbour median that is a spike
ELBOW_SPIKE_MAX_CM = 3.0     # refuse (and report) a correction larger than this
ELBOW_SPIKE_WINDOW_CM = 11.0  # only vertices this close to the arm chain
ELBOW_SPIKE_JOINT_CM = 9.0   # ... and this close to the elbow joint along the chain


def _chain_param_world(verts, chain):
    """Arc length along `chain` and distance to it, for every vertex."""
    import numpy as np

    best = np.full(len(verts), np.inf)
    arc = np.zeros(len(verts))
    acc = 0.0
    for a, b in zip(chain[:-1], chain[1:]):
        ab = b - a
        length = float(np.linalg.norm(ab))
        u = ab / max(length, 1e-12)
        t = np.clip((verts - a) @ u, 0.0, length)
        d = np.linalg.norm(verts - (a + np.outer(t, u)), axis=1)
        better = d < best
        best = np.where(better, d, best)
        arc = np.where(better, t + acc, arc)
        acc += length
    return arc, best


def despike_elbows(g: bm.Group, template: bm.Template,
                   bones=(("LeftArm", "LeftForeArm", "LeftHand"),
                          ("RightArm", "RightForeArm", "RightHand"))) -> list[dict]:
    """Pull authored elbow spikes back onto the ring they belong to.

    Runs on the shipped (idle-rest) geometry, so ``g.rest_worlds`` gives the
    joint positions. Each flagged vertex keeps its direction about the arm
    chain and moves to the median radius of its one-ring neighbours; the move
    is reduced (never below 25 %) until none of its own triangles flips. There
    is no topology, UV or weight change, and the build still gates on
    ``_check_flips``.
    """
    import numpy as np

    if not g.verts or not g.rest_worlds:
        return []
    v = np.array(g.verts, dtype=np.float64)
    n_old = np.array(g.normals, dtype=np.float64)
    faces = np.array(g.faces, dtype=np.int64)
    # outer blazer only: the sleeve is the surface being reviewed
    # the caster shares the body's triangles with a single ``shadow_caster``
    # slot, so it takes the same selection instead of the material test
    if "shadow_caster" in g.mat_slots:
        outer = np.ones(len(faces), dtype=bool)
    else:
        outer = np.zeros(len(faces), dtype=bool)
        for (_src, _bv, base_i, tris, _nv), slot in zip(g.slices, g.mat_slots):
            if slot == "mtr_c02_01":
                first = base_i // 3
                outer[first:first + tris] = True
    adj: dict[int, set[int]] = {}
    for f in faces[outer]:
        for i, j in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            adj.setdefault(int(i), set()).add(int(j))
            adj.setdefault(int(j), set()).add(int(i))
    of_vert: dict[int, list[int]] = {}
    for fi in np.where(outer)[0]:
        for i in faces[fi]:
            of_vert.setdefault(int(i), []).append(int(fi))
    n0 = np.cross(v[faces[:, 1]] - v[faces[:, 0]], v[faces[:, 2]] - v[faces[:, 0]])
    a0 = np.linalg.norm(n0, axis=1)
    new = v.copy()
    records: list[dict] = []
    for parent, child, hand in bones:
        if any(n not in g.rest_worlds for n in (parent, child, hand)):
            continue
        chain = [np.asarray(g.rest_worlds[n], float).reshape(4, 4)[3, :3]
                 for n in (parent, child, hand)]
        arc, radius = _chain_param_world(v, chain)
        s_joint = float(np.linalg.norm(chain[1] - chain[0]))
        near = (radius <= ELBOW_SPIKE_WINDOW_CM) & (np.abs(arc - s_joint) <= ELBOW_SPIKE_JOINT_CM)
        field = np.where(near, radius, np.inf)
        cand = [int(i) for i in np.where(near)[0] if adj.get(int(i))]
        moved = 0
        limited = 0
        refused = 0
        biggest = 0.0
        touched: set[int] = set()
        for i in cand:
            nbrs = [j for j in adj.get(i, ()) if np.isfinite(field[j])]
            if len(nbrs) < 3:
                continue
            target = float(np.median(radius[nbrs]))
            excess = radius[i] - target
            if excess <= ELBOW_SPIKE_CM:
                continue
            if excess > ELBOW_SPIKE_MAX_CM:
                p = v[i]
                raise SystemExit(
                    f"despike {child}: vertex {i} at ({p[0]:.1f}, {p[1]:.1f}, "
                    f"{p[2]:.1f}) cm stands {excess:.2f} cm off its ring "
                    f"(limit {ELBOW_SPIKE_MAX_CM}); inspect it before raising "
                    f"the limit")
            best = None
            for a, b in zip(chain[:-1], chain[1:]):
                ab = b - a
                t = np.clip((v[i] - a) @ ab / max(float(ab @ ab), 1e-12), 0.0, 1.0)
                p = a + t * ab
                d = float(np.linalg.norm(v[i] - p))
                if best is None or d < best[0]:
                    best = (d, p)
            d, p = best
            if d < 1e-6:
                continue
            unit = (v[i] - p) / d
            for frac in (1.0, 0.75, 0.5, 0.35, 0.25):
                trial = new.copy()
                trial[i] = p + unit * (d + (target - d) * frac)
                ok = True
                for fi in of_vert.get(i, ()):
                    a, b, c = faces[fi]
                    tn = np.cross(trial[b] - trial[a], trial[c] - trial[a])
                    if (float(tn @ n0[fi]) <= 0.0
                            or float(np.linalg.norm(tn)) < 0.25 * a0[fi]):
                        ok = False
                        break
                if ok:
                    new = trial
                    moved += 1
                    touched.add(i)
                    if frac < 1.0:
                        limited += 1
                    biggest = max(biggest, float(np.linalg.norm(new[i] - v[i])))
                    break
            else:
                refused += 1
        if moved or refused:
            records.append({"joint": child, "verts": moved,
                            "partial": limited, "refused": refused,
                            "max_shift_cm": round(biggest, 2)})
            print(f"  de-spike {child}: {moved} verts pulled back onto their "
                  f"ring about the arm chain ({limited} only part way, "
                  f"{refused} refused as wedge vertices), largest shift "
                  f"{biggest:.2f} cm; ids {sorted(touched)[:30]}")
    if not records:
        return records
    g.verts = [tuple(row) for row in new]
    _check_flips(g, v, f"elbow de-spike {g.name}")
    _recompute_normals(g, n_old)
    return records


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


# Author the arm skinning rest pose where the heister actually idles. The old
# rest bind baked a 72-degree elbow and required a 60-degree correction before
# the first visible frame; every local corrective then had to repair that
# extreme deformation. A 12-degree rest elbow needs no idle corrective at all.
IDLE_ELBOW_STRAIGHTEN = 60.0
IDLE_WRIST_STRAIGHTEN = -8.0
IDLE_REST_TAUBIN_PASSES = 8

# Bounded multi-pose fold solves for the slim sleeve after coverage repair.
# Each vertex is limited to +/-0.30 cm per axis. The objective checks adjacent
# face normals at 72/50/27/22/12/0 degrees, with coincident UV/material vertices
# welded. Left and right are independent solutions; nearest-position mirroring
# was explicitly rejected because the two corrected rest surfaces differ.
SLIM_FOLD_DELTAS = {
    "Left": {
        1953: (.1227, -.1101, -.0015), 1954: (.0730, .0396, -.0203),
        1945: (-.0421, .0748, .0379), 1944: (-.1599, -.0785, -.0259),
        1959: (.1299, .0793, .1692), 1964: (.0410, .1344, -.1317),
        1965: (.3000, .1252, .3000), 1955: (-.2966, -.2408, -.2472),
        1966: (.0336, .3000, -.3000), 1956: (-.0034, -.0138, .0094),
        1974: (-.3000, -.3000, .3000), 1984: (-.3000, -.3000, .3000),
        1985: (.3000, .2411, -.3000),
    },
    "Right": {
        1356: (.0100, -.2690, -.1637), 1359: (.0200, .0009, .0153),
        1358: (-.1057, .0568, -.0759), 1370: (.0521, -.0876, .2840),
        1368: (.3000, -.3000, .3000), 1371: (.1628, .0859, -.2471),
        1372: (-.2312, .3000, .1925), 1367: (-.0135, -.0482, -.0150),
        1376: (-.2383, .2435, .1419), 1373: (-.0294, .3000, .2750),
        1375: (.3000, -.2713, -.3000), 1374: (-.3000, -.3000, .3000),
        1369: (.2889, -.3000, .0462), 1378: (-.1339, .1435, -.1363),
        1377: (-.2163, .3000, -.1002),
    },
}


def idle_arm_rest_worlds(template: bm.Template) -> dict:
    """Absolute PD2 worlds for the near-idle authoring pose."""
    import render_mesh_skeleton as rms

    pose = {f"{side}Arm": (2, 22) for side in ("Left", "Right")}
    pose.update({f"{side}ForeArm": (rms.BEND_AXIS, -IDLE_ELBOW_STRAIGHTEN)
                 for side in ("Left", "Right")})
    pose.update({f"{side}Hand": (rms.BEND_AXIS, IDLE_WRIST_STRAIGHTEN)
                 for side in ("Left", "Right")})
    return rms.posed_worlds(template, pose)


def _coincident_groups(verts) -> list[list[int]]:
    """UV/material duplicate indices sharing an authored position."""
    import numpy as np

    groups = {}
    for i, point in enumerate(np.asarray(verts, float)):
        groups.setdefault(tuple(np.round(point, 4)), []).append(i)
    return [ids for ids in groups.values() if len(ids) > 1]


def _weld_positions(verts, groups) -> None:
    for ids in groups:
        verts[ids] = verts[ids].mean(axis=0)


def _elbow_coverage_correction(g: bm.Group, template: bm.Template) -> dict:
    """Extend the existing near sleeve boundary where posed coverage opens.

    The 50-degree side view exposed a real gap beyond the outer sleeve's posed
    vertex boundary; widening the camera depth only hid it with far-side body
    faces. For each small enclosed background component, extend the nearest
    existing boundary vertex just past that component. Convert the posed +Y
    displacement through the inverse of that vertex's linear-blend matrix and
    store it in the authored rest mesh. UV/material duplicates receive exactly
    the same delta. No faces, vertices, weights, UVs or materials are added.

    Repeat at the near-idle and intermediate review angles, then recheck 50
    degrees. The right arm is evaluated in a mirrored side camera, so both arms
    get the same near-shell treatment. The depth band remains tight throughout.
    """
    import contextlib
    import io
    import tempfile
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    import diesel_model as dm
    import render_mesh_skeleton as rms
    from elbow_before_after import pose_for, window_for

    if not g.verts:
        return {"vertices": 0, "max_shift_cm": 0.0}
    blendindices = [[pi for pi, _w in row] for row in g.weights]
    blendweights = [[w for _pi, w in row] for row in g.weights]
    rotations = [dm.mat_inv(g.rest_worlds[name]) for name in g.palette]
    skel = {"objects": [template.name_id[name] for name in g.palette],
            "rotations": rotations}
    outer_faces = []
    for (_src, _bv, base_i, tris, _nv), slot in zip(g.slices, g.mat_slots):
        if slot in ("mtr_c02_01", "shadow_caster"):
            first = base_i // 3
            outer_faces.extend(g.faces[first:first + tris])
    outer_faces = np.asarray(outer_faces, dtype=np.int64)
    start = np.asarray(g.verts, dtype=np.float64)
    groups = _coincident_groups(start)
    moved = set()
    remaining = []

    def enclosed(path: Path, minimum: int = 100):
        pixels = np.asarray(Image.open(path).convert("RGB"))
        dark = pixels.max(axis=2) < 45
        dark[:70] = False  # intentional renderer legend
        labels, _count = ndimage.label(dark)
        border = set(np.unique(np.concatenate(
            [labels[0], labels[-1], labels[:, 0], labels[:, -1]])).tolist())
        result = []
        for index in np.unique(labels):
            if not index or index in border:
                continue
            mask = labels == index
            area = int(mask.sum())
            if area <= minimum:
                continue
            ys, xs = np.where(mask)
            result.append((area, (int(xs.min()), int(ys.min()),
                                  int(xs.max()), int(ys.max())), mask))
        return result

    with (tempfile.TemporaryDirectory(prefix="christie-elbow-coverage-") as tmp,
          contextlib.redirect_stdout(io.StringIO())):
        image_path = Path(tmp) / "near_shell.png"
        for side in ("Left", "Right"):
            for straighten in (22.0, 60.0, 45.0, 0.0, 22.0):
                worlds, bones = pose_for(template, -straighten)
                geo = {"verts": g.verts, "faces": g.faces,
                       "blendindices": blendindices, "blendweights": blendweights}
                posed = rms.skin_verts(geo, skel, worlds)
                view_posed = posed.copy()
                pivot = np.array(
                    worlds[template.name_id[f"{side}ForeArm"]][12:15], float)
                if side == "Right":
                    view_posed[:, 0] *= -1.0
                    pivot[0] *= -1.0
                near_distance = np.linalg.norm(view_posed - pivot, axis=1)
                if not (near_distance <= 6.5).any():
                    raise RuntimeError(f"coverage framing {g.name} {side} {straighten}: "
                                       f"min {near_distance.min()} pivot {pivot} "
                                       f"bounds {view_posed.min(axis=0)} {view_posed.max(axis=0)}")
                window, _ = window_for([view_posed], pivot, "side", 6.5)
                depth = float(rms.depth_towards_camera(
                    "side", np.atleast_2d(pivot))[0])
                outer = {"verts": view_posed, "faces": outer_faces}
                rms.render(outer, bones, "side", image_path, zoom=window,
                           depth=(depth - 9.0, depth + 9.0))
                holes = enclosed(image_path)
                if straighten == 22.0 and not holes:
                    continue

                u0, u1, v0, v1 = window
                scale = min(940.0 / (u1 - u0), 940.0 / (v1 - v0))
                offset = np.array([30.0 - u0 * scale, 30.0 + v1 * scale])
                uv = rms.project(view_posed, "side")
                screen = np.column_stack(
                    [uv[:, 0] * scale + offset[0], -uv[:, 1] * scale + offset[1]])
                face_depth = rms.depth_towards_camera(
                    "side", view_posed[outer_faces].mean(axis=1)) - depth
                candidates = np.unique(outer_faces[np.abs(face_depth) < 9.0])
                # Keep the repair at the elbow, not the mid-bicep proportion
                # slices. A farther boundary vertex is not required: the near
                # one can extend across the same exposed component.
                candidates = candidates[
                    np.linalg.norm(view_posed[candidates] - pivot, axis=1) <= 8.0]

                # Row-vector LBS: rest_delta @ A = posed_delta.
                matrices = np.zeros((len(posed), 3, 3))
                for i, weights in enumerate(g.weights):
                    for pi, weight in weights:
                        if weight <= 0.0:
                            continue
                        inv_bind = np.asarray(rotations[pi], float).reshape(4, 4)[:3, :3]
                        pose = np.asarray(
                            worlds[template.name_id[g.palette[pi]]],
                            float).reshape(4, 4)[:3, :3]
                        matrices[i] += weight * (inv_bind @ pose)

                desired = np.zeros_like(posed)
                selected = {}
                for area, (x0, y0, x1, y1), mask in holes:
                    for lo in range(y0, y1 + 1, 60):
                        hi = min(lo + 60, y1 + 1)
                        row = mask[lo:hi]
                        if not row.any():
                            continue
                        target = int(np.where(row)[1].max()) + 60
                        nearby = candidates[
                            (screen[candidates, 1] >= lo - 30)
                            & (screen[candidates, 1] <= hi + 30)
                            & (screen[candidates, 0] < x0 + 10)
                            & (screen[candidates, 0] > x0 - 180)]
                        if not len(nearby):
                            continue
                        best = int(nearby[np.argmax(screen[nearby, 0])])
                        selected[best] = max(selected.get(best, target), target)
                for index, target in selected.items():
                    dy = float(np.clip((target - screen[index, 0]) / scale, 0.0, 8.0))
                    desired[index] = np.linalg.solve(
                        matrices[index].T, np.array([0.0, dy, 0.0]))
                updated = np.asarray(g.verts, dtype=np.float64)
                for index in selected:
                    for ids in groups:
                        if index in ids:
                            desired[ids] = desired[index]
                            break
                updated += desired
                g.verts = [tuple(map(float, row)) for row in updated]
                moved.update(selected)

        # A boundary extension must not invert its adjacent rest triangles.
        # Damp only the offending movers and re-weld duplicated UV/material
        # vertices after every pass, then validate the posed coverage below.
        faces = np.asarray(g.faces, dtype=np.int64)
        displacement = np.asarray(g.verts, float) - start
        for _ in range(4):
            displacement = _damp_flips(faces, start, displacement, passes=48)
            for ids in groups:
                displacement[ids] = displacement[ids].mean(axis=0)
        g.verts = [tuple(map(float, row)) for row in start + displacement]

        # The final 50-degree pass above must leave no enclosed near-shell gap.
        worlds, bones = pose_for(template, -22.0)
        for side in ("Left", "Right"):
            geo = {"verts": g.verts, "faces": g.faces,
                   "blendindices": blendindices, "blendweights": blendweights}
            posed = rms.skin_verts(geo, skel, worlds)
            pivot = np.array(worlds[template.name_id[f"{side}ForeArm"]][12:15], float)
            if side == "Right":
                posed[:, 0] *= -1.0
                pivot[0] *= -1.0
            window, _ = window_for([posed], pivot, "side", 6.5)
            depth = float(rms.depth_towards_camera("side", np.atleast_2d(pivot))[0])
            rms.render({"verts": posed, "faces": outer_faces}, bones, "side",
                       image_path, zoom=window, depth=(depth - 9.0, depth + 9.0))
            remaining.extend((side, area, bounds)
                             for area, bounds, _mask in enclosed(image_path, 500))
    if remaining:
        raise SystemExit(f"idle elbow coverage {g.name}: remaining gaps {remaining}")
    shift = np.linalg.norm(np.asarray(g.verts, float) - start, axis=1)
    return {"vertices": len(moved), "max_shift_cm": round(float(shift.max()), 5)}


def _apply_slim_fold_solution(g: bm.Group) -> dict:
    """Apply the independently solved, seam-welded slim fold corrections."""
    import numpy as np

    start = np.asarray(g.verts, dtype=np.float64)
    updated = start.copy()
    groups = _coincident_groups(start)
    for side, deltas in SLIM_FOLD_DELTAS.items():
        for index, delta in deltas.items():
            if index >= len(updated):
                raise SystemExit(f"slim fold solution {g.name}: missing vertex {index}")
            if not any(g.palette[pi].startswith(side) and w > 0.01
                       for pi, w in g.weights[index]):
                raise SystemExit(f"slim fold solution {g.name}: wrong vertex {index}")
            for ids in groups:
                if index in ids:
                    updated[ids] += np.asarray(delta, float)
                    break
            else:
                updated[index] += np.asarray(delta, float)
    g.verts = [tuple(map(float, row)) for row in updated]
    return {"vertices": sum(len(v) for v in SLIM_FOLD_DELTAS.values()),
            "max_shift_cm": round(float(np.linalg.norm(updated - start, axis=1).max()), 5)}


def rebind_arms_at_idle(g: bm.Group, template: bm.Template,
                        passes: int = IDLE_REST_TAUBIN_PASSES,
                        slim: bool = False) -> dict:
    """Re-author geometry and inverse binds together in the idle arm pose.

    This is a *rest-pose change*, not a pose-space corrective. First the old
    packed skinning evaluates the near-idle pose. Coincident UV/material
    vertices share that displacement, then a small seam-welded Taubin pass
    relaxes the outer sleeve's folded rest surface. Finally every palette
    bone's inverse bind is authored from the same absolute idle world (via
    ``Group.rest_worlds``), so evaluating that pose in the shipped model is the
    identity: the relaxed surface is exactly what the game displays at idle.

    The pose uses the renderer's measured flexion axis. Torso, leg, head and
    other unposed bones keep their old worlds. Weights, topology, UVs and
    materials are unchanged; body and shadow run through the same function.
    """
    import numpy as np
    import diesel_model as dm

    if not g.verts:
        return {"verts": 0, "passes": 0}
    old = np.asarray(g.verts, dtype=np.float64)
    worlds = idle_arm_rest_worlds(template)
    transforms = {}
    for pi, name in enumerate(g.palette):
        sid = template.name_id[name]
        old_world = template.worlds[sid]
        new_world = worlds.get(sid, old_world)
        transforms[pi] = np.array(
            dm.mat_mul(dm.mat_inv(old_world), new_world), float).reshape(4, 4)

    # Phase 1: rotate stored normals by the same LBS skinning matrix that
    # poses the vertices. Row-vector convention (posed = v @ R + t), so the
    # normal (a covector) transforms as n' = n @ (R^-1)^T. Snapshot *before*
    # g.verts is modified so hard-edge fallback uses the rotated authored
    # normal, not the stale 72°-bind-pose normal.
    n_pre = np.asarray(g.normals, dtype=np.float64)
    n_rot = np.zeros_like(n_pre)
    for i in range(len(n_pre)):
        R = np.zeros((3, 3), dtype=np.float64)
        tot = 0.0
        for pi, w in g.weights[i]:
            R += w * transforms[pi][:3, :3]
            tot += w
        R /= tot or 1.0
        nr = n_pre[i] @ np.linalg.inv(R).T
        ln = float(np.linalg.norm(nr))
        n_rot[i] = nr / ln if ln > 1e-12 else n_pre[i]
    posed = np.zeros_like(old)
    for i, point in enumerate(old):
        matrix = np.zeros((4, 4))
        total = 0.0
        for pi, weight in g.weights[i]:
            matrix += weight * transforms[pi]
            total += weight
        matrix /= total or 1.0
        posed[i] = point @ matrix[:3, :3] + matrix[3, :3]

    # Rebind displacement must not open duplicated material/UV seams.
    groups = _coincident_groups(old)
    for ids in groups:
        displacement = (posed[ids] - old[ids]).mean(axis=0)
        posed[ids] = old[ids] + displacement
    g.rest_worlds = {
        name: worlds.get(template.name_id[name], template.worlds[template.name_id[name]])
        for name in g.palette
    }
    g.verts = [tuple(map(float, row)) for row in posed]

    # Taubin smoothing (positive/negative Laplacian pair) relaxes the folded
    # sleeve without the shrinkage of ordinary Laplacian smoothing. The fade
    # is full within 3 cm of the elbow and zero by 10 cm; hands and other bone
    # chains are excluded. Each pass re-welds coincident positions.
    verts = posed.copy()
    before_relax = verts.copy()
    faces = np.asarray(g.faces, dtype=np.int64)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.concatenate([edges, edges[:, ::-1]])
    degree = np.bincount(edges[:, 0], minlength=len(verts)).astype(float)
    degree[degree == 0.0] = 1.0
    alpha = np.zeros(len(verts))
    for side in ("Left", "Right"):
        names = (f"{side}Arm", f"{side}ForeArm", f"{side}Hand")
        if any(name not in g.palette for name in names[:2]):
            continue
        A, E, H = [np.asarray(g.rest_worlds[name], float).reshape(4, 4)[3, :3]
                   for name in names]
        best = np.full(len(verts), np.inf)
        arc = np.zeros(len(verts))
        accumulated = 0.0
        for a, b in ((A, E), (E, H)):
            ab = b - a
            length = float(np.linalg.norm(ab))
            unit = ab / length
            t = np.clip((verts - a) @ unit, 0.0, length)
            distance = np.linalg.norm(verts - (a + t[:, None] * unit), axis=1)
            better = distance < best
            best[better] = distance[better]
            arc[better] = accumulated + t[better]
            accumulated += length
        distance_from_joint = np.abs(arc - np.linalg.norm(E - A))
        x = np.clip((10.0 - distance_from_joint) / 7.0, 0.0, 1.0)
        fade = x * x * (3.0 - 2.0 * x)
        pair_weight = np.array([
            sum(w for pi, w in g.weights[i] if g.palette[pi] in names[:2])
            for i in range(len(verts))])
        hand_weight = np.array([
            sum(w for pi, w in g.weights[i] if g.palette[pi] == names[2])
            for i in range(len(verts))])
        use = (pair_weight > 0.5) & (best < 12.0)
        alpha = np.maximum(alpha, fade * use * (1.0 - np.clip(hand_weight, 0.0, 1.0)))
    movable = np.where(alpha > 0.0)[0]
    for _ in range(passes):
        for lam in (0.55, -0.58):
            mean = np.column_stack([
                np.bincount(edges[:, 0], weights=verts[edges[:, 1], axis],
                            minlength=len(verts)) / degree
                for axis in range(3)])
            target = verts + lam * (mean - verts)
            verts[movable] = ((1.0 - alpha[movable, None]) * verts[movable]
                              + alpha[movable, None] * target[movable])
            _weld_positions(verts, groups)
    # Relaxation is useful only if the resulting outer surface remains valid.
    # Damp the largest mover at each inverting sliver, then re-weld the *delta*
    # so a seam cannot reopen after damping. A global backoff is the final
    # deterministic guard for a cluster of mutually adjacent slivers.
    displacement = verts - before_relax
    for _ in range(4):
        displacement = _damp_flips(faces, before_relax, displacement, passes=48)
        for ids in groups:
            displacement[ids] = displacement[ids].mean(axis=0)
    tri = faces
    n0 = np.cross(before_relax[tri[:, 1]] - before_relax[tri[:, 0]],
                  before_relax[tri[:, 2]] - before_relax[tri[:, 0]])
    for _ in range(20):
        candidate = before_relax + displacement
        n1 = np.cross(candidate[tri[:, 1]] - candidate[tri[:, 0]],
                      candidate[tri[:, 2]] - candidate[tri[:, 0]])
        bad = np.einsum("ij,ij->i", n0, n1) <= 0.0
        bad &= np.linalg.norm(displacement[tri], axis=2).max(axis=1) > 1e-6
        if not bad.any():
            break
        displacement *= 0.85
    else:
        raise SystemExit(f"idle elbow relaxation {g.name}: inversion damping failed")
    verts = before_relax + displacement
    g.verts = [tuple(map(float, row)) for row in verts]
    _check_flips(g, before_relax, f"idle elbow relaxation {g.name}")
    before_coverage = np.asarray(g.verts, dtype=np.float64).copy()
    coverage = _elbow_coverage_correction(g, template)
    _check_flips(g, before_coverage, f"idle elbow coverage {g.name}")
    fold = {"vertices": 0, "max_shift_cm": 0.0}
    if slim:
        before_fold = np.asarray(g.verts, dtype=np.float64).copy()
        fold = _apply_slim_fold_solution(g)
        _check_flips(g, before_fold, f"slim multi-pose fold solution {g.name}")
    _recompute_normals(g, n_rot)
    report = {
        "rest_elbow_deg": 72.0 - IDLE_ELBOW_STRAIGHTEN,
        "taubin_passes": passes,
        "verts": len(verts),
        "coincident_groups": len(groups),
        "max_rebind_shift_cm": round(float(np.linalg.norm(posed - old, axis=1).max()), 5),
        "max_relax_shift_cm": round(float(np.linalg.norm(verts - before_relax, axis=1).max()), 5),
        "coverage_vertices": coverage["vertices"],
        "max_coverage_shift_cm": coverage["max_shift_cm"],
        "fold_solution_vertices": fold["vertices"],
        "max_fold_solution_shift_cm": fold["max_shift_cm"],
    }
    print(f"  idle arm rest {g.name}: {len(movable)} verts in relaxation window, "
          f"{len(groups)} seam groups, max relax {report['max_relax_shift_cm']} cm; "
          f"coverage {coverage['vertices']} verts / "
          f"{coverage['max_shift_cm']} cm; fold solve "
          f"{fold['vertices']} verts / {fold['max_shift_cm']} cm")
    return report


# ---------------------------------------------------------------------------
# sleeve stitch: the source sheet is cut open along the inner arm and pinched
# shut at the elbow crease; both are topology, not deformation
# ---------------------------------------------------------------------------
def _arm_chain_weight(g: bm.Group):
    """Per-vertex weight on the arm chain (Shoulder/Arm/ForeArm/Hand)."""
    import numpy as np

    chain = tuple(pi for pi, name in enumerate(g.palette)
                  if name.endswith(("Arm", "Shoulder")) or name in
                  ("LeftHand", "RightHand"))
    out = np.zeros(len(g.verts))
    for i, infl in enumerate(g.weights):
        out[i] = sum(w for pi, w in infl if pi in chain)
    return out


def _sleeve_shells(g: bm.Group, arm):
    """Connected components (over triangles) dominated by arm weights.

    The blazer sleeve is one shell per arm; the cuff band is another. Anything
    hanging off a different bone chain (torso panels, trouser legs, shoes) is
    excluded, so the repair below cannot touch them.
    """
    import numpy as np

    parent = list(range(len(g.verts)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in g.faces:
        ra = find(int(a))
        for x in (int(b), int(c)):
            rx = find(x)
            if rx != ra:
                parent[rx] = ra
    root = np.array([find(i) for i in range(len(g.verts))])
    seen: dict[int, set[int]] = {}
    for a, b, c in g.faces:
        seen.setdefault(int(root[a]), set()).update((int(a), int(b), int(c)))
    keep = {r for r, vs in seen.items()
            if sum(arm[i] for i in vs) / len(vs) > 0.5}
    return root, keep


def _weld_attributes(g: bm.Group, i: int, j: int, v, n) -> None:
    """Give two duplicate vertices one position, normal and influence list."""
    import numpy as np

    wi = {p: w for p, w in g.weights[i]}
    wj = {p: w for p, w in g.weights[j]}
    merged = {p: 0.5 * (wi.get(p, 0.0) + wj.get(p, 0.0)) for p in set(wi) | set(wj)}
    top = sorted(merged.items(), key=lambda t: -t[1])[:3]
    total = sum(w for _, w in top) or 1.0
    g.weights[i] = [(p, w / total) for p, w in top]
    g.weights[j] = list(g.weights[i])
    nx = n[i] + n[j]
    nx /= float(np.linalg.norm(nx)) or 1.0
    g.normals[i] = g.normals[j] = tuple(float(x) for x in nx)
    px = 0.5 * (v[i] + v[j])
    g.verts[i] = g.verts[j] = tuple(float(x) for x in px)
    v[i] = v[j] = px


def _rim_pairs(v, n, ring, max_gap_cm: float, min_dot: float,
               weld_cm: float = 0.06):
    """Matched rims of one cut edge, as runs of (i, j) loop-index pairs.

    A sheet cut open along one line leaves ONE boundary loop that runs up one
    rim, around the far opening and back down the other rim, so the two rims are
    traversed in opposite directions and index as ``j = C - i``. That reflection
    is what separates a cut edge from a real opening: the two rims of a sock
    mouth pair up as ``j = i + n/2`` (a rotation across the hole), whose vertices
    face opposite ways. Both tests are required — see the module notes in
    ``docs/audits/2026-11-07-christie-slim-diagnosis.md``.
    """
    import numpy as np

    m = len(ring)
    P = v[np.asarray(ring, dtype=np.int64)]
    D = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2)
    for k in range(m):
        for d in (0, 1, m - 1):
            D[k, (k + d) % m] = np.inf
    part = -np.ones(m, dtype=np.int64)
    for k in range(m):
        j = int(np.argmin(D[k]))
        if D[k, j] <= max_gap_cm and int(np.argmin(D[j])) == k:
            part[k] = j
    pairs = [(k, int(part[k])) for k in range(m) if part[k] >= 0 and k < int(part[k])]
    if len(pairs) < 2:
        return []
    # same-facing surface only: the opposite sides of a round opening are
    # antiparallel and must not be bridged
    same = []
    for i, j in pairs:
        if float(n[ring[i]] @ n[ring[j]]) < min_dot:
            continue
        # Surface-tangency filter: genuine cloth slits separate tangentially
        # across the sheet; double-walled cuff shells and linings step
        # radially along the average normal, so they must not be bridged.
        gap = float(np.linalg.norm(v[ring[j]] - v[ring[i]]))
        if gap > weld_cm:
            d = v[ring[j]] - v[ring[i]]
            n_avg = n[ring[i]] + n[ring[j]]
            n_len = float(np.linalg.norm(n_avg))
            if n_len > 1e-9:
                n_hat = n_avg / n_len
                if abs(float(d @ n_hat)) / gap > 0.45:
                    continue
        same.append((i, j))
    if len(same) < 2:
        return []
    sums = {}
    for i, j in same:
        sums[(i + j) % m] = sums.get((i + j) % m, 0) + 1
    c_id, c_hits = max(sums.items(), key=lambda t: t[1])
    if c_hits < max(2, 0.6 * len(same)):
        return []
    sel = sorted((i, j) for i, j in same if (i + j) % m == c_id)
    runs: list[list[tuple[int, int]]] = []
    cur = [sel[0]]
    for prev, nxt in zip(sel, sel[1:]):
        # one unpartnered corner vertex on both rims is allowed (the cuff end of
        # the slit): the loft below steps over it. A bigger jump is a different
        # opening (the armhole) and must not be spanned.
        if 1 <= nxt[0] - prev[0] <= 2 and 1 <= prev[1] - nxt[1] <= 2:
            cur.append(nxt)
        else:
            runs.append(cur)
            cur = [nxt]
    runs.append(cur)
    return [r for r in runs if len(r) >= 2]


def _insert_faces(g: bm.Group, faces: list[tuple], slot: str) -> tuple[int, int]:
    """Add triangles to the render atom(s) whose vertex block contains them.

    A Diesel render atom is a (vertex block, triangle run) pair; the run has to
    stay contiguous and must never index outside its own block (an out-of-range
    D3D9 sample). Each new triangle is spliced into the run of the slice whose
    vertex block contains all three of its vertices, and later runs' ``base_index``
    is shifted to match. The vertex array is left untouched.

    The old rule - appending every triangle to the first slice with a matching
    material slot - is wrong for single-slot groups: s_body maps every slice to
    `shadow_caster`, so it always returned k = 0 and put slice-1's cuff
    triangles in atom 0's run, indexing past its own vertex block.

    Triangles whose vertices span more than one block, or fall in no block at
    all (e.g. the external neck cap), keep the historical behaviour and are
    appended to the first matching slice's run.
    """
    if not faces:
        return (0, 0)
    added = len(faces)
    cands = [k for k, s in enumerate(g.mat_slots) if s == slot]
    if not cands:
        base_i = len(g.faces) * 3
        g.faces.extend(faces)
        g.slices.append((slot, len(g.verts), base_i, added, 0))
        g.mat_slots.append(slot)
        return (base_i // 3, added)

    def owner(f: tuple[int, int, int]) -> int | None:
        for k in cands:
            _m, bv, _bi, _t, nv = g.slices[k]
            if all(bv <= v < bv + nv for v in f):
                return k
        return None

    groups: dict[int, list[tuple[int, int, int]]] = {k: [] for k in cands}
    homeless: list[tuple[int, int, int]] = []
    for f in faces:
        k = owner(f)
        if k is None:
            homeless.append(f)
        else:
            groups[k].append(f)

    # Rebuild the index buffer and the atom table so each triangle sits in the
    # run of the slice whose vertex block contains it.  Slices are processed in
    # ascending base_index so the new runs stay contiguous and tile the stream.
    old_faces = list(g.faces)
    order = sorted(range(len(g.slices)), key=lambda k: g.slices[k][2])
    new_faces: list[tuple[int, int, int]] = []
    new_slices: list[tuple] = []
    cursor = 0
    first_at = None
    for k in order:
        slot_k, base_v, base_i, tri_count, nverts = g.slices[k]
        old_start = base_i // 3
        new_faces.extend(old_faces[old_start:old_start + tri_count])
        new_tris = groups.get(k, [])
        new_faces.extend(new_tris)
        new_tri_count = tri_count + len(new_tris)
        new_slices.append((slot_k, base_v, cursor * 3, new_tri_count, nverts))
        if new_tris and first_at is None:
            first_at = cursor * 3 + tri_count * 3
        cursor += new_tri_count

    # Homeless triangles (vertices span blocks or fall in no block): historical
    # behaviour - append to the first matching slice's run.
    if homeless:
        for i, (slot_k, _bv, base_i, tri_count, _nv) in enumerate(new_slices):
            if slot_k == slot:
                at = (base_i // 3) + tri_count
                new_faces[at:at] = homeless
                slot_k2, bv2, _bi, t2, nv2 = new_slices[i]
                new_slices[i] = (slot_k2, bv2, base_i, t2 + len(homeless), nv2)
                if first_at is None:
                    first_at = base_i + tri_count * 3
                break

    g.faces = new_faces
    g.slices = new_slices
    return (first_at if first_at is not None else 0, added)


def _check_slices(g: bm.Group, tag: str) -> None:
    """The render atoms must still tile the triangle stream."""
    want = 0
    for _m, _bv, base_i, tris, _nv in sorted(g.slices, key=lambda s: s[2]):
        if base_i != want * 3:
            raise SystemExit(f"{tag}: render atom starts at triangle "
                             f"{base_i // 3}, not {want}")
        want += tris
    if want != len(g.faces):
        raise SystemExit(f"{tag}: atoms draw {want} of {len(g.faces)} triangles")


def _edge_maps(faces):
    """Undirected edge -> use count, and the owner's direction when there is one.

    ``dirn[key]`` is how the single owning face traverses the edge (``x -> y``);
    any edge used twice loses its entry, because a closed edge has no direction
    to match. This is the whole basis of the fill/bridge validation below: a new
    triangle may only be added to an edge that has room for it, and where it will
    be the second user it has to run *against* the owner or the engine culls one
    of the two faces and the hole it was meant to close reappears.
    """
    count: dict[tuple[int, int], int] = {}
    dirn: dict[tuple[int, int], tuple[int, int]] = {}
    for a, b, c in faces:
        for x, y in ((a, b), (b, c), (c, a)):
            k = (x, y) if x < y else (y, x)
            count[k] = count.get(k, 0) + 1
            if count[k] == 1:
                dirn[k] = (x, y)
            else:
                dirn.pop(k, None)
    return count, dirn


def _face_edges(tri):
    return ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0]))


def _tri_area(v, tri) -> float:
    import numpy as np

    return 0.5 * float(np.linalg.norm(
        np.cross(v[tri[1]] - v[tri[0]], v[tri[2]] - v[tri[0]])))


def _face_vn_dot(v, n, tri) -> float:
    """Unit geometric normal dotted with the unit mean vertex normal of a
    triangle. 1.0 = the face shades smoothly with its vertices; negative =
    the face is inside-out or a bulkhead fin orthogonal to the surface."""
    import numpy as np

    fn = np.cross(v[tri[1]] - v[tri[0]], v[tri[2]] - v[tri[0]])
    fn_len = float(np.linalg.norm(fn))
    if fn_len < 1e-9:
        return -1.0
    fn_hat = fn / fn_len
    vn = n[list(tri)].mean(axis=0)
    vn_len = float(np.linalg.norm(vn))
    if vn_len < 1e-9:
        return -1.0
    return float(fn_hat @ (vn / vn_len))


def _closable(tris, count, dirn) -> bool:
    """Would adding ``tris`` keep every edge they touch 2-manifold and wound?"""
    use: dict[tuple[int, int], list] = {}
    for t in tris:
        for x, y in _face_edges(t):
            k = (x, y) if x < y else (y, x)
            use.setdefault(k, []).append((x, y))
    for k, dirs in use.items():
        have = count.get(k, 0)
        if have + len(dirs) > 2:
            return False
        if have == 1 and len(dirs) == 1 and dirs[0] == dirn[k]:
            return False
    return True


def _commit(tris, count, dirn) -> None:
    for t in tris:
        for x, y in _face_edges(t):
            k = (x, y) if x < y else (y, x)
            count[k] = count.get(k, 0) + 1
            if count[k] == 1:
                dirn[k] = (x, y)
            else:
                dirn.pop(k, None)


def _rim_arc(m: int, start: int, stop: int, step: int) -> list[int]:
    """Positions walking the loop from ``start`` to ``stop`` (cyclic)."""
    out = [start]
    k = start
    for _ in range(m):
        if k == stop:
            return out
        k = (k + step) % m
        out.append(k)
    return []


#: By how much a later fan has to beat the best one so far to replace it.
_FAN_TIE = 1e-9


def _fill_ring(ring, taken, count, dirn, v, n, min_face_cm2):
    """Triangulate a small boundary loop, wound against its own edges.

    Every fan start is tried, because the first one can be blocked: the elbow
    pinhole has a triangle lying across one diagonal, so a fan from the wrong
    corner would either duplicate it or put three faces on that edge. Triangles
    that already exist (as that flap) are dropped rather than re-added — a
    coincident copy would z-fight — and the best-scoring fan wins. The winding
    is never guessed from vertex normals: the loop is directed by its owning
    faces, so the reverse direction is exact.

    A fan is accepted only if its area-weighted mean face/vertex-normal
    alignment is positive — rejecting inside-out caps on small decorative
    cuff-tab perimeters while keeping genuine pinholes (whose area-weighted
    mean stays > 0 even when individual faces sit in a crease).
    """
    m = len(ring)
    best = None
    for start in range(m):
        rr = ring[start:] + ring[:start]
        cand = [(rr[0], rr[k + 1], rr[k]) for k in range(1, m - 1)]
        cand = [t for t in cand if len(set(t)) == 3]
        cand = [t for t in cand if frozenset(t) not in taken]
        cand = [t for t in cand if _tri_area(v, t) >= min_face_cm2]
        if not cand or (m > 3 and len(cand) < 2):
            continue
        if not _closable(cand, count, dirn):
            continue
        total_area = 0.0
        weighted = 0.0
        for t in cand:
            area = _tri_area(v, t)
            total_area += area
            weighted += area * _face_vn_dot(v, n, t)
        if total_area <= 0.0:
            continue
        mean = weighted / total_area
        # A later start has to be better by more than rounding can explain. Two
        # starts often give the same triangles (a quad has one diagonal that
        # works), and then their means are equal in exact arithmetic. Until
        # 2026-11-12 whichever of them the CPU's rounding made larger won, and
        # that decided the order of the triangles in the file.
        if best is None or mean > best[0] + _FAN_TIE:
            best = (mean, cand)
    if best is None or best[0] <= 0.0:
        return []
    return best[1]


def coincident_normal_report(g: bm.Group, max_deg: float = 30.0) -> dict:
    """Count coincident vertex pairs whose normals disagree by > ``max_deg``.

    The 2B reference carries 22,486 coincident pairs and **none** of them
    diverges: in a PD2-authored mesh a duplicated vertex is a UV/material
    split, not a shading edge. Ours had 480 (slim) / 856 (base) diverging,
    which shades as a hard crease exactly along every seam. Pairs are only
    counted as *interior* when neither copy sits on a border edge - those are
    real garment folds (hem, cuff rim, lining edge) and must keep their own
    normals.
    """
    import numpy as np

    verts = np.asarray(g.verts, float)
    normals = np.asarray(g.normals, float)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    # Same 3D surface-topology border/crease definition as
    # unify_coincident_normals, so the build gate and the report agree on what
    # is an exempt garment fold vs. a UV split that must be unified.
    border, crease, gid_of = _surface_border_and_creases(g, verts)
    exempt = border | crease
    interior = border_pairs = 0
    for ids in _coincident_groups(verts):
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                if np.degrees(np.arccos(np.clip(normals[a] @ normals[b],
                                                -1, 1))) <= max_deg:
                    continue
                if gid_of[a] in exempt or gid_of[b] in exempt:
                    border_pairs += 1
                else:
                    interior += 1
    return {"interior": interior, "border": border_pairs,
            "pairs": interior + border_pairs}




def _surface_border_and_creases(g: bm.Group, verts, tol: float = 1e-4,
                                smooth_deg: float = 15.0):
    """Classify coincident copies by 3D surface topology, not index identity.

    Returns (border, crease, gid_of): ``border``/``crease`` are sets of 3D
    group ids whose surface is open, or whose copies sit across a genuine
    crease. A group in either set keeps its own normals. ``gid_of[i]`` is the
    group id of vertex index ``i``.

    A UV/material split duplicates one 3D position into two indices, so the
    seam's own edges are index-space boundaries. Measuring "is this a surface
    border?" in index space conflates "this edge is a UV seam" with "this edge
    is the edge of the garment", which exempted 82 % of coincident groups
    wholesale. The 3D test below only excludes real open rims (an edge used by
    != 2 faces in 3D group space) and real creases (copies whose geometric
    normals diverge past ``smooth_deg``).
    """
    import numpy as np

    key = np.round(verts / tol).astype(np.int64)
    gid_of = np.empty(len(verts), np.int64)
    index_of = {}                      # position key -> group id
    groups = {}                        # group id      -> [vertex indices]
    for i, k in enumerate(map(tuple, key)):
        if k not in index_of:
            index_of[k] = len(index_of)
            groups[index_of[k]] = []
        gid_of[i] = index_of[k]
        groups[index_of[k]].append(i)

    faces = np.asarray(g.faces, np.int64)
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                  verts[faces[:, 2]] - verts[faces[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)

    # 3D edge -> incident faces. An edge shared by != 2 faces is an open border.
    edge = {}
    for fi, (a, b, c) in enumerate(faces):
        for x, y in ((a, b), (b, c), (c, a)):
            gx, gy = gid_of[x], gid_of[y]
            if gx == gy:
                continue
            edge.setdefault((gx, gy) if gx < gy else (gy, gx), []).append(fi)

    border = set()
    for (gx, gy), fs in edge.items():
        if len(fs) != 2:
            border.add(gx)
            border.add(gy)

    # Per-copy geometric normal, to measure the crease across the seam.
    vf = {}
    for fi, (a, b, c) in enumerate(faces):
        for v in (a, b, c):
            vf.setdefault(v, []).append(fi)
    crease = set()
    for gid, ids in groups.items():
        if len(ids) < 2 or gid in border:
            continue
        gnorm = []
        for i in ids:
            m = fn[vf[i]].sum(axis=0)
            ln = float(np.linalg.norm(m))
            gnorm.append(m / ln if ln > 1e-9 else np.zeros(3))
        gnorm = np.asarray(gnorm)
        sep = np.degrees(np.arccos(np.clip((gnorm @ gnorm.T).min(), -1.0, 1.0)))
        if sep > smooth_deg:
            crease.add(gid)
    return border, crease, gid_of


def unify_coincident_normals(g: bm.Group, *, max_deg: float = 1.0,
                             max_mean_deg: float = 120.0) -> dict:
    """Give every *interior* coincident group one shared normal.

    Coincident vertices exist because one position needs several UVs or
    materials. PD2 meshes authored that way carry identical normals
    on every copy (2B: 0 of 22,486 pairs diverge), so the UV split is invisible.
    Ours inherited the source's copy-per-corner normals instead, and each seam
    shades as a hard step - the one shading defect the screenshot review found
    that survived re-measurement (diagnosis work order item 1).

    Only *interior* groups are unified: a copy that sits on a border edge is
    the edge of a garment panel, and its two sides are a real fold (the cuff
    rim, the sleeve opening, the lining edge). Those keep both normals, so the
    pass cannot blanket-smooth genuine hard edges.

    Positions, UVs, faces, materials and weights are untouched - only the
    stored normal of interior duplicates is replaced by the group mean.

    ``max_deg`` is the already-agree tolerance: copies whose stored normals are
    within ``max_deg`` of each other need no work (the census treats groups at
    <= 1 deg as "no work"). ``max_mean_deg`` is the upper guard: copies more
    than ``max_mean_deg`` apart are left alone because their mean lies further
    than 60 degrees from both and would shade neither surface. The worst
    interior pair in the shipped meshes is 101 (slim) / 103 (base) degrees,
    comfortably inside that bar; the guard exists so a future edit cannot
    average two genuinely opposed layers into a sideways normal.
    """
    import numpy as np

    report = {"groups": 0, "verts": 0}
    if not len(g.verts) or len(g.normals) != len(g.verts):
        return report
    verts = np.asarray(g.verts, float)
    normals = np.asarray(g.normals, float)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    count: dict[tuple[int, int], int] = {}
    for a, b, c in g.faces:
        for x, y in ((a, b), (b, c), (c, a)):
            k = (x, y) if x < y else (y, x)
            count[k] = count.get(k, 0) + 1
    border, crease, gid_of = _surface_border_and_creases(g, verts)
    for ids in _coincident_groups(verts):
        # All copies of one position share a gid: either the whole group is a
        # real open rim/crease (kept) or every copy is interior (unified).
        if gid_of[ids[0]] in border or gid_of[ids[0]] in crease:
            continue
        # Redundant split: every copy carries the same UV, so there is no
        # seam to fix (plan §3.4 "no UV difference" row). These groups are
        # excluded from the unification count even when their stored normals
        # disagree - nothing about the UV map needs healing here.
        if len(g.uvs) == len(g.verts):
            uv0 = np.asarray(g.uvs[ids[0]], float)
            if all(np.allclose(np.asarray(g.uvs[i], float), uv0, atol=1e-6)
                   for i in ids[1:]):
                continue
        inner = [i for i in ids if gid_of[i] not in border]
        if len(inner) < 2:
            continue
        sub = normals[inner]
        spread = float(np.degrees(np.arccos(np.clip((sub @ sub.T).min(), -1, 1))))
        if spread <= max_deg or spread > max_mean_deg:
            continue
        mean = sub.sum(axis=0)
        length = float(np.linalg.norm(mean))
        if length < 1e-9:      # two copies flat opposite: no meaningful mean
            continue
        normals[inner] = mean / length
        report["verts"] += len(inner)
        report["groups"] += 1
        report["verts"] += len(ids)
    if report["verts"]:
        g.normals = [tuple(float(x) for x in row) for row in normals]
    return report


def stitch_sleeve_seams(g: bm.Group, template: bm.Template, *,
                        max_gap_cm: float = 3.6, weld_cm: float = 0.06,
                        min_normal_dot: float = 0.3,
                        max_hole_verts: int = 6,
                        min_face_cm2: float = 2.0e-3) -> dict:
    """Close the topology holes the DOA5 blazer sleeve ships with.

    **The underarm slit.** The sleeve is authored as a sheet wrapped around the
    arm and cut open along the inner-arm line. One boundary loop runs up the
    front rim, around the armhole and back down the back rim; the two rims
    coincide at the armpit and again near the cuff, but stand 2-3 cm apart
    across the upper arm and the elbow. Nothing spans that strip, so at the
    authored idle it is hidden against the ribs and at any other pose the game
    shows a slit of bare arm inside the sleeve. Measured off the shipped model:
    a 20-40 degree open sector of the sleeve cross-section from z 121 to z 133.
    This pass bridges the strip with new triangles built from the *existing* rim
    vertices — no vertex is moved, added or removed, so every rim keeps its own
    UV and the two texture islands stay intact. Those islands are neighbouring
    columns of the same fabric (flat tan across the whole gap), which is what
    lets the bridge read as continuous cloth; the winding comes from the rim
    edges themselves, not from a shading guess.

    **The elbow pinhole.** A 4-vertex boundary loop sits in the same shell at
    the inner elbow, identical in both packs, so it is inherited from the source
    rather than caused by the slim pass. It is triangulated across its free
    diagonal; a triangle already covering the other diagonal is left in place
    and not duplicated.

    Pairs closer than ``weld_cm`` are the opposite case — duplicated rows that
    are already touching — and get one position, normal and influence list so
    they can never shade apart or be driven apart.

    Only shells dominated by the arm chain are touched, and every edit is
    validated against the edge map first: a new triangle may only go where the
    edge it attaches to has room for it and the right direction. Returns the
    report shown in the build log.
    """
    import numpy as np

    report = {"loops": 0, "filled": 0, "bridged": 0, "welded": 0,
              "new_faces": 0, "details": []}
    if not g.faces:
        return report
    v = np.asarray(g.verts, dtype=np.float64)
    n = np.asarray(g.normals, dtype=np.float64)
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    # UV continuation: clone bridge vertices that wrap across the sleeve UV
    # island so bridge triangles don't stretch Δu ≈ 0.20 across the seam.
    uvs_arr = np.asarray(g.uvs, dtype=np.float64) if len(g.uvs) == len(g.verts) else None
    has_uvs = uvs_arr is not None and float(np.ptp(uvs_arr)) > 1e-4
    clone_map: dict[int, int] = {}
    clone_data: list[tuple] = []
    next_clone = len(g.verts)
    arm = _arm_chain_weight(g)
    root, shells = _sleeve_shells(g, arm)
    if not shells:
        return report

    slice_of = [-1] * len(g.faces)
    for si, (_m, _bv, base_i, tris, _nv) in enumerate(g.slices):
        for f in range(base_i // 3, base_i // 3 + tris):
            slice_of[f] = si
    owner_face: dict[tuple[int, int], int] = {}
    for f, (a, b, c) in enumerate(g.faces):
        for x, y in ((a, b), (b, c), (c, a)):
            k = (x, y) if x < y else (y, x)
            owner_face.setdefault(k, f)

    faces = [(int(a), int(b), int(c)) for a, b, c in g.faces]
    taken = {frozenset(t): i for i, t in enumerate(faces)}
    count, dirn = _edge_maps(faces)

    # Connected-component triangle counts over g.faces (union-find by vertex
    # index, NOT 3D-coincident position shells). Used to gate short-loop hole
    # filling: small decorative cuff-tab perimeters (6-9 tris) are rejected,
    # while the 698-triangle main sleeve shell keeps its inner-elbow pinhole.
    comp_parent = list(range(len(v)))

    def comp_find(x):
        while comp_parent[x] != x:
            comp_parent[x] = comp_parent[comp_parent[x]]
            x = comp_parent[x]
        return x

    for a, b, c in faces:
        ra, rb, rc = comp_find(a), comp_find(b), comp_find(c)
        comp_parent[rb] = ra
        comp_parent[rc] = ra
    comp_tris = {}
    for a, b, c in faces:
        r = comp_find(a)
        comp_tris[r] = comp_tris.get(r, 0) + 1
    comp_of = {i: comp_tris[comp_find(i)] for i in range(len(v))}

    extra: dict[str, list[tuple]] = {}
    for loop in bm.boundary_loops(faces):
        ring = [int(i) for i in loop[:-1]]
        if len(ring) < 3 or len(set(ring)) != len(ring):
            continue
        if not all(int(root[i]) in shells for i in ring):
            continue
        if sum(arm[i] > 0.4 for i in ring) / len(ring) < 0.8:
            continue
        slots: dict[str, int] = {}
        for k in range(len(ring)):
            x, y = ring[k], ring[(k + 1) % len(ring)]
            kk = (x, y) if x < y else (y, x)
            if count.get(kk) != 1 or kk not in owner_face:
                continue
            slot = g.mat_slots[slice_of[owner_face[kk]]]
            slots[slot] = slots.get(slot, 0) + 1
        if not slots:
            continue
        slot = max(slots.items(), key=lambda t: t[1])[0]
        report["loops"] += 1
        centre = v[np.asarray(ring)].mean(axis=0)

        if len(ring) <= max_hole_verts:
            # Only close interior holes in a substantial sleeve shell
            # (min component triangle count >= 32). Rejects small decorative
            # cuff-tab perimeters (6-9 tris) whose caps would shade inside-out;
            # keeps the 698-triangle main sleeve's inner-elbow pinhole.
            if min(comp_of[i] for i in ring) < 32:
                continue
            tris = _fill_ring(ring, taken, count, dirn, v, n, min_face_cm2)
            if tris:
                _commit(tris, count, dirn)
                extra.setdefault(slot, []).extend(tris)
                for t in tris:
                    taken[frozenset(t)] = -1
                report["filled"] += 1
                report["details"].append(
                    f"filled {len(tris)} tri(s) at ({centre[0]:.1f},"
                    f"{centre[1]:.1f},{centre[2]:.1f})")
            continue

        m = len(ring)
        for run in _rim_pairs(v, n, ring, max_gap_cm, min_normal_dot, weld_cm):
            # Weld the touching pairs first: the loft must measure the final
            # positions, or a triangle that closes an already-coincident pair
            # is built at its pre-weld area and collapses to a degenerate one.
            for i, j in run:
                if float(np.linalg.norm(v[ring[i]] - v[ring[j]])) <= weld_cm:
                    _weld_attributes(g, ring[i], ring[j], v, n)
                    report["welded"] += 1
            quads: list[tuple] = []
            n_quads = 0
            for (i, j), (i2, j2) in zip(run, run[1:]):
                # Loft the two rim arcs between consecutive matched pairs. They
                # are the same length whenever the pairing is contiguous; where
                # a corner vertex on both rims has no partner (the cuff end of
                # the slit) the arcs are one step longer and still match, which
                # is what closes that corner instead of leaving a wedge.
                arc_a = _rim_arc(m, i, i2, 1)
                arc_b = _rim_arc(m, j, j2, -1)
                if not arc_a or len(arc_a) != len(arc_b):
                    continue
                for k in range(len(arc_a) - 1):
                    a, b = ring[arc_a[k]], ring[arc_a[k + 1]]
                    d, c = ring[arc_b[k]], ring[arc_b[k + 1]]
                    if len({a, b, c, d}) < 4:
                        continue
                    # Two candidate diagonals for quad (a, b, c, d). Score each
                    # valid split by the worst face/vertex-normal alignment and
                    # keep the better one; reject bulkhead fins orthogonal to
                    # the surface (defect 2a).
                    best = None
                    for cand in (
                        [(a, d, c), (a, c, b)],
                        [(a, d, b), (d, c, b)],
                    ):
                        for winding in (cand, [(t[0], t[2], t[1]) for t in cand]):
                            if any(_tri_area(v, t) < min_face_cm2 for t in winding):
                                continue
                            if not _closable(winding, count, dirn):
                                continue
                            score = min(_face_vn_dot(v, n, t) for t in winding)
                            if best is None or score > best[0]:
                                best = (score, winding)
                    if best is None or best[0] < 0.5:
                        continue
                    # UV continuation: clone rim-B vertices that wrap across the
                    # sleeve UV island from their rim-A partners, so bridge
                    # triangles don't stretch Δu ≈ 0.20 across the seam.
                    # Clones are created only for selected quads; a vertex is
                    # cloned once globally (first wrap wins) and its clone is
                    # used whenever that vertex wraps again.
                    quad_clone: dict[int, int] = {}
                    if has_uvs:
                        for orig, anchor in ((d, a), (c, b)):
                            if float(np.linalg.norm(uvs_arr[orig] - uvs_arr[anchor])) > 0.05:
                                if orig in clone_map:
                                    quad_clone[orig] = clone_map[orig]
                                else:
                                    quad_clone[orig] = next_clone
                                    clone_map[orig] = next_clone
                                    clone_data.append((v[orig], n[orig],
                                                       tuple(uvs_arr[anchor]),
                                                       list(g.weights[orig])))
                                    next_clone += 1
                    _commit(best[1], count, dirn)
                    # Emit with clone indices for UV continuity; edge tracking
                    # above used original IDs so manifold checks stay valid.
                    resolved = [tuple(quad_clone.get(x, x) for x in t)
                                for t in best[1]]
                    quads.extend(resolved)
                    n_quads += 1
            if quads:
                extra.setdefault(slot, []).extend(quads)
                report["bridged"] += n_quads
                gap_max = max(float(np.linalg.norm(v[ring[i]] - v[ring[j]]))
                              for i, j in run)
                report["details"].append(
                    f"bridged {n_quads} quad(s) / {len(quads)} tris over "
                    f"{len(run)} rim pairs, gap to {gap_max:.2f} cm at "
                    f"({centre[0]:.1f},{centre[1]:.1f},{centre[2]:.1f})")

    # Append cloned vertices (same position/normal/weights, adjusted UV) and
    # extend the owning slice's vertex range so clone indices fall in-bounds.
    if clone_data:
        orig_len = len(g.verts)
        for cd in clone_data:
            g.verts.append(tuple(cd[0]))
            g.normals.append(tuple(cd[1]))
            g.uvs.append(tuple(cd[2]))
            g.weights.append(cd[3])
        for si in range(len(g.slices)):
            _m, bv, _bi, _t, nv = g.slices[si]
            if bv + nv == orig_len:
                g.slices[si] = (_m, bv, _bi, _t, nv + len(clone_data))
                break

    for slot, tris in extra.items():
        start, added = _insert_faces(g, tris, slot)
        report["new_faces"] += added
    if report["new_faces"]:
        _check_slices(g, f"stitch {g.name}")
        breaks = bm.orientation_breaks(g)
        agree = bm.winding_agreement(g.verts, g.faces, g.normals)
        if breaks:
            raise SystemExit(f"stitch {g.name}: {breaks} orientation breaks "
                             "after closing the sleeve")
        if agree < 0.9:
            raise SystemExit(f"stitch {g.name}: winding agreement {agree:.1%}")
    return report


def taper_cuff(g: bm.Group, template: bm.Template,
               bones=("Left", "Right")) -> list[dict]:
    """Pull the sleeve mouth in toward the forearm axis (the "cone" cuff).

    ``p' = c(t) + off * scale`` with ``c`` the point on the ForeArm axis and
    ``off`` the radial offset, so the mouth keeps its axial position - the
    in-game glove spawns at the ``Hand`` pivot and the fit report measures that
    distance - while the radius comes down over the last ``CUFF_TAPER_CM``.
    The scale is ``1 - CUFF_TAPER * s`` with ``s`` a smoothstep from the start
    of the window to the wrist. Guard rails:

      * only the visible outer shell moves (``d > CUFF_INNER_CM``); the lining
        and the hidden cap verts stay, or they get squeezed toward the axis;
      * nothing is ever pushed *outward*: the pull stops at
        ``min(d, max(hand p90 + CUFF_HAND_CLEAR_CM, CUFF_FLOOR_CM))`` per slab,
        so the sleeve cannot swallow the hand or the glove;
      * verts carrying no ForeArm weight are untouched, so the torso, the other
        arm and the coat hem do not move.

    The displacement field is *diffused over the mesh graph* before it is
    applied and any inverting sliver is damped afterwards: the sleeve is
    bridged to the hand (32 triangles mix a ForeArm- and a Hand-dominant
    vertex) and every ring carries several layers, so a per-vertex or
    per-weight-class scale tears those bridge triangles (measured: 63 and 38
    flipped faces on two earlier attempts). Skeleton, bind matrices and skin
    weights are untouched.

    Measured effect (base pack, p90 radius at the mouth): 6.37 -> 5.39 cm,
    median 5.04 -> 3.89 cm; slim 5.98 -> 5.15. Axial distance from the mouth
    ring to the ``Hand`` pivot is unchanged; the cuff ring metric moves
    1.12 -> 1.03 cm because it is a 3D distance and the ring came in radially.
    """
    import numpy as np

    v = np.array(g.verts, dtype=np.float64)
    n_old = np.array(g.normals, dtype=np.float64)
    new = v.copy()
    disp_all = np.zeros_like(v)
    sides: list[dict] = []
    records: list[dict] = []
    for side in bones:
        arm, fore, hand = (f"{side}{n}" for n in ("Arm", "ForeArm", "Hand"))
        if fore not in template.name_id or hand not in template.name_id:
            continue
        e, h = _joint(template, fore), _joint(template, hand)
        u = (h - e) / float(np.linalg.norm(h - e))
        L = float(np.linalg.norm(h - e))
        t = (v - e) @ u
        off = (v - e) - np.outer(t, u)
        d = np.linalg.norm(off, axis=1)
        # weights: sleeve verts move, hand-dominant verts do not
        idx = {name: g.palette.index(name) for name in (fore, hand)
               if name in g.palette}
        if fore not in idx:
            continue
        w_fore = np.zeros(len(v))
        w_hand = np.zeros(len(v))
        for i, infl in enumerate(g.weights):
            for pi, w in infl:
                if pi == idx[fore]:
                    w_fore[i] += w
                elif hand in idx and pi == idx[hand]:
                    w_hand[i] += w
        # Per-slab scale, not per-vertex: a vertex's own weight swings from 0.8
        # to 1.0 across one ring and to 0 on the hand, and scaling each vertex
        # by its own weight tears the bridge triangles between the layers
        # (measured: 63 flipped faces on the first attempt). One scale per
        # slab moves a cross-section rigidly in the radial direction, which
        # cannot flip anything.
        edges = np.arange(L - CUFF_TAPER_CM, L + 2.0, 1.0)
        slab_scale = np.ones(len(edges) - 1)
        slab_clear = np.zeros(len(edges) - 1)
        for k in range(len(edges) - 1):
            m = (t >= edges[k]) & (t < edges[k + 1])
            hnd = m & (w_hand > 0.6)
            s_mid = _smoothstep((0.5 * (edges[k] + edges[k + 1])
                                 - (L - CUFF_TAPER_CM)) / CUFF_TAPER_CM)
            slab_scale[k] = 1.0 - CUFF_TAPER * s_mid
            slab_clear[k] = (np.percentile(d[hnd], 90) + CUFF_HAND_CLEAR_CM
                             if hnd.sum() >= 3 else 0.0)
        # smooth the guard profile so a sparse slab cannot punch a dent
        for _ in range(2):
            slab_clear = 0.5 * slab_clear + 0.25 * (np.roll(slab_clear, 1)
                                                    + np.roll(slab_clear, -1))
        # The sleeve is *bridged* to the hand (32 triangles mix a ForeArm-
        # dominant and a Hand-dominant vertex) and every ring carries several
        # layers at once, so any per-vertex or per-class switch tears slivers
        # (measured: 63 flipped faces from per-vertex weights, 38 from a
        # weight-membership guard plus a per-slab scale, 9 from a spatial
        # smoothstep on the distance to the hand). The displacement field is
        # therefore diffused over the mesh graph: start from the slab taper,
        # then repeatedly replace every vertex's value by a blend of itself
        # and its edge neighbours. That turns the step into a gradient a few
        # edges wide, which no triangle can flip, and leaves the taper's
        # amplitude intact where the sleeve is a clean tube.
        ks = np.clip(np.searchsorted(edges, t) - 1, 0, len(edges) - 2)
        # Only the visible outer shell is tapered: the lining sits 3-3.5 cm
        # from the axis and squeezing it toward the floor flips the slivers
        # that seam it to the mouth ring (measured: 2 flipped faces). The step
        # this mask introduces is removed by the diffusion below.
        alpha = np.where((w_fore > 0.05) & (d > CUFF_INNER_CM),
                         1.0 - slab_scale[ks], 0.0)
        alpha = _diffuse(g.faces, alpha, iterations=40)
        alpha = np.where(w_fore > 0.02, alpha, 0.0)
        # guards: never *push* a vertex outwards (the sleeve has inner layers
        # and hidden cap verts well inside CUFF_FLOOR_CM - clamping them up
        # inflated the mesh by up to 2.9 cm and tore the rings apart); only
        # stop the pull-in early.
        lo = np.minimum(d, np.maximum(slab_clear[ks], CUFF_FLOOR_CM))
        target = np.maximum(d * (1.0 - alpha), lo)
        target = np.minimum(target, d)
        scale = np.where(d > 1e-9, target / np.maximum(d, 1e-9), 1.0)
        disp = off * (scale - 1.0)[:, None]
        disp_all += disp
        sides.append({"side": side, "d": d, "u": u, "e": e,
                      "mov": np.linalg.norm(disp, axis=1) > 1e-6,
                      "shift": np.linalg.norm(disp, axis=1).max(),
                      "mouth": (np.abs(t - L) < 2.0) & (w_fore > 0.6)
                      & (w_hand < 0.3)})
    # -- flip-safe damping -------------------------------------------------
    # A few sliver triangles (0.07-0.35 cm^2 - the lining seaming the mouth
    # ring to the hand) can still invert when one of their vertices moves and
    # the others do not. Instead of leaving them flipped or softening the whole
    # taper, the largest-moving vertex of every inverting triangle is damped by
    # half, repeatedly, until none invert: a local, deterministic correction on
    # a handful of verts.
    disp_all = _damp_flips(g.faces, v, disp_all)
    new = v + disp_all
    for info in sides:
        sel = info["mouth"]
        if not sel.any():
            continue
        e, u, d = info["e"], info["u"], info["d"]
        after = np.linalg.norm(
            new[sel] - (e + np.outer((new[sel] - e) @ u, u)), axis=1)
        records.append({"side": info["side"],
                        "verts": int(info["mov"].sum()),
                        "mouth_p90_cm": round(float(np.percentile(d[sel], 90)), 2),
                        "mouth_p90_after_cm": round(float(np.percentile(after, 90)), 2),
                        "max_shift_cm": round(
                            float(info["shift"]), 2)})
        r = records[-1]
        print(f"  cuff {info['side']}: {r['verts']} verts, mouth p90 "
              f"{r['mouth_p90_cm']} -> {r['mouth_p90_after_cm']} cm, largest "
              f"shift {r['max_shift_cm']} cm")
    g.verts = [tuple(row) for row in new]
    _check_flips(g, v, f"cuff taper {g.name}")
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
# what the pack registers; las_outfit_pack.py writes the files
# ---------------------------------------------------------------------------
def registration(identity: Identity, textures=(), with_fps: bool = True) -> lop.Registration:
    """What a Christie pack tells BeardLib and LAS about itself.

    No head, so `replace_body`. `textures` are the pack's texture files: each
    `_df` among them registers its df/nm pair by base name. The pack without
    hands ships the glove adapter (`las_outfit_pack.render_glove_adapter_lua`).
    """
    stems = [name[:-len(".texture")] if name.endswith(".texture") else name for name in sorted(textures)]
    return lop.Registration(
        item_id=identity.item_id, display_name=identity.display_name, description=identity.description,
        unit=identity.tpp_unit, fps_unit=identity.fps_unit if with_fps else None, flags=FLAG_KEYS,
        pairs=tuple(f"{identity.unit_base}/{stem[:-3]}" for stem in stems if stem.endswith("_df")),
        glove_adapter=identity.glove_adapter)








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
    told = registration(identity, textures, with_fps)
    (pack / "main.xml").write_text(lop.main_xml(told))
    (pack / "hooks" / f"{identity.item_id}_las.lua").write_text(lop.hook_lua(told))
    if identity.glove_adapter:
        (pack / "hooks" / f"{identity.item_id}_glove_adapter.lua").write_text(
            lop.render_glove_adapter_lua(identity.item_id, identity.pack_dir_name))
    (pack / "localization" / "english.txt").write_text(lop.localization(told))

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
        # False since 2026-11-13. It was True on the strength of the 2026-11-05 test of the base pack,
        # in both packs and through every later rebuild: no bytes this builder tracks were ever in
        # game. What a person saw, and of which bytes, is in docs/pd2-las/HANDOFF.md.
        "runtime_verified": False,
        "payload_sha256": payload,
    }
    info.update(extra)
    (pack / "BUILD_INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return pack


# ---------------------------------------------------------------------------
def _figures(report):
    """A fit report as it is written to a file: every number to six decimals.

    Written in full, the numbers carried the last bits of a least-squares fit
    into BUILD_INFO.json, and those bits belong to the CPU that ran it.
    """
    if isinstance(report, float):
        return round(float(report), 6)
    if isinstance(report, dict):
        return {key: _figures(value) for key, value in report.items()}
    if isinstance(report, (list, tuple)):
        return [_figures(value) for value in report]
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, default=bm.DEFAULT_TEMPLATES,
                    help="directory with 2b.model / fps_2b.model (from 2b.rar; "
                         "default: where recover_env.sh unpacks it, under "
                         "build/pd2-las/2b/)")
    ap.add_argument("--variant", choices=sorted(IDENTITIES), default="base",
                    # argparse %-formats help strings: a literal percent sign is "%%"
                    help="base = full body with hands; "
                         f"slim = {(1 - SLIM_SCALE):.0%}% thinner in x/y (arms an "
                         "extra 20%%), height unchanged, hands cut at the wrist "
                         "for in-game gloves (glove adapter hook shipped)")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "pd2-las")
    ap.add_argument("--dist", type=Path, default=REPO / "dist")
    ap.add_argument("--no-fps", dest="fps", action="store_false", default=True,
                    help="ship only the third-person unit (no fps viewmodel)")
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args(argv)
    determinism.enter(__file__)
    bm.require_templates(args.templates,
                         ("2b.model", "fps_2b.model") if args.fps else ("2b.model",))

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
    spike_report: list[dict] = []
    cuff_report: list[dict] = []
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
        cuffs = taper_cuff(groups[gname], template)
        if gname == "body":
            cuff_report = cuffs
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
            groups[gname] = drop_bare_arm_rings(groups[gname])  # no bare-arm ring in the adapter pack
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

    # Author the final body and shadow in the actual near-idle skinning pose.
    # This is deliberately after slim / hand cutting so every surviving vertex
    # and its final weights share one coherent rest bind; FPS extraction below
    # carries the same rest_worlds into the viewmodel.
    idle_rest: dict[str, dict] = {}
    stitch: dict[str, dict] = {}
    unified: dict[str, dict] = {}
    normals_left: dict[str, dict] = {}
    for gname in ("body", "shadow"):
        idle_rest[gname] = rebind_arms_at_idle(
            groups[gname], template, slim=args.variant == "slim")
        # Close the sleeve's cut edges while every vertex and weight is final:
        # the underarm slit (a 12 x 3 cm hole in the sheet) and the 4-vertex
        # elbow pinhole. Topology only — no vertex, UV or material is touched.
        stitch[gname] = stitch_sleeve_seams(groups[gname], template)
        print(f"[{gname}] sleeve stitch: {stitch[gname]['new_faces']} new tris, "
              f"{stitch[gname]['welded']} duplicate rims welded, "
              f"{stitch[gname]['filled']} hole(s) filled")
        for line in stitch[gname]["details"]:
            print(f"  {line}")
        # Seam shading: one normal per interior coincident group, exactly what
        # the 2B reference does (0 of its 22,486 pairs diverge). Borders keep
        # both normals - those copies are a garment fold, not a UV split.
        unified[gname] = unify_coincident_normals(groups[gname])
        normals_left[gname] = coincident_normal_report(groups[gname])
        print(f"[{gname}] seam normals: {unified[gname]['verts']} interior "
              f"copies unified over {unified[gname]['groups']} groups; "
              f"{normals_left[gname]['interior']} interior / "
              f"{normals_left[gname]['border']} border pair(s) still diverging")
        if normals_left[gname]["interior"]:
            raise SystemExit(
                f"[{gname}] {normals_left[gname]['interior']} interior "
                "coincident pairs still disagree on their normal")
        breaks = bm.orientation_breaks(groups[gname])
        agree = bm.winding_agreement(groups[gname].verts, groups[gname].faces,
                                     groups[gname].normals)
        print(f"[{gname}] after idle rebind: orientation breaks {breaks}, "
              f"winding agreement {agree:.1%}")
        if breaks or agree < 0.9:
            raise SystemExit(f"[{gname}] idle rebind broke the mesh")
        # The shipped geometry is the idle pose now, so this is the last - and
        # the only - place where a vertex can be judged in the pose the game
        # actually shows. Pull the authored elbow spikes back onto their ring.
        spikes = despike_elbows(groups[gname], template)
        if gname == "body":
            spike_report = spikes
        if gname == "shadow":
            # The caster duplicates the body mesh, so it has to lose the same
            # spikes: compare the vertex counts, not the shifts (the shadow
            # carries the same circle but tests its own, slightly different,
            # fan normals)
            if [s["verts"] for s in spikes] != [s["verts"] for s in spike_report]:
                raise SystemExit(
                    f"de-spike touched {[s['verts'] for s in spikes]} shadow "
                    f"verts but {[s['verts'] for s in spike_report]} body verts")

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
        "elbow_despike": spike_report,
        "cuff_taper": cuff_report,
        "idle_arm_rest": idle_rest,
        "sleeve_stitch": stitch,
        "seam_normals": {g: {"unified": unified[g], "left": normals_left[g]}
                         for g in unified},
        "fit_tpp": _figures(fit),
        "fit_fps": _figures(fps_fit) if fps_bytes is not None else None,
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
                             "fit_tpp": _figures(fit),
                             "fit_fps": _figures(fps_fit),
                             "centring": centring,
                             "elbow_trim": elbow_report,
                             "elbow_despike": spike_report,
                             "cuff_taper": cuff_report,
                             "idle_arm_rest": idle_rest,
                             "sleeve_stitch": stitch,
                             "seam_normals": {g: {"unified": unified[g],
                                                  "left": normals_left[g]}
                                              for g in unified}},
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
