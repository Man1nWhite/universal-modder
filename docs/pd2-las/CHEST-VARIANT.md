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
main  = (1 - r2)^1.6,   r2 = ((x ∓ 6.0)/7.0)² + ((z - 139.0)/r_z)²
r_z   = 5.0 above the apex, 8.5 below it                       per breast
soft  = same shape at 2.0× the size, weight 0.25, power 1.8      chest fullness
w±    = (main + 0.25·soft) / 1.25                               normalised: apex = 1
gate  = smoothstep((y - 6.5)/6.5) · smoothstep((13.0 - |x|)/2.0)
ceil  = smoothstep((154 - z)/5)                                 soft upper bound
depth = max(0, y - 5.0)                                         existing protrusion
gain  = 0.62 + 0.14 · min(1, depth/15)                          cup + fullness
valley= 1 - 0.70 · exp(-(x/2.1)²)                               sternum damping

dy = (w+ + w-) · gate · ceil · gain · depth · valley
dz = 0.5 · ((w+ + w-) · gate · ceil)²                           bounded lift
dx = 0.7 · (w+ - w-) · gate · ceil                              zero on the midline
```

Why each term exists:

| Term | Reason |
| --- | --- |
| asymmetric `r_z` (5.0 up / 8.5 down) | a breast's fullness sits **below** the nipple and its upper pole fades toward the collarbone. The mirrored version put the mass above the apex and the tangent into the neckline |
| `soft` dome | a single dome has to end somewhere; at this cup size the rim landed near the neckline as a ridge. The wide shallow dome carries the upper chest down to the base mesh |
| normalising by `1.25` | `cup_gain` keeps meaning "fraction of the existing depth" whatever the soft weight is |
| `dz ∝ fall²` | the first version used `dz = lift · fall`, which raised the whole upper pole by as much as the apex and flattened the top of the breast into a shelf |
| `ceil` smoothstep | `Z_CEILING` used to clip the field to zero in one step, leaving a horizontal ridge across the upper chest |
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

`cup_gain 0.62`, `round_gain 0.14`, `lift 0.5`, `spread 0.7`, `valley 0.70`,
subdivision level 1 (red/green), 3 relaxation steps @ 0.32:

| Metric | Base | Variant |
| --- | --- | --- |
| front reach at the apex (y) | 19.98 cm | **30.46 cm** (+10.5) |
| apex position | x 5.59, z 140.0 | x 6.12, z 139.7 |
| chest width at the apex height | 23.59 cm | 24.27 cm |
| body vertices | 5,645 | **6,168** (+523 from the split) |
| chest silhouette | 18.6 → 20.0 → 17.9 | 18.6 → 23.7 → 28.4 → 26.2 → 23.4 → 18.1 → 14.2 (z = 136…148) |

The silhouette is monotone into the apex and back out again, with no step: the
upper pole reaches the neckline at 13.4 cm against a base 14.2 cm at the same
height, i.e. the swell has decayed to nothing before it touches the collar.

Containment checks (all zero vertices moved): back of the torso, both arms
(`|x| > 14`), legs (`z < 115`), head and neck (`z > 152`). The chest band has
**no open edges** after the split (asserted in `tests/test_bust_variant.py`), and
the added vertices all lie inside `|x| < 14`, `124 < z < 152`.

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

## Still open

* In-game check: `docs/pd2-las/in-game-checklist.md`, plus the two variant
  specifics — the outfit appears as **Miranda Lawson (Busty)** and both LAS
  entries can be worn without a restart.
* The ME2 asset redistribution-rights gate applies to this pack exactly as it
  does to `Miranda_LAS.zip`. Private experimental use only.
