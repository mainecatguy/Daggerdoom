using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.AddressableAssets.Settings;
using UnityEngine;
using Debug = UnityEngine.Debug;

// Command-line build: Unity -batchmode -executeMethod CliBuild.BuildWindows64
public static class CliBuild
{
    public static void BuildWindows64()
    {
        if (!BridgeBindingsFresh())
        {
            Debug.LogError("CliBuild result: Failed (stale bridge bindings)");
            EditorApplication.Exit(1);
            return;
        }

        AddressableAssetSettings.BuildPlayerContent();

        var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = "Builds/Windows64/DaggerfallUnity.exe",
            target = BuildTarget.StandaloneWindows64,
            options = BuildOptions.None
        });
        Debug.Log("CliBuild result: " + report.summary.result);
        EditorApplication.Exit(report.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded ? 0 : 1);
    }

    // The C# bridge definitions are generated from bridge/doomerfall_bridge.h.
    static bool BridgeBindingsFresh()
    {
        string script = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "bridge", "generate_bindings.py"));
        var start = new ProcessStartInfo("python", "\"" + script + "\" --check")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        try
        {
            using (Process process = Process.Start(start))
            {
                string output = process.StandardOutput.ReadToEnd() + process.StandardError.ReadToEnd();
                process.WaitForExit();
                if (process.ExitCode == 0)
                {
                    Debug.Log("CliBuild: " + output.Trim());
                    return true;
                }
                Debug.LogError("CliBuild: " + output.Trim());
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError("CliBuild: could not run the bridge bindings check with python: " + e.Message);
        }
        return false;
    }
}
