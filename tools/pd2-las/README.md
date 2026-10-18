# pd2-las — Miranda Lawson as a PAYDAY 2 Legendary Armour Skins outfit

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
python -m pytest -q tests/                      # 188 tests, run offline
```

## Geometry authoring (build_models.py)

Meshes from the L4D source (`l4d2_miranda_lawson_1.zip`, `VpkArchive.from_zip`)
are re-authored onto the 2B LAS skeleton and written with the verified Diesel
codec (`diesel_model.py`, byte-exact round-trips vs p2mt):

- **Retargeting** (`retarget_maps`): one similarity fit (Umeyama/Procrustes,
  numpy SVD, proper rotation, uniform scale clamped to [0.5, 6.0]) per TARGET
  bone, shared by every source bone that resolves to it (explicit
  `skeleton_map.json` pairs + ancestor walk). Pairs are fit over the source
  joints whose targets lie in that target's subtree of the template skeleton;
  single-pair targets use the global registration with exact joint placement.
  Vertices transfer as `v' = Σ_j w_j · v · X_j` in world space (source world is
  inches, target cm — the fits carry the ≈2.54 scale). Faces and UVs are
  copied verbatim (3-weight renormalized; winding swapped `(a,b,c)→(a,c,b)`
  to match p2mt's GLTF import, signed volume positive like the 2B reference).
- **Groups**: `g_body`, `g_head`, `s_body` (TPP, per-material palettes), `g_arms`,
  `s_arms` (FPS); template `c_block` and all shared skeleton/material plumbing
  are kept untouched. LODs share lod0's group sections (same contract as 2B).
- **Previews** land in `build/pd2-las/previews/` — geometry flat-shaded per
  material plus the source-texture reference renders.

Remaining for install: an in-game check. The material layer is complete
(`2b.material_config` proved the contract: model materials are name-hash
carriers; the `*.material_config` side binds names to `render_template`
combos + `df`/`nm` textures, and `main.xml` registers `df_nm`/`texture`/
`unit_mat` entries). UV orientation of `TEXCOORD0` is `v = 1 − v_src` per
the p2mt GLTF import convention — confirm in game and flip if the textures
read upside-down. Release also waits on the ME2 asset redistribution rights.

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
| `source_model.py` | MDL 48/49 + VVD v4 + VTX v7 reader (source-sdk-2013 struct layouts) → bones, weighted vertices, material triangles |
| `vtf.py` | VTF 7.2–7.4 reader → DDS (`.texture`, mip chain reordered: VTF stores smallest first) and PNG previews |
| `dds_encode.py` | RGBA → DXT5 (naive endpoints, c0 > c1 always) and BGRA8888 DDS writers for icons/previews |
| `las_pack.py` | the 2B-contract scaffold: hook, manifest, locales, unit/object/material_config XMLs, `BUILD_INFO.json` |
| `build_las.py` | CLI: zip → VPK → models/textures → scaffold |

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
