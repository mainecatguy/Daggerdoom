// Doomerfall: Daggerfall's two falling damage exemptions, published every frame in dfb_df_state.player_flags so Doom
// applies them to its falls (mods/doomerfall/src/zscript/DoomerfallJump.zs). Daggerfall owns the rule
// (AcrobatMotor): a Slowfall effect restarts the fall each frame, so damage counts only from where it ended, and a
// landing outdoors on a water tile (StreamingWorld.PlayerTileMapIndex 0) does no damage. The player's position here is
// the one Doom sends (DoomerfallPositionSync), so the tile is the one under Doom's player.

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallFallState
    {
        readonly DoomerfallBridge bridge;
        readonly DoomerfallPositionSync sync;
        uint lastFlags;

        public DoomerfallFallState(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
        }

        // Runs every frame and allocates nothing except the log line when the flags change.
        public void Fill(ref DfbDfState state)
        {
            uint flags = 0;
            GameManager gm = GameManager.HasInstance ? GameManager.Instance : null;
            if (sync.InGame && gm != null && gm.PlayerEntity != null)
            {
                if (gm.PlayerEntity.IsSlowFalling)
                    flags |= Dfb.PLF_SLOWFALL;
                if (gm.PlayerEnterExit != null && !gm.PlayerEnterExit.IsPlayerInside && gm.StreamingWorld != null &&
                    gm.StreamingWorld.PlayerTileMapIndex == 0)
                    flags |= Dfb.PLF_OUTDOOR_WATER;
            }
            state.playerFlags = flags;
            if (flags != lastFlags)
            {
                bridge.LogLine(string.Format("fall state: slowfall {0} outdoor water {1}", (flags & Dfb.PLF_SLOWFALL) != 0 ? 1 : 0,
                    (flags & Dfb.PLF_OUTDOOR_WATER) != 0 ? 1 : 0));
                lastFlags = flags;
            }
        }
    }
}
