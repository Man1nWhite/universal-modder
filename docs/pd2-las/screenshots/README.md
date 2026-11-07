# Christie_LAS_Slim — in-game screenshots (2026-11-07)

Eleven captures of `dist/Christie_LAS_Slim.zip` (sha256 `33832eaf…aca7`, the
2026-11-07 elbow/cuff rebuild) taken in PAYDAY 2, kept byte-identical to what the
user supplied so the crops and pixel coordinates in
[`docs/audits/2026-11-07-christie-slim-screenshot-review.md`](../../audits/2026-11-07-christie-slim-screenshot-review.md)
stay reproducible.

- `01`–`07` — lobby / idle, walking the camera around the character.
- `08`–`11` — menu pose holding a sniper rifle.

Notes on reading them:

- A **mouse cursor** is visible in several frames: these are ordinary desktop
  captures, not clean renders.
- These are **lossy, slightly resampled** frames (~491–563 px wide). Judging
  shading means looking at **native 1:1 pixels**; magnifying an upscaled crop
  invents structure that is not in the mesh, which is exactly the mistake that
  produced (and then had to withdraw) the "faceted shading" finding in the audit.
- The Christie face and hair are **not from this pack** — it ships no head
  (`headless: true`). A heister head mod was active, so head/neck appearance
  belongs to that mod, not here.
- Pixel coordinates quoted in the audit are in each file's own pixel space; the
  frames are all slightly different sizes.
