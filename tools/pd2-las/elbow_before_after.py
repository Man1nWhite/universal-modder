#!/usr/bin/env python3
"""Before/after sheets for the two things that read as "bad arms" in game.

Three composites, all built the same way:

    --mode elbow   the elbow at 47 / 22 / 12 deg (12 deg = the in-game idle)
    --mode cuff    the sleeve mouth at the idle pose, front and side
    --mode idle    just the idle elbow, one row (the file the docs link to)

Each row is one camera/pose; the left column is the pack you shipped and the
right column is the new build. The crop window for a row is computed from the
**union of both columns' geometry**, is square, and the two panels therefore
share scale, centre and depth band - the previous sheet let each panel auto-
frame its own subset, so "the mesh changed" and "the camera changed" were
indistinguishable, which is worse than no picture at all. The window size in
cm is printed in the row label so the scale is on the page.

Usage (the "before" pack is whatever you last shipped, e.g. from git):

    git show <sha>:dist/Christie_LAS.zip > build/before.zip
    .venv/bin/python tools/pd2-las/elbow_before_after.py --mode elbow \\
        --pack Christie_LAS --item christie \\
        --before build/before.zip --after dist/Christie_LAS.zip \\
        --templates "<2B>/assets/units/2b/skins/2b" \\
        --out docs/pd2-las/renders

The pose is the renderer's in-game idle: shoulder (2, 22), elbow on the
flexion axis (`render_mesh_skeleton.BEND_AXIS`), wrist eased 8 deg.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))
import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402
import render_mesh_skeleton as rms  # noqa: E402

PANEL = 1000
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
#: (straightening on the flexion axis, elbow angle it produces)
ELBOW_ROWS = ((-25.0, "47"), (-50.0, "22"), (-60.0, "12"))
CUFF_ROWS = (("front", "front - looking along -y"),
             ("side", "side - character's left, looking along +x"))


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except OSError:                       # no DejaVu: fall back, still legible
        return ImageFont.load_default()


def load_pack(zip_path: Path, pack: str, item: str):
    """g_body geometry + skinbones out of one pack zip (same parse as the
    renderer, so a panel and a `--zip` render are the same picture)."""
    with zipfile.ZipFile(zip_path) as zf:
        geo = rms.g_body_geo(zf, pack, item)
        mf = dm.ModelFile.read(
            zf.read(f"{pack}/assets/units/{item}/skins/{item}/{item}.model"))
        hl = dm.decode_custom_hashlist(
            mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
        for s in mf.by_type(dm.MODEL_DATA):
            md = dm.decode_model_data(s.payload)
            name = next((n for n in hl if dm.hash64(n) == md["name_hash"]), "")
            if name == "g_body" and md.get("version") == 3:
                return geo, dm.decode_skinbones(
                    mf.by_id(md["skinbones"]).payload)
    raise SystemExit(f"no g_body in {zip_path}")


def pose_for(template, straighten: float):
    pose = {f"{s}Arm": (2, 22) for s in ("Left", "Right")}
    pose.update({f"{s}ForeArm": (rms.BEND_AXIS, straighten)
                 for s in ("Left", "Right")})
    pose.update({f"{s}Hand": (rms.BEND_AXIS, -8) for s in ("Left", "Right")})
    pw = rms.posed_worlds(template, pose)
    bones = [(template.id_name[sid], np.array(pw[sid][12:15], float),
              template.id_name.get(template.id_obj[sid]["parent"])
              if template.id_obj[sid]["parent"] else None)
             for sid in pw]
    return pw, bones


def window_for(posed, pivot, view: str, radius: float, pad: float = 0.35):
    """Square screen window around `pivot` covering every posed mesh given."""
    pts = [pv[np.linalg.norm(pv - pivot, axis=1) <= radius] for pv in posed]
    p = np.vstack(pts)
    uv = rms.project(p, view)
    side = max(np.ptp(uv[:, 0]), np.ptp(uv[:, 1])) + 2.0 * pad
    cu, cv = 0.5 * (uv[:, 0].min() + uv[:, 0].max()), 0.5 * (
        uv[:, 1].min() + uv[:, 1].max())
    return (cu - side / 2, cu + side / 2, cv - side / 2, cv + side / 2), side


def render_panel(geo, bones, posed, win, pivot, out: Path, title: str,
                 view: str, band_cm: float) -> Image.Image:
    d0 = float(rms.depth_towards_camera(view, np.atleast_2d(pivot))[0])
    rms.render(geo, bones, view, out, zoom=win, verts=posed,
               depth=(d0 - band_cm, d0 + band_cm))
    img = Image.open(out).convert("RGB")
    # the renderer stamps its bone-colour legend in the top-left corner; the
    # sheet already colours the arm chain, so that space carries the label
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 470, 44], fill=(24, 24, 28))
    d.text((12, 8), title, font=_font(FONT_B, 26), fill=(255, 255, 255))
    return img


def compose(panels, row_labels, caption, out: Path, header: str):
    rows, cols = len(panels), 2
    pad, top = 16, 70
    W = cols * PANEL + (cols + 1) * pad
    H = top + rows * (PANEL + 34 + pad) + 30 * len(caption) + 30
    sheet = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 14), header, font=_font(FONT_B, 34), fill=(20, 20, 20))
    for r, row in enumerate(panels):
        y = top + r * (PANEL + 34 + pad)
        for c, img in enumerate(row):
            x = pad + c * (PANEL + pad)
            sheet.paste(img, (x, y + 34))
            d.rectangle([x, y + 34, x + PANEL, y + 34 + PANEL],
                        outline=(150, 150, 150))
        d.text((pad, y), row_labels[r], font=_font(FONT, 26), fill=(20, 20, 20))
    y = top + rows * (PANEL + 34 + pad) + 10
    for line in caption:
        d.text((pad, y), line, font=_font(FONT, 22), fill=(40, 40, 40))
        y += 30
    sheet.save(out)
    print(f"wrote {out} {sheet.size}")


def build_panels(args, template, rows):
    geo_b, skel_b = load_pack(args.before, args.pack, args.item)
    geo_a, skel_a = load_pack(args.after, args.pack, args.item)
    panels, labels = [], []
    for r, (view, straighten, label, joint, radius, band) in enumerate(rows):
        pw, bones = pose_for(template, straighten)
        pb = rms.skin_verts(geo_b, skel_b, pw)
        pa = rms.skin_verts(geo_a, skel_a, pw)
        pivot = np.array(pw[template.name_id[joint]][12:15], float)
        win, size = window_for([pb, pa], pivot, view, radius)
        left = render_panel(geo_b, bones, pb, win, pivot,
                            args.scratch / f"{args.item}_r{r}_before.png",
                            "BEFORE - previously shipped pack", view, band)
        right = render_panel(geo_a, bones, pa, win, pivot,
                             args.scratch / f"{args.item}_r{r}_after.png",
                             "AFTER - this build", view, band)
        print(f"  row {r}: {view} {straighten:+.0f} deg, frame {size:.1f} cm")
        panels.append([left, right])
        labels.append(label.format(size=size))
    return panels, labels


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("elbow", "cuff", "idle"), default="elbow")
    ap.add_argument("--pack", default="Christie_LAS")
    ap.add_argument("--item", default="christie")
    ap.add_argument("--before", type=Path, required=True,
                    help="previously shipped pack zip (e.g. git show <sha>:dist/...)")
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--templates", type=Path, required=True,
                    help="<2B>/assets/units/2b/skins/2b")
    ap.add_argument("--out", type=Path, default=REPO / "docs/pd2-las/renders")
    ap.add_argument("--scratch", type=Path, default=REPO / "build/pd2-las/panels")
    ap.add_argument("--suffix", default=None,
                    help="file-name stem suffix (default: from --item)")
    ap.add_argument("--note", action="append", default=[],
                    help="extra caption line (measurements for this pack); "
                         "repeatable - the numbers are per pack and this tool "
                         "cannot measure them")
    args = ap.parse_args(argv)
    template = bm.load_template(args.templates / "2b.model")
    args.out.mkdir(parents=True, exist_ok=True)
    args.scratch.mkdir(parents=True, exist_ok=True)
    stem = args.suffix or args.item
    slim = "slim" in (args.pack + args.item).lower()
    name = f"Christie {'slim ' if slim else ''}"
    shipped = ("before = previously shipped pack (left). after = this build "
               "(right). Same row = same crop, scale and depth band")
    if args.mode == "elbow":
        rows = [("side", s, f"elbow {elbow} deg - frame {{size:.1f}} cm square",
                 "LeftForeArm", 6.5, 9.0)
                for s, elbow in ELBOW_ROWS]
        panels, labels = build_panels(args, template, rows)
        compose(panels, labels, [
            shipped + " (window = union of both panels).",
            "after = 12 deg authoring rest + seam-welded Taubin relaxation.",
            *args.note,
        ], args.out / f"{stem}_elbow_bend_before_after.png",
            f"{name}elbow: shipped (left) vs current build (right)")
    elif args.mode == "idle":
        rows = [("side", ELBOW_ROWS[-1][0],
                 "in-game idle, elbow " + ELBOW_ROWS[-1][1] +
                 " deg - frame {size:.1f} cm", "LeftForeArm", 6.5, 9.0)]
        panels, labels = build_panels(args, template, rows)
        compose(panels, labels, [
            shipped + " (window = union of both panels).",
            "in-game idle = shoulder (2, 22), elbow straightened 72 -> 12 deg "
            "on the flexion axis, wrist -8 deg.",
            *args.note,
        ], args.out / f"{stem}_elbow_idle_before_after.png",
            f"{name}elbow at the in-game idle: shipped (left) vs current build (right)")
    else:
        rows = [(view, ELBOW_ROWS[-1][0],
                 f"cuff at the idle pose - {label} - frame {{size:.1f}} cm",
                 "LeftHand", 6.0, 7.0) for view, label in CUFF_ROWS]
        panels, labels = build_panels(args, template, rows)
        compose(panels, labels, [
            shipped + " (window = union of both panels).",
            "after = cuff taper: radial 1 - 0.28 on the outer shell over the "
            "last 9 cm, floor 3 cm, 0.5 cm clearance to the hand.",
            "the mouth keeps its axial position, so the in-game glove spawn "
            "is unchanged.",
            *args.note,
        ], args.out / f"{stem}_cuff_before_after.png",
            f"{name}cuff: shipped (left) vs current build (right)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
