---
kind: game
title: "LAS armor-skin outfits in PAYDAY 2 from a Source-engine character mod"
game: "PAYDAY 2"
games_also: ["Left 4 Dead 2"]
game_version: "User build 1.0.0-159028 for the earlier crash logs; no agent-side game runtime"
platform: windows
engine: diesel
route: asset-only
tools: ["Python 3.11", "SuperBLT", "BeardLib 5.2.0", "Legendary Armour Skins 4.x"]
anti_cheat: "Offline only; no client, loader or game installation changes"
status: in-progress
agents: ["Arena.ai agent"]
humans: []
date: 2026-10-18
links:
- "https://github.com/Vladik268/P2/tree/b7c38c1d358fe054df51201788126c25a0da1938/mod/Legendary%20Armour%20Skins"
- "https://github.com/simon-wh/PAYDAY-2-BeardLib/tree/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046"
tags: [payday-2, diesel, las, armor-skin, l4d2, source-engine, vpk, mdl, vtf, outfit]
---

# LAS armor-skin outfits in PAYDAY 2 from a Source-engine character mod

> **Status 2026-10-19:** the standalone LAS pack is built and offline-verified
> end to end — Diesel `.model` authoring (verified codec + divergence-filter
> retarget onto the 2B skeleton), guide-compliant `material_config`s, textures,
> reproducible `Miranda_LAS.zip`, 192 tests. Four verification passes and a
> structural diff vs the 2B reference are in
> `docs/audits/2026-10-19-las-guide-compliance.md`. What remains: the user-side
> in-game checklist (`docs/pd2-las/in-game-checklist.md`) and the ME2
> redistribution-rights gate before any public release. Start-here doc for the
> next agent: `docs/pd2-las/HANDOFF.md`; one-command rebuild:
> `bash tools/pd2-las/bootstrap.sh`.

## Setup

- Source material: `l4d2_miranda_lawson_1.zip` (GameMaps.com "Miranda Lawson"
  L4D2 addon; a single-file VPK replacing Rochelle: third-person
  `survivor_producer.{mdl,vvd,phy,dx80/dx90/sw.vtx}`, first-person
  `v_arms_producer_new.*`, 8 VTF + 6 VMT materials). User-supplied private input.
- Product-contract reference: `2b.rar` (2B LAS pack: `LegendaryArmours.twobee`
  hook on `lib/tweak_data/armorskinstweakdata`, unit + fps_unit, hide_mask /
  hide_armor / replace_all / fps flags, BeardLib `main.xml` + `unit_mat`
  registration). Studied as text/binary, not installed.
- Pipeline: `tools/pd2-las/` (Python 3.11, Pillow/numpy for previews and the
  icon encoder), tests in `tests/test_pd2_las.py` against the tracked zip.
  No PAYDAY 2 install in this environment.

## Route and why

The retired route replaced Clover/Bonnie/Sydney by surgically editing their
Diesel `.model` containers (SkinBones palettes, DODB section renumbering, FPS
arm cuts) and built outfit packs on the same rigged mesh. It was a dead end:
the source rig/UVs were broken at export, the character packs rendered wrong,
the LAS-branded outfit crashed, and every "fix" was a speculative binary patch
that could not be verified without the game. Direct model surgery is where the
time went and none of it produced a loadable, correct character.

The new route adds a standalone LAS armor skin instead of changing any shipped
model: one unit + one fps unit registered through the LAS
`LegendaryArmours` table, exactly the 2B contract. The mesh does not start from
a broken rig this time — the L4D2 mod is a complete, working character model
(third-person body and first-person arms with their own materials).

## How the game works (what we had to learn)

- **LAS registration contract** (from `2b.rar` + LAS 4.x sources): a SuperBLT
  hook on `lib/tweak_data/armorskinstweakdata` creates
  `LegendaryArmours.<id>` with `category`, `unit`, `fps_unit` and the boolean
  flags `hide_mask`, `hide_armor`, `replace_all`, `fps_hide_armor`,
  `fps_replace_body`. LAS maps the item into Outfit/Player Styles
  (`las_<id>` on LAS 4.x). A BeardLib `PlayerStyle` is NOT the same contract.
- **BeardLib packaging** (2B `main.xml`): a `<table>` with `<Localization>`,
  `<Hooks source_file=...>`, and `<AddFiles>` registering `texture`, `df_nm`
  (df+nm pair shorthand) and `unit_mat` (model+object+unit+material_config
  shortcut) resources. Texture registration must cover every new `.texture`.
- **Target object naming** (from `2b.model`'s embedded hashlist): the outfit
  model uses the PD2 player skeleton (`root_point`, `Hips`, `Spine`, `Spine1`,
  `Spine2`, `Neck`, `Head`, `eyeAim`, finger chains, `a_weapon_*`, `aim`,
  `BackPack1`, leg chain) plus graphics objects `s_body`, `g_body`,
  `g_body_lod1`, `g_head`, `g_head_lod1` and collision `c_sphere_*`/`c_capsule_*`.
- **Source studio formats** (source-sdk-2013 `studio.h`/`optimize.h`): MDL 48
  (L4D2) with struct-relative `sznameindex` offsets, 216-byte bones, 64-byte
  texture records, 16-byte bodyparts, 116-byte meshes; VVD v4 with
  `numLODVertexes[MAX_NUM_LODS=8]` and 48-byte vertices (3 bone weights);
  VTX v7 `#pragma pack(1)` (FileHeader 36 bytes with `bodyPartOffset`,
  strip groups reference `origMeshVertID` back into the VVD).
- **VTF 7.4**: resource entries at offset 80 (IMAGE tag 0x30 with absolute
  offset), low-res width/height are single bytes at 61/62, and the high-res
  mip chain is stored **smallest mip first** (mip 0 is at the tail — verified by
  decoding both orders of the real face texture). DXT5 payloads convert to DDS
  (PAYDAY 2 `.texture`) by reversing the chain; DXT5 colour endpoints must be
  written c0 > c1 or decoders render blocks as holes.

## Build steps

```sh
bash tools/pd2-las/bootstrap.sh    # venv + 2B templates + build + tests + lint
# or, manually:
python tools/pd2-las/build_models.py --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
python -m pytest -q tests/
```

`build_las.py` (extract / inventory / textures / scaffold stages) feeds the
pack scaffold; `build_models.py` builds the models and auto-creates the
scaffold if missing, then zips. Output goes to `build/pd2-las/` (gitignored):
`miranda.model`, `fps_miranda.model`, `Miranda_LAS/` (installable pack) and
`Miranda_LAS.zip` (reproducible, fixed timestamps), plus `previews/`,
`textures/`, `source_inventory.json`. Provenance (payload hashes, source zip
hash, 2B template input hashes) lives in `Miranda_LAS/BUILD_INFO.json`.

## Verification

- 192 offline tests (5 skip without ffmpeg): readers against the tracked
  source zip, byte-exact Diesel codec round-trips, retarget coherence
  (weights, winding, signed volumes, bind placement), pack/registration
  contract vs 2B, guide material_config contract, zip reproducibility.
- Four verification sweeps (see the compliance audit): guide conformance
  audit + fixes, build-flow bug fixes, deep artifact probes (index/atom
  bounds, skinbones `rotations=inv(world)`, UV = `1 − v_src` numerically,
  texture provenance byte-equal to fresh VTF re-derivations), and a
  structural diff vs the 2B reference (identical schema at every layer the
  engine reads).
- **Not verified:** anything in-game. Known watch items are checklist
  items 17–18 (normal-map Y+ orientation, contour silhouette) plus the
  boot-sole ground clip (~12 cm).

## Gotchas

1. **Symptom:** rebuilt packs crashed in `SkinBones`/`load_packages` after
   minutes of binary patching. **Cause:** surgical edits of shipped character
   models (bone-mapping indices, section-ID contiguity) with no game oracle.
   **Fix:** don't change shipped models at all — ship a standalone LAS item
   like the 2B reference. Treat the old route as abandoned, not "almost fixed".
2. **Symptom:** VPK entries read as garbage headers. **Cause:** `entry_offset`
   is relative to the end of the directory tree, not the file start; root-level
   files use a single-space folder marker. **Fix:** add `tree_start + tree_size`
   and map `" "` to the bare stem.
3. **Symptom:** VTF→DDS previews showed tiled mip garbage at the top of mip 0.
   **Cause:** VTF stores the high-res chain smallest-mip-first and the first
   slice builder kept file order. **Fix:** slice in file order, then reverse to
   mip 0 first; sanity-check by decoding both orders of a real texture.
4. **Symptom:** DXT5 icon decoded with transparent holes. **Cause:** colour
   endpoints written with c0 <= c1 select the 3-colour + transparent-index
   block mode. **Fix:** always emit c0 > c1.
5. **Symptom:** `sznameindex`-style names resolved to binary noise.
   **Cause:** Source `sznameindex` fields are offsets relative to their own
   struct, not file offsets. **Fix:** `struct_start + sznameindex`.
6. **Symptom:** mesh/strip-group strides guessed from one file looked wrong.
   **Cause:** VTX structs are `#pragma pack(1)` (mesh 9 bytes, strip 27,
   group 25) while MDL structs are 32-bit aligned (mesh 116). **Fix:** take
   strides from `source-sdk-2013` headers; verify arrays tile exactly.
7. **Symptom:** retargeted models came out as ribbon blades or collapsed
   limbs. **Cause:** raw frame-delta transfer fails in every form tried
   (`v·inv(S_j)·W`, anatomical frames, shortest-arc, per-source Umeyama,
   unit-scaled deltas), and a single shared fit across both legs collapses
   the thighs onto one point. **Fix:** target-centric per-bone Umeyama fits
   with divergence filtering (>30° from global rotation → inherit nearest
   kept ancestor), hand subtrees sharing the palm fit, leg fits kept local
   and mirrored. See `retarget_maps` in `tools/pd2-las/build_models.py`.
8. **Symptom:** `Miranda_LAS.zip` differed byte-wise between identical
   builds. **Cause:** `zipfile` embeds file mtimes. **Fix:** fixed ZipInfo
   timestamps (2020-01-01) + 0644 perms in `las_pack.zip_pack`; asserted in
   tests.
9. **Symptom:** a clean-checkout build silently produced no pack and no zip;
   `--stage inventory` left no `source_inventory.json`. **Cause:**
   `build_models.py` only refreshed a pre-existing scaffold, and
   `build_las.py` gated the inventory write to *other* stages. **Fix:**
   auto-scaffold in `build_models.py`, inventory always persisted. Both
   covered by tests now.
10. **Symptom:** arena sandbox wipes `.venv`/`/tmp`/`build` and rewinds local
    git so the worktree looks like untracked files on `66cfdb7`. **Cause:**
    sandbox snapshot restore. **Fix:** the work is on the remote —
    `git fetch && git reset --hard origin/<branch>`, then
    `bash tools/pd2-las/bootstrap.sh`. Push early; this happened 3×.
11. **Symptom:** API friction. **Cause:** convenience wrappers differ from
    stdlib guesses. **Fix:** `VpkArchive.from_zip(path_str, name)` takes a
    path not a `ZipFile`; `ModelFile.read(data)` not `read_bytes`;
    `skeleton_map.json` is `map` / `drop.patterns` / `target_only.names`;
    dropped/unmapped source bones fold into the nearest mapped ancestor
    (that is how facial flex bones and `hlp_*` helpers are absorbed).

## Assets

All geometry and textures come from the user-supplied L4D2 addon (itself a
fan-made Mass Effect 2 character rip). No fal generation. The menu icon is the
face diffuse cropped/resized to 256×256 and BC3-encoded by
`tools/pd2-las/dds_encode.py` (naive endpoints; fine for UI, not for
materials).

## Open questions

1. **In-game verification ladder** (menu preview → offline heist →
   animations, mask/armor hiding, FPS alignment) — the only remaining
   engineering unknown. Checklist: `docs/pd2-las/in-game-checklist.md`.
   Watch items: normal-map OpenGL Y+ (flip green if lighting inverts),
   contour silhouette, boot-sole ground clip (~12 cm).
2. **Redistribution rights** for ME2-derived assets: private experimental
   use only until resolved; never a public release. This is a release gate,
   not a code problem.

Resolved since the route change: Source mesh → Diesel `.model` authoring
(verified `diesel_model.py` codec + retarget, see `tools/pd2-las/README.md`);
material strategy (`*.material_config` with diffuse+normal DXT5, `CONTOUR`
per the ModWorkshop guide, `DEPTH_SCALING` on fps — no in-model texture
hashing, no EyeRefract/phong surgery).
