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

### D11 — Christie is body-only: the heister keeps their head

- **Decided:** 2026-11-05 · `5f9129e`
- **Decision:** the Christie packs ship no head geometry and register
  `replace_body`, not `replace_all`.
- **Mechanism:** LAS expands `replace_all` to head, armour, body, hands, arms
  and vest, and `replace_body` to body, hands and arms. An outfit that
  declares `replace_all` without shipping a head is shown decapitated
  (`672eb03`, 2026-11-02).
- **Why headless at all, when the Miranda packs are full characters:** to
  keep the heister's own head and wear Christie's outfit with it (the user,
  asked on 2026-11-11). The commit describes the result as "headless like LAS
  police uniforms".
- **Source:** `5f9129e`, `672eb03`; `CHRISTIE.md`
- **Status:** holds.

### D12 — Christie slim: 10% thinner, same height, wrists cut for the in-game gloves

- **Decided:** 2026-11-05 · `99fe202`, `d2aa2cc`, `0262d2d`, `1d95b30`
- **Decision:** the slim variant scales the body by 0.9 in x and y and leaves
  z alone, cuts the hands at the wrist and ships a glove-adapter hook, so the
  gloves the player equips show at the end of the sleeves.
- **History:** it began the same day at 0.8 (`99fe202`) and went to 0.9
  together with the wrist cut (`0262d2d`). The wrist cut first shipped as a
  separate no-hands pack (`d2aa2cc`), which was dropped that day because slim
  supersedes it (`1d95b30`).
- **Mechanism:** LAS 4.1.9 force-disables the glove adapter for
  `replace_body` outfits. The hook re-enables it with `glove_adapter = {}`,
  a table, because boolean `true` crashes BeardLib's table merge (`7fb50ac`,
  2026-11-03).
- **Why 0.8 became 0.9:** 20% thinner looked too thin (the user, asked on
  2026-11-11).
- **Source:** the commits above; `CHRISTIE.md`
- **Status:** holds. Open defect: both slim sleeves are still open just past
  the elbow. It is marked as a known failure, not fixed (D18).

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

## Environment, tests and documents

### D14 — Inputs live in `models/` and `references/`

- **Decided:** 2026-10-20 · `94bb4b0`
- **Decision:** source models are in `models/`, reference mods in
  `references/`. One source sits among the references:
  `references/Christie.zip`.
- **Why:** not recorded beyond the commit subject ("organize").
- **Source:** `94bb4b0`; `models/README.md`, `references/README.md`
- **Status:** holds.

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
  (`xfail`), for the same reason (D18).
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

### D18 — A known defect is an expected failure, strict and bounded; the suite stays green

- **Decided:** 2026-11-11, by the user
- **Decision:** the two slim-sleeve cases of
  `test_sleeve_tube_is_closed_along_its_length` are expected failures
  (`KNOWN_SLEEVE_LEAK_CM2` in `tests/test_christie_las.py`). The sleeves
  themselves are not fixed.
- **Why:** with the 2B templates unpacked, the suite was red on exactly these
  two cases, so the `test` target, `bootstrap.sh` (retired since, D28) and `check_all.py --full`
  exited non-zero on every run and a new failure had nothing to stand out
  against. Asked on 2026-11-11, the user chose marking the cases over a
  geometry repair: the suite goes green without touching the pack, and the
  cases report again the day a sleeve is fixed.
- **What a repair would have meant:** a new `Christie_LAS_Slim.zip` in place
  of the build that the user's latest in-game screenshots were taken with
  (`CHRISTIE.md`, 2026-11-10), with no certainty of success: the journal
  calls the hole "a geometry limitation beyond stitching", because the two
  rims have no paired vertices to bridge.
- **What keeps the marker from hiding anything:**
  - it is strict: when a sleeve closes, its case turns red (XPASS) until the
    entry is deleted;
  - it accepts an `AssertionError` only: a measurement that breaks still fails;
  - `test_known_sleeve_leak_does_not_grow` fails if a recorded leak gets
    worse;
  - `tools/pd2-port/check_skip_budget.py` names the tests that may be expected
    to fail and fails on any other `xfail`.
- **For the next known defect:** give its marker the same four guards. A
  bare skip or a bare `xfail` is not an option.
- **Source:** the user's answer on 2026-11-11; the comment at
  `KNOWN_SLEEVE_LEAK_CM2`; the 2026-11-11 sleeve-seam entry of
  `tools/pd2-las/MODLOG.md` for the defect itself
- **Status:** holds. When a sleeve is closed, delete its entry in
  `KNOWN_SLEEVE_LEAK_CM2`; when both are, also the line in `ALLOWED_XFAIL`.
  The rule for known defects stays.

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
  `test_bust_variant.py`, `test_christie_las.py`) check the same properties in
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
  has), which the Christie builder follows and `las_pack.py` does not.
- **Two exceptions that were written down, and are gone.** Each was a set in
  the test file whose test failed when the set grew and when it shrank, so the
  list could not spread and could not outlive a fix (the rule of D18, without
  an `xfail`). Both packs were rebuilt on 2026-11-11 and both sets were
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
  - the Christie fit rule in `AGENTS.md` → a line under the README's "Do
    not", with the detail in `CHRISTIE.md`.
- **Corrected on the way, both in `AGENTS.md`:**
  - a normal map is not `R = G = B = ny`. Both writers put X in alpha and Y in
    green and fill red with 255 and blue with 0, and the Textures test holds
    the tracked packs to it;
  - the `ForeArm` does not flex about local Z. On the 2B skeleton local Y is
    the normal of the bind-pose bend and local X runs along the forearm, as
    `CHRISTIE.md` measured on 2026-11-07.
- **Not kept:** `git reset --hard origin/<branch>` as a routine first
  command. It is right only when everything local is already on the remote;
  otherwise it discards unpushed work. `AGENTS.md` now says so.
- **Source:** `tests/test_pd2_las_status.py::test_pd2_las_has_one_entry_point`;
  `tests/test_las_pack.py::test_handoff_and_agents_quote_the_tracked_pack_bytes`
  for the handoff's table (every tracked zip, each with its own size and
  sha256)
- **Status:** superseded in part by D30 (2026-11-13): `AGENTS.md` has no copies, `HANDOFF.md` no longer
  quotes the tracked bytes, and the second test named above is gone. The rest holds.

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

- **Decision:** when `dist/Miranda_LAS.zip` changes, the four
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
     triangles fills a ring (`build_christie_las._fill_ring`).
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
  the two Christie packs differ in one or two normals whose component is
  zero up to rounding and, in the slim pack, in two positions. Nothing else
  in any pack moves.
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
- **Decision:** `main.xml`, the hook, the strings, the unit file, the glove adapter and the zip of every pack built in `tools/pd2-las/` are written by `las_outfit_pack.py`, and so is the zip of the head packs. What a pack chooses is a `Registration`: its flags (`WHOLE_CHARACTER` or `BODY_ONLY`), its units, its textures, the glove adapter. `las_pack.py`, `build_christie_las.py` and `las_outfit_pack.py` each state it in a function called `registration`.
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
- **Decision:** `build_christie_las.py` writes `"runtime_verified": false`, as the other builders do. Both
  Christie packs were rebuilt for it: one line of `BUILD_INFO.json` in each, every other member byte for
  byte the same.
- **Why:** the flag said `true` from the 2026-11-05 test of the base pack on, in both packs and through every
  rebuild after it, while `HANDOFF.md` recorded that no tracked bytes of either pack had been in game. A
  constant cannot follow what a person saw; the handoff's table does.
- **Rejected:** leaving the flag and saying so in `HANDOFF.md` (done on 2026-11-11; the pack went on saying
  the opposite of the record).
- **Source:** the user, asked on 2026-11-13; `docs/audits/2026-11-13-agent-entry.md`;
  `tests/test_christie_las.py`
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
  test and no recorded tool runs it; a person does. `CHRISTIE.md` documents it, and on
  `references/Christie.zip` it writes the five tracked `christie_source_*.png`, byte for byte.
- **Kept, because something else uses it:** `las_outfit_pack.py` writes the registration files of the
  Christie and Miranda packs; `preview_textured.py` and `pose_preview.py` are what `glove_check.py` and
  `pose_zoom.py` render with; `build_models.extract_bones` cuts the Christie first-person arms, and
  `extend_sleeves_to_wrist` stretches the sleeves of `Christie_LAS_Slim`. The tests of those functions that
  sat in the outfit's test files were kept and now run on what exists: `tests/test_las_outfit_pack.py`,
  `tests/test_build_models.py`, and `tests/test_glove_adapter.py` with `tests/test_glove_behavior_lua.py`
  on `Christie_LAS_Slim`, the pack that ships the glove adapter.
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
