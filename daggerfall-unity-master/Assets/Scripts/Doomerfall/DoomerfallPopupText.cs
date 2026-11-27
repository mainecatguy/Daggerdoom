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
            if (!DoomerfallBridge.SessionActive || parent == null)
                return;
            if (plain == null)
                plain = ImageReader.GetTexture(PlainImage);
            if (plain == null)
                return;
            // Cropped rects are texture pixels from the bottom left; scale for texture packs with larger images.
            float sx = plain.width / PlainWidth, sy = plain.height / PlainHeight;
            var cover = new Panel
            {
                Position = rect.position,
                Size = rect.size,
                BackgroundTexture = plain,
                BackgroundTextureLayout = BackgroundLayout.Cropped,
                BackgroundCroppedRect = new Rect(PlainRow.x * sx, (PlainHeight - PlainRow.yMax) * sy,
                    PlainRow.width * sx, PlainRow.height * sy),
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
    }
}
