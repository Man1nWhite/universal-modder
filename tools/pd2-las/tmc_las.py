#!/usr/bin/env python3
"""Helpers shared by the Diesel LAS packs built from a DOAXVV `.TMC`.

These are the frame and mesh post-process helpers of the TMC-only Honoka LAS pack,
kept when that pack and its driver were deleted on 2026-11-15
(`docs/pd2-las/DECISIONS.md`, D40). `build_honoko2_dae.py` is the one caller: it
takes the TMC's geometry frame, skin weights and joint world binds, and applies
these post-processes to the outfit retargeted onto the 2B skeleton.

* :func:`basis_matrix` / :func:`glbl_to_diesel` — the TMC frame (Y-up, cm) to the
  Diesel frame (Z-up, cm), det = +1, and the 171 world bind matrices with it.
* :func:`cut_group_at_wrists` — drop the hands so a heister glove covers the rim.
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


def cut_group_at_wrists(g, arm_joints, margin: float = 0.5) -> dict:
    """Drop every triangle with a vertex past the PD2 wrist plane.

    After retarget the outfit is in the 2B bind frame, arms straight out;
    the plane runs through the wrist joint along the forearm axis. Everything
    distal to it (the hand) is dropped; anything at or proximal to it is
    kept, so the rim sits exactly under the glove cuff.

    The drop is done slice by slice: each slice keeps its own compact vertex
    block (the Diesel atom invariant requires the slice's triangles to index
    inside its own block), unused vertices are dropped, and the slices'
    ``base_v``/``base_i`` are rebuilt.

    The hand is the region beyond the wrist joint (radial distance < 28 cm
    from the forearm axis); a plain half-space cut at the wrist is wrong for
    the PD2 bind pose (the forearm axis points down-forward, so the plane
    would contain the feet and cut the lower legs off).
    """
    import numpy as np

    wrist_l, elbow_l = (np.array(v, dtype=np.float64) for v in arm_joints[-1])
    wrist_r, elbow_r = (np.array(v, dtype=np.float64) for v in arm_joints[1])
    axis_l = wrist_l - elbow_l
    axis_l /= np.linalg.norm(axis_l)
    axis_r = wrist_r - elbow_r
    axis_r /= np.linalg.norm(axis_r)
    verts = np.asarray(g.verts, dtype=np.float64)

    def hand_side(wrist, axis, r_max=28.0):
        # beyond the wrist along the forearm axis, AND close to it: the hand and
        # the outstretched fingers.  A bare half-space would also swallow the
        # lower legs, because in the PD2 bind pose the forearm axis points
        # steeply down-forward.
        v = verts - wrist
        t = v @ axis
        perp = np.linalg.norm(v - np.outer(t, axis), axis=1)
        return (t > margin) & (perp < r_max)

    distal = hand_side(wrist_l, axis_l) | hand_side(wrist_r, axis_r)

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
    g.verts = new_verts
    g.normals = new_normals
    g.uvs = new_uvs
    g.weights = new_weights
    g.faces = new_faces
    g.slices = new_slices
    return {"slices": report_per_slice,
            "tris_dropped": sum(s["tris_dropped"] for s in report_per_slice),
            "verts_after": vbase}


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
