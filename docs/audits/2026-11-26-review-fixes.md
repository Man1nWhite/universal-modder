# Review sweep — bugs, gates and the first five minutes of a clone, 2026-11-26

**Scope:** the whole tree, from the outside in: a fresh clone with the dependencies from
`pyproject.toml` only, the `um` CLI's own commands, the two CI workflows, the suite, and every
relative Markdown link. Not a pack audit: nothing under `tools/pd2-las/` that builds a ZIP changed,
and no tracked ZIP was rebuilt or touched.

**Method:** install what `pyproject.toml` declares, then `pytest tests`; a coverage run
(`pytest --cov=um --cov=tools`); `pyflakes`; `um kb check --index`; `um publish check .`; a link
scan of all 430 Markdown files; `make -sC tools/pd2-las status`; and reading the modules that
coverage said had no tests (`um/sprite.py` 58% with no test file, `um/render3d.py` 47% with none,
`um/video.py` 19%).

## Fixed — the CLI

1. **`um sprite info` and `um sprite cutout` died on any image under 4 px in either dimension.**
   `border_color()` sampled a fixed 4x4 corner, so `px[w - k, y]` went out of range: a 64×2 hair
   strip, a 3×64 emblem, a 1×1 swatch. `k` is now clamped to the image (and a zero-sized canvas
   answers `(0, 0, 0)`). New `tests/test_sprite.py` — the module had **no test file at all** —
   covers the thin shapes, `cutout`, `fit`, `pixelate`, `sheet`/`slice_sheet`, `snap_palette`,
   `team_mask` and the card renderers' font files.
2. **`um backup create --name ../../escape` wrote the snapshot outside `~/.universal-modder/backups/`.**
   `_root()` joined the name to the data directory and only rejected `""`, `"."` and `".."`, so a
   relative traversal escaped where `list`/`restore` would never look for it — and `restore` reuses
   the name for the undo snapshot it takes first. `_validate_name()` now accepts one path component
   (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`, no Windows device names), a folder-derived default name is
   sanitised instead of rejected, and the `-pre-restore` suffix cannot overflow the 64-character
   limit. `tests/test_backup_name_safety.py` pins all of it.
3. **`um win ps`/`pid_of` pasted user-supplied names into a PowerShell single-quoted string.**
   PowerShell ends such a string at the first `'`, so `Assassin's Creed` was a parse error and
   anything after the quote was parsed as script. Values now go through `ps_literal()`
   (`'` doubled). `um win launch --steam` no longer routes the URL through `cmd /c start` (which
   re-parses `&`, `|`, `%VAR%`): native Windows hands it to ShellExecute, WSL keeps `cmd start`,
   and arguments carrying cmd metacharacters are refused with the reason. `tests/test_win_quoting.py`.
4. **`um/common.to_win()`'s three-way one-line conditional** had a branch that could never run and
   silently turned the drive-relative `C:Games` into `C:\Games`. Rewritten as the two assignments it
   was computing; behaviour for WSL and Windows paths is unchanged.
5. **`um/scan.save_hints()`'s `{docs, prof and str(...)} - {None}`** never dropped the empty string
   (`prof and ...` yields `""`, not `None`), so `Path("")` probed the current directory. Guarded.
6. **`um/kb sync()` cached a truncated GitHub answer as the whole knowledge base** and stamped it
   fresh for 24 hours: `tree["truncated"]` was never read, so `um kb search` could quietly answer
   from part of the notes. It now fails loudly (and `resolve_root` falls back to the cache it
   already has), a per-request retry with backoff covers a dropped connection among 250 requests,
   and an empty or non-JSON answer is an error rather than an empty cache. `tests/test_kb_sync.py`.
7. **`um publish check .` printed 34 warnings on a clean tree** — 32 large archives that
   `references/README.md` names in full, and two `/home/<user>/…` fixtures in test files that exist
   to exercise the rule being warned about. An archive named in a README/CREDITS/Markdown file is
   now provenance-recorded, and the user-path rule skips test files. The tree is back to
   **PASS: 0 failures, 0 warnings**, which is what makes a new warning mean something.
   `tests/test_publish_provenance.py`.

## Fixed — the suite and CI

8. **A fresh clone's suite was red with messages that read like a broken checkout**: four
   `FileNotFoundError: …/2b.model` failures (the gitignored 2B templates) and four `py7zr` errors.
   New `tests/conftest.py` owns the import paths (every test file used to prepend `tools/` and
   `tools/pd2-las/` itself) and tries the documented extraction once; if it cannot, it skips the
   tests that read the templates with `extract_2b.MISSING` — the wording the skip budget already
   knows. `pyproject.toml` now declares what the suite needs:
   `pip install -e '.[dev]'` (pytest, hypothesis, py7zr, pyflakes, pytest-cov, imageio-ffmpeg) and
   `pytest` from the root is the same run as `pytest tests`.
9. **`test.yml` ran both halves of the job on every push**, with no concurrency group, no pip cache
   and no path filter: a docs-only change paid for a 15-minute byte-for-byte rebuild, and a
   superseded push held a runner to the end. It is now two jobs: `test` (all the fast gates, ~3 min,
   with a pip cache and `concurrency: cancel-in-progress`) and `packs` (the rebuild), which runs on
   a push to `main`, a tag, a nightly schedule, a manual run, or a pull request labelled
   `rebuild-packs`. `make -sC tools/pd2-las green` still runs both locally.
10. **Three `um` groups had no tests** (`um/sprite.py`, `um/render3d.py`, `um/video.py` 19%):
    `tests/test_sprite.py`, `tests/test_render3d.py` and `tests/test_video_pure.py` cover what does
    not need Blender or ffmpeg — the anim spec parser, the EDL timing, the ffmpeg filter strings,
    the card renderers, the ffprobe fallback.

## Fixed — documentation and developer experience

11. **Two broken relative links** in the newest capture set
    (`docs/renders/honoka/in-game/officesuite/2026-11-26/README.md`, one `../` short each): the
    evidence for D75 pointed at a file that has never existed. New
    `tools/pd2-port/check_links.py` (code spans and fenced blocks are not links — a note about
    decompiled code legitimately contains `victim["Get Damage"](...)`) runs in the suite, in CI and
    in `green`: **PASS, 431 Markdown files, 0 broken**.
12. **`docs/` had no entry point** across 25 guides, audits and handoffs. `tools/gen_docs_index.py`
    generates `docs/README.md` from each document's own `# ` heading, with a `--check` mode in CI
    (`tests/test_docs_index.py`), the way `knowledge/INDEX.md` has always worked.
13. **The build pipeline had no supported entry point on native Windows** — the Makefile hardcodes
    `.venv/bin/python`, shells out to `bash` and relies on GNU make, while the fork's subject is a
    Windows game. `tools/tasks.py` repeats every Makefile target in Python with no dependencies;
    `tests/test_tasks.py` fails while the two lists differ (including the order of `all`).
14. **README's one-line "MIT licensed"** covered a tree that redistributes third-party game assets.
    `NOTICE.md` separates the MIT grant (code, skills, knowledge, docs) from what stays the
    creators' (archives, packs, captures) and points at the provenance table in
    `references/README.md`. The README also documents the 420 MB clone and the two cheap ways to
    get the code without the packs.
15. **Repository weight had no guard**: `tests/test_repo_weight.py` fails on a new tracked file over
    25 MB (the largest today is 24 MB) and names the two legitimate options — a release asset or
    Git LFS — so the next one is a decision instead of an accident.
16. Skills have one command to keep their three copies in step (`tools/sync_skills.py`, `--check`
    included), and `docs/audits/2026-11-05-repository-mistakes.md` now says in its gates section that
    its numbers are that day's, not today's.

## Left alone, on purpose

- **The 420 MB of history.** Superseded by the release-asset plan: the manifest (`assets.json`),
  `tools/release_assets.py` and the gated runbook in
  [`../pd2-las/RELEASE_ASSETS.md`](../pd2-las/RELEASE_ASSETS.md) are in the tree, and the switch
  waits only on the upload, so `dist/` and `references/` stay tracked until `remote` says PASS.
- **Three copies of `skills/`.** `test_skill_copies_match` keeps them equal and symlinks are
  unreliable on Windows without developer mode. `tools/sync_skills.py` makes the copy one command.
- **Splitting `tests/test_pd2_las.py` (1,750 lines) and `tests/test_um.py` (1,294).** Structural, and
  every one of those tests pins a pack invariant; not a change to make in a review sweep.
- **The `um/scan.py` game tables** (about 500 of its 924 lines are data). Moving them to
  `um/data/*.json` is worth doing when the next engine is added, not before.
- **Actions pinned by major tag, not SHA.** Worth doing with a tool that keeps them current.

## Gates after the sweep

```
make -sC tools/pd2-las green        → all 16 stages passed; 24 of 24 tracked zips are their
                                      tracked bytes after a fresh build (683.6s)
pytest -q tests                     → 1157 passed, 14 skipped   (budget: OK, 0 new skip reasons)
python -m pyflakes um tools tests   → clean
um kb check --index                 → PASS, 247 notes
um publish check .                  → PASS, 1247 files, 0 failures, 0 warnings
python tools/pd2-port/check_links.py → PASS, 433 Markdown files, 0 broken
python tools/gen_docs_index.py --check → PASS, 27 documents
```
