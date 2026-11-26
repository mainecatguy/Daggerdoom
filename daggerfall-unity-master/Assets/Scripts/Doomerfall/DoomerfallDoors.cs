// Doomerfall: Daggerfall's side of locked dungeon doors (bridge kinds DFB_KIND_DOOR_*). Runs only in a bridge session.
//
// Daggerfall owns every lock: the live DaggerfallActionDoor in its hidden dungeon, whose CurrentLockValue already
// persists through Daggerfall's save. Doom keeps a door shut while this class lists it as locked, asks here when the
// player uses it, and runs the lockpicking minigame with Daggerfall's chance. The result comes back here, where
// DoomerfallLocks does Daggerfall's bookkeeping (skill tally, broken pick, unlock).
//
// The full locked list goes to Doom whenever the dungeon, a load, or any lock changes it, and whenever Doom asks
// (a new map or a load on Doom's side), so a reload restores exactly the locks Daggerfall's save holds.

using System.Collections.Generic;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallDoors : MonoBehaviour
    {
        const float PollSeconds = 0.5f;

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallInfo info;
        float nextPoll;
        bool resend = true;
        ulong lastHash;
        int lastSpace;
        DaggerfallActionDoor[] spaceDoors = new DaggerfallActionDoor[0];
        ulong pickDoor; // the door the minigame runs on; only its result is accepted
        readonly List<KeyValuePair<ulong, uint>> locked = new List<KeyValuePair<ulong, uint>>();

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync, DoomerfallInfo infoSender)
        {
            bridge = owner;
            sync = positionSync;
            info = infoSender;
        }

        internal void OnRequest()
        {
            resend = true;
        }

        bool Ready
        {
            get { return !sync.LoadRunning && GameManager.HasInstance && sync.InGame && GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon; }
        }

        // Use on a door Doom holds as locked.
        internal void OnUse(ulong id)
        {
            if (!Ready)
                return;
            DaggerfallActionDoor door = DoomerfallLocks.Find(id);
            DoomerfallLocks.State state = DoomerfallLocks.StateOf(door);
            int picks = DoomerfallLockpick.Count(GameManager.Instance.PlayerEntity.Items);
            bridge.LogLine(string.Format("doors: use {0} state {1} picks {2}", id, state, picks));
            switch (state)
            {
                case DoomerfallLocks.State.Unknown:
                    return;
                case DoomerfallLocks.State.Unlocked:
                    Send(id, Dfb.DOOR_UNLOCKED, Dfb.DOOR_OPEN, 0, picks); // Doom's list was stale; open it
                    resend = true;
                    return;
                case DoomerfallLocks.State.Magic:
                    Text(DoomerfallLocks.Label(door));
                    return;
            }
            if (picks <= 0)
            {
                Text(DoomerfallLocks.Label(door)); // card 01: the locked message only
                return;
            }
            pickDoor = id;
            Send(id, Dfb.DOOR_LOCKED, Dfb.DOOR_PICK, DoomerfallLocks.Chance(door), picks);
        }

        // The minigame's result for the door named in the last DFB_DOOR_PICK. A cancel costs nothing.
        internal void OnLockpick(ulong id, uint result)
        {
            if (id != pickDoor || pickDoor == 0)
            {
                bridge.LogLine(string.Format("doors: ignored lockpick result {0} for {1} (expected {2})", result, id, pickDoor));
                return;
            }
            pickDoor = 0;
            if (result == Dfb.PICK_CANCEL || !Ready)
            {
                bridge.LogLine(string.Format("doors: lockpick on {0} cancelled", id));
                return;
            }
            DaggerfallActionDoor door = DoomerfallLocks.Find(id);
            bool hit = result == Dfb.PICK_HIT;
            DoomerfallLocks.State after = DoomerfallLocks.ApplyAttempt(door, hit);
            int picks = DoomerfallLockpick.Count(GameManager.Instance.PlayerEntity.Items);
            bridge.LogLine(string.Format("doors: lockpick on {0} {1}, now {2}, picks {3}", id, hit ? "hit" : "miss", after, picks));
            Text(TextManager.Instance.GetLocalizedText(hit ? "lockpickingSuccess" : "lockpickingFailure"));
            if (after == DoomerfallLocks.State.Unlocked)
                Send(id, Dfb.DOOR_UNLOCKED, Dfb.DOOR_OPEN, 0, picks);
            resend = true;
        }

        void Update()
        {
            if (Time.unscaledTime < nextPoll && !resend)
                return;
            nextPoll = Time.unscaledTime + PollSeconds;
            if (sync.LoadRunning)
            {
                lastHash = 0; // a load restores Daggerfall's locks: send them again afterwards
                return;
            }
            if (!Ready)
                return;
            DfbUzState peer;
            bridge.ReadPeerState(out peer);
            if (peer.worldContext != Dfb.WORLD_DUNGEON || GameManager.Instance.PlayerGPS.CurrentLocation.MapTableData.MapId != peer.spaceTarget)
                return;
            DaggerfallDungeon dungeon = GameManager.Instance.PlayerEnterExit.Dungeon;
            if (!dungeon)
                return;
            if (dungeon.GetInstanceID() != lastSpace)
            {
                lastSpace = dungeon.GetInstanceID();
                spaceDoors = dungeon.GetComponentsInChildren<DaggerfallActionDoor>(true);
                lastHash = 0;
                pickDoor = 0;
            }
            locked.Clear();
            ulong hash = 14695981039346656037UL;
            foreach (DaggerfallActionDoor door in spaceDoors)
            {
                if (!door || door.LoadID == 0)
                    continue;
                DoomerfallLocks.State state = DoomerfallLocks.StateOf(door);
                if (state != DoomerfallLocks.State.Locked && state != DoomerfallLocks.State.Magic)
                    continue;
                uint wire = state == DoomerfallLocks.State.Magic ? Dfb.DOOR_MAGIC : Dfb.DOOR_LOCKED;
                locked.Add(new KeyValuePair<ulong, uint>(door.LoadID, wire));
                hash = (hash ^ door.LoadID ^ ((ulong)wire << 60)) * 1099511628211UL;
            }
            hash |= 1; // never 0, so a cleared hash always sends
            if (hash == lastHash && !resend)
                return;
            lastHash = hash;
            resend = false;
            for (int i = 0; i < locked.Count; i++)
                Send(locked[i].Key, locked[i].Value, (i == 0 ? Dfb.DOOR_LIST_BEGIN : 0) | (i == locked.Count - 1 ? Dfb.DOOR_LIST_END : 0), 0, 0);
            if (locked.Count == 0)
                Send(0, 0, Dfb.DOOR_LIST_BEGIN | Dfb.DOOR_LIST_END, 0, 0);
            bridge.LogLine(string.Format("doors: sent the locked list, {0} of {1} doors", locked.Count, spaceDoors.Length));
        }

        void Send(ulong id, uint state, uint flags, int chance, int picks)
        {
            DfbEvent e = default(DfbEvent);
            e.kind = Dfb.KIND_DOOR_STATE;
            e.tic = (uint)Time.frameCount;
            e.door.id = id;
            e.door.kind = Dfb.DOOR_DUNGEON;
            e.door.state = state;
            e.door.flags = flags;
            e.door.chance = chance;
            e.door.picks = picks;
            bridge.Send(ref e);
        }

        void Text(string text)
        {
            info.Send(0, text, false, Dfb.KIND_DOOR_TEXT);
        }
    }
}
