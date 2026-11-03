# Business Woman LAS — in-game verification checklist

Pack to install: `dist/BusinessWoman_LAS/` (or `dist/BusinessWoman_LAS.zip`) →
drop the folder into `PAYDAY 2\assets\mod_overrides\`. Needs BeardLib + the
LegendaryArmours framework, exactly like the 2B reference pack.

**Private build.** `5.zip/Please Read.txt` (Melodic) says the mod is not to be
published outside LoversLab without permission. It ships in `dist/` at the repo
owner's direction; that is a decision, not a permission.

Nothing below can be verified offline; every item needs the running game.
Report failures with the item number and a screenshot.

## Install sanity

1. Game reaches the menu with no script errors (BeardLib console clean).
2. The outfit appears under armour skins as **Business Woman** with the
   three-quarter icon.

## Third person

3. Full outfit visible in the lobby preview and in game: body, both jacket
   layers, skirt, heels, necklace. No missing or black drawable.
4. **Wall outline** draws around the heister (needs `CONTOUR` + `unique` +
   the contour variables; all three are in `businesswoman.material_config`).
5. **Ground contact** — the soles sit on the floor, not through it and not
   floating. The source shoe was re-fitted from a 12 cm heel pose; this is the
   first item to check and the most likely to need a nudge.
6. **Feet look right while walking** — the shoe was compressed, not
   re-modelled, so the heel is lower than the Skyrim original. Frames where the
   foot rolls onto the toe are the ones to watch.
7. **Neck** — no hole, no dark disc, no seam ring where the collar was capped.
   Look up at the character from below, where the inside of a hole would show.
8. **Head** — the heister's own head is expected; confirm it is not the 2B
   character (the template's head is stripped out on purpose) and that no
   transparent or doubled head appears.
9. Weights: elbows, knees and shoulders bend without candy-wrapping; the
   necklace stays on the chest and does not stretch into the collar.
10. **Necklace** — the chain follows the body, beads read as beads at heister
    distance (9:1 decimated) and do not shimmer or z-fight.
11. Skirt does not intersect the jacket flaps when crouching (both are static
    skins; the source's HDT sway is not ported).
11a. **Gloves are changeable** — open the inventory and swap gloves, including
    setting them to "none". The outfit ships **no hand geometry** (adapter
    route); the hands you see are the vanilla glove unit plus the `hnd_forearms`
    glove adapter, exactly like a DLC/Infamy suit. This is the point of the
    change, so it is the first hand item to confirm.
11b. **No double hands** — with a glove equipped there is one pair of hands (the
    glove), not a glove drawn over a baked hand. With gloves set to "none" the
    bare `hnd_forearms` adapter shows, not a second pair of hands.
11c. **Wrists / cuff** — the sleeve ends at the wrist (its mouth is *not* welded
    or capped on the adapter route) and the adapter forearm fills the opening,
    in front of her, at her sides, and mid-animation. If a gap or a skin seam
    opens at the cuff in motion, this is the item.

## First person

12. Arms visible on weapon viewmodels; the sleeve is there, with `DEPTH_SCALING`
    keeping it in front of world geometry. The hands come from the camera-unit
    gloves — BeardLib spawns `char_gloves`/`char_glove_adapter` on the local
    peer's camera unit — not from the outfit itself.
13. No torso or leg geometry in the viewmodel (the arms were sliced out of the
    full body, so this confirms the cut).
13a. **First-person hands are present** — the equipped glove (or the bare
    adapter with gloves set to "none") shows on the viewmodel. If the FPS hands
    are missing, the fallback is an FPS-only graft; `--hands graft` rebuilds the
    legacy welded-hand route. Report it and we will switch.

## Materials

14. No pink/error material, no chrome-black fabric, no flat-shaded plastic.

## What to report

For anything that fails: the item number, a screenshot, and whether the same
outfit looks right in the lobby preview (some failures are skinning, some are
materials, and the split is diagnostic).
