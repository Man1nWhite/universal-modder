# Christie packs — from-scratch build and independent verification (2026-11-14)

**Why this exists.** The user, on 2026-11-14, directed that the Christie packs be **built from scratch**, because
"the previous one was a failure". Clarified in the same exchange: the Christie effort as a whole was the failure;
the ask is the whole thing done properly — fresh builder understanding, fresh verification, honest pass/fail.
Scope is unchanged: body-only LAS outfits built from `references/Christie.zip`, pack shape per the 2B reference.

**Environment reality (read first).** The workspace was re-created from a fresh clone of the branch at `6f26633`
**three times on 2026-11-14**. Local commits never survive (`bb05641`, `8d54557` — the re-application of the lost
Christie deletion — are gone again with this one). Files that persist are the untracked/modified working tree.
`dist/` has never changed: `Christie_LAS.zip` is `b65fb27e…` (matches its `.sha256` sidecar), `Christie_LAS_Slim.zip`
is `9da90dd3…`. Everything below is measured on those bytes, in this tree, on this date. Nothing here is durable
until the branch is pushed — see the last section.

## 1. Builder recovered (pre-bridge, not the lost bridge)

The deleted builder was restored from the base commit, not from memory of the lost work:

```sh
git show 6f26633:tools/pd2-las/build_christie_las.py   > tools/pd2-las/build_christie_las.py
git show 6f26633:tools/pd2-las/christie_skeleton_map.json > tools/pd2-las/christie_skeleton_map.json
```

These are the **pre-sleeve-bridge** sources (the 2026-11-13/14 `8dd498b` bridge was never pushed and is
unrecoverable; recreating those bytes would require re-authoring it). As of this writing the recovered files sit
in `tools/pd2-las/` as untracked changes; the committed deletion is untouched in history.

## 2. From-scratch build (pinned environment)

`bash tools/pd2-las/recover_env.sh` rebuilt `.venv` (pins: `tools/pd2-las/pins.txt`; pytest, pillow, numpy,
pyyaml, py7zr, scipy) and unpacked the 2B templates into `build/pd2-las/2b/`. Then:

```sh
.venv/bin/python tools/pd2-las/build_christie_las.py --out build/christie-scratch/out      --dist build/christie-scratch/dist      --variant base
.venv/bin/python tools/pd2-las/build_christie_las.py --out build/christie-scratch/out-slim --dist build/christie-scratch/dist-slim --variant slim
```

Both succeeded from `references/Christie.zip` (sha256 `605c352af06761fe00ea38846a78d505b95c767f7b4c77d02ff25bdf5d282a3b`,
matching `source_zip_sha256` in BUILD_INFO). The outputs are **byte-identical to the tracked `dist/` zips**:

| pack | rebuilt | tracked | identical |
|---|---|---|---|
| Christie_LAS.zip | `b65fb27ee4e94d453c3f580e453570d3005274790c2e8ecadec451bf9ffc6548` | same | yes |
| Christie_LAS_Slim.zip | `9da90dd3e9779832fd03443d78dd39b968a8d6c63a09ce3d52cadf5cd3201f29` | same | yes |

So "build from scratch" reproduces, exactly, the packs the user called a failure. **A rebuild cannot fix the
defects by itself** — the defects are in the source data / design, not in an environment slip. Whatever failed
in game (neck bands, inner-elbow flap, tone) will still be there. See §5.

## 3. Independent verification (fresh code, not the builder's say-so)

Scripts (untracked, under `build/christie-scratch/verify/`): `verify_pack.py` (payload hashes, zip layout,
flags, XML/Lua/localization, texture decode via `texture2ddecoder`, alpha statistics), `verify_mesh.py`
(hand-written container walk + geometry invariants + edge topology). Repo codec used only as a second signal.

**Base pack — 15/15 pass. Slim pack — 15/15 pass.** In particular:

- `payload_sha256` in `BUILD_INFO.json` matches every shipped file (20/20). No unexpected paths; 21 entries (base) / 22 (slim).
- Registration: `replace_body` set (never `replace_all`); TPP + FPS hide/replace flags; hook adds `la.christie = {…}` /
  `la.christie_slim = {…}` with `hide_mask`, `hide_armor`, `replace_body`, `fps_*`; no head unit referenced anywhere;
  `main.xml` well-formed; `english.txt` keys are item-scoped. Slim also ships the glove-adapter hook (no authored hands).
- All 9 textures per pack are DXT5 with full mip pyramids (11/11/11/11/10/10/9/9; GUI 256×256 mips=1) and decode cleanly.
  `christie_body_df` top-mip BC3 alpha endpoints average **27.3** (slim 28.3), 0% at 254+ — the diffuse-alpha
  attenuation (phong-mask from the normal map) is real, not nominal.
- `runtime_verified` is `false`; `headless` true; no face/hair/eye/lash bytes in payload; `material_config` is XML
  with exactly the four kept materials (`body`, `c02_01`, `c02_02`, `c02_05`, df+nm each) plus `shadow_caster`.
- Both models parse: every container section tiles the file exactly; all triangle indices in range; **zero degenerate
  triangles**. Mesh statistics:
  - `christie.model`: LOD0 10,373 verts / 17,289 tris; LOD1 10,369 verts / 17,289 tris; 3,298 boundary edges
    (inflated by UV-split seam corners — not a hole count); **13 nonmanifold edges** (observation, not fixed here).
  - `fps_christie.model`: main FP arms 4,157 verts / 6,921 tris (×2 LODs) + one 8-vert/12-tri auxiliary mesh; 0 nonmanifold.
- Determinism across environments: zips built today match the tracked bytes produced in earlier sessions, byte for byte.

## 4. What is NOT verified

- **In-game behaviour.** The game was not run. `runtime_verified` stays `false`; the in-game steps (including the
  sleeve-slit history, which refers to the now-lost bridge) are in `docs/pd2-las/in-game-checklist.md` ("Christie LAS").
- **The inner-elbow flap** (authored crease), **neck bands**, **tonal patches**: not fixed — they were never offline-repairable.
- **Sleeve-bridge bytes** (`1ec1c95a…`): lost with the never-pushed `8dd498b`; today's build is the pre-bridge base.
  Do not cite `1ec1c95a` as existing anywhere.
- **Winding agreement 97.9%** (the builder's own printed figure; below the 98 advisory line used in earlier gate
  drafts) and the 13 nonmanifold edges — recorded, not addressed.
- The Slim pack's glove-adapter hook is syntax-simple and XML-checked, not executed.

## 5. Verdict

The tracked Christie packs are **deterministically reproducible** and pass **all offline gates** written for them.
They are **not** thereby "fixed" — if the 2026-11-14 failure is what shows in game, the next step is in-game
verification of these exact bytes (install `dist/Christie_LAS.zip` per the in-game checklist), not another rebuild.
`dist/` was deliberately left untouched: the rebuilt bytes *are* the tracked bytes, so replacing them would change nothing.

`Christie_LAS_Slim` is likewise reproducible and verified the same way.

## 6. Durability — the one open risk

As of this writing, none of this is on the remote: the branch history was wiped three times today; the recovered
builder and skeleton map (`tools/pd2-las/`), this report, the scratch outputs (`build/christie-scratch/`), the two
edited docs (`AGENTS.md`, `docs/pd2-las/HANDOFF.md`) and the Christie deletion re-application are **uncommitted or
unpushed**. The user has not yet approved a push. Until one happens, any re-clone can delete all of it again.
