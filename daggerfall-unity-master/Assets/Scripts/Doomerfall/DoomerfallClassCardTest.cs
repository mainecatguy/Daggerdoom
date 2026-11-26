// Doomerfall test only (-dfclasscardtest with -dfsynctest): gives the character each preset class the way a new
// game does, then saves and loads characters with pre-card class lists (a levelled preset and custom classes), and
// logs the class lists, levels and gun skills so bridge/test/class_card_test.py can check them against the proposal and
// against what Doom read. Saves go to the portable install's private folder.

using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Player;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;
using S = DaggerfallConnect.DFCareer.Skills;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallClassCardTest : MonoBehaviour
    {
        const float StepSeconds = 0.6f, WaitSeconds = 12f;
        static readonly string[] OldSaveNames = { "PreSkills", "PreRifles", "PreEnergyMelee" };
        static readonly S[] Guns = { S.Shotguns, S.Automatics, S.Explosives, S.Pistols, S.Rifles, S.EnergyWeapons, S.Melee };

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        bool loaded;
        string character;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            if (DaggerfallUnityApplication.IsPortableInstall)
                StartCoroutine(Run());
            else
                bridge.LogLine("error: -dfclasscardtest needs a portable install");
        }

        void Log(string text) { bridge.LogLine("class card test: " + text); }

        IEnumerator Run()
        {
            while (!sync.InGame)
                yield return null;
            yield return new WaitForSecondsRealtime(StepSeconds);
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            character = GameManager.Instance.PlayerEntity.Name;
            Log("baseline");

            // Class maker choices (guns mode).
            var maker = new CreateCharCustomClass(DaggerfallUI.UIManager);
            typeof(CreateCharCustomClass).GetMethod("Setup", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(maker, null);
            var offered = (List<string>)typeof(CreateCharCustomClass).GetField("skillsList", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(maker);
            Log("class maker offers [" + string.Join(",", offered.ToArray()) + "]");

            // Each preset class from its CLASS*.CFG, as the new-game wizard loads it and a new game assigns it.
            for (int i = 0; i < 18; i++)
            {
                DFCareer career = new ClassFile(ClassPath(i)).Career;
                AssignNew(career, i, false);
                yield return new WaitForSecondsRealtime(StepSeconds);
                LogCharacter("preset " + i);
            }

            // Old saves the demo copies in must still load at their level.
            foreach (string oldSave in OldSaveNames)
            {
                saves.EnumerateSaves();
                if (saves.FindSaveFolderByNames(character, oldSave) < 0)
                    continue;
                yield return LoadAndWait(saves, oldSave);
                LogCharacter("old save " + oldSave + (loaded ? "" : " (load timed out)"));
            }

            // A levelled Warrior with its classic class lists (as a save from before the cards has), saved and loaded.
            AssignNew(new ClassFile(ClassPath(16)).Career, 16, false);
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            SetLists(player.Career, RawClassicLists(16));
            foreach (S s in new[] { S.Axe, S.LongBlade, S.BluntWeapon, S.HandToHand, S.Archery, S.ShortBlade })
                player.Skills.SetPermanentSkillValue(s, 60);
            player.Level = 5;
            player.SetCurrentLevelUpSkillSum();
            player.StartingLevelUpSkillSum = player.CurrentLevelUpSkillSum - 54; // halfway through level 5
            LogCharacter("pre-card warrior before save");
            saves.Save(character, "PreCardsWarrior");
            yield return new WaitForSecondsRealtime(1.5f);
            yield return LoadAndWait(saves, "PreCardsWarrior");
            LogCharacter("pre-card warrior loaded" + (loaded ? "" : " (load timed out)"));

            // A custom class from before the cards (Daggerfall weapons, Critical Strike, a removed language).
            DFCareer custom = new ClassFile(ClassPath(16)).Career;
            custom.Name = "Test Duelist";
            SetLists(custom, new[] { S.ShortBlade, S.LongBlade, S.Stealth, S.CriticalStrike, S.Axe, S.Pistols,
                S.Archery, S.BluntWeapon, S.Running, S.Medical, S.Etiquette, S.Centaurian });
            AssignNew(custom, 16, true);
            LogCharacter("old custom before save");
            saves.Save(character, "PreCardsCustom");
            yield return new WaitForSecondsRealtime(1.5f);
            yield return LoadAndWait(saves, "PreCardsCustom");
            LogCharacter("old custom loaded" + (loaded ? "" : " (load timed out)"));

            // A custom class made in guns mode keeps its own picks.
            custom = new ClassFile(ClassPath(16)).Career;
            custom.Name = "Test Gunner";
            SetLists(custom, new[] { S.Pistols, S.Shotguns, S.Stealth, S.Rifles, S.Melee, S.Running,
                S.Explosives, S.EnergyWeapons, S.Automatics, S.Medical, S.Etiquette, S.Dodging });
            AssignNew(custom, 16, true);
            LogCharacter("guns custom before save");
            saves.Save(character, "GunsCustom");
            yield return new WaitForSecondsRealtime(1.5f);
            yield return LoadAndWait(saves, "GunsCustom");
            LogCharacter("guns custom loaded" + (loaded ? "" : " (load timed out)"));

            // One full new game (Knight), world and all.
            var start = FindObjectOfType<StartGameBehaviour>();
            start.CharacterDocument = NewDocument(new ClassFile(ClassPath(17)).Career, 17, false);
            start.StartMethod = StartGameBehaviour.StartMethods.NewCharacter;
            yield return new WaitForSecondsRealtime(2f);
            LogCharacter("new game knight");
            Log("done");
        }

        static string ClassPath(int index)
        {
            return Path.Combine(DaggerfallUnity.Instance.Arena2Path, "CLASS" + index.ToString("00") + ".CFG");
        }

        static S[] RawClassicLists(int index)
        {
            byte[] data = File.ReadAllBytes(ClassPath(index));
            var list = new S[12];
            for (int i = 0; i < 12; i++)
                list[i] = (S)data[16 + i];
            return list;
        }

        static void SetLists(DFCareer c, S[] l)
        {
            c.PrimarySkill1 = l[0]; c.PrimarySkill2 = l[1]; c.PrimarySkill3 = l[2];
            c.MajorSkill1 = l[3]; c.MajorSkill2 = l[4]; c.MajorSkill3 = l[5];
            c.MinorSkill1 = l[6]; c.MinorSkill2 = l[7]; c.MinorSkill3 = l[8];
            c.MinorSkill4 = l[9]; c.MinorSkill5 = l[10]; c.MinorSkill6 = l[11];
        }

        CharacterDocument NewDocument(DFCareer career, int classIndex, bool isCustom)
        {
            var doc = new CharacterDocument();
            doc.name = character;
            doc.career = career;
            doc.classIndex = classIndex;
            doc.isCustom = isCustom;
            doc.workingStats.SetPermanentFromCareer(career);
            var rollout = new SkillsRollout();
            rollout.SetClassSkills(career); // the new-game wizard's skill roll for the class lists
            doc.workingSkills.Copy(rollout.WorkingSkills);
            return doc;
        }

        // The character part of StartGameBehaviour.StartNewCharacter, without moving the world.
        void AssignNew(DFCareer career, int classIndex, bool isCustom)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            player.AssignCharacter(NewDocument(career, classIndex, isCustom));
            player.SetCurrentLevelUpSkillSum();
            player.StartingLevelUpSkillSum = player.CurrentLevelUpSkillSum;
        }

        // The class lists as the character sheet's skill buttons show them, the level state, and the gun skills.
        void LogCharacter(string label)
        {
            PlayerEntity p = GameManager.Instance.PlayerEntity;
            var groups = new[] { p.GetPrimarySkills(), p.GetMajorSkills(), p.GetMinorSkills() };
            var parts = new List<string>();
            foreach (var group in groups)
                parts.Add(string.Join(",", group.ConvertAll(s => DaggerfallUnity.Instance.TextProvider.GetSkillName(s)).ToArray()));
            var guns = new List<string>();
            foreach (S g in Guns)
                guns.Add(DaggerfallUnity.Instance.TextProvider.GetSkillName(g) + "=" + p.Skills.GetPermanentSkillValue(g));
            Log(string.Format("{0} | class {1} | primary [{2}] major [{3}] minor [{4}] | level {5} start {6} current {7} calculated {8} | guns {9}",
                label, p.Career.Name, parts[0], parts[1], parts[2], p.Level, p.StartingLevelUpSkillSum, p.CurrentLevelUpSkillSum,
                FormulaHelper.CalculatePlayerLevel(p.StartingLevelUpSkillSum, p.CurrentLevelUpSkillSum), string.Join(",", guns.ToArray())));
        }

        IEnumerator LoadAndWait(SaveLoadManager saves, string saveName)
        {
            loaded = false;
            SaveLoadManager.OnLoad += OnLoaded;
            saves.EnumerateSaves();
            saves.Load(character, saveName);
            float deadline = Time.unscaledTime + WaitSeconds;
            while (!loaded && Time.unscaledTime < deadline)
                yield return null;
            SaveLoadManager.OnLoad -= OnLoaded;
            GameManager.Instance.PauseGame(false);
            yield return new WaitForSecondsRealtime(1f);
        }

        void OnLoaded(SaveData_v1 data) { loaded = true; }
    }
}
