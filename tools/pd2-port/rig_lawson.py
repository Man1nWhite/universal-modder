#!/usr/bin/env python3
"""Rig Lawson onto Clover's Diesel skeleton (headless Blender via bpy).

Rebuilds the armature from the parsed .model, welds the OBJ, aligns scale, skins
via bone-heat (fallback: proximity), and exports lawson_mesh.json for build_model.py.

Run with stubs on LD_LIBRARY_PATH (see setup_work.sh):
  LD_LIBRARY_PATH=/home/user/pd2-work/stubs python3 rig_lawson.py
"""
import bpy, json, math, sys, struct, re
from mathutils import Vector, Euler
from pathlib import Path

WORK = Path('/home/user/pd2-work')
OUT = WORK / 'clover-lawson'
sys.path.insert(0, '/home/user/universal-modder/tools/pd2-port')
sys.path.insert(0, str(WORK))
from dmodel import DieselModel, Hashlist

SCALE = 0.01
NO_DEFORM = ('c_', 'a_weapon', 'e_taser', 'root_point', 'eyeAim', 'aim', 'BackPack', '#')

hl = Hashlist(str(WORK / 'PAYDAY-2-Hashlist/hashlist'))

CHARS = {
    'clover': dict(model='clover/npc_criminal_female_1.model',
                   out='lawson_mesh.json',
                   fit=('g_body', 'g_hands', 'g_head_fem1')),
    'bonnie': dict(model='Bonie/npc_criminal_bonnie.model',
                   out='lawson_mesh_bonnie.json',
                   fit=('g_body', 'g_hands', 'g_head')),
    'sydney': dict(model='Sydney/npc_criminal_sydney.model',
                   out='lawson_mesh_sydney.json',
                   fit=('g_body', 'g_hands', 'g_head')),
}
CHAR = sys.argv[1] if len(sys.argv) > 1 else 'clover'
SPEC = CHARS[CHAR]
m = DieselModel(str(OUT / SPEC['model']), hl)
# target bbox (meters, root space) from the pieces we will replace
tb_lo = [1e9]*3; tb_hi = [-1e9]*3
for s in m.sections:
    if s.tag == 'model_data' and (s.obj.name or '') in SPEC['fit']:
        gp = m.by_id[s.obj.passthrough_id].obj
        geo = m.by_id[gp.geometry_id].obj
        for p in geo.positions:
            for i in range(3):
                tb_lo[i] = min(tb_lo[i], p[i]*SCALE)
                tb_hi[i] = max(tb_hi[i], p[i]*SCALE)
print(f"[{CHAR}] target bbox:", [round(x,3) for x in tb_lo], [round(x,3) for x in tb_hi])
worlds = m.world_rows()
def wpos(sec_id):
    W = worlds[sec_id]
    return Vector((W[3][0]*SCALE, W[3][1]*SCALE, W[3][2]*SCALE))

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---- armature: Object3D sections only (model_data nodes are mesh instances) ----
arm_data = bpy.data.armatures.new(CHAR + 'Rig')
arm_obj = bpy.data.objects.new(CHAR + 'Rig', arm_data)
bpy.context.collection.objects.link(arm_obj)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='EDIT')
ebones = {}
obj_secs = m.objects()
kids = {}
ids = {s.id for s in obj_secs}
for s in obj_secs:
    p = s.obj.parent_id
    if p in ids and p != s.id:
        kids.setdefault(p, []).append(s.id)
for s in obj_secs:
    if s.tag != 'object3D':
        continue
    eb = arm_data.edit_bones.new(s.obj.name or f'obj_{s.id}')
    ebones[s.id] = eb
    eb.head = wpos(s.id)
    ch = [c for c in kids.get(s.id, []) if c in ebones or True]
    bone_kids = [c for c in kids.get(s.id, [])]
    pts = [wpos(c) for c in bone_kids]
    if pts:
        tail = sum(pts, Vector()) / len(pts)
        if (tail - eb.head).length < 1e-4:
            tail = eb.head + Vector((0, 0, 0.02))
        eb.tail = tail
    else:
        par = s.obj.parent_id
        d = (eb.head - wpos(par)) if par in worlds else Vector((0, 0, 0.02))
        if d.length < 1e-4:
            d = Vector((0, 0, 0.02))
        eb.tail = eb.head + d * 0.25 + Vector((0, 0, 0.005))
for s in obj_secs:
    if s.id not in ebones:
        continue
    p = s.obj.parent_id
    if p in ebones and p != s.id:
        ebones[s.id].parent = ebones[p]
        ebones[s.id].use_connect = False
for s in obj_secs:
    if s.id not in ebones:
        continue
    nm = s.obj.name or ''
    ebones[s.id].use_deform = not any(nm.startswith(p) or nm == p for p in NO_DEFORM)
bpy.ops.object.mode_set(mode='OBJECT')
deform = [b.name for b in arm_data.bones if b.use_deform]
print(f"armature: {len(arm_data.bones)} bones ({len(deform)} deform)")

# ---- Lawson OBJ ----
bpy.ops.wm.obj_import(filepath=str(OUT / 'lawson/Lawson_strip.obj'))
law = [o for o in bpy.data.objects if o.type == 'MESH'][0]
law.name = 'Lawson'
bpy.context.view_layer.objects.active = law
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0008)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
print(f"lawson welded: {len(law.data.vertices)} verts {len(law.data.polygons)} faces")

def bbox(obj):
    lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
    for c in obj.bound_box:
        v = obj.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, v)); hi = Vector(map(max, hi, v))
    return lo, hi
lo, hi = bbox(law)
ext = hi - lo
if ext.z < max(ext.x, ext.y) * 0.9:
    law.rotation_euler = Euler((-math.pi/2, 0, 0)) if ext.y >= ext.x else Euler((-math.pi/2, 0, math.pi/2))
    bpy.ops.object.transform_apply(rotation=True)
    lo, hi = bbox(law); ext = hi - lo
# fit Lawson's height to the target character's body pieces, then bbox-match
tb_h = tb_hi[2] - tb_lo[2]
s = tb_h / (ext.z or 1.0)
law.scale = (s, s, s)
bpy.ops.object.transform_apply(scale=True)
lo, hi = bbox(law)
cx, cy = (lo.x+hi.x)/2, (lo.y+hi.y)/2
tcx, tcy = (tb_lo[0]+tb_hi[0])/2, (tb_lo[1]+tb_hi[1])/2
law.location = (tcx - cx, tcy - cy, tb_lo[2] - lo.z)
bpy.ops.object.transform_apply(location=True)
lo, hi = bbox(law)
print(f"lawson aligned: {tuple(round(x,3) for x in lo)}..{tuple(round(x,3) for x in hi)} scale={s:.4f}")

# ---- arm alignment: Lawson is T-pose (arms horizontal); the rig's arms hang
# slightly down/back. Rotate arm verts about the shoulder so hands land next to
# the hand/finger bones (else proximity weights bind hands to forearm).
def bone_head_world(name):
    b = arm_obj.data.bones[name]
    return (arm_obj.matrix_world @ b.head_local).copy()
arm_setup = {}
for side, sx in (('Left', 1.0), ('Right', -1.0)):
    pivot = bone_head_world(side + 'Arm')
    tgt = (bone_head_world(side + 'Hand') - pivot).normalized()
    src = Vector((sx, 0, 0))
    arm_setup[side] = (pivot, src.rotation_difference(tgt))
def smooth(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
aligned = 0
for v in law.data.vertices:
    # arms only: above the waist and outboard of the spine (legs also have |x|~0.1)
    if abs(v.co.x) < 0.08 or v.co.z < 1.15:
        continue
    side = 'Left' if v.co.x > 0 else 'Right'
    pivot, q = arm_setup[side]
    t = smooth((abs(v.co.x) - 0.08) / 0.22)
    p = v.co.copy()
    p2 = pivot + q @ (p - pivot)
    v.co = p.lerp(p2, t)
    aligned += 1
for poly in law.data.polygons:
    pass  # normals recomputed below
law.data.update()
print(f"arm-aligned verts: {aligned}")

# ---- skin ----
for o in bpy.data.objects: o.select_set(False)
law.select_set(True); arm_obj.select_set(True)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
weighted = sum(1 for v in law.data.vertices if v.groups)
print(f"auto-weights: {weighted}/{len(law.data.vertices)}")
if weighted == 0:
    print("bone-heat failed -> proximity fallback")
    import numpy as np
    verts = np.array([v.co[:] for v in law.data.vertices], dtype=np.float64)
    segs = [(b.name, np.array(b.head_local[:]), np.array(b.tail_local[:]))
            for b in arm_obj.data.bones if b.use_deform]
    for name, _, _ in segs:
        if name not in law.vertex_groups:
            law.vertex_groups.new(name=name)
    d2 = np.zeros((len(segs), len(verts)))
    for i, (name, h, t) in enumerate(segs):
        d = t - h; dd = float(d @ d) or 1e-8
        w = np.clip(((verts - h) @ d) / dd, 0, 1)
        d2[i] = np.sum((verts - (h + w[:, None]*d))**2, axis=1)
    order = np.argsort(d2, axis=0)
    for vi in range(len(verts)):
        for k in range(4):
            si = order[k, vi]
            law.vertex_groups[segs[si][0]].add([vi], 1.0/(math.sqrt(d2[si, vi])+1e-4), 'REPLACE')
    for vi in range(len(verts)):
        gs = [(g.group, g.weight) for g in law.data.vertices[vi].groups]
        tot = sum(w for _, w in gs)
        if tot > 0:
            for gi, w in gs:
                law.vertex_groups[gi].add([vi], w/tot, 'REPLACE')
    weighted = sum(1 for v in law.data.vertices if v.groups)
    print(f"proximity weighted: {weighted}/{len(law.data.vertices)}")

# ---- export lawson_mesh.json ----
mats = [s.material.name if s.material else f'mat{i}' for i, s in enumerate(law.material_slots)]
mtl_map = {}
mtl_txt = (OUT/'lawson'/'Lawson_strip.mtl').read_text(errors='replace')
cur = None
for line in mtl_txt.splitlines():
    line = line.strip()
    if line.startswith('newmtl '): cur = line[7:].strip()
    elif line.startswith('map_Kd ') and cur: mtl_map[cur] = line[7:].strip()

def mat_key(name):
    mm = re.search(r'Material0*(\d+)', name)
    return mm.group(1) if mm else name

out = {
    'verts': [tuple(round(c, 6) for c in v.co[:]) for v in law.data.vertices],
    'normals': [tuple(round(c, 4) for c in v.normal[:]) for v in law.data.vertices],
    'uvs': None,
    'faces': [],
    'materials': [],
}
# per-loop UVs -> per-vertex (take first loop of each vert; weld kept seams as loops)
uv_layer = law.data.uv_layers.active
uvs = [None]*len(law.data.vertices)
for poly in law.data.polygons:
    for li in poly.loop_indices:
        vi = law.data.loops[li].vertex_index
        if uvs[vi] is None and uv_layer:
            uvs[vi] = tuple(round(c, 6) for c in uv_layer.data[li].uv[:])
out['uvs'] = [u or (0.0, 0.0) for u in uvs]
for poly in law.data.polygons:
    out['faces'].append((tuple(poly.vertices), poly.material_index))
for i, name in enumerate(mats):
    key = mat_key(name)
    out['materials'].append({'slot': i, 'name': name, 'key': key,
                             'texture': mtl_map.get(name) or mtl_map.get(f'Model001_Material{int(key):03d}')})
out['weights'] = {str(v.index): [(law.vertex_groups[g.group].name, round(g.weight, 5))
                                  for g in sorted(v.groups, key=lambda g: -g.weight)[:4]]
                   for v in law.data.vertices if v.groups}
json.dump(out, open(OUT/SPEC['out'], 'w'))
print(f"lawson_mesh.json: {len(out['verts'])} verts, {len(out['faces'])} faces, {len(mats)} materials")
for mt in out['materials']:
    print("  mat", mt)
print("DONE")
