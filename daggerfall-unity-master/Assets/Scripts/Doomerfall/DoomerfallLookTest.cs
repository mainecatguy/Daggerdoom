// Doomerfall test only (-dflooktest): once the player is inside a building (Doom lists piles only indoors), drops a Daggerfall loot pile holding one Iron
// Longsword where the hidden player stands, so tools/look_label can check the label under Doom's crosshair for a pile.
// The pile is an ordinary dropped pile (GameObjectHelper.CreateDroppedLootContainer), the same as a player's drop.

using System;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallLookTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        float readyAt = -1;
        bool dropped;

        internal static void Apply(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dflooktest") < 0)
                return;
            DoomerfallLookTest test = owner.gameObject.AddComponent<DoomerfallLookTest>();
            test.bridge = owner;
            test.sync = positionSync;
        }

        void Update()
        {
            if (dropped || !sync.InGame || !GameManager.HasInstance || !GameManager.Instance.PlayerEnterExit.IsPlayerInside)
                return;
            if (readyAt < 0)
                readyAt = Time.unscaledTime + 4f; // Position sync has moved the hidden player to Doom's place in the room by then.
            if (Time.unscaledTime < readyAt)
                return;
            dropped = true;
            DaggerfallLoot pile = GameObjectHelper.CreateDroppedLootContainer(GameManager.Instance.PlayerObject, DaggerfallUnity.NextUID);
            pile.Items.AddItem(ItemBuilder.CreateWeapon(Weapons.Longsword, WeaponMaterialTypes.Iron));
            bridge.LogLine(string.Format("looktest: dropped a pile with [{0}] at {1}", pile.Items.GetItem(0).LongName, pile.transform.position));
        }
    }
}
