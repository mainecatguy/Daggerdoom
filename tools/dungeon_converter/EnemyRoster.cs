using System;

record EnemyPlacement(double X, double Y, double Z, int Type, ulong Id);

// One random Doom enemy per Daggerfall enemy placement. The choice is a pure function of the placement's static data, so
// reconverting, reloading or visiting twice gives the same monster. Types are vanilla doomednums, so mods such as DRLA
// replace them through their own replacement rules. The roster is Doom II's regular monsters; bosses are left out.
static class EnemyRoster
{
    public static readonly int[] Types =
    {
        3004, // zombieman
        9,    // shotgun guy
        65,   // chaingunner
        3001, // imp
        3002, // demon
        58,   // spectre
        3006, // lost soul
        3005, // cacodemon
        69,   // hell knight
        3003, // baron of hell
        66,   // revenant
        67,   // mancubus
        68,   // arachnotron
        71,   // pain elemental
        64,   // arch-vile
    };

    // FNV-1a over the placement's own numbers. Not the converter's grid or scale, so it survives conversion changes.
    // DoomerfallMonsters.PlacementHash in Daggerfall Unity must compute the same value.
    public static ulong Hash(int mapId, string block, int blockX, int blockZ, int x, int y, int z, int record, int mobileId)
    {
        ulong h = 14695981039346656037UL;
        void Mix(long v) { for (int k = 0; k < 8; k++) { h ^= (byte)(v >> (8 * k)); h *= 1099511628211UL; } }
        Mix(mapId); Mix(blockX); Mix(blockZ); Mix(x); Mix(y); Mix(z); Mix(record); Mix(mobileId);
        foreach (char c in block) Mix(c);
        h ^= h >> 32; h *= 0x9E3779B97F4A7C15UL; h ^= h >> 29;
        return h;
    }

    public static int Pick(ulong hash) => Types[(int)(hash % (ulong)Types.Length)];

    // Tag 5, a 49-bit placement hash, and pack member 0 (12 member bits). See DFB_MONSTER_MEMBER_BITS in the bridge header.
    public const int MemberBits = 12;
    public static ulong MonsterId(ulong hash) => (5UL << 61) | ((hash & ((1UL << (61 - MemberBits)) - 1)) << MemberBits);
}
