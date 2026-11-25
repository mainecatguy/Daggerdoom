// Expanded Inventory (Nexus mod 1184, by Alex Falconson, AlikFalcon and LechatSokolov), built into Doomerfall's
// Daggerfall Unity instead of loaded as a .dfmod (owner, 2026-11-24). The mod registered its window from its mod
// Init; here it registers once the first scene has loaded, before Daggerfall's UI makes its inventory window.
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace ExpandedInventoryModHook
{
    public static class ExpandedInventory
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Register()
        {
            if (!ExpandedInventoryArt.Installed())
            {
                Debug.Log("ExpandedInventory: art not installed in " + ExpandedInventoryArt.Folder + "; keeping Daggerfall's inventory window");
                return;
            }
            UIWindowFactory.RegisterCustomUIWindow(UIWindowType.Inventory, typeof(ExpandedInventoryWindow));
            Debug.Log("ExpandedInventory: inventory window registered");
        }
    }
}
