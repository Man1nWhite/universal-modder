# Miranda Lawson — Legendary Armour Skins outfit (v2)

<!-- pack_version: 0.1.2 -->

**Asset:** `lawson_las.zip` (8,015,688 bytes)
**sha256:** `a24f0b7c54871c11d89fbeb6d8af3c72e527560a2d703835fdf6fbd2e8e4a503`
**Pack version:** `0.1.2` — *experimental, offline validated, not game-verified*

Miranda Lawson (Mass Effect 2) as an **equipable full-body outfit** for PAYDAY 2,
registered as a **Legendary Armour Skins** add-on. This is *not* a character
swap: it uses its own units and its own FPS (first-person) arms, and it hides
the heister's mask and armour while the skin is worn.

## What changed in 0.1.2

- **The skin is no longer punched full of holes.** The bind-pose transfer
  rotates every bone piece independently, and where the ME2 and the PD2 rigs
  disagree — the hips, the wrists, the ankles — neighbouring pieces ended up
  rotated against each other and a band of triangles folded back on itself.
  1,027 of the 18,277 triangles were wound inside out: the game culls them, so
  they left holes in the chest, the shoulders and the arms, and the skin
  around them shaded backwards. The builder now detects every triangle that
  faces away from its own vertex normals and reverses its winding, which puts
  the triangle back in front of the skin without moving a single vertex.
- **The audit can see it.** A new check (`N3`) decodes the built model and
  fails if any triangle is wound against its normals, so a pack with holes in
  it can never be published again. It failed on the 0.1.1 pack and passes on
  this one.
- **The audit is adversarially tested against that check too**: 16 deliberately
  broken packs, 16 caught (the self-test gained an "inverted triangle"
  mutation).
- **The test suite is mutation-tested as well**
  (`tools/pd2-port/check_test_suite_mutations.py`): 5 broken packs, 5 caught by
  the pack-level tests — a test that passes or skips instead of failing is
  reported as a hole.
- **The normal-map green channel was investigated**
  (`tools/pd2-port/check_nm_convention.py`): the source maps are genuine
  tangent-space normal maps, and the convention cannot be read out of the
  files (their blue channel is saturated, so both conventions are equally
  self-consistent). The source is a Mass Effect 2 (DirectX 9) asset, whose
  maps are Y-, and PD2 wants Y+, so the default build — which inverts the
  green channel — is the right one.

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
  now runs over the built pack: 38 checks pass, 1 warning, 0 failures against
  the ModWorkshop LAS/MOOG outfit guide. The audit is part of the test suite,
  so a pack that drifts from the guide fails the build — and the audit itself
  is mutation-tested (`check_guide_compliance_self_test.py`): 16 deliberately
  broken packs, 16 caught.

---

## Requirements

| | |
|---|---|
| Game | PAYDAY 2 (Windows) |
| Loaders | **SuperBLT** + **BeardLib** |
| Mod | **Legendary Armour Skins** (or Wardrobe Mod) |
| Version | 0.1.2 (current) |

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
welded vertex graph). Triangles that the transfer folded inside out are
detected and reversed afterwards. Models are authored as DODB `.model` files;
textures are repacked into PD2's DXT5 layout with full mip pyramids and the
PD2 normal-map convention (X in alpha, Y flipped).

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

- 187 automated tests pass, including an end-to-end test on the real source
  zip (ME2 COLLADA import, rig retarget, model authoring, pack assembly).
- The guide-compliance audit passes: 38 checks against the ModWorkshop
  LAS/MOOG rules, 0 failures (1 warning: the normal maps' green-channel
  convention is settled by the engine's provenance, not by the files, and only
  the game can confirm it). The auditor is itself tested: it must fail on 16
  deliberately broken packs, and it does.
- Every triangle of the built model faces the same way as its own vertex
  normals — the check that catches the holes 0.1.1 had.
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
- The bind-pose transfer fits every bone piece independently, so where the ME2
  and the PD2 rigs disagree the surface still creases locally (the 0.1.2
  repair un-winds those triangles, but the crease itself is still there). A
  transfer that keeps the two rigs consistent instead of fitting them bone by
  bone would remove it; that is a larger piece of work.
- The normal maps invert the green channel, because the source is a DirectX
  asset and PD2 wants OpenGL-style Y+. If the lighting looks inverted in game,
  rebuild with `--keep-nm-green`.
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
