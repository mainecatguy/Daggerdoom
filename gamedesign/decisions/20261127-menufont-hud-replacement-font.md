## 2026-11-27: Should the converter pick up a Daggerfall replacement font (e.g. FONT0003-SDF.ttf) for Doom's HUD lines?

- **Verdict:** Leans (needs a one-line owner confirm).
- **Answer:** Probably yes. Doom's HUD messages already use a Daggerfall font, baked into ddruntime.pk3 from Daggerfall
  Unity's built-in font. Picking up a replacement font would keep those lines matching the menus when a texture pack
  changes the font. Confirm that the owner's "support daggerfall texture packs for text" covers Doom's HUD lines.
- **Rests on:** Owner (2026-11-26): "use daggerfall font, support daggerfall texture packs for text". Merged behavior: the
  HUD lines already use Daggerfall's font. Inference: once a pack changes the menu font, HUD lines in the old font would
  bring back the inconsistency the owner reported.
- **Challenge:** The card's scope is "Daggerfall menus shown in Doom", and the owner's words were about the merchant
  menu. AGENTS.md gives Doom the combat HUD, and the Aesthetics row says combat effects look like Doom/DRLX. So the owner's
  rule plainly was not written about HUD lines and cannot settle them; hence the confirm. Not Deferred: it changes only
  which font file the existing converter bakes, with no new system and no ripple into play. Not minor: the player sees the
  result. Kept at Leans with a confirm.
