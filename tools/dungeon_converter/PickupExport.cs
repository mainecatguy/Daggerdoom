// Health, ammo and powerup pickups for generated dungeons, about one or two per room. Dungeons only: houses, shops
// and every other building interior get none (owner, 2026-11-26: "NO pickups in houses and shops").
// A room is a connected patch of walkable floor at least PickupCoreDepth steps from any wall, door, or ledge, so
// corridors and doorways get none. Placement and item choice come from fixed seeds, so the same dungeon always has the
// same pickups. The things are Doomerfall markers (mods/doomerfall, DoomerfallPickups.zs) that become stock or DRLA
// items in Doom.
//
// Item mix (owner, 2026-11-26): clips 30%, shells 25%, health 30%, rockets 10%, cells 3%, powerups 2% on average. Each
// dungeon leans toward one kind of ammo by a fixed amount taken from its loot identity (the loot seed of its map id, as
// Daggerfall's LootSeed builds it), so some dungeons are full of shells or rockets. The lean kind is drawn with the base
// odds and blended into the base ammo mix, so the average over many dungeons stays the base mix. Health keeps its 30%
// and powerups their 2% in every dungeon: the owner wants health restricted, not piled up in some dungeons.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

static partial class Program
{
    public const int PickupStimpackType = 31640, PickupClipType = 31641, PickupShellsType = 31642, PickupRocketsType = 31643,
        PickupCellsType = 31644, PickupBerserkType = 31645, PickupBlurType = 31646, PickupVisorType = 31647,
        PickupSoulsphereType = 31648, PickupMegasphereType = 31649, PickupInvulnerabilityType = 31650;
    // Ammo kinds a dungeon can lean toward, with the owner's base odds in percent.
    static readonly (int type, string name, double odds)[] PickupKinds =
    {
        (PickupClipType, "clips", 30), (PickupShellsType, "shells", 25), (PickupRocketsType, "rockets", 10), (PickupCellsType, "cells", 3),
    };
    const double PickupHealthShare = 0.30, PickupPowerupShare = 0.02;
    static readonly double PickupAmmoShare = 1 - PickupHealthShare - PickupPowerupShare;
    // Powerups (owner approved, 2026-11-26): Berserk, Partial Invisibility and the Light Amplification Visor about a
    // quarter each, Soulsphere 15%, Megasphere and Invulnerability 5% each.
    static readonly (int type, string name, double odds)[] PickupPowerups =
    {
        (PickupBerserkType, "berserk", 25), (PickupBlurType, "invisibility", 25), (PickupVisorType, "visor", 25),
        (PickupSoulsphereType, "soulsphere", 15), (PickupMegasphereType, "megasphere", 5), (PickupInvulnerabilityType, "invulnerability", 5),
    };
    // How hard a dungeon leans: strength = PickupLeanMax * v^3 for a fixed v in [0, 1). Most dungeons lean a little,
    // and about one in five gives over 40% of its ammo to the lean kind on top of the base mix.
    const double PickupLeanMax = 0.8;
    const long LootSeedDoomPickupLean = 8; // LootSeed.DoomPickupLean in Daggerfall Unity (Assets/Scripts/Game/Items/LootSeed.cs).

    const int PickupCoreDepth = 3;        // Graph steps (2 cells each) from the nearest edge of walkable floor.
    const int PickupMinRoomNodes = 6;     // Smaller wide spots, such as a corridor bend, are not rooms.
    const int PickupRoomNodes = 90;       // Core nodes in one typical room. Larger areas count as several rooms.
    const int PickupMinPartNodes = 300;   // A walkable part of the map not joined to the entrance gets pickups from this size.
    const double PickupSpacing = 96;      // Doom units between pickups in one room.
    const ulong PickupSalt = 0x5049434B55505331UL; // Keeps the placement seed apart from encounter seeds.

    static ulong pickupPlace;             // The dungeon's identity for placement, from its map id.
    static double[] pickupWeights;        // This dungeon's share of each PickupKinds entry; they sum to PickupAmmoShare.
    static int pickupLeanKind;            // Index in PickupKinds, for reports.
    static double pickupLeanStrength;
    static readonly List<int> pickupRoomCounts = new List<int>(); // Pickups in each room of the last map, for reports.

    const int PickupDungeon = 1;

    static void SetPickupPlace(int kind, long id)
    {
        pickupPlace = PickupMix(PickupMix(PickupSalt, kind), id);
        pickupWeights = PickupLean(id, out pickupLeanKind, out pickupLeanStrength);
    }

    // The dungeon's fixed mix. Only its map id goes in, so it is the same in every game and never follows the player.
    static double[] PickupLean(long mapId, out int leanKind, out double strength)
    {
        ulong h = (ulong)(uint)LootSeedOf(LootSeedDoomPickupLean, mapId);
        double total = PickupKinds.Sum(k => k.odds);
        double pick = PickupUnit(PickupMix(h, 1)) * total;
        leanKind = PickupKinds.Length - 1;
        for (int k = 0; k < PickupKinds.Length; k++)
        {
            if (pick < PickupKinds[k].odds) { leanKind = k; break; }
            pick -= PickupKinds[k].odds;
        }
        double v = PickupUnit(PickupMix(h, 2));
        strength = PickupLeanMax * v * v * v;
        var weights = new double[PickupKinds.Length];
        for (int k = 0; k < weights.Length; k++)
            weights[k] = PickupAmmoShare * ((1 - strength) * PickupKinds[k].odds / total + (k == leanKind ? strength : 0));
        return weights;
    }

    // The same value as Daggerfall Unity's LootSeed.Of(kind, null, values) (Assets/Scripts/Game/Items/LootSeed.cs).
    static int LootSeedOf(long kind, params long[] values)
    {
        static ulong Mix(ulong h, long v)
        {
            for (int k = 0; k < 8; k++) { h ^= (byte)(v >> (8 * k)); h *= 1099511628211UL; }
            return h;
        }
        ulong h = Mix(14695981039346656037UL, 0x6c6f6f74L);
        h = Mix(h, kind);
        foreach (long v in values) h = Mix(h, v);
        h ^= h >> 32;
        h *= 0x9E3779B97F4A7C15UL;
        h ^= h >> 29;
        return (int)(h ^ (h >> 32));
    }

    static double PickupUnit(ulong h) => (h >> 11) * (1.0 / (1UL << 53));

    // One item for a spot: a uniform roll through the health share, this dungeon's ammo weights, then the powerup share.
    static int PickupType(ulong roll)
    {
        double u = PickupUnit(roll);
        if (u < PickupHealthShare) return PickupStimpackType;
        u -= PickupHealthShare;
        for (int k = 0; k < PickupKinds.Length; k++)
        {
            if (u < pickupWeights[k]) return PickupKinds[k].type;
            u -= pickupWeights[k];
        }
        double p = Math.Min(u / PickupPowerupShare, 0.999999) * PickupPowerups.Sum(k => k.odds);
        foreach (var k in PickupPowerups)
        {
            if (p < k.odds) return k.type;
            p -= k.odds;
        }
        return PickupPowerups[PickupPowerups.Length - 1].type;
    }

    static string PickupName(int type) => type == PickupStimpackType ? "health" : PickupKinds.Concat(PickupPowerups).First(k => k.type == type).name;

    // --pickup-lean-survey: every dungeon's fixed lean and expected mix, and the average over all of them.
    static int PickupLeanSurvey(string arena2)
    {
        var maps = new DaggerfallConnect.Arena2.MapsFile(System.IO.Path.Combine(arena2, "MAPS.BSA"), DaggerfallConnect.FileUsage.UseMemory, true);
        var sum = new double[PickupKinds.Length];
        var leans = new int[PickupKinds.Length];
        int count = 0, strong = 0;
        for (int r = 0; r < maps.RegionCount; r++)
        {
            if (!maps.LoadRegion(r)) continue;
            var region = maps.GetRegion(r);
            if (region.MapNames == null) continue;
            for (int l = 0; l < region.LocationCount; l++)
            {
                var loc = maps.GetLocation(r, l);
                if (!loc.HasDungeon) continue;
                var w = PickupLean(loc.MapTableData.MapId, out int kind, out double strength);
                for (int k = 0; k < w.Length; k++) sum[k] += w[k];
                count++;
                leans[kind]++;
                if (strength > 0.4) strong++;
                Console.WriteLine(FormattableString.Invariant($"LEAN {loc.MapTableData.MapId} {region.Name}/{region.MapNames[l]} {PickupKinds[kind].name} {strength:F2} ")
                    + string.Join(" ", w.Select((x, k) => FormattableString.Invariant($"{PickupKinds[k].name}={x:P1}"))));
            }
        }
        Console.WriteLine($"dungeons {count}, lean strength over 0.4: {strong}");
        Console.WriteLine("average " + string.Join(" ", sum.Select((x, k) => FormattableString.Invariant($"{PickupKinds[k].name}={x / count:P2}"))) + FormattableString.Invariant($" health={PickupHealthShare:P2} powerups={PickupPowerupShare:P2}"));
        Console.WriteLine("lean kinds " + string.Join(" ", leans.Select((x, k) => $"{PickupKinds[k].name}={x}")));
        return 0;
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
                int type = PickupType(PickupMix(seed, 2000 + spots.Count));
                map.Append(FormattableString.Invariant($"thing {{ x = {x:F1}; y = {y:F1}; height = {span.F - spans[0].F}.0; angle = 0; type = {type}; skill1 = true; skill2 = true; skill3 = true; skill4 = true; skill5 = true; single = true; coop = true; dm = true; }}\n"));
                spots.Add((x, y, n.F));
                types[type] = types.GetValueOrDefault(type) + 1;
                placed++;
            }
            pickupRoomCounts.Add(spots.Count);
        }
        var histogram = pickupRoomCounts.GroupBy(c => c).OrderBy(g => g.Key).Select(g => $"{g.Key}:{g.Count()}");
        Console.WriteLine($"pickups: {placed} placed in {pickupRoomCounts.Count} rooms ({rooms.Count - pickupRoomCounts.Count} wide spots too small), "
            + $"per room {string.Join(" ", histogram)}, types {string.Join(" ", types.Select(t => PickupName(t.Key) + "x" + t.Value))}, lean {PickupKinds[pickupLeanKind].name} {pickupLeanStrength.ToString("F2", CultureInfo.InvariantCulture)}, {skipped} spots refused, "
            + $"reachable nodes {reach.Count(r => r)} of {nodes.Count}");
    }
}
