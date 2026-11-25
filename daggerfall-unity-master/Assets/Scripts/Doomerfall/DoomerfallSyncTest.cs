// Doomerfall test only (-dfsynctest <Daggerfall folder>, portable installs only): the town start most paired tests use.
// It skips Daggerfall's start menus and puts a blank 100 HP character in the test town (map pixel 207,213). Once
// position sync has aligned, it places a hostile rat beside the player, which must neither move nor attack, and checks
// that the main camera still renders. DoomerfallPositionSync reports the rat and the start health in its status line.
//   -dfsynctestenemyai   negative control: leaves enemy AI on, to prove the test can see an attack.
//   -dfinventorytest     also gives the character a longsword and a dagger to equip and move.

using System;
using System.Collections;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallSyncTest : MonoBehaviour
    {
        const int GameSceneIndex = 1;
        const int TestStartPixelX = 207, TestStartPixelY = 213;

        DoomerfallBridge bridge;
        bool enemySpawned, imageTaken;
        GameObject enemy;
        Vector3 enemyStart;

        internal bool WorldReady { get; private set; }
        internal bool EnemyAI { get; private set; }
        internal int StartHealth { get; private set; } = -1;

        // Null without -dfsynctest.
        internal static DoomerfallSyncTest Attach(DoomerfallBridge owner, GameObject host, string[] args)
        {
            int test = Array.IndexOf(args, "-dfsynctest");
            if (test < 0)
                return null;
            if (!DaggerfallUnityApplication.IsPortableInstall || test + 1 >= args.Length)
            {
                owner.LogLine("error: -dfsynctest needs a portable install and a Daggerfall path");
                return null;
            }
            var syncTest = host.AddComponent<DoomerfallSyncTest>();
            syncTest.bridge = owner;
            syncTest.EnemyAI = Array.IndexOf(args, "-dfsynctestenemyai") >= 0;
            syncTest.StartCoroutine(syncTest.TestStart(args[test + 1]));
            return syncTest;
        }

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
                player.Items.AddItem(ItemBuilder.CreateWeapon(Weapons.Longsword, WeaponMaterialTypes.Iron));
                player.Items.AddItem(ItemBuilder.CreateWeapon(Weapons.Dagger, WeaponMaterialTypes.Steel));
            }
            StartHealth = player.CurrentHealth;
            WorldReady = true;
            bridge.LogLine("sync test: entered the world, health " + StartHealth);
        }

        // DoomerfallPositionSync, each exterior frame while engaged.
        internal void Frame(GameManager game, bool aligned, float alignedTime)
        {
            // After the first teleport, because a teleport clears loose enemies.
            if (WorldReady && !enemySpawned && aligned)
                SpawnEnemy(game);
            if (WorldReady && !imageTaken && alignedTime > 3f)
                CaptureImage(game);
        }

        // How far the rat has moved since it was placed, for the status line.
        internal string EnemyMoved()
        {
            if (!enemy)
                return "none";
            Vector3 moved = enemy.transform.position - enemyStart;
            return string.Format("{0:F3},{1:F3},{2:F3}", moved.x, moved.y, moved.z);
        }

        // Renders what the main camera would show, which works while the window is minimized.
        void CaptureImage(GameManager game)
        {
            imageTaken = true;
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

        // A hostile enemy beside the player, which must neither move nor attack.
        void SpawnEnemy(GameManager game)
        {
            enemySpawned = true;
            Transform player = game.PlayerObject.transform;
            enemy = GameObjectHelper.CreateEnemy("SyncTestEnemy", MobileTypes.Rat, player.position + player.forward * 3f,
                MobileGender.Unspecified, game.StreamingWorld.StreamingTarget.transform);
            enemyStart = enemy.transform.position; // World space: its parent can be re-based while it stands still.
            bridge.LogLine("sync test: hostile enemy placed 3 m from the player");
        }
    }
}
