# Christie LAS packs — DOA5 Christie as body-only PAYDAY 2 LAS outfits

- `dist/Christie_LAS.zip` (+ `.sha256`, sha256 `fa77d312…0bc92ae`, 4,767,247 B)
  — full body incl. Christie's hands.
- `dist/Christie_LAS_Slim.zip` (+ `.sha256`, sha256 `5b389eaf…16df085`,
  4,201,848 B) — 10% thinner torso/legs, 20%
  thinner arms in cross-section (plus a 10% bicep tuck, so the upper-arm belly
  lands at 0.736 of base — see `test_slim_cross_section_ratios`), **and no
  hands** (`--variant slim`; the separate no-hands pack was removed — slim
  supersedes it). The v4 slim pass
  (`slim_group`) works on the bind-pose mesh only — skeleton, bone lengths
  and skin weights untouched — applying per-segment radial cross-section
  scaling `p' = p + Σ α_j (s_j − 1) r_j` with separate joint-anchored axes for
  each upper arm / forearm / thigh / calf (s = 0.80 arms, 0.90 legs, and the
  forearm alpha now fades out over the last 8 cm before the bitwise-unchanged
  cuff ring — the old full-strength-into-the-ring pass pinched the mid-arm
  against an untouched mouth and flared 2.27x; it is 1.17x now, base 1.04x),
  a Z-monotonic torso centerline for the pelvis/spine (s = 0.90, neck fade),
  shoulder and crotch weight routing, an explicit identity field for
  protected head/hands/feet, smoothstep fades to 1.0 at the wrist/ankle with
  the surviving cuff ring enforced bitwise unchanged, and normals recomputed
  from the final triangles. Height is preserved (final min/max z match the
  base pack); verified principal cross-section radii: upper arm 0.736, forearm
  0.800, legs 0.900 vs base. Both packs' diffuse alpha (PD2's specular mask)
  is additionally attenuated by ~55% inside the sleeve UV regions — in game
  the sleeves read glossier than the torso (see "Sleeve gloss" below). Then
  the hands
  are cut at the wrist, the sleeves are stretched deep past the wrist joint
  (blazer −4.5 cm, skin −3.5 cm, shirt −3.0 cm) so the spawned glove sits well
  inside the cuff in every pose, plus a `*_glove_adapter.lua` compat hook
  (default glove restored, adapter re-enabled) so the heister's changeable
  in-game gloves show through the sleeves. Applied before the fps extraction
  so the viewmodel arms match.

**2026-11-06 in-game fix round** (user screenshots of the slim pack): the
elbow X-fold, the wrist seam and the sleeve gloss are addressed by
`widen_elbow_blend` (both packs, weights only), the forearm wrist fade
(slim), and the diffuse-alpha sleeve retouch (both packs) — see the sections
below. The 25%-arm slim scale was rebalanced to 20% + tuck at the same time.

**2026-11-07 elbow round** — *the 11-06 poses rotated the elbow about the
wrong axis*, so the fold they tuned against was a twisted sleeve, not a bent
elbow (see [The elbow, measured on the elbow's own
axis](#the-elbow-measured-on-the-elbows-own-axis-2026-11-07)). On the real
flexion axis the shipped sleeve still crumpled when the bind's 72° elbow
straightened to the in-game idle's ~12°; `trim_elbows` now also de-puffs the
**outer** side of the bend (wider window, `ELBOW_OUTER_TRIM = 0.65`), which
takes the worst edge in the elbow window from 3.12 cm of shortening to
2.08 cm and from 0.187 to 0.295 of bind length, with 0 inverted faces. Packs
rebuilt (`fa77d312…` base, `5b389eaf…` slim), elbow thickness at the joint
7.18 → **6.69 cm** (2B reference 7.03). Tests renamed/re-based:
`test_elbow_bend_axis_is_flexion`, `test_elbow_does_not_crumple_at_the_idle_angle`.

Both are Legendary Armour Skins add-ons built from `references/Christie.zip`
(Dead or Alive 5, `christie_c2` — MDL/VVD/VTX + VMT/VTF materials). Install to
`PAYDAY 2\assets\mod_overrides\` with SuperBLT + BeardLib + Legendary Armour
Skins / Wardrobe. The base pack was **tested in game on 2026-11-05**: the
headless LAS contract works (the heister keeps their own head).

**"Without head"** = the police-uniform style LAS contract: the pack ships no
head geometry and registers `replace_body`, not `replace_all` (LAS's
`replace_all` sets head=true and would decapitate the heister when the outfit
has no head). Face/lashes/eyes/glasses/hair/helmet meshes are all dropped; the
heister keeps their own head. See the `las_outfit_pack.py` FLAG_KEYS comment for
the loader semantics.

**Arm bone mapping:** the Arm/ForeArm bind operators from `retarget_maps`
are built in PD2's standing menu pose and are **affine with a rank-1 axial
stretch** (singular values {λ axial, s_core radial}), not similarities — the
elbow blend of two different stretch axes is a small, accepted candy-wrapper
loss. The menu-pose composition (`M_menu^-1` after the standing-frame pin)
moves the elbow pivot, leaving the elbows ~5.3 cm inboard of the PD2 `Arm`
pivots, so after `retarget_maps` the build runs `fix_arm_fits()`, which is
the actual joint pin: it **pure-translates** the existing `Arm`/`ForeArm`
fits (rotation kept, translation replaced, delta added to matrix rows 12–14)
so each source Arm joint lands exactly on its same-named PD2 pivot — elbow/
wrist deviation 0.00 cm, no vertex spikes (z extent stays ≈164 cm, 0
orientation breaks). Do NOT re-fit those bones with a fresh rotation: the
harmonic blend with the Spine1 fit spikes shoulder-top verts to z ≈191–199.

**Elbow weld:** near the elbow the source mesh has PURE Arm and PURE ForeArm
verts interleaved at the crease; after the retarget (the two bones' fits differ
by the full ~100 deg elbow bend) pure-weight neighbours tear into a visible
spike. `weld_elbows()` runs before transfer and splits Arm/ForeArm weights by
a smoothstep of axial position across the joint (zone 4 cm arm-side + 3 cm
past the joint in source coords — the source arm is only 10.5 cm vs the
target 23.3 cm, so a symmetric zone would spill into the acceptance slices).
The packed blendweights carry the weld into the game. In slim, verts within
8 cm (euclidean) of the elbow joint are protected (p' = p): the two segment
axes meet at ~100 deg, so any per-vertex blend of both segment deforms folds
thin crease triangles (hard flip failure).

**Bind-pose straightening:** the menu-pose retarget can leave a small
mid-forearm centerline kink, so after transfer every variant runs
`straighten_segments()` on the forearm segments before slim. v3: per-slice
**2D medians** of pure high-weight verts (w > 0.85, perp < 4.5 cm) from the
segment interior only, fitted in an orthonormal basis (e1, e2) ⟂ the segment
axis so the correction is exactly perpendicular (axial coordinate preserved
exactly, t' = t; a component-wise 3D median does not preserve uᵀc = 0).
Deg-2 polynomial in the normalized variable xn = (t − L/2)/(L/2) ∈ [−1, 1]
(raw t made the Vandermonde ill-conditioned). The cap (3.5 cm over the fitted interior) is a loud build
assert, not a silent clip. 6 cm end fades (elbow/wrist blend verts barely
move, so the slim pass cannot flip them), weights untouched, flip-checked.
Upper-arm segments are skipped (too few clean verts). The elbow bend itself
is the PD2 template bind pose and is intentionally left alone — only
straightness *within* each segment is enforced.

**Elbow blend widening (`widen_elbow_blend`, 2026-11-06, both packs):** the
*(2026-11-07 caveat: the probe pose this was tuned on rotated the ForeArm
about a **twist** axis, so the numbers below describe a wrung-out sleeve
rather than a bent elbow. The pass itself is kept — a wide, smooth weight
ramp is correct for both axes — but the elbow-quality numbers to trust are
the ones in [The elbow, measured on the elbow's own
axis](#the-elbow-measured-on-the-elbows-own-axis-2026-11-07).)* the
weld ring above is narrow *in target space*: 4+3 cm in source coordinates
spans 9.4 cm of the 23.3 cm target arm with 64 mixed-weight verts (2B: 16.2
cm / 331). The bind pose bakes a ~72° elbow bend and the in-game idle hangs
near straight, so at rest the sleeve must unfold ~50° **through that weight
step** — and a narrow, steep step folds the snug sleeve into a braid of
pleats: the X-fold on the outer elbow in the 2026-11-06 screenshots, worst
when the arm hangs, invisible in the bind pose (where every fit metric was
already at reference). The pass runs right after `transfer_group` (before
straighten/slim/fps consume the weights) and re-splits each affected vertex's
(Arm + ForeArm) mass by `s = smoothstep((x + a)/(a + b))`, a = 7 cm proximal,
b = 9 cm distal of the pivot, where **x is a monotone material coordinate**:
signed cm from the elbow along the vertex's own dominant-side bone axis
(proximal verts on the Arm axis, distal on the ForeArm axis). Do NOT use a
single arc-length coordinate about the bent chain: the two axes meet at ~72°,
so arc position is discontinuous across the crease, and an arc-length re-split
(prototyped and measured) makes the fold *worse* — opposed-normal pairs at
the hang go 5 → 12, while the monotone split flattens the braid (edge
compression at 22° straightening: min ratio 0.70 → 0.86; at 45°: 0.53 → 0.71
with 0% of edges under 0.70). A vertex carrying only one of the two bones
gets the other added in a free blendindices slot (4 wide). Weight sums are
preserved exactly; positions/UVs/palette untouched, so every bind-pose fit
number is unchanged by construction. Pinned by
`test_elbow_blend_is_wide` (≥ 10.8 cm span, ≥ 72 mixed verts; measured 12.1/83)
and `test_elbow_does_not_fold_at_the_hang_angle` (posed-LBS compression +
opposed-normal pair bounds at 22/45/80° of straightening), which measure the
shipped bytes through the same `posed_worlds`/`skin_verts` LBS the diagnostic
renderer uses. New `--hang` renders (`christie{,_slim}_hang{,_elbow}_{front,side}.png`
in `docs/pd2-las/renders/`) show the near-straight in-game pose; the slim
elbow at −80° is a smooth tube, no braid.

### The elbow, measured on the elbow's own axis (2026-11-07)

Every posed elbow number in this document up to 2026-11-06 came from a pose
that rotated the `ForeArm` bone about its **local X**. On this rig that is not
flexion. The joint angle per axis, measured on the 2B template with
`render_mesh_skeleton.posed_worlds`:

| ForeArm rotation | −72° | −40° | +40° | +72° |
| --- | --- | --- | --- | --- |
| local **X** (what the 11-06 pose used) | 72.1° | 72.1° | 72.1° | 72.1° |
| local **Y** (real flexion) | 0.1° | 32.1° | 112.1° | 144.1° |

A local-X rotation swings the forearm on a cone about the upper arm and leaves
the elbow at its bind **72.1°** for every angle — i.e. it twists the sleeve at
the weld ring (that *is* a real deformation, and the 2026-11-06 X-fold may
well have included it, but it is not the elbow bending). Local Y moves the
joint angle 1:1, so that is the axis every elbow probe uses now:
`render_mesh_skeleton.BEND_AXIS`, `--hang` = straighten 72° → 12° (−60° on Y),
and `test_elbow_bend_axis_is_flexion` pins the distinction so it cannot drift
back.

**What the correct axis shows.** The bind pose bakes 72° into the elbow; the
heister's idle hangs at ~12°, so the sleeve has to give back about
`r·Δθ ≈ 6 cm × 1.05 rad` of length on the **outside of the bend** — material
that LBS cannot shrink, only fold. Measured on the shipped 2026-11-06 packs
(worst edge in the ±12 cm elbow window, base = slim on this metric):

| straightening from bind | elbow | min edge ratio | worst edge shortening |
| --- | --- | --- | --- |
| 22° | 50° | 0.736 | 0.71 cm |
| 45° | 27° | 0.399 | 2.31 cm |
| **60° (in-game idle)** | **12°** | **0.187** | **3.12 cm** |
| 72° (hyperextension probe) | 0° | 0.066 | 3.62 cm |

PD2's own 2B body, same code and same angles: 0.719 / 0.98 cm at the idle. So
Christie's sleeve was compressing 3× harder than the reference and crumpling
~3 cm of material into a crease — the visual defect, and it survives every
weight profile: widening the blend (`widen_elbow_blend` 4+3 → 7+9 → 12+12 cm)
moves the *same* crushed material onto more edges (measured at 12+12: worst
edge 3.28 cm, 0.119 min ratio — worse than shipped) and rubberises the limb
(1.1 cm of displacement 8 cm down the forearm). Relative edge ratios can look
better while the absolute fold gets bigger, which is why the test now asserts
**absolute shortening** as well.

**The fix: de-puff the outside of the bend.** The excess length is generated
on the outer half of the ring, so `trim_elbows` now squeezes that side too,
over a much wider window than the 0.88 uniform trim: `ELBOW_OUTER_TRIM = 0.65`
(extra radial scale), full strength within 3 cm of the joint in *arc length*,
fading to 1.0 by 9 cm, blended around the ring by the bend-plane bisector
(`outer = clip(-(p − elbow)·normalize(u_arm + u_forearm) / 6 cm)`, floor 0.15
so the crook is not dented). Positions only — skeleton, bind matrices, bone
lengths and weights are untouched, and `_check_flips` still gates the build.
74 + 73 verts move, largest shift 3.78 cm, and the elbow's own p90 thickness
drops 7.18 → 6.69 cm (2B 7.03), so the joint is no longer the widest part of
the arm.

| | 2026-11-06 pack | 2026-11-07 pack | 2B reference |
| --- | --- | --- | --- |
| idle (elbow 12°) min edge ratio | 0.187 | **0.295** | 0.719 |
| idle worst edge shortening | 3.12 cm | **2.08 cm** | 0.98 cm |
| 45° straightening min edge ratio | 0.399 | **0.464** | 0.769 |
| 45° worst edge shortening | 2.31 cm | **1.53 cm** | 0.67 cm |
| inverted faces (elbow window) | 0 | 0 | 0 |
| p90 thickness at the joint | 7.18 cm | 6.69 cm | 7.03 cm |

The remaining gap to 2B is real and is *not* a weighting problem: 2B's sleeve
is thinner at the joint (r ≈ 4 cm vs 6 cm), so it has proportionally less
material to fold. Closing it further would mean a snugger sleeve at the
elbow, which is a shape decision, not a fit bug — the trim above is the part
of it that is free.

Renders: `christie{,_slim}_elbow_idle_before_after.png` (both packs, in-game
idle, old pack left / new right) and the regenerated `*_hang_*` /
`*_skel_pose_*` sets, which now show the actual in-game pose.

## Build

```sh
.venv/bin/python tools/pd2-las/build_christie_las.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # base pack
.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # slim pack
```

After `straighten_segments` the build runs **`centre_segments`** (puts a limb
tube back on the bone that drives it — see [Mesh-vs-skeleton
fit](#mesh-vs-skeleton-fit)) and then **`trim_elbows`** (squeezes the joint
bulge about the arm chain — see [The elbows](#the-elbows-why-they-were-puffy-and-what-was-done)).
Then the slim/hand-cut steps and `assemble_model` follow.

Pipeline: `build_christie_las.load_christie` parses the MDL with **every
bodygroup model** walked (DOA5 ships body/glasses/bra/head as bodypart model
variants; `source_model.load_model` only reads each bodypart's first model and
its VVD LOD0 count check then fails — 21,979 vs 18,359) → kept-material filter
(`cri_body_base`, `cri_02_01/02/05_base`; everything head-carried dropped) →
`build_models.retarget_maps` with `tools/pd2-las/christie_skeleton_map.json`
(DOA `MOT*`/`OPT_Hand_*` bones → PD2 skeleton; `MOT02_Chest` maps to **Spine1**,
not Spine2 — measured joint deviation after retarget drops 9.6 → 3.5 cm and the
arm chain improves 6.2 → 5.3 cm) → `transfer_group` (body +
shadow) → `assemble_model(..., drop_drawables=("g_head", "g_head_lod1"))` →
fps arms via `extract_bones(is_fps_arm_bone)` on the fps_2b template → VTF→DDS
textures (bumpmap resolved from each VMT's `$bumpmap`, normals swizzled
`invert_y=True`, **diffuse alpha attenuated from the normal map's alpha** —
Source leaves diffuse alpha at 255, which PD2 reads as full mirror gloss; that
was the washed-out look in the first in-game test — and **every map expanded to
a full mipmap pyramid** in vanilla PD2's header shape (flags 0x000A1007,
caps 0x00401008; the source VTFs ship mip 0 only, and mip-0-only .texture files
render wrong in game — see tools/pd2-port/dds.py) → pack + reproducible zip
(fixed 2020-01-01 timestamps, so the `.sha256` sidecar is a true build hash).

Verified offline: 0 orientation breaks, 98% winding agreement, models
byte-round-trip, material_config names hash64-match the models, all tests in
`tests/test_christie_las.py`, byte-reproducible rebuild. **Base pack verified
in game 2026-11-05** (headless LAS renders the heister's own head; texture
gloss fixed). The icon sheet
(`build/pd2-las/previews/christie_icon_sheet.png`) shows a coherent clothed
body with an open neck (headless by design).

Registration: `LegendaryArmours.christie`, `...christie_no_hands`,
`...christie_slim`,
`units/<id>/skins/<id>/<id>[_fps]`, textures
`<id>_{body,c02_01,c02_02,c02_05}_{df,nm}`, icon
`guis/dlcs/<id>/armor_skins/<id>`.

## Mesh + skeleton renders

`docs/pd2-las/renders/` — orthographic renders of the built packs' `g_body`
mesh with the PD2 skeleton overlaid (arm chain in red), produced by
`tools/pd2-las/render_mesh_skeleton.py`:

Both packs are named after the pack: `christie_*` is the base pack, and
`christie_slim_*` is the slim one. Every file below comes out of the same
command, so the whole set is reproducible in one run per pack:

```bash
.venv/bin/python tools/pd2-las/render_mesh_skeleton.py \
    --zip dist/Christie_LAS.zip --pack Christie_LAS --item christie \
    --templates "<2B>/assets/units/2b/skins/2b" \
    --out docs/pd2-las/renders --pose --hang
# slim pack: the same command with
#   --zip dist/Christie_LAS_Slim.zip --pack Christie_LAS_Slim --item christie_slim
```

- `christie_skel_{front,side,iso,top,bottom}.png` — full body from five
  directions. `top` looks down the body axis from above and `bottom` looks up
  it from below; in both, the arms swing out to the sides so the hands land by
  the "ears". These two are for the *radial* offset of a limb tube (is the bone
  in the middle of the sleeve, seen along its length), not for left/right - the
  arms are near the body axis, so screen x is a weak left/right signal here.
  Check left/right on `front`.

  Both were wrong before 2026-11-06, in different ways, and neither error is
  visible as "impossible geometry" - the shading uses `abs(normal)` and the body
  is close to symmetric, so a bad depth order still produces a believable
  picture. `bottom` projected as `(-x, -y)`, i.e. the `top` view rotated 180
  degrees, so it never showed the underside at all; `top` sorted faces by `-z`
  with the camera above, so it painted the far side last and showed the jacket's
  *lining* over the shoulders. `depth_towards_camera()` now derives the sort key
  from a per-view camera direction, and `tests/test_render_mesh_skeleton.py`
  pins both the projection axes and the depth sign.
- `christie_skel_wrist_{front,side}.png` — left-wrist close-ups (the sleeve cuff
  surrounds the `Hand` pivot where the in-game glove spawns)
- `christie_forearm_{front,side}.png` — left arm from shoulder to hand, the view
  that answers "is the bone in the middle of the sleeve"

  The close-ups are *isolated limbs*, not zoomed crops: the renderer keeps the
  triangles within 8 cm of the arm bones and the bones near that chain, then
  frames what is left. That matters because a crop window is a slab through an
  orthographic scene - it always drags in the torso and the far shoulder, which
  is how these images spent two revisions showing a correctly-fitted bone
  buried in a wall of cloth. `side` is the character's **left** side (the model
  faces +y with up +z, so left is -x, which is where every `Left*` bone sits);
  a camera at +x would film the left arm through the body.
- `christie_source_{front,side,iso,forearm_front,forearm_side}.png` — the
  ORIGINAL DOA5 model from `references/Christie.zip` with its own skeleton
  (`--source` mode of the renderer), as the reference for comparisons
- `christie_{base,slim}_fit_before_after.png` — left forearm/wrist, the pack as
  shipped before 2026-11-06 (bone along the top edge of the sleeve, cuff off the
  `Hand` pivot) next to the re-centred build. Generated by
  `/home/user/work/before_after.py`-style two-crop composites, not by the
  renderer, so it is the only pair here the command above does not refresh.
- `christie_skel_pose_{front,side}.png`, `christie_skel_pose_wrist_*.png` (and
  the `slim` pair) — the mesh re-skinned into a relaxed pose with the posed
  skeleton drawn on top; regenerate with `--pose`
- `christie{,_slim}_hang_{front,side}.png` and
  `christie{,_slim}_hang_elbow_{front,side}.png` — the **in-game idle**:
  shoulder swung down 22°, elbow straightened from the bind's 72° to 12° on
  the *flexion* axis (`BEND_AXIS`, i.e. −60° on local Y) and the wrist eased
  8°, the pose the sleeve has to survive; regenerate with `--hang`. The
  close-ups are selected on the *posed* positions. Until 2026-11-07 this pose
  rotated the ForeArm about local X, which is a twist and left the elbow at
  72°, so the images showed a wrung sleeve, not a hanging arm.
- `christie{,_slim}_elbow_idle_before_after.png` — the same close-up, 2000 px
  wide: 2026-11-06 pack on the left, 2026-11-07 on the right, with the measured
  numbers in the caption. Composed from `old_render/` + this directory, so a
  future reader can see *what changed* without rebuilding the previous pack.

Until 2026-11-06 this list named files that never existed (`*_skel_wrist_side`
with no base-pack prefix, `christie_base_skel_top`) and the renderer never wrote
`bottom` or the pack `forearm` views at all, so the committed images were
hand-renamed one-offs and could not be rebuilt. The CLI now writes the whole
set, and `tests/test_render_mesh_skeleton.py` keeps the naming honest.

### Why the forearm sleeve curls, and whether it should

Short answer: it should **not** be parallel to the bone, and most of what reads
as a curl is not a curl. Over the forearm interior (5-18 cm of a 22.5 cm bone),
fitting a Kasa circle to each cross section in the plane perpendicular to the
bone:

| mesh | lean vs bone | deviation from straight | tube radius | flare | mean centre offset |
|---|---|---|---|---|---|
| Christie base | 4.4° | 1.45 cm | 3.7 → 5.6 cm | 1.52x | 0.63 cm |
| Christie slim | 1.1° | 1.49 cm | 2.3 → 5.1 cm | 2.27x | 0.59 cm |
| PD2 2B reference | 1.9° | 0.48 cm | 2.7 → 4.3 cm | 1.63x | 0.94 cm |

Every ring plane is perpendicular to the bone to 0.0° on all three meshes (SVD
least-variance normal), so there is no kink at the ring level and nothing is
"twisting" along the sleeve. Three separate things make up the look:

1. **Lean — shared with the reference, and anatomically correct.** A forearm is
   not a cylinder centred on its bone: the ulna runs down the outside, so the
   mass sits off-axis. The 2B reference leans 1.9° and sits 0.94 cm off its own
   bone, i.e. further off than either Christie pack. Being parallel to the bone
   is a property of a bare limb, not of a sleeve.
2. **Flare — shared with the reference.** The sleeve opens from 3.7 to 5.6 cm
   (1.52x) toward the cuff; 2B flares 1.63x over the same span. Base is
   therefore *less* flared than the reference. A sleeve is a flared tube, and a
   flare seen edge-on in a side view is exactly what the eye reads as a curl.
   Slim is the outlier (2.27x): its slim pass narrows the mid-forearm to
   2.3-3.0 cm and then the outer layer flares back out to the cuff, so the
   silhouette pinches and reopens.
3. **Drift at the wrist end — Christie-specific, and now fixed.** From 5-17 cm
   the section centre stays within 1 cm of the bone (its *direction* jitters,
   which is noise on a multi-layer ring; its magnitude does not wander). Past
   17 cm it moved smoothly and monotonically out to 2.4 cm as the mouth flared.
   Total deviation from a straight line was 1.45 cm against 2B's 0.48 cm — the
   one line in the table where Christie was clearly worse, and the only part
   worth calling a bend. It is 0.47 cm now (slim 0.45) after `centre_segments`
   was made to correct the mouth (see [Mesh-vs-skeleton
   fit](#mesh-vs-skeleton-fit)); the lean and the flare in the table above are
   unchanged, because they are the arm and the garment, not a fit error.

The source is not the cause. The DOA source's own forearm holds its section
centre within 0.11 cm of the bone for the whole of its 10.6 cm interior — it is
straight, so the residual bend comes from the menu-pose retarget, not from the
model. `straighten_segments()` targets exactly this: it fits a deg-2 centreline
over interior slices and refuses the build (3.5 cm assert) rather than clip if
the correction is large. Its 6 cm end fades mean the last ~6 cm of the bone —
where the traffic above 17 cm lives — is deliberately left alone; that fade is
why ~1.5 cm of bend survives instead of the several-cm kink the first build had.

`christie_forearm_side.png` and `christie_slim_forearm_side.png` show all of
this at once: a straight mount, a widening sleeve, an off-axis mouth.

### The elbows: why they were puffy, and what was done

The DOA source's arm is thickest exactly at the joint. p90 thickness over a 2 cm
band about the `Arm -> ForeArm -> Hand` polyline, by arc length from the shoulder:

| arc (cm) | 18 | **22 (elbow)** | 26 |
|---|---|---|---|
| Christie, before | 7.34 | **8.16** | 6.83 |
| Christie, now | 6.96 | **7.18** | 6.33 |
| PD2 2B reference | 6.72 | **7.03** | 6.02 |

2B thickens at the elbow too (6.7 -> 7.0 -> 6.0), so a slight swell is correct —
Christie's was just 0.8 cm deeper relative to its own arm, and that is what reads
as a padded elbow. `trim_elbows` squashes the cross-section about the arm chain:
`p' = p + a * (0.88 - 1) * r`, where `r` is the offset from the nearest point on
`Shoulder -> Elbow -> Wrist` and `a` is 1 within 2 cm (arc) of the joint, fading
to 0 at 6 cm. 74 vertices move, 1.0 cm at most; the hand and its cuff are held
still (`1 - w(hand)`), and the skeleton, weights and bone lengths are untouched.

Two locality mistakes are worth recording, because both look right and neither
works:

- **axial coordinate about a segment.** The segments meet at 72 degrees, so a
  vertex on the *outside* of the elbow is ~6.5 cm "along" both axes: an axial
  blend gave 0.01 cm of the 0.66 cm it should have applied, i.e. it trimmed the
  far side of the joint and left the bulge;
- **distance to the joint.** The outer surface of the elbow is ~8 cm from the
  pivot, further than parts of the arm 8 cm up the bone. A spherical fade moved
  20 vertices by 0.06 cm.

Arc length along the chain is the only unambiguous locality here. The crease
metric moved 2.57 -> 2.17 cm (slim 2.33 -> 2.17) rather than away, and
`tests/test_christie_las.py::test_elbow_is_not_puffier_than_the_reference` holds
the thickness at the joint under 7.4 cm. Since the 2026-11-07 outer de-puff
the joint measures **6.69 cm** — slightly under the 2B reference (7.03) — and
the [posed measurement](#the-elbow-measured-on-the-elbows-own-axis-2026-11-07)
is what keeps the *deformation* honest, not just the bind-pose silhouette.

### The far end: what the cuff mouth looks like

`christie_{,slim_}skel_cuff.png` looks straight down the forearm, because a cuff
opening is a ring seen edge-on in every body view. Sleeve-mouth free boundary
within 1-6 cm of the `Hand` pivot, radius about the bone axis:

| | base | slim |
|---|---|---|
| mouth angular coverage | **2 / 36 sectors** | 20 / 36 sectors |
| mouth radius, median | 4.62 cm | 3.01 cm |
| axial raggedness | 4.8 cm | 3.2 cm |

Slim's mouth is a real ring; base's is not. Only two of thirty-six angular
sectors carry free-boundary geometry while the mouth spans 4.8 cm along the
bone, so it is neither a clean cut nor a torn hole - it is a short flap of cloth
hanging off the cuff, most likely the coat tail of the blazer layer, which the
slim pass flattens toward the bone (that flattening is what closes the ring).

Inherited, not introduced: the DOA source's own sleeve ends in a ruffled blazer
cuff. Both cuff rings are still centred on the bone (rim centre 0.30 cm base /
0.39 cm slim off the axis), so this is a mouth-shape note, not a fit regression.

### Sleeve gloss (2026-11-06)

PD2's `DIFFUSE_TEXTURE:NORMALMAP` shader reads the specular mask from the
**diffuse texture's alpha**, and the sleeve UV islands carry a stronger Source
phong mask than the torso region of the same atlas — in game the arms read
glossier than the body (2026-11-06 screenshots, slim pack). `sleeve_uv_masks`
marks a vertex as sleeve when > 40% of its skin weight sits on the arm chain
(Arm/ForeArm/Hand/fingers), splats a 24-texel disc at its UV (1024² working
res, feathered with a box blur, row convention = `preview_textured._sample`
with `flip_v=True` on the stored internal `(u, −v)` pairs), and
`retouch_sleeve_gloss` attenuates diffuse alpha by 55% inside the mask **at
every mip** (each level's mask is the previous level's 2×2 block mean; the
payload is a full pyramid with mip 0 first). Only DXT5 alpha blocks are
rewritten — RGB colour blocks are untouched. Verified: outside the mask the
max alpha delta vs the pre-change pack is the feather (15/255 on boundary
blocks) and the sleeve-region mean alpha drops 23.5 → 11.6; the mask was
confirmed to land on the sleeves by rendering the built model with the mask
tint-baked into the diffuse (red arms, grey torso).
`c02_05` (heels) gets an empty mask — no arm-chain verts — and is left alone.

### The elbow at the in-game hang (why the first build looked fine offline)

Every bind-pose metric in the table below was already at-or-better than the 2B
reference when the X-fold shipped, and the offline `--pose` preview (elbow
bent 22° from bind) was clean. The fold only exists between bind and rest:
the PD2 template bakes ~72° into the elbow, the menu/idle hangs near
straight, and the deformation in between is driven by the *weights*, which
the fit never exercises. Two traps were re-confirmed here:

- A weighted-metric proxy (edge compression) **contradicts the render**: the
  shipped 2B reference compresses *harder* than Christie at −80° (min ratio
  0.31 vs 0.43) yet stays smooth, because its 331-vert blend spreads the
  stretch. Judge fold fixes on renders + opposed-normal pairs, not on
  compression alone.
- The widened weights shift which verts count as "unblended" downstream
  (`_principal_radius` w > 0.99 populations moved), so the slim acceptance
  test needed re-baselining with the widen in place, not before it. And the
  bicep tuck must AMPLIFY the slim displacement (`α × (1 + s·tuck/(1−s))`),
  not dim it — the displacement is what's left of the radius, so dimming the
  move fattens the belly (first attempt measured 0.812 where 0.736 was
  intended).

## Mesh-vs-skeleton fit

Two questions decide whether an outfit looks attached to its heister:

1. **Does the limb tube wrap its bone?** If the tube sits off the bone axis the
   `Arm`/`ForeArm` bone runs along the edge of the sleeve instead of down the
   middle, and it looks worse toward the wrist because the offset grows.
2. **Does the mesh bend where PD2 pivots?** PD2 rotates about the `ForeArm`
   joint, not about the mesh's elbow crease.

`tools/pd2-las/segment_fit.py` measures both on any built pack, and
`tests/test_christie_las.py` asserts on them, so a regression fails CI instead
of showing up in a preview image months later:

- **tube offset** — per axial slab, a *Kasa circle fit* of the cross-section.
  The circle centre is the ring's centre; a median or centroid of the slab's
  perpendicular offsets answers "where is the average vertex" instead, and that
  swings by several cm when a lace seam or the elbow crease lands in the slab
  (it reports 3.4 cm on the reference 2B body, whose forearm is visibly
  straight). Slabs only count if they have ≥ 8 verts, cover ≥ 4 of 6 angular
  sectors, and actually fit a circle (residual ≤ 0.5 r).
- **drift** — the change of that offset along the segment, i.e. "the bone
  slides off the sleeve toward the wrist".
- **crease → pivot** — distance from the `ForeArm`/`Leg` pivot to the centroid
  of the verts blended between the two bones meeting there.
- **cuff → wrist** — distance from the `Hand` pivot to the surviving ring of
  sleeve verts, i.e. where the in-game glove spawns.

Reference numbers (same code, PD2's own fitted 2B body):

| quantity | 2B reference | Christie base, before | Christie base, **now** |
|---|---|---|---|
| forearm slab centre off the axis (slice max) | 0.4 – 1.2 cm | 1.61 / 1.43 cm, drift 1.48 / 1.88 | **1.03 / 0.82 cm, drift 0.30 / 0.83** |
| forearm slab centre (slim) | 0.4 – 1.2 cm | 0.98 / 0.88 cm, drift 0.83 / 0.90 | **1.10 / 1.15 cm, drift 0.47 / 1.21** |
| upper arm | 1.8 – 3.1 cm | 0.5 – 0.9 cm | unchanged |
| thigh / calf | 0.7 – 2.6 cm | 0.3 – 1.6 cm | unchanged |
| crease → elbow pivot | 4.9 cm | 2.6 cm | **2.85 / 2.99 cm** (the widened ring's weight centroid is wider; the geometric crease is untouched — limit 3.5) |
| cuff → wrist pivot | 1.5 cm | 2.0 cm (slim 2.2) | **1.18 / 1.13 cm (slim 1.87 / 2.02)** |

The forearm is now closer to its bone than PD2's own 2B body, and the cuff ring
is inside the reference's own 1.5 cm. "Before" is the pack as it shipped up to
`eb4f77d`; the change that got there is described below.

Two of those numbers look alarming and are **not** defects, which is why the
build does not "fix" them:

- **thigh 10 cm at the hip, upper arm 5–7 cm** — the thigh number is the blazer
  hem flaring out, weighted to `UpLeg` on purpose (a coat has to swing with the
  leg), and the upper-arm slabs hold 6–14 verts around the deltoid mass, so
  their centres scatter by several cm (2B: 3.7 cm). Auto-centring them folds the
  coat into the leg and nudges a shoulder that is not measurably wrong. The
  centring pass is scoped to the forearms for that reason, and the thresholds
  in the test are per-segment.
- `straighten_segments` could not fix the forearm either: its radial mask
  (`perp_max = 4.5 cm`) is an *absolute* distance from the bone axis, so the
  verts that are wrong are exactly the ones it excludes.

`centre_segments` right after `straighten_segments`; this is the pass that was
rewritten on 2026-11-06 to make the sleeve *coaxial* with the bone.

The measured per-slab profile is a **bow**: 1.2 cm off at the elbow, under 0.5 cm
mid-segment, 2.2 cm at the mouth. Two things about the old pass therefore had to
change, and one thing had to *not*:

- **Fade.** The old correction was multiplied by `smoothstep((L−t)/6)` at the
  wrist end, which is 0.36 at t = 20 cm and 0.12 at the mouth — it deleted the
  correction exactly where the sleeve is furthest off the bone, and that is why
  the cuff ring sat 2.2 cm from the `Hand` pivot. It is now elbow-only; the
  wrist end gets a 2.5 cm **taper** instead of a 6 cm fade, which absorbs the
  seam between the mouth ring and the glove ring. Taper and no taper were both
  built: none folds 55 triangles flat at the mouth, 1.5 cm folds 12, 2.5 cm
  folds none, and beyond 3 cm the cuff starts drifting out again (1.31 cm).
  The elbow keeps its wide 3D fade, because its crease has pure-`ForeArm` verts
  next to 20 %-ones and an axial-only fade folded two crease triangles there.
- **Weight.** The old displacement was `w · fade · chat` — each vertex moved in
  proportion to its own skin weight. A cross-section is a *stack* (outer sleeve,
  mid layer, bare arm, blazer cuff flap) with weights 0.8–1.0, so that slides
  the layers through each other and leaves the flap behind: the section then
  *spreads*, and the fit reports 3.9 cm of radius against 2.2 before. The ramp
  is now **saturated** — `smoothstep(w / 0.85)` — so the layers of one section
  translate together, while the hand (weight 0) and the rest of the body do not
  move. Dropping the weight factor altogether is also wrong, and measurably so:
  it translates everything on that side of the body, and the leg crease goes
  5.91 → 4.56 cm.
- **Sampling.** Slabs now run from 6 cm past the elbow to the end of the bone
  (`t ≤ L`, 14 slabs, `min_w` 0.05 so the 0.8/0.2 mouth ring counts); the
  weight-weighted line through them is held flat outside that range, because
  extrapolating turns a 0.7 cm intercept error into a 4 cm correction at the
  wrist.

The correction is perpendicular by construction, so `t` is preserved exactly
(asserted: axial leak ~1e-16 cm), and only positions move — skeleton, bind
matrices, bone lengths and skin weights are untouched. `_check_flips` still
gates the build, and it now reports the worst triangle's position, area and edge
stretch instead of only a count.

The 2B reference cannot be shipped as the threshold proxy in every respect: its
own crease sits 4.9 cm from the elbow pivot, further than Christie's 2.6 cm, so
the crease test asserts an absolute bound rather than "better than 2B".

Renders (`docs/pd2-las/renders/`): `*_skel_{front,side,iso,top}.png`, plus
`*_skel_pose_{front,side}.png` and `*_skel_pose_wrist_{front,side}.png` — the
mesh re-skinned into a relaxed pose. Those posed renders were wrong until
2026-11-06, from three separate bugs, each of which stayed *invisible* in the
bind pose — the only pose anyone checked at first:

1. `render_mesh_skeleton.skin_verts` built a numpy 4×4 and applied it as
   `M @ p`, but Diesel matrices are row-vector (`mat_apply_point`), so every
   blended matrix was silently transposed and the mesh flew off the skeleton.
2. `posed_worlds` pre-multiplied a local rotation, which rotates the joint
   *offset* instead of pivoting the bone about its own head.
3. `skin_verts` composed the skin matrix as `pose_world @ inv_bind`. The
   bind matrices are inverse-bind worlds, so the correct order is
   `inv_bind @ pose_world` (bind → model → posed). The swapped order applies
   each bone's pose rotation about the *model origin*, which is exactly the
   identity while every joint is at rest but flings the arm 45 cm at mid-forearm
   as soon as an elbow bends — the long blade-like spikes that used to appear
   through the hands in the `--pose` previews.

Bugs 1 and 3 are both exactly the identity at rest, so an at-rest overlay proves
nothing about them. `tests/test_render_mesh_skeleton.py` now bends an elbow and
asserts the joints stay put, no edge grows more than a few cm, and every vertex
stays near its bone. The shipped packs were never affected: this code only
draws the diagnostic previews, it does not bake the mesh.
