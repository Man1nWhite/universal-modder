# Christie LAS (`Slim` & `Base`) — Normal-Map Swizzle & Lossless DXT5 Mip-Chain Repair Plan (2026-11-07)

> **Audience:** an implementation agent picking up this repository cold.
> Every file path, line number, channel convention, block-level bit layout, and
> regression trap in this document has been empirically verified against commit
> `d0fe1e6`, `references/Christie.zip`, and the four in-game-verified PAYDAY 2
> packs in `dist/`.

## 0. Scope, Prerequisites & Context Links

### Problem Statement
Every `.texture` shipped in `dist/Christie_LAS_Slim.zip` and `dist/Christie_LAS.zip` suffers from two compounding texture-pipeline bugs in `tools/pd2-las/build_christie_las.py`, `tools/pd2-las/dds_encode.py`, and `tools/pd2-port/dds.py`:

1. **All four normal maps (`body`, `c02_01`, `c02_02`, `c02_05`) are swizzled 90° wrong:**
   `build_christie_las.py:374` calls `swizzle_source_normal_dxt5_to_pd2`, a helper written specifically for Mass Effect 2 / UE3-derived VTFs where `Red` and `Green` were pre-swapped (`R = Ny`, `G = Nx`). Christie's Dead or Alive 5 Source VTFs use **standard DirectX tangent-space channels (`R = +Nx right`, `G = +Ny down`, `B = +Nz`)**, so calling the UE3 helper puts `G_src` into `Alpha` and `255 - R_src` into `Green` — rotating and reflecting every pinstripe, lapel crease, shirt pleat, button, and skin contour by 90° (`mean error = 18.3–30.8 / 255` across the suit normal maps).
2. **Mip 0 of every diffuse and normal `.texture` is unnecessarily decoded and re-compressed with a naive lossy DXT5 encoder:**
   `_with_full_mip_chain` (`build_christie_las.py:333–354`) extracts `mip0`, leaves the variable unused, decodes the texture to 8-bit `RGBA`, and calls `pd2_dds.mip_payloads_from_image(rgba)`, overwriting lossless mip-0 BC3 blocks with naive min/max bounding-box RGB565 compression (`20.8%–59.3%` of mip-0 diffuse RGB pixels altered). `pd2_dds.mip_payloads_from_mip0` (`tools/pd2-port/dds.py:324`) repeats the same wasted mip-0 re-encode, and `retouch_sleeve_gloss` (`build_christie_las.py:463–503`) rebuilds full mip pyramids a second time even on roles where zero blocks changed.

### Related Audit & Repair Documents
- [`2026-11-07-christie-forearm-normals-and-seam-repair-plan.md`](2026-11-07-christie-forearm-normals-and-seam-repair-plan.md) — companion mesh normal, sleeve-seam stitch, `s_body` slice bounds, and orthonormal tangent-basis repair plan (can be implemented before, after, or together with this plan).
- [`2026-11-07-christie-slim-screenshot-review.md`](2026-11-07-christie-slim-screenshot-review.md) — 15-frame in-game visual defect review.
- [`../pd2-las/CHRISTIE.md`](../pd2-las/CHRISTIE.md) & [`../../tools/pd2-las/MODLOG.md`](../../tools/pd2-las/MODLOG.md) — Christie LAS build history and journal.

### Sandbox Bootstrap (Run First)
If `.venv` or `/tmp/2bsrc` is missing in a fresh workspace:

```bash
bash tools/pd2-las/bootstrap.sh
# Expected template directory for rebuilds and full tests:
# /tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b/{2b.model,fps_2b.model}
```

If `bootstrap.sh` does not extract `references/2b.rar` to `/tmp/2bsrc`, extract it before rebuilding (`mkdir -p /tmp/2bsrc && 7z x -y references/2b.rar -o/tmp/2bsrc`, or equivalent Python/unar extractor).

---

## 1. Empirical Root-Cause Verification

### 1.1 Proof of Channel Assignment & Handedness in `references/Christie.zip`
All four kept VMTs (`cri_body_base`, `cri_02_01_base`, `cri_02_02_base`, `cri_02_05_base`) are standard Source `VertexlitGeneric` materials with `$bumpmap` (no `$ssbump`) pointing to 1-mip `DXT5` VTFs.

1. **Sobel gradient-orientation test** comparing diffuse luminance edges $(\partial_x L, \partial_y L)$ against raw normal deflections $(|R - 128|, |G - 128|)$:

   | Source Material (`role`) | Size & Format | Vertical Edges (`∂xL ≫ ∂yL`, expect `\|Nx\| > \|Ny\|`) | Horizontal Edges (`∂yL ≫ ∂xL`, expect `\|Ny\| > \|Nx\|`) | Proven VTF Layout |
   |---|---|---|---|---|
   | `cri_body_base` (`body`) | `1024×1024` DXT5 (`1` mip) | `mean\|R-128\| = 5.01` vs `\|G-128\| = 1.10` (**4.6×**) | `mean\|G-128\| = 4.08` vs `\|R-128\| = 2.13` (**1.9×**) | `R = Nx`, `G = Ny` |
   | `cri_02_01_base` (`c02_01`) | `1024×1024` DXT5 (`1` mip) | `mean\|R-128\| = 37.55` vs `\|G-128\| = 12.57` (**3.0×**) | `mean\|G-128\| = 50.86` vs `\|R-128\| = 13.34` (**3.8×**) | `R = Nx`, `G = Ny` |
   | `cri_02_02_base` (`c02_02`) | `512×512` DXT5 (`1` mip) | `mean\|R-128\| = 49.06` vs `\|G-128\| = 11.53` (**4.3×**) | `mean\|G-128\| = 56.17` vs `\|R-128\| = 23.44` (**2.4×**) | `R = Nx`, `G = Ny` |
   | `cri_02_05_base` (`c02_05`) | `256×256` DXT5 (`1` mip) | Uniform lace/trim normal map (`R = Nx`, `G = Ny`, `meanRGB = [128.6, 127.9, 255.0]`) | Same DirectX VTF export | `R = Nx`, `G = Ny` |

2. **Sign/handedness test (`invert_y = True`):**
   - At concave dark creases ($\partial_x^2 L > 0$ or $\partial_y^2 L > 0$), raw `cri_body_base_nrm.vtf` yields:
     $$\text{corr}(\partial_x^2 L,\, \partial_x R) = -0.7408 \quad (+R = +X\text{ right}), \qquad \text{corr}(\partial_y^2 L,\, \partial_y G) = -0.7385 \quad (+G = +Y\text{ down, DirectX})$$
   - Measuring the same correlations on $(A, G)$ across all four **in-game-verified** PAYDAY 2 packs in `dist/` confirms Diesel's `DIFFUSE_TEXTURE:NORMALMAP` (`DXT5nm`) target convention:
     - `Miranda_L4D2_over_Joy` (`npc_criminal_joy_1_head_nm.texture`): `corr_X = -0.1753`, `corr_Y = +0.0570`
     - `Miranda_Romance_over_Joy` (`npc_criminal_joy_1_head_nm.texture`): `corr_X = -0.3035`, `corr_Y = +0.1433`
     - `Miranda_LAS` (`miranda_body_nm.texture`): `corr_X = -0.1207`, `corr_Y = +0.0227`
     - `lawson_las` (`body1_nm.texture`): `corr_X = -0.2853`, `corr_Y = +0.0763`
   - Every verified PAYDAY 2 normal map satisfies `corr_X < 0` (`A = +X right`) and `corr_Y > 0` (`G = +Y up`), i.e., matching `tools/pd2-port/dds.py::pd2_normal_channels(invert_y=True)`:
     $$R_{\text{out}} = 255, \qquad G_{\text{out}} = 255 - G_{\text{src}}, \qquad B_{\text{out}} = 0, \qquad A_{\text{out}} = R_{\text{src}}$$

3. **Palette LUT inaccuracy in existing `dds_encode.py:287`:**
   - Even when mapping a 2-bit BC1/BC3 index (`[1, 0, 2/3, 1/3]`) into 8-alpha DXT5 (`[1, 0, 6/7, 5/7, 4/7, 3/7, 2/7, 1/7]`), `dds_encode.py:287` hardcoded `lut_no_swap = [0, 1, 4, 5]` (`4/7 = 0.571`, `3/7 = 0.429` -> `9.5%` weight error) instead of `3` (`5/7 = 0.714`) and `6` (`2/7 = 0.286` -> `4.8%` weight error), or exact per-block 16-pixel `argmin`.

---

### 1.2 Proof of Mip-0 Re-encoding Damage (`_with_full_mip_chain` & `mip_payloads_from_mip0`)

1. **`_with_full_mip_chain` (`tools/pd2-las/build_christie_las.py:333–354`):**
   - `attenuate_dxt5_alpha_from_normal` (`dds_encode.py:152`) operates directly on the 8-byte DXT5 alpha half of each block, leaving 100% of the authored VTF RGB565 blocks (`bytes 8..16`) lossless.
   - Immediately afterward, `convert_textures` (`:375–376`) passes `df_dds` and `nm_dds` through `_with_full_mip_chain`, which decodes mip 0 to `RGBA` and calls `pd2_dds.mip_payloads_from_image(rgba)` — **discarding the lossless mip-0 blocks (`mip0` at `:347` is an unused dead variable!) and re-compressing mip 0 from scratch** with `pd2_dds.encode_dxt5`:

   | Texture (`role`) | Resolution | Mip-0 RGB Pixels Altered by `_with_full_mip_chain` | Max Channel Error | Mip-0 RGB PSNR vs VTF |
   |---|---|---:|---:|---:|
   | `body_df` | `1024×1024` | **`50.3%`** | `10 / 255` | `43.03 dB` |
   | `c02_01_df` | `1024×1024` | **`33.0%`** | `6 / 255` | `45.05 dB` |
   | `c02_02_df` | `512×512` | **`20.8%`** | `6 / 255` | `43.25 dB` |
   | `c02_05_df` | `256×256` | **`59.3%`** | `6 / 255` | `43.20 dB` |

2. **`pd2_dds.mip_payloads_from_mip0` (`tools/pd2-port/dds.py:324–327`):**
   - Decodes `mip0` and calls `mip_payloads_from_image(img)`, which re-encodes mip 0 (`75%` of all BC3 blocks in the entire mip pyramid!) before returning. `repair_dxt5_texture` (`dds.py:463`) and `retouch_sleeve_gloss` (`build_christie_las.py:501`) had to manually patch around this via `[mip0] + ...[1:]` / `chain[0] = bytes(mip0)`.

3. **Redundant second pyramid rebuild in `retouch_sleeve_gloss` (`build_christie_las.py:463–503`):**
   - Rebuilds all sub-mips `1..n` on every `*_df.texture` even when `(flat > 0.004).sum() == 0` (`body_df` and `c02_05_df` have zero sleeve-masked blocks).

---

## 2. Step-by-Step Implementation Specification

> **Rule reminder (`AGENTS.md`):** sequence edits to any single file one step at a time — never issue parallel edits to the same file.

### Phase 1 — Add Block-Space `swizzle_standard_normal_dxt5_to_pd2` in `dds_encode.py`
**File:** `tools/pd2-las/dds_encode.py`

> **CRITICAL TRAP — DO NOT MODIFY `swizzle_source_normal_dxt5_to_pd2` IN PLACE:**
> `tools/pd2-las/build_las.py:218` builds `dist/Miranda_LAS.zip` from `models/l4d2_miranda_lawson_1.zip`, whose UE3/ME2-derived VTFs genuinely store `R = ny_down` and `G = nx_right` (verified: `Miranda_LAS` has `corr_X = -0.1207, corr_Y = +0.0227`, and `tests/test_pd2_las.py` pins it). Leave `swizzle_source_normal_dxt5_to_pd2` intact for `build_las.py` (only clarifying its docstring), and add a **new** function `swizzle_standard_normal_dxt5_to_pd2` for standard DirectX `(R = Nx, G = Ny)` VTFs.

Add `swizzle_standard_normal_dxt5_to_pd2(nm_dds: bytes, invert_y: bool = True) -> bytes` right below `swizzle_source_normal_dxt5_to_pd2` (`:318`):

```python
def swizzle_standard_normal_dxt5_to_pd2(
    nm_dds: bytes, invert_y: bool = True
) -> bytes:
    """Swizzle standard DirectX DXT5 normal map (R=nx_right, G=ny_down, B=nz)
    to PAYDAY 2 DXT5nm (R=255, G=255-ny_down, B=0, A=nx_right) in BC3 block space.

    - Green (Ny): exact 6-bit -> 6-bit endpoint bijection (63 - g when invert_y)
      with lossless 2-bit index permutation (c_bits ^ 0x55555555 when swapped)
      so e0 >= e1 (R5=31, B5=0) holds on every block with zero quantization loss.
    - Alpha (Nx <- R): expands each block's exact 4-entry BC3 Red palette, fits
      8-bit endpoints (a0 >= a1) to the 16 block pixels' actual min/max, and
      assigns nearest 8-entry 3-bit alpha indices.
    """
    hdr = nm_dds[:128]
    blocks = np.frombuffer(nm_dds[128:], dtype=np.uint8).reshape(-1, 16)
    n = blocks.shape[0]
    out = np.zeros((n, 16), dtype=np.uint8)

    c0 = blocks[:, 8].astype(np.int32) | (blocks[:, 9].astype(np.int32) << 8)
    c1 = blocks[:, 10].astype(np.int32) | (blocks[:, 11].astype(np.int32) << 8)
    c_bits = (
        blocks[:, 12].astype(np.uint32)
        | (blocks[:, 13].astype(np.uint32) << 8)
        | (blocks[:, 14].astype(np.uint32) << 16)
        | (blocks[:, 15].astype(np.uint32) << 24)
    )

    # 1. Alpha <- Source Red (nx_right)
    r0 = ((c0 >> 11) & 31) * 255 // 31
    r1 = ((c1 >> 11) & 31) * 255 // 31
    pal_r = np.stack(
        [r0, r1, (2 * r0 + r1) // 3, (r0 + 2 * r1) // 3], axis=1
    )
    shifts_c = (2 * np.arange(16, dtype=np.uint32))[None, :]
    ci = (c_bits[:, None] >> shifts_c) & np.uint32(3)
    r_px = np.take_along_axis(pal_r, ci.astype(np.int64), axis=1)

    a0 = r_px.max(axis=1)
    a1 = r_px.min(axis=1)
    out[:, 0] = a0.astype(np.uint8)
    out[:, 1] = a1.astype(np.uint8)

    pal_a = np.empty((n, 8), dtype=np.int32)
    pal_a[:, 0] = a0
    pal_a[:, 1] = a1
    for i in range(1, 7):
        pal_a[:, i + 1] = ((7 - i) * a0 + i * a1) // 7
    idx_a = np.abs(r_px[:, :, None] - pal_a[:, None, :]).argmin(axis=2).astype(np.uint64)
    idx_a[a0 == a1] = 0
    shifts_a = (3 * np.arange(16, dtype=np.uint64))[None, :]
    a_bits = (idx_a << shifts_a).sum(axis=1, dtype=np.uint64)
    for b in range(6):
        out[:, 2 + b] = ((a_bits >> np.uint64(8 * b)) & np.uint64(0xFF)).astype(np.uint8)

    # 2. Green <- Source Green (ny_up if invert_y else ny_down), R=255, B=0
    g0 = (c0 >> 5) & 63
    g1 = (c1 >> 5) & 63
    if invert_y:
        g0 = 63 - g0
        g1 = 63 - g1
    swap_g = g0 < g1
    g_hi = np.where(swap_g, g1, g0)
    g_lo = np.where(swap_g, g0, g1)
    e0 = (31 << 11) | (g_hi << 5)
    e1 = (31 << 11) | (g_lo << 5)
    new_c_bits = np.where(swap_g, c_bits ^ np.uint32(0x55555555), c_bits)
    new_c_bits[e0 == e1] = 0

    out[:, 8] = (e0 & 0xFF).astype(np.uint8)
    out[:, 9] = ((e0 >> 8) & 0xFF).astype(np.uint8)
    out[:, 10] = (e1 & 0xFF).astype(np.uint8)
    out[:, 11] = ((e1 >> 8) & 0xFF).astype(np.uint8)
    for b in range(4):
        out[:, 12 + b] = ((new_c_bits >> np.uint32(8 * b)) & np.uint32(0xFF)).astype(np.uint8)

    return hdr + out.tobytes()
```

---

### Phase 2 — Preserve Mip 0 Losslessly in `tools/pd2-port/dds.py`
**File:** `tools/pd2-port/dds.py` (`:313–330`, `:460–466`)

1. **Factor sub-mip generation (`mips 1..n`) so `mip_payloads_from_mip0` never re-encodes mip 0:**
   ```python
   def _submip_payloads_from_image(img) -> list[bytes]:
       """Encode mip levels 1..n (size//2 down to 1x1) from an RGBA mip-0 array."""
       np = _np()
       level = np.asarray(img, dtype=np.uint8)
       h, w = level.shape[:2]
       if h != w or h == 0 or (h & (h - 1)):
           raise ValueError(f"texture must be square power-of-two, got {w}x{h}")
       payloads: list[bytes] = []
       while level.shape[0] > 1:
           level = downsample2x2(level)
           payloads.append(_level_payload(level))
       return payloads


   def mip_payloads_from_image(img) -> list[bytes]:
       """Full mip chain from an RGBA image (power-of-two, square)."""
       np = _np()
       arr = np.asarray(img, dtype=np.uint8)
       h, w = arr.shape[:2]
       if h != w or h == 0 or (h & (h - 1)):
           raise ValueError(f"texture must be square power-of-two, got {w}x{h}")
       return [_level_payload(arr)] + _submip_payloads_from_image(arr)


   def mip_payloads_from_mip0(mip0: bytes, size: int) -> list[bytes]:
       """Full mip chain preserving existing DXT5 mip-0 bytes losslessly (c0 >= c1)."""
       mip0_fixed, _ = fix_misordered_blocks(bytes(mip0), size)
       if size == 1:
           return [mip0_fixed]
       img = decode_dxt5(mip0_fixed, size, size)
       return [mip0_fixed] + _submip_payloads_from_image(img)
   ```
2. In `repair_dxt5_texture` (`:463`), simplify `payloads = [mip0] + mip_payloads_from_mip0(mip0, size)[1:]` to `payloads = mip_payloads_from_mip0(mip0, size)`.

---

### Phase 3 — Switch Christie Texture Pipeline to Standard Swizzle & Lossless Mip-0
**File:** `tools/pd2-las/build_christie_las.py` (`:62–66`, `:333–378`, `:463–503`)

1. **Imports (`:62–66`):**
   Replace `swizzle_source_normal_dxt5_to_pd2` with `swizzle_standard_normal_dxt5_to_pd2`.

2. **Lossless mip-0 preservation in `_with_full_mip_chain` (`:333–354`):**
   ```python
   def _with_full_mip_chain(dds_mip0: bytes) -> bytes:
       """Expand a 1-mip DXT5 .texture to vanilla PD2's full mipmap pyramid.

       Preserves the authored/block-edited mip-0 BC3 payload losslessly (after
       canonicalising c0 >= c1 endpoint order), decodes mip 0 via Pillow solely
       to box-filter mips 1..n down to 1x1, and writes the vanilla PD2 DDS header
       (flags 0x000A1007, caps 0x00401008).
       """
       import io

       import numpy as np
       from PIL import Image

       size, _mips, mip0 = pd2_dds.dds_mip0_slice(dds_mip0)
       mip0_fixed, _ = pd2_dds.fix_misordered_blocks(bytes(mip0), size)
       if size == 1:
           return pd2_dds.pack_dds([mip0_fixed], size)
       im = Image.open(io.BytesIO(dds_mip0))
       im.load()
       rgba = np.asarray(im.convert("RGBA"), dtype=np.uint8)
       payloads = [mip0_fixed] + pd2_dds._submip_payloads_from_image(rgba)
       return pd2_dds.pack_dds(payloads, size)
   ```

3. **Standard normal swizzle in `convert_textures` (`:374`):**
   ```python
   nm_dds = swizzle_standard_normal_dxt5_to_pd2(raw_nm, invert_y=True)
   ```

4. **Skip untouched roles & keep lossless mip 0 in `retouch_sleeve_gloss` (`:480–503`):**
   - Compute `role_touched = int((flat > 0.004).sum())`.
   - If `role_touched == 0`, `continue` immediately (avoids decoding and rebuilding 10 sub-mips on `body_df` and `c02_05_df` where 0 blocks changed).
   - Otherwise attenuate only `mip0[16 * bi : 16 * bi + 8]` (the 8-byte alpha block, leaving RGB bytes `8..16` bit-identical to the VTF), add `total += role_touched`, and pack `pd2_dds.pack_dds(pd2_dds.mip_payloads_from_mip0(bytes(mip0), size), size)`.
   - *Note on `DXT5nm` sub-mips (`1..n`):* Because PAYDAY 2's pixel shader reconstructs $n_z = \sqrt{\max(0, 1 - n_x^2 - n_y^2)}$ from $(A, G)$, 2×2 box filtering (`downsample2x2`) keeps uniform macro-slopes exact, cancels opposing pinstripe micro-ridges smoothly toward flat $(128, 128) \Rightarrow (0, 0, +1)$, and preserves `R = 255` (`R5 = 31`) and `B = 0` (`B5 = 0`) across every mip level `0..n`.
   - *Cross-defect note:* `sleeve_uv_mask` (`:390`) has a separate audit item for its V-flip (`(1.0 + v)` vs `(-v) % 1.0`). Because `retouch_sleeve_gloss` only edits mip-0 alpha blocks and preserves mip-0 RGB losslessly, this plan and any `sleeve_uv_mask` fix compose cleanly in either order.

---

### Phase 4 — Automated Tests, Diagnostics & Pack Rebuild
**Files:** `tests/test_las_pack.py`, `tests/test_christie_las.py`, `tools/pd2-las/MODLOG.md`

#### 4.1 Unit Tests (`tests/test_las_pack.py` — fast CI, no external archives needed)
1. **`test_swizzle_standard_normal_dxt5_to_pd2_repacks_channels`**:
   - Construct a `16×16` RGBA test image with distinct `(R=210, G=128, B=255, A=90)` and `(R=128, G=200, B=255, A=40)` blocks, encode to 1-mip DXT5 via `dds_encode.rgba_to_bc3_dds`, run `swizzle_standard_normal_dxt5_to_pd2(..., invert_y=True)` and `invert_y=False`, decode, and assert:
     - `R == 255` and `B == 0` everywhere (`R5 == 31`, `B5 == 0`, `c0 >= c1`).
     - `Alpha` tracks source `Red` (`|A - R_src| <= 3`) and ignores source `Alpha` (`90`/`40`).
     - `Green` tracks `255 - G_src` when `invert_y=True` and `G_src` when `invert_y=False`.
2. **`test_mip_payloads_from_mip0_preserves_mip0_bytes`**:
   - Construct a `16×16` canonical DXT5 mip-0 payload (`c0 >= c1`) whose RGB565 endpoints differ from `encode_dxt5`'s bounding-box choice; assert `dds.mip_payloads_from_mip0(mip0, 16)[0] == mip0` byte-for-byte and `len(chain) == 5`.

#### 4.2 Shipped-Pack Integration Tests (`tests/test_christie_las.py`, parametrized over `"slim"` and `"base"`)
1. **`test_normal_maps_match_standard_pd2_dxt5nm_layout`**:
   - For every role (`body`, `c02_01`, `c02_02`, `c02_05`), compare shipped `{item_id}_{role}_nm.texture` against raw VTF `raw_nm` from `references/Christie.zip`:
     - `pd2_dds.validate_dxt5_texture(blob) == []` and `pd2_dds.misordered_blocks(mip0, size) == []`.
     - Across **every** DXT5 block in the entire mip pyramid (`blob[128:]`), `((c0 >> 11) & 31) == 31` (`R = 255`) and `(c0 & 31) == 0` (`B = 0`).
     - Mip-0 decoded `Alpha` matches source decoded `Red` (`mean |A - R_src| < 1.0`, `corrcoef > 0.995` on `c02_01` / `c02_02` / `body`).
     - Mip-0 decoded `Green` matches `255 - G_src` (`max |G - (255 - G_src)| <= 2`).
     - **TRAP NOTE ON THE `<= 2` LSB TOLERANCE FOR DECODED `G`:** Even though `g_out = 63 - g_src` is an exact 6-bit bijection on endpoints `c0, c1` and 2-bit indices, `decode_dxt5` uses integer floor division `(2*e0 + e1) // 3`, and `255 - ((2*a + b) // 3)` differs by `1–2` LSB from `(2*(255 - a) + (255 - b)) // 3` when `(2*a + b) % 3 != 0`. Assert exact 6-bit endpoint complementarity on the raw RGB565 words **and/or** `<= 2` on decoded 8-bit `G` — do **not** assert `== 0` after integer floor-division decode.
2. **`test_diffuse_mip0_rgb_is_lossless_from_source_vtf`**:
   - For every role (`body`, `c02_01`, `c02_02`, `c02_05`), decode mip 0 of shipped `{item_id}_{role}_df.texture` and mip 0 of `vtf.to_dds(parse_vtf(...))` from `references/Christie.zip`, and assert **`np.array_equal(shipped_rgb, source_rgb)`** (`0` altered RGB pixels out of 1,048,576 at mip 0).

#### 4.3 Rebuild & Sign-Off Commands
Rebuild **both** Christie variants so `dist/*.zip`, `dist/*.zip.sha256`, `BUILD_INFO.json`, and `build/pd2-las/*_report.json` remain synchronized:

```bash
# 1. Rebuild both Christie LAS packs + previews
.venv/bin/python tools/pd2-las/build_christie_las.py \
    --variant slim \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

.venv/bin/python tools/pd2-las/build_christie_las.py \
    --variant base \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"

# 2. Run unit + pack integration suites (including Miranda_LAS & lawson_las regression checks)
.venv/bin/pytest tests/test_las_pack.py tests/test_pd2_las.py tests/test_christie_las.py -q
.venv/bin/pytest tests -q

# 3. Static lint
.venv/bin/python -m pyflakes \
    tools/pd2-las/dds_encode.py \
    tools/pd2-port/dds.py \
    tools/pd2-las/build_christie_las.py \
    tests/test_las_pack.py \
    tests/test_christie_las.py
```

#### 4.4 Acceptance Checklist Before Closing the Task
- [ ] `swizzle_source_normal_dxt5_to_pd2` preserved untouched for `build_las.py` (`Miranda_LAS.zip` tests in `tests/test_pd2_las.py` pass).
- [ ] All 4 `{item_id}_{role}_nm.texture` files in both `Christie_LAS_Slim.zip` and `Christie_LAS.zip` have `R=255`, `B=0`, `A ≈ R_src` (`mean_err < 1.0`), and `G ≈ 255 - G_src` (`max_err <= 2`), with valid 11/10/9-mip chains and `c0 >= c1` on every block.
- [ ] All 4 `{item_id}_{role}_df.texture` files in both packs have **100% lossless mip-0 RGB** (`max |RGB_shipped - RGB_vtf| == 0`, down from `20.8%–59.3%` altered pixels).
- [ ] `retouch_sleeve_gloss` skips roles with `0` masked blocks and `test_sleeve_gloss_mask_stays_on_the_sleeve` remains green.
- [ ] `tools/pd2-las/MODLOG.md` updated with rebuilt `dist/Christie_LAS_Slim.zip` and `dist/Christie_LAS.zip` byte sizes, SHA-256 hashes, and mip-0 fidelity numbers.
