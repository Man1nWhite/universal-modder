# Christie LAS packs — DOA5 Christie as body-only PAYDAY 2 LAS outfits

- `dist/Christie_LAS.zip` (+ `.sha256`) — full body incl. Christie's hands.
- `dist/Christie_LAS_No_hands.zip` (+ `.sha256`) — hands cut at the wrist
  (`--variant nohands`), sleeves stretched over the wrist gap, plus a
  `*_glove_adapter.lua` compat hook (default glove restored, adapter
  re-enabled) so the heister's changeable in-game gloves show through the
  sleeves.
- `dist/Christie_LAS_Slim.zip` (+ `.sha256`) — 20% thinner in width and depth
  (`--variant slim`): the retargeted body is scaled ×0.8 in X/Y about its own
  vertical axis (normals inverse-transpose corrected), **Z/height untouched**;
  applied before the fps extraction so the viewmodel arms match.

Both are Legendary Armour Skins add-ons built from `references/Christie.zip`
(Dead or Alive 5, `christie_c2` — MDL/VVD/VTX + VMT/VTF materials). Install to
`PAYDAY 2\assets\mod_overrides\` with SuperBLT + BeardLib + Legendary Armour
Skins / Wardrobe. The base pack was **tested in game on 2026-11-05**: the
headless LAS contract works (the heister keeps their own head).

**"Without head"** = the police-uniform style LAS contract: the pack ships no
head geometry and registers `replace_body`, not `replace_all` (LAS's
`replace_all` sets head=true and would decapitate the heister when the outfit
has no head). Face/lashes/eyes/glasses/hair/helmet meshes are all dropped; the
heister keeps their own head. See the `las_outfit_pack.py` FLAG_KEYS comment for
the loader semantics.

## Build

```sh
.venv/bin/python tools/pd2-las/build_christie_las.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # base pack
.venv/bin/python tools/pd2-las/build_christie_las.py --variant nohands \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # no-hands pack
.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # slim pack
```

Pipeline: `build_christie_las.load_christie` parses the MDL with **every
bodygroup model** walked (DOA5 ships body/glasses/bra/head as bodypart model
variants; `source_model.load_model` only reads each bodypart's first model and
its VVD LOD0 count check then fails — 21,979 vs 18,359) → kept-material filter
(`cri_body_base`, `cri_02_01/02/05_base`; everything head-carried dropped) →
`build_models.retarget_maps` with `tools/pd2-las/christie_skeleton_map.json`
(DOA `MOT*`/`OPT_Hand_*` bones → PD2 skeleton) → `transfer_group` (body +
shadow) → `assemble_model(..., drop_drawables=("g_head", "g_head_lod1"))` →
fps arms via `extract_bones(is_fps_arm_bone)` on the fps_2b template → VTF→DDS
textures (bumpmap resolved from each VMT's `$bumpmap`, normals swizzled
`invert_y=True`, **diffuse alpha attenuated from the normal map's alpha** —
Source leaves diffuse alpha at 255, which PD2 reads as full mirror gloss; that
was the washed-out look in the first in-game test) → pack + reproducible zip
(fixed 2020-01-01 timestamps, so the `.sha256` sidecar is a true build hash).

Verified offline: 0 orientation breaks, 98% winding agreement, models
byte-round-trip, material_config names hash64-match the models, all tests in
`tests/test_christie_las.py`, byte-reproducible rebuild. **Base pack verified
in game 2026-11-05** (headless LAS renders the heister's own head; texture
gloss fixed). The icon sheet
(`build/pd2-las/previews/christie_icon_sheet.png`) shows a coherent clothed
body with an open neck (headless by design).

Registration: `LegendaryArmours.christie`, `...christie_no_hands`,
`...christie_slim`,
`units/<id>/skins/<id>/<id>[_fps]`, textures
`<id>_{body,c02_01,c02_02,c02_05}_{df,nm}`, icon
`guis/dlcs/<id>/armor_skins/<id>`.
