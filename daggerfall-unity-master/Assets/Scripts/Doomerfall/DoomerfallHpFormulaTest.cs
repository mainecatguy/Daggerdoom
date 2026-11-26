// Doomerfall test only (-dfhpformulatest <output folder>, with -dfsynctest): checks DoomerfallEndurance against
// gamedesign/hp.md, then drives a live character through a new game, a level-up, Endurance changes, Fortify and
// Drain Endurance effects, and an older save, logging each Daggerfall max HP so the launch script can compare what Doom shows. Saves go to the portable
// install's private folder. Also screenshots the custom class editor.

using System;
using System.Collections;
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.MagicAndEffects;
using DaggerfallWorkshop.Game.Player;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHpFormulaTest : MonoBehaviour
    {
        const string SaveName = "HpFormulaTest";
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        string dir;
        int passed, failed;
        bool loaded;
        int loadedBreath;

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfhpformulatest");
            if (at < 0)
                return;
            var test = owner.gameObject.AddComponent<DoomerfallHpFormulaTest>();
            test.bridge = owner;
            test.sync = positionSync;
            test.dir = at + 1 < args.Length && !args[at + 1].StartsWith("-") ? args[at + 1] : Application.temporaryCachePath;
            test.StartCoroutine(test.Run());
        }

        void Check(string what, bool ok, string detail)
        {
            if (ok) passed++; else failed++;
            bridge.LogLine(string.Format("hp formula test: {0} {1}: {2}", ok ? "PASS" : "FAIL", what, detail));
        }

        void Expect(string what, int got, int expected)
        {
            Check(what, got == expected, string.Format("got {0}, expected {1}", got, expected));
        }

        static IEnumerator Frames(int n)
        {
            for (int i = 0; i < n; i++)
                yield return null;
        }

        static PlayerEntity Player { get { return GameManager.Instance.PlayerEntity; } }

        // Daggerfall's numbers for Doom's side of the comparison.
        void Report(string step)
        {
            PlayerEntity p = Player;
            bridge.LogLine(string.Format("hp formula test: state {0}: level {1}, endurance {2} live {3} (max {4}), hp {5}/{6}", step, p.Level,
                p.Stats.PermanentEndurance, p.Stats.LiveEndurance, p.Stats.GetMaxPermanentValue(DFCareer.Stats.Endurance), p.CurrentHealth, p.MaxHealth));
        }

        IEnumerator Run()
        {
            while (!sync.InGame)
                yield return null;
            yield return Frames(10);
            if (!DaggerfallUnityApplication.IsPortableInstall)
            {
                bridge.LogLine("error: -dfhpformulatest needs a portable install");
                yield break;
            }

            CheckFormula();
            CheckClassBonus();
            // Doom must be playing its map, so its pawn exists to follow each max HP (DRLA loads slower).
            float doomDeadline = Time.unscaledTime + 30f;
            DfbUzState peer;
            do
            {
                yield return null;
                bridge.ReadPeerState(out peer);
            } while (peer.uzPhase != Dfb.UZ_PHASE_PLAY && Time.unscaledTime < doomDeadline);
            yield return new WaitForSecondsRealtime(1f);
            Check("Doom is playing", peer.uzPhase == Dfb.UZ_PHASE_PLAY, "phase " + peer.uzPhase);
            yield return NewCharacter();
            yield return LevelAndEndurance();
            yield return EnduranceEffects();
            yield return OlderSave();
            yield return CustomClassShot();
            bridge.LogLine(string.Format("hp formula test: finished, {0} passed, {1} failed", passed, failed));
        }

        void CheckFormula()
        {
            // gamedesign/hp.md: 50 + END x (level + 14) / 15. Level 1 and 20 are the design's own examples.
            int[] endurance = { 30, 50, 75, 100 };
            int[,] expected = { { 80, 98, 118 }, { 100, 130, 163 }, { 125, 170, 220 }, { 150, 210, 277 } };
            int[] levels = { 1, 10, 20 };
            for (int e = 0; e < endurance.Length; e++)
                for (int l = 0; l < levels.Length; l++)
                    Expect(string.Format("formula END {0} level {1}", endurance[e], levels[l]), DoomerfallEndurance.MaxHealth(levels[l], endurance[e]), expected[e, l]);
        }

        void CheckClassBonus()
        {
            var classes = new[] { ClassCareers.Mage, ClassCareers.Warrior, ClassCareers.Barbarian };
            int[] bonus = { -2, 12, 17 };
            for (int i = 0; i < classes.Length; i++)
                CheckClass(classes[i].ToString(), DaggerfallEntity.GetClassCareerTemplate(classes[i]), bonus[i]);
            foreach (int hp in new[] { 4, 30 })
            {
                var custom = new DFCareer { Name = "Custom", HitPointsPerLevel = hp, Strength = 50, Intelligence = 50, Willpower = 50,
                    Agility = 50, Endurance = 50, Personality = 50, Speed = 50, Luck = 50 };
                CheckClass("custom " + hp + " hp per level", custom, hp - 8);
            }
        }

        void CheckClass(string name, DFCareer career, int bonus)
        {
            Expect(name + " bonus", DoomerfallEndurance.ClassBonus(career), bonus);
            DaggerfallStats stats = CharacterDocument.GetClassBaseStats(career);
            int baseEnd = stats.PermanentEndurance;
            DoomerfallEndurance.AddCreationBonus(stats, career);
            Expect(name + " start endurance", stats.PermanentEndurance, baseEnd + bonus);
            Expect(name + " max endurance", stats.GetMaxPermanentValue(DFCareer.Stats.Endurance), 100 + bonus);
            Expect(name + " max strength stays", stats.GetMaxPermanentValue(DFCareer.Stats.Strength), 100);
            Check(name + " bonus kept by a copy", stats.Clone().GetMaxPermanentValue(DFCareer.Stats.Endurance) == 100 + bonus && stats.Clone().DoomerfallEnduranceBonus, "");

            // The creation roll window: class base + 0..10 + bonus, and its spinner stops at the maximum.
            var rollout = new StatsRollout();
            rollout.Reroll(career);
            int rolled = rollout.StartingStats.PermanentEndurance;
            Check(name + " rolled endurance", rolled >= baseEnd + bonus && rolled <= baseEnd + 10 + bonus, string.Format("{0} in {1}..{2}", rolled, baseEnd + bonus, baseEnd + 10 + bonus));

            // Live Endurance (Fortify) is capped at the same maximum; level-up points stop there (IsAllMax).
            DaggerfallStats full = stats.Clone();
            for (int s = 0; s < DaggerfallStats.Count; s++)
                full.SetPermanentStatValue(s, full.GetMaxPermanentValue((DFCareer.Stats)s));
            Check(name + " all at max", full.IsAllMax(), "endurance " + full.PermanentEndurance);
            int[] mods = new int[DaggerfallStats.Count];
            mods[(int)DFCareer.Stats.Endurance] = 20;
            full.AssignMods(mods, new int[DaggerfallStats.Count]);
            Expect(name + " live endurance capped", full.LiveEndurance, 100 + bonus);
        }

        IEnumerator NewCharacter()
        {
            DFCareer warrior = DaggerfallEntity.GetClassCareerTemplate(ClassCareers.Warrior);
            var rollout = new StatsRollout();
            rollout.Reroll(warrior);
            var doc = new CharacterDocument { name = "HpFormula", career = warrior };
            doc.startingStats = rollout.StartingStats.Clone();
            doc.workingStats = rollout.WorkingStats.Clone();
            var start = FindObjectOfType<StartGameBehaviour>();
            start.CharacterDocument = doc;
            start.StartMethod = StartGameBehaviour.StartMethods.NewCharacter;
            float deadline = Time.unscaledTime + 10f;
            while ((Player.Name != "HpFormula" || !sync.InGame) && Time.unscaledTime < deadline)
                yield return null;
            GameManager.Instance.PauseGame(false);
            yield return new WaitForSecondsRealtime(2f);
            PlayerEntity p = Player;
            Expect("new warrior endurance includes +12", p.Stats.PermanentEndurance, doc.workingStats.PermanentEndurance);
            Expect("new warrior max hp", p.MaxHealth, 50 + p.Stats.PermanentEndurance);
            Expect("new warrior starts at full hp", p.CurrentHealth, p.MaxHealth);
            Report("new character");
        }

        IEnumerator LevelAndEndurance()
        {
            PlayerEntity p = Player;
            p.SetHealth(p.MaxHealth - 10);
            yield return Frames(3);
            int oldMax = p.MaxHealth, oldHp = p.CurrentHealth;
            // The real character sheet's level-up. Its HP label is written in the same call as the level-up, so it
            // must already show the new HP.
            p.ReadyToLevelUp = true;
            var sheet = new DaggerfallCharacterSheetWindow(DaggerfallUI.UIManager);
            DaggerfallUI.UIManager.PushWindow(sheet);
            yield return Frames(2);
            var labelField = typeof(DaggerfallCharacterSheetWindow).GetField("healthLabel", BindingFlags.NonPublic | BindingFlags.Instance);
            string shown = ((TextLabel)labelField.GetValue(sheet)).Text;
            Expect("level-up through the character sheet", p.Level, 2);
            int max = DoomerfallEndurance.MaxHealth(p.Level, p.Stats.PermanentEndurance);
            Expect("level-up max hp", p.MaxHealth, max);
            Expect("level-up raises hp by the gain", p.CurrentHealth, oldHp + (max - oldMax));
            Check("level-up sheet shows the new hp", shown == string.Format("{0}/{1}", oldHp + (max - oldMax), max), "label \"" + shown + "\"");
            if (DaggerfallUI.UIManager.TopWindow == sheet)
                DaggerfallUI.UIManager.PopWindow();
            yield return Frames(3);
            yield return new WaitForSecondsRealtime(1f);
            Report("level up");

            p.Level = 20;
            yield return Frames(3);
            int end = p.Stats.PermanentEndurance;
            oldMax = p.MaxHealth;
            p.Stats.SetPermanentStatValue(DFCareer.Stats.Endurance, end + 10);
            yield return Frames(3);
            Expect("level 20 endurance +10: full retroactive gain", p.MaxHealth - oldMax,
                DoomerfallEndurance.MaxHealth(20, end + 10) - DoomerfallEndurance.MaxHealth(20, end));
            Expect("order does not matter (same as gaining it at level 1)", p.MaxHealth, DoomerfallEndurance.MaxHealth(20, end + 10));
            yield return new WaitForSecondsRealtime(1f);
            Report("endurance up");

            p.Stats.SetPermanentStatValue(DFCareer.Stats.Endurance, end - 20);
            yield return Frames(3);
            Expect("endurance down max hp", p.MaxHealth, DoomerfallEndurance.MaxHealth(20, end - 20));
            Check("endurance down clamps hp", p.CurrentHealth <= p.MaxHealth && p.CurrentHealth > 0, p.CurrentHealth + "/" + p.MaxHealth);
            p.Stats.SetPermanentStatValue(DFCareer.Stats.Endurance, end);
            yield return new WaitForSecondsRealtime(1f);
            Report("endurance down and back");
        }

        // A real spell through Daggerfall's effect manager, caster only, no saving throw.
        static void Cast(string effectKey, int magnitude, int rounds)
        {
            EffectSettings settings = BaseEntityEffect.DefaultEffectSettings();
            settings.DurationBase = rounds;
            settings.DurationPlus = 0;
            settings.ChanceBase = 100;
            settings.MagnitudeBaseMin = settings.MagnitudeBaseMax = magnitude;
            settings.MagnitudePlusMin = settings.MagnitudePlusMax = 0;
            var spell = new EffectBundleSettings
            {
                Version = EntityEffectBroker.CurrentSpellVersion,
                BundleType = BundleTypes.Spell,
                TargetType = TargetTypes.CasterOnly,
                ElementType = ElementTypes.Magic,
                Name = "HP test " + effectKey,
                Effects = new[] { new EffectEntry(effectKey, settings) },
            };
            GameManager.Instance.PlayerEffectManager.AssignBundle(new EntityEffectBundle(spell, GameManager.Instance.PlayerEntityBehaviour),
                AssignBundleFlags.BypassSavingThrows | AssignBundleFlags.BypassChance);
        }

        // Effects and their timers run only in play: close any window left open (the level-up step leaves message
        // boxes) and unpause, logging what was in the way.
        IEnumerator InPlay(string step)
        {
            for (int i = 0; i < 5 && DaggerfallUI.UIManager.TopWindow != null && !(DaggerfallUI.UIManager.TopWindow is DaggerfallHUD); i++)
            {
                bridge.LogLine("hp formula test: " + step + ": closing " + DaggerfallUI.UIManager.TopWindow.GetType().Name);
                DaggerfallUI.UIManager.PopWindow();
                yield return Frames(2);
            }
            if (GameManager.IsGamePaused)
                bridge.LogLine("hp formula test: " + step + ": game was paused");
            GameManager.Instance.PauseGame(false);
            yield return Frames(3);
            Check("in play for " + step, GameManager.Instance.IsPlayingGame(), "top window " + DaggerfallUI.UIManager.TopWindow);
        }

        // Max HP follows live Endurance: Fortify raises it until the spell expires, Drain lowers it until healed.
        IEnumerator EnduranceEffects()
        {
            yield return InPlay("effects");
            PlayerEntity p = Player;
            int end = p.Stats.PermanentEndurance, level = p.Level;
            int baseMax = DoomerfallEndurance.MaxHealth(level, end);
            yield return Frames(3);
            Expect("before effects: max hp", p.MaxHealth, baseMax);
            p.SetHealth(p.MaxHealth - 30);
            yield return Frames(3);

            int hp = p.CurrentHealth;
            Cast("Fortify-Endurance", 15, 3);
            yield return new WaitForSecondsRealtime(1f); // Effect mods refresh on a short timer.
            int fortified = DoomerfallEndurance.MaxHealth(level, end + 15);
            Expect("fortify endurance: live endurance", p.Stats.LiveEndurance, end + 15);
            Expect("fortify endurance: permanent endurance unchanged", p.Stats.PermanentEndurance, end);
            Expect("fortify endurance raises max hp", p.MaxHealth, fortified);
            Expect("fortify endurance raises hp by the gain", p.CurrentHealth, hp + fortified - baseMax);
            Report("fortify endurance");
            yield return new WaitForSecondsRealtime(1f);

            // Expiry: pass game time the way resting does, so the spell's magic rounds run out.
            yield return InPlay("expiry");
            DaggerfallUnity.Instance.WorldTime.Now.RaiseTime(10 * 60);
            float deadline = Time.unscaledTime + 5f;
            while (p.Stats.LiveEndurance != end && Time.unscaledTime < deadline)
                yield return null;
            yield return Frames(3);
            Expect("fortify expired: live endurance", p.Stats.LiveEndurance, end);
            Expect("fortify expired: max hp falls back", p.MaxHealth, baseMax);
            Check("fortify expired: hp clamped", p.CurrentHealth == Mathf.Min(hp + fortified - baseMax, baseMax), p.CurrentHealth + "/" + p.MaxHealth);
            Report("fortify expired");
            yield return new WaitForSecondsRealtime(1f);

            yield return InPlay("drain");
            p.SetHealth(p.MaxHealth - 5);
            yield return Frames(3);
            Cast("Drain-Endurance", 20, 1);
            yield return new WaitForSecondsRealtime(1f);
            int drained = DoomerfallEndurance.MaxHealth(level, end - 20);
            Expect("drain endurance: live endurance", p.Stats.LiveEndurance, end - 20);
            Expect("drain endurance: permanent endurance unchanged", p.Stats.PermanentEndurance, end);
            Expect("drain endurance lowers max hp", p.MaxHealth, drained);
            Expect("drain endurance clamps hp", p.CurrentHealth, Mathf.Min(baseMax - 5, drained));
            Report("drain endurance");
            yield return new WaitForSecondsRealtime(1f);

            // Through a save and load the drained max HP and current HP stay as saved (no drop and rise on the way).
            hp = p.CurrentHealth;
            GameManager.Instance.SaveLoadManager.Save(p.Name, SaveName);
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Load(p.Name);
            p = Player;
            Expect("drained save loaded: max hp", p.MaxHealth, drained);
            Expect("drained save loaded: hp as saved", p.CurrentHealth, hp);
            Report("drained save loaded");

            yield return InPlay("heal");
            hp = p.CurrentHealth;
            GameManager.Instance.PlayerEffectManager.HealAttribute(DFCareer.Stats.Endurance, 20);
            yield return new WaitForSecondsRealtime(1f);
            Expect("drain healed: live endurance", p.Stats.LiveEndurance, end);
            Expect("drain healed: max hp back", p.MaxHealth, baseMax);
            Expect("drain healed: hp rises by the gain", p.CurrentHealth, hp + baseMax - drained);
            Report("drain healed");
            yield return new WaitForSecondsRealtime(1f);
        }

        // A save made before this change has no bonus flag, the class's raw Endurance, and the old max HP.
        IEnumerator OlderSave()
        {
            PlayerEntity p = Player;
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            int end = p.Stats.PermanentEndurance, bonus = DoomerfallEndurance.ClassBonus(p.Career);
            saves.Save(p.Name, SaveName);
            yield return new WaitForSecondsRealtime(1.5f);
            saves.EnumerateSaves();
            string file = Path.Combine(saves.GetSaveFolder(saves.FindSaveFolderByNames(p.Name, SaveName)), "SaveData.txt");
            string json = File.ReadAllText(file);
            Match flag = Regex.Match(json, @",\s*""doomerfallEnduranceBonus""\s*:\s*true");
            Check("save has the bonus flag", flag.Success, file);
            if (!flag.Success)
                yield break;
            int at = flag.Index;
            Match e = new Regex(@"""Endurance""\s*:\s*(\d+)", RegexOptions.RightToLeft).Match(json, 0, at);
            string old = json.Substring(0, e.Groups[1].Index) + (end - bonus) + json.Substring(e.Groups[1].Index + e.Groups[1].Length, at - e.Groups[1].Index - e.Groups[1].Length);
            string rest = json.Substring(at + flag.Length);
            // The Endurance maximum is saved with the stats, so a load restores breath against it.
            Match maxBonus = Regex.Match(rest, @"^\s*,\s*""doomerfallEnduranceMaxBonus""\s*:\s*(-?\d+)");
            Check("save has the endurance maximum bonus", maxBonus.Success && int.Parse(maxBonus.Groups[1].Value) == bonus,
                maxBonus.Success ? maxBonus.Groups[1].Value : "missing");
            if (maxBonus.Success)
                rest = rest.Substring(maxBonus.Length);
            rest = new Regex(@"""maxHealth""\s*:\s*-?\d+").Replace(rest, "\"maxHealth\": 45", 1);
            rest = new Regex(@"""currentHealth""\s*:\s*-?\d+").Replace(rest, "\"currentHealth\": 30", 1);
            File.WriteAllText(file, old + rest);
            bridge.LogLine(string.Format("hp formula test: older save written: endurance {0}, hp 30/45, no flag", end - bonus));

            yield return Load(p.Name);
            p = Player;
            int max = DoomerfallEndurance.MaxHealth(p.Level, end);
            Expect("older save: bonus added once", p.Stats.PermanentEndurance, end);
            Expect("older save: max hp from the formula", p.MaxHealth, max);
            Expect("older save: hp rises with max", p.CurrentHealth, Mathf.Min(max, 30 + max - 45));
            yield return new WaitForSecondsRealtime(1f);
            Report("older save loaded");

            // Endurance past 100 and full breath (Endurance / 2): a load must not clamp breath to 50.
            int top = p.Stats.GetMaxPermanentValue(DFCareer.Stats.Endurance);
            p.Stats.SetPermanentStatValue(DFCareer.Stats.Endurance, top);
            yield return Frames(3);
            p.CurrentBreath = p.MaxBreath;
            int breath = p.CurrentBreath;
            saves.Save(p.Name, SaveName);
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Load(p.Name);
            Expect("saved again and loaded: no double bonus", Player.Stats.PermanentEndurance, top);
            Expect("saved again and loaded: max hp", Player.MaxHealth, DoomerfallEndurance.MaxHealth(Player.Level, top));
            Expect("endurance " + top + ": breath kept through the load", loadedBreath, breath);
            max = Player.MaxHealth;
            Report("reloaded");
        }

        IEnumerator Load(string character)
        {
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            loaded = false;
            SaveLoadManager.OnLoad += OnLoaded;
            saves.EnumerateSaves();
            saves.Load(character, SaveName);
            float deadline = Time.unscaledTime + 12f;
            while (!loaded && Time.unscaledTime < deadline)
                yield return null;
            SaveLoadManager.OnLoad -= OnLoaded;
            GameManager.Instance.PauseGame(false);
            yield return new WaitForSecondsRealtime(1f);
            Check("load finished", loaded, character);
        }

        // Breath as the load restored it, before anything refills it.
        void OnLoaded(SaveData_v1 data) { loaded = true; loadedBreath = Player.CurrentBreath; }

        IEnumerator CustomClassShot()
        {
            var window = new CreateCharCustomClass(DaggerfallUI.UIManager);
            DaggerfallUI.UIManager.PushWindow(window);
            yield return Frames(10);
            for (int i = 0; i < 4; i++)
                window.HitPointsUpButton_OnMouseClick(null, Vector2.zero);
            yield return Frames(10);
            Expect("editor keeps hp per level", window.CreatedClass.HitPointsPerLevel, 12);
            Directory.CreateDirectory(dir);
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, "custom-class-editor.png"));
            yield return new WaitForEndOfFrame();
            yield return Frames(5);
            bridge.LogLine("hp formula test: screenshot " + Path.Combine(dir, "custom-class-editor.png"));
            DaggerfallUI.UIManager.PopWindow();
        }
    }
}
