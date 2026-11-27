// Test only (tools/hud_messages): -dfhudtest <folder>. Ten seconds into play, shows a sample of Daggerfall's own HUD
// messages through Daggerfall's own calls (DaggerfallUI.AddHUDText with Daggerfall's hold times, PopupMessage,
// SetMidScreenText), so Daggerfall Unity draws them in its window while DoomerfallHudMessages sends them to Doom. It
// saves Daggerfall Unity's window every quarter second for five seconds from the first message (df-NNN.png), for
// side-by-side frames with Doom's screenshots taken on the same schedule. Logs what it showed.
// Does nothing without the flag.

using System;
using System.IO;
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
        float playSince = -1, sentAt;
        int shot = -1;

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
        }

        void Update()
        {
            if (shot >= Shots)
                return;
            if (shot >= 0)
            {
                if (Time.unscaledTime - sentAt < shot * Step)
                    return;
                ScreenCapture.CaptureScreenshot(Path.Combine(folder, string.Format("df-{0:D3}.png", shot)));
                shot++;
                return;
            }
            bool playing = sync.InGame && !sync.LoadRunning && sync.Phase == Dfb.DF_PHASE_PLAY;
            if (!playing)
            {
                playSince = -1;
                return;
            }
            if (playSince < 0)
                playSince = Time.unscaledTime;
            if (Time.unscaledTime - playSince < After)
                return;

            TextManager text = TextManager.Instance;
            string place = GameManager.Instance.PlayerGPS.CurrentLocation.Loaded ? GameManager.Instance.PlayerGPS.CurrentLocation.Name : "Daggerfall";
            DaggerfallUI.AddHUDText(text.GetLocalizedText("youAreEntering").Replace("%s", place), 2);  // as PlayerEnterExit
            DaggerfallUI.AddHUDText(text.GetLocalizedText("youFeelSomewhatBad"), 2.5f);               // as DiseaseEffect
            DaggerfallUI.AddHUDText(text.GetLocalizedText("trapNoneEmpty"));                           // as the trap check
            DaggerfallUI.Instance.PopupMessage(text.GetLocalizedText("youSeeA").Replace("%s", "Imp")); // as Info on a monster
            DaggerfallUI.SetMidScreenText(text.GetLocalizedText("youHaveNoArrows"));                  // as the bow
            sentAt = Time.unscaledTime;
            shot = 0;
            Directory.CreateDirectory(folder);
            bridge.LogLine("hudtest: sample sent at " + sentAt.ToString("F2"));
        }
    }
}
