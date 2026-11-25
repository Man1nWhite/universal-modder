# pd2-las — decisions, and why

What was decided about the Source-model → LAS pipeline (`tools/pd2-las/`), when,
and for what reason, so that nobody undoes a decision by accident or argues one
out again from scratch. For how to build, start at
[`tools/pd2-las/README.md`](../../tools/pd2-las/README.md); for the dated state
of the packs, [`HANDOFF.md`](HANDOFF.md).

**How to read it.** One entry per decision. *Why* is what the record says, not
what seems plausible: where the repository never wrote the reason down, the
entry says "not recorded". *Source* names the commit or document the entry
rests on.

**Where it comes from.** Reconstructed on 2026-11-11 from the commit messages
on `main`, the audits in `docs/audits/`, `HANDOFF.md` and
`tools/pd2-las/MODLOG.md`. Three reasons that the record lacked were asked of
the user that day; they are marked "the user, asked on 2026-11-11". A checkout
made by the sandbox is shallow, so read a cited commit with `gh api
repos/Man1nWhite/universal-modder/commits/<sha> --jq .commit.message`, or run
`git fetch --unshallow` first.

**How to add to it.** Append an entry with its date. When a decision is
replaced, mark the old entry "superseded by D<n>" and leave its text alone.

## Product and routes

### D1 — Ship an additive LAS outfit; do not replace whole heister models

- **Decided:** 2026-10-18, by the user · `abd7219`, `62cdb5d`
- **Decision:** the product is a Legendary Armour Skins outfit that installs
  beside the game's content. The pipeline that edited shipped heister models
  in place was deleted.
- **Why:** in game, the replaced Clover model was visibly broken and the
  outfit packs crashed at menu spawn; the root cause was an unrigged source
  force-fitted to a heister skeleton, which later registration repairs could
  not fix. The old pipeline also needed a workspace outside the repository and
  did not reproduce from a clean checkout.
- **Not this:** the head-replacement packs of `tools/build_joy_head_mods.py`
  (from 2026-10-20) replace head units only, on the pattern of
  `references/Ada Wong over Joy.7z`. They are a separate product, not a return
  to this route.
- **Source:** `docs/audits/2026-10-18-route-change-audit.md`,
  `docs/audits/2026-10-18-old-model-retired-las-restart.md`
- **Status:** holds.

### D2 — The 2B pack is the contract and the skeleton donor, not an oracle

- **Decided:** 2026-10-18 · `abd7219`
- **Decision:** `references/2b.rar`, a working LAS outfit supplied by the
  user, defines the pack shape (a hook that creates `LegendaryArmours.<id>`,
  a third-person and a first-person unit, the hide/replace flags, BeardLib
  `main.xml`), and its two `.model` files are the templates every builder
  skins onto.
- **Why:** it is the one known-good example of the product. It was studied as
  a specification and never installed here.
- **Limit:** it has defects of its own that must not be copied: `ss.model` is
  shipped but registered nowhere, both `cooked_physics` files are empty, and
  `main.xml` says `<Hooks directory="Hooks">` where the folder is `hooks/`.
  Re-checked against the unpacked archive on 2026-11-11.
- **Source:** the two audits under D1;
  `knowledge/games/payday-2/las-armor-skin-outfit.md`
- **Status:** holds.

### D3 — The two LAS pipelines stay separate trees

- **Decided:** 2026-10-19 · `c5e5f14` (merge), `08648db`
- **Decision:** `tools/pd2-port/` (rigged COLLADA → LAS) and `tools/pd2-las/`
  (compiled Source model → LAS) are not merged. Methods may be ported from one
  to the other; files are not moved or unified.
- **Why:** the two were started in parallel sessions on 2026-10-18 from
  different sources and merged the next day. Same-job modules shared 2–5% of
  their lines; each codec encodes a different verified `.model` dialect, so a
  merged codec would put both byte-exact contracts behind one bug; and the
  release workflow of `tools/pd2-port/` is built on its paths.
- **Source:** `tools/README.md`, "Why they are not merged"
- **Status:** holds. One small exception since 2026-11-11:
  `tools/pd2-port/preview_check.py` imports `extract_2b` from this tree to
  find the 2B model (D15), rather than spell its path a second time.

### D4 — No public release

- **Decided:** 2026-10-18
- **Decision:** the packs and their sources are for private use; nothing is
  published or redistributed.
- **Why:** the sources are fan rips (Mass Effect 2 by way of an L4D2 addon;
  Dead or Alive 5) whose redistribution rights are unresolved.
- **Source:** the route-change audit; `tools/pd2-las/README.md`, "Status"
- **Status:** superseded by D32 (2026-11-13).

## Building

### D5 — Our own `.model` codec, byte-exact; no Blender or external tool in the build

- **Decided:** 2026-10-18 · `51bc8d9`
- **Decision:** `diesel_model.py` reads and writes Diesel `.model` files in
  pure Python, and a build needs nothing but the venv.
- **Why:** the retired pipeline depended on Blender stubs and an external
  workspace, which is what made it unreproducible (D1). The codec was
  validated byte for byte against round trips of payday2-model-tool, and
  `ModelFile.read → write` is byte-exact on both 2B templates.
- **Source:** `51bc8d9`; `tests/test_diesel_model.py`
- **Status:** holds.

### D6 — Retarget by anatomical partition, not per bone and not by frame deltas

- **Decided:** in steps, 2026-10-18 to 2026-11-02 · `51bc8d9`, `6196b2b`,
  `2e73ef4`, `34eedeb`, `219a8a4`, `115b4c4`, `f0a5129`
- **Decision:** `retarget_maps` fits the torso, neck and head as one upright
  frame, each leg as one four-joint fit, and each arm as a chain of
  shortest-arc segment alignments whose fingers share the hand's transform.
- **Why:** its docstring names the three failures of unconstrained
  per-subtree fits that the partition avoids: bent forearms and thirty finger
  bones pitching the spine backward, a two-point fit rolling the foot, and
  twist along the arm.
- **Superseded on the way:**
  - 2026-10-18 (`51bc8d9`): one similarity fit per target bone over its
    subtree. It tore at the fingers (up to 40°) and gave the neck a 58° rogue
    frame.
  - 2026-10-19 (`6196b2b`): the same, plus three coherence rules — everything
    under a hand shares the hand's fit, a fit more than 30° off the global
    registration inherits its ancestor's, single-pair targets keep exact
    joint placement. **This is the design the README still described until
    2026-11-11.** The description was dropped from the README then, not moved,
    because the code no longer works that way; its text is in the message of
    `6196b2b`. The constant `FIT_MAX_DIVERGENCE_DEG` was left over from it in
    `build_models.py` until 2026-11-13; nothing read it, and it went with D33.
- **Dead ends, do not retry:** raw frame-delta transfer in any form shears
  the mesh into ribbons; one shared fit across both legs collapses the thighs
  onto one point.
- **Source:** the `retarget_maps` docstring; `HANDOFF.md`, "Dead ends"; the
  message of `6196b2b`. The commits from `2e73ef4` to `115b4c4` carry a
  subject line only, so the reason for each intermediate step is not recorded.
- **Status:** holds.

### D7 — Geometry conventions are the 2B model's

- **Decided:** 2026-10-18 and 2026-10-19 · `51bc8d9`, `401195b`
- **Decision:** UVs are stored as `(u, 1 − v)`; triangle winding is reversed
  from Source; positions are world-at-bind centimetres with the feet at
  `z = 0`; every vertex has three weights. No step multiplies by 2.54: the
  retarget fits carry the inch-to-centimetre scale.
- **Why:** each convention is copied from `2b.model`, which is known to work
  in game, and matches the GLTF import of payday2-model-tool. The UV
  convention was then proved offline by rendering our UVs and 2B's through
  the same sampler (`uv_check.py`).
- **Source:** the `build_models.py` module docstring; `401195b`
- **Status:** holds. Each convention has a test of its own on the tracked
  packs (D21).

### D8 — Install under `assets/mod_overrides/`

- **Decided:** 2026-10-19 · `f2d1dfd`
- **Decision:** the packs go into `PAYDAY 2/assets/mod_overrides/`, not
  `mods/`.
- **Why:** the 2B pack, the MOOG template, the ModWorkshop guide and the
  other pipeline all use it, and BeardLib loads complete `main.xml` mods from
  there. `mods/` would probably work as well; this is the documented
  convention.
- **Source:** `f2d1dfd`
- **Status:** holds.

## Packs

### D9 — Built packs are tracked in git and must rebuild byte for byte

- **Decided:** 2026-10-19 and 2026-10-20 · `637b7a9`, `8564c91`, `fa798b2`,
  `5561380`, `6a1bd5f`
- **Decision:** every pack is committed under `dist/` with a `.sha256`
  sidecar. Zips are written with fixed timestamps and permissions, and
  pillow and numpy are pinned (in `tools/pd2-las/pins.txt` since D28; before that in `bootstrap.sh`, `recover_env.sh` and CI), so
  a rebuild of an unchanged tree gives the same bytes.
- **Why reproducible:** `zipfile` embedded modification times, so identical
  content produced a different zip on every build (`8564c91`); the pins exist
  so that "the byte check compares like with like" (`5561380`), and CI fails a
  push whose tracked pack differs from a fresh build (`fa798b2`).
- **Why tracked in git rather than only built:** so that a pack can be
  downloaded and installed straight from the repository, without building
  anything (the user, asked on 2026-11-11).
- **Source:** the commits above; `tests/test_dist_checksums.py`
- **Status:** holds, on any x86-64 Linux machine since 2026-11-12: D26.

### D10 — A variant is its own pack with its own LAS id

- **Decided:** 2026-11-04 · `73fbc85`
- **Decision:** `Miranda_Busty_LAS` registers `LegendaryArmours.miranda_busty`
  with its own unit paths, texture stems, icon and hook.
- **Why:** so that it installs beside `Miranda_LAS` instead of overwriting
  it, and the stock pack and its builder stay untouched.
- **Source:** `73fbc85`; `CHEST-VARIANT.md` for the morph, which was rebuilt
  on a subdivided chest on 2026-11-05
- **Status:** holds.

### D13 — The Skyrim outfit route is cancelled

- **Decided:** 2026-11-05, on the user's explicit request · `6ed6a23`
- **Decision:** the outfit, its source archives and every mention of its name
  and author were removed. The code that outlived it was kept and renamed
  after what it does (`build_skyrim_outfit.py`, `las_outfit_pack.py`,
  `skyrim_*.py`).
- **Why:** not recorded, and not to be reopened from here. Do not reintroduce
  the name or the author into any tracked file.
- **Consequence:** that builder cannot run in this checkout; its tests skip
  for the missing archives.
- **Source:** `6ed6a23`
- **Status:** holds; superseded in part by D33 (2026-11-13): the code that was kept is deleted.

### D36 — The Honoka pack is committed to `dist/`, tracked but not fresh-verified

- **Decided:** 2026-11-15, by the user. The publication options were put to them; they chose
  committing the built pack to the branch.
- **Decision:** `dist/Honoka_LAS.zip` (the DOAXVV "Secret Report" costume, `build_honoka_las.py`) and
  its `.sha256` sidecar are committed. `make honoka` rebuilds into `build/honoka-las/` and copies the
  zip into `dist/` with the sidecar rewritten to the `dist/` path; `fresh` does not rebuild it (the
  builder never writes `dist/`), so `status` reports `make: null`, as it does for the Christie packs.
  No release and no other publication is part of this decision. `runtime_verified` is false; the bytes
  have never been in game.
- **Why:** tracking follows the D9 discipline (a sidecar beside every zip) without claiming a rebuild
  path that cannot byte-verify the copy in `dist/`. A pinned-environment rebuild after a sandbox restart
  reproduced the previously delivered bytes exactly, but that check is not wired into `fresh`.
- **Status:** superseded by D40 (2026-11-15): the pack and its builder are deleted.

### D37 — The tracked Honoka pack was rebuilt with the source-connector filter

- **Decided:** 2026-11-15, by the user ("fix anything you want"), after the renders showed hairline
  streaks crossing the model (`build/honoka-las/previews-new/diagnostic_front.png`, untracked).
- **Decision:** `build_honoka_las.py` drops every triangle with an edge over 20 cm
  (`LONG_THIN_MAX_EDGE_CM`), per slice, after the wrist cut. 26 source strip-break connector
  triangles were removed; no other geometry changed. `dist/Honoka_LAS.zip` and its sidecar were
  re-committed; `make honoka` installs the new bytes. The previous bytes stay in git history
  (`2e49f14`). `runtime_verified` stays `false`; no release, no other publication.
- **Why:** the streaks are in the source TMC (pairs of slivers with a ~0.2 cm root edge and a far
  apex), not a decode, winding or normals defect, so nothing in the pipeline could repair them; they
  had to be dropped. The threshold sits in an empty gap of the edge-length distribution (longest
  legitimate edge 13.4 cm; smallest stray 23.7 cm), so no real geometry is cut. The pack still cannot
  be `fresh`-verified (the builder never writes `dist/`, see D36); a double build in a separate output
  directory reproduced the new bytes exactly.
- **Status:** superseded by D40 (2026-11-15): the pack and its builder are deleted; the connector filter
  itself lives on in `tools/pd2-las/tmc_las.py`.

### D38 — In-game menu captures were supplied for Honoka and both Christie packs; the HANDOFF table is the truth for what was in game

- **Decided:** 2026-11-15, by the user, who supplied six in-game screenshots and asked for the repository
  to be updated.
- **Decision:** `docs/renders/in-game-2026-11-15/` archives the six captures byte-identically with a
  `README.md` and a `manifest.json` (dimensions, sizes, SHA-256). They are all the outfit-menu
  armor-skin preview, not a heist: `Honoka_LAS` (the tracked pack, confirmed by the user),
  `Christie_LAS_Slim` with the white LAS gloves spawned, and full `Christie_LAS` with Christie's own
  hands — the Christie build identification is the user's, not hash-measured from the captured bytes.
  `docs/pd2-las/HANDOFF.md` (*Seen in game*) records all three packs as seen in game on 2026-11-15 and
  is the authority on what ran. `runtime_verified` in every pack's `BUILD_INFO.json` stays `false`
  (D31) — the flag is a builder constant, and the tracked pack bytes were not rebuilt or touched.
  Lobby/heist behaviour, the inner elbow under a rifle, movement, the cuff/glove stack in every pose
  and the crash logs remain open (`docs/pd2-las/in-game-checklist.md`). No release, no other publication.
- **Why:** the screenshots are the only in-game evidence that exists; deleting or ignoring them would
  leave HANDOFF saying "no record" for packs the user just ran. Archiving them with the install state the
  user reported keeps the record honest without pretending the checklist is done.
- **Status:** holds in part (the HANDOFF record stays); the archived captures were removed by D39
  (still reachable at `da891d7` in git history).

### D40 — The TMC-only Honoka pack is deleted; the `.dae` build (`Honoko2`) is the one that stays

- **Decided:** 2026-11-15, by the user: "delete Honoka_LAS.zip ... and tool and references to it.
  Honoko2.zip is much better — it was built from dae. keep it and upload screenshots that was made with it".
- **Decision:** `dist/Honoka_LAS.zip`, its `.sha256` sidecar, its builder (`build_honoka_las.py`), the
  `honoka` make target and that pack's renders and README are deleted; a decision, not a rebuild, so the
  bytes stay reachable in git history (`ce1d1c0`, and `2e49f14` before it). The handful of helpers the
  kept `.dae` builder still needs — the TMC frame map and bind matrices, the wrist cut, the long-thin
  triangle filter and the fallback icon — moved to `tools/pd2-las/tmc_las.py` unchanged, so `Honoko2`
  keeps its bytes, its `honokodae` target and its `fresh` verification. The eight in-game captures the
  user made with `Honoko2` are archived byte-identically in `docs/renders/honoka/in-game/2026-11-15/`
  with a `README.md` and a SHA-256 `manifest.json`; `docs/pd2-las/HANDOFF.md` records the pack as seen in
  game on 2026-11-15 and remains the authority on what ran.
- **Why:** the user compared both builds in game and judged the `.dae` one better. It keeps the six
  material slots the Collada export binds (body, suit, panties, bra, shoes, jewelry) and the buttoned
  suit, where the TMC build merged the raw meshes into three slots and overlaid the unbuttoned jacket
  shell on the buttoned one — the overlap that z-fights on the torso and back. Two packs of one costume
  also meant two builders, two sets of documents and a pack `fresh` could not verify (D36, D37); the
  worse one went.
- **Status:** holds. D36 and D37 are superseded. `runtime_verified` stays `false` in `Honoko2` (D31); the
  outfit-menu captures are the in-game record, not the flag.

### D41 — Hila's head packs are built from her own unit, and only they wear the supplied eye

- **Decided:** 2026-11-15, by the user ("make Miranda over Hila packs, both L4D and Romance version",
  and, asked which packs the attached `EYE_Diff.png` is for, "eyes of the new Hila packs").
- **Decision:** `dist/Miranda_L4D2/Miranda_L4D2_over_Hila.zip` and `dist/Miranda_Romance/Miranda_Romance_over_Hila.zip` are built by
  `_emit_hila_packages()` from `references/npc_criminals_ecp_female.7z`, the unit that ships the H3H3
  collaboration heister (DLC folder `ecp`): `g_head` (two atoms: head, 3D eyelashes) is replaced and the
  hair drawables `g_hair_mask_off` / `g_hair_mask_on` are collapsed to the hidden triangle and disabled
  in both object files, as for Sydney. The head material group runs `mtr_head` + the unit's own
  `mtr_lashes`. The eye quadrant of these two packs is the user's `references/EYE_Diff.png`
  (`load_hila_eye_texture()`); the nine other head packs do not read that file and stay byte-identical
  (the eight Miranda ones keep the synthesised eye, Geralt keeps Rust's own).
- **Why:** Hila is not in `Heister - FPS Gloves in TPS 2.zip` and has no Safe House (`*_chill`) unit, so
  her heist and menu models come from her own archive and no Safe House swap exists to emit. Her
  `mtr_head` is authored against a `*_head_gsma` gloss map for her own UVs, which the head atlas does not
  have, so the material becomes the same plain `DIFFUSE_TEXTURE:NORMALMAP` template the other heisters
  use and reads gloss from the diffuse alpha. The supplied eye is a 256x256 spherical eyeball map whose
  iris is small in the frame, while both pipelines re-project the eyeball as a planar pass over the
  palpebral opening, so it is magnified about its centre by a factor measured off the source - 2.8 for
  the first diffuse, 2.03 for the same day's repaint, whose iris is drawn 1.38x larger - to put the iris
  where the synthesised eye had it (r 0.156 of the quadrant in u,v, inside the 0.174 gloss iris disc, an
  ~11.7 mm iris in a ~30 mm opening; D43).
- **Carried by:** `references/EYE_Diff.png` and `references/npc_criminals_ecp_female.7z` are tracked, and
  `references/README.md` describes both.
- **Held to:** `tests/test_pd2_las.py::TestLasScaffold::test_hila_packs_replace_the_ecp_unit_and_use_the_supplied_eye`
  fails if the eyelash atom leaves `mtr_lashes`, if a hair drawable stays enabled, if `mtr_head` regains
  the GSMA slot, or if the eye quadrant stops being the supplied diffuse.
- **Source:** the user, 2026-11-15; `references/README.md`.
- **Status:** holds, as amended by D43: the same day's repaint of the supplied diffuse re-measured the
  zoom factor, and corrected the count of the other head packs above.

### D42 — `Honoko3` is `Honoko2`'s mesh scaled 5% about the rig's bones; both packs ship

- **Decided:** 2026-11-15, by the user ("make Honoko3 zip from dae with a bit smaller model — check
  screenshots"), who, asked what "smaller" means, chose *slimmer at the same height*, *~5 %*, and
  *keep both packs*.
- **Decision:** `tools/pd2-las/build_honoko2_dae.py` is driven by a `PackSpec` and `PACKS =
  (HONOKO2, HONOKO3)`: one build of the same Collada input, the same six materials, textures,
  registration, glove adapter and icon, writes `dist/Honoka/Honoko2.zip` and `dist/Honoka/Honoko3.zip` (plus
  sidecars) from one `make -sC tools/pd2-las honokodae`. `HONOKO3.slim = 0.95` is the only difference
  in geometry. The pass is `_slim_groups()`, after the wrist cut and its caps: every vertex is moved
  toward the weight-blended rest position of the bones in its palette —
  `out = anchor + 0.95 * (v - anchor)` — and the outfit is then re-seated so its lowest vertex is back
  at `z = -0.47`.
- **Why anchor the offsets instead of scaling the mesh:** the game animates the outfit through the 2B
  skeleton, so joints must stay where the rig puts them. Scaling in world space (or of the skinned
  bind pose) would drop the collar off the heister's head, leave the wrist cuts short of the vanilla
  gloves, move the feet off the floor and change bone lengths. Anchoring per bone, weighted the way
  the skin weights are, keeps height, joint placement, sleeve and skirt hems in place and shrinks
  only the distance from the bones: the girth.
- **Measured (built bytes, `dmodel` on the packed `.model`, both 31 577 vertices):** height
  167.76 → 167.43 cm, soles at `z = -0.47` in both, bbox depth 41.37 → 39.28 cm (**-5.05 %**, the
  factor), bbox width 97.46 → 96.60 cm (the arms are anchored at the shoulder and elbow bones, so
  their span barely moves). Per-slice widths through the torso read -3 to -6 %; the single +9.6 %
  slice at z = 140 and the -61 % depth at z = 60 are the crude ±1.5 cm windows catching the sleeve
  cuffs and the skirt hem at different heights, not geometry that grew. `dist/Honoka/Honoko2.zip` is
  byte-identical to the tracked pack after the refactor (`c56a76a3…`);
  `dist/Honoka/Honoko3.zip` is `e967cea4…`, 5,468,049 B.
- **Also:** `tools/render_mod_previews.py` renders `18_Honoko3.png` and puts both packs in the 18-cell
  `dist/` overview; `status.py` maps both names to `honokodae`; the tracked-zip count in the docs, the
  CI job and the tests goes 19 → 20 (18 packs), and the one-call `status` budget 2 KiB → 2.5 KiB, because a
  pack costs ~90 bytes of that JSON and the 17-pack output already sat at 2,015 of the 2,048.
- **Carried by:** `dist/Honoka/Honoko3.zip{,.sha256}`, `tools/pd2-las/build_honoko2_dae.py`,
  `docs/renders/honoka/model/dae/honoko3_las_sheet.png`.
- **Held to:** `tests/test_pd2_las.py::TestLasScaffold::test_honoko3_is_honoko2_slimmed_about_the_bones`
  (vertex count unchanged, height within 1 cm, soles at -0.47, palette unchanged, `slim` reported as
  0.95) and `tests/test_pd2_las_status.py` (both packs, one target).
- **Source:** the user, 2026-11-15; D40.
- **Status:** holds. Nothing of `Honoko3` has been in game; the in-game record stays `Honoko2` (D40).

### D43 — The supplied eye is repainted; the two Hila packs rebuild at a re-measured zoom

- **Decided:** 2026-11-15, by the user, attaching a 256x256 repaint: "Chance EYE_Diff.png to this one and
  rebuild Miranda over Hila packs".
- **Decision:** `references/EYE_Diff.png` becomes the repaint (the first diffuse stays in git history),
  `HILA_EYE_ZOOM` goes 2.8 -> 2.03, and `dist/Miranda_{L4D2,Romance}_over_Hila.zip` rebuild from it with
  fresh sidecars. Nothing else reads the file: the nine other head packs come out of the same
  `make heads` run byte-identical.
- **Why:** the repaint keeps the veined sclera and redraws the iris - rounder, with a catchlight, and
  1.38x the area-equivalent radius of the first diffuse (hole-filled blue-plus-limbal mask: r_eq 14.24
  -> 19.63 px of 256). The zoom is a measurement, not a preference: it exists to land the source iris at
  the radius the synthesised eye uses in the quadrant (r 0.156 in u,v, inside the 0.174 gloss iris disc).
  At the old 2.8 the repaint's iris would land at r 0.215 - an iris 1.38x too large in game, spilling out
  of its gloss disc - so the factor is the old one divided by the measured iris ratio (2.8 / 1.3788),
  and the in-game eye keeps its calibrated size while wearing the new art.
- **Carried by:** the swapped `references/EYE_Diff.png`, the `HILA_EYE_ZOOM` comment in
  `tools/build_joy_head_mods.py`, the rebuilt sidecars, and the renders in
  `docs/renders/miranda/model/over-hila/`.
- **Held to:** the D41 test, which rebuilds the expected quadrant from the reference at test time and so
  pins the new bytes without an edit; `make -sC tools/pd2-las green` rebuilds all 20 tracked zips and
  holds these two to the new sidecars and the other 18 to the old bytes.
- **Source:** the user, 2026-11-15.
- **Status:** holds.

### D44 — Honoko4 is Honoko3 in the user's alternate suit; Honoko3/4 open the layer gaps the
        close-ups showed

- **Decided:** 2026-11-15, by the user, attaching four in-game close-ups and the texture
  `references/Honoka/Tex_07(L_7) 2.dds`: "aply Tex_07(L_7) 2.dds texture ... to costume of Honoko3 and
  make it Honoko4? Also, any recomendations for the neck and nose? those recomendation you can aply to
  Honoko3 and Honoko4".
- **Decision:** `honokodae` builds a third pack: `Honoko4` is `Honoko3` vertex for vertex (same slim,
  same clearance pass) with the suit slot's diffuse read from the supplied alternate colourway (black
  jacket, orange shirt; `L_8.dds` stays its normal map). `Honoko3` and `Honoko4` are additionally built
  with `_clearance_pass`: the torso and neck skin sinks 2 mm along its own normals and the bra 0.5 mm,
  and their shadow-caster drawable drops the bra and panties shells. `Honoko2` keeps the old build, so
  its tracked bytes stand and the fix is scoped exactly where the user put it.
- **Why:** measured on the built mesh, the shells the flakes came from stood 0.2 mm (bra to skin),
  0.7 mm (necklace to skin) and 3.6 mm (collar to skin) apart, and the slim pass pressed each pair
  together a little more, which is why the close-ups of Honoko3 show what the Honoka captures of
  2026-11-15 do not. At those gaps the depth test and the shadow map alternate between the two
  surfaces and the engine draws one shell's unlit inside through the other; the fully enclosed bra and
  panties shells added nothing to the silhouette but did write shadow-map depth through them. The
  neck needed no geometry of its own: with the centroid axis measured, the pack's neck plug nests
  inside the head unit's neck and hair at every height, and the flakes on the throat were the same
  contact phenomenon at the collar. The nose in the close-ups is the Miranda head unit's, not this
  pack's: the body ends in a neck plug at z 167 and carries no head geometry, so nothing here can
  change it (the head packs are the place for that, and the user scoped this work to Honoko3/4).
- **Carried by:** `dist/Honoka/Honoko4.zip` + sidecar, the `clearance` block of both packs' `BUILD_INFO.json`,
  `honoko4_las_sheet.png` and the 19-pack `dist/` overview.
- **Held to:** `tests/test_pd2_las.py::TestLasScaffold::test_honoko4_is_honoko3_in_the_alt_suit` (the
  geometry is Honoko3's, the suit diffuse is the supplied file, every other slot is unchanged) and
  `...test_honoko3_and_4_open_the_layer_gaps_and_trim_the_shadow_caster` (>= 1 mm at every measured
  contact, four shells in the trimmed shadow caster, six in Honoko2's).
- **Source:** the user, 2026-11-15.
- **Status:** holds.

### D45 — Honoko5: the third colourway of the same slim build

- **Decided:** 2026-11-16, by the user: "Tex_07(L_7)3 - change texture to the costume, make honoko5,
  render agai with a head".
- **Decision:** `references/Honoka/Tex_07(L_7)3.dds` (uploaded to `main` as `7ea708e`, carried onto this
  branch) becomes the suit slot's diffuse of a fourth pack: `Honoko5` is `Honoko3`'s geometry vertex for
  vertex (same slim, same clearance) in the white-jacket-over-black-shirt colourway, and it is rendered
  both on its own sheet and combined with `Miranda_Romance_over_Hila`'s `g_head`, as Honoko4 was.
- **Why:** the same reason as D44: a colourway is a diffuse swap on one slot, not a new build - the
  geometry, the slim and the clearance passes are shared, and `BUILD_INFO.json` records which source
  DDS each slot's textures came from, with its sha256, so the pack carries the proof of its colourway.
- **Carried by:** `dist/Honoka/Honoko5.zip` + sidecar, `honoko5_las_sheet.png`,
  `honoko5_with_miranda_romance_over_hila_sheet.png`, the 20-pack `dist/` overview.
- **Held to:** `tests/test_pd2_las.py::TestLasScaffold::test_honoko4_and_5_are_honoko3_in_the_alt_suits`
  (both packs' geometry is Honoko3's, each suit diffuse is its supplied file, every other slot is
  unchanged) and the clearance test, which now covers Honoko5 as well.
- **Source:** the user, 2026-11-16; `references/Honoka/Tex_07(L_7)3.dds` via `main` @ `7ea708e`.
- **Status:** amended by D46: the user revised the source and Honoko5 was rebuilt.

### D46 — Revised Honoko5 colourway and Miranda nostril normals

- The user replaced `Tex_07(L_7)3.dds` on `main` at `526480e` and requested Honoko5 be redone.
  The updated suit diffuse is black jacket over light shirt; Honoko3 geometry and clearance remain unchanged.
- Nose diagnosis: comparing offline close-ups with the original face diffuse showed the diffuse alone
  did not remove the dark splotches. The head builder's broad, strongly downward nostril vertex-normal
  override affected the visible nose wings. Remove that override while retaining the repaired source
  normals and UV-pocket cavity treatments. Both Miranda variants and their heister packs are rebuilt.
- Verified in offline frontal and three-quarter renders, not yet in game. The renderer does not simulate
  PAYDAY 2 normal-map lighting, so in-game appearance still needs checking. The neck remains unchanged.

### D47 — Group shipped packs and consolidate source archives

- The user requested character folders inside `dist/`, including a separate `Geralt/`,
  and moved the source archives from `models/` into `references/` (superseding D14).
- The three full-body ZIPs are now `Miranda_L4D2_LAS.zip`,
  `Miranda_L4D2_Busty_LAS.zip`, and `Miranda_Romance_LAS.zip`; their internal mod
  folder names and ZIP bytes are unchanged. The builders, status, previews, checksums,
  CI and release workflow use the new paths. Shared tools remain in `tools/`.

### D48 — Match Romance-over-Hila head skin closer to the Honoko body

- The user asked to bring the head texture colour closer to the body. The active combination is
  Honoko5 and Miranda Romance over Hila. Their exposed upper-neck texture samples differed markedly;
  the builder applies a deterministic, skin-colour-masked RGB gain to the face/scalp quadrants of the
  Romance Hila atlas only. Hair, eyes, gloss alpha, normal maps and all geometry are unchanged; the
  Hila character icon is regenerated from the adjusted atlas. Other head packs are not changed.
- The tint is part of the Hila head pack, so it also appears when that head is used with other bodies.
  The head/body crossing is still geometry, and lighting differs across it: the adjustment reduces
  a colour mismatch rather than promising a seamless join. The result remains an offline render until
  the combination is checked in game.
- `tests/test_hila_skin_tone.py` checks the mask, unchanged eye/gloss and hair, and that sampled neck
  diffuse colours move closer to the Honoko5 body. `honoko5_head_skin_detail.png` shows two angles.

### D49 — Christie is rebuilt from source without head or hands; `Christie_LAS_Slim` is removed

- **Decided:** 2026-11-15/16 (`6f10770`, `632e25d`)
- **Decision:** `tools/pd2-las/build_christie_source.py` (`make -sC tools/pd2-las christie`) rebuilds
  `dist/Christie/Christie_LAS.zip` deterministically from `references/Christie.zip` onto the 2B PD2
  skeleton (`christie_fit_probe.py`, `christie_sleeve_gloss.py`) with head and authored hands cut off,
  registering `BODY_ONLY` + `glove_adapter.lua` alongside both third-person and first-person arm units.
  `dist/Christie/Christie_LAS_Slim.zip` (and its orphan model render) is removed at the user's request;
  its bytes remain reachable in git history.
- **Status:** holds.

### D50 — `Honoko5` fit/jewelry updates, `Christie_Clover_LAS` GLB outfit, and archived menu captures

- **Decided:** 2026-11-16..18 (`632e25d`, `d791361`)
- **Decision:** `Honoko5` adds targeted waist/hip/cuff clearance adjustments plus `Tex_07(L_7)3.dds`
  (suit) and `Tex_23(L_23)2.dds` (jewelry) diffuses (`build_honoko2_dae.py`), while
  `tools/pd2-las/build_clover_christie.py` (`clover_christie_glb.py`) builds an experimental TPP-only
  `BODY_ONLY` outfit `dist/Christie/Christie_Clover_LAS.zip` from the Christie primitives in
  `references/Clover-Christie.zip`, preserving glTF's OpenGL Y+ normal-map green channel (`corr > +0.99`
  against `Christie_LAS`) and full `BUILD_INFO.json` registration metadata. Offline model sheets for all
  20 packs live under `tools/render_mod_previews.py --unified`. User-supplied menu/lobby captures of
  `Christie_LAS` and pre-jewelry `Honoko5` are archived under `docs/renders/christie/in-game/2026-11-15/`
  and `docs/renders/honoka/in-game/honoko5/2026-11-15/`. `runtime_verified` stays `false` (D31).
- **Status:** holds.

### D51 — `dist/` is the sole tracked home for built zips; duplicate `build/pd2-las/*.zip` copies removed

- **Decided:** 2026-11-16 ("clean everything")
- **Decision:** the duplicate force-tracked archives `build/pd2-las/Miranda_LAS.zip` and
  `build/pd2-las/Miranda_Busty_LAS.zip` (and their `.sha256` sidecars), which duplicated
  `dist/Miranda_L4D2/Miranda_L4D2_{LAS,Busty_LAS}.zip` byte for byte inside gitignored `build/`, are
  untracked and removed. `dist/` holds all 20 tracked packs and sidecars; `build/*` is purely scratch.
- **Status:** holds.

### D52 — Honoko5 and Miranda Romance directly replace Hila

- **Decided:** 2026-11-18, by the user (body and head over Hila, explicitly not LAS).
- **Decision:** `dist/Honoka/Honoko5_Miranda_Romance_over_Hila.zip` is built by
  `tools/build_hila_body_mod.py` from the assembled `Honoko5` and `Miranda_Romance_over_Hila` ZIPs.
  Only `g_body` and `s_body` mesh blocks change on the Romance Hila model. The head, native hands,
  root, bones, attachments, and both object definitions are unchanged. There is no FPS or unit override.
- **Fit:** every weighted donor bone is resolved by hash on Hila's skeleton. Her knees sit ~2.4 cm
  farther back than the donor bind; the mesh follows that offset locally. A roughly 4 cm gap at the
  bare wrist cut required a tapered extension. The rim overlaps the unchanged gloves and follows
  the same hand bone so it doesn't pull apart when the hand rotates. The trimmed body caster gains
  the solid head and glove silhouettes on the existing one-weight shadow shader.
- **Why native:** `hila_texture_atlas.py` packs the six diffuse/normal pairs into Hila's existing
  `*_suite_df`/`*_suite_nm` slots. It preserves the wrapped UV islands and copies the donor BC3 blocks
  while the atlas gutters align. No new texture registration, Lua, LAS, or BeardLib is needed. Both
  material configs use the outfit's diffuse/normal shader on `mtr_suite_body`, not the old suit GSMA.
- **Held to:** `tests/test_hila_body_override.py` checks the ZIP and fit; `fresh.py` rebuilds this pack
  after its donors. The [compiled-model preview](../renders/honoka/model/over-hila/README.md) is offline;
  masks, armor, animation and performance are still unverified in the game.

## Environment, tests and documents

### D14 — Inputs live in `models/` and `references/`

- **Decided:** 2026-10-20 · `94bb4b0`
- **Decision:** source models are in `models/`, reference mods in
  `references/`. One source sits among the references.
- **Why:** not recorded beyond the commit subject ("organize").
- **Source:** `94bb4b0`; the former `models/README.md`, `references/README.md`
- **Status:** superseded by D47.

### D15 — The 2B templates are unpacked into `build/pd2-las/2b/`, never committed unpacked

- **Decided:** 2026-11-11, by the user · supersedes `/tmp/2bsrc`, where the
  archive had been unpacked until then
- **Decision:** `extract_2b.py` unpacks `references/2b.rar` into
  `build/pd2-las/2b/` and is the only place that path is written
  (`extract_2b.TEMPLATES`). The builders' `--templates` default,
  `status.py`, the diagnostics and the tests import it.
  `PD2_2B_TEMPLATES` overrides it for a second checkout.
- **Why moved:** `/tmp` does not outlive a session and does not exist on
  Windows, and the old path was written out in about thirty files, so every
  fresh session began with commands that pointed at nothing.
- **Why not committed unpacked:** it is somebody else's mod. The directory is
  gitignored, and a test checks that it stays so.
- **Why node-unrar-js:** the archive is RAR5 and the sandbox has no `unrar`,
  `7z` or `bsdtar` (`cba4688`, 2026-11-09). The repository carries that
  package at its root, so the extraction needs no network.
- **Still naming the old path:** the dated audits and the older MODLOG
  entries. They are records of their day and were left as written.
- **Source:** `tools/pd2-las/extract_2b.py`;
  `tests/test_pd2_las_status.py::test_the_2b_templates_have_one_home_inside_the_repo`
- **Status:** holds.

### D16 — Skips have a budget

- **Decided:** 2026-11-10 · `0a76215`
- **Decision:** `tools/pd2-port/check_skip_budget.py` allows each known skip
  reason a maximum count, and any new reason or any growth fails
  `check_all.py --full`. The reason for missing 2B templates has a budget of
  zero.
- **Why:** one unconditional `pytest.skip` inside a helper had switched off
  37 tests, and a missing fixture silenced 68 without any test failing.
- **Extended:** 2026-11-11 — the same tool budgets expected failures
  (`xfail`), for the same reason: one line may not hide a defect.
- **Source:** the docstring of `check_skip_budget.py`; `cba4688`
- **Status:** holds.

### D17 — The README is the entry point and carries no dates

- **Decided:** 2026-11-11, by the user
- **Decision:** `tools/pd2-las/README.md` holds status (as a command),
  commands, the file map, invariants, what not to do and what is next, in
  about 120 lines. Dated state goes to `HANDOFF.md`, the journal to
  `MODLOG.md`, reasons here, measurements to the packs' `BUILD_INFO.json`.
- **Why:** the README had grown to 320 lines, mostly journal, and
  contradicted itself: it called the models authored, listed model authoring
  as open, and showed `models_present=false` while every tracked pack says
  `true`.
- **Source:** `tests/test_pd2_las_status.py::test_readme_keeps_its_contract`,
  which enforces it
- **Status:** holds. D22 finishes it: the other two documents that acted as
  an entry point no longer do.

### D19 — Scratch and caches live under `build/`; nothing names a fixed temp path

- **Decided:** 2026-11-11 · asked for by the user ("move from tmp"); it
  extends D15 from the 2B templates to everything else
- **Decision:** no script, test or workflow reads or writes a fixed path under
  the system temp directory. Scratch that one run needs goes to pytest's
  `tmp_path` or to `tempfile`. Whatever a later run should find again goes
  under `build/`, inside the checkout and gitignored: `build/head-mods/` (the
  three archives `tools/build_joy_head_mods.py` unpacks),
  `build/pd2-port/preview/` and `build/pd2-port/shade/` (the default output of
  `preview_check.py` and `shade_check.py`).
- **Why:** the two reasons of D15: that directory does not outlive a session
  and is not a path on Windows. After the templates had moved, five places
  still used it: the head builder's extraction cache, a test that wrote models
  there only to read them back, a diagnostic that created a folder nothing
  used, and the default output of the two preview tools.
- **Why `build/` for the caches:** the head builder's three extractions are
  85 MB, and kept there a second run does not unpack them again. Two of the
  three archives are other people's mods, so they have to stay out of git; a
  test checks that the new directories are ignored.
- **Still naming that directory:** dated audits and older journal entries,
  left as written; `examples/aoe2-de-civ` and `examples/mindustry-homing`,
  where it is an output path the reader picks; two knowledge notes about other
  subjects; and prose that says the sandbox wipes it.
- **Source:**
  `tests/test_pd2_las_status.py::test_no_tool_or_test_depends_on_a_fixed_tmp_path`,
  which scans every tracked script, test and workflow and the entry documents
- **Status:** holds.

### D20 — The source inventory is tracked and says only what the source contains

- **Decided:** 2026-11-11 · the user's roadmap, item 7
- **Decision:** `tools/pd2-las/source_inventory.json` is in git: the source
  archive's hash, the VPK entries, both models' bones, meshes and triangle
  counts, each texture's format and size. Every stage of `build_las.py` writes
  the same record, and `make -sC tools/pd2-las inventory` rewrites the tracked
  copy. What a build adds, the hash of each converted texture, goes only into
  the pack's `BUILD_INFO.json`.
- **Why tracked:** the record existed only under `build/`, so reading how many
  bones or which textures the source has needed the venv and a build.
- **Why source facts only:** its content depended on the stage that ran last.
  The stages that convert textures added a `textures` section with build
  hashes; the others wrote none. A tracked file needs one right content.
- **Also fixed:** `--stage inventory` promised JSON on stdout and printed two
  progress lines before it; for that stage they go to stderr.
- **Proof that no pack changed:** both Miranda packs were rebuilt after the
  change and came out byte for byte the same.
- **Source:** in `tests/test_pd2_las.py`:
  `test_tracked_source_inventory_is_current`,
  `test_source_inventory_does_not_depend_on_the_stage`,
  `test_inventory_stage_prints_only_json`,
  `test_tracked_pack_embeds_the_tracked_source_inventory`
- **Status:** holds.

### D21 — Each invariant has one test, named after it, that reads the tracked packs

- **Decided:** 2026-11-11 · the user's roadmap, item 6
- **Decision:** `tests/test_pd2_las_invariants.py` holds one test per row of
  the README's Invariants table: Units, UVs, Winding, Skin, Atoms, Materials,
  Objects, Textures, Codec, Registration, Tracked bytes, Variants. A test's
  name starts with its row's name and its docstring opens with it;
  `test_readme_invariants_are_the_invariant_tests` keeps table and file the
  same list in the same order. The tests decode the packs in `dist/` with the
  codec alone: no build, no 2B templates.
- **Why:** the first four rows cited authoring tests that need the templates,
  so on a fresh clone and in CI those invariants had no running test. One name
  (`test_geometry_sane_and_winding_positive`) stood for two rows and four
  rows cited whole files, so a red test did not say which invariant broke.
- **Why on the tracked packs:** the bytes in git are the product (D9). A test
  on them runs everywhere, and it also notices a pack that was committed from
  a different tree than the code beside it.
- **What it does not replace:** the authoring suites (`test_build_models.py`,
  `test_bust_variant.py`) check the same properties in
  more detail, during a build.
- **How the thresholds were set:** every number was measured on the tracked
  packs first and stands beside its assertion. Each test was then run against
  mutated copies of the packs, held in memory: a mesh left in inches, a
  missing UV flip, one flipped triangle, atom indices counted from the block,
  diffuse alpha left at 255, an `AddFiles` line removed, and so on. 112
  mutations, each caught by the test it was aimed at; three controls stayed
  green. The tracked zips were not touched.
- **Four rows the table did not have:** Atoms and Materials were listed in
  `AGENTS.md` and in the old handoff but had no row; Textures had tests in
  three suites and no row; Objects was a rule in one docstring
  (`las_outfit_pack.render_object_xml`: the file lists exactly what the model
  has), which `las_pack.py` does not.
- **Two exceptions that were written down, and are gone.** Each was a set in
  the test file whose test failed when the set grew and when it shrank, so the
  list could not spread and could not outlive a fix (an expected failure is strict and
    bounded; no bare `xfail`). Both packs were rebuilt on 2026-11-11 and both sets were
  removed with the defects: D23 and D24.
  - `SINGLE_LEVEL`: `miranda_face_df` and `miranda_eyes` shipped one mip level
    where every other unit texture has the full chain.
  - `ABSENT_OBJECTS`: `fps_miranda_busty.object` listed `g_head` and
    `g_head_lod1`, and its model has no object of either name. The variant's
    builder drops the two disabled head drawables from the first-person model;
    `las_pack.render_object_xml` wrote a fixed list. In the 2B pack and in
    the other seven tracked units every `<object>` line has its object.
    Whether the game minds is not known: no Miranda pack has an in-game
    record. The pack was not changed at the time: a fix gives a tracked
    deliverable a new sha256, and that is the user's call. The user made it
    the same day (D23).
- **Source:** the docstring of `tests/test_pd2_las_invariants.py`
- **Status:** holds.

### D22 — One entry point: the README. `AGENTS.md` routes to it, `HANDOFF.md` is the dated record

- **Decided:** 2026-11-11 · the user's roadmap, item 4
- **Decision:** commands, status, the file map, invariants and open work for
  `tools/pd2-las/` are written in its README and nowhere else.
  - `AGENTS.md` and its two copies keep the table of deliverables, a "Where to
    start" table with one row per pipeline, what a restarted sandbox needs,
    and the engine facts that hold in every pipeline.
  - `HANDOFF.md` keeps what carries a date: the tracked bytes, what was seen
    in game and when, how the tracked bytes came about, the dead ends, and the
    claims it used to make that are no longer true.
- **Why:** three documents acted as the entry point and gave three different
  first commands: `bootstrap.sh` (retired since, D28) after a hard reset (`AGENTS.md`);
  `recover_env.sh --verify`, and a hard reset onto the branch of an earlier
  session (`HANDOFF.md`); `make env` (the README). The copies had drifted from
  the tree. On 2026-11-11 the handoff still said that the unit scale is
  exactly 2.54 (no code multiplies by it), that `s_body` draws 16
  out-of-bounds triangles (none in the tracked packs), that the suite cannot
  collect without the templates (it can) and that `pyflakes` is not clean (it
  is). A note at the top of the page corrected the text below it.
- **Where things went:**
  - quickstart, recovery, "Where things live" → the README's Commands and File
    map, which already had them;
  - "Do-not-break invariants" → the README's table and its tests (D21);
  - "Next actions" → the README's Next;
  - "Environment traps" → dropped: each note is in a docstring of the code it
    describes (`extract_2b.py`, `vpk.py`, `source_model.py`,
    `build_models.py`);
  - "Worktree state" → dropped: it described an uncommitted patch that has
    long been committed;
  - the fit rule for the body-only outfit in `AGENTS.md` → a line under the
    README's "Do not".
- **Corrected on the way, both in `AGENTS.md`:**
  - a normal map is not `R = G = B = ny`. Both writers put X in alpha and Y in
    green and fill red with 255 and blue with 0, and the Textures test holds
    the tracked packs to it;
  - the `ForeArm` does not flex about local Z. On the 2B skeleton local Y is
    the normal of the bind-pose bend and local X runs along the forearm, as
    as measured on the 2B skeleton on 2026-11-07.
- **Not kept:** `git reset --hard origin/<branch>` as a routine first
  command. It is right only when everything local is already on the remote;
  otherwise it discards unpushed work. `AGENTS.md` now says so.
- **Source:** `tests/test_pd2_las_status.py::test_pd2_las_has_one_entry_point`;
  `tests/test_las_pack.py::test_handoff_and_agents_quote_the_tracked_pack_bytes`
  for the handoff's table (every tracked zip, each with its own size and
  sha256)
- **Status:** superseded in part by D30 (2026-11-13): `AGENTS.md` has no copies, `HANDOFF.md` no longer
  quotes the tracked bytes, and the second test named above is gone. Superseded in part by D35 (2026-11-14):
  `HANDOFF.md` keeps the present state only.

### D23 — A unit's `.object` is written from the model beside it

- **Decision:** `las_pack.install_models` puts the two models into a pack and
  writes each `.object` from the drawables that model has. Both Miranda
  builders end on it. `las_pack.render_object_xml` without a model still
  gives the 2B list, which is what a scaffold without models needs.
- **Why:** `fps_miranda_busty.object` listed `g_head` and `g_head_lod1`, and
  its model has neither (D21). The file came from a fixed list; the model came
  from a builder that drops those two drawables. Nothing compared the two.
- **Two ways to make them agree, and why this one.** Remove the two lines, or
  keep the two head slots in the model, as the base pack and 2B do. What uses
  the unit decides, so it was read (2026-11-11):
  - the game spawns the outfit unit, links it, sets its material and enables
    it; it never asks it for an object by name
    (`lib/managers/criminalsmanager.lua` 468 to 500 in the decompiled Lua of
    update 214; `g_head` occurs in none of its 1,732 files);
  - BeardLib does the same in `Hooks/Items/PlayerStyleGloveHooks.lua` 372 to
    396 (commit `95eb1c0c`), and has no `g_head` either;
  - LAS maps `fps_unit` to the style's `unit` (`hooks/outfits/loader.lua` 8)
    and looks up objects by name only for the deployable bags of the
    character, each lookup guarded
    (`hooks/las_hooks/criminalsmanager.lua` 116 to 122, commit `b7c38c1d`).
  So nothing needs the head slots, and either way would do. The lines were
  removed because that changes one text file of 478 bytes and leaves the
  model, which has shipped since 2026-11-04, alone.
- **What files the game accepts show.** In the 34 units LAS itself ships and
  in both 2B units, every `<object>` line has a node in the model: none of the
  36 has the defect. A `culling_object` without a node does occur, once in LAS
  and once in 2B, so that kind is tolerated. Of the 15 first-person units of
  LAS, none lists `g_head`.
- **Not known:** what the engine does with an `<object>` line that has no
  node. It reads the file in native code, which is not in the Lua. The old
  pack was never run, and the fix does not need the answer.
- **Rejected:** keeping the head slots in the variant's first-person model.
  It would make that model the base pack's, byte for byte, which the Variants
  invariant would like; it is also a second change to a file nobody has seen
  in game, made for tidiness.
- **Source:** `las_pack.install_models`;
  `tests/test_pd2_las.py::TestLasScaffold::test_install_models_writes_each_object_from_its_model`;
  the Objects and Variants invariants;
  `docs/audits/2026-11-11-miranda-mips-and-object.md`
- **Status:** holds; not seen in game.

### D24 — The build encodes only what it changed, and its mip levels are judged as pictures

- **Decision:** three rules for the two Miranda textures the build does not
  simply convert.
  1. The repainted face keeps the source's blocks, at every mip level. Only
     the half of a block whose content changed is encoded again: colour where
     a texel's colour changed, alpha where its gloss did
     (`build_las.repainted_face_texture`). A lower level is the source's own
     level plus what the repaint added, averaged over each texel's area as
     light (`build_las.face_levels`).
  2. The eye texture is drawn, so every level is made here: the area average
     of the drawn eye, colour averaged as light, gloss as data
     (`build_las.mip_levels`), encoded with the pair search of
     `dds_encode.encode_bc3_texels` and with the iris counting sixteen times
     the sclera (`build_las.eye_weights`).
  3. Every level is held to limits written before it was measured
     (`mip_audit.LIMITS`): CIEDE2000 against the picture the level stands
     for, absolute error for gloss, and the colour of the iris. What the pack
     misses is a list in the same file, `KNOWN_MISSES`, and
     `tests/test_mip_audit.py` fails when the pack and the list disagree in
     either direction.
- **Why 1:** the build used to decode the whole face, repaint 2 % of it and
  encode all of it again as one level. That was a second lossy pass over
  every block, it threw the source's mip levels away, and the encoder wrote
  its alpha codes in the wrong order, so the gloss of 80 % of the blocks was
  scrambled inside the block (the worst texel off by 29 of 255). The module's
  own docstring said production textures are never re-encoded.
- **Why 2:** a block of DXT5 holds four colours on one line. From 64x64 down,
  a block of the eye holds pupil, iris, dark rim and sclera. The two encoders
  the repository had, and `quicktex` at its highest setting, spend the line
  on the sclera, and the iris of the 16x16 or the 8x8 level comes out grey.
  Those are the levels on screen from two to eight metres at 1080p. With the
  weights the iris is within 1.71 of the picture at every level.
- **Why the eye is drawn once and averaged**, where the task that asked for
  these levels said to draw it at each size: drawn again with one point per
  texel of a small level, the fibres of the iris fall between the points.
  Against a drawing with 16 points per texel of level 0, the average of one
  drawing stays within 1.66 in every texel of every level; a drawing per size
  is off by more than 13 in one texel of a hundred at 32x32, and its iris by
  11 at 4x4 (`mip_audit.eye_drawn_finer`, and the test named after it).
- **Why 3:** the first two attempts at these levels passed every test: the
  header was right, the payload was the declared chain, gloss was low. The
  tests asked whether the file was well formed, and the levels were grey.
- **What the limits are not.** They are not met everywhere, and they were not
  moved: levels 3 to 7 of the eyes miss the per-texel colour limits, as every
  encoder that was tried does on that picture. The list says so.
- **Rejected:**
  - generating the face's lower levels from its level 0 and encoding them
    whole: no closer to the ideal render than the source's own levels (mean
    CIEDE2000 1.31, 1.70, 2.30 at 2, 4 and 8 m against 1.24, 1.58, 2.25) and
    it re-encodes 21,847 blocks to change 487;
  - the shared helper `tools/pd2-port/dds.py` for the levels: it builds them
    from a decode of level 0, and its encoder gives the 16x16 iris
    (61, 55, 52);
  - an outside encoder in the build: `quicktex` is better than the pair
    search at 512 to 128 (mean 0.8 against 1.4), but a compiled dependency
    would decide the tracked bytes. It is the yardstick, in a separate
    environment, and nothing that ships is made with it;
  - an uncompressed eye texture, which would have no block error at all: a
    format no unit texture of any tracked pack uses, untested in game.
- **Source:** `docs/audits/2026-11-11-miranda-mips-and-object.md` (method,
  tables, the before/after render); `tools/pd2-las/mip_audit.py`;
  `tests/test_mip_audit.py`; `tests/test_pd2_las.py::TestMirandaTextures`
- **Status:** holds; not seen in game. In a still frame one level is closer
  to the ideal than eleven at every distance, and at 8 m the eyes come out
  grey-blue where one level shows them blue; what the levels are for is
  motion, which only the game shows.

### D25 — A pack built from another pack is rebuilt with it

- **Decision:** when `dist/Miranda_L4D2/Miranda_L4D2_LAS.zip` changes, the four
  `Miranda_L4D2_over_*` head packs are rebuilt and re-shipped in the same
  change.
- **Why:** `tools/build_joy_head_mods.py` takes the face, head and body
  textures out of that zip. Every tracked pack equals a fresh build (D9, and
  the README's "Done means"); a head pack built from the old face stops being
  one the moment the face changes, and the next full rebuild rewrites four
  packs nobody meant to touch.
- **How it came up:** the 2026-11-11 change was scoped to the two Miranda LAS
  packs. Rebuilding everything showed the four head packs move with them
  (the head atlas and the menu icon of each). The user was asked and chose to
  re-ship them.
- **Not done:** a head pack does not record which `Miranda_LAS.zip` it was
  built from, so nothing but a rebuild shows that one is stale.
- **Source:** `docs/pd2-las/HANDOFF.md`, "Head packs";
  `docs/audits/2026-11-11-miranda-mips-and-object.md`
- **Status:** holds.

### D26 — The tracked bytes do not depend on the CPU that builds them

- **Decided:** 2026-11-12
- **Replaces:** the first D26 (2026-11-11), which let a fresh build differ
  from the tracked pack in two named ways. That allowance and the comparison
  that implemented it (`fresh_check.py`) are deleted.
- **Decision:** a tracked zip is the tracked bytes on any x86-64 Linux
  machine with the pinned environment, and CI holds every one of the 16 to
  that with `sha256sum -c`, on its runner, with no tolerance
  (`make -sC tools/pd2-las fresh`). Four rules keep it so:
  1. A decision on a number that is zero in exact arithmetic gets a rule, in
     the code that takes it: the handedness of a tangent frame where the UV
     map gives none (`tangents.py`), and which of two fans with the same
     triangles fills a ring.
  2. What a file derives from other values in the same file is computed from
     those values as they are stored, with + - * / sqrt and exact sums:
     tangent frames, from the float32 positions, normals and UVs.
  3. A value that has been through sin, cos, exp, arctan2 or a power is
     rounded with a margin check that stops the build
     (`determinism.floor8`, `rounded`, `above`): what the build draws and
     repaints, and the mip levels made from it.
  4. What is left, float64 linear algebra that ends in a float32 of the
     geometry, runs on one declared code path: OpenBLAS's Nehalem kernels on
     one thread, numpy's x86-64-v2 loops, glibc asked for its plain math.
     Every builder restarts itself onto it, checks what numpy and OpenBLAS
     loaded and refuses to build otherwise (`determinism.enter`).
- **Why not rule 4 alone:** it would have made all 16 zips match, in a few
  lines. It would have left in every model a sign that rounding had chosen,
  and textures that the next numpy could redraw. Rules 1 to 3 hold on any
  code path; the code path is for what cannot be made to.
- **What rule 4 carries, measured:** with the code path left to the machine,
  the tracked packs differ in one or two normals whose component is
  zero up to rounding. Nothing else in any pack moves.
- **Where it ends:** x86-64 Linux. Elsewhere the declared code path does not
  exist and the builders refuse. glibc is asked and cannot be checked; no
  byte moved between its routines, or between glibc 2.36 and the runners'
  2.43. scipy, py7zr and the system's zlib are not pinned. `lawson_las`
  belongs to the other pipeline (D3), which does not enter the code path; it
  has not moved on any path or runner. The menu icons that are renders rest
  on the code path.
- **Rejected:** baking the drawn textures into tracked images (new binary
  sources, and the formula stops being the source of truth); rewriting the
  matrix code so that it needs no declared kernels; rounding what is drawn
  to the nearest byte, which changed the art (the build cut off, and still
  does).
- **Source:** `docs/audits/2026-11-12-cpu-independence.md`;
  `tools/pd2-las/determinism.py`, `tangents.py`, `fresh.py`;
  `tests/test_determinism.py`
- **Status:** holds.

### D27 — One writer for the files that register a pack

- **Decided:** 2026-11-12
- **Decision:** `main.xml`, the hook, the strings, the unit file, the glove adapter and the zip of every pack built in `tools/pd2-las/` are written by `las_outfit_pack.py`, and so is the zip of the head packs. What a pack chooses is a `Registration`: its flags (`WHOLE_CHARACTER` or `BODY_ONLY`), its units, its textures, the glove adapter. `las_pack.py` and `las_outfit_pack.py` each state it in a function called `registration`.
- **Why:** three copies gave the same bytes for the same pack but for those choices, measured on the four packs, so a fact learned about these files had to be written three times. The one line in which the hooks differed is no drift: a pack with a head says `replace_all`, a pack without says `replace_body`, and LAS drops the heister's head for the first.
- **Rejected:** the same writer for `lawson_las` (its files have another layout, which its tracked bytes carry); merging the writers of the `.object` and material files (they differ in what decides their content); keeping a second text of the glove adapter for the cancelled outfit (no build reached it).
- **Source:** `docs/audits/2026-11-12-tool-merge.md`; `tools/pd2-las/las_outfit_pack.py`; `tests/test_one_implementation.py`
- **Status:** holds.

### D28 — One environment script, and the pins are written once

- **Decided:** 2026-11-12
- **Decision:** `recover_env.sh` (`make -sC tools/pd2-las env`) is the only script that makes the environment. The versions of pillow and numpy are in `tools/pd2-las/pins.txt`: the script and both workflows install with it as their constraints file, and `status.py` reads it. `bootstrap.sh` is retired. What only it installed, lupa and sourcepp, is `recover_env.sh --extras`.
- **Why:** the two scripts made the same environment, 20 packages in the same versions, and four files wrote the two pins while a test kept them equal. One file cannot disagree with itself.
- **Rejected:** adding lupa and sourcepp to the default environment or to CI (that changes which tests run; it is reported in the audit instead); one file that fixes the whole list of packages (each place that installs keeps its own list, only the versions are shared).
- **Source:** `docs/audits/2026-11-12-tool-merge.md`; `tools/pd2-las/pins.txt`, `recover_env.sh`; `tests/test_pd2_las_status.py`, `tests/test_one_implementation.py`
- **Status:** holds.

### D29 — The idstring hash is written once; the two `.model` readers stay two

- **Decided:** 2026-11-12
- **Decision:** `tools/pd2-port/dmodel.py` takes `hash64` and the 13 tag numbers it shares from `tools/pd2-las/diesel_model.py`, and its unused `minv` is gone. The two readers themselves are not merged.
- **Why:** the hashes gave the same value on 20,261 inputs. The readers do not agree: `dmodel` does not undo the legacy shift of channel types and misreads 471 of 826 legacy geometry sections, while `diesel_model` cannot read the DODB container or the packed channels of `lawson_las`. One reader would change what `dmodel` returns, which is a fix and belongs in a change of its own.
- **Rejected:** merging the readers in the same change; merging the two writers of the DDS header (they agree on every tracked texture, and were the fourth job where three were allowed).
- **Source:** `docs/audits/2026-11-12-tool-merge.md`; `tests/test_one_implementation.py`
- **Status:** holds.

### D30 — One command per question, one instruction file, and no figure in a document that a command prints

- **Decided:** 2026-11-13
- **Decision:** `make -sC tools/pd2-las status` reports all 14 packs, each as `tracked`, `changed`, `broken`
  or `missing` against the commit. `env` puts back tracked files that are missing and ends with that status.
  `green` runs every check of the `test` workflow. A build target prints the state of what it wrote.
  `AGENTS.md` is the one instruction file: its table gives one command per question, `GEMINI.md` is the line
  that imports it, and there is no `CLAUDE.md`. No agent document quotes a size, a sha256 or a test count.
- **Why:** on eight ordinary questions the documents led to 26 calls and 114,895 bytes, and to 7 and 34,658
  afterwards. `status` reported four packs and `sha256_ok`, which compared a zip with a sidecar its own
  builder had just written. The instruction file was written three times, and the harnesses that read
  `CLAUDE.md` as well as `AGENTS.md` loaded it twice. Each rebuild meant editing four documents, under a test
  that required it.
- **Rejected:** a `CLAUDE.md` that imports `AGENTS.md` (Cursor's CLI, VS Code and Copilot CLI read both);
  writing lawson's `.sha256` from its make target (it is the one sidecar no builder writes, so the one whose
  check means something).
- **Source:** `docs/audits/2026-11-13-agent-entry.md`; `tests/test_agent_docs.py`,
  `tests/test_pd2_las_status.py`
- **Status:** holds. Supersedes D22 where it kept two copies of `AGENTS.md` and the tracked bytes in
  `HANDOFF.md`.

### D31 — `runtime_verified` is `false` in every pack

- **Decided:** 2026-11-13, by the user
- **Decision:** every builder writes `"runtime_verified": false`. The two packs whose flag said `true`
  were rebuilt for it: one line of `BUILD_INFO.json` in each, every other member byte for byte the same.
- **Why:** the flag said `true` from the 2026-11-05 test of the base pack on, in both packs and through every
  rebuild after it, while `HANDOFF.md` recorded that no tracked bytes of either pack had been in game. A
  constant cannot follow what a person saw; the handoff's table does.
- **Rejected:** leaving the flag and saying so in `HANDOFF.md` (done on 2026-11-11; the pack went on saying
  the opposite of the record).
- **Source:** the user, asked on 2026-11-13; `docs/audits/2026-11-13-agent-entry.md`
- **Status:** holds.

### D32 — No pack carries a redistribution restriction

- **Decided:** 2026-11-13, by the user
- **Decision:** no document says any more that the packs are for private use, that their sources are not
  cleared for redistribution, or that a public release is blocked. D4 is superseded. Gone with it: "Blocked:
  public release" and "Do not publish or redistribute the packs or their sources" in
  `tools/pd2-las/README.md`, the "release gate" item of `docs/pd2-las/in-game-checklist.md`, "not cleared
  for redistribution" in `tools/pd2-port/README.md`, and the sentence in the top-level `README.md`.
- **Why:** the user, on reading that sentence in the report of the agent-entry audit: "no mod has that
  restriction". The record had it as an inference, never as the owner's word: the route-change audit of
  2026-10-18 listed redistribution clearance as "open", D4 was reconstructed from that audit on 2026-11-11,
  and the sentence in `README.md` ("The sources are fan rips, so nothing here is cleared for
  redistribution") was written by the agent on 2026-11-13 from D4. The practice never followed D4 either:
  the repository is public, and the release workflow published the sibling pack `lawson_las` on 2026-10-19,
  the day after.
- **Not changed:** `CREDITS.txt` inside `lawson_las.zip` says "no redistribution permission is claimed"; it
  names the sources and is part of the tracked bytes, so changing it is a rebuild of the pack. The comment
  above `STATUS` in `tools/pd2-port/build_las_pack.py`, which writes that file, says the same. (Both went
  later that day: D34.) The rules
  under "What you ship" in `AGENTS.md` and in the skills are upstream's, for game files an agent extracts
  while modding any game; they stay. Publishing is still asked of the owner first, like any publishing.
- **Source:** the user, 2026-11-13; `docs/audits/2026-11-13-agent-entry.md`
- **Status:** holds.

### D33 — What is stale is deleted, not kept for later

- **Decided:** 2026-11-13, by the user ("Delete stale things"; which ones was asked and answered that day)
- **Decision:** five kinds of leftover went.
  - **The code of the cancelled Skyrim outfit** (D13 had kept it): `tools/skyrim-nif/` and its five pages
    under `docs/skyrim-nif/`; `build_skyrim_outfit.py`, `skyrim_materials.py`, `skyrim_retarget.py`,
    `skyrim_source.py`, `skin_texture.py` and `decimate.py` in `tools/pd2-las/`; the outfit's own
    registration and `write_pack` in `las_outfit_pack.py`; the command of `pose_preview.py`, which read
    that outfit's build directory, and the one of `preview_textured.py`, which looked every texture up
    under that outfit's file names and so drew any other pack untextured; and the tests of all of it.
    In `build_models.py`, the 39 functions that only that builder called, or nothing (the hand graft,
    the neck, collar, bust and sleeve passes, the hole cap, the redress), and two pieces inside functions
    that stay, both keyed on the outfit's material names: the shoulder stay for `jacket` in
    `transfer_group`, and the default targets of `extend_sleeves_to_wrist`. The file went from 3,543
    lines to 1,784.
  - **The release and the tags** of the sibling pack: `tools/pd2-port/STATUS.md`, "Released and tracked".
  - **Sixteen branches on GitHub**, fifteen of them merged session branches: `tools/pd2-port/MODLOG.md`.
  - **Five renders no page showed:** `docs/audits/2026-11-09-neck-arm/`. The one page that showed them,
    a repair plan, was deleted on 2026-11-10 (`0a76215`).
  - **Ten functions that nothing ran**, in modules that stay: `chest_extent` (`bust_variant.py`);
    `rgba_to_bgra_dds`, `set_dxt5_constant_alpha`, `attenuate_dxt5_alpha_by_block_mask` (`dds_encode.py`);
    `mat_apply_vec`, `mat_from_pos_rot_rows` (`diesel_model.py`); `_axis_to_camera`
    (`render_mesh_skeleton.py`); `repair_dxt5_texture`, `_encode_block`, `_rgb565` (`tools/pd2-port/dds.py`).
    Asked whether they should go, the owner answered with a question: "Are you sure they are not used?
    maybe it's the starting .py". They were measured, and deleted on the instruction above; shown the
    measurement, the owner confirmed: "yeah, delete those if Nothing runs them". In `tools/`, `tests/` and
    `um/` each name stood once, at its own definition (`_rgb565` also in `_encode_block`); under line
    coverage no test, no build of the 16 packs, none of the 26 recorded tools and no start of the five
    files ran a line of them; four had been called by the tools of October and lost those calls by
    2026-10-21, one served only one of those four, and five never had a caller. The measurement and the
    history: `docs/audits/2026-11-13-agent-entry/answers/`. `git checkout 4e15ed6 -- <file>` brings a file
    back.

    The same measurement saw two more functions run nowhere, kept at first because live code calls them.
    The owner's words were read as the test for those two as well, and one went by it:
    `diesel_model.compute_uv_directions`, with the constant only it used. It made every tangent frame
    until 2026-11-12; since `e5eb882` it was the fallback of `author_group_sections` for a group without
    one normal per vertex. No such group can be written: the geometry section declares a normal for every
    vertex, and written with fewer it cannot be read back. The builder now refuses such a group by name;
    for every group that can be written the bytes are what they were. The other stays: below.
- **Why:** a tool that cannot run and a test that can only skip look like coverage and are none: 21 of the
  suite's 29 skips were tests waiting for the outfit's archive, removed on 2026-11-05, or for its pack.
  A release that serves an older build under the same version number tells an installer the wrong thing.
- **Kept, because someone runs it:** `render_source`, the `--source` mode of `render_mesh_skeleton.py`. No
  test and no recorded tool runs it; a person does.
- **Kept, because something else uses it:** `las_outfit_pack.py` writes the registration files of the LAS
  packs; `preview_textured.py` and `pose_preview.py` are what `glove_check.py` and `pose_zoom.py` render
  with; `build_models.extract_bones` and `extend_sleeves_to_wrist` stay. The tests of those functions that
  sat in the outfit's test files were kept and now run on what exists: `tests/test_las_outfit_pack.py`,
  `tests/test_build_models.py`, and `tests/test_glove_adapter.py` with `tests/test_glove_behavior_lua.py`
  on a synthetic body-only outfit.
- **Held to:** no tracked pack moved by a byte (`make -sC tools/pd2-las fresh`), after the outfit's code
  went, after the ten functions went, and after the fallback went.
  `test_a_group_without_a_normal_for_every_vertex_is_refused` fails when such a group is written again.
- **Where it is:** `git show 19ca55a:<path>` has every deleted file as it last was on `main`. What the port
  taught is in `knowledge/games/payday-2/las-moog-outfit-porting.md`.
- **Source:** the user, 2026-11-13; `tools/pd2-las/MODLOG.md`
- **Status:** holds.

### D34 — `lawson_las` ships no `CREDITS.txt`

- **Decided:** 2026-11-13, by the user ("CREDITS - remove", asked whether its wording should change). Read
  as: the whole file goes, not only its sentence about redistribution.
- **Decision:** `tools/pd2-port/build_las_pack.py` no longer writes `Lawson_LAS/CREDITS.txt`, and the pack
  was built again without it. `check_guide_compliance.py` lost check `N2`, which looked for that file, and
  the comment above `STATUS` in the builder lost "not cleared for commercial redistribution".
- **Why:** the file said "this is an unlicensed, non-commercial fan derivative and no redistribution
  permission is claimed". It was the last place where a pack carried the restriction D32 removed. No other
  tracked pack has such a file.
- **What the pack still says of itself:** `build_manifest.json` names the source archive with its sha256 and
  says `"runtime_verified": false`; the menu description says "Mass Effect 2 outfit". Where the model comes
  from is under "Status and limits" in `tools/pd2-port/README.md`.
- **Consequence:** the tracked pack has 29 files where it had 30. The 28 others are byte for byte what they
  were, and the manifest lost one line. The version stays 0.1.2: `VERSION` moves with a release ("Publish a
  release" in `tools/pd2-port/README.md`), and there is none.
- **Held to:** `test_pack_layout_matches_2b_contract` fails when the builder writes a credits file again.
- **Source:** the user, 2026-11-13; `tools/pd2-port/MODLOG.md`
- **Status:** holds.

### D35 — The project's self-description starts from the present

- **Decided:** 2026-11-14, by the user (a clean slate, after the removal of the deleted packs' tooling)
- **Decision:** `HANDOFF.md` keeps the present state only: which bytes are tracked (by command, never by a
  quoted size), what was seen in game and when, the rebuild rule for the packs that can be rebuilt, and the
  dead ends. The dated narratives of how the tracked bytes came about and the table of claims that earlier
  copies made are removed. `tools/pd2-las/MODLOG.md` is reset to a fresh-start entry; the text of the removed
  entries is in git (`git log -- tools/pd2-las/MODLOG.md`). `DECISIONS.md` stays, with no name for the
  deleted packs' tooling.
- **Why:** the owner wanted a clean slate for the project's self-description. The dated archaeology
  duplicated `docs/audits/` and git history and no longer described the present.
- **Status:** D22's description of what `HANDOFF.md` keeps is superseded by this entry; the rest of D22
  holds.

### D39 — Unified rules for renders (`docs/renders/<project>/<ext>/...`); old tracked renders deleted

- **Decided:** 2026-11-15, by the user ("unify rules for renders", `docs/renders/<project>/<ext>/...`,
  and "Delete old" for existing renders).
- **Decision:** `docs/renders/` is the single tracked home for renders and in-game captures, structured
  as `docs/renders/<project>/<ext>/[<variant-or-scope>/][<YYYY-MM-DD>/]`, where `<project>` is the mod
  or character slug and `<ext>` is the source/asset format extension (or `in-game/` for live captures).
  All pre-existing tracked renders (`docs/previews/`, `docs/pd2-las/renders/`,
  `docs/renders/christie-2026-11-14/`, and `docs/renders/in-game-2026-11-15/`) were deleted (reachable
  in git history at `da891d7`). Scratch and per-build previews stay gitignored under `build/`.
- **Why:** tracked renders had split across `docs/previews/`, `docs/pd2-las/renders/`, and ad-hoc dated
  subdirectories under `docs/renders/` with inconsistent naming and stale snapshots.
- **Held to:** `tests/test_render_rules.py` fails on legacy render directories, tracked renders outside
  `docs/renders/`, or files inside `docs/renders/` that break the `<project>/<ext>/...` layout.
- **Source:** `docs/renders/README.md`; `tests/test_render_rules.py`.
- **Status:** holds.

### D53 — `OfficeSuite` ships a first-person arms unit

- **Decided:** 2026-11-22, by the user ("make FPS model for hands" for `OfficeSuite.zip`)
- **Decision:** `OfficeSuite` alone (the other three packs stay byte-identical) additionally ships
  `fps_officesuite.model` from the same slimmed, cleared outfit arms, cut at the wrist with the heister
  gloves spawning on top (`glove_adapter.lua` unchanged), registered with an `fps_unit`,
  `DEPTH_SCALING` materials and no head, the Christie pattern. The third-person body, the jewelry pass
  and the registration flags are unchanged; `Honoko2`..`Honoko4` reproduce their previous bytes.
- **Why:** the pack had `fps_replace_body` with no `fps_unit`, so LAS first-person had nothing of the
  outfit: the first-person view kept the heister's vanilla arms, not the outfit's sleeves. The
  slot list of the arms is the arm-weighted jewelry (the cuff) and bra straps, not the chest jewelry.
- **Held to:** the invariants (`tests/test_pd2_las_invariants.py`, `_stems`) read the `fps_officesuite`
  model; `fresh` rebuilds and compares the tracked bytes.
- **Source:** `tools/pd2-las/build_honoko2_dae.py`
- **Status:** holds, except where the cut is named: the arms unit is cut where the palm begins since
  D59 (not at the wrist as written above), and it registers the adapter again.

### D54 — `Honoko5` is renamed to `OfficeSuite`

- **Decided:** 2026-11-22, by the user ("change the name of Honoka5.zip to OfficeSuite. And change
  description to 'OfficeSuit \[LAS\]'", later confirmed as "OfficeSuite everywhere")
- **Decision:** the pack is renamed end to end — the ZIP (`OfficeSuite.zip`), the registration id
  (`LegendaryArmours.officesuite`), the hooks (`officesuite_las.lua`,
  `officesuite_glove_adapter.lua`), the unit paths (`units/officesuite/skins/officesuite/`), the
  material slots (`officesuite_<kind>`) and the fps stems (`fps_officesuite`), the localization keys and
  strings (`bm_askn_officesuite`, description `OfficeSuite [LAS]`, menu name `OfficeSuite`), and the
  native Hila override it feeds (`OfficeSuite_Miranda_Romance_over_Hila.zip`, the body donor it reads).
  The tracked zips are rebuilt, so the 2026-11-18 jewelry/colors/clearance bytes are the same.
  The third-person geometry, scale and clearance are untouched; only the identity moved.
- **Why:** the costume's name is no longer useful for the mod; the new name describes what the pack is.
- **Held to:** `tests/test_pd2_las_invariants.py` (`ITEMS`, `_stems`) and the invariants suite;
  `status.py` tracks `OfficeSuite` and `OfficeSuite_Miranda_Romance_over_Hila`; `fresh` rebuilds and
  compares the tracked bytes.
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`OFFICE_SUITE`), `tools/pd2-las/status.py`,
  `tools/pd2-las/dist_paths.py`
- **Status:** holds.

### D55 — `OfficeSuite` ships the outfit's own hands; the Hila override drops the stock gloves

- **Decided:** 2026-11-23, by the user ("can you change vanila hands in Hila?", then
  "Office Suite LAS too. Office suit donor hands. you just need to remove vanila wrist skin")
- **Decision:** `OfficeSuite` alone (`PackSpec.hands=True`; `Honoko2`..`Honoko4` stay byte-identical)
  no longer cuts the source at the PD2 wrists. The donor's palms, fingers and the outfit's bracelet
  stay in the body and shadow drawables on the PD2 `Hand` and finger bones, the `fps_officesuite`
  arms keep them too, and the pack registers **no** `glove_adapter.lua` (the adapter exists to give a
  handless pack the heister's handlers and changeable gloves back). The native Hila override inherits
  that body, turns Hila's stock `g_hands` node off and deletes the glove block from her unit model,
  and loses the cuff tuck (`Cuff`, `_measure_cuff`, `_pull_weights`): with hands in the mesh there is
  no cut rim to push inside a glove lip, and the donor's forearm seals the suit cuff itself.
- **Why:** the cut deleted the hands, so the wrists showed the heister's vanilla blue gloves with the
  donor's bare cuff rim poking out above them: the "vanilla wrist skin" in the screenshots. The
  source mesh already has complete hands; keeping them is cheaper and truer than retexturing a glove.
- **Also:** the pack's HUD/menu icon is a render of its own mesh, so it now shows the hands at the
  sleeve ends instead of the cut stubs; it changes with the geometry by construction, not by hand.
- **Held to:** `tests/test_pd2_las.py::…are_honoko3_in_the_alt_suits` (same vertex set plus the hands,
  `glove_adapter` false for `OfficeSuite` only); `tests/test_hila_body_override.py` (no glove sections
  survive, the hands reach the finger joints, both `.object`s have no `g_hands` node);
  `tests/test_one_implementation.py` (the writer emits no adapter for a pack that ships hands).
- **Rejected:** retexturing Hila's glove mesh to skin, and Miranda's black gloves (offered, not chosen);
  authoring new hand geometry (the donor's own hands are kept instead).
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`PackSpec.hands`, `build_pack`, `registration`),
  `tools/build_hila_body_mod.py` (`_fit_unit`, `_drop_hands`, `_object`),
  `tools/pd2-las/build_models.py` (`template`)
- **Status:** superseded by D59 (2026-11-25): the palms are cut again, at the palm's starting
  line rather than at the wrist joint, both LAS packs register the glove adapter again, and the
  Hila override keeps her stock `g_hands`. `runtime_verified` was never claimed.

### D56 — `OfficeSuite_Head` is a separate whole-character pack, not a change to `OfficeSuite`

- **Decided:** 2026-11-23, by the user ("Let's make office suite plus Miranda Head as a single LAS",
  then, asked which head and which scope, the ME2 Romance head and a new separate pack)
- **Decision:** a new tracked pack, `dist/Honoka/OfficeSuite_Head.zip`, registering
  `LegendaryArmours.officesuite_head`. It is the `OfficeSuite` body, hands and FPS unit plus the
  ME2 "Romance" head (`mtr_head` + `mtr_lashes`) that the Hila override already carries, both cut
  from the PD2 rig, in **one** `WHOLE_CHARACTER` unit: one model, `g_body` and `g_head` both enabled.
  `OfficeSuite.zip` and `Honoko2`..`Honoko4` are not touched.
- **Why whole character:** the registration says `replace_all` and `hide_mask`, so the game swaps
  the heister's head for the pack's and hides the mask that would otherwise sit over the new face.
  A `BODY_ONLY` registration (`OfficeSuite`'s own) would keep the stock head and give the outfit two
  faces' worth of geometry. The shape follows `Miranda_Romance_LAS.zip`: one unit, body and head,
  `WHOLE_CHARACTER`.
- **Why a separate pack:** the head is a second character, not a fix to the first. Folding it into
  `OfficeSuite` would change the bytes of a tracked pack and take the stock-head variant away; two
  packs in the menu let both exist. It also keeps `Honoko2`..`Honoko4` out of it by construction.
- **The head comes from the Hila override, not the full LAS-head port:** its own eyes and teeth stay
  Hila's (they are part of her stock head, which the pack does not replace), so no new eyeball or
  teeth work is in this pack.
- **The palette had to be mapped, not re-ordered:** the donor head's palette is its own order
  (`Hips`, `Spine2`, `Neck`, `Head`) and `Group.weights` indexes the *pack's* palette. Building the
  weights by enumerating the donor's influences bound the whole head to `Hips`, which travels with
  the hips; `las_head.load` now maps each donor influence to `HEAD_BONES.index(name)`.
- **Lashes** keep the donor's `opacity:DIFFUSE_TEXTURE:SKINNED_3WEIGHTS`, a single diffuse whose
  alpha is the cutout. The pack's material and gloss invariants name that shader explicitly instead
  of assuming every skin slot is a `generic` diffuse+normal pair.
- **Held to:** `tests/test_pd2_las_invariants.py::test_whole_character_packs_bring_their_own_head`
  (`replace_all` and `hide_mask` set, `replace_body` not, `g_body` and `g_head` in
  one model, the head bound above the collar and never to the hips, no FPS unit); the per-pack
  invariants now run over `OfficeSuite_Head` too. D59 put the glove adapter back on both packs: the
  body ships no hands for the adapter to double.
- **Rejected:** adding the head to `OfficeSuite` (offered; the user chose a separate pack); the full
  LAS-head port (offered; the user chose the existing Hila-override head); keeping the mask usable.
- **Status:** holds; `runtime_verified` stays `false` — the head fit is checked offline only.

### D57 — `Honoko2`, `Honoko3` and `Honoko4` are removed; `OfficeSuite` is the working pack

- **Decided:** 2026-11-23, by the user ("I want you to remove Honoko2.zip - Honoko4.zip. Only
  OfficeSuite.zip will be worked on from now on")
- **Decision:** the three packs stop being tracked and stop being built. `PACKS` is
  `(OFFICE_SUITE,)`, so `make -sC tools/pd2-las honokodae` writes one zip and CI has one to verify.
  `dist/Honoka/Honoko2.zip`, `Honoko3.zip` and `Honoko4.zip` and their `.sha256` sidecars are gone
  from the tree; their bytes stay in git history from the commits before this one. `OFFICE_SUITE`
  itself is untouched — same spec, same passes, same bytes.
- **Why:** the three were variants of the outfit the user no longer wants to carry: the base
  proportions, the 5% slim, and the alternate suit colourway. Work from here is on `OfficeSuite`
  alone (and its `OfficeSuite_Head` sibling), so keeping three near-identical zips means three
  rebuilds, three checksum entries and three sets of stale in-game records for pack nobody will use.
- **What was kept, because `OfficeSuite` uses it:** `SHADOW_DROPS`, the `slim` and `clearance` passes
  and the `PackSpec` fields they read. They were written for `Honoko3`/`Honoko4` but they are what
  builds `OfficeSuite`, so they stay and their comments now say so.
- **What moved rather than went:** the three tests that compared `Honoko4` and `OfficeSuite` against
  `Honoko3` (`test_honoko4_and_officesuite_are_honoko3_in_the_alt_suits`,
  `test_honoko3_and_4_open_the_layer_gaps_and_trim_the_shadow_caster`,
  `test_honoko3_is_honoko2_slimmed_about_the_bones`) are now
  `test_officesuite_carries_the_alt_suits_and_its_own_hands` (renamed
  `test_officesuite_carries_the_alt_suits_and_cuts_the_palms` by D59),
  `test_officesuite_opens_the_layer_gaps_and_trims_the_shadow_caster` and
  `test_officesuite_slims_about_the_bones_and_stays_on_the_floor`. They assert the same properties —
  the override diffuses and their source hashes, the hands and the absent glove adapter, four shadow
  shells, the measured neck and chest gaps, the 5% factor, the soles on the floor and the height —
  against `OfficeSuite`'s own tracked bytes instead of against a sibling that no longer exists.
- **Held to:** `tests/test_pd2_las.py` (the three tests above); the pack registry
  (`tests/test_pd2_las_invariants.py` `ITEMS`, `tools/pd2-las/status.py` `LAS_TARGETS`) and the
  tracked-zip counts in `tests/test_dist_layout.py` and `tests/test_determinism.py`.
- **Rejected:** keeping the three as unbuilt-but-tracked files (they would go stale and fail
  `fresh`), and folding them into `OfficeSuite` as alternate colourways behind one registration.
- **Record kept:** the 2026-11-15 in-game captures are of `Honoko2`, so their folder and manifest
  keep that name; `HANDOFF.md` labels the packs as removed rather than deleting the evidence.
- **Status:** holds; nothing about `OfficeSuite`'s bytes changed with this decision.

### D58 — An outfit with its own modelled hands never draws a default glove

- **Decided:** 2026-11-23, by the user ("For office suit with head LAS - I don't want to use
  vanilla gloves. Only hands from the model"), scoped by them to **every** pack this builder
  produces, with a deliberately equipped glove still allowed to win.
- **Decision:** a pack that models hands into its unit (`PackSpec.hands`, i.e. both `OfficeSuite`
  and `OfficeSuite_Head`) ships an `<item id>_own_hands.lua` hook on
  `lib/tweak_data/blackmarkettweakdata`. It sets the outfit's `default_glove_id = false`, so
  "Default" gloves resolve to no glove unit, and keeps `body_replacement.hands` and
  `third_body_replacement.hands` **true**, so the heister's stock hands stay hidden. The modelled
  hands are therefore the only hands on screen. A glove the player picks by name (`bonemittens`
  and the like) still resolves to its unit and replaces them.
- **Why a hook at all, when it already works:** it works *by accident*. LAS 4.1.9's loader sets
  `output.default_glove_id = output.default_glove_id or false` off the fresh output table
  (`tests/fixtures/las_loader_4.1.9.lua:30`), and BeardLib's `get_glove_value` returns `false`
  for "Default" gloves when that field is `false` — so no glove unit spawns today. That is an
  upstream bug the pack was relying on silently. If LAS ever reads the outfit's own field, the
  default becomes `heist_default`, a real glove unit spawns over the modelled hands, and nothing
  in the pack would have said otherwise. `tests/test_glove_behavior_lua.py` runs both cases
  against the real loader: with a *fixed* LAS and no hook, a glove spawns (the regression, pinned
  as a test); with the hook, it does not.
- **Why `hands = true` and not `false`:** BeardLib hides the stock hands while that flag is true
  and spawns nothing when no glove unit resolves — which is exactly the wanted state. The
  `hands = false` line belongs to the *adapter* hook, where the pack has no hands and the stock
  ones are the fallback. Copying that line here would put the heister's bare stock hands beside the
  modelled ones: the double-hands failure the adapter hook warns about.
- **The two hooks are opposites and must never both ship.** The adapter hook exists so a pack with
  **no** hands gets the heister's gloves back; this one exists so a pack with hands keeps them.
  `BUILD_INFO.registration.own_hands` records which, and the invariant fails if both are present.
- **What is deliberately not done:** gloves are not removed from the menu for these outfits, the
  glove exclude list is not touched, and the glove entries are not edited. The user's rule is about
  the *default*, not about taking the choice away.
- **Held to:** `tests/test_pd2_las_invariants.py::test_own_hands_packs_never_draw_a_default_glove`
  (hook present and wired, `default_glove_id = false`, `hands = true` in both replacements, no
  adapter hook, the hook names its own style); `tests/test_glove_behavior_lua.py` (the behaviour
  against the real LAS loader, including the fixed-LAS regression and the chosen-glove case).
- **Rejected:** removing the glove option for these outfits (offered; the user chose to let a
  chosen glove win); leaving the guarantee implicit in LAS's bug.
- **Status:** holds, and since D60 it is the hook the handless packs ship too: `default_glove_id =
  false` plus stock hands hidden is exactly what an outfit with no hands in its mesh wants, and it
  is what `OfficeSuite` and `OfficeSuite_Head` register. `runtime_verified` stays `false` — this is
  modelled against the verbatim LAS loader and the ported BeardLib logic, not seen in the game. The
  in-game checklist has the step.

### D59 — The OfficeSuite packs cut the hands where the palm begins, not at the wrist

> **Superseded in part by D60 (2026-11-25).** The plane, its landmark on the rig and the 28 cm
> radius stand. What does not: the whole-triangle drop (it stopped 2.2 cm short of the plane), the
> `kept_to_cm` numbers below, and the glove-adapter registration, which produced a vanilla bare
> forearm at the wrist in game.

- **Decided:** 2026-11-25, by the user ("remove the palms from the OfficeSuite packages and make
  explicit where the palm begins"), scoped by them to `OfficeSuite`, `OfficeSuite_Head` and the
  native Hila override.
- **Decision:** `PackSpec.hands` is a mode, not a flag: `"own"` (the D55 build, kept for a future
  pack) or `"palm_cut"`. Both `OfficeSuite` and `OfficeSuite_Head` are `"palm_cut"`, and the native
  override inherits that body. The cut plane is defined on the PD2 rig and per side: **origin** =
  the `Hand` joint (`ARM_JOINTS`' wrist, the pivot the game animates), **axis** = the mean of the
  four knuckle bases (`Hand{Index,Middle,Ring,Pinky}1`) minus that joint, normalised, pointing from
  the wrist towards the fingers. A triangle goes if any of its vertices is distal to the plane,
  inside a 28 cm radius of the axis (the radius is what stops the half-space from also cutting the
  legs — see D55's dead end), and the rim is capped. On the 2B rig that axis is **3.98°** off the
  forearm axis: that wedge is the heel of the hand, i.e. exactly the geometry a wrist-plane cut
  leaves behind. The plane, the margin, the removed triangle count, the rim cap count, the vertices
  removed per bone and how far short of the plane the shipped mesh now ends are all written into
  `BUILD_INFO.json` under `palm_cut` (per side: origin cm, axis, `deg_from_forearm`, `kept_to_cm`).
- **Why the palm line and not the wrist joint:** the user's earlier complaint (D55) was the vanilla
  blue glove showing under a bare cuff rim. Cutting at the wrist joint leaves the palm's own heel
  on the sleeve, so the sleeve end is neither a cuff nor a hand; cutting where the palm begins makes
  the sleeve end exactly a sleeve, and the heister's own glove — which the game sizes to a hand —
  covers the capped rim. It also gets the outfit's bracelet and cuff back to being jewellery rather
  than part of a modelled hand.
- **Why the register flips back to the adapter:** with no hands in the mesh, the pack needs the
  `_glove_adapter.lua` hook (`default_glove_id`, `hands = false`) that gives the heister the stock
  hands and changeable gloves, which is the opposite of D58's `_own_hands.lua`. `registration.own_hands`
  is `false` and `registration.glove_adapter` is `true` again, and the "never both" invariant covers
  this direction too.
- **The Hila override is a replacement, not a LAS pack,** so it has no hook to flip: it keeps Hila's
  stock `g_hands` drawable, its node enabled in both `.object` files, and its glove block in the
  unit model, all byte-identical to the game's. `build_hila_body_mod.py` no longer deletes that node
  or those sections, and the cuff tuck that D55 removed stays removed (with a capped rim inside a
  glove there is nothing to tuck).
- **Measured, not asserted:** the shipped `g_body` of both LAS packs has 31,577 vertices (61,347
  after the 5% slim); the cut removes 2,276 triangles and adds 25 rim-cap triangles; the removed
  vertices are dominated by `Left`/`RightHand` (209/211) and by every finger segment, with 17 per
  side on the forearm edge. What survives ends 2.22 cm (left) and 2.27 cm (right) **short** of the
  plane, because a triangle that straddles the crease goes with the palm; the cap closes the ring
  that is left. The Hila override's `g_body` carries the same cut, and Hila's own glove covers it.
- **Held to:** `tests/test_palm_cut.py` (the landmark is the `Hand` joint and the knuckle axis, the
  recorded plane is the rig's plane, both packs record `removed_tris`/`rim_cap_tris`/`kept_to_cm`,
  the shipped body has no vertex dominated by a hand bone and none distal to the plane, the Hila
  override carries the same cut with `g_hands` present and enabled);
  `tests/test_pd2_las.py::TestLasScaffold::test_officesuite_carries_the_alt_suits_and_cuts_the_palms`;
  `tests/test_pd2_las_invariants.py::test_whole_character_packs_bring_their_own_head`;
  `tests/test_hila_body_override.py` (the two models and two material configs are the only changed
  files, the glove block survives, the hands are absent from the body).
- **Rejected:** cutting at the wrist joint (D55's earlier geometry — leaves the palm heel and takes
  the bracelet); a bare half-space without the radius limit (it cuts the legs); retexturing Hila's
  glove mesh to skin, and Miranda's black gloves (offered under D55, not chosen); deleting Hila's
  glove drawable and letting the sleeves end bare.
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`PackSpec.hands`, `_last_kept_cm`,
  `_cap_cut_rims`, `_dominant_bones`, the build loop's cut and its stray-bone guard),
  `tools/pd2-las/build_models.py` (`PALM_KNUCKLES`, `palm_planes`, `is_hand_bone`),
  `tools/pd2-las/tmc_las.py` (`cut_group_at_planes`, `cut_group_at_palm_bases`),
  `tools/build_hila_body_mod.py` (`GLOVE`, `_fit_unit`)
- **Status:** superseded in part by D60: the plane and the measured landmark hold, the whole-triangle
  drop and the `BUILD_INFO` numbers do not, and the glove-adapter registration was wrong in game (a
  vanilla bare-forearm piece at the wrist). `runtime_verified` stays `false` — the cut is checked
  offline (renders and the shipped bytes) only. The in-game checklist has the wrist and glove steps.

### D60 — The palm cut is made on the plane, and a handless outfit spawns no glove and no forearm

> **Amended by D62 (2026-11-25).** The registration half stands unchanged: no glove adapter, no
> default glove, a chosen glove still spawns. What moves is where the cut sits — 4 cm *past* the palm
> line, inside the palm — because the game showed the capped end stopping short of the heister's glove
> cuff. The `clipped_to_cm: 0.0` / `kept_to_cm` / vertex-count numbers below describe the D60 bytes.

- **Decided:** 2026-11-25, by the user, after the first D59 build was seen in game: *"Forbid using
  the previous method. Go back to previous version. AND ONLY REMOVE the palm and fingers. So the
  standard skin should have no hands. You should remove exactly where palm begins. But choosing
  another gloves would give those gloves."*
- **What was wrong in game.** A third-person screenshot of the D59 build showed, from the sleeve
  down: bare forearm, then a salmon-pink band with a seam in it that the outfit does not have, then
  the black heister glove. That band is `hnd_forearms` — the vanilla *bare forearm* the glove
  adapter spawns to bridge a glove cuff and a short sleeve. It is a second, vanilla skin at the
  wrist, spawned by the `_glove_adapter.lua` hook D59 added, and no material or geometry of ours can
  hide it because it is drawn outside the outfit. The same screenshot also showed the cut itself
  leaving a ring: the D59 drop took a whole triangle as soon as one vertex was distal, so the sleeve
  stopped 2.22 cm (left) / 2.27 cm (right) short of the crease, i.e. the cut was near the palm line
  but not on it.
- **Decision, geometry:** the same plane as D59 (through the `Hand` joint, perpendicular to the palm,
  3.98° off the forearm axis, 28 cm radius), cut *on* the plane. `tmc_las.clip_group_at_planes`
  splits a straddling triangle where its edges cross, interpolates position, normal, UV and skin
  weights at the crossing, drops the distal part and leaves the proximal one. Crossing points are
  cached per *edge*, so neighbouring triangles share them and the rim stays one watertight loop,
  which is what lets the existing rim cap close it. `cut_group_at_planes` (whole-triangle drop) stays
  for the Christie builds, whose tracked bytes reproduce unchanged.
- **Decision, registration:** the packs go back to D58's `_own_hands.lua` and drop the adapter hook:
  `default_glove_id = false` and `body_replacement.hands = true`, so the game spawns no glove unit
  and hides the stock hands, and what the pack models is all there is on the arm. A glove the player
  picks by name still spawns and replaces the hands - that is the "choosing another gloves would give
  those gloves" half of the rule, and it is why the Hila override keeps its stock `g_hands` drawable
  and glove block: a chosen glove needs something to land on.
- **Why not keep the adapter off but still spawn a default glove:** it would put a vanilla glove
  hand on a pack whose whole point is that the outfit models no hands; "the standard skin should
  have no hands" is the default, not the fallback.
- **Measured, not asserted:** `BUILD_INFO.palm_cut` now records `exact: true`, `clipped_to_cm: 0.0`
  per side (the cut lands on the plane), `tris_split` 64 and `verts_added` 66 (crossing points that
  are shared between the triangles either side of an edge), `removed_tris` 2,276 and `rim_cap_tris`
  68. The shipped `g_body` has 31,643 vertices (61,479 after the 5% slim) - D59's 31,577 plus the 66
  the clip adds - and its most distal vertex is 0.76 cm (left) / 0.79 cm (right) **proximal** of the
  plane, which is the slim pulling the arm in towards its bones, not the cut: without the slim the
  number is 0.00.
- **Held to:** `tests/test_palm_cut.py` (the box test pins split-on-the-plane against
  drop-a-whole-face: crossing vertices exactly on the plane, one watertight rim loop, slice blocks
  intact; the pack tests pin `exact`/`clipped_to_cm`/`kept_to_cm` and that no hand bone survives);
  `tests/test_pd2_las.py::TestLasScaffold::test_officesuite_carries_the_alt_suits_and_cuts_the_palms`
  (vertex counts, `glove_adapter false`, `own_hands true`);
  `tests/test_pd2_las_invariants.py::test_whole_character_packs_bring_their_own_head` and
  `::test_own_hands_packs_never_draw_a_default_glove` (no adapter hook beside an own-hands hook, the
  hook's own body); `tests/test_glove_behavior_lua.py` (a chosen glove still spawns).
- **Rejected:** the glove adapter (the `hnd_forearms` band); a default glove unit on the handless
  outfit; keeping the whole-triangle drop and calling the 2.2 cm stop "the palm line"; adding a
  sleeve extension or a substitute wrist material to cover the seam - the user has rejected invented
  wrist geometry twice, and with the cut on the plane and no adapter there is nothing left to cover.
- **Source:** `tools/pd2-las/tmc_las.py` (`clip_group_at_planes`, `clip_group_at_palm_bases`,
  `_plane_distances`), `tools/pd2-las/build_honoko2_dae.py` (`registration`, the build loop,
  `_last_kept_cm`), `tools/pd2-las/las_outfit_pack.py` (`render_own_hands_lua`),
  `tools/render_mod_previews.py` (the sheets' captions).
- **Status:** holds; `runtime_verified` stays `false` - the D59 build is the one that was seen, and
  these bytes have not. The in-game checklist's hand step now asks for three things: no vanilla skin
  at the wrist, no glove by default, and the player's glove choice appearing when one is equipped.

### D61 — Only the id-keyed stream pack ships; the BeardLib voice pack is dropped

- **Decided:** 2026-11-25, by the user: *"remove the BeardLib voice pack from dist, keep only the
  stream one."*
- **Why:** the BeardLib `SoundsModule` pack (`dist/Hila/Miranda_Lawson_VO_over_Hila.zip`) was
  installed on 2026-11-24 and vanilla Hila still played. Its keying was then re-verified against
  BeardLib's `SoundManager`/`SoundsModule` and the game Lua (`ecp_female` is `rb21` in both the
  player and the team-AI path, and `<Sounds prefix="rb21">` is what `ComparePrefixes` matches), so
  the packing was right and the route still did not produce a line. The id-keyed `.stream` pack
  (`..._Stream.zip`) was built on the same picks the next day, installed, and reported working. Two
  routes, one of them verified in game: ship that one.
- **Decision:** `dist/Hila/` holds `Miranda_Lawson_VO_over_Hila_Stream.zip` and nothing else. The
  `voices` make target, the `voices` stage in `fresh.py`, `status.TARGETS`' entry and the builder
  itself are gone; `tools/build_hila_voice_mod.py` became `tools/hila_voice_clips.py`, which keeps
  the half the stream pack *does* use — archive listing, picks and splits, `cut_ogg`/`cut_ogg_ranges`,
  `match_level` at `-1.5 dBFS` — and whose `main()` now only refreshes the tracked
  `hila_slot_pieces.csv` build manifest (`python tools/hila_voice_clips.py`; it builds no pack, so it
  has no make target of its own).
- **What stays, and why:** `slot_picks.csv`, `hila_intent_cuts.csv`, `ogg_phrase_splits.csv` and
  `slot_event_ids.csv` are the picks and the intent table the stream pack cuts from — the event table
  no longer keys anything, but it is the record of which PD2 bark each slot stands for.
  `docs/pd2-voice-mod-install.md` §1–§6 stay as the record of the dropped route (marked as such),
  because a future pack on that route would start there.
- **Held to:** `tests/test_hila_voice_picks.py` (the pick table is complete and clean for every slot,
  the packs' window/splits are real, `dist/Hila` holds no BeardLib zip, no make target or `fresh`
  stage builds one, and the builder file is gone); `tests/test_hila_cut_edges.py` (the re-cut edges,
  now importing `hila_voice_clips`); `tests/test_hila_stream_pack.py` (the packed ids and bytes).
- **Rejected:** keeping both packs "just in case" (the user asked for one, and a route that has never
  played a line is not a fallback); keeping the builder as dead code behind an unused target.
- **Source:** `tools/hila_voice_clips.py`, `tools/build_hila_stream_mod.py`,
  `tools/pd2-las/Makefile`, `tools/pd2-las/fresh.py`, `tools/pd2-las/status.py`,
  `docs/pd2-voice-mod-install.md`, `voice_lines_vox/README.md`.
- **Status:** holds; the stream pack is the one whose clips were heard in game, and the two re-cut
  clips still await a listen (see the in-game checklist).

### D62 — The palms are cut 4 cm past the palm line, so the arm ends inside the glove

> **Amended by D63 (2026-11-25): the extension is 1.5 cm, not 4.** Everything else here stands
> — the plane, the margin mechanism, `extend_cm` in the record, the no-adapter registration.
> The 4 cm number was answered by the game the same day: it put the palm through the glove. The
> `clipped_to_cm` / vertex-count numbers below describe those bytes.

- **Decided:** 2026-11-25, by the user, after looking at the D60 build in game: two wrist
  screenshots showing the capped end of the arm sitting in mid-air, above the heister's black glove
  cuff, with a gap between them. Their instruction: *"you need to extend forearms a bit"*.
- **What was wrong.** D60 cut exactly where the palm begins, which is the right *landmark* and the
  wrong *place for a glove*. A PD2 glove is modelled around a hand, so its cuff starts below the
  outline of one — the sleeve's cap and the glove's rim do not meet, and the arm visibly stops before
  the glove. The geometry was correct and the wrist was still broken.
- **Decision, geometry:** keep D60's plane (through the `Hand` joint, along the knuckle axis, 3.98°
  off the forearm, 28 cm radius) and push the cut `PALM_EXTEND_CM = 4.0` cm along its own normal,
  into the palm: `tmc_las.clip_group_at_palm_bases(..., margin=PALM_EXTEND_CM)` splits where the edges
  cross *that* plane, and the rim cap runs in a window of `margin − 1.5 .. margin + 0.5` cm. The arm
  therefore continues down into the glove instead of ending above it. `BUILD_INFO.palm_cut` records
  it twice: `margin_cm` (the plane the split used) and `extend_cm` (what the module asked for), both
  4.0, so a build cannot silently drift from the number in the source.
- **Why 4 cm.** It is under two thirds of a palm's length, so no finger geometry comes back and the
  cut stays inside hand territory; it overlaps a glove cuff by a centimetre or two at worst, i.e. the
  cap is hidden, not merely close; and it is short enough that the fist still reads as a fist under a
  glove made for a full hand. Nothing was added to the mesh — the same arm, cut later.
- **What the extension changes about the *bones*.** At 0 cm the cut took 17 forearm-dominated
  vertices per side along the sleeve rim; at 4 cm it takes none (the `ForeArm` entries are gone from
  `removed_bones`), because the whole cut is now inside the hand. What survives at the rim is
  `Hand` (152/153 vertices) and the thumb's base — the thenar, `Thumb1`, 15 vertices per side — which
  is the palm's own proximal few centimetres and is exactly what makes the end continuous with the
  wrist. The thumb's phalanges and every finger segment are still gone.
- **Measured, not asserted:** `BUILD_INFO.palm_cut` has `exact: true`, `margin_cm`/`extend_cm` 4.0,
  `clipped_to_cm` 4.0 per side, `kept_to_cm` 3.97 (left) and 3.99 (right), `tris_split` 76,
  `verts_added` 78, `removed_tris` 2,070 and `rim_cap_tris` 88. The shipped `g_body` has 31,804
  vertices (61,801 after the 5% slim). Packs: `OfficeSuite` 5,766,633 B, `OfficeSuite_Head`
  10,384,852 B, `OfficeSuite_Miranda_Romance_over_Hila` 14,855,124 B.
- **Held to:** `tests/test_palm_cut.py` (both packs record `margin_cm == extend_cm == 4.0`, the
  shipped mesh reaches 3.8–4.0 cm past the palm line and no further, the only hand-dominated
  vertices left are `Hand` and the thenar, and the Hila override carries the same body and cut);
  `tests/test_hila_body_override.py::test_the_outfits_hands_end_where_the_palm_begins` (the override's
  body reaches 3.8–4.0 cm into the palm, keeps `Hand` and the thenar, and no finger);
  `tests/test_pd2_las.py::TestLasScaffold::test_officesuite_carries_the_alt_suits_and_cuts_the_palms`
  (vertex counts and `clipped_to_cm`). D60's registration tests are untouched: an own-hands pack still
  draws no default glove and still has no adapter hook.
- **Rejected:** reverting to the D55 modelled hands or the D59 glove adapter to make the wrist meet
  the glove (both were rejected by the user once already); lengthening the sleeve or the cuff instead
  of the arm (that is invented wrist geometry, rejected twice); a smaller extension (2–3 cm still
  leaves the cap above the cuff); a per-arm margin (the two planes are mirrored, and the game's glove
  is the same on both hands).
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`PALM_EXTEND_CM`, the clip call, `_cap_cut_rims`,
  the `palm_cut` record), `tools/pd2-las/tmc_las.py` (`clip_group_at_palm_bases`'s `margin`),
  `tests/test_palm_cut.py`, `tests/test_pd2_las.py`.
- **Status:** holds; `runtime_verified` stays `false`. The D60 build is the one that was seen in game,
  and this is the answer to what it showed — the in-game checklist's wrist step now asks that the cap
  sit inside the glove with no gap above it, and re-cutting is measured against that, not against the
  crease.

### D63 — The extension is 1.5 cm: as far into the glove as its own geometry allows

- **Decided:** 2026-11-25, by the user, after looking at the D62 build in game. Two wrist
  screenshots, and three words: *"Too much."* The arm now reached the glove, but it also came out
  of it — the palm's surface showed through and around the black glove at the wrist.
- **Why 4 cm was too much, measured.** The glove the game draws is `g_hands`, and it is in the
  same rig space as this body (its `Hand` joint is at `[-45.98, 18.69, 124.47]`, the body's palm
  origin at `[-45.99, 18.70, 124.47]`). Measured along this body's palm axis, that glove **starts
  0.42 cm past the crease** and is **3.5 cm in radius at its rim**, widening to 4.0 at 2 cm and
  4.3 at 3 cm. This outfit's wrist is 3.46 cm in radius and its palm passes 4.4 cm at 2 cm and
  5.6 at 3. So the arm can be tucked in until the palm meets the glove's interior, and no
  further: at 4 cm the rim sat 3.5 cm inside the glove, in territory the glove does not have room
  for, and the surface came through it. Renders of the same body at 1.0, 1.5, 2.0 and 2.5 cm with
  the glove composited over it show the silhouette breaking between 1.5 and 2.0.
- **Decision:** `PALM_EXTEND_CM = 1.5`. That is a centimetre past the glove's rim after the slim,
  which is what closes the gap, and it is the largest whole step that stays inside the glove.
- **Measured, not asserted:** `palm_cut` has `margin_cm`/`extend_cm` 1.5, `clipped_to_cm` 1.5 per
  side, `kept_to_cm` 0.90 (left) and 0.83 (right) — the 5% slim pulls the arm's end back about
  half a centimetre here, which is why the shipped numbers are not 1.5 — `tris_split` 67,
  `verts_added` 69, `removed_tris` 2,224 and `rim_cap_tris` 71. Both are still past the glove's
  0.42 cm rim, so the cap is inside the glove. The shipped `g_body` has 31,674 vertices (61,541
  after the slim) and **no vertex dominated by a hand or finger bone at all**: 1.5 cm into the
  wrist is still arm territory, so D62's kept thenar is gone with the rest of the palm. Packs:
  `OfficeSuite` 5,739,451 B, `OfficeSuite_Head` 10,357,873 B,
  `OfficeSuite_Miranda_Romance_over_Hila` 14,830,470 B.
- **Held to:** `tests/test_palm_cut.py` (1.5 cm in the record, `kept_to_cm` between 0.6 and 1.5
  **and past the glove's 0.42 cm rim**, the mesh reaching 0.6–1.5 cm and no further, no
  hand-dominated vertex, the rim allowed to take a handful of forearm-dominated ones);
  `tests/test_pd2_las.py` (31,674 / 61,541 vertices, `clipped_to_cm` 1.5);
  `tests/test_hila_body_override.py` (the same cut on the override's body).
- **Rejected:** keeping 4 cm and shrinking the palm so it fits inside the glove (invented
  geometry at a place the user can see, and it would have to be tuned against a glove the pack
  does not ship); 2.0 cm (the render shows the palm through the glove); 1.0 cm and below (the
  slim pulls the mesh back to 0.27–0.33 cm, short of the glove's 0.42 cm rim — the D60 gap
  returns); a per-heister margin (every glove is authored on the same hands and the same rig).
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`PALM_EXTEND_CM` and the measurements in its
  comment), `tests/test_palm_cut.py`, `tests/test_hila_body_override.py`.
- **Status:** holds; `runtime_verified` stays `false`. D60 and D62 are what was seen in game; this
  is the third answer to the same wrist. The glove measurements above come from
  `references/npc_criminals_ecp_female.7z` (`g_hands`), which is the glove this rig draws, not a
  photograph of the user's session — so the in-game checklist still decides.
