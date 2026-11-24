// Doomerfall: test-only silence. With -dfmute, Daggerfall Unity makes no sound for the whole run, with or
// without a bridge session. Without the flag this does nothing.
using System;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public class DoomerfallQuiet : MonoBehaviour
    {
        /// <summary>True when the command line asked for silence.</summary>
        public static bool Muted { get; private set; }

        /// <summary>The listener volume to use: the requested one, or 0 when muted.</summary>
        public static float Volume(float requested) { return Muted ? 0f : requested; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void StartIfRequested()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfmute") < 0)
                return;
            Muted = true;
            AudioListener.volume = 0;
            var host = new GameObject("DoomerfallQuiet");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallQuiet>();
        }

        // Catches any other code that raises the volume.
        void LateUpdate()
        {
            if (AudioListener.volume != 0)
                AudioListener.volume = 0;
        }
    }
}
