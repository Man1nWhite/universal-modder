#!/usr/bin/env python3
"""Author DODB .model containers for the LAS outfit units.

Builds a complete Diesel 3 (DODB) model from the PD2 rig contract
(``reference/las_rig.json``) plus retargeted meshes (``rig_target.RiggedMesh``).

Layout follows the canonical vanilla container order recovered in the retired
route's audits (contiguous 1-based section IDs; ``[material_group, its
materials]`` blocks; object3D/model_data in hierarchy order; then mesh groups
``[skinbones, geometry, topology, passthroughGP, topologyIP]``). Serialization
carries over the proven details of the retired ``build_model.py`` writer:

- topology indices are absolute (verified against vanilla multi-atom meshes);
- SkinBones mappings are 0-based local palette indices;
- ``SkinBones.rotations = inv(bone_world)`` and
  ``Global_skin_transform = Hips world``;
- drawable ``model_data`` transform is ``inv(Hips world)`` (verified against the
  2B reference), vertices in PD2 root space (cm);
- geometry channels: POSITION0 float3, TEXCOORD0 half2 (V negated in file),
  BLENDINDICES0 u16x4, BLENDWEIGHT0 f32x3, NORMAL0 + UV direction vectors
  packed (``SKINNED_3WEIGHTS`` compatible);
- render-atom ``MaterialId`` is the index into the drawable's material_group
  items (per the upstream ModelReader), so each drawable gets a group listing
  exactly its materials.

No index-count trimming: counts are u32 and references u16; a drawable is
capped only by 65,536 vertices (topology index width) — checked explicitly.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

from dmodel import TAGS_INV, hash_str
from me2_dae import minv
from rig_target import TargetRig

M64MASK = 0xFFFFFFFFFFFFFFFF
MAX_VERTS = 65536
MAX_PALETTE = 64


class BW:
    def __init__(self):
        self.b = bytearray()

    def u32(self, v): self.b += struct.pack('<I', v & 0xFFFFFFFF)
    def u64(self, v): self.b += struct.pack('<Q', v & M64MASK)
    def f32(self, v): self.b += struct.pack('<f', v)
    def u16(self, v): self.b += struct.pack('<H', v & 0xFFFF)
    def raw(self, d): self.b += d

    def matrix(self, rows):
        for r in range(4):
            for c in range(4):
                self.f32(rows[r][c])

    def vec3(self, v):
        for x in v:
            self.f32(x)


def half(x: float) -> int:
    return struct.unpack('<H', struct.pack('<e', float(x)))[0]


def pack_signed_byte(v: float) -> int:
    return max(0, min(255, int(round((v * 0.5 + 0.5) * 255.0))))


def section_bytes(type_: int, sid: int, payload: bytes) -> bytes:
    w = BW()
    w.u32(type_)
    w.u32(sid)
    w.u32(len(payload))
    w.raw(payload)
    return bytes(w.b)


@dataclass
class Atom:
    """One material block of a drawable (geometry is packed per atom)."""
    material: str
    positions: list[tuple[float, float, float]]
    normals: list[tuple[float, float, float]]
    uvs: list[tuple[float, float]]
    weights: list[list[tuple[str, float]]]      # per vertex (bone, w), 1..3
    faces: list[tuple[int, int, int]]           # vertex indices, atom-local


@dataclass
class Drawable:
    name: str
    atoms: list[Atom]


@dataclass
class BuildResult:
    data: bytes
    section_count: int
    drawables: dict[str, dict] = field(default_factory=dict)


def _norm3(v):
    ln = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / ln, v[1] / ln, v[2] / ln)


def build_model(rig: TargetRig, drawables: list[Drawable], *,
                extra_materials: tuple[str, ...] = ("shadow_caster",),
                cull_name: str = "c_block") -> BuildResult:
    """Assemble a DODB model from the rig skeleton and packed drawables."""
    entries = rig.entries                     # full main-tree object3D list
    if not any(e["name"] == "Hips" for e in entries):
        raise ValueError("rig has no Hips")
    hips = next(e for e in entries if e["name"] == "Hips")
    hips_world = hips["world"]
    inv_hips = minv(hips_world)

    # materials: per-drawable groups (canonical blocks) + extras (e.g.
    # shadow_caster) as standalone singleton groups. Shared materials across
    # drawables are rejected: each group lists exactly its drawable's materials.
    drawable_mats: dict[str, list[str]] = {}
    for dr in drawables:
        mats: list[str] = []
        for atom in dr.atoms:
            if atom.material not in mats:
                mats.append(atom.material)
        if not dr.atoms:
            raise ValueError(f"drawable {dr.name} has no atoms")
        drawable_mats[dr.name] = mats
    used = [m for mats in drawable_mats.values() for m in mats]
    if len(used) != len(set(used)):
        raise ValueError("materials shared across drawables; give each drawable its own")
    extra = [m for m in extra_materials if m not in used]

    # ---------- pack geometry per drawable ----------
    packed = []
    for dr in drawables:
        pal: list[str] = []
        for atom in dr.atoms:
            for wts in atom.weights:
                for n, _ in wts:
                    if n not in pal:
                        pal.append(n)
        if len(pal) > MAX_PALETTE:
            raise ValueError(f"{dr.name}: palette {len(pal)} > {MAX_PALETTE}")
        order = {e["name"]: e["id"] for e in entries if e["name"]}
        pal.sort(key=lambda n: order.get(n, 1 << 30))
        positions, normals, uvs, weights4 = [], [], [], []
        faces: list[tuple[int, int, int]] = []
        atom_ranges = []
        base_v = 0
        base_index = 0
        mats = drawable_mats[dr.name]
        for atom in dr.atoms:
            if not (len(atom.positions) == len(atom.normals)
                    == len(atom.uvs) == len(atom.weights)):
                raise ValueError(f"{dr.name}/{atom.material}: channel length mismatch")
            n_verts = len(atom.positions)
            if base_v + n_verts > MAX_VERTS:
                raise ValueError(f"{dr.name}: {base_v + n_verts} vertices > {MAX_VERTS}")
            for a, b, c in atom.faces:
                faces.append((a + base_v, b + base_v, c + base_v))
            for i in range(n_verts):
                positions.append(atom.positions[i])
                normals.append(atom.normals[i])
                uvs.append(atom.uvs[i])
                ent = []
                for name, w in atom.weights[i]:
                    if name not in pal:
                        raise ValueError(f"{dr.name}: weight bone {name} not in palette")
                    if w != w or w < -1e-6:
                        raise ValueError(f"{dr.name}: invalid weight {w}")
                    ent.append((pal.index(name), max(0.0, w)))
                if not ent:
                    ent = [(pal.index("Hips") if "Hips" in pal else 0, 1.0)]
                while len(ent) < 3:
                    ent.append((0, 0.0))
                tot = sum(w for _, w in ent) or 1.0
                weights4.append(tuple((i, w / tot) for i, w in ent[:3]))
            atom_ranges.append((base_v, n_verts, base_index, len(atom.faces),
                                mats.index(atom.material)))
            base_v += n_verts
            base_index += len(atom.faces) * 3
        packed.append({
            "name": dr.name,
            "positions": positions,
            "normals": normals,
            "uvs": uvs,
            "weights": weights4,
            "faces": faces,
            "atoms": atom_ranges,
            "pal": pal,
        })

    # ---------- section id assignment (canonical order) ----------
    next_id = 1

    def take():
        nonlocal next_id
        v = next_id
        next_id += 1
        return v

    group_ids: dict[str, int] = {}        # drawable name or extra material
    mat_ids: dict[str, int] = {}
    for dr in drawables:
        group_ids[dr.name] = take()
        for m in drawable_mats[dr.name]:
            mat_ids[m] = take()
    for m in extra:
        group_ids[m] = take()
        mat_ids[m] = take()

    bone_new: dict[int, int] = {}         # rig entry id -> new section id
    for e in entries:
        bone_new[e["id"]] = take()
    cull_id = take()
    drawable_ids = {p["name"]: take() for p in packed}
    mesh_ids = {p["name"]: {k: take() for k in
                            ("skinbones", "geometry", "topology", "passthrough", "topologyip")}
                for p in packed}
    total = next_id - 1

    # ---------- payloads ----------
    body = BW()
    count = 0

    def emit(type_, sid, payload):
        nonlocal count
        body.raw(section_bytes(type_, sid, payload))
        count += 1

    def material_payload(name: str) -> bytes:
        # name hash + fixed 48 constant bytes (identical across all 2B
        # reference materials) + 0 items: texture binding lives in the XML
        # material_config, not here.
        w = BW()
        w.u64(hash_str(name))
        w.raw(bytes.fromhex('00000000000000000000000000000000000000000000803f'
                            '0000000000000000000000000000803f0000000000000000'))
        w.u32(0)
        return bytes(w.b)

    def group_payload(mats: list[str]) -> bytes:
        w = BW()
        w.u32(len(mats))
        for m in mats:
            w.u32(mat_ids[m])
        return bytes(w.b)

    for dr in drawables:
        mats = drawable_mats[dr.name]
        emit(TAGS_INV['material_group'], group_ids[dr.name], group_payload(mats))
        for m in mats:
            emit(TAGS_INV['material'], mat_ids[m], material_payload(m))
    for m in extra:
        emit(TAGS_INV['material_group'], group_ids[m], group_payload([m]))
        emit(TAGS_INV['material'], mat_ids[m], material_payload(m))

    for e in entries:
        w = BW()
        w.u64(int(e["name_hash"], 16))
        w.u32(0)                                    # anim_ids
        rows = e["local"]
        w.matrix(rows)
        w.vec3((rows[3][0], rows[3][1], rows[3][2]))
        w.u32(bone_new.get(e["parent_id"], 0))
        emit(TAGS_INV['object3D'], bone_new[e["id"]], bytes(w.b))

    all_pos = [p for pack in packed for p in pack["positions"]]
    if all_pos:
        bmin = tuple(min(p[i] for p in all_pos) for i in range(3))
        bmax = tuple(max(p[i] for p in all_pos) for i in range(3))
        rad = max(math.sqrt(x * x + y * y + z * z) for x, y, z in all_pos)
    else:
        bmin, bmax, rad = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0

    def model_payload(name_hash, atoms, mg_id, sb_id, bounds, gp_id, tp_id) -> bytes:
        w = BW()
        w.u64(name_hash)
        w.u32(0)                                    # anim_ids
        w.matrix(inv_hips)
        w.vec3((inv_hips[3][0], inv_hips[3][1], inv_hips[3][2]))
        w.u32(bone_new[hips["id"]])                 # parent = Hips (2B convention)
        w.u32(3)                                    # version 3
        w.u32(gp_id)
        w.u32(tp_id)
        w.u32(len(atoms))
        for base_vertex, n_verts, base_index, tri_count, mat_index in atoms:
            w.u32(base_vertex)
            w.u32(tri_count)
            w.u32(base_index)
            w.u32(n_verts)
            w.u32(mat_index)
        w.u32(mg_id)
        w.u32(0)                                    # lightset
        w.u32(3)                                    # properties (2B: 3)
        w.vec3(bounds[0])
        w.vec3(bounds[1])
        w.f32(bounds[2])
        w.u32(0)                                    # bounding_int
        w.u32(sb_id)
        return bytes(w.b)

    emit(TAGS_INV['model_data'], cull_id,
         model_payload(hash_str(cull_name), [], 0, 0, (bmin, bmax, rad), 0, 0))

    for p in packed:
        xs = [q[0] for q in p["positions"]]
        ys = [q[1] for q in p["positions"]]
        zs = [q[2] for q in p["positions"]]
        bounds = ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)),
                  max(math.sqrt(x * x + y * y + z * z)
                      for x, y, z in p["positions"]))
        ids = mesh_ids[p["name"]]
        emit(TAGS_INV['model_data'], drawable_ids[p["name"]],
             model_payload(hash_str(p["name"]), p["atoms"],
                           group_ids[p["name"]], ids["skinbones"], bounds,
                           ids["passthrough"], ids["topologyip"]))

    for p in packed:
        ids = mesh_ids[p["name"]]
        pal = p["pal"]
        world_by_name = {e["name"]: e["world"] for e in entries if e["name"]}
        entry_by_name = {e["name"]: e for e in entries if e["name"]}
        pal_ids = [bone_new[entry_by_name[n]["id"]] for n in pal]
        sb = BW()
        n_atoms = len(p["atoms"])
        sb.u32(1 + n_atoms)
        for _ in range(1 + n_atoms):
            sb.u32(len(pal_ids))
            for local in range(len(pal_ids)):
                sb.u32(local)
        sb.u32(bone_new[hips["id"]])
        sb.u32(len(pal_ids))
        for pid in pal_ids:
            sb.u32(pid)
        for n in pal:
            sb.matrix(minv(world_by_name[n]))
        sb.matrix(hips_world)
        emit(TAGS_INV['skinbones'], ids["skinbones"], bytes(sb.b))

        g = BW()
        headers = [(3, 1), (9, 7), (7, 17), (3, 19), (8, 2), (8, 22), (8, 23)]
        g.u32(len(p["positions"]))
        g.u32(len(headers))
        for isz, ity in headers:
            g.u32(isz)
            g.u32(ity)
        for x, y, z in p["positions"]:
            g.vec3((x, y, z))
        for u, v in p["uvs"]:
            g.u16(half(u))
            g.u16(half(v))
        for ent in p["weights"]:
            i0, i1, i2 = (list(ent) + [(0, 0.0), (0, 0.0), (0, 0.0)])[:3]
            g.u16(i0[0]); g.u16(i1[0]); g.u16(i2[0]); g.u16(0)
        for ent in p["weights"]:
            i0, i1, i2 = (list(ent) + [(0, 0.0), (0, 0.0), (0, 0.0)])[:3]
            g.f32(i0[1]); g.f32(i1[1]); g.f32(i2[1])
        for n in p["normals"]:
            x, y, z = _norm3(n)
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y),
                         pack_signed_byte(x), 0]))
        tan_u = [[0.0, 0.0, 0.0] for _ in p["positions"]]
        tan_v = [[0.0, 0.0, 0.0] for _ in p["positions"]]
        for a, b, c in p["faces"]:
            p0, p1, p2 = p["positions"][a], p["positions"][b], p["positions"][c]
            w0, w1, w2 = p["uvs"][a], p["uvs"][b], p["uvs"][c]
            du1, dv1 = w1[0] - w0[0], w1[1] - w0[1]
            du2, dv2 = w2[0] - w0[0], w2[1] - w0[1]
            e1 = [p1[i] - p0[i] for i in range(3)]
            e2 = [p2[i] - p0[i] for i in range(3)]
            det = du1 * dv2 - du2 * dv1
            if abs(det) < 1e-12:
                continue
            r = 1.0 / det
            T = [(e1[i] * dv2 - e2[i] * dv1) * r for i in range(3)]
            B = [(e2[i] * du1 - e1[i] * du2) * r for i in range(3)]
            for vi in (a, b, c):
                for i in range(3):
                    tan_u[vi][i] += T[i]
                    tan_v[vi][i] += B[i]
        for vi in range(len(p["positions"])):
            x, y, z = _norm3(tan_v[vi])
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y),
                         pack_signed_byte(x), 0]))
        for vi in range(len(p["positions"])):
            x, y, z = _norm3(tan_u[vi])
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y),
                         pack_signed_byte(x), 0]))
        g.u64(hash_str(p["name"] + '.DieselGeometry'))
        emit(TAGS_INV['geometry'], ids["geometry"], bytes(g.b))

        t = BW()
        t.u32(3)                                    # TriangleList
        t.u32(len(p["faces"]) * 3)
        for a, b, c in p["faces"]:
            t.u16(a); t.u16(b); t.u16(c)
        t.u32(0)
        t.u64(hash_str(p["name"] + '.Topology'))
        emit(TAGS_INV['topology'], ids["topology"], bytes(t.b))

        emit(TAGS_INV['passthroughGP'], ids["passthrough"],
             struct.pack('<II', ids["geometry"], ids["topology"]))
        emit(TAGS_INV['topologyIP'], ids["topologyip"],
             struct.pack('<I', ids["topology"]))

    payload = bytes(body.b)
    out = BW()
    out.u32(0x42444F44)                             # DODB
    out.u32(1)                                      # version
    out.u32(16 + len(payload))
    out.u32(count)
    out.raw(payload)

    result = BuildResult(data=bytes(out.b), section_count=count)
    for p in packed:
        result.drawables[p["name"]] = {
            "verts": len(p["positions"]),
            "tris": len(p["faces"]),
            "palette": len(p["pal"]),
            "atoms": len(p["atoms"]),
        }
    if count != total:
        raise AssertionError(f"section count {count} != allocated {total}")
    return result
