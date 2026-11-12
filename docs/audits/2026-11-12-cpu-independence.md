# The tracked packs and the CPU that builds them

Date: 2026-11-12. This page is written in the order the work was done. Its second section was committed
(`20aafeb`) before the check it describes had run anywhere.

**What changed.** Until now 12 of the 14 tracked packs came out with other bytes on a CPU without AVX-512.
The causes were found, sorted into three kinds and fixed, each at its own level. Twelve packs were built again
and re-shipped. CI now builds every pack on its runner and compares each zip with its tracked sha256, with no
tolerance. The comparison that allowed a model to differ (`fresh_check.py`, the first D26) is deleted.

## Where this starts

One commit, `5477da7`, was built by two GitHub runners on 2026-11-12. On an AMD EPYC 9V74 (AVX-512) both
Miranda packs came out with all 20 members the same bytes as the tracked ones. On an AMD EPYC 7763 (AVX2, no
AVX-512) the third-person model of each differed in 136 bytes. CI was green both times, because the
comparison (`fresh_check.py`) allowed a model to differ in that way. The other twelve packs have never been
built on a machine that is not an Arena sandbox.

## What the strict check is expected to report (written before its first run)

`tools/pd2-las/fresh.py check` builds all 14 packs in a copy of the checkout and compares each of the 16
tracked zips with its tracked `.sha256` using `sha256sum -c`, with no tolerance. Nothing has been fixed yet.
The expectation comes from the sandbox runs of 2026-11-11, in which numpy and OpenBLAS were held to the code
paths of other CPUs.

- **On a runner with AVX-512** (the EPYC 9V74 kind): all 16 zips are the tracked bytes.
- **On a runner without AVX-512** (the EPYC 7763 kind): 14 of the 16 zips differ. They are `Miranda_LAS` and
  `Miranda_Busty_LAS` (both copies of each), `Christie_LAS`, `Christie_LAS_Slim`, the four
  `Miranda_L4D2_over_*` and the four `Miranda_Romance_over_*`. `lawson_las` and `Geralt_over_Rust` are the
  tracked bytes. A Miranda model differs in 136 bytes, a head atlas in 8 or 9.
- **What would make this wrong:** a difference between the sandbox and a runner that is not the CPU's
  instruction set. A runner has four threads where the sandbox has two, and its own C library; the Christie
  and head builders have met neither.

## What it reported, before anything was fixed

Commit `20aafeb`, four runs of the same job. The step did not block yet.

| Run | Runner's CPU | Threads | Zips that were the tracked bytes |
| --- | --- | --- | --- |
| 43219506181 | AMD EPYC 7763: AVX2, no AVX-512 | 4 | 2 of 16: `lawson_las`, `Geralt_over_Rust` |
| 43219499968 | Intel Xeon Platinum 8573C: AVX-512 | 4 | 16 of 16 |
| 43219496002 | Intel Xeon Platinum 8573C: AVX-512 | 4 | 16 of 16 |
| 43219495986 | AMD EPYC 9V74: AVX-512 | 4 | 16 of 16 |

Both halves of the expectation held. On the EPYC 7763 the 14 zips that differ are the 14 that were named, and
what differs inside them is, member by member, what the sandbox gave with numpy and OpenBLAS held to the AVX2
code path (`christie.model`: V directions at 194 of 10,373 vertices, 105 of them reversed; its first-person
model: 128, of which 73). The third line of the expectation, the one that could have gone wrong, did not: a
runner with four threads and another C library built the same 16 zips as the sandbox.

## Where two builds part

**Method.** `tools/pd2-las/fresh.py matrix` builds everything again under other numeric code paths: numpy and
OpenBLAS held to what they run on a CPU with AVX2 or with SSE4.2 only, one thread, four threads (the sandbox
has two cores, so OpenBLAS ran two and that build is the sandbox's own), and glibc's CPU-specific math switched
off. Each build runs in its own copy of the tree. `tools/pd2-las/trace_run.py` runs a builder with a checkpoint
trace: a checksum of what every function of the repository was given and of what it returned, in two halves,
everything and everything but float64. The first line of two traces that differs in the second half names the
function where a difference became able to reach a file. Two traces of one configuration are identical, with
two exceptions that were taken out by tracing one configuration twice and fixing Python's hash seed: the
Christie builder hands a render a scratch path, and the lawson builder walks a set of strings.

What the libraries do, on a million values per function, against the sandbox's own code path:

| Held to | numpy functions with other float64 results | With other float32 results |
| --- | --- | --- |
| AVX2 (numpy without AVX-512, OpenBLAS's Haswell kernels) | exp, log, power, arctan2, dot, lstsq, svd | power, arctan2, dot, matmul, svd |
| SSE4.2 (numpy's baseline, OpenBLAS's Nehalem kernels) | the same, and matmul | the same, and sin, cos, exp, log, lstsq |
| One thread | dot | none |
| glibc's plain math, on top of SSE4.2 | sin, cos, exp, log, power, arctan2 | cos |

sqrt, hypot and numpy's own sums gave the same bits on every path. Of 400,000 pairs of sin and cos from
Python's `math`, glibc 2.36 gives 589 another last bit with its CPU-specific routines than with its plain ones.

**Every byte that differed, by cause.** Kinds: **a**, a decision on a number that is zero in exact arithmetic;
**b**, a value rounded after a function whose last digit is not specified; **c**, a sum whose order depends on
the CPU. "AVX2" and "SSE4.2" are the code paths of the table above, against the tracked build.

| # | Where | Kind | Packs | What differed |
| --- | --- | --- | --- | --- |
| 1 | `build_models.author_group_sections`: the sign of a V direction where the UV map gives none. It was the sign of `dot(cross(n, u), v)` with a fallback `v` in the plane of `n` and `u` | a | the four LAS packs | AVX2: in each Miranda model 27 vertices of the hair and their copies in the shadow caster, 16 of them reversed, the rest in a component that is zero up to rounding (136 bytes); `christie.model` 194 vertices per geometry, 105 reversed; its first-person model 128, 73 reversed; `christie_slim.model` 62, 36 reversed; its first-person model 2. The eight models have 1,484 such vertices |
| 2 | `build_christie_las._fill_ring`: which of two fans fills a ring, when both are the same triangles and their scores are equal in exact arithmetic | a | the two Christie packs | two triangles of 17,289 (of 6,921 in first person) in another order and started from another corner, in both index lists of each model. The same triangles |
| 3 | `build_joy_head_mods.build_crisp_miranda_eye_texture`: float32 sin, cos, arctan2, exp and powers, cut off to bytes | b | the eight head packs | 18 texels of level 0 of the head atlas and one of level 1, by up to 9 of 255: 8 bytes of 5,592,560 |
| 4 | `build_joy_head_mods.shade_nostril_cavities`: float32 hypot, exp and a power, cut off to bytes | b | the four Romance head packs | one texel of level 0: one byte |
| 5 | The Christie geometry. Float64 results of OpenBLAS and of numpy's own routines differ in their last bits from `weld_elbows` on (the first line of the trace that differs); where such a value is zero up to rounding, the float32 that is stored differs | c | the two Christie packs | one normal component (-6.85e-08, at a vertex on the mirror plane) in both geometries of `christie.model`, and the U direction made from it. After the fix, with the code path left free: the same, and two positions in the slim pack |
| 6 | `segment_fit`'s figures, written to `BUILD_INFO.json` with all their digits | c | the two Christie packs | about 140 numbers in their last digits |
| 7 | `diesel_model.compute_uv_directions`, given float64 values | c | the two Miranda packs, SSE4.2 only | one U direction in its last bit, and five more V directions of kind 1: 174 bytes where AVX2 has 136 |
| 8 | `BUILD_INFO.json`: the sha256 it records for a member | follows | the four LAS packs | 60 to 64 bytes |
| - | Unexplained | | | none: every differing byte of a model lies in a channel or an index list named above, and every differing texel in a quarter of an atlas named above |

In bytes, against the SSE4.2 code path: `miranda.model` and `miranda_busty.model` 174 each; `christie.model`
943, `fps_christie.model` 602; `christie_slim.model` 348, its first-person model 18; a head atlas 8, in the
Romance packs 9. `lawson_las` and `Geralt_over_Rust`: none, on any path.

Two more places differ between code paths without having reached a byte. `build_las.draw_eye`: 4 of its 786,432
values came out one step different without AVX-512, and the encoder happened to give the same blocks. And
`build_las.face_levels`: where a whole 2x2 block of a flat dark area is repainted, the mean of the level below
is 8.5 give or take 1e-15, by whatever a power leaves over when it cancels; rounded to the even number, as
numpy rounds, that is 8 on one machine and 9 on another. The matrix did not find this one. The margin check
did, the first time the build ran with it.

## The rule for a vertex without UV area

A vertex all of whose triangles have no area in the UV map gets no V direction from the map. Two sources say
what to do with it.

`mikktspace.c` (mmikk/MikkTSpace at `1cb38f46977c`), the reference tangent-space code: a triangle without UV
area is flagged `GROUP_WITH_ANY`, and "first to group with a group-with-anything triangle determines it's
orientation" (lines 1156 to 1166): it takes the orientation of the neighbouring group that claims it. One that
no group claims keeps the flag it was given, not `ORIENT_PRESERVING` (line 988: only a positive UV area sets
it), which in this file's convention, with V along the image's rows, is the unmirrored handedness.

The models the game is known to accept, counted here (handedness: the sign of `dot(cross(n, u), v)`, where it
is above a half in size):

| Models | Vertices with UV area: +, -, no handed frame | Without UV area: +, -, no handed frame | Of those with a sign: agree with their neighbours, disagree, have none to compare |
| --- | --- | --- | --- |
| 2B's, 3 | 1,230, 9,463, 83,987 | 0, 8, 532 (U and V both zero) | 0, 0, 8 |
| Legendary Armour Skins' own, 34 (4 geometries unreadable) | 74,065, 323,595, 41,674 | 4, 631, 2,315 (363 of them with U equal to V) | 8, 0, 627 |
| This repository's 8, before | 40,694, 58,030, 0 | 1,142, 342, 0 | 82, 222, 1,180 |

So the game is fed anything at such a vertex, often no frame at all. Where there is a frame it is the
unmirrored one 631 times in 635, and it never contradicts its neighbours. The rule that was followed is
`mikktspace.c`'s, and the game's models do not speak against it: such a vertex takes the handedness of the
corners it shares a triangle with, by majority, and passes it on; with no neighbour to take it from, or a tie,
it is unmirrored (`tangents.py`). The one departure from `mikktspace.c`: there the first group to arrive
decides, which depends on the order of the triangles; here the majority decides, which does not.

In this repository's models the sign had been rounding's choice: 222 such vertices contradicted their
neighbours. The rule decides 1,492 vertices in the geometries this build authors: the 1,452 without UV area
and 40 more that get no V direction either (their triangles' contributions cancel, or no triangle uses them).
1,147 of them came out reversed against the previous build.

## What was changed

1. **A rule where the decision is taken** (kind a). `tangents.py` as above. `_fill_ring`: a later fan replaces
   the best one so far only if it is better by more than 1e-9, which rounding cannot produce.
2. **Derived values from what is stored.** Tangent frames are computed from the float32 positions, normals
   and UVs that are written to the file, with + - * / and sqrt, and sums by `math.fsum`, which is exact in any
   order. IEEE 754 fixes each of these to the last bit. A test computes every U and V direction of the eight
   tracked models again from the file and compares them bit for bit (rows 1 and 7; it leaves out one
   eight-vertex box that every first-person model copies from `fps_2b.model` unchanged).
3. **A margin for what the build draws and repaints** (kind b): both eyes, the face repaint, the head packs'
   nostril and lash pass, and the mip levels of the face and the eye. They are evaluated in float64; radii and
   whatever decides where to paint are made of * + and sqrt, or compared with `determinism.above`; the result
   is cut off by `determinism.floor8` or, for a mean, rounded by `determinism.rounded`. All three stop the
   build when a value lies within the margin of a boundary.
4. **A declared code path for the rest** (kind c): `determinism.enter`, called first in every builder's
   `main()`. The fit figures of row 6 are written to six decimals.

**The margin is 1e-9**, on the scale a value is rounded on. Two float64 math libraries that keep to their
documented accuracy differ by a few units in the sixteenth digit per function. Measured on the eye's 1,048,576
values before rounding, between the sandbox's own code path and the two others: 14,842 values differ at all,
the largest by 1.5e-12 of a step. The margin is 700 times that. The eye value nearest to a boundary is 1.9e-6
away, 1,900 margins. By chance alone the check stops a build for two values in a thousand million.

**Where the boundaries are.** The build always cut a drawn value off to the whole number below, and still
does: rounding to the nearest instead was tried and dropped, because it changed the art (one known miss of the
mip audit went away, and the audit is not allowed to move). But whole numbers are where values pile up: a
flat area, a clip, a paint weight of zero. So `floor8` puts its boundary 1/1024 of a step below each whole
number: 199.99999999999997 and 200.0 both come out as 200. Halves are where means pile up, as in the case of
8.5 above, so `rounded` puts its boundary 2^-25 below the half: a half goes up, on every machine. Neither
shift is visible; both are what makes a check possible at all.

## What the declared code path carries

The code path is OpenBLAS's Nehalem kernels on one thread, numpy's x86-64-v2 loops, and glibc asked for its
routines without FMA: what every CPU that can import the pinned numpy has. A builder that was started without
it starts itself again with it, then asks numpy and OpenBLAS what they loaded and refuses to build if it is
something else. glibc cannot be asked.

After the fix, the matrix again, against the build on the declared code path (which is the tracked bytes):

| Code path left to | Zips that differ | What differs |
| --- | --- | --- |
| SSE4.2 kernels, two threads, glibc as it comes | none | |
| The same with glibc's plain math | none | |
| The sandbox as it is: AVX-512, two threads | `Christie_LAS`, `Christie_LAS_Slim` | one normal in each; in the slim pack two positions as well; the hashes `BUILD_INFO.json` records for those models |
| The same on one thread | the same two | the same |
| AVX2 | the same two | two normals and the V direction made from one of them; in the slim pack one normal and two positions |

That is all the code path carries: row 5 of the table. The Miranda packs, the eight head packs, every texture,
every tangent frame and the order of every triangle are the same bytes on every path that was tried, without
it. Thread count and glibc's routines change no byte.

## Proof

Commit `e5eb882`, the fix, four runs. Every run reported the code path it loaded: numpy 2.4.6 dispatching to
X86_V2, OpenBLAS's Nehalem kernels on one thread, glibc 2.43.

| Run | Runner's CPU | Threads | Zips that were the tracked bytes |
| --- | --- | --- | --- |
| 43230655861 | Intel Xeon 6973P-C: AVX-512 | 4 | 16 of 16 |
| 43230649766 | AMD EPYC 7763: AVX2, no AVX-512 | 4 | 16 of 16 |
| 43230645277 | AMD EPYC 9V45: AVX-512 | 4 | 16 of 16 |
| 43230645261 | AMD EPYC 7763: AVX2, no AVX-512 | 4 | 16 of 16 |

The same job, on the same kind of runner that had 2 of 16 before. The comparison is `sha256sum -c`. The runs
on the commit that made the step blocking, and the one run on ARM, follow in "Afterwards".

What else stands behind it: `tests/test_determinism.py`, one test at least for each place that was fixed, each
of which fails when the old behaviour is put back; the tangent frames of the tracked models recomputed from the
file on whatever CPU runs the suite; the build's own checks, which run on every machine at every build.

## The packs

Twelve packs changed. Full hashes: `docs/pd2-las/HANDOFF.md`.

| Pack | Before | Now | Members that changed, with the bytes that differ |
| --- | --- | --- | --- |
| `Miranda_LAS.zip` | 5,919,788 B `f0e9c698…` | 5,919,822 B `b7fe6b08…` | `miranda.model` 128,952, `fps_miranda.model` 22,772, `miranda_eyes.texture` 270, `miranda_face_df.texture` 16, `BUILD_INFO.json` |
| `Miranda_Busty_LAS.zip` | 6,321,190 B `5c802b25…` | 6,321,140 B `d8856d8d…` | `miranda_busty.model` 181,662, `fps_miranda_busty.model` 22,772, the same two textures, `BUILD_INFO.json` |
| `Christie_LAS.zip` | 4,983,848 B `9e7c2d82…` | 4,982,791 B `1b486c42…` | `christie.model` 122,909, `fps_christie.model` 53,700, `BUILD_INFO.json` |
| `Christie_LAS_Slim.zip` | 4,393,967 B `7a4d010c…` | 4,392,978 B `79529a56…` | `christie_slim.model` 85,852, `fps_christie_slim.model` 15,712, `BUILD_INFO.json` |
| `Miranda_L4D2_over_Joy.zip` | 10,679,783 B `79032405…` | 10,679,847 B `2bd2d3af…` | head atlas 2,507, menu icon 6 |
| `Miranda_L4D2_over_Clover.zip` | 7,727,355 B `2ca4d494…` | 7,727,419 B `f36ade1b…` | the same |
| `Miranda_L4D2_over_Bonnie.zip` | 8,239,404 B `00398955…` | 8,239,468 B `12b1351d…` | the same |
| `Miranda_L4D2_over_Sydney.zip` | 7,226,214 B `74b6794f…` | 7,226,278 B `8df70903…` | the same |
| `Miranda_Romance_over_Joy.zip` | 10,238,712 B `c53953ea…` | 10,238,861 B `312b8cc3…` | head atlas 3,809, menu icon 30 |
| `Miranda_Romance_over_Clover.zip` | 7,297,599 B `28a4d849…` | 7,297,748 B `cf3c80f3…` | the same |
| `Miranda_Romance_over_Bonnie.zip` | 7,791,810 B `d51d9664…` | 7,791,959 B `756fdd6e…` | the same |
| `Miranda_Romance_over_Sydney.zip` | 6,805,595 B `b0df4909…` | 6,805,744 B `8eb937a3…` | the same |

`lawson_las.zip` and `Geralt_over_Rust.zip` are byte for byte what they were. A model changes in so many bytes
because every U and V direction is now made from float32 values: the last digits of nearly all of them moved.
In the textures: Decoded, 233 of the 262,144 texels of the eye's level 0 differ and 45 of the face's; 7,081 of the 4,194,304 texels of an L4D2 head atlas and 10,523 of a Romance one. What was drawn moved by one step at most; a block that holds such a texel is encoded again, so a decoded texel can move by more (11 steps at most in the eye). The mip audit passes with the same nine known misses, and its figures for the eye
are the previous ones to two decimals, except one (the p99 of level 1: 3.38, was 3.33).

## The guarantee, and where it ends

On an x86-64 Linux machine with the pinned environment (`make -sC tools/pd2-las env`), each of the 16 tracked
zips rebuilds to its tracked sha256, whatever the CPU. `make -sC tools/pd2-las fresh` checks it; CI runs it on
every push.

- **Holds on any code path:** the tangent frames and their handedness, the order of the triangles, everything
  the build draws or repaints, the figures in `BUILD_INFO.json`.
- **Rests on the declared code path:** the float32 geometry of the two Christie packs where float64 linear
  algebra ends in it (row 5).
- **Not x86-64 Linux:** no declared code path exists; the builders refuse to build. On ARM, left free, 14 of
  the 16 zips came out as tracked ("Afterwards"). Windows and macOS were not tried.
- **glibc** is asked for its plain math and cannot be checked. No byte moved between its routines here, and
  the runners' glibc 2.43 built what the sandbox's 2.36 built.
- **Not pinned:** scipy (the Christie builder uses `scipy.ndimage`), py7zr, the system's zlib. The runners and
  the sandbox agree today.
- **`lawson_las`** is built by the other pipeline (D3), which does not enter the code path. It has not moved
  on any path or on any runner.
- **The busty pack's menu icon and the head packs' portraits** are renders: float32 arithmetic through a
  rasteriser, not rounded with a margin. They rest on the code path. Changing them would have changed
  `Geralt_over_Rust`, whose portrait comes out of the same function.

## Not done, not known

- Nothing was looked at in the game. Whether a frame's handedness shows at a vertex without UV area is not
  known; the previous builds had it by chance, and the game's own models often have no frame there.
- The rule for a tie in `_fill_ring` was tested with stand-ins for its geometry, not on a second real ring.
- Which test fails on ARM (see "Afterwards").
- The Christie values of row 5 were not made independent of the code path. They are a least-squares fit and
  its consequences; making them so means the matrix code, which was out of scope.

## Afterwards

Commit `a005c05`, in which the step blocks:

| Run | Runner's CPU | Threads | Zips that were the tracked bytes |
| --- | --- | --- | --- |
| 43234112601 | Intel Xeon Platinum 8573C: AVX-512 | 4 | 16 of 16 |
| 43234105598 | AMD EPYC 9V74: AVX-512 | 4 | 16 of 16 |
| 43234099277 | AMD EPYC 9V74: AVX-512 | 4 | 16 of 16 |

None of these three landed on a runner without AVX-512. The two EPYC 7763 runs of `e5eb882` above built the
same zips with the same check: no pack changed between the two commits. Later runs are in pull request #30.

**One run on ARM** (43234100505: `ubuntu-24.04-arm`, a Neoverse V2 with glibc 2.39; not a gate). There is no
declared code path on ARM, so the builders were left free: numpy on NEON, OpenBLAS's neoversev2 kernels on
four threads. 14 of the 16 zips are the tracked bytes: both Miranda packs in both copies, all eight head
packs, `lawson_las`, `Geralt_over_Rust`. The two Christie packs differ, and in kind c only: two positions and
one or two normals in each third-person model, by 3e-14 to 2e-12, which are values that are zero up to
rounding; the U and V directions made from those values; the hashes `BUILD_INFO.json` records. That is row 5
again and nothing else. On another architecture, with other kernels, another thread count and another C
library, every rule held, and only what the declared code path carries moved.

The test step of that job failed as well. Its log cannot be read from the sandbox, and it was not looked
into: the suite has never been asked to pass on ARM.

## How to repeat it

`make -sC tools/pd2-las fresh` is the check. `python tools/pd2-las/fresh.py matrix` is the variation matrix
(seven builds of everything, two at a time; about seven minutes); with `--trace all` it also compares the
traces. `python tools/pd2-las/determinism.py` prints what a machine loads on the declared code path.
`PD2_CODEPATH=free` in front of a builder leaves the code path to the machine; such a build is not the tracked
bytes and says so.
