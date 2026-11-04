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

Pure function of the bind-pose position, so it is identical on every drawable
and trivially testable:

```
w±    = (1 - r2)²,  r2 = ((x ∓ 6.0)/6.6)² + ((z - 141.5)/10.6)²      per breast
gate  = smoothstep((y - 7.5)/8) · smoothstep((12.2 - |x|)/2.2)        front + lateral
depth = max(0, y - 5.0)                                               existing protrusion
gain  = 0.50 + 0.12 · min(1, depth/15)                                cup + fullness
valley= 1 - 0.85 · exp(-(x/1.6)²)                                     sternum damping

dy = (w+ + w-) · gate · gain · depth · valley
dz = 0.7 · (w+ + w-) · gate
dx = 1.2 · (w+ - w-) · gate                                           zero on the midline
```

Why each term exists:

| Term | Reason |
| --- | --- |
| `(1 - r2)²` | zero value **and** zero slope at the rim → no crease where the edit meets untouched geometry |
| forward gate | the back, flanks and the flat upper chest at the neckline never move |
| lateral gate → 0 at `|x| = 12.2` | the underarm seam and sleeve are 2–3 cm away from the chest; an ungated swell caught them and read as a boxy armpit |
| `gain · depth` (not a uniform push) | scales the *existing* bust, so the ribcage and waist do not inflate |
| valley term | the source has a 0.5 cm dip; without damping the added mass bridges it and the result reads as one barrel |
| `dx` from `w+ - w-` | algebraically zero on x=0 → the midline stays put and the mesh cannot split |

Normals: rebuilt area-weighted over position-welded vertices (so a UV seam
inside the edit does not become a shading crease) and blended into the source
normals by `smoothstep(2.5 × morph weight)`, leaving the rim shaded exactly as
the base build shipped it.

## Preset and measured result

`cup_gain 0.50`, `round_gain 0.12`, `lift 0.7`, `spread 1.2`, `valley 0.85`:

| Metric | Base | Variant |
| --- | --- | --- |
| front reach at the apex (y) | 19.98 cm | **28.84 cm** (+8.85) |
| depth over the chest wall | 14.98 cm | **23.84 cm** |
| breast-to-sternum valley depth | 0.41 cm | **9.19 cm** |
| chest-band volume proxy | 1434.8 | **1805.5** (+25.8 %) |
| body vertices moved | — | 195 of 5,645 (max 9.03 cm, mean 1.95 cm) |
| moved-vertex envelope | — | x ±13.6, y ≥ 6.1, z 132.1…148.5 |

Containment checks (all zero vertices moved): back of the torso, both arms
(`|x| > 14`), legs (`z < 115`), head and neck (`z > 152`).

Preview sheets (tracked, base vs variant on one camera):
[`previews/busty_compare_chest.png`](previews/busty_compare_chest.png) (front, 30°,
90°) and [`previews/busty_compare_full.png`](previews/busty_compare_full.png)
(full body, front and 34°). The builder regenerates both under
`build/pd2-las/previews/` on every run.

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

## Still open

* In-game check: `docs/pd2-las/in-game-checklist.md`, plus the two variant
  specifics — the outfit appears as **Miranda Lawson (Busty)** and both LAS
  entries can be worn without a restart.
* The ME2 asset redistribution-rights gate applies to this pack exactly as it
  does to `Miranda_LAS.zip`. Private experimental use only.
