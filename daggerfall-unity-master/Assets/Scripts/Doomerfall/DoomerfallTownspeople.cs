// Doomerfall: Daggerfall's side of persistent townspeople. Runs only in a bridge session.
//
// Townsfolk.cs generates each town's people from its map id and the world time. This lists the ones near the Doom
// player, with their motion, so Doom can draw them. The only saved state is who has died. A death that Doom reports
// goes in this ledger, and that person is never listed again.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Utility;
using FullSerializer;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallTownspeople : MonoBehaviour
    {
        const float PollSeconds = 0.5f;
        const double ViewRange = 6000;          // Daggerfall recycles wanderers past 150 m
        const double OutsideRect = 2500;        // PopulationManager's margin around the location
        const int MaxRows = 128;
        const string LedgerFile = "DoomerfallTownspeople.json";

        [fsObject("v1")]
        public sealed class LedgerData
        {
            public List<string> dead = new List<string>();
        }

        struct Candidate
        {
            public TownPerson person;
            public TownPose pose;
            public double distance;
        }

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        LedgerData ledger = new LedgerData();
        readonly HashSet<ulong> dead = new HashSet<ulong>();
        readonly List<Candidate> candidates = new List<Candidate>();
        TownRoster roster;
        uint generation;
        bool listedEmpty = true, report;
        float nextPoll, nextReport;
        double testHour = -1;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            string[] args = Environment.GetCommandLineArgs();
            report = Array.IndexOf(args, "-dftownreport") >= 0;
            int at = Array.IndexOf(args, "-dftownhour"); // Test only: sets the clock once, so separate launches share a time.
            if (at >= 0 && at + 1 < args.Length)
                double.TryParse(args[at + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out testHour);
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame += OnStartGame;
        }

        void OnDestroy()
        {
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame -= OnStartGame;
        }

        void OnStartGame(object sender, EventArgs e)
        {
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return;
            ForgetWorld();
        }

        internal void ForgetWorld()
        {
            ledger = new LedgerData();
            dead.Clear();
        }

        internal void OnRequest()
        {
            nextPoll = 0;
        }

        // The roster of the town the player is in, for later work such as dialogue. Null away from towns.
        internal TownRoster Roster { get { return roster; } }

        internal TownPerson FindPerson(ulong id)
        {
            if (roster == null || dead.Contains(id))
                return null;
            foreach (TownPerson p in roster.People)
                if (p.id == id)
                    return p;
            return null;
        }

        void Update()
        {
            if (Time.unscaledTime < nextPoll)
                return;
            nextPoll = Time.unscaledTime + PollSeconds;
            if (sync.LoadRunning || !GameManager.HasInstance || !sync.InGame)
                return;
            if (testHour >= 0)
            {
                DaggerfallDateTime now = DaggerfallUnity.Instance.WorldTime.Now;
                now.FromSeconds((now.ToSeconds() / 86400UL) * 86400UL + (ulong)(testHour * 3600));
                bridge.LogLine(string.Format("town: test clock set to {0}", now.LongDateTimeString()));
                testHour = -1;
            }
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            if (peer.worldContext != Dfb.WORLD_EXTERIOR || !gps.HasCurrentLocation || !TownRoster.HasTownsfolk(gps.CurrentLocation))
            {
                PublishEmpty();
                return;
            }
            DFLocation location = gps.CurrentLocation;
            if (roster == null || roster.MapId != location.MapTableData.MapId)
            {
                Stopwatch clock = Stopwatch.StartNew();
                roster = new TownRoster(location, PopulationRace(gps));
                bridge.LogLine(string.Format("town: {0} map {1} has {2} people and {3} places, built in {4} ms", location.Name, roster.MapId, roster.People.Length, roster.Sites.Count, clock.ElapsedMilliseconds));
                if (report)
                    Census();
            }
            double px = peer.worldX - roster.OriginX, pz = peer.worldZ - roster.OriginZ;
            double width = roster.GridW * TownRoster.Cell, height = roster.GridH * TownRoster.Cell;
            if (px < -OutsideRect || pz < -OutsideRect || px > width + OutsideRect || pz > height + OutsideRect)
            {
                PublishEmpty();
                return;
            }
            double hours = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() / 3600.0;
            Collect(hours, px, pz);
            Publish();
            if (report && Time.unscaledTime >= nextReport)
            {
                nextReport = Time.unscaledTime + 2;
                Report(hours, px, pz);
            }
        }

        void Collect(double hours, double px, double pz)
        {
            candidates.Clear();
            foreach (TownPerson p in roster.People)
            {
                if (dead.Contains(p.id))
                    continue;
                TownRoster.Step step;
                if (!roster.FindStep(p, hours, out step) || step.kind == 0)
                    continue;
                double x0, z0, x1, z1;
                roster.Bounds(p, step, out x0, out z0, out x1, out z1);
                if (px < x0 - ViewRange || px > x1 + ViewRange || pz < z0 - ViewRange || pz > z1 + ViewRange)
                    continue;
                TownPose pose = roster.Pose(p, step, hours);
                if (!pose.visible)
                    continue;
                double dx = pose.x - px, dz = pose.z - pz, d = Math.Sqrt(dx * dx + dz * dz);
                if (d <= ViewRange)
                    candidates.Add(new Candidate { person = p, pose = pose, distance = d });
            }
            candidates.Sort((a, b) => a.distance.CompareTo(b.distance));
            if (candidates.Count > MaxRows)
                candidates.RemoveRange(MaxRows, candidates.Count - MaxRows);
        }

        void Publish()
        {
            float scale = DaggerfallUnity.Instance.WorldTime.TimeScale;
            if (GameManager.IsGamePaused)
                scale = 0;
            generation++;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_TOWNSFOLK_BEGIN;
            e.tic = (uint)Time.frameCount;
            e.townsfolk.generation = generation;
            e.townsfolk.count = (uint)candidates.Count;
            e.townsfolk.mapId = roster.MapId;
            e.townsfolk.originX = roster.OriginX;
            e.townsfolk.originZ = roster.OriginZ;
            bridge.Send(ref e);
            foreach (Candidate c in candidates)
            {
                DfbEvent row = default(DfbEvent);
                row.kind = Dfb.KIND_TOWNSPERSON;
                row.tic = (uint)Time.frameCount;
                row.townsperson.id = c.person.id;
                row.townsperson.generation = generation;
                row.townsperson.archive = (ushort)c.person.archive;
                row.townsperson.flags = (ushort)(c.person.guard ? Dfb.TOWNSPERSON_GUARD : 0);
                row.townsperson.x = (float)c.pose.x;
                row.townsperson.y = (float)c.pose.z;
                row.townsperson.vx = (float)(c.pose.vx * scale);
                row.townsperson.vy = (float)(c.pose.vz * scale);
                row.townsperson.facing = c.pose.facing;
                bridge.Send(ref row);
            }
            e.kind = Dfb.KIND_TOWNSFOLK_END;
            bridge.Send(ref e);
            listedEmpty = candidates.Count == 0;
        }

        void PublishEmpty()
        {
            if (listedEmpty)
                return;
            candidates.Clear();
            generation++;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_TOWNSFOLK_BEGIN;
            e.tic = (uint)Time.frameCount;
            e.townsfolk.generation = generation;
            bridge.Send(ref e);
            e.kind = Dfb.KIND_TOWNSFOLK_END;
            bridge.Send(ref e);
            listedEmpty = true;
        }

        static Races PopulationRace(PlayerGPS gps)
        {
            switch (gps.ClimateSettings.People)
            {
                case FactionFile.FactionRaces.Redguard: return Races.Redguard;
                case FactionFile.FactionRaces.Nord: return Races.Nord;
                default: return Races.Breton;
            }
        }

        internal void OnDeath(ulong id, double worldX, double worldZ)
        {
            if (!dead.Add(id))
            {
                bridge.LogLine("town: repeat death ignored " + id.ToString("x16"));
                return;
            }
            ledger.dead.Add(id.ToString("x16"));
            TownPerson p = FindPersonAnyState(id);
            bridge.LogLine(string.Format("town: death {0:x16} {1} at {2:F0},{3:F0}; {4} dead in all", id, p != null ? p.Name + " (" + p.habit + ")" : "not in this town", worldX, worldZ, dead.Count));
            nextPoll = 0;
        }

        TownPerson FindPersonAnyState(ulong id)
        {
            if (roster != null)
                foreach (TownPerson p in roster.People)
                    if (p.id == id)
                        return p;
            return null;
        }

        internal void WriteLedger(string folder)
        {
            File.WriteAllText(Path.Combine(folder, LedgerFile), SaveLoadManager.Serialize(typeof(LedgerData), ledger, false), new UTF8Encoding(false));
        }

        internal void ReadLedger(string folder)
        {
            string path = Path.Combine(folder, LedgerFile);
            ledger = File.Exists(path) ? (LedgerData)SaveLoadManager.Deserialize(typeof(LedgerData), File.ReadAllText(path)) ?? new LedgerData() : new LedgerData();
            if (ledger.dead == null)
                ledger.dead = new List<string>();
            dead.Clear();
            foreach (string key in ledger.dead)
                dead.Add(Convert.ToUInt64(key, 16));
            nextPoll = 0;
            bridge.LogLine("town: ledger restored with " + dead.Count + " deaths");
        }

        // ---- Test reports, with -dftownreport ----

        // Who lives here and where they spend their days. Independent of the live clock, so launches can be compared.
        void Census()
        {
            StringBuilder all = new StringBuilder();
            foreach (TownPerson p in roster.People)
                all.AppendFormat("{0:x16}{1}{2}{3}{4:F3}{5:F3};", p.id, p.archive, p.home, p.habit, p.wake, p.sleep);
            bridge.LogLine(string.Format("town: census {0} people, digest {1:x16}", roster.People.Length, TownRoster.Hash(Fnv(all.ToString()), 1)));
            int day = (int)(DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() / 86400UL);
            int shown = 0, near = 0, samples = 0;
            for (int i = 0; i < roster.People.Length && i < 40; i++)
            {
                TownPerson p = roster.People[i];
                List<int> places = new List<int> { p.home };
                places.AddRange(p.haunts);
                int seen = 0, close = 0;
                // Seven days at four daytime hours: how often the person is at one of their own places.
                for (int d = 0; d < 7; d++)
                    foreach (double h in new[] { 9.0, 12.0, 15.0, 18.0 })
                    {
                        TownRoster.Step step;
                        if (!roster.FindStep(p, (day + d) * 24 + h, out step))
                            continue;
                        seen++;
                        if (step.kind != 2)
                            close++;
                    }
                near += close;
                samples += seen;
                if (shown++ < 12)
                    bridge.LogLine(string.Format("town: person {0} {1:x16} {2} archive {3} {4}, home {5} ({6}), haunts {7}, awake {8:F1}-{9:F1}, at own places {10}/{11}",
                        p.index, p.id, p.Name, p.archive, p.habit, roster.Sites[p.home].key, roster.Sites[p.home].type,
                        string.Join(",", Array.ConvertAll(p.haunts, s => roster.Sites[s].type.ToString())), p.wake, p.sleep, close, seen));
            }
            bridge.LogLine(string.Format("town: first 40 people were at one of their own places in {0} of {1} daytime samples", near, samples));
        }

        void Report(double hours, double px, double pz)
        {
            StringBuilder text = new StringBuilder();
            ulong digest = 17;
            foreach (Candidate c in candidates)
                digest = TownRoster.Hash(digest, c.person.id ^ (ulong)(long)Math.Round(c.pose.x) * 31 ^ (ulong)(long)Math.Round(c.pose.z));
            bridge.LogLine(string.Format("town: report hour {0:F3} player {1:F0},{2:F0} visible {3} digest {4:x16} dead {5}", hours % 24, px, pz, candidates.Count, digest, dead.Count));
            for (int i = 0; i < candidates.Count && i < 6; i++)
                bridge.LogLine(string.Format("townrow {0:x16} {1:F1} {2:F1} {3:F2} {4:F2} {5}", candidates[i].person.id, candidates[i].pose.x, candidates[i].pose.z, candidates[i].pose.vx, candidates[i].pose.vz, candidates[i].person.habit));
        }

        static ulong Fnv(string s)
        {
            ulong h = 14695981039346656037UL;
            foreach (char c in s)
            {
                h ^= c;
                h *= 1099511628211UL;
            }
            return h;
        }
    }
}
