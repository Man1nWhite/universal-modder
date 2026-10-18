---
kind: game
title: Character override packs listed but not loaded
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
tags: [payday-2, diesel, mod-overrides, beardlib, packaging, textures]
---
# Character override packs listed but not loaded

The user reported unchanged faces and suits despite enabling the Lawson packs,
while PocoHUD worked. Inspection found an incorrect installation path in all three
ZIP READMEs and missing registration metadata for new textures. Packaging was
repaired, but an in-game retest is still required; this is not a verified model port.

## Setup

- Three existing archives: Lawson replacements for Bonnie, Clover and Sydney.
- The user's exact game and BLT versions were not provided.
- Loader behavior checked against BeardLib source commit
  `95eb1c0c84e3f07d36f28a5e69197ec3b5c59046` (`main.xml` reports 5.2.0).
- Python 3.11 on Linux used for archive inspection and regression tests, not gameplay.

## Route and why

Keep the existing asset-override route. Use native overrides for existing model
and material paths; add a BeardLib manifest for the new texture database entries.
No Lua gameplay hooks or changes to the user's game installation were needed here.

## How the game works (what we had to learn)

- BeardLib's `main.xml` sets `mod_override_dir` to `assets/mod_overrides/`.
- `Classes/Frameworks.lua` discovers `main.xml` under each override folder.
- `Modules/Utils/AddFilesModule.lua` resolves `directory` relative to the mod root
  and delegates to `BeardLibPackageManager:LoadConfig`.
- `Classes/Managers/PackageManager.lua` takes extensionless `path` values and the
  resource type from each element name. `force=false` avoids replacing an existing
  entry. All three packs have byte-identical shared textures.
- PocoHUD exercising Lua hooks does not verify asset override discovery.

## Build steps

1. Run `python tools/pd2-port/package_metadata.py dist/lawson_bonnie.zip dist/lawson_clover.zip dist/lawson_sydney.zip`.
   It changes only README and manifest metadata, preserving every asset's bytes.
2. Future staging through `build_package2.py` writes the same metadata automatically.
3. Install SuperBLT and BeardLib using their instructions. With the game closed,
   back up old pack folders outside the game and extract one pack into
   `PAYDAY 2/assets/mod_overrides/`, so `lawson_clover/main.xml` and
   `lawson_clover/units/` are siblings (substitute the chosen character).
4. Temporarily remove conflicting replacements, restart, select the matching
   character and default outfit, and inspect the unmasked menu preview.
5. Back up saves before any offline heist test. Do not infer co-op compatibility.

## Verification

`tests/test_pd2_packages.py` checks all archives for valid ZIPs, matching roots,
19 registered textures per pack, material-reference coverage, identical shared
textures, consistent generated docs, and metadata-only/idempotent repair behavior.
Compare asset hashes against the original Git archives to confirm no assets changed.
No game process, log, screenshot, animation or mesh appearance was available here.
The earlier README's unsupported success claims were removed.

## Gotchas

1. **Mods enabled but characters unchanged.** The original instructions pointed to
   `mods/mod_overrides`, not `assets/mod_overrides`. Correct the install root first;
   a mod-manager listing is not evidence of engine resource loading.
2. **New texture paths without registration.** These are not existing game textures
   to override. Include a `main.xml` with explicit `AddFiles/texture` entries and
   require BeardLib; do not describe it as optional.
3. **Packaging tests mistaken for gameplay validation.** Correct paths and XML do
   not validate skinning, geometry, masks or animation. Keep status in-progress until
   the user's game provides the visual oracle.
4. **Repeated installs obscure the result.** Avoid nested archive folders and duplicate
   manager-created copies. Fully exit and restart after changing assets or settings.

## Assets

No new art or extracted game files were added. Existing archive payloads were left
unchanged; only metadata was repaired. Redistribution rights must be checked before
publishing third-party assets.

## Open questions

Does the user's installation have SuperBLT rather than legacy BLT, and BeardLib?
After the installation correction, do menu and third-person models load correctly?
If not, request the full install path, game/loader versions, latest loader log and,
for crashes, the crash log. Mesh and animation fixes may still be necessary.
