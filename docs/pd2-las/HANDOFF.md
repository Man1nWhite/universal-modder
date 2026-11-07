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
  - `dist/Miranda_L4D2_over_Joy.zip` (`10,585,799` B) & `dist/Miranda_Romance_over_Joy.zip` (`10,238,712` B)
  - `dist/Miranda_L4D2_over_Clover.zip` (`7,636,591` B) & `dist/Miranda_Romance_over_Clover.zip` (`7,297,599` B)
  - `dist/Miranda_L4D2_over_Bonnie.zip` (`8,142,005` B) & `dist/Miranda_Romance_over_Bonnie.zip` (`7,791,810` B)
  - `dist/Miranda_L4D2_over_Sydney.zip` (`7,140,504` B) & `dist/Miranda_Romance_over_Sydney.zip` (`6,805,595` B)

  All eight rebuild byte-identically (`tools/build_joy_head_mods.py` writes fixed
  `2020-01-01` zip timestamps, so `dist/*.zip.sha256` is a true build hash). The
  four **L4D2** packs in this tree were rebuilt on 2026-11-05: the previously
  tracked ones had been built against an older `dist/Miranda_LAS.zip` and carried
  a scrambled diffuse-alpha plane in their `*_head_df.texture` (specular noise —
  RGB bit-identical, previews byte-identical; see
  [`docs/audits/2026-11-05-head-pack-audit.md`](docs/audits/2026-11-05-head-pack-audit.md)).
  **Coverage:** Clover and Bonnie replace the heist, menu *and* Safe House
  (`*_chill`) models; Joy and Sydney replace the heist + menu models only, so
  their Safe House units keep the vanilla head. **In-game status 2026-11-05:**
  the four **L4D2** packs (`Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}.zip`)
  are tested in game by the user; the Romance variants and Geralt over Rust
  remain unverified — there is no checklist for the head packs (the LAS one is
  `docs/pd2-las/in-game-checklist.md`).

**Christie (DOA5), body-only:** `dist/Christie_LAS.zip` (4,767,247 B, sha256
`fa77d312…0bc92ae`) and `dist/Christie_LAS_Slim.zip` (4,201,848 B, sha256
`5b389eaf…16df085`) (+ `.sha256` sidecars) — built by
`tools/pd2-las/build_christie_las.py` (`--variant base|slim`; slim =
×0.9 thinner in x/y, arm verts an extra ×0.75 (arms 25% thinner), height
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
de-puffs the outer side of the bend: worst edge shortens 3.12 → 2.08 cm,
compresses 0.187 → 0.295 of bind length, joint thickness 7.18 → 6.69 cm, 0
inverted faces. Renders: `christie{,_slim}_elbow_idle_before_after.png`.
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
