# Arivus over Old Hoxton v2 — beside v1

The [offline preview](arivus_over_hoxton_v2_sheet.png) is three pairs of panels: the portrait,
the back three-quarter and the crown from above, v1 on the left of each pair and v2 on the
right. Every panel is the pack's own `g_head_old_hoxton` drawable over flat-coloured body parts,
drawn by the same rasteriser from the same atlas, so a difference between two panels is a
difference between the two packs. Suit and gloves use placeholder colours, and this is a
diffuse-only software render: it is not evidence of the game's lighting, animation or runtime
behaviour.

**What v2 is.** `references/templates/Arivus Head BLEND.7z` (the tracked archive the
[decisions record](../../../../pd2-las/DECISIONS.md#d96--arivus-v2-ships-the-owners-blender-scene-as-a-second-head-pack)
describes) holds the owner's Blender scene of this head — the same mesh, re-rigged onto three bones and
re-sculpted at the crown and the back of the skull, with v1's atlas packed in. Measured against
v1's shipped drawable, the scene is 0.03 cm different at the median vertex, 0.26 cm at p95 and
0.68 cm at the worst, and every move of more than 0.3 cm is above z 168.6 cm: the neck, the
UVs and the skin weights are v1's. That is what the sheet is for — side by side, the crown and
the back of the head are where the two differ, and nowhere else is.

**What v2 is not.** It is not a new head and not a re-texture. The 2048² atlas, its cutout mip
chain, the flat normal map and the icon are byte-identical to v1's, because both packs are built
from the same diffuse (`references/textures/old_hoxton_head_df.dds`) — the scene's own packed
diffuse was the earlier edit, and the builder supplies the tracked atlas instead. The two material configs, the two `.object` files and the heist, menu and Safe
House units are v1's own code and v1's own bytes.

**The neck.** v1's D79 skirt is in the scene already — 22 vertices at z 148.001 — so v2 ships
the owner's skirt rather than stitching a second one over it (which grew the mesh by 27 vertices
when tried). A ray-parity test against the suit's own body says all 22 vertices are enclosed on
the heist, menu and Safe House models.

Rebuild with `make -sC tools/pd2-las heads_v2`; the mesh it builds from is the tracked digest
`references/arivus_v2/head_v2.json`, which `tools/pd2-las/arivus_v2_from_blend.py` writes from the
scene. Install the ZIP's `Arivus over Hoxton v2` folder into `PAYDAY 2/assets/mod_overrides/`.
No in-game verification has been performed
([checklist](../../../../pd2-las/in-game-checklist.md)).
