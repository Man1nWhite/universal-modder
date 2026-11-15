#!/usr/bin/env python3
"""Build `Honoko2` — the DOAXVV Honoka "Secret Report" outfit from `.dae` as a PD2 LAS pack.

Unlike the earlier TMC-only build (deleted 2026-11-15, D40), which merged the raw
`.TMC` meshes into 3 material slots and overlaid the unbuttoned `WGT_cap2` jacket
on top of the buttoned `WGT_headdress2` suit, this driver builds from the Collada
export `references/Honoka/Honoka_DOAXVV_Secret_Reportout.dae`:

* **Clean garment selection + per-submesh materials** — uses the complete
  buttoned suit + skirt (`WGT_headdress2_0..5`) together with all body, bra,
  high-heel, and gold-jewelry submeshes (`WGT_new_aya_body_1..8`), avoiding the
  overlapping `WGT_cap2` shell that z-fights on the torso and back.
* **6 proper material slots** parsed from the `.dae` bindings and paired with
  their source normal maps (`references/Honoka/L_*.dds`):
  - `honoko2_body`: `L_3.dds` / `L_4.dds`
  - `honoko2_suit`: `L_7.dds` / `L_8.dds`
  - `honoko2_panties`: `L_14.dds` / `L_15.dds`
  - `honoko2_bra`: `L_17.dds` / `L_18.dds`
  - `honoko2_shoes`: `L_20.dds` / `L_21.dds`
  - `honoko2_jewelry`: `L_23.dds` / `L_24.dds`
* **Skinning transfer from `.TMC`** — the Noesis `.dae` export omits
  `<library_controllers>`, while every `.dae` vertex matches its corresponding
  vertex in `Honoka_DOAXVV_Secret_Report.TMC` to ~0.0001 cm. Exact 4-weight +
  palette-remapped influences are transferred from the TMC, then retargeted onto
  the 2B PD2 skeleton via `tmc_skeleton_map.json` + `build_models.retarget_maps`.
* **Third-person BODY_ONLY LAS pack (`LegendaryArmours.honoko2`)** — cuts hands
  at the PD2 wrists for heister gloves (`honoko2_glove_adapter.lua`), drops any
  long-thin connector triangles, and writes deterministic `dist/Honoko2.zip` +
  `dist/Honoko2.zip.sha256`.

`runtime_verified` stays `false` everywhere; nothing here has been run in
PAYDAY 2.

Usage:
  make -sC tools/pd2-las env
  .venv/bin/python tools/pd2-las/build_honoko2_dae.py
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import determinism  # noqa: E402
import extract_2b  # noqa: E402

DEFAULT_TEMPLATES = extract_2b.TEMPLATES
DEFAULT_OUT = REPO / "dist"
DEFAULT_WORK = REPO / "build" / "honoko2"
DAE_PATH = REPO / "references" / "Honoka" / "Honoka_DOAXVV_Secret_Reportout.dae"
SOURCE_ZIP = REPO / "references" / "Outfit for Honoka-109-1-1-1628020933.zip"
TMC_NAME = "Honoka_DOAXVV_Secret_Report.TMC"
TEX_DIR = REPO / "references" / "Honoka"

ITEM_ID = "honoko2"
PACK_DIR_NAME = "Honoko2"
UNIT_BASE = f"units/{ITEM_ID}/skins/{ITEM_ID}"
GUI_BASE = f"guis/dlcs/{ITEM_ID}/armor_skins"
TPP_UNIT = f"{UNIT_BASE}/{ITEM_ID}"
DISPLAY_NAME = "Honoka (Secret Report DAE)"
DESCRIPTION = (
    "Honoka in the DOAXVV 'Secret Report' formal outfit (built from Collada .dae "
    "with full per-part materials). Legendary Armour Skins BODY_ONLY outfit."
)

# Material slots sorted deterministically; every DAE submesh maps to one slot.
MAT_TEXTURES = {
    "honoko2_body": ("L_3.dds", "L_4.dds"),
    "honoko2_suit": ("L_7.dds", "L_8.dds"),
    "honoko2_panties": ("L_14.dds", "L_15.dds"),
    "honoko2_bra": ("L_17.dds", "L_18.dds"),
    "honoko2_shoes": ("L_20.dds", "L_21.dds"),
    "honoko2_jewelry": ("L_23.dds", "L_24.dds"),
}

# Submeshes kept from Honoka_DOAXVV_Secret_Reportout.dae -> (TMC parent mesh, out slot).
# Expected DAE texture filenames are verified against the XML scene bindings.
SUBMESH_SPEC = {
    "WGT_new_aya_body_1": ("WGT_new_aya_body_decl0", "honoko2_body", "L_3.dds"),
    "WGT_new_aya_body_2": ("WGT_new_aya_body_decl0", "honoko2_jewelry", "L_23.dds"),
    "WGT_new_aya_body_3": ("WGT_new_aya_body_decl0", "honoko2_shoes", "L_20.dds"),
    "WGT_new_aya_body_4": ("WGT_new_aya_body_decl0", "honoko2_jewelry", "L_23.dds"),
    "WGT_new_aya_body_5": ("WGT_new_aya_body_decl0", "honoko2_jewelry", "L_23.dds"),
    "WGT_new_aya_body_6": ("WGT_new_aya_body_decl0", "honoko2_jewelry", "L_23.dds"),
    "WGT_new_aya_body_7": ("WGT_new_aya_body_decl0", "honoko2_jewelry", "L_23.dds"),
    "WGT_new_aya_body_8": ("WGT_new_aya_body_decl0", "honoko2_bra", "L_17.dds"),
    "WGT_headdress2_0": ("WGT_headdress2", "honoko2_suit", "L_7.dds"),
    "WGT_headdress2_1": ("WGT_headdress2", "honoko2_suit", "L_7.dds"),
    "WGT_headdress2_2": ("WGT_headdress2", "honoko2_suit", "L_7.dds"),
    "WGT_headdress2_3": ("WGT_headdress2", "honoko2_suit", "L_7.dds"),
    "WGT_headdress2_4": ("WGT_headdress2", "honoko2_suit", "L_7.dds"),
    "WGT_headdress2_5": ("WGT_headdress2", "honoko2_panties", "L_14.dds"),
}

EXCLUDED_DAE = {
    "WGT_cap2_0..3": "unbuttoned jacket overlay (z-fights with buttoned WGT_headdress2 suit)",
    "WGT_new_aya_body_0": "280-vertex uniform-weight debug slab (decl1)",
    "WGT_sweat_chest_0": "chest emblem decal",
}


def _parse_dae_submeshes(dae_path: Path) -> list[dict]:
    """Parse geometry submeshes and material->DDS bindings from Collada XML."""
    ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
    root = ET.parse(dae_path).getroot()

    eff_img = {
        e.attrib["id"]: e.find(".//c:init_from", ns).text
        for e in root.findall(".//c:library_effects/c:effect", ns)
    }
    img_file = {
        im.attrib["id"]: urllib.parse.unquote(im.find("c:init_from", ns).text.split("/")[-1])
        for im in root.findall(".//c:library_images/c:image", ns)
    }
    mat_dds = {}
    for m in root.findall(".//c:library_materials/c:material", ns):
        eid = m.find("c:instance_effect", ns).attrib["url"].lstrip("#")
        fn = img_file[eff_img[eid]]
        dds = fn.split("(")[1].split(")")[0] + ".dds" if "(" in fn and ")" in fn else fn
        mat_dds[m.attrib["id"]] = dds

    geom_dds = {}
    for node in root.findall(".//c:library_visual_scenes//c:node", ns):
        ig = node.find("c:instance_geometry", ns)
        if ig is None:
            continue
        gid = ig.attrib["url"].lstrip("#")
        tgt = ig.find(".//c:instance_material", ns).attrib["target"].lstrip("#")
        geom_dds[gid] = mat_dds[tgt]

    import numpy as np

    out = []
    for g in root.findall(".//c:library_geometries/c:geometry", ns):
        gname = g.attrib.get("name", g.attrib["id"])
        if gname not in SUBMESH_SPEC:
            continue
        mesh = g.find("c:mesh", ns)
        tris_el = mesh.find("c:triangles", ns)
        srcs = {
            s.attrib["id"]: np.fromstring(s.find("c:float_array", ns).text, sep=" ")
            for s in mesh.findall("c:source", ns)
        }
        vinp = {
            i.attrib["semantic"]: i.attrib["source"].lstrip("#")
            for i in mesh.find("c:vertices", ns).findall("c:input", ns)
        }
        pos = srcs[vinp["POSITION"]].reshape(-1, 3)
        nrm = srcs[vinp["NORMAL"]].reshape(-1, 3)
        uv = srcs[vinp["TEXCOORD"]].reshape(-1, 2)
        tris = np.fromstring(tris_el.find("c:p", ns).text, sep=" ", dtype=np.int64).reshape(-1, 3)
        out.append({
            "name": gname,
            "dds": geom_dds[g.attrib["id"]],
            "pos_m": pos,
            "nrm": nrm,
            "uv": uv,
            "tris": tris,
        })
    return out


def _build_tmc_lookup(mesh):
    """Build quantized (0.1 mm) lookup table + raw arrays for fast vertex skin transfer."""
    import numpy as np

    pos_m = np.asarray(mesh.positions, dtype=np.float64) / 100.0
    pal = np.asarray(mesh.palette, dtype=np.int64) if mesh.palette is not None else None
    gidx = np.asarray(mesh.bone_indices, dtype=np.int64)
    if pal is not None:
        gidx = pal[gidx]
    wgt = np.asarray(mesh.weights, dtype=np.float64)

    table: dict[tuple[int, int, int], int] = {}
    q = np.rint(pos_m * 10000.0).astype(np.int64)
    for i in range(len(pos_m)):
        key = (int(q[i, 0]), int(q[i, 1]), int(q[i, 2]))
        if key not in table:
            table[key] = i
    return pos_m, gidx, wgt, table


def _match_skin_indices(pos_m, tmc_lookup) -> tuple[list[int], float]:
    import numpy as np

    ref_pos, _, _, table = tmc_lookup
    q = np.rint(pos_m * 10000.0).astype(np.int64)
    matched = [-1] * len(pos_m)
    miss = []
    for i in range(len(pos_m)):
        hit = table.get((int(q[i, 0]), int(q[i, 1]), int(q[i, 2])))
        if hit is not None:
            matched[i] = hit
        else:
            miss.append(i)
    max_err = 0.0
    if miss:
        sub = pos_m[miss]
        for start in range(0, len(sub), 256):
            chunk = sub[start : start + 256]
            d2 = ((chunk[:, None, :] - ref_pos[None, :, :]) ** 2).sum(axis=2)
            idx = np.argmin(d2, axis=1)
            err = float(np.sqrt(d2[np.arange(len(chunk)), idx]).max())
            max_err = max(max_err, err)
            for k, orig_i in enumerate(miss[start : start + 256]):
                matched[orig_i] = int(idx[k])
    if max_err > 1e-4:
        raise ValueError(f"DAE->TMC vertex match exceeded 0.1 mm: max_err={max_err:.6f} m")
    return matched, max_err


def _scale_leg_fits_to_floor(fits: dict, model, skel_map: dict, template, target_z: float = -0.47) -> float:
    """Scale leg retarget fits about each hip joint so the heels stand on `target_z`."""
    import numpy as np

    import diesel_model as dm

    # Find lowest vertex in honoko2_shoes after initial retargeting
    shoe_sub = next(m for m in model.meshes if m.material == "honoko2_shoes")
    shoe_vi = sorted({i for i in shoe_sub.triangle_indices})
    z_min = float("inf")
    for vi in shoe_vi:
        v = model.vertices[vi]
        p = np.zeros(3, dtype=np.float64)
        wsum = 0.0
        for b_idx, w in v.weights:
            if b_idx in fits:
                p += w * np.array(dm.mat_apply_point(fits[b_idx], v.pos), dtype=np.float64)
                wsum += w
        if wsum > 0:
            p /= wsum
            if p[2] < z_min:
                z_min = float(p[2])

    hip_l = np.array(template.worlds[template.name_id["LeftUpLeg"]][12:15], dtype=np.float64)
    z_hip = float(hip_l[2])
    k = (z_hip - target_z) / max(1e-6, z_hip - z_min)

    for side in ("Left", "Right"):
        anchor = np.array(template.worlds[template.name_id[f"{side}UpLeg"]][12:15], dtype=np.float64)
        s_mat = np.eye(4, dtype=np.float64)
        s_mat[:3, :3] = k * np.eye(3, dtype=np.float64)
        s_mat[3, :3] = (1.0 - k) * anchor
        scaled_legs: set[int] = set()
        for tname in (f"{side}UpLeg", f"{side}Leg", f"{side}Foot", f"{side}ToeBase"):
            for bi, bone in enumerate(model.bones):
                if skel_map["map"].get(bone.name) == tname and bi in fits and bi not in scaled_legs:
                    fits[bi] = dm.mat_mul(fits[bi], tuple(float(x) for x in s_mat.reshape(-1)))
                    scaled_legs.add(bi)
    return k


def _cap_wrist_cuts(g, arm_joints, margin: float = 0.5) -> int:
    """Cap open wrist-cut rims on `honoko2_body` inside its slice block."""
    import numpy as np

    if not g.slices or g.slices[0][0] != "honoko2_body":
        return 0
    src_mat, base_v, base_i, tri_count, nverts = g.slices[0]
    verts = np.asarray(g.verts, dtype=np.float64)
    sl_faces = np.asarray(g.faces[:tri_count], dtype=np.int64)

    # Directed edges used by exactly one triangle on honoko2_body slice
    counts: dict[tuple[int, int], int] = {}
    directed: list[tuple[int, int]] = []
    for a, b, c in sl_faces:
        for x, y in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            key = (x, y) if x < y else (y, x)
            counts[key] = counts.get(key, 0) + 1
            directed.append((x, y))
    bedges = [(x, y) for (x, y) in directed if counts[(x, y) if x < y else (y, x)] == 1]
    if not bedges:
        return 0

    wrist_l, elbow_l = (np.array(v, dtype=np.float64) for v in arm_joints[-1])
    wrist_r, elbow_r = (np.array(v, dtype=np.float64) for v in arm_joints[1])

    added_verts = []
    added_normals = []
    added_uvs = []
    added_weights = []
    added_faces = []

    for wrist, elbow in ((wrist_l, elbow_l), (wrist_r, elbow_r)):
        axis = wrist - elbow
        axis /= np.linalg.norm(axis)
        rim_edges = []
        for x, y in bedges:
            mid = 0.5 * (verts[x] + verts[y])
            rel = mid - wrist
            t = float(rel @ axis)
            perp = float(np.linalg.norm(rel - t * axis))
            if -1.5 <= t <= margin + 0.5 and perp < 10.0:
                rim_edges.append((x, y))
        if len(rim_edges) < 4:
            continue
        ring_idx = sorted({v for e in rim_edges for v in e})
        ctr = verts[ring_idx].mean(axis=0)
        c_idx = base_v + nverts + len(added_verts)
        added_verts.append((float(ctr[0]), float(ctr[1]), float(ctr[2])))
        added_normals.append((float(axis[0]), float(axis[1]), float(axis[2])))
        added_uvs.append(tuple(g.uvs[ring_idx[0]]))
        w_acc: dict[int, float] = {}
        for vi in ring_idx:
            for bi, w in g.weights[vi]:
                w_acc[bi] = w_acc.get(bi, 0.0) + w / len(ring_idx)
        top_w = sorted(w_acc.items(), key=lambda kv: kv[1], reverse=True)[:4]
        ws = sum(w for _, w in top_w) or 1.0
        added_weights.append([(bi, w / ws) for bi, w in top_w])

        # Fan every directed boundary edge in opposite orientation (y, x, c_idx)
        for x, y in rim_edges:
            added_faces.append((y, x, c_idx))

    if not added_verts:
        return 0

    nv = len(added_verts)
    nf = len(added_faces)
    # Insert cap verts at end of slice 0 vertex block and shift later slices/faces
    ins_v = base_v + nverts
    g.verts = g.verts[:ins_v] + added_verts + g.verts[ins_v:]
    g.normals = g.normals[:ins_v] + added_normals + g.normals[ins_v:]
    g.uvs = g.uvs[:ins_v] + added_uvs + g.uvs[ins_v:]
    g.weights = g.weights[:ins_v] + added_weights + g.weights[ins_v:]

    shifted_tail = [tuple(vi + nv if vi >= ins_v else vi for vi in f) for f in g.faces[tri_count:]]
    g.faces = list(g.faces[:tri_count]) + added_faces + shifted_tail

    new_slices = [(src_mat, base_v, base_i, tri_count + nf, nverts + nv)]
    for (m, bv, bi, tc, nl) in g.slices[1:]:
        new_slices.append((m, bv + nv, bi + nf * 3, tc, nl))
    g.slices = new_slices
    return nf


def dae_to_model_data(dae_submeshes: list[dict], tmc):
    """Build a `source_model.ModelData` from `.dae` geometry + `.TMC` skin weights."""
    import tmc_las
    from source_model import Bone, ModelData, SkinVertex, SubMesh

    M = tmc_las.basis_matrix()
    model = ModelData(name="honoko2_dae")
    for i, name in enumerate(tmc.node_names):
        model.bones.append(
            Bone(name=name, parent=int(tmc.hie_parent[i]), pos=(0.0, 0.0, 0.0), quat=(0.0, 0.0, 0.0, 1.0))
        )

    tmc_by_name = {m.source_id: _build_tmc_lookup(m) for m in tmc.load_meshes()}

    # Merge DAE submeshes by target material slot in deterministic MAT_TEXTURES order
    slot_verts: dict[str, list] = {slot: [] for slot in MAT_TEXTURES}
    slot_tris: dict[str, list] = {slot: [] for slot in MAT_TEXTURES}
    max_match_err = 0.0

    for sub in dae_submeshes:
        tmc_name, slot, want_dds = SUBMESH_SPEC[sub["name"]]
        if sub["dds"] != want_dds:
            raise ValueError(f"{sub['name']}: DAE texture {sub['dds']} != expected {want_dds}")
        lookup = tmc_by_name[tmc_name]
        _, gidx, wgt, _ = lookup
        matched, err = _match_skin_indices(sub["pos_m"], lookup)
        max_match_err = max(max_match_err, err)

        pos_d = (sub["pos_m"] * 100.0) @ M.T
        nrm_d = sub["nrm"] @ M.T
        uv = sub["uv"]
        vbase = len(slot_verts[slot])
        for n in range(len(pos_d)):
            ti = matched[n]
            infl = tuple(
                (int(gidx[ti, k]), float(wgt[ti, k]))
                for k in range(4)
                if wgt[ti, k] > 1e-6
            )
            slot_verts[slot].append(
                SkinVertex(
                    pos=(float(pos_d[n, 0]), float(pos_d[n, 1]), float(pos_d[n, 2])),
                    normal=(float(nrm_d[n, 0]), float(nrm_d[n, 1]), float(nrm_d[n, 2])),
                    uv=(float(uv[n, 0]), float(uv[n, 1])),
                    weights=infl,
                )
            )
        slot_tris[slot].extend(int(i) + vbase for i in sub["tris"].reshape(-1))

    for slot in MAT_TEXTURES:
        v0 = len(model.vertices)
        model.vertices.extend(slot_verts[slot])
        model.meshes.append(
            SubMesh(material=slot, triangle_indices=tuple(i + v0 for i in slot_tris[slot]))
        )
    return model, max_match_err


def _reduce_half(arr):
    h, w = arr.shape[:2]
    fh = 2 if h > 1 else 1
    fw = 2 if w > 1 else 1
    return arr.reshape(h // fh, fh, w // fw, fw, -1).mean(axis=(1, 3))


def _full_mip_levels(image, colour: bool) -> list:
    """All mip levels of RGBA `image` down to 1x1, supporting rectangular dims."""
    import numpy as np

    from dds_encode import linear_to_srgb, srgb_to_linear

    image = np.asarray(image, dtype=np.uint8)
    levels = [image]
    if colour:
        light = srgb_to_linear(image[..., :3] / 255.0)
        alpha = image[..., 3].astype(np.float64)
        while max(light.shape[:2]) > 1:
            light = _reduce_half(light)
            alpha = _reduce_half(alpha[..., None])[..., 0]
            rgb = np.clip(linear_to_srgb(light) * 255.0, 0.0, 255.0)
            levels.append(np.dstack([rgb, alpha]).round().astype(np.uint8))
    else:
        cur = image.astype(np.float64)
        while max(cur.shape[:2]) > 1:
            cur = _reduce_half(cur)
            levels.append(np.clip(cur, 0.0, 255.0).round().astype(np.uint8))
    return levels


def build_textures() -> tuple[dict[str, bytes], dict]:
    """Decode all 6 diffuse+normal DDS pairs into PD2 BC3 `.texture`s with full mips."""
    import hashlib as _hl

    import numpy as np
    from PIL import Image

    import dds_encode

    textures: dict[str, bytes] = {}
    report: dict[str, dict] = {}
    for slot, (df_dds, nm_dds) in sorted(MAT_TEXTURES.items()):
        for kind, dds_name in (("df", df_dds), ("nm", nm_dds)):
            stem = f"{slot}_{kind}"
            src_bytes = (TEX_DIR / dds_name).read_bytes()
            pil_im = Image.open(io.BytesIO(src_bytes)).convert("RGBA")
            if pil_im.width != pil_im.height:
                sq = min(pil_im.width, pil_im.height, 512) if kind == "nm" else min(max(pil_im.width, pil_im.height), 512)
                pil_im = pil_im.resize((sq, sq), Image.Resampling.LANCZOS)
            im = np.asarray(pil_im, dtype=np.uint8)
            if kind == "df":
                alpha = np.full(im.shape[:2], 20, dtype=np.uint8)
                img = np.dstack([im[..., :3], alpha]).astype(np.uint8)
                levels = _full_mip_levels(img, colour=True)
            else:
                x = im[..., 0].astype(np.int16)
                y = 255 - im[..., 1].astype(np.int16)
                img = np.dstack([
                    np.full(im.shape[:2], 255, np.uint8),
                    np.clip(y, 0, 255).astype(np.uint8),
                    np.zeros(im.shape[:2], np.uint8),
                    x.astype(np.uint8),
                ])
                levels = _full_mip_levels(img, colour=False)
            textures[f"{stem}.texture"] = dds_encode.bc3_dds_from_levels(levels)
            report[stem] = {
                "source": f"references/Honoka/{dds_name}",
                "source_sha256": _hl.sha256(src_bytes).hexdigest(),
                "size": list(im.shape[:2]),
                "mips": len(levels),
                "out_sha256": _hl.sha256(textures[f"{stem}.texture"]).hexdigest(),
            }
    return textures, report


def render_material_config() -> str:
    def contour_mat(slot: str) -> str:
        return (
            f'    <material name="{slot}" unique="true" version="2"\n'
            '              render_template="generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS">\n'
            f'        <diffuse_texture file="{UNIT_BASE}/{slot}_df"/>\n'
            f'        <bump_normal_texture file="{UNIT_BASE}/{slot}_nm"/>\n'
            '        <variable value="1 1 1" type="vector3" name="contour_color"/>\n'
            '        <variable value="0" type="scalar" name="contour_opacity"/>\n'
            "    </material>\n"
        )

    parts = [f'<materials version="3" group="{ITEM_ID}">\n\n']
    for slot in MAT_TEXTURES:
        parts.append(contour_mat(slot) + "\n")
    parts.append('    <material name="shadow_caster" render_template="shadow_caster_only:SKINNED_1WEIGHT" version="2"/>\n')
    parts.append("</materials>")
    return "".join(parts)


def registration():
    import las_outfit_pack as lop

    return lop.Registration(
        item_id=ITEM_ID,
        display_name=DISPLAY_NAME,
        description=DESCRIPTION,
        unit=TPP_UNIT,
        flags=lop.BODY_ONLY,
        fps_unit=None,
        category=ITEM_ID,
        icon=f"{GUI_BASE}/{ITEM_ID}",
        hook_file=f"{ITEM_ID}_las.lua",
        pairs=tuple(f"{UNIT_BASE}/{slot}" for slot in MAT_TEXTURES),
        textures=(),
        glove_adapter=True,
    )


def _render_icon_bytes(model_path: Path, textures: dict[str, bytes]) -> bytes:
    import numpy as np
    from PIL import Image

    import las_outfit_pack as lop
    import preview_textured as pt

    mesh_list = pt.material_meshes(model_path)
    tex_by_mat = {}
    for slot in MAT_TEXTURES:
        data = textures[f"{slot}_df.texture"]
        tex_by_mat[slot] = np.asarray(Image.open(io.BytesIO(data)).convert("RGBA"), dtype=np.float32) / 255.0

    size = 256
    imgs = [
        pt.render(mesh_list, tex_by_mat, view, size, 1.18, np.array([0.0, 2.0, 97.0]), flip_v=True, cull=True)
        for view in ("front", "side", "back", "threequarter")
    ]
    sheet = Image.new("RGB", (4 * size, size))
    for i, img in enumerate(imgs):
        sheet.paste(img, (i * size, 0))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return lop.build_icon(buf.getvalue(), view=3)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES,
                    help="directory containing 2b.model (default: where extract_2b.py unpacks it)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="directory for Honoko2.zip + .sha256 (default: dist)")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK,
                    help="working directory for intermediate model/pack tree (default: build/honoko2)")
    ap.add_argument("--dae", type=Path, default=DAE_PATH)
    ap.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    ap.add_argument("--no-previews", action="store_true",
                    help="skip the 3D render used to generate the HUD icon")
    args = ap.parse_args(argv)
    determinism.enter(__file__)

    import hashlib as _hl

    import tmc_las
    import build_models as bm
    import las_outfit_pack as lop
    import tmc as tmc_mod

    require = args.templates / "2b.model"
    if not require.is_file():
        raise SystemExit(f"{require} missing: {extract_2b.MISSING}")
    if not args.dae.is_file():
        raise SystemExit(f"missing Collada input: {args.dae}")
    if not args.source_zip.is_file():
        raise SystemExit(f"missing TMC archive: {args.source_zip}")
    template = bm.load_template(require)

    dae_bytes = args.dae.read_bytes()
    dae_sha = _hl.sha256(dae_bytes).hexdigest()
    zip_sha = _hl.sha256(args.source_zip.read_bytes()).hexdigest()

    with tempfile.TemporaryDirectory(prefix="honoko2_tmc_") as td:
        with zipfile.ZipFile(args.source_zip) as zf:
            tmc_bytes = zf.read(TMC_NAME)
        tmc_sha = _hl.sha256(tmc_bytes).hexdigest()
        tmc_path = Path(td) / TMC_NAME
        tmc_path.write_bytes(tmc_bytes)
        tmc = tmc_mod.TmcFile(str(tmc_path))
        src_worlds = tmc_las.glbl_to_diesel(tmc.global_raw)
        dae_subs = _parse_dae_submeshes(args.dae)
        model, max_match_err = dae_to_model_data(dae_subs, tmc)

    skel_map = json.loads((HERE / "tmc_skeleton_map.json").read_text())
    fits = bm.retarget_maps(model, skel_map, template, src_worlds=src_worlds)
    leg_floor_scale = _scale_leg_fits_to_floor(fits, model, skel_map, template, target_z=-0.47)

    slots = list(MAT_TEXTURES)
    specs = {
        "outfit": {
            "drawables": ["g_body", "g_body_lod1"],
            "materials": slots,
            "out_materials": slots,
            "mat_slots": {s: s for s in slots},
        },
        "shadow": {
            "drawables": ["s_body"],
            "materials": slots,
            "out_materials": ["shadow_caster"],
        },
    }

    groups = {}
    share = {}
    cut_report = {}
    for gname, spec in specs.items():
        g = bm.transfer_group(model, spec, skel_map, template, gname, fits=fits, swap_winding=False)
        cut = tmc_las.cut_group_at_wrists(g, bm.ARM_JOINTS)
        thin = tmc_las.drop_long_thin_triangles(g)
        cap_tris = _cap_wrist_cuts(g, bm.ARM_JOINTS)
        cut["long_thin"] = thin
        cut["wrist_cap_tris"] = cap_tris
        cut["leg_floor_scale"] = leg_floor_scale
        cut_report[gname] = cut
        groups[gname] = g
        for d in spec["drawables"]:
            share[d] = gname

    tpp_mf = bm.assemble_model(template, groups, share, drop_drawables=("g_head", "g_head_lod1"))

    args.work_dir.mkdir(parents=True, exist_ok=True)
    tpp_path = args.work_dir / f"{ITEM_ID}.model"
    tpp_path.write_bytes(tpp_mf.write())

    textures, tex_report = build_textures()
    reg = registration()

    pack = args.work_dir / PACK_DIR_NAME
    if pack.exists():
        shutil.rmtree(pack)
    unit_dir = pack / "assets" / UNIT_BASE
    gui_dir = pack / "assets" / GUI_BASE
    (pack / "hooks").mkdir(parents=True)
    (pack / "localization").mkdir(parents=True)
    unit_dir.mkdir(parents=True)
    gui_dir.mkdir(parents=True)

    (pack / "main.xml").write_bytes(lop.main_xml(reg).encode("utf-8"))
    (pack / "hooks" / f"{ITEM_ID}_las.lua").write_bytes(lop.hook_lua(reg).encode("utf-8"))
    (pack / "hooks" / f"{ITEM_ID}_glove_adapter.lua").write_bytes(
        lop.render_glove_adapter_lua(ITEM_ID, DISPLAY_NAME).encode("utf-8")
    )
    (pack / "localization" / "english.txt").write_bytes(lop.localization(reg).encode("utf-8"))

    if not args.no_previews:
        icon = _render_icon_bytes(tpp_path, textures)
    else:
        icon = tmc_las.fallback_icon()
    (gui_dir / f"{ITEM_ID}.texture").write_bytes(icon)
    for name, data in sorted(textures.items()):
        (unit_dir / name).write_bytes(data)

    (unit_dir / f"{ITEM_ID}.model").write_bytes(tpp_path.read_bytes())
    (unit_dir / f"{ITEM_ID}.unit").write_bytes(lop.render_unit_xml(TPP_UNIT).encode("utf-8"))
    drawables = lop.model_drawables(tpp_path.read_bytes())
    (unit_dir / f"{ITEM_ID}.object").write_bytes(lop.render_object_xml(TPP_UNIT, drawables).encode("utf-8"))
    (unit_dir / f"{ITEM_ID}.material_config").write_bytes(render_material_config().encode("utf-8"))

    payload = {
        path.relative_to(pack).as_posix(): _hl.sha256(path.read_bytes()).hexdigest()
        for path in sorted(pack.rglob("*"))
        if path.is_file()
    }
    build_info = {
        "pack": PACK_DIR_NAME,
        "item_id": ITEM_ID,
        "registration": {
            "hook_source": lop.HOOK_SOURCE,
            "table": f"LegendaryArmours.{ITEM_ID}",
            "flags": list(lop.BODY_ONLY),
            "unit": TPP_UNIT,
            "fps_unit": None,
            "glove_adapter": True,
        },
        "models_present": True,
        "runtime_verified": False,
        "source": {
            "dae": str(args.dae.relative_to(REPO)) if args.dae.is_relative_to(REPO) else str(args.dae),
            "dae_sha256": dae_sha,
            "skin_archive": str(args.source_zip.relative_to(REPO)) if args.source_zip.is_relative_to(REPO) else str(args.source_zip),
            "skin_archive_sha256": zip_sha,
            "tmc_sha256": tmc_sha,
            "dae_to_tmc_max_match_err_m": max_match_err,
            "submeshes": sorted(SUBMESH_SPEC),
            "excluded": EXCLUDED_DAE,
            "textures": tex_report,
        },
        "payload_sha256": payload,
    }
    (pack / "BUILD_INFO.json").write_text(json.dumps(build_info, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    args.out.mkdir(parents=True, exist_ok=True)
    zip_out = args.out / f"{PACK_DIR_NAME}.zip"
    built_zip = lop.zip_pack(pack)
    if built_zip != zip_out:
        shutil.copy2(built_zip, zip_out)
    zip_sha256 = _hl.sha256(zip_out.read_bytes()).hexdigest()
    sha_rel = zip_out.relative_to(REPO).as_posix() if zip_out.is_relative_to(REPO) else zip_out.name
    (zip_out.parent / f"{zip_out.name}.sha256").write_text(f"{zip_sha256}  {sha_rel}\n", encoding="utf-8")

    report = {
        "runtime_verified": False,
        "pack": PACK_DIR_NAME,
        "zip": sha_rel,
        "zip_sha256": zip_sha256,
        "drawables": drawables,
        "cut": cut_report,
        "groups": {
            gname: {"verts": len(g.verts), "tris": len(g.faces), "palette": list(g.palette)}
            for gname, g in groups.items()
        },
    }
    (args.work_dir / "honoko2_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {zip_out} ({zip_out.stat().st_size} bytes) sha256={zip_sha256[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
