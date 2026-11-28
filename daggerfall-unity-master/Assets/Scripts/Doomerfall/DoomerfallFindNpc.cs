// Doomerfall: Daggerfall's side of the debug find-NPC tool (dd_dev only; Doom's side is UZDoom/src/dd_findnpc.cpp).
//
// In:  DFB_KIND_FIND_NPC with a name, full or partial, matched case-insensitively.
// Out: for each match a DFB_KIND_FIND_TEXT label and a DFB_KIND_FIND_MATCH target, then DFB_KIND_FIND_END.
// Searches every NPC Daggerfall knows by name: quest people of active quests, NPCs Daggerfall has loaded (the building
// or dungeon the player is in, the town's street NPCs), the residents of every building in the current town (from the
// block data, named as StaticNPC names them), and the town's townspeople (Townsfolk.cs). It reads only: no discovery,
// no quest or save state changes. DFRandom's seed is restored after naming.

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallFindNpc
    {
        const int MaxSent = 30;
        const float DoomPerDaggerfall = 0.75f;

        struct Hit
        {
            public string name, label;
            public uint target;
            public ulong id;
            public double x, z;
            public int rank;
        }

        sealed class Context
        {
            public GameManager game;
            public PlayerGPS gps;
            public DfbUzState peer;
            public Transform space;          // the building or dungeon the player is in, else null
            public bool outside, inBuilding, inDungeon;
            public int building;             // key of the building the player is in
            public int mapId;
            public string town;
            public string query;
            public readonly List<Hit> hits = new List<Hit>();
            public readonly HashSet<string> seen = new HashSet<string>();
        }

        internal static void Find(DoomerfallBridge bridge, DoomerfallPositionSync sync, DoomerfallTownspeople townspeople, uint request, string query)
        {
            query = (query ?? "").Trim();
            Context c = new Context { query = query.ToLowerInvariant() };
            if (query.Length > 0 && !sync.LoadRunning && GameManager.HasInstance && sync.InGame)
            {
                try { Collect(c, bridge, sync, townspeople); }
                catch (Exception ex) { bridge.LogLine("findnpc: search failed: " + ex.Message); }
            }
            c.hits.Sort((a, b) => a.rank != b.rank ? a.rank.CompareTo(b.rank) : string.Compare(a.label, b.label, StringComparison.OrdinalIgnoreCase));
            int sent = Math.Min(MaxSent, c.hits.Count);
            for (int i = 0; i < sent; i++)
            {
                Hit h = c.hits[i];
                DoomerfallInfo.SendText(bridge, request, h.label, false, Dfb.KIND_FIND_TEXT);
                Send(bridge, Dfb.KIND_FIND_MATCH, request, h.target, h.id, h.x, h.z);
                bridge.LogLine(string.Format("findnpc: match {0} target {1} id {2:x16} at {3:F1} {4:F1}: {5}", i, h.target, h.id, h.x, h.z, h.label));
            }
            Send(bridge, Dfb.KIND_FIND_END, request, 0, (ulong)c.hits.Count, 0, 0);
            bridge.LogLine(string.Format("findnpc: request {0} \"{1}\": {2} matches, {3} sent", request, query, c.hits.Count, sent));
        }

        static void Send(DoomerfallBridge bridge, ushort kind, uint request, uint target, ulong id, double x, double z)
        {
            DfbEvent e = default(DfbEvent);
            e.kind = kind;
            e.tic = (uint)Time.frameCount;
            e.infoRequest.request = request;
            e.infoRequest.target = target;
            e.infoRequest.id = id;
            e.infoRequest.worldX = x;
            e.infoRequest.worldZ = z;
            bridge.Send(ref e);
        }

        static void Collect(Context c, DoomerfallBridge bridge, DoomerfallPositionSync sync, DoomerfallTownspeople townspeople)
        {
            c.game = GameManager.Instance;
            c.gps = c.game.PlayerGPS;
            bridge.ReadPeerState(out c.peer);
            c.outside = c.peer.worldContext == Dfb.WORLD_EXTERIOR;
            c.inBuilding = c.peer.worldContext == Dfb.WORLD_INTERIOR;
            c.inDungeon = c.peer.worldContext == Dfb.WORLD_DUNGEON;
            c.space = c.inBuilding || c.inDungeon ? sync.ItemSpace(ref c.peer) : null;
            c.building = c.inBuilding ? c.game.PlayerEnterExit.BuildingDiscoveryData.buildingKey : 0;
            c.mapId = c.gps.HasCurrentLocation ? c.gps.CurrentLocation.MapTableData.MapId : -1;
            c.town = c.gps.HasCurrentLocation ? c.gps.CurrentLocation.Name : "";
            QuestPeople(c);
            LoadedNpcs(c);
            Residents(c);
            Townspeople(c, townspeople);
        }

        static bool Matches(Context c, string name, out int rank)
        {
            rank = 0;
            if (string.IsNullOrEmpty(name))
                return false;
            string lower = name.ToLowerInvariant();
            int at = lower.IndexOf(c.query, StringComparison.Ordinal);
            if (at < 0)
                return false;
            rank = lower == c.query ? 0 : at == 0 || lower[at - 1] == ' ' ? 1 : 2;
            return true;
        }

        // here: 0 points in this area, 10 is elsewhere, so pointable matches list first.
        static void Add(Context c, string name, string what, uint target, ulong id, double x, double z, int rank)
        {
            string label = name + " - " + what;
            if (!c.seen.Add(label + "|" + target + "|" + id))
                return;
            c.hits.Add(new Hit { name = name, label = label, target = target, id = id, x = x, z = z, rank = rank + (target == Dfb.FIND_ELSEWHERE ? 10 : 0) });
        }

        static string BuildingName(Context c, int key)
        {
            PlayerGPS.DiscoveredBuilding b;
            if (key != 0 && (c.gps.GetDiscoveredBuilding(key, out b) || c.gps.GetBaseBuildingDiscoveryData(key, out b)) && !string.IsNullOrEmpty(b.displayName))
                return DaggerfallWorkshop.Localization.GrammarManager.grammarProcessor.ProcessGrammar(b.displayName);
            return "a building";
        }

        // A Unity point in the town scene as Daggerfall world units (DoomerfallInfo.FindBuilding's inverse).
        static void ToWorld(Context c, Vector3 p, out double x, out double z)
        {
            Vector3 player = c.gps.transform.position;
            x = c.gps.WorldX + (p.x - player.x) * StreamingWorld.SceneMapRatio;
            z = c.gps.WorldZ + (p.z - player.z) * StreamingWorld.SceneMapRatio;
        }

        // A Unity point in the current building or dungeon as Doom map units there (as DoomerfallNpcs.Report).
        static void ToLocal(Context c, Vector3 p, out double x, out double z)
        {
            Vector3 at = c.space.InverseTransformPoint(p);
            float units = DoomPerDaggerfall / MeshReader.GlobalScale;
            x = at.x * units;
            z = at.z * units;
        }

        // The world point of a building's door in the current town (or the dungeon entrance for key 0), outdoors only.
        static bool DoorOf(Context c, int key, out double x, out double z)
        {
            x = z = 0;
            DaggerfallLocation location = c.game.StreamingWorld.CurrentPlayerLocationObject;
            if (!c.outside || !location)
                return false;
            foreach (DaggerfallStaticDoors collection in location.GetComponentsInChildren<DaggerfallStaticDoors>())
            {
                if (collection.Doors == null)
                    continue;
                foreach (StaticDoor door in collection.Doors)
                {
                    bool wanted = key != 0 ? door.buildingKey == key && door.doorType == DoorTypes.Building : door.doorType == DoorTypes.DungeonEntrance;
                    if (!wanted)
                        continue;
                    Vector3 p = collection.transform.rotation * door.buildingMatrix.MultiplyPoint3x4(door.centre) + collection.transform.position;
                    ToWorld(c, p, out x, out z);
                    return true;
                }
            }
            return false;
        }

        // Someone inside a building of the current town: its door when outside, a note when elsewhere.
        static void InBuilding(Context c, string name, int key, int rank, string tag)
        {
            string building = BuildingName(c, key);
            double x, z;
            if (DoorOf(c, key, out x, out z))
                Add(c, name, tag + "in " + building, Dfb.FIND_WORLD, 0, x, z, rank);
            else
                Add(c, name, tag + "in " + building + ", " + c.town, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
        }

        static void QuestPeople(Context c)
        {
            QuestMachine machine = QuestMachine.Instance;
            if (machine == null)
                return;
            foreach (ulong uid in machine.GetAllActiveQuests())
            {
                Quest quest = machine.GetQuest(uid);
                if (quest == null)
                    continue;
                foreach (QuestResource resource in quest.GetAllResources(typeof(Person)))
                {
                    Person person = resource as Person;
                    int rank;
                    if (person == null || person.IsDestroyed || !Matches(c, person.DisplayName, out rank))
                        continue;
                    QuestPerson(c, quest, person, rank);
                }
            }
        }

        static void QuestPerson(Context c, Quest quest, Person person, int rank)
        {
            string name = person.DisplayName;
            Symbol symbol = person.GetAssignedPlaceSymbol();
            Place place = symbol != null ? quest.GetPlace(symbol) : person.GetHomePlace();
            if (place == null)
            {
                Add(c, name, "quest NPC, not placed anywhere", Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                return;
            }
            SiteDetails site = place.SiteDetails;
            string building = site.buildingKey != 0 && !string.IsNullOrEmpty(site.buildingName) ? site.buildingName : site.siteType == SiteTypes.Dungeon ? "the dungeon" : "";
            if (site.mapId != c.mapId)
            {
                string where = (building.Length > 0 ? building + ", " : "") + site.locationName + " (" + site.regionName + ")";
                Add(c, name, "quest NPC in " + where, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                return;
            }
            // In this location. Inside the very site, point at the live NPC.
            bool here = site.siteType == SiteTypes.Dungeon ? c.inDungeon : c.inBuilding && site.buildingKey == c.building;
            if (here && c.space)
            {
                foreach (StaticNPC npc in ActiveGameObjectDatabase.GetActiveStaticNPCs(true))
                {
                    QuestResourceBehaviour qrb = npc.GetComponent<QuestResourceBehaviour>();
                    if (!qrb || qrb.TargetResource != person)
                        continue;
                    if (!npc.gameObject.activeInHierarchy)
                        break;
                    double x, z;
                    ToLocal(c, npc.transform.position, out x, out z);
                    ulong id = DoomerfallNpcs.IdOf(npc);
                    Add(c, name, "quest NPC, here", id != 0 ? Dfb.FIND_ACTOR_LOCAL : Dfb.FIND_LOCAL, id, x, z, rank);
                    return;
                }
                Add(c, name, "quest NPC, placed here but not present now", Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                return;
            }
            if (site.siteType == SiteTypes.Dungeon)
            {
                double x, z;
                if (DoorOf(c, 0, out x, out z))
                    Add(c, name, "quest NPC in " + site.locationName, Dfb.FIND_WORLD, 0, x, z, rank);
                else
                    Add(c, name, "quest NPC in " + site.locationName, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                return;
            }
            if (site.buildingKey != 0)
                InBuilding(c, name, site.buildingKey, rank, "quest NPC ");
            else
                Add(c, name, "quest NPC in " + site.locationName, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
        }

        // NPCs Daggerfall has loaded: the building or dungeon the player is in, or the town's street NPCs.
        static void LoadedNpcs(Context c)
        {
            foreach (StaticNPC npc in ActiveGameObjectDatabase.GetActiveStaticNPCs(true))
            {
                if (npc.GetComponent<QuestResourceBehaviour>())
                    continue; // QuestPeople covers them
                int rank;
                string name = npc.DisplayName;
                if (!Matches(c, name, out rank))
                    continue;
                StaticNPC.NPCData data = npc.Data;
                double x, z;
                ulong id = DoomerfallNpcs.IdOf(npc);
                switch (data.context)
                {
                    case StaticNPC.Context.Building:
                        if (!c.inBuilding || data.buildingKey != c.building || !c.space)
                            continue; // Residents covers other buildings
                        if (!npc.gameObject.activeSelf)
                        {
                            Add(c, name, "lives here, away now", Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                            continue;
                        }
                        ToLocal(c, npc.transform.position, out x, out z);
                        Add(c, name, "here", id != 0 ? Dfb.FIND_ACTOR_LOCAL : Dfb.FIND_LOCAL, id, x, z, rank);
                        break;
                    case StaticNPC.Context.Dungeon:
                        if (!c.inDungeon || !c.space)
                            continue;
                        ToLocal(c, npc.transform.position, out x, out z);
                        Add(c, name, "here", id != 0 ? Dfb.FIND_ACTOR_LOCAL : Dfb.FIND_LOCAL, id, x, z, rank);
                        break;
                    default:
                        if (data.mapID != c.mapId)
                            continue;
                        if (c.outside)
                        {
                            ToWorld(c, npc.transform.position, out x, out z);
                            Add(c, name, "outside in " + c.town, id != 0 ? Dfb.FIND_ACTOR_WORLD : Dfb.FIND_WORLD, id, x, z, rank);
                        }
                        else
                            Add(c, name, "outside in " + c.town, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                        break;
                }
            }
        }

        // Every building's residents in the current town, named as StaticNPC names them (SetLayoutData, GetDisplayName).
        static void Residents(Context c)
        {
            if (!c.gps.HasCurrentLocation)
                return;
            DFLocation location = c.gps.CurrentLocation;
            int width = location.Exterior.ExteriorData.Width, height = location.Exterior.ExteriorData.Height;
            if (width <= 0 || height <= 0)
                return;
            DFBlock[] blocks = RMBLayout.GetLocationBuildingData(location);
            int locationIndex = location.LocationIndex;
            NameHelper.BankTypes bank = c.gps.GetNameBankOfCurrentRegion();
            var factions =c.game.PlayerEntity.FactionData;
            uint keep = DFRandom.Seed;
            try
            {
                for (int y = 0; y < height; y++)
                    for (int x = 0; x < width; x++)
                    {
                        DFBlock block = blocks[y * width + x];
                        DFBlock.RmbSubRecord[] records = block.RmbBlock.SubRecords;
                        for (int r = 0; records != null && r < records.Length; r++)
                        {
                            DFBlock.RmbBlockPeopleRecord[] people = records[r].Interior.BlockPeopleRecords;
                            if (people == null || people.Length == 0)
                                continue;
                            int key = BuildingDirectory.MakeBuildingKey((byte)x, (byte)y, (byte)r);
                            if (c.inBuilding && key == c.building)
                                continue; // LoadedNpcs has them, with who is present
                            foreach (DFBlock.RmbBlockPeopleRecord p in people)
                            {
                                string name;
                                FactionFile.FactionData faction;
                                Genders gender = (p.Flags & 32) == 32 ? Genders.Female : Genders.Male;
                                if (factions.GetFactionData(p.FactionID, out faction) && faction.type == (int)FactionFile.FactionTypes.Individual)
                                    name = faction.name;
                                else
                                {
                                    DFRandom.srand((int)p.Position ^ key + locationIndex);
                                    name = DaggerfallUnity.Instance.NameHelper.FullName(bank, gender);
                                }
                                int rank;
                                if (Matches(c, name, out rank))
                                    InBuilding(c, name, key, rank, "");
                            }
                        }
                    }
            }
            finally { DFRandom.Seed = keep; }
        }

        static void Townspeople(Context c, DoomerfallTownspeople townspeople)
        {
            TownRoster roster = townspeople ? townspeople.Roster : null;
            if (roster == null || roster.MapId != c.mapId)
                return;
            double hours = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() / 3600.0;
            foreach (TownPerson p in roster.People)
            {
                int rank;
                if (!Matches(c, p.Name, out rank) || townspeople.FindPerson(p.id) == null)
                    continue;
                TownRoster.Step step;
                if (!roster.FindStep(p, hours, out step))
                    continue;
                if (step.kind == 0)
                {
                    int key = step.a >= 0 && step.a < roster.Sites.Count ? roster.Sites[step.a].key : 0;
                    if (c.inBuilding && key == c.building)
                        Add(c, p.Name, "townsperson, here", Dfb.FIND_ACTOR_LOCAL, p.id, 0, 0, rank);
                    else
                        InBuilding(c, p.Name, key, rank, "townsperson ");
                    continue;
                }
                TownPose pose = roster.Pose(p, step, hours);
                if (c.outside && pose.visible)
                    Add(c, p.Name, "townsperson, outside", Dfb.FIND_ACTOR_WORLD, p.id, roster.OriginX + pose.x, roster.OriginZ + pose.z, rank);
                else
                    Add(c, p.Name, "townsperson, outside in " + c.town, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
            }
        }
    }
}
