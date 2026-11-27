// Doomerfall: Daggerfall's small NPC popups (merchant Talk / Sell, guild Join / Talk / Service, repair, witches' coven)
// paint some button words into their classic background image and draw others as text, so in Doom one menu shows two
// fonts: blocky painted words next to Daggerfall Unity's text font (owner, 2026-11-26). In a bridge session, over the
// classic image only, each painted word is covered with a plain strip cut from the same image and drawn as text in
// Daggerfall's default font, styled like the popup's own service label, so it follows any Daggerfall font replacement
// (StreamingAssets/Fonts or a mod's FONT0003-SDF). When a texture pack or mod replaces the popup image, the popup is
// left exactly as Daggerfall Unity draws it, so the pack's own lettering shows.
// Words come from the Internal text collection (keys below) when a translation provides them, else English.
using System.IO;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.Utility.ModSupport;
using DaggerfallWorkshop.Utility.AssetInjection;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public static class DoomerfallPopupText
    {
        // The greyed "Join Guild" GILD01I0.IMG paints for members.
        static readonly Color DimColor = new Color32(150, 150, 150, 255);

        // Plain strips: the merchant and guild images leave their service row plain; the repair and coven images paint
        // every row, but their centred "TALK" leaves x 6-46 of its row plain, tiled three times across a 120 px row.
        static readonly Rect MerchantPlain = new Rect(5, 14, 120, 7);
        static readonly Rect GuildPlain = new Rect(5, 23, 120, 7);
        static readonly Rect RepairPlain = new Rect(6, 14, 40, 7);
        static readonly Rect CovenPlain = new Rect(6, 5, 40, 7);
        static readonly Vector2 SmallSize = new Vector2(130, 42), LargeSize = new Vector2(130, 51);

        public static void Merchant(Panel mainPanel, Button talk)
        {
            if (Classic("GNRC01I0.IMG"))
                Cover(talk, Word("popupTalk", "Talk"), false, mainPanel.BackgroundTexture, MerchantPlain, SmallSize);
        }

        public static void Guild(Panel mainPanel, Button talk, Rect joinRect, bool member)
        {
            if (!Classic(member ? "GILD01I0.IMG" : "GILD00I0.IMG"))
                return;
            Texture2D image = mainPanel.BackgroundTexture;
            Cover(mainPanel, joinRect, Word("popupJoinGuild", "Join Guild"), member, image, GuildPlain, LargeSize);
            Cover(talk, Word("popupTalk", "Talk"), false, image, GuildPlain, LargeSize);
        }

        public static void Repair(Panel mainPanel, Button repair, Button talk, Button sell)
        {
            if (!Classic("REPR01I0.IMG"))
                return;
            Texture2D image = mainPanel.BackgroundTexture;
            Cover(repair, Word("popupRepairItem", "Repair Item"), false, image, RepairPlain, LargeSize);
            Cover(talk, Word("popupTalk", "Talk"), false, image, RepairPlain, LargeSize);
            Cover(sell, TextManager.Instance.GetLocalizedText("serviceSell"), false, image, RepairPlain, LargeSize);
        }

        public static void Coven(Panel mainPanel, Button talk, Button summon, Button quest)
        {
            if (!Classic("DAED00I0.IMG"))
                return;
            Texture2D image = mainPanel.BackgroundTexture;
            Cover(talk, Word("popupTalk", "Talk"), false, image, CovenPlain, LargeSize);
            Cover(summon, TextManager.Instance.GetLocalizedText("serviceDaedraSummon"), false, image, CovenPlain, LargeSize);
            Cover(quest, TextManager.Instance.GetLocalizedText("quest"), false, image, CovenPlain, LargeSize);
        }

        /// <summary>True in a bridge session when no loose file or mod replaces the classic image.</summary>
        static bool Classic(string imageName)
        {
            if (!DoomerfallBridge.SessionActive)
                return false;
            if (!DaggerfallUnity.Settings.AssetInjection)
                return true;
            Texture2D replaced;
            return !File.Exists(Path.Combine(TextureReplacement.ImagesPath, imageName + ".png")) &&
                !(ModManager.Instance && ModManager.Instance.TryGetAsset(imageName, null, out replaced));
        }

        static string Word(string key, string english)
        {
            string text;
            return TextManager.Instance.TryGetLocalizedText(TextCollections.Internal, key, out text) && !string.IsNullOrEmpty(text)
                ? text : english;
        }

        static void Cover(Button button, string text, bool dim, Texture2D image, Rect plain, Vector2 nativeSize)
        {
            if (button != null)
                Cover(button, new Rect(Vector2.zero, button.Size), text, dim, image, plain, nativeSize);
        }

        /// <summary>Covers rect (parent's native pixels) with plain, tiled across, and draws text over it.</summary>
        static void Cover(Panel parent, Rect rect, string text, bool dim, Texture2D image, Rect plain, Vector2 nativeSize)
        {
            if (parent == null || image == null)
                return;
            var cover = new Panel { Position = rect.position, Size = rect.size };
            parent.Components.Add(cover);
            // Cropped rects are texture pixels from the bottom left, scaled in case the image is larger than classic.
            float sx = image.width / nativeSize.x, sy = image.height / nativeSize.y;
            var crop = new Rect(plain.x * sx, (nativeSize.y - plain.yMax) * sy, plain.width * sx, plain.height * sy);
            for (float x = 0; x < rect.width; x += plain.width)
            {
                float w = Mathf.Min(plain.width, rect.width - x);
                cover.Components.Add(new Panel
                {
                    Position = new Vector2(x, 0),
                    Size = new Vector2(w, rect.height),
                    BackgroundTexture = image,
                    BackgroundTextureLayout = BackgroundLayout.Cropped,
                    BackgroundCroppedRect = new Rect(crop.x, crop.y, crop.width * w / plain.width, crop.height),
                });
            }
            // As the popups' own service label: one pixel down, centred, no shadow, default font and colour.
            TextLabel label = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(0, 1), text, cover);
            label.HorizontalAlignment = HorizontalAlignment.Center;
            label.ShadowPosition = Vector2.zero;
            if (dim)
                label.TextColor = DimColor;
        }
    }
}
