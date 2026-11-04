"""Chest-mass morph: the geometry half of the `Miranda_Busty_LAS` variant.

`build_busty_variant.py` rebuilds the Miranda LAS outfit through the untouched
`build_models.py` pipeline and then runs this pass over the authored mesh
groups before they are written to Diesel. Nothing here touches the shipped
`dist/Miranda_LAS.zip` route: the pass is only reachable through the variant
builder, which writes its own pack, unit paths and `dist/` archive.

What it does, and why it is shaped this way
-------------------------------------------
The source mesh (measured on `build/pd2-las/miranda.model`) carries the outfit's
chest as a broad, flat-fronted shell: the front surface peaks at y≈20 cm on a
z≈140 cm band whose apex spans |x| 2…11 cm, i.e. one continuous bulge with a
shallow sternum valley rather than two separable breast volumes. A real cup-size
increase therefore has to *grow* mass locally, not scale an existing form.

The morph is a pure function of the bind-pose position::

    two radial domes (one per breast)
      u = (x - sign*APEX_X) / RADIUS_X
      w = (z - APEX_Z) / RADIUS_Z
      r2 = u*u + w*w                       -> 0 at the apex, 1 at the rim
      falloff = (1 - r2)**2                -> C1 (zero slope) at the rim
      front_gate = smoothstep((y - GATE_LO) / (GATE_HI - GATE_LO))
      lat_gate   = smoothstep((X_ZERO - |x|) / (X_ZERO - X_FULL))

    depth   = max(0, y - WALL_Y)           # how far this surface already bulges
    rel     = min(1, depth / (APEX_Y - WALL_Y))
    gain    = cup_gain + round_gain * rel  # cup growth, fuller near the tip
    valley  = 1 - VALLEY * exp(-(x / VALLEY_W)**2)

    dy = falloff * front_gate * lat_gate * gain * depth * valley
    dz = lift   * falloff * front_gate * lat_gate
    dx = spread * (falloff_+x - falloff_-x) * front_gate * lat_gate

Properties that make this safe for a shipped pack:

* **Continuous everywhere.** Every term is a polynomial (or smoothstep) of the
  vertex position and the outermost term vanishes with zero slope at ``r2 = 1``,
  so there is no crease, step or tear at the boundary of the edited region.
* **Touches only the chest surface.** The forward gate means the back of the
  torso (``y < GATE_LO``) is untouched, and ``r2 >= 1`` excludes the shoulders,
  the neckline (``z > 148.8``), the under-bust ribcage (``z < 131``) and the
  neck/chin of the head block that shares the shadow-caster drawable.
* **Sign-safe by construction.** ``dx`` sums a positive-x dome minus a
  negative-x dome, so it is exactly zero on the midline (the sternum valley is
  preserved, not blurred across).
* **Same function on every drawable.** ``g_body``, ``g_body_lod1`` and the body
  block of ``s_body`` hold bit-identical positions (verified in tests), so
  running the same position-driven pass on each keeps the shadow caster and the
  LOD exactly aligned with the visible mesh.

Normals are rebuilt for the moved vertices (area-weighted, position-welded so
UV seams do not split into a crease) and blended back into the source normals by
the same falloff, so the rim of the edited region keeps the original shading.
"""

from __future__ import annotations

import math

#: Breast apex, measured on the authored mesh (cm, z-up, +y is the front). The
#: front surface peaks at y≈20 cm on a band centred at z≈140, |x| 2…11.
APEX_X = 6.0
APEX_Z = 141.5
#: Radial extent of the dome. The ellipse covers the measured apex plateau
#: (|x| 2…11, z 132…148) with room for the falloff; ``(1 - r2)**2`` keeps the
#: outermost ~20% of that radius nearly still so the rim never creases.
RADIUS_X = 6.6
RADIUS_Z = 10.6
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
GATE_LO = 7.5
GATE_HI = 15.5
#: Lateral gate: the underarm seam and the outer torso edge stay exactly where
#: the base build put them, so the arms cannot be caught by the swell.
X_FULL = 10.0
X_ZERO = 12.2
#: Cleavage: fraction of the *added* forward push removed on the midline. The
#: source chest is a single convex shell (sternum valley only ~0.6 cm deep), so
#: without this the enlarged chest reads as one barrel instead of two breasts.
VALLEY = 0.85
VALLEY_W = 1.6
#: Hard safety ceiling: no other body part lives between the dome rim (z≈149)
#: and the head, so this only ever guards the shared shadow-caster vertex block.
Z_CEILING = 152.0

#: Cup-size preset. ``cup_gain`` multiplies the forward protrusion measured from
#: the chest wall, ``round_gain`` adds extra growth near the apex (a fuller,
#: rounder breast rather than a scaled copy of the flat source shell), ``lift``
#: raises the mass and ``spread`` pushes each breast away from the sternum.
#:
#: cup_gain 0.5 on a ~15 cm apex-to-wall depth grows the apex by ~7.5 cm: about
#: two cup sizes up from the source figure, with the silhouette still reading as
#: the same character rather than a caricature.
DEFAULT_CUP_GAIN = 0.50
DEFAULT_ROUND_GAIN = 0.12
DEFAULT_LIFT = 0.7
DEFAULT_SPREAD = 1.2
DEFAULT_VALLEY = VALLEY


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
                 valley: float = DEFAULT_VALLEY):
        for name, value in (("cup_gain", cup_gain), ("round_gain", round_gain),
                            ("lift", lift), ("spread", spread)):
            if value < 0.0:
                raise ValueError(f"ChestMorph {name} must be non-negative")
        if not 0.0 <= valley <= 1.0:
            raise ValueError("ChestMorph valley must be within [0, 1]")
        self.cup_gain = float(cup_gain)
        self.round_gain = float(round_gain)
        self.lift = float(lift)
        self.spread = float(spread)
        self.valley = float(valley)

    # ---------------------------------------------------------------- profile
    def weight(self, x: float, z: float, side: int) -> float:
        """Radial falloff of the breast centred at ``side * APEX_X``."""
        u = (x - side * APEX_X) / RADIUS_X
        w = (z - APEX_Z) / RADIUS_Z
        r2 = u * u + w * w
        if r2 >= 1.0:
            return 0.0
        d = 1.0 - r2
        return d * d

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
        if z >= Z_CEILING:
            return (0.0, 0.0, 0.0)
        w_pos = self.weight(x, z, +1)
        w_neg = self.weight(x, z, -1)
        if w_pos == 0.0 and w_neg == 0.0:
            return (0.0, 0.0, 0.0)
        gate = self.front_gate(y) * self.lateral_gate(x)
        if gate == 0.0:
            return (0.0, 0.0, 0.0)
        fall = (w_pos + w_neg) * gate
        depth = max(0.0, y - WALL_Y)
        rel = min(1.0, depth / (APEX_Y - WALL_Y))
        gain = self.cup_gain + self.round_gain * rel
        dy = fall * gain * depth * self.valley_factor(x)
        dz = self.lift * fall
        dx = self.spread * (w_pos - w_neg) * gate
        return (dx, dy, dz)

    def weight_at(self, x: float, y: float, z: float) -> float:
        """Normalised edit strength in ``[0, 1]``, used to blend shading."""
        if z >= Z_CEILING:
            return 0.0
        return min(1.0, (self.weight(x, z, +1) + self.weight(x, z, -1))
                   * self.front_gate(y) * self.lateral_gate(x))

    # ------------------------------------------------------------------ apply
    def apply(self, group, materials=("miranda_body",)) -> int:
        """Move the chest vertices of one authored group; returns the count.

        ``group`` is a ``build_models.Group``; ``materials`` selects the slices
        to edit (the shadow-caster group holds the head materials too, and those
        must not be touched even if a vertex were inside the dome).
        """
        moved = 0
        touched_verts: list[int] = []
        for mat, base_v, _base_i, _tris, nverts in group.slices:
            if materials is not None and mat not in materials:
                continue
            for i in range(base_v, base_v + nverts):
                x, y, z = group.verts[i]
                dx, dy, dz = self.displacement(x, y, z)
                if dx == 0.0 and dy == 0.0 and dz == 0.0:
                    continue
                group.verts[i] = (x + dx, y + dy, z + dz)
                touched_verts.append(i)
                moved += 1
        if touched_verts:
            rebuild_normals(group, self, touched_verts)
        return moved

    # ----------------------------------------------------------------- checks
    def apex(self) -> tuple[float, float]:
        """Approximate forward reach at the apex, for logs and assertions."""
        return (APEX_X, WALL_Y)

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
            "radius_z_cm": RADIUS_Z,
            "wall_y_cm": WALL_Y,
            "gate_y_cm": [GATE_LO, GATE_HI],
            "gate_x_cm": [X_FULL, X_ZERO],
        }


# --------------------------------------------------------------------- normals

def _weld_keys(verts, indices):
    """Map each vertex index to a position-welded group id."""
    keys: dict[tuple[int, int, int], int] = {}
    out = {}
    for i in indices:
        x, y, z = verts[i]
        # 0.1 mm buckets: far below the smallest mesh feature, far above the
        # float noise the retarget leaves in shared seam positions
        k = (round(x * 1e4), round(y * 1e4), round(z * 1e4))
        out[i] = keys.setdefault(k, len(keys))
    return out


def rebuild_normals(group, morph: ChestMorph, touched: list[int]) -> None:
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
    weld_all = _weld_keys(verts, range(len(verts)))
    accum: dict[int, list[float]] = {}
    for a, b, c in faces:
        pa, pb, pc = verts[a], verts[b], verts[c]
        n = np.cross(np.subtract(pb, pa), np.subtract(pc, pa))
        norm = float(np.linalg.norm(n))
        if norm <= 0.0:
            continue
        for vi in (a, b, c):
            gid = weld_all[vi]
            slot = accum.get(gid)
            if slot is None:
                accum[gid] = [float(n[0]), float(n[1]), float(n[2])]
            else:
                slot[0] += float(n[0])
                slot[1] += float(n[1])
                slot[2] += float(n[2])

    for i in touched:
        raw = accum.get(weld_all[i])
        if raw is None:
            continue
        nn = np.asarray(raw, dtype=np.float64)
        length = float(np.linalg.norm(nn))
        if length <= 0.0:
            continue
        nn /= length
        x, y, z = verts[i]
        blend = smoothstep(morph.weight_at(x, y, z) * 2.5)
        if blend <= 0.0:
            continue
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
        moved = morph.apply(group)
        report["drawables"][name] = {"vertices_moved": moved,
                                     "vertices_total": len(group.verts)}
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
