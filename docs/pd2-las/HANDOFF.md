# HANDOFF — the dated state of the pd2-las packs

> **Start at [`tools/pd2-las/README.md`](../../tools/pd2-las/README.md).** Commands, status, the file map, the
> invariants and the open work are written there and nowhere else. This page is the dated record beneath it:
> what a person has seen in game and when, how the tracked bytes came about, which approaches failed. It
> gives no commands and keeps no work queue. Reasons: [`DECISIONS.md`](DECISIONS.md).
> Day by day: [`tools/pd2-las/MODLOG.md`](../../tools/pd2-las/MODLOG.md).

Rewritten on 2026-11-11. Until then this page was also a quickstart, a recovery guide, a file map, a list of
invariants and a work queue: second copies of what the README says, which had drifted from it and from the
tree. What they claimed and what was measured instead is under [Corrections](#corrections).

## Tracked packs

Which bytes are tracked is not written here. `make -sC tools/pd2-las status` prints each pack's size and sha256
and whether the zip is what git holds; `dist/<name>.zip.sha256` is the hash itself. A size or a hash on this
page is one that a person saw in game or that an earlier build had: `test_no_document_quotes_what_status_prints`
fails on a current one. The two Miranda LAS packs are also tracked, byte for byte, under `build/pd2-las/`.

Every pack rebuilds to its tracked bytes in the pinned environment on any x86-64 Linux machine: each builder writes
one fixed timestamp into every zip entry and, since 2026-11-12, puts itself on one declared numeric code path
before it computes anything, so a `.sha256` sidecar is a true build hash. CI builds all 14 packs on its runner
and compares the 16 zips with their tracked hashes, with no tolerance, and has done so on runners with AVX-512 and
without. Before that day 12 of the 14 packs came out differently on a CPU without AVX-512. The causes, the
fixes and where the guarantee ends are in
[`docs/audits/2026-11-12-cpu-independence.md`](../audits/2026-11-12-cpu-independence.md) and in
[`DECISIONS.md`](DECISIONS.md), D26.

## Seen in game

What a person has reported from the game, by date. Only the user has run the game; the screenshots are the
user's, and "no record" means that nothing in the repository says anyone looked.

`runtime_verified` in a pack's `BUILD_INFO.json` is a constant its builder writes, and it is `false` in every
pack that has one. Until 2026-11-13 both Christie packs said `true`, on the strength of the 2026-11-05 test of
the base pack and through every rebuild after it. The flag does not say whether the tracked bytes were in
game. This table does.

| Pack | Last seen in game | Were those the tracked bytes? |
| --- | --- | --- |
| `Miranda_LAS`, `Miranda_Busty_LAS` | no record | — |
| `Christie_LAS` | 2026-11-05, tested by the user: the headless outfit shows the heister's own head; the texture gloss was fixed by attenuating the diffuse alpha | no: the tracked zip comes from the later elbow, seam and normal rounds, and the record has no later sighting of the base pack |
| `Christie_LAS_Slim` | 2026-11-10, eight screenshots from the user | no: rebuilt on 2026-11-12 (tangent frames, the order of two triangles, `BUILD_INFO.json`) and on 2026-11-13 (one flag in `BUILD_INFO.json`); the screenshots show `7a4d010c…90a3e6f` |
| `Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}` | 2026-11-05, tested by the user | no: all four were rebuilt on 2026-11-07 with the neck skirt, again on 2026-11-11 and on 2026-11-12 |
| `Miranda_Romance_over_{Joy,Clover,Bonnie,Sydney}`, `Geralt_over_Rust` | no record | — |
| `lawson_las` | see [`tools/pd2-port/STATUS.md`](../../tools/pd2-port/STATUS.md) | |

- **`Christie_LAS_Slim`, 2026-11-10.** The [8-frame screenshot
  batch](../audits/2026-11-10-christie-slim-screenshot-review.md): the lobby silhouettes show no outward growth
  at the inner elbow, but the rifle pose still shows a thin flap-like fold there, and the rear-sleeve dark
  wedge and neck bands are still visible. That batch replaced every archived screenshot; the 2026-11-07 and
  11-frame sets are Git history only.
- **The Miranda LAS packs** have the checklist `docs/pd2-las/in-game-checklist.md` waiting for a person with
  the game. Offline confidence was rated 8/10 for "loads and displays correctly" (structural parity with the
  working 2B pack is the main reason; never having launched the game is the main doubt).
- **Head packs, coverage.** Clover and Bonnie replace the heist, menu *and* Safe House (`*_chill`) models; Joy
  and Sydney replace the heist + menu models only, so their Safe House units keep the vanilla head. There is
  no checklist for the head packs. Until someone looks at a throat again the four L4D2 packs are
  *offline-verified only*; the check that would settle it is in
  `docs/audits/2026-11-07-christie-slim-diagnosis.md` §10.4.

## How the tracked bytes came about

### The rebuild of 2026-11-13

Both Christie packs, for one line: `"runtime_verified"` in `BUILD_INFO.json` went from `true` to `false`
(above; [`DECISIONS.md`](DECISIONS.md), D31). Every other member of both zips is byte for byte what it was,
under the same names, in the same order, with the same zip fields:
[`christie-packs.txt`](../audits/2026-11-13-agent-entry/fixes/christie-packs.txt). Before: `Christie_LAS`
`1b486c42…`, `Christie_LAS_Slim` `79529a56…`. The slim zip kept its size to the byte, so only the hash tells
the two apart.

### The rebuild of 2026-11-12

Twelve packs were built again that day, so that their bytes no longer depend on the CPU that builds them: the
four LAS packs and the eight Miranda head packs. `lawson_las` and `Geralt_over_Rust` are byte for byte what
they were. Nothing that should show changed. The evidence is in
[`docs/audits/2026-11-12-cpu-independence.md`](../audits/2026-11-12-cpu-independence.md).

- **The four LAS packs:** every U and V direction of both models is now computed from the float32 positions,
  normals and UVs beside it, so their last digits moved, and where the UV map gives a vertex no handedness it
  is set by a rule: 1,492 vertices, of which 1,147 came out reversed against the previous build, whose signs rounding had chosen.
- **The two Miranda packs also:** `eyes` and `face_df`, now evaluated in float64 and cut off with a margin
  check. Decoded, 233 of the 262,144 texels of the eye's level 0 differ and 45 of the face's; 7,081 of the 4,194,304 texels of an L4D2 head atlas and 10,523 of a Romance one. What was drawn moved by one step at most; a block that holds such a texel is encoded again, so a decoded texel can move by more (11 steps at most in the eye).
- **The two Christie packs also:** two triangles in each index list changed places (they are the same
  triangles), and the fit figures in `BUILD_INFO.json` are written to six decimals.
- **The eight head packs:** the head atlas (the drawn eye; in the Romance packs also the nostril and lash
  pass) and the menu icon, which is a render of it.

Before: `Miranda_LAS` `5,919,788` B `f0e9c698…`, `Miranda_Busty_LAS` `6,321,190` B `5c802b25…`, `Christie_LAS`
`4,983,848` B `9e7c2d82…`, `Christie_LAS_Slim` `4,393,967` B `7a4d010c…`. The head packs' previous sizes and
hashes are in the audit.

### Miranda

Both packs were rebuilt on 2026-11-11 (before: `5,413,656` B, sha256 `e0e0c807…`, and `5,815,104` B,
`29644ddd…`). Three things changed, and nothing else in either zip. The evidence, the limits the textures
were held to and what they still miss are in
[`docs/audits/2026-11-11-miranda-mips-and-object.md`](../audits/2026-11-11-miranda-mips-and-object.md).

- **The face diffuse** has the source's eleven mip levels again, with the repaint (eye sockets, lash lines) in
  every one of them. Until then the build decoded the whole texture, repainted 2 % of it and encoded all of it
  again as a single level, with an encoder that wrote its alpha codes in the wrong order: the gloss of 3.9 %
  of the texels was off by two or more, the worst by 29 of 255. Now 1,731 of 87,383 blocks differ from the
  source's and every other byte is the source's.
- **The eye texture** has ten levels where it had one. Each is the area average of the drawn eye, taken as
  light, and encoded so that a block keeps its iris: the first two attempts at these levels had a grey iris at
  16x16, which is what is on screen from two to three metres.
- **`fps_miranda_busty.object`** lists `g_body` and `g_body_lod1`, the two drawables its model has. It used to
  list `g_head` and `g_head_lod1` as well. Both builders now write each `.object` from the model beside it.
- **The busty pack's menu icon** is a render of the model with its textures, so it moved with the face: 3.5 %
  of its texels differ.

### Head packs

The four **L4D2** packs were rebuilt on 2026-11-11 because their input changed: the head builder takes the
face from `dist/Miranda_LAS.zip`, and that face was fixed the same day (above). Each pack changed in two
members, its head atlas and its menu icon. In the atlas 17.5 % of level 0 differs, all of it in the face
quarter: against the face the Miranda build means, that quarter went from a mean CIEDE2000 of 1.42 to 0.57 and
its gloss from a mean error of 0.64 to 0.22 of 255 (measured on the Joy pack; the other three changed by the
same figures). The four **Romance** packs and `Geralt_over_Rust` do not read that file and are unchanged.

The four **L4D2** packs were rebuilt on 2026-11-05: the previously
tracked ones had been built against an older `dist/Miranda_LAS.zip` and carried
a scrambled diffuse-alpha plane in their `*_head_df.texture` (specular noise —
RGB bit-identical, previews byte-identical; see
[`docs/audits/2026-11-05-head-pack-audit.md`](../audits/2026-11-05-head-pack-audit.md)).
The 2026-11-07 rebuild adds `extend_neck_skirt()` to the **L4D2** head drawables
only - one extra ring 6.5 cm below the neck sheet's rim, tucked to 88 % and
shifted 0.5 cm forward, inside the torso: 4,402 -> 4,515 verts and 7,109 ->
7,321 tris (over Joy; 7,305 over Clover/Bonnie/Sydney), lowest point
z 149.48 -> 142.98. The four **Romance** packs are byte-identical to their
2026-11-05 state: on that rig the neck skin shares the `Hair` mesh with the
hair cap and the 1.5 mm flyaway wires, so the rim filter caught 741 hair edges
instead of ~145 and the wire pass that follows squashed the new ring into the
head (340 verts at z 168-170, 2,318 tris) - visible in the rendered previews as
a pale lump under the chin. `tests/test_pd2_las.py` pins the counts both ways.
On the Christie body the skirt changes no cell (`neck_junction.py --ab`: 0 of
2,401 throat cells change owner): it is insurance against a neckline wider than
Christie's, not a fix for item 7 of the diagnosis (the neck tonal split), which is still open -
`docs/audits/2026-11-07-christie-slim-diagnosis.md` §10.

### Christie

Built from `references/Christie.zip` (Dead or Alive 5) by `tools/pd2-las/build_christie_las.py`
(`--variant base|slim`). Slim is ×0.9 thinner in x/y, arm cross-sections ×0.80 plus the bicep tuck, height
unchanged, hands cut for in-game gloves with sleeves stretched deep past the wrist; `fix_arm_fits()`
translates the Arm/ForeArm/Hand fits so elbow, wrist and hand land exactly on the PD2 pivots. The separate
no-hands pack was removed (slim supersedes it). Detail and every measurement: `docs/pd2-las/CHRISTIE.md`.

- **2026-11-07, the elbow round** found that every posed elbow probe until then rotated the `ForeArm` about
  local X, which on this rig is a twist (the joint stays at its bind 72.1°); local Y is flexion. On the real
  axis the shipped sleeve crumpled when the bind elbow straightened to the idle's ~12°, so `trim_elbows` now
  also de-puffs the outer side of the bend, and a second pass the same day widened the Arm/ForeArm ramp to
  9+10 cm and pulled the flared cuff in (`taper_cuff`): worst edge shortens 3.12 → **1.83 cm**, compresses
  0.187 → **0.333** of bind length, joint thickness 7.18 → 6.69 cm, cuff mouth p90 6.37 → 5.39 cm, 0 inverted
  faces. Renders: `christie{,_slim}_{elbow_bend,elbow_idle,cuff}_before_after.png`, all fixed-frame per row
  from `tools/pd2-las/elbow_before_after.py`. Several later correctives were rendered and rejected. The final
  fix authors a 12° near-idle arm rest, reapplies the skin with seam-welded eight-pass Taubin relaxation and
  inversion damping, and propagates the custom rest worlds through both TPP and FPS inverse binds. A final
  tight-camera boundary repair closes the reviewed 50° near-sleeve gap on both arms; slim also has
  independent bounded multi-pose fold solutions. See `christie{,_slim}_idle_rest_outer_sheet.png` and
  `fps_christie{,_slim}_skel_{front,cuff}.png`.
- **2026-11-07, the sleeve seam.** `stitch_sleeve_seams` closed the sleeve's lengthwise slit and the 4-vertex
  elbow holes (0.00 cm² leaking on both sleeves of both packs *as built that day*, 0 orientation breaks, UVs
  byte-identical), and `unify_coincident_normals` gave every *interior* coincident vertex one normal (0
  interior divergent pairs, the border folds left alone). **The tracked slim pack is a later build and its
  sleeves are open again**, 6.70 and 4.95 cm² just past the elbow (the 2026-11-11 sleeve-seam entry of
  `MODLOG.md`). **Fixed on 2026-11-13** — the bridge faces reached no atom
  (`_insert_faces` dropped the cross-block triangles), and the residual left
  wedge is capped in the slim pack; both sleeves measure 0.00 cm2. The
  README's Next item and `DECISIONS.md`, D18, are updated to match; this
  pack still has no in-game sign-off.
- **2026-11-07, the sleeve gloss.** The mask was rebuilt: it is rasterised from the sleeve's own UV faces and
  clipped to that footprint, and only mip 0 is attenuated (the pyramid is regenerated from it). Leg-only UV
  coverage 3.2 % → **0.8 %** (151 → 33 faces, all on the boots, and those 33 are atlas sharing rather than
  mask reach); sleeve coverage 100 %, alpha inside/outside 5.51/11.25.
- **2026-11-07, the armpit notch** was measured and **closed as "not a defect"**: `cast_front` does not cull,
  so the wedge is empty space between the arm and the torso, the sleeve's armhole rim is coincident with the
  torso on its whole upper arc and free on the lower one — as an armhole is — and the 2B reference carries
  the same arm/body gap (8.2 cm² against 31.2). No build change.

## Dead ends — do not retry

- Raw frame-delta retargeting (all forms: `v·inv(S)`, shortest-arc,
  per-source Umeyama, unit-scaled deltas) → ribbon artifacts. Use
  `retarget_maps` as-is.
- One shared fit across both legs (`FIT_MIN_PAIRS` pair-count inheritance)
  → thighs collapse onto one point. Leg fits stay local/mirrored.
- Surgical replacement of shipped heister models — retired route, dead.
- `z.write()` for reproducible zips (embeds mtimes) — `las_pack.zip_pack`
  already solves this.
- Seam repair by *merging coincident vertex indices* → the two rims carry
  different UV islands, so the seam comes back as a texture tear. Weld the
  attributes (position/normal/weights), rewire the faces, keep the corners.
- Bridging the rims **before** welding them → zero-area triangles (a new
  triangle closes a pair that is already coincident at post-weld positions).
- Spanning a run gap of 3+ rim pairs while stitching → that "gap" is the
  armhole. The sleeve seam only ever jumps 1-2 rim pairs.

## Corrections

Claims that earlier copies of this page made, and that dated audits and `MODLOG.md` entries may still repeat.
Each was true of older bytes or of an older tree; none is true of what is tracked now. Measured 2026-11-11.

| Earlier claim | Measured on the tracked tree |
| --- | --- |
| "`s_body` draws 16 out-of-bounds triangles" in both Christie packs (2026-11-10) | none: no triangle of any drawable in the eight tracked models has a corner outside its atom's vertex block (`test_atoms_index_global_vertices_inside_their_own_block`) |
| "unit scale exactly 2.54" | nothing multiplies by 2.54. The per-bone fits carry the scale: by surface area the Miranda mesh is 2.90 × its source in third person and 2.35 × in first person |
| "shadow signed volume ≈ 81572 (tpp) / 1188 (fps)" | `Miranda_LAS`: 72,178.6 cm³ in third person. The first-person arms are an open mesh, so their figure (1,846.2) is not a volume and no test uses it |
| "boot soles ~12 cm below ground" | the lowest vertex of the `Miranda_LAS` body is at z = −0.75 cm |
| "a clean `bootstrap.sh` still yields a different base pack" (2026-11-05) | all four LAS packs rebuild to the tracked sha256, on any x86-64 Linux machine since 2026-11-12 (D26); the script itself is retired (D28) |
| "without the 2B templates `pytest` cannot collect"; "`pyflakes` is not clean"; "the worktree carries an uncommitted neck patch" (2026-11-10) | the suite collects and passes without the templates, with skips; `pyflakes um tools tests` is clean; the patch is part of the history |
| "fits more than 30° from the global rotation inherit the nearest kept ancestor" | that filter is not in the code: `DECISIONS.md`, D6 |
