# Arivus over Old Hoxton — compiled model preview

The [offline preview](arivus_over_hoxton_sheet.png) shows the rebuilt
`dist/Arivus/Arivus_over_Hoxton.zip`: front, three-quarter, back, full rig and
HUD icon. Suit and gloves use placeholder colours. This is a diffuse-only software
render, not evidence of the game's lighting, animation or runtime behavior.

The Arivus head and hair geometry still come from the Random4 ped in
`references/1581859199_135363.rar`. The new
`references/old_hoxton_head_df.dds` is an edited **Arivus atlas**, despite its
name: its face, eye and hair regions already match the Arivus UVs. The builder
preserves the supplied BC3 base-level blocks exactly, adds coverage-preserving
mipmaps for the cutout hair, and regenerates the icon from the supplied diffuse.
The normal map remains flat. The heist, menu and Safe House models are unchanged.
The previous procedural shave is not applied to the supplied artwork.

Rebuild with `make -sC tools/pd2-las heads`, then `make -sC tools/pd2-las glb`
for the separate bind-pose interchange export. Install the head ZIP's contained
`Arivus over Hoxton` folder into `PAYDAY 2/assets/mod_overrides/`. The GLB ZIP is
not an installable mod. No in-game verification has been performed. The known
out-of-range head skin palette indices described in
[`MODLOG.md`](../../../../../tools/pd2-las/MODLOG.md) D73 remain unresolved;
the GLB exporter repairs them for its own bind-pose export only.
