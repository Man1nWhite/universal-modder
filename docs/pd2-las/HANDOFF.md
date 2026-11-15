# HANDOFF — where the pd2-las packs stand

> **Start at [`tools/pd2-las/README.md`](../../tools/pd2-las/README.md).** Commands, status, the file map,
> the invariants and the open work are written there and nowhere else. This page is the state a person has
> seen: which bytes were in game and when, and which approaches are dead ends. It gives no commands and
> keeps no work queue.

## Tracked packs

Which bytes are tracked is not written here. `make -sC tools/pd2-las status` prints each pack's size and sha256
and whether the zip is what git holds; `dist/<name>.zip.sha256` is the hash itself. The two Miranda LAS packs
are also tracked, byte for byte, under `build/pd2-las/`.

Every pack that can be rebuilt reproduces its tracked bytes in the pinned environment on any x86-64 Linux
machine: each builder writes one fixed timestamp into every zip entry and puts itself on one declared numeric
code path before it computes anything, so a `.sha256` sidecar is a true build hash. CI builds the rebuildable
packs on its runner and holds the 16 zips to their tracked hashes, with no tolerance, on runners with AVX-512
and without. The two Christie packs cannot be rebuilt (their builder was deleted on 2026-11-14); their
sidecars still hold against the tracked zips. The tracked `Christie_LAS.zip` is the 2026-11-13/14 sleeve-bridge
build (`1ec1c95a…`, see `docs/audits/2026-11-14-christie-rebuild-redo.md`); on 2026-11-14 the pre-bridge builder
(recovered from `6f26633`) was used for a from-scratch build, which reproduces the **base** bytes (`b65fb27e…`),
not the tracked bridge bytes — it passed all offline gates (`docs/audits/2026-11-14-christie-from-scratch.md`).
Neither pack's bytes have been in game.

## Seen in game

What a person has reported from the game, by date. Only the user has run the game; the screenshots are the
user's, and "no record" means that nothing in the repository says anyone looked.

`runtime_verified` in a pack's `BUILD_INFO.json` is a constant its builder writes, and it is `false` in every
pack that has one. The flag does not say whether the tracked bytes were in game. This table does.

| Pack | Last seen in game | Were those the tracked bytes? |
| --- | --- | --- |
| `Miranda_LAS`, `Miranda_Busty_LAS` | no record | — |
| `Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}` | 2026-11-05, tested by the user | no: all four were rebuilt on 2026-11-07 with the neck skirt, again on 2026-11-11 and on 2026-11-12 |
| `Miranda_Romance_over_{Joy,Clover,Bonnie,Sydney}`, `Geralt_over_Rust` | no record | — |
| `lawson_las` | see [`tools/pd2-port/STATUS.md`](../../tools/pd2-port/STATUS.md) | |

- **The Miranda LAS packs** have the checklist `docs/pd2-las/in-game-checklist.md` waiting for a person with
  the game. No tracked bytes of either pack have been in game.
- **Head packs, coverage.** Clover and Bonnie replace the heist, menu *and* Safe House (`*_chill`) models; Joy
  and Sydney replace the heist + menu models only, so their Safe House units keep the vanilla head. There is
  no checklist for the head packs. Until someone looks at a throat again the four L4D2 packs are
  *offline-verified only*.

## Dead ends — do not retry

- Raw frame-delta retargeting (all forms: `v·inv(S)`, shortest-arc,
  per-source Umeyama, unit-scaled deltas) → ribbon artifacts. Use
  `retarget_maps` as-is.
- One shared fit across both legs (`FIT_MIN_PAIRS` pair-count inheritance)
  → thighs collapse onto one point. Leg fits stay local/mirrored.
- Surgical replacement of shipped heister models — retired route, dead.
- `z.write()` for reproducible zips (embeds mtimes) — `las_pack.zip_pack`
  already solves this.
- Seam repair by *merging coincident vertex indices* → the two rims carry
  different UV islands, so the seam comes back as a texture tear. Weld the
  attributes (position/normal/weights), rewire the faces, keep the corners.
- Bridging the rims **before** welding them → zero-area triangles (a new
  triangle closes a pair that is already coincident at post-weld positions).
- Spanning a run gap of 3+ rim pairs while stitching → that "gap" is the
  armhole. The sleeve seam only ever jumps 1-2 rim pairs.
