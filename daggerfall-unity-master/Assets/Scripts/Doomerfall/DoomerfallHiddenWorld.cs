// Doomerfall: keeps Daggerfall's hidden 3D world no larger than what Doom has loaded, and closes the gaps where it
// could still act on the game by itself. Runs only in a bridge session. See work/notes/20261124-191013.md.
//
// - Streaming radius. Doom's exterior window is 128 x 128 tiles of 256 Daggerfall units, one map pixel wide around
//   the player, and a Doom town map is one location, which fits in one map pixel. Daggerfall's streaming world with
//   TerrainDistance 1 keeps the player's map pixel and its 8 neighbours, so it still holds every world object Doom
//   can show or ask about. Daggerfall Unity's own setting (3 here) builds 49 terrains with their towns instead of 9.
// - Random encounters. PositionSync sets PreventEnemySpawns only on the paths of its Tick that reach the world, and
//   PlayerEntity clears the flag after each of its updates. On frames where Tick returned early (a door or load in
//   progress), a game minute could pass without it. This sets it every frame while the hidden player is engaged.
//
// Everything else stays as it is: the world is still built, drawing is still switched by -dfnodraw, and enemies are
// still held by DisableAI. -dfworldradius N (measurement and comparison only) uses radius N, or 0 for the setting.

using System;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHiddenWorld : MonoBehaviour
    {
        public const int SessionTerrainDistance = 1;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        int radius = SessionTerrainDistance;
        int lastLogged = -1;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, string[] args)
        {
            bridge = owner;
            sync = positionSync;
            int at = Array.IndexOf(args, "-dfworldradius");
            int value;
            if (at >= 0 && at + 1 < args.Length && int.TryParse(args[at + 1], out value) && value >= 0)
                radius = value;
            else if (int.TryParse(Environment.GetEnvironmentVariable("DOOMERFALL_WORLDRADIUS"), out value) && value >= 0)
                radius = value; // The same, for harnesses that cannot add Daggerfall arguments.
        }

        void LateUpdate()
        {
            if (!GameManager.HasInstance)
                return;
            GameManager game = GameManager.Instance;
            if (!game.IsReady)
                return;
            StreamingWorld world = game.StreamingWorld;
            if (radius > 0 && world && world.TerrainDistance != radius)
            {
                // StartGameBehaviour copies the setting into the streaming world at every game start.
                if (lastLogged != world.TerrainDistance)
                    bridge.LogLine(string.Format("hidden world: streaming radius {0} -> {1} map pixels", world.TerrainDistance, radius));
                lastLogged = world.TerrainDistance;
                world.TerrainDistance = radius;
            }
            if (sync.Engaged && game.PlayerEntity != null)
                game.PlayerEntity.PreventEnemySpawns = true;
        }
    }
}
