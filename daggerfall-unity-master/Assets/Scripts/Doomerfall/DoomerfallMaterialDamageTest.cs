// Doomerfall test only (-dfmaterialtest): two copies of one Doom gun in different Daggerfall materials, so a Doom
// harness (tools/ammo/ammo.py material) can show that the drawn gun's material scales the player's damage by the
// owner's table and multiplies with the loaded ammo's bonus. Gives shells a stand-in ammo bonus of +25%, and once the
// starting gun is adopted onto a hotkey, adds an Iron Shotgun on key 3, a Daedric Shotgun on key 4, and an Ebony DRLA
// Blaster (no reserve ammo) on key 5.
using System;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallMaterialDamageTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        bool gave;

        internal static void Attach(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfmaterialtest") >= 0)
                owner.gameObject.AddComponent<DoomerfallMaterialDamageTest>().Init(owner, tracker);
        }

        void Init(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            bridge = owner;
            ammo = tracker;
            DoomerfallAmmo.TestBonus = new[] { 0.0, 0.25, 0.0, 0.0 };
            bridge.LogLine("materialtest: stand-in ammo bonus Shell +25%");
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
                    bridge.LogLine("materialtest: the shotguns are already held (a loaded game)");
                    return;
                }
            }
            Give(items, hotkeys, 3, "Shotgun", WeaponMaterialTypes.Iron);
            Give(items, hotkeys, 4, "Shotgun", WeaponMaterialTypes.Daedric);
            Give(items, hotkeys, 5, "RLBlasterPickup", WeaponMaterialTypes.Ebony); // A gun with no reserve ammo.
        }

        // For the ammo-only tests (-dfequiptest, -dfchangeammotest): every Doom gun held becomes Steel (0%), so the damage
        // bonus they check is the ammo's alone.
        internal static void SteelGuns(DoomerfallBridge bridge, ItemCollection items)
        {
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem gun = items.GetItem(i) as DoomerfallDoomItem;
                if (gun != null && gun.IsGun)
                    gun.Material = WeaponMaterialTypes.Steel;
            }
            bridge.LogLine("test: every Doom gun held is now Steel, so only the ammo bonus shows");
        }

        void Give(ItemCollection items, DoomerfallHotkeys hotkeys, int key, string cls, WeaponMaterialTypes material)
        {
            DoomerfallDoomItem gun = new DoomerfallDoomItem(cls, true);
            gun.Material = material;
            items.AddItem(gun);
            hotkeys.Assign(key, 0, gun);
            bridge.LogLine(string.Format("materialtest: added \"{0}\" (modifier {1}) on key {2}", gun.ItemName, gun.GetWeaponMaterialModifier(), key));
        }
    }
}
