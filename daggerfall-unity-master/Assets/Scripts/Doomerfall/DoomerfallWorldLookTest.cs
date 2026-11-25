// Doomerfall test only (-dfworldlooktest "<hour>:<weather> ..." [seconds]): once in game, sets Daggerfall's clock and
// weather (and, with a third field, month 0-11) to each step in turn, holding each for the given seconds (default 8), so one paired run shows Doom drawing
// several hours and weathers. Weather numbers are WeatherType: 0 sunny, 2 overcast, 3 fog, 4 rain, 5 thunder, 6 snow.
// With -dfworldlookshots <dir> (and the launcher without --nodraw) it also saves what Daggerfall's own camera shows
// at the end of each step, as step<N>.png, for comparing brightness with Doom's screenshot of the same moment.

using System;
using System.IO;
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
        string shots;
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
            int dir = Array.IndexOf(args, "-dfworldlookshots");
            if (dir >= 0 && dir + 1 < args.Length)
                test.shots = args[dir + 1];
        }

        void Update()
        {
            if (step > steps.Length || !sync.InGame || !GameManager.HasInstance)
                return;
            if (nextAt < 0)
                nextAt = Time.unscaledTime + 3f;
            if (Time.unscaledTime < nextAt)
                return;
            nextAt = Time.unscaledTime + hold;
            if (step > 0 && shots != null)
                Shot(step);
            if (step == steps.Length)
            {
                step++;
                return;
            }
            string[] parts = steps[step++].Split(':');
            DaggerfallDateTime now = DaggerfallUnity.Instance.WorldTime.Now;
            now.Hour = int.Parse(parts[0]);
            now.Minute = 0;
            if (parts.Length > 2)
                now.Month = int.Parse(parts[2]); // Daggerfall swaps its terrain and town textures for the season live.
            if (parts.Length > 1)
                GameManager.Instance.WeatherManager.SetWeather((WeatherType)int.Parse(parts[1]));
            bridge.LogLine(string.Format("worldlooktest: step {0} hour {1} weather {2} season {3}", step, now.Hour, GameManager.Instance.WeatherManager.PlayerWeather.WeatherType, now.SeasonValue));
        }

        // Renders the main camera (works while minimized), as DoomerfallSyncTest does.
        void Shot(int number)
        {
            const int width = 640, height = 360;
            Camera main = GameManager.Instance.MainCamera;
            RenderTexture target = RenderTexture.GetTemporary(width, height, 24);
            RenderTexture previousTarget = main.targetTexture, previousActive = RenderTexture.active;
            main.targetTexture = target;
            main.Render();
            main.targetTexture = previousTarget;
            RenderTexture.active = target;
            var image = new Texture2D(width, height, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            RenderTexture.active = previousActive;
            RenderTexture.ReleaseTemporary(target);
            Directory.CreateDirectory(shots);
            File.WriteAllBytes(Path.Combine(shots, "step" + number + ".png"), image.EncodeToPNG());
            Destroy(image);
            bridge.LogLine(string.Format("worldlooktest: shot step {0} pitch {1:F1}", number, main.transform.eulerAngles.x));
        }
    }
}
