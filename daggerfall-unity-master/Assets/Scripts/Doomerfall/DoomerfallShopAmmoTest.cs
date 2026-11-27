// Doomerfall test only (-dfshopammotest): once Doom's ammo counts have reached Daggerfall, logs the seeded general store
// ammo (DoomerfallShopAmmo) over 2,000 stores, restocks one general store shelf through Daggerfall's own StockShopShelf,
// opens Daggerfall's trade window on it in Buy mode, buys every ammo stack through the window's own handlers and Yes,
// and logs what the inventory gained. Doom's harness (tools/ammo, shop run) then fires the bought bullets and cells.

using System;
using System.Reflection;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopAmmoTest : MonoBehaviour
    {
        const BindingFlags Any = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
        const int Stores = 2000, TestGold = 50000;
        static readonly string[] Names = { "bullets", "shotgun shells", "rockets", "energy cells" };

        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        int step, frames, settled, goldBefore, baseValue;
        int[] before = new int[4];
        GameObject holder;
        DaggerfallTradeWindow trade;

        internal static void Attach(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshopammotest") < 0)
                return;
            DoomerfallShopAmmoTest test = owner.gameObject.AddComponent<DoomerfallShopAmmoTest>();
            test.bridge = owner;
            test.ammo = tracker;
        }

        void Log(string text) { bridge.LogLine("shopammo: " + text); }

        void Update()
        {
            if (step < 0 || !ammo.Ready || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            frames++;
            settled = ammo.Settled ? settled + 1 : 0;
            if (frames > 3000) { Log("gave up at step " + step); step = -1; return; }
            try
            {
                switch (step)
                {
                    case 0:
                        if (settled < 30) return;
                        Stats();
                        OpenShop(player);
                        Next();
                        break;
                    case 1: // Put every ammo stack in the basket, then ask to pay.
                        if (frames < 10) return;
                        for (int i = trade.MerchantItems.Count - 1; i >= 0; i--)
                        {
                            DoomerfallAmmoItem item = trade.MerchantItems.GetItem(i) as DoomerfallAmmoItem;
                            if (item == null)
                                continue;
                            Call(trade, typeof(DaggerfallTradeWindow), "RemoteItemListScroller_OnItemClick", item, Mode("Remove"));
                            if (DaggerfallUI.UIManager.TopWindow != trade)
                                Log("a click on " + item.ItemName + " opened " + DaggerfallUI.UIManager.TopWindow);
                        }
                        ItemCollection basket = (ItemCollection)typeof(DaggerfallTradeWindow).GetField("basketItems", Any).GetValue(trade);
                        Log(string.Format("basket holds {0} stacks, carried weight {1:0.0} of {2:0.0} kg", basket.Count, player.CarriedWeight, player.MaxEncumbrance));
                        Call(trade, typeof(DaggerfallTradeWindow), "DoModeAction");
                        Next();
                        break;
                    case 2: // Daggerfall's trade question: Yes.
                    {
                        if (frames < 10) return;
                        DaggerfallMessageBox box = DaggerfallUI.UIManager.TopWindow as DaggerfallMessageBox;
                        if (box == null) { Log("no trade question; top window " + DaggerfallUI.UIManager.TopWindow); step = -1; return; }
                        Call(box, typeof(DaggerfallMessageBox), "ActivateButton", new Button { Tag = DaggerfallMessageBox.MessageBoxButtons.Yes });
                        Next();
                        break;
                    }
                    case 3: // Close the window once the purchase is done, and report.
                    {
                        if (frames < 10) return;
                        while (DaggerfallUI.UIManager.TopWindow != trade && DaggerfallUI.UIManager.WindowCount > 1)
                            DaggerfallUI.UIManager.PopWindow();
                        trade.CloseWindow();
                        string gained = "";
                        for (int t = 0; t < before.Length; t++)
                            gained += string.Format("{0}{1} +{2}", t > 0 ? ", " : "", Names[t], DoomerfallAmmo.Total(player.Items, t) - before[t]);
                        Log(string.Format("bought for {0} gold of base value {5}, region price {6}/1000 (gold {1} -> {2}); inventory gained {3}; holds{4}",
                            goldBefore - player.GetGoldAmount(), goldBefore, player.GetGoldAmount(), gained, ammo.Totals(), baseValue, RegionPrice()));
                        Destroy(holder);
                        step = -1;
                        break;
                    }
                }
            }
            catch (Exception e)
            {
                Log("error: " + e);
                step = -1;
            }
        }

        void Next() { step++; frames = 0; }

        // The fixed stock of many general stores, quality 1-20 in turn, one restock each.
        void Stats()
        {
            int n = Names.Length;
            double[] sum = new double[n], sq = new double[n];
            int[] min = new int[n], max = new int[n];
            int leaning = 0;
            for (int t = 0; t < n; t++) { min[t] = int.MaxValue; max[t] = 0; }
            for (int i = 0; i < Stores; i++)
            {
                int[] a = DoomerfallShopAmmo.Restock(DFLocation.BuildingTypes.GeneralStore, i % 20 + 1, 1000 + i / 7, i % 7 + 1);
                bool lean = false;
                for (int t = 0; t < n; t++)
                {
                    sum[t] += a[t]; sq[t] += (double)a[t] * a[t];
                    min[t] = Math.Min(min[t], a[t]); max[t] = Math.Max(max[t], a[t]);
                    lean |= a[t] > 2 * DoomerfallShopAmmo.Average[t];
                }
                if (lean) leaning++;
                if (i < 8)
                    Log(string.Format("store {0} (quality {1}): {2} bullets, {3} shells, {4} rockets, {5} cells", i, i % 20 + 1, a[0], a[1], a[2], a[3]));
            }
            for (int t = 0; t < n; t++)
            {
                double mean = sum[t] / Stores;
                Log(string.Format("stats {0}: mean {1:0.0} min {2} max {3} sd {4:0.0}", Names[t], mean, min[t], max[t], Math.Sqrt(sq[t] / Stores - mean * mean)));
            }
            Log(string.Format("{0} of {1} stores hold over twice the average of some type", leaning, Stores));
            int[] again = DoomerfallShopAmmo.Restock(DFLocation.BuildingTypes.GeneralStore, 10, 1234, 5);
            float[] fixedA = DoomerfallShopAmmo.Expected(DFLocation.BuildingTypes.GeneralStore, 10, 1234, 5);
            float[] fixedB = DoomerfallShopAmmo.Expected(DFLocation.BuildingTypes.GeneralStore, 10, 1234, 5);
            Log(string.Format("same store twice: fixed amounts {0}, a restock {1} bullets", fixedA[0] == fixedB[0] && fixedA[3] == fixedB[3] ? "equal" : "DIFFERENT", again[0]));
            Log(string.Format("other shops: armorer {0}, pawn shop {1}, alchemist {2}",
                DoomerfallShopAmmo.Sells(DFLocation.BuildingTypes.Armorer), DoomerfallShopAmmo.Sells(DFLocation.BuildingTypes.PawnShop), DoomerfallShopAmmo.Sells(DFLocation.BuildingTypes.Alchemist)));
        }

        void OpenShop(PlayerEntity player)
        {
            holder = new GameObject("Doomerfall shop ammo test");
            DaggerfallLoot shelf = holder.AddComponent<DaggerfallLoot>();
            PlayerGPS.DiscoveredBuilding building = new PlayerGPS.DiscoveredBuilding { buildingType = DFLocation.BuildingTypes.GeneralStore, quality = 10, buildingKey = 77, displayName = "Test General Store" };
            shelf.StockShopShelf(building);
            string text = "";
            for (int i = 0; i < shelf.Items.Count; i++)
            {
                DoomerfallAmmoItem item = shelf.Items.GetItem(i) as DoomerfallAmmoItem;
                if (item == null)
                    continue;
                text += string.Format(" [{0} x{1} {2} gold]", item.ItemName, item.stackCount, item.value);
                baseValue += item.value * item.stackCount;
            }
            Log(string.Format("general store shelf:{0} ({1} items in all)", text, shelf.Items.Count));
            for (int t = 0; t < before.Length; t++)
                before[t] = DoomerfallAmmo.Total(player.Items, t);
            // Test money, so the whole stock can be bought: a letter of credit, since that much coin would be too heavy to carry.
            DaggerfallUnityItem credit = ItemBuilder.CreateItem(ItemGroups.MiscItems, (int)MiscItems.Letter_of_credit);
            credit.value = TestGold;
            player.Items.AddItem(credit);
            goldBefore = player.GetGoldAmount();
            // The test character's regions never had Daggerfall's price roll (750-1250 in a real game); 0 would make
            // everything cost the minimum. 900 is a region priced under 100%, where per-round rounding made bullets free.
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            if (gps.HasCurrentLocation && player.RegionData[gps.CurrentRegionIndex].PriceAdjustment == 0)
                player.RegionData[gps.CurrentRegionIndex].PriceAdjustment = 900;
            trade = (DaggerfallTradeWindow)UIWindowFactory.GetInstanceWithArgs(UIWindowType.Trade,
                new object[] { DaggerfallUI.UIManager, null, DaggerfallTradeWindow.WindowModes.Buy, null });
            trade.MerchantItems = shelf.Items;
            DaggerfallUI.UIManager.PushWindow(trade);
            // The test runs outside any shop, so the window found no building ("old save, no trade"): give it this
            // general store, so it prices by the store's quality as it does in a real shop, and close the notice.
            typeof(DaggerfallTradeWindow).GetField("buildingDiscoveryData", Any).SetValue(trade, building);
            if (DaggerfallUI.UIManager.TopWindow is DaggerfallMessageBox)
                DaggerfallUI.UIManager.PopWindow();
        }

        static int RegionPrice()
        {
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            return gps.HasCurrentLocation ? GameManager.Instance.PlayerEntity.RegionData[gps.CurrentRegionIndex].PriceAdjustment : 1000;
        }

        static object Mode(string name)
        {
            return Enum.Parse(typeof(DaggerfallInventoryWindow).GetNestedType("ActionModes", BindingFlags.NonPublic), name);
        }

        static void Call(object target, Type type, string name, params object[] args)
        {
            MethodInfo method = type.GetMethod(name, Any);
            if (method == null)
                throw new MissingMethodException(type.Name, name);
            method.Invoke(target, args);
        }
    }
}
