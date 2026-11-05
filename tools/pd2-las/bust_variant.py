"""Chest-mass morph: the geometry half of the `Miranda_Busty_LAS` variant.

`build_busty_variant.py` rebuilds the Miranda LAS outfit through the untouched
`build_models.py` pipeline and then runs this pass over the authored mesh
groups before they are written to Diesel. Nothing here touches the shipped
`dist/Miranda_LAS.zip` route: the pass is only reachable through the variant
builder, which writes its own pack, unit paths and `dist/` archive.

Why this is not just "push the chest forward"
---------------------------------------------
Measured on the authored mesh (z-up, cm, +y is the front), the outfit's chest is
one broad, flat-fronted shell: the front surface peaks at y≈20 cm over a
| x | 2…11 cm band at z 132…148, with a **0.4 cm** sternum dip. Two problems
follow from that, and both were visible in the first previews:

1. *The source has nowhere near enough geometry for a new volume.* The breast
   region carries roughly one vertex every 2.5 cm, so any bulge reads as a
   faceted balloon. The pass therefore **subdivides the chest locally** (a
   one-to-four split of the triangles that cover the edit region) before it
   moves anything, and appends the new vertices after the group's existing
   blocks so the Diesel atom tiling is untouched.
2. *A radial push over a convex shell builds a shelf, not a breast.* The
   displacement is therefore a **height field over the (x, z) plane** — an
   elliptical cap, shorter below the apex than above it — scaled by how far the
   surface already stands proud of the chest wall, so the mass grows instead of
   the ribcage, and damped on the midline so the two breasts stay separate.

The morph is a pure function of the bind-pose position, so the identical pass
runs on `g_body`, `g_body_lod1` and the body block of `s_body` (which hold
bit-identical positions) and the shadow caster and LOD stay aligned with the
visible mesh::

    u     = (x - side*APEX_X) / RADIUS_X
    w     = (z - APEX_Z) / (RADIUS_Z_UP if z > APEX_Z else RADIUS_Z_DOWN)
    r2    = u*u + w*w                       -> 0 at the apex, 1 at the rim
    dome  = (1 - r2)**2                     -> C1 (zero slope) at the rim
    gate  = smoothstep((y - GATE_LO)/(GATE_HI - GATE_LO))        front
          * smoothstep((X_ZERO - |x|)/(X_ZERO - X_FULL))          lateral
    depth = max(0, y - WALL_Y)              -> existing protrusion
    gain  = cup_gain + round_gain*min(1, depth/(APEX_Y - WALL_Y))
    valley= 1 - VALLEY*exp(-(x/VALLEY_W)**2)                     sternum damping

    dy = (dome_+ + dome_-) * gate * gain * depth * valley
    dz =  lift * (dome_+ + dome_-) * gate
    dx =  spread * (dome_+ - dome_-) * gate     (exactly 0 on the midline)

After the displacement a short Laplacian relaxation smooths the region (the
boundary ring stays pinned, so nothing outside the edit moves), which removes
the flat-shaded facets and the sawtooth along the sleeve seam. Normals are then
rebuilt area-weighted over position-welded vertices and blended back by morph
strength, so the rim keeps the shading the base build shipped.
"""

from __future__ import annotations

import math

#: Breast apex, measured on the authored mesh (cm). The front surface peaks at
#: y≈20 cm on a band centred at z≈140, |x| 2…11; the cap sits slightly above
#: that peak because the lower pole carries more of the new mass.
APEX_X = 6.0
APEX_Z = 139.0
#: Cap extent. The lateral radius covers the measured plateau; the vertical
#: radii are deliberately asymmetric — a breast's lower pole ends in the
#: inframammary fold a few centimetres under the apex, while the upper pole
#: fades out slowly toward the collarbone. Equal radii produced the horizontal
#: "shelf" seen in the first previews.
RADIUS_X = 7.0
RADIUS_Z_UP = 5.0
RADIUS_Z_DOWN = 8.5
#: The breast alone has to stop somewhere, and a single dome that ends at the
#: rim leaves a visible *shoulder* on the upper chest — the side view showed the
#: upper pole as a flat shelf ending in a crease at the collarbone. A second,
#: much wider and much shallower dome underneath it (the fullness of the chest
#: above and between the breasts) carries the surface down to the base mesh
#: gradually, so the upper pole fades out instead of ending.
SOFT_SCALE = 2.0
SOFT_WEIGHT = 0.25
SOFT_POWER = 1.8
#: Top of the apex plateau on the source mesh — the reference depth that
#: normalises ``rel`` (how close a vertex is to the tip of the mass).
APEX_Y = 20.0
#: The chest wall plane: ``y - WALL_Y`` is how far the surface already bulges
#: forward, so scaling it grows the *existing* masses instead of inflating the
#: ribcage. Measured from the back surface (y≈-5) and the front (y≈20).
WALL_Y = 5.0
#: Forward gate: nothing behind the chest wall moves. Below ``GATE_LO`` (the
#: flanks and the flat upper chest at the neckline) the weight is 0; by
#: ``GATE_HI`` — the bust surface itself — it is 1.
GATE_LO = 6.5
GATE_HI = 13.0
#: Lateral gate: the underarm seam and the outer torso edge stay exactly where
#: the base build put them, so the arms cannot be caught by the swell.
X_FULL = 11.0
X_ZERO = 13.0
#: Cleavage: fraction of the *added* forward push removed on the midline.
VALLEY = 0.70
VALLEY_W = 2.1
#: Dome profile exponent. ``(1 - r2)**p`` with p > 1 keeps a broad, full centre
#: and a fast fade at the rim; p = 2 ramps too gently and reads as a plateau.
DOME_POWER = 1.6
#: Safety ceiling: no other body part lives between the cap rim and the head, so
#: this only ever guards the shared shadow-caster vertex block. The field fades
#: out over ``CEILING_FADE`` centimetres below it — a hard cut-off leaves a ridge.
Z_CEILING = 154.0
CEILING_FADE = 5.0

#: Cup-size preset (see the module docstring for what each term does).
DEFAULT_CUP_GAIN = 0.62
DEFAULT_ROUND_GAIN = 0.14
DEFAULT_LIFT = 0.5
DEFAULT_SPREAD = 0.7
DEFAULT_VALLEY = VALLEY
#: How far past the dome rim the local subdivision reaches (see in_region).
SUBDIVIDE_MARGIN = 1.25
#: Height band the local subdivision is allowed in (cm): the front chest panel
#: only, clear of the collar above and the waist seam below.
SUBDIVIDE_Z = (126.0, 147.0)
#: Longest UV distance an edge may span and still be split. A chest edge is
#: ~0.02…0.08 of the sheet; anything past this crosses a texture seam, and the
#: midpoint's averaged UV would land on the sheet's black border.
MAX_EDGE_UV_DISTANCE = 0.20
#: Local subdivision rounds and relaxation, in Laplacian steps of ``strength``.
DEFAULT_SUBDIVISIONS = 1
DEFAULT_SMOOTH_ITERATIONS = 3
DEFAULT_SMOOTH_STRENGTH = 0.32


def smoothstep(t: float) -> float:
    """Hermite ramp on ``[0, 1]`` with zero slope at both ends."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


class ChestMorph:
    """Position-driven breast enlargement for the Miranda outfit meshes."""

    def __init__(self, cup_gain: float = DEFAULT_CUP_GAIN,
                 round_gain: float = DEFAULT_ROUND_GAIN,
                 lift: float = DEFAULT_LIFT,
                 spread: float = DEFAULT_SPREAD,
                 valley: float = DEFAULT_VALLEY,
                 subdivisions: int = DEFAULT_SUBDIVISIONS,
                 smooth_iterations: int = DEFAULT_SMOOTH_ITERATIONS,
                 smooth_strength: float = DEFAULT_SMOOTH_STRENGTH):
        for name, value in (("cup_gain", cup_gain), ("round_gain", round_gain),
                            ("lift", lift), ("spread", spread)):
            if value < 0.0:
                raise ValueError(f"ChestMorph {name} must be non-negative")
        if not 0.0 <= valley <= 1.0:
            raise ValueError("ChestMorph valley must be within [0, 1]")
        if subdivisions < 0:
            raise ValueError("ChestMorph subdivisions must be >= 0")
        if not 0.0 <= smooth_strength <= 0.5:
            raise ValueError("ChestMorph smooth_strength must be within [0, 0.5]")
        self.cup_gain = float(cup_gain)
        self.round_gain = float(round_gain)
        self.lift = float(lift)
        self.spread = float(spread)
        self.valley = float(valley)
        self.subdivisions = int(subdivisions)
        self.smooth_iterations = int(smooth_iterations)
        self.smooth_strength = float(smooth_strength)

    # ---------------------------------------------------------------- profile
    def _falloff(self, x: float, z: float, side: int, scale: float,
                 power: float) -> float:
        u = (x - side * APEX_X) / (RADIUS_X * scale)
        rz = (RADIUS_Z_UP if z > APEX_Z else RADIUS_Z_DOWN) * scale
        w = (z - APEX_Z) / rz
        r2 = u * u + w * w
        if r2 >= 1.0:
            return 0.0
        return (1.0 - r2) ** power

    def weight(self, x: float, z: float, side: int) -> float:
        """Dome falloff of the breast centred at ``side * APEX_X``.

        Two nested domes: the breast itself, plus a wide shallow one that keeps
        the upper pole from ending in a ridge (see ``SOFT_WEIGHT``). Both are
        C1 at their rims, so the composite surface is smooth everywhere.
        """
        main = self._falloff(x, z, side, 1.0, DOME_POWER)
        soft = self._falloff(x, z, side, SOFT_SCALE, SOFT_POWER)
        # normalised so the composite still reaches exactly 1.0 at the apex:
        # `cup_gain` then means the same depth whether or not the soft dome is
        # in the mix, and the presets do not have to be re-tuned around it
        return (main + SOFT_WEIGHT * soft) / (1.0 + SOFT_WEIGHT)

    def front_gate(self, y: float) -> float:
        """1 on the bust surface, 0 behind the chest wall / on the upper chest."""
        return smoothstep((y - GATE_LO) / (GATE_HI - GATE_LO))

    def lateral_gate(self, x: float) -> float:
        """1 towards the midline, 0 at the underarm seam."""
        return smoothstep((X_ZERO - abs(x)) / (X_ZERO - X_FULL))

    def valley_factor(self, x: float) -> float:
        """``1 - VALLEY`` on the sternum, easing to 1 across the bust."""
        return 1.0 - self.valley * math.exp(-(x / VALLEY_W) ** 2)

    def displacement(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """Bind-pose displacement for a vertex at ``(x, y, z)`` (cm)."""
        ceil = self.ceiling(x, z)
        if ceil == 0.0:
            return (0.0, 0.0, 0.0)
        w_pos = self.weight(x, z, +1)
        w_neg = self.weight(x, z, -1)
        if w_pos == 0.0 and w_neg == 0.0:
            return (0.0, 0.0, 0.0)
        gate = self.front_gate(y) * self.lateral_gate(x)
        if gate == 0.0:
            return (0.0, 0.0, 0.0)
        fall = (w_pos + w_neg) * gate * ceil
        depth = max(0.0, y - WALL_Y)
        rel = min(1.0, depth / (APEX_Y - WALL_Y))
        gain = self.cup_gain + self.round_gain * rel
        dy = fall * gain * depth * self.valley_factor(x)
        # Lift is a *bounded* rise of the apex, strongest at the tip and zero at
        # the rim. Scaling it by the whole falloff (the first version) moved the
        # upper pole up as much as the apex, which flattened the top of the
        # breast into the horizontal shelf the side view showed.
        dz = self.lift * fall * fall
        dx = self.spread * (w_pos - w_neg) * gate
        return (dx, dy, dz)

    def ceiling(self, x: float, z: float) -> float:
        """Soft upper bound, 1 on the bust and 0 at ``Z_CEILING``.

        ``Z_CEILING`` guards the shared shadow-caster block above the chest, but
        clipping the displacement to zero in one step there put a hard horizontal
        edge across the upper chest — the "shelf" the tight side views showed.
        The bound is now a smoothstep over the last ``CEILING_FADE`` centimetres,
        so the field reaches zero with zero slope.
        """
        return smoothstep((Z_CEILING - z) / CEILING_FADE)

    def weight_at(self, x: float, y: float, z: float) -> float:
        """Normalised edit strength in ``[0, 1]``, used to blend shading."""
        if z >= Z_CEILING:
            return 0.0
        return min(1.0, (self.weight(x, z, +1) + self.weight(x, z, -1))
                   * self.front_gate(y) * self.lateral_gate(x)
                   * self.ceiling(x, z))

    def in_region(self, x: float, y: float, z: float) -> bool:
        """Whether a position is close enough to be worth subdividing.

        Deliberately a little larger than the displaced region — a one-to-four
        split changes the triangle size, and a density step that lands where the
        displacement is still non-zero shows up as a hairline. It is deliberately
        *smaller* than the whole chest band, though: it must stay on the front
        chest panel, away from the sleeve and panel seams where a split can
        interpolate UVs across a texture seam (that sampled the black border of
        the sheet in the first attempts).
        """
        if not (SUBDIVIDE_Z[0] <= z <= SUBDIVIDE_Z[1]):
            return False
        if abs(x) > X_ZERO or self.front_gate(y) < 0.75:
            return False
        for side in (+1, -1):
            u = (x - side * APEX_X) / (RADIUS_X * SUBDIVIDE_MARGIN)
            rz = (RADIUS_Z_UP if z > APEX_Z else RADIUS_Z_DOWN) * SUBDIVIDE_MARGIN
            w = (z - APEX_Z) / rz
            if u * u + w * w < 1.0:
                return True
        return False

    # ------------------------------------------------------------------ apply
    def apply(self, group, materials=("miranda_body",), subdivide: bool = True,
              label: str | None = None, log=None) -> int:
        """Subdivide, displace, relax and re-shade one authored group.

        Returns the number of vertices whose position changed. ``materials``
        restricts the edit to the given slices — the shadow-caster group also
        holds the head, and the third-person group holds the head drawable.
        """
        if subdivide and self.subdivisions and getattr(group, "faces", None):
            added = subdivide_region(group, self, levels=self.subdivisions,
                                     materials=materials)
            if log and added:
                log(f"[bust] {label or group.name}: +{added} chest vertices "
                    f"(local subdivision)")
        # snapshot *after* the split: the copy matcher uses pre-morph positions,
        # and the new vertices are part of the mesh it has to keep consistent
        origin = list(group.verts)
        moved = self.displace(group, materials)
        if moved:
            smooth_region(group, self, self.smooth_iterations, self.smooth_strength)
            keep_copies_together(group, origin)
            rebuild_normals(group, self)
        return moved

    def displace(self, group, materials=("miranda_body",)) -> int:
        """Move the chest vertices of one authored group; returns the count."""
        moved = 0
        for mat, base_v, _base_i, _tris, nverts in group.slices:
            if materials is not None and mat not in materials:
                continue
            for i in range(base_v, base_v + nverts):
                x, y, z = group.verts[i]
                dx, dy, dz = self.displacement(x, y, z)
                if dx == 0.0 and dy == 0.0 and dz == 0.0:
                    continue
                group.verts[i] = (x + dx, y + dy, z + dz)
                moved += 1
        return moved

    # ----------------------------------------------------------------- checks
    def describe(self) -> dict:
        return {
            "cup_gain": self.cup_gain,
            "round_gain": self.round_gain,
            "lift_cm": self.lift,
            "spread_cm": self.spread,
            "valley": self.valley,
            "apex_x_cm": APEX_X,
            "apex_z_cm": APEX_Z,
            "radius_x_cm": RADIUS_X,
            "radius_z_cm": [RADIUS_Z_DOWN, RADIUS_Z_UP],
            "wall_y_cm": WALL_Y,
            "gate_y_cm": [GATE_LO, GATE_HI],
            "gate_x_cm": [X_FULL, X_ZERO],
            "subdivisions": self.subdivisions,
            "smooth": [self.smooth_iterations, self.smooth_strength],
        }


# --------------------------------------------------------------- subdivision

def _last_slice_face_range(group) -> tuple[int, int]:
    """Face range ``[start, end)`` covered by the group's last slice."""
    _mat, _base_v, base_i, tris, _nverts = group.slices[-1]
    start = base_i // 3
    return start, start + tris


def _merge_weights(wa, wb):
    """Average two influence lists (top three, renormalised)."""
    acc: dict[int, float] = {}
    for i, w in wa:
        acc[i] = acc.get(i, 0.0) + 0.5 * w
    for i, w in wb:
        acc[i] = acc.get(i, 0.0) + 0.5 * w
    items = sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    total = sum(w for _, w in items) or 1.0
    return [(i, w / total) for i, w in items]


def _uv_distance(u, v) -> float:
    return max(abs(u[0] - v[0]), abs(u[1] - v[1]))


def _crosses_uv_seam(uvs, tri) -> bool:
    """True when one of the triangle's edges spans a texture seam."""
    a, b, c = tri
    return (_uv_distance(uvs[a], uvs[b]) > MAX_EDGE_UV_DISTANCE
            or _uv_distance(uvs[b], uvs[c]) > MAX_EDGE_UV_DISTANCE
            or _uv_distance(uvs[c], uvs[a]) > MAX_EDGE_UV_DISTANCE)


def _patch_faces(group, morph: ChestMorph) -> tuple[set[int], int, int]:
    """Faces the one-to-four split applies to, plus the last slice's range.

    A face is in the patch when part of it lies inside the edited region and it
    does not straddle a texture seam (splitting such a face would give its
    midpoint an averaged UV that lands on the sheet's black border). The patch
    border is handled by `_refine`, which inserts the same edge midpoints into
    the neighbouring faces so the surface cannot open along a T-junction.
    """
    first, last = _last_slice_face_range(group)
    # Vertices that exist more than once at the same position are the mesh's
    # UV-seam copies. A neighbour of such a vertex stores the seam as two
    # *unrelated* edges, so splitting one side inserts a midpoint the other side
    # does not have: a hairline crack, right on the bust's outer edge. Faces that
    # touch a copy are therefore left whole — they sit where the displacement
    # has already faded out.
    counts: dict[tuple[int, int, int], int] = {}
    for v in range(len(group.verts)):
        k = tuple(round(c * 1e4) for c in group.verts[v])
        counts[k] = counts.get(k, 0) + 1
    shared = set()
    for fi in range(first, last):
        for v in group.faces[fi]:
            k = tuple(round(c * 1e4) for c in group.verts[v])
            if counts[k] > 1:
                shared.add(v)
    patch: set[int] = set()
    for fi in range(first, last):
        tri = group.faces[fi]
        if any(v in shared for v in tri):
            continue
        if not any(morph.in_region(*group.verts[v]) for v in tri):
            continue
        if _crosses_uv_seam(group.uvs, tri):
            continue
        patch.add(fi)
    return patch, first, last


def subdivide_region(group, morph: ChestMorph, levels: int = 1,
                     materials=("miranda_body",)) -> int:
    """Split the chest triangles one-to-four, appending the new vertices.

    Only faces of the group's **last** slice are touched, and the new faces are
    appended directly after that slice's block, so the Diesel render atoms —
    which tile the vertex array and the index stream in slice order — keep
    describing the mesh exactly. Positions, UVs and skin weights of a new vertex
    are the average of its edge's endpoints, so the split itself changes nothing
    visible; it only gives the morph somewhere to put a smooth surface.

    The patch border is *green*-refined: a face just outside the patch that
    shares a split edge is re-triangulated through that edge's midpoint. Without
    that step the midpoint (which the morph then pulls off the straight edge)
    no longer lies on its neighbour's edge, and the mesh opens into the jagged
    black cracks the first attempts produced.
    """
    if not group.slices or not group.faces:
        return 0
    mat, base_v, base_i, tris, nverts = group.slices[-1]
    if materials is not None and mat not in materials:
        return 0
    added = 0
    for _level in range(levels):
        patch, first, last = _patch_faces(group, morph)
        if not patch:
            break
        added += _refine(group, patch, first, last)
        group.slices[-1] = (mat, base_v, base_i, len(group.faces) - first,
                            len(group.verts) - base_v)
        if not added:
            break
    return added


def _refine(group, patch: set[int], first: int, last: int) -> int:
    """Red-split ``patch`` and green-split the faces around it. Returns new verts."""
    # every edge that at least one patch face wants split
    split_edges: set[tuple[int, int]] = set()
    for fi in patch:
        a, b, c = group.faces[fi]
        split_edges.update(((min(a, b), max(a, b)), (min(b, c), max(b, c)),
                            (min(c, a), max(c, a))))
    # A face is re-triangulated if any of its edges is split, and any edge of
    # such a face that runs between two such faces is split too — otherwise the
    # neighbour would be left with a half-split edge (a T-junction) of its own.
    touching: set[int] = set(patch)
    for fi in range(first, last):
        a, b, c = group.faces[fi]
        for e in ((a, b), (b, c), (c, a)):
            if (min(e), max(e)) in split_edges:
                touching.add(fi)
                break
    grew = True
    while grew:
        grew = False
        owners: dict[tuple[int, int], list[int]] = {}
        for fi in touching:
            a, b, c = group.faces[fi]
            for e in ((a, b), (b, c), (c, a)):
                owners.setdefault((min(e), max(e)), []).append(fi)
        for e, fs in owners.items():
            if e in split_edges or len(fs) != 2:
                continue
            split_edges.add(e)
            grew = True

    before = len(group.verts)
    midpoints: dict[tuple, int] = {}

    def mid(i: int, j: int, own_uvs) -> int:
        """Midpoint of edge (i, j) as seen from a face with these UVs.

        Keyed on the edge *and* the two endpoint UVs, so an edge that carries a
        texture seam gets one midpoint per side, each with a correct
        interpolated UV, instead of a single averaged UV that samples garbage.
        """
        ui, uj = own_uvs(i), own_uvs(j)
        lo, hi, (ulo, uhi) = ((i, j, (ui, uj)) if i < j else (j, i, (uj, ui)))
        key = (lo, hi, round(ulo[0] * 512), round(ulo[1] * 512),
               round(uhi[0] * 512), round(uhi[1] * 512))
        got = midpoints.get(key)
        if got is not None:
            return got
        pi, pj = group.verts[lo], group.verts[hi]
        idx = len(group.verts)
        group.verts.append(tuple(0.5 * (pi[k] + pj[k]) for k in range(3)))
        ni, nj = group.normals[lo], group.normals[hi]
        group.normals.append(tuple(0.5 * (ni[k] + nj[k]) for k in range(3)))
        group.uvs.append((0.5 * (ulo[0] + uhi[0]), 0.5 * (ulo[1] + uhi[1])))
        group.weights.append(_merge_weights(group.weights[lo], group.weights[hi]))
        midpoints[key] = idx
        return idx

    appended: list[tuple[int, int, int]] = []
    for fi in sorted(touching):
        a, b, c = group.faces[fi]
        uv = lambda v: group.uvs[v]  # noqa: E731 - local alias, keeps it readable
        have = [(min(a, b), max(a, b)) in split_edges,
                (min(b, c), max(b, c)) in split_edges,
                (min(c, a), max(c, a)) in split_edges]
        k = sum(have)
        if k == 0:
            continue
        if k == 3:
            # red split: four triangles
            ab, bc, ca = mid(a, b, uv), mid(b, c, uv), mid(c, a, uv)
            group.faces[fi] = (a, ab, ca)
            appended += [(ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        elif k == 1:
            # green split through one edge: two triangles
            if have[0]:
                m = mid(a, b, uv)
                group.faces[fi] = (a, m, c)
                appended.append((m, b, c))
            elif have[1]:
                m = mid(b, c, uv)
                group.faces[fi] = (b, m, a)
                appended.append((m, c, a))
            else:
                m = mid(c, a, uv)
                group.faces[fi] = (c, m, b)
                appended.append((m, a, b))
        else:
            # two split edges: three triangles, hinged on the vertex between them
            if have[0] and have[1]:          # ab, bc -> hinge at b
                m, n = mid(a, b, uv), mid(b, c, uv)
                group.faces[fi] = (b, n, m)
                appended += [(m, n, a), (n, c, a)]
            elif have[1] and have[2]:        # bc, ca -> hinge at c
                m, n = mid(b, c, uv), mid(c, a, uv)
                group.faces[fi] = (c, n, m)
                appended += [(m, n, b), (n, a, b)]
            else:                            # ca, ab -> hinge at a
                m, n = mid(c, a, uv), mid(a, b, uv)
                group.faces[fi] = (a, n, m)
                appended += [(m, n, c), (n, b, c)]

    group.faces.extend(appended)
    return len(group.verts) - before


def keep_copies_together(group, origin) -> int:
    """Give duplicate vertices (UV seams) the exact same displacement.

    The mesh stores its UV seams as coincident vertex copies with different
    indices. They must move identically or the seam opens into a hairline crack
    — that is what happened when the relaxation, which walks per-index
    neighbours, pulled the two copies of a chest seam apart.

    Copies are matched on their *pre-morph* position (so the test cannot be
    confused by where they ended up). Every copy of a position receives the
    displacement of one representative, applied to its own original point, so
    even copies that were a few microns apart land a few microns apart.
    Returns the number of vertices that were re-synced.
    """
    if len(origin) != len(group.verts):
        return 0
    buckets: dict[tuple[int, int, int], list[int]] = {}
    for i, p in enumerate(origin):
        key = (round(p[0] * 1e4), round(p[1] * 1e4), round(p[2] * 1e4))
        buckets.setdefault(key, []).append(i)
    resynced = 0
    for idx in buckets.values():
        if len(idx) < 2:
            continue
        rep = idx[0]
        ox, oy, oz = origin[rep]
        dx = group.verts[rep][0] - ox
        dy = group.verts[rep][1] - oy
        dz = group.verts[rep][2] - oz
        if dx == 0.0 and dy == 0.0 and dz == 0.0:
            continue
        for i in idx[1:]:
            qx, qy, qz = origin[i]
            group.verts[i] = (qx + dx, qy + dy, qz + dz)
            resynced += 1
    return resynced


# ------------------------------------------------------------------ relaxing

def smooth_region(group, morph: ChestMorph, iterations: int, strength: float,
                  pin_below: float = 0.004) -> int:
    """Laplacian relaxation inside the edited region, boundary pinned.

    A one-to-four split makes the new vertices land on flat triangles, and the
    morph then pushes neighbouring vertices by slightly different amounts; a few
    relaxation steps even that out along the surface instead of leaving the
    facets and the seam sawtooth that the flat-shaded previews showed.

    The relaxation runs on **position-welded** vertices: the mesh stores
    duplicate vertices along its UV seams, and smoothing them as separate nodes
    (different neighbours) pulls the copies apart — that opened hairline cracks
    along the chest seam once the swell stretched them. Welded nodes are
    relaxed once and every copy is written back to the same point, so the seam
    cannot split. Nodes whose morph weight is at or below ``pin_below`` stay
    pinned, so the boundary of the edit cannot drift.
    """
    if iterations <= 0 or strength <= 0.0 or not group.faces:
        return 0
    verts = group.verts
    weld = _weld_keys(verts)
    members: dict[int, list[int]] = {}
    for i in range(len(verts)):
        members.setdefault(weld[i], []).append(i)
    adj: dict[int, set[int]] = {}
    for a, b, c in group.faces:
        wa, wb, wc = weld[a], weld[b], weld[c]
        for x, y in ((wa, wb), (wa, wc), (wb, wa), (wb, wc), (wc, wa), (wc, wb)):
            adj.setdefault(x, set()).add(y)

    movable = {w: morph.weight_at(*verts[idx[0]]) > pin_below
               for w, idx in members.items()}
    if not any(movable.values()):
        return 0
    touched = 0
    for _ in range(iterations):
        pos = {w: verts[idx[0]] for w, idx in members.items()}
        update: dict[int, tuple[float, float, float]] = {}
        for w, nbrs in adj.items():
            if not movable.get(w) or not nbrs:
                continue
            px = py = pz = 0.0
            for nb in nbrs:
                q = pos[nb]
                px += q[0]
                py += q[1]
                pz += q[2]
            n = len(nbrs)
            cur = pos[w]
            update[w] = (cur[0] + strength * (px / n - cur[0]),
                         cur[1] + strength * (py / n - cur[1]),
                         cur[2] + strength * (pz / n - cur[2]))
        for w, p in update.items():
            for i in members[w]:
                verts[i] = p
        touched = len(update)
    return touched


# --------------------------------------------------------------------- normals

def _weld_keys(verts, indices=None) -> dict[int, int]:
    """Map each vertex index to a position-welded group id.

    Position, not index: the mesh stores its UV seams as coincident copies with
    different indices, and everything that must treat them as one point (the
    relaxation, the copy matcher, the normal rebuild) has to key on the position
    the copy pair shares. ``indices`` defaults to every vertex — passing a subset
    used to leave the rest unmapped, which silently split the chest into
    disconnected fragments in the relaxation's adjacency.
    """
    if indices is None:
        indices = range(len(verts))
    keys: dict[tuple[int, int, int], int] = {}
    out: dict[int, int] = {}
    for i in indices:
        x, y, z = verts[i]
        k = (round(x * 1e4), round(y * 1e4), round(z * 1e4))
        out[i] = keys.setdefault(k, len(keys))
    return out


def rebuild_normals(group, morph: ChestMorph) -> None:
    """Rebuild normals over the edited chest and blend them in by strength.

    Area-weighted face normals are accumulated over *position-welded* vertices,
    so a UV seam inside the edited region does not turn into a shading crease.
    The rebuilt normal replaces the source normal proportionally to the morph
    weight (``smoothstep`` of the dome falloff), which leaves the rim of the
    region — and therefore the shading hand-off to the untouched torso — exactly
    as the base build shipped it.
    """
    import numpy as np

    verts = group.verts
    faces = group.faces
    if not faces:
        return
    weld = _weld_keys(verts)
    accum: dict[int, list[float]] = {}
    for a, b, c in faces:
        pa, pb, pc = verts[a], verts[b], verts[c]
        n = np.cross(np.subtract(pb, pa), np.subtract(pc, pa))
        if float(np.linalg.norm(n)) <= 0.0:
            continue
        for vi in (a, b, c):
            slot = accum.setdefault(weld[vi], [0.0, 0.0, 0.0])
            slot[0] += float(n[0])
            slot[1] += float(n[1])
            slot[2] += float(n[2])

    for i, p in enumerate(verts):
        blend = smoothstep(morph.weight_at(*p) * 1.6)
        if blend <= 0.0:
            continue
        raw = accum.get(weld[i])
        if raw is None:
            continue
        nn = np.asarray(raw, dtype=np.float64)
        length = float(np.linalg.norm(nn))
        if length <= 0.0:
            continue
        nn /= length
        ox, oy, oz = group.normals[i]
        bx = ox * (1.0 - blend) + float(nn[0]) * blend
        by = oy * (1.0 - blend) + float(nn[1]) * blend
        bz = oz * (1.0 - blend) + float(nn[2]) * blend
        blen = math.sqrt(bx * bx + by * by + bz * bz)
        if blen <= 1e-9:
            continue
        group.normals[i] = (bx / blen, by / blen, bz / blen)


def morph_groups(groups: dict, morph: ChestMorph | None = None,
                 log=print) -> dict:
    """Run the morph over the TPP groups (body, LOD and shadow caster).

    ``groups`` maps group name -> ``build_models.Group``. The first-person arms
    ship no chest and are left alone. Returns a small report for the build log
    and `BUILD_INFO.json`.
    """
    morph = morph or ChestMorph()
    report: dict = {"morph": morph.describe(), "drawables": {}}
    for name, group in groups.items():
        if name not in ("body", "shadow"):
            continue
        before = len(group.verts)
        moved = morph.apply(group, label=name, log=log)
        report["drawables"][name] = {
            "vertices_moved": moved,
            "vertices_total": len(group.verts),
            "vertices_added": len(group.verts) - before,
        }
        log(f"[bust] group {name}: {moved} of {len(group.verts)} vertices moved")
    return report


def chest_extent(verts, morph: ChestMorph | None = None) -> dict:
    """Front reach of the chest band — the number a cup preset is judged on."""
    morph = morph or ChestMorph()
    best = None
    for x, y, z in verts:
        if morph.weight_at(x, y, z) <= 0.0:
            continue
        if best is None or y > best[1]:
            best = (x, y, z)
    if best is None:
        return {"apex": None}
    return {"apex": [round(best[0], 2), round(best[1], 2), round(best[2], 2)]}


def _open_edges(group) -> list[tuple]:
    """Edges used by exactly one face, on position-welded topology."""
    from collections import defaultdict

    weld = _weld_keys(group.verts)
    count: dict[tuple[int, int], int] = defaultdict(int)
    for a, b, c in group.faces:
        for e in ((a, b), (b, c), (c, a)):
            x, y = weld[e[0]], weld[e[1]]
            count[(min(x, y), max(x, y))] += 1
    return [e for e, n in count.items() if n == 1]
