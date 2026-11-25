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
    """Drop the palms and fingers where each palm begins.

    ``palms`` is `build_models.palm_planes` output: per side, the ``Hand`` joint
    (the wrist crease) and the axis from it to the knuckle bases. The plane is
    perpendicular to the palm, not to the forearm, so the heel of the hand goes
    with the fingers; a forearm-plane cut at the same joint (``margin`` 0.5)
    leaves a wedge of it behind. ``margin`` 0 is the crease itself.
    """
    import numpy as np

    planes = [(np.asarray(palms[side]["origin"], dtype=float),
               np.asarray(palms[side]["axis"], dtype=float)) for side in (-1, 1)]
    return cut_group_at_planes(g, planes, margin)


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
