// Doomerfall test only (-dfresttest <file> [level]): once the game runs, takes the player down to a quarter of their
// health so a rest has something to restore, and clears the six-hour wait on Daggerfall's skill check so the check at the
// end of even a short rest runs. With "level" it also earns the character exactly one level (as -dfleveluptest), without
// running the check itself, so the rest's own check must grant it. Logs, each time it changes, the top window and the
// player's health, fatigue, magicka, level and game time, so a test can follow the rest from Doom.
// With -dfresttestroom it also rents a room for a day in the first tavern entered.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Serialization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallRestTest : MonoBehaviour
    {
        string path, last;
        DoomerfallPositionSync sync;
        float readyAt;
        bool done, level, room, rented;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfresttest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallRestTest");
            DontDestroyOnLoad(host);
            DoomerfallRestTest test = host.AddComponent<DoomerfallRestTest>();
            test.path = args[at + 1];
            test.level = at + 2 < args.Length && args[at + 2] == "level";
            test.room = Array.IndexOf(args, "-dfresttestroom") >= 0; // Also rent a room in the first tavern entered.
            File.WriteAllText(test.path, "rest test: started\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        void LateUpdate()
        {
            try { Prepare(); RentRoom(); }
            catch (Exception e) { Write("prepare error " + e.GetType().Name + " " + e.Message); done = true; }
            string line;
            try { line = Describe(); }
            catch (Exception e) { line = "error " + e.GetType().Name + " " + e.Message; }
            if (line == last)
                return;
            last = line;
            Write(line);
        }

        void Prepare()
        {
            if (done || !GameManager.HasInstance)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!sync || !sync.InGame || GameManager.Instance.SaveLoadManager.LoadInProgress || player == null)
            {
                readyAt = 0;
                return;
            }
            if (readyAt == 0)
                readyAt = Time.realtimeSinceStartup + 1f;
            if (Time.realtimeSinceStartup < readyAt)
                return;
            done = true;

            player.CurrentHealth = Math.Max(1, player.MaxHealth / 4);
            player.CurrentFatigue = player.MaxFatigue / 2;
            player.TimeOfLastSkillIncreaseCheck = 0;
            Write(string.Format("prepared: hp {0}/{1}, recovery per hour {2} (scale {3})", player.CurrentHealth, player.MaxHealth,
                FormulaHelper.CalculateHealthRecoveryRate(player), FormulaHelper.DoomerfallHealthRecoveryScale));
            if (!level)
                return;

            // As DoomerfallLevelUpTest: line the formula up with the current level, then raise primary skills to exactly one more.
            int current = player.Level, raised = 0;
            player.SetCurrentLevelUpSkillSum();
            player.StartingLevelUpSkillSum = player.CurrentLevelUpSkillSum + 28 - 15 * current;
            var primary = player.GetPrimarySkills();
            for (int i = 0; i < 600 && FormulaHelper.CalculatePlayerLevel(player.StartingLevelUpSkillSum, player.CurrentLevelUpSkillSum) <= current; i++)
            {
                DaggerfallConnect.DFCareer.Skills skill = primary[i % primary.Count];
                short value = player.Skills.GetPermanentSkillValue(skill);
                if (value >= 95)
                    continue;
                player.Skills.SetPermanentSkillValue(skill, (short)(value + 1));
                player.SetCurrentLevelUpSkillSum();
                raised++;
            }
            Write(string.Format("earned level {0} -> formula {1} after {2} skill points; the rest's skill check must grant it", current,
                FormulaHelper.CalculatePlayerLevel(player.StartingLevelUpSkillSum, player.CurrentLevelUpSkillSum), raised));
        }

        // As DaggerfallTavernWindow's rental, for one day, so Daggerfall's own rest check allows a rest here.
        void RentRoom()
        {
            if (!room || rented || !GameManager.HasInstance)
                return;
            PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
            if (!enter.IsPlayerInsideBuilding || !enter.Interior || enter.BuildingDiscoveryData.buildingType != DaggerfallConnect.DFLocation.BuildingTypes.Tavern)
                return;
            rented = true;
            int mapId = GameManager.Instance.PlayerGPS.CurrentLocation.MapTableData.MapId;
            int key = enter.BuildingDiscoveryData.buildingKey;
            GameManager.Instance.PlayerEntity.RentedRooms.Add(new RoomRental_v1
            {
                name = enter.BuildingDiscoveryData.displayName,
                mapID = mapId,
                buildingKey = key,
                allocatedBedIndex = 0,
                expiryTime = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() + (ulong)DaggerfallWorkshop.Utility.DaggerfallDateTime.SecondsPerDay,
            });
            SaveLoadManager.StateManager.AddPermanentScene(DaggerfallInterior.GetSceneName(mapId, key));
            Write("rented a room in building " + key);
        }

        static string Describe()
        {
            if (!DaggerfallUI.Instance || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return "none";
            UserInterface.IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            PlayerEntity p = GameManager.Instance.PlayerEntity;
            return string.Format("top {0} | hp {1}/{2} fatigue {3}/{4} magicka {5}/{6} level {7} ready {8} game_minutes {9}",
                top == null ? "none" : top.GetType().Name, p.CurrentHealth, p.MaxHealth, p.CurrentFatigue, p.MaxFatigue,
                p.CurrentMagicka, p.MaxMagicka, p.Level, p.ReadyToLevelUp, DaggerfallUnity.Instance.WorldTime.DaggerfallDateTime.ToClassicDaggerfallTime());
        }
    }
}
