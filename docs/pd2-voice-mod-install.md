# Packaging & installing the Hila voice pack (PAYDAY 2 · any BLT / SuperBLT)

One pack ships Miranda Lawson's clips over Hila, and this page is its contract:

| Pack | Route | Needs | Contract |
|---|---|---|---|
| `dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip` | one Wwise ADPCM `.stream` per voice-line id, in `soundbanks/streamed/regular_vox/` | any BLT / SuperBLT | **§1** |

It is the route the game itself uses — Wwise plays each voice-line id from
`soundbanks/streamed/<bank>/<id>.stream`, and a file under the same id replaces that line everywhere
it is used. The reference pack `references/Tokoyami Hila.7z` is built this way; it is dissected
file by file in [`tokoyami-hila-voice-mod-analysis.md`](tokoyami-hila-voice-mod-analysis.md).

Start from [`docs/voice/README.md`](voice/README.md) — it says which voice document is current and which
is history. Two things that are *not* on this page any more, on purpose:

- the **BeardLib `<Sounds>` over OGG** route, which shipped 2026-11-24 and played nothing in game:
  [`dropped-beardlib-sounds-route.md`](voice/dropped-beardlib-sounds-route.md) (D61);
- **several takes for one line**, which the game picks between through the random container the
  vanilla bank already has: [`multiple-variants.md`](voice/multiple-variants.md).

## 1. The stream pack (`Miranda_Lawson_VO_over_Hila_Stream.zip`)

The id-keyed route: the game streams `soundbanks/streamed/regular_vox/<voice-line id>.stream`, so the
file *is* the replacement. No event names, no Lua, no BeardLib, no XAudio API.

### 1.1 Layout

```
PAYDAY 2/
└─ mods/
   └─ Miranda Lawson VO over Hila Stream/     ← folder name is free-form
      ├─ main.xml                             ← <mod name="…"> and nothing else to configure
      ├─ mod.txt                              ← BLT mod-list metadata
      ├─ README.txt
      ├─ hila_stream_map.csv                  ← build manifest: id → slot → clip
      └─ soundbanks/streamed/regular_vox/
         ├─ 712675.stream                     ← 858 files, one per voice-line id
         └─ …
```

`main.xml` carries no `<Sounds>` and no `<Hooks>`: BLT serves the files and the game reads them by id,
so nothing has to be registered. `mod.txt` only makes the folder appear in the main-menu mod list.

### 1.2 The file format

RIFF, 64-byte header, then Wwise IMA ADPCM in 36-byte mono / 72-byte stereo blocks of 64 samples
(4-byte block header: `int16` predictor, `uint8` step index, reserved byte; then 32 bytes of nibbles
= 63 coded samples and one padding nibble). The byte rate is `(rate // 64) * block_align` — 24 804
for mono 44.1 kHz — and the six-byte `fmt` tail is `00 00 04 00 00 00` for mono. Both details are
read off real files and pinned by `tests/test_wwise_ima.py`; the full derivation, and why the encoder
picks a start index per block, is in
[`tokoyami-hila-voice-mod-analysis.md`](tokoyami-hila-voice-mod-analysis.md).

### 1.3 Coverage

| | |
|---|---|
| Voice-line ids in the mapping | 885 (`voice_lines_vox/miranda_lawson/hila_intent_cuts.csv`) |
| `.stream` files written | 858 — 14.04 MB of audio, 12.41 MB zipped (12,618,252 B) |
| Ids left vanilla | 27 (`hila_vorbis_ids.csv`): the vanilla bank streams those as Wwise Vorbis (`fmt` tag `0xFFFF`), which only the Wwise encoder writes. ADPCM under such an id is not the audio the bank expects, so it is not written. |
| Not covered by design | the `robbers_mission_gen` bank (heist-scripted NPC lines with their own text) and music/radio |

### 1.4 Install and check

1. Unzip into `PAYDAY 2/mods/` so that `mods/Miranda Lawson VO over Hila Stream/main.xml` exists —
   one folder deep, as in §1.1.
2. Start the game, play a heist with Hila (as your heister or as an AI teammate).
3. Nothing in `mods/logs/` is expected: this pack has no Lua and no loader API to fail. If a line
   still sounds like Hila, it is one of the 27 Vorbis ids (§1.3), or another Hila voice pack is
   loaded after this one and writes the same ids.

Rebuild and verify offline:

```bash
make -sC tools/pd2-las voices_stream      # rebuilds the zip + .sha256, prints `tracked`
unzip -p dist/Hila/Miranda_Lawson_VO_over_Hila_Stream.zip \
  "Miranda Lawson VO over Hila Stream/soundbanks/streamed/regular_vox/712675.stream" > /tmp/712675.stream
python tools/pd2-las/wwise_ima.py /tmp/712675.stream --wav /tmp/712675.wav   # header, duration, audio
.venv/bin/python -m pytest -q tests/test_wwise_ima.py tests/test_hila_stream_pack.py
```

Heard in game on 2026-11-25: the user installed this pack and reported that it works (the BeardLib
route did not, on 2026-11-24). The report also named two clips cut inside a word, `civ.down` and
`call_teammate.hey_you`; both edges were moved onto the gaps around the wanted words and pinned by
`tests/test_hila_cut_edges.py`, so the tracked bytes are newer than what was heard
(`docs/pd2-las/in-game-checklist.md`). Nothing else of it has been listened to line by line.
