# Daggerfall data and RPG systems survey

Research only. No engine, mod, converter, launcher, todo, or backlog files were changed.

**Evidence labels:** [data] counted from game files or quest scripts. [code] read in the source, not run. [judgment] my classification. **No quest was launched in this run**, so every "works" or "breaks" below is a code reading until the pilot quest is played.

## 1. Proposed task list

Ordered by dependency and value. `DESIGN` means it needs an owner decision. Coverage counts are explained in section 3.

**Quest path: first playable kill quest (pilot: `M0C00Y11`, Fighters Guild)**

- [ ] **Q1 · MVP** Show windows Daggerfall opens by itself (quest popups, rewards) in Doom and let the player dismiss them. Depends on: built UI bridge.
- [ ] **Q2 · MVP** Show interior NPCs in Doom as Daggerfall sprites with stable IDs. Depends on: building transitions (todo).
- [ ] **Q3 · MVP** Interact with an NPC runs Daggerfall's real click path (quest offer, guild menu, talk, shop). Depends on: Q1, Q2.
- [ ] **Q4 · MVP** Export quest spawn and item markers from interiors and dungeons to Doom. Depends on: building transitions.
- [ ] **Q5 · MVP** Spawn `place foe` targets at their markers, one Doom actor per foe for the pilot. Depends on: Q4. Final pack mapping is `DESIGN` (D1).
- [ ] **Q6 · MVP** Report quest foe injury and death from Doom to Daggerfall's `Foe` state. Depends on: Q5.
- [ ] **Q7 · MVP** Keep quest actors and their dead state correct across save, load, and re-entry. Depends on: Q5, Q6.
- [ ] **Q8 · MVP** Play `M0C00Y11` from offer to reward, including one save and reload. Depends on: Q1 to Q7.

**Quest path: broad coverage**

- [ ] **Q9 · Release** Apply quest NPC changes in Doom: placed, hidden, restored, destroyed, muted (77 quests use `place npc`, 53 use `hide npc`). Depends on: Q3, Q4.
- [ ] **Q10 · Release** Verify `pc at` and enter/exit conditions after transitions land (77 quests). Depends on: building transitions.
- [ ] **Q11 · Release** Quest items in the world, picked up with Interact. Depends on: Q4, "Daggerfall items in the world". Reaches 83 of 187.
- [ ] **Q12 · Release** Using quest items from the inventory fires their quest triggers. Depends on: inventory menu. Reaches 97.
- [ ] **Q13 · Release** Route `create foe` ambushes to Doom spawns near the player. Depends on: Q5, Q6. Pack size is `DESIGN` (D1). **Largest single gain: reaches 170.**
- [ ] **Q14 · Release** Quest spells, disease, cures, teleports, and sounds. Depends on: S2, S3. Reaches 187.
- [ ] **Q15 · Release** Main quest pass over all 34 `S*` scripts. Depends on: Q9 to Q14, existing "Support main quest dungeon quest steps".

**RPG systems with no backlog item**

- [ ] **S1 · MVP** Apply Daggerfall armor and resistances to Doom hits. HP currently applies damage unchanged. Depends on: nothing new.
- [ ] **S2 · Release** Player status effects reach Doom (paralysis, slow, vision, disease, poison). `DESIGN` for how each feels.
- [ ] **S3 · Release** Spellcasting bridge: cast, projectile, reported hits, magicka. Depends on: hotkeys.
- [ ] **S4 · Release** Crime, guards, surrender, court, and jail. Depends on: Q3, NPC combat. `DESIGN` (D2).
- [ ] **S5 · Release** Hostile NPCs become Doom bots. Depends on: Q2. `DESIGN` (D2).
- [ ] **S6 · Release** Resting from Doom, blocked by nearby monsters and interrupted by ambushes. Depends on: Q1.
- [ ] **S7 · Release** Skill XP from Doom actions. `DESIGN` for how guns map to Daggerfall skills.
- [ ] **S8 · Release** Stealth and detection use Daggerfall's stealth skill.
- [ ] **S9 · Release** Fatigue, encumbrance, swimming, and horse or cart movement modifiers.
- [ ] **S10 · Release** Send time of day, season, and weather to Doom's sky and lighting.
- [ ] **S11 · Release** Check music and Daggerfall audio during a bridged session. Not tested here.
- [ ] **S12 · Release** Doom keybinds for Daggerfall's other windows: journal, map, character sheet, spellbook, rest.
- [ ] **S13 · Later** Vampirism and lycanthropy forms in Doom. Depends on: S2.

**Owner decisions**

- **D1:** How a quest foe maps onto a mook pack (see Questions).
- **D2:** How peaceful NPCs react to being shot (see Questions).
- **D3:** Whether a playable kill quest is required for MVP (see Questions).

## 2. Data inventory

| Data | Count | Used by | Status |
|---|---:|---|---|
| Quest scripts (DFU text) | 265; 187 in classic list, 34 `S*` main | QuestMachine | Runs hidden, **no Doom link** |
| Original QBN / QRC files | 232 / 229 | Source of quest scripts | Not needed directly |
| Quest persons / foes / items | 574 / 444 / 551 | Quest resources | **Missing** in Doom |
| Quest places / clocks / variables | 359 / 399 / 442 | Quest state | Daggerfall only |
| Interior NPC records | 14,174 in block templates; 2,980 have a faction | Talk, guilds, shops, quests | **Missing**: converter deliberately skips them |
| Buildings in block templates | 9,005 in 920 RMB blocks | Towns | Built, conversion on demand |
| Dungeon blocks | 187 RDB | Dungeons | Built, audit planned |
| Regions / locations | 62 (45 with locations) / 15,251 | World, travel, quest sites | Built |
| 3D models | 10,251 | World | Built |
| Text records (`TEXT.RSC`) | 1,408 | UI, dialogue, messages | Daggerfall UI |
| Books | 95 files | Item use | Needs inventory menu |
| Factions | 366 | Reputation, guilds, quests | Daggerfall only; hostile link missing |
| Item templates | 288 | Inventory, loot, shops | Translation planned |
| Magic item definitions | 59 | Loot, artifacts | Translation planned |
| Standard spells | 89 | Spellbook, quests | **No task** beyond hotkeys |
| Monster records / quest foe types | 103 / 62 | Enemies | Random Doom roster; mapping planned |
| Class / biography files | 19 / 18 | Character creation | New game flow planned |
| Music / videos | 131 / 17 | Audio, cutscenes | **Not checked** |

## 3. Quest playability

**Key findings**

- [code] **Quest popups are the first blocker.** `Say` calls a message box, and pushing a window pauses Daggerfall with `Time.timeScale = 0` (`UserInterfaceManager.cs:184`, `GameManager.cs:607`). The UI bridge only handles windows Doom asked for (`DoomerfallUi.cs:249`), so the player would see nothing and quest ticking would stop.
- [code] **Clicks cannot reach Daggerfall.** The bridge disables `PlayerActivate` (`DoomerfallPositionSync.cs:333`), which is the only route to `StaticNPCClick`.
- [code] **NPCs and quest markers are not exported.** `FlatExport.cs:19` excludes NPC, treasure, and editor flats. `SiteExport.cs:144` keeps only enter and rest markers.
- [code] **Quest foes would be frozen and unkillable.** Daggerfall creates them in its hidden world with AI disabled. `PreventEnemySpawns` does not stop `create foe`.
- [code] **The bridge can avoid hidden 3D foes.** `Foe.SetInjured`, `Foe.IncrementKills`, and `SetPlayerClicked` are public, so Doom events can drive quest state directly.

**Actions by what they need** ([data] script lines / quests, [judgment] grouping)

| Need | Actions |
|---|---|
| **Runs hidden** (no Doom work expected) | when-task 794/216, end quest 543/251, timers 420/243, log 409/249, clear 209/165, reputation 207/102, get item 203/96, reveal 193/140, make permanent 136/78, dialog link 120/64, pick one 96/75, add dialog 77/43, have item 59/49, start task 49/36, take item 44/25, repute check 41/18, start quest 40/20, faces and questors 129 lines, daily 25/18, others under 20 lines |
| **Bridge: UI** | say 731/215, give pc 296/231, prompt 102/62, video 10/3 |
| **Bridge: NPC** | clicked npc 268/185, toting item and clicked 211/117, place npc 125/77, hide 89/53, create npc 48/38, create npc at 26/26, restore 14/6, mute 9/5, available 7/1, destroy 4/4 |
| **Bridge: foes** | place foe 224/125, killed 222/125, injured 172/98, give item 64/35, restrain 33/25, remove 22/13 |
| **Bridge: location** | pc at 95/77, enters/exits 8/2 |
| **Bridge: items** | place item 106/62, clicked item 66/45, dropped at place 8/5, item used 80/57 |
| **New system** | create foe 241/111, cast on foe 41/9, teleport 8/7, disease 11, cast spell 3/3, sound 3/2 |

Unused by any shipped script: 21 registered actions, including `pay money`, `spawn city guards`, `set player crime`, and `train pc`.

**Coverage if capabilities are added in this order** ([data] quests whose every action type is supported; this does not prove they play correctly)

| Add | Classic (187) | With unused ambushes skipped | Main (34) |
|---|---:|---:|---:|
| Popups and rewards | 0 | 0 | 3 |
| NPC use and placement | 15 | 17 | 7 |
| Location | 15 | 18 | 7 |
| Placed foes | **73** | 79 | 8 |
| World items | 83 | 103 | 12 |
| Item use | 97 | 124 | 14 |
| Ambush spawns | **170** | 170 | 28 |
| Spells, disease, teleport, sound | 187 | 187 | 34 |

**Smallest kill quest:** `M0C00Y11` uses 11 action types: timer, reveal, log, place foe, create npc at, end quest, killed, when, give pc, clicked npc, clear. Its target is one `Giant_scorpion` in a random local house, so it needs no dungeon. 48 enabled quests need only popups, NPCs, and placed foes.

**Facts for the pack decision** [data]

- 200 of 222 `killed` conditions need one kill, and 395 of 444 foe declarations are a single creature.
- Placed foes: 139 in dungeons, 77 in buildings, 8 at permanent sites.
- 82 enabled quests use `create foe`. In 50, a created foe is referenced by a kill or injury condition. In 32, it is not, so those could run without ambushes in a degraded form.

## 4. RPG systems against `gamedesign.md`

Backlog status comes from keyword searches of `work/backlog/`, plus the index.

| Domain | Status | Gap |
|---|---|---|
| World, time, weather | Partly built | Travel and position built. **Overlooked:** time and weather in Doom (S10) |
| Aesthetics | Partly built | Sprite scale and visual polish tracked |
| World persistence | Planned | Location state and item persistence in backlog |
| Combat and weapons | Partly built | DRLA runs. **Overlooked:** weapon damage types reaching Daggerfall (S1) |
| Monsters and encounters | Planned | Mook packs and roster in backlog |
| NPCs, dialogue, quests | **Overlooked** | Only wandering NPC and pack questions tracked (Q1 to Q15, S5) |
| Crime, guards | **Overlooked** | S4 |
| Vitals and death | Partly built | HP, death built. **Overlooked:** armor, fatigue, magicka (S1, S9) |
| Status effects | **Overlooked for the player** | Backlog covers mooks only (S2, S13) |
| Movement | Partly planned | Climbing and levitation planned. **Overlooked:** encumbrance, swimming, horses (S9) |
| Magic | **Overlooked** | Hotkey mention only (S3) |
| Loot and economy | Planned | Translation and world items planned. Shops depend on Q3 |
| Interactive world, locks | Planned | Locks in backlog. Traps need checking within that item |
| Stealth | **Overlooked** | S8 |
| Resting | **Overlooked** | S6 |
| Progression and skill XP | **Overlooked** | S7 |
| Audio and music | **Not checked** | S11 |

## Method and limits

- Actions were counted by applying each registered action's own regex, in `QuestMachine` registration order, to the QBN section of all 265 scripts. 89 unmatched lines were almost all global variable links.
- Binary counts use the layouts in Daggerfall Unity's readers. The spell count assumes 89-byte records: the file divides exactly and matches the 89-row quest spell table.
- NPC and building counts are block templates, not unique people in the world.
- "Runs hidden" is a classification. I read the bridge-critical actions, but not every simple action line by line.
- Failed approach: my first count treated `place npc/foe/item` actions as place declarations. I fixed the parser before using any numbers here.

## Play-test list

- After Q8, play `M0C00Y11`: accept it, find the target, kill it, return, get the reward, and save and reload midway.
- Judge whether quest popups interrupting Doom combat feel acceptable.
