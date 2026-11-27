## 2026-11-27: Approve the weapon skill reroute map? (Short Blade->Pistols, Long Blade->Automatics, Axe->Shotguns, Blunt->Melee, Archery->Explosives, Hand-to-Hand stays fists) [20261126]

- **Verdict:** Not determined (the owner reserved approval).
- **Answer:** None. The designer cannot approve it: "You propose the mapping and I'll approve/deny it"
  (`20261126-weapon-skill-reroute-owner.md`).
- **Settled facts the map must respect:**
  - Preset classes in guns mode use hand-made cards (`20261126-class-cards-hand-made.md`), so the reroute map only
    reaches custom classes (and anything else that converts a Daggerfall weapon skill without a card).
  - Rifles is a decided skill. `20261126-rifles-skill.md` records both "pistols and rifles becomes just pistols" (the
    pistol skill is Pistols) and "for rifles we need a skill. The skill is named Rifles". The quotes in
    `work/notes/20261126-145138.md` merged the old "Rifles and Pistols" idea into Pistols. They did not drop Rifles.
  - The class-card proposal the owner approved (`work/notes/20261126-class-skill-remap-proposal.md:119-122`) already gives
    a custom-class default of Archery->Rifles. Nine hand-made cards use Archery->Rifles. The new map's
    Archery->Explosives breaks with both, so the owner must choose between them.
  - "Every class has at least one firearm" is worded for the hand-made preset cards. The same proposal says "A custom
    class with no weapon skills gets no firearm" (line 122), so it does not bind custom classes.
- **Narrowed question:** For custom classes, approve Short Blade->Pistols, Long Blade->Automatics, Axe->Shotguns,
  Blunt->Melee, Hand-to-Hand unchanged. For Archery: Rifles (as in the approved proposal and the cards) or Explosives
  (as proposed now, perhaps because Rifles isn't built yet)?
- **Challenge:** The answer pass treated this as approval-ready. It is the owner's call by his own words, and the
  Archery row conflicts with approved material. Changed to Not determined.
