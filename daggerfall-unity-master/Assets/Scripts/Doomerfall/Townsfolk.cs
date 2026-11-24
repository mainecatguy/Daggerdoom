// Doomerfall: persistent townspeople. Pure generation, with no bridge, scene, or save state.
//
// A town's people are a function of its map id and the world time. Each person has a home, a few haunts, a waking
// window, and a habit of being out of doors or in. Each day's plan is rebuilt from (person seed, day), so habits hold
// while days differ. Walks follow Daggerfall's own city navigation grid (the rules of CityNavigation.SetRMBData), and a
// path is only found for someone near the player. The caller keeps the only lasting state: who has died.
//
// Coordinates are Daggerfall world units relative to the location's south-west corner, x east and z north.

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Utility;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal struct TownPose
    {
        public bool visible;
        public double x, z;     // relative to the town origin
        public double vx, vz;   // Daggerfall units per game second
        public float facing;    // Doom degrees: 0 east, counterclockwise
    }

    internal sealed class TownPerson
    {
        public enum Habit { Worker, Homebody, Roamer, NightOwl, Pacer, Guard }

        public ulong id;
        public int index;
        public ulong seed;
        public Habit habit;
        public bool guard;
        public Genders gender;
        public Races race;
        public int outfit, face, archive;
        public int home;                // site index
        public int[] haunts;            // site indices; for a worker the first is the workplace
        public double wake, sleep;      // hours after midnight; sleep may pass 24
        public double outdoors;         // chance that a stretch of time is spent outside
        public double speed;            // Daggerfall units per game second
        public double workEnd;

        internal int planDay = int.MinValue;
        internal List<TownRoster.Step> plan, planBefore;
        string name;

        public string Name
        {
            get
            {
                if (name == null)
                {
                    uint keep = DFRandom.Seed;
                    DFRandom.Seed = (uint)(seed >> 7);
                    NameHelper.BankTypes bank = race == Races.Redguard ? NameHelper.BankTypes.Redguard : race == Races.Nord ? NameHelper.BankTypes.Nord : NameHelper.BankTypes.Breton;
                    name = DaggerfallUnity.Instance.NameHelper.FullName(bank, gender);
                    DFRandom.Seed = keep;
                }
                return name;
            }
        }
    }

    internal sealed class TownRoster
    {
        public const int Cell = 64;                 // Daggerfall units per navigation cell
        const int BlockCells = 64;
        const double BaseSpeed = 5.0;               // about 1.5 m per real second at Daggerfall's 12x clock
        const int MaxPeople = 1200;

        internal struct Step
        {
            public double start, end;               // absolute hours since the epoch
            public int kind;                        // 0 inside, 1 outside, 2 walking
            public int a, b;                        // site indices
        }

        internal struct Site
        {
            public int key;
            public DFLocation.BuildingTypes type;
            public int cx, cy;                      // a walkable cell beside the building
        }

        public readonly int MapId;
        public readonly double OriginX, OriginZ;
        public readonly int GridW, GridH;
        public readonly List<Site> Sites = new List<Site>();
        public readonly TownPerson[] People;
        readonly byte[] weight;
        readonly Dictionary<long, Vector2[]> paths = new Dictionary<long, Vector2[]>();
        readonly Dictionary<long, Vector2> anchors = new Dictionary<long, Vector2>();
        readonly List<int> homes = new List<int>(), work = new List<int>(), taverns = new List<int>();

        // Daggerfall's populated location types (StreamingWorld adds a PopulationManager to these).
        public static bool HasTownsfolk(DFLocation location)
        {
            switch (location.MapTableData.LocationType)
            {
                case DFRegion.LocationTypes.TownCity:
                case DFRegion.LocationTypes.TownHamlet:
                case DFRegion.LocationTypes.TownVillage:
                case DFRegion.LocationTypes.HomeFarms:
                case DFRegion.LocationTypes.HomeWealthy:
                case DFRegion.LocationTypes.ReligionTemple:
                case DFRegion.LocationTypes.Tavern:
                    return location.Exterior.ExteriorData.Width > 0 && location.Exterior.ExteriorData.Height > 0;
                default:
                    return false;
            }
        }

        public TownRoster(DFLocation location, Races race)
        {
            MapId = location.MapTableData.MapId;
            Rect rect = DaggerfallLocation.GetLocationRect(location);
            OriginX = rect.xMin;
            OriginZ = rect.yMin;
            int width = location.Exterior.ExteriorData.Width, height = location.Exterior.ExteriorData.Height;
            GridW = width * BlockCells;
            GridH = height * BlockCells;
            weight = new byte[GridW * GridH];
            DFBlock[] blocks = RMBLayout.GetLocationBuildingData(location);
            for (int by = 0; by < height; by++)
                for (int bx = 0; bx < width; bx++)
                {
                    DFBlock block = blocks[by * width + bx];
                    for (int y = 0; y < BlockCells; y++)
                        for (int x = 0; x < BlockCells; x++)
                        {
                            if (block.RmbBlock.FldHeader.AutoMapData[y * BlockCells + x] != 0)
                                continue;
                            int gy = (height - 1 - by) * BlockCells + y;
                            weight[gy * GridW + bx * BlockCells + x] = TileWeight(block.RmbBlock.FldHeader.GroundData.GroundTiles[x / 4, y / 4].TextureRecord);
                        }
                    BuildingSummary[] buildings = RMBLayout.GetBuildingData(block, bx, by);
                    if (buildings == null)
                        continue;
                    foreach (BuildingSummary b in buildings)
                    {
                        double px = bx * RMBLayout.RMBSide / MeshReader.GlobalScale + b.Position.x / MeshReader.GlobalScale;
                        double pz = by * RMBLayout.RMBSide / MeshReader.GlobalScale + b.Position.z / MeshReader.GlobalScale;
                        int cx, cy;
                        if (Nearest(CellX(px), CellY(pz), 24, out cx, out cy))
                            Sites.Add(new Site { key = b.buildingKey, type = b.BuildingType, cx = cx, cy = cy });
                    }
                }
            for (int s = 0; s < Sites.Count; s++)
            {
                DFLocation.BuildingTypes t = Sites[s].type;
                if (t >= DFLocation.BuildingTypes.House1 && t <= DFLocation.BuildingTypes.House6)
                    homes.Add(s);
                else if (t == DFLocation.BuildingTypes.Tavern)
                    taverns.Add(s);
                if (t <= DFLocation.BuildingTypes.Palace && t != DFLocation.BuildingTypes.HouseForSale && t != DFLocation.BuildingTypes.Town4 && t >= 0)
                    work.Add(s);
            }
            if (homes.Count == 0)
                for (int s = 0; s < Sites.Count; s++)
                    homes.Add(s);
            if (work.Count == 0)
                work.AddRange(homes);

            // Daggerfall keeps 24 wanderers per 16 blocks (at most 4 x 24) within 150 m of the player. Spread that density
            // over the whole town, and double it because about half the town is indoors at any daytime moment.
            int blockCount = width * height;
            int pool = Mathf.Clamp(blockCount / 16, 1, 4) * 24;
            double perBlock = pool * (102.4 * 102.4) / (Math.PI * 150 * 150) * 1.9;
            int count = Sites.Count == 0 ? 0 : Mathf.Clamp((int)Math.Round(blockCount * perBlock), 4, MaxPeople);
            People = new TownPerson[count];
            ulong townSeed = Hash(0x746f776e73UL, (ulong)(uint)MapId);
            for (int i = 0; i < count; i++)
                People[i] = MakePerson(townSeed, i, race);
        }

        public static ulong MakeId(int mapId, int index)
        {
            ulong h = Hash(Hash(0x7065726fUL, (ulong)(uint)mapId), (ulong)index);
            return ((ulong)Dfb.TOWNSPERSON_TAG << 61) | (h & ((1UL << 61) - 1));
        }

        // The archives MobilePersonBillboard uses, by race, gender, and outfit.
        static readonly int[] MaleRedguard = { 381, 382, 383, 384 }, FemaleRedguard = { 395, 396, 397, 398 };
        static readonly int[] MaleNord = { 387, 388, 389, 390 }, FemaleNord = { 392, 393, 451, 452 };
        static readonly int[] MaleBreton = { 385, 386, 391, 394 }, FemaleBreton = { 453, 454, 455, 456 };
        const int GuardArchive = 399;

        TownPerson MakePerson(ulong townSeed, int index, Races race)
        {
            ulong seed = Hash(townSeed, (ulong)index + 1);
            Rng r = new Rng(seed);
            TownPerson p = new TownPerson { index = index, seed = seed, id = MakeId(MapId, index), race = race };
            // Daggerfall's own appearance rule (MobilePersonNPC.RandomiseNPC): one in 32 is a guard.
            p.guard = r.Next(32) == 0;
            p.gender = p.guard ? Genders.Male : r.Next(2) == 1 ? Genders.Female : Genders.Male;
            p.outfit = p.guard ? 0 : r.Next(4);
            p.face = r.Next(24);
            int[] set = race == Races.Redguard ? (p.gender == Genders.Male ? MaleRedguard : FemaleRedguard)
                : race == Races.Nord ? (p.gender == Genders.Male ? MaleNord : FemaleNord)
                : (p.gender == Genders.Male ? MaleBreton : FemaleBreton);
            p.archive = p.guard ? GuardArchive : set[p.outfit];
            p.home = homes[r.Next(homes.Count)];
            p.speed = BaseSpeed * r.Range(0.8, 1.2);
            p.wake = r.Normal(6.5, 0.9, 4.5, 9.5);
            p.sleep = r.Normal(21.5, 1.0, 19, 24.5);
            p.outdoors = r.Range(0.35, 0.8);
            double roll = r.Value();
            if (p.guard)
            {
                // A watch patrol: a loop of four stops, by day or by night.
                p.habit = TownPerson.Habit.Guard;
                p.haunts = new[] { Near(r, p.home, work), Near(r, p.home, work), Near(r, p.home, Sites), Near(r, p.home, work) };
                bool night = r.Next(3) == 0;
                p.wake = night ? 18 + r.Range(-0.5, 0.5) : 6 + r.Range(-0.5, 0.5);
                p.sleep = p.wake + 12;
                p.outdoors = 1;
                p.speed *= 0.85;
            }
            else if (roll < 0.36)
            {
                p.habit = TownPerson.Habit.Worker;
                p.haunts = new[] { Near(r, p.home, work), taverns.Count > 0 ? Near(r, p.home, taverns) : Near(r, p.home, work) };
                p.workEnd = r.Normal(17.5, 0.8, 15.5, 20);
            }
            else if (roll < 0.58)
            {
                p.habit = TownPerson.Habit.Homebody;
                p.haunts = new[] { Near(r, p.home, work) };
                p.outdoors = r.Range(0.5, 0.95);
            }
            else if (roll < 0.86)
            {
                p.habit = TownPerson.Habit.Roamer;
                p.haunts = new[] { Near(r, p.home, work), Near(r, p.home, Sites), Near(r, p.home, work) };
            }
            else if (roll < 0.96)
            {
                // Sleeps by day and keeps the taverns busy at night.
                p.habit = TownPerson.Habit.NightOwl;
                p.wake = r.Normal(15, 1.2, 12, 18);
                p.sleep = p.wake + r.Range(10, 13);
                p.haunts = new[] { taverns.Count > 0 ? Near(r, p.home, taverns) : Near(r, p.home, work), Near(r, p.home, Sites) };
            }
            else
            {
                // A restless walker who crosses town between two far places at all hours.
                p.habit = TownPerson.Habit.Pacer;
                p.haunts = new[] { Sites.Count > 0 ? r.Next(Sites.Count) : p.home, Near(r, p.home, work) };
                p.wake = r.Range(0, 6);
                p.sleep = p.wake + r.Range(17, 21);
                p.outdoors = 0.95;
            }
            return p;
        }

        // The nearest of three random candidates: people keep to their own part of town without being bound to it.
        int Near(Rng r, int from, List<int> pool)
        {
            int best = pool[r.Next(pool.Count)];
            for (int k = 0; k < 2; k++)
            {
                int c = pool[r.Next(pool.Count)];
                if (SiteDistance(from, c) < SiteDistance(from, best))
                    best = c;
            }
            return best;
        }

        int Near(Rng r, int from, List<Site> all)
        {
            int best = r.Next(all.Count);
            for (int k = 0; k < 2; k++)
            {
                int c = r.Next(all.Count);
                if (SiteDistance(from, c) < SiteDistance(from, best))
                    best = c;
            }
            return best;
        }

        double SiteDistance(int a, int b)
        {
            double dx = Sites[a].cx - Sites[b].cx, dy = Sites[a].cy - Sites[b].cy;
            return Math.Sqrt(dx * dx + dy * dy) * Cell;
        }

        // ---- Daily plans ----

        List<Step> BuildPlan(TownPerson p, int day)
        {
            Rng r = new Rng(Hash(p.seed, (ulong)(uint)day ^ 0x5bd1e995UL));
            List<Step> steps = new List<Step>();
            double t = day * 24.0 + p.wake + r.Range(-0.4, 0.4);
            double end = day * 24.0 + p.sleep + r.Range(-0.4, 0.4);
            int at = p.home;
            int stop = 0;
            bool tavernTonight = r.Value() < 0.45;
            while (t < end - 0.1)
            {
                int next;
                double dwell;
                switch (p.habit)
                {
                    case TownPerson.Habit.Worker:
                        if (stop == 0) { next = p.haunts[0]; dwell = day * 24.0 + p.workEnd + r.Range(-0.3, 0.3) - t; }
                        else if (stop == 1 && tavernTonight) { next = p.haunts[1]; dwell = r.Range(1, 3); }
                        else { next = p.home; dwell = end - t; }
                        break;
                    case TownPerson.Habit.Guard:
                    case TownPerson.Habit.Pacer:
                        next = p.haunts[stop % p.haunts.Length];
                        dwell = p.habit == TownPerson.Habit.Guard ? r.Range(0.1, 0.3) : r.Range(0.05, 0.5);
                        break;
                    case TownPerson.Habit.Homebody:
                        next = stop % 2 == 1 && r.Value() < 0.6 ? p.haunts[0] : p.home;
                        dwell = r.Range(0.75, 3);
                        break;
                    default:
                        next = r.Value() < 0.25 ? p.home : p.haunts[r.Next(p.haunts.Length)];
                        dwell = r.Range(0.5, 2.5);
                        break;
                }
                stop++;
                if (next != at)
                {
                    double walk = SiteDistance(at, next) * 1.35 / p.speed / 3600 + 0.02;
                    steps.Add(new Step { start = t, end = t + walk, kind = 2, a = at, b = next });
                    t += walk;
                    at = next;
                }
                dwell = Math.Max(0.25, Math.Min(dwell, end - t));
                double until = t + dwell;
                while (t < until - 0.01)
                {
                    double chunk = Math.Min(until - t, r.Range(0.4, 1.4));
                    steps.Add(new Step { start = t, end = t + chunk, kind = r.Value() < p.outdoors ? 1 : 0, a = at, b = at });
                    t += chunk;
                }
                if (steps.Count > 200)
                    break;
            }
            if (at != p.home)
            {
                double walk = SiteDistance(at, p.home) * 1.35 / p.speed / 3600 + 0.02;
                steps.Add(new Step { start = t, end = t + walk, kind = 2, a = at, b = p.home });
            }
            return steps;
        }

        void EnsurePlans(TownPerson p, int day)
        {
            if (p.planDay == day)
                return;
            p.planBefore = p.planDay == day - 1 ? p.plan : BuildPlan(p, day - 1);
            p.plan = BuildPlan(p, day);
            p.planDay = day;
        }

        // Cheap: where the person is, or which walk they are on, with no path search.
        public bool FindStep(TownPerson p, double hours, out Step step)
        {
            EnsurePlans(p, (int)Math.Floor(hours / 24));
            foreach (List<Step> plan in new[] { p.plan, p.planBefore })
                foreach (Step s in plan)
                    if (hours >= s.start && hours < s.end)
                    {
                        step = s;
                        return true;
                    }
            step = default(Step);
            return false;
        }

        // A rough position for a step, for deciding whether it is worth a full pose.
        public void Bounds(TownPerson p, Step s, out double x0, out double z0, out double x1, out double z1)
        {
            Vector2 a = Anchor(p, s.a), b = Anchor(p, s.b);
            x0 = Math.Min(a.x, b.x); x1 = Math.Max(a.x, b.x);
            z0 = Math.Min(a.y, b.y); z1 = Math.Max(a.y, b.y);
        }

        public TownPose Pose(TownPerson p, Step s, double hours)
        {
            TownPose pose = new TownPose();
            if (s.kind == 0)
                return pose;
            double seconds = (hours - s.start) * 3600;
            if (s.kind == 2)
            {
                Vector2[] path = Path(Anchor(p, s.a), Anchor(p, s.b));
                if (path == null)
                    return pose;
                double duration = (s.end - s.start) * 3600;
                return Along(path, seconds / duration, duration);
            }
            // Outside: stand, or pace between two nearby spots with pauses, as a periodic function of time.
            Rng r = new Rng(Hash(p.seed, (ulong)(s.start * 3600)));
            Vector2 a = Anchor(p, s.a);
            Vector2 b;
            float rest = (float)(r.Value() * 360);
            if (r.Value() < 0.35 || !Wander(r, a, out b))
            {
                pose.visible = true;
                pose.x = a.x; pose.z = a.y;
                pose.facing = rest;
                return pose;
            }
            double length = (b - a).magnitude, walk = length / (p.speed * 0.7), pause = r.Range(20, 120);
            double cycle = 2 * (walk + pause), u = seconds % cycle;
            Vector2[] line = { a, b };
            if (u < pause) { pose = Along(line, 0); pose.vx = pose.vz = 0; pose.facing = rest; }
            else if (u < pause + walk) pose = Along(line, (u - pause) / walk, walk);
            else if (u < 2 * pause + walk) { pose = Along(line, 1); pose.vx = pose.vz = 0; pose.facing = rest + 180; }
            else pose = Along(new[] { b, a }, (u - 2 * pause - walk) / walk, walk);
            return pose;
        }

        // A point along a polyline at fraction f, with the velocity that crossing it in duration seconds needs.
        static TownPose Along(Vector2[] path, double f, double duration = 0)
        {
            double total = 0;
            for (int i = 1; i < path.Length; i++)
                total += (path[i] - path[i - 1]).magnitude;
            f = Math.Max(0, Math.Min(1, f));
            double want = f * total;
            TownPose pose = new TownPose { visible = true, x = path[0].x, z = path[0].y };
            for (int i = 1; i < path.Length; i++)
            {
                Vector2 d = path[i] - path[i - 1];
                double len = d.magnitude;
                if (len <= 0)
                    continue;
                pose.facing = Mathf.Atan2(d.y, d.x) * Mathf.Rad2Deg;
                if (want <= len || i == path.Length - 1)
                {
                    double k = Math.Min(1, want / len);
                    pose.x = path[i - 1].x + d.x * k;
                    pose.z = path[i - 1].y + d.y * k;
                    if (duration > 0 && f < 1)
                    {
                        double speed = total / duration;
                        pose.vx = d.x / len * speed;
                        pose.vz = d.y / len * speed;
                    }
                    return pose;
                }
                want -= len;
            }
            return pose;
        }

        // ---- Grid helpers ----

        int CellX(double x) { return Mathf.Clamp((int)(x / Cell), 0, GridW - 1); }
        int CellY(double z) { return Mathf.Clamp(GridH - 1 - (int)(z / Cell), 0, GridH - 1); }
        Vector2 CellCenter(int cx, int cy) { return new Vector2(cx * Cell + Cell / 2, (GridH - cy) * Cell - Cell / 2); }
        bool Walkable(int cx, int cy) { return cx >= 0 && cy >= 0 && cx < GridW && cy < GridH && weight[cy * GridW + cx] > 0; }

        bool Nearest(int cx, int cy, int radius, out int ox, out int oy)
        {
            for (int ring = 0; ring <= radius; ring++)
                for (int dy = -ring; dy <= ring; dy++)
                    for (int dx = -ring; dx <= ring; dx++)
                    {
                        if (Math.Max(Math.Abs(dx), Math.Abs(dy)) != ring || !Walkable(cx + dx, cy + dy))
                            continue;
                        ox = cx + dx; oy = cy + dy;
                        return true;
                    }
            ox = oy = 0;
            return false;
        }

        // Each person has their own spot near each place, so a crowd does not stand on one cell.
        Vector2 Anchor(TownPerson p, int site)
        {
            long key = (long)p.index << 20 | (long)site;
            Vector2 at;
            if (anchors.TryGetValue(key, out at))
                return at;
            Site s = Sites[site];
            Rng r = new Rng(Hash(p.seed, (ulong)site + 77));
            int cx = s.cx, cy = s.cy;
            for (int tries = 0; tries < 6; tries++)
            {
                int nx = s.cx + r.Next(7) - 3, ny = s.cy + r.Next(7) - 3;
                if (Walkable(nx, ny) && Clear(s.cx, s.cy, nx, ny)) { cx = nx; cy = ny; break; }
            }
            at = CellCenter(cx, cy) + new Vector2((float)r.Range(-20, 20), (float)r.Range(-20, 20));
            anchors[key] = at;
            return at;
        }

        bool Wander(Rng r, Vector2 from, out Vector2 to)
        {
            int cx = CellX(from.x), cy = CellY(from.y);
            for (int tries = 0; tries < 6; tries++)
            {
                int nx = cx + r.Next(13) - 6, ny = cy + r.Next(13) - 6;
                if ((nx != cx || ny != cy) && Walkable(nx, ny) && Clear(cx, cy, nx, ny))
                {
                    to = CellCenter(nx, ny);
                    return true;
                }
            }
            to = from;
            return false;
        }

        // True when every cell on the straight line between two cells is walkable.
        bool Clear(int x0, int y0, int x1, int y1)
        {
            int steps = Math.Max(Math.Abs(x1 - x0), Math.Abs(y1 - y0));
            for (int i = 0; i <= steps; i++)
            {
                double k = steps == 0 ? 0 : (double)i / steps;
                if (!Walkable((int)Math.Round(x0 + (x1 - x0) * k), (int)Math.Round(y0 + (y1 - y0) * k)))
                    return false;
            }
            return true;
        }

        // A* over walkable cells, 8-connected, preferring Daggerfall's better tiles (roads), then straightened.
        Vector2[] Path(Vector2 from, Vector2 to)
        {
            int sx = CellX(from.x), sy = CellY(from.y), tx = CellX(to.x), ty = CellY(to.y);
            long key = ((long)(sy * GridW + sx) << 32) | (uint)(ty * GridW + tx);
            Vector2[] found;
            if (paths.TryGetValue(key, out found))
                return found;
            found = Search(sx, sy, tx, ty);
            if (found != null)
            {
                found[0] = from;
                found[found.Length - 1] = to;
            }
            paths[key] = found;
            return found;
        }

        Vector2[] Search(int sx, int sy, int tx, int ty)
        {
            if (!Walkable(sx, sy) || !Walkable(tx, ty))
                return null;
            int start = sy * GridW + sx, goal = ty * GridW + tx;
            Dictionary<int, float> cost = new Dictionary<int, float> { { start, 0 } };
            Dictionary<int, int> came = new Dictionary<int, int>();
            SortedSet<(float, int)> open = new SortedSet<(float, int)> { (0, start) };
            int expanded = 0;
            while (open.Count > 0 && expanded < 60000)
            {
                (float, int) head = open.Min;
                open.Remove(head);
                int cur = head.Item2;
                if (cur == goal)
                    break;
                expanded++;
                int cx = cur % GridW, cy = cur / GridW;
                for (int dy = -1; dy <= 1; dy++)
                    for (int dx = -1; dx <= 1; dx++)
                    {
                        if ((dx == 0 && dy == 0) || !Walkable(cx + dx, cy + dy) || (dx != 0 && dy != 0 && (!Walkable(cx + dx, cy) || !Walkable(cx, cy + dy))))
                            continue;
                        int n = (cy + dy) * GridW + cx + dx;
                        float step = (dx != 0 && dy != 0 ? 1.414f : 1f) * (1f + 6f / weight[n]);
                        float g = cost[cur] + step;
                        float old;
                        if (cost.TryGetValue(n, out old) && old <= g)
                            continue;
                        if (cost.ContainsKey(n))
                            open.Remove((old + Heuristic(n, tx, ty), n));
                        cost[n] = g;
                        came[n] = cur;
                        open.Add((g + Heuristic(n, tx, ty), n));
                    }
            }
            if (!came.ContainsKey(goal) && start != goal)
                return null;
            List<int> cells = new List<int> { goal };
            while (cells[cells.Count - 1] != start)
                cells.Add(came[cells[cells.Count - 1]]);
            cells.Reverse();
            // Keep only the corners a straight walk cannot skip.
            List<Vector2> points = new List<Vector2> { CellCenter(sx, sy) };
            int anchor = 0;
            for (int i = 2; i < cells.Count; i++)
                if (!Clear(cells[anchor] % GridW, cells[anchor] / GridW, cells[i] % GridW, cells[i] / GridW))
                {
                    anchor = i - 1;
                    points.Add(CellCenter(cells[anchor] % GridW, cells[anchor] / GridW));
                }
            points.Add(CellCenter(tx, ty));
            return points.ToArray();
        }

        float Heuristic(int n, int tx, int ty)
        {
            int dx = Math.Abs(n % GridW - tx), dy = Math.Abs(n / GridW - ty);
            return (Math.Max(dx, dy) + 0.414f * Math.Min(dx, dy)) * 1.4f;
        }

        // CityNavigation.GetTileWeight.
        static byte TileWeight(int tile)
        {
            switch (tile)
            {
                case 0: case 5: case 6: case 20: case 21: case 30: case 31: return 0;  // water and its edges
                case 3: return 4;                                                      // stone
                case 1: return 6;                                                      // dirt
                case 2: return 12;                                                     // grass
                case 46: case 47: case 55: return 15;                                  // road
                default: return 7;
            }
        }

        // ---- Deterministic randomness ----

        internal static ulong Hash(ulong a, ulong b)
        {
            ulong z = a * 0x9E3779B97F4A7C15UL + b + 0x632BE59BD9B4E019UL;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }

        internal struct Rng
        {
            ulong state;
            public Rng(ulong seed) { state = seed; }
            public ulong NextU64() { state += 0x9E3779B97F4A7C15UL; return Hash(state, 0); }
            public double Value() { return (NextU64() >> 11) * (1.0 / 9007199254740992.0); }
            public int Next(int n) { return n <= 0 ? 0 : (int)(NextU64() % (ulong)n); }
            public double Range(double lo, double hi) { return lo + (hi - lo) * Value(); }
            public double Normal(double mean, double sd, double lo, double hi)
            {
                double u = Math.Max(1e-9, Value()), v = Value();
                double n = Math.Sqrt(-2 * Math.Log(u)) * Math.Cos(2 * Math.PI * v);
                return Math.Max(lo, Math.Min(hi, mean + n * sd));
            }
        }
    }
}
