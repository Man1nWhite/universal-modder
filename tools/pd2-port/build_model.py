#!/usr/bin/env python3
"""Build the Clover->Lawson replacement .model.

Strategy: keep Clover's object tree/section IDs/transforms/material hashes and
replace the six enabled drawable models (g_body, g_head_fem1, g_hands,
g_hair_cloth1-3) with Lawson geometry. Formats verified against the original
file: SkinBones.Rotations = inv(bone_world), Global_skin_transform = Hips world,
model.Transform = inv(Hips world), verts in root space (cm), UV V negated in file.

Output: npc_criminal_female_1.model (also copied to _menu) + texture_plan.json.
"""
import json, math, struct, sys
from pathlib import Path

WORK = Path('/home/user/pd2-work')
OUT = WORK / 'clover-lawson'
sys.path.insert(0, '/home/user/universal-modder/tools/pd2-port')
from dmodel import (DieselModel, Hashlist, hash_str, mmul, minv, TAGS_INV)
from repair_skin_palettes import normalize_model_container

MAX_PALETTE = 32

# Lawson material key -> (target drawable, PD2 material). Hair(5) splits across
# g_hair_cloth1/2/3; limbs hand-verts go to g_hands.
ASSIGN = {
    '1':  ('g_body',        'mtr_enforcer_vest'),   # Vixen outfit
    '2':  ('g_body',        'mtr_enforcer_vest'),   # Vixen outfit
    '3':  ('g_body',        'mtr_toolbag'),         # Cri_swimmers
    '4':  ('g_body',        'mtr_vest_small'),      # underwear
    '5':  ('g_hair_cloth1', 'mtr_hair_1'),          # hair (split 3-way)
    '6':  ('g_head_fem1',   'mtr_hair_2'),          # lashes
    '7':  ('g_head_fem1',   'mtr_hair_3'),          # eyes
    '8':  ('g_body',        'mtr_arms'),            # limbs (hands -> g_hands)
    '9':  ('g_body',        'mtr_arms'),            # limbs
    '10': ('g_body',        'mtr_suite_body'),      # body skin
    '11': ('g_body',        'mtr_suite_body'),      # body skin
    '12': ('g_head_fem1',   'mtr_head'),            # face
    '13': ('g_head_fem1',   'mtr_hair_1'),          # scalp
}

def pack_signed_byte(v):
    v = max(-1.0, min(1.0, v))
    return int(round((v + 1.0) * 127.5)) & 0xFF

def half(x):
    return struct.unpack('<H', struct.pack('<e', x))[0]

class BW:
    def __init__(self):
        self.b = bytearray()
    def u32(self, v): self.b += struct.pack('<I', v & 0xFFFFFFFF)
    def u64(self, v): self.b += struct.pack('<Q', v & M64MASK)
    def f32(self, v): self.b += struct.pack('<f', v)
    def u16(self, v): self.b += struct.pack('<H', v & 0xFFFF)
    def raw(self, d): self.b += d
    def matrix(self, rows):
        for i in range(16):
            self.f32(rows[i])
    def vec3(self, v):
        self.f32(v[0]); self.f32(v[1]); self.f32(v[2])

M64MASK = (1 << 64) - 1

def section_bytes(type_, sid, payload):
    w = BW()
    w.u32(type_); w.u32(sid); w.u32(len(payload)); w.raw(payload)
    return bytes(w.b)

def main():
    orig_path = OUT / 'clover/npc_criminal_female_1.model'
    hl = Hashlist(str(WORK / 'PAYDAY-2-Hashlist/hashlist'))
    m = DieselModel(str(orig_path), hl)
    worlds = m.world_rows()
    mesh = json.load(open(OUT / 'lawson_mesh.json'))

    hips = m.find_by_name('Hips')[0]
    hips_world = worlds[hips.id]
    hips_inv = minv(hips_world)

    # name -> bone section id (Object3D nodes)
    bone_id = {}
    parent_of = {}
    for s in m.objects():
        if s.tag == 'object3D':
            bone_id[s.obj.name] = s.id
            parent_of[s.id] = s.obj.parent_id

    def ancestor_in(bid, palette_ids):
        while bid and bid not in palette_ids:
            bid = parent_of.get(bid)
        return bid if bid in palette_ids else None

    # ---------- split Lawson faces into pieces ----------
    verts = mesh['verts']; uvs = mesh['uvs']; weights = mesh['weights']
    norms = mesh['normals']
    faces_by_target = {}   # target -> list of (face_v_idx_tuple, matkey, pd2mat)
    hair_faces = []
    for f in mesh['faces']:
        (tri, mslot) = f
        key = mesh['materials'][mslot]['key']
        target, pd2mat = ASSIGN[key]
        if key == '5':
            hair_faces.append((tuple(tri), key, pd2mat))
            continue
        if key in ('8', '9'):
            # hand/finger-dominated verts -> g_hands (majority of face verts)
            def dom_hand(vi):
                ws = weights.get(str(vi), [])
                return ws and ('Hand' in ws[0][0])
            if sum(dom_hand(v) for v in tri) >= 2:
                target = 'g_hands'
                pd2mat = 'mtr_hands'
        faces_by_target.setdefault(target, []).append((tuple(tri), key, pd2mat))
    # hair: split by centroid x into 3 buckets -> cloth1/2/3
    buckets = {'g_hair_cloth1': [], 'g_hair_cloth2': [], 'g_hair_cloth3': []}
    for tri, key, pd2mat in hair_faces:
        cx = sum(verts[v][0] for v in tri) / 3.0
        b = 'g_hair_cloth1' if cx < -0.05 else ('g_hair_cloth3' if cx > 0.05 else 'g_hair_cloth2')
        buckets[b].append((tri, key, pd2mat))
    for b, fl in buckets.items():
        if fl:
            faces_by_target.setdefault(b, []).extend(fl)
    print("pieces:", {k: len(v) for k, v in faces_by_target.items()})

    # ---------- section id bookkeeping ----------
    max_id = max(m.by_id)
    next_id = [max_id + 1]
    def new_id():
        v = next_id[0]; next_id[0] += 1
        return v

    # sections to drop: old geometry/topology/passGP/topoIP/skinbones of targets,
    # plus material_groups only used by targets
    target_secs = {}
    for name in faces_by_target:
        hit = m.find_by_name(name)[0]
        target_secs[name] = hit
    drop = set()
    group_use = {}  # matgroup id -> set of model section ids
    for s in m.sections:
        if s.tag == 'model_data' and hasattr(s.obj, 'matgroup_id'):
            group_use.setdefault(s.obj.matgroup_id, set()).add(s.id)
    for name, sec in target_secs.items():
        md = sec.obj
        drop.add(md.passthrough_id)
        drop.add(md.topologyip_id)
        gp = m.by_id[md.passthrough_id].obj
        drop.add(gp.geometry_id); drop.add(gp.topology_id)
        tip = m.by_id[md.topologyip_id].obj
        drop.add(tip.topology_id)
        if md.skinbones_id:
            shared = any(o.id != sec.id and getattr(o.obj, 'skinbones_id', 0) == md.skinbones_id
                         for o in m.sections if o.tag == 'model_data')
            if not shared:
                drop.add(md.skinbones_id)
        mg = md.matgroup_id
        if mg and group_use.get(mg, {sec.id}) == {sec.id}:
            drop.add(mg)
    print(f"drop {len(drop)} sections")

    # ---------- build pieces ----------
    built = []   # (model_sec, payload_builder) appended at end
    tex_plan = {}
    for name, sec in target_secs.items():
        faces = faces_by_target[name]
        used = {}
        for tri, key, pd2mat in faces:
            for vi in tri:
                for bn, w in weights.get(str(vi), [])[:3]:
                    used[bn] = used.get(bn, 0.0) + w
        if len(used) > MAX_PALETTE:
            keep = set(sorted(used, key=lambda b: -used[b])[:MAX_PALETTE])
        else:
            keep = set(used)
        palette = sorted(keep, key=lambda b: (bone_id.get(b, 0)))
        pal_ids = [bone_id[b] for b in palette]
        pal_index = {bid: i for i, bid in enumerate(pal_ids)}

        # ---- group faces by atom (material), stable order ----
        mat_order = []
        f_by_mat = {}
        for tri, key, pd2mat in faces:
            if pd2mat not in f_by_mat:
                f_by_mat[pd2mat] = []
                mat_order.append(pd2mat)
            f_by_mat[pd2mat].append(tri)

        # ---- contiguous vertex blocks per atom (matches original layout) ----
        vmap = {}; pverts = []; pnorms = []; puvs = []; pweights = []
        atoms = []; pfaces = []; base_v = 0; base_index = 0
        for pm in mat_order:
            fl = f_by_mat[pm]
            used = sorted({vi for tri in fl for vi in tri})
            blk = base_v
            for vi in used:
                vmap[vi] = base_v
                x, y, z = verts[vi]
                pverts.append((x*100.0, y*100.0, z*100.0))   # m -> cm, root space
                nx, ny, nz = norms[vi]
                pnorms.append((nx, ny, nz))
                u, v = uvs[vi]
                puvs.append((u, -v))                          # file UV (V negated)
                ent = []
                for bn, w in weights.get(str(vi), [])[:3]:
                    bid = bone_id.get(bn)
                    if bid not in pal_index:
                        bid = ancestor_in(bid, pal_index) if bid else None
                    if bid is None:
                        bid = bone_id.get('Hips')
                    ent.append((pal_index.get(bid, 0), max(w, 0.0)))
                while len(ent) < 3:
                    ent.append((0, 0.0))
                tot = sum(w for _, w in ent) or 1.0
                pweights.append(tuple((i, w/tot) for i, w in ent))
                base_v += 1
            for tri in fl:
                pfaces.append(tuple(vmap[x] for x in tri))
            atoms.append({'base_vertex': blk, 'tri_count': len(fl),
                          'base_index': base_index, 'geo_len': base_v - blk, 'mat': pm})
            base_index += len(fl)*3
        print(f"  {name}: {len(pverts)} verts {len(pfaces)} tris palette={len(palette)} atoms={len(atoms)}")

        # UV direction (tangent/bitangent) accumulation
        tan_u = [[0.0, 0.0, 0.0] for _ in pverts]
        tan_v = [[0.0, 0.0, 0.0] for _ in pverts]
        for a, b, c in pfaces:
            p0, p1, p2 = pverts[a], pverts[b], pverts[c]
            w0, w1, w2 = puvs[a], puvs[b], puvs[c]
            du1, dv1 = w1[0]-w0[0], w1[1]-w0[1]
            du2, dv2 = w2[0]-w0[0], w2[1]-w0[1]
            e1 = [p1[i]-p0[i] for i in range(3)]
            e2 = [p2[i]-p0[i] for i in range(3)]
            det = du1*dv2 - du2*dv1
            if abs(det) < 1e-12:
                continue
            r = 1.0/det
            T = [(e1[i]*dv2 - e2[i]*dv1)*r for i in range(3)]
            B = [(e2[i]*du1 - e1[i]*du2)*r for i in range(3)]
            for vi in (a, b, c):
                for i in range(3):
                    tan_u[vi][i] += T[i]; tan_v[vi][i] += B[i]

        def nrm3(v):
            l = math.sqrt(v[0]**2+v[1]**2+v[2]**2) or 1.0
            return (v[0]/l, v[1]/l, v[2]/l)

        # ---------- geometry section payload ----------
        headers = [(3, 1), (9, 7), (7, 17), (3, 19), (8, 2), (8, 22), (8, 23)]
        g = BW()
        g.u32(len(pverts)); g.u32(len(headers))
        for isz, ity in headers:
            g.u32(isz); g.u32(ity)
        for p in pverts:            # POSITION0 floats
            g.vec3(p)
        for u, v in puvs:           # TEXCOORD0 halfs (u, v already file-negated)
            g.u16(half(u)); g.u16(half(v))
        for (i0, w0), (i1, w1), (i2, w2) in pweights:   # BLENDINDICES0
            g.u16(i0); g.u16(i1); g.u16(i2); g.u16(0)
        for (i0, w0), (i1, w1), (i2, w2) in pweights:   # BLENDWEIGHT0 (3 floats)
            g.f32(w0); g.f32(w1); g.f32(w2)
        for n in pnorms:            # NORMAL0 packed
            x, y, z = nrm3(n)
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y), pack_signed_byte(x), 0]))
        for vi in range(len(pverts)):   # UV_DIRECTION_V0 packed
            x, y, z = nrm3(tan_v[vi])
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y), pack_signed_byte(x), 0]))
        for vi in range(len(pverts)):   # UV_DIRECTION_U0 packed
            x, y, z = nrm3(tan_u[vi])
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y), pack_signed_byte(x), 0]))
        g.u64(hash_str(name + '.DieselGeometry'))

        # ---------- topology (once, material-major, block-local indices) ----------
        t = BW()
        t.u32(3)  # TriangleList
        t.u32(len(pfaces)*3)
        for a, b, c in pfaces:
            t.u16(a); t.u16(b); t.u16(c)
        t.u32(0)  # count2
        t.u64(hash_str(name + '.Topology'))

        # skinbones: mappings = [all] + one per atom (per GltfImporter)
        # Each mapping entry is a 0..N-1 local index into SkinBones.object_ids.
        sb = BW()
        sb.u32(1 + len(atoms))
        for _ in range(1 + len(atoms)):
            sb.u32(len(pal_ids))
            for local_idx in range(len(pal_ids)):
                sb.u32(local_idx)
        sb.u32(hips.id)
        sb.u32(len(pal_ids))
        for pid in pal_ids:
            sb.u32(pid)
        def write_mat(bw, rows):
            for r in range(4):
                for c in range(4):
                    bw.f32(rows[r][c])
        for pid in pal_ids:
            write_mat(sb, minv(worlds[pid]))
        write_mat(sb, hips_world)

        # ---------- material group ----------
        mg = BW()
        mg.u32(len(mat_order))
        mat_ids = []
        for pm in mat_order:
            hit = [s for s in m.sections if s.tag == 'material' and s.obj.name == pm]
            mat_ids.append(hit[0].id)
        for mid in mat_ids:
            mg.u32(mid)

        # ---------- model section payload ----------
        md = sec.obj
        w = BW()
        w.u64(md.name_hash)
        w.u32(len(md.anim_ids))
        for aid, _u in md.anim_ids:
            w.u32(aid); w.u64(0)
        rows = [list(md.matrix[i*4:(i+1)*4]) for i in range(4)]
        rows[3] = [md.pos[0], md.pos[1], md.pos[2], rows[3][3]]
        write_mat(w, rows)
        w.vec3(md.pos)
        w.u32(md.parent_id)
        if md.remaining:
            w.raw(md.remaining)
        # model body
        w.u32(3)  # version
        gp_id, tp_id, mg_id, sb_id = new_id(), new_id(), new_id(), new_id()
        w.u32(gp_id); w.u32(tp_id)
        w.u32(len(atoms))
        for a in atoms:
            w.u32(a['base_vertex']); w.u32(a['tri_count']); w.u32(a['base_index'])
            w.u32(a['geo_len']); w.u32(mat_ids[mat_order.index(a['mat'])] if False else mat_order.index(a['mat']))
        # hmm RenderAtom.MaterialId = index into the model's material list (per C#):
        #   MaterialId = (uint)ms.materials.IndexOf(matname)  -> index into group items
        w = BW()  # rebuild model payload cleanly with correct MaterialId
        w.u64(md.name_hash)
        w.u32(len(md.anim_ids))
        for aid, _u in md.anim_ids:
            w.u32(aid); w.u64(0)
        write_mat(w, rows)
        w.vec3(md.pos)
        w.u32(md.parent_id)
        w.u32(3)
        w.u32(gp_id); w.u32(tp_id)
        w.u32(len(atoms))
        for a in atoms:
            w.u32(a['base_vertex']); w.u32(a['tri_count']); w.u32(a['base_index'])
            w.u32(a['geo_len']); w.u32(mat_order.index(a['mat']))
        w.u32(mg_id)
        w.u32(md.lightset_id)
        w.u32(md.properties)
        xs = [p[0] for p in pverts]; ys = [p[1] for p in pverts]; zs = [p[2] for p in pverts]
        w.vec3((min(xs), min(ys), min(zs)))
        w.vec3((max(xs), max(ys), max(zs)))
        rad = max(math.sqrt(x*x+y*y+z*z) for x, y, z in pverts)
        w.f32(rad); w.u32(md.bounding_int)
        w.u32(sb_id)
        if md.remaining:
            w.raw(md.remaining)

        for pm in mat_order:
            hit = [s for s in m.sections if s.tag == 'material' and s.obj.name == pm][0]
            tex_plan.setdefault(pm, hit.id)

        built.append({
            'model_id': sec.id, 'model_payload': bytes(w.b),
            'sections': [
                (TAGS_INV['geometry'], new_id(), bytes(g.b)),
                (TAGS_INV['topology'], new_id(), bytes(t.b)),
                (TAGS_INV['passthroughGP'], gp_id, struct.pack('<II', 0, 0)),  # filled below
                (TAGS_INV['topologyIP'], tp_id, struct.pack('<I', 0)),
                (TAGS_INV['material_group'], mg_id, bytes(mg.b)),
                (TAGS_INV['skinbones'], sb_id, bytes(sb.b)),
            ],
            'geom_id_ref': None,
        })
        # fix passthroughGP/topologyIP payloads with the real new geometry/topology ids
        geo_id = built[-1]['sections'][0][1]
        topo_id = built[-1]['sections'][1][1]
        built[-1]['sections'][2] = (TAGS_INV['passthroughGP'], gp_id, struct.pack('<II', geo_id, topo_id))
        built[-1]['sections'][3] = (TAGS_INV['topologyIP'], tp_id, struct.pack('<I', topo_id))

    # ---------- assemble file ----------
    built_by_model = {b['model_id']: b for b in built}
    out = BW()
    body = BW()
    count = 0
    for s in m.sections:
        if s.id in drop:
            continue
        if s.id in built_by_model:
            b = built_by_model[s.id]
            body.raw(section_bytes(s.type, s.id, b['model_payload']))
            count += 1
            for type_, sid, payload in b['sections']:
                body.raw(section_bytes(type_, sid, payload))
                count += 1
        else:
            body.raw(m.data[s.offset:s.end])
            count += 1
    payload = bytes(body.b)
    out.u32(0x42444F44)   # DODB
    out.u32(1)            # version
    out.u32(16 + len(payload))  # filesize (header 16 + sections)
    out.u32(count)
    out.raw(payload)
    data = bytes(out.b)
    # canonical DODB layout: contiguous section IDs 1..count, materials first,
    # mesh groups after the model_data block (see repair_skin_palettes docstring)
    data, fixed = normalize_model_container(data)
    if fixed:
        print(f"normalize: repaired sections {fixed}")
    dest = OUT / 'npc_criminal_female_1.model'
    dest.write_bytes(data)
    (OUT / 'npc_criminal_female_1_menu.model').write_bytes(data)
    print(f"wrote {dest} ({len(data)} bytes, {count} sections)")
    json.dump(tex_plan, open(OUT / 'texture_plan.json', 'w'), indent=1)
    print("texture_plan:", tex_plan)

if __name__ == '__main__':
    main()
