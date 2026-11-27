// Project:         Doomerfall
// Description:     Test of DoomerfallLoadingPause, on only with -dfloadingpausetest.

using System;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.MagicAndEffects;
using DaggerfallWorkshop.Game.MagicAndEffects.MagicEffects;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    // Measures Daggerfall's clock and HP across each Doom loading hold and writes them to the bridge log for
    // tools/loading_hold/check_df_pause.py. At the first hold it poisons the player with Moonseed (no delay, 1-9 HP each
    // game minute), so HP has something to lose while the game is held. It logs the poison's state at the hold and the
    // release (unchanged), then the frame of its first tick after the release with the HP change in that frame, which
    // shows the poison was live and only the pause stopped it (Doom's hits arrive in other frames, via DoomerfallHp). Changes are counted from the first paused frame: the frame that first saw the hold had its time
    // step fixed before the pause, so it can move the clock by that one frame (the lead-in), reported with its bound.
    internal static class DoomerfallLoadingPauseTest
    {
        const float WatchSeconds = 10f; // 120 game seconds: Moonseed hits on its first game minute
        static int enabled = -1; // -1 not read yet
        static bool held, baselined, poisoned;
        static float heldSince, frameGameSeconds, releasedAt = -1f;
        static ulong noticeClock, clockAtHold, lastClock;
        static int hpAtHold, hpLastFrame;
        static string poisonAtHold = "none", poisonAtRelease = "none";

        static ulong Clock() { return DaggerfallUnity.Instance.WorldTime.Now.ToSeconds(); }

        static PoisonEffect Poison()
        {
            foreach (LiveEffectBundle bundle in GameManager.Instance.PlayerEffectManager.PoisonBundles)
                foreach (IEntityEffect effect in bundle.liveEffects)
                    if (effect is PoisonEffect)
                        return (PoisonEffect)effect;
            return null;
        }

        internal static void Tick(DoomerfallBridge bridge, bool loading)
        {
            if (enabled < 0)
                enabled = Array.IndexOf(Environment.GetCommandLineArgs(), "-dfloadingpausetest") >= 0 ? 1 : 0;
            if (enabled == 0 || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            ulong now = Clock();
            if (loading && !held)
            {
                held = true;
                baselined = false;
                heldSince = Time.unscaledTime;
                noticeClock = now;
                frameGameSeconds = Time.deltaTime * DaggerfallUnity.Instance.WorldTime.TimeScale;
                if (!poisoned)
                {
                    EntityEffectManager effects = GameManager.Instance.PlayerEffectManager;
                    effects.AssignBundle(effects.CreatePoison(Poisons.Moonseed), AssignBundleFlags.BypassSavingThrows);
                    poisoned = true;
                    bridge.LogLine("loadingpausetest: poisoned with Moonseed, poisons " + effects.PoisonCount);
                }
                bridge.LogLine(string.Format("loadingpausetest: hold seen, clock {0}, hp {1}, frame {2:0.00} game s", now, player.CurrentHealth, frameGameSeconds));
            }
            else if (loading && !baselined)
            {
                baselined = true;
                clockAtHold = now;
                hpAtHold = player.CurrentHealth;
                PoisonEffect p = Poison();
                poisonAtHold = p == null ? "gone" : p.CurrentState + " " + p.RoundsRemaining;
            }
            else if (loading && now != lastClock)
                bridge.LogLine(string.Format("loadingpausetest: clock moved during the hold to {0}, paused {1}", now, GameManager.IsGamePaused));
            else if (!loading && held)
            {
                held = false;
                if (!baselined)
                {
                    clockAtHold = now;
                    hpAtHold = player.CurrentHealth;
                }
                int hpAtRelease = player.CurrentHealth;
                PoisonEffect p = Poison();
                poisonAtRelease = p == null ? "gone" : p.CurrentState + " " + p.RoundsRemaining;
                releasedAt = Time.unscaledTime;
                bridge.LogLine(string.Format("loadingpausetest: released after {0:0} ms, clock {1} (changed {2} s), hp {3} (changed {4}), lead-in {5} s, frame {6:0.00} game s, poison {7} (at the hold {8})",
                    (Time.unscaledTime - heldSince) * 1000f, now, (long)(now - clockAtHold), hpAtRelease, hpAtRelease - hpAtHold,
                    (long)(clockAtHold - noticeClock), frameGameSeconds, poisonAtRelease, poisonAtHold));
            }
            else if (!loading && releasedAt >= 0)
            {
                // The poison's first tick after the hold: its own HP change, apart from Doom's hits in other frames.
                PoisonEffect p = Poison();
                string state = p == null ? "gone" : p.CurrentState + " " + p.RoundsRemaining;
                if (state != poisonAtRelease || Time.unscaledTime - releasedAt > WatchSeconds)
                {
                    bridge.LogLine(string.Format("loadingpausetest: poison after the release: {0} -> {1} after {2:0.0} s, hp {3} -> {4} in that frame (changed {5})",
                        poisonAtRelease, state, Time.unscaledTime - releasedAt, hpLastFrame, player.CurrentHealth, player.CurrentHealth - hpLastFrame));
                    releasedAt = -1f;
                }
            }
            lastClock = now;
            hpLastFrame = player.CurrentHealth;
        }
    }
}
