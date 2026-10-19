# HANDOFF — read this first (5 minutes), then the linked docs

**Mission:** equipable full-body Miranda Lawson outfit for PAYDAY 2, delivered
as a Legendary Armour Skins (LAS) armor skin (the `2b.rar` product shape),
built reproducibly from `l4d2_miranda_lawson_1.zip` by `tools/pd2-las/`.

**State:** the pack is built and offline-verified to the limit of what a
sandbox can prove. Deliverable: `build/pd2-las/Miranda_LAS.zip` (drop the
inner `Miranda_LAS/` into PD2 `mods/`; needs BeardLib + LegendaryArmours).
Remaining: (1) in-game checklist run by the user, (2) ME2 redistribution
rights gate before any public release. Nothing else is pending.

## Quickstart

```bash
bash tools/pd2-las/bootstrap.sh     # venv + 2B templates + build + tests + lint
```

That is the whole recovery procedure too. The arena sandbox periodically
wipes `.venv`, `/tmp` and `build/` and rewinds local git to `66cfdb7` while
the worktree looks dirty — **the work is safe on the remote**. Recover with:

```bash
git fetch origin && git reset --hard origin/arena/136395ac-universal-modder
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
| `docs/audits/2026-10-19-las-guide-compliance.md` | every verification pass + 2B structural diff |
| `docs/pd2-las/in-game-checklist.md` | 18 items for the user-side game test |
| `knowledge/games/payday-2/las-armor-skin-outfit.md` | engine field notes + gotchas |
| `2b.rar`, `l4d2_miranda_lawson_1.zip` | reference pack + source (both tracked) |

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
- ≤3 weights/vertex, weights sum to 1; UVs stored as `1 − v_src` (p2mt
  convention) — source V is intentionally tiled, out-of-[0,1] is normal.
- Winding `(a,b,c)→(a,c,b)`, unit scale exactly 2.54; shadow signed
  volume ≈ 81572 (tpp) / 1188 (fps).
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
