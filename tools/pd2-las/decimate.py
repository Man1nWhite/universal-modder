"""Mesh decimation for outfits whose source is denser than the target engine.

BodySlide/Skyrim body jewellery is authored for close-up renders: the Business
Woman necklace is 26,961 vertices across 222 separate beads, i.e. ~117 vertices
for a 4 mm sphere. A PAYDAY 2 heister body is ~5,000 vertices in total, so the
necklace alone would be five times the rest of the character.

The decimator here is **per-island vertex clustering**, which suits the actual
shape of the problem:

* the islands are independent, so an error inside one cannot propagate to
  another (a stray collapse never welds a bead to the chain link next to it);
* beads are convex blobs, and clustering a convex blob shrinks it by at most
  half a cell — measurable, and measured by `surface_error`;
* a UV seam inside a bead matters far less than the 4 mm of curvature it
  carries, so cluster-average UVs and normals are the right trade here. For a
  garment panel this function would be the wrong tool; for jewellery it is the
  right one.

`decimate` picks the cell size from the requested vertex budget rather than
asking for a ratio, because "keep 18 % of the vertices" means something
different on a bead than on a cuff.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Decimated:
    vertices: np.ndarray      # (n, 3) float64
    normals: np.ndarray       # (n, 3) float64
    uvs: np.ndarray           # (n, 2) float64
    triangles: np.ndarray     # (m, 3) int64
    cell: float               # cluster size actually used, in model units
    islands: int
    source_index: np.ndarray  # per new vertex: the source vertex it came from
    dropped: int = 0          # folded triangles removed to keep the winding clean

    @property
    def ratio(self) -> float:
        return self.vertices.shape[0]


def _islands(n_vertices: int, triangles: np.ndarray) -> np.ndarray:
    """Union-find island id per vertex."""
    parent = np.arange(n_vertices, dtype=np.int64)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for tri in triangles:
        a, b, c = (find(int(t)) for t in tri)
        if a != b:
            parent[a] = b
        b = find(b)
        c = find(c)
        if b != c:
            parent[b] = c
    roots = np.array([find(i) for i in range(n_vertices)], dtype=np.int64)
    _, ids = np.unique(roots, return_inverse=True)
    return ids


def _cluster_one(verts: np.ndarray, normals: np.ndarray, uvs: np.ndarray,
                 tris: np.ndarray, cell: float):
    """Collapse one island: grid-cluster vertices, keep surviving triangles."""
    key = np.floor((verts - verts.min(axis=0)) / cell).astype(np.int64)
    key -= key.min(axis=0)
    dims = key.max(axis=0) + 1
    flat = (key[:, 0] * dims[1] + key[:, 1]) * dims[2] + key[:, 2]
    uniq, inverse, counts = np.unique(flat, return_inverse=True, return_counts=True)

    # area-weighted centroid so a clump of vertices on one side of a cell does
    # not drag the new vertex away from the surface
    weights = np.zeros(uniq.size)
    np.add.at(weights, inverse, 1.0)
    new_verts = np.zeros((uniq.size, 3))
    np.add.at(new_verts, inverse, verts)
    new_verts /= weights[:, None]

    new_normals = np.zeros((uniq.size, 3))
    np.add.at(new_normals, inverse, normals)
    lengths = np.linalg.norm(new_normals, axis=1, keepdims=True)
    new_normals /= np.maximum(lengths, 1e-12)

    new_uvs = np.zeros((uniq.size, 2))
    np.add.at(new_uvs, inverse, uvs)
    new_uvs /= weights[:, None]

    # representative source vertex per cluster: the one closest to the centroid.
    # Callers use it to carry per-vertex data (blend weights) that cannot be
    # averaged, so a bead keeps the weights of its own nearest original vertex.
    dist = np.linalg.norm(verts - new_verts[inverse], axis=1)
    order = np.lexsort((dist, inverse))
    _, first = np.unique(inverse[order], return_index=True)
    representative = order[first]

    # source face normals, so an inverted cluster triangle can be spotted
    face_n = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]],
                      verts[tris[:, 2]] - verts[tris[:, 0]])
    out = []
    seen = set()
    for f, tri in enumerate(tris):
        a, b, c = (int(x) for x in inverse[tri])
        if a == b or b == c or a == c:
            continue                       # collapsed to an edge: zero area
        key3 = tuple(sorted((a, b, c)))
        if key3 in seen:
            # two source triangles landing on one cluster triple: keep the first
            # only when it is the same winding, else the surface doubles up
            continue
        # a cluster centroid can land on the wrong side of a sharp fold, which
        # mirrors the triangle; mirrored triangles show up as same-direction
        # shared edges (holes after back-face culling), so drop them
        new_n = np.cross(new_verts[b] - new_verts[a], new_verts[c] - new_verts[a])
        if float(np.dot(new_n, face_n[f])) <= 0.0:
            continue
        seen.add(key3)
        out.append((a, b, c))
    tris_out = (np.array(out, dtype=np.int64) if out
                else np.zeros((0, 3), dtype=np.int64))
    return new_verts, new_normals, new_uvs, tris_out, representative


def decimate(vertices: np.ndarray, triangles: np.ndarray, *, uvs=None,
             normals=None, max_vertices: int) -> Decimated:
    """Cluster-decimate ``vertices`` to at most ``max_vertices``, per island.

    The cell size is solved by bisection on the *actual* result, because the
    relationship between cell size and surviving vertex count depends on how the
    mesh is distributed in space. Twelve iterations is plenty: the count is
    monotone in the cell size.
    """
    verts = np.asarray(vertices, dtype=np.float64)
    tris = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    n = verts.shape[0]
    uvs = np.zeros((n, 2)) if uvs is None else np.asarray(uvs, dtype=np.float64)
    normals = (np.zeros((n, 3)) if normals is None
               else np.asarray(normals, dtype=np.float64))

    islands = _islands(n, tris)
    # `tris` variable reused below for the grouped pass
    groups = [(np.where(islands == i)[0]) for i in range(islands.max() + 1)]
    island_of_tri = islands[tris[:, 0]]

    extent = float(np.linalg.norm(verts.max(axis=0) - verts.min(axis=0)))
    spans = [float(np.linalg.norm(verts[g].max(axis=0) - verts[g].min(axis=0)))
             for g in groups]

    def survivor_count(cell: float) -> int:
        total = 0
        for g, span in zip(groups, spans):
            # never coarser than a third of an island, or a bead becomes a dot
            local = min(cell, max(span / 3.0, 1e-6))
            key = np.floor((verts[g] - verts[g].min(axis=0)) / max(local, 1e-9))
            total += int(np.unique(key, axis=0).shape[0])
        return total

    # vertex count falls monotonically with the cell size, so bisect on the
    # actual clustering rather than guessing an area ratio
    lo, hi = extent * 1e-5, extent * 0.5
    best = hi
    for _ in range(24):
        mid = (lo * hi) ** 0.5 if lo > 0 else (lo + hi) / 2
        if survivor_count(mid) <= max_vertices:
            best, hi = mid, mid
        else:
            lo = mid
        if hi - lo <= max(extent * 1e-6, 1e-9):
            break
    cell = best

    new_v, new_n, new_uv, new_t, new_src = [], [], [], [], []
    for g, island_index in zip(groups, range(len(groups))):
        local_tris = tris[island_of_tri == island_index]
        remap = np.full(n, -1, dtype=np.int64)
        remap[g] = np.arange(g.size)
        sub_tris = remap[local_tris]
        local = min(cell, max(spans[island_index] / 3.0, 1e-6))
        v, nn, uv, t, src = _cluster_one(verts[g], normals[g], uvs[g], sub_tris, local)
        base = sum(x.shape[0] for x in new_v)
        new_v.append(v)
        new_n.append(nn)
        new_uv.append(uv)
        new_t.append(t + base if t.size else t)
        new_src.append(g[src])

    out_v = np.concatenate(new_v) if new_v else np.zeros((0, 3))
    out_n = np.concatenate(new_n) if new_n else np.zeros((0, 3))
    out_uv = np.concatenate(new_uv) if new_uv else np.zeros((0, 2))
    out_t = np.concatenate(new_t) if new_t else np.zeros((0, 3), np.int64)
    out_src = (np.concatenate(new_src) if new_src
               else np.zeros(0, dtype=np.int64))

    # clustering folds a surface where it curves faster than one cell; the
    # folded triangles are what the engine would cull into holes
    fixed, dropped = drop_flipped(out_t)
    out_v, out_n, out_uv, out_t, out_src = compact(
        out_v, out_n, out_uv, fixed, out_src)

    return Decimated(
        vertices=out_v,
        normals=out_n,
        uvs=out_uv,
        triangles=out_t,
        cell=float(cell),
        islands=len(groups),
        source_index=out_src,
        dropped=int(dropped),
    )


def drop_flipped(triangles: np.ndarray, rounds: int = 12) -> tuple[np.ndarray, int]:
    """Remove triangles that share an edge in the *same* direction as a neighbour.

    Clustering folds a surface where it curves faster than one cell, and a folded
    triangle reads as a hole once the engine back-face culls. Dropping both
    members of every same-direction pair restores the invariant the rest of the
    pipeline asserts (`build_models.orientation_breaks == 0`); on a 4 mm bead the
    cost is a handful of sub-millimetre triangles hidden inside the chain.
    """
    tris = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    removed = 0
    for _ in range(rounds):
        edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for f, (a, b, c) in enumerate(tris):
            for x, y in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
                key = (x, y) if x < y else (y, x)
                edges.setdefault(key, []).append((f, 1 if x < y else -1))
        bad: set[int] = set()
        for dirs in edges.values():
            if len(dirs) == 2 and dirs[0][1] == dirs[1][1]:
                bad.add(dirs[0][0])
                bad.add(dirs[1][0])
        if not bad:
            break
        removed += len(bad)
        keep = np.ones(tris.shape[0], dtype=bool)
        keep[list(bad)] = False
        tris = tris[keep]
    return tris, removed


def compact(vertices: np.ndarray, normals: np.ndarray, uvs: np.ndarray,
            triangles: np.ndarray, source_index: np.ndarray):
    """Drop vertices no triangle uses, renumbering the triangles."""
    used = np.unique(triangles) if triangles.size else np.zeros(0, np.int64)
    remap = np.full(vertices.shape[0], -1, dtype=np.int64)
    remap[used] = np.arange(used.size)
    return (vertices[used], normals[used], uvs[used], remap[triangles],
            source_index[used])


def surface_error(vertices: np.ndarray, triangles: np.ndarray,
                  approx_vertices: np.ndarray, sample: int = 4000) -> dict:
    """How far the decimated surface drifts, measured on the original vertices.

    Nearest-vertex is a slight over-estimate of true point-to-surface distance,
    which is the safe direction for a "did we break it" check. Chunked so a
    26k-vertex necklace does not allocate a 26k x 26k matrix.
    """
    verts = np.asarray(vertices, dtype=np.float64)
    approx = np.asarray(approx_vertices, dtype=np.float64)
    rng = np.random.default_rng(0)
    idx = np.sort(rng.choice(verts.shape[0], size=min(sample, verts.shape[0]),
                             replace=False))
    worst = []
    for start in range(0, idx.size, 500):
        chunk = verts[idx[start:start + 500]]
        d = np.linalg.norm(chunk[:, None, :] - approx[None, :, :], axis=2)
        worst.append(d.min(axis=1))
    worst = np.concatenate(worst)
    return {
        "mean": float(worst.mean()),
        "p95": float(np.percentile(worst, 95)),
        "max": float(worst.max()),
    }
