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
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
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
                Log(string.Format("SXBUY {0} -> {1} for {2}, pool {3}, ready {4}", name, before + 1, need, P.SkillXp, P.ReadyToLevelUp));
                yield return null;
            }
            Log(string.Format("SXBOUGHT {0} points of {1} ({2} -> {3}), test grant {4} XP, earned {5}, ready {6}", bought, name, startValue,
                P.Skills.GetPermanentSkillValue(skill), grant, earned, P.ReadyToLevelUp));
            yield return new WaitForSecondsRealtime(1f);
            menu.CloseWindow();
            yield return new WaitForSecondsRealtime(1f);
            Log(string.Format("SXLEVEL before {0} after {1} top {2}", levelBefore, P.Level, Top.GetType().Name));

            // Save, spoil, load.
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
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
            Log("SXDONE");
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
