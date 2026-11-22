// Minimal stand-ins for the Unity-side classes that Daggerfall Unity's file readers
// reference. They disable mods, quests, and the "smaller dungeons" option so the
// converter always sees the original game data.
using DaggerfallConnect;
using DaggerfallConnect.Arena2;

namespace UnityEngine
{
    public class TextAsset { public byte[] bytes = null; }
    public static class Resources { public static T Load<T>(string name) where T : class => null; }
    public struct Color32
    {
        public byte r, g, b, a;
        public Color32(byte r, byte g, byte b, byte a) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public static Color32 Lerp(Color32 x, Color32 y, float t) => x;
        public static implicit operator Color(Color32 c) => new Color(c.r / 255f, c.g / 255f, c.b / 255f, c.a / 255f);
    }
    // The image readers reference these only in color helpers that the mesh export does not call.
    public struct Color
    {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a = 1f) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public static Color clear => new Color(0, 0, 0, 0);
        public static Color white => new Color(1, 1, 1, 1);
        public static void RGBToHSV(Color c, out float h, out float s, out float v) { h = s = 0; v = System.Math.Max(c.r, System.Math.Max(c.g, c.b)); }
        public static Color Lerp(Color x, Color y, float t) => x;
        public static implicit operator Color32(Color c) => new Color32((byte)(c.r * 255), (byte)(c.g * 255), (byte)(c.b * 255), (byte)(c.a * 255));
    }
    public static class Mathf
    {
        public static float Pow(float x, float y) => (float)System.Math.Pow(x, y);
        public static float Clamp01(float x) => x < 0 ? 0 : x > 1 ? 1 : x;
    }
    public static class Debug
    {
        public static void Log(object m) => System.Console.WriteLine(m);
        public static void LogWarning(object m) => System.Console.WriteLine(m);
        public static void LogError(object m) => System.Console.WriteLine(m);
        public static void LogFormat(string f, params object[] a) => System.Console.WriteLine(f, a);
    }
}

namespace DaggerfallConnect.Arena2
{
    public partial class FactionFile { public enum FactionRaces { None = -1, Nord = 0, Khajiit = 1, Redguard = 2, Breton = 3, Argonian = 4, WoodElf = 5, HighElf = 6, DarkElf = 7 } }
}

namespace DaggerfallWorkshop.Game { public class StubGameNamespace { } }
namespace DaggerfallWorkshop.Game.Utility { public class NameHelper { public enum BankTypes { Breton } } }

namespace DaggerfallWorkshop.Game.Questing
{
    public enum SiteTypes { None, Building, Dungeon }
    public enum QuestSmallerDungeonsState { NotSet, Disabled, Enabled }
    public struct SiteLink { public ulong questUID; }
    public class Quest { public QuestSmallerDungeonsState SmallerDungeonsState; }
    public class QuestMachine
    {
        public static readonly QuestMachine Instance = new QuestMachine();
        public SiteLink[] GetSiteLinks(SiteTypes type, int mapId) => null;
        public Quest GetQuest(ulong uid) => null;
    }
}

namespace DaggerfallWorkshop
{
    public class DaggerfallDungeon { public static bool IsMainStoryDungeon(int mapId) => true; }
    public class DaggerfallUnity
    {
        public class SettingsStub { public bool SmallerDungeons = false; }
        public static readonly SettingsStub Settings = new SettingsStub();
        public static void LogMessage(string message, bool showInConsole = false) => System.Console.WriteLine(message);
    }
}

namespace DaggerfallWorkshop.Utility.AssetInjection
{
    public static class WorldDataReplacement
    {
        public static string GetNewDFBlockName(int block) => null;
        public static int GetNewDFBlockIndex(string name) => -1;
        public static bool GetDFBlockReplacementData(int block, string name, out DFBlock dfBlock) { dfBlock = default; return false; }
        public static void GetDFRegionAdditionalLocationData(int region, ref DFRegion dfRegion) { }
        public static bool GetDFLocationReplacementData(int region, int location, out DFLocation dfLocation) { dfLocation = default; return false; }
        public static bool GetBuildingReplacementData(string blockName, int block, int recordIndex, out BuildingReplacementData data) { data = default; return false; }
        public static void ApplyBuildingReplacementAutoMapData(in BuildingReplacementData data, ref byte[] autoMapData) { }
    }
    public struct BuildingReplacementData { public DFBlock.RmbSubRecord RmbSubRecord; public ushort FactionId; public int BuildingType; public byte Quality; public ushort NameSeed; public byte[] AutoMapData; }
}
