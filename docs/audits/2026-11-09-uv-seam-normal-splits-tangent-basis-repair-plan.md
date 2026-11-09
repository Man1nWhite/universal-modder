# UV-Seam Normal Splits & Non-Orthogonal Tangent Basis

**Status:** diagnosis complete and measured on both shipped packs; fix spec ready to execute
**Date:** 2026-11-09
**Audience:** a cold-start coding agent with no prior session context
**Packs:** `dist/Christie_LAS_Slim.zip` (item `christie_slim`) and `dist/Christie_LAS.zip` (item `christie`)
**Supersedes:** nothing. **Extends** `2026-11-07-christie-forearm-normals-and-seam-repair-plan.md`
§Phase 3 and §Phase 4, whose rules this document measures, corrects and replaces.

Every number below was produced by running the code in §2 against the shipped zips. Nothing
is inferred from source reading alone.

> All `file:line` citations are `HEAD` line numbers. They drift once you patch —
> **grep for the symbol**, never trust the number.

---

## 0. TL;DR

There are **two independent defects**. They are different in size and must not be fixed by the
same rule.

### Defect A — the tangent basis is skewed (large, affects every vertex)

`build_models.py:2748-2755` projects `uvdir_u` and `uvdir_v` onto the normal's plane
*independently*. That forces `N·U = N·V = 0` exactly, but **never orthogonalizes U against V**.
The shipped result:

| pack | n | `\|U·V\|` p50 | p95 | max | >30° | >60° |
|---|---|---|---|---|---|---|
| SLIM body | 7695 | **5.26°** | 48.25° | 90.00° | 676 | 295 |
| SLIM fps | 1491 | **9.46°** | 46.45° | 90.00° | 176 | 48 |
| BASE body | 10361 | **5.91°** | 67.28° | 90.00° | 1606 | 603 |
| BASE fps | 4157 | **9.69°** | 90.00° | 90.00° | 1097 | 347 |

`N·U` and `N·V` are `0.0000` on every vertex — the existing gate passes. `U·V` is not
orthogonal on **98.7 %** of vertices.

**The reference is unambiguous.** Every pack in `dist/` produced by an *external* pipeline is
exactly orthogonal:

| pack | `\|U·V\|` p50 | p95 | max |
|---|---|---|---|
| Miranda_L4D2_over_{Bonnie,Clover,Sydney}, Miranda_Romance_over_* | **0.00°** | 0.00° | 0.00° |
| Geralt_over_Rust (body atoms) | **0.00°** | 0.00° | 0.00° |
| **Christie_LAS / Christie_LAS_Slim (ours)** | 5.26–5.91° | 48–67° | 90° |

`N·U` is 0 in the reference too. So PD2's contract is an **orthonormal basis**, and only the
packs this repo builds violate it.

### Defect B — normal splits across UV seams (small, concentrated)

The existing `unify_coincident_normals` (`build_christie_las.py:2343`) unifies only **26 groups /
52 verts** (slim) and **25 / 50** (base). It exempts any vertex carrying an index-space
boundary edge — which is **82 %** of all coincident groups (689/837 slim). A correct rule
unifies **87** (slim) and **128** (base) groups.

But the exemption is far too broad *and* far too narrow at once. Measured by dihedral angle
across the seam (the physically correct test — a smooth surface must not carry a hard normal
split):

| pack | UV-seam groups | smooth (dihedral ≤ 15°) | hard-normal split > 30° on a smooth seam |
|---|---|---|---|
| SLIM | 685 | 110 | **0** |
| BASE | 1104 | 159 | **11** (5 of them > 60°) |

So **slim is already clean**, and base has **11 genuinely wrong groups**. The naive counts
("611 groups >10°") are almost all *correct* creases or stacked layers — see §3.3, which is the
trap this task must not fall into.

### The gate that let both defects through

`tests/test_pd2_las.py:713-714` and `:823-824` assert orthonormality as

```python
assert float(np.abs(np.sum(nrm * tu, axis=1)).max()) < 1e-4
assert float(np.abs(np.sum(nrm * tv, axis=1)).max()) < 1e-4
```

`N·T` and `N·B` — **never `T·B`**. And the test only runs on the four `Miranda_*_over_*` packs,
i.e. geometry this repo did *not* build. No test has ever checked `U·V` on our own output.

---

## 1. Scope

| | |
|---|---|
| Tangent basis | `tools/pd2-las/build_models.py:2897-2909` (`assemble_model`), `tools/pd2-las/diesel_model.py:633` (`compute_uv_directions`) |
| Seam normals | `tools/pd2-las/build_christie_las.py:2343` (`unify_coincident_normals`), `:2305` (`coincident_normal_report`), `:1657` (`_coincident_groups`) |
| Tests | `tests/test_seam_normals.py` (6 tests), `tests/test_pd2_las.py:713-714`, `:823-824` |
| Artefacts | rebuilt `dist/Christie_LAS.zip`, `dist/Christie_LAS_Slim.zip` + both `.sha256` |

**Not in scope** (separate documents, do not re-litigate): the neck
(`2026-11-09-neck-three-zone-repair-plan.md`), the arm skin stub
(`2026-11-09-arm-skin-stub-glove-adapter-poke-through-plan.md`), the sleeve UV mask, the
normal-map DXT5 packing, and the *stored vertex normals' own* correctness on the forearms
(Phase 1 of the 2026-11-07 doc). This document is about the **relationship between normals,
UVs and the tangent frame**, not about which absolute normal a vertex should have.

---

## 2. Reproduce

Nothing needs the Skyrim sources and nothing needs a rebuild.

```python
import sys, zipfile, numpy as np
sys.path.insert(0, "tools/pd2-las")
sys.path.insert(0, "tools/pd2-port")
from diesel_model import decode_geometry
from dmodel import DieselModel


def unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)


def load(zp, mp):
    """Return (geometry dicts, face arrays) for one .model inside a zip."""
    with zipfile.ZipFile(zp) as zf:
        raw = zf.read(mp)
    m = DieselModel.from_bytes(raw)
    geos = [decode_geometry(raw[s.start:s.end]) for s in m.sections
            if s.tag == "geometry" and s.obj is not None]
    tris = []
    for s in m.sections:
        if s.tag != "model_data" or s.obj is None:
            continue
        md = s.obj
        if not hasattr(md, "passthrough_id"):
            continue
        pt = m.by_id.get(md.passthrough_id)
        if pt is None or pt.obj is None:
            continue
        ts = m.by_id.get(pt.obj.topology_id)
        if ts is not None:
            tris.append(np.asarray(ts.obj.faces, np.int64))
    return geos, tris


SLIM = ("dist/Christie_LAS_Slim.zip",
        "Christie_LAS_Slim/assets/units/christie_slim/skins/christie_slim/christie_slim.model")
BASE = ("dist/Christie_LAS.zip",
        "Christie_LAS/assets/units/christie/skins/christie/christie.model")

for tag, (zp, mp) in (("SLIM", SLIM), ("BASE", BASE)):
    d = load(zp, mp)[0][0]
    N = unit(np.array(d["normals"]))
    U = unit(np.array(d["uvdir_u"]))
    V = unit(np.array(d["uvdir_v"]))
    dot_nt = np.abs((N * U).sum(1))
    dot_nv = np.abs((N * V).sum(1))
    skew = np.degrees(np.arcsin(np.clip(np.abs((U * V).sum(1)), 0, 1)))
    print(f"{tag}: n={len(N)}")
    print(f"  |N.U| max={dot_nt.max():.6f}   |N.V| max={dot_nv.max():.6f}   <- both pass 1e-4")
    print(f"  |U.V| p50={np.median(skew):.2f} p95={np.percentile(skew, 95):.2f} "
          f"max={skew.max():.2f}  >30deg={int((skew > 30).sum())}   <- FAILS")
# expect SLIM 5.26/48.25/90.00/676 and BASE 5.91/67.28/90.00/1606
```

---

## 3. Measurements

### 3.1 Why `U·V ≠ 0`, exactly

`build_models.py:2741` calls `dm.compute_uv_directions` (a faithful port of p2mt's
`ComputeUvDirections`: accumulate the per-triangle UV gradient, then normalize). That function
returns **two independently accumulated, independently normalized** vectors. They are the exact
`∂P/∂u` and `∂P/∂v` of the UV map and are *not* perpendicular to each other unless the UV map is
conformal.

`assemble_model` then does:

```python
u_arr = u_arr - np.sum(u_arr * n_arr, axis=1, keepdims=True) * n_arr
v_arr = v_arr - np.sum(v_arr * n_arr, axis=1, keepdims=True) * n_arr
u_arr /= np.maximum(np.linalg.norm(u_arr, axis=1, keepdims=True), 1e-8)
v_arr /= np.maximum(np.linalg.norm(v_arr, axis=1, keepdims=True), 1e-8)
```

Two independent Gram–Schmidt projections against **N only**. Each is made orthogonal to `N`
and unit length. **Nothing makes U orthogonal to V.** The measured `N·U = N·V = 0` exactly is
precisely the signature of this code, and the measured `U·V` p50 ≈ 5° is the shear angle of the
UV map that the projection preserved.

This is not a numerical accident — it is the definition of the transformation.

### 3.2 The handedness is also unstable

`(U × V)·N` measures whether the frame is right-handed. A mirrored UV island legitimately gives
`-1`; a whole island should be consistent. Measured per connected face island:

| pack | islands | islands with **mixed** handedness | minority verts |
|---|---|---|---|
| SLIM | 69 | **18** | 531 |
| BASE | 92 | **26** | 570 |

A single connected surface carrying both `+` and `-` handedness is a **flipped frame inside one
island** — the normal map's green channel inverts across that line, which reads as a shading
crease that is not in the geometry. Note the external reference packs show the same
mixed-handedness signature on *some* atoms (e.g. `Geralt_over_Rust` 1741-vert atom at
`+1034/-707`), so mixed handedness alone is **not** automatically a defect — see §5.4 for how to
treat it without creating a new bug.

### 3.3 The seam-split trap (read this before writing any rule)

Naive counting on coincident position groups says the seam problem is enormous:

```
SLIM: 837 coincident groups, 611 with >10deg normal separation, max 113.87deg
BASE: 1286 coincident groups, 1021 with >10deg, max 140.18deg
```

**Almost all of that is correct.** Three independent discriminators each show it:

**(i) Dihedral across the seam.** A hard hem/cuff edge *should* carry a hard normal split. Only
the smooth ones are defects:

```
SLIM: 685 UV-seam groups -> 110 smooth (<=15deg dihedral) -> 0 with split >30deg
BASE: 1104 UV-seam groups -> 159 smooth                  -> 11 with split >30deg (5 >60deg)

# These 110/159 counts do NOT yet apply the open-border exclusion; §3.4 does, and is the
# number the implementation must produce.
```

**(ii) Component stacking.** Coincident vertices that belong to *different* connected components
are stacked garment layers (blazer over body), and must keep their own normals. Split by
component count:

```
SLIM: same-sheet 629 (sep p50 45.87deg) | stacked 208 (sep p50 0.00deg)
BASE: same-sheet 1070 (p50 52.39deg)    | stacked 216 (p50 0.00deg)
```

Stacked layers are *already* unified — they are not the problem. The large separations live in
same-sheet groups, and most of those are genuine creases per (i).

**(iii) What the shipped pass already achieves.** `unify_coincident_normals` unifies only
26/52 and 25/50, but the resulting mesh is *already* clean on slim by (i). So the current
`max_deg = 30` + interior-only rule is **not** obviously broken — it is merely mis-targeted
and, on base, misses 11 smooth-seam groups.

> **Do not "fix the 611 groups".** Unifying every coincident group with a >1° split would
> flatten 489 real creases (slim) and 857 (base) into a mean direction. That is the single most
> likely way to make this pack visibly worse.

### 3.4 Exact group census

Every group falls in exactly one row — the rows sum to the total (verified).

| | SLIM | BASE |
|---|---|---|
| coincident groups (2+ copies) | 837 | 1286 |
| vertex-count overhead | 7695 / 6805 = **1.13×** | 10361 / 9006 = **1.15×** |
| — on a 3D open border (real rim/fold) | 251 | 262 |
| — no UV difference (redundant split) | 5 | 26 |
| — crease ≥ 15° dihedral (real hard edge) | 489 | 857 |
| — copies already within 1° (no work) | 5 | 13 |
| — opposed (mean is meaningless) | 0 | 0 |
| **= unified by the §5.2 rule** | **87** | **128** |
| their split before: p50 / p90 / max | 10.18 / 13.90 / 24.83° | 10.40 / 15.13 / 67.89° |
| of those, split > 30° | **0** | **11** |

Note the two numbers that differ from §3.3 and why: §3.3's "110 smooth / 159 smooth" counted
smooth-dihedral groups **without** the open-border exclusion. The border row (251 / 262) is
applied first here, so the eligible set is 87 / 128. Both numbers are correct for their
definition; **87 / 128 is the one §5.2 must reproduce.**

---

## 4. Root cause

**Defect A.** `assemble_model` performs a projection, not an orthonormalization. It was written
to satisfy the two assertions that existed (`N·U`, `N·V`), and it satisfies them exactly. The
contract it actually needs to satisfy — an orthonormal frame — was never asserted.

**Defect B.** `unify_coincident_normals` decides "is this an interior vertex?" from
**index-space** edge counts:

```python
count[(x, y)] += 1 ...  border = {v for e, n in count.items() if n == 1 for v in e}
inner = [i for i in ids if i not in border]
```

A UV seam splits one 3D position into two indices, so the seam's own edges are index-space
boundaries. Every vertex on a UV seam therefore looks like a border vertex, and **689 of 837
groups** (82 %) are exempted wholesale. Whether a vertex is on a *surface* boundary is a
property of **3D** connectivity, not of index identity — measuring it in index space conflates
"this edge is a UV seam" with "this edge is the edge of the garment".

The 2026-11-07 doc's Phase 3 diagnosed exactly this and proposed an `_is_manifold_uv_seam_edge`
helper. It was **not implemented** — that is why the numbers in §3.3 still show the wide
exemption. This document supplies the corrected rule (§5.2), because the Phase 3 proposal's
`pos_dir == (1,1)` test is *necessary but not sufficient* (see §5.3).

---

## 5. Implementation

### 5.1 Fix A — orthonormalize the basis (do this first; it is the large defect)

**File:** `tools/pd2-las/build_models.py`, the block at `:2898-2909`.

Replace the two independent projections with a single Gram–Schmidt pair that keeps **U exact**
and reconstructs **V** from the frame, preserving the UV map's handedness:

```python
    if len(g.normals) == len(g.verts) and len(g.verts) > 0:
        import numpy as np

        n_arr = np.asarray(g.normals, dtype=np.float64)
        u_arr = np.asarray(du, dtype=np.float64)
        v_arr = np.asarray(dv, dtype=np.float64)
        n_len = np.linalg.norm(n_arr, axis=1, keepdims=True)
        # A stored normal of zero length would make every projection below NaN.
        n_arr = np.where(n_len > 1e-8, n_arr / np.maximum(n_len, 1e-8),
                         np.array([[0.0, 1.0, 0.0]]))

        # U: project onto the tangent plane, then normalize.
        u_arr = u_arr - np.sum(u_arr * n_arr, axis=1, keepdims=True) * n_arr
        u_len = np.linalg.norm(u_arr, axis=1, keepdims=True)

        # Degenerate UV triangles give u ~ 0. Fall back to any unit vector in
        # the tangent plane, chosen deterministically from the normal.
        deg = (u_len[:, 0] < 1e-6)
        if np.any(deg):
            nd = n_arr[deg]
            ref = np.where(np.abs(nd[:, :1]) < 0.9,
                           np.array([[1.0, 0.0, 0.0]]),
                           np.array([[0.0, 1.0, 0.0]]))
            fb = np.cross(nd, ref)
            fb /= np.maximum(np.linalg.norm(fb, axis=1, keepdims=True), 1e-12)
            u_arr[deg] = fb
            u_len[deg] = 1.0
        u_arr = u_arr / u_len

        # V: rebuild strictly orthogonal to both N and U. The sign is taken
        # from the UV map's own handedness so a mirrored island stays mirrored.
        b0 = np.cross(n_arr, u_arr)
        b0 /= np.maximum(np.linalg.norm(b0, axis=1, keepdims=True), 1e-12)
        sign = np.where(np.sum(b0 * v_arr, axis=1, keepdims=True) >= 0.0, 1.0, -1.0)
        v_arr = sign * b0

        du = [tuple(map(float, row)) for row in u_arr]
        dv = [tuple(map(float, row)) for row in v_arr]
```

Why this specific form:

* **U is kept, V is rebuilt.** U is the direction the UV `u` axis actually points; discarding it
  would rotate the normal map's red channel. Rebuilding V costs only the (already-approximate)
  `v` gradient and makes `T·B = 0` exact.
* **`sign` preserves mirroring.** A mirrored island has `v_arr` on the far side of the `N×U`
  line; taking `sign` from `dot(N×U, v)` keeps that island mirrored instead of silently
  flipping it. This is what makes `(U×V)·N` continue to read `-1` on mirrored islands.
* **The 90° case is real, not an error.** `|U·V| = 1.0` (max) means the UV gradient really is
  degenerate/parallel at that vertex — do **not** special-case it away; the rebuild handles it
  because `N×U` is still well-defined.
* The existing `1e-8` guards are kept in spirit but the zero-normal case is now explicit; the
  old code divided a zero vector by `1e-8`, producing exact zeros that then survive into the
  packed bytes as a zero-length normal.

**Do not** instead renormalize `V` after projecting it against both N and U — that is a
sequential Gram–Schmidt that *also* works, but it changes U's direction, and the U channel is
the one the artist's UV layout is defined against. Keep U.

### 5.2 Fix B — decide "surface border" in 3D, not index space

**File:** `tools/pd2-las/build_christie_las.py`, inside `unify_coincident_normals` (`:2343`).

Add a 3D-space adjacency pass and use it in place of the index-space `border` set. Keep the
existing `max_deg` / `max_mean_deg` semantics.

```python
def _surface_border_and_creases(g, verts, tol=1e-4, smooth_deg=15.0):
    """Classify coincident copies by 3D surface topology, not index identity.

    Returns (border, crease, gid_of): `border`/`crease` are sets of 3D group
    ids whose surface is open, or whose copies sit across a genuine crease. A
    group in either set keeps its own normals. `gid_of[i]` is the group id of
    vertex index `i`, so the caller can test membership without re-rounding.
    """
    import numpy as np

    key = np.round(verts / tol).astype(np.int64)
    gid_of = np.empty(len(verts), np.int64)
    index_of = {}                      # position key -> group id
    groups = {}                        # group id      -> [vertex indices]
    for i, k in enumerate(map(tuple, key)):
        if k not in index_of:
            index_of[k] = len(index_of)
            groups[index_of[k]] = []
        gid_of[i] = index_of[k]
        groups[index_of[k]].append(i)

    faces = np.asarray(g.faces, np.int64)
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                  verts[faces[:, 2]] - verts[faces[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)

    # 3D edge -> incident faces. An edge shared by != 2 faces is an open border.
    edge = {}
    for fi, (a, b, c) in enumerate(faces):
        for x, y in ((a, b), (b, c), (c, a)):
            gx, gy = gid_of[x], gid_of[y]
            if gx == gy:
                continue
            edge.setdefault((gx, gy) if gx < gy else (gy, gx), []).append(fi)

    border = set()
    for (gx, gy), fs in edge.items():
        if len(fs) != 2:
            border.add(gx)
            border.add(gy)

    # Per-copy geometric normal, to measure the crease across the seam.
    vf = {}
    for fi, (a, b, c) in enumerate(faces):
        for v in (a, b, c):
            vf.setdefault(v, []).append(fi)
    crease = set()
    for gid, ids in groups.items():
        if len(ids) < 2 or gid in border:
            continue
        gnorm = []
        for i in ids:
            m = fn[vf[i]].sum(axis=0)
            ln = float(np.linalg.norm(m))
            gnorm.append(m / ln if ln > 1e-9 else np.zeros(3))
        gnorm = np.asarray(gnorm)
        sep = np.degrees(np.arccos(np.clip((gnorm @ gnorm.T).min(), -1.0, 1.0)))
        if sep > smooth_deg:
            crease.add(gid)
    return border, crease, gid_of
```

Then in `unify_coincident_normals`, replace the `border` computation and the `inner` selection:

```python
    border, crease, gid_of = _surface_border_and_creases(g, verts)
    for ids in _coincident_groups(verts):
        if gid_of[ids[0]] in border or gid_of[ids[0]] in crease:
            continue                        # genuine open edge or real crease
        sub = normals[ids]
        ...                                 # unchanged from here
```

> The helper returns `gid_of` from the same rounding pass it used to build `groups`, so there is
> no second rounding to drift out of sync.
> **Do not** silently widen `max_deg`. With the corrected border the eligible population grows
> from 26 to 87 (slim) / 128 (base) groups and the existing `1° < spread <= 120°` band is
> correct as-is (§3.4 shows max spread 67.89° on base, well inside 120°).

### 5.3 Why not the 2026-11-07 Phase 3 rule verbatim

Phase 3 proposed gating on `pos_dir[(gx,gy)] == 1 and pos_dir[(gy,gx)] == 1` plus two incident
faces within 60°. That test is **necessary but not sufficient**: `pos_dir == (1,1)` and exactly
two faces also hold for a **closed manifold hem seen from both sides** (a cuff whose front and
back panels meet at the same 3D curve but face opposite directions). The `>= 0.5` face-normal
dot was supposed to exclude that, and it does — but only for the *face* normals, not for the
*stored* normals, so a pair whose faces agree within 60° but whose stored normals are 90° apart
still gets unified into a mean that lies 45° from both.

**The dihedral test in §5.2 is strictly stronger** because it compares the crease angle to a
fixed `smooth_deg` and requires the surface itself to be smooth before the normal split is
declared wrong. Measured on both packs it accepts 87/128 groups and rejects 489/857 creases plus 251/262
open borders, with **zero** smooth-seam groups above 30° left behind on slim and the 11 known
bad ones on base caught.

### 5.4 What this fix deliberately does **not** do

* **It does not make handedness uniform within an island.** §3.2 shows 18/26 islands carry both
  signs, but the external reference packs show the same signature, so a blanket "pick the
  majority sign" pass would change working geometry. If a specific flipped region is confirmed
  in-game, address it with a targeted, position-gated fix in its own document.
* **It does not touch stacked layers.** They are already unified (§3.3 ii).
* **It does not re-derive the stored normals.** `unify_coincident_normals` only replaces the
  normal of *duplicate copies* of one 3D position with their mean. The single-copy normal is
  never changed, and no vertex position, UV, face or weight is touched.
* **It does not renumber vertices.** Grouping copies without welding keeps the index buffer,
  the atoms, the material slices and the skin palette untouched.

---

## 6. Verification

### 6.1 Route A — offline, executable today

| # | Check | Pass condition |
|---|---|---|
| A1 | Reproduce §2 | `\|N·U\|` and `\|N·V\|` max `< 1e-4` on both packs **today** (the existing gate). |
| A2 | Reproduce Defect A | `\|U·V\|` >30° on ≥ 676 verts (slim) / ≥ 1606 (base) **today**. |
| A3 | Reproduce Defect B | slim: 110 smooth UV-seam groups, 0 above 30°; base: 159 smooth, **11** above 30°. |
| A4 | Fix A applied | after rebuild: `max\|U·V\| < 1e-4` on **all four** drawables (slim body, slim fps, base body, base fps); `max\|U×V\| - 1\| < 1e-4` (U and V remain unit). |
| A5 | Fix A preserves the UV map | the **U** channel must match the pre-fix build to within float32 quantization: `np.abs(old_uvdir_u - new_uvdir_u).max() < 1e-6` and the angular change `< 1e-4` degrees. U is kept and only re-projected; a larger change means the implementation rotated U — reject it. **Byte equality is the wrong bar**: the stored U is float32, so re-projecting it perturbs the last bits (measured 5.48e-08, 0.000004°). |
| A6 | Fix A preserves mirroring | count of `(U×V)·N < 0` verts stays within 5 % of the pre-fix count per drawable (slim body 5256, slim fps 1123, base body 6795, base fps 2677). **Measured expectation: +29 verts** on the slim body (5256 -> 5285), i.e. 0.4 %. Those are vertices whose V was within a hair of the `N×U` line, where the sign test legitimately may go either way. A large **drop** means mirroring was destroyed — that is the failure this row guards. |
| A7 | Fix B applied | slim: 0 unified groups above 30° (already 0 before the fix); base: **0** (was 11 after unification). |
| A8 | Fix B does not flatten creases | the number of unified groups is **exactly 87** (slim) and **exactly 128** (base), matching §3.4's census. A larger number means a crease or a border slipped through the new gate; a smaller one means a legitimate smooth seam is still exempted. |
| A9 | No geometry change | vertex count, face count, UVs, positions, atoms and material slices are **identical** to the pre-fix build for both packs. |
| A10 | Suite | `577 passed, 85 skipped` (run with `--ignore=examples --ignore=tests/test_render_mesh_skeleton.py`). |
| A11 | **New gate exists** | add the assertions in §6.3; they must fail on the current packs and pass after the fix. |

### 6.2 Route B — render

Tangent-space error is a *lighting* defect, so a plain textured render will not show it. Render
the **normal map applied through the basis** and compare against the same surface lit with a
flat normal:

```python
import sys, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, "tools/pd2-las")

import preview_textured as pt

MODEL = Path("/tmp/chr/Christie_LAS_Slim/assets/units/christie_slim/skins/christie_slim/christie_slim.model")
meshes = pt.material_meshes(MODEL)
# Same camera for before/after; the arm cuff seam and the shoulder are the
# places where a skewed basis shows as a lighting crease.
for view in ("front", "threequarter"):
    ...
```

| # | Criterion | Pass condition |
|---|---|---|
| B1 | Shoulder / upper arm | no lighting crease that does not correspond to a geometric crease. |
| B2 | Cuff rim | the rim's highlight is continuous around the circumference; a skewed basis makes it pinch at one clock position. |
| B3 | Before/after | render the pre-fix and post-fix model with the *same* camera and diff them; differences must be confined to the **normal-mapped shading**, with silhouettes identical. A silhouette change means positions moved — reject. |
| B4 | In game | normal-mapped detail on the sleeve/shoulder reads consistently under a moving light. |

### 6.3 The missing gate (add these tests)

The root cause of both defects is that the assertions in the repo test the wrong thing. Add:

```python
def test_our_packs_have_an_orthonormal_tangent_basis(self):
    """N.U, N.V *and* U.V must all be zero; U and V must be unit length.

    The existing assertions only cover N.U and N.V, which a plain projection
    satisfies exactly - that is how a 5-20 degree shear shipped in every pack
    this repo builds.
    """
    import zipfile
    import numpy as np
    import diesel_model as dm

    specs = [
        ("Christie_LAS_Slim.zip", "Christie_LAS_Slim",
         "assets/units/christie_slim/skins/christie_slim/christie_slim.model"),
        ("Christie_LAS_Slim.zip", "Christie_LAS_Slim",
         "assets/units/christie_slim/skins/christie_slim/fps_christie_slim.model"),
        ("Christie_LAS.zip", "Christie_LAS",
         "assets/units/christie/skins/christie/christie.model"),
        ("Christie_LAS.zip", "Christie_LAS",
         "assets/units/christie/skins/christie/fps_christie.model"),
    ]
    for zip_name, prefix, model_rel in specs:
        with zipfile.ZipFile(REPO / "dist" / zip_name) as z:
            mf = dm.ModelFile.read(z.read(f"{prefix}/{model_rel}"))
        for sec in mf.by_type(dm.GEOMETRY):
            geo = dm.decode_geometry(sec.payload)
            n = np.asarray(geo["normals"], dtype=np.float64)
            u = np.asarray(geo["uvdir_u"], dtype=np.float64)
            v = np.asarray(geo["uvdir_v"], dtype=np.float64)
            tag = f"{zip_name}:{model_rel}"
            assert np.abs(np.linalg.norm(u, axis=1) - 1.0).max() < 1e-4, f"{tag}: U not unit"
            assert np.abs(np.linalg.norm(v, axis=1) - 1.0).max() < 1e-4, f"{tag}: V not unit"
            assert np.abs((n * u).sum(1)).max() < 1e-4, f"{tag}: N.U"
            assert np.abs((n * v).sum(1)).max() < 1e-4, f"{tag}: N.V"
            assert np.abs((u * v).sum(1)).max() < 1e-4, f"{tag}: U.V  <- the missing one"
```

Add a second test for the seam rule:

```python
def test_no_hard_normal_split_on_a_smooth_uv_seam(self):
    """A smooth surface must not carry a hard normal split across its UV seam."""
    ...  # §5.2's helper, asserting zero groups with dihedral <= 15 and split > 30
```

Both must be shown to **fail on the current packs** before the fix and pass after — a test that
passes before the change proves nothing.

---

## 7. Rejected alternatives

### 7.1 Rejected: orthonormalize by re-projecting V against N and U, keeping V
Sequential Gram–Schmidt on V works numerically but rotates **U**, and U is the channel the UV
layout is authored against. Measured consequence would be a small, hard-to-attribute shift of
the normal map's red axis on every vertex. Fix U, rebuild V (§5.1).

### 7.2 Rejected: rebuild both U and V from the face UVs after orthonormalizing
Equivalent to recomputing `compute_uv_directions`, but then *both* channels change and A5's
byte-identity check on U is lost — you can no longer prove the UV layout was preserved. Keep the
existing accumulation and fix only the frame.

### 7.3 Rejected: weld coincident vertices to remove the split entirely
Welding would remove the defect at the source, but it renumbers vertices and therefore breaks
every atom, material slice and skin-palette index in the pack. The 1.13–1.15× vertex overhead is
the *correct* PD2 representation; seam splits are normal and the reference packs have them too.

### 7.4 Rejected: unify all coincident normals (drop the interior/border distinction)
Would flatten 489 real creases (slim) and 857 (base) into a mean direction. Explicitly the
worse outcome — see §3.3.

### 7.5 Do not "unify" `test_glove_adapter.py`-style flags here
Unrelated, listed only because a grep for "seam" and "basis" touches several files. This plan
changes geometry metadata only; it does not touch materials, the glove hook, or the LAS Lua.

---

## 8. What is NOT reproducible from this checkout

| Missing | Consequence |
|---|---|
| ~~`references/1.zip`–`5.zip` … packs cannot be rebuilt~~ | **Retracted 2026-11-10.** Christie rebuilds **byte-identically** (`build_christie_las.py --variant slim --dist /tmp/...` → sha256 `5e55745f…b4d`, `dist/` clean), and `tools/pd2-las/recover_env.sh` restores the environment from a wipe in ~17 s. So Fix A and Fix B can be validated by **real rebuild + re-read**, not only by patching shipped-zip geometry dicts. The scratch-dir discipline still applies whenever you do overwrite a pack. |
| The game | B4 cannot be executed here. Tangent-space error is only fully confirmable in game. |
| ~~A vanilla Overkill-authored `npc_criminal_*.model`~~ **— RESOLVED 2026-11-10** | **The `2b.rar` template is a vanilla, Overkill-authored body and it settles this.** Measured on `2b.model` `g_body`, 27,741 verts: `max |U·V| = 0.000000`, i.e. **exactly 0.0000° from orthogonal on every vertex**. So the "0.00°" property is not an artefact of third-party ports — it is what the engine's own authored geometry does. Contrast, same measurement on the packs this repo builds: `Christie_LAS` max **90.00°** / mean 14.78° (10,361 verts), `Christie_LAS_Slim` max **90.00°** / mean 11.61° (7,695), FPS units 20.38° / 14.93°.

**Distribution — a fix must handle a degenerate core, not just shear.** All channels are unit-length (no zero-length tangents), so 90° is a real measurement, not a normalisation artefact. Of the shipped vertices: **116 (slim) / 327 (base)** have `|U·V| = 1.0`, i.e. U and V are *parallel* — a fully degenerate tangent basis, not merely skewed. By threshold: `>30°` covers 8.8 % (slim) / 15.5 % (base), `>60°` covers 3.8 % / 5.8 %, and only ~14 % sit under 1°. Vanilla 2B is `== 0` in every bucket. **Fix B must therefore reconstruct U and V from the UV gradient rather than re-orthogonalising the stored pair** — Gram-Schmidt on a pair that is already parallel yields an arbitrary perpendicular and will move those vertices visibly. |
| ~~`references/2b.rar` unreadable~~ **— VERIFIED 2026-11-10** | **Retracted: the template is readable and the claim is now measured, not inherited.** `bootstrap.sh` unpacks the RAR with `node-unrar-js` (no system extractor needed). Measured on `2b.model` `g_body` (27,741 verts, 35,260 tris): **22,486 total coincident pairs** across 4,783 groups, of which **0 diverge** by >30° — `{'interior': 0, 'border': 0, 'pairs': 0}`. The 2026-11-07 figure is exactly right. This is the reference anchor the whole seam argument rests on, and it now holds independently. |

### 8.1 Re-measure the reference anchor (run this first)

The anchor that the whole seam argument rests on is now cheaply checkable. It takes ~1 s:

```python
"""Verify the 2B seam-normal anchor. Needs /tmp/2bsrc (recover_env.sh)."""
import sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, "/home/user/universal-modder/tools/pd2-port")
sys.path.insert(0, "/home/user/universal-modder/tools/pd2-las")
import diesel_model as dm, build_christie_las as bcl, build_models as bm

mf = dm.ModelFile.read(open(
    "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b/2b.model", "rb").read())
hl = dm.decode_custom_hashlist(
    mf.by_type(dm.CUSTOM_HASHLIST)[0].payload)["names"]
for sec in mf.by_type(dm.MODEL_DATA):
    md = dm.decode_model_data(sec.payload)
    if next((n for n in hl if dm.hash64(n) == md["name_hash"]), "") != "g_body":
        continue
    gp = dm.decode_passthroughgp(mf.by_id(md["passthroughgp"]).payload)
    geo = dm.decode_geometry(mf.by_id(gp["geometry"]).payload)
    top = dm.decode_topology(mf.by_id(gp["topology"]).payload)
    g = bm.Group(name="2b",
                 verts=[tuple(map(float, v)) for v in geo["verts"]],
                 normals=[tuple(map(float, n)) for n in geo["normals"]],
                 faces=[tuple(map(int, f)) for f in
                        np.asarray(top["indices"], int).reshape(-1, 3)])
    break

groups = defaultdict(list)
for i, p in enumerate(np.asarray(g.verts, float)):
    groups[tuple(np.round(p, 5))].append(i)
total = sum(len(v) * (len(v) - 1) // 2 for v in groups.values())
assert total == 22486, total                       # the 2026-11-07 figure
assert bcl.coincident_normal_report(g)["pairs"] == 0
print("ANCHOR OK:", len(g.verts), "verts,", total, "coincident pairs, 0 diverging")
```

Measured output: `ANCHOR OK: 27741 verts, 22486 coincident pairs, 0 diverging`.

**Note on the two counts.** `coincident_normal_report` returns *diverging* pairs, so on 2B it
returns `pairs: 0` — that is not a contradiction with "22,486 pairs", which counts **all**
coincident pairs. Do not "fix" the report to return 22,486; the 22,486 is the population and the
`0` is the finding.

---

## 9. Execution order

1. **Fix A** (§5.1) — largest defect, smallest change, fully verifiable offline (A1–A6, A9).
2. **Write the missing gate** (§6.3) and prove it fails on the current pack, passes after.
3. **Fix B** (§5.2) — verify A7/A8; confirm the eligible-group count is exactly 87/128.
4. Rebuild both packs, regenerate both `dist/*.zip.sha256`
   (`build_christie_las.py:3446-3449`).
5. Run A10 (`577 passed, 85 skipped`) and B1–B3.
6. Report B4 as unverified unless the user can launch the game.

> **Prior belief to correct before starting:** the 2026-11-07 Phase 3 text asserts the defect
> is "73 `33°–50°` spine/sleeve UV-seam splits". That number is **not** what the shipped mesh
> shows: §3.3 measures **0** smooth-seam groups above 30° on slim and **11** on base. Do not
> tune a rule to reproduce 73 — measure the pack you are actually fixing.

---

## 10. Cold-start verification log

Run 2026-11-09 on this checkout. Each executable block was extracted from **this document** and
run as a subprocess from the repo root; nothing was retyped.

### 10.1 Results

| block (indexed by content) | result |
|---|---|
| §2 reproduce | **PASS** — `SLIM 5.26/48.25/90.00/676`, `BASE 5.91/67.28/90.00/1606`; `\|N·U\|` and `\|N·V\|` both `0.000000` |
| §5.2 `_surface_border_and_creases` | **PASS** — runs unmodified and reproduces the §3.4 census exactly: slim `837 groups / 251 border / 489 crease / UNIFY 87`, base `1286 / 262 / 857 / UNIFY 128` |
| §5.1 Fix A applied to the shipped geometry | **PASS** — `\|U·V\|` `1.00` → `1.67e-16`; `\|U\|`, `\|V\|` deviation `3.3e-16`; `\|N·U\|`, `\|N·V\|` `1.7e-16` |
| §6.3 new gate | **FAILS on all 8 non-degenerate drawables today** (as required) — every one fails on `U.V` only, with `max = 1.0000` |

### 10.2 Fix A on the shipped slim body, before/after

```
  BEFORE   |U|dev=4.20e-08 |V|dev=4.61e-08 |N.U|=7.22e-08 |N.V|=7.22e-08 |U.V|=1.00e+00 mirrored=5256
  AFTER    |U|dev=3.33e-16 |V|dev=2.22e-16 |N.U|=2.22e-16 |N.V|=1.67e-16 |U.V|=1.67e-16 mirrored=5285
```

Mirroring moves by **+29 verts (0.4 %)** — A6's documented expectation.

### 10.3 Notes for the executing agent

* **There are five geometry sections per pack, not four.** Four substantive drawables (body,
  body-shadow, fps, fps-shadow) plus a **tiny 8-vertex section** that is exactly orthogonal
  (`U.V = 0.0000`). A test that loops `by_type(GEOMETRY)` will visit all five; do not assert a
  fixed count of four.
* **`gen.save` / `encode_geometry` round-trips are lossy at float32.** The stored `U` is float32,
  so re-projecting an already-projected `U` moves it by `5.5e-08` (`0.000004°`) purely from
  quantization. That is why A5 is a tolerance, not byte equality. Do not "fix" that difference.
* **Index code fences by content, never position.** This document has ten Python fences in order:
  the `N·U`/`N·V` assertion excerpt, the §2 reproduce block, the current-code excerpt, the
  index-space border excerpt, Fix A, the §5.2 helper, the §5.2 usage, the §6.2 render sketch,
  the §6.3 test, and the second §6.3 test stub. Pulling "the fifth block" happens to be Fix A
  today; do not rely on it.
* **`_surface_border_and_creases` takes a `Group`-like object** and only reads `g.faces`; the
  helper signature in §5.2 is `(g, verts, tol, smooth_deg)` and returns
  `(border, crease, gid_of)`. The earlier draft returned a 2-tuple and iterated a
  `key -> gid` dict as if it were `gid -> [verts]`; both are fixed, and the version in this
  document is the one that was executed.
* **The 2026-11-07 Phase 3 claim of "73 splits" does not reproduce.** §3.4 measures 87 eligible
  groups on slim of which **0** exceed 30°. Do not tune a threshold to manufacture 73.
* **Retracted 2026-11-10** — `references/2b.rar` is readable and the reference anchor is now
  measured directly: 2B `g_body` has 22,486 coincident pairs and 0 of them diverge (see §8).
  The earlier note in this file saying the figure was inherited and unverified is withdrawn —
  the anchor the whole seam argument depends on now holds on its own measurement.

