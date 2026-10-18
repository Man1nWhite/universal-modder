"""Shared offline model preparation for LAS and BeardLib outfit packages.

Keep the source skeleton and selected drawables, slice FPS arms deterministically,
and require complete resource references. These checks do not test Diesel runtime
loading, rendering or animation, and do not re-rig the source geometry.
"""
from __future__ import annotations

import math
import struct

import dmodel
import repair_skin_palettes as rp
from dmodel import hash_str

ARM_SUFFIXES = (
    "Shoulder", "Arm", "ForeArm", "ForeArmRoll", "Hand",
    "HandThumb1", "HandThumb2", "HandThumb3",
    "HandIndex1", "HandIndex2", "HandIndex3",
    "HandMiddle1", "HandMiddle2", "HandMiddle3",
    "HandRing1", "HandRing2", "HandRing3",
    "HandPinky1", "HandPinky2", "HandPinky3",
)
ARM_BONE_NAMES = {
    *(s + suf for s in ("Left", "Right") for suf in ARM_SUFFIXES),
    "a_weapon_left_front", "a_weapon_right_front",
}


GRAPHICS_ENABLED = [
    "g_head_fem1", "g_hair_cloth1", "g_hair_cloth2", "g_hair_cloth3",
    "g_body", "g_hands", "s_body",
]
GRAPHICS_DISABLED = [
    "g_hair_mask_cloth1", "g_hair_mask_cloth2", "g_hair_mask_cloth3",
    "g_vest_small", "g_vest_thies", "g_vest_neck", "g_vest_shoulder",
    "g_vest_body", "g_vest_leg_arm", "g_toolbag", "g_ammobag", "g_medicbag",
    "g_sentrybag", "g_bodybagsbag", "g_armorbag", "g_firstaidbag",
]
SHADOW_CASTERS = {"g_head_fem1", "g_body", "g_hands", "s_body"}

TPP_DRAWABLES = frozenset(GRAPHICS_ENABLED)
FPS_DRAWABLES = frozenset({"g_body", "g_hands"})


def _nm(o) -> str:
    """Object name string; parse-time names are hash-only, use .name from hashlist."""
    return o.name if isinstance(o.name, str) else f"#{o.name_hash:016x}"


def _model_by_name(sections, name: str):
    h = hash_str(name)
    for s in sections:
        if s.tag == "model_data" and getattr(s.obj, "name_hash", None) == h:
            return s
    raise KeyError(f"model_data {name!r} not found")


def _serialize_object_prefix(o) -> bytes:
    """name_hash + anim_ids + matrix(with pos in row 4) + pos + parent_id."""
    w = bytearray()
    w += struct.pack("<Q", o.name_hash)
    w += struct.pack("<I", len(o.anim_ids))
    for aid, u in o.anim_ids:
        w += struct.pack("<I", aid) + struct.pack("<Q", u)
    rows = list(o.matrix)
    rows[12:15] = [o.pos[0], o.pos[1], o.pos[2]]
    for v in rows:
        w += struct.pack("<f", v)
    for v in o.pos:
        w += struct.pack("<f", v)
    w += struct.pack("<I", o.parent_id)
    return bytes(w)


def _chain_ids(md, by_id) -> list[int]:
    if getattr(md, "version", 3) == 6 or not hasattr(md, "passthrough_id"):
        return []  # version-6 (LOD/collision) models carry inline data
    ids = []
    pg = by_id.get(md.passthrough_id)
    if pg is not None:
        ids.append(pg.obj.geometry_id)
        ids.append(pg.obj.topology_id)
        ids.append(pg.id)
    if md.topologyip_id:
        ids.append(md.topologyip_id)
    if md.skinbones_id:
        ids.append(md.skinbones_id)
    return ids


def _arm_bone_ids(sections) -> set[int]:
    want = {hash_str(n) for n in ARM_BONE_NAMES}
    return {
        s.id
        for s in sections
        if s.tag == "object3D" and s.obj.name_hash in want
    }


def _vert_bones(geom, sb, vi) -> set[int]:
    """Bone object3D ids a vertex is bound to (palette-local blend indices)."""
    bones = set()
    mapping = sb.bone_mappings[0]  # identity in our models; per-atom maps match
    for j, w in zip(geom.joints[vi], geom.weights4(vi)):
        if w > 0.0 and j < len(mapping):
            slot = mapping[j]
            if slot < len(sb.object_ids):
                bones.add(sb.object_ids[slot])
    return bones


def rebuild_drawable(sections, by_id, raw_by_id, md_sec, keep_verts: set[int]):
    """Rewrite one drawable's chain in raw_by_id keeping only keep_verts.

    Face indices are global (verified against _trim_redundant_atoms).  Vertex
    order is preserved so per-atom blocks stay contiguous; atoms with no kept
    verts are dropped.  Geometry channels are sliced bit-exactly.
    """
    md = md_sec.obj
    pg_sec = by_id[md.passthrough_id]
    geom_sec = by_id[pg_sec.obj.geometry_id]
    topo_sec = by_id[pg_sec.obj.topology_id]
    geom, topo = geom_sec.obj, topo_sec.obj

    kept = sorted(v for v in keep_verts if v < geom.vert_count)
    if not kept:
        raise ValueError(f"{_nm(md)}: no vertices kept")
    remap = {old: new for new, old in enumerate(kept)}

    # ---- geometry: per-channel slices of kept vertices ----
    g_raw = bytes(raw_by_id[geom_sec.id])
    hdr_end = 8 + 8 * len(geom.headers)
    sizes = dmodel.DieselGeometry.RAID_SIZES if geom.format == "raid" else dmodel.DieselGeometry.PAYDAY_SIZES
    new_g = bytearray(struct.pack("<II", len(kept), len(geom.headers)))
    new_g += g_raw[8:hdr_end]
    ch_off = hdr_end
    for isz_code, _ity in geom.headers:
        isz = sizes[isz_code]
        for vi in kept:
            new_g += g_raw[ch_off + vi * isz : ch_off + (vi + 1) * isz]
        ch_off += geom.vert_count * isz
    new_g += g_raw[ch_off:]          # name hash + remaining
    raw_by_id[geom_sec.id] = new_g

    # ---- topology + atoms ----
    # kept preserves old order and atom ranges are contiguous, so the new
    # global layout is atom-major and face indices stay global (as in
    # _trim_redundant_atoms).
    new_faces: list[tuple[int, int, int]] = []
    new_atoms: list[dict[str, int]] = []
    new_base_v = 0
    new_base_idx = 0
    for atom in md.render_atoms:
        v0, vlen = atom["base_vertex"], atom["geo_len"]
        f0, fcnt = atom["base_index"] // 3, atom["tri_count"]
        atom_verts = [vi for vi in kept if v0 <= vi < v0 + vlen]
        if not atom_verts:
            continue
        block_map = {vi: new_base_v + i for i, vi in enumerate(atom_verts)}
        faces = [
            tuple(block_map[x] for x in tri)
            for tri in topo.faces[f0 : f0 + fcnt]
            if tri[0] in block_map and tri[1] in block_map and tri[2] in block_map
        ]
        new_faces.extend(faces)
        new_atoms.append(
            {
                "base_vertex": new_base_v,
                "tri_count": len(faces),
                "base_index": new_base_idx,
                "geo_len": len(atom_verts),
                "material_id": atom["material_id"],
            }
        )
        new_base_v += len(atom_verts)
        new_base_idx += len(faces) * 3

    new_t = bytearray(struct.pack("<II", topo.primitive, len(new_faces) * 3))
    for tri in new_faces:
        new_t += struct.pack("<3H", *tri)
    new_t += struct.pack("<I", len(topo.items2)) + topo.items2
    new_t += struct.pack("<Q", topo.name_hash) + topo.remaining
    raw_by_id[topo_sec.id] = new_t

    # ---- model payload ----
    w = bytearray(_serialize_object_prefix(md))
    w += struct.pack("<I", 3)                      # version
    w += struct.pack("<II", md.passthrough_id, md.topologyip_id)
    w += struct.pack("<I", len(new_atoms))
    for a in new_atoms:
        w += struct.pack(
            "<IIIII",
            a["base_vertex"], a["tri_count"], a["base_index"],
            a["geo_len"], a["material_id"],
        )
    w += struct.pack("<I", md.matgroup_id)
    w += struct.pack("<I", md.lightset_id)
    w += struct.pack("<I", md.properties)
    for v in list(md.bounds_min) + list(md.bounds_max):
        w += struct.pack("<f", v)
    w += struct.pack("<f", md.bounding_radius)
    w += struct.pack("<I", md.bounding_int)
    w += struct.pack("<I", md.skinbones_id)
    w += md.remaining
    raw_by_id[md_sec.id] = w

    # ---- skinbones: same palette, one identity mapping per new atom ----
    sb_sec = by_id[md.skinbones_id]
    sb = sb_sec.obj
    sw = bytearray()
    sw += struct.pack("<I", 1 + len(new_atoms))
    for _ in range(1 + len(new_atoms)):
        sw += struct.pack("<I", len(sb.object_ids))
        for i in range(len(sb.object_ids)):
            sw += struct.pack("<I", i)
    sw += struct.pack("<I", sb.root_bone_id)
    sw += struct.pack("<I", sb.count)
    for bid in sb.object_ids:
        sw += struct.pack("<I", bid)
    for rows in sb.rotations:
        for v in rows:
            sw += struct.pack("<f", v)
    for v in sb.global_skin_transform:
        sw += struct.pack("<f", v)
    sw += sb.remaining
    raw_by_id[sb_sec.id] = sw

    return new_atoms


def validate_model(data: bytes) -> None:
    """Additional range checks, independent of the old validator's blind spots.

    This builder intentionally accepts only modern DODB input. Vertex references
    are UInt16; the topology's *index count* is UInt32, not limited to 65,535.
    This is structural validation, not proof the engine can animate the model.
    """
    if data[:8] != b"DODB\x01\x00\x00\x00":
        raise ValueError("Expected a repaired modern DODB version-1 model")
    sections, _, _, filesize, by_id = rp.parse_model_bytes(data)
    if filesize != len(data) or not sections or sections[-1].end != len(data):
        raise ValueError("Model container length mismatch")
    if len(by_id) != len(sections):
        raise ValueError("Duplicate model section IDs")
    errors = rp._check_section_refs(sections, by_id)
    if errors:
        raise ValueError("; ".join(errors))
    for sec in sections:
        if sec.tag != "model_data" or sec.obj.version == 6:
            continue
        md = sec.obj
        gp = by_id[md.passthrough_id].obj
        geo = by_id[gp.geometry_id].obj
        topo_sec = by_id[gp.topology_id]
        topo = topo_sec.obj
        vertex_count = len(geo.positions)
        index_count = struct.unpack_from("<I", data, topo_sec.start + 4)[0]
        if index_count != len(topo.faces) * 3:
            raise ValueError(f"Model {sec.id}: topology index count is not a triangle list")
        if any(not math.isfinite(v) for p in geo.positions for v in p):
            raise ValueError(f"Model {sec.id}: non-finite vertex position")
        if any(v >= vertex_count for face in topo.faces for v in face):
            raise ValueError(f"Model {sec.id}: vertex reference outside geometry")
        materials = by_id[md.matgroup_id].obj.items
        for atom in md.render_atoms:
            v0, v1 = atom["base_vertex"], atom["base_vertex"] + atom["geo_len"]
            i0, i1 = atom["base_index"], atom["base_index"] + atom["tri_count"] * 3
            if not (0 <= v0 <= v1 <= vertex_count):
                raise ValueError(f"Model {sec.id}: render-atom vertex range outside geometry")
            if i0 % 3 or not (0 <= i0 <= i1 <= index_count):
                raise ValueError(f"Model {sec.id}: render-atom index range outside topology")
            if atom["material_id"] >= len(materials):
                raise ValueError(f"Model {sec.id}: render-atom material outside material group")
            if any(not v0 <= v < v1 for face in topo.faces[i0 // 3:i1 // 3] for v in face):
                raise ValueError(f"Model {sec.id}: vertex reference outside render-atom range")
        if md.skinbones_id:
            if len(geo.joints) != vertex_count or len(geo.weights3) != vertex_count:
                raise ValueError(f"Model {sec.id}: missing skin channels")
            if any(not math.isfinite(w) for weights in geo.weights3 for w in weights):
                raise ValueError(f"Model {sec.id}: non-finite skin weight")
    errors = rp.validate_model_skinning(data, strict_layout=False)
    if errors:
        raise ValueError("; ".join(errors))


def select_arm_verts(md, geo, topo, skin, arm_ids: set[int]) -> set[int]:
    """Select arm-bound vertices plus ONE ring, never flood-fill in face order."""
    seeds = frozenset(
        i for atom in md.render_atoms
        for i in range(atom["base_vertex"], atom["base_vertex"] + atom["geo_len"])
        if _vert_bones(geo, skin, i) & arm_ids
    )
    selected = set(seeds)
    for face in topo.faces:
        if any(v in seeds for v in face):
            selected.update(face)
    return selected


def material_hashes(data: bytes) -> set[int]:
    sections, _, _, _, by_id = rp.parse_model_bytes(data)
    used = set()
    for sec in sections:
        if sec.tag != "model_data" or sec.obj.version == 6:
            continue
        md = sec.obj
        group = by_id[md.matgroup_id].obj.items
        used.update(by_id[group[a["material_id"]]].obj.name_hash for a in md.render_atoms)
    return used


def prepare_model(data: bytes, *, first_person: bool) -> bytes:
    """Keep the heister skeleton, but remove unused mesh chains and materials."""
    validate_model(data)
    sections, _, _, _, by_id = rp.parse_model_bytes(data)
    names = FPS_DRAWABLES if first_person else TPP_DRAWABLES
    wanted = {_model_by_name(sections, n).id for n in names}
    payloads = {s.id: bytearray(data[s.start:s.end]) for s in sections}
    keep_chain, keep_groups = set(), set()
    culling_positions = []
    for sid in wanted:
        md = by_id[sid].obj
        keep_chain.update(_chain_ids(md, by_id))
        keep_groups.add(md.matgroup_id)
        gp = by_id[md.passthrough_id].obj
        geo, topo = by_id[gp.geometry_id].obj, by_id[gp.topology_id].obj
        if first_person and sid == _model_by_name(sections, "g_body").id:
            selected = select_arm_verts(md, geo, topo, by_id[md.skinbones_id].obj, _arm_bone_ids(sections))
            if not selected:
                raise ValueError("Arm selection is empty")
            rebuild_drawable(sections, by_id, payloads, by_id[sid], selected)
            culling_positions.extend(geo.positions[i] for i in sorted(selected))
        else:
            culling_positions.extend(geo.positions)

    drop = set()
    for sec in sections:
        if sec.tag == "model_data" and sec.id not in wanted:
            drop.add(sec.id)
            if sec.obj.version != 6:
                drop.update(set(_chain_ids(sec.obj, by_id)) - keep_chain)
    keep_materials = {mid for gid in keep_groups for mid in by_id[gid].obj.items}
    drop.update(s.id for s in sections if s.tag == "material_group" and s.id not in keep_groups)
    drop.update(s.id for s in sections if s.tag == "material" and s.id not in keep_materials)

    # Use a real bounded drawable for culling, not an empty co_box locator.
    # Conservatively expand g_body's bounds to include every retained mesh.
    body = _model_by_name(sections, "g_body")
    raw = bytearray(payloads[body.id])
    prefix_len = len(_serialize_object_prefix(body.obj))
    atom_count = struct.unpack_from("<I", raw, prefix_len + 12)[0]
    bounds_off = prefix_len + 16 + 20 * atom_count + 12
    lo = [min(p[i] for p in culling_positions) for i in range(3)]
    hi = [max(p[i] for p in culling_positions) for i in range(3)]
    radius = math.sqrt(sum(max(abs(a), abs(b)) ** 2 for a, b in zip(lo, hi)))
    struct.pack_into("<7f", raw, bounds_off, *lo, *hi, radius)
    payloads[body.id] = bytes(raw)

    kept = [s for s in sections if s.id not in drop]
    result = bytearray(b"DODB" + struct.pack("<III", 1, 0, len(kept)))
    for sec in kept:
        payload = payloads[sec.id]
        result += struct.pack("<III", sec.type, sec.id, len(payload)) + payload
    struct.pack_into("<I", result, 8, len(result))
    normalized, _ = rp.normalize_model_container(bytes(result))
    validate_model(normalized)
    return normalized
