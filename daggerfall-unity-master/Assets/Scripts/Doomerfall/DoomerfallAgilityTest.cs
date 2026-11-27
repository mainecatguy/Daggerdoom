// Doomerfall test only (-dfagilitytest [seconds], with -dfsynctest or -dfflow): once in game, cycles the character's
// Agility through low, high and middle values through Daggerfall's own stats, holding each for a few seconds, so a
// paired launch can see Doom's reload and weapon switch speed and evasion follow it (tools/agility/agility_paired.py).

using System;
using System.Collections;
using DaggerfallConnect;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallAgilityTest : MonoBehaviour
    {
        static readonly int[] Values = { 1, 100, 50, 10 }; // not 0: Daggerfall kills a character with an attribute at 0

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        float HoldSeconds = 6f; // "-dfagilitytest <seconds>" holds each value longer, for a person to try it.

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfagilitytest");
            if (at < 0)
                return;
            var test = owner.gameObject.AddComponent<DoomerfallAgilityTest>();
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
                    stats.SetPermanentStatValue(DFCareer.Stats.Agility, v);
                    bridge.LogLine(string.Format("agility test: agility {0} (live {1})", v, stats.LiveAgility));
                    yield return new WaitForSecondsRealtime(HoldSeconds);
                }
            }
            bridge.LogLine("agility test: done");
        }
    }
}
