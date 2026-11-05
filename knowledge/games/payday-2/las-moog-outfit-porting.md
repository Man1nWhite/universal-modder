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
  `e_taser`, …) — deleting them breaks effects and interactions. The finger
  chains are not decoration: a hand whose vertices are all bound to the wrist
  bone is a mitten that cannot articulate.
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
source, `rig_target.py` maps bones by name (folds twists/face to parent bones
and maps the finger chains onto PD2's finger bones; swaps sides when the source
labels `Left*` at +X) and rebinds the skin
mathematically to the PD2 bind — one **bone-segment-fit** rigid transform per
target bone (source bone head→tail aligned onto the target bone, minimal
rotation; stored frame orientations never enter, they differ per engine and
tear the mesh at joints), with folded joints sharing one transform and the
weight field smoothed over the **welded** vertex graph first —
the triangles that this per-bone fit folds inside out are detected and
re-wound afterwards (`rig_target.repair_winding`, see gotcha 19) —
`las_model.py` writes the DODB model (3-weight channels),
`build_las_pack.py` writes the unit/object/material_config/LAS hook and DXT5
textures. `preview_check.py report|render` verifies the transfer offline
(edge preservation, displacement spikes, twin separation, bone anchors) and
rasters source/retarget/decoded previews without Blender.
`check_all.py` runs every check of the Lawson build in one command (the
audit, the winding check, the normal-map analysis, the mutation tests and
the pytest suite); the state of that work, its open problems and its traps
are written down in `tools/pd2-port/STATUS.md`.
`check_guide_compliance.py` audits the built pack against this guide's rules
(one check per rule, each citing it); it runs in the test suite, so a pack
that drifts from the guide fails the build.

## Verification

The guide is community documentation, not an oracle; its claims above are
prescriptions. We adopted its material/normal-map/FPS rules into the Lawson
build and verified the **offline** invariants only (config↔model material
coverage, 3-weight geometry, DXT5 validity). `check_guide_compliance.py`
turns the guide's rules into an automated audit of the built pack: 38 checks
pass, 1 warning (the normal maps' green-channel convention, which the files
cannot settle — see gotcha 19 — and only the game can confirm), 0 failures —
after the finger-binding fix in gotcha 14. The
guide's own in-game heuristic:
load the model before editing materials — black/grey in the default pose is
success. Nothing here is game-verified by us.

A third pass attacked the *auditor* instead of the pack: the audit is now
mutation-tested (gotcha 17), the guide text was re-read rule by rule, and the
2B reference pack was decoded field by field as an oracle (gotcha 18). The
pack's bytes did not change; the auditor gained two fixes (P2 now also
requires every shipped texture/unit to be *registered*, P3 now requires the
LAS flags to be switched **on**, not merely present).

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

14. **Symptom.** The outfit's hands are mittens: the fingers never move.
    **Cause.** The source's finger joints were folded onto the wrist bone.
    The rig contract's finger bones are hash-only (the Model Tool writes
    names only with the PAYDAY-2-Hashlist installed), so there were no names
    to map onto and every finger token was folded to the hand. **Fix.**
    Recover the names offline — the contract's hash is the lookup3 variant in
    `dmodel.hash64`, so hash PD2's naming convention
    (`LeftHandThumb1..3`, `LeftHandIndex1..3`, `LeftHandMiddle1..3`,
    `LeftHandRing1..3`, `LeftHandPinky1..3` and the Right set) and match it
    against the stored `name_hash` values (`resolve_rig_names.py` in
    `tools/pd2-port/`, 30 of 187 hash-only bones resolve); then map the
    source's finger chains one-to-one onto them (side swaps with the arms;
    ME2's "Pink" is PD2's "Pinky"). Check the result: every finger bone
    should hold vertices, and the finger-dominant vertices should sit within
    a couple of cm of their bone's origin.

15. **Symptom.** A rig contract full of `#a1b2c3d4e5f60718` names and no
    way to get the real ones. **Cause.** The Model Tool stores bone names
    only with the PAYDAY-2-Hashlist installed; without it, only the hash
    survives. **Fix.** Do not install the hashlist for this: the hash is a
    plain lookup3 over the name, so brute-force the naming convention over
    the game's own bone names and match. A name that hashes to the stored
    value is proven correct — keep the stored hash and add the name next to
    it (never edit the hash), and add a test that every named bone hashes to
    its own `name_hash`.

16. **Symptom.** The first-person view model has hands cut off at the
    knuckles, or a part of the body silently disappears from the FPS unit
    after a re-rig. **Cause.** The FPS unit is cut by *dominant* bone
    against a fixed bone list (arm, forearm, wrist). A re-rig that moves
    vertices onto new bones (here: the finger chains) moves them out of that
    list's bucket, and they are dropped from the view model — the third-person
    unit still shows them, so the pack looks fine in the preview and breaks in
    first person. **Fix.** Make the cut a rule, not a list: keep the arm cut
    in step with the rig (here `is_arm_bone` matches the finger chains too),
    and check the two units against each other — the FPS unit must carry the
    same hand/finger bones as the third-person one, and its vertex count must
    not change silently between builds.
    *Hit again, on our own pack.* The cancelled Skyrim clothing build grafted PD2 hands
    (532 finger-dominant vertices) onto a body whose viewmodel cut was still
    the fixed list `Shoulder/Arm/ForeArm/Hand/HandThumb1`: the shipped
    `fps_skyrim_outfit.model` kept 12 of them, so first person held the gun
    with stumps while third person was perfect. The cut is now the predicate
    `build_models.is_fps_arm_bone` (side prefix + `Shoulder`/`Arm`/`Hand`, and
    the finger bones all contain `Hand`), `extract_bones` accepts a predicate,
    and `tests/test_fps_hands.py` compares the two units' finger bones.

17. **Symptom.** A compliance auditor reports "all green" for a pack that
    breaks the guide in half the places. **Cause.** The auditor was only
    ever run against a good pack; nobody checked that it *can* fail, and two
    of its rules were one-directional (they checked that the registered
    files resolve, not that every shipped file is registered; they checked
    that a flag name appears in the hook, not that the flag is set to true).
    **Fix.** Mutation-test the auditor: break the pack the way the guide
    forbids and assert that the matching check fails
    (`check_guide_compliance_self_test.py`, 16/16 caught). Keep the negative
    controls too — a pre-fix pack from git history must still fail the
    check that caught it. Mutation-test the *test suite* as well
    (`check_test_suite_mutations.py`): break the shipped pack and require the
    matching pytest to fail — a test that passes or skips is a hole.

18. **Symptom.** A working reference pack's bytes look incompatible with
    yours — its weights sit in vertex channel 20 where yours sit in 19, its
    section table has different ids, it carries `animation_data`/`author`/
    `custom_hashlist` sections you do not have. **Cause.** The reference is
    a *legacy* Diesel container: its channel ids above TEXCOORD7 are shifted
    by +2, and the extra sections are stock-model metadata. **Fix.** Read it
    as a behavioural oracle, not a byte template: map the channel ids
    (legacy 15→BLENDINDICES, 17→BLENDWEIGHT0, 20/21→the two UV-direction
    streams) and compare the *structure* — flag set, unit/object/config
    shape, locator set, skin palettes — not the raw bytes. Its
    `custom_hashlist` section is a plain list of custom names, which decodes
    the whole rig without any hashlist.


19. **Symptom.** A pack passes every structural audit and still shows holes
    and black patches on the skin in game. **Cause.** The bind-pose transfer
    fits every bone piece independently, and where the two rigs disagree
    (hips, wrists, ankles) the fits end up 120-156° apart: the triangles
    between the pieces fold back on themselves and are wound inside out. The
    game culls them, so they leave holes. Neither the guide audit nor the
    preview gates looked at triangle winding, and the preview's flat colours
    cannot show a fold. **Fix.** Check the winding of every triangle against
    its own vertex normals (`check_mesh_geometry.py`, and as audit check
    `N3`), and repair it where it disagrees: the vertex normals describe the
    unfolded surface, so the winding is what is wrong — reverse the triangle
    and leave the vertices where they are. Corner-split meshes make this
    safe: no edge is shared, so flipping one triangle cannot desync its
    neighbours. Note the limits of the repair: it fixes the holes, not the
    crease, because the crease comes from the rigs disagreeing.

20. **Symptom.** The normal map's green channel has to be flipped, and there
    is no way to tell from the files which way it is. **Cause.** The
    convention is a property of the engine that authored the map, not of the
    file: an OpenGL (Y+) and a DirectX (Y-) map are equally self-consistent
    with their own image layout, and a saturated blue channel hides the
    height field that would otherwise give the answer. **Fix.** Measure what
    the files can say (`check_nm_convention.py`: they *are* tangent-space
    normal maps, and the convention is not recoverable), then fall back to
    the provenance — Mass Effect 2 is a DirectX 9 game, so its maps are Y- and
    PD2's Y+ wants them inverted. Keep the build switch either way: the
    in-game look is the final word.

21. **Symptom.** The viewmodel's hands are simply *not there* in first person
    (or render untextured), while the third-person model is correct and every
    structural audit passes. **Cause.** The fist-person unit is its own model
    with its own `fps_*.material_config`, and the two are checked separately:
    a material that the fps model references but its config does not declare
    cannot be resolved by the game, so those triangles do not draw. Ours
    carried the grafted hands' `mtr_hands` but the config listed only
    `mtr_body`/`mtr_jacket`/`mtr_jacket2`. **Fix.** Build the fps config from
    the *fps model's own* material set, not from a hand-written list
    (`FPS_MATERIALS` now includes `mtr_hands`), and assert the closure both
    ways in a test: every material hash in the model appears in its config,
    for the TPP and the FPS unit (`tests/test_fps_hands.py`). The rule is
    general — a material is only resolvable by the config of the unit that
    owns it.

22. **Symptom.** A grafted part (hands, head, anything) is *in* the model — the
    vertex count went up, the preview that reads the mesh shows it — but in game
    it is invisible, and drawing a material-tagged view shows parts of the
    *body* wearing that material instead. **Cause.** Two offset bugs, both in
    the merge, both silent. (a) `append_group` rebased a slice's vertex offset
    but not its *triangle* offset, so the appended slice's render atom pointed
    at the first triangles of the host. (b) `graft_pd2_hands` recorded each
    slice's `base_i` from `len(faces)` *after* extending the face list, so every
    slice claimed to start one slice late. A Diesel render atom is a range —
    `base_vertex`/`slice_len` for vertices, `base_index`/`tri_count` for
    triangles — and a file whose atoms do not *tile* the index stream is still
    structurally valid. **Fix.** `build_models.atom_problems` /`audit_model`
    assert that the atoms' vertex blocks and triangle runs tile the geometry
    exactly once; the build refuses to write a model that fails, and
    `tests/test_fps_hands.py` re-checks the shipped pack.

23. **Symptom.** The grafted hands sample near-black and render as dark grey
    mittens, even though the donor's texture is shipped with them. **Cause.**
    UV convention, not lighting. Every slice in the block is stored as the
    *internal* `(u, 1 - v)`; the graft wrote the donor's raw `v`, which lands the
    samples in the other half of the atlas — the half with the donor's black
    bodysuit (median 0.03 vs 0.69 for skin). **Fix.** Convert once, on the way
    in (`1 - v`), and assert it (`test_graft_uvs_use_the_internal_v_convention`).
    Also: a donor's atlas is mostly clothing. Sampling "the donor's own texture"
    is only correct if its hand islands are skin, which for 2B they are not —
    the hands' albedo is authored at the *body bake's* measured tone instead
    (`skin_texture.hand_tone_from_body`), with the normal map left flat.

24. **Symptom.** The hands hover a hand's width below the cuff, and no
    animation brings them together. **Cause.** Not an error: PD2's `Hand` bone
    is where weapons are parented, and in the bind pose it hangs well forward of
    the forearm axis, while a retargeted Skyrim sleeve ends along its own
    forearm. The offset is rigid — both ends follow their own bones — so it
    never closes. **Fix.** Move the *sleeve* (`weld_wrist`): translate the mouth
    onto the hand's opening with a falloff that runs *along* the arm (a radial
    falloff shears the cuff into a cone), then cap the cuff's opening with a fan
    that takes the mouth's own material. Caps, not a band: the two rings have
    different vertex counts and winding, and every band attempt produced a
    visible twist across the wrist.

    Three details, each of which was a visible defect on its own:

    - **Rigid shift only.** Mapping the 76-vertex cuff ring onto the 94-vertex
      hand ring vertex by vertex needs a correspondence that does not exist; the
      interpolated target wobbles round the circle and turns a round cuff into a
      jagged star of blades. Translation of the whole cuff neighbourhood is
      enough — and the cuff keeps its own seam.
    - **The cap's apex is sunk, not flat.** A fan to the centroid of a mouth
      ring that has just been dragged onto a hand is not planar: it pokes out of
      the sleeve as a pale flange. `_fan_cap` pushes the apex back along the
      *bordering faces'* inside direction (vertex normals on a garment edge point
      either way), so the cone hides inside the cuff.
    - **The hand's opening is left open.** Walked on a grafted hand its boundary
      is not one loop — neighbours are up to 10 cm apart — so a fan across it
      throws long blades well outside the cuff. Nothing can see into it: the
      cuff's own cap sits in front of the hole.

25. **Symptom.** After the wrist work a spray of flat blades stuck out of both
    cuffs, pale and clearly not part of either surface. **Cause.** A donor ships
    its hand three times — `s_body`, `g_body_lod1`, `g_body` — and the graft took
    every model whose vertices are weighted to hand bones, so the decimated LOD
    was drawn on top of the full hand. It is not *inside* the full mesh, so it
    reads as loose blades off the wrist. **Fix.** `graft_pd2_hands` skips nodes
    whose name says `lod` and then keeps only nodes with at least a quarter of
    the richest candidate's triangles (in case a donor's LODs are unnamed). The
    grafted hand went from 602 + 5101 tris to 5101, and the blades went with the
    LOD.


## Assets

Reference-only in this repo: `2b.rar` (working LAS pack, user-supplied), the
ME2 Miranda DAE/texture zip. The MOOG template (mod 58492) and the guide's
render-template zip are external downloads.

## Open questions

- The green-channel orientation of ripped ME2 normals (DirectX vs OpenGL) is
  not decidable offline; currently flipped by default with a build flag.
- Whether `CONTOUR` can combine with `ALPHA_MASKED` for masked materials
  (lashes/hair cards) is not attested; such materials currently use the 2B
  template without contour.
- Whether the forearm twist bones should carry weight: the 2B reference
  keeps `Left/RightForeArmRoll` in its skin palette, our model keeps the
  bone in the skeleton but binds no weight to it — which is what the guide
  asks of a *ported* model ("merge the twist bones down"). The forearm
  therefore does not twist with the animation.

Resolved in the third pass: the locator/effect inventory. The 2B
`custom_hashlist` decodes the rig's names, and the working pack carries
exactly five locator objects — `aim`, `BackPack1`, `eyeAim`,
`a_weapon_left_front`, `a_weapon_right_front` — the last two hanging off the
hands (they are the weapon sockets, not thumb tips). Our model carries the
same five, and the audit now checks them by name.

26. **How LAS itself handles hands** (read off the mod, not guessed). A LAS
    outfit keeps the hands *inside its own unit*: `units/.../pool_repair_suit`
    declares `mtr_body`, `mtr_hands` and — first person only — `mtr_arms`
    pointing at `units/payday2/characters/shared_textures/fps_wrist_female_1_*`,
    i.e. a bare-wrist skin map between the sleeve and the glove. The cop
    outfits go further and ship the whole body (`g_body`, `g_armor_*`,
    `g_throat`, `g_neck`, `s_body`) with `replace_body = true`, so nothing of
    the stock heister survives. Either way there is never a *seam*: the sleeve
    overlaps a skin arm, and the skin material is what shows in the opening.

    Two consequences for a ported outfit:

    - Cap the sleeve mouth in **skin**, sampled from the hand's own UVs, not in
      the mouth's garment material. `weld_wrist` did the latter (on the theory
      that a stitched seam takes the cloth), and because the cap samples the
      garment's *inner* layer it came out white lace at both wrists.
    - Do **not** try to borrow the donor's forearm and let the sleeve overlap
      it. A donor's skin arm is bound to PD2's `ForeArm` in PD2's bind pose,
      which sits 20 cm off the hand and does not follow a retargeted Skyrim
      sleeve; the seam just moves up to the elbow. Grafting hands and welding
      the cuff is the only arrangement that holds on a ported body.

27. **Changeable gloves via the vanilla glove adapter — the mechanism is right,
    but it did NOT render in-game; graft is the shipped default** (2026-11-03,
    read off `Vladik268/P2` = LAS 4.1.9 + BeardLib, and the decompiled vanilla
    Lua in `AzureeDev/payday-2-luajit`; the Skyrim build only).

    **Empirical outcome (overrides the theory below):** the adapter route — even
    with the corrected `default_glove_id = "heist_default"` compat hook, and even
    though it passes a LuaJIT behavioural test that executes the *verbatim* LAS
    loader — produced **neither the glove unit nor the `hnd_forearms` adapter
    in-game** (main menu + blackmarket preview both showed bare, handless cuffs).
    The in-game spawn path evidently differs from the modelled one (hook timing,
    or the preview not invoking `set_beardlib_character_visual_state`'s glove
    block), and it cannot be verified without launching the game. **So the
    shipped default is `--hands graft`** (note 26): PD2 hands grafted into the
    mesh + cuff welded, which always render. The adapter route is kept as an
    option and the mechanism notes below are still the correct *theory* of how
    vanilla suits do it — but do not ship it as the default until it is confirmed
    in-game. The lesson: a faithful offline simulation of the *tweak-data* chain
    is necessary but not sufficient; the *unit-spawn* chain must be confirmed in
    the actual game.

    Note 26 concluded the graft was the only arrangement that holds. That is
    true for a *donor* forearm, but it missed the arrangement the base game
    itself uses: **ship no hands at all and let the vanilla glove + the
    `hnd_forearms` glove adapter supply them.** The adapter is bound to the
    *same PD2 skeleton* the outfit retargets onto, so it follows the sleeve —
    exactly the property the donor forearm lacked. This is how every DLC/Infamy
    suit keeps gloves changeable.

    - **Vanilla semantics — hands come from a REAL default glove, not from
      stock hands.** `playerstyletweakdata.lua` gives the suits
      `body_replacement_standard` (`hands/arms = true` — stock hands HIDDEN);
      `glovestweakdata.lua` sets `suit_default_gloves[style] = "heist_default"`
      for most suits, and BeardLib's `BeardLibInitGloves` PostHook copies that
      into `player_styles[style].default_glove_id`. So "Default" gloves resolve
      through `default_glove_id` to a real glove unit
      (`hnd_glv_heistwrinkled`) — `gloves.default` itself has NO unit. The same
      file defines the adapter
      (`unit = units/pd2_dlc_hnd/characters/hnd_forearms/hnd_forearms`,
      per-heister `character_sequence`, `player_style_exclude_list =
      {"none","slaughterhouse"}`). BeardLib's
      `set_beardlib_character_visual_state` spawns `char_gloves` (the hand
      mesh) iff a glove unit resolves, plus `char_glove_adapter` (the bare
      forearm) unless glove/style adapter data is `false`. "Vanilla hands" =
      real default glove unit + adapter, with stock hands hidden.
    - **LAS 4.1.9 loader bugs — TWO fresh-table reads, both no-ops.**
      `hooks/outfits/loader.lua` does `output.glove_adapter = output.glove_adapter
      or false` AND `output.default_glove_id = output.default_glove_id or false`
      reading the *fresh* `output` table (not `data.*`), so both are always
      false, and it force-inserts every `replace_body`/`replace_all` outfit into
      `glove_adapter.player_style_exclude_list`. Config-only flags therefore do
      nothing. **`default_glove_id = false` is the killer:** BeardLib's
      `get_glove_value` returns `false` for "Default" gloves when the style's
      `default_glove_id` is `false` → no glove unit spawns, while
      `body_replacement.hands = true` hides the stock hands → **NO HANDS AT
      ALL** (shipped once on the Skyrim build; the adapter forearms alone do not
      compensate — stock hands do not render on a replaced body).
    - **The fix is a compat hook that restores the vanilla mechanism.**
      PostHook `BlackMarketTweakData:init` (runs after LAS's loader): set
      `player_styles["las_<id>"].default_glove_id = "heist_default"` (custom
      gloves stay selectable — the default only applies to "Default"), set
      `glove_adapter = {}`, reverse-loop `table.remove` the style from
      `glove_adapter.player_style_exclude_list`, and KEEP
      `body_replacement.hands = true` + `third_body_replacement.hands = true`
      (the spawned gloves supply the hands; unhiding stock hands risks doubles
      and does nothing on a replaced body). **`{}` not `true`:** BeardLib's
      `set_beardlib_character_visual_state` does `table.merge(final,
      gloves_adapter_data or player_style_adapter_data or {})` and BeardLib's
      `table.merge` calls `pairs(new_table)` — a boolean raises `pairs(true)` and
      crashes. `{}`/nil keep the default `hnd_forearms` adapter; `false` disables.
    - **Test the chain, not the strings.** The first adapter pack passed every
      string-assertion test because the offline smoke test stubbed the host
      with the wrong assumption ("default gloves returning false is fine").
      The regression suite now EXECUTES the verbatim LAS loader
      (`tests/fixtures/las_loader_4.1.9.lua`) plus the generated hooks inside
      LuaJIT 2.1 (`lupa`), against faithful ports of BeardLib's resolution
      code, and asserts a glove unit actually spawns for Default AND custom
      gloves in FPS and TPP — plus a no-hook control that must reproduce the
      no-hands bug (`tests/test_glove_behavior_lua.py`).
    - **FPS comes for free.** BeardLib moves to `unit:camera():camera_unit()`
      for the local peer and spawns `char_gloves`/`char_glove_adapter` there, so
      the gloves show in first person without shipping any FPS hand geometry.
      Fallback if a heister's camera-unit gloves ever fail: an FPS-only graft.
    - **When to prefer which.** Adapter route when the ported body already ends
      at the wrist (the Skyrim 3BA does) and you want changeable gloves;
      graft + weld (note 26) when the outfit must own the hands outright (cop
      suits, full character replacements) or the sleeve/hand seam must be
      skinned as one. The adapter trades a skinned cuff for an open sleeve mouth
      the adapter forearm fills — verify the cuff in motion in game.

28. **Axial-vs-radial retarget scaling distorts a ported body's neck and bust**
    (2026-11-03, measured on the Skyrim 3BA → PD2 clothing port). A
    similarity/axial retarget that matches the target's bone lengths does *not*
    preserve the source's soft-tissue proportions, in two predictable ways:

    - **The bust flattens relative to the torso.** The spine chain is stretched
      *axially* (rank-1 scale along each segment) to reach PD2's longer torso,
      but the bust is *radial* — breast helper bones fold into `Spine2`, so the
      bust only receives the smaller global similarity scale. Measured: source
      bust protrusion / torso length = **0.640**, after retarget **0.485** (~24%
      flatter). Fix: scale the front chest's forward protrusion back up by the
      ratio (≈1.32), proportional to each vertex's existing forward offset and
      with a smooth height falloff so it blends into waist and collar without
      tearing (`build_models.restore_bust`). Apply to body **and** shadow.
      **Also add a *lateral* falloff** (full near the centreline, fading to zero
      before the underarm): pushing the whole front width pulls the chest panel
      away from the sleeve and opens a visible armpit gap. Confine the push to
      the centre bust (|x| ≲ 10–15 cm here) and leave the sleeve/torso seam put.
    - **The neck lands forward of the target's head.** A body authored for a
      *separate* head (Skyrim 3BA) keeps its neck opening positioned for that
      head's bind pose; after retarget it can sit at Head-bone height but several
      cm *forward* of the target's Head bone, jutting past the chin. If the outfit
      ships no head (LAS keeps the heister's), that stub is a duplicate neck —
      fold it down into the collar (`build_models.trim_neck`) and let the
      heister's own neck show above.
    - **General rule:** after any retarget, measure soft-tissue landmarks (bust
      protrusion, neck opening) against *both* the source and the target rig —
      "every joint lands on target (0.00 cm)" says nothing about the flesh
      between the joints. Both fixes are continuous vertex edits (no re-topology),
      so they cannot introduce holes; verify with the orientation-break count.
    - **The underarm sliver is skin *through* the jacket, not an open seam.** A
      jacket-only render shows the blazer fully covers the underarm (no hole); a
      skin=red render plus a per-pixel depth test (skin depth vs jacket depth)
      prove the thin pre-existing sliver is skin poking through the jacket surface
      along the overlap seam, plus a little genuine gap in the overlap. Diagnose
      gap vs poke-through with a depth test before choosing a fix — they need
      opposite treatments.
    - **Gentle fix — tuck the skin, not the jacket.**
      `build_models.tuck_underarm_skin` pushes the near-jacket skin inward along
      its own normal (≈0.7 cm, smooth proximity falloff, confined to the underarm
      band), body + shadow. This removes the poke-through bulk without touching
      the jacket; a thin overlap-gap residue remains for the in-game check.
    - **Dead ends — do not retry:** (1) welding the panel *overlap* seam shut
      (zipping the torso/sleeve boundary chains coincident, average position +
      weights) **distorts the sleeve into spikes and widens the gap** — the sleeve
      edge *overlaps* the torso edge (~3.7 source units lateral), it is not a
      meet-seam, and the overlap is load-bearing. (2) A stronger skin tuck and
      (3) tucking along the **jacket** normal instead of the skin normal both
      distorted the skin and *increased* the poke-through (depth-test pixel counts
      rose). The gentle skin-normal tuck is the best gentle outcome; closing the
      residue fully is a re-drape / re-authoring job, not a vertex nudge.

29. **A "stray ornament" on the back may be the source outfit's own decoration**
    (2026-11-03, a cancelled Skyrim SE 3BA blazer → PD2). The row of
    medallions that appeared on the ported upper back was **not** a retarget or
    UV bug: the source `Jacket_diffA` atlas paints a ceremonial collar band
    (7 medallions over beige tabs, atlas v≈0.66–0.77), and the source NIF has the
    same 394 collar/yoke verts UV-ing into it — a 1:1 port. In the source outfit
    the white V-lapel hides the band from the front; after the retarget it lands
    on the back yoke where nothing covers it, so it reads as an artifact.
    **Before "fixing" an artifact, locate it in the source atlas and count the
    source verts that sample it** — if the source carries the same decoration it
    is intentional design, and the choice is to keep it (source fidelity) or
    paint it out (a deliberate design change), not to hunt for a nonexistent
    retarget bug. To paint it out: a luminance gate isolates the ornament from
    the dark collar (fill with the collar's sampled base colour) and reset the
    gated normal texels to tangent-flat to drop the matching bump relief
    (`skyrim_materials.remove_collar_decoration`). Do it in the texture build,
    not on the packed `.texture`, so it stays reproducible; geometry untouched.
    Watch the UV convention when locating the band: NIF `v` is from the bottom,
    the atlas image row is from the top (`v_top = 1 − v`).

30. **Skin blotches need ALL THREE of albedo, normal and gloss made uniform —
    fixing only normal+gloss is not enough** (2026-11-03/04, Skyrim clothing legs).
    In-game the thighs/calves had large camo-like patches. The first fix flattened
    the normal map and made the gloss uniform, but the blotches PERSISTED, because
    a third source remained: the **albedo itself**. `build_diffuse` had been
    layering large-scale structure into the diffuse RGB — a low-frequency fbm
    mottle, a curvature/occlusion term, and an `_anatomy_shading` pass that painted
    knee/shin/ankle bands. Each is only a few percent, but they concentrate into
    broad leg patches that the game's lighting reads as blotches. The offline
    diffuse preview looked smooth because it did not amplify the subtle variation.
    **Definitive fix: ship a UNIFORM albedo (flat base tone), a flat normal map and
    a uniform gloss** — skin at heister distance is a tone, and the geometry
    normals + game lighting supply all the shading. Diagnose by decoding the actual
    packed `.texture` and amplifying the deviation from the mean colour (×6): large
    patches jump out even when per-channel std is only ~6/255. Do NOT trust the
    un-amplified offline preview, and do not stop at normal/specular — check the
    albedo too. (`skin_texture.build_diffuse` / `build_normal`.)

31. **A ported garment's overlap armhole opens into a hole under the arms-down
    idle; keep the sleeve shoulder weighted to the torso** (2026-11-03,
    Skyrim clothing blazer). The blazer armhole is an *overlap* (sleeve fabric
    lapped over the torso), not a sewn seam — hundreds of boundary edges in the
    shoulder band. In the bind pose (arms out) the overlap covers the armhole;
    when the arms adduct in the idle, the Arm-weighted sleeve shoulder rotates
    away from the torso-weighted armhole edge and the overlap opens into a hole
    that backface culling exposes. Welding the overlap edges was tried and
    rejected (it distorts the sleeve into spikes). The safe fix is a **weight
    stay**: in `transfer_group`, for jacket verts in the shoulder band, blend up
    to ~45 % of the upper-arm weight into the clavicle with a smooth height
    falloff, so the sleeve top follows the torso and the overlap stays closed.
    Verify with an offline **pose simulator** that re-skins the body with the arms
    adducted (`tools/pd2-las/pose_preview.py`): the static bind-pose preview cannot
    show a deformation-only hole. The simulator now **backface-culls** by default
    (`preview_textured.render(..., cull=True)`; `--no-cull` to disable), so it
    reproduces the in-game see-through hole instead of filling it with the far
    side of the fabric. Culling sign is pinned by `tests/test_preview_cull.py`
    (front face survives, back face dropped, view-relative) — an inverted sign
    culls the whole outfit and reads as a blank gray figure.

    **The stay has a balance, not a "more is better" knob.** ~45 % is the sweet
    spot: the large overlap hole closes to a small armpit notch. Pushing it harder
    (55 % with a plateau falloff across the whole band) was measured and is WORSE —
    the sleeve shoulder then stays with the torso while the skin upper arm still
    follows the arm bone, so the sleeve pulls away and a large patch of **skin**
    shows at the armpit. Too little stay opens a see-through hole; too much exposes
    the skin arm. Do not strengthen past the balance to chase the last notch. The
    small residue that remains (armpit notch, shoulder-top spots near the collar)
    is the genuine overlap gap / skin poke-through that `tuck_underarm_skin`
    already documents as un-closable without distorting the sleeve.

32. **White patches on a dark sleeve are usually the under-layer garment, not
    skin — probe the material's FULL extent before concluding** (2026-11-04,
    Skyrim clothing blazer). After the uniform-albedo fix the legs were clean but
    white upper-arm patches remained in-game. An earlier probe had checked
    `mtr_jacket2` only at z>140, found zero verts, and wrongly concluded the
    patches were skin. The band was too high: the white **shirt sleeves** sit at
    z 124.6–130.6, |x| 30–50 (2016 verts, 100 % arm-weighted), *below* the
    shoulder-stay band. They are the shirt under the blazer, poking through /
    z-fighting the blazer sleeve once the game skins the arms. **Fix:
    `tuck_shirt_sleeves`** — push jacket2 verts in the upper-arm band inward along
    their normal (up to ~1.6 cm, smoothstep falloff to the nearest blazer vert),
    raising the shirt↔blazer separation (mean 1.09 → 1.75 cm) so the shirt stays
    hidden; leave the visible collar/lapel (small |x|) and the blazer untouched,
    and cap the amount so the shirt is not pushed through the arm skin beneath
    (that would just swap white patches for tan). Two lessons: (a) when a white
    patch survives an albedo fix, look for a white *under-layer mesh* in the same
    region and measure its real z/|x| extent — do not assume skin; (b) the offline
    rigid-arm pose sim may NOT reproduce in-game poke-through/z-fighting even with
    an elbow bend, because the game's skinning brings near-coincident layers closer
    than the sim does — validate such a fix **geometrically** (layer separation
    increased, no skin clipping) rather than by reproducing the defect offline.
    The wrist white ring is the same shirt cuff; the tuck band covers it, but a
    residual cuff→glove gap is inherent to the adapter route (no authored hands).

33. **A cuff at a sleeve *opening* must retract ALONG the limb, not just inward**
    (2026-11-04, Skyrim clothing wrist). After the radial shirt-sleeve tuck (note 32)
    the upper-arm patches were gone but a white ring remained at the wrist: the shirt
    cuff is a ring of 100 %-`ForeArm`-weighted verts sitting exactly at the sleeve
    opening, where there is no blazer beyond it to hide behind, so a radial (inward)
    tuck cannot hide it. **Fix: `tuck_shirt_cuffs`** — slide the cuff verts up the
    limb along the measured wrist->elbow axis *and* project them onto that axis and
    pull them toward it. The axis projection matters: sliding along the axis alone
    keeps the cuff at its original radial offset (on the blazer tube's edge, still
    peeking out); pulling toward the axis seats it inside the tube. Verify the layer
    order numerically — cuff radial distance must land BETWEEN the skin radius and
    the blazer radius (here 2.58 < 2.89 < 3.31 cm) so it is over the skin and under
    the blazer, not clipping either. Validate with a before/after render of the
    opening (visible shirt area shrinks) and a profile render of the limb (no
    poke-through). A little shirt may still show up through the opening at the exact
    limb-vertical angle, and the cuff->glove gap remains inherent to the adapter
    route — do not author hands to close it.

34. **Identify a poke-through layer by highlighting EACH material in a POSED render
    before fixing it — white patches under a dark garment can be skin, not the
    under-layer shirt** (2026-11-04, Skyrim clothing arm). White arm patches survived
    two cycles of shirt (`jacket2`) tucks. A posed render with `mtr_body`=GREEN showed
    green exactly at the patches while `mtr_jacket2`=RED showed only the collar: the
    patches were **arm skin poking through the blazer**, not the shirt. Exposed skin
    can read *white* in-game from lighting even with a uniform tan albedo — do not
    assume "white = shirt". Diagnose by rendering the actual in-game-ish pose
    (adduction + elbow bend) with one material overridden to a flat color at a time;
    the rigid bind-pose preview hides deformation-only poke-through. Then check the
    fix's COVERAGE: a nearest-jacket probe found the existing underarm skin tuck
    (band z 137–154) missed 837 poke-through skin verts down the upper-arm sleeve at
    z 125–137. Extending the band's `z_lo` to 125 (same gentle 0.7 cm skin-normal
    amount — stronger tucks distort, see note 31) cut the posed skin=green area from
    large patches to two thin slivers at the genuine overlap gap. Re-verify with the
    same material-highlight render after the fix.

35. **A ported neck must be RECENTERED and TAPERED onto the target head-neck axis, not
    just squashed — and verified with the reference head attached offline**
    (2026-11-04, Skyrim clothing neck). The outfit showed a horizontal skin shelf across
    the front of the neck base plus a notch behind it. Measuring cross-sections (plane
    / triangle intersections, welded by rounded position) showed why: the source skin
    neck is a *wide* tube (axis y≈9.5, diagonal opening rim centroid y≈13.6) while the
    PD2 head's own neck is *thin* (axis y≈7.5, radius ~2.5 @z158 / ~3.1 @z159, starting
    z≈157). A vertical-only squash (`trim_neck`) collapses the wide stub into a
    forward-offset pancake at the collar line — it never moves the opening, so the cap
    sticks out in front of the neck and leaves a gap behind. The fix (`align_neck`)
    blends skin verts above the shoulder line from the source axis onto the target axis
    while tapering the radius to *inside* the head-neck radius, so the column, the folded
    stub and the cap all hide inside the heister's own neck and the visible seam is where
    the surfaces cross. Gate the blend radially (smoothstep in z × smoothstep in radius)
    so the outer shoulder / upper-arm skin is untouched and prior tucks are not silently
    changed. Attach the template head as an offline fit reference (never ship it) and
    render front / side / three-quarter close-ups to confirm the shelf and notch are gone
    and the cap footprint lies inside the head-neck cross-section. Do not reweight the
    neck to the Neck bone for a *position* fix: the visible neck base sits below the Neck
    pivot, so torso weighting (like the collar) is correct and avoids collar gaps.

36. **A white ring at the sleeve opening / wrist is usually SHIPPED hand geometry, not the
    shirt cuff — enforce the adapter hand route with a build-time guard**
    (2026-11-04, Skyrim clothing forearms). The "forearm" defect (white wrist ring between
    blazer sleeve and game glove, plus tan hands) was a regressed pack that carried a
    `mtr_hands` slice: source/graft hands whose wrist stub reaches below the blazer sleeve
    end (sleeve z117.7, hands z112) and protrudes as a white ring. Diagnose with a posed
    per-material highlight render (the wrist ring lit up as its own material, distinct from
    `mtr_body` forearm and `mtr_jacket2` cuff). The adapter route must ship NO hands: the
    heister's stock hands / gloves + the vanilla `hnd_forearms` adapter are the only hands
    visible. Verify the body forearm and shirt cuff both end *inside* the blazer sleeve so
    the sleeve mouth is cleanly filled by the game adapter once the hands are gone. Guard
    the route in the builder: count verts with >0.5 summed weight on any `LeftHand*` /
    `RightHand*` palette bone (`count_hand_verts`) and abort the build if nonzero in adapter
    mode — forearm verts that merely blend a little hand weight stay under the threshold.
    Re-verify by decoding the SHIPPED zip (not just the build tree): a stale/graft zip can
    differ from a clean rebuild, so always confirm the packed `.model` has no `mtr_hands`.

37. **Match an outfit's authored body-skin tone to the HE head it pairs with, by sampling
    that head's diffuse — not a generic reference swatch** (2026-11-04, Skyrim clothing skin
    colour). The exposed body skin (neck / chest / legs) read too light & pink against the
    heister head at the seam because the flat body albedo base was sampled from a *different*
    character's face swatch. Fix: decode the paired head's diffuse (e.g.
    `miranda_head_df.texture`), skin-mask it (warm R>G>B, mid luminance, moderate R−B) and
    take the per-channel median; set the body bake base tone to exactly that (unity gain) so
    body and head match under the same game lighting. Verify by decoding the SHIPPED body
    diffuse and comparing its skin-island median to the head median (should be within ~1/255),
    and pin it with a regression test (base tone within ±4/255 of the head median) so future
    tone tweaks cannot drift the seam. Remember the body skin is a *flat* albedo (geometry
    normals + game lighting supply shading), so matching albedo medians is the correct target.

38. **When a ported neck sits forward of the head, TURN the whole body mesh rather than
    tapering/hiding the body neck — hiding it leaves the collar unsupported**
    (2026-11-04, Skyrim clothing neck redo; supersedes the taper half of note 35). The
    recenter+taper+fold approach (note 35) looked fine offline but in-game left a hard
    head/body seam at the collar, tan skin "wings" above the collar back, and an unsupported
    standing collar: hiding the body neck inside the head removes the surface that should
    fill the collar opening. The accepted fix is a RIGID whole-body pitch (`turn_body`,
    ~0.8° about the ground pivot z=0) that swings the neck column back onto the head-neck
    axis while keeping the feet planted, with the body's own neck left at full height to
    rise and meet the head and fill the collar. A rigid rotation preserves all earlier
    seams/tucks and cannot tear; verify with the reference head attached (front/side/back)
    that head→neck→collar is continuous and the collar back shows no skin wings. Prefer
    rigid whole-body alignment over local neck surgery when the offset is a global
    placement error; reserve local tapers for genuine thickness mismatches.

39. **A white wrist ring that survives hand-removal is the SHIRT CUFF poking radially out of
    the sleeve mouth — retract it harder AND overlap the glove with the outer sleeve**
    (2026-11-04, Skyrim clothing forearms redo). After dropping shipped hands (note 36) the
    white wrist ring + a sleeve→glove gap persisted in-game. A posed render with a stand-in
    glove (template hand tinted blue) showed the white `jacket2` cuff protruding *radially*
    at the blazer sleeve opening, and the blazer stopping short of the glove. Two-part fix:
    (a) strengthen the cuff retraction (slide further up the forearm axis AND pull further
    toward the axis so it clears the sleeve's inner radius, not just its edge); (b) lengthen
    the OUTER (blazer) sleeve down the forearm axis with a smooth falloff so it overlaps the
    game glove / forearm adapter and closes the junction. Diagnose wrist defects with a posed
    render plus a stand-in glove, because the glove/adapter is a game asset absent from the
    outfit model — without it the junction gap is invisible offline. Garment-only changes;
    never author hand geometry to bridge a wrist gap.
