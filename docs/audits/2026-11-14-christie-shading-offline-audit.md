# Christie packs — offline shading audit for the remaining review items (2026-11-14)

Request 2026-11-14 ("continue fixing" on top of the sleeve round): the
remaining 2026-11-10 review list — neck bands, inner-elbow flap/beak,
coarse suit shading, cuff/glove rim.

Everything below was measured on the tracked bytes in `dist/`
(`Christie_LAS.zip` `1ec1c95a…`, `Christie_LAS_Slim.zip` `ebe44af7…`), the
source `references/Christie.zip`, and the known-good 2B reference. **No model,
texture, hook or ZIP byte changed in this round.** The only edits are docs.
`runtime_verified` stays `false` for everything. `check_all.py --full` after the
docs: rc = 0, 13/13 stages, pytest **711 passed / 5 skipped**, 16/16 tracked
zips rebuild byte-identical.

## Summary

| Defect | Offline verdict | Can this round fix it? | What closes it |
| --- | --- | --- | --- |
| Rear-sleeve wedge | fixed 2026-11-13 (`8dd498b`) | done | in-game re-check when next installing |
| Neck bands | not present in any pack channel measured; pack carries no head | no — the pack is clean on every channel we can read offline | **head on/head off** in-game, same pose/camera/light |
| Inner-elbow flap | not a self-intersection, not a normal kink at the crease; the authored crease lit at grazing angle | no — no defect measurement to repair | in-game rifle-pose capture, rifle vs no-rifle |
| Coarse tonal patches | not a vertex/UV/tangent defect; consistent with coarse tessellation + engine lighting response | no — nothing measurable to repair | matched installed build, then channels one at a time (2026-11-10 next-steps #4) |
| Cuff / glove rim | red speck = AA fringe (closed 2026-11-10); rim = tessellated cut + glove adapter comparison; base carries hands, slim does not | no — must not cut the sleeve further | in-game look at the sleeve/glove/hand stack |

## 1. UV convention and the c02_05 "open observation" — closed

The 2026-11-07 diagnosis carried an open observation ("c02_05 samples outside
`[0, 1]` and clamps"). It is closed now: the section in
[`2026-11-07-christie-slim-diagnosis.md`](2026-11-07-christie-slim-diagnosis.md)
records the measurements on the tracked packs (atom split, source VVD UVs,
the pinned Wrap convention, the 2B reference). Short version: the source
authors the three main materials on the UDIM `[1, 2]` page and `cri_02_05` on
`[0, 1]`; the pipeline stores `(u, 1 - v_src)` losslessly, so atom 3 storing
v ∈ [+0.04, +0.98] while the other islands store v ∈ [-1, 0] is the source's
island placement, not a conversion fault. Tests pin both halves of the
convention (`test_uvs_are_stored_as_u_and_one_minus_v`,
`test_uv_to_texel_frac_matches_udim_wrap_for_both_tile_signs`). Nothing is
clamped; nothing to repair.

## 2. Vertex and tangent integrity (both packs)

Measured on decoded TEXCOORD0/NORMAL/UV_DIRECTION_{U,V}0 of `g_body`
(`s_body` identical bytes):

| probe | slim | base | 2B (reference) |
| --- | --- | --- | --- |
| verts / tris | 7,603 / 12,782 | 10,373 / 17,309 | 27,741 / 35,260 |
| normals | unit [1.0000, 1.0000] | same | — |
| uvdir U / V | unit, exactly ⟂ to normals (max \|u·n\| = 0.0000), 0 zero tangents | same | layout identical (headers 1/7/17/19/2/22/23) |
| handedness | 5,269 unmirrored / 2,334 mirrored islands | 7,145 / 3,228 | mixed likewise |
| face-normal vs avg vertex normal: p50 / p90 / p99 | 6.1° / 38.3° / 119.9° | 7.0° / 33.3° / 114.2° | 6.2° / 20.1° / 39.5° |
| faces with angle > 30° | 12.3 % | 11.1 % | 3.2 % |
| interior coincident pairs disagreeing > 30° | **0** | **0** | 0 |

The p90 gap to 2B is tessellation, not shading: 2B is ~2-3× denser, so its
flat face normals track the smooth ones; ours encode the source's hi-res
curvature in vertex normals that the flat normals cannot represent.

**The > 90° face class (the "bright rim" suspect, measured precisely):**

| | slim | base |
| --- | --- | --- |
| faces with fn·vn < 0 | 323 (2.5 %) | 366 (2.1 %) |
| by g_body atom | atom 0: 173, atom 1: 150 | atom 0: 174, atom 1: 150, atom 2: 42 |
| z band (cm) | mostly 88–130 | mostly 88–130 |
| distance centroid → nearest boundary vertex: p50 / p90 | 1.77 / 3.69 cm | 1.54 / 3.53 cm |
| within 0.5 cm of a boundary (slit rim) | 6 | 21 |
| within 1.5 cm | 118 | 176 |

These are the slit-rim / fold-ridge faces — the class the suite deliberately
leaves divergent at garment folds (`test_interior_coincident_normals_agree`
requires interior == 0 and border > 300). The bright-rim lighting the
2026-11-10 review saw at the inner elbow is consistent with this class
(rim lighting grazing faces whose vertex normals belong to the fold).
**Nothing was rewritten** — smoothing them would break the border invariant
and the authored fold, and there is no in-game confirmation that these faces
render wrong. If a matched capture ever attributes a hard edge to them, the
repair is a normal fix on that strip, not a deletion.

## 3. Self-intersections (exact tri–tri test, arm window)

Exact Möller–Trombore / edge-triangle test over all non-adjacent face pairs in
z ∈ [108, 145] cm, |x| > 14 cm (both packs):

| | slim | base |
| --- | --- | --- |
| faces in window | 1,752 | 1,923 |
| true intersections (non-adjacent) | **633** | **900** |
| by atom pair | (0,0) 91 · (0,1) 470 · (1,1) 72 | (1,1) 129 · (0,1) 303 · (1,2) 212 · (0,0) 147 · (0,2) 100 · (2,2) 9 |
| depth proxy (centroid → other tri): p50 / p90 / p99 / max | 0.23 / 0.68 / 1.10 / 1.41 cm | 0.25 / 0.76 / 1.16 / 1.76 cm |
| within 6 cm of either elbow pivot | **0** | **0** |

The pack's overlaps are the blazer/sleeve shells and the slit-rim bridge faces
crossing the other shell — cloth layering at ≤ 2 mm median depth. The source
has the same class by construction (`cri_02_01_base` alone has 64 in the same
window). **Zero** intersections at the crease, so the inner-elbow flap is not a
penetration. The 633/900 pairs are not visible geometry errors (they are
near-coincident shells hidden under the blazer) and are not edited —
locally pushing shells apart would fight the slit stitch and the sleeve-wedge
closure for zero visible gain.

## 4. Textures as shipped (decoded from the packs)

All `_df`/`_nm` textures decode (DXT5, full mip chains, vanilla header shape —
see 2026-11-13 MODLOG). Measured/previewed:

- throat close-up, textured software render, pack bytes (`/tmp/base_throat.png`):
  smooth skin, collar, clean V — **no band of any kind**;
- neck specular (DF alpha = PD2 specular mask): neck island (mtr_body, z > 142)
  mean **34.6**, max **54** — modest and comparable to the rest of the body
  (mean 27.2, p50 22.0); the dark inner top (`c02_05`) is **3.6** — matte;
- `mtr_body` normal map at the throat: smooth (faint stitch seams only);
- c02_05 diffuse: near-uniform dark (mean RGB ≈ 23/22/25) with fine weave — no
  stripes, nothing that reads as a band;
- the pack **renders hands**: base (2,666 hand-weighted skin vertices per the
  2026-11-07 diagnosis; confirmed in the textured render — full hands at both
  cuffs). Slim is genuinely cut above the hand: skin verts at z < 124 stay
  inside |x| ≤ 16.5 (trousers only) — its cuffs end on bare forearm and the
  vanilla glove unit fills the gap in-game;
- both packs render a tiny red/dark detail at the belt-line centre. It is the
  source atlas's own baked belt item (visible bottom-centre of
  `christie_body_df`), identical in base and slim. Not ours, not a defect.

## 5. Per-defect attribution

### Neck bands — high impact, still undecidable offline

The pack carries **no head at all** (`s_body`, `g_body`, `g_body_lod1`; no
`g_head`). Offline, every pack-side channel of the throat measured clean:

- diffuse: throat close-up renders as smooth skin, no step, no band
  (software rasteriser, cull on);
- specular mask: neck alpha 34.6 / max 54 — not hot;
- normal map: smooth there; vertex normals unit; interior coincident pairs = 0;
- the > 90° suspect class stops at z ≈ 130 cm and is matte-dark `c02_05` there
  (alpha 3.6);
- the throat is 84.3–99.5 % body by surface area in the §10 ownership measurement
  (2026-11-07 diagnosis) — unchanged.

**The only remaining explanation space is the engine's skin-shader response on
the body** (specular quantisation or the collar/throat shell) **or the head
unit's neck rim** (which §10 measured as buried below the collar). Deciding
between them needs the in-game bisect — same heister, pose, camera and
lighting, head replacement on vs off — nothing else has that power. Offline
work for this item is exhausted; do not "fix" the pack on this evidence.

### Inner-elbow flap/beak — the beak stays fixed; the flap is not a geometry defect we can measure

- exact tri–tri: **0** self-intersections within 6 cm of either elbow pivot
  (both packs);
- interior coincident normals: 0 (a fold cannot be shaded by a split vertex);
- elbow deformation probes (2026-11-10) stand: edge compression 1.000 at the
  in-game idle, 0 flipped faces;
- what remains visible in the rifle pose is consistent with the **authored
  crease** in the source (DOA5 models the inner-elbow fold explicitly) lit at
  grazing angle, or with the rim-adjacent faces of §2 catching the key light;
- the slit/boundary line the wedge repair closed (z ≈ 110–114 cm) is in the same
  silhouette and is the brighter rim's more likely host — already measured
  closed (0.00 cm², both packs, 2026-11-13).

No blind edit. The isolation the review asked for (rifle vs no-rifle, matched
camera) is in-game work. If the in-game capture then shows a hard edge, the
fix direction is a targeted normal repair on the crease strip — after that
capture, not before.

### Coarse tonal patches — tessellation and engine response, not a data defect

The coat/trousers patches cross smooth panels and show no fixed sub-structure
(2026-11-10: "not fabric detail"). Everything at the data level measured clean
(§2, §4): unit tangents exactly ⟂ to unit normals, interior normals agreeing,
modest specular mask, smooth NM, faithful source UVs under the pinned Wrap
convention. 2B supports the tessellation reading: ~2-3× the triangles, no broad
banded shading at the same world-size panels, and its face-normal p90
(20.1°) vs ours (33.3–38.3°) is exactly the flat-vs-smooth divergence expected
of the coarser mesh.

The remaining explanation is the engine's own response — lighting/DOS on large
near-flat panels, or the normal-map/specular pair — i.e. precisely the
"global suit shading channels, one at a time, matched installed build" step the
2026-11-10 review schedules as next-steps #4. It is not measurable further
offline, and no channel will be touched without that matched build.

### Cuff / glove junction — the red speck is closed; the join is a comparison

- The "small red/orange marks" are **antialiasing fringe** on the rim light
  (2026-11-10: 948 of 962 red-leaning pixels on the bright object contour,
  **zero** inside the cuff/glove boxes, 100 % in shots 05/06/07). This review
  carried that forward: **not an open texture defect.**
- The pale band and stepped rim are real but they are the **sleeve/hand/glove
  stack**, not the glove: base ships hands (§4), slim ends on bare forearm.
  Ownership sits with the vanilla glove adapter and the alternative glove —
  the review's call stands: *not* a reason to cut more sleeve.
- Measured rim (mouth + slit-end merged boundary components): two components
  per wrist at z ≈ 110.7–113.6 cm (base: ≈ +39.9/+42.8 cm and −40.1/−40.9 cm;
  slim: ≈ +42.8/−40.1 cm at z 110.7–113.2), 12–42 vertices each, zero vertices
  of degree > 2 (no T-junctions), ring radius spread 6.9–9.6 cm (the spread is
  the slit end riding the mouth's circle, not a stepped circle). The unevenness
  the review saw is the tessellated cut line at glancing angle.
- No change made; any in-game look belongs to a matched sleeve-vs-glove
  comparison, not to another offline reshape.

## 6. What changed this round

- docs only: [`2026-11-07-christie-slim-diagnosis.md`](2026-11-07-christie-slim-diagnosis.md)
  (the c02_05 open observation closed with measurements) and this file.
- `dist/` bytes unchanged; both packs remain the `8dd498b` builds; sidecars,
  BUILD_INFO, pins and docs that do pin bytes all still match (verified this
  round: `sha256sum` matches `BUILD_INFO.json` and `pins.txt`).
- `check_all.py --full` rc = 0 after the docs; tracked zips rebuild identically.

## 7. The user's side of the fence (the only remaining deciders)

1. **Neck bands** — lobby or menu shot, same heister, same pose/camera/lighting:
   once with the replacement head, once with it off. Same band either way →
   the engine skin shader on the body; gone with the head → the head unit's
   neck rim; report which, and the fix lands as a texture/shader-side change.
2. **Inner-elbow flap** — one rifle-pose capture, rifle vs no-rifle, same
   camera. If a hard edge persists in both, flag it and the crease strip gets
   a targeted normal repair; if it is softer without the rifle, it is the
   authored fold and nothing to fix.
3. **Coarse tonal patches** — two matched captures on the installed build;
   then the channels (diffuse, specular mask, normals) one at a time.
4. **Cuff rim** — matched close-up of the sleeve/glove junction; if uneven
   enough to matter after this, the fix is a mouth-ring low-pass on the rim
   vertices (a small, silhouette-safe edit) — but only with that evidence,
   because the glove adapter is not ours.
5. Standing questions, unchanged from 2026-11-13: the PR for
   `arena/4f5923fc-universal-modder` is not opened; the D18 `xfail` removal
   without sign-off (check_skip_budget, `ALLOWED_XFAIL = {}`, the three sleeve
   probes now plain assertions) is still flagged for the user's call.

`runtime_verified` remains `false`. Nothing in this file claims in-game
behaviour for any of the five defects.

## 8. Continuation-round addendum (same day, after a sandbox rollback)

The workspace rolled back to `6f26633` at the start of the continuation round:
`.venv` was gone, `dist/` held pre-`8dd498b` bytes, and the local branch ref had
moved. The remote branch on origin held `85b757c`, so recovery was
`git fetch origin arena/4f5923fc-universal-modder && git reset --hard FETCH_HEAD`
plus `bash tools/pd2-las/recover_env.sh --extras`; `dist/` bytes match the
`8dd498b` pins again (`1ec1c95a…` / `ebe44af7…`), and the tree is otherwise
byte-identical to the state this file was written for.

Two read-mostly probes were added to close the remaining unexamined classes:

**Degenerate / sliver triangles** — zero zero-area faces in both packs.
Min-angle < 2.5°: slim 174 of 12,782, base 157 of 17,309 — concentrated in the
forearm slit-rim zone (16 / 10 faces at |x| > 33 cm, z ∈ [105, 121] cm),
i.e. they *are* the seam-stitch bridge quads and cannot be eliminated without
re-opening the slit. **In the crease window (z ∈ [124, 145], |x| > 25 cm,
y > −2): 0 (slim), 1 (base; 1.86°, 0.2 cm² — sharp but not degenerate).**
No degenerate-triangle defect exists to repair.

**Collar / neck zones (the "pale band" hypothesis, closed):**

| zone | faces (base / slim) | p50 | p90 | > 30° |
| --- | --- | --- | --- | --- |
| collar band z [144,152) | 630 / 633 | 5.2° / 5.2° | 27.1° / 26.2° | 8% / 7% |
| neck/jaw top z [152,165) | 1,144 / 1,140 | 8.2° / 8.6° | 49.5° / 49.7° | 17% / 17% |
| throat hollow z [140,144) | 439 / 439 | 4.0° / 4.0° | 18.7° / 18.5° | 5% / 5% |
| c02_05 zone z [130,140) | 1,177 / 1,182 | 5.4° / 5.3° | 26.7° / 26.2° | 8% / 7% |

The > 30° neck faces are smooth shading over the neck's curvature under the
jaw (authored, expected), and the collar's standing edge carries **no specular
boost**: the collar island's DF alpha is 10.6 vs the whole blazer island's 10.3,
identical in both packs (p50 10.0 everywhere). The pale band is therefore not
driven by pack-side collar gloss either. The three strata the screenshot
review counted (pale band / darker throat / abrupt chest step) match the
authored collar-rim → shadowed hollow → shirt front stack, with rim light on a
hard horizontal edge as the most probable enhancer. Attribution and the
remedy remain with the in-game head on/off bisect (§5) — nothing here
identifies a pack byte as the cause, and no specular or normal edit is
defensible offline.

**Net: no new repairable defect surfaced. Attribution is unchanged.**
