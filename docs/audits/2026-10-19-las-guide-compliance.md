# LAS/MOOG guide compliance audit — 2026-10-19

Source of truth: the ModWorkshop Wiki **Legendary Armor Skins/LAS/MOOG/Outfit
Module Guide** (by Columbus):
<https://wiki.modworkshop.net/books/payday-2-mod-creation/page/legendary-armor-skinslasmoogoutfit-module-guide>

Scope: does the `tools/pd2-las` pipeline + `Miranda_LAS` pack follow the
guide's file-format and configuration contract? Our pipeline authors the
models programmatically (verified Diesel codec) instead of the guide's
Blender + Model Tool flow; the **outcomes** the guide specifies are what
this audit checks.

## Conforms

| Guide requirement | Where enforced |
| --- | --- |
| PD2 rig skeleton (pelvis/3-spine/shoulders/arms/forearms+hands/5×3 fingers/thighs/legs/feet/toes); leave locators & effect spawners (`BackPack1`, `aim`, `e_taser`, …) untouched | Template object tree kept verbatim; only mesh blocks are re-authored (`build_models.assemble_model`) |
| Max **3 weight influences per vertex** (Limit Total → 3) | `BLENDWEIGHT0` is 3-wide, renormalized; asserted in `tests/test_build_models.py` |
| Model posed to the PD2 bind pose | Target-centric Umeyama retarget (`retarget_maps`); bind placement tests |
| FPS model is arms-only, separate unit | `fps_miranda.model` (arms+shadow groups) + `fps_miranda.unit` |
| FPS render template includes **`DEPTH_SCALING`** | `generic:DEPTH_SCALING:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS` — exact match to the guide's fps example |
| `SKINNED_3WEIGHTS` on rigged materials | All skinned materials (eyes included) |
| Material `name` = the model's material names (`mtr_*`) | hash64 names in the model match `material_config` (verified vs the 2B reference) |
| Texture paths **without file extension** | `units/miranda/skins/miranda/miranda_*_df` etc.; asserted in tests |
| Tangents present (normal maps need them) | UV direction streams (`UV_DIRECTION_U/V0`) authored per face |
| Diffuse saved **DXT5** (alpha channel kept for specular trick) | Source VTFs are DXT5, converted DDS DXT5 |
| Normal maps compressed **DXT5** (alpha channel required) | `*_nm.texture` are DXT5 |

## Fixed in this pass (was non-conformant)

| Guide requirement | Fix |
| --- | --- |
| `<materials version="3" **group="…**">` header — `group` is part of the required header | Added `group="miranda"` / `group="fps_miranda"` |
| `unique="true"` required on materials (else buggy contour outlines) | Added on the four TPP skin materials (the ones with CONTOUR), matching the guide's example placement |
| Character materials use the **`CONTOUR`** template + `contour_color` / `contour_opacity` variables or the wall-outline won't render | TPP `mtr_body/face/head/hair` now use `generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:SKINNED_3WEIGHTS` + both variables (values copied from the guide's example). Eyes stay diffuse-only (CONTOUR without NORMALMAP is not a documented combo); fps stays contour-free per the guide's fps example; `shadow_caster` stays `shadow_caster_only:SKINNED_1WEIGHT` (2B reference parity) |

## Watch items (verify in game)

- **Normal-map orientation**: PD2's shaders expect **OpenGL-style (Y+)**
  normal maps. The L4D/Source normals are typically Y+ already, but if
  bumps light inverted in game, flip the green channel of the `*_nm`
  textures (guide's "To format a DirectX-style normal map" recipe).
- `shadow_caster_only:SKINNED_1WEIGHT` is kept byte-compatible with the
  2B reference (proven in game) even though our shadow mesh carries 3
  weights; if shadows deform oddly, that combination is the first suspect.
- The 2B reference pack itself omits `group`/`unique`/`CONTOUR` and works;
  the guide is newer and states them as required, so this pack follows the
  guide and treats 2B only as the LAS registration/geometry contract.

## Double-check pass (same day) — build-flow fixes & model/config parity

A verification sweep after the compliance changes found and fixed two
pipeline bugs and one benign deviation:

1. **`build_las.py --stage inventory` never wrote `source_inventory.json`**
   (the file write was gated to *other* stages, which also omitted the
   models section). Fixed: the models inventory is computed for every
   stage and the record is always persisted (`--stage inventory` still
   dumps pure JSON to stdout).
2. **`build_models.py` silently skipped the pack/zip step** when no
   scaffold existed (fresh checkout → no deliverable, no warning), while
   the README documents it as a one-command build. Fixed: it now builds
   the scaffold via `build_las --stage all` first and refuses to finish
   without a pack.
3. **fps `c_block` material is undefined in `material_config`** — this is
   **2B parity, not a defect**: the kept template drawable `c_block`
   references template material `0x8db63936…`, which the working 2B
   reference also leaves undefined (the 2B fps model carries 5
   config-undefined materials; we carry 1). The probe now asserts
   "defined in config OR kept-template parity with 2B". The third-person
   model has zero gaps: all 6 atom-referenced materials are defined.

Verified after the fixes: one-command build from a clean tree produces
the full pack + zip; zip is byte-identical across rebuilds (5,388,811 B);
BUILD_INFO covers all 20 files with matching hashes; suite 191 passed.

## Not applicable to this pipeline

Blender import/export steps (Bone Dir = Blender, Apply Modifiers off,
export .glb, Model Tool add-on, MOOG template editing) — replaced by the
programmatic authoring path; the produced `.model`/`.material_config`/
`.unit`/`.object` files are what matter. GSMA/IL/OP texture types are
optional and unused (diffuse + normal only, as in the 2B reference).
