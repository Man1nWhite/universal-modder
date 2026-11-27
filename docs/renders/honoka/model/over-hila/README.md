# OfficeSuite + Miranda Romance over Hila — retired

**Retired 2026-11-26 (D82).** This page is kept for provenance: the pack it described,
`OfficeSuite_Miranda_Romance_over_Hila.zip`, is no longer in `dist/` and its sheet is no longer
rendered. The same body and head ship as one whole-character LAS item,
[`OfficeSuite_Head`](../head/README.md) — one unit, one armor-skin entry, and no
`mod_overrides` install.

## What the retired pack was

The native replacement route for Hila: OfficeSuite's body on her own unit plus the ME2 Romance head,
installed by extracting a folder into `PAYDAY 2/assets/mod_overrides/` with no LAS, SuperBLT or
BeardLib. It was the only OfficeSuite pack that did not need Legendary Armour Skins. Its palms were
cut on the line where they begin with no extension past it (D70), its distal wrist twisted on
`ForeArmRoll` (D75), and Hila's stock gloves stayed in the pack, enabled, so an equipped glove had
something to land on.

## Why it went, and what it left behind

`OfficeSuite_Head` already carried the same body, cut and first-person arms with the same head, as a
registered LAS item, and both native over-Hila replacements carried a byte-identical `g_head`
drawable — so the retired pack was also the donor `OfficeSuite_Head` read its head from. That donor is
now `dist/Miranda/Miranda_Romance_over_Hila.zip`: `OfficeSuite_Head` was rebuilt from it and differs
from the retired build in one string inside `BUILD_INFO.json` (`head_donor`) and nothing else.

The install instructions for the retired route are gone with it; the surviving item's are in the
[in-game checklist](../../../../pd2-las/in-game-checklist.md). The `--only-hila` switch of
`tools/render_mod_previews.py` went with the sheet it rendered.
