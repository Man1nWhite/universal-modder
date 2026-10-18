---
kind: game
title: Standalone BeardLib player-style outfits without LAS
game: PAYDAY 2
games_also: []
game_version: "User build unknown; no game runtime available"
platform: windows
engine: native
route: loader-api
tools: [Python 3.11, Pillow, numpy, pytest, SuperBLT, BeardLib 5.2.0, Lua 5.1 via lupa]
anti_cheat: "Not assessed on user's installation; offline tests only, no game/client modifications performed"
status: in-progress
agents: [Arena.ai agent]
humans: []
date: '2026-10-18'
links:
- https://github.com/simon-wh/PAYDAY-2-BeardLib/tree/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046
- https://github.com/steam-test1/Payday-2-LuaJIT-Complete/tree/e3a8b6168a8dca75ebe741cd77babd1080904032
- https://github.com/diesel-modding/PAYDAY2-SuperBLT-Lua/tree/5602d35c9a0020c2cba87cd79f25563f8d5435d7
tags: [payday-2, diesel, beardlib, player-style, outfit, materials, first-person, packaging]
---
# Standalone BeardLib player-style outfits without LAS

Added an independent Lawson outfit using BeardLib's native `PlayerStyle` module,
not Legendary Armour Skins (LAS). The package builds reproducibly, passes offline
structural tests, and its configuration passes an actual-upstream Lua API smoke
test in a stubbed host. **It has not been tested in PAYDAY 2**; status remains
in-progress until visual, animation and outfit-switching checks succeed.

## Setup

- Engine: Diesel (the KB's generic `native` engine family); target PC/Windows.
- Build lab: Python 3.11 on Linux, Pillow/numpy and pytest. No game installation,
  Blender, loader installation or Windows/game automation was used.
- Source: the supplied repaired `dist/lawson_clover.zip` plus the supplied
  `Lawson model/Miranda_face_d.png` icon input. The already-rigged binary mesh is
  reused; this is not a reproducible fresh OBJ-to-rig pipeline.
- BeardLib API checked at commit `95eb1c0c84e3f07d36f28a5e69197ec3b5c59046`
  (5.2.0), not asserted to be the user's installed/latest version.
- Game API inspected at `e3a8b6168a8dca75ebe741cd77babd1080904032`.
  Public source was kept outside the repository; no decompiled code is shipped.

## Route and why

The request was an additional BeardLib version, preserving the existing archives.
The legacy `Lawson_LAS` archive actually already contains a `PlayerStyle`
manifest despite its LAS branding. Renaming it would preserve its resource-ID
collisions, missing material and order-dependent FPS cut. The separate builder
uses its own `lawson_beardlib` item/global-value ID, asset paths and icon bundle,
without requiring LAS, Wardrobe Mod or the source character replacement at runtime.

## How the game works (what we had to learn)

- BeardLib `Modules/PD2/PlayerStyleModule.lua` inserts the parsed configuration
  into the native `player_styles` table through `BeardLibCreateCustomPlayerStyles`.
- The game's `BlackMarketTweakData:get_player_style_value` checks character
  overrides before global fields. Global `unit` / `third_unit` therefore avoid an
  incomplete hard-coded list of heisters. This is a configuration fallback, not
  proof that every skeleton/body proportion is visually compatible.
- `CriminalsManager` reads `body_replacement` for the local player and
  `third_body_replacement` for third person. Supported flags are head, body,
  hands, arms, vest and armor. Store them as **boolean XML attributes**, not child
  tables containing a `value` member. A `mask` flag here does not hide the
  separately spawned mask.
- BeardLib `PlayerStyleGloveHooks.lua` honors `default_gloves="false"` through
  `default_glove_id=false`: choosing Default gloves returns a false glove unit.
  Non-default gloves are still selectable; `exclude_glove_adapter` alone does
  not suppress every glove.
- `.object` files use `dynamic_object` / `diesel` / `graphics/graphic_group`;
  `culling_object` belongs to the graphic group. The pack uses a real `g_body`
  drawable with conservative bounds, not the legacy empty `co_box` locator.
- Materials must cover the **model's used render atoms**, not merely have names
  present somewhere in the model. The retained `s_body` uses `shadow_caster`,
  with `shadow_caster_only:SKINNED_1WEIGHT`. FPS body materials use the existing
  `generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS` template.
- Diesel topology index **counts** are UInt32; individual vertex references are
  UInt16. The new range checker rejects bad vertex/material/range references
  without treating 65,535 as the total-index-count limit. It supplements the
  old validator; it does not repair all unrelated normalization/parser issues.

## Build steps

From the repository root, with project dependencies installed:

```sh
python tools/pd2-port/build_outfit_beardlib.py
python -m pytest -q tests/test_outfit_beardlib_pack.py tests/test_outfit_pack.py
```

Output is the ignored local `dist/lawson_outfit_BeardLib.zip`. Extract directly
under `PAYDAY 2/assets/mod_overrides/`, giving
`Lawson_Outfit_BeardLib/main.xml`. Requires SuperBLT + BeardLib; do not install
under `mods/mod_overrides`. In the native Outfit / Player Styles list, select
**Miranda Lawson (BeardLib)** and Default gloves. Back up the profile and mod
folder, disable conflicting character replacements and test offline first.
Before removal, equip a vanilla outfit; close the game and remove only this
pack's folder. Full instructions are in the bundled README and
[the builder guide](../../../tools/pd2-port/README.md#standalone-beardlib-outfit).

## Verification

- 34 dedicated offline tests passed: safe single-root ZIP, manifest coverage and
  dependency order, namespace separation, native boolean fields, strict JSON,
  skeleton/TPP geometry preservation, FPS subset, actual material coverage,
  complete DDS mip chains, alpha-derived opacity and atomic failure behavior.
- The FPS `g_body` keeps 1,998 vertices from an immutable 1,825-vertex arm-bound
  seed plus one adjacency ring. Reversal and seeded shuffling give the same
  subset; a synthetic chain confirms it cannot flood-fill beyond that ring.
- Invalid render-atom material IDs, out-of-range vertex references and atom
  ranges are rejected. A synthetic topology with more than 65,535 valid indices
  is accepted by the new checker.
- CLI builds from a different working directory produce byte-identical ZIPs.
  Original four ZIPs and `2b.rar` remain unchanged. The archive contains a source /
  icon / payload hash manifest and an explicit `runtime_verified=false` flag.
- Extra manual Lua 5.1 smoke: the actual pinned BeardLib XML boolean conversion,
  `PlayerStyleModule`, game fallback functions, BeardLib glove getter and
  SuperBLT json10 decoder accepted the generated configuration/localization.
  Five heister names, including one outside the old allowlist, resolved both
  units; Default gloves returned false; a legacy `lawson` registry entry stayed
  intact. Host/engine objects were stubbed, so this is **not** a game test.
- No rendered gameplay, weapon alignment, animation, VR or multiplayer evidence
  exists. Full-suite/check results are recorded in the
  [journal](../../../tools/pd2-port/MODLOG.md).

## Gotchas

1. **LAS branding can misidentify the integration.** A `wardrobe_mod` resource
   path or `[LAS]` name is not registration. Inspect `PlayerStyle` versus
   `LegendaryArmours` use before choosing dependencies or menu instructions.
2. **Third-person body duplication despite FPS replacement.** The game uses
   separate replacement maps. Supply both with supported native fields.
3. **Missing shadow material survives one-way tests.** Checking only config names
   against model names misses model-used-but-undefined materials. Compare used
   render-atom hashes to configuration hashes in both directions.
4. **Changing triangle order changes an arm cut.** Growing the seed while walking
   faces turns adjacency into an accidental flood fill. Keep the initial seed
   immutable and expand exactly the intended number of rings. This is not a
   watertightness guarantee.
5. **Wrong opacity or opaque lashes.** The supplied alpha differs from Clover's
   unrelated opacity map. Derive grayscale maps from the supplied BC3 alpha with
   Pillow, use the source's existing alpha-masked shader permutation for lashes,
   and retain all mip levels. Visual shader behavior remains unverified.
6. **Mask still visible / non-default gloves overlap.** Native replacement does
   not implement LAS-style mask hiding and custom gloves may still spawn. State
   these limits; do not introduce untested global mask/glove hooks.
7. **Native bools versus string/table truthiness.** A nested `head/value=true`
   table would be truthy in Lua even for false contents. Use the native attribute
   schema and, when possible, exercise the actual loader's conversion logic.

## Assets

No new image-generation service was used. All 19 supplied DDS texture payloads
are copied unchanged; two opacity maps come from the supplied hair/lash alpha
and one small flat normal is generated locally, all with full DXT5 pyramids.
The icon uses the supplied face texture and existing icon encoder. Only the
standard game hair cubemap remains an external material resource.

The model's original UV seams and rigging are not reauthored here. Input asset
ownership/redistribution permissions remain unresolved. Generated game/model
assets are kept out of Git and are **not a cleared public release**; no loader,
LAS code or `2b.rar` payload is included.

## Open questions

- Does it load/render on the user's precise PAYDAY 2 / SuperBLT / BeardLib build?
- Are arm/hand transforms correct through ADS, reload, melee and weapon changes?
- Do head/hair/masks and every armor/heister combination clip or deform?
- Do culling, opacity and lighting work at normal gameplay distances?
- VR and online synchronization remain untested; test offline first and do not
  assume peers without the same assets will see the outfit.
- Resolve source attribution/licensing before requesting any public release.
