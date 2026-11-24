// Doomerfall: Daggerfall's side of world items and containers. Runs only in a bridge session.
//
// Daggerfall stays the authority. It lists the real loot containers in the space the player is in. Doom
// draws the piles, aims Use at them and at furniture containers, and asks. Daggerfall then opens its own
// window for that container, exactly as its activation would, and Doom shows the window.
//
// Daggerfall rebuilds and rerolls a dungeon on every entry, so a small ledger records each container the
// player has opened and what is left in it. It travels inside the save bundle.

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using FullSerializer;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallItems : MonoBehaviour
    {
        const float PollSeconds = 0.25f;
        const float DoomPerDaggerfall = 0.75f;
        // Daggerfall's treasure reach, doubled because the hidden player trails Doom by a few frames.
        const float MaxReach = PlayerActivate.TreasureActivationDistance * 2f;
        const float WindowAnswerSeconds = 3f;
        const string LedgerFile = "DoomerfallItems.json";

        [fsObject("v1")]
        public sealed class LedgerData
        {
            public Dictionary<string, ItemData_v1[]> piles = new Dictionary<string, ItemData_v1[]>();
            // Shop shelves and house containers restock by date, so their stocked date is kept with their contents.
            public Dictionary<string, int> stocked = new Dictionary<string, int>();
        }

        struct Pile
        {
            public DaggerfallLoot loot;
            public string key;
            public Vector3 local;
        }

        struct Known
        {
            public DaggerfallLoot loot;
            public Vector3 local;
            public Bounds box; // Furniture only: space-local bounds, Daggerfall units.
            public ulong id;
        }

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        LedgerData ledger = new LedgerData();
        readonly Dictionary<ulong, Pile> live = new Dictionary<ulong, Pile>();
        readonly HashSet<int> restored = new HashSet<int>();
        readonly Dictionary<int, Known> roster = new Dictionary<int, Known>();
        readonly List<int> gone = new List<int>();
        readonly List<DaggerfallLoot> found = new List<DaggerfallLoot>();
        readonly List<DfbWorldItem> rows = new List<DfbWorldItem>();
        readonly List<DfbWorldContainer> boxes = new List<DfbWorldContainer>();
        uint generation;
        ulong lastHash;
        int lastSpace;
        bool resend;
        float nextPoll;
        Pile window;          // The container Doom was told to open a window for, then the one whose window is open.
        float windowAnswerBy;
        bool windowOpen;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame += OnStartGame;
        }

        void OnDestroy()
        {
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame -= OnStartGame;
        }

        // A new character starts with an untouched world. A loaded game replaces the ledger in ReadLedger.
        void OnStartGame(object sender, EventArgs e)
        {
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return;
            ledger = new LedgerData();
            ForgetSpace();
        }

        // A held new character's dungeon exists before OnStartGame fires, so the last character's ledger must go first.
        internal void ForgetWorld()
        {
            ledger = new LedgerData();
            ForgetSpace();
        }

        void ForgetSpace()
        {
            live.Clear();
            roster.Clear();
            restored.Clear();
            lastHash = 0;
            resend = true;
            if (!windowOpen)
                window = default(Pile);
        }

        internal void OnRequest()
        {
            resend = true;
        }

        void Update()
        {
            if (Time.unscaledTime < nextPoll && !resend)
                return;
            nextPoll = Time.unscaledTime + PollSeconds;
            if (sync.LoadRunning)
                return;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            Transform space = sync.ItemSpace(ref peer);
            if (!space)
                return;
            if (space.GetInstanceID() != lastSpace)
            {
                lastSpace = space.GetInstanceID();
                ForgetSpace();
            }
            ulong hash = Collect(space);
            if (hash == lastHash && !resend)
                return;
            lastHash = hash;
            resend = false;
            Publish(ref peer);
        }

        static string PlaceKey()
        {
            GameManager game = GameManager.Instance;
            int map = game.PlayerGPS.CurrentLocation.MapTableData.MapId;
            return game.PlayerEnterExit.IsPlayerInsideDungeon ? "D" + map : "B" + map + ":" + game.PlayerEnterExit.BuildingDiscoveryData.buildingKey;
        }

        // A repeated dungeon block repeats its LoadIDs, so the position inside the space is part of the identity.
        static ulong PileId(ulong loadId, Vector3 local)
        {
            const ulong prime = 1099511628211UL;
            ulong h = 14695981039346656037UL;
            ulong[] parts = { loadId, (ulong)(long)Mathf.RoundToInt(local.x / MeshReader.GlobalScale), (ulong)(long)Mathf.RoundToInt(local.z / MeshReader.GlobalScale) };
            foreach (ulong part in parts)
                for (int shift = 0; shift < 64; shift += 8)
                    h = (h ^ ((part >> shift) & 0xff)) * prime;
            return h == 0 ? 1 : h;
        }

        // Shop shelves and house containers are furniture models with no sprite. Doom aims at their box.
        static bool IsFurniture(DaggerfallLoot loot)
        {
            return loot.ContainerType == LootContainerTypes.ShopShelves || loot.ContainerType == LootContainerTypes.HouseContainers;
        }

        static Bounds LocalBounds(Transform space, DaggerfallLoot loot)
        {
            Bounds world;
            Collider collider = loot.GetComponent<Collider>();
            Renderer renderer = loot.GetComponent<Renderer>();
            if (collider)
                world = collider.bounds;
            else if (renderer)
                world = renderer.bounds;
            else
                world = new Bounds(loot.transform.position, Vector3.one * 0.5f);
            Bounds local = new Bounds(space.InverseTransformPoint(world.center), Vector3.zero);
            for (int i = 0; i < 8; i++)
                local.Encapsulate(space.InverseTransformPoint(world.center + Vector3.Scale(world.extents, new Vector3((i & 1) != 0 ? 1 : -1, (i & 2) != 0 ? 1 : -1, (i & 4) != 0 ? 1 : -1))));
            return local;
        }

        ulong Collect(Transform space)
        {
            string place = PlaceKey();
            live.Clear();
            rows.Clear();
            boxes.Clear();
            // A pile's object can briefly leave the space's hierarchy while staying intact, so each pile is
            // remembered for the whole visit. Only emptying or destroying it takes it off the list.
            space.GetComponentsInChildren(true, found);
            foreach (DaggerfallLoot candidate in found)
            {
                if (candidate.ContainerType == LootContainerTypes.Nothing)
                    continue;
                if (!roster.ContainsKey(candidate.GetInstanceID()))
                {
                    Vector3 at = space.InverseTransformPoint(candidate.transform.position);
                    Known known = new Known { loot = candidate, local = at, id = PileId(candidate.LoadID, at) };
                    if (IsFurniture(candidate))
                        known.box = LocalBounds(space, candidate);
                    roster[candidate.GetInstanceID()] = known;
                }
            }
            gone.Clear();
            ulong hash = 17;
            float units = DoomPerDaggerfall / MeshReader.GlobalScale;
            foreach (KeyValuePair<int, Known> known in roster)
            {
                DaggerfallLoot loot = known.Value.loot;
                if (!loot)
                {
                    gone.Add(known.Key);
                    continue;
                }
                Vector3 local = known.Value.local;
                ulong id = known.Value.id;
                string key = place + "|" + id.ToString("x16");
                bool furniture = IsFurniture(loot);
                if (!loot.customDrop && restored.Add(known.Key))
                    ApplyLedger(loot, key, furniture);
                // An empty shelf or wardrobe can still be opened, and Daggerfall restocks it then.
                if (!loot.gameObject.activeSelf || (loot.Items.Count == 0 && !furniture))
                    continue;
                if (live.ContainsKey(id))
                {
                    bridge.LogLine("items: duplicate pile id " + id.ToString("x16") + " skipped");
                    continue;
                }
                live[id] = new Pile { loot = loot, key = key, local = local };

                if (furniture)
                {
                    Bounds box = known.Value.box;
                    boxes.Add(new DfbWorldContainer
                    {
                        id = id,
                        minX = box.min.x * units,
                        minY = box.min.z * units,
                        minZ = box.min.y * units,
                        maxX = box.max.x * units,
                        maxY = box.max.z * units,
                        maxZ = box.max.y * units,
                    });
                    hash = (hash ^ id) * 1099511628211UL;
                    hash = (hash ^ (ulong)box.center.GetHashCode()) * 1099511628211UL;
                    continue;
                }

                Vector2 size = new Vector2(1, 1);
                DaggerfallBillboard billboard = loot.GetComponent<DaggerfallBillboard>();
                if (billboard)
                    size = billboard.Summary.Size;
                rows.Add(new DfbWorldItem
                {
                    id = id,
                    archive = loot.TextureArchive,
                    record = loot.TextureRecord,
                    itemCount = loot.Items.Count,
                    x = local.x * units,
                    y = local.z * units,
                    z = local.y * units,
                    width = size.x * units,
                    height = size.y * units,
                });
                hash = (hash ^ id) * 1099511628211UL;
                hash = (hash ^ (ulong)(uint)loot.Items.Count) * 1099511628211UL;
                hash = (hash ^ (ulong)(uint)(loot.TextureArchive << 16 | loot.TextureRecord)) * 1099511628211UL;
            }
            foreach (int instance in gone)
                roster.Remove(instance);
            return hash;
        }

        void ApplyLedger(DaggerfallLoot loot, string key, bool furniture)
        {
            ItemData_v1[] left;
            if (!ledger.piles.TryGetValue(key, out left))
                return;
            loot.Items.Clear();
            if (left != null && left.Length > 0)
                loot.Items.DeserializeItems(left);
            int date;
            if (furniture && ledger.stocked != null && ledger.stocked.TryGetValue(key, out date))
                loot.stockedDate = date;
            bridge.LogLine(string.Format("items: restored {0} with {1} items, stocked {2}", key, loot.Items.Count, loot.stockedDate));
            if (loot.Items.Count == 0 && !furniture)
                GameObjectHelper.RemoveLootContainer(loot);
        }

        void Publish(ref DfbUzState peer)
        {
            generation++;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_ITEMS_BEGIN;
            e.tic = (uint)Time.frameCount;
            e.worldItems.generation = generation;
            e.worldItems.context = peer.worldContext;
            e.worldItems.target = peer.spaceTarget;
            e.worldItems.count = (uint)rows.Count;
            bridge.Send(ref e);
            foreach (DfbWorldItem row in rows)
            {
                DfbEvent item = default(DfbEvent);
                item.kind = Dfb.KIND_ITEM;
                item.tic = (uint)Time.frameCount;
                item.worldItem = row;
                item.worldItem.generation = generation;
                bridge.Send(ref item);
            }
            foreach (DfbWorldContainer box in boxes)
            {
                DfbEvent item = default(DfbEvent);
                item.kind = Dfb.KIND_CONTAINER;
                item.tic = (uint)Time.frameCount;
                item.worldContainer = box;
                item.worldContainer.generation = generation;
                bridge.Send(ref item);
            }
            e.kind = Dfb.KIND_ITEMS_END;
            bridge.Send(ref e);
            bridge.LogLine(string.Format("items: list {0} has {1} piles and {2} containers, context {3}, target {4}", generation, rows.Count, boxes.Count, peer.worldContext, peer.spaceTarget));
        }

        // Use on a container. Daggerfall decides everything in its own activation, once Doom has opened the window
        // that will show it. Grab and Steal are the same to a container in PlayerActivate.ActivateLootContainer, so
        // the mode is only recorded.
        internal void OnTake(uint request, ulong id, uint mode)
        {
            uint status = Dfb.ITEM_REFUSED;
            Pile pile = default(Pile);
            float distance = 0;
            if (!windowOpen && Find(id, out pile, out status, out distance))
            {
                window = pile;
                windowAnswerBy = Time.unscaledTime + WindowAnswerSeconds;
                status = Dfb.ITEM_WINDOW;
            }
            SendResult(request, id, status, pile.loot ? pile.loot.Items.Count : 0);
            bridge.LogLine(string.Format("items: use {0} on {1:x16} ({2}, {3}): status {4}, distance {5:F2}", request, id, mode == Dfb.TAKE_STEAL ? "steal" : "grab",
                pile.loot ? pile.loot.ContainerType.ToString() : "none", status, distance));
        }

        bool Find(ulong id, out Pile pile, out uint status, out float distance)
        {
            pile = default(Pile);
            distance = 0;
            status = Dfb.ITEM_REFUSED;
            if (sync.LoadRunning || !GameManager.HasInstance || GameManager.IsGamePaused)
                return false;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            Transform space = sync.ItemSpace(ref peer);
            if (!space)
                return false;
            Collect(space);
            if (!live.TryGetValue(id, out pile) || !pile.loot)
            {
                status = Dfb.ITEM_GONE;
                return false;
            }
            Vector3 player = GameManager.Instance.PlayerObject.transform.position;
            Vector3 target = space.TransformPoint(pile.local);
            Known known;
            if (IsFurniture(pile.loot) && roster.TryGetValue(pile.loot.GetInstanceID(), out known))
                target = space.TransformPoint(known.box.ClosestPoint(space.InverseTransformPoint(player)));
            Vector3 offset = target - player;
            offset.y = 0;
            distance = offset.magnitude;
            return distance <= MaxReach;
        }

        // DoomerfallUi calls this once Doom has asked for DFB_UI_LOOT and the window target is in place.
        internal bool OpenWindow()
        {
            if (windowOpen || !window.loot || Time.unscaledTime > windowAnswerBy)
            {
                window = default(Pile);
                return false;
            }
            windowOpen = true;
            bridge.LogLine(string.Format("items: opening {0} {1} with {2} items", window.loot.ContainerType, window.key, window.loot.Items.Count));
            // Doom has measured the reach already, and Daggerfall's hidden player trails it, so the distance given is Doom's.
            GameManager.Instance.PlayerActivate.DoomerfallActivateLoot(window.loot, 0);
            return true;
        }

        // The window is gone, so whatever it did to the container is final. Taken, added, bought, or restocked, the
        // container's contents now are what must come back after re-entry, save, and load.
        internal void WindowClosed()
        {
            if (!windowOpen)
                return;
            windowOpen = false;
            DaggerfallLoot loot = window.loot;
            if (loot && !loot.customDrop)
            {
                ledger.piles[window.key] = loot.Items.SerializeItems();
                if (IsFurniture(loot))
                    ledger.stocked[window.key] = loot.stockedDate;
            }
            bridge.LogLine(string.Format("items: closed {0}, {1} items left, carried {2:F2}/{3} kg, gold {4}", window.key, loot ? loot.Items.Count : 0,
                GameManager.Instance.PlayerEntity.CarriedWeight, GameManager.Instance.PlayerEntity.MaxEncumbrance, GameManager.Instance.PlayerEntity.GoldPieces));
            window = default(Pile);
            resend = true;
        }

        void SendResult(uint request, ulong id, uint status, int remaining)
        {
            byte[] body = new byte[48];
            BitConverter.GetBytes(id).CopyTo(body, 0);
            BitConverter.GetBytes(request).CopyTo(body, 8);
            BitConverter.GetBytes(status).CopyTo(body, 12);
            BitConverter.GetBytes(0).CopyTo(body, 16);
            BitConverter.GetBytes(remaining).CopyTo(body, 20);
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_ITEM_RESULT;
            e.tic = (uint)Time.frameCount;
            e.SetPayload(body, body.Length);
            bridge.Send(ref e);
        }

        // Called with the staged save, before the bundle's file count is taken.
        internal void WriteLedger(string folder)
        {
            File.WriteAllText(Path.Combine(folder, LedgerFile), SaveLoadManager.Serialize(typeof(LedgerData), ledger, false), new UTF8Encoding(false));
        }

        // A save without the file comes from before this feature, so nothing in it has been picked up through Doom.
        internal void ReadLedger(string folder)
        {
            string path = Path.Combine(folder, LedgerFile);
            ledger = File.Exists(path) ? (LedgerData)SaveLoadManager.Deserialize(typeof(LedgerData), File.ReadAllText(path)) ?? new LedgerData() : new LedgerData();
            if (ledger.piles == null)
                ledger.piles = new Dictionary<string, ItemData_v1[]>();
            if (ledger.stocked == null)
                ledger.stocked = new Dictionary<string, int>();
            ForgetSpace();
            bridge.LogLine("items: ledger restored with " + ledger.piles.Count + " piles");
        }
    }
}
