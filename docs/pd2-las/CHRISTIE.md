# Christie LAS packs — DOA5 Christie as body-only PAYDAY 2 LAS outfits

- `dist/Christie_LAS.zip` (+ `.sha256`) — full body incl. Christie's hands.
- `dist/Christie_LAS_Slim.zip` (+ `.sha256`) — 10% thinner in width and depth
  **and no hands** (`--variant slim`; the separate no-hands pack was removed —
  slim supersedes it): the retargeted body is scaled ×0.9 in X/Y about its own
  vertical axis (normals inverse-transpose corrected), **Z/height untouched**;
  arm-chain verts (bone palette names containing "Arm"/"Hand") get an extra
  ×0.75 in X/Y so the arms are 25% thinner than the base pack, then the hands
  are cut at the wrist, the sleeves are stretched deep past the wrist joint
  (blazer −4.5 cm, skin −3.5 cm, shirt −3.0 cm) so the spawned glove sits well
  inside the cuff in every pose, plus a `*_glove_adapter.lua` compat hook
  (default glove restored, adapter re-enabled) so the heister's changeable
  in-game gloves show through the sleeves. Applied before the fps extraction
  so the viewmodel arms match.

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

**Arm bone mapping:** the menu-pose retarget leaves the elbows ~5.3 cm inboard
of the PD2 `Arm` pivots, so after `retarget_maps` the build runs
`fix_arm_fits()`, which **pure-translates** the existing `Arm`/`ForeArm` fits
(rotation untouched, delta added to matrix rows 12–14) so each source Arm
joint lands exactly on its same-named PD2 pivot — elbow/wrist deviation 0.00 cm,
no vertex spikes (z extent stays ≈164 cm, 0 orientation breaks). Do NOT
re-fit those bones with a fresh rotation: the harmonic blend with the Spine1
fit spikes shoulder-top verts to z ≈191–199.

## Build

```sh
.venv/bin/python tools/pd2-las/build_christie_las.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # base pack
.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"   # slim pack
```

Pipeline: `build_christie_las.load_christie` parses the MDL with **every
bodygroup model** walked (DOA5 ships body/glasses/bra/head as bodypart model
variants; `source_model.load_model` only reads each bodypart's first model and
its VVD LOD0 count check then fails — 21,979 vs 18,359) → kept-material filter
(`cri_body_base`, `cri_02_01/02/05_base`; everything head-carried dropped) →
`build_models.retarget_maps` with `tools/pd2-las/christie_skeleton_map.json`
(DOA `MOT*`/`OPT_Hand_*` bones → PD2 skeleton; `MOT02_Chest` maps to **Spine1**,
not Spine2 — measured joint deviation after retarget drops 9.6 → 3.5 cm and the
arm chain improves 6.2 → 5.3 cm) → `transfer_group` (body +
shadow) → `assemble_model(..., drop_drawables=("g_head", "g_head_lod1"))` →
fps arms via `extract_bones(is_fps_arm_bone)` on the fps_2b template → VTF→DDS
textures (bumpmap resolved from each VMT's `$bumpmap`, normals swizzled
`invert_y=True`, **diffuse alpha attenuated from the normal map's alpha** —
Source leaves diffuse alpha at 255, which PD2 reads as full mirror gloss; that
was the washed-out look in the first in-game test — and **every map expanded to
a full mipmap pyramid** in vanilla PD2's header shape (flags 0x000A1007,
caps 0x00401008; the source VTFs ship mip 0 only, and mip-0-only .texture files
render wrong in game — see tools/pd2-port/dds.py) → pack + reproducible zip
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
