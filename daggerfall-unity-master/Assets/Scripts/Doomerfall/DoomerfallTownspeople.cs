// Doomerfall: Daggerfall's side of persistent townspeople. Runs only in a bridge session.
//
// Townsfolk.cs generates each town's people from its map id and the world time. This lists the ones near the Doom
// player, with their motion, so Doom can draw them. The only saved state is who has died. A death that Doom reports
// goes in this ledger, and that person is never listed again.
//
// Inside a house, this lists the people whose schedule has them at home there (asleep, or indoors at home), each on
// a spot picked from their own seed, so they are found in the same place on every visit.
//
// The ledger also keeps the corpses of people killed in Doom (DoomerfallCorpses.cs), which these lists carry too.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.MagicAndEffects.MagicEffects;
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
            public List<DoomerfallCorpse> corpses = new List<DoomerfallCorpse>();
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
        readonly List<DoomerfallCorpse> shownCorpses = new List<DoomerfallCorpse>();
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

        // A menu that ran the clock is closing (DoomerfallUi): list everyone where the new time puts them, now.
        internal void PublishNow()
        {
            nextPoll = 0;
            Update();
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
            if (peer.worldContext == Dfb.WORLD_INTERIOR && gps.HasCurrentLocation && TownRoster.HasTownsfolk(gps.CurrentLocation))
            {
                UpdateIndoors(ref peer, gps);
                return;
            }
            if (peer.worldContext != Dfb.WORLD_EXTERIOR || !gps.HasCurrentLocation || !TownRoster.HasTownsfolk(gps.CurrentLocation))
            {
                PublishEmpty();
                return;
            }
            EnsureRoster(gps);
            double px = peer.worldX - roster.OriginX, pz = peer.worldZ - roster.OriginZ;
            double width = roster.GridW * TownRoster.Cell, height = roster.GridH * TownRoster.Cell;
            if (px < -OutsideRect || pz < -OutsideRect || px > width + OutsideRect || pz > height + OutsideRect)
            {
                PublishEmpty();
                return;
            }
            double hours = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() / 3600.0;
            Collect(hours, px, pz);
            DoomerfallCorpses.Select(ledger.corpses, roster.MapId, 0, roster.OriginX, roster.OriginZ, px, pz, ViewRange, shownCorpses);
            Publish();
            if (test != null) test.AfterPublish(bridge, roster, candidates, hours, px, pz, dead.Count);
        }

        void EnsureRoster(PlayerGPS gps)
        {
            DFLocation location = gps.CurrentLocation;
            if (roster != null && roster.MapId == location.MapTableData.MapId)
                return;
            Stopwatch clock = Stopwatch.StartNew();
            roster = new TownRoster(location, PopulationRace(gps));
            bridge.LogLine(string.Format("town: {0} map {1} has {2} people and {3} places, built in {4} ms", location.Name, roster.MapId, roster.People.Length, roster.Sites.Count, clock.ElapsedMilliseconds));
        }

        // ---- At home ----

        const float DoomPerDaggerfall = 0.75f;
        const float CrowdStep = 28f;                // Doom units between people who share one spot
        readonly List<Vector3> homeSpots = new List<Vector3>();
        readonly List<Vector3> homeRows = new List<Vector3>();
        readonly Dictionary<ulong, Vector3> spotOf = new Dictionary<ulong, Vector3>();
        readonly List<Vector3> homeWorld = new List<Vector3>();     // the same spots in Daggerfall's world space

        // A spot a step or two around a shared marker. Daggerfall's interior colliders (built whether or not it draws)
        // must show open floor on the same level with nothing in between; the seeded direction is tried first, then
        // the other seven. If none is clear, the person shares the marker itself rather than stand in a wall.
        Vector3 CrowdSpot(Vector3 marker, Vector3 markerSpot, ulong startDegrees, int crowd, Transform space, float units, ref string note)
        {
            float floor;
            if (!FloorBelow(marker + Vector3.up * 0.5f, 2f, out floor))
            {
                note += " nofloor";
                return markerSpot;
            }
            for (int step = crowd; step >= 1; step--)
            {
                float distance = CrowdStep * step / units;
                for (int k = 0; k < 8; k++)
                {
                    float angle = (startDegrees + 45f * k) * Mathf.Deg2Rad;
                    Vector3 dir = space.TransformDirection(new Vector3(Mathf.Cos(angle), 0, Mathf.Sin(angle))).normalized;
                    Vector3 low = new Vector3(marker.x, floor + 0.35f, marker.z), high = new Vector3(marker.x, floor + 1.3f, marker.z);
                    if (Blocked(low, dir, distance + 0.3f) || Blocked(high, dir, distance + 0.3f))
                        continue;
                    Vector3 target = high + dir * distance;
                    float there;
                    if (!FloorBelow(target, 2f, out there) || Mathf.Abs(there - floor) > 0.25f)
                        continue;
                    Vector3 local = space.InverseTransformPoint(target);
                    return new Vector3(local.x * units, local.z * units, markerSpot.z);
                }
            }
            note += " shared";
            return markerSpot;
        }

        static bool Blocked(Vector3 from, Vector3 dir, float distance)
        {
            GameObject player = GameManager.Instance.PlayerObject;
            foreach (RaycastHit hit in Physics.RaycastAll(from, dir, distance, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                if (!hit.collider.transform.IsChildOf(player.transform))
                    return true;
            return false;
        }

        // The highest floor below a point, ignoring the hidden player.
        static bool FloorBelow(Vector3 from, float distance, out float y)
        {
            GameObject player = GameManager.Instance.PlayerObject;
            y = float.MinValue;
            foreach (RaycastHit hit in Physics.RaycastAll(from, Vector3.down, distance, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                if (!hit.collider.transform.IsChildOf(player.transform) && hit.point.y > y)
                    y = hit.point.y;
            return y > float.MinValue;
        }
        int homeBuilding = -1, homeSpace;
        string lastHomeLine;

        // True when the schedule has the person inside their own home: asleep between days, or a stretch indoors at home.
        internal bool AtHome(TownPerson p, double hours)
        {
            TownRoster.Step step;
            if (!roster.FindStep(p, hours, out step))
                return true;
            return step.kind == 0 && step.a == p.home;
        }

        void UpdateIndoors(ref DfbUzState peer, PlayerGPS gps)
        {
            PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
            Transform space = sync.ItemSpace(ref peer);
            if (!space || !enter.IsPlayerInsideBuilding || !enter.Interior)
                return;     // Daggerfall is not in the same room as Doom yet, so keep whatever Doom has.
            EnsureRoster(gps);
            int building = enter.BuildingDiscoveryData.buildingKey;
            if (building != homeBuilding || space.GetInstanceID() != homeSpace)
            {
                homeBuilding = building;
                homeSpace = space.GetInstanceID();
                FindHomeSpots(enter.Interior, space);
            }
            double hours = DaggerfallUnity.Instance.WorldTime.Now.ToSeconds() / 3600.0;
            candidates.Clear();
            homeRows.Clear();
            foreach (TownPerson p in roster.People)
            {
                Vector3 at;
                if (!spotOf.TryGetValue(p.id, out at) || dead.Contains(p.id) || !AtHome(p, hours))
                    continue;
                candidates.Add(new Candidate { person = p });
                homeRows.Add(at);
            }
            PublishHome(building);
        }

        // Daggerfall's rest markers are where it places quest people in a building; the entry markers are the fallback.
        // Each spot is Doom map units (x east, y north, z height) in the interior map.
        void FindHomeSpots(DaggerfallInterior interior, Transform space)
        {
            homeSpots.Clear();
            homeWorld.Clear();
            Vector3[] markers = interior.FindMarkers(DaggerfallInterior.InteriorMarkerTypes.Rest);
            string kind = "rest";
            if (markers.Length == 0)
            {
                markers = interior.FindMarkers(DaggerfallInterior.InteriorMarkerTypes.Enter);
                kind = "enter";
            }
            float units = DoomPerDaggerfall / MeshReader.GlobalScale;
            // Leave out the marker Daggerfall lands the player on (the one nearest the street door used, as
            // PlayerEnterExit does), so nobody stands inside the player on the way in. At least one spot stays.
            HashSet<int> skipped = new HashSet<int>();
            Vector3 landing;
            if (markers.Length > 1 && interior.FindClosestEnterMarker(DaggerfallStaticDoors.GetDoorPosition(interior.EntryDoor), out landing))
                for (int i = 0; i < markers.Length; i++)
                    if ((markers[i] - landing).sqrMagnitude < 0.01f)
                        skipped.Add(i);
            if (skipped.Count >= markers.Length)
                skipped.Clear();
            StringBuilder left = new StringBuilder();
            for (int i = 0; i < markers.Length; i++)
            {
                if (skipped.Contains(i))
                {
                    Vector3 by = space.InverseTransformPoint(markers[i]);
                    left.AppendFormat(" {0:F0},{1:F0},{2:F0}", by.x * units, by.z * units, by.y * units);
                    continue;
                }
                Vector3 local = space.InverseTransformPoint(markers[i]);
                homeSpots.Add(new Vector3(local.x * units, local.z * units, local.y * units));
                homeWorld.Add(markers[i]);
            }
            // Every resident gets a fixed spot, alive or dead, home or out, so nobody moves when a housemate is missing.
            // Roster order settles a contested spot; once every spot is taken, people stand a step around one.
            spotOf.Clear();
            List<int> taken = new List<int>();
            int residents = 0;
            string crowded = "";
            foreach (TownPerson p in roster.People)
            {
                if (roster.Sites[p.home].key != homeBuilding)
                    continue;
                residents++;
                if (homeSpots.Count == 0)
                    continue;
                int first = (int)(p.seed % (ulong)homeSpots.Count), spot = first, crowd = 0;
                while (taken.Contains(spot * 64 + crowd))
                {
                    spot = (spot + 1) % homeSpots.Count;
                    if (spot == first)
                        crowd++;
                }
                taken.Add(spot * 64 + crowd);
                Vector3 at = homeSpots[spot];
                if (crowd > 0)
                    at = CrowdSpot(homeWorld[spot], at, (p.seed >> 20) % 360, crowd, space, units, ref crowded);
                spotOf[p.id] = at;
            }
            bridge.LogLine(string.Format("town: building {0} has {1} residents and {2} {3} spots (left out where the player lands:{4}){5}", homeBuilding, residents, homeSpots.Count, kind, left,
                crowded.Length > 0 ? "; crowding:" + crowded : ""));
        }

        void PublishHome(int building)
        {
            DoomerfallCorpses.Select(ledger.corpses, roster.MapId, building, 0, 0, 0, 0, 0, shownCorpses);
            generation++;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_TOWNSFOLK_BEGIN;
            e.tic = (uint)Time.frameCount;
            e.townsfolk.generation = generation;
            e.townsfolk.count = (uint)(candidates.Count + shownCorpses.Count);
            e.townsfolk.mapId = roster.MapId;
            e.townsfolk.space = Dfb.TOWNSFOLK_INTERIOR;
            bridge.Send(ref e);
            StringBuilder line = new StringBuilder();
            for (int i = 0; i < candidates.Count; i++)
            {
                TownPerson p = candidates[i].person;
                Vector3 at = homeRows[i];
                DfbEvent row = default(DfbEvent);
                row.kind = Dfb.KIND_TOWNSPERSON;
                row.tic = (uint)Time.frameCount;
                row.townsperson.id = p.id;
                row.townsperson.generation = generation;
                row.townsperson.archive = (ushort)p.archive;
                row.townsperson.flags = (ushort)(p.guard ? Dfb.TOWNSPERSON_GUARD : 0);
                row.townsperson.x = at.x;
                row.townsperson.y = at.y;
                row.townsperson.z = at.z;
                row.townsperson.facing = (float)((p.seed >> 40) % 360);
                bridge.Send(ref row);
                line.AppendFormat(" {0:x16}@{1:F0},{2:F0},{3:F0}", p.id, at.x, at.y, at.z);
            }
            foreach (DoomerfallCorpse c in shownCorpses)
            {
                SendCorpse(c, (float)c.x, (float)c.y);
                line.AppendFormat(" corpse {0}@{1:F0},{2:F0},{3:F0}", c.id, c.x, c.y, c.z);
            }
            e.kind = Dfb.KIND_TOWNSFOLK_END;
            bridge.Send(ref e);
            listedEmpty = candidates.Count + shownCorpses.Count == 0;
            string text = string.Format("town: at home in building {0}: {1}{2}", building, candidates.Count, line);
            if (text != lastHomeLine)
            {
                lastHomeLine = text;
                bridge.LogLine(text);
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
            e.townsfolk.count = (uint)(candidates.Count + shownCorpses.Count);
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
            foreach (DoomerfallCorpse c in shownCorpses)
                SendCorpse(c, (float)(c.x - roster.OriginX), (float)(c.y - roster.OriginZ));
            e.kind = Dfb.KIND_TOWNSFOLK_END;
            bridge.Send(ref e);
            listedEmpty = candidates.Count + shownCorpses.Count == 0;
        }

        void SendCorpse(DoomerfallCorpse c, float x, float y)
        {
            DfbEvent row = default(DfbEvent);
            row.kind = Dfb.KIND_TOWNSFOLK_CORPSE;
            row.tic = (uint)Time.frameCount;
            row.corpse.id = Convert.ToUInt64(c.id, 16);
            row.corpse.generation = generation;
            row.corpse.archive = (ushort)c.archive;
            row.corpse.record = (ushort)c.record;
            row.corpse.x = x;
            row.corpse.y = y;
            row.corpse.z = c.z;
            bridge.Send(ref row);
        }

        // Doom reports where a Daggerfall person's body fell, just before the death itself. Daggerfall decides the
        // corpse: a townsperson lies as the human corpse, except a guard, who becomes the city watch instead
        // (ApplyCrime); a city guard lies as its own enemy corpse (guardCorpse, from DoomerfallGuards).
        internal void OnCorpsePlace(ulong id, double x, double y, float z, uint space, DoomerfallGuards guards)
        {
            string key = id.ToString("x16");
            int archive = DoomerfallCorpses.HumanArchive, record = DoomerfallCorpses.HumanRecord;
            if ((id >> 61) == Dfb.TOWNSPERSON_TAG)
            {
                TownPerson p = FindPersonAnyState(id);
                if (p != null && p.guard)
                {
                    bridge.LogLine("corpse: " + key + " was a guard, who becomes the city watch and leaves no corpse");
                    return;
                }
            }
            else if ((id >> 61) != Dfb.GUARD_TAG || !guards.CorpseOf(id, out archive, out record))
            {
                bridge.LogLine("corpse: " + key + " is no Daggerfall person this keeps");
                return;
            }
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
            bool inside = space == Dfb.TOWNSFOLK_INTERIOR;
            if (!gps.HasCurrentLocation || (inside && !enter.IsPlayerInsideBuilding) || DoomerfallCorpses.Has(ledger.corpses, key))
            {
                bridge.LogLine("corpse: " + key + " not kept (no location, not inside, or already kept)");
                return;
            }
            DoomerfallCorpse c = new DoomerfallCorpse
            {
                id = key, mapId = gps.CurrentMapID, building = inside ? enter.BuildingDiscoveryData.buildingKey : 0,
                x = x, y = y, z = z, archive = archive, record = record,
            };
            ledger.corpses.Add(c);
            bridge.LogLine(string.Format("corpse: kept {0} in map {1} building {2} at {3:F1},{4:F1},{5:F1} as {6}-{7}; {8} corpses in all",
                key, c.mapId, c.building, x, y, z, archive, record, ledger.corpses.Count));
            nextPoll = 0;
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
            if (p != null && GameManager.HasInstance)
                ApplyCrime(p, worldX, worldZ);
            nextPoll = 0;
        }

        // What Daggerfall does when the player's weapon hits a mobile townsperson (WeaponManager.WeaponDamage): a commoner
        // dies, which is murder and calls the guards; a guard becomes a city watch knight on that spot, which is assault.
        void ApplyCrime(TownPerson p, double worldX, double worldZ)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!p.guard)
            {
                player.TallyCrimeGuildRequirements(false, 5);
                player.CrimeCommitted = PlayerEntity.Crimes.Murder;
                player.SpawnCityGuards(true);
                FeedRacialOverride(player);
                bridge.LogLine(string.Format("town: murder; crime {0}, Dark Brotherhood tally {1}", player.CrimeCommitted, player.DarkBrotherhoodRequirementTally));
                return;
            }
            player.CrimeCommitted = PlayerEntity.Crimes.Assault;
            Vector3 at;
            if (!GuardSpot(worldX, worldZ, out at))
            {
                bridge.LogLine("town: assault on a guard, but there is no spot for the city watch");
                return;
            }
            player.SpawnCityGuard(at, Vector3.forward);
            bridge.LogLine(string.Format("town: assault on a guard; crime {0}, city watch spawned", player.CrimeCommitted));
        }

        // Outdoors, the dead guard's spot relative to Daggerfall's player. Inside, Daggerfall's player does not follow
        // Doom, so the watch comes in at the lowest outer door, as PlayerEntity.SpawnCityGuards does indoors.
        static bool GuardSpot(double worldX, double worldZ, out Vector3 at)
        {
            at = Vector3.zero;
            PlayerEnterExit enterExit = GameManager.Instance.PlayerEnterExit;
            if (enterExit.IsPlayerInside)
            {
                Vector3 normal;
                if (enterExit.Interior == null || !enterExit.Interior.FindLowestOuterInteriorDoor(out at, out normal))
                    return false;
                at += normal * (GameManager.Instance.PlayerController.radius + 0.1f);
                return true;
            }
            PlayerGPS gps = GameManager.Instance.PlayerGPS;
            at = GameManager.Instance.PlayerObject.transform.position
                + new Vector3((float)(worldX - gps.WorldX), 0, (float)(worldZ - gps.WorldZ)) * MeshReader.GlobalScale;
            return true;
        }

        // A vampire feeds and a lycanthrope sates its hunger by killing an innocent. Daggerfall passes the mobile's own
        // civilian entity, which Doomerfall does not keep, so a stand-in dead civilian is made for the call.
        static void FeedRacialOverride(PlayerEntity player)
        {
            RacialOverrideEffect racialOverride = GameManager.Instance.PlayerEffectManager.GetRacialOverrideEffect();
            if (racialOverride == null)
                return;
            GameObject standIn = new GameObject("DoomerfallDeadTownsperson");
            try
            {
                DaggerfallEntityBehaviour behaviour = standIn.AddComponent<DaggerfallEntityBehaviour>();
                behaviour.EntityType = EntityTypes.CivilianNPC;
                behaviour.Entity = new CivilianEntity(behaviour);
                behaviour.Entity.SetHealth(0);
                racialOverride.OnWeaponHitEntity(player, behaviour.Entity);
            }
            finally
            {
                DestroyImmediate(standIn);
            }
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
            if (ledger.corpses == null)
                ledger.corpses = new List<DoomerfallCorpse>();
            dead.Clear();
            foreach (string key in ledger.dead)
                dead.Add(Convert.ToUInt64(key, 16));
            nextPoll = 0;
            bridge.LogLine("town: ledger restored with " + dead.Count + " deaths and " + ledger.corpses.Count + " corpses");
        }
    }
}
