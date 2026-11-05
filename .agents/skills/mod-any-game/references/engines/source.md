# Source (1) and Source 2

## Source 1 (Half-Life 2, Portal 2, TF2, L4D2, Garry's Mod, CS:S...)
**Identify.** `<mod>/gameinfo.txt`, `*_dir.vpk`, and `bin/engine.dll`.
- **Content without code:**
  - `custom/` or `addons/` folders take loose files or VPKs that override by path;
  - maps with Hammer (`.vmf` → vbsp/vvis/vrad → `.bsp`);
  - models via Crowbar (decompile/compile `.mdl` with `.qc`);
  - materials `.vmt`/`.vtf` via VTFEdit.
- **Scripting:**
  - VScript (Squirrel) in Portal 2, L4D2, TF2 and CS:GO-era games: `scripts/vscripts/*.nut`, entity
    I/O;
  - Garry's Mod: Lua addons (`lua/autorun/...`);
  - SourceMod + Metamod:Source for **servers you run** (plugins in SourcePawn).
- **Garry's Mod specifically.** It is Source 2013 plus a Lua layer, and its addons are not VPKs:
  - `addons/<name>/` is an unpacked addon: `addoninfo.txt` in the old KeyValues form, or
    `addon.json` for anything packed by `gmad`. Loose files override the game's by path.
  - `steamapps/workshop/content/4000/<id>/<id>.gma` is a subscribed workshop item. `.gma` (GMAD
    v1-3) is a thin container around ordinary Source files, and it ends with a CRC32 of itself;
    some workshop downloads are LZMA-wrapped and have to be decompressed before parsing.
  - `lua/autorun/` (plus `lua/autorun/client/` and `lua/autorun/server/`) runs on load; anything
    else under `lua/` needs `require`. Realm matters: a client hook that touches `LocalPlayer()`
    crashes the server realm, and vice versa.
  - `addon.json` can list `ignore` globs, which is how server-only files are kept out of what
    clients download. A `.gma` can also declare **required content** (`"half-life 2"`): without
    that game mounted in GMod's Games menu the addon renders broken while every file is present.
  - Native code arrives as a module Lua `require`s (a `.dll` in the addon), which is how
    in-process C++ like libsm64 reaches the game. GMod has no VAC on servers you host, but a
    workshop addon shipping a DLL is still a trust decision.
  - Measuring an addon without extracting or rendering it: `python tools/pd2-las/inspect_gma.py
    <id>.gma` for rig/geometry, `inspect_textures.py <folder|zip|vpk|gma>` for whether every
    material's `.vmt`→`.vtf` chain actually exists and decodes. Never commit the assets.
  - Writing one: `gmad.exe` packs (`addon.json` + its `ignore` globs, and a whitelist that rejects
    stray file types), `gmpublish.exe` uploads — but publishing needs Windows and a signed-in Steam
    client, so an agent can prepare an addon and never upload it. Lint the Lua first with `glualint`
    (GLuaFixer): GMod's dialect rejects ordinary Lua in ways the game only tells you at load, and
    `SERVER`/`CLIENT` realm mistakes are invisible until something runs in the wrong realm.
  - Fetching one on a headless box: `steamcmd +workshop_download_item 4000 <id>` or `pip install
    steamctl` (pure Python, and `steamctl workshop info` describes the item before you download it).
- **Code:** Source SDK 2013 (github.com/ValveSoftware/source-sdk-2013) builds your own mod (a new game
  folder under `sourcemods/`). It's the official, fully legal route for new mechanics in HL2-era games.
- **Browse:** VPKEdit (cross-platform) or GCFScape (Windows/.NET, the GUI over HLLib) to open VPKs,
  including multi-chunk `*_dir.vpk` + `*_000.vpk` sets; for models, Crowbar; for maps, BSPSource.
  Neither browse tool opens Garry's Mod's `.gma` — that needs `gmad`/`gmpublisher` (see above).

## Source 2 (CS2, Dota 2, Half-Life: Alyx, Deadlock)
**Identify.** `game/bin/win64/engine2.dll` and `game/<mod>/gameinfo.gi`.
- **Official tools:** the Workshop Tools DLC (Hammer 2, Material Editor, ModelDoc, Particle Editor). Addons
  go in `game/<mod>_addons/<addon>/`, and `-tools` launches the editors.
  - Half-Life: Alyx: VScript Lua.
  - CS2: map workshop and VScript successors. Check the current state; Valve changes it.
  - Dota 2: custom games (Lua + Panorama UI).
- **Read assets:** Source 2 Viewer / ValveResourceFormat (VRF) decompiles `_c` resources: models, maps,
  textures, even collision. `um`'s authors used VRF to export CS2 map collision for a movement clone.
  Derived data stays out of git.

## Rules
- VAC: modified clients on VAC-secured servers get banned. Test with `-insecure` on a local listen server
  and never inject into CS2/Dota/Deadlock/TF2 on official matchmaking.
- The Workshop, maps, custom games and VScript are the sanctioned routes for the multiplayer titles.
- Demos (`.dem`) are a great oracle for gameplay work. DemoFile.Net and the demoparser libraries extract
  per-tick state.
