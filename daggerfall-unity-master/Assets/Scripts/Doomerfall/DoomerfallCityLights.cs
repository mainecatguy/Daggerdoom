// Doomerfall: town lamps follow Daggerfall's clock. Daggerfall Unity turns city lights on and off with
// WorldTime.Now.IsCityLightsOn (DaggerfallLight). Doom draws the lamps, so this tells Doom with the bridge text
// "citylights 1" or "citylights 0" when the flag changes, and again every few seconds in case Doom restarted its map.

using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public class DoomerfallCityLights : MonoBehaviour
    {
        const float ResendSeconds = 5f;

        DoomerfallBridge bridge;
        int sent = -1;
        string sentWindows;
        float nextSend;

        public void Init(DoomerfallBridge owner) { bridge = owner; }

        void Update()
        {
            DaggerfallUnity dfUnity = DaggerfallUnity.Instance;
            if (bridge == null || dfUnity == null || !dfUnity.IsReady || dfUnity.WorldTime == null) return;
            int on = dfUnity.WorldTime.Now.IsCityLightsOn ? 1 : 0;
            string windows = WindowLine(dfUnity, on != 0);
            if (on == sent && windows == sentWindows && Time.unscaledTime < nextSend) return;
            if (on != sent) bridge.LogLine("city lights " + (on != 0 ? "on" : "off") + " at " + dfUnity.WorldTime.Now.MinuteOfDay / 60 + "h");
            if (windows != sentWindows) bridge.LogLine(windows);
            sent = on;
            sentWindows = windows;
            nextSend = Time.unscaledTime + ResendSeconds;
            bridge.SendText("citylights " + on);
            bridge.SendText(windows);
        }

        // Window glow: the emission colour MaterialReader gives window materials for the style DaggerfallLocation
        // picks (Night while city lights are on, otherwise Day; Day only without automated texture swaps), and
        // DaggerfallInterior's Disabled style inside buildings and dungeons. Sent as "windows <r> <g> <b>", 0 to 255.
        static string WindowLine(DaggerfallUnity dfUnity, bool lightsOn)
        {
            MaterialReader reader = dfUnity.MaterialReader;
            PlayerEnterExit enterExit = GameManager.HasInstance ? GameManager.Instance.PlayerEnterExit : null;
            Color c = Color.black;
            if (reader != null && (enterExit == null || !enterExit.IsPlayerInside))
                c = lightsOn && dfUnity.Option_AutomateTextureSwaps
                    ? reader.NightWindowColor * reader.NightWindowIntensity
                    : reader.DayWindowColor * reader.DayWindowIntensity;
            return string.Format(System.Globalization.CultureInfo.InvariantCulture, "windows {0:F0} {1:F0} {2:F0}",
                Mathf.Clamp01(c.r) * 255f, Mathf.Clamp01(c.g) * 255f, Mathf.Clamp01(c.b) * 255f);
        }
    }
}
