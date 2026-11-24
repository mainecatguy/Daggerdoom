// Doomerfall: Doom reserve ammo held in Daggerfall's inventory. Runs only in a bridge session.
//
// Daggerfall holds each ammo type as a stack (one round per unit) that weighs and is priced per round. Doom's ammo
// inventory is the live counter that guns spend, so Doom reports its counts (DFB_KIND_AMMO) and Daggerfall mirrors
// them. Changes made on Daggerfall's side (dropping, trading, taking from a pile) go to Doom as numbered deltas
// (DFB_KIND_AMMO_ADD). Each report carries the last delta Doom applied, so a delta still in flight is never counted twice.
// Doom's ammo is in its own save and Daggerfall's stacks in its own, both in the bundled save. After a load Doom
// reports again and its count wins any difference.

using System;
using System.Collections.Generic;
using DaggerfallConnect.FallExe;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // One stack of one ammo type. No material tiers yet.
    public class DoomerfallAmmoItem : DaggerfallUnityItem, ICustomItemImage
    {
        public DoomerfallAmmoItem() : base(ItemGroups.MiscItems, DoomerfallAmmo.Types[0].template)
        {
        }

        // Daggerfall reloads its item templates after the bridge registers custom ones, so the custom templates are gone by
        // play time. The item carries its own weight and value, saved with it, and its group index names its type.
        public DoomerfallAmmoItem(int type, int count) : base(ItemGroups.MiscItems, DoomerfallAmmo.Types[type].template)
        {
            stackCount = Math.Max(1, count);
            shortName = DoomerfallAmmo.Types[type].name;
            weightInKg = DoomerfallAmmo.Types[type].weightKg;
            value = DoomerfallAmmo.Types[type].price;
        }

        // -1 for an item that is not ammo.
        public int AmmoType { get { return DoomerfallAmmo.TypeOfTemplate(GroupIndex); } }
        public string DoomClass { get { int t = AmmoType; return t < 0 ? "" : DoomerfallAmmo.Types[t].doomClass; } }
        public override string ItemName { get { int t = AmmoType; return t < 0 ? base.ItemName : DoomerfallAmmo.Types[t].name; } }
        public override string LongName { get { return ItemName; } }
        public override bool IsStackable() { return true; }
        public override bool UseItem(ItemCollection collection)
        {
            DaggerfallUI.MessageBox("Your guns load this ammo by themselves.");
            return true;
        }
        public bool TryGetImage(out ImageData image) { return DoomerfallDoomItems.TryGetImage(DoomClass, out image); }

        public override ItemData_v1 GetSaveData()
        {
            ItemData_v1 data = base.GetSaveData();
            data.className = typeof(DoomerfallAmmoItem).ToString();
            return data;
        }
    }

    internal sealed class DoomerfallAmmo : MonoBehaviour
    {
        internal struct AmmoType
        {
            public int template;
            public string doomClass, name;
            public float weightKg;
            public int price;
        }

        // The owner's weights and base prices per round (2026-11-24). Doom's class names match dd_items.cpp AmmoClasses.
        internal static readonly AmmoType[] Types =
        {
            new AmmoType { template = 9101, doomClass = "Clip", name = "Bullets", weightKg = 0.02f, price = 1 },
            new AmmoType { template = 9102, doomClass = "Shell", name = "Shotgun shells", weightKg = 0.1f, price = 3 },
            new AmmoType { template = 9103, doomClass = "RocketAmmo", name = "Rockets", weightKg = 0.2f, price = 10 },
            new AmmoType { template = 9104, doomClass = "Cell", name = "Energy cells", weightKg = 0.02f, price = 5 },
        };

        sealed class Track
        {
            public int report = -1;  // Doom's last reported count, or -1 before any report.
            public uint reportAck;   // The last AMMO_ADD Doom had applied when it sent that report.
            public int synced;       // Daggerfall's inventory total as of the last time both sides agreed.
            public readonly List<KeyValuePair<uint, int>> pending = new List<KeyValuePair<uint, int>>(); // Deltas sent, not yet applied.
        }

        static bool registered;
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        readonly Track[] tracks = new Track[Types.Length];
        bool ready;
        uint nextAdd = 1;

        internal static int TypeOfTemplate(int template)
        {
            for (int i = 0; i < Types.Length; i++)
                if (Types[i].template == template)
                    return i;
            return -1;
        }

        static int TypeOfClass(string cls)
        {
            for (int i = 0; i < Types.Length; i++)
                if (Types[i].doomClass == cls)
                    return i;
            return -1;
        }

        // Before any save can load, so Daggerfall can rebuild ammo stacks from it.
        internal static void Register()
        {
            if (registered)
                return;
            registered = true;
            AddTemplates();
            // A class registers for loading only once. A save names the class, and the item's own data names its type.
            DaggerfallUnity.Instance.ItemHelper.RegisterCustomItem(Types[0].template, ItemGroups.None, typeof(DoomerfallAmmoItem));
        }

        // Adds any ammo template Daggerfall does not hold. Its template list is rebuilt after Register runs.
        static void AddTemplates()
        {
            ItemHelper helper = DaggerfallUnity.Instance.ItemHelper;
            ItemTemplate placeholder = helper.GetItemTemplate((int)MiscItems.Letter_of_credit); // Shown until Doom sends the sprite.
            foreach (AmmoType type in Types)
            {
                helper.AddCustomItemTemplate(new ItemTemplate
                {
                    index = type.template,
                    name = type.name,
                    baseWeight = type.weightKg,
                    basePrice = type.price,
                    isNotRepairable = true,
                    worldTextureArchive = placeholder.worldTextureArchive,
                    worldTextureRecord = placeholder.worldTextureRecord,
                    playerTextureArchive = placeholder.playerTextureArchive,
                    playerTextureRecord = placeholder.playerTextureRecord,
                });
            }
        }

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            for (int i = 0; i < tracks.Length; i++)
                tracks[i] = new Track();
            SaveLoadManager.OnLoad += OnLoad;
        }

        void OnDestroy()
        {
            SaveLoadManager.OnLoad -= OnLoad;
        }

        // Reports from before the load describe the old game. Doom reports its restored counts once both games resume.
        void OnLoad(SaveData_v1 saveData)
        {
            foreach (Track t in tracks)
            {
                t.report = -1;
                t.pending.Clear();
            }
            ready = false;
            bridge.LogLine("ammo: after load Daggerfall holds" + Totals());
        }

        // One DFB_KIND_AMMO report. Applied in Update, once Daggerfall is in a game.
        internal void OnReport(uint ack, uint count, string cls)
        {
            int type = TypeOfClass(cls);
            if (type < 0)
                return;
            tracks[type].report = (int)Math.Min(count, (uint)int.MaxValue);
            tracks[type].reportAck = ack;
        }

        internal bool Ready { get { return ready; } }

        internal static int Total(ItemCollection items, int type)
        {
            int total = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item != null && item.AmmoType == type)
                    total += item.stackCount;
            }
            return total;
        }

        internal string Totals()
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            if (player == null)
                return " (no player)";
            string text = "";
            for (int i = 0; i < Types.Length; i++)
                text += string.Format(" {0} {1};", Types[i].doomClass, Total(player.Items, i));
            text += string.Format(" carried {0:F2} kg; stacks", player.CarriedWeight);
            for (int i = 0; i < player.Items.Count; i++)
            {
                DoomerfallAmmoItem item = player.Items.GetItem(i) as DoomerfallAmmoItem;
                if (item != null)
                    text += string.Format(" [{0} x{1} {2} kg {3} gold each]", item.ItemName, item.stackCount, item.weightInKg, item.value);
            }
            return text;
        }

        // Adds (or removes, for a negative change) rounds of one type in the player's inventory.
        internal static void Change(ItemCollection items, int type, int change)
        {
            if (change > 0)
            {
                items.AddItem(new DoomerfallAmmoItem(type, change));
                return;
            }
            for (int i = items.Count - 1; i >= 0 && change < 0; i--)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item == null || item.AmmoType != type)
                    continue;
                int take = Math.Min(item.stackCount, -change);
                change += take;
                if (take >= item.stackCount)
                    items.RemoveItem(item);
                else
                    item.stackCount -= take;
            }
        }

        void Update()
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            if (player == null || !sync.InGame || sync.LoadRunning)
            {
                ready = false;
                return;
            }
            ItemCollection items = player.Items;
            if (!ready)
            {
                AddTemplates();
                // Whatever Daggerfall holds now is its side; the next report brings Doom's side.
                for (int i = 0; i < tracks.Length; i++)
                {
                    tracks[i].synced = Total(items, i);
                    tracks[i].pending.Clear();
                }
                ready = true;
            }
            bool changed = false;
            for (int i = 0; i < tracks.Length; i++)
            {
                Track t = tracks[i];
                if (t.report >= 0)
                {
                    t.pending.RemoveAll(p => p.Key <= t.reportAck);
                    int believed = t.report;
                    foreach (KeyValuePair<uint, int> p in t.pending)
                        believed += p.Value;
                    believed = Math.Max(0, believed);
                    if (believed != t.synced)
                    {
                        // Doom picked up or spent ammo.
                        Change(items, i, believed - t.synced);
                        t.synced = believed;
                        changed = true;
                    }
                }
                int total = Total(items, i);
                if (total != t.synced && t.report >= 0)
                {
                    // Daggerfall's side changed: a drop, a trade, a pile, or a stack that could not go below zero.
                    int delta = total - t.synced;
                    uint id = nextAdd++;
                    t.pending.Add(new KeyValuePair<uint, int>(id, delta));
                    t.synced = total;
                    Send(id, delta, Types[i].doomClass);
                    bridge.LogLine(string.Format("ammo: add {0} {1} {2:+0;-0} sent to Doom, Daggerfall holds {3}", id, Types[i].doomClass, delta, total));
                }
            }
            if (changed)
            {
                DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallInventoryWindow window =
                    DaggerfallUI.UIManager.TopWindow as DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallInventoryWindow;
                if (window != null)
                    window.Refresh(false);
                bridge.LogLine("ammo: Doom changed the count, Daggerfall holds" + Totals());
            }
        }

        void Send(uint request, int delta, string cls)
        {
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_AMMO_ADD;
            e.tic = (uint)Time.frameCount;
            e.doomItem.request = request;
            e.doomItem.status = unchecked((uint)delta);
            byte[] name = System.Text.Encoding.UTF8.GetBytes(cls);
            e.doomItem.SetCls(name, Math.Min(name.Length, 39));
            bridge.Send(ref e);
        }
    }
}
