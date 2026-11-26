# tools/ — the three PAYDAY 2 pipelines

Commands for all of them are make targets in `tools/pd2-las/Makefile`, listed in `AGENTS.md`;
`make -sC tools/pd2-las status` prints every pack with the target that rebuilds it. Which archive feeds which
pack: `references/README.md`. ZIPs are grouped by character in `dist/`; their internal mod
folders remain the installable names. The Hila Romance head's skin diffuse is matched to Honoko's
body and therefore changes with that head on other bodies too.

| | `tools/pd2-port/` — COLLADA → LAS | `tools/pd2-las/` — Source MDL / COLLADA / GLB → LAS | Native heister overrides |
| --- | --- | --- | --- |
| Builds | a full-body LAS outfit from a rigged COLLADA character. Not tied to one character; the port it ships is Miranda Lawson from the Mass Effect 2 *Romance* archive, `Miranda_Romance_LAS` | LAS outfits re-authored onto the 2B template skeleton: `Miranda_L4D2_LAS`, its larger-chest variant `Miranda_L4D2_Busty_LAS` (its own `LegendaryArmours.miranda_busty` entry), the body-only `Christie_LAS` (Source MDL/VVD/VTX), the experimental body-only `Christie_Clover_LAS` (rigged GLB), plus the `OfficeSuite` and `OfficeSuite_Head` outfits from COLLADA with TMC skinning | eleven head replacements over the vanilla heisters, modeled on `Ada Wong over Joy.7z` and `Heister - FPS Gloves in TPS 2.zip`: Miranda (L4D2 and ME2 Romance heads) over Joy, Clover, Bonnie, Sydney and Hila, and Geralt over Rust. It takes the L4D2 face from `dist/Miranda_L4D2/Miranda_L4D2_LAS.zip`, so it runs after that pack. `tools/build_hila_body_mod.py` builds the standalone OfficeSuite + Miranda Romance body/head override from the two assembled donors; the audio pack is Miranda barks over Hila's `rb21` voice lines — `tools/build_hila_stream_mod.py` writes one Wwise IMA ADPCM `.stream` per voice-line id (the id-keyed route, format in `tools/pd2-las/wwise_ima.py`), on the clip, cut and level helpers in `tools/hila_voice_clips.py`; since 2026-11-25 two more packs of the same route ship: `Geralt_VO_over_Rust_Stream` and `Arivus_VO_over_Hoxton_Stream` (`tools/build_character_stream_mod.py`, one pack per purpose-authored bark set, writing the same shared ids — install only one; [packaging and install contract](../docs/pd2-voice-mod-install.md) §8); the BeardLib `SoundsModule` variant it replaced was dropped on 2026-11-25 (D61) |
| Voice-line id tables and the re-key | `tools/build_stream_tables.py` (make `voices_tables`) writes `voice_lines_vox/targets/<target>_shared_regular_vox.csv` — slot → bank → id for Rust and Old Hoxton, equal to the tracked zips' file names — plus the measured `char_rust` table; `tools/build_character_stream_mod.py --bank char_rust` (make `voices_char_rust`) re-keys Geralt's takes onto Rust's own bank from `voice_lines_vox/geralt/char_rust_ids.csv` and refuses until that map names every id; the two banks and both open questions are in [the stream-table note](../docs/pd2-voice-stream-tables.md) (D73, D74); `tools/import_voiceline_sheet.py` (make `voices_sheets SHEET=<export>.csv [WANT=Rust] [LEADS=1]`) turns a community `id | who | what` sheet into `voice_lines_vox/sheets/<tab>.csv` plus word-overlap slot *leads* — a lead is not a mapping, and a `regular_vox` sheet never names `char_rust` ids (D75) |
| Start at | `tools/pd2-port/README.md`; the dated state of the shipped port is `tools/pd2-port/STATUS.md` | `tools/pd2-las/README.md`; the dated record is `docs/pd2-las/HANDOFF.md` | the docstring of `tools/build_joy_head_mods.py`. For the native Hila body/head pack, see [its install notes](../docs/renders/honoka/model/over-hila/README.md). Tracked renders: `docs/renders/README.md`; scratch preview sheets: `build/previews/` (`tools/render_mod_previews.py`) |
| Pack layout | `Lawson_LAS/assets/units/…` | `Miranda_LAS/assets/units/…` and the like | `{Miranda …, Geralt} over {Joy,Clover,Bonnie,Sydney,Hila,Rust}/units/…`; Geralt is two atoms, `mtr_head` and an `ALPHA_MASKED` `mtr_hair` |
| Install | extract into `PAYDAY 2\assets\mod_overrides\`; needs SuperBLT + BeardLib + Legendary Armour Skins | the same | extract into `PAYDAY 2\assets\mod_overrides\` (native replacement, no loader or LAS) |
| `.model` dialect | DODB container, unshifted channel types, packed normals | plain container, shifted types, float normals (byte-exact to the game-tested 2B template) | |
| Rig work | `rig_target.py` + `reference/las_rig.json` | `skeleton_map.json` + the retarget in `build_models.py` | |
| Verification | `check_all.py` (mutation-tested), release CI | one test per invariant on the tracked packs (`tests/test_pd2_las_invariants.py`), the authoring suites, byte round-trips of the codec | |

## Invariants that hold in every pipeline (do not break)

A pipeline's own invariants, and the tests that enforce them, are in its README.

1. **Two Diesel `.model` Parsers**:
   - `tools/pd2-las/diesel_model.py` (`dm.ModelFile.read` + `dm.decode_geometry` / `dm.decode_topology` / `dm.decode_model_data`) decodes any legacy PAYDAY 2 `.model` (`2b.model`, `miranda.model`, `npc_criminal_joy_1.model`).
   - `tools/pd2-port/dmodel.py` (`DieselModel.from_bytes`) only populates `geo.weights3` for the models `tools/pd2-port/las_model.py` writes (such as `lawson.model`).
2. **Global `Topology` Indices in Multi-Atom Drawables**:
   - In Diesel `.model` files (`npc_criminal_joy_1.model`, `miranda.model`), triangle indices in `Topology` for `RenderAtom` `i` are **global vertex indices** in `[base_vertex, base_vertex + slice_len - 1]`, never local `0 .. slice_len - 1`.
3. **UV Coordinate Convention (`v_diesel = 1.0 - v_img`)**:
   - Diesel `Geometry.uv0` stores OpenGL/COLLADA bottom-up `v` (`v = 1.0` is top row `y_img = 0` of the DDS image; `v = 0.0` is bottom row `y_img = H - 1`).
   - When packing a 2×2 atlas at top-down quadrant `(qx, qy) ∈ {0, 1}²`, map `u_diesel = 0.5 * qx + 0.5 * u_img` and `v_diesel = 1.0 - (0.5 * qy + 0.5 * v_img)`.
4. **DXT5 Diffuse Alpha = Specular/Gloss & DXT5nm Normal Maps**:
   - In `generic:...:DIFFUSE_TEXTURE:NORMALMAP:...` shaders (without `ALPHA_MASKED`), the diffuse texture's alpha channel is **gloss/specular intensity** (`alpha = 255` makes skin/fabric look like wet plastic in-game). Keep diffuse alpha low (`<= 28` or normal-slope attenuated).
   - Diesel normal maps are **DXT5** with X in alpha and Y in green (Y+: a DirectX-style source has its green inverted). The shader reads only those two channels; both writers here, `dds.pd2_normal_channels(arr, invert_y=True)` in `tools/pd2-port/` and `swizzle_source_normal_dxt5_to_pd2` in `tools/pd2-las/dds_encode.py`, fill red with 255 and blue with 0.
5. **Standing-Pose Shoulder/Arm Alignment & Elbow Hinge Axis (Full-Body LAS)**:
   - PAYDAY 2's in-game standing pose swings `RightShoulder`/`LeftShoulder` ~19° downward from bind pose (`z: 147→142 cm`). Retargeting must align clavicle/upper-arm/forearm directions in the **animated standing pose**, and the elbow has to bend about the axis PD2 bends it about so it never shears.
   - On the PD2 rig that axis is the `ForeArm`'s **local Y**. Measured on the 2B skeleton: the bind elbow is bent 72.1°, local Y is the normal of that bend, and local X runs along the forearm, so a rotation about X is a twist that leaves the elbow angle unchanged.
6. **Joy Head-Replacement (`mod_overrides`) Collar & Skinning Contract**:
   - `npc_criminal_joy_1.model` (`and identical npc_criminal_joy_1_menu.model`) uses `g_head_mask_off` (`id=120`, `geo=228`, `topo=229`) and `g_head` (`id=121`, `geo=233`, `topo=234`), both bound to `SkinBones 44` (`['Spine2', 'Neck', 'Head']`).
   - Joy's `g_body` hoodie collar (`z ∈ [151, 160]`) is weighted `95.5%` to `Spine2` (`0% Neck`), with an inner collar cone at `y ≈ 7.2–8.5 cm` and outer V-neck lapel at `y ∈ [12.9, 15.5] cm`. Keep lower-throat vertices in the collar channel `y ∈ [9.0, 10.6] cm` and weight `z <= 156 cm` `100%` to `Spine2` so the neck never separates from the collar when `Neck`/`Head` rotate.

## Sharing code between the trees

Two tools that do one job may be merged only if no byte of a tracked pack changes. What was merged, what was
left apart and why, with the measurements: `docs/audits/2026-11-12-tool-merge.md`. A merge is held to
`make -sC tools/pd2-las green` and to `tests/test_one_implementation.py`.

- The two `.model` dialects in the table stay two writers: each is byte-exact to its own contract.
- `tools/pd2-port/` is released from hardcoded paths by `.github/workflows/lawson-las.yml`, with the notes
  of a release in `tools/pd2-port/releases/lawson-las-v<N>.md`: moving its files breaks the release.
- Porting a method across the trees is fine: reimplement it in the target tree's dialect and keep both
  suites green.

## Looking at a compiled unit: `.model` → `.glb` + `.dds`

`tools/pd2-las/model_to_glb.py` writes a glTF 2.0 `.glb` (and the unit's `.texture` files as
`.dds` — a PAYDAY 2 `.texture` is a DDS buffer) from a `.model`, a directory or a pack. It is the
one place a compiled unit leaves this tree in a form Blender, three.js or a phone can open:

    .venv/bin/python tools/pd2-las/model_to_glb.py dist/Arivus/Arivus_over_Hoxton.zip \
        -o build/arivus_glb --all-textures --skin

Its conventions — metres/y-up, the UV flip, global RenderAtom indices, DXT5nm → tangent-space RGB,
`ALPHA_MASKED` → `alphaMode: MASK`, and the bind-pose skin whose matrices compose to the identity —
are pinned by `tests/test_model_to_glb.py` on a synthetic unit, so the test needs no game asset.
The output derives from game bytes and may be committed at the owner's call (D74). The tracked
`dist/Arivus/Arivus_Head_over_Old_Hoxton_GLB.zip` is exactly this: `make -sC tools/pd2-las glb`
runs `tools/pd2-las/build_arivus_glb_pack.py`, which exports the head and its five `.dds` from the
tracked `Arivus_over_Hoxton.zip` with `model_to_glb.py`, writes a reproducible zip and its `.sha256`,
and `tests/test_arivus_glb_pack.py` pins the members to the source pack's bytes. Ad-hoc exports still
default to `build/`.
