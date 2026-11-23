# Heister Voice IDs — General Callouts Table
> Source: https://docs.google.com/spreadsheets/d/1m0LBg2PKpB-bnWfOFj40AglCI1dLmAHLH3ydi3Y7uz8 (gid=0 + gviz html, 2 chunks)
> For use as Pocorose replacements or manual `managers.player:local_player():sound():say("xxxx",true,true)` keybinds.
> Original note: "Apologies in advance for the poor formatting"

## Legend for character variable in f-lines
From sheet header row:
- `{a,b,c,d} = Dallas, Chains, Wolf, Hoxton`
- `{l,m,n,o} = Houston, Wick, Clover, Dragan`
- `{p,q,r,s} = Jacket, Bonnie, Sokol, Gyro/Jiro`
- `{t} = Bodhi`
- Characters who call themselves are usually blank
- `x` placeholder in g30x_any etc = character index; replace `x` with desired character id letter above
- `_any` suffix = all difficulties, `_sin` = single, `_plu` = plural, etc.

---

## General Callouts ("g" — work on all heists)

| ID | Line |
|---|---|
| g01 | Downstairs |
| g02 | Upstairs |
| g03 | Left |
| g04 | Right |
| g05 | Go Up |
| g06 | Go Down |
| g07 | We gotta get out |
| g08 | Get Inside |
| g09 | Hurry |
| g10 | Careful |
| g11 | Wrong Way |
| g12 | Right Way |
| g13 | Let's Go |
| g14 | This is the place |
| g15 | There! (Look) |
| g16 | Keep Defending |
| g17 | Time to Go |
| g18 | Move (Inspire Go Faster) |
| g19 | Go Straight |
| g20 | Jump Down |
| g21 | Drill Mounted |
| g22 | POS Drill (Post drill repair) |
| g23 | Shoot em! |
| g24 | Mission Success Lines |
| g25 | Take out Cameras |
| g26 | Use Cable Ties |
| g27 | Watch the Civilians |
| g28 | Almost there! (Escape) |
| g29 | FUCK! |
| g30 | BullDozer Killed |
| g30x_any | BullDozer Killed (Delayed) |
| g31x_any | Shield Killed (Delayed) |
| g32x_any | Tazer Killed (Delayed) |
| g33x_any | Cloaker Killed (Delayed) |
| g35x_any | Sniper Killed |
| g36x_any | Medic Killed |
| g40x_any | SMOKE! (Third Person) |
| g41x_any | FLASHBANG! |
| g42x_any | TEARGAS! |
| g43 | Grenade! (Throwing) |
| g50 | Get ready for action (Third Person) |
| g60 | SHIT! |
| g61 | I got the Drill |
| g62 | Thirty Seconds |
| g63 | One Minute |
| g64 | One Thirty |
| g65 | Two Minutes |
| g66 | Two Thirty |
| g67 | Any Second Now |
| g68 | Overrun with Cops |
| g69 | We're Easy Targets (Can't Stay) |
| g70 | Cops just got here (Third Person) |
| g72 | I'm on it! (Wolf Only) |
| g80x_plu | Need Medic Bag! |
| g81x_plu | Need Ammo Bag! |
| g90 | Taunt (Only when Heist has gone Loud, otherwise blank) |
| g92 | Found it (Gage Package) |

## P Callouts ("p" — do not work on every heist, heist-specific)

| ID | Line |
|---|---|
| p01 | Alright, Let's do this. |
| p02 | Let's do this. |
| p03 | Time to go to work. |
| p04 | Hurry up and Freakin' Wait |
| p05 | Cops just got here |
| p06 | Ok |
| p07 | We gotta go through with the hostage trade |
| p08 | Computer is Jammed (d03_plu is better) |
| p09 | Computer Jammed Again (d04_plu is better) |
| p10 | Piece of Shit hardware (Jammed Drill, Chains/Hoxton) |
| p12 | Go go |
| p13 | Get a move on! |
| p14 | MOVE IT! |
| p15 | Get Moving! |
| p16 | MOVE |
| p17 | Almost, Any second now! |
| p18 | What're you waiting for!? (Wolf Only) |
| p19 | I'm coming for ya (as in Revive) |
| p20 | Come with me |
| p21 | Plan B Time |
| p22 | Police Assault Incoming |
| p23 | Get ready for action |
| p24 | Alright, back to work (Police assault over) |
| p25 | Flashbang! (g41x_any is better) |
| p26 | Cover their flanks |
| p27 | Loot Bag Secured |
| p28 | That's all the loot bags |
| p29 | Picking the lock! |
| p30 | Using a keycard! |
| p31 | Cops are stealing our loot |
| p32 | You go case the place, I'll wait here as backup |
| p33 | They're coming in through the Skylights |
| p34 | They're on the roof |
| p35 | They're coming down the sides (or walls) |
| p36 | They're coming through the wall panel |
| p37 | They're coming from the floors |
| p38 | They're coming from outside |
| p39 | They're Climbing down on the outside |
| p40 | They're Climbing up on the outside |
| p41 | Swat Helicopter inbound |
| p42 | Swat insertion |
| p43 | Snipers! (Responding to spawn) |
| p44 | They're coming from the woods |
| p45 | Anybody, HEEEELP! (Help I'm dying) |
| p46 | Jump! |
| p47 | "Let's get the Party Started!" (Excited about going Loud) |

## V Callouts ("v" — work on most heists, mission progress)

| ID | Line |
|---|---|
| v01 | Okay, On it! |
| v03 | We're in, We're Through |
| v04 | Found it, It's here |
| v05 | Found one, Got one |
| v06 | Found another one, Found one more |
| v07 | It's Done, It's finished |
| v08 | DONE, We're done |
| v09 | C'mon onto the next objective |
| v10 | Found a Keycard (See) |
| v11 | I got the Keycard (Pickup) |
| v12 | BEEP BEEP MOTHERFUCKER (use Keycard) |
| v13 | Back up, Clear the blast zone (Plant mission C4) |
| v14 | Knock Knock, We make our own doors (Blow mission C4) |
| v15 | Get this Motherfucking door open |
| v16 | Let's open this door |
| v17 | Lets go team |
| v18 | Wipe em out, Clear the room |
| v19 | Here it comes |
| v20 | It's here, It has Arrived |
| v21 | Its P A Y D A Y |
| v22 | We got all of it |
| v23 | The Drill is done |
| v24 | The Computer is done |
| v25 | It's done lets move on |
| v26 | There's our ride, There's our escape |
| v27 | There are cops in the vents |
| v28 | Spotted the mark |
| v29 | There she is |
| v30 | There he is |
| v31 | There they are |
| v32 | There it is |
| v33 | Where's the manager!? |
| v34 | LISTEN UP THIS IS A ROBBERY (Heat Speech) |
| v35 | Bain!? |
| v36 | Fuck! Now what? |
| v37 | Stay sharp, I got a bad feeling about this |
| v38 | Search the place |
| v39 | Find the mark, Find the target |
| v40 | C'mon find her |
| v41 | C'mon find him |
| v42 | C'mon find them |
| v43 | C'mon find it |
| v44 | Keep looking |
| v45 | Oh no a turret, Aw shit they brought a turret |
| v46 | YES (Excited) |
| v47 | Is that enough? |
| v48 | Nah get all of it |
| v49 | Shoot it down, Fire at it |
| v50 | Murkies! |
| v51 | Let's get this loot moving |
| v52 | Shit it's stuck |
| v53 | This place smells bad |
| v54 | God DAMN that was loud |
| v55 | Skydive Hype |
| v56 | Hey (Counterfeit Greeting) |
| v57 | Found Crowbar |
| v58 | SIT (Telling Taxman to get in the chair) |

## Teammate / Marking / Hostage / Drills

| ID | Line |
|---|---|
| f11a_sin | Dallas Help me up! |
| f11e_plu | Guys I need Help! |
| f13a_sin | Dallas come uncuff me! |
| f21a_sin | Dallas Follow me! |
| f30x_any | Spot BullDozer |
| f30y_any | Oh Shit BullDozer! |
| f31x_any | Spot Shield |
| f31y_any | Oh Shit Shield! |
| f32x_any | Spot Taser |
| f32y_any | Oh Shit Taser! |
| f33x_any | Spot Cloaker |
| f33y_any | Oh Shit Cloaker! |
| f34x_any | Spot Sniper |
| f34y_any | Oh Shit Sniper! |
| f36x_any | Inspire Revive |
| f37_any | Mark Guard Line |
| f38_any | Follow me (Generic) |
| f39_any | Mark Camera Line |
| f40_any | (To Hostage) Get Moving! |
| f41_any | Wake up sleepyhead (Sokol only) |
| f42_any | Look Out! (Generic) |
| f43_any | Wake up (Sokol only) |
| f44x_any | There's a Swat Turret! |
| f45x_any | Watch out! (Generic) |
| f46x_any | Taxman Interrogation lines |
| f47x_any | There's a Medic! |
| f48x_any | Stop, Halt, Wait |
| f02x_plu | Get Down! (Everybody) |
| f02x_sin | Get Down! (To Hostage) |
| f02b_sin | I told *you* to get down! |
| f03a_plu | Stay Down! (Everybody) |
| f03a_sin | Stay Down! (You) |
| f03b_any | And don't move! (To Hostage) |
| s01x_plu | I Placed Ammo Bag |
| s02x_plu | I placed Doctor Bag |
| s05x_sin | Thanks (Helped up) |
| s07x_sin | Tazed (Wolf/Chains/Houston) |
| s08x_sin | Hang on, I'm reviving you |
| s12 | Placed First Aid Kit |
| s13 | Bodybag Case Placed |
| s14 | Bodybag Secured (Hoxton Only?) |
| s32x_sin | That was my Last Cable Tie |
| d01x_sin | Hear a Drill Jammed |
| d02x_sin | Drill Jammed again |
| d03_plu | Hear a Jammed Computer |
| d03_sin | Hear a Jammed Thermal Lance |
| d04_plu | Computer Jammed Again |
| d04_sin | Thermal Lance Jammed Again |
| d05 | Generic Shit's broke |
| a01x_any | (Putting mask on) Let's do this |
| i01x_any | (Assault only) Anticipation |
| r01x_sin | (Delayed) Affirmative (Bot Follow me Response) |
| r02a_sin | (Delayed) I'm on my way! (Bot Rescue response) |
| t01x_sin | Few Minutes Left |
| t02x_sin | Halfway there |
| t03x_sin | Any Second Now! |
| l01x_sin | Hands up! (Intimidate, "L"01x) |
| l02x_sin | On your knees! (Intimidate "L"02x) |
| l03x_sin | Cuffs, Now. (Intimidate "L"03x) |
| whistling_attention | Whistle Command |
| dsp_radio_checking_1 | Player Pager Answering Lines |
| dsp_stop_all | Stop Radio Static |

## Special Units kills (second tab, gid=674215167)

| Unit | IDs |
|---|---|
| Bulldozer | bdz_c01, bdz_entrance, bdz_entrance_elite, bdz_g90, bdz_post_kill_taunt, bdz_visor_lost, bdz_x01a_any_3p (hurt), bdz_x02a_any_3p (death) |
| Taser | tsr_c01, tsr_entrance, tsr_elite, tsr_g90, tsr_post_tasing_taunt, tsr_tasered, tsr_x01a_any_3p, tsr_x02a_any_3p, tsr_burnhurt, tsr_burndeath |
| Shield | shield_identification |
| Cloaker | clk_c01x_plu, cloaker_spawn (whistle), cloaker_detect_mono (WOOPWOOP), cloaker_detect_christmas_mono (JINGLE), cloaker_presence_loop, clk_* sounds (baton, crawl, jump, kick, punch) |
| Captain Winters | cpa_a02_01, cpw_a01, cpw_a02, cpw_a04, cpw_a05 |
| Medic | mdc_entrance, mdc_g90, mdc_heal, mdc_burnhurt, mdc_burndeath, mdc_x01a_any_3p, mdc_x02a_any_3p |
| Turret | swatturret_alert, cooldown, destroy, fire, disarmed_loop, mount, pressure_release, reload, spin_loop, weakspot_hit etc |

> Full raw gviz HTML saved; this markdown is reformatted for readability. For complete numeric <-> event mapping see robbers_mission_gen sheet.
