# Голос Лоусон.7z — Miranda Lawson Voice Archive (checked on main)

> **File:** `references/Голос Лоусон.7z` (15.4 MB, added via upload dda3846 on `origin/main` 2026-11-23) — now extracted here for Hila `rb21` reuse.
> **Content:** 866 × `.ogg` (OggS Vorbis, avg 24.7 KB, 20.4 MB total) — 214 unique conversation stems (`<package>_<scene>_[a-h]_S_INT.<line>.ogg`)
> **Language:** English VO (Yvonne Strahovski) — filename prefix `Голос` = Russian "Voice" but audio is EN; ready for Payday `wwise_ima_adpcm` → `regular_vox/<id>.stream`.

## Where it came from vs free alternatives

This archive matches the **Evil Banana pattern** (LE PCC/AFC → AFC → ogg via LEX/Sound Explorer) but without paywall — same stems as `Mass Effect Legion/EDI/Kasumi Voice Lines.zip` on Patreon, just for Miranda. Compared to XCOM packs (Spicy Meat 2593914005 = 370 lines) this has **866 lines**, including deep DLC and Normandy banter.

## Prefix → Mission map (from ME3/LE file layout)

| Prefix | Count | What it is (for Hila mapping) |
|---|---|---|
| `norvx` | 218 | **Normandy** — Miranda's cabin talks, romance/catch-up, loyalty confrontations (`relationship_00..04`, `loyalty_01/02`, `starter`, `culmination`). Best for Hila `Inspire`/`Revive`/"Follow me" |
| `procer` | 134 | **Prologue Cerberus** — Lazarus, Vixen briefings, shuttle. Good for `Mask up`/`Let's go` |
| `twrvxl` | 100 | **Miranda's sister Oriana arc** (`twrvxl_aboutaboy`, `uptospeed`, `oldfriend`, `main_contact`) — emotional, pager-response friendly |
| `endgm2` | 81 | **ME2 Suicide Mission** — longwalk, team, huddle, warnings. `Cops arriving`/`Victory` |
| `profre` | 38 | **Freedom's Progress / Veetor** |
| `endgm1` | 32 | **ME1/2 endgame huddle/warship** |
| `cspcr2` | 28 | **Collector Ship / Cerberus lab** |
| `horcr1` | 27 | **Horizon** (first meeting) |
| `jnkkga` | 25 | **Jack's loyalty?** actually Miranda vs Jack fight |
| `twrmwa` | 22 | **Miranda vs Wrex?** — use for `Taxman intimidate` |
| `pronor` | 17 | **Normandy SR2 intro** |
| `prscva` | 15 | **CVA?** |
| `n7` | 13 | **N7 missions** |
| `omggra`/`omgpra` | 12+12 | **Omega Gratitude?** Aria |
| `bchlml` | 10 | **Miranda's father arc** (Beach, Village, Epilogue, FatherFinal) |
| `gthgtl` | 10 | **Geth?** |
| `omghub` | 10 | **Omega Hub** |
| `cithub` | 4 | **Citadel Hub — direct Miranda talks** (`tp_miranda`) — cleanest for pager / "Nothing happening here, control" |
| ... | — | See `Голос_Лоусон_manifest.csv` for full 866 rows with `prefix` + `package_hint` |

Top stems (most lines, best for variation):
- `norvx_relationship_03_h_S_INT` 42, `norvx_starter_h_S_INT` 40, `norvx_relationship_00_h_S_INT` 30
- `procer_vixen_briefing_d_S_INT` 24, `norvx_loyalty_01_h_S_INT` 23

## On-disk layout after extraction

```
voice_lines_vox/miranda_lawson/Голос_Лоусон/Голос Лоусон/*.ogg   # original nested 7z path (866 oggs)
voice_lines_vox/miranda_lawson/Голос_Лоусон_flat/*.ogg          # flattened copy (866 oggs, same names)
voice_lines_vox/miranda_lawson/Голос_Лоусон_manifest.csv         # filename | stem | prefix | package_hint | category_guess | size_bytes
```

`git` on `origin/main` now has `references/Голос Лоусон.7z` (dda3846); this branch `arena/da8ae3ab-universal-modder` has it pulled via `git checkout origin/main -- references/Голос Лоусон.7z`.

## How to use for Hila (rb21) — regular_vox bank

1. Pick lines from manifest → map to `hila_regular_vox.csv` IDs (887 IDs, e.g. `28880249 "Uh… I thought there was something going on…"` = pager; `712675 "(pained) You, hey!"` = downed). Replace Miranda ogg → Wwise `wwise_ima_adpcm -e` → `soundbanks/streamed/regular_vox/<ID>.stream` with switch `robber=rb21`.
2. For pager diversity, use `cithub_tp_miranda` (only 2 lines, clean control-talk) + `twrvxl_*` (miranda-sister) vs `norvx_relationship_*` for soft lines.
3. For combat, use `endgm2_longwalk` / `cspcr2_*` / `horcr1_*` (louder, directive).

> All voice lines © BioWare/EA — use as `mod_overrides` only, don't redistribute standalone.

## Comparison to previous docs in this folder

- `miranda_text_me2_me3.md` — 119 lines text transcript (Fandom + IMDB quotes) — now audio covers 7× more.
- `audio_next.md` / `extraction_community.md` — LEX Sound Explorer / Dialogue Dumper workflow (how this 7z was made).
- `shared_audio_posts.md` / `free_evil_banana_alternatives.md` — Steam 2593914005 (Spicy Meat 370) + Patreon Evil Banana paid series — this file is the free 866-line equivalent.
- `hila_regular_vox.csv/.md` — 887 Hila IDs this audio plugs into.

