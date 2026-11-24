using System;

record EnemyPlacement(double X, double Y, double Z, ulong Hash, int Record, int MobileId);

// Daggerfall enemy placements become invisible encounter markers. Doom's encounter planner decides the monsters at
// load, so the converter no longer picks any.
static class EnemyRoster
{
    // A marker is a MapSpot (9001, invisible and inert). Its args carry:
    //   arg0  MarkerMagic, so Doom can tell encounter markers from other map spots;
    //   arg1  placement hash bits 32 to 48 (the 49 bits a monster id keeps);
    //   arg2  placement hash bits 0 to 31, as a signed int;
    //   arg3  the Daggerfall record type: 15 random enemy, 16 fixed enemy;
    //   arg4  the record's FactionOrMobileId: the fixed enemy's MobileTypes, or the random enemy's data.
    public const int MarkerMagic = 7365;
    public const int MarkerType = 9001;

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

    // 49 placement bits, the part of the hash a monster id keeps (DFB_MONSTER_MEMBER_BITS 12 in the bridge header).
    public const int MemberBits = 12;
    public static ulong PlacementBits(ulong hash) => hash & ((1UL << (61 - MemberBits)) - 1);

    public static string MarkerThing(EnemyPlacement e, int height)
    {
        ulong bits = PlacementBits(e.Hash);
        int hi = (int)(bits >> 32), lo = unchecked((int)(uint)bits);
        return FormattableString.Invariant($"thing {{ x = {e.X:F1}; y = {e.Y:F1}; height = {height}.0; type = {MarkerType}; arg0 = {MarkerMagic}; arg1 = {hi}; arg2 = {lo}; arg3 = {e.Record}; arg4 = {e.MobileId}; comment = \"encounter {bits:x13}\"; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; coop = true; dm = true; }}\n");
    }
}
