// Doomerfall: Daggerfall's small NPC popups (merchant Talk / Sell, guild Join / Talk / Service, repair, witches' coven)
// paint some button words into their background image and draw others as text, so in Doom one menu shows two fonts:
// blocky painted words next to Daggerfall Unity's text font (owner, 2026-11-26). In a bridge session each painted word
// is covered with a plain strip of the same panel and drawn as text in Daggerfall's default font, styled like the
// popup's own service label. Text then follows any Daggerfall font replacement (StreamingAssets/Fonts or a mod's
// FONT0003-SDF), and the plain strip follows any texture pack that replaces the popup image.
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public static class DoomerfallPopupText
    {
        // GNRC01I0.IMG (merchant Talk / Sell, 130 x 42) leaves its second button row plain for the service label.
        const string PlainImage = "GNRC01I0.IMG";
        const float PlainWidth = 130, PlainHeight = 42;
        static readonly Rect PlainRow = new Rect(5, 14, 120, 7);

        // The greyed "Join Guild" GILD01I0.IMG paints for members.
        static readonly Color DimColor = new Color32(150, 150, 150, 255);

        static Texture2D plain;

        /// <summary>Covers a painted button word at rect (in parent's native pixels) and draws text in its place.</summary>
        public static void Relabel(Panel parent, Rect rect, string text, bool dim = false)
        {
            if (!DoomerfallBridge.SessionActive)
                return;
            if (plain == null)
                plain = ImageReader.GetTexture(PlainImage);
            Relabel(parent, rect, text, dim, plain, PlainRow, new Vector2(PlainWidth, PlainHeight));
        }

        /// <summary>As Relabel, covering with plainRow of source, an image whose classic size is nativeSize.</summary>
        public static void Relabel(Panel parent, Rect rect, string text, bool dim, Texture2D source, Rect plainRow, Vector2 nativeSize)
        {
            if (!DoomerfallBridge.SessionActive || parent == null || source == null)
                return;
            // Cropped rects are texture pixels from the bottom left; scale for texture packs with larger images.
            float sx = source.width / nativeSize.x, sy = source.height / nativeSize.y;
            var cover = new Panel
            {
                Position = rect.position,
                Size = rect.size,
                BackgroundTexture = source,
                BackgroundTextureLayout = BackgroundLayout.Cropped,
                BackgroundCroppedRect = new Rect(plainRow.x * sx, (nativeSize.y - plainRow.yMax) * sy,
                    plainRow.width * sx, plainRow.height * sy),
            };
            parent.Components.Add(cover);
            // As the popups' own service label: one pixel down, centred, no shadow, default font and colour.
            TextLabel label = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(0, 1), text, cover);
            label.HorizontalAlignment = HorizontalAlignment.Center;
            label.ShadowPosition = Vector2.zero;
            if (dim)
                label.TextColor = DimColor;
        }

        /// <summary>Relabels a button whose whole area holds one painted word.</summary>
        public static void Relabel(Button button, string text)
        {
            if (button != null)
                Relabel(button, new Rect(Vector2.zero, button.Size), text);
        }

        /// <summary>
        /// The guild popup (GILD00I0/GILD01I0.IMG, 130 x 51) relabels its Join Guild and Talk rows with strips of its own
        /// plain service row, so a texture pack that restyles only the guild image still matches.
        /// </summary>
        public static void RelabelGuild(Panel mainPanel, Button talkButton, Rect joinRect, Rect serviceRect, bool member)
        {
            if (!DoomerfallBridge.SessionActive || mainPanel == null)
                return;
            var size = new Vector2(130, 51);
            Relabel(mainPanel, joinRect, "Join Guild", member, mainPanel.BackgroundTexture, serviceRect, size);
            if (talkButton != null)
                Relabel(talkButton, new Rect(Vector2.zero, talkButton.Size), "Talk", false, mainPanel.BackgroundTexture, serviceRect, size);
        }
    }
}
