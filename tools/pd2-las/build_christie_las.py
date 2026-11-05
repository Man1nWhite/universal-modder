#!/usr/bin/env python3
"""Build Christie LAS packs — body-only PAYDAY 2 LAS outfits from the DOA5 model.

Source: `references/Christie.zip` (Dead or Alive 5 Christie, costume c2:
`models/plasmid/doa5/christie_c2.{mdl,vvd,dx90.vtx,phy}` + VMT/VTF materials).
Outputs (in `dist/`):

- `Christie_LAS.zip`           — full body incl. Christie's own hands
- `Christie_LAS_No_hands.zip`  — same outfit with the hands cut at the wrist,
  so the heister's in-game gloves (changeable, via the glove adapter compat
  hook) show through the sleeves; `--variant nohands`
- `Christie_LAS_Slim.zip`      — 20% thinner in width/depth, height unchanged;
  `--variant slim`

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
  .venv/bin/python tools/pd2-las/build_christie_las.py --variant nohands \
      --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"            # no hands
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
import las_outfit_pack as lop  # noqa: E402
import preview as pv  # noqa: E402
import source_model as sm  # noqa: E402
from dds_encode import (  # noqa: E402
    attenuate_dxt5_alpha_from_normal,
    swizzle_source_normal_dxt5_to_pd2,
)
from vtf import parse_vtf, to_dds  # noqa: E402

SOURCE_ZIP = REPO / "references" / "Christie.zip"
SKEL_MAP = HERE / "christie_skeleton_map.json"

MDL_PATH = "models/plasmid/doa5/christie_c2.mdl"
VVD_PATH = "models/plasmid/doa5/christie_c2.vvd"
VTX_PATH = "models/plasmid/doa5/christie_c2.dx90.vtx"
MAT_DIR = "materials/models/plasmid/doa5/christie/c2/"

HOOK_SOURCE = "lib/tweak_data/armorskinstweakdata"
GLOVE_HOOK_SOURCE = "lib/tweak_data/blackmarkettweakdata"

#: Horizontal (X/Y) scale for the slim variant; Z (height) is left untouched.
SLIM_SCALE = 0.8


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
    "nohands": Identity(
        item_id="christie_no_hands",
        pack_dir_name="Christie_LAS_No_hands",
        display_name="Christie (DOA5, no hands)",
        description=("Christie from Dead or Alive 5, body-only LAS outfit with "
                     "the hands cut at the wrist so the in-game gloves show "
                     "through the sleeves. No head — the heister keeps their "
                     "own."),
        glove_adapter=True,
    ),
    "slim": Identity(
        item_id="christie_slim",
        pack_dir_name="Christie_LAS_Slim",
        display_name="Christie (DOA5, slim)",
        description=("Christie from Dead or Alive 5, body-only LAS outfit scaled "
                     f"{SLIM_SCALE:.0%} thinner in width and depth (height "
                     "unchanged). No head — the heister keeps their own."),
        glove_adapter=False,
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


def convert_textures(zf: zipfile.ZipFile, identity: Identity) -> dict[str, bytes]:
    """VTF -> Diesel .texture payloads, keyed by pack stem (<id>_<role>_df.texture).

    Diffuse alpha is attenuated from the normal map's alpha (Source phong mask)
    so PD2 doesn't read full mirror gloss; the normal map itself is swizzled
    for Diesel (Y flipped).
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
        textures[f"{identity.texture_prefix}_{role}_df.texture"] = df_dds
        textures[f"{identity.texture_prefix}_{role}_nm.texture"] = nm_dds
    return textures


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
# slim variant: 20% thinner in X/Y, height (Z) untouched
# ---------------------------------------------------------------------------
def slim_group(g: bm.Group, scale: float = SLIM_SCALE) -> bm.Group:
    """Scale the group horizontally about its own vertical axis.

    x/y shrink by `scale` around the mesh's XY centroid (so the outfit stays
    centered on the skeleton axis), z is untouched — height preserved. Normals
    are transformed by the inverse-transpose of diag(s, s, 1) and renormalized,
    so shading follows the thinner silhouette instead of staying spherical.
    """
    import numpy as np

    v = np.array(g.verts, dtype=np.float64)
    c = v.mean(axis=0)
    v[:, 0] = c[0] + (v[:, 0] - c[0]) * scale
    v[:, 1] = c[1] + (v[:, 1] - c[1]) * scale
    n = np.array(g.normals, dtype=np.float64)
    n[:, 0] /= scale
    n[:, 1] /= scale
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    g.verts = [tuple(row) for row in v]
    g.normals = [tuple(row) for row in n]
    print(f"[{g.name}] slim x{scale}: x {np.ptp(v[:, 0]):.1f} cm, "
          f"y {np.ptp(v[:, 1]):.1f} cm, z {np.ptp(v[:, 2]):.1f} cm "
          f"(z unchanged: {np.allclose(v[:, 2], np.array([p[2] for p in g.verts]))})")
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
                    help="base = full body with hands; nohands = hands cut at the "
                         "wrist for in-game gloves (glove adapter hook shipped); "
                         f"slim = {SLIM_SCALE:.0%} thinner in x/y, height unchanged")
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

    kept = {m.material for m in model.meshes if m.material in KEEP_MATERIALS}
    dropped = sorted({m.material for m in model.meshes} - kept)
    print(f"[{identity.pack_dir_name}] source: {model.name}: {len(model.bones)} bones, "
          f"{len(model.vertices)} verts, {model.triangle_count} tris, "
          f"{len(model.meshes)} meshes")
    print(f"  kept materials: {sorted(kept)}")
    print(f"  dropped (head) materials: {dropped}")

    skel_map = json.loads(SKEL_MAP.read_text())
    template = bm.load_template(args.templates / "2b.model")
    fits = bm.retarget_maps(model, skel_map, template)
    print(f"retarget: {len(fits)} bone transforms")

    groups: dict[str, bm.Group] = {}
    share: dict[str, str] = {}
    for gname, spec in TPP_GROUPS.items():
        g = bm.transfer_group(model, spec, skel_map, template, gname, fits=fits)
        print(f"group {gname}: {len(g.verts)} verts, {len(g.faces)} tris, "
              f"palette {len(g.palette)}, slots {sorted(set(g.mat_slots))}")
        if not g.verts:
            raise SystemExit(f"group {gname} is empty")
        groups[gname] = g
        for drawable in spec["drawables"]:
            share[drawable] = gname

    if args.variant == "slim":
        # Thinner in width/depth only; height (z) and the skeleton untouched.
        # Applied before the fps extraction so the viewmodel arms match.
        for gname in ("body", "shadow"):
            slim_group(groups[gname])
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
                mats={"cri_body_base": -2.2, "cri_02_01_base": -2.5,
                      "cri_02_02_base": -2.0})
            print(f"[{gname}] sleeves reach the glove: {rep['moved']} verts "
                  f"{rep['materials']} (was -> target: {rep['reaches']})")
            breaks = bm.orientation_breaks(groups[gname])
            agree = bm.winding_agreement(groups[gname].verts, groups[gname].faces,
                                         groups[gname].normals)
            print(f"[{gname}] after cut: orientation breaks {breaks}, "
                  f"winding agreement {agree:.1%}")
            if breaks or agree < 0.9:
                raise SystemExit(f"[{gname}] hand cut broke the mesh")

    tpp = bm.assemble_model(template, groups, share, drop_drawables=DROP_DRAWABLES)
    tpp_path = args.out / f"{identity.item_id}.model"
    tpp_path.parent.mkdir(parents=True, exist_ok=True)
    tpp_path.write_bytes(tpp.write())
    print(f"wrote {tpp_path} ({tpp_path.stat().st_size} bytes)")
    problems = bm.audit_model(tpp_path)
    if problems:
        raise SystemExit("tpp render atoms do not tile the mesh:\n  "
                         + "\n  ".join(problems))

    fps_bytes = None
    fps_slots: list[str] | None = None
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
    }
    (args.out / f"{identity.item_id}_report.json").write_text(
        json.dumps(report, indent=2) + "\n")

    args.dist.mkdir(parents=True, exist_ok=True)
    pack = write_pack(args.dist, identity, tpp_path.read_bytes(), fps_bytes,
                      textures, icon, source_sha,
                      extra={"build_report": f"build/pd2-las/{identity.item_id}_report.json"},
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
