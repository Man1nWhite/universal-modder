# Skyrim 3BA outfit (`1.zip` … `5.zip`) — source audit and port plan

Status: **source decoded and audited; nothing ported yet.** This page answers
"can you make an LOS outfit out of these `.nif` files, and what do you need?"
with measured numbers instead of guesses. Regenerate it any time:

```bash
bash tools/pd2-las/bootstrap.sh          # once, for the venv (pillow/numpy)
.venv/bin/python tools/skyrim-nif/inventory.py \
    --json build/skyrim-nif/source_inventory.json \
    --markdown build/skyrim-nif/REPORT.md \
    --previews docs/previews
```

Machine-readable inventory: `build/skyrim-nif/source_inventory.json` (gitignored,
rebuild it). Tracked previews: `docs/previews/business_woman_outfit.png`,
`docs/previews/business_woman_textures.png`.

---

## 1. Answer first: what I need from you

| # | Needed | Why it blocks |
| --- | --- | --- |
| 1 | **What "LOS" means / which target** — this repo's product is a **PAYDAY 2 LAS** (Legendary Armour Skin) outfit, built the same way as the Miranda packs. If you meant Skyrim SE armour, Fallout 4, or something else, say which and the plan changes from §5 on. | The rig, the file format and the installer are completely different per target. Everything up to §4 is target-independent. |
| 2 | **The glasses mesh.** `4.zip` has `Heels_*`, `Jacket_*`, `Necklace_*`, `Skirt_*` — no `Glasses_0.nif` / `Glasses_1.nif`, although `5.zip` ships glasses BodySlide sliders (`[Melodic] Business Woman Glasses 3BA.osp/.osd/.nif`) and the plugin's armour add-on `0BusinessWomanGlasses` points at `Melodic\Business Woman\Glasses_1.nif`. | The outfit as shipped cannot be complete without it. Either send the file or we ship 4 of 5 pieces. |
| 3 | **Which colourway** — `1.zip` is the default (black jacket + black skirt, nude/beige shoes), `2.zip` and `3.zip` hold 8 palettes: navy (`3/`), red and maroon (`4/`, `7/`), white (`5/`), grey (`2/`, `9/`), gold-rust (`8/`) plus the black default. | Textures are 2048² each; the pack should ship one palette, not eight. |
| 4 | **Do we keep the 3BA body?** `Jacket_0.nif` also contains a full nude 3BA body (`3BA`, 18 436 verts / 35 904 tris) plus `3BA_Vagina`, `3BA_Anus`; `Heels_0.nif` contains `feet`. BodySlide merges them in so the outfit fits. Any non-Skyrim port must delete them (the target supplies its own body) — confirm you do not want them kept. | Shipping them into another game means shipping a nude body you do not own; and they carry body textures (`textures\actors\character\female\femalebody_1.dds`) that are not in the archives. |
| 5 | **Redistribution permission.** `5.zip/Please Read.txt`: *"do not publish this mod outside Loverslab without permission"* — author **Melodic**. | Private/experimental use is fine. Publishing a port (`dist/*.zip` + release) needs the author's OK, exactly like the ME2 Miranda line's asset-rights gate. |
| 6 | **An in-game check** for whatever the target is (for PAYDAY 2: Windows + the game + SuperBLT + BeardLib + LAS). | Repo rule: no release without an in-game check — the retired 2026-10-18 route died precisely on unverifiable crashes. |

Nice to have: whether the skirt/necklace need **HDT physics** motion
(`5.zip/Please Read.txt` lists `HDT Physics Extensions` as a requirement). No
target in this repo has a physics skin, so the port will be statically skinned
unless you want to fake sway with extra bones.

---

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

Validated by eye: the assembled outfit renders correctly from four angles
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

---

## 5. Route options

### A. PAYDAY 2 LAS outfit (this repo's default assumption)

Same product shape as `dist/Miranda_LAS.zip`: `assets/units/<name>/skins/<name>/`
with a third-person and a first-person model, mask and armor hidden, registered
through BeardLib + Legendary Armour Skins.

Work items, in order:

1. **Fit, per garment.** The outfit is built for 3BA; PD2 has one body. Either
   (a) re-fit the garment vertices onto the PD2 body with a similarity fit per
   bone (`skeleton_map.json` + the `retarget_maps` machinery), or (b) keep the
   3BA body shape as the "skin" and retarget its 18 436 vertices too — that is
   what the Miranda line does, because a LAS outfit is a full body replacement.
   (b) is the safer read of the LAS contract and uses the code that already
   exists.
2. **Fold the helper bones** (twists, belly, butt, breasts, 3BA-only bones) per
   `skeleton_map.json`; renormalise the four weights per vertex.
3. **Pose-correct the arms** in the standing pose (see §4), then export.
4. **Materials.** PD2 materials are `*.material_config` + `*_df.texture` /
   `*_nm.texture`; the garment normal maps are DXT5nm-style Skyrim normals and
   must be re-encoded (the `dds.pd2_normal_channels` helper already does the
   channel swizzle), diffuse alpha must stay low (gloss contract, `STATUS.md`
   §4), and the `*_metal` masks have no PD2 equivalent — fold them into a fixed
   gloss value or a per-material constant.
5. **Transparency.** All garments use `NiAlphaProperty` flags `4844`
   (blend + test, threshold 128) — sequins and the jacket's open front. PD2 has
   `ALPHA_MASKED`; treat the garment as alpha-tested, not blended.
6. **Heels.** The shoe is modelled around a raised heel; `Heels_0.nif` ships the
   posed 3BA `feet` shape at that angle. PD2's foot bones are flat, so the foot
   has to be rotated to the shoe's pitch or the instep will clip.
7. **First-person arms.** No gloves/V arms exist in this pack. Either derive them
   from the jacket sleeves (expensive) or ship the third-person unit first and
   add FPS arms later, as `fps_miranda.model` did.
8. **In-game check** before anything is published.

Estimated blob count: 4 garments (3 if the glasses stay missing) ×
(TPP model + FPS model + material config + 2–4 textures), plus the BeardLib
manifest and locales — the same shape as `dist/Miranda_LAS.zip`.

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
1.zip .. 5.zip                  user-supplied source (tracked at repo root)
tools/skyrim-nif/nif.py         Skyrim SE NIF reader
tools/skyrim-nif/preview.py     .dds sheets + flat-shaded mesh renders
tools/skyrim-nif/inventory.py   this report (JSON / Markdown / PNG)
tools/skyrim-nif/skeleton_map.json   XPMSE 3BA -> PD2 LAS bone map (53/53 used bones)
docs/previews/business_woman_*.png   tracked previews
build/skyrim-nif/               generated report + inventory (gitignored)
tools/pd2-las/                  the pipeline to reuse for route A
```
