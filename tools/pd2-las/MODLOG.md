# PAYDAY 2 LAS — review journal

## 2026-11-11 — Christie forearm normals + sleeve seam repair (executed plan)

- Executed `docs/audits/2026-11-07-christie-forearm-normals-and-seam-repair-plan.md`
  (then deleted per plan convention).
- **Forearm normal rotation:** `rebind_arms_at_idle` now rotates stored normals
  by the same LBS skinning matrix that poses the vertices
  (covector transform `n' = n @ (R^-1)^T`), fixing dark rear-forearm shading
  patches where `fn · vn` was 0.29 → ≥ 0.90 on `mtr_c02_01` rear forearms.
- **`stitch_sleeve_seams`:** `min_normal_dot` 0.2→0.3; surface-tangency filter
  rejects radial cuff-vent/lining bulkheads (chord/normal angle > 0.45); quad
  loft scored by worst face/vertex-normal alignment (best_score ≥ 0.5) rejects
  inside-out caps; short-loop fill gated on connected-component tri count ≥ 32
  (rejects 6–9 tri decorative cuff patches, keeps the 698-tri pinhole); UV
  continuation clones wrapped bridge vertices (Δu 0.20 → < 0.08). Only the
  genuine inner-elbow pinhole is now filled (1 hole vs 4).
- **Packs rebuilt:** `Christie_LAS.zip` 4,981,789 B sha256
  `196606c0…3d5e24`; `Christie_LAS_Slim.zip` 4,392,046 B sha256
  `ee85fc15…5bd7b8`. `.sha256` sidecars regenerated. `HANDOFF.md` and
  `CHRISTIE.md` sizes/hashes updated.
- Seam unification counts: slim 348 copies over 87 groups, base 512 over 128
  groups; interior divergent pairs 0 on both; border pairs untouched (480/836).
- Validation: 644 passed, 30 skipped, 2 failed —
  `test_sleeve_tube_is_closed_along_its_length` for slim remains at 6.70/4.95
  cm² leak (rims in z 125.3–126.6 have no paired vertices to bridge; a
  geometry limitation beyond stitching). All other Christie tests pass.
- New files: `tools/pd2-las/extract_2b.py`, `tools/pd2-port/check_skip_budget.py`.
- `bootstrap.sh` now uses `extract_2b.py` (file-based, fixes `node -e` wasm
  `__dirname` failure) instead of broken inline `node -e` RAR extraction.

## 2026-11-07 — replace Christie Slim screenshots and reassess appearance

- Request: replace the archived screenshots with 15 new uploads, then analyze
  issues. This is an evidence/documentation update, not a model-fix round.
- Replaced the former 11 PNGs in `docs/pd2-las/screenshots/` with the 15 supplied
  originals, byte-for-byte in upload order (8 lobby, 7 menu/rifle). Added a
  SHA-256/dimensions/upload mapping in `manifest.json`; updated the index.
- Installed pack hash was not supplied. The local ZIP remains
  `5e55745f…70b4d`; do not assign that hash to the captures by assumption.
- Rewrote `docs/audits/2026-11-07-christie-slim-screenshot-review.md` for this
  batch. Open visual findings: dark rear forearm patches, hard neck bands,
  coarse suit tonal patches, angular elbow folds, rough cuff/glove junction.
  Evidence coordinates are in the new PNGs' native pixel spaces. Appearance
  is separated from speculative geometry/material/head/glove ownership.
- Marked the previous numerical recheck and structural diagnosis as historical
  relative to the replaced batch, and linked the current review from
  `docs/pd2-las/CHRISTIE.md`. The earlier screenshots/review remain in Git history.
- Validation: 15/15 archive files match the supplied originals; Christie and
  seam-normal regressions 78 passed. Current Slim radial sleeve probes read
  0.00 cm² leakage on each arm. Neither result clears the visible render issues.
- No source model, texture, Lua hook or distributable ZIP changed. Temporary
  native crops/nearest-neighbour edge-inspection aids are in ignored `build/`.
- Next: match the installed hash and active head/glove setup, isolate rear-arm
  shading and neck surface ownership, then test suit channels and deformation
  in controlled in-game comparisons before making a corrective build.

## 2026-11-10 — verification-layer audit: five repair plans, one active test mask

- Request: "make a detailed plan for bugs in diagnostics & tests that masked these
  issues" — an audit of the verification layer, not a geometry round. Documents only;
  **no source model, texture, Lua hook or distributable ZIP changed.**
- Wrote five agent-executable repair plans in `docs/audits/`: forearm normals,
  normal maps/DXT5, sleeve UV mask, three-zone neck, arm-stub/glove adapter, UV-seam
  splits + tangent basis, `s_body` atom OOB, and finally the diagnostics audit itself.
- **Main finding.** A faithful mutant of `Christie_LAS_Slim.zip` — 4 triangles moved
  from atom 1 into atom 0, tiling preserved exactly as in the shipped defect — draws
  16 out-of-bounds triangles. The full geometry suite (207 tests, run *with* the 2B
  fixture extracted) passes it. Every failure it produces is bookkeeping: a byte
  count, a sha256, a BUILD_INFO field. `atom_problems()` returns `[]` because it
  checks tiling only and never tests an index against a block bound.
- `check_test_suite_mutations.py` is green (5/5) but carries **zero** atom, tangent or
  seam mutations and only ever touches `dist/lawson_las.zip`. Green proves nothing here.
- The shipped defect is still live: both Christie packs draw **16 OOB triangles** from
  `s_body`, max reach past its own vertex block 920 (base) / 730 (slim); `g_body` 0.
- **Corrections made against the first draft** (recorded because they changed the
  conclusion): the 2B fixture turns out to be *obtainable* — `bootstrap.sh` uses
  `node-unrar-js`, not a system `unrar`, and extraction works here. With it present the
  suite is `645 passed, 30 skipped`, all **67** Christie tests pass, and `pytest -q tests`
  collects cleanly. So the 37-Test skip (M1) and the `check_all.py --full` failure (M5)
  are **the same fixable fixture problem**, and neither is currently hiding a defect.
  `assert report["border"] > 300` (M3) has 131–506 pairs of slack and does not block the
  seam fix either. **M2 — the absent containment check — is the one active mask.**
- Also found: `pytest.importorskip` at module scope in `test_glove_behavior_lua.py:36`
  deletes 7 tests but reports a single skip, which is why the suite total does not
  reconcile (661 collected, 662 outcomes).
- Validation: `577 passed, 85 skipped` with `--ignore=tests/test_render_mesh_skeleton.py`;
  `645 passed, 30 skipped` with the fixture. All 19 `file:line` citations in the new
  document resolve at `HEAD`. `dist/Christie_LAS_Slim.zip` was swapped for the mutant and
  restored byte-exactly (4,222,761 B, sha256 `5e55745f…b4d`, sidecar agrees).
- Also updated `docs/pd2-las/HANDOFF.md`: corrected the stale `650 passed / 26 skipped`
  claim, replaced the recovery command that pointed at a dead branch
  (`arena/ab9ca3e6-…`), and documented the uncommitted neck patch and the untracked
  `tests/test_neck_three_zone.py`.

## 2026-11-10 (later) — environment reset; the build is reproducible after all

- The sandbox wiped `.venv` and `/tmp/2bsrc` between rounds, exactly as `HANDOFF.md`
  warns. Rebuilt both: `python3 -m venv .venv` + the documented pip set, then the
  `node-unrar-js` extractor. 29 entries, `2b.model` 3,897,376 B.
- **Retracted: "packs cannot be rebuilt in place."** That was wrong. With
  `references/Christie.zip` and `references/2b.rar` both present, the Christie builder
  runs and is **byte-reproducible**:
  `.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim --templates
  "/tmp/2bsrc/…/2b" --out /tmp/rebuild --dist /tmp/rebuild-dist` →
  sha256 `5e55745f…b4d`, identical to the tracked `dist/Christie_LAS_Slim.zip`, with
  `git status dist/` clean. This matters for the open plans: P2 and §5.1a of the atom
  plan can be validated against **real rebuilds**, not only shipped zips.
- Trap recorded: `--out` alone still writes the zip to `dist/`; `--dist` is the flag
  that redirects it. Always pass both when experimenting.
- Trap recorded: the `node -e '<one-liner>'` form of the rar extraction **fails** —
  the emscripten wasm sidecar resolves against `__dirname`, which is empty under `-e`.
  A script file works. Fixed in `HANDOFF.md` and in the diagnostics plan.
- Validation after restore: `pytest -q tests` → **645 passed, 30 skipped** (fixture
  present), `dist/` unchanged. No model, texture or ZIP was modified this round; the
  rebuild wrote only to `/tmp`.

## 2026-11-10 (third pass) — `recover_env.sh`, and four more stale claims retired

- The sandbox wiped `.venv` and `/tmp/2bsrc` **again** between sessions. Rather than repeat
  the manual restore, added **`tools/pd2-las/recover_env.sh`**: venv + deps + 2B template
  extraction, idempotent, `--verify` also runs the suite. Tested from a genuine wipe
  (`.venv` and `/tmp/2bsrc` deleted): restores both in **13 s**, suite then
  `645 passed, 30 skipped`.
- **Retracted: "`tools/pd2-las/glove_check.py` cannot run"** (arm-stub plan §9). It runs —
  `glove_check.py /tmp/gc/christie_slim.model /tmp/gc/wrist.png 60` → rc 0, 4-panel render.
  The plan told the next agent to avoid it and use `preview_textured` instead.
- **Retracted: "no `unrar`/`7z`/`bsdtar` ⇒ 2B templates unobtainable."** `bootstrap.sh`
  uses `node-unrar-js`, which installs and runs fine. There was never a missing tool.
- `diagnose_mesh.py --templates` sleeve-slit block now measures:
  **`0.00 cm²` open through the tube's mid-band, both arms, 0 leaky slices** — previously it
  printed `skipped`, so that clearance had never actually been measured with the tool.
- **Retracted: "`pyflakes` clean."** It is not: 5 warnings. Four come from the *uncommitted*
  neck patch (`build_models.py:2027` redundant `import math`, `:2701` redundant
  `import numpy as np`, `:2772` unused `z`, `tests/test_neck_three_zone.py:26` unused
  `pytest`); one pre-exists at `HEAD` (`tests/test_christie_las.py:462`). `HEAD` is clean.
  Recorded in `HANDOFF.md` and `CHRISTIE.md` so the next session does not chase it.
- `HANDOFF.md`: the manual extraction snippet was replaced by one `recover_env.sh` call, and
  the recovery section now says to read the branch name from git instead of copying it.
- Validation: `pytest -q tests` → **645 passed, 30 skipped**, `dist/` clean. No model,
  texture or ZIP changed; the only new file is `recover_env.sh`.

## 2026-11-10 (fourth pass) — the 2B template settles two "unverifiable" claims

- `recover_env.sh` worked unattended: the sandbox had wiped `.venv` and `/tmp/2bsrc` again,
  and the script restored both in **17 s**. That was the first real test of it.
- **The 2B template is a vanilla Overkill-authored body.** Two things that the seam plan
  listed as unverifiable are now measured:
  - **Seam normals.** `g_body` (27,741 verts / 35,260 tris): **22,486 total coincident pairs**
    across 4,783 groups, of which **0 diverge** by >30°. The 2026-11-07 figure is exactly
    right — it had only been inherited because the RAR was thought unreadable.
  - **Tangent basis.** `max |U·V| = 0.000000` on all 27,741 verts — **exactly 0.0000° from
    orthogonal, everywhere**. This retires the caveat that the only "0.00°" evidence was
    third-party ports; the engine's own geometry does it too.
- New finding from that comparison, and it changes the seam fix: the shipped packs are worse
  than "skewed". **116 (slim) / 327 (base) vertices have `|U·V| = 1.0`** — U and V are
  *parallel*, a fully degenerate basis. All channels are unit-length, so this is not a
  normalisation artefact. Gram-Schmidt cannot repair a parallel pair; Fix B must reconstruct
  U and V from the UV gradient.
- Distribution recorded in the seam plan: `>30°` 8.8 % (slim) / 15.5 % (base), `>60°` 3.8 % /
  5.8 %, `<1°` ~14 %. Vanilla 2B is 0 in every bucket.
- Added §8.1 to the seam plan: a ~1 s runnable check that asserts the 22,486 / 0 anchor, so
  the foundation of the whole seam argument is now a command rather than a citation.
- Retracted the "packs cannot be rebuilt" and "2b.rar unreadable" rows in the **atom** plan
  §8 as well, so all four plans now agree with measurement.
- Validation: `pytest -q tests` unaffected (docs only), `dist/` clean, no model changed.

## 2026-11-10 (fifth pass) — `check_all --full` is green; the neck patch touches nothing shipped

- `recover_env.sh` again restored the wiped sandbox unattended (18 s).
- **Retracted the third false alarm: `check_all.py --full` passes.** Seven of seven stages green
  (tracked checksum, guide compliance, winding/tangent frame, normal-map convention, 5/5 pack
  mutations, 16/16 auditor self-test, 645-test suite). I had reported it "permanently red"; it
  was only ever missing the 2B fixture, which is M1 again. The single `warn` in the guide audit
  is rule `G1` (green-channel direction) and `check_nm_convention.py` confirms the build already
  satisfies it — it is a confirmation prompt, not a failure.
- **The uncommitted neck patch changes no shipped artefact.** Rebuilt with the patch applied:
  `build_christie_las --variant slim` → sha256 `5e55745f…b4d` and `build_busty_variant` →
  `52f4c461…`, both byte-identical to the tracked packs, `dist/` untouched. Its only caller is
  `build_skyrim_outfit.py:313`/`:413`, and the Skyrim reference zips are absent — so the patch is
  **never exercised by a build in this checkout**, only by 16 unit tests. Safe to commit; not
  build-verified. Recorded in `HANDOFF.md`.
- Re-ran both mutation harnesses against the restored suite: pack-level 5/5, auditor self-test
  16/16. Unchanged, and still with **no atom/tangent/seam mutation** — M2 remains the one active
  mask.
- Pattern now explicit in the diagnostics plan: three of the seven initially reported mechanisms
  (M1, M5, "packs cannot be rebuilt") were all the same missing environment step. Restore the
  environment before believing a diagnostic is broken.
- Validation: `pytest -q tests` → 645 passed, 30 skipped; `dist/` clean; no model or texture
  changed. Only documentation updated this round.
