// Doomerfall: Daggerfall owns time and weather, and Doom draws them. This sends what Daggerfall's own hidden sky,
// light and weather objects show, so Doom ports none of their curves or tables (UZDoom/src/playsim/dd_weather.cpp):
//   "sky <index> <frame> <stars> <night> <ambient> <weather> <loop> <sun> <elevation>"
//     index, frame   DaggerfallSky.SkyIndex and SkyFrame (0-63; 32 and up is the mirrored afternoon)
//     stars          1 when DaggerfallSky shows the starry night sky (night and normal weather)
//     night          WorldTime.Now.IsNight
//     ambient        PlayerAmbientLight's exterior ambient (CalcDaytimeAmbientLight), 0-255
//     weather        PlayerWeather.WeatherType
//     loop           the clip AmbientEffectsPlayer loops: rain, crickets, or 0
//     sun            SunlightManager's sun light intensity x 100 (0 at night); exterior daylight is ambient plus sun
//     elevation      the sun light's height above the horizon in whole degrees (negative below); flat ground gets
//                    the sun's light times the sine of it
//     winter         1 in Daggerfall's winter season; Doom then converts places with the winter texture sets (the
//                    converter applies ClimateSwaps' winter rules, so climates without snow stay as they are)
//   "fog <on> <mode> <density> <start> <end> <r> <g> <b> <sky>"
//     Unity's RenderSettings fog (mode 1 linear, 2 exponential, 3 exponential squared; distances in metres) and
//     1 when the outdoor fog also covers the sky (WeatherManager's excludeSkybox off: heavy fog)
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
        string sent, logged, sentFog;
        float nextSend, nextFogSend;

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
            int elevation = sunLight ? Mathf.RoundToInt(Mathf.Asin(Mathf.Clamp(-sunLight.transform.forward.y, -1f, 1f)) * Mathf.Rad2Deg) : 0;
            int loop = 0;
            if (weather.WeatherEffects)
            {
                var presets = weather.WeatherEffects.Presets;
                if (presets == AmbientEffectsPlayer.AmbientSoundPresets.Rain || presets == AmbientEffectsPlayer.AmbientSoundPresets.Storm)
                    loop = (int)SoundClips.AmbientRaining;
                else if (presets == AmbientEffectsPlayer.AmbientSoundPresets.ClearNight)
                    loop = (int)SoundClips.AmbientCrickets;
            }
            bool winter = dfUnity.WorldTime.Now.SeasonValue == DaggerfallWorkshop.Utility.DaggerfallDateTime.Seasons.Winter;
            string line = string.Format("sky {0} {1} {2} {3} {4} {5} {6} {7} {8} {9}", sky.SkyIndex, sky.SkyFrame, stars ? 1 : 0, night ? 1 : 0,
                ambient, (int)weather.PlayerWeather.WeatherType, loop, sunPercent, elevation, winter ? 1 : 0);
            SendFog(weather);
            if (line == sent && Time.unscaledTime < nextSend) return;
            string key = sky.SkyIndex + " " + stars + " " + weather.PlayerWeather.WeatherType + " " + loop;
            if (key != logged) bridge.LogLine("world look " + line + " at " + dfUnity.WorldTime.Now.MinuteOfDay / 60 + "h");
            logged = key;
            sent = line;
            nextSend = Time.unscaledTime + ResendSeconds;
            bridge.SendText(line);
        }

        // The fog Unity draws now, as WeatherManager.SetFog and DaggerfallSky left it: clear-weather linear fog,
        // weather, interior and dungeon fog, and whether the sky is fogged too (heavy fog).
        void SendFog(WeatherManager weather)
        {
            Color c = RenderSettings.fogColor;
            string line = string.Format(System.Globalization.CultureInfo.InvariantCulture, "fog {0} {1} {2:0.######} {3:0.#} {4:0.#} {5} {6} {7} {8}",
                RenderSettings.fog ? 1 : 0, (int)RenderSettings.fogMode, RenderSettings.fogDensity, RenderSettings.fogStartDistance,
                RenderSettings.fogEndDistance, Mathf.RoundToInt(c.r * 255), Mathf.RoundToInt(c.g * 255), Mathf.RoundToInt(c.b * 255),
                weather.currentOutdoorFogSettings.excludeSkybox ? 0 : 1);
            if (line == sentFog && Time.unscaledTime < nextFogSend) return;
            if (line != sentFog) bridge.LogLine("world look " + line);
            sentFog = line;
            nextFogSend = Time.unscaledTime + ResendSeconds;
            bridge.SendText(line);
        }
    }
}
