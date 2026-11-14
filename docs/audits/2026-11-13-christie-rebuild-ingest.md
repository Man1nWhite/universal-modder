# Christie rebuild — independent ingest audit (2026-11-13)

Prompt step 1 of the Christie rebuild: what the raw
material *is*, read by means that did not write it. No pack was rebuilt and nothing under
`dist/` changed in this audit. Baseline for the rebuild: this branch is green on 2026-11-13
(`make -sC tools/pd2-las green`, 2026-11-13, before the sleeve rebuild: all 13 stages, 16/16 zips
rebuilt byte-identically; suite 711 passed, 5 skipped, 2 expected failures — the two D18
slim-sleeve cases; the slim-sleeve cases have since been fixed and the expected failures
removed, see `docs/audits/2026-11-13-christie-sleeve-wedge.md`). The throwaway probe used here is `build/ingest_probe.py` (not tracked; its findings are
reproduced below).

**Honesty box — what "independent" means here, leg by leg**

- MDL/VVD/VTX walks: written from the SDK struct layouts as a differential check on
  `tools/pd2-las/source_model.py` and `tools/pd2-las/build_christie_las.py`. This is a second code
  path, not a third-party tool. It found no contradiction in the builder's own numbers.
- VTF/VMT: `sourcepp` 2026.11.1 (C++ reader, installed by `recover_env.sh --extras`) — genuinely
  not this repo's code.
- MDL third-party: **not available on this machine**. SourceIO's Linux native library requires
  glibc ≥ 2.38 (master needs ≥ 2.43); this box has glibc 2.36 and no root to raise it, and no
  earlier tag ships a Linux build. Blender itself **does** run here as `bpy` 4.5.16 LTS from PyPI,
  headless, verified by a mesh build + a Cycles CPU render. A SourceIO run remains desirable on a
  machine with a newer glibc; what is recorded below is the best available here, labelled as what it is.
- Screenshots: re-measured at 1:1 from the archived PNGs with Pillow.

## The source archive, as found

`references/Christie.zip` — 7,445,876 bytes, 20 VTFs, 20 VMTs, 1 MDL, 1 VVD, 1 VTX, 1 PHY.
Its sha256 today equals `source_zip_sha256` inside both tracked Christie packs' `BUILD_INFO.json`
(checked 2026-11-13): **the tracked packs were built from these exact bytes.** That also freezes the
ingest target: any "from the beginning" rebuild starts here, not from the tracked packs.

Cross-file integrity: MDL, VVD and VTX all carry the same checksum `0xb6426643`
— one compile, no mixed files. The MDL checksum field spells its own path:
`Plasmid/DOA5/Christie_c2.mdl` — a fan conversion for Source by "Plasmid" of a DOA5 costume, MDL
version 48, SM 3.0 vertex program (`dx90.vtx`). That provenance string is the first thing the
digest never told anyone. No license text ships in the zip; the packs are derivatives of DOA5
assets. Your D32/D34 redistribution decisions stand as you made them; the rebuild does not change them.

**Units are inches.** Vertex extent z = −0.91..70.59 in → 181.6 cm tall (DOA5 Christie, canon
≈ 181 cm). Eye position z = 70 in; illumposition z ≈ 34.6 in (mid-torso). Hull fields exist
(min (−7.485, −26.216, −1.667), max (7.834, 26.308, 70.967)) —
the hull is whatever the converter wrote and is unusable as evidence of game behaviour; recorded,
not interpreted. Flags = 9 (meaning not parsed; recorded verbatim).

**Bones: 98.** One root, `MOT00_Hips`; parents strictly precede children; skin weights reference
at most bone 96; 1–3 influences per vertex; every sampled weight set sums to 1. DoA-style bone
names (`MOT00_*`, plus `OPT_AS_*_Hip` helpers and `Jacket_L`/`Jacket_R`), not ValveBiped — the
retarget map (`christie_skeleton_map.json`) is not optional decoration.

**One sequence declared** (`numlocalseq` 1) and one local anim. The port consumes no sequences —
LAS replays the heister's own animation set — so it stays out of scope, and its contents are not
relied on anywhere.

**Bodygroups (the part of the source the pack drops, in full):**

| Bodypart | Models (each ≥ 1) | Verts |
|---|---|---|
| `studio` | `christie_c2_reference.smd` — 7 meshes | 14,615 |
| `glasses` | `christie_c2_glasses.smd` — 1 mesh; `christie_c2_none.smd` (placeholder) | 1,370 + 3 |
| `bra` | `christie_c2_bra.smd` — 1 mesh; `christie_c2_none.smd` | 230 + 3 |
| `head` | `christie_c2_hair.smd` — 6 meshes (hair/face shell); **`christie_c2_helmet.smd` — 5 meshes** | 2,144 + **3,614** |

All-bodygroup vertex sum = **21,979**, exactly `numLODVertexes[0]` of the VVD (14,615 + 1,370 + 3 +
230 + 3 + 2,144 + 3,614). Model-0-only sum = 18,359 — the generic L4D2 dialect of `source_model.py`
(first model, `mstudiomodel_t` stride 96) therefore **refuses this file by design**; the Christie
path (`build_christie_las.load_christie`) walks all bodygroup models with stride 148 and matches the
VVD exactly. The two are legitimately different dialects of the same codec family; this is now
written down instead of discovered mid-debug. The `.phy` (35,995 B) ships in the rip and is unused —
no physics is exported by the contract.

The `none.smd` 3-vertex dummies fill the +3-vertex alignment gaps between per-bodygroup vertex
ranges (glasses at 14,615 (1,370) → placeholder at 15,985 (3) → bra at 15,988 (230) → placeholder
at 16,218 (3) → hair at 16,221 (2,144) → helmet at 18,365 (3,614), ending exactly at 21,979). Whole 21,979-vertex array accounted for, 1:1, with 6 pad vertices.

**VTX**: version 7, same checksum. All-bodygroup walk yields 22 meshes (studio 7, glasses 1 +
placeholder 1, bra 1 + placeholder 1, hair 6, **helmet 5**) = the MDL's mesh total; model-0-only is
15; strip indices 110,760; triangle upper bound 36,920 before the builder's tristrip expansion,
degenerate removal and dedup. VTX↔MDL mesh counts agree both ways.

**VTFs**: 20 files, every one DXT5; every one a single mip except `pupil_ambient` (v2, 8 mips);
no sRGB flags. No source texture needs format conversion — only mip rebuilds and the gloss/alpha
retouches, which the build already does.

**The VMTs tell three stories the digest never did:**

1. **The source cannot ship a head, because its head textures do not exist.** Missing (referenced,
   absent): the dry face (`cri_face_base`, `face_n` — the zip carries only the *wet* face pair),
   `cri_glasses_base`, every `cri_hair*_base{,_trans}` / `_nrm` (C1 tree), `cri_sitamatuge` (lashes),
   every wet variant's `$bumpmap` (`jessie/glass_n`, from a different character's rip), and the
   `faceWRp` lightwarp that `cri_body_base`, `cri_face_base` and their wet twins sample
   (`$lightwarptexture`). The only face assets present are the *wet* face pair + the two eyes.
   The LAS body-only contract for this pack is **forced by the rip**, not merely preferred.
2. **Phong intent is in the file**: body/costume pieces `$phongexponent` 7 (`cri_02_01`, `$nocull 1`)
   – 10, `$phongboost` 1–3, `$phongfresnelranges [.3 .85 30]`, `$halflambert 1` (body is 0); the wet variants are 75/1/`[1 6 15]` (latex/glass). The pack ships the dry
   set (`mtr_body`, `mtr_c02_01`, `mtr_c02_02`, `mtr_c02_05`) — the right call, but the phong data
   the build currently discards is a better starting gloss signal than the one the pipeline
   reconstructs from the normal map. That is a material-rebuild decision, listed in the plan, not
   settled here.
3. **`cry_face_base_wet`'s bumpmap is `jessie/glass_n`** — a file that never shipped either; the wet
   face pair is itself half-broken. It ships nothing today; recorded so nobody "fixes" the pack by
   shipping it later without knowing it.
4. **One shipped material is not self-contained either**: `cri_body_base` names a
   `$lightwarptexture` — `models/plasmid/DOA5/Christie/C1\detail/faceWRp` — which is **absent
   from the rip** (checked directly, along with the four kept VMTs' own `$basetexture`/`$bumpmap`
   and `$lightwarptexture` entries). Diesel has no lightwarp concept and the builder does not emit
   one, so the pack does not depend on the file — but the Source material as shipped does not render
   "as authored" without it. The other three kept VMTs also carry `$model 1`; `cri_02_01_base`
   carries `$nocull 1` (two-sided fabric) which the pack does not reproduce. These are recorded,
   not silently inherited.

## Independent re-measurement of the archived 2026-11-10 screenshots

1:1, Pillow, same native PNGs (no resize/recompress):

| Shot | Region | 2026-11-10 review | This audit |
|---|---|---|---|
| 01 | neck, box (200,160,300,260) | step 9.4 (y 168) | step 10.94 (y 169) |
| 02 | neck, box (215,130,315,240) | step 11.9 (y 172) | step 13.90 (y 236) |
| 08 | neck, box (255,240,300,292) | step 6.9 (y 283) | step 16.05 (y 279) |
| 05 | rear-sleeve wedge, core 8×8 @(470,518) vs wall (498–518,510–530) | core (29,30,26) vs wall (41,42,38) | core (26.0,28.9,25.3) vs wall (42.2,43.7,38.8) |
| 08 | inner-elbow flap, box (50,525,130,600) | thin flap w/ bright rim | 4.5 % of px < 60 luminance, min 25.5 |

The exact numbers move with the crop box; the conclusions do not: the throat shows a hard planar
step, the rear sleeve carries a near-black wedge below the elbow, and the rifle frame carries a
thin flap at the inner elbow. The archived review's defect list stands, measured twice. Nothing in
the re-measurement *clears* the neck band as "head-only" or "body-only" — the §10.4 bisect (head
pack removed, body alone) remains the experiment that assigns ownership, and it is scheduled before
any mesh work in the plan.

## What this audit validates / does not validate

Validates (this branch, 2026-11-13):

- the tracked packs were built from exactly these source bytes (source hash == pack's recorded
  `source_zip_sha256`);
- the builder's Christie dialect reads the files consistently: checksums agree across MDL/VVD/VTX,
  all-bodygroup vertex sums match the VVD exactly, VTX↔MDL mesh counts agree, weights are sane,
  one LOD, no fixups, tangent/vertex regions tile the file exactly;
- the Christie path executes end-to-end to a byte-identical result: `tools/pd2-las/fresh.py` rebuilt
  `Christie_LAS.zip` and `Christie_LAS_Slim.zip` from this archive on 2026-11-13 and the rebuilt
  bytes equal the tracked bytes — which runs `load_christie()` (all-bodygroup walk, `sm._read_vvd`
  at 21,979 vertices, VTX mesh count == MDL mesh spec count == 22) on every fresh-build invocation;
- the source's missing pieces are known and named (face, lashes, eyes-are-present, glasses, hair, lightwarp),
  so the body-only contract is not fragile preference — it is what this rip can produce;
- the builder's four shipped materials are *available* from the rip — each one's own diffuse and
  bump maps exist (basetexture/bumpmap walked by VMTs, all 20 VTFs parsed); `cri_body_base` also
  names an absent `$lightwarptexture`, which Diesel drops by design (see item 4 above). No other
  dependency of shipped bytes is missing;
- the suite is green on this branch: 711 passed, 5 skipped, 0 expected failures (the D18
  slim-sleeve cases were fixed on 2026-11-13 and the expected-failure machinery removed;
  see `docs/audits/2026-11-13-christie-sleeve-wedge.md`), and the full local workflow check
  passed on 2026-11-13 (`make -sC tools/pd2-las green`, all 13 stages, including every tracked
  pack rebuilt byte-identically);
- the failure modes seen on screen are reproducible from the archived frames.

Does **not** validate (open, in priority order): in-game behaviour of these bytes at all; the neck
band's owner; the inner-elbow flap; the rear-sleeve wedge; the coarse suit tonal patches; the cuff/glove rim; the D18 slim-sleeve leak; the mip/gloss policy in motion (the game's
sampling is not the offline pyramid); first-person arms at 60 Hz; performance/crash-freedom. The
second renderer (bpy/Cycles, verified working) will be used for the offline material pass; the game
remains the only judge of the final look.

## What the digest did not say (summary)

- Provenance: "Plasmid/DOA5/Christie_c2.mdl" — fan conversion; no license ships in the zip.
- A **helmet bodygroup** (5 meshes, 3,614 verts) exists in the source and is dropped.
- The dry face, glasses, lashes, hair and the lightwarp are **absent from the rip** — the head was
  never ship-able from this archive; the wet face's own bumpmap is a file from another character's rip.
- One LOD only; no vertex fixups; vertex/tangent regions tile the VVD exactly.
- 21,979 = all-bodygroup sum; 18,359 for model 0s alone — the generic L4D2 reader is the wrong
  tool for this file by construction.
- Source-compile checksum is the same 4 bytes in all three files (`0xb6426643`) — a fingerprint the
  pack can (and during the rebuild will) record.
- The digest never said the tracked packs provably came from these bytes (now: yes, hash-checked).

Related: the rebuild plan is recorded in `docs/pd2-las/CHRISTIE.md` (historical fit record) and the
pre-registered in-game protocol in `docs/pd2-las/in-game-checklist.md`; the signed acceptance gates are in
`docs/pd2-las/DECISIONS.md`. All three are unchanged by this audit.
