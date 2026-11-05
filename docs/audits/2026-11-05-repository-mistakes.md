# Repository mistakes — a sweep, 2026-11-05

**Scope:** the whole tree, not one game: the `um` CLI, `tools/`, `tests/`, the knowledge base, the docs,
`.gitignore` and CI. The GMod reader audit of the same day
([2026-11-05-gmod-tools-second-pass.md](2026-11-05-gmod-tools-second-pass.md)) covered `tools/pd2-las/`.

**Method:** the gates first (`pytest`, `um publish check .`, `um kb check --index`, `pyflakes`), then
mechanical sweeps — every relative Markdown link, every `src=`/`srcset=`/`href=` target, every
`path/like/this.py` in prose, every duplicate blob by sha256, every dodgy AST shape (bare except,
`except: pass`, `== None`, mutable default) — then reading each hit to separate a mistake from a
deliberate choice.

## Fixed

1. **`um publish check` warned about its own documentation.** The "absolute user path" rule matched
   `C:\Users\<user>\` and the literal fragment `C:\Users\` inside the scrubbing guide, producing the two
   warnings this repository had carried for weeks. `um kb check` already skipped `<...>` placeholders; the
   two checks disagreed. Both now share `publish.user_path()`, which skips `<...>`, `%VAR%`, `$VAR` and
   `${VAR}`, and the warning names the matched path. `um publish check .` is now **0 failures, 0 warnings**. New test: `test_publish_check_ignores_path_placeholders`.
2. **`um scan` could not name PAYDAY 2.** `knowledge/games/payday-2/las-armor-skin-outfit.md` declares
   `engine: diesel`, which was not one of `um scan`'s keys — so `um kb check --index` warned on the
   repository's own flagship port, and a PAYDAY 2 install fingerprinted as `native`. Added the `diesel`
   engine (exe `payday2_win32_release.exe` at 100, the `assets/*/*.bundle` tree at 80 for a copy without
   the game binary), the BeardLib loader entry (`mods/beardlib/*`, PAYDAY-only, so it cannot mislabel
   another game) and `skills/mod-any-game/references/engines/diesel.md`, wired into the SKILL.md index.
   `um kb check --index` is now clean (246 notes, no warnings). Two tests.
3. **Nothing verified that `um scan`'s playbook paths exist.** `ENGINES` prints "read `<x>.md`" for 34
   engines; a renamed playbook sends an agent to a file that isn't there and no gate noticed (the
   knowledge base check only validates note front matter). New test: `test_every_engine_playbook_exists`.
4. **Four dangling links in docs.** `docs/audits/2026-10-18-old-model-retired-las-restart.md` linked two
   audits that were never committed to this repository (not in `git log --all` either); the text now names
   them instead of linking. `knowledge/games/payday-2/las-moog-outfit-porting.md` linked two notes that
   were never written; it now links the LAS note that exists and says plainly that the two companions are
   unwritten. `um kb check --index` no longer warns.
5. **~25 lint findings sat in the tree** because no gate ever ran a linter: unused imports and dead locals
   in `um/sprite.py`, `um/video.py`, `tools/pd2-port/{dmodel,build_las_pack,check_all,extract_las_rig,
   preview_check,check_guide_compliance*}.py` and four test files, plus `f"…"` strings with no
   placeholders. Cleared (`pyflakes` is clean over `um tools tests`) and **CI now runs it**, so they
   cannot come back.
6. **`references/Geralt.7z` was a byte-identical duplicate of `models/Geralt.7z`** — 14 MB tracked twice,
   with `tools/build_joy_head_mods.py` reading the `models/` copy while `references/README.md` claimed the
   archive was in `references/`. Deleted the `references/` copy, documented the archive in
   `models/README.md` (where the code and the other ported sources live) and left a pointer in
   `references/README.md`.
7. **`.gitignore` did not match what is tracked.** `dist/Geralt_over_Rust.zip` is tracked but was not in
   the un-ignore list, so restoring it after a checkout would silently skip it; the comment claimed only
   "the LAS and Joy packs" are tracked when twelve are. Both corrected.

## Found, deliberately left

- **~15 MB is tracked twice more:** `build/pd2-las/{Miranda_LAS,Miranda_Busty_LAS}.zip` and their
  `.sha256` are byte-identical to the `dist/` copies. CI builds the pack and checks
  `build/pd2-las/Miranda_LAS.zip.sha256` to prove the build is reproducible, which is why the checksum is
  worth tracking — the zips are not. Untracking them is a one-line change plus a CI edit, but it changes
  how the reproducibility gate is phrased, so it is the user's call.
- **The repository is 220 MB of tracked bytes**, about 100 MB of it reference archives (`references/`,
  `models/`) and built packs (`dist/`). That is a deliberate decision (the packs are the deliverables, the
  archives are the only copy of the source models), but it is permanent in history and will keep every
  clone at that size.
- **Three copies of `skills/`** (`skills/`, `.agents/skills/`, `.claude/skills/`, 34 files each) exist
  because the harnesses look in different places. `test_skill_copies_match` enforces equality; the cost is
  review noise, not drift.
- **`um publish check` skips game-file matching below 64 bytes** (`if sz < 64: continue`). It keeps the
  check from flagging empty files and licence stubs; a verbatim-copied 40-byte game file also gets through.
  Documented behaviour, worth knowing when reading a clean result.
- **46 tests skip on this machine:** three need `ffmpeg` (CI installs it), the rest need the deleted Skyrim
  archives (`1.zip`–`5.zip`, removed 2026-11-04 with the cancelled port) or Git Bash. Expected.
- **Prose references that are not broken links** (checked, then dismissed): `docs/CONTRACT.md`,
  `docs/HANDOFF.md`, `docs/MIGRATION_STATUS.md` and friends in knowledge notes point at the *user's* mod
  project layouts, and `victim["Get Damage"](...)` / `(*(void***)o)` inside code spans are code, not
  Markdown links. A naive link checker reports six; four were real.

## Gates after the sweep

```
pytest tests -q                     → 500 passed, 46 skipped, 1 warning
um kb check --index                 → PASS, 246 notes, 0 warnings
um publish check .                  → PASS, 815 files, 0 failures, 0 warnings
python -m pyflakes um tools tests   → clean
```
