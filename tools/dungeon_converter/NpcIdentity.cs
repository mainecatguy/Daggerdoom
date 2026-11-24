// The stable id of one Daggerfall NPC layout record. DoomerfallNpcs.MakeId in Daggerfall Unity must compute the same value.
// Blocks repeat across a location, so the id combines where the block is used with the record's offset in BLOCKS.BSA.
static class NpcIdentity
{
    public const int Exterior = 1, Interior = 2, Dungeon = 3;
    const ulong Tag = 6;
    const int TagShift = 61;

    // Exterior: block x and y. Interior: block x and y, and the building's record. Dungeon: block x and z.
    public static ulong Make(int mapId, int scope, int a, int b, int c, long position)
    {
        ulong h = 14695981039346656037UL;
        foreach (long v in new long[] { mapId, scope, a, b, c, (int)position })
            for (int k = 0; k < 8; k++)
            {
                h ^= (byte)(v >> (8 * k));
                h *= 1099511628211UL;
            }
        h ^= h >> 32;
        h *= 0x9E3779B97F4A7C15UL;
        h ^= h >> 29;
        return (Tag << TagShift) | (h & ((1UL << TagShift) - 1));
    }
}
