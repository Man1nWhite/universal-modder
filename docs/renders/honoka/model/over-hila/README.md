# The OfficeSuite + Miranda Romance over Hila override — retired

**Retired 2026-11-26.** This folder is the record of a pack that is no longer in `dist/`:
`OfficeSuite_Miranda_Romance_over_Hila.zip` went first (D82), and the two packs that could have stood
in for it — `OfficeSuite_Head` and `Miranda_Romance_over_Hila.zip` — went with the whole ME2 Romance
line hours later (D83). No sheet is rendered here any more; the last one is in git history.

## What the pack was

The native replacement route for Hila: OfficeSuite's body on her own unit plus the ME2 Romance head,
installed by extracting a folder into `PAYDAY 2/assets/mod_overrides/` with no LAS, SuperBLT or
BeardLib. It was the only OfficeSuite pack that needed no loader. Its palms were cut on the line
where they begin with no extension past it (D70), its distal wrist twisted on `ForeArmRoll` (D75), and
Hila's stock gloves stayed in the pack, enabled, so an equipped glove had something to land on.

The sheet showed the installed paths from inside the final ZIP — front, three-quarter and back in
the bind pose, plus the face and side — with Hila's stock glove drawable flat-shaded, because its
material samples a vanilla glove texture the pack did not ship.

## Why it went

Everything it carried had a second home: `OfficeSuite_Head` was the same body, palm cut, wrist pass
and head as one registered `WHOLE_CHARACTER` LAS item, and `Miranda_Romance_over_Hila.zip` was the
head on its own. What the retirement cost was the no-LAS install route, not content — and when the
Romance line itself followed, that route went with it for good.

Because the retired pack was also the head donor `OfficeSuite_Head` read, this is where the
measurement that made the switch safe is written down: both over-Hila replacements carried a
byte-identical `g_head` `MODEL_DATA` payload (`8125a6c6cb6066f7`) and the same four head/lash
textures, so the rebuild from `Miranda_Romance_over_Hila.zip` changed one member of
`OfficeSuite_Head` (two lines of `BUILD_INFO.json`) and nothing else.

## Where the rest of it is

- The in-game checks that were written for this route are gone from
  [`in-game-checklist.md`](../../../../pd2-las/in-game-checklist.md) with the pack.
- D82 (this pack) and D83 (the Romance line) in [`DECISIONS.md`](../../../../pd2-las/DECISIONS.md).
- The builder, `tools/build_hila_body_mod.py`, and its render function, `render_native_hila_sheet`,
  were deleted; the last bytes of each are in git at `5272168` and `c26b990`.
