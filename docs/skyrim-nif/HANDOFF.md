# Skyrim clothing → PAYDAY 2 LAS — archived handoff

> **CANCELLED by the user on 2026-11-04.** The in-game model remained
> unacceptable after repeated attempts. There is no pack to install or
> distribute. See [`STATUS.md`](STATUS.md).

The original source archives, the built pack and its checksum were removed from
the current branch, along with every note that described the outfit. The
conversion and inspection scripts remain under `tools/pd2-las/` and
`tools/skyrim-nif/`, but cannot run without re-supplying the sources.

## What is still worth knowing

These are the constraints that made the port fail, written without reference to
the outfit that produced them — they apply to *any* layered clothing source:

- **Layered BodySlide sheets poke through each other.** A body, a shirt and a
  jacket exported separately all occupy the same space; at heister scale the
  inner layers surface through the outer one. Weld coincident rows
  (`weld_open_seams`), never the *overlap* rows — welding an overlap folds the
  sleeve into spikes.
- **Sleeves stop short of the wrist.** Clothing authored to be worn *with hands*
  ends before the hand joint, and PD2 spawns the glove at the joint, so the gap
  reads as a floating glove. `extend_sleeves_to_wrist` redistributes the last
  stretch of each arm layer along the forearm axis.
- **Collars and shirt tips ride out over the jacket.** Copy the nearest jacket
  vertex's influence list onto the under-layer across the shoulder band
  (`follow_layer_weights`) rather than moving geometry.
- **A physics-driven skirt does not survive.** Diesel heister models have no
  cloth chain; a skirt weighted to spring bones goes rigid or clips through the
  thighs. Prefer a source whose skirt is rigidly thigh-weighted, or skip the
  skirt entirely.
- **A retarget that lands every joint says nothing about the flesh between
  them.** Measure bust protrusion and neck opening against *both* rigs; see
  note 28 in `knowledge/games/payday-2/las-moog-outfit-porting.md`.
- **Skin needs uniform albedo, normal and gloss.** Blotches survived two of the
  three fixes; the third was the diffuse itself.

Do not restore the old package or resume the port unless explicitly asked.
Earlier Git commits still contain the removed files; this cleanup removes them
from the current branch tip, not from history.
