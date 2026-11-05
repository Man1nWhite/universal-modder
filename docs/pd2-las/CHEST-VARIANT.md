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
bash tools/pd2-las/bootstrap.sh          # venv, 2B templates, textures
.venv/bin/python tools/pd2-las/build_busty_variant.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
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

* `tests/test_bust_variant.py` — 22 test functions, **21 passing on a clean checkout** plus the
  end-to-end geometry one, which skips without the extracted 2B templates at `/tmp/2bsrc`:
  morph contract, continuity across
  the edit rim, taut-catsuit cleavage contour, slice containment, open-boundary
  collar-lip pinning during fairing, watertight welded subdivision across seams,
  out-of-repo `_display_path`, and end-to-end regression checks on
  `dist/Miranda_Busty_LAS.zip` (distinct DDS icon, vertex count, `< 0.05 cm`
  abdominal neutrality, `< 2.0 cm` chest triangle edges, `< 1.80x` global UV/edge
  stretch, spine-side root expansion, and exact `BUILD_INFO.json` `front_y_max_cm`
  agreement across all vertices).
* `um publish check` & `um kb check --index` — clean pass.

## Rebuilding the tracked zip

The tracked `dist/Miranda_Busty_LAS.zip` was built before the subdivision midpoints were
renormalised (`bust_variant.subdivide_region` averaged two unit normals into one 0.9867 long, and 12
vertices at the top of the chest band shipped that way — see the normalisation test). A rebuild
therefore produces *different bytes*: every `payload_sha256` in `BUILD_INFO.json`, both `.sha256`
sidecars, the sizes in `docs/pd2-las/HANDOFF.md` and the `AGENTS.md` table all change.
`tests/test_las_pack.py::test_handoff_and_agents_quote_the_tracked_pack_bytes` fails until they are
updated, which is the point. Rebuild with `bash tools/pd2-las/bootstrap.sh` on a machine that has
node (it unpacks `references/2b.rar` for the templates).

## Key lessons (do not repeat)

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
