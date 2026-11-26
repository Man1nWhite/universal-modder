#!/usr/bin/env python3
"""Render the wrist the way the 2026-11-26 first-person captures showed it (D73).

The captures showed the outfit's own wrist standing through the white dress glove's cuff in
weapon poses. This renders the same junction offline, before and after the wrist pass, posed with
the rotations a weapon pose puts on the wrist (a forearm twist that carries the hand, plus a
bend): the outfit's skin in grey, a PD2 glove's `g_hands` shell in blue. The blue is what the
player sees; grey above the blue, at the crease, is skin over the cuff.

    .venv/bin/python tools/pd2-las/wrist_compare.py [--glove sydney] [--pose ext30_twist] OUT.png

"It before" is the body this pass replaced: pass ``--before PATH`` for a model to compare
against (e.g. the tracked one from `git show`), or nothing to draw only the current build.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402
import preview_textured as pt  # noqa: E402

GLOVES = REPO / "references" / "Heister - FPS Gloves in TPS 2.zip"
UNITS = "Heister - FPS Gloves in TPS/Heister - FPS Gloves in TPS/units/"
GLOVE_MODELS = {
    "sydney": UNITS + "pd2_dlc_opera/characters/npc_criminals_fem_3/npc_criminal_sydney.model",
    "joy": UNITS + "pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model",
    "clover": UNITS + "pd2_dlc_chill/characters/shared_character/npc_criminal_female_chill.model",
}


def rot(axis, deg):
    a = np.asarray(axis, dtype=np.float64) / np.linalg.norm(axis)
    t = np.radians(deg)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * k + (1 - np.cos(t)) * (k @ k)


def pose_matrices(template, rotations):
    """Skinning matrices with children following parents (see pose_preview for the convention)."""
    parent = {n: template.id_name.get(template.id_obj[s].get("parent"), "")
              for n, s in template.name_id.items()}
    by_bone: dict[str, list] = {}
    for bone, axis, deg, pivot in rotations:
        by_bone.setdefault(bone, []).append((axis, deg, pivot))
    order, seen = [], set()

    def visit(name):
        if name in seen or name not in template.name_id:
            return
        seen.add(name)
        order.append(name)
        for child, par in parent.items():
            if par == name:
                visit(child)
    visit("Hips")
    order += [n for n in template.name_id if n not in seen]
    acc = {}
    for name in order:
        par = parent.get(name, "")
        a = acc[par].copy() if par in acc else np.eye(4)
        for axis, deg, pivot in by_bone.get(name, ()):
            r = np.eye(4)
            r[:3, :3] = rot(axis, deg)
            t = np.eye(4)
            t[3, :3] = np.asarray(pivot) - np.asarray(pivot) @ r[:3, :3]
            a = a @ (r @ t)
        acc[name] = a
    return {n: a for n, a in acc.items() if n in template.name_id}


def skin(verts, weights, posed):
    acc = np.zeros_like(verts)
    tot = np.zeros(len(verts))
    for i, infl in enumerate(weights):
        for bone, w in infl.items():
            if w <= 0.0 or bone not in posed:
                continue
            acc[i] += w * (np.append(verts[i], 1.0) @ posed[bone])[:3]
            tot[i] += w
    ok = tot > 1e-9
    acc[ok] /= tot[ok, None]
    acc[~ok] = verts[~ok]
    return acc


def read_drawable(path_or_bytes, drawable):
    blob = (path_or_bytes.read_bytes() if isinstance(path_or_bytes, Path) else path_or_bytes)
    mf = dm.ModelFile.read(blob)
    template = bm.template(mf)
    md = next(dm.decode_model_data(s.payload) for s in mf.by_type(dm.MODEL_DATA)
              if dm.decode_model_data(s.payload).get("name_hash") == dm.hash64(drawable))
    gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
    bones = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
    names = [template.id_name.get(o, f"#{o}") for o in bones["objects"]]
    bi = np.asarray(geo["blendindices"], dtype=np.int64)
    bw = np.asarray(geo["blendweights"], dtype=np.float64)
    weights = []
    for i in range(len(bi)):
        d = {}
        for k in range(3):
            if bw[i, k] > 1e-6:
                d[names[bi[i, k]]] = d.get(names[bi[i, k]], 0.0) + float(bw[i, k])
        rest = 1.0 - float(bw[i].sum())
        if rest > 1e-6:
            d[names[bi[i, 3]]] = d.get(names[bi[i, 3]], 0.0) + rest
        weights.append(d)
    return dict(template=template, names=names,
                verts=np.asarray(geo["verts"], dtype=np.float64), weights=weights,
                faces=np.asarray(topo["indices"], dtype=np.int64).reshape(-1, 3),
                normals=np.asarray(geo["normals"], dtype=np.float64),
                uvs=np.asarray(geo["uv0"], dtype=np.float64))


def wrist_poses(template, side):
    key = "Left" if side < 0 else "Right"
    elbow = np.asarray(template.worlds[template.name_id[key + "ForeArm"]][12:15], dtype=np.float64)
    wrist = np.asarray(template.worlds[template.name_id[key + "Hand"]][12:15], dtype=np.float64)
    paxis = np.asarray(bm.palm_planes(template)[side]["axis"], dtype=np.float64)
    faxis = (wrist - elbow) / np.linalg.norm(wrist - elbow)
    ext = np.cross(paxis, faxis)
    ext /= np.linalg.norm(ext)
    twist = [(key + "ForeArmRoll", faxis, 45, wrist), (key + "Hand", faxis, 45, wrist)]
    return {"rest": [], "twist": twist,
            "ext30": [(key + "Hand", ext, 30, wrist)],
            "ext45": [(key + "Hand", ext, 45, wrist)],
            "ext30_twist": twist + [(key + "Hand", ext, 30, wrist)],
            "ext30_roll": [(key + "ForeArmRoll", faxis, 45, wrist), (key + "Hand", ext, 30, wrist)]}


def part(verts, faces, normals, uvs, material, keep=None):
    if keep is not None:
        faces = faces[keep[faces].all(axis=1)]
    used = np.unique(faces)
    remap = np.full(len(verts), -1, np.int64)
    remap[used] = np.arange(len(used))
    return dict(material=material, vertices=verts[used], normals=normals[used],
                uvs=uvs[used], triangles=remap[faces])


STATIONS = (-3.6, -3.0, -2.4, -1.8, -1.2, -0.9)


def wall(points, side, planes, station, half=0.45, rmax=8.0):
    """{sector: largest radius} of one surface in a station band - its wall across the cuff."""
    origin = np.asarray(planes[side]["origin"], dtype=np.float64)
    axis = np.asarray(planes[side]["axis"], dtype=np.float64)
    rel = points - origin
    ax = rel @ axis
    radial = rel - np.outer(ax, axis)
    r = np.linalg.norm(radial, axis=1)
    e1 = np.cross(axis, [0.0, 0.0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    sec = (np.arctan2(radial @ e2, radial @ e1) % (2 * np.pi) / (2 * np.pi) * 12).astype(int) % 12
    out = {}
    for s in range(12):
        m = (np.abs(ax - station) < half) & (sec == s) & (r > 1.0) & (r < rmax)
        if m.any():
            out[s] = float(r[m].max())
    return out


def table(label, body_skin, glove_skin, side, planes):
    """How far the skin's wall stands outside the glove's, per palm-axial station, in mm.

    Negative is the good direction: the glove is still outside the skin there.
    """
    cells = []
    for station in STATIONS:
        a = wall(body_skin, side, planes, station)
        b = wall(glove_skin, side, planes, station)
        gaps = [a[s] - b[s] for s in a if s in b]
        cells.append(f"{max(gaps) * 10.0:+7.1f}" if gaps else "    n/a")
    print(f"  {label:7s}" + "".join(f"{c:>8s}" for c in cells))


def render(out: Path, before: Path | None = None, body: Path | None = None,
           glove: str = "sydney", pose: str = "ext30_twist", side: int = -1,
           size: int = 520) -> Path:
    """Draw the junction before and/or after the wrist pass; returns the sheet's path."""
    body = body or REPO / "build/honoko2/officesuite/officesuite.model"
    with zipfile.ZipFile(GLOVES) as z:
        glove_data = read_drawable(z.read(GLOVE_MODELS[glove]), "g_hands")
    template = glove_data["template"]
    planes = bm.palm_planes(template)
    posed = pose_matrices(template, wrist_poses(template, side)[pose])
    glove_skin = skin(glove_data["verts"], glove_data["weights"], posed)

    print(f"skin outside the glove's cuff, mm (negative = the glove is still outside it), "
          f"{pose} · {glove} · {'left' if side < 0 else 'right'}")
    print(f"  {'':7s}" + "".join(f"{s:+.1f}cm".rjust(8) for s in STATIONS))
    frames = []
    panels = ([("before", before)] if before else []) + [("after", body)]
    for label, path in panels:
        data = read_drawable(path, "g_body")
        ov = skin(data["verts"], data["weights"], posed)
        origin = np.asarray(planes[side]["origin"], dtype=np.float64)
        keep = np.abs(ov[:, 0] - origin[0]) < 14.0
        meshes = [part(ov, data["faces"], data["normals"], data["uvs"], "body", keep),
                  part(glove_skin, glove_data["faces"], glove_data["normals"],
                       glove_data["uvs"], "glove")]
        texture = np.array([[[0.20, 0.35, 0.85, 1.0]]], dtype=np.float32)
        table(label, ov, glove_skin, side, planes)
        img = pt.render(meshes, {"glove": texture}, "threequarter", size, size / 16.0,
                        origin - np.asarray(planes[side]["axis"]) * 0.6, cull=True)
        ImageDraw.Draw(img).text((6, 4), f"{label} · {pose} · {glove}", fill=(235, 235, 235))
        frames.append(img)

    sheet = Image.new("RGB", (size * len(frames), size))
    for i, img in enumerate(frames):
        sheet.paste(img, (i * size, 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print("->", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--glove", default="sydney", choices=sorted(GLOVE_MODELS))
    ap.add_argument("--pose", default="ext30_twist")
    ap.add_argument("--side", default="left", choices=("left", "right"))
    ap.add_argument("--body", type=Path, default=REPO / "build/honoko2/officesuite/officesuite.model")
    ap.add_argument("--before", type=Path, default=None,
                    help="a pre-pass model to draw beside the current one")

    ap.add_argument("--size", type=int, default=520)
    args = ap.parse_args()

    render(args.out, before=args.before, body=args.body, glove=args.glove,
           pose=args.pose, side=-1 if args.side == "left" else 1, size=args.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
