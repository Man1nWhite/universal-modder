# Business Woman Skyrim → PAYDAY 2 LAS port — cancelled

**Status:** cancelled by the user on 2026-11-04. The in-game result remained unacceptable after repeated iterations. Do not treat this port as a usable or installable mod.

## Cleanup performed

- Removed the five original source archives (`1.zip`–`5.zip`, including Melodic's original mesh archive) from the current branch.
- Removed `dist/BusinessWoman_LAS.zip`, its checksum, and the extracted package folder.
- Removed generated `build/skyrim-nif/` model, texture, and preview build artifacts.
- Retained the conversion, inspection, and preview tools under `tools/pd2-las/` and `tools/skyrim-nif/` at the user's direction.
- Retained historical measurements, failed-fix notes, documentation, and the user-provided visual references so the work can be understood if explicitly resumed.

The retained tools are not currently buildable from this checkout: the source archives are gone. Rebuilding would require the user to re-provide the inputs and explicitly restart the project. Do not recreate or publish the outfit unless asked.

**Git history note:** this removes the archives and pack from the current branch tip; earlier commits in repository history still contain the previously committed files. They have not been purged by rewriting history.

## Historical references

- [`HANDOFF.md`](HANDOFF.md) — archived summary and constraints.
- [`PORT-PLAN.md`](PORT-PLAN.md) — original source audit/plan, retained as historical notes.
- [`AUDIT-2026-11-04.md`](AUDIT-2026-11-04.md) and [`FIXES-2026-11-04.md`](FIXES-2026-11-04.md) — measurements and unsuccessful iterations.
- Reference screenshots were removed on request.
