#!/usr/bin/env python3
"""Re-save the owner's Arivus v2 `.blend` so the pinned Blender can open it, in place.

    python tools/bootstrap_bpy.py -- tools/pd2-las/resave_arivus_blend.py --check
        # report, write nothing
    python tools/bootstrap_bpy.py -- tools/pd2-las/resave_arivus_blend.py --dump
        # stage 1, needs a 5.x Blender
    python tools/bootstrap_bpy.py -- tools/pd2-las/resave_arivus_blend.py --rebuild
        # stage 2, needs Blender 4.2

`references/templates/Arivus Head BLEND.7z` shipped a scene saved by Blender **5.1**
(file version 501.30). Blender 4.2 — this repository's own pinned Blender (4.2.23 LTS,
see `docs/audits/2026-11-14-christie-rebuild-redo.md`) — refuses it: "File written by newer
Blender binary". `arivus_v2_from_blend.py` could only read it by installing 5.0.1 in a
throwaway environment.

This rewrites the scene with **4.2.23**, so the archive opens in the Blender the repository
actually pins. A plain "open in 5.x and save" does not achieve that: `bpy.data.version`
inherits the *opened* file's stamp, so the re-save still says 501.30 and 4.2 still refuses
it (measured). The scene is therefore rebuilt in a fresh 4.2 document from a data dump of
the original — armature and three bones with their rest transforms and pose state, the head
mesh's vertices/edges/polygons/UVs/vertex groups/material, the two packed 2048² images, and
the material's eight nodes. Nothing is re-sculpted, re-rigged, re-UV'd or re-imported
through a file format: every value is copied. Two stages are needed because the 5.1 file
cannot be opened by 4.2 at all, so each Blender writes its own stage's data:

    # stage 1: 5.0.1 reads the 5.1 file and dumps its data
    python tools/bootstrap_bpy.py -- tools/pd2-las/resave_arivus_blend.py --dump
    # stage 2: 4.2.23 rebuilds the scene from the dump and repacks the archive
    python tools/bootstrap_bpy.py -- tools/pd2-las/resave_arivus_blend.py --rebuild

Both stages need `bpy`, which the build `.venv` does not carry, plus the GL/X11 stubs that
`tools/bootstrap_bpy.py` builds for a machine with no display (`--dump` runs in a 5.0.1
environment, `--rebuild` in a 4.2.23 one). Neither is on the build path, and `make` never
runs them. `--check` reports what the tracked archive holds and whether the
pack's digest still names it.

The archive keeps its name and its members; the 5.1 `.blend` is replaced, everything else
(including the v1 GLB/DDS export folder beside it) is copied through unchanged. The new
`.7z` is written with py7zr's fixed LZMA2 settings and a sorted member order, so two runs
produce the same bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

ARCHIVE = ROOT / "references/templates/Arivus Head BLEND.7z"
MEMBER = "Untitled.blend"
MESH_OBJECT = "g_head_old_hoxton"
DIGEST = ROOT / "references/arivus_v2/head_v2.json"


def _members(path: Path) -> tuple[dict[str, bytes], list[str]]:
    """Every file in the archive, and the directory entries above them."""
    import py7zr

    with tempfile.TemporaryDirectory() as scratch:
        stage = Path(scratch)
        with py7zr.SevenZipFile(path, mode="r") as archive:
            files = [item.filename for item in archive.list() if not item.is_directory]
            dirs = [item.filename for item in archive.list() if item.is_directory]
            archive.extract(path=stage, targets=files)
        return {name: (stage / name).read_bytes() for name in files}, dirs


def _rewrite(path: Path, members: dict[str, bytes], dirs: list[str]) -> None:
    import py7zr

    with tempfile.TemporaryDirectory() as scratch:
        stage = Path(scratch)
        for name in sorted(members):
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(members[name])
        # fixed settings: one LZMA2 block, sorted member order, so two runs are identical
        with py7zr.SevenZipFile(path, mode="w",
                                filters=[{"id": py7zr.FILTER_LZMA2, "preset": 7}]) as archive:
            for name in sorted(dirs):
                archive.write(stage / name, name)
            for name in sorted(members):
                archive.write(stage / name, name)


DUMP = ROOT / "build/arivus_v2/blend_dump.pkl"


def dump() -> int:
    """Stage 1 (needs a Blender that can read the 5.1 file): write its data to `DUMP`."""
    import pickle

    import bpy
    import numpy as np

    _blend, scratch = _extract()
    bpy.ops.wm.open_mainfile(filepath=str(scratch))
    head = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(MESH_OBJECT))
    arm = head.parent
    mesh = head.data
    count = len(mesh.vertices)
    co = np.zeros(count * 3)
    mesh.vertices.foreach_get("co", co)
    uv = np.zeros(len(mesh.loops) * 2)
    mesh.uv_layers[0].data.foreach_get("uv", uv)
    weights: dict[int, dict[int, float]] = {i: {} for i in range(count)}
    for vertex in mesh.vertices:
        for element in vertex.groups:
            weights[vertex.index][element.group] = element.weight
    document = {
        "blender": ".".join(str(p) for p in bpy.app.version),
        "name": head.name,
        "co": co.reshape(-1, 3),
        "uv": uv.reshape(-1, 2),
        "polys": np.array([tuple(p.vertices) for p in mesh.polygons]),
        "smooth": [p.use_smooth for p in mesh.polygons],
        "groups": [g.name for g in head.vertex_groups],
        "weights": weights,
        "matrix_world": np.array(head.matrix_world),
        "matrix_parent_inverse": np.array(head.matrix_parent_inverse),
        "object_props": {k: str(v) for k, v in head.items()},
        "armature_name": arm.name,
        "armature_matrix": np.array(arm.matrix_world),
        "pose_position": arm.data.pose_position,
        "bones": [{"name": b.name, "head": tuple(b.head_local), "tail": tuple(b.tail_local),
                   "matrix": np.array(b.matrix_local),
                   "parent": b.parent.name if b.parent else None,
                   "connect": b.use_connect} for b in arm.data.bones],
        "pose": [{"name": pb.name, "location": tuple(pb.location), "scale": tuple(pb.scale),
                  "quaternion": tuple(pb.rotation_quaternion), "mode": pb.rotation_mode}
                 for pb in arm.pose.bones],
        "material": mesh.materials[0].name,
        "material_blend_method": mesh.materials[0].blend_method,
        "nodes": [(n.type, n.name, getattr(n, "operation", None))
                  for n in mesh.materials[0].node_tree.nodes],
        "images": [(i.name, bytes(i.packed_file.data), i.filepath, i.colorspace_settings.name)
                   for i in bpy.data.images if i.packed_file],
    }
    DUMP.parent.mkdir(parents=True, exist_ok=True)
    DUMP.write_bytes(pickle.dumps(document))
    print(f"{DUMP.relative_to(ROOT)}: {count} vertices, {len(mesh.polygons)} polygons, "
          f"read by {document['blender']}")
    return 0


def _extract() -> tuple[bytes, Path]:
    """The archive's `.blend`, and a scratch path holding it."""
    members, _dirs = _members(ARCHIVE)
    name = next(name for name in members if name.endswith(MEMBER))
    scratch = ROOT / "build/arivus_v2/blend/source.blend"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_bytes(members[name])
    return name, scratch


def rebuild() -> int:
    """Stage 2 (needs Blender 4.2): rebuild the scene from `DUMP` and repack the archive."""
    import pickle

    import bpy
    from mathutils import Matrix, Vector

    document = pickle.loads(DUMP.read_bytes())
    _member, _scratch = _extract()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    images = {}
    for name, payload, filepath, colorspace in document["images"]:
        image = bpy.data.images.new(name, 2048, 2048, alpha=True)
        image.pack(data=payload, data_len=len(payload))
        image.source, image.filepath = "FILE", filepath
        image.colorspace_settings.name = colorspace
        images[name] = image

    # Blender 4.2 renamed the shader node types its `nodes.new()` takes
    node_type = {"BSDF_PRINCIPLED": "ShaderNodeBsdfPrincipled",
                 "OUTPUT_MATERIAL": "ShaderNodeOutputMaterial", "FRAME": "NodeFrame",
                 "MATH": "ShaderNodeMath", "TEX_IMAGE": "ShaderNodeTexImage",
                 "NORMAL_MAP": "ShaderNodeNormalMap"}
    material = bpy.data.materials.new(document["material"])
    material.use_nodes = True
    tree = material.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)
    for kind, name, operation in document["nodes"]:
        node = tree.nodes.new(node_type.get(kind, kind))
        node.name = name
        if operation:
            node.operation = operation
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    output = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL")
    textures = [n for n in tree.nodes if n.type == "TEX_IMAGE"]
    normal_map = next(n for n in tree.nodes if n.type == "NORMAL_MAP")
    names = sorted(images)
    textures[0].image = images[next(n for n in names if n.endswith("_df"))]
    textures[1].image = images[next(n for n in names if n.endswith("_nm"))]
    tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    tree.links.new(textures[0].outputs["Color"], shader.inputs["Base Color"])
    tree.links.new(textures[0].outputs["Alpha"], shader.inputs["Alpha"])
    tree.links.new(textures[1].outputs["Color"], normal_map.inputs["Color"])
    tree.links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
    subtract = next(n for n in tree.nodes if n.type == "MATH" and n.operation == "SUBTRACT")
    less_than = next(n for n in tree.nodes if n.type == "MATH" and n.operation == "LESS_THAN")
    subtract.inputs[0].default_value, subtract.inputs[1].default_value = 1.0, 0.5
    less_than.inputs[1].default_value = 0.05
    tree.links.new(textures[0].outputs["Alpha"], subtract.inputs[0])
    tree.links.new(subtract.outputs[0], less_than.inputs[0])
    tree.links.new(less_than.outputs[0], output.inputs["Surface"])
    material.blend_method = document["material_blend_method"]

    armature_data = bpy.data.armatures.new(document["armature_name"])
    armature = bpy.data.objects.new(document["armature_name"], armature_data)
    scene.collection.objects.link(armature)
    armature_data.pose_position = document["pose_position"]
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in document["bones"]:
        edit = armature_data.edit_bones.new(bone["name"])
        edit.head, edit.tail = Vector(bone["head"]), Vector(bone["tail"])
        edit.matrix = Matrix(bone["matrix"])
        if bone["parent"]:
            edit.parent = armature_data.edit_bones[bone["parent"]]
        edit.use_connect = bone["connect"]
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.matrix_world = Matrix(document["armature_matrix"])
    for pose in document["pose"]:
        bone = armature.pose.bones[pose["name"]]
        bone.location, bone.scale = pose["location"], pose["scale"]
        bone.rotation_mode = pose["mode"]
        bone.rotation_quaternion = pose["quaternion"]

    mesh = bpy.data.meshes.new(document["name"])
    mesh.from_pydata([tuple(v) for v in document["co"]], [],
                     [tuple(int(i) for i in p) for p in document["polys"]])
    mesh.validate()
    for polygon, smooth in zip(mesh.polygons, document["smooth"]):
        polygon.use_smooth = smooth
    mesh.update()
    layer = mesh.uv_layers.new(name="UVMap")
    for i, loop in enumerate(mesh.loops):
        layer.data[i].uv = (float(document["uv"][i][0]), float(document["uv"][i][1]))
    mesh.materials.append(material)
    head = bpy.data.objects.new(document["name"], mesh)
    scene.collection.objects.link(head)
    head.matrix_world = Matrix(document["matrix_world"])
    head.matrix_parent_inverse = Matrix(document["matrix_parent_inverse"])
    head.parent = armature
    for name in document["groups"]:
        head.vertex_groups.new(name=name)
    groups = {g.name: g for g in head.vertex_groups}
    for vertex, weights in document["weights"].items():
        for index, weight in weights.items():
            groups[document["groups"][index]].add([int(vertex)], float(weight), "REPLACE")
    head.modifiers.new("Armature", "ARMATURE").object = armature
    for key, value in document["object_props"].items():
        head[key] = value

    target = ROOT / "build/arivus_v2/blend/resaved.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(target), compress=True, copy=True)
    members, dirs = _members(ARCHIVE)
    member = next(name for name in members if name.endswith(MEMBER))
    members[member] = target.read_bytes()
    _rewrite(ARCHIVE, members, dirs)
    print(f"{ARCHIVE.relative_to(ROOT)}: rewritten, `{member}` re-saved by {bpy.app.version_string} "
          f"({len(members[member]):,} bytes)")
    print(f"  sha256 {hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()}")
    return 0


def check() -> int:
    """Report what the archive holds and who wrote it; write nothing."""
    import json

    members, _dirs = _members(ARCHIVE)
    digest = json.loads(DIGEST.read_text())
    print(f"{ARCHIVE.relative_to(ROOT)}: {len(members)} member(s) {sorted(members)}")
    member = next(name for name in members if name.endswith(MEMBER))
    print(f"  {member}: {len(members[member]):,} bytes, "
          f"sha256 {hashlib.sha256(members[member]).hexdigest()[:16]}")
    print(f"  the pack's digest names this archive as "
          f"{digest['source']['archive_sha256'][:16]} ({digest['source']['blender_that_wrote_it']})")
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != digest["source"]["archive_sha256"]:
        print("  STALE: the tracked digest was read from another archive than this one")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report, write nothing")
    ap.add_argument("--dump", action="store_true", help="stage 1: dump the scene's data (5.x)")
    ap.add_argument("--rebuild", action="store_true", help="stage 2: rebuild it with 4.2 and repack")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    if args.dump:
        return dump()
    if args.rebuild:
        return rebuild()

    print("nothing to do: pass --check, --dump (stage 1) or --rebuild (stage 2)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
