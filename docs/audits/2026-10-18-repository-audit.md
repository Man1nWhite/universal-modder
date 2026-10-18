# Repository audit — PAYDAY 2 Lawson / 2B reference

**Date:** 2026-10-18

**Audited commit:** `52cc0bef4ae17acd2bfee0f289bce475bd45708c`

**Reference:** the repository's `2b.rar`

**Changes made by this audit:** this report only; no implementation changes, archive repairs, game installation changes, commits, pushes or PRs.

## Verdict

**There is a useful toolkit and a substantial Lawson asset-conversion experiment here, but not yet a verified, reliable equivalent of the supplied 2B mod.** Keep the reusable work; do not start another round of speculative binary repairs before fixing the integration contract and improving the tests.

The reference establishes the intended product much more clearly than the top-level README: **a selectable full-body Legendary Armour Skins (LAS) item with its own third-person model and first-person arms**, rather than permanently replacing Clover, Bonnie or Sydney.

- `dist/lawson_clover.zip`, `lawson_bonnie.zip` and `lawson_sydney.zip` are character overrides. They solve a different problem.
- `dist/lawson_outfit.zip` is the closest existing deliverable, but registers a **BeardLib `PlayerStyle`**, not the reference's **`LegendaryArmours` armor skin**. A player style can be a legitimate alternative; it is not the same registration/menu contract.
- The outfit also has an incomplete material configuration. Its binary validators have both false negatives and false positives, and its source-to-package build is not reproducible from a clean checkout as documented.
- The repository explicitly acknowledges that no in-game verification was performed. Passing its Python tests does not establish that the model loads, deforms, hides the underlying heister, or behaves correctly in a heist.

**Recommendation:** make one standalone Lawson LAS pack matching the reference's registration mechanism, or explicitly choose and document a modern player-style alternative. Do not require installation of the three character-replacement packs to obtain a wearable outfit.

## Scope and verification

This was a targeted repository audit: deep inspection of `tools/pd2-port/`, all four shipped Lawson ZIPs, the supplied RAR, their tests, and the toolkit's backup/publish safety boundaries; plus the complete existing automated suite, CLI help smoke tests, and knowledge-base validation. This is not an exhaustive security assessment of every example mod or a live test of every supported game.

The RAR was listed and read into an isolated scratch directory, checking entry paths before writing. Its Lua hook was inspected as text, not run. Original assets were not copied into new tracked files.

| Check | Result |
|---|---|
| Existing suite, initially without multimedia tools | **179 passed, 5 skipped** |
| Existing suite with FFmpeg 7.0.2 and ffprobe available | **183 passed, 1 skipped** in about 44 seconds |
| Remaining skip | Git Bash / MSYS-specific launcher test |
| All ten CLI command-group help pages | Passed |
| `um kb check --index` | **245 notes passed**, with a warning that `diesel` is not a scanner engine key |
| `um publish check .`, including this report | Exit 0: **757 files, 0 failures, 8 warnings** |
| Character-pack repair checker, check-only | All three character ZIPs reported `OK` |
| Shipped outfit versus freshly built outfit payloads | Passed existing parity test |
| Canonicalization of the three tracked non-menu vanilla reference models | Byte-identical no-op |
| `build_character.py clover` from this checkout | Failed on missing external workspace input |
| PAYDAY 2 / native Windows execution | **Not performed; unavailable in this environment** |

Environment: Python 3.11.2, NumPy 2.4.6, Pillow 13.0.0, PyYAML 6.0.3 and pytest 9.1.1. One existing Pillow deprecation warning remains. Test dependencies and extraction tools were installed only in ignored/scratch locations.

## What `2b.rar` actually contains

The archive has **17 files and 12 directory entries**, totaling **36,415,621 uncompressed bytes**. It is a mod pack, not source for a general-purpose modding application.

```text
2B - LAS/
  main.xml
  hooks/matthelzor_based_awedsy_2b.lua
  localization/english.txt
  assets/
    guis/dlcs/2b/armor_skins/twobee.texture
    units/2b/skins/2b/
      2b.model / .unit / .object / .material_config
      fps_2b.model / .unit / .object / .material_config
      base_df.texture
      base_nm.texture
      2b.cooked_physics       # empty placeholder
      fps_2b.cooked_physics   # empty placeholder
      ss.model
```

Its manifest registers a hook on `lib/tweak_data/armorskinstweakdata`. The hook populates `LegendaryArmours.twobee`, sets `unit` and `fps_unit`, and requests mask/armor hiding and full-body replacement. Localization uses `bm_menu_twobee_armor_skins`, `bm_askn_twobee` and `bm_askn_twobee_desc`.

The Lawson outfit instead declares `GlobalValue` and `PlayerStyle` XML modules, uses `bm_suit_lawson` localization, and has no LAS hook. Both approaches can share model/texture conversion code, but their registrations are not interchangeable.

Do not blindly copy every reference artifact: `ss.model` is not registered by its manifest, its physics files are empty, and its manifest's `Hooks` casing differs from the archive's `hooks` directory. The archive is a specification example, **not an independently verified runtime oracle**.

## Prioritized findings

**P1:** fix before relying on the relevant feature or calling the target mod ready.

**P2:** important correctness, reproducibility or release-hardening work.

**Release review:** a provenance/policy question, not a legal determination.

| ID | Priority | Finding |
|---|---|---|
| A01 | P1 / target fit | The outfit does not implement the reference's LAS armor-skin registration |
| A02 | P1 | An enabled outfit mesh references an omitted material |
| A03 | P1 / security | Backup restore can write outside its selected destination |
| A04 | P1 | Model validation accepts invalid triangle and material references |
| A05 | P2 | A 16-bit index-value limit is incorrectly applied to the number of indices |
| A06 | P2 | Legacy geometry decoding cannot correctly inspect the supplied 2B models |
| A07 | P2 | The DXT5 decoder incorrectly applies DXT1 transparency rules |
| A08 | P2 | The rig exporter destroys UV seams after welding vertices |
| A09 | P2 | First-person arm selection depends on triangle order and is not face-closed |
| A10 | P2 | The full Lawson build depends on an untracked, hard-coded workspace |
| A11 | P2 / security tooling | Publish lint silently ignores the contents of release archives |
| A12 | Release review | Tracked game/model/reference assets have no documented redistribution provenance |

### A01 — Different integration contract from the supplied reference

**Location:** [`build_outfit.py:566–606`](../../tools/pd2-port/build_outfit.py#L566-L606), [`build_outfit.py:610–639`](../../tools/pd2-port/build_outfit.py#L610-L639); `dist/lawson_outfit.zip!/Lawson_LAS/main.xml`.

The generated manifest registers `PlayerStyle id="lawson"`, while its README describes the same system as the 2B LAS pack and directs the user to the armor-skin menu. It does not register a hook or create a `LegendaryArmours.lawson` entry. The existing test explicitly expects a `PlayerStyle`, so it cannot detect this requirements mismatch.

**Impact:** the package has no implementation of the supplied reference's LAS inventory registration. It may work as a separately selectable player style with the appropriate framework, but that has neither been demonstrated nor accurately distinguished in the installation instructions. This is not evidence that BeardLib's `PlayerStyle` API is invalid.

**Repair:** choose the target explicitly. To match `2b.rar`, generate the LAS hook, matching armor-skin localization/icon references, and the corresponding registration contract. If retaining `PlayerStyle`, describe it as a player-style pack, test its actual menu/equip flow, and do not promise the reference's LAS behavior.

### A02 — Missing material for an enabled shadow mesh

**Location:** [`build_outfit.py:91–102`](../../tools/pd2-port/build_outfit.py#L91-L102), [`build_outfit.py:523–543`](../../tools/pd2-port/build_outfit.py#L523-L543); `Lawson_LAS/assets/units/wardrobe_mod/armor_skins/lawson/lawson.material_config` inside the outfit ZIP.

The third-person `.object` enables `s_body`. Its shipped model has **173 vertices** and a render atom using **`shadow_caster`**. `material_configs()` retains only `lawson_*` blocks, so the accompanying material configuration omits `shadow_caster` entirely.

The current material test checks that every configuration entry has a name somewhere in the model. It does **not** check the necessary reverse direction: that every used mesh material has a configuration entry. It therefore passes this incomplete material graph.

**Impact:** missing-material/loading or shadow-rendering problems are possible. This audit does not establish it as the cause of a particular native crash.

**Repair:** prune unused vanilla drawable chains and preserve/define every material still required by the retained model, including its shadow material. Test material coverage by traversing render atoms, material groups and material hashes, not just by searching for XML names in the model.

### A03 — Backup restore permits destination escape

**Location:** [`um/backup.py:104–125`](../../um/backup.py#L104-L125).

Restore trusts names from `_um_manifest.json` and directly opens `target / rel` for writing. It does not reject absolute paths, `..` components or symlink escapes.

**Reproduced safely:** a temporary ZIP with a manifest entry `../outside.txt` was restored into a new temporary `restore-target` directory. Restore printed success and overwrote the neighboring sentinel file. That file was outside the selected destination and was not protected by a pre-restore snapshot.

**Impact:** choosing a crafted snapshot with `--snapshot ... --yes` can overwrite files outside the displayed restore folder. This requires supplying/restoring such an archive; it is not a demonstrated remote, unauthenticated exploit.

**Repair:** validate the complete manifest and archive before making changes; reject escaping paths and links; enforce destination containment; verify expected sizes/checksums; and stage writes safely. Add traversal, absolute-path, symlink/junction and corrupt-archive tests. A confirmation flag is not a substitute for path containment.

### A04 — Model validator certifies invalid native-resource references

**Location:** [`repair_skin_palettes.py:186–316`](../../tools/pd2-port/repair_skin_palettes.py#L186-L316).

The validator checks section references and blend palettes, but does not verify triangle vertex references against geometry bounds or render-atom material indices against material-group length.

Using the existing synthetic `make_model_bytes()` fixture, both of these returned **`[]`**, even with `strict_layout=True`:

- A three-vertex model with triangle `(0, 1, 65535)`.
- A one-material model with a render atom referring to material index `999`.

**Impact:** an `OK` result can hide out-of-range references in assets consumed by native engine code. No such invalid triangle/material reference was established in the current shipped packs; this is a confirmed validator defect, not a claim that all current assets are corrupt.

**Repair:** preflight every geometry/topology/atom range and material reference, validate palette-set counts and raw weight data, and return structured errors rather than indexing beyond decoded arrays. Add deliberately corrupt fixtures that must fail. Keep validator tests independent of the builder's own assumptions.

### A05 — Index count is confused with index value

**Location:** [`repair_skin_palettes.py:71–78`](../../tools/pd2-port/repair_skin_palettes.py#L71-L78), [`repair_skin_palettes.py:214–225`](../../tools/pd2-port/repair_skin_palettes.py#L214-L225), [`repair_skin_palettes.py:411–439`](../../tools/pd2-port/repair_skin_palettes.py#L411-L439).

`MAX_UINT16_INDICES = 65535` is used to reject topology buffers containing more than 65,535 indices, and normalization can delete entire material layers to get under that threshold. But the topology's **count is a 32-bit field**; its individual vertex references are 16-bit values. Many triangles can reference the same small set of vertices.

Evidence:

- A synthetic model containing 22,000 triangles over only three vertices was rejected solely because its index count was 66,000.
- The supplied `2b.model` contains a `g_body` topology with **105,780 indices**, **27,741 vertices**, and a maximum vertex index of **27,740**.
- The upstream model tool independently reads the count with `ReadUInt32()` and each vertex reference with `ReadUInt16()`.

The reference is a legacy container, so its sparse section IDs should not be used to infer DODB ordering requirements. Likewise, these observations do not prove the absence of every engine-specific resource cap. They do establish that a generic 16-bit *count* rule is not justified by the field format.

**Repair:** validate index **values** and atom ranges. Treat redundant-layer removal as an explicit mesh optimization, not automatic container repair. Require separate engine evidence for any additional count cap. Reword the documentation's claimed crash causes as hypotheses unless a controlled in-game test establishes them.

### A06 — Legacy model channels are decoded using modern channel IDs

**Location:** [`dmodel.py:109–126`](../../tools/pd2-port/dmodel.py#L109-L126), [`dmodel.py:206–268`](../../tools/pd2-port/dmodel.py#L206-L268).

The container reader detects legacy files but does not propagate that distinction into the geometry channel decoder. The upstream reader remaps legacy channel IDs above `TEXCOORD7` by **+2**. This implementation does not.

For the 2B model, the legacy blend-index and blend-weight channels are consequently misinterpreted. The local parser reports zero decoded weights, and `validate_model_skinning()` raises **`IndexError: list index out of range`** instead of returning a validation result. The same exception was observed for all three reference `.model` files.

**Impact:** the toolkit cannot reliably inspect the very reference intended to guide this port; direct conversion or comparison through this reader would be unsafe.

**Repair:** carry the container/section format into the geometry reader, implement the legacy remapping and component layouts, and test small synthetic legacy fixtures plus an optional local-reference round trip. Unsupported formats must produce an explicit error rather than partially decoded data.

### A07 — DXT5 decoding uses the wrong color-palette rule

**Location:** [`dds.py:55–97`](../../tools/pd2-port/dds.py#L55-L97), [`dds.py:256–327`](../../tools/pd2-port/dds.py#L256-L327); the same explanation is repeated in the PD2 documentation.

BC3/DXT5 has a separate alpha block and uses a four-color RGB palette irrespective of the RGB endpoint ordering. The decoder instead switches to the BC1/DXT1 three-color/transparent case when `c0 <= c1`. The validator also labels valid `c0 < c1` blocks corrupt.

**Independent decoder comparison:** for one valid opaque block with RGB endpoints `0` and `65535` and color index `3`:

```text
Pillow DDS decoder: (170, 170, 170, 255)
local _decode_block: (0, 0, 0, 0)
```

**Impact:** valid imported DXT5 data can decode as transparent black and be falsely rejected. The endpoint swap/remap can preserve base-level colors, but is not proof that the original image contained transparent holes; unnecessary repair can also regenerate lower mip levels. The currently shipped sorted-endpoint textures are not, by themselves, evidence of this visual failure.

**Repair:** always use the DXT5 four-color rule; remove endpoint ordering as a validity requirement; compare decode results against an independent decoder; and separate engine-specific mipmap preferences from DDS format validity.

### A08 — Welded vertices lose their distinct UV coordinates

**Location:** [`rig_lawson.py:108–116`](../../tools/pd2-port/rig_lawson.py#L108-L116), [`rig_lawson.py:225–240`](../../tools/pd2-port/rig_lawson.py#L225-L240).

The rig stage merges coincident vertices, then exports a single UV coordinate per vertex by taking only its first mesh loop. UVs actually belong to face corners; a welded vertex can have multiple different loop UVs at a texture seam.

Inspection of `Lawson_strip.obj`, resolving its relative/negative indices correctly, found **1,939 exact-coordinate groups with differing UV coordinates**. These are concrete seam cases, before considering additional vertices merged by the 0.0008 distance threshold.

**Impact:** rebuilding through this exporter can smear/stretch textures across UV seams. This is a source-pipeline defect; the audit did not render the current binary packs in-game to quantify their appearance.

**Repair:** weld only for rigging if necessary, then export vertices split by position/UV/normal/material attributes, copying weights to the split vertices. Add a two-triangle seam fixture whose shared position has different UVs on each triangle.

### A09 — Arm extraction is triangle-order dependent

**Location:** [`build_outfit.py:218–228`](../../tools/pd2-port/build_outfit.py#L218-L228), [`build_outfit.py:381–409`](../../tools/pd2-port/build_outfit.py#L381-L409).

The routine mutates the selected vertex set while making a single pass over triangles. Newly added vertices can pull later triangles into the selection, while earlier adjacent triangles are never reconsidered. This is neither a stable cut nor the promised face closure.

Measured on the shipped Clover source's `g_body`:

```text
Original arm-influenced vertices:      1,825
Selection in original triangle order: 3,129
Selection with triangle order reversed: 2,740
Symmetric difference:                   755 vertices
Faces still crossing the selected/unselected boundary: 407
```

**Impact:** innocuous face reordering changes the resulting FPS mesh. Vertex-count and bone-name checks do not establish an arms-only silhouette or watertight shoulder boundaries.

**Repair:** use explicit arm groups or a deliberately defined anatomical cut, with appropriate boundary handling/capping. Do not simply flood-fill a connected full-body garment. Test invariance under triangle reordering, spatial bounds, and expected boundary loops, then verify reload/weapon poses in-game.

### A10 — The asset build is not reproducible from the checkout

**Location:** [`build_character.py:21–25`](../../tools/pd2-port/build_character.py#L21-L25), [`build_character.py:126–132`](../../tools/pd2-port/build_character.py#L126-L132), [`build_package2.py:17–19`](../../tools/pd2-port/build_package2.py#L17-L19), [`rig_lawson.py:7–23`](../../tools/pd2-port/rig_lawson.py#L7-L23).

The scripts expect a `pd2-work/clover-lawson` layout at a hard-coded, developer-specific absolute location, an external hashlist checkout, generated mesh JSONs and a referenced `setup_work.sh` that is not tracked. There is no documented command that stages those dependencies from the actual inputs. The source rig additionally needs a compatible Blender version, which is not pinned.

Running `build_character.py clover` failed immediately because the expected model under that workspace did not exist, despite the repository containing a Clover reference model elsewhere.

The outfit parity test is valuable, but starts from the already-built `dist/lawson_clover.zip`. It proves **archive-to-outfit** reproducibility, not **OBJ/rig-to-character-to-outfit** reproducibility.

**Repair:** introduce explicit input/work/output paths, pinned external-tool/hashlist versions, preflight diagnostics and a documented build sequence. Keep licensed user/game inputs outside version control; generated intermediate JSON need not be committed. Build in a temporary staging directory and replace outputs only after validation.

### A11 — Archive payloads bypass publish lint

**Location:** [`um/publish.py:38–43`](../../um/publish.py#L38-L43), [`um/publish.py:54–99`](../../um/publish.py#L54-L99); [CI:25–26](../../.github/workflows/test.yml#L25-L26).

Publish lint scans selected text files on disk, not members of ZIP/RAR archives. Those common release containers are not even in its archive-warning extension set.

**Reproduced safely:** a temporary release folder containing a README and a ZIP with an internal `.env` plus a synthetic recognizable key assignment produced:

```text
PASS: 2 files, 0 failures, 0 warnings
```

**Impact:** CI can be green while the actual distributable contains secrets or unreviewed asset payloads. This was a synthetic probe, not discovery of a real leaked credential.

**Repair:** inspect supported archive members with nesting/size/file-count limits, or explicitly report uninspected containers and require release checks on an unpacked staging tree. Do not silently treat an unexamined release archive as a clean security result.

### A12 — Asset provenance must be resolved before publication

**Location:** tracked `Bonie/`, `clover/`, `Sydney/`, `Lawson model/`, `2b.rar` and `dist/`; [contribution policy:35–61](../../CONTRIBUTING.md#L35-L61).

The checkout includes six model files described by its own documentation as vanilla references, sixteen DDS files, a Lawson OBJ and textures, the third-party reference pack, and four built mod archives. There is no corresponding third-party asset provenance/permission manifest. This conflicts with the repository's stated policy against committing extracted game content and leaves the scope of the blanket MIT license unclear.

**Impact:** a technically correct mod is not automatically authorized for redistribution. User-supplied private working inputs are not the same as publication rights. This audit does not determine ownership or allege infringement.

**Repair:** review origin, authorship, permissions and required credits for each asset set; explicitly scope the code license; keep non-redistributable inputs in private local storage; and publish conversion tooling or patches where appropriate. Do not remove the user's reference files as part of an audit without agreement.

## Checks that should not be mistaken for confirmed runtime bugs

1. **Comma-less localization:** the outfit's `english.txt` is rejected by strict Python JSON parsing. However, BeardLib's localization loader uses `json10`, and the pinned SuperBLT legacy decoder **successfully decoded the shipped file in a Lua 5.1 runtime**. The Jack Cooper example uses the same comma-less convention. Generate standards-compliant JSON for interoperability, but do not claim these missing commas explain a game failure.
2. **Culling, physics, animation and network behavior:** empty `co_box`, missing/empty cooked-physics sidecars, rig alignment, mask handling, animation blending and co-op remain runtime questions. Neither matching a file list nor seeing a mod-manager entry proves them.
3. **Previous crash diagnoses:** the palette/index/layout repairs have useful regression coverage, but the documentation sometimes presents inferred native-engine crash mechanisms as established causes. No controlled in-game retest was performed here. Preserve the distinction between a measured binary inconsistency and a proven crash cause.

## Recommended repair sequence

### 1. Establish the exact product contract

Use the 2B armor-skin integration as the default target unless a different player-style UX is explicitly chosen. One Lawson pack should be selectable independently of heister choice, include its own TPP/FPS assets, and hide the underlying body/head/mask as intended. Keep it separate from the three vanilla character overrides.

For a reference-style LAS implementation, the minimum contract is:

- A manifest with `Localization`, `Hooks` and `AddFiles`.
- A real, correctly cased hook file on the armor-skin tweak-data initialization route.
- One uniquely named `LegendaryArmours` entry with the correct TPP/FPS unit paths and replacement flags.
- Matching armor-skin localization keys and icon path.
- Consistent unit/object/material/model/texture references under pack-owned paths.

### 2. Fix correctness before rebuilding assets

Fix A02–A09 with small synthetic regression fixtures. In particular, reverse the material-coverage test direction, add invalid triangle/material tests, implement legacy channel decoding, compare BC3 decoding with Pillow, and preserve seam attributes during export.

Fix the backup containment vulnerability separately; do not wait for the game-model work to be finished.

### 3. Make the pipeline reproducible

Address A10 and A11, record source/tool hashes, build into staging, lint the unpacked **actual release payload**, and compare the result to a known reference contract. The current archive-to-outfit parity test should remain, but needs a source-to-package complement.

Resolve A12 before any public distribution. Do not add more extracted game data to make tests easier; use tiny authored fixtures and optional local-reference tests instead.

### 4. Obtain actual offline game evidence

With saves backed up and conflicting replacements removed, record exact game/SuperBLT/BeardLib/LAS versions and verify:

- Clean game startup and no new loader errors.
- The intended armor-skin or player-style menu contains Lawson, with the correct name/icon.
- Equip and unequip on at least two different heisters; the base heister's geometry does not leak through.
- Third-person and first-person appearance, shadows/culling, mask transitions, weapon handling and reloads.
- Offline heist launch, animation/deformation, restart persistence and clean uninstall.

Collect a menu screenshot, first-person screenshot, third-person screenshot, a short offline clip and relevant logs. Until then, label the output **experimental / not verified in-game**. Treat multiplayer as a separate test phase, not an implication of single-player success.

## Reproduction notes

Run from the repository root in an environment containing its Python dependencies and pytest:

```sh
python -m pytest -q -ra tests
python -m um kb check --index
python -m um publish check .
python tools/pd2-port/repair_skin_palettes.py --check dist/lawson_bonnie.zip dist/lawson_clover.zip dist/lawson_sydney.zip
```

Minimal reproduction of the validator false negatives (A04), using the existing authored fixture rather than any game binary:

```python
import runpy
fixture = runpy.run_path("tests/test_pd2_packages.py")
make = fixture["make_model_bytes"]
validate = fixture["skin_repair"].validate_model_skinning

bad_triangle = make(
    material_names=["lawson_outfit"],
    atoms=[(0, 0, 3, 1, 0)], faces=[(0, 1, 65535)], vert_count=3,
)
bad_material = make(
    material_names=["lawson_outfit"],
    atoms=[(999, 0, 3, 1, 0)], faces=[(0, 1, 2)], vert_count=3,
)
print(validate(bad_triangle, strict_layout=True))  # currently []
print(validate(bad_material, strict_layout=True))  # currently []
```

The destination-escape and archive-secret probes used only disposable temporary directories, fabricated manifests and synthetic marker data. They did not operate on user saves, credentials or game installations.

## Source references and artifact identity

External source was read for comparison, not added to the repository:

- [BeardLib `PlayerStyleModule.lua`, pinned commit `95eb1c0`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Modules/PD2/PlayerStyleModule.lua): player-style registration, distinct from the supplied LAS hook.
- [BeardLib `FileIO.lua`, same pin](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Classes/Utils/FileIO.lua): localization is decoded through `json10`.
- [SuperBLT legacy JSON decoder, pinned commit `5602d35`](https://github.com/diesel-modding/PAYDAY2-SuperBLT-Lua/blob/5602d35c9a0020c2cba87cd79f25563f8d5435d7/req/utils/json-1.0.lua): optional commas in object parsing; the shipped localization was decoded with this implementation.
- [Model-tool `Geometry.cs`, pinned commit `6ca72e1`](https://github.com/diesel-modding/payday2-model-tool/blob/6ca72e1940f5813ce57eecb400e685a62ecfd95a/PD2ModelParser/Sections/Geometry.cs): legacy geometry channel-ID remapping.
- [Model-tool `Topology.cs`, same pin](https://github.com/diesel-modding/payday2-model-tool/blob/6ca72e1940f5813ce57eecb400e685a62ecfd95a/PD2ModelParser/Sections/Topology.cs): 32-bit index count, 16-bit vertex references.
- [LASCreator hook template, pinned commit `b0baf8e`](https://github.com/LebiFur/LASCreator/blob/b0baf8ec2e228eaa69c07a7694f86a112191f987/LASCreator/Sources/hook.lua): independent example of the LAS registration pattern found in `2b.rar`.

SHA-256 of the audited artifacts:

```text
2b.rar
925a29ef79f7033cb681dd47a1f9c3856ef91d88a14e6728eb68b36396501fd9

dist/lawson_bonnie.zip
af3e723bebe581642f663c74308827b973e8877c96462a169c423c6ded70c7b8

dist/lawson_clover.zip
95f3d4ab3718c71a84c8ed4695e130712e3b5c132b6b68e377530f40460b271f

dist/lawson_outfit.zip
5f58d8f86d3bdc49ada4efcb6f7e32d6121207c1bd8b94b2e55c3114e090cefe

dist/lawson_sydney.zip
c200d9ec321ecba890e8d51fe52fb6aa6819539e17b350013984121027e6c4ab
```
