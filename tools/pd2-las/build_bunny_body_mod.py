#!/usr/bin/env python3
"""Pack OfficeSuite over the vanilla Hop to It (`bunny`) outfit as a native `mod_overrides` zip.

    .venv/bin/python tools/pd2-las/build_bunny_body_mod.py
    .venv/bin/python tools/pd2-las/build_bunny_body_mod.py --out build/OfficeSuite_over_Bunny.zip

Reads the tracked ``dist/Miranda/OfficeSuite.zip`` (the 5% slim DOAXVV Honoka
"Secret Report" outfit with D70 palm cut and D75 ``ForeArmRoll`` wrist twist) and
``references/templates/ccmt_acc_bunny.7z`` (the vanilla ``player_styles.bunny``
units), and emits ``dist/Miranda/OfficeSuite_over_Bunny.zip`` for installation in
``PAYDAY 2\\assets\\mod_overrides\\`` without BeardLib or Legendary Armour Skins.

All five third-person body variants (``female_average``, ``female_fat``,
``male_average``, ``male_big``, ``male_fat``) share ``shared_materials/ccmt_acc_bunny``
(``mtr_body`` + ``shadow_caster``), while ``ccmt_acc_fps_bunny_male`` uses
``shared_materials/ccmt_acc_bunny_fps`` (``mtr_fpsarms``). Replacing every `.model`
that samples those shared textures prevents any body type from drawing the vanilla
bunny UVs against the OfficeSuite 6-tile BC3 atlas (`hila_texture_atlas.py`).

First-person alignment: ``ccmt_acc_fps_bunny_male.model`` keeps ``Hips`` at
``[0, 0, -59.9]`` (``Head`` near the FPS camera origin) with ``g_arms`` at world
identity, a pure translation from the third-person / ``fps_2b`` bind pose. Shifting
``fps_officesuite``'s vertices by ``Hips_bunny - Hips_source`` preserves exact
bone-local coordinates across every joint while keeping ``g_arms`` inside
``ccmt_acc_fps_bunny_male``'s ``co_box`` culling bounds.
"""
from __future__ import annotations

import argparse
import math
import sys
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import archive_cache  # noqa: E402
import determinism  # noqa: E402
import diesel_model as dm  # noqa: E402
import hila_texture_atlas as hta  # noqa: E402
import tangents  # noqa: E402
from dist_paths import dist_path  # noqa: E402
from las_outfit_pack import zip_bytes  # noqa: E402
from pack_checksum import write_pack_checksum  # noqa: E402

DEFAULT_SOURCE = dist_path(ROOT, "OfficeSuite.zip")
DEFAULT_BUNNY_ARCHIVE = ROOT / "references/templates/ccmt_acc_bunny.7z"
DEFAULT_CACHE = ROOT / "build/pd2-las/ccmt_acc_bunny"
DEFAULT_OUT = dist_path(ROOT, "OfficeSuite_over_Bunny.zip")

MOD_PREFIX = "OfficeSuite over Bunny"
UNIT_ROOT = "units/pd2_dlc_ccmt/characters/ccmt_acc_bunny"
ICON_PATH = "guis/dlcs/ccmt/textures/pd2/blackmarket/icons/player_styles/bunny.texture"
STAMP = (2020, 1, 1, 0, 0, 0)

TPP_UNITS: tuple[str, ...] = (
    "ccmt_acc_bunny_female_average",
    "ccmt_acc_bunny_female_fat",
    "ccmt_acc_bunny_male_average",
    "ccmt_acc_bunny_male_big",
    "ccmt_acc_bunny_male_fat",
)
FPS_UNIT = "ccmt_acc_fps_bunny_male"

HIPS_HASH = dm.hash64("Hips")
G_BODY_HASH = dm.hash64("g_body")
S_BODY_HASH = dm.hash64("s_body")
G_ARMS_HASH = dm.hash64("g_arms")
MTR_BODY_HASH = dm.hash64("mtr_body")
MTR_FPSARMS_HASH = dm.hash64("mtr_fpsarms")
SHADOW_CASTER_HASH = dm.hash64("shadow_caster")
SLOT_BY_MAT_HASH = {dm.hash64(f"officesuite_{slot}"): slot for slot in hta.TILES}


def ensure_bunny_extracted(archive: Path = DEFAULT_BUNNY_ARCHIVE,
                           cache: Path = DEFAULT_CACHE) -> Path:
    """Unpack ``ccmt_acc_bunny.7z`` once into ``build/pd2-las/ccmt_acc_bunny``."""
    if not archive.is_file():
        raise SystemExit(f"missing bunny template archive: {archive}")
    required = [
        *(f"ccmt_acc_bunny/{stem}/{stem}.model" for stem in (*TPP_UNITS, FPS_UNIT)),
        *(f"ccmt_acc_bunny/{stem}/{stem}.object" for stem in (*TPP_UNITS, FPS_UNIT)),
        "ccmt_acc_bunny/shared_materials/ccmt_acc_bunny.material_config",
        "ccmt_acc_bunny/shared_materials/ccmt_acc_bunny_fps.material_config",
        "ccmt_acc_bunny/bunny.dds",
    ]
    if not archive_cache.current(archive, cache):
        import py7zr

        def unpack(dest: Path) -> None:
            with py7zr.SevenZipFile(archive, mode="r") as zf:
                zf.extractall(path=dest)

        archive_cache.refresh(archive, cache, unpack, required)
    return cache / "ccmt_acc_bunny"


def _object_worlds(mf: dm.ModelFile) -> tuple[dict[int, dict[str, Any]], dict[int, tuple[float, ...]]]:
    """Decode every Object3D/ModelData section and compute its row-major world matrix."""
    objs = {
        s.id: dm.decode_object3d(s.payload)
        for s in mf.sections
        if s.type in (dm.OBJECT3D, dm.MODEL_DATA)
    }
    worlds_np: dict[int, np.ndarray] = {}

    def world(sid: int) -> np.ndarray:
        if sid not in worlds_np:
            loc = np.asarray(objs[sid]["matrix"], dtype=np.float64).reshape(4, 4)
            pid = objs[sid]["parent"]
            worlds_np[sid] = loc @ world(pid) if pid in objs and pid != sid else loc
        return worlds_np[sid]

    for sid in objs:
        world(sid)
    return objs, {sid: tuple(float(x) for x in w.reshape(-1)) for sid, w in worlds_np.items()}


def _extract_office_drawable(mf: dm.ModelFile, drawable_hash: int, *,
                             remap_atlas: bool) -> dict[str, Any]:
    """Extract a single-atom drawable from ``officesuite.model`` or ``fps_officesuite.model``."""
    objs, worlds = _object_worlds(mf)
    hips_sid = next(sid for sid, o in objs.items() if o["name_hash"] == HIPS_HASH)
    hips_pos = np.asarray(worlds[hips_sid][12:15], dtype=np.float64)

    mats = {s.id: dm.decode_material(s.payload)["name_hash"] for s in mf.by_type(dm.MATERIAL)}
    md_sec = next(
        s for s in mf.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6
        and dm.decode_model_data(s.payload)["name_hash"] == drawable_hash
    )
    md = dm.decode_model_data(md_sec.payload)
    mg = dm.decode_material_group(mf.by_id(md["matgroup"]).payload)
    sb = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
    pg = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(pg["geometry"]).payload)
    topo = dm.decode_topology(mf.by_id(pg["topology"]).payload)

    verts = np.asarray(geo["verts"], dtype=np.float64)
    normals = np.asarray(geo["normals"], dtype=np.float64)
    uv0 = np.asarray(geo["uv0"], dtype=np.float64)
    faces = np.asarray(topo["indices"], dtype=np.int64).reshape(-1, 3)

    if remap_atlas:
        atlas_uv = np.empty_like(uv0)
        for atom in md["atoms"]:
            mat_section_id = mg["material_ids"][atom["material_id"]]
            mat_hash = mats[mat_section_id]
            if mat_hash not in SLOT_BY_MAT_HASH:
                raise ValueError(f"unexpected OfficeSuite material hash {mat_hash:#x}")
            slot = SLOT_BY_MAT_HASH[mat_hash]
            bv, sl = atom["base_vertex"], atom["slice_len"]
            bi, tc = atom["base_index"] // 3, atom["tri_count"]
            local_faces = faces[bi:bi + tc] - bv
            atlas_uv[bv:bv + sl] = hta.atlas_uvs(uv0[bv:bv + sl], local_faces, slot)
    else:
        atlas_uv = uv0

    map0 = sb["maps"][0] if sb["maps"] else list(range(len(sb["objects"])))
    palette_hashes = [objs[sb["objects"][p]]["name_hash"] for p in map0]
    bi_arr = np.asarray(geo["blendindices"], dtype=np.int64)
    bw_arr = np.asarray(geo["blendweights"], dtype=np.float64)
    w4 = np.column_stack([bw_arr, np.maximum(0.0, 1.0 - bw_arr.sum(axis=1))])

    used_pal_slots = sorted({int(p) for p in bi_arr[w4 > 1e-6].tolist()})
    compact_hashes = [palette_hashes[p] for p in used_pal_slots]
    old_to_compact = {old_p: new_p for new_p, old_p in enumerate(used_pal_slots)}

    compact_bi: list[tuple[int, int, int, int]] = []
    for row_i, row_w in zip(bi_arr.tolist(), w4.tolist()):
        mapped = [
            old_to_compact[p] if w > 1e-6 and p in old_to_compact else 0
            for p, w in zip(row_i, row_w)
        ]
        compact_bi.append((mapped[0], mapped[1], mapped[2], mapped[3]))

    return {
        "hips_pos": hips_pos,
        "verts": verts,
        "normals": normals,
        "uv0": atlas_uv,
        "faces": [tuple(int(i) for i in f) for f in faces.tolist()],
        "indices": [int(i) for i in topo["indices"]],
        "palette_hashes": compact_hashes,
        "blendindices": compact_bi,
        "blendweights": [tuple(float(x) for x in w) for w in geo["blendweights"]],
    }


def _bounds(verts: list[tuple[float, float, float]]) -> tuple[
    tuple[float, float, float], tuple[float, float, float], float
]:
    arr = np.asarray(verts, dtype=np.float32).astype(np.float64)
    bmin = (float(arr[:, 0].min()), float(arr[:, 1].min()), float(arr[:, 2].min()))
    bmax = (float(arr[:, 0].max()), float(arr[:, 1].max()), float(arr[:, 2].max()))
    radius = float(math.sqrt(float((arr * arr).sum(axis=1).max())))
    return bmin, bmax, radius


def _skinbones_for_target(
    base_sb: dict[str, Any],
    palette_hashes: list[int],
    bone_id_by_hash: dict[int, int],
    target_worlds: dict[int, tuple[float, ...]],
    existing_ibm: dict[int, tuple[float, ...]],
) -> dict[str, Any]:
    objects: list[int] = []
    rotations: list[tuple[float, ...]] = []
    for h in palette_hashes:
        if h not in bone_id_by_hash:
            raise ValueError(f"target model missing weighted bone hash {h:#x}")
        bid = bone_id_by_hash[h]
        objects.append(bid)
        rotations.append(existing_ibm.get(bid) or dm.mat_inv(target_worlds[bid]))
    full_map = list(range(len(objects)))
    return {
        "maps": [full_map, list(full_map)],
        "root": base_sb["root"],
        "objects": objects,
        "rotations": rotations,
        "global": base_sb["global"],
        "remaining": base_sb.get("remaining", b""),
    }


def _top2_weights(
    blendindices: list[tuple[int, int, int, int]],
    blendweights: list[tuple[float, float, float]],
) -> tuple[list[tuple[int, int, int, int]], list[tuple[float, float, float]]]:
    """Normalize top-2 weights per vertex for ``s_body``'s 2-float BLENDWEIGHT0 stream."""
    out_bi: list[tuple[int, int, int, int]] = []
    out_bw: list[tuple[float, float, float]] = []
    for (i0, i1, i2, i3), (w0, w1, w2) in zip(blendindices, blendweights):
        w3 = max(0.0, 1.0 - w0 - w1 - w2)
        pairs = sorted(((w0, i0), (w1, i1), (w2, i2), (w3, i3)), key=lambda x: -x[0])
        (wa, ia), (wb, ib) = pairs[0], pairs[1]
        total = wa + wb
        if total > 1e-8:
            wa, wb = wa / total, wb / total
        else:
            wa, wb, ib = 1.0, 0.0, 0
        if wb <= 1e-6:
            wa, wb, ib = 1.0, 0.0, 0
        out_bi.append((ia, ib, 0, 0))
        out_bw.append((wa, wb, 0.0))
    return out_bi, out_bw


def patch_bunny_tpp_model(
    model_bytes: bytes,
    packed_body: dict[str, Any],
    packed_shadow: dict[str, Any],
    uv_frame_cache: dict[tuple[float, float, float], tuple[
        list[tuple[float, float, float]], list[tuple[float, float, float]]
    ]] | None = None,
) -> bytes:
    """Replace ``g_body`` and ``s_body`` in one third-person ``ccmt_acc_bunny_*.model``."""
    mf = dm.ModelFile.read(model_bytes)
    objs, worlds = _object_worlds(mf)
    bone_id_by_hash = {o["name_hash"]: sid for sid, o in objs.items()}
    hips_sid = bone_id_by_hash[HIPS_HASH]
    target_hips = np.asarray(worlds[hips_sid][12:15], dtype=np.float64)

    existing_ibm: dict[int, tuple[float, ...]] = {}
    for s in mf.by_type(dm.SKINBONES):
        sb = dm.decode_skinbones(s.payload)
        for bid, rot in zip(sb["objects"], sb["rotations"]):
            existing_ibm.setdefault(bid, rot)

    mat_by_hash = {
        dm.decode_material(s.payload)["name_hash"]: s.id
        for s in mf.by_type(dm.MATERIAL)
    }
    mtr_body_id = mat_by_hash[MTR_BODY_HASH]
    shadow_mat_id = mat_by_hash[SHADOW_CASTER_HASH]

    body_shift = target_hips - packed_body["hips_pos"]
    body_verts = [
        (float(v[0] + body_shift[0]), float(v[1] + body_shift[1]), float(v[2] + body_shift[2]))
        for v in packed_body["verts"].tolist()
    ]
    body_normals = [tuple(float(x) for x in n) for n in packed_body["normals"].tolist()]
    body_uvs = [tuple(float(x) for x in uv) for uv in packed_body["uv0"].tolist()]
    cache_key = (float(target_hips[0]), float(target_hips[1]), float(target_hips[2]))
    if uv_frame_cache is not None and cache_key in uv_frame_cache:
        u_dirs, v_dirs = uv_frame_cache[cache_key]
    else:
        u_dirs, v_dirs = tangents.tangent_frames(
            body_verts, body_normals, body_uvs, packed_body["faces"]
        )
        if uv_frame_cache is not None:
            uv_frame_cache[cache_key] = (u_dirs, v_dirs)
    body_bmin, body_bmax, body_rad = _bounds(body_verts)

    sh_shift = target_hips - packed_shadow["hips_pos"]
    sh_verts = [
        (float(v[0] + sh_shift[0]), float(v[1] + sh_shift[1]), float(v[2] + sh_shift[2]))
        for v in packed_shadow["verts"].tolist()
    ]
    sh_bi, sh_bw = _top2_weights(packed_shadow["blendindices"], packed_shadow["blendweights"])
    sh_bmin, sh_bmax, sh_rad = _bounds(sh_verts)

    g_md_sec = next(
        s for s in mf.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6
        and dm.decode_model_data(s.payload)["name_hash"] == G_BODY_HASH
    )
    s_md_sec = next(
        s for s in mf.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6
        and dm.decode_model_data(s.payload)["name_hash"] == S_BODY_HASH
    )
    g_md = dm.decode_model_data(g_md_sec.payload)
    s_md = dm.decode_model_data(s_md_sec.payload)
    g_pg = dm.decode_passthroughgp(mf.by_id(g_md["passthroughgp"]).payload)
    s_pg = dm.decode_passthroughgp(mf.by_id(s_md["passthroughgp"]).payload)

    new_sections: list[dm.Section] = []
    for s in mf.sections:
        if s.id == g_pg["geometry"]:
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = len(body_verts)
            dec["verts"] = body_verts
            dec["normals"] = body_normals
            dec["uv0"] = body_uvs
            dec["blendindices"] = packed_body["blendindices"]
            dec["blendweights"] = packed_body["blendweights"]
            dec["uvdir_u"] = u_dirs
            dec["uvdir_v"] = v_dirs
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id == g_pg["topology"]:
            dec = dm.decode_topology(s.payload)
            dec["indices"] = packed_body["indices"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id == g_md_sec.id:
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = [{
                "base_vertex": 0,
                "tri_count": len(packed_body["faces"]),
                "base_index": 0,
                "slice_len": len(body_verts),
                "material_id": 0,
            }]
            dec["bounds_min"] = body_bmin
            dec["bounds_max"] = body_bmax
            dec["bounding_radius"] = body_rad
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        elif s.id == g_md["matgroup"]:
            dec = dm.decode_material_group(s.payload)
            dec["material_ids"] = [mtr_body_id]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_material_group(dec)))
        elif s.id == g_md["skinbones"]:
            dec = _skinbones_for_target(
                dm.decode_skinbones(s.payload),
                packed_body["palette_hashes"],
                bone_id_by_hash,
                worlds,
                existing_ibm,
            )
            new_sections.append(dm.Section(s.type, s.id, dm.encode_skinbones(dec)))
        elif s.id == s_pg["geometry"]:
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = len(sh_verts)
            dec["verts"] = sh_verts
            dec["blendindices"] = sh_bi
            dec["blendweights"] = sh_bw
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id == s_pg["topology"]:
            dec = dm.decode_topology(s.payload)
            dec["indices"] = packed_shadow["indices"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id == s_md_sec.id:
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = [{
                "base_vertex": 0,
                "tri_count": len(packed_shadow["faces"]),
                "base_index": 0,
                "slice_len": len(sh_verts),
                "material_id": 0,
            }]
            dec["bounds_min"] = sh_bmin
            dec["bounds_max"] = sh_bmax
            dec["bounding_radius"] = sh_rad
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        elif s.id == s_md["matgroup"]:
            dec = dm.decode_material_group(s.payload)
            dec["material_ids"] = [shadow_mat_id]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_material_group(dec)))
        elif s.id == s_md["skinbones"]:
            dec = _skinbones_for_target(
                dm.decode_skinbones(s.payload),
                packed_shadow["palette_hashes"],
                bone_id_by_hash,
                worlds,
                existing_ibm,
            )
            new_sections.append(dm.Section(s.type, s.id, dm.encode_skinbones(dec)))
        elif s.type == dm.GEOMETRY:
            # Re-encode cooked DODB geometry (co_box) into legacy float-packed channels.
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dm.decode_geometry(s.payload))))
        else:
            new_sections.append(s)

    return dm.ModelFile(new_sections).write()


def patch_bunny_fps_model(model_bytes: bytes, packed_fps: dict[str, Any]) -> bytes:
    """Replace ``g_arms`` in ``ccmt_acc_fps_bunny_male.model``, shifted into FPS rig space."""
    mf = dm.ModelFile.read(model_bytes)
    objs, worlds = _object_worlds(mf)
    bone_id_by_hash = {o["name_hash"]: sid for sid, o in objs.items()}
    hips_sid = bone_id_by_hash[HIPS_HASH]
    target_hips = np.asarray(worlds[hips_sid][12:15], dtype=np.float64)

    existing_ibm: dict[int, tuple[float, ...]] = {}
    for s in mf.by_type(dm.SKINBONES):
        sb = dm.decode_skinbones(s.payload)
        for bid, rot in zip(sb["objects"], sb["rotations"]):
            existing_ibm.setdefault(bid, rot)

    mat_by_hash = {
        dm.decode_material(s.payload)["name_hash"]: s.id
        for s in mf.by_type(dm.MATERIAL)
    }
    mtr_fps_id = mat_by_hash[MTR_FPSARMS_HASH]

    fps_shift = target_hips - packed_fps["hips_pos"]
    fps_verts = [
        (float(v[0] + fps_shift[0]), float(v[1] + fps_shift[1]), float(v[2] + fps_shift[2]))
        for v in packed_fps["verts"].tolist()
    ]
    fps_normals = [tuple(float(x) for x in n) for n in packed_fps["normals"].tolist()]
    fps_uvs = [tuple(float(x) for x in uv) for uv in packed_fps["uv0"].tolist()]
    u_dirs, v_dirs = tangents.tangent_frames(fps_verts, fps_normals, fps_uvs, packed_fps["faces"])
    fps_bmin, fps_bmax, fps_rad = _bounds(fps_verts)

    arms_md_sec = next(
        s for s in mf.by_type(dm.MODEL_DATA)
        if dm.decode_model_data(s.payload)["version"] != 6
        and dm.decode_model_data(s.payload)["name_hash"] == G_ARMS_HASH
    )
    arms_md = dm.decode_model_data(arms_md_sec.payload)
    arms_pg = dm.decode_passthroughgp(mf.by_id(arms_md["passthroughgp"]).payload)

    new_sections: list[dm.Section] = []
    for s in mf.sections:
        if s.id == arms_pg["geometry"]:
            dec = dm.decode_geometry(s.payload)
            dec["vert_count"] = len(fps_verts)
            dec["verts"] = fps_verts
            dec["normals"] = fps_normals
            dec["uv0"] = fps_uvs
            dec["blendindices"] = packed_fps["blendindices"]
            dec["blendweights"] = packed_fps["blendweights"]
            dec["uvdir_u"] = u_dirs
            dec["uvdir_v"] = v_dirs
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dec)))
        elif s.id == arms_pg["topology"]:
            dec = dm.decode_topology(s.payload)
            dec["indices"] = packed_fps["indices"]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_topology(dec)))
        elif s.id == arms_md_sec.id:
            dec = dm.decode_model_data(s.payload)
            dec["atoms"] = [{
                "base_vertex": 0,
                "tri_count": len(packed_fps["faces"]),
                "base_index": 0,
                "slice_len": len(fps_verts),
                "material_id": 0,
            }]
            dec["bounds_min"] = fps_bmin
            dec["bounds_max"] = fps_bmax
            dec["bounding_radius"] = fps_rad
            new_sections.append(dm.Section(s.type, s.id, dm.encode_model_data(dec)))
        elif s.id == arms_md["matgroup"]:
            dec = dm.decode_material_group(s.payload)
            dec["material_ids"] = [mtr_fps_id]
            new_sections.append(dm.Section(s.type, s.id, dm.encode_material_group(dec)))
        elif s.id == arms_md["skinbones"]:
            dec = _skinbones_for_target(
                dm.decode_skinbones(s.payload),
                packed_fps["palette_hashes"],
                bone_id_by_hash,
                worlds,
                existing_ibm,
            )
            new_sections.append(dm.Section(s.type, s.id, dm.encode_skinbones(dec)))
        elif s.type == dm.GEOMETRY:
            new_sections.append(dm.Section(s.type, s.id, dm.encode_geometry(dm.decode_geometry(s.payload))))
        else:
            new_sections.append(s)

    return dm.ModelFile(new_sections).write()


def build_members(
    office_suite_zip: Path = DEFAULT_SOURCE,
    bunny_archive: Path = DEFAULT_BUNNY_ARCHIVE,
    cache_dir: Path = DEFAULT_CACHE,
) -> dict[str, bytes]:
    """Build all zip entries for ``OfficeSuite_over_Bunny.zip``."""
    if not office_suite_zip.is_file():
        raise SystemExit(
            f"missing {office_suite_zip}; build OfficeSuite first (`make -sC tools/pd2-las honokodae`)"
        )
    bunny_dir = ensure_bunny_extracted(bunny_archive, cache_dir)

    with zipfile.ZipFile(office_suite_zip) as zf:
        tpp_mf = dm.ModelFile.read(
            zf.read("OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite.model")
        )
        fps_mf = dm.ModelFile.read(
            zf.read("OfficeSuite/assets/units/officesuite/skins/officesuite/fps_officesuite.model")
        )
        tiles_df = {
            slot: zf.read(
                f"OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite_{slot}_df.texture"
            )
            for slot in hta.TILES
        }
        tiles_nm = {
            slot: zf.read(
                f"OfficeSuite/assets/units/officesuite/skins/officesuite/officesuite_{slot}_nm.texture"
            )
            for slot in hta.TILES
        }
        icon_dds = zf.read("OfficeSuite/assets/guis/dlcs/officesuite/armor_skins/officesuite.texture")

    df_atlas = hta.make_atlas(tiles_df, normal=False)
    nm_atlas = hta.make_atlas(tiles_nm, normal=True)

    packed_body = _extract_office_drawable(tpp_mf, G_BODY_HASH, remap_atlas=True)
    packed_shadow = _extract_office_drawable(tpp_mf, S_BODY_HASH, remap_atlas=False)
    packed_fps = _extract_office_drawable(fps_mf, G_BODY_HASH, remap_atlas=True)
    uv_frame_cache: dict[tuple[float, float, float], tuple[
        list[tuple[float, float, float]], list[tuple[float, float, float]]
    ]] = {}

    files: dict[str, bytes] = {
        f"{MOD_PREFIX}/{ICON_PATH}": icon_dds,
        f"{MOD_PREFIX}/{UNIT_ROOT}/shared_materials/ccmt_acc_bunny.material_config": (
            bunny_dir / "shared_materials/ccmt_acc_bunny.material_config"
        ).read_bytes(),
        f"{MOD_PREFIX}/{UNIT_ROOT}/shared_materials/ccmt_acc_bunny_fps.material_config": (
            bunny_dir / "shared_materials/ccmt_acc_bunny_fps.material_config"
        ).read_bytes(),
        f"{MOD_PREFIX}/{UNIT_ROOT}/acc_bunny_df.texture": df_atlas,
        f"{MOD_PREFIX}/{UNIT_ROOT}/acc_bunny_nm.texture": nm_atlas,
        f"{MOD_PREFIX}/{UNIT_ROOT}/acc_bunny_fps_df.texture": df_atlas,
        f"{MOD_PREFIX}/{UNIT_ROOT}/acc_bunny_fps_nm.texture": nm_atlas,
    }

    for stem in TPP_UNITS:
        patched_tpp = patch_bunny_tpp_model(
            (bunny_dir / stem / f"{stem}.model").read_bytes(),
            packed_body,
            packed_shadow,
            uv_frame_cache,
        )
        files[f"{MOD_PREFIX}/{UNIT_ROOT}/{stem}/{stem}.model"] = patched_tpp
        files[f"{MOD_PREFIX}/{UNIT_ROOT}/{stem}/{stem}.object"] = (
            bunny_dir / stem / f"{stem}.object"
        ).read_bytes()

    patched_fps = patch_bunny_fps_model(
        (bunny_dir / FPS_UNIT / f"{FPS_UNIT}.model").read_bytes(),
        packed_fps,
    )
    files[f"{MOD_PREFIX}/{UNIT_ROOT}/{FPS_UNIT}/{FPS_UNIT}.model"] = patched_fps
    files[f"{MOD_PREFIX}/{UNIT_ROOT}/{FPS_UNIT}/{FPS_UNIT}.object"] = (
        bunny_dir / FPS_UNIT / f"{FPS_UNIT}.object"
    ).read_bytes()

    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-zip", type=Path, default=DEFAULT_SOURCE,
                    help="path to OfficeSuite.zip (default: dist/Miranda/OfficeSuite.zip)")
    ap.add_argument("--bunny-archive", type=Path, default=DEFAULT_BUNNY_ARCHIVE,
                    help="path to ccmt_acc_bunny.7z (default: references/templates/ccmt_acc_bunny.7z)")
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_CACHE,
                    help="extraction cache directory (default: build/pd2-las/ccmt_acc_bunny)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help="output zip path (default: dist/Miranda/OfficeSuite_over_Bunny.zip)")
    args = ap.parse_args(argv)
    determinism.enter(__file__)

    files = build_members(
        office_suite_zip=args.source_zip,
        bunny_archive=args.bunny_archive,
        cache_dir=args.work_dir,
    )
    raw = zip_bytes([(name, files[name]) for name in sorted(files)], stamp=STAMP)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(raw)
    out_resolved = args.out.resolve()
    sha = write_pack_checksum(
        out_resolved, None if not out_resolved.is_relative_to(ROOT / "dist") else ROOT
    )
    rel = out_resolved.relative_to(ROOT).as_posix() if out_resolved.is_relative_to(ROOT) else str(args.out)
    print(f"wrote {rel} ({len(raw):,} bytes, {len(files)} files) sha256={sha[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
