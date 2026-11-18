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
