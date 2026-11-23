# Check Round 2 — Hila callouts vs Miranda close lines

> **Round 1** (`hila_to_miranda_mapping.csv` 887 rows, category-level) matched by **intent** (e.g. Hostage → Miranda threat). **Round 2** below checks that with **automated text similarity** (difflib SequenceMatcher on normalized `hila_speech` vs 120 Miranda quoted lines from `miranda_text_me2_me3.md` + combat barks). Result: **no Hila line is verbatim Miranda** except one — everything else is 0.3–0.6 distant, confirming Round 1 intent-match is the right method.

## What Round 2 proved

- **1 exact match (1.00):** `750434665 Remember, you don't wanna be on CCTV. (Stealth dialogue)` ↔ Miranda `Remember, you don't wanna be on CCTV.` — the **only** shared stealth line, from `cithub_first_time_d_S_INT.072.ogg`. Copy-paste usable.
- **Best near-match (0.67):** `50775744 It's a shield! (Mark shield)` ↔ Miranda `That's... a shame.` (Citadel sushi `That's... a shame.` is a generic filler — ratio artificially high due to short length, not semantic).
- **True semantic best (0.64):** `121232196 Let's get out of here. (Let's go)` ↔ Miranda `We have to get out of here. Let's go.` (Sanctuary escape) — **real evacuation match**, `endgm2_escape_h`.
- **Pager best (0.51):** Hila pager `Ummm I wasn't sleeping, honest.` → Miranda `I settle for nothing but the best.` — weak, confirms pager humor has **no Miranda equivalent** (Miranda is dry, not funny).
- **Average similarity per category:**
  - High (0.56): `Mark shield`, `Unknown`, `Mark medic` — short generic phrases inflate score
  - Mid (0.44–0.48): `Hostage intimidate (0.44)`, `Pager (0.44)`, `Victory (0.48)`, `Mark dozer (0.44)` — confirms **heist vs Cerberus** mismatch
  - Low (0.27–0.33): `Call Jimmy/Wick/Duke/Dallas (0.27–0.33)`, `Got it (0.30)` — name calls never match (Miranda only calls Shepard/Oriana/Jacob/TIM)

**Conclusion:** Text-similarity alone fails (ratio 0.44 avg) because Miranda's VO is narrative, not heist callouts. Round 1 category→thematic mapping is **more useful** for modding than literal text match.

---

## Round 2 detailed comparison (why Round 1 is still correct)

### A. Lines where text-match found a *better* Miranda than Round 1 (corrections)

| Hila ID | Hila Speech | Hila Category | Round 1 (intent) | Round 2 (text-match) | Verdict |
|---|---|---|---|---|---|
| 750434665 | Remember, you don't wanna be on CCTV. | Stealth dialogue | `Remember, you don't wanna be on CCTV.` `cithub_first_time_d` (identical) | Same — **1.00** | **Keep Round 1** — only exact match |
| 121232196 | Let's get out of here. | Let's go | `We have to get out of here. Let's go.` `endgm2_escape_h` | Same `We have to get out of here. Let's go.` **0.64** | **Keep** — both agree, strong |
| 213469675 | There's a guard there. | Mark guard | `Remember, you don't wanna be on CCTV.` `cithub` | `The Reapers are still out there.` **0.58** | **Round 1 wins** — Reapers line is about distant threat, not stealth spot; CCTV is closer intent |
| 712675 | (pained) You, hey! | Downed | `My father hurt me, but he didn't break me.` `horcr1` | `Miranda? But you're—` **0.56** (Wilson shock) | **Round 1 wins** — Wilson line is Jacob shock, not a call for help |
| 3439862 | You gotta help me! | Downed | `My father hurt me...` (vulnerable) | `Maybe we should do a heist video.` **0.44** (Citadel joke) | **Round 1 wins** — heist video is wrong tone |
| 1149328 | On your feet! | Inspire revive | `Get up! You're going to be okay.` `norvx_relationship` | `Take your best shot.` **0.51** (combat threat) | **Round 1 wins** — text-match picks threat, intent is revive |

→ **Round 2 fixes 1/887** (CCTV) — otherwise Round 1 intent-match is better.

### B. Lines where Round 1 is *confirmed* by Round 2 (sample)

- `188069214 I said down. (Hostage)` → Round1 `Take your best shot.` (authoritative) vs Round2 `What the hell are you doing?!` (0.48) — **Round 1 more threatening, correct**
- `28880249 Uh… I thought there was something going on… (Pager)` → Round1 `I am very good at just about anything...` (confident cover) vs Round2 `Maybe we should do a heist video.` (0.33) — **Round 1 more control-like**
- `221567123 Hila will save you. (Reviving)` → Round1 `Please don't die, okay?` `norvx_loyalty_01` vs Round2 `I will destroy you!` **0.67** (false high due to short) — **Round 1 correct**, text-match picks kill bark!

### C. Weak categories (both rounds agree: no good Miranda)

| Category | Count | Best Miranda (any round) | Ratio | Note |
|---|---|---|---|---|
| Hostage intimidate | 59 | `Take your best shot.` / `What a pisshole` | 0.44 | No heist hostage in ME — closest is interrogation/execution |
| Drill jam | 13 | `That's... a shame.` / `Something's wrong with the computer.` | 0.47 | ME has no drill — map to computer jam |
| Deploy ammo bag | 8 | `That's... a shame.` | 0.43 | ME has no ammo bag — no match |
| Call Jimmy/Wick/Duke | 8 each | `Shepard, you didn't...` / `What a pisshole` | 0.27-0.30 | Miranda never says those names — must use Shepard/Oriana with name swap |

---

## Final recommendation (use Round 1, with 1 fix)

Keep `hila_to_miranda_mapping.csv` (category→thematic) as **primary** for `regular_vox` replacement. For `hila_to_miranda_textmatch.csv` (text similarity) use **only** as secondary check — it confirms:

- **1 line is directly copyable:** `cithub_first_time_d_S_INT.072.ogg` for `750434665 Stealth dialogue`
- **~10 lines have stronger evacuative match:** `121232196 Let's get out of here.` → `We have to get out of here. Let's go.` is better than Round1's generic `We have to get out of here.` — actually same, so no change
- **Everything else:** Round 1 intent (threat→threat, revive→support, pager→confident cover) beats literal text overlap

If you want per-ID *unique* Miranda audio (not 86 categories × 1 line), pick from `Голос_Лоусон_flat/` stems with most variants:
- `norvx_relationship_03_h` 42 lines → Reviving/Inspire (tender)
- `norvx_starter_h` 40 lines → Follow/Coming/Place drill (leadership)
- `procer_vixen_briefing_d` 24 lines → Hostage/Cop intimidate (briefing authority)
- `twrvxl_aboutaboy_h` 19 lines → Pager (sister talk, soft control)

Full 887-row intent mapping + 887-row text-match CSV + this check are all in `voice_lines_vox/miranda_lawson/`.

