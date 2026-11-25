// Doomerfall: in a bridge session Daggerfall Unity's window is only a render host for the UI that Doom shows, so it
// stays a plain window at the size the command line asks for, and never locks the mouse cursor.
//
// Why: Daggerfall's settings.ini defaults to Fullscreen=True at 1920x1080, and SceneControl and StartGameBehaviour
// apply those settings at start, overriding -screen-fullscreen 0. A fresh play folder therefore came up fullscreen.
// Doom reads all input in Doomerfall, so Daggerfall never needs the cursor. A locked cursor is a ClipCursor that
// Windows applies to the user's real pointer even when Daggerfall runs on a private desktop, as the launcher puts it.
// The settings change is in memory only, so a later save of settings.ini would only keep it in the private copy.
using System;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    [DefaultExecutionOrder(-10000)] // before PlayerMouseLook.Update, so the cursor never locks for even one frame
    public sealed class DoomerfallWindow : MonoBehaviour
    {
        const int DefaultWidth = 1280, DefaultHeight = 800;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void StartInSession()
        {
            string[] args = Environment.GetCommandLineArgs();
            if (Array.IndexOf(args, "-dfbridge") < 0)
                return;

            var settings = DaggerfallUnity.Settings;
            settings.Fullscreen = false;
            settings.ExclusiveFullscreen = false;
            settings.ResolutionWidth = Size(args, "-screen-width", DefaultWidth);
            settings.ResolutionHeight = Size(args, "-screen-height", DefaultHeight);
            Screen.SetResolution(settings.ResolutionWidth, settings.ResolutionHeight, FullScreenMode.Windowed);

            var host = new GameObject("DoomerfallWindow");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallWindow>();
        }

        static int Size(string[] args, string name, int fallback)
        {
            int at = Array.IndexOf(args, name), value;
            return at >= 0 && at + 1 < args.Length && int.TryParse(args[at + 1], out value) && value > 0 ? value : fallback;
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

        void LateUpdate()
        {
            if (Cursor.lockState != CursorLockMode.None)
                Cursor.lockState = CursorLockMode.None;
        }
    }
}
