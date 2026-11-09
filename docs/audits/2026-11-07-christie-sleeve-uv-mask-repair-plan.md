# Christie LAS (`base` + `slim`) — Upside-Down `sleeve_uv_mask` Repair & Verification Plan

**Status:** ready to execute — every number below was measured on the shipped archives in this repo
**Date:** 2026-11-07
**Audience:** a cold-start coding agent with no prior session context
**Revision:** supersedes the earlier draft of this file. The draft had the right *conclusion* (the mask is
vertically mirrored) but two wrong *mechanisms* and one wrong *test threshold*. §3.2, §3.3, §4.2, §4.3 and
§5.4 are the rewritten parts; §4.2 is the one that changes the acceptance gate.

---

## 0. TL;DR

`sleeve_uv_mask` (`tools/pd2-las/build_christie_las.py:390`) rasterises sleeve triangles at
`y = (1.0 + v) * work`. The row the GPU actually samples is `y = mod(-v, 1.0) * work`.

Because `1 − mod(-v,1) ≡ mod(v,1)`, that is a **vertical mirror inside each UV tile**, not a shift. On the
blazer/trouser/boot atlas (`c02_01`) it lands the sleeve's `−55 %` specular-alpha cut on Christie's
**hips and trouser seat**: 402 of the 630 faces at `z ∈ [20,60) cm` are darkened (68.5 % of that band,
`Δmean = −3.71` alpha levels), while 94 % of the sleeves keep their full sheen.

Both existing guards (`diagnose_mesh.mval`, the `centroid` helper in the test) re-implement the same wrong
row, so they query the mask *where it was drawn* rather than where the GPU reads, and report `100 %` coverage
on a pack that visibly has none. §4.2 tabulates all four combinations — that table is the proof, and it is
also why the fix must change the *query* and the *rasteriser* together.

The old test also passes today only because of that shared mistake: with the query corrected, the buggy mask
drops to `5.8 %` sleeve coverage *and* `37.3 %` leg-area coverage, so one assertion alone cannot tell the two
failure modes apart. §5.4 splits it into two gates that each fail on exactly one mistake.

---

## 1. Scope and deliverables

| | |
|---|---|
| Primary fix | `tools/pd2-las/build_christie_las.py` — new `uv_to_texel_frac`, rewritten `sleeve_uv_mask` (`:390`) |
| Upstream cause | `tools/pd2-las/preview_textured.py` — `_sample` (`:111`) |
| Diagnostics | `tools/pd2-las/diagnose_mesh.py` — `mval` (`:347`) |
| Tests | `tests/test_christie_las.py` — `test_sleeve_gloss_mask_stays_on_the_sleeve` (`:747`) |
| Artefacts | rebuilt `dist/Christie_LAS.zip` + `dist/Christie_LAS_Slim.zip` and their `.sha256` |

**Leave `retouch_sleeve_gloss` (`:460`) alone** — see §8.3. Its DXT5 re-encode problem belongs to the
normal-map plan; this plan only changes *which* blocks it selects.

**Companion plans, safe in any order:** `2026-11-07-christie-forearm-normals-and-seam-repair-plan.md`,
`2026-11-07-christie-normal-maps-and-dxt5-mip-repair-plan.md`. §8.4 explains why the seam plan's new bridge
triangles cannot be reached by this mask.

---

## 2. What the code does today

`build_variant` (`:3340`) calls `sleeve_uv_masks(groups["body"])`, which selects faces with mean arm-chain
weight `> SLEEVE_BONE_SHARE = 0.40` and rasterises them per material role; `retouch_sleeve_gloss` then scales
the diffuse alpha (= PAYDAY 2's specular mask) of each touched DXT5 block by `1 − 0.55·mask`. The rasteriser:

```python
# tools/pd2-las/build_christie_las.py:408-413  (current)
        for i in (a, b, c):
            u, v = uvs[int(i)]
            # stored UVs are internal (u, -v_source): row 0 of the texture is
            # sampled at internal v = -1, so y = (1 + v) * size — the same
            # mapping preview_textured._sample(flip_v=True) applies.
            pts.append((float(u) * work, (1.0 + float(v)) * work))
```

Both halves of the comment are wrong: `transfer_group` authored `(u_src, 1 − v_src)`, not `(u, −v_src)`
(§3.1), and `preview_textured._sample` does not compute `(1 + v)` either (§3.2).

---

## 3. Root cause

### 3.1 The convention

`build_models.py:785` (and `:962` for grafted hands):

```python
g.uvs.append((sv.uv[0], 1.0 - sv.uv[1]))  # p2mt GLTF-import convention
```

With `v_src` the Source/VTF **top-down** coordinate (`0` = image row `0`), the `.model` stores
`u_stored = u_src`, `v_stored = 1 − v_src`. DOA5 authored three of Christie's four atlases in UDIM tile
`v_src ∈ [1,2]`, so those stored values are **negative**:

| material | faces (slim / base) | stored `v` | stored `u` |
|---|---:|---|---|
| `mtr_body` | 2028 / 4566 | `[−0.835, −0.023]` / `[−0.975, 0.000]` | `[0.005, 0.998]` |
| `mtr_c02_01` | 8825 / 8850 | `[−0.995, −0.008]` | `[0.005, 0.998]` |
| `mtr_c02_02` | 1765 / 3557 | `[−0.985, 0.000]` | — |
| `mtr_c02_05` | 378 / 378 | **`[+0.043, +0.980]`** | — |

Under D3D9 `Wrap` the GPU reduces both axes, so the top-down row fraction of a stored `v`, in **any** tile,
either sign, is

```
row(v) = mod(-v, 1.0)        # == mod(1 - v, 1.0)
```

`build_models.py:2439` already uses that form (`1.0 - uv[:, 1]`).

### 3.2 Why the current code produced `mod(v,1)` — the identity that hid the bug

`tools/pd2-las/preview_textured.py:111-118` (current):

```python
    u = np.mod(uv[..., 0], 1.0)
    v = np.mod(-uv[..., 1] if flip_v else uv[..., 1], 1.0)
    x = u * w - 0.5
    y = (1.0 - v) * h - 0.5
```

With `flip_v=True` (the default) `v` **is already** `row(v_stored)`; the extra `1.0 - v` un-does it:

```
y/h = 1 − mod(-v_stored, 1) = mod(v_stored, 1)          (v_stored non-integer)
```

That is a vertical mirror inside each tile. Measured directly:

| `v_stored` | current `flip_v=True` row | correct `mod(-v,1)` | |
|---|---:|---:|---|
| `−0.9951` | `0.0049` | `0.9951` | mirrored |
| `−0.6000` | `0.4000` | `0.6000` | mirrored |
| `−0.0052` | `0.9948` | `0.0052` | mirrored |
| `+0.0435` | `0.0435` | `0.9565` | mirrored |
| `+0.9796` | `0.9796` | `0.0204` | mirrored |

**The trap that made this invisible:** `1 − mod(x,1) ≡ mod(−x,1)` for non-integer `x`. So the *other* branch,
`flip_v=False`, is numerically identical to the correct formula — which is why the Miranda head preview is
only upright with `--no-flip-v`, and why every script that happened to pass one flag or the other looked fine.

### 3.3 Ground truth on the DOA5 atlas

`references/Christie.zip` → `.../c2/cri_02_01_base.vtf`, 1024², sampled on `christie_slim.model`:

| group | faces | `v_stored` | `row = mod(-v,1)·1024` | `mod(v,1)·1024` (current) |
|---|---:|---|---|---|
| boots `z < 12` | 1261 | `[−0.994, −0.568]` | `[581, 1018]` → RGB `[86.8, 52.2, 49.3]` **dark burgundy leather** | `[5, 442]` → RGB `[145.9, 140.3, 132.9]` **cream jacket sleeve** |
| trousers `z > 20` | 1343 | — | `[542, 923]` | — |
| sleeve (`arm > 0.4`) | 1740 | `[−0.652, −0.011]` | `[10, 667]` | `[356, 1013]` |

Rendered proof from the shipped bytes (§5.2): with `_sample` unfixed the front view of
`dist/Christie_LAS_Slim.zip` shows **bare arms and a navy plaid skirt** (the mirrored trouser island);
patching the single row line gives **skin-tone arms and grey pinstripe trousers**.

Positive-`v` atlas `c02_05` is worse than mirrored — `(1 + v)` maps to `y ∈ [1069, 2027]`, entirely
off-canvas. It has no sleeve faces today, so nothing is visibly lost, but the helper is unusable for that tile
as written.

---

## 4. Measurements that define the acceptance gates

All of this is reproducible with the snippets in §6.2.

### 4.1 Footprint coverage and leakage at true GPU texel coordinates

`hit` = mask value > `0.05` at `(mod(u,1)·1023, mod(-v,1)·1023)`; sleeve coverage uses `> 0.5`.

| pack | role | sleeve faces | BUGGY sleeve `> 0.5` | FIXED sleeve `> 0.5` | BUGGY non-sleeve hits | FIXED non-sleeve hits |
|---|---|---:|---:|---:|---:|---:|
| slim | `c02_01` | 1740 | **5.80 %** (101) | **99.37 %** (1729) | **834** | 180 |
| slim | `c02_02` | 679 | **15.76 %** (107) | **100.00 %** (679) | 0 | 0 |
| slim | `mtr_body` | 160 | **62.50 %** (100) | **100.00 %** (160) | 0 | 0 |
| base | `c02_01` | 1765 | **6.74 %** (119) | **99.38 %** (1754) | **836** | 184 |
| base | `c02_02` | 679 | **15.76 %** (107) | **100.00 %** (679) | **251** | 0 |
| base | `mtr_body` | 928 | **12.72 %** (118) | **99.78 %** (926) | **95** | 21 |

### 4.2 Why the existing guards passed — the four-way matrix

Same two masks, each queried at each coordinate convention (`c02_01`, `slim`; `base` matches to ±3 faces):

| mask | query | sleeve `> 0.5` | non-sleeve hits | of which trouser `z∈[20,60)` | leg-only faces | leg-area share | leg hits with `z > 20` | max hit `z` |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BUGGY | **buggy coord** `(1+v)` ← *what the test does today* | **99.66 %** | 176 | 0 | 31 | **0.76 %** | 0 | 12.1 cm |
| BUGGY | true GPU `mod(-v,1)` ← *what the GPU does* | **5.80 %** | **834** | **402** | **627** | **37.33 %** | **564** | **89.1 cm** |
| FIXED | true GPU | **99.37 %** | 180 | **0** | 34 | 0.79 % | **0** | 12.1 cm |
| FIXED | buggy coord | 5.92 % | 838 | 403 | 631 | 37.61 % | 568 | 89.1 cm |

(`slim`; `base` reads `1759 / 119 / 122 / 1754` on the sleeve column and `180 / 836 / 840 / 184` on leakage —
same percentages to two decimals.)

Three conclusions the executing agent must not lose:

1. **The BUGGY/buggy cell is why nobody noticed:** the two mistakes cancel, so the test's own numbers look
   excellent (`99.66 %` sleeve, `31` leg faces, `0.76 %` area) on a pack whose sleeves are actually
   unattenuated. That cell *is* today's shipped test result.
2. **Only the true-GPU row distinguishes the masks.** Comparing BUGGY@true-GPU with FIXED@true-GPU is the
   whole fix in one line: `5.80 % → 99.37 %` coverage, `402 → 0` trouser hits, `564 → 0` leg hits above
   20 cm, `37.33 % → 0.79 %` leg-area share.
3. **Fixing only one side is worse than fixing neither.** Fixing the query but not the mask ("MIXED") gives
   `5.80 %` coverage and `37.33 %` leakage — the test fails loudly, but for a reason a careless reader would
   blame on the test. Land §5.1 and §5.4 in the same commit.

### 4.3 What shipped, in the texture

`Δ` against the pre-retouch texture (`convert_textures` output) sampled at mesh centroids, `(size−1)`
convention. Both packs agree to `0.01` on `c02_01` (shared trouser island).

| pack | role | band | faces | shipped `Δmean` | faces darkened `> 1 LSB` | darkened share |
|---|---|---|---:|---:|---:|---:|
| slim | `c02_01` | sleeve | 1740 | **−0.27** *(should be ≈ −5.9)* | 96 | 3.6 % |
| slim | `c02_01` | **trousers `z∈[20,60)`** | 630 | **−3.71** *(should be 0.00)* | **402** | **68.5 %** |
| slim | `c02_01` | boots `z<20` | 1392 | −0.36 | 91 | 11.7 % |
| slim | `c02_01` | blazer hem `z∈[60,110)` | 2798 | −0.47 | 216 | 11.2 % |
| slim | `mtr_body` | boots `z<20` | 436 | 0.00 | 0 | 0 % |
| base | `c02_01` | sleeve | 1765 | **−0.33** | 114 | 3.8 % |
| base | `c02_01` | **trousers `z∈[20,60)`** | 630 | **−3.71** | **402** | **68.5 %** |
| base | `c02_02` | blazer hem `z∈[60,110)` | 2012 | **−3.34** | 244 | 8.0 % |
| base | `mtr_body` | boots `z<20` | 436 | **−2.39** | 96 | 25.6 % |

### 4.4 What the fix delivers, in the texture

Post-fix `mip 0` alpha at mesh centroids, `(size−1)` convention, same rebuild path as the builder:

| pack | role | sleeve | trouser `z>20` | ratio |
|---|---|---:|---:|---:|
| slim | `c02_01` | **5.94** | **11.35** | **0.523** |
| base | `c02_01` | **6.00** | **11.35** | **0.529** |
| slim / base | `c02_02` | **5.15** | — | — |

Trouser alpha is *bit-identical* to pre-retouch (`11.35` both sides, `0` faces darkened `> 1 LSB` across all
630 faces). Sleeves drop `11.86 → 5.94` (`−50 %`).

### 4.5 The residual 180 hits are genuine atlas overlap, not mask error

The fixed mask still reports 180 (`slim`) / 184 (`base`) non-sleeve `c02_01` faces. They are **not** a mask
defect, and no mask can remove them:

- **`0` of them are in the trouser band `z ∈ [20, 60)`** — the band the bug actually painted. All 180 sit
  at `z ≤ 12.4` (`34` boot/ankle-strap faces, all in `z ∈ [2.0, 12.4]`) or at `z ≥ 60` (`50` hem +
  `96` torso/lapel faces). Consequently **no leg-weighted face above `z = 20`** is hit (`34 / 34` leg hits are
  at `z ≤ 12.1`), which is the property the test gates on.
- Their UV islands are DOA5-shared: 96 of them are 96 of the 144 faces of the island that also holds 48 sleeve
  faces; the other 84 sit on two further shared islands. Their dominant weights are `Spine1`/`Hips`/`Foot`
  (mean arm weight `< 0.05`), so they are body geometry, but they sample the sleeve's metal-trim texels.
- Measured face-area overlap with the hard sleeve footprint: mean `0.934`, median `1.000` — they are *inside*
  the sleeve's own UV footprint, so excluding them would mean cutting the sleeve's cuff trim too.
- The damage they take from the fixed mask is small: hem `Δmean = −0.12` (`slim`) / `−0.13` (`base`), boots
  `−0.14`, torso `−0.20`, i.e. ~0.9 % of those bands' mean alpha.

Hence the acceptance gate is **"no leg-weighted hit at `z > 20` and nothing in the trouser band"**, not
"zero hits". §8.1 shows the ownership-weighting scheme that tries to zero them and why it is rejected.

---

## 5. Implementation

### 5.1 `tools/pd2-las/build_christie_las.py`

Insert the constant and helper immediately above `sleeve_uv_mask` (`:390`) and replace the function body.
Keep the existing defaults.

```python
MAX_SLEEVE_TRI_UV_SPAN = 0.12


def uv_to_texel_frac(uv):
    """Stored Diesel ``.model`` ``uv0`` -> top-down ``[0, 1)`` texel fractions.

    ``build_models.transfer_group`` authored ``(u_src, 1.0 - v_src)`` where
    ``v_src = 0`` is image row 0, so under D3D9 ``Wrap`` the GPU samples
    ``(mod(u, 1), mod(-v, 1))`` for every UDIM tile, negative ``v`` included.
    """
    import numpy as np

    arr = np.asarray(uv, dtype=np.float64)
    out = np.empty_like(arr, dtype=np.float64)
    out[..., 0] = np.mod(arr[..., 0], 1.0)
    out[..., 1] = np.mod(-arr[..., 1], 1.0)
    return out


def sleeve_uv_mask(uvs, faces, *, work: int = 1024, feather_texels: float = 3.0,
                   max_uv_span: float = MAX_SLEEVE_TRI_UV_SPAN):
    """Texel coverage of a set of UV triangles (the sleeve's own islands).

    Rasterising the *faces* rather than splatting a disc around each vertex is
    what keeps the sleeve gloss mask off the rest of the suit: the mask is then
    exactly the UV footprint of the sleeve, so a texel that belongs to the
    trousers or the shoes cannot pick it up no matter how close the islands sit
    in the atlas. The blur is applied **inside** that footprint only (the
    blurred mask is clipped to the unblurred one), so the feather softens the
    edge of the change without ever reaching a texel the sleeve does not own.

    Each triangle is unwrapped as a unit -- ``u - floor(mean(u))`` and
    ``row - floor(mean(row))`` with ``row = mod(-v, 1)`` -- so a triangle that
    straddles an integer tile boundary is never torn across the canvas, and the
    positive-``v`` atlas (``c02_05``, stored ``v in [0.043, 0.980]``) lands
    inside the canvas instead of at ``y ~ 1.04 * work``. Triangles spanning more
    than ``max_uv_span`` on either axis are skipped: those are the seam-stitch
    bridges, whose UVs jump between two islands and would otherwise streak
    across unrelated texels.
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    im = Image.new("L", (work, work), 0)
    if faces:
        uv_arr = np.asarray(uvs, dtype=np.float64)
        frac = uv_to_texel_frac(uv_arr)
        pen = ImageDraw.Draw(im)
        for a, b, c in faces:
            tri = frac[[int(a), int(b), int(c)]]
            if float(np.ptp(tri, axis=0).max()) > max_uv_span:
                continue
            pts = [((float(u) - np.floor(tri[:, 0].mean())) * work,
                    (float(v) - np.floor(tri[:, 1].mean())) * work)
                   for u, v in tri]
            pen.polygon(pts, fill=255)
    hard = np.asarray(im, dtype=np.float64) / 255.0
    if feather_texels > 0 and faces:
        soft = np.asarray(im.filter(ImageFilter.GaussianBlur(feather_texels)),
                          dtype=np.float64) / 255.0
        return np.where(hard > 0.0, soft, 0.0)
    return hard
```

Review notes:

- `uv_to_texel_frac` runs once per call on the whole array; the per-triangle shift only removes the integer
  tile, which is what keeps a boundary-crossing triangle's three vertices within one unit of each other.
- `max_uv_span = 0.12` clears every authored sleeve triangle on both packs (worst authored spans `du = 0.0607`
  / `dv = 0.0881` for `c02_02`, `du = 0.0881` for `c02_01`). It drops only the 43 (`slim`) / 36 (`base`)
  seam-stitch bridges (`du` up to `0.2119`). Verified: with and without the guard the raster is identical
  (`13.288 %` / `13.348 %` of the atlas) and so is the hit set, so the guard is pure insurance.
- `sleeve_uv_masks` (`:423`) needs no functional change; its call at `:455` keeps working.

### 5.2 `tools/pd2-las/preview_textured.py`

Only line `:117` changes — `y = (1.0 - v) * h - 0.5` becomes `y = v * h - 0.5`:

```python
def _sample(tex: np.ndarray, uv: np.ndarray, flip_v: bool) -> np.ndarray:
    """Bilinear wrap sample from a top-down ``(H, W, 4)`` texture array.

    ``flip_v=True`` is the convention for UVs authored by
    ``build_models.transfer_group``: they store ``(u_src, 1 - v_src)``, so the
    top-down row fraction is ``mod(-uv_y, 1.0)`` and must not be inverted a
    second time (``1 - mod(-x, 1) == mod(x, 1)``, which silently mirrors the
    model). ``flip_v=False`` keeps the raw-``v`` reading for NIF-sourced UVs.
    """
    h, w = tex.shape[:2]
    u = np.mod(uv[..., 0], 1.0)
    v = np.mod(-uv[..., 1], 1.0) if flip_v else np.mod(uv[..., 1], 1.0)
    x = u * w - 0.5
    y = v * h - 0.5
```

**Audit the callers before landing, and pass `flip_v=False` where the UVs did not come from
`transfer_group`:** `preview_textured.main` (`--flip-v` defaults **True**), `pose_preview.py:148`,
`pose_zoom.py:45`, `glove_check.py:166`, `build_skyrim_outfit.py:505`. Skyrim NIF UVs are authored by
`nif.py`, not `build_models`, so those paths are the ones at risk. `tests/test_preview_cull.py` passes
`tex=None` and is unaffected.

Verified on `dist/Christie_LAS_Slim.zip` (same texture bytes, only this line patched): boots
`RGB [145.7, 141.0, 133.1]` → `[83.0, 48.8, 45.4]`; front view goes from bare arms + plaid skirt to skin-tone
arms + grey pinstripe trousers.

### 5.3 `tools/pd2-las/diagnose_mesh.py`

Replace the private mirror (`:347-351`) with the shared helper, and split the printed report so coverage and
leakage are reported separately — they have opposite meanings and today's single `... covered 100%` line is
actively misleading:

```python
    from build_christie_las import uv_to_texel_frac

    def mval(fi):
        c = uv_to_texel_frac(p["uv"][f[fi]].mean(0))
        y = int(np.clip(c[1] * 1024, 0, 1023))
        x = int(np.clip(c[0] * 1024, 0, 1023))
        return mask[y, x]
```

```text
sleeve gloss mask: sleeve faces covered 99.4%; leg-only UV area 0.79% over 34 faces,
                   all at z < 20 cm, 0 above
```

### 5.4 `tests/test_christie_las.py`

Rewrite the body of `test_sleeve_gloss_mask_stays_on_the_sleeve` (`:747-821`). Keep the docstring history
(the earlier vertex-disc mask reached `3.2 % / 151` faces) but replace the mechanics.

**1. Shared helper, not a local mirror.**

```python
    def centroid(fi: int) -> tuple[float, float]:
        c = bcl.uv_to_texel_frac(uvs[faces[fi]].mean(axis=0))
        return float(c[0]), float(c[1])
```

**2. Split the leg gate in two — this is the assertion that must change.**
With the fixed mask the leg-only face share is `1.5031 %` (`34 / 2262`) on both packs and would **fail** the
current `assert share < 0.015` by `0.0031` of a point. Do not just loosen the constant: with the *buggy* mask
the same corrected query gives `37.33 %` and `627` faces, `564` of them at `z > 20 cm` (up to `89 cm` — the
trousers and the seat), so a single share threshold cannot separate "34 boot faces on a shared island" from
"stamped the trousers". Two gates can:

```python
    leg = [fi for fi in np.where(fmat == role)[0]
           if float(leg_w[faces[fi]].mean()) > 0.5
           and float(arm_w[faces[fi]].mean()) < 0.1]
    z = np.array([float(verts[faces[fi]].mean(axis=0)[2]) for fi in leg])

    # Gate 1 -- the trousers and the seat must be untouched.  The shipped pack
    # darkened 402 of the 630 faces at z in [20, 60) cm before this was fixed.
    trouser = [fi for fi, zz in zip(leg, z) if 20.0 < zz < 60.0]
    assert trouser, f"{which}: no trouser faces found to gate"
    _, t_count = coverage(trouser)
    assert t_count == 0, (
        f"{which}: gloss mask reaches {t_count} trouser faces at "
        f"z in [20, 60) cm")

    # Gate 2 -- DOA5 shares the boot / ankle-strap islands with the sleeve cuff
    # trim, so a few feathered faces are expected, but every leg-weighted hit
    # must be down at the boot (z <= 12.1 cm measured; 20 cm is the margin).
    # Bound the residue by area and confirm nothing reaches the legs proper.
    share, count = coverage(leg)
    assert share < 0.010, (
        f"{which}: mask covers {share:.2%} of the leg-only UV area "
        f"over {count} faces (fixed expectation 0.79% / 34; the buggy mask "
        f"scores 37.33% / 627 with 564 of them above z=20 cm, and the retired "
        f"vertex-disc mask 3.2% / 151)")
    assert count <= 60, f"{which}: mask touches {count} leg-only faces"
    hit_z = [zz for fi, zz in zip(leg, z) if coverage([fi])[1]]
    assert max(hit_z) < 20.0, (
        f"{which}: a leg-weighted face at z={max(hit_z):.1f} cm is attenuated")
```

Measured on both packs: `share = 0.7900 %`, `count = 34`, `t_count = 0`, `max(hit_z) = 12.1`. Reverting
`uv_to_texel_frac` to `(1 + v)` fails Gate 1 with **`403`** and Gate 2 with **`37.33 %`**. Forgetting the
`centroid` fix fails Gate 1 with `403` too, but Gate 2 then reads `0.76 %` / `31` and `max(hit_z) = 12.1`, so
the failure is only caught by Gate 1 — which is exactly why the gates are split and why the `centroid` line
must change in the same commit.

**3. Texture check: sample by band, not through the mask.** The current `alpha[mask > 0.5]` (`:816-821`) is
circular — a wrong mask indexing an equally wrong texture always yields a plausible ratio. Replace it:

```python
    size, mips, mip0 = pd2_dds.dds_mip0_slice(blob)
    assert size == 1024 and mips == 11
    alpha = pd2_dds.decode_dxt5(mip0, size, size)[..., 3].astype(np.float64)

    def mean_alpha(indices) -> float:
        return float(np.mean([alpha[int(y * (size - 1)), int(x * (size - 1))]
                              for x, y in (centroid(fi) for fi in indices)]))

    sleeve_mu, trouser_mu = mean_alpha(sleeve), mean_alpha(trouser)
    assert sleeve_mu < 0.75 * trouser_mu, (
        f"{which}: sleeve specular alpha {sleeve_mu:.2f} vs trousers "
        f"{trouser_mu:.2f} - the attenuation is not on the sleeve")
```

Expected after rebuild: `5.94` vs `11.35` → ratio `0.523` (`slim`), `6.00` vs `11.35` → `0.529` (`base`).
Before the fix the same comparison reads `11.58` vs `8.73` → `1.327`, i.e. the sleeves are *glossier* than the
trousers — the defect in one number. `trouser` is guaranteed non-empty (`1343` faces on both packs).

**4. New regression test — the wrap identity.** Cheap, archive-free, and the only thing that stops a future
"cleanup" from re-introducing the mirror:

```python
def test_uv_to_texel_frac_matches_udim_wrap_for_both_tile_signs():
    """Both UDIM tile signs must map to the same top-down row."""
    import build_christie_las as bcl

    v_src = 0.62                                          # row 0.62 of the image
    negative_tile = np.array([[0.25, -v_src]])            # v_src = 1.62 -> stored v = -0.62
    positive_tile = np.array([[0.25, 1.0 - v_src]])       # v_src = 0.62 -> stored v = 0.38
    a = bcl.uv_to_texel_frac(negative_tile)
    b = bcl.uv_to_texel_frac(positive_tile)
    assert np.allclose(a, b), (a, b)
    assert abs(float(a[0, 1]) - v_src) < 1e-9, a
```

---

## 6. Build and verify

```bash
cd /home/user/universal-modder
.venv/bin/pytest -q tests/test_christie_las.py -k "gloss or texel_frac"

.venv/bin/python tools/pd2-las/build_christie_las.py --variant base \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

.venv/bin/python tools/pd2-las/diagnose_mesh.py
.venv/bin/pytest -q
```

The builder rewrites both `dist/*.zip` and their `.sha256` sidecars (`:3446-3449`); the pack tests compare the
sidecar digest, so regenerate them together. The build needs the 2B templates extracted at
`/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b` (`references/2b.rar`).

Two environment prerequisites, both verified on this checkout:

- `scipy` must be installed (`.venv/bin/pip install scipy`). Without it,
  `tests/test_christie_las.py::test_elbow_closeup_depth_has_no_false_holes` errors with
  `ModuleNotFoundError` in all four parametrisations — unrelated to this plan but it masks your result.
- `examples/` and `tests/test_render_mesh_skeleton.py` fail collection on a bare checkout (missing
  `websockets`, and a module-level `pytest.skip`). Use
  `--ignore=examples --ignore=tests/test_render_mesh_skeleton.py` when you want a clean signal.

With both handled, the **pre-fix baseline is `569 passed, 85 skipped`**. Treat any other starting state as a
dirty tree and stop.

### 6.1 Verify the **shipped** archive, not an in-memory mask

`diagnose_mesh` rebuilds a fresh mask in process, so it cannot detect a stale zip. Check the archive:

```python
import zipfile, numpy as np
import build_christie_las as bcl, diagnose_mesh as dg, dds as pd2_dds

PATH, PACK, ITEM = "dist/Christie_LAS_Slim.zip", "Christie_LAS_Slim", "christie_slim"
p = dg.load(PATH, PACK, ITEM)
uv, faces, fmat, verts = p["uv"], p["faces"], p["fmat"], p["verts"]
with zipfile.ZipFile(PATH) as zf:
    blob = zf.read(next(n for n in zf.namelist()
                        if n.endswith(f"{ITEM}_c02_01_df.texture")))
size, _m, mip0 = pd2_dds.dds_mip0_slice(blob)
alpha = pd2_dds.decode_dxt5(mip0, size, size)[..., 3].astype(float)

def band(pred):
    sel = [fi for fi in np.where(fmat == "mtr_c02_01")[0] if pred(fi)]
    c = bcl.uv_to_texel_frac(uv[faces[sel]].mean(1))
    return alpha[(c[:, 1] * (size - 1)).astype(int),
                 (c[:, 0] * (size - 1)).astype(int)].mean()

arm, leg = p["w"]["arm"], p["w"]["leg"]
z = lambda fi: float(verts[faces[fi], 2].mean())
print("sleeve  ", band(lambda fi: float(arm[faces[fi]].mean()) > 0.40))
print("trousers", band(lambda fi: float(leg[faces[fi]].mean()) > 0.5
                       and float(arm[faces[fi]].mean()) < 0.1 and z(fi) > 20))
```

Pass condition on both packs: sleeve `5.94 ± 0.5`, trousers `11.35 ± 0.4`.

### 6.2 Reproduce the §4 tables

`§4.1` and `§4.2` are just the helper above applied to two mask implementations × two query conventions;
`§4.3`/`§4.4` compare `convert_textures(...)` output before and after
`retouch_sleeve_gloss(textures, None, ITEM, masks)`. Note `retouch_sleeve_gloss` keys masks by **role stem**
(`"c02_01"`, `"body"`, …), not by slot name — pass `{"body": …, "c02_01": …, "c02_02": …, "c02_05": …}`.

---

## 7. Acceptance criteria

1. `bcl.uv_to_texel_frac` exists and is the **only** UV→texel conversion in `build_christie_las.py`,
   `diagnose_mesh.py` and `tests/test_christie_las.py`. `grep -rn "1 + c\[1\]\|1.0 + c\[1\]\|1.0 + float(v)\|(1 + v)"
   tools/ tests/` returns nothing but prose.
2. Mask, at true texel coordinates, both packs:
   - `c02_01`: sleeve `> 0.5` **≥ 99.3 %** (`1729 / 1740`, `1754 / 1765`); non-sleeve hits in the trouser band
     `z ∈ [20, 60)` **== 0**; leg-only area share **< 1.0 %** (`0.79 %`); leg-only faces `≤ 60` (`34`); every
     leg hit at `z < 20` (`max = 12.1`); boot/ankle hits `≤ 40` (`34`).
   - `c02_02`: sleeve **100 %** (`679 / 679`); non-sleeve hits **== 0** (`base` drops `251 → 0`).
   - `mtr_body`: sleeve **≥ 99.7 %** (`160 / 160`, `926 / 928`); boot hits **== 0** (`base` drops `95 → 0`);
     hem residue `≤ 25` (`21`).
   - `c02_05`: mask stays all-zero; `uv_to_texel_frac` maps its stored `v ∈ [0.043, 0.980]` into
     `row ∈ [0.020, 0.957]`, never `[1.04, 1.98]`.
   - Read this as **two** numbers, never one: `0` in the trouser band is the correctness gate, `180` residual
     faces on shared islands (§4.5) is expected. A run that reports `0` total non-sleeve hits has probably
     broken the query again — real `c02_01` geometry shares islands with the sleeve.
3. Shipped `*_c02_01_df.texture`, both packs: sleeve alpha `∈ [5.4, 6.5]`, trouser (`z > 20`) alpha
   `∈ [11.0, 11.7]`, ratio `< 0.60`, and the trouser faces are unchanged from pre-retouch (`0 / 1343`
   darkened by more than 1 LSB).
4. `preview_textured._sample(..., flip_v=True)` on `cri_02_01_base.vtf` at boots (`z < 10`) returns
   `≈ (83, 49, 45)` on the 0–255 scale, not `≈ (146, 141, 133)`.
5. `diagnose_mesh.py` prints sleeve coverage `≥ 99 %` **and** a `0` for the trouser band, both packs.
6. `.venv/bin/pytest -q --ignore=examples --ignore=tests/test_render_mesh_skeleton.py` green at
   `569 passed, 85 skipped` or better (baseline in §6). `test_sleeve_gloss_mask_stays_on_the_sleeve` must fail
   Gate 1 if `uv_to_texel_frac` reverts to `(1 + v)` **or** if `centroid` reverts, and Gate 2 on the mask
   revert.

### 7.1 Self-check the agent can run before reporting done

Every criterion above was executed against a staged copy of the patched tree while writing this plan; the
recorded outputs were:

```
C1 wrap-identity test: PASS                      # both tile signs -> row 0.62
C2 slim  c02_01 sleeve=1729/1740 trouser=0 leg=34/0.79% maxz=12.1
   base  c02_01 sleeve=1754/1765 trouser=0 leg=34/0.79% maxz=12.1
   both  c02_02 sleeve=679/679  leakage=0 ; body sleeve 160/160 & 926/928
C3 slim sleeve=5.94 trouser=11.35 ratio=0.524 darkened=0/1343
   base sleeve=6.00 trouser=11.35 ratio=0.528 darkened=0/1343
C4 new _sample flip_v=True on boots = [83.0, 48.8, 45.4]
```

If your run disagrees with any line by more than a rounding step, do not proceed — the cause is almost always
one of: the guard threshold, `retouch_sleeve_gloss` receiving **slot** keys instead of **role stems**
(`"c02_01"`, not `"mtr_c02_01"`), or a stale `dist/*.zip` masking a correct in-memory mask (§6.1).

---

## 8. Rejected alternatives and interactions

### 8.1 Rejected: per-texel ownership weighting

Normalising the feathered mask by sleeve vs non-sleeve coverage (`own = S / (S + N)`) reduces the residual
faces' *intensity* but not their membership, and costs real sleeve attenuation:

| | plain (§5.1) | ownership-weighted |
|---|---:|---:|
| sleeve hit `> 0.5` (`c02_01` slim) | **99.37 %** | **88.50 %** |
| sleeve mean alpha | **5.95** | **6.34** |
| non-sleeve faces still hit | 180 | 180 |

It fails criterion 2 without improving the gate that matters.

### 8.2 Rejected: widen the face selection instead of fixing the row

Selecting sleeve faces by `z` / `|x|` bounds, or by material alone, "covers the arms" while still painting
hips (the `slim` arms are 25 % thinner, so their UVs do not move — only the bones do). The row is the bug.

### 8.3 Interaction with the DXT5 / normal-map plan

`retouch_sleeve_gloss` ends with `chain = pd2_dds.mip_payloads_from_mip0(...); chain[0] = mip0`, which
re-encodes **mip 0** and the whole pyramid. Measured on `_with_full_mip_chain` output: a
`pack_dds(mip_payloads_from_image(...))` round-trip of an untouched texture differs from the original in
`29 035` bytes, and mip 0 alone differs by up to `6 LSB`. That is the normal-map plan's item. If both land,
keep its lossless `_with_full_mip_chain` / `mip_payloads_from_mip0` replacement and this plan's mask
semantics; they compose (this plan changes *which* blocks are selected, that one changes *how* the pyramid is
serialised).

Also note `retouch_sleeve_gloss` rewrites all four `_df` textures even when a mask is all zero (`c02_05`
always; `c02_02` on `slim`). After the normal-map plan lands, assert that an all-zero mask is a byte-level
no-op rather than relying on the encoder being idempotent.

### 8.4 Interaction with the seam / forearm plan

`stitch_sleeve_seams` appends 43 (`slim`) / 36 (`base`) bridge triangles inside the arm shells. Their UVs jump
between the two rim islands (`du` up to `0.2119`), which is exactly what `max_uv_span = 0.12` skips. Run order
does not matter: measured, the guard changes neither the painted area nor the hit set.

### 8.5 Not fixed here: the atlas genuinely overlaps

`c02_01`'s sleeve island also carries 96 non-sleeve hem faces, and the boots share the sleeve-cuff trim
(§4.5). Fixing that needs new UVs for the DOA5 atlas — out of scope for a UV-row repair. Record it, gate the
trouser band at `0` and the leg residue at `< 1 %` area / `z < 20 cm`, and leave it.
