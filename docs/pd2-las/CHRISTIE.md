# Christie LAS packs — DOA5 Christie as body-only PAYDAY 2 LAS outfits

- `dist/Christie_LAS.zip` (+ `.sha256`) — full body incl. Christie's hands.
- `dist/Christie_LAS_Slim.zip` (+ `.sha256`) — 10% thinner torso/legs, 25%
  thinner arms in cross-section, **and no hands** (`--variant slim`; the
  separate no-hands pack was removed — slim supersedes it). The v4 slim pass
  (`slim_group`) works on the bind-pose mesh only — skeleton, bone lengths
  and skin weights untouched — applying per-segment radial cross-section
  scaling `p' = p + Σ α_j (s_j − 1) r_j` with separate joint-anchored axes for
  each upper arm / forearm / thigh / calf (s = 0.75 arms, 0.90 legs), a
  Z-monotonic torso centerline for the pelvis/spine (s = 0.90, neck fade),
  shoulder and crotch weight routing, an explicit identity field for
  protected head/hands/feet, smoothstep fades to 1.0 at the wrist/ankle with
  the surviving cuff ring enforced bitwise unchanged, and normals recomputed
  from the final triangles. Height is preserved (final min/max z match the
  base pack); verified principal cross-section radii: arms 0.747–0.764,
  legs 0.900 vs base. Then the hands
  are cut at the wrist, the sleeves are stretched deep past the wrist joint
  (blazer −4.5 cm, skin −3.5 cm, shirt −3.0 cm) so the spawned glove sits well
  inside the cuff in every pose, plus a `*_glove_adapter.lua` compat hook
  (default glove restored, adapter re-enabled) so the heister's changeable
  in-game gloves show through the sleeves. Applied before the fps extraction
  so the viewmodel arms match.

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

## Build

```sh
.venv/bin/python tools/pd2-las/build_christie_las.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # base pack
.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # slim pack
```

After `straighten_segments` the build runs **`centre_segments`** — the pass
that puts a limb tube back on the bone that drives it (see
[Mesh-vs-skeleton fit](#mesh-vs-skeleton-fit)). Then the slim/hand-cut steps and
`assemble_model` follow.

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
    --out docs/pd2-las/renders --pose          # add --Slim for the slim pack
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

Until 2026-11-06 this list named files that never existed (`*_skel_wrist_side`
with no base-pack prefix, `christie_base_skel_top`) and the renderer never wrote
`bottom` or the pack `forearm` views at all, so the committed images were
hand-renamed one-offs and could not be rebuilt. The CLI now writes the whole
set, and `tests/test_render_mesh_skeleton.py` keeps the naming honest.

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

| quantity | 2B reference | Christie base, before | Christie base, after |
|---|---|---|---|
| forearm slab centre off the axis | 0.4 – 1.2 cm | 1.6 → 3.3 cm (drift) | ≤ 1.5 cm, drift ~1 |
| forearm slab centre (slim) | 0.4 – 1.2 cm | 3.8 – 4.0 cm | ≤ 2.1 cm |
| upper arm | 1.8 – 3.1 cm | 0.5 – 0.9 cm | unchanged |
| thigh / calf | 0.7 – 2.6 cm | 0.3 – 1.6 cm | unchanged |
| crease → elbow pivot | 4.9 cm | 2.6 cm | 2.6 cm |
| cuff → wrist pivot | 1.5 cm | 2.0 cm (slim 2.5) | 1.8 cm (slim 2.2) |

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

`centre_segments` therefore displaces each vertex by
`- w~(bone) · fade(t) · chat(t)`: `chat` is the segment's measured
mesh-centreline (a vertex-weighted line through the slab centres, held constant
outside the measured range — extrapolating turns a 0.7 cm intercept error into a
4 cm correction at the wrist), `w~` is the slim pass's routed weight and `fade`
is an axial smoothstep plus a 3D radius fade around each end joint. The end
fades are asymmetric: wide at the elbow (the crease has pure-`ForeArm` verts
next to 20 %-ones, and an axial-only fade folded two 3 cm² crease triangles
there) and tight at the wrist (the drift peaks there, and there is no crease to
fold). The correction is perpendicular by construction, so `t` is preserved
exactly (asserted: axial leak ~1e-16 cm), and only positions move — skeleton,
bind matrices, bone lengths and skin weights are untouched. `_check_flips` and
the 0-orientation-breaks gate still run.

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
