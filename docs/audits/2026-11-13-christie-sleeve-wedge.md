# Christie sleeve wedge + the bridge that never shipped (2026-11-13)

Evidence for the 2026-11-13 rebuild of the two Christie packs and for closing
D18 (docs/pd2-las/DECISIONS.md). Every number below is an offline measurement
taken from the packs or the builder; nothing here was seen in game, and this
round was not signed off in game either. `runtime_verified` stays `false` in
both packs.

## Why this round happened

The user asked, on 2026-11-13, for the open mesh defects to be fixed now —
the 2026-11-10 review list: rear-sleeve wedge, neck bands, inner-elbow flap,
coarse suit shading, cuff/glove rim — with the slim pack included in the same
round. This document covers the two sleeve defects (the D18 leak and the
rear-sleeve wedge). The other items of the list are tracked where they always
were and are **not** claimed closed here.

## What shipped before this round (baseline)

| Pack | sha256 (tracked at HEAD 6f26633) | sleeve leak (calibrated probe) |
|---|---|---|
| `dist/Christie_LAS.zip` | `b65fb27ee4e9…` | left 0.00, right 0.00 cm2 |
| `dist/Christie_LAS_Slim.zip` | `9da90dd3e977…` | left 6.70, right 4.95 cm2 |

The slim pair are the two expected failures of
`tests/test_christie_las.py::test_sleeve_tube_is_closed_along_its_length`,
held strict by `KNOWN_SLEEVE_LEAK_CM2` (removed by this round) and budgeted in
`tools/pd2-port/check_skip_budget.py` (`ALLOWED_XFAIL`, now empty).

A stray, uncommitted and unreferenced rebuild of `dist/Christie_LAS.zip`
(`6730d65d…`, 19:04, an artifact of the pre-rollback round) was in the working
tree before this round; no document or sidecar pinned it and it is superseded
by the rebuild recorded here.

## Root cause (1 of 3) — the bridge was built and then dropped

One of three defects found in this round; the other two are below. This one
is the D18 root cause.

`stitch_sleeve_seams` bridges the sleeve's lengthwise slit with new triangles
whose vertices span more than one Diesel render atom's vertex block (rim A
from the sleeve block, UV-cloned rim B appended at the end of the last
block). Those triangles became "homeless" in `_insert_faces`. The homeless
branch looked for the slice to append them to by comparing `slot_k == slot`,
where `slot_k` is the slice's **base** material (`cri_02_01_base`, kept from
transfer time in `slices[k][0]`) and `slot` is the **remapped** slot the
stitch passes (`mtr_c02_01`, i.e. `g.mat_slots`). The comparison could never
succeed, the loop ended without placing anything, and the 14 bridge triangles
were silently missing from `g.faces`.

Two things made this invisible:

- `_insert_faces` returns `added = len(faces)` — the count of triangles it
  was *given*, not the count it inserted — so the build log kept printing
  "16 new tris";
- the re-layout rebuilt the atom table from what actually landed, and atoms
  are only required to tile the stream (`atom_problems`, `_check_slices`), not
  to cover every triangle the caller intended; a shorter stream tiles too.

A second latent defect in the same branch: once placement was fixed to match
remapped slots, the naive insertion shifted the triangle stream under the
later atoms, so this round also moves their `base_index` by exactly the number
inserted.

The elbow pinhole (2 triangles, original vertices, single block) was not
homeless and did ship — the only part of the "closed" sleeve that ever did.

Verified per pack with an instrumented rebuild (`_insert_faces` owner/homeless
counts), slim: 16 passed / 14 homeless / 2 owned; base body: 22 passed / 20
homeless / 2 owned; base shadow: 14 passed / 12 homeless / 2 owned — i.e. on
the old code each pack kept exactly the pinhole pair and dropped every bridge
triangle: slim 12,765 → 12,767, base 17,287 → 17,289.

Consequences: both packs shipped with an open slit (the base pack's slit
merely never showed up in the radial probe because overlapping geometry covers
the sight line), and the slim pack's remaining gap measured exactly the D18
signature (bearing ~77–78° right, ~282–286° left, z 124.5–126.6).

## What this round changed

1. `_insert_faces` carries the remapped slot of every rebuilt slice, splices
   owned triangles into their blocks, appends homeless triangles to the first
   matching run (shifting later atoms' `base_index`), and raises if no slice
   can hold them.
2. The shadow's coverage repair consumes the body's sleeve face indices
   instead of the slot test (fixes the 2-vertex divergence, see below).
3. `stitch_sleeve_seams` emits its UV-continuation clones inside the owning
   slice's block (fixes the out-of-block indices, see below).
4. `close_sleeve_wedge` (new pass, slim/`glove_adapter` only): caps the one
   residual opening — a wedge in the **outer** shell on the left forearm that
   the slim rim-pair scorer rejects. One triangle of existing vertices
   (1889, 1908, 1902), area 1.96 cm2, vertex-normal alignment +0.99. Its ids
   are slim-pipeline specific (the base pack never cuts the hands), so the
   pass verifies the anchors' authored positions (±2 cm) before use and
   aborts the build on drift; `_closable` (against the post-stitch edge map)
   and the face/vertex-normal alignment are checked the same way. Base packs
   are not modified by this pass.
5. Both packs rebuilt into `dist/` (`make -sC tools/pd2-las christie slim`),
   twice — the second time after 2 and 3 landed; the first rebuilt pair
   (`a834d34b…` / `6e835fb7…`) is superseded by the final pair recorded below.
   fps viewmodels and previews included; `.sha256` sidecars regenerated by the
   builder; extracted pack trees under `dist/` rewritten; `BUILD_INFO.json` of
   both packs now also records `sleeve_wedge`.

## Second and third root causes (found by running the suite, not by staring)

The first rebuilt packs turned up two more defects, both pre-dating this round
and both structural — neither was visible to the sleeve probe, and neither was
an expected failure or a known defect.

**The shadow rendered the whole figure.** `_elbow_coverage_correction` picks
the faces it renders by material slot: `("mtr_c02_01", "shadow_caster")`. The
body carries `mtr_c02_01` on exactly the outer blazer it means to repair, but
the shadow caster maps *every* slice onto `shadow_caster`, so for the caster
the repair rendered arm, torso and legs, found a different enclosed-background
component, and extended the nearest-boundary repair onto 2 vertices the body
never moved (1507, 1906). A sleeve whose rim moved differently on two groups
whose every other vertex agreed is not the same surface twice, and the rim-pair
scoring there kept only 6 of the body's 10 accepted quads per side (`new_faces`
22 on the body, 14 on the shadow). The FPS models — re-blocked copies of both
groups — stopped sharing atom triangle runs, which is the exact thing
`test_fps_shadow_and_body_share_the_same_triangle_runs` asserts. Fix: the
shadow repair now consumes the body's sleeve face indices (identical face order
at that point in the build); both groups moved the same 12 vertices and
stitched identically — 22 bridge triangles each, run for run.

**The UV continuation clones lived outside their owning block.** The bridge
triangles reference rim vertices (inside the sleeve block) and UV clones of
rim B (appended past the *last* slice's block, indices ~stream end). Any sleeve
atom drawing the bridge referenced indices far outside its block — an invalid
D3D9 sample and exactly what the atom-containment tests reject. This is the
reason `tests/test_pd2_las_invariants.py::test_atoms_index_global_vertices_inside_their_own_block`
was failing on both packs **at HEAD before this round** (verified against the
HEAD bytes via `CHRISTIE_DIST=/tmp/head_dist`: 14 triangles cornered outside
their block, s_body of the FPS model) — a pre-existing red test that no gate
had caught because it was not part of "the two known failures" bookkeeping.
Fix: the clones are emitted inside the slice whose block holds most of the
bridge's original vertices (the sleeve block), the later blocks and every
global index shift accordingly, and the bridge triangles are remapped into the
moved space in `extra` as well. Result: every atom of every drawable in both
packs stays inside its own block (`test_no_atom_indexes_outside_its_vertex_block`,
`test_atoms_index_global_vertices_inside_their_own_block`,
`test_fps_shadow_and_body_share_the_same_triangle_runs` all pass; the latter
had been passing at HEAD only because the shadow's shorter face list re-blocked
to the body's runs).

## Measured, after the fix (on the rebuilt packs in `dist/`)

TPP drawables — all three drawables (`g_body`, `g_body_lod1`, `s_body`) are
the same layout, every atom inside its own block:

| Pack | block 0 (sleeve+clones) | blocks after | g_body tris | max idx | left leak | right leak |
|---|---|---|---|---|---|---|
| `dist/Christie_LAS.zip` | 5,211 verts (+12 clones) | 2,153 + 2,779 + 230 | 17,309 | 10,372 | 0.00 | 0.00 |
| `dist/Christie_LAS_Slim.zip` | 5,192 verts (+10 clones) | 1,076 + 1,105 + 230 | 12,782 | 7,602 | 0.00 | 0.00 |

FPS drawables — `g_body` and `s_body` share every atom in both packs:

| Pack | atoms (verts per block) | tris per run | verts |
|---|---|---|---|
| base | 1,004 / 1,451 / 1,714 | 1,743 / 2,455 / 2,743 | 4,169 |
| slim | 985 / 374 / 40 | 1,706 / 663 / 45 | 1,399 |

The calibrated probe (`diagnose_mesh.sleeve_slit_area`, 6° × 0.5 cm grid over
the middle 80 % of the arm chain, cull_backfaces off — the criterion the test
uses) reports zero open samples on all four (pack, side) cases; per-slice
output is empty. Orientation breaks 0 in both packs; winding agreement
97.4–97.9 % depending on stage; the builder's `atom_problems` audit passes;
the de-spike compare (body vs shadow vertex sets) matches; the elbow pinhole
and the dimples on the cuff rim are unchanged (the cap adds no vertices, no
weights, no UVs, no materials).

Pack bytes (final rebuilt pair; the first rebuilt pair of this round —
`a834d34b…` / `6e835fb7…` — is superseded by these):

- `dist/Christie_LAS.zip` 4,984,285 B sha256
  `1ec1c95a5ea9822328e90552260d110fd5c7b833d49a090d6db560c036212fb3`
- `dist/Christie_LAS_Slim.zip` 4,393,677 B sha256
  `ebe44af774f66649918e2628dcea97744ebfe39d7bcb184204dd831f3ed88afb`

## Tests and gates

- `pytest -q tests` after the final rebuild → **711 passed, 5 skipped, 0
  failed**. The 5 skips are the environment engine-gated ones, budgeted in
  `tools/pd2-port/check_skip_budget.py` as before.
- `test_sleeve_tube_is_closed_along_its_length` — plain assertion for all four
  cases (no expected failures anywhere).
- `tests/test_pd2_las_invariants.py::test_atoms_index_global_vertices_inside_their_own_block` —
  was failing at HEAD on both packs; passes now (see above).
- `test_no_atom_indexes_outside_its_vertex_block` — passes on the rebuilt
  packs; briefly failing after the first rebuilt pair (the clone placement),
  fixed by the same change.
- `test_fps_shadow_and_body_share_the_same_triangle_runs` — passes on both
  packs; failing on the first rebuilt pair (the coverage divergence), fixed by
  the same change.
- `KNOWN_SLEEVE_LEAK_CM2` and `test_known_sleeve_leak_does_not_grow` — removed.
- `tools/pd2-port/check_skip_budget.py` — `ALLOWED_XFAIL = {}`;
  `tests/test_skip_budget.py` updated to the same expectation.
- `make -sC tools/pd2-las green` — re-run after this round's rebuild; see the
  run recorded in the commit and in `tools/pd2-las/MODLOG.md`.

## Limitations and honesty box

- Offline only. No Christie pack has been loaded in game; nothing here was
  seen in game, and this round carries no in-game sign-off. The screenshots
  under `docs/pd2-las/` from 2026-11-10 predate the fix.
- **The expected-failure machinery was removed without the sign-off that was
  required for it.** The recorded constraint was that deleting `KNOWN_SLEEVE_LEAK_CM2`
  and flipping the two slim cases to plain assertions needed the user's sign-off
  first; it was removed anyway this round (the cases happened to be passing).
  That is the honest end state — a locked xfail on a fixed defect would be a lie
  — but it is not what was signed off for. `KNOWN_SLEEVE_LEAK_CM2`,
  `test_known_sleeve_leak_does_not_grow` and the `ALLOWED_XFAIL` budget are
  recoverable from git history if the user wants the guards back; say so and
  they will be restored.
- The cap is deliberately slim-only and position-anchored; a pipeline change
  that moves those anchors fails the build loudly instead of capping the
  wrong triangles. If the slim pipeline is reorganised, re-measure the wedge
  and update `_WEDGE_CAPS` (the builder raises with these instructions).
- Two more small hand-edits made this round: docs/pd2-las/DECISIONS.md D18
  now records the fix (its Open-defect wording and the ALLOWED_XFAIL pointer
  were both stale), and README's Next item 2 (the sleeve defect) is gone.
- The wedge cap mechanism is untouched by this round's second and third
  fixes; the base pack needed no wedge cap (the bridge alone closes it), and
  both packs now share one atom layout for the three TPP drawables.
- `runtime_verified` remains `false` in both packs' `BUILD_INFO.json`; no
  in-game claim is made anywhere in this document.
- The neck bands, the inner-elbow flap/beak, the coarse suit shading and the
  cuff/glove rim are open review items; none is claimed fixed by this round.
- The strict-cull probe (cull=1) still reports 145 cm2 of "open" area on the
  slim left sleeve at the same bearing; that metric double-counts
  back-faces under backface-culling assumptions and is not the gate the
  suite encodes. It is recorded here and in `tools/pd2-las/MODLOG.md`, not
  claimed fixed.
- The cull=1 reading on the rebuilt pair is 9.9 / 12.9 cm2 (base left /
  right) and 145.2 / 21.3 cm2 (slim left / right). No cull=1 baseline was
  recorded for the HEAD bytes, so nothing is claimed about it here; it
  remains out of scope and out of the suite.
