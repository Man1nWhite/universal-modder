# Source Character Model Archives

This directory contains the upstream character model archives ported into PAYDAY 2:

| Archive | Source Format | Consumed By | Outputs in `dist/` |
|---|---|---|---|
| `l4d2_miranda_lawson_1.zip` | Left 4 Dead 2 `miranda_rochelle.vpk` (`.mdl` / `.vvd` / `.vtx` / `.vtf`) | `tools/pd2-las/build_models.py`, `tools/pd2-las/build_las.py`, `tools/build_joy_head_mods.py` | `dist/Miranda_LAS.zip`, `dist/Miranda_L4D2_over_{Joy,Clover,Bonnie,Sydney}.zip` |
| `PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip` | Mass Effect 2 COLLADA `.dae` (`Miranda Lawson (Romance) - Adjusted Version.dae`) + `.png` textures | `tools/pd2-port/build_las_pack.py`, `tools/build_joy_head_mods.py` | `dist/lawson_las.zip`, `dist/Miranda_Romance_over_{Joy,Clover,Bonnie,Sydney}.zip` |
