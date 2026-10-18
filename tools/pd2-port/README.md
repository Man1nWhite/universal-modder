# PAYDAY 2 Lawson character packs

## Characters unchanged or crashing at startup when the packs load?

Two defects existed in the earlier Lawson archives:

1. **Wrong installation path and missing texture manifest (fixed in revision 1.1):**
   Asset overrides go under `PAYDAY 2\assets\mod_overrides\`, not
   `PAYDAY 2\mods\mod_overrides\`. PocoHUD is a Lua mod; it working does not prove
   that asset overrides load. Because these packs also introduce **new texture
   paths** (`units/payday2/characters/shared_textures/lawson/*`), BeardLib is
   required and `main.xml` must register all 19 custom textures via `AddFiles`.
2. **Corrupted `SkinBones` bone-palette mappings in `.model` files (fixed in revision 1.2):**
   Once the packs were placed in `PAYDAY 2\assets\mod_overrides\` so the engine
   actually loaded the `.model` overrides, `build_character.py` and `build_model.py`
   had written skeleton `Object3D` section IDs (up to `98` in Bonnie, `152` in
   Clover, and `99` in Sydney) into `SkinBones.bone_mappings` instead of 0-based
   local indices (`0 .. count - 1`) into `SkinBones.object_ids`. That caused
   PAYDAY 2's native skinning code to read past the end of each `SkinBones` matrix
   array and crash at startup / character display.

### Install the corrected ZIPs (revision 1.2)

1. Close PAYDAY 2 completely.
2. Use **SuperBLT and BeardLib**. Legacy BLT is not enough. Install BeardLib following
   [its release instructions](https://github.com/simon-wh/PAYDAY-2-BeardLib/releases);
   its `mod.txt` belongs at `PAYDAY 2\mods\BeardLib\mod.txt`.
3. Move old `lawson_*` folders outside the game as backups, including any copies in
   `mods`, `mods\mod_overrides`, or `assets\mod_overrides`. Do not overlay a new copy
   onto a manager-generated wrapper or leave duplicate copies installed.
4. Extract **one** corrected ZIP into `PAYDAY 2\assets\mod_overrides\`. For example:

   ```text
   PAYDAY 2/
     mods/
       BeardLib/
         mod.txt
       PocoHud3/              (leave your existing HUD installation alone)
     assets/
       mod_overrides/
         lawson_clover/
           main.xml
           README.txt
           units/
             payday2/
               characters/...
   ```

   No extra `lawson_clover/lawson_clover` directory level. Bonnie and Sydney use
   the same installation pattern with their own folder names.
5. Temporarily move conflicting character replacements outside the game. Restart,
   choose the matching character and the default outfit/two-piece suit, and check
   the unmasked character preview. This replaces a character; it adds no selectable
   outfit. Back up saves before an offline heist test. First-person arms are not a
   reliable test of a third-person replacement.
6. If unchanged, provide a screenshot showing the full path to `main.xml`, the game
   version, SuperBLT/BeardLib versions, and the newest `mods\logs\` log, if present.
   If it crashes, also provide `%LOCALAPPDATA%\PAYDAY 2\crash.txt`, if present.

**Verification limit:** archive structure, material texture references, manifest
coverage, and `.model` `SkinBones` / vertex blend-index bounds are tested
automatically. These fixes do not prove that in-game mesh deformation, rig
alignment, animations, masks, or multiplayer work. No PAYDAY 2 installation is
available in this development environment. Test offline first.

## Maintaining the packages

- `build_character.py` and `build_model.py` now emit 0-based local `0 .. len(pal_ids) - 1`
  indices in `SkinBones.bone_mappings`.
- `build_package2.py` is the three-character staging builder and writes `main.xml`
  and `README.txt` through `package_metadata.py`.
- `repair_skin_palettes.py` inspects (`--check`) or repairs in place both
  `SkinBones.bone_mappings` inside `.model` files and `main.xml` / `README.txt`
  inside `dist/lawson_*.zip` archives (using only the Python standard library):

```sh
python tools/pd2-port/repair_skin_palettes.py dist/lawson_bonnie.zip dist/lawson_clover.zip dist/lawson_sydney.zip
python tools/pd2-port/repair_skin_palettes.py --check dist/lawson_bonnie.zip dist/lawson_clover.zip dist/lawson_sydney.zip
python -m pytest -q tests/test_pd2_packages.py
```

The command updates the ZIPs in place atomically, rewriting only the out-of-range
`SkinBones` mapping tables in the `.model` files and refreshing `README.txt` and
`main.xml`; vertex geometry, weights, inverse bind matrices, material configs, and
textures are preserved.

The manifest registers new textures with `force="false"`; the three packs share
identical maps, so another installed pack need not register the same path again.
Existing `.model` and `.material_config` paths remain native overrides.

### Upstream references checked

- BeardLib 5.2.0 source at commit `95eb1c0c84e3f07d36f28a5e69197ec3b5c59046`:
  - [`main.xml`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/main.xml): asset override directory.
  - [`Classes/Frameworks.lua`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Classes/Frameworks.lua): `main.xml` discovery.
  - [`Modules/Utils/AddFilesModule.lua`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Modules/Utils/AddFilesModule.lua) and
    [`Classes/Managers/PackageManager.lua`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Classes/Managers/PackageManager.lua): registration syntax and `force` behavior.
- `diesel-modding/payday2-model-tool` (`PD2ModelParser/Sections/SkinBones.cs`,
  `PD2ModelParser/Sections/Bones.cs`, `PD2ModelParser/Importers/GltfImporter.cs`):
  `SkinBones.Bone_mappings` stores `0 .. Objects.Count - 1` local palette indices,
  repeated `1 + RenderAtoms.Count` times.
