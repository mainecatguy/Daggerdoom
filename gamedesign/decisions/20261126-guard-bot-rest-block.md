## 2026-11-26: Should hostile guard bots block resting, like monsters do? (recheck of the 2026-11-24 rest part) [20261123-233427]

- **Verdict:** Follows clearly.
- **Answer:** Yes. Hostile guard bots nearby block rest, as hostile guards do in Daggerfall. Only the rest part of the
  2026-11-24 entry changes; its crime part stands and its travel part stays open.
- **Rests on:** `gamedesign.md`, Resting row: prevailing system "Daggerfall", and "Rest opens in Doom as Daggerfall's
  rest menu exactly as in Daggerfall ... (owner, 2026-11-26)". Daggerfall's rest menu itself refuses to rest when enemies
  are near (`DaggerfallRestWindow.cs:403`, `AreEnemiesNearby(true)`, message 354 "enemies nearby"), and hostile city
  guards count as enemies there. The Crime row: guard bots are Daggerfall's guards, "hostile guards pursue and fight like
  Doom bots".
- **Options struck:** "guard bots do not block rest" contradicts the owner's "exactly as in Daggerfall" for the rest
  menu, whose own check refuses rest with hostile guards near. One option is left.
- **Inference:** the hostile bot is the Doom body of a Daggerfall guard, so Daggerfall's enemy-nearby check applies to
  it the same way the row's "blocked when Doom monsters are nearby" applies to monsters.
- **Challenge:** The owner's "exactly" may describe the menu's look and keybind, not its refusal rule, and the Resting
  row names "Doom monsters", not bots. But the refusal is part of the menu's behavior, and the row's prevailing system is
  Daggerfall either way, so both readings land on blocking. It builds nothing new: Doom already has to report nearby
  hostiles for the monster block, and a hostile bot is one more hostile. Not a Deferred question. Kept, upgraded from
  Leans to Follows clearly.
