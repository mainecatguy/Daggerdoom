// Doomerfall: moves the hidden Daggerfall player through the same door the Doom player used, with
// Daggerfall's own building and dungeon transitions, so its interior data is the one in memory.
//
// Doom sends one ordered event per door. This object only acts in a bridge session. The player's
// controller, activation, and weapons stay off, and dungeons load without their Daggerfall enemies.

using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTransition
    {
        const float TimeoutSeconds = 15f;
        const double DoorToleranceUnits = 128; // Doom's use reach. A wider miss means the wrong door.

        readonly DoomerfallBridge bridge;
        uint want = Dfb.WORLD_EXTERIOR, seq;
        double doorX, doorZ;
        int target;
        bool pending, attempted, teleported, greet;
        float deadline, startedAt;

        internal DoomerfallTransition(DoomerfallBridge owner)
        {
            bridge = owner;
        }

        // True until Daggerfall has reached the place Doom last reported, or has given up on it.
        internal bool Pending { get { return pending; } }

        // True when Daggerfall has finished entering the space Doom reports, so its local position applies.
        internal bool IsIn(PlayerEnterExit enter, uint context, int spaceTarget)
        {
            return !pending && !enter.IsRespawning && want == context && Actual(enter) == context && target == spaceTarget;
        }

        internal void OnEvent(uint action, uint eventSeq, double x, double z, int targetId)
        {
            want = action == Dfb.TRANSITION_ENTER_BUILDING ? Dfb.WORLD_INTERIOR : action == Dfb.TRANSITION_ENTER_DUNGEON ? Dfb.WORLD_DUNGEON : Dfb.WORLD_EXTERIOR;
            seq = eventSeq;
            doorX = x;
            doorZ = z;
            target = targetId;
            pending = true;
            // Daggerfall greets a player who walks in, not one a load puts inside (DFB_KIND_TRANSITION is sent for both).
            greet = action == Dfb.TRANSITION_ENTER_BUILDING && !bridge.PositionSync.LoadRunning;
            attempted = teleported = false;
            deadline = 0; // Starts at the first update, because Daggerfall may still be loading its world.
        }

        static uint Actual(PlayerEnterExit enter)
        {
            return enter.IsPlayerInsideDungeon ? Dfb.WORLD_DUNGEON : enter.IsPlayerInside ? Dfb.WORLD_INTERIOR : Dfb.WORLD_EXTERIOR;
        }

        // Runs each frame. True means the exterior position sync must not touch the player this frame.
        internal bool Update(GameManager game)
        {
            PlayerEnterExit enter = game.PlayerEnterExit;
            if (enter.IsRespawning)
                return true;
            if (!pending)
                return enter.IsPlayerInside;
            if (deadline == 0)
            {
                startedAt = Time.unscaledTime;
                deadline = startedAt + TimeoutSeconds;
            }

            uint actual = Actual(enter);
            if (actual == want)
            {
                Finish(game, actual);
                return actual != Dfb.WORLD_EXTERIOR;
            }
            if (Time.unscaledTime > deadline)
                return Fail(enter, "timed out");

            if (actual == Dfb.WORLD_INTERIOR)
            {
                enter.TransitionExterior(false);
                return true;
            }
            if (actual == Dfb.WORLD_DUNGEON)
            {
                enter.TransitionDungeonExterior(false);
                return true;
            }
            return Enter(game, enter);
        }

        bool Enter(GameManager game, PlayerEnterExit enter)
        {
            if (attempted)
                return Fail(enter, "Daggerfall's transition did not complete");
            StreamingWorld world = game.StreamingWorld;
            if (!world.DoomerfallPositionSettled)
                return true;

            DFPosition pixel = MapsFile.WorldCoordToMapPixel((int)doorX, (int)doorZ);
            if (world.MapPixelX != pixel.X || world.MapPixelY != pixel.Y)
            {
                if (teleported)
                    return true;
                teleported = true;
                world.TeleportToWorldCoordinates((int)doorX, (int)doorZ);
                return true;
            }

            DaggerfallLocation location = world.CurrentPlayerLocationObject;
            PlayerGPS gps = game.PlayerGPS;
            // Both lag the terrain after a map pixel change, and until then they still describe the previous location.
            if (!location || location.Summary.MapPixelX != pixel.X || location.Summary.MapPixelY != pixel.Y ||
                !gps.HasCurrentLocation || gps.CurrentLocation.Name != location.Summary.LocationName)
                return true;

            DoorTypes type = want == Dfb.WORLD_DUNGEON ? DoorTypes.DungeonEntrance : DoorTypes.Building;
            Vector3 player = gps.transform.position;
            DaggerfallStaticDoors bestOwner = null;
            StaticDoor bestDoor = new StaticDoor();
            double bestError = double.MaxValue;
            foreach (DaggerfallStaticDoors collection in location.StaticDoorCollections)
            {
                foreach (StaticDoor candidate in collection.Doors)
                {
                    if (candidate.doorType != type)
                        continue;
                    StaticDoor door = candidate;
                    door.ownerPosition = collection.transform.position;
                    door.ownerRotation = collection.transform.rotation;
                    Vector3 at = DaggerfallStaticDoors.GetDoorPosition(door);
                    double dx = gps.WorldX + (at.x - player.x) * StreamingWorld.SceneMapRatio - doorX;
                    double dz = gps.WorldZ + (at.z - player.z) * StreamingWorld.SceneMapRatio - doorZ;
                    double error = System.Math.Sqrt(dx * dx + dz * dz);
                    if (error < bestError)
                    {
                        bestError = error;
                        bestDoor = door;
                        bestOwner = collection;
                    }
                }
            }
            if (!bestOwner || bestError > DoorToleranceUnits)
                return Fail(enter, string.Format("no matching {0} door in {1}, nearest {2:F1} units", type, location.name, bestOwner ? bestError : -1));

            attempted = true;
            game.AcrobatMotor.ClearFallingDamage();
            bridge.LogLine(string.Format("transition {0}: door found in {1}, error {2:F1} units, building key {3}", seq, gps.CurrentLocation.Name, bestError, bestDoor.buildingKey));
            if (want == Dfb.WORLD_DUNGEON)
            {
                // No enemies: Doom owns the monsters, and this keeps the hidden player out of any fight.
                enter.StartDungeonInterior(gps.CurrentLocation, true, false);
                return true;
            }

            gps.DiscoverBuilding(bestDoor.buildingKey);
            PlayerGPS.DiscoveredBuilding building;
            if (!gps.GetDiscoveredBuilding(bestDoor.buildingKey, out building))
                return Fail(enter, "no discovery data for building key " + bestDoor.buildingKey);
            enter.BuildingDiscoveryData = building;
            enter.IsPlayerInsideOpenShop = RMBLayout.IsShop(building.buildingType) && PlayerActivate.IsBuildingOpen(building.buildingType);
            enter.IsPlayerInsideTavern = RMBLayout.IsTavern(building.buildingType);
            enter.IsPlayerInsideResidence = RMBLayout.IsResidence(building.buildingType);
            bool unlocked = true;
            bool greeting = greet && PlayerActivate.buildingGreetingsEnabled && Unlocked(game, world, bestDoor.buildingKey, out unlocked);
            enter.TransitionInterior(bestOwner.transform, bestDoor, false, false);
            if (greeting)
                Greet(game, bestDoor.buildingKey, building.buildingType, unlocked);
            return true;
        }

        // Daggerfall's own lock rule for the building, read before the transition while its exterior directory is current.
        static bool Unlocked(GameManager game, StreamingWorld world, int buildingKey, out bool unlocked)
        {
            unlocked = true;
            BuildingDirectory directory = world.GetCurrentBuildingDirectory();
            BuildingSummary summary;
            if (!directory || !directory.GetBuildingSummary(buildingKey, out summary))
                return false;
            unlocked = game.PlayerActivate.BuildingIsUnlocked(summary);
            return true;
        }

        // The message Daggerfall shows on walking in (PlayerActivate.PresentBuildingGreeting): an open home's greeting or a
        // shop's quality, as a message box that Doom shows (DoomerfallUi asks for it) or as HUD text, per Daggerfall's
        // ShopQualityPresentation setting. Daggerfall shows it before the player steps in; here the player is already in.
        // Doom does not lock building doors yet, so entering one Daggerfall holds locked counts as breaking in, the only
        // way in Daggerfall to be inside it: a shop still shows its quality, a home gives no greeting.
        void Greet(GameManager game, int buildingKey, DFLocation.BuildingTypes type, bool unlocked)
        {
            DaggerfallWorkshop.Game.UserInterfaceWindows.DaggerfallMessageBox box = game.PlayerActivate.PresentBuildingGreeting(buildingKey, type, true, !unlocked);
            bridge.LogLine(string.Format("transition {0}: greeting for building {1} type {2}, unlocked {3}: {4}", seq, buildingKey, type, unlocked,
                box != null ? "message box" : "none or HUD text"));
        }

        void Finish(GameManager game, uint actual)
        {
            pending = false;
            PlayerEnterExit enter = game.PlayerEnterExit;
            string place = actual == Dfb.WORLD_DUNGEON ? "dungeon " + game.PlayerGPS.CurrentLocation.Name
                : actual == Dfb.WORLD_INTERIOR ? "building " + enter.BuildingDiscoveryData.buildingKey + " type " + enter.BuildingType + " in " + game.PlayerGPS.CurrentLocation.Name
                : "exterior";
            bridge.LogLine(string.Format("transition {0}: Daggerfall is in {1}, target {2}, {3:F0} ms, gps {4},{5}, health {6}, submerged {7}", seq, place, target,
                (Time.unscaledTime - startedAt) * 1000f, game.PlayerGPS.WorldX, game.PlayerGPS.WorldZ, game.PlayerEntity.CurrentHealth, enter.IsPlayerSubmerged));
        }

        bool Fail(PlayerEnterExit enter, string why)
        {
            pending = false;
            bridge.LogLine("error: transition " + seq + " failed, " + why + ". Daggerfall stays where it is.");
            return enter.IsPlayerInside;
        }
    }
}
