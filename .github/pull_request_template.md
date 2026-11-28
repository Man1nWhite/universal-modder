<!-- Field note PR? Most of this is filled in by `um kb pr`. -->

**What:** <!-- one line: game + what was built / learned, or the tool/skill change -->

**Checklist**
- [ ] `um kb check` passes (field notes) / `pytest -q` passes after `pip install -e '.[dev]'` (code;
      the 2B template models are tracked, so nothing is unpacked first)
- [ ] `um kb index` regenerated (field notes) / `python tools/gen_docs_index.py` regenerated (docs)
- [ ] `python tools/pd2-port/check_links.py` passes (docs)
- [ ] `dist/`, a builder or `tools/pd2-las/packs.py` changed: `make -sC tools/pd2-las fresh`
      passes, or the `packs` job reports it (see `docs/pd2-las/ADD-A-PACK.md`)
