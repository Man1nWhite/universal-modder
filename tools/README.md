# tools/ — PAYDAY 2 character & head-replacement build pipelines

Three PAYDAY 2 pipelines live in `tools/`, producing the tracked deliverables in **`dist/`**:

1. **`tools/pd2-port/`** — rigged COLLADA character → full-body LAS outfit. The pipeline is not tied to one character; the port it ships is Miranda Lawson from the Mass Effect 2 *Romance* archive → **`dist/lawson_las.zip`**. Start at `tools/pd2-port/README.md` (what is reusable, what a port of another character changes); the state of the shipped port is in `tools/pd2-port/STATUS.md`.
2. **`tools/pd2-las/`** — compiled Source-engine model (MDL/VVD/VTX) → LAS outfit, re-authored onto the 2B template skeleton: **`dist/Miranda_LAS.zip`** from the L4D2 archive, its larger-chest variant **`dist/Miranda_Busty_LAS.zip`** (`build_busty_variant.py`, its own `LegendaryArmours.miranda_busty` entry), and the body-only **`dist/Christie_LAS.zip`** / **`dist/Christie_LAS_Slim.zip`** (`build_christie_las.py`). Start at `tools/pd2-las/README.md` and `python3 tools/pd2-las/status.py`; the dated state is in `docs/pd2-las/HANDOFF.md`.
3. **`tools/build_joy_head_mods.py`** — Nine vanilla-heister head-replacement `mod_overrides` packages (**Miranda L4D2** and **Miranda ME2 Romance** variants over **Joy**, **Clover**, **Bonnie**, and **Sydney**, plus **Witcher 3 Geralt of Rivia** from `models/Geralt.7z` over **Rust**), modeled on `Ada Wong over Joy.7z` and `Heister - FPS Gloves in TPS 2.zip`:
   - **`dist/Miranda_L4D2_over_Joy.zip`** & **`dist/Miranda_Romance_over_Joy.zip`**
   - **`dist/Miranda_L4D2_over_Clover.zip`** & **`dist/Miranda_Romance_over_Clover.zip`**
   - **`dist/Miranda_L4D2_over_Bonnie.zip`** & **`dist/Miranda_Romance_over_Bonnie.zip`**
   - **`dist/Miranda_L4D2_over_Sydney.zip`** & **`dist/Miranda_Romance_over_Sydney.zip`**
   - **`dist/Geralt_over_Rust.zip`**

| | `tools/pd2-port/` — COLLADA → LAS | `tools/pd2-las/` — Source MDL → LAS | `tools/build_joy_head_mods.py` — Heister Head Mods |
| --- | --- | --- | --- |
| Source | a rigged COLLADA archive; shipped port: `models/PC _ Computer … Miranda Lawson (Romance).zip`. Rig contract extracted once from `references/2b.rar` | `models/l4d2_miranda_lawson_1.zip`, `references/Christie.zip` + the `references/2b.rar` templates | `models/*` + `references/Ada Wong over Joy.7z` + `references/Heister - FPS Gloves in TPS 2.zip` |
| Output in `dist/` | `dist/lawson_las.zip` (tracked, sha256-pinned) | `dist/Miranda_LAS.zip`, `dist/Miranda_Busty_LAS.zip`, `dist/Christie_LAS.zip`, `dist/Christie_LAS_Slim.zip` (tracked, sha256-pinned) | `dist/Miranda_{L4D2,Romance}_over_{Joy,Clover,Bonnie,Sydney}.zip` + `dist/Geralt_over_Rust.zip` (tracked, sha256-pinned) |
| Pack layout | `Lawson_LAS/assets/units/…` (LAS outfit) | `Miranda_LAS/assets/units/…` and the like (LAS outfits) | `{Miranda …, Geralt} over {Joy,Clover,Bonnie,Sydney,Rust}/units/…` |
| Install | `assets/mod_overrides/` (needs SuperBLT + BeardLib + LAS) | `assets/mod_overrides/` (needs SuperBLT + BeardLib + LAS) | `assets/mod_overrides/` (vanilla heister head replacement) |
| `.model` dialect | DODB container, unshifted channel types, packed normals | plain container, shifted types, float normals (byte-exact to the game-tested 2B template) |
| Rig work | `rig_target.py` + `reference/las_rig.json` (anatomically partitioned similarity retarget) | `skeleton_map.json` + anatomically partitioned similarity retarget in `build_models.py` |
| Verification | `check_all.py` (mutation-tested; `--full` adds the test suite and the skip budget), release CI | one test per invariant on the tracked packs (`tests/test_pd2_las_invariants.py`), the authoring suites, `test_diesel_model` byte round-trips |

## Why they are not merged (measured, 2026-10-19)

- **No code to deduplicate.** Same-job module pairs (codec, pack builder, DDS,
  preview) share 2–5% of lines and one function name (`hash64`). They are
  independent implementations, not copies.
- **Different format dialects.** The two Diesel codecs each encode a verified
  dialect (see the table). A merged codec would be one file with two dialects
  inside, and a bug there breaks **both** byte-exact contracts at once.
- **Different release contracts.** The pack `tools/pd2-port/` ships is tracked
  with a sha256 pin, built by `.github/workflows/lawson-las.yml` from hardcoded
  `tools/pd2-port/…` paths, with release notes under
  `tools/pd2-port/releases/`. Moving those files breaks the release pipeline
  and the checksum gate for zero functional gain.
- **The right sharing already exists**: one test bed (`tests/`, 234 tests),
  one knowledge base (`knowledge/`), and cross-audited check semantics
  (`tools/pd2-port/check_mesh_geometry.py::analyse` handles both mesh
  topologies — welded vs corner-split).

## Rule of thumb for future work

- Porting a *method* across routes (e.g. the divergence-filter retarget into
  `tools/pd2-port/rig_target.py`): yes — reimplement in the target tree's
  dialect, keep both suites green.
- Moving or unifying *files* across the two trees: no — see above. If a third
  route ever appears, extract a shared codec **then**, with both existing
  dialects as test fixtures.
