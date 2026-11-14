# Honoka "Secret Report" TMC — decode findings and rigged export (2026-11-14)

**Status: decode complete, export written, nothing game-verified.**
`runtime_verified` stays `false`. This is a research/decode record, not an
in-game verification. Nothing here has been run inside PAYDAY 2 or DOAXVV.

## Source

| File | sha256 |
|---|---|
| `references/Outfit for Honoka-109-1-1-1628020933.zip` | `86fc084c7310e9cd78bfb39cd4bb15486a15295f1c233c754492e1c4f572e154` |
| `Honoka_DOAXVV_Secret_Report.TMC` (in the zip) | `12d4f370ee47a183bfc3ba4792b7fda47b4176b13444a87745c89089cefa129b` |
| `references/Honoka/Honoka_DOAXVV_Secret_Report_ALL_EXPORT.OBJ` (3rd-party dump) | `e6e2529018eff64d84721f1468538abc9750564265ca7ea01b2e0bdebe97f4bd` |
| `references/Honoka/Honoka_DOAXVV_Secret_Report.rigged.glb` (this repo's export) | `b5f5128293274244d1e6e5bfbdfde3bfe339519ab17167b328ad8718869d8f13` |

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
- Body has **no head geometry** (neck stump) ✓ LAS-compatible; **hands ARE
  present** in `WGT_new_aya_body_decl0` and must be cut/retargeted at the
  wrist for the LAS body (cf. `Christie_Slim`); wrist cut not started.
- Whether to keep cap2/headdress2/feather/sweat_chest (jacket, skirt,
  ribbons, emblem) or body-only; whether accessories are separate LAS atoms
  or dropped. Owner decision pending.
- `*T_body_feather` decodes to long sash-like slivers; the OBJ exporter
  dropped this mesh entirely. Purpose unverified — exclude from any build
  until reviewed.
- `MCAPACK` (37 material records) not decoded; texture mapping to
  `references/Honoka/L_*.dds` unverified (TMCL = textures only).
- LAS-side bone mapping is manual (`skeleton_map.json` has no MOT* names);
  the XNALara-ish `MOT*` skeleton → PD2 Diesel 136-bone names is the
  remaining big task.
- Nothing in-game checked; `runtime_verified` = false everywhere it
  appears.
