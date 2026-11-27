// Doomerfall: Daggerfall's top-of-screen HUD messages and mid-screen text, shown in Doom. Runs only in a bridge session.
//
// Every message Daggerfall puts in its HUD through DaggerfallUI.AddHUDText, PopupMessage or SetMidScreenText goes to Doom as
// (deliberately not the three direct PopupText.AddText calls in PlayerEnterExit and TransportManager: they report
// Daggerfall repositioning its own hidden 3D player, "Terrain sampler changed. Repositioning player.", meaningless in Doom)
// DFB_KIND_HUD_TEXT with the seconds Daggerfall holds it, and Doom draws and scrolls it as Daggerfall Unity's
// PopupText does (mods/doomerfall/src/zscript/Doomerfall.zs). Info and Use on NPCs capture the hook for a moment to
// answer their own request (DoomerfallInfo.Capture) and then hand it back, so no line is sent twice.

using DaggerfallWorkshop.Localization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallHudMessages
    {
        static DoomerfallBridge bridge;

        internal static void Install(DoomerfallBridge owner)
        {
            bridge = owner;
            DaggerfallUI.DoomerfallHudText = Forward;
        }

        static void Forward(string text, bool mid, float seconds)
        {
            if (string.IsNullOrEmpty(text) || bridge == null)
                return;
            // As PopupText.AddText shows it.
            string shown = mid ? text : GrammarManager.grammarProcessor.ProcessGrammar(text);
            uint holdMs = (uint)Mathf.Clamp(seconds * 1000f, 0f, 60000f);
            DoomerfallInfo.SendText(bridge, holdMs, shown, mid, Dfb.KIND_HUD_TEXT);
            bridge.LogLine(string.Format("hud: {0} {1} ms: {2}", mid ? "mid" : "top", holdMs, shown));
        }
    }
}
