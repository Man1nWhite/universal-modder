# PAYDAY 2 LAS — review journal

## 2026-11-27 — the supplied eye reaches the outfit pack, and the head pack catches up with it

`dist/Miranda_L4D2_LAS.zip` and `dist/Miranda/Miranda_L4D2_over_Hila.zip` are rebuilt. The outfit's
`miranda_eyes.texture` is now `references/textures/EYE_Diff.png` - `supplied_eye_values()` /
`supplied_eye_texture()` in `build_las.py`, the picture cropped to the eyeball's own planar map at a
measured 2.7x - where it had been the eye `build_las` drew. The drawing (`eye_values`, `draw_eye`,
`eye_texture`) is retired with it, and `mip_audit.py` judges the supplied picture instead: the shipped eye
is closer to the picture than the drawing was on every limit, and the per-texel colour limit is now missed
from 128x128 down (the picture's sclera has veins where the drawing had a smooth field) and the iris limit
at 16x16 and 4x4; `KNOWN_MISSES` lists exactly that, and every other encoder tried misses the same levels.

The head pack's eye quadrant was stale: it had been built from the 2026-11-15 repaint before that day's
second repaint, while the builder reads the tracked picture as it is. `test_hila_packs_replace_the_ecp_unit_and_use_the_supplied_eye`
was failing on the merged tree because of it; rebuilt, the quadrant is the tracked picture's 2.03 crop
again and the test passes.

New besides the packs: `tools/extract_beard_textures.py` writes Geralt's beard out of
`Geralt_over_Rust.zip`'s head atlas as textures of its own under `references/textures/`
(`geralt_beard_df`/`_nm`, PNG and DXT5 DDS with full mips). It only reads `dist/`. Reasoning: D84.

## 2026-11-26 — the Romance line is retired (D83)

`dist/Miranda_Romance/Miranda_Romance_LAS.zip`, `dist/Miranda/Miranda_Romance_over_Hila.zip` and
`dist/Miranda/OfficeSuite_Head.zip` are deleted with everything that existed only for them: the `lawson`
and `honokodae_head` make targets and their `tasks.py` entries, `tools/pd2-las/lawson-las.yml`, the
Romance builder in `tools/build_joy_head_mods.py`, `las_head.py` and its test file, five render paths, and
the Romance-only half of `tools/pd2-port/` — `build_las_pack.py`, `rig_target.py`, `las_model.py`,
`preview_check.py`, `shade_check.py`, `check_guide_compliance.py`, `check_nm_convention.py` and
`check_test_suite_mutations.py`.

Nothing unique went with them. `OfficeSuite_Head` and `Miranda_Romance_over_Hila` carried a
byte-identical `g_head` `MODEL_DATA` payload (`8125a6c6cb6066f7`) and the same four head textures, so the
head that survives (`Miranda_L4D2_over_Hila`) is that head, and `Miranda_L4D2_LAS` is the outfit. What is
gone is the ME2 Romance character's LAS route and the no-LAS install route.

`tools/pd2-port/` stays as the archive reader and the gates that still apply: `dds.py`, `dmodel.py`,
`me2_dae.py`, `check_links.py`, `check_skip_budget.py` and `check_mesh_geometry.py`, with `check_all.py`
pack-only and no default pack. `status.py` reports one LAS target. Tracked zips: twelve → nine, and the
overview sheet re-rendered to nine cells.

## 2026-11-26 — the native Hila override is retired (D82)

`dist/Miranda/OfficeSuite_Miranda_Romance_over_Hila.zip` and its sidecar are deleted, with the table row,
the `hila` make target, the `tasks.py` entry, `tools/build_hila_body_mod.py`, its test file and its render.
The pack combined OfficeSuite's body with the ME2 Romance head on Hila's own unit with no LAS; both halves
ship without it (`OfficeSuite_Head` as one whole-character LAS item, `Miranda_Romance_over_Hila.zip` as the
head over Hila), so what went is a second install route, not content.

It was also `OfficeSuite_Head`'s head donor. The two over-Hila replacements carry a byte-identical `g_head`
`MODEL_DATA` payload (`8125a6c6cb6066f7`) and the same four head/lash textures, so the builder now reads
`Miranda_Romance_over_Hila.zip`; rebuilt from it, `OfficeSuite_Head` differs from its previous bytes in one
member and two lines — `BUILD_INFO.json`'s `head.donor` and `head_donor` — with the other 28 members
byte-identical. `las_head.read()` takes the donor's name as a parameter so no report names the retired pack.

Also fixed while here: `render_mod_previews.py --unified` crashed at the end (it saved the overview under
`00_all_dist_mods_overview.png`, a key `UNIFIED_PATHS` no longer had). The overview it then wrote is the
first in a while — the tracked one still carried a full extra row of packs retired on 2026-11-26, including
this one. Tracked zips: thirteen → twelve.

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

## 2026-11-25 — the arm is cut 4 cm past the palm line, so it ends inside the glove

The D60 build was seen in game, at the wrist. Two screenshots from the user showed what the cut had
done: the arm ended in a flat cap in mid-air, with the heister's black glove cuff below it and a
visible gap between the two. Their instruction: *"you need to extend forearms a bit"* (D62).

The cut was in the right place and the wrong one at once. D60 put it exactly where the palm begins,
which is the right landmark for "no hands", but a PD2 glove is modelled around a hand, so its cuff
starts below the outline of one and never meets a cut made on the crease. The fix is to extend the
arm into the glove, not to add anything: `PALM_EXTEND_CM = 4.0` in `build_honoko2_dae.py` is passed
as `margin=` to `tmc_las.clip_group_at_palm_bases`, so the split plane moves 4 cm along the palm's own
normal, into the palm, and `_cap_cut_rims` caps the ring in a window of `margin − 1.5 .. margin + 0.5`
cm instead of around the plane. No spawned piece, no adapter, no vanilla skin: D60's registration
stands exactly as it was.

Four centimetres is under two thirds of a palm's length, so no finger geometry comes back: the cut
now takes no forearm-dominated vertex at all (the `ForeArm` entries left `removed_bones`), and what
survives at the rim is `Hand` (152/153 vertices) plus the thumb's *base* — the thenar, 15 vertices a
side — which is the palm's own proximal few centimetres and what makes the end continuous with the
wrist. On the tracked bytes: `clipped_to_cm` 4.00 both sides, `kept_to_cm` 3.97/3.99 (the slim
pulling the arm in, again), 76 triangles split, 78 vertices added, 2,070 triangles removed, 88 cap
triangles, 31,804 body vertices (61,801 after the 5% slim). Packs: `OfficeSuite` 5,766,633 B,
`OfficeSuite_Head` 10,384,852 B, `OfficeSuite_Miranda_Romance_over_Hila` 14,855,124 B.

`BUILD_INFO.palm_cut` records `margin_cm` (the plane the split used) and `extend_cm` (what the module
asked for), so a build cannot drift from the source number without saying so. Tests: the pack tests
in `tests/test_palm_cut.py` pin both fields at 4.0, the shipped mesh reaching 3.8–4.0 cm past the
palm line and no further, and the thenar as the only finger bone left; the stray-bone assertion is
now `[]` rather than `["LeftForeArm", "RightForeArm"]`, and the whole-triangle rim expectation follows
the moved window. `tests/test_pd2_las.py` carries the new vertex counts and `clipped_to_cm`, and
`tests/test_hila_body_override.py::test_the_outfits_hands_end_where_the_palm_begins` follows the
override's body into the palm instead of stopping it at the crease. The
sheets under `docs/renders/honoka/model/` were re-rendered.

`runtime_verified` stays `false`: the D60 bytes are the ones that were seen, these have not been. The
in-game checklist's wrist step now asks that the cap sit inside the glove with no gap above it.

## 2026-11-25 — the extension is 1.5 cm, not 4: the glove is only so big inside

The D62 build was seen in game at the wrist, and the user's answer was three words long:
*"Too much."* Two screenshots showed the arm reaching the glove and coming out of it — the palm's
surface showing through and around it. The gap was closed; the fix overshot.

Where the limit is can be measured, because the glove is in the repository. The game draws
`g_hands`, and `references/npc_criminals_ecp_female.7z` carries one on the same rig: its `Hand`
joint sits at `[-45.98, 18.69, 124.47]` where this body's palm origin is at
`[-45.99, 18.70, 124.47]`. Measured along this body's palm axis, that glove starts **0.42 cm past
the crease** and is **3.5 cm in radius at its rim**, 4.0 at 2 cm, 4.3 at 3 cm. This outfit's wrist
is 3.46 cm in radius, its palm 4.4 at 2 cm and 5.6 at 3. So there is about a centimetre and a half
of glove the arm fits inside, and past that the palm is wider than the glove and comes through it.

`PALM_EXTEND_CM` is 1.5. Renders of the same body cut at 1.0, 1.5, 2.0 and 2.5 cm, with that glove
composited over it (flat-shaded, three angles), were compared before choosing: 1.0 leaves the
slim-pulled end at 0.27–0.33 cm, short of the 0.42 cm rim; 2.0 and 2.5 show the silhouette breaking
at the cuff. On the tracked bytes: `clipped_to_cm` 1.50 both sides, `kept_to_cm` 0.90/0.83 (the 5%
slim pulls the end back about half a centimetre at this depth), 67 triangles split, 69 vertices
added, 2,224 removed, 71 cap triangles, 31,674 body vertices (61,541 after the slim). At 1.5 cm the
cut is still inside the wrist, so **no vertex of the shipped body is dominated by a hand or finger
bone at all** — D62's kept thenar is gone with the rest of the palm, and only the rim carries a
handful of forearm-dominated ones. Packs: `OfficeSuite` 5,739,451 B, `OfficeSuite_Head`
10,357,873 B, `OfficeSuite_Miranda_Romance_over_Hila` 14,830,470 B.

`BUILD_INFO` records 1.5 in both `margin_cm` and `extend_cm`. Tests: `tests/test_palm_cut.py` pins
the reach to 0.6–1.5 cm **and** past the glove's 0.42 cm rim, drops the thenar allowance and lets
the rim take a handful of `ForeArm` vertices; `tests/test_pd2_las.py` carries 31,674 / 61,541 and
`clipped_to_cm` 1.5; `tests/test_hila_body_override.py` carries the same body and cut. The sheets
and their captions were re-rendered at the new depth.

`runtime_verified` stays `false`: D60 and D62 are the builds that were seen, this is the third
answer to the same wrist, and the checklist's wrist step is what settles it.

## 2026-11-25 — two barks are picked again: "No calls." and "Stop."

The user listened to the stream pack in game and named two lines (D61's route, so these are the
shipped clips):

- **`civ.nophone`** was "There's nothing we can do," — despair, not the warning the bark is: Hila's
  line for it is *"If you try to make a phone call, it would be your last."* The pack has no phone
  line at all (no "phone", "call", "police" or "cops" anywhere in the 866 transcripts), so the pick
  is now the one take that reads as *don't do that*: **"I'd rather we didn't."** —
  `norvx_starter_h_S_INT.006.ogg`, `0.000-0.960` (the whole file: the line to 0.82, the "didn't"
  release to 0.95, then the gap).
- **`cop.hands`** played as a chopped "smi". It was cut `0.420-0.650` of
  `norvx_relationship_03_h_S_INT.037.ogg` = *"and stop smiling, dammit."*, and 0.42 is where the
  **next** word starts. Measured on the source: "and" runs to 0.08, the `/s/` of "stop" is
  0.10-0.17, the `/t/` closure 0.19-0.22, the `/ɑ/` 0.22-0.32, the `/p/` decays by 0.34, then
  silence to 0.40 — and 0.42 is a 53%-high-band fricative, the `/s/` of "smiling". The pick is now
  `0.090-0.360`: the word itself, from its own `/s/` to the gap after the `/p/`.

Both are edge measurements, not guesses, and `tests/test_hila_cut_edges.py` now measures them
again: the `cop.hands` test asserts a fricative in the head of the clip, a high-band-free vowel in
the middle, a gap at the end, and — so the diagnosis cannot go stale — that 0.420 s is still the
fricative it was mistaken for; the `civ.nophone` test asserts the take is whole, from its first
sound to the gap after it. `voice_lines_vox/README.md`'s "known gaps" list says the same in one
line each.

`slot_picks.csv` carries the two rows with their reasoning, `hila_intent_fit.csv` and
`hila_slot_pieces.csv` were regenerated by `tools/fit_hila_intents.py`, and
`dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip` was rebuilt: 13,926,249 B against 13,926,657.
`runtime_verified` stays `false` for the pack; the two new clips are unheard, and the checklist's
voice step is what settles them.

## 2026-11-25 — the Arivus face is shaved properly (D64)

"And improve Arivus more", on the evidence of the offline portrait, which showed a black crescent
around each ear, a straight seam down each side of the face and across the jaw, and a flat lower
face. All three came from `shave_arivus_face`:

- The crescent was the ear protect ellipse being smaller than the sideburn painted over it, with a
  `MaxFilter(9)` "ring" that inpainted *around* the ellipse instead of over the beard outside it.
- The seam was the harmonic fill's box (`y 130:356, x 128:400`) ending in a hard edge.
- The flat jaw was one median skin tone (`lum 146.8` against the chin's `98.5`) relaxing across the
  whole U, and a mask that stopped at the geometric hairline while the painted beard edge is soft —
  which also left a reddish stipple at 30–40% coverage.

The mask now grows along the beard (every pixel darker than 90% of this raster's own skin level,
stopping at the ear's lighter rim), the fill is relaxed from the clean skin ring around it and then
tone-matched to that ring at a ±15% gain, the raster's own pore-and-freckle structure is added at
1.10x from a clean patch, and the result is feathered into the untouched skin over 2.5 px. The lips
are measured rather than boxed (redness 52..64 against the moustache's 35, `x 210..298, y
252..292`), the mouth slit is kept by taking each column's span between its top and bottom lip
pixel, and nothing is dilated past the lip — one pixel of dilation is enough to paste a dark lip
liner back on.

Measured: dark pixels in the beard box fall from 73.0% to 0.48%; the jaw's high-pass structure is
6.40 against the clean cheek's 9.62 (0.67 of it, and zero before); the mask's bottom row steps no
more than the rows inside the face; ears, brows and lips change by at most four pixels; the alpha
channel and the 512x512 layout are untouched. `tests/test_arivus_shave.py` holds all of it, plus
that two runs are byte-identical. Sheets re-rendered with `--unified`; the pack is 8,436,333 B
(`7056d2476ab5`) against 8,281,629.

`runtime_verified` stays `false`: the portrait is a software Z-buffer with diffuse textures, and
the in-game checklist's Arivus step is what settles whether the shave reads as skin.

## 2026-11-25 — the wrist cut a little shorter, the shave only on the beard

Two reports from the game, both actionable.

**`OfficeSuite_Head` (D65).** *"Pretty close, just need to cut a bit more."* The hands are off and
the cuff covers the wrist, but the in-game screenshots show a wedge of skin through the glove's cuff
at the wrist bend. `PALM_EXTEND_CM` goes 1.5 → **1.25**: the last half-centimetre of the arm is its
fattest (4.0 cm in radius against the glove's cuff at 3.5–3.9) and that is the part finding its way
through. Measured: `kept_to_cm` 0.61 / 0.53 after the slim, both still past the glove's 0.42 cm rim,
`g_body` 31,666 vertices (61,525 slimmed), no hand-dominated vertex. Packs: `OfficeSuite`
5,737,727 B, `OfficeSuite_Head` 10,356,127 B, `OfficeSuite_Miranda_Romance_over_Hila` 14,828,794 B.

**Arivus (D66).** *"Still need work on textures."* The portrait showed it: D64's mask grew from the
beard through every pixel darker than 90% of the raster's own skin level, and on this raster that is
the *whole face* - so the flood repainted the cheeks, the nose's flank and the eye sockets, and its
bounding box left a soft rectangle. The growth is now a rim of 8 px around the geometric beard
(`MaxFilter(17)`); the face keeps its own shading. Two follow-ons: below the mouth slit, pixels
darker than 70% of skin go back to the mask (the ped paints hairs onto the skin under the lower lip
and a few passed the lip test, which is what pasted a "soul patch" on), and stranded single hairs
inside the filled area are swept into the local fill. The shave now changes 18.9% of the raster
instead of repainting the face; the chin patch goes from luminance 94.3 to 123.4. Pack 8,433,226 B
(`6b356c19e0d8`).

`tests/test_arivus_shave.py` holds the new behaviour (including the chin patch and the unchanged
lips), and the sheets were re-rendered. `runtime_verified` stays `false` for every pack involved.

## 2026-11-25 — `call_teammate.hey_you` is one shouted "You"

The user heard the re-picked three-word clip ("you take point", 0.667 s) as just "you" and said what
they wanted: *"She just needs to shout 'you'."* The pack's own bytes were not the problem — decoded
from the shipped `.stream`, the clip is 0.29 s of three syllables — so the conclusion is that the
game stops these lines earlier than ours run, and the answer is a line that is *one word*.

The pick is now the **"You" of "You don't know what my father wants for her."**
(`twrvxl_oldfriend_d_S_INT.043.ogg`, `0.000-0.300`): the /j/ onset at 0.06, the stressed /u/ peaking
-9.6 dBFS at 0.16-0.20, and the decay into the /d/ closure at 0.29-0.31, which is where the cut ends
— "don't" starts at 0.33, so nothing of it is in the clip. It is the most emphatic bare "you" in the
866 transcripts: no /l/ of "you'll", no following word. Level-matched to -1.4 dBFS peak like every
other bark, and short enough (0.289 s) that a third of it cannot be all the game plays.

`tests/test_hila_cut_edges.py` measures it again — silence at the head, the vowel within 3 dB of the
clip's loudest point, the tail inside the closure, and the next word still where the cut assumes it
is — and `slot_picks.csv`, `hila_intent_fit.csv` and `hila_slot_pieces.csv` carry the new row. The
stream pack is rebuilt: 12,608,121 B (`6b7d827dfe93`) against 13,926,249.

## 2026-11-25 — Arivus takes its skin tone from the jaw it meets

**Arivus, the colour (D69).** *"Work more on Arivus texture - check renders."* The portrait from D66
still showed a grey mask over the jaw. The tone match was using the raster's global skin patches
(172,134,123), which are the **forehead**, not the jaw's skin: measured around the beard, the clean ring
is ≈ (148,105,90), a much warmer value. Using the pale median as the reference desaturates the fill into
soot — the numbers can be made to agree with the forehead and it still looks wrong, because it is chroma,
not level, that reads as a mask. The fill now keeps its own luminance and is pulled 68% toward the
**local** ring's chroma, level-matched to that ring within ±10%, feathered 5 px, with the ring selection
widened to `clip(smooth(9) − smooth(4)) > 0.12` so it is a thin band just outside the mask rather than a
box. Final field (136.9, 101.1, 89.5) against the jaw ring's own (148, 105, 90) and the pale
(172, 132, 123) the old code had been matching; jaw luminance 110.5 ± 6.1 where it was 64.8 ± 41.4. Two
pins in `tests/test_arivus_shave.py` were rewritten to the new, deliberate behaviour: the beard is gone
in the sense that matters — 73% of the box was stubble-dark and 12% is now dark at all, but the hair's
strokes are what has to go, so the test also pins the box's high-pass energy at 18.2 → 7.0 (< 55% of
before) — and the lower lip lifts by 18 rather than 29, because the fill keeps its own light instead of
being flattened. Then the sheet changed the code twice more: the blend is faded outward over ~9 px
rather than stamped on a grown zone (a binary zone leaves a soft rectangle of its own), and the
sideburn boxes were widened to the ears, where the old ones stopped 18 px short and left a strip of
painted stubble in front of them. Pack: 8,420,283 B (`55cc0fc55b35`).

## 2026-11-25 — A round of semantic fit scores for the voice pack

The 2026-11-24 stale sweep noted `hila_intent_fit.csv` carries "pinned" in the score column for every
slot — it records *that* a clip was hand-picked, never *how well* the pick serves the slot. This
round scores all 78 slots 0–10 on semantic fit to the slot's **game intention** (the engine/sheet
event in `slot_event_ids.csv` and the dominant `hila_category` — what the bark *does* in the game),
not to Hila's wording. The artifact is `voice_lines_vox/miranda_lawson/hila_semantic_fit.csv`, one row
per slot with the category, the event, the clip and a one-line rationale. Nothing reads it at build
time; no clip, cut or level moved, and the pack's bytes are unchanged.

Mean 7.45, use-weighted 7.73. Thirty-four slots score 9–10. The ones below 4, in order:
`tech.drill_jam` 2 ("There must be some other explanation." — general bewilderment, no drill, no jam;
it belongs to `tech.generic` at best), `civ.nophone` 3, `cop.kneel` 3, `mark.taser` 3, `nade.smoke` 3
("Hostile fire." — bullets, not smoke) and `tech.fix` 3 ("You'll have to do it." — delegation, not
repair). Readers of this list should note the pack's own known-gaps section already flags that
`cop.*`, `civ.nophone`, `tech.fix` and friends are closest-available takes from a pack with no
police, phone or repair vocabulary; the scores just say how far those compromises sit from the bark's
intention. Re-cut any of the below-4 slots if a better take is ever recorded.

## 2026-11-25 — The sub-8 lines are vanilla; the LAWSON takes are in (D68)

The user read the semantic-fit scores and said *"remove everything that is worse fit than 8. Use
LAWSON VOICE (PAYDAY 2).7z"* — and, asked about scope, that every slot with an archive take ships it,
8/8+ included. Two kinds of change followed.

The 33 slots with a take in `references/LAWSON VOICE (PAYDAY 2).7z` now ship it: the 28 PD2-bark-named
`Mira-*.mp3` files plus the 5 call-tagged files mapped per the user's answers (`uffs..` → `cop.cuffs`,
`nees..` → `cop.kneel`, `Tazer` → `mark.taser`, `gun_` → `cop.drop`, `Now._.` → `tech.fix`). They are
cut whole — an earlier pass kept only the silence-trimmed body and the first-window scan showed ~0.10 s
of digital silence at the heads that silencedetect (d = 0.15 s) had never reported, so every take now
carries a 30 ms pre-roll of the file's own leading silence and a 50 ms post-roll (sample-scanned above
-40 dBFS). `hila_semantic_fit.csv` marks them `replaced_tts` (the table was re-scored: 9s across the
board — the takes are purpose-authored for their slots; mean 9.1, use-weighted 8.88, nothing below 8
among what ships).

The 17 slots below 8 with no take anywhere are **out of the pack**: `assault.ready` (18 uses),
`civ.talk`, `civ.ties`, `cuffed.pick`, `drop.body`, `hurt.hit`, `hurt.medic`, `kill.medic`,
`kill.taser`, `mark.guard`, `mark.medic`, `move.on_me`, `move.this_way`, `nade.generic`, `pager.clear`
(32 uses), `pager.cover`, `tech.comp` — recorded in `removed_slots.csv` with the clip each slot played
and the reason. ~162 ids are absent from the rebuilt zip; vanilla Hila answers them. (Three of the
162 are also Vorbis and would not have been written anyway.)

`removed_slots.csv` is deliberately not a deletion from `hila_intent_cuts.csv`: the cuts table stays
the authoritative ID → slot map, and the builders (`hila_voice_clips.py`, `fit_hila_intents.py`,
`build_hila_stream_mod.py`) refuse to pick for removed slots and record `removed:` rows in the manifest
instead — so recording a take later revives the slot by editing one file. The pack rebuilds to
**14,405,864 B `3779f6a969f8`**: 699 `.stream` files (was 858), 661 s of audio, 61 slots. All voice
tests pass (`116 passed, 2 skipped`); `civ.down` and `civ.nophone` are re-pinned as whole-take
contract tests. The rebuilt bytes are NOT heard in game — the 2026-11-25 report was on the previous
build, and this one needs a fresh pass.

## 2026-11-25 — Geralt over Rust and Arivus over Old Hoxton, same stream route (D71)

The user asked for two more voice packs of the D68/D61 route: **Geralt over Rust** and **Arivus over
Hoxton**, clarifying for the latter *"not the brother to Dallas — Huston"* and then choosing the
**Old Hoxton** ped (`mtr_old_hoxton`, the target of `Arivus_over_Hoxton.zip`) from the options. Same
questions settled the rest: same route as Hila (the id-keyed `.stream` pack, not the BeardLib prefix
route); uncovered slots stay vanilla; the name-callout takes go to `call_teammate.hey_you` — the
Geralt set's 'Hoxton.' callout is borrowed for the Arivus pack, and Rust's hey_you stays vanilla
until the user supplies a take.

Both packs write the **same shared regular_vox voice-line ids** as the Hila pack — they are
alternatives, not companions (install one; last loaded wins otherwise) — and they are the same
885-id table with per-pack coverage from purpose-authored bark sets:

- `dist/Geralt/Geralt_VO_over_Rust_Stream.zip` — `references/GERALT VOICE (PAYDAY 2).zip` ("Геральт",
  CP866 names). 29 covered slots, 315 `.stream` files (24 covered ids are also Wwise Vorbis),
  584 s of audio. Uncovered (49 slots, 546 ids): vanilla. Alternate takes in the set (`civ.down (2..4)`,
  `mask.go (2)`, `inspire.faster (2)`) are left unused and noted in `geralt/slot_picks.csv`.
  Rust = `npc_criminal_wild_1`; **whether he barks from `regular_vox` is not verified** — the
  original crew do, newer heisters are documented elsewhere as `char_<heister>`. The tracked bytes
  are not heard in game.
- `dist/Arivus/Arivus_VO_over_Hoxton_Stream.zip` — `references/ARIVUS VOICE (PAYDAY 2).zip`. 18
  covered slots + `call_teammate.hey_you` (the Geralt 'Hoxton.' callout, borrowed per the user's
  decision — that one slot is Geralt's voice), 324 `.stream` files (21 covered ids also Vorbis),
  442 s of audio. The set's peaks sit at −2.8…−7.5 dBFS, so the −1.5 dBFS peak match boosts them
  (max ≈ +6 dB, within the clamp). Uncovered (59 slots, 540 ids): vanilla. Not heard in game.

New builder `tools/build_character_stream_mod.py` (`--pack geralt-rust|arivus-old-hoxton|all`, make
targets `voices_geralt` / `voices_arivus`, in `all`) reuses the shared cuts table, the Vorbis list,
and the cut/level/encode helpers — the Hila builder is untouched and its bytes are unchanged. Picks
keep 30 ms of each file's leading silence and 50 ms of trailing (sample-scanned above −40 dBFS).
Tests: `tests/test_character_stream_packs.py` (16 tests: coverage invariants, zip contract, manifest
vs streams, ADPCM header/blocks, alternative-not-companion wording). Both packs rebuild byte for
byte (`737f1fb13616…` / `9e04ccfde24b…`); the sub-8 slot rule from D68 does not transfer — the sets
were authored per slot, so covered takes ship as-is.

## 2026-11-25 — all palm extensions reverted: the cut is back on the crease (D70)

The user's first-person screenshot of `OfficeSuite_Head` showed a wedge of skin past the white
glove at the wrist, and the instruction was to *"revert extensions, before 4 cm (D62)"*. D62 had
cut 4 cm into the palm to close D60's in-game gap; D63 reduced it to 1.5 cm when the palm came
through the glove, D65 to 1.25 cm when a wedge still showed. All three kept arm skin past the
wrist crease. This change takes `PALM_EXTEND_CM` back to **0.0**, which is D60's cut exactly:
`clip_group_at_palm_bases` splits on the plane through the rig's `Hand` joint and
`_cap_cut_rims` caps the ring there. The registration is untouched — `own_hands true`,
`glove_adapter false`, no default glove, and a chosen glove still supplies hands; the Hila
override keeps its own `g_hands`.

Measured on the rebuilt packs: `margin_cm`/`extend_cm` 0.0, `clipped_to_cm` 0.0 both sides,
`kept_to_cm` -0.76 (left) / -0.79 (right) after the 5% slim (the mesh stops just proximal of
the plane), 64 triangles split, 66 vertices added, 2,276 removed, 68 cap triangles, and a
shipped `g_body` of 31,643 vertices (61,479 after the slim) with no hand- or
finger-dominated vertex. `tests/test_palm_cut.py` now pins the plane and the zero extension,
`tests/test_pd2_las.py` the vertex counts and the clip record, and
`tests/test_hila_body_override.py` the same cut on the native override.

`runtime_verified` stays `false`: the D62 and D65 builds are the ones seen in game. The gap
that motivated D62 is the known trade-off of this choice, and the wrist step of the in-game
checklist now describes the current bytes.

## 2026-11-25 — Arivus: no rectangle on the face, no skin at the back of the collar

**Arivus (D72).** *"I want you to improve Arivus head mod. Check renders for mistakes."* Looking at
the compiled-portrait sheet found three: a dark rectangle across the lower face with a straight
edge under the eyes, a painted dark strip in front of each ear, and a jagged strip of skin through
the back of Old Hoxton's collar. The atlas showed two more: pale blobs beside the nose and hard
vertical inpaint edges at the temples.

The rectangle was the mask, not the fill. D64's "geometric U" started at `(135, 148)` and ran
diagonally to the moustache at `y ≈ 235`, while the sideburn boxes were 88 px wide from `y 140` to
`344`; between them they repainted the clean cheeks, eye corners and nose bridge. `shave_arivus_face`
now seeds on this raster's own dark hairs and floods through the softer stubble only inside the
zone a beard can occupy (lower face and narrow sideburn strips, with a tighter threshold at the
temples). A close/open pass bridges the gaps between strokes; the feature ring is confined to that
zone; only the cheek-facing edge of the ear ellipse yields its dark, low-redness hairs, while the
pink ear stays byte for byte; the two stubble ticks the lip column span used to protect at the
mouth's corners are given back to the mask. The beard box goes from 73% to 1.1% dark and its hair
strokes from 18.2 to 7.2 high-pass; the eyes and nose are untouched; the jaw fill is
(152, 110, 95) against the (91, 62, 52) stubble it replaced.

The collar strip was mesh: the ped's neck was cut at `z ≈ 159.4`, and from behind the front of
that neck showed through the suit's collar opening. The extraction now lowers the cut edge by 6 cm
and shortens the neck above it by 4 cm (both smoothly faded), so no back-half neck vertex remains
inside the opening and the throat still meets the front of the collar. The shaved raster is
`9083aa578e2eb6ac`; the pack is 8,429,027 B (`ad4cb8afafdc`). `tests/test_arivus_shave.py` gained
four upper-face pins (16 tests total) and `tests/test_arivus_neck_fit.py` checks all three shipped
models. Sheets re-rendered with `--unified`; `runtime_verified` stays false.

## 2026-11-26 — a compiled `.model` becomes `.glb` + `.dds` (`model_to_glb.py`, D73)

**The ask.** *"I want to transform arivus .model to .glb and .dds."* Neither half existed: the tree
could decode a Diesel unit (`diesel_model.py`) and rasterise it into a preview sheet
(`render_mod_previews.py`), but nothing wrote an interchange mesh, and the `.texture` side had only
ever been read. `tools/pd2-las/model_to_glb.py` does both, from a `.model`, a directory or a pack
zip, reusing `diesel_model` for the container and `tmc_export.Glb` as the tree's one glTF binary
writer (D16's rule: no second implementation of a format).

**Why the conventions are the hard part.** Four ways an export can be silently wrong, each pinned
by a test in `tests/test_model_to_glb.py` (10 tests, a synthetic unit written by the same codecs the
builders use — no game assets, no 2B templates):

- diesel is z-up centimetres and glTF is y-up metres, so `q = p @ A` with
  `A = [[0.01,0,0,0],[0,0,0.01,0],[0,-0.01,0,0],[0,0,0,1]]`; det > 0, so winding survives and no
  triangle is flipped (checked: face normals agree with the vertex normals on 100% of the Arivus
  head's triangles);
- glTF images start at the top-left and diesel's decoded `uv0` is bottom-up, so `v_gltf = 1 - v` —
  the same convention the tracked sheets were rasterised with, and the reason the exported atlas
  lands right-way-up;
- RenderAtom indices are **global** vertex indices (`AGENTS.md` invariant 2), so every atom is one
  primitive over one vertex buffer;
- DXT5nm (X in alpha, Y in green) is unswizzled to tangent-space RGB with `z = sqrt(1 - x² - y²)`,
  and `ALPHA_MASKED` keeps its `alpha_ref` (0.05) as `alphaMode: MASK`, so the hair cutout is
  there. A missing texture is a stable placeholder tint and a line in the report, never a crash —
  a shared suit unit references 20 textures no head pack ships.

**A real defect in the shipped Arivus pack, found by the skin path (open).** `g_head_old_hoxton`
weights four bones from `bone_offset=1` in `build_arivus_hoxton_mod` (the Clover/Bonnie/Sydney/Rust
convention, whose head palettes start at `Hips`), but its `SkinBones` section lists three bones
`[40, 41, 42]` — the vanilla suit's `Spine2, Neck, Head`. 4,582 of 4,596 vertices therefore carry
`BLENDINDICES 3`, one past the end of the palette, and the intended `Hips` entry (`37`, the skin
root) is not in the section at all. The exporter repairs exactly that shape — every stray index one
past the end, and the root's bind matrix present in another drawable's palette — by prepending the
root, and records it in the GLB's `extras.warnings`; the pack bytes are untouched and what the game
does with the stray index is unknown. The 2026-11-25 renders could not see this: they are
bind-pose, where the skinning matrices cancel. `tests/test_arivus_neck_fit.py` measures geometry,
not weights. Whether to rebuild the three Arivus models with `bone_offset=0` is the owner's call.

**Output and hygiene.** The conversion writes under `build/arivus_glb/` (ignored): three whole
models, a head+body+hands GLB for looking at the replacement, and five `.dds` (a PD2 `.texture` is a
DDS buffer, so this is a byte copy) with PNG twins for viewers that do not take DDS. Nothing
game-derived is committed. A round trip back through the repo's own rasteriser reproduces the
tracked sheet's head, eyeballs and hair cutout (`build/check_glb.py`); the suit is a placeholder
because its textures are not in the pack. `runtime_verified` stays false.


## 2026-11-26 — game-derived exports may ship, and the Arivus GLB does (D74)

**The ask.** *"Change the repo's rule about committing game-derived exports."* The owner chose the
repo-wide repeal and a checksummed ZIP: no blanket ban on game-derived assets anywhere in the
tree, and the pending Arivus head export tracked as a distribution pack rather than loose ignored
files.

**What changed.** `AGENTS.md` and `CONTRIBUTING.md` no longer forbid game files or extracted
assets; the mirrored skill docs, the knowledge-base checklist and `um publish check` say the same.
Decompiled code, secrets and the ownership/anti-cheat rules stay out. `um publish check --game`
now reports byte-identical game files as `INFO` provenance instead of a `FAIL`; the tests for that
lint were updated with it. D32's "the rules stay" is superseded by D74 in
`docs/pd2-las/DECISIONS.md`.

**The pack.** `tools/pd2-las/build_arivus_glb_pack.py` reads the tracked
`Arivus_over_Hoxton.zip`, calls `model_to_glb.py` for the `g_head_old_hoxton` drawable with its
bind-pose skin and all five `.texture` files, and writes `Arivus_Head_over_Old_Hoxton_GLB.zip`
with a fixed member order, the tree's one zip writer and a repo-relative `.sha256`. Inside: the
`.glb`, five `.dds`, a provenance README and a manifest of per-file digests. `make -sC
tools/pd2-las glb` builds it, `status.py` reports it, `fresh.py check` rebuilds it in a copy and
`tests/test_arivus_glb_pack.py` pins its members to the source pack's bytes. Two consecutive
builds were byte-identical. The loose ignored copies at the root of `dist/` from the earlier
turn were removed; this pack is the shipped form. `runtime_verified` stays false — it is a viewer
export, not a mod to install, and no bytes of it have been seen in game.

## 2026-11-26 — Arivus rebuilt with the supplied diffuse

The owner requested a rebuild using `references/old_hoxton_head_df.dds` and
selected transfer of its face onto the Arivus head. Inspection showed the input
is already an edited Arivus atlas, not a vanilla Hoxton UV layout: skin, eyes
and hair line up with the existing head mesh. The builder now reads it rather
than procedurally shaving the GTA texture, preserves the supplied DXT5 base
blocks byte for byte, generates the cutout-aware mip chain and renders the icon
from the edit. The Arivus geometry, flat normal, and other packs are unchanged;
the GLB export was rebuilt from the resulting head pack. The diffuse-only offline
preview is updated; the in-game appearance and animation remain unverified.
The pre-existing head skin palette issue documented in D73 is not changed by
this texture rebuild; the GLB export still repairs it for the export only.

## 2026-11-26 — Arivus: the neck is rebuilt, the cut rim is closed, the skinning is fixed (D79)

**The ask.** *"What's with the neck of the Aivus head mod. Check renders"*, then *"Fix everything"*.
The tracked sheet shows the neck as a hard angular line across the collarbones with a short
throat — the "collar" in those panels is mostly the edge of a truncated neck, shaded as skin.

**What the renders were hiding.** Three things, each reproduced by a measurement before it was
touched:

1. **D72 had squashed the neck.** `extract_arivus_part` applied `z -= 6·ss((166−z)/6.6)` and
   `z += 4·ss((168−z)/8)` with `z` re-evaluated after the first move, so the net displacement ran
   −2.99 cm at z 157 to −4.26 cm at z 165 and back to 0 at 173. A smoothstep became a shear, and
   ~10 cm of neck was compressed into half of it.
2. **The cut is a V, and the collar only reaches the front of it.** The ped's neck ends at z 159.4
   across the throat and z 164.9 at the back; the suit's collar rim tops out at z 159.8–160.5. From
   behind, the back of the V stood above the collar and the opening looked into the neck — the
   visible band is the throat's own **far wall**, i.e. back-facing interior geometry. Rendering
   back-facing head triangles in magenta and everything else normally put the whole band in magenta,
   which is how that was settled without guessing.
3. **The head weighed the wrong bones.** `bone_offset=1` with a `SkinBones` section that lists
   exactly `[Spine2, Neck, Head]` (40, 41, 42; root 37) left **4,595 of 4,596** vertices carrying
   `BLENDINDICES 3`, one past the end of a three-entry palette. Bind-pose renders cannot see this,
   which is why it survived four rebuilds; D73 found it from the GLB side and left it open.

**What was done.** `bone_offset=0`. `push_neck_rim` drops the cut rim to z 159.0, full weight from
60° either side of the back, fading to nothing at the throat, so the V ends under the collar and the
throat keeps its length; the boundary loop that also climbs the back of the head to z 186 is split
off first, so only the neck ring moves. `extend_neck_into_collar` welds the extracted part (it is
triangle soup, so the rim is not an open edge until `deduplicate_mesh` has run), takes the connected
boundary loop owning the neck's lowest vertex, and stitches a skirt to z 148.0 tucked to **0.35** of
each rim vertex's radius about the ped's neck axis `(0, 1)` — inward, because the suit closes around
the neck below the collar and an outward skirt pushes through it (a sweep of widening skirts peaked
at 85% of columns enclosed, no matter the taper).

**Evidence.** Ray-parity against `g_body` (odd crossings along ±x and ±y = enclosed): **23 of 23**
skirt vertices inside on all three shipped models. All four camera views rendered clean, including
the back that previously showed the band. The throat's front reaches z 166 again. `runtime_verified`
stays false and the pack is still unseen in game. `tests/test_arivus_neck_fit.py` was rewritten to
measure these four properties on the shipped models; **8 of its 12 tests fail on the D72 bytes**, so
the regression is now pinned by the thing that regressed rather than by vertex counts.
`arivus_over_hoxton_sheet.png` re-rendered with `--unified`, and `Arivus_Head_over_Old_Hoxton_GLB.zip`
rebuilt from the new source — its skin is 3 joints with no repair warning, so
`tests/test_arivus_glb_pack.py` now asserts 3 (it asserted 4, which encoded the bug).
Pack `c1630f56289b`, 8,543,738 B; GLB pack `534075b32a28`, 3,442,128 B.

## 2026-11-26 — Arivus rebuilt with the retouched atlas

**The ask.** *"I want you to rebuild Arivus with references/old_hoxton_head_df(1).dds."* The file is a
retouch of the supplied diffuse: the same single-level 2048² BC3 layout and the same alpha cutout
(upper half ≥ 18, hair {0, 24}), with ~118 k repainted pixels — softer, lighter brows in place of the
thick angled ones, one catchlight on the iris instead of the two highlights and stray tan wedge that
sat on it, and small skin adjustments along the brow, lid, nose and lip rows of the head cell. The
outside the head cell only 100 texels moved, all on two cell seams (column 1024 rows 860–943, and
rows 1024–1027 columns 888–891) — block-edge leftovers of the editor's re-encode, shipped as supplied.

**The rebuild.** `ARIVUS_DIFFUSE` in `tools/build_joy_head_mods.py` now reads the retouch, and
`status.py`'s INPUTS names it, so a recovered clone fetches the input the builder wants. The builder
still ships the supplied base-level BC3 blocks byte for byte and regenerates the cutout mips and the
HUD icon from them: `Arivus_over_Hoxton.zip` is `d5f569610d2c`, 8,546,107 B (was `c1630f56289b`,
8,543,738 B). `make heads` reproduced the other eleven head packs byte-identical to their tracked
bytes, so the change is Arivus alone; the GLB interchange export rebuilt from the new source pack is
`7986f8eaef7f`, 3,443,523 B. The suite passes (1023 passed, 14 skipped) and
`tests/test_arivus_diffuse.py` now pins the retouch's base blocks inside the pack. The offline sheet
and the dist overview re-rendered with `--unified`; every other sheet came back byte-identical. The
first edit stayed in git and on disk as `references/old_hoxton_head_df.dds` until 2026-11-26, when it
left the tree and stayed in git only (the entry below).
`runtime_verified` stays false — how the retouch reads under the game's lighting remains a check
waiting for a person with the game.

## 2026-11-26 — `references/` grouped into six folders, four files gone

**The ask.** *"Analyse `/references` — what can be deleted safely? How can they be grouped in
folders?"* The audit that answers it is `docs/audits/2026-11-26-references-inventory.md`; this entry
is the change it proposed, executed. Paths in the entries above this one are as they were written.

**Grouped.** 63 tracked files became 59, in `characters/` (4), `templates/` (6), `textures/` (3),
`honoka/` (31, the old `Honoka/`), `voice/` (7) and `sheets/` (7). Grouped by what reads them, so the
folder a file is in says which builder wants it. `references/README.md` now names every one of them —
it named 22 of 63 before, which is why `2b.rar` (a build input) and `Hoxier Hoxton V2.zip` (a
curiosity) read the same.

**Removed** (in git history, nothing read them): `Honoka/location`, a `Location$` shell artifact;
`Hila regular_vox - regular_vox.csv`, content-identical to `voice_lines_vox/hila_regular_vox.csv`
(885 ids in both); `old_hoxton_head_df.dds`, the first Arivus atlas edit, superseded by `(1).dds`;
`Honoka/Tex_07(L_7) 2.dds`, the retired `Honoko4` suit diffuse (D44), which leaves `status.INPUTS`.
Kept deliberately: `Hoxier Hoxton V2.zip` (reference-only, but the evidence for the icon DDS format),
the fifteen unused `L_*.dds` (the tracked contact sheet, its renderer and its test all glob them) and
`Syndey Voicelines.pdf` (a print, but a VO mod may need the printed table).

**Rebuilt, five packs.** They embed `references/` paths of their own, so their `BUILD_INFO.json` or
`README.txt` changed with the layout: `OfficeSuite` is `1b34bbea1732`, 5,768,993 B; `OfficeSuite_Head`
`0e27343de92c`, 10,386,984 B; `Miranda_Lawson_VO_over_Hila_Stream` `fbcd89cfe600`, 14,405,868 B;
`Geralt_VO_over_Rust_Stream` `ce6ba0246d80`, 12,825,557 B; `Arivus_VO_over_Hoxton_Stream`
`5ef59bf31f29`, 9,699,268 B. Every other pack is byte-identical: only those five name a source path,
and `OfficeSuite_Miranda_Romance_over_Hila` came back `tracked` when its target re-ran. `fresh.py
check` then rebuilt all 13 from a copy of the new tree: **13 of 13 same**.

**Also.** `status.INPUTS` dropped the removed diffuse and gained the six `voice/` archives the stream
targets read, so `ready` is now honest for them; the suit-unit search in `build_joy_head_mods.py`
walks `references/` recursively instead of one level; `references/README.md` documents the sheets and
voice packs it had never named. The suite is 1060 passed, 13 skipped (2 `test_repo_weight` tests read
HEAD and pass once this lands); `pack_checksum.py` 13 match; `check_links.py` 433/0; `um publish
check .` PASS, 0 warnings.
