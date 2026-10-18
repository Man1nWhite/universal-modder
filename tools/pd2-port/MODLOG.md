# Lawson pack repair journal

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
