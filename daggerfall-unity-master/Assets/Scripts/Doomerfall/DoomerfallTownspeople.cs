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

        internal struct Candidate
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
        bool listedEmpty = true;
        float nextPoll;
        DoomerfallTownspeopleTest test;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            test = DoomerfallTownspeopleTest.FromCommandLine(); // Null unless a test flag is given.
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
            if (test != null) test.BeforePoll(bridge);
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
            if (test != null) test.AfterPublish(bridge, roster, candidates, hours, px, pz, dead.Count);
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
    }
}
