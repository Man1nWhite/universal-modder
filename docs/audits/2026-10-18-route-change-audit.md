# Repository audit and route change — retire the old-model pipeline, start the LAS route

**Date:** 2026-10-18
**Baseline:** `66cfdb7c0132474e710dc149f8a64146a78784f0` (single upstream commit, "Add files via upload")
**Reference product spec:** `2b.rar` (user-supplied)
**New source material:** `l4d2_miranda_lawson_1.zip` (user-supplied)
**Scope:** full audit of the PAYDAY 2 Lawson experiment grafted onto the
universal-modder toolkit; execution of the user's decision to delete the
old-model work and start over on the Legendary Armour Skins (LAS) route.

## Verdict

**The old-model route is retired as a dead end.** Everything the repo carried
for it — character replacements, outfit packs, the model-surgery pipeline,
extracted game files and its documentation — has been deleted (114 files,
~135k text lines plus ~85 MB of binary assets). A new, tested pipeline for the
LAS route has been started in `tools/pd2-las/`, built from the L4D2 Miranda
Lawson source model and following the registration contract of `2b.rar`.
Diesel `.model` authoring is the one remaining hard step; nothing is
game-verified yet.

## What was here (the old-model experiment)

Beside the toolkit (`um/`, `skills/`, `knowledge/`, `examples/` — unaffected by
this audit and healthy), the checkout carried a PAYDAY 2 Miranda Lawson
character experiment in four layers:

| Layer | Contents | Problem |
| --- | --- | --- |
| Sources | `Lawson model/` (ME2-ripped OBJ + textures), `clover/`, `Bonie/`, `Sydney/` (extracted PAYDAY 2 game files), `LawsonME2/` (empty placeholder) | Game/ripped assets checked into the repo, against the repo's own `CONTRIBUTING.md` rule ("no game files") and with unresolved redistribution rights |
| Pipeline | `tools/pd2-port/` (16 scripts + README + repair journal): Diesel `.model` surgery (`dmodel.py`, `build_model.py`, `build_character.py`, `rig_lawson.py`, `repair_skin_palettes.py`), outfit builders, package/texture helpers | Hard-coded external workspace (home-directory `pd2-work/`, hashlist, Blender stubs); not reproducible from a clean checkout; every runtime defect was "fixed" by speculative binary patching |
| Outputs | `dist/lawson_{clover,bonnie,sydney}.zip`, `dist/lawson_outfit.zip`, `dist/lawson_outfit_BeardLib.zip` (~35 MB) | Derivatives of the ripped assets; the character packs replace heisters and the outfits inherit the same broken rig |
| Docs/tests | `tools/pd2-port/{README,MODLOG}.md`, 2 audit reports, 3 knowledge notes, 3 test modules (~58 KB) | Documented and tested the dead end; the journal records ≥4 crash-fix revisions without a verified fix |

Runtime history (user reports): `lawson_clover` loaded but its model was
visibly broken; the LAS-branded outfit crashed (menu `spawn_unit` /
`load_packages` failures); registration "repairs" could not fix a rig/UV export
that was broken at the source. Directly changing shipped character models was
the wrong product and the wrong technique.

## Audit findings

1. **P1 — dead end, confirmed.** Surgically editing shipped Diesel `.model`
   containers (SkinBones palettes, DODB section renumbering, FPS arm cuts) was
   the pipeline's core. Multiple crash classes were patched speculatively; the
   final state is a broken-looking character and a crashing outfit. New
   evidence is unobtainable without the game. **Action: deleted, route
   replaced** (this document).
2. **P1 — repo hygiene.** Extracted game files and ME2 rips were tracked
   (~85 MB), contrary to `CONTRIBUTING.md`. Redistribution rights were already
   flagged as a release gate in the previous audits. **Action: deleted.**
3. **P2 — non-reproducible builds.** `build_model.py` / `rig_lawson.py`
   required untracked external inputs. Only archive-level rebuilding worked.
   **Action: deleted with the route; the new pipeline is reproducible from the
   tracked source zip** (`build_las.py`, offline tests).
4. **P2 — misleading integration naming.** "LAS" branding registered a
   BeardLib `PlayerStyle` in one variant and an actual `LegendaryArmours` entry
   in another; instructions confused the two. **Action: documented in the
   field note; the new scaffold is LAS-only and its contract is asserted in
   tests.**
5. **Toolkit health (context).** The deletions do not touch `um/`, skills or
   examples. Current suite after the change: **172 passed, 5 skipped** (the
   skips are multimedia/MSYS environment gates). `um kb check` passes;
   `knowledge/INDEX.md` regenerated (245 notes).

## What `2b.rar` establishes (the product)

A standalone LAS armor-skin add-on: hook on `lib/tweak_data/armorskinstweakdata`
creating `LegendaryArmours.twobee` with `unit` + `fps_unit` and
`hide_mask` / `hide_armor` / `replace_all` / `fps_hide_armor` /
`fps_replace_body`; BeardLib `<table>` manifest registering icon texture,
df/nm pairs and `unit_mat` model units; separate third-person and first-person
models on the PD2 player skeleton (bone names recovered from the embedded
hashlist of `2b.model`, recorded in `tools/pd2-las/las_target_skeleton.json`).
Its defects (unregistered `ss.model`, empty `cooked_physics`, `Hooks`/`hooks`
casing mismatch) are documented and not to be copied.

## The new source (`l4d2_miranda_lawson_1.zip`)

A complete, working L4D2 character mod (VPK v1, 25 entries, CRC-checked):
third-person `miranda.smd` (104 bones, 9,874 vertices, 16,433 triangles),
first-person `miranda_arms.smd` (53 bones, 2,892 triangles), 8 DXT5 VTF
materials and 6 VMTs. It replaces Rochelle in L4D2 and is thus a *finished*
body+arms source — exactly what the LAS route needs — instead of a mesh to be
surgically force-fit onto a heister. Provenance: fan mod of ME2-ripped assets;
private experimental use only.

## Actions taken (2026-10-18)

**Deleted (114 files):** `Bonie/`, `Sydney/`, `clover/`, `Lawson model/`,
`LawsonME2/`, `dist/` (all five ZIPs), `tools/pd2-port/` (entire pipeline),
`tests/test_{pd2_packages,outfit_pack,outfit_beardlib_pack}.py`, the two
previous audit reports, and the three old PAYDAY 2 knowledge notes (their
still-true contract facts are folded into the new field note).
`.gitignore` dist exceptions removed. Top-level README section rewritten.

**Started (`tools/pd2-las/` + `tests/test_pd2_las.py`):**

| Step | Status |
| --- | --- |
| VPK extraction (safe paths, CRC checks) | done, tested |
| Source model parse (bones, weights, triangles, materials, body + arms) | done, tested |
| VTF → DDS (`.texture`) + PNG previews, verified mip order | done, tested |
| BC3 icon encoder (naive endpoints, c0 > c1) | done, tested |
| LAS pack scaffold (2B contract: hook, manifest, locales, unit/object/material_config) | done, tested |
| Skeleton mapping plan (`skeleton_map.json`) | recorded |
| Diesel `.model` authoring (skinned to PD2 skeleton) | **open — last hard step** |
| In-game verification | **open — blocked on models** |
| Redistribution clearance | **open — release gate** |

Build: `python tools/pd2-las/build_las.py` → `build/pd2-las/` (gitignored,
`Miranda_LAS/` marked `WIP_DO_NOT_INSTALL.txt`, `models_present=false`,
`runtime_verified=false` in `BUILD_INFO.json`). 23 new structural tests run
against the tracked source zip; full suite **172 passed, 5 skipped**.

## Open items

1. Author the two Diesel models (`miranda.model`, `fps_miranda.model`) on the
   PD2 player skeleton using `skeleton_map.json`; the retired `dmodel.py`
   format knowledge is gone — re-derive from `diesel-modding/payday2-model-tool`.
2. Materials: EyeRefract eyes, phong hair, alpha-masked lashes.
3. Test ladder in the real game (menu → offline heist → animations, alignment,
   mask/armor hiding). Structural tests are not an engine test.
4. Resolve ME2 asset redistribution before any public release; everything so
   far is private experimental tooling.
