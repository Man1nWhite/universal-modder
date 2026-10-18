# Miranda LAS — in-game verification checklist

Pack to install: `build/pd2-las/Miranda_LAS` (or the zipped copy
`build/pd2-las/Miranda_LAS.zip`) → drop the `Miranda_LAS` folder into
`PAYDAY 2/mods/`. Requires BeardLib + the LegendaryArmours (LAS) framework,
exactly like the 2B reference pack (`2b.rar`).

Nothing here can be verified offline — every item needs the running game.
Report failures with the item number and a screenshot.

## Install sanity

1. Game reaches the menu without script errors (BeardLib console clean).
2. The outfit appears under armor skins as **Miranda Lawson** with the
   face-crop icon.

## Third person (main view)

3. Full body visible in the lobby preview and in-game: head, torso, arms,
   legs, boots — no missing groups (`g_body`, `g_head` enabled per
   `miranda.object`; `s_body` handled by the engine).
4. **Texture orientation** — UVs were written with the p2mt GLTF import
   convention `v = 1 − v_src`. If any texture reads upside-down or mirrored
   (watch the face: lips above eyes is the failure mode), it is a single
   sign flip in `build_models.py` (`transfer_group`, the `g.uvs` append)
   plus the same flip in `tests/test_build_models.py`.
5. **Winding** — surfaces opaque from all angles; no inside-out faces
   (signed volume matches the 2B reference offline, so this should hold).
6. Skin weights: elbows, knees, shoulders bend smoothly; no candy-wrapper
   or spiking at joints. Fingers are the weakest area of the retarget —
   expect minor noise there; the face (all bones under `Head`) shares one
   rigid fit and should read cleanly.
7. Face intact at close range: eyes, nose, lips present; slight lip/jaw
   softness is known/acceptable for v1.
8. Shadow (`s_body`) renders under the character.

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
