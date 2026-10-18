# Lawson pack repair journal

## 2026-10-18 — mod manager lists packs, models remain vanilla

- Report: all three characters retain their faces/suits; packs enabled; BLT present;
  PocoHUD works. Exact loader/game versions and installation paths unknown.
- Searched local knowledge base for PAYDAY 2: no matching prior note.
- Inspected all tracked dist ZIPs: each contains 2 models, 2 material configs,
  19 textures and a README; no main.xml. README wrongly says to install under
  mods/mod_overrides and that BeardLib is optional. It also claims in-game success
  without available evidence.
- Compared material paths with the existing local character object references;
  the packaged material directories agree with those references.
- Chosen route: fix asset-override packaging, not Lua gameplay hooks or geometry.
  Source of truth: BeardLib 5.2.0 source at
  95eb1c0c84e3f07d36f28a5e69197ec3b5c59046 (see README links).
- Added shared metadata generation to build_package2.py and a standard-library
  metadata-only ZIP repair command. All packs now carry main.xml texture entries,
  correct assets/mod_overrides instructions, explicit SuperBLT/BeardLib requirements,
  conflict/restart diagnostics and honest verification limits.
- Repaired the existing tracked archives. Compared every original asset with
  git show HEAD:dist/<archive>: all 23 asset payloads per pack are byte-identical.
- Tests: 10 packaging tests pass; full suite 159 passed, 5 skipped. Knowledge-base
  validation passes. No game launched, loaders installed, user files changed,
  commits pushed, or PRs opened.
- Next oracle: user installs one corrected pack, restarts, selects matching
  character/default outfit and supplies a menu screenshot. Back up saves before
  offline heist testing. If unchanged, request full install path and loader logs.
  Model deformation, texture orientation, facial animation and multiplayer remain
  unverified; packaging validation alone cannot establish that they work.

## 2026-10-18 — startup crash: SkinBones mappings out of range

- Report: some users see an access violation while loading menu packages with the
  corrected metadata packs. `crash.txt` mentions menu units; loader not confirmed.
- Validated the two `.model` files in each `dist` archive with a bounds-checked
  DODB v1 reader (`tools/pd2-port/repair_skin_palettes.py`): 6 of 24 SkinBones
  sections in Clover, 4 of 19 in Bonnie and 5 of 19 in Sydney contained
  out-of-range palette indices. Example: Clover `sid 418` stored 28 object IDs
  (41, 42, 43 … 152) in the per-atom mapping arrays instead of local indices
  0..27. The engine would index outside the skin's `object_ids` array.
- Root cause: `build_model.py` and `build_character.py` wrote
  `for pid in pal_ids: sb.u32(pid)` for every mapping. `object_ids` belong in
  `SkinBones.object_ids` (the bone list); the mappings must contain
  0-based indices into that list. The bug was systematic: every mapping in each
  affected section duplicated the full `object_ids` list.
- Fix: both builders now write `for idx in range(len(pal_ids)): sb.u32(idx)` —
  the same local palette for every atom of a drawable, matching the verified
  per-atom layout (`atom_count + 1` identical mappings). No matrices, geometry,
  material groups, object IDs or texture registration were changed.
- Repaired the three tracked archives in place with a strict binary patch:
  only the exact writer defect is corrected; any other invalid mapping is
  rejected instead of guessed. The patch was validated with
  `validate_skin_palettes` on both models per pack (24/24 for Clover,
  19/19 for Bonnie and Sydney). No game was launched; physics, animation,
  masking and networking remain unverified.
- Added `tools/pd2-port/repair_skin_palettes.py` (Python 3.10+, stdlib only) and
  a PowerShell equivalent for users without Python. Both write a new
  `lawson_<character>_skinfix.zip` beside the original and add
  `SKIN_PALETTE_REPAIR.txt` documenting the trial. The staged builders are fixed
  so future packages do not reintroduce the defect; a packaging test now
  enforces the 0..N-1 range on every shipped model.
- Next oracle: install only the newly repaired Clover pack (after moving all
  older Lawson folders outside the game), confirm the main menu opens, then the
  unmasked preview with the default outfit. Test offline; back up saves first.
  If it still crashes, disable the pack and share the fresh `crash.txt` and
  `mods/logs/` log.

