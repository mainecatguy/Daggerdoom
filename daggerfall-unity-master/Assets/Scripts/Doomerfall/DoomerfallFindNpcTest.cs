// Doomerfall test only (-dffindtest <file>): sets up the find-NPC test (tools/find_npc/findnpc.py). Once the game runs
// outdoors in a town, it starts two real quests, keeps one quest person where the quest put them (another town), and
// points another quest person's place at a building of this town, then writes both names. Indoors it writes the names
// of the NPCs present. Starts itself from the flag; no game class calls it.

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallFindNpcTest : MonoBehaviour
    {
        static readonly string[] Quests = { "A0C00Y00", "A0C00Y11" };
        string path;
        bool seeded;
        int residentsFor;
        float readyAt;
        DoomerfallPositionSync sync;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dffindtest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallFindNpcTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallFindNpcTest>().path = args[at + 1];
            File.WriteAllText(args[at + 1], "FT started\n");
        }

        void Write(string line) { File.AppendAllText(path, line + "\n"); }

        void LateUpdate()
        {
            try { Step(); }
            catch (Exception e) { Write("FT error " + e.GetType().Name + " " + e.Message); seeded = true; residentsFor = -1; }
        }

        void Step()
        {
            if (!GameManager.HasInstance || QuestMachine.Instance == null)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            GameManager game = GameManager.Instance;
            if (!sync || !sync.InGame || game.SaveLoadManager.LoadInProgress || !game.PlayerGPS.HasCurrentLocation)
                return;
            if (!seeded && !game.PlayerEnterExit.IsPlayerInside)
            {
                if (readyAt == 0)
                    readyAt = Time.realtimeSinceStartup + 3f;
                if (Time.realtimeSinceStartup >= readyAt)
                    Seed(game);
            }
            int key = game.PlayerEnterExit.IsPlayerInsideBuilding ? game.PlayerEnterExit.BuildingDiscoveryData.buildingKey : 0;
            if (key != 0 && key != residentsFor && residentsFor >= 0)
            {
                residentsFor = key;
                foreach (StaticNPC npc in ActiveGameObjectDatabase.GetActiveStaticNPCs(true))
                    if (npc.gameObject.activeSelf && npc.Data.context == StaticNPC.Context.Building && npc.Data.buildingKey == key)
                        Write(string.Format("FT resident {0}|{1:x16}", npc.DisplayName, DoomerfallNpcs.IdOf(npc)));
                Write("FT residents done " + key);
            }
        }

        void Seed(GameManager game)
        {
            seeded = true;
            var people = new List<KeyValuePair<Quest, Person>>();
            foreach (string name in Quests)
            {
                Quest quest = QuestMachine.Instance.ParseQuest(name, QuestMachine.Instance.GetQuestSourceText(name));
                if (quest == null)
                    continue;
                QuestMachine.Instance.StartQuest(quest);
                foreach (QuestResource r in quest.GetAllResources(typeof(Person)))
                {
                    Person p = r as Person;
                    if (p != null && PlaceOf(quest, p) != null)
                        people.Add(new KeyValuePair<Quest, Person>(quest, p));
                }
            }
            if (people.Count < 2)
            {
                Write("FT error only " + people.Count + " placed quest people");
                return;
            }
            KeyValuePair<Quest, Person> far = people[0], moved = people[1];
            Write(string.Format("FT far {0}|{1}", far.Value.DisplayName, PlaceOf(far.Key, far.Value).SiteDetails.locationName));
            // The middle building of this town from the block data (Daggerfall's town scene is inert under Doom).
            var keys = new List<int>();
            DaggerfallConnect.DFBlock[] blocks = RMBLayout.GetLocationBuildingData(game.PlayerGPS.CurrentLocation);
            int w = game.PlayerGPS.CurrentLocation.Exterior.ExteriorData.Width;
            for (int i = 0; i < blocks.Length; i++)
                for (int r = 0; r < blocks[i].RmbBlock.SubRecords.Length; r++)
                    if (blocks[i].RmbBlock.SubRecords[r].Exterior.Block3dObjectRecords.Length > 0)
                        keys.Add(BuildingDirectory.MakeBuildingKey((byte)(i % w), (byte)(i / w), (byte)r));
            int key = keys.Count > 0 ? keys[keys.Count / 2] : 0;
            Write("FT buildings " + keys.Count);
            PlayerGPS.DiscoveredBuilding b;
            string buildingName = game.PlayerGPS.GetBaseBuildingDiscoveryData(key, out b) ? b.displayName : "test building";
            DaggerfallConnect.DFLocation location = game.PlayerGPS.CurrentLocation;
            Place place = PlaceOf(moved.Key, moved.Value);
            SiteDetails site = new SiteDetails
            {
                questUID = moved.Key.UID,
                siteType = SiteTypes.Building,
                mapId = location.MapTableData.MapId,
                locationId = location.Exterior.ExteriorData.LocationId,
                regionIndex = location.RegionIndex,
                regionName = location.RegionName,
                locationName = location.Name,
                buildingKey = key,
                buildingName = buildingName,
            };
            typeof(Place).GetField("siteDetails", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(place, site);
            Write(string.Format("FT quest {0}|{1}|{2}", moved.Value.DisplayName, key, buildingName));
        }

        static Place PlaceOf(Quest quest, Person p)
        {
            Symbol s = p.GetAssignedPlaceSymbol();
            return s != null ? quest.GetPlace(s) : p.GetHomePlace();
        }
    }
}
