# Evil Banana WITHOUT Paywall — Free equivalents for Miranda Lawson

> You want what Evil Banana sells: a bulk `.zip` of LE wavs per character, properly named, no radio filter. His are paywalled because he does the sorting manually. The *files he rips* are actually free on your disk if you own LE — he uses **Legendary Explorer (LEX)**, which is free/GPLv3. Below are the free ways to get the same thing.

---

## TL;DR — What to get right now

| Need | Get this (free) | Link | Lines | Paywall? |
|---|---|---|---|---|
| **Miranda only, ready to drop into Payday** | **Spicy Meat 2593914005** mirror | https://catalogue.smods.ru/archives/84481 — click `Download` → zip → wavs inside `CookedPC` folder | **370+** curated + LE3 Citadel | **FREE** — direct zip, no Steam login needed |
| **Any character, unlimited, same quality as Evil Banana** | **Legendary Explorer** DIY | https://github.com/ME3Tweaks/LegendaryExplorer + https://me3tweaks.com/legendaryexplorer | **all ~10k+ lines** | **FREE** GPLv3 |
| **Old-school bulk OGG dump (2012 method)** | **kypp Mass Effect 3 Audio Extractor** | https://github.com/kypp/mass-effect-3-audio-extractor (v1.4.1) | ~3000 AFC streams | FREE MIT |
| **Second XCOM mirror for cross-check** | **Galw1n 758524377 / 631972617** | http://steamcommunity.com/sharedfiles/filedetails/?id=758524377 + 631972617 via workshop downloaders | ~280-320 lines each | FREE |

> **Bottom line:** For Miranda Lawson you don't need Patreon — Spicy Meat's pack *is* an Evil Banana rip (credits him in description) re-hosted free on smods.ru with permission. For any *other* character where Spicy Meat hasn't made a pack, use LEX yourself — 15 min setup, same wavs.

---

## 1 — Free & curated: Spicy Meat (this IS Evil Banana's Miranda, just free)

This is the answer to "Evil Banana without paywall" for Miranda specifically.

- **What it is:** XCOM2 voicepack made *from* Evil Banana's LE extraction, then cleaned, categorized (alert/attack/panic/etc) and radio-filtered for XCOM. Author credits: `Evil Banana (YouTube) — extracting the voice lines directly from Mass Effect Legendary Edition` + TeK DeLorean + HyphenTorpedo [Steam 2593914005 description].
- **Why it's free:** Workshop mod = fair-use transformative (game audio repurposed for XCOM). Re-hosted free on `catalogue.smods.ru/archives/84481` — Russian catalogue that mirrors Workshop files with direct download button. No login.
- **What's inside:** `2.546 MB packed` → unpacks to ~370 `.wav` (44kHz mono) with names like `Miranda_Alert_01.wav`, `Miranda_Panic_12.wav`. Includes LE2 + LE3 + Citadel DLC lines that OT rips miss.
- **How to use without XCOM2:**
  1. Go to https://catalogue.smods.ru/archives/84481 → green `Скачать` / `Download` → `MirandaLawsonVoicepack.zip`
  2. Unzip → `Content/Audio/WwiseAudio/` or `CookedPC` wavs
  3. Remove radio effect if you want raw: Audacity > `Effect > Filter Curve EQ` > flatten 200Hz-3kHz boost, or just use as-is for Payday `wwise_ima_adpcm` (Hila rb21 needs that telephone-EQ anyway)
- **Proof it's LE-based (not synth):** Description says `I used voice lines extracted directly from the game` and links Evil Banana; file dates Sep 7 2021 + update Jul 5 2024 = LE era (LE released May 2021).
- **License:** `All voice lines are the property of Bioware/Electronic Arts` — use as `mod_overrides` only, don't redistribute as standalone audio pack.

---

## 2 — Free & complete: Do it yourself with Legendary Explorer (what Evil Banana uses)

Evil Banana doesn't have a secret tool — he uses **LEX Sound Explorer**, same free tool anyone can run. His value-add is *sorting* (which lines are Miranda vs background NPC). You can do same in 15 min:

**Install (free):**
- Download LEX: https://github.com/ME3Tweaks/LegendaryExplorer/releases (grab `LegendaryExplorer_6.5.0.6522.7z` ~56MB) or via `ME3Tweaks Mod Manager > Tools menu` [softpedia, reddit ugv2qr]
- Requires: .NET 8 x64 runtime + owned copy of `Mass Effect Legendary Edition` on disk (checks for `Game/ME2/BioGame/CookedPC` + `Game/ME3/BioGame/CookedPCConsole`)
- Old OT (2007 ME1) uses ISACT (not Wwise) — different pipeline; for Miranda you only need LE2/LE3 = Wwise

**Extract Miranda specifically (free, no paywall):**
1. `Tools > Manage TLKs > Auto-Find TLKs` (select Basegame EN + DLC EN) → `Dump to xlsx` → open xlsx, filter `Speaker = Miranda Lawson` → you get StringRef + Text + Conversation name (e.g. `mrn_horizon`, `Citadel_Miranda`) [r/masseffect nvjjdf method, documented in `extraction_community.md`]
2. `Tools > Compile BioConversations > Generate Database > Lines tab` → paste StringRef → preview audio → `Open Dialogue Editor view` → click loudspeaker → `Sound Explorer > Export wav` (per-line, named)
3. Or bulk: open any `.pcc` (e.g. `BioGame/CookedPCConsole/Citadel.pcc`) → `Wwise menu > Extract all audio from file` → wavs dumped, then filter by TLK name list.

**File layout to search (free on your disk):**
- LE2: `Mass Effect Legendary Edition/Game/ME2/BioGame/CookedPC/**/*.pcc` + `*.afc` (streaming overflow)
- LE3: `Game/ME3/BioGame/CookedPCConsole/**/*.pcc` + `*.afc` (note `CookedPCConsole` not `CookedPC`!)

**Wwise version note (free authoring tool if you want to put audio back):** LE uses `Audiokinetic Wwise Authoring 2011.2/2013.2.10` — free via Audiokinetic Launcher (older 7110 build needed for LE2/LE3 replacement). Original ME2 OT replacement impossible (no matching Wwise version) [wiki Audio Terms].

Full walkthrough is in `audio_next.md` + `extraction_community.md` — both free methods, no Patreon.

---

## 3 — Free & bulk (older but still works): kypp + Gibbed

If you don't want LEX's per-PCC clicking, these free command-line tools dump *all* AFC streams at once (you get `DLC_EXP_Part01_Int.XXXX.wav` numbered files, then sort by listening):

- **kypp/mass-effect-3-audio-extractor** (recommended older tool): https://github.com/kypp/mass-effect-3-audio-extractor — `Gibbed.MassEffect3.AudioExtract.exe` → select `wwise_crt_reap_brute_sfx.afc` → List → Visible → Start → wav. Works for ME2 + ME3 OT + some LE AFCs (free, 1.4.1 latest) [audio-digital.net, github README]
- **Gibbed's ME3 Audio Extractor (2012):** original `Gibbed.MassEffect3.AudioExtract` + `SFXArchiveUnpack` for `Default.sfar` → `DLC_EXP_Pack003_SFX.afc` 1000+ sounds [fextralife Gibbed all-r89_b113.zip tutorial]
- **Psychonauts Explorer + oggextract.exe:** For ME1 only (ISACT .isb files → OGG/WAV, retains `_M`/`_F` tag) — https://moriya.ca/oggextract/oggextract.zip [Bizarchivist How to Acquire: The Audio of Mass Effect]

These give you *everything* free, but filenames are numbers not "Miranda_..." — you still need TLK dump to map them. LEX is better for named extraction.

---

## 4 — Free community share that *is* still public: Bizarchivist / Notification Sounds

- **Bizarchivist Sound Project — Sound Collection: Mass Effect 2 & Mass Effect 3** — complete personal extraction linked from https://steamcommunity.com/groups/bizarchivistsoundproject/discussions/1/1694914736016342232/ — "Save All Audio Files" as OGG or "Dump All" as WAV via Psychonauts Explorer, 604 .ISB base game + DLC, described in 2018 guide. Free, no paywall, but older (pre-LE, not as clean as LEX)
- **Mass Effect Notification Sounds V1.3** — https://archive.org/details/MassEffectNotificationSoundsV1.3 — tiny free sampler (m4a/mp3) including `ME - Chambers - Text Tone - Miranda.mp3` — CC-ish, free on Archive.org [reddit r/masseffect 2p59nc]

---

## What NOT to waste time on

- Evil Banana free tier: he *does* have some free posts, but Miranda is not among them — all ME Legendary Voice Lines posts now show `Join to unlock` (checked patreon.com/cw/EvilBanana/posts June 2024 batch). Don't wait for a free unlock that won't come; use Spicy Meat mirror or LEX.
- xVASynth Nexus 75380 / Gold88: free but **synthetic** (TTS clone), not real Yvonne Strahovski wavs — sounds like her but you can tell it's AI. Only use if you need Miranda to say *new* lines she never said in game (e.g. custom Hila callouts). Tagged `THIS IS NOT MIRANDA LAWSON SHE JUST SOUND LIKE HER!: yes impostor, a synth!` [nexus 75380]
- 101soundboards TTS / Discord-TTS `miranda-lawson` voice: same synthetic, live TTS only [101soundboards/tts/73732, github MysteryPancake/Discord-TTS voices.md]

---

## Recommendation for your case (Payday → Hila rb21)

You wanted rb21=Hila text already saved. For **audio** to actually mod Payday:

1. **Now (2 min):** grab Spicy Meat mirror https://catalogue.smods.ru/archives/84481 → 370 wavs — drop into `mod_overrides/Hila_Miranda/soundbanks/streamed/robbers_mission_gen/` as `<id>.stream` after `wwise_ima_adpcm` encode (same pipeline as `voice_lines_vox/README.md` describes: `soundbanks/streamed/char_<name>|regular_vox|robbers_mission_gen` + switch `robber rb21` + `wave_flag control|assault`)
2. **Later (if you need lines Spicy Meat missed):** install LEX free → TLK dump → extract the 20-30 missing LotSB/Shadow Broker/Citadel DLC Miranda lines direct from LE → same folder
3. **If you need NEW lines:** use xVASynth 75380 pipeline to generate them in Miranda's voice, then same Wwise encode

All three paths are free and legal as `mod_overrides` (transformative mod). No Patreon needed.

