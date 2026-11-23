# Hila "On me." for Call categories only — revert

> **Revert:** deleted `generic_on_me_for_all.csv` (888 rows all → On me) per request.
> **New:** `hila_call_on_me.csv` (888 lines: header + 887 IDs) — **only** `Call <Name>` categories (158 IDs, 20 names) become `On me.`; all other categories keep original Hila speech.

## What changed
- **Before (wrong):** all 887 Hila IDs → generic Miranda `norvx_starter_h_S_INT.001.ogg` "On me. / Follow me." — even pager/hostage/revive etc.
- **After (correct):** only `Call Bonnie` (8), `Call Sokol` (8), `Call Hoxton` (8), `Call Wolf` (8), `Call Jiro` (8), `Call Scarface` (8), `Call Rust` (8), `Call Dragan` (8), `Call Clover` (8), `Call Chains` (8), `Call Dallas` (8), `Call Duke` (7), `Call Ethan` (8), `Call Houston` (8), `Call Jimmy` (8), `Call Bodhi` (9), `Call Sangres` (8), `Call Wick` (8), `Call Sydney` (7), `Call Jacket` (7) → `On me.` (158 rows)
- **Kept original:** 729 other IDs (Hostage intimidate, Pager response, Direction, Inspire, Mark shield/dozer/taser, Reviving, Victory, etc.) — keep Hila's recorded line or use per-category Miranda mapping in `miranda_lawson/hila_to_miranda_mapping.csv` if you want Miranda VO.

## Why "On me." for Calls
- Hila `Call <Name>` are name-shouts ("Bonnie. Hey, Sokol! Hey, Hoxton!") — replace with generic Follow `On me.` (Hila IDs `1884286/2425875/29476265/36727215` are already "On me." in that category) so Miranda's `norvx_starter_h` "Come with me. Follow me." can be duplicated for any heister without recording 20 names.
- In Wwise this is `regular_vox/<PD2 ID>.stream` for each Call ID → all 158 now play same `norvx_starter_h_S_INT.001.ogg` "On me." via duplicate copy.

## How to install
```bat
rem 1. Convert Miranda generic "On me." (one ogg):
wwise_ima_adpcm.exe -e voice_lines_vox\miranda_lawson\Голос_Лоусон_flat\norvx_starter_h_S_INT.001.ogg temp.stream
rem 2. Copy only for Call IDs listed in hila_call_on_me.csv where New Speech="On me.":
for /f "skip=1 tokens=1 delims=," %i in (hila_call_on_me.csv) do (
  for /f "tokens=4 delims=," %n in ('findstr /c:"%i" hila_call_on_me.csv ^| findstr "On me."') do copy temp.stream mod_overrides\Hila_Miranda\soundbanks\streamed\regular_vox\%i.stream
)
rem Or simpler: read CSV and copy where New Speech="On me." (158 files)
```

> Full per-category Miranda variation stays in `miranda_lawson/hila_to_miranda_mapping.csv` + text-match `hila_to_miranda_textmatch.csv`; this file is the "generic On me for Calls only" fix.
