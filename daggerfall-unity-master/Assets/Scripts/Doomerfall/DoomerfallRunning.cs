// Doomerfall: Running skill uses from running in Doom. The hidden Daggerfall pawn never runs, so Doom reports the time
// its player ran (UZDoom/src/dd_running.cpp: the run key held while moving). Input: DFB_KIND_RUN_TIME, in Doom tics.
// Output: Daggerfall's own TallySkill(Running), so advancement stays Daggerfall's.
// Rate: PlayerEntity.FixedUpdate tallies one use every 4 classic updates while running. A classic update comes on the
// first FixedUpdate at or past GameManager.classicUpdateInterval (the timer restarts from 0), so its real period is a
// whole number of fixed steps: 0.08 s at the project's 0.02 s step, one use per 0.32 s of running. Owner (2026-11-25):
// running in Doom tallies at 1.5 times that rate, one use per 0.2133 s (about 4.7 a second).

using System;
using DaggerfallConnect;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallRunning
    {
        const double DoomTicSeconds = 1.0 / 35;
        const int ClassicUpdatesPerUse = 4;  // PlayerEntity.FixedUpdate's runningTallyCounter
        const double RateMultiplier = 1.5;   // owner, 2026-11-25

        static double pendingUses;           // the fraction of a use carried between reports

        // Seconds of running per Running use in Daggerfall Unity itself.
        internal static double DaggerfallSecondsPerUse
        {
            get
            {
                double step = Time.fixedDeltaTime;
                double classic = Math.Ceiling(GameManager.classicUpdateInterval / step - 1e-6) * step;
                return ClassicUpdatesPerUse * classic;
            }
        }

        internal static void OnRunTime(DoomerfallBridge bridge, uint tics)
        {
            if (!GameManager.HasInstance || GameManager.Instance.PlayerEntity == null || tics == 0)
                return;
            if (tics > 35 * 60)
                return; // Doom reports about once a second, so a large value is a fault.
            if (GameManager.Instance.PlayerMotor != null && GameManager.Instance.PlayerMotor.IsRiding)
                return; // Daggerfall's rule: no Running uses while riding.

            pendingUses += tics * DoomTicSeconds * RateMultiplier / DaggerfallSecondsPerUse;
            short uses = (short)Math.Floor(pendingUses);
            pendingUses -= uses;
            if (uses > 0)
                GameManager.Instance.PlayerEntity.TallySkill(DFCareer.Skills.Running, uses);
            if (bridge.LogEnabled)
                bridge.LogLine(string.Format("running: {0} running tics, tallied {1} Running uses, total {2}", tics, uses,
                    GameManager.Instance.PlayerEntity.SkillUses[(int)DFCareer.Skills.Running]));
        }
    }
}
