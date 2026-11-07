# Recheck: `2026-11-07-christie-slim-screenshot-review.md`

Scope: re-derive every offline number the slim screenshot audit quotes, from the
same artifacts it says it reviewed — `dist/Christie_LAS_Slim.zip`
(sha256 `33832eaf…aca7`, 4,206,230 B), `dist/Christie_LAS.zip`, and the 2B LAS
template extracted from `references/2b.rar` by `tools/pd2-las/bootstrap.sh`.
Tooling: `numpy 2.4.6` + `pillow 13.0.0` (the pins in `bootstrap.sh`).

Reproduce the table with:

```bash
.venv/bin/python tools/pd2-las/audit_metrics.py
```


**Update, later on 2026-11-07:** the table below describes the morning pack
(`33832eaf…`). It has since been rebuilt twice — the authored near-idle arm
rest, then the sleeve seam stitch (`14f75d66…`, §8 of the diagnosis audit).
Vertex counts, UVs and every texel-density number stand (the stitch pass adds no
vertices and leaves `uv0` byte-identical). What moves, re-running
`audit_metrics.py` on the shipped packs:

| pack | tris | t/1000cm² | bad verts | dup pairs | diverged |
| --- | --- | --- | --- | --- | --- |
| Christie base | 17287 → 17351 | 447 → 448 | 750 → 792 → 788 | 1437 → 1440 | 856 → 806 |
| Christie slim | 12925 → 12996 | 375 → 376 | 480 → 526 → 522 | 949 → 953 | 480 → 431 |

Two builds move these columns. The seam stitch welds 21/23 rim pairs and adds
64/71 triangles; welding averages the two rims' normals, which raises "bad
verts" by 42/46 (a vertex with one incident face >90° off its normal — the mean
of an outer and an inner surface is exactly that). The second build adds
`unify_coincident_normals` (work order item 1, §9 of the diagnosis), which
gives interior copies one shared normal: interior divergent pairs 50 (base) / 49
(slim) → **0**, and the audit's own `diverged` column falls to 806 / 431. Every
remaining divergent pair sits on a garment edge and is kept on purpose — those
are folds, not seams.

A third build, the sleeve-gloss mask fix (§7 of the diagnosis), touches only
`c02_01_df.texture`: no vertex, UV, topology or texel-density number in this
document moves. The pack in `dist/` today is `5e55745f…70b4d` (slim) /
`c57edbba…1f765` (base).

`audit_metrics.py` now prints both the divergent-pair height histogram
(`--z-hist`, which always sums to the `diverged` column) and the diffuse-alpha
statistics (`--alpha`, over the whole texel grid), so the audit's own numbers are
reproducible rather than quoted.

**Bottom line:** the *defect list* in the audit survives (items 1–5 are real;
item 6 is partly mis-explained). The **"Correction" section does not**: its
"2B reference" column is the Christie **base** pack, so the central claim —
"the slim pack's shading data is better than the PD2-authored reference" — is
unsupported: on the audit's own metric the real reference is ~27× better than
slim, whereas the table implies slim is 13 % better than the reference.

## 1. The "2B reference (PD2)" column is the Christie base pack

The audit's table reads:

> vertices with an incident face >90° off their own vertex normal |
> **750 / 10361 = 7.2 % (base)** | 480 / 7695 = 6.2 %

10,361 is exactly `christie.model` `g_body`'s vertex count, and recomputing the
metric gives exactly 750 (7.24 %) for the **base** pack. The 2B reference's
`g_body` is a different mesh entirely:

| pack | verts | tris | bad verts (>90° face vs vertex normal) |
| --- | --- | --- | --- |
| 2B reference (PD2) | **27,741** | 35,260 | **65 = 0.23 %** |
| Christie base | **10,361** | 17,287 | **750 = 7.24 %** |
| Christie slim | 7,695 | 12,925 | 480 = 6.24 % |

The audit even annotates the cell "(base)", so this looks like a column slip
while assembling the table — but it changes the conclusion, because the prose
uses the 7.2 % as the reference to beat.

The same table proves the slip internally: it credits the 2B model with 22,486
coincident-vertex pairs. At the measured 17,716 coincident groups those pairs
need at least 35,432 vertices — more than three times the 10,361 the table
claims for that model. 22,486 is the genuine 2B number; 10,361 is not.

**Effect:** "better than the PD2-authored reference" is wrong. On this metric
slim is 6.24 % vs the reference's 0.23 %.

**Caveat on the metric itself** (worth stating either way): percentage-of-
vertices falls with tessellation. 2B has 2.7× the triangles and 3.6× the
vertices, so a raw comparison is density-confounded. The defensible statement
is narrower: slim's normal/face agreement is in the same band as the project's
own base pack (6.2 % vs 7.2 %) and far from the reference's 0.2 %.

## 2. Two more rows of the same table do not reproduce

| row | audit says | measured |
| --- | --- | --- |
| tris per 1000 cm², 2B | 695 | **1,024** (35,260 tris / 34,448 cm²) |
| tris per 1000 cm², slim | 375 | 375 ✓ |
| texels per cm (1024²), 2B | 5.58 | 5.52 ✓ (rounding) |
| texels per cm (1024²), slim | **9.02** | **5.52** |

- 695 is close to `g_head_lod1`'s 691 — likely the wrong drawable got measured
  for the reference row.
- 9.02 is impossible on its own row: 375 tris/1000 cm² with 12,925 tris implies
  34,427 cm², and 1024/√34427 = 5.52. Both packs ship a 1024² body atlas over
  ≈34.4k cm², so slim's texel pitch is the same as the reference's, not 1.6×.

## 3. Issue 1's height distribution accounts for 384 of 480 pairs

Listed bins: 132 + 99 + 134 + 19 = **384**, not 480. The missing 96 pairs are

- **87 pairs at z < 0** — the boot soles sit 3.15 cm below the ground plane
  (model z range −3.15 … 163.76 cm), so the largest "feet" cluster is actually
  below the first bin, not in it;
- **9 pairs at z ≥ 160** (collar/neck).

Everything that is listed is exact (140–160: 132, 0–20: 99, 100–140: 134,
80–100: 19), but the distribution is presented as complete.

## 4. Two metrics are undefined, so nothing can check them

"faceted score (smooth regions only)" (29.9 % / 6.5 %) and "diffuse
low-freq / high-freq ratio" (1.18 / 2.24) have no definition, no code and no
region masks in the repo. Given that three neighbouring rows are wrong (§1–§2),
they cannot be used as evidence in either direction. If they are to stay, they
need a definition and a script (the new `tools/pd2-las/audit_metrics.py` exists
for exactly that reason).

## 5. Specular-alpha numbers are not reproducible as written

The audit: "Christie garment alpha sits at mean 10–12 with ~85 levels …
(Miranda body 21.6/64 levels, lawson body1 17.2/40 levels)".

Whole-texture DXT5-alpha measurements of the shipped files:

| texture | mean | min | max | levels (max−min+1) |
| --- | --- | --- | --- | --- |
| `christie_slim_c02_01_df` (blazer/garment atlas) | 9.68 | 0 | 255 | 256 |
| `christie_slim_c02_02_df` | 5.41 | 0 | 255 | 256 |
| `christie_slim_body_df` | 27.44 | 0 | 255 | 256 |
| `miranda_body_df` | 19.83 | 0 | 63 | 64 ✓ |
| `lawson body1_df` | 16.56 | 2 | 41 | 40 ✓ |

The 64/40 "levels" are exactly the reproducible value range (max − min + 1),
which confirms the metric — and then "~85 levels" cannot describe a whole
garment texture whose alpha spans 0–255. Likewise the reference means are 2–9 % above the
whole-texture means. Both are explicable if everything was measured through an
unstated region mask (sleeves / opaque pixels), but as written the check is not
reproducible, and "inside the shipped-pack envelope" is doing more work than the
numbers support.

## 6. Smaller corrections

- **Item 3 (armpit notch)** — real, but the coordinates are ~15–25 px left of
  the notch: the hard-edged triangle is at x ≈ 354–367, y ≈ 414–426 in
  `christie_slim_01_lobby_front-three-quarter.png`; the audit quotes
  x 330–355, y 395–425.
- **Item 4 (wrist)** — the quoted red peak RGB (187, 44, 21) does exist, exactly
  once, at **image 03, (343, 585)**; within ±20 px there are 168 pixels with
  R−B > 40, so "155 px" is plausible. But the item names neither the image nor
  the crop, and the cream band (208, 182, 171) is not localized, so the numbers
  cannot be re-measured without guessing the region.
- **Item 6 (trouser blotches)** — the finding may be real, the mechanism is not:
  `retouch_sleeve_gloss()` rewrites only the diffuse **alpha** channel (PD2's
  specular mask), so it can change gloss, never albedo; the mask is box-blurred
  and bilinearly resized, so the splat edge cannot produce stair-steps. What
  does produce axis-aligned blocks is the attenuation being applied per DXT
  block, and at coarse mips one block spans many texels. The UV-bleed half of
  the hypothesis is at least possible — with a 0.5 arm-share cutoff (the build
  uses 0.40, so this is conservative) 78 of 1,821 leg-weighted vertices (4.3 %)
  have a UV inside the 24-texel splat radius of an arm-weighted vertex — but
  "mask pyramid bleeding across UI islands" does not apply: the masks are per
  body-material role, and no UI atlas is involved.

## 7. What checks out (so the audit is not thrown away)

- Pack identity: size, sha256, 11 archived screenshots, widths 491–563 px.
- The duplicate-vertex table, all three rows, exactly:
  2B 22,486 pairs / 0 diverged; base 1,437 / 857 (59.6 %);
  slim 949 / 480 (50.6 %).
- Normal maps: all Christie `_nm` files are R = 255, G varying, B = 0, and
  `miranda_body_nm` has the same structure (R = 255, B = 0) — correct.
- Item 1's defect and fix direction: coincident groups really do disagree while
  the 2B reference's do not, and `_weld_positions()` really is the existing
  precedent for group-wise normal unification.
- Item 2 is the best-evidenced item in the audit: the quoted box
  (image 05, x 86–90, y 420–470) lands exactly on a near-white sliver separated
  from the sleeve by background pixels.
- Item 3 (notch) and item 5 (glove fingers as black slots in images 08–10) are
  visible at native scale.
- Item 7's scoping to the heister head mod is right; the pack ships no head.
- Code references: `cut_hands()` really does keep a face only when all three
  vertices are non-hand; `_elbow_coverage_correction()`
  and `_apply_slim_fold_solution()` exist as named.

## Suggested edits to the audit

*All eight are applied to
[`2026-11-07-christie-slim-screenshot-review.md`](2026-11-07-christie-slim-screenshot-review.md)
on 2026-11-07; the list is kept as the record of what was wrong.*


1. Replace the "2B reference (PD2)" column with the real 2B numbers, or relabel
   it "Christie base" and delete the "better than the reference" claim.
2. Add the density caveat, or normalize the metric (bad vertices per 1000 tris,
   or mean angle) before comparing meshes of different resolution.
3. Fix the texel-density row (5.52 for both) and the reference tri-density row
   (1,024), or drop both.
4. Extend the z histogram to z < 0 and state that it sums to 480.
5. Define or remove "faceted score" and "LF/HF ratio".
6. State the mask/region behind the alpha numbers, or re-measure whole-texture
   and say so.
7. Add image + crop coordinates to items 3 and 4.
8. Rewrite item 6's mechanism (per-block specular attenuation, not the splat
   edge; no UI islands).

## Follow-up

The root causes behind the defects (shell structure, the zero-width sleeve seam,
the inherited elbow hole, the armpit wedge, the sleeve mask) are derived in
[`2026-11-07-christie-slim-diagnosis.md`](2026-11-07-christie-slim-diagnosis.md),
reproducible with `tools/pd2-las/diagnose_mesh.py`.
