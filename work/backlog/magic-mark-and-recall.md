# Magic: Mark and Recall

**Waiting on:** "Magic: casting and self spells" and owner approval. Owner wants this (2026-11-25).

- **Recall** is Daggerfall's Teleport effect: return to a marked place. Daggerfall owns the position and saves; Doom loads that area and places the player, through the existing area loading and transition path.
- **Mark** is new: remember up to 12 locations (owner: "up to 12 I guess"). Stock Daggerfall Teleport keeps one anchor. The list is Daggerfall state and goes in saves.

Owner decisions (2026-11-25):

- Casting Mark opens a simple Daggerfall menu listing slots 1 to 12; the player picks one, empty or used, and a used slot is overwritten. Recall uses the same kind of list.
- The implementer may use basic, common-sense UI affordances (for example showing each slot's place name and date, greying empty slots on Recall, a yes/no before overwriting) without asking, as long as it stays simple.
