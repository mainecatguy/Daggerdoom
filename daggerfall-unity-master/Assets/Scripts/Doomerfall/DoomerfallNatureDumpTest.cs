// Doomerfall test only (-dfnaturedump <dir>): Daggerfall Unity's own wilderness nature layout, for checking Doom's port
// (UZDoom/src/playsim/dd_nature.cpp) with tools/nature/compare.py. Needs no bridge session.
//
// Writes into <dir>:
//   unity.txt         Mathf.PerlinNoise, UnityEngine.Random and Unity.Mathematics.Random samples
//   pixel_X_Y.txt     one wilderness map pixel per climate: climate, archive, tile types, and the flats LayoutNature makes
//   shot_X_Y.png      the view from tile (16, 64) of that pixel, facing east, at noon in summer
//   report.txt        what was chosen, or the error

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallNatureDumpTest : MonoBehaviour
    {
        string dir;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfnaturedump");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallNatureDumpTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallNatureDumpTest>().dir = args[at + 1];
        }

        IEnumerator Start()
        {
            // Same scene start as DoomerfallHotkeyShotsTest.
            float giveUp = Time.realtimeSinceStartup + 60;
            while ((DaggerfallUnity.Instance == null || !DaggerfallUnity.Instance.IsReady) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            Application.runInBackground = true;
            if (GameObject.FindWithTag("Player") == null)
                yield return SceneManager.LoadSceneAsync(1);
            while ((GameObject.FindWithTag("Player") == null || !GameManager.Instance.IsReady || DaggerfallUI.Instance == null) && Time.realtimeSinceStartup < giveUp)
                yield return null;
            StartGameBehaviour start = FindObjectOfType<StartGameBehaviour>();
            if (start != null)
                start.EnableVideos = false;
            DaggerfallUI.Instance.enableVideos = false;
            for (int i = 0; i < 5; i++)
                yield return null;
            DaggerfallUI.Instance.PopToHUD();
            Directory.CreateDirectory(dir);
            var report = new StringBuilder();
            IEnumerator run = Run(report);
            while (true)
            {
                bool more;
                try { more = run.MoveNext(); }
                catch (Exception e) { report.AppendLine("error " + e); more = false; }
                if (!more) break;
                yield return run.Current;
            }
            File.WriteAllText(Path.Combine(dir, "report.txt"), report.ToString());
            Application.Quit();
        }

        IEnumerator Run(StringBuilder report)
        {
            WriteUnitySamples();
            DaggerfallDateTime now = DaggerfallUnity.Instance.WorldTime.Now;
            now.Month = 5;  // summer, so the nature archives are the summer ones
            now.Hour = 12;
            now.Minute = 0;
            // Map pixels to visit follow the folder on the command line: -dfnaturedump <dir> x1 y1 x2 y2 ...
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfnaturedump") + 2;
            GameManager.Instance.StreamingWorld.gameObject.SetActive(true);
            for (; at + 1 < args.Length && int.TryParse(args[at], out int mx) && int.TryParse(args[at + 1], out int my); at += 2)
            {
                report.AppendLine($"pixel {mx} {my}");
                yield return Visit(mx, my, report);
            }
        }

        IEnumerator Visit(int mx, int my, StringBuilder report)
        {
            StreamingWorld world = GameManager.Instance.StreamingWorld;
            world.TeleportToCoordinates(mx, my, StreamingWorld.RepositionMethods.None);
            float giveUp = Time.realtimeSinceStartup + 60;
            yield return null;
            while (world.IsInit && Time.realtimeSinceStartup < giveUp)
                yield return null;
            yield return new WaitForSecondsRealtime(2f);
            DaggerfallTerrain terrain = null;
            foreach (DaggerfallTerrain t in FindObjectsOfType<DaggerfallTerrain>())
                if (t.MapPixelX == mx && t.MapPixelY == my)
                    terrain = t;
            if (terrain == null) { report.AppendLine($"  terrain {mx},{my} not loaded"); yield break; }
            File.WriteAllText(Path.Combine(dir, $"pixel_{mx}_{my}.txt"), Layout(terrain));

            // Stand at tile (16, 64), facing east.
            Terrain unityTerrain = terrain.GetComponent<Terrain>();
            float tile = unityTerrain.terrainData.size.x / MapsFile.WorldMapTileDim;
            Vector3 at = terrain.transform.position + new Vector3(16 * tile, 0, 64 * tile);
            at.y = unityTerrain.SampleHeight(at) + terrain.transform.position.y + 1.0f;
            GameManager.Instance.PlayerObject.transform.position = at;
            GameManager.Instance.PlayerMotor.FixStanding();
            GameManager.Instance.PlayerMouseLook.SetFacing(90, 0);
            yield return new WaitForSecondsRealtime(3f);
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, $"shot_{mx}_{my}.png"));
            yield return new WaitForSecondsRealtime(1f);
            report.AppendLine($"  done, player at {GameManager.Instance.PlayerObject.transform.position}");
        }

        // DefaultTerrainNature.LayoutNature's own steps, recording each flat instead of drawing it.
        static string Layout(DaggerfallTerrain dfTerrain)
        {
            var text = new StringBuilder();
            MapPixelData data = dfTerrain.MapData;
            DFLocation.ClimateSettings climate = MapsFile.GetWorldClimateSettings(data.worldClimate);
            int archive = ClimateSwaps.GetNatureArchive(climate.NatureSet, DaggerfallUnity.Instance.WorldTime.Now.SeasonValue);
            text.AppendLine($"pixel {dfTerrain.MapPixelX} {dfTerrain.MapPixelY} climate {data.worldClimate} archive {archive} worldHeight {data.worldHeight} rect {data.locationRect.xMin} {data.locationRect.xMax} {data.locationRect.yMin} {data.locationRect.yMax}");
            int tDim = MapsFile.WorldMapTileDim;
            var tiles = new StringBuilder("tiles");
            for (int y = 0; y < tDim; y++)
                for (int x = 0; x < tDim; x++)
                    tiles.Append(' ').Append(data.tilemapSamples[x, y] & 0x3F);
            text.AppendLine(tiles.ToString());

            Rect rect = data.locationRect;
            if (rect.x > 0 && rect.y > 0) { rect.xMin -= 4; rect.xMax += 4; rect.yMin -= 4; rect.yMax += 4; }
            float elevationScale = Mathf.Clamp(data.worldHeight / 128f, 0.4f, 1.0f);
            float climateScale = climate.ClimateType == DFLocation.ClimateBaseType.Desert ? 0.25f : 1.0f;
            float chanceOnDirt = 0.2f * elevationScale * climateScale, chanceOnGrass = 0.9f * elevationScale * climateScale, chanceOnStone = 0.05f * elevationScale * climateScale;
            TerrainData terrainData = dfTerrain.GetComponent<Terrain>().terrainData;
            UnityEngine.Random.InitState(TerrainHelper.MakeTerrainKey(dfTerrain.MapPixelX, dfTerrain.MapPixelY));
            int hDim = DaggerfallUnity.Instance.TerrainSampler.HeightmapDimension;
            float maxTerrainHeight = DaggerfallUnity.Instance.TerrainSampler.MaxTerrainHeight, beachLine = DaggerfallUnity.Instance.TerrainSampler.BeachElevation;
            var steep = new StringBuilder("steep");
            var flats = new List<string>();
            for (int y = 0; y < tDim; y++)
                for (int x = 0; x < tDim; x++)
                {
                    float steepness = terrainData.GetSteepness((float)x / tDim, (float)y / tDim);
                    steep.Append(' ').Append(steepness.ToString("F2", System.Globalization.CultureInfo.InvariantCulture));
                    if (steepness > 50f) continue;
                    if (rect.x > 0 && rect.y > 0 && rect.Contains(new Vector2(x, y))) continue;
                    int tile = data.tilemapSamples[x, y] & 0x3F;
                    float chance = tile == 1 ? chanceOnDirt : tile == 2 ? chanceOnGrass : tile == 3 ? chanceOnStone : -1;
                    if (chance < 0) continue;
                    if (UnityEngine.Random.Range(0f, 1f) > chance) continue;
                    int hx = (int)Mathf.Clamp(hDim * ((float)x / (float)tDim), 0, hDim - 1);
                    int hy = (int)Mathf.Clamp(hDim * ((float)y / (float)tDim), 0, hDim - 1);
                    if (data.heightmapSamples[hy, hx] * maxTerrainHeight < beachLine) continue;
                    flats.Add($"{x} {y} {UnityEngine.Random.Range(1, 32)}");
                }
            text.AppendLine(steep.ToString());
            text.AppendLine("flats " + flats.Count);
            foreach (string f in flats)
                text.AppendLine(f);
            return text.ToString();
        }

        void WriteUnitySamples()
        {
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            var text = new StringBuilder();
            for (int i = 0; i < 64; i++)
            {
                float x = 417028f + i * 0.37f, y = 417028f + i * 0.61f;
                if (i >= 32) { x = i * 1.13f - 20; y = i * 0.71f + 3; }
                text.AppendLine(string.Format(inv, "perlin {0:R} {1:R} {2:R}", x, y, Mathf.PerlinNoise(x, y)));
            }
            UnityEngine.Random.InitState(12345);
            for (int i = 0; i < 8; i++) text.AppendLine(string.Format(inv, "value {0:R}", UnityEngine.Random.value));
            UnityEngine.Random.InitState(TerrainHelper.MakeTerrainKey(207, 213));
            for (int i = 0; i < 8; i++) text.AppendLine(string.Format(inv, "range01 {0:R}", UnityEngine.Random.Range(0f, 1f)));
            for (int i = 0; i < 8; i++) text.AppendLine("range132 " + UnityEngine.Random.Range(1, 32));
            for (uint i = 0; i < 8; i++) text.AppendLine(string.Format(inv, "indexed {0} {1:R}", i * 1000, Unity.Mathematics.Random.CreateFromIndex(i * 1000).NextFloat(-1.5f, 1.5f)));
            File.WriteAllText(Path.Combine(dir, "unity.txt"), text.ToString());
        }
    }
}
