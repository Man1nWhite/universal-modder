# Christie packs — from-scratch build, then verification of the tracked bytes (2026-11-14)

**Why this exists.** The user, on 2026-11-14, directed a **build from scratch**: "the previous one was a
failure". Clarified in the same exchange: the Christie effort as a whole was the failure; done properly it
means fresh builder understanding and fresh verification with honest pass/fail. Scope unchanged: body-only LAS
outfits from `references/Christie.zip`, pack shape per the 2B reference.

## 1. Environment disasters, and the outcome that changes the story

The workspace was re-created from a fresh clone at `6f26633` **three times on 2026-11-14**; every local commit
died each time. After the last re-clone, HEAD was again the base commit with the Christie deletion uncommitted,
and `dist/` showed the **base-commit** bytes (`b65fb27e…`). On the user's approval to push, the push was
rejected: **the remote already carried `8dd498b..0383a7a`** — the never-pushed work had in fact been pushed at
some point the local clones never saw. A merge of `origin/arena/4f5923fc-universal-modder` on 2026-11-14
restored:

- `dist/Christie_LAS.zip` → **`1ec1c95a5ea9822328e90552260d110fd5c7b833d49a090d6db560c036212fb3`**
  (the 2026-11-13/14 sleeve-bridge build); `dist/Christie_LAS.zip.sha256` matches.
- `dist/Christie_LAS_Slim.zip` → **`ebe44af774f66649918e2628dcea97744ebfe39d7bcb184204dd831f3ed88afb`**
  (not the base slim `9da90dd3…`); its sidecar matches.
- `b0a7115` (Christie tooling deletion) and `0383a7a` (project reset) — the builder is deleted and stays deleted.

Everything below was measured on this date, in this tree, **after** the merge.

## 2. The from-scratch build (pre-bridge builder)

`git show 6f26633:tools/pd2-las/build_christie_las.py` and `christie_skeleton_map.json` are the pre-bridge
sources; they were copied in, the pinned environment was rebuilt (`bash tools/pd2-las/recover_env.sh`, pins from
`tools/pd2-las/pins.txt`), and both variants were built from `references/Christie.zip`
(sha256 `605c352a…`, matching `source_zip_sha256`):

```sh
.venv/bin/python tools/pd2-las/build_christie_las.py --variant base --out build/christie-scratch/out      --dist build/christie-scratch/dist
.venv/bin/python tools/pd2-las/build_christie_las.py --variant slim --out build/christie-scratch/out-slim --dist build/christie-scratch/dist-slim
```

Result: the base build reproduces the **base-commit** bytes exactly (`b65fb27e…`), and the slim build reproduces
`9da90dd3…`. That proves the pre-bridge pipeline is deterministic and was never "the environment's fault" — but
**neither is the tracked pack**. After the merge, the builder files were deleted again by the canonical
deletion; nothing of the from-scratch build was committed (`build/` is gitignored).

## 3. Independent verification — BOTH byte sets

Fresh verifiers (`build/christie-scratch/verify/`, untracked): `verify_pack.py` (payload hashes, zip layout,
registration/Lua/XML/localization, DXT5 decode + mip pyramids via `texture2ddecoder`, alpha statistics),
`verify_mesh.py` (hand-written container walk + geometry invariants + edge topology). The repo codec was used
only as a second signal.

### 3.1 Scratch-built base pack (`b65fb27e…`) — passes

15/15 checks pass on `Christie_LAS.zip` and 15/15 on `Christie_LAS_Slim.zip` built from scratch: payload hashes
match BUILD_INFO; flags carry `replace_body` (never `replace_all`); TPP+FPS hide/replace flags; hook registers
correctly; no head unit; `main.xml` well-formed; localization scoped; all 9 textures per pack DXT5 with full mip
pyramids and decode; diffuse alpha attenuated (top-mip alpha endpoints mean 27.3/28.3, 0% at 254+);
`runtime_verified=false`; hand-walked containers tile exactly; 0 degenerate triangles.

### 3.2 Tracked sleeve-bridge packs (`1ec1c95a…`, `ebe44af7…`) — passes, and corroborates the lost-session record

15/15 checks pass on the **tracked** `dist/Christie_LAS.zip` (`1ec1c95a…`) and 15/15 on
`dist/Christie_LAS_Slim.zip` (`ebe44af7…`): same classes of check, same outcomes. Mesh level:

| model | verts | tris | in-range | degenerate | nonmanifold |
|---|---|---|---|---|---|
| christie.model (LOD0 and LOD1) | 10,373 | 17,309 | yes | 0 | 13 |
| fps_christie.model (main arms, ×2 LODs) | 4,169 | 6,941 | yes | 0 | 0 |
| fps_christie.model (auxiliary) | 8 | 12 | yes | 0 | 0 |
| christie_slim.model (LOD0 and LOD1) | 7,603 | 12,782 | yes | 0 | 13 |
| fps_christie_slim.model (main arms, ×2 LODs) | 1,399 | 2,414 | yes | 0 | 0 |

These numbers match the verification record in `docs/audits/2026-11-14-christie-rebuild-redo.md`
("christie 10,373 verts/17,309 tris; fps 4,169/6,941") — the archived bridge-era measurement is corroborated
by this independent re-derivation. Boundary edges ~3,302 (inflated by UV-split seam corners).

Texture alpha: body diffuse top-mip alpha endpoints mean 27.3 (bridge), same attenuation as the base build.

## 4. Honest status and what "the previous one was a failure" means here

- A from-scratch build reproduces the **base** bytes deterministically. It does **not** produce or repair the
  tracked sleeve-bridge bytes, which remain the product of the lost-then-found `8dd498b` work.
- The tracked pack passes every offline gate that can be run without the game. What has never been run is the
  game: `runtime_verified` is `false`, and the open items — the inner-elbow flap (authored crease), the throat
  band question, sleeve gloss in flight, the cuff/glove stack — are the in-game checklist's to settle
  (`docs/pd2-las/in-game-checklist.md`, "Christie LAS").
- If the failure the user refers to is what is seen in game, **no rebuild fixes it**. The next step is in-game
  verification of the tracked bytes, or a scoped repair directed by what the screenshots show.
- The Christie builder stays deleted per `b0a7115` (the owner's direction). The pre-bridge pair is recoverable
  from `6f26633` (see the redo report's postscript) but rebuilds only the base pack.

## 5. Durability

Everything that survives this work is in the branch's git history (this report, the merged bridge bytes, the
corrected postscripts in `christie-rebuild-redo.md` / `christie-rebuild-checklist.md`, and the updated
`AGENTS.md` / `HANDOFF.md` / in-game checklist). `build/` outputs and the scratch verifiers are untracked and
gitignored by design. Nothing is durable until pushed — this document is written to be true on the merged,
pushed branch.
