// Doomerfall: a new character's starting gun follows their highest gun skill, in place of Doom's starter pistol
// (owner, 2026-11-26; card startgun 01). Runs when a bridged New Game arrives (DoomerfallNewGame.OnArrived).
//
// Doom reports its starter pistol on arrival (DFB_KIND_STARTER): the loaded mods' pistol by pickup class (DRLA's
// RLPistolPickup, else stock Pistol), its weapon slot, and the start amount N of its reserve ammo. The owner's table:
//
//   Pistols    the starter pistol   N bullets         Shotguns    shotgun          N/3 shells
//   Rifles     Light Carbine        N bullets         Explosives  rocket launcher  N/5 rockets
//   Automatics chaingun             N bullets         Melee       chainsaw         no ammo
//
// DRLA's gun when DRLA is loaded, stock Doom's otherwise; the Light Carbine is the Doomerfall mod's either way. Only these
// six skills count, compared by value whether trained or not (not Hand-to-Hand, Daggerfall's weapon skills, or Energy
// Weapons, which comes later). Class skill or not makes no difference (owner, 2026-11-27): a class with none of
// the six gets its best untrained roll's gun. The starter pistol stays only when all six are 0. Ties give every tied
// gun; each ammo type comes once, the largest amount any tied gun gets, so a Pistols and Rifles tie gets N bullets, not
// 2N. The first tied gun in the table's order is drawn. Every gun goes on its weapon slot key while that key has room.
// Doom keeps only its fist; the kit is made of real Daggerfall items, and Daggerfall's ammo stacks set Doom's counters.
// A future "no guns" option would make Kit return no guns: Doom then keeps only its fist.

using System.Collections.Generic;
using System.Text;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Utility;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal static class DoomerfallStartingGun
    {
        internal struct Gun
        {
            public DFCareer.Skills skill;
            public string cls;
            public int slot, ammoType, ammo;
        }

        struct Row
        {
            public DFCareer.Skills skill;
            public string drla, stock; // null: Doom's starter pistol
            public int slot, ammoType, divisor; // divisor 0: no ammo
            public Row(DFCareer.Skills skill, string drla, string stock, int slot, int ammoType, int divisor)
            { this.skill = skill; this.drla = drla; this.stock = stock; this.slot = slot; this.ammoType = ammoType; this.divisor = divisor; }
        }

        const int Clip = 0, Shell = 1, Rocket = 2; // DoomerfallAmmo.Types
        static readonly Row[] Table =
        {
            new Row(DFCareer.Skills.Pistols, null, null, -1, -1, 1),
            new Row(DFCareer.Skills.Rifles, "DoomerfallLightCarbine", "DoomerfallLightCarbine", 4, Clip, 1),
            new Row(DFCareer.Skills.Automatics, "RLChaingunPickup", "Chaingun", 4, Clip, 1),
            new Row(DFCareer.Skills.Shotguns, "RLShotgunPickup", "Shotgun", 3, Shell, 3),
            new Row(DFCareer.Skills.Explosives, "RLRocketLauncherPickup", "RocketLauncher", 5, Rocket, 5),
            new Row(DFCareer.Skills.Melee, "RLChainsawPickup", "Chainsaw", 1, -1, 0),
        };

        // How many kits were given this session.
        internal static int Given { get; private set; }

        // The skill's Doomerfall name (the enum's ToString can give a pre-Doomerfall alias, such as Orcish for Shotguns).
        static string Name(DFCareer.Skills skill) { return DaggerfallUnity.Instance.TextProvider.GetSkillName(skill); }

        // The last DFB_KIND_STARTER.
        static string starterClass = "";
        static int starterSlot = -1, starterAmmoType = -1, starterAmmo;

        internal static void OnStarter(uint request, uint amount, string cls)
        {
            starterClass = cls ?? "";
            starterSlot = (int)(request & 0xff) == 0xff ? -1 : (int)(request & 0xff);
            starterAmmoType = (int)(request >> 8) - 1;
            starterAmmo = (int)amount;
        }

        // The kit for this character: the guns of the highest of the six skills (all of them on a tie).
        internal static List<Gun> Kit(DaggerfallSkills skills, string pistol, int pistolSlot, int pistolAmmoType, int n, out string why)
        {
            bool drla = pistol.StartsWith("RL");
            int best = 0;
            foreach (Row r in Table)
                best = System.Math.Max(best, skills.GetPermanentSkillValue(r.skill));
            List<Gun> kit = new List<Gun>();
            StringBuilder s = new StringBuilder();
            foreach (Row r in Table)
            {
                int value = skills.GetPermanentSkillValue(r.skill);
                s.AppendFormat("{0}{1} {2}", s.Length == 0 ? "" : ", ", Name(r.skill), value);
                if (best <= 0 || value != best)
                    continue;
                if (r.drla == null)
                    kit.Add(new Gun { skill = r.skill, cls = pistol, slot = pistolSlot, ammoType = pistolAmmoType, ammo = n });
                else
                    kit.Add(new Gun { skill = r.skill, cls = drla ? r.drla : r.stock, slot = r.slot, ammoType = r.divisor > 0 ? r.ammoType : -1, ammo = r.divisor > 0 ? n / r.divisor : 0 });
            }
            if (kit.Count == 0) // All six at 0: the starter pistol, as before.
                kit.Add(new Gun { skill = DFCareer.Skills.Pistols, cls = pistol, slot = pistolSlot, ammoType = pistolAmmoType, ammo = n });
            why = string.Format("{0}; highest {1}{2}", s, best, kit.Count > 1 ? " (a tie: every tied gun)" : "");
            return kit;
        }

        // A bridged New Game arrived. False when Doom sent no starter pistol: the old adoption then takes Doom's gun.
        internal static bool Give(DoomerfallHotkeys hotkeys, DoomerfallAmmo ammo, DoomerfallBridge bridge)
        {
            if (hotkeys == null || ammo == null || string.IsNullOrEmpty(starterClass))
            {
                bridge.LogLine("starting gun: Doom sent no starter pistol; Doom's own gun is adopted");
                return false;
            }
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            string why;
            List<Gun> kit = Kit(player.Skills, starterClass, starterSlot, starterAmmoType, starterAmmo, out why);
            ItemCollection items = player.Items;
            // Anything Doom's new game class already put in Daggerfall's inventory is not the player's.
            for (int i = items.Count - 1; i >= 0; i--)
            {
                DaggerfallUnityItem item = items.GetItem(i);
                if (item is DoomerfallAmmoItem || (item is DoomerfallDoomItem && ((DoomerfallDoomItem)item).IsGun))
                {
                    bridge.LogLine(string.Format("starting gun: removed Doom's new game item {0} x{1}", item.ItemName, item.stackCount));
                    items.RemoveItem(item);
                }
            }
            int[] rounds = new int[DoomerfallAmmo.Types.Length];
            List<DoomerfallDoomItem> guns = new List<DoomerfallDoomItem>();
            List<int> slots = new List<int>();
            StringBuilder s = new StringBuilder();
            foreach (Gun g in kit)
            {
                DoomerfallDoomItem gun = DoomerfallDoomItem.Create(g.cls, Dfb.DOOM_ITEM_GUN, LootSeed.Of(LootSeed.DoomStarterGun, g.cls)); // the same for every new character
                items.AddItem(gun);
                guns.Add(gun);
                slots.Add(g.slot);
                if (g.ammoType >= 0 && g.ammoType < rounds.Length)
                    rounds[g.ammoType] = System.Math.Max(rounds[g.ammoType], g.ammo);
                s.AppendFormat("{0}{1} for {2} (slot {3})", s.Length == 0 ? "" : ", ", g.cls, Name(g.skill), g.slot);
            }
            for (int t = 0; t < rounds.Length; t++)
                if (rounds[t] > 0)
                {
                    items.AddItem(new DoomerfallAmmoItem(t, DoomerfallAmmoTiers.Regular, rounds[t]));
                    s.AppendFormat(", {0} Regular {1}", rounds[t], DoomerfallAmmo.Types[t].lowerName);
                }
            bridge.LogLine(string.Format("starting gun: Doom's starter is \"{0}\" with {1} of ammo type {2}; skills {3}; gave {4}",
                starterClass, starterAmmo, starterAmmoType, why, s));
            starterClass = ""; // Used once.
            Given++;
            ammo.PreferDaggerfall();
            hotkeys.BeginStartKit(guns, slots);
            return true;
        }
    }
}
