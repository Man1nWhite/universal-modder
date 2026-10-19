# Miranda Lawson — Legendary Armour Skins outfit (v1)

> **Superseded by [`lawson-las-v2`](https://github.com/Man1nWhite/universal-modder/releases/tag/lawson-las-v2).**
> This build has holes in the skin: 1,027 of its triangles are wound inside
> out, and the game culls them. The 0.1.2 pack repairs them. Use v2.

<!-- pack_version: 0.1.1 -->

**Asset:** `lawson_las.zip` (8,015,689 bytes)
**sha256:** `063d5f64ba7878edc88d43901d690dc32a3324ba6e6b319fe93941ed0a556dbb`
**Pack version:** `0.1.1` — *experimental, offline validated, not game-verified*

Miranda Lawson (Mass Effect 2) as an **equipable full-body outfit** for PAYDAY 2,
registered as a **Legendary Armour Skins** add-on. This is *not* a character
swap: it uses its own units and its own FPS (first-person) arms, and it hides
the heister's mask and armour while the skin is worn.

## What changed in 0.1.1

- **The fingers articulate.** The outfit is now bound to PD2's 30 finger bones
  instead of folding the whole hand onto the wrist bone, so the fingers move
  with the heister's hands instead of staying rigid mittens. The finger bone
  names were recovered offline by hashing PD2's naming convention against the
  2B rig's stored hashes (`tools/pd2-port/resolve_rig_names.py`); the ME2
  finger chains map onto them one-to-one.
- **The first-person hands keep their fingers too.** Binding the fingers to
  their own bones moved their vertices out of the old "arm" bucket, which
  silently cut them from the view model; the arm cut now knows the finger
  chains, so the FPS unit carries all 30 of them.
- **A guide-compliance audit** (`tools/pd2-port/check_guide_compliance.py`)
  now runs over the built pack: 36 checks pass, 1 warning, 0 failures against
  the ModWorkshop LAS/MOOG outfit guide. The audit is part of the test suite,
  so a pack that drifts from the guide fails the build — and the audit itself
  is mutation-tested (`check_guide_compliance_self_test.py`): 15 deliberately
  broken packs, 15 caught.

---

## Requirements

| | |
|---|---|
| Game | PAYDAY 2 (Windows) |
| Loaders | **SuperBLT** + **BeardLib** |
| Mod | **Legendary Armour Skins** (or Wardrobe Mod) |
| Version | 0.1.0 (first public build) |

## Install

1. **Back up** your PAYDAY 2 save and your `assets\mod_overrides` folder.
2. Close the game.
3. Extract `lawson_las.zip` into **`PAYDAY 2\assets\mod_overrides\`** — *not*
   `mods\mod_overrides`. You should end up with
   `PAYDAY 2\assets\mod_overrides\Lawson_LAS\main.xml`.
4. If an older `Lawson_LAS` folder is already there, **move it out completely**
   first. Renaming it in place leaves both versions active and the game loads
   the stale one.
5. Start the game, open the outfit/armor menu, pick **[LAS] Miranda Lawson**
   and keep the default gloves.
6. Test the menu preview first. Only then try a **backed-up offline heist**.

## What is inside

```
Lawson_LAS/
  main.xml                              BeardLib manifest (Localization + Hooks + AddFiles)
  hooks/lawson.lua                      LegendaryArmours.lawson registration
  localization/english.txt              menu strings
  CREDITS.txt                           provenance and rights
  build_manifest.json                   version + per-file sha256
  guis/dlcs/lawson/armor_skins/
    lawson.texture                      256x256 DXT5 menu icon
  units/lawson/skins/lawson/
    lawson.model / .unit / .object      TPP unit (body + head)
    lawson.material_config              TPP materials (contour + normal maps)
    fps_lawson.model / .unit / .object  FPS unit (arms only)
    fps_lawson.material_config          FPS materials (depth scaling)
    body1/body2/face/hair/eyes/
    lashes/teeth/mouth _df.texture      DXT5 diffuse maps, full mip pyramids
    ..._nm.texture                      DXT5 normal maps (PD2 layout: X in alpha)
```

The hook registers the skin with the 2B flag set:

```lua
la.lawson = {
    category = "lawson",
    unit = "units/lawson/skins/lawson/lawson",
    fps_unit = "units/lawson/skins/lawson/fps_lawson",
    hide_mask = true, hide_armor = true, replace_all = true,
    fps_hide_armor = true, fps_replace_body = true
}
```

## How it was built

The outfit is derived entirely from the tracked source
`PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson
(Romance).zip` (rigged COLLADA + textures). The ME2 skeleton is retargeted onto
the PAYDAY 2 biped rig contract extracted from the 2B reference pack, and the
skin is re-bound with a per-bone segment fit (one rigid transform per target
bone, folds sharing their parent's transform, weights smoothed over the
welded vertex graph). Models are authored as DODB `.model` files; textures are
repacked into PD2's DXT5 layout with full mip pyramids and the PD2 normal-map
convention (X in alpha, Y flipped).

The build follows the [ModWorkshop LAS/MOOG outfit guide](https://wiki.modworkshop.net/books/payday-2-mod-creation/page/legendary-armor-skinslasmoogoutfit-module-guide)
(Columbus): PD2's 54-bone skeleton (including the 3-bones-per-finger chains),
at most 3 weight influences per vertex, one `material_config` entry per mesh
material with the attested render templates only, contour materials with
`unique="true"` plus `contour_color`/`contour_opacity`, a separate
arms-only first-person unit with `DEPTH_SCALING`, and DXT5 textures with
full mip pyramids. `tools/pd2-port/check_guide_compliance.py` re-checks the
built pack against those rules on every build.

Build it yourself from the repository:

```sh
python tools/pd2-port/build_las_pack.py          # -> dist/lawson_las.zip
python tools/pd2-port/build_las_pack.py --check  # validate only, write nothing
```

The build is deterministic — same source and same tool code, same zip bytes.
`dist/lawson_las.zip` is tracked in the repository, and the
[lawson-las-pack workflow](https://github.com/Man1nWhite/universal-modder/blob/main/.github/workflows/lawson-las.yml)
rebuilds and re-publishes it on every `lawson-las-v*` tag.

## Verification status — read this before installing

**Nothing here is game-verified.** The pack is offline-validated only:

- 185 automated tests pass, including an end-to-end test on the real source
  zip (ME2 COLLADA import, rig retarget, model authoring, pack assembly).
- The guide-compliance audit passes: 36 checks against the ModWorkshop
  LAS/MOOG rules, 0 failures (1 warning: the normal maps' green-channel
  convention can only be settled in game). The auditor is itself tested: it
  must fail on 15 deliberately broken packs, and it does.
- The pack's structure was diffed field by field against the working 2B
  Legendary Armour Skins reference pack (manifest, hook flags, unit, object,
  material config, localization, locator objects) — it matches.
- The geometry gates in `tools/pd2-port/preview_check.py` pass: no weld
  discontinuities above 2.4 cm, no face/mouth/eye distortion, zero corner-split
  twin separation, arm-only FPS cut of 10,468 vertices.
- An encode/decode round trip is pixel-identical on three views (max per-axis
  deviation 7.6e-06 cm).

Still unknown until someone runs it in the game:

- how the shoulder and hip alignment look on the real animation set;
- whether the contour (wall outline) renders as intended on every heister;
- whether the fingers articulate as expected (they are bound to PD2's finger
  bones, and the offline weight check puts every finger vertex within 2.6 cm
  of its bone, but only the game can show the animation);
- FPS arm visibility and deformation in first person;
- multiplayer safety. **Test offline only until it is verified.**

## Known limits

- Shoulder/hip alignment still needs a visual check; the source figure's own
  pose differs slightly at the hips (a small waistband wrinkle, present in the
  ME2 model too).
- The side swap maps by world side: if the source mesh is mirrored, asymmetric
  surface detail will show it.
- The normal maps assume the source is DirectX-style (green inverted to PD2's
  OpenGL-style Y+). If the lighting looks inverted in game, rebuild with
  `--keep-nm-green`.
- No cooked-physics payloads are shipped; BeardLib's `unit_mat` registration
  supplies the default.

## Credits and rights

- **Model and textures:** ripped from *Mass Effect 2* (BioWare / EA), supplied
  via The Models Resource as *PC / Computer - Mass Effect 2 - Non-Playable
  Characters - Miranda Lawson (Romance)*.
- **Registration and layout:** follows the user-supplied 2B Legendary Armour
  Skins reference pack.
- Not affiliated with or endorsed by BioWare/EA or Supermassive Games. The
  model, the textures and the reference pack are **not ours to license**: this
  is an unlicensed, non-commercial fan derivative and no redistribution
  permission is claimed. The original artists and publishers keep all rights
  to their work.
- Everything is shipped "as is", with no warranty of any kind.
