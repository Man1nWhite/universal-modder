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
- **Status:** holds.

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
    `6196b2b`. The constant `FIT_MAX_DIVERGENCE_DEG` is left over from it in
    `build_models.py`; nothing reads it.
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
  pillow and numpy are pinned (in `bootstrap.sh`, `recover_env.sh` and CI), so
  a rebuild of an unchanged tree gives the same bytes.
- **Why reproducible:** `zipfile` embedded modification times, so identical
  content produced a different zip on every build (`8564c91`); the pins exist
  so that "the byte check compares like with like" (`5561380`), and CI fails a
  push whose tracked pack differs from a fresh build (`fa798b2`).
- **Why tracked in git rather than only built:** so that a pack can be
  downloaded and installed straight from the repository, without building
  anything (the user, asked on 2026-11-11).
- **Source:** the commits above; `tests/test_dist_checksums.py`
- **Status:** holds.

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
- **Status:** holds.

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
  two cases, so the `test` target, `bootstrap.sh` and `check_all.py --full`
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
- **Two exceptions that are written down.** Each is a set in the test file,
  and its test fails when the set grows and when it shrinks, so the list
  cannot spread and cannot outlive a fix (the rule of D18, without an
  `xfail`: nothing fails today). Both are under the README's Next.
  - `SINGLE_LEVEL`: `miranda_face_df` and `miranda_eyes` ship one mip level
    where every other unit texture has the full chain. Whether it shows in
    game is not known.
  - `ABSENT_OBJECTS`: `fps_miranda_busty.object` lists `g_head` and
    `g_head_lod1`, and its model has no object of either name. The variant's
    builder drops the two disabled head drawables from the first-person model;
    `las_pack.render_object_xml` writes a fixed list. In the 2B pack and in
    the other seven tracked units every `<object>` line has its object.
    Whether the game minds is not known: no Miranda pack has an in-game
    record. The pack was not changed: a fix gives a tracked deliverable a new
    sha256, and that is the user's call.
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
  first commands: `bootstrap.sh` after a hard reset (`AGENTS.md`);
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
- **Status:** holds.
