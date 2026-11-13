# Tools that do one job in more than one place

This file is written in the order of the work. The section "What is expected" was
written and committed before any copy was run against a real file. What was
measured, the table of differences and what was merged follow it.

A merge is allowed here only if no byte of a tracked pack changes.

## The candidates

| Job | Where it is done |
| --- | --- |
| Diesel `.model` | `tools/pd2-port/dmodel.py` reads; `tools/pd2-las/diesel_model.py` reads and writes; `tools/pd2-port/las_model.py` writes |
| DDS textures | `tools/pd2-port/dds.py`; `tools/pd2-las/dds_encode.py` |
| The files that register a pack with LAS | `tools/pd2-las/las_pack.py`; `tools/pd2-las/las_outfit_pack.py`; `render_hook_lua`, `render_localization`, `render_main_xml` and `render_glove_adapter_lua` inside `tools/pd2-las/build_christie_las.py`; and a fourth copy that turned up when the code was read, `hook_lua`, `main_xml`, `unit_xml`, `localization` and `write_zip` inside `tools/pd2-port/build_las_pack.py` |
| The environment | `tools/pd2-las/bootstrap.sh`; `tools/pd2-las/recover_env.sh`; the pinned versions are also written in `.github/workflows/test.yml` and `.github/workflows/lawson-las.yml` |

## What is expected

From reading the code, before anything was run. Numbered, so that each can be
answered.

`.model`

1. The idstring hash (`dmodel.hash64`, `diesel_model.hash64`) gives the same value for every name in every file and for random bytes.
2. The two tag tables give the same number to the 13 names both have. `dmodel` names 7 more.
3. Every model in the packs built by `tools/pd2-las/`, in the head packs, in the 2B templates and among the 34 LAS models is a legacy container. The two models of `lawson_las` are DODB containers. `diesel_model` refuses DODB; `dmodel` reads both.
4. On legacy files the two readers give the same values for object3D, model_data, topology, material, material_group, skinbones, passthroughGP and topologyIP. In geometry they agree on positions, normals and the first UV set, and disagree on bone indices and weights in every skinned mesh: `dmodel` does not undo the legacy shift of channel types above 14, so it takes channel 15 for a UV set, 17 for indices and 20 for a second weight set. Where a vertex has three weights its read goes out of step, and the name hash at the end of the section is wrong too.
5. On the DODB files `dmodel` is the one that is right. Given the same payloads, the section decoders of `diesel_model` read every section the same except geometry.
6. `write(read(x))` gives `x` back for every legacy file. `encode(decode(section))` gives the section back for every section of the packs built here and of 2B. Among the 34 LAS models some geometry sections will not decode, for a channel the codec does not know. I do not know how many.
7. Only `dmodel` reads `bones`. Only `diesel_model` reads `custom_hashlist`.
8. `dmodel.minv` and `me2_dae.minv` are the same text. `diesel_model.mat_inv` is another method: it differs in the last bits, and after packing to float32 it is usually the same and sometimes not.

DDS

9. The two header writers (`dds.pack_dds`, `dds_encode._dds_header`) write the same 128 bytes for a square texture with a full chain of levels, from 2x2 to 4096x4096. They differ for 1x1 and for a file with one level, which only `_dds_header` can write.
10. Every DXT5 header in the 16 tracked zips is one that one of the two writers writes.
11. The two decoders (`dds.decode_dxt5`; `dds_encode.decode_bc3_level`, which is Pillow) agree on alpha everywhere and differ by at most 1 in colour, in a minority of texels: they widen 5 and 6 bits to 8 differently. `texture2ddecoder`, written elsewhere, agrees with Pillow exactly.
12. The three encoders (`dds.encode_dxt5`; `dds_encode.rgba_to_bc3_dds`; `dds_encode.encode_bc3_texels`) give different bytes for the same picture, flat blocks apart. The third has the least error.
13. The two functions that put the colour endpoints in order (`dds.fix_misordered_blocks`, `dds_encode._enforce_c0_ge_c1`) give the same bytes for a block with c0 < c1 and differ for a block with c0 = c1 whose indices are not zero: the second clears the indices. I expect such blocks in the textures of the Christie packs and none in the normal maps of the Miranda packs.
14. The two level tables (`dds.dds_mip0_slice`, `dds_encode.bc3_levels`) agree on every tracked texture.

The files that register a pack

15. `render_unit_xml` of `las_pack` and of `las_outfit_pack` give the same bytes. The one of `build_las_pack` ends with a newline.
16. For the same names, the hook of `las_pack`, of the Christie builder and of `las_outfit_pack` is the same text except one flag (`replace_all` against `replace_body`) and the `glove_adapter` line. The hook of `build_las_pack` has the keys of `las_pack` and other white space.
17. The localisation file has the same shape in all four. The one of `build_las_pack` ends with a newline.
18. `main.xml` of the Christie builder is that of `las_outfit_pack` for the same data. That of `las_pack` adds a `<texture>` line for the eyes and lists the pairs in the order of their roles. That of `build_las_pack` is indented with four spaces.
19. The glove adapter of the Christie builder is a shorter copy of the one in `las_outfit_pack`: the same Lua once the comments are removed. I am not sure of this one.
20. `zip_pack` of `las_pack` and of `las_outfit_pack` give the same bytes for the same folder, and each gives the tracked zip back from its unpacked contents. `write_zip` of `build_las_pack` stamps 2026 where they stamp 2020.

The environment

21. The four places carry the same two pins.
22. The venv part of `bootstrap.sh` and `recover_env.sh` install the same version of everything both install. `bootstrap.sh` adds `lupa` and `sourcepp`. `recover_env.sh` upgrades pip.
23. The tests that need `lupa` or `sourcepp` skip after `make env` and in CI.

What I expect to be able to merge without changing a byte: the registration files
of the three `tools/pd2-las/` writers (one implementation, the flag as data); the
environment (one script, the pins written once); and of `.model` only what agrees
(the hash, the inverse). The two readers and the two decoders I expect to
disagree, so they would stay apart and be reported.

## What was recorded before anything changed

`python tools/pd2-las/copies.py record`. The results are in
`2026-11-12-tool-merge/` next to this file (`reference.json`, `record.txt`,
`trace/`).

- Every tracked pack was built again with each builder logging the files it
  opens and the function that opens them, and with line coverage of the ten
  files that hold the copies. 16 of 16 zips were the tracked bytes, so the
  measuring changed nothing.
- The suite ran under the same coverage. Without this audit's script 786 tests
  pass. With it one failed, and that one was the script: it spelled the path
  of the 2B templates, which a test forbids. Corrected.
- 30 tools were started in a copy of the tree, twice: every tool that uses one
  of the copies and is not a builder, and what the Makefile and the workflows
  start. Kept for each: its exit code, what it prints, a sha256 of every file it
  writes. All 30 were the same both times. 22 end with exit 0. Eight do not,
  the same way each time: three need the sources of the cancelled Skyrim
  outfit; `check_guide_compliance.py` stops inside `dmodel` on `Miranda_LAS`
  and on `Christie_LAS` (M3 below); `check_mesh_geometry.py` looks for the
  paths of `lawson_las` in them; `uv_check.py` stops after writing four files,
  with the arguments it was given here, and that was not looked into.
- The checkpoint trace of the six builders was taken twice: 1,145 functions,
  each with a checksum of everything it returned. None differed between the
  two runs.
- pylint 4.1.3, duplicate-code: 18 blocks, 218 lines, in 67 files.

What the log of opened files added to reading the code: a zip was written from
four functions, not two (`las_pack.zip_pack`, `las_outfit_pack.zip_pack`,
`build_joy_head_mods.write_deterministic_zip`, `build_las_pack.write_zip`).
What the coverage added: six functions of `las_outfit_pack.py`, the ones that
register the cancelled Skyrim outfit, are reached by tests only. No build calls
them.

## What the copies give on real files

`python tools/pd2-las/copies.py compare` takes the copies as they were at
`26fce3e` and runs them on every `.model` and `.texture` in the 16 tracked
zips, in the 2B templates and in the LAS mod of `Vladik268/P2` at `b7c38c1d`
(34 models and 41 textures made by other people with other tools). That is 60
different models with 11,808 sections, and 92 different textures; the 58 that
are DXT5 hold 106 million texels over all their levels. The full output is
`2026-11-12-tool-merge/compare.txt`.

Each expectation, answered:

| # | Result |
| --- | --- |
| 1 | Right. 0 of 20,261 inputs differ (261 names from the files, 20,000 random byte strings), with a level and as text too. Of the name hashes in the models of 2B, 586 of 640 are the hash of a name the same file lists. |
| 2 | Right. |
| 3 | Right: 58 legacy, 2 DODB. `dmodel` reads all 60 to the end without stopping. |
| 4 | Right for the eight kinds, 10,709 sections. Worse than expected for geometry: of 826 sections both read, positions agree in all, bone indices and weights differ in 471, and so do normals in 226 and UVs in 220, because in those files the skin channels come first. The name hash is wrong in 127, the rest of the section in 71. |
| 5 | Right. 154 sections of the two DODB files read the same. The 3 geometry sections stop `diesel_model`: normals packed in four bytes, UVs as half floats. |
| 6 | Right for all 58 files and for every section of the packs and of 2B. In the LAS mod 4 geometry sections do not decode (a vertex colour channel) and 2 decode but cannot be encoded again (a fourth weight). |
| 7 | Half tested. 24 `custom_hashlist` sections, read by `diesel_model` only. No file has a `bones` section. |
| 8 | Wrong. `diesel_model.mat_inv` gives exactly what `dmodel.minv` gives on 3,037 matrices from the files. `dmodel.minv` has the body of `me2_dae.minv`, and nothing calls it. |
| 9 | Right for the 41 tracked textures with a full chain. Four tracked textures have one level, and only `_dds_header` writes those. |
| 10 | Right: 45 of 45. |
| 11 | Right on alpha (never differs) and on the step (1). Wrong on "a minority": colour differs in 12% to 72% of the texels of a group, about half in the packs built here. Pillow and `texture2ddecoder` agree on every texel. |
| 12 | Right that the bytes differ. Wrong that the third has the least error: on 12 samples `dds.encode_dxt5` has the least colour error in 7, `encode_bc3_texels` in 2, 3 are level, and only `encode_bc3_texels` loses any alpha. The samples are decoded blocks, the easy case for the other two, so this says nothing about a fresh picture. |
| 13 | Could not be tested, and wrong about the Christie packs. No texture has a block with c0 < c1 (0 of 6.6 million blocks). Blocks with c0 = c1 and indices exist in 3 textures of the LAS mod only, and there both functions leave them alone: `_enforce_c0_ge_c1` returns before clearing when it has nothing to swap. |
| 14 | Right, 58 textures. |
| 15 to 18 | Right. The order of the pairs changes no byte of a tracked pack. |
| 19 | Right: the same 14 lines of Lua. The name given to the hook differs (the item id against a fixed word), and the comments. |
| 20 | Right, and more: each `zip_pack` gives the tracked bytes of 13 of the 14 zips in `dist/`, the nine head packs among them, which a third writer made. |
| 21 to 23 | Right. 20 packages, the same versions. Only `bootstrap.sh` adds `lupa 2.8` and `sourcepp 2026.11.1`. Without them 3 tests skip where 12 more would run. |

The tests written for one copy, run against the other, all pass: `dmodel` with
the hash of `diesel_model` (180), `diesel_model` with the hash of `dmodel`
(353), `las_pack` with the unit file and zip of `las_outfit_pack` (88), and the
reverse (114).

## Every difference between the copies

Kinds: (a) a tracked pack needs it; (b) a fix one copy has and the other lacks,
reported and not fixed here; (c) reached by nothing.

| # | Difference | Kind | Evidence |
| --- | --- | --- | --- |
| M1 | `dmodel` reads the DODB container, `diesel_model` refuses it | a | the two models of `lawson_las` are DODB; the other 58 files are legacy |
| M2 | `dmodel` reads normals packed in four bytes and half-float UVs | a | 3 geometry sections of `lawson_las` |
| M3 | `diesel_model` undoes the legacy shift of channel types above 14, `dmodel` does not | b | 471 of 826 legacy geometry sections come out of `dmodel` without bone indices or weights and wrong behind the first skin channel. No pack is written from that reading. What works without the fix: `check_guide_compliance.py` stops with `struct.error` on `Miranda_LAS` and `Christie_LAS`, so only `lawson_las` has a guide audit |
| M4 | `dmodel` steps over a vertex colour channel, `diesel_model` refuses the section | b | 4 sections, all in the LAS mod; no pack here has the channel |
| M5 | `dmodel` keeps a fourth weight, `diesel_model` keeps three | b | 2 sections, both in the LAS mod, decode and cannot be encoded again; no pack here has four weights |
| M6 | `dmodel` gives a zero for five ids a version-6 `model_data` does not have | c | 474 sections; no value differs |
| M7 | only `dmodel` has a reader for `bones` | c | no file has the section |
| M8 | only `diesel_model` reads `custom_hashlist` | a | 24 sections: the models built in `tools/pd2-las/` carry one |
| M9 | `dmodel` names seven more kinds of section | c | 2 `light` sections met; a name, nothing read |
| M10 | only `diesel_model` checks the size the header states | c | every file states its size right |
| M11 | `las_model.py` writes DODB with packed channels, `diesel_model.encode_*` writes legacy sections | a | `lawson_las` against the 13 other packs; eight kinds of section are the same bytes either way (154 sections) |
| D1 | `dds.decode_dxt5` widens 5 and 6 bits to 8 another way than Pillow | a | both run in builds: `Christie_LAS`, `Christie_LAS_Slim` through `dds.decode_dxt5`, `Miranda_Busty_LAS`, `Miranda_LAS` through `dds_encode.decode_bc3_level` |
| D2 | three encoders, three results | a | `dds.encode_dxt5`: `Christie_LAS`, the nine head packs, `lawson_las`, `Christie_LAS_Slim`. `dds_encode.encode_bc3_texels`: `Miranda_Busty_LAS`, `Miranda_LAS`. `dds_encode.rgba_to_bc3_dds`: `Miranda_Busty_LAS`, `Christie_LAS`, `Miranda_LAS`, `Christie_LAS_Slim` |
| D3 | only `_dds_header` writes a file with one level | a | four tracked textures |
| D4 | the two level tables treat a cut-off file differently | c | no file is cut off; they agree on all 58 |
| D5 | `_enforce_c0_ge_c1` also clears the indices where c0 = c1, `fix_misordered_blocks` does not | not comparable | no file of the corpus has a block to swap, and without one neither function changes anything |
| W1 | `replace_all` in one hook, `replace_body` in the others | a | `Miranda_LAS` and `Miranda_Busty_LAS` have a `g_head` object, `Christie_LAS` and `Christie_LAS_Slim` have none. LAS, `hooks/outfits/loader.lua`: `if data.replace_all then output.third_body_replacement = {head=true,...}` |
| W2 | only `las_pack` registers a texture on its own | a | the eyes of the two Miranda packs have no normal map |
| W3 | only the other two write the glove adapter and its line in `main.xml` | a | `Christie_LAS_Slim` |
| W4 | only `las_outfit_pack` wrote `glove_adapter = true` into the hook | c | no tracked pack has the line, and LAS never reads it: `output.glove_adapter = output.glove_adapter or false` reads its own new table |
| W5 | `las_outfit_pack` had a fixed description, a fixed name for the adapter's hook and longer comments in it | c | reached by tests only |
| W6 | `build_las_pack` indents with four spaces, names its table and hook file otherwise, ends two files with a newline, stamps its zip 2026 | a | the bytes of `lawson_las`; nothing reads the white space |
| W7 | `las_pack.render_object_xml` puts one tab before `</graphic_group>`, `las_outfit_pack.render_object_xml` two; one lists a fixed table of objects, the other what the model has | a | the bytes of the Miranda packs and of the Christie packs. All 32 `</graphic_group>` lines in the 36 `.object` files of 2B and the LAS mod have two tabs (four of the files have no such line); a parser reads both |
| W8 | the first-person material file of `las_pack` lists four head materials without `DEPTH_SCALING` | c | in the first-person models of `Miranda_LAS` and `Miranda_Busty_LAS` the `g_*` objects draw with `mtr_body`, which has it, and `s_body` with `shadow_caster`; one more object, which the `.object` file does not name, draws with a material that the material file does not list; no object draws with any of the four |
| E1 | only `bootstrap.sh` installs `lupa` and `sourcepp` | b | after `make env` and in CI, 12 tests do not run. Among them are the ones that run the hook and the glove adapter of a pack in a Lua interpreter |
| E2 | only `recover_env.sh` upgrades pip | c | the same 20 packages either way |
| E3 | `bootstrap.sh` went on to build four packs in place, wrote `dist/lawson_las.zip.sha256` from that build and then checked it, ran the suite and a lint | c | no Makefile target, workflow or test started it. A checksum written from the build it checks cannot fail |
| E4 | the list of packages is written three times: `recover_env.sh` installs pytest, pillow, numpy, pyyaml, pyflakes, py7zr and scipy; `test.yml` installs a list of its own without py7zr; `lawson-las.yml` one without py7zr, pyflakes and scipy | b | four tests of `tests/test_christie_las.py` import scipy. With the four packages of `lawson-las.yml` the suite ends with 4 failed, the same four at `26fce3e` and after the merges, and on GitHub the `tests` step of `lawson LAS pack` fails (run 43287034158). `main` has the same test and the same list. No file under `tests/` names py7zr. This row was added after that run: the comparison had held the pins of the workflows against each other, not their lists |
| | unexplained | | none |

No difference at all: the hash; the 13 tag numbers; the inverse on 3,037
matrices; the header of every tracked texture with a full chain; the level
tables; the unit file; the strings; the zip of three writers; the two pins in
four places.

## How each job was sorted

| Job | Sorted as | What was done |
| --- | --- | --- |
| idstring hash, tag numbers | one right answer, the copies agree | merged |
| the files that register a pack, the unit file, the glove adapter, the zip | a choice | the shared part merged; what a pack chooses is a `Registration` |
| the environment and the pins | a choice | the two scripts and the pins merged; the choice is `--extras`. Each workflow still installs a list of packages of its own (E4): reported |
| reading a `.model` | one right answer, the copies disagree (M3) and each reads what the other cannot (M1, M2, M4) | apart. One reader would change what `dmodel` returns for 471 sections: that is the fix of M3, and it is not made here |
| writing a `.model` | apart on purpose (M11) | apart |
| decoding and encoding BC3 | a choice with nothing shared: the bytes are the choice (D1, D2) | apart |
| the DDS header and the level table | one right answer, the copies agree on every real file | apart: they could be merged, and are the fourth job where three were allowed |
| putting the endpoints in order | not comparable on these files (D5) | apart |
| registering `lawson_las` | apart on purpose (W6): another layout, in the other pipeline | apart |
| the `.object` file, the material files | a choice (W7, W8) | apart |
| the 4x4 inverse | `dmodel.minv` reached by nothing | removed with the hash. `me2_dae.minv` and `diesel_model.mat_inv` agree on every matrix tried and take matrices in different shapes; the bytes of `lawson_las` go through the first. Apart |

## The three merges

Each is one commit. After each, `python tools/pd2-las/copies.py after` built
every pack again, ran the suite, took every builder's trace and started the 30
tools, and compared all of it with the record.

**The idstring hash and the tag numbers (`4d7cb0e`).** `dmodel.py` takes
`hash64` and the 13 shared numbers from `diesel_model.py`; its `minv` is gone.
16 of 16 zips; 790 tests pass (786 and 4 new). In the trace of the lawson
builder `dmodel.hash64` and `dmodel._mix` are gone and the same values come
from `diesel_model.hash64` and `diesel_model._mix64`; every other function of
every builder returns what it returned. 30 of 30 tools give what they gave,
once the line numbers of a traceback are left out of the comparison: two of
them stop inside `dmodel.py`, which is 33 lines shorter.

**The files that register a pack (`3846653`).** `las_outfit_pack.py` writes
`main.xml`, the hook, the strings, the unit file, the glove adapter and the
zip. `las_pack.py`, `build_christie_las.py` and the module itself each say in a
`registration` function what their packs choose. `build_joy_head_mods.py` zips
through the same function. The glove adapter is the text the tracked
`Christie_LAS_Slim` has; that text names `las_outfit_pack.render_glove_adapter_lua`
in a comment, which is why the function stays under that name. 16 of 16 zips;
793 tests pass. In the traces the four functions of the Christie builder are
gone and the same values come from `las_outfit_pack`; six helper functions are
called another number of times and return the same values each time (the
Registration is built once per file written); none returns anything else. 30 of
30 tools. With `lupa` and `sourcepp` installed aside, the tests that run the
hook and the adapter in a Lua interpreter pass before and after: 53.

**The environment (`692ea90`).** `recover_env.sh` is the one script, with
`--extras` for `lupa` and `sourcepp`. `pins.txt` holds the two versions; the
script and both workflows install with it as their constraints file, and
`status.py` reads it. `bootstrap.sh` is deleted, and every document that named
it says so. In a copy of the tree the script makes the same 20 packages as
before the merge, and `--extras` adds exactly the two that `bootstrap.sh`
added. 16 of 16 zips; 794 tests pass; traces and tools as after the second
merge. The workflows do not run the script: each still installs a list of
packages of its own (E4).

Each merge has tests in `tests/test_one_implementation.py` (and one in
`tests/test_pd2_las_status.py`) that fail when the copy or the difference is
put back. Shown failing: the old hash, a tag number and `minv` written into
`dmodel.py` again; a second hook template; the flag of a Miranda pack changed
to `replace_body`; the year of the zip changed; a second zip writer;
`bootstrap.sh` restored; a version written into `test.yml` again. Nine of nine.

What is left under the old names. `las_pack.render_hook_lua`,
`render_localization` and `render_main_xml`, and the three functions of the
same names in `las_outfit_pack.py`, are one line each: they hand that module's
`Registration` to the writer. `dmodel.hash_str` is one line over
`diesel_model.hash64`, and `dmodel.TAGS` is the 13 shared numbers and the
seven kinds that only `dmodel` names. `build_joy_head_mods.write_deterministic_zip`
takes the bytes of its zip from `las_outfit_pack.zip_bytes` and writes them
next to their `.sha256`. Builders, checks and tests call these names. None of
them holds a template, the constant of the hash, a tag number or a `ZipInfo`,
and the tests of `tests/test_one_implementation.py` fail if one does.

Test edits beyond an import line: `test_status_reads_its_pins_from_bootstrap`
became `test_the_pins_are_written_once` (it read `bootstrap.sh` and held three
copies equal to it; there is nothing left to hold equal); two tuples in
`tests/test_pd2_las_status.py` lost `bootstrap.sh`; the reason of one skip in
`tests/test_render_mesh_skeleton.py` names the Makefile target. One import line
changed in `tests/test_pd2_las.py`. Nothing else in a test changed.

## Where the check was changed after it reported a mismatch

Three times `copies.py after` reported a mismatch and the comparison was
changed, not the code it checks. Each change makes the check weaker than "the
same bytes", so each is named here.

1. The line numbers of a traceback are left out of what a tool prints. Two of
   the 30 tools stop with a traceback inside `dmodel.py`, which is 33 lines
   shorter since the first merge.
2. For `um kb check` and `um publish check` the numbers are left out of what
   they print. Both walk the whole tree and count what they see, and the tree
   has new files. Their exit codes are still compared. Run by hand on this
   tree, `um kb check` ends with exit 0 and `PASS: 247 notes checked`.
3. A function that a build calls another number of times is held to the set of
   values it returned. Every other function is held to a checksum chained over
   all its calls. Since the second merge a `Registration` is made once for each
   file written, so six helper functions are called more or fewer times
   than before, 29 times at most. The rule covers functions called up to 40
   times, and `after` lists the ones it was applied to. For this rule two fields
   were added to each of the 1,145 rows of the reference traces in the commit of
   the second merge, taken from the two recordings made before the merges. What
   each row held before is unchanged.

A run of `after` on `8bd4fbf` with three date lines added to
`docs/pd2-las/DECISIONS.md` gave: 16 of 16 zips; 794 tests pass; of the 1,145
functions in the six traces 1,118 return what they returned, 12 are
called another number of times and return the same values, 15 are gone and
none returns anything else; 30 of 30 tools. Of the 15 that are gone,
13 have their values coming from the function that replaced them;
the other two are `render_main_xml.<locals>._base`, a helper inside a deleted
function, once in the trace of each Christie pack.

## Jobs with more than one implementation

| Job | Before | After |
| --- | --- | --- |
| idstring hash | 2 | 1 |
| tag numbers | 2 | 1 |
| glove adapter | 2 | 1 |
| making the environment | 4 (`bootstrap.sh`, `recover_env.sh`, the list of packages in each workflow) | 3 (`recover_env.sh`, the list in each workflow: E4) |
| the two pins | 4 places | 1 |
| `main.xml`, the hook, the strings | 4 | 2 (`las_outfit_pack.py`; `build_las_pack.py` for `lawson_las`) |
| unit file | 3 | 2 (the same two) |
| reproducible zip | 4 | 2 (the same two) |
| 4x4 inverse | 3 | 2 |
| reading a `.model` | 2 | 2 |
| writing a `.model` | 2 | 2 |
| decoding BC3 | 2 | 2 |
| encoding BC3 | 3 | 3 |
| DDS header, level table, endpoint order | 2 each | 2 each |
| `.object` file | 2 | 2 |
| material file | 3 | 3 |

Eighteen jobs had more than one implementation. Fourteen still do: one script
makes the environment now, and each workflow still installs a list of packages
of its own (E4). pylint's
duplicate-code report: 18 blocks and 218 lines before, 16 blocks and 195 lines after.

## What machines that are not this one showed

The workflow `test` runs the suite on a GitHub runner, then builds all 14 packs
there and holds each of the 16 zips to its tracked sha256 with `sha256sum -c`.
What is read here comes through the API: the result of each step, and the lines
the workflow writes about its runner and its build. The logs themselves cannot
be read from this sandbox.

| Commit | Runs | CPUs of the runners | Suite | Zips that were the tracked bytes |
| --- | --- | --- | --- | --- |
| `75f3d8f`, the expectations | 2 | EPYC 7763 (no AVX-512); EPYC 9V45 (AVX-512) | passes | 16 of 16 in both |
| `d641fc4`, the script of this audit | 2 | EPYC 9V74 twice (AVX-512) | fails in both. A clean checkout of the commit gives 1 failed here: the test the script itself broke, named in the record above and corrected in the next commit | 16 of 16 in both |
| `4d7cb0e`, the first merge | 2 | EPYC 9V74; EPYC 9V45 (both AVX-512) | passes | 16 of 16 in both |
| `3846653`, the second merge | 2 | EPYC 7763 (no AVX-512); EPYC 9V74 (AVX-512) | passes | 16 of 16 in both |
| `8bd4fbf`, all three merges | 21 | without AVX-512: EPYC 7763 five times, EPYC 9V74 once. With it: EPYC 9V74 seven times, Xeon Platinum 8573C seven times, Xeon 6975P-C once | passes in all 21 | 16 of 16 in all 21 |

`b5e36d3` and `692ea90` were pushed together with the commit after them and
have no run of their own. So the first merge on its own met only CPUs with
AVX-512, and the third merge ran only together with the first two. One EPYC
9V74 reported no AVX-512 where seven others reported it; the line is what that
runner said about itself.

The commits after `8bd4fbf` change documents, the record next to this file and
the script of this audit, and no file that a build reads. Their runs are on
the pull request.

The workflow `lawson LAS pack` was started once by hand, on `8bd4fbf` (run
43287034158). It built `lawson_las.zip`, the zip was the tracked bytes, and
then its `tests` step failed (E4). Its publishing step runs for a tag
`lawson-las-v*` only, so nothing was published.

## Reported, not fixed

1. `tools/pd2-port/dmodel.py` misreads the skinned geometry of legacy models
   (M3). `check_guide_compliance.py` therefore audits `lawson_las` and stops with
   `struct.error` on `Miranda_LAS` and `Christie_LAS`, the two legacy packs it
   was started on here. Fixing it means undoing the shift in `dmodel`
   or reading legacy files through `diesel_model`; either changes what several
   checks print.
2. After `make env` and in CI the tests that need `lupa` or `sourcepp` skip
   (E1). They include the only tests that execute the Lua a pack ships. They
   pass when run by hand with `recover_env.sh --extras`.
3. `diesel_model` cannot read a geometry section with a vertex colour channel
   and cannot write back one with four weights (M4, M5). No pack here has
   either; six sections of other people's models do.
4. Each workflow installs a list of packages of its own, and the list in
   `.github/workflows/lawson-las.yml` has no scipy (E4). Four tests of
   `tests/test_christie_las.py` import it, so the `tests` step of
   `lawson LAS pack` fails and the upload after it is skipped. `main` has the
   same test and the same list, and the workflow runs on every push to `main`,
   so the next push there should show it. Adding `scipy` to that install line
   ends the failure. Having both workflows run `recover_env.sh` would end the
   third copy of the list as well.

## How to repeat

`make -sC tools/pd2-las env`, then `python tools/pd2-las/copies.py compare`
for the comparison (it fetches the LAS mod and installs `texture2ddecoder`
under `build/copies/`, outside the environment) and
`python tools/pd2-las/copies.py after` for the check a merge is held to, about
14 minutes. `record` and `assemble` describe the tree before a merge
and write the tracked reference. Where the files that held the copies differ
from `26fce3e` they refuse to run.

## Corrected after the first version of this file

- W7 counted 32 `.object` files. There are 36, with 32 `</graphic_group>`
  lines among them.
- W8 said every object of the first-person model draws with `mtr_body`.
- The changes put back to show a test failing were counted as ten. Nine were
  made.
- The first item of "Reported, not fixed" said `check_guide_compliance.py`
  stops on 13 packs. It was started on two.
- E4, the fourth item of "Reported, not fixed" and the count of fourteen came
  from starting `lawson LAS pack` on GitHub. The first version counted
  thirteen.
- The sections on the runners and on the changes to the check are new.
- In the commits of the first two merges the reference was assembled again,
  and the recorded coverage was counted against merged files. That changed
  four entries of `reach` in `reference.json` and four lines of `record.txt`.
  Both are back to what was recorded before the merges. The builds, the suite,
  the traces and the lint figures of the reference never changed, and nine
  recorded outputs have another hash only through the first two changes to
  the check.

## 2026-11-13: four of the thirty recorded tools are gone

The owner had the code of the cancelled Skyrim outfit deleted (`docs/pd2-las/DECISIONS.md`, D33). Four
entries of `outputs` in `reference.json` were records of that code, and are taken out with it; `GOLDEN` in
`copies.py` lists 26 tools now. Nothing else in the reference was touched.

| Entry | What was recorded | What became of the tool |
| --- | --- | --- |
| `build_skyrim_outfit` | exit 2: it needs the outfit's archive, removed on 2026-11-05 (`eb2a9c5`) | deleted |
| `skin_texture` | exit 1, for the same archive | deleted |
| `pose_preview` | exit 1: its command read `build/skyrim-nif/` | the command is deleted; `glove_check.py` and `pose_zoom.py` import the pose |
| `preview_textured` | exit 0 and one PNG, of `miranda.model` with no texture on it: the command looked for `outfit_<material>_df.texture`, the file names of that outfit | the command is deleted; the same two tools and two test files import the rasteriser |

They were three of the eight that did not end with exit 0, which leaves five, and one of the 22 that did.

`python tools/pd2-las/copies.py after` on the tree without that code: 16 of 16 zips are the tracked bytes
after a fresh build; the report on every builder's trace is line for line the one above, with no function
that returns something else; 26 of 26 tools give what they gave
([`2026-11-13-agent-entry/deleted/copies-after.txt`](2026-11-13-agent-entry/deleted/copies-after.txt)).
`MODEL_TESTS` and `SWAPS` in `copies.py` still name test files that are gone from the tree: `compare` runs
them in a worktree of `26fce3e`, where they are.

## 2026-11-13: `lawson_las` built again without its credits file, and the reference follows

The owner had `CREDITS.txt` taken out of `lawson_las` (`docs/pd2-las/DECISIONS.md`, D34). The pack was built
again on purpose, so `copies.py after` gave exit 1: 22 of 26 outputs, and two traced functions of the Lawson
builder that return something else. Each difference was held against the reference before the reference was
changed.

| Entry | Was, is | How it was checked |
| --- | --- | --- |
| `outputs.status` | another size and sha256 for `lawson_las` | the new text with the old size and hash put back has the recorded checksum |
| `outputs.check_guide_compliance` | 123 lines, 120: the three lines of check `N2` are gone and the summary counts 37 passes for 38 | the checker of `4e15ed6` on the pack of `4e15ed6` prints the recorded text; `diff` against the new one shows those four lines and no other |
| `outputs.check_guide_compliance_self_test` | "(39 checks)", "(38 checks)" | the new text with 39 put back has the recorded checksum |
| `outputs.check_test_suite_mutations` | prints the same; the pack it writes has the new sha256 | the recorded text is unchanged |
| `trace/lawson.txt`, `build_las_pack.credits_txt` | gone | the function is deleted |
| `trace/lawson.txt`, `build_las_pack.assemble` | returns the pack's files, one fewer | the 28 files left are byte for byte the old ones ([`pack-diff.txt`](2026-11-13-agent-entry/answers/pack-diff.txt)) |
| `trace/lawson.txt`, `build_las_pack.sha256` | called 30 times, was 31; 28 different values, were 29 | the 28 values, with the new zip's hash taken out and the hashes of the old zip and of the old `CREDITS.txt` put in, have the recorded checksum of the 29 |

The last row says that every hash the builder computes, of its source archive and of each of the 28 files, is
the one it computed at `26fce3e`. `trace.functions.lawson` counts 143 for 144. Nothing else in the reference
was touched, and with these entries recorded again `copies.py after recheck` gives 26 of 26 and exit 0.
