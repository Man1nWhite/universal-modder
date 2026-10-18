# PAYDAY 2 Lawson character packs

## Choose a package

| Archive | Integration | Where it appears |
| --- | --- | --- |
| `lawson_outfit_BeardLib.zip` | **Standalone BeardLib-native `PlayerStyle`; no LAS** | Native Outfit / Player Styles selector: **Miranda Lawson (BeardLib)** |
| `lawson_outfit.zip` | Legacy **LAS-branded**, but its manifest also uses `PlayerStyle` | Legacy `lawson` style; retained unchanged |
| `lawson_bonnie.zip`, `lawson_clover.zip`, `lawson_sydney.zip` | Character asset replacements | Replaces the corresponding heister; no new outfit entry |

The new BeardLib variant is additive: its item ID, asset paths, icon bundle and
folder are independent of the legacy pack. The original four archives and
`2b.rar` are not rebuilt or modified. None of these packages is game-verified;
see the [repository audit](../../docs/audits/2026-10-18-repository-audit.md) for
the older packages' remaining limitations.

## Standalone BeardLib outfit

**Build output:** `dist/lawson_outfit_BeardLib.zip`. Requires **SuperBLT + BeardLib**
with the `PlayerStyle` module (API checked against BeardLib 5.2.0). **Legendary
Armour Skins / Wardrobe Mod is not required or bundled.** The source Clover ZIP
is a build input only; it does not have to be installed, and you do not have to
play as Clover to select this outfit.

### Install / equip

1. With the game closed, back up `assets/mod_overrides/` and your save/profile.
2. Extract the ZIP directly into `PAYDAY 2/assets/mod_overrides/`. Check this exact
   layout (no extra enclosing directory):

   ```text
   PAYDAY 2/
     mods/BeardLib/mod.txt
     assets/mod_overrides/
       Lawson_Outfit_BeardLib/
         main.xml
         README.txt
         CREDITS.txt
         BUILD_INFO.json
         loc/english.txt
         assets/units/mods/lawson_beardlib/...
         assets/guis/dlcs/lawson_beardlib/...
   ```

3. Open the native **Outfit / Player Styles** list in Inventory and select
   **Miranda Lawson (BeardLib)**, not a LAS armor-skin entry. Choose **Default
   gloves** to use the included hands. No extra outfit-unlocker is needed for
   this custom item.
4. Initially disable other character replacements/appearance mods. Check the
   preview, then an **offline** heist: FPS weapon alignment, reloads, movement,
   mask-on, armor/heister changes, switching back to a vanilla outfit and restart.
   Separate IDs prevent registration/resource collisions with the old outfit;
   they are not proof that all appearance mods work together.
5. To remove it, **equip a vanilla outfit first**, close the game, then remove
   only `assets/mod_overrides/Lawson_Outfit_BeardLib/`. Leave shared loaders and
   the original Lawson folders alone. Restore the backup if needed.

### Rebuild / checks

From the repository root, using Python 3.10+ with the project's Pillow/numpy
requirements and pytest installed:

```sh
python tools/pd2-port/build_outfit_beardlib.py
# Optional explicit inputs/output (defaults shown):
python tools/pd2-port/build_outfit_beardlib.py --source dist/lawson_clover.zip --icon "Lawson model/Miranda_face_d.png" --out dist/lawson_outfit_BeardLib.zip
python -m pytest -q tests/test_outfit_beardlib_pack.py tests/test_outfit_pack.py
```

The builder works from other working directories, refuses to overwrite the four
original archives / reference archive / inputs, writes atomically, and produces
a deterministic ZIP. `BUILD_INFO.json` records source/icon hashes, the checked
API commits and every other payload's SHA-256. The generated ZIP follows the
existing ignored `dist/` convention; game/model assets are not added to Git or
published by this change. Keep the private download, or regenerate it locally.

Implementation details:

- `PlayerStyle id="lawson_beardlib"`, global FPS/TPP unit fallback (no incomplete
  per-character allowlist), and both `body_replacement` /
  `third_body_replacement` with native boolean attributes.
- Full third-person mesh, separate FPS arms/hands on the supplied heister
  skeleton; unused vanilla drawables/material groups are pruned. The new FPS
  selector expands **one ring from an immutable arm-bound seed set**, so changing
  triangle order cannot flood-fill the torso. This does not make the cut watertight.
- Real `g_body` culling geometry with bounds covering retained mesh positions,
  complete render-atom material coverage including `shadow_caster`, and
  `DEPTH_SCALING` first-person shaders. Reference/material/index-range checks
  supplement (not repair globally) the older model validator.
- The 19 repaired input textures are unchanged. Two full-mip grayscale opacity
  maps are derived from the supplied hair/lash alpha, plus a flat normal for the
  alpha-masked lashes. No Clover-specific head/hair textures are required at
  runtime; only the game's standard hair cubemap remains an external material
  resource. Shader behavior still needs a visual check.
- Standard JSON localization, own outfit icon bundle, no runtime Lua hooks,
  updater, downloads, vanilla unit-path overrides, save edits or gameplay changes.

**Verification limits:** structural tests are not an engine test. This reuses the
already-rigged source, so rig deformation, UV seams, hand/weapon alignment,
materials, armor clipping, culling and animations are still unverified. Native
`PlayerStyle` replacement does **not** hide the separately equipped mask; mask
clipping is possible. Non-default gloves may override the supplied hands. VR,
individual heister proportions and online synchronization are untested; do not
assume unmodded peers can see the outfit. It is not a demonstrated equivalent of
the 2B reference. Input asset authorship/redistribution permissions remain
unresolved: this is a **private experimental derivative, not a cleared public
release** (see bundled `CREDITS.txt`).

## Characters unchanged or crashing at startup when the packs load?

Four defects existed in the earlier Lawson archives:

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
3. **Non-contiguous DODB section IDs and layout (fixed in revision 1.3):**
   Every vanilla `.model` has strictly contiguous section IDs `1 .. count` and a
   canonical section order (materials first, then the object/model tree, then one
   `[skinbones, geometry, topology, passthroughGP, topologyIP]` group per mesh in
   model order). `build_character.py` dropped whole mesh groups (leaving holes in
   `1 .. max_id`, so `max_id > count`: `450 > 417` in Clover, `250 > 228` in
   Bonnie, `265 > 237` in Sydney), spliced new groups into the middle of the
   model block, and appended new materials at the end of the file. Any
   engine-side section table indexed by ID then reads out of bounds — matching
   the access violation at `MenuSetup:load_packages()` in `crash.txt`. Revision
   1.3 renumbers all sections `1 .. count` in the vanilla order and remaps every
   internal reference. `g_body` also stacked hidden overlapping swim/underwear
   layers into one Topology of 73k indices (vanilla meshes stay under 18k);
   those two layers are dropped so the mesh fits 16-bit index limits.
4. **`.texture` files lacked mipmap pyramids (fixed in revision 1.3):**
   `build_package2.py` wrote mip 0 only (`dwMipMapCount = 0`, flags
   `0x00081007`, caps `0x00001000`) and mis-ordered some DXT5 colour endpoints
   (`c0 < c1`), which decoders read as the 3-colour mode with a transparent
   index — visible holes. Every `.texture` now carries the full DXT5 pyramid
   (flags `0x000A1007`, caps `0x00401008`, `dwMipMapCount = log2(size) + 1`,
   exactly like vanilla) and all blocks decode in the intended 4-colour mode
   (bit-exact repair: endpoints swapped and indices remapped, no re-encode).

### Install the corrected ZIPs (revision 1.3)

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
coverage, `.model` container layout / `SkinBones` / vertex blend-index bounds and
`.texture` mipmap pyramids are tested automatically (and the canonical layout is
verified to round-trip vanilla `.model` files byte-identically). These fixes do
not prove that in-game mesh deformation, rig alignment, animations, masks, or
multiplayer work. No PAYDAY 2 installation is available in this development
environment. Test offline first.

## Legacy LAS-branded outfit (`dist/lawson_outfit.zip`)

`build_outfit.py` and the original ZIP are retained unchanged. Despite the
`Lawson_LAS` folder and `wardrobe_mod` resource names, its actual registration is
BeardLib's native **`PlayerStyle`**, not a `LegendaryArmours` Lua skin. The name
alone does not make it use the same integration as `2b.rar`. Prefer the separate
[standalone BeardLib edition](#standalone-beardlib-outfit) above for the explicit
no-LAS variant and its additional checks. To reproduce the legacy payload:

```sh
python tools/pd2-port/build_outfit.py --source dist/lawson_clover.zip --out dist/lawson_outfit.zip
python -m pytest -q tests/test_outfit_pack.py
```

Layout mirrors the working "Jack Cooper - Legendary Armour Skin" pack
(`mod_overrides/Jack Cooper - Legendary Armour Skin` in `Vladik268/P2`):
`main.xml` + `localization/` + `assets/units/wardrobe_mod/armor_skins/{lawson,
lawson_fps}/` (`.model/.unit/.object/.material_config` each) + shared
`assets/units/wardrobe_mod/armor_skins/textures/` + a 128x128 DXT5 icon
without mips. The third-person model is the repaired model plus an empty
`co_box` locator (`culling_object="co_box"`); the first-person model keeps the
standard heister skeleton (`Hips`..fingers, `a_weapon_left_front/right_front`,
`aim` — verified against `jack_fps.model`) with only the arm chains
(`g_body` arm shell + `g_hands`). Requires `numpy` + `Pillow`; the source pack
must already be repaired (`repair_skin_palettes.py`), so textures come out as
full DXT5 pyramids.

Not verified in-game; test offline first. Known concerns in this retained
archive include incomplete material coverage and order-dependent FPS selection,
as documented in the [audit](../../docs/audits/2026-10-18-repository-audit.md).
FPS deformation, empty-locator culling, masks and co-op remain unverified.

## Maintaining the packages

- `build_character.py` and `build_model.py` now emit 0-based local `0 .. len(pal_ids) - 1`
  indices in `SkinBones.bone_mappings`, and pass their output through
  `normalize_model_container` so new builds get contiguous `1 .. count` section
  IDs in the canonical vanilla order.
- `build_package2.py` is the three-character staging builder and writes `main.xml`
  and `README.txt` through `package_metadata.py`. Its textures are built by
  `dds.py` with full mipmap pyramids and strictly ordered DXT5 endpoints.
- `build_outfit_beardlib.py` builds the separate native BeardLib variant from
  `dist/lawson_clover.zip`; see [above](#standalone-beardlib-outfit).
- `build_outfit.py` builds `dist/lawson_outfit.zip`, the legacy LAS-branded outfit
  with a native `PlayerStyle` manifest, from a repaired source pack (see above). It reuses
  `repair_skin_palettes.normalize_model_container` / `validate_model_skinning`
  for every model it emits and `dds.encode_dxt5` for the icon.
- `repair_skin_palettes.py` inspects (`--check`) or repairs in place the
  `.model` and `.texture` files inside `dist/lawson_*.zip` archives (SkinBones
  palettes, canonical DODB layout with contiguous IDs, over-limit Topology
  trimming, DXT5 mipmap pyramids and endpoint order) and refreshes
  `main.xml` / `README.txt`. Encoding needs `numpy`; `--check` is stdlib-only:

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
