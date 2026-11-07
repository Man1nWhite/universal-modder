"""Measure the head <-> body neck junction of a LAS body with a heister head.

The LAS packs are *headless*: they replace the heister's body and keep whatever
head the heister has, including the nine head-replacement packs in
`tools/build_joy_head_mods.py`. Nothing in either pack knows about the other, so
the throat is where the two meshes have to agree on their own. This tool puts
the body and the head in one space, ray-casts the throat from the front and
reports which mesh the visible surface belongs to.

Why that matters: the 2026-11-07 Christie review (item 7) saw a hard tonal
boundary on the throat, pale on one side and tan on the other. Pale-against-tan
is what two *skins* look like when the head's neck skirt and the body's neck
surface interpenetrate, and the boundary is ragged because the winner changes
from triangle to triangle.

    .venv/bin/python tools/pd2-las/neck_junction.py \
        --body dist/Christie_LAS.zip \
        --head dist/Miranda_L4D2_over_Joy.zip

Reported per head:

* the head's neck border -- the lowest boundary loop near the neck axis. That
  border is the edge the head model *ends* on, i.e. the line the body has to
  hide;
* the throat window (front of the neck): share of cells where the head is in
  front, where the body is in front, and where a ray misses everything;
* ``--render`` writes a tinted composite (head orange, body grey) so the
  raggedness is visible without guessing from a compressed screenshot.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pd2-port"))

CHRISTIE_BODY = REPO / "dist" / "Christie_LAS.zip"
HEADS = (
    REPO / "dist" / "Miranda_L4D2_over_Joy.zip",
    REPO / "dist" / "Miranda_L4D2_over_Clover.zip",
    REPO / "dist" / "Miranda_L4D2_over_Bonnie.zip",
    REPO / "dist" / "Miranda_L4D2_over_Sydney.zip",
)

THROAT = dict(x=(-6.0, 6.0), z=(149.0, 161.0), step=0.25)


def _body_mesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Vertices and triangles of the pack's `g_body` drawable."""
    import audit_metrics as am

    geo, top = am._drawable(am._model_bytes(path), "g_body")
    return (np.asarray(geo["verts"], float),
            np.asarray(top["indices"], int).reshape(-1, 3))


def _head_mesh(path: Path, tmp: Path) -> tuple[np.ndarray, np.ndarray]:
    """Vertices and triangles of the pack's head drawable.

    The drawable is not always called ``g_head``: Clover's pack ships it as
    ``g_head_fem1`` (4,402 verts / 7,109 tris, like the other seven), so the
    name is matched as a prefix and the largest match wins - ``c_headphys*``
    collision boxes are 24-vertex cubes and lose that comparison anyway.
    """
    import diesel_model as dm

    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist()
                 if n.endswith(".model") and "_menu" not in n and "/fps_" not in n]
        if not names:
            raise SystemExit(f"{path.name}: no .model")
        blob = zf.read(names[0])
    mf = dm.ModelFile.read(blob)
    hashlist = mf.by_type(dm.CUSTOM_HASHLIST)
    known = (dm.decode_custom_hashlist(hashlist[0].payload)["names"]
             if hashlist else [])
    best = None
    for section in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(section.payload)
        name = next((n for n in known if dm.hash64(n) == md["name_hash"]), "")
        if not name.startswith("g_head") or md.get("version") != 3:
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        verts = np.asarray(geo["verts"], float)
        faces = np.asarray(topo["indices"], int).reshape(-1, 3)
        if best is None or len(verts) > len(best[0]):
            best = (verts, faces, name)
    if best is None:
        raise SystemExit(f"{path.name}: no g_head* drawable")
    return best[0], best[1]


def front_depth(verts, faces, xs, zs, y0: float = 60.0) -> np.ndarray:
    """Front-most y of any hit per (x, z) cell; NaN where a ray misses."""
    tri = verts[faces]
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    d = np.array([0.0, -1.0, 0.0])
    pv = np.cross(np.broadcast_to(d, e2.shape), e2)
    det = np.einsum("ij,ij->i", e1, pv)
    ok = np.abs(det) > 1e-9
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    out = np.full((len(zs), len(xs)), np.nan)
    for iz, z in enumerate(zs):
        for ix, x in enumerate(xs):
            tv = np.array([x, y0, z]) - v0
            u = np.einsum("ij,ij->i", tv, pv) * inv
            qv = np.cross(tv, e1)
            w = (qv @ d) * inv
            t = np.einsum("ij,ij->i", e2, qv) * inv
            hit = ok & (u >= 0) & (u <= 1) & (w >= 0) & (u + w <= 1) & (t > 0)
            if hit.any():
                out[iz, ix] = y0 - t[hit].min()
    return out


def neck_border(verts, faces, *, min_z: float = 145.0) -> dict:
    """The lowest boundary loop near the neck axis: z range, radius, size."""
    import diagnose_mesh as dg

    edges, bverts = dg.boundary(faces)
    best = None
    for loop in dg.loops_of(edges, bverts):
        pts = verts[loop]
        centre = pts.mean(axis=0)
        if abs(centre[0]) > 4.0 or centre[2] < min_z:
            continue
        radius = float(np.hypot(pts[:, 0] - centre[0],
                                pts[:, 1] - centre[1]).mean())
        if radius > 8.0:
            continue
        if best is None or pts[:, 2].min() < best["z"][0]:
            best = {"n": len(loop), "z": (float(pts[:, 2].min()),
                                          float(pts[:, 2].max())),
                    "radius": radius,
                    "centre": (float(centre[0]), float(centre[1]))}
    return best or {}


def junction(body: Path, head: Path, tmp: Path) -> dict:
    bv, bf = _body_mesh(body)
    hv, hf = _head_mesh(head, tmp)
    xs = np.arange(THROAT["x"][0], THROAT["x"][1] + 1e-9, THROAT["step"])
    zs = np.arange(THROAT["z"][0], THROAT["z"][1] + 1e-9, THROAT["step"])
    db = front_depth(bv, bf, xs, zs)
    dh = front_depth(hv, hf, xs, zs)
    body_wins = np.isfinite(db) & (~np.isfinite(dh) | (db <= dh + 0.02))
    head_wins = np.isfinite(dh) & (~np.isfinite(db) | (dh < db - 0.02))
    seen = body_wins | head_wins
    return {
        "labels": (np.round(xs, 2), np.round(zs, 2)),
        "grid": {"body": body_wins, "head": head_wins, "miss": ~seen},
        "depth": (db, dh),
        "head_border": neck_border(hv, hf),
        "body_border": neck_border(bv, bf),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--body", type=Path, default=CHRISTIE_BODY)
    ap.add_argument("--head", type=Path, action="append")
    ap.add_argument("--render", type=Path, help="write a tinted composite PNG")
    args = ap.parse_args(argv)
    if not args.body.is_file():
        raise SystemExit(f"missing body pack {args.body}")

    heads = [Path(h) for h in (args.head or HEADS)]
    tmp = Path("/tmp/neck_junction")
    tmp.mkdir(parents=True, exist_ok=True)
    rendered = 0
    for head in heads:
        if not head.is_file():
            print(f"{head.name}: not built")
            continue
        rep = junction(args.body, head, tmp)
        total = rep["grid"]["body"].size
        print(f"\n== {head.name} over {args.body.name}")
        b = rep["body_border"]
        if b:
            print(f"   body neck border: {b['n']} verts, z {b['z'][0]:.1f}-{b['z'][1]:.1f}, "
                  f"radius {b['radius']:.2f} cm")
        h = rep["head_border"]
        if h:
            print(f"   head neck border: {h['n']} verts, z {h['z'][0]:.1f}-{h['z'][1]:.1f}, "
                  f"radius {h['radius']:.2f} cm")
        else:
            print("   head neck border: none found near the axis")
        for key, label in (("body", "body in front"), ("head", "head in front"),
                           ("miss", "see-through")):
            share = rep["grid"][key].sum() / total * 100
            print(f"   {label:14s} {share:5.1f} % of the throat window")
        if args.render and not rendered:
            _render(args.body, head, args.render, tmp)
            rendered += 1
    return 0


def _render(body: Path, head: Path, out: Path, tmp: Path) -> None:
    from PIL import Image

    import shellview

    bv, bf = _body_mesh(body)
    hv, hf = _head_mesh(head, tmp)
    verts = np.vstack([bv, hv])
    faces = np.vstack([bf, hf + len(bv)])
    colours = np.vstack([np.tile([0.62, 0.66, 0.72], (len(bf), 1)),
                         np.tile([0.95, 0.45, 0.15], (len(hf), 1))])
    img = shellview.render(verts, faces, colours,
                     np.array([0.0, -40.0, 154.0]), np.array([0.0, 0.0, 154.0]),
                     np.array([0.0, 0.0, 1.0]), width=520, height=520, fov=26.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(out)
    print(f"   wrote {out} (head orange, body grey)")


if __name__ == "__main__":
    raise SystemExit(main())
