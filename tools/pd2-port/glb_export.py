#!/usr/bin/env python3
"""Export a built Diesel3 .model to GLB for visual verification (static bind pose)."""
import sys, struct, json as js
sys.path.insert(0, '/home/user/universal-modder/tools/pd2-port')
from dmodel import DieselModel, Hashlist

def unpack3(b):
    return [b[2]/127.5-1, b[1]/127.5-1, b[0]/127.5-1]  # packed z,y,x

def half2f(h):
    s = (h >> 15) & 1; e = (h >> 10) & 0x1f; f = h & 0x3ff
    if e == 0: v = (f/1024)*2**-14
    elif e == 31: v = float('inf') if not f else float('nan')
    else: v = (1+f/1024)*2**(e-15)
    return -v if s else v

def export(model_path, out_glb, plan_path=None, only=None):
    hl = Hashlist('/home/user/pd2-work/PAYDAY-2-Hashlist/hashlist')
    m = DieselModel(model_path, hl)
    plan = {}
    if plan_path:
        plan = {k: v for k, v in js.load(open(plan_path)).items()}
    # find piece geometry via model_data names
    pieces = []
    for s in m.sections:
        if s.tag != 'model_data' or not s.obj.render_atoms:
            continue
        nm = s.obj.name or ''
        if only and nm not in only:
            continue
        if not nm.startswith(('g_', 's_')):
            continue
        gp = m.by_id[s.obj.passthrough_id].obj
        geo = m.by_id[gp.geometry_id].obj
        topo = m.by_id[gp.topology_id].obj
        pieces.append((nm, s, gp, geo, topo))
    bin_data = bytearray(); accessors = []; buffer_views = []; meshes = []; nodes = []
    def add_view(data, target=None):
        off = len(bin_data)
        bin_data.extend(data)
        while len(bin_data) % 4: bin_data.append(0)
        bv = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target: bv["target"] = target
        buffer_views.append(bv); return len(buffer_views) - 1
    materials = []
    PNG = {
        'mtr_enforcer_vest': 'Vixen_d.png', 'mtr_toolbag': 'Cri_swimmers_base.png',
        'mtr_vest_small': 'underwear_d.png', 'mtr_hair_1': 'Miranda_hair_d.png',
        'mtr_hair_2': 'Miranda_scalp_d.png', 'mtr_hair_3': 'HMF_HED_PROMiranda_Lashes.png',
        'mtr_head': 'Miranda_face_d.png', 'mtr_arms': 'miranda limbs d.png',
        'mtr_suite_body': 'miranda body d.png', 'mtr_hands': 'Miranda_eye_d.png',
        'lawson_face': 'Miranda_face_d.png', 'lawson_scalp': 'Miranda_scalp_d.png',
        'lawson_lashes': 'HMF_HED_PROMiranda_Lashes.png', 'lawson_eyes': 'Miranda_eye_d.png',
        'lawson_hair': 'Miranda_hair_d.png', 'lawson_body': 'miranda body d.png',
        'lawson_limbs': 'miranda limbs d.png', 'lawson_outfit': 'Vixen_d.png',
        'lawson_under': 'underwear_d.png', 'lawson_swim': 'Cri_swimmers_base.png',
    }
    # piece -> material name (matches build_model ASSIGN)
    PIECE_MTR = {
        'g_body': 'mtr_suite_body', 'g_head_fem1': 'mtr_head', 'g_hands': 'mtr_arms',
        'g_hair_cloth1': 'mtr_hair_1', 'g_hair_cloth2': 'mtr_hair_1', 'g_hair_cloth3': 'mtr_hair_1',
    }
    images = []; textures = []
    from dmodel import hash_str as _hs
    NAME_BY_HASH = {_hs(n): n for n in PNG}
    def add_image(png_path):
        data = open(png_path, 'rb').read()
        bv = add_view(data)
        images.append({"bufferView": bv, "mimeType": "image/png"})
        textures.append({"source": len(images) - 1})
        return len(textures) - 1
    tex_root = '/home/user/pd2-work/clover-lawson/lawson/'
    for pi, (nm, sec, gp, geo, topo) in enumerate(pieces):
        pos = [[p[0]/100.0, p[1]/100.0, p[2]/100.0] for p in geo.positions]
        nrm = [list(n) for n in geo.normals] or [[0, 0, 1]] * len(pos)
        # reader stores Blender v; GLB wants file convention v
        uv = [[u, -v] for (u, v) in geo.uvs] or [[0, 0]] * len(pos)
        flat = [i for f in topo.faces for i in f]
        mg = m.by_id.get(sec.obj.matgroup_id)
        ai = 0
        for atom in sec.obj.render_atoms:
            tris = atom['tri_count']; base_i = atom['base_index']; base_v = atom['base_vertex']
            idx = flat[base_i:base_i + tris*3]
            used = sorted(set(idx))
            remap = {v: i for i, v in enumerate(used)}
            sub_idx = [remap[v] for v in idx]
            sub_pos = [pos[v] for v in used]
            sub_nrm = [nrm[v] if v < len(nrm) else [0,0,1] for v in used]
            sub_uv = [uv[v] if v < len(uv) else [0,0] for v in used]
            mtr_name = 'mtr_head'
            if mg and atom['material_id'] < len(mg.obj.items):
                mi = m.by_id[mg.obj.items[atom['material_id']]]
                mtr_name = NAME_BY_HASH.get(mi.obj.name_hash) or mi.obj.name or mtr_name
            pv = add_view(struct.pack(f'<{len(sub_pos)*3}f', *[x for p in sub_pos for x in p]), 34962)
            nv = add_view(struct.pack(f'<{len(sub_nrm)*3}f', *[x for p in sub_nrm for x in p]), 34962)
            tv = add_view(struct.pack(f'<{len(sub_uv)*2}f', *[x for p in sub_uv for x in p]), 34962)
            iv = add_view(struct.pack(f'<{len(sub_idx)}I', *sub_idx), 34963)
            mn = [min(p[i] for p in sub_pos) for i in range(3)] if sub_pos else [0,0,0]
            mx = [max(p[i] for p in sub_pos) for i in range(3)] if sub_pos else [0,0,0]
            accessors.append({"bufferView": pv, "componentType": 5126, "count": len(sub_pos), "type": "VEC3", "min": mn, "max": mx})
            accessors.append({"bufferView": nv, "componentType": 5126, "count": len(sub_nrm), "type": "VEC3"})
            accessors.append({"bufferView": tv, "componentType": 5126, "count": len(sub_uv), "type": "VEC2"})
            accessors.append({"bufferView": iv, "componentType": 5125, "count": len(sub_idx), "type": "SCALAR"})
            base = len(accessors) - 4
            mi = len(materials)
            meshes.append({"name": f"{nm}:{ai}", "primitives": [{"attributes": {"POSITION": base, "NORMAL": base+1, "TEXCOORD_0": base+2}, "indices": base+3, "material": mi}]})
            nodes.append({"name": f"{nm}:{ai}", "mesh": len(meshes)-1})
            mat = {"name": mtr_name, "pbrMetallicRoughness": {"metallicFactor": 0, "roughnessFactor": 0.85}}
            png = PNG.get(mtr_name)
            if png:
                tex = add_image(tex_root + png)
                mat["pbrMetallicRoughness"]["baseColorTexture"] = {"index": tex}
            materials.append(mat)
            ai += 1
    glb = {"asset": {"version": "2.0"},
           "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
           "nodes": nodes, "meshes": meshes, "materials": materials, "accessors": accessors,
           "bufferViews": buffer_views, "buffers": [{"byteLength": len(bin_data)}],
           "images": images, "textures": textures}
    blob = js.dumps(glb).encode()
    while len(blob) % 4: blob += b' '
    total = 12 + 8 + len(blob) + 8 + len(bin_data)
    with open(out_glb, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, total))
        f.write(struct.pack('<II', len(blob), 0x4E4F534A) + blob)
        f.write(struct.pack('<II', len(bin_data), 0x004E4942) + bytes(bin_data))
    print(f"wrote {out_glb}: {len(pieces)} meshes, {sum(len(p[4].faces) for p in pieces)} tris")

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('model'); ap.add_argument('out')
    ap.add_argument('--plan', default='/home/user/pd2-work/clover-lawson/texture_plan.json')
    a = ap.parse_args()
    export(a.model, a.out, a.plan)
