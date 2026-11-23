# Miranda Lawson — Who Actually Shared AUDIO (not just text)

> Fandom wiki text is everywhere, but *audio* shares are rarer — EA audio is copyrighted. The only public shares that survive are XCOM2 Workshop voicepacks (fair-use modding) and the extractor community's bulk rips (Patreon/Discord + GitHub tools). This file catalogs the posts that actually gave you wav/ogg.

---

## 1 — Extraction instructor (the source for everyone else)

### Evil Banana — YouTube + Patreon
- **Who:** Evil Banana — Mass Effect voice line archivist on YouTube (showcase videos) + Patreon
- **What he shared:** Full per-character zips for *Mass Effect Legendary Edition* ripped directly from PCC/AFC (LE2/LE3). Each post has video preview + `*.zip/.7z` with wavs.
- **Examples of his library (Patreon, search `Mass Effect: Legendary Edition - <Name> Voice Lines`):**
  - `Mass Effect Legion Voice Lines.zip` — https://www.patreon.com/posts/mass-effect-54984597
  - `Mass Effect EDI Voice Lines.zip` — https://www.patreon.com/posts/54780734
  - `Mass Effect Kaidan Alenko Voice Lines.7z` — https://www.patreon.com/posts/55667616
  - `Mass Effect Kasumi Voice Lines.zip` — https://www.patreon.com/EvilBanana/posts/mass-effect-55665895
  - `Mass Effect Thane Voice Lines.zip`, `Jacob Taylor Voice Lines.zip` etc (same template, replace name in URL)
  - All posts marked `Videos showcasing voice lines of game characters and SFX` + downloadable attachment [search results 3-10]
- **Miranda specifically:** Not a public free post (most recent posts are paywalled), but he *is* the credited extractor for Miranda:
  > **Spicy Meat**: `Evil Banana (YouTube) — extracting the voice lines directly from Mass Effect Legendary Edition` [catalogue.smods.ru/archives/84481, Steam 2593914005 description]
- **How he extracts:** LEX Sound Explorer / AFC → wav (see extraction_community.md). His rips are the rawest community source — no radio filter.
- **Access:** Patreon `patreon.com/EvilBanana` — some zips free, most behind `Join to unlock` (e.g. `Dylan Voice Lines.7z`, `Jesse Faden Voice Lines.7z` pattern). YouTube channel has preview compilations if you want to audition before joining.
- **YouTube demo for extraction method itself:** `How to extract the audio from Mass Effect 3` — https://www.youtube.com/watch?v=dHQysCbvpCw (302 Moved, old Gibbed tutorial, still valid for concepts) + his own `Yvonne Strahovski Interview - Mass Effect 2 (HD)` https://www.youtube.com/watch?v=fTWaov0Fn_8 as reference.

---

## 2 — XCOM 2 Workshop — the 3 public Miranda voicepacks (all XCOM2 → Payday/Hila pipeline reuses these)

These are the *only* large, curated, free Miranda wavs on the open web (~300-370 lines each, already cleaned, radio effect optional). All credit Evil Banana or direct PCC rips.

### A) Spicy Meat — current best (RECOMMENDED)

- **Workshop:** `2593914005` — `Mass Effect Miranda Lawson Voicepack (WOTC version)` — https://steamcommunity.com/sharedfiles/filedetails/?id=2593914005
  - **Mirror/catalog:** https://catalogue.smods.ru/archives/84481 (same description, file size 2.55 MB, Sep 7 2021, updated Jul 5 2024, last revision 28 Jul 2022 14:52 UTC)
  - **Author:** Spicy Meat (Steam Workshop, also `Spicy Meat's Workshop` collection — 59 voicepacks)
  - **Stats:** **370+ voice lines**, applied radio effect, 312 ratings ☆☆☆☆☆, 2.546 MB packed (wav → bnk), WOTC + War of the Chosen
  - **Quote from description:** `Miranda Lawson (wonderfully voiced by Yvonne Strahovski ... ) -- Features 370+ voice lines with an applied radio effect. I'm aware that there are already two other Miranda voicepacks on the workshop. I was actually inspired by them but chose to make my own since I used voice lines extracted directly from the game`
  - **Credits in description:** `TeK DeLorean — taught me XCOM modding`, `HyphenTorpedo — voicepack modding Q&A`, `Evil Banana (YouTube) — extracting the voice lines directly from Mass Effect Legendary Edition`, plus note about `DefaultModOptions.ini ActiveMods="MirandaVoicepack" / "MirandaVoice"` unbind fix.
  - **How to get audio without owning XCOM2:**
    1. Subscribe on Steam (needs Steam login) *or* use `steamworkshopdownloader.io / workshop.steamfunc.com / catalogue.smods.ru direct download` to fetch `.bin` → rename to `.zip` → `CookedPC` wav folder.
    2. Or fetch mirror `smods.ru/archives/84481` which rehosts the Workshop file (direct zip).
  - **Licensing note in description:** `All voice lines are the property of Bioware/Electronic Arts.`

- **Why this one for Hila/Payday reuse:** Biggest curated set, newest (LE-based), includes LE3 Citadel lines, clean filenames, radio filter easy to remove in Audacity (undo EQ).

### B) Galw1n — older LE2-based pack (the one Spicy Meat links)

- **Workshop:** `758524377` — `Miranda Lawson Voice Pack (Galw1n's Edition)` — http://steamcommunity.com/sharedfiles/filedetails/?id=758524377 (referenced as `Check out Galw1n's Miranda Voice Pack` in Kexx's WOTC Miranda Squadmate description [catalogue.smods.ru/archives/32550])
- **Seen in mod lists:** `WOTC Miranda Squadmate 1163123939` requires/recommends `Miranda Voice Pack (Galw1n's Edition) 758524377` [pastebin R3ZYbs2n]
- **Status:** Still listed in Steam collections (e.g. `WOTC Miranda Squadmate` page says *entire mesh reworked* May 24 2020, links to Galw1n). Not always visible due to Steam age gate, but downloadable via same downloader tricks.

### C) Original 2016 pack (the oldest)

- **Workshop:** `631972617` — `Miranda Lawson Voicepack` (often `MirandaLawsonVoicePack` internal name)
  - Seen in `Working Mod List - RealityMachina` (132. Miranda Lawson Voice Pack 631972617) [pastebin scd2NKFk]
  - Seen in `Scrap's Xcom mod list` (83. Miranda Lawson Voice Pack 631972617) [pastebin iCUgUmau]
  - Seen alongside `Me3 Miranda Squadmate 1163123939` + `Geralt voicepack 750528939` in Long War lists [pastebin CieKxLDQ]
- **Difference vs Spicy Meat:** Older rip (OT ME2/ME3, not LE), fewer lines (~280?), no radio fix notes. Useful as alternate take / cross-check for line presence.

### D) Companion squadmate mods that bundle Miranda voice + model

- `1163123939` — `WOTC Miranda Squadmate` by Kexx — https://steamcommunity.com/sharedfiles/filedetails/?id=1163123939 — full 3D head (physics hair update Oct 1 2016 thanks to Destroyer1101) + links to voicepacks above. Shows what XCOM modders pair Miranda audio with visually.

---

## 3 — Reddit / Discord / Forum posts where people *actually* handed you files or step-by-steps

| Date | Author | Where | What they shared | Link |
|---|---|---|---|---|
| 2012-07-16 | ozman51 | r/masseffect | `Mass Effect Notification Sound Archive (.M4A V1.0/1.2/1.3)` — .m4a notification tones including `ME - EDI - Msg from Lawson.m4a` (tiny Miranda snippet via EDI) + `*ME - EDI - Msg from Lawson.m4a`, `*ME - Chakwas - How May I Help You.mp3` etc — hosted on archive.org `MassEffectNotificationSoundsV1.3` | https://reddit.com/r/masseffect/comments/we8rc/mass_effect_notification_sound_archive_m4a_format/ + direct `archive.org/details/MassEffectNotificationSoundsV1.3` |
| 2014-10-14 | Sir_Cxyrtyx + PumaGranite | r/masseffect | `You can use ME3Explorer to rip the dialog sound files right out of the game` — step-by-step + offer `I don't have ME3 installed right now, but forums might extract for you` | https://reddit.com/r/masseffect/comments/2j8835/does_anyone_know_where_i_can_get_mass_effect/ |
| 2015-04-24 | Kinkojiro / Giftfish | ME3Explorer forums t1826 | `ME2 DLC Audio Extraction` — notes Gibbed only does base game, ME2 DLC is one AFC with 1547 unnamed `DLC_EXP_Part01_Int.XXXX.wav` (the pain of Miranda LotSB rips), crashes with `ww2ogg.exe`, Soundplorer also crashes — actionable for Miranda DLC hunters | https://www.tapatalk.com/groups/me3explorer/me2-dlc-audio-extraction-t1826.html |
| 2015-02-06 | me3explorer forum t1701 | ME3Explorer forums | `Audio MOD` — explains 3 Wwise categories (wav-in-PCC vs streaming AFC vs soundbank DATA) — needed to know *where* Miranda barks are (most dialogue = WwiseStream in PCC + AFC streaming) | https://www.tapatalk.com/groups/me3explorer/audio-mod-t1701.html |
| 2016-02-08 | Herobrine24 | r/masseffect | `Full ME2 subtitles and descriptions as txt` — txt dump of all TLK dialogue (all characters) + note `Gibbed's audio extractor` + `Psychonauts Explorer` for wav extraction workflow | https://reddit.com/r/masseffect/comments/44qs8l/full_me2_subtitles_and_descriptions_as_txt/ |
| 2021-06-09 | Herobrine24 | r/masseffect nvjjdf | `A dialog database for all the lines` — Dialogue Dumper → xlsx + Asset Database → Lines tab workflow (the canonical LEX method, described in extraction_community.md) | https://reddit.com/r/masseffect/comments/nvjjdf/a_dialog_database_for_all_the_lines_said_in_the/ |
| 2022-05-02 | alynnidalar | r/masseffect ugv2qr | `You need Legendary Explorer → Sound Explorer → open file → play/export individual sounds, Wwise menu > extract all audio from single file` + Discord `ME3Tweaks → #legendary_explorer` | https://reddit.com/r/masseffect/comments/ugv2qr/mass_effect_2_audio_files_extractor/ |
| 2022-08-04 | Chinese community | Steam Guide 2844561628 | `音乐、对话、音效解包` (Mass Effect LE audio unpack Chinese) — `afcextr` drag-drop + `ww2ogg --pcb packed_codebooks_aoTuV_603.bin` → ogg (Miranda AFCs work same) | https://steamcommunity.com/sharedfiles/filedetails/?id=2844561628 |
| 2023-03-05 | alynnidalar / Tajfun403 | r/masseffect 11j0ajl | `Is there any way to get specific sounds from ME2?` — LEX Sound Explorer + `SFXGame → Wwise_Generic_Foley`, `Startup_INT → Wwise_Weapons_Standard`, `Wwise_GUI_Generic` for UI (Miranda hurt barks share SFX pools) | https://reddit.com/r/masseffect/comments/11j0ajl/is_there_any_way_to_get_specific_sounds_from_me2/ |
| 2024-03-29 | super-gargoyle | r/MECoOp | MP files named `<race>_<class>_MP_LOC_INT.pcc`, need DLC Unpacker for `DLC_CON_MP*` (not Miranda MP, but same extraction path) | https://reddit.com/r/MECoOp/comments/1bqcdhm/me3_coop_voicelines/ |

---

## 4 — Synthetic / non-official shares (NOT real Yvonne, but community still posts)

- **xVASynth / SKVA Synth v3** — https://www.nexusmods.com/skyrimspecialedition/mods/44184 (xVASynth v3 - SKVA Synth) — Python + Torch TTS voice cloning toolkit. Community uses it to *synthesize* new Miranda lines.
- **Example synthetic Miranda voicepack:** `Miranda Lawson's sarcastic female voice set` by Gold88 — https://www.nexusmods.com/skyrimspecialedition/mods/75380 — 20+ files, `xVASynth-win32-x64CPU` TTS, `CustomVoice` folder install (`Data/Sound/fx/CustomVoice`), MCM `Player Voice Sets`. Tagline: `THIS IS NOT MIRANDA LAWSON SHE JUST SOUND LIKE HER!: yes impostor, a synth!` — useful if you want *new* lines in her voice, not rips.
- Companion mods: `Miranda - fire mage` (Bijin skin + Mirabella Ervin + xVASynth2 additional VO) https://www.nexusmods.com/skyrimspecialedition/mods/62327 — same synth pipeline.

---

## 5 — Where to get Miranda audio *right now* (ranked for your use case Payday → Hila)

1. **Fastest — XCOM pack (already curated, no LEX needed):** `catalogue.smods.ru/archives/84481` (Spicy Meat 2593914005) → 370 wavs with radio effect — strip filter in Audacity `Effect > Filter Curve` or just use as-is for Payday `wwise_ima_adpcm` encoding. Mirror has direct zip, no Steam login.
2. **Rawest — Evil Banana Patreon:** search `site:patreon.com/EvilBanana "Voice Lines"` — paywall but complete LE rips per character with proper TLK names (not just `Int.XXXX`).
3. **Full control — LEX yourself:** install LE + LEX per `audio_next.md` + `extraction_community.md` → dump TLK xlsx → target only Miranda's StringRefs → export wavs fresh. Best if you want *unfiltered* + *all* DLC (LotSB/Shadow Broker, Citadel, Leviathan) without waiting for someone else's upload.
4. **Synthetic — xVASynth 75380:** if you need Miranda to say things she never said (e.g. new Hila pager lines), clone with xVASynth v3.

All shares above note: `All voice lines are the property of Bioware/Electronic Arts` — use as mod-local `mod_overrides` only, don't redistribute as standalone audio pack.

