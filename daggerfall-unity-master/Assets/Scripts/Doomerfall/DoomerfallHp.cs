// Doomerfall: player HP in a bridge session. Daggerfall owns the value and death. Doom sends each hit or
// heal as a numbered event; they are applied here in order, unchanged (no armor or scaling yet). Daggerfall's
// own damage changes the player directly and is simply published. Nothing runs outside a bridge session.

using DaggerfallWorkshop.Game.Entity;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHp
    {
        readonly DoomerfallBridge bridge;
        readonly DoomerfallPositionSync sync;
        readonly bool test;
        uint applied;
        bool deadLatched, wasValid;
        int lastLoggedHp = int.MinValue;
        int logged;

        public DoomerfallHp(DoomerfallBridge owner, DoomerfallPositionSync positionSync, string[] args)
        {
            bridge = owner;
            sync = positionSync;
            test = System.Array.IndexOf(args, "-dfhptest") >= 0;
        }

        static PlayerEntity Player
        {
            get { return GameManager.HasInstance ? GameManager.Instance.PlayerEntity : null; }
        }

        // Doom's event, in the order it was sent. Events after death are consumed and ignored.
        public void OnEvent(uint number, uint type, int amount)
        {
            PlayerEntity player = Player;
            if (number != applied + 1)
                bridge.LogLine(string.Format("hp: event {0} arrived after {1} (expected {2})", number, applied, applied + 1));
            applied = number;
            if (player == null || player.CurrentHealth <= 0 || amount <= 0)
                return;

            int before = player.CurrentHealth;
            // SetHealth, not DecreaseHealth: Daggerfall's shield and armor rules come later.
            if (type == Dfb.HP_HIT) player.SetHealth(before - amount);
            else if (type == Dfb.HP_HEAL) player.SetHealth(before + amount);
            if (logged++ < 600)
                bridge.LogLine(string.Format("hp: applied event {0}: {1} {2}, hp {3} -> {4} (max {5})", number,
                    type == Dfb.HP_HIT ? "hit" : "heal", amount, before, player.CurrentHealth, player.MaxHealth));
        }

        public uint Applied { get { return applied; } }

        // Test only: Doom asks for Daggerfall-side damage, standing in for a Daggerfall attacker.
        public void OnText(string text)
        {
            const string Prefix = "hptest damage ";
            PlayerEntity player = Player;
            if (!test || player == null || !text.StartsWith(Prefix))
                return;
            int amount;
            if (!int.TryParse(text.Substring(Prefix.Length), out amount))
                return;
            int before = player.CurrentHealth;
            player.DecreaseHealth(amount); // The path Daggerfall's own attackers take.
            bridge.LogLine(string.Format("hp: Daggerfall-side damage {0}, hp {1} -> {2}", amount, before, player.CurrentHealth));
        }

        // Fills the HP fields of the published state. Runs every frame.
        public void Fill(ref DfbDfState state)
        {
            PlayerEntity player = Player;
            bool inGame = sync.InGame && player != null;
            if (inGame && player.CurrentHealth <= 0) deadLatched = true;
            else if (inGame) deadLatched = false;

            uint flags = 0;
            if (inGame || (deadLatched && wasValid)) flags |= Dfb.HPF_VALID;
            if (deadLatched) flags |= Dfb.HPF_DEAD;
            wasValid = (flags & Dfb.HPF_VALID) != 0;

            state.hpAppliedEvent = applied;
            state.hpFlags = flags;
            if (player != null && inGame)
            {
                state.hpCurrent = player.CurrentHealth;
                state.hpMax = player.MaxHealth;
                if (state.hpCurrent != lastLoggedHp && logged < 600)
                {
                    lastLoggedHp = state.hpCurrent;
                    bridge.LogLine(string.Format("hp: publishing {0}/{1}, applied through {2}, dead {3}", state.hpCurrent, state.hpMax,
                        applied, deadLatched));
                }
            }
        }
    }
}
