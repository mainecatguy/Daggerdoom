// Doomerfall test only (-dfwillpowertest [seconds], with -dfsynctest or -dfflow): once in game, sets the character's
// Willpower to low, high and middle values through Daggerfall's own stats, holding each for a while, so a paired
// launch can see the damage Doom deals the player follow it (tools/willpower/willpower_paired.py).

using System;
using System.Collections;
using DaggerfallConnect;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallWillpowerTest : MonoBehaviour
    {
        static readonly int[] Values = { 1, 100, 50, 75 }; // not 0: Daggerfall kills a character with an attribute at 0

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        float HoldSeconds = 20f; // "-dfwillpowertest <seconds>" holds each value longer, for a person to try it.

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfwillpowertest");
            if (at < 0)
                return;
            var test = owner.gameObject.AddComponent<DoomerfallWillpowerTest>();
            test.bridge = owner;
            test.sync = positionSync;
            float seconds;
            if (at + 1 < args.Length && float.TryParse(args[at + 1], System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out seconds) && seconds > 0)
                test.HoldSeconds = seconds;
            test.StartCoroutine(test.Run());
        }

        IEnumerator Run()
        {
            while (!sync.InGame)
                yield return null;
            yield return new WaitForSecondsRealtime(3f);
            var stats = GameManager.Instance.PlayerEntity.Stats;
            foreach (int v in Values)
            {
                stats.SetPermanentStatValue(DFCareer.Stats.Willpower, v);
                bridge.LogLine(string.Format("willpower test: willpower {0} (live {1})", v, stats.LiveWillpower));
                yield return new WaitForSecondsRealtime(HoldSeconds);
            }
            bridge.LogLine("willpower test: done");
        }
    }
}
