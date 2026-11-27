# pd2-las — decisions, and why

What was decided about the Source-model → LAS pipeline (`tools/pd2-las/`), and later about the
voice-line packs (`tools/*stream*.py`), when, and for what reason, so that nobody undoes a
decision by accident or argues one out again from scratch. For how to build, start at
[`tools/pd2-las/README.md`](../../tools/pd2-las/README.md); for the dated state of the packs,
[`HANDOFF.md`](HANDOFF.md).

**How to read it.** One entry per decision, under the section it belongs to. *Why* is what the
record says, not what seems plausible: where the repository never wrote the reason down, the
entry says "not recorded". *Source* names the commit or document the entry rests on, *Status*
says whether it still holds or what replaced it.

**How the sections work.** The five sections are the subject, not the date: an entry is filed by
what it decides, so the numbers jump between sections (D53 is in the packs, D61 in voice). Inside
a section they only ever go up, because that is the order they were appended in. Numbers are
cited from documents, tests and tools — `grep -rn "D61" .` finds every place — so **a number is
its identity: never reuse one, never renumber an entry that has been cited.** A new decision takes
the next free number, wherever it is filed. `python tools/check_decisions_index.py` checks all of
this, and `tests/test_decisions_index.py` runs it.

**One number, one entry.** D74 was used twice for a day — once for game-derived exports, once for
the Geralt re-key — which made every citation of it ambiguous. The re-key is now D76: the wrist fix
merged on `main` took D75 first, so when the branch merged, the re-key and the two voice-sheet
decisions after it moved up one (D76, D77, D78). Those are the only edits this record has made to a
number, both in the same week, and both before the moved entries were cited from outside the file.

**Where it comes from.** Reconstructed on 2026-11-11 from the commit messages
on `main`, the audits in `docs/audits/`, `HANDOFF.md` and
`tools/pd2-las/MODLOG.md`. Three reasons that the record lacked were asked of
the user that day; they are marked "the user, asked on 2026-11-11". A checkout
made by the sandbox is shallow, so read a cited commit with `gh api
repos/Man1nWhite/universal-modder/commits/<sha> --jq .commit.message`, or run
`git fetch --unshallow` first.

**How to add to it.** Append an entry with its date. When a decision is
replaced, mark the old entry "superseded by D<n>" and leave its text alone.

**Index.** Every entry, by number, with the section that holds it. The numbers are cited
from documents, tests and tools, so they never change; the headings are appendix-ordered.

*Product and routes* — [D1](#d1--ship-an-additive-las-outfit-do-not-replace-whole-heister-models), [D2](#d2--the-2b-pack-is-the-contract-and-the-skeleton-donor-not-an-oracle), [D3](#d3--the-two-las-pipelines-stay-separate-trees), [D4](#d4--no-public-release)

*Building and the build environment* — [D5](#d5--our-own-model-codec-byte-exact-no-blender-or-external-tool-in-the-build), [D6](#d6--retarget-by-anatomical-partition-not-per-bone-and-not-by-frame-deltas), [D7](#d7--geometry-conventions-are-the-2b-models), [D8](#d8--install-under-assetsmod_overrides), [D80](#d80--the-over-joy-zips-are-gone-the-assembly-that-wrote-them-is-the-over-hila-builder)

*Packs and characters* — [D9](#d9--built-packs-are-tracked-in-git-and-must-rebuild-byte-for-byte), [D10](#d10--a-variant-is-its-own-pack-with-its-own-las-id), [D13](#d13--the-skyrim-outfit-route-is-cancelled), [D36](#d36--the-honoka-pack-is-committed-to-dist-tracked-but-not-fresh-verified), [D37](#d37--the-tracked-honoka-pack-was-rebuilt-with-the-source-connector-filter), [D38](#d38--in-game-menu-captures-were-supplied-for-honoka-and-both-christie-packs-the-handoff-table-is-the-truth-for-what-was-in-game), [D40](#d40--the-tmc-only-honoka-pack-is-deleted-the-dae-build-honoko2-is-the-one-that-stays), [D41](#d41--hilas-head-packs-are-built-from-her-own-unit-and-only-they-wear-the-supplied-eye), [D42](#d42--honoko3-is-honoko2s-mesh-scaled-5-about-the-rigs-bones-both-packs-ship), [D43](#d43--the-supplied-eye-is-repainted-the-two-hila-packs-rebuild-at-a-re-measured-zoom), [D44](#d44--honoko4-is-honoko3-in-the-users-alternate-suit-honoko34-open-the-layer-gaps-the), [D45](#d45--honoko5-the-third-colourway-of-the-same-slim-build), [D46](#d46--revised-honoko5-colourway-and-miranda-nostril-normals), [D47](#d47--group-shipped-packs-and-consolidate-source-archives), [D48](#d48--match-romance-over-hila-head-skin-closer-to-the-honoko-body), [D49](#d49--christie-is-rebuilt-from-source-without-head-or-hands-christie_las_slim-is-removed), [D50](#d50--honoko5-fitjewelry-updates-christie_clover_las-glb-outfit-and-archived-menu-captures), [D51](#d51--dist-is-the-sole-tracked-home-for-built-zips-duplicate-buildpd2-laszip-copies-removed), [D52](#d52--honoko5-and-miranda-romance-directly-replace-hila), [D53](#d53--officesuite-ships-a-first-person-arms-unit), [D54](#d54--honoko5-is-renamed-to-officesuite), [D55](#d55--officesuite-ships-the-outfits-own-hands-the-hila-override-drops-the-stock-gloves), [D56](#d56--officesuite_head-is-a-separate-whole-character-pack-not-a-change-to-officesuite), [D57](#d57--honoko2-honoko3-and-honoko4-are-removed-officesuite-is-the-working-pack), [D58](#d58--an-outfit-with-its-own-modelled-hands-never-draws-a-default-glove), [D59](#d59--the-officesuite-packs-cut-the-hands-where-the-palm-begins-not-at-the-wrist), [D60](#d60--the-palm-cut-is-made-on-the-plane-and-a-handless-outfit-spawns-no-glove-and-no-forearm), [D62](#d62--the-palms-are-cut-4-cm-past-the-palm-line-so-the-arm-ends-inside-the-glove), [D63](#d63--the-extension-is-15-cm-as-far-into-the-glove-as-its-own-geometry-allows), [D64](#d64--the-arivus-shave-fills-from-grown-beard-matched-skin-and-real-structure--no-ring-no-seam-no-flat-panel), [D65](#d65--the-palm-cut-goes-back-to-125-cm-the-arms-fattest-half-centimetre-was-still-in-the-gloves-cuff), [D66](#d66--the-shave-fills-the-beard-not-the-face), [D69](#d69--arivus-the-shaved-area-takes-the-skins-chroma-not-a-new-one), [D70](#d70--the-palm-extensions-are-reverted-the-cut-is-on-the-crease-again), [D72](#d72--arivus-the-beard-is-found-the-rectangle-and-the-collar-gap-are-gone), [D79](#d79--arivus-the-neck-is-a-neck-again-and-the-head-is-skinned-to-its-own-palette), [D82](#d82--the-native-hila-override-is-retired-officesuite_head-carries-the-same-body-and-head), [D83](#d83--the-romance-line-is-retired-and-the-tracker-chain-that-only-it-used)

*Voice lines and the stream packs* — [D61](#d61--only-the-id-keyed-stream-pack-ships-the-beardlib-voice-pack-is-dropped), [D67](#d67--call_teammatehey_you-is-one-shouted-word-not-a-phrase), [D68](#d68--the-hila-stream-pack-ships-61-slots-lawson-voice-takes-in-sub-8-slots-out), [D71](#d71--the-character-packs-write-the-shared-bank-and-only-one-pack-ships-at-a-time), [D73](#d73--the-stream-tables-are-tracked-and-the-rust-bank-question-stays-open), [D75](#d75--the-wrist-twists-on-forearmroll-and-its-ring-is-centred-on-the-glove-officesuites-cuff-fix), [D76](#d76--geralts-takes-are-re-keyed-to-char_rust-the-map-that-names-the-ids-is-the-one-open-input), [D77](#d77--the-community-voice-line-sheet-is-a-shared-bank-source-imported-not-trusted), [D78](#d78--tab-inventory-which-bank-each-community-sheet-actually-covers), [D81](#d81--the-three-sheet-tabs-are-imported-in-full-from-exports-that-were-already-in-the-tree)

*Environment, tests and documents* — [D14](#d14--inputs-live-in-models-and-references), [D15](#d15--the-2b-templates-are-unpacked-into-buildpd2-las2b-never-committed-unpacked), [D16](#d16--skips-have-a-budget), [D17](#d17--the-readme-is-the-entry-point-and-carries-no-dates), [D19](#d19--scratch-and-caches-live-under-build-nothing-names-a-fixed-temp-path), [D20](#d20--the-source-inventory-is-tracked-and-says-only-what-the-source-contains), [D21](#d21--each-invariant-has-one-test-named-after-it-that-reads-the-tracked-packs), [D22](#d22--one-entry-point-the-readme-agentsmd-routes-to-it-handoffmd-is-the-dated-record), [D23](#d23--a-units-object-is-written-from-the-model-beside-it), [D24](#d24--the-build-encodes-only-what-it-changed-and-its-mip-levels-are-judged-as-pictures), [D25](#d25--a-pack-built-from-another-pack-is-rebuilt-with-it), [D26](#d26--the-tracked-bytes-do-not-depend-on-the-cpu-that-builds-them), [D27](#d27--one-writer-for-the-files-that-register-a-pack), [D28](#d28--one-environment-script-and-the-pins-are-written-once), [D29](#d29--the-idstring-hash-is-written-once-the-two-model-readers-stay-two), [D30](#d30--one-command-per-question-one-instruction-file-and-no-figure-in-a-document-that-a-command-prints), [D31](#d31--runtime_verified-is-false-in-every-pack), [D32](#d32--no-pack-carries-a-redistribution-restriction), [D33](#d33--what-is-stale-is-deleted-not-kept-for-later), [D34](#d34--lawson_las-ships-no-creditstxt), [D35](#d35--the-projects-self-description-starts-from-the-present), [D39](#d39--unified-rules-for-renders-docsrendersprojectext-old-tracked-renders-deleted), [D74](#d74--game-derived-exports-may-be-committed)

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

## Building and the build environment

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

## Packs and characters

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
  pins the new bytes without an edit; `make -sC tools/pd2-las green` rebuilds every tracked zip (13 at
  2026-11-26; 20 when this decision was written) and holds these two to the new sidecars and the rest
  to the old bytes.
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

- **Decided:** 2026-10-30, by the user, who replaced a texture on `main` and asked for the rebuild.
- **Decision:** the user replaced `Tex_07(L_7)3.dds` on `main` at `526480e` and requested Honoko5 be redone.
  The updated suit diffuse is black jacket over light shirt; Honoko3 geometry and clearance remain unchanged.
- Nose diagnosis: comparing offline close-ups with the original face diffuse showed the diffuse alone
  did not remove the dark splotches. The head builder's broad, strongly downward nostril vertex-normal
  override affected the visible nose wings. Remove that override while retaining the repaired source
  normals and UV-pocket cavity treatments. Both Miranda variants and their heister packs are rebuilt.
- **Status:** holds offline only. Verified in offline frontal and three-quarter renders, not yet in
  game. The renderer does not simulate PAYDAY 2 normal-map lighting, so in-game appearance still
  needs checking. The neck remains unchanged.

### D47 — Group shipped packs and consolidate source archives

- **Decided:** 2026-10-30, by the user (character folders inside `dist/`).
- **Decision:** the user requested character folders inside `dist/`, including a separate `Geralt/`,
  and moved the source archives from `models/` into `references/` (superseding D14).
- The three full-body ZIPs are now `Miranda_L4D2_LAS.zip`,
  `Miranda_L4D2_Busty_LAS.zip`, and `Miranda_Romance_LAS.zip`; their internal mod
  folder names and ZIP bytes are unchanged. The builders, status, previews, checksums,
  CI and release workflow use the new paths. Shared tools remain in `tools/`.
- **Status:** holds; no pack's bytes changed with the reorganisation.

### D48 — Match Romance-over-Hila head skin closer to the Honoko body

- **Decided:** 2026-10-30, by the user, from the render comparison.
- **Decision:** The user asked to bring the head texture colour closer to the body. The active combination is
  Honoko5 and Miranda Romance over Hila. Their exposed upper-neck texture samples differed markedly;
  the builder applies a deterministic, skin-colour-masked RGB gain to the face/scalp quadrants of the
  Romance Hila atlas only. Hair, eyes, gloss alpha, normal maps and all geometry are unchanged; the
  Hila character icon is regenerated from the adjusted atlas. Other head packs are not changed.
- **Status:** holds offline only; the tint is part of the Hila head pack, so it also appears when
  that head is used with other bodies.
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
  untracked and removed. `dist/` holds every tracked pack and sidecar (20 then, 13 now);
  `build/*` is purely scratch.
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
  after its donors.
- **Status:** holds offline. The [compiled-model preview](../renders/honoka/model/over-hila/README.md)
  is offline; masks, armor, animation and performance are still unverified in the game.

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

> **Restored by D70 (2026-11-25).** D62's extension and its D63/D65 reductions are reverted: the
> tracked packs cut on this plane again, with the registration as decided here.
>
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

### D62 — The palms are cut 4 cm past the palm line, so the arm ends inside the glove

> **Superseded by D70 (2026-11-25): the extension is reverted to 0 cm.** The plane, mechanism and
> measurements below remain the record of the D62 bytes; the tracked packs no longer use them.
>
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

> **Superseded by D70 (2026-11-25): the extension is reverted to 0 cm.** The glove measurements
> below still describe the glove in the references archive; the tracked packs cut on the crease.

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

### D64 — The Arivus shave fills from grown beard, matched skin and real structure — no ring, no seam, no flat panel

- **Decided:** 2026-11-25, by the user: *"And improve Arivus more."* The evidence base is the
  offline portrait (`docs/renders/arivus/model/over-hoxton/`), which showed three things reading
  wrong on a clean-shaven ped: a **black crescent around each ear**, a **straight seam** down each
  side of the face and across the jaw, and a **flat, slightly too-bright lower face**.
- **Why they were there, measured on the source raster.** (1) The ear ellipses `(110,210,21,34)` /
  `(419,210,21,34)` are smaller than the painted sideburn over them, and the "ring" pass inpainted a
  band *around* the protected ellipse with `MaxFilter(9)` — so the beard between ellipse and cheek
  stayed dark on a flat skin field. (2) The Laplace relaxation ran only inside `y 130:356, x 128:400`
  and started from **one** median skin tone (`lum 146.8` against the chin's `98.5`), so it ended in a
  hard rectangle and the jaw came out as a single shade. (3) The mask stopped at the geometric
  U-shaped hairline while the painted beard edge is soft, which left a reddish stipple at 30–40%
  coverage across the jaw: the "5 o'clock shadow" a clean shave must not have.
- **Decision:** grow the mask along the beard, then fill it and give it skin.
  `shave_arivus_face` now (a) grows the geometric U through every pixel darker than **90%** of this
  raster's own skin level (`0.90 x 143.5`), limited to the face box and never through a protected
  feature, so the mask follows the stubble to where it fades and stops at the ear's lighter rim
  instead of at an ellipse; (b) relaxes a harmonic fill over that region from the clean skin ring
  around it; (c) matches the fill's level to the mean of that ring, **capped at ±15% gain** so it
  cannot invent shading; (d) adds the high-frequency structure of the raster's cleanest skin patch
  (forehead, mirrored on both axes before tiling so it does not repeat as a grid) at 1.10x; and
  (e) blends the result into the untouched raster over 2.5 px. Lips, nostrils, ears and eyebrows
  are pasted back byte for byte, and the lips are found by measurement, not by a box: the lip
  colour is `redness 52..64` against the moustache's `~35`, occupying `x 210..298, y 252..292`,
  so each column keeps the span from its top lip pixel to its bottom one — lips, mouth slit and
  corners together — with **no dilation**, because one pixel of dilation pasted a dark lip liner
  back on.
- **Measured, not asserted.** In the beard box (`y 250..340, x 145..385`, mouth excluded), pixels
  darker than 72% of skin fall from **73.0%** to **0.48%**. The jaw's high-pass structure is
  **6.40** against the clean cheek's **9.62** (0.67 of it, where before it was zero) and the
  untouched beard's 19.1. The seam check at the mask's bottom row (344) steps **no more than the
  rows inside the face**. The shaved raster is `1a4fa5b16ee25e58` and is identical across runs; the
  pack is **8,436,333 B**, `7056d2476ab5`.
- **Held to:** `tests/test_arivus_shave.py` — the source really is 73% dark in that box, less than
  2% is left after the shave, the jaw keeps 0.4–1.4 of the cheek's structure, the boundary row
  steps no more than twice the interior, the ears, brows and lips change by at most four pixels, the
  alpha channel and the 512x512 layout are untouched, and two runs are byte-identical.
- **Rejected:** the `MaxFilter(9)` ring around the protected ellipses (it rings the feature instead
  of covering the beard outside it); a relaxation confined to a smaller box (the seam moves, it does
  not go); one median tone for the whole U (that *is* the flat jaw); a colour flood fill from the
  mouth's centre (the chin beard matches the lips' redness and `lum 55..165`, so it leaked and
  pasted a goatee back); row-span fills through the mouth oval (they carried the under-lip stubble
  with them); dilating the lip mask (a one-pixel beard ring reads as a drawn outline around the
  mouth); and the closing/opening variants tried between them, which all trade a pale mouth for a
  dark one.
- **Source:** `tools/build_joy_head_mods.py` (`shave_arivus_face`, `ARIVUS_SKIN_PATCHES`,
  `ARIVUS_DETAIL_PATCH`), `tests/test_arivus_shave.py`,
  `docs/renders/arivus/model/over-hoxton/`.
- **Status:** holds offline only. `runtime_verified` stays `false`; the offline render is a software
  Z-buffer with diffuse textures and no lighting rig, so the checklist's Arivus step is what settles
  whether the shave reads as skin in game.

### D65 — The palm cut goes back to 1.25 cm: the arm's fattest half-centimetre was still in the glove's cuff

> **Superseded by D70 (2026-11-25): the extension is reverted to 0 cm.** Only the history below
> remains; the shipped body no longer carries the extra 1.25 cm of forearm.
>
- **Decided:** 2026-11-25, by the user, looking at `OfficeSuite_Head` in game (two first-person
  screenshots with the black FPS-gloves glove): *"pretty close, just need to cut a bit more."*
  The hand was gone and the cuff covered the wrist, but a wedge of skin still showed through the
  glove's cuff at the wrist bend.
- **Why.** D63's 1.5 cm kept a centimetre and a half of the palm, which is where the arm is still
  growing: 3.46 cm in radius at the crease, 4.0 at 1.25, 4.4 at 2.0. The glove's cuff is 3.5 cm at
  its rim and widens more slowly, so the last half-centimetre of the arm is the fattest part of it
  and the part that finds its way through the cuff. Cutting a little more takes that back.
- **Decision:** `PALM_EXTEND_CM = 1.25`.
- **Measured, not asserted:** `clipped_to_cm` 1.25 per side, `kept_to_cm` **0.61** (left) and
  **0.53** (right) after the 5% slim - both still past the glove's 0.42 cm rim, so D60's gap does
  not return - `tris_split` 68, `verts_added` 70, `removed_tris` 2,242, `rim_cap_tris` 74. The
  shipped `g_body` is 31,666 vertices (61,525 after the slim), still with no hand-dominated vertex.
  Packs: `OfficeSuite` 5,737,727 B `d9438879522d`, `OfficeSuite_Head` 10,356,127 B `b21084a4c8d3`,
  `OfficeSuite_Miranda_Romance_over_Hila` 14,828,794 B `77082170d623`.
- **Held to:** `tests/test_palm_cut.py` (1.25 in the record, `kept_to_cm` between 0.45 and 1.25
  **and past 0.42**, the mesh reaching 0.45–1.25 cm, no hand-dominated vertex);
  `tests/test_pd2_las.py` (31,666 / 61,525, `clipped_to_cm` 1.25);
  `tests/test_hila_body_override.py` (the same cut on the override's body).
- **Rejected:** 1.0 cm and below (the slim pulls the mesh back to 0.27–0.33 cm, short of the
  glove's 0.42 cm rim: D60's gap returns); going back to D63's 1.5 (that is the build the user is
  looking at); sliming the wrist itself (inventing geometry at the one place the user can see, and
  the outfit's arm is the donor's).
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`PALM_EXTEND_CM`), `tests/test_palm_cut.py`.
- **Status:** holds offline only; `runtime_verified` stays `false`. The next lever, if a wedge of
  skin is still visible, is the arm's radius at the cut rather than the cut's depth.

### D66 — The shave fills the beard, not the face

- **Decided:** 2026-11-25, by the user, from the in-game portrait: *"Arivus still need work on
  textures."* The face read washed out and flat, with a faint rectangle around it.
- **Why.** D64's mask grew from the beard through every pixel darker than 90% of this raster's own
  skin level. That raster's *whole face* is darker than its own skin level - cheeks, the nose's
  flank, the eye sockets - so the flood ran straight through the face and repainted all of it: the
  nose lost its shading, the cheeks their structure, and the growth's bounding box left a soft
  rectangle from temple to jaw. The fill itself was never the problem; the mask was.
- **Decision:** the growth is a **rim**, not a search: `dark` pixels only within 8 px
  (`MaxFilter(17)`) of the geometric beard - wider than the painted edge, far narrower than a
  cheek. Two consequences were then handled explicitly: (a) the hairs the ped paints onto the skin
  under the lower lip are reddish enough to pass the lip test and were being pasted back as a
  "soul patch", so below the mouth slit (`y > 276`) any pixel darker than 70% of skin is returned
  to the mask; (b) single hairs stranded by the rim limit are swept: inside the filled area (plus a
  2 px skirt), a pixel darker than 80% of the local fill becomes that fill.
- **Measured, not asserted:** the shave now changes 18.9% of the raster instead of 100% of the
  face, the nose and eye sockets keep their original shading, the chin's hair patch goes from
  luminance **94.3 to 123.4**, and the lips/upper-lip/slit pixels are unchanged (≤4). The pack is
  8,433,226 B `6b356c19e0d8`.
- **Held to:** `tests/test_arivus_shave.py` (beard gone, jaw structure, no seam, features intact,
  the chin patch brightened, alpha and layout untouched, reproducible).
- **Rejected:** keeping the face-wide growth and fixing the tone afterwards (the shading it
  destroys cannot be put back); protecting the whole mouth oval as D64 did (it pasted the hair
  under the lip on with it); a red-channel test to separate lip from chin hair (this raster's
  skin sits at redness 44–50 against the lips' 50–64 - too close to threshold).
- **Source:** `tools/build_joy_head_mods.py` (`shave_arivus_face`, `LIP_ROWS`),
  `tests/test_arivus_shave.py`.
- **Status:** holds offline only. Known and left alone: the hairline is the hair mesh's own alpha
  edge, which no texture here can soften, and the ped's painted skin carries compression mottling
  on the cheeks.

### D69 — Arivus: the shaved area takes the skin's chroma, not a new one

- **Decided:** 2026-11-25, by the user, from the offline portrait: *"Work more on Arivus texture - check
  renders."* D66 removed the beard, and the portrait still read as soot on the cheeks and jaw.
- **Why.** Two things were still in there. (1) The fill's chroma came from `ARIVUS_SKIN_PATCHES`, whose
  median is the *pale forehead* — (172, 134, 123) — while the clean skin the jaw meets is
  (148, 105, 90): a meter of red that reads as grey next to its neighbours. (2) The rim could only
  follow the painted edge, and the mirrored detail pass re-added the clean patch's grain at 1.1×, so
  what survived of the stubble read as dirt rather than as a shadow.
- **Decision:** the shaved area keeps its own luminance — every wrinkle, every shadow — and is pulled
  **68% of the way to this raster's own skin chroma**, measured from a ring of clean skin just outside
  the mask rather than from the whole-face patches. The level is then matched to that same ring
  (±10%), and the mask is feathered over 5 px rather than 2.5. The first attempt flattened the field
  instead and the result was worse: a grey, airbrushed rectangle against untouched skin, which the
  portrait showed immediately — so the flattening was reverted to this blend.
- **Measured, not asserted:** jaw patch luminance **64.8 ± 41.4 → 110.5 ± 6.1**, its redness
  **31.1 → 41.6** (the clean ring's own is ~40), and the shaved field's mean colour
  **(136.9, 101.1, 89.5)** against the jaw ring's measured **(148, 105, 90)** and the pale patch
  **(172, 132, 123)** the D66 code had been matching — one skin, not a patch, and nine points under
  the pale one rather than a flood of it. The lips, brows, nostrils and ears are pasted back verbatim.
- **Held to:** the twelve tests in `tests/test_arivus_shave.py` (beard gone, jaw structure, no seam,
  features intact, chin brighter than the beard, alpha and layout untouched, reproducible).
- **Rejected:** flattening the field to one tone (grey rectangle); keeping D66's whole-face skin median
  as the chroma (a shade cooler than the cheeks); a global blur (it takes the wrinkle structure with
  it).
- **Source:** `tools/build_joy_head_mods.py` (`shave_arivus_face`, the "one even skin field" pass).
- **Amended the same day, from the render.** Three follow-ons, each from looking at the sheet rather
  than at the numbers. (1) The blend is **faded** outward from the mask over ~9 px instead of stamped
  on a mask grown by `MaxFilter(9)`: the grown zone is binary, so it leaves a soft rectangle of its own
  — the same failure by another route. (2) The sideburn boxes (`xx 318..396`) stopped short of the ear,
  which left a strip of painted stubble in front of it; they now reach the ear (`318..414`, mirrored on
  the other side to `118`, `yy 140..344`) and rely on `protect` to stop at the ear's rim. (3) The dark
  band that is *still* in front of the ear on the 3/4 view is **not** texture: the ped's hair half of
  the atlas carries 5,952 triangles whose vertices reach down to z ≈ 169.5, i.e. modelled sideburn
  cards, and the shave only touches the painted beard. They stay — the user's rule for this pack is
  texture, not mesh.
- **Status:** holds offline; the in-game face check is still the user's call. Known and left alone: the
  hairline is the hair mesh's own alpha edge, the forehead's shadow band is the hair mesh's shadow, and
  the sideburn cards in front of the ears are geometry.

### D70 — The palm extensions are reverted: the cut is on the crease again

- **Decided:** 2026-11-25, by the user, from a first-person screenshot of
  `OfficeSuite_Head`: *"I want you to revert extensions, before 4 cm (D62)"*. The shot showed
  a wedge of bare arm on the far side of the white glove at the wrist; the D65 cut had left
  skin inside the cuff and it still read as skin over the glove.
- **Why.** D62 put the cut 4 cm past the palm line to close the gap D60 showed in game.
  D63 reduced that to 1.5 cm when the arm came through the glove, D65 to 1.25 cm when a
  wedge still showed. Each step kept some of the forearm's skin past the wrist crease, and
  the user's answer to all three is to keep none of it: return to D60's landmark and let
  the cut end where the palm begins.
- **Decision:** `PALM_EXTEND_CM = 0.0`. `clip_group_at_palm_bases` splits on the plane
  through the rig's `Hand` joint, perpendicular to the palm axis, and `_cap_cut_rims` caps
  the ring there. No new geometry, no adapter and no change to the registration: the packs
  still hide the stock hands and a glove the player picks is what puts hands on them
  (D58/D60). The Hila override inherits the same body and keeps its own `g_hands`.
- **Measured, not asserted:** the rebuild reproduces D60's cut on all three packs:
  `margin_cm`/`extend_cm` 0.0, `clipped_to_cm` 0.0 per side, `kept_to_cm` -0.76 (left) and
  -0.79 (right) after the 5% slim — the surface stops just *short* of the crease because
  the slim pulls it towards the bones — `tris_split` 64, `verts_added` 66,
  `removed_tris` 2,276, `rim_cap_tris` 68, and a shipped `g_body` of 31,643 vertices
  (61,479 after the slim). The cut removes both hands' fingers and a handful of
  forearm-dominated rim vertices; no hand- or finger-dominated vertex survives.
- **Held to:** `tests/test_palm_cut.py` (0.0 in the record, the clip on the plane, the
  shipped mesh at or proximal of the crease, no hand-dominated vertex),
  `tests/test_pd2_las.py` (the body and slim vertex counts, `clipped_to_cm` 0.0),
  `tests/test_hila_body_override.py` (the same cut on the override's body).
- **Rejected:** keeping any positive extension, including D65's 1.25 cm (the reported
  wedge); shrinking the arm's radius to fit a glove the pack does not ship; changing the
  registration or spawning a glove by default (D58/D60).
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`PALM_EXTEND_CM`),
  `tools/pd2-las/tmc_las.py`, `tests/test_palm_cut.py`, `tests/test_hila_body_override.py`.
- **Status:** holds offline only; `runtime_verified` stays `false`. The D62 and D65 builds
  are the ones that were seen in game, these bytes have not been. The D60 gap that
  motivated D62 is the known trade-off of this choice; the wrist step of the in-game
  checklist records what to look for now.

### D72 — Arivus: the beard is found, the rectangle and the collar gap are gone

- **Renumbered:** drafted as D70 on the parallel branch; main uses D70 for the palm
  reversion and D71 for the character VO packs.

- **Decided:** 2026-11-25, by the user: *"I want you to improve Arivus head mod. Check renders for
  mistakes."* The compiled-portrait sheet was the evidence. Three mistakes were visible in it: a
  dark rectangular field over the lower face with its top edge across the cheeks, a painted dark
  strip in front of each ear, and a strip of skin with a jagged top edge showing through the back
  of Old Hoxton's collar. A fourth showed up only in the atlas: pale blobs beside the nose and a
  straight inpaint edge at each temple.
- **Why.** (1) D64's "geometric U" is not the beard's outline: its anchors run from `(135, 148)`
  diagonally to the moustache at `y ≈ 235`, and the sideburn boxes were 88 px wide (`118..206`,
  `318..414`, `y 140..344`). Between them they masked the clean cheeks, eye corners and nose bridge;
  the feature ring dilated another 8 px over that. Feathering 9 px cannot hide a mask that big, so the
  face came out as one rectangle under a pale forehead. (2) The ear ellipses (`cx 110/419`, `rx 21`)
  covered the painted hairs in front of the ears, so those hairs were pasted back byte for byte.
  (3) The neck is cut at `z ≈ 159.4` cm; from behind, the suit's collar rim has an opening through
  which the *front* of that neck was visible as skin with a jagged top.
- **Decision:** stop drawing the beard by hand. `shave_arivus_face` now seeds on the raster's own
  dark hairs (`lum < 0.70 × skin`) and floods through the softer stubble (`0.86 × skin` on the jaw,
  a tighter `0.78 × skin` at the temples), **only inside the zone a beard can occupy** — the lower
  face and narrow strips in front of the ears. A close/open pass bridges the gaps between hair
  strokes, the feature ring is confined to that zone, and only the cheek-facing edge of each ear
  ellipse is given up: ear pixels are kept by their pink chroma (redness ~37..49) while the darker,
  low-redness hairs overlapping the ellipse are inpainted. The two dark ticks the lip column-span
  used to protect at the mouth's corners are given back too, without touching the central slit.
  For the collar, the extracted neck's cut edge is lowered 6 cm with a smooth fade out by `z = 166`,
  then the neck below `z = 168` is shortened 4 cm so no surface sits inside the back opening while
  the throat still reaches the front of the collar. Face and hair vertices are untouched.
- **Measured, not asserted:** in the beard box (mouth excluded) pixels under 72% of skin fall from
  **73% to 1.1%**, and the hair strokes' high-pass energy from **18.2 to 7.2**. The eyes and nose
  bridge are byte-identical to the source; the jaw fill goes from **(91, 62, 52)** to
  **(152, 110, 95)**, i.e. skin at the level of the cheeks it meets. The shaved raster is
  `9083aa578e2eb6ac`; the pack is **8,429,027 B**, `ad4cb8afafdc` (was 8,420,283 B, `55cc0fc55b35`).
  In all three shipped models the head's lowest vertex is now at **z ≈ 157.4 cm** and there is no
  back-half neck vertex below z 164 inside the collar opening, while ≥3 throat vertices remain
  below z 160 in front.
- **Held to:** `tests/test_arivus_shave.py` (16 tests: beard gone, jaw structure, no seam, features
  intact, the clean upper face repainted in <10% of any reference box, alpha and layout untouched,
  reproducible) and `tests/test_arivus_neck_fit.py` (the collar fit on the heist, menu and chill
  models). Sheets re-rendered with `--unified`.
- **Rejected:** widening the sideburn zone to `x 185/345` (a flood through the temple's own shadow
  left a *wider* straight edge); shrinking the ear ellipse (it erased the ear's inner detail along
  with the hair); clipping low neck triangles (the teeth survived in the triangles that straddled
  the opening); raising the neck on its own (it closed the back gap but opened one at the throat);
  raising the suit's collar mesh (a change to shared body geometry for a defect in the donated head).
- **Source:** `tools/build_joy_head_mods.py` (`shave_arivus_face`, `extract_arivus_part`),
  `tests/test_arivus_shave.py`, `tests/test_arivus_neck_fit.py`,
  `docs/renders/arivus/model/over-hoxton/`.
- **Status:** holds offline; the in-game face and collar checks in
  [`docs/pd2-las/in-game-checklist.md`](in-game-checklist.md) are still the user's call. Known and
  left alone: the hair cards' triangular shading and the hair mesh's alpha hairline are geometry,
  and this pack changes texture and neck fit only.


### D79 — Arivus: the neck is a neck again, and the head is skinned to its own palette

- **Decided:** 2026-11-26, by the user: *"What's with the neck of the Aivus head mod. Check renders"*,
  then *"Fix everything"*. The evidence was the tracked sheet: a hard angular line across the
  collarbones in the front and three-quarter panels, a short throat, and from behind either a strip
  of skin or a jagged patch depending on which build you looked at.
- **Three defects, not one.**
  1. **D72 squashed the neck.** `extract_arivus_part` pushed every vertex below `z 166` down by up to
     6 cm and lifted every vertex below `z 168` by up to 4 cm — with `z` re-evaluated *after* the
     first move — so a net −3.0 to −4.3 cm displacement turned a smoothstep into a shear. That
     squashed ~10 cm of neck into half its height, kinked it at z 166–168 (the crease across the
     throat) and still left the ped's cut edge in the collar opening.
  2. **The cut is a V, and the collar only reaches the front of it.** The Random4 ped's neck ends at
     `z 159.4` across the throat but at `z ≈ 164.9` at the back, while the suit's collar rim tops out
     at `z ≈ 159.8–160.5`. From behind, the back of the V stands *above* the collar, and the
     opening looks straight into the neck — the skin band is the throat's own far wall, i.e.
     back-facing interior geometry, not a strip of the near surface.
  3. **The head weighed the wrong bones.** `bone_offset=1` assumed a palette beginning at `Hips`,
     but this drawable's `SkinBones` section lists exactly `[Spine2, Neck, Head]` (ids 40, 41, 42)
     with root 37. 4,595 of 4,596 vertices therefore carried `BLENDINDICES 3`, one past the end of a
     three-entry palette. D73's GLB exporter saw this and repaired it on its own copy; the shipped
     pack was untouched, and no render can see it because bind-pose cancels the skinning matrices.
- **Decision:** leave the ped where it lands and close the neck from below.
  - `bone_offset=0`, so every vertex indexes a palette slot that exists.
  - `push_neck_rim` drops the cut rim's vertices to `z 159.0`, at full weight from 60° either side of
    the back and fading to nothing across the throat, so the back of the V ends under the collar and
    the throat keeps its length. Only the neck's own ring is touched: the loop that also runs up the
    back of the head to `z 186` is split off first.
  - `extend_neck_into_collar` welds the extracted part (the extraction is triangle soup, so the rim
    only exists as an open edge after `deduplicate_mesh`), takes the connected boundary loop owning
    the neck's lowest vertex, and stitches one skirt ring: each rim vertex moves radially inward
    about the ped's neck axis `(0, 1)` to 0.35 of its own radius, down to `z 148.0`. Inward, not
    outward — the suit closes around the neck below the collar, so a skirt that widens pushes
    *through* it, while one that tucks goes inside.
- **Measured, not asserted.** A ray-parity test against the suit's own `g_body` (odd crossings along
  ±x and ±y, i.e. genuinely enclosed) says **23 of 23** skirt vertices are inside the suit on all
  three shipped models, and all four rendered views are clean. The ped's own neck height is back:
  the throat's front reaches `z 166` again instead of 163.4. The pack is **8,543,738 B**,
  `c1630f56289b` (was 8,540,550 B, `31127712ab92`).
- **Held to:** `tests/test_arivus_neck_fit.py` (12 tests, three models × four properties: no cut-rim
  edge above the collar, the skirt enclosed by the suit, the throat not squashed, every blend index
  inside the palette). All 12 pass on these bytes and **8 of them fail on the D72 bytes** — the neck
  test now measures what the renderer would show, not how many vertices sit at a given height, which
  is what let D72 regress quietly. `tests/test_arivus_glb_pack.py` asserts the GLB's skin has **3**
  joints and no repair warning; it said 4, which was the bug.
- **Rejected:** welding positions only (it merges the seam across two UV islands — the D72-era note in
  `HANDOFF.md`); clipping the low neck triangles (the teeth survive in the triangles that straddle
  the opening); widening the skirt outward (measured: 15% of columns always end outside the suit);
  dropping the skirt to `z 146.5` (the suit stops surrounding the neck at ~148, so the ring leaves
  its lower half in the open); rebuilding the three models with a taller neck (the donation has no
  more neck to give).
- **Source:** `tools/build_joy_head_mods.py` (`extract_arivus_part`, `push_neck_rim`,
  `neck_skirt_ring`, `extend_neck_into_collar`, `_neck_rim_loop`), `tests/test_arivus_neck_fit.py`,
  `tests/test_arivus_glb_pack.py`, `docs/renders/arivus/model/over-hoxton/`.
- **Status:** holds offline. Still not seen in game — the neck's motion under the `Neck`/`Head`
  bones and the way the game's own culling treats the skirt are the in-game checks in
  [`in-game-checklist.md`](in-game-checklist.md).

### D82 — The native Hila override is retired; `OfficeSuite_Head` carries the same body and head

- **Decided:** 2026-11-26, by the owner: *"You can delete `OfficeSuite_Miranda_Romance_over_Hila.zip`"*
- **Decision:** `dist/Miranda/OfficeSuite_Miranda_Romance_over_Hila.zip` is gone, with its sidecar, its
  table row, its `hila` make target, its `tasks.py` entry, its builder (`tools/build_hila_body_mod.py`)
  and its render. Tracked zips go from thirteen to twelve.
- **Why:** it was the only pack that combined OfficeSuite's body with the ME2 Romance head on Hila's
  own unit with no LAS, and both halves of that already ship: `OfficeSuite_Head` is the same body,
  the same palm cut (D70) and wrist pass (D75) and the same head as one registered `WHOLE_CHARACTER`
  unit, and `Miranda_Romance_over_Hila.zip` is the head on its own. What the retirement cost is the
  no-LAS install route, not any content.
- **The head donor moved with it, and provably changed nothing.** `OfficeSuite_Head` read its head from
  the retired pack. The two over-Hila replacements carry a byte-identical `g_head` `MODEL_DATA`
  payload (sha256[:16] `8125a6c6cb6066f7`), name the same `npc_criminal_ecp_female_head_df/_nm` and
  `_lashes_df` maps, and those four textures hash identically, so
  `tools/pd2-las/build_honoko2_dae.py` now reads `Miranda_Romance_over_Hila.zip`. Rebuilt from it,
  `OfficeSuite_Head` differs from its previous bytes in **one member and two lines** —
  `BUILD_INFO.json`'s `head.donor` and `head_donor` strings; all 28 other members are byte-identical.
- **What survives in code:** `las_head.read()` reports its donor as a parameter (`donor_name`) instead
  of a literal, so no report names a pack that is not there. The `heads` target no longer depends on a
  `hila` target; `honokodae_head` depends on `heads`, which is where its donor is built.
- **Kept:** the renders of the retired pack.
  `docs/renders/honoka/model/over-hila/officesuite_miranda_romance_over_hila_sheet.png` is deleted
  with the sheet that produced it, and that folder's README is now the record of what the pack was
  and why it went; dated records (`docs/audits/`, earlier MODLOG entries) keep the old name, as they
  keep every name the repository used at the time.
- **Rejected:** keeping the pack as an unmaintained second route (it would have kept a builder, a
  make target and a donor dependency alive for content `OfficeSuite_Head` already serves); deleting
  `Miranda_Romance_over_Hila.zip` too (it is the head donor, and a pack in its own right); rewriting
  the retired name out of dated documents.
- **Source:** `docs/pd2-las/ADD-A-PACK.md` §"Retire a pack"; `tools/pd2-las/{packs,status,fresh}.py`;
  `tools/pd2-las/Makefile`; `tools/build_honoko2_dae.py`; `tools/pd2-las/las_head.py`;
  `tests/test_one_implementation.py`.
- **Status:** superseded by D83: the pack it kept, `OfficeSuite_Head`, is retired too.

### D83 — The Romance line is retired, and the tracker chain that only it used

- **Decided:** 2026-11-26, by the owner: *"You can delete Miranda_Romance, … Miranda_Romance_over_Hila.zip
  and … OfficeSuite_Head.zip"*, choosing both Romance packs and confirming the head pack goes too.
- **Decision:** `dist/Miranda_Romance/Miranda_Romance_LAS.zip`, `dist/Miranda/Miranda_Romance_over_Hila.zip`
  and `dist/Miranda/OfficeSuite_Head.zip` are gone with everything that existed only to build, verify,
  render or document them: the `lawson` and `honokodae_head` make targets and their `tasks.py` entries,
  `tools/pd2-las/lawson-las.yml`, the Romance builder in `tools/build_joy_head_mods.py`, `las_head.py`,
  `tests/test_las_pack.py`, five render paths, and the Romance-only half of `tools/pd2-port/`
  (`build_las_pack.py`, `rig_target.py`, `las_model.py`, `preview_check.py`, `shade_check.py`,
  `check_guide_compliance.py`, `check_nm_convention.py`, `check_test_suite_mutations.py`). Tracked zips
  go from twelve to nine.
- **Why:** the owner asked for the packs to go. `Miranda_L4D2_LAS` is the LAS outfit the project ships,
  the ME2 Romance character has no LAS route left to serve, and `OfficeSuite_Head` existed to give the
  OfficeSuite body a head on its own — a route D82 had already reduced to a donor of the pack that is now
  gone as well.
- **What the head donor proved on its way out:** the `g_head` `MODEL_DATA` payload in
  `OfficeSuite_Head` and in `Miranda_Romance_over_Hila` was byte-identical (sha256[:16]
  `8125a6c6cb6066f7`) and their four head textures hashed identically, so D82's donor swap changed
  only two `BUILD_INFO.json` lines. Deleting both costs no content that is not also in
  `Miranda_L4D2_over_Hila` or `Miranda_L4D2_LAS`.
- **What survives:** `Miranda_L4D2_over_Hila` is the only over-Hila head and the only pack that carries
  the supplied `EYE_Diff.png`; `Miranda_L4D2_LAS` is the only LAS outfit. `tools/pd2-port/` keeps the
  archive reader (`dds.py`, `dmodel.py`, `me2_dae.py`), the link gate, the skip budget and the geometry
  check — `check_all.py` now runs on whatever pack it is pointed at, with no default. `status.py`'s
  `LAS_TARGETS` is `("build", "honokodae")`, one outfit.
- **Kept, as history:** `docs/audits/`, earlier `DECISIONS` and `MODLOG` entries and the two READMEs
  under `docs/renders/*/model/over-hila/` keep the names they were written with; live documents are
  rewritten to the nine packs. The retired sheets are in git at `5272168` (LAS, head) and `c26b990`
  (render tree before this change).
- **Rejected:** keeping `OfficeSuite_Head` as the head donor for a pack that no longer exists; keeping
  `pd2-port`'s Romance-shaped checks as a record (their subject was one pack, and the link gate, the skip
  budget and the geometry gate carry the checks that still apply); rewriting the retired names out of
  dated records.
- **Source:** `tools/pd2-las/{packs,status,dist_paths,fresh,tasks}.py`; `tools/pd2-las/Makefile`;
  `tools/render_mod_previews.py`; `tools/pd2-port/{README,STATUS}.md`; `docs/pd2-las/HANDOFF.md`;
  `tests/test_agent_docs.py`, `tests/test_pack_paths_resolve.py`.
- **Status:** holds; `dist/` is nine zips and every one of them rebuilds. D82 is superseded: neither the
  native override nor the pack that replaced it is tracked.

## Voice lines and the stream packs

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

### D67 — `call_teammate.hey_you` is one shouted word, not a phrase

- **Decided:** 2026-11-25, by the user, after hearing the re-picked line: *"She just needs to
  shout 'you'."* The slot had shipped 0.667 s of "you take point" and the report heard "just you".
- **Why.** The clip was not cut short — decoded out of the shipped `.stream` it is 0.29 s with three
  syllables intact — so the game is stopping the line well before the file ends, and any line longer
  than a word will be heard as its first word. The slot is a call-out (*Call* summons a teammate), so
  one emphatic "You" is the whole correct answer, and a short one cannot be truncated into anything
  else. The pack has no "hey" in its 866 transcripts (`hila_call_hey_you.csv`, README), so "Hey, you."
  was never available as such.
- **Decision:** the pick is the **"You" of "You don't know what my father wants for her."** -
  `twrvxl_oldfriend_d_S_INT.043.ogg`, `0.000-0.300` - measured at 10 ms: the /j/ onset at 0.06, the
  stressed /u/ within 3 dB of the file's peak at 0.16-0.20, and the decay into the /d/ closure at
  0.29-0.31, which is where the cut ends ("don't" starts at 0.33). Chosen over "You'll die for that,
  bitch!" (same delivery, but the /l/ is audible) and over "You ass." (the word is 60 ms there, too
  short to be a call).
- **Measured, not asserted:** the shipped clip is **0.289 s at -1.4 dBFS peak**; the pack rebuilds to
  12,608,121 B `6b7d827dfe93` (was 13,926,249). 158 ids carry it.
- **Held to:** `tests/test_hila_cut_edges.py::test_the_hey_you_line_is_one_shouted_word` (silent head,
  the vowel at the loudest point, the tail inside the closure, "don't" still at 0.33 s, 0.20-0.40 s).
- **Rejected:** keeping three words and trusting the game to play more of it (it does not);
  synthesising a "you" (the pack is one voice, unprocessed); skewing the clip's length (a shorter file
  does not make the game play more of it).
- **Source:** `voice_lines_vox/miranda_lawson/slot_picks.csv`, `tools/fit_hila_intents.py`,
  `tools/build_hila_stream_mod.py`.
- **Status:** holds offline only; heard by the user only after the next in-game pass.

### D68 — The Hila stream pack ships 61 slots: LAWSON VOICE takes in, sub-8 slots out

- **Decided:** 2026-11-25, by the user, after the semantic-fit round: *"remove everything that is worse
  fit than 8. Use LAWSON VOICE (PAYDAY 2).7z"* and, on the scope question, "every slot with a take in the
  archive — including slots that scored 8+ — gets it".
- **Why.** `hila_semantic_fit.csv` scored all 78 slots against game intention (engine event from
  `slot_event_ids.csv` plus the dominant PD2 category), not against Hila's wording; 36 scored below 8.
  19 of those had a take in the new archive; 17 did not, and for those the pack had only closest-ever
  compromises. The new archive exists precisely for the slots the source pack could not carry
  (`references/LAWSON VOICE (PAYDAY 2).7z`, purpose-authored Mira Lawson barks).
- **Decision:** (a) every slot with a take in the archive — all 36 that map onto picks, ≥8 scorers
  included — ships that take, whole, with 30 ms of the file's own leading silence and 50 ms of its
  trailing silence kept, peak-matched to −1.5 dBFS with the existing clamps; the 5 call-tagged takes
  map as `uffs..` → `cop.cuffs`, `nees..` → `cop.kneel`, `Tazer` → `mark.taser`, `gun_` → `cop.drop`,
  `Now._.` → `tech.fix`. (b) The 17 slots below 8 with no take are **removed from the pack entirely**:
  their ~162 ids are absent from `soundbanks/streamed/regular_vox/`, so vanilla Hila plays them —
  recorded in `removed_slots.csv` with the clip each slot used to play. (c) The semantic-fit table now
  carries a `status` column (`kept` / `replaced_tts` / `removed`).
- **Measured, not asserted:** the pack rebuilds to **14,405,864 B `3779f6a969f8`** — 699 `.stream`
  files (885 ids − 27 Vorbis − 162 removed, the three shared counted once), 661 s of audio, 61 slots,
  ids sharing a slot sharing identical bytes. `hila_slot_pieces.csv` is the re-picked window record;
  `removed_slots.csv` carries the 17 slots.
- **Held to:** `tests/test_hila_voice_picks.py` (picks ∪ removed covers the cut table, no slot in both,
  no rank names), `tests/test_hila_stream_pack.py` (699 streams, removed ids recorded `removed:` in the
  manifest with `stream_bytes 0`), `tests/test_hila_cut_edges.py` (`civ.down` and `civ.nophone` are now
  the whole TTS takes, verified against the archive). `tools/hila_voice_clips.py`,
  `tools/fit_hila_intents.py` and `tools/build_hila_stream_mod.py` all read `removed_slots.csv`.
- **Rejected:** keeping the sub-8 takes and shipping them anyway (the user's explicit instruction);
  substituting takes from `ARIVUS VOICE (PAYDAY 2).zip` / `GERALT VOICE (PAYDAY 2).zip` (not sanctioned);
  deleting the removed slots from the cut table (the table is the authoritative ID → slot map; removal
  is enforced at pick/build time, so a take recorded later can revive a slot); folding D67's one-word
  rule away (unaffected).
- **Source:** `voice_lines_vox/miranda_lawson/slot_picks.csv`, `removed_slots.csv`,
  `hila_semantic_fit.csv`, `tools/build_hila_stream_mod.py`.
- **Status:** holds offline only; the rebuilt pack has NOT been heard in game — the user's call.

### D71 — The character packs write the shared bank, and only one pack ships at a time

- **Renumbered:** drafted as D70 on the parallel branch; D70 is the palm-reversion entry on main, so this one is D71.
- **Decided:** 2026-11-25, by the user, after the Hila rounds: *"I also want VO mod for Geralt over Rust
  and Arivus over Hoxton (not the brother to Dallas - Huston)"*, then choosing from the options: Rust =
  the punk heister (`npc_criminal_wild_1`, the `Geralt_over_Rust` head-pack target); Arivus over **Old
  Hoxton** (`mtr_old_hoxton`, the `Arivus_over_Hoxton` head-pack ped) — not Victor Hoxton, Dallas's
  brother; the **same route as Hila** (the id-keyed `.stream` pack, not the BeardLib prefix route);
  uncovered slots stay **vanilla**; the name-callout takes wire into `call_teammate.hey_you`.
- **Why.** The purpose-authored sets (`references/GERALT VOICE (PAYDAY 2).zip`, "Геральт", CP866 file
  names; `references/ARIVUS VOICE (PAYDAY 2).zip`) cover only part of the slot taxonomy — shipping a
  closest-available compromise for the rest was rejected by the user, and forcing coverage via
  unrelated takes is what produced the sub-8 problem D68 cleaned up. Both sets are authored for their
  slots, so their takes ship without a scoring round.
- **Decision:** one pack per set, built by `tools/build_character_stream_mod.py` (`--pack
  geralt-rust|arivus-old-hoxton`), same container/format as D68: IMA ADPCM `.stream` per **shared
  `regular_vox` id** — the same ids the Hila pack writes, which makes the three **alternatives, not
  companions** (install one; last loaded wins). Ids of uncovered slots stay vanilla; the 27 Wwise
  Vorbis ids stay vanilla as before. The ARIVUS pack borrows the GERALT set's 'Hoxton.' callout for
  `call_teammate.hey_you` (per the user's mapping; that one slot is Geralt's voice); the GERALT pack
  leaves `hey_you` vanilla — no Rust name take exists yet. The Hila pack and its builder are
  untouched, and the sub-8 removal (D68) is per-archive: it does not transfer (the Geralt pack ships
  `kill.taser`/`mark.taser`).
- **Measured, not asserted:** `Geralt_VO_over_Rust_Stream.zip` — 315 streams, 584 s, 49 slots uncovered
  (546 ids), `737f1fb13616…`; `Arivus_VO_over_Hoxton_Stream.zip` — 324 streams, 442 s, 59 slots
  uncovered (540 ids), `9e04ccfde24b…`; both reproducible byte for byte; 885-row manifests agree with
  the zips; peaks within −1.97…−0.32 dBFS after the −1.5 dBFS match.
- **Held to:** `tests/test_character_stream_packs.py` (coverage invariants, the alternatives-not-
  companions README line, manifest vs streams, ADPCM headers).
- **Rejected:** the BeardLib `<Sounds prefix="rbXX">` route for per-heister targeting (it failed silently
  for Hila, D61); a `char_wild` bank guess (no evidence it exists; the user chose the shared route);
  borrowing Geralt takes to fill the Arivus gaps beyond the mapped callout; scoring the purpose-authored
  takes against game intention (they exist to be the answer).
- **Source:** `voice_lines_vox/geralt/slot_picks.csv`, `voice_lines_vox/arivus/slot_picks.csv`,
  `tools/build_character_stream_mod.py`, `docs/pd2-voice-mod-install.md` §8.
- **Status:** holds offline only; neither pack has been heard in game. **Whether Rust barks from
  `regular_vox` is unknown** — if his voice is vanilla in game, he is not on the shared bank and this
  route cannot cover him; the fix is a dedicated-bank variant once the bank is known.

### D73 — The stream tables are tracked, and the Rust bank question stays open

- **Decided:** 2026-11-26, by the user: *"find stream tables for Rust and Hoxton for the VO mod"*,
  in the session that had just shipped the two character packs (D71) with the shared-bank keying
  and no table to read the ids from.
- **Why.** A `.stream` pack's whole contract is a file name: `soundbanks/streamed/<bank>/<id>.stream`.
  The fork had the *event* table (`slot_event_ids.csv`, D61's failed route) and the shared id list
  (`hila_intent_cuts.csv`), but nothing that said, per target heister, which bank folder and which
  numeric ids its lines live in. That is exactly the question a "rust stream table" or a "hoxton
  stream table" asks, and answering it by hand once is how a pack drifts from its zip.
- **Found.** Two banks, never interchangeable: `regular_vox` (shared, one id set, every heister's
  pack on it replaces everyone's line) and `char_<module>` (dedicated, its own ids —
  `char_rust`, `char_sydney`, `char_joy` … in the community Wwise bank dump, `Javgarag/pd2-mods`,
  `resources/wwise-ids/`). `references/Marine VO for Rust.7z.001+.002` is a reference Rust pack
  carrying 1,046 `char_rust` ids plus a `<Sounds>` module whose only entry is `g36x_any`
  (`prefix="rb16"`) → four `rust_med_kill` OGGs. Measured overlap between `char_rust`'s ids and the
  shared `regular_vox` ids (the 885 the packs write): **0**. The `rb` numbers are Wwise switch
  values, not folder names. No `char_hoxton` exists in the bank dump, so Old Hoxton stays
  shared-bank.
- **Decision:** `tools/build_stream_tables.py` (make `voices_tables`) writes the shared table per
  target, tracked: `voice_lines_vox/targets/rust_shared_regular_vox.csv` and
  `old_hoxton_shared_regular_vox.csv` — 885 rows each, `written=yes` on exactly the 315 / 324 ids
  the tracked zips carry, the 27 Vorbis ids and unpicked slots marked vanilla, and
  `dedicated_bank` naming the folder a heister's own bank would be. A `dedicated` table is only
  ever *measured* from a reference pack (`--bank dedicated --dedicated <mod>`); it is not generated,
  because ids of a dedicated bank cannot be derived. One is tracked:
  `voice_lines_vox/targets/rust_dedicated_char_rust.csv`, the 1,046 `char_rust` ids of
  `references/Marine VO for Rust.7z.001` + `.002` (py7zr joins the volumes).
- **Measured, not asserted:** `tests/test_stream_tables.py` — the id sets equal `hila.load_ids()`,
  `written` equals each zip's `.stream` file names, no Vorbis id is claimed, the dedicated-table test
  skips when no measured table is tracked, and the doc names the tables, the folders and the
  switches. The 0-overlap figure is from the reference archive, not from a document.
- **Rejected:** deriving the bank from the switch (`rb16` → `char_rb16`: a folder the game does not
  read); treating the reference Rust pack's `char_rust` as proof that Rust's *heister barks* stream
  from there (it also carries objective callouts; nobody documents which lines move); writing an
  empty `char_hoxton` table (no such bank is listed anywhere); re-keying the tracked packs onto a
  dedicated bank before the question is settled (the shared pack works for the crew and is inert
  for Rust at worst).
- **Source:** `tools/build_stream_tables.py`, `voice_lines_vox/targets/`,
  `docs/pd2-voice-stream-tables.md`, `tests/test_stream_tables.py`, `references/Marine VO for Rust.7z.001`.
- **Status:** holds offline; **which bank Rust barks from is still an open question** (D71), and the
  in-game check that settles it is `docs/pd2-las/in-game-checklist.md` 1e.

### D75 — The wrist twists on `ForeArmRoll`, and its ring is centred on the glove: OfficeSuite's cuff fix

- **Decided:** 2026-11-26, by the user, from four in-game captures: *"I like Combine Idea 1 + a
  gentle Idea 2."* The captures show `OfficeSuite` in first person with white buttoned dress
  gloves: a sliver of the outfit's own wrist stands through the glove's cuff in the weapon poses
  (`image-1`, `image-4`), while the menu's third-person turntable (`image-2`, `image-3`) looks
  nearly clean.
- **Why the gloves are not at fault.** The outfit's wrists are cut on the rig's palm plane (D59/D60,
  extended and reverted at D62-D70), and the pack ships no hands, so what a glove does at the cuff
  decides everything. Measured on the built mesh, the circle of skin the cut leaves is the right
  size but sits off-centre: its centroid is 0.28 cm from the rig's `Hand` joint on the left wrist
  and 0.54 cm on the right, because `retarget_maps` fits *one* rigid matrix per segment to both of
  the source forearm's joints - on a 20 cm forearm a 1.75 deg angular error does that, and it lands
  Honoka's wrist 3.4 cm from where the 2B rig's is. The widest sector of that offset ring faces the
  dress gloves' button slit, which is the sector the captures show. On top of it the forearm was
  still 100% `ForeArm` right up to the crease, where vanilla Sydney's own body has been handing the
  distal forearm to `ForeArmRoll` since `u = 0.37` (full by `u = 0.80`) - so the outfit's wrist
  stayed rigid while a glove's cuff turned with the forearm.
- **Decision: one pass, after the slim** (`build_honoko2_dae._wrist_pass`). Three things, none of
  them on the cut:
  1. **Twist.** Over `u` 0.35 -> 0.95 of the forearm, `ForeArm`'s weight hands over to
     `ForeArmRoll` (the rig's twist bone, a child of `ForeArm` halfway down it), which is vanilla
     Sydney's own curve. The gold bracelet rides the forearm *and* its roll, so it rotates with the
     wrist like a ring does - it is never bent.
  2. **Hand.** Over `-3.2 .. -0.6 cm` of the palm's own axis, the wrist skin blends up to 0.30 of
     `Hand` - the bone a glove is bound to - so in a bent-wrist pose the skin goes where the cuff
     goes instead of lagging into it. It stops at 0.30, not 0.48: measured against four gloves, a
     larger majority of `Hand` *increases* protrusion, because the skin then swings on the glove's
     pivot and its rim flares out of the cuff. Under 0.5 also keeps every wrist vertex dominated by
     `ForeArmRoll`, which `tests/test_palm_cut.py` and `tests/test_hila_body_override.py` require.
  3. **Tuck and centre.** Over the same stretch the skin is pulled in 0.35 cm towards the palm's
     axis (gentle Idea 2 - it is a 5 cm-wide wrist, not a rope), and the ring the cut leaves is
     re-centred on the palm's axis by exactly the offset measured on that ring. The tuck fades out
     over the last half centimetre of radius so the rim's cap vertices never cross the axis.
  Both run on the outfit and the shadow caster, are restricted to the skin's own slice (the
  bracelet only takes the twist), and keep every vertex at four influences or fewer.
- **Ordering, and why it matters.** The pass runs *after* `_slim_groups`. The slim pulls each vertex
  towards the rest point of the bones carrying it, and `ForeArmRoll`'s rest point is 10 cm down the
  forearm from `ForeArm`'s: re-weighting first moved the slim's own anchors and with them
  `kept_to_cm` (-0.76 affected nothing) and the floor shift every test pins.
- **Measured, not asserted.** Rebuilt all three packs. `BUILD_INFO.json` now carries a `wrist`
  block: ramp, blend, tuck, and per group `vertices_reweighted` 1,839, `vertices_tapered` 102,
  `max_shift_cm` 0.88, `max_hand_weight` 0.297, palette + `Left/RightForeArmRoll`. The cut is
  untouched: `kept_to_cm` -0.76 / -0.79, `clipped_to_cm` 0.0, body 31,643 vertices, slim 61,479.
  Posed against the game's own gloves (`npc_criminal_sydney`, `joy`, `chill`'s Clover), the worst
  sector where the skin's wall stands outside the glove's cuff across six wrist poses fell from
  **+2.67 mm to +1.63** (Sydney), **+3.19 to -1.79** (Joy - inside the cuff now in every pose) and
  **-2.61 to -5.51** (Clover). The capture-driven render, and the tool that prints that table:
  [`docs/renders/honoka/model/wrist/`](../renders/honoka/model/wrist/README.md).
- **Held to:** `tests/test_wrist_twist.py` (the recorded curve, the curve on the shipped mesh, no
  hand-dominated vertex, the rim and the bracelet where they were, the shadow caster in step, and
  the posed protrusion under 0.20 cm against three gloves).
- **Rejected:** any change to the cut or to `PALM_EXTEND_CM` (D70 stands: an extension is what put
  skin *inside* the glove); a `Hand` majority (it made the protrusion worse in the sweep, and it
  would break the palm-cut tests); a rigid radial shrink of the whole wrist (it narrows the bare
  stub in third person, where nothing was wrong); moving the bracelet (it is the outfit's own ring);
  registering `glove_adapter` (D59/D60).
- **Source:** `tools/pd2-las/build_honoko2_dae.py` (`TWIST_RAMP`, `HAND_BLEND_CM`,
  `HAND_BLEND_MAX`, `TAPER_CM`, `TAPER_MAX_CM`, `CENTRE_WRIST`, `_wrist_pass`),
  `tools/pd2-las/wrist_compare.py` (the offline comparison render), `tests/test_wrist_twist.py`,
  `docs/renders/honoka/in-game/officesuite/2026-11-26/`.
- **Status:** holds offline only; `runtime_verified` stays `false`, and these bytes have not been
  seen in game. The dress gloves' own tightness at the cuff is still the limit: the pass removes
  what the outfit contributed, not what the glove's material does.

### D76 — Geralt's takes are re-keyed to `char_rust`; the map that names the ids is the one open input

- **Decided:** 2026-11-26, by the user: *"redo Geralt VO with numbers from the Marine mod"* — the
  re-key option (not "both banks", not "tables only"), the same 29 Geralt takes
  (`voice_lines_vox/geralt/slot_picks.csv`, unchanged), and *"work around it"* for the id → line
  mapping: ship only what the evidence supports rather than wait for a source.
- **Why.** D71 shipped `Geralt_VO_over_Rust_Stream` on the shared `regular_vox` ids and recorded
  the open question — whether Rust barks from that bank at all. The reference Rust pack answers a
  large part of it: `references/Marine VO for Rust.7z.001` + `.002` (kzn's "Houshou Marine VO for
  Rust", the current release) holds **no `regular_vox` folder at all**; it writes 1,046 ids under
  `char_rust` and 220 under `robbers_mission_gen`. Its changelog says so in the author's words:
  the 2026-08-17 build is *"Now Diesel 3.0 ver"* and the 2026-09-27 one *"Removed some useless
  regular_vox and robbers_mission_gen lines from U247"*. A working Rust voice pack on the 64-bit
  build is therefore dedicated-bank only, which is why the shared pack changes every heister on
  `regular_vox` except, most likely, Rust.
- **What blocks a full re-key.** Wwise keeps no name for a streamed file, and the Marine pack
  carries no id → line list: its only named entry is a `<Sounds>` redirect of the medic-kill bark
  (`g36x_any`, `prefix="rb16"`) to four OGGs — an *event*, not a numeric id. Measured, its
  `char_rust` ids share **0** with the 885 shared ids, so a slot take cannot be moved across by any
  arithmetic. Appending the same 29 takes to the first 29 measured ids would play the wrong line 29
  times; that is the one thing this route must not do.
- **Decision:** `tools/build_character_stream_mod.py` grows `--bank shared|char_rust` (make
  `voices_char_rust`). On `char_rust` it writes the *same picks* to
  `soundbanks/streamed/char_rust/<id>.stream`, taking every id from
  `voice_lines_vox/geralt/char_rust_ids.csv` (tracked template, **no rows yet**), validating each
  against the measured bank table. It raises while any picked slot lacks a named id, and raises for
  an id that is not in `voice_lines_vox/targets/rust_dedicated_char_rust.csv`. The tracked
  `dist/Geralt/Geralt_VO_over_Rust_Stream.zip` is **not** rewritten: the shared pack stays the only
  shipped Geralt pack, and the re-keyed one ships the day the map is filled.
- **Measured, not asserted:** the route was run end-to-end on a throwaway synthetic map (29 ids from
  the measured bank, deleted afterwards): 29 `.stream` members under `char_rust/`, **0**
  `regular_vox` members, ADPCM headers valid at 44.1 kHz mono, manifest carrying `slot`, `id`,
  `named_by` per row. `tests/test_character_stream_packs.py` pins the refusal (it must fire before
  any encoding), the empty tracked template, and that the two banks share no id.
- **Rejected:** guessing the mapping by size, order or count (the measured bank's sizes span 676 B
  to 486 KB and the Marine takes are unrelated lengths); shipping a keyed-to-`char_rust` pack with
  the ids left as the shared ones (inert at best); replacing the tracked shared pack now (it is the
  only Geralt pack that works for the crew on `regular_vox`); re-keying Arivus/Hoxton the same way
  (needs `char_hoxton`, which no bank dump lists).
- **Source:** `tools/build_character_stream_mod.py`, `voice_lines_vox/geralt/char_rust_ids.csv`,
  `voice_lines_vox/targets/rust_dedicated_char_rust.csv`, `references/Marine VO for Rust.7z.001`,
  `docs/pd2-voice-stream-tables.md`, `tests/test_character_stream_packs.py`.
- **Status:** the route holds offline and refuses to guess; **the map is the open input** — one
  extract of the game's `soundbanks/streamed/char_rust` (or any source naming id → line) fills it
  and the next `make -sC tools/pd2-las voices_char_rust` produces the re-keyed pack.

### D77 — The community voice-line sheet is a shared-bank source, imported not trusted

- **Decided:** 2026-11-26, by the user, who supplied the sheet and said *"add this info"*.
- **Context:** the user supplied a Google Sheets export, tab `regular_vox`, as the id → line source
  the re-key (D76) had been waiting for. Shape: a 6-row status block (99.88%, 20,293 complete,
  50 partial, 0 incomplete, 32 marked `(?)`), then a `Who | What | Notes` header whose id column is
  unlabeled to its left, then 20,343 data rows. Its speakers are the vanilla shared cast (Clover,
  Bain, Chains, Dallas, Hoxton, Houston, Wolf, Wick, the cop/security/civilian voices) — **no Rust
  row on the pages that were read, and the tab is not titled `char_rust`**.
- **Decision:** ingest it as a tracked, reproducible table, and treat every slot suggestion it
  yields as a *lead*, not a mapping. `tools/import_voiceline_sheet.py` (make `voices_sheets
  SHEET=… [WANT=Rust] [LEADS=1]`) strips the status block, keeps ids as digits, keeps `notes`,
  carries the sheet's `(?)` as `needs_review`, dedupes nothing (a repeated id is printed, not
  silently merged), and writes `voice_lines_vox/sheets/<tab>.csv`; `--keys` additionally writes
  `<tab>_keys.csv` (`slot, id, score, what, who`) by word overlap against `cut_line`.
- **Why a lead is not a mapping:** the sheet gives the line text, not which heister says which id.
  "Help me up!" scores as `downed.need_help` for Hoxton *and* Dallas, and a line that is a
  sentence ("Lemme uh, just, just gimme a minute here umm, thanks") shares a word with many slots.
  Scoring is therefore the F1 of word overlap in both directions, not recall against the slot's
  line — recall alone scored "I need a medic bag" as a perfect `downed.need_help`. A false mapping
  plays the wrong bark forever, which is worse than a missing one (D74).
- **Rejected:** paging the export through the page reader 138 times (136 chunks unread; the reader
  normalizes every `gid=`/`sheet=`/`tq=select` variant back to page 1, and this sandbox has no
  outbound HTTPS to `docs.google.com`), so a full ingest waits on a one-click `File ->
  Download -> CSV`; writing `voice_lines_vox/geralt/char_rust_ids.csv` from these ids (wrong bank);
  writing shared-bank ids as if they were dedicated ones; auto-appending leads to any tracked table.
- **Source:** `tools/import_voiceline_sheet.py`, `tests/test_voiceline_sheet_import.py`,
  `tests/fixtures/regular_vox_head.csv` (first 25 real rows, preamble included),
  `voice_lines_vox/sheets/`, `docs/pd2-voice-stream-tables.md` §"The voice-line sheet".
- **Status:** the importer, its fixture and 9 tests are in. The 25-row head this entry shipped was
  replaced by the full tab on 2026-11-26 (D81). The re-key stays blocked (D76). The productive use of
  the full export is the shared-bank reconciliation described in the note: join it against
  `voice_lines_vox/targets/*_shared_regular_vox.csv` on id, then confirm the line each slot claims.

### D78 — Tab inventory: which bank each community sheet actually covers

- **Decided:** 2026-11-26, by the user, who asked the same four links again as a coverage question.
- **Context:** D77 recorded the `regular_vox` tab of `196bzO0M…` as the only sheet read, and a
  wrong access note (that tab selection did not work). Four tabs across two documents have now been
  read, and the note needs correcting: **`&gid=<number>` selects a tab; `&sheet=<name>` does not**
  (it silently returns the first tab, which is what D76 saw).
- **Read:** `196bzO0M…` → `regular_vox` (`gid=0`, 20,293 complete, 32 `(?)`);
  `robbers_mission_gen` (`gid=1280565535`, 1,720 complete / 93 partial / 2,407 incomplete);
  `char_sydney` (`gid=1647606386`, 1,037 complete, 0 outstanding). `1c3uXGyH…` → `regular_vox`
  (`gid=0`, 887 rows / 885 ids, `PD2 ID | Speech | Category`).
- **Findings that change what can be claimed:**
  - `1c3uXGyH…` is exactly `voice_lines_vox/hila_regular_vox.csv` (all 885 ids, first, middle and
    last rows byte-identical). So the ids the repo calls Rust's and Old Hoxton's "shared" lines are
    **Hila's line list**, separated per heister by Wwise's `robber` switch only — not by a
    per-heister table. D73's classification stands; its evidence is now explicit.
  - `robbers_mission_gen` **does name Rust lines by id** (`3115131` It's delivered, `6480123` Find
    him!, `10609593` Delivered, `11367917` Found it), and those four ids are in the Marine pack's
    221-file `robbers_mission_gen` folder. That is a real id → line source for the objective-callout
    bank — but it is a different bank from `char_rust`, and none of the shared slots' ids live there.
  - A **dedicated-bank community sheet exists** (`char_sydney`, 100% covered), which rules out the
    assumption that only shared tabs get written up. `char_rust` is not a tab of either document
    (`&gid=` on it returns page one of `regular_vox`), so no such sheet is known for Rust.
- **Decision:** track the tab inventory in `voice_lines_vox/sheets/README.md` and leave D76's refusal
  in place. Nothing here names a `char_rust` id, and a `robbers_mission_gen` id must not be written
  to `char_rust` (0 ids in common with the measured `char_rust` table; the banks are not
  interchangeable).
- **Rejected:** treating `1c3uXGyH…` as new information (it is already imported, in full);
  re-keying onto `robbers_mission_gen` to "unblock" the objective callouts (a third bank, and D76
  is about the heister barks); paging all 138 chunks of `regular_vox` before the tabs it is being
  compared against are actually wanted.
- **Source:** `voice_lines_vox/sheets/README.md` (inventory), `tools/import_voiceline_sheet.py`
  (access note), `voice_lines_vox/hila_regular_vox.csv`,
  `voice_lines_vox/targets/rust_shared_regular_vox.csv`,
  `references/Marine VO for Rust.7z.001`/`.002`.
- **Status:** holds; every count here is the sheet's own status block, re-read on
  every import, and no tab of either document is `char_rust`.

### D81 — The three sheet tabs are imported in full, from exports that were already in the tree

- **Decided:** 2026-11-26, by the user, who chose *"Yes, import them"* from the audit of `references/`.
- **Context:** `voice_lines_vox/sheets/COVERAGE.md` had been reporting three tabs as held at 0.1 % and
  page 1, and asking for a one-click `File → Download → CSV` that would fill them. The exports were
  already in `references/`: somebody had made that download and nobody had imported it, so the
  document said the repo was missing data it held. D78's tab inventory was right about the sheets and
  wrong about the tree.
- **Decision:** import every tab in full, from the exports already tracked in `references/sheets/`
  (no network, so the import is reproducible from a clone). What that puts in `voice_lines_vox/sheets/`:
  `regular_vox` 20,404 rows / 20,403 ids (22 speakers, 29 `needs_review`, one repeated id
  `1052460785`); `robbers_mission_gen` 5,499 rows, of which 1,813 carry a speaker and a line and
  3,686 are bare ids the sheet has not filled in; `char_sydney` 1,037 rows, all Sydney, none marked.
  Leads for the intent slots: 3,994 over 65 slots and 22 speakers, plus the `--who Hoxton` slice
  (1,550 rows, 434 leads) as the worked example of a per-heister import.
- **The status block is a snapshot, not a count.** `regular_vox` declares 20,343 rows and holds
  20,404; `robbers_mission_gen` declares 4,220 and holds 5,499. The importer prints both and compares
  them, which is why it never trusts the block alone; where they disagree the block is stale, and
  `--require-full` would refuse a *short* file, not a longer one.
- **What it does not change:** D76's refusal. No tab of either document is `char_rust`; the
  `robbers_mission_gen` Rust ids are a third bank (D78). The **shared**-bank reconciliation is now
  unblocked, which it was not before: join the tab against
  `voice_lines_vox/targets/*_shared_regular_vox.csv` on id, take the rows whose `who` is the heister,
  and check the line each slot claims. A lead still becomes nothing until a line is confirmed.
- **Kept as it was:** `char_sydney.csv` carries the tab's first four columns, so `Type` lands in
  `notes` and `Sub-Type`/the second `Notes` column are not carried. Changing the importer's schema
  would invalidate D77's fixtures for a column no build reads; the export in `references/sheets/`
  keeps every column.
- **Rejected:** paging the tabs through the page reader; treating the status block as the row count;
  merging the repeated id silently; writing the `robbers_mission_gen` ids into `char_rust` (D78);
  dropping `references/sheets/*.csv` after importing them (they are what makes the import
  reproducible, and the audit's deletion pass had to be told they are inputs, not leftovers).
- **Source:** `tools/import_voiceline_sheet.py`; `voice_lines_vox/sheets/{README,COVERAGE}.md`;
  `references/sheets/`; `docs/pd2-voice-stream-tables.md` §"The voice-line sheet";
  `tests/test_voiceline_sheet_import.py`; `docs/audits/2026-11-26-references-inventory.md` §2.
- **Status:** holds; the four tabs are held in full and the coverage table now says so.

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
- **Status:** holds on redistribution; the "What you ship" rules it left in place were repealed by D74.

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

### D74 — Game-derived exports may be committed

- **Decided:** 2026-11-26, by the user ("Change the repo's rule about committing game-derived exports")
- **Decision:** game-derived assets and exports may be committed anywhere in this repo at the
  owner's call. `AGENTS.md`'s "What you ship" and `CONTRIBUTING.md`'s "No game content" hard rule
  were rewritten, the mirrored skill docs, `knowledge/README.md` and the `um publish check` lint
  follow, and D32's note that those rules stay is superseded. Decompiled code, secrets, links to
  pirated copies and the ownership/anti-cheat rules are unchanged. The first shipped export is
  `Arivus_Head_over_Old_Hoxton_GLB.zip`: a tracked, checksummed pack with a deterministic builder
  and its own make target, not loose ignored files.
- **Why:** the owner decided that a self-imposed hygiene rule should not keep a requested
  deliverable out of the repository. The rule was a convention of this fork, not a property of the
  assets; D32 had already removed every redistribution restriction from the packs. Provenance is
  kept instead of a prohibition: the pack names its source, the manifest records per-file digests,
  and `um publish check --game` reports game-derived files as `INFO`.
- **Source:** `tools/pd2-las/build_arivus_glb_pack.py`, `tests/test_arivus_glb_pack.py`,
  `AGENTS.md`, `CONTRIBUTING.md`, `tools/README.md`.
- **Status:** holds; publishing outside the repo is still asked of the owner first.

### D80 — The over Joy zips are gone; the assembly that wrote them is the over Hila builder

- **Decided:** 2026-11-27, by the agent, under the owner's "fix everything" instruction
- **Decision:** `build_l4d2_joy_mod` / `build_me2_romance_joy_mod` assembled a head, wrote a Joy
  zip into a caller-supplied path list and then emitted `Miranda_{L4D2,Romance}_over_Hila.zip`;
  since the dist clean-up `main()` passed `[]`, so every `heads` build patched Joy's model and
  encoded Joy's textures for a zip nobody wrote. The zip packaging and the five functions only it
  used (`patch_joy_model`, the Bonnie/Clover/Sydney material-config patchers, `suit_collar_radius`)
  are deleted, and the two builders are renamed `build_l4d2_hila_head` /
  `build_me2_romance_hila_head`, which is what they produce.
- **Why:** the assembly is not dead — it is the only source of the two over Hila packs — so the
  first attempt (delete the whole cluster) left `heads` unable to produce them, which the `packs`
  job caught within a build and `fresh.py check --builders heads` reproduced locally. What is dead
  is the Joy-shaped output path, and only that is gone.
- **Held to:** `fresh.py check --builders heads` builds the four packs of that target from scratch
  and compares them with their sidecars: 4 of 4 identical, before and after the deletion.
- **Source:** `tools/build_joy_head_mods.py`, `tools/pd2-las/fresh.py`, the `packs` job of
  `.github/workflows/test.yml`, `docs/ci.md`.
- **Status:** holds.
