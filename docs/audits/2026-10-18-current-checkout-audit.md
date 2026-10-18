# Current-checkout audit — toolkit and PAYDAY 2 outfit addition

**Date:** 2026-10-18

**Source baseline:** `2a64e1e5d13b1a83d92f64dcb2580ae33ae4136d`

**Reference supplied by the user:** `2b.rar`

**Audit changes:** documentation only. No production code, tests, input assets or tracked archives changed; no game installation, loader installation, commit, push, publication or PR performed.

**Subsequent runtime work:** this report records the baseline above, before the
user-requested LAS repair. `build_outfit.py` / `dist/lawson_outfit.zip` have since
been rebuilt as an actual LAS add-on; shared helpers moved to `outfit_model.py`.
Old code line references and archive facts below describe the audited baseline,
not the repaired candidate. See the [LAS field note](../../knowledge/games/payday-2/las-outfit-unit-resources.md)
and [journal](../../tools/pd2-port/MODLOG.md) for current changes and limits.
The runtime crash is **not** yet verified resolved.

This is a follow-up to the [earlier repository audit](2026-10-18-repository-audit.md). That report predates `build_outfit_beardlib.py`; its findings must not all be attributed to the newer variant. Finding IDs below retain the earlier numbering for continuity.

## Verdict

**The repository now contains a credible, separately selectable outfit implementation in addition to the three character replacements, but it is still an experimental asset pipeline, not a game-verified release.** The new BeardLib builder is materially better than the legacy outfit. Do not discard those improvements or keep making speculative crash repairs without an offline game test.

`2b.rar` illustrates an **equipable full-body addition with separate third-person and first-person assets**. It is not just a replacement for a particular heister. The new BeardLib `PlayerStyle` is a reasonable alternative way to deliver the additive-outfit goal. However, it deliberately does **not** implement LAS armor-skin registration or LAS-style mask hiding. Treat exact LAS behavior as a product choice, not something implied by a folder name.

**Highest priorities:** fix backup containment; stop treating publish lint as inspection of ZIP/RAR payloads; fix shared model/texture validation and the inherited index-count rule; retain the newer outfit's improvements; then obtain real offline game evidence. Resolve asset redistribution permissions before any public release.

## What the reference establishes

The RAR was independently listed, its paths checked, and its 17 files read in an ignored audit workspace. It contains 12 directory entries and **36,415,621 uncompressed bytes**. Its Lua was inspected as text, not executed.

| Contract | Supplied 2B pack | Legacy Lawson outfit | New BeardLib Lawson builder |
|---|---|---|---|
| Registration | Hook on `lib/tweak_data/armorskinstweakdata`, creating `LegendaryArmours.twobee` | BeardLib `PlayerStyle id="lawson"`, despite LAS branding | BeardLib `PlayerStyle id="lawson_beardlib"`, explicitly no LAS |
| Selection | LAS armor-skin entry | Player style; bundled instructions confuse this with LAS | Native Outfit / Player Styles selector |
| Standalone addition | Own unit and FPS-unit paths | Own resources; not a character swap | Own resources and IDs; source Clover ZIP needed only at build time |
| Whole-body replacement | `replace_all`, `hide_armor`, FPS replacement flags | Native replacement maps | Separate native FPS/TPP replacement maps |
| Mask hiding | `hide_mask = true` | A `mask` attribute in native replacement maps does not establish this behavior | Explicitly not implemented; mask clipping disclosed |
| First-person assets | `fps_2b.model` and sidecars | Arms selected by an order-dependent algorithm | Stable one-ring selection, separate hands; cut not claimed watertight |
| Runtime evidence in this audit | None | None | None |

The three `lawson_{clover,bonnie,sydney}.zip` files remain **character overrides**, not selectable additions. The new `lawson_outfit_BeardLib.zip` is a **generated, ignored output**, not a fifth checked-in release archive.

The reference is not an independently verified oracle: its hook-directory casing differs between manifest and archive (`Hooks`/`hooks`), its cooked-physics files are empty, and `ss.model` is not registered. Do not reproduce these details merely to match its file count.

## Checks performed on this checkout

| Check | Observed result |
|---|---|
| Complete existing suite, with FFmpeg and ffprobe available | **217 passed, 1 skipped**, one Pillow deprecation warning; approximately 73 seconds |
| Remaining skip | Git Bash / MSYS-specific launcher test, `tests/test_um.py:1236` |
| Suite before supplying multimedia tools | 213 passed, 5 skipped |
| Main CLI help and all ten command-group help pages | Passed |
| `python -m um kb check --index` | **246 notes passed**; existing warning: `diesel` is not a scanner engine key |
| `python -m um publish check .`, before audit documentation edits | Exit 0: **760 files, 0 failures, 8 warnings**; not an archive-content inspection |
| Check-only repair command on all three character ZIPs | All three reported `OK` |
| Normalizer on all six tracked vanilla reference models | Byte-identical no-op |
| Legacy outfit rebuilt from the source ZIP | Existing payload-parity test passed |
| New BeardLib builder | Built successfully; **36 payload files**, 24,313,566 uncompressed bytes |
| New builder determinism, isolation from old packs, atomic failure behavior, material coverage and arm selection | Existing dedicated tests passed |
| Lint of the actual, unpacked new outfit payload | **PASS: 36 files, 0 failures, 0 warnings**; no game-install comparison available |
| Python wheel | Built successfully; required fonts, PowerShell files and Blender render script included |
| Fresh source-to-character build | `build_character.py clover` failed on the missing external workspace model |
| PAYDAY 2, Windows input, Blender rigging, VR or multiplayer | **Not run** |

Environment: Python 3.11.2, NumPy 2.4.6, Pillow 13.0.0, PyYAML 6.0.3, pytest 9.1.1; static FFmpeg/ffprobe 6.0. RAR inspection used `rarfile` 4.5 for listing and `node-unrar-js` 2.0.2 for decompression. Retained audit tooling, inspection builds and extracted files stayed in ignored `.venv/` storage; tests also used disposable temporary directories. These are not project dependencies or deliverables.

Scope: deep inspection of the PD2 scripts, reference archive, four tracked mod ZIPs, new generated pack, backup/publish boundaries and their tests; review of build/CI setup, selected toolkit I/O/input paths, CLI smoke tests and the complete existing suite. This is not an exhaustive security review of every example, a dependency-CVE audit, or proof of native game compatibility.

## Findings and current status

**P1:** fix before relying on the affected safety/correctness boundary. **P2:** correctness or hardening work. **Release gate:** unresolved requirements, runtime evidence or permissions, not necessarily a code defect.

| ID | Priority / scope | Current status |
|---|---|---|
| A01 | Product contract | **Clarified, not exact reference parity.** The new builder explicitly implements an additive native player style; it does not implement LAS or mask hiding. The older ZIP still has misleading LAS instructions. |
| A02 | P1 — legacy outfit | **Open in the original ZIP; addressed in the new variant.** Enabled `s_body` uses `shadow_caster`, omitted by the legacy material config. New tests check model-to-config coverage. |
| A03 | P1 — toolkit safety | **Open.** Backup restore escapes its destination through manifest traversal or a destination symlink; recorded hashes are not verified. |
| A04 | P1 — shared validator; P2 — new wrapper | **Partially addressed.** Shared validation still accepts invalid triangle/material references. The new wrapper rejects those cases, but still accepts finite negative skin weights. |
| A05 | P2 — both model pipelines | **Open, including the new builder's end-to-end path.** Its new validator accepts large valid index counts, but `prepare_model()` still calls the old trimming/normalization rule. |
| A06 | P2 — shared model parser | **Open.** The supplied legacy 2B models decode without weight channels and crash validation. The new builder explicitly rejects legacy input; that is a useful restriction, not legacy-format support. |
| A07 | P2 — DDS helpers | **Open.** The BC3 decoder applies BC1 transparency rules. The new opacity-map path correctly uses Pillow instead, but the shared decoder/repair assumptions remain wrong. |
| A08 | P2 — source rig/export | **Open.** Welding and exporting the first loop UV loses seams. The new builder reuses the existing rigged binary; it does not repair this source-pipeline defect. |
| A09 | P2 — legacy FPS selector | **Addressed in the new variant; open in the old one.** New immutable-seed selection is order-independent, but still needs anatomical/pose verification. |
| A10 | P2 — full source build | **Open.** Hard-coded external workspace and untracked generated inputs prevent an OBJ-to-pack rebuild. Archive-to-outfit rebuilding is working. |
| A11 | P2 — release lint | **Open.** ZIP/RAR members are not inspected or even reported as uninspected containers. |
| A12 | Release gate — provenance | **Unresolved.** The new credits accurately disclose uncertainty; disclosure does not establish redistribution permission. |
| A13 | P2 — desktop automation safety | **Newly examined.** A rejected foreground-input command automatically issues `focus` and retries; held inputs lack guaranteed release on focus loss. |

### A03 — Backup restore can overwrite outside the chosen folder

**Code:** [`um/backup.py:104–125`](../../um/backup.py#L104-L125).

Restore directly writes `target / rel` for manifest-provided paths. In disposable temporary directories, both of these overwrote a neighboring sentinel while restore reported success:

- Manifest member `../outside.txt`.
- Normal member `link/sentinel.txt`, with `target/link` a symlink to a neighboring directory.

The out-of-destination files are not protected by the selected destination's pre-restore snapshot. A separate probe declared the SHA-1 of `RIGHT` but stored `WRONG`; restore accepted the wrong bytes. These are local, supplied-snapshot/destination conditions, not a demonstrated unauthenticated remote exploit.

**Repair:** validate the complete archive and manifest before writing; reject absolute/traversing names and link escapes; enforce containment for writes and cleanup; verify sizes and hashes; stage safely. Test Windows paths/junctions as well as POSIX symlinks. Do not treat `--yes` as path validation.

### A04 — Validation is improved locally, not fixed centrally

**Code:** [`repair_skin_palettes.py:186–316`](../../tools/pd2-port/repair_skin_palettes.py#L186-L316), [`build_outfit_beardlib.py:57–109`](../../tools/pd2-port/build_outfit_beardlib.py#L57-L109).

The existing authored three-vertex fixture still produces `[]` from shared strict validation for a triangle `(0, 1, 65535)`, and separately for material index `999` in a one-material model. The new builder correctly rejects both with `ValueError`.

However, a fixture with raw skin weights `(-1, 1, 1)` passes even the new wrapper: its additional check only verifies finiteness. Normalizing/clamping values in the reader does not validate the raw weights that remain in the output binary. Required null references, malformed/truncated sections and palette-set counts also need deliberate negative fixtures and controlled diagnostics rather than incidental indexing exceptions.

**Repair:** consolidate the stronger checks into the shared validator; validate raw channel lengths, weight ranges and expected sums for the actual shader/channel contract. Keep tests that deliberately violate each invariant. This is a validator defect, **not evidence that current default output contains those corrupt triangles or negative weights**.

### A05 — The new builder still inherits the false 65,535-index-count restriction

**Code:** [`build_outfit_beardlib.py:191–192`](../../tools/pd2-port/build_outfit_beardlib.py#L191-L192), [`repair_skin_palettes.py:411–439`](../../tools/pd2-port/repair_skin_palettes.py#L411-L439), [`repair_skin_palettes.py:550–560`](../../tools/pd2-port/repair_skin_palettes.py#L550-L560).

The new test at [`tests/test_outfit_beardlib_pack.py:299–320`](../../tests/test_outfit_beardlib_pack.py#L299-L320) exercises **validation**, not the complete prepare/build path. The latter still invokes `normalize_model_container()`, which rejects or deletes layers based on the old count threshold.

Reproduction: duplicate 22,000 valid triangles within the source Clover `g_body`'s first material atom; update the UInt32 count, affected atom ranges, section size and container size. The resulting topology has **129,975 indices**, without adding vertices or invalid vertex references:

```text
new validate_model(): accepted
new prepare_model(first_person=False):
ValueError: Model 167: Topology 305 has 129975 indices (> 65535)
            and no redundant layers to drop
```

The supplied `2b.model` independently has **105,780 indices**, **27,741 vertices**, maximum index **27,740**. The pinned upstream reader stores counts as UInt32 and vertex references as UInt16. This refutes the field-width explanation for the generic count cap; it does not establish every possible engine-specific resource limit.

**Repair:** remove count-based trimming from generic normalization and add an end-to-end large-topology regression. Mesh-layer optimization should be explicit and separate from container repair. Do not extend the earlier documentation's unproven crash diagnosis to this format-valid input.

### A02 / A09 — Do not confuse legacy defects with the new outfit

**Legacy material code:** [`build_outfit.py:523–543`](../../tools/pd2-port/build_outfit.py#L523-L543). The original ZIP enables `s_body`, whose 173 vertices use `shadow_caster`; the matching material config omits it. The new pack retains that material and passes bidirectional coverage tests.

**Legacy arm selection:** [`build_outfit.py:218–228`](../../tools/pd2-port/build_outfit.py#L218-L228). Reproduced on the shipped source:

| Measurement | Legacy | New variant |
|---|---:|---:|
| Arm-bound seed vertices | 1,825 | 1,825 |
| Selected in normal face order | 3,129 | 1,998 |
| Selected in reversed face order | 2,740 | 1,998 |
| Order-invariant | No: 755-vertex symmetric difference | Yes |

The legacy selection still leaves 407 faces crossing the selected/unselected boundary. The new one-ring cut solves order dependence, not a complete anatomical/watertightness problem. Verify the shoulder boundary and hand/weapon alignment through actual animation poses.

### A06 / A07 / A08 — Reference decoding and source-asset correctness remain weak

- **Legacy channels:** [`dmodel.py:109–126`](../../tools/pd2-port/dmodel.py#L109-L126), [`dmodel.py:206–268`](../../tools/pd2-port/dmodel.py#L206-L268). All three RAR models (`2b`, `fps_2b`, `ss`) have zero decoded weight entries and raise `IndexError` during shared validation. The upstream reader remaps legacy channel IDs above `TEXCOORD7` by +2; the local parser does not propagate that format distinction. Add authored legacy fixtures and explicit unsupported-format diagnostics.
- **BC3/DXT5:** [`dds.py:55–97`](../../tools/pd2-port/dds.py#L55-L97), [`dds.py:294–327`](../../tools/pd2-port/dds.py#L294-L327). A valid opaque block with RGB endpoints 0/65535 and RGB index 3 decodes to `(170, 170, 170, 255)` with Pillow and `(0, 0, 0, 0)` locally. DXT5 has separate alpha and always uses the four-color RGB palette. Correct the decoder, validity checks and related documentation; do not call `c0 < c1` intrinsically corrupt. This does not establish visible holes in the currently shipped sorted-endpoint textures.
- **UV seams:** [`rig_lawson.py:108–116`](../../tools/pd2-port/rig_lawson.py#L108-L116), [`rig_lawson.py:225–240`](../../tools/pd2-port/rig_lawson.py#L225-L240). The source OBJ has **1,939 exact-coordinate groups with differing UVs**, resolving negative indices correctly. Welding then retaining one loop UV per vertex cannot preserve these seams. Export split position/UV/normal/material vertices with duplicated skin weights. A two-triangle authored seam fixture should cover this without bundling game content.

### A10 — The reproducible part starts at a prebuilt character ZIP

**Code:** [`build_character.py:21–25`](../../tools/pd2-port/build_character.py#L21-L25), [`build_character.py:126–132`](../../tools/pd2-port/build_character.py#L126-L132), [`build_package2.py:17–19`](../../tools/pd2-port/build_package2.py#L17-L19), [`rig_lawson.py:7–23`](../../tools/pd2-port/rig_lawson.py#L7-L23).

The full build still requires a developer-specific `pd2-work/clover-lawson` layout, external hashlist, generated mesh JSON and a referenced but untracked `setup_work.sh`. `build_character.py clover` fails before rebuilding geometry because that workspace's reference model is absent, despite a reference model existing elsewhere in the checkout. A compatible Blender version is not pinned.

The newer builder's explicit paths, atomic output and hash manifest are useful improvements. Its deterministic archive-to-outfit test does not establish reproducibility of the missing source-to-rig-to-character stages. Parameterize/stage those inputs and document/pin the toolchain without committing additional extracted assets.

### A11 — Publish lint misses the distributable's contents

**Code:** [`um/publish.py:38–43`](../../um/publish.py#L38-L43), [`um/publish.py:84–99`](../../um/publish.py#L84-L99); [CI](../../.github/workflows/test.yml#L25-L26).

A temporary README plus a ZIP containing an internal `.env` with a synthetic recognizable key assignment returns:

```text
PASS: 2 files, 0 failures, 0 warnings   # exit 0
```

Checking the same known payload unpacked returns two failures (env file and key assignment), exit 1. ZIP/RAR extensions are not in the container-warning set either. The normal repository CI result therefore says nothing about secrets or copied game files **inside** its release ZIPs. No actual credential was used in this probe.

**Repair:** safely inspect supported containers with nesting/size/count limits, or make uninspected containers explicit and require linting of unpacked release staging. Include the actual new outfit payload in release checks. A missing `--game` installation also means verbatim game-asset comparison was not performed here.

### A12 — Provenance is a publication gate, not a technical assertion

Tracked vanilla-reference models/DDS files, Lawson OBJ/textures, `2b.rar` and built archives have no per-asset permission manifest. The blanket MIT license does not itself document the rights to those inputs. This conflicts with the repository's [contribution policy](../../CONTRIBUTING.md#L35-L61).

The new pack's `CREDITS.txt` accurately calls it a private experimental derivative with unresolved permissions. That improves disclosure, not authorization. Record origin/authorship/permission/credits, scope the code license clearly, and move non-redistributable working inputs outside version control with the user's agreement. This audit neither determines ownership nor alleges infringement, and did not delete the supplied assets.

### A13 — Foreground rejection is followed by automatic focus takeover

**Code:** [`um/win.py:397–404`](../../um/win.py#L397-L404), [`WinDrive.ps1:144–154`](../../um/ps1/WinDrive.ps1#L144-L154), [`WinDrive.ps1:187–216`](../../um/ps1/WinDrive.ps1#L187-L216).

A mock of the Python driver's existing stdin/stdout protocol, with an initial response reporting an editor in the foreground, produces these commands for a single `click 10 10` request:

```text
click 10 10
focus
click 10 10
```

There is no idle/consent check before this recovery. On a shared desktop, treating every foreground rejection as permission to regain focus can interrupt the human's active work. The existing `retry=False` option is not exposed by the convenience `click`/`hold`/`type` methods.

Source inspection additionally shows cursor movement before the safety check, and down/sleep/up sequences whose release uses the same foreground guard. Losing focus after key/button down can refuse the corresponding release; there is no held-input cleanup on EOF. This second part was **not reproduced on Windows** here and should be tested there, not presented as an observed desktop incident.

**Repair:** fail closed by default on foreground loss; make unattended focus recovery explicit; check the intended window before cursor movement; track held inputs and guarantee best-effort release on cancellation/error/EOF without injecting new presses into another application. Use a fake input sink for event-state tests and a controlled Windows integration test.

## Recommended next steps

1. **Toolkit safety first:** A03 containment/integrity tests and fix; A11 explicit archive handling/release-staging checks. Address A13 before unattended driving on a shared desktop.
2. **Keep the additive new pack:** decide whether the native player-style UX is acceptable or exact LAS/mask-hiding parity is required. Do not install the three replacements merely to obtain the standalone outfit.
3. **Repair shared asset tools with small authored fixtures:** A04–A08, including an end-to-end large-topology test. Preserve the newer material, stable-selection and atomic-build regressions.
4. **Make the full build repeatable:** explicit input/work/output paths, preflight errors, pinned Blender/hashlist/tool versions and source/tool hashes. Keep private game-derived inputs out of new Git changes.
5. **Get the missing oracle:** back up saves, disable conflicting appearance mods, record exact game/SuperBLT/BeardLib versions, and test the intended pack offline. Capture the outfit menu, FPS view, TPP view, equip/unequip on two heisters, masks, reload/ADS/movement, culling, restart persistence and uninstall. Save logs and a short clip. VR/online synchronization remain separate work.
6. **Clear provenance before publishing.** Until runtime and permissions gates are resolved, label outputs **experimental / not verified in-game**, not finished releases.

## Reproduction commands and source references

From the repository root, with the project requirements and pytest installed, and FFmpeg/ffprobe on PATH for multimedia tests:

```sh
python -m pytest -q -ra tests
python -m um kb check --index
python -m um publish check .
python tools/pd2-port/repair_skin_palettes.py --check dist/lawson_bonnie.zip dist/lawson_clover.zip dist/lawson_sydney.zip
python tools/pd2-port/build_outfit_beardlib.py --out scratch/audit/lawson_outfit_BeardLib.zip
python tools/pd2-port/build_character.py clover  # reproduces the missing-workspace failure
```

The [earlier report's authored-fixture reproduction](2026-10-18-repository-audit.md#reproduction-notes) still reproduces the shared validator false negatives. Backup, symlink, integrity and archive-lint probes in this recheck used only disposable directories, fabricated manifests and synthetic marker text. No user saves, installed games, real credentials or external AI APIs were touched.

Upstream comparisons were read at pinned revisions, not added to tracked files:

- [BeardLib `PlayerStyleModule.lua`, `95eb1c0`](https://github.com/simon-wh/PAYDAY-2-BeardLib/blob/95eb1c0c84e3f07d36f28a5e69197ec3b5c59046/Modules/PD2/PlayerStyleModule.lua): confirms native player-style registration and automatic localization-key defaults. This is an API comparison, not an engine test.
- [Model-tool `Geometry.cs`, `6ca72e1`](https://github.com/diesel-modding/payday2-model-tool/blob/6ca72e1940f5813ce57eecb400e685a62ecfd95a/PD2ModelParser/Sections/Geometry.cs#L280-L289): legacy channel mapping.
- [Model-tool `Topology.cs`, same revision](https://github.com/diesel-modding/payday2-model-tool/blob/6ca72e1940f5813ce57eecb400e685a62ecfd95a/PD2ModelParser/Sections/Topology.cs#L91-L107): UInt32 count, UInt16 vertex references.

The reference and four tracked ZIP hashes match the earlier report exactly. `2b.rar` remains SHA-256 `925a29ef79f7033cb681dd47a1f9c3856ef91d88a14e6728eb68b36396501fd9`. The temporary new BeardLib build in the environment above was SHA-256 `591f6d7b9c6ef9a8c6a8b6f2c0183519e2d1a728711e0ed8a75fc555cfe7283f`; this identifies the audited build, not a cleared release or a promise of cross-toolchain byte identity.
