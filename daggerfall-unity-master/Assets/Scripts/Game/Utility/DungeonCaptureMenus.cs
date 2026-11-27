// Doomerfall test tool, part of DungeonCaptureTest (-dfcapture <job file>, portable installs only).
// Visual parity menu pass (tools/visual_parity/menus.py): starts the same blank character that the paired tests'
// -dfsynctest -dfinventorytest start makes, at the paired session's place and time, opens Daggerfall Unity's own
// windows one at a time and saves a picture of each over the 3D view.
// Job lines: "exterior <map pixel x> <map pixel y>", "world <x> <z>" (Daggerfall world coordinates, after the pixel),
// "yaw <degrees>", "time <classic minutes>", "testcharacter", "menu <id> <window>", where <window> is one of
// inventory, travelmap, automap, journal, rest.

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
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
        int exteriorX = 207, exteriorY = 213, worldX = -1, worldZ = -1;
        float startYaw = float.NaN;
        long classicMinutes = -1;
        bool testCharacter;
        readonly Dictionary<EventType, int> guiEvents = new Dictionary<EventType, int>();

        void ReadMenuJob(string[] p)
        {
            if (p[0] == "menu" && p.Length > 2)
                menus.Add(new MenuShot { Id = p[1], Window = p[2] });
            else if (p[0] == "exterior" && p.Length > 2)
            {
                exteriorX = int.Parse(p[1]);
                exteriorY = int.Parse(p[2]);
            }
            else if (p[0] == "world" && p.Length > 2)
            {
                worldX = int.Parse(p[1]);
                worldZ = int.Parse(p[2]);
            }
            else if (p[0] == "yaw" && p.Length > 1)
                startYaw = Number(p[1]);
            else if (p[0] == "time" && p.Length > 1)
                classicMinutes = long.Parse(p[1]);
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

        [DllImport("user32.dll")] static extern IntPtr GetActiveWindow();
        [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);

        // Diagnosis: which IMGUI events this player gets at all (Daggerfall Unity draws its windows on Repaint).
        void OnGUI()
        {
            int n;
            guiEvents.TryGetValue(Event.current.type, out n);
            guiEvents[Event.current.type] = n + 1;
        }

        string GuiEventCounts()
        {
            var s = new System.Text.StringBuilder();
            foreach (var e in guiEvents)
                s.AppendFormat(" {0}={1}", e.Key, e.Value);
            return s.Length == 0 ? " none" : s.ToString();
        }

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

        static bool HasPixels(Texture2D image)
        {
            foreach (Color32 c in image.GetPixels32())
                if (c.a != 0 || c.r != 0 || c.g != 0 || c.b != 0)
                    return true;
            return false;
        }

        // Draws the top window into a texture outside Unity's own GUI pass, for players that get no Repaint event
        // (a window nobody sees). Daggerfall Unity's drawing calls only act on a Repaint event, so one is supplied.
        Texture2D DrawTopWindowYourself(out string error)
        {
            error = null;
            var target = RenderTexture.GetTemporary(Screen.width, Screen.height, 0, RenderTextureFormat.ARGB32);
            RenderTexture old = RenderTexture.active;
            Event oldEvent = Event.current;
            Texture2D image = null;
            try
            {
                RenderTexture.active = target;
                GL.Clear(true, true, Color.clear);
                GL.PushMatrix();
                GL.LoadPixelMatrix(0, Screen.width, Screen.height, 0);
                Event.current = new Event { type = EventType.Repaint };
                if (DaggerfallUI.UIManager.TopWindow != null)
                    DaggerfallUI.UIManager.TopWindow.Draw();
                GL.PopMatrix();
                image = ReadTexture(target);
            }
            catch (Exception e)
            {
                error = e.GetType().Name + ": " + e.Message.Replace('\n', ' ');
            }
            finally
            {
                Event.current = oldEvent;
                RenderTexture.active = old;
                RenderTexture.ReleaseTemporary(target);
            }
            return image;
        }

        static void LayOver(Texture2D scene, Texture2D ui)
        {
            Color32[] w = scene.GetPixels32(), u = ui.GetPixels32();
            for (int i = 0; i < w.Length; i++) // the UI over the 3D view, by the UI's alpha
                w[i] = Color32.Lerp(w[i], new Color32(u[i].r, u[i].g, u[i].b, 255), u[i].a / 255f);
            scene.SetPixels32(w);
            scene.Apply();
        }

        static IEnumerator EndOfFrame(WaitForEndOfFrame wait, Action done)
        {
            yield return wait;
            done();
        }

        IEnumerator RunMenus()
        {
            // As the paired game's -dfsynctest start does: a window nobody sees may never get a vertical blank.
            DaggerfallUnity.Settings.VSync = false;
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;
            // The UI draws into a texture, as Doomerfall's DoomerfallUi does, and is laid over the rendered 3D frame.
            var host = new GameObject("CaptureUiTarget");
            host.transform.SetParent(DaggerfallUI.Instance.transform, false);
            uiTarget = host.AddComponent<UserInterfaceRenderTarget>();
            uiTarget.CustomWidth = Screen.width;
            uiTarget.CustomHeight = Screen.height;
            DaggerfallUI.Instance.CustomRenderTarget = uiTarget;
            // The same start as DoomerfallSyncTest.TestStart, so the character matches the paired session.
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
            if (worldX >= 0) // The paired session's exact spot inside the town.
            {
                world.TeleportToWorldCoordinates(worldX, worldZ);
                until = Time.realtimeSinceStartup + 20f;
                yield return null;
                while ((world.IsInit || world.IsRepositioningPlayer || !world.IsReady) && Time.realtimeSinceStartup < until)
                    yield return null;
            }
            if (!float.IsNaN(startYaw))
                GameManager.Instance.PlayerMouseLook.SetFacing(startYaw, 0f);
            if (classicMinutes >= 0)
                DaggerfallUnity.Instance.WorldTime.Now.FromClassicDaggerfallTime((uint)classicMinutes);
            yield return new WaitForSecondsRealtime(3f);
            results.AppendFormat("MENUSTART pixel {0} {1} location {2} screen {3}x{4} iconic {5} gui{6}\n", GameManager.Instance.PlayerGPS.CurrentMapPixel.X,
                GameManager.Instance.PlayerGPS.CurrentMapPixel.Y, GameManager.Instance.PlayerGPS.HasCurrentLocation ? GameManager.Instance.PlayerGPS.CurrentLocation.Name : "none",
                Screen.width, Screen.height, IsIconic(GetActiveWindow()), GuiEventCounts());
            File.WriteAllText(Path.Combine(outDir, "df_probes.txt"), results.ToString());

            var endOfFrame = new WaitForEndOfFrame();
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
                // After a frame's GUI pass, if the player renders frames at all (bounded: a hidden window may not).
                bool frameEnded = false;
                StartCoroutine(EndOfFrame(endOfFrame, () => frameEnded = true));
                for (float t = Time.realtimeSinceStartup + 2f; !frameEnded && Time.realtimeSinceStartup < t;)
                    yield return null;
                // The 3D view renders into a texture, because a screen grab is empty on a desktop nobody sees.
                Camera main = GameManager.Instance.MainCamera;
                var frame = new RenderTexture(Screen.width, Screen.height, 24, RenderTextureFormat.ARGB32);
                main.targetTexture = frame;
                main.Render();
                main.targetTexture = null;
                Texture2D scene = ReadTexture(frame);
                frame.Release();
                // The UI: what Daggerfall Unity's own GUI pass drew, else the top window drawn here.
                string how = "gui pass";
                string error = null;
                Texture2D ui = uiTarget.TargetTexture ? ReadTexture(uiTarget.TargetTexture) : null;
                if (ui == null || !HasPixels(ui))
                {
                    if (ui != null)
                        Destroy(ui);
                    ui = DrawTopWindowYourself(out error);
                    how = ui != null && HasPixels(ui) ? "drawn here" : "empty";
                }
                if (ui != null && ui.width == scene.width && ui.height == scene.height)
                {
                    File.WriteAllBytes(Path.Combine(outDir, shot.Id + ".dfui.png"), ui.EncodeToPNG());
                    LayOver(scene, ui);
                }
                if (ui != null)
                    Destroy(ui);
                File.WriteAllBytes(Path.Combine(outDir, shot.Id + ".df.png"), scene.EncodeToPNG());
                var top = DaggerfallUI.UIManager.TopWindow;
                results.AppendFormat("MENU {0} {1} top {2} size {3}x{4} ui {5}{6} frame_end {7} gui{8}\n", shot.Id, shot.Window, top == null ? "none" : top.GetType().Name,
                    scene.width, scene.height, how, error == null ? "" : " error " + error, frameEnded, GuiEventCounts());
                Destroy(scene);
                File.WriteAllText(Path.Combine(outDir, "df_probes.txt"), results.ToString()); // progress, if the player is ended
            }
            DaggerfallUI.Instance.PopToHUD();
            Finish("DONE", 0);
        }
    }
}
