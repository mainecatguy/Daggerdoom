// Doomerfall: Daggerfall's side of world item pickups. Runs only in a bridge session.
//
// Daggerfall stays the authority. It lists the real loot piles in the space the player is in, and it
// moves items into the real inventory. Doom only draws the list and asks for a pickup.
//
// Daggerfall rebuilds and rerolls a dungeon on every entry, so a small ledger records each pile the
// player has touched and what is left in it. It travels inside the save bundle.

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Questing;
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
        const string LedgerFile = "DoomerfallItems.json";

        [fsObject("v1")]
        public sealed class LedgerData
        {
            public Dictionary<string, ItemData_v1[]> piles = new Dictionary<string, ItemData_v1[]>();
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
        uint generation;
        ulong lastHash;
        int lastSpace;
        bool resend, weightTest;
        float nextPoll;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            weightTest = Array.IndexOf(Environment.GetCommandLineArgs(), "-dfitemweighttest") >= 0;
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

        ulong Collect(Transform space)
        {
            string place = PlaceKey();
            live.Clear();
            rows.Clear();
            // A pile's object can briefly leave the space's hierarchy while staying intact, so each pile is
            // remembered for the whole visit. Only emptying or destroying it takes it off the list.
            space.GetComponentsInChildren(true, found);
            foreach (DaggerfallLoot candidate in found)
            {
                // Shop shelves, house containers, and corpses belong to the separate containers task.
                if (candidate.ContainerType != LootContainerTypes.RandomTreasure && candidate.ContainerType != LootContainerTypes.DroppedLoot)
                    continue;
                if (!roster.ContainsKey(candidate.GetInstanceID()))
                {
                    Vector3 at = space.InverseTransformPoint(candidate.transform.position);
                    roster[candidate.GetInstanceID()] = new Known { loot = candidate, local = at, id = PileId(candidate.LoadID, at) };
                }
            }
            gone.Clear();
            ulong hash = 17;
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
                if (!loot.customDrop && restored.Add(known.Key))
                    ApplyLedger(loot, key);
                if (!loot.gameObject.activeSelf || loot.Items.Count == 0)
                    continue;
                if (live.ContainsKey(id))
                {
                    bridge.LogLine("items: duplicate pile id " + id.ToString("x16") + " skipped");
                    continue;
                }
                live[id] = new Pile { loot = loot, key = key, local = local };

                Vector2 size = new Vector2(1, 1);
                DaggerfallBillboard billboard = loot.GetComponent<DaggerfallBillboard>();
                if (billboard)
                    size = billboard.Summary.Size;
                float units = DoomPerDaggerfall / MeshReader.GlobalScale;
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

        void ApplyLedger(DaggerfallLoot loot, string key)
        {
            ItemData_v1[] left;
            if (!ledger.piles.TryGetValue(key, out left))
                return;
            loot.Items.Clear();
            if (left != null && left.Length > 0)
            {
                loot.Items.DeserializeItems(left);
                bridge.LogLine("items: restored the remainder of " + key + ", first stack " + loot.Items.GetItem(0).stackCount);
            }
            else
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
            e.kind = Dfb.KIND_ITEMS_END;
            bridge.Send(ref e);
            bridge.LogLine(string.Format("items: list {0} has {1} piles, context {2}, target {3}", generation, rows.Count, peer.worldContext, peer.spaceTarget));
        }

        // Test only: the real weight rule with the player loaded to the limit, then with room for half the pile.
        void RunWeightTest(ulong id)
        {
            weightTest = false;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            Pile pile;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            Transform space = sync.ItemSpace(ref peer);
            if (!space)
                return;
            Collect(space);
            if (!live.TryGetValue(id, out pile) || pile.loot.Items.Count != 1 || !pile.loot.Items.GetItem(0).IsOfTemplate(ItemGroups.Currency, (int)Currency.Gold_pieces) || pile.loot.Items.GetItem(0).stackCount < 2)
            {
                bridge.LogLine("items: weight test skipped, the pile is not one stack of gold");
                return;
            }
            int goldBefore = player.GoldPieces, stack = pile.loot.Items.GetItem(0).stackCount, half = stack / 2;
            int room = Mathf.RoundToInt(player.MaxEncumbrance * 400f) - Mathf.RoundToInt(player.CarriedWeight * 400f);
            player.GoldPieces += room;
            int taken = 0, remaining = 0;
            string name = string.Empty;
            uint full = Take(id, ref taken, ref remaining, ref name);
            int takenFull = taken;
            player.GoldPieces -= half;
            taken = 0;
            uint part = Take(id, ref taken, ref remaining, ref name);
            int left = pile.loot.Items.Count > 0 ? pile.loot.Items.GetItem(0).stackCount : 0;
            player.GoldPieces -= room - half;
            bridge.LogLine(string.Format("items: weight test stack {0}: at the limit status {1} took {2}; with room for {3} status {4} took {5}, pile keeps {6}; gold {7} to {8}, conserved {9}",
                stack, full, takenFull, half, part, taken, left, goldBefore, player.GoldPieces, player.GoldPieces - goldBefore + left == stack && takenFull == 0));
            resend = true;
        }

        internal void OnTake(uint request, ulong id)
        {
            if (weightTest)
            {
                RunWeightTest(id);
                return;
            }
            int taken = 0, remaining = 0;
            string name = string.Empty;
            uint status = Take(id, ref taken, ref remaining, ref name);
            SendResult(request, id, status, taken, remaining, name);
            bridge.LogLine(string.Format("items: take {0} pile {1:x16}: status {2}, took {3}, left {4}, first \"{5}\", carried {6:F2}/{7} kg, gold {8}", request, id, status, taken, remaining, name,
                GameManager.Instance.PlayerEntity.CarriedWeight, GameManager.Instance.PlayerEntity.MaxEncumbrance, GameManager.Instance.PlayerEntity.GoldPieces));
            resend = true;
        }

        uint Take(ulong id, ref int taken, ref int remaining, ref string name)
        {
            if (sync.LoadRunning || !GameManager.HasInstance || GameManager.IsGamePaused)
                return Dfb.ITEM_REFUSED;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            Transform space = sync.ItemSpace(ref peer);
            if (!space)
                return Dfb.ITEM_REFUSED;
            Collect(space);
            Pile pile;
            if (!live.TryGetValue(id, out pile) || !pile.loot)
                return Dfb.ITEM_GONE;

            Vector3 offset = space.TransformPoint(pile.local) - GameManager.Instance.PlayerObject.transform.position;
            offset.y = 0;
            if (offset.magnitude > MaxReach)
            {
                remaining = pile.loot.Items.Count;
                return Dfb.ITEM_REFUSED;
            }

            bool tooHeavy = false;
            ItemCollection items = pile.loot.Items;
            for (int i = items.Count - 1; i >= 0; i--)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                string itemName = item.LongName;
                int moved = TakeItem(item, items, ref tooHeavy);
                if (moved > 0)
                {
                    taken += moved;
                    if (name.Length == 0)
                        name = itemName;
                }
            }
            remaining = items.Count;
            if (taken == 0)
                return tooHeavy ? Dfb.ITEM_TOO_HEAVY : Dfb.ITEM_REFUSED;

            if (!pile.loot.customDrop)
                ledger.piles[pile.key] = items.SerializeItems();
            if (remaining == 0)
            {
                GameObjectHelper.RemoveLootContainer(pile.loot);
                return Dfb.ITEM_TAKEN;
            }
            return Dfb.ITEM_PARTIAL;
        }

        // Follows DaggerfallInventoryWindow.TransferItem for a move from a loot pile to the player.
        static int TakeItem(DaggerfallUnityItem item, ItemCollection from, ref bool tooHeavy)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (item.IsSummoned)
                return 0;

            if (item.IsOfTemplate(ItemGroups.MiscItems, (int)MiscItems.Map))
            {
                RevealMapLocation();
                from.RemoveItem(item);
                return 1;
            }

            Item questItem = null;
            if (item.IsQuestItem)
            {
                Quest quest = QuestMachine.Instance.GetQuest(item.QuestUID);
                questItem = quest != null ? quest.GetItem(item.QuestItemSymbol) : null;
                if (questItem == null)
                    return 0;
            }

            int canCarry = CanHold(item.stackCount, item.EffectiveUnitWeightInKg(), player.MaxEncumbrance, player.CarriedWeight);
            if (canCarry <= 0)
            {
                tooHeavy = true;
                return 0;
            }
            DaggerfallUnityItem moving = item;
            if (canCarry < item.stackCount)
            {
                tooHeavy = true;
                if (!item.IsAStack())
                    return 0;
                moving = from.SplitStack(item, canCarry);
                if (moving == null)
                    return 0;
            }

            // Only once the item is certain to move, so a refused quest item keeps its quest state.
            if (questItem != null)
            {
                questItem.PlayerDropped = false;
                if (questItem.MadePermanent)
                    moving.MakePermanent();
            }

            int count = moving.stackCount;
            if (moving.IsOfTemplate(ItemGroups.Currency, (int)Currency.Gold_pieces))
            {
                player.GoldPieces += count;
                from.RemoveItem(moving);
                return count;
            }
            player.Items.Transfer(moving, from, moving.IsQuestItem ? ItemCollection.AddPosition.Front : ItemCollection.AddPosition.DontCare);
            return count;
        }

        // The same rounding as DaggerfallInventoryWindow.ComputeCanHoldAmount.
        static int CanHold(int available, float unitKg, float capacityKg, float loadKg)
        {
            int unit = Mathf.RoundToInt(unitKg * 400f);
            if (unit <= 0)
                return available;
            return Math.Min(available, (Mathf.RoundToInt(capacityKg * 400f) - Mathf.RoundToInt(loadKg * 400f)) / unit);
        }

        static void RevealMapLocation()
        {
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            try
            {
                DaggerfallConnect.DFLocation revealed = gps.DiscoverRandomLocation();
                if (string.IsNullOrEmpty(revealed.Name))
                    return;
                string place = TextManager.Instance.GetLocalizedLocationName(revealed.MapTableData.MapId, revealed.Name);
                gps.LocationRevealedByMapItem = place;
                GameManager.Instance.PlayerEntity.Notebook.AddNote(TextManager.Instance.GetLocalizedText("readMap").Replace("%map", place));
            }
            catch (Exception)
            {
                // Every location in this region is already known. Daggerfall still consumes the map.
            }
        }

        void SendResult(uint request, ulong id, uint status, int taken, int remaining, string name)
        {
            byte[] body = new byte[48];
            BitConverter.GetBytes(id).CopyTo(body, 0);
            BitConverter.GetBytes(request).CopyTo(body, 8);
            BitConverter.GetBytes(status).CopyTo(body, 12);
            BitConverter.GetBytes(taken).CopyTo(body, 16);
            BitConverter.GetBytes(remaining).CopyTo(body, 20);
            byte[] text = Encoding.UTF8.GetBytes(name);
            int length = Math.Min(text.Length, 23);
            while (length > 0 && length < text.Length && (text[length] & 0xC0) == 0x80)
                length--; // Never cut a UTF-8 character in half.
            Array.Copy(text, 0, body, 24, length);
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
            ForgetSpace();
            bridge.LogLine("items: ledger restored with " + ledger.piles.Count + " piles");
        }
    }
}
