# Miranda Lawson — Audio extraction (Mass Effect 2 & 3 — TEXT done, AUDIO next)

Text is in `miranda_text_me2_me3.md`. This file tells you how to get the actual .wavs for Miranda (Yvonne Strahovski) so you can reuse them as Payday 2 voicelines or anything else.

## Where Miranda's audio lives

### Mass Effect 2 (2010) + Mass Effect 2 Legendary Edition (LE2)
- **Base game + DLC:** `Mass Effect 2/BioGame/CookedPC/*.pcc` + `BioGame/CookedPCDLC/DLC_*/CookedPC/*.pcc` + `*.afc` (audio file cache). ME2 stores dialogue as Wwise streams referenced by `WwiseStream` objects in the PCC; actual PCM is in AFCs alongside (e.g. `Citadel.afc`, `Normandy.afc`, `DLC_EXP_Part01.afc` for LotSB).
- **Legendary Edition:** same layout but under `Mass Effect Legendary Edition/Game/ME2/BioGame/CookedPC/` (and DLC subfolders). Legendary Explorer handles both.

### Mass Effect 3 (2012) + Mass Effect 3 Legendary Edition (LE3)
- `Mass Effect 3/BioGame/CookedPCConsole/*.pcc` (not CookedPC — console-named folder) + `*.afc`. Multiplayer co-op lines are in `<race>_<class>_MP_LOC_INT.pcc` [r/MECoOp].
- LE3: `Game/ME3/BioGame/CookedPCConsole/`.

> ME1 is different (UPK/ISACT) — not needed for Miranda (she's ME2+).

## Tool 1 — Legendary Explorer (LEX) — recommended (handles both OG + LE2/LE3) [me3tweaks.com/legendaryexplorer]

LEX = rebranded ME3Explorer-Tweaks, upgraded to .NET 8, supports LE. Install via ME3Tweaks Mod Manager > Tools card > Legendary Explorer (Stable) or direct from GitHub.

### Method A — Sound Explorer (fastest for Miranda barks + combat)
1. Open LEX > **Sound Explorer** (renamed from Soundplorer).
2. File > Open > pick a `.pcc` (e.g. `BioGame_Female.pcc` or `Citadel.pcc` — see below for which PCCs contain Miranda).
3. Filter/search `Miranda` or `mir` in the export list; hit Play to preview Wwise stream.
4. **Extract > All** or Selected — choose `wav`. For LE2/LE3 the tool auto-runs Wwise conversion (`ww2ogg` + `wwise_ima_adpcm` equivalent inside LECore). You get clean wavs.

**Which PCCs to open for Miranda?**
- Look up conversations first (Method B below) — they give you the exact `.pcc` + export number.
- Quick hits: `Normandy.pcc` / `NormandySR2_Miranda.pcc`, `Citadel DLC` PCCs (`Citadel.pcc` / `DLC_EXP_Part01`), `Sanctuary` level PCCs (`Sanctuary.pcc` / `Horizon.pcc`), `Orchestral` etc. ME3 Citadel DLC lines are in `DLC_EXP_Part01_Citadel`.
- Multiplayer not needed for Miranda (she's not playable in MP), but the pattern is `<race>_<class>_MP_LOC_INT.pcc`.

### Method B — Dialogue Editor + Dialogue Dumper + Asset Database (full transcript + audio linked)

This is the canonical way to get **every Miranda line with TLK text + audio** in order:

1. **TLK first:** LEX > **Dialogue Dumper** > `Manage TLKs` > `Auto-Find TLKs` (Basegame English + DLC English checked). Then Dump to `xlsx` — you get columns: **Speaker Name, TLK StringRef, Text, Conversation, Game, File, Export #** [r/masseffect Herobrine24 A dialog database].
2. **Asset Database:** LEX > **Asset Database** > Tools > `Compile BioConversations` (won't work until TLKs are managed above) > Generate Database for ME2 (or ME3/LE2/LE3). Now every TLK ID is linked to its `WwiseStream` + `FaceFX` export.
3. **Find Miranda:** In the Database > **Lines tab** > search `Miranda` or search by `TLK StringRef` number from the Excel dump from step 1. Use the Loudspeaker icon on the right to open in **Sound Explorer**; Export to wav (female path — Shepard lines have both male/female, Miranda only one).
4. **Dialogue Editor (optional):** Click the speech-bubble icon on a line to see the conversation tree (kismet, conditions, plot bools). Double-click stage direction to select node.

This gets you ~300+ Miranda lines in ME2 (Normandy, loyalty, romance, suicide mission) + ~80+ in ME3 (Sanctuary, Citadel, Citadel DLC) — essentially everything subtitled.

### Method C — AFC bulk extract (older, noisier)

- Old tools: **Gibbed's ME2 Audio Extractor** (base-game AFCs only), **Kypp's ME3 afc extractor** (`mass-effect-3-audio-extractor` on GitHub, also works on ME2 AFCs) [me3explorer t1826], **AFC2OGG / ww2ogg**.
- Each AFC yields 500-2000 unnamed `DLC_EXP_Part01_Int.XXXX.wav` files [same thread]. You then have to hunt by listening. **Use LEX Method A/B instead** unless you need raw bulk dump.

### Gotchas

- **ME2 DLC audio is pakaged like ME3** — one AFC per DLC, ~1547 oggs in LotSB part 1 alone [me3explorer thread].
- **ME3 DLC is unpacked MP DLC:** If hunting MP co-op voicepacks, run DLC Unpacker first (ME3Tweaks Mod Manager) because `DLC_CON_MP*` folders stay packed [r/MECoOp super-gargoyle].
- **Not all wavs play identically to in-game** — Wwise applies pitch/RTPC/reverb at runtime (e.g. helmet radio). Raw export is dry [r/masseffect yz4bl4].
- **ME2 Audio Extractor dead links (Bioware Social Network):** use Legendary Explorer instead [r/masseffect ugv2qr].
- **LE vs OG differences:** LE repackages audio but same WwiseStream logic; LEX handles both [releases ME3Tweaks/LegendaryExplorer].

## Example — pull Miranda's Sanctuary warning (text in miranda_text file §7)

1. In Dialogue Dumper xlsx filter Speaker=Miranda Lawson, Conversation=`Sanctuary` — find TLK StringRef e.g. `... "This is Miranda Lawson. If you managed to get this far..."` (TLK ID ~ 123xxx).
2. In Asset Database Lines tab paste that TLK ID > preview > Export wav → `miranda_sanctuary_warning.wav`.
3. Do same for `Miranda_Loyalty_Resignation` (“I noticed. Consider this my resignation.”) — conversation `Normandy_MirandaLoyalty`.

## After extraction — to use in Payday 2

1. Normalize to Payday 2 voice spec: mono 16-bit wav, then encode with `wwise_ima_adpcm.exe -e_all` into `soundbanks/streamed/char_hila/<numeric_id>.stream` (or `regular_vox` if overriding OG crew). Length mismatch is OK — don't rename .wav to .stream, don't zip+rename [Voice Over Modding guide].
2. Keep original ME wavs in `voice_lines_vox/miranda_lawson/raw_wavs/` (not tracked) so you can re-encode for other targets (XCOM voicepack workflow does same — see Steam Workshop 2593914005 which built 370+ lines with radio effect).

## Quick self-check

- No game install here yet → verify you have `Game/ME2/BioGame/CookedPC` (or LE) visible to LEX.
- Run `LEX Sound Explorer > Wwise menu > Extract all audio from file` on `Citadel.pcc` — you should get wavs with internal IDs like `mir01_xxxx`.
- If you hit `ww2ogg.exe` crashes [giftfish], update LEX to latest .NET 8 build and install via Mod Manager (bundles correct wwise_cli).

---

Sources: LEX docs (me3explorer.fandom Utilities / Sound Explorer), r/masseffect full subtitles thread (Gibbed's tool mention), r/masseffect ugv2qr+alynnidalar LEX instructions, r/MECoOp ME3 co-op voicelines, me3explorer forums ME2 DLC extraction (1547 oggs note), r/masseffect yz4bl4 SFX locations (SFXGame Wwise_Generic_Foley etc), Herobrine24 dialog database post (Dialogue Dumper workflow), Steam Workshop 2593914005 Miranda Voicepack (370+ lines example).

