# Second pass over the Garry's Mod tooling: what was wrong, what is better

**Date:** 2026-11-05
**Baseline:** `8a5ead8` (`main`, the merge that landed `gma.py` + the two inspectors)
**Scope:** `tools/pd2-las/gma.py`, `inspect_gma.py`, `inspect_textures.py`, and the
Source readers underneath them (`vpk.py`, `vtf.py`, `source_model.py`), plus the tool
survey in `tools/pd2-las/README.md`.

No game runtime was available and none is needed: every finding below is reproducible
offline. Three sources of truth were used, in this order of authority:

1. Facepunch's own `gmad` (`include/AddonReader.h`, `src/create_gmad.cpp`) — the writer
   and reader that produce every `.gma` in existence.
2. A **second implementation**, `sourcepp`'s `vpkpp` (pip wheel), driven against the
   same bytes the tests build, for a machine-checked opinion rather than a reading.
3. Two real archives already in this repo — the L4D2 `miranda_rochelle.vpk` and
   `models/Geralt.7z`, which is an **unpacked Garry's Mod workshop addon**
   (`addons`-layout, item `1259069870`: 2 MDLs at v49, 28 VTFs, 27 VMTs).

That third item is the one that changed the verdict. The previous pass validated the
readers against L4D2 and inferred GMod from it; the Geralt addon is real GMod-shaped
content and it is now the second validation set.

## Verdict

The readers were **structurally right and behaviourally incomplete**. Every byte-level
layout claim in `gma.py` matched `gmad` — the parser was not confused about the format.
What was missing was the checks and the shapes a real addon uses:

- the **trailing archive CRC32** `gmad` appends was never read, so the one check that
  covers the header, the index and every body at once was absent;
- the **required-content list** was parsed and thrown away, although GMod acts on it;
- only `.gma` was readable at all — the tracked Geralt addon, which is a **folder**,
  could not be fed to either inspector;
- a model with **bodygroups** (a hat, alternate hair, a wear variant) failed outright;
- MDL **v44–v47** were refused, which is exactly what an HL2-era GMod ragdoll is;
- three output/labelling bugs made correct data look wrong (missing Pillow reported as a
  broken texture, a wrong DDS pitch, and alpha/luminance surfaces mislabelled).

The tool survey was mostly sound but carried **two factual errors** that would have cost
real time — one of them forbidding the use of a library that is permissively licensed,
the other crediting a library with MDL support it does not ship to Python.

## What was wrong, with the evidence

### 1. The archive CRC32 was invisible (`gma.py`)

`src/create_gmad.cpp` finishes every addon with `Hasher::CRC32::Easy(...)` over
everything written so far. `vpkpp` agrees and exposes it as
`verify_pack_file_checksum()`; our fixture, which the old docstring described as
"exactly as `gmad create` writes one", omitted those four bytes — so the test suite was
pinning an archive shape `gmad` never produces.

**Now:** the trailing CRC is parsed when present (`archive_crc`), verified
(`archive_crc_ok`), reported by `inspect_gma.py` as a `WARNING` line, and the fixture
appends it. A CRC mismatch is a warning rather than a hard error on purpose: a stale
checksum after a hex-edit is a fact about the file, not a reason to refuse to read it.
`test_sourcepp_reads_the_same_archive` keeps `vpkpp` asserting that the fixture's entry
checksums **and** pack checksum verify, so the format claim is now machine-checked
against a second implementation.

### 2. Required content was parsed and dropped (`gma.py`)

The v2+ header carries a list of games the addon needs mounted. `gma.py` walked it with
`while cstr(): pass`. It is now `GmaArchive.required_content`, shown by `summary()` and
by `inspect_gma.py` — because "every file is present" and "it will render" are different
questions in GMod, and only the second one matters after you install something.

### 3. A folder addon could not be inspected (`inspect_textures.py`)

`open_container()` accepted `.gma`, `.vpk`, `.zip` and nothing else. The addon this repo
actually tracks (`models/Geralt.7z`, extracted to an `addons`-style folder) is the common
case, not the exotic one: an unpacked addon, a legacy zip with one wrapper folder, or a
`.gma`. All three now open through the same interface, and:

- a wrapper folder (`MyAddon/materials/...`) is stripped, but a **content root**
  (`materials/`, `models/`, `lua/`, …) never is — otherwise a folder addon whose only
  content is under `materials/` would lose its paths;
- `addoninfo.txt` is read in **both** spellings found in the wild — GMod's KeyValues
  form (`"name" "Geralt"`, `"tags" "fun"`) and the older Valve form L4D2 addons still
  ship (`AddonTitle "Geralt"`, `AddonDescription "..."`, `AddonContent_*`) — plus
  `addon.json` for `gmad`-packed addons;
- a latent bug is fixed while doing it: the `zip` branch used to hand out `zf.read`
  after its `with` block had closed the archive, so any zip that was not a single
  `.gma`/`.vpk` member would parse the tree and then fail on the first read. Zip members
  are now read while the handle is open.

### 4. A model with bodygroups failed (`source_model.py`)

`_read_vtx_meshes` walked **every** model of every bodypart, while the MDL side only
describes model 0 — the default state. The two counts could never agree for any model
that has an alternate state, so a playermodel with one hat died with
`VTX has 6 meshes, MDL has 5`. GMod playermodels are built out of these alternates.

**Now:** only each bodypart's model 0 is walked, matching the mesh table; the number of
skipped alternates is exposed as `ModelData.skipped_bodygroup_models` and printed by both
inspectors, so the omission is visible instead of silent. `tests/test_source_model.py`
builds a VTX byte-by-byte with 3 bodygroup models and asserts only the default is read —
the case neither real archive contains.

### 5. MDL v44–v47 were refused (`source_model.py`)

The gate was `(48, 49)`, with "L4D2-era" in the docstring. Everything this reader touches
is identical from 44 to 49: `studiohdr_t`'s count/offset pairs, the 216-byte
`mstudiobone_t`, and `mstudiomodel_t` addressed with `vertexindex / 48`. Source-faithful
parsers branch only at 36, 44, 53 and 2531, and GMod ragdolls imported from SFM/HL2 are
commonly v44. **Now:** 44–49, with the reasoning in `SUPPORTED_MDL_VERSIONS`, and a test
that rewrites the real model's version field to 44 and requires identical geometry.

### 6. A missing optional dependency reported as a broken asset (`inspect_textures.py`)

`_decodes()` caught `Exception` and returned `False`, so on a machine without Pillow
**every** texture was reported `✗` with "decoder refused the image data" — the one wrong
answer that sends someone hunting through their VMTs. It is now tri-state: `None` prints
`?` with "decoded: not checked — Pillow is not installed", and such a texture is not
counted as missing.

### 7. DDS output lied about its own layout (`vtf.py`)

Only visible when the DDS is read by something other than Pillow:

- `dwPitchOrLinearSize` was set to the **whole image size** for uncompressed formats
  instead of one scanline — a reader that trusts it steps `height×` too far per row;
- `A8` was labelled `RGB|ALPHAPIXELS` with no masks, `I8`/`IA88` as RGB with the
  luminance channel in green — both decode to black in an external viewer;
- `BGRX8888` declared an alpha channel it does not have;
- volumetric VTFs were half-converted (DDS said depth 0 while the payload had depth);
  now refused with a clear error, since a volume's mip chain shrinks in depth too.

### 8. Smaller ones

- `vpk.py` used `data.index()` for tree strings, so a truncated VPK raised a bare
  `ValueError` past the CLI's `except VpkError` and printed a traceback. Now `VpkError`.
- `parse_vtf` indexed bytes 61–64 without a length check (short file → `IndexError`).
- `inspect_gma.py`'s docstring promised "material/texture presence" as item 4 and never
  did it; the report now says out loud that textures are `inspect_textures.py`'s job, and
  the verdict no longer implies the rig alone decides usability.
- `inspect_gma.py --json out/report.json` failed when `out/` did not exist.
- `model_paths()` ignored `.dx80.vtx`/`.sw.vtx`, so a DX8-era addon was reported as
  containing no readable model at all. Shared as `VTX_SUFFIXES`.

## What was wrong in the tool survey

| claim | verdict |
| --- | --- |
| `sourcepp` covers "MDL 44-49" via `mdlpp` | **wrong for the pip wheel.** `mdlpp` exists as C++ headers (`include/mdlpp/`); the wheel binds `bsppp gamepp kvpp sourcepp steampp toolpp vcryptpp vpkpp vtfpp` only. `import sourcepp; sourcepp.mdlpp` → `AttributeError`. MDL parsing is not reachable from Python. |
| `srctools` is **GPL-3.0**, so "do not vendor" | **wrong.** `LICENSE` is MIT (only `libsquish/` is excluded) and PyPI's classifier says `License :: OSI Approved :: MIT License`. The conclusion drawn from it does not hold. |
| `sourcepp` is "the one worth having" | still true, with a caveat found by driving it: `vpkpp`'s `GMA::open` reads the required-content list as a **single** string, so an addon that declares one comes back with an empty name and a mangled path (`materials/...` → `ame`). It parses the file list and CRCs correctly; use it as a cross-check, never as the oracle. |
| VPK "v0/v1/v2/v54", VTF "7.0-7.6" | correct (`VPK::create` accepts 0/1/2/54; `VTF.cpp` rejects `version > 6`). |

One addition to the landscape: [`diogo464/gma`](https://github.com/diogo464/gma) (Rust,
MIT) is the only other implementation found that reads **and** writes the LZMA-compressed
workshop form, which it documents plainly ("Garry's mod can't read compressed gma files
but some when downloaded directly from the steam workshop some files are lzma compressed").
`gma.py` already unwraps that; nothing here can call Rust, so it is recorded, not adopted.

Still not adopted, and why nothing changes there: Crowbar and Noesis are Windows-only
human tools; SourceIO is the right answer *if* a Blender exists, which this sandbox has
shown it does not (`bpy` needs `libXrender`/`libXi`); `srctools` is MIT but nothing needed
`packlist` yet.

## How this was verified

```
.venv/bin/python -m pytest tests -q          # 496 passed, 46 skipped
.venv/bin/python -m pyflakes tools/pd2-las/{gma,vpk,vtf,source_model,inspect_gma,inspect_textures}.py
python tools/pd2-las/inspect_gma.py /tmp/geralt.gma           # 2 MDLs, 55,793 verts, ValveBiped
python tools/pd2-las/inspect_textures.py /tmp/geralt/1259069870  # folder addon, addoninfo.txt read
```

The Geralt run is the honest end-to-end check: 28 VTFs, 27 VMTs, and a real finding — the
addon's `armor_d`/`armor_d_it` materials name `armor_d.vtf`, which the addon does not
ship (`✗ armor_d: … -> no texture`). That is the tool doing its job on licensed content
that stays outside the repository.

## What was not verified, and the traps left standing

- **No real v44–v47 model was parsed.** The widening is argued from the struct layouts
  and tested only by rewriting a v48 header, so treat it as "should work" until a real
  HL2-era ragdoll is run through it. The parser's own cross-checks (VVD vertex count,
  VTX mesh count, vertex range) make a silent misparse unlikely — it fails loudly instead.
- **A bodygroup model with different *mesh counts* than its default** is still only
  counted, not read. Reading alternates means choosing one, which is a product decision
  (which hat?) and belongs with the caller, not in the reader.
- **LZMA-wrapped `.gma` was tested synthetically** (the test compresses the fixture both
  ways); no workshop download of that shape was available offline.
- **`dt`-bearing or animated models** are out of scope as before: this reader is for
  geometry, bones and materials, and no animation data is parsed.
- The 4 skipped `sourcepp` tests need the optional wheel; CI does not install it, so the
  second-opinion path is exercised on dev machines only.
