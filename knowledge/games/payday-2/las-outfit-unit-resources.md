---
kind: game
title: Repairing Lawson LAS registration and outfit-unit resources
game: PAYDAY 2
games_also: []
game_version: "User crash logs: 1.0.0-159028; no agent-side game runtime"
platform: windows
engine: native
route: loader-api
tools: [Python 3.11, numpy, Pillow, pytest, Lua 5.1 via lupa, SuperBLT, BeardLib 5.2.0, Legendary Armour Skins 4.1.9]
anti_cheat: "Offline/manual tests only; no client, loader or game installation changes"
status: in-progress
agents: [Arena.ai agent]
humans: []
date: '2026-10-18'
links:
- https://github.com/Vladik268/P2/tree/b7c38c1d358fe054df51201788126c25a0da1938/mod/Legendary%20Armour%20Skins
- https://github.com/simon-wh/PAYDAY-2-BeardLib/tree/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046
tags: [payday-2, diesel, las, wardrobe, outfit, materials, culling, crash, packaging]
---
# Repairing Lawson LAS registration and outfit-unit resources

**Status: an offline-tested repair candidate, not a verified game fix.** The user
reports that the original `Lawson_LAS` crashes, while the source Clover override
loads but its model is badly broken. The new LAS pack still inherits that rig.

## Setup

Private Linux build workspace, Python 3.11 with Pillow/numpy/pytest; optional
lupa provides Lua 5.1 contract execution. User-provided Windows crash logs report
game build 1.0.0-159028. No PAYDAY 2 installation or Windows automation is
available here, and the user's exact loader/framework versions are unconfirmed.
Inputs are the supplied Clover ZIP, icon texture and 2B format reference.

## Route and evidence

The latest three crash records fail natively on Main during `spawn_unit` through
`spawn_and_link_unit`, `set_character_visual_state` and the menu character update.
Eleven older records instead fail in `load_packages`; one has no script stack.
The logs do not identify an offending asset or prove a specific native cause.
Do not infer an audio fault from repeated unresolved AK::WriteBytesCount symbols.

The original LAS-branded manifest actually registered a plain BeardLib
`PlayerStyle id="lawson"`. The supplied 2B RAR instead registers a
`LegendaryArmours` entry in a hook on `lib/tweak_data/armorskinstweakdata`.
The user requested work on the LAS edition, separately from the no-LAS BeardLib
variant, so the repair adopts that actual LAS contract.

Read LAS 4.1.9 in the pinned public `Vladik268/P2` copy above and BeardLib 5.2.0
at the pinned ref. These are API reference versions, not assertions about the
user's installed or latest versions. Third-party Lua and extracted reference
assets were kept outside Git; no framework code or 2B assets are bundled.

## What was changed

- `build_outfit.py` creates `LegendaryArmours.lawson`, with the 2B-style
  `hide_mask`, `hide_armor`, `replace_all`, `fps_hide_armor` and
  `fps_replace_body` flags. LAS 4.x's `hooks/outfits/loader.lua` maps it to
  `las_lawson` in the Outfit / Player Styles selector. LAS owns mask handling;
  a plain native PlayerStyle flag is not an equivalent replacement.
- `outfit_model.py` shares preparation with the native BeardLib builder: retain
  the skeleton, prune unused drawables/chains/material groups, cut FPS with an
  immutable one-ring arm selection and check actual render-atom references.
  The broader parser/normalizer audit findings are not all repaired here.
- The old TPP binary kept 52 drawables, many using materials omitted by the
  sidecar. Even enabled `s_body` lacked its `shadow_caster` definition. The
  candidate keeps 7 TPP / 2 FPS drawables and defines every retained material.
  Missing source definitions now abort packaging.
- Culling uses real `g_body` geometry with bounds enclosing all retained mesh
  positions, not an empty `co_box` object3D. FPS body has 1,998 vertices plus the
  original 4,538 hand vertices. This is not a watertight or alignment guarantee.
- Keep BeardLib's `unit_mat auto_cp="true"`: its actual package-manager shortcut
  registers model, object, unit and material_config plus BeardLib's own default
  cooked_physics. Do not fabricate an empty physics payload or eagerly load it.
- Localization is standard JSON. Both LAS `armor_skins/lawson` and native
  fallback `player_styles/las_lawson` icon paths are supplied. The ZIP is atomic
  and deterministic, with source/payload hashes and `runtime_verified=false`.

## Rebuild and install

From the repository root with Pillow/numpy installed:

```sh
python tools/pd2-port/build_outfit.py
python -m pytest -q tests/test_outfit_pack.py tests/test_outfit_beardlib_pack.py tests/test_pd2_packages.py
```

Output: `dist/lawson_outfit.zip`, root `Lawson_LAS/`, version `1.1.0-rc1`.
Requires SuperBLT, BeardLib and Legendary Armour Skins / Wardrobe Mod (#24006).
The separate `dist/lawson_outfit_BeardLib.zip` remains the no-LAS variant.

Back up saves and mod_overrides; select vanilla before upgrading if possible.
With the game closed, move the OLD Lawson_LAS completely outside
`assets/mod_overrides`, then extract the candidate there. Renaming a folder
inside mod_overrides can leave both versions active. Restart completely.
On LAS 4.x choose **[LAS] Miranda Lawson**, internal ID `las_lawson`, with Default
gloves, not the obsolete plain `lawson` style. Older LAS may use its armor menu.
Start with other character replacements and the BeardLib Lawson edition off.

Check the menu preview once; if it crashes, stop and collect fresh crash/loader
logs and exact game/BeardLib/LAS versions. Only if it works, continue with a
backed-up offline heist. No automated game input, loader install, save edit or
online test was performed. To remove, equip vanilla if possible, close the game
and move only this pack out; do not delete shared loaders or saves.

## Verification and limits

- **87 related tests passed**, covering registration, resource/material coverage,
  bounded culling, skeleton/TPP preservation, stable FPS cuts, input overwrite
  guards, atomic failures, metadata hashes and distribution-payload parity.
- Full suite with FFmpeg/ffprobe and optional Lua 5.1 execution available:
  **240 passed, 1 skipped** (MSYS-only); one existing Pillow deprecation warning.
- Manual Lua 5.1 smoke executed the actual pinned BeardLib `HooksModule` and
  `LoadConfigUnitShortcutNode`, and LAS 4.1.9's loader against the generated
  manifest/registration. Confirmed the post-hook source/path/case, 10 implicit
  unit resources including external default physics, `las_lawson` units,
  default gloves/adapter flags, body/mask fields equal to the supplied 2B
  registration, icon routing and coexistence with the native style ID.
  Engine/file boundaries and host objects were stubbed: not native loading.
- LAS ZIP: 35 files, 6,092,512 bytes, SHA-256
  `f729868d51bb8a7547a4cfddbd3e8184e12c8c72112c11536fdf1c5f6fca7230`.
- The BeardLib builder delegates to the same model helpers but its ZIP remains
  byte-identical: SHA-256
  `591f6d7b9c6ef9a8c6a8b6f2c0183519e2d1a728711e0ed8a75fc555cfe7283f`.
  Three character archives and `2b.rar` are unchanged.
- No PAYDAY 2 runtime test: crash resolution, appearance, rigging/UVs, mask
  visibility, animation, weapon alignment, VR and multiplayer remain unverified.
  No publication or redistribution clearance is implied.

## Gotchas

1. **LAS in a filename is not LAS registration.** Check the actual registry/API
   and the framework's current item ID and menu mapping.
2. **Disabled XML objects can leave unresolved binary resources.** Prune unused
   drawable chains; compare every remaining model material against the config.
3. **Material-name checks in only one direction miss missing shadows.** Test
   model-to-config coverage as well as config-to-model names.
4. **An empty object3D is not bounded culling geometry.** Use a real drawable and
   bounds that include all retained pieces, then verify culling in the game.
5. **Face-order-dependent selection grows beyond one ring.** Freeze the initial
   seed before walking topology; test reversed and shuffled faces.
6. **Passing structure/API tests is not crash or visual success.** Keep the
   user's real failure authoritative until the game oracle demonstrates a fix.
