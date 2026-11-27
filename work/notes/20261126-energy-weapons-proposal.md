# Energy Weapons skill: proposal

Status: proposal for the owner (2026-11-26). Nothing here is decided except the theme and the 25 perk's direction
(`work/backlog/skills-in-doom.md`). Style and scale follow the sibling cards in `work/queue/skillperks/`.

Theme (owner): "escalating damage for even more escalating cost and ammo use, the rich guy's guns."
Money facts used below: a cell costs 5 gold; a stock plasma rifle fires about 12 shots a second at 1 cell each, so it
already burns about 60 gold a second. Gold weighs 0.0025 kg a coin (`DaggerfallBankManager.cs`), 400 coins per kg.

## 1. Which weapons count

Rule: **a weapon counts if it is fed by cells** (Doom's `Cell` ammo, or a DRLA magazine filled from cells), **plus the
BFG family and DRLA's "nuclear" self-recharging energy guns.** Stock Doom: **plasma rifle, BFG9000.**

DRLA guns fed by cells (from `Weapon.AmmoType` in `GameMods/ExtractedData/DoomRL_Arsenal_1.1.5`), clear cases:
Plasma Rifle, Laser Rifle, High Power Plasma/Laser Rifle, Plasma Rifle Mk II, Burst and Assault Plasma/Laser Rifles,
BFG9000, High Power BFG9000, VBFG9000, BFG10K, Biggest Fucking Gun, Tristar Blaster (and High Power), Hyper Blaster,
Laser Minigun, Plasma Refractor, Voltgun, Zeus Cannon, Particle Beam Cannon, Plasma Redirection Cannon, Tantrum Cannon,
Null Pointer, Chameleon Rifle, Baron Blaster, Reality Distortion Array, Hell's Reign, Plasma Cannon, Lucifer Cannon,
Neural Stunner, Suss Gun. Nuclear (self-recharging) plasma rifles, pistols and burst/assault variants also count.

Borderline:
- **Plasma pistols** (Plasma Pistol, Combat, Handcannon, Marksman, Plasma Uzi) and **plasma/laser shotguns** (Plasma
  Shotgun, Mk II, Heavy, Plasmatic Shrapnel, Laser Shotgun): fed by cells, but also pistols or shotguns. See question 1.
- **Railgun**: has DRLA's rifle token, but uses cells. Rifles are not counted by Pistols, so it falls here.
- **Energysaw**: a cell-fed melee weapon. Proposed: Melee, not Energy Weapons (it fights like a melee weapon).
- **Unmaker** (demonic, cells) and **Combat Translocator** (utility): proposed in for Unmaker, out for the Translocator
  (it is not an attack).
- **Nanomachic Plasma/Laser Rifles** make their own ammo, so cost perks have nothing to charge. Proposed: they count
  for damage, and their extra cost is taken as a slower self-refill (same drain, applied to the internal magazine).

## 2. Continuous scaling

Damage +0% to +60% across skill 0-100, linear (same as Automatics and Explosives). No cost change from scaling alone:
the cost comes from the perks.

## 3. Perks

**25: Overcharge** (decided direction, numbers proposed). Every energy shot costs **2x ammo** and deals **+50% damage**.
- Why: more damage per second, less damage per cell (0.75x efficiency). The first step of paying more for more.
- Detail: if the gun cannot pay the doubled cost, the shot fires at normal cost and normal damage. Stock BFG: 80 cells
  a shot. Fractions (DRLA guns that use partial cells) are tracked per gun and rounded as they add up.

**50: Line of Credit.** When an energy weapon runs dry (magazine and reserve both empty), it buys Regular cells from
the **gold you carry** at **2x shop price (10 gold a cell)**, 10 cells at a time, and keeps firing.
- Why: the rich guy never runs out, he just pays. Turns gold straight into firepower, and at 2x it is the most
  expensive ammo in the game.
- Alternative: no markup (5 gold a cell), but only 1 cell in 2 bought shots fires (same price, felt as waste).

**75: Escalation.** While you keep firing, each shot grows stronger and much costlier. Every cell spent in the current
streak adds **+1% damage (up to +100%)** and **+2% ammo cost (up to +200%)**. The streak ends 1 second after the last
shot.
- Why: "escalating damage for even more escalating cost", literally. Counted in cells, not shots, so it works the same
  for a fast plasma rifle (ramps over about 2 seconds) and a slow BFG (full in 3 shots).
- Distinct from Automatics' burst fire, which rewards the *first* shots; this rewards holding the trigger.
- At full stack with Overcharge, a plasma rifle shot costs 6 cells and deals 3x base damage (before the +60% scaling).

**100: Money Is No Object.** Energy weapons deal **+1% damage per 500 gold carried, up to +100% at 50,000 gold**
(125 kg of coin).
- Why: the richer you walk in, the harder you hit. It fights Line of Credit (spending gold lowers the bonus) and
  carry weight, so being rich is a real choice, not free.
- Alternative: **Overcharge II**: Overcharge becomes 4x ammo for +125% damage. Simpler, but repeats the 25 perk.

All multipliers multiply each other and the ammo tier bonus, like the other skills' damage bonuses.

## 4. Questions for the owner

1. **Overlap:** do plasma pistols and plasma/laser shotguns use Energy Weapons, their Pistols/Shotguns skill, or both
   (both perk sets apply)? Proposed: Energy Weapons only, since cells decide it.
2. **Overcharge on or off:** is Overcharge always on from 25, or a mode the player toggles (for example with the
   weapon's alt key when it has none)? Always on fits "the rich guy's guns"; a toggle lets a poor character still use
   cells.
3. **Line of Credit source:** gold carried only, or also the bank (letters of credit)? Carried only keeps it in tension
   with the 100 perk and carry weight.
4. **100 perk:** Money Is No Object or Overcharge II?

## 5. Implementation notes

- **Tag:** an energy-weapon list in the Doomerfall mod, built like the rifle tag (`rifletag` 01): cells as ammo, plus
  a short named list for BFG ammo, nuclear and nanomachic guns, and excluded items. Stock plasma rifle and BFG9000 by
  class. Projectiles (plasma balls, BFG ball and its tracers) carry the firing weapon's category so damage scaling
  applies on impact.
- **Damage:** the same skill damage hook the other gun skills use; Daggerfall sends the multiplier, Doom applies it.
- **Ammo cost:** Doom takes extra ammo after each energy shot (from the DRLA magazine first, else the reserve), with a
  per-gun fraction counter. Automatics' "one ammo per 2 shots" needs the same counter in reverse; share it.
- **Escalation:** a per-player streak counter (cells spent, reset 1 s after the last shot); no bridge traffic.
- **Line of Credit and Money Is No Object:** Daggerfall sends gold carried to Doom (the sheet sync already sends stats).
  Doom spends from that local budget and reports gold spent in batches (like Skill XP batching), Daggerfall deducts
  it. Bought cells are Regular tier.
- **Without Daggerfall:** no skill, so no perks; standard WADs are unaffected.
- Test guns: stock plasma rifle and BFG9000, DRLA Plasma Rifle, a nuclear plasma rifle, and the Railgun.

---

## Revision 2 (product owner, 2026-11-26): five options per level

Owner: "Propose like 5 perks for each level also the 'rich guy' theme is more the weapon should be logistically
expensive not every perk should force wedge that theme." The theme lives mostly in the 25 perk and the guns' ammo
appetite; the other levels are simply good energy-weapon perks. All work with the stock plasma rifle and BFG9000.

### 25 (decided direction: more ammo per shot, more damage)
1. **Overcharge:** 2x cells per shot, +50% damage.
2. **Hot cells:** +1 cell per shot and +X flat damage per shot (strong on the 1-cell plasma rifle, small on the BFG).
3. **Overdrive:** 1.5x cells, +25% damage and +15% fire rate.
4. **Fat bolts:** 2x cells, bigger projectiles with a small splash (the extra damage comes as splash).
5. **Charge-up:** holding fire charges a shot up to 3x cells for up to 2x damage (needs a hold-to-charge input).

### 50
1. **Piercing bolts:** energy projectiles pass through the first enemy they hit.
2. **Ionize:** a hit makes the target take +10% damage from energy weapons for 3 s.
3. **Shock:** energy hits are twice as likely to make monsters flinch (Doom pain chance x2).
4. **Thermal splash:** every energy hit does a small splash around the target.
5. **Direct feed:** energy guns with magazines never need reloading; they fire straight from carried cells
   (fewer pauses, faster drain).

### 75
1. **Escalation:** while firing continuously, each cell spent adds +1% damage (up to +100%) and +2% ammo cost
   (up to +200%); resets 1 s after the last shot.
2. **Arc:** a kill sends a bolt to the nearest enemy within about 5 m for 50% of the shot's damage.
3. **Plasma burn:** hits set targets burning for an extra 20% of the damage over 3 s.
4. **Resistance cutter:** energy weapons ignore half of a monster's energy resistance (DRLA resistances).
5. **Tracer storm:** BFG tracers +50%; plasma shots have a 10% chance to fire a small tracer.

### 100
1. **Overcharge II:** the 25 perk doubles again (4x cells, +125% damage).
2. **Meltdown:** monsters killed by energy weapons burst, damaging nearby monsters (not the player).
3. **Mana battery:** when cells run out, energy guns keep firing on Daggerfall magicka at a set cost per cell.
4. **Ricochet:** energy projectiles bounce once off walls.
5. **Money Is No Object:** +1% damage per 500 gold carried, up to +100% at 50,000 gold (kept from the first draft).

Dropped from the first draft: **Line of Credit** (cells bought from carried gold appear from nowhere, which breaks the
object permanence principle).
