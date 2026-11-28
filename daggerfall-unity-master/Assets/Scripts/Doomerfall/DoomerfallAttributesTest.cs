// Doomerfall test only (-dfattrtest [seconds], with -dfsynctest or -dfflow): once in game, cycles the character's Strength and Speed through
// low, high and middle values through Daggerfall's own stats, holding each for a few seconds, so a paired launch can
// see Doom's melee damage and movement speed follow them (tools/attributes/attributes_paired.py). Agility and Luck are
// held at 50 meanwhile (no Agility gun bonus, no Luck crits), so the hits that test compares are unchanged by them.
// "-dfattrtest <seconds> rework" instead sets Strength, Agility and Luck to each triple of Rework in turn, once
// (tools/attributes/attributes_rework_paired.py). 1 is the lowest: Daggerfall kills a character whose live attribute
// is 0.

using System;
using System.Collections;
using DaggerfallConnect;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallAttributesTest : MonoBehaviour
    {
        static readonly int[] Values = { 0, 100, 50, 10 };
        static readonly int[,] Rework = { { 50, 50, 50 }, { 1, 50, 50 }, { 100, 50, 50 }, { 50, 1, 50 }, { 50, 100, 50 },
            { 1, 1, 50 }, { 100, 100, 50 }, { 50, 50, 100 } };

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        float HoldSeconds = 6f; // "-dfattrtest <seconds>" holds each value longer, for a person to try it.
        bool rework;

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
            test.rework = Array.IndexOf(args, "rework") > at;
            test.StartCoroutine(test.Run());
        }

        IEnumerator Run()
        {
            while (!sync.InGame)
                yield return null;
            yield return new WaitForSecondsRealtime(HoldSeconds);
            var stats = GameManager.Instance.PlayerEntity.Stats;
            if (rework)
            {
                for (int i = 0; i < Rework.GetLength(0); i++)
                {
                    stats.SetPermanentStatValue(DFCareer.Stats.Strength, Rework[i, 0]);
                    stats.SetPermanentStatValue(DFCareer.Stats.Agility, Rework[i, 1]);
                    stats.SetPermanentStatValue(DFCareer.Stats.Luck, Rework[i, 2]);
                    bridge.LogLine(string.Format("attr test: strength {0} agility {1} luck {2} (live {3} {4} {5})", Rework[i, 0],
                        Rework[i, 1], Rework[i, 2], stats.LiveStrength, stats.LiveAgility, stats.LiveLuck));
                    yield return new WaitForSecondsRealtime(HoldSeconds);
                }
                bridge.LogLine("attr test: done");
                yield break;
            }
            stats.SetPermanentStatValue(DFCareer.Stats.Agility, 50);
            stats.SetPermanentStatValue(DFCareer.Stats.Luck, 50);
            for (int round = 0; round < 2; round++)
            {
                foreach (int v in Values)
                {
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
