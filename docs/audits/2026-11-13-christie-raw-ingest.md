# Christie redo — raw-input ingest and re-measurement (2026-11-13)

Scope: `dist/Christie_LAS.zip` and `dist/Christie_LAS_Slim.zip` only. Nothing
was rebuilt. Every number below was re-derived on 2026-11-13 from the files the
repository tracks or from the raw sources, in tools that did not write them,
because the previous attempt's account of the same defects is a claim with named
evidence, not a measurement that transfers.

Tools used, and why they are independent:

| tool | version | used for |
| --- | --- | --- |
| Blender (headless, `bpy` wheel) | 4.5.16 LTS | topology, boundary loops, Cycles renders of the **packed** bytes |
| SourceIO | 5.5.4 | a second parser of `christie_c2.mdl` / `.vtx` / `.vvd` |
| sourcepp | 2026.11.1 | a third opinion tried on the VTFs; it rejects the archive's VTF 7.4 headers as `ImageFormat.EMPTY` (the header size is 96 where 7.4 is 104), so it is **not** used for a number here |
| the repo's readers | — | `diagnose_mesh.py`, `source_model.py`, `dds_encode.py` |

The Blender wheel has no GL driver in this sandbox; it runs with the Cycles CPU
device, and the linkage stubs that made that possible are outside the repo.

---

## 1. Is the repo's parser's own picture of the source right?

Re-derived three ways. The MDL declares **98 bones, 20 materials, 4 bodyparts,
7 models, 1 "ragdoll" sequence**; every reader agrees.

| | repo `load_christie` | SourceIO 5.5.4 | agreement |
| --- | --- | --- | --- |
| bones | 98 | 98 | yes |
| materials | 20 | 20 | yes |
| bodyparts / models | 4 / 7 | 4 / 7 | yes |
| triangles, all models | 36,920 | 36,920 | yes |
| VVD vertices | 21,979 | 21,979 | yes |

**One discrepancy, and the repo's reader is the odd one out.** `source_model.load_model`
(`MDL`/`VVD`/`VTX`) raises *"VVD LOD0 vertex count 21979 != model numvertices
18359"* on this source. It sums `numvertices` over **every model of every
bodypart**, but the VVD holds one LOD-0 block for the whole file, 21,979
vertices — the sum over the 7 models is not the file's vertex count. The
Christie builder does not use `load_model`; it has its own
`load_christie`/`_read_vtx_meshes_all_models` path, which is correct here and
reproduces SourceIO's 36,920 triangles exactly. So the failing assertion is in a
reader this pack does not go through, and the pack's numbers reconcile with an
independent parser. It is still a live trap for the next pack that calls
`load_model` on a multi-model bodypart; it is recorded, not fixed, because it is
outside this scope.

**What the source is, and what the pack drops.** The archive is DOA5 costume `c2`
with four bodyparts: `studio` (body + bra underlay + both eyes + a tattoo decal),
`glasses`, `bra` (a second bra variant with its own material), `head` (two
models: hair with six hair materials, and a helmet with the hood and glasses
lens). The pack keeps four of the twenty materials — skin, blazer, shirt,
inner top — and drops everything the head carries: face, both eyes, the tattoo,
all six hair materials, the glasses, the hood/helmet materials. That is the
body-only contract working as intended.

---

## 2. Surprises, in order of how much they change the plan

### 2.1 The body keeps a bare neck under the vanilla head (217 vertices)

`mtr_body` (skin) carries **217 vertices between z 150 cm and z 163 cm**, i.e.
from the collar up to mid-neck, with **58 boundary edges above z 145 cm**. Under
a *different* head — which is what LAS gives you when no head pack is installed —
that bare neck sits inside or behind the heister's own head.

This matters for the neck tonal split (§10.4 in the 2026-11-07 diagnosis, still
open there): the 2026-11-07 audit measured the *head's* neck rim and the
*body's UVs* and ruled both out, and shipped a "skirt" as insurance. It did not
report that the pack draws its own neck through the region where two different
skin textures meet. The bisect in the checklist (§5) has to start there, not
with the head packs.

The 2026-11-10 frame shows the line: a pale, matte neck column between the jaw
and the blazer collar, reading lighter and warmer than the face above it. That
is consistent with two skin materials lit by one shader, but **a single frame is
not proof of which surface it is** — the bisect is what decides, and it has not
been run.

### 2.2 The gloss mask is not derived from the phong parameters — and it is inverted per material

The build computes each material's gloss from the **normal map's alpha** with a
hand-chosen `(scale, max_a)` pair (`DF_SPECULAR_FROM_NORMAL` in
`build_christie_las.py`), then attenuates the sleeve by a fixed 55 %. The VMTs
in the same archive carry `$phongboost` / `$phongexponent` /
`$phongfresnelranges` per material, and those were not used.

Measured on the shipped zip, the result is not a uniform choice of gloss; it is
different in direction per material:

| material | source diffuse α (p50 / p99) | source normal α (the phong mask) | shipped diffuse α (p50 / p99) |
| --- | --- | --- | --- |
| skin `mtr_body` | 12 / 176 | 90 / 222 | 22 / 58 |
| blazer `mtr_c02_01` | 32 / 170 | 58 / 212 | 10 / 40 |
| shirt `mtr_c02_02` | 255 / 255 | 14 / 248 | 2 / 44 |
| inner `mtr_c02_05` | 38 / 255 | 56 / 179 | 4 / 12 |

The shirt is the sharp one: **flat 255 in the source's diffuse alpha, 14 at the
median in its phong mask**, and the pack ships it at median 2 — the lowest gloss
of the four. The blazer's mask peaks at 212 and ships at p99 40. Meanwhile the
skin, whose mask median is 90 (the most uniform mid-gloss of the four), ships
closer to its own mask. So the "sleeves read glossier than the torso" fix (a 55 %
attenuation inside the sleeve UV footprint) was applied to a mask that had
already been read from a different channel than the one the source uses for
specular.

**Not yet established:** what PD2's `generic:DIFFUSE_TEXTURE:NORMALMAP` shader
does with the diffuse alpha, per texel, in this build. The 2B reference's own
diffuse alpha is not flat (its first DXT5 block's alpha indices span the full
range), so "alpha is the specular mask" is not contradicted by the reference —
but neither is it confirmed by anything measured here. Rebuilding the decision
(checklist M1/M2) needs that confirmed first, or it is another hand-chosen scale
with a longer story.

### 2.3 The elbow fix squashes material instead of giving it back

Re-measured with the repo's own LBS on the shipped bytes, ±12 cm window, both
arms, forearm on local Y:

| pose | base min ratio | slim min ratio | 2B reference |
| --- | --- | --- | --- |
| idle (elbow 12°) | **1.000** | **1.000** | 0.719 |
| rifle (elbow ~40°) | 0.620 | 0.669 | — |
| bind (elbow 72°, authored) | 0.186 | **0.037** | — |

Two things follow.

- **The idle figure is 1.000 because the mesh is authored in the idle pose.**
  It is true by construction, not a fit: at idle the mesh is its bind, so no
  edge moves. The 2026-11-10 audit's headline "min edge ratio 1.000, 0 edges
  shortened" therefore says nothing about how the sleeve behaves when the
  elbow is *not* at idle — and the game plays the other poses.
- **The documented fix makes the other poses worse.** The 2026-11-07 round
  de-puffed the outer bend (`ELBOW_OUTER_TRIM = 0.65`, 74 + 73 verts moved up to
  3.78 cm). Checked at the bind pose, where those same vertices also live, the
  slim sleeve now reaches a **0.037** ratio — an edge at 3.7 % of its length,
  with 4.25 cm of shortening. The base pack at bind is 0.186. A squeeze applied
  to make one pose behave does not shrink the material; it leaves it squashed
  in every other pose the mesh is drawn in, which is exactly the "fill it in,
  don't squish it" the brief names.
- A Cycles render of the packed slim body at idle, front, shows a **dent on each
  outer forearm** at the elbow. The axial profile, taken perpendicular to the
  bone, has the sleeve at r90 ≈ 5.1–5.7 cm from 6 cm to 22 cm down the forearm
  and **3.9 cm at t = 8 cm**, a 25 % notch with no counterpart in the source.
  At the same station the base pack reads 4.9–5.6 cm. That is a second
  authoring-stage defect, not in the previous build's documented set.

### 2.4 The open elbow rims are still there, and the stitch pass's own log says so

55 boundary loops per sleeve material. One loop per elbow sits **4.5 cm from the
pivot** — 58 vertices on the left, 56 on the right, centred at (−30.3, 1.4,
124.7) and (29.9, 1.5, 125.2) cm. These are not free garment edges: they are the
rims the 2026-11-07 audit measured as "6–7 boundary edges, 8–9 rim vertices,
gap 0.6–2.2 cm", now larger because the stitch pass bridged across them.

The build's own `BUILD_INFO.json` says it: *"bridged 5 quad(s) / 10 tris over
10 rim pairs, gap to 2.94 cm"* for the base pack. A bridge across a gap is not a
closed surface — the ray cast still escapes, and **the base pack leaks 0.00 cm²
only because those rays happen to hit the overlapping layer behind**. Both packs
carry the open rim; only the slim's is wide enough to be caught.

D18 is unchanged and reproduces exactly: slim left 6.70 cm², slim right
4.95 cm², base 0.00/0.00, same leaky slices at z 125.3–126.6.

### 2.5 The source's own normal-map convention is Y−, and the build flips it

Both `cri_body_base_nrm` and `cri_02_01_nrm` decode with a green channel centred
just *below* 128 (127.4 and 127.1, and only 7.9 % / 34.5 % of texels above 128).
The build calls `swizzle_standard_normal_dxt5_to_pd2(raw_nm, invert_y=True)`,
which is the same decision `lawson` and Miranda make. Consistent, and correct
for a DirectX-style source; recorded because it was assumed to be a question and
turned out to be already right.

### 2.6 The lightwarp and every `C1` texture the pack would need are absent

`cri_body_base.vmt` points at `models/plasmid/DOA5/Christie/C1/detail/faceWRp`
and sets `$halflambert 0`; every hair material points at a `C1` base texture and
a `C1/detail/hair_gloss` warp. **None of those files is in the archive** — the
archive carries `c2` only. So the source model, in the game it was made for,
shows its body without a lightwarp while its face has one. Whatever is done with
the neck (§2.1), the body and the vanilla head will not agree on how they are
lit by the source's own material settings; the difference is a property of the
input, not of the pack's build.

---

## 3. What this does **not** establish

- **Which surface the 2026-11-10 neck line belongs to.** One frame, no bisect.
  The checklist's §5 exists for this and has not been run.
- **That any pose in §2.3 is a pose the game plays.** P1/P2 are the repo's
  measured idle and a hand-set rifle approximation; the game's own arm IK is not
  in this repository and was not available.
- **That the gloss table means what it appears to mean in game.** The packed
  alpha is measured; the shader's use of it is not.
- **Anything about the head, hair, eyes or glasses.** They are dropped by
  contract; they are inputs to the bisect, not build targets.
- **That the tracked zips load.** Only a user can run the game. Nothing in this
  note says a pack loads, and the install matrix in the checklist has not been
  recorded.

---

## 4. Two artefacts for the decisions this report cannot make

### 4.1 The slim target (decision (a))

[`docs/pd2-las/renders/christie_redo_target_comparison.png`](../pd2-las/renders/christie_redo_target_comparison.png)
is one orthographic front view each of the **raw source body** in its own bind
pose, the **base pack** at idle, and the **slim pack** at idle, each scaled to
its own height, same light, no textures.

It is here because the question "current proportions or re-derived from the DOA5
silhouette" needs a picture, and the packs and the source are in different poses
(arms out and hands present vs idle and hands cut), so a width-vs-height table
is not a fair comparison — a first attempt at one produced nonsense (0.14–1.02
ratios at the same height fractions) for exactly that reason.

What the sheet shows, stated as observation and not as a recommendation: the
slim pack's arms are thinner than both the source and the base pack through the
whole forearm, its torso is narrower at the waist, and the trouser flare — which
the source has and which the base pack keeps — is intact in both. **Where the
slim pack departs from the source's own silhouette is the arm, not the leg.** It
does not settle which target is right; that is the decision.

Read with §2.3: at idle the slim sleeve is also dented 25 % on its outer
forearm, so "thinner" in this sheet is partly a fit artefact, not a proportion.

### 4.2 The neck, as the bisect will see it

In the same sheet, the base and slim figures show the bare skin neck (§2.1)
standing out of the blazer collar as a separate band, above the collar and below
where the vanilla head will sit. That is the surface the §10.4 bisect has to
rule in or out first. **The sheet is not evidence about the in-game line**: it
is unlit by the game, untextured, and has no head on it.

### 4.3 The retarget overlay

Not done in this pass, and said plainly rather than implied: the overlay of the
source ghost against the target skeleton needs the authoring scene, which is the
next step and is gated on the three decisions below. The bind-pose alignment it
would validate is currently only checked by the numbers the build already
records (`fit_tpp`, in `BUILD_INFO.json`): joint offsets of 1.76 cm (left
forearm) and 2.01 cm (right), cuff placement within 1.02 cm of the pivot.
Those are the pack's own measurements of itself and are therefore assumption,
not verification.

## 5. Re-measurement of the pack's own defect claims (same day, offline only)

Every claim below was re-derived from the tracked zips with a probe that can be
re-run from this tree; the probes are described so the numbers can be disputed
without trusting the person who ran them. Nothing in this section changed a
tracked byte: `dist/Christie_LAS.zip` is still `b65fb27e…` and
`dist/Christie_LAS_Slim.zip` still `9da90dd3…`, and both rebuild from this tree
byte-identically (`make -sC tools/pd2-las fresh` → 16 of 16).

### 5.1 The outer-forearm "dent" is not caused by `ELBOW_OUTER_TRIM`

`CHRISTIE.md` and §2.3 of this audit attribute the 25 % narrowing of the slim
sleeve's outer forearm to the elbow trim. Tested by rebuilding the base pack
once, saving the body group exactly as `trim_elbows` receives it, and applying
the trim **once** per setting to that same input:

| setting | p10 / p90 radius at elbow | dent (p90 r, 1 cm station at 8 cm) |
|---|---|---|
| as shipped (0.88 / outer 0.65) | 4.37 / 6.69 cm | 5.76 cm |
| 0.88 / outer 0.82 | 4.89 / 6.89 | 5.76 |
| 0.88 / outer 1.00 (outer trim off) | 5.24 / 7.17 | 5.76 |
| 1.00 / 1.00 (no trim at all) | 5.24 / 7.17 | 5.76 |

The outer trim changes the elbow radius by 0.5 cm and the forearm dent by
**0.00 cm**. (An earlier version of this probe double-applied the trim —
`trim_elbows` is not idempotent, re-running the shipped settings moves the dent
from 4.94 to 5.08 cm — and was discarded rather than cited.) The dent is
therefore a property of the source silhouette or of a different pass; attributing
it to the trim is wrong. With `ELBOW_TRIM = 1.0` the slim build also stops
passing its own `idle elbow coverage` gate, so the trim cannot simply be
switched off.

### 5.2 D18 is not a hole, and not a fixed slit either

The strict xfail (`KNOWN_SLEEVE_LEAK_CM2`) describes "each slim sleeve still
open just past the elbow". Measured:

* every leaking sample sits on one ray direction per arm (a 6° sample at 282° on
  the left, 78° on the right);
* the nearest boundary edge to that ray is **4.4 cm** away and the nearest
  sleeve surface vertex **4.3 cm** away — so it is not an open edge, and not a
  slit with unpaired rims. The ray passes close to the surface and misses
  through a gap between triangles large enough to slip a ray but far smaller
  than the "open sleeve" wording implies;
* the reported area is resolution-dependent and not conservative: left sleeve
  6.70 cm² at 6°/0.5 cm sampling, 8.36 cm² at 3°, 7.25 cm² at 1°; right sleeve
  4.95 cm² at 6° but **1.65 cm²** at 1°. The single number in the test is an
  artefact of the sample grid, in both directions.

Which pass opens it is still **unassigned**. Ruled out by direct rebuild:
`ELBOW_OUTER_TRIM` (setting it to 1.0 leaves the left leak at 6.70 and worsens
the right to 8.26), the `SLIM_FOLD_DELTAS` correction table (skipping it leaves
both leaks at exactly 6.70 / 4.95), and `stitch_sleeve_seams` settings
(`max_gap_cm` 3.6/4.5/6.0, `min_normal_dot` 0.3/0.0, `weld_cm` 0.06/0.5 all
leave the measured area unchanged).

### 5.3 The base pack is not clean by the same measure

Run with `cull_backfaces=True` — the setting that matches what D3D9 draws — the
check is not "slim is open", it is "both packs have grazing gaps". That was not
measured in this pass and is the next thing to measure before any sleeve-fix
work is planned; it decides whether D18 is a slim regression or a property of
the sleeve that the slim pass merely exposes.

### 5.4 Blender is no longer installed in this sandbox

`bpy` lived in `/tmp`, which is not part of the snapshot, so the Cycles
"second eye" leg cannot run until it is reinstalled. Stated so that no later
summary claims a renderer cross-check this round did not have. The images used
above come from the repo's own `render_mesh_skeleton.py`.
