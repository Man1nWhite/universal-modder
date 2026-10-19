# Miranda LAS — in-game verification checklist

Pack to install: `build/pd2-las/Miranda_LAS` (or the zipped copy
`build/pd2-las/Miranda_LAS.zip`) → drop the `Miranda_LAS` folder into
`PAYDAY 2\assets\mod_overrides\`. Requires BeardLib + the LegendaryArmours
(LAS) framework, exactly like the 2B reference pack (`2b.rar`), which
installs the same way (its `main.xml` + `hooks/` are loaded by BeardLib's
AddFramework from `assets/mod_overrides/`).

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
8. Shadow (`s_body`) renders under the character. Ground contact: the
   boot soles may sit a few cm below the target ground plane (z ≈ -12 cm
   offline) — check for floor clipping and report if visible.

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
