# tools/ — two independent tool trees, on purpose

Two Lawson LAS routes live side by side. They answer the same product brief
from different source assets, and their tool trees are **deliberately not
merged**. Read `docs/pd2-las/HANDOFF.md` (L4D2 route) and
`tools/pd2-port/STATUS.md` (ME2 route) for each pipeline's own start-here.

| | `tools/pd2-port/` — ME2 route | `tools/pd2-las/` — L4D2 route |
| --- | --- | --- |
| Source | ME2 *Romance* COLLADA zip | `l4d2_miranda_lawson_1.zip` (MDL/VVD/VTX in a VPK) |
| Output | `dist/lawson_las.zip` (tracked, sha256-pinned) | `build/pd2-las/Miranda_LAS.zip` (reproducible) |
| Pack layout | `Lawson_LAS/units/…` → `assets/mod_overrides/` | `Miranda_LAS/assets/units/…` → `mods/` (SuperBLT) |
| `.model` dialect | DODB container, unshifted channel types, packed normals | plain container, shifted types, float normals (byte-exact to the game-tested 2B template) |
| Rig work | `rig_target.py` + `reference/las_rig.json` (per-bone fits) | `skeleton_map.json` + divergence-filter Umeyama in `build_models.py` |
| Verification | `check_all.py` (5 stages, mutation-tested), release CI | 234-test suite incl. `test_diesel_model` byte round-trips |

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
