# PAYDAY 2 LAS — review journal

## 2026-11-14 — fresh start

The dated journal that stood here before this entry was removed on 2026-11-14, at the owner's direction:
the project's self-description starts from the present. What the packs are and how they are built lives in
`tools/pd2-las/README.md`; the dated evidence of how the tracked bytes came about lives in `docs/audits/`.
The text of the removed entries is in git (`git log -- tools/pd2-las/MODLOG.md`).

## 2026-11-15 — the Honoka pack is tracked

`dist/Honoka_LAS.zip` and its sidecar are committed (the DOAXVV "Secret Report" costume, built by
`build_honoka_las.py`; `make honoka` builds into `build/honoka-las/` and copies the zip into `dist/`).
It is the one tracked pack `fresh` does not verify: the builder writes `build/honoka-las/`, and the copy into
`dist/` is part of the make target. The pinned-environment rebuild after a sandbox restart reproduced the
previously delivered bytes exactly (same size, same sha256), confirming the build is byte-reproducible.
`runtime_verified` is false; nothing has been run inside PAYDAY 2.

## 2026-11-15 — long-thin connector triangles dropped; pack re-committed

The tracked `dist/Honoka_LAS.zip` was rebuilt with the new source-connector filter
(`drop_long_thin_triangles` in `build_honoka_las.py`, 20 cm edge limit — the gap between the 13.4 cm longest
legitimate edge and the 23.7 cm smallest stray): 26 triangles removed (6 `WGT_cap2`, 8 `WGT_headdress2`,
12 `WGT_new_aya_body_decl0`), 50244 -> 50218 triangles per geometry. They drew as hairline streaks (wrist to
feet) in every preview render. A second build of the same tree in a different output directory reproduced the
new zip byte for byte; it is tracked with a rewritten sidecar (new size and sha256 — `status` prints them).
The previous bytes remain in git history (`2e49f14`). `runtime_verified` stays `false`.

## 2026-11-15 — in-game menu captures archived for Honoka and both Christie packs

The user supplied six in-game screenshots (all the outfit menu armor-skin preview, not a heist):
`Honoka_LAS` (the tracked pack, user-confirmed), `Christie_LAS_Slim` with the white LAS gloves spawned, and
full `Christie_LAS` with Christie's own hands (the Christie build identification is the user's, not
hash-measured from the captured bytes). They are archived byte-identically in
`docs/renders/in-game-2026-11-15/` with a README and a SHA-256 manifest; `docs/pd2-las/HANDOFF.md`
(*Seen in game*) now records all three packs as seen in game on 2026-11-15 and is the authority on what ran.
The tracked pack bytes were not rebuilt or touched; `runtime_verified` in `BUILD_INFO.json` remains `false`
in every pack (D31) — the HANDOFF table, not the flag, is the record. Lobby/heist behaviour, the inner
elbow under a rifle, movement, the cuff/glove stack in every pose and the crash logs remain open
(`docs/pd2-las/in-game-checklist.md`). See D38.

## 2026-11-15 — unified render rules under `docs/renders/`; old renders deleted

All pre-existing tracked renders (`docs/previews/`, `docs/pd2-las/renders/`,
`docs/renders/christie-2026-11-14/`, `docs/renders/in-game-2026-11-15/`) were removed at the
owner's direction (still in git history at `da891d7`). `docs/renders/README.md` defines the single
layout (`docs/renders/<project>/<ext>/...`), enforced by `tests/test_render_rules.py`. See D39.

## 2026-11-15 — the TMC-only Honoka pack deleted; `Honoko2` (.dae) kept, with in-game captures

At the owner's direction the TMC-only Honoka pack is gone: `dist/Honoka_LAS.zip` and its sidecar, the
builder `build_honoka_las.py`, the `honoka` make target and the renders and README it produced were
deleted (the bytes stay in git history). The owner compared the two builds in game and judged the `.dae`
one much better: it keeps the six material slots of the buttoned suit instead of overlaying the
unbuttoned jacket shell. `Honoko2` keeps its tracked bytes, its `honokodae` target and `fresh`
verification, and the helpers it still needed from the deleted builder (TMC frame map, bind matrices,
wrist cut, long-thin triangle filter, fallback icon) moved untouched into `tmc_las.py`.

The owner also supplied eight in-game captures made with `Honoko2` (outfit menu, armor-skin preview: front,
three-quarter, side and back on the preview turntable). They are archived byte-identically, with a README
and a SHA-256 manifest, in `docs/renders/honoka/in-game/2026-11-15/`; `docs/pd2-las/HANDOFF.md` records the
pack as seen in game. `runtime_verified` stays `false` in the pack (D31). See D40.

## 2026-11-15 — `Honoko3`: the same outfit 5% slimmer, both packs ship

At the owner's request ("make Honoko3 zip from dae with a bit smaller model"): slim, at the same
height, ~5%, and `Honoko2` untouched. `build_honoko2_dae.py` now takes a `PackSpec`, and one run of
`make -sC tools/pd2-las honokodae` writes both `dist/Honoko2.zip` (byte-identical to the tracked pack,
so the refactor is not a rebuild) and `dist/Honoko3.zip` from the same Collada input. The only
geometric difference is `_slim_groups(factor=0.95)`: every vertex is pulled toward the weight-blended
rest position of the bones in its palette, `anchor + 0.95 * (v - anchor)`, then the outfit is re-seated
so its soles are back at `z = -0.47`. Scaling in world space would have dropped the collar off the
heister's head, left the wrist cuts short of the gloves and shortened the bone lengths; anchoring per
bone keeps the joints, the sleeve and skirt hems and the height, and shrinks the girth — 5.05% front to
back, with the same 31,577 vertices, the same palettes and the same six materials. Previews:
`docs/renders/honoka/model/dae/honoko3_las_sheet.png`; the 18-pack `dist/` overview now carries both.
Nothing of `Honoko3` has been in game. See D42.

## 2026-11-15 — the supplied eye is repainted; both Hila packs rebuild

The user supplied a second `references/EYE_Diff.png` (same 256x256 frame and veined sclera, the iris
redrawn rounder, 1.38x the area-equivalent radius and with a catchlight) and asked for the Miranda over
Hila packs to be rebuilt from it. The file is the repaint now; `HILA_EYE_ZOOM` went 2.8 -> 2.03, because
the factor is measured off the source iris (hole-filled blue-plus-limbal mask, r_eq 14.24 -> 19.63 px of
256) and exists to land it at the synthesised eye's quadrant radius (r 0.156 in u,v, inside the 0.174
gloss disc): at the old factor the new iris would have sat 1.38x too large in game and spilled out of its
gloss disc. One `make -sC tools/pd2-las heads` run rebuilt the two Hila zips and their sidecars and left
the other nine head packs byte-identical; the two Hila sheets and both `dist/` overviews were re-rendered
(`docs/renders/miranda/model/over-hila/`). The hila test rebuilds the expected eye quadrant from the
reference at test time, so it pins the new bytes without an edit. Nothing of the Hila packs has been in
game. See D43.

## 2026-11-15 — `Honoko4`: Honoko3 in the user's alternate suit; both slim packs get layer clearance

The user supplied `references/Honoka/Tex_07(L_7) 2.dds` (the suit's UV layout repainted: black jacket,
orange shirt) and four in-game close-ups of the neck and chest, and asked for the texture on Honoko3's
costume as a new pack plus fixes for what the close-ups show. `honokodae` now writes three packs:
`Honoko2` byte-identical to its tracked bytes, `Honoko4` = `Honoko3`'s geometry with the suit slot read
from the new diffuse, and both slim packs rebuilt with `_clearance_pass`: the torso and neck skin sinks
2 mm along its own normals, the bra 0.5 mm, and the shadow-caster drawable drops the bra and panties
shells. Measured before the fix, those shells stood 0.2 mm (bra to skin), 0.7 mm (necklace) and 3.6 mm
(collar) apart - the dark angular flakes in the close-ups are the depth test and the shadow map
alternating across gaps that thin - and the 5% slim had pressed each pair tighter, which is why the
flakes appeared with Honoko3. After it, every measured contact stands >= 1.2 mm open. The neck plug
needed no change of its own: measured about its centroid axis it nests inside the head unit's neck and
hair at every height. The nose in the close-ups is the Miranda head unit's, not the body pack's (the
pack ends in a neck plug at z 167); nothing here changes it. Counts go 18 -> 19 packs and 20 -> 21
tracked zips; previews: `honoko4_las_sheet.png` and the 19-pack `dist/` overview. Nothing of Honoko3 or
Honoko4 has been in game. See D44.

## 2026-11-16 — `Honoko5`: the third colourway, rendered with the head again

The user supplied `references/Honoka/Tex_07(L_7)3.dds` (the suit's UV layout repainted once more: white
jacket over a black shirt; uploaded to `main` as `7ea708e`) and asked for it as `Honoko5`, rendered again
with a head. `honokodae` now writes four packs: `Honoko2` byte-identical, `Honoko3`/`Honoko4` untouched,
`Honoko5` = `Honoko3`'s geometry with the suit slot read from the new diffuse. Previews: `24_Honoko5`
and, as for Honoko4, the combination with `Miranda_Romance_over_Hila`'s `g_head`
(`25_Honoko5_with_Miranda_Romance_over_Hila`); the `dist/` overview carries all 20 packs. Counts go
19 -> 20 packs and 21 -> 22 tracked zips. Nothing of Honoko5 has been in game. See D45.

## Honoko5 revised texture and Miranda nose-normal cleanup

The user revised `references/Honoka/Tex_07(L_7)3.dds` (main `526480e`): rebuild
Honoko5 with the revised black jacket and light shirt, preserving its mesh and clearance.
The older colourway described in the preceding entry is superseded. A close-up diagnosis
of the Miranda head isolated a broad downward vertex-normal override as a major contributor
to the dark nostril blotches. Removed it at the head-building source, keeping the original
skin repair and nostril UV treatments. Rebuilt both Miranda variants over each heister, and
regenerated their previews and the Honoko5-with-head combination. Offline renders improve,
but normal-map lighting and the still-unmodified neck need an in-game check. See D46.

## Romance-over-Hila skin-tone match for Honoko5

The user requested a head texture colour closer to the body. The Hila Romance face and scalp skin
are adjusted toward Honoko5's exposed neck diffuse via a deterministic colour mask; the eyes, hair,
alpha, geometry and other head packs are kept unchanged. The Hila portrait and offline combo views
are regenerated. The remaining neck crossing and in-game lighting are not addressed by the tint. D48.

## Honoko5 jewelry texture update

Rebuilt Honoko5 with `references/Honoka/Tex_23(L_23)2.dds` in the jewelry diffuse slot,
retaining its existing suit diffuse, geometry, and jewelry normal map. Honoko2–4 reproduce their
previous tracked bytes. The updated Honoko5 pack has not been verified in game; earlier screenshots
were taken before this change.

## Clover-Christie LAS intake

The user chose a selectable LAS outfit for `references/Clover-Christie.zip`. The archive
contains `PD2/Clover.glb` and `PD2/Clover.blend`, not an installable pack. The GLB contains
a skinned mesh named `6021834874957821078` with four `cri_*` material primitives and embedded
PNG textures, alongside numerous other meshes with numeric material names. The existing LAS
builders do not accept GLB; a source-specific importer, rig mapping, mesh selection and validation
are needed. No Clover-Christie pack has been built or tested. Avoid shipping the unrelated
numerically named meshes without establishing their provenance.

## Clover-Christie experimental LAS builder

Added a narrow GLB importer and a deterministic BODY_ONLY TPP LAS builder. The skinned
Christie mesh's weighted joints all resolve to the LAS template by Diesel hash; bind-joint
positions differ by at most 5 cm, so this is a direct bind rather than a pose retarget.
Only Christie material primitives and their embedded textures are used. Wrists are cut,
the heister supplies head and gloves, and there is no custom first-person unit. Blended
material is approximated with alpha test; its shadow is opaque. Normal-map green channels in
`PD2/Clover.glb` are already OpenGL Y+ (matching `Christie_LAS` with `corr > +0.99`), so the
builder preserves `G` without inverting it a second time, and `BUILD_INFO.json` carries full
`item_id`/`models_present`/`registration` metadata. All offline model renders (including
`Christie_Clover_LAS` and the updated `Honoko5` + 20-pack overview sheets) are generated by
`tools/render_mod_previews.py --unified`. Runtime animation, cuffs, transparency and shadows
still require in-game review (`runtime_verified: false`).

## Stale-tool sweep: three live references to deleted things

A reachability pass over all 67 tools, 45 test modules and the live docs found nothing orphaned and no
test duplicated or empty, but three references had outlived what they named:

- `tools/pd2-las/render_mesh_skeleton.py` documented its usage with
  `--zip dist/Christie/Christie_LAS_Slim.zip ... --item christie_slim`, a pack deleted on 2026-11-14.
  The example now names `Christie_LAS.zip` / `christie` and was run to confirm it writes its nine PNGs.
- `tools/pd2-port/check_all.py` still said "19 zips" in the module docstring that describes what
  `--full` adds. It is 20.
- `docs/renders/christie/model/clover/README.md` was the only model render page not in the
  structured form its siblings use, and it omitted the HUD/menu icon that its six-panel sheet carries.
  Rewritten to match, with the normal-map and cutout caveats that the in-game check has to settle.

`docs/pd2-las/in-game-checklist.md` had sections for `Miranda_L4D2_LAS` and `Christie_LAS` only, so the
two packs whose bytes are newest and unverified — `Christie_Clover_LAS` and the `Honoko5` jewelry diffuse —
had no checklist to be checked against. Both now have one, numbered in the page's existing style, and
`tools/pd2-las/README.md`'s "Next" lists them.

## 2026-11-22 — OfficeSuite gains a first-person arms unit

At the owner's request ("make FPS model for hands" for OfficeSuite.zip), `OfficeSuite` now ships
`fps_officesuite.model`: the same slimmed, cleared outfit arms as the third-person body, cut at the
wrist with the heister gloves spawning on top, registered with an `fps_unit`, `DEPTH_SCALING`
materials, no head drawables and no authored hands. The third-person body is untouched and
`Honoko2`..`Honoko4` reproduce their previous tracked bytes. The in-game first-person check is the
third item in the OfficeSuite section of `docs/pd2-las/in-game-checklist.md`. The
`runtime_verified` flag stays `false`; the unit is new tracked bytes, unseen in game. See D53.

## 2026-11-22 — Honoko5 is renamed OfficeSuite

At the owner's request ("change the name of Honoka5.zip to OfficeSuite. And change description to
'OfficeSuit [LAS]'"), the pack is renamed end to end: the ZIP (`OfficeSuite.zip`), the registration
(`officesuite`), the hooks, the unit paths, the material slots, the localizations
(`bm_askn_officesuite`, description `OfficeSuite [LAS]`, menu name `OfficeSuite`), and the native
Hila override it feeds (`OfficeSuite_Miranda_Romance_over_Hila.zip`). The recorded renders and
captures are renamed along with it. The third-person geometry, slim, clearance and colourway bytes
are the same as the pre-rename build. The in-game first-person check stays the third item in the
OfficeSuite section of `docs/pd2-las/in-game-checklist.md`. See D54.

## 2026-11-23 — OfficeSuite and the Hila override wear the outfit's own hands

At the owner's request ("can you change vanila hands in Hila?", "Office Suite LAS too. Office suit
donor hands. you just need to remove vanila wrist skin"), `OfficeSuite` stops cutting the source at the
PD2 wrists: `PackSpec.hands=True` skips `cut_group_at_wrists`/`_cap_wrist_cuts` for it, so the donor's
palms, fingers and bracelet stay in the third-person body, the shadow caster and `fps_officesuite`, on
the PD2 `Hand` and finger bones the template's own `g_body` already uses. The pack registers no
`glove_adapter.lua` any more; `Honoko2`..`Honoko4` keep the cut and the adapter and reproduce their
previous tracked bytes. The native Hila override inherits that body, turns Hila's stock `g_hands` off,
deletes the glove block from her unit model, and loses the cuff tuck (`Cuff`, `_measure_cuff`,
`_pull_weights`) that used to push the cut rim inside the glove lip. `build_models.template()` exposes
the `Template` view of a model already in memory, which the override uses for that deletion. The
renders of both packs are regenerated; the wrists now show the outfit's skin and sleeve cuff where the
vanilla blue gloves were. `runtime_verified` stays `false` and the wrists are the first thing on the
Hila and OfficeSuite in-game checklist items. See D55.

## 2026-11-23 — `OfficeSuite_Head`, then `Honoko2`..`Honoko4` removed

Two changes of the same day. First `OfficeSuite_Head` (`LegendaryArmours.officesuite_head`) joined
`OfficeSuite`: the same body, hands and first-person arms with the ME2 Romance head and lashes from
the Hila override, in one `WHOLE_CHARACTER` unit, `replace_all` with `hide_mask` (D56). Building it
found two bugs worth keeping in mind: the donor head's palette order is its own, so a head re-skinned
by enumerating the donor's influence indices binds to `Hips` and rides the hips — `las_head.load` maps
each influence through `HEAD_BONES.index(name)`, and an invariant now fails if a head vertex lands on
the hips bone; and `BUILD_INFO` recorded the head donor as an absolute path, which made the tracked zip
impossible to reproduce from another tree (that is what `fresh` builds) until it was recorded
repo-relative like `dae` and `skin_archive`.

Then the user removed the three earlier builds of the same source: `Honoko2` (base proportions),
`Honoko3` (5% slim) and `Honoko4` (slim, alternate suit). `PACKS` is `OfficeSuite` alone, so
`make honokodae` writes one zip. The zips and sidecars are deleted; their bytes remain in git history.
The slim and clearance passes and `SHADOW_DROPS` stay, because `OfficeSuite` is built with them, and
the three tests that compared the variants now assert the same properties on `OfficeSuite`'s own
tracked bytes rather than against a sibling that is gone. `OfficeSuite`'s bytes did not change. See D57.

## 2026-11-23 — an outfit with its own hands stops relying on LAS's glove bug

The user's rule: "For office suit with head LAS - I don't want to use vanilla gloves. Only hands
from the model", scoped to every pack this builder produces, with a deliberately equipped glove
still allowed to win (D58). Both OfficeSuite packs already behaved that way, but only because LAS
4.1.9 reads `default_glove_id` off a fresh table and so leaves it `false` — an upstream bug. That
is not something a pack should depend on silently, so each pack with `PackSpec.hands` now ships
`<item id>_own_hands.lua`: `default_glove_id = false` on purpose, and `body_replacement.hands`
kept true so the stock hands stay hidden behind the modelled ones. The `hands = false` line is the
*adapter* hook's, for packs with no hands; copying it here would show the heister's bare hands
beside the outfit's.

`tests/test_glove_behavior_lua.py` now runs the own-hands hook against the real loader in four
combinations, including the one that matters: a LAS that reads the outfit's own field (patched
fixture) with no hook spawns a real glove over the modelled hands, and with the hook it does not.
Installing `lupa` for it is worth it — that suite had been skipped in this sandbox all along.
`OfficeSuite`'s and `OfficeSuite_Head`'s geometry and textures are unchanged; the zips gain the one
hook and the `main.xml`/`BUILD_INFO` lines that name it.

## 2026-11-25 — the palms come off, and where the palm begins is a number

The user reversed D55: "remove the palms from the OfficeSuite packages and make explicit where the
palm begins", scoped to `OfficeSuite`, `OfficeSuite_Head` and the native Hila override (D59). The
boundary is the palm's starting line, not the wrist joint.

`build_models.palm_planes` defines it on the rig: origin = the `Hand` joint (the same point
`ARM_JOINTS` calls the wrist), axis = mean of `Hand{Index,Middle,Ring,Pinky}1` minus that joint. On
the 2B bind pose that axis is 3.98° off the forearm axis — the heel of the hand, which is what a
wrist-plane cut leaves on the sleeve. `tmc_las.cut_group_at_planes` is the generalised cut (the old
`cut_group_at_wrists` is now a wrapper over it, same cone radius of 28 cm, same rim behaviour);
`cut_group_at_palm_bases` is the palm wrapper — and the wrist wrapper drops the new
`removed_vertex_ids` key from its report, because the two Christie packs persist that report in
their `BUILD_INFO.json` and their tracked bytes must not move (they rebuilt byte-identically). `PackSpec.hands` became a mode, `"own"` or
`"palm_cut"`, and both OfficeSuite specs are `"palm_cut"`.

`BUILD_INFO.json` now carries what "where the palm begins" resolves to, per side: `origin_cm`,
`axis`, `deg_from_forearm`, `kept_to_cm` (how far short of the plane the shipped mesh ends, measured
after the slim and clearance passes), plus `removed_tris`, `rim_cap_tris` and the vertex count per
bone the cut took. On the tracked bytes: 2,276 triangles removed, 25 cap triangles, 2.22 cm / 2.27 cm
short of the plane, 31,577 body vertices (61,347 after the 5% slim). The build now fails if the cut
would remove geometry dominated by anything but a hand or the forearm edge.

Registration went back to the adapter: `glove_adapter = true`, `own_hands = false`, and the packs
ship `officesuite_glove_adapter.lua` / `officesuite_head_glove_adapter.lua` instead of
`*_own_hands.lua`. `build_hila_body_mod.py` lost the glove deletion: her `g_hands` node stays
enabled in both `.object` files, her glove block stays in the unit model, and no `.object` is
patched at all any more — there is nothing to gate, because her gloves are the hands now.

Tests: new `tests/test_palm_cut.py` pins the landmark to the rig, the record to the mesh and the
mesh to the landmark; the OfficeSuite tests in `tests/test_pd2_las.py` and the whole-character
invariant in `tests/test_pd2_las_invariants.py` follow the new facts (31,577 vertices, the adapter
back, no hand-dominated vertex). `tests/test_hila_body_override.py` inverted its glove assertions:
the two models and the two material configs are the only changed files, the glove block and its
node survive, the hands are gone from the body. The render sheets were re-rendered; the native-Hila
sheet draws her stock gloves flat-shaded, because their material samples a vanilla glove texture
that a replacement pack does not ship.

`runtime_verified` stays `false` in both packs; the wrist and glove steps are in
`docs/pd2-las/in-game-checklist.md`.

## 2026-11-25 — the palm cut moves onto the plane, and the vanilla wrist skin comes off

The D59 build was seen in game. The user's screenshot showed, from the sleeve down: bare forearm, a
salmon band with a seam in it, then the black glove. That band is `hnd_forearms`, the vanilla *bare
forearm* the glove adapter spawns between a glove cuff and a short sleeve — a second, vanilla skin at
the wrist, drawn outside the outfit and impossible to hide with our material or geometry. Their
instruction: *"Forbid using previous method. Go back to previous version. AND ONLY REMOVE the palm
and fingers. So the standard skin should have no hands. You should remove exactly where palm begins.
But choosing another gloves would give those gloves."* (D60.)

Two changes, one per half of that:

- **The cut is made on the plane.** `tmc_las.clip_group_at_planes` splits a straddling triangle where
  its edges cross the plane, interpolates position, normal, UV and skin weights at the crossing,
  drops the distal part and keeps the proximal one; crossing points are cached per *edge*, so
  neighbouring triangles share them and the rim stays one watertight loop for `_cap_cut_rims`.
  `cut_group_at_planes` is untouched, so the two Christie packs still rebuild byte-identically.
  `cut_group_at_palm_bases` stays as the coarse form; the build now calls
  `clip_group_at_palm_bases`. On the tracked bytes: `clipped_to_cm` 0.00 both sides (was 2.22/2.27
  short), 64 triangles split, 66 vertices added, 2,276 triangles removed, 68 cap triangles,
  31,643 body vertices (61,479 after the 5% slim) and `kept_to_cm` −0.76/−0.79 — the last two
  hundredths of that are the slim pulling the arm in, not the cut.
- **Registration goes back to D58's hook.** `glove_adapter = false`, `own_hands = true`: no default
  glove unit spawns and the stock hands stay hidden, so the pack's own body — hands cut off — is
  what shows, and a glove the player picks by name is the only thing that puts hands on the
  character. `render_own_hands_lua`'s docstring and file header now say so, and say why the adapter
  is not the answer. The Hila override keeps its `g_hands` drawable and glove block, unchanged from
  D59, because a chosen glove needs somewhere to land.

`BUILD_INFO.palm_cut` gained `exact`, `tris_split`, `verts_added` and per-side `clipped_to_cm`;
`registration` flipped both flags. Tests: `tests/test_palm_cut.py` gained a box test that shows the
difference in one place (the clip ends exactly on the plane with one closed rim loop of eight edges;
the whole-triangle drop keeps nothing above the plane's last full face) and the pack tests now pin
`exact`/`clipped_to_cm`/`kept_to_cm` and the flipped registration;
`tests/test_pd2_las.py::test_officesuite_carries_the_alt_suits_and_cuts_the_palms` carries the new
vertex counts (31,643 / 61,479) and the flipped flags;
`tests/test_pd2_las_invariants.py::test_whole_character_packs_bring_their_own_head` carries them for
the head pack. All five render sheets of these packs were re-rendered, and the native-Hila caption no
longer claims her gloves cover the cut in game.

`runtime_verified` stays `false`: D59's bytes are the ones that were seen, these have not been.

## 2026-11-25 — only the streamed voice pack ships

The user asked for `dist/Hila/Miranda_Lawson_VO_over_Hila.zip` to go, keeping only the `_Stream`
pack (D61). The BeardLib pack was the route that was installed on 2026-11-24 and never played a
line; the id-keyed `.stream` pack was heard working on 2026-11-25. So: the zip and its `.sha256` are
deleted, and everything that would have built it back is deleted with it — the `voices` make target,
the `voices` stage in `fresh.py`, and `status.TARGETS`' entry for the pack.

`tools/build_hila_voice_mod.py` was the BeardLib builder *and* the clip library the stream pack
imports, so it is now `tools/hila_voice_clips.py`: the archive listing, the picks and splits, the
cutters, `match_level` at `-1.5 dBFS` and the stem heuristic stay, the `<Sounds>` XML, the README and
`mod.txt` text, the zip writer and the packaging `main()` go. `main()` now only refreshes the tracked
`hila_slot_pieces.csv` build manifest (run it directly; it has no make target, since it builds no pack),
which is what `fit_hila_intents.py` also writes. `tests/test_hila_voice_pack.py` became
`tests/test_hila_voice_picks.py`: the route-independent half is kept (a pick for every slot, no name
in the text that is supposed to be cut out, real windows), the `<Sounds>` keying tests go with the
route, and a new test pins the packaging — no BeardLib zip in `dist/Hila`, no target or `fresh` stage
that builds one, no builder file. `tests/test_hila_cut_edges.py` follows the rename.

Docs: `docs/pd2-voice-mod-install.md` now opens on the one pack that ships, with §1–§6 marked as the
record of the dropped route; `voice_lines_vox/README.md`, `tools/README.md`, `tools/pd2-las/README.md`
and the in-game checklist follow; `HANDOFF.md`'s row records the pack as dropped rather than as an
install-environment failure.

## 2026-11-25 — the streamed voice pack is heard in game; two clips are cut again

The user installed `dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip` and reported that it **works**:
Hila's barks are Miranda's through the id-keyed route, which the BeardLib pack did not manage on
2026-11-24. The same report named two clips whose cuts land inside a word:

- `civ.down` — `procer_cover_tutorial_a_S_INT.011.ogg` 0.020–1.020, heard as "keep you head down,
  Shep". The 1.020 edge is 0.2 s inside "Shepard": the name's "sh" starts at 0.82 s (4–9 kHz is
  65–84% of the energy from there) and runs to 1.20 s, so the clip ended mid-name.
- `call_teammate.hey_you` — `profre_cover_tutorial_a_S_INT.002.ogg` 1.310–2.180, heard as "just
  you". The 1.310 edge is on the "-ard" of "Shepard," and 2.180 is inside the next word's fricative,
  so the clip carried a fragment at each end around "you take point".

Both edges are now measured rather than eyeballed, on the same acoustic reading: level per 20 ms
plus the share of energy between 4 and 9 kHz, which separates a fricative ("sh", "t") from the
nasal and vowel tails around it. `civ.down` is **0.020–0.810** (ends in the 0.78–0.80 gap, 0% high
band, with the "sh" of the name at 0.82 untouched) and `call_teammate.hey_you` is
**1.450–2.105** (the `-ard` behind the start, the closing fricative after the end, the plosive
closure of "point" inside). Clips: 0.79 s and 0.66 s instead of 1.00 s and 0.87 s, so the stream
zip is 13.9 MB rather than 14.9 MB and 204 ids carry the shorter audio.

`slot_picks.csv` and `hila_intent_fit.csv` carry the new windows and say what the edges were moved
onto; `tools/build_hila_voice_mod.py` regenerated `hila_slot_pieces.csv` from them on the rebuild.
Both packs were rebuilt (`voices`, `voices_stream`) — the BeardLib twin ships the same two clips as
OGG.

`tests/test_hila_cut_edges.py` decodes the two source oggs out of the tracked archive (with the
pinned `py7zr` and `imageio-ffmpeg`, no skip) and pins the edges: the `civ.down` cut ends on a 0%
high-band tail with 80%-high-band speech starting at the edge, and the `hey_you` clip is gap to gap
with the "t" burst and the "point" closure inside it. It is the test that would have caught the
clip the user heard.

Nothing else was listened to line by line; the other picks have not moved. `runtime_verified` stays
`false` in both packs, and `HANDOFF.md` records the 2026-11-25 report as a *partial* — the route is
confirmed, the tracked bytes are not what was heard.
