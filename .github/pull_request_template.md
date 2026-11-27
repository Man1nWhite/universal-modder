<!-- Field note PR? Most of this is filled in by `um kb pr`. -->

**What:** <!-- one line: game + what was built / learned, or the tool/skill change -->

**Checklist**
- [ ] `um kb check` passes (field notes) / `pytest -q` passes after `pip install -e '.[dev]'` (code;
      the 2B templates are extracted on first run, or those tests skip with the command that fixes it)
- [ ] `um kb index` regenerated (field notes) / `python tools/gen_docs_index.py` regenerated (docs)
- [ ] `python tools/pd2-port/check_links.py` passes (docs)
- [ ] `dist/`, a builder or `tools/pd2-las/packs.py` changed: `make -sC tools/pd2-las fresh`
      passes, or the `packs` job reports it (see `docs/pd2-las/ADD-A-PACK.md`)
- [ ] no game files, extracted assets, decompiled code dumps or secrets
- [ ] nothing that cheats other players or bypasses anti-cheat / DRM / ownership checks
- [ ] versions, verification and what was NOT verified are written down
- [ ] authored by (agent + model / human): <!-- e.g. Codex (gpt-6) with @someone -->
