// Doomerfall test only (-dfammotest): makes one change to the ammo stacks on Daggerfall's side, as a drop and a pile
// would, once Doom's bullets have arrived. Daggerfall then sends the change to Doom (DoomerfallAmmo).
using DaggerfallWorkshop.Game.Entity;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallAmmoTest : MonoBehaviour
    {
        const int DropBullets = 7, AddShells = 20, MinBullets = 60;
        DoomerfallBridge bridge;
        DoomerfallAmmo ammo;
        bool done;

        internal void Init(DoomerfallBridge owner, DoomerfallAmmo tracker)
        {
            bridge = owner;
            ammo = tracker;
        }

        void Update()
        {
            if (done || !ammo.Ready || !GameManager.HasInstance)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            // The harness picks up bullets first, so this waits for more than a fresh start holds.
            if (DoomerfallAmmo.Total(player.Items, 0) < MinBullets)
                return;
            done = true;
            DoomerfallAmmo.Change(player.Items, 0, -DropBullets);
            DoomerfallAmmo.Change(player.Items, 1, AddShells);
            bridge.LogLine(string.Format("ammotest: Daggerfall dropped {0} bullets and took {1} shells, now holds{2}", DropBullets, AddShells, ammo.Totals()));

            // Arrow weight: 100 arrows should add 1 kg.
            float before = player.CarriedWeight;
            DaggerfallWorkshop.Game.Items.DaggerfallUnityItem arrows = DaggerfallWorkshop.Game.Items.ItemBuilder.CreateWeapon(DaggerfallWorkshop.Game.Items.Weapons.Arrow, DaggerfallWorkshop.Game.Items.WeaponMaterialTypes.Iron);
            arrows.stackCount = 100;
            player.Items.AddItem(arrows);
            float after = player.CarriedWeight;
            player.Items.RemoveItem(arrows);
            bridge.LogLine(string.Format("ammotest: 100 arrows ({0} kg each) add {1:F2} kg", arrows.weightInKg, after - before));
        }
    }
}
