// Doomerfall: keeps the hidden Daggerfall player in the same exterior area as the Doom player, so the
// world objects Doom asks about are loaded. This is not a matching simulation.
//
// UZDoom publishes Daggerfall world units (doom / 0.75 + window origin). Position is applied about once
// per second. An area change is applied as soon as its event arrives.
//
// Only active in a bridge session, and only while Doom reports the Daggerfall exterior.

using System;
using System.Collections;
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
        const uint WorldNone = 0, WorldExterior = 1, WorldInterior = 2, WorldDungeon = 3;
        const uint PhaseBoot = 0, PhasePlay = 3;
        const long ApplyIntervalNs = 1000000000;
        const int TeleportPixels = 2; // Farther than this, streaming would have nothing loaded at the target.
        const int GameSceneIndex = 1;
        const int TestStartPixelX = 207, TestStartPixelY = 213;

        DoomerfallBridge bridge;
        bool engaged, savedDisableAI, savedMotor, savedController, savedLook, savedActivate, savedWeapons;
        bool areaDirty, areaPending, verifyPending, noDraw, testWorldReady, testEnemySpawned, testImageTaken;
        uint phase = PhaseBoot;
        int areaX, areaY, targetX, targetZ, teleports, applies;
        bool aligned;
        float mismatchStreak, mismatchTotal, worstMismatch, alignedTime, worstFrame;
        int slowFrames, alignedFrames;
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

        // True once the test start has put Daggerfall in a game. The real startup flow replaces this.
        public bool InGame { get { return testWorldReady; } }

        public void Init(DoomerfallBridge owner, string[] args)
        {
            bridge = owner;
            noDraw = Array.IndexOf(args, "-dfnodraw") >= 0;
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
            startHealth = player.CurrentHealth;
            testWorldReady = true;
            bridge.LogLine("sync test: entered the world, health " + startHealth);
        }

        public void OnAreaEvent(uint context, int pixelX, int pixelY, long sentNs)
        {
            if (context != WorldExterior)
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

            switch (peer.worldContext)
            {
                case WorldExterior:
                    break;
                case WorldInterior:
                case WorldDungeon:
                    return; // Reserved: the building and dungeon transition task moves Daggerfall indoors.
                case WorldNone:
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
            if (!world || !world.isActiveAndEnabled || world.suppressWorld || game.PlayerEnterExit.IsPlayerInside)
                return;

            Engage(game);
            game.DisableAI = !testEnemyAI;
            game.PlayerEntity.PreventEnemySpawns = true; // Cleared by PlayerEntity after each update.

            long nowNs = DfbNative.dfb_now_ns();
            if (noDraw && nowNs >= nextCameraCheckNs)
            {
                nextCameraCheckNs = nowNs + ApplyIntervalNs;
                HideWorld(game);
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
            }

            if (!world.DoomerfallPositionSettled)
                return;
            phase = PhasePlay;

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
            nextApplyNs = nowNs + ApplyIntervalNs;
            Apply(game, world, gps, ref peer);
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
            phase = PhaseBoot;
            GameManager game = GameManager.Instance;
            game.DisableAI = savedDisableAI;
            game.PlayerObject.GetComponent<CharacterController>().enabled = savedController;
            game.PlayerMotor.enabled = savedMotor;
            game.PlayerMouseLook.enabled = savedLook;
            game.PlayerActivate.enabled = savedActivate;
            game.WeaponManager.enabled = savedWeapons;
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
                "sync engaged={0} nodraw={1} gps={2},{3} pixel={4},{5} applies={6} teleports={7} wrong_pixel_s={8:F2}/{9:F1} worst_wrong_pixel_s={18:F2} worst_apply_err={10:F2} worst_lag={11:F0} health={12}/{13} enemy_moved={14} mem_mb={15} all_frames={19} over_16ms={20} worst_frame_ms={21:F1} frame {16} | area {17}",
                engaged, noDraw, ready ? game.PlayerGPS.WorldX : -1, ready ? game.PlayerGPS.WorldZ : -1,
                ready ? game.StreamingWorld.MapPixelX : -1, ready ? game.StreamingWorld.MapPixelY : -1,
                applies, teleports, mismatchTotal, alignedTime, worstApplyError, worstLag,
                ready && game.PlayerEntity != null ? game.PlayerEntity.CurrentHealth : -1, startHealth, enemy,
                GC.GetTotalMemory(false) / (1024 * 1024), frameMs.Summary(), areaLatency.Summary(), worstMismatch, alignedFrames, slowFrames, worstFrame * 1000f));
        }
    }
}
