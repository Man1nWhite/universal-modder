# Skyrim 3BA outfit (`1.zip` … `5.zip`) — source audit and port plan

Status: **feature-complete offline** — the outfit (3BA body + both jacket layers
+ skirt + heels + decimated necklace) exists as a PAYDAY 2 Diesel model with
every joint on the LAS skeleton, its own textures, `material_config`s, a
first-person arms unit and a pack folder. It stands on the floor, its neck is
closed, and the template's head (someone else's character) is stripped out.
What is left is the in-game check on Windows.

Target decided (2026-11-02): a **PAYDAY 2 LAS outfit, keeping the 3BA body** as
the outfit's body; **black** palette, **both jacket layers**, **no glasses** (the
mesh is not in the archives), skin texture **authored** rather than shipped.

This page answers "can you make an LAS outfit out of these `.nif` files, and
what do you need?" with measured numbers instead of guesses.
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

| # | Item | Status |
| --- | --- | --- |
| 1 | **Body skin textures** — the merged 3BA body points at vanilla `femalebody_1` files that are not in the archives, and 28 % of the body surface stays visible with the garments on (measured: all of the lower legs, most of the thighs, half the hips, the V-neck chest, the hands) | ✅ **authored** — `tools/pd2-las/skin_texture.py` bakes a 2048² diffuse + normal from the mesh itself (cavity AO, anatomy shading, mottle) with the tone sampled as statistics from the 2B pack's skin. No Bethesda pixels, no Overkill pixels. |
| 2 | **Glasses mesh** — `4.zip` has no `Glasses_*.nif` although the plugin references `Melodic\Business Woman\Glasses_1.nif` | **decided: ship without glasses.** The outfit is jacket + skirt + heels + necklace over the 3BA body. |
| 3 | **Colourway** — `1.zip` black default; eight palettes across `2.zip`/`3.zip` | **decided: black** (`1.zip` diffuse + normal + metal). |
| 4 | **Jacket variant** — `0_Jacket` vs `0_Jacket2` in the same NIF | **decided: both.** They are not alternatives: `0_Jacket` is the sleeved blazer (101.8-163.0 cm) and `0_Jacket2` is the buttoned bustier worn *under* it (116.6-165.1 cm), which is why the plugin calls the second armour record "Business Woman **Jacket Xtra**" and why both point at the same NIF. Shipping `0_Jacket2` alone leaves the torso and arms bare. `--jacket blazer|bustier` drops one for experiments. |
| 5 | **Redistribution permission** — `5.zip/Please Read.txt`: *"do not publish this mod outside Loverslab without permission"* (author **Melodic**) | **open.** Private build only until the author says otherwise. |
| 6 | **In-game check** on Windows (PD2 + SuperBLT + BeardLib + LAS) | **open.** Nothing ships before it. |

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

## 3. What already works (built in this branch)

| piece | what it does | verified how |
| --- | --- | --- |
| `tools/skyrim-nif/nif.py` | Skyrim SE NIF reader (header, `BSTriShape`, `NiSkinPartition` geometry, `BSDismemberSkinInstance`, materials, legacy `NiTriShape` for the `_g` files) | **byte-exact against nifly**: 91/91 checks on all 12 meshes |
| `nifly_wrap.cpp` + `nifly_bridge.py` + `build_nifly.sh` + `crosscheck.py` | nifly (the Outfit Studio library) compiled with `g++` behind a C ABI, loaded with ctypes — the oracle behind the row above | [`TOOLING.md`](TOOLING.md), [`CROSSCHECK.md`](CROSSCHECK.md) |
| `preview.py`, `inventory.py` | `.dds` sheets, four-view mesh renders, the audit report | tracked previews |
| `skeleton_map.json` | XPMSE/3BA → PD2 LAS bone map, helper-bone folds, 3BA-only drops | covers 53/53 bones the meshes use |
| `tools/pd2-las/skyrim_source.py` | `.nif` → the `ModelData` contract the LAS authoring path takes: world-space vertices, helper bones folded, ≤3 weights, one submesh per material | 7 tests in `tests/test_skyrim_retarget.py` |
| `tools/pd2-las/skyrim_retarget.py` | XPMSE/3BA → PD2 player skeleton: one core similarity fit + axial chains for spine/arms/legs | **every joint lands on its PD2 joint (error 0.00 cm)** |
| `tools/pd2-las/build_business_woman.py` | end-to-end: `4.zip` → `business_woman.model` + four-view sheet | see below |

Real output of the pipeline (gitignored, regenerate):

```
source: 55099 verts / 100845 tris over 20 PD2 bones
  materials: {'skin': 23960, 'jacket': 14674, 'jacket2': 10385, 'skirt': 1312, 'heels': 4768}
[body] orientation breaks: 0, normals agree with winding: 98.5%
group body: 55099 verts, 100845 tris, palette 20, slots mtr_body/mtr_heels/mtr_jacket/mtr_jacket2/mtr_skirt
group shadow: 55099 verts, 100845 tris, palette 20, shadow_caster
wrote build/skyrim-nif/business_woman.model (10988316 bytes)
pack  -> dist/BusinessWoman_LAS
zip   -> dist/BusinessWoman_LAS.zip
```

`docs/previews/business_woman_pd2.png` is the four-view flat sheet of that model;
`docs/previews/business_woman_textured.png` is the same mesh with the packed
textures sampled through its own UVs, which is what proves the mapping, and
`docs/previews/business_woman_materials.png` shows every shipped map next to the
channels PD2 actually reads.

Why the bone list is 20 and not 53: BodySlide exports only the bones the merged
mesh actually weights, and these garments are skinned to 20 deform joints (no
fingers past the first thumb, no toes, no neck/head — confirmed against the
file's node list). The toes, neck and head simply do not exist in the source, so
nothing has to be invented for them; they ride the chain above them.

### 3.1 Materials: what the two engines disagree about

A Skyrim `BSLightingShaderProperty` hands over up to nine textures; Diesel binds
two. The mapping is mostly boring (diffuse → `df`, normal → `nm`) except for the
alpha channels, which mean **opposite things**:

| channel | Skyrim | PAYDAY 2 |
| --- | --- | --- |
| diffuse alpha | opacity, tested by `NiAlphaProperty` | **gloss**: 0 = matte, 255 = mirror |
| normal alpha | specular strength | part of the `DXT5nm` packing (holds X) |

So a verbatim copy would turn every garment chrome and throw the real specular
away. `skyrim_materials.build_diffuse` keeps the colour texels, discards Skyrim's
opacity and writes `gloss = normal_alpha x gloss_scale x metal_mask`, which is
what the `*_metal` maps are for: jacket, jacket2 and skirt ship 16x16 **black**
(fully matte fabric), the necklace ships **white** (gold). The normal maps are
swizzled `R = 255, G = 255 - Y, B = 0, X → alpha`, i.e. Diesel's `DXT5nm` layout,
with every mip level written.

| material | shape | diffuse | normal | gloss source | shipped size |
| --- | --- | --- | --- | --- | --- |
| `mtr_body` | `3BA` + `feet` | authored | authored | authored (`skin_texture.py`) | 1024² |
| `mtr_jacket` | `0_Jacket` | `Jacket_diffA` | `Jacket_norm` | `Jacket_metal` (16² black) | 1024² |
| `mtr_jacket2` | `0_Jacket2` | `Jacket2_diffA` | `Jacket2_norm` | `Jacket2_metal` (16² black) | 1024² |
| `mtr_skirt` | `0_Skirt` | `Skirt_diffA` | `Skirt_norm` | `Skirt_metal` (16² black) | 1024² |
| `mtr_heels` | `0_Heels001` | `Heels_diffA` | `Heels_norm` | `Heels_metal` (512², mean 24) | 1024² |

Two findings worth recording:

* **The Skyrim normal maps are nearly flat** — R and G sit at 126 ± 4…20 with the
  real detail in alpha (Skyrim's specular). That is faithful: the fabric weave in
  these garments is painted into the diffuse, and the specular map is what we
  repurposed as gloss. A "more normal" normal map would be invented detail.
* **The necklace's normal is inert** (R = G = 126, B = 255) and its metal mask is
  solid white, so it will read as polished gold for free once it is decimated.

### 3.2 Winding: a bug this pass found

`transfer_group` swapped two triangle corners per face ("CW → CCW"), but carried
the vertex normals through unchanged, so every mesh it authored came out
**inside-out**: signed volume −110 346 cm³, normals agreeing with the winding on
1 % of faces. The shipped 2B reference model and every Skyrim source mesh both
score ~0.97 with **positive** volume, so the swap was inverting both.

The fix is in the source adapter, not the shared authoring path: `skyrim_source`
now reverses the NIF's clockwise winding, which the existing swap then cancels
exactly. `build_models.winding_agreement()` measures it (98.5 % agree, volume
+110 346 cm³) and `transfer_group` refuses to write a model below 90 %, so this
cannot silently come back.

### How the reader is validated

Three independent proofs, all reproducible:

1. **nifly agrees exactly** — 91/91 checks across all 12 meshes: same shape
   lists, vertex counts, vertex positions (delta `0.0`), triangle sets, bone
   lists, texture paths, node counts; per-bone weight totals within `3.6e-2`
   (float weights vs the half-float partition copy).
2. **Invariants** — weights sum to 1.0 per vertex, triangle indices in range,
   the 3BA body comes out 163 cm tall, the skirt sits at 86.6–117.7 cm, UVs land
   inside 0…1 on the 2048² atlases.
3. **By eye** — `docs/previews/business_woman_outfit.png` (four views of the
   source meshes) and `docs/previews/business_woman_textures.png` (the black
   default palette, including the 0-byte `Glasses_norm` placeholder).

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
full-body replacement: body + buttoned jacket + skirt + heels.

| # | Work item | State |
| --- | --- | --- |
| 1 | **One mesh, one skeleton** — 3BA + feet + `0_Jacket2` + `0_Skirt` + `0_Heels001` merged and retargeted onto the LAS skeleton | ✅ `skyrim_source.py` + `skyrim_retarget.py`; every joint on target (0.00 cm) |
| 2 | **Fold the helper bones** — twists, belly, butt, breasts; drop the 10 3BA-only bones | ✅ folded before retarget, weights renormalised to ≤3 influences |
| 3 | **Pose-correct the arms** into PD2's bind pose | ✅ axial chains spread them from the source's 60° hang to PD2's A-pose |
| 4 | **Skin texture** for the exposed 28 % of the body (authored, PD2-appropriate) | ✅ `skin_texture.py` — 2048² DXT5 df + nm with full mip chain, baked in the mesh's own UV space |
| 5 | **Materials** — `BSLightingShaderProperty` + 9-slot texture set → `*.material_config` (`df`/`nm`, DXT5nm swizzle with `invert_y`, `*_metal` gloss → alpha) | ✅ `skyrim_materials.py`; 10 textures, 5 materials, guide contract (`CONTOUR`, `unique`, contour variables) — see §3.1 |
| 6 | **Alpha** — all garments use `NiAlphaProperty` 4844 | ✅ **nothing to do**: `4844/128` is alpha-*tested*, but no diffuse in `1.zip` has a texel below 128 (measured 0.00 %), so the test never fires and the plain template is correct. A future palette with cut-outs needs `ALPHA_MASKED` + `alpha_ref`. |
| 7 | **Heels** — keep the shoe's ankle pitch while PD2's foot bones are flat | ✅ **measured, then re-fitted**: the source shoe stands on z = −12 cm (Skyrim raises heel rigs by the heel height), so shipped verbatim the character sank ~12 cm into the floor. `fit_feet_to_ground` compresses the shoe below the ankle joint by 0.42 with an eased ramp; the sole now lands at z = 0.000 and the ankle joint stays put. `--heels keep` ships the source pose. |
| 8 | **Necklace** — 26 961 verts is a PD2-scale problem: decimate, or drop it into the pack as a separate drawable | ✅ **shipped, decimated 9:1** to 3 000 verts / 3 918 tris. 222 bead islands, 117 verts each, 4 mm across; per-island vertex clustering leaves the silhouette unchanged and 0.05 mm mean / 0.11 mm max off the source surface. Blend weights are copied from the nearest source vertex, never averaged. |
| 9 | **Head and hair** — Skyrim ships neither; the LAS unit needs a `g_head` (reuse the 2B/PD2 head and its materials, or port a Skyrim head) | ✅ **decided: ship without one, and leave no hole.** The template's `g_head`/`g_head_lod1` are *deleted* from the pack (they are the 2B character; shipping her face here would be both wrong and unlicensed) and the 3BA collar is closed with a 26-triangle fan weighted like the neck it caps. The heister's own head is what LAS supplies when the outfit sets `hide_mask`. |
| 10 | **First-person arms** — derive from the jacket sleeves + body arms, or ship TPP first | ✅ `extract_bones` slices the already-posed TPP geometry down to the arm chain (12 682 verts / 23 026 tris: skin + both sleeve layers), and both templates share an identical PD2 bind pose (verified: 0.00 cm delta on every arm joint), so no second retarget is needed. `fps_businesswoman.material_config` uses `DEPTH_SCALING`. |
| 11 | **Pack scaffold** — `bw_pack.py` with new IDs, locales, icon, `BUILD_INFO.json` | ✅ `dist/BusinessWoman_LAS/` (11 MB with textures); FPS unit deliberately absent until the arms exist |
| 12 | **In-game check**, then (only with Melodic's permission) a tracked `dist/*.zip` + sha256 + previews | ⬜ **the only thing left** — see `docs/skyrim-nif/in-game-checklist.md` |

Deliverable shape: `BusinessWoman_LAS.zip` with a BeardLib manifest, locales,
2 models, 2 material configs and 12 textures — 13 MB, comparable to
`dist/Miranda_LAS.zip` (5.4 MB) but with a full-body outfit rather than a
character replacement.

Two construction notes that are not obvious from the outside:

* **The bone list is 20, not 53.** BodySlide only exports the bones the merged
  mesh weights; these garments are skinned to 20 deform joints (no fingers past
  the first thumb, no toes, no neck, no head). `skeleton_map.json` covers the 53
  names that appear anywhere in the outfit, but a given NIF carries only its own
  subset. Anything the source lacks rides its chain's fit.
* **The 3BA body ships without vertex normals.** Its descriptor flags are
  `0x043` where the garments carry `0x05b`; `nif.smooth_normals()` rebuilds them
  from the topology (and `skyrim_source` uses it automatically). Anything that
  reads these SSE meshes has to do the same or it lights them flat black.
* **`build_models.retarget_maps` cannot drive this rig.** It keys off Source
  names (`HandMiddle1`, `ToeBase`) and needs the full 53-joint skeleton; with 20
  joints and no fingers it silently lands the arms in the wrong place. That is
  why `skyrim_retarget.py` exists as its own module rather than a flag.

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
* **Body ownership** — the 3BA body is kept (decided), but its vanilla
  `femalebody_*` textures are not: they are replaced by authored ones, so no
  Bethesda asset travels in a pack.
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
tools/pd2-las/skyrim_source.py        .nif -> ModelData adapter (bones resolved to PD2 names)
tools/pd2-las/skyrim_retarget.py      XPMSE/3BA -> PD2 skeleton fit (joints land exactly)
tools/pd2-las/build_business_woman.py the end-to-end build (4.zip -> business_woman.model)
tools/pd2-las/skin_texture.py         authored skin: UV-space bake -> df + nm DXT5 with mips
tools/pd2-las/skyrim_materials.py     Skyrim shader -> PD2 df/nm/gloss + material_config
tools/pd2-las/decimate.py             per-island vertex clustering for over-dense meshes
tools/pd2-las/bw_pack.py              LAS pack folder: manifest, hook, locales, icon, hashes
tools/pd2-las/preview_textured.py     UV-sampling textured render + texture contact sheet
docs/skyrim-nif/in-game-checklist.md  the 14 in-game checks that are still outstanding
tests/test_skyrim_retarget.py         7 offline tests for the two modules above
tests/test_skin_texture.py            10 offline tests for the baker (incl. real meshes)
tests/test_skyrim_materials.py        25 offline tests for materials + pack assembly
tests/test_skyrim_fit.py              24 offline tests for the heel, necklace, cap and fps slicers
docs/previews/business_woman_*.png    tracked previews (source, PD2 model, textured, materials, skin)
build/skyrim-nif/                     generated report, inventory, crosscheck, .model (gitignored)
tools/pd2-las/                        the rest of the LAS pipeline
```
