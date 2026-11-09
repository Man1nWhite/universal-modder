# Out-of-Bounds D3D9 Render Atom Indices in `s_body` + FPS Rig & Elbow/Cuff Issues

**Status:** diagnosis complete and measured on both shipped packs; fix spec ready to execute
**Date:** 2026-11-10
**Audience:** a cold-start coding agent with no prior session context
**Packs:** `dist/Christie_LAS_Slim.zip` and `dist/Christie_LAS.zip` (TPP **and** FPS models)
**Related:** `2026-11-09-arm-skin-stub-glove-adapter-poke-through-plan.md` (owns the wrist-cuff
geometry). This document owns the **atom/index** defect and the **FPS rig** invariants.

Every number below was produced by running the code in §2 against the shipped zips.

> All `file:line` citations are `HEAD` line numbers. They drift once you patch —
> **grep for the symbol**.

---

## 0. TL;DR

### The headline: `s_body`'s atom 0 claims 16 triangles that belong to another material slice

`s_body` is the shadow caster. Its first render atom declares

```
base_vertex = 0     slice_len = 5182     tri_count = 8841
```

but the 8841 triangles it owns index up to **vertex 5911**, i.e. **730 vertices past the end of
its own block**, and every one of the 16 offending triangles lives *entirely* inside atom 1's
vertex block:

| | SLIM | BASE |
|---|---|---|
| offending triangles | **16** | **16** |
| offending indices | **48** | **48** |
| distinct foreign vertices | **24** | **24** |
| how far past the block | **730 verts** (5182 → 5911) | **919 verts** (5199 → 6118) |
| where they are | both wrist cuffs, `z 104.8–116.4`, `\|x\| ≤ 45` | both wrist cuffs |

**D3D9 rejects this.** The index buffer is bound with the atom's vertex block; sampling index
`>= base_vertex + slice_len` is out of the bound vertex range. The shadow pass draws garbage or
the device debug layer raises. It is invisible offline because `atom_problems` (§4) deliberately
allows it.

**The exact defect: `s_body` atom 0's `tri_count` is 16 too large and atom 1's is 16 too small.**
The two drawables have **identical `slice_len`** (`[5182, 1076, 1207, 230]`) and identical total
triangles (12996), but the triangle split differs:

| atom | `s_body` `tri_count` | `g_body` `tri_count` | delta |
|---|---|---|---|
| 0 | **8841** | 8825 | **+16** |
| 1 | **1749** | 1765 | **−16** |
| 2 / 3 | 2028 / 378 | 2028 / 378 | 0 |

The 16 triangles are **atom 1's geometry**, drawn by atom 0. They are **not** drawn twice — atom 1
lost exactly those 16 (§3.4). `_insert_faces` spliced 16 faces onto the *end* of atom 0's run
instead of into atom 1's, and atom 1's run was shortened by the same amount.

### The second half: elbow and cuff

* **Cuff is in-scope but already documented.** The wrist cuffs have a large open mouth
  (`n=43`, r≈7 cm) on both sides, and `s_body`/`g_body` have **identical** loop structure
  (79/79 SLIM, 110/110 BASE). The visual defect is owned by the arm doc; what this document adds
  is that **the shadow copy must be fixed by the same rule as the visible body**, or the
  shadow's silhouette stops matching (`§3.5`).
* **Elbow is NOT a hole.** Both elbows carry one boundary loop of `n=27` / `n=25`, but its
  vertices run **17–18 cm** apart in 3D along a closed path. It is an index-space **seam along a
  cylinder**, not an opening. Treating it as a hole would be a new bug. `§3.6`.
* **FPS rig:** `s_body` and `g_body` have **different vertex counts** (1515 vs 1491 SLIM,
  4181 vs 4157 BASE) yet **share the identical index buffer** (2628 / 6983 triangles). That is
  legal only because the 24 extra cap vertices sit inside atom 0 in FPS. The invariant that makes
  it safe is exactly the one `s_body` TPP violates.

---

## 1. Scope

| | |
|---|---|
| Atom / index defect | `tools/pd2-las/build_models.py` — `group_atom_plan` (`:2809`), `atom_problems` (`:2819`), `assemble_model` (`:3044`) |
| Face splicing | `tools/pd2-las/build_christie_las.py` — `_insert_faces` (`:2165`), `_check_slices` (`:2195`), caller `:2551` |
| Cuff caps | `tools/pd2-las/build_models.py` — cap/band slice append (`:1204-1214`) |
| FPS extraction | `build_christie_las.py:3365` (`extract_bones` → `fps_shadow`) |
| Tests | `tests/test_hands_graft.py:335-397` (the existing atom-tiling tests) |
| Artefacts | rebuilt `dist/Christie_LAS.zip`, `dist/Christie_LAS_Slim.zip` + both `.sha256` |

**Out of scope:** the neck pass, the sleeve UV mask, the normal maps, the tangent basis
(separate documents), and the *geometry* of the wrist stub — that last one belongs to
`2026-11-09-arm-skin-stub-glove-adapter-poke-through-plan.md`. This document covers the
**render-atom encoding** of the same region plus the **FPS rig** invariants.

---

## 2. Reproduce

```python
import sys, zipfile, numpy as np
sys.path.insert(0, "tools/pd2-las")
sys.path.insert(0, "tools/pd2-port")

import diesel_model as dm
from diesel_model import (decode_geometry, decode_model_data,
                          decode_passthroughgp, decode_topology)
from dmodel import DieselModel

WANT = {dm.hash64(n): n for n in ("g_body", "g_body_lod1", "s_body")}


def atoms_of(zip_path, model_rel):
    """Yield (drawable name, verts, indices, atoms) for every atomised drawable."""
    with zipfile.ZipFile(zip_path) as zf:
        raw = zf.read(model_rel)
    m = DieselModel.from_bytes(raw)
    for s in m.sections:
        if s.tag != "model_data" or s.obj is None:
            continue
        md = decode_model_data(raw[s.start:s.end])
        if "atoms" not in md:
            continue
        pt = m.by_id.get(md["passthroughgp"])
        if pt is None or pt.obj is None:
            continue
        pg = decode_passthroughgp(raw[pt.start:pt.end])
        gs, ts = m.by_id.get(pg["geometry"]), m.by_id.get(pg["topology"])
        geo = decode_geometry(raw[gs.start:gs.end])
        idx = np.asarray(decode_topology(raw[ts.start:ts.end])["indices"], np.int64)
        yield WANT.get(md["name_hash"], f"#{md['name_hash']:016x}"), geo, idx, md["atoms"]


def oob_per_atom(geo, idx, atoms):
    """Indices drawn by an atom that fall outside that atom's own vertex block."""
    rows = []
    for ai, a in enumerate(atoms):
        bv, sl, tc, bi = a["base_vertex"], a["slice_len"], a["tri_count"], a["base_index"]
        end = bv + sl
        seg = idx[bi // 3 * 3:(bi // 3 + tc) * 3]
        n = int(((seg < bv) | (seg >= end)).sum())
        if n:
            rows.append((ai, bv, end, int(seg.min()), int(seg.max()), n))
    return rows


SPECS = [
    ("SLIM TPP", "dist/Christie_LAS_Slim.zip",
     "Christie_LAS_Slim/assets/units/christie_slim/skins/christie_slim/christie_slim.model"),
    ("SLIM FPS", "dist/Christie_LAS_Slim.zip",
     "Christie_LAS_Slim/assets/units/christie_slim/skins/christie_slim/fps_christie_slim.model"),
    ("BASE TPP", "dist/Christie_LAS.zip",
     "Christie_LAS/assets/units/christie/skins/christie/christie.model"),
    ("BASE FPS", "dist/Christie_LAS.zip",
     "Christie_LAS/assets/units/christie/skins/christie/fps_christie.model"),
]

for tag, zp, mp in SPECS:
    for name, geo, idx, atoms in atoms_of(zp, mp):
        rows = oob_per_atom(geo, idx, atoms)
        print(f"{tag:9s} {name:12s} verts={geo['vert_count']:5d} "
              f"{'OOB ' + str(rows) if rows else 'clean'}")
# SLIM TPP s_body -> [(0, 0, 5182, 0, 5911, 48)]
# BASE TPP s_body -> [(0, 0, 5199, 0, 6118, 48)]
# every g_body / g_body_lod1 / FPS drawable -> clean
```

---

## 3. Measurements

### 3.1 The violation is isolated to `s_body` atom 0

| pack | drawable | verts | global OOB | per-atom OOB |
|---|---|---|---|---|
| SLIM TPP | **`s_body`** | 7695 | 0 | **48** |
| SLIM TPP | `g_body_lod1` | 7695 | 0 | 0 |
| SLIM TPP | `g_body` | 7695 | 0 | 0 |
| SLIM FPS | `s_body` | 1515 | 0 | **0** |
| SLIM FPS | `g_body_lod1` / `g_body` | 1491 | 0 | 0 |
| BASE TPP | **`s_body`** | 10361 | 0 | **48** |
| BASE TPP | `g_body_lod1` / `g_body` | 10361 | 0 | 0 |
| BASE FPS | `s_body` | 4181 | 0 | **0** |
| BASE FPS | `g_body_lod1` / `g_body` | 4157 | 0 | 0 |

**Global** out-of-bounds is **zero everywhere** — every index is a valid vertex of the shared
array. Only the *per-atom* bounds are violated. That is why nothing in the repo noticed.

### 3.2 The offending triangles are entire, not straddling

```
triangles in atom0's run reaching past the slice end : 16
  all three indices past the end                    : 16   <- entirely foreign
  straddling (some in, some out)                    :  0
  triangles fully inside atom0's own block          : 8825
```

So this is **not** the documented neck-cap case (a fan anchored on the rim and reaching one ring
outside). It is 16 whole triangles whose every vertex belongs to the next slice. They are
**present twice** in the index buffer: once in atom 0's run and once in atom 1's run. Their
positions are the wrist cuffs — `z 104.8–116.4`, `|x| ≤ 45`, 24 distinct vertices.

### 3.3 The 16 triangles are atom 1's geometry, assigned to atom 0

Every vertex of every offending triangle lies inside **atom 1's** block:

```
foreign vertex range           : [5182, 5911]
atom 0's own block             : [0, 5182)
atom 1's block                 : [5182, 6258)
all verts inside atom 1's block: True (16/16 triangles)
```

and the vertex/normal positions are the **wrist cuffs** (`z 104.8–116.4`, `|x| ≤ 45`) — the same
region the arm doc works on, which is why this is easy to mistake for a cuff-geometry bug.

It is not. It is a **triangle-range accounting** bug.

### 3.4 The delta is exactly ±16, and it cancels

`slice_len` is identical in both drawables, so the vertex blocks are fine. Only the triangle split
moved:

```
s_body tri_counts = [8841, 1749, 2028,  378]   sum = 12996
g_body tri_counts = [8825, 1765, 2028,  378]   sum = 12996
                     ^^^^  ^^^^
                     +16   -16        (cancel)
s_body atom1 base_index = 26523 -> triangle 8841
g_body atom1 base_index = 26475 -> triangle 8825
8825 + 16 = 8841   ==  s_body atom1's start
```

Set-difference of the two atom-0 runs: `s_body` atom 0 holds **exactly 16** triangles that
`g_body` atom 0 does not, and those 16 are **absent from `s_body` atom 1** (not duplicated). So the
pack draws each triangle once; the *atom assignment* is simply wrong for 16 of them, pointing
atom 0 at atom 1's vertex block.

**`_insert_faces` (`build_christie_las.py:2165`) is the mechanism.** It splices faces at

```python
end = base_i + 3 * tris
at = end // 3
g.faces[at:at] = faces                       # into the END of the target slice's run
for k, (...bi2, t2, nv2) in enumerate(g.slices):
    if k != si and bi2 >= end:
        g.slices[k] = (..., bi2 + 3 * added, t2, nv2)   # shift later runs
g.slices[si] = (src, base_v, base_i, tris + added, nverts)
```

When the target slot resolves to **atom 0** it absorbs the faces and atom 1 is shifted and (via
the caller's recomputation) shortened — atom 1's `tri_count` loses the 16 while atom 0 gains them,
so the total stays right and `_check_slices` (`:2195`), which validates only that the runs tile
the stream, passes.

> **Why `g_body` is clean and `s_body` is not:** the two groups have *different* `mat_slots`, so
> `_insert_faces` resolves `si` differently. `s_body`'s only slot is `shadow_caster`, so every
> spliced face lands in the *first* slice carrying that slot — atom 0. `g_body` has several
> material slots, so the same call resolves to the slice that actually owns that material. The
> defect is therefore **a consequence of the shadow group collapsing every material into one
> slot**, which is exactly what `TPP_GROUPS["shadow"]` does (`build_models.py:86-89`).

### 3.5 `s_body` tracks `g_body` exactly (cuff implication)

Boundary-loop census, TPP:

| pack | drawable | loops | cuff-region loops | largest cuff loop |
|---|---|---|---|---|
| SLIM | `g_body` | 79 | 16 | `n=43` + `n=43` (both sides) |
| SLIM | `s_body` | **79** | **16** | **`n=43` + `n=43`** |
| BASE | `g_body` | 110 | 16 | `n=175` + `n=175` |
| BASE | `s_body` | **110** | **16** | **`n=175` + `n=175`** |

`s_body` is a faithful copy of `g_body`'s topology. **Consequence for the arm fix:** any change
to the cuff (cap, taper, deletion) must be applied to `body` *and* `shadow` in the same pass, or
the shadow caster's silhouette will diverge from the visible body and the character will cast a
shadow that does not match what is drawn. The arm plan already loops over `("body", "shadow")`
(`build_christie_las.py:3280`, `:3304`) — **keep that**; do not "optimise" it to body only.

### 3.6 The elbow is a seam, not a hole — do not cap it

Each elbow carries exactly one boundary loop:

```
elbow R: n=27   centre=(34.3, -0.7, 128.9)   max 3D distance from the start vertex: 18.05 cm
elbow L: n=25   centre=(-34.2, -0.5, 129.3)  max 3D distance from the start vertex: 17.29 cm
```

A 27-vertex loop whose vertices run 18 cm apart along a closed path is **an index-space seam
running the length of the cylinder**, not an opening. For comparison a genuine opening (the wrist
mouth) is `n=43` with all vertices within ~9 cm of its own centre and `max` distance from the
start roughly the diameter. Passing the elbow loop to `cap_holes`/`_fan_cap` would stitch the
sleeve shut along its length.

> **Do not "fix" the elbow by capping it.** If the elbow reads badly in game it is a *shading*
> (the 2026-11-07 forearm-normals doc) or a *weight* problem, not a hole.

### 3.7 The FPS rig shares one index buffer between different vertex counts

```
SLIM FPS:  g_body 1491 verts / 2628 tris        s_body 1515 verts / 2628 tris
           index buffers byte-identical: True
BASE FPS:  g_body 4157 verts / 6983 tris        s_body 4181 verts / 6983 tris
           index buffers byte-identical: True
```

A single index buffer drives two geometries with different vertex counts. That is only sound
because the extra vertices are all inside atom 0 and atom 0 is the only consumer that reaches
them. **The invariant to enforce is exactly §3.1's.** If a future edit appends cap vertices in
FPS the way TPP did, FPS `s_body` breaks identically.

---

## 4. Root cause

Three layers, in order of what to change.

### 4.1 `_insert_faces` splices into the wrong atom for a single-slot group

`_insert_faces` (`build_christie_las.py:2165`) finds its target with

```python
si = next((k for k, s in enumerate(g.mat_slots) if s == slot), None)
```

For a group whose every slice maps to the **same** slot — `s_body`, whose only output is
`shadow_caster` (`build_models.py:86-89`) — this always returns `k = 0`. So every spliced face is
appended to **atom 0's** run regardless of which material slice actually owns the geometry, and
atom 1's `tri_count` is correspondingly short by that amount. That is the ±16 in §3.4.

`g_body` escapes because it has several slots, so `si` lands on the slice that genuinely owns the
material. **The bug is latent in every single-slot group** and `s_body` is simply the first place
it produces an index that leaves its own block.

### 4.2 `atom_problems` cannot see it

`atom_problems` (`build_models.py:2819`) enforces **tiling only**, and says so:

> Indices are absolute, so a triangle may reach vertices outside its own block (the neck-cap fan
> does exactly that); what must hold is that the atoms *tile* both the vertex array and the
> triangle stream, with nothing shared and nothing left over.

`s_body` tiles perfectly, so the validator returns `[]` on both shipped packs:

```
SLIM s_body: atom_problems() -> NO PROBLEMS (passes)
BASE s_body: atom_problems() -> NO PROBLEMS (passes)
```

**The stated justification is not even true of these packs.** Measured across all 14 atomised
drawables in all four models, the maximum number of vertices any atom reaches past its own block
is **0** — including every drawable that carries a neck cap. The neck-cap fan reuses rim vertices
already inside the block. So the exemption in that docstring has never been exercised, and the
containment check can be strict (§5.1a).

### 4.3 This exact failure mode shipped once before

`tests/test_hands_graft.py:355` records it:

> Only the vertex offset used to be rebased, so the appended slice's render atom pointed at the
> first triangles of the body: the grafted hands were in the file but no atom ever drew them, and
> two torso patches were drawn with the hand material instead. Structurally valid, invisible to
> every preview.

A *tiling* test was written afterwards (`:390`). A *containment* test never was, because §4.2's
docstring declared containment optional. That is the gap to close.

## 5. Implementation

### 5.1 Fix the invariant, not the symptom (recommended)

**Make every atom's index run reference only its own vertex block, with one explicit, declared
exception.** Then the `s_body` violation cannot exist and the next one is caught at build time.

**(a) Add the containment check to `atom_problems`.** **Measured fact that decides the design:
`allow_outside = 0` is correct.** Every atom of every drawable in all four models — including the
ones that carry a neck cap — is *fully contained*; the maximum reach past an atom's own block
across all clean drawables is **0**. The neck-cap fan reuses rim vertices that are already inside
the block, so it has never needed the exemption the docstring claims. Do not add an allowance to
be safe: an allowance is what let this ship.

```python
def atom_problems(geo: dict, topo: dict, atoms: list[dict]) -> list[str]:
    """...existing tiling checks unchanged, then..."""
    problems = []
    # ... existing vertex-block and triangle-run tiling checks ...

    idx = topo["indices"]
    for k, a in enumerate(atoms):
        bv, sl, tc, bi = (a["base_vertex"], a["slice_len"],
                          a["tri_count"], a["base_index"])
        end = bv + sl
        seg = idx[bi:bi + tc * 3]
        if not seg:
            continue
        low, high = min(seg), max(seg)
        if low < bv:
            problems.append(f"atom {k} indexes below its block ({low} < {bv})")
        if high >= end:
            problems.append(
                f"atom {k} reaches vertex {high}, {high - end + 1} past its "
                f"block [{bv}, {end}) - that is another material slice")
        foreign = sum(1 for i in range(0, len(seg), 3)
                      if all(v >= end for v in seg[i:i + 3]))
        if foreign:
            problems.append(
                f"atom {k} draws {foreign} whole triangles that lie entirely "
                f"inside another slice's vertex block")
    return problems
```

Call it from `audit_model` (`:2935`). **`s_body` then fails the audit** (730/920 past the block,
16 foreign triangles), which is the point.

> **Measured false-positive rate: zero.** Run against all 14 atomised drawables in the four
> models, this check fails **exactly 2** (`s_body` TPP in SLIM and BASE) and passes the other 12.
> If your implementation flags any `g_body`, `g_body_lod1`, FPS drawable or the 8-vertex stub,
> the check is wrong — see §10.2.

**(b) Fix the splice so a face lands in the atom that owns its vertices.**

The real fix is in `_insert_faces`: choose the target slice by **which vertex block the new faces
belong to**, not by which slot happens to come first.

```python
def _insert_faces(g: bm.Group, faces: list[tuple], slot: str) -> tuple[int, int]:
    ...
    if not faces:
        return (0, 0)
    cands = [k for k, s in enumerate(g.mat_slots) if s == slot]
    if not cands:
        base_i = len(g.faces) * 3
        g.faces.extend(faces)
        g.slices.append((slot, len(g.verts), base_i, added, 0))
        g.mat_slots.append(slot)
        return (base_i // 3, added)
    # Pick the slice that owns the vertices these faces are built from. Appending
    # to the first slice with a matching slot is wrong for a single-slot group:
    # it puts one material slice's triangles in another slice's atom, and the
    # atom then indexes past its own vertex block (a D3D9 out-of-range sample).
    def owns(k: int) -> int:
        _m, bv, _bi, _t, nv = g.slices[k]
        return sum(1 for f in faces if all(bv <= v < bv + nv for v in f))
    si = max(cands, key=owns)
    ...
```

If `max(owns)` is 0 for every candidate, the faces bridge two slices; keep the current behaviour
and **report it**, because that is the only case where reaching outside a block is legitimate:

```python
    if owns(si) == 0:
        report_bridging_slice(slot, len(faces))   # or a warnings.warn
```

> **Do NOT implement the earlier draft of this section.** It proposed sorting `g.slices` and
> `g.mat_slots` together by `base_index`. That is a **no-op on the shipped packs**: both lists are
> already in ascending `base_index` order (`base_index` ascending: `True`, `base_vertex`
> ascending: `True`). Sorting cannot fix a `tri_count` split, because the split is not an ordering
> problem. Verified, then discarded.

> **Also do not delete the 16 triangles.** They are real cuff geometry owned by atom 1; removing
> them drops 16 triangles from the shadow mesh. The fix is to *reassign* them, not to drop them.

### 5.2 FPS rig: keep the shared index buffer, enforce the invariant

The FPS `s_body`/`g_body` pair legitimately shares one index buffer at two vertex counts
(§3.7). Do **not** fork the buffers — that doubles the index data and would need the atom
`base_index` values rewritten. Instead:

* Add the §6.1 **A6** invariant: for every atomised drawable, every atom's maximum index must be
  `< base_vertex + slice_len`. This is what makes sharing sound.
* Add the §6.1 **A7** cross-drawable check: if `s_body` and `g_body` in one model share an
  identical index buffer, their **atom triangle runs must be identical** (same `base_index`,
  same `tri_count`) so the shared stream is consumed the same way. Today they are identical in
  FPS and differ in TPP (by the 16) — so this check also fails today and is another signal.

### 5.3 Cuff and elbow — explicitly out of this fix

* **Cuff**: geometry is owned by the arm doc. This document's contribution is §3.5 — the shadow
  copy must receive the same treatment. Add §6.1 **A8**.
* **Elbow**: no change. §3.6 explains why. If someone proposes capping the elbow, this section is
  the answer.

---

## 6. Verification

### 6.1 Route A — offline, executable today

| # | Check | Pass condition |
|---|---|---|
| A1 | Reproduce §3.1 | `s_body` TPP in **both** packs reports exactly `[(0, bv, bv+sl, lo, hi, 48)]`; every other drawable reports clean. |
| A2 | Reproduce §3.2 | all 16 offending triangles are **entirely** foreign; 0 straddling; 8825 own-block triangles. |
| A3 | Reproduce §3.7 | FPS `s_body` and `g_body` index buffers are byte-identical while vertex counts differ by exactly 24. |
| A4 | After the splice fix | `s_body` TPP reports **0** OOB indices and **0** foreign triangles; `atom_problems` returns `[]`; `s_body` atom `tri_count` becomes `[8825, 1765, 2028, 378]` — **identical to `g_body`**; total triangles still 12996 and `slice_len` still `[5182, 1076, 1207, 230]`. |
| A5 | New gate is discriminating | the new `atom_problems` call **fails on the current shipped packs** (16 foreign triangles) and passes after the fix. A test that passes before the change proves nothing. |
| A6 | Containment invariant, all drawables | for every atom of every drawable in all four models, `max(index) < base_vertex + slice_len`. |
| A7 | FPS shared-buffer invariant | in FPS models, `s_body` and `g_body` atom `(base_index, tri_count)` runs are identical. **Fails today**; must pass after. |
| A8 | Shadow tracks body | `s_body` and `g_body` boundary-loop **counts** stay equal (79/79 SLIM, 110/110 BASE) after any cuff change. |
| A9 | Elbow untouched | the elbow loop stays `n=27` / `n=25` with 3D extent > 17 cm — i.e. **not capped**. |
| A10 | No geometry drift | vertex and face counts, UVs and positions are identical to pre-fix for every drawable except the 16 triangles' *atom assignment*. |
| A11 | Suite | `577 passed, 85 skipped` (`--ignore=examples --ignore=tests/test_render_mesh_skeleton.py`). |

### 6.2 Route B — render / in game

| # | Criterion | Pass condition |
|---|---|---|
| B1 | Shadow silhouette | the cast shadow still matches the visible body at the wrists — no missing cuff disc, no doubled cap. |
| B2 | No flicker at the wrist | the 16 duplicated triangles were drawn twice by two atoms; after the fix each is drawn once. Any wrist shimmering disappears. |
| B3 | Device debug layer (if available) | no `D3D9` warning about index out of range during the shadow pass. |
| B4 | FPS viewmodel | no change to the viewmodel — it is already clean (A1); confirm rather than assume. |

### 6.3 Tests to add

```python
def test_no_atom_indexes_outside_its_vertex_block(self):
    """An atom's index run must not reference another material slice's block.

    ``s_body``'s atom 0 draws 16 whole triangles that live 730 vertices inside
    atom 1 on both shipped packs. D3D9 binds the index buffer with the atom's
    vertex block, so that is an out-of-range sample; every offline preview reads
    the mesh directly and cannot see it.
    """
```

and

```python
def test_fps_shadow_and_body_share_the_same_triangle_runs(self):
    """Different vertex counts, one index buffer => the runs must agree."""
```

Both must be shown to **fail on the current packs** before the fix.

---

## 7. Rejected alternatives

### 7.1 Rejected: raise `slice_len` of atom 0 to cover the foreign vertices
`slice_len` is what the atom binds; widening atom 0 to 5911 would overlap atoms 1–3's vertex
blocks and break the **tiling** invariant that `atom_problems` *does* enforce. Trades a
containment bug for a tiling bug.

### 7.2 Rejected: sorting `slices`/`mat_slots` by `base_index`
This was the first proposed fix and it is a **verified no-op** (§5.1b). Both lists are already in
ascending `base_index` order on both packs, and the defect is a `tri_count` split, not an ordering
problem.

### 7.3 Rejected: giving `atom_problems` an `allow_outside` allowance
This was the first design and it is **wrong on measurement**: no atom in any of the four models
reaches even one vertex past its own block (§5.1a). The neck-cap fan reuses rim vertices already
inside the block, so the exemption its docstring claims has never been exercised. An allowance
parameter is the mechanism that would let the next violation through, so the check is strict.

### 7.4 Rejected: capping the elbow
§3.6: the elbow loop is 17–18 cm of path, not an opening. Capping it would weld the sleeve shut.

### 7.5 Rejected: forking the FPS index buffers
§5.2. The shared buffer is legal under the containment invariant and doubling it changes every
FPS atom offset.

---

## 8. What is NOT reproducible from this checkout

| Missing | Consequence |
|---|---|
| ~~`references/1.zip`–`5.zip` … packs cannot be rebuilt~~ | **Retracted 2026-11-10 — this plan can be validated by a real rebuild.** `references/Christie.zip` and `2b.rar` are both tracked and the builder is byte-reproducible: `build_christie_las.py --variant slim --dist /tmp/...` reproduces sha256 `5e55745f…b4d`, the tracked pack, leaving `dist/` clean. So §5.1a's containment check and the `owns()` fix can be exercised end-to-end (build → re-read → assert), not only on synthetic `Group`s. `tools/pd2-las/recover_env.sh` restores the toolchain after a sandbox wipe. **Do not overwrite `dist/`** — always pass `--dist /tmp/...`; note `--out` alone still writes the zip to `dist/`. |
| A D3D9 device | §6.2 B3 cannot be run here. The claim "D3D9 rejects this" is a specification argument from the bound-vertex-range rule, **not** an observed device error — treat it as the reason the fix is required, not as a measured log line. |
| The game | B1/B2/B4 cannot be executed. |
| ~~`references/2b.rar` unreadable~~ | **Retracted 2026-11-10** — it is readable (`recover_env.sh` / `node-unrar-js`). No rule in this plan depends on it, so nothing else changes. |

---

## 9. Execution order

1. **Add the containment check** (§5.1a) and prove it **fails** on the current packs (A5).
2. **Apply the splice fix** (§5.1b) so a face lands in the atom that owns its vertices.
3. Re-run A1–A4, A6, A7 — all four models, both packs.
4. Confirm A8/A9: shadow/body loop counts still equal; elbow still open.
5. Rebuild both packs, regenerate `dist/*.zip.sha256` (`build_christie_las.py:3446-3449`).
6. A10/A11, then B1–B2. Report B3/B4 as unverified.

---

## 10. Cold-start verification log

Run 2026-11-10 on this checkout. Each executable block was extracted from **this document** and
run as a subprocess from the repo root.

### 10.1 Results

| block (indexed by content) | result |
|---|---|
| §2 reproduce (`atoms_of` + `oob_per_atom`) | **PASS** — exactly two failures, both `s_body` TPP: SLIM `(0,0,5182,0,5911,48)`, BASE `(0,0,5199,0,6118,48)`; all 12 other drawables clean |
| §5.1a containment check, `allow_outside` absent | **PASS (discriminating)** — fails exactly 2 of 14 drawables, zero false positives |
| §5.1b `owns()` selection | **PASS** — `owns()` scores `[0, 16, 0, 0]`, selects slice 1, yielding `[8825, 1765, 2028, 378]` = `g_body`'s split exactly |

Verbatim §5.1a output on today's packs:

```
SLIM TPP  s_body       FAILS (2 problems)
    atom 0 reaches vertex 5911, 730 past its block [0, 5182)
    atom 0 draws 16 whole triangles inside another slice
SLIM TPP  g_body_lod1  pass
SLIM TPP  g_body       pass
SLIM FPS  s_body       pass
...
=> 2 drawables fail
```

### 10.2 Three things that were measured and refuted during this investigation

Recorded so the executing agent does not repeat them.

1. **"The neck cap legitimately reaches outside its block."** **False.** Max reach past the atom's
   own block, measured across all 14 atomised drawables in all four models: **0**. The neck-cap
   fan reuses rim vertices already inside the block. Hence §5.1a is strict and §7.3 rejects the
   allowance parameter. If your implementation needs an allowance, it is wrong.

2. **"The foreign vertices are freshly appended cap vertices."** **False.** They span
   `[5182, 5911]`, which is the *middle* of atom 1's block `[5182, 6258)`, and the vertex array
   ends at 7694. They are ordinary slice-1 vertices, not an append tail.

3. **"Sort `slices` and `mat_slots` by `base_index` to fix it."** **False — verified no-op.** Both
   lists are already in ascending order on both packs (`base_index ascending: True`,
   `base_vertex ascending: True`). The defect is a `tri_count` split (±16 between atoms 0 and 1),
   not an ordering problem. See §7.2.

### 10.3 Notes for the executing agent

* **There are 14 atomised drawables**, not 4: TPP models have `s_body`, `g_body_lod1`, `g_body`;
  FPS models have those three plus an 8-vertex stub (`#edcd315c53f74a6c`, 12 triangles). The stub
  is a useful negative control — it must always pass.
* **`s_body` and `g_body` have identical `slice_len` but different `tri_count`.** Always compare
  both tuples; comparing only the totals hides the defect (both sum to 12996).
* **Index code fences by content, never position.** This document has 8 Python fences in order:
  the §2 reproduce block, the cap-append excerpt, the atom-plan excerpt, the §5.1a check, the
  §5.1b `_insert_faces`, the §5.1b `owns()` addition, the §6.3 test stub, the second test stub.
* **`decode_geometry` needs `diesel_model`, not `dmodel`.** `dmodel.DieselModel` gives you the
  section table; the channel layout (and the `item_size`-is-a-component-count trap) lives in
  `diesel_model.decode_geometry`. Hand-rolling the channel loop produced vectors of length √3
  during this investigation — use the repo's decoder.
* **`build_models.py` in the working tree is 156 lines longer than `HEAD`** (the neck patch is
  uncommitted). All line numbers here are `HEAD`. Grep the symbol.

