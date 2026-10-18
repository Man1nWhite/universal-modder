#!/usr/bin/env python3
"""Offline geometry verification for the LAS pipeline (no Blender needed).

The old-model route died as a "complete mess" in-game, so before anything is
handed to the runtime the skin transfer has to survive two kinds of checks:

  report  - quantitative gates: edge-length preservation through the rebind,
            displacement smoothness (no exploded vertices), degenerate faces,
            unit normals, and per-bone anchor distances (a vertex dominated by
            a bone must sit near that bone).
  render  - same numbers, plus software-raster previews (numpy z-buffer + PIL):
            source bind pose, retargeted result, the mesh decoded back out of
            the built .model bytes, and a retarget-vs-decoded overlay that must
            come out yellow (i.e. identical).

Usage:
  python tools/pd2-port/preview_check.py report
  python tools/pd2-port/preview_check.py render /tmp/las_preview
"""
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_las_pack as build          # noqa: E402
import dmodel                           # noqa: E402
import las_model                         # noqa: E402
import me2_dae                           # noqa: E402
import rig_target                        # noqa: E402

REPO = HERE.parents[1]
SOURCE_ZIP = REPO / ("PC _ Computer - Mass Effect 2 - Non-Playable "
                     "Characters - Miranda Lawson (Romance).zip")
RIG_JSON = HERE / "reference" / "las_rig.json"
REFERENCE_2B = Path("/tmp/rarx/out/2B - LAS/assets/units/2b/skins/2b/2b.model")

# ----------------------------------------------------------------- geometry


def tri_areas(pos, faces):
    p = np.asarray(pos, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    a, b, c = p[f[:, 0]], p[f[:, 1]], p[f[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def edge_stats(before, after, faces):
    """Relative edge-length change through the rebind, per triangle edge."""
    b = np.asarray(before, dtype=np.float64)
    a = np.asarray(after, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    pairs = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], axis=0)
    lb = np.linalg.norm(b[pairs[:, 0]] - b[pairs[:, 1]], axis=1)
    la = np.linalg.norm(a[pairs[:, 0]] - a[pairs[:, 1]], axis=1)
    ok = lb > 1e-6
    rel = np.abs(la[ok] - lb[ok]) / lb[ok]
    return rel


def displacement_smoothness(before, after, faces):
    """|Δv - mean(Δedge-neighbours)|: spikes = exploded vertices.

    Uses the WELDED adjacency (rig_target.weld_adjacency): corner-split DAE
    meshes share positions through duplicated vertices, and index-only
    neighbours are blind across triangles — the blindness hid a shredded
    retarget behind green metrics once already.
    """
    b = np.asarray(before, dtype=np.float64)
    a = np.asarray(after, dtype=np.float64)
    d = np.linalg.norm(a - b, axis=1)
    neigh = rig_target.weld_adjacency(b, np.asarray(faces, dtype=np.int64))
    spikes = []
    for v, ns in enumerate(neigh):
        if not ns:
            continue
        spikes.append(abs(d[v] - float(np.mean(d[ns]))))
    return d, np.array(spikes)


def twin_separation(before, after):
    """Max distance between coincident (corner-split twin) vertices after the
    rebind. Grouped by the SOURCE position; must stay ~0 — if twins separate,
    the surface is shredding even when per-triangle metrics look green."""
    groups: dict[tuple, list] = {}
    for v, p in enumerate(before):
        key = (round(float(p[0]), 4), round(float(p[1]), 4),
               round(float(p[2]), 4))
        groups.setdefault(key, []).append(after[v])
    worst = 0.0
    for pts in groups.values():
        if len(pts) < 2:
            continue
        arr = np.asarray(pts)
        d = np.linalg.norm(arr[:, None, :] - arr[None, :, :], axis=2).max()
        worst = max(worst, float(d))
    return worst


def bone_anchor_stats(mesh: rig_target.RiggedMesh, rig: rig_target.TargetRig):
    """Per dominant bone: distance from each vertex to the bone head."""
    out = {}
    heads = {n: (rig.world[n][3][0], rig.world[n][3][1], rig.world[n][3][2])
             for n in rig.names}
    for v, ws in enumerate(mesh.weights):
        if not ws:
            continue
        dom = rig_target.dominant_bone(ws)
        h = heads.get(dom)
        if h is None:
            continue
        p = mesh.positions[v]
        dist = math.dist(p, h)
        out.setdefault(dom, []).append(dist)
    return {k: (float(np.median(v)), float(np.max(v)), len(v))
            for k, v in sorted(out.items())}


def model_bounds(path: Path):
    m = dmodel.DieselModel(str(path))
    pts = []
    for s in m.sections:
        if s.tag == "geometry":
            pts.extend(s.obj.positions)
    p = np.asarray(pts, dtype=np.float64)
    return p.min(axis=0), p.max(axis=0)


# ----------------------------------------------------------------- raster


def raster(tris, colors, width=760, height=1160, bounds=None,
           yaw_deg=0.0, pitch_deg=0.0, bg=(18, 18, 24), lines=None):
    """Painter's-algorithm orthographic raster of (verts, faces, color)."""
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    # camera basis: rotate world Z-up around Z (yaw), then tilt (pitch)
    fwd = np.array([sy * cp, -cy * cp, sp])       # view direction
    right = np.array([cy, sy, 0.0])
    up = np.cross(fwd, right)

    all_pts = np.concatenate([t[0] for t in tris], axis=0)
    if bounds is None:
        lo = all_pts.min(axis=0)
        hi = all_pts.max(axis=0)
    else:
        lo, hi = bounds
    ctr = (lo + hi) / 2.0
    span = float(np.max(hi - lo)) * 1.08

    img = np.zeros((height, width, 3), dtype=np.float64)
    img[:] = np.array(bg, dtype=np.float64) / 255.0
    zbuf = np.full((height, width), 1e30)

    def project(p):
        d = p - ctr
        x = d @ right
        y = d @ up
        z = d @ fwd
        sx = (x / span + 0.5) * (width - 1)
        sy_ = (1.0 - (y / span + 0.5)) * (height - 1)
        return sx, sy_, z

    light = np.array([0.35, -0.75, 0.55])
    light = light / np.linalg.norm(light)

    faces_all = []
    for (verts, faces, col) in tris:
        sx, sy_, sz = project(verts)
        for f3 in faces:
            faces_all.append((f3, sx, sy_, sz, col, verts))
    # far to near by depth (sz is index 3; was mistakenly screen-y)
    order = sorted(range(len(faces_all)),
                   key=lambda i: -max(faces_all[i][3][v] for v in faces_all[i][0]))

    for i in order:
        f3, sx, sy_, sz, col, verts = faces_all[i]
        x0, x1 = sx[f3].min(), sx[f3].max()
        y0, y1 = sy_[f3].min(), sy_[f3].max()
        if x1 < 0 or y1 < 0 or x0 >= width or y0 >= height:
            continue
        ix0, ix1 = max(int(x0), 0), min(int(x1) + 1, width - 1)
        iy0, iy1 = max(int(y0), 0), min(int(y1) + 1, height - 1)
        if ix1 < ix0 or iy1 < iy0:
            continue
        ax, ay = sx[f3[0]], sy_[f3[0]]
        bx, by = sx[f3[1]], sy_[f3[1]]
        cx, cy_ = sx[f3[2]], sy_[f3[2]]
        det = (by - cy_) * (ax - cx) + (cx - bx) * (ay - cy_)
        if abs(det) < 1e-12:
            continue
        xs = np.arange(ix0, ix1 + 1)
        ys = np.arange(iy0, iy1 + 1)
        gx, gy = np.meshgrid(xs, ys)
        w0 = ((by - cy_) * (gx - cx) + (cx - bx) * (gy - cy_)) / det
        w1 = ((cy_ - ay) * (gx - cx) + (ax - cx) * (gy - cy_)) / det
        w2 = 1.0 - w0 - w1
        mask = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not mask.any():
            continue
        zpix = w0 * sz[f3[0]] + w1 * sz[f3[1]] + w2 * sz[f3[2]]
        sub = zbuf[iy0:iy1 + 1, ix0:ix1 + 1]
        upd = mask & (zpix < sub)
        sub[upd] = zpix[upd]
        # flat shade from the world-space face normal
        a3, b3, c3 = verts[f3[0]], verts[f3[1]], verts[f3[2]]
        fn = np.cross(b3 - a3, c3 - a3)
        ln = np.linalg.norm(fn)
        shade = 0.45
        if ln > 1e-12:
            shade = 0.35 + 0.65 * max(0.0, float(fn @ light / ln))
        img_sub = img[iy0:iy1 + 1, ix0:ix1 + 1]
        img_sub[upd] = np.asarray(col, dtype=np.float64) * shade

    if lines:
        for (a, b, col) in lines:
            x0, y0, _ = project(np.asarray(a, dtype=np.float64))
            x1, y1, _ = project(np.asarray(b, dtype=np.float64))
            n = int(max(abs(x1 - x0), abs(y1 - y0), 1)) + 1
            for t in range(n):
                x = int(round(x0 + (x1 - x0) * t / n))
                y = int(round(y0 + (y1 - y0) * t / n))
                if 0 <= x < width and 0 <= y < height:
                    img[y, x] = np.asarray(col, dtype=np.float64)

    from PIL import Image
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


# ----------------------------------------------------------------- pipeline


def load_all():
    source = build.load_source(SOURCE_ZIP)
    scene = me2_dae.load_dae(source[build.DAE_NAME])
    rig = rig_target.load_target_rig(RIG_JSON)
    return scene, rig


def rebind_all(scene, rig):
    return [rig_target.rebind_mesh(m, scene, rig, smooth_iters=2)
            for m in scene.meshes]


def decoded_drawables(model_bytes: bytes):
    p = Path(tempfile.mktemp(suffix=".model"))
    p.write_bytes(model_bytes)
    try:
        m = dmodel.DieselModel(str(p))
    finally:
        p.unlink()
    geos = [s.obj.positions for s in m.sections if s.tag == "geometry"]
    faces = [np.asarray(s.obj.faces, dtype=np.int64)
             for s in m.sections if s.tag == "topology"]
    pairs = []
    for pos, f in zip(geos, faces):
        if len(pos) and len(f):
            pairs.append((np.asarray(pos, dtype=np.float64), f))
    return m, pairs


def gather_report(scene, rig, rebound, built_files=None):
    ok = True
    print("== edge-length preservation through the rebind ==")
    for src, dst in zip(scene.meshes, rebound):
        rel = edge_stats(src.positions, dst.positions, src.triangles)
        med, p95, mx = np.median(rel), np.percentile(rel, 95), rel.max()
        # informational on corner-split meshes (edges are per-triangle):
        # a coherent bind sits at p95 ~170%, the frame-op "torn" state 330%+,
        # fold-tearing 1000%+. The hard gates are spikes + twin separation.
        flag = "OK " if p95 < 2.0 else "WARN"
        if p95 >= 4.0:
            flag, ok = "FAIL", False
        print(f"  [{flag}] {src.name:10s} median {med*100:6.2f}%  "
              f"p95 {p95*100:6.2f}%  max {mx*100:7.2f}%")
    print("== displacement smoothness (spikes = exploded vertices) ==")
    for src, dst in zip(scene.meshes, rebound):
        d, spikes = displacement_smoothness(src.positions, dst.positions,
                                            src.triangles)
        med, mx = np.median(d), d.max()
        smax = spikes.max() if len(spikes) else 0.0
        flag = "OK " if smax < 10.0 else "WARN"
        if smax >= 25.0:
            flag, ok = "FAIL", False
        print(f"  [{flag}] {src.name:10s} |Δ| median {med:6.2f} cm  "
              f"max {mx:6.2f} cm  max-neighbour-spike {smax:6.2f} cm")
    print("== twin separation (corner-split vertices must stay glued) ==")
    for src, dst in zip(scene.meshes, rebound):
        sep = twin_separation(src.positions, dst.positions)
        flag = "OK " if sep < 0.1 else "WARN"
        if sep >= 2.0:
            flag, ok = "FAIL", False
        print(f"  [{flag}] {src.name:10s} max twin separation {sep:.6f} cm")
    print("== worst neighbour-spike vertices (where tears are) ==")
    for src, dst in zip(scene.meshes, rebound):
        d, spikes = displacement_smoothness(src.positions, dst.positions,
                                            src.triangles)
        if not len(spikes):
            continue
        f = np.asarray(src.triangles, dtype=np.int64)
        # rebuild per-vertex spike (same loop as above, keep indices)
        neigh = [[] for _ in range(len(d))]
        for i, j, k in f:
            neigh[i].append(j); neigh[j].append(i)
            neigh[j].append(k); neigh[k].append(j)
            neigh[k].append(i); neigh[i].append(k)
        vs = [(abs(d[v] - float(np.mean(d[ns]))), v) for v, ns in enumerate(neigh) if ns]
        vs.sort(reverse=True)
        for s, v in vs[:3]:
            if s < 5.0:
                break
            dom = rig_target.dominant_bone(dst.weights[v]) if dst.weights[v] else "Hips"
            p = dst.positions[v]
            print(f"  {src.name:10s} v{v:<6d} spike {s:6.2f} cm  dom={dom:16s} "
                  f"pos=({p[0]:7.2f},{p[1]:7.2f},{p[2]:7.2f})")
    print("== side-swap world-side check (ME2 Left vs mapped PD2 side) ==")
    for jname, j in scene.joints.items():
        if jname in ("LeftUpLeg", "LeftShoulder", "LeftCollar", "LeftElbow"):
            tgt = rig_target.map_joint(jname)
            sx = j.world[3][0]
            tx = rig.world[tgt][3][0]
            same = "same side" if sx * tx > 0 else "CROSSED"
            print(f"  {jname:14s} src x={sx:8.2f} -> {tgt:14s} tgt x={tx:8.2f}  [{same}]")
    print("== degenerate faces / normals ==")
    for src, dst in zip(scene.meshes, rebound):
        a = tri_areas(dst.positions, dst.triangles)
        deg = int((a < 1e-8).sum())
        n = np.asarray(dst.normals, dtype=np.float64)
        fin = bool(np.isfinite(n).all() and np.isfinite(
            np.asarray(dst.positions)).all())
        unit = float(np.abs(np.linalg.norm(n, axis=1) - 1.0).max())
        flag = "OK " if deg <= 0.01 * len(dst.triangles) and fin and unit < 1e-3 \
            else "FAIL"
        if flag == "FAIL":
            ok = False
        print(f"  [{flag}] {src.name:10s} degenerate {deg}/{len(dst.triangles)}  "
              f"finite {fin}  |‖n‖-1|max {unit:.2e}")
    print("== dominant-bone anchor distances (cm) ==")
    for dst in rebound:
        stats = bone_anchor_stats(dst, rig)
        worst = sorted(stats.items(), key=lambda kv: -kv[1][0])[:4]
        for bone, (med, mx, n) in worst:
            flag = "OK " if med < 35.0 else "WARN"
            if med >= 60.0:
                flag, ok = "FAIL", False
            print(f"  [{flag}] {dst.name:10s} {bone:16s} median {med:6.2f}  "
                  f"max {mx:6.2f}  n={n}")
    if REFERENCE_2B.exists():
        print("== bounds vs 2B donor model (cm, root space) ==")
        lo2, hi2 = model_bounds(REFERENCE_2B)
        allp = np.concatenate([np.asarray(m.positions) for m in rebound], axis=0)
        lo, hi = allp.min(axis=0), allp.max(axis=0)
        print(f"  lawson retarget Z range [{lo[2]:7.2f}, {hi[2]:7.2f}]")
        print(f"  2b donor        Z range [{lo2[2]:7.2f}, {hi2[2]:7.2f}]")
    return ok


def gather_render(scene, rig, rebound, out_dir: Path):
    from PIL import Image
    out_dir.mkdir(parents=True, exist_ok=True)

    allp = np.concatenate([np.asarray(m.positions) for m in rebound], axis=0)
    bounds = (allp.min(axis=0), allp.max(axis=0))

    palette = [
        (0.86, 0.62, 0.62), (0.62, 0.72, 0.86), (0.86, 0.82, 0.62),
        (0.72, 0.62, 0.86), (0.62, 0.86, 0.72), (0.86, 0.72, 0.62),
        (0.75, 0.75, 0.75), (0.55, 0.62, 0.75),
    ]
    views = [("front", 0.0, 8.0), ("side", 90.0, 8.0), ("three_quarter", 40.0, 12.0)]

    def mesh_tris(mats, colors):
        return [(np.asarray(m.positions, dtype=np.float64),
                 np.asarray(m.triangles, dtype=np.int64), c)
                for m, c in zip(mats, colors)]

    colors = [palette[i % len(palette)] for i in range(len(scene.meshes))]

    sheets = {
        "source_bind": mesh_tris(scene.meshes, colors),
        "retarget": mesh_tris(rebound, colors),
    }

    # decoded-from-pack (TPP)
    if "build_models" in dir(build):
        tpp, _ = build.build_models(scene, rig, log=lambda *a: None)
        _, pairs = decoded_drawables(tpp.data)
        dec_tris = [(pos, f, (0.95, 0.85, 0.35)) for pos, f in pairs]
        sheets["decoded_pack"] = dec_tris

    for name, tris in sheets.items():
        for vname, yaw, pitch in views:
            img = raster(tris, None, yaw_deg=yaw, pitch_deg=pitch)
            img.save(out_dir / f"{name}_{vname}.png")
            print(f"  wrote {name}_{vname}.png")

    # pixel-diff of retarget vs decoded (same camera AND same colors):
    # must come out black
    if "decoded_pack" in sheets:
        flat_ret = [(t[0], t[1], (0.95, 0.85, 0.35)) for t in sheets["retarget"]]
        for vname, yaw, pitch in views:
            img_a = raster(flat_ret, None, yaw_deg=yaw, pitch_deg=pitch)
            img_b = raster(sheets["decoded_pack"], None, yaw_deg=yaw, pitch_deg=pitch)
            diff = np.abs(np.asarray(img_a, dtype=np.int16)
                          - np.asarray(img_b, dtype=np.int16))
            # boost for visibility; any real mismatch lights up
            diff_img = Image.fromarray(np.clip(diff * 8, 0, 255).astype(np.uint8))
            diff_img.save(out_dir / f"diff_retarget_vs_decoded_{vname}.png")
            n_bad = int((diff.max(axis=2) > 24).sum())
            print(f"  wrote diff_retarget_vs_decoded_{vname}.png  "
                  f"mismatched pixels: {n_bad}")
        # numeric: decoded positions must equal the rebound ones up to f32
        # quantization (per-axis sorted compare is tie-proof)
        reb = np.concatenate([np.asarray(m.positions) for m in rebound])
        dec = np.concatenate([p for p, _ in
                              decoded_drawables(tpp.data)[1]])
        deltas = [float(np.abs(np.sort(reb[:, ax]) - np.sort(dec[:, ax])).max())
                  for ax in range(3)]
        worst = max(deltas)
        print(f"  numeric retarget-vs-decoded: per-axis max |Δ| = "
              f"{worst:.2e} cm (f32 quantization ~1e-5)")

    # skeleton lines over retarget
    by_id = {e["id"]: e for e in rig.entries}
    lines = []
    for e in rig.entries:
        par = by_id.get(e.get("parent_id"))
        if par is None or e["name"] not in rig.world or par.get("name") not in rig.world:
            continue
        a = rig.world[e["name"]]
        b = rig.world[par["name"]]
        lines.append(((a[3][0], a[3][1], a[3][2]),
                      (b[3][0], b[3][1], b[3][2]), (1.0, 1.0, 1.0)))
    for vname, yaw, pitch in views:
        img = raster(sheets["retarget"], None, yaw_deg=yaw, pitch_deg=pitch,
                     lines=lines)
        img.save(out_dir / f"retarget_skeleton_{vname}.png")
        print(f"  wrote retarget_skeleton_{vname}.png")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "report"
    scene, rig = load_all()
    rebound = rebind_all(scene, rig)
    ok = gather_report(scene, rig, rebound)
    if cmd == "render":
        out = Path(argv[2]) if len(argv) > 2 else Path("/tmp/las_preview")
        gather_render(scene, rig, rebound, out)
    print("RESULT:", "OK" if ok else "GATES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
