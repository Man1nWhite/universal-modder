# pd2-las — 2B-template outfits for PAYDAY 2

Builds **Legendary Armour Skins (LAS)** outfits from compiled Source models (`.mdl`/`.vvd`/`.vtx` + `.vtf`),
rigged GLB and COLLADA-with-TMC characters, and written as Diesel `.model`/`.texture`/`.material_config` behind
a BeardLib `LegendaryArmours.<id>` registration. After unpacking the templates the builders run in Python;
no Source compile step, Blender, or running game is needed.

| Tracked pack (`dist/<character>/<name>.zip`) | Source archive | Builder | `make` target |
| --- | --- | --- | --- |
| `Miranda_L4D2_LAS` — full body and first-person arms | `references/characters/l4d2_miranda_lawson_1.zip` | `build_models.py` | `build` |
| `OfficeSuite` — the DOAXVV "Secret Report" costume, built from `.dae` (6 mats), 5% slim with the user's suit and jewelry diffuses, palms cut *on* the line where they begin, with no extension past it (`palm_cut`, `extend_cm`/`clipped_to_cm: 0.0` in `BUILD_INFO.json`, D70; no default glove, a chosen one wins), in TPP and FPS | `references/honoka/Honoka_DOAXVV_Secret_Reportout.dae` | `build_honoko2_dae.py` | `honokodae` |
| `OfficeSuite_over_Bunny` — the same `OfficeSuite` body, shadow caster and FPS arms packed into a 4096×2048 BC3 6-tile atlas over the vanilla **Hop to It** (`player_styles.bunny`, `ccmt_acc_bunny`) outfit across all five body types plus the `bunny` outfit icon; native `mod_overrides`, no BeardLib or LAS (D85) | `OfficeSuite.zip` + `references/templates/ccmt_acc_bunny.7z` | `build_bunny_body_mod.py` | `bunny` |
| `Miranda_Lawson_VO_over_Hila_Stream` — the same audio on the id-keyed route: 699 Wwise IMA ADPCM `.stream` files named after Hila's voice-line ids in `soundbanks/streamed/regular_vox/`, no BeardLib (`install` tab of voice_lines_vox/vo_master.xlsx) | references/voice/Голос Лоусон.7z (clips), `references/voice/LAWSON VOICE (PAYDAY 2).7z` (purpose-authored takes for the slots below the fit floor), `references/voice/Tokoyami Hila.7z` (the container it copies) | `tools/build_hila_stream_mod.py` over `wwise_ima.py` | `voices_stream` |
| `Arivus_Head_over_Old_Hoxton_GLB` — the `g_head_old_hoxton` drawable as a bind-pose `.glb` plus the five pack `.texture` files as `.dds`; a viewer export, not an installable mod | `Arivus_over_Hoxton.zip` (the tracked pack itself) | `build_arivus_glb_pack.py` over `model_to_glb.py` | `glb` |

See `docs/pd2-las/HANDOFF.md` for in-game evidence.
## Status

Authoritative: `python3 tools/pd2-las/status.py` — read-only, no venv needed, one JSON object: the environment, every tracked pack of the three pipelines (size, sha256, `make` target, whether the zip `is` what git tracks), the next command.
## Commands

The toolkit requires Python 3.11+ everywhere (the CLI floor and CI).
From the repo root, `make -sC tools/pd2-las` with no target lists them.

```sh
make -sC tools/pd2-las env      # fresh clone or restarted sandbox: missing tracked files, pinned .venv, 2B templates; ends with status
make -sC tools/pd2-las status   # the JSON above; when something is missing, its "hint" is the command to run
make -sC tools/pd2-las build    # or honokodae | bunny | heads | voices_stream | glb | all  (the former voices_geralt / voices_arivus targets were removed with the retired packs, D88)
make -sC tools/pd2-las fresh    # every tracked pack built again in a copy, each zip against its sha256, no tolerance
make -sC tools/pd2-las test     # the whole suite, offline
make -sC tools/pd2-las green    # everything the test workflow checks, test and fresh included, one line each
```

- `make -n <target>` prints what a target runs. Without `-s`, make wraps the JSON in "Entering directory" lines.
- Windows: `env` is a bash script. Make the venv once by hand (`py -3.11 -m venv .venv`), install with
  `pip install -c tools/pd2-las/pins.txt` (the versions the packs rebuild byte for byte with), then the
  same `make` calls work under git-bash/MSYS: they find `.venv/Scripts/python.exe` themselves.
- `env` unpacks the 2B templates into `build/pd2-las/2b/` (gitignored) or refreshes a stale one.
  `PD2_2B_TEMPLATES` points setup, builds and `fresh` at a shared unit folder; `extract_2b.py` manages
  only the default cache. Of tracked files, `env` restores only missing ones.
- The LAS outfit's eye is `references/textures/EYE_Diff.png`, the same picture the Hila head pack wears, cropped to the eyeball's own planar map (`EYE_ZOOM`, D84); it is not converted from the source, whose eye is drawn by a shader and has no texture to convert.
- A build **overwrites the tracked zips** in dist/, so only
  `"is": "tracked"` (the zip is what git holds) proves a rebuild; the builder's output is in
  `build/pd2-las/<target>.log`. In the pinned environment an unchanged tree reproduces the zips on any x86-64
  Linux machine: every builder uses the declared `determinism.py` code path. `fresh` verifies original
  checksums before building in a copy; `check --builders NAME` limits what it rebuilds. A custom Miranda
  `--out` does not promote to dist/; verify its sidecar from there.
- Order: `build` before `heads`, which reads the L4D2 pack's model. **Done means:** `green` passes and `status` shows `changed` only for the packs you meant to change.
## File map

| Path (tools/pd2-las/) | Role |
| --- | --- |
| `build_models.py` | the whole Miranda build (both models, the scaffold stage, the zip), and the mesh library every builder imports: retarget (`retarget_maps`), `transfer_group`, `assemble_model`, mesh audits |
| `build_las.py`, `las_pack.py` | scaffold stage: VPK → textures, hook, `main.xml`, locales, unit XML, `BUILD_INFO.json`, reproducible zip. Run alone, `build_las.py` leaves a scaffold without models, marked `WIP_DO_NOT_INSTALL.txt` |
| `source_inventory.json` | what the L4D2 source archive contains (bones, meshes, triangle counts, texture formats); tracked, make -sC tools/pd2-las inventory rewrites it, and a test fails while it is stale |
| `build_honoko2_dae.py`, las_head.py, `tmc_las.py`, `tmc.py`, `tmc_export.py`, `tmc_skeleton_map.json`, `render_honoka.py` | the OfficeSuite LAS packs built from the Collada `.dae` with the TMC's skinning, the donor head re-skin, TMC decoder + glTF exporter, MOT → PD2 bone map, and Honoka source preview renderer |
| `packs.py`, `dist_paths.py`, `las_outfit_pack.py` | **the one pack table** (name → dist/ folder, make target, builder); the path map derived from it; shared registration, hook, localization, unit/object XML, zip, glove adapter |
| `diesel_model.py` | Diesel `.model` codec; change it only with the round-trip tests green |
| `vpk.py`, `source_model.py`, `vtf.py`, `dds_encode.py` | Source readers (VPK, MDL 44–49 + VVD + VTX, VTF) and DDS writers |
| `skeleton_map.json`, `las_target_skeleton.json` | Source → PD2 bone map; the PD2 rig and object names |
| `segment_fit.py`, `render_mesh_skeleton.py`, `preview.py` | fit measurements and renders the builders call |
| `pose_preview.py`, `preview_textured.py`, `shellview.py` | what those diagnostics render with: the arms-down pose and two rasterisers, one lit, one flat per face |
| `gma.py`, `smd.py`, `inspect_gma.py`, `inspect_textures.py` | GMod/Source addon inspection and SMD export, off the build path |
| `mip_audit.py` | for the two Miranda textures the build writes itself (the repainted face and the supplied eye): which mip level is on screen at which distance, how far each level is from the picture it stands for, and the before/after render (make -sC tools/pd2-las audit) |
| `Makefile`, `status.py`, `recover_env.sh`, `extract_2b.py`, `pins.txt` | the commands above, the state of the distribution packs, environment (`env` runs `recover_env.sh`), where the 2B pack is unpacked, and the pinned Pillow/NumPy versions |
| `pack_checksum.py`, `archive_cache.py` | the sha256 sidecars of the tracked and scratch packs (`python tools/pd2-las/pack_checksum.py`), and validating extracted build inputs by archive and payload instead of sentinel files |
| `build_arivus_glb_pack.py`, `build_bunny_body_mod.py`, `model_to_glb.py`, `rw_dff.py`, `hila_texture_atlas.py`, `wwise_ima.py` | the Arivus `.glb` interchange pack, the `OfficeSuite_over_Bunny` native outfit replacement, and their shared readers/packers: Diesel `.model` → glTF + DDS, RenderWare DFF/TXD, the 6-tile BC3 atlas packer for single-material outfit overrides, Wwise IMA in a `.stream` |
| `audit_metrics.py`, `diagnose_mesh.py`, `neck_junction.py`, `elbow_before_after.py`, `glove_check.py`, `pose_zoom.py`, `uv_check.py`, `wrist_compare.py` | one measurement or before/after sheet each, over a shipped pack: the audit numbers, a mesh deep-dive, the neck seam, elbow and wrist, sleeve/glove junctions, the UV convention |
| `determinism.py`, `tangents.py`, `fresh.py`, `trace_run.py` | what keeps the bytes independent of the machine: the declared code path and rounding margin; tangent frames from stored values; the rebuild check behind `fresh` and its variation matrix; a checkpoint trace for any builder |

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
| **Own hands:** a pack keeps "Default" gloves from spawning over its own arms — its modelled hands, or the cut where a `palm_cut` pack removed them (the palm line since D70) — and ships no bare-forearm adapter | `test_own_hands_packs_never_draw_a_default_glove` |

## Do not

- Do not copy the 2B pack's defects (an unregistered `ss.model`, empty
  `cooked_physics` files, `Hooks` in `main.xml` where the folder is hooks/).
- Do not apply tools/pd2-port's vertex-normal winding repair here: these
  meshes are welded, and the hole test is `build_models.orientation_breaks`.
- Do not re-measure the source by hand: read `source_inventory.json`.
- Do not judge by eye how a mesh sits on the skeleton: `segment_fit.py`
  measures it.
- Do not retry the approaches under "Dead ends" in `docs/pd2-las/HANDOFF.md`.
- Do not revive the speculative whole-heister retarget (`docs/audits/2026-10-18-route-change-audit.md`).
- Do not silence a failing test with a skip or an `xfail`: both are budgeted
  by `tools/pd2-port/check_skip_budget.py`.
- Do not cut a computed value off with `astype(np.uint8)`, and do not decide on a number that is zero up to
  rounding: `determinism.floor8`, `rounded` and `above` stop the build at a boundary; a tie needs a rule (D26).
- Do not put dates or measurements in this file (`HANDOFF.md`, `MODLOG.md`, the packs' `BUILD_INFO.json`),
  nor a size, a hash or a test count in any document: `status` and `green` print them.
- Do not write commands, invariants or open work anywhere else: `AGENTS.md`
  and `HANDOFF.md` point here, and a test keeps them from growing their own.

## Next

1. In-game checks (`docs/pd2-las/in-game-checklist.md`) still need a human with PAYDAY 2: `Miranda_L4D2_LAS`,
   the jewelry swap, and the OfficeSuite palm cut/glove behavior.
   The Hila stream voice pack was reported working, but its latest tracked clips have not been heard;
   the checklist records the remaining re-cut checks. It needs SuperBLT, not BeardLib.
2. Gloss, measured and not fixed (`docs/audits/2026-11-11-miranda-mips-and-object.md`): full-gloss texels in
   the Miranda packs' `body_df`/`head_df`; no in-game record of the head packs.

## Further reading

- The sibling pipelines (tools/pd2-port/, `tools/build_joy_head_mods.py`): [`tools/README.md`](../README.md)
- Why it is built this way: `docs/pd2-las/DECISIONS.md`; dated audits: docs/audits/; renders: `docs/renders/README.md`
- The tracked bytes, what was seen in game and when, dead ends: `docs/pd2-las/HANDOFF.md`
- LAS runtime contract and gotchas: `knowledge/games/payday-2/las-armor-skin-outfit.md`
- Retarget and matrix conventions: the `build_models.py` docstring, `retarget_maps`
