# OfficeSuite + Miranda Romance over Hila

[Download the standalone ZIP](../../../../../dist/Miranda/OfficeSuite_Miranda_Romance_over_Hila.zip) ·
[View the compiled-model preview](officesuite_miranda_romance_over_hila_sheet.png)

## Install

1. Remove any other Hila head/body override, including **Miranda Romance over Hila** or
   **Miranda L4D2 over Hila**, from `PAYDAY 2/assets/mod_overrides/`.
2. Extract the `OfficeSuite and Miranda Romance over Hila` folder into `PAYDAY 2/assets/mod_overrides/`.
3. Select **Hila** with her **default outfit and gloves**. This replaces her default third-person
   body and head in the menu/lobby and heists. It doesn't add an entry to the armor-skin menu.

Neither donor ZIP nor LAS, SuperBLT, or BeardLib is required. The outfit's palms are cut on the line
where they begin, with no extension past it (D70), so the sleeve ends there and **Hila's stock gloves** — kept in the pack,
untouched and enabled, so that a glove the game equips still has somewhere to land — are what the
game puts over it; her first-person arms are unchanged. Other
outfit/glove mods can hide parts of the replacement, and heavy armor or masks may clip. Remove this one folder to uninstall.

## Preview provenance

- Generated with `.venv/bin/python tools/render_mod_previews.py --unified --only-hila` from the
  installed paths **inside the final ZIP**. This is not the older overlay of two donor ZIPs.
- The left three views are front, three-quarter, and back in the bind pose; the right column
  shows the face and side. Hila's stock glove drawable is drawn flat-shaded in that sheet: its
  material samples a vanilla glove texture a replacement pack does not ship, and in game the game's
  own texture applies. The face and the six outfit surfaces use
  packed diffuses.
- Sources: the final OfficeSuite (DOAXVV *Secret Report*) body and caster, and the skin-matched ME2
  Romance head from Miranda Romance over Hila (including the supplied eyes and character icon).
- Offline validation only. The renderer does not show the game's normal maps, shadows, mask/armor
  layering, or animations. See the [in-game checklist](../../../../pd2-las/in-game-checklist.md#native-hila-body--head-override-no-las).
