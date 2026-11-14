"""Limb-fit diagnostics: how well does a built pack's mesh sit on the skeleton?

A Diesel character is only as good as the distance between the mesh and the
bones that drive it. The failure the eye catches first is a limb tube that is
*parallel to* its bone but offset sideways: in the ``render_mesh_skeleton.py``
overlays the bone then runs along the edge of the sleeve instead of down the
middle, the elbow dot sits on the silhouette, and the cuff no longer surrounds
the ``Hand`` pivot where the in-game glove spawns.

Everything here is measured against the PD2 bind-pose skeleton the pack ships
with (``2b.model`` from ``references/2b.rar``), in the same units (cm) and the
same space as the built ``g_body`` geometry, so the numbers are directly
comparable between a pack and the vanilla-fitted 2B reference.

Two measurements per limb segment (``Arm``, ``ForeArm``, ``UpLeg``, ``Leg``):

``offset``
    Per axial slice (a slab of the tube), the median perpendicular distance
    from the slice centre to the bone axis, and the signed perpendicular
    offset vector. A tube that is centred on its bone has ``offset ~ 0``.
    Reported as ``rms`` (all slices), ``d_proximal``/``d_distal`` (first and
    last slice) plus the fitted **drift** - the slope of ``offset(t)`` - which
    is what makes the bone look like it is sliding off the limb toward the
    wrist or ankle.

``joint``
    Distance from a joint pivot (elbow / wrist / knee / ankle) to the centroid
    of the mesh's own crease, i.e. the vertices blended between the two bones
    that meet there. This is the "does it bend where the bone is" number:
    PD2 rotates about the pivot, not about the mesh's crease.

Used by ``build_models.segment_fit_report``.
"""
from __future__ import annotations

import numpy as np

#: limb segment bone -> the child joint it ends at (its own axis end)
SEGMENTS = {
    "LeftArm": "LeftForeArm",
    "LeftForeArm": "LeftHand",
    "RightArm": "RightForeArm",
    "RightForeArm": "RightHand",
    "LeftUpLeg": "LeftLeg",
    "LeftLeg": "LeftFoot",
    "RightUpLeg": "RightLeg",
    "RightLeg": "RightFoot",
}

#: joint pivot -> (parent segment bone, child segment bone or None)
JOINTS = {
    "LeftForeArm": ("LeftArm", "LeftForeArm"),
    "LeftHand": ("LeftForeArm", None),
    "RightForeArm": ("RightArm", "RightForeArm"),
    "RightHand": ("RightForeArm", None),
    "LeftLeg": ("LeftUpLeg", "LeftLeg"),
    "LeftFoot": ("LeftLeg", None),
    "RightLeg": ("RightUpLeg", "RightLeg"),
    "RightFoot": ("RightLeg", None),
}

#: slices are taken from the interior only: the ends of a segment are a blend
#: zone (weights halfway to the neighbouring bone), and their centroids do not
#: describe the limb at all.
INTERIOR = (0.12, 0.88)
#: radius mask as a multiple of the slice's median radius: keeps lace/hair/
#: holster-ish stray geometry from dragging the median around
RADIUS_FACTOR = 1.6
MIN_SLICE_VERTS = 8      # enough for the circle fit to mean something
#: a slab only counts if the verts ring the bone: near the shoulder the limb is
#: a broad deltoid mass with 6-10 verts per slab, and their median jumps around
#: by several cm from slab to slab - that is sampling noise, not an offset.
SECTORS = 6
MIN_SECTORS = 4


def limb_geom(template) -> dict[str, tuple]:
    """segment bone -> (a, u, L, child) from the template's bind-pose worlds."""
    geom: dict[str, tuple] = {}
    for bone, child in SEGMENTS.items():
        if bone not in template.name_id or child not in template.name_id:
            continue
        a = np.array(template.worlds[template.name_id[bone]][12:15], float)
        b = np.array(template.worlds[template.name_id[child]][12:15], float)
        d = b - a
        L = float(np.linalg.norm(d))
        if L < 1e-6:
            continue
        geom[bone] = (a, d / L, L, child)
    return geom


def joint_pos(template, name: str) -> np.ndarray:
    return np.array(template.worlds[template.name_id[name]][12:15], float)


def per_bone_weights(weights, palette) -> dict[str, np.ndarray]:
    """palette-name -> (n_verts,) array of that bone's total weight per vert."""
    out: dict[str, np.ndarray] = {}
    n = len(weights)
    for pi, name in enumerate(palette):
        col = np.zeros(n, float)
        for i, infl in enumerate(weights):
            for p, w in infl:
                if p == pi:
                    col[i] += w
        out[name] = col
    return out


def _kasa_circle(points2d):
    """Algebraic (Kasa) circle fit: returns (centre2d, radius, rms residual).

    A limb cross-section is a ring of verts, so its *centre* is what the bone
    should run through. A centroid or a median of the slab answers a different
    question - "where is the average vertex" - and answers it wrong whenever
    the verts are unevenly spaced around the ring, which is exactly what
    happens at lace seams and at the elbow crease. The circle fit is immune to
    that clustering, which is why this diagnostic can resolve ~0.3 cm on 2B and
    still show the Christie forearm's drift.
    """
    P = np.asarray(points2d, float)
    A = np.column_stack([P[:, 0], P[:, 1], np.ones(len(P))])
    rhs = -(P[:, 0] ** 2 + P[:, 1] ** 2)
    sol, *_ = np.linalg.lstsq(A, rhs, rcond=None)
    cx, cy = -sol[0] / 2.0, -sol[1] / 2.0
    r2 = cx * cx + cy * cy - sol[2]
    R = float(np.sqrt(max(r2, 1e-9)))
    resid = float(np.sqrt(np.mean(
        (np.linalg.norm(P - np.array([cx, cy]), axis=1) - R) ** 2)))
    return np.array([cx, cy]), R, resid


def slice_offsets(verts, w_bone: np.ndarray, geom_entry: tuple,
                  slices: int = 8, min_w: float = 0.5):
    """Per-slab centre of the ring of verts driven by one segment bone.

    Returns ``(t, offset, n, sectors)`` per usable slab: ``t`` is the axial
    coordinate of the slab mid-point, ``offset`` the perpendicular vector from
    the bone axis to the slab's fitted circle centre, ``sectors`` how many of
    ``SECTORS`` angular sectors the slab covers. Slabs with too few verts, or
    whose verts cover only part of the circumference, are skipped.
    """
    a, u, L, _child = geom_entry
    v = np.asarray(verts, float)
    rel = v - a
    t = rel @ u
    r = rel - np.outer(t, u)
    perp = np.linalg.norm(r, axis=1)
    inside = (w_bone >= min_w) & (t >= 0.0) & (t <= L)
    if inside.sum() < MIN_SLICE_VERTS:
        return []
    rad = float(np.median(perp[inside]))
    if rad <= 1e-6:
        return []
    inside &= perp <= RADIUS_FACTOR * rad
    tmp = np.array([1.0, 0.0, 0.0]) if abs(u[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(u, tmp)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    out = []
    t0, t1 = INTERIOR[0] * L, INTERIOR[1] * L
    step = (t1 - t0) / slices
    for k in range(slices):
        lo = t0 + k * step
        hi = t0 + (k + 1) * step
        m = inside & (t >= lo) & (t < hi)
        if m.sum() < MIN_SLICE_VERTS:
            continue
        r2 = r[m] @ np.stack([e1, e2], axis=1)      # exactly perpendicular
        ang = np.arctan2(r2[:, 1], r2[:, 0])
        sectors = len({int((a_ + np.pi) / (2 * np.pi) * SECTORS) % SECTORS
                       for a_ in ang})
        if sectors < MIN_SECTORS:
            continue
        c2, _radius, resid = _kasa_circle(r2)
        # a slab that does not look like a ring is not a cross-section
        if resid > 0.5 * max(_radius, 1e-6):
            continue
        out.append((float(t[m].mean()),
                    c2[0] * e1 + c2[1] * e2,
                    int(m.sum()), sectors))
    return out


def fit_offset_field(slices) -> dict:
    """Least-squares line offset(t) = c0 + c1*t through the slice offsets."""
    if len(slices) < 3:
        return {}
    ts = np.array([s[0] for s in slices])
    offs = np.array([s[1] for s in slices])
    wts = np.array([s[2] for s in slices], float)
    A = np.stack([np.ones_like(ts), ts], axis=1) * np.sqrt(wts)[:, None]
    coef, *_ = np.linalg.lstsq(A, offs * np.sqrt(wts)[:, None], rcond=None)
    resid = offs - (coef[0] + np.outer(ts, coef[1]))
    mag = np.linalg.norm(offs, axis=1)
    # plain floats: these land in the build report JSON
    return {
        "c0": [float(x) for x in coef[0]],   # offset at t=0 (proximal joint)
        "c1": [float(x) for x in coef[1]],   # drift along the segment
        "rms": float(np.sqrt((wts * (np.linalg.norm(resid, axis=1) ** 2)).sum()
                             / wts.sum())),
        "d_proximal": float(np.linalg.norm(coef[0])),
        "d_distal": float(np.linalg.norm(coef[0] + coef[1] * float(ts.max()))),
        "drift": float(np.linalg.norm(coef[1]) * float(ts.max() - ts.min())),
        "max": float(mag.max()),
    }


def crease_centroid(verts, bone_w: dict[str, np.ndarray], parent: str, child: str,
                    lo: float = 0.25):
    """Centroid of the verts blended between the two bones meeting at a joint."""
    wa = bone_w.get(parent)
    wb = bone_w.get(child)
    if wa is None or wb is None:
        return None
    m = (wa > lo) & (wb > lo)
    if m.sum() < 4:
        return None
    return np.asarray(verts, float)[m].mean(axis=0)


def measure(verts, weights, palette, template) -> dict:
    """Full diagnostic for one drawable, in the template's (PD2) space.

    Returns ``{"segments": {bone: report}, "joints": {joint: cm}}`` plus the
    aggregate scalars the tests assert on:
    ``worst_segment_offset`` (max slice offset), ``worst_joint`` (max crease to
    pivot distance) and ``worst_drift``.
    """
    bone_w = per_bone_weights(weights, palette)
    geom = limb_geom(template)
    seg: dict[str, dict] = {}
    for bone, entry in geom.items():
        w = bone_w.get(bone)
        if w is None or w.max() <= 0.0:
            continue
        slices = slice_offsets(verts, w, entry)
        if not slices:
            continue
        rep = fit_offset_field(slices)
        if rep:
            rep["slices"] = len(slices)
            rep["L"] = entry[2]
            rep["min_sectors"] = min(s[3] for s in slices)
            seg[bone] = rep
    joints: dict[str, float] = {}
    for joint, (parent, child) in JOINTS.items():
        if joint not in template.name_id:
            continue
        if child is None:
            continue        # terminal joint: nothing to cross-check the cuff against
        c = crease_centroid(verts, bone_w, parent, child)
        if c is None:
            continue
        joints[joint] = float(np.linalg.norm(c - joint_pos(template, joint)))
    return {
        "segments": seg,
        "joints": joints,
        "worst_segment_offset": max((r["max"] for r in seg.values()), default=0.0),
        "worst_drift": max((r["drift"] for r in seg.values()), default=0.0),
        "worst_joint": max(joints.values(), default=0.0),
    }


def cuff_distance(verts, weights, palette, template, bone: str = "LeftHand",
                  lo: float = 0.5) -> float | None:
    """Distance from a wrist/ankle pivot to the mesh's surviving end ring.

    For the no-hands packs the sleeve opening must *surround* the ``Hand``
    pivot, because that is where the in-game glove spawns.
    """
    if bone not in template.name_id:
        return None
    parent = bone.replace("Hand", "ForeArm").replace("Foot", "Leg")
    bone_w = per_bone_weights(weights, palette)
    geom = limb_geom(template)
    entry = geom.get(parent)
    if entry is None:
        return None
    a, u, L, child = entry
    if child != bone:
        return None
    w = bone_w.get(parent)
    if w is None:
        return None
    v = np.asarray(verts, float)
    t = (v - a) @ u
    m = (w >= lo) & (t >= L - 3.0)
    if m.sum() < 4:
        return None
    return float(np.linalg.norm(v[m].mean(axis=0) - joint_pos(template, bone)))


def format_report(tag: str, rep: dict, cuffs: dict | None = None) -> str:
    """Human-readable table; also what the builder prints at build time."""
    lines = [f"[{tag}] mesh-vs-skeleton fit (cm, PD2 bind space)"]
    lines.append(f"  {'segment':12s} {'slice max':>9s} {'rms':>6s} "
                 f"{'prox':>6s} {'dist':>6s} {'drift':>6s}")
    for bone in sorted(rep["segments"]):
        r = rep["segments"][bone]
        lines.append(f"  {bone:12s} {r['max']:9.2f} {r['rms']:6.2f} "
                     f"{r['d_proximal']:6.2f} {r['d_distal']:6.2f} {r['drift']:6.2f}")
    if rep["joints"]:
        lines.append("  joint crease -> pivot: " + ", ".join(
            f"{j} {d:.2f}" for j, d in sorted(rep["joints"].items())))
    if cuffs:
        lines.append("  cuff ring -> wrist/ankle pivot: " + ", ".join(
            f"{k} {d:.2f}" for k, d in sorted(cuffs.items()) if d is not None))
    return "\n".join(lines)
