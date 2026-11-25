// Doomerfall: Daggerfall's location ledger. Runs only in a bridge session.
//
// Daggerfall holds the permanent record of what happened in each place, and Doom builds the place from it (bridge
// kinds 200-205, UZDoom/src/dd_locations.cpp). A place's record is its facts, the changes from what the map, the
// encounter plan, or a Daggerfall placement rebuilds: dead mooks and where their corpses lie, monsters that were hurt
// or moved, pickups taken, and items dropped. Doom still decides the physics and reports the whole record when the
// player leaves a place and when it saves there; this ledger replaces its copy each time. When the player enters a
// place, Doom asks, and the record goes back. Doom's own world table is only a cache of it.
//
// Keys are Daggerfall's: "D<map id>" for a dungeon, "B<map id>:<building key>" for a building interior, and
// "O<chunk x>,<chunk y>" for an exterior world chunk (32 x 32 tiles; towns and the overworld alike). Facts are keyed by
// Daggerfall-derived ids: mook ids (DoomerfallMonsters), map pickup ids, NPC and townsperson ids (DoomerfallNpcs,
// DoomerfallTownsfolk), and overworld monster ids (tag 2: the world chunk and the monster's index in its seeded pack,
// see OverworldMonsterId). A Doom drop has no Daggerfall id; it is kept by position with DFB_FACT_SESSION. Positions
// are Daggerfall units in the place's own frame (for a chunk: x and y from its corner, z the world height). Exterior
// chunks arrive whenever their facts changed, and an id lives in one chunk only: a monster that walked into another
// chunk leaves the old one. The ledger also wraps the death ledger: a dungeon corpse whose death never reached
// DoomerfallMonsters is recorded there when its record arrives.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using DaggerfallWorkshop.Game.Serialization;
using FullSerializer;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallLocations : MonoBehaviour
    {
        const string LedgerFile = "DoomerfallLocations.json";
        const float DoomPerDaggerfall = 0.75f;
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        internal sealed class Place
        {
            public uint kind = Dfb.PLACE_DUNGEON;
            public int mapId;
            public int key;            // an interior's building key, or an exterior chunk's y
            public int mooks = -1;     // the dungeon's planned mook count, or -1 before it was planned
            public readonly List<DfbPlacePlan> plan = new List<DfbPlacePlan>();
            public readonly List<string> names = new List<string>();
            public readonly List<DfbPlaceFact> facts = new List<DfbPlaceFact>();
        }

        // On disk: one line of text per fact, so a slaughter-sized dungeon stays small.
        public sealed class PlaceData
        {
            public uint kind;          // 0 in ledgers written before interiors and chunks: a dungeon
            public int key;
            public int mapId;
            public int mooks = -1;
            public string[] names;
            public string[] plan;      // placement x y z enemyType (Doom units)
            public string[] facts;     // id kind flags cls death x y z angle height health amount
        }

        [fsObject("v1")]
        public sealed class LedgerData
        {
            public Dictionary<string, PlaceData> places = new Dictionary<string, PlaceData>();
        }

        DoomerfallBridge bridge;
        DoomerfallMonsters monsters;
        readonly Dictionary<string, Place> places = new Dictionary<string, Place>();
        Place incoming;
        uint incomingGeneration;
        bool incomingOnSave;

        internal void Init(DoomerfallBridge owner, DoomerfallMonsters deaths)
        {
            bridge = owner;
            monsters = deaths;
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
            places.Clear();
            incoming = null;
            sendQueue.Clear();
        }

        // A slaughter-sized record is thousands of events, more than the ring and the outbox hold at once, so the
        // reply goes out a share per frame. Doom waits for its END before planning the dungeon's mooks.
        const int PacePerFrame = 2048;
        readonly Queue<DfbEvent> sendQueue = new Queue<DfbEvent>();

        void Post(DfbEvent e)
        {
            sendQueue.Enqueue(e);
        }

        void Update()
        {
            for (int n = 0; n < PacePerFrame && sendQueue.Count > 0; n++)
            {
                DfbEvent e = sendQueue.Dequeue();
                bridge.Send(ref e);
            }
        }

        static string DungeonKey(int mapId)
        {
            return "D" + mapId.ToString(Inv);
        }

        static string PlaceKey(uint kind, int mapId, int key)
        {
            if (kind == Dfb.PLACE_INTERIOR)
                return "B" + mapId.ToString(Inv) + ":" + key.ToString(Inv);
            if (kind == Dfb.PLACE_CHUNK)
                return "O" + mapId.ToString(Inv) + "," + key.ToString(Inv);
            return DungeonKey(mapId);
        }

        static string PlaceKey(Place place)
        {
            return PlaceKey(place.kind, place.mapId, place.key);
        }

        // The id Doom gives the n-th monster of an overworld chunk's seeded pack (dd_treadmill.cpp BuildSeeds): tag 2,
        // the chunk's y and x, and the index. It is a function of the world chunk alone, so Daggerfall can name it.
        internal static ulong OverworldMonsterId(int chunkX, int chunkY, int index)
        {
            return (1UL << 62) | ((ulong)(uint)chunkY << 40) | ((ulong)(uint)chunkX << 16) | (ulong)(ushort)index;
        }

        // Where Doom last left this mook's corpse, in Daggerfall units in the dungeon's frame.
        internal bool TryGetCorpse(int mapId, ulong id, out Vector3 position)
        {
            position = Vector3.zero;
            Place place;
            if (!places.TryGetValue(DungeonKey(mapId), out place))
                return false;
            foreach (DfbPlaceFact f in place.facts)
                if (f.id == id && f.kind == Dfb.FACT_CORPSE)
                {
                    position = new Vector3(f.x, f.y, f.z);
                    return true;
                }
            return false;
        }

        // Doom's record of a place, sent on leaving and on saving.
        internal void OnEvent(ref DfbEvent ev)
        {
            switch (ev.kind)
            {
                case Dfb.KIND_PLACE_BEGIN:
                    incomingGeneration = ev.place.generation;
                    incomingOnSave = (ev.place.flags & Dfb.PLACE_ON_SAVE) != 0;
                    uint kind = ev.place.placeKind;
                    incoming = kind == Dfb.PLACE_DUNGEON || kind == Dfb.PLACE_INTERIOR || kind == Dfb.PLACE_CHUNK
                        ? new Place { kind = kind, mapId = ev.place.mapId, key = ev.place.key } : null;
                    if (incoming != null)
                        incoming.facts.Capacity = (int)ev.place.facts;
                    break;
                case Dfb.KIND_PLACE_NAME:
                    if (incoming == null || ev.placeName.generation != incomingGeneration)
                        break;
                    while (incoming.names.Count <= ev.placeName.index)
                        incoming.names.Add(string.Empty);
                    byte[] bytes = new byte[40];
                    ev.placeName.CopyText(bytes);
                    int length = Array.IndexOf(bytes, (byte)0);
                    incoming.names[ev.placeName.index] += Encoding.UTF8.GetString(bytes, 0, length < 0 ? bytes.Length : length);
                    break;
                case Dfb.KIND_PLACE_PLAN:
                    if (incoming == null || ev.placePlan.generation != incomingGeneration)
                        break;
                    if (ev.placePlan.header != 0)
                        incoming.mooks = ev.placePlan.value;
                    else
                        incoming.plan.Add(ev.placePlan);
                    break;
                case Dfb.KIND_PLACE_FACT:
                    if (incoming != null && ev.placeFact.generation == incomingGeneration)
                        incoming.facts.Add(ev.placeFact);
                    break;
                case Dfb.KIND_PLACE_END:
                    if (incoming == null || ev.place.generation != incomingGeneration)
                        break;
                    if (incoming.facts.Count != ev.place.facts)
                        bridge.LogLine(string.Format("locations: error: record of {0} arrived with {1} of {2} facts; kept the old one", PlaceKey(incoming), incoming.facts.Count, ev.place.facts));
                    else
                        Accept(incoming);
                    incoming = null;
                    break;
                case Dfb.KIND_PLACE_REQUEST:
                    if (ev.place.placeKind == Dfb.PLACE_WORLD)
                        SendWorld(ev.place.generation);
                    else
                        SendPlace(ev.place.generation, ev.place.placeKind == 0 ? Dfb.PLACE_DUNGEON : ev.place.placeKind, ev.place.mapId, ev.place.key);
                    break;
            }
        }

        void Accept(Place place)
        {
            string key = PlaceKey(place);
            if (place.kind == Dfb.PLACE_CHUNK)
            {
                AcceptChunk(key, place);
                return;
            }
            if (place.mooks < 0)
            {
                // Doom had no plan yet (it never got Daggerfall's facts); keep the one this ledger already has.
                Place old;
                if (places.TryGetValue(key, out old) && old.mooks >= 0)
                {
                    place.mooks = old.mooks;
                    place.plan.AddRange(old.plan);
                }
            }
            places[key] = place;
            int[] kinds = new int[4];
            int deathsAdded = 0;
            foreach (DfbPlaceFact f in place.facts)
            {
                kinds[Math.Min((int)f.kind, 3)]++;
                // Wraps the death ledger: a corpse that is a Daggerfall mook is dead there too, even if its death event was lost.
                if (place.kind == Dfb.PLACE_DUNGEON && f.kind == Dfb.FACT_CORPSE && (f.flags & Dfb.FACT_SESSION) == 0 && (f.id >> (int)Dfb.MONSTER_TAG_SHIFT) == Dfb.MONSTER_TAG && monsters && !monsters.IsDead(f.id))
                {
                    monsters.OnDeath(f.id, place.mapId, f.x * DoomPerDaggerfall, f.y * DoomPerDaggerfall, f.z * DoomPerDaggerfall);
                    deathsAdded++;
                }
            }
            bridge.LogLine(string.Format("locations: record of {0} from Doom{1}: {2} facts ({3} monsters, {4} corpses, {5} items, {6} gone), plan {7} mooks, {8} deaths added to the death ledger",
                key, incomingOnSave ? " for a save" : " on leaving", place.facts.Count, kinds[0], kinds[1], kinds[2], kinds[3], place.mooks, deathsAdded));
        }

        // An exterior chunk's whole record. An id lives in one chunk only, so a monster or item that moved here leaves
        // the chunk it was in (ids Doom made up for this session are not compared: they mean nothing across a load).
        void AcceptChunk(string key, Place place)
        {
            HashSet<ulong> ids = new HashSet<ulong>();
            foreach (DfbPlaceFact f in place.facts)
                if ((f.flags & Dfb.FACT_SESSION) == 0)
                    ids.Add(f.id);
            int moved = 0;
            List<string> emptied = new List<string>();
            if (ids.Count > 0)
                foreach (KeyValuePair<string, Place> other in places)
                {
                    if (other.Value.kind != Dfb.PLACE_CHUNK || other.Key == key)
                        continue;
                    moved += other.Value.facts.RemoveAll(f => (f.flags & Dfb.FACT_SESSION) == 0 && ids.Contains(f.id));
                    if (other.Value.facts.Count == 0)
                        emptied.Add(other.Key);
                }
            foreach (string gone in emptied)
                places.Remove(gone);
            if (place.facts.Count == 0)
                places.Remove(key);
            else
                places[key] = place;
            int[] kinds = new int[4];
            foreach (DfbPlaceFact f in place.facts)
                kinds[Math.Min((int)f.kind, 3)]++;
            bridge.LogLine(string.Format("locations: record of {0} from Doom{1}: {2} facts ({3} monsters, {4} corpses, {5} items, {6} gone){7}",
                key, incomingOnSave ? " for a save" : " on leaving", place.facts.Count, kinds[0], kinds[1], kinds[2], kinds[3],
                moved > 0 ? ", " + moved + " moved out of other chunks" : string.Empty));
        }

        // Every exterior chunk, one record each, then an empty PLACE_WORLD record, answering Doom after a load.
        void SendWorld(uint generation)
        {
            Stopwatch watch = Stopwatch.StartNew();
            int chunks = 0, facts = 0, events = 0;
            foreach (Place place in places.Values)
            {
                if (place.kind != Dfb.PLACE_CHUNK)
                    continue;
                events += PostRecord(generation, place.kind, place.mapId, place.key, place);
                chunks++;
                facts += place.facts.Count;
            }
            events += PostRecord(generation, Dfb.PLACE_WORLD, 0, 0, null);
            bridge.LogLine(string.Format(Inv, "locations: sent the exterior ledger to Doom: {0} chunks, {1} facts, {2} events, {3:F2} ms",
                chunks, facts, events, watch.Elapsed.TotalMilliseconds));
        }

        // Answers Doom's request on entering a place, in the same order Doom sends its own.
        void SendPlace(uint generation, uint kind, int mapId, int key)
        {
            Stopwatch watch = Stopwatch.StartNew();
            Place place;
            bool known = places.TryGetValue(PlaceKey(kind, mapId, key), out place);
            int sent = PostRecord(generation, kind, mapId, key, known ? place : null);
            bridge.LogLine(string.Format(Inv, "locations: sent the record of {0} to Doom: {1}, {2} facts, {3} events, {4:F2} ms",
                PlaceKey(kind, mapId, key), known ? "known" : "no record", known ? place.facts.Count : 0, sent, watch.Elapsed.TotalMilliseconds));
        }

        // One record as events (BEGIN, NAMEs, PLANs, FACTs, END); a null place sends an empty, unknown one.
        int PostRecord(uint generation, uint kind, int mapId, int key, Place place)
        {
            bool known = place != null;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_PLACE_BEGIN;
            e.tic = (uint)Time.frameCount;
            e.place.generation = generation;
            e.place.placeKind = kind;
            e.place.mapId = mapId;
            e.place.key = key;
            e.place.flags = known ? Dfb.PLACE_KNOWN : 0;
            e.place.facts = known ? (uint)place.facts.Count : 0;
            e.place.names = known ? (uint)place.names.Count : 0;
            e.place.planLines = known && place.mooks >= 0 ? (uint)place.plan.Count + 1 : 0;
            DfbEvent header = e;
            Post(e);
            int sent = 1;
            if (known)
            {
                for (int n = 0; n < place.names.Count; n++)
                {
                    byte[] bytes = Encoding.UTF8.GetBytes(place.names[n]);
                    int at = 0;
                    do
                    {
                        int count = Math.Min(40, bytes.Length - at);
                        byte[] part = new byte[40];
                        Array.Copy(bytes, at, part, 0, count);
                        at += count;
                        DfbEvent name = default(DfbEvent);
                        name.kind = Dfb.KIND_PLACE_NAME;
                        name.tic = e.tic;
                        name.placeName.generation = generation;
                        name.placeName.index = (ushort)n;
                        name.placeName.SetText(part, count);
                        Post(name);
                        sent++;
                    } while (at < bytes.Length);
                }
                if (place.mooks >= 0)
                {
                    DfbEvent plan = default(DfbEvent);
                    plan.kind = Dfb.KIND_PLACE_PLAN;
                    plan.tic = e.tic;
                    plan.placePlan.generation = generation;
                    plan.placePlan.header = 1;
                    plan.placePlan.value = place.mooks;
                    Post(plan);
                    sent++;
                    foreach (DfbPlacePlan line in place.plan)
                    {
                        plan.placePlan = line;
                        plan.placePlan.generation = generation;
                        plan.placePlan.header = 0;
                        Post(plan);
                        sent++;
                    }
                }
                foreach (DfbPlaceFact fact in place.facts)
                {
                    DfbEvent f = default(DfbEvent);
                    f.kind = Dfb.KIND_PLACE_FACT;
                    f.tic = e.tic;
                    f.placeFact = fact;
                    f.placeFact.generation = generation;
                    Post(f);
                    sent++;
                }
            }
            header.kind = Dfb.KIND_PLACE_END;
            Post(header);
            sent++;
            return sent;
        }

        static string FactLine(DfbPlaceFact f)
        {
            return string.Format(Inv, "{0:x16} {1} {2} {3} {4} {5:R} {6:R} {7:R} {8} {9:R} {10} {11}",
                f.id, f.kind, f.flags, f.cls, f.death, f.x, f.y, f.z, f.angle, f.height, f.health, f.amount);
        }

        static bool ParseFact(string line, out DfbPlaceFact f)
        {
            f = default(DfbPlaceFact);
            string[] p = line.Split(' ');
            if (p.Length < 12)
                return false;
            try
            {
                f.id = ulong.Parse(p[0], NumberStyles.HexNumber, Inv);
                f.kind = byte.Parse(p[1], Inv);
                f.flags = byte.Parse(p[2], Inv);
                f.cls = ushort.Parse(p[3], Inv);
                f.death = ushort.Parse(p[4], Inv);
                f.x = float.Parse(p[5], Inv);
                f.y = float.Parse(p[6], Inv);
                f.z = float.Parse(p[7], Inv);
                f.angle = ushort.Parse(p[8], Inv);
                f.height = float.Parse(p[9], Inv);
                f.health = int.Parse(p[10], Inv);
                f.amount = int.Parse(p[11], Inv);
                return true;
            }
            catch (FormatException) { return false; }
            catch (OverflowException) { return false; }
        }

        internal void WriteLedger(string folder)
        {
            Stopwatch watch = Stopwatch.StartNew();
            LedgerData data = new LedgerData();
            int facts = 0;
            foreach (KeyValuePair<string, Place> entry in places)
            {
                Place place = entry.Value;
                PlaceData d = new PlaceData { kind = place.kind, key = place.key, mapId = place.mapId, mooks = place.mooks, names = place.names.ToArray() };
                d.plan = new string[place.plan.Count];
                for (int n = 0; n < place.plan.Count; n++)
                {
                    DfbPlacePlan q = place.plan[n];
                    d.plan[n] = string.Format(Inv, "{0:x16} {1:R} {2:R} {3:R} {4}", q.placement, q.x, q.y, q.z, q.value);
                }
                d.facts = new string[place.facts.Count];
                for (int n = 0; n < place.facts.Count; n++)
                    d.facts[n] = FactLine(place.facts[n]);
                facts += place.facts.Count;
                data.places[entry.Key] = d;
            }
            string path = Path.Combine(folder, LedgerFile);
            File.WriteAllText(path, SaveLoadManager.Serialize(typeof(LedgerData), data, false), new UTF8Encoding(false));
            bridge.LogLine(string.Format(Inv, "locations: ledger written, {0} places, {1} facts, {2} bytes, {3:F2} ms",
                places.Count, facts, new FileInfo(path).Length, watch.Elapsed.TotalMilliseconds));
        }

        internal void ReadLedger(string folder)
        {
            places.Clear();
            incoming = null;
            string path = Path.Combine(folder, LedgerFile);
            LedgerData data = File.Exists(path) ? (LedgerData)SaveLoadManager.Deserialize(typeof(LedgerData), File.ReadAllText(path)) : null;
            int facts = 0, bad = 0;
            if (data != null && data.places != null)
                foreach (KeyValuePair<string, PlaceData> entry in data.places)
                {
                    PlaceData d = entry.Value;
                    if (d == null)
                        continue;
                    Place place = new Place { kind = d.kind == 0 ? Dfb.PLACE_DUNGEON : d.kind, key = d.key, mapId = d.mapId, mooks = d.mooks };
                    if (d.names != null)
                        place.names.AddRange(d.names);
                    if (d.plan != null)
                        foreach (string line in d.plan)
                        {
                            string[] p = line.Split(' ');
                            if (p.Length < 5)
                                continue;
                            place.plan.Add(new DfbPlacePlan
                            {
                                placement = ulong.Parse(p[0], NumberStyles.HexNumber, Inv),
                                x = float.Parse(p[1], Inv),
                                y = float.Parse(p[2], Inv),
                                z = float.Parse(p[3], Inv),
                                value = int.Parse(p[4], Inv),
                            });
                        }
                    if (d.facts != null)
                        foreach (string line in d.facts)
                        {
                            DfbPlaceFact f;
                            if (ParseFact(line, out f))
                                place.facts.Add(f);
                            else
                                bad++;
                        }
                    facts += place.facts.Count;
                    places[entry.Key] = place;
                }
            bridge.LogLine(string.Format("locations: ledger restored with {0} places, {1} facts{2}", places.Count, facts, bad > 0 ? ", " + bad + " unreadable lines skipped" : string.Empty));
        }
    }
}
