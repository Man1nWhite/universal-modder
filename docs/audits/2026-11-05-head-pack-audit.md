# Heister head-replacement packs — audit, 2026-11-05

**Scope:** the newest Miranda deliverable set — the nine `mod_overrides` head-replacement packages built
by `tools/build_joy_head_mods.py` (`dist/Miranda_{L4D2,Romance}_over_{Joy,Clover,Bonnie,Sydney}.zip` plus
`dist/Geralt_over_Rust.zip`), their `.sha256` sidecars, the preview sheets in `docs/previews/`, and the two
reference archives they are built from.

**Method:** structural probes rather than reading the builder — zip entry inventory and timestamps,
`sha256` of every entry and of the whole archive, DDS header/mip/alpha analysis, a full `diesel_model`
decode of every shipped `.model` (drawables, atoms, material groups, materials, skinbones), cross-checks
of every `*.material_config` against the models and against the files in the archive, geometry invariants
(normal length, weight sums, bone index range, UV range, atom/index bounds, degenerate triangles), and a
full rebuild of all nine packages to test the reproducibility claim.

Nine packages: Joy 10 entries, Clover 13, Bonnie 13, Sydney 12, Geralt 15.

## Fixed

1. **The four L4D2 packs could not be reproduced, and carried a scrambled specular plane.**
   Running `tools/build_joy_head_mods.py` against the tree reproduced the four **Romance** packs and
   `Geralt_over_Rust.zip` byte for byte, but every **L4D2** pack came out **95,478 bytes smaller** and with a
   different digest:

   | pack | tracked before | rebuilt now |
   | --- | --- | --- |
   | `Miranda_L4D2_over_Joy.zip` | 10,681,277 B | **10,585,799 B** |
   | `Miranda_L4D2_over_Clover.zip` | 7,732,069 B | **7,636,591 B** |
   | `Miranda_L4D2_over_Bonnie.zip` | 8,237,483 B | **8,142,005 B** |
   | `Miranda_L4D2_over_Sydney.zip` | 7,235,982 B | **7,140,504 B** |

   All four differ in exactly one entry, the shared `*_head_df.texture` (5,592,560 B either way), and only
   in the **alpha channel**: RGB colour blocks are bit-identical (identical block multiset), the difference
   is confined to the face quadrant `[0:1024, 0:1024]`, is bounded by 18/255 (mean 4.1), and touches 91 % of
   that quadrant. The tracked alpha is *decorrelated* from every plausible source — the LAS face diffuse
   alpha (r = +0.01), luminance (+0.04), the face R/G/B channels (≤ +0.05), the head and body alpha
   (≤ +0.05) — while the rebuilt alpha is exactly `min(source alpha, 18)` as the code intends. The four
   old zips were therefore built against a **different (earlier) `dist/Miranda_LAS.zip`** and never
   rebuilt; the L4D2 face diffuse alpha in them is specular noise rather than the attenuated-gloss map
   that `tests/test_pd2_las.py::test_tracked_pack_specular_alpha_and_pd2_normal_layout` expects (PD2 reads
   diffuse alpha as specular). Rebuilt all nine packages: two consecutive runs are byte-identical, the
   Romance packs and Geralt are unchanged, `dist/*.zip.sha256`, the sizes in `docs/pd2-las/HANDOFF.md`,
   `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` were updated, and regenerating every preview sheet and icon
   reproduced the tracked PNGs **byte for byte** — the fix is invisible in the deliverable sheets, which is
   why nothing caught it.

2. **The codec could not read four vanilla meshes that these very packs ship.**
   `tools/pd2-las/diesel_model.py::decode_geometry` raised `ValueError: unsupported geometry channel 8
   (item size 2)` on `g_armorbag`, `g_medicbag`, `g_sentrybag` and `g_bodybagsbag` — the bag meshes carry
   a second and third UV set (`TEXCOORD1`/`TEXCOORD2`, enum 8/9, `float2` per vertex), which the decoder had
   no branch for. Any whole-model verification of Clover, Bonnie, Sydney or Joy aborted on them.
   Added both channels (decoded as `uv1`/`uv2`, re-encoded verbatim) and a test that round-trips every
   geometry section of two shipped models byte for byte (22/22 in `npc_criminal_bonnie.model`) plus one
   asserting the extra UV sets arrive with `vert_count` entries and a fully consumed payload. The
   interpretation is confirmed by the byte accounting: 1563 vertices × 92 B + 8 B section header + 72 B
   channel headers + 8 B name hash = the 143,884 B payload exactly.

3. **`references/README.md` named five `Heister - FPS Gloves in TPS 2.zip` templates, four of them wrong**
   (`npc_criminal_bonnie_1.model`, `npc_criminal_sydney_1.model`, `chill_npc_criminal_female_1.model`,
   `chill_npc_criminal_bonnie_1.model`). The archive contains `npc_criminal_bonnie.model`,
   `npc_criminal_sydney.model`, `npc_criminal_female_chill.model` and `npc_criminal_bonnie_chill.model`
   (and also the Joy, Wild and Max units). Corrected.

4. **Nothing in the tree said what each pack replaces, or that nobody has looked at the result in game.**
   README §3 and `docs/pd2-las/HANDOFF.md` now state the coverage — Clover and Bonnie replace the heist,
   menu *and* Safe House (`*_chill`) model; Joy and Sydney replace heist + menu only — and that the whole
   nine-pack set is *offline-verified only*, unlike the LAS pack, which has
   `docs/pd2-las/in-game-checklist.md`.

## Checked and clean

- Every `.sha256` sidecar matches its archive; all entries carry the fixed `2020-01-01 00:00:00` timestamp;
  no duplicate or empty entries; all nine archives rebuild deterministically.
- Head drawables in all eight Miranda packs: 4,402 vertices / 7,109 triangles (atom 0 = head 6,885 tris,
  atom 1 = 3D eyelashes 224 tris), unit normals, blend weights summing to 1, bone indices in range, UVs
  inside `[0,1]`, `uvdir_u`/`uvdir_v` unit length, declared bounds equal to the real bounds, no degenerate
  or duplicated triangles, every atom slice inside its geometry/topology. **These are the 2026-11-05
  counts.** The 2026-11-07 neck-skirt rebuild (§10.3 of
  `docs/audits/2026-11-07-christie-slim-diagnosis.md`) moved the four L4D2 packs to 4,515 / 7,321 tris
  over Joy and 4,508 / 7,305 over Clover, Bonnie and Sydney, lowest vertex z 149.48 → 142.98; the four
  Romance packs are byte-identical to the ones audited here, and
  `tests/test_pd2_las.py::test_neck_skirt_is_on_the_l4d2_heads_and_not_on_the_romance_ones` pins both.
- Every material a drawable can reach resolves in the `*.material_config` shipped in the same directory.
  The only unresolved hash (`#84ea363244e1050b`) belongs to the collision drawables (`c_headphys1/2`),
  which never render.
- Every shipped `.texture` is referenced by a shipped config, and every texture a config references that is
  *not* shipped is a vanilla path (`shared_textures/vest_*`, `equipment_bag_*`, `fps_gloves_*`,
  `sus_npc_*_arms`, `npc_criminal_*_suite_*`, …). Clover's `mtr_head` really does point at the shipped
  `shared_textures/clover_head_df`/`_nm`, not at a vanilla atlas.
- Icons are uncompressed 128×128 BGRA (65,664 B) and differ per source (L4D2 `9ccd0112…`,
  Romance `dc11fb6b…`).
- **The Joy packs are structurally the Ada Wong reference, by design.** Same ten files, same 24 drawables,
  same config material set; the only config difference is the eyelash `alpha_ref` (`0.042000003159046` →
  `0.30`). `npc_criminal_joy_1_eyes_df.texture` being a byte copy of `npc_criminal_joy_1_lashes_df.texture`
  is *required*, not a bug: Joy's `mtr_hair_off` renders the lash atom through the `*_eyes_df` path, so the
  eyes slot must carry the lash strip; the alpha is binary (22.5 % coverage), which is what `alpha_ref 0.30`
  cuts, and `*_lashes_op.texture` is a luminance mask (alpha constant 1.0) as the `opacity:` template
  expects.
- Clover's six legacy hair drawables are collapsed to a 3-vertex triangle at `(0, 5.33, 166.76)` (inside the
  head bone) and disabled in both `.object` files; Sydney's two hair-mask drawables are collapsed the same
  way and `g_hair_mask_off` is disabled (the `_on` variant is absent from the object file, so it keeps the
  reference's default, and the hidden triangle makes that immaterial).

## Found, deliberately left

1. **L4D2-over-Sydney keeps the reference's opaque hair material.** `patch_sydney_material_config(...,
   alpha_masked=is_romance)` upgrades `mtr_hair` to
   `generic:ALPHA_MASKED:…EXTERNAL_ALPHA_REF…` (alpha_ref 0.30) only for the Romance source; the L4D2 pack
   ships the reference's `generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:RL_PLAYERS:SKINNED_3WEIGHTS`, which has
   no alpha test — so the 224-triangle eyelash strip is drawn opaque there, while Joy
   (`ALPHA_MASKED`), Bonnie (`ALPHA_MASKED`, alpha_ref 0.05) and Clover (`opacity:` + `npc_female_hair_1_op`)
   all cut it. The branch is deliberate (its docstring says "For ME2 Romance over Sydney"), so this is a
   watch item, not a patch: it needs a look in game. The preview sheets cannot settle it — the sheet
   rasterizer alpha-cuts atom 1 unconditionally.
2. **Joy and Sydney ship no Safe House model.** Clover and Bonnie ship `*_chill.model` + the chill
   `*.material_config`; Sydney ships only the chill material config, Joy neither. If the vanilla chill units
   exist and read the same `*_head_df`/`*_hair_df` paths (Sydney's head textures live in the opera unit
   directory the chill unit also references), the Safe House would show Miranda's head texture on the
   vanilla head mesh. That cannot be checked offline — no vanilla assets in the repository — so it is now
   documented as a coverage limit rather than "fixed".
3. **Bonnie's `.object` files list eleven drawables the model does not have** (`g_lootbag`, `g_safe`,
   `g_safe_ovk`, `g_chute`, `g_cagebag`, `g_canvas_bag`, `g_explosives_bag`, `g_g_bag`, `g_body_bag`,
   `g_toolsbag`, `g_toolsbag_large`). They are all `enabled="false"` and both files are byte-identical to
   the reference package's, i.e. vanilla-consistent, not a packaging mistake.
4. **The preview sheets colour the body, gloves and arms with flat placeholder RGB** (`rasterize_parts`
   never samples those materials). The blue gloves in the Clover/Bonnie/Sydney sheets are that stub colour,
   not a broken material.

## Rebuild

```sh
.venv/bin/python tools/build_joy_head_mods.py      # all nine packs + .sha256
.venv/bin/python tools/render_mod_previews.py      # docs/previews/*.png + the overview sheet
.venv/bin/python -m pytest tests -q                # 506 tests
```
