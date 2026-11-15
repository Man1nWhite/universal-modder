# In-game captures — Honoka_LAS and Christie_LAS (2026-11-15)

Six user-supplied PNGs, byte-identical to the uploads, archived without resizing, recompression
or annotation. All six show the **outfit menu (armor-skin preview)** of PAYDAY 2 with the LAS
outfits equipped — not a heist. They are the user's, captured on 2026-11-15.

| # | Upload | Archived file | Pack (as reported by the user) | View |
| --- | --- | --- | --- | --- |
| 1 | `image-6.png` | [`honoka_menu_front.png`](honoka_menu_front.png) | `Honoka_LAS` — the pack as tracked in `dist/` (ce1d1c0, sliver-fixed build) | front |
| 2 | `image-7.png` | [`honoka_menu_side.png`](honoka_menu_side.png) | same | side (profile) |
| 3 | `image-8.png` | [`christie_slim_menu_front_white-gloves.png`](christie_slim_menu_front_white-gloves.png) | `Christie_LAS_Slim`, with the white LAS gloves equipped | front |
| 4 | `image-9.png` | [`christie_slim_menu_side_white-gloves.png`](christie_slim_menu_side_white-gloves.png) | `Christie_LAS_Slim`, with the white LAS gloves equipped | side (profile) |
| 5 | `image-10.png` | [`christie_menu_front.png`](christie_menu_front.png) | `Christie_LAS` (full, with hands) | front |
| 6 | `image-11.png` | [`christie_menu_side.png`](christie_menu_side.png) | `Christie_LAS` (full, with hands) | side (profile) |

## What these show

- **Honoka (1–2):** the purple "Secret Report" blazer, black skirt, white LAS gloves with the
  red wrist stripe — the tracked pack loads and renders in the menu preview, clean silhouette,
  no hairline streaks from the dropped connector triangles (`ce1d1c0`). Head, hair and face are
  the heister's own; the pack is body-only (`replace_body`).
- **Christie, Slim + white LAS gloves (3–4):** the white blazer and trousers render in the menu
  preview; the spawned white LAS gloves cover the wrist cut, red wrist stripe visible.
- **Christie, full (5–6):** the same white suit with Christie's own hands — pale skin with dark
  fingertips — visible in the preview.

## What these do not show

- No heist / no third-person in-world view, no first-person viewmodel, no movement, no animations,
  no rifle or elbow stress test. The open items in
  [`docs/pd2-las/in-game-checklist.md`](../../pd2-las/in-game-checklist.md) (inner elbow under a rifle,
  sleeve/cuff/glove stack across all poses, contour outline, crash logs) are untouched by these frames.
- The installed Christie builds were **identified by the user**, not hash-measured from the captured
  bytes; the two pairs differ by hand appearance only (gloved vs Christie's own hands), which matches
  the Slim-plus-gloves and the full pack as reported. Honoka was confirmed to be the currently tracked
  pack. Nothing here says anything about the head model, the spawned gloves' own bytes, or any other
  installed mod.
- `runtime_verified` in each pack's `BUILD_INFO.json` is a constant its builder writes and stays
  `false`; it is not a runtime record. What ran in game, per date and per user report, is the table in
  [`docs/pd2-las/HANDOFF.md`](../../pd2-las/HANDOFF.md).

Exact dimensions, sizes and SHA-256 digests of every file: [`manifest.json`](manifest.json).
