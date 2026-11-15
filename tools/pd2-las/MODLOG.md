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
