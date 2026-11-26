// Doomerfall: Daggerfall's side of locked dungeon doors (bridge kinds DFB_KIND_DOOR_*). Runs only in a bridge session.
//
// Doom owns each live lock on the current map and runs Daggerfall's door order (door_objects.zs). Daggerfall owns the
// rules and the player: Doom asks here when the player uses a locked door, with the door's lock value, and this class
// answers with Daggerfall's chance (the minigame starts) or a refusal message (no picks, magically held). The
// minigame's result comes back for Daggerfall's bookkeeping (skill tally, broken pick, message).
//
// The doors the player picked open are a permanent fact per dungeon, kept here and saved with the game. When Doom
// builds a dungeon's map fresh it asks for its facts: this class arms the locks and names the picked doors. A saved
// game restores Doom's own live locks instead.

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using DaggerfallWorkshop.Game.Serialization;
using FullSerializer;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallDoors : MonoBehaviour
    {
        const string LedgerFile = "DoomerfallDoors.json";

        // Castle Daggerfall's magically held foyer doors (DaggerfallAction.CastleDaggerfallMagicDoorsSpecialOpenHack).
        const int CastleDaggerfallMapId = 1291010263;
        static readonly ulong[] CastleFoyerDoors = { 29331574, 29331622 };

        [fsObject("v1")]
        public sealed class LedgerData
        {
            // Dungeon MapId -> LoadIDs of the doors the player picked open there.
            public Dictionary<string, List<ulong>> picked = new Dictionary<string, List<ulong>>();
        }

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallInfo info;
        LedgerData ledger = new LedgerData();
        bool factsWanted;
        ulong pickDoor; // the door the minigame runs on; only its result is accepted

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, DoomerfallInfo infoSender)
        {
            bridge = owner;
            sync = positionSync;
            info = infoSender;
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame += OnStartGame;
        }

        void OnDestroy()
        {
            DaggerfallWorkshop.Game.Utility.StartGameBehaviour.OnStartGame -= OnStartGame;
        }

        bool InGame
        {
            get { return !sync.LoadRunning && GameManager.HasInstance && sync.InGame; }
        }

        // Daggerfall is in the dungeon Doom is in. The facts and picks belong to it.
        bool InDoomsDungeon(out string key)
        {
            key = null;
            if (!InGame || !GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon)
                return false;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            int mapId = GameManager.Instance.PlayerGPS.CurrentLocation.MapTableData.MapId;
            if (peer.worldContext != Dfb.WORLD_DUNGEON || mapId != peer.spaceTarget)
                return false;
            key = mapId.ToString();
            return true;
        }

        // Doom built a dungeon map fresh. Answered once Daggerfall is in the same dungeon (see Update).
        internal void OnFactsRequest()
        {
            factsWanted = true;
            pickDoor = 0;
        }

        // Use on a shut door whose live lock (in Doom) is lockValue.
        internal void OnUse(ulong id, uint lockValue)
        {
            if (!InGame)
                return;
            int lockAt = (int)lockValue;
            int picks = DoomerfallLockpick.Count(GameManager.Instance.PlayerEntity.Items);
            bridge.LogLine(string.Format("doors: use {0} lock {1} picks {2}", id, lockAt, picks));
            if (lockAt <= 0)
                return;
            if (lockAt >= 20) // magically held: cannot be picked
            {
                Text(DoomerfallLocks.Label(lockAt));
                if (CastleFoyerOpens(id))
                    Send(id, Dfb.DOOR_OPEN, 0, 0, picks);
                return;
            }
            if (picks <= 0)
            {
                Text(DoomerfallLocks.Label(lockAt)); // card 01: the locked message only
                return;
            }
            pickDoor = id;
            Send(id, Dfb.DOOR_PICK, 0, DoomerfallLocks.Chance(lockAt), picks);
        }

        // Daggerfall Unity lets a player who teleported into Castle Daggerfall open its magically held foyer doors, so
        // they cannot be shut in the throne room. The player still sees the magically held message, then the door opens.
        static bool CastleFoyerOpens(ulong id)
        {
            PlayerEnterExit enterExit = GameManager.Instance.PlayerEnterExit;
            return enterExit.PlayerTeleportedIntoDungeon && enterExit.IsPlayerInsideDungeon &&
                GameManager.Instance.PlayerGPS.CurrentLocation.MapTableData.MapId == CastleDaggerfallMapId &&
                Array.IndexOf(CastleFoyerDoors, id) >= 0;
        }

        // The minigame's result for the door named in the last DFB_DOOR_PICK. A cancel costs nothing. Doom opens the door
        // itself on a hit, so Daggerfall only does its bookkeeping and keeps the fact.
        internal void OnLockpick(ulong id, uint result)
        {
            if (id != pickDoor || pickDoor == 0)
            {
                bridge.LogLine(string.Format("doors: ignored lockpick result {0} for {1} (expected {2})", result, id, pickDoor));
                return;
            }
            pickDoor = 0;
            if (result == Dfb.PICK_CANCEL || !InGame)
            {
                bridge.LogLine(string.Format("doors: lockpick on {0} cancelled", id));
                return;
            }
            bool hit = result == Dfb.PICK_HIT;
            DoomerfallLocks.ApplyAttempt(hit);
            string key;
            if (hit && InDoomsDungeon(out key))
            {
                List<ulong> doors;
                if (!ledger.picked.TryGetValue(key, out doors))
                    ledger.picked[key] = doors = new List<ulong>();
                if (!doors.Contains(id))
                    doors.Add(id);
            }
            bridge.LogLine(string.Format("doors: lockpick on {0} {1}, picks {2}", id, hit ? "hit" : "miss", DoomerfallLockpick.Count(GameManager.Instance.PlayerEntity.Items)));
            Text(TextManager.Instance.GetLocalizedText(hit ? "lockpickingSuccess" : "lockpickingFailure"));
        }

        void Update()
        {
            string key;
            if (!factsWanted || !InDoomsDungeon(out key))
                return;
            factsWanted = false;
            List<ulong> doors;
            if (!ledger.picked.TryGetValue(key, out doors))
                doors = new List<ulong>();
            int count = doors.Count;
            Send(0, Dfb.DOOR_ARM, (uint)count, 0, 0); // the count tells Doom when its door setup is complete
            foreach (ulong id in doors)
                Send(id, Dfb.DOOR_FACT, 0, 0, 0);
            bridge.LogLine(string.Format("doors: armed dungeon {0}, {1} picked open", key, count));
        }

        void Send(ulong id, uint flags, uint lockValue, int chance, int picks)
        {
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_DOOR_STATE;
            e.tic = (uint)Time.frameCount;
            e.door.id = id;
            e.door.kind = Dfb.DOOR_DUNGEON;
            e.door.state = lockValue;
            e.door.flags = flags;
            e.door.chance = chance;
            e.door.picks = picks;
            bridge.Send(ref e);
        }

        void Text(string text)
        {
            info.Send(0, text, false, Dfb.KIND_DOOR_TEXT);
        }

        // A new character starts with no picked doors. A loaded game replaces the ledger in ReadLedger.
        void OnStartGame(object sender, EventArgs e)
        {
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return;
            ForgetWorld();
        }

        internal void ForgetWorld()
        {
            ledger = new LedgerData();
            pickDoor = 0;
        }

        // Called with the staged save, before the bundle's file count is taken.
        internal void WriteLedger(string folder)
        {
            File.WriteAllText(Path.Combine(folder, LedgerFile), SaveLoadManager.Serialize(typeof(LedgerData), ledger, false), new UTF8Encoding(false));
        }

        // A save without the file comes from before this feature: no door was picked open.
        internal void ReadLedger(string folder)
        {
            string path = Path.Combine(folder, LedgerFile);
            ledger = File.Exists(path) ? (LedgerData)SaveLoadManager.Deserialize(typeof(LedgerData), File.ReadAllText(path)) ?? new LedgerData() : new LedgerData();
            if (ledger.picked == null)
                ledger.picked = new Dictionary<string, List<ulong>>();
            pickDoor = 0;
            factsWanted = false; // the loaded game's map brings its own live locks
            bridge.LogLine("doors: ledger restored with " + ledger.picked.Count + " dungeons");
        }
    }
}
