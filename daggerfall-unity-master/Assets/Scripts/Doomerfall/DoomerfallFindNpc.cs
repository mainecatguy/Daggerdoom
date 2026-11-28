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
        const double NearTown = 32768; // Daggerfall units (a map pixel): a location this close may share Doom's stitched town map (the test's dungeon is ~600 m from its town)

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
            public DoomerfallBridge bridge;
            public GameManager game;
            public PlayerGPS gps;
            public DfbUzState peer;
            public Transform space;          // the building or dungeon the player is in, else null
            public bool outside, inBuilding, inDungeon;
            public int building;             // key of the building the player is in
            public int mapId;
            public string town;
            public string query;
            public string[] words;
            public bool list, questPass;
            public readonly List<DFLocation> towns = new List<DFLocation>(); // [0] the current location, then the nearby ones
            public readonly List<Hit> hits = new List<Hit>();
            public readonly HashSet<string> seen = new HashSet<string>();
        }

        // list: the pick list's search (DFB_FIND_LIST). An empty query then lists the active quests' NPCs, and a typed
        // one lists matching quest NPCs before everyone else.
        internal static void Find(DoomerfallBridge bridge, DoomerfallPositionSync sync, DoomerfallTownspeople townspeople, uint request, string query, bool list)
        {
            query = (query ?? "").Trim();
            Context c = new Context { query = query.ToLowerInvariant(), list = list };
            c.words = c.query.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if ((query.Length > 0 || list) && !sync.LoadRunning && GameManager.HasInstance && sync.InGame)
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
            bridge.LogLine(string.Format("findnpc: request {0} \"{1}\"{2}: {3} matches, {4} sent", request, query, list ? " (list)" : "", c.hits.Count, sent));
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
            c.bridge = bridge;
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
            Towns(c);
            c.questPass = true;
            QuestPeople(c);
            c.questPass = false;
            if (c.query.Length == 0)
                return; // the opening list: the active quests' NPCs only
            LoadedNpcs(c);
            Residents(c);
            Townspeople(c, townspeople);
        }

        // Lenient: closest first. 0 the whole name, 1 its start, 2 a word's start, 3 anywhere in it, then 4 + typos when
        // every typed word is the start of some word of the name, or that close to one (1 typo for 3-5 letters, 2 above).
        static bool Matches(Context c, string name, out int rank)
        {
            rank = 0;
            if (string.IsNullOrEmpty(name))
                return false;
            if (c.query.Length == 0)
                return true;
            rank = Score(name.ToLowerInvariant(), c.query, c.words);
            return rank >= 0;
        }

        static readonly char[] WordBreaks = { ' ', '-', '\'', '.', ',' };

        internal static int Score(string name, string query, string[] words)
        {
            if (name == query)
                return 0;
            if (name.StartsWith(query, StringComparison.Ordinal))
                return 1;
            int at = name.IndexOf(query, StringComparison.Ordinal);
            if (at > 0)
                return Array.IndexOf(WordBreaks, name[at - 1]) >= 0 ? 2 : 3;
            string[] parts = name.Split(WordBreaks, StringSplitOptions.RemoveEmptyEntries);
            int total = 0;
            foreach (string w in words)
            {
                int best = int.MaxValue;
                foreach (string part in parts)
                    best = Math.Min(best, WordDistance(w, part));
                if (best > (w.Length < 3 ? 0 : w.Length <= 5 ? 1 : 2))
                    return -1;
                total += best;
            }
            return words.Length > 0 ? 4 + total : -1;
        }

        // Typos between a typed word and a word of the name, also against just as many of its first letters (a partial word).
        static int WordDistance(string typed, string word)
        {
            if (word.StartsWith(typed, StringComparison.Ordinal))
                return 0;
            int d = Edits(typed, word);
            if (word.Length > typed.Length)
                d = Math.Min(d, Edits(typed, word.Substring(0, typed.Length)));
            return d;
        }

        // Levenshtein distance with adjacent swaps (optimal string alignment).
        static int Edits(string a, string b)
        {
            int[,] d = new int[a.Length + 1, b.Length + 1];
            for (int i = 0; i <= a.Length; i++) d[i, 0] = i;
            for (int j = 0; j <= b.Length; j++) d[0, j] = j;
            for (int i = 1; i <= a.Length; i++)
                for (int j = 1; j <= b.Length; j++)
                {
                    int cost = a[i - 1] == b[j - 1] ? 0 : 1;
                    int v = Math.Min(Math.Min(d[i - 1, j] + 1, d[i, j - 1] + 1), d[i - 1, j - 1] + cost);
                    if (i > 1 && j > 1 && a[i - 1] == b[j - 2] && a[i - 2] == b[j - 1])
                        v = Math.Min(v, d[i - 2, j - 2] + 1);
                    d[i, j] = v;
                }
            return d[a.Length, b.Length];
        }

        // Closest match first; in the pick list quest NPCs before everyone else; then those Doom can point at.
        static void Add(Context c, string name, string what, uint target, ulong id, double x, double z, int rank)
        {
            string label = name + " - " + what;
            if (!c.seen.Add(label + "|" + target + "|" + id))
                return;
            c.hits.Add(new Hit { name = name, label = label, target = target, id = id, x = x, z = z, rank = (c.list && !c.questPass ? 1000 : 0) + rank * 10 + (target == Dfb.FIND_ELSEWHERE ? 1 : 0) });
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

        // The world point of the current location's dungeon entrance, outdoors only (from Daggerfall's scene).
        static bool DungeonDoor(Context c, out double x, out double z)
        {
            x = z = 0;
            if (!c.outside)
                return false;
            DaggerfallLocation location = c.game.StreamingWorld.CurrentPlayerLocationObject;
            if (!location)
                return false;
            foreach (DaggerfallStaticDoors collection in location.GetComponentsInChildren<DaggerfallStaticDoors>())
            {
                if (collection.Doors == null)
                    continue;
                foreach (StaticDoor door in collection.Doors)
                {
                    if (door.doorType != DoorTypes.DungeonEntrance)
                        continue;
                    Vector3 p = collection.transform.rotation * door.buildingMatrix.MultiplyPoint3x4(door.centre) + collection.transform.position;
                    ToWorld(c, p, out x, out z);
                    return true;
                }
            }
            return false;
        }

        // A building's door from the map data alone (as RMBLayout.AddModels places models and GetStaticDoors their
        // doors), since Daggerfall's town scene is inert under Doom and may hold no door lists. World units as
        // TownRoster: location rect origin + block offset + block-local position. Falls back to the building's origin.
        static bool BuildingDoor(Context c, DFLocation location, int key, out double x, out double z)
        {
            x = z = 0;
            if (!c.outside)
                return false;
            int width = location.Exterior.ExteriorData.Width, height = location.Exterior.ExteriorData.Height;
            int bx, by, r;
            BuildingDirectory.ReverseBuildingKey(key, out bx, out by, out r);
            if (bx < 0 || by < 0 || bx >= width || by >= height)
                return false;
            DFBlock block = RMBLayout.GetLocationBuildingData(location)[by * width + bx];
            DFBlock.RmbSubRecord[] records = block.RmbBlock.SubRecords;
            if (records == null || r < 0 || r >= records.Length)
                return false;
            DFBlock.RmbSubRecord record = records[r];
            Vector3 recordPosition = new Vector3(record.XPos, 0, BlocksFile.RMBDimension - record.ZPos) * MeshReader.GlobalScale;
            Matrix4x4 recordMatrix = Matrix4x4.TRS(recordPosition, Quaternion.Euler(0, -record.YRotation / BlocksFile.RotationDivisor, 0), Vector3.one);
            Vector3 local = recordPosition;
            bool found = false;
            foreach (DFBlock.RmbBlock3dObjectRecord obj in record.Exterior.Block3dObjectRecords)
            {
                ModelData model;
                if (!DaggerfallUnity.Instance.MeshReader.GetModelData(obj.ModelIdNum, out model) || model.Doors == null)
                    continue;
                Vector3 position = new Vector3(obj.XPos, -obj.YPos, obj.ZPos) * MeshReader.GlobalScale;
                Vector3 rotation = new Vector3(-obj.XRotation / BlocksFile.RotationDivisor, -obj.YRotation / BlocksFile.RotationDivisor, -obj.ZRotation / BlocksFile.RotationDivisor);
                Matrix4x4 matrix = recordMatrix * Matrix4x4.TRS(position, Quaternion.Euler(rotation), RMBLayout.GetModelScaleVector(obj));
                foreach (StaticDoor door in GameObjectHelper.GetStaticDoors(ref model, block.Index, r, matrix))
                {
                    if (door.doorType != DoorTypes.Building)
                        continue;
                    local = matrix.MultiplyPoint3x4(door.centre);
                    found = true;
                    break;
                }
                if (found)
                    break;
            }
            Rect rect = DaggerfallLocation.GetLocationRect(location);
            x = rect.xMin + bx * RMBLayout.RMBSide / MeshReader.GlobalScale + local.x / MeshReader.GlobalScale;
            z = rect.yMin + by * RMBLayout.RMBSide / MeshReader.GlobalScale + local.z / MeshReader.GlobalScale;
            c.bridge.LogLine(string.Format("findnpc: building {0} block {1},{2} record {3} {4} at {5:F1} {6:F1}", key, bx, by, r, found ? "door" : "origin (no door in model data)", x, z));
            return true;
        }

        // Someone inside a building of a town here (c.towns[town]): its door when outside, a note when elsewhere.
        static void InBuilding(Context c, string name, string building, int town, int key, int rank, string tag)
        {
            if (string.IsNullOrEmpty(building))
                building = town == 0 ? BuildingName(c, key) : "a building";
            double x, z;
            if (BuildingDoor(c, c.towns[town], key, out x, out z))
                Add(c, name, tag + "in " + building + (town == 0 ? "" : ", " + c.towns[town].Name), Dfb.FIND_WORLD, 0, x, z, rank);
            else
                Add(c, name, tag + "in " + building + ", " + c.towns[town].Name, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
        }

        // The current location and the locations near the player: Doom stitches neighbouring locations into one town map
        // (a dungeon beside a town), while Daggerfall's current location is only the nearest of them.
        static void Towns(Context c)
        {
            if (!c.gps.HasCurrentLocation)
                return;
            c.towns.Add(c.gps.CurrentLocation);
            DaggerfallConnect.Utility.DFPosition at = c.gps.CurrentMapPixel;
            ContentReader reader = DaggerfallUnity.Instance.ContentReader;
            for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++)
                {
                    ContentReader.MapSummary summary;
                    DFLocation location;
                    if (!reader.HasLocation(at.X + dx, at.Y + dy, out summary) || !reader.GetLocation(summary.RegionIndex, summary.MapIndex, out location))
                        continue;
                    if (location.MapTableData.MapId == c.mapId || location.Exterior.ExteriorData.Width <= 0)
                        continue;
                    Rect r = DaggerfallLocation.GetLocationRect(location);
                    double ox = Math.Max(0, Math.Max(r.xMin - c.gps.WorldX, c.gps.WorldX - r.xMax));
                    double oz = Math.Max(0, Math.Max(r.yMin - c.gps.WorldZ, c.gps.WorldZ - r.yMax));
                    if (ox <= NearTown && oz <= NearTown)
                        c.towns.Add(location);
                }
        }

        static int TownOf(Context c, int mapId)
        {
            for (int i = 0; i < c.towns.Count; i++)
                if (c.towns[i].MapTableData.MapId == mapId)
                    return i;
            return -1;
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
            int town = TownOf(c, site.mapId);
            if (town < 0 || (town > 0 && (site.siteType != SiteTypes.Building || site.buildingKey == 0)))
            {
                string where = (building.Length > 0 ? building + ", " : "") + site.locationName + " (" + site.regionName + ")";
                Add(c, name, "quest NPC in " + where, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                return;
            }
            // In this location. Inside the very site, point at the live NPC.
            bool here = town == 0 && (site.siteType == SiteTypes.Dungeon ? c.inDungeon : c.inBuilding && site.buildingKey == c.building);
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
                if (site.mapId == c.mapId && DungeonDoor(c, out x, out z))
                    Add(c, name, "quest NPC in " + site.locationName, Dfb.FIND_WORLD, 0, x, z, rank);
                else
                    Add(c, name, "quest NPC in " + site.locationName, Dfb.FIND_ELSEWHERE, 0, 0, 0, rank);
                return;
            }
            if (site.buildingKey != 0)
                InBuilding(c, name, site.buildingName, town, site.buildingKey, rank, "quest NPC ");
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

        // Every building's residents in the towns here, named as StaticNPC names them (SetLayoutData, GetDisplayName).
        static void Residents(Context c)
        {
            int scanned = 0;
            for (int t = 0; t < c.towns.Count; t++)
                scanned += Residents(c, t);
            c.bridge.LogLine("findnpc: residents scanned " + scanned + " in " + c.towns.Count + " locations");
        }

        static int Residents(Context c, int town)
        {
            DFLocation location = c.towns[town];
            int width = location.Exterior.ExteriorData.Width, height = location.Exterior.ExteriorData.Height;
            if (width <= 0 || height <= 0)
                return 0;
            DFBlock[] blocks = RMBLayout.GetLocationBuildingData(location);
            int locationIndex = location.LocationIndex;
            NameHelper.BankTypes bank = c.gps.GetNameBankOfCurrentRegion();
            var factions =c.game.PlayerEntity.FactionData;
            uint keep = DFRandom.Seed;
            int scanned = 0;
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
                            if (town == 0 && c.inBuilding && key == c.building)
                                continue; // LoadedNpcs has them, with who is present
                            foreach (DFBlock.RmbBlockPeopleRecord p in people)
                            {
                                scanned++;
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
                                    InBuilding(c, name, null, town, key, rank, "");
                            }
                        }
                    }
            }
            finally { DFRandom.Seed = keep; }
            return scanned;
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
                        InBuilding(c, p.Name, null, 0, key, rank, "townsperson ");
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
