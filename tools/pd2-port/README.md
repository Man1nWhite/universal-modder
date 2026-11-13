# PAYDAY 2 — rigged character → Legendary Armour Skins (LAS) outfit

This directory is a pipeline that turns a **rigged, skinned character model**
into an **equipable, additive full-body outfit** for PAYDAY 2 — a
[Legendary Armour Skins](https://github.com/Vladik268/P2) registration with
its own third-person unit and first-person arms — on the contract
demonstrated by the user-supplied `2b.rar` reference pack. It is **not** a
character-model replacement.

Most of it is independent of the character: a COLLADA importer, a skin
transfer onto PAYDAY 2's biped rig, a Diesel `.model` writer, a DXT5 texture
encoder, a pack assembler and a set of offline checks. What belongs to one
character is its **configuration** — the source archive, the joint map, the
texture slots, the pack's names — and a handful of **fix-ups** for defects of
that source. Both are written into the code, as constants and helper
functions, not into a config file, so porting another character means editing
them. [Porting another character](#porting-another-character) lists every
place.

**The shipped port.** The configuration in the tree ports **Miranda Lawson**
from *Mass Effect 2* and builds `dist/lawson_las.zip`. It is the worked
example for everything below. Its pack is tracked in git, compared byte for
byte in CI and published by the release workflow. Names such as `me2_dae.py`,
`lawson_las.zip` and `Lawson_LAS/` still carry the character because tests,
CI and other tools in the repository refer to them. Wherever this page says
"the shipped port", it means that build.

Earlier attempts at the same character — the character swaps (`lawson_clover`
/ `lawson_bonnie` / `lawson_sydney`) and the old-model outfit packs — are
retired and deleted; see the
[restart audit](../../docs/audits/2026-10-18-old-model-retired-las-restart.md)
and the journal in [`MODLOG.md`](MODLOG.md).

## Status and handoff

[`STATUS.md`](STATUS.md) is the status and handoff page of the shipped port:
what is shipped, the measured check results, the open problems and the
workflow traps. Read it before touching the pipeline. Its pack facts are
pinned by tests; the rest is a dated snapshot, and the note at its top says
what has moved since. [`MODLOG.md`](MODLOG.md) is the journal behind it. Both
are written about that one port, but what they record about the PAYDAY 2
side — the rig contract, the guide's rules, the build environment — holds
for any character.

One command tells you whether a checkout is sound:

```sh
python tools/pd2-port/check_all.py          # pack checksum, audit, winding, nm, mutations
python tools/pd2-port/check_all.py --full   # + the auditor self-test, pytest and the skip budget
```

`--full` judges the whole repository, not only this directory. Its
skip-budget stage expects the 2B reference templates to be extracted to
`build/pd2-las/2b/` (`bash tools/pd2-las/recover_env.sh` does that) and fails
without them. The same stage budgets expected failures: an `xfail` that
`check_skip_budget.py` does not name fails it.

## Inputs and outputs

| | What the pipeline takes or makes | The shipped port |
|---|---|---|
| Source model | a zip archive holding a rigged, skinned COLLADA `.dae` and its PNG textures (the repo keeps sources under `models/`) | `models/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip`; of its two `.dae` files the build reads `Miranda Lawson (Romance) - Adjusted Version.dae` |
| Rig contract | `reference/las_rig.json` — the PD2 biped skeleton an LAS unit animates on, extracted from the model in `references/2b.rar` by `extract_las_rig.py` (skeleton data only; no 2B art) | the same file — PAYDAY 2's rig does not change with the outfit |
| Output | a BeardLib pack zip, built deterministically | `dist/lawson_las.zip`, root `Lawson_LAS/` (**tracked in git** and published as the release asset) |
| Checksum | — | `dist/lawson_las.zip.sha256` (tracked; CI refuses to publish a build that differs from it) |
| Release | — | [`lawson-las-v2`](https://github.com/Man1nWhite/universal-modder/releases/tag/lawson-las-v2) — notes in [`releases/lawson-las-v2.md`](releases/lawson-las-v2.md) (v1 kept for comparison; it has holes in the skin) |

What a source has to look like for the pipeline as it stands:

- **Geometry and rig:** COLLADA with `<matrix>` node transforms, triangulated
  meshes and `<instance_controller>` skins (the importer's exact subset is in
  the `me2_dae.py` docstring). Z-up, coordinates in centimeters, standing
  upright at life size. The three heaviest weights per vertex are kept.
- **Textures:** PNGs — a diffuse per material and, optionally, a
  tangent-space normal map and a specular map. Diffuse and normal maps must
  be square with a power-of-two side.
- **Size:** at most 65,536 vertices and 64 skinning bones per drawable (the
  shipped port uses two drawables, body and head).

## Build

Python 3.10+, Pillow and numpy (the repo's own dependencies). The commands
take no character argument: they build and check whatever the configuration
in the code describes, which is the shipped port.

```sh
python tools/pd2-port/build_las_pack.py          # -> dist/lawson_las.zip
python tools/pd2-port/build_las_pack.py --check  # validate only
# --source / --out replace the source archive and the output zip; the .dae
# name, the texture slots and the pack's names stay those of the code
# --version stamps the release version into build_manifest.json
# (default 0.1.2; the release notes carry the same value)
# --keep-nm-green keeps the source Y channel instead of the default PD2 flip
# (only for sources already authored with PD2's green convention)
python tools/pd2-port/preview_check.py report    # geometry gates on the rebind
python tools/pd2-port/preview_check.py render DIR  # + raster previews (flat, textured, diff)
python tools/pd2-port/check_guide_compliance.py  # audit the pack against the
                                                # ModWorkshop LAS/MOOG guide
python tools/pd2-port/check_guide_compliance_self_test.py
                                                # prove the auditor fails on
                                                # broken packs (16 mutations)
python tools/pd2-port/check_mesh_geometry.py     # winding / tangent frame of
                                                # the built model (no inverted
                                                # triangles may survive)
python tools/pd2-port/shade_check.py DIR         # shaded render of the rebind
                                                # with the pack's own normals
python tools/pd2-port/check_nm_convention.py     # the source normal maps'
                                                # green-channel convention
python tools/pd2-port/check_test_suite_mutations.py
                                                # prove the pack-level tests
                                                # fail on a broken pack
python tools/pd2-port/check_all.py              # run every check, one verdict
python tools/pd2-port/resolve_rig_names.py       # recover PD2 bone names from
                                                # the rig contract's hashes
python -m pytest -q tests/test_las_pack.py
```

The build is **deterministic**: same source + same tool code -> the same zip
bytes (fixed zip timestamps, sorted entries). The tracked
`dist/lawson_las.zip` is therefore exactly what the release serves. Byte
equality also needs the pinned environment — Python 3.11, `pillow==13.0.0`,
`numpy==2.4.6`; see [`STATUS.md`](STATUS.md) §7.

## Pipeline

Five stages, one module each. `<id>` is the outfit's id — `lawson` for the
shipped port.

1. **Import — `me2_dae.py`.** Reads the rigged COLLADA: meshes (positions,
   normals, UVs, triangles), materials, skin weights and the joint hierarchy
   with bind transforms. The module is named after its first source, a Mass
   Effect 2 export; the parser itself is plain COLLADA.
2. **Retarget — `rig_target.py`.** `BONE_MAP` names the PD2 bone for every
   source joint: twist, IK and facial joints fold into their parent's bone,
   and finger chains map onto PD2's three bones per finger. `target_ops`
   builds one bind operator per PD2 bone from joint positions alone — for a
   humanoid source, one upright rigid transform for the torso, head and legs
   and constructed fits for the shoulders, arms, hands and fingers — and
   `rebind_mesh` moves the skin with a harmonic blend of them,
   `p' = p · (Σ wᵢ·opᵢ⁻¹)⁻¹`. The weights are smoothed over the welded vertex
   graph first, and `repair_winding` re-winds any triangle the move folded
   inside out.
3. **Author the models — `las_model.py`.** Writes DODB `.model` files
   (canonical section order, 0-based SkinBones palette indices, absolute
   topology indices, `shadow_caster` material, no index-count trimming).
4. **Encode the textures — `dds.py`.** DXT5 with full mip pyramids; normal
   maps go into PD2's packed layout (X in alpha, Y in green).
5. **Assemble the pack — `build_las_pack.py`.** Holds the character's
   configuration and fix-ups, and writes the 2B-shaped pack: `main.xml`
   (Localization + Hooks + AddFiles), `hooks/<id>.lua`
   (`LegendaryArmours.<id>` with `hide_mask` / `hide_armor` / `replace_all` /
   `fps_hide_armor` / `fps_replace_body`), localization, the TPP unit `<id>`
   and the FPS unit `fps_<id>` (arms cut by dominant bone), the DXT5
   `.texture` pairs, `CREDITS.txt` and a hash manifest.

Shared format library: `dmodel.py`, the Diesel `.model` reader behind the
checks and the rig extraction. The rig contract itself was produced once, by
`extract_las_rig.py` and `resolve_rig_names.py`, from the 2B reference model.

## What is reusable and what is per character

| Piece | Works for any character | Written for the shipped port |
|---|---|---|
| `me2_dae.py` | the COLLADA parser | one fix-up keyed on a mesh named `Eyelashes` |
| `rig_target.py` | rig loading, weight smoothing, the harmonic-blend rebind, winding repair, the first-person arm cut, the generic per-segment branch of `target_ops` | `BONE_MAP` and the finger/face tokens (the source skeleton's joint names); the humanoid branch of `target_ops` (the source's facing, 1:1 scale, a hand-tuned arm pose) |
| `las_model.py`, `dds.py`, `dmodel.py` | everything | — |
| `reference/las_rig.json`, `extract_las_rig.py`, `resolve_rig_names.py` | everything | — |
| `build_las_pack.py` | model, texture and pack assembly, validation, the deterministic zip | the constants at the top (source, texture slots, layout, identity), the text of the hook, `main.xml`, localization and credits, the mesh and texture fix-ups |
| `check_guide_compliance.py` and its self-test | the guide's rules and the mutations | the pack paths and names they look under; the `N2` credits check and the `G1` warning text |
| `check_mesh_geometry.py`, `check_test_suite_mutations.py`, `check_all.py` | the analysis and the chain | the pack and model paths |
| `preview_check.py`, `shade_check.py`, `check_nm_convention.py` | the gates, the rasterisers, the measurement | the source path constants, a few mesh and joint names, the normal-map verdict text |

The docstring of every module with per-character parts names them, and
comments mark those values where they are defined.

## Porting another character

There is one configuration in the tree at a time. The steps below turn it
into another character's; nothing in this list has been exercised on a second
character yet, so treat it as a map of what to touch, not as a tested recipe.

1. **Bring the source.** Put the archive in `models/` and set `SOURCE_ZIP`
   and `DAE_NAME` in `build_las_pack.py`. `preview_check.py`,
   `check_nm_convention.py` and `shade_check.py` keep their own copy of the
   archive path (`shade_check.py` also of the `.dae` name).
2. **Map the skeleton.** Rewrite `BONE_MAP` and the finger/face tokens in
   `rig_target.py` for the source's joint names; the targets are the named
   bones of `reference/las_rig.json`. `map_joint` raises on the first
   weighted joint it cannot place, so the build tells you what is missing.
   Unweighted vertices are bound through the source's root joint, which
   `rebind_mesh` looks up as `root` or `God`.
3. **Check the retarget.** `target_ops` has two branches. A skeleton with
   `Pelvis`, `LeftShoulder` and `RightShoulder` joints takes the humanoid
   branch. It reads the collar, elbow, wrist and finger joints by the shipped
   source's names (a missing one is a `KeyError`) and assumes that source's
   facing (−Y, `Left*` at +X), its scale (already PD2's, 1:1) and its arm
   proportions. Any other skeleton takes the generic branch, a rigid fit per
   bone segment that only the unit-test fixtures have used so far. Either
   way, look before trusting it: `preview_check.py report` and
   `preview_check.py render DIR`. In the report, the side check prints
   `CROSSED` for a source that needs the half turn about Z — that is the
   expected reading for the shipped port, not a failure.
4. **Describe the meshes and materials.** `TEXTURE_SLOTS`, `SPECULAR_SLOTS`,
   `TPP_LAYOUT`, `FPS_LAYOUT`, `TEMPLATE` and `MAT_BASE` in
   `build_las_pack.py`, plus the material and drawable lists in `assemble()`.
   Use only render templates the guide or the 2B pack attest (see below).
5. **Remove or replace the fix-ups.** They repair defects of the shipped
   source and find their targets by its mesh names and UV layout: the hair
   strips, skin normals, collar snap and eye UVs in `build_models()`; the
   `face` and `eyes` branches of `_prepare_diffuse_rgba()` and
   `encode_textures()`, and the menu icon taken from the `Face` diffuse; the
   `Eyelashes` block in `me2_dae.load_dae`.
6. **Settle the normal maps.** `check_nm_convention.py` measures what the
   files can say; the green channel is decided by the engine that authored
   them. A DirectX-style (Y−) source takes the default build, which inverts
   green; an OpenGL-style (Y+) source builds with `--keep-nm-green`. Check
   the channel order as well: `encode_textures()` swaps red and green on
   every source normal map, because the shipped source is read as Y in red
   and X in green. A source with X in red must not take that swap.
7. **Name the pack.** `UNIT_DIR`, `GUI_DIR`, `ROOT_DIR` and `DEFAULT_OUT`,
   and the `lawson` literals in `hook_lua()`, `main_xml()`, `localization()`,
   `credits_txt()`, `material_config()`, `encode_textures()` (the icon's file
   name), `assemble()` and `validate()`. Then the same names where the checks
   look for them: `check_guide_compliance.py` and its self-test,
   `check_mesh_geometry.py`, `check_test_suite_mutations.py` and the `--pack`
   default of `check_all.py`.
8. **Verify offline, then in game.** `build_las_pack.py --check`, the guide
   audit, `check_mesh_geometry.py`, `shade_check.py` — then the install steps
   below, menu preview first.

Changing the constants in place replaces the shipped port: its tests
(`tests/test_las_pack.py`), its tracked pack and its release workflow
([`lawson-las.yml`](../../.github/workflows/lawson-las.yml): paths, tag
pattern, release title) are all wired to its names. Keeping two characters in
the tree at once needs the configuration lifted out of the code first, and a
second pack that is tracked and released needs tests and a workflow of its
own.

## Guide compliance

Packs built here follow the [ModWorkshop LAS/MOOG outfit guide](https://wiki.modworkshop.net/books/payday-2-mod-creation/page/legendary-armor-skinslasmoogoutfit-module-guide)
(Columbus). `check_guide_compliance.py` re-reads the built zip and checks it
against the guide's rules, each check citing the rule it enforces:

| Area | Checks |
|---|---|
| Skeleton | PD2's 54-bone set (incl. 3 bones per finger), locators kept, twist bones merged, ≤ 3 influences per vertex, finger bones actually carry weight, tangents present and non-degenerate |
| Materials | `version="3"` + `group=`, one entry per model material (hash-checked), attested render templates only, contour materials with `unique="true"` + `contour_color`/`contour_opacity`, extensionless texture paths that resolve, skinning keyword matching the geometry |
| First person | separate unit, arms only (hands and fingers included), `DEPTH_SCALING` template |
| Textures | DXT5 with a full mip pyramid, PD2 normal layout (X in alpha, R white, B black) |
| Packaging | `main.xml` with Localization/Hooks/AddFiles, every AddFiles entry resolving, the full LAS flag set, menu localization |

The audit runs in the test suite (`test_built_pack_passes_the_guide_compliance_check`),
so a pack that drifts from the guide fails the build. Current state of the
shipped port: **38 pass, 1 warning, 0 failures** — the warning is the normal
maps' green-channel convention, which the files cannot settle (see
`check_nm_convention.py`) and only the running game can confirm.

The auditor is itself tested: `check_guide_compliance_self_test.py` mutates the
built pack the way the guide forbids (invented render template, contour
without `unique="true"`, FPS without `DEPTH_SCALING`, mip-0-only texture,
unregistered texture, hook flag switched off, ...) and asserts that the
matching check fails — 16/16 mutations are caught (including a triangle wound
inside out). It runs in the suite as
`test_the_compliance_checker_actually_fails_on_broken_packs`, because an
auditor that only ever passes proves nothing. The pytest wrappers around the
auditor are mutation-tested too:
`check_test_suite_mutations.py` breaks the shipped pack five ways and
requires the matching test to fail — a test that passes or skips is a hole.

## Install (when you have a candidate)

A pack built here installs like any LAS add-on. PAYDAY 2 with
**SuperBLT + BeardLib + Legendary Armour Skins / Wardrobe Mod**. Extract the
pack's root folder into **`PAYDAY 2\assets\mod_overrides\`** (not
`mods\mod_overrides`). Back up saves and `mod_overrides` first; with the game
closed, move any previous copy of that folder completely out of
`mod_overrides` before extracting a new one (renaming inside the folder can
leave both versions active). Select the outfit in the outfit/armor menu with
Default gloves.

For the shipped port: download `lawson_las.zip` from the [release page](https://github.com/Man1nWhite/universal-modder/releases/tag/lawson-las-v2)
(or build it yourself — the bytes are identical), extract `Lawson_LAS/`, and
select **[LAS] Miranda Lawson**.

Test the menu preview first. If it crashes, stop and collect fresh crash/loader
logs plus exact game/BeardLib/LAS versions before trying anything else. Only
after the preview works, try a backed-up offline heist.

## Publish a release

This is the release route of the shipped port. The GitHub release is
tag-driven: on a `lawson-las-v*` tag the
[`lawson LAS pack` workflow](../../.github/workflows/lawson-las.yml) rebuilds
the pack, runs the tests and attaches the zip to the release of that tag.
Below, `N` is the next release number; the latest release is
`lawson-las-v2`.

1. Add `releases/lawson-las-vN.md` (the release page body) with its
   `<!-- pack_version: X.Y.Z -->` marker — the workflow stamps that version
   into the pack — and set `VERSION` in `build_las_pack.py` to the same
   value (a test keeps the two equal).
2. Rebuild the pack and its checksum from the repository root, and commit
   both (the zip must match the release asset):

   ```sh
   python tools/pd2-port/build_las_pack.py
   sha256sum dist/lawson_las.zip > dist/lawson_las.zip.sha256
   ```

3. If the bytes changed, update the size, checksum and audit result quoted
   in [`STATUS.md`](STATUS.md), and the size and checksum in
   `docs/pd2-las/HANDOFF.md` and the `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`
   table — tests pin them to the tracked pack.
4. Tag and push:

   ```sh
   git tag lawson-las-vN && git push origin lawson-las-vN
   ```

   The workflow creates the release page, uploads `lawson_las.zip` +
   `lawson_las.zip.sha256`, and fails loudly if the tests fail or if the
   runner's build differs from the committed bytes.

Every push to `main` also rebuilds the pack and exposes it as a workflow
artifact, so the zip is always downloadable from GitHub even between releases.

## Status and limits

- **Offline-validated only. Nothing is game-verified.** The bind-pose rebind
  is principled, but shoulder and hip alignment still need visual
  verification in game.
- **The retarget is tuned on one body.** The humanoid branch moves the torso,
  head and legs rigidly at 1:1, which is right for the shipped port because
  its source already stands at PD2's proportions (hips at 101.2 cm against
  101.8, head at 166.1 against 166.8). A character of another height or
  build has to be scaled or fitted first.
- **Sides are mapped by name after a half turn about Z** (the shipped source
  faces −Y, PD2 faces +Y), so `Left*` joints land on PD2's `Left*` bones and
  nothing is mirrored. A source with another facing or other side labels
  needs that checked before anything else.
- The pack follows the ModWorkshop LAS/MOOG guide (see
  `knowledge/games/payday-2/las-moog-outfit-porting.md`): `group=`-keyed
  materials with attested-only render templates, contour on TPP, DEPTH_SCALING
  on FPS, and PD2 normal layout (X in alpha, R white, B black, Y-flipped).
- The skin transfer is built from joint positions (stored frame orientations
  never enter), joints folded onto the same PD2 bone share one operator, and
  weights are smoothed over the welded vertex graph; `preview_check.py` gates
  all of it offline and rasters previews (source vs retarget vs
  decoded-from-pack).
- Provenance: a port inherits the rights position of its source. The shipped
  port's model and textures are ripped *Mass Effect 2* assets and `2b.rar` is
  a third-party reference. Fine for private use; **not cleared for
  redistribution** — the release ships as an unlicensed, non-commercial fan
  derivative, credited in `CREDITS.txt` and on the release page.
- No cooked-physics payloads are shipped; BeardLib's `unit_mat` registration
  supplies its default.
