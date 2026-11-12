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
