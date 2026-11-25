// Doomerfall measurement only: what Daggerfall's hidden 3D world costs in a bridge session.
// Enabled by -dfworldcost (or DOOMERFALL_WORLDCOST=1 for harnesses that cannot add Daggerfall arguments), and only
// writes to the bridge log. Nothing here changes the game.
//
// The run is cut into segments, one per place Daggerfall is in (menu, loading, exterior map pixel, building,
// dungeon). Each segment logs its frame times, its hitches over 50 ms, how long Daggerfall took to report ready to
// Doom, process and Unity memory, and a census of what the hidden scene holds. The census walks the scene, so the
// frame after it is left out of the frame statistics. tools/hidden_world/analyze.py reads the "worldcost" lines.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Serialization;
using UnityEngine;
using UnityEngine.Profiling;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallWorldCost : MonoBehaviour
    {
        const float CensusAfterSeconds = 3f, PeriodicSeconds = 10f, HitchMs = 50f;
        const int Buckets = 2000; // 0.1 ms each, up to 200 ms
        const int MaxHitches = 24;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        string key;
        float segmentStart, nextPeriodic;
        bool censusDone, skipNextFrame, readyLogged;
        long frames, over16, over33, over100;
        double sumMs, maxMs;
        readonly int[] histogram = new int[Buckets + 1];
        readonly List<string> hitches = new List<string>();
        int segmentIndex;

        internal static void Attach(DoomerfallBridge owner, DoomerfallPositionSync positionSync, string[] args)
        {
            if (Array.IndexOf(args, "-dfworldcost") < 0 && Environment.GetEnvironmentVariable("DOOMERFALL_WORLDCOST") != "1")
                return;
            DoomerfallWorldCost cost = owner.gameObject.AddComponent<DoomerfallWorldCost>();
            cost.bridge = owner;
            cost.sync = positionSync;
        }

        void Update()
        {
            float now = Time.realtimeSinceStartup;
            string current = Place();
            if (current != key)
            {
                if (key != null)
                    EndSegment(now, "left");
                key = current;
                segmentStart = now;
                nextPeriodic = now + PeriodicSeconds;
                censusDone = readyLogged = false;
                segmentIndex++;
                bridge.LogLine(string.Format("worldcost begin {0} {1} | {2}", segmentIndex, key, Memory()));
                // This frame's time is the change itself (a door, load or teleport), so it counts in the new place.
            }

            float ms = Time.unscaledDeltaTime * 1000f;
            if (skipNextFrame)
                skipNextFrame = false;
            else
                AddFrame(ms, now - segmentStart);

            if (!readyLogged && sync.Phase == Dfb.DF_PHASE_PLAY)
            {
                readyLogged = true;
                bridge.LogLine(string.Format(CultureInfo.InvariantCulture, "worldcost ready {0} {1} after {2:F0} ms", segmentIndex, key, (now - segmentStart) * 1000f));
            }
            if (!censusDone && now - segmentStart >= CensusAfterSeconds)
            {
                censusDone = true;
                Census("settled");
            }
            if (now >= nextPeriodic)
            {
                nextPeriodic = now + PeriodicSeconds;
                EndSegment(now, "periodic"); // A running total: the segment goes on.
            }
        }

        void AddFrame(float ms, float atSeconds)
        {
            frames++;
            sumMs += ms;
            if (ms > maxMs) maxMs = ms;
            if (ms > 16.7f) over16++;
            if (ms > 33.3f) over33++;
            if (ms > 100f) over100++;
            histogram[Math.Min((int)(ms * 10f), Buckets)]++;
            if (ms > HitchMs && hitches.Count < MaxHitches)
                hitches.Add(string.Format(CultureInfo.InvariantCulture, "{0:F0}ms@{1:F2}s", ms, atSeconds));
            if (ms > 100f) // A test may stop the game soon after a big hitch, so its summary comes out a second later.
                nextPeriodic = Math.Min(nextPeriodic, Time.realtimeSinceStartup + 1f);
        }

        string Place()
        {
            if (!GameManager.HasInstance || !GameManager.Instance.IsReady || !sync.InGame)
                return "menu";
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return "loading";
            GameManager game = GameManager.Instance;
            PlayerEnterExit enter = game.PlayerEnterExit;
            string location = game.PlayerGPS.HasCurrentLocation ? game.PlayerGPS.CurrentLocation.Name.Replace(' ', '_') : "-";
            if (enter.IsPlayerInsideDungeon)
                return "dungeon:" + location;
            if (enter.IsPlayerInsideBuilding)
                return "building:" + location;
            return string.Format("exterior:{0},{1}:{2}", game.StreamingWorld.MapPixelX, game.StreamingWorld.MapPixelY, location);
        }

        double Percentile(double fraction)
        {
            long wanted = (long)(frames * fraction), seen = 0;
            for (int i = 0; i <= Buckets; i++)
            {
                seen += histogram[i];
                if (seen > wanted)
                    return (i + 1) / 10.0;
            }
            return maxMs;
        }

        void EndSegment(float now, string why)
        {
            bridge.LogLine(string.Format(CultureInfo.InvariantCulture,
                "worldcost frames {0} {1} {2} seconds={3:F1} frames={4} mean_ms={5:F3} p50_ms={6:F1} p95_ms={7:F1} p99_ms={8:F1} max_ms={9:F1} over16={10} over33={11} over100={12} hitches={13} | {14}",
                segmentIndex, key, why, now - segmentStart, frames, frames > 0 ? sumMs / frames : 0, Percentile(0.5), Percentile(0.95), Percentile(0.99),
                maxMs, over16, over33, over100, hitches.Count > 0 ? string.Join(",", hitches.ToArray()) : "none", Memory()));
            if (why == "periodic")
            {
                skipNextFrame = true; // Reading process memory takes a moment.
                return;
            }
            frames = over16 = over33 = over100 = 0;
            sumMs = maxMs = 0;
            Array.Clear(histogram, 0, histogram.Length);
            hitches.Clear();
            skipNextFrame = false;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct ProcessMemoryCounters
        {
            public uint cb, PageFaultCount;
            public UIntPtr PeakWorkingSetSize, WorkingSetSize, QuotaPeakPagedPoolUsage, QuotaPagedPoolUsage,
                QuotaPeakNonPagedPoolUsage, QuotaNonPagedPoolUsage, PagefileUsage, PeakPagefileUsage, PrivateUsage;
        }

        [DllImport("kernel32.dll")]
        static extern bool K32GetProcessMemoryInfo(IntPtr process, out ProcessMemoryCounters counters, uint size);

        [DllImport("kernel32.dll")]
        static extern IntPtr GetCurrentProcess();

        // Mono's Process.WorkingSet64 reads 0 in the player, so this asks Windows directly.
        static string Memory()
        {
            ProcessMemoryCounters counters;
            ulong ws = 0, priv = 0;
            if (K32GetProcessMemoryInfo(GetCurrentProcess(), out counters, (uint)Marshal.SizeOf(typeof(ProcessMemoryCounters))))
            {
                ws = counters.WorkingSetSize.ToUInt64();
                priv = counters.PrivateUsage.ToUInt64();
            }
            return string.Format(CultureInfo.InvariantCulture, "ws_mb={0} private_mb={1} unity_alloc_mb={2} unity_reserved_mb={3} mono_mb={4} gfx_mb={5}",
                ws >> 20, priv >> 20, Profiler.GetTotalAllocatedMemoryLong() >> 20,
                Profiler.GetTotalReservedMemoryLong() >> 20, Profiler.GetMonoUsedSizeLong() >> 20, Profiler.GetAllocatedMemoryForGraphicsDriver() >> 20);
        }

        void Census(string why)
        {
            Stopwatch watch = Stopwatch.StartNew();
            int renderers = 0, renderersOn = 0;
            foreach (Renderer r in FindObjectsOfType<Renderer>()) { renderers++; if (r.enabled) renderersOn++; }
            int colliders = 0, collidersOn = 0, meshColliders = 0;
            foreach (Collider c in FindObjectsOfType<Collider>()) { colliders++; if (c.enabled) collidersOn++; if (c is MeshCollider) meshColliders++; }
            int enemies = 0, hostile = 0, aiOn = 0;
            foreach (DaggerfallEntityBehaviour enemy in ActiveGameObjectDatabase.GetActiveEnemyBehaviours())
            {
                enemies++;
                EnemyMotor motor = enemy.GetComponent<EnemyMotor>();
                if (motor && motor.IsHostile) hostile++;
                if (motor && motor.enabled) aiOn++;
            }
            GameManager game = GameManager.Instance;
            var line = new StringBuilder();
            line.AppendFormat(CultureInfo.InvariantCulture,
                "worldcost census {0} {1} {2} terrain_distance={3} terrains={4} renderers={5} renderers_on={6} colliders={7} colliders_on={8} mesh_colliders={9} rigidbodies={10} " +
                "behaviours={11} enemies={12} enemies_hostile={13} enemy_motors_on={14} disable_ai={15} mobile_npcs={16} static_npcs={17} loot={18} lights={19} particles={20} " +
                "audio={21} meshes={22} textures={23} materials={24} census_ms={25:F1}",
                segmentIndex, key, why, game.StreamingWorld ? game.StreamingWorld.TerrainDistance : -1, FindObjectsOfType<Terrain>().Length, renderers, renderersOn,
                colliders, collidersOn, meshColliders, FindObjectsOfType<Rigidbody>().Length, FindObjectsOfType<MonoBehaviour>().Length, enemies, hostile, aiOn,
                game.DisableAI, FindObjectsOfType<MobilePersonNPC>().Length, FindObjectsOfType<StaticNPC>().Length, FindObjectsOfType<DaggerfallLoot>().Length,
                FindObjectsOfType<Light>().Length, FindObjectsOfType<ParticleSystem>().Length, FindObjectsOfType<AudioSource>().Length,
                Resources.FindObjectsOfTypeAll<Mesh>().Length, Resources.FindObjectsOfTypeAll<Texture2D>().Length, Resources.FindObjectsOfTypeAll<Material>().Length,
                watch.Elapsed.TotalMilliseconds);
            line.Append(" | ").Append(Memory());
            bridge.LogLine(line.ToString());
            skipNextFrame = true;
        }
    }
}
