# pd2-las — Miranda Lawson as a PAYDAY 2 Legendary Armour Skins outfit

> Quickstart: `bash tools/pd2-las/bootstrap.sh` (venv + 2B templates + build +
> tests). Context for a new agent: [`docs/pd2-las/HANDOFF.md`](../../docs/pd2-las/HANDOFF.md).

**Status: textures + scaffold + geometry authoring done offline and wired to
the material layer (`*.material_config` render templates + textures, model
materials named `mtr_body`/`mtr_face`/`mtr_head`/`mtr_hair`/`mtr_eyes`/
`shadow_caster` with the 2B default bytes). Not installable until an in-game
check (and the ME2 asset-rights gate for release)**
(Diesel `.model` authoring is the remaining step — see [Roadmap](#roadmap)).

Build one equipable **Legendary Armour Skins (LAS) armor-skin add-on** for
PAYDAY 2 — the same product shape as the reference pack `2b.rar`: a selectable
full-body outfit with its own third-person unit and first-person arms, mask and
armor hidden — out of the source assets in `l4d2_miranda_lawson_1.zip` (the
GameMaps.com L4D2 addon that replaces Rochelle with Miranda Lawson).

This replaces the retired "change the heister models directly" pipeline
(`tools/pd2-port/`, deleted 2026-10-18): surgical Diesel model editing produced
crashing or visibly broken packs and could not be verified without the game.
See the [route-change audit](../../docs/audits/2026-10-18-route-change-audit.md)
and the [field note](../../knowledge/games/payday-2/las-armor-skin-outfit.md).

## What this builds

Following the `2b.rar` contract (studied as a spec, not installed):

| Piece | 2B reference | This pack |
| --- | --- | --- |
| Registration | hook on `lib/tweak_data/armorskinstweakdata` → `LegendaryArmours.twobee` | → `LegendaryArmours.miranda` |
| Units | `units/2b/skins/2b/{2b,fps_2b}` | `units/miranda/skins/miranda/{miranda,fps_miranda}` |
| Flags | `hide_mask`, `hide_armor`, `replace_all`, `fps_hide_armor`, `fps_replace_body` | same five |
| Manifest | BeardLib `<table>` with `texture`/`df_nm`/`unit_mat` AddFiles | same, fresh paths |
| Locales | `bm_menu_*_armor_skins`, `bm_askn_*`, `bm_askn_*_desc` | `bm_menu_miranda_*`, `bm_askn_miranda*` |

Target skeleton (PD2 player rig) and object names are recorded in
[`las_target_skeleton.json`](las_target_skeleton.json); the Source→PD2 bone
mapping plan is [`skeleton_map.json`](skeleton_map.json).

## Source

`l4d2_miranda_lawson_1.zip` (tracked at the repo root, user-supplied private
input) contains `miranda_rochelle.vpk` — a VPK v1 addon:

- `models/survivors/survivor_producer.{mdl,vvd,phy,dx80/dx90/sw.vtx}` —
  third-person body (`miranda.smd`, MDL 48, **104 bones**, 9,874 vertices,
  **16,433 triangles** over hair/eyeballs/face/head/body);
- `models/weapons/arms/v_arms_producer_new.*` — first-person arms
  (`miranda_arms.smd`, 53 bones, 1,774 vertices, 2,892 triangles);
- `materials/models/miranda/` — 8 VTF (all DXT5 7.4, 128²–1024², full chains)
  + 6 VMT (hair shares the head textures; eyeballs use the `miranda_eyes` iris).

Provenance: a fan-made L4D2 mod built from Mass Effect 2 rips. **Private
experimental use only — redistribution rights are unresolved.** Never publish
derivatives.

## Pipeline

```sh
python tools/pd2-las/build_las.py              # extract → inventory → textures → scaffold
python tools/pd2-las/build_las.py --stage inventory   # JSON summary on stdout
python tools/pd2-las/build_models.py --templates /tmp/2bsrc/2B\ -\ LAS/assets/units/2b/skins/2b
                                                   # author miranda.model + fps_miranda.model
python -m pytest -q tests/                      # 190 tests, run offline
```

The installable test pack is `build/pd2-las/Miranda_LAS/` (tracked zip copies
at `dist/Miranda_LAS.zip` and `build/pd2-las/Miranda_LAS.zip`);
verify it in game with `docs/pd2-las/in-game-checklist.md` before any public
release.

## Chest variant (`build_busty_variant.py`)

A second, *separate* LAS pack built from the same source with a larger chest:
`Miranda_Busty_LAS.zip` registers `LegendaryArmours.miranda_busty` (its own
unit paths, texture stems and `mod_overrides` folder), so it installs **beside**
`Miranda_LAS.zip` and the stock outfit stays untouched.

```sh
.venv/bin/python tools/pd2-las/build_busty_variant.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
```

The build repeats `build_models.py`'s retarget and Diesel authoring verbatim
and applies `bust_variant.ChestMorph` to the authored third-person groups
between `transfer_group` and `assemble_model`. The first-person arms are built
exactly as the base pack builds them — the morph never touches the viewmodel.

**What the morph does.** Two radial domes (one per breast, apex z≈141.5) whose
falloff `(1 - r2)**2` is zero-slope at the rim, gated forward (nothing behind
the chest wall or on the flat upper chest) and laterally (nothing past |x|=12.2,
so the arms cannot be caught). The forward push scales the *existing* protrusion
measured from the chest wall, so the mass grows instead of the ribcage; a
midline valley term keeps the two breasts separate, which matters because the
source chest is a single convex shell with a ~0.6 cm sternum dip.

Measured with the shipped preset (`cup_gain 0.50`, `round_gain 0.12`,
`lift 0.7`, `spread 1.2`, `valley 0.85`): front reach 19.98 → 28.84 cm
(**+8.85 cm** of depth at the apex), breast-to-sternum valley depth
0.41 → 9.19 cm, 195 of 5,645 body vertices moved, and **zero** vertices moved on
the back, arms, legs or head. `build/pd2-las/busty_variant_report.json` records
the same numbers plus every parameter.

**Safety rails.** The same position-driven pass runs on `g_body`,
`g_body_lod1` and the body block of `s_body` — those blocks hold bit-identical
positions, so the shadow caster and the LOD stay aligned with the visible mesh
(a test asserts it). Normals are rebuilt area-weighted over position-welded
vertices and blended in by morph strength, so the rim of the edit keeps the
shading the base build shipped.

```sh
.venv/bin/python tools/pd2-las/build_busty_variant.py --cup-gain 0.75   # bigger
.venv/bin/python tools/pd2-las/build_busty_variant.py --valley 0.95     # deeper cleavage
```

Previews land in `build/pd2-las/previews/busty_compare_{full,chest}.png`
(base vs variant, same camera). Like the base pack this is offline-verified
only: it still needs `docs/pd2-las/in-game-checklist.md`, and the ME2 asset
rights gate applies to it exactly as it does to `Miranda_LAS.zip`.

## Geometry authoring (build_models.py)

Meshes from the L4D source (`l4d2_miranda_lawson_1.zip`, `VpkArchive.from_zip`)
are re-authored onto the 2B LAS skeleton and written with the verified Diesel
codec (`diesel_model.py`, byte-exact round-trips vs p2mt):

- **Retargeting** (`retarget_maps`): one similarity fit (Umeyama/Procrustes,
  numpy SVD, proper rotation, uniform scale clamped to [0.5, 6.0]) per TARGET
  bone, shared by every source bone that resolves to it (explicit
  `skeleton_map.json` pairs + ancestor walk). Pairs are fit over the source
  joints whose targets lie in that target's subtree of the template skeleton.
  Two coherence rules: everything under a Hand shares the hand's fit (fingers
  ride the palm), and a fit deviating >30° from the global registration
  inherits the nearest ancestor's fit (kills rogue 2-pair frames like the
  diagonal neck). Single-pair targets keep exact joint placement on top of
  their fit. Vertices transfer as `v' = Σ_j w_j · v · X_j` in world space
  (source world is inches, target cm — the fits carry the ≈2.54 scale).
  Faces and UVs are copied verbatim (3-weight renormalized; winding swapped
  `(a,b,c)→(a,c,b)` to match p2mt's GLTF import, signed volume positive like
  the 2B reference).
- **Groups**: `g_body`, `g_head`, `s_body` (TPP, per-material palettes), `g_arms`,
  `s_arms` (FPS); template `c_block` and all shared skeleton/material plumbing
  are kept untouched. LODs share lod0's group sections (same contract as 2B).
- **Previews** land in `build/pd2-las/previews/` — geometry flat-shaded per
  material plus the source-texture reference renders. `uv_check.py` renders
  the authored UVs against the known-good 2B model with an identical
  sampler (the `uvcheck_*` PNGs) — the offline proof that the TEXCOORD0
  convention matches the reference.

Remaining for install: an in-game check — follow
`docs/pd2-las/in-game-checklist.md`. The material
layer is complete
(`2b.material_config` proved the contract: model materials are name-hash
carriers; the `*.material_config` side binds names to `render_template`
combos + `df`/`nm` textures, and `main.xml` registers `df_nm`/`texture`/
`unit_mat` entries). UV orientation of `TEXCOORD0` (`v = 1 − v_src`, the p2mt
GLTF import convention) is pre-verified offline against the 2B reference via
`uv_check.py` — if a future change flips it, the probe PNGs will show it.
Release also waits on the ME2 asset redistribution rights.

Output under `build/pd2-las/` (gitignored):

```
extracted/            VPK contents (safe paths only, CRC-checked)
previews/             PNG texture previews (QA)
textures/             DDS .texture payloads
source_inventory.json bone/mesh/triangle/textures inventory + source hashes
Miranda_LAS/          the pack scaffold:
  main.xml                      BeardLib manifest (registration)
  hooks/miranda_las.lua         LegendaryArmours.miranda entry
  localization/english.txt
  assets/guis/.../miranda.texture          menu icon (face crop, BC3)
  assets/units/.../*.texture               converted materials
  assets/units/.../*.{unit,object,material_config}
  BUILD_INFO.json               per-file SHA-256, registration echo,
                                models_present=false, runtime_verified=false
  WIP_DO_NOT_INSTALL.txt
```

Modules (all tested against the real source zip):

| File | What it does |
| --- | --- |
| `vpk.py` | VPK v1/v2 reader; `entry_offset` is tree-relative; CRC-checked reads; traversal-safe extraction |
| `source_model.py` | MDL **44-49** + VVD v4 + VTX v7 reader (source-sdk-2013 struct layouts; the 44-49 range is documented in `SUPPORTED_MDL_VERSIONS`) → bones, weighted vertices, material triangles |
| `vtf.py` | VTF 7.2–7.4 reader → DDS (`.texture`, mip chain reordered: VTF stores smallest first) and PNG previews |
| `dds_encode.py` | RGBA → DXT5 (naive endpoints, c0 > c1 always) and BGRA8888 DDS writers for icons/previews |
| `las_pack.py` | the 2B-contract scaffold: hook, manifest, locales, unit/object/material_config XMLs, `BUILD_INFO.json` |
| `build_las.py` | CLI: zip → VPK → models/textures → scaffold |
| `gma.py` | Garry's Mod `.gma` reader (GMAD v1–v3; unwraps the LZMA payload Steam sometimes serves; JSON description unpacked; required-content list kept; per-file **and** trailing archive CRC32 checked; `dx90`/`vtx`/`dx80`/`sw` VTX variants; traversal-safe) |
| `inspect_gma.py` | report a subscribed workshop addon: file tree by extension, declared required content, a damaged-archive warning, every model's verts/tris/materials, **bone names** and how much of the rig `skeleton_map.json` already covers. Textures are explicitly *not* its job — it says so and points at `inspect_textures.py` |
| `smd.py` | **SMD read/write** (`parse_smd`, `write_smd`, `ModelData` ↔ SMD with exact quaternion↔Tait-Bryan conversion) + stub `.qc`; CLI exports `.gma`/`.vpk`/`.zip` → per-model `.smd` for Blender |
| `inspect_textures.py` | follow every material a model names to its `.vmt` → `.vtf` inside a `.gma`/`.vpk`/`.zip`/**unpacked addon folder**, report present/missing with real size + mip count, and prove each texture actually **decodes** (optional second opinion from `sourcepp`; no Pillow reports `?` rather than a false ✗). Reads `addoninfo.txt` (GMod and L4D2 spellings) and `addon.json` |

### Reading a subscribed GMod / SFM addon

A workshop addon is a `.gma`, and a `.gma` is a thin wrapper around Source
assets this repo already reads — so an addon can be *measured* rather than
guessed at from its description:

```sh
# after subscribing, the archive is in
#   steamapps/workshop/content/4000/<item id>/*.gma
python tools/pd2-las/inspect_gma.py path/to/<item id>.gma --json /tmp/report.json

# the same questions for an unpacked addon folder (addons/<name>/), a legacy
# zip, or a VPK — including whether every material's texture is really there
python tools/pd2-las/inspect_textures.py path/to/<addon folder>
```

The report gives the file tree grouped by extension, the required-content mounts
the addon declares, a warning if the trailing archive CRC no longer matches
(truncated or hex-edited after packing), then per model: vertex and triangle
counts, material names, and the skeleton split into *already mapped* /
*Source-only* / *unknown* against `skeleton_map.json`. That is what decides
whether an outside port is a cheap reference (a `ValveBiped` rig half-covered by
the existing map) or new work. Nothing is extracted or rendered: the addon is
someone else's licensed content, so private inspection only.

Three GMod shapes have to be told apart, and the readers now cover all three:

| on disk | what it is | reader |
| --- | --- | --- |
| `addons/<name>/…` | an **unpacked** addon (workshop items someone extracted, and the layout `gmad` packs from) | `inspect_textures.py <folder>` |
| `<id>.gma` in `steamapps/workshop/content/4000/<id>/` | the packed addon; LZMA-wrapped when Steam compressed the download | `inspect_gma.py`, and `inspect_textures.py` too |
| `addons/*.zip` / `.vpk` | the pre-2013 download format, usually one wrapper folder deep | `inspect_textures.py` |

### The rest of the tool landscape

Surveyed 2026-11-05 for "what else deals with GMod mods", with the verdict that
matters here — can it run in this repo, and does it add something the existing
readers do not:

| tool | what it covers | licence / platform | verdict for this repo |
| --- | --- | --- | --- |
| [`sourcepp`](https://pypi.org/project/sourcepp/) (`vpkpp`, `vtfpp`, `bsppp`, `kvpp`) | **GMA v1-3, VPK v0/v1/v2/v54, BSP, VTF 7.0-7.6**; read *and* write for the pack formats. **No `mdlpp` in the Python wheel** — `mdlpp` exists as a C++ header (`include/mdlpp/`), the wheel binds only `bsppp gamepp kvpp sourcepp steampp toolpp vcryptpp vpkpp vtfpp`, so MDL parsing is not reachable from Python | MIT, C++20 + nanobind wheels | **the one worth having.** Installed and verified (2026-11-05): decodes a real DXT5 VTF from the tracked L4D2 pack and agrees with `vtf.py` pixel-for-pixel (max abs diff 1 = DXT rounding), and its GMA reader agrees with `gma.py` on the file list and CRCs — **except on required content**: `GMA::open` reads that list as one string, so any addon that actually declares a mount ("half-life 2") comes back with an empty name and a mangled entry path (`ame`), while `gma.py` loops to the empty terminator. Use it as a second opinion, not as the oracle. Optional dev-only cross-check; not a project dependency |
| [`gma`](https://github.com/diogo464/gma) (Rust crate) | read **and write** `.gma`, **including the LZMA-compressed workshop form** the Rust author documents as "Garry's Mod can't read compressed gma files but some, downloaded directly from the Steam workshop, are lzma compressed" | MIT | the only other implementation found that handles the compressed download; not usable from Python here, and `gma.py` covers the read half |
| [Crowbar](https://github.com/ZeqMacaw/Crowbar) | MDL → SMD/QC/QCI/VTA/VRD and back via `studiomdl`; unpacks VPK/GMA | free, closed source, **Windows only** | **not needed for measurement**, and it cannot run here. Still the standard answer if a human wants SMD/QC in Blender |
| [Blender Source Tools](https://github.com/Artfunkel/BlenderSourceTools) | SMD/DMX/QC import + export | open source, Blender 4.x | no MDL/VTF support by design, and it needs Blender, which this sandbox lacks |
| [SourceIO](https://github.com/REDxEYE/SourceIO) | **`.mdl` + `.vmt` + `.vtf` + `.bsp` direct import**, "Garry's Mod: full support" | MIT, Blender 4.0+ | the tool that skips Crowbar entirely — *if* a Blender existed here. Worth naming in a hand-off |
| GMad (`gmad.exe`) | create/extract GMA, publish | Valve, bundled with GMod | `gma.py` replaces the extract half on Linux; `vpkpp` can also **write** GMA if a repack is ever needed |
| [VPKEdit](https://github.com/craftablescience/VPKEdit) | GUI/CLI over `vpkpp`: VPK, GMA, BSP, VTF, ZIP | MIT | fine for humans, redundant with the readers above |
| [`srctools`](https://github.com/TeamSpen210/srctools) | VPK/VTF/BSP/VMF/DMX read+write, MDL partial, mount chains, `packlist` dependency resolution | **MIT** (the repo `LICENSE` excludes only libsquish; PyPI classifier says `License :: OSI Approved :: MIT License`) — an earlier revision of this table said GPL-3.0 and drew the wrong conclusion from it | usable, not vendored: nothing here needs `packlist` yet. Its idea (walk a map's or model's dependencies before declaring an addon complete) is the one thing worth re-implementing |
| [MareTF](https://github.com/craftablescience/MareTF) / `vtex2` / `vtf2png` | VTF ↔ image converters, every VTF variant | MIT / libpng | redundant: `vtf.py` converts, and is bytes-checked against `vtfpp` |

### Round two: the rest of the field (same day)

| tool | what it is | verdict |
| --- | --- | --- |
| **SMD, written here** | `smd.py` — SMD is plain text, so the hand-off to Blender needs no tool at all | **closed the gap.** `python tools/pd2-las/smd.py addon.gma --out dir --qc` writes one `.smd` per model plus a stub QC. Verified against the tracked pack: 104 bones, 16,433 triangles, 6 materials, and every bind-pose rotation survives the text round trip to 1e-7 |
| [`bpy`](https://pypi.org/project/bpy/) | Blender 4.x/5.x as a `pip` wheel (`import bpy`, headless) | **tried, does not run here.** Installs, then dies on `libXrender.so.1` / `libXi` / `libGL`; `apt` can only reach a blocked mirror, so the libs cannot be added. It *would* give a real headless Blender on a normal Linux box |
| [gmpublisher](https://github.com/WilliamVenner/gmpublisher) | Rust+Tauri GUI **and CLI**: extract/publish GMA, bulk download, addon size treemap, no `gmad.exe` needed | the publishing half (nothing here publishes to GMod); its Linux build is Linux-only-Windows-CLI and history is mixed. `gma.py` covers reading |
| [Noesis](https://www.richwhitehouse.com/noesis/) | Windows GUI/CLI converter with **Source `.mdl` + VPK import** and a Python plugin API | Windows-only, so it belongs to the same bucket as Crowbar: a human-side tool, not something this repo can call |
| Linux `studiomdl` | Valve's compiler is Windows-only; Crowbar/`studiomdl` under Wine is the usual workaround | not worth it: the compile step is only needed to make a *Source* model, and nothing here builds one |

Two conclusions. **Acquiring** an addon needs nothing new: `steamcmd +login
anonymous +workshop_download_item 4000 <id> +quit` lands the `.gma` in
`steamapps/workshop/content/4000/<id>/` for a free app like GMod, and that is the
only reliable route for an item whose workshop page has been delisted. **The
writing gap is closed** by `smd.py` (pure Python, no Blender needed): rigged
geometry leaves this repo as SMD, which Crowbar, Blender Source Tools and SourceIO
all import, and which the Windows side can turn into an FBX/GLB for the existing
GLB retarget if a `.model` route is preferred later. What is still missing is only
*compiling* back to Source (studiosmdl, Windows) — irrelevant here, because the
target engine is Diesel, not Source. The retarget path is unchanged: Source mesh →
`ModelData` → `transfer_group` → Diesel.

## Roadmap

- [x] VPK extraction (safe, CRC-checked)
- [x] Source model parse (body + FP arms: bones, weights, triangles, materials)
- [x] VTF → DDS conversion (mip order verified visually) + previews
- [x] LAS registration scaffold matching the 2B contract (offline-tested)
- [x] Skeleton mapping plan (`skeleton_map.json`)
- [ ] **Diesel `.model` authoring** — skin `miranda.smd` onto the PD2 player
      skeleton (`skeleton_map.json`), emit `g_body`/`g_head`/`s_body` drawables,
      culling objects and `SkinBones` with 0-based local indices; same for
      `fps_miranda` from `miranda_arms.smd`. This is the last hard step; the
      retired pipeline's format notes died with it — re-derive from
      `diesel-modding/payday2-model-tool` research notes and the 2B models.
- [ ] Material pass: Diesel templates for eyes (Source EyeRefract), phong hair,
      alpha-masked lashes
- [ ] In-game verification ladder: menu preview → offline heist → animation,
      weapon alignment, mask/armor hiding, outfit switching
- [ ] Release gate (blocked): asset redistribution permissions

## Notes

- Keep `2b.rar` (contract reference) and `l4d2_miranda_lawson_1.zip` (source)
  at the repo root; tests read the source zip directly.
- The 2B pack is a **spec example, not a runtime oracle**: its `ss.model` is
  unregistered, its `cooked_physics` files are empty and its manifest `Hooks`
  casing differs from its `hooks/` directory. Don't copy those defects.
- Runtime contract facts (LAS 4.x mapping to `las_<id>`, BeardLib `unit_mat`
  shortcuts) are recorded in the
  [field note](../../knowledge/games/payday-2/las-armor-skin-outfit.md).
