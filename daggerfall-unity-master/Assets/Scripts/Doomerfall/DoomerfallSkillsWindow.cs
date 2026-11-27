// Doomerfall: the skill purchase menu (owner, 2026-11-26). Opens from the "Skills" button on Daggerfall's character
// sheet, and from Doom's own key (DFB_UI_SKILLS). The left list holds every playable skill and its value; the right side
// shows the chosen skill's next point price in Skill XP, the Buy button, and its perks at 25, 50, 75 and 100 in full
// (owner, 2026-11-25: perks must be visible in game, not behind a right-click). Rules: DoomerfallSkillXp.
// A level-up earned by a bought point opens Daggerfall's character sheet for it as RaiseSkills does.

using System.Collections.Generic;
using DaggerfallConnect;
using DaggerfallWorkshop.Game.Entity;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Game.UserInterfaceWindows;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    public sealed class DoomerfallSkillsWindow : DaggerfallPopupWindow
    {
        static readonly Color Back = new Color(0.05f, 0.04f, 0.03f, 0.92f), Edge = new Color(0.45f, 0.38f, 0.25f, 1f),
            ButtonBack = new Color(0.25f, 0.2f, 0.12f, 1f), ButtonOff = new Color(0.15f, 0.15f, 0.15f, 1f),
            Grey = new Color(0.6f, 0.6f, 0.6f, 1f), Gold = DaggerfallUI.DaggerfallDefaultTextColor;

        const int ListX = 6, ListY = 26, ListW = 136, ListH = 152, Rows = 19, InfoX = 160, InfoW = 154;

        readonly List<DFCareer.Skills> skills = new List<DFCareer.Skills>();
        ListBox list;
        VerticalScrollBar scroll;
        TextLabel poolLabel, nameLabel, valueLabel, priceLabel, statusLabel;
        readonly TextLabel[] perkLabels = new TextLabel[4];
        Button buyButton;

        public DoomerfallSkillsWindow(IUserInterfaceManager uiManager, IUserInterfaceWindow previous = null)
            : base(uiManager, previous)
        {
        }

        static PlayerEntity Player { get { return GameManager.Instance.PlayerEntity; } }

        /// <summary>The character sheet's "Skills" button (one line in DaggerfallCharacterSheetWindow.Setup).</summary>
        public static void AddSheetButton(IUserInterfaceWindow sheet, Panel nativePanel)
        {
            Button b = DaggerfallUI.AddButton(new Rect(92, 181, 42, 15), nativePanel);
            Style(b, "SKILLS", true);
            b.OnMouseClick += (sender, position) =>
            {
                DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
                DaggerfallUI.UIManager.PushWindow(new DoomerfallSkillsWindow(DaggerfallUI.UIManager, sheet));
            };
        }

        static void Style(Button b, string text, bool enabled)
        {
            b.BackgroundColor = enabled ? ButtonBack : ButtonOff;
            b.Outline.Enabled = true;
            b.Outline.Color = Edge;
            b.Label.Text = text;
            b.Label.TextColor = enabled ? Gold : Grey;
        }

        protected override void Setup()
        {
            AllowCancel = true;
            ParentPanel.BackgroundColor = new Color(0, 0, 0, 0.5f);
            Panel main = DaggerfallUI.AddPanel(new Rect(0, 0, 320, 200), NativePanel);
            main.BackgroundColor = Back;
            main.Outline.Enabled = true;
            main.Outline.Color = Edge;

            TextLabel title = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(0, 4), "SKILLS", main);
            title.HorizontalAlignment = HorizontalAlignment.Center;
            poolLabel = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(0, 13), "", main);
            poolLabel.HorizontalAlignment = HorizontalAlignment.Center;
            poolLabel.TextColor = Gold;

            for (int i = 0; i < (int)DFCareer.Skills.Count; i++)
                if (DoomerfallSkillXp.Buyable((DFCareer.Skills)i))
                    skills.Add((DFCareer.Skills)i);
            skills.Sort((a, b) => string.CompareOrdinal(SkillName(a), SkillName(b)));

            list = new ListBox();
            list.Position = new Vector2(ListX, ListY);
            list.Size = new Vector2(ListW, ListH);
            list.RowsDisplayed = Rows;
            list.SelectedTextColor = Gold;
            list.TextColor = Color.white;
            list.AlwaysAcceptKeyboardInput = true;
            list.OnSelectItem += Refresh;
            list.OnScroll += () => scroll.ScrollIndex = list.ScrollIndex;
            main.Components.Add(list);

            scroll = new VerticalScrollBar();
            scroll.Position = new Vector2(ListX + ListW + 2, ListY);
            scroll.Size = new Vector2(6, ListH);
            scroll.DisplayUnits = Rows;
            scroll.TotalUnits = skills.Count;
            scroll.OnScroll += () => list.ScrollIndex = scroll.ScrollIndex;
            main.Components.Add(scroll);

            nameLabel = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(InfoX, ListY), "", main);
            nameLabel.TextColor = Gold;
            valueLabel = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(InfoX, ListY + 10), "", main);
            priceLabel = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(InfoX, ListY + 19), "", main);
            buyButton = DaggerfallUI.AddButton(new Rect(InfoX, ListY + 29, 54, 12), main);
            buyButton.OnMouseClick += (sender, position) => BuyClicked();
            statusLabel = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(InfoX + 58, ListY + 31), "", main);
            statusLabel.TextColor = Grey;

            TextLabel perks = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(InfoX, ListY + 46), "PERKS", main);
            perks.TextColor = Gold;
            for (int i = 0; i < perkLabels.Length; i++)
            {
                TextLabel l = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(InfoX, ListY + 56), "", main);
                l.MaxWidth = InfoW;
                l.WrapText = true;
                l.WrapWords = true;
                perkLabels[i] = l;
            }

            TextLabel help = DaggerfallUI.AddTextLabel(DaggerfallUI.DefaultFont, new Vector2(ListX, 186), "Damage enemies to earn Skill XP: 1 per 100 damage.", main);
            help.TextColor = Grey;
            Button close = DaggerfallUI.AddButton(new Rect(270, 184, 44, 12), main);
            Style(close, "CLOSE", true);
            close.OnMouseClick += (sender, position) => CloseWindow();

            Fill(0);
        }

        static string SkillName(DFCareer.Skills s)
        {
            return DaggerfallUnity.Instance.TextProvider.GetSkillName(s);
        }

        void Fill(int select)
        {
            int top = list.ScrollIndex;
            list.ClearItems();
            foreach (DFCareer.Skills s in skills)
                list.AddItem(string.Format("{0,3}  {1}", Player.Skills.GetPermanentSkillValue(s), SkillName(s)));
            list.ScrollIndex = top;
            list.SelectIndex(Mathf.Clamp(select, 0, skills.Count - 1));
            Refresh();
        }

        void Refresh()
        {
            PlayerEntity p = Player;
            poolLabel.Text = string.Format("Skill XP: {0:N0}", p.SkillXp);
            int index = list.SelectedIndex;
            if (index < 0 || index >= skills.Count)
                return;
            DFCareer.Skills s = skills[index];
            int value = p.Skills.GetPermanentSkillValue(s);
            nameLabel.Text = SkillName(s);
            valueLabel.Text = string.Format("Skill: {0}", value);
            string capped = DoomerfallSkillXp.Capped(p, s);
            int price = DoomerfallSkillXp.Price(p, s);
            priceLabel.Text = capped ?? string.Format("Next point: {0:N0} Skill XP", price);
            bool canBuy = capped == null && p.SkillXp >= price;
            Style(buyButton, "BUY POINT", canBuy);
            statusLabel.Text = capped == null && !canBuy ? "Not enough XP" : "";

            float y = ListY + 56;
            for (int i = 0; i < perkLabels.Length; i++)
            {
                int level = DoomerfallPerks.Thresholds[i];
                string text = DoomerfallPerks.Describe(s, level) ?? "Not available yet.";
                TextLabel l = perkLabels[i];
                l.Position = new Vector2(InfoX, y);
                l.Text = string.Format("{0} {1}: {2}", value >= level ? "*" : "-", level, text);
                l.TextColor = value >= level ? Gold : Color.white;
                y += l.Size.y + 3;
            }
        }

        void BuyClicked()
        {
            int index = list.SelectedIndex;
            if (index < 0 || index >= skills.Count || !DoomerfallSkillXp.Buy(Player, skills[index]))
                return;
            DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
            Fill(index);
        }

        public override void OnPop()
        {
            base.OnPop();
            // As RaiseSkills: a level-up opens the character sheet, which runs it. The sheet itself runs it on return.
            if (Player.ReadyToLevelUp && !(PreviousWindow is DaggerfallCharacterSheetWindow))
                DaggerfallUI.PostMessage(DaggerfallUIMessages.dfuiOpenCharacterSheetWindow);
        }
    }
}
