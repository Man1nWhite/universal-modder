---
kind: game
title: "Porting a rigged character model into a PAYDAY 2 LAS/MOOG outfit (ModWorkshop guide distilled)"
game: "PAYDAY 2"
games_also: ["Mass Effect 2"]
game_version: "community guide, ModWorkshop wiki (work in progress); user game build 1.0.0-159028 in earlier sessions"
platform: windows
engine: native
route: loader-api
tools: ["Blender", "PAYDAY 2 Model Tool v2.18", "PAYDAY-2-Hashlist", "Diesel Bundle Viewer", "SuperBLT", "BeardLib", "Legendary Armour Skins"]
anti_cheat: "offline/asset-only; mod_overrides + loader frameworks, no client tampering"
status: in-progress
agents: ["Arena.ai agent"]
humans: ["Columbus (guide author, credit)"]
date: 2026-10-18
links:
- https://wiki.modworkshop.net/books/payday-2-mod-creation/page/legendary-armor-skinslasmoogoutfit-module-guide
- https://modworkshop.net/mod/58492
- https://github.com/kythyria/payday2-model-tool/releases/tag/v2.18
- https://github.com/Luffyyy/PAYDAY-2-Hashlist
tags: [payday-2, las, moog, outfit, porting, rigging, materials, render-templates, textures, normals]
---

# Porting a rigged character model into a PAYDAY 2 LAS/MOOG outfit

> What the ModWorkshop "Legendary Armor Skins/LAS/MOOG/Outfit Module Guide" (by
> Columbus; also a PAYDAY 2 character-porting guide) actually prescribes, and
> which of those prescriptions we folded into the automated Lawson LAS build.
> Read against [las-outfit-unit-resources](las-outfit-unit-resources.md) (unit
> resources) and [beardlib-player-style-outfits](beardlib-player-style-outfits.md)
> (the no-LAS alternative). The guide is explicitly a work in progress.

## Setup

The guide's manual toolchain: Blender; PAYDAY 2 Model Tool v2.18 (.NET 6);
PAYDAY-2-Hashlist in the Model Tool root (without it exports show hash strings
instead of names); a `.model` extractor (Diesel Bundle Viewer for the legacy
branch, Diesel Crate Browser for 64-bit — note the guide's warning that
64-bit-branch exports do not re-import into current Model Tool); optional
Cpone-derived Blender add-on for direct `.model` import and a bone/vertex-group
merge add-on for twist-bone cleanup. There is a community **MOOG template**
(mod 58492) with commented files; no outfit template for ordinary heisters yet.

## Route and why

Loader-side asset route: a MOOG/LAS outfit is a standalone unit registered
through the Legendary Armour Skins module — an additive equipable, not a
character swap. Replacing a heister's model in place is the harder, more
breakable route (compare the retired Lawson character swaps). The guide is the
human (Blender) workflow; we automate the mechanical parts of the same recipe.

## How the game works (what the guide fixes)

- **Skeleton.** The PD2 humanoid rig is 54 bones: 1 pelvis/hips, 3 spine,
  L/R shoulder, arm, forearm (+ twist), hand, 3 bones per finger (thumb/index/
  middle/ring/pinky), thigh, lower leg, foot, toebase. Source rigs must be
  converted to exactly this set: merge twist/extra bones, then **rename to PD2
  bone names**. Leave engine locator/effect objects alone (`BackPack1`, `Aim`,
  `e_taser`, …) — deleting them breaks effects and interactions.
- **Weights.** Maximum **3 influences per vertex** (Blender: Weight Paint →
  Weights → Limit Total → 3, subset All Groups). Anything more misbehaves.
- **Fitting.** Scale/rotate the source to the PD2 proportions, then **pose it
  to the PD2 bind pose** (shoulders first), apply all transforms, and parent
  with Armature Deform. Proportion differences are expected; edit mesh or bones.
- **Materials.** One `.material_config` entry per Blender material, `name`
  matching the model's material names. The header takes a `group` attribute
  (free-form). `unique="true"` on contour materials is required or outlines
  bug out. Contour (wall-outline) rendering needs `CONTOUR` in the render
  template **plus** `contour_color` (vector3) / `contour_opacity` (scalar)
  variables or the outline does not render.
- **Render templates are a fixed vocabulary.** Hand-combining keywords the game
  does not support yields black materials. Attested combinations from the guide
  and the 2B reference: `generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS`
  (the standard ported-model template), `generic:DEPTH_SCALING:DIFFUSE_TEXTURE:
  NORMALMAP:SKINNED_3WEIGHTS` (first-person), `generic:DIFFUSE_TEXTURE:NORMALMAP:
  SKINNED_3WEIGHTS`, `generic:ALPHA_MASKED:DIFFUSE_TEXTURE:EXTERNAL_ALPHA_REF:
  NORMALMAP:SKINNED_1WEIGHT`. `SKINNED_3WEIGHTS` is required for anything with
  an armature.
- **First person.** A separate unit with **arms only** (nothing else), and its
  material template must include `DEPTH_SCALING` so the arms draw in front of
  world geometry.
- **Normal maps.** PD2 shaders expect the OpenGL-style Y+ convention but a
  packed channel layout: **X (red) moves into alpha**, red becomes white, blue
  becomes black (Diesel reads only A and G), green stays Y (invert green when
  the source is DirectX-style). Compress with DXT5 — every PD2 normal map uses
  an alpha channel; uncompressed costs measurable memory (32-bit, 4 GB cap).
- **Textures.** Diffuse is albedo; optional AO is multiplied into it (Photoshop
  Multiply or Blender Mix node, then baked in Cycles); metallic look is faked by
  subtracting a mask from the albedo; specular can live in the diffuse's alpha
  (save DXT5 ARGB 8bpp Interpolated Alpha — DXT1 discards alpha and the model
  turns glossy). Specialized slots: `_il` illumination (`il_multiplier`,
  `il_bloom`, named presets like `neonsign`/`identity`), `_op` opacity
  (R=Fresnel, G=opacity, B=cubemap), GSMA (R=gloss, G=specular, B=material
  mask, A=opacity) with `GSMA_ALPHA_MASKING` templates.
- **Export from Blender.** Tangents on (or normal maps break), vertex colors
  off; with the Model Tool add-on keep Apply Modifiers and Correct Axes
  unchecked.

## Build steps

Human path (guide): extract base `.model` → export `.glb` → import to Blender
(Bone Dir "Blender") → fit/pose/rename/merge → limit to 3 weights → export
`.glb`/`.model` → drop into the MOOG template → test menu preview before
touching materials (a black/grey model in the default pose means the model
loaded fine) → wire `.material_config` and textures.

Automated path (ours, `tools/pd2-port/`): `me2_dae.py` imports the rigged
source, `rig_target.py` maps bones by name (folds twists/fingers/face to parent
bones; swaps sides when the source labels `Left*` at +X) and rebinds the skin
mathematically to the PD2 bind — one **bone-segment-fit** rigid transform per
target bone (source bone head→tail aligned onto the target bone, minimal
rotation; stored frame orientations never enter, they differ per engine and
tear the mesh at joints), with folded joints sharing one transform and the
weight field smoothed over the **welded** vertex graph first —
`las_model.py` writes the DODB model (3-weight channels),
`build_las_pack.py` writes the unit/object/material_config/LAS hook and DXT5
textures. `preview_check.py report|render` verifies the transfer offline
(edge preservation, displacement spikes, twin separation, bone anchors) and
rasters source/retarget/decoded previews without Blender.

## Verification

The guide is community documentation, not an oracle; its claims above are
prescriptions. We adopted its material/normal-map/FPS rules into the Lawson
build and verified the **offline** invariants only (config↔model material
coverage, 3-weight geometry, DXT5 validity). The guide's own in-game heuristic:
load the model before editing materials — black/grey in the default pose is
success. Nothing here is game-verified by us.

## Gotchas

1. **Symptom.** Model loads with hash strings instead of names. **Cause:**
   Model Tool without the hashlist. **Fix:** drop PAYDAY-2-Hashlist into the
   Model Tool root.
2. **Symptom.** Broken/odd skeleton after GLB import to Blender. **Cause:**
   glTF Bone Dir left on Temperance. **Fix:** set Bone Dir to Blender before
   importing.
3. **Symptom.** Normal maps look wrong in game. **Cause:** missing tangent
   export, or DirectX-style green channel / unpacked X. **Fix:** Tangents on at
   export; repack normals X→alpha with R=white, B=black, green Y+ (invert if
   needed), DXT5.
4. **Symptom.** Material renders black. **Cause:** invented render-template
   keyword combination. **Fix:** use only combinations seen in game files /
   attested templates.
5. **Symptom.** Contour outline missing or bugged. **Cause:** `CONTOUR`
   template without `contour_color`/`contour_opacity` variables, or missing
   `unique="true"`. **Fix:** both, per the guide's config example.
6. **Symptom.** First-person arms clip into walls. **Cause:** FPS material
   lacks `DEPTH_SCALING`, or the FPS unit carries more than arms. **Fix:** arms
   only + `DEPTH_SCALING` template.
7. **Symptom.** Animation misbehaves on ported rigs. **Cause:** more than 3
   weights per vertex, or leftover twist bones. **Fix:** Limit Total 3, merge
   twists into their parents.
8. **Symptom.** Effects/interactions break (tase, bags). **Cause:** locator
   objects (`Aim`, `e_taser`, `BackPack1`…) deleted from the unit. **Fix:** keep
   them; they are not mesh.
9. **Symptom.** Retargeted pieces sit at mutually wrong angles ("complete
   mess") although each piece is intact. **Cause:** operators built from
   stored joint-frame orientations (`minv(W_s) @ W_t`) — per-bone frame
   conventions differ between engines and land as mesh rotations. **Fix:**
   fit bone SEGMENTS (head→tail directions) instead; frame orientation must
   not enter the transfer.
10. **Symptom.** Face/eyelid meshes tear apart during any per-vertex process.
    **Cause:** many source joints fold onto one target bone (face→Head), each
    with its own transform. **Fix:** one shared transform per target bone
    (representative = most-weighted source joint of the fold).
11. **Symptom.** Mesh shreds into per-triangle confetti after smoothing or
    welding, while per-triangle metrics look fine. **Cause:** game-ripped DAEs
    are corner-split (positions duplicated per vertex-normal/UV corner);
    index-based adjacency is blind across triangles. **Fix:** weld by position
    for any neighbour operation (smooth weights on the welded graph and
    broadcast back), and gate on twin separation (coincident vertices must
    stay coincident).

12. **Symptom.** Eyes render as blank pink spheres with no iris. **Cause:**
    ME2's eye shader placed the iris (Iris/Lens/4×spec maps are shader
    inputs); `EYE_Diff.png` draws it at the tile centre and the DAE UVs land
    that circle ON the eyeball's u-seam facing the camera — triangles
    spanning the seam smear it. `EYE_Diff_s.png` is a black mask layer, not
    an alternate diffuse. **Fix:** planar-project each eyeball's UVs from its
    frontal plane (`build_las_pack.eye_uv_planar` — static approximation of
    that shader). Diagnose with UVs-as-colour renders: a colour seam across
    the region of interest means wrap interpolation is corrupting it.

13. **Symptom.** Teeth/Mouth texture tiles look like hair art. **Cause:** the
    source head atlas `HMF_HED_PROMiranda_Scalp_Diff.png` is SHARED — its
    islands include hair AND the teeth (u≈0.002–0.159, v≈0.248–0.543, white
    teeth + pink gums) AND the mouth interior (u≈0.921–0.998, v≈0.306–0.468).
    `TEXTURE_SLOTS` mapping those meshes to Scalp_Diff is faithful. **Do not**
    "fix" it to a separate teeth texture or flag the tiles as mislabeled —
    contact-sheet tiles show the whole atlas; only per-mesh textured renders
    show what the mesh samples. Verify suspected texture bugs with a UV-box
    overlay before changing anything.

## Assets

Reference-only in this repo: `2b.rar` (working LAS pack, user-supplied), the
ME2 Miranda DAE/texture zip. The MOOG template (mod 58492) and the guide's
render-template zip are external downloads.

## Open questions

- The green-channel orientation of ripped ME2 normals (DirectX vs OpenGL) is
  not decidable offline; currently flipped by default with a build flag.
- Exact inventory of locator/effect object names an LAS outfit unit should
  carry (the 2B reference's undecoded object3Ds) — the guide only lists three
  examples.
- Whether `CONTOUR` can combine with `ALPHA_MASKED` for masked materials
  (lashes/hair cards) is not attested; such materials currently use the 2B
  template without contour.
