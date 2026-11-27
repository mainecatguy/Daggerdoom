// Doomerfall test only (-dflucktest <value>, with -dfsynctest or -dfflow): as soon as a game is running, sets the
// character's Luck to <value> (1-100) through Daggerfall's own stats, so a paired launch can see Doom's monster ammo
// drops follow it (tools/luck/luck_paired.py).

using System;
using System.Collections;
using DaggerfallConnect;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallLuckTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        int value;

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dflucktest");
            int v;
            if (at < 0 || at + 1 >= args.Length || !int.TryParse(args[at + 1], out v))
                return;
            var test = owner.gameObject.AddComponent<DoomerfallLuckTest>();
            test.bridge = owner;
            test.sync = positionSync;
            test.value = Mathf.Clamp(v, 1, 100); // not 0: Daggerfall kills a character with an attribute at 0
            test.StartCoroutine(test.Run());
        }

        IEnumerator Run()
        {
            while (!sync.InGame)
                yield return null;
            var stats = GameManager.Instance.PlayerEntity.Stats;
            stats.SetPermanentStatValue(DFCareer.Stats.Luck, value);
            bridge.LogLine(string.Format("luck test: luck {0} (live {1})", value, stats.LiveLuck));
        }
    }
}
