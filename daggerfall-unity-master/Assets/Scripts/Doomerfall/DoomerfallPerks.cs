// Doomerfall: tells the player when a skill earns a perk (at 25, 50, 75 and 100).
//
// Daggerfall owns skills, so it owns the perk text too. This watches permanent skill values every frame, so training,
// the level-up check, and any other source need no hooks of their own. When a skill crosses a perk threshold during
// play, Daggerfall opens its own message box once the player is back at the HUD. DoomerfallUi then asks Doom to show
// that window, and Doom pauses behind it until it is closed (DFB_KIND_UI_ASK), as for a quest message.
// Loads and new characters set a new starting point, so they never show perks the character already had.

using System;
using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallPerks : MonoBehaviour
    {
        public static readonly int[] Thresholds = { 25, 50, 75, 100 };

        // Owner decisions in work/backlog/skills-in-doom.md. Keyed by DFCareer.Skills name, so a skill this build does
        // not have (the gun skills before they are merged) is skipped. A missing entry means that perk is still open,
        // and nothing is shown for it. Built: the perk works in game (later cards set it).
        struct Perk
        {
            public string skill;
            public int level;
            public string text;
            public bool built;
            public Perk(string skill, int level, string text, bool built = false)
            {
                this.skill = skill; this.level = level; this.text = text; this.built = built;
            }
        }

        static readonly Perk[] PerkText =
        {
            new Perk("Jumping", 25, "Your jumps get a sudden boost of 25% extra height.", true),
            new Perk("Jumping", 50, "Double jump: jump once more in mid-air.", true),
            new Perk("Jumping", 75, "Falling no longer hurts you.", true),
            new Perk("Jumping", 100, "Triple jump: jump twice more in mid-air.", true),

            new Perk("Shotguns", 25, "Shotguns reload about 35% faster.", true),
            new Perk("Shotguns", 50, "Shotguns fire 50% more pellets.", true),
            new Perk("Shotguns", 75, "Shotgun blasts knock enemies back and stagger them. The more pellets hit, the harder the shove, and big enemies move less. An enemy slammed into a wall takes up to 200 extra damage.", true),
            new Perk("Shotguns", 100, "Shotguns fire twice the pellets, and the knockback and wall slam are twice as strong (up to 400 damage).", true),

            new Perk("Pistols", 25, "Pistols reload 20% faster. (Planned: fast-firing pistols will deal more damage. This part does not work yet.)", true),
            new Perk("Pistols", 50, "Overkill: when a pistol shot kills, its leftover damage carries on through the body into the next enemy behind it. Each pistol shot uses up a 100-damage bonus, added to its damage if it hits; the bonus refills every half second. Pistols reload 40% faster.", true),
            new Perk("Pistols", 75, "Pistols reload 60% faster. (Planned: Deadeye, slow-firing pistols will deal more damage. This part does not work yet.)", true),
            new Perk("Pistols", 100, "Shrapnel: every pistol hit bursts into 3 fragments that fly on behind the enemy, each doing a third of the hit's damage. A fragment swerves into an enemy close to its path.", true),

            new Perk("Automatics", 25,"Burst fire: the first 3 shots of a burst do 30% more damage. The bonus comes back 0.3 seconds after you stop firing.", true),
            new Perk("Automatics", 50, "Every second shot from an automatic weapon uses no ammo.", true),
            new Perk("Automatics", 75, "Each hit from an automatic weapon makes the enemy take 1% more damage from everything, up to 15%. It never wears off.", true),
            new Perk("Automatics", 100, "Automatic weapons use only 1 ammo for every 4 shots.", true),

            new Perk("Explosives", 25, "Your own explosions hurt you 95% less.", true),
            new Perk("Explosives", 50, "Explosives do extra damage to the enemy they hit directly."),
            new Perk("Explosives", 75, "Your own explosions hurt you 99% less.", true),
            new Perk("Explosives", 100, "Inpulsa's Broken Heart: enemies your explosives kill explode for a quarter of their maximum health. Those blasts chain, each at half the strength of the one before, and never hurt you.", true),
        };

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        readonly short[] known = new short[DaggerfallSkills.Count];
        readonly List<string> pending = new List<string>();
        bool hasBaseline;

        public void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            SaveLoadManager.OnStartLoad += OnStartLoad;
            StartGameBehaviour.OnStartGame += OnStartGame;
        }

        void OnDestroy()
        {
            SaveLoadManager.OnStartLoad -= OnStartLoad;
            StartGameBehaviour.OnStartGame -= OnStartGame;
        }

        void OnStartLoad(SaveData_v1 data) { Reset(); }
        void OnStartGame(object sender, EventArgs e) { Reset(); }

        void Reset()
        {
            hasBaseline = false;
            pending.Clear();
        }

        /// <summary>The perk text Daggerfall shows for this skill and threshold, or null when that perk is still open.</summary>
        internal static string Describe(DFCareer.Skills skill, int level)
        {
            for (int i = 0; i < PerkText.Length; i++)
            {
                if (PerkText[i].level != level || !Enum.IsDefined(typeof(DFCareer.Skills), PerkText[i].skill))
                    continue;
                if ((DFCareer.Skills)Enum.Parse(typeof(DFCareer.Skills), PerkText[i].skill) == skill)
                    return PerkText[i].built ? PerkText[i].text : PerkText[i].text + " (This perk does not work yet.)";
            }
            return null;
        }

        void Update()
        {
            PlayerEntity player = GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null;
            SaveLoadManager saves = SaveLoadManager.Instance;
            if (player == null || !sync.InGame || sync.LoadRunning || sync.Phase != Dfb.DF_PHASE_PLAY || DoomerfallNewGame.HoldsNewCharacter ||
                (saves != null && saves.LoadInProgress))
            {
                hasBaseline = false; // A perk already waiting still shows; a load or new character clears it.
                return;
            }

            for (int i = 0; i < known.Length; i++)
            {
                short now = player.Skills.GetPermanentSkillValue(i);
                if (hasBaseline && now > known[i])
                    Gained((DFCareer.Skills)i, known[i], now);
                known[i] = now;
            }
            if (!hasBaseline)
                bridge.LogLine("perks: watching skills from here");
            hasBaseline = true;

            // A window opened on top of another, such as the travel window, could be closed by that window, so wait for the HUD.
            if (pending.Count > 0 && DaggerfallUI.Instance && DaggerfallUI.UIManager.TopWindow is DaggerfallHUD)
                Show();
        }

        void Gained(DFCareer.Skills skill, int from, int to)
        {
            for (int t = 0; t < Thresholds.Length; t++)
            {
                int level = Thresholds[t];
                if (from >= level || to < level)
                    continue;
                string text = Describe(skill, level);
                string name = DaggerfallUnity.Instance.TextProvider.GetSkillName(skill);
                bridge.LogLine(string.Format("perks: {0} rose from {1} to {2}, perk at {3}: {4}", name, from, to, level, text ?? "none yet"));
                if (text != null)
                    pending.Add(string.Format("{0} {1}|{2}", name, level, text));
            }
        }

        void Show()
        {
            var tokens = new List<TextFile.Token>();
            for (int i = 0; i < pending.Count; i++)
            {
                string[] parts = pending[i].Split('|');
                if (i > 0)
                    tokens.Add(TextFile.NewLineToken);
                tokens.Add(TextFile.CreateTextToken("New perk: " + parts[0]));
                tokens.Add(TextFile.NewLineToken);
                tokens.Add(TextFile.CreateTextToken(parts[1]));
                tokens.Add(TextFile.NewLineToken);
            }
            var box = new DaggerfallMessageBox(DaggerfallUI.UIManager, null, true);
            box.SetTextTokens(tokens.ToArray(), null, false);
            box.ClickAnywhereToClose = true;
            box.Show();
            bridge.LogLine("perks: showing " + pending.Count + " perk(s)");
            pending.Clear();
        }
    }
}
