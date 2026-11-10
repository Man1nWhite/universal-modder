# Christie LAS — elbow check across every committed render (2026-11-10)

Scope: all 100 files in `docs/pd2-las/renders/` (base pack, slim pack, FPS
units, DOA5 source reference), plus the 15 in-game screenshots. Question asked:
**are there mistakes around the elbows?**

Everything below was re-derived from the shipped bytes in `dist/`, not from the
numbers in `CHRISTIE.md`. Two scripts were used, both already in the tree:

```bash
bash tools/pd2-las/recover_env.sh          # venv + /tmp/2bsrc (was wiped)
.venv/bin/python tools/pd2-las/render_mesh_skeleton.py \
    --zip dist/Christie_LAS.zip --pack Christie_LAS --item christie \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b" \
    --out build/elbow-audit/repro --pose --hang          # + --fps in a second run
.venv/bin/python tools/pd2-las/diagnose_mesh.py \
    --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b"
.venv/bin/python -m pytest tests/test_christie_las.py -q \
    -k "elbow or forearm or cuff or crease"               # 21 passed
```

Deformation numbers come from re-skinning the shipped `g_body` with the same
LBS the renderer uses (`pose_for` / `skin_verts`), sampling 5 elbow angles from
the bind 72° through the in-game idle 12° and past it to 0°.

## Verdict in one line

**No spike, tear, pinch, braid or collapsed sleeve at any elbow in any render,
at any angle.** One real geometry defect remains, and it is exactly at the
elbow: a small open rim in the inner sleeve that the seam-stitch pass was
supposed to close, still present on the slim pack and measurable with the
project's own probe. Two renders are also stale and one artifact is a
depth-band clip.

## What measures clean

| probe (both packs unless noted) | result |
| --- | --- |
| elbow edge compression at the **in-game idle 12°** | min edge ratio **1.000**, 0 edges shortened — the pack is authored in this pose, so it moves by exactly nothing |
| straightening bind 72° → 47° / 22° | max edge growth 0.78 / 0.25 cm, **0 edges over 2 cm** |
| surface area preserved | ratio 0.9993–1.0000 |
| arm radius across the elbow at 12° | p10/p50/p90 = 4.35/4.58/5.00 cm at the joint → 4.72/5.42/6.92 cm 6–9 cm distal — monotone, no step, no pinch |
| elbow thickness (p90, 2 cm band) | within the 7.4 cm test limit (`test_elbow_is_not_puffier_than_the_reference`) |
| boundary edges near the elbow | 6 (base) / 7 (slim) per side, 0 within 2 cm of the pivot — nothing has opened up *at* the joint |
| flipped faces at the in-game idle | **0** in both packs |

Also checked, and negative: the pointed flaps visible at the top of
`*_forearm_{front,side}.png` and in the `--hang` close-ups are the blazer's
armhole/panel border caught inside the 8 cm radius selection (the same shapes
appear in `christie_source_*`), not folds of the elbow surface.

## Defect 1 — the slim inner-elbow sleeve is still open (the only real one)

`diagnose_mesh.py --templates`, unchanged, on the shipped packs:

| | base left | base right | **slim left** | **slim right** |
| --- | --- | --- | --- | --- |
| sleeve slit (cm²) | 0.00 | 0.00 | **6.70** | **4.95** |

`CHRISTIE.md` records `21.53 → 0.00` / `35.14, 4.95 → 0.00, 0.00` for the
stitch pass and those two zeros are what the doc still claims for the shipped
hash `ee85fc15…`. They do not reproduce: the four leaky slices sit at
**z = 125.3–126.6 cm**, i.e. on the inner elbow (the `ForeArm` pivot is at
z 127.3), one ray of 60 escaping per slice. The base pack also has the open rims —
6 boundary edges, the same 3–4-vertex loops — but no radial ray escapes through
them, so its 0.00 does not mean the surface is closed there.

The rims themselves are present in **both** packs, and they are not a
zero-width slit — the nearest other vertex is 0.6–2.2 cm away:

```
base Left : 6 boundary edges, 8 rim verts, gap min 0.00 / med 0.59 / max 1.45 cm
base Right: 6 boundary edges, 8 rim verts, gap min 0.00 / med 0.73 / max 1.67 cm
slim Left : 7 boundary edges, 9 rim verts, gap min 0.00 / med 1.18 / max 2.17 cm
slim Right: 7 boundary edges, 9 rim verts, gap min 0.00 / med 1.04 / max 1.67 cm
```

All adjacent faces are `mtr_c02_01` (the blazer). This is the "4-vertex hole at
the back of each elbow" the diagnosis already documented; the stitch pass
reports 4 holes plugged per pack, but a 3–4-vertex loop per elbow survives.
It is small (a couple of cm²) and does not read as a hole in any committed
render, but it is a genuine unclosed surface at the joint, and it is where the
screenshots' "angular elbow fold" is most likely to be seen from the right
angle — it is the one thing in this sweep worth a fix.

## Defect 2 — inverted faces at full flexion (known, budgeted)

Posing to the 72° menu/bind angle inverts **13 faces on the base pack**
(6 on slim), every one of them `mtr_c02_01`, 9–13 cm from the `ForeArm` pivot on
the inner sleeve, rest positions z ≈ 124–128 cm (both sides; the base pair is
symmetric, 6 left + 7 right). At 47° this drops to 2 (base) / 0 (slim) and at
the in-game idle it is 0.

The committed renders do not show it — `render_mesh_skeleton.render` shades with
`abs(normal)` and no culling, and a face drawn either way looks the same. With
backface culling on (what D3D9 does) they disappear rather than show. So this is
not a visible defect, but it is the same inner-elbow patch the seam stitch
documented as a side effect ("opposed pairs at the old 72° menu pose base 5 → 7,
slim 1 → 4"), and it is worth keeping in the budget rather than declaring closed.

## Defect 3 — the two `hang_elbow` pairs do not match each other or the code

Re-running the documented `--hang` command does not reproduce four committed
images:

| file | diff vs fresh render | note |
| --- | --- | --- |
| `christie_hang_elbow_front.png` | 246 px (0.02 %) | small; subset tie-break |
| `christie_skel_pose_front.png` | 93 px | " |
| `christie_skel_pose_wrist_front.png` | 1 282 px | " |
| `christie_hang_front.png` | 64 px | " |
| `christie_slim_hang_elbow_front.png` | **107 581 px (10.8 %)** | different geometry selected |
| `christie_slim_hang_elbow_side.png` | **119 516 px (12.0 %)** | " |
| `christie_slim_skel_pose_wrist_front/side` | 11 926 / 5 148 px | " |

`christie_forearm_*`, `christie_skel_*`, `*_skel_{front,side,iso,top,bottom,cuff,
wrist_*}`, `fps_christie*` and the `outer_sheet` / `rest_*` files are byte-identical
to a fresh run, so the rest of the set is reproducible.

The slim pair is not a rounding difference — it is a different set of triangles.
Silhouette IoU against a fresh render is 0.834, and the fresh image contains the
shoulder/armhole panel flap that the committed base-pack image shows but the
committed slim image has been cleanly cut away. `_largest_blobs(sub, count=3)`
is what the renderer uses today; the slim files match `count=2` more closely
(1 185 / 3 499 px) but not exactly, so they predate a further change.

Consequence for reading the set: **`christie_hang_elbow_*` and
`christie_slim_hang_elbow_*` cannot be compared to each other as they stand.**
Both need regenerating, or the base ones will keep showing a flap the slim ones
hide. (Neither flap is elbow geometry.)

## Artifact — the black wedge at the bottom of the AFTER panels

`*_elbow_bend_before_after.png` / `*_elbow_idle_before_after.png` show a black
wedge at the bottom edge of several AFTER panels. It is **not** a hole in the
mesh: the sheet renders with a ±9 cm depth band around the pivot, and the
bottom of the 12.7 cm frame runs past that band where the cuff swings toward the
camera. Re-rendering the identical pose/frame with the band widened to ±30 cm
(or removed) fills the wedge with sleeve, at the same pixel coordinates.

## Per-file sweep

| group | files | elbow verdict |
| --- | --- | --- |
| `christie{,_slim}_{0,22,45,60,72}_{front,side}` | 20 | clean at all five angles; only at 72° does the outer elbow show a crease, and it stays a crease, not a braid |
| `*_elbow_{bend,idle}_before_after` | 4 | clean; the bottom-edge wedge is the depth-band artifact above |
| `*_hang_elbow_{front,side}`, `*_hang_{front,side}` | 8 | elbow clean in all; slim pair stale (defect 3) |
| `*_forearm_{front,side}` (base, slim, fps, source) | 8 | clean; flaps at the crop edge are armhole geometry, present in the source render too |
| `*_skel_pose_{front,side}`, `*_skel_pose_wrist_*` | 8 | clean; the only inverted faces are at 72°, not in these poses |
| `*_skel_{front,side,iso,top,bottom,cuff,wrist_*}` | 24 | clean; cuff mouth round and open, hand stub inside it, no elbow contact |
| `*_cuff_before_after`, `*_fit_before_after` | 4 | out of elbow scope, nothing at the joint |
| `*_outer_sheet`, `*_idle_rest_outer_sheet`, `*_rest_*` | 8 | clean; outer blazer isolated, elbow tube unbroken at every angle |
| `fps_christie{,_slim}_*` | 20 | clean and byte-reproducible |
| `christie_source_*` | 5 | reference only; its own elbow is a smooth tube with no crease |
| `neck_*` | 3 | out of elbow scope |
| `docs/pd2-las/screenshots/*.png` | 15 | the arm reads as a smooth sleeve in the profiles; no hole or spike at the elbow in any of them |

## Recommended follow-up

1. Close the residual 3–4-vertex inner-elbow loop on both packs (extend the
   small-loop fan in `stitch_sleeve_seams` to loops that are still open after
   welding, or refuse to ship while `sleeve_slit_area()` reads non-zero inside
   z 118–134), then regenerate the slit numbers in `CHRISTIE.md` — the current
   0.00/0.00 for slim does not reproduce.
2. Re-render the four stale `--hang` images with today's renderer so the base
   and slim pairs are comparable.
3. Optionally widen the before/after sheet's depth band (or clamp the frame to
   it) so the bottom-edge clip stops looking like a hole.
