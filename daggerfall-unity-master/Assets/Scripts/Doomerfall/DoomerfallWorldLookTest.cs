// Doomerfall test only (-dfworldlooktest "<hour>:<weather> ..." [seconds]): once in game, sets Daggerfall's clock and
// weather to each step in turn, holding each for the given seconds (default 8), so one paired run shows Doom drawing
// several hours and weathers. Weather numbers are WeatherType: 0 sunny, 2 overcast, 3 fog, 4 rain, 5 thunder, 6 snow.

using System;
using DaggerfallWorkshop.Game.Weather;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallWorldLookTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        string[] steps;
        float hold = 8, nextAt = -1;
        int step;

        internal static void Apply(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfworldlooktest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            DoomerfallWorldLookTest test = owner.gameObject.AddComponent<DoomerfallWorldLookTest>();
            test.bridge = owner;
            test.sync = positionSync;
            test.steps = args[at + 1].Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            float seconds;
            if (at + 2 < args.Length && float.TryParse(args[at + 2], out seconds))
                test.hold = seconds;
        }

        void Update()
        {
            if (step >= steps.Length || !sync.InGame || !GameManager.HasInstance)
                return;
            if (nextAt < 0)
                nextAt = Time.unscaledTime + 3f;
            if (Time.unscaledTime < nextAt)
                return;
            nextAt = Time.unscaledTime + hold;
            string[] parts = steps[step++].Split(':');
            DaggerfallDateTime now = DaggerfallUnity.Instance.WorldTime.Now;
            now.Hour = int.Parse(parts[0]);
            now.Minute = 0;
            if (parts.Length > 1)
                GameManager.Instance.WeatherManager.SetWeather((WeatherType)int.Parse(parts[1]));
            bridge.LogLine(string.Format("worldlooktest: step {0} hour {1} weather {2}", step, now.Hour, GameManager.Instance.WeatherManager.PlayerWeather.WeatherType));
        }
    }
}
