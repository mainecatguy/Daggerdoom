// Doomerfall: Daggerfall's side of monster deaths. Runs only in a bridge session.
//
// A monster id is tag (3 bits, value 5) | placement hash (49) | pack member (12). Doom reports each death once
// per id. This ledger makes it count once across saves, loads, and re-entry. It updates the quest foe, rolls
// the drop with Daggerfall's loot tables, and keeps the drop so a rebuilt dungeon can show it again.

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Utility;
using FullSerializer;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMonsters : MonoBehaviour
    {
        const float PollSeconds = 0.25f;
        const float DoomPerDaggerfall = 0.75f;
        const float PopupSeconds = 4f;
        const string LedgerFile = "DoomerfallMonsters.json";
        const ulong PlacementMask = (1UL << (int)(Dfb.MONSTER_TAG_SHIFT - Dfb.MONSTER_MEMBER_BITS)) - 1;
        const ulong MemberMask = (1UL << (int)Dfb.MONSTER_MEMBER_BITS) - 1;
        const int RandomEnemyRecord = 15, FixedEnemyRecord = 16, EditorArchive = 199;

        public sealed class Death
        {
            public int mapId;
            public int x, y, z;          // Daggerfall units within the dungeon, whole so a rebuilt pile keeps its identity.
            public bool rolled;
            public ItemData_v1[] drop;
        }

        [fsObject("v1")]
        public sealed class LedgerData
        {
            public Dictionary<string, Death> deaths = new Dictionary<string, Death>();
        }


        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        LedgerData ledger = new LedgerData();
        readonly Dictionary<ulong, MobileTypes> placements = new Dictionary<ulong, MobileTypes>();
        readonly HashSet<ulong> piled = new HashSet<ulong>();
        readonly List<DfbMonster> rows = new List<DfbMonster>();
        int placementsMap = -1, placementsLevel = 1, lastSpace;
        uint generation;
        ulong lastHash;
        bool resend;
        float nextPoll, popupUntil;
        string testQuest;
        bool reportQuest;
        int lastReportedKills = -1;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfmonsterquest");
            if (at >= 0 && at + 1 < args.Length)
                testQuest = args[at + 1];
            reportQuest = at >= 0 || Array.IndexOf(args, "-dfmonsterreport") >= 0;
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame += OnStartGame;
        }

        void OnDestroy()
        {
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame -= OnStartGame;
        }

        void OnStartGame(object sender, EventArgs e)
        {
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return;
            ledger = new LedgerData();
            ForgetSpace();
        }

        // A held new character's dungeon exists before OnStartGame fires, so the last character's dead list must go first.
        internal void ForgetWorld()
        {
            ledger = new LedgerData();
            ForgetSpace();
        }

        void ForgetSpace()
        {
            piled.Clear();
            lastHash = 0;
            resend = true;
        }

        internal void OnRequest()
        {
            resend = true;
        }

        // Must equal EnemyRoster.Hash in the dungeon converter.
        internal static ulong PlacementHash(int mapId, string block, int blockX, int blockZ, int x, int y, int z, int record, int mobileId)
        {
            ulong h = 14695981039346656037UL;
            foreach (long v in new long[] { mapId, blockX, blockZ, x, y, z, record, mobileId })
                h = Mix(h, v);
            foreach (char c in block)
                h = Mix(h, c);
            h ^= h >> 32;
            h *= 0x9E3779B97F4A7C15UL;
            h ^= h >> 29;
            return h;
        }

        static ulong Mix(ulong h, long v)
        {
            for (int k = 0; k < 8; k++)
            {
                h ^= (byte)(v >> (8 * k));
                h *= 1099511628211UL;
            }
            return h;
        }

        static ulong MakeId(ulong hash, int member)
        {
            return ((ulong)Dfb.MONSTER_TAG << (int)Dfb.MONSTER_TAG_SHIFT) | ((hash & PlacementMask) << (int)Dfb.MONSTER_MEMBER_BITS) | ((ulong)member & MemberMask);
        }

        static ulong FoeHash(ulong questUid, string symbol)
        {
            ulong h = Mix(14695981039346656037UL, (long)questUid);
            foreach (char c in symbol)
                h = Mix(h, c);
            h ^= h >> 32;
            h *= 0x9E3779B97F4A7C15UL;
            return h ^ (h >> 29);
        }

        static string Key(ulong id)
        {
            return id.ToString("x16");
        }

        void Update()
        {
            ClosePopups();
            if (Time.unscaledTime < nextPoll && !resend)
                return;
            nextPoll = Time.unscaledTime + PollSeconds;
            if (sync.LoadRunning || !GameManager.HasInstance || !sync.InGame)
                return;
            RunTestQuest();
            ReportQuest();

            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            if (peer.worldContext != Dfb.WORLD_DUNGEON)
                return;
            Transform space = sync.ItemSpace(ref peer);
            if (!space || !GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon)
                return;
            int map = GameManager.Instance.PlayerGPS.CurrentLocation.MapTableData.MapId;
            if (map != peer.spaceTarget)
                return;
            if (space.GetInstanceID() != lastSpace)
            {
                lastSpace = space.GetInstanceID();
                ForgetSpace();
            }
            BuildPlacements(map);
            ShowDrops(space, map);
            ulong hash = CollectRows(map);
            if (hash == lastHash && !resend)
                return;
            lastHash = hash;
            resend = false;
            Publish(ref peer);
        }

        // Daggerfall pauses behind a quest message after a kill, and Doom cannot show those windows yet.
        void ClosePopups()
        {
            if (Time.unscaledTime >= popupUntil || !DaggerfallUI.Instance)
                return;
            DaggerfallMessageBox box = DaggerfallUI.UIManager.TopWindow as DaggerfallMessageBox;
            if (box == null)
                return;
            box.CloseWindow();
            bridge.LogLine("monsters: closed a quest message Doom cannot show yet");
        }

        void BuildPlacements(int map)
        {
            if (placementsMap == map)
                return;
            placementsMap = map;
            placements.Clear();
            DaggerfallDungeon dungeon = GameManager.Instance.PlayerEnterExit.Dungeon;
            DFLocation location = dungeon.Summary.LocationData;
            int areaLevel = placementsLevel = DoomerfallDrops.AreaLevel(location);
            DoomerfallDrops.EnemyPicker picker = new DoomerfallDrops.EnemyPicker(location.Dungeon.RecordElement.Header.LocationId,
                dungeon.Summary.DungeonType, areaLevel, dungeon.RandomMonsterVariance, DaggerfallUnity.Settings.AlternateRandomEnemySelection);
            foreach (DFLocation.DungeonBlock block in location.Dungeon.Blocks)
            {
                DFBlock data = DaggerfallUnity.Instance.ContentReader.BlockFileReader.GetBlock(block.BlockName);
                if (data.RdbBlock.ObjectRootList == null)
                    continue;
                foreach (DFBlock.RdbObjectRoot group in data.RdbBlock.ObjectRootList)
                {
                    if (group.RdbObjects == null)
                        continue;
                    foreach (DFBlock.RdbObject obj in group.RdbObjects)
                    {
                        if (obj.Type != DFBlock.RdbResourceTypes.Flat || obj.Resources.FlatResource.TextureArchive != EditorArchive)
                            continue;
                        int record = obj.Resources.FlatResource.TextureRecord;
                        if (record != RandomEnemyRecord && record != FixedEnemyRecord)
                            continue;
                        int mobile = obj.Resources.FlatResource.FactionOrMobileId;
                        ulong hash = PlacementHash(map, block.BlockName, block.X, block.Z, obj.XPos, obj.YPos, obj.ZPos, record, mobile);
                        placements[hash & PlacementMask] = record == RandomEnemyRecord
                            ? picker.PickRandom(hash, obj.Resources.FlatResource.Flags, obj.YPos, block.WaterLevel)
                            : DoomerfallDrops.PickFixed(mobile, obj.Resources.FlatResource.IsCustomData, obj.YPos, block.WaterLevel);
                    }
                }
            }
            bridge.LogLine(string.Format("monsters: {0} has {1} placements at area level {2} ({3})", location.Name, placements.Count, areaLevel, DoomerfallAreaLevels.Status()));
        }

        // Every foe assigned to a marker in this dungeon, by id.
        void ForEachQuestFoe(int map, Action<Foe, QuestMarker, ulong> visit)
        {
            SiteLink[] links = QuestMachine.Instance.GetSiteLinks(SiteTypes.Dungeon, map);
            if (links == null)
                return;
            HashSet<ulong> seen = new HashSet<ulong>();
            foreach (SiteLink link in links)
            {
                Quest quest = QuestMachine.Instance.GetQuest(link.questUID);
                Place place = quest != null ? quest.GetPlace(link.placeSymbol) : null;
                if (place == null)
                    continue;
                VisitMarker(quest, place.SiteDetails.selectedMarker, seen, visit);
                if (place.SiteDetails.questSpawnMarkers != null)
                    foreach (QuestMarker marker in place.SiteDetails.questSpawnMarkers)
                        VisitMarker(quest, marker, seen, visit);
            }
        }

        static void VisitMarker(Quest quest, QuestMarker marker, HashSet<ulong> seen, Action<Foe, QuestMarker, ulong> visit)
        {
            if (marker.targetResources == null)
                return;
            foreach (Symbol target in marker.targetResources)
            {
                Foe foe = quest.GetResource(target) as Foe;
                if (foe == null)
                    continue;
                ulong hash = FoeHash(quest.UID, foe.Symbol.Name);
                if (seen.Add(hash))
                    visit(foe, marker, hash);
            }
        }

        Foe FindFoe(ulong id)
        {
            ulong want = (id >> (int)Dfb.MONSTER_MEMBER_BITS) & PlacementMask;
            foreach (ulong uid in QuestMachine.Instance.GetAllActiveQuests())
            {
                Quest quest = QuestMachine.Instance.GetQuest(uid);
                if (quest == null)
                    continue;
                foreach (QuestResource resource in quest.GetAllResources(typeof(Foe)))
                    if ((FoeHash(uid, resource.Symbol.Name) & PlacementMask) == want)
                        return (Foe)resource;
            }
            return null;
        }

        ulong CollectRows(int map)
        {
            rows.Clear();
            float units = DoomPerDaggerfall / MeshReader.GlobalScale;
            ForEachQuestFoe(map, (foe, marker, hash) =>
            {
                if (foe.IsHidden)
                    return;
                Vector3 local = new Vector3(marker.dungeonX * RDBLayout.RDBSide, 0, marker.dungeonZ * RDBLayout.RDBSide) + marker.flatPosition;
                for (int member = 0; member < foe.SpawnCount; member++)
                {
                    ulong id = MakeId(hash, member);
                    if (!ledger.deaths.ContainsKey(Key(id)))
                        rows.Add(new DfbMonster { id = id, state = Dfb.MONSTER_PLACE, x = local.x * units, y = local.z * units, z = local.y * units });
                }
            });
            foreach (KeyValuePair<string, Death> death in ledger.deaths)
                if (death.Value.mapId == map)
                    rows.Add(new DfbMonster { id = Convert.ToUInt64(death.Key, 16), state = Dfb.MONSTER_DEAD });
            ulong hashOut = 17;
            foreach (DfbMonster row in rows)
                hashOut = ((hashOut ^ row.id) * 1099511628211UL) ^ row.state;
            return hashOut;
        }

        void Publish(ref DfbUzState peer)
        {
            generation++;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_MONSTERS_BEGIN;
            e.tic = (uint)Time.frameCount;
            e.worldItems.generation = generation;
            e.worldItems.context = peer.worldContext;
            e.worldItems.target = peer.spaceTarget;
            e.worldItems.count = (uint)rows.Count;
            bridge.Send(ref e);
            foreach (DfbMonster row in rows)
            {
                DfbEvent item = default(DfbEvent);
                item.kind = Dfb.KIND_MONSTER;
                item.tic = (uint)Time.frameCount;
                item.monster = row;
                item.monster.generation = generation;
                bridge.Send(ref item);
            }
            e.kind = Dfb.KIND_MONSTERS_END;
            bridge.Send(ref e);
            bridge.LogLine(string.Format("monsters: list {0} has {1} rows for target {2}", generation, rows.Count, peer.spaceTarget));
        }

        internal void OnDeath(ulong id, int target, float x, float y, float z)
        {
            string key = Key(id);
            if (ledger.deaths.ContainsKey(key))
            {
                bridge.LogLine("monsters: repeat death ignored " + key);
                return;
            }
            ledger.deaths[key] = new Death
            {
                mapId = target,
                x = Mathf.RoundToInt(x / DoomPerDaggerfall),
                y = Mathf.RoundToInt(y / DoomPerDaggerfall),
                z = Mathf.RoundToInt(z / DoomPerDaggerfall),
            };
            Foe foe = FindFoe(id);
            if (foe != null)
            {
                foe.SetInjured();
                foe.IncrementKills();
                popupUntil = Time.unscaledTime + PopupSeconds;
            }
            bridge.LogLine(string.Format("monsters: death {0} target {1}, quest foe {2}, kills {3}", key, target, foe != null ? foe.Symbol.Name : "none", foe != null ? foe.KillCount : 0));
            resend = true;
        }

        void ShowDrops(Transform space, int map)
        {
            foreach (KeyValuePair<string, Death> entry in ledger.deaths)
            {
                Death death = entry.Value;
                if (death.mapId != map)
                    continue;
                ulong id = Convert.ToUInt64(entry.Key, 16);
                if (!death.rolled)
                    Roll(death, id);
                if (death.drop == null || death.drop.Length == 0 || !piled.Add(id))
                    continue;
                float scale = MeshReader.GlobalScale;
                Vector3 at = space.TransformPoint(new Vector3(death.x * scale, death.z * scale, death.y * scale));
                int[] icons = DaggerfallLootDataTables.randomTreasureIconIndices;
                // LoadID 0 until the serializer is gone: this ledger, not Daggerfall's scene save, keeps the pile.
                DaggerfallLoot loot = GameObjectHelper.CreateLootContainer(LootContainerTypes.DroppedLoot, InventoryContainerImages.Chest, at, space,
                    DaggerfallLootDataTables.randomTreasureArchive, icons[(int)(id % (ulong)icons.Length)]);
                SerializableLootContainer serializer = loot.GetComponent<SerializableLootContainer>();
                if (serializer)
                    DestroyImmediate(serializer);
                loot.LoadID = id;
                loot.Items.DeserializeItems(death.drop);
                bridge.LogLine(string.Format("monsters: drop for {0} has {1} items", entry.Key, loot.Items.Count));
            }
        }

        // Rolled once. The result is saved, so a load or a rebuilt dungeon cannot roll it again.
        void Roll(Death death, ulong id)
        {
            death.rolled = true;
            MobileTypes type = MobileTypes.None;
            DaggerfallUnityItem[] queued = null;
            Foe foe = FindFoe(id);
            int lootSeed;
            if (foe != null)
            {
                type = foe.FoeType;
                queued = foe.GetClonedItemQueue();
                lootSeed = QuestFoeLootSeed(death.mapId, foe, id);
            }
            else
            {
                // A placement id is built only from the dungeon, block, marker, and pack member, so it is a fixed fact.
                lootSeed = LootSeed.Of(LootSeed.DoomerfallEnemy, null, (long)(id & ((1UL << (int)Dfb.MONSTER_TAG_SHIFT) - 1)));
                if (!placements.TryGetValue((id >> (int)Dfb.MONSTER_MEMBER_BITS) & PlacementMask, out type))
                    bridge.LogLine("monsters: no Daggerfall placement for " + Key(id) + ", so no drop");
            }
            ItemCollection items = DoomerfallDrops.RollEnemy(type, placementsLevel, queued, lootSeed);
            death.drop = items.SerializeItems();
            bridge.LogLine(string.Format("monsters: rolled {0} as {1}, {2} items", Key(id), type, items.Count));
        }

        // A quest's UID differs in every save, so a foe's loot seed uses the dungeon, the quest's name, the foe's
        // symbol, and the pack member instead.
        static int QuestFoeLootSeed(int mapId, Foe foe, ulong id)
        {
            string quest = foe.ParentQuest != null ? foe.ParentQuest.QuestName : string.Empty;
            return LootSeed.Of(LootSeed.QuestFoe, quest + "/" + foe.Symbol.Name, mapId, (long)(id & MemberMask));
        }

        // Test only: starts a real quest whose random dungeon resolves to the one at this location.
        void RunTestQuest()
        {
            if (string.IsNullOrEmpty(testQuest))
                return;
            GameManager game = GameManager.Instance;
            if (game.PlayerEnterExit.IsPlayerInside || !game.PlayerGPS.HasCurrentLocation || !game.PlayerGPS.CurrentLocation.HasDungeon)
                return;
            string name = testQuest;
            testQuest = null;
            DFLocation location = game.PlayerGPS.CurrentLocation;
            Quest quest = QuestMachine.Instance.ParseQuest(name, QuestMachine.Instance.GetQuestSourceText(name));
            Place place = quest != null ? quest.GetPlace(new Symbol("_mondung_")) : null;
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
                questUID = quest.UID,
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
            QuestMachine.Instance.StartQuest(quest);
            bridge.LogLine(string.Format("monsters: started quest {0} uid {1}; rolled {2}, test site {3} with {4} spawn markers", name, quest.UID, rolled, location.Name, site.questSpawnMarkers.Length));
        }

        void ReportQuest()
        {
            if (!reportQuest)
                return;
            Quest quest = null;
            foreach (ulong uid in QuestMachine.Instance.GetAllActiveQuests())
            {
                Quest candidate = QuestMachine.Instance.GetQuest(uid);
                if (candidate != null && candidate.GetFoe(new Symbol("_imp_")) != null)
                    quest = candidate;
            }
            if (quest == null)
                return;
            Foe foe = quest.GetFoe(new Symbol("_imp_"));
            Task task = quest.GetTask(new Symbol("_mondead_"));
            bool triggered = task != null && task.IsTriggered;
            int state = foe.KillCount * 2 + (triggered ? 1 : 0);
            if (state == lastReportedKills)
                return;
            lastReportedKills = state;
            bridge.LogLine(string.Format("monsters: quest {0} kills {1}, injured {2}, killed task triggered {3}", quest.UID, foe.KillCount, foe.InjuredTrigger, triggered));
        }

        internal void WriteLedger(string folder)
        {
            File.WriteAllText(Path.Combine(folder, LedgerFile), SaveLoadManager.Serialize(typeof(LedgerData), ledger, false), new UTF8Encoding(false));
        }

        internal void ReadLedger(string folder)
        {
            string path = Path.Combine(folder, LedgerFile);
            ledger = File.Exists(path) ? (LedgerData)SaveLoadManager.Deserialize(typeof(LedgerData), File.ReadAllText(path)) ?? new LedgerData() : new LedgerData();
            if (ledger.deaths == null)
                ledger.deaths = new Dictionary<string, Death>();
            ForgetSpace();
            bridge.LogLine("monsters: ledger restored with " + ledger.deaths.Count + " deaths");
        }
    }
}
