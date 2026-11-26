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

**The neck.** The ped's neck is cut in a V — z 159.4 across the throat, z 164.9 at the back —
while the suit's collar rim only reaches z ~159.8–160.5. D75 leaves the ped where it lands, drops
the cut rim to the collar's height (full weight behind and at the sides, fading out across the
throat so its length is kept) and closes it with a skirt tucked to 0.35 of the rim's radius that
ends at z 148 inside the suit; a ray-parity test against the suit's own body says all 23 skirt
vertices are enclosed on the heist, menu and Safe House models. The sheet's back panel is the view
that changes most: it used to show a band of the throat's far wall through the collar opening.

All three shipped models also now weight **the palette their `SkinBones` section actually lists**
(`Spine2, Neck, Head` → indices 0–2). The drawable previously carried `BLENDINDICES 3` on 4,595 of
4,596 vertices, one past the end of a three-entry palette — invisible to any bind-pose render,
because bind-pose cancels the skinning matrices. That is the defect
[`MODLOG.md`](../../../../../tools/pd2-las/MODLOG.md) D73 reported as unresolved; these bytes fix it
in the pack rather than in the exporter, and the shipped GLB's skin is now 3 joints with no repair
warning.

Rebuild with `make -sC tools/pd2-las heads`, then `make -sC tools/pd2-las glb`
for the separate bind-pose interchange export. Install the head ZIP's contained
`Arivus over Hoxton` folder into `PAYDAY 2/assets/mod_overrides/`. The GLB ZIP is
not an installable mod. No in-game verification has been performed: the neck's
deformation under the `Neck` and `Head` bones, and how the game's culling treats
the tucked skirt, are the checks still waiting for a person with the game
([checklist](../../../../pd2-las/in-game-checklist.md)).
