# Player HP

Game design rules for the player's maximum HP. Owner decisions are dated.

## Formula (owner, 2026-11-25)

- **Starting HP = 50 + Endurance.**
- **Each level after the first adds Endurance / 15.**
- It always uses the player's current live Endurance, so Fortify and Drain Endurance change max HP while they last
  (owner, 2026-11-25). Because it is current, so the order Endurance is gained never matters: raising it later
  counts for all past levels too. As one line: max HP = 50 + Endurance x (level + 14) / 15.
- No flat bonus per level. Low Endurance means low HP, by design ("if you want to be able to take damage then have
  some endurance": player agency).
- Examples at level 1 / level 20: Endurance 30 gives 80 / 118, 50 gives 100 / 163, 75 gives 125 / 220, 100 gives
  150 / 277.

## Class bonus (owner, 2026-11-25)

- Class no longer sets HP. A class's HP per level becomes an **Endurance bonus = class HP per level - 8**. It adds to
  the starting Endurance and to the maximum Endurance, which is currently the way past 100 Endurance (or below the usual cap of 100).
- Stock classes: Mage and Sorcerer -2; Healer, Nightblade, Burglar, Acrobat 0; Battlemage, Bard, Thief +2;
  Spellsword, Rogue, Assassin +4; Monk +6; Archer +8; Ranger, Knight +10; Warrior +12; Barbarian +17. Custom classes
  (4 to 30 HP per level) get -4 to +22.
- In the custom class editor the control is labeled **ENDURANCE (AND MAX END) BONUS**.
