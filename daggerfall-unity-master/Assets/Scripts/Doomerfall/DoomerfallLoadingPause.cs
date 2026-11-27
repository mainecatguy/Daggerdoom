// Project:         Doomerfall
// Description:     Pauses Daggerfall while Doom holds the game behind its loading message.

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // Doom publishes uz_phase LOADING while a long operation holds the game (UZDoom dd_loading.cpp): a dungeon
    // conversion, a door handoff, a big dungeon spawn. Doom's world is frozen then, so Daggerfall pauses too and its
    // clock and effects (poison, disease, regeneration) do not move while the player cannot act.
    // It pauses only when nothing else had and resumes only a pause it made. A Daggerfall window closing during the
    // hold unpauses the game, so the pause is asserted every frame; a window still open at the end keeps its own pause.
    internal class DoomerfallLoadingPause
    {
        readonly DoomerfallBridge bridge;
        bool held, pausedHere, baselined;
        float heldSince;
        ulong noticeClock, clockAtHold, lastClock;
        int hpAtHold;

        internal DoomerfallLoadingPause(DoomerfallBridge bridge)
        {
            this.bridge = bridge;
        }

        // Each bridge frame: loading is true while Doom is live and publishes uz_phase LOADING.
        internal void Tick(bool loading)
        {
            if (!GameManager.HasInstance || (!loading && !held))
                return;
            GameManager game = GameManager.Instance;
            if (loading)
            {
                ulong now = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds();
                if (!held)
                {
                    held = true;
                    baselined = false;
                    heldSince = UnityEngine.Time.unscaledTime;
                    noticeClock = now;
                    bridge.LogLine(string.Format("loading: Daggerfall held for Doom's loading, clock {0}, hp {1}, already paused {2}",
                        now, game.PlayerEntity.CurrentHealth, GameManager.IsGamePaused));
                }
                else if (!baselined)
                {
                    // The frame that saw the hold first had its time step fixed before the pause; it still moved the clock
                    // by that one step (the lead-in). From this frame on the pause holds, so this is the hold's baseline.
                    baselined = true;
                    clockAtHold = now;
                    hpAtHold = game.PlayerEntity.CurrentHealth;
                    bridge.LogLine(string.Format("loading: Daggerfall paused, clock {0}, hp {1}, lead-in {2} s", now, hpAtHold, (long)(now - noticeClock)));
                }
                else if (now != lastClock || !GameManager.IsGamePaused)
                    bridge.LogLine(string.Format("loading: Daggerfall clock {0} moved during the hold, paused {1}, frame {2}", now, GameManager.IsGamePaused, UnityEngine.Time.frameCount));
                lastClock = now;
                if (!GameManager.IsGamePaused)
                {
                    game.PauseGame(true);
                    pausedHere = true;
                }
                return;
            }

            held = false;
            ulong clock = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds();
            int hp = game.PlayerEntity.CurrentHealth;
            if (!baselined)
            {
                clockAtHold = clock; // a hold of one frame: only its lead-in
                hpAtHold = hp;
            }
            bool resume = pausedHere && GameManager.IsGamePaused && DaggerfallUI.UIManager.WindowCount <= 1;
            if (resume)
                game.PauseGame(false);
            pausedHere = false;
            bridge.LogLine(string.Format("loading: Daggerfall released after {0:0} ms, clock {1} (changed {2} s), hp {3} (changed {4}), resumed {5}, lead-in {6} s",
                (UnityEngine.Time.unscaledTime - heldSince) * 1000f, clock, (long)(clock - clockAtHold), hp, hp - hpAtHold, resume, (long)(clockAtHold - noticeClock)));
        }
    }
}
