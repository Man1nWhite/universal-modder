#!/usr/bin/env python3
"""Material-isolated elbow review for a built Christie pack.

The ordinary same-colour body renders overlap blazer, shirt, lining and skin.
This sheet draws only the outer blazer at five elbow angles, with independent,
correctly framed front and side cameras, plus the encoded rest-bottom view.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
import build_models as bm  # noqa: E402
import render_mesh_skeleton as rms  # noqa: E402
from elbow_before_after import load_pack, pose_for, window_for  # noqa: E402


def material_subset(geo: dict, material: str) -> dict:
    out = dict(geo)
    out["faces"] = [face for face, name in zip(geo["faces"], geo["face_materials"])
                    if name == material]
    return out


def review(zip_path: Path, out: Path, pack: str, item: str, template_path: Path,
           material: str = "mtr_c02_01") -> None:
    template = bm.load_template(template_path)
    out.mkdir(parents=True, exist_ok=True)
    geo, skel = load_pack(zip_path, pack, item)
    outer = material_subset(geo, material)
    angles = (0, 22, 45, 60, 72)  # template-relative straightening angles
    sheet = Image.new("RGB", (2000, 1000 * len(angles)))
    draw = ImageDraw.Draw(sheet)
    for row, angle in enumerate(angles):
        worlds, bones = pose_for(template, -angle)
        posed = rms.skin_verts(geo, skel, worlds)
        pivot = np.array(worlds[template.name_id["LeftForeArm"]][12:15], float)
        for col, view in enumerate(("side", "front")):
            window, _ = window_for([posed], pivot, view, 6.5)
            depth = float(rms.depth_towards_camera(view, np.atleast_2d(pivot))[0])
            path = out / f"{angle}_{view}.png"
            # Keep the near-shell depth band tight: widening it can hide a
            # genuine gap with unrelated far-side body faces.
            rms.render(outer, bones, view, path, zoom=window, verts=posed,
                       depth=(depth - 9, depth + 9))
            image = Image.open(path).convert("RGB")
            sheet.paste(image, (col * 1000, row * 1000))
            draw.text((col * 1000 + 15, row * 1000 + 15),
                      f"{72 - angle} deg elbow / {view}", fill="white")
    sheet.save(out / "outer_sheet.png")
    bones = rms.rest_skeleton(template, skel)
    rms.render(geo, bones, "bottom", out / "rest_bottom.png")
    rms.render(outer, bones, "bottom", out / "rest_outer_bottom.png")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--pack", default="Christie_LAS")
    parser.add_argument("--item", default="christie")
    parser.add_argument("--templates", type=Path, required=True,
                        help="<2B>/assets/units/2b/skins/2b")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--material", default="mtr_c02_01")
    args = parser.parse_args(argv)
    review(args.zip, args.out, args.pack, args.item,
           args.templates / "2b.model", args.material)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
