# Christie_LAS_Slim — in-game screenshot review (2026-11-07)

Source: 11 user screenshots of the **slim pack** in game (lobby/idle + two
action poses with a sniper rifle). Pack under review is the tracked
`dist/Christie_LAS_Slim.zip`, sha256 `33832eaf…aca7` (4,206,230 B) — the
2026-11-07 rebuild with the elbow round, the cuff taper and the glove adapter.

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
with interpolation before judging them. Measured on the actual packed model, the
slim pack's shading data is *better* than the PD2-authored reference:

| metric | 2B reference (PD2) | Christie slim |
| --- | --- | --- |
| vertices with an incident face >90° off their own vertex normal | 750 / 10361 = **7.2 %** (base) | 480 / 7695 = **6.2 %** |
| "faceted" score (smooth regions only) | **29.9 %** | **6.5 %** |
| tris per 1000 cm² of surface | **695** | 375 |
| texels per cm (1024² atlas) | 5.58 | **9.02** |
| diffuse low-freq / high-freq ratio | 1.18 | 2.24 (clean fabric weave, no baked lighting) |

Also cleared, with evidence:

- **Normal map format is correct.** `c02_01_nm` is R=255, G=varying, B=0 —
  tangent-space DXT5nm. The user-tested `Miranda_LAS` `miranda_body_nm` has the
  byte-identical structure (R=255, G varying, B=0), so this is not a build bug.
- **Specular (diffuse alpha) is fine.** Christie garment alpha sits at mean
  10–12 with ~85 levels, inside the shipped-pack envelope (Miranda body 21.6/64
  levels, lawson body1 17.2/40 levels). The 2026-11-06 sleeve retouch landed.
- **At native 1:1 pixel scale the blazer shades smoothly.** The apparent
  "polygon plates" are the fabric weave in the diffuse plus the matcap, and they
  only read as faceting when upscaled with smoothing.

Lesson for future screenshot reviews: **judge shading at native pixel scale**;
magnification invents structure that is not in the mesh.

## Confirmed issues

### 1. Hard normal seams at duplicated UV-seam vertices — the one real shading defect

This survived every test, and it is the item the withdrawn diagnosis was
groping for. Around duplicated (coincident) vertices, adjacent copies do not
agree on their normal:

| pack | duplicate vertex pairs | pairs with normals >30° apart |
| --- | --- | --- |
| 2B reference (PD2-authored) | 22486 | **0 (0.0 %)** |
| Christie base | 1437 | 857 (59.6 %) |
| **Christie slim** | 949 | **480 (50.6 %)** |

In the reference, duplicated seam vertices carry *identical* normals, so seams
are invisible. In ours, half of them diverge by more than 30°, which shades as a
hard crease/step exactly along the seam. Distribution by height (z, cm):

- z 140–160 (upper chest / collar): 132
- z 0–20 (feet / boot tops): 99
- z 100–140 (waist / hips): 134
- z 80–100: 19

This is the most defensible defect in the set: it is measured against the
reference the project already treats as ground truth, it is deterministic, and
it is testable offline with no game access. Fix direction: after
`_recompute_normals()`, propagate one normal per coincident group (average the
group, or copy the predominant one), the same way `_weld_positions` already
handles positions. Careful: `_recompute_normals` deliberately preserves genuine
hard edges, so do not blanket-smooth — only unify *coincident* vertices.

### 2. Elbow: detached sliver on the outer silhouette

Confirmed at native scale (image 5, x ≈ 86–90, y ≈ 420–470 on the left arm; a
matching one on the right): a thin near-white **spike stands clear of the arm**
with background pixels between it and the sleeve. Not a highlight — there is a
real gap. Consistent with `_elbow_coverage_correction` / the bounded slim fold
solution displacing a vertex whose neighbours did not follow. Bound each moved
vertex's displacement relative to its 1-ring, not only against face inversion.

### 3. Armpit: hole in the sleeve–torso seam

Confirmed at native scale (image 1, x ≈ 330–355 / y ≈ 395–425): a **hard-edged
triangular notch** where the background is visible through the underside of the
arm where sleeve meets blazer, with straight edges too regular to be shading.
Likely the bind-pose-stitched seam opening when `rebind_arms_at_idle` takes the
elbow from PD2's 72° to the idle 12°.

### 4. Wrist line: bare skin band, red UV speck, ragged cuff lip

- A **pale cream/tan band** (RGB ≈ 208,182,171; R−B ≈ +37 vs the sleeve's −4)
  shows between cuff and glove — skin-toned, i.e. the bare wrist between the
  stretched sleeve end and the spawned glove, or the blazer lining.
- A **red texture patch** (peak RGB 187,44,21; 155 px with R−B > 40) sits
  exactly on the wrist seam — the red/white trim island picked up by a UV that
  the stretched boundary falls onto.
- The cuff lip is a **sawtooth** of alternating light/dark rather than a ring.

### 5. Fingertips render spiky

The glove fingers end in thin pointed blades with hard black slots (image 8, 9,
10). Partly the vanilla PD2 glove, but the slivers match this pack's own cut:
`cut_hands()` keeps a face only when all three verts are non-hand, leaving a
ragged open border exactly where the glove spawns and where the sleeve was
stretched past the wrist.

### 6. Soft axis-aligned blotches on the trousers

Confirmed at native scale (image 8, y ≈ 700–730): low-contrast patches with
**stair-stepped axis-aligned edges** — a texture/mip artifact, not geometry.
Most likely `sleeve_uv_masks` splatting its 24-texel disc from arm-weighted
vertices whose UVs land on leg islands, and/or the mask pyramid bleeding across
UI islands at coarse mips. Check that the mask only covers sleeve islands.

### 7. Neck tonal split (head-mod territory — verify ownership first)

A hard vertical boundary on the throat, pale RGB(121,120,127) left vs tan
RGB(147,129,117) right, with horizontal banding. This is almost certainly the
**heister head mod's** UV seam, not this pack. Flagged only so it is not
chased in the wrong repository.

## Suggested order of work

1. **Coincident-vertex normal unification** (item 1) — measured, reference-backed,
   testable offline. Add a test asserting 0 % divergent coincident pairs, matching
   the 2B reference.
2. **Elbow sliver + armpit hole** (2–3) — the two places where the mesh visibly
   comes apart.
3. **Wrist line** (4) — skin band, red UV speck, cuff lip.
4. **Trouser blotches** (6) — mask/mip scope.
5. Defer item 7 to the head mod.
