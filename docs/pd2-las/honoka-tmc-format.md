# Honoka "Secret Report" TMC — decode findings, rigged export, LAS build (2026-11-14/15)

**Status: decode complete; an LAS build runs end-to-end offline (2026-11-15).** `runtime_verified` stays `false`
in `BUILD_INFO.json`. Later on 2026-11-15 the tracked pack was in the outfit menu in game
(user report; captures in `docs/renders/in-game-2026-11-15/`); read the rest of this page as the pre-game record.
The build is section
"2026-11-15 (build): the LAS pack builds" near the end; the sections before it
are the decode record and are kept as written.

## Source

| File | sha256 |
|---|---|
| `references/Outfit for Honoka-109-1-1-1628020933.zip` | `86fc084c7310e9cd78bfb39cd4bb15486a15295f1c233c754492e1c4f572e154` |
| `Honoka_DOAXVV_Secret_Report.TMC` (in the zip) | `12d4f370ee47a183bfc3ba4792b7fda47b4176b13444a87745c89089cefa129b` |
| `references/Honoka/Honoka_DOAXVV_Secret_Report_ALL_EXPORT.OBJ` (3rd-party dump) | `e6e2529018eff64d84721f1468538abc9750564265ca7ea01b2e0bdebe97f4bd` |
| `references/Honoka/Honoka_DOAXVV_Secret_Report.rigged.glb` (this repo's export, regenerated 2026-11-15 with palette-remapped joints and normal-aligned winding) | `ef23c55e738bf857b2b04ace890c4dffa3413f7d1e831bef7dd438e05940c326` |

## What the file is

A Dead or Alive Xtreme Venus Vacation (DOAXVV) costume TMC for the custom
character Honoka. Sections (`tmc_dump.py`): `MdlGeo` (7 ObjGeo) → `VtxLay`
(11 buffers) + `IdxLay` (8 strips) + `MtrCol` (19) + `MdlInfo` (7) +
`HieLay` (171 nodes, hierarchy) + `NodeLay` (171 node records) + `GlblMtx`
(171 world bind matrices, offset table at `+HSize`) + `BnOfsMtx` (171) +
`MCAPACK` (37 material records) + `TTDM`/`RENPACK`/`ACSCLS`/`cpf`
(unparsed).

Tools: `tools/pd2-las/tmc.py` (reader), `tools/pd2-las/tmc_export.py`
(exporter). Both are repo code; neither reads the OBJ.

## Vertex format (little-endian)

| stride | buffers (use) | layout |
|---|---|---|
| 0x40 (64) | 2, 5, 7 (cap2, headdress2, body) | pos f3 @0 · nrm f3 @12 · **weights u8×4 @24 (sum 255)** · **bone indices u8×4 @28** · tangent f4 @32 · uv1 half2 @48 (stored ×4) |
| 0x3c (60) | 0, 10 (feather, sweat_chest) | same, uv1 duplicated ×3 |
| 0x24 (36) | 9 (body decl1) | pos @0 · nrm @12 · weights @24 · indices @28 · uv1 half2 @32 (no tangent) |
| 0x30 (48) | 1, 4 (WGT_cap, WGT_headdress placeholders) | 1-vertex dummy decls, skipped |

- Positions are **metres**; ×100 reproduces the OBJ `v` coordinates for
  27,970/27,970 body vertices (the OBJ is a different vertex order — a
  permutation was built and used only for cross-checks).
- Weights: normalized by 255 on export. 62 all-zero rows exist (60 in the
  feather group + 0 elsewhere… see "Open items"); those are placeholder rows,
  rewritten to joint 0 / weight 1.0 and tagged `__unweighted_placeholder`.
- Normals/tangents are unit length; float `1.0` at @44 is a handedness
  constant (tangent.w in the export).
- UV: half-precision float2 at @48 (or @32 for stride 0x24); verified
  against OBJ `vt` for the sweat_chest (exact, e.g. vert0 = (0.85546875,
  0.00905609130859375)). Negative UVs occur on some groups and match the
  source data; not an artifact of the reader.

## Index buffers: triangle strips, alternating parity

> **Superseded in part 2026-11-15 (later).** The absolute-parity rule below
> is not a single rule for the whole file; the decoder now post-aligns every
> triangle to its stored vertex normals. See the section
> "2026-11-15 (later): strip winding is not one rule" at the end of this
> document.

`IdxLay` stores one **triangle strip** per declaration (`IDXcount` elements,
uint16, no 0xFFFF restart). Decoding rule (validated two ways):

1. window `(s[i], s[i+1], s[i+2])`, winding alternates with absolute parity
   of `i`; windows repeating any vertex index (zero-area stitching) are
   dropped.
2. With that rule, face normals agree with stored vertex normals on
   **100%** of sweat_chest triangles and **~94%** of body triangles; the
   natural-order alternative gets 48%/59%. The remaining ~6% disagrees on
   inward/trim faces; vertex normals are stored per-vertex, so shading is
   unaffected.

The included OBJ dump is **not usable for decoding**: it emits every window
as a triangle in natural order (odd windows wound backwards, zero-area
faces included), and its per-group material split drops a mesh-dependent
number of windows (cap2 −6, headdress2 −10, body −5,014) with no consistent
rule. Its 109,810 face count includes 48,886 zero-area faces. It was used
only for position/UV cross-checks and group naming.

## Skeleton (171 nodes)

Names (`NodeLay` records): `MOT00_Hips…MOT20_RightToe` (21), helper bones
`OPT_acs_ground`, `OPT_acs_skirt0..74` (75), `OPT_AS_*` (twist/elbow/knee/
hip/wrist), `OPT_Breast_*` (12), `OPT_Hand_*_*` (finger bones, 34), mesh
attachment nodes `WGT_acs_skirt`, `WGT_body_feather`, `WGT_cap`, `WGT_cap2`,
`WGT_headdress`, `WGT_headdress2`, `WGT_new_aya_body`, `WGT_sweat_chest`
(8).

`HieLay` records: 16-float bind (row-major rows R, translation row at
+0x30, w=1) + i32 parent (−1 = root) + u32 child count + u32 depth + u32
pad + children u32s. The tree parses fully: 170/170 links consistent
(parent⇔child), single root (MOT00_Hips), depths match, anatomy textbook
(Hips→UpLeg→Leg→Foot→Toe, Waist→Chest→Neck→Head, shoulders→hands→fingers,
breast chains, skirt bones under `WGT_acs_skirt`).

`GlblMtx` = 171 world bind matrices (offset table at `+HSize`, matrices at
`section_base + offset`, stride 64). **Validated**: composing HieLay locals
in tree order reproduces GlblMtx with max abs error **4.06e-08**, both for
column-major and for the transposed reading. Locals are orthonormal
(det ≈ +1) everywhere.

## Decoded meshes

| glTF mesh | buffer | verts | tris | notes |
|---|---|---|---|---|
| `TMC_WGT_body_feather__unweighted_placeholder` | 0 | 1,121 | 1,402 | 60 zero-weight rows; long sash slivers; **excluded candidates — do not ship without owner review** |
| `TMC_WGT_cap2` | 2 | 4,165 | 6,220 | the jacket/blazer |
| `TMC_WGT_headdress2` | 5 | 4,963 | 7,560 | skirt + jacket trim layer |
| `TMC_WGT_new_aya_body_decl0` | 7 | 27,970 | 38,740 | main body (headless; neck stump) incl. hands |
| `TMC_WGT_new_aya_body_decl1` | 9 | 280 | 300 | debug-like mesh: 28 weight refs to *every* bone 0–39, 1/4 weight each; unknown purpose |
| `TMC_WGT_sweat_chest` | 10 | 51 | 64 | chest emblem |

Placeholder decls `WGT_cap`/`WGT_headdress` (1-vertex dummies) are skipped
by the reader. Total decoded: 38,550 verts / 54,286 tris.

## Export

`references/Honoka/Honoka_DOAXVV_Secret_Report.rigged.glb` (~2.9 MB,
glTF 2.0 binary; 171-joint skin, identity scene = bind pose). Validation
(`build/honoka-analysis/check_glb.py`, rebuilds everything from the file):
container/views in bounds; scene lists only `[Hips_root, mesh nodes]`;
171/171 joints reachable; `W·IBM ≈ I` ≤ 5e-06 per joint; glTF world
matrices == TMC GlblMtx ≤ 5e-06; all weight rows sum to 1.0; indices in
range; triangle totals match the decoder; positions point-in-time render
(`build/honoka-analysis/tmc_render_front.png`, `tmc_render_side.png`)
matches the OBJ silhouette (headless body, jacket, skirt, ribbons, hands,
heels).

## Open items

- "LOS mod" reading: **assumes LAS** (Legendary Armour Skin, the Christie /
  2B template in `tools/pd2-las/`). Unconfirmed.
- Body has **no head geometry** (neck stump) ✓ LAS-compatible; hands are
  cut at the wrist by the LAS build (see the 2026-11-15 build section).
- Whether to keep cap2/headdress2/feather/sweat_chest (jacket, skirt,
  ribbons, emblem) or body-only: the build keeps cap2/headdress2, excludes
  feather and sweat_chest (owner decision pending).
- `*T_body_feather` decodes to long sash-like slivers; the OBJ exporter
  dropped this mesh entirely. Purpose unverified — excluded from the build
  until reviewed.
- `MCAPACK` (37 material records): not decoded; string-free records (word6
  holds small counts, word7 = 0). Texture mapping to `references/Honoka/
  L_*.dds` rests on render evidence, not on the file — see the build
  section.
- LAS-side bone mapping: done — `tools/pd2-las/tmc_skeleton_map.json`
  (MOT* → PD2 Diesel names; unmapped helpers merge into their nearest
  mapped ancestor).
- Nothing in-game checked; `runtime_verified` = false everywhere it
  appears.

## 2026-11-15: skin-palette indirection in `NodeLay` (corrects the skinning note above)

**The vertex buffers' bone indices are not node indices.** Each
mesh-bearing `WGT_*` node carries an inline per-mesh skin palette; the
`u8[4]` in the vertex layout indexes into it. Discovered when every
region check of the raw slots landed on anatomically impossible bones
(hands weighted 100% to leg/skirt bones, ~55% of the body dominated by
`MOT15_Neck`).

Record layout (verified byte-by-byte on this file):

```
WGT_* NodeObj record (+0x40 name, length = record size)
  +0x60/0x70 : u32 offset (head offset table) -> objidx (u32)
  objidx + 4 : u32 palette_count (0 => no palette)
  objidx + 8 : u32 self node index
  objidx + 12: 4x4 float matrix (64 bytes; a near-identity constant whose
               exact role is unverified — not parsed, not needed)
  objidx + 76: one trailing float (0x3f800000 = 1.0; role unverified)
  objidx + 80: palette_count x u32 global node indices
```

Decoded palettes (all entries valid, all counts distinct):

| MdlGeo objidx | mesh | palette_count |
|---|---|---|
| 0 | `WGT_body_feather` | 0 (none — slots are coherent as raw node indices) |
| 2 | `WGT_cap2` (jacket) | 41 |
| 4 | `WGT_headdress2` (skirt/trim) | 43 |
| 5 | `WGT_new_aya_body` (body decl0 + decl1 share it) | 85 |
| 6 | `WGT_sweat_chest` | 9 |

With palette remapping, skinning is anatomically coherent everywhere
(breast verts bind to `OPT_Breast_*_tip` within centimetres; hand verts to
`OPT_Hand_*`/`MOT*Hand`; torso to `MOT02_Chest`; feet to feet). `tools/
pd2-las/tmc.py` now parses the palettes (`mesh_palettes`, attached per
`MeshPayload.palette`), and `tmc_export.py` remaps `JOINTS_0` through them:
the tracked `references/Honoka/Honoka_DOAXVV_Secret_Report.rigged.glb` was
regenerated (sha256 `ef23c55e…`; the previous `b5f51282…` bound vertices to
raw slot indices and is superseded). The feather mesh has no palette and
keeps raw node indices; it remains excluded from any build.

Consequences for downstream work:

- Any bone-frequency histogram of raw slots is meaningless; always remap
  through `payload.palette` first.
- The per-mesh palettes also reveal each mesh's actual deform set (85 bones
  for the body, incl. twist/elbow/breast/wrist helpers and no `MOT05_
  LeftHand` at all — left-hand geometry binds to `OPT_Hand_Left_Root` +
  finger bones), which is the correct input for the LAS retarget palette.
- The `MdlInfo` records remain undecoded; no palette data hides in them
  (the palettes live inline in the `WGT_*` `NodeLay` records, as above).

Not re-verified end-to-end: nothing here has been run in-game;
`runtime_verified` stays `false`.

## 2026-11-15 (later): strip winding is not one rule; decoder now force-aligns to vertex normals

Follow-up to the palette fix. The alternating-parity strip decode gave
face·vertex-normal agreement of only 0.69 (cap2), 0.49 (headdress2), 0.19
(feather), 0.94 (body). Splitting at runs of dropped zero-area windows
(run-relative parity) fixes all of those to 0.97–1.00 but breaks
sweat_chest (0.48; absolute parity was exactly 1.00 there) — sweat_chest
is the only mesh whose gaps never reset the phase, and no single parity
rule covers all six declarations. `tmc.py` therefore post-processes the
decoded triangles with `_align_winding_to_normals`: any triangle whose
face normal disagrees with the summed (unit-length) vertex normals is
swapped (indices 1<->2). Agreement is now exactly 1.0000 on every mesh.
Measured per buffer (natural/swapped, absolute-parity rule): decl0 0.9385,
cap2 0.6945, headdress2 0.4948, feather 0.1954 — see
`docs/pd2-las/honoka-tmc-format.md` history and
`tools/pd2-las/tmc.py::_align_winding_to_normals`.

Consequences: all consumers of `tmc.load_meshes()` (the renderer, the
glTF exporter, the LAS build) now see normal-consistent winding. The
stripped-parity code (`_strip_to_tris`) is still what generates the
triangle list; the alignment is a deterministic post-fix, not a new
heuristic. `runtime_verified` stays `false`.

## 2026-11-15 (build): the LAS pack builds

`tools/pd2-las/build_honoka_las.py` turns the TMC into a Legendary Armour
Skins pack (third invocation of the `build_models.py` library; TMC source
instead of Source, Miranda's pipeline reused for retarget/assembly). Output
of one run (all git-ignored, nothing in `dist/`):

```
build/honoka-las/honoka_las.model            6,155,357 B — third-person model
build/honoka-las/Honoka_LAS/                 installable pack folder
build/honoka-las/Honoka_LAS.zip              5,740,871 B; .sha256 next to it
build/honoka-las/honoka_las_report.json      build report (runtime_verified: false)
build/honoka-las/Honoka_LAS/previews/honoka_4views.png   own render, 4 views
```

### Decisions and evidence

- **Scope**: `WGT_new_aya_body_decl0` (body, 27,970 v / 38,740 t), `WGT_cap2`
  (suit jacket, 4,165 v / 6,220 t), `WGT_headdress2` (skirt/trim, 4,963 v /
  7,560 t). Excluded: decl1 (debug-like 28-bone uniform-weight slab, 280 v),
  sweat_chest (chest emblem, 51 v — owner decision pending), body_feather
  (sash slivers — excluded), placeholders. After the wrist cut: **36,464 /
  6,220 / 7,560 triangles**.
- **No head** — the body has none; `g_head`/`g_head_lod1` drawables are
  dropped from the model and the registration flips `replace_all` →
  `replace_body` (`BODY_ONLY`). First-person: no `fps_unit` is registered —
  an LAS entry without one behaves better than one pointing at a missing
  file; LAS keeps the vanilla FPS arms. The pack is **third-person complete**; the first-person
  view keeps the vanilla arms.
- **No hands — wrist cut**: both arms are cut at the PD2 wrist joints
  (`build_models.ARM_JOINTS`: LeftHand/RightHand, used by the Miranda
  sleeve bridge). First attempt cut with a half-space plane (centred on the
  wrist, normal along the forearm axis) and **swallowed the lower legs**:
  in the PD2 bind pose the forearm axis points steeply down-forward, so the
  plane contains the shins (feet project ~19 cm "beyond" the wrist). The
  fix is cylindrical: keep a vertex unless it is beyond the wrist
  (`t > 0.5 cm`) **and** within 28 cm of the forearm axis — only
  hand/fingers qualify (the fingertip bones' bind positions are exactly
  there); the leg geometry is ~120 cm off-axis. Result: 2,276 body tris /
  1,358 verts dropped; cap2/headdress2 drop 0.
- **The legs are intentionally coarse** below the skirt hem (~2,900 verts
  under y_s < −60; long low-poly triangles). The earlier "tapering ribbons"
  seen in probe renders were an artefact of the broken wrist cut, not the
  source data; with the fix the legs render as a normal (low-poly) column
  with heels. Barely any vertices exist below mid-shin — the mesh simply
  ends at the shoes' outline.
- **Basis change**: TMC (Y-up, cm, +y horizontal forward) → Diesel Z-up cm
  as `R_x(+90°)` (det = +1): `x→x`, `y→z`, `z→−y`. `GlblMtx` world bind
  matrices (metres, column-convention 4×4) map as `M·W·Mᵀ` with translation
  ×100; `build_honoka_las.glbl_to_diesel`. Positions/normals rotated the
  same way; det +1 everywhere. The built model stands z-up with
  feet at z ≈ 48 cm and neck stump at ≈ 167 cm.
- **Winding**: `tmc.load_meshes()` emits normal-aligned outward CCW
  triangles, so the build passes `transfer_group(..., swap_winding=False)`
  (the Source-engine default `True` would invert everything). Face vs
  vertex-normal agreement 99.7% after transfer (skinned-joint blending may
  shade slightly off — that is fine). `orientation_breaks` reports 102 same-
  direction shared edges (0.2% of ~48k, body + 6 panels in cap2/headdress2).
  The flagged faces are predominantly sub-0.01 cm² sliver stitch triangles
  along UV seams plus a handful of quad panels split inconsistently in the
  source. They were left as decoded: vertex normals agree with winding
  1.0000 mesh-wide, and flipping them would create the very holes the
  metric exists to find. Watch in-game for pin-hole culls there.
- **Retarget**: `skeleton_map.json` → `tmc_skeleton_map.json` (MOT* → PD2
  names; breast/skirt/twist/helper bones unmapped and merged into their
  nearest mapped ancestor via the ancestor walk — e.g. bust → Spine2,
  skirt helpers → Hips, i.e. a rigid skirt at runtime; LAS has no skirt
  bones). 171/171 source bones get a fit. `retarget_maps(...,
  src_worlds=...)` accepts the precomputed Diesel-frame world binds.
- **Textures**: the 27 `references/Honoka/L_*.dds` are ordinary DXT5 DDS
  (Pillow-readable). Shipped `.texture` payloads in PD2 packs are plain
  DXT5 DDS too (verified in `dist/Miranda_LAS.zip` — magic `DDS `, fourcc
  `DXT5`), so they can be opened/re-encoded one line at a time.
  Mapping used (provisional, swap the constants in the driver to change):

  | role | diffuse | normal |
  |---|---|---|
  | body   | `L_3.dds` | `L_4.dds` |
  | jacket | `L_7.dds` | `L_8.dds` |
  | skirt  | `L_9.dds` | `L_11.dds` |

  All six re-encoded as BC3 with **full mip chains** (`bc3_dds_from_levels`;
  colour averaged in linear light, alpha as stored values, down to 1×1).
  Mip convention mirrors `build_las.py`. `L_10` (light grey-blue tie/panels)
  and `L_12` rejected for cap2/headdress2. The skirt assignment is
  unsettled (`L_17`–`L_26` are lingerie/bra pieces; owner to confirm).
- **L_3 alpha is not a cutout**. It is a per-texel grayscale detail map
  (mean ≈ 85; feet/hands/body creases brighter — reads as baked
  AO/self-shadowing, not a silhouette). The earlier "silhouette mask" note
  was a misread of a 90-px thumbnail. The body ships with a flat matte
  gloss alpha (20) like the garments; no alpha-test is used anywhere.
- **Normal maps**: `L_4`/`L_8` are re-encoded to PD2's layout (X in alpha,
  Y+ in green, Y inverted for the DirectX-style sources, R 255 / B 0 —
  `pd2-port/dds.pd2_normal_channels` convention). If the Green channel of
  the sources turns out to be Y+, lighting will look inverted — that is the
  single most likely visual bug, and it is a one-line change in
  `build_textures()`.
- **Registration**: `LegendaryArmours.honoka`, BODY_ONLY flags, own TPP
  unit `units/honoka/skins/honoka/honoka`, no FPS unit, `honoka_las.lua` +
  `honoka_glove_adapter.lua` (restores `default_glove_id = "heist_default"`,
  re-enables the glove adapter table, un-excludes `las_honoka` — LAS 4.1.9
  otherwise spawns no hands). `main.xml`, localization, deterministic
  `BUILD_INFO.json` (`runtime_verified: false`, `models_present: true`),
  deterministic zip + sha256. `.object` lists `g_body` on, `g_body_lod1`
  off (LOD1 = same geometry, harmless); `.unit` keeps the ContourExt like
  Miranda's; materials: `generic:CONTOUR:DIFFUSE_TEXTURE:NORMALMAP:
  SKINNED_3WEIGHTS` + `shadow_caster`.
- **Icon**: our own 4-view render of the built model (nothing from DOAXVV
  re-distributed; the tile is this model). `build_icon(..., view=3)`
  composites the three-quarter view on a gradient.
- **In-game checks that still must run** (none of the below is heist-verified; the outfit-menu
  preview is, as of 2026-11-15 — captures in `docs/renders/in-game-2026-11-15/`, user report):
  gloves spawn at the cut (or hands go skinless); jacket/skirt
  arm silhouette; normal-map strength and Y direction; skirt hem rags
  z-fighting/culling; `g_body_lod1` on/off flicker; contour outline; LAS
  menu shows the tile and the name; the glove adapter keys
  (`las_honoka` player style) are right for the installed LAS version;
  gloss=20 matte look on skin.
- **Process**: the sandbox `.git` was reset to the branch base once
  (2026-11-15) and the earlier local commit briefly ceased to exist; the
  full tree was re-committed as `9ade581` (the 2026-11-14 work) and
  `7ad904b` (build driver). Test suite: 600 passed, 8 skipped (before the
  reset and again after re-anchoring). `dist/` was never rebuilt or staged.
- **Source connector slivers — dropped at build** (2026-11-15). Every mesh
  in the TMC carries the same artefact: triangle fans from the source's
  strip-break quads, each pair a long thin sliver (a ~0.2 cm root edge, apex
  up to 146 cm away in the retargeted frame) joining unrelated body parts
  (wrist to feet, neck to ankle, head-top to wrist). They drew as hairline
  streaks in every preview (2026-11-15 renders). Their presence is in the
  source index data (6 in cap2, 8 in headdress2, 12 in the body), so no
  decode/winding repair can remove them; the build now drops every triangle
  with an edge over `LONG_THIN_MAX_EDGE_CM` (20 cm) per slice after the wrist
  cut. The threshold sits in an empty gap (longest legitimate edge 13.4 cm;
  smallest stray 23.7 cm). Per geometry: 50,244 → 50,218 triangles; signed
  volume 181,599 → 188,011 cm³. The pack was rebuilt (byte-reproducible in a
  second output directory) and re-committed to `dist/`.

`runtime_verified` stays `false` everywhere it appears.
