# tools/pd2-port — the DODB readers, the pack checks and the repository gates

Three things live here, and one that used to.

**The checks that read a built pack.** `check_mesh_geometry.py` decodes the geometry out of any
tracked ZIP and judges it the way the engine would: triangle winding (an inside-out face is culled,
so the character renders as holes) and the tangent frame the `uvdir_u`/`uvdir_v` streams carry
(a frame that disagrees with the UVs mirrors the normal map's lighting). It is also a stage of
`check_all.py --pack` and of both builders: `build_models.py` runs it on what it just wrote.

**The repository gates.** `check_all.py` is the whole verification chain (`make -sC tools/pd2-las
green` = `check_all.py --full`); `check_links.py` resolves every relative Markdown link;
`check_skip_budget.py` holds the suite's skips to the budget `tests/conftest.py` declares.

**Two format readers other tools still use.** `dmodel.py` reads legacy and Diesel 3 ("DODB")
containers without depending on the character inside them — the geometry check and
`tools/render_mod_previews.py` both run on it. `dds.py` is the DXT5 encoder/decoder; `me2_dae.py`
is the COLLADA importer, still read by `tools/build_joy_head_mods.py`, which takes the ME2 face
mesh's UVs to place the L4D2 head's eyelashes.

```sh
.venv/bin/python tools/pd2-port/check_all.py --pack dist/Miranda/OfficeSuite.zip   # checksum + geometry
make -sC tools/pd2-las green                                                       # everything, one line per stage
.venv/bin/python tools/pd2-port/check_mesh_geometry.py [pack.zip]                  # the geometry alone
.venv/bin/python tools/pd2-port/check_links.py                                     # every relative link
```

`check_all.py` has no default pack: it verifies the repository, and a pack only when `--pack` names
one. A selected pack gets its checksum and its geometry and nothing else — it never inherits an audit
result from an unrelated source or another pipeline.

## The port that was here

This directory was the ME2 → PAYDAY 2 LAS port: build_las_pack.py imported a rigged COLLADA
character, transferred its skin onto 2B's rig (rig_target.py, the rig contract in
`reference/las_rig.json`), wrote the model (las_model.py) and assembled
the Romance LAS pack, with preview_check.py and shade_check.py to look
at the result and three auditors of its own (check_guide_compliance.py and its self-test,
check_nm_convention.py, check_test_suite_mutations.py).

**The owner retired it on 2026-11-26 (D83)**, together with the other two ME2 packs
(`OfficeSuite_Head`, `Miranda_Romance_over_Hila`): the pipeline, its tests, its audits, its rig
contract and its pack are gone from the tree. What it decided and what it learned is still written
down — [`STATUS.md`](STATUS.md) is the port's dated record, [`MODLOG.md`](MODLOG.md) its journal,
and the audits in [docs/audits/](../../docs/audits/) cover the winding repair, the green-channel
question and the guide compliance it built. The port's own test module went with the code it tested.

The LAS contract itself did not go: it is in
[`knowledge/games/payday-2/las-armor-skin-outfit.md`](../../knowledge/games/payday-2/las-armor-skin-outfit.md),
and the two LAS packs the repository still ships — `Miranda_L4D2_LAS` and `OfficeSuite` — are built
by [tools/pd2-las/](../pd2-las/README.md).
