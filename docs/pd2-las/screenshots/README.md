# Christie_LAS_Slim — replacement in-game screenshots (2026-11-10)

**8 user-supplied PNGs replace the previous 15 screenshots.** Each file is
byte-identical to its upload, without resizing, recompression or annotation.
The filenames follow upload order. The old set is no longer in this directory;
it remains in Git history. Do not reuse older reviews' crop coordinates.

- `01`–`07`: lobby / idle, camera around the character.
- `08`: menu / rifle pose.
- The batch has **one** menu/rifle frame, not seven. The six rifle angles from
  the previous batch (former `09`–`15`) are not in the current archive, so the
  rifle pose is documented from a single viewpoint only.
- **Installed build: `Christie_LAS_Slim`**, recorded as SHA-256
  `7a4d010c…90a3e6f` (4,393,967 B) on the user's report. That is the pack hash,
  not a hash measured from the captured bytes, and it says nothing about the
  head model or the spawned gloves visible in the frames.

Current analysis:
[replacement screenshot review](../../audits/2026-11-10-christie-slim-screenshot-review.md).
The 2026-11-07 review and the earlier 11-frame review describe replaced images
and are historical. Upload-to-archive mapping, exact dimensions, sizes and full
SHA-256 digests: [`manifest.json`](manifest.json).

## Index

Left/right labels describe the direction the face points in the image, not
the character’s anatomical side. Each PNG has its own coordinate space.

| Shot | Original upload | Archived screenshot | View | Pixels |
|---|---|---|---|---|
| 01 | `image-2.png` | [`christie_slim_01_lobby_front.png`](christie_slim_01_lobby_front.png) | Lobby / idle, front | 524 × 1008 |
| 02 | `image-3.png` | [`christie_slim_02_lobby_right-three-quarter.png`](christie_slim_02_lobby_right-three-quarter.png) | Lobby / idle, front three-quarter, face toward image-right | 539 × 1013 |
| 03 | `image-4.png` | [`christie_slim_03_lobby_right-profile.png`](christie_slim_03_lobby_right-profile.png) | Lobby / idle, profile, face toward image-right | 525 × 1021 |
| 04 | `image-5.png` | [`christie_slim_04_lobby_back-three-quarter-right.png`](christie_slim_04_lobby_back-three-quarter-right.png) | Lobby / idle, back three-quarter, image-right-facing side | 546 × 1021 |
| 05 | `image-6.png` | [`christie_slim_05_lobby_back.png`](christie_slim_05_lobby_back.png) | Lobby / idle, back | 544 × 1040 |
| 06 | `image-7.png` | [`christie_slim_06_lobby_back-three-quarter-left.png`](christie_slim_06_lobby_back-three-quarter-left.png) | Lobby / idle, back three-quarter, image-left-facing side | 541 × 1040 |
| 07 | `image-8.png` | [`christie_slim_07_lobby_left-profile.png`](christie_slim_07_lobby_left-profile.png) | Lobby / idle, profile, face toward image-left | 508 × 1066 |
| 08 | `image-9.png` | [`christie_slim_08_menu_front-three-quarter-right-rifle.png`](christie_slim_08_menu_front-three-quarter-right-rifle.png) | Menu / rifle, front three-quarter, face toward image-right | 555 × 1021 |

The in-game frames are uploads `image-2.png` … `image-9.png`. The batch also
carried an `image-1.png` that is a Blender bone overlay close-up of the elbow,
not an in-game screenshot; it is not archived here, so this directory holds only
what the game rendered.

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
