#!/usr/bin/env python3
"""Render a GLB (bind pose) headless. Usage: glb_render.py in.glb out_prefix"""
import sys, math, bpy
from mathutils import Vector

glb, out = sys.argv[1], sys.argv[2]
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=glb)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
# GLB data here is Diesel root-space (Z-up); importer baked its Y-up conversion
# into the mesh data — bake the inverse rotation back into the vertices.
from mathutils import Matrix
fix = Matrix.Rotation(-math.pi/2, 4, 'X')
for o in meshes:
    o.data.transform(fix)
    o.data.update()
print("imported:", [(o.name, len(o.data.polygons)) for o in meshes])

# frame all (bound_box is stale after mesh.transform in headless; use verts)
lo = Vector((1e9,)*3); hi = Vector((-1e9,)*3)
for o in meshes:
    mw = o.matrix_world
    for i, v in enumerate(o.data.vertices):
        if i % 5:
            continue
        p = mw @ v.co
        lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
ctr = (lo + hi) / 2
print("bbox", tuple(round(x,3) for x in lo), tuple(round(x,3) for x in hi))

# lights + camera
sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 3.0
so = bpy.data.objects.new('sun', sun); bpy.context.collection.objects.link(so)
so.rotation_euler = (math.radians(55), 0, math.radians(30))
fill = bpy.data.lights.new('fill', 'SUN'); fill.energy = 1.2
fo = bpy.data.objects.new('fill', fill); bpy.context.collection.objects.link(fo)
fo.rotation_euler = (math.radians(70), 0, math.radians(-140))
cam = bpy.data.cameras.new('cam'); cam.lens = 50
co = bpy.data.objects.new('cam', cam); bpy.context.collection.objects.link(co)
co.location = ctr + Vector((2.6, -2.6, 0.6))
d = ctr - co.location
co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
scene = bpy.context.scene
scene.camera = co
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 512; scene.render.resolution_y = 768
world = bpy.data.worlds.new('w'); scene.world = world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (0.25, 0.25, 0.28, 1)

for name, loc in [('beauty', (2.6, -2.6, 0.6)), ('front', (0, -3.6, 0.3)), ('side', (3.6, 0, 0.3))]:
    co.location = ctr + Vector(loc)
    d = ctr - co.location
    co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = f"{out}_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath)
