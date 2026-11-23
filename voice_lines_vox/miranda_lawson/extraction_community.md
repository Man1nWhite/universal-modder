# Mass Effect Voice Extraction — Real Community (NOT just fandom wiki)

Fandom wikis give you *text* transcripts. For actual **audio extraction** (Miranda Lawson wav/ogg) the Mass Effect modding scene did 10+ years of reverse engineering. This is the real community.

---

## 1 — ME3Tweaks — the hub (makers of all modern tools)

- **Site:** https://me3tweaks.com — mods, guides, Mod Manager, ModMaker, DLC database, LE Multiplayer
- **GitHub org:** https://github.com/ME3Tweaks — `LegendaryExplorer`, `ME3TweaksModManager`, `LEBinkProxy`, `Wwiser.NET`, `MassEffectLegendaryEditionRandomizer`
- **Main tool:** **Legendary Explorer (LEX)** — https://github.com/ME3Tweaks/LegendaryExplorer — GPLv3, ~30 tools: Package Editor, Dialogue Editor, Sound Explorer (Soundplorer), Asset Database, Sequence Editor, TLK Editor, FaceFX Editor, Live Level Editor. Successor to ME3Explorer (retired 2021). Supports OT (ME1/ME2/ME3) + LE (LE1/LE2/LE3) — 7 UE3 variants auto-resolved [blog modding].
  - Download: via **ME3Tweaks Mod Manager > Tools menu** (stable + nightly) or Nexus `me3tweaks.com/legendaryexplorer` / https://www.nexusmods.com/masseffect3/mods/674
  - Requires .NET 7/8 x64 + game installed (checks for ME1/ME2/ME3/LE files on disk)
  - Source nightly builds contain bleeding-edge fixes (e.g. Dialogue Dumper speed, Wwise 2013 parsing) [github releases]
- **Mod Manager (M3):** https://github.com/ME3Tweaks/ME3TweaksModManager — generates/installs `.m3m` merge mods + empty DLC mods, Starter Kit for blank mods. This is how you *install* mods; LEX is how you *make* them [me3tweaks wiki Getting Started].
- **Discord — THE live help desk:** `https://discord.me3tweaks.com` or https://me3tweaks.com/discord — `#legendary_explorer` channel for Sound Explorer/Dialogue Editor questions, `#resources` for wiki tutorials. Core devs **Mgamerz** (lead), SirCxyrtyx, Kinkojiro, HenBagle hang there [reddit ugv2qr alynnidalar].
  - Also private **Workshop** Discord for vetted mod devs.
- **Wiki (official tutorials):** https://github.com/ME3Tweaks/LegendaryExplorer/wiki
  - `Legendary Edition Modding: Getting Started` — terminology: PCC (= .pcc package), TLK (talk table, string ref), AFC (audio file cache — concatenated Wwise data, referenced by offset by WwiseStream exports), Wwise (ME2/LE2/ME3/OT3 audio middleware), ISACT (ME1/LE1 2005 Creative audio) [wiki Getting Started]
  - Tutorials: `Dialogue Editor Overview`, `FaceFX Principles`, `Redirecting/Replacing/Adding Audio to Conversations`, `Editing LE1 Audio with ISACT`, `How to add new audio to LE1 conversations`, etc. — community-written, linked in Discord #resources [wiki Home]

## 2 — What these tools do for Miranda specifically

| Goal | Tool | How |
|---|---|---|
| **Find every Miranda line with text + TLK id + conversation name** | **Dialogue Dumper** in LEX | Manage TLKs > Auto-Find TLKs (Basegame EN + DLC EN) > Dump to xlsx. Gives Speaker, StringRef, Text, Conversation, Game, File, Export # [r/masseffect nvjjdf Herobrine24] |
| **Link that text to its wav** | **Asset Database** | Tools > Compile BioConversations (after TLKs managed) > Generate Database > Lines tab — search by TLK StringRef, preview audio, switch male/female, open Dialogue Editor view [same post] |
| **See dialogue tree + conditions** | **Dialogue Editor** | Open .pcc (e.g. `Citadel.pcc`, `Normandy.pcc`), shows E/R lists, State Transitions, plot bools, FaceFXAnimSet cloning [tutorial Dialogue Editing t1471] |
| **Play/extract raw audio** | **Sound Explorer / SoundplorerWPF** | Open any `.pcc` > Wwise menu > Extract all audio from file > wavs. Or per-export loudspeaker icon in Dialogue Editor > Sound Explorer > Export wav [reddit ugv2qr, me3explorer Utilities] |
| **Bulk TLK management** | **TLK Editor + Batch Add String Range** | Bulk import/export TLKs (LE bulk support added 2024) [releases] |
| **Fix mouth movement** | **FaceFX Editor (with waveform graph)** | Clone FaceFX for new lines [releases] |
| **Replace Miranda audio back into game** | **Package Editor + Soundpanel + AFC Compactor** | Create AFC if needed, replace WwiseStream export, requires correct Wwise Authoring version (7110 via Audiokinetic Launcher). LE2/LE3 audio replacement supported; ME2 original not possible (no matching Wwise version available) [wiki Audio Terms, Nexus replacer thread] |

> **Key gotcha:** ME2 (original) dialogue replacement is effectively impossible without the exact Wwise version BioWare used; LE2/LE3 replacement *is* possible. Extraction works for both [wiki Audio Terms].

## 3 — File layout you will search (with LEX)

- **ME2 OT:** `Mass Effect 2/BioGame/CookedPC/**/*.pcc` + `CookedPCDLC/DLC_*/CookedPC/*.pcc` + `*.afc`
- **ME2 LE:** `Mass Effect Legendary Edition/Game/ME2/BioGame/CookedPC/**`
- **ME3 OT:** `Mass Effect 3/BioGame/CookedPCConsole/**/*.pcc` + `*.afc` (ME3 uses `CookedPCConsole` not `CookedPC`!)
- **ME3 LE:** `Game/ME3/BioGame/CookedPCConsole/**`
- **MP lines:** `<race>_<class>_MP_LOC_INT.pcc` (ME3 co-op) [r/MECoOp]
- **Miranda hot files:** `BioGame_SFXGame.pcc` (Wwise_Generic_Foley, Wwise_GUI_Generic), `Startup_INT.pcc` (Wwise_Weapons_Standard), `Normandy.pcc`, `NormandySR2_Miranda.pcc`, `Citadel.pcc`, `Sanctuary/Horizon.pcc`, `DLC_EXP_Part01*.pcc/.afc` (Citadel DLC = `DLC_EXP_Pack003*.afc` — Base has 1000+ sounds, other 600+ [Tutorial Extracting Citadel DLC]) [community notes yz4bl4, fextralife]

## 4 — Older/alternate community tools (still referenced)

- **Gibbed's tools:** `Gibbed.MassEffect2.AudioExtractor` / `Gibbed.MassEffect3.AudioExtract.exe` + `Gibbed.MassEffect3.SFXArchiveUnpack` (unpacks `.sfar` Default.sfar DLC containers before AFC extraction). Base-game AFCs only (Gibbed fails on ME2 DLC single-AFC layout — 1547 oggs in LotSB part 1 with names like `DLC_EXP_Part01_Int.XXXX.wav`) [me3explorer t1826 t1701].
- **Kypp's extractor:** https://github.com/kypp/mass-effect-3-audio-extractor — `afcextr` + `ww2ogg` + `packed_codebooks_aoTuV_603.bin` pipeline: drag AFC onto `afcextr`, then `ww2ogg <file>.wav --pcb <codebook>` → playable `ogg` [Steam Guide 2844561628 Chinese tutorial + audio-digital.net].
- **ww2ogg / ww2ogg.exe + revorb:** converts Wwise Vorbis (`wwise_ima_adpcm` analogue but for Wwise streams) to ogg.
- **AFC File caches:** documented at `dotwhat.net/file/extension/afc/10913` + ME3Tweaks wiki Audio Terms: AFC = concatenated Wwise data, offset-referenced by WwiseStream exports.
- **ISACT (ME1/LE1 only):** Creative ISACT v1.64 for ME1 audio: `.ISB`/`.ICB`/`.SAC` banks via `Psychonauts Explorer` / LEX LE1 audio editing tutorials [wiki Getting Started].

## 5 — Community hubs beyond ME3Tweaks

| Hub | What to find | Link |
|---|---|---|
| **Nexus Mods** | LEX download (674), XCOM Miranda Voicepack (2593914005) as extraction example (370+ lines + radio effect), hundreds of MELE mods, Pinnacle Station restoration case study | https://www.nexusmods.com/masseffect3/mods/674, https://steamcommunity.com/sharedfiles/filedetails/?id=2593914005 |
| **Reddit** | `r/masseffect` (ME1 UPK extraction via Psychonauts Explorer, Full ME2 subtitles txt dump), `r/MECoOp` (MP voiceline locations), `r/masseffect ugv2qr` (LEX audio extractor howto) | https://www.reddit.com/r/masseffect/comments/ugv2qr/mass_effect_2_audio_files_extractor/, https://www.reddit.com/r/MECoOp/comments/1bqcdhm/me3_coop_voicelines/ |
| **ME3Explorer legacy forums** | Deep-dives: ME2 DLC audio extraction pain (t1826), Audio MOD implementation (t1701 — WwiseStream + Soundbank DATA vs AFC streaming) | https://www.tapatalk.com/groups/me3explorer/ |
| **BGForums / Fextralife** | Citadel DLC music extraction tutorial (all-r89_b113.zip + Gibbed + default.sfar) | https://fextralife.com/forums/t325499/tutorial-extracting-citadel-dlc-musicaudio |
| **YouTube — Evil Banana** | Practical rip demos: extracting Miranda lines directly from LE and building XCOM voicepack | referenced in Steam Workshop 2593914005 description |
| **Steam Workshop XCOM2** | Proof that Miranda extraction is battle-tested at scale: Spicy Meat's Miranda Voicepack (370+ lines, WOTC) — used LEX Sound Explorer, noted INI trick `ActiveMods="MirandaVoicepack"` | https://steamcommunity.com/sharedfiles/filedetails/?id=2593914005 |
| **PCGamer article** | How LEX's Asset Database donor system ported Pinnacle Station (95% asset reuse, Ghidra + LExASIs) | https://www.pcgamer.com/meet-the-modders-who-restored-mass-effects-lost-dlc/ |

## 6 — Quick start for Miranda today (community path)

1. Install **ME3Tweaks Mod Manager** → Tools → Install **Legendary Explorer Stable** (or nightly if you need latest dialogue dump speed) [me3tweaks.com/legendaryexplorer].
2. Install **Audiokinetic Launcher** → Wwise **7110** (only needed if you will *replace* audio, not for extraction) [Nexus replacer thread].
3. In LEX: `Dialogue Dumper > Manage TLKs > Auto-Find > Dump xlsx` → open in Excel, filter `Speaker = Miranda Lawson`.
4. `Asset Database > Tools > Compile BioConversations > Generate` → Lines tab → paste TLK StringRef → play → export wav.
5. Batch alternative: `Sound Explorer > File > Open > Wwise menu > Extract all` on `BioGame_Female.pcc` etc for quick bark collection.
6. Stuck? Ask in **ME3Tweaks Discord #legendary_explorer** with your PCC name + TLK ID — devs answer same day.

---

> Fandom is the *encyclopedia*, this community is the *toolchain*. Fandom copies what LEX already lets you read directly from the PCC/TLK. If you want *audio* — not just text — LEX + TLK + AFC is the only full path, and ME3Tweaks Discord is where the people who built it live.
