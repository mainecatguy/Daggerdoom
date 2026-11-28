## 2026-11-27: Intelligence and Personality scale gun enchantments; enchanted guns show it

- **Verdict:** Owner decided.
- **Intelligence and Personality:** each scales the effectiveness of gun enchantments: -25% at 0, 0% at 50, +50% at
  100 (two straight lines meeting at 50). They are multipliers applied after all other calculations. They cost nothing:
  no extra magicka or charge use, no faster pool drain.
- **Visibility:** an enchanted gun must be recognisable on the ground or in a better weapon card. If Daggerfall's
  enchanted names work as for "Longsword of Sparks", showing the full name ("Battle Rifle of Sparks") when the gun
  drops is enough; if not, the agent reports how enchanted items can be told apart.
- **Order:** low priority, before the attribute help card (`attributes` 07).
- **Owner's words:** "let's have Intelligence and Personality both increase the effectiveness of gun enchantments from
  -25% to 0% (50) to +50% at 100". "intelligence and personality modifiers are multipliers after all damage
  calculations they don't increase point consumptions deplete the pool faster or anything".
- **Note (orchestrator):** today no Doom item carries enchantments (`DoomerfallDoomItems.cs`: "no Doom item has
  condition or enchantments yet"), so both depend on guns getting enchantments first. Whether Intelligence and
  Personality multiply with each other was not stated; other attribute bonuses multiply.
