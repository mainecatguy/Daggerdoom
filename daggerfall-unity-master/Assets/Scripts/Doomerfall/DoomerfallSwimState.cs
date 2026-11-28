// Doomerfall: Daggerfall's outdoor swimming while Doom moves the player (owner, 2026-11-27, Q&A item 59). Doom reports
// that its player swims on outdoor water (dfb_uz_state.player_motion, decided in dd_bridge.cpp from the water tile and
// Water Walking that DoomerfallFallState publishes). Daggerfall's hidden player has its motor off, so the height changer
// that would set IsPlayerSwimming outdoors (PlayerHeightChanger.DoSinking) never runs; this sets it instead. Daggerfall's
// own rules then run unchanged: each game minute PlayerEntity tallies Swimming and charges swimming fatigue on a failed
// Swimming roll (Argonians never), and resting is refused. Breath is untouched: outdoors Daggerfall never submerges.

using DaggerfallConnect;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallSwimState
    {
        static bool applied; // IsPlayerSwimming was set from Doom's report and not cleared yet

        // Runs every frame after the peer state is read. Allocates nothing except the log line on a change.
        public static void Apply(DoomerfallBridge bridge, bool inGame, ref DfbUzState peer)
        {
            if (!GameManager.HasInstance || GameManager.Instance.PlayerEnterExit == null)
                return;
            PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
            bool swimming = inGame && peer.worldContext == Dfb.WORLD_EXTERIOR && !enter.IsPlayerInside &&
                (peer.playerMotion & Dfb.UZM_SWIMMING) != 0;
            if (swimming)
                enter.IsPlayerSwimming = true; // kept set each frame, as the height changer keeps it while sunk
            else if (applied && !enter.IsPlayerInside)
                enter.IsPlayerSwimming = false; // only what was set here; dungeons keep their own swimming state
            if (swimming != applied)
            {
                applied = swimming;
                Entity.PlayerEntity player = GameManager.Instance.PlayerEntity;
                if (player != null)
                    bridge.LogLine(string.Format("swim state: swimming {0} Swimming skill {1} uses {2} fatigue {3} breath {4} time {5}", swimming ? 1 : 0,
                        player.Skills.GetLiveSkillValue(DFCareer.Skills.Swimming), player.SkillUses[(int)DFCareer.Skills.Swimming],
                        player.CurrentFatigue, player.CurrentBreath, DaggerfallUnity.Instance.WorldTime.Now.ToClassicDaggerfallTime()));
            }
        }
    }
}
