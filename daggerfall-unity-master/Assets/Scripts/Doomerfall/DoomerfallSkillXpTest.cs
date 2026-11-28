// Doomerfall test only, run by tools/skillxp/skillxp.py: -dfskillxptest <log>.
// In play it waits for Skill XP from Doom's real damage reports (the harness hurts monsters and a townsperson), logs the
// skills menu Doom opens through its key (-dfuitest, menu 15) with the perk lines it shows, then closes it. Then it
// opens the character sheet, clicks its SKILLS button, grants test XP (logged as such), buys points of the first primary
// skill with the menu's BUY POINT button until a level-up is ready, closes the menu so the sheet runs the level-up,
// saves with Daggerfall's own save, spoils the pool and the skill, loads that save and logs what came back.

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallSkillXpTest : MonoBehaviour
    {
        string path;
        DoomerfallPositionSync sync;

        // DoomerfallBridge.Init. Does nothing without the flag.
        internal static void Attach(GameObject host, DoomerfallPositionSync positionSync, string[] args)
        {
            int i = Array.IndexOf(args, "-dfskillxptest");
            if (i < 0 || i + 1 >= args.Length)
                return;
            var t = host.AddComponent<DoomerfallSkillXpTest>();
            t.path = args[i + 1];
            t.sync = positionSync;
        }

        void Log(string s)
        {
            File.AppendAllText(path, string.Format("{0:F1} {1}\n", Time.realtimeSinceStartup, s));
        }

        static PlayerEntity P { get { return GameManager.Instance.PlayerEntity; } }
        static IUserInterfaceWindow Top { get { return DaggerfallUI.UIManager.TopWindow; } }

        IEnumerator Start()
        {
            while (!sync.InGame || sync.Phase != Dfb.DF_PHASE_PLAY || !GameManager.HasInstance || P == null)
                yield return null;
            Log(string.Format("SXSTART pool {0} level {1} class {2}", P.SkillXp, P.Level, P.Career.Name));

            // The menu from Doom's key.
            float until = Time.realtimeSinceStartup + 90;
            while (!(Top is DoomerfallSkillsWindow) && Time.realtimeSinceStartup < until)
                yield return null;
            if (Top is DoomerfallSkillsWindow)
            {
                yield return new WaitForSecondsRealtime(2.5f); // Doom's -dfuitest screenshot
                LogMenu("SXKEYMENU");
                ((DoomerfallSkillsWindow)Top).CloseWindow();
            }
            else
                Log("SXKEYMENU none");

            // XP from Doom's damage reports.
            until = Time.realtimeSinceStartup + 60;
            while (P.SkillXp <= 0 && Time.realtimeSinceStartup < until)
                yield return null;
            yield return new WaitForSecondsRealtime(3f); // the rest of the reports
            Log(string.Format("SXEARNED pool {0} uses {1}", P.SkillXp, string.Join(",", Array.ConvertAll(P.SkillUses, u => u.ToString()))));

            // The sheet's button.
            while (!(Top is DaggerfallHUD))
                yield return null;
            DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenCharacterSheetWindow);
            until = Time.realtimeSinceStartup + 20;
            while (!(Top is DaggerfallCharacterSheetWindow) && Time.realtimeSinceStartup < until)
                yield return null;
            var sheet = Top as DaggerfallCharacterSheetWindow;
            Button skillsButton = sheet != null ? Find<Button>(sheet.NativePanel, b => b.Label.Text == "SKILLS") : null;
            Log("SXSHEET " + (sheet != null) + " button " + (skillsButton != null));
            if (skillsButton == null)
                yield break;
            yield return new WaitForSecondsRealtime(1.5f);
            skillsButton.TriggerMouseClick();
            yield return null;
            var menu = Top as DoomerfallSkillsWindow;
            Log("SXBUTTONMENU " + (menu != null));
            if (menu == null)
                yield break;

            yield return EarnedPoint(menu);

            // Buy points of the first primary skill until a level-up is ready.
            DFCareer.Skills skill = P.GetPrimarySkills()[0];
            int levelBefore = P.Level, startValue = P.Skills.GetPermanentSkillValue(skill), earned = P.SkillXp;
            ListBox list = Find<ListBox>(menu.NativePanel, l => true);
            string name = DaggerfallUnity.Instance.TextProvider.GetSkillName(skill);
            for (int i = 0; i < list.Count; i++)
                if (list.GetItem(i).textLabel.Text.EndsWith("  " + name))
                    list.SelectIndex(i);
            yield return null;
            LogMenu("SXSELECTED");
            // Line Daggerfall's level formula up with the current level first, as DoomerfallLevelUpTest does: the blank
            // test character's starting sum (0) would otherwise report a level-up at the first check, bought or not.
            P.SetCurrentLevelUpSkillSum();
            P.StartingLevelUpSkillSum = P.CurrentLevelUpSkillSum + 28 - 15 * P.Level;
            bool staleReady = P.ReadyToLevelUp;
            P.ReadyToLevelUp = false;
            Log(string.Format("SXBASELINE level {0} formula {1} sum {2} start {3} ready {4} (was {5})", P.Level, Formula(), P.CurrentLevelUpSkillSum,
                P.StartingLevelUpSkillSum, P.ReadyToLevelUp, staleReady));
            Button buy = Find<Button>(menu.NativePanel, b => b.Label.Text == "BUY POINT");
            int price = DoomerfallSkillXp.Price(P, skill);
            buy.TriggerMouseClick(); // with earned XP only: refused unless the pool covers the price
            Log(string.Format("SXEARNEDBUY price {0} pool {1} skill {2}", price, P.SkillXp, P.Skills.GetPermanentSkillValue(skill)));
            int grant = 0, bought = 0;
            while (!P.ReadyToLevelUp && bought < 40)
            {
                int need = DoomerfallSkillXp.Price(P, skill);
                if (P.SkillXp < need)
                {
                    grant += need - P.SkillXp;
                    P.SkillXp = need; // test grant
                }
                int before = P.Skills.GetPermanentSkillValue(skill);
                buy.TriggerMouseClick();
                if (P.Skills.GetPermanentSkillValue(skill) == before)
                    break;
                bought++;
                Log(string.Format("SXBUY {0} -> {1} for {2}, pool {3}, sum {4}, formula {5}, ready {6}", name, before + 1, need, P.SkillXp,
                    P.CurrentLevelUpSkillSum, Formula(), P.ReadyToLevelUp));
                yield return null;
            }
            Log(string.Format("SXBOUGHT {0} points of {1} ({2} -> {3}), test grant {4} XP, earned {5}, ready {6}", bought, name, startValue,
                P.Skills.GetPermanentSkillValue(skill), grant, earned, P.ReadyToLevelUp));
            for (int i = 0; i < list.Count; i++)
                if (list.GetItem(i).textLabel.Text.EndsWith("  Jumping"))
                    list.SelectIndex(i);
            yield return null;
            LogMenu("SXPERKS");
            yield return new WaitForSecondsRealtime(1f);
            menu.CloseWindow();
            yield return new WaitForSecondsRealtime(1f);
            Log(string.Format("SXLEVEL before {0} after {1} top {2}", levelBefore, P.Level, Top.GetType().Name));
            yield return LevelingRefused();

            // Save, spoil, load.
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            P.SkillXp += 777; // test grant, so the saved pool is not zero
            int poolSaved = P.SkillXp, skillSaved = P.Skills.GetPermanentSkillValue(skill), levelSaved = P.Level;
            string character = P.Name;
            saves.Save(character, "SkillXpTest");
            yield return new WaitForSecondsRealtime(3f);
            P.SkillXp = 12345;
            P.Skills.SetPermanentSkillValue(skill, 5);
            saves.EnumerateSaves();
            SaveLoadManager.OnLoadEventHandler loaded = null;
            bool done = false;
            loaded = data =>
            {
                SaveLoadManager.OnLoad -= loaded;
                done = true;
            };
            SaveLoadManager.OnLoad += loaded;
            Log(string.Format("SXSAVED pool {0} {1} {2} level {3}; loading", poolSaved, name, skillSaved, levelSaved));
            saves.Load(character, "SkillXpTest");
            until = Time.realtimeSinceStartup + 30;
            while (!done && Time.realtimeSinceStartup < until)
                yield return null;
            Log(string.Format("SXLOADED {0} pool {1} {2} {3} level {4}", done, P.SkillXp, name, P.Skills.GetPermanentSkillValue(skill), P.Level));
            yield return SecondLevel(skill, name);
            Log("SXDONE");
        }

        // One point bought with Skill XP earned from Doom's damage only (no test grant): the cheapest buyable skill,
        // selected in the menu's list and bought with its BUY POINT button. The menu's pool line is logged around it.
        IEnumerator EarnedPoint(DoomerfallSkillsWindow menu)
        {
            DFCareer.Skills cheapest = DFCareer.Skills.None;
            for (DFCareer.Skills s = 0; s < DFCareer.Skills.Count; s++)
                if (DoomerfallSkillXp.Buyable(s) && DoomerfallSkillXp.Capped(P, s) == null &&
                    (cheapest == DFCareer.Skills.None || DoomerfallSkillXp.Price(P, s) < DoomerfallSkillXp.Price(P, cheapest)))
                    cheapest = s;
            ListBox list = Find<ListBox>(menu.NativePanel, l => true);
            string name = DaggerfallUnity.Instance.TextProvider.GetSkillName(cheapest);
            for (int i = 0; i < list.Count; i++)
                if (list.GetItem(i).textLabel.Text.EndsWith("  " + name))
                    list.SelectIndex(i);
            yield return null;
            LogMenu("SXEARNEDMENU");
            int pool = P.SkillXp, price = DoomerfallSkillXp.Price(P, cheapest), before = P.Skills.GetPermanentSkillValue(cheapest);
            Find<Button>(menu.NativePanel, b => b.Label.Text == "BUY POINT").TriggerMouseClick();
            yield return null;
            LogMenu("SXEARNEDAFTER");
            Log(string.Format("SXEARNEDPOINT {0} {1} -> {2}, price {3}, pool {4} -> {5}, earned only {6}", name, before,
                P.Skills.GetPermanentSkillValue(cheapest), price, pool, P.SkillXp, pool >= price));
        }

        // While the sheet is leveling (stat rollout showing), its SKILLS button must not open the menu, so a purchase
        // cannot start a second level-up that would re-roll the attribute points being assigned.
        IEnumerator LevelingRefused()
        {
            var sheet = Top as DaggerfallCharacterSheetWindow;
            Button skillsButton = sheet != null ? Find<Button>(sheet.NativePanel, b => b.Label.Text == "SKILLS") : null;
            if (skillsButton == null)
            {
                Log("SXLEVELINGREFUSED no sheet");
                yield break;
            }
            int level = P.Level;
            P.SkillXp += 100000; // test grant: enough to buy through another threshold if the menu opened
            skillsButton.TriggerMouseClick();
            yield return null;
            var box = Top as DaggerfallMessageBox;
            Log(string.Format("SXLEVELINGREFUSED menu {0} message {1} level {2} -> {3}", Top is DoomerfallSkillsWindow, box != null, level, P.Level));
            if (Top is DoomerfallSkillsWindow)
                ((DoomerfallSkillsWindow)Top).CloseWindow();
            else if (box != null)
                box.CloseWindow();
            yield return null;
            P.SkillXp -= 100000;
            Log(string.Format("SXLEVELINGAFTER top {0} level {1}", Top.GetType().Name, P.Level));

            // Doom's close key on the leveling sheet: DoomerfallUi.OnClose pops to the HUD without the sheet's own
            // close, so the points stay unassigned in its rollout. Then the menu opens as Doom's skills key opens it
            // (DoomerfallUi, UI_SKILLS) and tries to buy through another threshold; buying must wait.
            var rollout = typeof(DaggerfallCharacterSheetWindow).GetField("statsRollout", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(sheet) as StatsRollout;
            int poolBefore = rollout.BonusPool, workingBefore = StatSum(rollout.WorkingStats);
            DaggerfallUI.Instance.PopToHUD();
            yield return null;
            DaggerfallUI.UIManager.PushWindow(new DoomerfallSkillsWindow(DaggerfallUI.UIManager));
            yield return null;
            var menu = Top as DoomerfallSkillsWindow;
            DFCareer.Skills skill = P.GetPrimarySkills()[0];
            int skillBefore = P.Skills.GetPermanentSkillValue(skill);
            P.SkillXp += 100000; // test grant
            Button buy = menu != null ? Find<Button>(menu.NativePanel, b => b.Label.Text == "BUY POINT") : null;
            ListBox list = menu != null ? Find<ListBox>(menu.NativePanel, l => true) : null;
            string skillName = DaggerfallUnity.Instance.TextProvider.GetSkillName(skill);
            for (int i = 0; list != null && i < list.Count; i++)
                if (list.GetItem(i).textLabel.Text.EndsWith("  " + skillName))
                    list.SelectIndex(i);
            yield return null;
            for (int i = 0; buy != null && i < 30; i++)
                buy.TriggerMouseClick();
            LogMenu("SXPENDINGMENU");
            Log(string.Format("SXPENDINGBUY menu {0} {1} {2} -> {3}, ready {4}, level {5}", menu != null, skillName, skillBefore,
                P.Skills.GetPermanentSkillValue(skill), P.ReadyToLevelUp, P.Level));
            P.SkillXp -= 100000;
            if (menu != null)
                menu.CloseWindow();
            yield return null;
            DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenCharacterSheetWindow);
            float until = Time.realtimeSinceStartup + 10;
            while (!(Top is DaggerfallCharacterSheetWindow) && Time.realtimeSinceStartup < until)
                yield return null;
            Log(string.Format("SXPENDINGKEPT bonus {0} -> {1}, working stat sum {2} -> {3}, level {4}, top {5}", poolBefore, rollout.BonusPool,
                workingBefore, StatSum(rollout.WorkingStats), P.Level, Top.GetType().Name));

            // Assign the bonus points as the player would (in the rollout's working stats), close the sheet, and check
            // that the assigned points reached the character.
            int pool = rollout.BonusPool, before = StatSum(P.Stats), left = pool;
            for (int i = 0; i < DaggerfallStats.Count && left > 0; i++)
            {
                int v = rollout.WorkingStats.GetPermanentStatValue(i), add = Math.Min(left, 100 - v);
                rollout.WorkingStats.SetPermanentStatValue(i, v + add);
                left -= add;
            }
            rollout.BonusPool = left;
            sheet.CancelWindow();
            yield return null;
            Log(string.Format("SXASSIGNED bonus {0}, stat sum {1} -> {2}, top {3}", pool, before, StatSum(P.Stats), Top.GetType().Name));
        }

        // After load (the first level committed): open the sheet, click SKILLS, buy through the next threshold and let
        // the sheet run the second level-up from bought points.
        IEnumerator SecondLevel(DFCareer.Skills skill, string name)
        {
            float until = Time.realtimeSinceStartup + 20;
            while (!(Top is DaggerfallHUD) && Time.realtimeSinceStartup < until)
                yield return null;
            DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenCharacterSheetWindow);
            until = Time.realtimeSinceStartup + 20;
            while (!(Top is DaggerfallCharacterSheetWindow) && Time.realtimeSinceStartup < until)
                yield return null;
            var sheet = Top as DaggerfallCharacterSheetWindow;
            Button skillsButton = sheet != null ? Find<Button>(sheet.NativePanel, b => b.Label.Text == "SKILLS") : null;
            if (skillsButton == null)
            {
                Log("SXSECOND no sheet");
                yield break;
            }
            yield return null;
            skillsButton.TriggerMouseClick();
            yield return null;
            var menu = Top as DoomerfallSkillsWindow;
            P.SetCurrentLevelUpSkillSum();
            Log(string.Format("SXSECONDSTART menu {0} level {1} formula {2} ready {3}", menu != null, P.Level, Formula(), P.ReadyToLevelUp));
            if (menu == null)
                yield break;
            ListBox list = Find<ListBox>(menu.NativePanel, l => true);
            for (int i = 0; i < list.Count; i++)
                if (list.GetItem(i).textLabel.Text.EndsWith("  " + name))
                    list.SelectIndex(i);
            yield return null;
            Button buy = Find<Button>(menu.NativePanel, b => b.Label.Text == "BUY POINT");
            int level = P.Level, bought = 0, grant = 0, start = P.Skills.GetPermanentSkillValue(skill);
            while (!P.ReadyToLevelUp && bought < 40)
            {
                int need = DoomerfallSkillXp.Price(P, skill);
                if (P.SkillXp < need)
                {
                    grant += need - P.SkillXp;
                    P.SkillXp = need; // test grant
                }
                int before = P.Skills.GetPermanentSkillValue(skill);
                buy.TriggerMouseClick();
                if (P.Skills.GetPermanentSkillValue(skill) == before)
                    break;
                bought++;
            }
            Log(string.Format("SXSECONDBOUGHT {0} points ({1} -> {2}), test grant {3}, sum {4}, formula {5}, ready {6}", bought, start,
                P.Skills.GetPermanentSkillValue(skill), grant, P.CurrentLevelUpSkillSum, Formula(), P.ReadyToLevelUp));
            menu.CloseWindow();
            yield return new WaitForSecondsRealtime(1f);
            Log(string.Format("SXSECONDLEVEL before {0} after {1} top {2}", level, P.Level, Top.GetType().Name));
        }

        static int StatSum(DaggerfallStats stats)
        {
            int sum = 0;
            for (int i = 0; i < DaggerfallStats.Count; i++)
                sum += stats.GetPermanentStatValue(i);
            return sum;
        }

        static int Formula()
        {
            return FormulaHelper.CalculatePlayerLevel(P.StartingLevelUpSkillSum, P.CurrentLevelUpSkillSum);
        }

        void LogMenu(string tag)
        {
            var menu = Top as DoomerfallSkillsWindow;
            if (menu == null)
                return;
            var texts = new List<string>();
            Collect(menu.NativePanel, texts);
            Log(tag + " " + string.Join(" | ", texts));
        }

        static void Collect(BaseScreenComponent c, List<string> texts)
        {
            if (c is TextLabel && !string.IsNullOrEmpty(((TextLabel)c).Text))
                texts.Add(((TextLabel)c).Text.Replace("\n", " "));
            if (c is Panel)
                foreach (BaseScreenComponent child in ((Panel)c).Components)
                    Collect(child, texts);
        }

        static T Find<T>(BaseScreenComponent c, Predicate<T> match) where T : BaseScreenComponent
        {
            if (c is T && match((T)c))
                return (T)c;
            if (c is Panel)
                foreach (BaseScreenComponent child in ((Panel)c).Components)
                {
                    T found = Find(child, match);
                    if (found != null)
                        return found;
                }
            return null;
        }
    }
}
