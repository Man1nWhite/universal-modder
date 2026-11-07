# Christie_LAS_Slim — structural diagnosis (2026-11-07)

> **Historical scope:** this diagnosis investigates the earlier 11-frame review
> and records subsequent offline mesh changes. The user has since replaced the
> screenshot archive with 15 PNGs. The [current screenshot review](2026-11-07-christie-slim-screenshot-review.md)
> uses the new filenames/coordinates and separates visible dark forearm patches,
> neck bands and coarse suit shading from these structural checks. Old screenshot
> coordinates below refer to the former batch in Git history. Its installed
> hash and the new batch's installed hash must not be conflated. A closed sleeve
> probe is not visual clearance for those appearances.

The earlier 11-frame screenshot review (the previous version of
`2026-11-07-christie-slim-screenshot-review.md`) explained
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

**What the ray cast actually says (measured 2026-11-07).** `cast_front` does not
cull backfaces — any triangle hit counts — so a *miss* is a ray that passes
through **no geometry at all**. The wedge is therefore not a hole in a surface
and not the sleeve's interior showing through: it is the empty space between two
separate silhouette blocks, the sleeve shell on the lateral side and the blazer
torso on the medial side, with the background visible between them. There is
nothing to patch — closing it means moving one block into the other.

Measured rim-to-torso clearance, sleeve armhole loop 17 (22 verts, shell 9),
nearest vertex outside the sleeve shells:

| rim vertex | z | clearance |
| --- | --- | --- |
| v2013 | 153.3 | 0.00 cm (coincident with the torso) |
| v2010 | 148.5 | 0.00 cm |
| v2003 | 143.7 | 0.00 cm |
| v1997 | 141.1 | 0.00 cm |
| v2002 | 135.0 | 8.66 cm |
| v2068 | 130.3 | 13.14 cm |

So the armhole's **upper arc is already sewn to the torso** (exactly what
`unify_coincident_normals` then shades) and its lower arc is free by design —
that is what an armhole is. The pack has no modelling error here; the slit the
screenshots show is the gap between a hanging arm and the waist.

**The reference does not close it either.** Same ray cast, same window, on the
2B template (`g_body` of `2b.model`):

| | total | z 131–136 | z 136–141 | z ≥ 146 |
| --- | --- | --- | --- | --- |
| 2B template | 8.2 cm² | **0.0 cm²** | 7.8 cm² | 0.5 cm² |
| Christie slim | 31.2 cm² | 11.5 cm² | 19.8 cm² | 0.0 cm² |

Read that with the metric's own bias in mind: a cell only counts when there is
geometry within 6 cm on **both** sides, so a *wider* arm/body gap scores *fewer*
cells. 2B's clearance at z 134 is 15.5 cm against Christie's 9.5 cm — the
reference scores zero below z 136 largely because its arm hangs further out, not
because its armhole is closed. The honest reading is that both models carry an
open arm/body gap and the tighter one produces more "crack" cells.

**Decision: no build change.** The gap is inherited (base 39.5 cm², slim
31.2 cm²), it is empty space rather than a hole, and the only ways to remove it
— pull the sleeve's underarm into the torso, or bridge rim to torso with a
gusset — change the silhouette and cannot be validated without an in-game pose
test. Recorded here so the next round starts from the measurement instead of
re-deriving it.

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

**Fix, shipped in this build.** Two changes, both in
`tools/pd2-las/build_christie_las.py`:

1. `sleeve_uv_mask(uvs, faces)` replaces the 24-texel vertex discs: the UV
   triangle of every face whose mean arm-chain share exceeds `SLEEVE_BONE_SHARE`
   is rasterised into the 1024 atlas (PIL polygon fill), blurred by
   `SLEEVE_FEATHER_TEXELS = 3.0` and **clipped back to the unblurred footprint**,
   so the feather softens the edge of the change without ever reaching a texel
   the sleeve does not own.
2. `retouch_sleeve_gloss()` attenuates **mip 0 only** and rebuilds the whole
   chain with `pd2_dds.mip_payloads_from_mip0` + `pack_dds`, so the mips are a
   filtered version of one full-resolution mask instead of a separately
   quantised one at every level — the stair-stepping cannot grow with distance.

Result off the rebuilt packs (same numbers in base and slim, the mask is a UV
property):

| | vertex discs | face raster |
| --- | --- | --- |
| leg-only UV area touched | 3.2 % | **0.8 %** |
| leg-only faces touched | 151 | **33** |
| where | 123 of 151 at z 0–20 (shoes) | all 33 at z 2.6–11.9 (shoes) |
| sleeve faces covered | — | 100 % of 1,740 |
| atlas area covered | — | 13.3 % |

The 33 remaining faces are **atlas sharing, not mask reach**: their UVs sit
inside the sleeve islands of `c02_01_df` (mask value 0.29–1.00 at their
centroids), so those texels are sampled by both the sleeve and the boot. No mask
can separate them; that would need the boots re-UV'd.

Attenuation still lands where it should — mean alpha inside the mask 5.51 against
11.25 outside (0.49×, `SLEEVE_GLOSS_ATTEN = 0.55` after DXT), with the mip count
(11) and the texture payload (1,398,256 B) unchanged, so the change is scope and
sampling only, not a different texture format.

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
Christie tests, 633 tests overall, 26 skipped, 0 failed** (after the gloss pass
of §7: 67 / 635, same skips). Nothing here has been
checked in game. The packs to check were `14f75d66…` (slim) / `2934c818…` (base)
at the time of writing; the gloss pass of §7 rebuilt them again, and the current
bytes are `5e55745f…70b4d` (slim) / `c57edbba…1f765` (base), which are the ones in
`dist/` and the ones an in-game check would cover.

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

## 10. Item 7 (throat): the head's neck skirt, measured — and a correction

The review called this "almost certainly the heister head mod's UV seam, not
this pack", and left it alone because the head was not in the repository. It is:
`tools/build_joy_head_mods.py` builds the nine head-replacement packs, and four
of them mount a Miranda head over a heister body — the combination a Christie LAS
player actually sees, because LAS keeps the heister's head.
`tools/pd2-las/neck_junction.py` puts the body and a head in one space and
ray-casts the throat on a 0.25 cm grid (x ±6 cm, z 149–161 cm).

### 10.1 The first version of this section was read backwards

The first pass published two numbers here: "~70 % of the throat is the head's
skin" and "110 of 110 of the head's neck border edges are the front-most
surface", and concluded that the head's rim at z 149.5 was the visible hard line.
Both are wrong, for three separate reasons, all in the measuring tool:

1. **`+y` is the character's front, so the front-most surface has the largest
   y.** `front_depth` returns the largest y of any hit — correct. The test in
   `border_exposure` then demanded `depth > y - 0.05` to call an edge *exposed*
   when that is precisely the condition for a body surface standing in front of
   it. The count was inverted: 110/110 "front-most" meant 110/110 **covered**.
2. **`junction`'s winner test had the same inversion.** `body_wins` used
   `db <= dh + 0.02`, which picks the mesh *behind* the body's surface. The
   published "head in front 69.3 %" was the body's share.
3. **The border set was wrong, and the render was taken from behind.**
   `diagnose_mesh.boundary` returns the head's **53** boundary loops — hair
   sheets and lashes included — and one of them, the hair outline, spans the
   whole 38.6 cm of the model; the neck sheet's rim is a 98–106 edge loop inside
   that soup. And `_render` placed the camera at y −40, i.e. behind the
   character, so the committed PNG showed the **nape and the hair** hanging over
   the blazer's back, not the throat.

The direction is now pinned by two tests, so it cannot silently invert again:
`test_the_front_camera_sees_the_largest_y` (front = +y, `preview_textured`'s
"Portrait Front" looks straight at the face, which is the head's narrow
y-maximum) and `test_border_exposure_reads_both_sides_the_right_way_round`
(a slab in front of the rim covers it; the same slab behind does not).
`border_exposure` now measures the neck rim exactly as `extend_neck_skirt` picks
it (`neck_rim_edges`: edges used once, both ends z ≤ 156, within 8.5 cm of the
neck axis), from the front **and** from behind, and `junction` reports
coincident surfaces (≤ 2 mm) as body rather than as see-through.

### 10.2 What the corrected measurement says

`dist/Christie_LAS.zip` with the four `Miranda_L4D2_over_*` heads, before and
after the skirt of §10.3:

| | before (z 149.5 rim) | after (z 143.0 rim) |
| --- | --- | --- |
| head neck rim, over Joy | 106 edges, z 149.5, r 5.98 | 120 edges, z 143.0, r 5.78 |
| head neck rim, over Clover/Bonnie/Sydney | 98 edges, z 149.5, r 5.90 | 114 edges, z 143.0, r 5.70 |
| rim edges exposed from the front | **0** | **0** |
| rim edges exposed from behind | **0** | **0** |
| body in front of the throat window, Joy | 99.5 % | 99.5 % |
| head in front, Joy | 0.5 % | 0.5 % |
| body in front, Clover/Bonnie/Sydney | 84.3 % | 84.3 % |
| head in front, Clover/Bonnie/Sydney | 15.7 % | 15.7 % |
| see-through | 0.0 % | 0.0 % |

So: **the head's neck is almost never the visible surface of the Christie
throat.** The body's own collar, blazer and chest skin own 84–99.5 % of the
window, nothing leaves a gap, and the head's rim is buried in the torso behind
it from both sides. The tan of the review's boundary is the body's own skin
(`mtr_body`), not the head's neck; the pale side is the white blazer. And the
body does not split *itself* either: its throat samples one uniform tan on both
sides (205,157,128 on the front band, and the darker samples at x ±3.5–5.0 are
the same value mirrored), which the earlier pass already found.

`neck_junction.py --ab <before.zip>` settles that cell by cell: between the
2026-11-05 packs and the skirted ones, **0 of 2,401 throat cells change owner**
(body 0, head 0, miss 0). The textured front and back composites taken during
this round (`preview_textured.render` over body + head, z 156 ± 11 cm) came out
byte-identical as well.

The tinted render that ships with this section
(`docs/pd2-las/renders/neck_junction_christie_joy.png`, head orange, body grey)
is now taken from the **front** and says the same thing: the throat is body-grey
edge to edge, with two orange slivers at the shoulders where the head's sheets
are the nearest surface.

### 10.3 The skirt shipped on the L4D2 path — and the render caught it on Romance

`build_joy_head_mods.py` now runs `extend_neck_skirt()` on the neck sheet of the
**L4D2** head path (`build_l4d2_meshes`, `mid == 3`): it finds the rim edges of
§10.1 item 3 and extrudes one ring, dropped 6.5 cm, tucked to 88 % of the radius,
0.5 cm towards the front, carrying the rim's normals and UVs and stitched with two
triangles per rim edge, winding chosen from the rim's own faces. Existing indices
do not move; `compute_joy_head_weights` then puts the new ring on Neck/Spine2 by
z. The head drawable goes **4,402 verts / 7,109 tris -> 4,515 / 7,321** (7,305 for
Clover/Bonnie/Sydney), its lowest point **z 149.48 -> 142.98**.

The **Romance** path does not take it, and that is a bug the renders found rather
than the numbers. On that rig the neck skin is part of the `Hair` mesh, together
with the hair cap and the 1.5 mm flyaway wire strips, so the same rim filter caught
**741 hair-sheet edges instead of the neck's ~145**; the wire pass that follows
(`keep_v` / `wire_mask`, which squashes everything outside the largest triangle
component to 20 % about `(0, 6, 175)`) then treated the new ring as a flyaway and
dragged it into the head: **+340 verts at z 168-170 and +2,318 triangles** instead
of +145 / +290 at z 143, and the rendered previews showed a pale lump under the
chin on all four Romance packs
(`docs/pd2-las/renders/neck_skirt_romance_regression.png`: the neck of
`Miranda_Romance_over_Clover`, 2026-11-05 build above, skirted build below, 4x).
Re-rendering `docs/previews/` was what surfaced it;
`neck_junction.py` could not, because the squashed ring is hidden and the throat
window is unaffected. The four Romance packs were rebuilt back to their
2026-11-05 bytes, and `tests/test_pd2_las.py` now pins head vert/tri counts and the
lowest vertex for all eight packs, so the two paths cannot be confused again.

Why ship the L4D2 skirt when it changes nothing on Christie: it costs 14.9 kB in
the Joy pack, it is entirely inside the torso there (the textured front and back
composites are byte-identical), and it makes the head's open end independent of how
deep the body's neckline is. The neckline that hides it on Christie is Christie's;
the measuring window cannot speak for a collar that sits lower.

### 10.4 Item 7 is therefore open, with a bisect instead of a theory

Nothing measured offline on this body splits the throat, so the next step is a
two-minute in-game bisect rather than another hypothesis:

1. Uninstall the head pack, keep `Christie_LAS_Slim` — LAS keeps the vanilla
   heister head, so this is the body alone.
2. If the pale/tan boundary is still there, it is the body (the blazer's neckline
   against `mtr_body`, or the in-game lighting across it) and it belongs in this
   audit, not in the head packs.
3. If it is gone, it is the head pack, and the next measurement is the hair
   sheets, which are the only part of that head that is still in front of the
   blazer — from behind, not on the throat.

Two cheaper things are already ruled out: the head's neck rim (§10.2) and the
body's own UVs (§10.2).

## What this changes in the audit

| audit item | status after diagnosis |
| --- | --- |
| 1 normal seams | real; the 49 interior groups are unified (**§9**), the 431 free-edge folds stay by design |
| 2 elbow sliver | the inherited hole and sleeve seam were **closed structurally in §8**; that does not establish that the old outer-silhouette sliver is gone in game. The replacement review keeps visual clearance open and separately records dark rear-forearm patches |
| 3 armpit hole | **not a hole**: the ray cast passes through empty space between the arm and the torso, the armhole's upper arc is sewn (0.00 cm) and the reference carries the same kind of gap; inherited, slim smaller than base. No build change made (§3) |
| 4 wrist band / red speck | band = open cuff interior + 0.5 cm of skin, not a bare wrist; red not reproducible from the pack |
| 5 spiky fingertips | the pack has no hands; only the cuff ring is ours |
| 6 trouser blotches | mask bleed was real, gloss-only, mostly on the shoes; mechanism was per-block attenuation, not the splat edge — **fixed**: face-raster mask, mip 0 only, leg UV coverage 3.2 % → 0.8 % (§7) |
| 7 neck tonal split | measured twice and corrected once (§10): the head's neck rim is **not** the visible line (0 of 98–120 rim edges exposed, front or back; the body owns 84.3–99.5 % of the throat window) and the body's own UVs do not split it either. The skirt shipped on the L4D2 path as insurance (§10.3). **Open**; next step is the in-game bisect of §10.4 |

## Suggested order of work

1. ~~**Interior coincident-normal unification**~~ — **done**, see §9:
   `unify_coincident_normals`, 0 interior divergent pairs, border folds kept,
   `tests/test_seam_normals.py` + `test_interior_coincident_normals_agree`.
2. ~~**Weld/plug the sleeve seam and the 4-vertex elbow loop**~~ — **done**, see
   §8: `stitch_sleeve_seams()`, both packs rebuilt, sleeve tube closed on every
   slice, 0 orientation breaks.
3. ~~**Close the armpit**~~ — **measured and closed as "no defect"**, see §3:
   the ray cast passes through empty space, the armhole's upper arc is welded to
   the torso, and the 2B reference has the same arm/body gap. No build change.
4. ~~**Mask scope**~~ — **done**, see §7: the mask is rasterised from the sleeve
   UV faces and clipped to that footprint, mip 0 is attenuated and the pyramid
   regenerated from it.
5. **Neck split** — measured twice, corrected once (§10): the head's neck rim is
   **not** the visible line (0 of 98–120 rim edges exposed, front or back; the
   body owns 84–99.5 % of the throat window), and the skirt extension shipped as
   insurance, not as the cure. **Open**, with the in-game bisect of §10.4 next.
6. Leave the gloves, the red speck and the cream band alone until the glove
   model is part of the comparison — they are not in this mesh.

## Open observation (unverified)

`c02_05` (the dark inner top) is the only material whose stored UVs are positive
in v (`0.04 … 0.98`); every other role is `-1 … 0`. Under the (1 + v) row mapping
the pipeline uses everywhere else, those texels are fetched outside `[0, 1]` and
clamp to an edge row. The texture is nearly uniform dark, so a wrong row would
be invisible in game. Cheap test: brighten `c02_05_df` for one build and check
whether the chest panel changes; if it does not, the material is sampling a
clamped edge.
