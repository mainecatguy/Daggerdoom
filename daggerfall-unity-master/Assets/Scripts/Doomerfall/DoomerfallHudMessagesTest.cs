// Test only (tools/hud_messages): -dfhudtest <folder> [-dfhudtestsize WxH]. Ten seconds into play, shows a sample of
// Daggerfall's own HUD messages through Daggerfall's own calls (DaggerfallUI.AddHUDText with Daggerfall's hold times,
// PopupMessage, SetMidScreenText), so Daggerfall Unity draws them while DoomerfallHudMessages sends them to Doom.
// Daggerfall's window draws only black in a paired run, so for the side-by-side frames its interface is drawn into a
// render texture of Doom's screen size (as DoomerfallUi does for menus) and saved every quarter second for five
// seconds from the first message (df-NNN.png). Logs what it showed. Does nothing without the flag.

using System;
using System.Collections;
using System.IO;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Localization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHudMessagesTest : MonoBehaviour
    {
        const float After = 10f, Step = 0.25f;
        const int Shots = 21;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        string folder;
        int width, height;
        float playSince = -1;
        bool started;

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfhudtest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            var test = owner.gameObject.AddComponent<DoomerfallHudMessagesTest>();
            test.bridge = owner;
            test.sync = positionSync;
            test.folder = args[at + 1];
            int size = Array.IndexOf(args, "-dfhudtestsize");
            string[] wh = size >= 0 && size + 1 < args.Length ? args[size + 1].Split('x') : new string[0];
            if (wh.Length != 2 || !int.TryParse(wh[0], out test.width) || !int.TryParse(wh[1], out test.height))
            {
                test.width = Screen.width;
                test.height = Screen.height;
            }
        }

        void Update()
        {
            if (started)
                return;
            bool playing = sync.InGame && !sync.LoadRunning && sync.Phase == Dfb.DF_PHASE_PLAY && DaggerfallUI.UIManager.TopWindow is DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallHUD;
            if (!playing)
            {
                playSince = -1;
                return;
            }
            if (playSince < 0)
                playSince = Time.unscaledTime;
            if (Time.unscaledTime - playSince >= After)
            {
                started = true;
                StartCoroutine(Run());
            }
        }

        IEnumerator Run()
        {
            Directory.CreateDirectory(folder);
            var target = new GameObject("DoomerfallHudTestTarget").AddComponent<UserInterfaceRenderTarget>();
            target.transform.SetParent(DaggerfallUI.Instance.transform, false);
            target.CustomWidth = width;
            target.CustomHeight = height;
            DaggerfallUI.Instance.CustomRenderTarget = target;
            yield return null;
            yield return null;

            TextManager text = TextManager.Instance;
            string place = GameManager.Instance.PlayerGPS.CurrentLocation.Loaded ? GameManager.Instance.PlayerGPS.CurrentLocation.Name : "Daggerfall";
            DaggerfallUI.AddHUDText(text.GetLocalizedText("youAreEntering").Replace("%s", place), 2);  // as PlayerEnterExit
            DaggerfallUI.AddHUDText(text.GetLocalizedText("youFeelSomewhatBad"), 2.5f);               // as DiseaseEffect
            DaggerfallUI.AddHUDText(text.GetLocalizedText("trapNoneEmpty"));                           // as SoulTrap
            DaggerfallUI.Instance.PopupMessage(text.GetLocalizedText("youSeeA").Replace("%s", "Imp")); // as Info on a monster
            DaggerfallUI.SetMidScreenText(text.GetLocalizedText("youHaveNoArrows"));                  // as the bow
            float sentAt = Time.unscaledTime;
            bridge.LogLine(string.Format("hudtest: sample sent at {0:F2}, Daggerfall drawn at {1}x{2}", sentAt, width, height));

            var image = new Texture2D(width, height, TextureFormat.RGB24, false);
            for (int shot = 0; shot < Shots; shot++)
            {
                while (Time.unscaledTime - sentAt < shot * Step)
                    yield return null;
                yield return new WaitForEndOfFrame();
                RenderTexture old = RenderTexture.active;
                RenderTexture.active = target.TargetTexture;
                image.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                RenderTexture.active = old;
                File.WriteAllBytes(Path.Combine(folder, string.Format("df-{0:D3}.png", shot)), image.EncodeToPNG());
            }
            if (DaggerfallUI.Instance.CustomRenderTarget == target)
                DaggerfallUI.Instance.CustomRenderTarget = null;
            Destroy(target.gameObject);
            bridge.LogLine("hudtest: " + Shots + " Daggerfall frames saved");
        }
    }
}
