# HANDOFF — read this first (5 minutes), then the linked docs

**Mission:** equipable full-body Miranda Lawson outfit for PAYDAY 2, delivered
as a Legendary Armour Skins (LAS) armor skin (the `2b.rar` product shape),
built reproducibly from `l4d2_miranda_lawson_1.zip` by `tools/pd2-las/`.

**State:** the packs are built and tracked in git. **Read the 2026-11-10 rows of
"Next actions" before touching anything** — five repair plans are unexecuted and
the worktree carries an uncommitted neck patch (see "Worktree state").
**Environment, measured 2026-11-10.** The sandbox wipes `.venv` and `/tmp` **between
sessions** — assume it did. Restore everything with one script:

```bash
bash tools/pd2-las/recover_env.sh --verify    # venv + 2B templates + suite
```

It is idempotent. Doing it by hand is the trap: without the 2B template in `/tmp/2bsrc`,
`pytest -q tests` cannot even *collect* (`test_render_mesh_skeleton.py:42` runs
`_templates()` at import) and 68 tests vanish.

| state of `/tmp/2bsrc` | command | result |
| --- | --- | --- |
| **extracted** | `pytest -q tests` | **645 passed, 30 skipped** (rc=0) |
| absent | `pytest -q tests` | **fails collection** (rc=2) |
| absent, worked around | `pytest -q tests --ignore=tests/test_render_mesh_skeleton.py` | 577 passed, 85 skipped |

**`pyflakes` is NOT clean right now** (measured 2026-11-10): 5 warnings — 4 introduced by the
uncommitted neck patch (`build_models.py:2027` redundant `import math`, `:2701` redundant
`import numpy as np`, `:2772` unused local `z`, and `tests/test_neck_three_zone.py:26` unused
`pytest`) and 1 pre-existing at `HEAD` (`tests/test_christie_las.py:462` unused `bm` import).
`HEAD` itself is clean. Fix the four in the necks patch when it is committed. `recover_env.sh` extracts the RAR with
`node-unrar-js` — **from a script file, never `node -e`**, which cannot resolve the
emscripten wasm sidecar and dies with a long stack trace.

Deliverables in **`dist/`**:
- `dist/Miranda_LAS.zip` (5,413,656 bytes, sha256 `e0e0c807…b87e`, also staged at `build/pd2-las/Miranda_LAS.zip`) — Full-body LAS outfit from L4D2.
- `dist/lawson_las.zip` (9,123,392 bytes, sha256 `9c8a28368862edccc8030a9df378766a804665a750a70954f47b4168a3ce4ad2`) — Full-body LAS outfit from ME2 Romance.
- `dist/Miranda_Busty_LAS.zip` (5,815,104 bytes, sha256 `29644ddd…05b`, also staged at `build/pd2-las/Miranda_Busty_LAS.zip`) — the same full-body LAS outfit with a
  **larger chest**; its own `LegendaryArmours.miranda_busty` entry, so it installs
  beside `Miranda_LAS.zip` instead of replacing it. Builder
  `tools/pd2-las/build_busty_variant.py`, morph `tools/pd2-las/bust_variant.py`,
  audit `docs/pd2-las/CHEST-VARIANT.md`, tests `tests/test_bust_variant.py`.
- Female heister head-replacement `mod_overrides` packages built by `tools/build_joy_head_mods.py`:
  - `dist/Miranda_L4D2_over_Joy.zip` (`10,600,653` B) & `dist/Miranda_Romance_over_Joy.zip` (`10,238,712` B)
  - `dist/Miranda_L4D2_over_Clover.zip` (`7,648,225` B) & `dist/Miranda_Romance_over_Clover.zip` (`7,297,599` B)
  - `dist/Miranda_L4D2_over_Bonnie.zip` (`8,160,274` B) & `dist/Miranda_Romance_over_Bonnie.zip` (`7,791,810` B)
  - `dist/Miranda_L4D2_over_Sydney.zip` (`7,147,084` B) & `dist/Miranda_Romance_over_Sydney.zip` (`6,805,595` B)


  All eight Miranda packs rebuild byte-identically (`tools/build_joy_head_mods.py`
  writes fixed `2020-01-01` zip timestamps, so `dist/*.zip.sha256` is a true
  build hash); `Geralt_over_Rust.zip` is unchanged by the rebuild. Current shas
  (2026-11-07, neck skirt — see the last paragraph of this item):

  - `Miranda_L4D2_over_Joy.zip` — 10,600,653 B, sha256 `2b19542b7e20770536091e750eb23cc460e7a28ddce572bde10055dbdbb7bc95`
  - `Miranda_L4D2_over_Clover.zip` — 7,648,225 B, sha256 `baa9b5cf5ea3575a5a08a368d7144b044ce434d63c30020fc1fd241de3519d0a`
  - `Miranda_L4D2_over_Bonnie.zip` — 8,160,274 B, sha256 `9cdb80c1fec899437ea1ef48ba6b832f85898121d0c0fa0ecbd3fee6d7164977`
  - `Miranda_L4D2_over_Sydney.zip` — 7,147,084 B, sha256 `d0c88d7ce45ed6b9ea5dbd39e975341b46203ded5e66aa5746fcbf533eb0f2ef`
  - `Miranda_Romance_over_Joy.zip` — 10,238,712 B, sha256 `c53953eabf0dd41021d92ce12c56c880df8432c25c4506199cfda03beee39e6d`
  - `Miranda_Romance_over_Clover.zip` — 7,297,599 B, sha256 `28a4d849a7a232ac8766345b3042b4b557a62cb41145e7fea74ca152b5548847`
  - `Miranda_Romance_over_Bonnie.zip` — 7,791,810 B, sha256 `d51d96640712eddeb1b6c97cc8776b56ada4438c1e553159b0ff1e74c4d71a27`
  - `Miranda_Romance_over_Sydney.zip` — 6,805,595 B, sha256 `b0df49097cd3800f83ae28a5388eadc62d717b2e9fe682d8534f36bdf5fd9d07`
  - `Geralt_over_Rust.zip` — 8,121,550 B, sha256 `0dfb58069f948795488f8a3fd6c3dadbdb935ebc2876df5467c0fa104bf0b65d`

  The four **L4D2** packs were rebuilt on 2026-11-05 as well: the previously
  tracked ones had been built against an older `dist/Miranda_LAS.zip` and carried
  a scrambled diffuse-alpha plane in their `*_head_df.texture` (specular noise —
  RGB bit-identical, previews byte-identical; see
  [`docs/audits/2026-11-05-head-pack-audit.md`](docs/audits/2026-11-05-head-pack-audit.md)).
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
  Christie's, not a fix for item 7, which is still open -
  `docs/audits/2026-11-07-christie-slim-diagnosis.md` §10.

  **Coverage:** Clover and Bonnie replace the heist, menu *and* Safe House
  (`*_chill`) models; Joy and Sydney replace the heist + menu models only, so
  their Safe House units keep the vanilla head. **In-game status 2026-11-05:**
  the four **L4D2** packs (`Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}.zip`)
  were tested in game by the user; the Romance variants and Geralt over Rust
  remain unverified — there is no checklist for the head packs (the LAS one is
  `docs/pd2-las/in-game-checklist.md`). **That test covers the 2026-11-05 bytes,
  not the ones tracked now:** the 2026-11-07 neck-skirt rebuild changed all four
  L4D2 packs (the Romance four came out byte-identical to 2026-11-05, see the
  paragraph below), so until someone looks at a throat again they are
  *offline-verified only*. The check that would settle it is in
  `docs/audits/2026-11-07-christie-slim-diagnosis.md` §10.4.

**Christie (DOA5), body-only:** `dist/Christie_LAS.zip` (4,983,848 B, sha256
`9e7c2d82…94fd95c`) and `dist/Christie_LAS_Slim.zip` (4,393,967 B, sha256
`7a4d010c…90a3e6f`) (+ `.sha256` sidecars) — built by
`tools/pd2-las/build_christie_las.py` (`--variant base|slim`; slim =
×0.9 thinner in x/y, arm cross-sections ×0.80 plus the bicep tuck, height
unchanged, hands cut for in-game gloves with sleeves stretched deep past the
wrist; `fix_arm_fits()` translates the Arm/ForeArm/Hand fits so
elbow/wrist/hand land exactly on the PD2 pivots) from
`references/Christie.zip`, headless LAS (`replace_body`, no `g_head`; the
slim variant cuts the wrists and ships the glove-adapter hook so in-game
gloves work). The separate no-hands pack was removed (slim supersedes it).
Base pack **tested in game 2026-11-05** (headless LAS confirmed;
texture gloss fixed via specular-alpha attenuation). **Slim pack seen in game
2026-11-10** in the [current 8-frame screenshot
batch](../audits/2026-11-10-christie-slim-screenshot-review.md), reported as the
de-spiked `7a4d010c…90a3e6f` bytes: the lobby silhouettes show no outward growth
at the inner elbow, but the rifle pose still shows a thin flap-like fold there,
and the rear-sleeve dark wedge and neck bands are still visible. That batch
replaced every archived screenshot; the 2026-11-07 and 11-frame sets are Git
history only, and their "not tested in game" status does not extend to this
build. The **2026-11-07 elbow
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
`fps_christie{,_slim}_skel_{front,cuff}.png`. Validation at that
point: 59 Christie tests and 613 tests overall (29 skipped); the suite is at 650 /
26 skipped today. Nothing built after 2026-11-05 has been in game yet, so an
in-game idle-elbow check is still recommended.
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

**Recovery.** The arena sandbox periodically wipes `.venv`, `/tmp` and `build/` and
rewinds local git while the worktree looks dirty — **the work is safe on the session
branch**. Recover with:

```bash
git fetch origin
git reset --hard origin/arena/282ccb75-universal-modder   # read the branch first, below
bash tools/pd2-las/recover_env.sh --verify
```

The branch name changes every session (`arena/<id>-universal-modder`); **read it from
`git rev-parse --abbrev-ref HEAD` rather than copying the line above**, which is only
correct for the session that wrote it.

`bootstrap.sh` still works, but it also builds every pack (slow) and its RAR step is the
fragile part; `recover_env.sh` does only the two things a wiped sandbox actually needs.

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

## Do-not-break invariants (each has a test — run `pytest -q tests`)

> **Caveat, 2026-11-10:** "has a test" does **not** mean "is protected". The list below is
> accurate about intent, but the atom-tiling invariant in particular has no containment check,
> and a tiling-preserving mutant that draws 16 out-of-bounds triangles passes 207 geometry
> tests. See the diagnostics plan before treating a green suite as evidence.

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

## Worktree state (2026-11-10 — check this before assuming a clean tree)

`git status` is **not clean**, and the suite numbers above depend on it:

| path | state | why it matters |
| --- | --- | --- |
| `tools/pd2-las/build_models.py` | modified **+209 / −53** | the three-zone neck work; **uncommitted** |
| `tests/test_neck.py` | modified +14 / −6 | pairs with the above |
| `tests/test_neck_three_zone.py` | **untracked**, 8 tests | part of the 645/577 counts |
| `docs/audits/2026-11-09-neck-arm/` | untracked | reference renders |
| nine `docs/audits/*.md` | untracked | the repair plans referenced throughout |

**What the neck patch does and does not affect** (measured 2026-11-10, worth knowing before you
commit it):

* It rewrites `slim_neck` and `cap_holes` and adds three helpers (`_top_rim`, `_ring_plane`,
  `_planar_diameter`).
* **Both runnable builders are byte-identical with it applied.** `build_christie_las --variant
  slim` still produces sha256 `5e55745f…b4d`, and `build_busty_variant` still produces
  `52f4c461…` — both equal to the tracked packs. So the patch changes **no shipped artefact**.
* That is because its **only caller is `build_skyrim_outfit.py:313` / `:413`**, and the Skyrim
  reference zips are absent (`references/1.zip`–`5.zip`). **The patch is therefore never
  exercised by a build in this checkout** — only by 16 unit tests (`tests/test_neck.py`,
  `tests/test_neck_three_zone.py`), which do call `slim_neck` directly.
* Consequence: it is safe to commit (it cannot alter `dist/`), but do not claim it is
  *build-verified*. Its end-to-end validation needs the Skyrim sources.

**Do not `git checkout .` or `git stash` to clean up** — that deletes the only copy of
`tests/test_neck_three_zone.py` (it is untracked, so git cannot restore it) and drops the
neck patch. Commit or stash deliberately, and read the neck plan first.

**`dist/` IS rebuildable, and the build is byte-reproducible** (measured 2026-11-10, correcting an
earlier claim in this file that it was not):

```bash
.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b" \
    --out /tmp/rebuild --dist /tmp/rebuild-dist
# -> sha256 7a4d010c7e15e92615cf3aedcbbc11ce69781e4b15ab8a461e4d0a88190a3e6f
#    identical to the tracked dist/Christie_LAS_Slim.zip, dist/ left clean
```

`references/Christie.zip` and `references/2b.rar` are both tracked, so nothing external is
missing. **Always pass `--dist /tmp/...`** — `--out` alone still writes the zip into `dist/`.
If you do mutate or overwrite a shipped pack, restore the bytes and verify the sha256: three
tests (`test_sha256_sidecar`, `test_build_info_records_headless_and_provenance`,
`test_handoff_and_agents_quote_the_tracked_pack_bytes`) fail on any rezip, which looks like a
caught bug but is only byte drift.

Still out of reach: the **Skyrim** route (`references/1.zip`–`5.zip` absent) and the ME2/L4D2
packs' own sources. This rebuild claim covers **Christie only**, which is what every open repair
plan touches.

## Next actions, in order

### 2026-11-11 — repair plans executed (deleted per plan convention)

Each lives in `docs/audits/` and is self-contained (root cause, exact `file:line`, phases,
acceptance criteria). Plans executed and deleted; see `tools/pd2-las/MODLOG.md` for results.

0. **Extract the 2B fixture** (`bash tools/pd2-las/bootstrap.sh`). Do this before anything else —
   every measurement was taken against a half-dark suite without it.

Executed plans (deleted from `docs/audits/`):
- `2026-11-07-christie-forearm-normals-and-seam-repair-plan.md` — forearm LBS normal rotation +
  `stitch_sleeve_seams` fixes (cuff bulkheads, inverted caps, UV continuation). Packs rebuilt.
- `2026-11-09-uv-seam-normal-splits-tangent-basis-repair-plan.md` — orthonormal tangent basis +
  3D-manifold seam normal unification (87/128 groups). Packs rebuilt.
- `2026-11-10-diagnostics-and-tests-masking-repair-plan.md` — skip budget tool, `stage()` error
  detail, field-name trap, bootstrap extractor fix.
- `2026-11-07-christie-normal-maps-and-dxt5-mip-repair-plan.md` — executed previously.
- `2026-11-07-christie-sleeve-uv-mask-repair-plan.md` — executed previously.
- `2026-11-09-arm-skin-stub-glove-adapter-poke-through-plan.md` — executed previously.
- `2026-11-09-neck-three-zone-repair-plan.md` — executed previously.
- `2026-11-10-s-body-atom-oob-fps-elbow-cuff-repair-plan.md` — NOT yet executed (active defect:
  `s_body` draws 16 OOB triangles in both packs).

Then, unchanged from before the 2026-11-10 round:

6. User runs `docs/pd2-las/in-game-checklist.md` against
   `build/pd2-las/Miranda_LAS.zip` (or the freshly bootstrapped one —
   byte-identical). Known watch items: normal-map Y+ (flip green if
   lighting inverts), contour silhouette behind walls, boot soles ~12 cm
   below ground.
7. Fix whatever the checklist finds (expect small touch-ups, not redesign).
8. **Release gate:** resolve ME2 asset redistribution rights. Until then the
   pack is for private testing only.

Offline confidence was rated 8/10 for "loads and displays correctly"
(structural parity with the working 2B pack is the main reason; never
having launched the game is the main doubt).
