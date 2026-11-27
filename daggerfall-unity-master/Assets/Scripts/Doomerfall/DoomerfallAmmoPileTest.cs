// Doomerfall test only (-dfammopiletest): drops ammo through Daggerfall's real inventory window, for the ammo pile route
// (tools/ammo_pile/ammo_pile.py). Once the player holds all four ammo types (the harness gives them in Doom), it makes
// five piles, one window drop each: 10 bullets, every shell, every rocket, every cell, then 5 bullets with a ruby. Each
// new pile is moved a little to the side so the piles stand apart. Every few seconds, in every run, it logs the dropped
// piles in the scene with their contents and the look Doom is sent (DoomerfallAmmoPileArt).

using System;
using System.Collections.Generic;
using System.Reflection;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallAmmoPileTest : MonoBehaviour
    {
        const int SettleFrames = 30, WindowFrames = 10, Drops = 5;
        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        int step, frames, settled;
        float nextReport;
        string lastReport;
        readonly HashSet<ulong> known = new HashSet<ulong>();
        // A load run starts from a save that already has the piles; it only reports.
        readonly bool dropRun = Array.IndexOf(Environment.GetCommandLineArgs(), "-dfammopiledrop") >= 0;

        internal static void Attach(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfammopiletest") < 0)
                return;
            DoomerfallAmmoPileTest test = owner.gameObject.AddComponent<DoomerfallAmmoPileTest>();
            test.bridge = owner;
            test.ammo = tracker;
        }

        void Update()
        {
            if (!ammo.Ready || !GameManager.HasInstance)
                return;
            if (Time.unscaledTime >= nextReport)
            {
                nextReport = Time.unscaledTime + 2f;
                Report();
            }
            if (!dropRun || step >= Drops * 2)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            frames++;
            settled = ammo.Settled ? settled + 1 : 0;
            if (step == 0)
            {
                for (int t = 0; t < DoomerfallAmmo.Types.Length; t++)
                    if (DoomerfallAmmo.Total(player.Items, t) < (t == 0 ? 20 : 1))
                        return;
                if (!GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon)
                    return;
                foreach (DaggerfallLoot loot in FindObjectsOfType<DaggerfallLoot>())
                    known.Add(loot.LoadID);
                bridge.LogLine("ammopiletest: start, holds" + ammo.Totals());
            }
            if (step % 2 == 0)
            {
                if (settled < SettleFrames)
                    return;
                if (step == Drops * 2 - 2)
                    player.Items.AddItem(ItemBuilder.CreateItem(ItemGroups.Gems, (int)Gems.Ruby));
                DaggerfallUI.Instance.InventoryWindow.LootTarget = null;
                DaggerfallUI.UIManager.PushWindow(DaggerfallUI.Instance.InventoryWindow);
                Next();
                return;
            }
            if (frames < WindowFrames)
                return;
            DaggerfallInventoryWindow window = DaggerfallUI.Instance.InventoryWindow;
            int drop = step / 2;
            if (drop == 0 || drop == 4)
            {
                // Part of the bullet stack, the way the split popup does it.
                DaggerfallUnityItem part = player.Items.SplitStack(Find(player.Items, 0), drop == 0 ? 10 : 5);
                Click(window, part);
                if (drop == 4)
                    for (int i = 0; i < player.Items.Count; i++)
                        if (player.Items.GetItem(i).IsOfTemplate(ItemGroups.Gems, (int)Gems.Ruby))
                        {
                            Click(window, player.Items.GetItem(i));
                            break;
                        }
            }
            else
                Click(window, Find(player.Items, drop));
            window.CloseWindow();
            Spread(drop);
            bridge.LogLine(string.Format("ammopiletest: window drop {0} done, holds{1}", drop, ammo.Totals()));
            Next();
        }

        void Next()
        {
            step++;
            frames = 0;
            settled = 0;
        }

        // Moves the pile this drop made 1.2 m to the player's right per drop, so the piles stand apart.
        void Spread(int drop)
        {
            Transform player = GameManager.Instance.PlayerObject.transform;
            foreach (DaggerfallLoot loot in FindObjectsOfType<DaggerfallLoot>())
                if (loot.customDrop && known.Add(loot.LoadID))
                    loot.transform.position += player.right * (1.2f * (drop - 2)) + player.forward * 1.5f;
        }

        void Report()
        {
            List<string> piles = new List<string>();
            foreach (DaggerfallLoot loot in FindObjectsOfType<DaggerfallLoot>())
            {
                if (!loot.customDrop || loot.ContainerType != LootContainerTypes.DroppedLoot || loot.Items.Count == 0)
                    continue;
                List<string> items = new List<string>();
                for (int i = 0; i < loot.Items.Count; i++)
                    items.Add(loot.Items.GetItem(i).ItemName + " x" + loot.Items.GetItem(i).stackCount);
                items.Sort();
                int archive, record;
                string look = DoomerfallAmmoPileArt.TryGet(loot, out archive, out record)
                    ? string.Format("ammo art {0}:{1}", archive, record) : string.Format("loot pile {0}:{1}", loot.TextureArchive, loot.TextureRecord);
                piles.Add(string.Format("{0:x16} {1} [{2}]", loot.LoadID, look, string.Join(", ", items.ToArray())));
            }
            piles.Sort();
            string text = string.Format("ammopiletest: {0} dropped piles: {1}", piles.Count, string.Join(" | ", piles.ToArray()));
            if (text == lastReport)
                return;
            lastReport = text;
            bridge.LogLine(text);
        }

        static DoomerfallAmmoItem Find(ItemCollection items, int type)
        {
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item != null && item.AmmoType == type)
                    return item;
            }
            return null;
        }

        // The window's own click handler in Remove mode: the item goes to the window's drop pile.
        static void Click(DaggerfallInventoryWindow window, DaggerfallUnityItem item)
        {
            if (item == null)
                return;
            const BindingFlags flags = BindingFlags.Instance | BindingFlags.NonPublic;
            Type type = typeof(DaggerfallInventoryWindow);
            object action = Enum.Parse(type.GetNestedType("ActionModes", BindingFlags.NonPublic), "Remove");
            type.GetMethod("LocalItemListScroller_OnItemClick", flags).Invoke(window, new object[] { item, action });
        }
    }
}
