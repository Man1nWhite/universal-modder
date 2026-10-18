# Lawson pack repair journal

## 2026-10-18 — mod manager lists packs, models remain vanilla

- Report: all three characters retain their faces/suits; packs enabled; BLT present;
  PocoHUD works. Exact loader/game versions and installation paths unknown.
- Searched local knowledge base for PAYDAY 2: no matching prior note.
- Inspected all tracked dist ZIPs: each contains 2 models, 2 material configs,
  19 textures and a README; no main.xml. README wrongly says to install under
  mods/mod_overrides and that BeardLib is optional. It also claims in-game success
  without available evidence.
- Compared material paths with the existing local character object references;
  the packaged material directories agree with those references.
- Chosen route: fix asset-override packaging, not Lua gameplay hooks or geometry.
  Source of truth: BeardLib 5.2.0 source at
  95eb1c0c84e3f07d36f28a5e69197ec3b5c59046 (see README links).
- Added shared metadata generation to build_package2.py and a standard-library
  metadata-only ZIP repair command. All packs now carry main.xml texture entries,
  correct assets/mod_overrides instructions, explicit SuperBLT/BeardLib requirements,
  conflict/restart diagnostics and honest verification limits.
- Repaired the existing tracked archives. Compared every original asset with
  git show HEAD:dist/<archive>: all 23 asset payloads per pack are byte-identical.
- Tests: 10 packaging tests pass; full suite 159 passed, 5 skipped. Knowledge-base
  validation passes. No game launched, loaders installed, user files changed,
  commits pushed, or PRs opened.
- Next oracle: user installs one corrected pack, restarts, selects matching
  character/default outfit and supplies a menu screenshot. Back up saves before
  offline heist testing. If unchanged, request full install path and loader logs.
  Model deformation, texture orientation, facial animation and multiplayer remain
  unverified; packaging validation alone cannot establish that they work.

## 2026-10-18 — startup crash after moving packs to assets/mod_overrides

- Report: once installed under `PAYDAY 2\assets\mod_overrides\`, PAYDAY 2 crashes
  at startup / character preview when loading the Lawson `.model` overrides.
- Inspected all 6 `.model` files inside `dist/lawson_*.zip` alongside the vanilla
  reference models (`clover/`, `Bonie/`, `Sydney/`) and upstream
  `diesel-modding/payday2-model-tool` (`SkinBones.cs`, `Bones.cs`, `GltfImporter.cs`).
- Root cause: `build_character.py` and `build_model.py` populated
  `SkinBones.bone_mappings` with skeleton `Object3D` section IDs (`pal_ids`) instead
  of 0-based local indices (`0 .. len(pal_ids) - 1`) into `SkinBones.object_ids`:
  - `dist/lawson_bonnie.zip`: 4 rebuilt `SkinBones` sections (`230, 236, 242, 248`)
    per `.model` had max index `98` vs bone counts `24, 6, 5, 32`.
  - `dist/lawson_clover.zip`: 6 rebuilt `SkinBones` sections (`418, 424, 430, 436, 442, 448`)
    per `.model` had max index `152` vs bone counts `28, 5, 32, 5, 5, 6`.
  - `dist/lawson_sydney.zip`: 5 rebuilt `SkinBones` sections (`239, 245, 251, 257, 263`)
    per `.model` had max index `99` vs bone counts `26, 5, 32, 6, 6`.
- Fixed `build_character.py` and `build_model.py` to write `0 .. len(pal_ids) - 1`
  into each `SkinBones` mapping set.
- Added `tools/pd2-port/repair_skin_palettes.py` and repaired all 6 `.model` files
  across `dist/lawson_bonnie.zip`, `dist/lawson_clover.zip`, and
  `dist/lawson_sydney.zip` in place, updating `README.txt` and `main.xml` to
  packaging revision 1.2 while preserving all geometry, weights, inverse bind
  matrices, material configs, and `.texture` files.
- Expanded `tests/test_pd2_packages.py` to validate `SkinBones` palette ranges and
  vertex blend indices across all shipped `.model` files and test in-place repair.
- Next oracle: user extracts the updated `dist/lawson_*.zip` into
  `PAYDAY 2\assets\mod_overrides\`, launches PAYDAY 2, and verifies whether the
  character preview loads without crashing and deforms properly.
