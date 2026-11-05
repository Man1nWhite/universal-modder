# Miranda `Miranda_Busty_LAS` — chest-size variant

Deliverable: **`dist/Miranda_Busty_LAS.zip`** (+ `.sha256`), a second PAYDAY 2
Legendary Armour Skins outfit built from the same L4D2 Miranda source as
`dist/Miranda_LAS.zip`, with a larger chest. It registers its own
`LegendaryArmours.miranda_busty` entry, so **both packs can be installed at
once** and the stock outfit is not modified.

Builder: `tools/pd2-las/build_busty_variant.py` · morph: `tools/pd2-las/bust_variant.py`
· tests: `tests/test_bust_variant.py` · report: `build/pd2-las/busty_variant_report.json`.

```sh
bash tools/pd2-las/bootstrap.sh          # venv, 2B templates, textures
.venv/bin/python tools/pd2-las/build_busty_variant.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
```

## Model space (measured, not assumed)

The authored mesh is z-up, centimetres, feet at z=0, **+y is the front**
(settled from the face and hair geometry of `g_head`, not from the eye-orbit
vertices — those sit toward the back of the head and read as a false negative).
The chest is a broad shell: front surface reaches y≈20 cm over a plateau at
| x | 2…11 cm, z 132…148, apex at (x≈5.6, z≈140), with only a **0.4–0.6 cm**
sternum dip. Breast-apex-to-back depth is ≈20 cm, chest wall (front of the
ribcage, estimated from the back surface at y≈-5) at y≈5 cm.

That shape drives the design: there is no separable "two-breast" volume to
scale, so the morph must **add** mass in two domes and carve the cleavage back
in, rather than inflate the existing form.

## The morph

The first attempt pushed the existing chest plate forward with a single radial
falloff. It read as a faceted balloon with a hard shelf, and close up the shelf
was exactly where the swell's rim met the outfit's raised sleeve-panel seam.
Two structural changes fixed that: the chest is **locally subdivided** before it
moves, and the displacement is a **two-scale** height field rather than one dome.

### 1. Local subdivision of the chest panel

The source chest is one flat plate with roughly one vertex every 2.5 cm — there
is nowhere for a new volume to live. `subdivide_region` splits the chest
triangles one-to-four (red/green refined, so a face on the patch border is
re-triangulated through the same edge midpoint instead of being left with a
T-junction) and appends the new vertices after the block each group already
owns, so the Diesel render atoms keep describing the mesh exactly.

Two guards, both learned from broken previews:

* faces whose edges span a **UV seam** are never split (the midpoint's averaged
  UV lands on the sheet's black border), and
* faces touching a **duplicated (seam-copy) vertex** are left whole, because the
  two copies store the seam as unrelated edges and splitting one side alone
  opens a hairline crack.

New positions/UVs/skin weights are edge midpoints, so the split itself is
invisible; only the morph makes it matter.

### 2. Two-scale falloff

```
r_x   = 9.2 toward the midline, 4.2 toward the armpit           asymmetric in x
u     = (x ∓ 6.0) / (r_x · side) · s                            s = dome scale
r2    = u² + ((z - 139.0)/r_z)²
main  = (1 - r2)^1.6
r_z   = 11.0 above the apex, 8.0 below it                       per breast
soft  = same shape at 1.35× the size, weight 0.30, power 1.8     chest fullness
w±    = (main + 0.30·soft) / 1.30                               normalised: apex = 1
gate  = smoothstep((y - 6.5)/6.5) · smoothstep((12.0 - |x|)/2.5)
ceil  = smoothstep((152.5 - z)/6)                               soft upper bound
head  = 0 for z ≥ 152.0                                         hard collar stop
depth = max(0, y - 5.0)                                         existing protrusion
gain  = 0.58 + 0.14 · min(1, depth/15)                          cup + fullness
valley= 1 - 0.78 · exp(-(x/2.4)²)                               sternum damping

dy = (w+ + w-) · gate · ceil · head · gain · depth · valley
dz = 0.5 · ((w+ + w-) · gate · ceil · head)²                    bounded lift
dx = 0.7 · (w+ - w-) · gate · ceil · head                       zero on the midline
```

Why each term exists:

| Term | Reason |
| --- | --- |
| asymmetric `r_x` (9.2 medial / 4.2 lateral) | a circular footprint leaked mass into the armpit: at 90° the side read as a long pointed wedge, and the bust width grew by only +0.68 cm because the swell was going *sideways* instead of *forward*. Narrowing the lateral radius and keeping the medial one wide puts the volume in front and lets the two forms meet near the sternum |
| asymmetric `r_z` (11.0 up / 8.0 down) | a breast's fullness sits **below** the nipple, but a tight `r_z_up` makes the top release abruptly (measured −2.4 to −3.9 cm/cm of reach against the base's own −0.1 to −1.2), which reads as "pushed up". Widening the upper radius flattens the upper flank to ≈−1.2 cm/cm, matching the base |
| `soft` dome | a single dome has to end somewhere; at this cup size the rim landed near the neckline as a ridge. The wide shallow dome carries the upper chest down to the base mesh |
| normalising by `1.25` | `cup_gain` keeps meaning "fraction of the existing depth" whatever the soft weight is |
| `dz ∝ fall²` | the first version used `dz = lift · fall`, which raised the whole upper pole by as much as the apex and flattened the top of the breast into a shelf |
| `ceil` smoothstep | `Z_CEILING` used to clip the field to zero in one step, leaving a horizontal ridge across the upper chest |
| `head` hard stop | the soft ceiling alone still handed the topmost collar vertices (~z 152.2) about 50 µm of motion. The field is already ~0.006 there, so cutting it at `HEAD_Z = 152.0` is a 60 µm step across one edge — unresolvable, and it keeps the neck strictly untouched |
| forward gate | the back, flanks and the flat upper chest at the neckline never move |
| lateral gate → 0 at `\|x\| = 13` | the underarm seam and sleeve are 2–3 cm from the chest; an ungated swell caught them and read as a boxy armpit |
| `gain · depth` (not a uniform push) | scales the *existing* bust, so the ribcage and waist do not inflate |
| valley term | without damping the added mass bridges the 0.4 cm sternum dip and the result reads as one barrel |
| `dx` from `w+ - w-` | algebraically zero on x=0 → the midline stays put and the mesh cannot split |

After the displacement a short Laplacian relaxation (3 steps, strength 0.32)
runs on **position-welded** nodes and every duplicate copy is written back to
the same point (`keep_copies_together`); smoothing the copies independently was
what tore the chest seam open.

Normals: rebuilt area-weighted over position-welded vertices (so a UV seam
inside the edit does not become a shading crease) and blended into the source
normals by `smoothstep(1.6 × morph weight)`, leaving the rim shaded exactly as
the base build shipped it.

## Preset and measured result

`cup_gain 0.58`, `round_gain 0.14`, `lift 0.5`, `spread 0.7`, `valley 0.78`, relaxation 3 @ 0.12,
subdivision level 1 (red/green), 3 relaxation steps @ 0.32:

| Metric | Base | Variant |
| --- | --- | --- |
| front reach at the apex (y) | 19.98 cm | **30.37 cm** (+10.39) |
| apex position | x 5.59, z 140.0 | x 6.01, z 140.7 |
| chest width at the apex height | 23.59 cm | 23.59 cm (unchanged: the lateral gate now holds the ribcage) |
| body vertices | 5,645 | **6,060** (+415 from the split) |
| chest silhouette (side) | 19.98 → 17.80 → 12.54 (z = 140…150) | 30.37 → 22.59 → 12.26 |
| cross-section gain at z 137, by \|x\| band | — | 0–1 +3.36, 2–3 +6.23, 5–6 +10.57, 9–10 +6.46, 10–11 +3.18, 11–12 +0.03 |

The silhouette is monotone into the apex and back out again, with no step: the
upper pole reaches the neckline at 13.4 cm against a base 14.2 cm at the same
height, i.e. the swell has decayed to nothing before it touches the collar.

Containment checks (all zero vertices moved): back of the torso, both arms
(`|x| > 14`), legs (`z < 115`), head and neck (`z > 152`). The chest band has
**no open edges** after the split (asserted in `tests/test_bust_variant.py`), and
the added vertices all lie inside `|x| < 14`, `124 < z < 152` — measured span
after the current build: `z 129.97 … 147.05`, `|x| ≤ 10.88`.

The 90° preview cell uses its own `(scale 8.5, y_shift 14.0)` override
(`_render_sheets(..., views={90.0: (...)})`). Without it the bust runs out of
frame and the cell shows the shoulder instead of the profile.

Note on the side view: the base mesh's own profile is a stiff, padded prow
(catsuit over a low-poly torso) — reach drops 19.98 → 12.54 cm between z 140 and
150 in the *unmodified* model. The variant scales that shape, so the upper
shoulder slope is inherited from the base rather than introduced by the morph;
flattening it further would mean rebuilding the shoulder, not the chest.

Preview sheets (tracked, base vs variant on one camera):
[`previews/busty_compare_chest.png`](previews/busty_compare_chest.png) (front, 30°,
90°) and [`previews/busty_compare_full.png`](previews/busty_compare_full.png)
(full body, front and 34°). The builder regenerates both under
`build/pd2-las/previews/` on every run, and the "before" row is rendered from the
base pack's own `miranda.model` — reusing the variant's triangle list with the
base's shorter vertex array collapses the subdivided panels onto the origin.

## Verification

* `tests/test_bust_variant.py` — 17 tests: morph contract (zero off the chest,
  monotonic in `cup_gain`, midline preserved, continuity across the rim,
  cleavage deepening, parameter validation, material-slice scoping, normal
  rebuild), pack identity (distinct id/units/textures, `df_nm` base-name
  registration, base rendering unchanged), and integration against the tracked
  zips (checksums, `BUILD_INFO`, self-consistent payload hashes, viewmodel
  drawables identical to the base pack, `g_body` topology unchanged and only
  chest vertices moved).
* Full suite: `471 passed, 8 skipped`; the one failure
  (`test_build_models.test_retarget_joint_errors_and_palettes`, RightArm 5.71 cm
  vs a 5.0 cm bound) is **pre-existing** — it fails on a clean checkout of the
  branch base with none of this work applied.
* `tools/pd2-las/preview_textured.py` and the high-quality rasterizer in
  `tools/render_mod_previews.py` were used for visual checks; the builder writes
  `build/pd2-las/previews/busty_compare_{full,chest}.png` (base vs variant, one
  camera, textured).

## Traps hit while building this (do not repeat)

1. **The base route must not be re-run.** `dist/Miranda_LAS.zip` in git does not
   reproduce byte-exactly from the current `build_models.py`: the tracked zip
   carries 18 extra `OBJECT3D`/geometry sections and an older section-id layout
   (338 vs 320 sections), while its `.sha256` sidecar matches the *builder's*
   output. The variant therefore never writes the base pack, and
   `build_models.py` was left byte-for-byte untouched (a mid-way edit that
   looked equivalent changed the base zip and was reverted; a regression test
   now pins `las_pack`'s base rendering).
2. **`df_nm` registers the pair's base name**, not the `_df` stem: BeardLib
   appends `_df`/`_nm` itself, so `miranda_body_df` makes it look for
   `miranda_body_df_df`.
3. **Two packs in one `mod_overrides/` share paths.** Hence the `miranda_busty_`
   texture stem prefix, the separate unit directory, icon path and hook name —
   the pack identity (`las_pack.PackIdentity`) exists for exactly this.
4. **`s_body` shares the head block.** The shadow-caster drawable holds the head
   *and* the body, so the morph is scoped by material slice (`miranda_body`) as
   well as by position.
5. **Eye-orbit vertices are not a front-axis oracle** (see model space above).
6. **A bare grid is not a watertightness fixture.** Checking "no open edges" on
   a patch of quads fails immediately — a grid has a genuinely open border. The
   test uses a closed box with an optional duplicated seam column instead.
7. **`_weld_keys` must map every vertex.** It originally only returned ids for
   the indices it was handed, and `smooth_region` then iterated the returned
   *dict* instead of the vertex range — which wired unrelated parts of the body
   together and flung single vertices dozens of centimetres.
8. **`enumerate(dict)` yields keys, not indices.** The relaxation's `members`
   map was built that way, so it pointed at the wrong vertices while still
   looking plausible; the vertex-count assertion caught it, the previews did not.
9. **A duplicated seam vertex has to move as one.** Both copies must get the
   *same displacement* (matched on their pre-morph position), not merely similar
   ones, or the chest seam opens into a hairline tear when the swell stretches
   it.

10. **`_patch_faces` must split only when *every* corner is in the region.**
    With `any(...)` the patch marched one ring at a time down the torso: the
    widened soft dome put vertices at z≈122 (below the 124 guard) and the waist
    started to budge. `all(...)` confines the split to the chest band. Both the
    face test and the vertex test use the same asymmetric `in_region`.
11. **Do not measure cleavage depth with a band `max(y)`.** Taking the maximum
    `y` over a ±2 cm strip around the midline sweeps the inner *slopes* too, so
    the number tracks the whole contour and saturates — it reported a bogus
    1.1 cm valley and sent one iteration chasing a defect that did not exist.
    Use a per-`|x|` cross-section instead (see the table above).
12. **The side "wedge" was the lateral footprint, not the depth.** A circular
    `r_x = 7.0` put as much displacement into the armpit as into the sternum.
    At 90° that reads as a long pointed prow and the bust grows in width
    instead of reach (+0.68 cm before, +0.0 cm after the gate holds, with all
    the extra going forward).

13. **Unbounded Laplacian relaxation smears the texture at the rim.** The
    relaxation step was `cur + strength*(mean(neighbours) - cur)` for every
    vertex above weight 0.004. A neckline vertex sits at weight ~0.006 while the
    breast half a centimetre below it had moved 10 cm, so the step yanked it
    toward that mass. Its triangles are the *coarse* unsubdivided ones, so the
    hex pattern stretched until two of them covered 6.3x their original area —
    texel density down to 16%, which renders as a dark diagonal smear. Fix:
    scale each step by the vertex's own morph weight (`k = strength *
    min(1, weight)`). Max density inflation went 6.34x -> 2.13x.
14. **`SUBDIVIDE_Z` must reach past the displacement, not just the dome.** The
    subdivision stopped at z = 147 while the field still delivered 2 cm of reach
    at 147.5 and 1.5 cm at 148, so a band of coarse triangles sat right where
    the surface was still moving — a visible ledge under the collar. Raising the
    limit to 149 (the collar seam is at 152.2, so the split still cannot
    interpolate UVs across it) took the max inflation to **1.21x with zero
    triangles above 1.5x**.
15. **Matching base triangles by index hides the damage after a split.** The
    first smear metric compared only triangles present in both meshes; the split
    *replaces* the originals, so the worst offenders silently dropped out of the
    sample (320 matched -> 286) and the score improved without the render
    changing. Measure texel density in **spatial bins** instead — that compares
    subdivided and coarse geometry at the same place.

## Still open

* In-game check: `docs/pd2-las/in-game-checklist.md`, plus the two variant
  specifics — the outfit appears as **Miranda Lawson (Busty)** and both LAS
  entries can be worn without a restart.
* The ME2 asset redistribution-rights gate applies to this pack exactly as it
  does to `Miranda_LAS.zip`. Private experimental use only.
