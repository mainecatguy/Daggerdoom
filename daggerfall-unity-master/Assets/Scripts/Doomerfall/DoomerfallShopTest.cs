// Doomerfall test only (-dfshoptest): plays a shop visit inside the windows Doom's Use opened, through each window's
// own handlers, so a minimized test can prove the route. The first merchant menu picks Sell, later ones pick Talk.
// A Sell window sells one item, the first Buy window (a shelf) buys the cheapest one, both confirmed with Daggerfall's
// own Yes. Any other window (such as the private property question) is closed. Gold and inventory are logged.
// With -dfshopdoomgun, the first merchant menu first gives the player Doom guns (DRLA's pistol, shotgun and BFG, one
// Daedric) and logs their value, weight and this shop's price; the Sell window then sells a Doom gun only.

using System;
using System.Collections.Generic;
using System.Reflection;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopTest : MonoBehaviour
    {
        const float ActSeconds = 1.5f;
        const BindingFlags Any = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;

        DoomerfallBridge bridge;
        IUserInterfaceWindow seen;
        float actAt;
        bool acted, confirming, bought;
        int menus;
        int goldBefore, countBefore;
        string traded;
        readonly bool doomGun = Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshopdoomgun") >= 0;
        bool given;
        DaggerfallUnityItem sold;

        internal void Init(DoomerfallBridge owner)
        {
            bridge = owner;
        }

        void Log(string text) { bridge.LogLine("shoptest: " + text); }

        static PlayerEntity Player { get { return GameManager.Instance.PlayerEntity; } }

        void Update()
        {
            if (!DaggerfallUI.Instance || !DoomerfallInput.Active)
            {
                seen = null;
                return;
            }
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            if (top != seen)
            {
                seen = top;
                acted = false;
                actAt = Time.unscaledTime + ActSeconds;
                Log("window " + (top == null ? "none" : top.GetType().Name));
            }
            if (acted || Time.unscaledTime < actAt || !(top is UserInterfaceWindow) || top is DaggerfallHUD)
                return;
            acted = true;
            try { Act(top); }
            catch (Exception e)
            {
                Log("error: " + e);
                ((UserInterfaceWindow)top).CloseWindow();
            }
        }

        void Act(IUserInterfaceWindow top)
        {
            DaggerfallTradeWindow trade = top as DaggerfallTradeWindow;
            DaggerfallMessageBox box = top as DaggerfallMessageBox;
            string mode = trade != null ? typeof(DaggerfallTradeWindow).GetProperty("WindowMode", Any).GetValue(trade, null).ToString() : null;
            if (top is DaggerfallMerchantServicePopupWindow || top is DaggerfallMerchantRepairPopupWindow)
            {
                if (doomGun && !given)
                    GiveGuns();
                // A shop's menu (Talk / Sell / Exit), or a repair shop's (Repair / Talk / Sell / Exit): Sell first, then Talk.
                string handler = menus++ > 0 ? "TalkButton_OnMouseClick" : top is DaggerfallMerchantRepairPopupWindow ? "SellButton_OnMouseClick" : "ServiceButton_OnMouseClick";
                Log(string.Format("{0} {1}: pressing {2}", top.GetType().Name, menus, handler));
                Call(top, top.GetType(), handler, null, Vector2.zero);
            }
            else if (trade != null && mode == "Buy" && bought && traded == null)
            {
                Log("already bought; closing the Buy window");
                trade.CloseWindow();
            }
            else if (trade != null && !confirming && traded == null)
            {
                if (mode == "Buy")
                    bought = true;
                goldBefore = Player.GoldPieces;
                countBefore = Player.Items.Count;
                DaggerfallUnityItem item = mode == "Buy" ? Cheapest(Filtered(trade, "remoteItemsFiltered")) : null;
                // The player's list shows one tab at a time, so look through each tab as a player would.
                foreach (DaggerfallInventoryWindow.TabPages tab in Enum.GetValues(typeof(DaggerfallInventoryWindow.TabPages)))
                {
                    if (item != null || mode == "Buy")
                        break;
                    Call(trade, typeof(DaggerfallInventoryWindow), "SelectTabPage", tab);
                    item = Sellable(Filtered(trade, "localItemsFiltered"));
                }
                if (item == null)
                {
                    List<DaggerfallUnityItem> shown = Filtered(trade, mode == "Buy" ? "remoteItemsFiltered" : "localItemsFiltered");
                    var names = new List<string>();
                    if (shown != null)
                        foreach (DaggerfallUnityItem each in shown)
                            names.Add(string.Format("{0} (value {1}{2})", each.LongName, each.value, each.IsEquipped ? ", equipped" : ""));
                    Log(string.Format("{0} window: nothing to trade among {1} shown: {2}", mode, names.Count, string.Join(", ", names.ToArray())));
                    trade.CloseWindow();
                    return;
                }
                traded = mode + " \"" + item.LongName + "\"";
                sold = item;
                Log(string.Format("{0} window ({1} merchant items): choosing \"{2}\" (value {3}, shop price {6}), gold {4}, carried {5}", mode,
                    trade.MerchantItems != null ? trade.MerchantItems.Count : -1, item.LongName, item.value, goldBefore, countBefore,
                    FormulaHelper.CalculateCost(item.value, GameManager.Instance.PlayerEnterExit.BuildingDiscoveryData.quality, item.ConditionPercentage)));
                Type actions = typeof(DaggerfallInventoryWindow).GetNestedType("ActionModes", Any);
                // Remove buys without equipping (Select would equip it), so the bought item can be sold back.
                object select = Enum.Parse(actions, mode == "Buy" ? "Remove" : "Select");
                Call(trade, typeof(DaggerfallTradeWindow), mode == "Buy" ? "RemoteItemListScroller_OnItemClick" : "LocalItemListScroller_OnItemClick", item, select);
                confirming = true;
                Call(trade, typeof(DaggerfallTradeWindow), "DoModeAction");
            }
            else if (trade != null)
            {
                Log(string.Format("{0} done: gold {1} to {2}, carried {3} to {4}, item still carried {5}", traded, goldBefore, Player.GoldPieces, countBefore, Player.Items.Count,
                    sold != null && Player.Items.Contains(sold)));
                traded = null;
                trade.CloseWindow();
            }
            else if (box != null && confirming)
            {
                confirming = false;
                Log("answering Yes to the trade question");
                Button yes = new Button { Tag = DaggerfallMessageBox.MessageBoxButtons.Yes };
                Call(box, typeof(DaggerfallMessageBox), "ActivateButton", yes);
            }
            else if (top is DaggerfallTalkWindow)
            {
                TalkManager talk = GameManager.Instance.TalkManager;
                StaticNPC npc = talk.StaticNPC;
                Log(string.Format("talking to \"{0}\" (static npc {1}, faction {2}), greeting \"{3}\"", talk.NameNPC,
                    npc ? npc.DisplayName : "none", npc ? npc.Data.factionID : -1, talk.NPCGreetingText));
                ((UserInterfaceWindow)top).CloseWindow();
            }
            else
            {
                Log("closing " + top.GetType().Name);
                ((UserInterfaceWindow)top).CloseWindow();
            }
        }

        static void Call(object target, Type type, string name, params object[] args)
        {
            MethodInfo method = type.GetMethod(name, Any);
            if (method == null)
                throw new MissingMethodException(type.Name, name);
            method.Invoke(target, args);
        }

        static List<DaggerfallUnityItem> Filtered(DaggerfallTradeWindow trade, string field)
        {
            FieldInfo info = typeof(DaggerfallInventoryWindow).GetField(field, Any);
            return info != null ? info.GetValue(trade) as List<DaggerfallUnityItem> : null;
        }

        // An ordinary Daggerfall item the store takes: not equipped, not a Doom item, not a quest item, worth something.
        // With -dfshopdoomgun, a Doom gun instead.
        DaggerfallUnityItem Sellable(List<DaggerfallUnityItem> items)
        {
            if (items == null) return null;
            foreach (DaggerfallUnityItem item in items)
                if (!item.IsEquipped && (item is DoomerfallDoomItem) == doomGun && !item.IsQuestItem && item.value > 0)
                    return item;
            return null;
        }

        void GiveGuns()
        {
            given = true;
            int quality = GameManager.Instance.PlayerEnterExit.BuildingDiscoveryData.quality;
            foreach (string cls in new[] { "RLPistolPickup", "RLShotgunPickup", "RLBFG9000Pickup" })
            {
                DoomerfallDoomItem gun = DoomerfallDoomItem.Create(cls, Dfb.DOOM_ITEM_GUN);
                if (cls == "RLBFG9000Pickup")
                {
                    gun.Material = WeaponMaterialTypes.Daedric;
                    DoomerfallWeaponValues.Apply(gun);
                }
                Player.Items.AddItem(gun);
                // The test town has no weaponsmith or pawn shop, so ask the trade window's own buy lists directly.
                var buys = (Dictionary<DaggerfallConnect.DFLocation.BuildingTypes, List<ItemGroups>>)typeof(DaggerfallTradeWindow)
                    .GetField("storeBuysItemType", BindingFlags.Static | BindingFlags.NonPublic).GetValue(null);
                foreach (var shop in new[] { DaggerfallConnect.DFLocation.BuildingTypes.WeaponSmith, DaggerfallConnect.DFLocation.BuildingTypes.PawnShop, DaggerfallConnect.DFLocation.BuildingTypes.Alchemist })
                    Log(string.Format("{0} buys \"{1}\": {2}", shop, gun.ItemName, DoomerfallWeaponValues.SellsHere(gun, buys[shop])));
                Log(string.Format("gave \"{0}\" ({1}, {2}): value {3}, {4} kg, shop price {5} at quality {6}", gun.ItemName, cls, gun.Material, gun.value, gun.weightInKg,
                    FormulaHelper.CalculateCost(gun.value, quality, gun.ConditionPercentage), quality));
            }
        }

        static DaggerfallUnityItem Cheapest(List<DaggerfallUnityItem> items)
        {
            DaggerfallUnityItem best = null;
            if (items != null)
                foreach (DaggerfallUnityItem item in items)
                    // Worth something, and a kind a general store buys back (weapons, clothing, books, jewellery), so
                    // the Sell step has something to sell.
                    if (item.value > 0 && (item.ItemGroup == ItemGroups.Weapons || item.ItemGroup == ItemGroups.MensClothing ||
                        item.ItemGroup == ItemGroups.WomensClothing || item.ItemGroup == ItemGroups.Books || item.ItemGroup == ItemGroups.Jewellery) &&
                        (best == null || item.value < best.value))
                        best = item;
            return best;
        }
    }
}
