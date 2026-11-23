# In-game captures — `Honoko2` (2026-11-15)

Eight user-supplied PNGs of the `Honoko2` LAS outfit in PAYDAY 2, archived byte-identically to the uploads
(no resizing, recompression or annotation). All eight are the **outfit menu, armor-skin preview**, not a
heist: the character stands on the preview turntable and the capture is cropped to the figure, with the
menu's scroll bars and the Russian menu heading visible at the edges.

- **Pack:** `dist/Honoka/Honoko2.zip` — the DOAXVV "Secret Report" costume built from
  `references/Honoka/Honoka_DOAXVV_Secret_Reportout.dae` by `tools/pd2-las/build_honoko2_dae.py`
  (`make -sC tools/pd2-las honokodae`). The user states these captures are of this pack. The slimmer
  siblings `dist/Honoka/Honoko3.zip` (same outfit, mesh scaled 5% about the rig's bones, D42) and
  `dist/Honoka/Honoko4.zip` / `dist/Honoka/OfficeSuite.zip` (alternate suit colourways, D44–D46, D50) are
  **not** in these frames (`OfficeSuite`'s own menu/lobby captures are archived separately under
  [`../officesuite/2026-11-15/`](../officesuite/2026-11-15/README.md)).
- **Camera/view convention:** the game's preview turntable, seen from the front, three-quarter, side and
  back as the player rotates the character. No fixed camera: the eight frames are the rotations the user
  captured, not eight renders of one camera.
- **Caveats:** the head, hair and face are the menu heister's own (the pack is body-only,
  `LegendaryArmours.honoko2`); the hands in the frames are the vanilla blue heister gloves over the wrist
  cut, with the pack's gold bracelet/watch visible above the left cuff. `runtime_verified` in the pack's
  `BUILD_INFO.json` stays `false` — it is a builder constant, not a record that the pack ran.
  [Seen in game](../../../../pd2-las/HANDOFF.md) is the record of what ran.

| # | Upload | Archived file | View |
| --- | --- | --- | --- |
| 1 | `image-1.png` | [`honoko2_menu_01_front.png`](honoko2_menu_01_front.png) | front |
| 2 | `image-2.png` | [`honoko2_menu_02_threequarter.png`](honoko2_menu_02_threequarter.png) | three-quarter (turned right) |
| 3 | `image-3.png` | [`honoko2_menu_03_side.png`](honoko2_menu_03_side.png) | side (profile) |
| 4 | `image-4.png` | [`honoko2_menu_04_back.png`](honoko2_menu_04_back.png) | back |
| 5 | `image-5.png` | [`honoko2_menu_05_back.png`](honoko2_menu_05_back.png) | back (second angle) |
| 6 | `image-6.png` | [`honoko2_menu_06_back-threequarter.png`](honoko2_menu_06_back-threequarter.png) | back three-quarter |
| 7 | `image-7.png` | [`honoko2_menu_07_side.png`](honoko2_menu_07_side.png) | side (profile, second angle) |
| 8 | `image-8.png` | [`honoko2_menu_08_threequarter.png`](honoko2_menu_08_threequarter.png) | three-quarter (turned left) |

## What these show

- The buttoned purple blazer over the white blouse, the purple skirt with its side slit, the badge and gold
  chain on the lapel, and the gold bracelet on the left wrist — the six-material `.dae` build's garments and
  jewelry render in the menu preview, front, side and back.
- The wrist cut sits under the vanilla heister gloves: no bare hands, no gap at the cuff, and no hairline
  streaks crossing the silhouette (the source's strip-break connector slivers are dropped at build).
- Skirt and legs read as a normal garment from every angle; nothing z-fights or culls in these frames.

## What these do not show

- No heist, no in-world third-person view, no first-person viewmodel, no movement, no animations, no rifle
  or elbow stress test. The open items in
  [`docs/pd2-las/in-game-checklist.md`](../../../../pd2-las/in-game-checklist.md) (inner elbow under a rifle,
  sleeve/cuff/glove stack across all poses, contour outline, crash logs) are untouched by these frames.
- The installed bytes were identified by the user, not hash-measured from the captures; nothing here says
  anything about the spawned gloves' own bytes or about any other installed mod.

Exact dimensions, sizes and SHA-256 digests of every file: [`manifest.json`](manifest.json).
