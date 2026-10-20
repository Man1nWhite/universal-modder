# tools/ — PAYDAY 2 Miranda Lawson build pipelines

Three PAYDAY 2 pipelines live in `tools/`, producing the four tracked deliverables in **`dist/`**:

1. **`tools/pd2-port/`** — Full-body LAS outfit from the Mass Effect 2 *Romance* COLLADA archive → **`dist/lawson_las.zip`** (`9,101,185` bytes). See `tools/pd2-port/STATUS.md`.
2. **`tools/pd2-las/`** — Full-body LAS outfit from the L4D2 Source MDL/VVD/VTX archive → **`dist/Miranda_LAS.zip`** (`5,844,737` bytes). See `docs/pd2-las/HANDOFF.md`.
3. **`tools/build_joy_head_mods.py`** — Two Joy head-replacement `mod_overrides` packages modeled on `Ada Wong over Joy.7z` → **`dist/Miranda_L4D2_over_Joy.zip`** (`10,496,415` bytes) and **`dist/Miranda_Romance_over_Joy.zip`** (`10,660,971` bytes).

| | `tools/pd2-port/` — ME2 LAS | `tools/pd2-las/` — L4D2 LAS | `tools/build_joy_head_mods.py` — Joy Head Mods |
| --- | --- | --- | --- |
| Source | ME2 *Romance* COLLADA zip + `2b.rar` | `l4d2_miranda_lawson_1.zip` + `2b.rar` | Both sources + `Ada Wong over Joy.7z` |
| Output in `dist/` | `dist/lawson_las.zip` (tracked, sha256-pinned) | `dist/Miranda_LAS.zip` (tracked, sha256-pinned) | `dist/Miranda_L4D2_over_Joy.zip` & `dist/Miranda_Romance_over_Joy.zip` (tracked, sha256-pinned) |
| Pack layout | `Lawson_LAS/assets/units/…` (LAS outfit) | `Miranda_LAS/assets/units/…` (LAS outfit) | `Miranda {L4D2,Romance} over Joy/units/pd2_dlc_joy/…` (vanilla Joy head override) |
| Install | `assets/mod_overrides/` (needs SuperBLT + BeardLib + LAS) | `assets/mod_overrides/` (needs SuperBLT + BeardLib + LAS) | `assets/mod_overrides/` (vanilla Joy head replacement) |
| `.model` dialect | DODB container, unshifted channel types, packed normals | plain container, shifted types, float normals (byte-exact to the game-tested 2B template) |
| Rig work | `rig_target.py` + `reference/las_rig.json` (anatomically partitioned similarity retarget) | `skeleton_map.json` + anatomically partitioned similarity retarget in `build_models.py` |
| Verification | `check_all.py` (5 stages, mutation-tested), release CI | 235-test suite incl. `test_diesel_model` byte round-trips |

## Why they are not merged (measured, 2026-10-19)

- **No code to deduplicate.** Same-job module pairs (codec, pack builder, DDS,
  preview) share 2–5% of lines and one function name (`hash64`). They are
  independent implementations, not copies.
- **Different format dialects.** The two Diesel codecs each encode a verified
  dialect (see the table). A merged codec would be one file with two dialects
  inside, and a bug there breaks **both** byte-exact contracts at once.
- **Different release contracts.** The ME2 pack is tracked with a sha256 pin,
  built by `.github/workflows/lawson-las.yml` from hardcoded
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
