// Project:         Doomerfall
// Description:     Pauses Daggerfall while Doom holds the game behind its loading message.

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // Doom publishes uz_phase LOADING while a long operation holds the game (UZDoom dd_loading.cpp): a dungeon
    // conversion, a door handoff, a big dungeon spawn. Doom's world is frozen then, so Daggerfall pauses too and its
    // clock and effects (poison, disease, regeneration) do not move while the player cannot act.
    // It pauses only when nothing else had and resumes only a pause it made. A Daggerfall window closing during the
    // hold unpauses the game, so the pause is asserted every frame; a window still open at the end keeps its own pause.
    // The test of it is DoomerfallLoadingPauseTest (-dfloadingpausetest).
    internal class DoomerfallLoadingPause
    {
        readonly DoomerfallBridge bridge;
        bool pausedHere;

        internal bool Held { get; private set; }

        internal DoomerfallLoadingPause(DoomerfallBridge bridge)
        {
            this.bridge = bridge;
        }

        // Each bridge frame: loading is true while Doom is live and publishes uz_phase LOADING.
        internal void Tick(bool loading)
        {
            if (!GameManager.HasInstance || loading == Held && !loading)
                return;
            if (loading)
            {
                if (!Held)
                    bridge.LogLine("loading: Daggerfall paused for Doom's loading");
                Held = true;
                if (!GameManager.IsGamePaused)
                {
                    GameManager.Instance.PauseGame(true);
                    pausedHere = true;
                }
                return;
            }
            Held = false;
            bool resume = pausedHere && GameManager.IsGamePaused && DaggerfallUI.UIManager.WindowCount <= 1;
            if (resume)
                GameManager.Instance.PauseGame(false);
            pausedHere = false;
            bridge.LogLine("loading: Daggerfall released, resumed " + resume);
        }
    }
}
