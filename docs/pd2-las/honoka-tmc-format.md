# Honoka "Secret Report" TMC — decode findings and rigged export (2026-11-14/15)

**Status: decode complete; the rigged export is tracked.** This page is the record of the source file. The outfits
that ship are `Honoko2`..`OfficeSuite`, built from the Collada export and using this TMC only for their skin weights and
joint world binds (`docs/pd2-las/DECISIONS.md`, D40–D46, D50); the TMC-only pack built here in 2026-11-15 was deleted
the same day. Read the decode sections as written; the last section says what the shipped build takes from this file.

## Source

| File | sha256 |
|---|---|
| `references/Outfit for Honoka-109-1-1-1628020933.zip` | `86fc084c7310e9cd78bfb39cd4bb15486a15295f1c233c754492e1c4f572e154` |
| `Honoka_DOAXVV_Secret_Report.TMC` (in the zip) | `12d4f370ee47a183bfc3ba4792b7fda47b4176b13444a87745c89089cefa129b` |
| `references/Honoka/Honoka_DOAXVV_Secret_Report_ALL_EXPORT.OBJ` (3rd-party dump) | `e6e2529018eff64d84721f1468538abc9750564265ca7ea01b2e0bdebe97f4bd` |
| `references/Honoka/Honoka_DOAXVV_Secret_Report.rigged.glb` (this repo's export, regenerated 2026-11-15 with palette-remapped joints and normal-aligned winding) | `ef23c55e738bf857b2b04ace890c4dffa3413f7d1e831bef7dd438e05940c326` |

## What the file is

A Dead or Alive Xtreme Venus Vacation (DOAXVV) costume TMC for the custom
character Honoka. Sections: `MdlGeo` (7 ObjGeo) → `VtxLay`
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
- Weights: normalized by 255 on export. 62 all-zero rows exist; those are placeholder rows,
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
glTF 2.0 binary; 171-joint skin, identity scene = bind pose). Recorded export validation:
container/views in bounds; scene lists only `[Hips_root, mesh nodes]`;
171/171 joints reachable; `W·IBM ≈ I` ≤ 5e-06 per joint; glTF world
matrices == TMC GlblMtx ≤ 5e-06; all weight rows sum to 1.0; indices in
range; triangle totals match the decoder; positions point-in-time render
(`build/honoka-analysis/tmc_render_front.png`, `tmc_render_side.png`)
matches the OBJ silhouette (headless body, jacket, skirt, ribbons, hands,
heels).

## Resolved items

- **Target format:** Legendary Armour Skin (`LAS`, `BODY_ONLY` + `glove_adapter.lua` in `tools/pd2-las/`).
- Body has **no head geometry** (neck stump) ✓ LAS-compatible; the shipped
  build cuts the hands at the wrist (`tmc_las.cut_group_at_wrists`).
- Garment selection: the shipped `.dae` build takes the body
  and the buttoned suit submeshes and excludes `WGT_cap2`, `feather` and `sweat_chest`.
- `*T_body_feather` decodes to long sash-like slivers; excluded from the build.
- `MCAPACK` (37 material records): not decoded; the shipped build takes its texture
  assignment from the `.dae` material bindings, not from this file.
- LAS-side bone mapping: `tools/pd2-las/tmc_skeleton_map.json`
  (MOT* → PD2 Diesel names; unmapped helpers merge into their nearest
  mapped ancestor).
- In-game menu/lobby captures of `Honoko2` and `OfficeSuite` are archived under
  `docs/renders/honoka/in-game/` (`docs/pd2-las/HANDOFF.md`); `runtime_verified`
  stays `false` as a builder constant (D31).

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
glTF exporter, the skinning the `.dae` build transfers) now see
normal-consistent winding. The
stripped-parity code (`_strip_to_tris`) is still what generates the
triangle list; the alignment is a deterministic post-fix, not a new
heuristic. `runtime_verified` stays `false`.

## The outfit ships from the `.dae` (2026-11-15)

`Honoko2`..`OfficeSuite` are built by `tools/pd2-las/build_honoko2_dae.py` from
`references/Honoka/Honoka_DOAXVV_Secret_Reportout.dae`, which carries the six material slots the source binds and
the buttoned suit. The TMC-only pack this page used to describe — three merged material slots over the raw TMC
meshes, the unbuttoned `WGT_cap2` jacket laid over the buttoned `WGT_headdress2` suit — was deleted on 2026-11-15
at the owner's direction; its bytes stay in git history (`ce1d1c0`, `2e49f14`). See D40–D46, D50.

What the shipped build still takes from this file:

- **Skinning.** The Collada export has no `<library_controllers>`; every `.dae` vertex matches a TMC vertex to
  ~0.0001 cm, so the four influences are matched and transferred per vertex, then palette-remapped onto the TMC's
  171 joint names and retargeted with `tmc_skeleton_map.json`.
- **Frame and bind pose.** `tmc_las.basis_matrix()` (Y-up cm → Z-up cm, det = +1) and `tmc_las.glbl_to_diesel()`
  for the world bind matrices.
- **Mesh post-processes.** `tmc_las.cut_group_at_wrists()` for the glove cut and
  `tmc_las.drop_long_thin_triangles()` for the source's strip-break connector slivers.

`runtime_verified` stays `false` in the packs; the outfit-menu and lobby captures of 2026-11-15 (`Honoko2` and
`OfficeSuite`) are the in-game record (`docs/pd2-las/HANDOFF.md`).
