# Bugs in Diagnostics & Tests That Masked These Issues

**Status:** diagnosis complete, every claim measured on this checkout; fix spec ready to execute
**Date:** 2026-11-10
**Audience:** a cold-start coding agent with no prior session context
**Scope:** the *verification* layer — `tools/pd2-port/check_*.py`, `tools/pd2-las/diagnose_mesh.py`,
and `tests/`. Not the geometry defects themselves; those have their own documents (§1).

Every number below was produced by running the code in §2 against this checkout. Where a claim is
an argument rather than a measurement, it says so.

> All `file:line` citations are `HEAD` line numbers. They drift once you patch —
> **grep for the symbol**.

---

## 0. TL;DR

Six independent mechanisms let real defects through a **green** suite. They are ranked by how much
they actually hide.

| # | Mechanism | Evidence | What it hid |
|---|---|---|---|
| **M1** | **37 of 67 Christie tests never run** in a default checkout; repo-wide **59 of 85 skips are one missing fixture** (`2b.model`) | §3.1 | **Nothing — they all pass when the fixture is restored (measured).** The risk is that the whole geometry half of the evidence is absent, so a future regression there is invisible |
| **M2** | **No containment check anywhere**, and a mutation harness with 0 atom mutations | §3.2 | 60 out-of-bounds atom indices; `132 passed, 17 skipped` on a mutant pack |
| **M3** | **`assert report["border"] > 300`** is a *lower* bound on divergence: it cannot express its own stated intent, and it fails if border divergence ever legitimately reaches 0 | §3.3 | It does **not** currently block any fix (measured slack 131–506). A latent trap, not an active mask |
| **M4** | **`U·V` is asserted nowhere**; the orthonormality tests check only `N·U`/`N·V`, on 4 external packs | §3.4 | A 5–20° tangent shear on 98.7 % of vertices, in every pack this repo builds |
| **M5** | **`check_all.py --full` is GREEN** — retracted. It only failed while the fixture was missing, and even then the cause was M1. Its `detail` is still one truncated line, which did hide the reason | §3.5 | Nothing. A second false alarm of mine; the retraction is the finding |
| **M6** | **A three-name field trap** (`geo_len` / `slice_len` / `vertex_count`) with a comment naming a field that does not exist | §3.6 | Future containment checks silently reading `None` |
| **M7** | **`pytest.importorskip` at module scope deletes a whole file's tests but reports one skip** | §3.7 | 7 glove-behaviour Lua tests, `collected 0 / skipped 1` |

The single most important sentence: **the one active mask is M2.** A handed-crafted mutant that
keeps atom tiling perfect draws 16 out-of-bounds triangles, and **207 tests — the entire geometry
suite, with the 2B fixture present — pass it.** Every failure it produces is a byte count or a
hash. See §3.2.

M1, M3 and **M5 are latent or false alarms, not active masks**, and were overstated while
drafting. With the 2B fixture extracted: all 67 Christie tests pass, `border` sits at 431/806
against a floor of 300, and `check_all.py --full` is **green, 7 of 7 stages**. Correcting that
matters because the cheap action — run `recover_env.sh` — dissolves M1 and M5 outright, and the
expensive rewrite of the seam assertion (P3) buys less than it first appeared. See §3.1, §3.3,
§3.5.

**Pattern worth naming.** Three of the seven mechanisms I first reported (M1, M5, and the
"packs cannot be rebuilt" claim) were all the same missing environment step wearing different
clothes. When a diagnostic looks broken in this repo, restore the environment before believing
it.

---

## 1. Context: the defects that got through

These are documented elsewhere; this document is about why they survived review.

| Defect | Owner document |
|---|---|
| Neck three-zone rim/cap | `2026-11-09-neck-three-zone-repair-plan.md` |
| Arm skin stub + glove adapter | `2026-11-09-arm-skin-stub-glove-adapter-poke-through-plan.md` |
| UV-seam splits + non-orthogonal tangent basis | `2026-11-09-uv-seam-normal-splits-tangent-basis-repair-plan.md` |
| `s_body` atom OOB + FPS rig + elbow/cuff | `2026-11-10-s-body-atom-oob-fps-elbow-cuff-repair-plan.md` |
| Sleeve UV mask arg-order | `2026-11-07-christie-sleeve-uv-mask-repair-plan.md` |

**This document does not restate the geometry.** It fixes the verification layer so the next
defect of that shape is caught.

---

## 2. Reproduce every claim

```python
import subprocess, sys, zipfile, numpy as np
from pathlib import Path

REPO = Path("/home/user/universal-modder")
PY = str(REPO / ".venv/bin/python")


def run(args, **kw):
    return subprocess.run([PY, *args], cwd=REPO, capture_output=True, text=True, **kw)


# ---- M1: how much of the Christie test file actually executes? ----
r = run(["-m", "pytest", "tests/test_christie_las.py", "-q", "--no-header", "-rs"])
print("M1:", [l for l in r.stdout.splitlines() if "passed" in l or "SKIPPED" in l][-2:])
# WITH the 2B fixture (see P1a):  -> ['67 passed in 25.8s']      # everything runs
# WITHOUT it:                     -> ['SKIPPED [37] ... 539: 2B templates not
#                                      extracted', '30 passed, 37 skipped']
# i.e. the skip state is reversible and currently costs 55 tests suite-wide.

# ---- M2: is there any per-atom containment check? ----
# atom_problems validates that atoms TILE the vertex array and the triangle
# stream. It never checks that a triangle's indices fall inside its own block.
src = (REPO / "tools/pd2-las/build_models.py").read_text()
body = src.split("def atom_problems")[1].split("\ndef ")[0]
print("M2: atom_problems checks tiling only:",
      all(k in body for k in ("base_vertex", "slice_len", "tri_count", "base_index")))
print("M2: ...and never tests an index against a block bound:",
      "range(" not in body and " not in " not in body and "<=" not in body)
print("M2: mutation harness atom mutations:",
      (REPO / "tools/pd2-port/check_test_suite_mutations.py").read_text().count("atom"))

# ---- M5: is check_all --full reachable? ----
r = run(["-m", "pytest", "-q", "tests"])
print("M5: 'pytest -q tests' rc =", r.returncode, "| last line:",
      (r.stdout + r.stderr).strip().splitlines()[-1])
# WITH the fixture:  rc = 0 | '645 passed, 30 skipped, 1 warning'
# WITHOUT it:        rc = 2 | '1 skipped, 1 error in 0.31s'
# Same cause as M1: test_render_mesh_skeleton.py:42 runs _templates() at import.
```

Run this block **once with `/tmp/2bsrc` present and once without**, and diff the two
outputs. That difference is the whole of M1 and M5, and it is larger than every other
finding in this document except M2.

---

## 3. The six mechanisms, measured

### 3.1 M1 — 37 of 67 Christie tests are skipped by one missing fixture

```
$ .venv/bin/python -m pytest tests/test_christie_las.py -q -rs
....................s........sssssssssssssssssssss..sssssssssssssss      [100%]
SKIPPED [37] tests/test_christie_las.py:539: 2B templates not extracted (run tools/pd2-las/bootstrap.sh)
30 passed, 37 skipped in 3.23s
```

**55 % of the file never executes.** The cause is a single gate:

```python
def _templates() -> Path:
    """The 2B reference pack (references/2b.rar), extracted by bootstrap.sh."""
    for cand in (Path("/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"), ...):
        if (cand / "2b.model").is_file():
            return cand
    pytest.skip("2B templates not extracted (run tools/pd2-las/bootstrap.sh)")
```

`references/2b.rar` is in the repo but **cannot be extracted here** — there is no `unrar`, `7z` or
`bsdtar` in the sandbox (§8). So those 37 tests are skipped on **every** run in this environment,
which is the environment every document in §1 was produced in.

What is inside those 37 skips, by selector:

```
$ .venv/bin/python -m pytest tests/test_christie_las.py -q -k "elbow or sleeve or cuff or seam or atom"
2 passed, 24 skipped, 41 deselected
```

**24 of 26 elbow/sleeve/cuff/seam tests are skipped.** The two that ran are the non-fixture ones.

**Important correction — measured, and it changes the lesson.** Extracting the fixture is
possible in this sandbox (`bootstrap.sh` uses `node-unrar-js` via npm, not a system `unrar`;
§8 previously claimed otherwise and was wrong). With `2b.model` in place:

```
$ .venv/bin/python -m pytest tests -q --ignore=tests/test_render_mesh_skeleton.py
632 passed, 30 skipped          # was 577 passed, 85 skipped

$ .venv/bin/python -m pytest tests/test_christie_las.py -q
67 passed                       # all 67, including every elbow/sleeve/seam test
```

**All 55 restored tests pass.** So M1 is *not* currently hiding a defect — the skipped
elbow, sleeve, cuff and seam tests are consistent with the shipped packs and would pass.
That is a much narrower finding than "the coverage is broken", and it must be stated as
such: **M1 is a latent risk, not an active mask.** The active masks are M2 and M4.
The lesson stands but its justification changes: a 59-skip default state means nobody sees
these results on a normal run, so the first regression to land there will be invisible.

And there is **no atom test in this file at all**:

```
$ .venv/bin/python -m pytest tests/test_christie_las.py -q -k atom --collect-only
no tests collected (67 deselected)
```

Repo-wide the skip cause is even more concentrated — this is the full `-rs` breakdown,
grouped (counts are the pytest `[N]` values, so they sum to 85):

| skip reason | count |
|---|---|
| `2B templates not extracted (run bootstrap.sh)` | 37 |
| `extracted 2B templates at /tmp/2bsrc not present` | 10 |
| `2b.rar reference models not extracted to /tmp/2bsrc` | 7 |
| `2B templates not extracted` | 4 |
| `templates` | 1 |
| **all 2B-fixture skips** | **59** |
| `pack not built in this checkout` | 7 |
| `4.zip absent` | 6 |
| `needs ffmpeg` | 4 |
| `sourcepp is an optional extra` | 2 |
| Skyrim archive removed | 2 |
| `nifly not built` | 2 |
| `lupa` / `build output` / `Git Bash` | 1 each |
| **total** | **85** |

And by file, the skips concentrate exactly where the §1 defects are:

| file | skipped |
|---|---|
| `tests/test_christie_las.py` | **37** |
| `tests/test_skyrim_retarget.py` | 8 |
| `tests/test_build_models.py` | 7 |
| `tests/test_diesel_model.py` | 7 |
| `tests/test_fps_hands.py` | 5 |

**59 of 85 skips — 69 %, about two thirds — are one missing fixture.** That is the
single highest-value thing to fix in this document. That is the single highest-value thing to fix
in this document.

### 3.2 M2 — no containment check, and the mutation harness does not exercise atoms

**The harness exists and is green:**

```
$ .venv/bin/python tools/pd2-port/check_test_suite_mutations.py
  ok   triangle wound inside out                    failed as expected
  ok   triangle wound inside out (the audit must notice) failed as expected
  ok   FPS unit not registered                      failed as expected
  ok   localization emptied                         failed as expected
  ok   tangent channels removed from the geometry   failed as expected
5/5 pack-level test mutations caught
```

**But:** 5 mutations, all on `dist/lawson_las.zip`, only 5 distinct tests, and
`grep -c "atom"` over the file returns **0**. There is no mutation for atoms, tangents,
`U·V`, seam normals, or any Christie pack.

**A faithful mutant passes the whole suite.** Reproduced by shifting 4 triangles from atom 1 into
atom 0 (atom0 `+4`, atom1 `−4`, `base_index` shifted) — this is the *exact* shape of the shipped
`s_body` defect, and it keeps tiling perfect so `atom_problems` returns `[]`:

```
fps_christie_slim.model   atom_problems=NONE   OOB indices=12
christie_slim.model       atom_problems=NONE   OOB indices=60
```

Then, with `dist/Christie_LAS_Slim.zip` swapped for the mutant:

```
$ .venv/bin/python -m pytest tests/test_las_pack.py tests/test_hands_graft.py \
      tests/test_build_models.py tests/test_seam_normals.py \
      tests/test_glove_adapter.py tests/test_fps_hands.py -q
132 passed, 17 skipped, 1 deselected
```

**132 passed on a pack with 60 out-of-bounds atom indices.** The one deselected test was
`test_handoff_and_agents_quote_the_tracked_pack_bytes`, which fails only because rezipping changes
the file size by one byte — a *false* signal that has nothing to do with geometry.

**Re-run with the 2B fixture extracted, i.e. with the full geometry suite live** — this is the
strongest result in the document, because it removes the "the tests were merely skipped"
objection:

```
$ .venv/bin/python -m pytest tests/test_las_pack.py tests/test_hands_graft.py \
      tests/test_build_models.py tests/test_seam_normals.py tests/test_glove_adapter.py \
      tests/test_fps_hands.py tests/test_christie_las.py -q
FAILED test_las_pack.py::test_handoff_and_agents_quote_the_tracked_pack_bytes     # byte count
FAILED test_christie_las.py::TestPack::test_sha256_sidecar[slim]                  # hash
FAILED test_christie_las.py::TestPack::test_build_info_records_headless_and_provenance[slim]
3 failed, 207 passed, 7 skipped
```

**207 tests ran, and every single failure is bookkeeping** — a byte count, a sha256, and a
BUILD_INFO field. **Not one geometry test noticed 16 out-of-bounds atoms.** The shipped defect is
also still present in both packs right now (`s_body`: 16 OOB triangles, max reach past its own
block 920 in base / 730 in slim; `g_body`: 0). (That test is
itself a masking mechanism of the M5 kind: it fires on the wrong thing.)

The two atom tests that do exist are **synthetic-only** and never open a pack:

```
tests/test_hands_graft.py::test_atom_problems_catches_a_stale_index_offset
tests/test_hands_graft.py::test_weld_wrist_reports_atoms_that_tile
```

They build a `bm.Group` in memory. Neither reads `dist/`. So `atom_problems` is tested against
hand-made tiling errors and never against the shipped artefact.

### 3.3 M3 — `assert report["border"] > 300` forbids the correct answer

`tests/test_christie_las.py:847-853`:

```python
report = bcl.coincident_normal_report(g)
assert report["interior"] == 0, (...)
# ...and the pass must not have blanket-smoothed genuine folds: every
# remaining divergence has to sit on a border edge.
assert report["border"] > 300, (
    f"{which}: only {report['border']} border pairs diverge - a garment "
    "edge lost its hard normal, which means the pass went too far")
```

The comment states the intent: *"every remaining divergence has to sit on a border edge."* The
assertion is a **lower bound of 300**. So the test encodes:

* `border == 0` → **fail** (even though that is the correct, defect-free state)
* `border > 300` → pass

Meanwhile the same repo, three lines up in `diagnose_mesh.py:292-294`, prints the same metric as a
bare count with **no threshold and no verdict**:

```
divergent (>30 deg) coincident pairs: 431
   cross-mat/diff-uv      border      35
   cross-mat/same-uv      border       6
   same-mat/diff-uv       border     390
```

`431` is printed, labelled nothing, and the tool **always exits 0** (`diagnose_mesh.py:397`
`return 0`, no failure path). A diagnostic that cannot fail is a log line.

**Correction — measured, and it retracts a stronger claim made earlier in drafting.**

The measured values are `base border = 806`, `slim border = 431`, against a floor of 300. So
there is **131–506 pairs of slack**: the assertion is not currently forcing any divergence to
stay. And the seam repair plan (`2026-11-09-uv-seam…` §5) targets **interior** pairs — every
skipped/re-enabled test (`test_interior_coincident_normals_agree`) asserts
`interior == 0` — so a correct fix would not push `border` to 0 either.

The honest statement is therefore weaker: **this assertion cannot express its own comment**
("every remaining divergence has to sit on a border edge" is a *property*, not a *count*), and
it would fail on a genuinely divergence-free mesh. It is a **latent trap for a future change**,
not the cause of the seam defect getting through.

What *is* an active problem in the same area: `border = 431` and `806` are large numbers that
no test interprets. A hard normal split on a genuinely smooth seam and a correct split on a
fold are counted identically. That is the real gap, and P3 addresses it.

### 3.4 M4 — `U·V` is asserted nowhere on any pack this repo builds

`tests/test_pd2_las.py:713-714` and `:823-824`:

```python
assert float(np.abs(np.sum(nrm * tu, axis=1)).max()) < 1e-4
assert float(np.abs(np.sum(nrm * tv, axis=1)).max()) < 1e-4
```

`N·Tu` and `N·Tv`. **Never `Tu·Tv`.** And the spec list those lines run over is the four
`Miranda_*_over_*` packs — **externally produced** geometry this repo did not build.

Measured elsewhere (`2026-11-09-uv-seam…` §3.1): every external pack is exactly `0.00°` on `U·V`,
and every pack this repo builds is 5–20° skewed on 98.7 % of vertices. So:

* the only orthonormality assertion in the repo runs on packs that are already correct;
* the channel pair that is actually broken (`Tu·Tv`) is not asserted;
* `assert N·U < 1e-4` is exactly what an independent projection of U and V against N satisfies
  *by construction*. The test cannot distinguish a correct implementation from the buggy one.

`diagnose_mesh.py` mentions `uvdir` **zero** times. `uv_check.py` is a texture-orientation probe
that renders PNGs for eyeballing and asserts nothing.

### 3.5 M5 — retracted: `check_all.py --full` passes

I first reported this stage as "permanently red". **That was wrong, and it is worth recording
because it is the second false alarm of the same kind** (M1 and M5 were both the missing fixture,
presented as independent defects). Executed 2026-11-10 with the environment restored:

```
$ .venv/bin/python tools/pd2-port/check_all.py --full
  [ok  ] tracked pack matches its checksum          9123392 bytes, sha256 9c8a28368862edcc…
  [ok  ] guide compliance audit               1.0s  summary: 38 pass, 1 warn, 0 fail
  [ok  ] winding and tangent frame            0.6s  summary: 20677 triangles, 0 inverted, 0 degenerate
  [ok  ] normal-map convention                0.8s  VERDICT: the source is DirectX-style (Y-); the default build inverts…
  [ok  ] pack-level test mutations           11.6s  5/5 pack-level test mutations caught
  [ok  ] auditor self-test                   33.8s  16/16 mutations detected
  [ok  ] pytest suite                       103.1s  645 passed, 30 skipped, 1 warning
all 7 stages passed
```

So the orchestrator is sound and the pipeline is green end-to-end. Two residual notes, neither a
defect:

* The one `warn` is the guide's own green-channel rule (`G1`), and it is **already satisfied** —
  `check_nm_convention.py` reports *"the default build does invert the green channel, which is
  what PD2 wants."* The warn asks you to confirm the direction; it is not an unresolved failure.
* `stage()` still reports only `tail[-1]`. That is the one part of the original M5 worth keeping:
  on a real collection error it printed `1 skipped, 1 error` and named neither the file nor the
  cause.

### 3.6 M6 — the three-name field trap

The same atom field carries three different names depending on where you read it:

| location | name |
|---|---|
| `diesel_model.py:347` (`decode_model_data`) | `slice_len` |
| `dmodel.py:155` (the port's parser) | **`geo_len`** |
| `check_mesh_geometry.py:128` (a comment) | **`vertex_count`** |

Verified — `vertex_count` does not exist on the object:

```python
dmodel render_atoms keys: ['base_vertex', 'tri_count', 'base_index', 'geo_len', 'material_id']
has 'vertex_count'?  False
has 'slice_len'?     False
has 'geo_len'?       True
```

Today this is harmless *only because* `check_mesh_geometry.py` never actually uses the field — it
reads `base_index` and `tri_count` and slices faces. But it is a live trap: the first person to
write the containment check (§3.2) by following that comment gets `KeyError` or, worse, a
`getattr(..., None)` that silently disables the check. The comment already describes a field
containment check would need, and names it wrongly.

**Related, and already costing accuracy:** `check_mesh_geometry.py` folds every atom's face run
into one flat list (`:126-133`) and then analyses the union. It therefore cannot report
*per-atom* anything, which is why the atom defect is invisible to it even though it iterates atoms.

### 3.7 M7 — a module-level `importorskip` makes 7 tests report as 1 skip

`tests/test_glove_behavior_lua.py:36`:

```python
lupa = pytest.importorskip("lupa", reason="lupa (LuaJIT) not installed")
```

The file defines **7** test functions. With `lupa` absent:

```
$ .venv/bin/python -m pytest tests/test_glove_behavior_lua.py -q
1 skipped in 0.10s          # collected: 0
```

So a whole file's coverage collapses to a single skip line that looks like any other
unavailable-fixture skip. **This is why the suite total does not reconcile:** `-v` shows
`577 PASSED + 84 SKIPPED = 661`, but the summary says `85 skipped`. The extra one is this
module-level skip, which produces no collected item. Measured per-file: 661 collected, 662
outcomes. Anyone reconciling counts — or writing a skip budget (P1) — must account for
module-level skips separately, because they are invisible to collection.

Reproduce:

```python
import subprocess
r = subprocess.run([".venv/bin/python", "-m", "pytest",
                    "tests/test_glove_behavior_lua.py", "-q"],
                   capture_output=True, text=True)
print(r.stdout.strip())            # 1 skipped
# ...but the file defines 7 tests and collects 0
```

---

## 4. What the suite is structurally unable to see

Beyond the six mechanisms, three gaps are by construction:

**(a) Diagnostics that cannot fail.** `diagnose_mesh.py` returns `0` on every path
(`:397`). It is a report, not a check. Anything it prints — `431` divergent pairs, `125`
see-through armpit cells, `12 %` boundary edges — is advisory. Nothing in CI or in
`check_all.py` consumes it.

**(b) Previews read the mesh directly.** Every preview module decodes geometry and indices
itself and never touches render atoms — `grep -c render_atoms` returns **0** for
`preview_textured.py`, `neck_junction.py`, `glove_check.py`, `uv_check.py` and
`diagnose_mesh.py`. So an atom defect is **invisible to every
preview in the repo** by design — the previews draw what the mesh says, not what the game will
draw. `build_models.py:2832` (inside `atom_problems`) says this outright: *"a silent failure: the file stays structurally
valid and previews that read the mesh directly look perfect."*

**(c) The reference anchor — was unavailable, now resolved.** Several tests compare against
`2b.model` as ground truth (`test_christie_las.py:858-873` asserts it is
`{"interior": 0, "border": 0, "pairs": 0}`). Because no `*.model` is committed, that anchor is
only present once the RAR is extracted into `/tmp`. **It now can be, and the anchor was measured
directly on 2026-11-10:** 2B `g_body` (27,741 verts / 35,260 tris) carries **22,486 coincident
pairs** in 4,783 groups and **none** diverge. So every "matches the reference" claim that rests
on this figure is now independently verified rather than inherited — including the border
comparison in §3.3, where the reference sits at `0` and the shipped packs at 431 (slim) /
806 (base).

---

## 5. Implementation

Ordered by value per unit of risk. **P1–P3 are the ones that matter.**

### P1 — Extract the fixture, then budget what remains

**P1a (do this first, it is a two-command fix).** The 2B templates are *not* absent by nature —
they are absent because nobody ran the extractor:

```bash
cd /tmp && mkdir -p rarx && cd rarx && npm init -y && npm install node-unrar-js
cat > x.js <<'JS'
const { createExtractorFromFile } = require("node-unrar-js");
(async () => {
  const ex = await createExtractorFromFile({
    filepath: "/home/user/universal-modder/references/2b.rar",
    targetPath: "/tmp/2bsrc",
  });
  let n = 0; for (const f of ex.extract().files) n++;
  console.log("entries:", n);          // expect 29
})().catch(e => { console.error("FAIL:", e && e.message); process.exit(1); });
JS
node x.js
```

It **must** be a script file. `node -e '...'` fails: the wasm sidecar resolves paths relative to
`__dirname`, which is empty under `-e`, and the process dies inside emscripten. Both forms were
measured; only the file form works.

Measured: 29 entries, `2b.model` 3,897,376 B, and the suite goes
**`577 passed, 85 skipped` → `632 passed, 30 skipped`**, with `test_christie_las.py` at
**67/67 passed**. This single step removes 55 of the 85 skips and activates the entire geometry
half of the Christie evidence. It changes no code.

**P1b.** Once the fixture is present, keep it present: add the extractor to
`bootstrap.sh`'s guard (it is already at `bootstrap.sh:33-48`, so this is really "make sure
bootstrap is actually run"), and make a *regression* to a 59-skip state visible.

The goal is that **`577 passed, 85 skipped` stops reading as success.**

Add a skip budget to `check_all.py`'s pytest stage and to the docs' canonical command:

```python
# check_all.py --full
# `--ignore=examples` is a no-op while the path argument is `tests` (measured):
# `pytest -q tests --ignore=examples` still errors on the render module alone.
results.append(stage("pytest suite",
                     ["-m", "pytest", "-q", "tests",
                      "--ignore=tests/test_render_mesh_skeleton.py"]))
```

and add a separate stage that fails on an **unexpected** skip:

```python
# tools/pd2-port/check_skip_budget.py  (new)
"""Skips are allowed only for fixtures that are absent by design.

An unconditional `pytest.skip` inside a helper (test_christie_las.py:539) turns
off 37 tests with one line. This makes the budget explicit: each known skip
reason has a maximum count, and any new reason or growth fails.
"""
# Counts are the measured `-rs` totals on HEAD; see the table in §3.1.
ALLOWED = {
    "2B templates not extracted (run tools/pd2-las/bootstrap.sh)": 37,
    "extracted 2B templates at /tmp/2bsrc not present": 10,
    "2b.rar reference models not extracted to /tmp/2bsrc": 7,
    "2B templates not extracted": 4,
    "templates": 1,                                  # 59 in total, one fixture
    "pack not built in this checkout": 7,
    "4.zip absent": 6,
    "needs ffmpeg": 4,
    "sourcepp is an optional extra": 2,
    "the Skyrim source archive was intentionally removed": 2,
    "nifly not built": 2,
    "lupa (LuaJIT) not installed": 1,
    "build output not present": 1,
    "Git Bash / MSYS only": 1,                       # sums to 85
}
```

Fail if a reason is not in `ALLOWED` or exceeds its count. This converts "85 skipped, whatever"
into "59 of the 85 are the known-missing 2B fixture, and the other 26 are accounted for".

**Also report the ratio.** Emit `30 passed, 37 skipped` per file for the four pack-test files, so a
file that is mostly skipped is visible in the summary rather than buried in `-rs`.

### P2 — Add the containment check and the mutation that proves it fires

Two pieces, both required:

1. The strict per-atom containment check from
   `2026-11-10-s-body-atom-oob-fps-elbow-cuff-repair-plan.md` §5.1a (no `allow_outside`
   parameter — measured max reach past a block across all 14 drawables is **0**).
2. A mutation in `check_test_suite_mutations.py` that reproduces the shipped shape: atom0 `+N`,
   atom1 `−N`, `base_index` shifted, **tiling preserved**. That mutant must make a test fail.

```python
def m_atom_oob(files: dict[str, bytes]) -> dict[str, bytes]:
    """Shift N triangles from atom 1 into atom 0, keeping tiling perfect.

    This is the shipped s_body shape: every atom still tiles the vertex array
    and the triangle stream, and atom 0 now indexes past its own block.
    """
    # +N on atom0.tri_count, -N on atom1.tri_count, +3N on atom1.base_index
```

**Critical calibration, measured:** a mutation that breaks tiling is caught today (`atom 1 draws
from triangle 1760, not 1764`). Only the tiling-preserving mutant is invisible. The mutation must
be the second kind, or it proves nothing.

### P3 — Replace `assert border > 300` with a bound on the *right direction*

The intent (per its own comment) is "the pass did not blanket-smooth genuine folds". A lower bound
of 300 cannot express that, and it forbids the fix. Replace with an **upper** bound plus a floor
tied to the geometric crease test:

```python
# Divergence is only acceptable where the surface genuinely creases. A hard
# normal split on a smooth surface is the defect; a hard split on a fold is
# correct. Count only the former.
smooth_splits = bcl.hard_split_on_smooth_seam(g, max_dihedral_deg=15.0,
                                             min_split_deg=30.0)
assert smooth_splits == 0, (
    f"{which}: {smooth_splits} hard normal splits on a smooth (<=15 deg) seam")
# The pass must still leave real folds alone; assert it preserved creases
# rather than asserting a raw divergence total.
assert report["border"] >= bcl.crease_pair_count(g), ...
```

The exact helper belongs in `build_christie_las.py` next to `coincident_normal_report`, and is
specified in `2026-11-09-uv-seam…` §5.2. **Do not simply raise or lower the 300** — that trades one
blind state for another.

### P4 — Assert `U·V`, on our own packs

Add `|U·V| < 1e-4` alongside the existing `N·U` / `N·V` assertions, and run the same test over
`dist/Christie_LAS*.zip` (this repo's own output), not only the external `Miranda_*` packs.
Specification: `2026-11-09-uv-seam…` §6.3.

### P5 — Stop letting a missing fixture break collection, and stop truncating the error

Both are small, and both matter even after P1a:

* `tests/test_render_mesh_skeleton.py:42` runs `TEMPLATES = _templates()` at import time, and
  `_templates()` calls `pytest.skip` — which pytest rejects at module scope. Make `_templates()`
  return `None` and move the decision into `pytestmark`, so a missing fixture produces a
  **skipped module, never an uncollectable one**:

```python
TEMPLATES = _templates() or None
pytestmark = [
    pytest.mark.skipif(TEMPLATES is None, reason="2B templates not extracted"),
    pytest.mark.skipif(not PACK.is_file(), reason="Christie base pack not built"),
]
```

* Make `stage()` keep the first error line, not `tail[-1]`:

```python
def stage(name, args, cwd=ROOT):
    ...
    lines = [l.strip() for l in (proc.stdout + proc.stderr).strip().splitlines() if l.strip()]
    errs = [l for l in lines if l.startswith("ERROR") or " error" in l.lower()]
    detail = (errs[0] if errs else lines[-1] if lines else "")[:120]
```

Do **not** add `--ignore=tests/test_render_mesh_skeleton.py` as a permanent workaround. It hides
13 real tests (including `test_cuff_mouth_view_looks_down_the_forearm`) to work around a fixable
import-time bug.

### P6 — Fix the field-name trap

Rename in `dmodel.py:155` `geo_len` → `slice_len` for consistency with `diesel_model.py:347`, or
document both names at a single place and correct the `check_mesh_geometry.py:128` comment to name
a field that exists. Do not leave a comment describing a phantom field.

---

## 6. Verification

| # | Check | Pass condition |
|---|---|---|
| A1 | Fixture restored | `pytest -q tests` reports **30 skipped**, not 85 (measured achievable with P1a) |
| A1b | Skip budget exists | a new skip reason, or one existing reason growing, fails `check_skip_budget.py` |
| A2 | Skip visibility | the pytest summary shows per-file passed/skipped for the four pack-test files |
| A3 | Containment check discriminates | it fails on the current shipped packs and passes after the §5.1a fix; **0 false positives** across all 14 drawables |
| A4 | Atom mutation caught | `m_atom_oob` (tiling-preserving) makes a test FAIL; run `check_test_suite_mutations.py` and see it in the list |
| A5 | Border assertion is directional | lowering divergence to 0 must **pass**, not fail; a smooth-seam split must fail (latent — see §3.3) |
| A6 | `U·V` asserted | the test fails on today's `dist/Christie_LAS*.zip` and passes after the tangent fix |
| A7 | `check_all.py --full` stays green | already green (7/7 stages, measured); it must not regress |
| A8 | Error detail is useful | forcing a collection error makes `stage()` print the `ERROR` line, not the count summary |
| A8b | Missing fixture cannot break collection | delete `/tmp/2bsrc`; `pytest -q tests` still **collects**, rc 0 |
| A9 | No regression | `pytest -q tests` → **645 passed, 30 skipped** with the fixture, **577 passed, 85 skipped** without |
| A10 | Field names agree | `grep` finds no reference to a field the parser does not produce |

**A5 is the one to be careful with.** It is the only check in this document that changes what a
*passing* test asserts, and getting its direction backwards re-introduces the original masking.

---

## 7. Rejected alternatives

### 7.1 Rejected: making the 2B tests fail instead of skip
They assert against a fixture that genuinely is not in the repo. Failing them makes the suite
permanently red (see M5 for how that ends) and teaches people to ignore it. The fix is to **budget
and surface** the skips, not to convert them.

### 7.2 Rejected: vendoring a reference model into the repo
Would fix A1's root cause, but it is a redistributable-artefact question, not a test-design one,
and `references/2b.rar` is already tracked. Out of scope; note it and let the user decide.

### 7.3 Rejected: deleting `assert report["border"] > 300`
Deletes the only guard against blanket-smoothing real folds. Replace it with a directional
assertion (P3), do not remove it.

### 7.4 Rejected: adding more mutations to the existing harness without fixing its scope
The harness points at one pack and five tests. Adding atom mutations there without also covering
the Christie packs leaves §3.2's actual blindness (no pack-level atom test) intact.

### 7.5 Rejected: trusting previews as the visual check
§4(b): every preview reads the mesh directly and cannot see an atom defect. Any "it renders fine"
conclusion from `preview_textured` is evidence about geometry only.

---

## 8. What is NOT reproducible from this checkout

| Missing | Consequence |
|---|---|
| ~~`unrar` / `7z` / `bsdtar`~~ | **This row was wrong and is retracted.** No system extractor exists, but `bootstrap.sh` does not use one — it unpacks `2b.rar` with `node-unrar-js` via npm (`bootstrap.sh:35`). That works here: `npm install node-unrar-js` then the extractor writes 29 entries and `2b.model` (3,897,376 B) lands in `/tmp/2bsrc`. **The 37 M1 skips are entirely avoidable** — this is the cheapest fix in the document. |
| A committed reference `.model` | No ground truth is in the repo (`find . -name "*.model"` → nothing). Every "matches 2B / vanilla" claim is unverifiable in this checkout, including the anchor M3 relies on. |
| ~~Packs cannot be rebuilt~~ | **Retracted for Christie.** `references/Christie.zip` + `2b.rar` are both tracked and the builder is byte-reproducible: rebuilding slim yields sha256 `5e55745f…b4d`, identical to the tracked pack, with `--dist /tmp/...` leaving `dist/` clean. So **P2 and §5.1a can be validated with real rebuilds**, not just shipped zips and synthetic `Group`s. Still out of reach: the Skyrim route (`references/1.zip`–`5.zip` absent). |
| A D3D9 device, the game | "Out of bounds is a real device error" remains a specification argument, not an observation. No test here can close that. |
| `ffmpeg`, `sourcepp`, `lupa`, `nifly` | 8 further skips. `test_glove_behavior_lua.py` (the LAS Lua loader test) is among them. |

### 8.1 Retracted rows (measured 2026-11-10, second pass)

Two entries in the first version of this table were wrong, and correcting them **widens**
what an executing agent can verify:

| Old claim | Reality |
|---|---|
| "No `unrar`/`7z`/`bsdtar` ⇒ 2B templates unobtainable ⇒ 37 skips permanent" | `bootstrap.sh` uses `node-unrar-js` (npm), not a system extractor. `tools/pd2-las/recover_env.sh` restores venv + templates from a genuine wipe in **13 s**. |
| "Packs cannot be rebuilt ⇒ validate against shipped zips only" | Christie **rebuilds byte-identically** (slim → sha256 `5e55745f…b4d`, `dist/` untouched with `--dist /tmp/...`). P2 / §5.1a can use real rebuilds. |

Two further tools turn out to run that earlier documents called unrunnable:

* `tools/pd2-las/glove_check.py MODEL OUT.png [deg]` → rc 0, writes the 4-panel cuff render.
* `tools/pd2-las/diagnose_mesh.py --pack slim --templates <2b>` → the sleeve-slit block that
  otherwise prints `skipped`, and it measures **`0.00 cm²` open, both arms, 0 leaky slices**.

And one environment fact worth knowing: `--out` alone does **not** redirect the zip;
`build_christie_las.py` has a separate `--dist` flag. Use both when experimenting.

---

## 9. Execution order

0. **P1a first** — run the extractor. Two commands, no code change, and it takes the suite from
   85 skips to 30 while turning on every Christie geometry test. Do this before measuring
   anything else, or you will keep re-deriving results against a half-dark suite.
1. **P5** — unbreak `check_all.py --full` and its error detail. Everything else is measured
   through it, and today it cannot be green.
2. **P1b** — skip budget for what remains.
3. **P2** — containment check + the tiling-preserving mutation. Highest-value new gate.
4. **P4** — `U·V` assertion on our own packs.
5. **P3** — directional border assertion. **Do this after** P4, because it changes an existing
   passing test and you want the new failures distinguishable.
6. **P6** — field-name cleanup.
7. Re-run: `577 passed` + budgeted skips, `check_test_suite_mutations.py` green with the new
   mutation listed, `check_all.py --full` green.
