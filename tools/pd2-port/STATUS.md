# LAWSON LAS pack — status and handoff

*Last updated: 2026-10-19, after the fourth check (the "quadruple check").*
*Everything here was measured; nothing is inherited from a previous session's memory.*

If you are a new agent picking this work up: read this page first, then
[`MODLOG.md`](MODLOG.md) (the journal, newest first) and the
[knowledge note](../../knowledge/games/payday-2/las-moog-outfit-porting.md)
(the reusable gotchas). This page is the *current state*; the journal is the
*history*.

## 1. What is shipped

| | |
|---|---|
| Pack | `dist/lawson_las.zip` — **0.1.2**, 9,123,392 bytes, sha256 `9c8a28368862edccc8030a9df378766a804665a750a70954f47b4168a3ce4ad2` |
| Release | [`lawson-las-v2`](https://github.com/Man1nWhite/universal-modder/releases/tag/lawson-las-v2) (pre-release) — assets: the zip + `lawson_las.zip.sha256` |
| Tag | `lawson-las-v2` → commit `282703f`; the v1 release stays up but **has holes in the skin** (see §4) |
| Docs | [`releases/lawson-las-v2.md`](releases/lawson-las-v2.md) is the release body (the workflow reads its `pack_version:` marker to stamp the build) |
| Status | *experimental — offline validated, never game-verified* |

Install: extract `Lawson_LAS/` into `PAYDAY 2\assets\mod_overrides\`. Needs
SuperBLT + BeardLib + Legendary Armour Skins (or Wardrobe).

## 2. The one command that tells you where things stand

```sh
python tools/pd2-port/check_all.py          # ~2 min: build check, audit, mesh, nm, mutations
python tools/pd2-port/check_all.py --full   # + the auditor self-test and the pytest suite (~10 min)
```

It prints one line per stage and exits non-zero if anything fails. Use it
first; it is the fastest way to tell a fresh checkout from a broken one.

## 3. Current check state (all green as of 2026-10-19)

| Check | Command | Result |
|---|---|---|
| Guide audit | `check_guide_compliance.py` | **38 pass, 1 warn, 0 fail** (39 checks) |
| Auditor self-test | `check_guide_compliance_self_test.py` | **16/16** mutations caught |
| Winding / tangent frame | `check_mesh_geometry.py` | **0** inverted triangles in TPP body, TPP head and FPS arms |
| Pack-level test mutations | `check_test_suite_mutations.py` | **5/5** broken packs caught by the pytest wrappers |
| Normal-map convention | `check_nm_convention.py` | not decidable from the files — the provenance decides it (§5) |
| Test suite | `pytest -q tests` | **190 passed, 5 skipped** |
| Geometry gates | `preview_check.py report` | RESULT OK (max weld discontinuity 2.38 cm) |

The single warning is `G1` (the normal maps' green channel) — it is a *known,
documented* warning, not an open bug.

## 4. What the fourth check found (and fixed)

**The 0.1.1 pack had 1,027 triangles wound inside out** (946 in the TPP body,
81 in the head, 291 in the FPS arms — the body and the head are counted in
the TPP total). The game culls such a triangle, so 0.1.1 showed **holes in
the chest, shoulders and arms** and shaded the skin around them backwards.

* Cause: the bind-pose transfer fits every bone piece *independently*
  (`rig_target.target_ops`). Where the ME2 and the PD2 rigs disagree, the
  fits end up 120–156° apart, the neighbouring pieces are rotated against
  each other, and the triangles between them fold back on themselves. The
  source ME2 meshes have **zero** inverted triangles, so the transfer
  created them.
* Fix (shipped in 0.1.2): `rig_target.repair_winding()` reverses every
  triangle that faces away from its own vertex normals. The normals describe
  the *unfolded* surface, so the winding is what is wrong, and the ME2
  meshes are corner-split (no shared edges), so flipping a triangle cannot
  desync its neighbours. 0 inverted triangles remain.
* Guard: audit check `N3` fails any pack with inverted triangles (it failed
  on 0.1.1), and the auditor's self-test gained an "inverted triangle"
  mutation.

**What is still wrong (not fixed, by design):** the *crease* remains where
the rigs disagree. The repair removes the holes and the black patches, not
the local fold. See §6 for the planned fix.

## 5. The normal-map green channel — settled as far as it can be

`check_nm_convention.py` measures what the files can say: the source maps are
genuine tangent-space normal maps (blue saturated at 255, red and green
centred on 128), but their blue channel is saturated, so the height field is
not recoverable and an OpenGL (Y+) and a DirectX (Y−) map are *equally*
self-consistent with their own image layout. The file cannot settle it.

The provenance can: Mass Effect 2 runs on DirectX 9, whose normal maps are
Y−, and PD2 wants OpenGL Y+ (the ModWorkshop guide). So the **default build
(which inverts the green channel) is correct**; `--keep-nm-green` is only
right for a Y+ source. If the lighting looks inverted in game, that is the
flag to flip — and the in-game look is the final word.

## 6. The next piece of work: a consistent bind-pose transfer

This is the open task, and the expensive one. It is **not** a formatting
problem — it changes the shape of the skin, so it needs a real review.

### The constraint set (do not break these)

1. The skin is worn by a PD2 character, so the mesh must follow **PD2's
   skeleton**: each bound piece has to sit on the PD2 bone it is bound to,
   and the silhouette must follow PD2's proportions (the PD2 A-pose, not
   ME2's). A transfer that keeps ME2's proportions is *wrong* for a skin.
2. The mesh must stay **coherent**: no triangle may fold (see §4).
3. Keep the parts that already work: 3 weight influences per vertex, the
   30 finger bones, the arms-only FPS cut, the contour/unique material
   rules, the DXT5 texture layout, the 54-bone rig contract.

### What was measured (do not re-derive this)

* The two rigs are *nearly identical* in the spine and head: the source's
  pelvis is at z = 101.2 and its head at 166.1; PD2's are at 101.8 and
  166.8. The source and the target scene are both Z-up.
* They differ strongly in the *distal limbs*. The ME2 A-pose has the wrists
  **in front** of the elbows (the source's left wrist is at
  `(49.3, −12.6, 108.8)`, its elbow at `(40.4, −5.9, 115.9)`), while the
  PD2 rig puts the hand **behind** the forearm (the right hand at
  `(46.0, 18.7, 124.5)`, its forearm at `(39.5, −1.0, 133.3)`) — about
  31 cm of disagreement in y. The feet disagree the same way: the ME2 toe
  is at y = −3.6 (forward of its ankle at 8.1), the PD2 toe at y = +15.1
  (behind its foot at 0.9). The pelvis-to-knee direction agrees in both.
  **Open question:** whether the PD2 rig's distal bones really are yawed
  that way, or whether the rig extraction (or the 2B donor's own pose)
  is responsible — worth one careful look before designing the fix.
* The current scheme's tear angles (the rotation between a bone's operator
  and its parent's): spine 156°, up-legs 149°, feet 133°, thumbs 122°,
  forearms 113–117°, hands 87°. Everything else is under 30°.
* Two prototypes were tried and **both rejected**:
  - *Hierarchical operators* (each bone relative to its parent, using the
    parent's offset as the direction): 0 inverted triangles in the TPP body,
    but Body 2 unchanged (665) and — decisively — the mesh became rigid
    with respect to the source, i.e. ME2's proportions, which breaks
    constraint 1.
  - *Parent-offset directions with the independent fits*: worse (832
    inverted in Body 2).
* The `rig_target.py` docstring still describes the *old* rationale ("one
  operator per target bone, a rigid fit of the source bone segment onto the
  target bone segment"). Update it when the transfer changes.

### A shape that is likely to work

Keep the per-bone rigid fit (it is what makes the mesh follow PD2's bones),
but make the operators **mutually consistent** instead of independent:
derive each bone's rotation from its parent's operator plus the *local*
angle difference between the two rigs, and resolve the twist consistently
(the minimal rotation between two directions leaves the roll about the bone
axis free — that freedom is what tears the mesh). The hard part is that the
rigs' *distal* limbs disagree by tens of degrees, so the "local angle
difference" is not small there; the surface between the elbow and the wrist
has to absorb it without folding.

## 7. Environment and workflow (the things that cost time)

* **Recreate the venv** if it is missing (it does not survive a sandbox
  wipe): `python3 -m venv .venv && .venv/bin/pip install pillow==13.0.0
  numpy==2.4.6 pyyaml pytest`.
* **The pack's bytes depend on the interpreter**: the zip is built with
  Python 3.11 + `pillow==13.0.0` + `numpy==2.4.6`. A different Python or
  zlib changes the deflate output, and CI compares the tracked pack byte for
  byte. `uv run` (the repo's default) is **not** that environment — build
  and compare inside `.venv` or in CI with the pinned versions.
* **Never upload release assets from the sandbox**: `gh release upload`
  fails with EOF there. Tag the release and let the `lawson-las.yml` workflow
  build and upload (it creates the release if needed).
* The ME2 source zip and `2b.rar` sit in the repo root. `2b.rar` is RAR5:
  there is no preinstalled tool, so build one —
  `curl -L https://codeload.github.com/pmachapman/Unrar/tar.gz/refs/heads/master
  | tar xz -C /tmp && make -C /tmp/unrar-master -j4` — and run
  `unrar x 2b.rar -o+/tmp/rarx` (the `-o` is attached; a positional
  out-directory is read as another archive). The reference pack is the
  2B LAS unit, used as the ground truth for the rig contract and the
  manifest layout.
* `um publish check .` and `um kb check --index` are the repo-wide gates;
  run both before pushing (0 failures, the warnings are pre-existing).
* Sequence file edits — parallel edits to the same file race.

## 8. Related work on other branches (do not duplicate it)

A parallel agent session works on `arena/136395ac-universal-modder` (branch
`136395ac`). It ran its own double/triple/quadruple sweeps and added a
**handoff kit of its own**:

* `docs/pd2-las/HANDOFF.md` — a 5-minute start-here (state, quickstart,
  do-not-break invariants, dead ends, environment traps, next actions);
* `tools/pd2-las/bootstrap.sh` — one command from a clean checkout (or after
  a sandbox wipe) to a built pack and green tests: venv, 2B template
  extraction, build, pytest, pyflakes;
* `knowledge/games/payday-2/las-armor-skin-outfit.md` — its own knowledge
  note (a different file from the one this branch edits, so the two do not
  conflict textually).

The two lines are complementary and neither contains the other: **this
branch** has the winding defect and its repair, the guide audit with the
`N3` check, and this status page; **that branch** has the bootstrap script
and its own sweeps (crash-safety bounds, build-input provenance, a 2B
structural comparison). It does *not* have the winding fix — the defect is
only found on this line. If both are to be kept, merge them deliberately
(the root `README.md` is the one file both sides edit).

## 9. Where the code is

| File | What it is |
|---|---|
| `build_las_pack.py` | the builder (`python tools/pd2-port/build_las_pack.py` → `dist/lawson_las.zip`); `--check` validates without writing, `--version` stamps the manifest, `--keep-nm-green` keeps the source's green channel |
| `me2_dae.py` | the ME2 COLLADA importer (meshes, joints, skin weights) |
| `rig_target.py` | the retarget: bone mapping, per-bone operators, the rebind, `repair_winding()`, the FPS cut |
| `las_model.py` | the DODB model writer (3 weights, tangent channels 22/23) |
| `dds.py` | DXT5 encode/decode and PD2's packed normal-map layout |
| `dmodel.py` | the Diesel model reader (also `DieselModel.from_bytes` for a model inside a pack) |
| `reference/las_rig.json` | the 60-entry PD2 rig contract (ids, parents, names, hashes) |
| `check_guide_compliance.py` | the guide audit (S/M/K/F/T/P/N/G checks) |
| `check_guide_compliance_self_test.py` | the auditor's mutation test (16 cases) |
| `check_mesh_geometry.py` | winding, tangent frame and the UV/normal agreement of the built model |
| `shade_check.py` | a small z-buffered renderer: the retargeted mesh with the pack's own normals |
| `check_nm_convention.py` | the normal-map convention analysis (§5) |
| `check_test_suite_mutations.py` | breaks the shipped pack and requires the pytest wrappers to fail |
| `preview_check.py` | the geometry gates and the raster previews (no Blender needed) |
| `resolve_rig_names.py` | recovers PD2's finger bone names from the rig contract's hashes |
| `releases/lawson-las-v*.md` | the release bodies; the `pack_version:` marker drives the build |
