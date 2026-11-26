## 2026-11-26: Should the level-up sound (and Daggerfall's window sounds) be heard, and should Doom add a HUD line? [20261126-003657]

- **Verdict:** Sound heard: Follows clearly. New HUD line: Not determined.
- **Answer:** Daggerfall's level-up sound and its window sounds should be heard in a bridge session. Whether Daggerfall
  plays them or Doom plays Daggerfall's sound is engineering. A "You have reached level N" line is new (Daggerfall
  Unity has none) and goes to the owner.
- **Rests on:** `gamedesign.md`, Audio row: "Daggerfall supplies music, UI sounds, and NPC barks; Doom supplies combat
  SFX." The owner's skill point card (`skillmenu` 02): "play a Daggerfall sound and show the notification message
  Daggerfall uses ... shown on Doom's screen."
- **Challenge:** The session-wide mute (`DoomerfallNewGame`) may have been a deliberate engineering choice, and Doom
  owns the window. But AGENTS.md does not give Doom sound, and the Audio row names UI sounds as Daggerfall's outright.
  Unmuting Daggerfall entirely would also bring back its music, which is a larger change; the verdict covers UI sounds
  only. Kept.
