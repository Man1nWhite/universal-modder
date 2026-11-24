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
3. **First person** — a heist with a weapon out, reload and interact once: the outfit's sleeves show
   from the wrists to the hands, the jewelry cuff and the bra straps read as part of the outfit, the
   heister's vanilla gloves spawn at the wrist cut, and nothing is missing, duplicated or clipped.
   The cuff and straps are arm-weighted geometry by construction; the hands stay the heister's.

Everything else for this pack is covered by the 2026-11-15 sections of the render pages; the
captures there predate this texture and cannot be used to judge the jewelry, and predate the
first-person unit entirely.

## Native Hila body + head override (no LAS)

Install only `dist/Honoka/OfficeSuite_Miranda_Romance_over_Hila.zip` for Hila, following the
[install notes](../renders/honoka/model/over-hila/README.md). Select Hila's default outfit and gloves.
The ZIP was checked offline; these steps still need the game:

1. In the lobby/menu, rotate Hila: OfficeSuite's black jacket, light shirt and jewelry, and Miranda's
   Romance head should all show together, with no pink materials or missing triangles.
2. Start an offline heist. Check the third-person model moving and reloading; look for wrist gaps,
   neckline flicker, shading or shadow artifacts, and knee deformation. First-person arms should
   still be Hila's. **The wrists are the new bytes (D55):** the Hila override now shows the outfit's
   own skin and black sleeve cuff where the vanilla blue gloves used to be, and the LAS pack does the
   same under `LegendaryArmours.officesuite`. Check both from the front, the side and while the hand
   closes on a weapon: no blue glove, no bare wrist band, no gap where the cuff meets the hand.
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
5. **No vanilla glove, and not the stock hands (D58).** With gloves on "Default" in the blackmarket,
   the wrists must show the outfit's own hands — no `hnd_glv_heistwrinkled` band at the cuff, and no
   bare heister hands beside the modelled ones (that would be the stock hands failing to hide).
   Both packs ship `*_own_hands.lua` for this. Then equip a named glove (Bone Mittens): it must
   spawn over the hands, because a chosen glove is allowed to win.
6. **The body is unchanged.** Wrists read as D55 (the outfit's own skin and cuff, no blue glove);
   jewellery, suit colourway and the first-person arms match `OfficeSuite`'s own checks above.

`OfficeSuite` itself is unchanged by this pack: it keeps the stock head and its `BODY_ONLY`
registration, so both entries should sit in the menu and both be selectable.

## `Miranda_Lawson_VO_over_Hila` — audio only (2026-11-24)

No LAS, no head pack: SuperBLT + BeardLib 5.1.0+ and the pack folder in `mods/`. Nothing of it has
been heard in game; the packaging contract is [`docs/pd2-voice-mod-install.md`](../pd2-voice-mod-install.md).

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
