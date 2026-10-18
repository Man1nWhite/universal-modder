# PAYDAY 2 Lawson character packs

## Choose a package

| Archive | Integration | Where it appears |
| --- | --- | --- |
| `lawson_outfit_BeardLib.zip` | **Standalone BeardLib-native `PlayerStyle`; no LAS** | Native Outfit / Player Styles selector: **Miranda Lawson (BeardLib)** |
| `lawson_outfit.zip` | **LAS / Wardrobe Mod add-on**, repaired candidate `1.1.0-rc1` | **[LAS] Miranda Lawson** in Outfits on LAS 4.x (`las_lawson`) |
| `lawson_bonnie.zip`, `lawson_clover.zip`, `lawson_sydney.zip` | Character asset replacements | Replaces the corresponding heister; no new outfit entry |

The new BeardLib variant is additive: its item ID, asset paths, icon bundle and
folder are independent of the LAS pack. The three character archives and
`2b.rar` remain unchanged; `lawson_outfit.zip` has been rebuilt after the reported
crash. Neither outfit candidate is game-verified;
see the [current-checkout audit](../../docs/audits/2026-10-18-current-checkout-audit.md)
for the 2B comparison, improvements in the new variant, and remaining limitations.

**Runtime feedback, 2026-10-18:** the user reports that `lawson_clover` loads but
its model is visually broken, and the original `Lawson_LAS` crashes. Keep that
old version disabled. The latest logs fail during menu outfit-unit spawning/linking;
they do not identify the exact offending asset. The [rebuilt LAS candidate](#las-outfit-distlawson_outfitzip)
addresses reproducible resource/registration defects, not a proven native crash cause.
The BeardLib variant remains
untested in-game and **inherits the same Clover-rigged mesh**: rebuilding or
changing registration does not repair that mesh. See the latest entry in
[the repair journal](MODLOG.md) for evidence and the next diagnostic step.

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
API commits and every other payload's SHA-256. The requested ZIP is present in
`dist/`; a narrow `.gitignore` exception keeps
`dist/lawson_outfit_BeardLib.zip` visible while other generated outputs remain
ignored. It is also available as a private download. No release, commit, push or
publication is performed; asset redistribution rights remain unresolved.

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

## LAS outfit (`dist/lawson_outfit.zip`)

`build_outfit.py` now builds the **LAS / Wardrobe Mod** edition, root
`Lawson_LAS/`, version **1.1.0-rc1**. Requires **SuperBLT + BeardLib + Legendary
Armour Skins / Wardrobe Mod** (ModWorkShop #24006). The separate BeardLib ZIP
above does not require LAS. Neither loader/framework is bundled.

### What was repaired

- Replaced the old plain `PlayerStyle id="lawson"` manifest with a lowercase,
  case-consistent `hooks/register_lawson.lua` registration on
  `lib/tweak_data/armorskinstweakdata`, creating `LegendaryArmours.lawson`.
  This follows the supplied 2B integration rather than only its folder branding.
- Inspected LAS **4.1.9** in `Vladik268/P2` at
  [`b7c38c1d358fe054df51201788126c25a0da1938`](https://github.com/Vladik268/P2/tree/b7c38c1d358fe054df51201788126c25a0da1938/mod/Legendary%20Armour%20Skins).
  Its loader maps this registry entry to **`las_lawson`** in the native Outfit /
  Player Styles selector and uses LAS-specific mask handling. This is a pinned
  public copy, not a claim about the user's installed/latest LAS version.
- Pruned the source's unused drawable chains: TPP now contains **7** drawable
  models instead of **52**, and FPS contains only **2**. Disabling an object in
  XML is not treated as a substitute for removing unused binary resources.
- Defined every retained model material, including the enabled `s_body` shadow
  mesh's **`shadow_caster`**. Source materials missing from the configuration now
  fail the build. Used-material coverage is tested in both directions.
- Replaced the empty `co_box` culling locator with real **`g_body`** geometry and
  bounds enclosing every retained drawable. FPS selection is an immutable
  one-ring cut (**1,998** body vertices plus **4,538** original hand vertices),
  not the old face-order-dependent flood fill; it is not claimed watertight.
- Kept `unit_mat auto_cp="true"`: the inspected BeardLib shortcut supplies its
  own built-in default cooked-physics resource. No empty/custom physics blob is
  fabricated, bundled or eagerly loaded.
- Added standard JSON localization, LAS and native-fallback icon paths,
  `BUILD_INFO.json` source/payload hashes, credits, overwrite protection and a
  deterministic, atomic build.

### Upgrade / test / rollback

1. Back up the save/profile and `assets/mod_overrides/`. Select a vanilla outfit
   before removing/upgrading an equipped custom one if possible.
2. With the game closed, **move the old `Lawson_LAS` completely outside
   `assets/mod_overrides/`**, then extract the new ZIP there. Do not overlay it or
   merely rename the old folder inside that directory; BeardLib may load both.
3. Confirm `PAYDAY 2/assets/mod_overrides/Lawson_LAS/main.xml` and
   `Lawson_LAS/hooks/register_lawson.lua`. Restart the game completely.
4. On LAS 4.x select **[LAS] Miranda Lawson** in **Outfits / Player Styles**
   (`las_lawson`), with **Default gloves**. Older LAS versions may expose it in
   their armor-skin menu. Do not select the obsolete plain `lawson` style. Start
   with other character replacements and the BeardLib Lawson edition disabled.
5. Check **only the menu preview first**. If it crashes, stop and capture fresh
   crash.txt/crashlog.txt, loader logs and exact game/BeardLib/LAS versions.
   Only if the menu works, continue with a backed-up **offline** heist. Do not
   keep repeating the same crashing preview.
6. To roll back, equip vanilla if possible, close the game and move only this
   pack outside `mod_overrides`. Keep the known-crashing old version disabled;
   do not delete shared loaders or saves.

**Not a verified game fix or a re-rig.** The original crash logs identify native
unit spawning, not an exact bad asset. The candidate corrects reproducible
resource defects and the LAS contract, but retains the user-reported broken
Clover mesh, its weights and UVs. No source re-rig, UV/weapon alignment repair,
rendering, animation, mask, VR or co-op success is claimed.

### Rebuild / checks

```sh
python tools/pd2-port/build_outfit.py
python -m pytest -q tests/test_outfit_pack.py tests/test_outfit_beardlib_pack.py tests/test_pd2_packages.py
```

Output: **`dist/lawson_outfit.zip`**, root `Lawson_LAS/`, 35 files. `lupa` is an
optional test dependency for executing the registration in Lua 5.1. The manual
contract smoke additionally executed the actual pinned BeardLib Hooks/Package
and LAS loader code with stubbed engine/file boundaries. It checks registry and
resource interpretation, **not** native unit loading/rendering. See
[the repair journal](MODLOG.md) for the current results and artifact hashes.

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
- `build_outfit.py` builds the actual LAS add-on in `dist/lawson_outfit.zip`;
  `outfit_model.py` shares pruning, stable FPS selection and reference checks
  with the native BeardLib builder. Both retain the original rig. The shared
  implementation still uses the existing model normalizer; broader parser /
  large-topology limitations in the audit are not claimed resolved here.
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
