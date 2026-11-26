// Doomerfall: Daggerfall's rest window opened from Doom (DFB_UI_REST), and the level-up line on Doom's HUD. Runs only in
// a bridge session.
//
// Daggerfall's own rest code runs unchanged: its window, its time, its vitals, its skill and level-up check. Doom owns the
// world the player stands in, so the two things Daggerfall's hidden world cannot know come from Doom with the request:
// whether hostile Doom monsters are near (Daggerfall's "enemies nearby" check while resting), and whether the player is
// on the ground and out of deep water (its "cannot rest now" check). HP recovered per hour of rest is three times
// Daggerfall's (gamedesign/hp.md, owner 2026-11-26).

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public static class DoomerfallRest
    {
        const int HealthRecoveryScale = 3;

        static DoomerfallBridge bridge;
        static bool fromDoom;
        static uint doomState;

        internal static void Begin(DoomerfallBridge owner)
        {
            bridge = owner;
            Formulas.FormulaHelper.DoomerfallHealthRecoveryScale = HealthRecoveryScale;
        }

        internal static void End()
        {
            bridge = null;
            fromDoom = false;
            Formulas.FormulaHelper.DoomerfallHealthRecoveryScale = 1;
        }

        /// <summary>Doom asked for the rest window; state is its DFB_REST_* bits.</summary>
        internal static void Opening(uint state)
        {
            fromDoom = true;
            doomState = state;
            bridge.LogLine(string.Format("rest: Doom asks to rest, monsters near {0}, on the ground {1}",
                (state & Dfb.REST_MONSTERS_NEAR) != 0, (state & Dfb.REST_NOT_GROUNDED) == 0));
            if (GameManager.HasInstance)
                PlayerEntityLog("rest: menu opening");
        }

        /// <summary>Doom's menu for the rest window closed.</summary>
        internal static void Closed()
        {
            if (fromDoom && bridge != null && GameManager.HasInstance)
            {
                PlayerEntityLog("rest: menu closed");
            }
            fromDoom = false;
            doomState = 0;
        }

        /// <summary>For GameManager.AreEnemiesNearby while resting: Doom's monsters were near when the rest was asked for.
        /// Doom is paused behind the window, so they stay where they were.</summary>
        public static bool DoomMonstersNear { get { return fromDoom && (doomState & Dfb.REST_MONSTERS_NEAR) != 0; } }

        /// <summary>For DaggerfallUI's rest check: true when this rest came from Doom, with Doom's answer to
        /// "swimming or not on the ground" in cannotRest.</summary>
        public static bool FromDoom(out bool cannotRest)
        {
            cannotRest = fromDoom && (doomState & Dfb.REST_NOT_GROUNDED) != 0;
            return fromDoom;
        }

        /// <summary>The character sheet raised the player's level. Doom shows the line on its HUD (owner, 2026-11-26).</summary>
        public static void LevelReached(int level)
        {
            if (bridge == null)
                return;
            DoomerfallInfo.SendText(bridge, 0, string.Format("You have reached level {0}", level), false, Dfb.KIND_HUD_TEXT);
            bridge.LogLine("rest: level up, sent the HUD line for level " + level);
        }

        static void PlayerEntityLog(string what)
        {
            var p = GameManager.Instance.PlayerEntity;
            if (p != null)
                bridge.LogLine(string.Format("{0}: hp {1}/{2} fatigue {3}/{4} magicka {5}/{6} level {7} game_minutes {8}", what, p.CurrentHealth, p.MaxHealth,
                    p.CurrentFatigue, p.MaxFatigue, p.CurrentMagicka, p.MaxMagicka, p.Level, DaggerfallUnity.Instance.WorldTime.DaggerfallDateTime.ToClassicDaggerfallTime()));
        }
    }
}
