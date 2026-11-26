// Doomerfall test only (-dfpilestest): drops what the player would drop from Daggerfall's inventory window, for the
// location record's paired route (tools/location_record/piles.py). Outdoors, once the exterior record has no dropped
// pile, it drops a pile in front of the player. In a dungeon whose record has no dropped pile, it drops a pile and a
// modded DRLA shotgun through the window's own path (DoomerfallDoomItems.DropToDoom). Every few seconds it logs the
// dropped piles in the scene, so a route can see them leave and come back.

using System;
using System.Collections.Generic;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallPilesTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallLocations locations;
        float steadySince = -1, nextReport;
        string lastReport, lastPlace;

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync, DoomerfallLocations ledger)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfpilestest") < 0)
                return;
            DoomerfallPilesTest test = owner.gameObject.AddComponent<DoomerfallPilesTest>();
            test.bridge = owner;
            test.sync = positionSync;
            test.locations = ledger;
        }

        void Update()
        {
            if (!GameManager.HasInstance || !sync.InGame || !sync.Engaged || sync.LoadRunning || (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress))
            {
                steadySince = -1;
                return;
            }
            GameManager game = GameManager.Instance;
            PlayerEnterExit enter = game.PlayerEnterExit;
            string place = enter.IsPlayerInsideDungeon ? "dungeon" : enter.IsPlayerInside ? "building" : "outside";
            if (place != lastPlace)
            {
                lastPlace = place;
                steadySince = Time.unscaledTime;
            }
            if (steadySince < 0)
                steadySince = Time.unscaledTime;
            float steady = Time.unscaledTime - steadySince;
            int map = game.PlayerGPS.CurrentLocation.MapTableData.MapId;
            if (place == "outside" && steady > 4 && firstRun && !AnyExteriorPile())
                Drop("town", false);
            else if (place == "dungeon" && steady > 6 && firstRun && locations.Piles(Dfb.PLACE_DUNGEON, map, 0).Count == 0 && !droppedHere)
            {
                droppedHere = true;
                Drop("dungeon", true);
            }
            if (Time.unscaledTime >= nextReport)
            {
                nextReport = Time.unscaledTime + 3f;
                Report(place);
            }
        }

        bool droppedHere;
        // A load run (no -dfmonsterquest) starts in a held game before the save loads; a pile dropped there would leak into it.
        readonly bool firstRun = Array.IndexOf(Environment.GetCommandLineArgs(), "-dfmonsterquest") >= 0;

        bool AnyExteriorPile()
        {
            foreach (KeyValuePair<DoomerfallLocations.Place, List<DoomerfallLocations.PileData>> entry in locations.PilesOfKind(Dfb.PLACE_CHUNK))
                return true;
            return droppedTown;
        }

        bool droppedTown;

        void Drop(string where, bool gun)
        {
            if (where == "town")
                droppedTown = true;
            DaggerfallLoot loot = GameObjectHelper.CreateDroppedLootContainer(GameManager.Instance.PlayerObject, DaggerfallUnity.NextUID);
            loot.Items.AddItem(ItemBuilder.CreateItem(ItemGroups.Gems, (int)Gems.Ruby));
            loot.Items.AddItem(ItemBuilder.CreateGoldPieces(where == "town" ? 17 : 23));
            bridge.LogLine(string.Format("pilestest: dropped a {0} pile {1:x16} with {2} items at {3}", where, loot.LoadID, loot.Items.Count, loot.transform.position));
            if (!gun)
                return;
            DoomerfallDoomItem shotgun = new DoomerfallDoomItem("RLShotgunPickup", true);
            shotgun.GunState = "RLShotgunClip=3;RLShotgunModLimit=1;RLShotgunPowerMod=1";
            ItemCollection window = new ItemCollection();
            window.AddItem(shotgun);
            DoomerfallDoomItems.DropToDoom(window);
            bridge.LogLine(string.Format("pilestest: dropped Doom gun \"{0}\" through the inventory window's path; {1} left in the window's pile", shotgun.shortName, window.Count));
        }

        void Report(string place)
        {
            Transform root = place == "outside" ? GameManager.Instance.StreamingTarget.transform : place == "dungeon" ? GameManager.Instance.PlayerEnterExit.Dungeon.transform : GameManager.Instance.PlayerEnterExit.Interior.transform;
            if (!root)
                return;
            List<string> piles = new List<string>();
            foreach (DaggerfallLoot loot in root.GetComponentsInChildren<DaggerfallLoot>(true))
                if (loot.customDrop && loot.ContainerType == LootContainerTypes.DroppedLoot)
                    piles.Add(string.Format("{0:x16}:{1}", loot.LoadID, loot.Items.Count));
            piles.Sort();
            string text = string.Format("pilestest: {0} scene has {1} dropped piles [{2}]", place, piles.Count, string.Join(" ", piles.ToArray()));
            if (text == lastReport)
                return;
            lastReport = text;
            bridge.LogLine(text);
        }
    }
}
