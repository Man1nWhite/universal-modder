#!/usr/bin/env python3
"""Extract the PD2 outfit-skeleton contract from a reference LAS unit model.

Reads a Diesel .model (the unit model of a working Legendary Armour Skins pack,
e.g. the `2b.model` inside the user-supplied `2b.rar` reference) and writes a
JSON rig contract: bone object3Ds (name hash, hierarchy, local and world bind
matrices) and each skinned drawable's SkinBones palette layout.

The JSON holds functional skeleton/animation data only — no mesh, texture or
other art is copied. Hashes of known names are verified against `hash64` so the
bipeds are self-describing.

Usage:
    python tools/pd2-port/extract_las_rig.py REFERENCE.model tools/pd2-port/reference/las_rig.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dmodel import DieselModel, hash_str, mmul, minv  # noqa: E402

# Names verified against the reference by hash64 brute force (2026-10-18).
KNOWN_NAMES = [
    "root_point", "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftForeArmRoll", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightForeArmRoll", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
    "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase",
    "s_body", "g_body_lod1", "g_head_lod1", "g_body", "g_head",
    "mtr_body", "mtr_head", "shadow_caster",
]
NAME_BY_HASH = {hash_str(n): n for n in KNOWN_NAMES}


def extract(model_path: str) -> dict:
    m = DieselModel(model_path)
    worlds = m.world_rows()
    objs = {s.id: s for s in m.objects()}
    bones = []
    for s in m.objects():
        if s.tag != "object3D":
            continue
        o = s.obj
        rows = [list(o.matrix[i * 4:(i + 1) * 4]) for i in range(4)]
        rows[3] = [o.pos[0], o.pos[1], o.pos[2], rows[3][3]]
        parent = o.parent_id if o.parent_id in objs and o.parent_id != s.id else 0
        bones.append({
            "id": s.id,
            "name": NAME_BY_HASH.get(o.name_hash),
            "name_hash": f"{o.name_hash:016x}",
            "parent_id": parent,
            "local": rows,
            "world": worlds.get(s.id, rows),
        })
    palettes = []
    for s in m.objects():
        if s.tag != "model_data":
            continue
        md = s.obj
        if not getattr(md, "skinbones_id", 0):
            continue
        sb = m.by_id[md.skinbones_id].obj
        palettes.append({
            "drawable": NAME_BY_HASH.get(md.name_hash, f"#{md.name_hash:016x}"),
            "drawable_hash": f"{md.name_hash:016x}",
            "root_bone_id": sb.root_bone_id,
            "object_ids": sb.object_ids,
            "global_skin_transform": sb.global_skin_transform,
        })
    return {
        "source": "extracted from the user-supplied 2b.rar reference model "
                  "(functional skeleton data only; no art)",
        "matrix_convention": "row-vector System.Numerics style, translation in "
                             "rows[3][0..2], lengths in PD2 cm",
        "bones": bones,
        "skinbones_palettes": palettes,
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    data = extract(sys.argv[1])
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1))
    named = sum(1 for b in data["bones"] if b["name"])
    print(f"wrote {out}: {len(data['bones'])} object3Ds ({named} named), "
          f"{len(data['skinbones_palettes'])} skinned palettes")


if __name__ == "__main__":
    main()
