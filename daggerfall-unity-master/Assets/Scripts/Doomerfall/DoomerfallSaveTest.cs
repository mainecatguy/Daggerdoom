// Doomerfall test only, run by tools/synchronized_save/run_controls.py:
//   -dfplainsavetest          once in play, makes a normal Daggerfall save through its own entry point (into the
//                             private portable folder) and logs the files it wrote.
//   -dfloadsavetest <save>    once in play, loads a Daggerfall half taken out of a bundle through Daggerfall's normal loader.
// The save fault injection (-dfsavetestfail df_write) stays in DoomerfallSave, at the step it fails.

using System;
using System.Collections;
using System.IO;
using DaggerfallWorkshop.Game.Serialization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallSaveTest
    {
        // DoomerfallSave.Init. Does nothing without either flag.
        internal static void Attach(MonoBehaviour host, DoomerfallBridge bridge, DoomerfallPositionSync sync, string[] args)
        {
            if (Array.IndexOf(args, "-dfplainsavetest") >= 0)
                host.StartCoroutine(PlainSave(bridge, sync));
            int load = Array.IndexOf(args, "-dfloadsavetest");
            if (load >= 0 && load + 1 < args.Length)
                host.StartCoroutine(LoadSave(bridge, sync, args[load + 1]));
        }

        static IEnumerator LoadSave(DoomerfallBridge bridge, DoomerfallPositionSync sync, string saveName)
        {
            while (!sync.InGame || sync.Phase != Dfb.DF_PHASE_PLAY)
                yield return null;
            yield return new WaitForSecondsRealtime(1f);
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            saves.EnumerateSaves();
            SaveLoadManager.OnLoadEventHandler logLoaded = null;
            logLoaded = data =>
            {
                SaveLoadManager.OnLoad -= logLoaded;
                bridge.LogLine(string.Format("load test: loaded health {0}/{1}, position {2},{3}", GameManager.Instance.PlayerEntity.CurrentHealth,
                    GameManager.Instance.PlayerEntity.MaxHealth, data.playerData.playerPosition.worldPosX, data.playerData.playerPosition.worldPosZ));
            };
            SaveLoadManager.OnLoad += logLoaded;
            saves.Load(GameManager.Instance.PlayerEntity.Name, saveName);
        }

        static IEnumerator PlainSave(DoomerfallBridge bridge, DoomerfallPositionSync sync)
        {
            while (!sync.InGame || sync.Phase != Dfb.DF_PHASE_PLAY)
                yield return null;
            yield return new WaitForSecondsRealtime(1f);
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            string character = GameManager.Instance.PlayerEntity.Name;
            saves.Save(character, "PlainSaveTest");
            yield return new WaitForSecondsRealtime(2f);
            int key = saves.FindSaveFolderByNames(character, "PlainSaveTest");
            string folder = key >= 0 ? saves.GetSaveFolder(key) : null;
            bridge.LogLine("plain save test: " + (folder == null ? "no save found" : "files " + string.Join(",", Array.ConvertAll(Directory.GetFiles(folder), Path.GetFileName))));
        }
    }
}
