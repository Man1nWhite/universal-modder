# HANDOFF — BusinessWoman (Skyrim 3BA → PAYDAY 2 LAS) — read this first

*Last updated: 2026-11-04, after the waist-pivoted upper-body alignment pass.*
*Everything here was measured in-session; nothing is inherited from memory alone.*

**Mission:** an equipable full-body "Business Woman" outfit (Skyrim SE 3BA body +
Melodic blazer / bustier / skirt / heels / necklace) for PAYDAY 2, delivered as a
Legendary Armour Skins (LAS) armor skin, built reproducibly from `4.zip` (meshes) +
`1.zip`/`2.zip`/`3.zip` (textures) + the `references/2b.rar` PD2 template, by
`tools/pd2-las/build_business_woman.py`. The outfit ships **no head and no hands**:
the heister's own head (Miranda) and gloves / forearm adapter show through.

**Sibling docs (do not duplicate):** [`tools/pd2-port/MODLOG.md`](../../tools/pd2-port/MODLOG.md)
is the journal (newest first); [`tools/pd2-port/STATUS.md`](../../tools/pd2-port/STATUS.md)
is the *Lawson/ME2* route; [`docs/pd2-las/HANDOFF.md`](../pd2-las/HANDOFF.md) is the
*Miranda/L4D2* route. This page is the **BusinessWoman / Skyrim** route only.
Reusable gotchas: [`knowledge/games/payday-2/las-moog-outfit-porting.md`](../../knowledge/games/payday-2/las-moog-outfit-porting.md)
notes **28–39**. User-side game test: [`in-game-checklist.md`](in-game-checklist.md).

---

## 1. Current state (verified)

| | |
|---|---|
| Branch | `arena/97ae3b36-universal-modder` (active). |
| Deliverable | `dist/BusinessWoman_LAS.zip` — 26 entries, sha256 `c89edf9edd3f08289e8d701509048d1477f95083b125d90d449e7d4ff97b3bc8` |
| Hands | **adapter route** — no hand geometry shipped; build aborts if any vert is >0.5 hand-bone weighted (`count_hand_verts`) |
| Head | none shipped; template `g_head`/`g_head_lod1` dropped; neck closed with `cap_holes` |
| Body skin tone | matched to Miranda head diffuse: base `(172,134,106)`, unity gain; shipped `bw_body_df` median `(172,133,106)` |
| Neck | full-height neck kept; upper outfit pitched back 1.8° about waist (`turn_upper_body`) to align to the heister head without tilting legs |
| Forearms | shirt cuff retracted (9 up / 2.5 inward) + blazer sleeve extended ~3 cm to overlap glove |
| Bust | source-faithful **1.32×** (`restore_bust`) — do NOT dial back |
| Gates | pytest **451 passed / 9 skipped / 1 pre-existing fail**; kb **PASS 246**; publish **26 / 0 / 1**; pyflakes clean |

The single pytest failure, `tests/test_build_models.py::test_retarget_joint_errors_and_palettes`
(Miranda tpp RightArm ~5.7 cm), is **pre-existing and unrelated** to BusinessWoman. Do not
"fix" it as part of this route; it predates the saga.

### Commit chain (newest first)
```
f67f7de forearms redo — hide shirt cuff + overlap glove with blazer sleeve
302ca35 neck redo — TURN whole body instead of taper/hide
4090de2 match body skin colour to Miranda's head texture
a000d67 fix forearms — drop shipped source hands, enforce adapter route
60ebf6f neck recenter+taper   (SUPERSEDED by 302ca35 — do not resurrect)
9cbeaa7 white arm patches are SKIN — extend underarm skin tuck (z_lo 125)
90df4d6 retract white wrist cuff into blazer sleeve
24d7138 tuck white shirt sleeves under blazer
0b049e9 uniform albedo (real blotch fix) + adapter route, no authored hands
2097a98 rebuild stale body textures + backface-culled pose-sim verification
342a3bb graft hands, smooth skin, shoulder overlap stay   (hands later removed)
```

---

## 2. Recovery / quickstart (the sandbox WILL wipe you)

The arena sandbox periodically **wipes `.venv`, `/tmp` and `build/` and rewinds local
git to the base merge commit while the worktree looks dirty**. The work is safe on the
remote. Recover:

```bash
git fetch origin
git reset --hard origin/arena/68a9d94f-universal-modder
bash tools/pd2-las/bootstrap.sh        # venv + 2B templates + builds + tests + lint
```

If you only need the BusinessWoman route (bootstrap also builds Lawson/Miranda):

```bash
python3 -m venv .venv
# PINNED: tracked dist bytes depend on these exact versions
.venv/bin/pip install pillow==13.0.0 numpy==2.4.6 pyyaml py7zr lupa pytest pyflakes
# templates (2b.rar -> /tmp/2bsrc), needs node+npm (registry.npmjs.org allowed):
mkdir -p /tmp/rarx /tmp/2bsrc && cd /tmp/rarx
npm init -y && npm install node-unrar-js
node -e 'const{createExtractorFromFile}=require("node-unrar-js");(async()=>{const e=await createExtractorFromFile({filepath:process.argv[1],targetPath:"/tmp/2bsrc"});console.log([...e.extract().files].length);})()' \
  "$OLDPWD/references/2b.rar"
cd "$OLDPWD"
.venv/bin/python tools/pd2-las/build_business_woman.py \
  --templates "/tmp/2bsrc/2B - LAS/assets/units/2b/skins/2b" --pack
```

Build is ~35 s (model) / ~80 s (`--pack`). **Commit + push early and often; NO PR.**

---

## 3. Pipeline order (build_business_woman.py, main)

`transfer_group` (retarget) → hands adapter guard → `restore_bust`(1.32) →
`tuck_underarm_skin`(0.7, z125–154) → `tuck_shirt_sleeves`(1.6) →
`weld_open_seams`(0.2 mm) → `follow_layer_weights`(z136–158) →
`tuck_shirt_collar`(z150, x0.93, z0.88) → **`slim_neck`**(z157–161, r≤8 cm,
x·0.55 y·0.70) → **`redress_from_source`**(blazer + shirt + necklace, k=6
clearances, body scale ≈1.25, **faded out above 108 source units** — the Skyrim
body ends at 114.1, so the collar keeps its retargeted shape) → `extend_sleeves_to_wrist`(jacket −2.5 / skin
−2.2 / shirt +1.0, t_knee 13) → **`tuck_necklace_chain`**(z156, ×0.80) →
`lower_collar`(z158, k=`COLLAR_K`=0.55, blazer + shirt only) → `turn_upper_body`(1.8°, smooth waist hinge) →
`cap_holes`(min_z155, skin-only, max_span14) → `assemble_model(drop g_head/g_head_lod1)`
→ textures (`skin_texture`) → `bw_pack.write_pack` → zip. Body **and** shadow get every
geometry pass. `extend_blazer_sleeves` and `tuck_shirt_cuffs` are **no longer called**
(superseded by `extend_sleeves_to_wrist`; see `FIXES-2026-11-04.md`).

`redress_from_source` is what fixes the **bare shoulders**: the retarget keeps
the body right but drags the blazer's neckline out over the trapezius, and since
the per-material vertex order is preserved it rebuilds every garment vertex on
the shipped body at the *source's* clearance (mean 0.6/1.1 cm, peak 7.6 cm at
the collar). The 3BA neck stub also has to be slimmed (`slim_neck`, 2B pack
is the reference) and the collar kept standing (`COLLAR_K`) — see Round 3 of
`FIXES-2026-11-04.md`. See `FIXES-2026-11-04.md`, "Round 2".

Key helpers live in `tools/pd2-las/build_models.py` (grep by name; line numbers shift):
`turn_upper_body`, `turn_body` (legacy primitive), `weld_open_seams`, `follow_layer_weights`, `tuck_shirt_collar`,
`extend_sleeves_to_wrist`, `tuck_shirt_sleeves`, `tuck_underarm_skin`, `lower_collar`,
`cap_holes`, `count_hand_verts`, `restore_bust`. Verification renders:
`tools/pd2-las/pose_zoom.py` (posed shoulder close-up) and `tools/pd2-las/glove_check.py`
(sleeve/glove junction with a glove proxy on the hand bone).
**`align_neck` and `trim_neck` still exist but are UNUSED** (the taper/hide neck was
rejected in-game; see note 38). `turn_body` remains a low-level whole-body helper;
the current pipeline uses `turn_upper_body` instead. Do not wire `align_neck` or
`trim_neck` back in.

Skin tone: `tools/pd2-las/skin_texture.py` `REFERENCE_TONE=(172,134,106)`,
`BODY_TONE_GAIN=1.0`; albedo is **flat** (geometry normals + game lighting supply shading).

---

## 4. Standing user constraints (do not violate)

- **Don't author hands.** No grafting/modelling/re-posing hand geometry. Adapter route so
  the game's gloves + `hnd_forearms` adapter show. Forearm/sleeve/cuff tweaks are garment-only.
- **Bust stays source-accurate at 1.32×.**
- **Commit + push, NO PR.** Present the zip when done.
- Neck: the neck must remain full-height to meet the head. The accepted correction from the user's in-game references is **pitch the upper outfit about the waist** (1.8° measured from the ~2 cm neck-axis offset), rather than trimming the neck or tilting the legs. See the latest note in `FIXES-2026-11-04.md`.
- Skin colour: match **Miranda's head** diffuse, not a generic swatch (note 37).

---

## 5. Known open issues / accepted residue

- **Armhole tears: FIXED (2026-11-04).** The beige patches were *not* an overlap gap — the
  blazer's seam is two exactly coincident vertex rows with different weights, so it split
  at any pose. `weld_open_seams` averages the rows (≠ the rejected overlap-edge weld, which
  merged two different surfaces). See `FIXES-2026-11-04.md`.
- **Sleeve/glove gap: FIXED (2026-11-04).** `extend_sleeves_to_wrist` stretches each arm
  layer until it reaches the PD2 hand joint (blazer 2.5 cm past it). Target numbers are
  `targets` inside that function if the in-game glove needs more/less.
- **Shirt collar "wings": mitigated (2026-11-04)** — weights follow the blazer + a mild
  collar nip. If they still flare in game, raise the *blazer's* collar, do not shrink the
  shirt further.
- **Neck/head/shoulder alignment: current focus.** The user supplied in-game front and
  side screenshots plus a Clover body and the Melodic source outfit for comparison. The
  neck must reach the head opening; do not shorten it to make the collar appear to fit.
  Use a small waist-pivoted upper-body pitch so legs stay vertical and the shoulder line
  is not dragged by a whole-body tilt. Keep those reference images' intent in mind for
  future iterations; the upload itself is transient and is not checked into Git.
- **In-game head reads lighter than body albedo** under some scene lighting. The albedo
  match is correct offline; if the user complains, tune body tone to compensate for the
  *in-game* head appearance, not the offline median.
- **Miranda retarget test** fails pre-existing (see §1); unrelated.

---

## 6. Workflow traps (each has burned a session)

- **Stale-artifact:** after ANY geometry/tone change, re-run `--pack` AND decode-verify the
  SHIPPED zip (a stale/graft zip once differed from a clean rebuild). Never trust build-tree alone.
- **Sandbox wipe:** see §2. Local git rewinds; `.venv`/`/tmp`/`build/` vanish. Recover from remote.
- **Material masks:** build masks from `md['atoms']`/`mat_names`, NOT vertex offsets.
- **Pose sign:** `pose_preview.pose(b,-41.5,41.5)` = arms-down; positive raises left arm.
  Reproducing idle poke-through = adduct ~33° + elbow bend ~28°.
- **Head attach offline:** template/Miranda head geometry is ALREADY in world cm — do NOT
  apply the drawable object matrix (it double-transforms and flips the head).
- **No scipy** in `.venv`; use numpy chunked nearest-neighbour.
- **`Template.worlds`** is a flat 16-float row-major matrix; translation = `[12:15]`.
- **edit/write tools cannot target `/tmp`;** put scratch under `build/` (gitignored).
- **Push transient errors** (TLS / Internal Server Error): retry with backoff; check the push
  exit code directly (a pipe to `tail` masks it).
- **Glove/adapter is a game asset** absent from the outfit model; to see the wrist junction
  offline, attach a stand-in (template hand tinted blue) in the posed render.

---

## 7. Verification recipes

- **Identify a poke-through layer:** posed render (adduct+bend) with ONE material overridden
  to a flat colour at a time (`mtr_body`=GREEN, `mtr_jacket2`=RED, `mtr_jacket`=BLUE). The
  rigid bind-pose preview hides deformation-only poke-through.
- **Wrist junction:** posed render + blue stand-in glove; confirm sleeve overlaps glove and no
  white cuff flap.
- **Neck:** attach Miranda head (raw world verts) and render front/side/back; confirm
  head→neck→collar continuous, no skin wings above collar back.
- **Skin tone:** decode shipped `bw_body_df` + `miranda_head_df`, skin-mask
  (R>G+4, G>B+2, 70<R<250, 10<R−B<120), compare medians (target within ~1/255).
- **Gates:** `.venv/bin/python -m pytest tests/ -q`; `-m um kb check`;
  `-m um publish check dist/BusinessWoman_LAS`; `-m pyflakes tools/pd2-las tests/test_hands_graft.py`.

---

## 8. Likely next asks / next steps

1. **In-game colour compensation** if the head still reads lighter than the body (tune tone
   against the *in-game* head, keep the regression test meaningful).
2. **Further forearm/neck polish** from new screenshots — always diagnose with the posed
   per-material / stand-in-glove / head-attach renders BEFORE changing geometry.
3. **Armhole weld** only if the user reverses their rejection (it spikes the sleeve; note 31).
4. Keep MODLOG + knowledge notes current with each cycle; update the zip sha in §1.
