// Doomerfall test tool: captures dungeon viewpoints for comparison with the converted UZDoom map.
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
    public partial class DungeonCaptureTest : MonoBehaviour
    {
        const int GameSceneIndex = 1;
        const int SettleFrames = 30;
        const float ProbeRange = 4096f;
        const float FloodCell = 16f;
        const float FloodStartLift = 8f;
        const float FloodJumpRise = 48f;
        const float FloodClearance = 20f; // body check starts above the feet, so ramps and steps do not count as obstacles
        const float FloodKnee = 30f;
        const float FloodBodyFit = 0.9f;
        const int FloodLimit = 400000;

        struct View { public string Id; public float X, Y, Z, Yaw, Pitch; }

        string dungeonName, outDir, daggerfallPath;
        int width = 960, height = 720;
        float verticalFov = 73.74f;
        bool hasFlood, lit, noNpcs;
        float floodX, floodY, floodFloor;
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
                    case "lit": lit = true; break;
                    case "nonpcs": noNpcs = true; break; // visual parity: hide the dungeon's NPC flats as well as its enemies
                    default: ReadMenuJob(p); break; // DungeonCaptureMenus.cs
                    case "flood": hasFlood = true; floodX = Number(p[1]); floodY = Number(p[2]); floodFloor = Number(p[3]); break;
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
            if (menus.Count > 0)
            {
                yield return RunMenus();
                yield break;
            }

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

            if (noNpcs)
                foreach (StaticNPC npc in dungeon.GetComponentsInChildren<StaticNPC>(true))
                    npc.gameObject.SetActive(false);

            // Stop everything that could move the player or the view between captures.
            GameObject player = GameManager.Instance.PlayerObject;
            player.GetComponent<CharacterController>().enabled = false;
            GameManager.Instance.PlayerMotor.enabled = false;
            GameManager.Instance.PlayerMouseLook.enabled = false;

            // Flat light, so geometry can be compared instead of Daggerfall's dark torch lighting. A "lit" job keeps the game's lights.
            if (!lit)
            {
                RenderSettings.fog = false;
                RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
                RenderSettings.ambientLight = Color.white;
            }

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

            if (hasFlood)
            {
                // Doors count as passable because the player can open them. Other moving objects stay at their start position.
                foreach (DaggerfallActionDoor door in dungeon.GetComponentsInChildren<DaggerfallActionDoor>(true))
                    foreach (Collider collider in door.GetComponentsInChildren<Collider>(true))
                        collider.enabled = false;
                Physics.SyncTransforms();
                CharacterController controller = player.GetComponent<CharacterController>();
                float walkRise = Mathf.Max(controller.stepOffset / MeshReader.GlobalScale, FloodCell);
                results.AppendFormat(CultureInfo.InvariantCulture, "FLOODBODY radius {0:F1} height {1:F1} step {2:F1} slope {3:F0} walkrise {4:F1}\n",
                    controller.radius / MeshReader.GlobalScale, controller.height / MeshReader.GlobalScale,
                    controller.stepOffset / MeshReader.GlobalScale, controller.slopeLimit, walkRise);
                float radius = controller.radius, bodyHeight = controller.height;
                yield return Flood(root, "walk", walkRise, radius, bodyHeight);
                yield return Flood(root, "jump", FloodJumpRise, radius, bodyHeight);
            }
            Finish("DONE", 0);
        }

        // Walks Daggerfall's real collision from the flood start, on a grid, and writes every standing position reached.
        IEnumerator Flood(Transform root, string name, float maxRise, float radius, float bodyHeight)
        {
            float scale = MeshReader.GlobalScale;
            var seen = new HashSet<long>();
            var open = new Queue<Vector3>();
            var lines = new StringBuilder();
            Vector3 first;
            if (!FloorBelow(root.TransformPoint(new Vector3(floodX, floodFloor + FloodStartLift, floodY) * scale), out first))
            {
                results.Append("FLOOD " + name + " no floor at start\n");
                yield break;
            }
            seen.Add(Key(root, first));
            open.Enqueue(first);
            Vector3[] steps = { root.right, root.forward, -root.right, -root.forward };
            int visited = 0;
            while (open.Count > 0 && visited < FloodLimit)
            {
                Vector3 at = open.Dequeue();
                visited++;
                Vector3 local = root.InverseTransformPoint(at) / scale;
                lines.AppendFormat(CultureInfo.InvariantCulture, "{0:F0} {1:F0} {2:F0}\n", local.x, local.z, local.y);
                foreach (Vector3 step in steps)
                {
                    Vector3 next = at + step * FloodCell * scale;
                    // Search for the floor from under any ceiling, so a low room cannot land on the level above it.
                    float lift = (maxRise + 1f) * scale;
                    RaycastHit roof;
                    if (Physics.Raycast(next + Vector3.up * 2f * scale, Vector3.up, out roof, lift, ~0, QueryTriggerInteraction.Ignore))
                        lift = roof.distance + 1.5f * scale;
                    Vector3 from = next + Vector3.up * lift;
                    Vector3 floor;
                    if (!FloorBelow(from, out floor) || !seen.Add(Key(root, floor)))
                        continue;
                    Vector3 knee = Vector3.up * FloodKnee * scale;
                    bool blocked = Physics.Linecast(at + knee, floor + knee, ~0, QueryTriggerInteraction.Ignore)
                        || Physics.CheckCapsule(floor + Vector3.up * (radius + FloodClearance * scale),
                            floor + Vector3.up * Mathf.Max(radius + FloodClearance * scale, bodyHeight - radius),
                            radius * FloodBodyFit, ~0, QueryTriggerInteraction.Ignore);
                    if (blocked)
                        seen.Remove(Key(root, floor));
                    else
                        open.Enqueue(floor);
                }
                if (visited % 4000 == 0)
                    yield return null;
            }
            File.WriteAllText(Path.Combine(outDir, "df_flood_" + name + ".txt"), lines.ToString());
            results.AppendFormat(CultureInfo.InvariantCulture, "FLOOD {0} maxrise {1:F1} visited {2}{3}\n", name, maxRise, visited,
                open.Count > 0 ? " LIMIT REACHED" : "");
        }

        static bool FloorBelow(Vector3 from, out Vector3 floor)
        {
            RaycastHit hit;
            if (Physics.Raycast(from, Vector3.down, out hit, ProbeRange * MeshReader.GlobalScale, ~0, QueryTriggerInteraction.Ignore))
            {
                floor = hit.point;
                return true;
            }
            floor = from;
            return false;
        }

        static long Key(Transform root, Vector3 world)
        {
            Vector3 local = root.InverseTransformPoint(world) / MeshReader.GlobalScale;
            long x = Mathf.RoundToInt(local.x / FloodCell) + 4096;
            long y = Mathf.RoundToInt(local.z / FloodCell) + 4096;
            long z = Mathf.RoundToInt(local.y / 4f) + 4096;
            return (x << 26) | (y << 13) | z;
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
