# Source and Reference Archives

Source character archives and reference PAYDAY 2 mods used by the build pipelines. The older
`models/` source archives now live here; packaged downloads are grouped under `dist/`. See the
[render index](../docs/renders/README.md) for previews and their source provenance:

## Character sources

| Archive | Source Format | Consumed By | Outputs in `dist/` |
|---|---|---|---|
| `l4d2_miranda_lawson_1.zip` | Left 4 Dead 2 `miranda_rochelle.vpk` (`.mdl` / `.vvd` / `.vtx` / `.vtf`) | `tools/pd2-las/build_models.py`, `tools/pd2-las/build_las.py`, `tools/pd2-las/build_busty_variant.py`, `tools/build_joy_head_mods.py` | `dist/Miranda_L4D2/Miranda_L4D2_LAS.zip`, `dist/Miranda_L4D2/Miranda_L4D2_Busty_LAS.zip`, `dist/Miranda_L4D2/Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney,Hila}.zip` |
| `PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip` | Mass Effect 2 COLLADA `.dae` (`Miranda Lawson (Romance) - Adjusted Version.dae`) + `.png` textures | `tools/pd2-port/build_las_pack.py`, `tools/build_joy_head_mods.py` | `dist/Miranda_Romance/Miranda_Romance_LAS.zip`, `dist/Miranda_Romance/Miranda_Romance_over_{Joy,Clover,Bonnie,Sydney,Hila}.zip` |
| `Geralt.7z` | Witcher 3 Geralt of Rivia L4D2 port archive (a subscribed Garry's Mod addon: `.mdl`/`.vvd`/`.vtx`/`.vtf`, LZMA `.gma` layout) | `tools/build_joy_head_mods.py` | `dist/Geralt/Geralt_over_Rust.zip` |

## Templates and other references

| Archive | Purpose | Consumed By |
|---|---|---|
| `2b.rar` | Reference Legendary Armour Skins (`LAS`) pack (`2B - LAS`) providing the 136-bone Diesel `.model` skeleton template (`2b.model`, `fps_2b.model`) | `tools/pd2-las/` (templates, unpacked to `build/pd2-las/2b/` by `recover_env.sh`); `tools/pd2-port/extract_las_rig.py` (the rig contract `reference/las_rig.json` was extracted from its model once) |
| `Christie.zip` | Dead or Alive 5 Christie model as Source-engine files (`.mdl` / `.vvd` / `.vtx` + VMT/VTF) | `tools/pd2-las/build_christie_source.py` builds `dist/Christie/Christie_LAS.zip` |
| `Clover-Christie.zip` | Blender project and rigged GLB containing the Christie outfit and other meshes | `tools/pd2-las/build_clover_christie.py` selects the Christie mesh for `dist/Christie/Christie_Clover_LAS.zip` |
| `Outfit for Honoka-109-1-1-1628020933.zip` | Source: a Dead or Alive Xtreme Venus Vacation (DOAXVV) costume — the "Secret Report" office-lady outfit for the custom character Honoka (`Honoka_DOAXVV_Secret_Report.{TMC,TMCL,PHYD,texch,dlicon}`) | `tools/pd2-las/tmc.py` + `tmc_export.py` read the TMC (Route B, 2026-11-14); exports extracted under `Honoka/` (OBJ + DDS + `Honoka_DOAXVV_Secret_Report.rigged.glb`, the 171-joint skinned export; findings in `docs/pd2-las/honoka-tmc-format.md`); source of the skin weights and joint binds transferred by `build_honoko2_dae.py` into the tracked Honoka packs (`dist/Honoka/OfficeSuite.zip` and its siblings; the earlier `Honoko2`..`Honoko4` builds of this route were removed on 2026-11-23, D57) |
| `Honoka/` | Unpacked Honoka sources: 3rd-party OBJ/DDS dump, the Collada export `Honoka_DOAXVV_Secret_Reportout.dae` the Honoko packs are built from, the user's alternate diffuses `Tex_07(L_7) 2.dds`, `Tex_07(L_7)3.dds` and `Tex_23(L_23)2.dds` (supplied 2026-11-15..18: `Honoko4` suit black jacket over orange shirt, D44; `OfficeSuite` suit black jacket over light shirt plus updated jewelry diffuse, D45/D46/D50), plus this repo's own skinned glTF export (`Honoka_DOAXVV_Secret_Report.rigged.glb`) rebuilt from the TMC by `tools/pd2-las/tmc_export.py` | `tools/pd2-las/tmc.py` / `tmc_export.py`; `build_honoko2_dae.py` reads the `.dae`; findings in `docs/pd2-las/honoka-tmc-format.md` |
| `Ada Wong over Joy.7z` | Reference Joy `mod_overrides` package (`units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model`) | `tools/build_joy_head_mods.py` |
| `Heister - FPS Gloves in TPS 2.zip` | Reference heister third-person & Safe House `.model` templates (`npc_criminal_female_1.model`, `npc_criminal_bonnie.model`, `npc_criminal_sydney.model`, `npc_criminal_female_chill.model`, `npc_criminal_bonnie_chill.model`, plus the Joy, Wild and Max units) | `tools/build_joy_head_mods.py` |
| `npc_criminals_ecp_female.7z` | Reference Hila `mod_overrides` unit (H3H3 collaboration heister, DLC folder `ecp`): `npc_criminal_ecp_female.model` / `_menu.model`, both `.object` files and `mtr_criminal_ecp_female[_cc].material_config`; her hair is `g_hair_mask_off` / `g_hair_mask_on` and her head `g_head` carries two atoms (head, 3D eyelashes) on `mtr_head` + `mtr_lashes` | `tools/build_joy_head_mods.py` (`_emit_hila_packages`) |


**Supplied textures:** `EYE_Diff.png` — the Miranda Lawson eye diffuse (256×256 RGB: blue iris, veined sclera),
supplied by the user on 2026-11-15, and repainted again the same day (rounder iris, 1.38x the first
repaint's, with a catchlight; the earlier bytes stay in git history). It is a repaint of `EYE_Diff.png`
inside `references/PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip`,
kept here as its own input because the archives are read in place and not edited. It is the eye texture
of the two Hila packs only (under `dist/Miranda_L4D2/` and `dist/Miranda_Romance/`): `load_hila_eye_texture()` in
`tools/build_joy_head_mods.py` magnifies it about its centre into the head atlas' eye quadrant, by a
factor measured off the iris it finds in the source (2.03 since the second repaint, D43). The nine other
head packs do not read it: the eight Miranda ones keep the synthesised eye
(`build_crisp_miranda_eye_texture`), Geralt keeps Rust's own.

**Removed source inputs:** the Skyrim source archives `1.zip` through `5.zip` were deleted from the repository on 2026-11-04, after the Skyrim outfit port was cancelled, and the tools that read them on 2026-11-13 (`docs/pd2-las/DECISIONS.md`, D33). Do not fetch or republish the archives unless the user explicitly reopens the work.
