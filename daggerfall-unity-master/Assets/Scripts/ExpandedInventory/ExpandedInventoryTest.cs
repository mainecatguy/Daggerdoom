// Doomerfall test only (-dfexpinvtest <dir>): in a bridge session, once both games agree on the ammo counts, opens the
// real inventory window (Expanded Inventory) with the ground on the right, and logs to the bridge log: the window class,
// the two lists' columns and places, which tab lists each Doom gun and ammo stack, then moves the bullets and one
// Daggerfall item to the right-hand list and back with the window's own click handler. Saves screenshots of each step
// into <dir>. The last line ends PASS when the layout is 4 and 2, Doom guns and ammo are on Weapons, both items went
// across and back, and the ammo counts are what they were. Starts itself; no hook in game classes.

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class ExpandedInventoryTest : MonoBehaviour
    {
        const int SettleFrames = 60;
        const int WindowFrames = 20;
        const BindingFlags Any = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        string dir;
        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        int step, frames, settled;
        string before;
        bool pass = true;
        DaggerfallUnityItem bullets, other;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfexpinvtest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("ExpandedInventoryTest");
            DontDestroyOnLoad(host);
            host.AddComponent<ExpandedInventoryTest>().dir = args[at + 1];
        }

        void Log(string text) { bridge.LogLine("expinv: " + text); }

        void Check(bool ok, string what)
        {
            pass &= ok;
            Log((ok ? "ok " : "FAIL ") + what);
        }

        void Shot(string name)
        {
            Directory.CreateDirectory(dir);
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, name));
        }

        void Update()
        {
            if (step < 0)
                return;
            if (bridge == null) bridge = FindObjectOfType<DoomerfallBridge>();
            if (ammo == null) ammo = FindObjectOfType<DoomerfallAmmo>();
            if (bridge == null || ammo == null || !GameManager.HasInstance || DaggerfallUI.Instance == null)
                return;
            frames++;
            settled = ammo.Settled ? settled + 1 : 0;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            DaggerfallInventoryWindow window = DaggerfallUI.Instance.InventoryWindow;
            try
            {
                switch (step)
                {
                    case 0:
                        if (settled < SettleFrames)
                            return;
                        // A town-start character carries nothing loose, so give it one Daggerfall item to move.
                        items.AddItem(ItemBuilder.CreateWeapon(Weapons.Longsword, WeaponMaterialTypes.Steel));
                        before = ammo.Totals();
                        Log("start, holds" + before);
                        window.LootTarget = null;
                        DaggerfallUI.UIManager.PushWindow(window);
                        Next();
                        break;
                    case 1:
                        if (frames < WindowFrames)
                            return;
                        Layout(window);
                        Tabs(window, items);
                        Select(window, "All");
                        Shot("1-open.png");
                        Next();
                        break;
                    case 2: // Across: the bullets and one Daggerfall item.
                        if (frames < WindowFrames)
                            return;
                        bullets = null;
                        other = null;
                        for (int i = 0; i < items.Count; i++)
                        {
                            DaggerfallUnityItem item = items.GetItem(i);
                            if (bullets == null && item is DoomerfallAmmoItem && ((DoomerfallAmmoItem)item).AmmoType == 0)
                                bullets = item;
                            else if (other == null && !item.IsEquipped && !(item is DoomerfallAmmoItem) && !(item is DoomerfallDoomItem) && !item.IsQuestItem)
                                other = item;
                        }
                        Check(bullets != null && other != null, string.Format("found bullets {0} and a Daggerfall item {1}",
                            bullets == null ? "none" : bullets.ItemName + " x" + bullets.stackCount, other == null ? "none" : other.ItemName));
                        foreach (DaggerfallUnityItem item in new[] { bullets, other })
                            if (item != null)
                                Click(window, "LocalItemListScroller_OnItemClick", item);
                        Next();
                        break;
                    case 3:
                        if (frames < WindowFrames)
                            return;
                        List<DaggerfallUnityItem> remote = Filtered(window, "remoteItemsFiltered");
                        Log("right-hand list after moving across: " + Names(remote));
                        Check(bullets != null && remote.Contains(bullets) && other != null && remote.Contains(other) && !items.Contains(bullets),
                            "both items moved to the right-hand list");
                        Shot("2-across.png"); // Captured at the end of this frame, so move back next step.
                        Next();
                        break;
                    case 4:
                        if (frames < WindowFrames)
                            return;
                        foreach (DaggerfallUnityItem item in Filtered(window, "remoteItemsFiltered"))
                            Click(window, "RemoteItemListScroller_OnItemClick", item);
                        Next();
                        break;
                    case 5:
                        if (frames < WindowFrames)
                            return;
                        List<DaggerfallUnityItem> local = Filtered(window, "localItemsFiltered");
                        Log("right-hand list after moving back: " + Names(Filtered(window, "remoteItemsFiltered")) + "; left: " + Names(local));
                        Check(Filtered(window, "remoteItemsFiltered").Count == 0 && other != null && items.Contains(other), "both items came back to the player's list");
                        Shot("3-back.png");
                        Next();
                        break;
                    case 6:
                        if (frames < WindowFrames)
                            return;
                        window.CloseWindow();
                        Next();
                        break;
                    case 7:
                        if (settled < SettleFrames)
                            return;
                        string after = ammo.Totals();
                        Check(after == before, "ammo counts after the round trip" + after + " (before" + before + ")");
                        Log(pass ? "PASS" : "FAIL");
                        step = -1;
                        break;
                }
            }
            catch (Exception e)
            {
                Log("FAIL exception " + e);
                step = -1;
            }
        }

        void Next()
        {
            step++;
            frames = 0;
            settled = 0;
        }

        void Layout(DaggerfallInventoryWindow window)
        {
            Check(window.GetType().Name == "ExpandedInventoryWindow", "inventory window is " + window.GetType().Name);
            BaseScreenComponent local = (BaseScreenComponent)Field(window, "localItemListScroller");
            BaseScreenComponent remote = (BaseScreenComponent)Field(window, "remoteItemListScroller");
            int localColumns = (int)Field(local, "listWidth");
            int remoteColumns = (int)Field(remote, "listWidth");
            Log(string.Format("left list at x {0} width {1} ({2} columns); right list at x {3} width {4} ({5} columns)",
                local.Position.x, local.Size.x, localColumns, remote.Position.x, remote.Size.x, remoteColumns));
            Check(localColumns == 4 && remoteColumns == 2, "4 columns on the left and 2 on the right");
            // The left list's scroll bar must sit after its last column and before the right-hand list.
            BaseScreenComponent scrollBar = (BaseScreenComponent)Field(local, "itemListScrollBar");
            float bar = local.Position.x + scrollBar.Position.x;
            Check(bar >= local.Position.x + localColumns * 23f && bar + scrollBar.Size.x <= remote.Position.x,
                string.Format("left scroll bar at x {0}-{1}, between the left list's last column (ends {2}) and the right list (starts {3})",
                    bar, bar + scrollBar.Size.x, local.Position.x + localColumns * 23f, remote.Position.x));
        }

        void Tabs(DaggerfallInventoryWindow window, ItemCollection items)
        {
            StringBuilder text = new StringBuilder();
            bool doomOk = true;
            int doomCount = 0;
            Dictionary<string, List<DaggerfallUnityItem>> lists = new Dictionary<string, List<DaggerfallUnityItem>>();
            foreach (string tab in new[] { "Weapons", "Armor", "JewelleryItems", "MagicItems", "Ingredients", "ReadingItems", "ClothingAndMisc" })
            {
                Select(window, tab);
                lists[tab] = Filtered(window, "localItemsFiltered");
            }
            for (int i = 0; i < items.Count; i++)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                if (!(item is DoomerfallAmmoItem) && !(item is DoomerfallDoomItem))
                    continue;
                doomCount++;
                List<string> on = new List<string>();
                foreach (var pair in lists)
                    if (pair.Value.Contains(item))
                        on.Add(pair.Key);
                bool armor = item is DoomerfallDoomItem && ((DoomerfallDoomItem)item).IsArmor && !((DoomerfallDoomItem)item).IsGun;
                bool equipped = item.IsEquipped; // Equipped items are on the paper doll, not in the list.
                doomOk &= equipped || (on.Count == 1 && on[0] == (armor ? "Armor" : "Weapons"));
                text.AppendFormat(" [{0} x{1}{2}: {3}]", item.ItemName, item.stackCount, equipped ? " equipped" : "", on.Count > 0 ? string.Join("+", on.ToArray()) : "no tab");
            }
            Log("Doom items by tab:" + text);
            Check(doomCount > 0 && doomOk, "Doom guns and ammo on Weapons, Doom armor on Armor, nowhere else");
        }

        static void Select(DaggerfallInventoryWindow window, string tab)
        {
            Type tabs = window.GetType().GetNestedType("LocalTabPages");
            window.GetType().GetField("localSelectedTabPage", Any).SetValue(window, Enum.Parse(tabs, tab));
            window.GetType().GetField("currentFilter1Value", Any).SetValue(window, -1);
            window.GetType().GetMethod("FilterLocalItems", Any).Invoke(window, null);
            window.GetType().GetMethod("FilterRemoteItems", Any).Invoke(window, null);
        }

        static List<DaggerfallUnityItem> Filtered(DaggerfallInventoryWindow window, string field)
        {
            return new List<DaggerfallUnityItem>((List<DaggerfallUnityItem>)Field(window, field));
        }

        static object Field(object target, string name)
        {
            for (Type t = target.GetType(); t != null; t = t.BaseType)
            {
                FieldInfo f = t.GetField(name, Any | BindingFlags.DeclaredOnly);
                if (f != null)
                    return f.GetValue(target);
            }
            throw new MissingFieldException(target.GetType().Name, name);
        }

        static string Names(List<DaggerfallUnityItem> list)
        {
            List<string> names = new List<string>();
            foreach (DaggerfallUnityItem item in list)
                names.Add(item.ItemName + (item.stackCount > 1 ? " x" + item.stackCount : ""));
            return names.Count == 0 ? "(empty)" : string.Join(", ", names.ToArray());
        }

        // The window's own click handler, in the Remove action mode (move to the other list).
        static void Click(DaggerfallInventoryWindow window, string handler, DaggerfallUnityItem item)
        {
            Type type = typeof(DaggerfallInventoryWindow);
            object action = Enum.Parse(type.GetNestedType("ActionModes", BindingFlags.NonPublic), "Remove");
            type.GetMethod(handler, Any).Invoke(window, new object[] { item, action });
        }
    }
}
