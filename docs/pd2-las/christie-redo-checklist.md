# Christie redo — pre-registered verification checklist (2026-11-13)

Written **before** any geometry is authored, as the plan requires. Nothing on
this page is a result yet: every row has a pass/fail rule fixed in advance, so
that after the build the answer per row is one word and cannot be chosen to fit
what came out.

The pattern is [`in-game-checklist.md`](in-game-checklist.md). Its rules still
apply (what counts as a capture, how a hash is recorded). This page is Christie's
own, and it exists because the 2026-11-10 defect record was judged without one.

Two things are deliberately **not** on this page: any size, sha256 or test count
(`test_no_document_quotes_what_status_prints` forbids a second copy; `status`
and `green` print them), and any claim about what the game does with bytes that
nobody has installed.

---

## 0. What "the captured bytes" means here

The 2026-11-10 batch was captured from `Christie_LAS_Slim` and the report says
`7a4d010c…`; the tracked slim zip has been rebuilt twice since, so those frames
are **not** of the tracked bytes (HANDOFF, "Seen in game"). Every in-game row
below therefore starts from a fresh install of the exact zip in `dist/`, and the
hash written beside a row is the sha256 of the zip that was installed, computed
at capture time from the file the user installed — not copied from a document.

`runtime_verified` stays `false` in both packs until the user confirms that the
bytes they captured are the bytes `dist/` holds for that pack.

---

## 1. Install matrix (fix it before the first capture, and record it)

Record the exact values; a capture made on a different matrix does not count for
any row below.

| item | to record | how |
| --- | --- | --- |
| PAYDAY 2 | Steam build id and the game's update date | Steam → PAYDAY 2 → Properties → Updates; or `appmanifest_218620.acf` |
| SuperBLT | its `version.txt` / release tag | `<game>/mods/` loader file |
| BeardLib | its `main.xml` `version` attribute | `<game>/mods/BeardLib/main.xml` |
| LegendaryArmours | the `LegendaryArmours.lua` sha256 | hash the file; the repo's copy is the reference |
| the pack | zip sha256 **and** the member hashes of `christie.model`, `__fps` model and the four `_df`/`_nm` textures | `sha256sum dist/<pack>.zip`; members with `unzip -p … | sha256sum` |
| other LAS outfits | which packs are installed at the same time | the mods list; a second LAS outfit over the same heister invalidates `replace_body` captures |
| head | which head pack, if any (see the bisect in §5) | the mods list |

Pass = every cell filled before the first screenshot of a session.
Fail = a cell is missing or was filled in afterwards from memory.

---

## 2. Camera / light / distance matrix

One row per capture. The point is that the same defect is looked at twice: once
in the pose the game plays, once under light that would show it.

| # | where | pose | camera | light | distance | what it is for |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | lobby / idle | idle | front | lobby | 3 m | the whole silhouette; the 01 and 08 frames' viewpoint |
| C2 | lobby | idle | back three-quarter, both sides | lobby | 2 m | rear sleeve, the documented dark wedge |
| C3 | lobby | idle | left profile | lobby | 2 m | outer forearm, inner elbow from the side |
| C4 | lobby | idle | low three-quarter (**camera below the elbow**) | lobby | 1.2 m | the inner-elbow crook; **the frame the 2026-11-10 batch is missing** |
| C5 | menu | rifle | front three-quarter right, as frame 08 | menu | 1.5 m | the pose with the flap |
| C6 | menu | rifle | same pose, camera below the elbow | menu | 0.9 m | the flap, closed or open |
| C7 | in heist | crouch | three-quarter | heist | 2 m | the elbow at its tightest angle |
| C8 | in heist | reload | three-quarter | heist | 2 m | the elbow while the wrist rolls |
| C9 | in heist | run | side | heist | 3 m | the sleeve at speed, motion blur off |
| C10 | first person | arms out | viewmodel | as played | — | `fps_christie` on its own: cuffs, gloves, sleeve mouth |
| C11 | any | idle | **shadow** on a plain wall, sun through a window | — | 3 m | the silhouette the shadow caster writes; the `s_body` drawable |
| C12 | lobby | idle | neck, tight | lobby | 0.8 m | the §10.4 bisect frames (§5) |

Pass = every row captured at the stated pose and distance, with the file's own
sha256 recorded beside it.
Fail = a row is missing, or was shot at a distance that cannot show the item.

---

## 3. Geometry and deformation, judged offline first (no game needed)

These are the criteria the authoring stage is held to **before** a zip is built.
They are stated as pass/fail so the build either clears them or is not shipped.

| # | item | pass | how it is measured | fails if |
| --- | --- | --- | --- | --- |
| G1 | sleeve tube closed at every slice | 0 open slices on **both** sleeves of **both** packs | `diagnose_mesh.py --templates` radial ray cast, the probe behind D18 | any slice leaks, or the leak is excused by a new `xfail` |
| G2 | open rims at the elbow | 0 boundary loops within 3 cm of either elbow pivot, in the blazer material | boundary-edge loops on the packed mesh, in Blender | a rim survives; a rim moved past the 3 cm window without closing is a fail, not a pass |
| G3 | inverted faces in the elbow window | 0 at every pose of §4 | signed face normal vs vertex normals, per pose | one inverted face |
| G4 | worst-edge compression at idle | ratio **≥ 0.719** (the 2B reference) in the ±12 cm window, both arms | edge length posed / bind, the repo's LBS | any edge below 0.719 at idle |
| G5 | worst-edge compression, rifle | ratio **≥ 0.719**, or a written re-acceptance if not | same | below 0.719 without the re-acceptance |
| G6 | no visible flap under fixed inner-elbow light | no self-intersection and no shadow edge across the crook in C4/C6, and none in the matching Cycles render | Cycles render from the same camera, plus a signed-distance self-intersection test | a shadow or a crease line that the 2B body does not have at the same camera |
| G7 | bind → idle gives back length | the sleeve does not crumple: no edge shorter than 60 % of bind within 12 cm of the pivot | same as G4 | any such edge |
| G8 | slim proportions preserved | upper arm ≥ 0.70 and forearm ≥ 0.78 of base at the same station; height equal to base | cross-sections perpendicular to the bone | the ratio drifts, or the height changes |

"Fixed at the authoring stage" means: the closed tube, the filled rim and the
weight repaint all exist in the **exported** mesh as real topology, and survive
the deterministic export byte-for-byte. A test expectation is never the fix.

---

## 4. The pose sweep (offline, every sample rendered)

Poses the game plays, on the PD2 skeleton, with the forearm rotated about its
**local Y** (flexion) and never local X:

| sample | pose |
| --- | --- |
| P1 | idle (elbow 12°) |
| P2 | rifle / menu (elbow ≈ 40°) |
| P3 | crouch (elbow ≈ 80°) |
| P4 | reload (elbow ≈ 95°, wrist rolled) |
| P5 | run (idle elbow, shoulder swung 25°) |
| P6 | bind (elbow 72°, the pose the mesh is authored in) |

Each of P1..P6 × {base, slim} × {inner, outer} elbows is rendered and kept. The
files named in the report are the evidence; a P-row passes only when **every**
sample of it exists and G3/G4 hold on it.

Pass = the renders exist, G3 is 0 everywhere, and G4's ratio holds at P1 and P2.
Fail = a pose was skipped, or a sample was rendered after the criteria changed.

---

## 5. The §10.4 neck bisect — before any mesh conclusion

Run in this order, one capture (C12) per step, everything else in the install
matrix unchanged. The 2026-11-07 audit left the neck split open with the head
rim and the body's UVs both ruled out; the next measurement is this bisect, not
another hypothesis.

| step | install | if the tonal line is **still** there | if it is **gone** |
| --- | --- | --- | --- |
| N0 | base pack, **no head pack** (vanilla heister head) | it is the body: the blazer neckline against the skin material, or the lighting across it | — |
| N1 | base pack + vanilla head, **body's own neck ring removed** (a build variant, offline) | it is not the neck ring | it is the neck ring |
| N2 | base pack + each head pack this repo builds, one at a time | it is not that head pack | it is that head pack |
| N3 | slim pack, same three steps | the same result holds for slim | a slim-only cause |

Pass = all four steps run and recorded; the cause is named with the step that
isolated it.
Fail = a mesh conclusion is written before N0..N2 are done.

**Checked before running it:** the body keeps **217 skin (`mtr_body`) vertices
between the collar and mid-neck (z 150–163 cm)** under the vanilla head, and 58
of its boundary edges sit above z 145. So N0 is a real test of a real surface —
but note the consequence: the pack does **not** simply stop at the collar.

---

## 6. Materials

Rebuild the gloss decision from the VMT phong parameters, and hold the texture
leg to these:

| # | item | pass | how |
| --- | --- | --- | --- |
| M1 | gloss mask derived from the phong parameters | every kept material's diffuse alpha is a stated function of `$phongboost`, `$phongexponent`, `$phongfresnelranges` and the normal map's alpha, with the rule written down | the derivation goes in the audit, with the numbers per material |
| M2 | no mask by hand-chosen scale | the build contains no per-material `(scale, max_a)` pair that is not derived by M1 | reading `build_christie_las.py` |
| M3 | mips bottom-up | every level is the area average of the level above it, and the pack's level count equals the vanilla shape | `mip_audit.py`, plus a second decoder |
| M4 | Y+ normals | the packed normal's green channel convention is the one lawson and Miranda use, verified by decoding a known-flat texel | second decoder |
| M5 | DXT5 verified twice | every packed `.texture` decodes to the same RGBA through two independent decoders, within 1/255 | `dds_encode.decode_bc3_level` and `inspect_textures`'s `sourcepp` path |
| M6 | sRGB and flags | flags and format of every packed texture equal the 2B pack's for the same role | header compare |

Fail = any packed texture has no rule behind it, or a decoder disagrees.

---

## 7. Export and the pipeline (the contract, unchanged)

| # | item | pass |
| --- | --- | --- |
| E1 | `make -sC tools/pd2-las green` | green |
| E2 | `make -sC tools/pd2-las fresh` | green, both packs rebuild to their tracked hashes |
| E3 | no test loosened | the diff adds tests; it removes no assertion and adds no `xfail` |
| E4 | determinism | the code path is declared and the declared one is what loads (see the note below) |

**Environment note, measured 2026-11-13:** `green` is **red in a fresh sandbox**
before any of this work, for reasons that have nothing to do with Christie:
`recover_env.sh` installs numpy without `pins.txt`'s constraint unless a
constraint is passed (it does pass `-c pins.txt`; the failure was seen when the
venv had been built by an earlier run without it), and `fresh` stops with
`not on the declared code path: OpenBLAS … 0 thread(s)` while the pinned
numpy 2.4.6 loads cleanly. Restoring `numpy==2.4.6` turned both failing tests
green. This is recorded here because "green is green" has to be true *before*
the Christie work, or a red result later cannot be attributed.

---

## 8. Cycles turntable, as the second eye

For each pack: a Cycles turntable of the **packed bytes** (the mesh decoded from
the zip, not the authoring scene), four views, at the same light angles as the
game frames. It is compared against:

- the in-game frames of §2, same pose and camera;
- the 2B pack captured the same session, same camera, same light.

| # | item | pass |
| --- | --- | --- |
| T1 | turntable exists for both packs, from the zip | 8 images, each from the shipped `.model` |
| T2 | elbow at the in-game camera | the turntable and the frame show the same surface; no crease, shadow or rim in one and not the other |
| T3 | 2B side by side | wherever Christie differs from 2B at the same camera, the difference is named in the audit |

Fail = the turntable is rendered from the authoring scene instead of the packed
bytes, or a difference from 2B is left unnamed.

---

## 9. Sign-off (the user's, not the agent's)

| # | item | who |
| --- | --- | --- |
| S1 | base pack in game, every row of §2 and §3 read out | user |
| S2 | slim is not put in `dist/` until S1 is signed | agent holds; user releases |
| S3 | the D18 leak: fixed at the authoring stage, or re-accepted in writing with images | user |
| S4 | the body-only LAS contract (replace_body, no head/hands for slim, glove adapter) — any change is a proposal with evidence, never a change | user |
| S5 | `runtime_verified` flipped | user confirms bytes → agent flips, and updates HANDOFF's table |

---

## What this checklist does not cover, and says so

- **The head, hair, eyes and the missing `C1` textures.** The pack drops them
  by contract; anything about them is a bisect input (§5), not a build target.
- **Which pack the game actually loaded.** Only the member hashes of the
  installed zip prove that; a screenshot cannot.
- **Anything about a pose the game plays that is not P1–P6**, including the
  weapon-specific arm IK, which is not in this repository.
