// Test only (tools/lockpick/paired): -dflocktest. Once the player is inside a dungeon, takes every lockpick so the
// first Use on a locked door is refused, then gives 3 picks 20 seconds later for the minigame cases. Logs each change.
// Does nothing without the flag. The load run of the test does not pass the flag.

using System;
using DaggerfallWorkshop.Game.Entity;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallLockTest : MonoBehaviour
    {
        const float GiveAfter = 20f;

        DoomerfallBridge bridge;
        int phase;
        float giveAt;

        internal static void Attach(DoomerfallBridge owner)
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dflocktest") >= 0)
                owner.gameObject.AddComponent<DoomerfallLockTest>().bridge = owner;
        }

        void Update()
        {
            if (phase > 1 || !GameManager.HasInstance || !GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (phase == 0)
            {
                while (DoomerfallLockpick.BreakOne(player.Items)) { }
                giveAt = Time.unscaledTime + GiveAfter;
                phase = 1;
                bridge.LogLine("locktest: took every lockpick, picks 0");
            }
            else if (Time.unscaledTime >= giveAt)
            {
                player.Items.AddItem(new DoomerfallLockpickItem(3));
                phase = 2;
                bridge.LogLine("locktest: gave 3 lockpicks, picks " + DoomerfallLockpick.Count(player.Items));
            }
        }
    }
}
