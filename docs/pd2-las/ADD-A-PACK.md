# Add or retire a distribution pack

The packs in `dist/` are bytes in git: a `<name>.zip`, a `<name>.zip.sha256` beside it, and a
builder that reproduces them. This is the runbook for the two changes that touch all of that.
`tools/pd2-las/packs.py` is the table every other view is checked against; nothing else needs
to be found by hand.

## Add a pack

1. **Decide the identity.** The name is `<Character>_<what it replaces>_<variant>` and the
   folder is `dist/<group>/` — `Miranda`, `Miranda_L4D2`, `Geralt`,
   `Arivus`. A pack that replaces a whole character or outfit goes to the character's folder;
   an `*_over_<heister>` head replacement goes to `dist/Miranda/` (or its own character's).
2. **Add one row to `tools/pd2-las/packs.py`**: name, group, make target, builder argv, one
   line of `what`. Pack two outputs under one target only if one builder writes both.
3. **Write the builder** under `tools/`, or extend an existing one. It must print nothing that
   is not part of its log, write the zip deterministically (`las_outfit_pack.write_zip`, fixed
   timestamps, the declared code path of `determinism.py`) and let `pack_checksum` write the
   sidecar.
4. **Add the make target** in `tools/pd2-las/Makefile` (one `$(call BUILD,...)` line) and the
   matching entry in `tools/tasks.py`, or the table tests fail. `make -sC tools/pd2-las help`
   must list it.
5. **Build it:** `make -sC tools/pd2-las <target>`. Done means `make -sC tools/pd2-las status`
   reports `"is": "tracked"` for the new pack — the bytes in `dist/` are the bytes in git.
6. **Document it:** the pack's row in `docs/renders/…` if it ships a preview sheet, the decision
   in `docs/pd2-las/DECISIONS.md` (one entry, dated, with the reasoning), and the install
   instructions in `docs/pd2-las/in-game-checklist.md`. Regenerate `docs/README.md`
   (`python tools/gen_docs_index.py`) after adding or renaming a document.
7. **Prove it:** `make -sC tools/pd2-las green` locally, or push and let `test` + `packs` run.
   `packs` rebuilds every tracked zip from scratch and compares it with the sidecar.

## Retire a pack

1. **Delete the row** from `tools/pd2-las/packs.py`, and its make target and `tasks.py` entry.
   `tests/test_one_pack_table.py` lists every view that still names it.
2. **Delete the builder machinery that only wrote it** — the assembly functions, their private
   helpers and the docstrings that describe them. A builder that is left calling
   `build_x(..., [])` to "keep the shared pass" is doing the work and throwing it away; if a
   pass is still needed, the pack that needs it must call it.
3. **`git rm` the zip and its sidecar.** `status.pack_paths()` follows the index, so tests stop
   seeing the pack in the same commit that removes it; `make status` still reports it as
   `missing` until the deletion is committed.
4. **Sweep the references:** `tests/test_pack_paths_resolve.py` fails on any
   `dist/<group>/<name>.zip` left in a script or a live doc; `dist_paths.dist_path()` raises on
   a name with no folder, so a stale name cannot silently create one. Dated records
   (`docs/audits/`, `docs/pd2-las/DECISIONS.md`, `tools/pd2-las/MODLOG.md`, the per-batch
   `docs/renders/**/README.md`) are history and are allowed to keep the old name.
5. **Keep the renders** in `docs/renders/` as provenance; the preview script stops rendering a
   pack that is gone, and the batch README says which build it shows.
6. **Say so** in `docs/pd2-las/DECISIONS.md` (what was retired, why, what replaced it) and
   regenerate the docs index.

## What fails if a step is skipped

| Skipped | Fails |
| --- | --- |
| the `packs.py` row | `tests/test_one_pack_table.py`, `status` (no make target for the name) |
| the Makefile or `tasks.py` entry | `tests/test_one_pack_table.py`, `make help`, `green` |
| a `dist/` path left in a script or doc | `tests/test_pack_paths_resolve.py` |
| the sidecar | `tests/test_dist_checksums.py`, `packs` (fresh compares against it) |
| the docs index, a link | `tools/gen_docs_index.py --check`, `tools/pd2-port/check_links.py` |
| a stale byte in `dist/` | the `packs` job: `fresh.py check` builds it again and compares |
