# Skyrim clothing → PAYDAY 2 LAS — cancelled

**Status:** cancelled by the user on 2026-11-04. The in-game result remained
unacceptable after repeated iterations. Do not treat this port as a usable or
installable mod.

This page is the only remaining record. The source-audit, plan and
fixes write-ups were deleted on 2026-11-05 along with every reference to the
outfit they described.

## What was cancelled

A Skyrim SE body-slide outfit (body + blazer + bustier + pencil skirt + heels +
necklace, delivered as five `.zip`/`.rar` archives) was being converted into a
full-body LAS armour skin with the clothes' own body kept, the same way the
Miranda line keeps hers. It was built, rendered offline, and tried in game; the
sleeve/hand junction, the shirt collar over the jacket and the physics-driven
skirt never came out clean, and the user cancelled the port.

## Cleanup performed

- Removed the five original source archives (`1.zip`–`5.zip`) from the current
  branch.
- Removed the built `dist/` pack, its checksum, and the extracted package
  folder.
- Removed generated `build/skyrim-nif/` model, texture and preview artefacts.
- Removed the tracked outfit preview renders, the user-supplied reference
  screenshots (`docs/skyrim-nif/reference-images/`), and the `secretary/`
  placeholder directory.
- Retained the conversion, inspection and preview tools under `tools/pd2-las/`
  and `tools/skyrim-nif/`, along with the generic technique note in
  `knowledge/games/payday-2/las-moog-outfit-porting.md`.

The retained tools are not currently buildable from this checkout: the source
archives are gone. Rebuilding would require re-supplying the inputs and
explicitly restarting the project. Do not recreate or publish the outfit unless
asked.

**Git history note:** this removes the archives and pack from the current branch
tip; earlier commits still contain the previously committed files. They have not
been purged by rewriting history.

## If the work is ever reopened

Start from the reusable half, which is source-agnostic and still in the tree:

- `tools/pd2-las/build_skyrim_outfit.py` — end-to-end build and preview driver.
- `tools/pd2-las/las_outfit_pack.py` — LAS pack layout: manifest, hook, locales,
  unit/object XMLs, material configs, icon and `BUILD_INFO.json`.
- `build_models.py`'s `weld_open_seams`, `extend_sleeves_to_wrist` and
  `follow_layer_weights` — the three passes a layered clothing port needs.
Read [`HANDOFF.md`](HANDOFF.md) for the constraints that were learned the
expensive way before picking any clothing source.
