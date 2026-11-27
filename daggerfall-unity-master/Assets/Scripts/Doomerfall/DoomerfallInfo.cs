// Doomerfall: Daggerfall's Info interaction on what Doom's player looks at. Runs only in a bridge session.
//
// Doom names the target: an NPC id, a point on a building, or a monster's Doom name. Daggerfall runs its own Info
// code for it and every message that code shows is sent back for Doom to display. Daggerfall's Info messages are all
// HUD text (PopupMessage is HUD text too), so no Daggerfall window opens and neither game needs to pause.

using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallInfo : MonoBehaviour
    {
        const float FootprintMargin = 1f; // Unity units. Doom's wall can sit a raster cell outside the model.
        const int TextBytes = 40;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        uint nameRequest;
        string monsterName;
        readonly List<KeyValuePair<string, bool>> lines = new List<KeyValuePair<string, bool>>();
        Action<string, bool, float> capture;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            capture = (text, mid, seconds) => { if (!string.IsNullOrEmpty(text)) lines.Add(new KeyValuePair<string, bool>(text, mid)); };
        }

        internal DoomerfallItems Items;
        internal DoomerfallTownspeople Townspeople;

        // The label under Doom's crosshair (UZDoom/src/dd_look.cpp): the name Daggerfall knows for an NPC, townsperson, pile
        // or building door. Reads only; it runs no interaction, so nothing is discovered or changed, and it answers while paused.
        internal void OnLook(uint request, uint target, ulong id, double worldX, double worldZ)
        {
            string label = "";
            if (!sync.LoadRunning && GameManager.HasInstance && sync.InGame)
                label = Label(request, target, id, worldX, worldZ) ?? "";
            Send(request, label, false, Dfb.KIND_LOOK_TEXT);
            bridge.LogLine(string.Format("look: request {0} target {1} id {2:x16}: [{3}]", request, target, id, label));
        }

        string Label(uint request, uint target, ulong id, double worldX, double worldZ)
        {
            switch (target)
            {
                case Dfb.INFO_DOOM_GUN:
                    // The pickup class came in the DFB_KIND_INFO_NAME just before; world_x is the material it carries + 1.
                    return request == nameRequest ? DoomerfallDoomItems.FloorGunLabel(monsterName, id, (int)worldX) : "";
                case Dfb.INFO_NPC:
                    StaticNPC npc = DoomerfallNpcs.FindNpc(id);
                    return npc ? npc.DisplayName : "";
                case Dfb.INFO_TOWNSPERSON:
                    TownPerson person = Townspeople ? Townspeople.FindPerson(id) : null;
                    return person != null ? person.Name : "";
                case Dfb.INFO_PILE:
                    return Items ? Items.Label(id) : "";
                case Dfb.INFO_DOOR:
                    return DoomerfallLocks.Label((int)id); // the door's live lock value, from Doom
                case Dfb.INFO_BUILDING:
                    // As Daggerfall's Info names a building (PlayerActivate.ActivateBuilding), without discovering it.
                    StaticBuilding building;
                    if (!FindBuilding(worldX, worldZ, out building))
                        return "";
                    PlayerGPS gps = GameManager.Instance.PlayerGPS;
                    PlayerGPS.DiscoveredBuilding known;
                    if (!gps.GetDiscoveredBuilding(building.buildingKey, out known) && !gps.GetBaseBuildingDiscoveryData(building.buildingKey, out known))
                        return "";
                    return DaggerfallWorkshop.Localization.GrammarManager.grammarProcessor.ProcessGrammar(known.displayName);
            }
            return "";
        }

        internal void OnName(uint request, string name)
        {
            nameRequest = request;
            monsterName = name;
        }

        internal void OnRequest(uint request, uint target, ulong id, double worldX, double worldZ)
        {
            lines.Clear();
            string what = "nothing";
            if (!sync.LoadRunning && GameManager.HasInstance && sync.InGame && !GameManager.IsGamePaused)
            {
                Action<string, bool, float> standing = DaggerfallUI.DoomerfallHudText; // DoomerfallHudMessages, while not captured
                DaggerfallUI.DoomerfallHudText = capture;
                try { what = Run(request, target, id, worldX, worldZ); }
                finally { DaggerfallUI.DoomerfallHudText = standing; }
            }
            foreach (KeyValuePair<string, bool> line in lines)
                Send(request, line.Key, line.Value);
            var log = new StringBuilder();
            log.AppendFormat("info: request {0} target {1} on {2}: {3} messages", request, target, what, lines.Count);
            foreach (KeyValuePair<string, bool> line in lines)
                log.Append(line.Value ? " | mid: " : " | ").Append(line.Key);
            bridge.LogLine(log.ToString());
        }

        string Run(uint request, uint target, ulong id, double worldX, double worldZ)
        {
            switch (target)
            {
                case Dfb.INFO_NPC:
                    StaticNPC npc = DoomerfallNpcs.FindNpc(id);
                    if (!npc)
                        return string.Format("npc {0:x16} (not found)", id);
                    GameManager.Instance.PlayerActivate.DoomerfallInfoNpc(npc);
                    return string.Format("npc {0:x16}", id);

                case Dfb.INFO_MONSTER:
                    if (request != nameRequest || string.IsNullOrEmpty(monsterName))
                        return "monster (no name)";
                    // As PlayerActivate.ActivateMobileEnemy, with the Doom monster's own name.
                    bool vowel = "aeiouAEIOU".IndexOf(monsterName[0]) >= 0;
                    string message = TextManager.Instance.GetLocalizedText(vowel ? "youSeeAn" : "youSeeA").Replace("%s", monsterName);
                    DaggerfallUI.Instance.PopupMessage(message);
                    return "monster " + monsterName;

                case Dfb.INFO_BUILDING:
                    StaticBuilding building;
                    if (!FindBuilding(worldX, worldZ, out building))
                        return string.Format("point {0:F0},{1:F0} (no building)", worldX, worldZ);
                    PlayerGPS gps = GameManager.Instance.PlayerGPS;
                    PlayerGPS.DiscoveredBuilding known;
                    bool before = gps.GetDiscoveredBuilding(building.buildingKey, out known);
                    GameManager.Instance.PlayerActivate.DoomerfallInfoBuilding(building);
                    return string.Format("building {0} at {1:F0},{2:F0} (on the map before: {3}, after: {4})", building.buildingKey, worldX, worldZ,
                        before, gps.GetDiscoveredBuilding(building.buildingKey, out known));
            }
            return "unknown target";
        }

        // The building whose footprint holds the world point. Daggerfall's own HasHit tests a point in 3D, and Doom's
        // heights do not match Daggerfall's, so this tests the footprint only.
        bool FindBuilding(double worldX, double worldZ, out StaticBuilding found)
        {
            found = new StaticBuilding();
            GameManager game = GameManager.Instance;
            if (game.PlayerEnterExit.IsPlayerInside)
                return false;
            DaggerfallLocation location = game.StreamingWorld.CurrentPlayerLocationObject;
            if (!location)
                return false;
            PlayerGPS gps = game.PlayerGPS;
            Vector3 player = gps.transform.position;
            Vector3 point = new Vector3(
                player.x + (float)((worldX - gps.WorldX) / StreamingWorld.SceneMapRatio), 0,
                player.z + (float)((worldZ - gps.WorldZ) / StreamingWorld.SceneMapRatio));
            float best = FootprintMargin;
            bool any = false;
            foreach (DaggerfallStaticBuildings collection in location.GetComponentsInChildren<DaggerfallStaticBuildings>())
            {
                if (collection.Buildings == null)
                    continue;
                foreach (StaticBuilding b in collection.Buildings)
                {
                    Vector3 origin = (Vector3)b.modelMatrix.GetColumn(3) + collection.transform.position;
                    Quaternion rotation = Quaternion.LookRotation(b.modelMatrix.GetColumn(2), b.modelMatrix.GetColumn(1));
                    Vector3 local = Quaternion.Inverse(rotation) * (point - origin);
                    float outside = Mathf.Max(Mathf.Abs(local.x - b.centre.x) - b.size.x / 2, Mathf.Abs(local.z - b.centre.z) - b.size.z / 2);
                    if (outside <= best)
                    {
                        best = outside;
                        found = b;
                        any = true;
                    }
                }
            }
            return any;
        }

        // Runs a Daggerfall interaction and sends every HUD message it shows to Doom as the answer to this request.
        internal void Capture(uint request, Action run, string what)
        {
            lines.Clear();
            Action<string, bool, float> standing = DaggerfallUI.DoomerfallHudText;
            DaggerfallUI.DoomerfallHudText = capture;
            try { run(); }
            finally { DaggerfallUI.DoomerfallHudText = standing; }
            var log = new StringBuilder();
            log.AppendFormat("{0}: {1} messages", what, lines.Count);
            foreach (KeyValuePair<string, bool> line in lines)
            {
                Send(request, line.Key, line.Value);
                log.Append(line.Value ? " | mid: " : " | ").Append(line.Key);
            }
            bridge.LogLine(log.ToString());
        }

        // Long messages go out in parts. Doom joins them until an event without DFB_INFO_MORE.
        internal void Send(uint request, string text, bool mid, ushort kind = Dfb.KIND_INFO_TEXT)
        {
            SendText(bridge, request, text, mid, kind);
        }

        internal static void SendText(DoomerfallBridge bridge, uint request, string text, bool mid, ushort kind)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(text);
            int at = 0;
            do
            {
                int count = Math.Min(TextBytes, bytes.Length - at);
                // Never split a UTF-8 sequence.
                while (count < bytes.Length - at && count > 0 && (bytes[at + count] & 0xC0) == 0x80)
                    count--;
                byte[] body = new byte[48];
                BitConverter.GetBytes(request).CopyTo(body, 0);
                BitConverter.GetBytes(mid ? Dfb.INFO_MID : Dfb.INFO_HUD).CopyTo(body, 4);
                Array.Copy(bytes, at, body, 8, count);
                at += count;
                DfbEvent e = default(DfbEvent);
                e.kind = kind;
                e.tic = (uint)Time.frameCount;
                e.flags = (ushort)(at < bytes.Length ? Dfb.INFO_MORE : 0);
                e.SetPayload(body, body.Length);
                bridge.Send(ref e);
            }
            while (at < bytes.Length);
        }
    }
}
