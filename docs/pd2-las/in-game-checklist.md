# Miranda LAS — in-game verification checklist

Pack to install: `dist/Miranda_L4D2/Miranda_L4D2_LAS.zip` → extract the `Miranda_LAS`
folder into `PAYDAY 2\assets\mod_overrides\`. Requires BeardLib + the LegendaryArmours
(LAS) framework, exactly like the 2B reference pack (`2b.rar`), which
installs the same way (its `main.xml` + `hooks/` are loaded by BeardLib's
AddFramework from `assets/mod_overrides/`).

Nothing here can be verified offline — every item needs the running game.
Report failures with the item number and a screenshot.

## Ten minutes: the rebuild of 2026-11-11

> The six packs below and the four Romance head packs were built again on 2026-11-12,
> so that their bytes no longer depend on the CPU that builds them
> (`docs/audits/2026-11-12-cpu-independence.md`). Nothing that should show changed: the steps are the same, on
> the packs as they are tracked now. The one place that could look different is how a surface without texture
> area shades: a few hair cards of Miranda.

Six packs were rebuilt that day: `Miranda_L4D2_LAS`, `Miranda_L4D2_Busty_LAS` and the four
`Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}` head packs. What changed, and what was measured offline,
is in `docs/audits/2026-11-11-miranda-mips-and-object.md`. None of it has been
seen in the game. These five steps are what would settle it. Write down the
resolution, the FOV setting, the texture quality and the anisotropic filter
before you start: the offline figures assume 1080p or 2160p, the game's default
field of view and no anisotropic filter.

Install `Miranda_L4D2_LAS.zip` (`Miranda_LAS/`) and `Miranda_L4D2_Busty_LAS.zip` (`Miranda_Busty_LAS/`) together; they are separate
outfits. For the comparisons, the packs as they were are
`git show 13538a1:dist/Miranda_LAS.zip` and the same for the other five.

| Step | What to do | Pass | Fail |
| --- | --- | --- | --- |
| A. It loads | Start the game, open the outfits, equip the busty outfit | The menu comes up, both outfits are listed, the preview shows the body | A crash, a script error, or an outfit that is missing |
| B. First person | Play any heist alone with the busty outfit: look at the arms with a weapon out, reload, interact once | The arms are there and move; the heist starts and ends without a crash | No arms, or a crash when the heist loads. This is the step the `.object` change is about |
| C. The face, close | In the outfit preview, zoom in on the face and turn it under the light | The lash lines are clean, the eyes are blue, the sheen on the skin is even | Sparkling dots of gloss on the cheeks or the forehead (the old pack had its gloss scrambled inside each block; a few such dots at mid distance are a known finding for the neck and the body) |
| D. The face, a few metres away | Look at the character where the game shows it from a few metres (the lobby, or a friend's view of you at about 4 m and 8 m), while it moves | At about 4 m the eyes read as blue; the face holds still as it moves. At about 8 m an eye is three pixels wide and the offline render shows it grey-blue: that is expected | Grey eyes at 4 m, or a face that crawls and sparkles as it moves. Do the same with the old pack: it had one mip level, so it should crawl where the new one holds still, and its eyes may look bluer at 8 m. If you cannot tell them apart, or you prefer the old one, say so |
| E. A head pack | Equip the heister whose head pack you use and look at the face in the menu | It looks as it did | A visible change in colour, or gloss dots on the face |

Afterwards read the game's `crash.txt` and `crashlog.txt` (the two files you sent
for the lawson pack) and the BLT log of that session. Pass: no entry from this
session, and no line that names `miranda`, `g_head` or `fps_miranda_busty`.

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

## Christie LAS — in-game verification (2026-11-14)

> **Update, 2026-11-15.** Earlier packs were in the game outfit menu on 2026-11-15 (user report:
> removed `Christie_LAS_Slim` and the older full `Christie_LAS`, captures archived at `da891d7` and
> removed in D39), and later menu/lobby captures of the rebuilt `Christie_LAS` are archived under
> `docs/renders/christie/in-game/2026-11-15/`. The heist look, first-person arms, rifle elbow,
> cuff/glove stack across poses and crash logs remain open, and installed hashes were not measured.

Pack to install: `dist/Christie/Christie_LAS.zip` → drop `Christie_LAS` into
`PAYDAY 2\assets\mod_overrides\` (SuperBLT + BeardLib + LAS, same as the 2B reference). It is a
headless and handless LAS outfit (`replace_body`, not `replace_all`, with `glove_adapter.lua`): the
heister keeps their own head and spawns their LAS/vanilla gloves over the wrist cut.

The current `Christie_LAS.zip` is the source rebuild (`build_christie_source.py`) with no head or
authored hands; check its `.sha256` sidecar to identify the installed bytes. `runtime_verified`
remains `false`. Write down resolution, FOV, texture quality and anisotropic filter first.

1. **It loads** — menu outfits list "Christie (DOA5)"; the preview shows the body (open neck by
   design). A crash or a script error fails this item.
2. **Third person** — full body in lobby preview and in game: blazer, shirt, trousers, spawned
   gloves over the wrist cut, shoes; no missing groups; the neckline is the designed open collar.
3. **First person** — heist with a weapon out: arms present and moving; reload and interact; no
   crash.
4. **The inner elbow, rifle vs no rifle** — the same heister, pose, camera and lighting: (a) arms
   down (idle), (b) rifle shouldered. In (b) look at the inside of the elbow from the off side.
   Fail: a hard flat edge or a bright flap that was not there in (a). The earlier build had a
   reported elbow issue; the new build has not been tested in-game. If it shows, capture both
   views and the installed hash before deciding on a repair.
5. **The throat, head on vs head off** — equip Christie, then equip the vanilla heister, same
   spot, same light. Fail: a band across the throat only with Christie on. (The pack ships no
   head; offline work cannot assign this between the body and the head rim.)
6. **Sleeves gloss** — sleeves should read matte, like the torso, not wet. Fail: a mirror
   response on the sleeves (the diffuse alpha was rebuilt from the normal map; this item checks
   it in engine).
7. **Cuff / glove stack** — spawn a glove, then an alternate glove: the cuff should sit outside
   the glove in every pose. Fail: sleeve swallowing the glove, or glove floating outside the
   cuff.
8. **Movement** — sprint, crouch, interact near-objects: no popping, no spiking fingers, elbows
   bend cleanly, the shadow follows the body.

Afterwards check the game's crash logs and BLT log for anything naming `christie`,
`fps_christie` or `LegendaryArmours.christie`.

## Christie Clover LAS — in-game verification (2026-11-18)

Pack to install: `dist/Christie/Christie_Clover_LAS.zip` → drop `Christie_Clover_LAS` into
`PAYDAY 2\assets\mod_overrides\` (SuperBLT + BeardLib + LAS). It is an experimental, third-person-only
`BODY_ONLY` outfit built from the Christie primitives in `references/Clover-Christie.zip`
(`build_clover_christie.py`), registered as `LegendaryArmours.clover_christie`. **Nothing of this pack
has been in game**, `runtime_verified` is `false`, and there is no `fps_unit`: the arms stay the
heister's own in first person, which is by design and not a defect.

Check its `.sha256` sidecar to identify the installed bytes. Write down resolution, FOV, texture
quality and anisotropic filter before starting.

1. **It loads** — the menu outfits list a Clover/Christie entry; the preview shows the body. A crash
   or a script error fails this item.
2. **Bind pose and fit** — the jacket, trousers and heels in lobby and in game: no collapsed or
   inside-out groups, shoulders and hips not torn, soles on the floor. Offline bind-joint positions
   differ from the LAS template by up to 5 cm, so this is the item that decides whether the direct
   bind holds in animation.
3. **Normal maps** — light a shoulder and a thigh from the side. The builder preserves the glTF
   normal maps' Y+ orientation; this is not the raw Source normal-map path. Check for dents where
   the materials should look raised. Offline channel agreement is not an in-game result.
4. **The lace cutout** — the skirt slit. Offline it is an approximated alpha test and its shadow is
   opaque. Fail: a hard rectangular edge, fringe, or a shadow that still shows the cut-out piece.
5. **First person** — heist with a weapon out: the arms are the heister's own and move normally
   (there is no `fps_unit` and nothing should be missing or doubled).
6. **Movement** — sprint, crouch, interact: no popping, elbows bend cleanly, the shadow follows.

Afterwards check the game's crash logs and BLT log for anything naming `clover_christie` or
`LegendaryArmours.clover_christie`.

## OfficeSuite — the jewelry diffuse (2026-11-18)

Pack to install: `dist/Honoka/OfficeSuite.zip` → drop `OfficeSuite` into `PAYDAY 2\assets\mod_overrides\`.
Only the jewelry diffuse changed (`references/Honoka/Tex_23(L_23)2.dds`, D50); the geometry, the
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

## OfficeSuite — the palms are cut, and no glove is spawned over them (2026-11-25, D60/D62/D63/D65)

Install `dist/Honoka/OfficeSuite.zip` as above. The body has no hands in it: everything from where
the palm begins outwards is gone — and since D62 the cut sits **past that line**, inside the wrist
(**1.25 cm** since D65, `palm_cut` in `BUILD_INFO.json`: `extend_cm` and `clipped_to_cm` both `1.25`,
`kept_to_cm` 0.61 / 0.53 after the slim), so the arm
continues down into the heister's glove instead of ending above it — and the rim is capped. The plane
is still D60's: through the PD2 `Hand` joint, perpendicular to the palm. The pack registers
`officesuite_own_hands.lua`, not the glove adapter: no default glove unit spawns, so the body has no
hands by default, and a glove the player picks by name is the only thing that puts hands on the
character. Offline the sleeve ends read as a clean cuff; what only the game can show:

1. **No vanilla skin at the wrist.** The D59 build showed a salmon-pink band with a seam between the
   sleeve and the black glove — that was the adapter's `hnd_forearms`, a vanilla bare forearm drawn
   outside the outfit. There must be none now: the sleeve, its black cuff and the jewelry cuff, then
   either the cut or the glove. Fail: any second skin band, any band with a seam in it, any vanilla
   `hnd_glv_heistwrinkled` glove at the cuff.
2. **No hands by default.** With gloves on "Default" the character's hands must be *absent* where the
   outline of a hand would be: the sleeve runs on past the wrist into a capped end, and no stock bare
   hand shows beside it. This is the D60 state and it is intended to look handless.
   **The wrist is the D62/D63/D65 fix:** the D60 build ended in a flat cap in mid-air, above the
   heister's glove, with a visible gap; the D62 build closed the gap by cutting 4 cm into the palm
   and came out through the glove instead. The cap must now sit *inside* the glove and stay there:
   no gap above the cuffs, no ring of background between the sleeve end and the glove, and **no
   skin showing through or around the glove** at the wrist, in any pose. Move the hand, aim, and
   reload — a spot of skin that appears on the glove in one pose is the extension being too deep.
   D63 cut 1.5 cm and that wedge of skin was still there in the first-person screenshots of
   2026-11-25; this build cuts 1.25 cm, which takes the arm's fattest half-centimetre out. If a wedge
   survives this one, the lever is the arm's radius at the cut, not its depth.
3. **A chosen glove wins.** Equip a named glove (Bone Mittens): it must spawn over the cut and read
   as the character's hands, with the sleeve's cuff still outside it and no gap between them, and the
   arm's capped end hidden inside it. Then go back to "Default": the glove must disappear again
   rather than stick.
4. **The first-person arms match.** The `fps_officesuite` arms are cut on the same plane; a weapon
   held and a reload should show the sleeve running on past the wrist and into the glove, with the
   cut end hidden inside the glove, never a hand modelled in the outfit and never a vanilla skin
   band at the wrist — with a glove equipped, the glove is what holds the weapon.
5. **The shadow.** The trimmed shadow caster is cut too: look at the character's own shadow on the
   ground while turning — no hand, and no hole where the hands used to be.

The same checks apply to `OfficeSuite_Head` (its body is this body), and to the Hila override
below without the hook: there the hands are Hila's stock gloves, which the override keeps so a
chosen glove has something to land on.

## Native Hila body + head override (no LAS)

Install only `dist/Honoka/OfficeSuite_Miranda_Romance_over_Hila.zip` for Hila, following the
[install notes](../renders/honoka/model/over-hila/README.md). Select Hila's default outfit and gloves.
The ZIP was checked offline; these steps still need the game:

1. In the lobby/menu, rotate Hila: OfficeSuite's black jacket, light shirt and jewelry, and Miranda's
   Romance head should all show together, with no pink materials or missing triangles.
2. Start an offline heist. Check the third-person model moving and reloading; look for wrist gaps,
   neckline flicker, shading or shadow artifacts, and knee deformation. First-person arms should
   still be Hila's. **The wrists are the new bytes (D60/D62/D63):** the outfit's palms are cut 1.5 cm
   past the line where the palm begins, so the sleeve runs on into its cuff and the capped end sits
   inside the glove without coming through it, and **Hila's own stock gloves** —
   kept in the pack, node and all, so a chosen glove still has somewhere to land — are what the game
   puts over it. The LAS pack reaches the same sleeve end under `LegendaryArmours.officesuite` and
   spawns no default glove at all (D60). Check the hands from the front, the side and while the hand
   closes on a weapon: no gap between the glove and the sleeve, no capped rim showing past the glove
   lip, no vanilla skin band above the glove, no second pair of hands.
3. Mask up and check the mask, a heavier vest, and a carried deployable. These use the original
   Hila attachments; check that the fit is acceptable. Alternate outfits/gloves are not the target.

## OfficeSuite_Head — whole character with the Romance head (D56)

Install `dist/Honoka/OfficeSuite_Head.zip`, then pick `OfficeSuite + Miranda Head` under
`LegendaryArmours.officesuite_head` on any heister. This pack is `replace_all`: it brings the
body **and** the head, and hides the mask. The checks that the offline build cannot make:

1. **The head is the Romance one, on the body.** Face, hair and skin tone should match
   `OfficeSuite_Miranda_Romance_over_Hila.zip`'s Hila; the eyes and teeth are Hila's stock ones, so
   they should not be missing or doubled.
2. **The lashes (the open risk).** The donor's lashes are one diffuse whose alpha is the cutout,
   drawn with `opacity:`. Look at the eyes up close and at an angle: the lashes should read as
   lashes, not as solid black quads and not as a hole in the face. This is the one thing no render
   here settles.
3. **No second head, no floating mask.** The heister's stock head must not show through or beside
   the pack's, and the mask must not appear on the face. Swap to another heister and back.
4. **The neck.** Rotate the head in the lobby and reload in a heist: no gap or stretched skin where
   the pack's head meets OfficeSuite's collar, and no head that follows the hips instead of the head.
5. **No hands by default, and no vanilla skin (D60).** With gloves on "Default" in the blackmarket,
   nothing must spawn over the cut: no `hnd_glv_heistwrinkled` glove at the cuff, no bare heister
   hands beside the sleeve, and above all no `hnd_forearms` band — the salmon bare-forearm piece
   D59's adapter put there. The pack ships `officesuite_head_own_hands.lua` for this. Then equip a
   named glove (Bone Mittens): it must spawn over the cut as the character's hands.
6. **The body is the cut body.** Wrists read as D60 (cuff and jewellery cuff, then the cut, or the
   player's glove); jewellery, suit colourway and the first-person arms match `OfficeSuite`'s own
   checks above.

`OfficeSuite` itself is unchanged by this pack: it keeps the stock head and its `BODY_ONLY`
registration, so both entries should sit in the menu and both be selectable.

## `Miranda_Lawson_VO_over_Hila` — audio only (2026-11-24, dropped 2026-11-25)

**This pack no longer ships (D61).** It was installed on 2026-11-24 and vanilla Hila still played;
the keying was re-verified against the loaders and was right, so the route itself never produced a
line. The id-keyed stream pack below does, and it is the only one in `dist/Hila/`. The steps stay as
the record of what was asked of it, and as the checklist a future pack on that route would start
from; the packaging contract (and the reason for the drop) is
[`docs/pd2-voice-mod-install.md`](../pd2-voice-mod-install.md) §1–§6.

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
expect. 858 `.stream` files named after Hila's voice-line ids, 27 ids left vanilla (Wwise Vorbis in
the vanilla bank). **Heard in game on 2026-11-25: the user installed it and reported it works** — this
route replaces Hila's barks where the BeardLib pack did not. That report also named two clips cut
inside a word, which are re-cut below; the bytes it heard are not the tracked ones.

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

2. **No loader noise.** `mods/logs/` should show the mod folder loaded and no error from it: the pack
   has no Lua, no hooks and no XML to parse beyond `<mod name=…>`.
3. **Line-by-line, not event-by-event.** A heist-scripted line Hila speaks as an NPC keeps Hila's
   voice (the `robbers_mission_gen` bank); a heister bark that is still Hila's is either one of the 27
   Vorbis ids (`voice_lines_vox/miranda_lawson/hila_vorbis_ids.csv`) or a second pack writing the same
   ids after this one.
4. **Length.** A replacement keeps its clip length (0.22–1.95 s), so a replaced line can be shorter or
   longer than the vanilla one. No subtitle changes: those still show Hila's line.
5. **First person.** Nothing to check — audio only.

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
3. **The features are the ped's own.** Eyebrows, both lips (with the mouth's dark slit), nostrils and
   the ears should sit where they did before: nothing blurry, nothing doubled, no pale or thin mouth,
   and no drawn outline around it.
4. **The hair reads as hair.** The cutout fringe is `ALPHA_MASKED` with `alpha_ref 0.05`: it should
   not flicker, halo or draw as a solid band against the forehead, and the scalp should not show
   through at the crown.
5. **The head still fits the suit.** No gap or stretched skin at the collar, the menu portrait
   matches the in-game head, and the HUD icon is the same face.
