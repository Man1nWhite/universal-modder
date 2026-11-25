#!/usr/bin/env python3
"""Helpers shared by the Diesel LAS builders (`build_honoko2_dae.py`, `christie_fit_probe.py`).

These are the frame and mesh post-process helpers extracted when the TMC-only
Honoka LAS pack and its driver were deleted on 2026-11-15
(`docs/pd2-las/DECISIONS.md`, D40). `build_honoko2_dae.py` uses the TMC frame,
world-bind, wrist-cut, sliver-drop, and fallback-icon helpers; `christie_fit_probe.py`
and `build_christie_source.py` reuse the wrist-cut helper for Christie's heister-glove seam.

* :func:`basis_matrix` / :func:`glbl_to_diesel` — the TMC frame (Y-up, cm) to the
  Diesel frame (Z-up, cm), det = +1, and the 171 world bind matrices with it.
* :func:`cut_group_at_planes` — drop everything distal to a set of planes, slice
  by slice; :func:`cut_group_at_wrists` (the hands at the wrist joint, along the
  forearm axis) and :func:`cut_group_at_palm_bases` (the palms where they begin,
  perpendicular to the palm) are the two named ways into it.
* :func:`clip_group_at_planes` — the same cut made *on* the plane, splitting the
  triangles that straddle it, with :func:`clip_group_at_palm_bases` as its named
  caller: a whole-triangle drop stops up to a band short of the plane, which
  leaves 2.2 cm of wrist above a palm cut.
* :func:`drop_long_thin_triangles` — drop the source's strip-break connector slivers.
* :func:`fallback_icon` — the placeholder HUD tile for a build with `--no-previews`.

Nothing here reads a file or picks a material; the caller owns everything else.
"""

from __future__ import annotations

#: Source strip-break/connector triangles span the whole model (one edge past 23 cm,
#: up to 146 cm in the retargeted cm frame). The longest legitimate edge in the
#: outfit measures 13.4 cm, so 20.0 sits in the gap; these draw as hairline streaks
#: from the wrist to the feet.
LONG_THIN_MAX_EDGE_CM = 20.0


#: A right-handed map from the TMC's Y-up centimetre frame to Diesel's Z-up frame.
#: p_d = M p_s with det(M) = +1; the retarget fits absorb the yaw.
_M = ((1.0, 0.0, 0.0),
      (0.0, 0.0, -1.0),
      (0.0, 1.0, 0.0))


def basis_matrix():
    import numpy as np

    M = np.array(_M, dtype=np.float64)
    assert abs(float(np.linalg.det(M)) - 1.0) < 1e-12
    return M


def glbl_to_diesel(glbl_raw) -> list:
    """TMC GlblMtx (metres, Y-up) -> diesel world bind (row-vector dm.Mat, cm)."""
    import numpy as np

    M = basis_matrix()
    out = []
    for raw in glbl_raw:
        W = np.array(raw, dtype=np.float64).reshape(4, 4, order="F")  # column-convention 4x4
        R = W[:3, :3]
        t = W[:3, 3]
        R2 = M @ R @ M.T
        t2 = 100.0 * (M @ t)
        Wd = np.eye(4)
        Wd[:3, :3] = R2
        Wd[:3, 3] = t2
        out.append(tuple(float(x) for x in Wd.T.reshape(16)))
    return out


def drop_long_thin_triangles(g, max_edge: float = LONG_THIN_MAX_EDGE_CM) -> dict:
    """Drop triangles with any edge longer than ``max_edge`` cm.

    The TMC reader emits triangle fans for the source's strip-break connector
    quads; each quad becomes a pair of slivers that join two unrelated parts of
    the outfit (wrist to feet, neck to ankle). They render as hairline streaks
    crossing the silhouette. They are not salvageable by repair: the two
    triangles share a ~0.2 cm root edge but their apex is hundreds of cm away
    in the neighbouring body region, and no UV or weight data makes them
    meaningful. Dropping them loses nothing measurable: the affected pixels
    were background.

    Same slice-walk as :func:`cut_group_at_wrists`: keeps each slice's own
    compact vertex block (the Diesel atom invariant) and rebuilds slices.
    """
    import numpy as np

    verts = np.asarray(g.verts, dtype=np.float64)
    faces = np.asarray(g.faces, dtype=np.int64)
    e0 = np.linalg.norm(verts[faces[:, 1]] - verts[faces[:, 0]], axis=1)
    e1 = np.linalg.norm(verts[faces[:, 2]] - verts[faces[:, 1]], axis=1)
    e2 = np.linalg.norm(verts[faces[:, 0]] - verts[faces[:, 2]], axis=1)
    emax = np.maximum(np.maximum(e0, e1), e2)
    drop = emax > max_edge

    new_verts, new_normals, new_uvs, new_weights, new_faces, new_slices = [], [], [], [], [], []
    report_per_slice = []
    vbase = fbase = cursor = 0
    for (src_mat, base_v, base_i, tri_count, nverts) in g.slices:
        sl_drop = drop[cursor:cursor + tri_count]
        sl_faces = faces[cursor:cursor + tri_count]
        cursor += tri_count
        old_lo, old_hi = base_v, base_v + nverts
        keep_mask = ~sl_drop
        kept = sl_faces[keep_mask]
        remap = {}
        for f in kept:
            for vi in f:
                assert old_lo <= vi < old_hi
                if int(vi) not in remap:
                    remap[int(vi)] = len(remap)
        for old_vi in sorted(remap, key=remap.get):
            new_verts.append(g.verts[old_vi])
            new_normals.append(g.normals[old_vi])
            new_uvs.append(g.uvs[old_vi])
            new_weights.append(g.weights[old_vi])
        for f in kept:
            new_faces.append(tuple(remap[int(vi)] + vbase for vi in f))
        report_per_slice.append({
            "src_mat": src_mat,
            "tris_before": tri_count,
            "tris_after": int(keep_mask.sum()),
            "tris_dropped": int(sl_drop.sum()),
        })
        new_slices.append((src_mat, vbase, fbase * 3, len(kept), len(remap)))
        vbase += len(remap)
        fbase += len(kept)
    g.verts = new_verts
    g.normals = new_normals
    g.uvs = new_uvs
    g.weights = new_weights
    g.faces = new_faces
    g.slices = new_slices
    return {"slices": report_per_slice,
            "tris_dropped": sum(s["tris_dropped"] for s in report_per_slice),
            "verts_after": vbase}


def _unit(vector):
    import numpy as np

    v = np.asarray(vector, dtype=np.float64)
    return v / np.linalg.norm(v)


def cut_group_at_planes(g, planes, margin: float = 0.5, r_max: float = 28.0) -> dict:
    """Drop every triangle with a vertex distal to any of the given planes.

    ``planes`` is a sequence of ``(origin, axis)`` pairs: a point on the plane
    and a unit axis pointing distally, away from the body. A vertex is distal
    when it lies further than ``margin`` cm along that axis from the origin
    **and** within ``r_max`` cm of the axis line. The radius limit is not
    optional: in the PD2 bind pose the arm axes point steeply down-forward, so a
    bare half-space would also swallow the lower legs.

    The drop is done slice by slice: each slice keeps its own compact vertex
    block (the Diesel atom invariant requires the slice's triangles to index
    inside its own block), unused vertices are dropped, and the slices'
    ``base_v``/``base_i`` are rebuilt.

    The report carries ``removed_vertex_ids`` - the old indices of vertices that
    only distal triangles used - so a caller can say which bones it removed.
    """
    import numpy as np

    verts = np.asarray(g.verts, dtype=np.float64)
    distal = np.zeros(len(verts), dtype=bool)
    for origin, axis in planes:
        origin = np.asarray(origin, dtype=np.float64)
        axis = np.asarray(axis, dtype=np.float64)
        rel = verts - origin
        axial = rel @ axis
        perp = np.linalg.norm(rel - np.outer(axial, axis), axis=1)
        distal |= (axial > margin) & (perp < r_max)

    # slice layout of the incoming faces: transfer_group extends faces slice by
    # slice, in model.meshes order; recover each slice's kept face list from it
    faces = np.asarray(g.faces, dtype=np.int64)
    new_verts = []
    new_normals = []
    new_uvs = []
    new_weights = []
    new_faces = []
    new_slices = []
    report_per_slice = []
    vbase = 0
    fbase = 0
    # faces of the old group are laid out in slice order; walk them with a
    # cursor and match each slice to its (old) vertex block
    cursor = 0
    removed: set[int] = set()
    for (src_mat, base_v, base_i, tri_count, nverts) in g.slices:
        sl_faces = faces[cursor:cursor + tri_count]
        cursor += tri_count
        old_lo, old_hi = base_v, base_v + nverts
        keep_mask = ~distal[sl_faces].any(axis=1)
        kept = sl_faces[keep_mask]
        remap = {}
        for f in kept:
            for vi in f:
                assert old_lo <= vi < old_hi
                if int(vi) not in remap:
                    remap[int(vi)] = len(remap)
        for old_vi in sorted(remap, key=remap.get):
            new_verts.append(g.verts[old_vi])
            new_normals.append(g.normals[old_vi])
            new_uvs.append(g.uvs[old_vi])
            new_weights.append(g.weights[old_vi])
        for f in kept:
            new_faces.append(tuple(remap[int(vi)] + vbase for vi in f))
        report_per_slice.append({
            "src_mat": src_mat,
            "verts_before": nverts,
            "tris_before": tri_count,
            "verts_after": len(remap),
            "tris_after": int(keep_mask.sum()),
            "tris_dropped": int((~keep_mask).sum()),
        })
        new_slices.append((src_mat, vbase, fbase * 3, len(kept), len(remap)))
        vbase += len(remap)
        fbase += len(kept)
        removed.update(int(vi) for vi in np.unique(sl_faces[~keep_mask]) if int(vi) not in remap)
    g.verts = new_verts
    g.normals = new_normals
    g.uvs = new_uvs
    g.weights = new_weights
    g.faces = new_faces
    g.slices = new_slices
    return {"slices": report_per_slice,
            "tris_dropped": sum(s["tris_dropped"] for s in report_per_slice),
            "verts_after": vbase,
            "removed_vertex_ids": sorted(removed)}


def _plane_distances(verts, planes, margin: float):
    """Per plane: the axial distance (cm, positive distal) and the perpendicular one.

    The distance is measured to the plane itself; ``perp`` is what decides whether a
    vertex is inside that plane's radius limit at all, because a bare half-space would
    also take the legs off (see :func:`cut_group_at_planes`).
    """
    import numpy as np

    out = []
    for origin, axis in planes:
        origin = np.asarray(origin, dtype=np.float64)
        axis = np.asarray(axis, dtype=np.float64)
        rel = verts - origin
        axial = rel @ axis
        perp = np.linalg.norm(rel - np.outer(axial, axis), axis=1)
        out.append((axial - margin, perp))
    return out


def clip_group_at_planes(g, planes, margin: float = 0.0, r_max: float = 28.0) -> dict:
    """Cut the mesh *on* the planes, splitting the triangles that straddle them.

    :func:`cut_group_at_planes` drops a triangle whole as soon as one of its vertices
    is distal, so the surface it leaves stops up to one triangle band short of the
    plane - on the OfficeSuite forearm that is 2.2 cm of wrist left behind. This is
    the same cut made exactly on the plane: a straddling triangle is split where its
    edges cross, the distal part is dropped, and the crossing points carry
    interpolated normal, UV and skin weights. Nothing is added to the surface, and
    nothing survives distal to the plane.

    Crossing points are shared between the two triangles either side of an edge (the
    edge, not the triangle, is the cache key), so the rim stays a watertight boundary
    loop and :func:`_cap_cut_rims`-style capping still sees it. Each slice keeps its
    own compact vertex block; the report has the same keys as
    :func:`cut_group_at_planes`, plus ``tris_split`` and ``verts_added``.
    """
    import numpy as np

    verts = np.asarray(g.verts, dtype=np.float64)
    planes = [(np.asarray(o, dtype=np.float64), np.asarray(a, dtype=np.float64))
              for o, a in planes]
    per_plane = _plane_distances(verts, planes, margin)
    # > 0 distal (goes), <= 0 proximal (stays); vertices outside every radius limit
    # are proximal by construction.
    dist = np.full(len(verts), -1e30)
    for axial, perp in per_plane:
        dist = np.maximum(dist, np.where(perp < r_max, axial, -1e30))

    faces = np.asarray(g.faces, dtype=np.int64)
    new_verts, new_normals, new_uvs, new_weights, new_faces, new_slices = [], [], [], [], [], []
    report_per_slice = []
    removed: set[int] = set()
    vbase = fbase = cursor = 0
    split_total = 0
    originals = 0
    for (src_mat, base_v, base_i, tri_count, nverts) in g.slices:
        sl_faces = faces[cursor:cursor + tri_count]
        cursor += tri_count
        old_lo, old_hi = base_v, base_v + nverts
        slice_start = len(new_verts)
        face_start = len(new_faces)
        index: dict[int, int] = {}
        crossings: dict[tuple[int, int], int] = {}

        def push(pos, normal, uv, weights, _start=slice_start, _base=vbase):
            # faces carry global indices (the slice tuple's base_v is where this
            # slice's block starts in the rebuilt arrays)
            new_verts.append(tuple(float(c) for c in pos))
            new_normals.append(tuple(float(c) for c in normal))
            new_uvs.append(tuple(float(c) for c in uv))
            new_weights.append(weights)
            return _base + len(new_verts) - 1 - _start

        def keep(vi: int) -> int:
            nonlocal originals
            if vi not in index:
                originals += 1
                index[vi] = push(g.verts[vi], g.normals[vi], g.uvs[vi], g.weights[vi])
            return index[vi]

        def crossing(a: int, b: int, da: float, db: float) -> int:
            key = (a, b) if a < b else (b, a)
            if key not in crossings:
                s = da / (da - db)                      # 0 at a, 1 at b
                pos = verts[a] + s * (verts[b] - verts[a])
                na = np.asarray(g.normals[a], dtype=np.float64)
                nb = np.asarray(g.normals[b], dtype=np.float64)
                normal = na + s * (nb - na)
                length = float(np.linalg.norm(normal))
                normal = normal / length if length > 1e-12 else np.zeros(3)
                ua = np.asarray(g.uvs[a], dtype=np.float64)
                ub = np.asarray(g.uvs[b], dtype=np.float64)
                merged: dict[int, float] = {}
                for bi, w in g.weights[a]:
                    merged[bi] = merged.get(bi, 0.0) + (1.0 - s) * w
                for bi, w in g.weights[b]:
                    merged[bi] = merged.get(bi, 0.0) + s * w
                top = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
                total = sum(w for _, w in top) or 1.0
                crossings[key] = push(pos, normal, ua + s * (ub - ua),
                                      [(bi, w / total) for bi, w in top])
            return crossings[key]

        kept_here = 0
        dropped_here = 0
        split_here = 0
        for face in sl_faces:
            tri = (int(face[0]), int(face[1]), int(face[2]))
            assert old_lo <= min(tri) and max(tri) < old_hi
            ds = [float(dist[v]) for v in tri]
            if max(ds) <= 0.0:
                new_faces.append(tuple(keep(v) for v in tri))
                kept_here += 1
                continue
            if min(ds) > 0.0:
                dropped_here += 1
                removed.update(tri)
                continue
            split_here += 1
            # One plane cuts this face: the arms are 90 cm apart, so the plane whose
            # cone holds the distal vertices is the only candidate. Its own distance
            # (not the clamped one) is what places the crossing points, so an edge
            # that leaves the cone still splits where the plane is.
            plane = min(range(len(per_plane)),
                        key=lambda i: (not any(per_plane[i][1][v] < r_max and
                                               per_plane[i][0][v] > 0.0 for v in tri),
                                       -max(float(per_plane[i][0][v]) for v in tri)))
            axial = per_plane[plane][0]
            d = [float(axial[v]) for v in tri]
            poly = []
            for i in range(3):
                cur, nxt = tri[i], tri[(i + 1) % 3]
                dc, dn = d[i], d[(i + 1) % 3]
                if dc <= 0.0:
                    poly.append(("v", cur))
                if (dc < 0.0 < dn) or (dn < 0.0 < dc):
                    poly.append(("x", cur, nxt, dc, dn))

            def resolve(ref):
                if ref[0] == "v":
                    return keep(ref[1])
                return crossing(ref[1], ref[2], ref[3], ref[4])

            ring = [resolve(ref) for ref in poly]
            for k in range(1, len(ring) - 1):
                new_faces.append((ring[0], ring[k], ring[k + 1]))
        split_total += split_here
        report_per_slice.append({
            "src_mat": src_mat,
            "verts_before": nverts,
            "tris_before": tri_count,
            "verts_after": len(new_verts) - slice_start,
            # every source triangle that had geometry distal to the plane
            "tris_dropped": dropped_here + split_here,
            "tris_split": split_here,
            "tris_after": len(new_faces) - face_start,
        })
        new_slices.append((src_mat, vbase, fbase * 3, len(new_faces) - fbase,
                           len(new_verts) - slice_start))
        vbase += len(new_verts) - slice_start
        fbase = len(new_faces)
    g.verts = new_verts
    g.normals = new_normals
    g.uvs = new_uvs
    g.weights = new_weights
    g.faces = new_faces
    g.slices = new_slices
    return {"slices": report_per_slice,
            "tris_dropped": sum(s["tris_dropped"] for s in report_per_slice),
            "tris_split": split_total,
            "verts_added": len(new_verts) - originals,
            "verts_after": vbase,
            "removed_vertex_ids": sorted(removed)}


def cut_group_at_wrists(g, arm_joints, margin: float = 0.5) -> dict:
    """Drop the hands at the PD2 wrist joints, along the forearm axis.

    After retarget the outfit is in the 2B bind frame, arms straight out; the
    plane runs through the wrist joint along the forearm axis. Everything distal
    to it (the hand) is dropped; anything at or proximal to it is kept, so the
    rim sits exactly under a heister glove cuff. See :func:`cut_group_at_planes`
    for the radius limit that keeps this from cutting the legs off.
    """
    import numpy as np

    planes = [(np.asarray(arm_joints[side][0], dtype=float),
               _unit(np.subtract(arm_joints[side][0], arm_joints[side][1])))
              for side in (-1, 1)]
    report = cut_group_at_planes(g, planes, margin)
    # The Christies persist this report in their BUILD_INFO.json, and their
    # tracked bytes predate `removed_vertex_ids`; the palm caller reads it and
    # the wrist caller keeps its own record, so it ends here.
    del report["removed_vertex_ids"]
    return report


def cut_group_at_palm_bases(g, palms, margin: float = 0.0) -> dict:
    """Drop the palms and fingers where each palm begins, a whole triangle at a time.

    ``palms`` is `build_models.palm_planes` output: per side, the ``Hand`` joint
    (the wrist crease) and the axis from it to the knuckle bases. The plane is
    perpendicular to the palm, not to the forearm, so the heel of the hand goes
    with the fingers; a forearm-plane cut at the same joint (``margin`` 0.5)
    leaves a wedge of it behind. ``margin`` 0 is the crease itself.

    This is the coarse form: it stops up to a triangle band short of the plane.
    Use :func:`clip_group_at_palm_bases` when the surface has to end *on* it.
    """
    return cut_group_at_planes(g, _palm_planes(palms), margin)


def clip_group_at_palm_bases(g, palms, margin: float = 0.0) -> dict:
    """Cut the palms exactly where they begin, splitting the triangles on the plane.

    Same plane as :func:`cut_group_at_palm_bases` (the ``Hand`` joint, perpendicular
    to the palm), but cut on the plane rather than at the last triangle wholly
    proximal to it: the surface ends where the palm begins, to the millimetre, and
    nothing of the wrist is left standing above the cut.

    ``margin`` moves that plane along its own normal, in the group's units (cm), so a
    non-zero margin cuts *past* the crease. The shipped packs pass
    ``build_honoko2_dae.PALM_EXTEND_CM = 0.0`` again: D70 reverted the D62/D63/D65
    extensions, so the arm ends on the crease rather than inside the heister's glove.
    """
    return clip_group_at_planes(g, _palm_planes(palms), margin)


def _palm_planes(palms) -> list:
    """[(origin, axis)] for both palms, the form the cut helpers take."""
    import numpy as np

    return [(np.asarray(palms[side]["origin"], dtype=float),
             np.asarray(palms[side]["axis"], dtype=float)) for side in (-1, 1)]


def fallback_icon() -> bytes:
    """Navy tile with the pack initial — used with --no-previews."""
    import numpy as np
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (256, 256), (24, 28, 52))
    d = ImageDraw.Draw(img)
    d.text((104, 92), "H", fill=(232, 216, 164))
    rgba = np.dstack([np.asarray(img), np.full((256, 256), 255, np.uint8)])
    from dds_encode import rgba_to_bc3_dds as _enc
    return _enc(rgba)
