# Three-Zone Neck Artifact — Protruding Unslimmed Rim + Rejected Opening + Mis-Normalled Cap

**Status:** ready to execute — every number below was measured on this checkout
**Date:** 2026-11-09
**Audience:** a cold-start coding agent with no prior session context
**Repos touched:** `tools/pd2-las/build_models.py`, `tests/test_neck.py`, new `tests/test_neck_three_zone.py`

---

## 0. TL;DR

The neck defect is **three independent failures that stack**, not one:

| Zone | What you see | What it is | Where |
|---|---|---|---|
| **1** | The body's neck rim juts out over the collar | `slim_neck`'s radial mask is **exactly zero at the rim** (`r_stop = 14` against a 9.4–18.8 cm rim), and it is centred on the **PD2** axis (`y=7.0`) rather than the retarget's **3BA** axis (`y≈9.5`), so the visible shrink is asymmetric | `build_models.py:2027` |
| **2** | The neck is **open to the inside of the torso** | `cap_holes` throws the real opening away twice: `min_z` is all-or-nothing on the loop's *lowest* vertex, and `max_span` measures the **bbox diagonal**, which inflates a circle by √2 | `build_models.py:2605` |
| **3** | A flat skin **shelf slants across the throat** | the cap's stored vertex normal is `Σ n̂ᵢ / ‖Σ n̂ᵢ‖`. A round rim's vertex normals **cancel**, so this is normalised rounding noise — **90° off the facets it belongs to**. The lid is geometrically flat but shades like a vertical wall | `build_models.py:2644-2649` |

The three are ordered: while zone 1 keeps the rim wide, zone 2 rejects the loop, so **zone 3 never gets to run on the neck** and the player sees zone 1's rim plus a hole. That is why fixing any one of them alone made the artifact worse in the earlier attempts (§8.1).

**Chain, measured (§4.3): the old passes leave a 14.05 cm opening that `cap_holes` refuses; the fix takes it to 9.40 cm — the PD2 reference — and closes it with a 32-facet lid whose normal is the rim's own plane normal.**

---

## 1. Scope and deliverables

| | |
|---|---|
| Primary fix | `tools/pd2-las/build_models.py` — `slim_neck` (`:2027`), `cap_holes` (`:2605`), new helpers `_top_rim`, `_ring_plane`, `_planar_diameter` |
| Tests | new `tests/test_neck_three_zone.py` (8 tests); `tests/test_neck.py` — 4 tests moved to the explicit-constant contract |
| Call sites | `tools/pd2-las/build_skyrim_outfit.py:313` (`slim_neck`), `:413` (`cap_holes`) — **no change needed**, the defaults do the right thing |
| Artefacts | rebuild `dist/` only if the Skyrim port is reopened (§7.1) |

### 1.1 Can this be executed here? — read before starting

Both functions are called from exactly two places, both in the Skyrim 3BA outfit port:

```
tools/pd2-las/build_skyrim_outfit.py:313        rep = bm.slim_neck(groups[gname])
tools/pd2-las/build_skyrim_outfit.py:413        capped = bm.cap_holes(g, min_z=NECK_Z_CM, ...)
```

That port is **cancelled and not rebuildable from this checkout** (`docs/skyrim-nif/STATUS.md`): the five source archives were deleted on 2026-11-04, the built pack and `build/skyrim-nif/` were removed, and `tests/test_skyrim_fit.py:177` skips the archive-dependent packet tests explicitly.

There are therefore two routes, with different acceptance criteria:

- **Route A (default, fully executable today):** land the code and the synthetic-fixture regression tests. The fixtures are built at the measurements the pass docstrings record, so the geometry contract is pinned by tests that run without the archives. §4.3 and §7.2 apply. **This is completable end to end — do it and stop.**
- **Route B (needs the user to re-supply sources):** rebuild the pack and verify in-geometry. §7.1 applies. **Do not start Route B unless the user explicitly reopens the port** — `docs/skyrim-nif/STATUS.md` says so in as many words.

### 1.2 What is *not* in scope

- **Christie.** `dist/Christie_LAS.zip` / `dist/Christie_LAS_Slim.zip` do **not** route through either function — the Christie builder uses `slim_group` (`build_christie_las.py:2716`), never `slim_neck`. Both shipped packs have **no neck opening at all**; §3.4 is the measurement. Do not try to reproduce the artifact there.
- **`align_neck` / `trim_neck`.** Already reverted out of the build (`tools/pd2-port/MODLOG.md:36`); they remain as library functions with their own tests. Leave them.

---

### 1.3 Anchor every edit by symbol, never by line number

All line numbers in this document are **`HEAD` line numbers**, verified against
`git show HEAD:tools/pd2-las/build_models.py` on 2026-11-09. They are correct
for the tree you start from and **wrong the moment you apply §5** — §5.1 adds
`_top_rim` and §5.2 adds `_ring_plane` + `_planar_diameter`, which shifts
everything below them down by ~5 and ~130 lines respectively.

Locate code by symbol:

```bash
grep -n "^def slim_neck\|^def cap_holes\|^def _slice_vertex_order\|^def winding_agreement" \
    tools/pd2-las/build_models.py
```

The two replacements are bounded by symbols, not offsets:

* **§5.1** replaces the text from `def slim_neck(` up to **but not including**
  `def _slice_vertex_order(`.
* **§5.2** replaces the text from `def cap_holes(` up to **but not including**
  `def winding_agreement(`.

Do not `sed -i '2027,...d'` or apply any offset-based edit. If a line number in
this document disagrees with `grep`, **`grep` is right**.

## 2. What the code does today

### 2.1 `slim_neck` — `build_models.py:2027` (at `HEAD`; `:2083` after this plan)

```python
def slim_neck(g: Group, mats=("skin",), axis=(0.0, 7.0),
              z_lo: float = 157.0, z_full: float = 161.0,
              r_full: float = 8.0, r_stop: float = 14.0,
              sx: float = 0.55, sy: float = 0.70) -> dict:
```

Per skin vertex above `z_lo = 157`:

```
r    = hypot(x - 0.0, y - 7.0)
mask = smooth((r_stop - r) / (r_stop - r_full))     # = smooth((14 - r) / 6)
t    = smooth((z - 157) / 4) * mask
k    = 1 - (1 - 0.55) * t                            # x;  0.70 for y
x,y  = axis + (x,y - axis) * k
```

A radial scale about `(0, 7.0)`, full for `r ≤ 8`, **exactly zero for `r ≥ 14`**, ramped in with height over `157 → 161`.

### 2.2 `cap_holes` — `build_models.py:2605` (at `HEAD`; `:2728` after this plan)

For every boundary loop:

```
if min(z[idx]) < min_z:                     continue     # all-or-nothing
if any(i not in allowed for i in idx):      continue
span = || max(P) - min(P) ||                            # bbox diagonal
if span > max_span:                         continue
centre = mean(P[ring])                                  # fine: on the cut plane
normal = sum(normals[ring]) / (||sum|| or 1.0)          # <-- cancels to ~0
... fan (b, a, new_index) for each ring edge ...
```

Caller (`build_skyrim_outfit.py:413`) passes `min_z=NECK_Z_CM = 155.0` (`:45`), `max_span=14.0`.

### 2.3 Pass order (`build_skyrim_outfit.py`)

```
:313  slim_neck            <- zone 1 created here
:325  redress_from_source
       weld_open_seams, follow_layer_weights, tuck_*, extend_sleeves_to_wrist,
       tuck_necklace_chain
:386  lower_collar          (k = COLLAR_K = 0.55)
:404  turn_upper_body       (1.8 deg about (0, 2.5, 98), ramp 98 -> 118)
:413  cap_holes             <- zones 2 and 3 decided here
```

Order matters twice, both against the fix: `slim_neck` runs **before** the pitch that aligns the neck, and `cap_holes` runs **after** it, so the pitch has already lowered the back of the rim when the `min_z` gate reads it (§3.2).

---

## 3. Root cause

### 3.1 Zone 1 — the mask is zero at the rim, and it is centred on the wrong axis

**(a) The mask is zero exactly where the rim is.** The docstring's own measurement says the retargeted column is *"18.8 cm wide at 160"* and the PD2 reference *"9.4 cm"*. Read 18.8/9.4 as diameters (half-widths 9.4/4.7) and evaluate:

| half-width r | `smooth((14-r)/6)` | radius after the `sx=0.55` scale |
|---:|---:|---:|
| 4.70 | 1.000 | 2.59 |
| 8.00 | 1.000 | 4.40 |
| 9.40 | **0.862** | 5.75 |
| 10.00 | 0.741 | 6.67 |
| 12.00 | 0.259 | 10.60 |
| 13.00 | 0.074 | 12.57 |
| **14.00** | **0.000** | 14.00 |
| 18.80 | 0.000 | 18.80 |

The rim lands at 5.75 cm half-width, **1.22×** the 4.70 cm reference. Read 18.8 as a *half-width* instead and `mask = 0`, so the rim is **not touched at all**: 18.80 against 4.70, **4.0×**.

**(b) The axis is the wrong theister's.** `axis=(0.0, 7.0)` is the **PD2** neck axis; the retarget recentres onto the **3BA** axis first, which `align_neck`'s docstring records at *"y≈9.5 cm"* (`build_models.py:1510`). A 9.4 cm-radius rim centred at `y = 9.5`, masked about `y = 7.0`:

| point on the rim | `y` | `r` about 7.0 | mask | half-width after |
|---|---:|---:|---:|---:|
| front (+y) | 18.90 | 11.900 | 0.282 | **8.21** |
| front-side | 16.15 | 11.305 | 0.424 | 7.61 |
| side (+x) | 9.50 | 9.727 | 0.799 | 6.02 |
| back-side | 2.85 | 7.833 | 1.000 | 5.17 |
| back (−y) | 0.10 | 6.900 | 1.000 | **5.17** |

The front comes out **1.59×** the back: the opening is no longer a circle, it is an egg points-forward. Run on the real fixture (§4.5) the rim's circularity becomes **0.116** against **0.000** for the calibrated pass, and the far side of the neck disappears under the collar while the near side stands proud of it. That is exactly the *"hard horizontal skin **shelf** across the front of the neck base and a **notch** behind it"* recorded in `tools/pd2-port/MODLOG.md:101-105`.

> **Which reading of "18.8 cm wide" is right?** The docstring and the MODLOG disagree and I cannot settle it: the mesh that would answer it (`dist/skyrim_outfit.zip`) was deleted with the port. **The fix does not depend on the answer** (§5.1), but in any write-up say "1.2× to 4.0× too wide" rather than picking one.

### 3.2 Zone 2 — `cap_holes` rejects the real opening, twice over

**Gate A, `min_z`, is all-or-nothing on the loop's lowest vertex.** A diagonally cut opening straddles any threshold, and `turn_upper_body` has already lowered the back of the neck by ~0.3 cm before this gate runs:

| rim centre z | `min(z[idx])` after the 1.8° pitch | gate at 155.0 |
|---:|---:|---|
| 155.50 | 153.988 | **REJECTED** |
| 156.00 | 154.488 | **REJECTED** |
| 156.50 | 154.988 | **REJECTED** |
| 156.75 | 155.238 | passes |
| 157.00 | 155.487 | passes |

A 1.5 cm cut swings the verdict across ±0.75 cm of ring centre: the same neck is capped or not depending on where its diagonal happens to sit.

**Gate B, `max_span`, measures the bbox diagonal, not the opening.** For a circle of diameter D in a plane, `‖max − min‖` inflates by up to √2, and a tilted ring inflates on the third axis as well:

| ring | bbox diagonal | in-plane diameter | `bbox ≤ 14` | `planar ≤ 14` |
|---|---:|---:|---|---|
| circle D=9.40, flat | 13.29 | 9.40 | pass | pass |
| circle D=9.40, 1.5 cm tilt | 13.63 | 9.87 | pass | pass |
| circle D=9.86, 1.5 cm tilt | 14.26 | 10.31 | **reject** | pass |
| circle D=14.05, 1.5 cm tilt | 20.44 | 14.05 | **reject** | **reject** |
| circle D=15.50, flat | 21.92 | 15.50 | reject | reject |
| circle D=18.80, flat | 26.59 | 18.80 | reject | reject |
| UV seam, straight 100 cm | 100.00 | 100.00 | reject | reject |
| UV seam, 40×44 ellipse | 59.46 | 44.00 | reject | reject |

So the gate is simultaneously **too strict** (rejects a 9.86 cm neck) and pointed at the wrong quantity. It is also **too loose in the other direction**: a closed *seam* between two UV shells is a boundary loop too, and a small seam loop passes `bbox ≤ 14` happily. On the shipped Christie packs, 3 loops above `z=155` pass both gates and all 3 are seam loops, not openings (§3.4).

### 3.3 Zone 3 — the cap's normal is normalised rounding noise

`normal = Σ n̂ᵢ / (‖Σ n̂ᵢ‖ or 1.0)`.

**The arithmetic-mean apex is fine — I checked, and it is not the defect.** For a symmetric rim the centroid lies exactly on the cut plane (measured: `0.000000 cm` off-plane for 4-, 8- and 32-segment rings at every tilt). On the shipped meshes it is at most **0.586 cm** off, and the maximum facet tilt it can induce is small. Do not "fix" the apex; there is nothing there.

**The stored normal is the defect.** A tube's rim vertex normals point radially outward and **cancel exactly**:

| ring | ‖Σ n̂ᵢ‖ | stored normal | correct (fan plane) normal | error |
|---|---:|---|---|---:|
| round, 32 seg, flat | 1.5e-15 | (−0.696, −0.718, **0.000**) | (0, 0, ±1) | **90.0°** |
| round, 32 seg, 1.5 cm tilt | 1.5e-15 | (−0.696, −0.718, **0.000**) | (0, 0, −0.975) | **101.4°** |
| round, 8 seg, flat | 2.2e-16 | — | (0, 0, ±1) | **90.0°** |

The `or 1.0` guard is what makes it dangerous: `float(np.linalg.norm(v)) or 1.0` forwards the ~1e-15 residue instead of catching it, so the shader receives a **unit vector pointing in an essentially random direction** — horizontal on a horizontal cap.

Measured on the **shipped** Christie pack (same code path, so the defect is live even though the neck is elsewhere) — this is the table to reproduce:

| loop n | zmin | ‖Σ n̂ᵢ‖ | stored vs fan | apex off-plane | min facet \|nz\| |
|---:|---:|---:|---:|---:|---:|
| 56 | 155.1 | 13.514 | **85.6°** | 0.586 | 0.048 |
| 54 | 155.1 | 8.312 | **57.0°** | 0.231 | 0.066 |
| 20 | 160.9 | 0.781 | **31.4°** | 0.239 | 0.938 |
| 4 | 159.1 | 0.677 | **93.2°** | 0.208 | 0.278 |
| 4 | 158.1 | 0.268 | **66.8°** | 0.230 | 0.728 |
| 3 | 156.8 | 3.000 | 0.0° | 0.000 | 0.818 |

**5 of 6 caps ship a normal more than 30° off their own facets.** That is the shelf: a geometrically flat lid lit as though it were a wall across the throat.

### 3.4 Why you cannot reproduce this on Christie

| | slim | base |
|---|---:|---:|
| boundary loops | 79 | 110 |
| loops passing `min_z ≥ 155` | 6 | 6 |
| loops passing **both** current gates | 3 | 3 |
| loops that are the neck opening | **0** | **0** |

Every high loop is a UV-shell seam with a 17–23 cm bbox span (`max_span` rejects it) or a small 3–4-vertex closed seam (which it admits — the §3.2 looseness). Neither shipped Christie pack has an open neck: the widest top loop spans `z 160.9–163.2` and is a seam, and the mesh is otherwise closed. Christie uses `slim_group` (`build_christie_las.py:2716`), never `slim_neck`.

**Do not spend time trying to reproduce this on Christie.** Any reproduction must be synthetic (this plan) or come from a rebuilt Skyrim pack.

---

## 4. Measurements that define the acceptance gates

### 4.1 The `slim_neck` mask table (§3.1)

```python
def smooth(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
[r for r in (4.7, 8, 9.4, 10, 12, 13, 14, 18.8)]
# mask:  1.000 1.000 0.862 0.741 0.259 0.074 0.000 0.000
```

Gate: the rim must land within **5 %** of `target_hw`, and its **circularity** `std(r)/mean(r)` about its own centroid must be `< 0.02`.

### 4.2 The two `cap_holes` gates (§3.2)

- **z:** compare the loop **centroid** to `min_z`, not `min(z[idx])`.
- **span:** compare the **in-plane diameter** to `max_span`; add a roundness bound so a pathological ring (a hair-sheet boundary, a sliver) cannot be capped.

Measured roundness `std(r)/mean(r)` for the Christie loops that pass the current z gate:

| loop n | zmin | bbox | in-plane Ø | roundness | verdict |
|---:|---:|---:|---:|---:|---|
| 56 | 155.1 | 21.95 | 17.22 | 0.086 | seam, span-rejected |
| 54 | 155.1 | 21.94 | 17.19 | 0.065 | seam, span-rejected |
| 20 | 160.9 | 17.05 | 12.52 | **0.048** | admitted by the planar gate — §8.2 |
| 4 | 159.1 | 6.28 | 5.34 | 0.078 | seam, admitted today |
| 4 | 158.1 | 6.60 | 6.60 | 0.202 | seam, admitted today |
| 3 | 156.8 | 5.96 | 5.76 | 0.320 | seam, admitted today |

Roundness across all 79 / 110 loops: median 0.300 / 0.194, 40 / 66 loops below 0.30. **A roundness bound alone cannot separate openings from seams** — §8.2.

### 4.3 The end-to-end fixture — this is the acceptance table

Synthetic 3BA column: 12 cm half-width at the 157 source stop (per the `slim_neck` docstring), 9.4 cm half-width at 167 ("18.8 cm wide"), a 1.5 cm diagonal opening cut, 32 segments, bottom closed.

```
                     stage   top rim Ø   bbox diag    cap_holes
        after OLD slim_neck       14.05       20.44    OPEN
        after NEW slim_neck        9.40       13.63    CLOSED 32
                (2B reference)     9.40
```

The old chain leaves a **14.05 cm hole** that both gates refuse (`bbox 20.44 > 14`, and after `turn_upper_body` `min_z 153.4 < 155`). The new chain lands the rim on the reference to 2 decimals and closes it with 32 facets. `tests/test_neck_three_zone.py` asserts this table.

### 4.4 Real-mesh safety, measured

The calibrated `slim_neck` over the shipped Christie slim body (a good proxy for any body: 18.8 cm diameter at 160, same as the retarget):

```
axis  = (0.015, 4.088)     scale = 0.807     rim_hw = 5.83 cm
displaced: 448 verts, max 1.25 cm
  shoulder z 137-154, |x|>10 :     0 /  320 moved
  arms |x|>18                :     0 / 1592 moved
  chest z 120-150 front      :     0 / 1257 moved
  neck z>157                 :   448 /  485 moved
```

**Zero displacement outside the neck** — the property the trapezius mask exists to protect. (The old pass displaced 485 verts by up to 3.75 cm.)

### 4.5 Real-mesh rim shape, measured

The same fixture geometry on the real body, comparing the two passes:

| state | rim half-width | circularity | front | back |
|---|---:|---:|---:|---:|
| untouched (retargeted) | 9.40 | 0.0000 | 9.40 | 9.40 |
| **OLD** `slim_neck` | 7.03 | **0.1155** | 8.39 | 7.33 |
| **NEW** `slim_neck` | **4.70** | **0.0000** | 4.70 | 4.70 |

The old pass leaves the rim 1.5× too wide *and* egg-shaped; the new one hits the reference exactly and keeps it round.

---

## 5. Implementation

Apply §5.1 and §5.2 to `tools/pd2-las/build_models.py`. Both replacements are drop-in; **the call sites in `build_skyrim_outfit.py` need no edit.**

### 5.1 `slim_neck` — replace the whole function

Replace from `def slim_neck(` up to (not including) `def _slice_vertex_order(`. Put the new `_top_rim` helper immediately before it.

```python
import numpy as np


def _top_rim(g: Group, mats) -> list[int] | None:
    """The boundary ring of the skin slice whose vertices sit highest.

    The neck opening is the only boundary loop of the skin slice that reaches
    the top of the column. Reading the geometry off this rim (instead of
    carrying a hardcoded axis, radius and scale) is what keeps the pass working
    when the retarget changes the column width.
    """
    skin: set[int] = set()
    for mat, base_v, _bi, _t, nv in g.slices:
        if mat in mats:
            skin.update(range(base_v, base_v + nv))
    if not skin:
        return None
    counts: dict[tuple[int, int], int] = {}
    directed: dict[tuple[int, int], int] = {}
    for a, b, c in g.faces:
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            counts[key] = counts.get(key, 0) + 1
            directed[(x, y)] = directed.get((x, y), 0) + 1
    edges = [(x, y) for (x, y) in directed
             if counts[(x, y) if x < y else (y, x)] == 1
             and x in skin and y in skin]
    if not edges:
        return None
    nxt: dict[int, list[int]] = {}
    for x, y in edges:
        nxt.setdefault(x, []).append(y)
    seen: set[tuple[int, int]] = set()
    best: tuple[float, list[int]] | None = None
    for x, y in edges:
        if (x, y) in seen:
            continue
        loop, cur = [x], (x, y)
        while cur not in seen:
            seen.add(cur)
            loop.append(cur[1])
            cand = [v for v in nxt.get(cur[1], []) if (cur[1], v) not in seen]
            if not cand:
                break
            cur = (cur[1], cand[0])
        if len(loop) < 4 or loop[0] != loop[-1]:
            continue
        ring = loop[:-1]
        top = max(g.verts[i][2] for i in ring)
        if best is None or top > best[0]:
            best = (top, ring)
    return None if best is None else best[1]


def slim_neck(g: Group, mats=("skin",), axis=None,
              z_lo: float = 157.0, z_full: float = 161.0,
              r_full: float | None = None, r_stop: float | None = None,
              sx: float | None = None, sy: float | None = None,
              target_hw: float = 4.70, fade: float = 5.0,
              min_scale: float = 0.30) -> dict:
    """Slim the neck to the PD2 reference, measured on the mesh's own opening.

    The 3BA body is authored for Skyrim, where the *head* mesh supplied most of
    the neck: the source body stops at 157 cm and hands the neck over. The
    retarget stretches the spine axially to PD2's longer torso, which also lifts
    and widens that stub, so the shipped body carries an 18.8 cm wide column up
    to 167 cm -- in the previews it reads as a stovepipe rising out of the
    collar, and no collar can close over it. The PD2 reference body (2B) is the
    ground truth for this rig: 9.4 cm wide at 160-163.

    Three constants have to be right for the pass to bite, and each was wrong:

    ``axis``
        the column's own centre. The retarget is recentred onto the 3BA axis
        (y≈9.5, see :func:`align_neck`), not the PD2 one (y≈7.0). Measuring
        about the wrong centre moves the radial mask by 2.5 cm, so the *front*
        of the neck (r 11.9 from y=7.0) is barely touched while the *back*
        (r 6.9) is slimmed to the floor -- a 1.6x front/back asymmetry that
        reads as a rim protruding over the collar.
    ``r_full`` / ``r_stop``
        the mask band. With ``r_full=8, r_stop=14`` every vertex between 14 and
        the 18.8 cm rim takes ``mask = 0`` and is left exactly as the retarget
        built it. The rim is the one part that must move.
    ``sx`` / ``sy``
        the scale. 0.55 on an 18.8 cm half-width still lands at 10.3 cm, i.e.
        2.2x the 4.7 cm reference. The factors were tuned on a 9.4 cm column
        and never revisited when the docstring's own measurement said 18.8.

    With no ``axis``/``r_full``/``r_stop``/``sx``/``sy`` given, the pass reads
    its geometry off the mesh: the top rim of the skin slice gives the axis and
    the half-width, the mask band is derived from that half-width (full inside
    it, fading out over ``fade``), and the scale is whatever makes the rim land
    on ``target_hw``. Callers that pass the constants explicitly get the old
    behaviour, which is what the existing unit tests pin.

    It keeps the radial-only, height-ramped shape either way: the neck must
    retain its full height to meet the heister's head (shortening it opened a
    gap under the jaw), and the trapezius and shoulder line stay untouched.
    """
    def smooth(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    calibrated = axis is None
    rim_hw = 0.0
    scale = 1.0
    if calibrated:
        ring = _top_rim(g, mats)
        if not ring or len(ring) < 3:
            return {"moved": 0, "peak": 0.0, "axis": None, "scale": 1.0,
                    "rim_hw": 0.0}
        P = np.asarray([g.verts[i] for i in ring], dtype=np.float64)
        cx, cy = float(P[:, 0].mean()), float(P[:, 1].mean())
        rim_hw = float(np.hypot(P[:, 0] - cx, P[:, 1] - cy).mean())
        if rim_hw <= 1e-6:
            return {"moved": 0, "peak": 0.0, "axis": None, "scale": 1.0,
                    "rim_hw": 0.0}
        scale = max(min_scale, min(1.0, target_hw / rim_hw))
        axis = (cx, cy)
        r_full = rim_hw * 1.05
        r_stop = r_full + fade
        sx = sy = scale
    else:
        r_full = 8.0 if r_full is None else r_full
        r_stop = 14.0 if r_stop is None else r_stop
        sx = 0.55 if sx is None else sx
        sy = 0.70 if sy is None else sy

    ax, ay = axis
    touched, moved = 0, 0.0
    for mat, base_v, _bi, _t, nv in g.slices:
        if mat not in mats:
            continue
        for i in range(base_v, base_v + nv):
            x, y, z = g.verts[i]
            if z <= z_lo:
                continue
            r = math.hypot(x - ax, y - ay)
            mask = smooth((r_stop - r) / max(r_stop - r_full, 1e-6))
            t = smooth((z - z_lo) / max(z_full - z_lo, 1e-6)) * mask
            if t <= 0.0:
                continue
            kx = 1.0 - (1.0 - sx) * t
            ky = 1.0 - (1.0 - sy) * t
            nx = ax + (x - ax) * kx
            ny = ay + (y - ay) * ky
            moved = max(moved, math.hypot(nx - x, ny - y))
            g.verts[i] = (nx, ny, z)
            touched += 1
    return {"moved": touched, "peak": moved, "axis": axis,
            "scale": scale, "rim_hw": rim_hw}
```

**Why calibrated rather than re-tuned.** The three defective constants (`axis`, `r_full`/`r_stop`, `sx`/`sy`) are all *properties of the source mesh*, and this checkout can no longer measure that mesh. A hardcoded replacement would be a guess that silently stops working the next time the retarget changes the column width. Reading the axis and half-width off the mesh's own top rim makes the pass **unable to silently no-op**, and `target_hw = 4.70` is the one constant taken from the reference (`slim_neck` docstring: *"4.7 cm at 160, 4.8 at 162"*).

**Backward compatibility is deliberate:** passing `axis=` explicitly keeps the old hardcoded behaviour, which is what `tests/test_neck.py` pins (§5.4). `axis=None` (the default) calibrates.

### 5.2 `cap_holes` — replace the whole function

Replace from `def cap_holes(` up to (not including) `def winding_agreement(`. Put `_ring_plane` and `_planar_diameter` immediately before it.

```python
import numpy as np


def _ring_plane(P):
    """Best-fit plane of a boundary ring: centroid, unit normal (up-facing)."""
    c = P.mean(axis=0)
    Q = P - c
    _u, _s, vt = np.linalg.svd(Q, full_matrices=False)
    n = vt[2]
    if n[2] < 0.0:
        n = -n
    return c, n


def _planar_diameter(P, n):
    """Max pairwise distance of the ring projected into its own plane.

    The bbox diagonal the gate used to measure inflates a circular ring by
    sqrt(2): a perfectly good 9.4 cm neck opening reads as 13.3 cm and a
    15.5 cm one as 21.9, so a real opening is thrown away as if it were a UV
    seam. Measuring in the ring's own plane compares like with like.
    """
    Q = P - P.mean(axis=0)
    Q = Q - np.outer(Q @ n, n)
    return float(np.sqrt(((Q[:, None, :] - Q[None, :, :]) ** 2).sum(-1).max()))


def cap_holes(g: Group, min_z: float, slot: str,
              source_material: str = "skin", allowed: set[int] | None = None,
              max_span: float = 14.0, max_roundness: float = 0.55) -> int:
    """Close boundary loops of the group that lie entirely above `min_z`.

    The 3BA body is authored to wear a *separate* Skyrim head, so it ends in an
    open collar. Without a head the player sees the inside of her own torso
    through it, and the shadow mesh is not closed either. Each loop above
    `min_z` gets a fan to its centre, with the centre weighted like the loop it
    closes so the cap deforms with the neck instead of tearing off.

    Three things had to change for the cap to actually close the neck flush:

    *The `min_z` gate is all-or-nothing on the loop's lowest vertex.* A
    diagonally cut opening straddles the threshold: at a 1.5 cm cut the ring is
    rejected until its centre clears 156.75 cm, and :func:`turn_upper_body`
    (which runs *before* this pass, pitching the upper body 1.8 degrees about
    (0, 2.5, 98)) lowers the back of the neck by ~0.3 cm. Compare the loop's
    *centre* against the threshold, not its extreme.

    *The span gate measured the bbox diagonal.* See :func:`_planar_diameter`.
    A real opening is also checked against a roundness bound: a UV-shell seam is
    a boundary loop too, but it is a ragged arc, not a circle, and its radius
    scatters. ``max_roundness`` is the coefficient of variation of the ring
    radius about its own centroid, measured in the ring's plane; the neck rims
    in the shipped packs score 0.05-0.33 and the torso-length seam loops that
    must stay open score 0.87.

    *The apex was the ring's arithmetic mean, and the stored normal was the
    normalised sum of the rim's vertex normals.* On a diagonally cut opening the
    mean sits above the low side, so every facet on that side tilts its plane
    upward -- the fan stops being a lid and becomes a shelf across the throat.
    And on a round rim the vertex normals cancel exactly, ``length = norm or
    1.0`` leaves the zero vector unnormalised, and the cap ships a (0, 0, 0)
    normal. The apex is now the ring centroid (which lies on the cut plane by
    construction) and the normal is that plane's normal; each facet is wound
    against it so the fan cannot flip across a tilted rim.

    Returns the number of triangles added, and registers them as their own
    render atom so the engine actually draws the cap.
    """
    if not g.faces:
        return 0
    p = np.asarray(g.verts, dtype=np.float64)
    z = p[:, 2]
    base_v = len(g.verts)
    base_i = len(g.faces) * 3
    added = 0
    for loop in boundary_loops(g.faces):
        idx = [i for i in loop if i < len(g.verts)]
        if len(idx) < 3:
            continue
        if allowed is not None and any(i not in allowed for i in idx):
            continue
        ring = idx[:-1] if len(idx) > 3 and idx[0] == idx[-1] else idx
        if len(ring) < 3:
            continue
        P = p[ring]
        centre, normal = _ring_plane(P)
        if float(centre[2]) < min_z:
            continue
        if _planar_diameter(P, normal) > max_span:
            continue
        radial = P - centre
        radial = radial - np.outer(radial @ normal, normal)
        rad = np.linalg.norm(radial, axis=1)
        if float(rad.mean()) <= 1e-9:
            continue
        if float(rad.std() / rad.mean()) > max_roundness:
            continue
        length = float(np.linalg.norm(normal)) or 1.0
        normal = normal / length
        weight_sum: dict[int, float] = {}
        for i in ring:
            for pal, w in g.weights[i]:
                weight_sum[pal] = weight_sum.get(pal, 0.0) + w / len(ring)
        total = sum(weight_sum.values()) or 1.0
        infl = sorted(((pal, w / total) for pal, w in weight_sum.items()),
                      key=lambda t: -t[1])[:3]
        renorm = sum(w for _, w in infl) or 1.0
        infl = [(pal, w / renorm) for pal, w in infl]
        uv = np.array([g.uvs[i] for i in ring], dtype=np.float64).mean(axis=0)
        new_index = len(g.verts)
        g.verts.append(tuple(float(x) for x in centre))
        g.normals.append(tuple(float(x) for x in normal))
        g.uvs.append((float(uv[0]), float(uv[1])))
        g.weights.append(infl)
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]
            # wind every facet against the same plane normal: the old
            # "reversed relative to the boundary walk" rule flips across a
            # tilted rim and leaves the fan inside-out on one side
            # cross(p[b] - p[a], centre - p[a]) is the facet normal of the
            # winding (a, b, apex); keep it when it agrees with the ring plane
            if float(np.cross(p[b] - p[a], centre - p[a]) @ normal) > 0.0:
                g.faces.append((a, b, new_index))
            else:
                g.faces.append((b, a, new_index))
            added += 1
    if added:
        g.slices.append((source_material, base_v, base_i, added,
                         len(g.verts) - base_v))
        g.mat_slots.append(slot)
    return added
```

Four behavioural notes:

1. **`min_z` compares the loop centroid**, which is on the cut plane by construction. The signature is unchanged, so `build_skyrim_outfit.py:413` keeps working verbatim.
2. **`max_span` compares the in-plane diameter.** `max_span=14.0` still admits the 9.4–9.9 cm reference neck and still rejects every 15 cm + seam loop.
3. **The fan normal is the ring plane's normal**, replacing the cancelling vertex-normal sum. `_ring_plane` returns a **unit** vector by construction (an SVD of a zero-mean matrix), so `‖normal‖ = 1` and no `or 1.0` fallback can ever fire. **Do not re-add one** — that is exactly the bug.
4. **The winding test is `cross(p[b]-p[a], centre-p[a]) · normal > 0`.** I had this backwards on the first pass and it produced `orientation_breaks == 4` on the existing box fixture — the fan came out inside-out. The existing test `test_cap_holes_closes_only_the_ring_above_the_cut` catches exactly that, so **run §6.2 before believing the port.**

### 5.3 `tests/test_neck.py` — 4 tests move to the explicit-constant contract

`slim_neck`'s defaults now calibrate, and these fixtures have **no faces**, so calibration cannot find a rim. They must pass their constants explicitly.

**Replace the whole contiguous region** from `def test_slim_neck_narrows_only_the_column(`
up to — but not including — `def test_turn_upper_body_aligns_neck_but_leaves_legs_upright(`
with the block below. That region contains **six** tests, not four: the two
`tuck_necklace_chain` tests sit between the `slim_neck` ones and must survive.
(An earlier draft of this plan spliced only the four `slim_neck` tests and would
have silently deleted the necklace pair — a cold-start run caught it by landing
on 40 passed instead of 42.)

```python
def test_slim_neck_narrows_only_the_column():
    """The mask band is full inside the rim and fades out over ``fade``.

    The defaults are the documented ones (axis y=7.0, full to r=8, gone by
    r=14); the calibrated path is covered in ``test_neck_three_zone.py``.
    """
    g = _group([("skin", [
        (0.0, 7.0, 150.0),      # below the band
        (0.0, 7.0, 157.0),      # exactly at z_lo: untouched
        (9.0, 7.0, 162.0),      # r=9: inside the fade, narrowed
        (20.0, 7.0, 162.0),     # trapezius, r = 20 > r_stop: untouched
    ])])

    rep = bm.slim_neck(g, axis=(0.0, 7.0), r_full=8.0, r_stop=14.0,
                       sx=0.55, sy=0.70)

    assert rep["moved"] == 1
    assert g.verts[0] == (0.0, 7.0, 150.0)
    assert g.verts[1] == (0.0, 7.0, 157.0)
    assert 0.0 < g.verts[2][0] < 9.0            # pulled toward the axis
    assert abs(g.verts[2][1] - 7.0) < 1e-9      # stays on the axis in y
    assert abs(g.verts[2][2] - 162.0) < 1e-9    # heights are never touched
    assert g.verts[3] == (20.0, 7.0, 162.0)


def test_slim_neck_ramps_in_with_height():
    """A vertex at the bottom of the ramp moves less than one at the top."""
    g = _group([("skin", [(9.0, 7.0, 158.0), (9.0, 7.0, 162.0)])])

    bm.slim_neck(g, axis=(0.0, 7.0), r_full=8.0, r_stop=14.0,
                 sx=0.55, sy=0.70)

    low = 9.0 - g.verts[0][0]
    high = 9.0 - g.verts[1][0]
    assert 0.0 < low < high


def test_slim_neck_leaves_the_garment_alone():
    """Only ``mats`` move: the collar is re-dressed separately, not scaled."""
    g = _group([("skin", [(9.0, 7.0, 162.0)]),
                ("jacket", [(9.0, 7.0, 162.0)])])

    rep = bm.slim_neck(g, axis=(0.0, 7.0), r_full=8.0, r_stop=14.0,
                       sx=0.55, sy=0.70)

    assert rep["moved"] == 1
    assert g.verts[1] == (9.0, 7.0, 162.0)


def test_tuck_necklace_chain_sinks_only_the_loop():
    """Above ``z_min`` the chain is drawn inside the neck; the pendant is not."""
    g = _group([("necklace", [(6.0, 7.0, 150.0), (6.0, 7.0, 160.0)])])

    n = bm.tuck_necklace_chain(g, scale=0.5)

    assert n == 1
    assert g.verts[0] == (6.0, 7.0, 150.0)          # chest chain: untouched
    assert abs(g.verts[1][0] - 3.0) < 1e-9          # loop half the radius
    assert abs(g.verts[1][2] - 160.0) < 1e-9


def test_tuck_necklace_chain_ignores_other_materials():
    g = _group([("skin", [(6.0, 7.0, 160.0)])])

    assert bm.tuck_necklace_chain(g) == 0
    assert g.verts[0] == (6.0, 7.0, 160.0)



def test_slim_neck_preserves_the_full_neck_height():
    """Keep the neck reaching the head; align the outfit rather than cutting it."""
    g = _group([("skin", [(0.0, 7.0, 150.0), (3.0, 7.0, 160.0),
                          (3.0, 7.0, 164.0), (3.0, 7.0, 167.0)])])

    bm.slim_neck(g, axis=(0.0, 7.0), r_full=8.0, r_stop=14.0,
                 sx=0.55, sy=0.70)

    assert max(v[2] for v in g.verts) == 167.0
    assert g.verts[0] == (0.0, 7.0, 150.0)
    assert g.verts[2][2] == 164.0
    assert g.verts[3][2] == 167.0
```

Nothing else in `tests/test_neck.py` changes.

### 5.4 `tests/test_neck_three_zone.py` — the new regression suite

A new file. It is listed in full at §9 so you can install it verbatim; every fixture is synthetic.

---

## 6. Build and verify

### 6.1 Prerequisites

```bash
python3 -m venv .venv
.venv/bin/pip install numpy pillow pyyaml pytest scipy
```

`scipy` is required by `tests/test_elbow_closeup_depth_has_no_false_holes`. The venv is excluded from snapshots — rebuild it in a fresh sandbox.

### 6.2 Gate 1 — the existing tests must still pass

The single most valuable check here is the one that caught my own winding bug. Run it first and read the failure if it appears:

```bash
.venv/bin/python -m pytest tests/test_skyrim_fit.py -k cap -q
# expect: 4 passed, 20 deselected
.venv/bin/python -m pytest tests/test_neck.py tests/test_hands_graft.py -q
# expect: 42 passed, 3 skipped
#   test_neck.py        8 passed
#   test_hands_graft.py 34 passed, 3 skipped
```

If `test_cap_holes_closes_only_the_ring_above_the_cut` reports `assert 4 == 0`, your winding condition is inverted — flip the comparison in §5.2 and re-run.

### 6.3 Gate 2 — the new fixture suite

```bash
.venv/bin/python -m pytest tests/test_neck_three_zone.py -q
# expect: 8 passed
```

**On the unpatched tree 6 of these 8 must fail** (verified — §7.2 A4). The 2 that pass either way are honest non-discriminators: `test_cap_never_ships_a_zero_normal` (the 1e-15 residue already normalises to a unit vector, so the *zero* case needs an exactly-cancelling float sum this fixture cannot hit) and `test_cap_facets_are_all_wound_the_same_way` (the old fixed fan is consistently wound on a spherical rim; it only flips on real asymmetric rims). They are kept because the fixed code must **keep** those properties, not because they catch the old one. Do not delete them to make the ratio look better, and do not weaken the other six.

### 6.4 Gate 3 — the full suite

```bash
.venv/bin/python -m pytest tests -q --ignore=tests/test_render_mesh_skeleton.py --ignore=examples
# expect: 577 passed, 85 skipped
```

Baseline **before** this change is `569 passed, 85 skipped`; `569 + 8` = **577**. If you see 569 the new file is not collected. `examples/` fails collection on a missing `websockets` — pre-existing, ignore it.

`--ignore=examples` is required: without it collection aborts before any test runs.

### 6.5 Gate 4 — reproduce §4.3

Do not take §4.3 on faith. Regenerate it with the fixture from the new test module after patching:

```python
import sys, math, numpy as np
sys.path.insert(0, "tools/pd2-las")
import build_models as bm
sys.path.insert(0, "tests")
from test_neck_three_zone import _group, retargeted_3ba, top_ring, rim_half_width

g = _group(*retargeted_3ba())
bm.slim_neck(g)
ring, P = top_ring(g)
print("rim diameter", round(2 * rim_half_width(P), 2))   # 9.40
print("capped", bm.cap_holes(g, min_z=155.0, slot="mtr_body", max_span=14.0))  # 32
```

### 6.6 Gate 5 — only if the port is reopened (Route B)

Then, and only then: rebuild, decode the shipped `outfit.model`, and check §7.1.

---

## 7. Acceptance criteria

### 7.1 Route B — in-geometry (needs the rebuilt pack)

| # | Criterion | Pass condition |
|---|---|---|
| B1 | Rim diameter | Top skin boundary loop in-plane Ø is `9.4 ± 0.5 cm` about its own centroid. |
| B2 | Rim shape | Circularity `std(r)/mean(r) < 0.02`. The old pass scores 0.116 (§4.5). |
| B3 | Shoulder preserved | Zero vertices with `z < 154` displaced by more than 0.01 cm. |
| B4 | Neck closed | No remaining loop with centroid `z > 155` and in-plane Ø below 12 cm. |
| B5 | Cap normal | `min(|n̂ · fan plane|) > 0.99` over every cap vertex. The old code scores 0.39–0.86 on 5 of 6 loops (§3.3). |
| B6 | Facets are a lid | Every cap facet has `|nz| ≥ 0.95`; the whole fan shares one sign. |
| B7 | Render | With the reference head attached offline (never shipped), front / side / three-quarter show no protruding rim above the collar, no hole, no shelf. |

### 7.2 Route A — code and tests (executable today)

| # | Criterion | Pass condition |
|---|---|---|
| A1 | Mask table | §4.1 reproduces exactly. |
| A2 | Gate margins | §4.2's verdicts reproduce; the 9.86 cm tilted circle flips reject → pass. |
| A3 | Fixture chain | §4.3 reproduces: old chain `14.05 → OPEN`, new `9.40 → CLOSED 32`. |
| A4 | New tests fail unpatched | **6 of 8** fail on the tree with `build_models.py` at `HEAD`. |
| A5 | New tests pass patched | `8 passed`. |
| A6 | Existing tests | `test_skyrim_fit.py -k cap` → 4 passed, 20 deselected; `test_neck.py test_hands_graft.py` → 42 passed, 3 skipped. |
| A7 | Full suite | `577 passed, 85 skipped`. |
| A8 | Real-mesh safety | §4.4 reproduces: zero displacement outside `z > 157` on `dist/Christie_LAS_Slim.zip`. |
| A9 | Rim shape | §4.5 reproduces: circularity 0.116 → 0.000, half-width 7.03 → 4.70. |

### 7.3 The result

After this plan the neck has **one** behaviour: a rim slimmed to the PD2 reference and still circular, a closed lid at that rim, and a cap whose normal is the rim plane's normal. Three independent mechanisms, one regression test per mechanism, so a future edit that re-breaks one cannot hide behind the other two.


### 7.4 Self-check log — this plan was executed cold, from a pristine `HEAD` tree

So you do not have to take §7.2 on faith, and so you know what "verified" means
here: I extracted `git archive HEAD` into an empty directory, applied **only**
the code blocks in §5.1, §5.2, §5.3 and §5.4, and ran every gate. No other file
was touched.

| Gate | Command | Result |
|---|---|---|
| 6.2 Gate 1a | `pytest tests/test_skyrim_fit.py -k cap` | `4 passed, 20 deselected` |
| 6.2 Gate 1b | `pytest tests/test_neck.py tests/test_hands_graft.py` | `42 passed, 3 skipped` |
| 6.3 Gate 2 | `pytest tests/test_neck_three_zone.py` | `8 passed` |
| 6.4 Gate 3 | `pytest tests --ignore=tests/test_render_mesh_skeleton.py --ignore=examples` | `577 passed, 85 skipped` |

`575 → 577` matters: the first cold run landed on **575** because §5.3's block
covered only the four `slim_neck` tests and therefore **silently deleted the two
`tuck_necklace_chain` tests** that sit between them. The block is now the whole
contiguous region and the instruction says so. If your own run lands on 575,
re-read §5.3 — you have dropped those two tests.

The resulting `build_models.py` (both replacement regions) and both test files
are **byte-identical** to the tree this plan was authored against.

**A4 restated as measured:** on pristine `HEAD` with only the new test file
installed, `6 failed, 2 passed`. The two that pass are named and justified in
§6.3 — they are non-discriminators by construction, not weak assertions.


---

## 8. Rejected alternatives and interactions

### 8.1 Rejected: `trim_neck` — squash the stub instead of narrowing it

`trim_neck` (`:1559`, `z0=159, k=0.05`) folds every skin vertex above `z0` down to `z0 + (z - z0)*0.05`. On its own it *collapses the column into a forward-offset pancake* — `tools/pd2-port/MODLOG.md:104`: *"the shelf in front and the gap behind … the cap sticks out in front of the neck"*. It moves the opening instead of shrinking it, so the rim's **radius** is unchanged and zone 1 survives untouched. Combined with `align_neck` it produced the *"hard pale-head / tan-body seam … tan skin wings"* that got the whole taper/hide approach reverted (`MODLOG.md:27-36`). Do not reintroduce either pass.

### 8.2 Rejected: using the roundness bound to tell an opening from a seam

It would be elegant, and it does not hold on this data. Across the shipped Christie packs the median roundness is 0.300 / 0.194; a perfectly good circular 8-vertex loop at `z 150.9` scores **0.026** while a genuine 4-vertex seam at `z 158.1` scores **0.202**. Any bound tight enough to reject the seams rejects real openings, and any bound loose enough to keep them admits the seams.

So `max_roundness=0.55` is included **only to reject pathological rings**, not as the seam discriminator; that remains `allowed` + `max_span`. §4.2's table shows the planar gate newly admitting one 20-vertex, 12.52 cm seam loop at `z 160.9`. That is **acceptable and expected**: a closed UV seam being capped is cosmetically invisible, and it is strictly better than today's behaviour of capping three even smaller seams. Do not "fix" it by tightening `max_span`.

### 8.3 Rejected: making `slim_neck` per-material

The Christie body's garment slices also reach above `z = 150`, so slimming each material about its own centroid looks tempting. Rejected: `slim_neck` is skin-only by contract (`mats=("skin",)`), the garment is re-dressed onto the body afterwards (`redress_from_source`, `:325`), and moving the collar independently of the body is what `follow_layer_weights` exists to prevent. Keep `mats` as it is.

### 8.4 Interaction with `turn_upper_body`

`turn_upper_body` (`:1429`) runs **between** the two fixed passes and rotates vertices *and* normals by the same smooth per-vertex angle. Two consequences:

- The calibrated `slim_neck` runs **before** the pitch, so `_top_rim` must be called at the top of the function, on un-pitched geometry. That is deliberate: it measures the retarget's own axis, which is what zone 1 is about.
- The `min_z` gate reads post-pitch geometry. Because §5.2 compares the **centroid**, the ~0.3 cm the pitch takes off the back of the neck no longer swings the verdict (§3.2 Gate A).

Do not reorder these passes. Every measurement in this document was taken in the order `slim_neck` → … → `turn_upper_body` → `cap_holes`.

### 8.5 Not fixed here: the collar still has to be re-dressed onto a narrowing neck

`redress_from_source` (`:325`) rebuilds the collar from the *source's* clearances, gated by `z_fade=(108.0, 112.0)` — above 112 source units it leaves the collar at its retargeted shape because *"the source body stops at 114.1 units and hands the neck over to the head mesh"* (`:2286` at the time of writing — grep for `114.1 units`). Narrowing the body's neck makes the collar/body gap **larger** until `lower_collar` (`:386`) and the re-dress act on it. That is out of scope here and can only be judged from a Route B render; if it shows up, it is a `redress_from_source` problem, not a `slim_neck` one.

---

## 9. Full listing — `tests/test_neck_three_zone.py`

Install verbatim.

```python
"""Three-zone neck artifact: unslimmed rim, rejected opening, mis-normalled cap.

Every fixture here is synthetic. The real geometry came from the deleted Skyrim
3BA sources (``docs/skyrim-nif/STATUS.md``), so these regressions must be
reproducible from code alone. The fixtures are built at the measurements the
pass docstrings record, so a change that breaks the geometry contract breaks
these tests.

Each test guards exactly one mechanism:

* zone 1 — ``slim_neck``'s radial mask must reach the rim, and must be centred
  on the rim, not on the PD2 axis;
* zone 2 — ``cap_holes`` must admit a real opening (centroid z gate, in-plane
  diameter) and must not mistake a UV seam for one;
* zone 3 — the cap's stored vertex normal must be the fan's own plane normal;
  the old ``sum(normals) / ||sum||`` produces a vector 90 degrees off its own
  facets on every round rim, which is what shades as a shelf.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "pd2-las"))

import build_models as bm  # noqa: E402

AXIS = (0.0, 9.5)          # documented 3BA neck axis (align_neck docstring)
SEG = 32


def _tube(half_width, zs, tilt=0.0, axis=AXIS, seg=SEG):
    """An open-topped neck tube, bottom fan-closed so only the top is open."""
    verts, rows = [], []
    for z in zs:
        row = []
        for k in range(seg):
            th = 2.0 * math.pi * k / seg
            r = half_width(z)
            verts.append((axis[0] + r * math.sin(th),
                          axis[1] + r * math.cos(th),
                          z + tilt * math.cos(th)))
            row.append(len(verts) - 1)
        rows.append(row)
    faces = []
    for zi in range(len(rows) - 1):
        a, b = rows[zi], rows[zi + 1]
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((a[k], a[k2], b[k2]))
            faces.append((a[k], b[k2], b[k]))
    cb = len(verts)
    verts.append((axis[0], axis[1], zs[0] - 0.01))
    for k in range(seg):
        faces.append((rows[0][(k + 1) % seg], rows[0][k], cb))
    return np.asarray(verts, float), faces


def _group(verts, faces, normal=(0.0, 0.0, 1.0)):
    g = bm.Group(name="body")
    g.verts = [tuple(map(float, p)) for p in verts]
    g.uvs = [(0.0, 0.0)] * len(verts)
    g.normals = [tuple(normal)] * len(verts)
    g.weights = [[(0, 1.0)]] * len(verts)
    g.faces = [tuple(map(int, t)) for t in faces]
    g.slices = [("skin", 0, 0, len(faces), len(verts))]
    g.mat_slots = ["mtr_body"]
    return g


def retargeted_3ba():
    """18.8 cm diameter at 167 (slim_neck docstring), 12 cm half-width at the 157
    stop, and the source's diagonal opening cut."""
    zs = [150, 153, 156, 157, 159, 161, 163, 165, 167]

    def hw(z):
        if z <= 157.0:
            return 12.0
        return 12.0 + (9.4 - 12.0) * (z - 157.0) / 10.0

    return _tube(hw, zs, tilt=1.5)


def top_ring(g):
    """(ring, P) of the highest boundary loop."""
    best = None
    for loop in bm.boundary_loops(g.faces):
        idx = [i for i in loop if i < len(g.verts)]
        if len(idx) < 3:
            continue
        ring = idx[:-1] if len(idx) > 3 and idx[0] == idx[-1] else idx
        P = np.asarray([g.verts[i] for i in ring], float)
        if best is None or P[:, 2].max() > best[0]:
            best = (P[:, 2].max(), ring, P)
    return best[1], best[2]


def rim_half_width(P):
    return float(np.hypot(P[:, 0] - P[:, 0].mean(), P[:, 1] - P[:, 1].mean()).mean())


def bbox_span(P):
    return float(np.linalg.norm(P.max(axis=0) - P.min(axis=0)))


def planar_diameter(P):
    c = P.mean(axis=0)
    Q = P - c
    _, _, vt = np.linalg.svd(Q, full_matrices=False)
    n = vt[2]
    Q = Q - np.outer(Q @ n, n)
    return float(np.sqrt(((Q[:, None, :] - Q[None, :, :]) ** 2).sum(-1).max()))


def plane_normal(P):
    c = P.mean(axis=0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    n = vt[2]
    return n / (np.linalg.norm(n) or 1.0)


# ------------------------------------------------------------------ zone 1
def test_slim_neck_actually_shrinks_the_rim_to_the_reference():
    """The mask used to be zero at the rim; after the fix the rim lands on 4.70."""
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    _, P = top_ring(g)
    hw = rim_half_width(P)
    assert abs(hw - 4.70) < 0.25, f"rim half-width {hw:.2f} cm, target 4.70"


def test_slim_neck_keeps_the_rim_circular():
    """Measuring about the wrong centre turns the round opening into an ellipse.

    The rim is a circle centred at y=9.5. A radial mask about y=7.0 is stronger
    on the back of the neck than on the front, so the opening comes out
    egg-shaped: 8.39 cm at the front against 7.33 at the back, circularity
    (std(r)/mean(r) about the rim's own centroid) 0.116 against 0.000.
    A shading-visible rim over the collar is exactly this asymmetry.
    """
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    _, P = top_ring(g)
    r = np.hypot(P[:, 0] - P[:, 0].mean(), P[:, 1] - P[:, 1].mean())
    circularity = float(r.std() / r.mean())
    assert circularity < 0.02, (
        f"rim circularity {circularity:.4f}: the opening is not a circle "
        f"(radius {r.min():.2f}-{r.max():.2f} cm)")


def test_bbox_diagonal_inflates_a_circular_opening():
    """The old span gate measured the bbox diagonal, which is sqrt(2) too big."""
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    _, P = top_ring(g)
    assert planar_diameter(P) < 12.0
    assert planar_diameter(P) < bbox_span(P)          # the inflation is real


def test_cap_holes_closes_the_neck_after_slimming():
    v, f = retargeted_3ba()
    g = _group(v, f)
    bm.slim_neck(g)
    ring, P = top_ring(g)
    added = bm.cap_holes(g, min_z=155.0, slot="mtr_body", max_span=14.0)
    assert added == len(ring), f"cap added {added} tris for a {len(ring)}-vertex ring"


def test_cap_holes_z_gate_uses_the_loop_centre_not_its_lowest_vertex():
    """A diagonally cut opening straddles min_z; its centre must decide."""
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=2.0)
    g = _group(v, f)
    ring, P = top_ring(g)
    centre_z = float(P[:, 2].mean())
    lowest = float(P[:, 2].min())
    assert lowest < centre_z - 1.0                # the fixture really straddles
    added = bm.cap_holes(g, min_z=centre_z - 0.1, slot="mtr_body", max_span=30.0)
    assert added == len(ring), (
        f"a ring centred at {centre_z:.2f} with a low side at {lowest:.2f} "
        f"was rejected against min_z={centre_z - 0.1:.2f}")


def test_cap_vertex_normal_is_the_fan_plane_not_cancelled_rim_normals():
    """The rim's own vertex normals cancel, so the old sum/||sum|| is 90 degrees off."""
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=0.0)
    g = _group(v, f)
    P = np.asarray(g.verts, float)
    # radial (horizontal) vertex normals: they cancel exactly around a round rim
    rad = P - np.array([AXIS[0], AXIS[1], 0.0])
    rad[:, 2] = 0.0
    ln = np.linalg.norm(rad, axis=1, keepdims=True)
    rad = np.divide(rad, np.maximum(ln, 1e-12),
                    out=np.tile([0.0, 0.0, 1.0], (len(P), 1)), where=ln > 1e-9)
    g.normals = [tuple(rad[i]) for i in range(len(g.verts))]

    # capture the ring BEFORE capping: afterwards it is no longer a boundary
    _, Pr = top_ring(g)
    expected = plane_normal(Pr)

    before = len(g.verts)
    added = bm.cap_holes(g, min_z=150.0, slot="mtr_body", max_span=30.0)
    assert added > 0
    stored = np.asarray(g.normals[before], float)

    cos = abs(float(stored @ expected))
    assert cos > 0.99, (
        f"cap normal {np.round(stored, 3)} is {math.degrees(math.acos(min(1, cos))):.1f} "
        f"degrees off the fan plane {np.round(expected, 3)}")


def test_cap_never_ships_a_zero_normal():
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=0.0)
    g = _group(v, f)
    P = np.asarray(g.verts, float)
    rad = P - np.array([AXIS[0], AXIS[1], 0.0])
    rad[:, 2] = 0.0
    ln = np.linalg.norm(rad, axis=1, keepdims=True)
    rad = np.divide(rad, np.maximum(ln, 1e-12),
                    out=np.tile([0.0, 0.0, 1.0], (len(P), 1)), where=ln > 1e-9)
    g.normals = [tuple(rad[i]) for i in range(len(g.verts))]
    before = len(g.verts)
    bm.cap_holes(g, min_z=150.0, slot="mtr_body", max_span=30.0)
    for i in range(before, len(g.normals)):
        assert np.linalg.norm(g.normals[i]) > 0.5, f"cap vertex {i} normal is degenerate"


def test_cap_facets_are_all_wound_the_same_way():
    v, f = _tube(lambda z: 6.5, [150, 156, 160], tilt=2.0)
    g = _group(v, f)
    before = len(g.faces)
    bm.cap_holes(g, min_z=150.0, slot="mtr_body", max_span=30.0)
    V = np.asarray(g.verts, float)
    signs = []
    for t in g.faces[before:]:
        n = np.cross(V[t[1]] - V[t[0]], V[t[2]] - V[t[0]])
        L = np.linalg.norm(n)
        if L > 0:
            signs.append(n[2] / L)
    signs = np.asarray(signs)
    assert (signs > 0).all() or (signs < 0).all(), f"mixed winding {signs}"
    assert np.abs(signs).min() > 0.95, "a facet is nearly edge-on: the fan is a skirt"


```

---

## 10. Open question for the user

**Route A or Route B?** Route A lands the fix and the regression suite and is complete on its own. Route B additionally rebuilds and verifies in-geometry, which requires re-supplying the five Skyrim source archives that `docs/skyrim-nif/STATUS.md` says were deliberately deleted after the cancellation. Default to Route A and stop there unless told otherwise.
