# Christie LAS (`Slim` & `Base`) — Forearm Vertex Normals & Sleeve-Seam Repair Plan (2026-11-07)

> **Audience:** an implementation agent picking up this repository cold.
> Every file path, line number, vertex/face index, metric, and geometric trap in
> this plan has been empirically verified against commit `d0fe1e6` and the
> shipped `dist/Christie_LAS_Slim.zip` / `dist/Christie_LAS.zip` artefacts.

## 0. Scope, Prerequisites & Context Links

### Problem Statement
In-game screenshots of `Christie_LAS_Slim` (`docs/pd2-las/screenshots/christie_slim_*.png`) exhibit:
1. **Symmetric dark/black shading patches on both rear forearms** (`mtr_c02_01` blazer sleeves around `[±36.5, -4.5, 120.3]`) and corrupted normals on the 1st-person viewmodel (`fps_christie_slim.model`).
2. **Dark/inverted shading strips, backface-culled pinholes, internal cuff webs, and UV-stretched triangles along the stitched inner-sleeve seams**, plus **48 out-of-bounds Direct3D 9 vertex indices** in `s_body` introduced by the same stitch pass.
3. **Hard shading steps (`33°–50°`) along manifold UV seams** (notably the blazer centre-back spine and sleeve seams) that `unify_coincident_normals` skipped.
4. **Non-orthogonal vertex tangent bases `(N, T, B)`** (`|dot(T, B)|` `p95 = 0.746`, `max = 1.000` vs vanilla Overkill `0.00000`), skewing tangent-space normal-map lighting across the sleeves and stitched strips.

### Related Audit Documents
- [`2026-11-07-christie-slim-screenshot-review.md`](2026-11-07-christie-slim-screenshot-review.md) — 15-frame visual defect catalogue.
- [`2026-11-07-christie-slim-diagnosis.md`](2026-11-07-christie-slim-diagnosis.md) — mesh shell/slit background.
- [`../pd2-las/CHRISTIE.md`](../pd2-las/CHRISTIE.md) & [`../../tools/pd2-las/MODLOG.md`](../../tools/pd2-las/MODLOG.md) — Christie LAS build history and journal.

### Sandbox Bootstrap (Run First)
If `.venv` or `/tmp/2bsrc` is missing in a fresh workspace:

```bash
bash tools/pd2-las/bootstrap.sh
# Expected template directory for rebuilds and full tests:
# /tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b/{2b.model,fps_2b.model}
```

If `bootstrap.sh` does not extract `references/2b.rar` to `/tmp/2bsrc`, extract it with Python (`rarfile` / `7z` / `unar` / `bsdtar`, whichever is installed; e.g. `mkdir -p /tmp/2bsrc && 7z x -y references/2b.rar -o/tmp/2bsrc`).

---

## 1. Pass-by-Pass Empirical Root-Cause Trace

Tracing `groups["body"]` across all 11 geometry stages of `tools/pd2-las/build_christie_las.py::build_variant` (`variant="slim"`, arm filter `|x| > 20` and `z > 95`) pinpoints the exact stages where vertex normals (`vn`) diverge from area-weighted geometric normals (`n_geom`) and triangle face normals (`fn`):

| Step in `build_variant` | Arm Verts `dot(vn, n_geom) < 0.5` | Arm Faces `fn · vn < 0.3` | Arm Faces `fn · vn < 0` | Mechanism |
|---|---:|---:|---:|---|
| `1. bm.transfer_group` + `widen_elbow_blend` | `87` | `142` | `69` | Mostly hand/finger creases + 13 inner-elbow crease tris folded when skinning DOA5 T-pose into PD2's 72° bind pose |
| `2. straighten_segments` | `106` | `145` | `65` | Updates `g.normals` via `_recompute_normals` |
| `3. centre_segments` | `106` | **`222`** | **`103`** | Shifts forearm slabs up to `3.11 cm` **without** updating `g.normals` |
| `4–6. trim_elbows` → `taper_cuff` → `slim_group` | `90` | `217` | `106` | Three more vertex-deforming passes leave `g.normals` untouched |
| `7–8. cut_hands` → `extend_sleeves_to_wrist` | **`19`** | `112` | `62` | Removing hands drops discordant arm verts to **19** (double-sided cuff rims + inner-elbow crease) |
| **`9. rebind_arms_at_idle`** | **`123` (`+104`)** | `121` | `56` | **Rotates `g.verts` by `60.3°–67.7°` without rotating `g.normals`; `_recompute_normals` (`dots < 0.5`) snaps 104 smooth forearm verts back to stale 72°-bent normals** |
| **`10. stitch_sleeve_seams`** | `127` | **`164` (`+43`)** | **`88` (`+32`)** | **Adds 45 false-positive internal cuff bulkheads & inverted patch caps, stretches bridge UVs `Δu ≈ 0.20`, writes 48 OOB `s_body` indices, never updates normals** |
| `11. unify_coincident_normals` | `127` | `164` | `88` | Treats every `idx_count == 1` UV-split edge as an open garment border, skipping 73 manifold UV-seam pairs |

### Concrete Diagnostic Anchors (Verify Before & After)
1. **Rear-forearm black patches (`rebind_arms_at_idle`, `:1883–2040`)**:
   - Right sleeve `mtr_c02_01` `fi = 2467, 2468` at `[+36.5, -4.4, 120.4]` and Left sleeve `fi = 3218, 3219` at `[-36.5, -4.5, 120.3]`.
   - Pre-rebind: `fn · vn = +0.98..+1.00`.
   - Shipped post-rebind (buggy): `fn = [∓0.03, -1.00, -0.01]`, `vn = [±0.65, -0.30, -0.70]`, **`fn · vn = +0.29`** (reverted to 72°-pose normal because arm rotation `> 60°` tripped `dots < 0.5` in `_recompute_normals` at `:1066`).
   - With LBS-rotated reference normals (`n_rot`): **`fn · vn = +0.99..+1.00`**, and post-rebind discordant arm verts stay at **`20`** instead of jumping to **`123`**.
   - `fps_christie_slim.model` extracts `fps_arms` directly from `groups["body"]` (`:3366`), inheriting `128 / 1,491` (`8.6%`) corrupted normals in the shipped pack.

2. **Four distinct defects in `stitch_sleeve_seams` (`:2125–2558`)**:
   - **2a. Radial cuff/lining bulkheads (`_rim_pairs`, `:2125`)**: Across `z = 103.3..116.7`, outer cuff rims and inner cuff/shirt lining rims have roughly parallel normals (`n_i · n_j >= 0.2`), while the chord $d = v_j - v_i$ steps **radially** between layers rather than tangentially across a slit. Bridging them builds internal bulkhead fins orthogonal/opposed to the surface normals:
     - `mtr_c02_01`: `fi = 8770..8777` (Left cuff vent, `fn · vn = -0.58..+0.47`), `fi = 8790..8794` & `8807..8812` (Right cuff vent/lining, `fn · vn = -0.28..+0.07`).
     - `mtr_c02_02`: **all 16 stitched triangles** (`fi = 10574..10589`, French shirt cuffs at `[±36.6..42.5, +0.2..+0.9, 106.0..115.4]`, `fn · vn = -0.24..+0.20`).
   - **2b. Inverted caps over tiny standalone cuff patches (`_fill_ring`, `:2232`)**:
     - Boundary loops at `v5113` (Left, `comp = 12 verts / 9 tris`), `v1622` (Right, `comp = 9 verts / 6 tris`), and `v1625` (Right, `comp = 9 verts / 6 tris`) around `[±40.3, ±1.2, 113.4]` are **outer perimeters of standalone decorative cuff-strap patches** (merged into `_sleeve_shells` only via shared corner positions), *not* holes in the sleeve tube. Capping them emits `6.9–9.4 cm²` inside-out sheets (`fi = 8813..8822`, `fn · vn = -0.97..-0.54`).
     - By contrast, the 4-vertex loop at `v1966` (`[1966, 1965, 1985, 1984]` at `[-30.8, 3.1, 124.9]`) sits inside the **698-triangle** main sleeve component (`fn · vn = +0.63..+0.85` on `slim`) and is a genuine pinhole that **must** remain closed.
   - **2c. Full-island UV wrap-stretch on valid outer-sleeve bridges**:
     - The **24 genuine underarm bridge triangles** (`fi = 8778..8789` Left, `8795..8806` Right, `z = 117.7..130.8`) have clean outward normals (`fn · vn = +0.87..+1.00`), but their opposite rims lie on opposite edges of the cylindrical sleeve UV island (`Δu = 0.185..0.212`, `~205 texels`). Connecting them directly compresses and mirror-reverses the entire sleeve width across a 1–3 cm strip and flips `face_u` tangents along both rims.
   - **2d. Cross-slice D3D9 OOB indices in `s_body` (`_insert_faces`, `:2165`)**:
     - `_insert_faces` looks up the target slice by material slot name (`si = next(k for k, s in enumerate(g.mat_slots) if s == slot)`). In `groups["shadow"]` (`s_body`), **all 4 slices share `slot == "shadow_caster"`**, so slice-1 (`cri_02_02_base`, vertices `[5182..6257]`) faces were spliced into slice-0 (`base_vertex = 0, slice_len = 5182`), producing 48 out-of-bounds vertex references in D3D9 `DrawIndexedPrimitive`.

3. **UV-seam blindness in `unify_coincident_normals` (`:2342–2405`)**:
   - `border = {v for e, n in count.items() if n == 1 for v in e}` counts edges by **vertex index** `(x, y)`. Every UV/material split duplicates vertex indices along the seam, giving both halves `count == 1` and excluding 100% of manifold UV-split seams (73 pairs along the blazer spine and sleeves with `33°–50°` normal splits).

4. **Non-orthogonal tangent basis in `build_models.py` (`:2741–2755`)**:
   - `assemble_model` projects `u_arr` and `v_arr` orthogonal to `n_arr`, but never orthogonalizes `v_arr` against `u_arr` and leaves zero vectors if `u_arr ∥ n_arr`.

---

## 2. Step-by-Step Implementation Specification

> **Rule reminder (`AGENTS.md`):** sequence edits to any single file (`build_christie_las.py`, `build_models.py`, etc.) one step at a time — never issue parallel edits to the same file.

### Phase 1 — LBS Normal Rotation in `rebind_arms_at_idle` & Incremental Pre-Rebind Normal Updates
**File:** `tools/pd2-las/build_christie_las.py`

1. **Rotate stored normals by the vertex skinning matrix inside `rebind_arms_at_idle` (`:1905–2025`)**:
   - Note convention: `diesel_model.py` / `build_christie_las.py` uses **row-vector** $4 \times 4$ matrices (`posed_i = sum_k w_k * ([v_i, 1] @ transforms[pi_k])`).
   - Before modifying `g.verts`, snapshot `n_pre = np.asarray(g.normals, dtype=np.float64)` and compute `n_rot`:
     ```python
     n_pre = np.asarray(g.normals, dtype=np.float64)
     n_rot = np.zeros_like(n_pre)
     for i in range(len(n_pre)):
         R = np.zeros((3, 3), dtype=np.float64)
         tot = 0.0
         for pi, w in g.weights[i]:
             R += w * transforms[pi][:3, :3]
             tot += w
         R /= tot or 1.0
         # Row-vector covector transform: n' = n @ (R^-1)^T
         nr = n_pre[i] @ np.linalg.inv(R).T
         ln = float(np.linalg.norm(nr))
         n_rot[i] = nr / ln if ln > 1e-12 else n_pre[i]
     ```
   - At `:2022` (after Taubin relaxation, `_elbow_coverage_correction`, and `_apply_slim_fold_solution`), replace:
     ```python
     _recompute_normals(g, np.asarray(g.normals, dtype=np.float64))
     ```
     with:
     ```python
     _recompute_normals(g, n_rot)
     ```
   - Why this works: every smooth forearm panel now has `dot(n_new, n_rot) >= 0.5` and adopts the exact post-relaxation/post-fold area-weighted normal, while genuine double-sided cuff hems and folded inner-elbow slivers (`dot < 0.5`) fall back to idle-pose-aligned `n_rot` rather than stale 72°-bent normals.

2. **Refresh `g.normals` incrementally across pre-rebind deformations in `build_variant` (`:3275–3305`)**:
   - On `groups["body"]` (when `len(g.normals) == len(g.verts)`), call `_recompute_normals(g, np.asarray(g.normals, dtype=np.float64))` after:
     - `centre_segments` / `trim_elbows` / `taper_cuff`,
     - `slim_group` (for `variant == "slim"`), and
     - `bm.extend_sleeves_to_wrist`.
   - This tracks gradual `15°–35°` surface tilts per pass so five deformations never accumulate past the `60°` (`dot < 0.5`) guard before `rebind_arms_at_idle`.

---

### Phase 2 — Geometrically Gated, Slice-Safe, UV-Local `stitch_sleeve_seams`
**File:** `tools/pd2-las/build_christie_las.py` (`:2125–2558`)

#### 2.1 Replace `_insert_faces(g, faces, slot)` with Slice-Indexed `_insert_into_slice` & Strict Atom Bounds
1. Track the owning **slice index `si: int`** (`slice_of[owner_face[kk]]`) on each boundary loop instead of collapsing to `slot: str = g.mat_slots[si]`.
2. Implement `_insert_into_slice(g: bm.Group, si: int, new_verts: list[dict], new_faces: list[tuple[int, int, int]]) -> tuple[int, int]`:
   - Each entry in `new_verts` carries `{"vert": (x,y,z), "normal": (nx,ny,nz), "uv": (u,v), "weights": [...]}`.
   - Let `src, base_v, base_i, tris, nverts = g.slices[si]`.
   - If `K = len(new_verts) > 0`:
     - Insert vertex attributes at `v_at = base_v + nverts` into `g.verts`, `g.normals` (if non-empty), `g.uvs` (if non-empty), and `g.weights`.
     - Remap any vertex index `idx >= v_at` in **existing** `g.faces` (and in pending `extra` lists for other slices, or run `_insert_into_slice` in **descending `v_at` / `si` order** — or even simpler: allocate cloned vertices per slice in one pass from highest `base_v` slice down to `0`, or shift indices deterministically on insertion) by `+K`.
     - Update `g.slices[si]` `nverts -> nverts + K`, and for every slice `k != si` with `bv2 > base_v` (or `bv2 == base_v and k > si`), shift `bv2 -> bv2 + K`.
   - Splice `new_faces` at `at = (base_i + 3 * tris) // 3`, update `tris -> tris + len(new_faces)`, and shift `bi2 -> bi2 + 3 * len(new_faces)` for every slice `k != si` with `bi2 >= base_i + 3 * tris`.
3. Harden `_check_slices(g, tag)` (`:2191`):
   - Keep the contiguous `base_i` tiling check, **and** verify for every slice `(src, base_v, base_i, tris, nverts)` that every vertex index referenced in `g.faces[base_i // 3 : base_i // 3 + tris]` satisfies `base_v <= idx < base_v + nverts`. Fail with `SystemExit` if any index is out of bounds.
   - Update the outdated docstring on `_insert_faces` (`:2170`) that claimed cross-block indices were legal.

#### 2.2 Reject Radial Cuff-Vent / Lining Bulkheads (`_rim_pairs` & Quad Loft)
1. In `_rim_pairs(v, n, ring, max_gap_cm, min_dot)` (`:2125`):
   - Change default `min_normal_dot` in `stitch_sleeve_seams` from `0.2` to `0.4`.
   - Add a **surface-tangency filter** on non-touching candidate pairs: when `gap = ||v[ring[j]] - v[ring[i]]|| > weld_cm`, compute:
     ```python
     d = v[ring[j]] - v[ring[i]]
     n_avg = n[ring[i]] + n[ring[j]]
     n_len = float(np.linalg.norm(n_avg))
     if n_len < 1e-9:
         continue
     n_hat = n_avg / n_len
     # Genuine cloth slits separate tangentially across the sheet;
     # double-walled cuff shells + linings step radially along n_hat.
     if abs(float(d @ n_hat)) / gap > 0.45:
         continue
     ```
2. In the quad loft loop (`:2515–2538`):
   - Helper `_face_vn_dot(v, n, tri) -> float`: unit geometric normal `(v[b]-v[a]) × (v[c]-v[a])` dotted with unit mean vertex normal `mean(n[a], n[b], n[c])`.
   - Evaluate **both** candidate splits of quad `(a, b, c, d)`:
     - Split 1: `[(a, d, c), (a, c, b)]` (and reversed winding if needed for `_closable`)
     - Split 2: `[(a, d, b), (d, c, b)]` (and reversed winding if needed for `_closable`)
   - Filter each split to triangles with `_tri_area(v, t) >= min_face_cm2` that satisfy `_closable(tris, count, dirn)`, score each valid split by `min(_face_vn_dot(v, n, t) for t in tris)`, pick the higher-scoring split, and **require `best_score >= 0.5`**.
   - **Verified behaviour:** Rejects 100% of `mtr_c02_01` cuff-vent chords (`8770..8777`, `8790..8794`, `8807..8812`) and all 16 `mtr_c02_02` shirt-cuff bulkheads (`10574..10589`), while keeping all 24 outer-sleeve underarm bridge triangles (`fn · vn = +0.87..+1.00`).

#### 2.3 Reject Standalone Decorative-Patch Caps While Preserving True Pinholes (`_fill_ring`)
1. Precompute **topological** connected-component triangle counts `comp_tris` over `g.faces` (union-find by **vertex index** `a, b, c` — **not** 3D-coincident position shells):
   - Standalone decorative cuff tabs (`v5113`, `v1622`, `v1625`) have `comp_tris` = `9`, `6`, `6`.
   - The main sleeve shell containing the inner-elbow pinhole (`v1966`, `[1966, 1965, 1985, 1984]`) has `comp_tris = 698`.
2. Gate short-loop hole filling (`len(ring) <= max_hole_verts`, `:2491`) on:
   - `min(comp_tris[i] for i in ring) >= 32` (ensuring the loop is an interior hole in a substantial sleeve shell, never the outer perimeter of a small decorative patch).
3. Inside `_fill_ring(ring, taken, count, dirn, v, n, min_face_cm2)` (`:2232`):
   - Test all cyclic rotations `rot = order[p:] + order[:p]` (`p = 0 .. m - 1`) of `order = list(reversed(ring))`.
   - Keep rotations where all `m - 2` fan triangles pass area, `taken`, and `_closable`, and pick the rotation maximizing `min(_face_vn_dot(v, n, t) for t in fan)`.
   - Require **area-weighted mean** `sum(area_t * dot_t) / sum(area_t) > 0.0` (rejecting inside-out caps).
   - **CRITICAL TRAP — DO NOT REQUIRE `min_t(dot_t) >= 0.5` ON `_fill_ring`:**
     On `slim`, `SLIM_FOLD_DELTAS` flattens the 4-vertex inner-elbow pinhole `[1966, 1965, 1985, 1984]` to `fn · vn = [+0.632, +0.848]`. On `base` (`slim=False`), that same 4-vertex pinhole sits inside the un-flattened elbow crease with `fn · vn = [-0.315, +0.371]` (area-weighted mean `> 0.0`). Dropping that pinhole on `base` opens a **`21.50 cm²` ray leak** in `test_sleeve_tube_is_closed_along_its_length`! The combination `comp_tris >= 32` + `area_weighted_mean(fn · vn) > 0.0` rejects 100% of decorative-patch caps (`mean = -0.78..-0.73`, `comp_tris = 6..9`) while keeping `loop[58]` closed on **both** `slim` and `base` (`0.00 cm²` slit area on both).

#### 2.4 Local UV Continuation Across Bridge Quads (Eliminate `Δu ≈ 0.20` Island Wrap)
1. Only run UV cloning when `len(g.uvs) == len(g.verts)` and UVs are non-trivial (`np.ptp(uvs) > 1e-4`; `groups["shadow"]` has zeroed UVs and needs `0` cloned vertices).
2. For each valid bridge run in slice `si`:
   - From the adjacent sleeve triangles owning rim A's directed boundary edges `(a -> b)`, compute a local tangent-to-UV linear map `(du_dx, dv_dx)` ($2 \times 3$ Jacobian of `uv` with respect to 3D position on rim A's triangle, fallback `0.006 uv/cm` along local tangent if degenerate).
   - When a matched pair `(a, d)` (`a` on rim A, `d` on rim B) has `||uv[d] - uv[a]|| > 0.05` (wrapping across the sleeve UV island):
     - Reuse or create a slice-local clone `d'` of vertex `d` (`vert = g.verts[d]`, `normal = g.normals[d]`, `weights = list(g.weights[d])`) with:
       $$\text{uv}[d'] = \text{uv}[a] + J_a \, (v_d - v_a)$$
       clamped within `±0.04` of `uv[a]` so `d'` stays cleanly on local sleeve fabric.
     - Substitute `d'` / `c'` for `d` / `c` in the bridge triangles `(a, d', c')`, `(a, c', b)`.
   - Note on edge maps & vertex indices:
     - Validate `_closable` against the topological vertex IDs `(a, b, c, d)` *before* substituting `c' / d'` so manifold boundary-edge checks work identically; emit `(a, d', c')` / `(a, c', b)` with the cloned indices.
     - `stitch_sleeve_seams` runs at step 10 (*after* `_apply_slim_fold_solution` at step 9), so appending slice-local cloned vertices does **not** shift any hardcoded vertex indices in `SLIM_FOLD_DELTAS`.

#### 2.5 Post-Stitch Normal Refresh & Clone Sync
- At the end of `stitch_sleeve_seams` (when `report["new_faces"] > 0` and `len(g.normals) == len(g.verts)`):
  - Recompute area-weighted vertex normals over the stitched mesh, updating only vertices touched by welded pairs or newly added triangles where `dot(n_new, n_cur) >= 0.5`.
  - Copy the final normal between every `(d, d')` clone pair (`n_shared = normalize(n[d] + n[d'])`) so the seam edge between rim B and the bridge strip shades with zero discontinuity.

---

### Phase 3 — 3D-Manifold UV-Seam Normal Unification
**File:** `tools/pd2-las/build_christie_las.py` (`coincident_normal_report` `:2305–2340` & `unify_coincident_normals` `:2342–2405`)

1. **Distinguish true open 3D garment borders from manifold 3D UV/material splits**:
   - Compute `_coincident_groups(verts)` and assign each vertex `i` a 3D group ID `gid[i]` (`0 .. G-1`, singletons get unique IDs).
   - Build:
     - `idx_count[(min(x, y), max(x, y))]`: undirected edge count in vertex-index space.
     - `pos_dir[(gx, gy)]`: directed half-edge count in 3D group space (skipping `gx == gy`).
     - `pos_fnorms[(min(gx, gy), max(gx, gy))]`: list of unit geometric face normals of triangles incident to `(gx, gy)`.
   - Helper `_is_manifold_uv_seam_edge(gx, gy) -> bool`:
     - `gx != gy`
     - `pos_dir.get((gx, gy), 0) == 1` and `pos_dir.get((gy, gx), 0) == 1` (two panels traverse the shared 3D curve in **opposite** manifold directions — ruling out stacked open rims like `tests/test_seam_normals.py::_layers(caps=False)` where both prisms traverse `g0 -> g1` in the *same* direction `pos_dir == 2`!).
     - `len(pos_fnorms[key]) == 2` and `float(pos_fnorms[key][0] @ pos_fnorms[key][1]) >= 0.5` (the two panels meet smoothly within `60°`, ruling out sharp `150°–180°` double-sided cuff/collar hems).
   - A vertex `v` is a **garment border vertex** iff it has at least one incident triangle edge `(x, y)` with `idx_count[(min(x, y), max(x, y))] == 1` **and** `not _is_manifold_uv_seam_edge(gid[x], gid[y])`.
   - Track whether each interior vertex `i` participates in at least one manifold UV-seam edge (`on_uv_seam[i]`).

2. **Thresholding in `unify_coincident_normals`**:
   - For an interior coincident group `inner`:
     - If any vertex in `inner` has `on_uv_seam[i] == True`, unify whenever `1.0 < spread <= max_mean_deg` (eliminating all `1°–120°` steps across UV/material seams, matching the 2B reference's `0.0°` seam spread).
     - Otherwise (stacked closed interior shells with `idx_count >= 2` everywhere), keep the existing `max_deg < spread <= max_mean_deg` (`max_deg = 30.0°`) rule.
   - Keep `coincident_normal_report` using the `max_deg = 30.0°` threshold over the same `border` definition so:
     - **All 9 unit tests in `tests/test_seam_normals.py` pass unchanged** (`_layers(caps=False, tilt=90°)` has `pos_dir == 2` -> `border = 1, interior = 0`; `_layers(caps=True, tilt=10°)` has `on_uv_seam == False` -> untouched under `30°`).
     - **`tests/test_christie_las.py::test_interior_coincident_normals_agree` passes unchanged** (`report["interior"] == 0` and `report["border"] > 300` on real cuff/hem folds), while all 73 `33°–50°` spine/sleeve UV-seam splits are unified to `0.0°`.

---

### Phase 4 — Orthonormal Diesel Tangent Basis `(N, T, B)`
**File:** `tools/pd2-las/build_models.py` (`:2741–2755`)

In `assemble_model` where `du, dv = dm.compute_uv_directions(g.verts, g.uvs, g.faces)` is post-processed:
1. Normalize `n_arr` (`n_arr /= np.maximum(np.linalg.norm(n_arr, axis=1, keepdims=True), 1e-12)`).
2. Project `u_arr` orthogonal to `n_arr`:
   ```python
   u_proj = u_arr - np.sum(u_arr * n_arr, axis=1, keepdims=True) * n_arr
   u_len = np.linalg.norm(u_proj, axis=1, keepdims=True)
   ```
3. Construct deterministic unit fallback tangents wherever `u_len[:, 0] < 1e-6` (degenerate UV triangle or `u_arr ∥ n_arr`):
   ```python
   deg = u_len[:, 0] < 1e-6
   if np.any(deg):
       ref = np.where(np.abs(n_arr[deg, :1]) < 0.9,
                      np.array([[1.0, 0.0, 0.0]]),
                      np.array([[0.0, 1.0, 0.0]]))
       fb = np.cross(n_arr[deg], ref)
       fb /= np.maximum(np.linalg.norm(fb, axis=1, keepdims=True), 1e-12)
       u_proj[deg] = fb
       u_len[deg] = 1.0
   t_arr = u_proj / u_len
   ```
4. Construct strictly orthonormal bitangent `b_arr = s * (n_arr × t_arr)` preserving per-UV-island mirror handedness (matching vanilla Overkill `npc_criminal_joy_1.model`, where `max|N·B| == 0.00000`, `max|T·B| == 0.00000`, and `(N × T) · B < 0` on unmirrored islands):
   ```python
   b0 = np.cross(n_arr, t_arr)
   b0 /= np.maximum(np.linalg.norm(b0, axis=1, keepdims=True), 1e-12)
   dots_bv = np.sum(b0 * v_arr, axis=1, keepdims=True)
   sign = np.where(dots_bv > 1e-8, 1.0, -1.0)
   b_arr = sign * b0
   du = [tuple(map(float, row)) for row in t_arr]
   dv = [tuple(map(float, row)) for row in b_arr]
   ```

---

### Phase 5 — FPS Viewmodel Propagation Check
**File:** `tools/pd2-las/build_christie_las.py` (`:3364–3382`)

- `fps_arms = bm.extract_bones(groups["body"], bm.is_fps_arm_bone, "arms")` and `fps_shadow = bm.extract_bones(groups["shadow"], bm.is_fps_arm_bone, "shadow")` run **after** Phases 1–3 and write geometry through `bm.assemble_model` (Phase 4).
- Verify that `fps_christie_slim.model` and `fps_christie.model` pass `bm.audit_model(fps_path)` (including the new per-atom vertex-slice bounds check) and have zero stale-bind normals on the forearms.
- *Cross-defect note:* `groups["body"].normals` are now in the 12° idle-arm frame; if a separate task later applies `rebind_idle_arm_rest(fps_tpl)` to align `fps_tpl`'s `SkinBones` inverse-bind matrices with `Object3D`, **do not** rotate `fps_arms.normals` a second time.

---

### Phase 6 — Diagnostics, Automated Tests & Pack Rebuild

#### 6.1 Diagnostic & Model-Audit Hardening
1. **`tools/pd2-las/build_models.py::audit_model`**:
   - Extend `audit_model` so every `PASSTHROUGH_GP` / `MODEL_DATA` render atom validates `atom.base_vertex <= idx < atom.base_vertex + atom.slice_len` over its triangle range `atom.base_index // 3 .. (atom.base_index + atom. tri_count * 3) // 3`.
2. **`tools/pd2-las/diagnose_mesh.py::sleeve_slit_area` (`:178`)**:
   - Add keyword parameter `cull_backfaces: bool = False` (default `False` preserves existing call signatures).
   - When `cull_backfaces=True`, cast rays **inward** from outside the sleeve (`origin = o + 15.0 * ray_dir`, `d = -ray_dir`, `0 < t < 15.0`) and count only **front-face** hits (`det = e1 · (d × e2) > 1e-9`), catching inside-out caps or reversed bridge triangles that D3D9 backface culling renders invisible.

#### 6.2 New Automated Regression Tests
1. **`tests/test_seam_normals.py`**:
   - `test_manifold_uv_split_seam_is_unified`: Build two adjacent quads sharing a 3D seam edge with duplicated vertex indices (`idx_count == 1` on each quad, opposing 3D half-edges, `40°` normal divergence, `20°` face angle) and assert `unify_coincident_normals` unifies the seam pair to `< 1e-6°` while leaving outer perimeter vertices untouched.
2. **`tests/test_christie_las.py`** (parametrized over `which in sorted(PACKS)` — both `"slim"` and `"base"`):
   - `test_forearm_normals_align_with_surface`: Decode `g_body` from both TPP (`{item_id}.model`) and FPS (`fps_{item_id}.model`); assert that on rear/outer forearm `mtr_c02_01` faces (`|x| > 24`, `108 < z < 132`, non-crease faces with area `> 0.05 cm²`), at least `98%` satisfy `fn · vn >= 0.70`, and specifically in the rear-forearm patch window (`32 < |x| < 41`, `y < -2.0`, `116 < z < 125`) **every** face satisfies `fn · vn >= 0.90` (was `0.29`).
   - `test_stitched_sleeve_seams_have_clean_normals_and_local_uvs`: Assert `mtr_c02_02` has `0` cross-cuff internal bulkhead triangles (`|fn_y| > 0.85` at `|x| > 35, 105 < z < 116`), no small sleeve sub-component (`< 20` tris) is capped with `fn · vn < 0`, `dg.sleeve_slit_area(p, joints, side, cull_backfaces=True)["cm2"] < 1.0` on both arms, and inner-arm sleeve triangles (`|x| > 22, 117 < z < 132`) have `max(uv_ptp[:, 0]) < 0.08` (was `0.212`).
   - `test_all_render_atom_indices_within_vertex_slices`: Assert `bm.audit_model` reports `0` problems on both TPP and FPS `.model` files inside each shipped zip (`0` OOB indices across `g_body`, `g_body_lod1`, and `s_body`).
   - `test_model_tangent_bases_are_orthonormal`: Decode `normals`, `uvdir_u`, `uvdir_v` on TPP and FPS `g_body`; assert unit norms (`| ||v|| - 1 | < 1e-5`) and mutual orthogonality (`max|N·T| < 1e-5`, `max|N·B| < 1e-5`, `max|T·B| < 1e-5`).

#### 6.3 Rebuild & Sign-Off Commands
Rebuild both variants so `dist/*.zip`, `dist/*.zip.sha256`, `BUILD_INFO.json`, and `build/pd2-las/*_report.json` stay in sync (`test_fit_numbers_match_the_build_report` enforces exact agreement):

```bash
# 1. Rebuild both Christie LAS packs + previews
.venv/bin/python tools/pd2-las/build_christie_las.py \
    --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

.venv/bin/python tools/pd2-las/build_christie_las.py \
    --variant base \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

# 2. Run mesh diagnostics on both rebuilt packs
.venv/bin/python tools/pd2-las/diagnose_mesh.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

# 3. Run test suites & static lint
.venv/bin/pytest tests/test_seam_normals.py tests/test_christie_las.py -q
.venv/bin/pytest tests -q
.venv/bin/python -m pyflakes tools/pd2-las/build_christie_las.py \
    tools/pd2-las/build_models.py tools/pd2-las/diagnose_mesh.py \
    tests/test_seam_normals.py tests/test_christie_las.py
```

#### 6.4 Acceptance Checklist Before Closing the Task
- [ ] `fi = 2467, 2468` (Right) and `fi = 3218, 3219` (Left) rear-forearm triangles in `Christie_LAS_Slim` achieve `fn · vn >= 0.95` (up from `0.29`).
- [ ] `0` out-of-bounds indices in `g_body`, `g_body_lod1`, and `s_body` across both `Christie_LAS_Slim.zip` and `Christie_LAS.zip` (TPP and FPS).
- [ ] `0` false-positive `mtr_c02_02` cuff-bridge triangles and `0` inverted caps on 6–9-triangle cuff patches; `sleeve_slit_area(..., cull_backfaces=True)` `< 1.0 cm²` on Left and Right for **both** `slim` and `base`.
- [ ] Bridge triangle `uv_span` on `mtr_c02_01` reduced from `0.185–0.212` to `< 0.08`.
- [ ] Spine and sleeve manifold UV-seam normal splits unified (`0` `> 1°` splits on smooth manifold UV seams), while `coincident_normal_report(g)["border"] > 300` and all 9 tests in `tests/test_seam_normals.py` remain green.
- [ ] `max|N·T|`, `max|N·B|`, `max|T·B|` `< 1e-5` across all vertices of TPP and FPS models.
- [ ] Visual inspection of `build/pd2-las/previews/christie_slim_*.png` confirms smooth shading across rear forearms, cuffs, inner-arm stitch lines, and back spine seam.
- [ ] Append an entry to `tools/pd2-las/MODLOG.md` recording the new `dist/Christie_LAS_Slim.zip` and `dist/Christie_LAS.zip` byte sizes, SHA-256 digests, and before/after normal & stitch metrics.
