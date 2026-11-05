"""Chest-mass morph: the geometry half of the `Miranda_Busty_LAS` variant.

`build_busty_variant.py` rebuilds the Miranda LAS outfit through the untouched
`build_models.py` pipeline and then runs this pass over the authored mesh
groups before they are written to Diesel. Nothing here touches the shipped
`dist/Miranda_LAS.zip` route: the pass is only reachable through the variant
builder, which writes its own pack, unit paths and `dist/` archive.

Sculpt & topology architecture
------------------------------
Measured on the authored mesh (z-up, cm, +y is the front), Miranda's Cerberus
catsuit has a modelled 3D piping bevel (~0.55 cm wide) framing the chest panel:
an inframammary underbust seam at ``z ≈ 135.0–135.6``, vertical side piping at
``|x| ≈ 8.0–8.6``, and an upper-chest seam at ``z ≈ 146.3–147.0``, with the
base breast mound peaking at ``y = 19.98 cm`` near ``(|x| ≈ 5.6, z ≈ 140.0)``
and spanning laterally out to ``|x| ≈ 10.8 cm``.

Four design choices keep the enlarged bust anatomically natural and free of
cone/shelf artifacts or UV/piping distortion:

1. **Welded edge-length local subdivision.** Edges inside the chest region
   longer than ``MAX_CHEST_EDGE_CM`` are split in lockstep across
   position-welded vertices (preserving per-island UVs on seams while leaving
   short ~0.55 cm cross-piping steps intact so no micro-triangles fold).
2. **3D radial-spherical teardrop expansion (not a 1D ``+y`` push).** Pushing
   chest vertices purely along ``+y`` stretches a ~4.5 cm hemisphere into a
   horizontal beak at 60°/90°. Instead, combining a wide super-ellipsoid
   profile ``(1 - r^p)^q`` (``p ≈ 3.3`` across the front/lower cup, easing to
   ``p ≈ 1.8`` on the upper slope) with bounded radial ``dz`` and ``dx``
   expansion around the mammary root rounds the lower pole downward toward the
   ``z ≈ 135.0`` inframammary fold and broadens the upper-front arc into a true
   D-shaped spherical cup, with zero bulge on the abdomen below ``z = 134.2``.
3. **Taut catsuit sternum contour.** Soft-union blending of the left/right cups
   plus a localized sternum contour deepens cleavage between the mounds while
   keeping the taut stretch-fabric bridge of Miranda's zipped hex catsuit.
4. **Feature-preserving normal-projected fairing.** Laplacian offsets over
   position-welded neighbours are projected onto the smooth surface normal
   (zero tangential UV sliding) and attenuated across pre-existing 3D piping
   bevels on ``origin``, eliminating flat base-mesh facets on the smooth cup
   while keeping the suit's tailored seams crisp.
"""

from __future__ import annotations

import math

#: Breast apex, aligned with the anatomical breast mound centre (cm).
APEX_X = 5.05
APEX_Z = 140.95
#: Internal radial expansion pivot (cm), aligned with ``APEX_Z``.
RADIAL_Z = 140.95
RADIAL_X = 5.05
RADIAL_Z_LO = 132.2
RADIAL_Z_HI = 150.8
#: Nominal symmetric lateral radius (kept for introspection compatibility;
#: actual profile crossfades ``RADIUS_X_IN`` and ``RADIUS_X_OUT``).
RADIUS_X = 7.15
#: Wide, balanced lateral radii (cm) paired with variable-exponent dome
#: ``(1 - rho)^(0.78 + 0.47*rho)`` so each breast forms a broad, blunt
#: spherical dome ``(    )(    )`` curving smoothly across ``|x| = 1..9.5``
#: with C-infinity rim continuity and <1.78x edge/UV stretch everywhere.
RADIUS_X_IN = 7.30
RADIUS_X_OUT = 7.00
#: Asymmetric vertical radii (cm) for forward ``+dy`` protrusion:
#: ``140.95 - 6.16 * 1.12 = 134.05 cm`` (strictly above the stomach/ribcage);
#: ``140.95 + 8.85 * 1.12 = 150.86 cm`` (gentle upper-chest taper, strictly
#: below ``HEAD_Z = 152.0`` and gentle across the ``z ≈ 146.2`` collar lip).
RADIUS_Z_UP = 8.85
RADIUS_Z_DOWN = 6.16
SOFT_SCALE = 1.12
SOFT_WEIGHT = 0.24
SOFT_POWER = 1.85
#: Smooth variable-exponent hemisphere ``(1 - rho)^(q_lo + (q_hi - q_lo)*rho)``:
#: - Near ``rho = 0`` (apex), ``q ≈ 0.78`` matches a blunt Euclidean sphere
#:   (zero parabolic cone tip!).
#: - Near ``rho = 1`` (collar & inframammary rim), ``q ≈ 1.25..1.40`` eases to
#:   zero smoothly (<7.5%-peak/0.25cm step and <1.78x UV stretch everywhere).
CUP_P_X = 3.20
CUP_P_X_DOME = 2.45
CUP_P_LOWER = 1.98
CUP_P_UPPER = 1.88
CUP_Q_LOWER = 0.78
CUP_Q_UPPER = 1.25
#: Gentle C2 medial union for taut catsuit tension across two distinct cups.
MEDIAL_OVERLAP = 0.11
#: Legacy constant retained for report/introspection compatibility.
DOME_POWER = 1.35
#: Saturation depth on the front chest & spine/ribcage depth pivot (cm).
APEX_Y = 14.4
WALL_Y = 2.6
#: Forward gate (cm): 0 on the back (``y <= 5.15``), ramping smoothly across
#: ``y = 5.15..11.0``.
GATE_LO = 5.15
GATE_HI = 11.0
#: Lateral gate (cm): full across the pectoral root, 0 before the arm seam.
X_FULL = 11.0
X_ZERO = 13.4
#: Soft taut-catsuit sternum contour (``~0.65-0.85 cm`` smooth U-curve between
#: the two wide hemispheres — neither a narrow V-crease nor a flat monoboob).
VALLEY = 0.145
VALLEY_W = 2.25
#: Safety ceiling & collar guard (cm).
Z_CEILING = 151.8
CEILING_FADE = 2.8
HEAD_Z = 152.0
#: Half-width (cm) of the medial/lateral radius crossfade.
RADIUS_BLEND = 3.0
#: Editable vertical chest band (cm), easing smoothly to zero at both ends.
BAND_LO = 131.2
BAND_HI = 151.7
BAND_FADE_LO = 1.8
BAND_FADE_HI = 1.6

#: Default sculpt preset: two symmetric, smooth spherical hemispheres ``(   )(   )``.
DEFAULT_CUP_GAIN = 0.382
DEFAULT_ROUND_GAIN = 0.046
DEFAULT_LIFT = 0.18
DEFAULT_SPREAD = 0.34
DEFAULT_ROOT_GAIN = 0.70
DEFAULT_ROOT_SPREAD = 0.42
DEFAULT_VALLEY = VALLEY

#: Local subdivision & 3-ring normal-projected polish.
SUBDIVIDE_MARGIN = 1.34
SUBDIVIDE_Z = (132.5, 151.0)
MAX_EDGE_UV_DISTANCE = 0.20
MAX_CHEST_EDGE_CM = 0.25
DEFAULT_SUBDIVISIONS = 2
DEFAULT_SMOOTH_ITERATIONS = 13
DEFAULT_SMOOTH_STRENGTH = 0.32


def smoothstep(t: float) -> float:
    """Cubic Hermite ramp on ``[0, 1]`` with zero first derivative at ends."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def smootherstep(t: float) -> float:
    """Quintic Perlin ramp on ``[0, 1]`` with zero 1st and 2nd derivatives."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


class ChestMorph:
    """Position-driven 3D radial-spherical chest sculpt for Miranda's outfit."""

    def __init__(self, cup_gain: float = DEFAULT_CUP_GAIN,
                 round_gain: float = DEFAULT_ROUND_GAIN,
                 lift: float = DEFAULT_LIFT,
                 spread: float = DEFAULT_SPREAD,
                 valley: float = DEFAULT_VALLEY,
                 root_gain: float = DEFAULT_ROOT_GAIN,
                 root_spread: float = DEFAULT_ROOT_SPREAD,
                 subdivisions: int = DEFAULT_SUBDIVISIONS,
                 smooth_iterations: int = DEFAULT_SMOOTH_ITERATIONS,
                 smooth_strength: float = DEFAULT_SMOOTH_STRENGTH):
        for name, value in (("cup_gain", cup_gain), ("round_gain", round_gain),
                            ("lift", lift), ("spread", spread),
                            ("root_gain", root_gain), ("root_spread", root_spread)):
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
        self.root_gain = float(root_gain)
        self.root_spread = float(root_spread)
        self.subdivisions = int(subdivisions)
        self.smooth_iterations = int(smooth_iterations)
        self.smooth_strength = float(smooth_strength)

    # ---------------------------------------------------------------- profile
    def _radial_x(self, x: float, side: int) -> float:
        """C2 crossfade between medial (``RADIUS_X_IN``) and lateral radius."""
        dx = (x - side * APEX_X) * side
        t = smootherstep((dx + RADIUS_BLEND) / (2.0 * RADIUS_BLEND))
        return RADIUS_X_IN + (RADIUS_X_OUT - RADIUS_X_IN) * t

    def _cup_profile(self, x: float, z: float, side: int) -> float:
        """C-infinity variable-exponent sphere ``(1 - rho)^(q_lo + dq*rho)``."""
        u = abs(x - side * APEX_X) / self._radial_x(x, side)
        rz = RADIUS_Z_UP if z > APEX_Z else RADIUS_Z_DOWN
        w = (z - APEX_Z) / rz
        up_t = smootherstep(max(0.0, (w - 0.15) / 0.65))
        pz = CUP_P_LOWER + (CUP_P_UPPER - CUP_P_LOWER) * up_t
        rho = (u ** CUP_P_X_DOME) + (abs(w) ** pz)
        if rho >= 1.0:
            return 0.0
        q_base = CUP_Q_LOWER + (CUP_Q_UPPER - CUP_Q_LOWER) * rho
        q = q_base + 0.15 * up_t
        return (1.0 - rho) ** q

    def _soft_profile(self, x: float, z: float, side: int) -> float:
        """Subtle C2 cushion blending the cup rim into the surrounding chest."""
        u = (x - side * APEX_X) / (self._radial_x(x, side) * SOFT_SCALE)
        rz = (RADIUS_Z_UP if z > APEX_Z else RADIUS_Z_DOWN) * SOFT_SCALE
        w = (z - APEX_Z) / rz
        r2 = u * u + w * w
        if r2 >= 1.0:
            return 0.0
        return (1.0 - r2) ** SOFT_POWER

    def weight(self, x: float, z: float, side: int) -> float:
        """Composite normalized dome weight in ``[0, 1]`` for side ``+1`` or ``-1``."""
        main = self._cup_profile(x, z, side)
        soft = self._soft_profile(x, z, side)
        return (main + SOFT_WEIGHT * soft) / (1.0 + SOFT_WEIGHT)

    def _combined_dome(self, w_pos: float, w_neg: float) -> float:
        """Smooth C1/C2 arch union across the left and right Euclidean hemispheres."""
        hi = 0.5 * (w_pos + w_neg + math.sqrt((w_pos - w_neg) ** 2 + 0.0036)) - 0.03
        lo = 0.5 * (w_pos + w_neg - math.sqrt((w_pos - w_neg) ** 2 + 0.0036)) + 0.03
        return min(1.0, max(0.0, hi) + MEDIAL_OVERLAP * max(0.0, lo))

    def front_gate(self, y: float) -> float:
        """1 on the front chest surface, 0 behind the chest wall / flanks."""
        return smootherstep((y - GATE_LO) / (GATE_HI - GATE_LO))

    def lateral_gate(self, x: float) -> float:
        """1 across the cup, 0 at and beyond the underarm/sleeve seam."""
        return smootherstep((X_ZERO - abs(x)) / (X_ZERO - X_FULL))

    def valley_factor(self, x: float, z: float | None = None) -> float:
        """Gentle taut-catsuit saddle: smooth over suit fabric, softer on keyhole."""
        v_depth = self.valley
        if z is not None:
            suit_env = smootherstep((z - 135.8) / 2.4) * smootherstep((145.6 - z) / 2.6)
            skin_env = smootherstep((z - 146.2) / 1.8) * smootherstep((150.8 - z) / 2.0)
            v_depth = self.valley * (0.35 + 0.65 * suit_env) + 0.05 * skin_env
        return 1.0 - v_depth * math.exp(-(x / VALLEY_W) ** 2)

    def band(self, z: float) -> float:
        """C2 vertical chest band guard, strictly zero outside ``[BAND_LO, BAND_HI]``."""
        lo = smootherstep((z - BAND_LO) / BAND_FADE_LO)
        hi = smootherstep((BAND_HI - z) / BAND_FADE_HI)
        return lo * hi

    def ceiling(self, x: float, z: float) -> float:
        """Soft horizontal upper bound (no x-dip so collar borders stay straight)."""
        return smootherstep((Z_CEILING - z) / CEILING_FADE)

    def _horizontal_cup(self, x: float) -> float:
        """Pure lateral cup envelope in ``[0, 1]`` for radial ``dz`` scaling."""
        best = 0.0
        for side in (+1, -1):
            u = abs(x - side * APEX_X) / (self._radial_x(x, side) * SOFT_SCALE)
            if u < 1.0:
                best = max(best, (1.0 - (u ** CUP_P_X)) ** 1.5)
        return best

    def _root_bells(self, x: float, y: float, z: float) -> float:
        """Posterior/lateral breast-root bell for parts closer to the spine.

        Targets the lateral & posterior breast root (``y ≈ 5.3..18.5``,
        ``|x| ≈ 5.8..13.4``) where the breast attaches to the ribcage closer to
        the spine, expanding it in one continuous convex C-arc (outward ``±dx``
        and forward ``+dy``) while staying strictly zero on the front meridian
        (``|x| < 5.8``) so the 60°/90° upper-cup profile remains inflection-free.
        """
        rz = RADIUS_Z_UP if z > APEX_Z else RADIUS_Z_DOWN
        wz = abs(z - APEX_Z) / rz
        if wz >= 1.0:
            return 0.0
        z_bell = (1.0 - (wz ** 2.4)) ** 1.85

        y_side = smootherstep((y - 5.3) / 3.5) * (1.0 - smootherstep((y - 14.5) / 4.2))
        x_side = smootherstep((abs(x) - 5.8) / 3.6) * smootherstep((13.4 - abs(x)) / 1.4)
        return y_side * x_side * z_bell

    def displacement(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        """Bind-pose displacement ``(dx, dy, dz)`` for a vertex at ``(x, y, z)`` (cm)."""
        if z >= HEAD_Z:
            return (0.0, 0.0, 0.0)
        band = self.band(z)
        if band == 0.0:
            return (0.0, 0.0, 0.0)
        ceil = self.ceiling(x, z) * band
        if ceil == 0.0:
            return (0.0, 0.0, 0.0)
        fg = self.front_gate(y)
        lg = self.lateral_gate(x)
        gate = fg * lg
        if gate == 0.0:
            return (0.0, 0.0, 0.0)

        w_pos = self.weight(x, z, +1)
        w_neg = self.weight(x, z, -1)
        hx = self._horizontal_cup(x)
        side_root = self._root_bells(x, y, z)
        if w_pos == 0.0 and w_neg == 0.0 and hx == 0.0 and side_root == 0.0:
            return (0.0, 0.0, 0.0)

        env = gate * ceil
        dome = self._combined_dome(w_pos, w_neg)
        fall = dome * env
        v_fac = self.valley_factor(x, z)
        cap_v = dome * v_fac

        raw_depth = max(0.0, y - WALL_Y)
        ref_depth = APEX_Y - WALL_Y
        eff_depth = min(raw_depth, ref_depth)
        rel = min(1.0, raw_depth / ref_depth)

        # Blend 76% constant-curvature twin-sphere target projection (from
        # smooth_pass7, which replaces the rectangular suit-flap box and
        # +0.65 cm right-flap asymmetry with two true circular sphere caps and
        # zero collar scar) + 24% proportional depth push for subtle relief.
        gain_scale = (self.cup_gain + self.round_gain * rel) / (
            DEFAULT_CUP_GAIN + DEFAULT_ROUND_GAIN
        )
        # Symmetric twin-sphere target projection: equalizes Miranda's +0.63 cm
        # right-flap plateau (y ≈ 19.98 vs 19.35) while keeping sph_gate flat
        # across the front chest (y >= 13.8) so underbust/collar hexes stay <1.78x.
        excess_y = 0.5 * ((y - 18.50) + math.sqrt((y - 18.50) ** 2 + 0.25))
        sph_amp = max(
            0.70 * gain_scale,
            5.10 * gain_scale - 0.86 * excess_y * min(1.0, gain_scale),
        )
        collar_taper = 1.0 - 0.22 * smootherstep((z - 145.0) / 3.8)
        sph_gate = smootherstep((y - 9.0) / 4.8) * collar_taper
        sph_pull = sph_amp * cap_v * sph_gate
        base_push = (
            (self.cup_gain + self.round_gain * rel)
            * eff_depth
            * cap_v
            * collar_taper
        )

        root_dy = self.root_gain * side_root * env
        dy = env * (0.86 * sph_pull + 0.14 * base_push) + root_dy

        # Wide-support fold-free vertical radial expansion, kept even across
        # the arch (`v_lat = 0.92 + 0.08 * v_fac`) so the underbust never
        # droops into twin hanging spikes in Bottom 48° views:
        dz = 0.0
        if hx > 0.0 and self.lift > 0.0 and RADIAL_Z_LO < z < RADIAL_Z_HI:
            v_lat = 0.92 + 0.08 * v_fac
            if z < RADIAL_Z:
                u_dn = (RADIAL_Z - z) / (RADIAL_Z - RADIAL_Z_LO)
                dz = -self.lift * (6.5 * u_dn * ((1.0 - u_dn) ** 2.3)) * hx * v_lat * env
            else:
                u_up = (z - RADIAL_Z) / (RADIAL_Z_HI - RADIAL_Z)
                dz = +(0.85 * self.lift) * (6.5 * u_up * ((1.0 - u_up) ** 2.3)) * hx * v_lat * env

        # Outward-only horizontal rounding + spine-root fullness (never pinching
        # |x| < RADIAL_X inward into /\ /\ cones; strictly 0 on x=0):
        if abs(x) < 1e-12 or (fall == 0.0 and side_root == 0.0):
            dx = 0.0
        else:
            sign = 1.0 if x > 0.0 else -1.0
            outer_guard = smootherstep((13.35 - abs(x)) / 1.45)
            x_arm = smootherstep((abs(x) - 2.4) / 5.6)
            dx = sign * outer_guard * (
                self.spread * x_arm * fall
                + self.root_spread * side_root * env
            )

        return (dx, dy, dz)

    def weight_at(self, x: float, y: float, z: float) -> float:
        """Normalised edit strength in ``[0, 1]``, strictly zero outside the band."""
        if z >= HEAD_Z:
            return 0.0
        b = self.band(z)
        if b == 0.0:
            return 0.0
        c = self.ceiling(x, z) * b
        if c == 0.0:
            return 0.0
        dome = self._combined_dome(self.weight(x, z, +1), self.weight(x, z, -1))
        side_root = self._root_bells(x, y, z)
        z_rad_wt = 0.0
        if RADIAL_Z_LO < z < RADIAL_Z_HI:
            if z < RADIAL_Z:
                u = (RADIAL_Z - z) / (RADIAL_Z - RADIAL_Z_LO)
            else:
                u = (z - RADIAL_Z) / (RADIAL_Z_HI - RADIAL_Z)
            z_rad_wt = 0.35 * (6.5 * u * ((1.0 - u) ** 2.3)) * self._horizontal_cup(x)
        root_wt = 0.65 * side_root
        return min(1.0, max(dome, z_rad_wt, root_wt) * self.front_gate(y) * self.lateral_gate(x) * c)

    def in_region(self, x: float, y: float, z: float) -> bool:
        """Whether a position lies inside the local chest subdivision patch."""
        if not (SUBDIVIDE_Z[0] <= z <= SUBDIVIDE_Z[1]):
            return False
        if abs(x) > X_ZERO or y < 8.0:
            return False
        for side in (+1, -1):
            u = (x - side * APEX_X) / (self._radial_x(x, side) * SUBDIVIDE_MARGIN)
            rz = (RADIUS_Z_UP if z > APEX_Z else RADIUS_Z_DOWN) * SUBDIVIDE_MARGIN
            w = (z - APEX_Z) / rz
            if u * u + w * w < 1.0:
                return True
        return False

    # ------------------------------------------------------------------ apply
    def apply(self, group, materials=("miranda_body",), subdivide: bool = True,
              label: str | None = None, log=None, stats: dict | None = None) -> int:
        """Subdivide, displace, normal-project fair, unfold, and re-shade one group.

        ``stats``, when given, receives the repair counters (``vertices_faired`` and
        ``faces_inverted``) so callers can report or assert on them.
        """
        if stats is not None:
            stats.setdefault("vertices_faired", 0)
            stats.setdefault("faces_inverted", 0)
        if subdivide and self.subdivisions and getattr(group, "faces", None):
            added = subdivide_region(group, self, levels=self.subdivisions,
                                     materials=materials)
            if log and added:
                log(f"[bust] {label or group.name}: +{added} chest vertices "
                    f"(local subdivision)")
        origin = list(group.verts)
        moved = self.displace(group, materials)
        if moved:
            smooth_region(group, self, self.smooth_iterations,
                          self.smooth_strength, origin=origin,
                          materials=materials)
            keep_copies_together(group, origin)
            folds = unfold_region(group, origin)
            if stats is not None or log:
                left = len(inverted_faces(group.verts, group.faces, origin))
                if stats is not None:
                    stats["vertices_faired"] = folds
                    stats["faces_inverted"] = left
                if log and folds:
                    log(f"[bust] {label or group.name}: faired {folds} vertices "
                        f"that folded the keyhole lip"
                        + (f" ({left} faces still inverted)" if left else ""))
            rebuild_normals(group, self, materials=materials)
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
            "root_gain_cm": self.root_gain,
            "root_spread_cm": self.root_spread,
            "valley": self.valley,
            "apex_x_cm": APEX_X,
            "apex_z_cm": APEX_Z,
            "radial_pivot_cm": [RADIAL_X, RADIAL_Z],
            "radius_x_cm": [RADIUS_X_OUT, RADIUS_X_IN],
            "radius_z_cm": [RADIUS_Z_DOWN, RADIUS_Z_UP],
            "soft_scale": SOFT_SCALE,
            "soft_weight": SOFT_WEIGHT,
            "cup_p": [CUP_P_LOWER, CUP_P_UPPER],
            "cup_q": [CUP_Q_LOWER, CUP_Q_UPPER],
            "wall_y_cm": WALL_Y,
            "gate_y_cm": [GATE_LO, GATE_HI],
            "gate_x_cm": [X_FULL, X_ZERO],
            "band_z_cm": [BAND_LO, BAND_HI],
            "subdivisions": self.subdivisions,
            "max_chest_edge_cm": MAX_CHEST_EDGE_CM,
            "smooth": [self.smooth_iterations, self.smooth_strength],
        }


# --------------------------------------------------------------- subdivision

def _selected_vertex_set(group, materials) -> set[int] | None:
    """Vertex index set covered by ``materials`` (``None`` means all vertices)."""
    if materials is None or not getattr(group, "slices", None):
        return None
    allowed: set[int] = set()
    for mat, base_v, _base_i, _tris, nverts in group.slices:
        if mat in materials:
            allowed.update(range(base_v, base_v + nverts))
    return allowed


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
    """True when one of the triangle's edges spans a disjoint texture island."""
    if not uvs:
        return False
    a, b, c = tri
    return (_uv_distance(uvs[a], uvs[b]) > MAX_EDGE_UV_DISTANCE
            or _uv_distance(uvs[b], uvs[c]) > MAX_EDGE_UV_DISTANCE
            or _uv_distance(uvs[c], uvs[a]) > MAX_EDGE_UV_DISTANCE)


def _edge_length(verts, i: int, j: int) -> float:
    a, b = verts[i], verts[j]
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def subdivide_region(group, morph: ChestMorph, levels: int = 1,
                     materials=("miranda_body",),
                     max_edge_cm: float = MAX_CHEST_EDGE_CM) -> int:
    """Refine chest edges longer than ``max_edge_cm`` across welded topology."""
    if not getattr(group, "slices", None) or not getattr(group, "faces", None):
        return 0
    mat, base_v, base_i, tris, _nverts = group.slices[-1]
    if materials is not None and mat not in materials:
        return 0
    first = base_i // 3
    if tris <= 0:
        return 0

    has_uvs = bool(getattr(group, "uvs", None)) and len(group.uvs) == len(group.verts)
    has_weights = bool(getattr(group, "weights", None)) and len(group.weights) == len(group.verts)

    added_total = 0
    for _level in range(levels):
        last = first + group.slices[-1][3]
        weld = _weld_keys(group.verts)
        rep_pos: dict[int, tuple[float, float, float]] = {}
        for idx, wid in weld.items():
            if wid not in rep_pos:
                rep_pos[wid] = group.verts[idx]

        bad_wedges: set[tuple[int, int]] = set()
        if has_uvs:
            for fi in range(first, last):
                tri = group.faces[fi]
                if _crosses_uv_seam(group.uvs, tri):
                    a, b, c = tri
                    for u, v in ((a, b), (b, c), (c, a)):
                        bad_wedges.add((min(weld[u], weld[v]), max(weld[u], weld[v])))

        split_wedges: set[tuple[int, int]] = set()
        edge_thresh = 0.35 if _level == 0 else max_edge_cm
        for fi in range(first, last):
            a, b, c = group.faces[fi]
            for u, v in ((a, b), (b, c), (c, a)):
                we = (min(weld[u], weld[v]), max(weld[u], weld[v]))
                if we[0] == we[1] or we in bad_wedges:
                    continue
                if _edge_length(group.verts, u, v) <= edge_thresh:
                    continue
                pu, pv = rep_pos[we[0]], rep_pos[we[1]]
                mx = 0.5 * (pu[0] + pv[0])
                my = 0.5 * (pu[1] + pv[1])
                mz = 0.5 * (pu[2] + pv[2])
                if morph.in_region(mx, my, mz) or (
                    morph.in_region(*pu) and morph.in_region(*pv)
                ):
                    split_wedges.add(we)

        if not split_wedges:
            break

        before_v = len(group.verts)
        midpoints: dict[tuple, int] = {}

        def get_mid(u: int, v: int) -> int:
            lo, hi = (u, v) if u < v else (v, u)
            if has_uvs:
                ulo, uhi = group.uvs[lo], group.uvs[hi]
                key = (lo, hi, round(ulo[0] * 4096), round(ulo[1] * 4096),
                       round(uhi[0] * 4096), round(uhi[1] * 4096))
            else:
                ulo = uhi = (0.0, 0.0)
                key = (lo, hi)
            got = midpoints.get(key)
            if got is not None:
                return got
            wlo, whi = min(weld[lo], weld[hi]), max(weld[lo], weld[hi])
            p0, p1 = rep_pos[wlo], rep_pos[whi]
            idx = len(group.verts)
            group.verts.append((0.5 * (p0[0] + p1[0]),
                                0.5 * (p0[1] + p1[1]),
                                0.5 * (p0[2] + p1[2])))
            n0, n1 = group.normals[lo], group.normals[hi]
            # the average of two unit normals is shorter than 1, and midpoints outside the morph's
            # weight region never reach rebuild_normals(): normalise here or the mesh ships
            # non-unit normals (12 of them did, down to 0.9867)
            nlen = math.sqrt((n0[0] + n1[0]) ** 2 + (n0[1] + n1[1]) ** 2 + (n0[2] + n1[2]) ** 2)
            if nlen > 1e-9:
                group.normals.append(((n0[0] + n1[0]) / nlen,
                                      (n0[1] + n1[1]) / nlen,
                                      (n0[2] + n1[2]) / nlen))
            else:
                group.normals.append((0.0, 1.0, 0.0))
            if has_uvs:
                group.uvs.append((0.5 * (ulo[0] + uhi[0]),
                                  0.5 * (ulo[1] + uhi[1])))
            if has_weights:
                group.weights.append(_merge_weights(group.weights[lo],
                                                    group.weights[hi]))
            midpoints[key] = idx
            return idx

        appended: list[tuple[int, int, int]] = []
        for fi in range(first, last):
            a, b, c = group.faces[fi]
            eab = (min(weld[a], weld[b]), max(weld[a], weld[b])) in split_wedges
            ebc = (min(weld[b], weld[c]), max(weld[b], weld[c])) in split_wedges
            eca = (min(weld[c], weld[a]), max(weld[c], weld[a])) in split_wedges
            k = eab + ebc + eca
            if k == 0:
                continue
            if k == 3:
                ab, bc, ca = get_mid(a, b), get_mid(b, c), get_mid(c, a)
                group.faces[fi] = (a, ab, ca)
                appended += [(ab, b, bc), (ca, bc, c), (ab, bc, ca)]
            elif k == 1:
                if eab:
                    m = get_mid(a, b)
                    group.faces[fi] = (a, m, c)
                    appended.append((m, b, c))
                elif ebc:
                    m = get_mid(b, c)
                    group.faces[fi] = (b, m, a)
                    appended.append((m, c, a))
                else:
                    m = get_mid(c, a)
                    group.faces[fi] = (c, m, b)
                    appended.append((m, a, b))
            else:
                if eab and ebc:
                    m, n = get_mid(a, b), get_mid(b, c)
                    group.faces[fi] = (b, n, m)
                    if _edge_length(group.verts, m, c) < _edge_length(group.verts, n, a):
                        appended += [(m, n, c), (m, c, a)]
                    else:
                        appended += [(m, n, a), (n, c, a)]
                elif ebc and eca:
                    m, n = get_mid(b, c), get_mid(c, a)
                    group.faces[fi] = (c, n, m)
                    if _edge_length(group.verts, m, a) < _edge_length(group.verts, n, b):
                        appended += [(m, n, a), (m, a, b)]
                    else:
                        appended += [(m, n, b), (n, a, b)]
                else:
                    m, n = get_mid(c, a), get_mid(a, b)
                    group.faces[fi] = (a, n, m)
                    if _edge_length(group.verts, m, b) < _edge_length(group.verts, n, c):
                        appended += [(m, n, b), (m, b, c)]
                    else:
                        appended += [(m, n, c), (n, b, c)]

        group.faces.extend(appended)
        step_added = len(group.verts) - before_v
        added_total += step_added
        group.slices[-1] = (mat, base_v, base_i, len(group.faces) - first,
                            len(group.verts) - base_v)
        if not step_added:
            break
    return added_total


def keep_copies_together(group, origin) -> int:
    """Give duplicate UV-seam vertices the exact same displacement."""
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

def _tri_normal(verts, tri) -> tuple[float, float, float]:
    """Un-normalised face normal (its length is twice the triangle area)."""
    ax, ay, az = verts[tri[0]]
    bx, by, bz = verts[tri[1]]
    cx, cy, cz = verts[tri[2]]
    e1x, e1y, e1z = bx - ax, by - ay, bz - az
    e2x, e2y, e2z = cx - ax, cy - ay, cz - az
    return (e1y * e2z - e1z * e2y,
            e1z * e2x - e1x * e2z,
            e1x * e2y - e1y * e2x)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(a) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def inverted_faces(verts, faces, origin) -> list[tuple[int, int, int]]:
    """Faces whose winding the morph reversed relative to ``origin``.

    A geometric sign test, not a shading one: a face whose vertex normals disagree with its
    winding is only a lighting artefact (the stock base mesh ships seven of those), but a
    face whose *orientation* flipped is a fold — the surface turned through itself.
    """
    bad = []
    for tri in faces:
        n0 = _tri_normal(origin, tri)
        n1 = _tri_normal(verts, tri)
        if _length(n0) <= 1e-12 or _length(n1) <= 1e-12:
            continue
        if _dot(n0, n1) < 0.0:
            bad.append(tri)
    return bad


def unfold_region(group, origin, rounds: int = 8, strength: float = 0.5) -> int:
    """Fair away the micro-triangles the morph folded through themselves.

    The keyhole flap over the sternum is a thin (~1 cm) open overhang that sits exactly on
    the cup's upper rim, where the dome weight falls from 0.19 to 0.008 between ``z = 146.0``
    and ``z = 147.6`` — a gradient that runs *inside the flap's own thickness*. The base
    mesh's coarse triangles survive that shear, but the local subdivision cuts the lip into
    0.002–0.1 cm² slivers and 20 of them came out inside out (signed area negative against
    the bind pose), which reads as a crumpled, dark lip in the 30°/40° views.

    Two cheaper repairs were tried and rejected on the rendered result: damping the
    displacement (leaves a plateau and a 0.5 cm step where the plateau ends) and keeping the
    lip's coarse triangles (leaves a low-poly plate that does not follow the grown chest).
    Fairing instead keeps the surface where the sculpt put it and only slides the offending
    welded vertices toward the mean of their neighbours — the same operation the main fairing
    uses — so the fold is ironed out without a dent or a step. Iterates until no face has
    reversed; returns the number of welded vertex groups touched.
    """
    faces = getattr(group, "faces", None)
    verts = group.verts
    if not faces or not origin or len(origin) != len(verts):
        return 0
    weld = _weld_keys(verts)
    members: dict[int, list[int]] = {}
    for i, wid in weld.items():
        members.setdefault(wid, []).append(i)
    neighbours: dict[int, set[int]] = {}
    for tri in faces:
        for vi in tri:
            slot = neighbours.setdefault(weld[vi], set())
            for other in tri:
                nw = weld[other]
                if nw != weld[vi]:
                    slot.add(nw)

    touched: set[int] = set()
    for _ in range(rounds):
        bad = inverted_faces(verts, faces, origin)
        if not bad:
            break
        zone: set[int] = set()
        for tri in bad:
            for vi in tri:
                wid = weld[vi]
                zone.add(wid)
                zone |= neighbours.get(wid, set())
        fair_zone(verts, members, neighbours, zone, strength)
        touched |= zone
    return len(touched)


def fair_zone(verts, members, neighbours, zone, strength) -> None:
    """Move every welded group in ``zone`` a fraction of the way to its neighbours' mean."""
    moved: dict[int, tuple[float, float, float]] = {}
    for wid in zone:
        nb = neighbours.get(wid)
        if not nb:
            continue
        ax = ay = az = 0.0
        count = 0
        for other in nb:
            j = members[other][0]
            ox, oy, oz = verts[j]
            ax += ox
            ay += oy
            az += oz
            count += 1
        if not count:
            continue
        ax /= count
        ay /= count
        az /= count
        i0 = members[wid][0]
        px, py, pz = verts[i0]
        moved[wid] = (px + (ax - px) * strength,
                      py + (ay - py) * strength,
                      pz + (az - pz) * strength)
    for wid, point in moved.items():
        for i in members[wid]:
            verts[i] = point

# ------------------------------------------------------------------ relaxing

def _welded_normals(verts, faces, weld: dict[int, int],
                    allowed: set[int] | None = None) -> dict[int, tuple[float, float, float]]:
    """Area-weighted unit normals per welded vertex id."""
    accum: dict[int, list[float]] = {}
    for a, b, c in faces:
        if allowed is not None and (a not in allowed or b not in allowed or c not in allowed):
            continue
        pa, pb, pc = verts[a], verts[b], verts[c]
        ex, ey, ez = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        fx, fy, fz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        nx = ey * fz - ez * fy
        ny = ez * fx - ex * fz
        nz = ex * fy - ey * fx
        for vi in (a, b, c):
            slot = accum.setdefault(weld[vi], [0.0, 0.0, 0.0])
            slot[0] += nx
            slot[1] += ny
            slot[2] += nz
    out: dict[int, tuple[float, float, float]] = {}
    for wid, (nx, ny, nz) in accum.items():
        ln = math.sqrt(nx * nx + ny * ny + nz * nz)
        if ln > 1e-9:
            out[wid] = (nx / ln, ny / ln, nz / ln)
        else:
            out[wid] = (0.0, 1.0, 0.0)
    return out


def smooth_region(group, morph: ChestMorph, iterations: int, strength: float,
                  pin_below: float = 0.004, origin=None,
                  materials=None) -> int:
    """Feature-preserving normal-projected fairing inside the edited chest."""
    if iterations <= 0 or strength <= 0.0 or not getattr(group, "faces", None):
        return 0
    verts = group.verts
    allowed = _selected_vertex_set(group, materials)
    base_pts = origin if (origin is not None and len(origin) == len(verts)) else None
    ref_pts = base_pts if base_pts is not None else verts

    weld = _weld_keys(ref_pts)
    members: dict[int, list[int]] = {}
    for i in range(len(verts)):
        if allowed is not None and i not in allowed:
            continue
        members.setdefault(weld[i], []).append(i)
    if not members:
        return 0

    adj: dict[int, set[int]] = {}
    edge_uses: dict[tuple[int, int], int] = {}
    for a, b, c in group.faces:
        if allowed is not None and (a not in allowed or b not in allowed or c not in allowed):
            continue
        wa, wb, wc = weld[a], weld[b], weld[c]
        for x, y in ((wa, wb), (wa, wc), (wb, wa), (wb, wc), (wc, wa), (wc, wb)):
            if x != y:
                adj.setdefault(x, set()).add(y)
        for u, v in ((wa, wb), (wb, wc), (wc, wa)):
            if u != v:
                ek = (u, v) if u < v else (v, u)
                edge_uses[ek] = edge_uses.get(ek, 0) + 1

    boundary_welded: set[int] = set()
    for (u, v), cnt in edge_uses.items():
        if cnt == 1:
            boundary_welded.add(u)
            boundary_welded.add(v)

    # Smoothly fade fairing to 0 near open welded boundaries (such as the z≈146.2
    # collar bib overhang) so neither the open lip nor the skin directly beneath
    # it drifts apart into a visible seam slit in overhead clay views.
    boundary_pts = [ref_pts[members[bw][0]] for bw in boundary_welded if bw in members]
    boundary_fade: dict[int, float] = {}
    if boundary_pts and len(members) > 16:
        for w, idx in members.items():
            if w in boundary_welded:
                boundary_fade[w] = 0.0
                continue
            px, py, pz = ref_pts[idx[0]]
            d2_min = min(
                (px - bx) ** 2 + (py - by) ** 2 + (pz - bz) ** 2
                for bx, by, bz in boundary_pts
            )
            boundary_fade[w] = smootherstep((math.sqrt(d2_min) - 1.1) / 1.5)
    else:
        for w in members:
            boundary_fade[w] = 0.0 if w in boundary_welded else 1.0

    weight = {w: morph.weight_at(*ref_pts[idx[0]])
              for w, idx in members.items()}
    movable = {w: (wt > pin_below and boundary_fade.get(w, 1.0) > 0.0)
               for w, wt in weight.items()}
    if not any(movable.values()):
        return 0

    # Gradual dome-wide ramp (`wt / 0.56` instead of a sharp `0.12` cliff!)
    # eliminates soap-film box corners at `z ≈ 144.5` and `z ≈ 136.5`. Keep full
    # smoothing across `|x| <= 9.8` so the base mesh's x≈+8.0..+8.5 bib cliff
    # melts into a spherical arc, then taper on `|x| > 9.8` to preserve the
    # posterior/lateral breast root (`root_spread`), and lightly damp the
    # concave sternum saddle (`|x| < 1.8`) so fairing does not flatten cleavage.
    smooth_mask: dict[int, float] = {}
    for w, wt in weight.items():
        px, _py, pz = ref_pts[members[w][0]]
        flank_keep = 1.0
        sternal_keep = 1.0
        if len(members) > 16:
            flank_keep = 0.20 + 0.80 * smootherstep((11.8 - abs(px)) / 2.0)
            mid_z = smootherstep((pz - 138.8) / 1.6) * smootherstep((143.8 - pz) / 1.6)
            sternal_keep = 1.0 - 0.34 * mid_z * (1.0 - smootherstep((abs(px) - 0.4) / 1.8))
        smooth_mask[w] = (
            smootherstep((wt - pin_below) / 0.56)
            * boundary_fade.get(w, 1.0)
            * flank_keep
            * sternal_keep
        )

    # Precompute a 3-ring Gaussian-weighted geodesic stencil (~2.2 cm diameter
    # on subdivided chest tris) so coarse ~2.8 cm base-mesh facets melt into a
    # smooth curve in ~10 steps without soap-film flattening the macro-dome.
    use_multiring = len(members) > 16
    stencil: dict[int, list[tuple[int, float]]] = {}
    for w, r1 in adj.items():
        if not movable.get(w) or not r1:
            continue
        weights_nb: dict[int, float] = {}
        for nb in r1:
            if nb in members and nb != w:
                weights_nb[nb] = 1.0
        if use_multiring:
            r2: set[int] = set()
            for nb in r1:
                for nb2 in adj.get(nb, ()):
                    if nb2 != w and nb2 not in weights_nb and nb2 in members:
                        weights_nb[nb2] = 0.65
                        r2.add(nb2)
            for nb2 in r2:
                for nb3 in adj.get(nb2, ()):
                    if nb3 != w and nb3 not in weights_nb and nb3 in members:
                        weights_nb[nb3] = 0.35
        if weights_nb:
            tot = sum(weights_nb.values())
            stencil[w] = [(nb, wt_nb / tot) for nb, wt_nb in weights_nb.items()]

    touched = 0
    for step_idx in range(iterations):
        if step_idx % 2 == 0:
            wnorm = _welded_normals(verts, group.faces, weld, allowed)
        pos = {w: verts[idx[0]] for w, idx in members.items()}
        update: dict[int, tuple[float, float, float]] = {}
        for w, nb_wts in stencil.items():
            px = py = pz = 0.0
            for nb, wn in nb_wts:
                q = pos[nb]
                px += q[0] * wn
                py += q[1] * wn
                pz += q[2] * wn
            cur = pos[w]
            lx = px - cur[0]
            ly = py - cur[1]
            lz = pz - cur[2]
            nw = wnorm.get(w, (0.0, 1.0, 0.0))
            proj = lx * nw[0] + ly * nw[1] + lz * nw[2]
            k = strength * smooth_mask.get(w, 0.0)
            # Purely normal-dominated fairing (93% normal + 7% tangential)
            # melts out-of-plane /\ /\ cone ridges into round spheres while
            # keeping UV seams and painted suit borders straight and unwarped.
            on_mid = abs(ref_pts[members[w][0]][0]) < 1e-6
            ux = 0.0 if on_mid else (0.93 * proj * nw[0] + 0.07 * lx)
            uy = 0.93 * proj * nw[1] + 0.07 * ly
            uz = 0.93 * proj * nw[2] + 0.07 * lz
            update[w] = (
                cur[0] + k * ux,
                cur[1] + k * uy,
                cur[2] + k * uz,
            )
        for w, p in update.items():
            for i in members[w]:
                verts[i] = p
        touched = len(update)
    return touched


# --------------------------------------------------------------------- normals

def _weld_keys(verts, indices=None) -> dict[int, int]:
    """Map each vertex index to a position-welded group id."""
    if indices is None:
        indices = range(len(verts))
    keys: dict[tuple[int, int, int], int] = {}
    out: dict[int, int] = {}
    for i in indices:
        x, y, z = verts[i]
        k = (round(x * 1e4), round(y * 1e4), round(z * 1e4))
        out[i] = keys.setdefault(k, len(keys))
    return out


def rebuild_normals(group, morph: ChestMorph, materials=None) -> None:
    """Rebuild normals over the edited chest and blend them in by strength."""
    import numpy as np

    verts = group.verts
    faces = getattr(group, "faces", None)
    if not faces:
        return
    allowed = _selected_vertex_set(group, materials)
    weld = _weld_keys(verts)
    accum: dict[int, list[float]] = {}
    for a, b, c in faces:
        if allowed is not None and (a not in allowed or b not in allowed or c not in allowed):
            continue
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
        if allowed is not None and i not in allowed:
            continue
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
    """Run the morph over the TPP groups (body, LOD and shadow caster)."""
    morph = morph or ChestMorph()
    report: dict = {"morph": morph.describe(), "drawables": {}}
    for name, group in groups.items():
        if name not in ("body", "shadow"):
            continue
        before = len(group.verts)
        stats: dict = {}
        moved = morph.apply(group, label=name, log=log, stats=stats)
        report["drawables"][name] = {
            "vertices_moved": moved,
            "vertices_total": len(group.verts),
            "vertices_added": len(group.verts) - before,
            **stats,
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
