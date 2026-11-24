// Doomerfall: Daggerfall's side of NPC identity and presence. Runs only in a bridge session.
//
// An NPC id is tag (3 bits, value 6) | hash of its layout record (61). The converter computes the same id in
// NpcIdentity.cs. Inside a building, this lists who Daggerfall has present, so closed shops and owned houses stay
// empty in Doom. FindNpc turns an id back into the live StaticNPC for later talk and death work.

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
        const int ScopeExterior = 1, ScopeInterior = 2, ScopeDungeon = 3;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        readonly List<ulong> present = new List<ulong>();
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

        // The id of a layout NPC, or 0 for one a quest created.
        internal static ulong IdOf(StaticNPC npc)
        {
            StaticNPC.NPCData data = npc.Data;
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
            if (peer.worldContext != Dfb.WORLD_INTERIOR)
                return;
            Transform space = sync.ItemSpace(ref peer);
            if (!space)
                return;
            if (space.GetInstanceID() != lastSpace)
            {
                lastSpace = space.GetInstanceID();
                resend = true;
            }
            present.Clear();
            ulong hash = 17;
            foreach (StaticNPC npc in space.GetComponentsInChildren<StaticNPC>(false))
            {
                ulong id = IdOf(npc);
                if (id == 0)
                    continue;
                present.Add(id);
                hash = (hash ^ id) * 1099511628211UL;
            }
            if (hash == lastHash && !resend)
                return;
            lastHash = hash;
            resend = false;
            Publish(ref peer);
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
            e.worldItems.count = (uint)present.Count;
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
            e.kind = Dfb.KIND_NPCS_END;
            bridge.Send(ref e);
            bridge.LogLine(string.Format("npcs: list {0} has {1} present for target {2}", generation, present.Count, peer.spaceTarget));
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
