// Doomerfall test only (-dfinvtabstest): in a bridge session, logs which inventory tab lists each Doom ammo stack, using
// the inventory window's own tab filter (DaggerfallInventoryWindow.AddLocalItem). Logs again whenever the stacks change,
// after a load too, once both games agree on the counts (DoomerfallAmmo.Settled). Each line ends PASS when every ammo
// stack is on Weapons & Armor and nowhere else. Starts itself; no hook in game classes.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallInventoryTabsTest : MonoBehaviour
    {
        const int SettleFrames = 30;
        const float Interval = 0.5f;

        // The real window class, never shown: only its tab filter runs.
        sealed class Probe : DaggerfallInventoryWindow
        {
            public Probe(IUserInterfaceManager ui) : base(ui) { }

            public List<DaggerfallUnityItem> Tab(ItemCollection items, TabPages tab)
            {
                localItems = items;
                selectedTabPage = tab;
                FilterLocalItems();
                return new List<DaggerfallUnityItem>(localItemsFiltered);
            }
        }

        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        Probe probe;
        int settled;
        float next;
        string last;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfinvtabstest") < 0)
                return;
            GameObject host = new GameObject("DoomerfallInventoryTabsTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallInventoryTabsTest>();
        }

        void Update()
        {
            if (bridge == null)
                bridge = FindObjectOfType<DoomerfallBridge>();
            if (ammo == null)
                ammo = FindObjectOfType<DoomerfallAmmo>();
            if (bridge == null || ammo == null || !GameManager.HasInstance || DaggerfallUI.Instance == null)
                return;
            settled = ammo.Settled ? settled + 1 : 0;
            if (!ammo.Ready)
                last = null; // A load or a new game: report again once settled.
            if (settled < SettleFrames || Time.unscaledTime < next)
                return;
            next = Time.unscaledTime + Interval;
            if (probe == null)
                probe = new Probe(DaggerfallUI.UIManager);

            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            var tabs = (DaggerfallInventoryWindow.TabPages[])Enum.GetValues(typeof(DaggerfallInventoryWindow.TabPages));
            var lists = new List<DaggerfallUnityItem>[tabs.Length];
            for (int t = 0; t < tabs.Length; t++)
                lists[t] = probe.Tab(items, tabs[t]);

            StringBuilder text = new StringBuilder();
            bool pass = true;
            int stacks = 0;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallAmmoItem item = items.GetItem(i) as DoomerfallAmmoItem;
                if (item == null)
                    continue;
                stacks++;
                List<string> on = new List<string>();
                for (int t = 0; t < tabs.Length; t++)
                    if (lists[t].Contains(item))
                        on.Add(tabs[t].ToString());
                pass &= on.Count == 1 && on[0] == DaggerfallInventoryWindow.TabPages.WeaponsAndArmor.ToString();
                text.AppendFormat(" [{0} x{1}: {2}]", item.ItemName, item.stackCount, on.Count > 0 ? string.Join("+", on.ToArray()) : "no tab");
            }
            string line = text.ToString();
            if (line == last)
                return;
            last = line;
            bridge.LogLine(string.Format("invtabs: {0} ammo stacks, both games agree on the counts;{1}; Doom's counters{2} {3}",
                stacks, line, ammo.Totals(), stacks > 0 && pass ? "PASS" : stacks == 0 ? "NO AMMO" : "FAIL"));
        }
    }
}
