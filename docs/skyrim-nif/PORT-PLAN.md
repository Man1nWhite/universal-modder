# Skyrim 3BA outfit (`1.zip` … `5.zip`) — source audit and port plan

Status: **source decoded, audited, and validated against nifly; port not started.**
Target decided (2026-11-02): a **PAYDAY 2 LAS outfit, keeping the 3BA body** as
the outfit's body. This page answers "can you make an LAS outfit out of these
`.nif` files, and what do you need?" with measured numbers instead of guesses.
Regenerate it any time:

```bash
bash tools/pd2-las/bootstrap.sh          # once, for the venv (pillow/numpy)
.venv/bin/python tools/skyrim-nif/inventory.py \
    --json build/skyrim-nif/source_inventory.json \
    --markdown build/skyrim-nif/REPORT.md \
    --previews docs/previews
bash tools/skyrim-nif/build_nifly.sh     # optional: cross-check binary
.venv/bin/python tools/skyrim-nif/crosscheck.py \
    --markdown docs/skyrim-nif/CROSSCHECK.md
```

Machine-readable inventory: `build/skyrim-nif/source_inventory.json` (gitignored,
rebuild it). Tracked previews: `docs/previews/business_woman_outfit.png`,
`docs/previews/business_woman_textures.png`.

---

## 1. Answer first: what is still needed

Decided on 2026-11-02: target is a **PAYDAY 2 LAS outfit** (`LOS` = `LAS`), and
the **3BA body is kept** — it becomes the outfit's body, the same way the ME2
Miranda line keeps hers. That removes the "what is the target" question and turns
the body from a problem into the deliverable. What remains:

| # | Needed | Why it blocks |
| --- | --- | --- |
| 1 | **Body skin textures.** The merged 3BA body points at vanilla Skyrim files (`textures\actors\character\female\femalebody_1.dds`, `_msn`, `_sk`, `_s`) that are **not in the archives** and not redistributable. Measured: **28 % of the body surface is visible** with the garments on (all of the lower legs, most of the thighs, half the hips, the V-neck chest, the hands) — see §4. | Without a skin texture the LAS pack has naked grey legs. Either send the body texture you run in Skyrim (and a licence to use it), or we author one (PD2's own heister skin, or a CC0 base) — say which. |
| 2 | **The glasses mesh.** `4.zip` has `Heels_*`, `Jacket_*`, `Necklace_*`, `Skirt_*` — no `Glasses_0.nif`/`Glasses_1.nif`, although `5.zip` ships glasses sliders and the plugin's `0BusinessWomanGlasses` armour points at `Melodic\Business Woman\Glasses_1.nif`. | The outfit is 4/5 of itself without them. |
| 3 | **Which colourway** — `1.zip` is the black default; `2.zip`/`3.zip` hold 8 palettes (navy `3/`, red `4/`, maroon `7/`, white `5/`, grey `2/`,`9/`, gold-rust `8/`). | One palette per pack; 2048² textures each. |
| 4 | **The jacket variant.** `Jacket_0.nif` holds `0_Jacket` (open front) *and* `0_Jacket2` (buttoned, its own palette). A LAS outfit swaps one mesh, so pick one — or we ship the open one and a second pack for "Xtra". | Two garments, one slot. |
| 5 | **Redistribution permission.** `5.zip/Please Read.txt`: *"do not publish this mod outside Loverslab without permission"* — author **Melodic**. | Private build is fine today; publishing `dist/*.zip` + a release needs the author's OK, like the ME2 line's asset-rights gate. |
| 6 | **An in-game check** on Windows (PD2 + SuperBLT + BeardLib + LAS). | Repo rule; the retired 2026-10-18 route died on unverifiable crashes. |

Open technical question, answerable by us: whether to fake **HDT skirt/necklace
motion**. No PD2 target in this repo has a physics skin, so the default is a
static skin with the 13 skirt bones as the seams a sway chain would attach to.

## 2. What the five archives actually contain

| archive | size | contents |
| --- | --- | --- |
| `1.zip` | 10.6 MB | 18 `.dds` — the **default palette**: `Jacket_`, `Jacket2_`, `Skirt_`, `Heels_`, `Necklace_` × `diffA`/`norm`/`metal`, plus `bloodfree_e` (emissive-ish detail) and `ore_gold_e` (necklace gold) |
| `2.zip` | 20.8 MB | 23 `.dds` — palettes `2/`, `3/`, `4/`, `5/`, `6/`, `7/` (diffuse only, no normals), plus `chrome_desat` |
| `3.zip` | 24.3 MB | 19 `.dds` — palettes `8/`, `9/` (these two carry full `diffA`+`norm`+`metal` sets), plus `Glasses_*` for palette `8`. `8/Glasses_norm.dds` is a **0-byte placeholder** |
| `4.zip` | 14.4 MB | the **meshes**: `meshes/Melodic/Business Woman/{Jacket,Skirt,Heels,Necklace}_{0,1,g}.nif` (12 files). `_0` = weight-0 body, `_1` = weight-100 body, `_g` = ground/collision model. No glasses mesh |
| `5.zip` | 25.7 MB | BodySlide: 5 `.osp` slider sets, 5 `.osd` + 5 source `.nif` under `CalienteTools/BodySlide/ShapeData/…`, `[Melodic] Business Woman SE 3BA.esp` (TES4 form version 44 → Skyrim SE), and `Please Read.txt` |

Every file is `20.2.0.7 / user 12 / stream 100` (Skyrim Special Edition NIF).
The `.esp` is a Skyrim SE plugin (records: 6 armour add-ons, 6 armours, recipes,
tempering), so `1.zip`…`5.zip` are a complete, installable **Skyrim SE** mod.
On Skyrim it already works — no port needed.

### Garment geometry (measured from `_0.nif`)

| piece | garment shapes | vertices | triangles | skinned to | vertical span |
| --- | --- | --- | --- | --- | --- |
| Jacket | `0_Jacket` (open) + `0_Jacket2` (buttoned) | 25 059 | 45 451 | 53 bones | 101.8 → 165.1 cm |
| Skirt | `0_Skirt` | 1 312 | 2 480 | 13 bones | 86.6 → 117.7 cm |
| Necklace | `0_Necklace` | 26 961 | 44 516 | 6 bones | 149.9 → 161.3 cm |
| Heels | `0_Heels001` | 4 768 | 8 576 | 4 bones | −12.0 → 6.7 cm (local to the shoe) |

Two things stand out and both matter for a port:

* the **necklace is 26 961 vertices** — more than the skirt and the shoes
  together, 90 % of it weighted to `Spine2`. That is BodySlide/3D-scan-grade
  density for a necklace; a decimation pass is worth doing for any target.
* the **jacket is two garments in one file**. `0_Jacket` (open front, 27 k tris)
  and `0_Jacket2` (buttoned, 18 k tris, its own `Jacket2_diffA` palette) are both
  inside `Jacket_0.nif`, and both of the plugin's armour records ("Business
  Woman Jacket" and "… Jacket Xtra") point at that same `Jacket_1.nif`. A port
  has to pick one — a LAS outfit swaps one mesh, not a node's visibility.

### Textures

| group | files | notes |
| --- | --- | --- |
| garment diffuse | `*_diffA.dds` 2048², DXT1 | 8 palettes; `1.zip`'s black set is the default |
| garment normal | `*_norm.dds` 2048², DXT5 | `Skirt_norm` is effectively flat (two-tone), `Necklace_norm` is 64² |
| garment metal/spec | `*_metal.dds` 16²–512², DXT1 | tiny masks, they are gloss/spec lookups |
| emissive detail | `bloodfree_e` 128², `ore_gold_e` 512² DXT1 | gold jewellery and the sequin sparkle |
| body | `textures\actors\character\female\femalebody_1.dds` + `_msn`/`_sk`/`_s` | **referenced, not shipped** — vanilla Skyrim files, used by the merged 3BA body only |

The NIFs reference `textures\melodic\buisenesswoman\…` (note the typo in the
author's folder name); the archives store the same files flat or in numbered
variant folders, so any port must **remap texture paths**, not copy them 1:1.
Our inventory resolves all garment references — 0 missing after normalization.

---

## 3. What already works (built today, in this branch)

`tools/skyrim-nif/` is new and has no dependency beyond numpy/Pillow:

| file | what it does | state |
| --- | --- | --- |
| `nif.py` | Skyrim SE NIF reader: block table, node tree, `BSTriShape`, `BSDismemberSkinInstance` → `NiSkinData`/`NiSkinPartition` (that is where the geometry actually lives for skinned SSE shapes), `BSLightingShaderProperty` → `BSShaderTextureSet`, alpha flags, body-part ids | reads all 12 meshes; only `NiSkinData` (the redundant per-bone copy) is skipped |
| `preview.py` | Pillow contact sheets for `.dds`, and a z-buffered flat-shaded four-view renderer for the meshes | outputs `docs/previews/business_woman_{outfit,textures}.png` |
| `inventory.py` | the report above, as JSON + Markdown + previews | `build/skyrim-nif/source_inventory.json` |
| `skeleton_map.json` | XPMSE/3BA → PAYDAY 2 LAS bone map, with the helper-bone folds and the 3BA-only bones to drop | covers **53/53** bones actually used by the meshes |
| `nifly_wrap.cpp` + `nifly_bridge.py` + `crosscheck.py` | the same files decoded by **nifly** (the library behind Outfit Studio) through a ctypes bridge, shape by shape | **91/91 checks agree**, vertex and UV deltas exactly `0.0`; see [`TOOLING.md`](TOOLING.md) and [`CROSSCHECK.md`](CROSSCHECK.md) |

Validated three ways: byte-exact against nifly (91/91 checks), by the invariants
below, and by eye — the assembled outfit renders correctly from four angles
(`docs/previews/business_woman_outfit.png` — jacket, skirt and shoes; the
necklace is a thin band and reads as a small cluster at the neck), and the
contact sheet shows the black default palette including the 0-byte
`Glasses_norm` placeholder.

---

## 4. Feasibility, measured rather than assumed

The PAYDAY 2 question is "does this rig fit the player skeleton". Both skeletons
decode to world-space joint positions, so the answer is arithmetic:

| joint | Skyrim 3BA (cm) | PD2 2B LAS template (cm) |
| --- | --- | --- |
| pelvis / `Hips` | z 98.4 | z 101.8 |
| spine chain | 103.8 / 116.3 / 130.3 | 114.7 / 126.9 / 139.2 |
| clavicle | 156.7 | 151.0 |
| upper arm | 152.1 | 146.7 |
| forearm | 122.4 | 133.3 |
| hand | 103.9 | 124.5 |
| knee | 47.9 | 52.7 |
| ankle | 8.7 | 9.9 |
| pelvis → sole | 89.7 | 91.9 |

So:

* **Height matches to 2 %** (`scale_ratio 1.02`) — no global rescale; the
  existing per-bone similarity fit in `tools/pd2-las/build_models.py` is enough.
* **The arms are in different poses.** In the Skyrim source the hand hangs at
  z ≈ 104 cm, in the PD2 template at z ≈ 124 cm with an elbow bend. This is
  exactly the failure the `tools/pd2-port/STATUS.md` §5 invariant describes
  (align in the *animated standing pose*, not in bind pose) — reuse that work,
  do not re-derive it.
* **Skyrim's `Spine [Spn0]` sits at the pelvis** (98.4 → 103.8 is 5 cm), while
  PD2's `Spine` is mid-abdomen (101.8 → 114.7 is 13 cm). Spine weights must be
  redistributed, not just renamed.
* **The meshes only weight one finger bone per hand** (`… Finger00 [LF00]`), so
  hands will be rigid unless the fingers are re-skinned from the collar data.
* **28 % of the 3BA body is not covered by any garment** (5 202 of 18 436
  vertices are > 2 cm from the nearest garment vertex): the whole lower leg, most
  of the thigh, half the hips, the V-neck chest and the hands. Those are the
  vertices that need a real skin texture — see §1.1. Torso is well covered
  (557 exposed vertices), so the jacket does its job.

Measured joint targets are in the table above; the full map, including the folds
and the drop list, is `tools/skyrim-nif/skeleton_map.json`.

---

## 5. Route options

### A. PAYDAY 2 LAS outfit — the chosen route

Same product shape as `dist/Miranda_LAS.zip`: `assets/units/<name>/skins/<name>/`
with a third-person and a first-person model, mask and armour hidden, registered
through BeardLib + Legendary Armour Skins. The 3BA body is kept, so the pack is a
full-body replacement: body + jacket + skirt + heels (+ necklace, + glasses).

Work items, in order:

1. **One mesh, one skeleton.** Merge `3BA` + `0_Jacket` + `0_Jacket2` +
   `0_Skirt` + `0_Heels001` + `0_Necklace` into the PD2 unit, retargeted onto the
   2B LAS skeleton with the existing similarity-fit machinery
   (`tools/pd2-las/build_models.py::retarget_maps`). Garments ride on the same
   bone transforms as the body, so a garment vertex keeps sticking to the skin it
   was fitted to.
2. **Fold the helper bones** — twists, belly, butt, breasts, and the 10 3BA-only
   bones — per [`skeleton_map.json`](../../tools/skyrim-nif/skeleton_map.json)
   (53/53 used bones covered), renormalise the four weights per vertex. Order
   matters: fold first, then retarget, or the twist weights leak onto bones that
   do not exist.
3. **Pose-correct the arms** in PD2's standing pose (§4) — the source arms hang
   at z ≈ 104 cm, the template's are at ≈ 124 cm with an elbow bend.
4. **Skin textures** for the exposed 28 % of the body (see §1.1), and a
   `mtr_skin` material with PD2's `ALPHA_MASKED`/gloss contract.
5. **Materials.** Skyrim `BSLightingShaderProperty` + 9-slot texture set →
   PD2 `*.material_config` with `df`/`nm` textures. Normal maps are DXT5nm and
   need the channel swizzle (`dds.pd2_normal_channels(..., invert_y=True)`);
   diffuse alpha must stay low (gloss contract, `tools/pd2-port/STATUS.md` §4);
   the `*_metal` gloss masks have no PD2 equivalent and become per-material
   constants.
6. **Alpha.** All garments use `NiAlphaProperty` 4844 (blend + test, threshold
   128) — treat as `ALPHA_MASKED`, not blended: sequins and the open jacket front.
7. **Heels.** The shoe is modelled around a raised heel and `Heels_0.nif` ships
   the 3BA `feet` shape already pitched to it. PD2's foot bones are flat, so the
   ankle needs the shoe's pitch or the instep clips.
8. **First-person arms.** Nothing in the pack is a first-person model. Derive
   them from the jacket sleeves + body arms, or ship the TPP unit first and add
   `fps_*.model` later (the Miranda line added it after the third-person unit
   worked).
9. **Decimate the necklace** (26 961 verts → a PD2-scale budget) before it goes
   into the unit.
10. **In-game check**, then (only with Melodic's permission) a tracked
    `dist/*.zip` + sha256 + previews, like every other pack in this repo.

Deliverable shape: `BusinessWoman_LAS.zip` with a BeardLib manifest, locales,
2 models, ~6 material configs and ~10 textures — comparable to
`dist/Miranda_LAS.zip` (5.4 MB).

### B. Keep it on Skyrim

Nothing to do: the five archives *are* a working SE mod. If you want a variant
(LE conversion, a different palette, glasses restored), that is a much smaller
job and needs no rig work — say so and it becomes a `tools/skyrim-nif` export
instead of a port.

### C. Anything else

The only target-independent work is what exists now: the reader, the inventory,
the previews and the bone map. A different engine needs its own skeleton
decoded first, then the same three-step plan (fit → fold → pose-correct).

---

## 6. Risks that survived the audit

* **Missing glasses mesh** (§1.2) — a shipped "Business Woman" pack without them
  is 4/5 of the outfit.
* **Necklace density** — 26 961 vertices on a neck band; needs decimation in any
  engine with a vertex budget (`npc_criminal_*` bodies are ~5 000 vertices).
* **HDT physics** — the skirt is meant to sway; statically skinned it will look
  stiff at the hem when crouching. The 13 skirt bones are the seams where a
  physics chain would attach.
* **Body ownership** — the merged 3BA body (and its vanilla body textures) must
  not travel into a shipped pack.
* **Rights** (§1.5) — private use only until Melodic says otherwise.
* **The `.esp` is irrelevant off-Skyrim** — it is useful as documentation of the
  intended set (6 pieces, tempering recipes, the "Xtra" jacket variant) and as
  proof that `Glasses_1.nif` is expected to exist.

---

## 7. Where the pieces live

```
1.zip .. 5.zip                        user-supplied source (tracked at repo root)
tools/skyrim-nif/nif.py               Skyrim SE NIF reader (pure Python)
tools/skyrim-nif/preview.py           .dds sheets + flat-shaded mesh renders
tools/skyrim-nif/inventory.py         this report (JSON / Markdown / PNG)
tools/skyrim-nif/skeleton_map.json    XPMSE 3BA -> PD2 LAS bone map (53/53 used bones)
tools/skyrim-nif/nifly_wrap.cpp       C ABI over ousnius/nifly (cross-check oracle)
tools/skyrim-nif/nifly_bridge.py      ctypes loader for the above
tools/skyrim-nif/build_nifly.sh       clone + compile nifly (~90 s, g++ only)
tools/skyrim-nif/crosscheck.py        nif.py vs nifly, per shape, all 12 meshes
docs/skyrim-nif/TOOLING.md            why nifly works here and PyNifly/PyFFI/SkyMeshGLTF do not
docs/skyrim-nif/CROSSCHECK.md         91/91 checks green, vertex Δ = 0
docs/previews/business_woman_*.png    tracked previews
build/skyrim-nif/                     generated report + inventory + crosscheck (gitignored)
tools/pd2-las/                        the pipeline to reuse for route A
```
