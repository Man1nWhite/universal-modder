# Audit and restart — retire the old-model route, rebuild on Legendary Armour Skins

**Date:** 2026-10-18

**Baseline:** `3c5c413203037aa9012d7faf03f0897536e1bba0` (single "Add files via upload" commit; working tree clean)

**User direction this audit records:**

1. `2b.rar` is the example of what to make: an equipable, additive full-body outfit
   (a Legendary Armour Skins registration), not a character swap.
2. Changing character models directly is a bad idea. The Legendary Armor (LAS)
   route is easier.
3. Delete everything built with/for the old model — it is a dead end.
4. Start anew from `PC _ Computer - Mass Effect 2 - Non-Playable Characters -
   Miranda Lawson (Romance).zip`.

This supersedes the product direction in the two earlier audits
([repository audit](2026-10-18-repository-audit.md),
[current-checkout audit](2026-10-18-current-checkout-audit.md)). Their technical
findings about the toolkit remain accurate; their Lawson-pack recommendations are
moot because those packs are being deleted. No game runtime was available; every
conclusion below is offline evidence or user runtime report.

## Verdict

**The repo is two things bolted together: a general-purpose modding toolkit
(`um/`, `skills/`, `knowledge/`, `examples/`, docs) and a PAYDAY 2 Miranda Lawson
asset pipeline (`tools/pd2-port/`, `dist/`, and the loose asset folders).** The
toolkit is healthy (217 tests passing at the last full audit). The Lawson
pipeline is a dead end in its current form and is retired by this audit:

- The **character swaps** (`lawson_clover` / `lawson_bonnie` / `lawson_sydney`)
  replace a heister's model in place. User runtime evidence in
  [`tools/pd2-port/MODLOG.md`](../../tools/pd2-port/MODLOG.md): the Clover swap
  loads but the mesh is a "complete mess"; this is direct model surgery on
  another character's rig and it shows.
- The **outfits** built on the same machinery (`lawson_outfit`,
  `lawson_outfit_BeardLib`) crashed at `spawn_unit` in the user's game and
  inherit the same rigged-to-Clover geometry.
- The shared root cause: the old source (`Lawson model/Lawson_strip.obj`) was a
  bare, un-rigged mesh that had to be force-fitted onto Clover's skeleton with
  heuristics (`rig_lawson.py`), with known UV-seam loss and arm-mirroring
  defects (audits A08, and the MODLOG rig findings).

The replacement route is exactly what `2b.rar` demonstrates: a **standalone
Legendary Armour Skins add-on** — own units, own FPS units, whole-body
replacement flags — assembled around a *properly rigged* source model.

## What `2b.rar` establishes (the product contract)

17 files, 36,415,621 uncompressed bytes. Independently listed and extracted
(this session, `node-unrar-js` 2.x; extraction stayed in `/tmp`, not in Git).
Root `2B - LAS/`:

| Piece | 2B pack | Role |
|---|---|---|
| `main.xml` | `<table name="2B" image="guis/dlcs/2b/armor_skins/twobee">` with `Localization`, `Hooks`, `AddFiles` | BeardLib manifest |
| `hooks/matthelzor_based_awedsy_2b.lua` | `LegendaryArmours.twobee = { category, unit, fps_unit, hide_mask=true, hide_armor=true, replace_all=true, fps_hide_armor=true, fps_replace_body=true }`, hooked on `lib/tweak_data/armorskinstweakdata` | the LAS registration |
| `localization/english.txt` | `bm_menu_twobee_armor_skins`, `bm_askn_twobee`, `bm_askn_twobee_desc` | menu strings |
| `AddFiles` | `<texture>` icon, `<df_nm path="units/2b/skins/2b/base"/>`, `<unit_mat>` for `2b` and `fps_2b` | resource registration |
| `assets/units/2b/skins/2b/` | `2b.unit/.object/.model/.material_config`, `fps_2b.*`, `base_df.texture`, `base_nm.texture` | TPP + FPS units |
| `assets/guis/dlcs/2b/armor_skins/twobee.texture` | menu icon | |

Details worth copying and worth not copying (from the earlier audits and re-checked
here):

- **Copy:** the registration shape, the flag set, unit/object/material layout,
  `shadow_caster` material present in both material configs, `unit_mat`
  registration, consistent `Hooks` directory casing (the 2B archive itself mixes
  `Hooks`/`hooks` — do not imitate), standard JSON localization (2B uses a JSON
  body in a `.txt`).
- **Do not copy:** empty `*.cooked_physics` payloads (2B ships two 0-byte files).
  BeardLib's `unit_mat` shortcut supplies its own default cooked physics; ship
  none rather than ship empty ones (decision carried over from the MODLOG repair).
- **Do not copy:** the unregistered `ss.model` sidecar (3.9 MB of duplicated
  geometry never referenced by the manifest).
- The 2B `.model` files are **legacy** Diesel containers (not DODB), with
  channel-layout quirks the local parser does not fully read (audit A06). They
  are a behavioral oracle, not a byte template.

### Skeleton contract decoded (new this session)

Brute-forcing `hash64` name hashes in `2b.model` decoded the skeleton an LAS
unit must carry — the standard PD2 biped:

```
root_point
Hips ─ Spine ─ Spine1 ─ Spine2 ─ Neck ─ Head
     ├ LeftShoulder ─ LeftArm ─ LeftForeArm ─ LeftForeArmRoll ─ LeftHand (+finger chains)
     ├ RightShoulder ─ RightArm ─ RightForeArm ─ RightForeArmRoll ─ RightHand (+finger chains)
     ├ LeftUpLeg ─ LeftLeg ─ LeftFoot ─ LeftToeBase
     └ RightUpLeg ─ RightLeg ─ RightFoot ─ RightToeBase
```

Drawables: `s_body`, `g_body_lod1`, `g_head_lod1`, `g_body`, `g_head`.
Materials: `shadow_caster`, `mtr_body`, `mtr_head` (+ LOD materials).
This answers the old open question of what skeleton an outfit unit animates on,
and it is the rig target for the restart.

## The new source

`PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson
(Romance).zip` (tracked at repo root; from The Models Resource naming):

- `Miranda Lawson (Romance) - Vanilla.dae` and `... - Adjusted Version.dae` —
  COLLADA, **fully rigged and skinned**: 124 nodes, 8 geometries (Body_1,
  Body_2, Face, Hair, Eyes, Eyelashes, Teeth, Mouth_Inside), 8 skin controllers
  with real weights.
- Full ME2 facial biped: `God/root/LowerBack/Chest…`, collars/arms/fingers with
  twist bones, `Pelvis/LeftHip/RightHip` legs, facial chains (brow/eye/lip/jaw/
  tongue), IK targets.
- 34 textures (face/scalp/body/limbs/eyes/lashes, diffuse + normal + specular)
  plus `Texture Setup.txt` naming the intended slots.

This is categorically better input than the old OBJ: weights and a real skeleton
exist, so skin transfer can be a **mathematical rebind** (`v' = Σ wᵢ ·
(bone_pd2 · bone_me2⁻¹) · v`) instead of the positional heuristics that wrecked
the old model. Unmapped twist/facial joints fold into parent bones.

## Inventory and deletion boundary

Deleted as the old-model dead end (assets, packs, and code that exists only to
build/repair them; all recoverable from `3c5c413`):

| Deleted | Why |
|---|---|
| `Lawson model/` (OBJ + textures) | the old model itself |
| `LawsonME2/` | stub folder of an abandoned restart |
| `Bonie/`, `Sydney/`, `clover/` | character-swap workspaces built from the old model |
| `dist/lawson_{clover,bonnie,sydney}.zip` | character swaps (the "changing models directly" route) |
| `dist/lawson_outfit.zip`, `dist/lawson_outfit_BeardLib.zip` | outfits built on the old model/rig |
| `tools/pd2-port/{rig_lawson,build_model,build_character,build_package,build_package2,build_outfit,build_outfit_beardlib,outfit_model,repair_skin_palettes,package_metadata,glb_export}.py` | old-source rigging, model surgery, character packaging, old-pack repair, old-workspace GLB dump |
| `tests/{test_outfit_pack,test_outfit_beardlib_pack,test_pd2_packages}.py` | test the deleted builders |

Retained deliberately:

| Kept | Why |
|---|---|
| `2b.rar` | the product/format reference |
| `PC _ Computer … Miranda Lawson (Romance).zip` | the new source of truth |
| `l4d2_miranda_lawson_1.zip` | third-party Source-engine reference (GameMaps.com download, Rochelle reskin), **not** part of the old-model lineage; flag if it should go too |
| `tools/pd2-port/dmodel.py`, `dds.py` | generic Diesel model / DDS libraries (audited defects A05/A07 still apply and are fixed on the new path) |
| `knowledge/games/payday-2/*.md` | field notes (durable knowledge, not model material) |
| `docs/audits/*` | audit trail |
| `tools/pd2-port/MODLOG.md` | journal of the retired route (kept as record, banner added) |

## Restart plan (the new pipeline)

`tools/pd2-port/` gains a clean, source-driven pipeline. No step depends on the
deleted workspaces or an external `pd2-work` tree:

1. **`me2_dae.py`** — COLLADA importer: meshes, materials, skin weights, joint
   hierarchy with bind transforms. (Done in this restart; synthetic-fixture
   tests.)
2. **`reference/las_rig.json` + `extract_las_rig.py`** — the PD2 biped rig
   contract (names, hierarchy, bind matrices, palette layout) extracted from the
   user-supplied `2b.rar` model. Functional skeleton data only; no 2B mesh or
   texture art is copied into the tree.
3. **`rig_target.py`** — ME2→PD2 bone mapping (explicit table; every DAE joint
   must map), weight folding (twists/fingers/face → parent bones), and
   bind-pose skin transfer to the PD2 rig.
4. **`las_model.py`** — DODB `.model` authoring (geometry/topology/skinbones/
   materials/object3D), carrying forward the proven serialization from
   `build_model.py` with the audit fixes (0-based local palette indices, no
   false 65,535-index trimming, `shadow_caster` present).
5. **`build_las_pack.py`** — assembles `dist/lawson_las.zip`, root
   `Lawson_LAS/`, on the 2B contract: `main.xml`, `hooks/lawson.lua`
   (`LegendaryArmours.lawson`), localization, TPP + FPS units, DXT5 `.texture`
   pairs with full mip pyramids.

### Open risks (carried into the restart)

- **Release gate — provenance (A12), unchanged.** ME2 ripped assets and the 2B
  reference have no redistribution grant. Fine for private use; blocks any
  public release regardless of build quality.
- **Bind-pose transfer quality.** The rebind formula assumes source/target bind
  poses are comparable. It is principled and inspectable, but shoulder/hip
  alignment still needs in-game verification. The old route's failures were
  worse and unfixable in kind (no weights to transfer).
- **Runtime evidence.** Nothing here is game-verified. Same protocol as before:
  menu preview first, fresh logs on crash, offline heist only after the preview
  works.
- **Audits A03/A04/A05/A07/A11/A13** (toolkit-level backup traversal, shared
  validator gaps, index-count rule, BC3 decoder, publish lint, win-driver focus
  behavior) remain open and unchanged by this restart; the new pipeline avoids
  the shared validator/normalizer path rather than inheriting it.
