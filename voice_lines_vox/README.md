# Payday 2 Voice Lines — rb21 = Hila

Saved from: https://docs.google.com/spreadsheets/d/1m0LBg2PKpB-bnWfOFj40AglCI1dLmAHLH3ydi3Y7uz8/edit?gid=0#gid=0

This folder archives the community voice-line tables referenced by Payday 2 modders.

## Contents

- `heister_voice_ids.md` — General callouts table (g/p/v/f/d/s prefixes) from the main spreadsheet tab (gid=0). This is the sheet used for `managers.player:local_player():sound():say("xxxx",true,true)` and Pocorose / Basic Voices keybinds.
- `hila_rb21_quotes.md` — Full text transcript for **rb21 = Hila** from `payday.fandom.com/wiki/Hila/Quotes` (CC-BY-SA).
- `robbers_mission_gen_hila_ids.csv + hila_regular_vox.csv/.md (new, full regular_vox bank)` — Extract of **Hila rows** from Waitin' For a M8's `robbers_mission_gen` spreadsheet (https://docs.google.com/spreadsheets/d/196bzO0M-VAmtjd7V2MT2I0r3ELik4BTL8SGZDFFAZvA) - numeric stream IDs that map to `soundbanks/streamed/char_hila/` or `regular_vox` depending on era.
- `sources.md` — Where each bank lives on disk.

## Why rb21?

From `wiki.modworkshop.net/books/payday-2-mod-creation/page/extracting-sounds` Voiceline switches table:

| Character | Voice |
|---|---|
| Dallas | rb4 |
| Wolf | rb3 |
| Chains | rb1 |
| Houston | rb2 |
| John Wick | rb6 |
| Hoxton | rb5 |
| Clover | rb7 |
| Dragan | rb8 |
| Jacket | rb9 |
| Bonnie | rb10 |
| Sokol | rb11 |
| Jiro | rb12 |
| Bodhi | rb13 |
| Jimmy | rb14 |
| Sydney | rb15 |
| Rust | rb16 |
| Scarface | rb17 |
| Sangres | rb18 |
| Joy | rb19 |
| Ethan | rb20 |
| **Hila** | **rb21** |
| Duke | rb22 |

`rb21` is the Wwise switch value for Hila. Her `regular_vox` spreadsheet is archived at `modworkshop.net/mod/47714` (Snoozeds — Hila regular_vox voicelines spreadsheet) and her `robbers_mission_gen` entries at the sheet above.

## On-disk layout

After bundle extraction:

```
soundbanks/streamed/regular_vox/<numeric_id>.english.stream   # OG crew (Dallas, Chains, Wolf, Hoxton, Houston share this)
soundbanks/streamed/char_<name>/<numeric_id>.english.stream   # From Jacket onward: char_jacket, char_dragan, ..., char_hila (if present)
soundbanks/streamed/robbers_mission_gen/<numeric_id>.english.stream
soundbanks/streamed/safehouse_vo/<numeric_id>.english.stream
soundbanks/*.bnk  -> events like Play_ban_b02c -> random containers -> .stream files
```

Use `wwise_ima_adpcm.exe -d_all` to decode, or Wwiser + vgmstream + wwnames.txt to generate TXTPs as per the Extracting & Locating Specific Sounds guide.

Sources: ModWorkshop Voice Over Modding guide, Extracting Sounds guide, Basic Voices spreadsheet (ID 1m0LBg2PKpB-bnWfOFj40AglCI1dLmAHLH3ydi3Y7uz8), Payday Wiki Hila/Quotes, UnknownCheats CharTweakData dumps for speech_prefix tables.
