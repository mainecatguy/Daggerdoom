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
        bool holding;

        /// <summary>True in a flow session. StartGameBehaviour then waits for Doom before starting the game.</summary>
        public static bool HoldsNewCharacter { get { return instance != null; } }

        /// <summary>Daggerfall's enemies stay out of a Doomerfall start, because Doom owns the monsters.</summary>
        public static bool ImportEnemies { get { return instance == null; } }

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
            AudioListener.volume = 1;
            start.EnableVideos = true;
            DaggerfallUI.Instance.enableVideos = true;
            // A previous character may have died. Its death state must not carry into the new one.
            if (GameManager.Instance.PlayerDeath)
                GameManager.Instance.PlayerDeath.ResetCamera();
            DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiStartNewGameWizard);
        }

        internal void CreationClosed(bool characterMade)
        {
            if (!characterMade)
                AudioListener.volume = 0;
        }

        /// <summary>StartNewCharacter calls this in place of starting the clock and quests.</summary>
        public static void CharacterPlaced()
        {
            if (instance == null)
                return;
            instance.holding = true;
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
                },
            };
            bridge.Send(ref e);
            bridge.LogLine(string.Format("new game: {0} held at pixel {1},{2}, {3}, health {4}/{5}", game.PlayerEntity.Name, pixelX, pixelY,
                dungeon ? "dungeon " + gps.CurrentLocation.Name : "outdoors", game.PlayerEntity.CurrentHealth, game.PlayerEntity.MaxHealth));
        }

        internal void OnArrived(bool ok)
        {
            if (!holding)
                return;
            holding = false;
            if (!ok)
            {
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
