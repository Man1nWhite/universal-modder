# Sources & File Map

## Primary spreadsheet (requested URL)
https://docs.google.com/spreadsheets/d/1m0LBg2PKpB-bnWfOFj40AglCI1dLmAHLH3ydi3Y7uz8/edit?gid=0#gid=0
- Title: "Payday voice IDs for use as Pocorose replacements or manual keybinds"
- Tabs fetched via gviz: gid=0 (Heister Voice IDs), gid=674215167 (Special Units), gid=1022978531 (Heist Specific - partial), gid=1978302558 (duplicate dump)
- Canonical copy also referenced at: http://download.paydaymods.com/mods/447 (Basic Voices Reborn) and https://modworkshop.net/mod/33438 (Radial Menu Vocalizer)

## Hila-specific references
- Payday Wiki: https://payday.fandom.com/wiki/Hila/Quotes (full transcript, CC-BY-SA) — extracted to hila_rb21_quotes.md
- ModWorkshop: https://modworkshop.net/mod/47714 — Snoozeds "Hila regular_vox voicelines spreadsheet" (template, categories not fully useful; points to Waitin' For a M8 for robbers_mission_gen)
- Spreadsheet ID 196bzO0M-VAmtjd7V2MT2I0r3ELik4BTL8SGZDFFAZvA gid=1280565535 — robbers_mission_gen numeric IDs with "Who" column (Hila rows extracted)
- Wiki guide confirming rb21: https://wiki.modworkshop.net/books/payday-2-mod-creation/page/extracting-sounds (Voiceline-related switches table: Hila = rb21)
- Additional context: https://modworkshop.net/mod/47758 — "(Audio) Payday 2 Hila replaces Pearl" — maps 736 Pearl lines to Hila with spreadsheet

## Hila regular_vox (new, rb21)
https://docs.google.com/spreadsheets/u/0/d/1c3uXGyH5wRb7J1BH__cFEwXcxKgPiKuvGWGuRu-NCv4/htmlview
- ID 1c3uXGyH5wRb7J1BH__cFEwXcxKgPiKuvGWGuRu-NCv4 — tab "Hila regular_vox" (gid=0, 7 gviz chunks, 887 lines + header: PD2 ID | Speech | Category) saved as hila_regular_vox.csv + hila_regular_vox.md
- Bank confirmed: regular_vox, not robbers_mission_gen — each PD2 ID maps to soundbanks/streamed/regular_vox/<id>.stream + .wem/stream via Wwise Event switch robber=rb21

## Engine / Lua tables
- `lib/tweak_data/charactertweakdata.lua` — speech_prefix_p1/p2/count per enemy (cop l1n_, gensec l, bulldozer bdz_, medic mdc_, etc), chatter presets
- `lib/units/enemies/cop/copsound.lua` — CopSound:say builds prefix + sound_name (e.g. "hlp" -> "l1n_hlp"), syncs via SoundDevice:string_to_id
- `lib/tweak_data/customsafehousetweakdata.lua` — heisters.<name>.voice = get_voice(tweak_data, "<voice_id>"), events like Play_{voice}_idle_phone
- Soundbanks: Wwise 2013.2.10, events -> actions -> objects -> audio (embedded or streamed .stream/.wem). Searching: Wwiser gviz TXTPs named `EVENT [switch=value] {rVARIATION} {l=en}` list audio/<id>.wem -> maps to soundbanks/streamed/<BANK>/<id>.stream
