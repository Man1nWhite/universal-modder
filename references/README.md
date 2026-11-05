# Reference PAYDAY 2 Mod Archives

This directory contains the reference PAYDAY 2 mod archives used as binary/skeleton templates for building the LAS outfits and female heister head-replacement `mod_overrides` packages:

| Archive | Purpose | Consumed By |
|---|---|---|
| `2b.rar` | Reference Legendary Armour Skins (`LAS`) pack (`2B - LAS`) providing the 136-bone Diesel `.model` skeleton template (`2b.model`, `fps_2b.model`) | `tools/pd2-las/bootstrap.sh`, `tools/pd2-port/build_las_pack.py` |
| `Ada Wong over Joy.7z` | Reference Joy `mod_overrides` package (`units/pd2_dlc_joy/characters/npc_criminals_joy_1/npc_criminal_joy_1.model`) | `tools/build_joy_head_mods.py` |
| `Heister - FPS Gloves in TPS 2.zip` | Reference female heister third-person & Safe House `.model` templates (`npc_criminal_female_1.model`, `npc_criminal_bonnie_1.model`, `npc_criminal_sydney_1.model`, `chill_npc_criminal_female_1.model`, `chill_npc_criminal_bonnie_1.model`) | `tools/build_joy_head_mods.py` |


**Not here:** the Geralt of Rivia L4D2 port archive lives in `models/Geralt.7z` (it was tracked in both
directories, byte for byte, which is only a way to restore the wrong copy); `tools/build_joy_head_mods.py`
reads the `models/` one.

**Removed source inputs:** the original Skyrim source archives `1.zip` through `5.zip` were deleted from the repository on 2026-11-04 after the skyrim outfit port was cancelled. The retained `tools/pd2-las/` scripts require those user-supplied inputs to rebuild; do not fetch or republish them unless the user explicitly reopens the work.
