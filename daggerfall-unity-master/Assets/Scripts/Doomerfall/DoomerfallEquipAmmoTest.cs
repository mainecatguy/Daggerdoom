// Doomerfall test only (-dfequiptest): gives each ammo type a stand-in material bonus (bullets +50%, shells +25%), so
// the damage bonus shows which ammo Daggerfall thinks the ready gun has loaded. Once the starting gun is adopted onto
// a hotkey, it also adds a stock shotgun to Daggerfall's inventory on key 3, so the harness can equip it from
// Daggerfall with that hotkey (DFB_GUN_GIVE).
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallEquipAmmoTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        bool gave;

        internal void Init(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            bridge = owner;
            ammo = tracker;
            DoomerfallAmmo.TestBonus = new[] { 0.5, 0.25, 0.0, 0.0 };
            bridge.LogLine("equiptest: stand-in ammo bonuses Clip +50%, Shell +25%");
        }

        void Update()
        {
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            if (gave || !ammo.Ready || hotkeys == null || !GameManager.HasInstance)
                return;
            bool adopted = false;
            foreach (DoomerfallHotkeys.Square sq in hotkeys.table)
                adopted |= sq != null;
            if (!adopted)
                return;
            gave = true;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem old = items.GetItem(i) as DoomerfallDoomItem;
                if (old != null && old.DoomClass == "Shotgun")
                {
                    bridge.LogLine("equiptest: the shotgun is already held (a loaded game)");
                    return;
                }
            }
            DoomerfallDoomItem shotgun = new DoomerfallDoomItem("Shotgun", true);
            items.AddItem(shotgun);
            hotkeys.Assign(3, 0, shotgun);
            DoomerfallMaterialDamageTest.SteelGuns(bridge, items);
            bridge.LogLine("equiptest: added a shotgun on key 3");
        }
    }
}
