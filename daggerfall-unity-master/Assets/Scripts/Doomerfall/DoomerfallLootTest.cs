// Doomerfall test only (-dfloottest): acts inside whichever container window Doom's Use opened, through the
// window's own code, so a minimized test can prove the whole route. It takes the first item from a loot window,
// answers Yes to the private property question, and closes a trade window after reporting it.

using System.Reflection;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallLootTest : MonoBehaviour
    {
        const float ActSeconds = 1.0f;

        DoomerfallBridge bridge;
        IUserInterfaceWindow seen;
        float actAt;
        bool acted;

        internal void Init(DoomerfallBridge owner)
        {
            bridge = owner;
        }

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
                bridge.LogLine("loottest: window " + (top == null ? "none" : top.GetType().Name));
            }
            if (acted || top == null || Time.unscaledTime < actAt)
                return;
            acted = true;

            DaggerfallInventoryWindow inventory = top as DaggerfallInventoryWindow;
            DaggerfallTradeWindow trade = top as DaggerfallTradeWindow;
            DaggerfallMessageBox box = top as DaggerfallMessageBox;
            if (inventory != null && inventory.LootTarget != null)
            {
                ItemCollection remote = inventory.LootTarget.Items;
                int before = remote.Count;
                if (before > 0)
                {
                    DaggerfallUnityItem item = remote.GetItem(0);
                    string name = item.LongName;
                    MethodInfo transfer = typeof(DaggerfallInventoryWindow).GetMethod("TransferItem", BindingFlags.Instance | BindingFlags.NonPublic);
                    transfer.Invoke(inventory, new object[] { item, remote, GameManager.Instance.PlayerEntity.Items, null, false, false, true });
                    bridge.LogLine(string.Format("loottest: took \"{0}\" from {1}, {2} to {3} items, gold {4}", name, inventory.LootTarget.ContainerType, before, remote.Count, GameManager.Instance.PlayerEntity.GoldPieces));
                }
                inventory.CloseWindow();
            }
            else if (trade != null)
            {
                bridge.LogLine(string.Format("loottest: trade window with {0} merchant items", trade.MerchantItems != null ? trade.MerchantItems.Count : -1));
                trade.CloseWindow();
            }
            else if (box != null)
            {
                bridge.LogLine("loottest: answering Yes to the message box");
                GameManager.Instance.PlayerActivate.PrivateProperty_OnButtonClick(box, DaggerfallMessageBox.MessageBoxButtons.Yes);
            }
            else if (!(top is DaggerfallHUD) && top is UserInterfaceWindow)
            {
                ((UserInterfaceWindow)top).CloseWindow();
            }
        }
    }
}
