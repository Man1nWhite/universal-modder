# Christie_LAS_Slim — replacement screenshot review (2026-11-07)

## Evidence and scope

This review **replaces the earlier 11-frame screenshot review**. The user
supplied 15 replacement PNGs, archived byte-for-byte in
[`docs/pd2-las/screenshots/`](../pd2-las/screenshots/README.md): **8 lobby/idle
views and 7 menu views holding a rifle**. The filenames follow upload order;
[`manifest.json`](../pd2-las/screenshots/manifest.json) records each upload
name, archived name, dimensions, byte count and full SHA-256. Old filenames and
crop coordinates in the historical recheck/diagnosis do not identify these new
frames; the former images remain in Git history, not in the current archive.

**The installed pack's hash was not supplied.** The repository ZIP is
`dist/Christie_LAS_Slim.zip`, SHA-256
`5e55745f940e4426734010ef56e12bc084b708d5cae36c76126058acc4170b4d`
(4,222,761 B), but that does not establish which bytes are installed in the
screenshots. Do not label these frames with that hash or use them to certify
that rebuild. The date above is the date the batch was supplied, not a claim
about the files' capture timestamps.

Appearance was judged at **native 1:1 resolution**. Unfiltered crops were used
to locate evidence; nearest-neighbour enlargement was used only to trace edges,
not to diagnose faceting. No screenshot was resized, recompressed or annotated
in the archive. PNG storage is lossless; the upstream capture/resampling
history is unknown. Mouse cursors and UI overlays are not model defects.

### Frame index

Left/right in these filenames describe the direction the face points **in the
image**, not an anatomical left/right assignment to a limb. Each file has its
own pixel space. All crop boxes below use `(left, top, right, bottom)`, origin
at the upper-left, with right/bottom exclusive.

| Shot | Archived file | View | Pixels |
|---|---|---|---|
| 01 | [`christie_slim_01_lobby_front.png`](../pd2-las/screenshots/christie_slim_01_lobby_front.png) | lobby, front | 506 × 980 |
| 02 | [`christie_slim_02_lobby_right-three-quarter.png`](../pd2-las/screenshots/christie_slim_02_lobby_right-three-quarter.png) | lobby, front 3/4, facing image-right | 495 × 1000 |
| 03 | [`christie_slim_03_lobby_right-profile.png`](../pd2-las/screenshots/christie_slim_03_lobby_right-profile.png) | lobby, profile, facing image-right | 528 × 1012 |
| 04 | [`christie_slim_04_lobby_back-three-quarter-right.png`](../pd2-las/screenshots/christie_slim_04_lobby_back-three-quarter-right.png) | lobby, back 3/4 | 540 × 1020 |
| 05 | [`christie_slim_05_lobby_back.png`](../pd2-las/screenshots/christie_slim_05_lobby_back.png) | lobby, back | 594 × 1010 |
| 06 | [`christie_slim_06_lobby_back-three-quarter-left.png`](../pd2-las/screenshots/christie_slim_06_lobby_back-three-quarter-left.png) | lobby, opposite back 3/4 | 560 × 1055 |
| 07 | [`christie_slim_07_lobby_left-profile.png`](../pd2-las/screenshots/christie_slim_07_lobby_left-profile.png) | lobby, profile, facing image-left | 502 × 1018 |
| 08 | [`christie_slim_08_lobby_left-three-quarter.png`](../pd2-las/screenshots/christie_slim_08_lobby_left-three-quarter.png) | lobby, front 3/4, facing image-left | 519 × 1017 |
| 09 | [`christie_slim_09_menu_front-three-quarter-right-rifle.png`](../pd2-las/screenshots/christie_slim_09_menu_front-three-quarter-right-rifle.png) | menu, front 3/4, rifle | 585 × 911 |
| 10 | [`christie_slim_10_menu_right-profile-rifle.png`](../pd2-las/screenshots/christie_slim_10_menu_right-profile-rifle.png) | menu, profile, rifle | 557 × 916 |
| 11 | [`christie_slim_11_menu_back-three-quarter-right-rifle.png`](../pd2-las/screenshots/christie_slim_11_menu_back-three-quarter-right-rifle.png) | menu, back 3/4, rifle | 541 × 890 |
| 12 | [`christie_slim_12_menu_back-rifle.png`](../pd2-las/screenshots/christie_slim_12_menu_back-rifle.png) | menu, back, rifle | 574 × 910 |
| 13 | [`christie_slim_13_menu_left-profile-rifle.png`](../pd2-las/screenshots/christie_slim_13_menu_left-profile-rifle.png) | menu, opposite profile, rifle | 536 × 881 |
| 14 | [`christie_slim_14_menu_front-three-quarter-left-rifle.png`](../pd2-las/screenshots/christie_slim_14_menu_front-three-quarter-left-rifle.png) | menu, opposite front 3/4, rifle | 531 × 902 |
| 15 | [`christie_slim_15_menu_front-rifle.png`](../pd2-las/screenshots/christie_slim_15_menu_front-rifle.png) | menu, front, rifle | 536 × 899 |

## Findings — observed appearance, not assumed root causes

### 1. Large dark patches on the rear forearms — high visual impact

**Evidence:** shots 04–06, clearest in **05**, crops `(55, 435, 125, 590)`
and `(435, 435, 505, 590)`.

Both sleeves have a conspicuous dark green/black, angular patch immediately
below the elbow. These are not just a thin seam or an isolated antialiased
pixel. They interrupt the white sleeve over a substantial area, and the two
arms show a similar failure. The smooth/dark interior contrasts with both the
surrounding cloth and the textured wall.

Do **not** turn this into a confirmed see-through hole from colour similarity
alone. In shot 05, the image-left patch core `(83, 479, 93, 495)` has RGB mean
about `(43, 50, 38)` and channel standard deviations around 2, whereas the
adjacent wall `(38, 479, 48, 495)` has mean `(44, 48, 42)` and standard
deviations around 10. The dark region does not visibly reproduce the wall's
weave. This supports investigating a shaded/overlapping surface as well as
culling; it does not identify the cause.

**Next isolation:** after matching the installed pack hash, compare this exact
rear pose with the sleeve alone under unlit diffuse, flat-normal lighting and
ordinary normal-mapped lighting. Check local normals/tangent frames, inner
layers and self-overlap; do not add more seam faces just because a patch is
dark. The old closed-tube test does not test this appearance.

### 2. Hard neck colour bands and planar-looking throat — high visual impact

**Evidence:** lobby shots 01–02 and 08; stronger in menu shots **09** and
**15**, especially 15 crop `(150, 265, 330, 420)`.

There is a sharp light band running across the neck below the jaw, a much
darker central throat region, and another abrupt transition toward the chest.
The boundary is circumferential/angular, not merely a gentle light-to-shadow
gradient. The stepped tonal regions are visible at native scale and remain an
open appearance problem.

The pack is body-only and the head is separate, but **that does not prove the
whole visible neck artifact belongs to the head mod**. The prior offline
junction diagnosis ruled out its original neck-rim theory on the measured
combination; it did not explain these rendered bands. Nor does the screenshot
prove a skin gap, a particular skirt fault, or a specific wrong material.

**Next isolation:** same heister, pose, camera and lighting, first without the
head replacement, then with it; retain the same LAS body. If necessary repeat
with the ordinary body as the other half of the comparison. Establish which
surface owns each band before changing neck geometry or textures.

### 3. Coarse, hard-edged tonal patches across the suit — high visual impact

**Evidence:** shot **12**, back crop `(100, 300, 520, 850)`; shots **10–11**
and **14–15**, shoulders/upper arms and coat panels; shot **01**, trouser crop
`(85, 640, 355, 950)`.

The coat has large, stair-stepped and irregular light/dark patches across the
back, shoulders, sleeves and lower panels. The trousers also look strongly
mottled. In the rifle views, some boundaries cut across otherwise broad smooth
panels. These patches are visible at native resolution, not solely after
smoothed enlargement. The result is inconsistent material/lighting response,
not a clean, uniformly shaded white suit.

This is an **appearance finding**, not a claim that the triangles themselves
are faceted or that all authored fabric folds/stains are wrong. The screenshots
alone cannot distinguish diffuse detail, normal/tangent response, specular
quantisation, overlapping surfaces, or engine lighting/shadow artefacts.

The earlier statement that the broad blotching was "fixed" was too sweeping.
The face-raster gloss mask and filtered mip rebuild fixed a specific build
operation; their scope tests do not establish that all visible suit blotching
is gone. In particular, the known residual **boot** UV overlap cannot explain
patches on the back or upper arms. The old normal-map format check likewise
does not certify the final engine shading.

**Next isolation:** on a matched installed build, compare the same panels with
unlit diffuse, specular disabled, then a flat normal map, changing one thing at
a time. A change in appearance under one of those controls identifies the
channel to investigate; it is not a reason to smooth or reweight the whole
mesh speculatively.

### 4. Elbow folds remain pinched and angular — medium/high visual impact

**Evidence:** shot **10**, crop `(155, 480, 310, 640)`; shot **15**, crop
`(390, 515, 510, 640)`; idle profiles 03 and 07 provide comparison views.

The bent inner elbow has a sharply compressed multi-ridge crease and a
triangular, flap-like boundary at the upper-arm/forearm transition. The idle
profiles also show an abrupt elbow bulge/step. Some sleeve folding is expected;
these views do not provide a frame-by-frame animation comparison or prove an
inverted face. They do show why a passing topology/coverage metric is not
sufficient visual clearance.

**Next isolation:** inspect both arms over the actual idle-to-rifle movement
in game, with a flat-shaded wireframe/normal diagnostic offline on the matching
mesh. Separate self-intersection, baked source folds and shading discontinuity
before adjusting skin weights or corrective positions. The known extra fold
at maximum flexion after stitching is a watch item, not by itself proof that
it caused these screenshots.

### 5. Cuff/glove junction remains rough — medium visual impact

**Evidence:** shot **08**, crop `(275, 535, 365, 655)`; shots 01–03 and 07;
the glove over the rifle in shot 09 gives another pose.

Visible symptoms include a thin pale cuff-interior band, an uneven cuff edge,
small red/orange marks at the junction, and long black, tapered streaks across
the back of the gloves. The join does not read as a consistently clean sleeve
over a glove.

Do not call every black streak a hole or a broken fingertip. They may be glove
texture detail, overlapping stock/glove/adapter surfaces, or another rendering
interaction. The body pack does not author the finger mesh, so sculpting
Christie's deleted hands cannot repair this. Conversely, that ownership fact
is **not** evidence that the combined outfit/glove result is visually correct.
The earlier cuff UV sampling did not reproduce the red speck from the body
texture; it did not locate the speck's actual owner.

**Next isolation:** compare the same selected gloves on the vanilla outfit,
then on Slim, in the same pose. Inspect glove/adapter/stock-hand visibility and
the cuff separately before cutting more geometry or changing the glove hook.

## What is not established by this batch

- **A new armpit tear:** the visible background gap between hanging arm and
  torso is not enough to overturn the prior diagnosis that this is silhouette
  clearance, not a torn surface. No new hole is asserted here.
- **The old detached elbow sliver is fixed in game:** no directly matched
  before/after or installed-hash evidence establishes that. The new dark rear
  forearm patches and angular bend need their own investigation.
- **Hard normal seams everywhere:** the repository model has no divergent
  *interior* coincident-normal pairs. Its retained border/lining folds are not
  automatically defects, and this count does not explain every tonal patch.
- **Correct boot appearance, FPS arms, or walking/reload deformation:** the
  feet and first-person view are not shown, and these are static lobby/menu
  captures, not a gameplay animation test.
- **A confirmed inner-top UV fault:** the `c02_05` mapping observation in the
  structural diagnosis remains unverified; these screenshots do not isolate it.
- **A shader-format regression:** visible shading problems do not establish
  that DXT5nm encoding or the global diffuse-alpha convention is wrong.

## Offline checks on the repository artifact

The following apply to the **repository ZIP**, not automatically to the
installation shown in the screenshots:

```bash
.venv/bin/python -m pytest -q tests/test_christie_las.py tests/test_seam_normals.py
.venv/bin/python tools/pd2-las/diagnose_mesh.py --pack slim \
  --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
```

- **78 tests passed**, covering both Christie packs and the seam-normal pass.
- Slim: **7,695 vertices / 12,996 triangles**, 66 shells.
- **0 divergent interior coincident-normal pairs**; all 431 retained divergent
  pairs are on borders.
- Sleeve mid-band leakage: **0.00 cm² left / 0.00 cm² right**.
- Sleeve gloss mask covers 100% of its sleeve-face centroid samples; **33
  boot faces / 0.8% of leg-only UV area** still share that footprint. This is
  an offline atlas limitation, not a boot appearance observation in this batch.
- No vertices have a hand-chain weight above 0.5; the wrist blend peaks at 0.40.

These checks constrain topology, attributes and mask scope. They do not
invalidate the visible issues above or establish crash-free gameplay.

**Verification metadata is still misleading:**
[`build_christie_las.py`](../../tools/pd2-las/build_christie_las.py) hardcodes
`runtime_verified: true` using the November 5 base-pack check, and the regression
test asserts that inherited boolean. It is not per-build visual certification.
This screenshot/documentation update does not change that code or rebuild any
pack.

## Next work, in order

1. Record the installed Slim ZIP/payload identity and active head/glove setup.
   Keep the five visual findings open regardless of whether offline tests pass.
2. Isolate the rear forearm patches and the neck bands with the controls above;
   these have the clearest local boundaries and highest visual impact.
3. Isolate the global suit shading channels; do not attribute the back/arm
   patches to the small residual boot UV overlap.
4. Review elbow deformation through motion and the cuff/glove combination
   against vanilla, then make the smallest targeted fix supported by those
   comparisons.
5. Capture matched lobby/menu views plus a short gameplay/FPS check before
   calling the corrected build visually verified.
