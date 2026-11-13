# LAS outfit packs — audit, 2026-11-05

> Note of 2026-11-12: `tools/pd2-las/bootstrap.sh`, which this record names, was retired later. The environment is
> `make -sC tools/pd2-las env` (`recover_env.sh`): `docs/audits/2026-11-12-tool-merge.md`.

**Scope:** the newest addition to the LAS line — `dist/Miranda_LAS.zip` and its chest-morph sibling
`dist/Miranda_Busty_LAS.zip`, their `.sha256` sidecars, every `.model` / `.texture` /
`*.material_config` / `.object` / `.unit` / `hooks/*.lua` / `localization/english.txt` / `main.xml` entry
inside them, and the two builders (`tools/pd2-las/build_models.py`,
`tools/pd2-las/build_busty_variant.py` → `tools/pd2-las/bust_variant.py`).

**Method:** structural probes, not reading the builders first — zip entry inventory and timestamps, a full
`diesel_model` decode of all four shipped `.model` files with a write-back round-trip and a per-section
re-encode comparison, geometry invariants (normal length, winding/normal agreement, orientation breaks,
weight sums, bone-index range, atom slices, UV finiteness, duplicate triangles), BUILD_INFO
`payload_sha256` replay, `.material_config` → texture resolution, `main.xml` / hook / localization /
`.unit` / `.object` cross-references, and a **full rebuild of both packs** to test the reproducibility
claim. The 2B templates that the rebuild needs (`references/2b.rar`, 29 entries) were extracted with
`node-unrar-js` (the `bootstrap.sh` route), which is what unblocked the rebuild below.

Both packs: 20 entries, every entry timestamp `2020-01-01 00:00:00`, sidecars correct.

## Fixed

1. **`dist/Miranda_Busty_LAS.zip` was a stale artifact: 36 non-unit vertex normals.** The chest morph
   splits chest-band triangles and a split vertex's normal is the average of two unit normals, so it is
   *shorter* than one. `bust_variant.rebuild_normals` only renormalises inside the morph weight region, so
   12 vertices at the top of the chest band shipped short — **in `g_body`, `g_body_lod1` and `s_body` at
   once (3 × 12 = 36 normals per pack)**:

   | | shipped bytes | rebuilt |
   | --- | --- | --- |
   | non-unit drawable normals | **36** (12 per drawable) | **0** |
   | worst \|1 − \|n\|\| | **1.33 %** (\|n\| = 0.9867) | 2 × 10⁻⁸ |
   | vertex position of the 12 | `z ∈ [150.80, 150.97]`, `y ∈ [11.22, 11.44]`, `x ∈ [−2.22, 3.04]` | unchanged |

   The code fix (`subdivide_region` / `rebuild_normals`) had already landed; the *artifact* had not been
   rebuilt because the templates were missing from the sandbox, and `docs/pd2-las/CHEST-VARIANT.md`
   documented the rebuild as pending. It is now done:

   | | before | after |
   | --- | --- | --- |
   | `dist/Miranda_Busty_LAS.zip` | 5,815,039 B, `3043fcba330f53fb…` | **5,815,197 B, `91dbd3271de478b2…`** |

   What the rebuild changed, entry by entry (verified against the old bytes, drawable by drawable):

   * `miranda_busty.model` — `g_body`/`g_body_lod1`/`s_body`: **2,775 normals**, **2,776 `uvdir_u`** and
     **2,770 `uvdir_v`** differ (max Δ 0.167 / 0.351 / 0.208) and they are exactly the morphed band (rows
     5,645+ in `g_body`, 9,874+ in `s_body`); byte-identical everywhere else. Positions, `uv0`,
     blend indices/weights, headers and topology tails are bit-identical, so the silhouette and skinning are
     untouched — only shading and tangents in the reshaped chest.
   * `fps_miranda_busty.model` — **byte-identical** (the viewmodel never entered the morph region).
   * `miranda_busty.texture` — the 256×256 outfit icon regenerated from the same portrait: 336 of 65,536
     pixels differ, all in the chest window (`x 57–159`, `y 136–219`), max Δ 66/255. Compared side by side
     the two icons are visually indistinguishable.
   * `BUILD_INFO.json` — same size, `payload_sha256` of the model and the icon re-stamped; the `variant`
     measurements (`depth_gain_cm`, `front_y_max_cm`) are unchanged because no vertex moved.

   Two consecutive rebuilds are byte-identical (deterministic). `tests/test_bust_variant.py::
   test_shipped_pack_drawable_normals_are_unit_length` was added and **fails on the old bytes** ("12 of
   13166 normals are not unit length, |n| = 0.9867 … 1.0000") and passes on the new ones, so a stale
   artifact can no longer ship quietly. Sizes in `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` /
   `docs/pd2-las/HANDOFF.md` and the "rebuild pending" section of `docs/pd2-las/CHEST-VARIANT.md` were
   updated with it.

2. **The suite was only green without the 2B templates.** `tools/pd2-las/bootstrap.sh` promises "one
   command from a clean checkout to a built pack **and a green test suite**", but extracting
   `references/2b.rar` un-skips `tests/test_build_models.py::test_retarget_joint_errors_and_palettes`,
   which failed: `tpp RightArm: err=5.713cm` against a `< 5.0 cm` budget (same for `LeftArm`, 5.713 —
   perfectly symmetric). The upper-arm offset is *deliberate*: `retarget_maps` widens the shoulder
   "+1.2 cm outward from L4D2's UpperArm head" and steps the elbow 2.8 cm inward onto the hinge axis to
   avoid a bicep bulge and an outward elbow bow (`build_models.py`, the `M_menu` block), so the 5 cm bound
   was written before that change and nothing on a machine with the templates could ever satisfy it. For
   scale, the same probe gives Spine2 8.53 cm, Spine1 5.04, forearms 2.80, hands 2.43, head 2.02 (all
   inside their own budgets). Raised to 6.0 cm with the measurement and the reason in the docstring; the
   bound still trips on a retarget regression. Suite with the templates present: **526 passed,
   27 skipped** (before this sweep it was 525 passed + 1 failed, 27 skipped); without them 508 passed,
   45 skipped.

3. **`dist/Miranda_Busty_LAS.zip`: the keyhole lip was folded inside out.** The neckline flap over the
   sternum sits in the 0.19 → 0.008 dome-weight gradient (`z = 146.0 … 147.6`), so the morph shears it
   through its own 1 cm thickness. The local subdivision cut it into 992 faces (the stock mesh has 64
   there) with slivers down to 0.0019 cm² / 0.064 cm, and **10 of them had their winding reversed
   against the bind pose** — real folds, visible as a crumpled notch in the 30–45° chest views and a
   hard edge at 0°. The earlier normals rebuild missed it because it is geometric: 25 faces disagreed
   with their winding, but only the 10 whose triangles had turned through themselves were the defect.

   Fixed in `bust_variant.unfold_region()` (fairing of the folded vertices toward their neighbours'
   mean, iterated until no face is inverted) and rebuilt:

   | | before (`91dbd327…`, 5,815,197 B) | after (`d26b93e1…`, 5,815,206 B) |
   | --- | --- | --- |
   | `g_body` faces inverted against the bind pose | **10** | **0** |
   | faces whose normals disagree with their winding | 25 (18 in the lip) | 22 (15 in the lip) |
   | dihedral edges > 170° / > 175° | 7 / 4 | 4 / 3 |
   | vertices moved by the repair | — | 38, max 2.23 mm |
   | `volume_proxy` / `depth_gain_cm` / `width_cm` | 2,917.7 / 3.23 / [25.47, 25.48] | 2,917.8 / 3.23 / [25.47, 25.48] |

   Damping the displacement, vetoing the lip's subdivision and widening the keyhole box were all tried
   and rejected on the rendered result (each leaves a C0 step in a smooth surface); the numbers and the
   reasoning are in `docs/pd2-las/CHEST-VARIANT.md`. Rebuilds are deterministic (the same bytes come
   back every run), and `tests/test_bust_variant.py` pins `faces_inverted == 0` on the geometry path
   plus a unit test per half of the repair, so the fold cannot come back unnoticed. New preview sheets:
   `docs/previews/12_Miranda_Busty_LAS.png`, `13_Miranda_Busty_vs_LAS_chest.png` (0–90°, framing pulled
   back as the yaw widens) and `14_Miranda_Busty_vs_LAS_top_below.png` (58° above / 58° below).

   The overhead and underside views then showed the keyhole hem at `z = 146.2` coming out **bowed**: a
   straight garment edge in the stock mesh tilted 1.25 cm across 5 cm, because the field pushes it
   0.75 cm at the sternum and 2.0 cm at the cups. Fixed by band-limiting the forward push laterally
   across the hem (three taps 0.9 cm apart inside a smooth z envelope, correction gated by
   `lateral_gate` so it cannot leak into the sleeve — `test_built_variant_model…` caught that when the
   gate was missing). Hem-band dihedral mean/p90 9.6°/19.9° → 9.2°/18.4°, `depth_gain_cm` and
   `front_y_max_cm` unchanged. A follow-up pass then removed the hard step down the outside of the
   +x cup (see `CHEST-VARIANT.md`): the field is band-limited vertically across the hem and
   laterally across the vertical side seam, and no fairing pass is used. Final artifact:
   **5,815,174 B, `52f4c461a35e06320a3da6ec4af73774ccf8400c9994c80c97da0723658cd24a`**.

## Found, deliberately left

4. **Every authored `.model` carries its MATERIAL / MATERIAL_GROUP sections twice.** In
   `build_models.py` the authored material sections are collected into `new_mat_secs` and inserted before
   the object tree, but `flush_groups()` then emits `group_secs[gname]` *in full*, and each of those lists
   already starts with the same MATERIAL / MATERIAL_GROUP sections. The result is pairs of sections with
   **identical ids and identical payloads**:

   * a clean rebuild of `Miranda_LAS.zip`: 19 `MATERIAL` (7 template + 12 authored = 2 copies × 6) and
     13 `MATERIAL_GROUP` (7 + 6 = 2 × 3); the fix below would give 13 / 10;
   * the tracked `Miranda_LAS.zip` even carries a **legacy second set** on top (`10222` / `10232` / `10239`
     with materials `10221` / `10228` / `10229` / `10230` / `10231` / `10238`), 31 / 19 in total — it was
     built when the group list held two entries.

   Consequence: a clean `bootstrap.sh` run does **not** reproduce `dist/Miranda_LAS.zip`
   (`99b9ecc7…` → `02053dc7…`, 5,414,012 → 5,413,779 B, models 1,820,997 → 1,819,989 and 362,092 →
   361,724 B). Crucially the geometry is *not* affected: all five drawables of the rebuilt base model
   (`s_body`, `g_body`, `g_body_lod1`, `g_head`, `g_head_lod1`) have **byte-identical vertices, normals,
   UVs, weights and topology**, so the divergence is ~1 KB of dead duplicate sections and nothing else.

   One-line fix (`tools/pd2-las/build_models.py`, `flush_groups`):

   ```python
   for gname in groups:
       out_sections.extend(s for s in group_secs[gname]
                           if s.type not in (dm.MATERIAL, dm.MATERIAL_GROUP))
   ```

   **Why it is not applied here:** it changes the bytes of `dist/Miranda_LAS.zip` and
   `dist/Miranda_Busty_LAS.zip`, and the four `Miranda_L4D2_over_*` packs embed `miranda.model` verbatim
   from `dist/Miranda_LAS.zip`, so the fix re-ships six artifacts and every size and digest in the
   `AGENTS.md`/`HANDOFF.md` tables — a full release pass, not a sweep fix. Duplicate ids are harmless to
   the Diesel loader (it resolves an id to one section; the twins are identical), so nothing in game
   changes. Recorded here so the next full rebuild both applies the patch and expects the size drop.

## Checked and clean

* **Round-trip fidelity.** `ModelFile.read(bytes).write()` reproduces all four shipped models byte for
  byte (`miranda.model` 338 sections, `fps_miranda.model` 184, `miranda_busty.model` 320,
  `fps_miranda_busty.model` 174), and re-encoding every section individually is a no-op — including
  `OBJECT3D` (encoder output + payload tail).
* **Geometry invariants** (per v3/atoms drawable, both packs): winding/normal agreement 0.997–1.000,
  **0 orientation (shared-edge) breaks** anywhere, blend weights sum to 1, bone indices in palette range,
  atom slices inside the geometry, no duplicate/malformed triangles, all UVs finite.
* **Pack hygiene.** 20 entries each, `2020-01-01` timestamps everywhere, `.sha256` sidecars match the
  bytes, `BUILD_INFO.json` `payload_sha256` replays 19/19 for both packs (only `BUILD_INFO.json` itself is
  unlisted), `models_present: true`, `runtime_verified: false`.
* **Scaffolding parity.** `main.xml` (`name`, `image`, `Localization`/`Hooks`/`AddFiles` directories) is
  well-formed and points at files that exist; both hooks register the right `category` with matching
  `unit` / `fps_unit` paths; `localization/english.txt` keys follow the `bm_menu_<item>_armor_skins` /
  `bm_askn_<item>` pattern; `.unit` → `.object` → `.model` and `materials=` chains resolve;
  every `diffuse_texture` / `bump_normal_texture` in both `*_material_config` files resolves to a
  `.texture` inside the same pack (the busty pack never borrows a base-pack texture path).
* **Textures.** 8 per pack (outfit icon + body/face/head `_df`/`_nm` + eyes), all valid DDS, expected
  sizes (icon 256², body nm and eyes 512², body/face/head df and face/head nm 1024²), RGBA decode clean.
* **The base pack's bytes themselves:** `miranda.model` has no non-unit normals, no orientation breaks and
  no inaccessible atoms; `dist/Miranda_LAS.zip` was left exactly as tracked.

## Probes that produced false alarms (do not re-report)

* `bounds_min` / `bounds_max` / `bounding_radius` "mismatches" are a probe artefact of coordinate order;
  the shipped values are consistent with the vertices.
* A "blend weights do not sum to 1" hit on `c_block` is the template's culling cube: 8 vertices, 12
  triangles, axis-aligned normals (`±X`, `±Y`, no `±Z`), therefore 4 of 12 faces dot to exactly 0 and
  read as "disagreeing" in a winding test. Identical in both packs, invisible in game, not authored here.

## Rebuild

```bash
# templates (29 entries) — the step that was missing in the sandbox
bash tools/pd2-las/bootstrap.sh          # unpacks references/2b.rar via node-unrar-js, then builds

# minimal rebuild of just the variant, once the templates are at /tmp/2bsrc
.venv/bin/python tools/pd2-las/build_busty_variant.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
sha256sum -c dist/Miranda_Busty_LAS.zip.sha256
```

Do not re-run `build_models.py` as part of this: it overwrites `dist/Miranda_LAS.zip` with the duplicate-
section-free bytes described in finding 2, which changes the four L4D2 head packs on their next rebuild.
