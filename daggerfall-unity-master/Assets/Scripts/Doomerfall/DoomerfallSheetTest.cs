// Doomerfall test only (-dfsheettest with -dfsynctest): changes the character through Daggerfall's own systems
// so the launch can compare what Doom read. Saves go to the portable install's private folder.

using System.Collections;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.MagicAndEffects;
using DaggerfallWorkshop.Game.Player;
using DaggerfallWorkshop.Game.Serialization;
using DaggerfallWorkshop.Game.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallSheetTest : MonoBehaviour
    {
        const float StepSeconds = 0.5f, WaitSeconds = 12f;
        const string SaveName = "SheetTest";

        DoomerfallBridge bridge;
        DoomerfallPositionSync sync;
        bool loaded;

        internal void Init(DoomerfallBridge owner, DoomerfallPositionSync positionSync)
        {
            bridge = owner;
            sync = positionSync;
            if (DaggerfallUnityApplication.IsPortableInstall)
                StartCoroutine(Run());
            else
                bridge.LogLine("error: -dfsheettest needs a portable install");
        }

        IEnumerator Step(string name)
        {
            yield return new WaitForSecondsRealtime(StepSeconds);
            bridge.LogLine("sheet test: " + name);
        }

        IEnumerator Run()
        {
            while (!sync.InGame)
                yield return null;
            yield return Step("baseline");
            PlayerEntity player = GameManager.Instance.PlayerEntity;

            player.Skills.SetPermanentSkillValue(DFCareer.Skills.Archery, (short)(player.Skills.GetPermanentSkillValue(DFCareer.Skills.Archery) + 7));
            yield return Step("training");

            player.Level++;
            player.Stats.SetPermanentStatValue(DFCareer.Stats.Strength, player.Stats.PermanentStrength + 3);
            yield return Step("level up");

            DaggerfallUnityItem helm = ItemBuilder.CreateArmor(Genders.Male, Races.Breton, Armor.Helm, ArmorMaterialTypes.Iron);
            player.Items.AddItem(helm);
            player.ItemEquipTable.EquipItem(helm, true, false);
            player.UpdateEquippedArmorValues(helm, true);
            yield return Step("equipped");

            EffectSettings settings = BaseEntityEffect.DefaultEffectSettings();
            settings.DurationBase = 120;
            settings.ChanceBase = 100;
            settings.MagnitudeBaseMin = settings.MagnitudeBaseMax = 10;
            var spell = new EffectBundleSettings
            {
                Version = EntityEffectBroker.CurrentSpellVersion,
                BundleType = BundleTypes.Spell,
                TargetType = TargetTypes.CasterOnly,
                ElementType = ElementTypes.Magic,
                Name = "Sheet test",
                Effects = new[] { new EffectEntry("Fortify-Strength", settings), new EffectEntry("ElementalResistance-Fire", settings) },
            };
            GameManager.Instance.PlayerEffectManager.AssignBundle(new EntityEffectBundle(spell, GameManager.Instance.PlayerEntityBehaviour),
                AssignBundleFlags.BypassSavingThrows | AssignBundleFlags.BypassChance);
            yield return new WaitForSecondsRealtime(1f); // Effect mods refresh on a short timer.
            yield return Step("effect");

            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            string character = player.Name;
            saves.Save(character, SaveName);
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Step("saved");

            player.Skills.SetPermanentSkillValue(DFCareer.Skills.Archery, (short)(player.Skills.GetPermanentSkillValue(DFCareer.Skills.Archery) + 20));
            yield return Step("changed after save");

            SaveLoadManager.OnLoad += OnLoaded;
            saves.EnumerateSaves();
            saves.Load(character, SaveName);
            float deadline = Time.unscaledTime + WaitSeconds;
            while (!loaded && Time.unscaledTime < deadline)
                yield return null;
            SaveLoadManager.OnLoad -= OnLoaded;
            GameManager.Instance.PauseGame(false);
            yield return new WaitForSecondsRealtime(1f);
            yield return Step(loaded ? "loaded" : "load timed out");

            var start = FindObjectOfType<StartGameBehaviour>();
            start.CharacterDocument = new CharacterDocument();
            start.StartMethod = StartGameBehaviour.StartMethods.NewCharacter;
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Step("new character");
            bridge.LogLine("sheet test: done");
        }

        void OnLoaded(SaveData_v1 data) { loaded = true; }
    }
}
