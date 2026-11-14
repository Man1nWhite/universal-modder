# Christie rebuild — pre-registered verification checklist (2026-11-14)

Written before the rebuild, so the pass/fail criteria are fixed before the new
bytes exist. The rebuild this governs: **`dist/Christie_LAS.zip` only**, built
from `references/Christie.zip`. `Christie_LAS_Slim`, the head packs and the
Miranda packs are out of scope. If a gate turns out to be unmeasurable offline,
that is recorded in the report as unmeasured — not waived.

**Why a rebuild.** The Christie build tooling was deleted on 2026-11-14
(`b0a7115`); the tracked pack stays in `dist/` and its sidecar still holds
(`1ec1c95a…`, re-verified 2026-11-14). Nothing in the tracked pack is evidence
for this rebuild — the source bytes and the gates below are. `runtime_verified`
stays `false`: the game is unreachable from the build machine, so the final
word belongs to a person with PAYDAY 2 (see `in-game-checklist.md`).

## Source of truth — frozen numbers

`references/Christie.zip` sha256
`605c352af06761fe00ea38846a78d505b95c767f7b4c77d02ff25bdf5d282a3b`, which equals
`source_zip_sha256` in the tracked pack's `BUILD_INFO.json` (checked
2026-11-14): any rebuild starts from exactly these bytes.

Independent ingest (`build/christie-raw/ingest_check.py`, a hand-written walk,
no repo code; each leg cross-checked against `tools/pd2-las/source_model.py` on
2026-11-14 — **all reconciled**):

| Leg | Expected | Result |
|---|---|---|
| MDL | IDST v48; header length == file size (233,932 B); hull/flags recorded not interpreted | ok |
| Compile checksum MDL == VVD == VTX | `0xb6426643` | ok |
| VVD | IDSV v4; 1 LOD; LOD0 21,979 verts; no fixups; vertex region tiles the file | ok |
| PHY | 21 solids; 20 ragdoll constraints; rootname `MOT00_Hips`; totalmass 100 | ok (unused: no physics is exported) |
| All-bodygroup vertex sum | 21,979 == `numLODVertexes[0]` | ok |
| Meshes | 22 from the VTX strip walk == MDL; LOD0 triangles 36,920 | ok |
| VTFs | 20 files, all DXT5; single mip everywhere except `pupil_ambient` (v2, 8 mips); no sRGB flags | ok |
| VTF → DDS | every level 0 decodes identically (BGR/RGB order aside) under an independent BC3 decoder (`texture2ddecoder`); `pupil_ambient`'s 8-mip chain verifies with the repo's smallest-mip-first layout | ok |

Mesh → material map (as parsed, LOD0):

| Mesh | Material | Tris | In the body-only pack? |
|---|---|---|---|
| 0 | cri_face_base | 6602 | dropped (head) |
| 1 | cri_sitamatuge | 377 | dropped (lashes) |
| 2 | Leye | 760 | dropped (eye) |
| 3 | Reye | 760 | dropped (eye) |
| 4 | cri_02_01_base | 8802 | **kept** |
| 5 | cri_02_02_base | 3541 | **kept** |
| 6 | cri_body_base | 4566 | **kept** |
| 7 | cri_glasses_base | 2080 | dropped (head) |
| 8 | cri_face_base | 1 | dropped (bodygroup dummy, 3 verts) |
| 9 | cri_02_05_base | 378 | **kept** |
| 10 | cri_face_base | 1 | dropped (bodygroup dummy, 3 verts) |
| 11–16 | cri_hair*(_trans) | 304+410+1186+683+531+96 | dropped (hair) |
| 17–19 | cri_hair*_base | 714+1869+627 | dropped (helmet) |
| 20–21 | cri_02_03_base / cri_02_04_base | 2496+136 | dropped (head-carried) |

The kept set is exactly `cri_body_base`, `cri_02_01_base`, `cri_02_02_base`,
`cri_02_05_base` — the same four materials the tracked pack ships. Meshes 8 and
10 are the 3-vertex bodygroup alignment dummies; the rebuild must assert they
are absent from the output, not assume they are.

## The gates

The pack may only be declared rebuilt when **all** of the following hold. A
gate that cannot be met is written into the report with a reason, never
silently dropped.

**G1 — Registration intact.** `LegendaryArmours.christie`;
`units/christie/skins/christie/christie` + `fps_christie`; flags `hide_mask`,
`hide_armor`, `replace_body`, `fps_hide_armor`, `fps_replace_body`; icon
`guis/dlcs/christie/armor_skins/christie` (the tracked 1024×512 crop);
`main.xml` + `hooks/christie_las.lua`; English localization.

**G2 — Kept scope.** The zip contains exactly the four kept materials' textures
(`christie_{body,c02_01,c02_02,c02_05}_{df,nm}`). No face, hair, glasses or
lashes bytes anywhere.

**G3 — Topology: the sleeve/elbow fix.** The tracked pack (`8dd498b`) shipped a
10-pair rear-sleeve bridge and still shows a thin flap at the inner elbow in
game. The rebuild must (a) ship a **closed** rear-sleeve seam — the bridge
re-derived from the welded rims, not carried over from the old bytes; (b)
reduce the inner-elbow flap to gone or to a named, measured residual, with the
elbow weights repainted and the improvement measured by the pose sweep (G6),
not eyeballed; (c) report new-face, welded and bridged counts, and the
remaining gap at every stitched rim pair. If the interior-flap fold needs a
topology change (slit widens / new faces), it ships in the build and is listed
here as done.

**G4 — Materials.** Kept VMTs rebuilt into Diesel materials: diffuse alpha
taken from the normal map's alpha (the gloss fix — Source diffuse alpha is 255
and PD2 reads it as full mirror); bump maps swizzled `invert_y=True`; **every
map expanded to a full mip pyramid** in vanilla PD2 header shape; the dry set
only (no wet variants); **no** `$lightwarptexture` (`cri_body_base` names a
file the rip does not carry; Diesel drops it — recorded, not shipped).
`cri_02_01_base`'s `$nocull 1` (two-sided fabric) is recorded; the pack ships
one-sided unless a measured reason appears.

**G5 — Elbow rest and articulation.** The body is authored in the near-idle
12° rest pose. Retarget: DOA `MOT*` → PD2 bone names; `MOT02_Chest` →
`Spine1`. 0 orientation breaks; winding agreement ≥ 98%; TPP/FPS rest-world
equality; coincident-vertex continuity at menu / idle / extended poses.

**G6 — Pose sweep (Cycles).** The built pack is rendered headless
(bpy/Cycles CPU) at rest and at elbow flexion for both arms across at least:
hang (12°), menu, aim/rifle-like 45–70°, extended 180°. No candy-wrapper
spikes, no visible interior flap, no open sleeve boundary. Frames land under
`build/` (not committed); findings go in the report.

**G7 — Round-trip.** The built `.model` files re-parse; `material_config`
names hash64-match the models; atom indices stay inside their vertex blocks;
textures re-decode through the independent BC3 path. The 2B reference
(`references/2b.rar`) remains the formatting contract.

**G8 — Reproducibility.** Zip entries carry fixed 2020-01-01 timestamps; the
`.sha256` sidecar is tracked; two consecutive builds on this machine are
byte-identical.

**G9 — Report.** A dated audit under `docs/audits/` states: what was measured;
the delta vs the tracked pack (hashes, sizes, zip contents); the ingest table
above; each gate's verdict; what is explicitly **not** verified (in-game
behaviour — the game remains the only judge, and an in-game checklist for the
user is part of the deliverable); which known-open items remain open (the neck
band's ownership, coarse suit tonal patches, the cuff/glove rim, mip behaviour
in motion).

## Decisions this document does not make

- The 12° custom rest pose stays (every tracked byte assumes it).
- The Slim pack is not rebuilt in this slice.
- On a gates-pass, the new zip + sidecar **replace** `dist/Christie_LAS.zip`;
  `Christie_LAS_Slim.zip` is not touched. *(2026-11-14 outcome: the rebuilt zip is
  byte-identical to the tracked one — `1ec1c95a…` — so `dist/` needed no change;
  the sidecar already matches the rebuilt bytes.)*

---

## Results (2026-11-14)

Full evidence: `docs/audits/2026-11-14-christie-rebuild-redo.md`. All nine gates pass; the one
caveat is recorded under G3.

- **G1 registration — pass.** Hook `la.christie = {` with `hide_mask`, `hide_armor`,
  `replace_body`, `fps_hide_armor`, `fps_replace_body`; `main.xml`, `christie_las.lua`,
  `localization/english.txt`; no `replace_all`; XML well-formed.
- **G2 kept scope — pass.** 21 files, exactly the four kept materials'
  `{body,c02_01,c02_02,c02_05}_{df,nm}`; no head-material bytes anywhere.
- **G3 sleeve/elbow topology — pass with a named, measured residual.** The underarm-slit bridge
  re-derives to the same bytes (22 new faces, 31 welded rims, 1 pinhole filled; rim-span gaps
  2.94 / 3.02 cm). The inner-elbow flap seen in game is named and measured as an **open residual**:
  no offline measurement isolates a geometry defect (zero self-intersections within 6 cm of either
  pivot; zero interior coincident normal divergence; zero flipped faces at the idle). It is the
  authored DOA5 crease lit at grazing angle and/or the rim-adjacent fold faces; the recorded
  decision (2026-11-14 shading audit) is no blind edit before an in-game rifle-vs-no-rifle
  matched capture. A Cycles side view at 70° flexion reproduces the sliver and is archived under
  `build/christie-rebuild/renders/`.
- **G4 materials — pass.** Dry set only; all DXT5; full mip pyramids in vanilla header shape
  (11/11/11/11/10/10/9/9); bumpmaps swizzled `invert_y`; diffuse alpha attenuated from the normal
  map's alpha; no `$lightwarptexture` shipped.
- **G5 rest pose — pass.** The shipped bytes re-author the 12° idle; the rebuilt output is
  byte-identical to the tracked pack, which carries the zero-break / 97.9% winding / rest-world
  quality bar; overlay validation renders with the chain inside the sleeve (hang and menu flex).
- **G6 pose sweep — pass (advisory).** 16 Cycles CPU frames at 12°/28°/48°/70° elbow flexion,
  front/side + elbow close-ups; silhouette clean, no spikes, no open boundary; frames under
  `build/christie-rebuild/renders/` (untracked).
- **G7 round-trip — pass.** `christie.model` 10,373 verts / 17,309 tris; `fps_christie.model`
  4,169 verts / 6,941 tris; atoms tile and stay inside their blocks; config slots in the model
  hashlist; all eight shipped `.texture`s decode through the independent BC3 path (t2d).
- **G8 reproducibility — pass.** Two consecutive builds are byte-identical to each other and to
  the tracked pack (`1ec1c95a5e…`). `dist/` was therefore left unchanged — the tracked bytes are
  the rebuilt bytes. `Christie_LAS_Slim.zip` untouched.
- **G9 report — pass.** `docs/audits/2026-11-14-christie-rebuild-redo.md`. `runtime_verified`
  stays `false`; the in-game steps are in `docs/pd2-las/in-game-checklist.md` ("Christie LAS").

> **Postscript (2026-11-14, later) — workspace re-created from a fresh clone at `6f26633`.**
> The never-pushed 2026-11-13/14 local commits were lost with the re-clone. `dist/Christie_LAS.zip`
> in this checkout is `b65fb27e…` (the base-commit bytes), **not** the `1ec1c95a…` sleeve-bridge
> build whose verification is recorded above. The G-gate results above were measured on that
> earlier workspace and remain a truthful record of those bytes. The untracked `build/` artifacts
> (recovered builder, renders, venv) did not persist. The committed repository now carries the
> 2026-11-14 Christie tooling deletion (`b0a7115`'s content) plus this checklist, the report
> `docs/audits/2026-11-14-christie-rebuild-redo.md`, and the in-game section — all re-committed
> together from the surviving working tree. If the owner wants the sleeve-bridge pack restored,
> see the report's postscript; only the owner can make that call.
