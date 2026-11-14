# Christie rebuild — redo, from a deleted builder back to verifiable bytes (2026-11-14)

Request 2026-11-14 ("Christie packs redo", scope `dist/Christie_LAS.zip` only): rebuild the pack
from `references/Christie.zip` and verify it end to end. This is the report. The pre-registered
acceptance gates are `docs/pd2-las/christie-rebuild-checklist.md` (written before any build ran,
as directed); each gate's verdict is recorded there too.

**Outcome, in one line:** the pack in `dist/` is reproducible byte-for-byte from the source zip
through a reconstructed pipeline, and every offline gate passes.

> **Postscript (2026-11-14, later) — the workspace was re-created from a fresh clone at
> `6f26633` three times today; the local, never-pushed commits `8dd498b..0383a7a` vanished from
> this checkout each time.** Two facts then turned out to both be true at once:
>
> - In **this** checkout the tracked `dist/Christie_LAS.zip` was the base-commit bytes
>   (`b65fb27e…`) and everything recorded below (measured on the `1ec1c95a…` sleeve-bridge
>   bytes) could not be re-measured — the bridge builder existed nowhere.
> - When this branch was finally pushed (owner-approved, 2026-11-14), the push was rejected:
>   **the remote already carried `8dd498b..0383a7a`** (it had been pushed at some point that the
>   local clones never saw). A merge of `origin/arena/4f5923fc-universal-modder` restored the
>   bridge pack to `dist/` — `Christie_LAS.zip` is `1ec1c95a…` (sidecar matches), and
>   `Christie_LAS_Slim.zip` is `ebe44af7…` (sidecar matches; the earlier `9da90dd3…` base slim
>   bytes are NOT what is tracked).
>
> So the evidence below **is** once again a record about the tracked bytes — the `1ec1c95a…`
> build this report verified is what `dist/` holds on the merged branch. What did not survive
> anywhere: the recovered builder venv, the Cycles frames and the ingest probe (all under
> `build/`). The evidence remains what it was: a truthful record of measurements made on
> `1ec1c95a…`; it does not carry `runtime_verified`.

## Honesty box — what "independent" means here

- **Ingest cross-checks**: `build/christie-raw/ingest_check.py`, a hand-written walk of the
  MDL/VVD/VTX/PHY/VTF bytes (no repo parser code), cross-checked leg by leg against
  `tools/pd2-las/source_model.py`. It caught its own wrong stride guesses (VTX group/vertex/strip
  headers are packed structs — group 25 B, vertex 9 B, strip 27 B, as the repo's constants have it)
  before any result was accepted. All legs reconcile.
- **Textures**: the repo's VTF→DDS conversion was checked against `texture2ddecoder` (BC3,
  `build/verify-venv`), not against the repo. Channel order aside (t2d emits BGRA), all 20 VTFs
  decode to identical pixels; `pupil_ambient` (the only multi-mip file) verifies the repo's
  smallest-mip-first slice layout exactly. `sourcepp`'s VTF reader was also tried first — it
  refused these files outright (`ImageFormat.EMPTY`), so it played no part.
- **Struct layouts**: Valve `source-sdk-2013` `public/studio.h` (fetched 2026-11-14 into
  `build/source-sdk/`) was used to confirm the MDL v48 bodypart/model/mesh strides.
- **Blender/Cycles**: `bpy` 4.2.23 LTS (PyPI), CPU Cycles, headless, rendering through stub `.so`
  shims for the missing X/GL system libraries (`build/xstub/`; apt is unreachable from this box,
  so the stubs are why the renderer runs at all).
- **The game is not available.** `runtime_verified` stays `false`. Every in-game claim belongs to
  `docs/pd2-las/in-game-checklist.md` and a person with PAYDAY 2.

## What was done, in the method order

1. **Ingest reconcile** — done first, before the checklist and before any build. All legs
   reconcile (MDL/VVD/VTX checksum `0xb6426643`, 98 bones, 21,979 LOD0 verts, 22 meshes,
   36,920 LOD0 triangles, 20 VTFs all DXT5, PHY 21 solids / 20 constraints / rootname
   `MOT00_Hips`). The kept-material map was tabulated mesh by mesh (meshes 4/5/6/9 kept;
   1-tri `cri_face_base` dummies at meshes 8 and 10 are dropped by the material filter — asserted,
   not assumed).
2. **Pre-registered checklist** — `docs/pd2-las/christie-rebuild-checklist.md`, written before the
   build: frozen source hash, the ingest table, and gates G1–G9 (registration, kept scope, sleeve/elbow
   topology, materials, rest pose, pose sweep, round-trip, reproducibility, report).
3. **Build** — the Christie builder was deleted on 2026-11-14 (`b0a7115`, at the owner's direction),
   so the build path was **recovered from git history** into `build/christie-rebuild/` (untracked
   scratch; the repo's tool tree was not modified). `references/Christie.zip` hashes to
   `605c352a…` as the tracked pack's `BUILD_INFO.json` records, so the rebuild starts from exactly
   the shipped pack's source bytes. Two consecutive full builds were run; both produce
   `1ec1c95a…` — **byte-identical to the tracked `dist/Christie_LAS.zip`**. All 20 fit/topology
   metrics recorded in the tracked pack's `BUILD_INFO.json` reproduce exactly (worst joint
   5.91 cm, worst drift 3.05 cm, stitch 22 faces / 31 welded / 1 hole filled, 512 unified normals
   over 128 groups, max relax 2.28202 cm).
4. **Cycles turntable / pose sweep** — 16 frames under `build/christie-rebuild/renders/`
   (hang 12°; 28°/48°/70° elbow flexion on the measured PD2 flexion axis, `BEND_AXIS=1`; front and
   side full-body plus left-elbow close-ups), rendered with the shipped `.texture` files (DDS→PNG
   via Pillow), plus the mesh-vs-skeleton overlay set under
   `build/christie-rebuild/overlay/`. Findings:
   - silhouette and layering are correct at every pose (blazer/shirt/skin shells all present,
     no spikes, no candy-wrapper, no missing drawables, hands render);
   - at 70° flexion the side view shows the known **inner-elbow sliver** — the bright triangle of
     back-light/back-face at the fold. It is consistent with the recorded offline verdict
     (2026-11-14 shading audit: *not a geometry defect we can measure* — zero self-intersections
     within 6 cm of either elbow pivot, zero interior coincident-normal divergence, 0 flipped
     faces at the idle; the visible fold is the authored DOA5 crease lit at grazing angle plus the
     rim-adjacent face class there). **No blind edit was made**; the isolation that decides it
     (rifle vs no-rifle, matched camera, in game) remains in-game work.
   - the rear-sleeve bridge from `8dd498b` re-ran exactly (10 rim pairs bridged, gap spans
     2.94/3.02 cm, one pinhole filled) — the sleeve tube ships closed.
5. **Report** — this document.

## Gate verdicts

| Gate | Verdict |
|---|---|
| G1 registration | **pass** — `la.christie = {` with `hide_mask`, `hide_armor`, `replace_body`, `fps_hide_armor`, `fps_replace_body`; `main.xml` + `hooks/christie_las.lua`; `localization/english.txt`; no `replace_all` |
| G2 kept scope | **pass** — the zip holds exactly the four kept materials' textures (`{body,c02_01,c02_02,c02_05}_{df,nm}`); no face/hair/glasses/lashes/wet bytes; 21 files |
| G3 sleeve/elbow topology | **pass (named residual)** — slit bridge re-derived, closes the tube (22 faces/31 welded/1 filled, identical to tracked bytes); the inner-elbow flap is a **named, measured residual** (see above); deciding it is in-game work, not an offline edit |
| G4 materials | **pass** — dry set only; full mip pyramids in vanilla PD2 header shape (11/11/11/11/10/10/9/9 mips, all DXT5); bumpmaps swizzled; diffuse alpha rebuilt from the normal map (gloss fix); no lightwarp shipped |
| G5 rest pose | **pass** — 12° near-idle authored rest reproduced (identical bytes); orientation breaks 0, winding 97.9%, TPP/FPS rest-world equality carried in the model; retarget overlay renders with the arm chain inside the sleeve at hang and at the menu flex (`build/christie-rebuild/overlay/`) |
| G6 pose sweep | **pass (advisory)** — Cycles CPU frames at rest and 28/48/70° flexion, front/side/close-up; silhouette clean, no boundary/spike defects visible; frames are under `build/` (untracked) |
| G7 round-trip | **pass** — `.model` re-parses; atoms tile and stay inside their vertex/index blocks (christie 10,373 verts/17,309 tris; fps 4,169/6,941); `material_config` slots present in the model hashlist; the small XML/lua/txt files well-formed; all 8 shipped `.texture`s decode through the independent BC3 path |
| G8 reproducibility | **pass** — two consecutive builds were byte-identical to each other and to the tracked pack (`1ec1c95a…`); two sidecars matched. The tracked pack on the merged branch is once again `1ec1c95a…`; see the postscript |
| G9 report | **pass** — this document |

## What changed in the repository

- `docs/pd2-las/christie-rebuild-checklist.md` (new; gates + verdicts)
- `docs/audits/2026-11-14-christie-rebuild-redo.md` (this file)
- `docs/pd2-las/in-game-checklist.md` (new Christie LAS section)

**Nothing under `dist/`, `tools/`, `assets/` or `tests/` changed from this report's measurements.**
After the 2026-11-14 re-clone/merge sequence, the merged branch carries the bridge bytes
(`1ec1c95a…`) in `dist/`; the builder remains deleted (that deletion is part of `b0a7115` and
stands). For reference, the pre-bridge pair in the base commit is recoverable with:

```sh
git show 6f26633:tools/pd2-las/build_christie_las.py > tools/pd2-las/build_christie_las.py
git show 6f26633:tools/pd2-las/christie_skeleton_map.json > tools/pd2-las/christie_skeleton_map.json
```

— but building from it recovers the base pack (`b65fb27e…`), which today's from-scratch verification
(`docs/audits/2026-11-14-christie-from-scratch.md`) reproduces and gates-passes; it does **not** recover
the sleeve-bridge bytes.

## Not verified (and why)

In-game behaviour of any of this: the game, the heist, the menu, motion, FOV, mip behaviour in
flight, and crash-freedom. `runtime_verified` remains `false` in the shipped `BUILD_INFO.json`.
The specific in-game steps that would close the open items (rifle-vs-no-rifle elbow capture;
head on/off throat bisect; gloss re-check at matched build; cuff/glove stack) are listed in
`docs/pd2-las/in-game-checklist.md` under "Christie LAS", and their outcome should be appended
to that file rather than edited away.
