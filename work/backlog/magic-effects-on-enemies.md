# Magic: effects on enemies

**Waiting on:** "Magic: casting and self spells" (cast plumbing) and owner approval.

Doom monsters are Doom actors, not Daggerfall entities, so effects on them need Doom-side versions. Doom's spell projectile or area carries an effect id and Daggerfall's rolled magnitude and duration; Doom applies it. Owner decisions, 2026-11-25:

- **Pacify and Charm become generic.** Daggerfall's Pacify Animal/Undead/Humanoid/Daedra split goes away for playability; one Pacify and one Charm work on any monster.
- **Paralyze freezes the monster.**
- **Soul Trap:** a trapped kill of any pack member (mooks included) gives soul energy based on the original Daggerfall entity the pack was spawned from. Generous on purpose, so the soul gem and enchanting system works.
- **Silence becomes Ranged Attack Suppression:** affected monsters cannot use ranged attacks. If this proves too complicated or problematic (DRLA monsters have many custom attack states), stop and ask the owner to reconsider.
- **Detect Enemy / Treasure / Magic:** marks on the automap (overlaps the Thaumaturgy "Sense" perk in `work/notes/20261125-skills-armor-proposal.md`).

Artifacts and items that ride on this work (Doom spawns a friendly monster, as Charm makes one friendly):

- **Azura's Star:** a reusable soul trap; works once Soul Trap does.
- **Sanguine Rose:** spawns an allied Daedroth. Doom spawns the monster the encounter system maps to a Daedroth, friendly.
- **Skull of Corruption:** spawns a friendly copy of the nearest enemy's Doom class.

Dispel Undead and Dispel Daedra are in `work/future-ideas.md`; Dispel Magic on monsters is too.
