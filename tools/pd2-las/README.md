# pd2-las — Source-engine characters as PAYDAY 2 LAS outfits

Builds **Legendary Armour Skins (LAS)** outfit packs for PAYDAY 2 from compiled Source-engine models
(`.mdl`/`.vvd`/`.vtx` + `.vtf`): each mesh is re-skinned onto the PD2 player skeleton of the `2b.rar` reference pack
and written as Diesel `.model` + `.texture` + `.material_config` behind a BeardLib `LegendaryArmours.<id>`
registration. Pure Python: no Source compile step, no Blender, and no game is needed to build.

| Tracked pack (`dist/<name>.zip`) | Source archive | Builder | `make` target |
| --- | --- | --- | --- |
| `Miranda_LAS` — full body and first-person arms | `models/l4d2_miranda_lawson_1.zip` | `build_models.py` | `build` |
| `Miranda_Busty_LAS` — the same with a larger chest, its own LAS id | same | `build_busty_variant.py` | `busty` |
| `Christie_LAS` — body only, the heister keeps their head | `references/Christie.zip` | `build_christie_las.py` | `christie` |
| `Christie_LAS_Slim` — slimmer, wrists cut for the in-game gloves | same | `build_christie_las.py --variant slim` | `slim` |

## Status

Authoritative: `python3 tools/pd2-las/status.py` — read-only, no venv needed, one JSON object: the environment, every
tracked pack of the three pipelines (size, sha256, `make` target, whether the zip `is` what git tracks), the next command.

## Commands

From the repo root; `make -sC tools/pd2-las` alone lists every target. They cover all three pipelines: `lawson`
and `heads` build the packs of `tools/pd2-port/` and `tools/build_joy_head_mods.py`.

```sh
make -sC tools/pd2-las env      # fresh clone or restarted sandbox: missing tracked files, pinned .venv, 2B templates; ends with status
make -sC tools/pd2-las status   # the JSON above; when something is missing, its "hint" is the command to run
make -sC tools/pd2-las build    # or busty | christie | slim | lawson | heads | all; prints the state of the packs it wrote
make -sC tools/pd2-las fresh    # every tracked pack built again in a copy, each zip against its sha256, no tolerance
make -sC tools/pd2-las test     # the whole suite, offline
make -sC tools/pd2-las green    # everything the test workflow checks, test and fresh included, one line each
```

- `make -n <target>` prints what a target runs. Without `-s`, make wraps the JSON in "Entering directory" lines.
- `env` unpacks the 2B templates into `build/pd2-las/2b/` (gitignored); the builders default `--templates` to
  it, and only `extract_2b.py` writes that path. Of tracked files it restores only missing ones.
- A build **overwrites the tracked zips** in `dist/` and `build/pd2-las/` and writes their `.sha256`, so only
  `"is": "tracked"` (the zip is what git holds) proves a rebuild; the builder's output is in
  `build/pd2-las/<target>.log`. In the pinned environment an unchanged tree reproduces the zips on any x86-64
  Linux machine: every builder first puts itself on one declared code path (`determinism.py`). `fresh` checks
  all 16 zips in a copy and touches no tracked file; nor does a builder run with `--out build/x` (Christie: also `--dist build/x`).
- **Done means:** `green` passes and `status` shows `changed` only for packs you meant to change. No
  document needs an edit; a changed `Miranda_LAS` needs `heads` run again.

## File map

| Path (`tools/pd2-las/`) | Role |
| --- | --- |
| `build_models.py` | the whole Miranda build (both models, the scaffold stage, the zip), and the mesh library every builder imports: retarget (`retarget_maps`), `transfer_group`, `assemble_model`, mesh audits |
| `build_las.py`, `las_pack.py` | scaffold stage: VPK → textures, hook, `main.xml`, locales, unit XML, `BUILD_INFO.json`, reproducible zip. Run alone, `build_las.py` leaves a scaffold without models, marked `WIP_DO_NOT_INSTALL.txt` |
| `source_inventory.json` | what the L4D2 source archive contains (bones, meshes, triangle counts, texture formats); tracked, `make -sC tools/pd2-las inventory` rewrites it, and a test fails while it is stale |
| `build_busty_variant.py`, `bust_variant.py` | the chest-morph variant |
| `build_christie_las.py`, `las_outfit_pack.py`, `christie_skeleton_map.json` | the Christie packs |
| `diesel_model.py` | Diesel `.model` codec; change it only with the round-trip tests green |
| `vpk.py`, `source_model.py`, `vtf.py`, `dds_encode.py` | Source readers (VPK, MDL 44–49 + VVD + VTX, VTF) and DDS writers |
| `skeleton_map.json`, `las_target_skeleton.json` | Source → PD2 bone map; the PD2 rig and object names |
| `segment_fit.py`, `render_mesh_skeleton.py`, `elbow_before_after.py`, `preview.py` | fit measurements and renders the builders call |
| `diagnose_mesh.py`, `neck_junction.py`, `uv_check.py`, `audit_metrics.py`, `glove_check.py`, `review_christie_idle.py`, `pose_zoom.py` | diagnostics for built packs, off the build path; each docstring carries its command |
| `pose_preview.py`, `preview_textured.py`, `shellview.py` | what those diagnostics render with: the arms-down pose and two rasterisers, one lit, one flat per face |
| `gma.py`, `smd.py`, `inspect_gma.py`, `inspect_textures.py` | GMod/Source addon inspection and SMD export, off the build path |
| `mip_audit.py` | for the two Miranda textures the build encodes itself: which mip level is on screen at which distance, how far each level is from the picture it stands for, and the before/after render (`make -sC tools/pd2-las audit`) |
| `Makefile`, `status.py`, `recover_env.sh`, `extract_2b.py` | the commands above, the state of all 14 packs, environment (`env` runs `recover_env.sh`), and where the 2B pack is unpacked |
| `determinism.py`, `tangents.py`, `fresh.py`, `trace_run.py` | what keeps the bytes independent of the machine: the declared code path and the rounding with a margin; tangent frames from the values the file stores; the rebuild check behind `fresh` and its variation matrix; a checkpoint trace for any builder |
| `pins.txt`, `copies.py` | the two pinned versions, written once (`recover_env.sh`, CI and `status.py` read them); what a merge of two tools is held to: `record`, `compare`, `after` |

## Invariants

One test each in `tests/test_pd2_las_invariants.py`, named after its row. They read the tracked
packs, so they need no build and no 2B templates; the authoring suites check more, during a build.

| Invariant | Test |
| --- | --- |
| **Units:** Source is inches, Diesel centimetres. Nothing multiplies by 2.54: the per-bone fits onto the 2B skeleton carry the scale | `test_units_are_centimetres_at_the_scale_of_the_rig` |
| **UVs** are stored as `(u, 1 − v_src)`, the 2B convention; Source V tiles, so values outside 0–1 are normal | `test_uvs_are_stored_as_u_and_one_minus_v` |
| **Winding** is reversed from Source, `(a,b,c) → (a,c,b)`: no inverted triangle, positive signed volume | `test_winding_is_outward_with_no_inverted_triangle` |
| **Skin:** 3 weights per vertex summing to 1, palette-local indices, parents before children (`Hips` first) | `test_skin_has_three_weights_and_a_root_first_palette` |
| **Atoms:** a render atom's triangle indices are global vertex indices, all inside the atom's own vertex block | `test_atoms_index_global_vertices_inside_their_own_block` |
| **Materials:** a model names its materials by hash and the `.material_config` declares them: `CONTOUR` and `unique` on third-person skin, `DEPTH_SCALING` in first person | `test_materials_are_the_ones_the_material_config_declares` |
| **Objects:** a unit's `.object` lists exactly the `g_` drawables its model has; the body is on, the LODs are off | `test_objects_listed_by_the_unit_are_the_ones_the_model_has` |
| **Textures:** every unit texture is DXT5 with a full mip chain; diffuse alpha is gloss and stays low at every level; a normal map holds X in alpha and Y in green | `test_textures_keep_gloss_low_and_normals_in_the_diesel_layout` |
| **Codec:** `ModelFile.read → write` is byte-exact on the 2B templates and on every tracked model | `test_codec_round_trips_byte_for_byte` |
| **Registration** follows the 2B contract: a hook on `lib/tweak_data/armorskinstweakdata` that creates `LegendaryArmours.<id>`, BeardLib `main.xml` AddFiles, menu locales | `test_registration_follows_the_2b_contract` |
| **Tracked bytes:** every zip equals its `.sha256` sidecar, and its `BUILD_INFO.json` hashes its own payload | `test_tracked_bytes_match_their_sidecar_and_build_info` |
| **Variants** change only what they claim: the busty pack is the base pack plus the chest, with the same head, arms and textures | `test_variants_change_only_what_they_claim` |

## Do not

- Do not copy the 2B pack's defects (an unregistered `ss.model`, empty
  `cooked_physics` files, `Hooks` in `main.xml` where the folder is `hooks/`).
- Do not apply `tools/pd2-port`'s vertex-normal winding repair here: these
  meshes are welded, and the hole test is `build_models.orientation_breaks`.
- Do not re-measure the source by hand: read `source_inventory.json`.
- Do not judge by eye how a mesh sits on the skeleton: `segment_fit.py`
  measures it and `test_christie_las.py` asserts on it (`docs/pd2-las/CHRISTIE.md`).
- Do not retry the approaches under "Dead ends" in `docs/pd2-las/HANDOFF.md`.
- Do not go back to swapping whole heister models in place; that route is
  retired (`docs/audits/2026-10-18-route-change-audit.md`).
- Do not silence a failing test with a skip or an `xfail`: both are budgeted
  by `tools/pd2-port/check_skip_budget.py`. The one exception: [Next](#next).
- Do not cut a computed value off with `astype(np.uint8)`, and do not decide on a number that is zero up to
  rounding: `determinism.floor8`, `rounded` and `above` stop the build at a boundary; a tie needs a rule (D26).
- Do not put dates or measurements in this file (`HANDOFF.md`, `MODLOG.md`, the packs' `BUILD_INFO.json`),
  nor a size, a hash or a test count in any document: `status` and `green` print them.
- Do not write commands, invariants or open work anywhere else: `AGENTS.md`
  and `HANDOFF.md` point here, and a test keeps them from growing their own.

## Next

1. In-game verification with `docs/pd2-las/in-game-checklist.md` (written for `Miranda_LAS`); it needs a human
   with PAYDAY 2, SuperBLT, BeardLib and LAS. It opens with a ten-minute check of the last rebuild of the Miranda packs.
2. Gloss, measured and not fixed (`docs/audits/2026-11-11-miranda-mips-and-object.md`):
   texels at full gloss in `body_df` and `head_df` of the Miranda packs and in three Christie
   textures; the Christie sleeve-gloss pass moves gloss around inside the blocks it touches.
3. The sibling packs: `lawson_las` and the nine head packs have no record of their tracked bytes in game, and
   the head packs have no checklist.

## Further reading

- The sibling pipelines (`tools/pd2-port/`, `tools/build_joy_head_mods.py`): [`tools/README.md`](../README.md)
- Why it is built this way: `docs/pd2-las/DECISIONS.md`; the journal: `tools/pd2-las/MODLOG.md`; dated audits: `docs/audits/`
- The tracked bytes, what was seen in game and when, dead ends: `docs/pd2-las/HANDOFF.md`
- LAS runtime contract and gotchas: `knowledge/games/payday-2/las-armor-skin-outfit.md`
- Chest morph: `docs/pd2-las/CHEST-VARIANT.md`; Christie fit: `docs/pd2-las/CHRISTIE.md`; retarget and matrix conventions: the `build_models.py` docstring, `retarget_maps`
