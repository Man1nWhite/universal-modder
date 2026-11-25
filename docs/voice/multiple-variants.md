# Several takes for one voice line

**Question** (2026-11-25): a bark slot says the same sentence every time. Can one line have variants —
two or three takes, picked at random as the game plays it?

**Short answer: yes — and the mechanism already exists. Do not add variations; use the ones the
vanilla event has.** Every voice line in PAYDAY 2 is a Wwise *random container*, and the pack already
writes one file per container member. Give the members different takes and the game does the
randomising for you, with no Lua, no BeardLib and nothing to keep in sync.

## 1. What the game actually does (sourced, not remembered)

The ModWorkshop wiki's [Extracting & Locating Specific Sounds](https://wiki.modworkshop.net/books/payday-2-mod-creation/page/extracting-locating-specific-sounds)
describes the soundbank as **event → action → object → audio**, with three things that shape playback:
*switches*, *RTPCs* and *random containers* — and says of the last one, in as many words: *"Random
containers make individual events able to play different sounds, well, at random. **All voicelines use
random containers.**"*

Wwiser's exported TXTPs show the container as a range on a `group` line, in the form
`group = -R20>1` — twenty members in a random container, play one — while `group = -S3` is a
*sequence* (play three in order). So the variation count is a property of the vanilla bank, per event.
A mod cannot add a member (that would mean editing the bank itself, which the `.stream`-override route
does not touch); a mod *can* decide what each existing member sounds like.

**Local confirmation, measured.** `voice_lines_vox/miranda_lawson/hila_intent_fit.csv` records, per
slot, how many `regular_vox` ids Hila's barks resolve to for that intent. The 78 slots cover 887 ids,
and the spread is exactly what random containers look like:

| ids for the slot | slots |
|---|---|
| 1 (no variation to give) | 3 |
| 2–3 | 4 |
| 4–8 | 35 |
| 9–16 | 15 |
| 18–46 | 6 |
| 158 (`call_teammate.hey_you` — every heister's *Call* bark) | 1 |

So 75 of the 78 slots already have more than one member, and 22 have nine or more. Today all of a
slot's ids carry the *same* clip, which is why the game repeats one take forever.

## 2. What implementing it looks like here

1. **Data.** `slot_picks.csv` allows the same `slot` on several rows (an ordered list of takes, best
   first). Nothing else changes: each row is already a file + time range like any other pick.
2. **Fit.** `fit_hila_intents.py` keeps every row for a slot, writes them to `hila_intent_fit.csv` as
   `slot#1`, `slot#2`, … and leaves slots with one row alone. Coverage stays "every id in the slot has
   a clip"; it becomes "every id has one of the slot's clips".
3. **Build.** `build_hila_stream_mod.py` assigns ids to takes *stably*: the slot's ids sorted
   numerically, then take `k mod n` — deterministic bytes, and each id keeps its take across rebuilds,
   so a rebuild never reshuffles what the player hears.
4. **Test.** For a slot with `n` takes, every one of its ids must carry one of the `n` clips, each take
   must be used at least once, and the choice must be a function of the id alone (same id → same take
   in two builds). That is a `tests/test_hila_stream_pack.py` case, not a listening test.
5. **Which slots to do first.** The ones a player hears most and that have the most members:
   `call_teammate.hey_you` (158, wants 2–3 different shouted "You"s), `civ.down` (46),
   `move.generic` (43), `pager.clear` (32), `revive.hold` (29), `curse.shit` (21). Single-id slots
   (`cop.hands` among them, 5 ids — enough for two takes) stay as they are.

## 3. What this cannot do

- **It cannot invent new lines.** The takes must be cut from the same archive like every other pick, so
  the vocabulary limit is unchanged: no "hands", as `cop.hands` shows.
- **It cannot change how often a member is picked.** Uniform at random is the bank's behaviour; there
  is no per-member weight to set from a mod.
- **It cannot survive a stub bank.** If a heister's event is a sequence (`-S`) rather than a random
  container, its members play in order — that is the bank's business, not ours.

## 4. Status

Researched and specified here on 2026-11-25; **not built yet**. The pack still ships one take per slot.
When it is built, this file's §2 is the plan to follow, and the in-game check is "the same bark twice,
two different takes".
