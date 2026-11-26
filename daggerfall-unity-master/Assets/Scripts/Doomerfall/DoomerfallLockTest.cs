// Test only (tools/lockpick/paired): -dflocktest. Once the player is inside a dungeon, holds back every lockpick so the
// first Use on a locked door is refused, then returns them 20 seconds later for the minigame cases (3 new picks if the
// character had none). Logs each change.
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
        int phase, held;
        float giveAt;

        internal static void Attach(DoomerfallBridge owner)
        {
            string[] args = Environment.GetCommandLineArgs();
            if (Array.IndexOf(args, "-dflocktest") >= 0 || Array.IndexOf(args, "-dflocktestmagic") >= 0)
            {
                var test = owner.gameObject.AddComponent<DoomerfallLockTest>();
                test.bridge = owner;
                test.magic = Array.IndexOf(args, "-dflocktestmagic") >= 0;
            }
        }

        // -dflocktestmagic (the load run): 15 s inside the dungeon, door 29539363 becomes magically held (lock 25).
        const ulong MagicDoor = 29539363;
        bool magic;
        float magicAt;

        void UpdateMagic()
        {
            if (phase > 1 || !GameManager.HasInstance || !GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon)
                return;
            if (phase == 0)
            {
                magicAt = Time.unscaledTime + 15f;
                phase = 1;
                return;
            }
            if (Time.unscaledTime < magicAt)
                return;
            DaggerfallActionDoor door = DoomerfallLocks.Find(MagicDoor);
            if (!door)
                return;
            door.CurrentLockValue = 25;
            phase = 2;
            bridge.LogLine("locktest: door " + MagicDoor + " is now magically held, picks " + DoomerfallLockpick.Count(GameManager.Instance.PlayerEntity.Items));
        }

        void Update()
        {
            if (magic)
            {
                UpdateMagic();
                return;
            }
            if (phase > 1 || !GameManager.HasInstance || !GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (phase == 0)
            {
                while (DoomerfallLockpick.BreakOne(player.Items))
                    held++;
                giveAt = Time.unscaledTime + GiveAfter;
                phase = 1;
                bridge.LogLine("locktest: held back " + held + " lockpicks, picks 0");
            }
            else if (Time.unscaledTime >= giveAt)
            {
                player.Items.AddItem(new DoomerfallLockpickItem(held > 0 ? held : 3)); // the character's own picks; 3 if it had none
                phase = 2;
                bridge.LogLine("locktest: returned " + (held > 0 ? "the held" : "3 new") + " lockpicks, picks " + DoomerfallLockpick.Count(player.Items));
            }
        }
    }
}
