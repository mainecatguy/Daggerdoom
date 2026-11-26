// Doomerfall: keeps the item piles the player drops through Daggerfall's inventory in the location record. Runs only in
// a bridge session.
//
// A dropped pile is a DaggerfallLoot with customDrop set. Daggerfall itself keeps one only in its scene cache, which it
// wipes on every map pixel change (PlayerGPS) and never fills for dungeons, so without this a dropped pile vanishes.
// The scene cache stays short-lived; the location record (DoomerfallLocations, the place's Daggerfall section) is the
// permanent copy.
//
// Indoors, the piles in the dungeon or building are the place's piles: the record follows the scene every poll, after
// the piles the record had were put back on entry. Outdoors, piles hang under the streaming target and each belongs to
// the exterior chunk its position is in ("O<chunk x>,<chunk y>"). A recorded pile near the player that is missing from
// the scene is put back; one is forgotten only once it was seen empty (Daggerfall removes an emptied pile). Anything
// that is already in the scene with the pile's LoadID (Daggerfall's own save or scene cache put it back, or a town
// stayed loaded) is the pile, so nothing is doubled. DoomerfallItems then lists it to Doom as before.

using System.Collections.Generic;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallPiles : MonoBehaviour
    {
        const float PollSeconds = 0.25f;
        const int ChunkUnits = Dfb.CHUNK_UNITS;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallLocations locations;
        float nextPoll;
        int restoredSpace;                 // the indoor space whose recorded piles were put back
        ulong lastHash;
        readonly List<DaggerfallLoot> found = new List<DaggerfallLoot>();
        // Outdoors: piles seen this stint, with whether they were empty when last seen.
        readonly Dictionary<ulong, bool> seenEmpty = new Dictionary<ulong, bool>();

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, DoomerfallLocations ledger)
        {
            bridge = owner;
            sync = positionSync;
            locations = ledger;
            locations.BeforeWrite = () => Poll(true);
        }

        void Update()
        {
            if (Time.unscaledTime < nextPoll)
                return;
            nextPoll = Time.unscaledTime + PollSeconds;
            Poll(false);
        }

        static bool IsDropped(DaggerfallLoot loot)
        {
            return loot && loot.customDrop && loot.ContainerType == LootContainerTypes.DroppedLoot;
        }

        void Poll(bool saving)
        {
            if (sync.LoadRunning || !sync.InGame || !sync.Engaged || !GameManager.HasInstance)
                return;
            GameManager game = GameManager.Instance;
            PlayerEnterExit enter = game.PlayerEnterExit;
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return;
            int map = game.PlayerGPS.CurrentLocation.MapTableData.MapId;
            if (enter.IsPlayerInside)
            {
                seenEmpty.Clear();
                Transform space = enter.IsPlayerInsideDungeon ? (enter.Dungeon ? enter.Dungeon.transform : null) : (enter.Interior ? enter.Interior.transform : null);
                if (!space)
                    return;
                uint kind = enter.IsPlayerInsideDungeon ? Dfb.PLACE_DUNGEON : Dfb.PLACE_INTERIOR;
                int key = enter.IsPlayerInsideDungeon ? 0 : enter.BuildingDiscoveryData.buildingKey;
                Indoor(space, kind, map, key, saving);
            }
            else
            {
                restoredSpace = 0;
                Outdoor(game, saving);
            }
        }

        void Indoor(Transform space, uint kind, int map, int key, bool saving)
        {
            space.GetComponentsInChildren(true, found);
            if (space.GetInstanceID() != restoredSpace)
            {
                restoredSpace = space.GetInstanceID();
                lastHash = 0;
                int back = 0;
                List<DoomerfallLocations.PileData> recorded = locations.Piles(kind, map, key);
                foreach (DoomerfallLocations.PileData pile in recorded)
                    if (!found.Exists(l => IsDropped(l) && l.LoadID == pile.loadId))
                    {
                        Create(pile, space.TransformPoint(new Vector3(pile.x, pile.z, pile.y) * MeshReader.GlobalScale));
                        back++;
                    }
                bridge.LogLine(string.Format("piles: {0} {1}:{2} has {3} dropped piles in its record, {4} put back", kind == Dfb.PLACE_DUNGEON ? "dungeon" : "building", map, key, recorded.Count, back));
                if (back > 0)
                    space.GetComponentsInChildren(true, found);
            }
            List<DoomerfallLocations.PileData> now = new List<DoomerfallLocations.PileData>();
            ulong hash = 17;
            foreach (DaggerfallLoot loot in found)
            {
                if (!IsDropped(loot) || loot.Items.Count == 0)
                    continue;
                Vector3 local = space.InverseTransformPoint(loot.transform.position) / MeshReader.GlobalScale;
                hash = Hash(hash, loot, local);
                now.Add(new DoomerfallLocations.PileData { loadId = loot.LoadID, x = local.x, y = local.z, z = local.y, archive = loot.TextureArchive, record = loot.TextureRecord });
            }
            if (hash == lastHash && !saving)
                return;
            lastHash = hash;
            foreach (DoomerfallLocations.PileData pile in now)
                pile.items = found.Find(l => IsDropped(l) && l.LoadID == pile.loadId).Items.SerializeItems();
            locations.SetPiles(kind, map, key, now);
            bridge.LogLine(string.Format("piles: record of {0} {1}:{2} now has {3} dropped piles{4}", kind == Dfb.PLACE_DUNGEON ? "dungeon" : "building", map, key, now.Count, saving ? " (saving)" : string.Empty));
        }

        static ulong Hash(ulong hash, DaggerfallLoot loot, Vector3 local)
        {
            hash = (hash ^ loot.LoadID) * 1099511628211UL;
            hash = (hash ^ (ulong)(uint)Mathf.RoundToInt(local.x * 4) ^ ((ulong)(uint)Mathf.RoundToInt(local.z * 4) << 32)) * 1099511628211UL;
            for (int i = 0; i < loot.Items.Count; i++)
            {
                DaggerfallUnityItem item = loot.Items.GetItem(i);
                hash = (hash ^ item.UID) * 1099511628211UL;
                hash = (hash ^ (ulong)(uint)item.stackCount) * 1099511628211UL;
            }
            return hash;
        }

        // Exterior positions: Daggerfall world units from the scene position, through the player's known world position.
        static void WorldOf(GameManager game, Vector3 position, out double wx, out double wz, out float height)
        {
            Vector3 player = game.PlayerObject.transform.position;
            wx = game.PlayerGPS.WorldX + (position.x - player.x) * StreamingWorld.SceneMapRatio;
            wz = game.PlayerGPS.WorldZ + (position.z - player.z) * StreamingWorld.SceneMapRatio;
            height = (position.y - game.StreamingWorld.WorldCompensation.y) / MeshReader.GlobalScale;
        }

        static Vector3 SceneOf(GameManager game, double wx, double wz, float height)
        {
            Vector3 player = game.PlayerObject.transform.position;
            return new Vector3(player.x + (float)((wx - game.PlayerGPS.WorldX) / StreamingWorld.SceneMapRatio),
                height * MeshReader.GlobalScale + game.StreamingWorld.WorldCompensation.y,
                player.z + (float)((wz - game.PlayerGPS.WorldZ) / StreamingWorld.SceneMapRatio));
        }

        void Outdoor(GameManager game, bool saving)
        {
            if (!game.StreamingTarget)
                return;
            // A dropped pile is a direct child of the streaming target (GameObjectHelper.CreateDroppedLootContainer), so
            // the towns and terrain under it need no search.
            Dictionary<ulong, DaggerfallLoot> live = new Dictionary<ulong, DaggerfallLoot>();
            foreach (Transform child in game.StreamingTarget.transform)
            {
                DaggerfallLoot loot = child.GetComponent<DaggerfallLoot>();
                if (IsDropped(loot))
                    live[loot.LoadID] = loot;
            }
            int px = Mathf.FloorToInt(game.PlayerGPS.WorldX / (float)ChunkUnits), py = Mathf.FloorToInt(game.PlayerGPS.WorldZ / (float)ChunkUnits);

            // Every recorded exterior pile: kept, put back, or forgotten once it was seen empty.
            Dictionary<long, List<DoomerfallLocations.PileData>> chunks = new Dictionary<long, List<DoomerfallLocations.PileData>>();
            List<KeyValuePair<int, int>> recordedChunks = new List<KeyValuePair<int, int>>();
            foreach (KeyValuePair<DoomerfallLocations.Place, List<DoomerfallLocations.PileData>> entry in locations.PilesOfKind(Dfb.PLACE_CHUNK))
                recordedChunks.Add(new KeyValuePair<int, int>(entry.Key.mapId, entry.Key.key));
            int back = 0, forgotten = 0;
            foreach (KeyValuePair<int, int> chunk in recordedChunks)
                foreach (DoomerfallLocations.PileData pile in locations.Piles(Dfb.PLACE_CHUNK, chunk.Key, chunk.Value))
                {
                    if (live.ContainsKey(pile.loadId))
                        continue;   // still in the scene: the scan below records it where it is now
                    bool empty;
                    if (seenEmpty.TryGetValue(pile.loadId, out empty) && empty)
                    {
                        forgotten++;
                        continue;
                    }
                    if (System.Math.Abs(chunk.Key - px) <= 1 && System.Math.Abs(chunk.Value - py) <= 1)
                    {
                        live[pile.loadId] = Create(pile, SceneOf(game, (double)chunk.Key * ChunkUnits + pile.x, (double)chunk.Value * ChunkUnits + pile.y, pile.z));
                        back++;
                        continue;
                    }
                    Add(chunks, chunk.Key, chunk.Value, pile);   // far away: kept as recorded
                }

            ulong hash = (ulong)(17 + recordedChunks.Count);
            foreach (DaggerfallLoot loot in live.Values)
            {
                seenEmpty[loot.LoadID] = loot.Items.Count == 0;
                if (loot.Items.Count == 0)
                    continue;
                double wx, wz;
                float height;
                WorldOf(game, loot.transform.position, out wx, out wz, out height);
                int cx = (int)System.Math.Floor(wx / ChunkUnits), cy = (int)System.Math.Floor(wz / ChunkUnits);
                Vector3 local = new Vector3((float)(wx - (double)cx * ChunkUnits), height, (float)(wz - (double)cy * ChunkUnits));
                hash = Hash(hash, loot, local);
                Add(chunks, cx, cy, new DoomerfallLocations.PileData { loadId = loot.LoadID, x = local.x, y = local.z, z = local.y, archive = loot.TextureArchive, record = loot.TextureRecord, items = null });
            }
            hash ^= (ulong)forgotten * 31 + (ulong)back;
            if (hash == lastHash && !saving && back == 0 && forgotten == 0)
                return;
            lastHash = hash;
            HashSet<long> touched = new HashSet<long>();
            foreach (KeyValuePair<int, int> chunk in recordedChunks)
                touched.Add(ChunkKey(chunk.Key, chunk.Value));
            foreach (long k in chunks.Keys)
                touched.Add(k);
            int total = 0;
            foreach (long k in touched)
            {
                int cx = (int)(k >> 32), cy = (int)(uint)k;
                List<DoomerfallLocations.PileData> list;
                if (!chunks.TryGetValue(k, out list))
                    list = new List<DoomerfallLocations.PileData>();
                foreach (DoomerfallLocations.PileData pile in list)
                {
                    DaggerfallLoot loot;
                    if (pile.items == null && live.TryGetValue(pile.loadId, out loot))
                        pile.items = loot.Items.SerializeItems();
                }
                locations.SetPiles(Dfb.PLACE_CHUNK, cx, cy, list);
                total += list.Count;
            }
            bridge.LogLine(string.Format("piles: exterior record now has {0} dropped piles in {1} chunks around chunk {2},{3}: {4} put back, {5} forgotten after being emptied{6}",
                total, chunks.Count, px, py, back, forgotten, saving ? " (saving)" : string.Empty));
        }

        static long ChunkKey(int cx, int cy)
        {
            return ((long)cx << 32) | (uint)cy;
        }

        static void Add(Dictionary<long, List<DoomerfallLocations.PileData>> chunks, int cx, int cy, DoomerfallLocations.PileData pile)
        {
            List<DoomerfallLocations.PileData> list;
            if (!chunks.TryGetValue(ChunkKey(cx, cy), out list))
                chunks[ChunkKey(cx, cy)] = list = new List<DoomerfallLocations.PileData>();
            list.Add(pile);
        }

        // Daggerfall's own way back for a dropped pile (SerializableStateManager does the same on load).
        DaggerfallLoot Create(DoomerfallLocations.PileData pile, Vector3 position)
        {
            DaggerfallLoot loot = GameObjectHelper.CreateDroppedLootContainer(GameManager.Instance.PlayerObject, pile.loadId, pile.archive, pile.record);
            loot.transform.position = position;
            loot.Items.Clear();
            if (pile.items != null && pile.items.Length > 0)
                loot.Items.DeserializeItems(pile.items);
            bridge.LogLine(string.Format("piles: put back dropped pile {0:x16} with {1} items", pile.loadId, loot.Items.Count));
            return loot;
        }
    }
}
