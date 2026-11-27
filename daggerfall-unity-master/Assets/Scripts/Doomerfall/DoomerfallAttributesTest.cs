// Doomerfall test only (-dfattrtest [seconds], with -dfsynctest or -dfflow): once in game, cycles the character's Strength and Speed through
// low, high and middle values through Daggerfall's own stats, holding each for a few seconds, so a paired launch can
// see Doom's melee damage and movement speed follow them (tools/attributes/attributes_paired.py).

using System;
using System.Collections;
using DaggerfallConnect;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallAttributesTest : MonoBehaviour
    {
        static readonly int[] Values = { 0, 100, 50, 10 };

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        float HoldSeconds = 6f; // "-dfattrtest <seconds>" holds each value longer, for a person to try it.

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfattrtest");
            if (at < 0)
                return;
            var test = owner.gameObject.AddComponent<DoomerfallAttributesTest>();
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
            yield return new WaitForSecondsRealtime(HoldSeconds);
            for (int round = 0; round < 2; round++)
            {
                foreach (int v in Values)
                {
                    var stats = GameManager.Instance.PlayerEntity.Stats;
                    stats.SetPermanentStatValue(DFCareer.Stats.Strength, v);
                    stats.SetPermanentStatValue(DFCareer.Stats.Speed, v);
                    bridge.LogLine(string.Format("attr test: strength {0} speed {1} (live {2} {3})", v, v,
                        stats.LiveStrength, stats.LiveSpeed));
                    yield return new WaitForSecondsRealtime(HoldSeconds);
                }
            }
            bridge.LogLine("attr test: done");
        }
    }
}
