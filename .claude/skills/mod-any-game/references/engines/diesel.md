# Diesel 3: PAYDAY 2 (Starbreeze)

Starbreeze's in-house engine. PAYDAY 2 (`payday2_win32_release.exe`) is the only title with a real modding
scene; it moved from 32-bit to **64-bit** in 2024, and that move splits the toolchain in two. PAYDAY 3 is
Unreal Engine 4/5 and shares nothing with this.

## The two file layouts

- **`assets/<dlc>/….bundle`** — Diesel containers. Each is a header plus named sections; the game streams
  units, textures and models out of them. Legacy (32-bit) bundles and Diesel 3 / "DODB" (64-bit) bundles are
  different containers, and a reader needs both: `tools/pd2-las/dmodel.py`'s `DieselModel` handles legacy and
  DODB `.model` files, which is the same split one layer down.
- **Loose files in `mod_overrides/`** — a file here replaces the bundled one of the same hash64 path, with no
  loader installed at all. This is the cheapest mod that exists in the game: one file, no Lua, no hooks.

**Names are hashed.** Paths, unit names, materials and bones are 64-bit hashes (a Jenkins lookup3 variant,
`Hash64.cs` in payday2-model-tool). Without [PAYDAY-2-Hashlist](https://github.com/Luffyyy/PAYDAY-2-Hashlist)
in the tool's root, every export shows hash strings instead of names — put the hashlist in first, always.
When a name is still unknown, recover it by hashing candidates (`hash_str()` in `dmodel.py`) rather than
guessing.

## Routes, in the order to try them

1. **`mod_overrides/` replacement** — no loader, no Lua, works offline. The head-replacement packs in
   `dist/` are built this way.
2. **SuperBLT + BeardLib in `mods/`** — Lua, custom units, `PlayerStyle` outfits, menu entries. SuperBLT is
   a `IPHLPAPI.dll` proxy plus `wsock32.dll`; BeardLib lives in `mods/BeardLib`. This is the route when the
   mod has to *do* something, not just replace a file.
3. **LAS / MOOG outfit modules** — a third-party framework (Legendary Armour Skins) that registers an
   outfit as `assets/units/<unit>/skins/<skin>/` with a `.unit`, one `.object` per mesh, `material_config`
   files and `.texture` DDS. Read `knowledge/games/payday-2/las-armor-skin-outfit.md` and `docs/pd2-las/`
   for the full contract, including what the ModWorkshop guide actually prescribes.

## Tools

- **PAYDAY 2 Model Tool** (diesel-modding/payday2-model-tool, .NET) — `.model` in and out, the reference for
  the container format. Its guide warns that **64-bit-branch exports do not re-import** into the current
  Model Tool; treat it as a 32-bit-era tool for authoring.
- **Diesel Bundle Viewer** (legacy) and **Diesel Crate Browser** (64-bit) — browsing/extracting bundles.
- **SuperBLT** and **BeardLib** — the loader and the mod framework.
- In this repo: `tools/pd2-las/dmodel.py` (PYTHONPATH: `tools/pd2-las`) reads `.model`, `build_las_pack.py`
  builds a reproducible LAS pack, `tools/pd2-port/` holds the pack contract and the offline checks. There is
  no bundle writer here: authoring goes through Model Tool or a hand-built container.

## Verification and safety

- Everything is verifiable offline: pack checksums, material↔model hash sets, DDS mip chains, texture names
  in `material_config`, and a structural diff against a known-good reference pack. `tools/pd2-port/` does
  exactly that; make it pass before asking for a game launch.
- The game's anti-cheat is server-side: **do not** touch the client, install loaders or change the install to
  test a pack. An outfit or an override is safe to test offline in an offline heist; anything that hooks the
  client is not.
- The LAS route is a *registration* in the framework, not a character swap. Swapping a heister's model in
  place is the route that produced a "complete mess" mesh; the note above records that dead end.
