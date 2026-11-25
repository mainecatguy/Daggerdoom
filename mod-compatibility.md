# Adding a Doom mod: compatibility conversion

The process for making a new Doom mod (weapons, monsters, items, classes) work in Doomerfall, so nothing is forgotten.
Follow it in order and record the results in a note in `work/notes/`. Game design choices it raises go to the owner;
make only the constrained mapping calls a written rule allows (AGENTS.md, "Game design belongs to the owner").

## Before you start

1. Read `manual.md` (what players see), `gamedesign/skills.md` (decided skill bindings) and `gamedesign/damage.md`.
2. Put the mod's PK3 in `GameMods/` and extract it to `GameMods/ExtractedData/<mod>` (read-only). Never commit either.
3. A mod set locks a save: class names must stay stable per save, and switching mods means a new save.

## Checklist

1. **Player classes.** The Doom player has no class. A mod's player classes and class perks must not apply; any
   wanted effect becomes a Daggerfall skill effect (`gamedesign/skills.md`). List the mod's classes and what each did.
2. **Weapons and skill bindings.** List every weapon and its category from the mod's own data (type tokens, slots,
   inventory groups). Bind each to its governing Daggerfall skill from `gamedesign/skills.md` (melee: Hand-to-Hand).
   A weapon with no clear category is an owner question.
3. **Ammo.** Map each ammo type to Doomerfall's ammo stacks in Daggerfall's inventory (weight, price, tiers). A new
   ammo type is an owner question.
4. **Weapon items in Daggerfall.** Guns become Daggerfall inventory items with a picture, weight, material and hotkey
   support. Check pickup by Use and that the mod's weapon modifications survive a swap, save and load.
5. **Health, armor and powerups.** Daggerfall owns HP and armor. Decide with the owner's rules whether each item heals
   against Daggerfall's max HP, converts, or is refused.
6. **Damage types.** Map the mod's damage types to Daggerfall resistances and to the damage bonus rules.
7. **Monsters.** Add each monster to the encounter pool with a price and traits (`mods/doomerfall/src/zscript/`
   `EncounterPool.zs`, `doomerfall_encounters.txt`). Prices follow the encounter rules; missing rules are owner questions.
8. **Drops and loot.** Native drops must be deterministic (fixed loot seeds). Mod items that Daggerfall rolls need a
   material tier and area level odds.
9. **Stock fallback.** Doomerfall must still run without the mod and with stock Doom weapons. Nothing may depend on the
   mod being present.
10. **Test.** Startup check with and without the mod (`uzdoom.exe -iwad <wad> -file <mods> -norun`, exit 1337), then a
    paired run: pick up, hotkey, fire, save, load.
11. **Document.** Update `manual.md` once merged to `main`, and record the mappings in the note.
