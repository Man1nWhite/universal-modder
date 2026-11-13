# lawson_las — the dated record of the shipped port

> **Start at [`README.md`](README.md).** Commands, the pipeline, the file map and the release route are
> written there and nowhere else. This page is the dated record beneath it, for the port that is in the tree
> (Miranda Lawson, *Mass Effect 2*): what a release serves and what is tracked, what has been seen in game,
> what was found and settled, which approaches failed. It gives no commands and keeps no work queue.
> Day by day: [`MODLOG.md`](MODLOG.md).

Rewritten on 2026-11-13. Until then this page was also a start-here, a table of check results, an
environment guide and a file map, written on 2026-10-19 and corrected by a note at its top. What it and the
README claimed that was not so is under [Corrections](#corrections).

## Released and tracked

**There is no release.** The pack is the tracked `dist/lawson_las.zip`, stamped 0.1.2. Its models, textures,
unit files, hook and menu strings are those built at `15b0fbe` (2026-10-22). On 2026-11-13 it was built
again without `CREDITS.txt`, at the owner's direction (`docs/pd2-las/DECISIONS.md`, D34): that file and its
line in the manifest went, and the other 28 files are byte for byte what they were.
`make -sC tools/pd2-las status` prints its size and sha256.

- **Deleted on 2026-11-13, at the owner's direction:** the pre-release `lawson-las-v2` of 2026-10-19 with its
  tag (→ `282703f`), the tag `lawson-las-v1` (→ `2b0b1b4`; its release was already gone) and the tag
  `lawson-clover-v1` (→ `9faa4a4`, the retired character swap). The three commits are in `main`. The
  release notes of v1 and v2 went with them: `git show 19ca55a:tools/pd2-port/releases/lawson-las-v2.md`.
  The zip the pre-release served is the one tracked at its commit: `git show 282703f:dist/lawson_las.zip`.
- **Why the pre-release was stale:** it served the build of `282703f` (`lawson_las.zip`, sha256 `a24f0b7c…`),
  and ten commits after the tag rebuilt the tracked pack, from 2026-10-19 to 2026-10-22
  (`git log 282703f..15b0fbe -- dist/lawson_las.zip.sha256`). By their subjects: an invisible unit; glossy
  textures; the retarget of the hands and fingers, then of the shoulders, upper arms and elbows; the normal
  maps; the seams at the cheek and mouth, with their bone weights and normals; the eyes, lashes and
  nostrils; hair at the throat and on the face; the shoulder pose. None of them moved `VERSION` in
  `build_las_pack.py`, so both packs were stamped 0.1.2. GitHub counted 0 downloads of each of the
  pre-release's two assets on the day it was deleted.
- **The next release is `lawson-las-v3`:** the numbers 1 and 2 are used, and a test rejects release notes
  with a lower number.
- 0.1.1, the pack at `2b0b1b4` (sha256 `063d5f64…`), has holes in the skin (below).

## Seen in game

No record: nothing in the repository says that anyone saw `lawson_las` in the game, on any date, in any
build. Two of the ten commit subjects speak of what showed in game ("lawson_las invisible unit", `2e73ef4`;
"Fix in-game normal maps … across all 10 Miranda mods", `309fc0a`) without a report, a screenshot or the
name of the pack that was looked at. `build_manifest.json` in the pack says `"runtime_verified": false`.

## Found and settled

- **0.1.1 had 1,027 triangles wound inside out** (found and fixed on 2026-10-19): 946 in the third-person
  body and 81 in its head. The first-person arms had 291. The game culls such a triangle, so 0.1.1 showed
  holes in the chest, the shoulders and the arms and shaded the skin around them backwards. The source meshes
  have none: the transfer of that day made them. It fitted every bone piece by itself, and where the two rigs
  disagree the fits came out 120 to 156 degrees apart, so the triangles between two pieces folded back.
  - Fix, in 0.1.2: `rig_target.repair_winding()` reverses every triangle that faces away from
    its own vertex normals. The source's meshes are split at every corner, so reversing one triangle cannot
    put its neighbours out of step.
  - Guard: audit check `N3` fails a pack with an inverted triangle, and the auditor's self-test has that
    mutation.
  - The transfer itself was replaced in the ten commits above: the torso, head and legs now move as one
    rigid piece and the arms, hands and fingers are built separately (the `target_ops` docstring). On
    2026-11-11 the build re-wound 3 triangles.
- **The green channel of the normal maps** (settled on 2026-10-19, by provenance). The files cannot say
  whether the source maps are Y+ or Y−: their blue channel is saturated, so the height field cannot be
  recovered, and both readings are consistent with the image. `check_nm_convention.py` measures that and
  prints the verdict. The provenance can: *Mass Effect 2* runs on DirectX 9, whose normal maps are Y−, and
  PAYDAY 2 wants Y+. So the default build, which inverts green, is the right one for this source, and
  `--keep-nm-green` is for a source that is already Y+. Nobody has looked at it in game. It is the audit's
  one warning, `G1`.

## Dead ends

Two transfers were tried on 2026-10-19 against the fold above, and both were rejected:

- **Hierarchical operators** (each bone relative to its parent, with the parent's offset as the direction):
  no inverted triangle in the third-person body, but 665 in `Body 2` as before, and the mesh came out rigid
  against the source, in the source's proportions instead of PAYDAY 2's.
- **Parent-offset directions with independent fits:** worse, 832 inverted in `Body 2`.

What made independent fits tear is in the rigs, and holds for any transfer: the two agree in the spine and
head, and disagree in the far limbs. The source's A-pose has the wrists in front of the elbows (left wrist
at `(49.3, −12.6, 108.8)`, elbow at `(40.4, −5.9, 115.9)`); PAYDAY 2's rig has the hand behind the forearm
(right hand at `(46.0, 18.7, 124.5)`, forearm at `(39.5, −1.0, 133.3)`): about 31 cm apart in y. The feet
disagree the same way: the source's toe is at y = −3.6, in front of its ankle at 8.1; PAYDAY 2's toe is at
y = +15.1, behind its foot at 0.9. Left open that day, and not recorded as answered since: whether PAYDAY
2's far bones really are turned that way, or the rig extraction or the 2B donor's own pose is responsible.

## Corrections

What this page and the README said until 2026-11-13, and what is so:

- **"The tracked `dist/lawson_las.zip` is therefore exactly what the release serves"**, and "build it
  yourself — the bytes are identical" (the README). The release serves the build of `282703f`; the tracked
  pack is ten rebuilds later. This page gave the tracked pack's size and sha256 in one table with the
  release, and a test kept those two figures current, so the table read as if they were the release's.
- **"the v1 release stays up"** (this page), "v1 kept for comparison" (the README). On 2026-11-13 there was
  no v1 release, only the tag. There had been one: the workflow ran on that tag six times on 2026-10-19 and
  its step "publish to the GitHub release" succeeded in five. Nothing here records who took it down, or
  when. (From `cf56805` through `b3b6966` this page said "never a release". That was wrong.)
- **"uploads `lawson_las.zip` + `lawson_las.zip.sha256`"** (the README, of the release workflow). Since
  `637b7a9` the workflow uploads `Miranda_LAS.zip` and its `.sha256` to the release as well. `lawson-las-v2`
  had the first two only.
- **"The next piece of work: a consistent bind-pose transfer"** was a plan for the transfer of 2026-10-19.
  The transfer was rebuilt another way within three days. The plan, its constraint set and the tear angles
  of the old scheme are gone from this page; what was measured on the rigs is under Dead ends.
- **The check results of 2026-10-19** (the audit's and the suite's counts, the timings of `check_all.py`)
  were a snapshot. `check_all.py` and `make -sC tools/pd2-las green` print today's.
- **The venv recipe** wrote the two pinned versions by hand. `make -sC tools/pd2-las env` makes the
  environment and `tools/pd2-las/pins.txt` is the one place the versions are written.
- **"Related work on other branches"** described `arena/136395ac-universal-modder`. Both lines of work are
  in `main` and the branch is gone.
