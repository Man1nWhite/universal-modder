# Christie — renders from every stage of the pipeline (2026-11-14)

Every file here is named with the **stage / source type** that produced it, then
the material (if any) and the view. All renders are orthographic software renders
of the actual bytes — they document geometry, materials, UVs and masks, not beauty
shots. The game remains the only truth for look (`runtime_verified` is `false`).

## The actual Christie pipeline (where each render comes from)

```
references/Christie.zip                    DOA5 christie_c2: .mdl/.vvd/.dx90.vtx (+.vmt/.vtf)
  │                                        sha256 605c352a…
  ▼  parse (tools/pd2-las/source_model.py, tested on this exact triple)
  00 · christie_mdl-vvd-vtx_*.png          bind-pose triangles per material
  ▼  retarget + author IN MEMORY (tools/pd2-las/{build_models,segment_fit,diesel_model}.py;
     Umeyama fits vs the 2B templates; 12° idle rest; elbow de-spike/trim; cuff taper;
     sleeve stitch + fill; seam-normal unification) — NO file stage exists here
  │                                        verified by the numbers in BUILD_INFO.json
  │                                        (seg max/rms cm, cuff/joint offsets) — see
  │                                        docs/audits/2026-11-14-christie-from-scratch.md
  ▼  Diesel codec writes .model; las_outfit_pack.py + las_pack.zip_pack
  02 · christie_model-bridge*.png          the .model INSIDE the shipped .zip (bridge bytes)
  ▼  packaged with hooks/BeardLib/main.xml/localization → dist/Christie_LAS.zip  (the mod)
```

Stage **01 (`christie_smd_*`)** is the repo's **text hand-off format** (Valve SMD +
`.qc` stub) used by the Blender route. The Christie LAS build does **not** pass
through SMD — the render exists to prove the exporter round-trips (17,287 triangles
out, 17,287 back, 4 meshes, 0 weight-link warnings) and to give anyone redoing the
port via Blender a known-good reference. `build/christie-render/christie_kept.smd`
and `christie.qc` regenerate on every driver run but stay untracked (the source is
already tracked as `references/Christie.zip`).

**No `.dae` or `.fbx` stage exists anywhere in this route** — nothing in
`tools/pd2-las` reads or writes them (`.dae` appears only as *input* to
`tools/build_joy_head_mods.py`, the ME2 head-pack product); `.fbx` appears nowhere
in the repository. If a Blender round-trip is ever wanted, stage 01 (SMD) is the
doorway; it is the one text format this repo can emit losslessly for weights.

## Naming

`christie[_slim]_<source-type>[_<material|set>]_<view>.png`

| token | meaning / provenance |
|---|---|
| `mdl-vvd-vtx_full` | every parsed submesh of the source triple, 22 meshes / 36,920 tris, head+hair+face+glasses included |
| `mdl-vvd-vtx_kept` | only the four kept materials: `cri_body_base`, `cri_02_01_base`, `cri_02_02_base`, `cri_02_05_base` — 17,287 tris (dry variants only; `*_wet_*` and `cri_02_03/04_base` are **dropped**) |
| `mdl-vvd-vtx_dropped` | everything dropped — what the body-only pack must not contain |
| `smd_kept` | the kept set as Valve SMD, re-parsed and rendered (see above) |
| `model-bridge_<mat>` | the tracked deliverable: `dist/Christie_LAS.zip` (sha256 `1ec1c95a…`), per-material flat renders, `shadow_caster` included |
| `model-bridge_body` | same pack, all materials combined, per-material flat colors (not textures) |
| `model-bridge_body-textured` | same pack, lit with correct UV sampling of the pack's own `.texture` files (DXT5 top mip), back-face culling — closest possible preview without the game |
| `model-bridge-fps_*` | the first-person viewmodel unit inside the same zip; `aux` is an 8-vert ~430 cm/unit proxy whose material hash (`8db63936938575bf`) is absent from the model hashlist — excluded from the combined `body` render (it spans the whole viewmodel space) and rendered separately |
| `model-scratchbase_*` | the from-scratch (pre-bridge) build, sha256 `b65fb27e…` — **provenance only, not the tracked pack** |
| `slim_model-bridge*` | the tracked Slim pack, sha256 `ebe44af7…` (hands cut at the wrist + glove-adapter hook) |

Views: `front` / `side` / `iso` (orbit = orthographic along Y/X/iso-diagonal, Z-up,
bounding-box framed, 720 px). Textured set: `front` / `side` / `threequarter`.

## Verifying what you see

The tracked bytes verify end-to-end offline per
`docs/audits/2026-11-14-christie-from-scratch.md` (payload hashes, DXT5 mip pyramids,
flags, model walk, degenerate-triangle = 0). The SMD/MDL figures above are printed by
the driver on every run. Regenerate everything with:

```sh
bash tools/pd2-las/recover_env.sh
.venv/bin/python tools/pd2-las/build_christie_las.py --out build/christie-scratch/out --dist build/christie-scratch/dist --variant base   # optional, for *_scratchbase_*
.venv/bin/python build/christie-render/render_all.py   # writes into this directory
```

(`build/` is gitignored; only the PNGs and this README are tracked.)

## Caveats

- The retarget stage has no file format; its outputs are the `.model` renders (02) —
  judge fit quality from BUILD_INFO.json numbers, not from these pictures.
- `model-bridge*` and `slim_model-bridge*` render the **bind pose**; the idle rest
  (12°) is stored in the model — the pack poses in-engine.
- FPS renders show the viewmodel frame, not the world frame.
- Textures are sampled mip-0 only; in-flight mip behaviour is not shown.
