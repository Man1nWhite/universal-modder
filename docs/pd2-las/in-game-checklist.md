# Miranda LAS — in-game verification checklist

Pack to install: `dist/Miranda_L4D2/Miranda_L4D2_LAS.zip` → extract the `Miranda_LAS`
folder into `PAYDAY 2\assets\mod_overrides\`. Requires BeardLib + the LegendaryArmours
(LAS) framework, exactly like the 2B reference pack (`2b.rar`), which
installs the same way (its `main.xml` + `hooks/` are loaded by BeardLib's
AddFramework from `assets/mod_overrides/`).

Nothing here can be verified offline — every item needs the running game.
Report failures with the item number and a screenshot.

## Ten minutes: the rebuild of 2026-11-11

> `Miranda_L4D2_LAS` and its head packs were built again on 2026-11-12,
> so that their bytes no longer depend on the CPU that builds them
> (`docs/audits/2026-11-12-cpu-independence.md`). Nothing that should show changed: the steps are the same, on
> the packs as they are tracked now. The one place that could look different is how a surface without texture
> area shades: a few hair cards of Miranda.

`Miranda_L4D2_LAS` and its head packs were rebuilt that day. What changed, and what was measured offline,
is in `docs/audits/2026-11-11-miranda-mips-and-object.md`. None of it has been
seen in the game. These five steps are what would settle it. Write down the
resolution, the FOV setting, the texture quality and the anisotropic filter
before you start: the offline figures assume 1080p or 2160p, the game's default
field of view and no anisotropic filter.

Install `Miranda_L4D2_LAS.zip` (`Miranda_LAS/`). For the comparisons, the packs as they were are
`git show 13538a1:dist/Miranda_LAS.zip` and the same for its head packs.

| Step | What to do | Pass | Fail |
| --- | --- | --- | --- |
| A. It loads | Start the game, open the outfits, equip the outfit | The menu comes up, both outfits are listed, the preview shows the body | A crash, a script error, or an outfit that is missing |
| B. First person | Play any heist alone with the outfit: look at the arms with a weapon out, reload, interact once | The arms are there and move; the heist starts and ends without a crash | No arms, or a crash when the heist loads. This is the step the `.object` change is about |
| C. The face, close | In the outfit preview, zoom in on the face and turn it under the light | The lash lines are clean, the eyes are blue, the sheen on the skin is even | Sparkling dots of gloss on the cheeks or the forehead (the old pack had its gloss scrambled inside each block; a few such dots at mid distance are a known finding for the neck and the body) |
| D. The face, a few metres away | Look at the character where the game shows it from a few metres (the lobby, or a friend's view of you at about 4 m and 8 m), while it moves | At about 4 m the eyes read as blue; the face holds still as it moves. At about 8 m an eye is three pixels wide and the offline render shows it grey-blue: that is expected | Grey eyes at 4 m, or a face that crawls and sparkles as it moves. Do the same with the old pack: it had one mip level, so it should crawl where the new one holds still, and its eyes may look bluer at 8 m. If you cannot tell them apart, or you prefer the old one, say so |
| E. A head pack | Equip the heister whose head pack you use and look at the face in the menu | It looks as it did | A visible change in colour, or gloss dots on the face |

Afterwards read the game's `crash.txt` and `crashlog.txt` (the two files you sent
for the lawson pack) and the BLT log of that session. Pass: no entry from this
session, and no line that names `miranda` or `g_head`.

Step D is the one the offline work cannot replace. In a still frame the old
pack is closer to the ideal picture than the new one at every distance; the mip
levels are there for motion, and only the game shows motion.

## Install sanity

1. Game reaches the menu without script errors (BeardLib console clean).
2. The outfit appears under armor skins as **Miranda Lawson** with the
   face-crop icon.

## Third person (main view)

3. Full body visible in the lobby preview and in-game: head, torso, arms,
   legs, boots — no missing groups (`g_body`, `g_head` enabled per
   `miranda.object`; `s_body` handled by the engine).
4. **Texture orientation** — **pre-verified offline** against the 2B
   reference: `tools/pd2-las/uv_check.py` renders our UVs and the known-good
   2B UVs with an identical sampler; the results match (see
   `build/pd2-las/previews/uvcheck_*` — face/outfit/eyes land anatomically). The probe
   reads the tracked ZIP and its textures by default. The stored convention is the p2mt GLTF import
   `v = 1 − v_src`, same as 2B. Still confirm in game; if it ever reads
   flipped, it is a single sign flip in `build_models.py`
   (`transfer_group`, the `g.uvs` append) plus the same flip in
   `tests/test_build_models.py`.
5. **Winding** — surfaces opaque from all angles; no inside-out faces
   (signed volume matches the 2B reference offline, so this should hold).
6. Skin weights: elbows, knees, shoulders bend smoothly; no candy-wrapper
   or spiking at joints. Fingers share the hand's similarity fit (rigid
   with the palm), so expect clean but slightly averaged fingers. The face
   region shares one frame and should read cleanly.
7. Face intact at close range: eyes, nose, lips present; slight lip/jaw
   softness is known/acceptable for v1.
8. Shadow (`s_body`) renders under the character. Ground contact: offline the
   lowest vertex of the body is at z = −0.75 cm, so the soles should stand on
   the floor — check for floor clipping or floating and report if visible.

## First person (arms)

9. Arms visible on weapon viewmodels; correct texture (body material with
   `DEPTH_SCALING`, mirroring the 2B fps contract).
10. No shadow mesh clipping into the fps camera.

## Materials

11. Body/face/head/hair use their own `df`/`nm` textures per
    `miranda.material_config`; eyeballs use `miranda_eyes.texture`.
12. Hair renders solid (no alpha-tested cards were authored — the source
    hair is a solid mesh).
13. No pink/error materials anywhere.

## Animation / framework

14. Outfit follows standard LAS animations (the skeleton retarget is
    authored on the 2B LAS skeleton — `units/2b/skins/2b` template tree).
15. `hide_mask` / `hide_armor` / `replace_all` / `fps_hide_armor` /
    `fps_replace_body` flags behave as with 2B.

## Guide watch items (ModWorkshop LAS/MOOG guide)

16. **Normal-map orientation** — check that bumps and creases light correctly. The builder
    swizzles the L4D2 Miranda source channels and inverts source Y when encoding PD2's Y+ maps.
    If the shipped textures look inverted, report the material and lighting; don't edit the
    textures during a check of the shipped bytes.
17. **Contour outline** — the four TPP materials support `CONTOUR` but the shipped configs set
    `contour_opacity=0`. Standing behind a wall alone is not a positive outline test. Only expect
    an outline when testing a game effect that explicitly turns it on.

## OfficeSuite — the jewelry diffuse (2026-11-18)

Pack to install: `dist/Miranda/OfficeSuite.zip` → drop `OfficeSuite` into `PAYDAY 2\assets\mod_overrides\`.
Only the jewelry diffuse changed (`references/honoka/Tex_23(L_23)2.dds`, D50); the geometry, the
suit and the registration are the same as the build the 2026-11-15 captures show, so a difference
seen here and nowhere else belongs to `L_23`. The pack also ships a first-person arms unit now
(D53): the third-person body is untouched, but the first-person check below is new.

1. **The jewelry reads correctly** — necklace, chain and brooch sit on the jacket with no seam
   across the collar and no wrong-chroma patch where the old diffuse's UV island was.
2. **It matches the suit** — the jewelry and the black jacket are lit by the same light without the
   jewelry looking like a separate cut-out pasted on top.
3. **First person** — a heist with a weapon out, reload and interact once: the outfit's sleeves run
   on past the wrist and end inside the gloves, the jewelry cuff and the bra straps read as part of
   the outfit, and nothing is missing, duplicated or clipped. The cuff and straps are arm-weighted
   geometry by construction; the pack models no hands at all, and no glove spawns by default (D60).

Everything else for this pack is covered by the 2026-11-15 sections of the render pages; the
captures there predate this texture and cannot be used to judge the jewelry, and predate the
first-person unit entirely.

## OfficeSuite — the palms are cut, and no glove is spawned over them (2026-11-25, D60/D70)

Install `dist/Miranda/OfficeSuite.zip` as above. The body has no hands in it: everything from where
the palm begins outwards is gone, and D70 has reverted the D62/D63/D65 extensions, so the cut is back
**on that line** (`palm_cut` in `BUILD_INFO.json`: `extend_cm` and `clipped_to_cm` both `0.0`,
`kept_to_cm` -0.76 / -0.79 after the slim) with the rim capped. The plane is D60's: through the PD2
`Hand` joint, perpendicular to the palm. The pack registers
`officesuite_own_hands.lua`, not the glove adapter: no default glove unit spawns, so the body has no
hands by default, and a glove the player picks by name is the only thing that puts hands on the
character. Offline the sleeve ends read as a clean cuff; what only the game can show:

1. **No vanilla skin at the wrist.** The D59 build showed a salmon-pink band with a seam between the
   sleeve and the black glove — that was the adapter's `hnd_forearms`, a vanilla bare forearm drawn
   outside the outfit. There must be none now: the sleeve, its black cuff and the jewelry cuff, then
   either the cut or the glove. Fail: any second skin band, any band with a seam in it, any vanilla
   `hnd_glv_heistwrinkled` glove at the cuff.
2. **No hands by default.** With gloves on "Default" the character's hands must be *absent* where the
   outline of a hand would be: the sleeve ends at the crease in a capped end, and no stock bare
   hand shows beside it. This is the D60 state and it is intended to look handless.
   **The wrist is D70's reversion:** D62 closed D60's in-game gap by cutting 4 cm into the palm,
   D63 cut 1.5 cm and D65 cut 1.25 cm, and each still showed arm skin at the glove in the user's
   screenshots. The cut is back on the palm line, so a flat cap above the heister's glove and a gap
   between it and the cuff are the *expected* result of this choice, not a build error. What still
   fails is any skin extending past the crease, a band of second skin, or a hand modelled by the
   outfit. Move the hand, aim, and reload and check that no skin pops through a glove in any pose.
   **D75 is the answer to what that check found:** first person with white dress gloves showed a
   sliver of the outfit's wrist in the glove's cuff (2026-11-26 captures, now archived under
   `docs/renders/honoka/in-game/officesuite/2026-11-26/`). The wrist now twists on `ForeArmRoll`,
   its last 2.6 cm blend up to 0.30 of `Hand`, that stretch is tucked 0.35 cm inwards and the cut
   ring is centred on the palm's axis. Check the same view again with the buttoned dress gloves:
   the cuff should close over the skin in aim, reload and sprint, and the bracelet should turn with
   the forearm instead of staying square to the sleeve. What still fails is skin *inside* the cuff
   showing through the glove, or the bracelet bending.
3. **A chosen glove wins.** Equip a named glove (Bone Mittens): it must spawn and read as the
   character's hands, with the sleeve's cuff still outside it. Since the arm ends on the crease, the
   glove may not reach the cut and a gap can remain; what matters is that no bare hand of ours sits
   above it. Then go back to "Default": the glove must disappear again rather than stick.
4. **The first-person arms match.** The `fps_officesuite` arms are cut on the same plane; a weapon
   held and a reload should show the sleeve ending at the crease, with no hand modelled in the outfit
   and no vanilla skin band at the wrist — with a glove equipped, the glove is what holds the weapon.
   This is the view that showed the skin wedge in D65, so check it in motion.
5. **The shadow.** The trimmed shadow caster is cut too: look at the character's own shadow on the
   ground while turning — no hand, and no hole where the hands used to be.

`OfficeSuite_Head` shared this body and would have needed the same checks; it was retired on
2026-11-26 (D83), as was the native Hila override (D82).

## Retired: `OfficeSuite_Head` and the native Hila override (D82/D83)

Both packs are gone from `dist/` (2026-11-26), and so is the Romance line they were built from, so
this page has no install steps for them and no checks left open. What was left unconfirmed at the
time stays on the record in [`HANDOFF.md`](HANDOFF.md): the lashes on the `opacity:` shader, the neck
under the collar, and whether the mask came back — none of them was ever seen in game.

## `Miranda_Lawson_VO_over_Hila` — audio only (2026-11-24, dropped 2026-11-25)

**This pack no longer ships (D61).** It was installed on 2026-11-24 and vanilla Hila still played;
the keying was re-verified against the loaders and was right, so the route itself never produced a
line. The id-keyed stream pack below does, and it is the only one in `dist/Miranda/`. The steps stay as
the record of what was asked of it, and as the checklist a future pack on that route would start
from; the packaging contract (and the reason for the drop) is the `install` tab of
[`voice_lines_vox/vo_master.xlsx`](../../voice_lines_vox/vo_master.xlsx).

1. **The mod list.** BeardLib's Mods menu lists *Miranda Lawson VO over Hila*, enabled, no red error line.
2. **It replaces at all.** Play Hila in any heist: the interaction and movement barks ("On me.", "Follow
   me.", "Get ready.") are Miranda, not Hila. If Hila still talks, the pack loaded but matched nothing —
   run the next step before touching any file.
3. **Only Hila's lines change.** With a second heister in the crew, their copies of the same barks
   (`On me.`, `Get ready.`) stay vanilla. That is what `prefix="rb21"` buys.
4. **Coverage, with `Log Sounds` on** (Mods → BeardLib options, default off): every bark you hear as
   vanilla and would expect to be replaced shows an `Incoming sound check: ID … Prefixes …` line in
   `payday2_win32_release_*.log`. A `Prefixes` list containing `rb21` is Hila's; the install doc §4d says
   what to do with an id you want answered.
5. **The deliberate gaps stay vanilla.** The heist-scripted callouts with heist-specific text (`p33`–`p47`,
   most of `v01`–`v58`, `g61`–`g68`) are left alone on purpose; hearing Hila there is not a bug. §4d of
   the install doc lists them.
6. **Bleed-over absences.** No subtitle, no lip movement: the clips are audio only, so a subtitle that
   still says Hila's line is expected and not fixable from the pack.

## `Miranda_Lawson_VO_over_Hila_Stream` — audio only (2026-11-25)

The only Hila voice pack that ships: SuperBLT and nothing else, no BeardLib, no `mods/logs` line to
expect. 699 `.stream` files named after Hila's voice-line ids, 189 ids left vanilla — 27 Vorbis in
the vanilla bank, and 162 ids of slots below the semantic-fit floor with no take in either source
archive (2026-11-25 rebuild; those lines are vanilla on purpose). **Heard in game on 2026-11-25: the
user installed the previous build and reported it works — the rebuilt pack is NOT yet heard in game.**
That report also named two clips cut inside a word, which are re-cut below; the rebuilt pack also
swapped 33 slots to purpose-authored takes from `LAWSON VOICE (PAYDAY 2).7z` and silenced nothing —
the sub-8 lines are vanilla now. The bytes it heard are not the tracked ones.

1. **It replaces at all.** Play Hila in any heist with the stream pack as the *only* Hila voice pack
   installed: the movement and interaction barks are Miranda. Passed 2026-11-25 — this is the check
   the BeardLib pack failed on 2026-11-24, so the id-keyed route is the one that works.
1a. **The two clips the 2026-11-25 report named.** Both were cut inside a word and re-cut by
   measurement (`slot_picks.csv`, `tests/test_hila_cut_edges.py`):
   - `civ.down` (46 ids) should say **"Keep your head down,"** and stop there — no fragment of
     "Shepard" after "down". It used to end 0.2 s inside that name and played as "keep you head down,
     Shep".
   - `call_teammate.hey_you` (158 ids) should say **"you take point"** — three words, not just "you".
     It used to start on the "-ard" of "Shepard," and end on the next word's fricative.
   If either still sounds wrong, note whether it is *cut short* (the line stops mid-way) or *cut
   wrong* (a fragment of the neighbouring word): the first is a playback-length question, the second
   is another edge to move, and they are different fixes.
1b. **The two clips the next report named** (2026-11-25, same day):
   - `cop.hands` (5 ids) should say **"Stop."** as one whole word. It used to play a chopped "smi",
     because 0.420 s of the source is the start of "smiling", not the end of "stop". If it still
     sounds odd, say whether a fricative is missing from the front or the word is cut off at the
     back — those are the two edges, and they move independently.
   - `civ.nophone` (1 id) is now **"I'd rather we didn't."** rather than "There's nothing we can do,".
     It is the pick the pack's vocabulary allows for *don't make that call*; if a better-sounding
     take exists, it can only be another line from the same archive.
1c. **`call_teammate.hey_you` is one word now** (2026-11-25, same day). It shipped 0.667 s of
   "you take point" and the report heard "just you"; the shipped `.stream` decodes as three
   syllables, so the line is now a single shouted "You" (0.289 s). Call a teammate: one clear
   word, not a clipped one. If it still sounds cut, the game is stopping the line before the file
   ends, and the next lever is the vanilla length rather than the cut.
1d. **The sub-8 slots are vanilla now** (2026-11-25 rebuild, not yet heard in game). 33 slots play
   purpose-authored takes from `references/voice/LAWSON VOICE (PAYDAY 2).7z` (whole takes, 30 ms pre-roll
   and 50 ms post-roll kept, −1.5 dBFS); 17 slots with no take — among them `civ.nophone`'s neighbours
   (`civ.talk`, `civ.ties`), the squad-move lines (`move.on_me`, `move.this_way`), the medic/police
   body lines (`hurt.medic`, `kill.taser`, `mark.medic`…) and `pager.clear` — are simply absent from
   the pack, so those ids play vanilla Hila. If one of those sounds like vanilla Hila instead of
   Miranda, that is by design, not a miss. The TTS wording itself has not been verified by ear: if a
   new take says something odd in context, that is the take, not the cut.
1e. **`Geralt_VO_over_Rust_Stream` — removed 2026-11-28 (D89).** The pack was never heard in game
   and the zip was deleted with its Arivus sibling; there is nothing to install for Rust VO any
   more. The question this item was to answer — whether Rust barks from the shared `regular_vox`
   bank or his own `char_rust` bank — stays open (O1; the measured bank is recorded in the
   `char_rust` tab of `voice_lines_vox/vo_master.xlsx`, and the `char_rust` route stays blocked on
   `voice_lines_vox/geralt/char_rust_ids.csv`, D76). Do not go looking for the pack.
1f. **`Arivus_VO_over_Hoxton_Stream` — removed 2026-11-28 (D89).** Never heard in game; the zip was
   deleted. Nothing to install for Old Hoxton VO any more; the slot picks stay in
   `voice_lines_vox/arivus/slot_picks.csv` as the record of what the set carried.
2. **No loader noise.** `mods/logs/` should show the mod folder loaded and no error from it: the pack
   has no Lua, no hooks and no XML to parse beyond `<mod name=…>`.
3. **Line-by-line, not event-by-event.** A heist-scripted line Hila speaks as an NPC keeps Hila's
   voice (the `robbers_mission_gen` bank); a heister bark that is still Hila's is either one of the 27
   Vorbis ids (`voice_lines_vox/miranda_lawson/hila_vorbis_ids.csv`) or a second pack writing the same
   ids after this one.
4. **Length.** A replacement keeps its clip length (0.22–1.95 s), so a replaced line can be shorter or
   longer than the vanilla one. No subtitle changes: those still show Hila's line.
5. **First person.** Nothing to check — audio only.

## Arivus over Old Hoxton v2 — the re-sculpted crown (2026-11-28, D97)

Install `dist/Arivus/Arivus_over_Hoxton_v2.zip` (**instead of** `Arivus_over_Hoxton.zip` — both write
the same `Arivus over Hoxton*` units and the same four `shared_textures/old_hoxton_head*` overrides, so
only one of them may be in `mod_overrides/` at a time). Put Old Hoxton in a heist, in the lobby, and in
the Safe House. v2 is the owner's Blender scene of the same head: v1's atlas, materials and suit, with
the crown and the back of the skull re-sculpted by up to 0.68 cm. The checks a bind-pose render cannot
make:

1. **The crown reads as hair, from above and behind.** Stand in third person and look down at him in
   the lobby: the top and back of the head should keep the hair card's volume and the same cutout
   edges as v1 — no hole through the scalp, no floating cards, and no sawtooth edge where the crown
   meets the sides.
2. **The neck still closes.** The scene already carried v1's D79 skirt; v2 ships it rather than
   stitching a second one. In the collar opening, at the throat and at the back of the neck, there
   must be no skin gap, no band of the throat's far wall, and no second rim standing inside the suit.
3. **The mask and the alpha test.** The head material keeps v1's `ALPHA_MASKED` template and its 0.05
   cutoff. The hair's cutout edges should be crisp at close range in the blackmarket preview, and the
   hair should be dark but not black through from behind (both faces of each card are in the mesh).
4. **Skinning at the seams.** Turn the head hard left and right in the lobby. The crown's extra
   vertices are weighted to the same `Spine2 / Neck / Head` palette as v1's; a crease, a pinch or a
   patch of head that stays behind belongs in the report with the view it happened in.
5. **Which pack is installed.** If the head looks exactly like v1, check that `Arivus over Hoxton v2`
   is the folder in `mod_overrides/` and that the v1 folder is not beside it — the two cannot be
   installed together, and whichever loads last wins.

## Arivus over Old Hoxton — the shaved face (2026-11-25, D64)

Install `dist/Arivus/Arivus_over_Hoxton.zip` and put Old Hoxton in a heist (and in the Safe House —
the pack also rewrites the chill model). The ped has no beard geometry; the beard is painted into its
head texture and the build inpaints it. These are the checks the offline render cannot make:

1. **The shave reads as skin.** Under the heist's lighting the jaw, cheeks and chin should look like
   one face, not like a lighter panel: no straight line down either side of the face, no line across
   the jaw, and no dark crescent beside either ear. Turn the head in the lobby, where the light
   moves across it, and look at the jaw in the blackmarket preview too.
2. **No stubble, and no washed-out face.** The painted beard's edge is soft; look for a reddish
   freckle-like shadow across the lower face at close range (the collar & head 3/4 view in the sheet
   is the reference angle) and for stray hairs under the lower lip. The face must also keep its own
   shading — the nose's flank, the eye sockets and the cheeks were flat in the 2026-11-25 build
   (D66: the shave had repainted the whole face), so a face that looks airbrushed is the failure.
   D69 tuned the colour: the shaved field takes its hue from the clean skin ring round the beard
   (the jaw's own ≈ 148,105,90), not from the pale forehead, and keeps its own light and shade. The
   face should read as **one skin tone under one light**; the two things to look for are a **grey or
   sooty patch** (the field taken the wrong hue — this is what the 2026-11-25 portrait showed) and a
   **flat rectangle** across the jaw (the level match, not the hue). Say which, since they are
   different levers, and say where on the face it starts. D72 found the beard from the raster's own
   hairs instead of a hand-drawn U, so the upper cheeks and eye corners must keep their own shading;
   the painted hairs in front of each ear and the two ticks at the mouth's corners are gone. The
   hair cards in the hair half of the atlas (z ≈ 169.5 upward) are still geometry and may shade a
   little dark in front of the ear under the game's light — that is not leftover paint.
3. **The features are the ped's own.** Eyebrows, both lips (with the mouth's dark slit), nostrils and
   the ears should sit where they did before: nothing blurry, nothing doubled, no pale or thin mouth,
   and no drawn outline around it.
4. **The hair reads as hair.** The cutout fringe is `ALPHA_MASKED` with `alpha_ref 0.05`: it should
   not flicker, halo or draw as a solid band against the forehead, and the scalp should not show
   through at the crown.
5. **The head still fits the suit.** No gap or stretched skin at the collar, **including the back
   of the neck**: D79 dropped the ped's V-shaped cut below the collar rim and closed it with a skirt
   tucked inside the suit, so from behind the collar should read as an unbroken line with skin above
   it and nothing showing through. Watch also for the neck creasing or pinching when the head turns
   (the rim now sits ~5 cm lower than the cut did, and it is the part the `Neck` bone moves).
   The menu portrait should match the in-game head, and the HUD icon is the same face.

## OfficeSuite over Bunny — native Hop to It outfit override (2026-11-27, D85)

Pack to install: `dist/Miranda/OfficeSuite_over_Bunny.zip` → extract the `OfficeSuite over Bunny`
folder into `PAYDAY 2\assets\mod_overrides\`. Copy its `OfficeSuite Bunny Forearm Fix` folder
into `PAYDAY 2\mods\` and restart. The companion needs SuperBLT; BeardLib and Legendary Armour Skins
are not required. Remove the companion if reverting to the vanilla Bunny outfit.
In-game, open **Outfits** in the BlackMarket and equip **Hop to It** (`bunny`, community / free outfit).

1. **Menu icon & turntable preview.** In the Outfits tab, the **Hop to It** tile shows the OfficeSuite
   icon (`bunny.texture`), and equipping it displays the black blazer, white blouse, skirt, heels,
   anklet, brooch/chain and wrist watch cleanly on both female (Clover/Hila/Joy/Sydney/Bonnie) and male
   heisters with no scrambled UVs or pink materials.
2. **Neck & head seam.** Because `player_styles.bunny` keeps `head = false`, the equipped heister's
   own head (or a head replacement such as `Miranda_L4D2_over_Hila`) sits above the OfficeSuite collar;
   turn the character in the lobby and check the base of the neck from front, side and behind. With
   the new Miranda head, also check the pictured beret, tiara and glasses for hair/face intersections;
   the accessory-clearance adjustment is a trial and has not been checked in game.
3. **Gloves.** With the companion installed, check Default and selected gloves in third and first person:
   the selected gloves should remain, with no separate `hnd_forearms` band over OfficeSuite skin.
   Check cuffs against the D70 palm cut and D75 `ForeArmRoll` wrist twist. Check another outfit too.
4. **First-person viewmodel.** Load a heist solo with **Hop to It** equipped: verify the black sleeves,
   white cuffs and wrist watch appear at normal weapon-holding height, do not vanish when looking up or
   down (`co_box` culling), and twist cleanly when aiming, reloading and interacting.
5. **Shadow caster.** Check the character's ground shadow in third person (`s_body` on `shadow_caster`).

