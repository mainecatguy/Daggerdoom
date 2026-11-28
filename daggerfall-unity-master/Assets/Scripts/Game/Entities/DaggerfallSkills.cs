// Project:         Daggerfall Unity
// Copyright:       Copyright (C) 2009-2023 Daggerfall Workshop
// Web Site:        http://www.dfworkshop.net
// License:         MIT License (http://www.opensource.org/licenses/mit-license.php)
// Source Code:     https://github.com/Interkarma/daggerfall-unity
// Original Author: Gavin Clayton (interkarma@dfworkshop.net)
// Contributors:    
// 
// Notes:
//

using UnityEngine;
using System;
using DaggerfallConnect;

namespace DaggerfallWorkshop.Game.Entity
{
    /// <summary>
    /// Daggerfall skills collection for every entity.
    /// </summary>
    [Serializable]
    public class DaggerfallSkills
    {
        #region Fields

        public const int Count = (int)DFCareer.Skills.Count;
        public const int PrimarySkillsCount = 3;
        public const int MajorSkillsCount = 3;
        public const int MinorSkillsCount = 6;
        const int minDefaultValue = 3;
        const int maxDefaultValue = 6;

        // Current permanent skill values
        [SerializeField] short Medical;
        [SerializeField] short Etiquette;
        [SerializeField] short Streetwise;
        [SerializeField] short Jumping;
        [SerializeField] short Shotguns;
        [SerializeField] short Automatics;
        [SerializeField] short Explosives;
        [SerializeField] short Pistols; // Doomerfall: was Dragonish; a save without this field starts it untrained
        [SerializeField] short Rifles; // Doomerfall: was Nymph; a save without this field starts it untrained
        [SerializeField] short EnergyWeapons; // Doomerfall: was Daedric; a save without this field starts it untrained
        [SerializeField] short Melee; // Doomerfall: was Spriggan; a save without this field starts it untrained
        [SerializeField] short Centaurian;
        [SerializeField] short Impish;
        [SerializeField] short Lockpicking;
        [SerializeField] short Mercantile;
        [SerializeField] short Pickpocket;
        [SerializeField] short Stealth;
        [SerializeField] short Swimming;
        [SerializeField] short Climbing;
        [SerializeField] short Backstabbing;
        [SerializeField] short Dodging;
        [SerializeField] short Running;
        [SerializeField] short Destruction;
        [SerializeField] short Restoration;
        [SerializeField] short Illusion;
        [SerializeField] short Alteration;
        [SerializeField] short Thaumaturgy;
        [SerializeField] short Mysticism;
        [SerializeField] short ShortBlade;
        [SerializeField] short LongBlade;
        [SerializeField] short HandToHand;
        [SerializeField] short Axe;
        [SerializeField] short BluntWeapon;
        [SerializeField] short Archery;
        [SerializeField] short CriticalStrike;

        // Doomerfall: 1 in every save written since the gun skills replaced the monster languages, 0 (missing) in older saves.
        [SerializeField] short GunSkillsFormat;
        // 2: also written since slot 7 became Pistols (in older data slot 7 is Dragonish).
        // 3: also written since slot 8 became Rifles (in older data slot 8 is Nymph).
        // 4: also written since slots 9 and 10 became Energy Weapons and Melee (in older data Daedric and Spriggan).
        // 5: also written since the class cards (older class lists may hold the placeholder's gun filler, slots 4-6).
        public bool IsGunSkillsFormat { get { return GunSkillsFormat >= 1; } set { GunSkillsFormat = (short)(value ? 5 : 0); } }
        public bool HasClassCards { get { return GunSkillsFormat >= 5; } }
        public bool HasPistolsSlot { get { return GunSkillsFormat >= 2; } }
        public bool HasRiflesSlot { get { return GunSkillsFormat >= 3; } }
        public bool HasEnergyAndMeleeSlots { get { return GunSkillsFormat >= 4; } }

        /// <summary>Doomerfall: the first skill slot a save's class lists still read as a monster language
        /// (DFCareer.ApplyClassCard).</summary>
        public static DFCareer.Skills FirstLanguageSlotOf(DaggerfallSkills saved)
        {
            if (saved == null || !saved.IsGunSkillsFormat)
                return DFCareer.Skills.Shotguns;
            if (!saved.HasPistolsSlot)
                return DFCareer.Skills.Pistols;
            if (!saved.HasRiflesSlot)
                return DFCareer.Skills.Rifles;
            return saved.HasEnergyAndMeleeSlots ? DFCareer.Skills.Centaurian : DFCareer.Skills.EnergyWeapons;
        }

        // Mods are temporary changes to skill values from effects
        // Default is 0 - effects can raise/lower mod values during their lifecycle
        // This is designed so that effects are never operating on permanent skill values
        int[] mods = new int[Count];

        #endregion

        #region Constructors

        public DaggerfallSkills()
        {
            SetDefaults();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Set default value to each skill.
        /// </summary>
        public void SetDefaults()
        {
            for (int i = 0; i < Count; i++)
            {
                SetPermanentSkillValue(i, (short)UnityEngine.Random.Range(minDefaultValue, maxDefaultValue + 1));
            }
            Array.Clear(mods, 0, Count);
        }

        /// <summary>
        /// Doomerfall: gives slots 4-10 (classic Orcish, Harpy, Giantish, Dragonish, Nymph, Daedric, Spriggan) untrained values, so a character imported from
        /// a classic save starts the weapon skills like any other untrained skill instead of inheriting a language value.
        /// </summary>
        public void ResetGunSkillsToDefaults()
        {
            for (int i = (int)DFCareer.Skills.Shotguns; i <= (int)DFCareer.Skills.Melee; i++)
                SetPermanentSkillValue(i, (short)UnityEngine.Random.Range(minDefaultValue, maxDefaultValue + 1));
        }

        /// <summary>
        /// Copy contents of another DaggerfallSkills into this one.
        /// Does not copy active effect mods.
        /// </summary>
        /// <param name="other">Skilla collection to copy from.</param>
        public void Copy(DaggerfallSkills other)
        {
            for (int i = 0; i < Count; i++)
            {
                SetPermanentSkillValue(i, other.GetPermanentSkillValue(i));
            }
            GunSkillsFormat = other.GunSkillsFormat;
        }

        /// <summary>
        /// Create a new copy of this stat collection.
        /// Does not copy active effect mods.
        /// </summary>
        /// <returns>New DaggerfallStats which is a copy of this DaggerfallStats.</returns>
        public DaggerfallSkills Clone()
        {
            DaggerfallSkills newSkills = new DaggerfallSkills();
            newSkills.Copy(this);

            return newSkills;
        }

        #endregion

        #region Getters

        /// <summary>
        /// Gets live skill value by enum, including effect mods.
        /// </summary>
        /// <param name="skill">Skill to get.</param>
        /// <returns>Skill value.</returns>
        public short GetLiveSkillValue(DFCareer.Skills skill)
        {
            int mod = mods[(int)skill];
            int value = GetPermanentSkillValue(skill) + mod;

            // TODO: Any other clamping or processing

            return (short)value;
        }

        /// <summary>
        /// Gets live skill value by index, including effect mods.
        /// </summary>
        /// <param name="index">Index of skill.</param>
        /// <returns>Skill value.</returns>
        public short GetLiveSkillValue(int index)
        {
            if (index < 0 || index >= Count)
                return 0;

            return GetLiveSkillValue((DFCareer.Skills)index);
        }

        /// <summary>
        /// Gets permanent skill value by index, does not include effect mods.
        /// </summary>
        /// <param name="index">Index of skill.</param>
        /// <returns>Skill value.</returns>
        public short GetPermanentSkillValue(int index)
        {
            if (index < 0 || index >= Count)
                return 0;

            return GetPermanentSkillValue((DFCareer.Skills)index);
        }

        /// <summary>
        /// Gets permanent skill value by enum, does not include effect mods.
        /// </summary>
        /// <param name="skill">Skill to get.</param>
        /// <returns>Skill value.</returns>
        public short GetPermanentSkillValue(DFCareer.Skills skill)
        {
            switch (skill)
            {
                case DFCareer.Skills.Medical:
                    return Medical;
                case DFCareer.Skills.Etiquette:
                    return Etiquette;
                case DFCareer.Skills.Streetwise:
                    return Streetwise;
                case DFCareer.Skills.Jumping:
                    return Jumping;
                case DFCareer.Skills.Shotguns:
                    return Shotguns;
                case DFCareer.Skills.Automatics:
                    return Automatics;
                case DFCareer.Skills.Explosives:
                    return Explosives;
                case DFCareer.Skills.Pistols:
                    return Pistols;
                case DFCareer.Skills.Rifles:
                    return Rifles;
                case DFCareer.Skills.EnergyWeapons:
                    return EnergyWeapons;
                case DFCareer.Skills.Melee:
                    return Melee;
                case DFCareer.Skills.Centaurian:
                    return Centaurian;
                case DFCareer.Skills.Impish:
                    return Impish;
                case DFCareer.Skills.Lockpicking:
                    return Lockpicking;
                case DFCareer.Skills.Mercantile:
                    return Mercantile;
                case DFCareer.Skills.Pickpocket:
                    return Pickpocket;
                case DFCareer.Skills.Stealth:
                    return Stealth;
                case DFCareer.Skills.Swimming:
                    return Swimming;
                case DFCareer.Skills.Climbing:
                    return Climbing;
                case DFCareer.Skills.Backstabbing:
                    return Backstabbing;
                case DFCareer.Skills.Dodging:
                    return Dodging;
                case DFCareer.Skills.Running:
                    return Running;
                case DFCareer.Skills.Destruction:
                    return Destruction;
                case DFCareer.Skills.Restoration:
                    return Restoration;
                case DFCareer.Skills.Illusion:
                    return Illusion;
                case DFCareer.Skills.Alteration:
                    return Alteration;
                case DFCareer.Skills.Thaumaturgy:
                    return Thaumaturgy;
                case DFCareer.Skills.Mysticism:
                    return Mysticism;
                case DFCareer.Skills.ShortBlade:
                    return ShortBlade;
                case DFCareer.Skills.LongBlade:
                    return LongBlade;
                case DFCareer.Skills.HandToHand:
                    return HandToHand;
                case DFCareer.Skills.Axe:
                    return Axe;
                case DFCareer.Skills.BluntWeapon:
                    return BluntWeapon;
                case DFCareer.Skills.Archery:
                    return Archery;
                case DFCareer.Skills.CriticalStrike:
                    return CriticalStrike;
                default:
                    return 0;
            }
        }

        #endregion

        #region Setters

        /// <summary>
        /// Sets permanent skill value by enum, does not change effect mods.
        /// </summary>
        /// <param name="skill">Skill to set.</param>
        /// <param name="value">Skill value.</param>
        public void SetPermanentSkillValue(DFCareer.Skills skill, short value)
        {
            switch (skill)
            {
                case DFCareer.Skills.Medical:
                    Medical = value;
                    break;
                case DFCareer.Skills.Etiquette:
                    Etiquette = value;
                    break;
                case DFCareer.Skills.Streetwise:
                    Streetwise = value;
                    break;
                case DFCareer.Skills.Jumping:
                    Jumping = value;
                    break;
                case DFCareer.Skills.Shotguns:
                    Shotguns = value;
                    break;
                case DFCareer.Skills.Automatics:
                    Automatics = value;
                    break;
                case DFCareer.Skills.Explosives:
                    Explosives = value;
                    break;
                case DFCareer.Skills.Pistols:
                    Pistols = value;
                    break;
                case DFCareer.Skills.Rifles:
                    Rifles = value;
                    break;
                case DFCareer.Skills.EnergyWeapons:
                    EnergyWeapons = value;
                    break;
                case DFCareer.Skills.Melee:
                    Melee = value;
                    break;
                case DFCareer.Skills.Centaurian:
                    Centaurian = value;
                    break;
                case DFCareer.Skills.Impish:
                    Impish = value;
                    break;
                case DFCareer.Skills.Lockpicking:
                    Lockpicking = value;
                    break;
                case DFCareer.Skills.Mercantile:
                    Mercantile = value;
                    break;
                case DFCareer.Skills.Pickpocket:
                    Pickpocket = value;
                    break;
                case DFCareer.Skills.Stealth:
                    Stealth = value;
                    break;
                case DFCareer.Skills.Swimming:
                    Swimming = value;
                    break;
                case DFCareer.Skills.Climbing:
                    Climbing = value;
                    break;
                case DFCareer.Skills.Backstabbing:
                    Backstabbing = value;
                    break;
                case DFCareer.Skills.Dodging:
                    Dodging = value;
                    break;
                case DFCareer.Skills.Running:
                    Running = value;
                    break;
                case DFCareer.Skills.Destruction:
                    Destruction = value;
                    break;
                case DFCareer.Skills.Restoration:
                    Restoration = value;
                    break;
                case DFCareer.Skills.Illusion:
                    Illusion = value;
                    break;
                case DFCareer.Skills.Alteration:
                    Alteration = value;
                    break;
                case DFCareer.Skills.Thaumaturgy:
                    Thaumaturgy = value;
                    break;
                case DFCareer.Skills.Mysticism:
                    Mysticism = value;
                    break;
                case DFCareer.Skills.ShortBlade:
                    ShortBlade = value;
                    break;
                case DFCareer.Skills.LongBlade:
                    LongBlade = value;
                    break;
                case DFCareer.Skills.HandToHand:
                    HandToHand = value;
                    break;
                case DFCareer.Skills.Axe:
                    Axe = value;
                    break;
                case DFCareer.Skills.BluntWeapon:
                    BluntWeapon = value;
                    break;
                case DFCareer.Skills.Archery:
                    Archery = value;
                    break;
                case DFCareer.Skills.CriticalStrike:
                    CriticalStrike = value;
                    break;
            }
        }

        /// <summary>
        /// Sets permanent skill value by index, does not change effect mods.
        /// </summary>
        /// <param name="index">Index of skill.</param>
        /// <param name="value">Skill value.</param>
        public void SetPermanentSkillValue(int index, short value)
        {
            if (index < 0 || index >= Count)
                return;

            SetPermanentSkillValue((DFCareer.Skills)index, value);
        }

        /// <summary>
        /// Assign mods from effect manager.
        /// </summary>
        public void AssignMods(int[] skillMods)
        {
            Array.Copy(skillMods, mods, Count);
        }

        #endregion

        #region Static Methods

        public static DFCareer.Stats GetPrimaryStat(DFCareer.Skills skill)
        {
            switch (skill)
            {
                case DFCareer.Skills.Medical:
                    return DFCareer.Stats.Intelligence;
                case DFCareer.Skills.Etiquette:
                    return DFCareer.Stats.Personality;
                case DFCareer.Skills.Streetwise:
                    return DFCareer.Stats.Personality;
                case DFCareer.Skills.Jumping:
                    return DFCareer.Stats.Strength;
                // Doomerfall gun skills: governing stats set by the owner (2026-11-27, gun skill governing attributes)
                case DFCareer.Skills.Shotguns:
                    return DFCareer.Stats.Strength;
                case DFCareer.Skills.Automatics:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.Explosives:
                    return DFCareer.Stats.Strength;
                case DFCareer.Skills.Pistols:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.Rifles:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.EnergyWeapons:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.Melee:
                    return DFCareer.Stats.Strength;
                case DFCareer.Skills.Centaurian:
                    return DFCareer.Stats.Intelligence;
                case DFCareer.Skills.Impish:
                    return DFCareer.Stats.Intelligence;
                case DFCareer.Skills.Lockpicking:
                    return DFCareer.Stats.Intelligence;
                case DFCareer.Skills.Mercantile:
                    return DFCareer.Stats.Personality;
                case DFCareer.Skills.Pickpocket:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.Stealth:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.Swimming:
                    return DFCareer.Stats.Endurance;
                case DFCareer.Skills.Climbing:
                    return DFCareer.Stats.Strength;
                case DFCareer.Skills.Backstabbing:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.Dodging:
                    return DFCareer.Stats.Speed;
                case DFCareer.Skills.Running:
                    return DFCareer.Stats.Speed;
                case DFCareer.Skills.Destruction:
                    return DFCareer.Stats.Willpower;
                case DFCareer.Skills.Restoration:
                    return DFCareer.Stats.Willpower;
                case DFCareer.Skills.Illusion:
                    return DFCareer.Stats.Willpower;
                case DFCareer.Skills.Alteration:
                    return DFCareer.Stats.Willpower;
                case DFCareer.Skills.Thaumaturgy:
                    return DFCareer.Stats.Willpower;
                case DFCareer.Skills.Mysticism:
                    return DFCareer.Stats.Willpower;
                case DFCareer.Skills.ShortBlade:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.LongBlade:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.HandToHand:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.Axe:
                    return DFCareer.Stats.Strength;
                case DFCareer.Skills.BluntWeapon:
                    return DFCareer.Stats.Strength;
                case DFCareer.Skills.Archery:
                    return DFCareer.Stats.Agility;
                case DFCareer.Skills.CriticalStrike:
                    return DFCareer.Stats.Agility;
                default:
                    return (DFCareer.Stats)(-1);
            }
        }

        public static DFCareer.Stats GetPrimaryStat(int index)
        {
            return GetPrimaryStat((DFCareer.Skills)index);
        }

        public static int GetAdvancementMultiplier(DFCareer.Skills skill)
        {
            switch (skill)
            {
                case DFCareer.Skills.Medical:
                    return 12;
                case DFCareer.Skills.Etiquette:
                case DFCareer.Skills.Streetwise:
                    return 1;
                case DFCareer.Skills.Jumping:
                    return 5;
                case DFCareer.Skills.Shotguns: // Doomerfall gun skills advance like Daggerfall's weapon skills
                case DFCareer.Skills.Automatics:
                case DFCareer.Skills.Explosives:
                case DFCareer.Skills.Pistols:
                case DFCareer.Skills.Rifles:
                case DFCareer.Skills.EnergyWeapons:
                case DFCareer.Skills.Melee:
                    return 2;
                case DFCareer.Skills.Centaurian:
                case DFCareer.Skills.Impish:
                    return 15;
                case DFCareer.Skills.Lockpicking:
                    return 2;
                case DFCareer.Skills.Mercantile:
                    return 1;
                case DFCareer.Skills.Pickpocket:
                case DFCareer.Skills.Stealth:
                    return 2;
                case DFCareer.Skills.Swimming:
                    return 1;
                case DFCareer.Skills.Climbing:
                    return 2;
                case DFCareer.Skills.Backstabbing:
                    return 1;
                case DFCareer.Skills.Dodging:
                    return 4;
                case DFCareer.Skills.Running:
                    return 50;
                case DFCareer.Skills.Destruction:
                    return 1;
                case DFCareer.Skills.Restoration:
                    return 2;
                case DFCareer.Skills.Illusion:
                case DFCareer.Skills.Alteration:
                    return 1;
                case DFCareer.Skills.Thaumaturgy:
                    return 2;
                case DFCareer.Skills.Mysticism:
                    return 1;
                case DFCareer.Skills.ShortBlade:
                case DFCareer.Skills.LongBlade:
                case DFCareer.Skills.HandToHand:
                case DFCareer.Skills.Axe:
                case DFCareer.Skills.BluntWeapon:
                    return 2;
                case DFCareer.Skills.Archery:
                    return 1;
                case DFCareer.Skills.CriticalStrike:
                    return 8;
                default:
                    return 0;
            }
        }

        /// <summary>
        /// Doomerfall removed the monster languages, so no skill is a language skill.
        /// </summary>
        public static bool IsLanguageSkill(DFCareer.Skills skill)
        {
            return false;
        }

        /// <summary>
        /// Doomerfall: true for the unused slots left by the removed monster languages (see DFCareer.IsRemovedSkill).
        /// </summary>
        public static bool IsRemovedSkill(DFCareer.Skills skill)
        {
            return DFCareer.IsRemovedSkill(skill);
        }

        #endregion
    }
}
