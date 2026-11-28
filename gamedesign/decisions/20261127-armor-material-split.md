## 2026-11-27: Armor material on shelves and in drops (leather/chain/plate split)

- **Verdict:** Leans / Not determined (was Follows clearly / Not determined).
- **Answer:** Leans: armor should reach the approved tier odds. Daggerfall's RandomArmorMaterial rolls leather 70%, chain
  20% and plate 10%, and only plate uses the approved odds, so Daedric armor is about 10x rarer than Daedric weapons (0.5%
  against 5% at level 30). That probably bends the approved odds, for shelves and enemy drops alike. Not determined: where
  leather and chain fit.
- **Rests on:** `work/notes/20261123-material-tier-proposal.md`, approved by the owner: the table is titled "Material
  odds for weapons, armor, and ammo" and runs Iron to Daedric, with no leather or chain. `gamedesign.md` Loot & Economy:
  "The material tier comes from the approved odds for the area level." Randomness: "Randomness never bends approved
  rules." Precedent: `20261127-triage-q34-shelf-material-odds.md`.
- **Challenge:** The same Loot & Economy line says Daggerfall "decides how much drops and in which category". Leather and
  chain can be read as armor kinds Daggerfall picks (light, medium and heavy armor), with the approved odds applying to
  plate. Under that reading the build follows the rules. Under the other reading they are materials below Iron, which is
  how Daggerfall's own data stores them, and 90% of armor misses the table. Both readings are honest. The q34 precedent
  was about the classic tier curve, not this split. The fix also changes what the player sees (how much leather and
  chain appears, and how common Daedric armor is). Downgraded to Leans, with the owner deciding.
- **Owner question:** Your approved tier table covers armor from Iron to Daedric. Should leather and chain count as armor
  kinds Daggerfall picks (Daedric armor then stays about 10x rarer than Daedric weapons), or should every armor piece roll
  the table, and if so where do leather and chain go?
