// Doomerfall test only (-dfenchantskillstest <log file>, with -dfsynctest): once in game, checks the Enhances Skill
// powers (DoomerfallSkillPowers): the item maker lists the weapon skills with their marker; every dead language power
// (classic slots 4-12), the Fire and Frost Daedra souls' forced power and the classic "of Venom Spitting" item raise
// their table skill; and a marked weapon skill power raises that skill. Live checks equip a ring carrying the power
// and read Daggerfall's live skill value. "MAP" lines are the mapping, compared across runs by
// tools/enchant_skills/run_enchant_skills.py.

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using DaggerfallConnect;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.MagicAndEffects;
using DaggerfallWorkshop.Game.MagicAndEffects.MagicEffects;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallEnchantSkillsTest : MonoBehaviour
    {
        DoomerfallPositionSync sync;
        string path;
        int passed, failed;

        internal static void Attach(GameObject host, DoomerfallPositionSync positionSync, string[] args)
        {
            int at = Array.IndexOf(args, "-dfenchantskillstest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            var test = host.AddComponent<DoomerfallEnchantSkillsTest>();
            test.sync = positionSync;
            test.path = args[at + 1];
            File.WriteAllText(test.path, "");
        }

        void Log(string s)
        {
            File.AppendAllText(path, s + "\n");
        }

        void Check(string what, bool ok, string detail)
        {
            if (ok) passed++; else failed++;
            Log(string.Format("{0} {1}: {2}", ok ? "PASS" : "FAIL", what, detail));
        }

        static PlayerEntity P { get { return GameManager.Instance.PlayerEntity; } }
        static string Name(DFCareer.Skills s) { return s == DFCareer.Skills.None ? "None" : DaggerfallUnity.Instance.TextProvider.GetSkillName(s); }

        IEnumerator Start()
        {
            while (!sync.InGame || !GameManager.HasInstance || P == null)
                yield return null;
            for (int i = 0; i < 30; i++)
                yield return null;
            Log("START");

            IEntityEffect enhances = GameManager.Instance.EntityEffectBroker.GetEffectTemplate(EnhancesSkill.EffectKey);
            IEntityEffect soulBound = GameManager.Instance.EntityEffectBroker.GetEffectTemplate(SoulBound.EffectKey);

            // Item maker list: every playable skill once; slots 4-10 carry the marker, the rest are classic.
            EnchantmentSettings[] listed = enhances.GetEnchantmentSettings();
            foreach (DFCareer.Skills s in DoomerfallSkillPowers.PlayableSkills())
            {
                EnchantmentSettings[] hits = listed.Where(e => e.ClassicParam == (short)s).ToArray();
                bool weapon = DFCareer.IsLegacyLanguageSlot((int)s);
                bool ok = hits.Length == 1 && hits[0].SecondaryDisplayName == Name(s)
                    && (weapon ? hits[0].CustomParam == DoomerfallSkillPowers.GunMarker + Name(s).Replace(" ", "") : string.IsNullOrEmpty(hits[0].CustomParam));
                Check("item maker lists " + Name(s), ok, hits.Length == 1 ? string.Format("'{0}' param '{1}'", hits[0].SecondaryDisplayName, hits[0].CustomParam) : hits.Length + " entries");
            }
            Check("item maker list size", listed.Length == DoomerfallSkillPowers.PlayableSkills().Count + 1, listed.Length + " entries (playable skills + Critical Strike)");

            // Dead languages, as an old item or classic save would carry them.
            for (int slot = (int)DFCareer.Skills.Shotguns; slot <= (int)DFCareer.Skills.Impish; slot++)
            {
                EnchantmentParam param = new EnchantmentParam { ClassicParam = (short)slot, CustomParam = string.Empty };
                DFCareer.Skills target = DoomerfallSkillPowers.SkillOf((short)slot, null);
                EnchantmentSettings? shown = enhances.GetEnchantmentSettings(param);
                Log(string.Format("MAP language slot {0} -> {1} ({2})", slot, (int)target, Name(target)));
                Check("language slot " + slot + " shows its target", shown.HasValue && shown.Value.SecondaryDisplayName == Name(target), shown.HasValue ? shown.Value.SecondaryDisplayName : "null");
                Check("language slot " + slot + " same twice", DoomerfallSkillPowers.SkillOf((short)slot, null) == target, Name(target));
                yield return LiveCheck("language slot " + slot, new[] { Legacy((short)slot) }, target);
            }

            // Souls that force a dead language.
            foreach (MobileTypes soul in new[] { MobileTypes.FireDaedra, MobileTypes.FrostDaedra })
            {
                ForcedEnchantmentSet? set = soulBound.GetForcedEnchantments(new EnchantmentParam { ClassicParam = (short)soul });
                ForcedEnchantment forced = set.Value.forcedEffects.First(f => f.key == EnhancesSkill.EffectKey);
                EnchantmentSettings shown = enhances.GetEnchantmentSettings(forced.param).Value;
                DFCareer.Skills target = DoomerfallSkillPowers.SkillOf(forced.param.ClassicParam, forced.param.CustomParam);
                Log(string.Format("MAP soul {0} -> {1} ({2})", soul, (int)target, Name(target)));
                Check(soul + " soul shows", shown.SecondaryDisplayName == Name(target), shown.SecondaryDisplayName);
                yield return LiveCheck(soul + " soul", new[] { shown }, target);
            }

            // Classic magic item templates that name a dead language (of Venom Spitting).
            MagicItemTemplate[] regular = DaggerfallUnity.Instance.ItemHelper.MagicItemTemplates.Where(t => t.type == MagicItemTypes.RegularMagicItem).ToArray();
            for (int i = 0; i < regular.Length; i++)
            {
                DaggerfallEnchantment old = regular[i].enchantments.FirstOrDefault(e => e.type == EnchantmentTypes.EnhancesSkill && DFCareer.IsLegacyLanguageSlot(e.param));
                if (old.type != EnchantmentTypes.EnhancesSkill)
                    continue;
                DaggerfallUnityItem made = ItemBuilder.CreateRegularMagicItem(i, P.Level, P.Gender, P.Race);
                made.IdentifyItem();
                DFCareer.Skills target = DoomerfallSkillPowers.SkillOf(old.param, null);
                string powers = string.Join(" | ", made.GetMacroDataSource().MagicPowers(DaggerfallConnect.Arena2.TextFile.Formatting.Nothing)
                    .Where(t => !string.IsNullOrEmpty(t.text)).Select(t => t.text).ToArray());
                Log(string.Format("MAP item {0} -> {1} ({2})", regular[i].name, (int)target, Name(target)));
                Check(regular[i].name + " powers text", powers.Contains(Name(target)), powers);
                yield return LiveCheck(regular[i].name, new[] { Legacy(old.param) }, target);
            }

            // New marked weapon skill powers, as the item maker writes them.
            foreach (EnchantmentSettings e in listed.Where(x => !string.IsNullOrEmpty(x.CustomParam)))
            {
                DFCareer.Skills s = (DFCareer.Skills)e.ClassicParam;
                yield return LiveCheck("marked " + Name(s), new[] { e }, s);
            }

            Log(string.Format("DONE passed {0} failed {1}", passed, failed));
        }

        static EnchantmentSettings Legacy(short param)
        {
            return new EnchantmentSettings { EffectKey = EnhancesSkill.EffectKey, ClassicType = EnchantmentTypes.EnhancesSkill, ClassicParam = param };
        }

        // Equips a ring carrying the powers and checks the target's live value rose by 15 and no other skill changed.
        IEnumerator LiveCheck(string what, EnchantmentSettings[] powers, DFCareer.Skills target)
        {
            short[] before = new short[(int)DFCareer.Skills.Count];
            for (int i = 0; i < before.Length; i++)
                before[i] = P.Skills.GetLiveSkillValue(i);
            DaggerfallUnityItem ring = ItemBuilder.CreateItem(ItemGroups.Jewellery, (int)Jewellery.Ring);
            ring.SetEnchantments(powers, P);
            ring.IdentifyItem();
            P.Items.AddItem(ring);
            P.ItemEquipTable.EquipItem(ring, true, false);
            yield return null;
            Refresh();
            List<string> changed = Changes(before);
            string expected = Name(target) + " +15";
            Check(what + " raises " + Name(target), changed.Count == 1 && changed[0] == expected,
                changed.Count == 0 ? "no change" : string.Join(", ", changed.ToArray()));
            P.ItemEquipTable.UnequipItem(ring.EquipSlot); // the slot overload stops the enchantments; UnequipItem(item) does not
            P.Items.RemoveItem(ring);
            yield return null;
            Refresh();
            Check(what + " ring removed", Changes(before).Count == 0, string.Join(", ", Changes(before).ToArray()));
        }

        // Daggerfall refreshes effect mods only while the game is in play (EntityEffectManager.Update), which a test
        // launch sitting in Doom's menu is not; do the same two steps here.
        static void Refresh()
        {
            EntityEffectManager manager = GameManager.Instance.PlayerEffectManager;
            typeof(EntityEffectManager).GetMethod("RemovePendingBundles", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(manager, null);
            manager.UpdateEntityMods();
        }

        static List<string> Changes(short[] before)
        {
            var changed = new List<string>();
            for (int i = 0; i < before.Length; i++)
            {
                int d = P.Skills.GetLiveSkillValue(i) - before[i];
                if (d != 0)
                    changed.Add(string.Format("{0} {1:+0;-0}", Name((DFCareer.Skills)i), d));
            }
            return changed;
        }
    }
}
