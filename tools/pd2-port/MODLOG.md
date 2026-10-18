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
