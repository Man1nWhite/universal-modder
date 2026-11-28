#!/usr/bin/env python3
"""Build `Arivus_over_Hoxton_v2.zip`: the owner's re-sculpted Arivus head over Old Hoxton.

    make -sC tools/pd2-las heads_v2          # writes dist/Arivus/Arivus_over_Hoxton_v2.zip
    .venv/bin/python tools/build_arivus_v2_mod.py --check   # ... and fails if bytes move

This is `build_joy_head_mods.build_arivus_hoxton_mod` (the v1 builder) with one
difference: the head and hair come from the owner's Blender scene, through the tracked
digest `references/arivus_v2/head_v2.json`, instead of from the Random4 `.dff` the v1
pack cuts. Everything after the mesh — the neck skirt, the hair's back faces, the
weights, the atlas and its mip chain, the flat normal map, the icon, the two `.object`
files, the three material configs, the heist/menu/Safe-House models — is the same code,
so the two packs differ only where the scene differs from the `.dff`.

Why the scene at all: it is the owner's own edit of this head, saved with the v1 atlas
packed in. It is the v1 mesh, re-rigged onto three bones and re-sculpted at the crown and
the back of the skull (0.03 cm median from v1, 0.26 cm p95, 0.68 cm max, none of it below
z 168.6), and it already carries v1's neck skirt and the v1 winding. `tests/test_arivus_v2.py`
holds that measurement to the two shipped zips, and holds the parts that must not move
(uv0, weights, the textures, the material, the suit) to the v1 pack's own bytes.

The user-facing difference is real but small, and the pack says so: it is the owner's
re-sculpt, not a new head. `docs/renders/arivus/model/over-hoxton-v2/` is the sheet that
shows it beside v1 from the same three cameras.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent            # the repository root: this file lives in tools/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))

import determinism  # noqa: E402
import build_joy_head_mods as v1  # noqa: E402
from dist_paths import dist_path  # noqa: E402

MESH = ROOT / "references/arivus_v2/head_v2.json"
PACK = dist_path(ROOT, "Arivus_over_Hoxton_v2.zip")
PREFIX = "Arivus over Hoxton v2"
#: the atlas cells the v1 builder cuts the `.dff` into (`extract_arivus_part(5, 0, .5, 0, .5)`
#: for skin, `(6, 0, .5, .5, .5)` for hair). The scene carries the same two cells; a `v`
#: below 0.5 is the cutout hair sheet.
HAIR_V = 0.5


def read_mesh(path: Path = MESH) -> dict:
    """The tracked digest as float arrays, in Diesel centimetres."""
    import numpy as np

    document = json.loads(path.read_text())
    positions = np.asarray(document["positions"], np.float64) * 1e-5
    uv = np.asarray(document["uv"], np.float64) * 1e-6       # (triangle, corner, 2)
    triangles = np.asarray(document["triangles"], np.int32)
    counts = document["counts"]
    if positions.shape != (counts["vertices"], 3):
        raise SystemExit(f"{path}: {positions.shape} of positions for {counts['vertices']} vertices")
    if triangles.shape != (counts["triangles"], 3) or uv.shape != (len(triangles), 3, 2):
        raise SystemExit(f"{path}: {triangles.shape} triangles and {uv.shape} corner UVs")
    # the digest is only trustworthy if it still describes the archive it names
    import hashlib

    archive = ROOT / document["source"]["archive"]
    recorded = document["source"]["archive_sha256"]
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != recorded:
        raise SystemExit(f"{path}: was read from {recorded[:16]}, but {archive.relative_to(ROOT)} "
                         f"is now {actual[:16]}: re-read it with "
                         f"tools/pd2-las/arivus_v2_from_blend.py")
    return {"positions": positions, "uv": uv, "triangles": triangles, "document": document}


def scene_parts(mesh: dict) -> dict[str, dict]:
    """The scene as the two meshes `build_arivus_hoxton_mod` cuts the `.dff` into.

    Same shape as `extract_arivus_part`'s return value, so the v1 pipeline cannot tell
    which source it was handed. The scene is one welded mesh with one vertex per corner
    value, so its corners are the triangle soup the `.dff` route starts from: emit one
    vertex per (triangle, corner) and let `deduplicate_mesh` weld it back.

    The normals are the scene's own per-corner normals, not recomputed from the
    triangles; on a head whose hair is separate cutout cards the two differ, and the
    scene's are the ones the owner sculpted against.
    """
    import numpy as np

    verts = mesh["positions"]
    corner_uv = mesh["uv"]
    triangles = mesh["triangles"]
    corner_normals = mesh.get("corner_normals")
    if corner_normals is None:
        corner_normals = face_normals(verts, triangles)[triangles.ravel()]
    else:
        corner_normals = np.asarray(corner_normals, np.float64) * 1e-6
        corner_normals = corner_normals.reshape(-1, 3)

    hair_tri = corner_uv.mean(axis=1)[:, 1] < HAIR_V
    parts = {}
    for name, wanted in (("head", ~hair_tri), ("hair", hair_tri)):
        tris = triangles[wanted]
        soup = tris.reshape(-1)                       # one vertex per corner, in order
        parts[name] = {
            "verts": verts[soup].astype(np.float32),
            "normals": corner_normals[wanted.reshape(-1, 1).repeat(3, 1).ravel()].astype(np.float32),
            "uvs": corner_uv[wanted].reshape(-1, 2).astype(np.float32),
            "tris": np.arange(len(soup), dtype=np.int32).reshape(-1, 3),
        }
    return parts


def face_normals(positions, triangles):
    """Area-weighted vertex normals, for a digest without the scene's own normals."""
    import numpy as np

    v0, v1, v2 = positions[triangles[:, 0]], positions[triangles[:, 1]], positions[triangles[:, 2]]
    face = np.cross(v1 - v0, v2 - v0)
    normals = np.zeros_like(positions)
    for corner in range(3):
        np.add.at(normals, triangles[:, corner], face)
    return normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)


def build() -> Path:
    determinism.enter(__file__)
    mesh = read_mesh()
    v1.build_arivus_hoxton_mod(
        v1.ensure_arivus_extracted(v1.EXTRACT_DIR / "arivus_extract"),
        v1.ensure_suit_reference(v1.EXTRACT_DIR / "suit_extract"),
        [PACK],
        parts=scene_parts(mesh),
        prefix=PREFIX,
        # the scene was derived from this pack and already carries the D79 skirt
        close_neck=False,
    )
    return PACK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="rebuild into memory and compare with the tracked bytes, writing nothing")
    args = ap.parse_args(argv)
    if not args.check:
        build()
        return 0
    before = PACK.read_bytes()
    build()
    after = PACK.read_bytes()
    if before != after:
        print(f"{PACK.name}: rebuilt bytes differ from the tracked ones")
        return 1
    print(f"{PACK.name}: rebuild reproduced the tracked bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
