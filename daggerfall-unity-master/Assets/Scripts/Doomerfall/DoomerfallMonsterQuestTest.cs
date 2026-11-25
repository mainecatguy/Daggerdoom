// Doomerfall test only, run by tools/monster_deaths, tools/area_level/runtime_check.py and tools/real_drops:
//   -dfmonsterquest <quest>   starts a real quest whose random dungeon resolves to the one at the player's location,
//                             and reports its _imp_ foe as -dfmonsterreport does.
//   -dfmonsterreport          logs the _imp_ foe's kills and whether the quest's _mondead_ task triggered.

using System;
using System.Reflection;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMonsterQuestTest
    {
        readonly DoomerfallBridge bridge;
        string quest;
        int lastReported = -1;

        DoomerfallMonsterQuestTest(DoomerfallBridge owner, string questName)
        {
            bridge = owner;
            quest = questName;
        }

        // Null without either flag.
        internal static DoomerfallMonsterQuestTest Create(DoomerfallBridge owner)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfmonsterquest");
            if (at < 0 && Array.IndexOf(args, "-dfmonsterreport") < 0)
                return null;
            return new DoomerfallMonsterQuestTest(owner, at >= 0 && at + 1 < args.Length ? args[at + 1] : null);
        }

        // DoomerfallMonsters, at each poll while in game.
        internal void Poll()
        {
            Start();
            Report();
        }

        void Start()
        {
            if (string.IsNullOrEmpty(quest))
                return;
            GameManager game = GameManager.Instance;
            if (game.PlayerEnterExit.IsPlayerInside || !game.PlayerGPS.HasCurrentLocation || !game.PlayerGPS.CurrentLocation.HasDungeon)
                return;
            string name = quest;
            quest = null;
            DFLocation location = game.PlayerGPS.CurrentLocation;
            Quest started = QuestMachine.Instance.ParseQuest(name, QuestMachine.Instance.GetQuestSourceText(name));
            Place place = started != null ? started.GetPlace(new Symbol("_mondung_")) : null;
            if (place == null)
            {
                bridge.LogLine("error: quest " + name + " did not parse with its dungeon place");
                return;
            }
            string rolled = place.SiteDetails.locationName;
            // Doom has one converted dungeon, so the test points the quest's dungeon at it. Its markers are the real ones.
            const BindingFlags Any = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static;
            object[] markerArgs = { location, null, null };
            typeof(Place).GetMethod("EnumerateDungeonQuestMarkers", Any).Invoke(place, markerArgs);
            SiteDetails site = new SiteDetails
            {
                questUID = started.UID,
                siteType = SiteTypes.Dungeon,
                mapId = location.MapTableData.MapId,
                locationId = location.Exterior.ExteriorData.LocationId,
                regionIndex = location.RegionIndex,
                regionName = location.RegionName,
                locationName = location.Name,
                questSpawnMarkers = (QuestMarker[])markerArgs[1],
                questItemMarkers = (QuestMarker[])markerArgs[2],
            };
            typeof(Place).GetField("siteDetails", Any).SetValue(place, site);
            QuestMachine.Instance.StartQuest(started);
            bridge.LogLine(string.Format("monsters: started quest {0} uid {1}; rolled {2}, test site {3} with {4} spawn markers", name, started.UID, rolled, location.Name, site.questSpawnMarkers.Length));
        }

        void Report()
        {
            Quest found = null;
            foreach (ulong uid in QuestMachine.Instance.GetAllActiveQuests())
            {
                Quest candidate = QuestMachine.Instance.GetQuest(uid);
                if (candidate != null && candidate.GetFoe(new Symbol("_imp_")) != null)
                    found = candidate;
            }
            if (found == null)
                return;
            Foe foe = found.GetFoe(new Symbol("_imp_"));
            Task task = found.GetTask(new Symbol("_mondead_"));
            bool triggered = task != null && task.IsTriggered;
            int state = foe.KillCount * 2 + (triggered ? 1 : 0);
            if (state == lastReported)
                return;
            lastReported = state;
            bridge.LogLine(string.Format("monsters: quest {0} kills {1}, injured {2}, killed task triggered {3}", found.UID, foe.KillCount, foe.InjuredTrigger, triggered));
        }
    }
}
