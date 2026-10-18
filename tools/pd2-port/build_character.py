#!/usr/bin/env python3
"""Generic Lawson-onto-PAYDAY-2-character .model builder.

Usage: build_character.py clover|bonnie|sydney

For each character: create dedicated lawson_* materials (cloned shader
templates from the same model), replace the character's body/head/hands/hair
drawables with the Lawson mesh (already weighted by rig_lawson.py), keep every
other drawable (vests, bags, capsules, shadow) untouched. Also writes
texture_plan.json for build_package.py.

Format conventions verified against vanilla files (see build_model.py history):
SkinBones.Rotations = inv(bone_world), Global_skin_transform = Hips world,
model.Transform = inv(Hips world), verts root-space cm, UV V negated in file,
palettes <= 32 bones, atom vertex blocks contiguous per material.
"""
import json, math, struct, sys
from pathlib import Path
from types import SimpleNamespace

WORK = Path('/home/user/pd2-work')
OUT = WORK / 'clover-lawson'
sys.path.insert(0, '/home/user/universal-modder/tools/pd2-port')
from dmodel import DieselModel, Hashlist, hash_str, minv, TAGS_INV

MAX_PALETTE = 32
M64MASK = (1 << 64) - 1

# ---------------------------------------------------------------- specs
def head_keys(piece):
    return {
        '1':  ('body',      'lawson_outfit'),
        '2':  ('body',      'lawson_outfit'),
        '3':  ('body',      'lawson_swim'),
        '4':  ('body',      'lawson_under'),
        '6':  ('head',      'lawson_lashes'),
        '7':  ('head',      'lawson_eyes'),
        '8':  ('body',      'lawson_limbs'),
        '9':  ('body',      'lawson_limbs'),
        '10': ('body',      'lawson_body'),
        '11': ('body',      'lawson_body'),
        '12': ('head',      'lawson_face'),
        '13': ('head',      'lawson_scalp'),
    }

CHARS = {
    'clover': dict(
        model_in='clover/npc_criminal_female_1.model',
        model_out='npc_criminal_female_1.model',
        mesh='lawson_mesh.json',
        pieces=dict(body='g_body', head='g_head_fem1', hand='g_hands'),
        hair=dict(mode='splitx', targets=['g_hair_cloth1', 'g_hair_cloth2', 'g_hair_cloth3'],
                  mat='lawson_hair', key='5'),
        hand_keys=('8', '9'), hand_mat='lawson_limbs',
        templates=dict(lawson_face='mtr_head', lawson_scalp='mtr_head',
                       lawson_lashes='mtr_head', lawson_eyes='mtr_head',
                       lawson_hair='mtr_hair_1', lawson_body='mtr_suite_body',
                       lawson_limbs='mtr_arms', lawson_outfit='mtr_enforcer_vest',
                       lawson_under='mtr_vest_small', lawson_swim='mtr_toolbag'),
    ),
    'bonnie': dict(
        model_in='Bonie/npc_criminal_bonnie.model',
        model_out='npc_criminal_bonnie.model',
        mesh='lawson_mesh_bonnie.json',
        pieces=dict(body='g_body', head=['g_head', 'g_head_mask_on'], hand='g_hands'),
        hair=dict(mode='dup', targets=['g_head'],
                  mat='lawson_hair', key='5'),
        hand_keys=('8', '9'), hand_mat='lawson_limbs',
        templates=dict(lawson_face='mtr_head', lawson_scalp='mtr_head',
                       lawson_lashes='mtr_head', lawson_eyes='mtr_head',
                       lawson_hair='mtr_hair', lawson_body='mtr_suite_body',
                       lawson_limbs='mtr_suite_body', lawson_outfit='mtr_suite_body',
                       lawson_under='mtr_suite_body', lawson_swim='mtr_suite_body'),
    ),
    'sydney': dict(
        model_in='Sydney/npc_criminal_sydney.model',
        model_out='npc_criminal_sydney.model',
        mesh='lawson_mesh_sydney.json',
        pieces=dict(body='g_body', head='g_head', hand='g_hands'),
        hair=dict(mode='dup', targets=['g_hair_mask_on', 'g_hair_mask_off'],
                  mat='lawson_hair', key='5'),
        hand_keys=('8', '9'), hand_mat='lawson_limbs',
        templates=dict(lawson_face='mtr_head', lawson_scalp='mtr_head',
                       lawson_lashes='mtr_head', lawson_eyes='mtr_head',
                       lawson_hair='mtr_hair', lawson_body='mtr_suite_body',
                       lawson_limbs='mtr_suite_body', lawson_outfit='mtr_suite_body',
                       lawson_under='mtr_suite_body', lawson_swim='mtr_suite_body'),
    ),
}

# ---------------------------------------------------------------- helpers
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
    def vec3(self, v):
        self.f32(v[0]); self.f32(v[1]); self.f32(v[2])

def section_bytes(type_, sid, payload):
    w = BW()
    w.u32(type_); w.u32(sid); w.u32(len(payload)); w.raw(payload)
    return bytes(w.b)

def nrm3(v):
    l = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2) or 1.0
    return (v[0]/l, v[1]/l, v[2]/l)

def write_mat(bw, rows):
    for r in range(4):
        for c in range(4):
            bw.f32(rows[r][c])

# ---------------------------------------------------------------- main
def main():
    char = sys.argv[1] if len(sys.argv) > 1 else 'bonnie'
    spec = CHARS[char]
    hl = Hashlist(str(WORK / 'PAYDAY-2-Hashlist/hashlist'))
    m = DieselModel(str(OUT / spec['model_in']), hl)
    worlds = m.world_rows()
    mesh = json.load(open(OUT / spec['mesh']))

    hips = m.find_by_name('Hips')[0]
    hips_world = worlds[hips.id]

    bone_id, parent_of = {}, {}
    for s in m.objects():
        if s.tag == 'object3D':
            bone_id[s.obj.name] = s.id
            parent_of[s.id] = s.obj.parent_id

    def ancestor_in(bid, palette_ids):
        while bid and bid not in palette_ids:
            bid = parent_of.get(bid)
        return bid if bid in palette_ids else None

    # ---------- ensure lawson_* material sections ----------
    max_id = max(m.by_id)
    next_id = [max_id + 1]
    def new_id():
        v = next_id[0]; next_id[0] += 1
        return v

    mat_by_name = {}
    extra_sections = []      # (type, id, payload) appended at end of file
    for s in m.sections:
        if s.tag == 'material':
            mat_by_name[s.obj.name] = s
    for name, tmpl_name in spec['templates'].items():
        if name in mat_by_name:
            continue
        tmpl = mat_by_name[tmpl_name]
        # tmpl.offset..end is the FULL section (12-byte header + payload)
        payload = bytearray(m.data[tmpl.offset + 12:tmpl.end])
        struct.pack_into('<Q', payload, 0, hash_str(name))
        sid = new_id()
        extra_sections.append((TAGS_INV['material'], sid, bytes(payload)))
        fake = SimpleNamespace(tag='material', id=sid, type=TAGS_INV['material'],
                               obj=SimpleNamespace(name=name), offset=0, end=0)
        mat_by_name[name] = fake
        print(f"  + material {name} (template {tmpl_name}) id={sid}")

    # ---------- split Lawson faces into pieces ----------
    verts = mesh['verts']; uvs = mesh['uvs']; weights = mesh['weights']
    norms = mesh['normals']
    keymap = head_keys(spec['pieces']['head'])
    P = spec['pieces']
    faces_by_target = {}
    hair_faces = []

    def dom_hand(vi):
        ws = weights.get(str(vi), [])
        return bool(ws) and ('Hand' in ws[0][0])

    for f in mesh['faces']:
        tri, mslot = f
        key = mesh['materials'][mslot]['key']
        if key == spec['hair']['key']:
            hair_faces.append((tuple(tri), key, spec['hair']['mat']))
            continue
        _, pd2mat = keymap[key]
        if key in spec['hand_keys'] and sum(dom_hand(v) for v in tri) >= 2:
            target, pd2mat = P['hand'], spec['hand_mat']
        else:
            target = P[keymap[key][0]]
        if isinstance(target, list):
            for t in target:
                faces_by_target.setdefault(t, []).append((tuple(tri), key, pd2mat))
        else:
            faces_by_target.setdefault(target, []).append((tuple(tri), key, pd2mat))

    hair = spec['hair']
    if hair['mode'] == 'splitx':
        buckets = {t: [] for t in hair['targets']}
        for tri, key, pd2mat in hair_faces:
            cx = sum(verts[v][0] for v in tri) / 3.0
            t0, t1, t2 = hair['targets']
            b = t0 if cx < -0.05 else (t2 if cx > 0.05 else t1)
            buckets[b].append((tri, key, pd2mat))
        for b, fl in buckets.items():
            if fl:
                faces_by_target.setdefault(b, []).extend(fl)
    else:  # 'dup': every hair target gets all hair faces
        for t in hair['targets']:
            faces_by_target.setdefault(t, []).extend(list(hair_faces))

    print("pieces:", {k: len(v) for k, v in faces_by_target.items()})

    # ---------- drop old sections of targets ----------
    target_secs = {}
    for name in faces_by_target:
        hits = m.find_by_name(name)
        if not hits:
            sys.exit(f"ERROR: target drawable {name} not in model")
        target_secs[name] = hits[0]
    drop = set()
    group_use = {}
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
    built = []
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
        palette = sorted(keep, key=lambda b: bone_id.get(b, 0))
        pal_ids = [bone_id[b] for b in palette]
        pal_index = {bid: i for i, bid in enumerate(pal_ids)}

        # contiguous vertex blocks per atom (matches vanilla layout)
        mat_order = []
        f_by_mat = {}
        for tri, key, pd2mat in faces:
            if pd2mat not in f_by_mat:
                f_by_mat[pd2mat] = []
                mat_order.append(pd2mat)
            f_by_mat[pd2mat].append(tri)

        vmap = {}; pverts = []; pnorms = []; puvs = []; pweights = []
        atoms = []; pfaces = []; base_v = 0; base_index = 0
        for pm in mat_order:
            fl = f_by_mat[pm]
            used_v = sorted({vi for tri in fl for vi in tri})
            blk = base_v
            for vi in used_v:
                vmap[vi] = base_v
                x, y, z = verts[vi]
                pverts.append((x*100.0, y*100.0, z*100.0))
                nx, ny, nz = norms[vi]
                pnorms.append((nx, ny, nz))
                u, v = uvs[vi]
                puvs.append((u, -v))
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

        # UV tangents
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

        # geometry
        headers = [(3, 1), (9, 7), (7, 17), (3, 19), (8, 2), (8, 22), (8, 23)]
        g = BW()
        g.u32(len(pverts)); g.u32(len(headers))
        for isz, ity in headers:
            g.u32(isz); g.u32(ity)
        for p in pverts:
            g.vec3(p)
        for u, v in puvs:
            g.u16(half(u)); g.u16(half(v))
        for (i0, w0), (i1, w1), (i2, w2) in pweights:
            g.u16(i0); g.u16(i1); g.u16(i2); g.u16(0)
        for (i0, w0), (i1, w1), (i2, w2) in pweights:
            g.f32(w0); g.f32(w1); g.f32(w2)
        for n in pnorms:
            x, y, z = nrm3(n)
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y), pack_signed_byte(x), 0]))
        for vi in range(len(pverts)):
            x, y, z = nrm3(tan_v[vi])
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y), pack_signed_byte(x), 0]))
        for vi in range(len(pverts)):
            x, y, z = nrm3(tan_u[vi])
            g.raw(bytes([pack_signed_byte(z), pack_signed_byte(y), pack_signed_byte(x), 0]))
        g.u64(hash_str(name + '.DieselGeometry'))

        # topology
        t = BW()
        t.u32(3); t.u32(len(pfaces)*3)
        for a, b, c in pfaces:
            t.u16(a); t.u16(b); t.u16(c)
        t.u32(0); t.u64(hash_str(name + '.Topology'))

        # skinbones
        sb = BW()
        sb.u32(1 + len(atoms))
        for _ in range(1 + len(atoms)):
            sb.u32(len(pal_ids))
            for idx in range(len(pal_ids)):
                sb.u32(idx)
        sb.u32(hips.id)
        sb.u32(len(pal_ids))
        for pid in pal_ids:
            sb.u32(pid)
        for pid in pal_ids:
            write_mat(sb, minv(worlds[pid]))
        write_mat(sb, hips_world)

        # material group
        mg = BW()
        mg.u32(len(mat_order))
        mat_ids = [mat_by_name[pm].id for pm in mat_order]
        for mid in mat_ids:
            mg.u32(mid)

        # model payload
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
        w.u32(3)
        gp_id, tp_id, mg_id, sb_id = new_id(), new_id(), new_id(), new_id()
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

        for pm in mat_order:
            tex_plan.setdefault(pm, mat_by_name[pm].id)

        built.append({
            'model_id': sec.id, 'model_payload': bytes(w.b),
            'sections': [
                (TAGS_INV['geometry'], new_id(), bytes(g.b)),
                (TAGS_INV['topology'], new_id(), bytes(t.b)),
                (TAGS_INV['passthroughGP'], gp_id, struct.pack('<II', 0, 0)),
                (TAGS_INV['topologyIP'], tp_id, struct.pack('<I', 0)),
                (TAGS_INV['material_group'], mg_id, bytes(mg.b)),
                (TAGS_INV['skinbones'], sb_id, bytes(sb.b)),
            ],
        })
        geo_id = built[-1]['sections'][0][1]
        topo_id = built[-1]['sections'][1][1]
        built[-1]['sections'][2] = (TAGS_INV['passthroughGP'], gp_id, struct.pack('<II', geo_id, topo_id))
        built[-1]['sections'][3] = (TAGS_INV['topologyIP'], tp_id, struct.pack('<I', topo_id))

    # ---------- assemble ----------
    built_by_model = {b['model_id']: b for b in built}
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
    for type_, sid, payload in extra_sections:
        body.raw(section_bytes(type_, sid, payload))
        count += 1
    payload = bytes(body.b)
    out = BW()
    out.u32(0x42444F44)
    out.u32(1)
    out.u32(16 + len(payload))
    out.u32(count)
    out.raw(payload)
    data = bytearray(out.b)
    struct.pack_into('<I', data, 8, len(data))
    dest = OUT / spec['model_out']
    dest.write_bytes(data)
    (OUT / (spec['model_out'].replace('.model', '_menu.model'))).write_bytes(data)
    print(f"wrote {dest} ({len(data)} bytes, {count} sections)")
    json.dump(tex_plan, open(OUT / f"texture_plan_{char}.json", 'w'), indent=1)
    print("texture_plan:", tex_plan)

if __name__ == '__main__':
    main()
