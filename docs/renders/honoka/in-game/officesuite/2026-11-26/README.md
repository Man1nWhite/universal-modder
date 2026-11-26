# In-game captures — `OfficeSuite` wrists (2026-11-26)

Four user-supplied PNGs of `OfficeSuite` wearing white buttoned dress gloves in PAYDAY 2, archived
byte-identically to the uploads (no resizing, recompression or annotation). They are the evidence
for [D75](../../../../../pd2-las/DECISIONS.md): the outfit's own wrist standing through the gloves'
cuffs in first person, while the menu's third-person turntable looks nearly clean.

| # | Upload | Archived file | View | Shows |
| --- | --- | --- | --- | --- |
| 1 | `image-1.png` | [`officesuite_fps_wrist_01.png`](officesuite_fps_wrist_01.png) | first person, left wrist | a sliver of skin over the glove's cuff |
| 2 | `image-2.png` | [`officesuite_menu_02_threequarter.png`](officesuite_menu_02_threequarter.png) | menu, three-quarter | the cuff clean at rest |
| 3 | `image-3.png` | [`officesuite_menu_03_side.png`](officesuite_menu_03_side.png) | menu, side | the bracelet above the cuff, unchanged |
| 4 | `image-4.png` | [`officesuite_fps_wrist_04.png`](officesuite_fps_wrist_04.png) | first person, right wrist | the same sliver, in the weapon pose |

## What these show

- In first person the outfit's wrist skin reaches past the glove's cuff in the wrist's dorsal-ulnar
  sector — the side of the button slit — while the menu poses, which put no bend or twist on the
  wrist, show the cuff closed.
- The pack ships no hands (D58/D59/D70): the gloves in these frames are the player's, and the wrist
  cut is at the crease under them.
- The gold bracelet sits above the cuff in every frame and is not part of the problem.

## What these do not show

- No heist movement, no third-person weapon pose, no other glove, no other heister.
- The installed bytes were identified by the user, not hash-measured from the captures; nothing here
  says anything about any other installed mod.
- These are the **D70** build (the cut reverted to the crease). The fix in D75 came after them; the
  offline comparison of the same junction is in
  [`../../model/wrist/`](../../../model/wrist/README.md).

Exact dimensions, sizes and SHA-256 digests of every file: [`manifest.json`](manifest.json).
