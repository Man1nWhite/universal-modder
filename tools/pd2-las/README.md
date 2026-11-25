# pd2-las — 2B-template outfits for PAYDAY 2

Builds **Legendary Armour Skins (LAS)** outfits from compiled Source models (`.mdl`/`.vvd`/`.vtx` + `.vtf`),
rigged GLB, and COLLADA with TMC skinning. Each mesh is re-skinned onto the PD2 player skeleton from `2b.rar`
and written as Diesel `.model`, `.texture`, and `.material_config` behind a BeardLib `LegendaryArmours.<id>`
registration. After unpacking the templates, the builders run in Python; no Source compile step, Blender,
or running game is needed.

| Tracked pack (`dist/<character>/<name>.zip`) | Source archive | Builder | `make` target |
| --- | --- | --- | --- |
| `Miranda_L4D2_LAS` — full body and first-person arms | `references/l4d2_miranda_lawson_1.zip` | `build_models.py` | `build` |
| `Miranda_L4D2_Busty_LAS` — the same with a larger chest, its own LAS id | same | `build_busty_variant.py` | `busty` |
| `Christie_LAS` — no head or hands; glove adapter, TPP and FPS | `references/Christie.zip` | `build_christie_source.py` | `christie` |
| `Christie_Clover_LAS` — experimental body-only outfit, glove adapter, TPP only | `references/Clover-Christie.zip` | `build_clover_christie.py` | `cloverchristie` |
| `OfficeSuite` — the DOAXVV "Secret Report" costume, built from `.dae` (6 mats), 5% slim with the user's suit and jewelry diffuses, palms cut *on* the line where they begin and 4 cm past it, into the palm, so the arm ends inside the glove (`palm_cut`, `extend_cm`/`clipped_to_cm: 4.0` in `BUILD_INFO.json`, D62; no default glove, a chosen one wins), in TPP and FPS | `references/Honoka/Honoka_DOAXVV_Secret_Reportout.dae` | `build_honoko2_dae.py` | `honokodae` |
| `OfficeSuite_Head` — `OfficeSuite`'s palm-cut body with the Miranda Romance head, one whole-character unit | `OfficeSuite_Miranda_Romance_over_Hila.zip` (its head) | `build_honoko2_dae.py --only officesuite_head` | `honokodae_head` |
| `Miranda_Lawson_VO_over_Hila_Stream` — the same audio on the id-keyed route: 858 Wwise IMA ADPCM `.stream` files named after Hila's voice-line ids in `soundbanks/streamed/regular_vox/`, no BeardLib (`docs/pd2-voice-mod-install.md` §7) | `references/Голос Лоусон.7z` (clips), `references/Tokoyami Hila.7z` (the container it copies) | `tools/build_hila_stream_mod.py` over `wwise_ima.py` | `voices_stream` |

See `docs/pd2-las/HANDOFF.md` for in-game evidence.
## Status

Authoritative: `python3 tools/pd2-las/status.py` — read-only, no venv needed, one JSON object: the environment, every
tracked pack of the three pipelines (size, sha256, `make` target, whether the zip `is` what git tracks), the next command.
## Commands

The general CLI supports Python 3.10+; `env` requires **Python 3.11+** (CI uses 3.11).
From the repo root, `make -sC tools/pd2-las` alone lists the targets for all three pipelines.

```sh
make -sC tools/pd2-las env      # fresh clone or restarted sandbox: missing tracked files, pinned .venv, 2B templates; ends with status
make -sC tools/pd2-las status   # the JSON above; when something is missing, its "hint" is the command to run
make -sC tools/pd2-las build    # or busty | lawson | honokodae | honokodae_head | christie | cloverchristie | heads | hila | voices | all
make -sC tools/pd2-las fresh    # every tracked pack built again in a copy, each zip against its sha256, no tolerance
make -sC tools/pd2-las test     # the whole suite, offline
make -sC tools/pd2-las green    # everything the test workflow checks, test and fresh included, one line each
```

- `make -n <target>` prints what a target runs. Without `-s`, make wraps the JSON in "Entering directory" lines.
- `env` unpacks the 2B templates into `build/pd2-las/2b/` (gitignored) or refreshes a stale one.
  `PD2_2B_TEMPLATES` points setup, builds and `fresh` at a shared unit folder; `extract_2b.py` manages
  only the default cache. Of tracked files, `env` restores only missing ones.
- A build **overwrites the tracked zips** in `dist/` (the Romance sidecar is updated separately), so only
  `"is": "tracked"` (the zip is what git holds) proves a rebuild; the builder's output is in
  `build/pd2-las/<target>.log`. In the pinned environment an unchanged tree reproduces the zips on any x86-64
  Linux machine: every builder uses the declared `determinism.py` code path. `fresh` verifies original
  checksums before building in a copy; `check --builders NAME` limits what it rebuilds. A custom Miranda
  `--out` does not promote to `dist/`; verify its sidecar from there.
- Order: `build` before `busty` and `heads`; `heads`, `honokodae` and then `honokodae_head` before `hila`, whose pack holds the head. Standalone `hila` builds a [native override](../../docs/renders/honoka/model/over-hila/README.md), not LAS. **Done means:** `green` passes and `status` shows `changed` only for the packs you meant to change.
## File map

| Path (`tools/pd2-las/`) | Role |
| --- | --- |
| `build_models.py` | the whole Miranda build (both models, the scaffold stage, the zip), and the mesh library every builder imports: retarget (`retarget_maps`), `transfer_group`, `assemble_model`, mesh audits |
| `build_las.py`, `las_pack.py` | scaffold stage: VPK → textures, hook, `main.xml`, locales, unit XML, `BUILD_INFO.json`, reproducible zip. Run alone, `build_las.py` leaves a scaffold without models, marked `WIP_DO_NOT_INSTALL.txt` |
| `source_inventory.json` | what the L4D2 source archive contains (bones, meshes, triangle counts, texture formats); tracked, `make -sC tools/pd2-las inventory` rewrites it, and a test fails while it is stale |
| `build_busty_variant.py`, `bust_variant.py` | the chest-morph variant |
| `build_honoko2_dae.py`, `las_head.py`, `tmc_las.py`, `tmc.py`, `tmc_export.py`, `tmc_skeleton_map.json`, `render_honoka.py` | the OfficeSuite LAS packs built from the Collada `.dae` with the TMC's skinning, the donor head re-skin, TMC decoder + glTF exporter, MOT → PD2 bone map, and Honoka source preview renderer |
| `build_christie_source.py`, `christie_fit_probe.py`, `christie_sleeve_gloss.py`, `build_clover_christie.py`, `clover_christie_glb.py` | Christie Source retarget + TPP/FPS pack, and experimental Clover-Christie GLB intake + TPP pack |
| `las_outfit_pack.py`, `dist_paths.py` | shared registration, hook, localization, unit/object XML, zip, glove-adapter companion, and canonical `dist/` path map |
| `diesel_model.py` | Diesel `.model` codec; change it only with the round-trip tests green |
| `vpk.py`, `source_model.py`, `vtf.py`, `dds_encode.py`, `source_to_obj.py` | Source readers (VPK, MDL 44–49 + VVD + VTX, VTF), DDS writers, and Source-to-OBJ converter |
| `skeleton_map.json`, `las_target_skeleton.json` | Source → PD2 bone map; the PD2 rig and object names |
| `segment_fit.py`, `render_mesh_skeleton.py`, `preview.py` | fit measurements and renders the builders call |
| `diagnose_mesh.py`, `neck_junction.py`, `uv_check.py`, `audit_metrics.py`, `elbow_before_after.py`, `glove_check.py`, `review_christie_idle.py`, `pose_zoom.py` | diagnostics for built packs, off the build path; each docstring carries its command |
| `pose_preview.py`, `preview_textured.py`, `shellview.py` | what those diagnostics render with: the arms-down pose and two rasterisers, one lit, one flat per face |
| `gma.py`, `smd.py`, `inspect_gma.py`, `inspect_textures.py` | GMod/Source addon inspection and SMD export, off the build path |
| `mip_audit.py` | for the two Miranda textures the build encodes itself: which mip level is on screen at which distance, how far each level is from the picture it stands for, and the before/after render (`make -sC tools/pd2-las audit`) |
| `Makefile`, `status.py`, `recover_env.sh`, `extract_2b.py`, `pins.txt` | the commands above, the state of the distribution packs, environment (`env` runs `recover_env.sh`), where the 2B pack is unpacked, and the pinned Pillow/NumPy versions |
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
| **Variants** change only what they claim: the busty pack is the base pack plus the chest, with the same head, arms and textures | `test_variants_change_only_what_they_claim` |
| **Own hands:** a pack keeps "Default" gloves from spawning over its own arms — its modelled hands, or the cut where a `palm_cut` pack removed them (both OfficeSuite packs, 4 cm into the palm since D62) — and ships no bare-forearm adapter | `test_own_hands_packs_never_draw_a_default_glove` |
| **Whole character:** a pack with its own head registers `replace_all`, hides the mask and binds that head to the head end of the rig, not the hips | `test_whole_character_packs_bring_their_own_head` |

## Do not

- Do not copy the 2B pack's defects (an unregistered `ss.model`, empty
  `cooked_physics` files, `Hooks` in `main.xml` where the folder is `hooks/`).
- Do not apply `tools/pd2-port`'s vertex-normal winding repair here: these
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

1. In-game verification (`docs/pd2-las/in-game-checklist.md`), which needs a human with PAYDAY 2, SuperBLT,
   BeardLib and LAS: `Miranda_L4D2_LAS`, `Christie_LAS`, `Christie_Clover_LAS`, `OfficeSuite_Head`, jewelry swap,
   the D60 palm cut (no vanilla skin at the wrist, no glove by default, a chosen glove winning) in both packs, and — audio, no LAS — `Miranda_Lawson_VO_over_Hila`:
   no bark has been heard in game yet, and the checklist's Log Sounds step is how a missed one shows up.
2. The native Hila body/head pack awaits its own [in-game check](../../docs/pd2-las/in-game-checklist.md#native-hila-body--head-override-no-las); it needs neither LAS nor BeardLib.
3. Gloss, measured and not fixed (`docs/audits/2026-11-11-miranda-mips-and-object.md`): full-gloss texels in
   the Miranda packs' `body_df`/`head_df`; no in-game record of `Miranda_Romance_LAS` or the eleven head packs.

## Further reading

- The sibling pipelines (`tools/pd2-port/`, `tools/build_joy_head_mods.py`): [`tools/README.md`](../README.md)
- Why it is built this way: `docs/pd2-las/DECISIONS.md`; dated audits: `docs/audits/`; renders: `docs/renders/README.md`
- The tracked bytes, what was seen in game and when, dead ends: `docs/pd2-las/HANDOFF.md`
- LAS runtime contract and gotchas: `knowledge/games/payday-2/las-armor-skin-outfit.md`
- Chest morph: `docs/pd2-las/CHEST-VARIANT.md`; retarget and matrix conventions: the `build_models.py` docstring, `retarget_maps`
