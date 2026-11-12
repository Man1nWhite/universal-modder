# Miranda `Miranda_Busty_LAS` — chest-size variant

Deliverable: **`dist/Miranda_Busty_LAS.zip`** (+ `.sha256`), a second PAYDAY 2
Legendary Armour Skins outfit built from the same L4D2 Miranda source as
`dist/Miranda_LAS.zip`, with a sculpted D-cup chest. It registers its own
`LegendaryArmours.miranda_busty` entry and ships a distinct 3/4 upper-body
portrait icon (`miranda_busty.texture`), so **both packs can be installed at
once** and the stock outfit is never modified.

Builder: `tools/pd2-las/build_busty_variant.py` · morph: `tools/pd2-las/bust_variant.py`
· tests: `tests/test_bust_variant.py`
· report: `build/pd2-las/busty_variant_report.json`.

```sh
bash tools/pd2-las/recover_env.sh        # venv + the 2B templates (build/pd2-las/2b/)
.venv/bin/python tools/pd2-las/build_busty_variant.py
```

## Model space (measured, not assumed)

The authored mesh is z-up, centimetres, feet at `z = 0`, **`+y` is the front**
(verified from `g_head` face/hair geometry). On the base `miranda.model`
(`g_body`), explicit `~0.3–0.6 cm` 3D suit piping bevels frame the hexagonal
chest panel at `z ≈ 135.0..136.2` (inframammary crease, `y ≈ 16.58 cm`),
`|x| ≈ 8.0..8.7` (diagonal stitched seam), and `z ≈ 146.2..147.1` (upper panel
edge). The base breast spans laterally out to `|x| ≈ 10.8 cm` and peaks at
`y = 19.98 cm` (`x = 5.59, z = 140.01`), with only a `0.4–0.6 cm` sternum dip
under the zipped white catsuit.

## The 3D radial-spherical catsuit sculpt

The sculpted variant (`bust_variant.py`) combines three geometric stages so the
chest reads as a round, proportional, anatomically clean bust inside Miranda's
high-tension hex-weave catsuit from every angle — **top** (`Top 68°`, `Top 48°`),
**bottom** (`Bottom 48°`, `Bottom 68°`), **front** (`0°`), **oblique** (`30°`,
`60°`), and **side** (`90°`):

### 1. Welded 2-level 1-to-4 local chest subdivision (`+3,292` chest vertices)

* `subdivide_region` refines the chest & breast-root patch (`SUBDIVIDE_Z = (132.5, 151.0)`,
  `DEFAULT_SUBDIVISIONS = 2`, `MAX_CHEST_EDGE_CM = 0.25`) using **3D-welded edge
  keys**.
* Co-located stitched-seam vertex pairs (e.g. `|x| ≈ 8.0–8.7` where UV distance
  across the seam is `< 0.05`) split **in lockstep** at identical 3D midpoints,
  preventing T-junctions and sawtooth steps while still skipping wide UV-island
  jumps (`MAX_EDGE_UV_DISTANCE = 0.20`).
* Using uniform 1-to-4 (`k = 3`) refinement across the chest quads avoids
  bisecting only quad hypotenuses (`k = 1` green fans), which otherwise create
  alternating valence-8 / valence-4 diamond shading stars on specular clay.

### 2. Variable-exponent twin-hemisphere dome + spine-root radial expansion (`ChestMorph`)

* **Anisotropic twin-hemisphere projection (`+dy`) & asymmetry equalization**:
  * Uses a separable variable-exponent hemisphere `(1 - rho)^(0.78 + 0.47 * rho + 0.15 * up_t)`
    where `rho = |u|^2.45 + |w|^pz` (`pz = 1.98 -> 1.88`) centred at
    `(APEX_X = 5.05, APEX_Z = 140.95)` (`RADIUS_X_IN = 7.30`, `RADIUS_X_OUT = 7.00`,
    `RADIUS_Z_DOWN = 6.16`, `RADIUS_Z_UP = 8.85`, `SOFT_SCALE = 1.12`,
    `SOFT_WEIGHT = 0.24`, `MEDIAL_OVERLAP = 0.11`, `VALLEY = 0.145, VALLEY_W = 2.25`):
    * Near `rho = 0` (the cup apex), `q ≈ 0.78` produces a wide, blunt circular
      hemisphere `(   )(   )` with zero parabolic cone tip in both horizontal
      (`Top 68°`, `Bottom 68°`, `Bottom 48°`) and vertical (`60°`, `90°`) slices.
    * Near `rho = 1` (collar & inframammary rim), `q ≈ 1.25–1.40` eases smoothly
      to zero with `< 7.5%` peak step per `0.25 cm` and `< 1.78x` linear UV stretch.
    * Balanced `RADIUS_X_IN = 7.30`, `MEDIAL_OVERLAP = 0.11`, and `VALLEY = 0.145`
      preserve two clearly separated hemispheres (`~0.6–0.85 cm` smooth U-saddle
      over Miranda's taut catsuit) without fusing into a central monoboob or
      carving an artificial sharp W-groove.
  * Blends `86%` symmetric twin-sphere target lift (`sph_pull`, damping `excess_y`
    above `18.50 cm` to equalize the base mesh's `+0.63 cm` overlapping right-bib
    asymmetry down to `0.21 cm` and melt the `x ≈ +8.0..+8.5` vertical bib step)
    with `14%` proportional depth push for subtle suit relief, plus a smooth
    lateral/posterior root bell (`DEFAULT_ROOT_GAIN = 0.70`,
    `DEFAULT_ROOT_SPREAD = 0.42`) for breast-root vertices closer to the spine
    (`y ≈ 5.3..18.5 cm`, `|x| ≈ 5.8..13.4 cm`).
  * Lower-pole support ends strictly at `140.95 - 6.16 * 1.12 = 134.05 cm`
    (above the ribcage/abdomen, eliminating abdominal bulge); upper-pole support
    ends strictly at `140.95 + 8.85 * 1.12 = 150.86 cm` (below `HEAD_Z = 152.0`).
* **3D vertical & lateral radial fullness (`dz`, `dx`)** around internal pivot
  `(RADIAL_X = 5.05, RADIAL_Z = 140.95)`:
  * Gentle vertical underbust support (`v_lat = 0.92 + 0.08 * v_fac`, `lift = 0.18`)
    keeps honeycomb hexagons unstretched (`1.76x` max) and prevents twin hanging
    underbust spikes in `Bottom 48°` views, while outward-only lateral rounding
    (`spread = 0.34`) avoids pinching medial vertices inward into `/\ /\` cones.

### 3. Slice-scoped 3-ring Gaussian normal-projected fairing (`smooth_region`)

* Precomputes a **3-ring geodesic stencil** (`~2.2 cm` diameter across subdivided
  chest triangles, weights `1.0 / 0.65 / 0.35`) projected `93%` onto the welded
  surface normal over `13` monotone passes (`strength = 0.32`) with a gradual
  dome-wide ramp (`wt / 0.56`) instead of a sharp rim cliff.
* Full fairing across `|x| <= 9.8 cm` melts Miranda's coarse `~2.8 cm` L4D2
  facets and the `x ≈ +8.0..+8.5` rectangular bib cliff into smooth spherical
  arcs, while gentle mid-sternum damping preserves two-cup separation and outer
  flank tapering (`|x| > 9.8 cm`) preserves spine-side breast-root fullness.
* Strictly scoped to selected material slices (`miranda_body`, `0.0 cm` leak into
  head/collar shadow slices) and faded smoothly near open welded mesh borders so
  the `z ≈ 146.2` keyhole lip remains completely seamless in overhead clay views.

## Preset and measured result

Default preset (`cup_gain = 0.382`, `round_gain = 0.046`, `lift = 0.18`,
`spread = 0.34`, `root_gain = 0.70`, `root_spread = 0.42`, `valley = 0.145`,
2-level welded subdivision, 13 3-ring normal-projected fairing steps @ `0.32`):

| Metric | Base (`Miranda_LAS`) | Variant (`Miranda_Busty_LAS`) |
| --- | --- | --- |
| Front reach `max(y)` in chest band | `19.98 cm` | **`23.21 cm` (`+3.23 cm` gain)** |
| Depth over `WALL_Y = 2.6 cm` | `17.38 cm` | **`20.61 cm`** |
| `g_body` vertex count | `5,645` | **`8,937` (`+3,292` chest vertices)** |
| `s_body` vertex count | `9,874` | **`13,166` (`+3,292` chest vertices)** |
| Max linear edge / UV stretch (`g_body`) | `1.00x` | **`1.76x`** (down from `2.47x`) |
| Left vs right cup peak symmetry (`z ≈ 140.7`) | `0.63 cm` skew | **`0.21 cm`** |
| Two-cup sternum separation (`y_cup - y(0)`) | `−0.23 cm` (single shell: the sternum is *in front* of the cups) | **`0.62–0.83 cm` smooth U-saddle** |
| Orientation breaks (`g_body`, `s_body`) | `0` | **`0`** |
| Abdominal `|dy|` below `z = 134 cm` | `0.00 cm` | **`< 0.01 cm`** (was `+5.10 cm`) |
| Unselected shadow-slice vertex drift | `0.00 cm` | **`0.00 cm`** (was `1.084 cm`) |
| Outfit-grid icon (`miranda_busty.texture`) | 2D face UV crop | **Distinct `256×256` 3/4 upper-body portrait (`DXT5`)** |

The base column is measured on the tracked `dist/Miranda_LAS.zip`, not on a fresh retarget, so it
describes the pack the variant actually sits beside.

**Runtime status: never loaded in game.** `BUILD_INFO.json` carries
`"runtime_verified": false`, exactly like the base pack — every number here is offline evidence
(measured geometry, rendered sheets, the tests below). `docs/pd2-las/in-game-checklist.md` is the
gate, and the ME2 asset-rights note applies to this pack as it does to `Miranda_LAS.zip`.

## Previews

Generated on **every build** into `build/pd2-las/previews/` (gitignored). The
copies that used to be tracked under `docs/pd2-las/previews/` were deleted to
keep the tree small; `tests/test_bust_variant.py` still pins that the builder
emits all five sheets by name:

* `busty_compare_top_bottom.png` — 4-angle whole-character top & bottom
  comparison (`Top 68° · 0° above front`, `Top 48° · 26° 3/4 above`,
  `Bottom 48° · 26° 3/4 below`, `Bottom 68° · 0° below front`), showing arch
  curvature, the spine-root transition and the hexagon layout intact.
* `busty_sculpt_top_bottom_clay.png` — untextured clay diagnostic, same angles.
* `busty_sculpt_clay.png` — matte-clay diagnostic (`0°`, `30°`, `60°`, `90°`)
  from actual `.model` vertex normals.
* `busty_compare_chest.png` — close-up chest comparison (`0°`, `30°`, `60°`, `90°`).
* `busty_compare_full.png` — full-body comparison (`0°`, `34°`, `90°`) incl. `g_head`.

## Verification

* `tests/test_bust_variant.py` — 24 test functions, **23 passing on a clean checkout** plus the
  end-to-end geometry one, which skips without the 2B templates unpacked (`build/pd2-las/2b/`):
  morph contract, continuity across
  the edit rim, taut-catsuit cleavage contour, slice containment, open-boundary
  collar-lip pinning during fairing, watertight welded subdivision across seams,
  out-of-repo `_display_path`, and end-to-end regression checks on
  `dist/Miranda_Busty_LAS.zip` (distinct DDS icon, vertex count, `< 0.05 cm`
  abdominal neutrality, `< 2.0 cm` chest triangle edges, `< 1.80x` global UV/edge
  stretch, spine-side root expansion, exact `BUILD_INFO.json` `front_y_max_cm`
  agreement across all vertices, and unit-length normals in every shipped drawable —
  the check that would have caught the pre-2026-11-05 artifact).
* `um publish check` & `um kb check --index` — clean pass.

## The tracked zip is rebuilt (2026-11-05)

The previously tracked `dist/Miranda_Busty_LAS.zip` predated the subdivision-midpoint
renormalisation: `bust_variant.subdivide_region` averaged two unit normals into one 0.9867 long, and
12 vertices at the top of the chest band (`z ≈ 150.8–151.0`, |n| = 0.9867 … 0.9985) shipped that way
in `g_body`, `g_body_lod1` and `s_body` — 36 non-unit normals per pack. The code was fixed earlier;
the artifact was not, because the 2B templates were unavailable. It is now rebuilt:

| | before | after |
|---|---|---|
| `dist/Miranda_Busty_LAS.zip` | 5,815,039 B, `3043fcba…` | **5,815,197 B, `91dbd3271de478b2cbc76c170de8d81385e0188b59fbece9d79f941758d21a00`** |
| non-unit drawable normals | 36 (max \|1−\|n\|| = 1.33 %) | **0** (max \|1−\|n\|| = 2e-8) |
| `g_body` vertex normals | — | 2,775 changed (morphed band only), plus 2,776 / 2,770 `uvdir_u` / `uvdir_v` |
| geometry, topology, weights, atoms, UVs | — | byte-identical |
| armor-skin icon | — | 336 of 65,536 px differ by ≤ 66/255 (chest shading) |

Two consecutive rebuilds produce identical bytes (deterministic). `tests/test_bust_variant.py::
test_shipped_busty_drawable_normals_are_unit_length` now pins the artifact, so a stale zip fails the
suite instead of shipping. Rebuild with `make -sC tools/pd2-las env busty` on a machine with node (`env`
unpacks `references/2b.rar` for the templates).

## The keyhole lip was folded inside out (2026-11-05)

The neckline overhang at the sternum — the "keyhole lip", an open ~1 cm flap between the two cup
rims — sits exactly in the gradient that weights the dome: 0.19 at `z = 146.0` falling to 0.008 by
`z = 147.6`. Those 1.6 cm cut *through the flap's own thickness*, so the flap is sheared instead of
translated. The stock mesh's coarse triangles survive that shear; the local subdivision does not.
In the previously shipped `91dbd327…` bytes the lip carried 992 faces where the base carries 64,
slivers down to 0.0019 cm² / 0.064 cm (base: 0.22 cm² / 0.50 cm), and **10 of them were inside
out** — winding reversed against the bind pose, i.e. the surface had turned through itself. The
30°/40°/45° chest views showed it as a crumpled, dark notch in the lip; the 0° view showed a hard
edge where the fold ended.

It survived the earlier normals rebuild because it is *geometric*, not shading: 25 faces disagreed
with their winding, but only the 10 whose triangles had literally folded were the defect.

**Fix:** `bust_variant.unfold_region()`, called from `ChestMorph.apply` after `keep_copies_together`
and before `rebuild_normals`. It tests each face's winding against the bind pose (`inverted_faces`,
a signed-area comparison — deliberately not a normal test, so the seven normal-only quirks the stock
pack ships and the twelve coincident-shell faces are left alone), then **fairs** the offending
welded vertices toward the mean of their neighbours, iterating until no face is inverted. Fairing
slides the slivers along the surface instead of damping the displacement, so the sculpt stays where
it was put.

| | base `Miranda_LAS` | busty before (`91dbd327…`) | busty now (`d26b93e1…`) |
|---|---|---|---|
| `g_body` vertices / faces | 5,645 / 9,548 | 8,937 / 16,072 | 8,937 / 16,072 |
| faces inverted against the bind pose | 0 | **10** | **0** |
| faces whose normals disagree with their winding | 7 | 25 (18 in the lip) | 22 (15 in the lip) |
| dihedral edges > 170° / > 175° | 2 / 2 | 7 / 4 | 4 / 3 |
| lip-band faces / min area / min edge | 64 / 0.22 cm² / 0.50 cm | 992 / 0.0019 cm² / 0.064 cm | 992 / 0.0026 cm² / 0.073 cm |
| vertices moved by the repair | — | — | 38 welded groups, max 2.23 mm, all within 6 cm of the midline |
| `depth_gain_cm` / `front_y_max_cm` / `depth_over_wall_cm` | — | 3.23 / [19.98, 23.21] / [17.38, 20.61] | unchanged |
| `width_cm` / `volume_proxy` | — | [25.47, 25.48] / 2,917.7 | [25.47, 25.48] / 2,917.8 |

The 15 residual "normals disagree" faces inside the lip crease are sub-millimetre slivers
(0.0026–0.108 cm², 0.83 cm² in total) whose *geometry* is valid — a 90° crease in a 1 cm flap cannot
avoid some of them; the base pack's own seven are larger (up to 1.71 cm²). `s_body` tracks `g_body`
exactly, the FPS arms are untouched, and two consecutive rebuilds are byte-identical.

Three cheaper repairs were tried on this mesh and rejected on the rendered result — do not retry
them: **damping the displacement** in the lip box (leaves a plateau and a 0.6 cm step where the
plateau ends, and `smooth_region` then relaxes 51 vertices), **vetoing subdivision** in the lip
(`in_keyhole_lip`; keeps the coarse plate, which stops following the grown chest, and leaves a
blocky notch), and **widening the keyhole box** to `x ±4.2, z 145.0–148.6` (8 flips but an obvious
silhouette step at 60–90°). All three are C0 discontinuities in a smooth field; fairing is not.
Fairing the repaired zone any further than the first valid state does not help either: two extra
gentle rounds (strength 0.2) re-invert a face and the guard reverts them, so the repair stops as soon
as the winding is legal and leaves the residual 15 normal quirks above.

Rendered evidence, regenerated from this build: `docs/previews/12_Miranda_Busty_LAS.png` (full-body
four-angle + portrait + FPS arms), `13_Miranda_Busty_vs_LAS_chest.png` (0°/30°/**45°**/60°/**90°**
close-ups with the framing pulled back as the yaw widens, stock above, variant below) and
`14_Miranda_Busty_vs_LAS_top_below.png` (58° above and 58° below, at 0° and 30° yaw). The builder's own sheets stay in
`build/pd2-las/previews/` (`busty_compare_chest.png`, `busty_compare_top_bottom.png`,
`busty_sculpt_clay.png`).

## The placket hem was bowing (2026-11-05, second pass)

The first pass above fixed the folds. Reviewing the chest from **58° above and 58° below** —
angles no front sheet can reach, now shipped as `docs/previews/14_Miranda_Busty_vs_LAS_top_below.png`
— showed a second, smaller defect: the keyhole hem at `z = 146.2`, a straight garment edge in the
stock mesh, came out **bowed**. The raw field pushes that edge 0.75 cm at the sternum and 2.0 cm at
the cups, so a 5 cm wide straight edge tilted by 1.25 cm and read as a notch in the overhead view and
as a kinked crease in clay close-ups.

**Fix:** `ChestMorph.displacement` now band-limits the forward push *laterally* across the hem — a
three-tap average `HEM_BLEND_X = 0.9 cm` apart, faded in and out by a smooth z envelope
(`z ≈ 145.0 … 147.9`), with the correction gated by `lateral_gate` so the taps cannot leak a
fraction of the cup's push into the sleeve. An average is smooth in x by construction, so unlike
every masking attempt in the previous section this one cannot leave a step; it just makes the hem
translate instead of tilt.

| | before this pass (`d26b93e1…`) | after (`abfeafbb…`) |
|---|---|---|
| hem-band dihedral (mean / p90) | 9.6° / 19.9° | **9.2° / 18.4°** |
| faces whose normals disagree with their winding | 22 | 28 (still ≤ 0.09 cm² each, all in the hem crease) |
| dihedral edges > 170° / > 175° | 4 / 3 | 4 / 3 |
| `depth_gain_cm` / `front_y_max_cm` / `width_cm` | 3.23 / [19.98, 23.21] / [25.47, 25.48] | unchanged |
| lip fold repair | 38 vertices faired, 0 inverted | 38 vertices faired, 0 inverted |

Two alternatives were measured and rejected. **Band-limiting the field in z** (`Z_BLEND = 0.6` and
`0.9 cm`) softened every vertical gradient in the chest, but it costs the apex: `depth_gain_cm` fell
3.23 → 3.20 → 3.17 and the flipped-face count rose to 25, i.e. it pays for a hem fix with the bust
itself. **Widening `collar_taper`** (0.22 over 3.8 cm → 0.34 over 4.4 cm) softened the upper rim
visibly but changed nothing about the hem. More lateral blending than 0.9 cm buys another 1° of hem
smoothness and introduces a 179.5° edge at the hem's end taper — a pinch, not a fix.

What the overhead views *also* show, and what is deliberately left alone: the hexagon texture and
the modelled piping bevels are stretched over the enlarged cups (chest texel scale +10 % on average,
p99 188 → 205), and the zipper emblem at the placket reads taller. That is what growing geometry
under a fixed texture does; attenuating the sculpt over the emblem to protect it would flatten the
cup, which is the larger artefact.

## The step on the right of the chest (2026-11-05, third pass)

Reported from the shipped previews as *"there is a step on a chest, it should be smooth"*, on the
viewer-right (i.e. **+x**) cup. Localising it took three tries, because the obvious suspects were
not guilty:

* **per-vertex normal deviation** in the chest box is *lower* in the variant than in stock
  (mean 1.2° vs 8.1°; only three vertices > 40° either way) — a dead end;
* **edge dihedral** around the keyhole hem (`|x − 2| < 1.6, y > 15.5, 145.5 < z < 147.8`) does
  show the hem's piping bevel sharpened (`8` edges > 120°, max 179.3°, against the stock's `2`,
  max 156.7°), but fixing those numbers alone did not move what the eye sees;
* **two shells poking through each other** was ruled out properly: after welding by position the
  body is three shells, and a Möller–Trumbore edge/triangle sweep finds **0** intersections between
  non-adjacent ones in either pack.

What the defect actually is: the field pushes the hem's **upper face and outer end** (|x| ≈ 7 … 10,
where the placket edge meets the side seam) further forward than the fold behind it, so the hem's
2.1 cm of forward relief lands as a *flat facet* with a hard top and side edge — a shelf that lights
up in clay at 20 px/cm from the front and at 25° yaw. The lateral blend from the second pass
(`HEM_BLEND_X = 0.9`) cannot reach across that end, and it does nothing at all for the shear across
the fold itself.

**Fix (field only, no fairing):** `ChestMorph.displacement` now also carries

* `HEM_BLEND_Z = 1.2 cm` — three vertical taps across the fold, so the hem's upper face does not
  outrun the fold behind it (that is where the shelf's top edge came from);
* `HEM_WIDE_X = 2.1 cm` — a second, wider lateral tap pair, faded in only over
  `|x| ∈ 6.8 … 10.4`, i.e. exactly the hem's outer end.

Both average the *correction* and stay inside the hem's existing z envelope, so the apex still sees
the analytic field **bit for bit** (asserted in
`test_hem_blend_pulls_the_outer_step_back_without_touching_the_cup`): `depth_gain_cm` 3.23,
`front_y_max_cm` [19.98, 23.21] and `width_cm` [25.47, 25.48] are unchanged from the second pass.
Lateral spread across the seam at the hem falls 7.5 … 12 % (|x| 7.5–9.5: ratios 0.89 / 0.76 / 0.70
at z = 145.6 / 146.0 / 146.4), and the push at the hem's outer end comes back 0.05 … 0.26 cm.

**Three repairs were measured and rejected — do not retry them.** A Laplacian `relax_creases` over
newly sharpened edges does converge (`faired 31 vertices that creased the placket hem`) but stretches
the short fold edges to **2.43x**, breaking the pack's own 1.80x UV/edge budget that keeps the
honeycomb hexes clean (the shipped build sits at 1.756x), and repeated rounds cascade
(10 → 0 → 4 → 2 → 0 edges per round) without moving the dihedral count. A y-only version of the same
pass (equalise the forward push across each sharpened edge, never touch x/z) is worse still — 2.33x
stretch and 20 chest edges > 120° — because the equalised vertex now shears against the neighbours it
was not paired with. Pushing the vertical blend to `HEM_BLEND_Z = 2.0` flattens the hem a little
further but puts the same edge at 1.96x, i.e. the same budget breach by a different route. And a
lateral band-limit across the *vertical* side seam (|x| ≈ 8.3, z 131 … 150) sounds right but is inert
below z ≈ 145 where the field is linear in x (curvature < 1e-3 cm): it is folded into the wide hem tap
instead of shipped as a separate pass that does nothing.

Rendered evidence: `docs/previews/13_…_chest.png` (0°/30°/45°/60°/90°) and
`14_…_top_below.png` (58° above/below); the clay A/B used for the call (committed vs this build,
front and 25° yaw, 20 px/cm, `center=(5, 18.5, 141.5)`) is reproducible with
`render_mod_previews.rasterize_parts(..., pitch_deg=0.0)`.

## Key lessons (do not repeat)

0. **"Make it smooth" is a stretch-budget problem, not a dihedral problem.** Every pass that
   *faired* the crease the user pointed at — Laplacian or y-only, 1 round or 14 — fixed or ignored
   the angle while pushing short fold edges to 2.33–2.43x, i.e. breaking the 1.80x UV/edge budget
   that keeps the honeycomb hexes clean, and the shipped build is at 1.756x with only 0.044x of
   headroom. Band-limit the *field* (smooth by construction, no edge lengthened) or leave it alone;
   and check `max_stretch` after every such experiment, because the archive test will.
1. **Do not re-run the base `Miranda_LAS` build.** `dist/Miranda_LAS.zip` is
   treated as immutable; `build_busty_variant.py` falls back directly to reading
   `miranda.model` from `dist/Miranda_LAS.zip` when building into a clean `--out`
   directory, and only updates `dist/Miranda_Busty_LAS.zip` on canonical builds
   (or `--update-dist`).
2. **Never slice `g_body` into a hollow torso ring for overhead/underbust previews.**
   Clipping `z ∈ [122, 152.2]` without `g_head` or lower body exposes the black
   interior of the neck/abdomen cavity and floating severed collar triangles at
   steep pitches (`±68°..82°`). Always render whole-character Top & Bottom views
   (`use_head = True`, `z ∈ [60, 190]`).
3. **Avoid both boob-sock trenches (`VALLEY >= 0.40`) and monoboob overlap
   (`MEDIAL_OVERLAP >= 0.40` / wide `smootherstep` rim crushing).** Deep sternum
   trenches turn Top & Bottom views into narrow `/\ /\` cones and stretch
   honeycomb hexagons up to `2.47x`, whereas excessive medial overlap fuses the
   chest into a single central prow and multiplying `sqrt(1 - r²)` by a wide
   `smootherstep` crushes dome shoulders into a `>` side-profile cone. Use a
   variable-exponent hemisphere (`q ≈ 0.78` at apex easing to `1.25–1.40` at the
   rim) with balanced radii (`RADIUS_X_IN = 7.30`, `MEDIAL_OVERLAP = 0.11`,
   `VALLEY = 0.145`) and bounded edge stretch (`< 1.80x`).
4. **Pin open welded boundary edges (`edge_uses == 1`) in `smooth_region` and
   saturate `eff_depth` below overlapping collar lips.** Unwelded garment
   overhangs (such as Miranda's `z ≈ 146.2` keyhole flap) have one-sided 1-rings
   and will pull open into a visible seam slit under overhead views unless
   boundary vertices are pinned and share the underlying skin's depth factor.
5. **Scope `smooth_region` by material slice and measure `after_verts` across
   *all* vertices.** Slicing `after_verts[:len(before_verts)]` drops every
   subdivided chest vertex right where the true apex lives.
