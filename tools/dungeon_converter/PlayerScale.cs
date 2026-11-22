// The one world and player scale value. World size and every player dimension derive from it.
using System;
using System.Globalization;
using System.IO;
using System.IO.Compression;

static class PlayerScale
{
    // Owner decision: converted maps default to 75% scale. 1.0 would mean 1 Daggerfall unit = 1 Doom unit. Override with --world-scale.
    public static double DoomUnitsPerDaggerfallUnit = 0.75;

    // Daggerfall Unity's player in Daggerfall units (PlayerAdvanced.prefab, PlayerHeightChanger.cs; 1 m = 40 units).
    const double DfHeight = 72, DfEyeBelowTop = 3.6, DfCrouchHeight = 36, DfRadius = 14, DfStep = 20;

    // The default body has stock Doom height, eye, step, and crouch. --daggerfall-player opts in to the scaled Daggerfall body and its package.
    public static bool DaggerfallBody;
    const double DoomHeight = 56, DoomEye = 41, DoomStep = 24;

    static double S => DoomUnitsPerDaggerfallUnit;
    public static double Height => DaggerfallBody ? DfHeight * S : DoomHeight;
    public static double EyeHeight => DaggerfallBody ? (DfHeight - DfEyeBelowTop) * S : DoomEye;
    public static double CrouchHeight => DaggerfallBody ? DfCrouchHeight * S : DoomHeight / 2;
    public static double CrouchEyeHeight => DaggerfallBody ? (DfCrouchHeight - DfEyeBelowTop) * S : DoomEye / 2;
    public static double Radius => DfRadius * S; // Owner decision: width follows Daggerfall at world scale in both modes
    public static double Step => DaggerfallBody ? DfStep * S : DoomStep;

    static string F(double v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    // Load this package with the map to use Daggerfall's player size. Leave it out, or set df_playersize 0, to turn it off.
    public static void WritePackage(string outDir, string slug)
    {
        string path = Path.Combine(outDir, slug + "_player.pk3");
        if (File.Exists(path)) File.Delete(path);
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        void Add(string name, string text)
        {
            using var s = new StreamWriter(zip.CreateEntry(name, CompressionLevel.Fastest).Open());
            s.Write(text);
        }
        Add("MAPINFO", "GameInfo\n{\n\tAddEventHandlers = \"DFPlayerSize\"\n}\n");
        Add("CVARINFO", "server bool df_playersize = true;\n");
        Add("zscript.zs", $@"version ""4.10""

// [DoomDaggerfall] Gives the current player class Daggerfall's size on converted maps only.
class DFPlayerSize : EventHandler
{{
	const PlayerRadius = {F(Radius)};
	const PlayerHeight = {F(Height)};
	const PlayerEye = {F(EyeHeight)};
	const PlayerStep = {F(Step)};

	static bool IsDaggerfallMap()
	{{
		return df_playersize && level.MapName ~== ""MAP01"" && Wads.CheckNumForName(""DFPOINTS"", Wads.ns_global) >= 0;
	}}

	override void WorldLoaded(WorldEvent e) {{ for (int i = 0; i < MAXPLAYERS; i++) if (playeringame[i]) Apply(players[i].mo); }}
	override void PlayerEntered(PlayerEvent e) {{ Apply(players[e.PlayerNumber].mo); }}

	static void Apply(PlayerPawn mo)
	{{
		if (!mo) return;
		bool df = IsDaggerfallMap();
		double h = df ? PlayerHeight : mo.Default.Height, v = df ? PlayerEye : mo.Default.ViewHeight;
		mo.A_SetSize(df ? PlayerRadius : mo.Default.Radius, h * mo.player.crouchfactor);
		mo.FullHeight = h;
		mo.ViewHeight = v;
		mo.MaxStepHeight = df ? PlayerStep : mo.Default.MaxStepHeight;
		mo.player.viewheight = v * mo.player.crouchfactor;
		mo.player.crouchviewdelta = mo.player.viewheight - v;
	}}
}}
");
    }
}
