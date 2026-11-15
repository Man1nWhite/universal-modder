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
