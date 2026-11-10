# Christie_LAS_Slim — in-game screenshot review (2026-11-10)

## Evidence and scope

This review covers the **8 PNGs supplied on 2026-11-10**, archived
byte-for-byte in [`docs/pd2-las/screenshots/`](../pd2-las/screenshots/README.md):
**7 lobby/idle views and 1 menu view holding a rifle**. Filenames follow upload
order; [`manifest.json`](../pd2-las/screenshots/manifest.json) records each
upload name, archived name, dimensions, byte count and full SHA-256.

The previous batches — the 15 PNGs of 2026-11-07 and the 11-frame set before
them — are **no longer in the archive** (they remain in Git history). Their crop
coordinates do not apply here, and the [2026-11-07
review](2026-11-07-christie-slim-screenshot-review.md) describes images that are
no longer in the repository. Read that document as history.

- **Installed build: `Christie_LAS_Slim`, reported by the user as SHA-256
  `7a4d010c…90a3e6f` (4,393,967 B)** — the de-spiked slim ZIP currently in
  `dist/`. That is the user's statement of what was installed; it is not a hash
  measured from these pixels, and it does not cover the head model or the
  spawned gloves, which are separate assets.
- This is the **first capture batch of a de-spiked build**, so the elbow
  comparison against the 2026-11-07 lobby frames is the first in-game check of
  that change. Nothing else in the packs changed between those two batches.

Appearance was judged at **native 1:1 resolution**. Unfiltered crops located the
evidence; nearest-neighbour enlargement was used only to trace edges. No
archived screenshot was resized, recompressed or annotated — the review crops
live in the ignored `build/` tree.

### Frame index

Left/right in the filenames describe the direction the face points **in the
image**, not an anatomical assignment. Each file has its own pixel space; all
crop boxes below are `(left, top, right, bottom)`, upper-left origin,
right/bottom exclusive, in that file's own pixels.

| Shot | Archived file | View | Pixels |
|---|---|---|---|
| 01 | [`christie_slim_01_lobby_front.png`](../pd2-las/screenshots/christie_slim_01_lobby_front.png) | lobby, front | 524 × 1008 |
| 02 | [`christie_slim_02_lobby_right-three-quarter.png`](../pd2-las/screenshots/christie_slim_02_lobby_right-three-quarter.png) | lobby, front 3/4, facing image-right | 539 × 1013 |
| 03 | [`christie_slim_03_lobby_right-profile.png`](../pd2-las/screenshots/christie_slim_03_lobby_right-profile.png) | lobby, profile, facing image-right | 525 × 1021 |
| 04 | [`christie_slim_04_lobby_back-three-quarter-right.png`](../pd2-las/screenshots/christie_slim_04_lobby_back-three-quarter-right.png) | lobby, back 3/4 | 546 × 1021 |
| 05 | [`christie_slim_05_lobby_back.png`](../pd2-las/screenshots/christie_slim_05_lobby_back.png) | lobby, back | 544 × 1040 |
| 06 | [`christie_slim_06_lobby_back-three-quarter-left.png`](../pd2-las/screenshots/christie_slim_06_lobby_back-three-quarter-left.png) | lobby, opposite back 3/4 | 541 × 1040 |
| 07 | [`christie_slim_07_lobby_left-profile.png`](../pd2-las/screenshots/christie_slim_07_lobby_left-profile.png) | lobby, profile, facing image-left | 508 × 1066 |
| 08 | [`christie_slim_08_menu_front-three-quarter-right-rifle.png`](../pd2-las/screenshots/christie_slim_08_menu_front-three-quarter-right-rifle.png) | menu, front 3/4, rifle | 555 × 1021 |

Limitation of the batch: the rifle pose is covered by **one** frame (shot 08),
not the seven of the replaced set, and no frame shows the second rifle angle on
the far side of the body.

## Findings — observed appearance, not assumed root causes

### 1. Inner elbow: the outward beak is gone, a thin flap and a hard crease remain — high visual impact

**Evidence:** shot **08** (rifle), `(50, 525, 130, 600)`; idle profiles **03**
`(255, 465, 325, 520)` and **07** `(235, 455, 300, 515)`; front views **01**
`(52, 410, 120, 472)` and `(395, 405, 458, 452)`, **02** `(85, 428, 155, 480)`.

What the frames support:

- **The de-spike is not contradicted.** In the 03 profile the arm contour, after
  an alignment offset of `(+3, +3)` px against the 2026-11-07 profile frame, sits
  **−14 to +6 px** relative to the old contour over the elbow rows
  (y 430–535) — i.e. level with it, mostly inside it. There is no new outward
  bulge in the lobby poses. That is a silhouette measurement on two different
  captures of two different builds, not a before/after render pair, so it
  bounds the change rather than certifying it.
- **The crease itself is still abrupt.** In the rifle frame the inner elbow
  carries a thin, flap-like fold with a bright rim, roughly `x 60–120,
  y 530–595`, that reads as a separate surface rather than a soft fabric
  crease. The idle profiles show the same effect at a smaller scale as a
  multi-ridge compressed crease, darkest at 03 `(300, 480)-(320, 500)`.
- **The crease is not symmetric across the two profiles.** With a fixed
  luminance floor, the elbow box holds **9.4 %** pixels below 60 in **03**
  (2679-pixel box) but **0.0 %** in the mirrored box of **07** (3240 px, minimum
  luminance 63). Part of that is the key light (the room light comes from image
  left, behind the camera in 03 and in front of it in 07) and part may be the
  pose. The screenshots cannot separate the two, so this is **not** a claim that
  one arm's geometry differs.

Not established: that the visible flap is a shading discontinuity, a
self-intersection, or a baked source fold. The remaining flap is the thing to
isolate next, because it is what a viewer now sees where the beak used to be.

### 2. Dark angular patch on the rear sleeve below the elbow — high visual impact

**Evidence:** shot **05** `(455, 490, 510, 565)` and `(50, 470, 140, 590)`; shot
**04** `(160, 370, 240, 470)`; shot **06** `(380, 420, 480, 520)`.

Both rear sleeves show a dark, sharply bounded wedge on the outer/rear surface
just below the elbow. It is still present in this build, so the change since the
replaced batch did not remove it.

Measured at 1:1 in shot 05, the right-sleeve wedge core (8 × 8 at `470, 518`)
has mean RGB **(29, 30, 26)**; the wall immediately beside it (`498–518,
510–530`) has mean **(41, 42, 38)** with per-channel σ ≈ 7. The wedge is
therefore *darker* than the background and does not reproduce the wall's weave
texture. That is consistent with a shaded, self-overlapping or inward-facing
surface, and **not** with a see-through hole — the same reading the previous
batch supported, and it still does not identify the owner.

Counting enclosed dark area (dark pixels surrounded by bright sleeve) in matched
fractional boxes gives **no clear improvement** over the replaced batch: shot 05
image-left `1323 px / largest blob 118` here against `1064 / 67` before, shot 05
image-right `461 / 36` against `505 / 59`. These boxes follow the arm only
approximately, so treat the direction as unmeasured rather than as a regression.

### 3. Hard neck bands and a planar throat — high visual impact

**Evidence:** shot **01** `(200, 160, 300, 260)`; shot **02**
`(215, 130, 315, 240)`; shot **08** `(255, 240, 300, 292)`.

A pale band runs across the neck under the jaw, a distinctly darker throat
region follows, and the transition to the chest is another abrupt step. Measured
as the largest single-row luminance change across the neck columns, the new
frames give **9.4** (01, y 168), **11.9** (02, y 172) and **6.9** (08, y 283);
the replaced 2026-11-07 front frame gave **10.6** (y 173) over the same
normalised band. The band magnitude is unchanged within measurement noise.

The pack is body-only; the head is a separate replacement. That does **not**
prove the bands belong to the head — nor to the body. Ownership still has to be
settled with a head-on / head-off comparison at the same pose and camera.

### 4. Coarse tonal patches across suit and trousers — medium/high visual impact

**Evidence:** shot **05** back `(120, 250, 430, 620)`; shot **04** arms and coat
panels; shot **01** trousers `(150, 660, 380, 960)`; shot **06** across the back.

The coat still breaks into broad, irregular light/dark patches on the back,
shoulders, sleeves and lower panels, and the trousers still read as mottled.
Boundaries cross otherwise smooth panels, so this is not fabric detail. As
before, the screenshots cannot distinguish diffuse detail, normal/tangent
response, specular quantisation, overlapping surfaces, or engine lighting —
and no channel of it is established here.

### 5. Cuff / glove junction: pale rim and uneven edge, but the red speck is gone — medium visual impact

**Evidence:** shot **01** `(10, 540, 200, 700)` and `(360, 540, 520, 700)`; shot
**02** `(70, 560, 200, 700)`; shot **05** `(40, 560, 160, 700)`.

The upper edge of each blue glove shows a pale cuff-interior band and an uneven,
slightly stepped rim where the sleeve ends. The join reads as sleeve abutting
glove rather than sleeve covering glove.

**The previous "small red/orange marks at the junction" are not reproduced.**
Strongly red pixels in these frames lie on the bright object contour, not in the
interior: shot 01 has 948 of 962, shots 05, 06 and 07 have 100 %, and there are
**zero** inside the cuff/glove box. That pattern is antialiasing fringe on the
rim light, not a texture speck. The earlier finding should not be carried
forward as an open texture defect on this evidence.

Ownership is still open: the body pack does not author the gloves, so a rough
join is a comparison problem between sleeve end, glove adapter and the selected
glove, not something to fix by cutting more sleeve.

### 6. Background visible between arm and torso — not asserted as a tear

**Evidence:** shot **04** `(120, 380, 260, 560)`; shot **06**
`(360, 400, 480, 580)`.

In the back three-quarter views a wedge of wall shows between the hanging arm
and the jacket body, with a thin inner surface visible inside the opening. The
prior diagnosis measured this as silhouette clearance (empty space between arm
and torso, `cast_front` does not cull) rather than a torn surface, and nothing
in these frames contradicts that. A single static frame cannot tell an armhole
apart from a gap, so this stays unasserted either way.

## What is not established by this batch

- **That the de-spike fully solved the inner elbow in game.** The lobby
  silhouettes show no outward growth, but the rifle pose still shows a thin
  flap-like fold, and no frame gives a matched before/after of the same pose and
  camera on both builds.
- **Ownership of any of the above.** Rear-sleeve dark patch, neck bands, tonal
  patches, cuff rim and elbow flap are all appearance observations; none of them
  is attributed to a specific mesh, material, normal map or asset here.
- **That the installed bytes are the repository ZIP.** The build identity is the
  user's report. The repository also records a forearm-normal rotation aimed at
  the dark rear-forearm shading; that entry carries no ZIP hash, so this archive
  cannot confirm whether the installed bytes include it.
- **First-person arms, feet, gameplay animation, reload and walking poses.**
  Static lobby/menu captures show none of them.
- **Stability of the installed pack** (crashes, script errors, other heists'
  models).

## Offline checks on the repository artifact

These apply to the **repository ZIP**, not automatically to the installation:

```bash
.venv/bin/python -m pytest -q tests/test_christie_las.py tests/test_seam_normals.py
```

- **86 passed, 2 failed.** The two failures are the pre-existing slim sleeve
  tube probes, `test_sleeve_tube_is_closed_along_its_length[-1-slim]` and
  `[1-slim]` (slim right sleeve 4.95 cm²; the rims in z 125.3–126.6 have no
  paired vertices to bridge). They are unchanged by this documentation round and
  are not caused by the screenshots; no model, texture, Lua hook or ZIP was
  rebuilt here.
- The de-spike itself was verified offline in
  [`2026-11-10-christie-elbow-render-audit.md`](2026-11-10-christie-elbow-render-audit.md)
  and `tools/pd2-las/MODLOG.md`: 97/97 renders reproduce byte-identically, and
  the new silhouette minus the old (dilated 1 px) is 0 px outward on slim at
  45/60/72° and on base at 22°, with only a 1 px antialiasing fringe elsewhere.
  That is a render-space result; this batch is the first look at it in game.

## Next work, in order

1. Isolate the **inner-elbow flap** in shot 08: same heister, pose and camera,
   rifle and no rifle, flat-normal and unlit-diffuse renders of the matching
   mesh, to separate a baked crease from a self-intersection and from a normal
   discontinuity.
2. Isolate the **rear-sleeve dark wedge** (shot 05) with the same controls. It
   survived a rebuild that removed material from the same joint, which argues it
   is shading or overlap rather than the removed vertices.
3. Settle **neck-band ownership** by repeating one lobby shot with and without
   the head replacement, same body and lighting.
4. Only then consider the **global suit shading channels** (diffuse, specular
   mask, normals), one at a time, on a matched installed build.
5. Before calling any build visually cleared: capture a matched angle set for
   both builds, plus the missing rifle angles and a short gameplay/FPS check.
