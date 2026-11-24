// Doomerfall test only (-dfammotest): makes one change to the ammo stacks on Daggerfall's side, as a drop and a pile
// would, once Doom's bullets have arrived. Daggerfall then sends the change to Doom (DoomerfallAmmo).
// Then it drives Daggerfall's real inventory window: drops the whole bullet stack and 5 shells split from their stack,
// closes the window (which makes a ground pile), opens that pile as a loot window, and takes everything back.
using System;
using System.Reflection;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallAmmoTest : MonoBehaviour
    {
        const int DropBullets = 7, AddShells = 20, MinBullets = 60, SplitShells = 5;
        const int SettleFrames = 30, WindowFrames = 10, GiveUpFrames = 3000;
        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        int step, frames, settled;
        DaggerfallLoot pile;
        int[] before = new int[DoomerfallAmmo.Types.Length];

        internal void Init(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            bridge = owner;
            ammo = tracker;
        }

        void Update()
        {
            if (step < 0 || !ammo.Ready || !GameManager.HasInstance)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            frames++;
            settled = ammo.Settled ? settled + 1 : 0;
            if (step > 0 && frames > GiveUpFrames)
            {
                bridge.LogLine(string.Format("ammotest: window step {0} gave up, holds{1}", step, ammo.Totals()));
                step = -1;
                return;
            }
            switch (step)
            {
                case 0:
                    // The harness picks up bullets first, so this waits for more than a fresh start holds.
                    if (DoomerfallAmmo.Total(player.Items, 0) < MinBullets)
                        return;
                    FirstChange(player);
                    Next();
                    break;
                case 1: // Open the plain inventory once both sides agree.
                    if (settled < SettleFrames)
                        return;
                    for (int i = 0; i < before.Length; i++)
                        before[i] = DoomerfallAmmo.Total(player.Items, i);
                    bridge.LogLine("ammotest: window before drop, holds" + ammo.Totals());
                    Open(null);
                    Next();
                    break;
                case 2: // Drop the bullet stack, and 5 shells the way the split popup would.
                {
                    if (frames < WindowFrames)
                        return;
                    DaggerfallInventoryWindow window = DaggerfallUI.Instance.InventoryWindow;
                    DoomerfallAmmoItem bullets = Find(player.Items, 0);
                    DoomerfallAmmoItem shells = Find(player.Items, 1);
                    if (bullets != null)
                        Click(window, "LocalItemListScroller_OnItemClick", bullets);
                    if (shells != null && shells.stackCount > SplitShells)
                    {
                        DaggerfallUnityItem part = player.Items.SplitStack(shells, SplitShells);
                        bridge.LogLine(string.Format("ammotest: split {0} shells gave {1} '{2}' x{3}, type {4}", SplitShells, part == null ? "null" : part.GetType().Name,
                            part == null ? "" : part.ItemName, part == null ? 0 : part.stackCount, part is DoomerfallAmmoItem ? ((DoomerfallAmmoItem)part).AmmoType : -1));
                        if (part != null)
                            Click(window, "LocalItemListScroller_OnItemClick", part);
                    }
                    bridge.LogLine("ammotest: window dropped, holds" + ammo.Totals());
                    window.CloseWindow();
                    Next();
                    break;
                }
                case 3: // Find the pile the window made and open it.
                    if (settled < SettleFrames)
                        return;
                    pile = null;
                    foreach (DaggerfallLoot loot in FindObjectsOfType<DaggerfallLoot>())
                        if (loot.playerOwned && Find(loot.Items, 0) != null)
                            pile = loot;
                    bridge.LogLine(string.Format("ammotest: window drop settled, pile {0} with {1} items, holds{2}", pile ? "found" : "missing", pile ? pile.Items.Count : 0, ammo.Totals()));
                    if (!pile)
                    {
                        step = -1;
                        return;
                    }
                    Open(pile);
                    Next();
                    break;
                case 4: // Take every item back with the loot window's default click.
                {
                    if (frames < WindowFrames)
                        return;
                    DaggerfallInventoryWindow window = DaggerfallUI.Instance.InventoryWindow;
                    for (int i = pile.Items.Count - 1; i >= 0; i--)
                    {
                        DaggerfallUnityItem item = pile.Items.GetItem(i);
                        // Bullets in the loot window's Remove mode, shells in Equip mode, the plain inventory's default.
                        Click(window, "RemoteItemListScroller_OnItemClick", item, item is DoomerfallAmmoItem && ((DoomerfallAmmoItem)item).AmmoType == 0 ? "Remove" : "Equip");
                        bridge.LogLine(string.Format("ammotest: window took {0} x{1}, pile has {2} left", item.ItemName, item.stackCount, pile ? pile.Items.Count : 0));
                    }
                    if (DaggerfallUI.UIManager.TopWindow != window)
                        bridge.LogLine("ammotest: window covered by " + DaggerfallUI.UIManager.TopWindow);
                    while (DaggerfallUI.UIManager.TopWindow != window && DaggerfallUI.UIManager.WindowCount > 1)
                        DaggerfallUI.UIManager.PopWindow();
                    window.CloseWindow();
                    Next();
                    break;
                }
                case 5:
                {
                    if (settled < SettleFrames)
                        return;
                    bool same = true;
                    for (int i = 0; i < before.Length; i++)
                        same &= before[i] == DoomerfallAmmo.Total(player.Items, i);
                    bridge.LogLine(string.Format("ammotest: window pickup settled, {0} the counts before the drop, holds{1}", same ? "same as" : "DIFFERENT from", ammo.Totals()));
                    step = -1;
                    break;
                }
            }
        }

        void Next()
        {
            step++;
            frames = 0;
            settled = 0;
        }

        void FirstChange(PlayerEntity player)
        {
            DoomerfallAmmo.Change(player.Items, 0, -DropBullets);
            DoomerfallAmmo.Change(player.Items, 1, AddShells);
            bridge.LogLine(string.Format("ammotest: Daggerfall dropped {0} bullets and took {1} shells, now holds{2}", DropBullets, AddShells, ammo.Totals()));

            // Arrow weight: 100 arrows should add 1 kg.
            float weightBefore = player.CarriedWeight;
            DaggerfallUnityItem arrows = ItemBuilder.CreateWeapon(Weapons.Arrow, WeaponMaterialTypes.Iron);
            arrows.stackCount = 100;
            player.Items.AddItem(arrows);
            float after = player.CarriedWeight;
            player.Items.RemoveItem(arrows);
            bridge.LogLine(string.Format("ammotest: 100 arrows ({0} kg each) add {1:F2} kg", arrows.weightInKg, after - weightBefore));
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

        static void Open(DaggerfallLoot loot)
        {
            DaggerfallUI.Instance.InventoryWindow.LootTarget = loot;
            DaggerfallUI.UIManager.PushWindow(DaggerfallUI.Instance.InventoryWindow);
        }

        // The window's own click handler, in the given action mode.
        void Click(DaggerfallInventoryWindow window, string handler, DaggerfallUnityItem item, string mode = "Remove")
        {
            const BindingFlags flags = BindingFlags.Instance | BindingFlags.NonPublic;
            Type type = typeof(DaggerfallInventoryWindow);
            object action = Enum.Parse(type.GetNestedType("ActionModes", BindingFlags.NonPublic), mode);
            type.GetMethod(handler, flags).Invoke(window, new object[] { item, action });
        }
    }
}
