---
kind: game
title: Character override packs listed but not loaded or crashing on SkinBones palettes
game: PAYDAY 2
games_also: []
game_version: "User build unknown; original package claimed Update 247, unverified"
platform: windows
engine: diesel
route: asset-only
tools: [Python, SuperBLT, BeardLib]
anti_cheat: "Not assessed on user's installation; offline testing only"
status: in-progress
agents: [Arena.ai agent]
humans: []
date: '2026-10-18'
links:
- https://github.com/simon-wh/PAYDAY-2-BeardLib/tree/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046
- https://github.com/diesel-modding/payday2-model-tool
tags: [payday-2, diesel, mod-overrides, beardlib, packaging, textures, skinbones, model]
---
# Character override packs listed but not loaded or crashing on SkinBones palettes

The user first reported unchanged faces and suits despite enabling the Lawson packs,
while PocoHUD worked. Inspection found an incorrect installation path in all three
ZIP READMEs (`mods/mod_overrides` instead of `assets/mod_overrides`) and missing
BeardLib `AddFiles` registration metadata for new textures.

Once installed under `assets/mod_overrides` so PAYDAY 2 actually loaded the `.model`
overrides, the game crashed at startup / character display. Binary inspection of the
shipped `.model` files against vanilla models and `diesel-modding/payday2-model-tool`
revealed that every rebuilt `SkinBones` (`0x65CC1825`) section had `bone_mappings`
populated with skeleton `Object3D` section IDs instead of 0-based local indices
(`0 .. count - 1`) into `SkinBones.object_ids`. Both the builder scripts and the
tracked `dist/lawson_*.zip` archives were repaired, though an in-game retest is
still required to confirm visual appearance and animation.

## Setup

- Three existing archives: Lawson replacements for Bonnie, Clover and Sydney.
- The user's exact game and BLT versions were not provided.
- Loader behavior checked against BeardLib source commit
  `95eb1c0c84e3f07d36f28a5e69197ec3b5c59046` (`main.xml` reports 5.2.0).
- Diesel `.model` `SkinBones` (`0x65CC1825`) layout verified against vanilla
  `.model` files and `diesel-modding/payday2-model-tool` (`SkinBones.cs`,
  `Bones.cs`, `GltfImporter.cs`).
- Python 3.11 on Linux used for binary inspection, in-place repair, and regression
  tests, not gameplay.

## Route and why

Keep the existing asset-override route. Use native overrides for existing model
and material paths; include a BeardLib `main.xml` manifest for the 19 new texture
database entries; and repair the `SkinBones.bone_mappings` palettes in place inside
the 6 `.model` files so skinning indices stay within `0 .. SkinBones.count - 1`.

## How the game works (what we had to learn)

- BeardLib's `main.xml` sets `mod_override_dir` to `assets/mod_overrides/`.
- `Classes/Frameworks.lua` discovers `main.xml` under each override folder.
- `Modules/Utils/AddFilesModule.lua` resolves `directory` relative to the mod root
  and delegates to `BeardLibPackageManager:LoadConfig`.
- `Classes/Managers/PackageManager.lua` takes extensionless `path` values and the
  resource type from each element name. `force=false` avoids replacing an existing
  entry. All three packs have byte-identical shared textures.
- In Diesel `.model` containers (`DODB` v1), a `SkinBones` (`0x65CC1825`) section
  starts with a `Bones` table containing `1 + len(render_atoms)` `uint32` mapping
  lists, followed by `root_bone_id`, `count`, `object_ids[count]`,
  `rotations[count]` (inverse bind matrices), and `global_skin_transform`.
- Each vertex's `BLENDINDICES` (`channel 17`, 4 `uint16` slots) indexes into its
  render atom's `bone_mappings[atom_idx]` list, and the value stored at
  `bone_mappings[atom_idx][blend_idx]` is a **0-based local index** (`0 .. count - 1`)
  into `SkinBones.object_ids` and `SkinBones.rotations`, **not** an `Object3D`
  section ID. Writing `Object3D` section IDs (up to 98, 152, and 99) into
  `bone_mappings` when `count` is 5..32 causes the native skinning shader upload to
  read out-of-bounds memory and crash immediately with an access violation.

## Build steps

1. Run `python tools/pd2-port/repair_skin_palettes.py dist/lawson_bonnie.zip dist/lawson_clover.zip dist/lawson_sydney.zip`.
   It rewrites out-of-range `SkinBones.bone_mappings` entries in place to
   `0 .. count - 1` across both `.model` files in each archive and refreshes
   `main.xml` and `README.txt` to revision 1.2 while preserving all geometry,
   weights, matrices, material configs, and textures.
2. Verify with `python tools/pd2-port/repair_skin_palettes.py --check dist/lawson_*.zip`.
3. Future model builds through `build_character.py` and `build_model.py` emit local
   `0 .. len(pal_ids) - 1` palette indices directly.
4. Install SuperBLT and BeardLib using their instructions. With the game closed,
   back up old pack folders outside the game and extract one pack into
   `PAYDAY 2/assets/mod_overrides/`, so `lawson_clover/main.xml` and
   `lawson_clover/units/` are siblings (substitute the chosen character).
5. Temporarily remove conflicting replacements, restart, select the matching
   character and default outfit, and inspect the unmasked menu preview.
6. Back up saves before any offline heist test. Do not infer co-op compatibility.

## Verification

`tests/test_pd2_packages.py` checks all archives for valid ZIPs, matching roots,
19 registered textures per pack, material-reference coverage, identical shared
textures, valid `SkinBones` local palette ranges (`0 .. count - 1`) and vertex
blend-index bounds across all 6 shipped `.model` files, and idempotent repair
behavior. No game process, screenshot, or live animation check was available in
this environment, so `status` remains `in-progress`.

## Gotchas

1. **Mods enabled but characters unchanged.** The original instructions pointed to
   `mods/mod_overrides`, not `assets/mod_overrides`. Correct the install root first;
   a mod-manager listing is not evidence of engine resource loading.
2. **New texture paths without registration.** These are not existing game textures
   to override. Include a `main.xml` with explicit `AddFiles/texture` entries and
   require BeardLib; do not describe it as optional.
3. **`SkinBones.bone_mappings` stores local indices, not section IDs.** In
   `diesel-modding/payday2-model-tool` (`GltfImporter.cs`), `bone_mapping` is filled
   with `0 .. skinBones.Objects.Count - 1` as bones are added to `skinBones.Objects`.
   Storing `Object3D` section IDs in `bone_mappings` passes basic container-size
   checks because both are `uint32` arrays of length `count`, but crashes the engine
   as soon as the skinned mesh is rendered.
4. **Packaging and binary range tests are not visual gameplay validation.** Valid
   palettes prevent the out-of-bounds skinning crash, but do not prove visual
   rigging quality, facial animation, masks, or multiplayer stability. Keep status
   `in-progress` until confirmed in-game.

## Assets

No new art or extracted game files were added. Existing archive `.model` files had
only their `SkinBones.bone_mappings` tables patched in place (`0 .. count - 1`), and
package metadata was updated to revision 1.2. Redistribution rights must be checked
before publishing third-party assets.

## Open questions

After extracting the revision 1.2 ZIPs into `PAYDAY 2/assets/mod_overrides/`, do the
menu preview and offline heist character models load and animate without crashing?
If another crash or visual issue occurs, check `%LOCALAPPDATA%\PAYDAY 2\crash.txt`
and the latest SuperBLT log under `PAYDAY 2\mods\logs\`.
