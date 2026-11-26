// Doomerfall test only (-dfresettest <days>): the first time Daggerfall follows the player out of a dungeon, this
// passes <days> days on Daggerfall's clock and makes PlayerGPS see a map pixel change, which is where Daggerfall
// Unity forgets the cached state of every place it is not keeping. A marker scene is cached first, so the log says
// whether that reset still ran. The Doom side then re-enters the dungeon and checks it is still cleared.
//
// Logs one "resettest:" line to the bridge log before and one after.

using System;
using System.Reflection;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallResetsTest : MonoBehaviour
    {
        const string Marker = "DoomerfallResetTest";
        float days;
        int step;
        float at;
        int spawnersBefore;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "-dfresettest");
            float wanted;
            if (index < 0 || index + 1 >= args.Length || !float.TryParse(args[index + 1], out wanted))
                return;
            GameObject host = new GameObject("DoomerfallResetsTest");
            DontDestroyOnLoad(host);
            host.AddComponent<DoomerfallResetsTest>().days = wanted;
        }

        void Awake()
        {
            PlayerEnterExit.OnTransitionDungeonExterior += OnLeftDungeon;
        }

        void OnDestroy()
        {
            PlayerEnterExit.OnTransitionDungeonExterior -= OnLeftDungeon;
        }

        void OnLeftDungeon(PlayerEnterExit.TransitionEventArgs args)
        {
            if (step != 0)
                return;
            step = 1;
            at = Time.unscaledTime + 1f;
        }

        static void Log(string line)
        {
            Debug.Log(line);
            DoomerfallBridge bridge = FindObjectOfType<DoomerfallBridge>();
            if (bridge)
                bridge.LogLine(line);
        }

        static bool MarkerCached()
        {
            foreach (SceneCacheEntry_v1 entry in SaveLoadManager.StateManager.GetSceneCache().sceneCache)
                if (entry.sceneName == Marker)
                    return true;
            return false;
        }

        void Update()
        {
            if (step == 0 || step == 3 || Time.unscaledTime < at)
                return;
            GameManager game = GameManager.Instance;
            if (step == 1)
            {
                DaggerfallDateTime now = DaggerfallUnity.Instance.WorldTime.Now;
                string before = now.LongDateTimeString();
                spawnersBefore = CountSpawners();
                SaveLoadManager.CacheScene(Marker);
                now.RaiseTime(days * DaggerfallDateTime.SecondsPerDay);
                // As if the player walked onto the next map pixel: PlayerGPS compares against this on its next update.
                typeof(PlayerGPS).GetField("lastMapPixelX", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(game.PlayerGPS, -2);
                Log(string.Format("resettest: left dungeon, marker cached {0}, clock {1} -> {2}, map pixel change forced",
                    MarkerCached(), before, now.LongDateTimeString()));
                step = 2;
                at = Time.unscaledTime + 1f;
                return;
            }
            bool kept = MarkerCached();
            Log(string.Format("resettest: after {0} days and a map pixel change, session {1}, scene cache kept {2}, foe spawners {3} -> {4}",
                days, DoomerfallBridge.SessionActive, kept, spawnersBefore, CountSpawners()));
            if (kept)
                SaveLoadManager.RestoreCachedScene(Marker); // takes the marker out of the cache again
            step = 3;
        }

        static int CountSpawners()
        {
            int n = 0;
            foreach (var spawner in ActiveGameObjectDatabase.GetActiveFoeSpawners(true))
                n++;
            return n;
        }
    }
}
