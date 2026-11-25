// Doomerfall test only (-dfplainloadtest <save name>, with Doom's -dfplainloadtest): when Daggerfall's Load window opens
// inside Doom, picks the named save as the player would. Run by tools/plain_load/run_plain_load.py.

using System;
using System.Collections;
using DaggerfallWorkshop.Game.Serialization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallPlainLoadTest
    {
        // DoomerfallPlainLoad.WindowOpened. Does nothing without the flag.
        internal static void WindowOpened(MonoBehaviour host, DoomerfallBridge bridge)
        {
            string[] args = Environment.GetCommandLineArgs();
            int test = Array.IndexOf(args, "-dfplainloadtest");
            if (test >= 0 && test + 1 < args.Length)
                host.StartCoroutine(Load(bridge, args[test + 1]));
        }

        static IEnumerator Load(DoomerfallBridge bridge, string saveName)
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
    }
}
