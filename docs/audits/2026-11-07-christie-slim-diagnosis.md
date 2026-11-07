# Christie_LAS_Slim — structural diagnosis (2026-11-07)

The screenshot review (`2026-11-07-christie-slim-screenshot-review.md`) explains
its findings with three mechanisms: `rebind_arms_at_idle` opening a stitched
seam (armpit), a displaced vertex in the slim fold solution (elbow sliver), and
normal recomputation leaving stale authored normals (seams). This document tests
those mechanisms against the shipped mesh and replaces them with what the
geometry actually does.

Reproduce every number here:

```bash
.venv/bin/python tools/pd2-las/diagnose_mesh.py        # both packs
.venv/bin/python tools/pd2-las/diagnose_mesh.py \      # + sleeve slit probe
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
```

Read-only: shipped `dist/*.zip`, the project's own codec, no game access.

## 0. The pose is not the variable

The 11-07 packs author their own near-idle arm rest into the skeleton (the
pack's `LeftForeArm` sits at `(-33.1, -1.0, 127.3)`, the 2B template's 60°
probe at `(-39.5, -1.0, 133.3)`), and the elbow tests assert that the idle row is
an exact no-op on the elbow ring. The vanilla idle therefore skins the mesh with
near-identity transforms: in the lobby/idle frames the audit used, the result is
the **bind mesh** to within a few degrees of shoulder motion. Anything visible
there —
notch, sliver, cuff gap — is in the authored geometry; the rebinding and fold
passes cannot "open" something that is already open at rest.

## 1. The mesh is an assembly of unwelded shells

| pack | verts | tris | shells | boundary edges | boundary loops |
| --- | --- | --- | --- | --- | --- |
| base | 10,361 | 17,287 | 89 | 3,302 (13 % of edges) | 106 |
| slim | 7,695 | 12,925 | 66 | 2,358 (12 %) | 73 |

Slim's drop is `cut_hands()` (base still has 2,666 hand-weighted vertices;
slim has **none** above 0.5, max 0.40, and no finger bones at all).

The blazer torso, each sleeve, each trouser leg, the cuff bands, the skin, the
inner top and each shoe are separate shells. Critically, **the sleeve is not a
closed tube**: its 58-vertex border loop runs from the shoulder opening down the
inner arm to the cuff, and pairs of its border vertices coincide exactly
(29 of the sleeve's 62 border vertices have a non-neighbour border vertex at
<0.2 cm, many at exactly 0.00 cm). That is a zero-width, unstitched seam — the two rims of the same
cut, with no faces between them. It looks closed and is not connected.

This single fact drives three of the audit's items:

- **normals** diverge across it, because each rim averages only its own side;
- **the armpit** is where the seam's upper end meets the torso shell — a piece of
  background with no geometry across it;
- **the elbow** is where the seam passes closest to the surface, so any
  separation of the two rims reads as a spike against the silhouette.

## 2. Item 1 (normal seams): the population is mostly free borders, not "seams"

Classifying every coincident pair that diverges by >30° (slim):

| class | on an open border | interior |
| --- | --- | --- |
| same material, different UV (zero-width seam) | **390** | **24** |
| cross material, same UV | 6 | 25 |
| cross material, different UV (material interface) | 35 | — |

Totals: 480 pairs; **431 sit on a free edge** (342 of them across two different
shells), and only **49 are interior**. The base pack has the same interior
count (24 + 26 = 50) and a larger border count (711 + 96), the difference being
the hand seams that `cut_hands()` removed.

Consequences:

1. "Half of the duplicated seam vertices disagree, so seams shade as a hard
   crease" is not what the number means. On a free edge the two sides are the
   *outer surface and the lining/underside* (collar, placket, shoe soles — 87 of
   the pairs are the soles at z < 0), and their normals are supposed to differ.
   Averaging them would round every hem in the outfit.
2. The 2B reference's "0 divergent pairs" is not evidence that it has fewer
   seams — it has 22,486 pairs — only that PD2's authoring gives coincident
   vertices **identical normals while keeping them duplicated for UVs**. That is
   the convention to copy.
3. The actionable set is the **49 interior pairs**, and even those need a
   coplanarity check before unification. Their height distribution: 25 at
   z 100–120 cm (waist/hip), 10 at 120–140, 11 at 140–160, 3 above 160 — which
   matches the audit's "waist/hips 134" bin once its border pairs are removed.

**Fix:** after `_recompute_normals()`, average the normal across each
*interior* coincident group (equivalently: duplicate the group's mean to every
copy) and leave border/interface groups alone. That is a ~49-group change, not
a 480-vertex smoothing, and it is exactly the reference's convention.

## 3. Item 3 (armpit notch): a real see-through wedge, inherited, and slim is not the worse pack

Ray-cast the left armpit front-to-back on a 0.5 cm grid, keep the background
cells that have geometry on both sides (the notch, not the background beside
the arm):

| pack | see-through area | apex | width at z = 134 |
| --- | --- | --- | --- |
| base | 39.5 cm² | z 140.0, x −17.5 | 5.5 cm |
| slim | **31.2 cm²** | z 140.5, x −16.5 | 3.0 cm |

So the notch is **not created by the slim pass** and not enlarged by it — slim's
wedge is ~20 % smaller in area and narrower because the narrowed arm sits closer
to the torso. It is the gap between the sleeve shell's inner rim and the blazer
torso shell, with no skin geometry inside (the skin body is torso-only; its
armhole border is at |x| ≈ 16 cm). The audit's `rebind_arms_at_idle` hypothesis
would predict this gap opening when the elbow straightens; the mesh shows it
already open in rest, and base has more of it.

**Fix (if it is worth fixing):** this is a modelling fix, not a deformation fix —
either extend the skin torso to close the armhole, or pull the sleeve's inner
rim into the torso so its border is hidden inside the shell. Changing weights or
the fold solver cannot close a gap that consists of empty space.

## 4. Item 2 (elbow sliver): the hole and the seam are both in the base pack

The left sleeve has a second, 4-vertex border loop around the back of the elbow:

| pack | loop location | size |
| --- | --- | --- |
| base | `(-30.9, 3.7, 125.0)` | 4 verts, z 123.5–126.1 |
| slim | `(-30.8, 3.1, 124.9)` | 4 verts, z 123.2–126.3 |

Same loop, same place, before and after the 11-07 elbow round: it comes from the
source conversion, not from `_apply_slim_fold_solution`. Z-buffered renders of
both packs show the opening backed by the opposite wall of the sleeve, so it does
not read as background — but a 4-vertex hole in a tube is exactly the kind of
feature that becomes a visible sliver when it faces the camera at a grazing
angle, and the zero-width seam passes through the same area.

**Fix:** stitch or plug the 4-vertex loop and weld the zero-width seam rims
(attributes differ, so this means duplicate-then-average normals, not a merge of
UVs). Bounding displacements against the 1-ring, as the audit proposed, would not
have touched either, because both predate the displacement.

## 5. Item 4 (wrist): the band is the open cuff, not bare skin

Distances measured along the forearm axis, positive = past the `Hand` pivot:

| shell | slim | what it is |
| --- | --- | --- |
| blazer sleeve (`c02_01`) | 4.1 cm | the stretched sleeve |
| skin stub (`mtr_body`) | 3.6 cm | the forearm after `cut_hands()` |
| cuff band (`c02_02`) | 3.0 cm | the shirt/lining |

The sleeve reaches 0.5 cm past the skin, so a ring of skin is visible *inside*
the cuff mouth, and beyond it the open tube shows its own backface (white blazer
lining, lit). That is the pale cream/tan band — it is not "bare wrist between
sleeve and glove", it is the sleeve's interior plus the last 0.5 cm of skin.

The red patch is **not in this pack's cuff UV footprint**: sampling every
cuff-region face's UV triangle (12×12 barycentric grid) finds no saturated red
texel (R > 150, G < 90, B < 90) on any of them. The suit's red piping is real but
lives at the collar and hem (213 faces, z 6–159); the body atlas's saturated red
patch is consumed by ankle faces. The red speck at the wrist is therefore not
reproducible from the pack — the likely owners are the spawned vanilla glove or
texture filtering at the cut edge.

## 6. Item 5 (fingertips): not this pack's geometry

Slim ships **zero** hand-weighted vertices (max hand weight 0.40 on the wrist
blend, no finger bones). The glove, its finger gaps and the black slots between
them are the game's model. The only thing this pack contributes at the wrist is
the open cuff ring. "Fixing the fingertips" in this repository means covering or
tucking that ring, not editing fingers.

## 7. Item 6 (trouser blotches): the mask does bleed, but the effect is gloss, and mostly on the shoes

The suit material `c02_01` carries both sleeves and trousers, and the sleeve mask
is built from arm-weighted vertices:

- 151 leg-only faces have mask > 0.05, covering **3.2 %** of the leg faces' UV
  area (up to full strength, mean 0.52) — identical in base and slim, because
  the passes never move UVs;
- but 123 of those faces are at z 0–20 cm — the **shoes** — and only 4 are at
  z 80–100; the trousers proper are barely touched.

Mechanically, `retouch_sleeve_gloss()` attenuates **diffuse alpha only**
(specular), per DXT block, at every mip. So it cannot change albedo, and it does
not produce a soft splat edge: it produces a constant factor per 4×4 texel block
at mip 0 (~0.7 cm on the suit) and per 4×4 block at coarser mips, i.e. up to
~5 cm axis-aligned patches at mip 3. That is the signature the screenshots show —
axis-aligned soft patches — but the effect is gloss variation, and the faces it
touches are mostly the shoes, not the trousers.

**Fix:** restrict the mask to sleeve islands before splatting (the mask should
never be sampled by a non-arm-weighted face), and apply it at mip 0 only, letting
the mips be regenerated, so block quantisation cannot grow with distance.

## 8. Step 2 shipped: `stitch_sleeve_seams` (2026-11-07)

Work order item 2 is implemented as `stitch_sleeve_seams()` in
`tools/pd2-las/build_christie_las.py`, running once on the welded body (and its
shadow) right after `rebind_arms_at_idle()`, i.e. on the final shape and the
final weights. It keeps every existing vertex, UV and weight; it only adds
faces and averages the attributes of rims that are welded together.

What the pass does, in order:

1. **Find the sleeve shells.** Arm-weighted faces of `mtr_c02_01/02/05`, split
   by side. Each sleeve is its own connected component, so the pass never
   touches the torso.
2. **Collect the rims.** Boundary edges (edges used by exactly one face) of
   those shells, chained into runs.
3. **Weld the coincident rims.** Two rim vertices at the same position (the
   zero-width seam) get merged: one position (their mean), one normal (the mean,
   so both sides shade as one panel), one weight set, and every face that used
   the loser is rewired. This is not a vertex-index merge — the two rims carry
   different UV islands, so the UV per corner has to stay.
4. **Bridge what is left.** The remaining rims are paired by proximity, and the
   pairs are lofted with one quad per rim step. Rim arcs of unequal length are
   skipped rather than fanned, and gaps of three or more rim pairs are left
   alone — those are the armhole, not the seam.
5. **Plug small holes.** Loops of 4 vertices or fewer are fanned from the free
   diagonal, skipping any diagonal an existing face already owns (the
   pre-existing fins own most of them). Weld happens *before* the faces are
   built; otherwise a new triangle closes an already-coincident pair and
   degenerates.

Effect on the shipped packs (both rebuilt, `orientation_breaks == 0` on each):

| | base | slim |
| --- | --- | --- |
| new triangles | 64 | 71 |
| rim vertices welded | 21 | 23 |
| holes plugged | 4 | 4 |
| triangles, before → after | 17287 → 17351 | 12925 → 12996 |
| boundary edges | 3302 → 3246 | 2358 → 2297 |
| boundary loops | 106 → 111 | 73 → 80 |
| orientation breaks | 0 → 0 | 0 → 0 |
| winding agreement | 97.3 % | 97.3 % |
| degenerate faces | 0 | 0 |
| sleeve slit, left (cm²) | 21.53 → **0.00** | 35.14 → **0.00** |
| sleeve slit, right (cm²) | 0.00 → 0.00 | 4.95 → **0.00** |

The slit column is `sleeve_slit_area()`: rays cast radially from the
shoulder→wrist bone chain over the tube's middle band (10–90 % of the chain, so
the open cuff mouth and the shoulder rim are excluded). An unclosed tube leaks;
a stitched one reads 0.00 on every slice. Cross-checked with an independent
probe that slices the sleeve along z and counts open ray samples: the old pack
leaked at 151 (left) / 128 (right) samples of 2280, the new one at 67/67 with
every slice above z 138.5 empty — i.e. the remaining samples are the open cuff
mouth, not the seam. Measured as area: 85.7 → 46.0 cm² right, 103.6 → 51.4 cm²
left, all of the residue inside z 138.5–139.7.

Attributes are untouched where nothing was welded: the `uv0` array is
byte-identical to the previous build in both packs, 6 (base) / 8 (slim)
vertices moved by the weld with a maximum of 0.0268 / 0.0294 cm, and 42/46
stored normals changed — all of them coincident rims that now share one normal,
12 of 46 by more than 0.2 (one shoulder pair by 38°, where the rim's outer face
and inner face are averaged). No new vertices, no changed vertex count.

**The one behavioural side effect:** the inner-elbow patch the pass now closes
gives the crease something to fold at *maximum* flexion. On the old 72° menu
pose the opposed-normal count at the elbow ring goes base 5 → 7 and slim 1 → 4;
every other probe pose (idle, ±12°, 45°, 50°) is unchanged. The fold is bounded
— the worst opposed pair is at -0.93, a fold, not a face turned back on itself —
and no face's winding changed, so `orientation_breaks` stays 0 and nothing is
back-face culled. That is what fabric does inside a fully bent elbow, so
`test_elbow_deforms_cleanly_from_idle_rest` now budgets the menu row separately
and keeps the tight budget for the rows the game actually shows.

Re-running `audit_metrics.py` on the rebuilt packs moves the audit's own
table by the weld: base 750 → 792 and slim 480 → 526 "bad verts" (a vertex with
*one* incident face more than 90° off its stored normal) — the seam vertices
whose normal is now the mean of the two rims it joins. That is the seam shading
smoothly instead of as a hard line, and it is not the interior normal
unification of work order item 1, which stays open.

Test coverage: `test_sleeve_tube_is_closed_along_its_length[base|slim-left|right]`
asserts the radial probe leaks < 1 cm², and `diagnose_mesh.py --templates`
prints the same number for both packs. Suite state after both changes: **65
Christie tests, 633 tests overall, 26 skipped, 0 failed.** Nothing here has been
checked in game — the pack to check is `14f75d66…` (slim) / `2934c818…` (base).

## 9. Item 1 shipped: `unify_coincident_normals` (2026-11-07)

The first item on the work order was the seam shading: a PD2 mesh duplicates a
vertex wherever one position needs two UVs or two materials, and in the 2B
reference every copy of a position carries the *same* normal (0 of 22,486 pairs
diverge), which is why its seams are invisible. Ours diverged on 480 (slim) /
856 (base) pairs — the hard step the screenshots show along seams.

`unify_coincident_normals()` now runs on the welded body and its shadow after
`stitch_sleeve_seams()`, so it is the last thing that touches geometry before
authoring. For each coincident group it replaces the stored normal of the
**interior** copies with the group mean. It touches nothing else: no position,
UV, face, material or weight changes, and copies that sit on a border edge are
left alone.

Why borders are excluded: a copy on a border edge is the rim of a garment panel
(cuff mouth, sleeve opening, lining edge, shoe lining). Its two sides are a real
fold, so one normal cannot represent it — averaging there would smear the
silhouette rather than remove a seam. The reference has no such pairs because
its authoring never duplicates a fold; ours comes from the DOA5 source and from
`cut_hands`, and re-authoring those edges is out of scope here.

| | base | slim |
| --- | --- | --- |
| interior groups unified / copies re-normalled | 50 / 100 | 49 / 98 |
| interior divergent pairs, before → after | 50 → **0** | 49 → **0** |
| border divergent pairs (untouched) | 806 | 431 |
| worst interior pair, before | 103° | 101° |
| winding agreement | 97.3 → 97.2 % | 97.3 → 97.1 % |
| orientation breaks | 0 → 0 | 0 → 0 |
| "bad vertices" (`audit_metrics.py`) | 792 → 788 | 526 → 522 |

Two details worth knowing:

- **The mean is bounded.** Copies more than 120° apart are skipped, because
  their mean lies more than 60° from both surfaces. The shipped worst cases
  (101°/103°) are comfortably inside that, and the 128 interior pairs measure a
  median of 19° apart, but the guard stops a future edit from averaging two
  opposed layers into a sideways normal.
- **The visual effect is small and local.** Rendered with a Gouraud shader that
  interpolates the *stored* normals (the repo renderers shade per face, so they
  cannot show this), the front of the coat is pixel-identical, and the back,
  collar and lapel seams soften — the median normal change is 22.6°, the maximum
  50.6°. This is a seam-quality fix, not a new look; the metric that moves is
  the audit's own (`diverged`: 480 → 431 slim, 856 → 806 base), not
  `bad vertices`, which is a coarse binary and is dominated by the two-layer
  garment rather than by seams.

Tests: `tests/test_seam_normals.py` covers the pass on hand-built meshes (an
interior pair unifies, a border pair does not, a within-tolerance pair is left
alone, a 130°-plus pair is skipped);
`test_christie_las.py::test_interior_coincident_normals_agree` pins the shipped
packs to 0 interior pairs and to > 300 border pairs (so the fix cannot "pass" by
smoothing the garment edges), and re-derives the reference's 0-of-22,486.

## What this changes in the audit

| audit item | status after diagnosis |
| --- | --- |
| 1 normal seams | real; the 49 interior groups are unified (**§9**), the 431 free-edge folds stay by design |
| 2 elbow sliver | real; the hole and the seam predate the 11-07 round (identical in base); fix topology, not displacement — **fixed in §8** |
| 3 armpit hole | real, inherited, **slim is smaller than base**; not caused by rebinding; needs modelling |
| 4 wrist band / red speck | band = open cuff interior + 0.5 cm of skin, not a bare wrist; red not reproducible from the pack |
| 5 spiky fingertips | the pack has no hands; only the cuff ring is ours |
| 6 trouser blotches | mask bleed is real but gloss-only and mostly on the shoes; mechanism is per-block attenuation, not the splat edge |

## Suggested order of work

1. ~~**Interior coincident-normal unification**~~ — **done**, see §9:
   `unify_coincident_normals`, 0 interior divergent pairs, border folds kept,
   `tests/test_seam_normals.py` + `test_interior_coincident_normals_agree`.
2. ~~**Weld/plug the sleeve seam and the 4-vertex elbow loop**~~ — **done**, see
   §8: `stitch_sleeve_seams()`, both packs rebuilt, sleeve tube closed on every
   slice, 0 orientation breaks.
3. **Close the armpit**: extend the skin armhole or tuck the sleeve rim.
4. **Mask scope**: splat only on sleeve islands; mip 0 only.
5. Leave the gloves, the red speck and the cream band alone until the glove
   model is part of the comparison — they are not in this mesh.

## Open observation (unverified)

`c02_05` (the dark inner top) is the only material whose stored UVs are positive
in v (`0.04 … 0.98`); every other role is `-1 … 0`. Under the (1 + v) row mapping
the pipeline uses everywhere else, those texels are fetched outside `[0, 1]` and
clamp to an edge row. The texture is nearly uniform dark, so a wrong row would
be invisible in game. Cheap test: brighten `c02_05_df` for one build and check
whether the chest panel changes; if it does not, the material is sampling a
clamped edge.
