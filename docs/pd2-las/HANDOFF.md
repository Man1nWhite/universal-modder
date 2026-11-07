# HANDOFF — read this first (5 minutes), then the linked docs

**Mission:** equipable full-body Miranda Lawson outfit for PAYDAY 2, delivered
as a Legendary Armour Skins (LAS) armor skin (the `2b.rar` product shape),
built reproducibly from `l4d2_miranda_lawson_1.zip` by `tools/pd2-las/`.

**State:** the pack is built, game-tested, tracked in git, and offline-verified.
Deliverables in **`dist/`**:
- `dist/Miranda_LAS.zip` (5,414,012 bytes, sha256 `99b9ecc7869b0e9acae3a283c5571e6a459eb318c022144b9f4e60815d216c65`, also staged at `build/pd2-las/Miranda_LAS.zip`) — Full-body LAS outfit from L4D2.
- `dist/lawson_las.zip` (9,123,392 bytes, sha256 `9c8a28368862edccc8030a9df378766a804665a750a70954f47b4168a3ce4ad2`) — Full-body LAS outfit from ME2 Romance.
- `dist/Miranda_Busty_LAS.zip` (5,815,174 bytes, sha256 `52f4c461a35e06320a3da6ec4af73774ccf8400c9994c80c97da0723658cd24a`) — the same full-body LAS outfit with a
  **larger chest**; its own `LegendaryArmours.miranda_busty` entry, so it installs
  beside `Miranda_LAS.zip` instead of replacing it. Builder
  `tools/pd2-las/build_busty_variant.py`, morph `tools/pd2-las/bust_variant.py`,
  audit `docs/pd2-las/CHEST-VARIANT.md`, tests `tests/test_bust_variant.py`.
- Female heister head-replacement `mod_overrides` packages built by `tools/build_joy_head_mods.py`:
  - `dist/Miranda_L4D2_over_Joy.zip` (`10,600,653` B) & `dist/Miranda_Romance_over_Joy.zip` (`10,307,642` B)
  - `dist/Miranda_L4D2_over_Clover.zip` (`7,648,225` B) & `dist/Miranda_Romance_over_Clover.zip` (`7,349,388` B)
  - `dist/Miranda_L4D2_over_Bonnie.zip` (`8,160,274` B) & `dist/Miranda_Romance_over_Bonnie.zip` (`7,877,915` B)
  - `dist/Miranda_L4D2_over_Sydney.zip` (`7,147,084` B) & `dist/Miranda_Romance_over_Sydney.zip` (`6,840,385` B)


  All eight Miranda packs rebuild byte-identically (`tools/build_joy_head_mods.py`
  writes fixed `2020-01-01` zip timestamps, so `dist/*.zip.sha256` is a true
  build hash); `Geralt_over_Rust.zip` is unchanged by the rebuild. Current shas
  (2026-11-07, neck skirt — see the last paragraph of this item):

  - `Miranda_L4D2_over_Joy.zip` — 10,600,653 B, sha256 `2b19542b7e20770536091e750eb23cc460e7a28ddce572bde10055dbdbb7bc95`
  - `Miranda_L4D2_over_Clover.zip` — 7,648,225 B, sha256 `baa9b5cf5ea3575a5a08a368d7144b044ce434d63c30020fc1fd241de3519d0a`
  - `Miranda_L4D2_over_Bonnie.zip` — 8,160,274 B, sha256 `9cdb80c1fec899437ea1ef48ba6b832f85898121d0c0fa0ecbd3fee6d7164977`
  - `Miranda_L4D2_over_Sydney.zip` — 7,147,084 B, sha256 `d0c88d7ce45ed6b9ea5dbd39e975341b46203ded5e66aa5746fcbf533eb0f2ef`
  - `Miranda_Romance_over_Joy.zip` — 10,307,642 B, sha256 `73a76496a344fffde7f174a0f2d267dc77d1531d9af1596fdf5e8e55ed85a686`
  - `Miranda_Romance_over_Clover.zip` — 7,349,388 B, sha256 `9f0488fd4aeeba4da10ccd021740b829cad6f16c1cb21e95e73489dad3c51a74`
  - `Miranda_Romance_over_Bonnie.zip` — 7,877,915 B, sha256 `b4bea22043bc674313697433dcc1c20c46fdb8dde000f519a1576283dd2e76fd`
  - `Miranda_Romance_over_Sydney.zip` — 6,840,385 B, sha256 `9e87a2255aa8d6f070452b7aea3a6e3c02917da4c8bf4188bbcef55accf56d3c`
  - `Geralt_over_Rust.zip` — 8,121,550 B, sha256 `0dfb58069f948795488f8a3fd6c3dadbdb935ebc2876df5467c0fa104bf0b65d`

  The four **L4D2** packs were rebuilt on 2026-11-05 as well: the previously
  tracked ones had been built against an older `dist/Miranda_LAS.zip` and carried
  a scrambled diffuse-alpha plane in their `*_head_df.texture` (specular noise —
  RGB bit-identical, previews byte-identical; see
  [`docs/audits/2026-11-05-head-pack-audit.md`](docs/audits/2026-11-05-head-pack-audit.md)).
  The 2026-11-07 rebuild adds `extend_neck_skirt()` to every Miranda head's neck
  sheet — one extra ring 6.5 cm below the rim, tucked to 88 % and shifted 0.5 cm
  forward, inside the torso: 4,402 → 4,515 verts, 7,109 → 7,321 tris, lowest
  point z 149.48 → 142.98. It changes no pixel on the Christie body (the junction
  renders are byte-identical before and after) and is there so the head's open
  end cannot surface on a body whose neckline is wider than Christie's. Item 7
  itself is still open — `docs/audits/2026-11-07-christie-slim-diagnosis.md` §10.
  **Coverage:** Clover and Bonnie replace the heist, menu *and* Safe House
  (`*_chill`) models; Joy and Sydney replace the heist + menu models only, so
  their Safe House units keep the vanilla head. **In-game status 2026-11-05:**
  the four **L4D2** packs (`Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}.zip`)
  are tested in game by the user; the Romance variants and Geralt over Rust
  remain unverified — there is no checklist for the head packs (the LAS one is
  `docs/pd2-las/in-game-checklist.md`).

**Christie (DOA5), body-only:** `dist/Christie_LAS.zip` (4,794,618 B, sha256
`c57edbba…b1f76`) and `dist/Christie_LAS_Slim.zip` (4,222,761 B, sha256
`5e55745f…170b4`) (+ `.sha256` sidecars) — built by
`tools/pd2-las/build_christie_las.py` (`--variant base|slim`; slim =
×0.9 thinner in x/y, arm cross-sections ×0.80 plus the bicep tuck, height
unchanged, hands cut for in-game gloves with sleeves stretched deep past the
wrist; `fix_arm_fits()` translates the Arm/ForeArm/Hand fits so
elbow/wrist/hand land exactly on the PD2 pivots) from
`references/Christie.zip`, headless LAS (`replace_body`, no `g_head`; the
slim variant cuts the wrists and ships the glove-adapter hook so in-game
gloves work). The separate no-hands pack was removed (slim supersedes it).
Base pack **tested in game 2026-11-05** (headless LAS confirmed;
texture gloss fixed via specular-alpha attenuation). The **2026-11-07 elbow
round** found that every posed elbow probe until then rotated the `ForeArm`
about local X, which on this rig is a twist (the joint stays at its bind
72.1°); local Y is flexion. On the real axis the shipped sleeve crumpled when
the bind elbow straightened to the idle's ~12°, so `trim_elbows` now also
de-puffs the outer side of the bend, and a second pass the same day widened
the Arm/ForeArm ramp to 9+10 cm and pulled the flared cuff in
(`taper_cuff`): worst edge shortens 3.12 → **1.83 cm**, compresses
0.187 → **0.333** of bind length, joint thickness 7.18 → 6.69 cm, cuff mouth
p90 6.37 → 5.39 cm, 0 inverted faces. Renders:
`christie{,_slim}_{elbow_bend,elbow_idle,cuff}_before_after.png`, all fixed-
frame per row from `tools/pd2-las/elbow_before_after.py`. Several later
correctives were rendered and rejected. The final fix authors a 12° near-idle
arm rest, reapplies the skin with seam-welded eight-pass Taubin relaxation and
inversion damping, and propagates the custom rest worlds through both TPP and
FPS inverse binds. A final tight-camera boundary repair closes the reviewed 50°
near-sleeve gap on both arms; slim also has independent bounded multi-pose fold
solutions. Final isolated outer sheets, cuff/idle comparisons and actual FPS
renders were inspected for base and slim. See
`christie{,_slim}_idle_rest_outer_sheet.png` and
`fps_christie{,_slim}_skel_{front,cuff}.png`. Validation: 59 Christie tests
and 613 tests overall passed (29 skipped). Nothing built after 2026-11-05 has
been in game yet, so an in-game idle-elbow check is still recommended.
The same day, `stitch_sleeve_seams` closed the sleeve's lengthwise slit and the
4-vertex elbow holes (0.00 cm² leaking on both sleeves of both packs, 0
orientation breaks, UVs byte-identical), and `unify_coincident_normals` gave
every *interior* coincident vertex one normal (0 interior divergent pairs, the
border folds left alone); see "2026-11-07 sleeve seam stitch" / "seam normals" in
`CHRISTIE.md`, §8-§9 of the diagnosis audit and the corrected screenshot review.
The same day the sleeve-gloss mask was rebuilt: it is now rasterised from the
sleeve's own UV faces and clipped to that footprint, and only mip 0 is
attenuated (the pyramid is regenerated from it). Leg-only UV coverage 3.2 % →
**0.8 %** (151 → 33 faces, all on the boots, and those 33 are atlas sharing
rather than mask reach); sleeve coverage 100 %, alpha inside/outside 5.51/11.25.
Work-order item 3 (the armpit notch) was measured and **closed as "not a
defect"**: `cast_front` does not cull, so the wedge is empty space between the
arm and the torso, the sleeve's armhole rim is coincident with the torso on its
whole upper arc and free on the lower one — as an armhole is — and the 2B
reference carries the same arm/body gap (8.2 cm² against 31.2). No build change.
67 Christie tests now, 635 overall.
See `docs/pd2-las/CHRISTIE.md` ("The elbow, measured on the elbow's own
axis"). Tests: `tests/test_christie_las.py`.

## Quickstart

```bash
bash tools/pd2-las/bootstrap.sh     # venv + 2B templates + build + tests + lint
```

That is the whole recovery procedure too. The arena sandbox periodically
wipes `.venv`, `/tmp` and `build/` and rewinds local git to `0f1d838` while
the worktree looks dirty — **the work is safe on the remote**. Recover with:

```bash
git fetch origin && git reset --hard origin/arena/ab9ca3e6-universal-modder
bash tools/pd2-las/bootstrap.sh
```

Commit and push early and often; everything through the latest sweep is on
the remote branch.

## Where things live

| Path | What |
| --- | --- |
| `tools/pd2-las/README.md` | the pipeline manual (read next) |
| `tools/pd2-las/build_models.py` | the build: retarget + geometry + pack |
| `tools/pd2-las/diesel_model.py` | verified Diesel `.model` codec (byte-exact) |
| `tools/pd2-port/STATUS.md` | the sibling ME2-route handoff (read to avoid duplication) |
| `docs/audits/2026-10-19-las-guide-compliance.md` | every verification pass + 2B structural diff + cross-route winding audit |
| `docs/pd2-las/in-game-checklist.md` | 18 items for the user-side game test |
| `knowledge/games/payday-2/las-armor-skin-outfit.md` | engine field notes + gotchas |
| `references/2b.rar`, `models/l4d2_miranda_lawson_1.zip` | reference pack + source (both tracked) |

## Pipeline in one breath

`l4d2 zip → VpkArchive → source_model (MDL/VVD/VTX) → transfer_group +
retarget_maps (divergence-filter Umeyama onto the 2B skeleton) →
diesel_model.assemble (template sections, mesh blocks replaced) →
las_pack.write_pack + zip → Miranda_LAS.zip`. Textures: VTF→DDS via
`vtf.py`/`dds_encode.py`. Provenance and hashes in `BUILD_INFO.json`
(payload, source zip, 2B template inputs).

## Do-not-break invariants (each has a test — run `pytest -q tests/`)

- Models byte-round-trip through `ModelFile.read → write`; builds are
  byte-reproducible (zip uses fixed 2020-01-01 timestamps).
  Caveat (2026-11-05): a clean `bootstrap.sh` still yields a *different*
  base pack, sha `02053dc7…` where the tracked one is `99b9ecc7…`, because
  `flush_groups` emits the authored MATERIAL / MATERIAL_GROUP sections a second
  time — the tracked base pack even carries a legacy extra set (18 redundant
  sections, ~1 KB, geometry byte-identical). Fix and numbers in
  `docs/audits/2026-11-05-las-pack-audit.md`; apply it on the next full
  rebuild — it re-ships both LAS packs and the four L4D2 head packs.
- ≤3 weights/vertex, weights sum to 1; UVs stored as `1 − v_src` (p2mt
  convention) — source V is intentionally tiled, out-of-[0,1] is normal.
- Winding `(a,b,c)→(a,c,b)`, unit scale exactly 2.54; shadow signed
  volume ≈ 81572 (tpp) / 1188 (fps); **0 edge-orientation breaks**
  (`build_models.orientation_breaks`) — the exact hole-by-culling test on
  these welded meshes. Do not apply the ME2 line's vertex-normal
  flip-repair here: it misreads skinned normal blending and *creates*
  breaks (analysis in the audit doc).
- Retarget: one Umeyama fit per target bone, hand-subtree shares the palm
  fit, fits >30° from global rotation inherit the nearest kept ancestor.
- Material names in `*.material_config` must hash64-match the model's
  materials; fps `mtr_body` needs `DEPTH_SCALING`; TPP skins carry the
  guide's `CONTOUR` + `unique="true"` + contour variables.
- `assemble_model` drops only the `AUTHOR` section; everything else in the
  2B template (including fps `c_block`'s materials) is kept.

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

## Environment traps (already fixed — know them)

- `VpkArchive.from_zip(path_str, vpk_name)` takes a path, not a ZipFile.
- `ModelFile.read(data)`; `SubMesh.triangle_indices` is global; geometry
  per-group lookup uses `hash64(f"{g}.DieselGeometry")`.
- `skeleton_map.json` schema: `map` / `drop.patterns` / `target_only.names`.
- Unmapped source bones fold into the nearest mapped ancestor (facial
  flex bones and `hlp_*`/`ValveBiped.*` helpers are covered this way).

## Next actions, in order

1. User runs `docs/pd2-las/in-game-checklist.md` against
   `build/pd2-las/Miranda_LAS.zip` (or the freshly bootstrapped one —
   byte-identical). Known watch items: normal-map Y+ (flip green if
   lighting inverts), contour silhouette behind walls, boot soles ~12 cm
   below ground.
2. Fix whatever the checklist finds (expect small touch-ups, not redesign).
3. **Release gate:** resolve ME2 asset redistribution rights. Until then the
   pack is for private testing only.

Offline confidence was rated 8/10 for "loads and displays correctly"
(structural parity with the working 2B pack is the main reason; never
having launched the game is the main doubt).
