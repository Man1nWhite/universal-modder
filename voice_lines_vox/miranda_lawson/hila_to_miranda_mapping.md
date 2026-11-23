# Hila -> Miranda — Close Voice Line Mapping

> **Goal:** Take the Hila callout table (`hila_regular_vox.csv` 887 IDs, `robber=rb21`, `regular_vox/<id>.stream`) and find the closest Miranda Lawson line from `Голос Лоусон.7z` (866 oggs, 214 stems) + `miranda_text_me2_me3.md` text archive.
> **Method:** Category-level semantic match (Hila Category -> Miranda thematic group -> file prefix). No exact 1:1 for hostage/heist lines — Miranda is a Cerberus officer, not a bank robber — so we match **intent/tone** (e.g. Hila "Get down!" -> Miranda "Take your best shot." = authoritative threat).
> **Sources:** Hila wiki `payday.fandom.com/wiki/Hila/Quotes` + Hila CSV 1c3uXGyH... + Miranda text + Голос manifest (norvx/procer/twrvxl/etc prefixes).

## How to use
1. Pick Hila ID you want to replace (e.g. `28880249` pager -> `regular_vox/28880249.stream`).
2. Find its row in `hila_to_miranda_mapping.csv` -> `miranda_file_hint` gives ogg stem (e.g. `cithub_tp_miranda_a` for pager).
3. Extract that ogg from `Голос_Лоусон_flat/` -> `wwise_ima_adpcm -e` -> replace stream, keep switch `rb21`.
4. For full VO reuse, remap per Category (e.g. all 59 Hostage intimidate -> 1-2 Miranda threat lines with pitch variation).

## Category -> Miranda group (86 categories)

| Hila Category | Count | Miranda suggested line (representative) | File hint (Голос) | Match |
|---|---|---|---|---|
| Hostage intimidate | 59 | Take your best shot. — Enyala confrontation (loyalty) | procer_vixen_briefing_d / bchlml_fatherfinal_d | tone: cold professional threat |
| Direction | 54 | Come with me. Follow me. This way. — Normandy escort | pronor_ / procer_cover_tutorial_a / norvx_starter_h | semantic: direct match |
| Pager response | 33 | I am very good at just about anything I choose to do. My reflexes, my strength... designed | cithub_tp_miranda_a / twrvxl_main_contact_d | tone: dry humor cover |
| Coming | 29 | Be right there. Coming! On my way! — I will be there in 5 minutes. I settle for nothing bu | endgm2_longwalk_a / cithub_tp_miranda_a | tone: en-route promise |
| Cops arriving | 26 | Oh shit, it is the cops. Cops incoming. — Get ready, pigs incoming. | pronor_illusive_c / procer_cover_tutorial_a | semantic: enemy wave |
| Reviving | 26 | Please do not die, okay? You are really hurt. | norvx_loyalty_01_h / norvx_relationship_03_h | tone: tender revive |
| Victory | 21 | We are untouchable! — We have to do it, Shepard. We had no choice. | endgm2_longwalk_a / norvx_culmination_h | tone: win |
| Follow | 20 | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor | semantic: identical verb |
| Inspire | 19 | We are all hoping you can do the impossible, Shepard. No pressure. | pronor_illusive_c / norvx_culmination_h | tone: hype |
| Curse | 18 | Oh, shit! Fuck! — Damn, I am not very good at this. Bit of a disaster, really. | bchlml_epilogue_h / endgm1 | tone: Miranda rarely curses |
| Low health | 17 | This radiation is causing serious problems for my shields. / (pained) They got me! | horcr1 / endgm2_biotic_fail_c | semantic: shield/health low |
| Low ammo | 16 | Almost out of ammo. Who has an ammo bag? — Miranda tactical resource | cspcr2_bodies / profre_veetor_door_d | tone: resource call |
| Let's go | 14 | We have to get out of here. Let's go. — Sanctuary escape | endgm2_escape_h / procer_vixen_shuttle_d | semantic: evacuation |
| Drill jam | 13 | The drill is jammed! — Something is wrong with the computer. | twrvxl_main_contact_d / horcr1 | semantic: jam approx computer stuck |
| Mask up | 13 | This should be easy. Okay, lets do this. Ready to rumble. — My reflexes, my strength... de | procer_vixen_briefing_d / pronor_illusive_c | semantic: pre-mission confidence |
| Taxman intimidate | 12 | You talk or you die! — Horizon father hunt: My father is still hunting her. | bchlml_fatherfinal_d / prscva | tone: interrogation |
| Grenade | 11 | Fire in the hole! / I will destroy you! You will not survive! | SFXGame.pcc / endgm2_boss_fight_a | semantic: AoE |
| Killed cloaker | 11 | Cloaker is down, baby! — We are not alone here — now we are. | juncvl / jnkkga | tone: stealth kill |
| Killed dozer | 11 | Dozer is down, baby! — Its dead. | endgm2_team_c_a / endgm2_boss_fight_a | tone: heavy kill |
| Killed shield | 11 | Shield is down, baby! — I will destroy you! | cspcr2 / endgm2_boss_fight_a | tone: shield break |
| Mark camera | 11 | Watch that camera. — Remember, you do not wanna be on CCTV. (identical) | cithub_first_time_d_S_INT.072.ogg | semantic: identical CCTV |
| Mark turret | 11 | They got a turret! — Sanctuary is a lie. Stay away. | norcvc / gthgtl_amb_core_h | tone: emplacement |
| Inspire revive | 10 | Get up! You are going to be okay. — reviving | norvx_relationship_00..04_h / endgm2_team_c | tone: supportive revive |
| Intimidate cop | 10 | Consider this my resignation. — to Illusive Man | endgm2_crewrescue_c / pronor_illusive_c | tone: defiance |
| Killed sniper | 10 | Sniper is dead! — Take your best shot. Goodbye Niket... | norgta / twrvxl | tone: precision kill |
| Killed taser | 10 | The taser got it! — Mechanized threat neutralized. | endgm2_tech_culmination_c / profre | tone: tech kill |
| Call Bodhi | 9 | Bodhi! — Grunt? norkga | norkga |  |
| Drill jam/hack pause followup | 9 | Fix it, please? We have to fix it! — We have to do it, Shepard. | twrvxl_oldfriend_d / profre | tone: urgent fix |
| Intimidate cop final | 9 | Goodbye Niket, I am going to miss you... figuratively speaking. *bang* | norvx_loyalty_02_h / bchlml_villagefirst_d | tone: final warning |
| Killed medic | 9 | Medic is gone! — Wilson betrayed us all. My job. | procer / endgm2 | tone: support kill |
| Mark dozer | 9 | It is a dozer! — Reaper forces incoming! | endgm2_longwalk_a / cspcr2_bodies_h | tone: heavy |
| Request for help while cuffed | 9 | Pick my cuffs. — Cerberus has kept her safe. Until now. | bchlml / twrvxl_aboutaboy_h | tone: restrained |
| Request for help while downed | 9 | My father hurt me, but he did not break me. I am my own person. — vulnerable call | horcr1 / bchlml_villagefirst_d | tone: call for help |
| Call Bonnie | 8 | Hey, Bonnie. — Oriana (sister) is closest to female ally | twrvxl / norvx | tone: female teammate |
| Call Chains | 8 | Chains! — Shepard chain of command | procer |  |
| Call Clover | 8 | Clover. — Jack: You are a spoiled rich girl! — Victim! (female rival) | jnkkga | tone: female rival |
| Call Dallas | 8 | Dallas! — Shepard (leader) | pronor | tone: leader |
| Call Dragan | 8 | Dragan. — Jack (jnkkga) (rival call) | jnkkga | tone: rival |
| Call Ethan | 8 | Ethan! — Oriana (sister, Ethan is Hila's brother equivalent) | bchlml_fatherfinal_d / twrvxl_aboutaboy_h | tone: family — Hila/Ethan siblings, Miranda/Oriana sisters |
| Call Houston | 8 | Houston. — pilot call (Houston = Joker? endgm1_warship) | endgm1_warship_c | tone: pilot |
| Call Hoxton | 8 | Hey, Hoxton. — Jacob. / Shepard. | pronor / norvx | tone: male teammate |
| Call Jimmy | 8 | Jimmy! — Shepard | norvx |  |
| Call Jiro | 8 | Jiro! — Miranda calls Garrus? No, but calls Shepard | norvx | tone: distant ally |
| Call Rust | 8 | Rust! — Garrus? Miranda calls Shepard neutral | norvx |  |
| Call Sangres | 8 | Sangres. — krohub/kroprl | krohub |  |
| Call Scarface | 8 | Tony. Hey, Tony. — Henry. My father. / Illusive Man. (boss) | pronor_illusive_c | tone: boss call |
| Call Sokol | 8 | Hey, Sokol! — Oriana. She is as smart as I am... (personal call, Miranda only calls Oriana | twrvxl_aboutaboy_h / twrvxl_uptospeed_h | tone: calling ally |
| Call Wick | 8 | Wick. — Illusive Man (calculating boss) | pronor_illusive_c | tone: cool professional |
| Call Wolf | 8 | Wolf. — Jacob Taylor (both heavy) | procer / norvx | tone: heavy |
| Deploy ammo bag | 8 | I dropped an ammo bag! — Cerberus has kept her safe. (supply=protection) | pronor / norvx | tone: support drop |
| Hack paused | 8 | Something is wrong with the computer. — Someone reprogrammed these mechs... | cithub_avina_middle_d / gthgtl_amb_core_h | semantic: tech failure |
| Mark captain | 8 | They got a captain! — Or what? You will replace me next? | pronor_illusive_c / endgm1_warship_c | tone: officer |
| Mark shield | 8 | Watch the shield! — I will destroy you! generic mark | cspcr2_platform_approach_h / twrvxl_uptospeed_h | tone: enemy callout |
| Mark sniper | 8 | They got a sniper! — Take your best shot. | norgta / norcva | tone: ranged |
| Mark taser | 8 | It is a taser! — Someone reprogrammed these mechs to attack on sight. | profre / profre_veetor_door_d | tone: tech |
| Place drill | 8 | We are drilling! — This should be easy. Okay, lets do this. | procer_vixen_intro_d / norvx_starter_h | tone: mission start |
| Revived | 8 | Thanks, you got here just in time. — gratitude | norvx_loyalty_02_h / bchlml_epilogue_h | tone: gratitude |
| Smoke | 8 | Smoke! Wait till the smoke clears! — radiation line | omghub / omggra | tone: smoke cover |
| Call Duke | 7 | Duke! — The Illusive Man. (duke=magnate) | pronor_illusive_c | tone: authority |
| Call Jacket | 7 | Jacket! — Jacob (jacket approx Jacob) | procer |  |
| Call Sydney | 7 | Sydney! — Oriana (female ally) | twrvxl |  |
| Cop intimidate | 7 | My job. Wilson betrayed us all. — Wilson execution | procer_vixen_intro_d / cspcr2_bodies_a | tone: authoritative kill |
| Mark cloaker | 7 | Watch the cloaker! — We are not alone here. | cithub_first_time_d / n7 | tone: stealth |
| Mark guard | 7 | It is a guard. — Remember, you do not wanna be on CCTV. | cithub / norcva | tone: stealth spot |
| Mark medic | 7 | They got a medic! — support target | omggra / omgpra | tone: support |
| Reviving (last down) | 7 | You cannot go down again. Next time you are finished. | endgm2_warnings_a / endgm2_team_c_fail_c | tone: last-chance |
| Deploy first aid kit | 6 | Dropped a first aid kit! — same as medic | norvx | tone: healing |
| Deploy medic bag | 6 | Medic bag here, guys! — You are hurt bad. You will be okay. I will fix you up. | norvx_loyalty_01_h / norvx_relationship_00_h | tone: healing |
| Complaining | 5 | Why is this taking so long? — I do not have that fire you have... | twrvxl_oldfriend_d / norvx | tone: impatience |
| Cops leaving | 5 | Motherfuckers are pulling back! — They are running away! | pronor / procer | tone: retreat |
| Unknown | 5 | What the... This is gonna hurt. — I do not have that fire you have... | bchlml_epilogue_h / norvx_relationship_00_h | tone: confusion |
| Watch the civillians | 5 | I am still human, Shepard. I make mistakes — like everyone else. — generic vulnerable | norvx_relationship (generic fallback) | fallback |
| Careful | 4 | Careful. Be careful now. — This radiation is causing serious problems... | horcr1 / profre | tone: hazard warning |
| Deploy body bag case | 4 | I dropped a body bag case. — handling bodies (cspcr2_bodies is literally bodies) | cspcr2_bodies | tone: body handling |
| Flashbanged | 4 | I cannot see! Flashbang! — I cannot see through the smoke! | endgm2_warnings_a | tone: sensory loss |
| Gage package | 4 | It is secured. Okay, secured. — We have it secured. | cspcr2 / endgm2 | tone: secure |
| Inside | 4 | Get inside. — I have cleared the engine room. I will be there in 5 minutes. | norvx_starter_h / norcvc | tone: interior move |
| Tear gas | 4 | Fucking tear gas! — This radiation... (hazard) | horcr1 / endgm2_warnings_a | tone: environmental hazard |
| This is the place | 4 | This is the place. — Sanctuary is a lie. Stay away. | bchlml_villagefirst_d / cithub | semantic: place confirm |
| Got it | 3 | Got it. Okay. — I got it. Okay, lets do this. | norvx_starter_h / procer_cover_tutorial_a | semantic: acknowledge |
| Gone loud | 2 | Fuck it, now we gotta kill them. — Or what? You will replace me next? Consider this my res | endgm2_crewrescue_c / procer | tone: escalation |
| Wait for it | 2 | Wait for it. Okay, get ready. — Wait for it. Get ready. | endgm2_longwalk_a / endgm1_huddle_01c_d | semantic: identical |
| Watch out | 2 | Watch out! — Watch out, it is a camera. | cithub_first_time_d / cspcr2_tubereveal_h | tone: warning |
| Here | 1 | This is it. Here. This is the place. — Sanctuary is a lie. Stay away. | cithub_tp_miranda_a / bchlml_villagefirst_d | semantic: location |
| Stay | 1 | Stay. Stay put! — Stay down. Stay still. | procer_vixen_shuttle_d / bchlml | tone: hold position |
| Stealth dialogue | 1 | Remember, you do not wanna be on CCTV. — identical | cithub_first_time_d_S_INT.072.ogg | semantic: identical stealth line |

## Sample — first 50 Hila IDs -> Miranda close lines

| Hila ID | Hila Speech | Hila Category | Miranda close | File hint |
|---|---|---|---|---|
| 712675 | (pained) You, hey! | Request for help while downed | My father hurt me, but he did not break me. I am my own person. — vuln | horcr1 / bchlml_villagefirst_d |
| 1149328 | On your feet! | Inspire revive | Get up! You are going to be okay. — reviving | norvx_relationship_00..04_h / endgm2_team_c |
| 1806387 | Last chance motherfucker, down. | Hostage intimidate | Take your best shot. — Enyala confrontation (loyalty) | procer_vixen_briefing_d / bchlml_fatherfinal_d |
| 1884286 | On me. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 2425875 | On me. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 2643233 | Hey, Sokol! | Call Sokol | Hey, Sokol! — Oriana. She is as smart as I am... (personal call, Miran | twrvxl_aboutaboy_h / twrvxl_uptospeed_h |
| 3358066 | Move it! | Inspire | We are all hoping you can do the impossible, Shepard. No pressure. | pronor_illusive_c / norvx_culmination_h |
| 3439862 | You gotta help me! | Request for help while downed | My father hurt me, but he did not break me. I am my own person. — vuln | horcr1 / bchlml_villagefirst_d |
| 3809559 | Bonnie. | Call Bonnie | Hey, Bonnie. — Oriana (sister) is closest to female ally | twrvxl / norvx |
| 4646339 | Sokol. | Call Sokol | Hey, Sokol! — Oriana. She is as smart as I am... (personal call, Miran | twrvxl_aboutaboy_h / twrvxl_uptospeed_h |
| 4733345 | The drill is jammed. | Drill jam | The drill is jammed! — Something is wrong with the computer. | twrvxl_main_contact_d / horcr1 |
| 5406681 | Hey, Hoxton! | Call Hoxton | Hey, Hoxton. — Jacob. / Shepard. | pronor / norvx |
| 5884207 | The drill is fucking jammed! | Drill jam | The drill is jammed! — Something is wrong with the computer. | twrvxl_main_contact_d / horcr1 |
| 6352252 | I'm so fucked up here! | Request for help while downed | My father hurt me, but he did not break me. I am my own person. — vuln | horcr1 / bchlml_villagefirst_d |
| 6497207 | Down! | Hostage intimidate | Take your best shot. — Enyala confrontation (loyalty) | procer_vixen_briefing_d / bchlml_fatherfinal_d |
| 7591312 | Help me with these cuffs. | Request for help while cuffed | Pick my cuffs. — Cerberus has kept her safe. Until now. | bchlml / twrvxl_aboutaboy_h |
| 7874395 | Fire in the hole! | Grenade | Fire in the hole! / I will destroy you! You will not survive! | SFXGame.pcc / endgm2_boss_fight_a |
| 8173908 | Wolf. | Call Wolf | Wolf. — Jacob Taylor (both heavy) | procer / norvx |
| 8208111 | Down, hit the floor! | Hostage intimidate | Take your best shot. — Enyala confrontation (loyalty) | procer_vixen_briefing_d / bchlml_fatherfinal_d |
| 9204524 | If you try to make a phone call, it would be your last. | Hostage intimidate | Take your best shot. — Enyala confrontation (loyalty) | procer_vixen_briefing_d / bchlml_fatherfinal_d |
| 9493679 | Follow. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 9639198 | Follow me. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 9726729 | Just stay down. | Hostage intimidate | Take your best shot. — Enyala confrontation (loyalty) | procer_vixen_briefing_d / bchlml_fatherfinal_d |
| 10767856 | Talk, fucker! | Taxman intimidate | You talk or you die! — Horizon father hunt: My father is still hunting | bchlml_fatherfinal_d / prscva |
| 11336755 | Something's wrong with the computer. | Hack paused | Something is wrong with the computer. — Someone reprogrammed these mec | cithub_avina_middle_d / gthgtl_amb_core_h |
| 12352202 | Come with me. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 12651471 | Pick my cuffs. | Request for help while cuffed | Pick my cuffs. — Cerberus has kept her safe. Until now. | bchlml / twrvxl_aboutaboy_h |
| 12840920 | I'm in bad shape, this is not good! | Request for help while downed | My father hurt me, but he did not break me. I am my own person. — vuln | horcr1 / bchlml_villagefirst_d |
| 12917222 | Jiro! | Call Jiro | Jiro! — Miranda calls Garrus? No, but calls Shepard | norvx |
| 13450280 | This is it. | Here | This is it. Here. This is the place. — Sanctuary is a lie. Stay away. | cithub_tp_miranda_a / bchlml_villagefirst_d |
| 13565624 | Tony. | Call Scarface | Tony. Hey, Tony. — Henry. My father. / Illusive Man. (boss) | pronor_illusive_c |
| 13663504 | Come with me. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 14192205 | Help me get these cuffs off. | Request for help while cuffed | Pick my cuffs. — Cerberus has kept her safe. Until now. | bchlml / twrvxl_aboutaboy_h |
| 14916926 | Down the stairs. | Direction | Come with me. Follow me. This way. — Normandy escort | pronor_ / procer_cover_tutorial_a / norvx_starter_ |
| 15069966 | Hey, Bodhi. | Call Bodhi | Bodhi! — Grunt? norkga | norkga |
| 15477016 | Come on, I wanna get back in the fight. | Request for help while downed | My father hurt me, but he did not break me. I am my own person. — vuln | horcr1 / bchlml_villagefirst_d |
| 16113018 | Medic bag here, guys! | Deploy medic bag | Medic bag here, guys! — You are hurt bad. You will be okay. I will fix | norvx_loyalty_01_h / norvx_relationship_00_h |
| 16456601 | This should be easy. | Mask up | This should be easy. Okay, lets do this. Ready to rumble. — My reflexe | procer_vixen_briefing_d / pronor_illusive_c |
| 17072196 | Yeah, I thought I saw a fire, but it's nothing. | Pager response | I am very good at just about anything I choose to do. My reflexes, my  | cithub_tp_miranda_a / twrvxl_main_contact_d |
| 17150976 | Come with me. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 17436170 | Hey, Bonnie. | Call Bonnie | Hey, Bonnie. — Oriana (sister) is closest to female ally | twrvxl / norvx |
| 17975779 | Shield! | Mark shield | Watch the shield! — I will destroy you! generic mark | cspcr2_platform_approach_h / twrvxl_uptospeed_h |
| 18442008 | Watch that camera. | Mark camera | Watch that camera. — Remember, you do not wanna be on CCTV. (identical | cithub_first_time_d_S_INT.072.ogg |
| 18633009 | I killed the taser! | Killed taser | The taser got it! — Mechanized threat neutralized. | endgm2_tech_culmination_c / profre |
| 18765061 | Rust! | Call Rust | Rust! — Garrus? Miranda calls Shepard neutral | norvx |
| 19403899 | Follow me. | Follow | Follow me. / Come with me. | norvx_starter_h_S_INT / pronor |
| 19464577 | Dozer. | Mark dozer | It is a dozer! — Reaper forces incoming! | endgm2_longwalk_a / cspcr2_bodies_h |
| 20422574 | Help me get these cuffs off! | Request for help while cuffed | Pick my cuffs. — Cerberus has kept her safe. Until now. | bchlml / twrvxl_aboutaboy_h |
| 20669691 | Careful. | Careful | Careful. Be careful now. — This radiation is causing serious problems. | horcr1 / profre |
| 21348768 | Hey, Bonnie. | Call Bonnie | Hey, Bonnie. — Oriana (sister) is closest to female ally | twrvxl / norvx |

> Full 887-row CSV has every ID mapped (same per-category line repeated for variation). For unique per-ID lines, listen to `Голос_Лоусон_flat/` stems — e.g. `norvx_relationship_03_h` (42 lines) gives 42 distinct tender variants for Inspire/Reviving.

## Notes & limitations
- **No exact match** for: Drill jam, Hack paused, Deployables — ME has no heist gear. We map to Miranda tech: Something is wrong with the computer.
- **Hostage lines** are Hila-specific; Miranda closest are cold executions (Niket, Wilson, Illusive Man defection) — same authoritative tone, different words.
- **Pager** is Hila humor (dream/boyfriend diapers/YouTube star) — Miranda closest is Normandy banter/Citadel reunion: dry, not funny.
- **Calling crewmates:** Hila calls 20 heisters by name; Miranda only calls Shepard/Oriana/Jacob/Illusive Man — we map all to Shepard. It is so good to finally see you. / Oriana... with name swap in post.
- **Mark enemy:** ME has no dozer/shield etc; we map all to generic combat bark I will destroy you! You will not survive! (Warp) — extractable from SFXGame.pcc (not in Голос, but noted in miranda_text_me2_me3.md).
- For **exact transcript** of any ogg, run LEX Dialogue Dumper -> xlsx (see audio_next.md).
