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

using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.MagicAndEffects.MagicEffects
{
    /// <summary>
    /// Enhances one skill by 15 points.
    /// Effect can stack over multiple items.
    /// </summary>
    public class EnhancesSkill : BaseEntityEffect
    {
        public static readonly string EffectKey = EnchantmentTypes.EnhancesSkill.ToString();

        const int enchantCost = 900;
        const int modAmount = 15;

        public override void SetProperties()
        {
            properties.Key = EffectKey;
            properties.ShowSpellIcon = false;
            properties.AllowedCraftingStations = MagicCraftingStations.ItemMaker;
            properties.ItemMakerFlags = ItemMakerFlags.AllowMultiplePrimaryInstances | ItemMakerFlags.AlphaSortSecondaryList;
            properties.EnchantmentPayloadFlags = EnchantmentPayloadFlags.Held;
        }

        public override string GroupName => TextManager.Instance.GetLocalizedText(EffectKey);

        /// <summary>
        /// Outputs all variant settings for this enchantment.
        /// </summary>
        public override EnchantmentSettings[] GetEnchantmentSettings()
        {
            List<EnchantmentSettings> enchantments = new List<EnchantmentSettings>();

            // Enumerate classic params
            for (int i = 0; i < DaggerfallSkills.Count; i++)
            {
                DFCareer.Skills skill = (DFCareer.Skills)i;
                if (DFCareer.IsLegacyLanguageSlot((int)skill))
                    continue; // Doomerfall: monster language slots 4-12; gun skill enchantments wait for the owner
                EnchantmentSettings enchantment = new EnchantmentSettings()
                {
                    Version = 1,
                    EffectKey = EffectKey,
                    ClassicType = EnchantmentTypes.EnhancesSkill,
                    ClassicParam = (short)i,
                    PrimaryDisplayName = GroupName,
                    SecondaryDisplayName = DaggerfallUnity.Instance.TextProvider.GetSkillName(skill),
                    EnchantCost = enchantCost,
                };

                enchantments.Add(enchantment);
            }

            return enchantments.ToArray();
        }

        /// <summary>
        /// Doomerfall: a monster language (slots 4-12; 4-6 now hold the gun skills) is not offered in the item maker, but a soul's forced
        /// power or an old item may still name one. It keeps its classic setting and cost and has no effect.
        /// </summary>
        public override EnchantmentSettings? GetEnchantmentSettings(EnchantmentParam param)
        {
            DFCareer.Skills skill = (DFCareer.Skills)param.ClassicParam;
            if (!string.IsNullOrEmpty(param.CustomParam) || !DFCareer.IsLegacyLanguageSlot((int)skill))
                return base.GetEnchantmentSettings(param);
            return new EnchantmentSettings()
            {
                Version = 1,
                EffectKey = EffectKey,
                ClassicType = EnchantmentTypes.EnhancesSkill,
                ClassicParam = param.ClassicParam,
                PrimaryDisplayName = GroupName,
                SecondaryDisplayName = RemovedLanguageName(skill),
                EnchantCost = enchantCost,
            };
        }

        /// <summary>Doomerfall: the classic name of a removed monster language, marked as having no effect.</summary>
        public static string RemovedLanguageName(DFCareer.Skills skill)
        {
            string[] keys = { "orcish", "harpy", "giantish", "dragonish", "nymph", "daedric", "spriggan", "centaurian", "impish" };
            string name = TextManager.Instance.GetLocalizedText(keys[(int)skill - (int)DFCareer.Skills.Shotguns]);
            return name + " (no effect)";
        }

        public override void Start(EntityEffectManager manager, DaggerfallEntityBehaviour caster = null)
        {
            base.Start(manager, caster);

            // Must have enchantment params
            if (EnchantmentParam == null)
                return;

            // Set skill mod
            DFCareer.Skills skill = (DFCareer.Skills)EnchantmentParam.Value.ClassicParam;
            if (DFCareer.IsLegacyLanguageSlot((int)skill))
                return; // Doomerfall: a removed monster language; the power has no effect
            SetSkillMod(skill, modAmount);
        }
    }
}