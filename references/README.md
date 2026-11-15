# Reference PAYDAY 2 Mod Archives

This directory contains the reference PAYDAY 2 mod archives used as binary/skeleton templates for building the LAS outfits and female heister head-replacement `mod_overrides` packages:

| Archive | Purpose | Consumed By |
|---|---|---|
| `2b.rar` | Reference Legendary Armour Skins (`LAS`) pack (`2B - LAS`) providing the 136-bone Diesel `.model` skeleton template (`2b.model`, `fps_2b.model`) | `tools/pd2-las/` (templates, unpacked to `build/pd2-las/2b/` by `recover_env.sh`); `tools/pd2-port/extract_las_rig.py` (the rig contract `reference/las_rig.json` was extracted from its model once) |
| `Christie.zip` | Not a reference but a source: the Dead or Alive 5 Christie model as Source-engine files (`.mdl` / `.vvd` / `.vtx` + VMT/VTF) | the tracked packs `dist/Christie_LAS.zip` and `dist/Christie_LAS_Slim.zip` (build tool deleted 2026-11-14; the packs remain) |
| `Outfit for Honoka-109-1-1-1628020933.zip` | Not a reference but a source: a Dead or Alive Xtreme Venus Vacation (DOAXVV) costume — the "Secret Report" office-lady outfit for the custom character Honoka (`Honoka_DOAXVV_Secret_Report.{TMC,TMCL,PHYD,texch,dlicon}`) | `tools/pd2-las/tmc.py` + `tmc_export.py` read the TMC (Route B, 2026-11-14); exports extracted under `Honoka/` (OBJ + DDS + `Honoka_DOAXVV_Secret_Report.rigged.glb`, the 171-joint skinned export; findings in `docs/pd2-las/honoka-tmc-format.md`); source of the skin weights and joint binds the `Honoko2` LAS pack transfers, and of its `.dae` garment selection |
| `Honoka/` | Unpacked Honoka sources: 3rd-party OBJ/DDS dump, the Collada export `Honoka_DOAXVV_Secret_Reportout.dae` the Honoko packs are built from, the user's alternate suit diffuse `Tex_07(L_7) 2.dds` (supplied 2026-11-15: the suit's UV layout repainted black jacket over orange shirt, the `Honoko4` colourway, D44), plus this repo's own skinned glTF export (`Honoka_DOAXVV_Secret_Report.rigged.glb`) rebuilt from the TMC by `tools/pd2-las/tmc_export.py` | `tools/pd2-las/tmc.py` / `tmc_export.py`; `build_honoko2_dae.py` reads the `.dae`; findings in `docs/pd2-las/honoka-tmc-format.md` |
| `Ada Wong over Joy.7z` | Reference Joy `mod_overrides` package (`units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model`) | `tools/build_joy_head_mods.py` |
| `Heister - FPS Gloves in TPS 2.zip` | Reference heister third-person & Safe House `.model` templates (`npc_criminal_female_1.model`, `npc_criminal_bonnie.model`, `npc_criminal_sydney.model`, `npc_criminal_female_chill.model`, `npc_criminal_bonnie_chill.model`, plus the Joy, Wild and Max units) | `tools/build_joy_head_mods.py` |
| `npc_criminals_ecp_female.7z` | Reference Hila `mod_overrides` unit (H3H3 collaboration heister, DLC folder `ecp`): `npc_criminal_ecp_female.model` / `_menu.model`, both `.object` files and `mtr_criminal_ecp_female[_cc].material_config`; her hair is `g_hair_mask_off` / `g_hair_mask_on` and her head `g_head` carries two atoms (head, 3D eyelashes) on `mtr_head` + `mtr_lashes` | `tools/build_joy_head_mods.py` (`_emit_hila_packages`) |


**Supplied textures:** `EYE_Diff.png` — the Miranda Lawson eye diffuse (256×256 RGB: blue iris, veined sclera),
supplied by the user on 2026-11-15, and repainted again the same day (rounder iris, 1.38x the first
repaint's, with a catchlight; the earlier bytes stay in git history). It is a repaint of `EYE_Diff.png`
inside `models/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip`,
kept here as its own input because the archives are read in place and not edited. It is the eye texture
of the two Hila packs only (`dist/Miranda_{L4D2,Romance}_over_Hila.zip`): `load_hila_eye_texture()` in
`tools/build_joy_head_mods.py` magnifies it about its centre into the head atlas' eye quadrant, by a
factor measured off the iris it finds in the source (2.03 since the second repaint, D43). The nine other
head packs do not read it: the eight Miranda ones keep the synthesised eye
(`build_crisp_miranda_eye_texture`), Geralt keeps Rust's own.

**Not here:** the Geralt of Rivia L4D2 port archive lives in `models/Geralt.7z` (it was tracked in both
directories, byte for byte, which is only a way to restore the wrong copy); `tools/build_joy_head_mods.py`
reads the `models/` one.

**Removed source inputs:** the Skyrim source archives `1.zip` through `5.zip` were deleted from the repository on 2026-11-04, after the Skyrim outfit port was cancelled, and the tools that read them on 2026-11-13 (`docs/pd2-las/DECISIONS.md`, D33). Do not fetch or republish the archives unless the user explicitly reopens the work.
