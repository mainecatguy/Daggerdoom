// Doomerfall test only (-dfstartguntest <skills>): the starting gun of a bridged New Game (DoomerfallStartingGun).
// <skills> is skills joined by '+', each optionally "=value" (default 40), for example "Rifles+Pistols" (a tie) or
// "EnergyWeapons+Shotguns=30", or "none" (no gun class skill). Until the starting guns are given, the named skills are
// the character's first class skills at those values and every other gun skill keeps an untrained 3-6 value (Hold).
// Six seconds after Doom takes the drawn gun, writes one "startguntest: report" line with the active gun,
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
                foreach (string part in skills.Split('+'))
                {
                    string[] f = part.Split('=');
                    high.Add((DFCareer.Skills)Enum.Parse(typeof(DFCareer.Skills), f[0], true));
                    values.Add(f.Length > 1 ? short.Parse(f[1]) : (short)40);
                }
            bridge.LogLine("startguntest: holding the class skills: " + skills);
        }

        // Untrained values as character creation rolls them (3-6), chosen so that a character with no gun class skill
        // ties Rifles and Shotguns (both 6) and gets the carbine and the shotgun.
        static readonly DFCareer.Skills[] Seven = { DFCareer.Skills.Pistols, DFCareer.Skills.Rifles, DFCareer.Skills.Automatics,
            DFCareer.Skills.Shotguns, DFCareer.Skills.Explosives, DFCareer.Skills.Melee, DFCareer.Skills.EnergyWeapons };
        static readonly short[] Untrained = { 3, 6, 5, 6, 4, 5, 4 };
        static readonly DFCareer.Skills[] Fillers = { DFCareer.Skills.Medical, DFCareer.Skills.Etiquette, DFCareer.Skills.Streetwise,
            DFCareer.Skills.Jumping, DFCareer.Skills.Lockpicking, DFCareer.Skills.Mercantile, DFCareer.Skills.Pickpocket,
            DFCareer.Skills.Stealth, DFCareer.Skills.Swimming, DFCareer.Skills.Climbing, DFCareer.Skills.Dodging, DFCareer.Skills.Running };
        readonly List<short> values = new List<short>();

        // The named skills become the first class skills at their values (default 40); the other class skills are non-gun
        // skills; the other gun skills and Energy Weapons hold untrained values.
        void Hold(Entity.PlayerEntity player)
        {
            DFCareer c = player.Career;
            if (c == null)
                return;
            DFCareer.Skills[] slots = new DFCareer.Skills[12];
            for (int i = 0, f = 0; i < 12; i++)
                slots[i] = i < high.Count ? high[i] : Fillers[f++];
            c.PrimarySkill1 = slots[0]; c.PrimarySkill2 = slots[1]; c.PrimarySkill3 = slots[2];
            c.MajorSkill1 = slots[3]; c.MajorSkill2 = slots[4]; c.MajorSkill3 = slots[5];
            c.MinorSkill1 = slots[6]; c.MinorSkill2 = slots[7]; c.MinorSkill3 = slots[8];
            c.MinorSkill4 = slots[9]; c.MinorSkill5 = slots[10]; c.MinorSkill6 = slots[11];
            for (int i = 0; i < Seven.Length; i++)
            {
                int at = high.IndexOf(Seven[i]);
                player.Skills.SetPermanentSkillValue(Seven[i], at >= 0 ? values[at] : Untrained[i]);
            }
        }

        void Update()
        {
            if (reported || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return;
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            if (DoomerfallStartingGun.Given == 0)
            {
                Hold(GameManager.Instance.PlayerEntity);
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
