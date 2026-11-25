// Doomerfall test only (-dfgundroptest): drops a shotgun from Daggerfall's inventory through the inventory window's own
// path (DoomerfallDoomItems.DropToDoom), for the gun ammo route (tools/location_record/gunammo.py). Each time a
// shotgun has been in the inventory for 6 s, it is dropped, three times in all; the route takes it back with Use.

using System;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallGunDropTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        ulong seenUid;
        float seenSince;
        int drops;

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfgundroptest") < 0)
                return;
            DoomerfallGunDropTest test = owner.gameObject.AddComponent<DoomerfallGunDropTest>();
            test.bridge = owner;
            test.sync = positionSync;
        }

        void Update()
        {
            if (drops >= 3 || !GameManager.HasInstance || !sync.InGame || !sync.Engaged || sync.LoadRunning)
                return;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            DoomerfallDoomItem gun = null;
            for (int i = 0; i < items.Count && gun == null; i++)
            {
                DoomerfallDoomItem doom = items.GetItem(i) as DoomerfallDoomItem;
                if (doom != null && doom.IsGun && (doom.DoomClass.StartsWith("RLShotgun") || doom.DoomClass == "Shotgun"))
                    gun = doom;
            }
            if (gun == null)
            {
                seenUid = 0;
                return;
            }
            if (gun.UID != seenUid)
            {
                seenUid = gun.UID;
                seenSince = Time.unscaledTime;
                return;
            }
            if (Time.unscaledTime - seenSince < 6f)
                return;
            drops++;
            seenUid = 0;
            bool held = DoomerfallHotkeys.Instance != null && DoomerfallHotkeys.Instance.ActiveGun == gun;
            ItemCollection window = new ItemCollection();
            window.Transfer(gun, items); // as the window does: the dropped items leave the inventory first
            DoomerfallDoomItems.DropToDoom(window);
            bridge.LogLine(string.Format("gundroptest: drop {0} of \"{1}\" (held {2}) through the inventory window's path", drops, gun.shortName, held));
        }
    }
}
