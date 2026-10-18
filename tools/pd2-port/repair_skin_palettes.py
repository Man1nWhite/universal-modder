#!/usr/bin/env python3
"""Inspect and repair PAYDAY 2 Diesel .model and .texture files in Lawson ZIPs.

Diesel DODB .model containers and vanilla DXT5 .texture files follow
structural invariants that build_character.py / build_package2.py did not.
Four defects (found by binary-diffing the generated files against the vanilla
clover/, Bonie/ and Sydney/ assets, then confirmed against crash logs showing
an access violation in MenuSetup:load_packages()):

1. SkinBones.bone_mappings (0x65CC1825): must contain 0-based local indices
   (0 .. count - 1) into SkinBones.object_ids / rotations, not Object3D
   section IDs.
2. DODB section layout: every vanilla .model has strictly contiguous,
   ascending 1-based section IDs 1 .. count and a canonical section order
   (animation_data/author -> [material_group, its materials] blocks ->
   object3D/model_data in hierarchy order -> mesh groups, unskinned models
   first then skinned, each group [skinbones, geometry, topology,
   passthroughGP, topologyIP] in model order). build_character.py dropped
   whole mesh groups while allocating new IDs past max_id, leaving holes in
   1 .. max_id (max_id > count: 450 > 417 in Clover, 250 > 228 in Bonnie,
   265 > 237 in Sydney), spliced new mesh groups into the middle of the
   model_data block, and appended new materials at the end of the file. Any
   engine-side section table indexed by ID then reads out of bounds.
3. Topology index bookkeeping in g_body: stacking the redundant, overlapping
   lawson_swim and lawson_under layers pushed g_body's Topology to
   73,371 / 73,239 / 73,323 indices (every vanilla character Topology stays
   at 15,609-18,360; face indices are uint16 and mesh tooling limits each
   Topology to 65,535 indices). Dropping those two hidden layers brings
   g_body to 63,975 / 63,843 / 63,927 indices.
4. DDS .texture mipmaps: build_package2.py wrote mip 0 only with
   dwMipMapCount = 0 (flags 0x00081007, caps 0x00001000), while vanilla DXT5
   textures carry the full pyramid (flags 0x000A1007, caps 0x00401008,
   dwMipMapCount = log2(size) + 1). Its block encoder also wrote colour
   endpoints as c0 < c1 on some blocks, which decoders read as the 3-colour
   mode with a transparent index (visible holes).

Usage:
    python repair_skin_palettes.py dist/lawson_*.zip           # repair in place
    python repair_skin_palettes.py --check dist/lawson_*.zip   # validate only

The repair is idempotent and preserves vanilla-canonical files byte-identical.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import struct
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import dds  # noqa: E402
import dmodel  # noqa: E402
import package_metadata  # noqa: E402

TAG_MODEL = dmodel.TAGS_INV["model_data"]
TAG_OBJECT3D = dmodel.TAGS_INV["object3D"]
TAG_SKINBONES = dmodel.TAGS_INV["skinbones"]
TAG_GEOMETRY = dmodel.TAGS_INV["geometry"]
TAG_TOPOLOGY = dmodel.TAGS_INV["topology"]
TAG_PASSTHROUGH = dmodel.TAGS_INV["passthroughGP"]
TAG_TOPOLOGY_IP = dmodel.TAGS_INV["topologyIP"]
TAG_MATGROUP = dmodel.TAGS_INV["material_group"]
TAG_MATERIAL = dmodel.TAGS_INV["material"]

MAX_UINT16_INDICES = 65535
MAX_UINT16_VERTS = 65536

# g_body stacks the outfit over the swimsuit and underwear layers; they occupy
# the same torso surface and are hidden by the outfit, so they can be dropped
# when a Topology exceeds the index limit.
REDUNDANT_BODY_MAT_HASHES = frozenset(
    {dmodel.hash_str("lawson_swim"), dmodel.hash_str("lawson_under")}
)


@dataclass(frozen=True)
class SkinPaletteIssue:
    section_id: int
    bone_count: int
    set_count: int
    out_of_range_indices: tuple[int, ...]
    matches_object_ids: bool


def parse_model_bytes(data: bytes) -> tuple[list[dmodel.Section], bool, int | None, int, dict[int, dmodel.Section]]:
    """Parse a Diesel .model binary buffer using dmodel's section readers."""
    sections, legacy, version, filesize = dmodel.read_container(data)
    hl = dmodel.Hashlist()
    by_id: dict[int, dmodel.Section] = {}
    for sec in sections:
        cls = dmodel.PARSERS.get(sec.tag)
        if cls:
            br = dmodel.BR(data)
            br.p = sec.start
            obj = cls()
            obj.parse(br, sec, hl)
            sec.obj = obj
        else:
            sec.obj = None
        by_id[sec.id] = sec
    return sections, legacy, version, filesize, by_id


def inspect_model_skin_palettes(data: bytes) -> list[SkinPaletteIssue]:
    """Return all SkinBones sections whose bone_mappings contain invalid indices."""
    sections, _, _, _, _ = parse_model_bytes(data)
    issues: list[SkinPaletteIssue] = []
    for sec in sections:
        if sec.type != TAG_SKINBONES:
            continue
        sb: dmodel.SkinBones = sec.obj
        bone_count = sb.count
        bad: list[int] = []
        for mapping in sb.bone_mappings:
            for idx in mapping:
                if idx < 0 or idx >= bone_count:
                    bad.append(idx)
        if bad:
            matches_obj_ids = all(
                list(mapping) == list(sb.object_ids) for mapping in sb.bone_mappings
            )
            issues.append(
                SkinPaletteIssue(
                    section_id=sec.id,
                    bone_count=bone_count,
                    set_count=len(sb.bone_mappings),
                    out_of_range_indices=tuple(bad),
                    matches_object_ids=matches_obj_ids,
                )
            )
    return issues


def _check_section_refs(sections, by_id) -> list[str]:
    """Every section-ID reference must resolve to an existing section."""
    errors: list[str] = []
    ids = set(by_id)

    def need(owner, label, ref, want_tag=None):
        if ref == 0:
            return
        target = by_id.get(ref)
        if target is None:
            errors.append(f"Section {owner}: dangling {label} reference {ref}")
        elif want_tag is not None and target.tag not in want_tag:
            errors.append(
                f"Section {owner}: {label} reference {ref} is {target.tag}, expected {want_tag}"
            )

    for sec in sections:
        o = sec.obj
        if o is None:
            continue
        if sec.tag in ("object3D", "model_data"):
            for aid, _ in o.anim_ids:
                need(sec.id, "anim", aid)
            need(sec.id, "parent", o.parent_id)
            if sec.type == TAG_MODEL and o.version != 6:
                need(sec.id, "passthrough", o.passthrough_id, ("passthroughGP",))
                need(sec.id, "topologyip", o.topologyip_id, ("topologyIP",))
                need(sec.id, "material_group", o.matgroup_id, ("material_group",))
                need(sec.id, "lightset", o.lightset_id)
                if o.skinbones_id:
                    need(sec.id, "skinbones", o.skinbones_id, ("skinbones",))
        elif sec.type == TAG_MATGROUP:
            for mid in o.items:
                need(sec.id, "material_group item", mid, ("material",))
        elif sec.type == TAG_PASSTHROUGH:
            need(sec.id, "geometry", o.geometry_id, ("geometry",))
            need(sec.id, "topology", o.topology_id, ("topology",))
        elif sec.type == TAG_TOPOLOGY_IP:
            need(sec.id, "topology", o.topology_id, ("topology",))
        elif sec.type == TAG_SKINBONES:
            need(sec.id, "root bone", o.root_bone_id)
            for oid in o.object_ids:
                need(sec.id, "bone object", oid)
    return errors


def validate_model_skinning(data: bytes, strict_layout: bool = False) -> list[str]:
    """Validate container layout, SkinBones palettes, and skinned Geometry indices.

    strict_layout additionally enforces the vanilla DODB layout: contiguous
    1..count section IDs and the canonical section order (see module docstring).
    """
    errors: list[str] = []
    sections, legacy, version, filesize, by_id = parse_model_bytes(data)
    if not legacy and version != 1:
        errors.append(f"Unexpected DODB version {version}")
    if filesize != len(data):
        errors.append(f"Header filesize {filesize} != actual {len(data)}")

    ids = [s.id for s in sections]
    if len(set(ids)) != len(ids):
        errors.append("Duplicate section IDs")
    if strict_layout and ids != list(range(1, len(sections) + 1)):
        errors.append(
            f"Section IDs are not contiguous 1..{len(sections)} "
            f"(min={min(ids) if ids else 0}, max={max(ids) if ids else 0})"
        )
    pos = {s.id: idx for idx, s in enumerate(sections)}

    for idx, sec in enumerate(sections):
        if sec.start <= 0 or sec.end > len(data):
            errors.append(
                f"Section {sec.id} ({sec.tag}) bounds {sec.start}..{sec.end} exceed {len(data)}"
            )
        if strict_layout and sec.type == TAG_TOPOLOGY:
            topo: dmodel.Topology = sec.obj
            n_idx = len(topo.faces) * 3
            if n_idx > MAX_UINT16_INDICES:
                errors.append(
                    f"Topology {sec.id}: index count {n_idx} exceeds uint16 max {MAX_UINT16_INDICES}"
                )
        elif strict_layout and sec.type == TAG_GEOMETRY:
            geom: dmodel.DieselGeometry = sec.obj
            if geom.vert_count > MAX_UINT16_VERTS:
                errors.append(
                    f"Geometry {sec.id}: vert_count {geom.vert_count} exceeds uint16 index range"
                )
        elif strict_layout and sec.type == TAG_PASSTHROUGH:
            pg: dmodel.PassthroughGP = sec.obj
            if pos.get(pg.geometry_id, idx + 1) > idx or pos.get(pg.topology_id, idx + 1) > idx:
                errors.append(
                    f"PassthroughGP {sec.id} precedes its Geometry ({pg.geometry_id}) or Topology ({pg.topology_id})"
                )
        elif strict_layout and sec.type == TAG_TOPOLOGY_IP:
            tip: dmodel.TopologyIP = sec.obj
            if pos.get(tip.topology_id, idx + 1) > idx:
                errors.append(f"TopologyIP {sec.id} precedes its Topology ({tip.topology_id})")

    errors.extend(_check_section_refs(sections, by_id))

    for sec in sections:
        if sec.type != TAG_SKINBONES:
            continue
        sb: dmodel.SkinBones = sec.obj
        bone_count = sb.count
        if bone_count <= 0 or len(sb.object_ids) != bone_count or len(sb.rotations) != bone_count:
            errors.append(
                f"SkinBones {sec.id}: invalid count ({bone_count}) / object_ids ({len(sb.object_ids)}) "
                f"/ rotations ({len(sb.rotations)})"
            )
        if sb.remaining:
            errors.append(f"SkinBones {sec.id}: unexpected trailing bytes ({len(sb.remaining)})")
        if not sb.bone_mappings:
            errors.append(f"SkinBones {sec.id}: empty bone_mappings")
        for set_idx, mapping in enumerate(sb.bone_mappings):
            if len(mapping) != bone_count:
                errors.append(
                    f"SkinBones {sec.id} set {set_idx}: mapping length {len(mapping)} != bone_count {bone_count}"
                )
            bad = [idx for idx in mapping if idx < 0 or idx >= bone_count]
            if bad:
                errors.append(
                    f"SkinBones {sec.id} set {set_idx}: {len(bad)} out-of-range indices "
                    f"(max={max(bad)}, bone_count={bone_count})"
                )

    for idx, sec in enumerate(sections):
        if sec.type != TAG_MODEL:
            continue
        md: dmodel.Model = sec.obj
        if md.version == 6:
            continue
        if strict_layout and pos.get(md.matgroup_id, idx + 1) > idx:
            errors.append(f"Model {sec.id} precedes its MaterialGroup {md.matgroup_id}")
        if getattr(md, "skinbones_id", 0) == 0:
            continue
        sb_sec = by_id.get(md.skinbones_id)
        if sb_sec is None or sb_sec.type != TAG_SKINBONES:
            errors.append(f"Model {sec.id}: missing SkinBones section {md.skinbones_id}")
            continue
        sb: dmodel.SkinBones = sb_sec.obj
        if len(sb.bone_mappings) < len(md.render_atoms):
            errors.append(
                f"Model {sec.id}: SkinBones {md.skinbones_id} has {len(sb.bone_mappings)} sets "
                f"for {len(md.render_atoms)} atoms"
            )
        pg_sec = by_id.get(md.passthrough_id)
        if pg_sec is None or pg_sec.type != TAG_PASSTHROUGH:
            errors.append(f"Model {sec.id}: missing PassthroughGP {md.passthrough_id}")
            continue
        pg = pg_sec.obj
        geom_sec = by_id.get(pg.geometry_id)
        if geom_sec is None or geom_sec.type != TAG_GEOMETRY:
            errors.append(f"Model {sec.id}: missing Geometry {pg.geometry_id}")
            continue
        geom: dmodel.DieselGeometry = geom_sec.obj
        if len(geom.joints) != geom.vert_count:
            errors.append(
                f"Model {sec.id}: Geometry {pg.geometry_id} blend index count "
                f"{len(geom.joints)} != vert_count {geom.vert_count}"
            )
            continue
        for atom_idx, atom in enumerate(md.render_atoms):
            palette_len = len(sb.bone_mappings[atom_idx])
            v0 = atom["base_vertex"]
            v1 = v0 + atom["geo_len"]
            for vi in range(v0, v1):
                w4 = geom.weights4(vi)
                for slot_idx, bi in enumerate(geom.joints[vi]):
                    if slot_idx < len(w4) and w4[slot_idx] == 0.0 and bi == 0:
                        continue
                    if bi < 0 or bi >= palette_len:
                        errors.append(
                            f"Model {sec.id} atom {atom_idx} vert {vi}: blend index {bi} >= palette_len {palette_len}"
                        )
                        break
    return errors


def repair_model_skin_palettes(data: bytes) -> tuple[bytes, list[int]]:
    """Rewrite any out-of-range SkinBones.bone_mappings in place to 0..bone_count-1.

    Returns (repaired_bytes, repaired_section_ids).
    """
    sections, _, _, _, _ = parse_model_bytes(data)
    buf = bytearray(data)
    repaired_ids: list[int] = []

    for sec in sections:
        if sec.type != TAG_SKINBONES:
            continue
        sb: dmodel.SkinBones = sec.obj
        bone_count = sb.count
        has_bad = any(
            idx < 0 or idx >= bone_count
            for mapping in sb.bone_mappings
            for idx in mapping
        )
        if not has_bad:
            continue
        if any(len(mapping) != bone_count for mapping in sb.bone_mappings):
            raise ValueError(
                f"SkinBones section {sec.id} mapping lengths {[len(m) for m in sb.bone_mappings]} "
                f"do not match bone_count {bone_count}; cannot patch in place"
            )
        rebuilt_bones = bytearray()
        rebuilt_bones += struct.pack("<I", len(sb.bone_mappings))
        local_palette = struct.pack(f"<{bone_count}I", *range(bone_count))
        for _ in sb.bone_mappings:
            rebuilt_bones += struct.pack("<I", bone_count)
            rebuilt_bones += local_palette
        expected_bones_bytes = 4 + len(sb.bone_mappings) * (4 + 4 * bone_count)
        if len(rebuilt_bones) != expected_bones_bytes:
            raise ValueError(
                f"SkinBones section {sec.id} rebuilt header size {len(rebuilt_bones)} != {expected_bones_bytes}"
            )
        buf[sec.start : sec.start + expected_bones_bytes] = rebuilt_bones
        repaired_ids.append(sec.id)

    repaired = bytes(buf)
    errors = validate_model_skinning(repaired)
    if errors:
        raise ValueError("Repaired model failed validation: " + "; ".join(errors[:5]))
    return repaired, repaired_ids


def canonical_order(sections: list[dmodel.Section], by_id) -> list[dmodel.Section]:
    """Vanilla DODB section order (see module docstring)."""
    ordered: list[dmodel.Section] = []
    seen: set[int] = set()

    def add(sec: dmodel.Section | None) -> None:
        if sec is not None and sec.id not in seen:
            seen.add(sec.id)
            ordered.append(sec)

    for sec in sections:
        if sec.tag in ("animation_data", "author"):
            add(sec)
    for sec in sections:
        if sec.type == TAG_MATGROUP:
            add(sec)
            for mid in sec.obj.items:
                add(by_id.get(mid))
    for sec in sections:
        if sec.type == TAG_MATERIAL:
            add(sec)
    for sec in sections:
        if sec.tag in ("object3D", "model_data"):
            add(sec)
    models = [
        s
        for s in sections
        if s.type == TAG_MODEL and s.obj.version != 6
    ]
    unskinned = [s for s in models if not getattr(s.obj, "skinbones_id", 0)]
    skinned = [s for s in models if getattr(s.obj, "skinbones_id", 0)]
    for sec in unskinned + skinned:
        md = sec.obj
        if md.skinbones_id:
            add(by_id.get(md.skinbones_id))
        pg = by_id[md.passthrough_id].obj
        add(by_id.get(pg.geometry_id))
        add(by_id.get(pg.topology_id))
        add(by_id.get(md.passthrough_id))
        add(by_id.get(md.topologyip_id))
    for sec in sections:
        add(sec)
    return ordered


def _trim_redundant_atoms(
    sections, by_id, raw_by_id: dict[int, bytearray], md_sec: dmodel.Section
) -> bool:
    """Drop hidden lawson_swim / lawson_under atoms from an over-limit model."""
    md = md_sec.obj
    if md.version == 6 or len(md.render_atoms) <= 1:
        return False
    pg_sec = by_id[md.passthrough_id]
    geom_sec = by_id[pg_sec.obj.geometry_id]
    topo_sec = by_id[pg_sec.obj.topology_id]
    mg_sec = by_id[md.matgroup_id]
    sb_sec = by_id.get(md.skinbones_id) if md.skinbones_id else None
    geom: dmodel.DieselGeometry = geom_sec.obj
    topo: dmodel.Topology = topo_sec.obj
    mg: dmodel.MaterialGroup = mg_sec.obj
    if len(topo.faces) * 3 <= MAX_UINT16_INDICES:
        return False

    kept: list[tuple[dict, int, int]] = []  # (atom, material section id, atom index)
    for atom_idx, atom in enumerate(md.render_atoms):
        mat_sid = mg.items[atom["material_id"]]
        mat = by_id[mat_sid].obj
        if mat.name_hash in REDUNDANT_BODY_MAT_HASHES:
            continue
        kept.append((atom, mat_sid, atom_idx))
    if not kept or len(kept) == len(md.render_atoms):
        raise ValueError(
            f"Model {md_sec.id}: Topology {topo_sec.id} has {len(topo.faces) * 3} indices "
            f"(> {MAX_UINT16_INDICES}) and no redundant layers to drop"
        )

    g_raw = bytes(raw_by_id[geom_sec.id])
    hdr_end = 8 + 8 * len(geom.headers)
    old_n = geom.vert_count
    new_n = sum(a["geo_len"] for a, _, _ in kept)
    new_g = bytearray(struct.pack("<II", new_n, len(geom.headers)))
    new_g += g_raw[8:hdr_end]
    ch_off = hdr_end
    sizes = dmodel.DieselGeometry.RAID_SIZES if geom.format == "raid" else dmodel.DieselGeometry.PAYDAY_SIZES
    for isz_code, _ity in geom.headers:
        isz = sizes[isz_code]
        for atom, _, _ in kept:
            v0 = atom["base_vertex"]
            vlen = atom["geo_len"]
            new_g += g_raw[ch_off + v0 * isz : ch_off + (v0 + vlen) * isz]
        ch_off += old_n * isz
    new_g += g_raw[ch_off:]
    raw_by_id[geom_sec.id] = new_g

    new_faces: list[tuple[int, int, int]] = []
    new_atoms: list[dict[str, int]] = []
    new_mat_ids: list[int] = []
    new_base_v = 0
    new_base_idx = 0
    for atom, mat_sid, _ in kept:
        if mat_sid not in new_mat_ids:
            new_mat_ids.append(mat_sid)
        new_mat_idx = new_mat_ids.index(mat_sid)
        old_v0 = atom["base_vertex"]
        vlen = atom["geo_len"]
        f0 = atom["base_index"] // 3
        fcnt = atom["tri_count"]
        v_shift = new_base_v - old_v0
        for a, b, c in topo.faces[f0 : f0 + fcnt]:
            new_faces.append((a + v_shift, b + v_shift, c + v_shift))
        new_atoms.append(
            {
                "base_vertex": new_base_v,
                "tri_count": fcnt,
                "base_index": new_base_idx,
                "geo_len": vlen,
                "material_id": new_mat_idx,
            }
        )
        new_base_v += vlen
        new_base_idx += fcnt * 3

    new_t = bytearray(struct.pack("<II", topo.primitive, len(new_faces) * 3))
    for a, b, c in new_faces:
        new_t += struct.pack("<3H", a, b, c)
    new_t += struct.pack("<I", len(topo.items2)) + topo.items2
    new_t += struct.pack("<Q", topo.name_hash) + topo.remaining
    raw_by_id[topo_sec.id] = new_t

    raw_by_id[mg_sec.id] = bytearray(
        struct.pack(f"<I{len(new_mat_ids)}I", len(new_mat_ids), *new_mat_ids)
    )
    mg.items = new_mat_ids

    if sb_sec is not None:
        sb: dmodel.SkinBones = sb_sec.obj
        old_sets = sb.bone_mappings
        if len(old_sets) == len(md.render_atoms) + 1:
            new_sets = [old_sets[i] for _, _, i in kept] + [old_sets[-1]]
        elif len(old_sets) == len(md.render_atoms):
            new_sets = [old_sets[i] for _, _, i in kept]
        else:
            raise ValueError(
                f"SkinBones {sb_sec.id}: {len(old_sets)} sets for {len(md.render_atoms)} atoms"
            )
        sb_raw = bytes(raw_by_id[sb_sec.id])
        old_bones_bytes = 4 + sum(4 + 4 * len(m) for m in old_sets)
        new_sb = bytearray(struct.pack("<I", len(new_sets)))
        for mapping in new_sets:
            new_sb += struct.pack("<I", len(mapping))
            new_sb += struct.pack(f"<{len(mapping)}I", *mapping)
        new_sb += sb_raw[old_bones_bytes:]
        raw_by_id[sb_sec.id] = new_sb

    md_raw = bytes(raw_by_id[md_sec.id])
    obj_prefix_len = 8 + 4 + 12 * len(md.anim_ids) + 64 + 12 + 4
    old_atoms_end = obj_prefix_len + 16 + 20 * len(md.render_atoms)
    new_md = bytearray(md_raw[:obj_prefix_len])
    new_md += struct.pack("<III", md.version, md.passthrough_id, md.topologyip_id)
    new_md += struct.pack("<I", len(new_atoms))
    for a in new_atoms:
        new_md += struct.pack(
            "<5I",
            a["base_vertex"],
            a["tri_count"],
            a["base_index"],
            a["geo_len"],
            a["material_id"],
        )
    new_md += md_raw[old_atoms_end:]
    raw_by_id[md_sec.id] = new_md
    md.render_atoms = new_atoms
    return True


def normalize_model_container(data: bytes) -> tuple[bytes, list[int]]:
    """Repair SkinBones palettes, trim over-limit meshes, canonicalize the layout.

    Reorders sections into the vanilla DODB order and renumbers them
    contiguously 1..count, remapping every internal section-ID reference.
    Returns (normalized_bytes, modified_section_ids) where the IDs are the
    pre-normalization IDs of repaired SkinBones / trimmed Model sections.
    """
    data, fixed_skin_ids = repair_model_skin_palettes(data)
    sections, legacy, version, _filesize, by_id = parse_model_bytes(data)
    if legacy:
        return data, fixed_skin_ids

    raw_by_id: dict[int, bytearray] = {
        s.id: bytearray(data[s.start : s.end]) for s in sections
    }
    trimmed_model_ids: list[int] = []
    for sec in sections:
        if sec.type == TAG_MODEL and _trim_redundant_atoms(sections, by_id, raw_by_id, sec):
            trimmed_model_ids.append(sec.id)

    ordered = canonical_order(sections, by_id)
    if len(ordered) != len(sections):
        raise ValueError(
            f"Canonical order lost sections ({len(ordered)} of {len(sections)})"
        )

    id_map = {sec.id: idx + 1 for idx, sec in enumerate(ordered)}
    id_map[0] = 0
    for sec in ordered:
        b = raw_by_id[sec.id]
        if sec.tag in ("object3D", "model_data"):
            n_anim = struct.unpack_from("<I", b, 8)[0]
            for i in range(n_anim):
                off = 12 + i * 12
                aid = struct.unpack_from("<I", b, off)[0]
                struct.pack_into("<I", b, off, id_map[aid])
            parent_off = 12 + n_anim * 12 + 64 + 12
            pid = struct.unpack_from("<I", b, parent_off)[0]
            struct.pack_into("<I", b, parent_off, id_map[pid])
            if sec.type == TAG_MODEL:
                ver_off = parent_off + 4
                ver = struct.unpack_from("<I", b, ver_off)[0]
                if ver != 6:
                    gp_id, tp_id, n_atoms = struct.unpack_from("<3I", b, ver_off + 4)
                    struct.pack_into("<II", b, ver_off + 4, id_map[gp_id], id_map[tp_id])
                    mg_off = ver_off + 16 + 20 * n_atoms
                    mg_id, ls_id, _prop = struct.unpack_from("<3I", b, mg_off)
                    struct.pack_into("<II", b, mg_off, id_map[mg_id], id_map.get(ls_id, ls_id))
                    sb_off = mg_off + 12 + 24 + 8
                    sb_id = struct.unpack_from("<I", b, sb_off)[0]
                    struct.pack_into("<I", b, sb_off, id_map.get(sb_id, sb_id))
        elif sec.type == TAG_MATGROUP:
            cnt = struct.unpack_from("<I", b, 0)[0]
            for i in range(cnt):
                off = 4 + i * 4
                mid = struct.unpack_from("<I", b, off)[0]
                struct.pack_into("<I", b, off, id_map[mid])
        elif sec.type == TAG_PASSTHROUGH:
            gid, tid = struct.unpack_from("<II", b, 0)
            struct.pack_into("<II", b, 0, id_map[gid], id_map[tid])
        elif sec.type == TAG_TOPOLOGY_IP:
            tid = struct.unpack_from("<I", b, 0)[0]
            struct.pack_into("<I", b, 0, id_map[tid])
        elif sec.type == TAG_SKINBONES:
            n_maps = struct.unpack_from("<I", b, 0)[0]
            off = 4
            for _ in range(n_maps):
                mcnt = struct.unpack_from("<I", b, off)[0]
                off += 4 + 4 * mcnt
            root_id, count = struct.unpack_from("<II", b, off)
            struct.pack_into("<I", b, off, id_map[root_id])
            off += 8
            for i in range(count):
                oid = struct.unpack_from("<I", b, off + i * 4)[0]
                struct.pack_into("<I", b, off + i * 4, id_map[oid])

    body = bytearray()
    for idx, sec in enumerate(ordered):
        payload = raw_by_id[sec.id]
        body += struct.pack("<III", sec.type, idx + 1, len(payload))
        body += payload
    header = struct.pack("<4I", 0x42444F44, 1, 16 + len(body), len(ordered))
    out_bytes = header + bytes(body)

    errors = validate_model_skinning(out_bytes, strict_layout=True)
    if errors:
        raise ValueError("Normalized model failed validation: " + "; ".join(errors[:5]))
    return out_bytes, fixed_skin_ids + trimmed_model_ids


def repair_archive_skin_palettes(
    archive: Path, normalize_container: bool = True
) -> dict[str, list[int]]:
    """Atomically repair all .model and .texture files in a Lawson ZIP and refresh metadata.

    Returns {entry: [old section ids]} for every .model entry.
    """
    character = archive.stem.removeprefix("lawson_")
    prefix = f"lawson_{character}/"
    temporary = None
    repaired_by_entry: dict[str, list[int]] = {}
    try:
        with ZipFile(archive) as source:
            names = source.namelist()
            if not names or any(not n.startswith(prefix) for n in names):
                raise ValueError(f"Unexpected ZIP root in {archive}")
            if len(names) != len(set(names)):
                raise ValueError(f"Duplicate ZIP entries in {archive}")
            textures = [n[len(prefix) :] for n in names if n.endswith(".texture")]
            metadata = package_metadata.package_metadata(character, textures)
            with tempfile.NamedTemporaryFile(
                dir=archive.parent, suffix=".zip", delete=False
            ) as tmp:
                temporary = Path(tmp.name)
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as output:
                output.comment = source.comment
                for info in source.infolist():
                    if info.filename in {prefix + n for n in metadata}:
                        continue
                    payload = source.read(info)
                    if info.filename.endswith(".model"):
                        if normalize_container:
                            payload, fixed_ids = normalize_model_container(payload)
                        else:
                            payload, fixed_ids = repair_model_skin_palettes(payload)
                        repaired_by_entry[info.filename] = fixed_ids
                    elif (
                        info.filename.endswith(".texture")
                        and len(payload) >= dds.DDS_HEADER_SIZE
                        and payload[:4] == b"DDS "
                    ):
                        payload, _ = dds.repair_dxt5_texture(payload)
                    output.writestr(info, payload)
                for name, data in metadata.items():
                    output.writestr(prefix + name, data)
        temporary.replace(archive)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return repaired_by_entry


def inspect_target(path: Path) -> dict[str, list[str]]:
    """Validate a .model file or a .zip containing .model and .texture files."""
    if path.suffix == ".model":
        errs = validate_model_skinning(path.read_bytes(), strict_layout=True)
        return {str(path): errs} if errs else {}
    if path.suffix == ".zip":
        problems: dict[str, list[str]] = {}
        with ZipFile(path) as zf:
            model_names = [n for n in zf.namelist() if n.endswith(".model")]
            if not model_names:
                problems[str(path)] = ["Archive contains no .model files"]
            for name in model_names:
                errs = validate_model_skinning(zf.read(name), strict_layout=True)
                if errs:
                    problems[f"{path}:{name}"] = errs
            for name in zf.namelist():
                if name.endswith(".texture"):
                    raw = zf.read(name)
                    if len(raw) >= dds.DDS_HEADER_SIZE and raw[:4] == b"DDS ":
                        tex_errs = dds.validate_dxt5_texture(raw)
                        if tex_errs:
                            problems[f"{path}:{name}"] = tex_errs
        return problems
    raise ValueError(f"Unsupported target {path}; expected .model or .zip")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path, nargs="+", help=".zip or .model files")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only; exit non-zero if any .model or .texture errors exist",
    )
    args = parser.parse_args()

    if args.check:
        had_errors = False
        for target in args.targets:
            problems = inspect_target(target)
            if problems:
                had_errors = True
                for key, errs in problems.items():
                    for err in errs:
                        print(f"FAIL {key}: {err}")
            else:
                print(f"OK   {target}")
        if had_errors:
            raise SystemExit(1)
        return

    for target in args.targets:
        if target.suffix == ".model":
            repaired, fixed_ids = normalize_model_container(target.read_bytes())
            target.write_bytes(repaired)
            print(f"Repaired {target}: sections {fixed_ids}")
        elif target.suffix == ".zip":
            report = repair_archive_skin_palettes(target)
            print(f"Repaired {target}: {report}")
        else:
            raise ValueError(f"Unsupported target {target}; expected .model or .zip")


if __name__ == "__main__":
    main()
