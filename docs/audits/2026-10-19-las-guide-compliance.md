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

## Triple-check pass (same day) — deep artifact probes

Byte-level verification of the shipped zip, beyond the test suite:

- **Units/objects/lua vs 2B reference**: exact structural parity — same
  lua schema (`category`, `unit`, `fps_unit`, five flags), same `.unit`
  extensions (`unit_data`, `ContourExt`), same `.object` drawables and
  enable flags (`g_body`/`g_head` on, LODs off, `c_block` culling,
  `root_point` orientation). Every `main.xml` path resolves to files in
  the pack; localization keys complete.
- **Geometry placement**: every drawable named in the `.object` files
  exists in the matching model; enabled drawables carry geometry
  (tpp `g_body` 9,548 tris, `g_head` 6,885 tris in 5 material atoms;
  fps `g_body` carries the arms). Weights: every vertex sums to 1 with
  no negative components (≤3 influences by format).
- **UV convention, numerically**: stored UVs are exactly `1 − v_src`
  (p2mt import convention). Source UVs are intentionally tiled — tpp
  v_src spans [0, 1.999], fps v_src sits at [1.23, 1.63] — so stored V
  falls outside [0, 1] on the tiled rows and wraps in-game exactly as it
  did in Source. 2B's clean [0, 1] range is its authored content, not a
  different convention. The 8 degenerate (100, 100) sentinel vertices in
  the fps model match the 2B reference exactly (8 = 8).
- **Skinbones**: all 52 (tpp) / 36 (fps) bones satisfy
  `rotations[i] · world_i = I` with hierarchy-accumulated worlds, and
  `global` equals the Hips world (tpp) / skeleton root world (fps — the
  arms rig has no Hips bone by design).
- **Codec round-trip**: both shipped models are byte-exact under
  `ModelFile.read → write`. All textures are DXT5 power-of-two; the
  armor-skin icon is 256×256 BC3. Zip entries carry the fixed
  2020-01-01 timestamps and 0644 permissions.
- **2B pack extras we intentionally omit**: `*.cooked_physics` (0-byte
  export placeholders) and `ss.model` (3.9 MB, referenced by nothing in
  the 2B pack). The only other layout difference is texture naming (2B
  ships 2 `base_*` textures; we ship 7 region-mapped ones) and our
  `BUILD_INFO.json` provenance file.

## Structural comparison vs the 2B reference (same day)

Systematic schema diff of the two packs:

**Identical structure** — `main.xml` element tree (same tags/attributes;
only the texture entry count differs), lua hook keys (all 8, same
schema), `.unit` and `.object` XML shapes (shape-equal on all four),
model drawables (tpp `g_body/_lod1`, `g_head/_lod1`, `s_body`; fps adds
`c_block`), the Object3D tree (212 nodes tpp / 98 fps — the full rig,
locators included), skinbones block format and inv-world convention, and
the geometry channel layout.

**Explainable differences**:

| Difference | Why |
| --- | --- |
| skinbones palette 52 bones (ours) vs 22 (2B) | Content: our mesh weights fingers/toes/Hips/Spine1; 2B's dress weights only 22 bones. Same skeleton tree — ours is a weighted-bone superset. |
| `AUTHOR` section present in 2B, absent in ours | Intentional: `assemble_model` drops p2mt/OVERKILL authoring metadata (2B carries `alfred.roettinger@starbreeze` build strings). |
| material_config sets differ (ours: mtr_face/hair/eyes + guide CONTOUR contract; 2B: `*_lod1`, `alpha_ref`, ALPHA_MASKED head) | Content: our hair is a solid mesh (no alpha cards); the guide's newer contract adds group/unique/CONTOUR. |
| Textures: 7 region-mapped DXT5 vs 2B's 2 giant atlases (`base_df` 22 MB) | Content: region-mapped from the L4D2 source (TEXTURE_PAIRS contract). |
| 19 MATERIAL sections (ours, per-group copies) vs 7 (2B) | Re-authoring artifact; same name contract, atom→matgroup resolution verified identical. |
| `BUILD_INFO.json`, no `cooked_physics`/`ss.model` | Ours adds provenance; 2B's extras are 0-byte/orphan export leftovers. |

Verdict: structurally the same product shape as 2B at every level the
engine reads — pack schema, unit/object graphs, skeleton tree, drawable
names, and skinning conventions — with content-driven differences only.

## Not applicable to this pipeline

Blender import/export steps (Bone Dir = Blender, Apply Modifiers off,
export .glb, Model Tool add-on, MOOG template editing) — replaced by the
programmatic authoring path; the produced `.model`/`.material_config`/
`.unit`/`.object` files are what matter. GSMA/IL/OP texture types are
optional and unused (diffuse + normal only, as in the 2B reference).
