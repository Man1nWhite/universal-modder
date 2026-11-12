# Miranda LAS — in-game verification checklist

Pack to install: `build/pd2-las/Miranda_LAS` (or the zipped copy
`build/pd2-las/Miranda_LAS.zip`) → drop the `Miranda_LAS` folder into
`PAYDAY 2\assets\mod_overrides\`. Requires BeardLib + the LegendaryArmours
(LAS) framework, exactly like the 2B reference pack (`2b.rar`), which
installs the same way (its `main.xml` + `hooks/` are loaded by BeardLib's
AddFramework from `assets/mod_overrides/`).

Nothing here can be verified offline — every item needs the running game.
Report failures with the item number and a screenshot.

## Ten minutes: the rebuild of 2026-11-11

Six packs were rebuilt that day: `Miranda_LAS`, `Miranda_Busty_LAS` and the four
`Miranda_L4D2_over_*` head packs. What changed, and what was measured offline,
is in `docs/audits/2026-11-11-miranda-mips-and-object.md`. None of it has been
seen in the game. These five steps are what would settle it. Write down the
resolution, the FOV setting, the texture quality and the anisotropic filter
before you start: the offline figures assume 1080p or 2160p, the game's default
field of view and no anisotropic filter.

Install `Miranda_LAS` and `Miranda_Busty_LAS` together; they are separate
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
   `build/pd2-las/previews/uvcheck_*` — face/outfit/eyes all land
   anatomically). The stored convention is the p2mt GLTF import
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

## Release gate (not a bug)

16. Mass Effect 2 asset redistribution rights — the textures/geometry are
    converted from the L4D2 Miranda mod, itself derived from ME2 assets.
    Do not publish the pack publicly until that is resolved. Offline
    testing by the pack owner is fine.

## Guide watch items (ModWorkshop LAS/MOOG guide)

17. **Normal-map orientation** — PD2 expects OpenGL-style (Y+) normal maps;
    the L4D/Source normals should already match. If bumps light up inverted
    (creases look like ridges), flip the green channel of the `*_nm.texture`
    files (guide: "To format a DirectX-style normal map for PAYDAY 2").
18. **Contour outline** — stand the character behind a wall: the four TPP
    skin materials carry `CONTOUR` + contour variables per the guide, so a
    colored silhouette should show through geometry. No outline = the
    contour variables need different values.
