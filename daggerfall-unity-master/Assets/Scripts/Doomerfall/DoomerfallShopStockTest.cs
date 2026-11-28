// Doomerfall test only (-dfshoptest): once Daggerfall is in a game, restocks a quality-20 weapon smith shelf and a
// general store shelf through Daggerfall's own StockShopShelf, and logs the tiered ammo each one got.

using System;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallShopStockTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        bool done;

        internal static void Attach(DoomerfallBridge owner)
        {
            DoomerfallShopLevelRatesTest.Attach(owner);   // -dfshoplevelrates
            DoomerfallShopLedgerTest.Attach(owner);       // -dfshopledgertest
            DoomerfallShopLotsTest.Attach(owner);         // -dfshoplotstest
            DoomerfallShopIdentityTest.Attach(owner);     // -dfshopidentitytest
            DoomerfallLockpickSurveyTest.Attach(owner);   // -dflockpicksurvey
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfshoptest") >= 0)
                owner.gameObject.AddComponent<DoomerfallShopStockTest>().bridge = owner;
        }

        void Update()
        {
            if (done || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || GameManager.Instance.PlayerGPS == null)
                return;
            if (Time.frameCount < 600)
                return;
            done = true;
            foreach (DFLocation.BuildingTypes type in new[] { DFLocation.BuildingTypes.WeaponSmith, DFLocation.BuildingTypes.GeneralStore })
            {
                GameObject holder = new GameObject("Doomerfall shop test");
                DaggerfallLoot shelf = holder.AddComponent<DaggerfallLoot>();
                shelf.StockShopShelf(new PlayerGPS.DiscoveredBuilding { buildingType = type, quality = 20 });
                string text = "";
                for (int i = 0; i < shelf.Items.Count; i++)
                {
                    DoomerfallAmmoItem item = shelf.Items.GetItem(i) as DoomerfallAmmoItem;
                    if (item != null)
                        text += string.Format(" [{0} x{1} {2} gold]", item.ItemName, item.stackCount, item.value);
                }
                bridge.LogLine(string.Format("shoptest: {0} shelf has {1} items; ammo:{2}", type, shelf.Items.Count, text));
                Destroy(holder);
            }
        }
    }
}
