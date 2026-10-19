# Lawson pack journal

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
- Pack rebuilt as **0.1.1**: 7,943,697 bytes, sha256
  `2cb1ed018b51b256ec42bec32a1a8a5c2105ff13b85f02e2d7ffefa96d680076`.
- The compliance audit is now part of the test suite
  (`test_built_pack_passes_the_guide_compliance_check`), so a pack that drifts
  from the guide fails the build. Suite: 183 passed, 5 skipped.
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
