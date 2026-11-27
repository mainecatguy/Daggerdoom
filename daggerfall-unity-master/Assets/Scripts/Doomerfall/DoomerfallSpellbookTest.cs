// Doomerfall test only (-dfspellbooktest <file> [nobook]): once the game runs, gives the player a spellbook (unless
// "nobook", which takes any away) with two standard spells, the cheapest caster-only spell first and the cheapest
// spell cast at range second, and fills their magicka. Logs, each time it changes, the top window, the spellbook's
// selected row and spell count, the player's magicka and HP, the ready spell and whether a cast is playing, so a test
// can follow the spellbook from Doom.
// Starts itself from the flag; no game class calls it.

using System;
using System.IO;
using System.Reflection;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Formulas;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.MagicAndEffects;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallSpellbookTest : MonoBehaviour
    {
        static readonly FieldInfo ListField = typeof(DaggerfallSpellBookWindow).GetField("spellsListBox", BindingFlags.NonPublic | BindingFlags.Instance);

        string path, last;
        DoomerfallPositionSync sync;
        float readyAt;
        bool done, noBook;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void StartIfRequested()
        {
            string[] args = Environment.GetCommandLineArgs();
            int at = Array.IndexOf(args, "-dfspellbooktest");
            if (at < 0 || at + 1 >= args.Length)
                return;
            GameObject host = new GameObject("DoomerfallSpellbookTest");
            DontDestroyOnLoad(host);
            DoomerfallSpellbookTest test = host.AddComponent<DoomerfallSpellbookTest>();
            test.path = args[at + 1];
            test.noBook = at + 2 < args.Length && args[at + 2] == "nobook";
            File.WriteAllText(test.path, "spellbook test: started\n");
        }

        void Write(string line)
        {
            File.AppendAllText(path, string.Format("{0:F2} {1}\n", Time.realtimeSinceStartup, line));
        }

        void LateUpdate()
        {
            try { Prepare(); }
            catch (Exception e) { Write("prepare error " + e.GetType().Name + " " + e.Message); done = true; }
            string line;
            try { line = Describe(); }
            catch (Exception e) { line = "error " + e.GetType().Name + " " + e.Message; }
            if (line == last)
                return;
            last = line;
            Write(line);
        }

        void Prepare()
        {
            if (done || !GameManager.HasInstance)
                return;
            if (!sync)
                sync = FindObjectOfType<DoomerfallPositionSync>();
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (!sync || !sync.InGame || GameManager.Instance.SaveLoadManager.LoadInProgress || player == null)
            {
                readyAt = 0;
                return;
            }
            if (readyAt == 0)
                readyAt = Time.realtimeSinceStartup + 1f;
            if (Time.realtimeSinceStartup < readyAt)
                return;
            done = true;

            DaggerfallUnityItem book;
            while ((book = player.Items.GetItem(ItemGroups.MiscItems, (int)MiscItems.Spellbook)) != null)
                player.Items.RemoveItem(book);
            if (noBook)
            {
                Write("prepared: no spellbook");
                return;
            }
            player.Items.AddItem(ItemBuilder.CreateItem(ItemGroups.MiscItems, (int)MiscItems.Spellbook));
            while (player.SpellbookCount() > 0)
                player.DeleteSpell(0);

            EntityEffectBroker broker = GameManager.Instance.EntityEffectBroker;
            EffectBundleSettings self = default(EffectBundleSettings), ranged = default(EffectBundleSettings);
            int selfCost = int.MaxValue, rangedCost = int.MaxValue;
            foreach (var record in broker.StandardSpells)
            {
                EffectBundleSettings settings;
                if (record.spellName.StartsWith("!") || !broker.ClassicSpellRecordDataToEffectBundleSettings(record, BundleTypes.Spell, out settings))
                    continue;
                int cost = FormulaHelper.CalculateTotalEffectCosts(settings.Effects, settings.TargetType, null, settings.MinimumCastingCost).spellPointCost;
                if (settings.TargetType == TargetTypes.CasterOnly && cost < selfCost)
                {
                    self = settings;
                    selfCost = cost;
                }
                else if (settings.TargetType == TargetTypes.SingleTargetAtRange && cost < rangedCost)
                {
                    ranged = settings;
                    rangedCost = cost;
                }
            }
            player.AddSpell(self);
            player.AddSpell(ranged);
            player.CurrentMagicka = player.MaxMagicka;
            Write(string.Format("prepared: spellbook with '{0}' (caster only, cost {1}) and '{2}' (at range, cost {3}), magicka {4}/{5}",
                self.Name, selfCost, ranged.Name, rangedCost, player.CurrentMagicka, player.MaxMagicka));
        }

        static string Describe()
        {
            if (!DaggerfallUI.Instance || !GameManager.HasInstance || GameManager.Instance.PlayerEntity == null)
                return "none";
            IUserInterfaceWindow top = DaggerfallUI.UIManager.TopWindow;
            PlayerEntity p = GameManager.Instance.PlayerEntity;
            string list = "-";
            var book = top as DaggerfallSpellBookWindow;
            if (book != null && ListField != null)
            {
                var box = ListField.GetValue(book) as ListBox;
                if (box != null)
                    list = box.SelectedIndex + "/" + box.Count;
            }
            EntityEffectManager effects = GameManager.Instance.PlayerEffectManager;
            EntityEffectBundle ready = effects ? effects.ReadySpell : null;
            return string.Format("top {0} | selected {1} spells {2} | magicka {3}/{4} hp {5}/{6} | ready {7} casting {8}",
                top == null ? "none" : top.GetType().Name, list, p.SpellbookCount(), p.CurrentMagicka, p.MaxMagicka, p.CurrentHealth, p.MaxHealth,
                ready == null ? "none" : "'" + ready.Settings.Name + "'", GameManager.Instance.PlayerSpellCasting.IsPlayingAnim);
        }
    }
}
