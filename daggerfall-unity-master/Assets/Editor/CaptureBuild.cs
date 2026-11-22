using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.AddressableAssets.Settings;
using UnityEngine;

// Builds the comparison-test player. Its separate product name and Portable.txt keep it away from the
// owner's Daggerfall Unity settings, saves, and registry entries.
public static class CaptureBuild
{
    const string Output = "Builds/Capture/DFCapture.exe";

    public static void BuildWindows64()
    {
        string productName = PlayerSettings.productName;
        bool succeeded = false;
        try
        {
            PlayerSettings.productName = "DoomDaggerfall Capture Test";
            AddressableAssetSettings.BuildPlayerContent();
            var scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray();
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = Output,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None
            });
            succeeded = report.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded;
            if (succeeded)
                File.WriteAllText(Path.Combine(Path.GetDirectoryName(Output), "Portable.txt"), "Comparison test install\n");
            Debug.Log("CaptureBuild result: " + report.summary.result);
        }
        finally
        {
            PlayerSettings.productName = productName;
            AssetDatabase.SaveAssets();
        }
        EditorApplication.Exit(succeeded ? 0 : 1);
    }
}
