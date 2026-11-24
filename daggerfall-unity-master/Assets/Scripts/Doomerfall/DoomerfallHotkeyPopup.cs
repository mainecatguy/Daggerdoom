// Doomerfall: the popup for one hotkey. Five gray squares: three for the plain key, one for Ctrl, one for Alt.
// Clicking a square puts the hovered item there. The small red x clears a square. A square whose consumable ran out
// shows a grey X until the player has more of it.

using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHotkeyPopup : DaggerfallPopupWindow
    {
        const float SquareSize = 28, Gap = 6, Top = 16;
        static readonly Color Gray = new Color(0.35f, 0.35f, 0.35f, 1f);

        readonly DaggerfallUnityItem item;
        readonly int key;
        readonly Panel[] squares = new Panel[DoomerfallHotkeys.Squares];
        readonly Button[] deletes = new Button[DoomerfallHotkeys.Squares];
        readonly TextLabel[] greyed = new TextLabel[DoomerfallHotkeys.Squares];
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
            return square < 3 ? k + " (" + (square + 1) + ")" : square == 3 ? "Ctrl+" + k : "Alt+" + k;
        }

        protected override void Setup()
        {
            AllowCancel = true;
            float width = DoomerfallHotkeys.Squares * SquareSize + (DoomerfallHotkeys.Squares + 1) * Gap;
            main = DaggerfallUI.AddPanel(new Rect((320 - width) / 2, 60, width, Top + SquareSize + 18), NativePanel);
            main.BackgroundColor = new Color(0f, 0f, 0f, 0.85f);
            DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(Gap, 4), "Hotkey " + key + ": " + item.ItemName, main);
            for (int q = 0; q < DoomerfallHotkeys.Squares; q++)
            {
                float x = Gap + q * (SquareSize + Gap);
                Panel square = DaggerfallUI.AddPanel(new Rect(x, Top, SquareSize, SquareSize), main);
                square.BackgroundColor = Gray;
                square.BackgroundTextureLayout = BackgroundLayout.ScaleToFit;
                square.Tag = q;
                square.OnMouseClick += Square_OnMouseClick;
                squares[q] = square;
                TextLabel grey = DaggerfallUI.AddTextLabel(DaggerfallUI.LargeFont, new Vector2(SquareSize / 2 - 5, 4), "X", square);
                grey.TextColor = new Color(0.6f, 0.6f, 0.6f, 0.9f);
                greyed[q] = grey;
                Button delete = DaggerfallUI.AddButton(new Rect(x + SquareSize - 7, Top, 7, 7), main);
                delete.BackgroundColor = new Color(0.6f, 0f, 0f, 0.9f);
                delete.Label.Text = "x";
                delete.Label.TextColor = Color.white;
                delete.Tag = q;
                delete.OnMouseClick += Delete_OnMouseClick;
                deletes[q] = delete;
                DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(x, Top + SquareSize + 3), Label(key, q), main);
            }
            ParentPanel.OnMouseClick += Parent_OnMouseClick;
            Refresh();
        }

        void Refresh()
        {
            DoomerfallHotkeys hotkeys = DoomerfallHotkeys.Instance;
            for (int q = 0; q < DoomerfallHotkeys.Squares; q++)
            {
                DoomerfallHotkeys.Square sq = hotkeys != null ? hotkeys.table[key, q] : null;
                DaggerfallUnityItem assigned = sq != null ? hotkeys.Resolve(sq) : null;
                squares[q].BackgroundTexture = assigned != null ? DaggerfallUnity.Instance.ItemHelper.GetInventoryImage(assigned).texture : null;
                greyed[q].Enabled = sq != null && assigned == null;
                deletes[q].Enabled = sq != null;
            }
        }

        public override void Update()
        {
            base.Update();
            if (DoomerfallInput.PollDown(KeyCode.Alpha0 + key))
                CloseWindow();
        }

        void Square_OnMouseClick(BaseScreenComponent sender, Vector2 position)
        {
            int q = (int)sender.Tag;
            if (deletes[q].Enabled && deletes[q].MouseOverComponent)
                return; // The red x sits on the square's corner.
            if (DoomerfallHotkeys.Instance == null)
                return;
            DoomerfallHotkeys.Instance.Assign(key, q, item);
            Refresh();
        }

        void Delete_OnMouseClick(BaseScreenComponent sender, Vector2 position)
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
