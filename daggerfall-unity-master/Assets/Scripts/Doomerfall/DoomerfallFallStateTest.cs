// Doomerfall test only (-dffalltest): drives Daggerfall's two falling damage exemptions for a paired run
// (tools/jumping/run_fall_exempt_test.py). A real Slowfall spell is cast on the player for 20 seconds and its spell
// bundles are cleared for the next 20, so the Doom probe can drop the player with and without it. Every few
// seconds it logs the nearest outdoor water tile of the player's terrain, as an offset from the player in Doom units
// (30 per metre, x east, y north), so the probe can find water on a later run.

using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.MagicAndEffects;
using DaggerfallWorkshop.Game.MagicAndEffects.MagicEffects;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallFallStateTest : MonoBehaviour
    {
        DoomerfallBridge bridge;
        float nextReport, nextCast;
        bool lastSlowfall, ready;

        internal void Init(DoomerfallBridge owner) { bridge = owner; }

        void Update()
        {
            if (!GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || bridge == null)
                return;
            GameManager gm = GameManager.Instance;
            bool slowfall = Time.realtimeSinceStartup % 40f < 20f;
            EntityEffectManager effects = gm.PlayerEffectManager;
            // The spell is cast again every second while it should be on: in the sync test it throws on assignment and
            // ends after about two seconds.
            if (ready && slowfall && effects != null && !gm.PlayerEntity.IsSlowFalling && Time.realtimeSinceStartup >= nextCast)
            {
                nextCast = Time.realtimeSinceStartup + 1f;
                lastSlowfall = false;
            }
            if (ready && slowfall != lastSlowfall && effects != null)
            {
                lastSlowfall = slowfall; // once per edge, even if the spell call fails
                try
                {
                    if (slowfall)
                    {
                        EffectSettings lasting = BaseEntityEffect.DefaultEffectSettings();
                        lasting.DurationBase = 100; // rounds; the default lasts only a moment, and the bundle is cleared after 20 s anyway
                        effects.AssignBundle(effects.CreateSpellBundle(Slowfall.EffectKey, ElementTypes.Magic, lasting), AssignBundleFlags.BypassSavingThrows);
                    }
                    else
                        effects.ClearSpellBundles();
                    bridge.LogLine("fall test: slowfall spell " + (slowfall ? "cast" : "cleared"));
                }
                catch (System.Exception e)
                {
                    bridge.LogLine("fall test: slowfall spell " + (slowfall ? "cast" : "cleared") + " threw " + e.GetType().Name + ": " + e.Message + " at " + (e.StackTrace ?? "").Split('\n')[0].Trim());
                }
            }
            if (Time.realtimeSinceStartup < nextReport)
                return;
            nextReport = Time.realtimeSinceStartup + 5f;
            ReportWater(gm);
        }

        // The nearest water tile among all loaded terrains, as an offset from the player in Doom units.
        void ReportWater(GameManager gm)
        {
            DaggerfallTerrain[] terrains = FindObjectsOfType<DaggerfallTerrain>();
            float dim = MapsFile.WorldMapTerrainDim * MeshReader.GlobalScale;
            int n = MapsFile.WorldMapTileDim;
            Vector3 player = gm.PlayerObject.transform.position;
            int water = 0, withMaps = 0;
            float best = float.MaxValue, bestX = 0, bestZ = 0;
            foreach (DaggerfallTerrain terrain in terrains)
            {
                if (!terrain.isActiveAndEnabled || terrain.TileMap == null || terrain.TileMap.Length != n * n)
                    continue;
                withMaps++;
                Vector3 origin = terrain.transform.position;
                for (int y = 0; y < n; y++)
                    for (int x = 0; x < n; x++)
                    {
                        if (terrain.TileMap[y * n + x].r / 4 != 0)
                            continue;
                        water++;
                        float wx = origin.x + (x + 0.5f) * dim / n - player.x;
                        float wz = origin.z + (y + 0.5f) * dim / n - player.z;
                        float d = wx * wx + wz * wz;
                        if (d < best) { best = d; bestX = wx; bestZ = wz; }
                    }
            }
            if (withMaps == 0)
            {
                bridge.LogLine("fall test: no player terrain");
                return;
            }
            ready = true; // the world is up, so a spell can be cast
            bridge.LogLine(string.Format("fall test: tile {0} terrains {1} water tiles {2} nearest dx {3:0} dy {4:0} (Doom units)",
                gm.StreamingWorld.PlayerTileMapIndex, withMaps, water, bestX * 30f, bestZ * 30f));
        }
    }
}
