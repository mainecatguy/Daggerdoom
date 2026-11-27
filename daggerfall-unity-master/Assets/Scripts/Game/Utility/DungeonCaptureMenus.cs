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
using DaggerfallWorkshop.Game.UserInterface;
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

        UserInterfaceRenderTarget uiTarget;

        static Texture2D ReadTexture(RenderTexture source)
        {
            RenderTexture old = RenderTexture.active;
            RenderTexture.active = source;
            var image = new Texture2D(source.width, source.height, TextureFormat.RGBA32, false);
            image.ReadPixels(new Rect(0, 0, source.width, source.height), 0, 0);
            image.Apply();
            RenderTexture.active = old;
            return image;
        }

        IEnumerator RunMenus()
        {
            // A screen grab is empty on a hidden desktop, so the UI draws into a texture, as Doomerfall's DoomerfallUi does.
            var host = new GameObject("CaptureUiTarget");
            host.transform.SetParent(DaggerfallUI.Instance.transform, false);
            uiTarget = host.AddComponent<UserInterfaceRenderTarget>();
            uiTarget.CustomWidth = Screen.width;
            uiTarget.CustomHeight = Screen.height;
            DaggerfallUI.Instance.CustomRenderTarget = uiTarget;
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
                Texture2D scene = ReadTexture(frame);
                frame.Release();
                Texture2D ui = uiTarget.TargetTexture ? ReadTexture(uiTarget.TargetTexture) : null;
                Texture2D image = scene;
                if (ui != null && ui.width == scene.width && ui.height == scene.height)
                {
                    File.WriteAllBytes(Path.Combine(outDir, shot.Id + ".dfui.png"), ui.EncodeToPNG());
                    Color32[] w = scene.GetPixels32(), u = ui.GetPixels32();
                    for (int i = 0; i < w.Length; i++) // the UI over the 3D view, by the UI's alpha
                        w[i] = Color32.Lerp(w[i], new Color32(u[i].r, u[i].g, u[i].b, 255), u[i].a / 255f);
                    scene.SetPixels32(w);
                    scene.Apply();
                    Destroy(ui);
                }
                File.WriteAllBytes(Path.Combine(outDir, shot.Id + ".df.png"), image.EncodeToPNG());
                var top = DaggerfallUI.UIManager.TopWindow;
                results.AppendFormat("MENU {0} {1} top {2} size {3}x{4}\n", shot.Id, shot.Window, top == null ? "none" : top.GetType().Name, image.width, image.height);
                Destroy(image);
            }
            DaggerfallUI.Instance.PopToHUD();
            Finish("DONE", 0);
        }
    }
}
