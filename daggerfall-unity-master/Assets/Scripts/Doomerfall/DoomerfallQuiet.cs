// Doomerfall: test-only quiet. With -dfmute, Daggerfall Unity makes no sound for the whole run, with or
// without a bridge session, and never locks the mouse cursor. Without the flag this does nothing.
//
// Why the cursor: a locked Unity cursor is a ClipCursor to one point at the window's centre, and Windows applies
// that to the user's real pointer even when the game runs on a private desktop, where its window counts as focused.
// Doom, not Daggerfall, reads the mouse in Doomerfall, so tests lose nothing.
using System;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    [DefaultExecutionOrder(-10000)] // before PlayerMouseLook.Update, so it never locks for even one frame
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
            var quiet = host.AddComponent<DoomerfallQuiet>();
            // The player's mouse look arrives with a scene: search on the first frame after each load.
            UnityEngine.SceneManagement.SceneManager.sceneLoaded += (scene, mode) => quiet.nextLookSearch = 0;
        }

        PlayerMouseLook look;
        float nextLookSearch;

        void Update()
        {
            // GameManager.PlayerMouseLook throws while there is no camera, so look it up quietly, at most once a second.
            if (look == null && Time.unscaledTime >= nextLookSearch)
            {
                look = FindObjectOfType<PlayerMouseLook>();
                nextLookSearch = Time.unscaledTime + 1f;
            }
            if (look != null && look.lockCursor)
                look.lockCursor = false;
            if (Cursor.lockState != CursorLockMode.None)
                Cursor.lockState = CursorLockMode.None;
        }

        // Catches any other code that raises the volume or locks the cursor.
        void LateUpdate()
        {
            if (AudioListener.volume != 0)
                AudioListener.volume = 0;
            if (Cursor.lockState != CursorLockMode.None)
                Cursor.lockState = CursorLockMode.None;
        }
    }
}
