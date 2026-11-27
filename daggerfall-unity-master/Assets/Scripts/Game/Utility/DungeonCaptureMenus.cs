// Doomerfall test tool, part of DungeonCaptureTest (-dfcapture <job file>, portable installs only).
// Visual parity menu pass (tools/visual_parity/menus.py): starts the same blank character that the paired tests'
// -dfsynctest -dfinventorytest start makes, in the same town, opens Daggerfall Unity's own windows one at a time and
// saves a screenshot of Daggerfall Unity's whole screen for each.
// Job lines: "exterior <map pixel x> <map pixel y>", "testcharacter", "menu <id> <window>", where <window> is one of
// inventory, travelmap, automap, journal, rest.

using System.Collections;
using System.Collections.Generic;
using System.IO;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game
{
    public partial class DungeonCaptureTest
    {
        struct MenuShot { public string Id, Window; }

        readonly List<MenuShot> menus = new List<MenuShot>();
        int exteriorX = 207, exteriorY = 213;
        bool testCharacter;

        void ReadMenuJob(string[] p)
        {
            if (p[0] == "menu" && p.Length > 2)
                menus.Add(new MenuShot { Id = p[1], Window = p[2] });
            else if (p[0] == "exterior" && p.Length > 2)
            {
                exteriorX = int.Parse(p[1]);
                exteriorY = int.Parse(p[2]);
            }
            else if (p[0] == "testcharacter")
                testCharacter = true;
        }

        static readonly Dictionary<string, string> MenuMessages = new Dictionary<string, string>
        {
            { "inventory", DaggerfallUIMessages.dfuiOpenInventoryWindow },
            { "travelmap", DaggerfallUIMessages.dfuiOpenTravelMapWindow },
            { "automap", DaggerfallUIMessages.dfuiOpenAutomap },
            { "journal", DaggerfallUIMessages.dfuiOpenQuestJournalWindow },
            { "rest", DaggerfallUIMessages.dfuiOpenRestWindow },
        };

        RenderTexture guiTarget, guiScreen;
        Texture2D guiImage;

        // Runs before Daggerfall Unity's OnGUI (higher depth first) and points the UI at the captured frame.
        class GuiBegin : MonoBehaviour
        {
            public DungeonCaptureTest Owner;
            void OnGUI()
            {
                GUI.depth = 100;
                if (Event.current.type != EventType.Repaint || !Owner.guiTarget || Owner.guiImage)
                    return;
                Owner.guiScreen = RenderTexture.active;
                RenderTexture.active = Owner.guiTarget;
            }
        }

        // Runs after Daggerfall Unity's OnGUI: reads the frame with the UI drawn over it.
        class GuiEnd : MonoBehaviour
        {
            public DungeonCaptureTest Owner;
            void OnGUI()
            {
                GUI.depth = -100;
                if (Event.current.type != EventType.Repaint || !Owner.guiTarget || Owner.guiImage || RenderTexture.active != Owner.guiTarget)
                    return;
                var image = new Texture2D(Owner.guiTarget.width, Owner.guiTarget.height, TextureFormat.RGB24, false);
                image.ReadPixels(new Rect(0, 0, image.width, image.height), 0, 0);
                image.Apply();
                RenderTexture.active = Owner.guiScreen;
                Owner.guiImage = image;
            }
        }

        IEnumerator RunMenus()
        {
            // Separate objects, so each hook's GUI.depth orders it against Daggerfall Unity's OnGUI.
            new GameObject("CaptureGuiBegin").AddComponent<GuiBegin>().Owner = this;
            new GameObject("CaptureGuiEnd").AddComponent<GuiEnd>().Owner = this;
            // The same start as DoomerfallSyncTest.TestStart, so the character and place match the paired session.
            GameManager.Instance.PlayerEnterExit.EnableExteriorParent();
            StreamingWorld world = GameManager.Instance.StreamingWorld;
            world.suppressWorld = false;
            world.TeleportToCoordinates(exteriorX, exteriorY);
            GameManager.Instance.PauseGame(false);
            PlayerEntity player = GameManager.Instance.PlayerEntity;
            if (testCharacter)
            {
                player.Stats.SetPermanentStatValue(DFCareer.Stats.Endurance, 50);
                player.Stats.DoomerfallEnduranceBonus = true;
                player.MaxHealth = 100;
                player.SetHealth(100, true);
                player.GoldPieces = 5000;
                if (player.SkillUses == null)
                    player.SkillUses = new short[DaggerfallSkills.Count];
                player.Career.ForbiddenProficiencies = 0;
                player.Career.ForbiddenMaterials = 0;
                player.Items.AddItem(ItemBuilder.CreateWeapon(Weapons.Longsword, WeaponMaterialTypes.Iron));
                player.Items.AddItem(ItemBuilder.CreateWeapon(Weapons.Dagger, WeaponMaterialTypes.Steel));
            }
            float until = Time.realtimeSinceStartup + 20f;
            while ((world.IsInit || world.IsRepositioningPlayer || !world.IsReady) && Time.realtimeSinceStartup < until)
                yield return null;
            yield return new WaitForSecondsRealtime(3f);
            results.AppendFormat("MENUSTART pixel {0} {1} location {2}\n", exteriorX, exteriorY,
                GameManager.Instance.PlayerGPS.HasCurrentLocation ? GameManager.Instance.PlayerGPS.CurrentLocation.Name : "none");

            foreach (MenuShot shot in menus)
            {
                string message;
                if (!MenuMessages.TryGetValue(shot.Window, out message))
                {
                    results.AppendFormat("MENU {0} {1} unknown window\n", shot.Id, shot.Window);
                    continue;
                }
                DaggerfallUI.Instance.PopToHUD();
                yield return new WaitForSecondsRealtime(0.5f);
                DaggerfallUI.PostMessage(message);
                yield return new WaitForSecondsRealtime(1.5f);
                // A screen grab is empty on a hidden desktop, so the 3D view renders into a texture and Daggerfall
                // Unity's UI then draws over it there, in its own OnGUI pass, as it would over the screen.
                Camera main = GameManager.Instance.MainCamera;
                var frame = new RenderTexture(Screen.width, Screen.height, 24, RenderTextureFormat.ARGB32);
                main.targetTexture = frame;
                main.Render();
                main.targetTexture = null;
                guiImage = null;
                guiTarget = frame;
                float limit = Time.realtimeSinceStartup + 5f;
                while (guiImage == null && Time.realtimeSinceStartup < limit)
                    yield return null;
                guiTarget = null;
                Texture2D image = guiImage ?? new Texture2D(1, 1);
                guiImage = null;
                File.WriteAllBytes(Path.Combine(outDir, shot.Id + ".df.png"), image.EncodeToPNG());
                frame.Release();
                var top = DaggerfallUI.UIManager.TopWindow;
                results.AppendFormat("MENU {0} {1} top {2} size {3}x{4}\n", shot.Id, shot.Window, top == null ? "none" : top.GetType().Name, image.width, image.height);
                Destroy(image);
            }
            DaggerfallUI.Instance.PopToHUD();
            Finish("DONE", 0);
        }
    }
}
