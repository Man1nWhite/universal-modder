# Christie source rebuild and fit notes

`Christie_LAS.zip` is rebuilt from `references/Christie.zip`, not from the old
compiled Christie outfit or its deleted builder. The new pack has third- and
first-person models, no head drawables, and no authored hands or bare wrist
skin at the cuff. LAS uses `replace_body`, not `replace_all`, and the included
glove adapter is intended to restore the heister's default/changeable gloves.
The heister's head and gloves are supplied by the game or other mods.
`Christie_LAS_Slim.zip` was later removed from distribution at the user’s request. To install the new base outfit, extract
its `Christie_LAS` folder to `PAYDAY 2/assets/mod_overrides/` with SuperBLT,
BeardLib and Legendary Armour Skins installed. Remove an older `Christie_LAS`
folder first so the files do not mix; keep any backup outside that directory.

The build maps the source rig to the 2B player skeleton, aligns arm pivots,
blends source elbow weights, removes triangles beyond the wrist plane and
hand-dominated vertices, and removes distal bare skin at the cuff. The FPS
arms and both shadow meshes are derived from the same cut body. The four
source material pairs are converted from VTF to DDS, with swizzled normals,
attenuated gloss masks and complete mipmaps. The separate
`tools/pd2-las/christie_sleeve_gloss.py` pass classifies faces by arm weights
and rasterises their wrapped UVs, including triangles crossing the atlas
boundary; feathering also wraps across atlas edges. At mip 0, it skips any BC3 block shared
with a face classified as non-sleeve, plus a one-texel sampling border. It
then regenerates filtered lower-mip alpha while preserving RGB bytes at every
level. This classification and its UV-overlap protection are approximations:
coarser mips mix neighboring texels, and the in-game shader has not been
checked. `BUILD_INFO.json` records per-material block counts, source and
payload hashes, fit measurements and `runtime_verified: false`.

Offline checks for the actual packaged bytes cover archive integrity, payload
hashes, LAS and glove hooks, XML and DDS mip chains; the visible, LOD and
shadow geometry of both models is decoded and checked for distal wrist
vertices and hand-dominated vertices. The packaged Lua hooks also run against
the LAS loader and BeardLib behavior harness for default/custom gloves and the
stock-hands fallback. The gloss tests check wrapped UV seams, BC3 block protection, unchanged RGB,
filtered lower mips and the actual ZIP against freshly converted source maps.
The model atom audit passes; a numerical elbow sweep at 22, 45 and 70 degrees
checks finite coordinates and bounded edge growth.
A coarse software-rendered sweep of those poses was also inspected; it is not
a substitute for game lighting or animation. Two builds in the pinned
environment matched byte-for-byte, including a fresh-tree rebuild. The old
2026-11-14 rebuild checklists and audits refer to different bytes and do not
verify this pack.

These checks do not establish in-game fit. In particular, inspect the head/neck
join, cuffs with default and modded gloves, first-person weapons, both sleeves
at idle and flexion, and shadows in PAYDAY 2. The software preview omits the
runtime head and gloves; dark/open cuff interiors are expected in that isolated
view but glove coverage and clipping must be judged in game. No game test has
been performed. The prior screenshot reports apply to older builds only.
