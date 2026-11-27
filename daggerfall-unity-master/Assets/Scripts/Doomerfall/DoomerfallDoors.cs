// Doomerfall: Daggerfall's side of locked dungeon doors (bridge kinds DFB_KIND_DOOR_*). Runs only in a bridge session.
//
// Doom owns each live lock on the current map and runs Daggerfall's door order (door_objects.zs). Daggerfall owns the
// rules and the player: Doom asks here when the player uses a locked door, with the door's lock value, and this class
// answers with Daggerfall's chance (the minigame starts) or a refusal message (no picks, magically held). The
// minigame's result comes back for Daggerfall's bookkeeping (skill tally, broken pick, message).
//
// Doom starts each door at the converted map's starting lock. Every lock change since (picks, levers, relocks) is kept
// in the location record's door fact, which Doom reports on leaving and saving (door_objects.zs DFDoorHandler.Distill)
// and DoomerfallLocations keeps and saves. A saved game restores Doom's own live locks.

using System;
using DaggerfallWorkshop.Game.Serialization;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallDoors : MonoBehaviour
    {
        // Castle Daggerfall's magically held foyer doors (DaggerfallAction.CastleDaggerfallMagicDoorsSpecialOpenHack).
        const int CastleDaggerfallMapId = 1291010263;
        static readonly ulong[] CastleFoyerDoors = { 29331574, 29331622 };

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        DoomerfallInfo info;
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
        // itself on a hit, so Daggerfall only does its bookkeeping; the door's new lock reaches the location record.
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
            bridge.LogLine(string.Format("doors: lockpick on {0} {1}, picks {2}", id, hit ? "hit" : "miss", DoomerfallLockpick.Count(GameManager.Instance.PlayerEntity.Items)));
            Text(TextManager.Instance.GetLocalizedText(hit ? "lockpickingSuccess" : "lockpickingFailure"));
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

        // A new character, or a loaded game: no minigame result from before belongs to it.
        void OnStartGame(object sender, EventArgs e)
        {
            if (SaveLoadManager.Instance != null && SaveLoadManager.Instance.LoadInProgress)
                return;
            ForgetWorld();
        }

        internal void ForgetWorld()
        {
            pickDoor = 0;
        }
    }
}
