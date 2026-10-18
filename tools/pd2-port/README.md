# PAYDAY 2 Lawson character packs

## Characters unchanged even though the mod manager lists the packs?

The original ZIP instructions were wrong: **asset overrides go under
`PAYDAY 2\assets\mod_overrides\`, not `PAYDAY 2\mods\mod_overrides\`.**
PocoHUD is a Lua mod; it working does not prove that asset overrides load.

These packs also introduce **new texture paths**, not only replacements for existing
assets. The original ZIPs omitted their registration manifest and incorrectly called
BeardLib optional. Packaging revision 1.1 includes `main.xml` with explicit BeardLib
`AddFiles` entries for all 19 custom textures.

### Install the corrected ZIPs

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

**Verification limit:** archive structure, material texture references, and manifest
coverage are tested automatically. These fixes do not prove that the mesh, rig,
animations, masks, or multiplayer work. No PAYDAY 2 installation is available in
this development environment. The earlier README's in-game success claims have
been removed. Test offline first.

## Maintaining the packages

`build_package2.py` is the current three-character staging builder. It now writes
both `main.xml` and `README.txt` through `package_metadata.py`. `build_package.py`
is the older Clover-only prototype, not the release builder.

To repair metadata on an existing local set of archives without rebuilding models
or textures (Python standard library only):

```sh
python tools/pd2-port/package_metadata.py dist/lawson_bonnie.zip dist/lawson_clover.zip dist/lawson_sydney.zip
python -m pytest -q tests/test_pd2_packages.py
```

The command updates the ZIPs in place atomically. It changes only `README.txt` and
`main.xml`; asset payloads are preserved. Archive compression may change. Keep your
own backup if you need the original ZIP bytes. Do not redistribute third-party
assets without the necessary rights.

The manifest registers new textures with `force="false"`; the three packs share
identical maps, so another installed pack need not register the same path again.
Existing `.model` and `.material_config` paths remain native overrides.

### Loader source checked

BeardLib 5.2.0 source at commit `95eb1c0c84e3f07d36f28a5e69197ec3b5c59046`:

- [`main.xml`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/main.xml): asset override directory.
- [`Classes/Frameworks.lua`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Classes/Frameworks.lua): `main.xml` discovery.
- [`Modules/Utils/AddFilesModule.lua`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Modules/Utils/AddFilesModule.lua) and
  [`Classes/Managers/PackageManager.lua`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Classes/Managers/PackageManager.lua): registration syntax and `force` behavior.
