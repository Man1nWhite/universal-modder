# Voice: where everything is

Four documents, one subject — Miranda Lawson's clips over Hila's voice. This page is the map: what is
current, what is history, and what to read first.

| Document | What it is | Current? |
|---|---|---|
| [`pd2-voice-mod-install.md`](../pd2-voice-mod-install.md) | **The shipping pack's contract**: the `.stream` route, layout, format, install, checks | **yes** — the only route that plays in game |
| [`tokoyami-hila-voice-mod-analysis.md`](../tokoyami-hila-voice-mod-analysis.md) | How the reference pack `references/Tokoyami Hila.7z` is built, file by file: container bytes, codec, banks | **yes** — evidence, not instructions |
| [`multiple-variants.md`](multiple-variants.md) | Several takes for one line: how the game already picks between variations, and how the pack can use that | **yes** — researched, not yet built |
| [`dropped-beardlib-sounds-route.md`](dropped-beardlib-sounds-route.md) | The BeardLib `<Sounds>` over OGG route that shipped 2026-11-24 and played nothing (D61) | **history** — kept as the record |
| [`../../voice_lines_vox/README.md`](../../voice_lines_vox/README.md) | The data: transcripts, intent cuts, slot picks, and what each slot says | **yes** — the source of every clip |
| [`../pd2-las/DECISIONS.md`](../pd2-las/DECISIONS.md) §D58–D70 | Why each slot's clip is what it is (re-picks, edges, levels) | **yes** — the decisions |
| [`../pd2-las/in-game-checklist.md`](../pd2-las/in-game-checklist.md) | What to listen for in game, step by step | **yes** |

## The one-paragraph version

Every heister line in PAYDAY 2 is a file `soundbanks/streamed/<bank>/<id>.stream`, and the game plays
it by the numeric id from its Wwise soundbank. Replace the file under that id and that line changes
everywhere it is used — no event table to keep in sync. The pack does exactly that for the 887
`regular_vox` ids Hila's barks resolve to: 78 clips, cut from Miranda's scene dialogue by
`tools/fit_hila_intents.py` through the hand-curated `voice_lines_vox/miranda_lawson/slot_picks.csv`,
and written by `tools/build_hila_stream_mod.py`.

The BeardLib `<Sounds>` route — keying an *event name* in `main.xml` and shipping OGG — was tried
first and produced nothing in game even with the keying verified; it is history now, and the file
that explains why is the third row of the table above.

## Stale by design

`dropped-beardlib-sounds-route.md` describes a route that is not shipped, and files in it name the
`Miranda_Lawson_VO_over_Hila.zip` pack that no longer exists in `dist/`. That is deliberate: it is
the record of D61, and it is where a future attempt on that route starts. Nothing else under
`docs/` describes a voice route that does not ship.
