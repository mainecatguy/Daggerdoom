// Doomerfall: Daggerfall's side of New Game (-dfflow <Daggerfall folder>). Daggerfall waits without a game
// behind Doom's title. Its real character creation and cinematics show inside Doom. A finished character is
// held, with quests and the clock stopped, until Doom says it has arrived in the same place.

using System;
using System.Collections;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public sealed class DoomerfallNewGame : MonoBehaviour
    {
        const int GameSceneIndex = 1;
        const float PlaceSeconds = 15f;

        static DoomerfallNewGame instance;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        StartGameBehaviour start;
        internal DoomerfallItems Items { get; set; }
        internal DoomerfallMonsters Monsters { get; set; }
        internal DoomerfallLocations Locations { get; set; }
        internal DoomerfallTownspeople Townspeople { get; set; }
        bool holding;

        /// <summary>True in a flow session. StartGameBehaviour then waits for Doom before starting the game.</summary>
        public static bool HoldsNewCharacter { get { return instance != null; } }

        /// <summary>Daggerfall's enemies stay out of a Doomerfall start, because Doom owns the monsters.</summary>
        public static bool ImportEnemies { get { return instance == null; } }

        /// <summary>Reflexes are not used in Doomerfall. A flow session skips the wizard's Reflexes step, locks the
        /// summary sheet's picker, and gives every new character this middle value ("Normal").</summary>
        public static bool FixedReflexes { get { return instance != null; } }
        public const Entity.PlayerReflexes NormalReflexes = Entity.PlayerReflexes.Average;

        internal static bool IsFlow(string[] args) { return Array.IndexOf(args, "-dfflow") >= 0; }

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, string[] args)
        {
            bridge = owner;
            sync = positionSync;
            int at = Array.IndexOf(args, "-dfflow");
            if (at < 0 || at + 1 >= args.Length)
                return;
            if (!DaggerfallUnityApplication.IsPortableInstall)
            {
                bridge.LogLine("error: -dfflow needs a portable install, so the player's own settings stay untouched");
                return;
            }
            instance = this;
            StartCoroutine(Boot(args[at + 1]));
        }

        IEnumerator Boot(string daggerfallPath)
        {
            var settings = DaggerfallUnity.Settings; // In memory only. The portable install keeps it private.
            settings.MyDaggerfallPath = daggerfallPath;
            settings.RunInBackground = true;
            Application.runInBackground = true;
            AudioListener.volume = 0; // Doom owns the sound except during character creation.

            yield return SceneManager.LoadSceneAsync(GameSceneIndex);
            while (!DaggerfallUnity.Instance.IsReady || !GameManager.Instance.IsReady)
                yield return null;

            start = FindObjectOfType<StartGameBehaviour>();
            start.EnableVideos = false; // Skips Daggerfall's title video. Doom shows the title.
            DaggerfallUI.Instance.enableVideos = false;
            for (int i = 0; i < 5; i++)
                yield return null;
            DaggerfallUI.Instance.PopToHUD();
            GameManager.Instance.PauseGame(true);
            sync.SetMenuPhase();
            bridge.LogLine("flow: Daggerfall is ready behind Doom's title");
        }

        /// <summary>Opens the real wizard, with its cinematics.</summary>
        internal void BeginCreation()
        {
            holding = false;
            bridge.Sheet.CreationStarted();
            Items.ForgetWorld();
            Monsters.ForgetWorld();
            if (Locations != null)
                Locations.ForgetWorld();
            if (Townspeople != null)
                Townspeople.ForgetWorld();
            AudioListener.volume = DoomerfallQuiet.Volume(1);
            start.EnableVideos = true;
            DaggerfallUI.Instance.enableVideos = true;
            // A previous character may have died. Its death state must not carry into the new one.
            if (GameManager.Instance.PlayerDeath)
                GameManager.Instance.PlayerDeath.ResetCamera();
            DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiStartNewGameWizard);
        }

        internal void CreationClosed(bool characterMade)
        {
            if (characterMade)
                return;
            AudioListener.volume = 0;
            bridge.Sheet.CreationCancelled();
        }

        /// <summary>StartNewCharacter calls this in place of starting the clock and quests.</summary>
        public static void CharacterPlaced()
        {
            if (instance == null)
                return;
            instance.holding = true;
            instance.bridge.Sheet.CharacterPlaced();
            AudioListener.volume = 0;
            DoomerfallUi.MarkResult();
            instance.StartCoroutine(instance.SendPlacement());
        }

        IEnumerator SendPlacement()
        {
            float deadline = Time.unscaledTime + PlaceSeconds;
            GameManager game = GameManager.Instance;
            while (game.PlayerEnterExit.IsRespawning && Time.unscaledTime < deadline)
                yield return null;
            yield return null;

            PlayerGPS gps = game.PlayerGPS;
            int pixelX = DaggerfallUnity.Settings.StartCellX, pixelY = DaggerfallUnity.Settings.StartCellY;
            DFPosition origin = MapsFile.MapPixelToWorldCoord(pixelX, pixelY);
            bool dungeon = game.PlayerEnterExit.IsPlayerInsideDungeon;
            // Not a number means no start point, so Doom keeps its map start, the entrance.
            Vector3 start = new Vector3(float.NaN, float.NaN, float.NaN);
            float startYaw = 90;
            string startNote = ", no start marker";
            if (dungeon)
                StartPoint(game, ref start, out startYaw, ref startNote);
            var e = new DfbEvent
            {
                kind = Dfb.KIND_NEWGAME,
                tic = (uint)Time.frameCount,
                newGame = new DfbNewGame
                {
                    // The middle of the start pixel. Doom then goes in through the location's real door.
                    worldX = origin.X + MapsFile.WorldMapTerrainDim / 2,
                    worldZ = origin.Y + MapsFile.WorldMapTerrainDim / 2,
                    yawDegrees = 0,
                    mapPixelX = pixelX,
                    mapPixelY = pixelY,
                    dungeonMapId = dungeon ? gps.CurrentLocation.MapTableData.MapId : -1,
                    startX = start.x,
                    startY = start.y,
                    startZ = start.z,
                    startYaw = startYaw,
                },
            };
            bridge.Send(ref e);
            bridge.LogLine(string.Format("new game: {0} held at pixel {1},{2}, {3}, health {4}/{5}, reflexes {6}{7}", game.PlayerEntity.Name, pixelX, pixelY,
                dungeon ? "dungeon " + gps.CurrentLocation.Name : "outdoors", game.PlayerEntity.CurrentHealth, game.PlayerEntity.MaxHealth,
                game.PlayerEntity.Reflexes, startNote));
        }

        // The marker StartDungeonInterior placed the new character at (StartGameBehaviour asks for the Enter marker
        // when the dungeon has one, else the Start marker), in Doom's space coordinates, and the facing it gave.
        static void StartPoint(GameManager game, ref Vector3 start, out float yaw, ref string note)
        {
            yaw = 90;
            DaggerfallDungeon dungeon = game.PlayerEnterExit.Dungeon;
            if (!dungeon)
                return;
            GameObject marker = dungeon.EnterMarker ? dungeon.EnterMarker : dungeon.StartMarker;
            if (!marker)
                return;
            float scale = MeshReader.GlobalScale;
            Vector3 local = dungeon.transform.InverseTransformPoint(marker.transform.position);
            start = new Vector3(local.x / scale, local.z / scale, local.y / scale);
            // Unity yaw 0 is north (+z, Doom's +y), turning clockwise; Doom yaw 90 is north, turning anticlockwise.
            yaw = Mathf.Repeat(90f - game.PlayerMouseLook.Yaw, 360f);
            Vector3 player = dungeon.transform.InverseTransformPoint(game.PlayerObject.transform.position);
            float apart = new Vector2(player.x - local.x, player.z - local.z).magnitude / scale;
            note = string.Format(", start {0} marker at {1:F1},{2:F1},{3:F1} yaw {4:F0}, hidden player {5:F1} units from it",
                marker == dungeon.EnterMarker ? "Enter" : "Start", start.x, start.y, start.z, yaw, apart);
        }

        internal void OnArrived(bool ok)
        {
            if (!holding)
                return;
            holding = false;
            if (!ok)
            {
                bridge.Sheet.CharacterDropped();
                bridge.LogLine("new game: Doom could not reach the start, the held character was dropped");
                return;
            }
            start.FinishNewCharacterStart();
            bridge.LogLine("new game: quests and clock started, paused " + GameManager.IsGamePaused);
            var e = new DfbEvent { kind = Dfb.KIND_NEWGAME_GO, tic = (uint)Time.frameCount };
            bridge.Send(ref e);
        }

        void OnDestroy()
        {
            if (instance == this)
                instance = null;
        }
    }
}
