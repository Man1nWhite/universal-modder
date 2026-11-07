# Christie_LAS_Slim — in-game screenshot review (2026-11-07)

Source: 11 user screenshots of the **slim pack** in game (lobby/idle + two
action poses with a sniper rifle). Pack under review is the tracked
`dist/Christie_LAS_Slim.zip`, sha256 `33832eaf…aca7` (4,206,230 B) — the
2026-11-07 rebuild with the elbow round, the cuff taper and the glove adapter.

**Update, later on 2026-11-07:** this review describes the pack as it was
shipped that morning. The sleeve has since been rebuilt with
`stitch_sleeve_seams` (sha256 `14f75d66…`): the lengthwise slit and the
4-vertex hole at the back of each elbow are closed, so the tube is watertight
along its length — see §8 of `2026-11-07-christie-slim-diagnosis.md`. That does
not settle item 2 below: the diagnosis attributes the *outer-silhouette* sliver
to pose coverage, not to the hole, which is always backed by the opposite wall
of the sleeve.

The user confirmed a **heister head mod is in play**, so the Christie face/hair
visible in the shots is not from this pack (which is `headless: true`). Head
appearance is out of scope below.

The screenshots are archived byte-identical in
[`docs/pd2-las/screenshots/`](../pd2-las/screenshots/) so the crops referenced
below stay reproducible:

| shot | file | view |
| --- | --- | --- |
| 1 | `christie_slim_01_lobby_front-three-quarter.png` | lobby, front 3/4 |
| 2 | `christie_slim_02_lobby_front.png` | lobby, front |
| 3 | `christie_slim_03_lobby_front-three-quarter-wrist.png` | lobby, front 3/4, wrist |
| 4 | `christie_slim_04_lobby_right-profile.png` | lobby, right profile |
| 5 | `christie_slim_05_lobby_back.png` | lobby, back |
| 6 | `christie_slim_06_lobby_back-three-quarter.png` | lobby, back 3/4 |
| 7 | `christie_slim_07_lobby_left-profile.png` | lobby, left profile |
| 8 | `christie_slim_08_menu_back-rifle.png` | menu, back, rifle |
| 9 | `christie_slim_09_menu_left-profile-rifle.png` | menu, left profile, rifle |
| 10 | `christie_slim_10_menu_front-rifle.png` | menu, front, rifle |
| 11 | `christie_slim_11_menu_right-three-quarter-rifle.png` | menu, right 3/4, rifle |

Pixel coordinates below are in **each file's own pixel space**, not a shared
canvas — the source crops are all slightly different sizes (491–563 px wide).

## Correction (read this first)

A first pass of this review blamed a **"blocky / faceted shading"** problem on
`_recompute_normals()` keeping stale authored normals. **That diagnosis was
wrong and is withdrawn.** It was an artifact of magnifying the screenshots 6–20×
with interpolation before judging them.

The table that replaced it was wrong too, in both columns. The cell labelled
"2B reference (PD2)" held the **Christie base** pack (10,361 vertices is
`christie.model` `g_body`), "695" is not the reference's triangle density, the
texel-density row contradicts itself (it gives 5.58 to a pack that measures 5.52
and 9.02 to one that measures 5.51), and two of its metrics — "faceted score"
and "diffuse low-freq / high-freq ratio" — were never defined anywhere in the
tooling. Re-measured with `tools/pd2-las/audit_metrics.py` on the shipped packs:

| metric | 2B reference (PD2) | Christie base | Christie slim |
| --- | --- | --- | --- |
| vertices / triangles | 27,741 / 35,260 | 10,361 / 17,351 | 7,695 / 12,996 |
| vertices with an incident face >90° off their own vertex normal | 65 = **0.23 %** | 788 = 7.6 % | 522 = 6.8 % |
| same, per 1,000 triangles | **1.8** | 45.4 | 40.2 |
| tris per 1,000 cm² of surface | **1,024** | 448 | 376 |
| texels per cm (1024² atlas) | **5.52** | 5.20 | 5.51 |

**Read the normalized row, not the percentage.** Percentage-of-vertices falls as
a mesh gets denser, and the reference has 2.7× our triangles and 3.6× our vertex
count, so the raw column is density-confounded; per 1,000 triangles says the
same thing, so the conclusion holds either way. It is narrower than the old
one: slim's normal/face agreement (6.8 %) is in the same band as this project's
own **base** pack (7.6 %) and roughly 20–25× the reference's rate. The claim
that the slim pack's shading data is *better than the PD2-authored reference*
does not survive — it rested on the mislabelled column.

Also cleared, with evidence:

- **Normal map format is correct.** `c02_01_nm` is R=255, G=varying, B=0 —
  tangent-space DXT5nm. The user-tested `Miranda_LAS` `miranda_body_nm` has the
  byte-identical structure (R=255, G varying, B=0), so this is not a build bug.
- **Specular (diffuse alpha) is in range.** `audit_metrics.py --alpha` over the
  **whole 1024×1024 texture** — all texels, unused padding included, which is
  the region these numbers describe — gives Christie garment `c02_01_df`
  mean alpha **10.13 / 85 distinct levels** (p10 4, p50 9, p90 16, max 255 on
  0.07 % of texels), against Miranda's shipped `body_df` **21.63 / 64** and
  lawson's `body1_df` **17.23 / 40**. The 2026-11-06 sleeve retouch landed; the
  garment is the *least* transparent of the three.
- **At native 1:1 pixel scale the blazer shades smoothly.** The apparent
  "polygon plates" are the fabric weave in the diffuse plus the matcap, and they
  only read as faceting when upscaled with smoothing.

Lesson for future screenshot reviews: **judge shading at native pixel scale**;
magnification invents structure that is not in the mesh.

## Confirmed issues

### 1. Hard normal seams at duplicated UV-seam vertices — fixed

This survived every test, and it is the item the withdrawn diagnosis was
groping for. Around duplicated (coincident) vertices, adjacent copies did not
agree on their normal:

| pack | duplicate vertex pairs | pairs with normals >30° apart | interior (before the fix) | on a border edge |
| --- | --- | --- | --- | --- |
| 2B reference (PD2-authored) | 22,486 | **0 (0.0 %)** | 0 | 0 |
| Christie base | 1,440 | 806 (56.0 %) | 0 (**was 50**) | 806 |
| **Christie slim** | 953 | 431 (45.2 %) | 0 (**was 49**) | 431 |

In the reference, duplicated seam vertices carry *identical* normals, so seams
are invisible. In ours, half of them diverged by more than 30°, which shades as
a hard crease/step exactly along the seam. Distribution by height, in uniform
20 cm bins (`audit_metrics.py --z-hist`), summing to the *diverged* column:

| z band (cm) | slim, shipped | slim, before the fix | base, shipped |
| --- | --- | --- | --- |
| below 0 (boot soles / shoe lining) | 87 | 87 | 87 |
| 0–20 (boot tops) | 99 | 99 | 100 |
| 80–100 | 19 | 19 | 359 |
| 100–120 (waist / hips) | 43 | 68 | 76 |
| 120–140 (sleeve) | 56 | 66 | 56 |
| 140–160 (chest / collar) | 121 | 132 | 122 |
| 160–180 | 6 | 9 | 6 |
| **sum** | **431** | **480** | **806** |

The earlier version of this list gave four ad-hoc bins that summed to **384 of
480** — it omitted the crown of the head and, more importantly, everything below
z 0, where a fifth of the divergent pairs live (the shoe's inner and outer
surfaces share positions).

**Fixed 2026-11-07** (`unify_coincident_normals` in
`tools/pd2-las/build_christie_las.py`): every *interior* coincident group gets
one shared normal, the group mean; shadow. Borders keep both normals — a copy
that sits on a border edge is the edge of a garment panel (cuff rim, sleeve
mouth, lining edge), and those are genuine folds, not UV splits. Slim unifies
98 copies over 49 groups, base 100 over 50; the worst interior pair is 101
(slim) / 103 (base) degrees, so the mean stands within ~50° of both sides —
pairs beyond 120° are skipped rather than averaged into a sideways normal.
Measured after the change: **0 interior divergent pairs in both packs**, 431 /
806 border pairs untouched, winding agreement 97.1 / 97.2 %, 0 orientation
breaks. Rendered with a Gouraud shader that interpolates the *stored* normals
(the repo renderers shade per face and cannot show this), the change is
invisible from the front and softens the back/collar and lapel seams; median
normal change 22.6°, maximum 50.6°. Guarded by
`test_interior_coincident_normals_agree` (shipped packs *and* the 2B reference,
which must stay at 0 of 22,486) and `tests/test_seam_normals.py` (the pass
itself, on hand-built meshes).

### 2. Elbow: detached sliver on the outer silhouette

Confirmed at native scale — `christie_slim_05_lobby_back.png`, crop
(60, 400)–(130, 490), nearest-neighbour ×5: at x ≈ 86–90, y ≈ 420–470 on the
left arm (and a matching one on the right) a thin near-white **spike stands
clear of the arm** with background pixels between it and the sleeve. Not a highlight — there is a
real gap. Consistent with `_elbow_coverage_correction` / the bounded slim fold
solution displacing a vertex whose neighbours did not follow. Bound each moved
vertex's displacement relative to its 1-ring, not only against face inversion.

### 3. Armpit: hole in the sleeve–torso seam

Confirmed at native scale — `christie_slim_01_lobby_front-three-quarter.png`,
crop (325, 390)–(365, 430), nearest-neighbour ×12: at x ≈ 330–355 / y ≈ 395–425
a **hard-edged triangular notch** where the background is visible through the underside of the
arm where sleeve meets blazer, with straight edges too regular to be shading.
Likely the bind-pose-stitched seam opening when `rebind_arms_at_idle` takes the
elbow from PD2's 72° to the idle 12°.

### 4. Wrist line: bare skin band, red UV speck, ragged cuff lip

All three are visible in one crop: `christie_slim_03_lobby_front-three-quarter-wrist.png`,
crop (300, 540)–(410, 630), nearest-neighbour ×5. Re-measured in that crop
(the first pass quoted a "cream band" without saying where it sampled):

- The **pale band just under the cuff lip** (box x 318–336, y 578–584, right at
  the sawtooth) averages RGB **(188, 175, 177)**, R−B = **+11**, against the
  sleeve above it at (206, 201, 201), R−B = +5. So the band is barely warmer
  than the garment: it is not obviously bare skin. A much warmer patch does
  exist in every shot (the statistic reaches R−B = +108 on the hand itself),
  which is probably where the earlier "208,182,171 / +37" figure came from — it
  measured skin, not the band. The diagnosis reaches the same conclusion from
  the mesh: the band is the **open cuff interior** plus ~0.5 cm of skin, and
  the pack contributes only the open ring.
- The **red texture patch** — the one hard fact here: peak RGB **(187, 44, 21)**
  at about (343, 583), 128 pixels with R−B > 40 and R > 120 inside the 40×40
  box (325, 565)–(365, 605). It sits exactly on the wrist seam.
- The cuff lip is a **sawtooth** of alternating light/dark rather than a ring
  (the top of the same crop).

### 5. Fingertips render spiky

The glove fingers end in thin pointed blades with hard black slots
(`christie_slim_08_menu_back-rifle.png`, `…_09_…`, `…_10_…`; in shot 8 the hand
sits at x 300–430, y 640–760). Partly the vanilla PD2 glove, but the slivers match this pack's own cut:
`cut_hands()` keeps a face only when all three verts are non-hand, leaving a
ragged open border exactly where the glove spawns and where the sleeve was
stretched past the wrist.

### 6. Soft axis-aligned blotches on the trousers

Confirmed at native scale — `christie_slim_08_menu_back-rifle.png`, crop
(150, 680)–(360, 760): low-contrast patches with **stair-stepped axis-aligned
edges**, i.e. a texture/mip artifact, not geometry.

The mechanism is **per-block specular attenuation, not the splat edge**. The
diagnosis measures it: `sleeve_uv_masks` builds a 24-texel disc mask from
arm-weighted vertices and `retouch_sleeve_gloss` attenuates **diffuse alpha
only** (the specular mask), **per 4×4 DXT block, at every mip**. So it cannot
change albedo at all, and its edge is quantised to the block grid: ~0.7 cm per
block at mip 0 on the suit, ~5 cm axis-aligned patches at mip 3 — which is
exactly the stair-stepped look. There is no "UI island" bleed to chase: the pass
writes to one atlas, `c02_01_df` (the suit), and the pack ships nine textures —
the icon, the skin df/nm pair, and a df/nm pair per garment material. None of
them is a UI sheet.

Two corrections to the first pass: the mask is far narrower than "the trousers"
— of the 151 leg-only faces it touched, 123 are at z 0–20 cm, i.e. the **shoes**
(3.2 % of the leg faces' UV area) — and the artifact is a *gloss* difference, so
it reads as a slightly different sheen, not as a stain.

**Fixed in the 2026-11-07 follow-up build.** The mask no longer comes from
vertex discs: each sleeve
face's UV triangle is rasterised into the atlas (`sleeve_uv_mask`, 3-texel
feather clipped to the footprint so no texel outside the sleeve is touched), and
`retouch_sleeve_gloss` attenuates **mip 0 only**, then regenerates the pyramid
from it (`mip_payloads_from_mip0`), so the mip chain is a filtered version of one
full-resolution mask instead of a separately quantised one per level. Measured
off the shipped packs:

| | first pass | this build |
|---|---|---|
| leg-only UV area touched | 3.2 % | **0.8 %** |
| leg-only faces touched | 151 | **33** (all z 2.6–11.9, the shoes) |
| sleeve faces covered | — | 100 % (1,740 faces) |
| alpha inside / outside the mask | — | 5.51 / 11.25 (0.49×) |
| mip count, texture payload | 11, 1,398,256 B | 11, 1,398,256 B |

The remaining 33 faces are **atlas sharing, not mask reach**: their UVs sit
inside the sleeve islands of `c02_01_df` (mask value up to 1.00 at their
centroids), so those texels are sampled by both the sleeve and the boot and no
mask can separate them. Removing that residue needs the boots re-UV'd, which is
a texture-authoring change, not a build pass.

### 7. Neck tonal split (measured twice — the first measurement was read backwards)

A hard vertical boundary on the throat, pale RGB(121,120,127) left vs tan
RGB(147,129,117) right, with horizontal banding.

The first pass guessed a heister-head UV seam and left it alone because the head
was not in the repository. It is: `tools/build_joy_head_mods.py` builds the nine
head-replacement packs, and four of them put a Miranda head over a heister — the
combination a Christie LAS player actually sees, because LAS keeps the heister's
head. `tools/pd2-las/neck_junction.py` was written to measure the junction, and
its first answer ("~70 % of the throat is the head's skin, the head's neck border
is 110/110 front-most, so the rim at z 149.5 is the hard line") was **wrong**:
the front-most surface is the largest y (+y is the character's front), the
exposure test and the winner test both compared the other way round, the border
set was all 53 of the head's boundary loops instead of the neck rim, and the
committed render had the camera behind the character. §10 of the diagnosis has
the details and the fixes, now pinned by tests.

Corrected, over `dist/Christie_LAS.zip` with the four `Miranda_L4D2_over_*`
heads:

- **0.0 % of the throat window is see-through** — the pale half is a surface;
- the **body owns 84.3–99.5 %** of the window (Joy 99.5 %, the other three
  84.3 %), the head 0.5–15.7 %: the tan is the body's own `mtr_body` skin, the
  pale is the white blazer, and the head's neck is buried behind both;
- **0 of 98–120 head neck-rim edges are exposed**, from the front or from
  behind, so the rim is not the line either — and it never was;
- the body does not split itself: its throat samples one uniform tan on both
  sides (205,157,128 in the front band, the darker samples at x ±3.5–5.0
  mirrored exactly).

The skirt extension that the first pass proposed shipped anyway, for the reason
in §10.3: it puts the head's open end 6.5 cm deeper inside the torso for the
bodies and collars this audit has not measured. On this body it changes no cell:
`neck_junction.py --ab` reports 0 of 2,401 throat cells changing owner between
the 2026-11-05 packs and the skirted ones.

**Item 7 stays open**, with a bisect instead of a theory (diagnosis §10.4):
uninstall the head pack, keep the slim body, and look at the throat again. If the
boundary survives, it is the body; if it vanishes, it is the head pack's hair
sheets, which are the only part of that head still in front of the blazer.

## Suggested order of work

1. ~~**Coincident-vertex normal unification** (item 1)~~ — **done**:
   `unify_coincident_normals`, 0 interior divergent pairs in both packs, borders
   left as folds, tests in `tests/test_seam_normals.py` and
   `test_interior_coincident_normals_agree`.
2. **Elbow sliver + armpit hole** (2–3) — the two places where the mesh visibly
   comes apart.
3. **Wrist line** (4) — skin band, red UV speck, cuff lip.
4. ~~**Trouser blotches** (6)~~ — **done**: face-raster mask scoped to the
   sleeve islands, mip 0 attenuated and the pyramid regenerated (0.8 % of the
   leg UV area left, and that residue is atlas sharing with the boots).
5. **Neck split** (7) — measured twice, corrected once; **open**: neither the
   head's neck rim nor the body's UVs split the throat offline, so the next step
   is the in-game bisect above (diagnosis §10).
