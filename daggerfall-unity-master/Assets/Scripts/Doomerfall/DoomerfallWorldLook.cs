// Doomerfall: Daggerfall owns time and weather, and Doom draws them. This sends what Daggerfall's own hidden sky,
// light and weather objects show, so Doom ports none of their curves or tables (UZDoom/src/playsim/dd_weather.cpp):
//   "sky <index> <frame> <stars> <night> <ambient> <weather> <loop> <sun>"
//     index, frame   DaggerfallSky.SkyIndex and SkyFrame (0-63; 32 and up is the mirrored afternoon)
//     stars          1 when DaggerfallSky shows the starry night sky (night and normal weather)
//     night          WorldTime.Now.IsNight
//     ambient        PlayerAmbientLight's exterior ambient (CalcDaytimeAmbientLight), 0-255
//     weather        PlayerWeather.WeatherType
//     loop           the clip AmbientEffectsPlayer loops: rain, crickets, or 0
//     sun            SunlightManager's sun light intensity x 100 (0 at night); exterior daylight is ambient plus sun
// on change and every few seconds, and "amb <clip>" for each ambient one-shot AmbientEffectsPlayer plays.

using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public class DoomerfallWorldLook : MonoBehaviour
    {
        const float ResendSeconds = 5f;

        DoomerfallBridge bridge;
        DaggerfallSky sky;
        PlayerAmbientLight ambientLight;
        string sent, logged;
        float nextSend;

        public void Init(DoomerfallBridge owner)
        {
            bridge = owner;
            AmbientEffectsPlayer.OnDoomerfallSound += OneShot;
        }

        void OnDestroy() { AmbientEffectsPlayer.OnDoomerfallSound -= OneShot; }

        void OneShot(SoundClips clip)
        {
            if (bridge != null) bridge.SendText("amb " + (int)clip);
        }

        void Update()
        {
            DaggerfallUnity dfUnity = DaggerfallUnity.Instance;
            GameManager game = GameManager.Instance;
            if (bridge == null || dfUnity == null || !dfUnity.IsReady || dfUnity.WorldTime == null || game == null) return;
            WeatherManager weather = game.WeatherManager;
            SunlightManager sun = game.SunlightManager;
            if (!sky) sky = weather ? weather.DaggerfallSky : null;
            if (!ambientLight && game.PlayerObject) ambientLight = game.PlayerObject.GetComponent<PlayerAmbientLight>();
            if (!sky || !sun || !ambientLight || !weather || !weather.PlayerWeather) return;

            bool night = dfUnity.WorldTime.Now.IsNight;
            bool stars = sky.IsNight && sky.WeatherStyle == WeatherStyle.Normal;
            Color c = Color.Lerp(ambientLight.ExteriorNightAmbientLight * DaggerfallUnity.Settings.NightAmbientLightScale,
                ambientLight.ExteriorNoonAmbientLight, sun.DaylightScale * sun.ScaleFactor);
            int ambient = Mathf.Clamp(Mathf.RoundToInt(c.r * 255), 0, 255);
            Light sunLight = sun.GetComponent<Light>();
            int sunPercent = sunLight && sunLight.enabled ? Mathf.Clamp(Mathf.RoundToInt(sunLight.intensity * 100), 0, 999) : 0;
            int loop = 0;
            if (weather.WeatherEffects)
            {
                var presets = weather.WeatherEffects.Presets;
                if (presets == AmbientEffectsPlayer.AmbientSoundPresets.Rain || presets == AmbientEffectsPlayer.AmbientSoundPresets.Storm)
                    loop = (int)SoundClips.AmbientRaining;
                else if (presets == AmbientEffectsPlayer.AmbientSoundPresets.ClearNight)
                    loop = (int)SoundClips.AmbientCrickets;
            }
            string line = string.Format("sky {0} {1} {2} {3} {4} {5} {6} {7}", sky.SkyIndex, sky.SkyFrame, stars ? 1 : 0, night ? 1 : 0,
                ambient, (int)weather.PlayerWeather.WeatherType, loop, sunPercent);
            if (line == sent && Time.unscaledTime < nextSend) return;
            string key = sky.SkyIndex + " " + stars + " " + weather.PlayerWeather.WeatherType + " " + loop;
            if (key != logged) bridge.LogLine("world look " + line + " at " + dfUnity.WorldTime.Now.MinuteOfDay / 60 + "h");
            logged = key;
            sent = line;
            nextSend = Time.unscaledTime + ResendSeconds;
            bridge.SendText(line);
        }
    }
}
