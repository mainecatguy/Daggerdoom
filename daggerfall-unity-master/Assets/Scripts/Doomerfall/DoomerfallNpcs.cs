// Doomerfall: Daggerfall's side of NPC identity and presence. Runs only in a bridge session.
//
// An NPC id is tag (3 bits, value 6) | hash of its layout record (61). The converter computes the same id in
// NpcIdentity.cs. Inside a building, this lists who Daggerfall has present, so closed shops and owned houses stay
// empty in Doom. FindNpc turns an id back into the live StaticNPC for later talk and death work.
//
// A quest Person that Daggerfall placed at a quest marker (GameObjectHelper.AddQuestNPC) has no layout record, so no
// converted map holds it. Its id is tag 6 | hash of the quest uid and Person symbol, and the list (in buildings and in
// dungeons) carries it as DFB_KIND_NPC_PLACED with its billboard and where it stands, so Doom draws it there. Quest
// actions that hide, restore, destroy or move it change Daggerfall's GameObject, and the next poll sends the new list.

using System;
using System.Collections.Generic;
using System.Text;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallNpcs : MonoBehaviour
    {
        const float PollSeconds = 0.25f;
        const float DoomPerDaggerfall = 0.75f;
        const int ScopeExterior = 1, ScopeInterior = 2, ScopeDungeon = 3, ScopeQuest = 4;

        struct Placed
        {
            public ulong id;
            public int archive, record;
            public Vector3 at; // Doom units in the space's map: x, y, feet z
            public Vector2 size;
        }

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        readonly List<ulong> present = new List<ulong>();
        readonly List<Placed> placed = new List<Placed>();
        uint generation;
        ulong lastHash;
        int lastSpace;
        bool resend, report, night;
        float nextPoll;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            report = Array.IndexOf(Environment.GetCommandLineArgs(), "-dfnpcreport") >= 0;
            night = report && Array.IndexOf(Environment.GetCommandLineArgs(), "-dfnpcnight") >= 0; // Test only: shops are closed.
        }

        internal void OnRequest()
        {
            resend = true;
        }

        // A menu that ran the clock is closing (DoomerfallUi): send who is present now.
        internal void PublishNow()
        {
            nextPoll = 0;
            lastHash = 0; // Publishes even an unchanged list; outside a building nothing is sent.
            Update();
        }

        // Must equal NpcIdentity.Make in the dungeon converter.
        internal static ulong MakeId(int mapId, int scope, int a, int b, int c, int position)
        {
            ulong h = 14695981039346656037UL;
            foreach (long v in new long[] { mapId, scope, a, b, c, position })
                for (int k = 0; k < 8; k++)
                {
                    h ^= (byte)(v >> (8 * k));
                    h *= 1099511628211UL;
                }
            h ^= h >> 32;
            h *= 0x9E3779B97F4A7C15UL;
            h ^= h >> 29;
            return ((ulong)Dfb.NPC_TAG << (int)Dfb.NPC_TAG_SHIFT) | (h & ((1UL << (int)Dfb.NPC_TAG_SHIFT) - 1));
        }

        // The id of a quest Person placed at a quest marker, or 0 for any other NPC. Stable across saves and visits.
        internal static ulong QuestIdOf(StaticNPC npc)
        {
            if (npc.Data.context != StaticNPC.Context.Custom)
                return 0;
            Questing.QuestResourceBehaviour quest = npc.GetComponent<Questing.QuestResourceBehaviour>();
            if (!quest || quest.TargetSymbol == null || string.IsNullOrEmpty(quest.TargetSymbol.Name))
                return 0;
            uint symbol = 2166136261u; // FNV-1a of the symbol's name, which string.GetHashCode does not promise to keep
            foreach (char ch in quest.TargetSymbol.Name)
                symbol = (symbol ^ ch) * 16777619u;
            return MakeId(0, ScopeQuest, (int)quest.QuestUID, (int)(quest.QuestUID >> 32), (int)symbol, 0);
        }

        // The id of a layout NPC or of a quest Person at a quest marker, or 0 for one Doom cannot draw.
        internal static ulong IdOf(StaticNPC npc)
        {
            StaticNPC.NPCData data = npc.Data;
            if (data.context == StaticNPC.Context.Custom)
            {
                ulong quest = QuestIdOf(npc);
                if (quest != 0)
                    return quest;
            }
            int locationIndex = GameManager.Instance.PlayerGPS.CurrentLocation.LocationIndex;
            switch (data.context)
            {
                case StaticNPC.Context.Building:
                    int x, y, record;
                    BuildingDirectory.ReverseBuildingKey(data.buildingKey, out x, out y, out record);
                    return MakeId(data.mapID, ScopeInterior, x, y, record, data.nameSeed ^ (data.buildingKey + locationIndex));
                case StaticNPC.Context.Dungeon:
                    DaggerfallDungeon dungeon = npc.GetComponentInParent<DaggerfallDungeon>();
                    Transform rdb = BlockRoot(npc.transform, dungeon ? dungeon.transform : null);
                    if (!rdb)
                        return 0;
                    Vector3 inDungeon = dungeon.transform.InverseTransformPoint(rdb.position);
                    return MakeId(data.mapID, ScopeDungeon, Mathf.RoundToInt(inDungeon.x / RDBLayout.RDBSide), Mathf.RoundToInt(inDungeon.z / RDBLayout.RDBSide), 0, data.nameSeed ^ locationIndex);
                default:
                    DaggerfallLocation location = npc.GetComponentInParent<DaggerfallLocation>();
                    Transform rmb = BlockRoot(npc.transform, location ? location.transform : null);
                    if (!rmb || !rmb.GetComponent<DaggerfallRMBBlock>())
                        return 0;
                    // The streaming world offsets every block by the location's origin, so count from the first block.
                    float minX = float.MaxValue, minZ = float.MaxValue;
                    foreach (Transform child in location.transform)
                        if (child.GetComponent<DaggerfallRMBBlock>())
                        {
                            minX = Mathf.Min(minX, child.localPosition.x);
                            minZ = Mathf.Min(minZ, child.localPosition.z);
                        }
                    return MakeId(data.mapID, ScopeExterior, Mathf.RoundToInt((rmb.localPosition.x - minX) / RMBLayout.RMBSide), Mathf.RoundToInt((rmb.localPosition.z - minZ) / RMBLayout.RMBSide), 0, data.nameSeed ^ location.Summary.LegacyLocation.LocationIndex);
            }
        }

        // The direct child of the location or dungeon that holds this NPC.
        static Transform BlockRoot(Transform from, Transform owner)
        {
            if (!owner)
                return null;
            while (from && from.parent != owner)
                from = from.parent;
            return from;
        }

        // Outdoor and dungeon NPCs beyond Daggerfall's culling range have no block parent, so only nearby ones are found.
        internal static StaticNPC FindNpc(ulong id)
        {
            foreach (StaticNPC npc in ActiveGameObjectDatabase.GetActiveStaticNPCs())
                if (IdOf(npc) == id)
                    return npc;
            return null;
        }

        void Update()
        {
            if (Time.unscaledTime < nextPoll && !resend)
                return;
            nextPoll = Time.unscaledTime + PollSeconds;
            if (sync.LoadRunning || !GameManager.HasInstance || !sync.InGame)
                return;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            if (report)
            {
                if (night)
                {
                    night = false;
                    DaggerfallUnity.Instance.WorldTime.Now.Hour = 23;
                }
                Report(ref peer);
            }
            bool interior = peer.worldContext == Dfb.WORLD_INTERIOR;
            if (!interior && peer.worldContext != Dfb.WORLD_DUNGEON)
                return;
            Transform space = sync.ItemSpace(ref peer);
            if (!space)
                return;
            if (space.GetInstanceID() != lastSpace)
            {
                lastSpace = space.GetInstanceID();
                resend = true;
            }
            // Closed shops and owned houses switch their people off. Distance culling only moves them under an inactive parent, so they still count.
            // A dungeon's layout NPCs are always drawn, so a dungeon's list holds only quest Persons.
            present.Clear();
            placed.Clear();
            PlayerEnterExit enter = GameManager.Instance.PlayerEnterExit;
            Transform site = interior ? (enter.Interior ? enter.Interior.transform : null) : (enter.Dungeon ? enter.Dungeon.transform : null);
            int building = enter.BuildingDiscoveryData.buildingKey;
            foreach (StaticNPC npc in ActiveGameObjectDatabase.GetActiveStaticNPCs(true))
            {
                if (!npc.gameObject.activeSelf)
                    continue;
                if (interior && npc.Data.context == StaticNPC.Context.Building && npc.Data.buildingKey == building)
                    present.Add(IdOf(npc));
                else if (site && npc.transform.IsChildOf(site))
                    AddPlaced(npc, space);
            }
            present.Sort();
            placed.Sort((a, b) => a.id.CompareTo(b.id));
            ulong hash = 17;
            foreach (ulong id in present)
                hash = (hash ^ id) * 1099511628211UL;
            foreach (Placed p in placed)
                hash = (hash ^ p.id ^ (ulong)(p.archive << 8 | p.record) ^ (ulong)Mathf.RoundToInt(p.at.x) << 40
                    ^ (ulong)(Mathf.RoundToInt(p.at.y) & 0xFFFFF) << 20 ^ (ulong)(Mathf.RoundToInt(p.at.z) & 0xFFFFF)) * 1099511628211UL;
            if (hash == lastHash && !resend)
                return;
            lastHash = hash;
            resend = false;
            Publish(ref peer);
        }

        // A quest Person at a marker in the current site, with its billboard and where it stands in Doom units.
        void AddPlaced(StaticNPC npc, Transform space)
        {
            ulong id = QuestIdOf(npc);
            Billboard billboard = id != 0 ? npc.GetComponent<Billboard>() : null;
            if (!billboard)
                return;
            float units = DoomPerDaggerfall / MeshReader.GlobalScale;
            Vector3 local = space.InverseTransformPoint(npc.transform.position);
            Vector2 size = billboard.Summary.Size * units;
            placed.Add(new Placed
            {
                id = id,
                archive = billboard.Summary.Archive,
                record = billboard.Summary.Record,
                at = new Vector3(local.x * units, local.z * units, local.y * units - size.y / 2), // a billboard's middle is its position
                size = size,
            });
        }

        void Publish(ref DfbUzState peer)
        {
            generation++;
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_NPCS_BEGIN;
            e.tic = (uint)Time.frameCount;
            e.worldItems.generation = generation;
            e.worldItems.context = peer.worldContext;
            e.worldItems.target = peer.spaceTarget;
            e.worldItems.count = (uint)(present.Count + placed.Count);
            bridge.Send(ref e);
            foreach (ulong id in present)
            {
                DfbEvent row = default(DfbEvent);
                row.kind = Dfb.KIND_NPC;
                row.tic = (uint)Time.frameCount;
                row.npc.id = id;
                row.npc.generation = generation;
                bridge.Send(ref row);
            }
            foreach (Placed p in placed)
            {
                DfbEvent row = default(DfbEvent);
                row.kind = Dfb.KIND_NPC_PLACED;
                row.tic = (uint)Time.frameCount;
                row.worldItem.id = p.id;
                row.worldItem.generation = generation;
                row.worldItem.archive = p.archive;
                row.worldItem.record = p.record;
                row.worldItem.x = p.at.x;
                row.worldItem.y = p.at.y;
                row.worldItem.z = p.at.z;
                row.worldItem.width = p.size.x;
                row.worldItem.height = p.size.y;
                bridge.Send(ref row);
                bridge.LogLine(string.Format("npcs: quest npc {0:x16} billboard {1}/{2} at doom {3:F1},{4:F1},{5:F1} size {6:F1}x{7:F1}",
                    p.id, p.archive, p.record, p.at.x, p.at.y, p.at.z, p.size.x, p.size.y));
            }
            e.kind = Dfb.KIND_NPCS_END;
            bridge.Send(ref e);
            bridge.LogLine(string.Format("npcs: list {0} has {1} present and {2} quest-placed for target {3}", generation, present.Count, placed.Count, peer.spaceTarget));
        }

        // Test only, with -dfnpcreport: each live layout NPC's id and its position in Doom units within its space.
        string lastReport;
        void Report(ref DfbUzState peer)
        {
            Transform space = peer.worldContext == Dfb.WORLD_INTERIOR || peer.worldContext == Dfb.WORLD_DUNGEON ? sync.ItemSpace(ref peer) : null;
            StringBuilder text = new StringBuilder();
            int count = 0;
            float units = DoomPerDaggerfall / MeshReader.GlobalScale;
            foreach (StaticNPC npc in ActiveGameObjectDatabase.GetActiveStaticNPCs())
            {
                ulong id = IdOf(npc);
                if (id == 0)
                    continue;
                Vector3 at = space ? space.InverseTransformPoint(npc.transform.position) : npc.transform.position;
                text.AppendFormat("npcrow {0:x16} {1:F2} {2:F2} {3:F2} {4}\n", id, at.x * units, at.z * units, at.y * units, npc.Data.context);
                count++;
            }
            string body = text.ToString();
            if (body == lastReport)
                return;
            lastReport = body;
            bridge.LogLine(string.Format("npcs: report context {0} target {1} rows {2}", peer.worldContext, peer.spaceTarget, count));
            foreach (string line in body.Split('\n'))
                if (line.Length > 0)
                    bridge.LogLine(line);
        }
    }
}
