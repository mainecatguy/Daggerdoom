# Magic: casting and self spells

**Waiting on:** owner approval to move to todo. This is the first magic slice (owner, 2026-11-25: self spells first).

Doom has no spell casting today. Daggerfall runs effects on its own entities; self-delivered effects therefore run in Daggerfall unchanged, and Doom only mirrors what changes play.

Scope:

1. **Cast plumbing.** A cast key in Doom casts Daggerfall's ready spell. Daggerfall checks and spends magicka, rolls the school skill, tallies skill uses, and runs the effects. Doom plays the cast animation and sound. Spellbook and spellmaker stay Daggerfall's UI.
2. **Self effects that already work through the sheet:** Fortify and Heal attributes, Heal Health/Fatigue/Spell Points, Regenerate, Cure Disease/Poison/Paralysis, Elemental Resistance, Spell Resistance, Spell Absorption, Shield (check that every hit goes through Daggerfall's damage path, and add a HUD readout of the absorb pool), Dispel Magic (player only for now, owner 2026-11-25), Identify, Create Item.
3. **Self effects Doom must mirror** (one sheet field each plus ZScript): Levitate (Doom flight), Slowfall (low gravity, no fall damage), Jumping (jump height multiplier), Invisibility Normal/True, Chameleon Normal/True, Shadow Normal/True (Doom shadow and invisibility flags; True means monsters cannot target the player; owner 2026-11-25: True Invisibility stays in), Light and Mage Light (dynamic light), Free Action (blocks Doom freezes), Water Breathing and Water Walking (only if converted maps have deep water).
4. **Item enchantments, ported as is** (owner, 2026-11-25), on Daggerfall items the player equips in Daggerfall:
   - Stat and utility: Enhances Skill, Improves Talents, Extra Spell Points, Strengthens Armor, Regens Health, Feather Weight, Increased Weight Allowance, Repairs Objects, Absorbs Spells.
   - **Cast When Used:** using the item casts its spell through the same cast path.
   - **Cast When Held:** while the item is equipped, Daggerfall applies its spell to the wearer and wears the item down each magic round (`CastWhenHeld.cs`). It acts only on the wearer, so it works with self effects as they are. Doom guns are not equipped in Daggerfall's sense, so this covers armor, clothing and jewellery.
5. **Artifacts and specials that work as is (owner agreed 2026-11-25):** Masque of Clavicus (better reactions while worn), Oghma Infinium (skill points on use), Racial Override and Passive Specials (owner: keep). Passive Specials includes sun damage, holy-place damage, regeneration in darkness, light or water, and magery weaker in light or darkness: check that Daggerfall still knows sunlight, darkness and water once its 3D world is off.

Effects cast on others (Touch, Target, Area deliveries) are in "Magic: effects on enemies".

Open questions for the owner:

1. Should Doom's magical monster projectiles (Imp, Baron, Cacodemon fireballs and similar) count as Magic, so Spell Reflection, Absorption and Resistance protect against them? Doom has reflection built in (`MF2_REFLECTIVE`).
