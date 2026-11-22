// DoomDaggerfall test tool: captures dungeon viewpoints for comparison with the converted UZDoom map.
// Inactive unless the player is started with -dfcapture <job file>, and refuses to run outside a portable install.
// See tools/dungeon_compare/README.md.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game
{
    public class DungeonCaptureTest : MonoBehaviour
    {
        const int GameSceneIndex = 1;
        const int SettleFrames = 30;
        const float ProbeRange = 4096f;

        struct View { public string Id; public float X, Y, Z, Yaw, Pitch; }

        string dungeonName, outDir, daggerfallPath;
        int width = 960, height = 720;
        float verticalFov = 73.74f;
        readonly List<View> views = new List<View>();
        readonly StringBuilder results = new StringBuilder();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Activate()
        {
            string[] args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "-dfcapture");
            if (index < 0)
                return;
            if (!DaggerfallUnityApplication.IsPortableInstall || index + 1 >= args.Length)
            {
                Debug.LogError("DFCAPTURE refused: needs a portable install and a job file.");
                Application.Quit(2);
                return;
            }
            var host = new GameObject("DungeonCaptureTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DungeonCaptureTest>().ReadJob(args[index + 1]);
        }

        void ReadJob(string path)
        {
            foreach (string line in File.ReadAllLines(path))
            {
                string[] p = line.Split('\t');
                switch (p[0])
                {
                    case "dungeon": dungeonName = p[1]; break;
                    case "out": outDir = p[1]; break;
                    case "daggerfall": daggerfallPath = p[1]; break;
                    case "size": width = int.Parse(p[1]); height = int.Parse(p[2]); break;
                    case "vfov": verticalFov = Number(p[1]); break;
                    case "view":
                        views.Add(new View { Id = p[1], X = Number(p[2]), Y = Number(p[3]), Z = Number(p[4]), Yaw = Number(p[5]), Pitch = Number(p[6]) });
                        break;
                }
            }
        }

        static float Number(string text)
        {
            return float.Parse(text, CultureInfo.InvariantCulture);
        }

        IEnumerator Start()
        {
            // These settings stay in memory. The portable install keeps anything Unity writes away from the owner's data.
            var settings = DaggerfallUnity.Settings;
            settings.MyDaggerfallPath = daggerfallPath;
            settings.Fullscreen = false;
            settings.ExclusiveFullscreen = false;
            settings.ResolutionWidth = width;
            settings.ResolutionHeight = height;
            settings.RunInBackground = true;
            settings.SoundVolume = 0;
            settings.MusicVolume = 0;
            Application.runInBackground = true;

            yield return SceneManager.LoadSceneAsync(GameSceneIndex);
            while (!DaggerfallUnity.Instance.IsReady || !GameManager.Instance.IsReady)
                yield return null;

            var start = FindObjectOfType<StartGameBehaviour>();
            start.EnableVideos = false;
            start.StartMethod = StartGameBehaviour.StartMethods.Void;
            yield return WaitFrames(5);
            DaggerfallUI.Instance.PopToHUD();

            DFLocation location;
            if (!FindDungeon(out location))
            {
                Finish("ERROR dungeon not found: " + dungeonName, 3);
                yield break;
            }
            var enterExit = GameManager.Instance.PlayerEnterExit;
            enterExit.StartDungeonInterior(location, false, false);
            GameManager.Instance.PauseGame(false);
            yield return WaitFrames(SettleFrames);

            DaggerfallDungeon dungeon = enterExit.Dungeon;
            if (!dungeon)
            {
                Finish("ERROR dungeon did not load", 3);
                yield break;
            }

            // Stop everything that could move the player or the view between captures.
            GameObject player = GameManager.Instance.PlayerObject;
            player.GetComponent<CharacterController>().enabled = false;
            GameManager.Instance.PlayerMotor.enabled = false;
            GameManager.Instance.PlayerMouseLook.enabled = false;

            // Flat light, so geometry can be compared instead of Daggerfall's dark torch lighting.
            RenderSettings.fog = false;
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = Color.white;

            Camera main = GameManager.Instance.MainCamera;
            var cameraObject = new GameObject("CaptureCamera");
            Camera camera = cameraObject.AddComponent<Camera>();
            camera.cullingMask = main.cullingMask;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = Color.magenta;
            camera.fieldOfView = verticalFov;
            camera.nearClipPlane = 0.02f;
            camera.farClipPlane = 300f;
            camera.enabled = false;

            Transform root = dungeon.transform;
            results.AppendFormat(CultureInfo.InvariantCulture, "ROOT {0} {1} {2} scale {3}\n",
                root.position.x, root.position.y, root.position.z, MeshReader.GlobalScale);

            foreach (View view in views)
            {
                Vector3 eye = root.TransformPoint(new Vector3(view.X, view.Z, view.Y) * MeshReader.GlobalScale);
                player.transform.position = eye;
                cameraObject.transform.position = eye;
                cameraObject.transform.rotation = Quaternion.Euler(view.Pitch, 90f - view.Yaw, 0);
                yield return WaitFrames(SettleFrames);
                yield return new WaitForEndOfFrame();
                SavePng(camera, Path.Combine(outDir, view.Id + ".df.png"));
                results.Append(Probe(view.Id, eye));
            }
            Finish("DONE", 0);
        }

        static IEnumerator WaitFrames(int count)
        {
            for (int i = 0; i < count; i++)
                yield return null;
        }

        bool FindDungeon(out DFLocation location)
        {
            MapsFile maps = DaggerfallUnity.Instance.ContentReader.MapFileReader;
            for (int r = 0; r < maps.RegionCount; r++)
            {
                DFRegion region = maps.GetRegion(r);
                if (region.MapNames == null)
                    continue;
                int index = Array.IndexOf(region.MapNames, dungeonName);
                if (index < 0)
                    continue;
                location = maps.GetLocation(r, index);
                if (location.HasDungeon)
                    return true;
            }
            location = new DFLocation();
            return false;
        }

        void SavePng(Camera camera, string path)
        {
            var target = RenderTexture.GetTemporary(width, height, 24, RenderTextureFormat.ARGB32);
            var image = new Texture2D(width, height, TextureFormat.RGB24, false);
            RenderTexture previous = RenderTexture.active;
            camera.targetTexture = target;
            camera.Render();
            RenderTexture.active = target;
            image.ReadPixels(new Rect(0, 0, width, height), 0, 0);
            image.Apply();
            camera.targetTexture = null;
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            File.WriteAllBytes(path, image.EncodeToPNG());
            Destroy(image);
        }

        // Distances in Daggerfall units from the eye: down, up, then Doom east, north, west, south. -1 means no hit.
        static string Probe(string id, Vector3 eye)
        {
            Vector3[] directions = { Vector3.down, Vector3.up, Vector3.right, Vector3.forward, Vector3.left, Vector3.back };
            var line = new StringBuilder("PROBE " + id);
            foreach (Vector3 direction in directions)
            {
                RaycastHit hit;
                bool found = Physics.Raycast(eye, direction, out hit, ProbeRange * MeshReader.GlobalScale, ~0, QueryTriggerInteraction.Ignore);
                line.Append(' ').Append((found ? hit.distance / MeshReader.GlobalScale : -1f).ToString("F1", CultureInfo.InvariantCulture));
            }
            return line.Append('\n').ToString();
        }

        void Finish(string status, int exitCode)
        {
            results.Append(status).Append('\n');
            File.WriteAllText(Path.Combine(outDir, "df_probes.txt"), results.ToString());
            Application.Quit(exitCode);
        }
    }
}
