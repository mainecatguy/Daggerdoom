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
using DaggerfallWorkshop.Game.Doomerfall;

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
                if (DFCareer.IsRemovedSkill(skill))
                    continue; // Doomerfall: unused slots 11-12
                // Doomerfall: slots 4-10 (weapon skills) carry a marker, since classic data reads them as dead languages (DoomerfallSkillPowers)
                bool marked = DFCareer.IsLegacyLanguageSlot(i);
                EnchantmentSettings enchantment = new EnchantmentSettings()
                {
                    Version = 1,
                    EffectKey = EffectKey,
                    ClassicType = EnchantmentTypes.EnhancesSkill,
                    ClassicParam = (short)i,
                    CustomParam = marked ? DoomerfallSkillPowers.MarkerParam(skill) : null,
                    PrimaryDisplayName = GroupName,
                    SecondaryDisplayName = DaggerfallUnity.Instance.TextProvider.GetSkillName(skill),
                    EnchantCost = enchantCost,
                };

                enchantments.Add(enchantment);
            }

            return enchantments.ToArray();
        }

        /// <summary>
        /// Doomerfall: a dead monster language power (classic slots 4-12, no marker), from a soul or an old item, raises
        /// another skill from a fixed table (DoomerfallSkillPowers.LanguageTarget). It keeps its classic setting and cost.
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
                SecondaryDisplayName = DaggerfallUnity.Instance.TextProvider.GetSkillName(DoomerfallSkillPowers.LanguageTarget(skill)),
                EnchantCost = enchantCost,
            };
        }

        public override void Start(EntityEffectManager manager, DaggerfallEntityBehaviour caster = null)
        {
            base.Start(manager, caster);

            // Must have enchantment params
            if (EnchantmentParam == null)
                return;

            // Set skill mod
            // Doomerfall: a marked weapon skill, or a dead language's table target (DoomerfallSkillPowers)
            DFCareer.Skills skill = DoomerfallSkillPowers.SkillOf(EnchantmentParam.Value.ClassicParam, EnchantmentParam.Value.CustomParam);
            if (skill == DFCareer.Skills.None)
                return;
            SetSkillMod(skill, modAmount);
        }
    }
}