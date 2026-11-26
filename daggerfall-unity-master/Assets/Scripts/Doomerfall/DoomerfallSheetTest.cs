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
        // Saves the demo copies in: written before the gun skills, and written before Rifles (Pistols era).
        static readonly string[] OldSaveNames = { "PreSkills", "PreRifles" };

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
            SaveLoadManager saves = GameManager.Instance.SaveLoadManager;
            string character = player.Name;

            // Older saves copied in by the demo must still load.
            foreach (string oldSave in OldSaveNames)
            {
                saves.EnumerateSaves();
                if (saves.FindSaveFolderByNames(character, oldSave) < 0)
                    continue;
                yield return LoadAndWait(saves, character, oldSave);
                player = GameManager.Instance.PlayerEntity;
                bridge.LogLine(string.Format("sheet test: old save {0} career {1} rifles {2}", oldSave,
                    string.Join(",", player.GetMinorSkills()), player.Skills.GetPermanentSkillValue(DFCareer.Skills.Rifles)));
                LogSheetSkills(player);
                yield return Step(loaded ? "old save loaded" : "old save load timed out");
            }

            player.Skills.SetPermanentSkillValue(DFCareer.Skills.Shotguns, (short)(player.Skills.GetPermanentSkillValue(DFCareer.Skills.Shotguns) + 5));
            player.Skills.SetPermanentSkillValue(DFCareer.Skills.Pistols, (short)(player.Skills.GetPermanentSkillValue(DFCareer.Skills.Pistols) + 9));
            player.Skills.SetPermanentSkillValue(DFCareer.Skills.Rifles, (short)(player.Skills.GetPermanentSkillValue(DFCareer.Skills.Rifles) + 11));

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

            saves.Save(character, SaveName);
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Step("saved");

            player.Skills.SetPermanentSkillValue(DFCareer.Skills.Archery, (short)(player.Skills.GetPermanentSkillValue(DFCareer.Skills.Archery) + 20));
            player.Skills.SetPermanentSkillValue(DFCareer.Skills.Explosives, (short)(player.Skills.GetPermanentSkillValue(DFCareer.Skills.Explosives) + 20));
            yield return Step("changed after save");

            yield return LoadAndWait(saves, character, SaveName);
            yield return Step(loaded ? "loaded" : "load timed out");

            var start = FindObjectOfType<StartGameBehaviour>();
            start.CharacterDocument = new CharacterDocument();
            start.StartMethod = StartGameBehaviour.StartMethods.NewCharacter;
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Step("new character");
            LogSheetSkills(GameManager.Instance.PlayerEntity);
            bridge.LogLine("sheet test: done");
        }

        // The skill names the character sheet's four skill buttons list (DaggerfallCharacterSheetWindow).
        void LogSheetSkills(PlayerEntity player)
        {
            var groups = new[] { player.GetPrimarySkills(), player.GetMajorSkills(), player.GetMinorSkills(), player.GetMiscSkills() };
            var parts = new System.Collections.Generic.List<string>();
            foreach (var group in groups)
                parts.Add(string.Join(",", group.ConvertAll(s => DaggerfallUnity.Instance.TextProvider.GetSkillName(s)).ToArray()));
            bridge.LogLine(string.Format("sheet test: sheet skills primary [{0}] major [{1}] minor [{2}] misc [{3}]",
                parts[0], parts[1], parts[2], parts[3]));
        }

        IEnumerator LoadAndWait(SaveLoadManager saves, string character, string saveName)
        {
            loaded = false;
            SaveLoadManager.OnLoad += OnLoaded;
            saves.EnumerateSaves();
            saves.Load(character, saveName);
            float deadline = Time.unscaledTime + WaitSeconds;
            while (!loaded && Time.unscaledTime < deadline)
                yield return null;
            SaveLoadManager.OnLoad -= OnLoaded;
            GameManager.Instance.PauseGame(false);
            yield return new WaitForSecondsRealtime(1f);
        }

        void OnLoaded(SaveData_v1 data) { loaded = true; }
    }
}
