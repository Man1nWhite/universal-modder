"""Deep-diagnose the Christie LAS packs from the shipped `.model` alone.

The screenshot audits describe *symptoms* (a notch, a sliver, a band). This
script answers the structural questions behind them, on either pack:

- how many shells the mesh is made of, and which of its borders are free
  garment edges instead of accidental holes;
- whether a coincident-vertex pair is a zero-width (unstitched) seam, a
  material interface, or an interior duplicate;
- where the silhouette is actually see-through (the armpit notch);
- how far the sleeve, cuff band and skin stub reach past the `Hand` pivot;
- how much of the trouser/shoe UV area the sleeve gloss mask touches;
- whether each sleeve is a *closed* tube, or still open along its lengthwise
  seam (needs the arm bone chain, hence `--templates`).

    .venv/bin/python tools/pd2-las/diagnose_mesh.py            # both packs
    .venv/bin/python tools/pd2-las/diagnose_mesh.py --pack slim
    .venv/bin/python tools/pd2-las/diagnose_mesh.py \
        --templates "build/pd2-las/2b/2B - LAS/assets/units/2b/skins/2b"   # + slit

Everything is read-only. Numbers quoted in
`docs/audits/2026-11-07-christie-slim-diagnosis.md` come from this script.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import build_models as bm  # noqa: E402
import diesel_model as dm  # noqa: E402
import render_mesh_skeleton as rms  # noqa: E402

PACKS = {
    "base": (REPO / "dist" / "Christie_LAS.zip", "Christie_LAS", "christie", -1.0),
    "slim": (REPO / "dist" / "Christie_LAS_Slim.zip", "Christie_LAS_Slim",
             "christie_slim", -1.0),
}
ROLE = ["mtr_body", "mtr_c02_01", "mtr_c02_02", "mtr_c02_05"]


# --------------------------------------------------------------------- load
def load(zpath: Path, pack: str, item: str) -> dict:
    with zipfile.ZipFile(zpath) as zf:
        name = [n for n in zf.namelist()
                if n.endswith(f"/{item}.model") and "/fps_" not in n][0]
        mf = dm.ModelFile.read(zf.read(name))
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    obj_name = {}
    for s in mf.by_type(dm.OBJECT3D):
        o = dm.decode_object3d(s.payload)
        obj_name[s.id] = next((n for n in hl if dm.hash64(n) == o["name_hash"]), "")
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        name = next((n for n in hl if dm.hash64(n) == md["name_hash"]), "")
        if name != "g_body" or md.get("version") != 3:
            continue
        gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
        geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
        topo = dm.decode_topology(mf.by_id(gp["topology"]).payload)
        skel = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
        faces = np.asarray(topo["indices"], int).reshape(-1, 3)
        # atoms list triangles in material order; material_id indexes the
        # model's material group (mtr_body, c02_01, c02_02, c02_05).
        fmat = np.concatenate([[ROLE[a["material_id"]]] * a["tri_count"]
                               for a in md["atoms"]])
        assert len(fmat) == len(faces)
        verts = np.asarray(geo["verts"], float)
        weights = np.asarray(geo["blendweights"], float)
        binds = np.asarray(geo["blendindices"], int)
        palette = [obj_name.get(i, "") for i in skel["objects"]]
        w = {}
        for key, pred in (("arm", lambda n: n.endswith("Arm") or n.endswith("ForeArm")
                           or n.endswith("Hand") or "Finger" in n),
                          ("leg", lambda n: n.endswith("UpLeg") or n.endswith("Leg")
                           or n.endswith("Foot")),
                          ("hand", lambda n: "Hand" in n or "Finger" in n)):
            acc = np.zeros(len(verts))
            for i in range(len(verts)):
                for pi, wi in zip(binds[i], weights[i]):
                    if wi > 0 and pi < len(palette) and pred(palette[pi]):
                        acc[i] += wi
            w[key] = acc
        return dict(verts=verts, faces=faces, fmat=fmat, uv=np.asarray(geo["uv0"], float),
                    normals=np.asarray(geo["normals"], float), w=w)
    raise SystemExit(f"no g_body in {zpath}")


def joints_of(zpath: Path, item: str, template) -> dict:
    """Rest positions of the arm bones, from the pack's own skinbones."""
    with zipfile.ZipFile(zpath) as zf:
        name = [n for n in zf.namelist()
                if n.endswith(f"/{item}.model") and "/fps_" not in n][0]
        mf = dm.ModelFile.read(zf.read(name))
    hl = dm.decode_custom_hashlist(mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
    for s in mf.by_type(dm.MODEL_DATA):
        md = dm.decode_model_data(s.payload)
        if next((n for n in hl if dm.hash64(n) == md["name_hash"]), "") == "g_body":
            skel = dm.decode_skinbones(mf.by_id(md["skinbones"]).payload)
            return {n: np.asarray(pt, float)
                    for n, pt, _ in rms.rest_skeleton(template, skel)}
    raise SystemExit(f"no g_body in {zpath}")


# ------------------------------------------------------------------ helpers
def shells(faces: np.ndarray, n: int):
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in faces:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(int(u)), find(int(v))
            if ru != rv:
                parent[rv] = ru
    roots = np.array([find(i) for i in range(n)])
    _, inv = np.unique(roots, return_inverse=True)
    return inv


def boundary(faces: np.ndarray):
    ef = defaultdict(int)
    for a, b, c in faces:
        for u, v in ((a, b), (b, c), (c, a)):
            ef[(min(u, v), max(u, v))] += 1
    edges = [e for e, c in ef.items() if c == 1]
    verts = set()
    for a, b in edges:
        verts.add(int(a)); verts.add(int(b))
    return edges, verts


def loops_of(edges, verts):
    adj = defaultdict(list)
    for a, b in edges:
        if a in verts and b in verts:
            adj[a].append(b); adj[b].append(a)
    seen, out = set(), []
    for s in adj:
        if s in seen:
            continue
        stack, comp = [s], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x); stack.extend(adj[x])
        out.append(comp)
    return out


def _hits_any(o, d, tri, front_faces_only: bool = False) -> bool:
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    pv = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, pv)
    if front_faces_only:
        ok = det > 1e-9          # front face only (D3D9 culls backfaces)
    else:
        ok = np.abs(det) > 1e-9  # either face
    inv = np.zeros_like(det); inv[ok] = 1.0 / det[ok]
    tv = o - v0
    u = np.einsum("ij,ij->i", tv, pv) * inv
    qv = np.cross(tv, e1)
    w = (qv @ d) * inv
    t = np.einsum("ij,ij->i", e2, qv) * inv
    return bool((ok & (u >= 0) & (u <= 1) & (w >= 0) & (u + w <= 1) & (t > 0)).any())


def sleeve_slit_area(p: dict, joints: dict, side: int, step_deg: float = 6.0,
                     slice_cm: float = 0.5, lo: float = 0.10, hi: float = 0.90,
                     cull_backfaces: bool = False) -> dict:
    """Radial-dodging area of one sleeve: the hole a zero-width slit makes.

    The sleeve is a tube: a ray cast radially from its bone axis must hit the
    garment surface in every direction. A slit is not a *gap in the surface*
    but an unclosed tube, so the rays that slip through it hit nothing at all.
    Only the tube's middle band is sampled (10 %..90 % of the shoulder->wrist
    bone chain) so the open cuff mouth and the shoulder rim - both legitimate
    garment openings - contribute nothing.

    `joints` maps bone names to rest positions (`{name: (x, y, z)}`, see
    :func:`diagnose`); `side` is -1 for the left (negative x) arm, +1 right.
    With ``cull_backfaces=True``, rays are cast inward from outside the sleeve
    and only front-face hits count, matching D3D9 backface culling so
    inside-out caps and reversed bridge triangles are caught as leaks.
    Returns ``{"cm2": float, "slices": [(s, z, cm2), ...]}``.
    """
    v, f, fmat = p["verts"], p["faces"], p["fmat"]
    sgn = v[:, 0] * side
    sleeve = f[np.isin(fmat, ("mtr_c02_01",))]
    tri = v[sleeve[(sgn[sleeve] > 0).all(1)]]
    sfx = "Left" if side < 0 else "Right"
    a0s = [joints[sfx + "Arm"], joints[sfx + "ForeArm"], joints[sfx + "Hand"]]
    segs = [(a0s[0], a0s[1]), (a0s[1], a0s[2])]
    span = sum(float(np.linalg.norm(b - a)) for a, b in segs)
    total, worst, s0 = 0.0, [], 0.0
    for a, b in segs:
        axis = b - a
        seg = float(np.linalg.norm(axis))
        u = axis / seg
        e1 = np.cross(u, [1.0, 0.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(u, e1)
        n = max(2, int(seg / slice_cm))
        for k in range(n):
            frac = (s0 + seg * (k + 0.5) / n) / span
            if not lo <= frac <= hi:
                continue
            o = a + u * (seg * (k + 0.5) / n)
            rel = tri.reshape(-1, 3) - o
            r = float(np.median(np.linalg.norm(rel - np.outer(rel @ u, u), axis=1)))
            if cull_backfaces:
                # Cast inward from outside; only front-face hits count, so an
                # inside-out cap or reversed bridge triangle reads as a leak.
                miss = sum(
                    0 if _hits_any(
                        o + 15.0 * ray_dir, -ray_dir, tri,
                        front_faces_only=True) else 1
                    for dg in np.arange(0.0, 360.0, step_deg)
                    for ray_dir in [np.cos(np.radians(dg)) * e1
                                    + np.sin(np.radians(dg)) * e2])
            else:
                miss = sum(0 if _hits_any(o, np.cos(np.radians(dg)) * e1
                                          + np.sin(np.radians(dg)) * e2, tri)
                           else 1
                           for dg in np.arange(0.0, 360.0, step_deg))
            if miss:
                a2 = miss / (360.0 / step_deg) * 2 * np.pi * r * (seg / n)
                total += a2
                if a2 > 0.05:
                    worst.append((round(float(frac), 2), round(float(o[2]), 1),
                                  round(a2, 2)))
        s0 += seg
    return {"cm2": total, "slices": worst}


def cast_front(verts, faces, xs, zs, y0=60.0):
    """True where a ray from +y hits any triangle (front-parallel)."""
    d = np.array([0.0, -1.0, 0.0])
    tri = verts[faces]
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    hit = np.zeros((len(zs), len(xs)), bool)
    for iz, z in enumerate(zs):
        for ix, x in enumerate(xs):
            o = np.array([x, y0, z])
            pv = np.cross(np.broadcast_to(d, e2.shape), e2)
            det = np.einsum("ij,ij->i", e1, pv)
            ok = np.abs(det) > 1e-9
            inv = np.zeros_like(det); inv[ok] = 1.0 / det[ok]
            tv = o - v0
            u = np.einsum("ij,ij->i", tv, pv) * inv
            qv = np.cross(tv, e1)
            w = (qv @ d) * inv
            t = np.einsum("ij,ij->i", e2, qv) * inv
            hit[iz, ix] = (ok & (u >= 0) & (u <= 1) & (w >= 0)
                           & (u + w <= 1) & (t > 0)).any()
    return hit


# ------------------------------------------------------------------- report
def diagnose(label: str, path: Path, pack: str, item: str,
             joints: dict | None = None) -> None:
    p = load(path, pack, item)
    v, f, fmat = p["verts"], p["faces"], p["fmat"]
    n = p["normals"] / np.linalg.norm(p["normals"], axis=1, keepdims=True)
    print(f"\n=== {label}: {len(v)} verts, {len(f)} tris")

    inv = shells(f, len(v))
    sizes = Counter(inv[f[:, 0]].tolist())
    edges, bverts = boundary(f)
    loops = loops_of(edges, bverts)
    print(f"shells {len(sizes)}  boundary edges {len(edges)} "
          f"({len(edges) / (len(f) * 1.5) * 100:.0f}% of edges)  boundary loops {len(loops)}")
    print("  loop sizes:", sorted((len(c) for c in loops), reverse=True)[:8])

    # coincident-vertex classification
    vmat = defaultdict(set)
    for fi in range(len(f)):
        for x in f[fi]:
            vmat[int(x)].add(fmat[fi])
    groups = defaultdict(list)
    for i, pt in enumerate(v):
        groups[tuple(pt)].append(i)
    cls = Counter()
    for grp in groups.values():
        if len(grp) < 2:
            continue
        for a in range(len(grp)):
            for b in range(a + 1, len(grp)):
                i, j = grp[a], grp[b]
                ang = np.degrees(np.arccos(np.clip(n[i] @ n[j], -1, 1)))
                if ang <= 30:
                    continue
                kind = ("same-mat" if vmat[i] == vmat[j] else "cross-mat")
                kind += "/same-uv" if np.allclose(p["uv"][i], p["uv"][j], atol=1e-5) else "/diff-uv"
                where = "border" if (i in bverts or j in bverts) else "interior"
                cls[(kind, where)] += 1
    total = sum(cls.values())
    print(f"divergent (>30 deg) coincident pairs: {total}")
    for (kind, where), c in sorted(cls.items()):
        print(f"   {kind:22s} {where:9s} {c:4d}")

    # armpit see-through wedge (left armpit)
    xs = np.arange(-34, -4.5, 0.5); zs = np.arange(126, 156, 0.5)
    hit = cast_front(v, f, xs, zs)
    miss = ~hit
    # a "wedge" cell is background with hits on both sides within 6 cm
    wedge = []
    for iz, z in enumerate(zs):
        for ix, x in enumerate(xs):
            if not miss[iz, ix]:
                continue
            left = hit[iz, max(0, ix - 12):ix].any()
            right = hit[iz, ix + 1:ix + 13].any()
            if left and right:
                wedge.append((x, z))
    if wedge:
        w = np.array(wedge)
        print(f"armpit: see-through wedge {len(wedge)} cells "
              f"({len(wedge) * 0.25:.1f} cm2); apex z {w[:, 1].max():.1f} cm at x "
              f"{w[w[:, 1].argmax(), 0]:.1f}; width at z=134 "
              f"{(w[(w[:, 1] > 133.5) & (w[:, 1] < 134.5)][:, 0].size * 0.5):.1f} cm")

    # distal extent of the wrist shells past the Hand pivot
    hand = np.array([-44.5, -0.1, 107.9]); elbow = np.array([-33.1, -1.0, 127.3])
    u = (hand - elbow) / np.linalg.norm(hand - elbow)
    for k, cnt in sizes.most_common(12):
        vs = np.unique(f[inv[f[:, 0]] == k])
        c = v[vs].mean(0)
        if not (c[0] < -34 and 95 < c[2] < 125):
            continue
        t = (v[vs] - hand) @ u
        mats = Counter(fmat[inv[f[:, 0]] == k]).most_common(1)[0][0]
        print(f"  wrist shell {k:2d} {mats:11s} verts {len(vs):4d} "
              f"t_past_hand max {t.max():5.1f} cm")

    # sleeve gloss mask: the mask the build actually ships. It is rasterised
    # from the sleeve's own UV triangles (build_christie_las.sleeve_uv_mask),
    # so a leg face can only be inside it if the sleeve and the trouser islands
    # overlap in the atlas.
    import build_christie_las as bcl

    role = "mtr_c02_01"
    sleeve_faces = [fi for fi in np.where(fmat == role)[0]
                    if float(p["w"]["arm"][f[fi]].mean()) > bcl.SLEEVE_BONE_SHARE]
    mask = bcl.sleeve_uv_mask(p["uv"], [f[fi] for fi in sleeve_faces],
                              feather_texels=bcl.SLEEVE_FEATHER_TEXELS)

    def uva(fi):
        t = p["uv"][f[fi]]
        return 0.5 * abs((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1])
                         - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1]))

    def mval(fi):
        c = bcl.uv_to_texel_frac(p["uv"][f[fi]].mean(0))
        y = int(np.clip(c[1] * 1024, 0, 1023))
        x = int(np.clip(c[0] * 1024, 0, 1023))
        return mask[y, x]

    leg = [fi for fi in np.where(fmat == role)[0]
           if p["w"]["leg"][f[fi]].mean() > 0.5 and p["w"]["arm"][f[fi]].mean() < 0.1]
    leg_z = [float(p["verts"][f[fi], 2].mean()) for fi in leg]
    tot = sum(uva(fi) for fi in leg)
    cov = sum(uva(fi) for fi in leg if mval(fi) > 0.05)
    leg_hits = [fi for fi in leg if mval(fi) > 0.05]
    trouser_hits = [fi for fi in leg_hits
                    if 20.0 < leg_z[leg.index(fi)] < 60.0]
    sleeve_pct = (sum(1 for fi in sleeve_faces if mval(fi) > 0.5)
                  / max(1, len(sleeve_faces)) * 100)
    max_hit_z = max([leg_z[leg.index(fi)] for fi in leg_hits] or [0.0])
    print(f"sleeve gloss mask: sleeve faces covered {sleeve_pct:.0f}%; "
          f"{role} leg-only UV area {cov / max(tot, 1e-9) * 100:.2f}% "
          f"({len(leg_hits)} of {len(leg)} faces, max z {max_hit_z:.1f} cm); "
          f"trouser band z in [20, 60) hits: {len(trouser_hits)}")

    # sleeve slit: the radial-dodging area of each sleeve tube. The stitch pass
    # is supposed to have closed the zero-width seam, so only the open cuff
    # mouth (excluded by the 8-88 % window) may still leak.
    if joints is None:
        print("sleeve slit: skipped (pass --templates to measure the seam)")
    else:
        for side, name in ((-1, "left"), (1, "right")):
            s = sleeve_slit_area(p, joints, side)
            print(f"sleeve slit {name:5s}: {s['cm2']:5.2f} cm2 open through the "
                  f"tube's mid-band over {len(s['slices'])} leaky slice(s)"
                  + (f", worst {s['slices'][:3]}" if s["slices"] else ""))

    print(f"hand-weighted verts > 0.5: {int((p['w']['hand'] > 0.5).sum())}, "
          f"> 0.0: {int((p['w']['hand'] > 0.0).sum())}, "
          f"max {p['w']['hand'].max():.2f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", choices=sorted(PACKS), action="append")
    ap.add_argument("--templates", type=Path, default=None,
                    help="2B template dir (with 2b.model); enables the sleeve "
                         "slit measurement, which needs the arm bone chain")
    args = ap.parse_args(argv)
    template = None
    if args.templates is not None and (args.templates / "2b.model").is_file():
        template = bm.load_template(args.templates / "2b.model")
    for label in (args.pack or sorted(PACKS)):
        path, pack, item, _ = PACKS[label]
        if not path.is_file():
            print(f"{label}: missing {path}")
            continue
        joints = joints_of(path, item, template) if template is not None else None
        diagnose(label, path, pack, item, joints)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
