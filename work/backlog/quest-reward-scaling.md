# Quest reward scaling

**Waiting on:** owner answer for quests no giver offers. Decided (owner, 2026-11-27): "Quest Gold: Agree, use Area
Level now." Quests a giver offers roll their gold and magic items at the level of the giver's place (a town's town
level, at least 5/10/15/20 by class; otherwise the place's area level), never the player's level; guild quest gold
still follows guild rank. Built by `work/queue/questgold/01` (notes `work/notes/20261128-045547.md`), replacing the
earlier fixed level 20 (`questrewards`, 2026-11-24).

Open: quests started by another quest (`start quest` / `run quest`), by a letter or by a timer still use the old fixed
level 20 (`WorldLevel.DoomerfallUnplacedQuestRewardLevel`) until the owner picks a place for them (for example the
parent quest's level or the quest's target place).
