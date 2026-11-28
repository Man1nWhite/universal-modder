#!/usr/bin/env python3
"""Read the owner's Arivus v2 Blender scene into the tracked mesh `build_joy_head_mods.py` builds from.

    python tools/bootstrap_bpy.py -- tools/pd2-las/arivus_v2_from_blend.py
        # writes references/arivus_v2/head_v2.json
    python tools/bootstrap_bpy.py -- tools/pd2-las/arivus_v2_from_blend.py --check
        # fails while the tracked file is stale

`references/templates/Arivus Head BLEND.7z` holds one `.blend` (and a copy of the v1
GLB/DDS interchange export beside it). It is a Blender scene of the Arivus head: the
`g_head_old_hoxton` mesh, re-rigged onto three bones and moved vertex by vertex, with
the v1 diffuse and normal maps packed in. This script is the only thing that reads it.

Why a script and not a build step: Blender is not a build dependency of this repository
(D5 — no external tool on the build path), and the pinned `.venv` cannot carry `bpy`
(Blender's Python wheels pin their own NumPy). So the scene is read *once*, here, into a
small tracked file: the mesh's positions, UVs and triangles, quantised and written in a
fixed order, so two runs are byte-identical and the pack builder stays pure Python.

What is read, and why exactly this:

* the **evaluated** mesh, not the object's own coordinates. The object's local mesh is
  in a different space (its armature carries the scale); the armature-modified mesh is
  the one that lands where the v1 pack's head sits — 0.03 cm median from it, and the
  neck identical, which is the measured claim `tests/test_arivus_v2.py` re-checks on the
  shipped packs.
* **positions** in Diesel's axes, times 100: the scene carries the head at the same
  place and in the same orientation as the v1 pack (z up, y forward, metres), so the only
  conversion is metres -> centimetres. (Only the *export* to glTF rotates y-up; the
  `.blend` does not.) Stored as integers in 1e-5 cm (0.1 µm), so the file carries no float formatting.
* **UVs** as the scene stores them, which is already this repository's `uv0`: pairing the
  scene's corners with the shipped head's by UV matches every one of them to 1.3e-8, with
  no flip. Stored as integers in 1e-6.
* **corner normals**, one per loop, as the scene stores them. A head whose hair is
  separate cutout cards has no face normals outside them; these are what the sculpt
  was made against, so the pack ships these rather than re-deriving them from the
  triangles. Stored as integers in 1e-6 (a unit vector, so 0.06 µm per step).
* **triangles** as Blender's polygon order, which is the v1 mesh's winding (measured: the
  v2 scene's 5,716 triangles have 3,486 distinct corner-UV triples, and all 3,486 appear
  in the shipped v1 head drawable).

`--check` re-reads the archive and compares, so the tracked file cannot drift from the
scene it claims to be. It needs `bpy`, which the build `.venv` does not carry (D5), so it
runs in a scratch environment instead:

    python3.11 -m venv "$SCRATCH/blender-venv"
    "$SCRATCH/blender-venv/bin/pip" install 'bpy==5.0.1' py7zr numpy
    "$SCRATCH/blender-venv/bin/python" tools/bootstrap_bpy.py -- \
        tools/pd2-las/arivus_v2_from_blend.py --check

with `SCRATCH` any directory of your own outside the repository. `bootstrap_bpy.py` makes
the GL/X11 stub libraries headless `bpy` needs on a machine without a display and imports
them before `bpy` (see its docstring); without a display and without the stubs, `import bpy`
fails on `libXrender.so.1`.

The tracked `.blend` is now saved by Blender **4.2.23 LTS** — this repository's pinned
Blender — after `resave_arivus_blend.py --rebuild` rewrote it from the 5.1 original
(the scene itself is unchanged: same vertices, UVs, weights and packed images, measured to
8e-6 cm). Any Blender 4.2 or later can read it; the 5.0.1 wheel in the scratch environment
reads it unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "references/templates/Arivus Head BLEND.7z"
MEMBER = "Untitled.blend"
OBJECT = "g_head_old_hoxton"
OUT = ROOT / "references/arivus_v2/head_v2.json"

#: integers, not floats: 1e-5 cm is 0.1 µm, 1e-6 of a UV texel is 1/512 of a texel on
#: the 2048 atlas. Both are far below anything the game or a render can show.
POS_SCALE = 100_000
UV_SCALE = 1_000_000
NORMAL_SCALE = 1_000_000


def blend_header(blend: Path) -> bytes:
    """The `.blend`'s own header — `BLENDER` and its version stamp.

    Blender compresses with zstd by default now, and a compressed `.blend` is a zstd frame
    whose first block begins with the standard Blender header verbatim: the frame's own
    header is at most 18 bytes. Scanning the first 64 bytes for the literal finds it without
    a decompressor, which matters because `zstandard` arrives with Blender's wheel, not with
    `pins.txt` — a reader that imported it would need Blender to read a version stamp.
    """
    raw = blend.read_bytes()
    at = raw[:64].find(b"BLENDER-v")
    if at < 0:
        raise SystemExit(f"{blend.name}: no Blender header in the first 64 bytes "
                         f"({raw[:16]!r}); is this a .blend?")
    return raw[at:at + 16]


def saved_by(blend: Path) -> str:
    """The version stamp in the `.blend`'s own header, as `major.minor`.

    Blender writes `BLENDER` + `-v` + the three digits of `BLENDER_VERSION`, which since
    3.0 is `major * 100 + minor` (`402` is 4.2, `501` is 5.1; before 3.0 the third digit
    was the release, so `280` is 2.80).
    """
    header = blend_header(blend)
    tail = header[7:]                      # `-v402`, or `17-01` before 3.0
    if not tail.startswith(b"-v"):
        raise SystemExit(f"{blend.name}: unreadable version stamp {tail[:5]!r}")
    stamp = tail[2:5].decode("ascii", "replace")
    if not stamp.isdigit():
        raise SystemExit(f"{blend.name}: unreadable version stamp {stamp!r}")
    major = int(stamp[0])
    if major >= 3:
        return f"{major}.{int(stamp[1:])}"
    return f"{major}.{stamp[1]}{stamp[2]}"


def archive_sha256() -> str:
    return hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()


def read_scene() -> dict:
    """The evaluated mesh of ``OBJECT``, in Diesel space, from the archive's `.blend`."""
    import bpy
    import numpy as np
    import py7zr

    scratch = ROOT / "build/arivus_v2/blend"
    scratch.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(ARCHIVE, mode="r") as archive:
        wanted = [name for name in archive.getnames() if name.endswith(MEMBER)]
        if len(wanted) != 1:
            raise SystemExit(f"{ARCHIVE.name}: expected one {MEMBER}, found {wanted}")
        archive.extract(path=scratch, targets=wanted)
    blend = scratch / wanted[0]

    bpy.ops.wm.open_mainfile(filepath=str(blend))
    objects = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(OBJECT)]
    if len(objects) != 1:
        raise SystemExit(f"{blend.name}: expected one mesh named {OBJECT}*, found "
                         f"{[o.name for o in bpy.data.objects]}")
    obj = objects[0]

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        count = len(mesh.vertices)
        co = np.zeros(count * 3)
        mesh.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        # one UV per loop, and Blender stores a polygon's loops consecutively, so this
        # reshapes to (triangle, corner, 2) in the polygons' own order.
        uv = np.zeros(len(mesh.loops) * 2)
        mesh.uv_layers[0].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        # The scene's own corner normals: a head whose hair is separate cutout cards
        # does not have face normals, and the sculpt was made against these.
        corner_normals = np.zeros(len(mesh.corner_normals) * 3)
        mesh.corner_normals.foreach_get("vector", corner_normals)
        corner_normals = corner_normals.reshape(-1, 3)
        polys = [tuple(int(i) for i in p.vertices) for p in mesh.polygons]
        if any(len(p) != 3 for p in polys):
            raise SystemExit(f"{blend.name}: the mesh is not all triangles")
        used = sorted({i for p in polys for i in p})
        if used != list(range(count)):
            raise SystemExit(f"{blend.name}: {count - len(used)} vertices are unused")
    finally:
        evaluated.to_mesh_clear()

    # The scene's own coordinates are already Diesel's axes, in metres: +z up, +y forward.
    diesel = co * 100.0
    # And its UVs are already stored the way this repository stores uv0: measured against
    # the shipped head, the scene's (u, v) is the pack's uv0 corner for corner, to 1.3e-8.
    diesel_uv = uv.copy()

    # The material's own alpha test, recorded so the pack's material can be checked
    # against the scene rather than against a guess (Blender 5 stores alphaMode MASK
    # with this cutoff; EAL 0.05 is the same number the v1 pack's material config uses).
    material = next((m for m in bpy.data.materials if m.name.startswith("mtr_")), None)
    cutoff = None
    images = []
    if material is not None:
        for node in material.node_tree.nodes:
            if node.type == "MATH" and node.operation == "LESS_THAN":
                cutoff = float(node.inputs[1].default_value)
            if node.type == "TEX_IMAGE" and node.image is not None:
                payload = bytes(node.image.packed_file.data) if node.image.packed_file else b""
                images.append({"node": node.label or node.name,
                               "image": node.image.name,
                               "colorspace": node.image.colorspace_settings.name,
                               "width": int(node.image.size[0]), "height": int(node.image.size[1]),
                               "sha256": hashlib.sha256(payload).hexdigest()})
    return {
        "blend_file": blend.name,
        "blender": bpy.data.version,          # the version that read it
        "saved_by": saved_by(blend),           # who wrote the file, from its own header
        "object": obj.name,
        "vertices": count,
        "triangles": len(polys),
        "positions": np.rint(diesel * POS_SCALE).astype(np.int64),
        "uvs": np.rint(diesel_uv * UV_SCALE).astype(np.int64).reshape(-1, 3, 2),
        "corner_normals": np.rint(corner_normals * NORMAL_SCALE).astype(np.int64).reshape(-1, 3, 3),
        "polys": polys,
        "alpha_cutoff": cutoff,
        "images": images,
        "bbox_cm": [np.rint(diesel.min(axis=0) * POS_SCALE).astype(int).tolist(),
                    np.rint(diesel.max(axis=0) * POS_SCALE).astype(int).tolist()],
    }


def as_document(scene: dict) -> dict:
    """The tracked file: the mesh, plus what a reader needs to trust it."""
    return {
        "what": "Arivus head, v2: the g_head_old_hoxton mesh of the owner's Blender scene, "
                "in Diesel space, as build_joy_head_mods.py builds the v2 pack from",
        "generated_by": "tools/pd2-las/arivus_v2_from_blend.py",
        "source": {
            "archive": ARCHIVE.relative_to(ROOT).as_posix(),
            "archive_sha256": archive_sha256(),
            "member": scene["blend_file"],
            "blender_that_wrote_it": scene["saved_by"],
            "blender_that_read_it": ".".join(str(part) for part in scene["blender"]),
            "object": scene["object"],
        },
        "units": {
            "positions": "integer, 1e-5 of a Diesel centimetre",
            "uvs": "integer, 1e-6 of a UV unit, in the pack's own uv0 convention (no flip)",
            "corner_normals": "integer, 1e-6 of a unit vector, one per triangle corner, in triangle order",
            "bbox": "integer, 1e-5 of a centimetre",
            "positions_convention": "Blender y-up metres -> Diesel z-up centimetres, (x, -z, y) * 100",
        },
        "counts": {"vertices": scene["vertices"], "triangles": scene["triangles"]},
        "bbox_cm": scene["bbox_cm"],  # integer, 1e-4 cm
        "alpha_cutoff": scene["alpha_cutoff"],
        "images": scene["images"],
        "uv": [[[int(a) for a in corner] for corner in scene["uvs"][i]]
               for i in range(len(scene["polys"]))],
        "corner_normals": [[[int(a) for a in corner] for corner in scene["corner_normals"][i]]
                           for i in range(len(scene["polys"]))],
        "positions": [[int(v) for v in row] for row in scene["positions"]],
        "triangles": [[int(a) for a in tri] for tri in scene["polys"]],
    }


def write(document: dict) -> bytes:
    """Fixed key order, one row per line: a diff of this file is a diff of the mesh."""
    lines = ["{"]
    for key, value in document.items():
        if key in ("positions", "triangles", "uv", "corner_normals"):
            rows = json.dumps(value)[1:-1]
            rows = rows.replace("]], [[[", "]],\n[[[").replace("], [", "], [")
            lines.append(f' "{key}": [{rows}],')
        else:
            lines.append(f' "{key}": {json.dumps(value, sort_keys=True)},')
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail while the tracked file is stale")
    args = parser.parse_args(argv)

    scene = read_scene()
    payload = write(as_document(scene))
    if args.check:
        if not OUT.is_file():
            raise SystemExit(f"{OUT.relative_to(ROOT).as_posix()} is missing; run "
                             "python tools/pd2-las/arivus_v2_from_blend.py")
        tracked = OUT.read_bytes()
        if tracked != payload:
            raise SystemExit(f"{OUT.relative_to(ROOT).as_posix()} is stale: the scene now reads "
                             f"{len(payload)} bytes, the tracked file is {len(tracked)}")
        print(f"{OUT.relative_to(ROOT).as_posix()}: up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}: {scene['vertices']} vertices, "
          f"{scene['triangles']} triangles, {len(payload)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
