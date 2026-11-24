// Doomerfall: the popup for one hotkey, drawn like Daggerfall's inventory. Five item slots: three for the plain key,
// one for Ctrl, one for Alt. Clicking a slot puts the hovered item there. The REMOVE button under a slot clears it.
// A slot whose consumable ran out shows a grey X until the player has more of it.
//
// Everything is cut at runtime from the inventory's own pictures (INVE00I0.IMG, and INVE01I0.IMG for a highlighted
// button), as DaggerfallInventoryWindow and ItemListScroller do: a stone panel with bevelled edges, the item list's
// slots, its yellow text, and its REMOVE button.

using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHotkeyPopup : DaggerfallPopupWindow
    {
        const string BaseTextureName = "INVE00I0.IMG", GoldTextureName = "INVE01I0.IMG";
        static readonly DFSize BaseSize = new DFSize(320, 200);

        // Layout in Daggerfall's native 320x200 pixels.
        const int SlotW = 50, SlotH = 38, Gap = 3, Margin = 5, TitleH = 12;
        const int SlotTop = TitleH + 3, LabelTop = SlotTop + SlotH + 2, ButtonTop = LabelTop + 8, ButtonW = 31, ButtonH = 14;
        const int Width = 2 * Margin + DoomerfallHotkeys.Squares * SlotW + (DoomerfallHotkeys.Squares - 1) * Gap;
        const int Height = ButtonTop + ButtonH + Margin;

        // Cut from INVE00I0.IMG: four slots of the player's item list and the top slot of the other list, so the slots
        // differ the way the inventory's do; plain stone from inside the paper doll's frame; the REMOVE button.
        static readonly Rect[] SlotRects =
        {
            new Rect(172, 48, SlotW, SlotH), new Rect(172, 86, SlotW, SlotH), new Rect(172, 124, SlotW, SlotH),
            new Rect(172, 162, SlotW, SlotH), new Rect(270, 48, SlotW, SlotH),
        };
        static readonly Rect StoneRect = new Rect(50, 15, 108, 180);
        static readonly Rect RemoveRect = new Rect(226, 80, ButtonW, ButtonH);

        // The inventory's edge colours, from INVE00I0.IMG.
        static readonly Color32 Outline = new Color32(46, 44, 46, 255), Light = new Color32(132, 132, 132, 255),
            Lit = new Color32(119, 119, 119, 255), Dark = new Color32(48, 48, 50, 255), Shade = new Color32(58, 58, 58, 255);

        readonly DaggerfallUnityItem item;
        readonly int key;
        readonly Button[] slots = new Button[DoomerfallHotkeys.Squares];
        readonly Panel[] icons = new Panel[DoomerfallHotkeys.Squares];
        readonly Button[] removes = new Button[DoomerfallHotkeys.Squares];
        readonly TextLabel[] greyed = new TextLabel[DoomerfallHotkeys.Squares];
        Texture2D removeNotSelected, removeSelected;
        Panel main;

        public DoomerfallHotkeyPopup(IUserInterfaceManager uiManager, IUserInterfaceWindow previous, DaggerfallUnityItem item, int key)
            : base(uiManager, previous)
        {
            this.item = item;
            this.key = key;
        }

        static string Label(int key, int square)
        {
            string k = key.ToString();
            return square < 3 ? k + " (" + (square + 1) + ")" : square == 3 ? "CTRL+" + k : "ALT+" + k;
        }

        protected override void Setup()
        {
            AllowCancel = true;
            Texture2D baseTexture = ImageReader.GetTexture(BaseTextureName);
            Texture2D goldTexture = ImageReader.GetTexture(GoldTextureName);
            removeNotSelected = ImageReader.GetSubTexture(baseTexture, RemoveRect, BaseSize);
            removeSelected = ImageReader.GetSubTexture(goldTexture, RemoveRect, BaseSize);

            main = DaggerfallUI.AddPanel(new Rect((320 - Width) / 2, 59, Width, Height), NativePanel);
            main.BackgroundTexture = Background(ImageReader.GetSubTexture(baseTexture, StoneRect, BaseSize));
            main.BackgroundTextureLayout = BackgroundLayout.StretchToFill;

            TextLabel title = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(0, 3), "HOTKEY " + key + ":  " + item.ItemName, main);
            title.HorizontalAlignment = HorizontalAlignment.Center;

            for (int q = 0; q < DoomerfallHotkeys.Squares; q++)
            {
                int x = Margin + q * (SlotW + Gap);
                Button slot = DaggerfallUI.AddButton(new Rect(x, SlotTop, SlotW, SlotH), main);
                slot.BackgroundTexture = ImageReader.GetSubTexture(baseTexture, SlotRects[q], BaseSize);
                slot.SetMargins(Margins.All, 2); // As ItemListScroller's item buttons.
                slot.Tag = q;
                slot.OnMouseClick += Slot_OnMouseClick;
                slots[q] = slot;

                Panel icon = new Panel();
                icon.AutoSize = AutoSizeModes.ScaleToFit;
                icon.MaxAutoScale = 1f;
                icon.HorizontalAlignment = HorizontalAlignment.Center;
                icon.VerticalAlignment = VerticalAlignment.Middle;
                slot.Components.Add(icon);
                icons[q] = icon;

                TextLabel grey = DaggerfallUI.AddTextLabel(DaggerfallUI.LargeFont, Vector2.zero, "X", slot);
                grey.HorizontalAlignment = HorizontalAlignment.Center;
                grey.VerticalAlignment = VerticalAlignment.Middle;
                grey.TextColor = DaggerfallUI.DaggerfallDisabledTextColor;
                grey.ShadowColor = Outline;
                greyed[q] = grey;

                Panel column = DaggerfallUI.AddPanel(new Rect(x, LabelTop, SlotW, 8), main);
                TextLabel label = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, Vector2.zero, Label(key, q), column);
                label.HorizontalAlignment = HorizontalAlignment.Center;

                Button remove = DaggerfallUI.AddButton(new Rect(x + (SlotW - ButtonW + 1) / 2, ButtonTop, ButtonW, ButtonH), main);
                remove.BackgroundTexture = removeNotSelected;
                remove.Tag = q;
                remove.OnMouseClick += Remove_OnMouseClick;
                remove.OnMouseEnter += (sender) => sender.BackgroundTexture = removeSelected;
                remove.OnMouseLeave += (sender) => sender.BackgroundTexture = removeNotSelected;
                removes[q] = remove;
            }
            ParentPanel.OnMouseClick += Parent_OnMouseClick;
            Refresh();
        }

        // The popup's stone panel, built at native size: inventory stone mirrored to fill it, a dark outline, a bevel
        // lit from the top left, and the bevelled line under the title.
        static Texture2D Background(Texture2D stone)
        {
            Color32[] src = stone.GetPixels32();
            int sw = stone.width, sh = stone.height;
            Color32[] dst = new Color32[Width * Height];
            for (int y = 0; y < Height; y++)
                for (int x = 0; x < Width; x++)
                {
                    int sx = Mirror(x * sw / (int)StoneRect.width, sw), sy = Mirror(y * sh / (int)StoneRect.height, sh);
                    Color32 c = src[(sh - 1 - sy) * sw + sx];
                    if (x == 0 || y == 0 || x == Width - 1 || y == Height - 1)
                        c = Outline;
                    else if (x == Width - 2 || y == Height - 2)
                        c = Shade;
                    else if (x == 1 || y == 1)
                        c = Light;
                    else if (y == TitleH && x > 1 && x < Width - 2)
                        c = Dark;
                    else if (y == TitleH + 1 && x > 1 && x < Width - 2)
                        c = Lit;
                    dst[(Height - 1 - y) * Width + x] = c;
                }
            Texture2D texture = new Texture2D(Width, Height, TextureFormat.ARGB32, false);
            texture.SetPixels32(dst);
            texture.Apply(false, true);
            texture.filterMode = DaggerfallUI.Instance.GlobalFilterMode;
            return texture;
        }

        static int Mirror(int i, int n)
        {
            i %= 2 * n;
            return i < n ? i : 2 * n - 1 - i;
        }

        void Refresh()
        {
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            for (int q = 0; q < DoomerfallHotkeys.Squares; q++)
            {
                DoomerfallHotkeys.Square sq = hotkeys != null ? hotkeys.table[key, q] : null;
                DaggerfallUnityItem assigned = sq != null ? hotkeys.Resolve(sq) : null;
                Panel icon = icons[q];
                if (assigned != null)
                {
                    // As DaggerfallInventoryWindow draws an accessory: the picture at its own size, shrunk only to fit.
                    ImageData image = DaggerfallUnity.Instance.ItemHelper.GetInventoryImage(assigned);
                    icon.BackgroundTexture = image.texture;
                    icon.Size = image.width != 0 && image.height != 0 ? new Vector2(image.width, image.height)
                        : new Vector2(image.texture.width, image.texture.height);
                    slots[q].ToolTipText = assigned.LongName;
                }
                else
                {
                    icon.BackgroundTexture = null;
                    slots[q].ToolTipText = string.Empty;
                }
                greyed[q].Enabled = sq != null && assigned == null;
                removes[q].Enabled = sq != null;
                if (sq == null)
                    removes[q].BackgroundTexture = removeNotSelected;
            }
        }

        public override void Update()
        {
            base.Update();
            if (DoomerfallInput.PollDown(KeyCode.Alpha0 + key))
                CloseWindow();
        }

        void Slot_OnMouseClick(BaseScreenComponent sender, Vector2 position)
        {
            if (DoomerfallHotkeys.Instance == null)
                return;
            DoomerfallHotkeys.Instance.Assign(key, (int)sender.Tag, item);
            Refresh();
        }

        void Remove_OnMouseClick(BaseScreenComponent sender, Vector2 position)
        {
            if (DoomerfallHotkeys.Instance == null)
                return;
            DoomerfallHotkeys.Instance.Clear(key, (int)sender.Tag);
            Refresh();
        }

        void Parent_OnMouseClick(BaseScreenComponent sender, Vector2 position)
        {
            if (!main.MouseOverComponent)
                CloseWindow();
        }
    }
}
