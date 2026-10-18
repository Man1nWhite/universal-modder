---
kind: game
title: "LAS armor-skin outfits in PAYDAY 2 from a Source-engine character mod"
game: "PAYDAY 2"
games_also: ["Left 4 Dead 2"]
game_version: "User build 1.0.0-159028 for the earlier crash logs; no agent-side game runtime"
platform: windows
engine: diesel
route: asset-only
tools: ["Python 3.11", "SuperBLT", "BeardLib 5.2.0", "Legendary Armour Skins 4.x"]
anti_cheat: "Offline only; no client, loader or game installation changes"
status: in-progress
agents: ["Arena.ai agent"]
humans: []
date: 2026-10-18
links:
- "https://github.com/Vladik268/P2/tree/b7c38c1d358fe054df51201788126c25a0da1938/mod/Legendary%20Armour%20Skins"
- "https://github.com/simon-wh/PAYDAY-2-BeardLib/tree/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046"
tags: [payday-2, diesel, las, armor-skin, l4d2, source-engine, vpk, mdl, vtf, outfit]
---

# LAS armor-skin outfits in PAYDAY 2 from a Source-engine character mod

> Route change for the Miranda Lawson project: retired surgical heister-model
> replacement (a dead end) and started an equipable Legendary Armour Skins
> (LAS) armor-skin add-on — the same product shape as the supplied `2b.rar`
> reference — built from the L4D2 "Miranda Rochelle" Source model. Extraction,
> Source model/VTF parsing and the LAS registration scaffold are working offline;
> the Diesel `.model` authoring and any in-game test remain.

## Setup

- Source material: `l4d2_miranda_lawson_1.zip` (GameMaps.com "Miranda Lawson"
  L4D2 addon; a single-file VPK replacing Rochelle: third-person
  `survivor_producer.{mdl,vvd,phy,dx80/dx90/sw.vtx}`, first-person
  `v_arms_producer_new.*`, 8 VTF + 6 VMT materials). User-supplied private input.
- Product-contract reference: `2b.rar` (2B LAS pack: `LegendaryArmours.twobee`
  hook on `lib/tweak_data/armorskinstweakdata`, unit + fps_unit, hide_mask /
  hide_armor / replace_all / fps flags, BeardLib `main.xml` + `unit_mat`
  registration). Studied as text/binary, not installed.
- Pipeline: `tools/pd2-las/` (Python 3.11, Pillow/numpy for previews and the
  icon encoder), tests in `tests/test_pd2_las.py` against the tracked zip.
  No PAYDAY 2 install in this environment.

## Route and why

The retired route replaced Clover/Bonnie/Sydney by surgically editing their
Diesel `.model` containers (SkinBones palettes, DODB section renumbering, FPS
arm cuts) and built outfit packs on the same rigged mesh. It was a dead end:
the source rig/UVs were broken at export, the character packs rendered wrong,
the LAS-branded outfit crashed, and every "fix" was a speculative binary patch
that could not be verified without the game. Direct model surgery is where the
time went and none of it produced a loadable, correct character.

The new route adds a standalone LAS armor skin instead of changing any shipped
model: one unit + one fps unit registered through the LAS
`LegendaryArmours` table, exactly the 2B contract. The mesh does not start from
a broken rig this time — the L4D2 mod is a complete, working character model
(third-person body and first-person arms with their own materials).

## How the game works (what we had to learn)

- **LAS registration contract** (from `2b.rar` + LAS 4.x sources): a SuperBLT
  hook on `lib/tweak_data/armorskinstweakdata` creates
  `LegendaryArmours.<id>` with `category`, `unit`, `fps_unit` and the boolean
  flags `hide_mask`, `hide_armor`, `replace_all`, `fps_hide_armor`,
  `fps_replace_body`. LAS maps the item into Outfit/Player Styles
  (`las_<id>` on LAS 4.x). A BeardLib `PlayerStyle` is NOT the same contract.
- **BeardLib packaging** (2B `main.xml`): a `<table>` with `<Localization>`,
  `<Hooks source_file=...>`, and `<AddFiles>` registering `texture`, `df_nm`
  (df+nm pair shorthand) and `unit_mat` (model+object+unit+material_config
  shortcut) resources. Texture registration must cover every new `.texture`.
- **Target object naming** (from `2b.model`'s embedded hashlist): the outfit
  model uses the PD2 player skeleton (`root_point`, `Hips`, `Spine`, `Spine1`,
  `Spine2`, `Neck`, `Head`, `eyeAim`, finger chains, `a_weapon_*`, `aim`,
  `BackPack1`, leg chain) plus graphics objects `s_body`, `g_body`,
  `g_body_lod1`, `g_head`, `g_head_lod1` and collision `c_sphere_*`/`c_capsule_*`.
- **Source studio formats** (source-sdk-2013 `studio.h`/`optimize.h`): MDL 48
  (L4D2) with struct-relative `sznameindex` offsets, 216-byte bones, 64-byte
  texture records, 16-byte bodyparts, 116-byte meshes; VVD v4 with
  `numLODVertexes[MAX_NUM_LODS=8]` and 48-byte vertices (3 bone weights);
  VTX v7 `#pragma pack(1)` (FileHeader 36 bytes with `bodyPartOffset`,
  strip groups reference `origMeshVertID` back into the VVD).
- **VTF 7.4**: resource entries at offset 80 (IMAGE tag 0x30 with absolute
  offset), low-res width/height are single bytes at 61/62, and the high-res
  mip chain is stored **smallest mip first** (mip 0 is at the tail — verified by
  decoding both orders of the real face texture). DXT5 payloads convert to DDS
  (PAYDAY 2 `.texture`) by reversing the chain; DXT5 colour endpoints must be
  written c0 > c1 or decoders render blocks as holes.

## Build steps

```sh
python tools/pd2-las/build_las.py            # extract + inventory + textures + scaffold
python -m pytest -q tests/test_pd2_las.py    # offline structural tests (23)
```

Output goes to `build/pd2-las/` (gitignored): `extracted/` (VPK contents),
`previews/` (PNG textures), `textures/` (DDS `.texture` files),
`Miranda_LAS/` (the LAS pack scaffold: main.xml, `miranda_las.lua` hook,
localization, converted textures, icon, unit/object/material_config XMLs,
`BUILD_INFO.json` with per-file hashes, `WIP_DO_NOT_INSTALL.txt`).

## Verification

- 23 structural tests pass against the tracked source zip: VPK inventory and
  CRC-checked reads, safe extraction, both models parsed (104/53 bones,
  16,433/2,892 triangles, valid weights and indices), all 7 VTFs converted with
  exact DDS chain sizes, mip-order proof, PNG previews, BC3 icon round-trip,
  and scaffold assertions against the 2B registration contract.
- Texture previews decode cleanly (face/body atlases) and the icon renders.
- **Not verified:** anything in-game. The Diesel `.model` authoring
  (Source mesh → PD2-skeleton skinned model) is not done, so the scaffold is
  deliberately incomplete and marked `WIP_DO_NOT_INSTALL.txt`. No claim about
  loading, animation, mask handling or multiplayer sync.

## Gotchas

1. **Symptom:** rebuilt packs crashed in `SkinBones`/`load_packages` after
   minutes of binary patching. **Cause:** surgical edits of shipped character
   models (bone-mapping indices, section-ID contiguity) with no game oracle.
   **Fix:** don't change shipped models at all — ship a standalone LAS item
   like the 2B reference. Treat the old route as abandoned, not "almost fixed".
2. **Symptom:** VPK entries read as garbage headers. **Cause:** `entry_offset`
   is relative to the end of the directory tree, not the file start; root-level
   files use a single-space folder marker. **Fix:** add `tree_start + tree_size`
   and map `" "` to the bare stem.
3. **Symptom:** VTF→DDS previews showed tiled mip garbage at the top of mip 0.
   **Cause:** VTF stores the high-res chain smallest-mip-first and the first
   slice builder kept file order. **Fix:** slice in file order, then reverse to
   mip 0 first; sanity-check by decoding both orders of a real texture.
4. **Symptom:** DXT5 icon decoded with transparent holes. **Cause:** colour
   endpoints written with c0 <= c1 select the 3-colour + transparent-index
   block mode. **Fix:** always emit c0 > c1.
5. **Symptom:** `sznameindex`-style names resolved to binary noise.
   **Cause:** Source `sznameindex` fields are offsets relative to their own
   struct, not file offsets. **Fix:** `struct_start + sznameindex`.
6. **Symptom:** mesh/strip-group strides guessed from one file looked wrong.
   **Cause:** VTX structs are `#pragma pack(1)` (mesh 9 bytes, strip 27,
   group 25) while MDL structs are 32-bit aligned (mesh 116). **Fix:** take
   strides from `source-sdk-2013` headers; verify arrays tile exactly.

## Assets

All geometry and textures come from the user-supplied L4D2 addon (itself a
fan-made Mass Effect 2 character rip). No fal generation. The menu icon is the
face diffuse cropped/resized to 256×256 and BC3-encoded by
`tools/pd2-las/dds_encode.py` (naive endpoints; fine for UI, not for
materials).

## Open questions

1. Source mesh → Diesel `.model` authoring: skin `miranda.smd` to the PD2
   player skeleton (ValveBiped → Hips/Spine/… mapping), emit `g_body`/`g_head`
   drawables with `s_body` and culling objects, plus `fps_miranda` from
   `miranda_arms.smd`. The retired `tools/pd2-port/dmodel.py` format knowledge
   (DODB section order, SkinBones local-index rule) is gone with the dead end —
   re-derive from `payday2-model-tool` research notes if needed.
2. Material strategy: Source EyeRefract eyes and phong hair need Diesel
   equivalents (`mtr_head` alpha-masked lashes in the 2B reference).
3. Redistribution rights for ME2-derived assets remain unresolved: private
   experimental use only, never a public release.
4. In-game verification ladder (menu preview → offline heist → animations,
   mask/armor hiding, FPS alignment) is entirely untouched.
