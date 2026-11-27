# Review Willpower's Daggerfall effects

Waiting on: the owner moving it to todo; best after `attributes` 01 (Willpower's Doom damage modifier).

Owner (2026-11-26): "take a backlog item to review the other effects of willpower and ensure they continue to work."

Known Daggerfall effects: Magic Resist = Willpower / 10, added to saving throws against spell effects
(`FormulaHelper.cs:1532`, `DaggerfallEntity.MagicResist`); Willpower is the governing attribute of six skills
(`DaggerfallSkills.cs:487-497`, effect unchecked). Find any others, check each still works in a bridged game
(for example whether Doom-side magic or status effects use the saving throw), and report what does not.
