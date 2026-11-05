# Business Woman Skyrim → PAYDAY 2 LAS — archived handoff

> **CANCELLED by the user on 2026-11-04.** The in-game model remained unacceptable after repeated attempts. There is no current pack to install or distribute. See [`STATUS.md`](STATUS.md).

The user asked to delete the original Melodic inputs and the built ZIP, update documentation, and leave the tools. Accordingly, the original archives (`1.zip`–`5.zip`), `dist/BusinessWoman_LAS.zip`, its checksum, and generated build output have been removed from the current branch. The conversion and inspection scripts remain under `tools/pd2-las/` and `tools/skyrim-nif/`, but cannot be run without re-supplying the source archives.

## Preserved context if the user explicitly reopens this work

- [`FIXES-2026-11-04.md`](FIXES-2026-11-04.md) records the attempted geometry fixes and why the in-game result still failed.
- [`PORT-PLAN.md`](PORT-PLAN.md) and [`AUDIT-2026-11-04.md`](AUDIT-2026-11-04.md) are historical measurements, not current build instructions.
- The user-supplied visual references (in-game and comparison screenshots)
  were removed on request; ask the user to re-supply them if the port is resumed.

Do not restore the old package or resume the port unless the user explicitly asks. Earlier Git commits still contain the removed archives and pack; this cleanup removes them from the current branch tip, not from history.
