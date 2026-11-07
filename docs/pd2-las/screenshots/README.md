# Christie_LAS_Slim — replacement in-game screenshots (2026-11-07)

**15 user-supplied PNGs replace the previous 11 screenshots.** Each file is
byte-identical to its upload, without resizing, recompression or annotation.
The filenames follow upload order. The old set is no longer in this directory;
it remains in Git history. Do not reuse the old review’s crop coordinates.

- `01`–`08`: lobby / idle, camera around the character.
- `09`–`15`: menu / rifle pose, camera around the character.
- **Installed build hash: not supplied.** Do not attribute these captures to
  a specific repository ZIP merely because it is currently in `dist/`.

Current analysis:
[replacement screenshot review](../../audits/2026-11-07-christie-slim-screenshot-review.md).
Upload-to-archive mapping, exact dimensions, sizes and full SHA-256 digests:
[`manifest.json`](manifest.json).

## Index

Left/right labels describe the direction the face points in the image, not
the character’s anatomical side. Each PNG has its own coordinate space.

| Shot | Original upload | Archived screenshot | View | Pixels |
|---|---|---|---|---|
| 01 | `image-1.png` | [`christie_slim_01_lobby_front.png`](christie_slim_01_lobby_front.png) | Lobby / idle, front | 506 × 980 |
| 02 | `image-2.png` | [`christie_slim_02_lobby_right-three-quarter.png`](christie_slim_02_lobby_right-three-quarter.png) | Lobby / idle, front three-quarter, face toward image-right | 495 × 1000 |
| 03 | `image-3.png` | [`christie_slim_03_lobby_right-profile.png`](christie_slim_03_lobby_right-profile.png) | Lobby / idle, profile, face toward image-right | 528 × 1012 |
| 04 | `image-4.png` | [`christie_slim_04_lobby_back-three-quarter-right.png`](christie_slim_04_lobby_back-three-quarter-right.png) | Lobby / idle, back three-quarter, image-right-facing side | 540 × 1020 |
| 05 | `image-5.png` | [`christie_slim_05_lobby_back.png`](christie_slim_05_lobby_back.png) | Lobby / idle, back | 594 × 1010 |
| 06 | `image-6.png` | [`christie_slim_06_lobby_back-three-quarter-left.png`](christie_slim_06_lobby_back-three-quarter-left.png) | Lobby / idle, back three-quarter, image-left-facing side | 560 × 1055 |
| 07 | `image-7.png` | [`christie_slim_07_lobby_left-profile.png`](christie_slim_07_lobby_left-profile.png) | Lobby / idle, profile, face toward image-left | 502 × 1018 |
| 08 | `image-8.png` | [`christie_slim_08_lobby_left-three-quarter.png`](christie_slim_08_lobby_left-three-quarter.png) | Lobby / idle, front three-quarter, face toward image-left | 519 × 1017 |
| 09 | `image-9.png` | [`christie_slim_09_menu_front-three-quarter-right-rifle.png`](christie_slim_09_menu_front-three-quarter-right-rifle.png) | Menu / rifle, front three-quarter, face toward image-right | 585 × 911 |
| 10 | `image-10.png` | [`christie_slim_10_menu_right-profile-rifle.png`](christie_slim_10_menu_right-profile-rifle.png) | Menu / rifle, profile, face toward image-right | 557 × 916 |
| 11 | `image-11.png` | [`christie_slim_11_menu_back-three-quarter-right-rifle.png`](christie_slim_11_menu_back-three-quarter-right-rifle.png) | Menu / rifle, back three-quarter, image-right-facing side | 541 × 890 |
| 12 | `image-12.png` | [`christie_slim_12_menu_back-rifle.png`](christie_slim_12_menu_back-rifle.png) | Menu / rifle, back | 574 × 910 |
| 13 | `image-13.png` | [`christie_slim_13_menu_left-profile-rifle.png`](christie_slim_13_menu_left-profile-rifle.png) | Menu / rifle, profile, face toward image-left | 536 × 881 |
| 14 | `image-14.png` | [`christie_slim_14_menu_front-three-quarter-left-rifle.png`](christie_slim_14_menu_front-three-quarter-left-rifle.png) | Menu / rifle, front three-quarter, face toward image-left | 531 × 902 |
| 15 | `image-15.png` | [`christie_slim_15_menu_front-rifle.png`](christie_slim_15_menu_front-rifle.png) | Menu / rifle, front | 536 × 899 |

## Reading the evidence

- Judge material/shading appearance at **native 1:1 pixels**. PNG storage is
  lossless, but the original capture/resampling history is unknown. Do not
  infer faceted geometry from interpolated enlargement.
- Crop boxes in the review are `(left, top, right, bottom)`, upper-left origin,
  with right/bottom exclusive; they refer to the original PNG pixels.
- Cursors, UI text and the rifle are not outfit defects.
- The LAS pack is **body-only**. A separate head and spawned gloves contribute
  to the visible result. That is a reason to isolate ownership, not to dismiss
  neck/cuff artifacts without a comparison.
- Static lobby/menu captures do not verify first-person arms, feet, gameplay
  animation, or the exact installed pack’s stability.
