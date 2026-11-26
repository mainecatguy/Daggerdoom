// Doomerfall: Daggerfall's side of locked doors (goal 20261125-073553). Daggerfall stays the authority for each door's
// lock: Doom names a dungeon or interior door by Daggerfall Unity's LoadID (block file position + record position, the
// same id RDBLayout gives the DaggerfallActionDoor and the converter exports in DFDOORS and DFACTIONS), and this class
// answers from the live door in Daggerfall's hidden world, whose unlocked state already persists through Daggerfall's
// save (SerializableActionDoor).
//
// DoomerfallDoors connects it to the bridge. Exterior building doors use PlayerActivate's building lock and are not
// handled here yet.

using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallLocks
    {
        internal enum State { Unknown, Unlocked, Locked, Magic }

        static readonly Dictionary<ulong, DaggerfallActionDoor> doors = new Dictionary<ulong, DaggerfallActionDoor>();

        // The live door with that LoadID in the area Daggerfall has loaded, or null.
        internal static DaggerfallActionDoor Find(ulong loadId)
        {
            DaggerfallActionDoor door;
            if (doors.TryGetValue(loadId, out door) && door)
                return door;
            doors.Clear(); // the area changed, or the door is new: index the area again
            PlayerEnterExit enterExit = GameManager.Instance.PlayerEnterExit;
            Component area = enterExit.IsPlayerInsideDungeon ? (Component)enterExit.Dungeon : enterExit.Interior;
            if (!area)
                return null;
            // Includes inactive objects: Doomerfall hides Daggerfall's 3D world.
            foreach (DaggerfallActionDoor d in area.GetComponentsInChildren<DaggerfallActionDoor>(true))
                if (d.LoadID != 0)
                    doors[d.LoadID] = d;
            return doors.TryGetValue(loadId, out door) ? door : null;
        }

        internal static State StateOf(DaggerfallActionDoor door)
        {
            if (!door) return State.Unknown;
            if (door.IsMagicallyHeld) return State.Magic; // Daggerfall: magically held doors cannot be picked
            return door.IsLocked ? State.Locked : State.Unlocked;
        }

        // The look label for a dungeon or interior door, in Daggerfall's own words where it has some: "Locked."
        // (lockedExteriorDoor) and "This is a magically held lock..." (magicLock). A plain unlocked door is "Door" (owner).
        internal static string Label(DaggerfallActionDoor door)
        {
            switch (StateOf(door))
            {
                case State.Magic: return TextManager.Instance.GetLocalizedText("magicLock");
                case State.Locked: return TextManager.Instance.GetLocalizedText("lockedExteriorDoor");
                default: return "Door";
            }
        }

        // Daggerfall's own interior lockpicking chance (5 to 95) for this door and the player now. The minigame turns it
        // into a difficulty; it replaces Daggerfall's roll.
        internal static int Chance(DaggerfallActionDoor door)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            return FormulaHelper.CalculateInteriorLockpickingChance(player.Level, door.CurrentLockValue,
                player.Skills.GetLiveSkillValue(DFCareer.Skills.Lockpicking));
        }

        // One finished minigame attempt (a cancel is not an attempt). Daggerfall's bookkeeping, as in
        // DaggerfallActionDoor.AttemptLockpicking: one Lockpicking tally per attempt. A hit unlocks the door and keeps the
        // pick; a miss breaks one pick. The owner's rule replaces Daggerfall's "no retry at the same skill level"
        // (FailedSkillLevel), so it is not set. Returns the door's state afterwards.
        internal static State ApplyAttempt(DaggerfallActionDoor door, bool hit)
        {
            State before = StateOf(door);
            if (before != State.Locked)
                return before;
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            player.TallySkill(DFCareer.Skills.Lockpicking, 1);
            if (hit)
                door.CurrentLockValue = 0;
            else
                DoomerfallLockpick.BreakOne(player.Items);
            Debug.LogFormat("locks: attempt on {0} {1}, picks left {2}", door.LoadID, hit ? "hit" : "miss", DoomerfallLockpick.Count(player.Items));
            return StateOf(door);
        }
    }
}
