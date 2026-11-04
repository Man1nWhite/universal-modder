# Lawson pack journal

> The **current state** lives in [`STATUS.md`](STATUS.md) — what is shipped,
> the measured check results, the open problem and the workflow traps. This
> journal is the history behind it.

## 2026-11-04 — BusinessWoman: match body skin colour to Miranda's head texture (NEW)

- **Report:** user asked to make the skin textures' colour closer to Miranda's head
  texture colour. The exposed body skin (neck, chest, legs) read too light / pink
  against the tan heister head at the seam.
- **Root cause.** The authored body albedo is a flat base = `REFERENCE_TONE *
  BODY_TONE_GAIN`. It was sampled from the *2B* face swatch (181,155,142 ×1.06 ≈
  192,164,150) — a different, lighter/pinker skin than the Miranda head the outfit
  actually pairs with.
- **Measured.** Skin-masked median of `miranda_head_df.texture` = **(172,134,106)**
  (the face swatch agrees at 172,133,106). Set `REFERENCE_TONE=(172,134,106)` and
  `BODY_TONE_GAIN=1.0` so the body albedo base IS the head skin tone.
- **Verified.** Re-baked the body skin and decoded the SHIPPED zip: `bw_body_df`
  skin median = (172,133,106) vs Miranda head (172,134,106) — a 1/255 match; a
  side-by-side swatch is indistinguishable. +1 regression test pinning the bake base
  tone to the Miranda head skin median (±4/255) so it cannot drift again.
- **Build/gates:** zip sha256
  `3b052a0d994711ad60c7d3a3aa860f554d931a52d1dcb425460745f9def4d77c`, 26 entries.
  pytest 432 passed / 9 skipped / 1 pre-existing Miranda failure; kb PASS 246;
  publish 26 / 0 / 1; pyflakes clean.

## 2026-11-04 — BusinessWoman: fix forearms — the white wrist ring was SHIPPED SOURCE HANDS; enforce the adapter route

- **Report:** user asked "Fix foreams" (forearms). In-game shots show a **white ring at
  the wrist** between the blazer sleeve end and the blue game glove, plus tan hands.
- **Root cause.** A posed per-material render showed the wrist ring / hands are a
  separate `mtr_hands` slice: the shipped zip had regressed to a **hands-containing
  model** (source/graft hands, 3278 hand verts, z112–126). Their wrist stub protrudes
  below the blazer sleeve (sleeve ends z117.7; hands reach z112) and reads as the white
  forearm/wrist ring. The adapter route is supposed to ship *no* hands so the heister's
  gloves + the vanilla `hnd_forearms` adapter are the only hands visible.
- **Fix.** Repack the true adapter route (no `mtr_hands`, no hand-weighted verts) and add
  a build-time guard: `count_hand_verts` (>0.5 weight on any `LeftHand*`/`RightHand*`
  bone) must be 0 for body + shadow in adapter mode, else the build aborts. This makes
  the regression impossible to ship again. The body forearm ends at z119.1 and the shirt
  cuff at z119.0, both *inside* the blazer sleeve (ends z117.7), so with the hands gone the
  sleeve mouth is cleanly filled in-game by the forearm adapter + glove; no white ring.
- **Verified:** posed wrist render now shows an open cuff (filled by the game adapter
  in-game) with no tan hands and no protruding wrist stub; `mtr_hands` absent from every
  TPP drawable in the shipped zip. No hand geometry authored (adapter route preserved).
- **Build/gates:** zip sha256
  `843d40695b960ac5d9f2807e24bbd121d5d49938a64707831e30eace09f6adb8`, 26 entries (same
  clean adapter+neck build as the neck cycle). pytest 431 passed / 9 skipped / 1
  pre-existing Miranda failure; kb PASS 246; publish 26 / 0 / 1; pyflakes clean.
  +2 `count_hand_verts` regression tests.

## 2026-11-04 — BusinessWoman: fix the neck position — recenter + taper onto the PD2 head-neck axis

- **Report:** user asked "Fix the neck position." With the template head attached
  offline, the outfit showed a hard horizontal skin **shelf** across the front of the
  neck base and a **notch** behind it where the collar met the head neck.
- **Root cause (measured, not guessed).** The retargeted 3BA skin neck is a *wide*
  tube whose axis sits at y≈9.5 cm and whose diagonally-cut opening rim centroids at
  y≈13.6 cm. The PD2 heister head (`2b.model` `g_head`) carries its own *thin* neck:
  centered y≈7.5 cm, radius ~2.5 cm at z158 and ~3.1 cm at z159, starting at z≈157.
  `trim_neck` alone only *squashed* the wide stub down to the collar line, collapsing
  it into a forward-offset pancake (cap centroid y≈13.6) — the shelf in front and the
  gap behind. Squashing never repositioned the opening.
- **Fix: `align_neck` (new, runs before `trim_neck`).** Blend every skin vertex above
  z154 from the source neck axis (y9.5) onto the PD2 axis (y7.6) while tapering its
  radial extent from the shoulder flare (6.5) down to 2.1 at z158 and above — i.e.
  *inside* the heister's own neck radius, so the tapered column, the folded stub and
  the `cap_holes` cap all hide within the head neck and the visible seam is where the
  two surfaces cross (~z157.6). The blend is a smoothstep (0 at z154) times a radial
  gate (1 inside 9 cm of the source axis, fading to 0 by 12 cm) so the outer shoulder /
  upper-arm skin stays exactly as the sleeve / underarm tucks shipped it. 739 verts
  aligned (body + shadow); `trim_neck` still folds 305; cap still 26 tris.
- **Verified offline with the reference head attached** (head never shipped): front
  shelf gone, back notch gone, neck seams smoothly into the head; cap centroid moved
  from (0, 13.6, 159.2) to (0, 9.0, 159.3) with a 3.9×1.9 cm footprint that sits inside
  the head neck cross-section. Outer shoulder silhouette unchanged (the accepted
  armhole sliver residue is untouched). No head or hand geometry authored.
- **Build/gates:** zip sha256
  `843d40695b960ac5d9f2807e24bbd121d5d49938a64707831e30eace09f6adb8`, 26 entries,
  11,537,339 bytes; decode-verified the shipped zip carries the recentered neck.
  pytest 429 passed / 9 skipped / 1 pre-existing Miranda failure; kb PASS 246;
  publish 26 / 0 / 1; pyflakes clean. +3 `align_neck` regression tests.

## 2026-11-04 — BusinessWoman: white arm patches are SKIN, not shirt — extend the skin tuck

- **Report:** 6 new in-game screenshots of the `90df4d6` pack — the white upper-arm
  patches and wrist rings are STILL there. The shirt-sleeve / cuff tucks did not
  remove them.
- **Root cause corrected (again).** A posed render with `mtr_body` highlighted GREEN
  shows green exactly where the white patches are, while `mtr_jacket2`=RED shows only
  the collar. So the patches are the **arm skin poking through the blazer**, not the
  shirt. The earlier shirt tucks targeted the wrong layer. (The skin reads *white*
  in-game because of the lighting on the exposed poke-through, not because of albedo.)
- **Why the old tuck missed it.** `tuck_underarm_skin` only covered the armpit band
  z 137–154. A nearest-blazer probe found **837 poke-through skin verts at z 125–137**
  (down the upper-arm sleeve) that the band never touched.
- **Fix:** extend `tuck_underarm_skin` `z_lo` 137 -> **125** (same gentle 0.7 cm
  skin-normal tuck; amount unchanged, per the documented dead-end that stronger tucks
  distort). Tucked verts 1753 -> **2569** (body + shadow). The posed skin=green render
  drops from large patches to **two thin slivers** at the genuine armhole overlap gap
  (the residue the MODLOG already notes cannot be closed without the spike-producing
  weld). Normal renders stay clean.
- **Build/gates:** zip sha256
  `7cb7702957913e44dcf87220082feb0a68f839e4aa5c971ccab1d9de9e627de8`, 26 entries.
  pytest 426 passed / 9 skipped / 1 pre-existing Miranda failure; kb PASS 246;
  publish 26 / 0 / 1; pyflakes clean. +1 upper-arm-band regression test.

## 2026-11-04 — BusinessWoman: forearms — retract the white wrist cuff into the sleeve

- **Report:** user asked "What about forearms?" Zooming the in-game screenshots shows
  the forearm sleeve itself is clean; the defect is at the **wrist** — a white shirt
  cuff ring, then a dark gap, then the blue game glove.
- **Root cause.** The shirt cuff (`mtr_jacket2`) is a ring of 100 %-`ForeArm`-weighted
  verts sitting right at the sleeve *opening* (z~125). The earlier radial
  `tuck_shirt_sleeves` hides the shirt along the arm but not here: there is no blazer
  beyond the opening to hide behind, so the cuff shows as a white ring.
- **Fix: `tuck_shirt_cuffs`.** Slide the cuff verts up the forearm along the measured
  wrist->elbow axis AND pull them toward that axis (project onto the axis, pull
  inward), so the cuff sits *inside* the blazer tube rather than on its edge.
  Verified: shirt end moves z 124.9 -> 127.2 (3 cm above the blazer opening), radial
  distance 2.89 cm = over the skin (2.58) and under the blazer (3.31) — no clipping.
  A before/after wrist render shows the visible shirt area shrink. Body + shadow,
  1828 verts each. No hand geometry authored (standing constraint).
- **Limits.** The offline rigid pose still shows a little shirt up through the sleeve
  opening at the exact arms-vertical angle; the retraction reduces but does not fully
  eliminate it, and the residual cuff->glove gap is inherent to the adapter route.
  The forearm itself renders clean in profile (no poke-through).
- **Build/gates:** zip sha256
  `0fce7aee2469a616d9185fa60d841c4db921121517966e5f7b56eb8861b35b4b`, 26 entries.
  pytest 425 passed / 9 skipped / 1 pre-existing Miranda failure; kb PASS 246;
  publish 26 / 0 / 1; pyflakes clean. +2 cuff regression tests.

## 2026-11-04 — BusinessWoman: white upper-arm patches = shirt sleeves, tucked

- **Report:** user sent 4 in-game screenshots of the `0b049e9` pack — legs now
  smooth and uniform (albedo fix confirmed in-game), game gloves now show (adapter
  confirmed), but white patches persist on the upper arms and a white ring shows at
  the wrist between the sleeve cuff and the glove.
- **Root cause corrected.** The prior cycle probed `mtr_jacket2` only at z>140 and
  found zero verts, concluding the white patches were skin. That band was too high:
  the shirt sleeves actually sit at **z 124.6–130.6, |x| 30–50** (2016 verts, 100 %
  arm-weighted). They are the white shirt under the black blazer, poking through /
  z-fighting the blazer sleeve in-game. The offline rigid-arm sim never reproduced it
  (even with an elbow bend) because the game's skinning brings the two nearly
  coincident sleeves closer than the sim does.
- **Fix: `tuck_shirt_sleeves`.** For jacket2 verts in the upper-arm band
  (z 116–138, |x|≥20), push inward along the vertex normal by up to 1.6 cm with a
  smoothstep proximity falloff to the nearest blazer vert. This raises the
  shirt↔blazer separation (mean 1.09 → 1.75 cm, verified in the shipped model) so the
  shirt stays hidden under the blazer. The visible collar/lapel (small |x|) and the
  blazer itself are untouched; the amount is capped to avoid pushing the shirt
  through the arm skin underneath. Applied to body + shadow.
- **Verification limits.** The offline pose sim cannot reproduce the in-game
  poke-through, so the fix is validated geometrically (separation increased, no skin
  clipping in the tucked render) rather than by reproducing the defect. The wrist
  white ring is the same shirt cuff and is partly tucked by the same band; a residual
  gap is inherent to the adapter route (no authored hands to bridge cuff→glove).
- **Build/gates:** zip sha256
  `79e6b23fdbbd1fa3da6206e23a9e40845a6afc3708936fbc75f8745722aed390`, 26 entries.
  pytest 423 passed / 9 skipped / 1 pre-existing Miranda failure; kb PASS 246;
  publish 26 / 0 / 1 no-README warning; pyflakes clean. Added 2 tuck regression tests.

## 2026-11-04 — BusinessWoman: uniform albedo (real blotch fix) + stop authoring hands

- **Report:** user sent 6 in-game screenshots — leg blotches STILL present, grafted
  hands look pale/claw-like, white patches at the shoulders — and said **"Don't try
  to author hands."**
- **Leg blotches → the albedo was the real source.** The prior flat-normal +
  uniform-gloss fix was necessary but not sufficient: `build_diffuse` still layered
  a low-frequency fbm mottle, a curvature/occlusion term and an `_anatomy_shading`
  pass (knee/shin/ankle bands) into the diffuse RGB. Decoding the shipped
  `bw_body_df.texture` and amplifying deviation ×6 showed broad leg patches (std
  ~6/255). **Fix: uniform albedo** — removed every variation layer, ship a flat base
  tone; geometry normals + game lighting do the shading. Verified: decoded shipped
  texture now has max deviation 2.7/255 (DXT5 block noise only), gloss std 0. The
  offline idle render shows smooth, even legs. Knowledge note 30 corrected.
- **Hands → adapter route, nothing authored.** Switched `--hands` default from
  `graft` to `adapter`: no PD2 hands are baked into the mesh. To avoid the old
  adapter's no-hands failure, the compat hook now keeps `body_replacement.hands =
  false` so the heister's **stock hands show as a guaranteed fallback**; any glove
  that spawns sets `var_hands_replace = 1` and replaces them (no double hands).
  Corrected the LuaJIT harness (stock hands survive a replaced body — the
  `body_replacement` flags are independent) and added a glove-spawn-failure fallback
  test. `test_glove_behavior_lua` 10/10, `test_glove_adapter` updated.
- **White shoulder patches → skin through the armhole, not the bustier.** Verified
  `mtr_jacket2` has ZERO vertices in the upper-arm band (z>140, |x|>20), so the white
  patches are the arm/shoulder skin showing through the overlap armhole, rendered
  pale by the old blotchy albedo. The uniform albedo makes that skin a consistent
  tone matching the legs; the 45 % shoulder stay keeps the hole small.
- **Build/gates:** adapter pack, zip sha256
  `bd3622d884f31ddc4cda8f18c9ccaa70799c1af9241f3a4fa72f08b943a6b4a2`, 26 entries (no
  hand texture; no `mtr_hands` referenced). pytest 421 passed / 9 skipped / 1
  pre-existing Miranda failure; kb PASS 246; publish 26 files / 0 failures /
  1 no-README warning.

## 2026-11-04 — BusinessWoman: rebuild fixes stale body textures + culled pose-sim verification

- **Headline — the shipped zip was STALE and still had the leg blotches.** The
  `342a3bb` commit updated `skin_texture.py` to a flat normal + uniform gloss, but
  the `dist/BusinessWoman_LAS.zip` committed alongside it (`303fbc77…`) had been
  packed *before* that texture fix and never rebuilt. Decoding the committed zip
  proves it: body normal per-channel std `[0, 1.72, 0, 1.63]` and diffuse gloss
  std `7.07` (mean 84) — i.e. the exact normal-blob + varied-gloss sources of the
  in-game camo blotches were still in the artifact the user installed. The unit
  test only exercises `build_diffuse`/`build_normal`, so it passed while the zip
  stayed stale. **Rebuilding with `--pack` now ships the fix for real:** body
  normal std `[0,0,0,0]` (flat `[255,128,0,128]`) and gloss std `0.0` (uniform 86).
  New zip sha256 `2952c6e3c6022be92d572e2bcf49bf5d8012c4aba2c764f0b8b4f1693566c07c`.
  Only `bw_body_df/nm.texture` (+ BUILD_INFO hashes) differ from the old zip; the
  model is byte-identical (`da0dfb55…`). Lesson: after a texture-code change,
  re-pack and decode the artifact, don't trust the function-level test alone.
- **Shoulder stay verified with backface culling.** The prior entry's pose
  simulator drew *both* sides of every triangle, so it could not actually show the
  backface-culled hole the game renders. Added **backface culling** to the textured
  renderer (`preview_textured.render(..., cull=True)`) and made `pose_preview.py`
  cull by default (`--no-cull` for the old both-sides view). Culling keeps a
  triangle when `face_normal · view_dir < 0` (front camera at +Y,
  `view_dir=(0,-1,0)`); winding sanity-checked against vertex normals (97.9 %
  agreement). With culling on, the shipped 45 % stay already closes the large
  in-game hole to a **small armpit notch** across 60–75° adduction and
  backward-extension stress poses — the big holes in the screenshots were from the
  *pre-stay* adapter pack.
- **Balance confirmed (do not over-strengthen):** tried 55 % with a plateau
  falloff to close the last notch — it made things **worse**, exposing a large
  skin patch at the armpit (sleeve shoulder stays with the torso while the skin
  arm follows the arm bone, so the sleeve pulls away). Reverted to 45 %. Too
  little stay = see-through hole; too much = skin shows. Recorded in knowledge
  note 31.
- **Static spots are a known limit:** the small shoulder-top / sleeve skin spots
  visible in the bind pose are the genuine overlap gap / poke-through that
  `tuck_underarm_skin` already documents as un-closable without distorting the
  sleeve. Not a regression; left as-is.
- **Regression test:** `tests/test_preview_cull.py` (3 tests) pins the culling
  direction — front face survives, back face dropped only when culling, and the
  sign is view-relative. Guards against an inverted sign culling the whole outfit.
- **Build/gates:** zip 27 entries, byte-reproducible across two `--pack` builds.
  pytest 417 passed / 11 skipped / 1 pre-existing Miranda failure; kb PASS 246;
  publish 27 files / 0 failures / 1 no-README warning.

## 2026-11-03 — BusinessWoman in-game review: graft hands, smooth skin, shoulder stay

- **Report:** user installed the default-glove pack and sent 7 in-game screenshots:
  still **no hands** (open cuff ring), large **holes at the shoulder/armhole**,
  and **camo-like blotches on the legs**. "Fix hands, posture, textures, everything."
- **Hands → graft (default).** The adapter route produced *neither* the glove unit
  *nor* the `hnd_forearms` adapter in-game (menu + blackmarket preview), despite
  passing the LuaJIT behavioural test against the real LAS loader. The in-game
  spawn path evidently differs from the modelled one (hook timing or the preview
  not invoking the glove spawn) and cannot be verified without the game. Switched
  the default to `--hands graft`: PD2 hands are grafted onto the wrists and the
  cuff welded (2.37 / 2.14 cm gaps closed), so the hands are *in the mesh* and
  always render. Gloves are no longer changeable on this route; the adapter route
  remains an option but is unverified in-game. `mtr_hands` + hand texture ship.
- **Leg blotches → smooth skin.** The offline diffuse preview was always smooth;
  the in-game blotches came from the **low-frequency normal-map fbm blobs** plus a
  **mottle/curvature-driven gloss** under the game's specular lighting. Fix:
  `build_normal` now ships a **neutral (flat)** normal map and `build_diffuse` a
  **uniform** gloss (alpha ≈ 87). Skin reads as an even tone in-game. Test updated
  to pin uniform gloss (`std == 0`).
- **Shoulder holes → overlap weight stay.** The blazer armhole is an *overlap*,
  not a sewn seam (471 boundary edges in the shoulder band). Under the arms-down
  idle the Arm-weighted sleeve shoulder rotates away from the torso and the
  overlap opens into a backface-culled hole. Added a jacket-only weight blend in
  `transfer_group`: in the shoulder band, shift up to 45 % of the upper-arm weight
  into the clavicle (smooth height falloff) so the sleeve top stays with the torso.
  Verified with a new offline **pose simulator** (`tools/pd2-las/pose_preview.py`,
  re-skins the body with the arms adducted) — the armpit notch and shoulder-top
  spots reduce and the bind pose is undistorted. This is a smooth weight change,
  not the rejected geometry weld.
- **Build/gates:** zip sha256
  `303fbc77b4ef4e894825a264d0fb11219a9d3c105fefc025209135f271e6b059`, 27 entries
  (adds the hand texture). pytest 414 passed / 11 skipped / 1 pre-existing Miranda
  failure; kb PASS 246; publish 27 files / 0 failures / 1 no-README warning.

## 2026-11-03 — BusinessWoman NO-HANDS bug fixed: restore a real default glove

- **Report:** with the shipped adapter pack installed, the outfit had **no
  hands in-game** (user-confirmed). The forearm adapter alone does not draw
  hands, and stock hands do not render on a replaced body.
- **Root cause (read off the real sources, not assumptions).** LAS 4.1.9's
  loader has a *second* fresh-table read next to the known `glove_adapter`
  one: `output.default_glove_id = output.default_glove_id or false` → every
  LAS outfit gets `default_glove_id = false`. BeardLib's `get_glove_value`
  returns `false` for "Default" gloves when the style's `default_glove_id` is
  `false` → **no glove unit spawns**, while `body_replacement.hands = true`
  hides the stock hands → no hands at all. Vanilla changeable-glove suits
  never hit this: `suit_default_gloves[style] = "heist_default"` (BeardLib's
  `BeardLibInitGloves` copies it to `default_glove_id`), so "Default" always
  resolves to the real `hnd_glv_heistwrinkled` unit.
- **Fix (`bw_pack.render_glove_adapter_lua`).** The compat hook now also sets
  `ps.default_glove_id = "heist_default"` (custom gloves stay selectable), and
  `body_replacement.hands`/`third_body_replacement.hands` stay **true**
  (vanilla `body_replacement_standard`) instead of the previous `false` — the
  spawned gloves supply the hands. Adapter `{}` + exclude-list removal
  unchanged. Geometry untouched: model byte-identical (`5dc4b807…`,
  10 152 550 B); only the hook file changed in the zip.
- **Why the old tests missed it:** they asserted strings, and the old smoke
  test stubbed the host with the wrong assumption ("default gloves returning
  false is fine; adapter + stock hands compensate"). New
  `tests/test_glove_behavior_lua.py` **executes the verbatim LAS 4.1.9 loader**
  (`tests/fixtures/las_loader_4.1.9.lua`, sha256 `21afb703…`) plus the
  generated hooks in **LuaJIT 2.1** (`lupa`, PD2's runtime) against faithful
  ports of BeardLib's `get_glove_value`/`get_glove_variation_value`/
  `BeardLibInitGloves`/visual-state block and the vanilla style lookups:
  8 tests — a no-hook control that must reproduce the no-hands bug, Default
  gloves spawning `hnd_glv_heistwrinkled` in FPS+TPP, custom gloves
  (`bonemittens`) still resolving, parity with a vanilla `hitman` suit, and
  the `pairs(true)` trap. `bootstrap.sh` installs `lupa`.
- **Build/gates:** zip sha256
  `31b2f0a43fc442cd41b91b34c61bfdb1f213beb07423f2055895221353e0e5e2`, 26
  entries (`BUILD_INFO.json` now records `default_glove_id: heist_default`). pytest 416 passed / 9 skipped / 1 pre-existing Miranda failure;
  kb PASS 246; publish 26 files / 0 failures / 1 no-README warning.
  Knowledge note 27 corrected (its "default gloves false is fine" assumption
  was the bug).

## 2026-11-03 — BusinessWoman back-collar medallion painted out

- **What the back artifact was.** The ornament row on the upper back is the
  source Melodic blazer's *intentional* collar decoration: a painted band of
  seven medallions (3 small + 1 large + 3 small), each over a beige tab, in
  `Jacket_diffA` at atlas v≈0.66–0.77 (u≈0.33–0.67). It is **not** a port bug —
  the source NIF has the same 394 collar/yoke verts UV-ing into that band, a 1:1
  port. In the source outfit the white V-lapel hides it from the front; after the
  retarget it lands on the back collar/yoke where nothing covers it, so it reads
  as a stray ornament. The normal map carries a faint matching relief.
- **Fix.** New `skyrim_materials.remove_collar_decoration()` paints the band out
  of the jacket diffuse — a luminance gate (>24) isolates the ornament from the
  dark collar and fills it with the collar's own sampled base colour — and resets
  the gated normal texels to tangent-flat (128,128,255), removing the bump relief
  too. Wired into `build_textures` for `mtr_jacket` only; geometry is untouched.
  The gate leaves the plain dark collar and every texel outside the band window
  (v 0.64–0.82, u 0.26–0.74) alone.
- Verified: band max brightness 177 → 24; back + upper-back renders show a plain
  black collar. 2 new tests in `test_skyrim_materials.py`; full suite
  **407 passed, 9 skipped, 1 failed** (the one failure is the pre-existing Miranda
  retarget tolerance, unrelated). Pack rebuilt, sha256
  `0a32adbefd4922be238f37e0369dfe8cafd26b3b78258446e93f62e52ec6a6e7`; textured
  sheet + icon previews refreshed. KB **246 notes pass**; publish lint **0
  failures**. `runtime_verified` still false — the collar needs the in-game check.

## 2026-11-03 — BusinessWoman neck + bust geometry fixes (NEW)

- Follow-up to the adapter route: two shape loose ends on the ported 3BA body,
  both measured against the source and the PD2 rig, both fixed as continuous
  (tear-free) vertex edits in `build_models.py`, applied to body **and** shadow.
- **Neck.** The capped 3BA neck opening landed at Head-bone height (z≈167) but
  ~4–5 cm *forward* of PD2's Head bone (y=5.3), so it jutted out in front of the
  heister's chin. No head is shipped (LAS keeps the heister's), so the stub above
  the collar was a duplicate neck. New `trim_neck()` folds the skin above the
  collar line (z0=159, k=0.05) down into the collar; the cap now sits at z≈159
  and the heister's own neck shows above. 305 verts folded.
- **Chest.** The retarget stretches the spine *axially* to PD2's longer torso but
  the bust is *radial* and only gets the smaller global similarity scale, so it
  came out ~24% flatter than the source (measured bust/torso **0.485 vs 0.640**).
  New `restore_bust()` scales the front chest's forward protrusion back up
  (factor 1.32, smooth height falloff, front only) to the source proportion —
  now **0.641**. Displacement is proportional to existing forward offset, so the
  bust peaks gain the most.
- **Armpit follow-up.** The first bust pass pushed the *whole* front width and
  pulled the chest panel away from the sleeve, opening a visible underarm gap.
  Added a *lateral* smoothstep falloff (full |x|≤10, zero by |x|=15) so the push
  is confined to the centre bust and leaves the underarm seam (|x|≈12–16) in
  place; bust still measures 0.641, 18 023 verts touched.
- **Underarm sliver — diagnosis + gentle fix.** A *thin* pre-existing underarm
  sliver remains after the bust fix. A jacket-only render shows the blazer fully
  covers the underarm (no hole), and a skin=red render plus a depth-buffer test
  prove the sliver is **skin poking through the jacket surface** along the
  overlap seam, plus a little genuine gap in the overlap — *not* an open
  meet-seam. New `tuck_underarm_skin()` tucks the near-jacket skin inward along
  its own normal (0.7 cm, smooth proximity falloff, |x|≥11, z 137–154), body
  **and** shadow — 1 753 verts — removing the poke-through bulk so the sliver
  drops from a thick band to a thin line. The jacket is never moved.
- **Dead ends — do not retry:** (1) zipping the seam shut in source space
  (`weld_armhole_seam`: pair the torso/sleeve boundary chains, average position +
  weights) made the underarm *worse* — spikes and a wider gap — because the
  blazer armhole is an **overlap** construction (sleeve edge ~3.7 source units
  lateral to the torso edge), not a meet-seam. (2) A stronger tuck (1.2 cm) and
  (3) tucking along the **jacket** normal instead of the skin normal both
  distorted the skin and *increased* the poke-through (depth-test pixel counts
  rose). The gentle 0.7 cm skin-normal tuck is the best gentle outcome; the thin
  residue is the overlap gap, which only the spike-producing weld could close.
  All three reverted; the thin line is left for the in-game check (likely hidden
  at heister distance).
- Order in the build: `restore_bust` → `tuck_underarm_skin` → `lower_collar` →
  `trim_neck` → `cap_holes`. 7 new unit tests in `test_hands_graft.py`; full suite
  **405 passed, 9 skipped, 1 failed** (the one failure is the pre-existing Miranda
  retarget tolerance, unrelated). Pack rebuilt, sha256
  `a4c32e8c54693e9e822028d9472fd9ae54ebea98e8ca936ee57a6c5ebab2be98`; previews
  refreshed. `runtime_verified` still false — the neck/collar fit and the bust
  silhouette need the in-game check.

## 2026-11-03 — glove_adapter implemented for BusinessWoman (adapter route + compat hook) (NEW)

- Scope (confirmed): **BusinessWoman only** — Miranda_LAS and lawson_las keep
  their baked/grafted hands for now.
- **Shipped the adapter route.** `build_business_woman.py` gained
  `--hands {adapter,graft}` (default `adapter`). On `adapter` the build ships
  **no hand geometry at all** (TPP *and* FPS): the graft/weld/cuff-cap pipeline,
  the hand diffuse texture and `mtr_hands` are all gated behind `--hands graft`.
  The sleeves end at the wrist; the vanilla glove + `hnd_forearms` adapter supply
  the hands, exactly like a DLC/Infamy suit.
- **The manifest flag alone is a no-op, so a compat hook does the work.**
  `la.businesswoman` now declares `glove_adapter = true` (intent), and a second
  hook `hooks/businesswoman_glove_adapter.lua` (PostHook
  `BlackMarketTweakData:init`, id `BusinessWoman_GloveAdapter`) runs after LAS's
  loader and actually enables it:
  - `ps.glove_adapter = {}` — a **table, not boolean `true`** (BeardLib's
    `table.merge` calls `pairs(new_table)`; `pairs(true)` crashes). `{}` keeps
    the default `hnd_forearms` adapter.
  - reverse-loop `table.remove` of `las_businesswoman` from
    `glove_adapter.player_style_exclude_list` (LAS force-adds every
    `replace_body` outfit).
  - `ps.body_replacement.hands = false` and
    `ps.third_body_replacement.hands = false` so the stock hands are not
    double-spawned under the gloves.
- **Build:** 26 files; body slots `mtr_body, mtr_heels, mtr_jacket, mtr_jacket2,
  mtr_necklace, mtr_skirt` (no `mtr_hands`); TPP 57,785 verts / 104,329 tris over
  20 PD2 bones; FPS arms 12,682 verts / 23,026 tris. Zip sha256
  `2874b8228f497d9e02d7fe83c1f1c6618669da8e4f929ed017a5ea1185be4b11`.
  `BUILD_INFO.json` records `hands: adapter`, `glove_adapter: true`,
  `runtime_verified: false`.
- **Tests:** new `tests/test_glove_adapter.py` (9) pins the registration
  contract; `test_fps_hands.py` now asserts **no** finger verts and no
  `mtr_hands` in either view on the adapter route; `test_hands_graft.py`
  unchanged (graft machinery retained). Hand suite **56 passed**. Full suite
  **398 passed, 9 skipped, 1 failed** — the one failure
  (`test_retarget_joint_errors_and_palettes`, Miranda route, RightArm 5.71 cm >
  5.0 cm) is **pre-existing and unrelated**: its inputs are byte-identical to
  base and CI skips it (`@needs_templates`, no 2B extraction in CI).
  `check_all.py` (lawson) all 5 stages green; every tracked `dist/*.zip.sha256`
  verifies.
- **Still outstanding (needs the game):** gloves changeable, no double hands,
  FPS hands present via the camera-unit gloves. Fallback if FPS hands are
  missing = FPS-only graft. `runtime_verified` stays `false` until a PC run.

## 2026-11-03 — glove_adapter research (repos read, not guessed) + branch cleanup (NEW)

- Request: `glove_adapter = true`, vanilla hands (or a hand-fix mod) acceptable;
  survey how DLC/Infamy/LAS-cop outfits treat hands. Also: clean stale branches.
- **Branch cleanup:** deleted all 13 stale `arena/*` session branches on origin
  (all merged or superseded: `a72d4579` duplicated merged PR#3; `ecdfa60b`'s nifly
  route was replaced by `skyrim_source.py`). Remote now: `main` + `star-chart` only.
- **Repos read:** `Vladik268/P2` (LAS 4.1.9 + BeardLib), `LebiFur/LASCreator`,
  `references/2b.rar`, and the decompiled vanilla Lua (`AzureeDev/payday-2-luajit`).
- **Vanilla/DLC/Infamy outfits keep gloves changeable.** `glovestweakdata.lua`
  defines `glove_adapter = { unit = units/pd2_dlc_hnd/characters/hnd_forearms/...,
  character_sequence = {female/male per heister}, player_style_exclude_list =
  {"none","slaughterhouse"} }`. `criminalsmanager.lua` hides the stock hands
  (`var_hands_replace`) when gloves are equipped, spawns `char_gloves` (the hand
  mesh) and `char_glove_adapter` (the bare forearm) unless the style is excluded.
  `playerstyletweakdata.lua` uses `body_replacement_standard` (hands/arms=true).
- **LAS cop outfits / 2B / LASCreator / Jack Cooper bake hands in.** cop_outfits.lua
  uses `replace_body=true` (whole body incl. hands); 2B + LASCreator use
  `replace_all=true`; Jack Cooper/Ringed Knight use BeardLib `exclude_glove_adapter`.
  Our 3 packs currently do the same (BusinessWoman grafts PD2 hands + welds cuff).
- **BLOCKER — LAS 4.1.9 loader bug:** `hooks/outfits/loader.lua` does
  `output.glove_adapter = output.glove_adapter or false` and
  `output.default_glove_id = output.default_glove_id or false` — reading the fresh
  `output` table, NOT `data.*`, so both are ALWAYS false. It also inserts any
  `replace_body`/`replace_all` outfit into `glove_adapter.player_style_exclude_list`.
  So `glove_adapter=true` cannot be enabled via the LAS config alone; a compat hook
  must re-enable it (set `player_styles.las_<id>.glove_adapter=true` + drop the
  exclude-list entry) after LAS loads. BeardLib's own path spawns the adapter by
  default unless `glove_adapter=false`, so the hook only fights LAS's forced false.
- **Plan:** drop baked/grafted hands, let vanilla glove + hnd_forearms adapter show
  (the "hands beside the outfit" arrangement note 26 describes; cleaner than the
  graft for BusinessWoman whose 3BA body already stops at the wrist). Unlike note
  26's rejected *donor forearm* (foreign bind pose, 20 cm off), the vanilla adapter
  is bound to the same PD2 skeleton the outfit retargets onto, so it follows.
- Awaiting scope confirmation (which of the 3 LAS packs) before model surgery.
- **Scope confirmed: BusinessWoman.** Also verified a second trap: BeardLib's
  `set_beardlib_character_visual_state` does `table.merge(final_adapter_data,
  gloves_adapter_data or player_style_adapter_data or {})`, and BeardLib's
  `table.merge` calls `pairs(new_table)` — so a boolean `glove_adapter=true` on
  the player_style would raise `pairs(true)`. The compat hook must enable the
  adapter with a table (empty `{}` keeps the default `hnd_forearms`) or nil, NOT
  a boolean. Gloves apply to FPS too: BeardLib moves to `unit:camera():camera_unit()`
  for the local peer and spawns `char_gloves`/`char_glove_adapter` there.

## 2026-10-19 — fourth check: the geometry was broken, and the checks could not see it (NEW)

- Asked for a fourth pass that attacks the *claims* instead of re-running the
  same checker. Five angles: (A) rebuild the pack from a fresh clone, (B)
  look at the geometry itself — winding, tangent frame, normal-map
  convention, (C) settle the normal map's green channel, (D) verify every
  factual claim of the release body, (E) mutation-test the pack-level test
  suite.
- **A: the build is reproducible.** A fresh `git clone` of the branch, a new
  venv (`pillow==13.0.0`, `numpy==2.4.6`) and
  `python tools/pd2-port/build_las_pack.py` produced the **byte-identical**
  pack (8,015,689 B, sha256 `063d5f64…`) in 84 s. Nothing in the build
  depends on the sandbox it was made in. (CI has to pin the same interpreter
  and libraries: a different Python/zlib changes the deflate output, which is
  why `uv run` in CI produced a different zip.)
- **B: the skin was punched full of holes.** A new tool
  (`tools/pd2-port/check_mesh_geometry.py`) decodes the built model and
  compares every triangle's winding with its own vertex normals. The 0.1.1
  pack has **946 of 10,189 body triangles (7.7 % of the body area) and 81
  head triangles wound inside out**, plus 291 in the first-person arms. An
  inside-out triangle is culled by the game: it leaves a **hole** in the
  chest, the shoulders and the arms, and the skin around it shades
  backwards.
  - The source ME2 meshes have **zero** inverted triangles, so the retarget
    introduced them. The cause: the bind-pose transfer fits every bone piece
    independently (one rigid transform per target bone), and the fits are
    not consistent with each other — the hips' fit is 156° away from the
    spine's, the ankles' 133°, the wrists' 122° — so the neighbouring pieces
    are rotated against each other and the triangles between them fold over.
  - Two fixes were prototyped. Making the operators hierarchical (each bone
    relative to its parent) removes every tear, but it also throws the
    shape-matching away: the arms keep the ME2 proportions instead of the
    PD2 rig's, which is wrong for a skin that has to follow PD2's skeleton.
    Using the parent's offset as the bone direction is worse still. A real
    fix is a bind-pose transfer that fits the rigs *consistently* — a bigger
    piece of work than a check should smuggle in.
  - The shipped fix is surgical: `rig_target.repair_winding()` finds every
    triangle that faces away from its own vertex normals and reverses its
    winding. The vertex normals describe the unfolded surface, so the
    winding is what is wrong; the ME2 meshes are corner-split, so flipping a
    triangle cannot make its neighbours inconsistent. **1,027 triangles** are
    repaired this way, and the check now reports 0 inverted triangles.
  - The audit gained a check (`N3`) that fails a pack with inverted
    triangles — it failed on 0.1.1 and passes on 0.1.2 — plus a
    "triangle wound inside out" mutation in the auditor's self-test
    (**16/16** now).
  - A second new tool (`tools/pd2-port/shade_check.py`) renders the
    retargeted mesh with the pack's own normals: before the repair 336 body
    faces (6.1 % of the area) were lit backwards, after it 0.
- **C: the green channel cannot be read out of the files.**
  `tools/pd2-port/check_nm_convention.py` measures the source maps: they are
  genuine tangent-space normal maps (blue saturated at 255, red and green
  centred on 128), but their blue channel is saturated, so the height field
  is not recoverable and an OpenGL (Y+) and a DirectX (Y-) map are equally
  self-consistent with their own image layout. Only the authoring engine
  settles it — and Mass Effect 2 runs on DirectX 9, whose maps are Y-, while
  PD2 wants Y+. So the default build (which inverts the green channel) is the
  right one; `--keep-nm-green` would only be right for a Y+ source.
- **D: the release body was checked line by line.** The size, the sha256, the
  pack version, the check count and the test count were all re-measured
  (they now say 0.1.2, 8,015,688 B, `a24f0b7c…`, 38 checks, 187 tests). The
  claims that survived: "no weld discontinuities above 2.4 cm" (the preview's
  metric says 2.38 cm), "pixel-identical encode/decode round trip on three
  views (7.63e-06 cm)", "arm-only FPS cut of 10,468 vertices", the 2B
  field-by-field diff, and the 15-mutation self-test (now 16).
- **E: the pack-level tests are load-bearing.**
  `tools/pd2-port/check_test_suite_mutations.py` breaks the shipped pack five
  ways (an inside-out triangle, an unregistered FPS unit, an emptied
  localization, the tangent channels deleted) and requires the matching test
  to **fail** — a test that passes or skips is reported as a hole. 5/5 caught.
- The pack is now **0.1.2** (8,015,688 B, sha256 `a24f0b7c…`); the 0.1.1
  release stays up for comparison, but it has holes in it.

## 2026-10-19 — third check: the auditor itself, the 2B oracle, the guide text (NEW)

- Asked for a third pass that attacks the *checker* instead of re-running it.
  Five angles: mutation-test the auditor, re-read the guide, diff the pack
  against the 2B reference pack, and the two assumptions nothing had tested
  yet (degenerate finger segments, 0-based skin palettes).
- **The auditor had two blind spots; a mutation test found them.** New
  `tools/pd2-port/check_guide_compliance_self_test.py` mutates the built pack
  the way the guide forbids (invented render template, contour without
  `unique="true"`, contour without `contour_opacity`, FPS without
  `DEPTH_SCALING`, mip-0-only texture, plain-RGB normal map, missing
  `df_nm` entry, missing `unit_mat` entry, manifest without Hooks, hook flag
  switched off, missing localization key, renamed material, wrong
  `materials` version, texture path with an extension, skinning keyword below
  the geometry's influences) and asserts that the matching check fails.
  Two mutations were **not** caught: P2 only checked that the registered
  files resolve, not that every shipped texture/unit *is* registered (an
  unregistered texture is never loaded by BeardLib), and P3 only looked for
  the flag names, not for their values (`fps_replace_body = false` passed).
  Both fixed; the self-test now detects **15/15** mutations and runs in the
  test suite (`test_the_compliance_checker_actually_fails_on_broken_packs`).
- **Negative controls from git history.** The pre-finger pack (7,967,568 B)
  fails exactly S6 ("no finger bone carries a vertex") and the pre-FPS-fix
  pack (7,943,697 B) fails exactly F3 ("the FPS unit is missing 18 finger
  bones") — the skeleton checks fail on real defects, not just on synthetic
  ones.
- **The guide, re-read from the wiki** (all four chunks): the 54-bone rig
  (1 pelvis + 3 spine + neck/head + shoulders/arms/forearms/hands + 3 bones
  per finger + legs/feet/toebases, forearm twist bones included), 3
  influences, `DEPTH_SCALING` for the FPS unit, `unique="true"` plus
  `contour_color`/`contour_opacity`, texture paths without an extension, no
  invented render templates, tangents on, vertex colours off, DXT5 ARGB 8bpp
  interpolated alpha, X in alpha / red white / blue black / green OpenGL Y+.
  Every rule the auditor enforces is in the source text; the one open
  question (the source's green-channel convention) is exactly the guide's
  "invert the green channel if needed".
- **The 2B reference pack, as an oracle.** The archive is RAR5 and the
  sandbox has no extractor, so `unrar` was built from source
  (`github.com/pmachapman/Unrar`) and the reference extracted. Field by
  field: `main.xml` (table/Localization/Hooks/`armorskinstweakdata`/
  AddFiles), the hook's flag set, the `.unit` (type `dah`, slot 1, the
  `unit_data` + `contour` extensions), the `.object` (`diesel` +
  `graphic_group`), the JSON localization keys and the material configs all
  match ours. Our model carries the same five locator/effect objects
  (`aim`, `BackPack1`, `eyeAim`, `a_weapon_left_front`,
  `a_weapon_right_front`); the auditor now checks them **by name** (S3)
  instead of counting unnamed objects.
- **A false alarm, resolved.** 2B's geometry stores its weights in channel
  id 20 where ours uses 19, which looked like an incompatible vertex layout.
  It is the legacy container's channel-id shift (audit A06: ids above
  TEXCOORD7 move by +2), so after the shift both files use the same
  channels: POSITION0, TEXCOORD0, BLENDINDICES, BLENDWEIGHT0, NORMAL0 and
  the two UV-direction streams. Our layout is right; 2B is a behavioural
  oracle, not a byte template.
- **The two untested assumptions, checked.** The PD2 finger bones are
  1.89-4.03 cm long and the ME2 finger segments 1.75-4.40 cm, so the
  segment fit cannot collapse on a zero-length bone; and every skin palette
  in the pack maps 0-based local indices (the retired route's bug class) with
  contiguous 1..N section ids.
- **Speed.** The auditor decoded the whole mip pyramid of every normal map;
  the layout rule is a property of the encoder, so mip 0 is enough now
  (12.6 s -> 8.3 s per audit, ~2 min for the self-test).
- Result: **36 pass, 1 warn, 0 fail**, and the *pack bytes did not change*
  (8,015,689 B, sha256 `063d5f64...`) - only the auditor and the tests
  grew. Suite: 185 passed, 5 skipped.
- **Still open:** the normal maps' green-channel convention (only the running
  game can settle it), and the forearm twist bones: the reference keeps
  `ForeArmRoll` in its skin palette, ours keeps the bone in the skeleton but
  binds no weight to it - which is what the guide asks of a ported model
  ("merge the twist bones down"). The twist is therefore not animated on the
  forearm.

## 2026-10-19 — guide-compliance audit: mitten hands found, fingers now articulate (NEW)

- Asked to check the pack against the ModWorkshop LAS/MOOG outfit guide.
  Wrote `tools/pd2-port/check_guide_compliance.py`: it re-reads the built zip
  and checks it against the guide's rules (skeleton, weights, materials,
  render templates, FPS unit, texture format, BeardLib packaging), each check
  citing the rule it enforces. 35 checks + 1 open question.
- **One real failure.** The guide's PD2 rig has three bones per finger; the
  rig contract has them, but the retarget folded every ME2 finger joint onto
  the wrist bone — the hands were mittens that could not articulate. Cause:
  `rig_target.map_joint` folded anything matching a finger token to the hand
  (the finger bones were hash-only in the contract, so there were no names to
  map onto).
- **Fix, step 1 — recover the bone names offline.** The contract stores a
  name *hash* per bone (the Model Tool writes names only with the
  PAYDAY-2-Hashlist installed). The hash is the lookup3 variant in
  `dmodel.hash64`, so PD2's naming convention can be hashed and matched
  against the stored hashes: 30 of 187 hash-only bones resolve
  (`LeftHandThumb1..3`, `LeftHandIndex1..3`, `LeftHandMiddle1..3`,
  `LeftHandRing1..3`, `LeftHandPinky1..3` and the Right set). New tool
  `tools/pd2-port/resolve_rig_names.py` does it and patches the contract
  (`name` only — the stored hashes are never touched, and a test now checks
  that every named bone hashes to its stored `name_hash`).
- **Fix, step 2 — map the fingers.** `rig_target` now maps the ME2 finger
  chains one-to-one onto the PD2 finger bones (`LeftIndexFinger` ->
  `RightHandIndex1`, `LeftIndexFinger2` -> `RightHandIndex3`, ...; the side
  swaps with the arms, and ME2's "Pink" is PD2's "Pinky"). The face still
  folds to Head (PD2 has no facial bones).
- **Verified.** All 30 finger bones now carry weight (58-253 vertices each),
  and every finger-dominant vertex sits 0.9-2.6 cm from its bone's origin
  (max 4.5 cm) — the weights are on the fingers, not scattered. The geometry
  gates still pass (max neighbour spike 2.38 cm, twin separation 0.000 cm, no
  degenerate faces) and the encode/decode round trip is still pixel-identical.
- **Second defect, caught by re-checking: the FPS cut dropped the fingers.**
  `rig_target.ARM_BONES` lists the arm and wrist bones only, and the FPS
  (arms-only) unit is cut by dominant bone — so 5,028 finger vertices were
  classified as "body" and left out of the view model: the first-person hands
  would have been cut off at the knuckles. The cut now knows the finger
  chains (`is_arm_bone`), the FPS unit carries all 30 finger bones and is back
  to 10,468 vertices (z 113-149 cm, the shoulder-to-hand band).
  The audit gained a check for it (F3: the FPS unit must carry the same
  finger chains as the third-person one) — it reproduced the defect on the
  pre-fix pack, and a unit test pins the cut.
- Pack rebuilt as **0.1.1**: 8,015,689 bytes, sha256
  `063d5f64ba7878edc88d43901d690dc32a3324ba6e6b319fe93941ed0a556dbb`.
- The compliance audit is now part of the test suite
  (`test_built_pack_passes_the_guide_compliance_check`), so a pack that drifts
  from the guide fails the build. Suite: 184 passed, 5 skipped.
  Compliance: 36 pass, 1 warn, 0 fail.
- **Still open:** the normal maps' green-channel convention (source assumed
  DirectX-style, inverted to PD2's OpenGL-style Y+). The guide's rule can only
  be settled in game; `--keep-nm-green` is the switch.

## 2026-10-19 — pack published: `dist/lawson_las.zip` tracked + GitHub release page (NEW)

- User direction: get `dist/lawson_las.zip` into GitHub and give it a release
  page. Built it with `python tools/pd2-port/build_las_pack.py`: 30 files,
  18,261,456 uncompressed bytes, 7,967,568 bytes, sha256
  `8629051ead84cd7a180a427c9969844363987213885c242eb05f6f34707247f3`.
- `dist/` was gitignored ("built packs are outputs, not sources"). The rule is
  now `dist/*` + `!dist/lawson_las.zip`, so the release asset is tracked and
  the repository always carries the exact bytes the release serves.
- Builder changes: `VERSION` `0.1.0-dev` -> `0.1.0`, new `--version` flag that
  stamps `build_manifest.json`, and a new `status` field ("experimental -
  offline validated, not game-verified") so the shipped artifact states its own
  verification level. `CREDITS.txt` rewritten: it still called the pack a
  "private experimental derivative" with no redistribution permission while the
  pack was about to be published publicly; it now says plainly that the model,
  the textures and the 2B reference pack are not ours to license, that this is
  an unlicensed non-commercial fan derivative, and that the original artists
  and publishers keep all rights to their work.
- The release page body is a file in the repo,
  `releases/lawson-las-v1.md`, with a `<!-- pack_version: 0.1.0 -->` marker
  the CI reads for the version stamp — the page text is versioned and
  reviewable instead of only typed into GitHub.
- New workflow `.github/workflows/lawson-las.yml`: builds the pack, runs the
  tests, uploads a workflow artifact on every push to `main`, and on a
  `lawson-las-v*` tag creates or updates the release and attaches
  `lawson_las.zip` + `lawson_las.zip.sha256`. A step diffs the runner's build
  against the tracked `dist/lawson_las.zip.sha256`, so a release asset can
  never drift from the committed pack.
- Release `lawson-las-v1` published on GitHub with the pack as its asset
  (marked **pre-release**: the pack is not game-verified, and the page says so
  before the install steps rather than in a footnote). The upload itself ran
  in CI, not from this session: the sandbox cannot reach
  `uploads.github.com`/`release-assets.githubusercontent.com`, so the first
  workflow run (missing `pyyaml` in the runner's pip install) and the tag
  move to the fixed commit were needed before the asset landed.
- `dist/lawson_las.zip.sha256` is tracked too, so a download can be checked
  against the repo without downloading the release.
- Tests: 179 passed, 5 skipped — unchanged. (A first local run showed 10
  kb/um failures; they were only a missing `pyyaml` in the local venv, not a
  regression. The same missing dependency broke the first CI run, which is
  why the workflow now installs `pyyaml` as well.) Determinism re-checked:
  rebuilding with the same version reproduces the same sha256, and the CI
  runner's build matches it byte for byte.
- Still **not game-verified**.

## 2026-10-18 — texture/UV verification session; eye iris fix; FPS verified (NEW)

- Added a textured software raster (`preview_check.raster_textured`, DF
  sampling with DirectX texel space, alpha-test 128) and textured sheets +
  face close-ups to `preview_check render`. Upright unmirrored face proves
  the writer's V-negation end-to-end. Three suspected texture bugs audited:
  1. **Teeth/Mouth tiles showing hair art — DISPROVEN.** The source head
     atlas HMF_HED_PROMiranda_Scalp_Diff.png legitimately contains teeth
     (u≈0.002–0.159, v≈0.248–0.543) and mouth-interior (u≈0.921–0.998,
     v≈0.306–0.468) islands; UV-box overlay + per-mesh textured renders
     (dental arch with pink gums, dark interior) show the
     `TEXTURE_SLOTS` mapping is faithful. Gotcha 13.
  2. **Eyelash tile black on contact sheet — DISPROVEN.** real alpha 0–255,
     23% opaque black strands; the sheet just alpha-composites them.
  3. **Eyes with no iris — REAL BUG, FIXED.** ME2's eye shader placed the
     iris; plain diffuse sampling smears it across the eyeball's u-seam
     (blank pink spheres). `build_las_pack.eye_uv_planar` now planar-projects
     each eyeball's UVs from its frontal plane (per-sphere centre + radius):
     round centered irises in the pack pipeline. `EYE_Diff_s.png` is a black
     mask layer, not a diffuse — never map it. Gotcha 12.
- **FPS model visually verified** for the first time: exactly the dominant-arm
  cut (10,468 verts = Body 1 1,792 + Body 2 8,676, z 116–149 shoulder-to-hand
  band), complete sleeves + hands + fingers, open shell at the shoulder as
  expected for a camera view model.
- New test `test_eye_uv_planar_centers_iris`; suite now 179 passed / 5
  skipped. Pack rebuilt (eye UVs change the model bytes):
  7,967,402 bytes, sha256 `9602c38cc04e0168aa87e72628bf2990a3fbbd52dc2189cda0748e40c13990c7`.

## 2026-10-18 — offline geometry verification; rebind rewritten twice

- Built `tools/pd2-port/preview_check.py` (`report` / `render`): quantitative
  gates on the skin transfer (edge preservation, displacement spikes over the
  WELDED vertex graph, corner-split twin separation, dominant-bone anchors,
  bounds vs the 2B donor) plus a numpy/PIL software raster (no Blender here):
  source bind, retarget, decoded-from-pack, pixel diffs, skeleton overlay.
  The donor rig itself renders as a clean A-pose — almost the same pose as the
  ME2 source, so a correct transfer must look like the source figure.
- The naive retarget was a torn mess. Two root causes found and fixed in
  `rig_target.py`:
  1. **Frame conventions.** `minv(W_s) @ W_t` bakes per-bone frame
     orientation deltas into the mesh; consecutive pieces (arm chain) landed
     at mutually wrong angles. Replaced with one **segment-fit** rigid
     transform per target bone (source bone head→tail aligned to the target
     bone, minimal rotation). Folded joints (face→Head, fingers→Hand,
     rolls/twists→parent) share the transform of the most-weighted source
     joint of the fold — per-fold transforms tore the face (edge distortion
     68% median). Calibrated result: weld-aware neighbour spikes 27-28 cm →
     **≤2.4 cm**, face/mouth/eyes/teeth edges 0% distortion.
  2. **Corner-split meshes.** The DAE duplicates vertices per corner (Body 1:
     10,437 verts, 1,789 unique positions). Weight smoothing on index
     adjacency treats each triangle as an island and shreds the surface —
     per-triangle metrics stayed green while it happened (blind). Smoothing
     now welds by position (one weight per unique position, smoothed on the
     welded graph, broadcast back) and the report gates **twin separation**
     (0.000000 cm across all meshes). The verify tool's own first metric
     design was blind to this; recorded as gotcha 11 in the knowledge note.
- Encode/decode verified end-to-end: pixel-diff of retarget vs decoded-from-
  pack renders = 0 mismatched pixels on 3 views; numeric per-axis max |Δ| =
  7.6e-06 cm (f32 quantization). Side-swap verified by world side (ME2 Left
  bones map onto same-side PD2 bones). 2B contract parity re-audited field by
  field (table/hooks/AddFiles/Lua) — clean; the 3 intentional diffs (hooks
  casing, no empty cooked_physics, no unregistered ss.model) unchanged.
- Tests: 3 new (fold transform, welded smoothing, corner-split twin glue) +
  an integration gate on the real source; full suite **178 passed, 5 skipped**.
  Remaining known cosmetic: small waistband wrinkle where shirt hem overlaps
  pants (pose difference at the hips, spikes ≤2 cm; present in source too).
  Offline only; nothing game-verified.

> **2026-10-18: the old-model route is retired.** The character swaps and both
> outfit packs were built from an un-rigged OBJ force-fitted onto Clover's
> skeleton; user runtime results (broken mesh, spawn crashes) made this a dead
> end. Everything derived from that model has been deleted; this journal is kept
> as the record of what was tried and why it failed. The rebuild starts from the
> rigged ME2 COLLADA source on the Legendary Armour Skins contract of `2b.rar`.
> See the [restart audit](../../docs/audits/2026-10-18-old-model-retired-las-restart.md).

## 2026-10-18 — aligned the LAS pack with the ModWorkshop LAS/MOOG guide (NEW)

- Read the Legendary Armour Skins/MOOG/Outfit module guide (Columbus, WIP) and
  distilled it into `knowledge/games/payday-2/las-moog-outfit-porting.md`
  (porting checklist, render-template reference from the live outfits,
  material_config contract, texture/DDS gotchas). The notes-first protocol was
  followed: knowledge first, then code.
- Normal maps: PD2 wants the normal **X channel in alpha**, R flat white, B
  flat black (G = Y, flip only when the source is DirectX-style). Our ME2 PNGs
  are standard RGB normals (B≈254 flat), so the builder now repacks them
  (`dds.pd2_normal_channels`; `--keep-nm-green` opts out of the Y flip).
  Without the repack the game reads bogus X and shading breaks.
- Materials: every material_config now carries `group=` (units reference by
  group; a global default risks clashes and engine fallbacks) and exactly the
  template keywords the shipped outfits use: TPP = `CONTOUR:DIFFUSE_TEXTURE:
  NORMALMAP:SKINNED_3WEIGHTS` (+ `unique="true"` + `contour_color` 1 1 1 /
  `contour_opacity` 0), FPS = `DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:
  SKINNED_3WEIGHTS` with no contour, lashes = the 2B-attested masked combo
  `ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:NORMALMAP:SKINNED_1WEIGHT`
  over a generated flat normal. Never invent keyword combinations — unknown
  combos can render black.
- Kept unchanged because the guide confirms them: locators/culling
  (`c_block`, `BackPack1`, `Aim`, `e_taser`) intact, skin weights ≤3 per
  vertex, texture config paths extensionless, textures `generate_mipmaps=true`,
  DXT5-family formats only.
- Tests: 3 new (channel remap, attested material set, whole-pack normal
  layout) — 174 passed, 5 skipped. Rebuilt `dist/lawson_las.zip`
  (30 files, sha256 `a6b0ad79…`). Offline only; nothing game-verified.

## 2026-10-18 — restart on the LAS route with the rigged ME2 source

- User direction: `2b.rar` is the example of what to make — an additive,
  equipable LAS outfit, not model swaps. Delete the old model and everything
  built from it. Start anew from `PC _ Computer - Mass Effect 2 - Non-Playable
  Characters - Miranda Lawson (Romance).zip`.
- Deleted: `Lawson model/`, `LawsonME2/`, `Bonie/`, `Sydney/`, `clover/`, all
  five `dist/lawson_*.zip`, and the old-source builders
  (`rig_lawson`, `build_model`, `build_character`, `build_package{,2}`,
  `build_outfit{,_beardlib}`, `outfit_model`, `repair_skin_palettes`,
  `package_metadata`, `glb_export`) plus their tests. Kept `dmodel.py`,
  `dds.py`, `glb_render.py` (generic format layer), the knowledge notes, audits
  and this journal. `l4d2_miranda_lawson_1.zip` is a third-party Source-engine
  reference, not old-model lineage; kept pending user word.
- Extracted and re-read `2b.rar` as the contract (its Lua registration, manifest
  and unit/object/material files). Decoded the LAS unit skeleton from
  `2b.model` name hashes: the standard PD2 biped (`root_point`, `Hips → Spine →
  Spine1 → Spine2 → Neck → Head`, shoulder/arm/hand chains with rolls, leg
  chains to toe bases). This is the rig target; it is stored as
  `tools/pd2-port/reference/las_rig.json` (skeleton data only — no 2B art).
- The new source is fully rigged and skinned COLLADA (8 meshes, 8 skin
  controllers, ME2 facial biped). Skin transfer becomes a bind-pose rebind
  against the PD2 rig (`rig_target.py`) instead of the old positional
  heuristics. New pipeline: `me2_dae.py` → `rig_target.py` → `las_model.py` →
  `build_las_pack.py`, output `dist/lawson_las.zip` on the 2B contract with
  `LegendaryArmours.lawson`.
- Offline only. No game, loader, or install changes. Nothing game-verified.

## 2026-10-18 — work on Lawson_LAS; put the BeardLib ZIP in dist

- User explicitly requested `lawson_outfit_BeardLib.zip` in `dist/` and work on
  `Lawson_LAS`, not another investigation of the Clover appearance first.
  Kept the native ZIP there and added a narrow `.gitignore` exception so that
  specific distribution is visible; other generated output remains ignored.
- Chosen route: fix the LAS edition as a real LAS/Wardrobe add-on, independently
  of the native `lawson_beardlib` edition. The original outfit's `PlayerStyle
  id="lawson"` did not implement the supplied 2B integration. Registered
  `LegendaryArmours.lawson` on `lib/tweak_data/armorskinstweakdata` instead,
  with the 2B hide/replace flags. LAS 4.x maps this to `las_lawson` in Outfits.
- Source of truth: safely re-extracted the supplied 2B reference; read LAS 4.1.9
  in Vladik268/P2 at `b7c38c1d358fe054df51201788126c25a0da1938`, particularly
  `hooks/outfits/loader.lua` and GUI/visual hooks, plus BeardLib 5.2.0 at
  `95eb1c0c84e3f07d36f28a5e69197ec3b5c59046` (`HooksModule`, `PackageManager`,
  `AddFilesModule`, `FileManager`). Public-copy versions are not asserted to be
  installed/latest. Sources and extracted 2B assets stay outside Git.
- Confirmed the old TPP model retained **52 drawables**, including collision,
  bag/vest and unused hair chains with undefined sidecar materials, in addition
  to the enabled `s_body` missing `shadow_caster`. Pruned to **7 TPP / 2 FPS**
  drawables and defined every retained material. Missing definitions fail the
  build. This is a reproducible resource defect, not proof of the exact native
  fault instruction in the user's crash logs.
- Shared model preparation moved to `outfit_model.py`: keep the full skeleton,
  preserve TPP geometry/topology/weights, use bounded `g_body` culling instead of
  empty `co_box`, and cut FPS with an immutable one-ring seed (1,998 body + 4,538
  original hand vertices). No source re-rig or UV/hand alignment repair attempted.
  Broader audited parser/normalizer defects are not claimed fixed by the move.
- Kept `unit_mat auto_cp="true"`: actual BeardLib code supplies its built-in
  default cooked_physics. No invented empty physics payload or eager physics
  load. Case-consistent hook paths, standard JSON, LAS + native fallback icon
  paths, credits and deterministic/atomic builds with input overwrite guards.
- Rebuilt **`dist/lawson_outfit.zip`**, root `Lawson_LAS/`, **1.1.0-rc1**, 35 files,
  6,092,512 bytes. SHA-256:
  `f729868d51bb8a7547a4cfddbd3e8184e12c8c72112c11536fdf1c5f6fca7230`.
  Preserved the original archive privately outside the checkout before replacing
  it (original SHA-256 `5f58d8f86d3bdc49ada4efcb6f7e32d6121207c1bd8b94b2e55c3114e090cefe`).
- Verified a fresh native BeardLib build after helper extraction is byte-identical
  to the requested dist ZIP: 6,155,761 bytes, SHA-256
  `591f6d7b9c6ef9a8c6a8b6f2c0183519e2d1a728711e0ed8a75fc555cfe7283f`.
  Clover/Bonnie/Sydney archives and `2b.rar` are unchanged. New archives are kept
  as private downloads too; no game-derived asset commit or publication performed.
- **87 related tests passed**. Full suite with FFmpeg/ffprobe on PATH and Lua 5.1
  available via optional lupa: **240 passed, 1 skipped** (MSYS-only), one existing
  Pillow deprecation warning, 55.37 seconds. ZIP CRC/payload hash/current-build
  checks pass. KB/index: 247 notes pass (one pre-existing Diesel engine warning).
  Repository publish lint: 764 files, 0 failures, 8 existing warnings; unpacked
  LAS payload lint: 35 files, 0 failures, 0 warnings. ZIP lint is not redistribution
  clearance. Documented the repair and baseline-audit historical scope.
- Extra manual Lua 5.1 smoke executed actual pinned BeardLib HooksModule,
  LoadConfigUnitShortcutNode and LAS 4.1.9 loader against the generated pack.
  Verified post-hook path/source/case, 10 implicit unit resources including
  external default physics, LAS units/default-glove flags, mask/body maps equal
  to the supplied 2B registration, icons and native-ID coexistence. Engine/file
  boundaries and host objects were stubbed: NOT a PAYDAY 2 spawn/render test.
- No game runtime, installation, save/profile/loader edits, OS input, online test,
  commit, push, PR or publication. The original failure is authoritative; crash
  resolution and visuals remain unverified. The candidate inherits the known
  bad Clover rig and is not described as a complete fix.
- Next oracle: back up, select vanilla if possible, move the old Lawson_LAS
  completely outside mod_overrides (do not merely rename it there), extract the
  candidate, restart completely, and try only the [LAS] Miranda Lawson menu
  preview with Default gloves and other appearance packs disabled. If it
  crashes, stop and obtain fresh crash/loader logs and exact dependency versions.
  Proceed to an offline heist only after the preview works; do not repeat the
  same failing legacy test. The bundled README gives upgrade/rollback details.

## 2026-10-18 — user runtime feedback: broken Clover mesh, legacy outfit spawn crash

- User reports `lawson_clover` no longer crashes but the displayed model is a
  "complete mess"; `Lawson_LAS` crashes. This is evidence of failure, not a
  successful in-game verification. No screenshot is available yet to separate
  geometry deformation, texture corruption and animation/rigging problems.
- Read the supplied crash.txt and crashlog.txt without copying the raw logs into
  Git. Game build: 1.0.0-159028. The latest crash.txt and three recent crashlog
  entries fail on the Main thread in `ManageSpawnedUnits:spawn_unit`, through
  `spawn_and_link_unit`, `CriminalsManager:set_character_visual_state` and the
  menu's character-visual update. Eleven older records instead fail during
  `MenuSetup:load_packages`; one additional record has no script stack.
- The new failure is at outfit-unit spawn/link time, not evidence that the
  earlier package-loading diagnosis still applies. No offending resource path
  or native fault instruction is identified. Repeated AK::WriteBytesCount and
  the presence of WSOCK32 are not proof of an audio or SuperBLT defect. Missing
  shadow material / culling / model resources remain suspects, not proven causes.
- Confirmed a source-rigging discrepancy worth fixing during a real source
  rebuild: `rig_lawson.py` labels positive-X arm vertices Left, but Clover's
  world-space LeftArm/LeftHand have negative X (-20.86/-45.98 cm); Right is
  positive X. The shipped Lawson `g_hands` already spans approximately
  -89.27..89.25 cm in bind geometry, versus -52.65..52.65 cm in the vanilla
  reference. This supports investigating the source arm alignment in addition
  to the previously identified UV seam export defect. It does not prove a sole
  cause of the user's observed model without seeing it in-game.
- Checked the tempting base-vertex hypothesis and did NOT change topology:
  tracked vanilla multi-atom meshes also use absolute topology references with
  nonzero BaseVertex. Blindly subtracting BaseVertex would be speculative.
- `lawson_outfit_BeardLib.zip` was absent: only the builder is tracked, and its
  `dist/` output is ignored/excluded from snapshots. Regenerated the unchanged
  builder's output, copied it into local dist/, and supplied an actual private
  download outside the checkout (`mod-deliverables/lawson_outfit_BeardLib.zip`).
  SHA-256 remains `591f6d7b9c6ef9a8c6a8b6f2c0183519e2d1a728711e0ed8a75fc555cfe7283f`,
  6,155,761 bytes, 36 files. Verified ZIP CRC and all BUILD_INFO payload hashes.
- The BeardLib pack inherits the same Clover-rigged geometry and is NOT a mesh
  repair. Do not describe this regeneration as fixing the user's model or crash.
  Dedicated PD2/package tests: 64 passed. No production code or existing tracked
  archives changed; no game, installation, save or loader modifications performed.
- Next: keep the legacy crashing outfit disabled; request a screenshot of the
  broken Clover model (and outfit/character selection). Rebuild rig/UV data from
  the source only after distinguishing the visual failure. Do not ask the user
  to keep repeating the same failing legacy outfit test.

## 2026-10-18 — separate BeardLib-native outfit variant (built; not game-verified)

- Request: add `lawson_outfit_BeardLib` alongside the existing outfit/character
  packs. Keep the existing four ZIPs and `2b.rar` unchanged.
- Route: a standalone BeardLib `PlayerStyle`, requiring SuperBLT + BeardLib only,
  with its own `lawson_beardlib` item ID and asset/icon namespace. Do not register
  `LegendaryArmours`, depend on LAS/Wardrobe Mod, or override vanilla heister paths.
- Source of truth: BeardLib 5.2.0 at
  `95eb1c0c84e3f07d36f28a5e69197ec3b5c59046` (`PlayerStyleModule`,
  `GlobalValueModule`, `PlayerStyleGloveHooks`) and the game's player-style value
  fallback / body-replacement behavior. The native replacement map supports head,
  body, hands, arms, vest and armor; it does not automatically hide the separate
  mask, so do not promise LAS-style mask hiding.
- Reuse the supplied repaired Clover->Lawson mesh, not a fresh speculative rig.
  Prune unused vanilla drawables/material groups, include the shadow material,
  make FPS selection triangle-order independent, and validate actual render-atom
  references and material coverage. Keep the original builder's output intact.
- Package generated game/model assets only as an ignored local/private download;
  no publication or new game-asset commit. Add the reproducible builder, tests,
  install instructions and provenance/verification limits to source control.
- Implemented `build_outfit_beardlib.py`, separate from the unchanged legacy
  builder. Output: `dist/lawson_outfit_BeardLib.zip`, root
  `Lawson_Outfit_BeardLib/`, 36 files, 6,155,761 bytes. SHA-256:
  `591f6d7b9c6ef9a8c6a8b6f2c0183519e2d1a728711e0ed8a75fc555cfe7283f`.
  The ignored ZIP is also provided as a private download outside `dist/` so it
  survives workspace snapshots; no new game/model assets are added to Git.
- Retained TPP geometry/topology and the complete source skeleton; removed
  unused drawable chains and material groups. FPS body: 1,825 arm-bound seed
  vertices + an immutable one-ring expansion = 1,998 vertices, plus the 4,538
  original hand vertices. Reversed/shuffled face orders produce the same cut.
  This is not a watertightness or animation guarantee.
- Used native `.unit` / `dynamic_object` schemas, real `g_body` culling geometry
  with conservative bounds, complete used-material coverage (including
  `shadow_caster`), and FPS `DEPTH_SCALING` templates. All 19 source texture
  payloads remain unchanged; added two alpha-derived grayscale opacity maps
  and one small flat normal, with full DXT5 mip chains. The source's existing
  alpha-masked Clover-hair shader permutation is used for lashes; shader
  appearance still needs an engine test.
- Added deterministic ordering/timestamps, atomic output, original-input/archive
  overwrite protection, standard JSON localization and `BUILD_INFO.json` hashes.
  The 34 dedicated tests passed; full repository suite with FFmpeg/ffprobe on
  PATH: **217 passed, 1 skipped** (MSYS-only), one existing Pillow deprecation
  warning, in 112.38 seconds. Existing outfit-payload parity tests also passed.
- Manual API contract smoke in Lua 5.1: executed the pinned BeardLib XML boolean
  conversion, `PlayerStyleModule` registration, actual game global fallback,
  BeardLib default-glove getters and actual SuperBLT json10 decoding against
  the generated config. FPS/TPP paths resolved for five names; default gloves
  returned false; non-default gloves remained selectable; the legacy `lawson`
  registration stayed intact. Host objects and character-name conversion were
  stubbed: this is **not a PAYDAY 2 rendering/animation test**. New localization loads in json10;
  the old comma-less localization is not being labeled a runtime blocker.
- KB: 246 notes pass with the original Diesel catalog warning. Publish lint:
  **761 files, 0 failures, 8 existing warnings**. This lint does not inspect ZIP
  payloads or clear redistribution rights; package contents were checked
  separately by the dedicated tests. Added an in-progress native-outfit field
  note and install/equip/rollback instructions, and corrected the old guide's
  LAS-versus-PlayerStyle branding without modifying its archive or builder.
- SHA-256 rechecks preserve all four original ZIPs and `2b.rar` exactly as
  recorded in the audit. Source Clover SHA-256:
  `95f3d4ab3718c71a84c8ed4695e130712e3b5c132b6b68e377530f40460b271f`.
- No PAYDAY 2 installation is available: in-game visual/animation/mask behavior,
  per-heister proportions, VR, other appearance mods and online sync remain
  unverified. Native masks stay separate; use Default gloves for Lawson hands.
  No loader installation, input automation, game-folder/save edits, commits,
  pushes, PRs or publication were performed. Next: user-controlled offline test,
  with logs/screenshots if loading, clipping or animation fails.

## 2026-10-18 — LAS wearable outfit pack (dist/lawson_outfit.zip)

- Request: build a Legendary Armour Skins ("Wardrobe Mod") outfit pack like
  "Yorha No. 2 Type B (2B) [LAS]" (ModWorkShop #30041) for Lawson, added to
  dist/. Depending on SuperBLT/BeardLib/LAS is accepted by the requester.
- Format ground truth (binary 2b.rar listing is unextractable over the
  allowed hosts): THOT-PATROLL/payday-2-outfit-helper `make_file()` templates
  and, decisively, the working "Jack Cooper - Legendary Armour Skin" pack in
  Vladik268/P2 (main.xml / units / objects / material_configs / icon header /
  jack_fps.model skeleton). LAS FPS rigs use the standard heister bone names
  (Hips..fingers + a_weapon_left_front/right_front + aim), a full skeleton in
  the FPS model, and an empty `co_box` locator object3D for culling.
- Session state recovery: a snapshot rollback had lost the earlier in-place
  repair of dist/lawson_*.zip (working tree back at the broken originals:
  non-contiguous section IDs, g_body 73,3xx indices, mip-0-only DDS). Re-ran
  `repair_skin_palettes.py` on all three packs (4m11s, deterministic;
  `--check` OK x3), so the dist character packs are repaired again and the
  outfit pack is built from repaired sources.
- New `tools/pd2-port/build_outfit.py`: builds `dist/lawson_outfit.zip`
  (`Lawson_LAS/`, no spaces) = Jack Cooper layout. TPP model = repaired
  model verbatim + co_box; FPS model = same skeleton minus head/hair/vests/
  bags/collision, with g_body cut to arm-chain verts (face-closed watertight
  shell) + full g_hands (the long-glove arms cover armpit->fingertips, so
  "fingers to shoulders" is complete). Sidecars adapt the proven mtr_fem1
  material names (lawson_outfit/swim/under/hair/lashes/eyes/limbs/body/face/
  scalp) to pack-local textures; FPS materials use DEPTH_SCALING templates
  with contour vars stripped. Icon: Miranda face, 128x128 DXT5, flags
  0x00081007, no mips (jack.texture header ground truth).
- Divergences from outfit_helper.py (tool bugs) corrected: `</materials>`
  closing tag, extension-less AddFiles paths, icon path uses the skin id,
  correct FPS texture paths, separate TPP/FPS object lists.
- Tests: new tests/test_outfit_pack.py (13 tests: layout, model validity,
  co_box/root_point, arms-only FPS + skeleton retention, object/material
  name resolution against model hashes, DEPTH_SCALING FPS materials, main.xml
  reference resolution, localization keys, icon header, repaired textures,
  shipped-zip parity with a fresh build). Full suite 179 passed, 5 skipped.
- Limits: not verified in-game. Unknowns the oracle must cover: LAS framework
  acceptance of the name-based body_replacement mapping, FPS arms visibility/
  deformation, whether `co_box` as an empty locator culls acceptably in this
  engine build (Jack ships the same), and co-op safety. Test offline first.

## 2026-10-18 — mod manager lists packs, models remain vanilla

- Report: all three characters retain their faces/suits; packs enabled; BLT present;
  PocoHUD works. Exact loader/game versions and installation paths unknown.
- Searched local knowledge base for PAYDAY 2: no matching prior note.
- Inspected all tracked dist ZIPs: each contains 2 models, 2 material configs,
  19 textures and a README; no main.xml. README wrongly says to install under
  mods/mod_overrides and that BeardLib is optional. It also claims in-game success
  without available evidence.
- Compared material paths with the existing local character object references;
  the packaged material directories agree with those references.
- Chosen route: fix asset-override packaging, not Lua gameplay hooks or geometry.
  Source of truth: BeardLib 5.2.0 source at
  95eb1c0c84e3f07d36f28a5e69197ec3b5c59046 (see README links).
- Added shared metadata generation to build_package2.py and a standard-library
  metadata-only ZIP repair command. All packs now carry main.xml texture entries,
  correct assets/mod_overrides instructions, explicit SuperBLT/BeardLib requirements,
  conflict/restart diagnostics and honest verification limits.
- Repaired the existing tracked archives. Compared every original asset with
  git show HEAD:dist/<archive>: all 23 asset payloads per pack are byte-identical.
- Tests: 10 packaging tests pass; full suite 159 passed, 5 skipped. Knowledge-base
  validation passes. No game launched, loaders installed, user files changed,
  commits pushed, or PRs opened.
- Next oracle: user installs one corrected pack, restarts, selects matching
  character/default outfit and supplies a menu screenshot. Back up saves before
  offline heist testing. If unchanged, request full install path and loader logs.
  Model deformation, texture orientation, facial animation and multiplayer remain
  unverified; packaging validation alone cannot establish that they work.

## 2026-10-18 — startup crash after moving packs to assets/mod_overrides

- Report: once installed under `PAYDAY 2\assets\mod_overrides\`, PAYDAY 2 crashes
  at startup / character preview when loading the Lawson `.model` overrides.
- Inspected all 6 `.model` files inside `dist/lawson_*.zip` alongside the vanilla
  reference models (`clover/`, `Bonie/`, `Sydney/`) and upstream
  `diesel-modding/payday2-model-tool` (`SkinBones.cs`, `Bones.cs`, `GltfImporter.cs`).
- Root cause: `build_character.py` and `build_model.py` populated
  `SkinBones.bone_mappings` with skeleton `Object3D` section IDs (`pal_ids`) instead
  of 0-based local indices (`0 .. len(pal_ids) - 1`) into `SkinBones.object_ids`:
  - `dist/lawson_bonnie.zip`: 4 rebuilt `SkinBones` sections (`230, 236, 242, 248`)
    per `.model` had max index `98` vs bone counts `24, 6, 5, 32`.
  - `dist/lawson_clover.zip`: 6 rebuilt `SkinBones` sections (`418, 424, 430, 436, 442, 448`)
    per `.model` had max index `152` vs bone counts `28, 5, 32, 5, 5, 6`.
  - `dist/lawson_sydney.zip`: 5 rebuilt `SkinBones` sections (`239, 245, 251, 257, 263`)
    per `.model` had max index `99` vs bone counts `26, 5, 32, 6, 6`.
- Fixed `build_character.py` and `build_model.py` to write `0 .. len(pal_ids) - 1`
  into each `SkinBones` mapping set.
- Added `tools/pd2-port/repair_skin_palettes.py` and repaired all 6 `.model` files
  across `dist/lawson_bonnie.zip`, `dist/lawson_clover.zip`, and
  `dist/lawson_sydney.zip` in place, updating `README.txt` and `main.xml` to
  packaging revision 1.2 while preserving all geometry, weights, inverse bind
  matrices, material configs, and `.texture` files.
- Expanded `tests/test_pd2_packages.py` to validate `SkinBones` palette ranges and
  vertex blend indices across all shipped `.model` files and test in-place repair.
- Next oracle: user extracts the updated `dist/lawson_*.zip` into
  `PAYDAY 2\assets\mod_overrides\`, launches PAYDAY 2, and verifies whether the
  character preview loads without crashing and deforms properly.

## 2026-10-18 — still crashing at MenuSetup:load_packages() after the SkinBones fix

- Report: `crash.txt` / `crashlog.txt` show 11 identical access violations on the
  Main thread at `load_packages() lib/setups/menusetup.lua:72` (coresetup.lua:322),
  PAYDAY 2 1.0.0-159028, i.e. while loading the menu packages that contain the
  overridden character models/textures — before any mesh is displayed.
- Binary-diffed the 6 shipped `.model` files and 19 `.texture` files against the
  vanilla `clover/`, `Bonie/`, `Sydney/` assets. Three more structural defects
  (revision 1.3 fixes all of them):
  1. DODB section table: vanilla models always have contiguous IDs `1 .. count`
     and a canonical order (animation/author -> [material_group + its materials]
     -> object3D/model_data -> mesh groups `[skinbones,] geometry, topology,
     passthroughGP, topologyIP` in model order, unskinned first). The generated
     models dropped whole mesh groups (22-33 IDs) while allocating new IDs past
     `max_id`, so `max_id > count` (450>417 Clover, 250>228 Bonnie, 265>237
     Sydney), spliced new groups into the model block and appended materials at
     the end. An engine section table indexed by ID reads out of bounds on any
     lookup of a dropped/gapped ID — the likely load-time crash mechanism.
  2. g_body's Topology held 73,371 / 73,239 / 73,323 indices (vanilla character
     meshes max at 15,609-18,360): the redundant overlapping `lawson_swim` and
     `lawson_under` layers were stacked into one mesh. Dropped those two hidden
     layers -> 63,975 / 63,843 / 63,927 indices.
  3. All 19 `.texture` files were mip-0-only (`dwMipMapCount = 0`, flags
     `0x00081007`, caps `0x1000`) vs vanilla full DXT5 pyramids (11/10/9 mips,
     flags `0x000A1007`, caps `0x00401008`); 10,067 blocks per pack also had
     colour endpoints written `c0 < c1` (decoder 3-colour mode + transparent
     index = visible holes).
- Fix: `normalize_model_container` in `repair_skin_palettes.py` (canonical order,
  contiguous renumbering with full reference remap, over-limit atom trimming,
  strict validation), `dds.py` (vanilla-shaped pyramid writer/repairer; the
  endpoint fix swaps `c0<->c1` and remaps indices `0<->1, 2<->3` — bit-exact
  for the intended colours, verified against the pristine textures). Repaired
  all 6 models and 19 textures x 3 packs in place; `main.xml`/`README.txt` bumped
  to packaging revision 1.3. `build_character.py` / `build_model.py` now normalize
  their output and `build_package2.py` writes full pyramids (the proposed
  header snippet that kept `dwMipMapCount = 0` and flags `0x00081007` would
  have left the header lying about the pyramid).
- Verified `normalize_model_container` is a byte-identical no-op on all 6 vanilla
  reference models and idempotent on the repaired ones. Tests: 17 packaging tests
  (strict layout, trim, pyramid, endpoint-order, idempotence), full suite 166
  passed, 5 skipped. No game launched; in-game rendering remains unverified.
- Next oracle: user installs one repaired pack and reports whether the menu loads
  and the character renders. If it still crashes, collect the new crash.txt and
  the exact install path; remaining unknowns are model deformation, animation
  binding and texture orientation.
