// Health and cheap ammo pickups for generated dungeons and building interiors, about one or two per room.
// A room is a connected patch of walkable floor at least CoreDepth steps from any wall, door, or ledge, so corridors
// and doorways get none. Placement and item choice come from a fixed seed (the place plus the room), so the same
// place always has the same pickups. The things are Doomerfall markers (mods/doomerfall, DoomerfallPickups.zs)
// that become stock or DRLA items in Doom.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

static partial class Program
{
    public const int PickupStimpackType = 31640, PickupClipType = 31641, PickupShellsType = 31642;
    // Dungeon values, then building interiors, whose rooms are small and full of furniture.
    static int PickupCoreDepth = 3;       // Graph steps (2 cells each) from the nearest edge of walkable floor.
    static int PickupMinRoomNodes = 6;    // Smaller wide spots, such as a corridor bend, are not rooms.
    static int PickupRoomNodes = 90;      // Core nodes in one typical room. Larger areas count as several rooms.
    const int PickupMinPartNodes = 300;   // A walkable part of the map not joined to the entrance gets pickups from this size.
    const double PickupSpacing = 96;      // Doom units between pickups in one room.
    const ulong PickupSalt = 0x5049434B55505331UL; // Keeps the loot seed apart from encounter seeds.

    static ulong pickupPlace;             // The place's identity: the dungeon map id, or the interior space id.
    static readonly List<int> pickupRoomCounts = new List<int>(); // Pickups in each room of the last map, for reports.

    const int PickupDungeon = 1, PickupInterior = 2;

    static void SetPickupPlace(int kind, long id)
    {
        pickupPlace = PickupMix(PickupMix(PickupSalt, kind), id);
        bool inside = kind == PickupInterior;
        PickupCoreDepth = inside ? 1 : 3;
        PickupMinRoomNodes = inside ? 8 : 6;
        PickupRoomNodes = inside ? 60 : 90;
    }

    static ulong PickupMix(ulong h, long v)
    {
        h ^= (ulong)v + 0x9E3779B97F4A7C15UL + (h << 6) + (h >> 2);
        h ^= h >> 30; h *= 0xBF58476D1CE4E5B9UL;
        h ^= h >> 27; h *= 0x94D049BB133111EBUL;
        return h ^ (h >> 31);
    }

    static void AppendPickups(StringBuilder map, List<Node> nodes, List<(int a, int b, bool door)> edges, int start)
    {
        pickupRoomCounts.Clear();
        if (nodes.Count == 0 || start < 0) return;
        var both = new HashSet<int>[nodes.Count]; // Level neighbors without a door between them.
        for (int k = 0; k < nodes.Count; k++) both[k] = new HashSet<int>();
        foreach (var e in edges)
        {
            if (!e.door && !nodes[e.a].Door && !nodes[e.b].Door) { both[e.a].Add(e.b); both[e.b].Add(e.a); }
        }

        // Floor joined to the entrance, or to a large part of the map. The walk graph does not follow lifts, moving
        // platforms, or teleports, so a strict walk from the entrance would leave most of some dungeons empty, while
        // small sealed pockets stay out.
        var undirected = new List<int>[nodes.Count];
        for (int k = 0; k < nodes.Count; k++) undirected[k] = new List<int>();
        foreach (var e in edges) { undirected[e.a].Add(e.b); undirected[e.b].Add(e.a); }
        var reach = new bool[nodes.Count];
        var seen = new bool[nodes.Count];
        var queue = new Queue<int>();
        var part = new List<int>();
        foreach (int root in new[] { start }.Concat(Enumerable.Range(0, nodes.Count)))
        {
            if (seen[root]) continue;
            part.Clear();
            seen[root] = true;
            queue.Enqueue(root);
            while (queue.Count > 0)
            {
                int k = queue.Dequeue();
                part.Add(k);
                foreach (int m in undirected[k])
                    if (!seen[m]) { seen[m] = true; queue.Enqueue(m); }
            }
            if (root == start || part.Count >= PickupMinPartNodes)
                foreach (int k in part) reach[k] = true;
        }

        // Steps to the nearest node that lacks a level neighbor in one of the four directions.
        var depth = new int[nodes.Count];
        Array.Fill(depth, int.MaxValue);
        foreach (var n in nodes)
        {
            int level = both[n.Id].Count(m => Math.Abs(nodes[m].F - n.F) <= StepHeight);
            if (level < 4 || n.Door) { depth[n.Id] = 0; queue.Enqueue(n.Id); }
        }
        while (queue.Count > 0)
        {
            int k = queue.Dequeue();
            foreach (int m in both[k])
                if (depth[m] > depth[k] + 1) { depth[m] = depth[k] + 1; queue.Enqueue(m); }
        }

        var room = new int[nodes.Count];
        Array.Fill(room, -1);
        var rooms = new List<List<Node>>();
        foreach (var n in nodes.OrderBy(n => n.J).ThenBy(n => n.I).ThenBy(n => n.F))
        {
            if (room[n.Id] >= 0 || !reach[n.Id] || depth[n.Id] < PickupCoreDepth) continue;
            var members = new List<Node>();
            room[n.Id] = rooms.Count;
            queue.Enqueue(n.Id);
            while (queue.Count > 0)
            {
                int k = queue.Dequeue();
                members.Add(nodes[k]);
                foreach (int m in both[k])
                    if (room[m] < 0 && reach[m] && depth[m] >= PickupCoreDepth) { room[m] = rooms.Count; queue.Enqueue(m); }
            }
            rooms.Add(members);
        }

        // Diagnostic: DD_PICKUP_DUMP=<file> writes every walkable node with its room (-1 for none) and depth.
        string dump = Environment.GetEnvironmentVariable("DD_PICKUP_DUMP");
        if (!string.IsNullOrEmpty(dump))
            System.IO.File.WriteAllLines(dump, nodes.Select(n => FormattableString.Invariant($"{n.I} {n.J} {n.F} {(reach[n.Id] ? room[n.Id] : -2)} {Math.Min(depth[n.Id], 99)}")));

        int placed = 0, skipped = 0;
        var types = new SortedDictionary<int, int>();
        foreach (var members in rooms)
        {
            if (members.Count < PickupMinRoomNodes) continue;
            // The room's first node in scan order names it, so its seed survives changes elsewhere in the map.
            var first = members.OrderBy(n => n.J).ThenBy(n => n.I).ThenBy(n => n.F).First();
            ulong seed = PickupMix(PickupMix(PickupMix(pickupPlace, first.I), first.J), first.F);
            int worth = Math.Max(1, (int)Math.Round(members.Count / (double)PickupRoomNodes));
            int want = 0;
            for (int r = 0; r < worth; r++) want += 1 + (int)(PickupMix(seed, 1000 + r) & 1);
            var order = members.Select(n => (n, key: PickupMix(PickupMix(PickupMix(seed, n.I), n.J), n.F))).OrderBy(p => p.key).Select(p => p.n);
            var spots = new List<(double x, double y, double z)>();
            foreach (var n in order)
            {
                if (spots.Count >= want) break;
                double x = minX + (n.I + 0.5) * cell, y = minY + (n.J + 0.5) * cell;
                if (spots.Any(s => (s.x - x) * (s.x - x) + (s.y - y) * (s.y - y) < PickupSpacing * PickupSpacing && Math.Abs(s.z - n.F) < ActorHeight)) continue;
                var spans = grid[Index(n.I, n.J)];
                var span = spans.FirstOrDefault(s => s.F == n.F && s.C - s.F >= ActorHeight);
                if (span == null || span.Door >= 0 || (span.Water != NoWater && (span.Water == WaterToCeiling || span.Water > span.F))) { skipped++; continue; }
                ulong pick = PickupMix(seed, 2000 + spots.Count) % 10;
                int type = pick < 4 ? PickupStimpackType : pick < 7 ? PickupClipType : PickupShellsType;
                map.Append(FormattableString.Invariant($"thing {{ x = {x:F1}; y = {y:F1}; height = {span.F - spans[0].F}.0; angle = 0; type = {type}; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; coop = true; dm = true; }}\n"));
                spots.Add((x, y, n.F));
                types[type] = types.GetValueOrDefault(type) + 1;
                placed++;
            }
            pickupRoomCounts.Add(spots.Count);
        }
        var histogram = pickupRoomCounts.GroupBy(c => c).OrderBy(g => g.Key).Select(g => $"{g.Key}:{g.Count()}");
        Console.WriteLine($"pickups: {placed} placed in {pickupRoomCounts.Count} rooms ({rooms.Count - pickupRoomCounts.Count} wide spots too small), "
            + $"per room {string.Join(" ", histogram)}, types {string.Join(" ", types.Select(t => t.Key + "x" + t.Value))}, {skipped} spots refused, "
            + $"reachable nodes {reach.Count(r => r)} of {nodes.Count}");
    }
}
