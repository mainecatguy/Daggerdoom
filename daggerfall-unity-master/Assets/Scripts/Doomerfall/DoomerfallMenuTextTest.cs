// Doomerfall test only (-dfmenutexttest): in a bridge session, shows item info text in Daggerfall's inventory so the
// text Doom shows can be compared with Daggerfall Unity's. Gives the player Casual Pants (the item in the owner's
// screenshot), and whenever the inventory is the top window, fills its info panel with that item, as hovering would.
// Starts itself; no hook in game classes. Used by tools/menu_text/menu_text.py --menutext.

using System;
using System.Collections;
using System.Reflection;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMenuTextTest : MonoBehaviour
    {
        static readonly MethodInfo UpdateInfo = typeof(DaggerfallInventoryWindow).GetMethod("UpdateItemInfoPanel",
            BindingFlags.Instance | BindingFlags.NonPublic, null, new[] { typeof(DaggerfallUnityItem) }, null);

        DaggerfallUnityItem pants;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            if (Array.IndexOf(args, "-dfmenutexttest") < 0 || Array.IndexOf(args, "-dfbridge") < 0)
                return;
            GameObject host = new GameObject("DoomerfallMenuTextTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallMenuTextTest>();
        }

        IEnumerator Start()
        {
            while (GameObject.FindWithTag("Player") == null || DaggerfallUI.Instance == null || !GameManager.HasInstance || !GameManager.Instance.IsReady)
                yield return null;
            yield return new WaitForSecondsRealtime(3f); // the paired test character is given after the scene is ready
            pants = ItemBuilder.CreateItem(ItemGroups.MensClothing, (int)MensClothing.Casual_pants);
            GameManager.Instance.PlayerEntity.Items.AddItem(pants);
        }

        void Update()
        {
            if (pants == null || !DaggerfallUI.Instance)
                return;
            var inventory = DaggerfallUI.UIManager.TopWindow as DaggerfallInventoryWindow;
            if (inventory != null && UpdateInfo != null)
                UpdateInfo.Invoke(inventory, new object[] { pants });
        }
    }
}
