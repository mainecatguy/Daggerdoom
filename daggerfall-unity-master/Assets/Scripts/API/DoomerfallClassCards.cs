// Doomerfall: the class cards. The owner's hand-made skill lists for the 18 preset classes in both modes, and the
// conversion rule for custom classes. Source: work/notes/20261126-class-skill-remap-proposal.md (hand-made section).

using System;
using S = DaggerfallConnect.DFCareer.Skills;

namespace DaggerfallConnect
{
    public static class DoomerfallClassCards
    {
        /// <summary>Guns mode: weapon skills are Doom skills. Always on today; a no-guns option does not exist yet.</summary>
        public static bool GunsMode = true;

        // No-guns cards: each preset class (CLASS00-17 order) with its removed languages and Critical Strike replaced
        // by Daggerfall skills. Same slots and tiers as classic: 3 primary, 3 major, 6 minor.
        static readonly S[][] NoGunsCards =
        {
            new[] { S.Mysticism, S.Alteration, S.Thaumaturgy, S.Illusion, S.Destruction, S.Restoration, S.Medical, S.ShortBlade, S.BluntWeapon, S.Etiquette, S.Mercantile, S.Dodging }, // 00 Mage
            new[] { S.Axe, S.LongBlade, S.BluntWeapon, S.Destruction, S.Illusion, S.Alteration, S.Restoration, S.Thaumaturgy, S.Mysticism, S.ShortBlade, S.HandToHand, S.Archery }, // 01 Spellsword
            new[] { S.Destruction, S.LongBlade, S.Axe, S.Thaumaturgy, S.Alteration, S.HandToHand, S.Illusion, S.Mysticism, S.Restoration, S.Archery, S.ShortBlade, S.BluntWeapon }, // 02 Battlemage
            new[] { S.Mysticism, S.Alteration, S.Thaumaturgy, S.Destruction, S.Restoration, S.Illusion, S.Medical, S.ShortBlade, S.BluntWeapon, S.Etiquette, S.Mercantile, S.Dodging }, // 03 Sorcerer
            new[] { S.Restoration, S.Medical, S.Dodging, S.Thaumaturgy, S.Mysticism, S.Alteration, S.Illusion, S.Streetwise, S.Etiquette, S.ShortBlade, S.HandToHand, S.BluntWeapon }, // 04 Healer
            new[] { S.Illusion, S.Stealth, S.Dodging, S.Thaumaturgy, S.ShortBlade, S.Lockpicking, S.Alteration, S.Archery, S.Mercantile, S.Destruction, S.Restoration, S.Backstabbing }, // 05 Nightblade
            new[] { S.Streetwise, S.Etiquette, S.Pickpocket, S.Stealth, S.ShortBlade, S.HandToHand, S.Lockpicking, S.Alteration, S.Illusion, S.Destruction, S.Archery, S.Restoration }, // 06 Bard
            new[] { S.Lockpicking, S.Stealth, S.Climbing, S.Mercantile, S.Dodging, S.ShortBlade, S.Jumping, S.Running, S.HandToHand, S.Pickpocket, S.Streetwise, S.Backstabbing }, // 07 Burglar
            new[] { S.LongBlade, S.Stealth, S.Dodging, S.Pickpocket, S.Backstabbing, S.Streetwise, S.ShortBlade, S.BluntWeapon, S.Lockpicking, S.HandToHand, S.Running, S.Swimming }, // 08 Rogue
            new[] { S.Jumping, S.Dodging, S.Running, S.Climbing, S.HandToHand, S.Stealth, S.Pickpocket, S.LongBlade, S.Backstabbing, S.ShortBlade, S.Archery, S.Swimming }, // 09 Acrobat
            new[] { S.Pickpocket, S.Stealth, S.ShortBlade, S.Backstabbing, S.Climbing, S.Lockpicking, S.BluntWeapon, S.Jumping, S.Running, S.Dodging, S.Streetwise, S.Mercantile }, // 10 Thief
            new[] { S.Running, S.Backstabbing, S.Stealth, S.ShortBlade, S.LongBlade, S.BluntWeapon, S.Axe, S.Archery, S.Lockpicking, S.Pickpocket, S.Climbing, S.Dodging }, // 11 Assassin
            new[] { S.HandToHand, S.Running, S.Dodging, S.Swimming, S.Medical, S.BluntWeapon, S.Axe, S.LongBlade, S.Archery, S.ShortBlade, S.Jumping, S.Climbing }, // 12 Monk
            new[] { S.Archery, S.HandToHand, S.Dodging, S.Axe, S.BluntWeapon, S.Backstabbing, S.LongBlade, S.ShortBlade, S.Climbing, S.Jumping, S.Running, S.Swimming }, // 13 Archer
            new[] { S.LongBlade, S.Axe, S.Climbing, S.Swimming, S.Archery, S.Stealth, S.BluntWeapon, S.HandToHand, S.ShortBlade, S.Running, S.Dodging, S.Medical }, // 14 Ranger
            new[] { S.BluntWeapon, S.LongBlade, S.Axe, S.Jumping, S.Running, S.Swimming, S.Medical, S.Climbing, S.Dodging, S.HandToHand, S.Archery, S.Streetwise }, // 15 Barbarian
            new[] { S.Axe, S.LongBlade, S.BluntWeapon, S.HandToHand, S.Archery, S.ShortBlade, S.Climbing, S.Jumping, S.Dodging, S.Running, S.Swimming, S.Medical }, // 16 Warrior
            new[] { S.LongBlade, S.Etiquette, S.BluntWeapon, S.Axe, S.Archery, S.ShortBlade, S.Medical, S.Dodging, S.HandToHand, S.Jumping, S.Swimming, S.Climbing }, // 17 Knight
        };

        // Guns cards: the no-guns card with every Daggerfall weapon slot given a Doom skill by hand.
        // Destruction, Hand-to-Hand and Dodging stay.
        static readonly S[][] GunsCards =
        {
            new[] { S.Mysticism, S.Alteration, S.Thaumaturgy, S.Illusion, S.Destruction, S.Restoration, S.Medical, S.Pistols, S.EnergyWeapons, S.Etiquette, S.Mercantile, S.Dodging }, // 00 Mage
            new[] { S.Shotguns, S.Melee, S.Automatics, S.Destruction, S.Illusion, S.Alteration, S.Restoration, S.Thaumaturgy, S.Mysticism, S.EnergyWeapons, S.HandToHand, S.Rifles }, // 01 Spellsword
            new[] { S.Destruction, S.Explosives, S.EnergyWeapons, S.Thaumaturgy, S.Alteration, S.HandToHand, S.Illusion, S.Mysticism, S.Restoration, S.Rifles, S.Melee, S.Shotguns }, // 02 Battlemage
            new[] { S.Mysticism, S.Alteration, S.Thaumaturgy, S.Destruction, S.Restoration, S.Illusion, S.Medical, S.Explosives, S.EnergyWeapons, S.Etiquette, S.Mercantile, S.Dodging }, // 03 Sorcerer
            new[] { S.Restoration, S.Medical, S.Dodging, S.Thaumaturgy, S.Mysticism, S.Alteration, S.Illusion, S.Streetwise, S.Etiquette, S.Pistols, S.HandToHand, S.EnergyWeapons }, // 04 Healer
            new[] { S.Illusion, S.Stealth, S.Dodging, S.Thaumaturgy, S.Pistols, S.Lockpicking, S.Alteration, S.Rifles, S.Mercantile, S.Destruction, S.Restoration, S.Backstabbing }, // 05 Nightblade
            new[] { S.Streetwise, S.Etiquette, S.Pickpocket, S.Stealth, S.Pistols, S.HandToHand, S.Lockpicking, S.Alteration, S.Illusion, S.Destruction, S.Automatics, S.Restoration }, // 06 Bard
            new[] { S.Lockpicking, S.Stealth, S.Climbing, S.Mercantile, S.Dodging, S.Pistols, S.Jumping, S.Running, S.HandToHand, S.Pickpocket, S.Streetwise, S.Backstabbing }, // 07 Burglar
            new[] { S.Shotguns, S.Stealth, S.Dodging, S.Pickpocket, S.Backstabbing, S.Streetwise, S.Pistols, S.EnergyWeapons, S.Lockpicking, S.HandToHand, S.Running, S.Swimming }, // 08 Rogue
            new[] { S.Jumping, S.Dodging, S.Running, S.Climbing, S.HandToHand, S.Stealth, S.Pickpocket, S.Automatics, S.Backstabbing, S.Pistols, S.Melee, S.Swimming }, // 09 Acrobat
            new[] { S.Pickpocket, S.Stealth, S.Pistols, S.Backstabbing, S.Climbing, S.Lockpicking, S.Explosives, S.Jumping, S.Running, S.Dodging, S.Streetwise, S.Mercantile }, // 10 Thief
            new[] { S.Running, S.Backstabbing, S.Stealth, S.Pistols, S.Rifles, S.Melee, S.Explosives, S.EnergyWeapons, S.Lockpicking, S.Pickpocket, S.Climbing, S.Dodging }, // 11 Assassin
            new[] { S.HandToHand, S.Running, S.Dodging, S.Swimming, S.Medical, S.Melee, S.Shotguns, S.EnergyWeapons, S.Rifles, S.Pistols, S.Jumping, S.Climbing }, // 12 Monk
            new[] { S.Rifles, S.HandToHand, S.Dodging, S.Explosives, S.Melee, S.Backstabbing, S.Automatics, S.EnergyWeapons, S.Climbing, S.Jumping, S.Running, S.Swimming }, // 13 Archer
            new[] { S.Rifles, S.Shotguns, S.Climbing, S.Swimming, S.Melee, S.Stealth, S.Explosives, S.HandToHand, S.Automatics, S.Running, S.Dodging, S.Medical }, // 14 Ranger
            new[] { S.Melee, S.Automatics, S.Shotguns, S.Jumping, S.Running, S.Swimming, S.Medical, S.Climbing, S.Dodging, S.HandToHand, S.Explosives, S.Streetwise }, // 15 Barbarian
            new[] { S.Shotguns, S.Automatics, S.Melee, S.HandToHand, S.Rifles, S.Explosives, S.Climbing, S.Jumping, S.Dodging, S.Running, S.Swimming, S.Medical }, // 16 Warrior
            new[] { S.Melee, S.Etiquette, S.EnergyWeapons, S.Shotguns, S.Rifles, S.Automatics, S.Medical, S.Dodging, S.HandToHand, S.Jumping, S.Swimming, S.Climbing }, // 17 Knight
        };

        // Custom classes (proposal's suggestion). A removed language becomes the first free of these...
        static readonly S[] LanguageFallback = { S.Etiquette, S.Streetwise, S.Mercantile, S.Medical };
        // ...and Critical Strike the first free of these.
        static readonly S[] CriticalStrikeFallback = { S.ShortBlade, S.LongBlade, S.Axe, S.BluntWeapon, S.Archery, S.Running };
        // Guns mode: Short Blade, Long Blade, Axe, Blunt Weapon, Archery become these; a repeat takes the first free gun skill.
        static readonly S[] DaggerfallWeapons = { S.ShortBlade, S.LongBlade, S.Axe, S.BluntWeapon, S.Archery };
        static readonly S[] DefaultGunMap = { S.Pistols, S.Automatics, S.Shotguns, S.Melee, S.Rifles };
        static readonly S[] GunFallback = { S.Pistols, S.Shotguns, S.Automatics, S.Rifles, S.Explosives, S.EnergyWeapons, S.Melee };

        public static int PresetCount { get { return GunsCards.Length; } }

        /// <summary>The card a preset class (0-17) uses in the current mode. A copy.</summary>
        public static S[] CardOf(int presetIndex)
        {
            return (S[])(GunsMode ? GunsCards : NoGunsCards)[presetIndex].Clone();
        }

        /// <summary>False for skills the custom class maker should not offer: Critical Strike (removed from class
        /// lists) and, in guns mode, the five Daggerfall weapon skills (the Doom skills are offered instead).</summary>
        public static bool OfferedInClassMaker(S skill)
        {
            if (skill == S.CriticalStrike || DFCareer.IsRemovedSkill(skill))
                return false;
            return !GunsMode || Array.IndexOf(DaggerfallWeapons, skill) < 0;
        }

        /// <summary>
        /// Which preset class a 12-skill list is, or -1 for a custom class. Found by the class's fixed skills (not its
        /// name, which may be localized): every slot that is not a weapon slot on the card must hold the card's skill,
        /// or something an older version put there (a monster language or gun-slot number 4-12, or Critical Strike),
        /// with at most two such older entries. Works for classic CLASS*.CFG data, saves from before the cards
        /// (placeholder filler) and saves with the cards.
        /// </summary>
        public static int PresetIndexOf(S[] list)
        {
            for (int c = 0; c < NoGunsCards.Length; c++)
            {
                int older = 0;
                bool match = true;
                for (int p = 0; p < 12 && match; p++)
                {
                    S card = NoGunsCards[c][p];
                    if (card != GunsCards[c][p])
                        continue; // weapon slot: Daggerfall or Doom skill, either mode
                    if (list[p] == card)
                        continue;
                    if (list[p] == S.CriticalStrike || (list[p] >= S.Shotguns && list[p] <= S.Impish))
                        older++;
                    else
                        match = false;
                }
                if (match && older <= 2)
                    return c;
            }
            return -1;
        }

        /// <summary>
        /// The class's skill lists for the current mode. A preset class takes its card. A custom class keeps its
        /// choices: each removed language (slots from firstLanguageSlot up, and 11-12) and Critical Strike take a
        /// Daggerfall skill, then in guns mode each Daggerfall weapon skill takes a Doom skill. Safe to repeat.
        /// </summary>
        public static S[] Apply(S[] list, S firstLanguageSlot)
        {
            int preset = PresetIndexOf(list);
            if (preset >= 0)
                return CardOf(preset);

            S[] result = (S[])list.Clone();
            for (int p = 0; p < result.Length; p++)
            {
                bool language = DFCareer.IsRemovedSkill(result[p]) || (result[p] >= firstLanguageSlot && result[p] <= S.Impish);
                if (language)
                    result[p] = FirstFree(result, LanguageFallback);
                else if (result[p] == S.CriticalStrike)
                    result[p] = FirstFree(result, CriticalStrikeFallback);
            }
            if (GunsMode)
            {
                for (int p = 0; p < result.Length; p++)
                {
                    int weapon = Array.IndexOf(DaggerfallWeapons, result[p]);
                    if (weapon < 0)
                        continue;
                    S gun = DefaultGunMap[weapon];
                    result[p] = Array.IndexOf(result, gun) < 0 ? gun : FirstFree(result, GunFallback);
                }
            }
            return result;
        }

        // First candidate the list lacks; if all are taken, the first skill the list lacks that a class may hold.
        static S FirstFree(S[] list, S[] candidates)
        {
            foreach (S s in candidates)
                if (Array.IndexOf(list, s) < 0)
                    return s;
            for (S s = S.Medical; s < S.Count; s++)
                if (Array.IndexOf(list, s) < 0 && s != S.CriticalStrike && !DFCareer.IsRemovedSkill(s)
                    && !(GunsMode && Array.IndexOf(DaggerfallWeapons, s) >= 0))
                    return s;
            return S.Medical; // unreachable: 33 usable skills, 12 slots
        }
    }
}
