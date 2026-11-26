// Doomerfall: the location record's compact form on disk (DoomerfallLocations). Runs only in a bridge session.
//
// In memory a place keeps Doom's facts at full precision, so Doom's cache still compares equal within a session. On
// disk each place is one base64 blob, so a cleared slaughter dungeon costs bytes per corpse, not a line of text:
//
//   corpses     a dead mook as 13 bytes: its placement (an index into the place's placement table), pack member, class
//               and death label (indices into small tables), its position in 16-bit steps of the place's frame, facing
//               and health. Its height is not kept: Doom uses the class's death height (dd_treadmill.cpp Restore).
//   loose items an item Doom made up this session (a drop) as one u64: class, x, y, height band, amount, dropped, and
//               whether it carries something (then its carried text's name index follows in a list).
//   gone pickups map items taken, as bits: one group per map, the bit is the item's index in map order.
//   exceptions  anything else (living monsters, Daggerfall-id items, values that do not fit) as a full 40-byte fact.
//
// Positions come back to within half a step (a quarter unit in a big dungeon), which Doom's settling absorbs.

using System;
using System.Collections.Generic;
using System.IO;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallPlaceCodec
    {
        const byte Version = 2;
        const ushort NoName = 0xFFFF;
        const ulong MapItemTag = 1;          // dd_treadmill.cpp MAP_ITEM_TAG >> 61
        const int MapItemIndexBits = 20;     // dd_treadmill.cpp MAP_ITEM_INDEX_BITS
        const int MemberBits = (int)Dfb.MONSTER_MEMBER_BITS;
        const ulong PlacementMask = (1UL << ((int)Dfb.MONSTER_TAG_SHIFT - MemberBits)) - 1;

        internal struct Stats
        {
            public int corpses, loose, gone, exceptions, bytes;
            public override string ToString()
            {
                return string.Format("{0} corpses, {1} loose items, {2} gone pickups, {3} full facts, {4} bytes", corpses, loose, gone, exceptions, bytes);
            }
        }

        struct Frame
        {
            public float minX, minY, minZ, cellXY, cellZ;

            public static Frame Of(List<DfbPlaceFact> facts, float steps, float stepsZ, float finest)
            {
                Frame f = new Frame();
                if (facts.Count == 0)
                {
                    f.cellXY = f.cellZ = 1;
                    return f;
                }
                float maxX = float.MinValue, maxY = float.MinValue, maxZ = float.MinValue;
                f.minX = f.minY = f.minZ = float.MaxValue;
                foreach (DfbPlaceFact p in facts)
                {
                    f.minX = Math.Min(f.minX, p.x); maxX = Math.Max(maxX, p.x);
                    f.minY = Math.Min(f.minY, p.y); maxY = Math.Max(maxY, p.y);
                    f.minZ = Math.Min(f.minZ, p.z); maxZ = Math.Max(maxZ, p.z);
                }
                f.cellXY = Math.Max(finest, Math.Max(maxX - f.minX, maxY - f.minY) / steps * 1.0001f);
                f.cellZ = Math.Max(finest, (maxZ - f.minZ) / stepsZ * 1.0001f);
                return f;
            }

            public void Write(BinaryWriter w) { w.Write(minX); w.Write(minY); w.Write(minZ); w.Write(cellXY); w.Write(cellZ); }
            public static Frame Read(BinaryReader r) { return new Frame { minX = r.ReadSingle(), minY = r.ReadSingle(), minZ = r.ReadSingle(), cellXY = r.ReadSingle(), cellZ = r.ReadSingle() }; }
        }

        static int Table<T>(List<T> table, Dictionary<T, int> index, T value, int limit)
        {
            int at;
            if (index.TryGetValue(value, out at))
                return at;
            if (table.Count >= limit)
                return -1;
            index[value] = table.Count;
            table.Add(value);
            return table.Count - 1;
        }

        static void WriteCount(BinaryWriter w, int n) { w.Write7BitEncoded(n); }

        static uint Step(float v, float min, float cell, uint max, bool up)
        {
            double s = (v - min) / cell;
            s = up ? Math.Ceiling(s - 1e-4) : Math.Round(s);
            return (uint)Math.Max(0, Math.Min(max, s));
        }

        internal static string Encode(int mooks, List<DfbPlacePlan> plan, List<DfbPlaceFact> facts, out Stats stats)
        {
            stats = new Stats();
            List<DfbPlaceFact> corpses = new List<DfbPlaceFact>(), loose = new List<DfbPlaceFact>(), exceptions = new List<DfbPlaceFact>();
            List<ulong> placements = new List<ulong>(); Dictionary<ulong, int> placementIndex = new Dictionary<ulong, int>();
            List<ushort> classes = new List<ushort>(); Dictionary<ushort, int> classIndex = new Dictionary<ushort, int>();
            List<ushort> deaths = new List<ushort>(); Dictionary<ushort, int> deathIndex = new Dictionary<ushort, int>();
            List<ushort> itemClasses = new List<ushort>(); Dictionary<ushort, int> itemClassIndex = new Dictionary<ushort, int>();
            SortedDictionary<ulong, SortedSet<int>> gone = new SortedDictionary<ulong, SortedSet<int>>();

            foreach (DfbPlaceFact f in facts)
            {
                bool session = (f.flags & Dfb.FACT_SESSION) != 0;
                if (f.kind == Dfb.FACT_CORPSE && f.flags == 0 && (f.id >> (int)Dfb.MONSTER_TAG_SHIFT) == Dfb.MONSTER_TAG
                    && Table(placements, placementIndex, (f.id >> MemberBits) & PlacementMask, 255) >= 0
                    && Table(classes, classIndex, f.cls, 255) >= 0 && Table(deaths, deathIndex, f.death, 15) >= 0)
                {
                    corpses.Add(f);
                    continue;
                }
                if (f.kind == Dfb.FACT_ITEM && session && f.amount >= 0 && f.amount < 4096 && Table(itemClasses, itemClassIndex, f.cls, 511) >= 0)
                {
                    loose.Add(f);
                    continue;
                }
                if (f.kind == Dfb.FACT_GONE && f.flags == 0 && (f.id >> 61) == MapItemTag)
                {
                    SortedSet<int> bits;
                    if (!gone.TryGetValue(f.id >> MapItemIndexBits, out bits))
                        gone[f.id >> MapItemIndexBits] = bits = new SortedSet<int>();
                    bits.Add((int)(f.id & ((1UL << MapItemIndexBits) - 1)));
                    continue;
                }
                exceptions.Add(f);
            }

            MemoryStream ms = new MemoryStream();
            using (BinaryWriter w = new BinaryWriter(ms))
            {
                w.Write(Version);
                w.Write(mooks);
                WriteCount(w, plan.Count);
                foreach (DfbPlacePlan q in plan)
                {
                    w.Write(q.placement); w.Write(q.x); w.Write(q.y); w.Write(q.z); w.Write(q.value);
                }
                WriteCount(w, facts.Count);

                Frame cf = Frame.Of(corpses, 65535, 65535, 1f / 16);
                cf.Write(w);
                WriteCount(w, placements.Count); foreach (ulong p in placements) w.Write(p);
                WriteCount(w, classes.Count); foreach (ushort c in classes) w.Write(c);
                WriteCount(w, deaths.Count); foreach (ushort d in deaths) w.Write(d);
                WriteCount(w, corpses.Count);
                foreach (DfbPlaceFact f in corpses)
                {
                    w.Write((byte)placementIndex[(f.id >> MemberBits) & PlacementMask]);
                    w.Write((ushort)((f.id & ((1UL << MemberBits) - 1)) | ((ulong)deathIndex[f.death] << MemberBits)));
                    w.Write((byte)classIndex[f.cls]);
                    w.Write((ushort)Step(f.x, cf.minX, cf.cellXY, 65535, false));
                    w.Write((ushort)Step(f.y, cf.minY, cf.cellXY, 65535, false));
                    w.Write((ushort)Step(f.z, cf.minZ, cf.cellZ, 65535, false));
                    w.Write((byte)(f.angle >> 8));
                    w.Write((short)Math.Max(short.MinValue, Math.Min(short.MaxValue, f.health)));
                }

                Frame lf = Frame.Of(loose, 16383, 511, 0.5f);
                lf.Write(w);
                WriteCount(w, itemClasses.Count); foreach (ushort c in itemClasses) w.Write(c);
                WriteCount(w, loose.Count);
                List<ushort> carried = new List<ushort>();
                foreach (DfbPlaceFact f in loose)
                {
                    bool hasCarried = f.death != NoName;
                    ulong v = (ulong)itemClassIndex[f.cls]
                        | (ulong)Step(f.x, lf.minX, lf.cellXY, 16383, false) << 9
                        | (ulong)Step(f.y, lf.minY, lf.cellXY, 16383, false) << 23
                        | (ulong)Step(f.z, lf.minZ, lf.cellZ, 511, true) << 37	// up: a drop lands on the floor rather than in it
                        | (ulong)f.amount << 46
                        | (ulong)((f.flags & Dfb.FACT_DROPPED) != 0 ? 1 : 0) << 58
                        | (ulong)(hasCarried ? 1 : 0) << 59;
                    w.Write(v);
                    if (hasCarried)
                        carried.Add(f.death);
                }
                foreach (ushort c in carried) w.Write(c);

                WriteCount(w, gone.Count);
                foreach (KeyValuePair<ulong, SortedSet<int>> g in gone)
                {
                    int bytes = g.Value.Max / 8 + 1;
                    byte[] bits = new byte[bytes];
                    foreach (int i in g.Value)
                        bits[i >> 3] |= (byte)(1 << (i & 7));
                    w.Write(g.Key);
                    WriteCount(w, bytes);
                    w.Write(bits);
                    stats.gone += g.Value.Count;
                }

                WriteCount(w, exceptions.Count);
                foreach (DfbPlaceFact f in exceptions)
                {
                    w.Write(f.id); w.Write(f.kind); w.Write(f.flags); w.Write(f.cls); w.Write(f.death);
                    w.Write(f.x); w.Write(f.y); w.Write(f.z); w.Write(f.angle); w.Write(f.height); w.Write(f.health); w.Write(f.amount);
                }
            }
            byte[] data = ms.ToArray();
            stats.corpses = corpses.Count;
            stats.loose = loose.Count;
            stats.exceptions = exceptions.Count;
            stats.bytes = data.Length;
            return Convert.ToBase64String(data);
        }

        internal static bool Decode(string blob, out int mooks, List<DfbPlacePlan> plan, List<DfbPlaceFact> facts)
        {
            mooks = -1;
            byte[] data = Convert.FromBase64String(blob);
            using (BinaryReader r = new BinaryReader(new MemoryStream(data)))
            {
                if (r.ReadByte() != Version)
                    return false;
                mooks = r.ReadInt32();
                int n = r.Read7BitEncoded();
                for (int i = 0; i < n; i++)
                    plan.Add(new DfbPlacePlan { placement = r.ReadUInt64(), x = r.ReadSingle(), y = r.ReadSingle(), z = r.ReadSingle(), value = r.ReadInt32() });
                int total = r.Read7BitEncoded();
                int start = facts.Count;

                Frame cf = Frame.Read(r);
                ulong[] placements = new ulong[r.Read7BitEncoded()];
                for (int i = 0; i < placements.Length; i++) placements[i] = r.ReadUInt64();
                ushort[] classes = new ushort[r.Read7BitEncoded()];
                for (int i = 0; i < classes.Length; i++) classes[i] = r.ReadUInt16();
                ushort[] deaths = new ushort[r.Read7BitEncoded()];
                for (int i = 0; i < deaths.Length; i++) deaths[i] = r.ReadUInt16();
                n = r.Read7BitEncoded();
                for (int i = 0; i < n; i++)
                {
                    ulong placement = placements[r.ReadByte()];
                    ushort md = r.ReadUInt16();
                    DfbPlaceFact f = new DfbPlaceFact
                    {
                        kind = (byte)Dfb.FACT_CORPSE,
                        id = ((ulong)Dfb.MONSTER_TAG << (int)Dfb.MONSTER_TAG_SHIFT) | (placement << MemberBits) | (ulong)(md & ((1 << MemberBits) - 1)),
                        death = deaths[md >> MemberBits],
                        cls = classes[r.ReadByte()],
                    };
                    f.x = cf.minX + r.ReadUInt16() * cf.cellXY;
                    f.y = cf.minY + r.ReadUInt16() * cf.cellXY;
                    f.z = cf.minZ + r.ReadUInt16() * cf.cellZ;
                    f.angle = (ushort)(r.ReadByte() << 8);
                    f.health = r.ReadInt16();
                    facts.Add(f);
                }

                Frame lf = Frame.Read(r);
                ushort[] itemClasses = new ushort[r.Read7BitEncoded()];
                for (int i = 0; i < itemClasses.Length; i++) itemClasses[i] = r.ReadUInt16();
                n = r.Read7BitEncoded();
                List<int> needCarried = new List<int>();
                for (int i = 0; i < n; i++)
                {
                    ulong v = r.ReadUInt64();
                    DfbPlaceFact f = new DfbPlaceFact
                    {
                        kind = (byte)Dfb.FACT_ITEM,
                        flags = (byte)(Dfb.FACT_SESSION | (((v >> 58) & 1) != 0 ? Dfb.FACT_DROPPED : 0)),
                        cls = itemClasses[v & 511],
                        x = lf.minX + ((v >> 9) & 16383) * lf.cellXY,
                        y = lf.minY + ((v >> 23) & 16383) * lf.cellXY,
                        z = lf.minZ + ((v >> 37) & 511) * lf.cellZ,
                        amount = (int)((v >> 46) & 4095),
                        death = NoName,
                        health = 1000,   // an item's actor health is never changed (AActor default)
                    };
                    if (((v >> 59) & 1) != 0)
                        needCarried.Add(facts.Count);
                    facts.Add(f);
                }
                foreach (int at in needCarried)
                {
                    DfbPlaceFact f = facts[at];
                    f.death = r.ReadUInt16();
                    facts[at] = f;
                }

                n = r.Read7BitEncoded();
                for (int i = 0; i < n; i++)
                {
                    ulong prefix = r.ReadUInt64();
                    byte[] bits = r.ReadBytes(r.Read7BitEncoded());
                    for (int b = 0; b < bits.Length * 8; b++)
                        if ((bits[b >> 3] & (1 << (b & 7))) != 0)
                            facts.Add(new DfbPlaceFact { kind = (byte)Dfb.FACT_GONE, id = (prefix << MapItemIndexBits) | (ulong)b, cls = NoName, death = NoName });
                }

                n = r.Read7BitEncoded();
                for (int i = 0; i < n; i++)
                    facts.Add(new DfbPlaceFact
                    {
                        id = r.ReadUInt64(), kind = r.ReadByte(), flags = r.ReadByte(), cls = r.ReadUInt16(), death = r.ReadUInt16(),
                        x = r.ReadSingle(), y = r.ReadSingle(), z = r.ReadSingle(), angle = r.ReadUInt16(), height = r.ReadSingle(),
                        health = r.ReadInt32(), amount = r.ReadInt32(),
                    });
                return facts.Count - start == total;
            }
        }

        static void Write7BitEncoded(this BinaryWriter w, int value)
        {
            uint v = (uint)value;
            while (v >= 0x80) { w.Write((byte)(v | 0x80)); v >>= 7; }
            w.Write((byte)v);
        }

        static int Read7BitEncoded(this BinaryReader r)
        {
            int result = 0, shift = 0;
            byte b;
            do { b = r.ReadByte(); result |= (b & 0x7F) << shift; shift += 7; } while ((b & 0x80) != 0);
            return result;
        }
    }
}
