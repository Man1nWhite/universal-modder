"""Tangent frames: the U and V direction of every vertex, from what the file holds.

A Diesel geometry stores, per vertex, the direction in which the texture's u
grows and the one in which its rows run (`diesel_model`: UV_DIRECTION_U0, V0).
This module makes both, in a way that gives the same bytes on every machine:

* It starts from the float32 positions, normals and UVs that are written to
  the file, not from the float64 values the builder was working with. Those
  differ in their last bits between CPUs; the float32 values do not.
* It uses + - * / and sqrt only, and sums with `math.fsum`. IEEE 754 fixes the
  result of each of these to the last bit, on any CPU, in any order of the
  triangles.
* Where the UV map gives a vertex no V direction (no triangle around it has
  area in UV), the handedness of its frame is a rule and not a computation.
  Until 2026-11-12 it was the sign of a number that is zero in exact
  arithmetic: the CPU's rounding decided it.

The rule. Such a vertex takes the handedness of the corners it shares a triangle
with, by majority, and passes it on to the next such vertex. With no neighbour
to take it from, or a tie, it is UNMIRRORED. Both halves have a precedent:

* `mikktspace.c` (mmikk/MikkTSpace at 1cb38f46977c), the reference tangent-space
  code. A triangle without UV area is "group with anything": the first group of
  neighbours that claims it "determines it's orientation" (lines 1156-1166); one
  that nothing claims keeps the flag "not orientation preserving" (line 988),
  which in this file's convention is UNMIRRORED.
* The models the game is known to accept (the 34 units Legendary Armour Skins
  ships; 2B's). Counted on 2026-11-12: of 635 such vertices that have a handed
  frame at all, 631 are UNMIRRORED, and the 8 with a neighbour to compare with
  agree with it. The other 2,847 have no frame (U equal to V, or zero), so the
  game is not particular here.
"""
from __future__ import annotations

import math

import numpy as np

#: A triangle with less UV area than this gives no direction (as diesel_model.UV_DET_EPS).
UV_DET_EPS = 1e-8
#: The handedness of an unmirrored UV island: V = UNMIRRORED * cross(normal, U).
#: U points where u grows and V where the image's rows run, downward; seen from
#: outside, with u to the right, cross(normal, U) points up.
UNMIRRORED = -1.0


def _stored(rows, width: int) -> list:
    """The values as the file will hold them: rounded to float32, read back."""
    return np.asarray(rows, dtype=np.float64).reshape(-1, width).astype(np.float32).astype(np.float64).tolist()


def _total(parts: list) -> tuple:
    return (math.fsum(p[0] for p in parts), math.fsum(p[1] for p in parts), math.fsum(p[2] for p in parts))


def tangent_frames(verts, normals, uvs, faces, details: bool = False):
    """(u_directions, v_directions) for a mesh, one unit 3-vector per vertex.

    U is the UV map's u direction, projected into the tangent plane; where the
    map gives none, a fixed direction of that plane. V is cross(normal, U) or
    its opposite: the handedness of the UV map around the vertex, or the rule
    in the module's docstring. With `details`, a third value: the vertices the
    rule decided.
    """
    points, around, coords = _stored(verts, 3), _stored(normals, 3), _stored(uvs, 2)
    count = len(points)
    parts_u = [[] for _ in range(count)]
    parts_v = [[] for _ in range(count)]
    for a, b, c in faces:
        pa, pb, pc = points[a], points[b], points[c]
        ta, tb, tc = coords[a], coords[b], coords[c]
        e1x, e1y, e1z = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        e2x, e2y, e2z = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        s1, t1, s2, t2 = tb[0] - ta[0], tb[1] - ta[1], tc[0] - ta[0], tc[1] - ta[1]
        det = s1 * t2 - s2 * t1
        if not abs(det) > UV_DET_EPS:
            continue
        inv = 1.0 / det
        fu = ((e1x * t2 - e2x * t1) * inv, (e1y * t2 - e2y * t1) * inv, (e1z * t2 - e2z * t1) * inv)
        fv = ((e1x * s2 - e2x * s1) * inv, (e1y * s2 - e2y * s1) * inv, (e1z * s2 - e2z * s1) * inv)
        for index in (a, b, c):
            parts_u[index].append(fu)
            parts_v[index].append(fv)

    u_out, crossed, sign = [], [], []
    for index in range(count):
        nx, ny, nz = around[index]
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 1e-8:
            nx, ny, nz = nx / length, ny / length, nz / length
        else:                                           # a normal of no length would make everything below NaN
            nx, ny, nz = 0.0, 1.0, 0.0
        ux, uy, uz = _total(parts_u[index])
        length = math.sqrt(ux * ux + uy * uy + uz * uz)
        if length < 1e-12:
            ux, uy, uz = 0.0, 1.0, 0.0
        else:
            ux, uy, uz = ux / length, uy / length, uz / length
        along = ux * nx + uy * ny + uz * nz
        ux, uy, uz = ux - along * nx, uy - along * ny, uz - along * nz
        length = math.sqrt(ux * ux + uy * uy + uz * uz)
        if length < 1e-6:                               # no U left in the tangent plane: one picked from the normal
            rx, ry, rz = (1.0, 0.0, 0.0) if abs(nx) < 0.9 else (0.0, 1.0, 0.0)
            ux, uy, uz = ny * rz - nz * ry, nz * rx - nx * rz, nx * ry - ny * rx
            length = max(math.sqrt(ux * ux + uy * uy + uz * uz), 1e-12)
        ux, uy, uz = ux / length, uy / length, uz / length
        bx, by, bz = ny * uz - nz * uy, nz * ux - nx * uz, nx * uy - ny * ux
        length = max(math.sqrt(bx * bx + by * by + bz * bz), 1e-12)
        bx, by, bz = bx / length, by / length, bz / length
        vx, vy, vz = _total(parts_v[index])
        if math.sqrt(vx * vx + vy * vy + vz * vz) < 1e-12:
            sign.append(0.0)                            # the UV map says nothing here: the rule decides
        else:
            sign.append(1.0 if bx * vx + by * vy + bz * vz >= 0.0 else -1.0)
        u_out.append((ux, uy, uz))
        crossed.append((bx, by, bz))

    ruled = [index for index in range(count) if sign[index] == 0.0]
    undecided = list(ruled)
    if undecided:
        neighbours = {index: [] for index in undecided}
        for face in faces:
            for index in face:
                if index in neighbours:
                    neighbours[index].extend(other for other in face if other != index)
        while undecided:
            votes = {index: sum(sign[other] for other in neighbours[index]) for index in undecided}
            decided = {index: (1.0 if vote > 0 else -1.0) for index, vote in votes.items() if vote != 0}
            if not decided:
                break
            for index, value in decided.items():
                sign[index] = value
            undecided = [index for index in undecided if index not in decided]
        for index in undecided:
            sign[index] = UNMIRRORED
    v_out = [(s * b[0], s * b[1], s * b[2]) for s, b in zip(sign, crossed)]
    return (u_out, v_out, ruled) if details else (u_out, v_out)
