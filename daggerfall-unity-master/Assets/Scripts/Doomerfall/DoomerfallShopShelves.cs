// Doomerfall: the level a shop's shelves roll at (weapon and armor material, magic items, modded weapons and armor).
// Runs only in a bridge session, as WorldLevel.ShopProvider.
//
// Inputs:  the building the player is in (PlayerEnterExit.BuildingDiscoveryData) and the current location's
//          building directory.
// Outputs: the shop's level from DoomerfallShopLevels, 1 to 30, or 0 if the building is not a known shop. With 0,
//          WorldLevel.Scope does nothing and the shelf rolls at the area level, as before.
// Shop ammo (DoomerfallAmmoTiers.StockShop) runs inside the same scope, so WorldLevel.Current is the shop level there
// too, but its odds do not read it yet: they wait on the owner's tiered ammo in shops question.

using System;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallShopShelves
    {
        internal static int Level(PlayerGPS.DiscoveredBuilding building, Action<string> log)
        {
            int level = 0;
            string where = "no building directory";
            BuildingDirectory directory = GameManager.HasInstance && GameManager.Instance.StreamingWorld != null
                ? GameManager.Instance.StreamingWorld.GetCurrentBuildingDirectory() : null;
            BuildingSummary summary;
            if (directory && directory.GetBuildingSummary(building.buildingKey, out summary))
            {
                level = DoomerfallShopLevels.ForShop(directory.LocationData, summary);
                where = string.Format("{0} / {1}", directory.LocationData.RegionName, directory.LocationData.Name);
            }
            else if (directory)
                where = "building " + building.buildingKey + " not in directory";
            if (log != null)
                log(string.Format("shop restock: {0} ({1}, quality {2}) in {3} at shop level {4}{5}", building.displayName,
                    building.buildingType, building.quality, where, level, level > 0 ? "" : " (area level used)"));
            return level;
        }
    }
}
