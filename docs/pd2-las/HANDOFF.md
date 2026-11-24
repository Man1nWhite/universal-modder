# HANDOFF — where the pd2-las packs stand

> **Start at [`tools/pd2-las/README.md`](../../tools/pd2-las/README.md).** Commands, status, the file map,
> the invariants and the open work are written there and nowhere else. This page is the state a person has
> seen: which bytes were in game and when, and which approaches are dead ends. It gives no commands and
> keeps no work queue.

## Tracked packs

Which bytes are tracked is not written here. `make -sC tools/pd2-las status` prints each pack's size and sha256
and whether the zip is what git holds; `dist/<character>/<name>.zip.sha256` is the hash itself.

Rebuildable packs use fixed timestamps and a declared numeric code path. The new
`Christie_LAS.zip` is a source rebuild with head and hands removed and a glove
adapter; it replaces the earlier `1ec1c95a…` full pack. New user-supplied
menu captures show the Christie outfit, but the installed bytes were not hash-verified.
The older `Christie_LAS_Slim.zip` was removed from distribution at the user’s request;
earlier Christie audit results describe older bytes, not the new pack.

The DOAXVV "Secret Report" outfit is built from the Collada `.dae` by `build_honoko2_dae.py` into
**one** pack, `OfficeSuite`. CI rebuilds it and verifies its bytes. Two earlier builds of the same source
were removed at the user's direction and stay reachable through git history: the TMC-only build, dropped
once the `.dae` pack proved the better one (D40), and `Honoko2`, `Honoko3` and `Honoko4` — the base,
5%-slim and alternate-suit siblings — dropped so that only `OfficeSuite` is worked on from then on (D57).
The in-game captures of 2026-11-15 are of `Honoko2`; they are kept as the record of that build and of what
the outfit looked like before the fit and colourway changes below.

`OfficeSuite` applies the user's revised third colourway (black jacket, light shirt,
`references/Honoka/Tex_07(L_7)3.dds`, D45/D46), updated jewelry diffuse (`references/Honoka/Tex_23(L_23)2.dds`),
and waist/hip/cuff fit adjustments (D50). It carries the 5% bone-anchored slim (`_slim_groups`, D42) and the
layer-clearance pass with the trimmed shadow caster that answer the 2026-11-15 neck and chest close-ups (D44).
Earlier user-supplied captures show `OfficeSuite` prior to the jewelry texture update. It also ships a
first-person arms unit (D53): the same slim/cleared arms, registered with an `fps_unit` and depth-scaled
materials, and no head. It keeps the outfit's own palms, fingers and bracelet on the PD2 hand and finger
bones — in the third-person body, the shadow caster and the first-person arms — and registers no glove
adapter (D55). Its wrists therefore show the outfit's skin and cuff, not the vanilla blue gloves. The
first-person arms have not been seen in game; the 2026-11-15 captures predate both the arms unit and the
hands.

`OfficeSuite_Head` (`make -sC tools/pd2-las honokodae_head`, D56) is that same body, hands and arms unit
with a head: the ME2 "Romance" head and lashes the Hila override carries, re-skinned onto the 2B rig and
packed in one `WHOLE_CHARACTER` unit. Its registration is `replace_all` with `hide_mask`, so the game
swaps the heister's head and the mask cannot be put back on; the pack's own eyes and teeth are Hila's stock
ones. It has not been seen in game; its lashes are the donation's `opacity:` shader with a real alpha cutout,
which is the one thing the offline checks cannot confirm. `Christie_Clover_LAS` (`build_clover_christie.py`, `references/Clover-Christie.zip`)
is an experimental TPP-only `BODY_ONLY` GLB outfit and has not been seen in game.

## Seen in game

What a person has reported from the game, by date. Only the user has run the game; the screenshots are the
user's, and "no record" means that nothing in the repository says anyone looked.

`runtime_verified` in a pack's `BUILD_INFO.json` is a constant its builder writes, and it is `false` in every
pack that has one. The flag does not say whether the tracked bytes were in game. This table does.

| Pack | Last seen in game | Were those the tracked bytes? |
| --- | --- | --- |
| `Miranda_L4D2_LAS`, `Miranda_L4D2_Busty_LAS` | no record | — |
| `Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}` | 2026-11-05, tested by the user | no: all four were rebuilt on 2026-11-07 with the neck skirt, again on 2026-11-11 and on 2026-11-12 |
| `Miranda_Romance_over_{Joy,Clover,Bonnie,Sydney}`, `Geralt_over_Rust` | no record | — |
| `Miranda_{L4D2,Romance}_over_Hila` | no record | — |
| `OfficeSuite_Miranda_Romance_over_Hila` | no record | — (native body, hands and head override; its render is from the single replacement ZIP) |
| `Miranda_Romance_LAS` | see [`tools/pd2-port/STATUS.md`](../../tools/pd2-port/STATUS.md) | |
| `Honoko2` (removed, D57) | 2026-11-15, outfit-menu preview, user report | yes per the user — the captures are of this pack; installed hashes not measured |
| `Honoko3`, `Honoko4` (removed, D57) | no record | — (built after the captures; the close-ups that drove D44 were of `Honoko3`) |
| `OfficeSuite` | 2026-11-15, user-supplied menu/lobby captures | **no** — captures precede the `Tex_23(L_23)2.dds` jewelry diffuse rebuild and the 2026-11-23 hands (D55); installed hash not measured |
| `Christie_LAS` | 2026-11-15, user-supplied menu/lobby captures | Build not hash-verified from captures; earlier captures showed the prior full pack |
| `Christie_Clover_LAS` | no record | — |
| `Christie_LAS_Slim` (removed) | 2026-11-15, menu armor-skin preview, user report | Earlier Slim capture; installed hash not measured |
| `Miranda_Lawson_VO_over_Hila` (audio/BeardLib) | no record | — (nothing has been heard in game yet; keyed on PD2 bark events since the re-key; packaging contract in [`docs/pd2-voice-mod-install.md`](../pd2-voice-mod-install.md)) |

New [Christie](../renders/christie/in-game/2026-11-15/README.md) and
[OfficeSuite](../renders/honoka/in-game/officesuite/2026-11-15/README.md) menu/lobby captures
are archived separately; they do not establish installed hashes, first-person behavior or animation.

Eight captures of `Honoko2` (no longer a tracked pack, D57) on 2026-11-15 — the outfit menu, not a
heist — are archived under
[`docs/renders/honoka/in-game/2026-11-15/`](../renders/honoka/in-game/2026-11-15/README.md): the purple
"Secret Report" blazer and skirt with the vanilla blue heister gloves over the wrist cut, from the front,
three-quarter, side and back. An earlier set of six captures (archived at `da891d7`, removed in the
`docs/renders/README.md` cleanup) showed the deleted TMC-only pack plus both Christie packs. Lobby/heist
behaviour, the inner elbow under a rifle, movement, the cuff/glove stack in every pose and the crash logs
remain unchecked — the [checklist](in-game-checklist.md) is still waiting for a person with the game. The builds
installed on 2026-11-15 were identified by the user, not hash-measured from the captured bytes.

- **The Miranda LAS packs** have the checklist `docs/pd2-las/in-game-checklist.md` waiting for a person with
  the game. No tracked bytes of either pack have been in game.
- **Head packs, coverage.** Clover and Bonnie replace the heist, menu *and* Safe House (`*_chill`) models; Joy,
  Sydney and Hila replace the heist + menu models only, so their Safe House units keep the vanilla head (Hila
  has no Safe House unit to swap). Hila is also the only heister whose head packs carry the user-supplied
  `references/EYE_Diff.png` in the eye quadrant (D41). There is no checklist for the head packs. Until someone
  looks at a throat again the five L4D2 packs are *offline-verified only*.

## Dead ends — do not retry

- Raw frame-delta retargeting (all forms: `v·inv(S)`, shortest-arc,
  per-source Umeyama, unit-scaled deltas) → ribbon artifacts. Use
  `retarget_maps` as-is.
- One shared fit across both legs (`FIT_MIN_PAIRS` pair-count inheritance)
  → thighs collapse onto one point. Leg fits stay local/mirrored.
- Speculative whole-heister retargeting and replacing the stock rig — retired route, dead. The native Hila
  pack instead keeps her rig and object/physics contract and uses the already authored body and head (D52).
- `z.write()` for reproducible zips (embeds mtimes) — `las_pack.zip_pack`
  already solves this.
- Seam repair by *merging coincident vertex indices* → the two rims carry
  different UV islands, so the seam comes back as a texture tear. Weld the
  attributes (position/normal/weights), rewire the faces, keep the corners.
- Bridging the rims **before** welding them → zero-area triangles (a new
  triangle closes a pair that is already coincident at post-weld positions).
- Spanning a run gap of 3+ rim pairs while stitching → that "gap" is the
  armhole. The sleeve seam only ever jumps 1-2 rim pairs.
