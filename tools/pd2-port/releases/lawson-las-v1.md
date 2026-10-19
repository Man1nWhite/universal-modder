# Miranda Lawson — Legendary Armour Skins outfit (v1)

<!-- pack_version: 0.1.0 -->

**Asset:** `lawson_las.zip` (7,967,568 bytes)
**sha256:** `8629051ead84cd7a180a427c9969844363987213885c242eb05f6f34707247f3`
**Pack version:** `0.1.0` — *experimental, offline validated, not game-verified*

Miranda Lawson (Mass Effect 2) as an **equipable full-body outfit** for PAYDAY 2,
registered as a **Legendary Armour Skins** add-on. This is *not* a character
swap: it uses its own units and its own FPS (first-person) arms, and it hides
the heister's mask and armour while the skin is worn.

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

- 179 automated tests pass, including an end-to-end test on the real source
  zip (ME2 COLLADA import, rig retarget, model authoring, pack assembly).
- The geometry gates in `tools/pd2-port/preview_check.py` pass: no weld
  discontinuities above 2.4 cm, no face/mouth/eye distortion, zero corner-split
  twin separation, arm-only FPS cut of 10,468 vertices.
- An encode/decode round trip is pixel-identical on three views (max per-axis
  deviation 7.6e-06 cm).

Still unknown until someone runs it in the game:

- how the shoulder and hip alignment look on the real animation set;
- whether the contour (wall outline) renders as intended on every heister;
- FPS arm visibility and deformation in first person;
- multiplayer safety. **Test offline only until it is verified.**

## Known limits

- Shoulder/hip alignment still needs a visual check; the source figure's own
  pose differs slightly at the hips (a small waistband wrinkle, present in the
  ME2 model too).
- The side swap maps by world side: if the source mesh is mirrored, asymmetric
  surface detail will show it.
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
