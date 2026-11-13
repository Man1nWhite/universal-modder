---
kind: technique
title: "Garry's Mod and Source addon tooling: what runs headless, what needs Windows"
status: working
agents: ["Arena.ai agent"]
humans: []
date: 2026-11-05
links: []
tags: [source-engine, garrys-mod, gma, vpk, vtf, mdl, smd, workshop, tooling-survey, sourcepp, crowbar]
---
# Garry's Mod and Source addon tooling: what runs headless, what needs Windows

> A subscribed Garry's Mod, SFM or L4D2 addon is a thin wrapper around Source assets, so it can be measured
> from its own files instead of guessed at from its workshop page. This note records how that is done in
> plain Python (no Steam client, no Windows, no Blender) and a survey of the tools around the formats: which
> ones run headless on Linux, which ones need Windows, and what each adds.

## When to use it
- Someone names a workshop addon as a possible model source and the question is what is really in it: which
  models, how many bones and triangles, which rig, whether every material's texture is there.
- You are choosing a tool for `.gma`, `.vpk`, `.mdl`, `.vtf` or `.bsp` work and want to know before
  installing it whether it can run in a headless Linux sandbox, and under which licence.
- You need to hand rigged Source geometry to a human with Blender and do not have Blender yourself.

Everything below was written inside one repository: the readers are `tools/pd2-las/gma.py`, `vpk.py`,
`source_model.py`, `vtf.py`, `smd.py` and the two inspectors next to them, and "this repo" in the verdict
columns means that repository's Linux sandbox. The survey is dated **2026-11-05**; tool versions, licences
and maintenance status are as found on that day.

## How

### Measure the addon instead of reading its description

A workshop addon is a `.gma`, and a `.gma` is a thin wrapper around Source
assets this repo already reads — so an addon can be *measured* rather than
guessed at from its description:

```sh
# after subscribing, the archive is in
#   steamapps/workshop/content/4000/<item id>/*.gma
python tools/pd2-las/inspect_gma.py path/to/<item id>.gma --json build/report.json

# the same questions for an unpacked addon folder (addons/<name>/), a legacy
# zip, or a VPK — including whether every material's texture is really there
python tools/pd2-las/inspect_textures.py path/to/<addon folder>
```

The report gives the file tree grouped by extension, the required-content mounts
the addon declares, a warning if the trailing archive CRC no longer matches
(truncated or hex-edited after packing), then per model: vertex and triangle
counts, material names, and the skeleton split into *already mapped* /
*Source-only* / *unknown* against `skeleton_map.json`. That is what decides
whether an outside port is a cheap reference (a `ValveBiped` rig half-covered by
the existing map) or new work. Nothing is extracted or rendered: the addon is
someone else's licensed content, so private inspection only.

### Tell the three on-disk shapes apart

Three GMod shapes have to be told apart, and the readers now cover all three:

| on disk | what it is | reader |
| --- | --- | --- |
| `addons/<name>/…` | an **unpacked** addon (workshop items someone extracted, and the layout `gmad` packs from) | `inspect_textures.py <folder>` |
| `<id>.gma` in `steamapps/workshop/content/4000/<id>/` | the packed addon; LZMA-wrapped when Steam compressed the download | `inspect_gma.py`, and `inspect_textures.py` too |
| `addons/*.zip` / `.vpk` | the pre-2013 download format, usually one wrapper folder deep | `inspect_textures.py` |

### The readers

| File | What it does |
| --- | --- |
| `gma.py` | Garry's Mod `.gma` reader (GMAD v1–v3; unwraps the LZMA payload Steam sometimes serves; JSON description unpacked; required-content list kept; per-file **and** trailing archive CRC32 checked; `dx90`/`vtx`/`dx80`/`sw` VTX variants; traversal-safe) |
| `inspect_gma.py` | report a subscribed workshop addon: file tree by extension, declared required content, a damaged-archive warning, every model's verts/tris/materials, **bone names** and how much of the rig `skeleton_map.json` already covers. Textures are explicitly *not* its job — it says so and points at `inspect_textures.py` |
| `smd.py` | **SMD read/write** (`parse_smd`, `write_smd`, `ModelData` ↔ SMD with exact quaternion↔Tait-Bryan conversion) + stub `.qc`; CLI exports `.gma`/`.vpk`/`.zip` → per-model `.smd` for Blender |
| `inspect_textures.py` | follow every material a model names to its `.vmt` → `.vtf` inside a `.gma`/`.vpk`/`.zip`/**unpacked addon folder**, report present/missing with real size + mip count, and prove each texture actually **decodes** (optional second opinion from `sourcepp`; no Pillow reports `?` rather than a false ✗). Reads `addoninfo.txt` (GMod and L4D2 spellings) and `addon.json` |

### Getting an addon in, and geometry out

Two conclusions. **Acquiring** an addon needs nothing new: `steamcmd +login
anonymous +workshop_download_item 4000 <id> +quit` lands the `.gma` in
`steamapps/workshop/content/4000/<id>/` for a free app like GMod, and that is the
only reliable route for an item whose workshop page has been delisted.
`steamctl` (in the table above) does the same from `pip`, and can read the item's metadata
first — cheaper when the question is "is this the business suit, and is it worth
downloading at all?". **The
writing gap is closed** by `smd.py` (pure Python, no Blender needed): rigged
geometry leaves this repo as SMD, which Crowbar, Blender Source Tools and SourceIO
all import, and which the Windows side can turn into an FBX/GLB for the existing
GLB retarget if a `.model` route is preferred later. What is still missing is only
*compiling* back to Source (studiosmdl, Windows) — irrelevant here, because the
target engine is Diesel, not Source. The retarget path is unchanged: Source mesh →
`ModelData` → `transfer_group` → Diesel.

## The tool landscape

Surveyed 2026-11-05 for "what else deals with GMod mods", with the verdict that
matters here — can it run in this repo, and does it add something the existing
readers do not:

| tool | what it covers | licence / platform | verdict for this repo |
| --- | --- | --- | --- |
| [`sourcepp`](https://pypi.org/project/sourcepp/) (`vpkpp`, `vtfpp`, `bsppp`, `kvpp`) | **GMA v1-3, VPK v0/v1/v2/v54, BSP, VTF 7.0-7.6**; read *and* write for the pack formats. **No `mdlpp` in the Python wheel** — `mdlpp` exists as a C++ header (`include/mdlpp/`), the wheel binds only `bsppp gamepp kvpp sourcepp steampp toolpp vcryptpp vpkpp vtfpp`, so MDL parsing is not reachable from Python | MIT, C++20 + nanobind wheels | **the one worth having.** Installed and verified (2026-11-05): decodes a real DXT5 VTF from the tracked L4D2 pack and agrees with `vtf.py` pixel-for-pixel (max abs diff 1 = DXT rounding), and its GMA reader agrees with `gma.py` on the file list and CRCs — **except on required content**: `GMA::open` reads that list as one string, so any addon that actually declares a mount ("half-life 2") comes back with an empty name and a mangled entry path (`ame`), while `gma.py` loops to the empty terminator. Use it as a second opinion, not as the oracle. Optional dev-only cross-check; not a project dependency |
| [`gma`](https://github.com/diogo464/gma) (Rust crate) | read **and write** `.gma`, **including the LZMA-compressed workshop form** the Rust author documents as "Garry's Mod can't read compressed gma files but some, downloaded directly from the Steam workshop, are lzma compressed" | MIT | the only other implementation found that handles the compressed download; not usable from Python here, and `gma.py` covers the read half |
| [Crowbar](https://github.com/ZeqMacaw/Crowbar) | MDL → SMD/QC/QCI/VTA/VRD and back via `studiomdl`; unpacks VPK/GMA | free, closed source, **Windows only** | **not needed for measurement**, and it cannot run here. Still the standard answer if a human wants SMD/QC in Blender |
| [Blender Source Tools](https://github.com/Artfunkel/BlenderSourceTools) | SMD/DMX/QC import + export | open source, Blender 4.x | no MDL/VTF support by design, and it needs Blender, which this sandbox lacks |
| [SourceIO](https://github.com/REDxEYE/SourceIO) | **`.mdl` + `.vmt` + `.vtf` + `.bsp` direct import**, "Garry's Mod: full support" | MIT, Blender 4.0+ | the tool that skips Crowbar entirely — *if* a Blender existed here. Worth naming in a hand-off |
| GMad (`gmad.exe`) | create/extract GMA, publish | Valve, bundled with GMod | `gma.py` replaces the extract half on Linux; `vpkpp` can also **write** GMA if a repack is ever needed |
| [VPKEdit](https://github.com/craftablescience/VPKEdit) | GUI/CLI over `vpkpp`: VPK, GMA, BSP, VTF, ZIP | MIT | fine for humans, redundant with the readers above |
| [`srctools`](https://github.com/TeamSpen210/srctools) | VPK/VTF/BSP/VMF/DMX read+write, MDL partial, mount chains, `packlist` dependency resolution | **MIT** (the repo `LICENSE` excludes only libsquish; PyPI classifier says `License :: OSI Approved :: MIT License`) — an earlier revision of this table said GPL-3.0 and drew the wrong conclusion from it | usable, not vendored: nothing here needs `packlist` yet. Its idea (walk a map's or model's dependencies before declaring an addon complete) is the one thing worth re-implementing |
| [GCFScape](https://nemstools.github.io/pages/GCFScape.html) (Nem's Tools) | explorer-style browser for `.bsp .gcf .ncf .pak .sga .vpk .wad .xzp` — **not `.gma`**, not `.mdl` | freeware, **Windows/.NET** GUI on top of HLLib | **the wrong door for GMod**, right door for stock content: it reads multi-chunk `*_dir.vpk` + `*_000.vpk`, which `vpk.py` refuses by design and which is how L4D2 ships everything not in the addon. A human tool: no CLI, no scripting, absent from this sandbox. Its blind spot is the same one the community works around with `gmad`/7-Zip first |
| [HLLib](https://nemstools.github.io/pages/Miscellaneous-HLLib.html) 2.4.6 (Nem's Tools) | the library under GCFScape: BSP, GCF, NCF, PAK, **VPK v1/v2 incl. dir VPKs**, SGA, WAD, XZP, ZIP | **LGPL-2.1**, C and C++ API, **builds on Linux** | the only scriptable piece of Nem's Tools, and still not worth adopting: `vpkpp` (MIT, maintained, already our optional cross-check) reads the same VPKs *and* BSP *and* writes, while HLLib has had no release since 2017 and no MDL/VTF/GMA. Would earn its place only if a repo dependency on a C library were cheaper than a Python wheel — it is not |
| [VTFLib](https://nemstools.github.io/pages/VTFLib.html) + VTFEdit / [`VTFEdit Reloaded`](https://github.com/Sky-rym/VTFEdit-Reloaded) | VTF/VMT **read and write**: library (LGPL-2.1) plus a GPL GUI/CLI front-end; the Reloaded fork is the maintained one (v2.1.x, 2025 releases), original 1.3.3 is abandoned | LGPL-2.1 (lib) / GPL (apps), Windows/.NET front-end | the human-side answer to the gap in `vtf.py`, which is **read-only on purpose**: making a `.vtf` for an addon needs a writer — `vtfpp`/MareTF (MIT) inside the pipeline, or this by hand. Unchanged verdict for reading: `vtf.py` + `vtfpp` cross-check are enough |
| [Crafty](https://nemstools.github.io/pages/Crafty.html) / [VMEX](https://www.tophattwaffle.com/downloads/vmex/) (Nem's Tools, map side) | Crafty: HL1/HL2 `.bsp .mdl .vmf .map .rmf .gl` viewer + exporter; VMEX: Java BSP→VMF decompiler (up to L4D) | Windows/.NET (Crafty), Java (VMEX); VMEX superseded by [BSPSource](https://github.com/ata4/bspsrc) (open source, VMEX-based) | out of scope here — this is the **map** route, not the model/texture route. Crafty's own author says its `.vmf` export is brush-only and points at VMEX for decompiling; for maps `BSPSource` is the maintained choice, and it is already the one the Source engine playbook (`skills/mod-any-game/references/engines/source.md`) names |
| [MareTF](https://github.com/craftablescience/MareTF) / `vtex2` / `vtf2png` | VTF ↔ image converters, every VTF variant | MIT / libpng | redundant: `vtf.py` converts, and is bytes-checked against `vtfpp` |
| [`steamctl`](https://github.com/ValvePython/steamctl) (ValvePython) | `workshop search / info / download / subscribe`, depots, WebAPI — pure Python `pip install steamctl` | **MIT**, Python 3 | the acquisition tool this repo should reach for before `steamcmd` (streamed 0.9.5): same anonymous access, no 32-bit binary and `lib32gcc`, and `workshop info` answers "what is this item, how big is it" *before* spending the bandwidth. `steamcmd +workshop_download_item 4000 <id>` stays the documented route for a real server; [DepotDownloader](https://github.com/SteamRE/DepotDownloader) `-pubfile` is the self-contained .NET alternative |
| [GLuaFixer](https://github.com/FPtje/GLuaFixer) (`glualint`) | linter **and** pretty printer for GMod's Lua dialect — one Haskell binary, CI-friendly | **LGPL-2.1**, Windows/Linux binaries | the gap nothing else in this repo fills: GMod mods are half Lua and `um publish check` does not read Lua at all. Run it over `lua/` before `gmad` packs an addon; it also catches the realm mix-ups (`SERVER`/`CLIENT`) that cost a game launch to find |
| [LuaLS](https://github.com/LuaLS/lua-language-server) + [glua-api-snippets](https://github.com/luttje/glua-api-snippets) / [gmod-glua-ls](https://github.com/Pollux12/gmod-glua-ls) | type checking and IntelliSense for GLua from the scraped wiki API; the fork adds realm and net-message diagnostics | MIT-ish, editor-side | editor-side only, so nothing here can use it — but it is the answer when the work is *writing* a GMod addon rather than measuring one, and `gmod-glua-ls`'s realm analysis overlaps `glualint`'s |
| [`bsp_tool`](https://github.com/snake-biscuits/bsp_tool) (same author as VPKEdit/vpkpp) | Python `.bsp` library: Valve/Source branches, ENTITIES, PAKFILE (embedded materials/models), BSPX, plus a CLI | **MIT**, `pip install bsp_tool` | the map-side counterpart to `sourcepp`: nothing in this repo reads a `.bsp`, and when a GMod addon's content is *inside the map* (very common) this is how a Python agent gets at it. `bsppp` in the `sourcepp` wheel covers the same ground if a wheel is already installed |
| [HLMV++](https://developer.valvesoftware.com/wiki/HLMV%2B%2B) (ficool2) | the real engine's model viewer: renders a compiled `.mdl` with its `.vmt`/`.vtf` chain | freeware, **Windows**, bundled with Hammer++ | the **visual oracle** the Python readers cannot be: it shows a missing or wrong material as the pink checkerboard the game shows, where `inspect_textures.py` can only prove the file exists and decodes. Human-side, one launch |
| [Hammer++](https://ficool2.github.io/HammerPlusPlus-Website/) (ficool2) | Source 1 Hammer replacement, fixes the 2007 editor's crashes; GMod/L4D2 configs | freeware, **Windows** | only relevant if the route is **maps** — the same author ships HLMV++, so one download covers both. Not a model/texture tool |

### Round two: the rest of the field (same day)

| tool | what it is | verdict |
| --- | --- | --- |
| **SMD, written here** | `smd.py` — SMD is plain text, so the hand-off to Blender needs no tool at all | **closed the gap.** `python tools/pd2-las/smd.py addon.gma --out dir --qc` writes one `.smd` per model plus a stub QC. Verified against the tracked pack: 104 bones, 16,433 triangles, 6 materials, and every bind-pose rotation survives the text round trip to 1e-7 |
| [`bpy`](https://pypi.org/project/bpy/) | Blender 4.x/5.x as a `pip` wheel (`import bpy`, headless) | **tried, does not run here.** Installs, then dies on `libXrender.so.1` / `libXi` / `libGL`; `apt` can only reach a blocked mirror, so the libs cannot be added. It *would* give a real headless Blender on a normal Linux box |
| [gmpublisher](https://github.com/WilliamVenner/gmpublisher) | Rust+Tauri GUI **and CLI**: extract/publish GMA, bulk download, addon size treemap, no `gmad.exe` needed | the publishing half, and worth knowing *why* nothing here publishes: the sanctioned route is GMod's own `bin/gmpublish.exe` (Windows, `create`/`update`/`list`, icon must be a 512×512 JPG under 1 MB) which talks to a **running Steam client** — so it can never run in this sandbox or in CI. `gmosh` (FPtje) does the same from Python but its author states support has been dropped (last update 2023). `gma.py` covers reading |
| [Noesis](https://www.richwhitehouse.com/noesis/) | Windows GUI/CLI converter with **Source `.mdl` + VPK import** and a Python plugin API | Windows-only, so it belongs to the same bucket as Crowbar: a human-side tool, not something this repo can call |
| Linux `studiomdl` | Valve's compiler is Windows-only; Crowbar/`studiomdl` under Wine is the usual workaround | not worth it: the compile step is only needed to make a *Source* model, and nothing here builds one |

## Gotchas
1. **Symptom.** `sourcepp`'s GMA reader agrees with `gma.py` on the file list and the CRCs, but an addon that
   declares required content comes back with an empty addon name and a mangled first path. **Cause:**
   `GMA::open` reads the required-content list as one string instead of looping to the empty terminator.
   **Fix:** use `sourcepp` as a second opinion on bytes and checksums, never as the oracle for the header.
2. **Symptom.** A plan to parse `.mdl` through `sourcepp` from Python goes nowhere. **Cause:** `mdlpp` exists
   only as a C++ header; the wheel binds `bsppp gamepp kvpp sourcepp steampp toolpp vcryptpp vpkpp vtfpp`.
   **Fix:** read MDL/VVD/VTX with `source_model.py`, and keep `sourcepp` for VPK, GMA, BSP and VTF.
3. **Symptom.** A `.gma` straight from the workshop download folder does not start with the `GMAD` magic.
   **Cause:** Steam hands out some older workshop items as a bare LZMA stream whose contents are the
   `.gma`. **Fix:** test for the magic and decompress first; `gma.py` does, and so does the Rust `gma`
   crate.
4. **Symptom.** A library gets ruled out, or adopted, on the strength of a licence remembered from a table.
   **Cause:** an earlier revision of this survey listed `srctools` as GPL-3.0; it is MIT (the repository
   `LICENSE` excludes only libsquish). **Fix:** read the `LICENSE` file and the PyPI classifier yourself
   before a licence decides anything.
5. **Symptom.** `pip install bpy` succeeds and `import bpy` dies on `libXrender.so.1`, `libXi` or `libGL`.
   **Cause:** the wheel needs the X11 and GL system libraries, and a sandbox whose `apt` mirror is blocked
   cannot add them. **Fix:** do not plan on headless Blender there; write SMD with `smd.py` and let a
   machine that has Blender import it.

## Seen in
- `games/payday-2/las-armor-skin-outfit.md`: the L4D2 addon these readers were first written for.
- `techniques/reading-source-engine-models-and-animations.md`: the MDL, VVD, VTX and animation formats
  themselves.
- In the repository: `tools/pd2-las/README.md` (file map and commands), the tests `tests/test_gma.py`,
  `tests/test_inspect_textures.py`, `tests/test_smd.py`, `tests/test_source_model.py`, and
  `docs/audits/2026-11-05-gmod-tools-second-pass.md`, the audit that corrected this survey.
