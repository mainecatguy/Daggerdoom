// Doomerfall: loading a plain Daggerfall save, one with no Doom half, from Daggerfall's own Load window shown inside Doom
// (DFB_UI_LOAD_GAME, opened by Doom's dd_load_daggerfall at its title). The bundled save's load (DoomerfallSave) is a
// separate path and never comes here.
//
// The loaded game is held (paused, position sync off) while Doom starts its default class through the New Game chain
// and goes to the saved place (DFB_KIND_PLAIN_LOAD). When Doom arrives, Daggerfall resumes the save as it was, with no
// new quests or clock start, and gives the starting weapon (DoomerfallHotkeys.BeginPlainStart, the owner's rules of
// 2026-11-24). Daggerfall's ammo stacks win over Doom's new-game counter (DoomerfallAmmo.PreferDaggerfall).

using System;
using System.Collections;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallPlainLoad : MonoBehaviour
    {
        const float SettleSeconds = 20f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        string testSave; // Test only (-dfplainloadtest <save name>): loads this save when the window opens.
        bool armed, holding;
        string starterClass = "";
        int starterSlot = -1, starterAmmoType = -1, starterAmmo;

        internal DoomerfallItems Items { get; set; }
        internal DoomerfallMonsters Monsters { get; set; }
        internal DoomerfallTownspeople Townspeople { get; set; }
        internal DoomerfallHotkeys Hotkeys { get; set; }
        internal DoomerfallAmmo Ammo { get; set; }

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, string[] args)
        {
            bridge = owner;
            sync = positionSync;
            int test = Array.IndexOf(args, "-dfplainloadtest");
            if (test >= 0 && test + 1 < args.Length)
                testSave = args[test + 1];
            SaveLoadManager.OnLoad += OnLoad;
        }

        void OnDestroy()
        {
            SaveLoadManager.OnLoad -= OnLoad;
        }

        // DoomerfallUi: Daggerfall's Load window is showing in Doom.
        internal void WindowOpened()
        {
            if (testSave != null)
                StartCoroutine(TestLoad(testSave));
        }

        // Test only: picks the named save as the player would in the window.
        IEnumerator TestLoad(string saveName)
        {
            yield return new WaitForSecondsRealtime(1f);
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            saves.EnumerateSaves();
            foreach (string character in saves.GetCharacterNames())
                if (saves.FindSaveFolderByNames(character, saveName) >= 0)
                {
                    bridge.LogLine("plain load test: loading \"" + saveName + "\" of " + character);
                    saves.Load(character, saveName);
                    DaggerfallUI.Instance.PopToHUD();
                    yield break;
                }
            bridge.LogLine("plain load test: no save named \"" + saveName + "\"");
        }

        // DoomerfallUi: the Load window closed while the save chosen in it is loading.
        internal void Arm()
        {
            armed = true;
            sync.LoadRunning = true;
            // As New Game: the previous game's world lists must not carry into this one. A plain save has no ledgers.
            Items.ForgetWorld();
            Monsters.ForgetWorld();
            if (Townspeople != null)
                Townspeople.ForgetWorld();
            bridge.LogLine("plain load: loading a Daggerfall save with no Doom data");
        }

        void OnLoad(SaveData_v1 data)
        {
            if (!armed)
                return;
            armed = false;
            holding = true;
            starterClass = "";
            starterSlot = starterAmmoType = -1;
            starterAmmo = 0;
            sync.LoadRunning = true; // Daggerfall must not follow Doom until Doom has reached the saved place.
            GameManager.Instance.DisableAI = true;
            GameManager.Instance.PauseGame(true);
            StartCoroutine(SendPlace());
        }

        IEnumerator SendPlace()
        {
            GameManager game = GameManager.Instance;
            float deadline = Time.unscaledTime + SettleSeconds;
            while ((game.PlayerEnterExit.IsRespawning || game.SaveLoadManager.LoadInProgress) && Time.unscaledTime < deadline)
                yield return null;
            yield return null;
            yield return null;

            PlayerEnterExit enter = game.PlayerEnterExit;
            PlayerGPS gps = game.PlayerGPS;
            Transform player = game.PlayerObject.transform;
            float scale = MeshReader.GlobalScale;
            var place = new DfbPlainLoad { worldX = gps.WorldX, worldZ = gps.WorldZ, dungeonMapId = -1, startX = float.NaN, startY = float.NaN, startZ = float.NaN };
            place.yawDegrees = Mathf.Repeat(90f - player.eulerAngles.y, 360f);
            string where;
            Transform space = null;
            if (enter.IsPlayerInsideDungeon && enter.Dungeon)
            {
                place.context = Dfb.WORLD_DUNGEON;
                DFPosition pixel = gps.CurrentMapPixel;
                DFPosition origin = MapsFile.MapPixelToWorldCoord(pixel.X, pixel.Y);
                place.worldX = origin.X + MapsFile.WorldMapTerrainDim / 2; // As New Game: Doom goes in through the location's door.
                place.worldZ = origin.Y + MapsFile.WorldMapTerrainDim / 2;
                place.dungeonMapId = gps.CurrentLocation.MapTableData.MapId;
                space = enter.Dungeon.transform;
                where = "dungeon " + gps.CurrentLocation.Name;
            }
            else if (enter.IsPlayerInside && enter.Interior)
            {
                place.context = Dfb.WORLD_INTERIOR;
                space = enter.Interior.transform;
                where = "building " + enter.BuildingDiscoveryData.buildingKey + " in " + gps.CurrentLocation.Name;
                // The building's door, in world units: its scene position relative to the player, as DoomerfallTransition finds doors.
                StaticDoor[] doors = enter.ExteriorDoors;
                if (doors != null && doors.Length > 0)
                {
                    Vector3 at = DaggerfallStaticDoors.GetDoorPosition(doors[0]);
                    place.worldX = gps.WorldX + (at.x - player.position.x) * StreamingWorld.SceneMapRatio;
                    place.worldZ = gps.WorldZ + (at.z - player.position.z) * StreamingWorld.SceneMapRatio;
                    where += string.Format(", door at {0:F0},{1:F0} ({2:F0} units from the player's world position)", place.worldX, place.worldZ,
                        Math.Sqrt((place.worldX - gps.WorldX) * (place.worldX - gps.WorldX) + (place.worldZ - gps.WorldZ) * (place.worldZ - gps.WorldZ)));
                }
                else
                    where += ", no exterior door recorded, using the player's world position";
            }
            else
            {
                place.context = Dfb.WORLD_EXTERIOR;
                where = "outdoors";
            }
            if (space)
            {
                // The player's feet in the space, in Doom's space coordinates (DoomerfallPositionSync.ApplyIndoor inverted).
                CharacterController controller = player.GetComponent<CharacterController>();
                Vector3 feet = player.position - new Vector3(0, controller ? controller.height / 2f : 0, 0);
                Vector3 local = space.InverseTransformPoint(feet);
                place.startX = local.x / scale;
                place.startY = local.z / scale;
                place.startZ = local.y / scale;
                float relative = (Quaternion.Inverse(space.rotation) * player.rotation).eulerAngles.y;
                place.startYaw = Mathf.Repeat(90f - relative, 360f);
            }
            var e = new DfbEvent { kind = Dfb.KIND_PLAIN_LOAD, tic = (uint)Time.frameCount, plainLoad = place };
            bridge.Send(ref e);
            bridge.LogLine(string.Format("plain load: {0} held in {1}, world {2},{3} yaw {4:F0}, space start {5:F1},{6:F1},{7:F1} yaw {8:F0}, health {9}/{10}, {11} items",
                game.PlayerEntity.Name, where, gps.WorldX, gps.WorldZ, place.yawDegrees, place.startX, place.startY, place.startZ, place.startYaw,
                game.PlayerEntity.CurrentHealth, game.PlayerEntity.MaxHealth, game.PlayerEntity.Items.Count));
        }

        // DFB_KIND_STARTER, sent by Doom just before it arrives.
        internal void OnStarter(uint request, uint amount, string cls)
        {
            starterClass = cls ?? "";
            starterSlot = (int)(request & 0xff) == 0xff ? -1 : (int)(request & 0xff);
            starterAmmoType = (int)(request >> 8) - 1;
            starterAmmo = (int)amount;
            bridge.LogLine(string.Format("plain load: Doom's starter gun is \"{0}\" (slot {1}), {2} of ammo type {3}", starterClass, starterSlot, starterAmmo, starterAmmoType));
        }

        // DFB_KIND_NEWGAME_ARRIVED. False when this was not a plain load, so New Game takes it.
        internal bool OnArrived(bool ok)
        {
            if (!holding)
                return false;
            holding = false;
            if (!ok)
            {
                sync.LoadRunning = false;
                bridge.LogLine("plain load: Doom could not reach the saved place; Daggerfall stays held behind Doom's title");
                return true;
            }
            Ammo.PreferDaggerfall();
            Hotkeys.BeginPlainStart(starterClass, starterSlot, starterAmmoType, starterAmmo);
            sync.LoadRunning = false;
            GameManager.Instance.PauseGame(false);
            bridge.LogLine("plain load: both games running, paused " + GameManager.IsGamePaused + ", Doom items " + DoomerfallHotkeys.DoomItemList(GameManager.Instance.PlayerEntity.Items));
            var e = new DfbEvent { kind = Dfb.KIND_NEWGAME_GO, tic = (uint)Time.frameCount };
            bridge.Send(ref e);
            return true;
        }
    }
}
