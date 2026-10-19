# PAYDAY 2 — Miranda Lawson Legendary Armour Skins (LAS) outfit

This directory builds an **equipable, additive full-body outfit** for PAYDAY 2 —
Miranda Lawson as a [Legendary Armour Skins](https://github.com/Vladik268/P2)
registration — on the contract demonstrated by the user-supplied `2b.rar`
reference pack. It is **not** a character-model replacement.

The previous character swaps (`lawson_clover` / `lawson_bonnie` /
`lawson_sydney`) and the old-model outfit packs are retired and deleted; see
the [restart audit](../../docs/audits/2026-10-18-old-model-retired-las-restart.md)
and the journal in [`MODLOG.md`](MODLOG.md).

## Source and outputs

| | |
|---|---|
| Source of truth | `PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip` (repo root) — rigged COLLADA + textures |
| Rig contract | `reference/las_rig.json` — the PD2 biped skeleton an LAS unit animates on, extracted from `2b.rar`'s model by `extract_las_rig.py` (skeleton data only; no 2B art) |
| Output | `dist/lawson_las.zip`, root `Lawson_LAS/` (deterministic build; **tracked in git** and published as the release asset) |
| Checksum | `dist/lawson_las.zip.sha256` (tracked; CI refuses to publish a build that differs from it) |
| Release | [`lawson-las-v1`](https://github.com/Man1nWhite/universal-modder/releases/tag/lawson-las-v1) — notes in [`releases/lawson-las-v1.md`](releases/lawson-las-v1.md) |

## Build

Python 3.10+, Pillow and numpy (the repo's own dependencies):

```sh
python tools/pd2-port/build_las_pack.py          # -> dist/lawson_las.zip
python tools/pd2-port/build_las_pack.py --check  # validate only
# --version stamps the release version into build_manifest.json
# (default 0.1.1; the release notes carry the same value)
# --keep-nm-green keeps the source Y channel instead of the default PD2 flip
# (only for sources already authored with PD2's green convention)
python tools/pd2-port/preview_check.py report    # geometry gates on the rebind
python tools/pd2-port/preview_check.py render DIR  # + raster previews (flat, textured, diff)
python tools/pd2-port/check_guide_compliance.py  # audit the pack against the
                                                # ModWorkshop LAS/MOOG guide
python tools/pd2-port/resolve_rig_names.py       # recover PD2 bone names from
                                                # the rig contract's hashes
python -m pytest -q tests/test_las_pack.py
```

The build is **deterministic**: same source + same tool code -> the same zip
bytes (fixed zip timestamps, sorted entries). The tracked
`dist/lawson_las.zip` is therefore exactly what the release serves.

## Pipeline

1. **`me2_dae.py`** — imports the ME2 COLLADA: meshes, materials, skin
   weights, joint hierarchy with bind transforms (cm, Z-up).
2. **`rig_target.py`** — maps ME2 joints onto the PD2 rig (twists, fingers and
   facial chains fold into parent bones; sides swap: the ME2 rig labels `Left*`
   at +X where PD2 has `Right*`), then rebinds the skin with the standard
   bind-pose transfer `p' = Σ wᵢ·(W_pd2·W_me2⁻¹)·p`.
3. **`las_model.py`** — authors DODB `.model` files (canonical section order,
   0-based SkinBones palette indices, absolute topology indices, `shadow_caster`
   material, no index-count trimming).
4. **`build_las_pack.py`** — assembles the 2B-shaped pack: `main.xml`
   (Hooks + AddFiles), `hooks/lawson.lua` (`LegendaryArmours.lawson` with
   `hide_mask` / `hide_armor` / `replace_all` / `fps_hide_armor` /
   `fps_replace_body`), localization, TPP unit `lawson` and FPS unit
   `fps_lawson` (arms cut by dominant bone), DXT5 `.texture` pairs with full
   mip pyramids, `CREDITS.txt` and a hash manifest.

Shared format libraries: `dmodel.py` (Diesel `.model` reader) and `dds.py`
(DXT5 encode/decode). `glb_render.py` renders a GLB bind-pose preview headless
in Blender if you need one.

## Guide compliance

The pack follows the [ModWorkshop LAS/MOOG outfit guide](https://wiki.modworkshop.net/books/payday-2-mod-creation/page/legendary-armor-skinslasmoogoutfit-module-guide)
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
so a pack that drifts from the guide fails the build. Current state: **36 pass,
1 warning, 0 failures** — the warning is the normal maps' green-channel
convention, which only the running game can settle.

## Install (when you have a candidate)

Download `lawson_las.zip` from the [release page](https://github.com/Man1nWhite/universal-modder/releases/tag/lawson-las-v1)
(or build it yourself — the bytes are identical).

PAYDAY 2 with **SuperBLT + BeardLib + Legendary Armour Skins / Wardrobe Mod**.
Extract `Lawson_LAS/` into **`PAYDAY 2\assets\mod_overrides\`** (not
`mods\mod_overrides`). Back up saves and `mod_overrides` first; with the game
closed, move any previous `Lawson_LAS` completely out of `mod_overrides` before
extracting a new one (renaming inside the folder can leave both versions
active). Select **[LAS] Miranda Lawson** in the outfit/armor menu with Default
gloves.

Test the menu preview first. If it crashes, stop and collect fresh crash/loader
logs plus exact game/BeardLib/LAS versions before trying anything else. Only
after the preview works, try a backed-up offline heist.

## Publish a release

The GitHub release is tag-driven — the
[`lawson-las-pack` workflow](../../.github/workflows/lawson-las.yml) rebuilds
the pack, runs the tests and attaches the zip to the release of that tag:

```sh
git tag lawson-las-v1 && git push origin lawson-las-v1
```

1. Update `releases/lawson-las-v1.md` (the release page body) and the
   `<!-- pack_version: X.Y.Z -->` marker in it — the workflow stamps that
   version into the pack.
2. Rebuild and commit the pack: `python tools/pd2-port/build_las_pack.py` and
   commit `dist/lawson_las.zip` + `dist/lawson_las.zip.sha256` (the zip must
   match the release asset).
3. Tag and push; the workflow creates the release page, uploads
   `lawson_las.zip` + `lawson_las.zip.sha256`, and fails loudly if the tests
   fail or if the runner's build differs from the committed bytes.

Every push to `main` also rebuilds the pack and exposes it as a workflow
artifact, so the zip is always downloadable from GitHub even between releases.

## Status and limits

- **Offline-validated only. Nothing is game-verified.** The bind-pose rebind is
  principled but shoulder/hip alignment still needs visual verification; the
  side-swap maps by world side — if the source mesh itself is mirrored,
  asymmetric surface detail will show it.
- The pack follows the ModWorkshop LAS/MOOG guide (see
  `knowledge/games/payday-2/las-moog-outfit-porting.md`): `group=`-keyed
  materials with attested-only render templates, contour on TPP, DEPTH_SCALING
  on FPS, and PD2 normal layout (X in alpha, R white, B black, Y-flipped).
- The skin transfer is segment-fit (frame conventions never enter), folds
  share one transform per target bone, and weights are smoothed over the
  welded vertex graph; `preview_check.py` gates all of it offline and rasters
  previews (source vs retarget vs decoded-from-pack).
- Provenance: the ME2 model/textures are ripped game assets and `2b.rar` is a
  third-party reference. Fine for private use; **not cleared for
  redistribution** — the release ships as an unlicensed, non-commercial fan
  derivative, credited in `CREDITS.txt` and on the release page.
- No cooked-physics payloads are shipped; BeardLib's `unit_mat` registration
  supplies its default.
