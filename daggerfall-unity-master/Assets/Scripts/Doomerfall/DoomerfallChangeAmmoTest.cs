// Doomerfall test only (-dfchangeammotest): once the starting gun is adopted onto a hotkey, adds 30 Regular, 20 Steel,
// and 10 Silver bullets and a DRLA pistol with 10 rounds in its magazine on key 4, so tools/ammo/ammo.py change can
// press the change ammo key, run the loaded tier dry, and check the automatic change and the magazine unload.
using System;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallChangeAmmoTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        bool gave;

        internal static void Attach(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfchangeammotest") < 0)
                return;
            DoomerfallChangeAmmoTest test = owner.gameObject.AddComponent<DoomerfallChangeAmmoTest>();
            test.bridge = owner;
            test.ammo = tracker;
        }

        void Update()
        {
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            if (gave || !ammo.Ready || hotkeys == null || !GameManager.HasInstance || hotkeys.ActiveGun == null)
                return;
            gave = true;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem old = items.GetItem(i) as DoomerfallDoomItem;
                if (old != null && old.IsGun && old.DoomClass == "RLPistolPickup" && old != hotkeys.ActiveGun)
                {
                    bridge.LogLine("changeammotest: the test pistol is already held (a loaded game)");
                    return;
                }
            }
            items.AddItem(new DoomerfallAmmoItem(0, DoomerfallAmmoTiers.Regular, 30));
            items.AddItem(new DoomerfallAmmoItem(0, 1, 20)); // Steel
            items.AddItem(new DoomerfallAmmoItem(0, 2, 10)); // Silver
            DoomerfallDoomItem pistol = new DoomerfallDoomItem("RLPistolPickup", true);
            pistol.GunState = "RLPistolClip=10";
            items.AddItem(pistol);
            hotkeys.Assign(4, 0, pistol);
            bridge.LogLine("changeammotest: added 30 Regular, 20 Steel, 10 Silver bullets and a DRLA pistol (10 in its magazine) on key 4");
            // The reload checks: two more DRLA guns with part-full magazines and a stock Doom shotgun (no magazine).
            items.AddItem(new DoomerfallAmmoItem(1, DoomerfallAmmoTiers.Regular, 12));
            items.AddItem(new DoomerfallAmmoItem(1, 1, 8)); // Steel shells
            AddGun(items, hotkeys, 5, "RLShotgunPickup", "RLShotgunClip=1");
            AddGun(items, hotkeys, 6, "RLChaingunPickup", "RLChaingunClip=7");
            AddGun(items, hotkeys, 7, "Shotgun", null);
            bridge.LogLine("changeammotest: added 12 Regular and 8 Steel shells, a DRLA shotgun (1) on key 5, a DRLA chaingun (7) on key 6, a stock shotgun on key 7");
        }

        static void AddGun(ItemCollection items, DoomerfallHotkeys hotkeys, int key, string doomClass, string state)
        {
            DoomerfallDoomItem gun = new DoomerfallDoomItem(doomClass, true);
            if (state != null)
                gun.GunState = state;
            items.AddItem(gun);
            hotkeys.Assign(key, 0, gun);
        }
    }
}
