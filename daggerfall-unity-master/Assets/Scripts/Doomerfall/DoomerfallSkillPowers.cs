// Doomerfall: which skill an "Enhances <skill>" power raises (owner, 2026-11-27, gamedesign/decisions/20261127-qa-batch11-owner.md).
//
// Slots 4-10 hold the weapon skills (Shotguns ... Melee) but classic data (items, souls, old saves) still reads them,
// and slots 11-12, as the removed monster languages. So:
// - A new item maker power for a skill in slots 4-10 carries a marker: it is stored as a custom enchantment whose
//   param is GunMarker + the skill's name (for example "DoomerfallSkill:Shotguns"). Only these name the new skills.
// - A classic power in slots 4-12 (no marker) is a dead language. Each one raises another playable skill instead, from
//   a fixed table, so the same item gives the same skill every time. The table spreads the nine languages evenly over
//   the playable skills (DoomerfallSkillXp.Buyable): language k takes playable skill floor(k * playable / 9).

using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.MagicAndEffects;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public static class DoomerfallSkillPowers
    {
        public const string GunMarker = "DoomerfallSkill:";

        const int LanguageCount = (int)DFCareer.Skills.Impish - (int)DFCareer.Skills.Shotguns + 1; // the nine classic languages, slots 4-12

        static DFCareer.Skills[] languageTargets;

        /// <summary>The skills a player can have and buy, in slot order.</summary>
        public static List<DFCareer.Skills> PlayableSkills()
        {
            var list = new List<DFCareer.Skills>();
            for (int i = 0; i < (int)DFCareer.Skills.Count; i++)
                if (DoomerfallSkillXp.Buyable((DFCareer.Skills)i))
                    list.Add((DFCareer.Skills)i);
            return list;
        }

        /// <summary>The skill a dead language power (classic slot 4-12, no marker) raises instead.</summary>
        public static DFCareer.Skills LanguageTarget(DFCareer.Skills languageSlot)
        {
            if (languageTargets == null)
            {
                List<DFCareer.Skills> playable = PlayableSkills();
                var targets = new DFCareer.Skills[LanguageCount];
                for (int k = 0; k < LanguageCount; k++)
                    targets[k] = playable[k * playable.Count / LanguageCount];
                languageTargets = targets;
            }
            return languageTargets[(int)languageSlot - (int)DFCareer.Skills.Shotguns];
        }

        /// <summary>The marker param of a new item maker power for a skill in slots 4-10.</summary>
        public static string MarkerParam(DFCareer.Skills skill)
        {
            // Fixed names: Skills.ToString() may return an obsolete alias (slots 4-10 share values with the old languages).
            return GunMarker + MarkerNames[(int)skill - (int)DFCareer.Skills.Shotguns];
        }

        static readonly string[] MarkerNames = { "Shotguns", "Automatics", "Explosives", "Pistols", "Rifles", "EnergyWeapons", "Melee" };

        /// <summary>The weapon skill a marker param names, or None.</summary>
        public static DFCareer.Skills MarkedSkill(string customParam)
        {
            if (string.IsNullOrEmpty(customParam) || !customParam.StartsWith(GunMarker))
                return DFCareer.Skills.None;
            for (int i = (int)DFCareer.Skills.Shotguns; i <= (int)DFCareer.Skills.Melee; i++)
                if (customParam == MarkerParam((DFCareer.Skills)i))
                    return (DFCareer.Skills)i;
            return DFCareer.Skills.None;
        }

        /// <summary>
        /// Adds an item's marked weapon skill powers to its "%mpw" power list. Classic code lists only classic powers,
        /// and these are stored as custom enchantments.
        /// </summary>
        public static void AddMarkedPowers(DaggerfallUnityItem item, List<TextFile.Token> tokens, TextFile.Formatting format)
        {
            if (item == null || !item.HasCustomEnchantments)
                return;
            foreach (CustomEnchantment enchantment in item.CustomEnchantments)
            {
                if (enchantment.EffectKey != EnchantmentTypes.EnhancesSkill.ToString())
                    continue;
                DFCareer.Skills skill = MarkedSkill(enchantment.CustomParam);
                if (skill == DFCareer.Skills.None)
                    continue;
                string power = TextManager.Instance.GetLocalizedTextList("itemPowers")[(int)EnchantmentTypes.EnhancesSkill];
                tokens.Add(TextFile.CreateTextToken(power + " " + DaggerfallUnity.Instance.TextProvider.GetSkillName(skill)));
                tokens.Add(TextFile.CreateFormatToken(format));
            }
        }

        /// <summary>
        /// The skill an Enhances Skill power raises: a marked weapon skill, a dead language's table target, or the
        /// classic skill. None for a param this does not recognise.
        /// </summary>
        public static DFCareer.Skills SkillOf(short classicParam, string customParam)
        {
            if (!string.IsNullOrEmpty(customParam))
                return MarkedSkill(customParam);
            if (classicParam < 0 || classicParam >= (short)DFCareer.Skills.Count)
                return DFCareer.Skills.None;
            DFCareer.Skills skill = (DFCareer.Skills)classicParam;
            return DFCareer.IsLegacyLanguageSlot(classicParam) ? LanguageTarget(skill) : skill;
        }
    }
}
