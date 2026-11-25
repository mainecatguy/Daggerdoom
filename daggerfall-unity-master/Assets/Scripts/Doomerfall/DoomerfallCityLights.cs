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
        float nextSend;

        public void Init(DoomerfallBridge owner) { bridge = owner; }

        void Update()
        {
            DaggerfallUnity dfUnity = DaggerfallUnity.Instance;
            if (bridge == null || dfUnity == null || !dfUnity.IsReady || dfUnity.WorldTime == null) return;
            int on = dfUnity.WorldTime.Now.IsCityLightsOn ? 1 : 0;
            if (on == sent && Time.unscaledTime < nextSend) return;
            if (on != sent) bridge.LogLine("city lights " + (on != 0 ? "on" : "off") + " at " + dfUnity.WorldTime.Now.MinuteOfDay / 60 + "h");
            sent = on;
            nextSend = Time.unscaledTime + ResendSeconds;
            bridge.SendText("citylights " + on);
        }
    }
}
