// Doomerfall: Daggerfall's lock rules for doors (goal 20261125-073553). Doom holds each live lock on the current map
// and names it by its lock value (DaggerfallActionDoor.CurrentLockValue's meaning: 0 unlocked, 1 to 19 locked,
// 20 or more magically held). These answer from that value and the player: the label, the lockpicking chance, and the
// bookkeeping of one attempt.
//
// DoomerfallDoors connects it to the bridge. Exterior building doors use PlayerActivate's building lock and are not
// handled here yet.

using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallLocks
    {
        // The look label for a door with this lock, in Daggerfall's own words where it has some: "Locked."
        // (lockedExteriorDoor) and "This is a magically held lock..." (magicLock). A plain unlocked door is "Door" (owner).
        internal static string Label(int lockValue)
        {
            if (lockValue >= 20) return TextManager.Instance.GetLocalizedText("magicLock");
            if (lockValue > 0) return TextManager.Instance.GetLocalizedText("lockedExteriorDoor");
            return "Door";
        }

        // Daggerfall's own interior lockpicking chance (5 to 95) for this lock and the player now. The minigame turns it
        // into a difficulty; it replaces Daggerfall's roll.
        internal static int Chance(int lockValue)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            return FormulaHelper.CalculateInteriorLockpickingChance(player.Level, lockValue,
                player.Skills.GetLiveSkillValue(DFCareer.Skills.Lockpicking));
        }

        // One finished minigame attempt (a cancel is not an attempt). Daggerfall's bookkeeping, as in
        // DaggerfallActionDoor.AttemptLockpicking: one Lockpicking tally per attempt. A hit keeps the pick; a miss breaks
        // one. The owner's rule replaces Daggerfall's "no retry at the same skill level" (FailedSkillLevel), so it is not
        // kept. Doom unlocks and opens the door itself on a hit.
        internal static void ApplyAttempt(bool hit)
        {
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            player.TallySkill(DFCareer.Skills.Lockpicking, 1);
            if (!hit)
                DoomerfallLockpick.BreakOne(player.Items);
            Debug.LogFormat("locks: attempt {0}, picks left {1}", hit ? "hit" : "miss", DoomerfallLockpick.Count(player.Items));
        }
    }
}
