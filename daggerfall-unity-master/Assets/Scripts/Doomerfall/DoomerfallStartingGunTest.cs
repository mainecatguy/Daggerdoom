// Doomerfall test only (-dfstartguntest <skills>): the starting gun of a bridged New Game (DoomerfallStartingGun).
// <skills> is one or more of Pistols, Rifles, Automatics, Shotguns, Explosives, Melee joined by '+' (a tie), or "none".
// Until the starting guns are given, the new character's six gun skills are held at 10, and the named ones at 90 ("none":
// all six at 0). Six seconds after Doom takes the drawn gun, writes one "startguntest: report" line with the active gun,
// the Doom items in Daggerfall's inventory, the hotkey table, and whether Doom's ammo counters agree with Daggerfall's
// stacks, then "startguntest: done". tools/starting_gun/run_starting_gun.py checks the report against the owner's table.

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallStartingGunTest : MonoBehaviour
    {
        static readonly DFCareer.Skills[] Six = { DFCareer.Skills.Pistols, DFCareer.Skills.Rifles, DFCareer.Skills.Automatics,
            DFCareer.Skills.Shotguns, DFCareer.Skills.Explosives, DFCareer.Skills.Melee };

        DoomerfallBridge bridge;
        readonly List<DFCareer.Skills> high = new List<DFCareer.Skills>();
        bool none, reported;
        float reportAt = -1;

        internal static void Attach(DoomerfallBridge owner)
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfstartguntest");
            if (at >= 0 && at + 1 < args.Length)
                owner.gameObject.AddComponent<DoomerfallStartingGunTest>().Init(owner, args[at + 1]);
        }

        void Init(DoomerfallBridge owner, string skills)
        {
            bridge = owner;
            none = skills == "none";
            if (!none)
                foreach (string name in skills.Split('+'))
                    high.Add((DFCareer.Skills)Enum.Parse(typeof(DFCareer.Skills), name, true));
            bridge.LogLine("startguntest: holding the gun skills, high: " + skills);
        }

        void Update()
        {
            if (reported || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return;
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            if (DoomerfallStartingGun.Given == 0)
            {
                foreach (DFCareer.Skills s in Six)
                    GameManager.Instance.PlayerEntity.Skills.SetPermanentSkillValue(s, (short)(none ? 0 : high.Contains(s) ? 90 : 10));
                return;
            }
            if (hotkeys == null || hotkeys.ActiveGun == null || hotkeys.SwapInFlight)
                return; // Doom has not taken the drawn gun yet.
            if (reportAt < 0)
                reportAt = Time.unscaledTime + 6f;
            if (Time.unscaledTime < reportAt)
                return;
            reported = true;
            DoomerfallAmmo ammo = GetComponent<DoomerfallAmmo>();
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            List<string> guns = new List<string>();
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem gun = items.GetItem(i) as DoomerfallDoomItem;
                if (gun != null && gun.IsGun) guns.Add(gun.DoomClass);
            }
            bridge.LogLine(string.Format("startguntest: report active={0} guns={1} | table={2} | settled={3} totals={4},{5},{6},{7}",
                hotkeys.ActiveGun.DoomClass, string.Join("+", guns.ToArray()), hotkeys.Describe(), ammo != null && ammo.Settled,
                DoomerfallAmmo.Total(items, 0), DoomerfallAmmo.Total(items, 1), DoomerfallAmmo.Total(items, 2), DoomerfallAmmo.Total(items, 3)));
            bridge.LogLine("startguntest: done");
        }
    }
}
