// Doomerfall: keeps the hidden Daggerfall player in the same exterior area as the Doom player, so the
// world objects Doom asks about are loaded. This is not a matching simulation.
//
// UZDoom publishes Daggerfall world units (doom / 0.75 + window origin). Position is applied about ten
// times per second. An area change is applied as soon as its event arrives.
//
// Indoors, Doom's map is the interior or dungeon's own layout at 75%, so the Daggerfall local position is
// (doomX, doomZ, doomY) / 0.75 / 40, placed through that space's transform.
//
// Only active in a bridge session, and only while Doom reports a Daggerfall place.

using System;
using System.Collections;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public sealed class DoomerfallPositionSync : MonoBehaviour
    {
        const long CameraCheckNs = 1000000000;
        const int DefaultSyncHz = 10;
        const float IndoorFootClearance = 0.05f;
        const int TeleportPixels = 2; // Farther than this, streaming would have nothing loaded at the target.
        const int GameSceneIndex = 1;
        const int TestStartPixelX = 207, TestStartPixelY = 213;
        const long TravelHoldNs = 30000000000;

        long applyIntervalNs = 1000000000L / DefaultSyncHz;
        long nextIndoorApplyNs;
        bool indoorLandingPending, savedFootsteps, testWaterBlocks, sawSwimming, sawSubmerged;
        int testSink; // Test only. 1 aims into flooded water with the guard on, 2 with it off.
        readonly SyncStats outdoorStats = new SyncStats(), indoorStats = new SyncStats();
        bool travelHold;
        int travelX, travelY;
        long travelHoldUntilNs;
        DoomerfallBridge bridge;
        DoomerfallTransition transition;
        bool logAfterExit;
        bool engaged, savedDisableAI, savedMotor, savedController, savedLook, savedActivate, savedWeapons;
        bool areaDirty, areaPending, verifyPending, noDraw, testWorldReady, testEnemySpawned, testImageTaken;
        uint phase = Dfb.DF_PHASE_BOOT;
        int areaX, areaY, targetX, targetZ, teleports, applies;
        bool aligned;
        float mismatchStreak, mismatchTotal, worstMismatch, alignedTime, worstFrame;
        int slowFrames, alignedFrames, indoorFrames;
        long nextApplyNs, areaSentNs, nextCameraCheckNs;
        double worstApplyError, worstLag;
        int startHealth = -1;
        GameObject testEnemy;
        Vector3 testEnemyStart;
        bool testEnemyAI; // Negative control: leaves enemy AI on, to prove the test can see an attack.
        float lastFrameTime;
        readonly DoomerfallBridge.Samples frameMs = new DoomerfallBridge.Samples();
        readonly DoomerfallBridge.Samples areaLatency = new DoomerfallBridge.Samples();

        public uint Phase { get { return phase; } }

        // True once Daggerfall is in a game, from the test start or a normal one.
        public bool InGame { get { return testWorldReady || (GameManager.HasInstance && GameManager.Instance.StateManager.GameInProgress); } }

        public void Init(DoomerfallBridge owner, string[] args)
        {
            bridge = owner;
            transition = new DoomerfallTransition(owner);
            noDraw = Array.IndexOf(args, "-dfnodraw") >= 0;
            int rate = Array.IndexOf(args, "-dfsynchz"); // Measurement only: compares update rates.
            int hz;
            if (rate >= 0 && rate + 1 < args.Length && int.TryParse(args[rate + 1], out hz) && hz > 0)
                applyIntervalNs = 1000000000L / hz;
            if (DaggerfallUnityApplication.IsPortableInstall)
                testSink = Array.IndexOf(args, "-dfsynctestsink") >= 0 ? 1 : Array.IndexOf(args, "-dfsynctestsinknoguard") >= 0 ? 2 : 0;
            int test = Array.IndexOf(args, "-dfsynctest");
            if (test < 0)
                return;
            testEnemyAI = Array.IndexOf(args, "-dfsynctestenemyai") >= 0;
            if (!DaggerfallUnityApplication.IsPortableInstall || test + 1 >= args.Length)
            {
                bridge.LogLine("error: -dfsynctest needs a portable install and a Daggerfall path");
                return;
            }
            StartCoroutine(TestStart(args[test + 1]));
        }

        // Test only. The real startup flow is a separate task.
        IEnumerator TestStart(string daggerfallPath)
        {
            var settings = DaggerfallUnity.Settings; // In memory only; the portable install keeps it private.
            settings.MyDaggerfallPath = daggerfallPath;
            settings.RunInBackground = true;
            settings.SoundVolume = 0;
            settings.MusicVolume = 0;
            Application.runInBackground = true;
            settings.VSync = false; // Frame times should show work rather than the display rate.
            settings.TargetFrameRate = 0;
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;

            yield return SceneManager.LoadSceneAsync(GameSceneIndex);
            while (!DaggerfallUnity.Instance.IsReady || !GameManager.Instance.IsReady)
                yield return null;

            var start = FindObjectOfType<StartGameBehaviour>();
            start.EnableVideos = false;
            start.StartMethod = StartGameBehaviour.StartMethods.Void;
            for (int i = 0; i < 5; i++)
                yield return null;
            DaggerfallUI.Instance.PopToHUD();

            GameManager.Instance.PlayerEnterExit.EnableExteriorParent();
            StreamingWorld world = GameManager.Instance.StreamingWorld;
            world.suppressWorld = false;
            world.TeleportToCoordinates(TestStartPixelX, TestStartPixelY);
            GameManager.Instance.PauseGame(false);

            PlayerEntity player = GameManager.Instance.PlayerEntity;
            player.MaxHealth = 100;
            player.SetHealth(100, true);
            player.GoldPieces = 5000; // Lets the travel menu test afford any trip.
            if (player.SkillUses == null) // The blank test character has none, and travel's skill check reads them.
                player.SkillUses = new short[DaggerfallSkills.Count];
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-dfinventorytest") >= 0) // Something to equip and move in the inventory test.
            {
                // The blank test character's career can forbid every weapon.
                player.Career.ForbiddenProficiencies = 0;
                player.Career.ForbiddenMaterials = 0;
                player.Items.AddItem(DaggerfallWorkshop.Game.Items.ItemBuilder.CreateWeapon(DaggerfallWorkshop.Game.Items.Weapons.Longsword, DaggerfallWorkshop.Game.Items.WeaponMaterialTypes.Iron));
                player.Items.AddItem(DaggerfallWorkshop.Game.Items.ItemBuilder.CreateWeapon(DaggerfallWorkshop.Game.Items.Weapons.Dagger, DaggerfallWorkshop.Game.Items.WeaponMaterialTypes.Steel));
            }
            startHealth = player.CurrentHealth;
            testWorldReady = true;
            bridge.LogLine("sync test: entered the world, health " + startHealth);
        }

        public void OnAreaEvent(uint context, int pixelX, int pixelY, long sentNs)
        {
            if (context != Dfb.WORLD_EXTERIOR)
                return;
            areaX = pixelX;
            areaY = pixelY;
            areaSentNs = sentNs;
            areaDirty = true;
            areaPending = true;
        }

        internal void Tick(ref DfbUzState peer)
        {
            float now = Time.realtimeSinceStartup;
            if (lastFrameTime > 0)
                frameMs.Add((long)((now - lastFrameTime) * 1e9f));
            lastFrameTime = now;

            bool indoors = false;
            switch (peer.worldContext)
            {
                case Dfb.WORLD_EXTERIOR:
                    break;
                case Dfb.WORLD_INTERIOR:
                case Dfb.WORLD_DUNGEON:
                    indoors = true;
                    break;
                case Dfb.WORLD_NONE:
                default:
                    Release();
                    return;
            }

            if (!GameManager.HasInstance)
                return;
            GameManager game = GameManager.Instance;
            if (!game.IsReady)
                return;
            StreamingWorld world = game.StreamingWorld;
            if (!world || LoadRunning)
                return;

            // Daggerfall follows Doom through doors. Indoors there is no exterior position to apply.
            if (InGame && transition.Update(game))
            {
                Engage(game);
                game.DisableAI = !testEnemyAI;
                game.PlayerEntity.PreventEnemySpawns = true;
                long indoorNowNs = DfbNative.dfb_now_ns();
                if (noDraw && indoorNowNs >= nextCameraCheckNs)
                {
                    nextCameraCheckNs = indoorNowNs + CameraCheckNs;
                    HideWorld(game);
                }
                if (!game.PlayerEnterExit.IsRespawning)
                    phase = Dfb.DF_PHASE_PLAY;
                if (indoorNowNs >= nextIndoorApplyNs && ApplyIndoor(game, ref peer))
                    nextIndoorApplyNs = indoorNowNs + applyIntervalNs;
                MeasureIndoor(game, ref peer);
                return;
            }

            if (!world.isActiveAndEnabled || world.suppressWorld || game.PlayerEnterExit.IsPlayerInside)
                return;

            Engage(game);
            game.DisableAI = !testEnemyAI;
            game.PlayerEntity.PreventEnemySpawns = true; // Cleared by PlayerEntity after each update.

            long nowNs = DfbNative.dfb_now_ns();
            if (noDraw && nowNs >= nextCameraCheckNs)
            {
                nextCameraCheckNs = nowNs + CameraCheckNs;
                HideWorld(game);
            }

            // Doom is indoors but Daggerfall could not follow. It waits at the last outdoor position,
            // which is the door the player used, and still answers menus.
            if (indoors)
            {
                indoorFrames++;
                if (world.DoomerfallPositionSettled)
                    phase = Dfb.DF_PHASE_PLAY;
                return;
            }

            // After a fast travel Daggerfall leads: Doom's old position must not pull the player back.
            if (travelHold)
            {
                if (peer.mapPixelX == travelX && peer.mapPixelY == travelY)
                {
                    travelHold = false;
                    bridge.LogLine(string.Format("travel: Doom reached pixel {0},{1}", travelX, travelY));
                }
                else if (nowNs < travelHoldUntilNs)
                    return;
                else
                {
                    travelHold = false;
                    bridge.LogLine("error: Doom did not arrive after fast travel, following Doom's position");
                }
            }

            // Measured from the first time both games agree, so the initial load is not counted as drift.
            bool samePixel = world.MapPixelX == peer.mapPixelX && world.MapPixelY == peer.mapPixelY;
            if (aligned)
            {
                mismatchStreak = samePixel ? 0 : mismatchStreak + Time.unscaledDeltaTime;
                if (!samePixel) mismatchTotal += Time.unscaledDeltaTime;
                worstMismatch = Mathf.Max(worstMismatch, mismatchStreak);
                alignedTime += Time.unscaledDeltaTime;
                // Every frame, because the percentile window holds only the most recent 1,024.
                worstFrame = Mathf.Max(worstFrame, Time.unscaledDeltaTime);
                if (Time.unscaledDeltaTime > 1f / 60f) slowFrames++;
                alignedFrames++;
                if (bridge.LogEnabled && !indoors)
                    outdoorStats.AddFrame(Distance(peer.worldX - game.PlayerGPS.WorldX, peer.worldZ - game.PlayerGPS.WorldZ), Time.unscaledDeltaTime);
            }

            if (!world.DoomerfallPositionSettled)
                return;
            phase = Dfb.DF_PHASE_PLAY;

            if (!aligned && samePixel)
            {
                aligned = true;
                worstLag = 0;
                worstApplyError = 0;
                bridge.LogLine("sync: aligned with Doom at pixel " + world.MapPixelX + "," + world.MapPixelY);
            }

            PlayerGPS gps = game.PlayerGPS;
            if (verifyPending)
            {
                verifyPending = false;
                worstApplyError = Math.Max(worstApplyError, Distance(gps.WorldX - targetX, gps.WorldZ - targetZ));
                if (logAfterExit)
                {
                    logAfterExit = false;
                    bridge.LogLine(string.Format("transition: back on Doom's position after the exit, off by {0:F1} units, gps {1},{2}, health {3}",
                        Distance(gps.WorldX - targetX, gps.WorldZ - targetZ), gps.WorldX, gps.WorldZ, game.PlayerEntity.CurrentHealth));
                }
            }
            if (areaPending && world.MapPixelX == areaX && world.MapPixelY == areaY)
            {
                areaPending = false;
                areaLatency.Add(nowNs - areaSentNs);
                if (bridge.LogEnabled)
                    bridge.LogLine(string.Format("sync: area {0},{1} loaded {2:F1} ms after Doom entered it", areaX, areaY, (nowNs - areaSentNs) / 1e6));
            }

            // After the first teleport, because a teleport clears loose enemies.
            if (testWorldReady && !testEnemySpawned && aligned)
                SpawnTestEnemy(game);

            if (testWorldReady && !testImageTaken && alignedTime > 3f)
                CaptureTestImage(game);

            if (!areaDirty && nowNs < nextApplyNs)
                return;
            areaDirty = false;
            nextApplyNs = nowNs + applyIntervalNs;
            long applyStart = System.Diagnostics.Stopwatch.GetTimestamp();
            Apply(game, world, gps, ref peer);
            outdoorStats.AddApply(System.Diagnostics.Stopwatch.GetTimestamp() - applyStart);
        }

        // Save handshake: moves Daggerfall to Doom's frozen position now instead of at the next update.
        // Indoors Doom keeps publishing the door it used, which the once-a-second update may not have reached.
        // False means the world cannot take the position yet.
        internal bool ApplyForSave(ref DfbUzState peer)
        {
            if (travelHold || transition.Pending)
                return false;
            GameManager game = GameManager.Instance;
            if (game.PlayerEnterExit.IsPlayerInside)
            {
                if (game.PlayerEnterExit.IsRespawning)
                    return false;
                ApplyIndoor(game, ref peer); // The save records where Doom's player really stands in the room.
                return true;
            }
            StreamingWorld world = game.StreamingWorld;
            bool known = peer.worldContext == Dfb.WORLD_EXTERIOR ||
                ((peer.worldContext == Dfb.WORLD_INTERIOR || peer.worldContext == Dfb.WORLD_DUNGEON) && peer.mapPixelX >= 0 && peer.mapPixelY >= 0);
            if (known)
            {
                if (!world.DoomerfallPositionSettled)
                    return false;
                Apply(game, world, game.PlayerGPS, ref peer);
            }
            return true;
        }

        // The exterior streaming world does not update while the player is indoors.
        internal bool PositionSettled
        {
            get
            {
                GameManager game = GameManager.Instance;
                return game.PlayerEnterExit.IsPlayerInside ? !game.PlayerEnterExit.IsRespawning : game.StreamingWorld.DoomerfallPositionSettled;
            }
        }

        // A load replaces Daggerfall's place. Doom reports its restored side of the door before the load ends.
        internal bool LoadRunning { get; set; }

        // Daggerfall has booted and waits behind Doom's title with no game.
        internal void SetMenuPhase() { phase = Dfb.DF_PHASE_MENU; }

        internal void OnTransitionEvent(uint action, uint seq, double x, double z, int target)
        {
            transition.OnEvent(action, seq, x, z, target);
            logAfterExit = action == Dfb.TRANSITION_EXIT_BUILDING || action == Dfb.TRANSITION_EXIT_DUNGEON;
            verifyPending = false; // A check still waiting from before the door would compare against an old target.
            indoorLandingPending = action == Dfb.TRANSITION_ENTER_BUILDING || action == Dfb.TRANSITION_ENTER_DUNGEON;
            nextIndoorApplyNs = 0;
            areaDirty = true; // Apply Doom's outdoor position as soon as the world allows it.
        }

        // Daggerfall has moved the player itself. Holds until Doom reports the same map pixel.
        internal void BeginTravelHold(int pixelX, int pixelY)
        {
            travelHold = true;
            travelX = pixelX;
            travelY = pixelY;
            travelHoldUntilNs = DfbNative.dfb_now_ns() + TravelHoldNs;
        }

        internal void EndTravelHold()
        {
            travelHold = false;
        }

        void Apply(GameManager game, StreamingWorld world, PlayerGPS gps, ref DfbUzState peer)
        {
            targetX = Mathf.Clamp((int)peer.worldX, MapsFile.MinWorldCoordX, MapsFile.MaxWorldCoordX - 1);
            targetZ = Mathf.Clamp((int)peer.worldZ, MapsFile.MinWorldCoordZ, MapsFile.MaxWorldCoordZ - 1);
            int dx = targetX - gps.WorldX, dz = targetZ - gps.WorldZ;
            worstLag = Math.Max(worstLag, Distance(dx, dz));

            Transform player = gps.transform;
            player.rotation = Quaternion.Euler(0, 90f - peer.yawDegrees, 0);
            applies++;

            if (Math.Abs(peer.mapPixelX - world.MapPixelX) > TeleportPixels || Math.Abs(peer.mapPixelY - world.MapPixelY) > TeleportPixels)
            {
                teleports++;
                world.TeleportToWorldCoordinates(targetX, targetZ);
                verifyPending = true;
                return;
            }

            Vector3 position = player.position;
            position.x += dx / StreamingWorld.SceneMapRatio;
            position.z += dz / StreamingWorld.SceneMapRatio;
            GameObject terrainObject = world.GetTerrainFromPixel(peer.mapPixelX, peer.mapPixelY);
            Terrain terrain = terrainObject ? terrainObject.GetComponent<Terrain>() : null;
            if (terrain)
            {
                CharacterController controller = player.GetComponent<CharacterController>();
                position.y = terrain.SampleHeight(position) + terrain.transform.position.y + controller.height / 2f + 0.15f;
            }
            player.position = position;
            verifyPending = true;
        }

        // The transform of the space Doom reports, once Daggerfall has finished entering that same space.
        Transform IndoorSpace(GameManager game, ref DfbUzState peer)
        {
            PlayerEnterExit enter = game.PlayerEnterExit;
            if (peer.spaceValid == 0 || !transition.IsIn(enter, peer.worldContext, peer.spaceTarget))
                return null;
            if (peer.worldContext == Dfb.WORLD_DUNGEON)
                return enter.Dungeon ? enter.Dungeon.transform : null;
            return peer.worldContext == Dfb.WORLD_INTERIOR && enter.Interior ? enter.Interior.transform : null;
        }

        // Moves the hidden player to Doom's place in the room. Its controller is off, so nothing here collides,
        // falls, or triggers. False means Daggerfall is not in Doom's space yet.
        bool ApplyIndoor(GameManager game, ref DfbUzState peer)
        {
            Transform space = IndoorSpace(game, ref peer);
            if (!space)
                return false;
            long applyStart = System.Diagnostics.Stopwatch.GetTimestamp();
            Transform player = game.PlayerObject.transform;
            float scale = MeshReader.GlobalScale;
            Vector3 feet = space.TransformPoint((float)peer.spaceX * scale, (float)peer.spaceZ * scale, (float)peer.spaceY * scale);
            Vector3 position = feet;
            position.y += player.GetComponent<CharacterController>().height / 2f + IndoorFootClearance;

            // Daggerfall would start its swimming and drowning rules from this height. Doom owns water now.
            PlayerEnterExit enter = game.PlayerEnterExit;
            if (enter.IsPlayerInsideDungeon)
            {
                if (testSink != 0)
                    SinkIntoWater(enter, space, ref position);
                DFLocation.DungeonBlock block;
                int index = enter.Dungeon.GetPlayerBlockIndex(position);
                if (testSink != 2 && index >= 0 && enter.Dungeon.GetBlockData(index, out block) && block.WaterLevel != 10000)
                    position.y = Mathf.Max(position.y, (-block.WaterLevel - 50) * scale + 0.95f + 0.01f);
            }

            if (indoorLandingPending)
            {
                indoorLandingPending = false;
                Vector3 landing = space.InverseTransformPoint(player.position);
                string marker = "";
                if (enter.IsPlayerInsideDungeon && enter.Dungeon.StartMarker)
                {
                    Vector3 start = space.InverseTransformPoint(enter.Dungeon.StartMarker.transform.position);
                    marker = string.Format(", Doom is {0:F1} units from Daggerfall's start marker", Distance(start.x / scale - peer.spaceX, start.z / scale - peer.spaceY));
                }
                bridge.LogLine(string.Format("sync indoor: Daggerfall landing is {0:F1} units from Doom's, target {1}{2}",
                    Distance(landing.x / scale - peer.spaceX, landing.z / scale - peer.spaceY), peer.spaceTarget, marker));
            }
            player.position = position;
            player.rotation = space.rotation * Quaternion.Euler(0, 90f - peer.spaceYaw, 0);
            applies++;
            indoorStats.AddApply(System.Diagnostics.Stopwatch.GetTimestamp() - applyStart);
            return true;
        }

        // Test only: floods the player's block in memory and aims the move deep under it, to prove the water guard works.
        void SinkIntoWater(PlayerEnterExit enter, Transform space, ref Vector3 position)
        {
            const short TestWaterLevel = 100;
            int index = enter.Dungeon.GetPlayerBlockIndex(position);
            if (index < 0)
                return;
            enter.Dungeon.Summary.LocationData.Dungeon.Blocks[index].WaterLevel = TestWaterLevel;
            enter.blockWaterLevel = TestWaterLevel;
            testWaterBlocks = true;
            position.y = (-TestWaterLevel - 400) * MeshReader.GlobalScale;
        }

        void MeasureIndoor(GameManager game, ref DfbUzState peer)
        {
            sawSwimming |= game.PlayerEnterExit.IsPlayerSwimming;
            sawSubmerged |= game.PlayerEnterExit.IsPlayerSubmerged;
            if (!bridge.LogEnabled || indoorLandingPending || testSink != 0)
                return;
            Transform space = IndoorSpace(game, ref peer);
            if (!space)
                return;
            Vector3 local = space.InverseTransformPoint(game.PlayerObject.transform.position);
            indoorStats.AddFrame(Distance(local.x / MeshReader.GlobalScale - peer.spaceX, local.z / MeshReader.GlobalScale - peer.spaceY), Time.unscaledDeltaTime);
        }

        // Stops what would let the moved player act on the world. Effects such as poison keep running.
        void Engage(GameManager game)
        {
            if (engaged)
                return;
            engaged = true;
            savedDisableAI = game.DisableAI;
            CharacterController controller = game.PlayerObject.GetComponent<CharacterController>();
            savedController = controller.enabled;
            savedMotor = game.PlayerMotor.enabled;
            savedLook = game.PlayerMouseLook.enabled;
            savedActivate = game.PlayerActivate.enabled;
            savedWeapons = game.WeaponManager.enabled;
            PlayerFootsteps footsteps = game.PlayerObject.GetComponent<PlayerFootsteps>();
            savedFootsteps = footsteps && footsteps.enabled;
            if (footsteps) footsteps.enabled = false; // Doom plays the player's sounds, and these moves are not steps.
            controller.enabled = false;
            game.PlayerMotor.enabled = false;
            game.PlayerMouseLook.enabled = false;
            game.PlayerActivate.enabled = false;
            game.WeaponManager.enabled = false;
            game.AcrobatMotor.ClearFallingDamage();
            bridge.LogLine("sync: engaged, hidden player stopped" + (noDraw ? ", 3D drawing off" : ""));
        }

        // Test only: renders what the main camera would show, which works while the window is minimized.
        void CaptureTestImage(GameManager game)
        {
            testImageTaken = true;
            const int width = 320, height = 180;
            Camera main = game.MainCamera;
            RenderTexture target = RenderTexture.GetTemporary(width, height, 24);
            RenderTexture previousTarget = main.targetTexture, previousActive = RenderTexture.active;
            main.targetTexture = target;
            main.Render();
            main.targetTexture = previousTarget;
            RenderTexture.active = target;
            var image = new Texture2D(width, height, TextureFormat.RGB24, false);
            image.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            RenderTexture.active = previousActive;
            RenderTexture.ReleaseTemporary(target);

            int lit = 0;
            Color32[] pixels = image.GetPixels32();
            foreach (Color32 pixel in pixels)
                if (pixel.r > 8 || pixel.g > 8 || pixel.b > 8)
                    lit++;
            bridge.LogLine(string.Format("sync test: main camera image {0:F1}% non-black, culling mask {1}, enabled cameras {2}",
                100f * lit / pixels.Length, main.cullingMask, Camera.allCamerasCount));
            Destroy(image);
        }

        // Test only: a hostile enemy beside the player, which must neither move nor attack.
        void SpawnTestEnemy(GameManager game)
        {
            testEnemySpawned = true;
            Transform player = game.PlayerObject.transform;
            testEnemy = GameObjectHelper.CreateEnemy("SyncTestEnemy", MobileTypes.Rat, player.position + player.forward * 3f,
                MobileGender.Unspecified, game.StreamingWorld.StreamingTarget.transform);
            testEnemyStart = testEnemy.transform.position; // World space: its parent can be re-based while it stands still.
            bridge.LogLine("sync test: hostile enemy placed 3 m from the player");
        }

        void Release()
        {
            if (!engaged)
                return;
            engaged = false;
            phase = (uint)(DoomerfallNewGame.HoldsNewCharacter ? Dfb.DF_PHASE_MENU : Dfb.DF_PHASE_BOOT); // Doom's title can start a new game.
            GameManager game = GameManager.Instance;
            game.DisableAI = savedDisableAI;
            game.PlayerObject.GetComponent<CharacterController>().enabled = savedController;
            game.PlayerMotor.enabled = savedMotor;
            game.PlayerMouseLook.enabled = savedLook;
            game.PlayerActivate.enabled = savedActivate;
            game.WeaponManager.enabled = savedWeapons;
            PlayerFootsteps footsteps = game.PlayerObject.GetComponent<PlayerFootsteps>();
            if (footsteps) footsteps.enabled = savedFootsteps;
            bridge.LogLine("sync: released");
        }

        // The main camera stays on with nothing to draw, so the 2D interface keeps rendering.
        static void HideWorld(GameManager game)
        {
            Camera main = game.MainCamera;
            foreach (Camera camera in Camera.allCameras)
                if (camera != main)
                    camera.enabled = false;
            main.cullingMask = 0;
            main.clearFlags = CameraClearFlags.SolidColor;
            main.backgroundColor = Color.black;
        }

        static double Distance(double x, double z)
        {
            return Math.Sqrt(x * x + z * z);
        }

        public void LogStatus()
        {
            if (!bridge.LogEnabled)
                return;
            GameManager game = GameManager.HasInstance ? GameManager.Instance : null;
            bool ready = game && game.IsReady && game.StreamingWorld;
            string enemy = "none";
            if (testEnemy)
            {
                Vector3 moved = testEnemy.transform.position - testEnemyStart;
                enemy = string.Format("{0:F3},{1:F3},{2:F3}", moved.x, moved.y, moved.z);
            }
            bridge.LogLine(string.Format(
                "sync engaged={0} nodraw={1} gps={2},{3} pixel={4},{5} applies={6} teleports={7} wrong_pixel_s={8:F2}/{9:F1} worst_wrong_pixel_s={18:F2} worst_apply_err={10:F2} worst_lag={11:F0} health={12}/{13} enemy_moved={14} mem_mb={15} all_frames={19} over_16ms={20} worst_frame_ms={21:F1} indoor_frames={22} frame {16} | area {17}",
                engaged, noDraw, ready ? game.PlayerGPS.WorldX : -1, ready ? game.PlayerGPS.WorldZ : -1,
                ready ? game.StreamingWorld.MapPixelX : -1, ready ? game.StreamingWorld.MapPixelY : -1,
                applies, teleports, mismatchTotal, alignedTime, worstApplyError, worstLag,
                ready && game.PlayerEntity != null ? game.PlayerEntity.CurrentHealth : -1, startHealth, enemy,
                GC.GetTotalMemory(false) / (1024 * 1024), frameMs.Summary(), areaLatency.Summary(), worstMismatch, alignedFrames, slowFrames, worstFrame * 1000f, indoorFrames));
            bridge.LogLine("syncstat hz=" + (1000000000L / applyIntervalNs) + " outdoor " + outdoorStats.Summary() + " | indoor " + indoorStats.Summary() +
                " | water test=" + testSink + " flooded_block=" + testWaterBlocks + " saw_swimming=" + sawSwimming + " saw_submerged=" + sawSubmerged);
        }

        // Whole-run position error and cost. The error is how far Daggerfall is behind Doom on each frame.
        sealed class SyncStats
        {
            const double BucketUnits = 4;
            readonly int[] buckets = new int[4096];
            long frames, applies, applyTicks, maxApplyTicks;
            double errorSum, errorMax, frameSeconds, frameMax;

            public void AddFrame(double error, float seconds)
            {
                frames++;
                errorSum += error;
                errorMax = Math.Max(errorMax, error);
                frameSeconds += seconds;
                frameMax = Math.Max(frameMax, seconds);
                buckets[Math.Min((int)(error / BucketUnits), buckets.Length - 1)]++;
            }

            public void AddApply(long ticks)
            {
                applies++;
                applyTicks += ticks;
                maxApplyTicks = Math.Max(maxApplyTicks, ticks);
            }

            double Percentile(double fraction)
            {
                long wanted = (long)(frames * fraction), seen = 0;
                for (int i = 0; i < buckets.Length; i++)
                {
                    seen += buckets[i];
                    if (seen > wanted)
                        return (i + 1) * BucketUnits;
                }
                return errorMax;
            }

            public string Summary()
            {
                double tickMs = 1000.0 / System.Diagnostics.Stopwatch.Frequency;
                return string.Format(System.Globalization.CultureInfo.InvariantCulture,
                    "frames={0} err_mean={1:F1} err_p95={2:F0} err_max={3:F0} frame_mean_ms={4:F3} frame_max_ms={5:F1} applies={6} apply_mean_us={7:F1} apply_max_ms={8:F2} apply_share={9:F4}%",
                    frames, frames > 0 ? errorSum / frames : 0, Percentile(0.95), errorMax, frames > 0 ? frameSeconds * 1000 / frames : 0, frameMax * 1000,
                    applies, applies > 0 ? applyTicks * tickMs * 1000 / applies : 0, maxApplyTicks * tickMs,
                    frameSeconds > 0 ? applyTicks * tickMs / (frameSeconds * 1000) * 100 : 0);
            }
        }
    }
}
