# How a PAYDAY 2 voice pack is made: dissecting `references/Tokoyami Hila.7z`

The reference pack replaces Hila's (`ecp_female`, voice switch `rb21`) heister lines by **writing one
game file per voice-line id**. It is the only working example of the route this repository's
`Miranda_Lawson_VO_over_Hila_Stream` pack uses, so it was taken apart file by file. Everything below
is read from the archive itself, not from memory.

| | |
|---|---|
| Archive | `references/Tokoyami Hila.7z` (20 MB, `Tokoyami Towa Voice for Hila`) |
| Contents | `main.xml`, `hooks/localization.lua`, 1,089 `.stream`, two DDS-wrapped `ecp_female.texture` icons |
| Bank layout | `soundbanks/streamed/regular_vox/` 887 files, `soundbanks/streamed/robbers_mission_gen/` 202 |
| Mechanism | no `<Sounds>`, no BeardLib module, no OGG — the soundbanks are the entire mod |
| Extras | `hooks/localization.lua` renames the heister Hila → "Towa" (cosmetic; the audio works without it) |

`main.xml` is a BeardLib-shaped root with one `<Hooks>` node pointing at that Lua file. Nothing else.

## 1. Why this route exists

Every heister line in the game is a file `soundbanks/streamed/<bank>/<id>.stream`, and the game plays
it by the numeric voice-line id from the SoundBank. Replacing the file under that id replaces the
line — every bark, teammate callout and heist-scripted line that uses that id at once, with no event
table to keep in sync (the BeardLib `SoundsModule` route keys on the *event name* the game posts,
which is a different, smaller set of names and needs SuperBLT's XAudio API plus BeardLib).

## 2. The container

Both chunks and header sizes are fixed. For a mono file (bytes 0–63):

```
0000  52 49 46 46 9c 02 00 00 57 41 56 45   RIFF, size = filesize-8, WAVE
000c  66 6d 74 20 18 00 00 00               fmt , payload 24 bytes
0014  02 00  01 00                        wFormatTag 2 (IMA ADPCM), channels
0018  44 ac 00 00                        sample rate 44100
001c  e4 60 00 00                        byte rate 24804
0020  24 00  04 00  06 00                  block align 36, 4 bits/sample, cbSize 6
0028  00 00 04 00 00 00                  Wwise's six-byte tail (mono; stereo ends 03 00)
002e  4a 55 4e 4b 04 00 00 00 00*4         JUNK, 4 zero bytes
003a  64 61 74 61 <size>                  data
0040  <audio>
```

Two details are worth writing down because a "correct" IMA encoder still gets them wrong:

- **The byte rate is `(rate // 64) * block_align`**, i.e. 689 blocks a second at 44.1 kHz
  (24 804 for mono, 49 608 for stereo). The textbook `rate * block_align / 64` gives 24 806.
- **`block_align` is 36 bytes per channel** (mono 36, stereo 72) and the six-byte `fmt` tail differs
  by channel count (`00 00 04 00 00 00` mono, `00 00 03 00 00 00` stereo). The layout is a plain RIFF
  chunk walk: RIFF 12 + fmt 32 + JUNK 12 + data header 8 = 64.

Across the 1,089 files only four ADPCM variants exist: 44.1 kHz mono (394), 44.1 kHz stereo (631),
22.05 kHz mono (33), 22.05 kHz stereo (4) — byte rates 24 804 / 49 608 / 12 384 / 24 768, all
consistent with the rule above, and `data` is always a whole number of blocks with
`RIFF size = filesize - 8`.

## 3. The codec, per block

One block = one 36-byte sub-block per channel, in channel order (so 72 bytes for stereo):

```
+0  int16  predictor   the first sample of the block, verbatim
+2  uint8  step index  0..88, an index into the 89-entry IMA step table
+3  uint8  reserved    0
+4  32 bytes           64 nibbles, low nibble first
```

Each nibble is 3 bits of magnitude (0–7) and a sign bit (8), and expands to
`delta = ((2 * magnitude + 1) * step) >> 3`, added or subtracted from the predictor and clamped to
int16; the index then moves by `(-1, -1, -1, -1, 2, 4, 6, 8)[magnitude]`, clamped to 0..88.
**A block is 64 frames**: the header sample plus 63 coded samples. The 64th nibble is padding and is
zero in practice, so a sub-block codes 64 samples and the last nibble is not part of any of them.

Blocks are independent — the predictor and index restart from the header every 36 bytes — which is
what makes an encoder possible offline and what makes the per-block start index matter (§5).

## 4. 27 of the 1,089 files are not ADPCM

`fmt` size 66, tag `0xFFFF`, `cbSize` 48: Wwise Vorbis. Only the Wwise encoder writes that setup
header, so those 27 ids cannot be reproduced by a hand-rolled pack; the reference pack carries them
as the vanilla game had them. `voice_lines_vox/miranda_lawson/hila_vorbis_ids.csv` lists the 27, and
the stream builder leaves those ids out rather than putting ADPCM under an id the bank expects to be
Vorbis.

## 5. Reproducing it here

`tools/build_hila_stream_mod.py` builds the repo's stream pack; `tools/pd2-las/wwise_ima.py` is the
format (read, decode, encode, write) and is what the tests pin.

```
make -sC tools/pd2-las voices_stream        # -> dist/Miranda/Miranda_Lawson_VO_over_Hila_Stream.zip
python tools/pd2-las/wwise_ima.py FILE.stream [--wav out.wav]   # what is in a file, or hear it
```

- **Audio**: the same cut oggs the BeardLib pack ships (`slot_picks.csv` → slot ranges, level-matched
  to −1.5 dBFS), decoded to 44.1 kHz mono PCM and re-encoded. Nothing is copied out of the reference
  pack or out of a game install.
- **One file per id**: 885 ids in `hila_intent_cuts.csv`, 27 skipped as Vorbis, 162 more skipped as
  below-fit-8 slots with no matching take (`removed_slots.csv`; 3 of them overlap Vorbis), 699
  `.stream` files, 661 s of audio, 14.4 MB zipped. Ids that share a slot share the identical bytes.
- **Encoder**: integer-only numpy over whole batches of blocks, so the bytes do not depend on the
  machine's math library. Per block it tries a handful of start indices (the previous block's, one
  derived from the block's opening three-sample slope, and ±2 around it) and keeps the one with the
  smallest squared error. That is not a micro-optimisation: encoding a block from index 0 measured
  13 dB SNR on speech, choosing the start index per block 30–35 dB. Round-tripping a real 2.02 s
  stereo file from the reference pack reproduces its exact byte count and header, at 33 dB.
- **Verified offline**: header bytes identical to a real mono file, every stream decodes, the
  manifest agrees with the zip (`tests/test_wwise_ima.py`, `tests/test_hila_stream_pack.py`).
  **Not verified**: that the game plays them — no `.stream` from either pack has been heard in game
  (`docs/pd2-las/in-game-checklist.md`).
