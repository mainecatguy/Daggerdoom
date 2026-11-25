// Expanded Inventory (Nexus mod 1184): the item list. Decompiled from the mod's v1 .dfmod; see
// ExpandedInventoryWindow.cs.
using System.Collections.Generic;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Utility;
using ExpandedInventoryModHook;
using UnityEngine;

namespace DaggerfallWorkshop.Game.UserInterface
{
	public class CustomItemScroller : ItemListScroller
	{
		public new delegate Color ItemBackgroundColourHandler(DaggerfallUnityItem item);

		public new delegate Texture2D[] ItemBackgroundAnimationHandler(DaggerfallUnityItem item);

		public new delegate Texture2D[] ItemForegroundAnimationHandler(DaggerfallUnityItem item);

		public new delegate string ItemLabelTextHandler(DaggerfallUnityItem item);

		public new delegate void OnItemClickHandler(DaggerfallUnityItem item);

		public new delegate void OnItemRightClickHandler(DaggerfallUnityItem item);

		public new delegate void OnItemMiddleClickHandler(DaggerfallUnityItem item);

		public new delegate void OnItemHoverHandler(DaggerfallUnityItem item);

		// Doomerfall: the mod's lists were always 3 columns (69 pixels). The column count is now per list.
		private Rect itemListPanelRect = new Rect(0f, 0f, 69f, 120f);

		private Rect[] itemButtonRects;

		private Rect upArrowRect = new Rect(232f, 43f, 9f, 15f); // In the mod's own art, before ExpandedInventoryArt moves columns.

		private Rect downArrowRect = new Rect(232f, 147f, 9f, 15f);

		private DFSize arrowsFullSize = new DFSize(320, 200);

		private Texture2D redUpArrow;

		private Texture2D greenUpArrow;

		private Texture2D redDownArrow;

		private Texture2D greenDownArrow;

		private Button itemListUpButton;

		private Button itemListDownButton;

		private VerticalScrollBar itemListScrollBar;

		private Button[] itemButtons;

		private Panel[] itemIconPanels;

		private Panel[] itemAnimPanels;

		private TextLabel[] itemStackLabels;

		private TextLabel[] itemMiscLabels;

		private Texture2D[] itemListTextures;

		private const int listDisplayUnits = 6;

		private readonly int listWidth = 3;

		private readonly int listDisplayTotal = 18;

		private const int itemButtonMargin = 1;

		private const float textScale = 0.75f;

		private bool scroller = true;

		private int miscLabelOffsetDist;

		private int miscLabelOffsetIdx;

		private float foregroundAnimationDelay = 0.2f;

		private float backgroundAnimationDelay = 0.2f;

		private List<DaggerfallUnityItem> items = new List<DaggerfallUnityItem>();

		private ToolTip toolTip;

		private ItemBackgroundColourHandler backgroundColourHandler;

		private ItemBackgroundAnimationHandler backgroundAnimationHandler;

		private ItemForegroundAnimationHandler foregroundAnimationHandler;

		private ItemLabelTextHandler labelTextHandler;

		public new ItemBackgroundColourHandler BackgroundColourHandler
		{
			get
			{
				return backgroundColourHandler;
			}
			set
			{
				backgroundColourHandler = value;
			}
		}

		public new ItemBackgroundAnimationHandler BackgroundAnimationHandler
		{
			get
			{
				return backgroundAnimationHandler;
			}
			set
			{
				backgroundAnimationHandler = value;
			}
		}

		public new float BackgroundAnimationDelay
		{
			get
			{
				return backgroundAnimationDelay;
			}
			set
			{
				backgroundAnimationDelay = value;
			}
		}

		public new ItemForegroundAnimationHandler ForegroundAnimationHandler
		{
			get
			{
				return foregroundAnimationHandler;
			}
			set
			{
				foregroundAnimationHandler = value;
			}
		}

		public new float ForegroundAnimationDelay
		{
			get
			{
				return foregroundAnimationDelay;
			}
			set
			{
				foregroundAnimationDelay = value;
			}
		}

		public new ItemLabelTextHandler LabelTextHandler
		{
			get
			{
				return labelTextHandler;
			}
			set
			{
				labelTextHandler = value;
			}
		}

		public new List<DaggerfallUnityItem> Items
		{
			get
			{
				return items;
			}
			set
			{
				items = value;
				UpdateItemsDisplay(delayScrollUp: true);
			}
		}

		public new event OnItemClickHandler OnItemClick;

		public new event OnItemRightClickHandler OnItemRightClick;

		public new event OnItemMiddleClickHandler OnItemMiddleClick;

		public new event OnItemHoverHandler OnItemHover;

		public new void ResetScroll()
		{
			if (scroller)
			{
				itemListScrollBar.Reset(6);
			}
		}

		public CustomItemScroller(float x, float y, int columns, ToolTip toolTip)
			: base(toolTip, disableEnhanced: true)
		{
			this.toolTip = toolTip;
			// Doomerfall: the mod left this panel without a size and placed its parts at window coordinates, so
			// MouseOverComponent was never true (Doomerfall's hotkeys need it). Like the stock scroller, the panel now
			// covers the list and its scroll bar, and the parts sit inside it.
			Position = new Vector2(x, y);
			Size = new Vector2(ExpandedInventoryArt.CellWidth * columns + 10f, itemListPanelRect.height);
			listWidth = columns;
			listDisplayTotal = listDisplayUnits * columns;
			itemListPanelRect.width = ExpandedInventoryArt.CellWidth * columns;
			itemButtonRects = new Rect[listDisplayTotal];
			for (int i = 0; i < listDisplayTotal; i++)
			{
				itemButtonRects[i] = new Rect(ExpandedInventoryArt.CellWidth * (i % columns), 20f * (i / columns), ExpandedInventoryArt.CellWidth, 20f);
			}
			Components.Clear();
			TextLabel miscLabelTemplate = new TextLabel
			{
				Position = Vector2.zero,
				HorizontalAlignment = HorizontalAlignment.Left,
				VerticalAlignment = VerticalAlignment.Top,
				TextScale = 0.75f
			};
			LoadTextures();
			SetupScrollBar();
			SetupScrollButtons();
			SetupItemsList(miscLabelTemplate);
		}

		private void LoadTextures()
		{
			Texture2D asset = ExpandedInventoryArt.Get("INVE00I0");
			redUpArrow = ImageReader.GetSubTexture(asset, upArrowRect, arrowsFullSize);
			redDownArrow = ImageReader.GetSubTexture(asset, downArrowRect, arrowsFullSize);
			Texture2D asset2 = ExpandedInventoryArt.Get("INVE01I0");
			greenUpArrow = ImageReader.GetSubTexture(asset2, upArrowRect, arrowsFullSize);
			greenDownArrow = ImageReader.GetSubTexture(asset2, downArrowRect, arrowsFullSize);
		}

		private void SetupScrollBar()
		{
			itemListScrollBar = new VerticalScrollBar
			{
				Position = new Vector2(itemListPanelRect.x + itemListPanelRect.width + 1f, itemListPanelRect.y + 17f),
				Size = new Vector2(9f, itemListPanelRect.height - 35f),
				DisplayUnits = 6
			};
			Components.Add(itemListScrollBar);
			itemListScrollBar.OnScroll += ItemsScrollBar_OnScroll;
		}

		private void SetupScrollButtons()
		{
			itemListUpButton = new Button
			{
				Position = new Vector2(itemListPanelRect.x + itemListPanelRect.width + 1f, itemListPanelRect.y),
				Size = new Vector2(upArrowRect.width, upArrowRect.height),
				BackgroundTexture = redUpArrow
			};
			Components.Add(itemListUpButton);
			itemListUpButton.OnMouseClick += ItemsUpButton_OnMouseClick;
			itemListDownButton = new Button
			{
				Position = new Vector2(itemListPanelRect.x + itemListPanelRect.width + 1f, itemListPanelRect.y + itemListPanelRect.height - 16f),
				Size = new Vector2(downArrowRect.width, downArrowRect.height),
				BackgroundTexture = redDownArrow
			};
			Components.Add(itemListDownButton);
			itemListDownButton.OnMouseClick += ItemsDownButton_OnMouseClick;
		}

		private void SetupItemsList(TextLabel miscLabelTemplate)
		{
			Panel panel = DaggerfallUI.AddPanel(itemListPanelRect, this);
			panel.OnMouseScrollUp += ItemsListPanel_OnMouseScrollUp;
			panel.OnMouseScrollDown += ItemsListPanel_OnMouseScrollDown;
			panel.OnMouseLeave += ItemsListPanel_OnMouseLeave;
			itemButtons = new Button[listDisplayTotal];
			itemIconPanels = new Panel[listDisplayTotal];
			itemAnimPanels = new Panel[listDisplayTotal];
			itemStackLabels = new TextLabel[listDisplayTotal];
			itemMiscLabels = new TextLabel[listDisplayTotal];
			Vector2 vector = miscLabelTemplate.Position + new Vector2(0f, miscLabelOffsetDist);
			int num = miscLabelOffsetIdx;
			for (int i = 0; i < listDisplayTotal; i++)
			{
				itemButtons[i] = DaggerfallUI.AddButton(itemButtonRects[i], panel);
				itemButtons[i].SetMargins(Margins.All, 1);
				itemButtons[i].ToolTip = toolTip;
				itemButtons[i].Tag = i;
				itemButtons[i].OnMouseClick += ItemButton_OnMouseClick;
				itemButtons[i].OnRightMouseClick += ItemButton_OnRightMouseClick;
				itemButtons[i].OnMiddleMouseClick += ItemButton_OnMiddleMouseClick;
				itemButtons[i].OnMouseEnter += ItemButton_OnMouseEnter;
				itemButtons[i].OnMouseScrollUp += ItemButton_OnMouseEnter;
				itemButtons[i].OnMouseScrollDown += ItemButton_OnMouseEnter;
				itemAnimPanels[i] = DaggerfallUI.AddPanel(itemButtonRects[i], panel);
				itemAnimPanels[i].AnimationDelayInSeconds = foregroundAnimationDelay;
				itemIconPanels[i] = DaggerfallUI.AddPanel(itemButtons[i], AutoSizeModes.ScaleToFit);
				itemIconPanels[i].HorizontalAlignment = HorizontalAlignment.Center;
				itemIconPanels[i].VerticalAlignment = VerticalAlignment.Middle;
				itemIconPanels[i].MaxAutoScale = 1f;
				itemStackLabels[i] = DaggerfallUI.AddTextLabel(DaggerfallUI.Instance.Font4, Vector2.zero, string.Empty, itemButtons[i]);
				itemStackLabels[i].HorizontalAlignment = HorizontalAlignment.Right;
				itemStackLabels[i].VerticalAlignment = VerticalAlignment.Bottom;
				itemStackLabels[i].ShadowPosition = Vector2.zero;
				itemStackLabels[i].TextScale = 0.75f;
				itemStackLabels[i].TextColor = DaggerfallUI.DaggerfallUnityDefaultToolTipTextColor;
				Vector2 vector2 = miscLabelTemplate.Position;
				if (miscLabelOffsetDist != 0 && i == num)
				{
					vector2 = vector;
					num += listWidth;
				}
				itemMiscLabels[i] = DaggerfallUI.AddTextLabel(miscLabelTemplate.Font, vector2, string.Empty, itemButtons[i]);
				itemMiscLabels[i].HorizontalAlignment = miscLabelTemplate.HorizontalAlignment;
				itemMiscLabels[i].VerticalAlignment = miscLabelTemplate.VerticalAlignment;
				itemMiscLabels[i].TextScale = miscLabelTemplate.TextScale;
			}
		}

		private void ItemsScrollBar_OnScroll()
		{
			UpdateItemsDisplay(delayScrollUp: false);
		}

		private void ItemsUpButton_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			if (scroller)
			{
				itemListScrollBar.ScrollIndex--;
				DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			}
		}

		private void ItemsDownButton_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			if (scroller)
			{
				itemListScrollBar.ScrollIndex++;
				DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			}
		}

		private void ItemsListPanel_OnMouseScrollUp(BaseScreenComponent sender)
		{
			if (scroller)
			{
				itemListScrollBar.ScrollIndex--;
			}
		}

		private void ItemsListPanel_OnMouseScrollDown(BaseScreenComponent sender)
		{
			if (scroller)
			{
				itemListScrollBar.ScrollIndex++;
			}
		}

		private void ItemsListPanel_OnMouseLeave(BaseScreenComponent sender)
		{
			UpdateItemsDisplay(delayScrollUp: false);
		}

		private void ItemButton_OnClick(BaseScreenComponent sender, Vector2 position, bool rightClick, bool middleClick = false)
		{
			int num = GetScrollIndex() * listWidth + (int)sender.Tag;
			if (num < items.Count)
			{
				DaggerfallUnityItem daggerfallUnityItem = items[num];
				if (middleClick && daggerfallUnityItem != null && OnItemMiddleClick != null)
				{
					OnItemMiddleClick(daggerfallUnityItem);
				}
				else if (rightClick && daggerfallUnityItem != null && OnItemRightClick != null)
				{
					OnItemRightClick(daggerfallUnityItem);
				}
				else if (daggerfallUnityItem != null && OnItemClick != null)
				{
					OnItemClick(daggerfallUnityItem);
				}
				ItemButton_OnMouseEnter(sender);
			}
		}

		private void ItemButton_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			ItemButton_OnClick(sender, position, rightClick: false);
		}

		private void ItemButton_OnRightMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			ItemButton_OnClick(sender, position, rightClick: true);
		}

		private void ItemButton_OnMiddleMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			ItemButton_OnClick(sender, position, rightClick: false, middleClick: true);
		}

		private void ItemButton_OnMouseEnter(BaseScreenComponent sender)
		{
			int num = GetScrollIndex() * listWidth + (int)sender.Tag;
			if (num < items.Count)
			{
				DaggerfallUnityItem daggerfallUnityItem = items[num];
				if (daggerfallUnityItem != null && OnItemHover != null)
				{
					OnItemHover(daggerfallUnityItem);
				}
			}
		}

		private void UpdateItemsDisplay(bool delayScrollUp)
		{
			ClearItemsList();
			if (items == null)
			{
				return;
			}
			int num = 0;
			if (scroller)
			{
				int num2 = (items.Count + listWidth - 1) / listWidth;
				itemListScrollBar.TotalUnits = num2;
				num = GetSafeScrollIndex(itemListScrollBar, delayScrollUp);
				UpdateListScrollerButtons(num, num2);
				num *= listWidth;
			}
			for (int i = 0; i < listDisplayTotal; i++)
			{
				if (num + i < items.Count)
				{
					DaggerfallUnityItem daggerfallUnityItem = items[num + i];
					ImageData inventoryImage = DaggerfallUnity.Instance.ItemHelper.GetInventoryImage(daggerfallUnityItem);
					if (inventoryImage.animatedTextures != null && inventoryImage.animatedTextures.Length != 0)
					{
						itemIconPanels[i].AnimatedBackgroundTextures = inventoryImage.animatedTextures;
					}
					itemIconPanels[i].BackgroundTexture = inventoryImage.texture;
					if (inventoryImage.width != 0 && inventoryImage.height != 0)
					{
						itemIconPanels[i].Size = new Vector2(inventoryImage.width, inventoryImage.height);
					}
					else
					{
						itemIconPanels[i].Size = new Vector2(inventoryImage.texture.width, inventoryImage.texture.height);
					}
					if (daggerfallUnityItem.stackCount > 1)
					{
						itemStackLabels[i].Text = daggerfallUnityItem.stackCount.ToString();
					}
					if (backgroundColourHandler != null)
					{
						itemButtons[i].BackgroundColor = backgroundColourHandler(daggerfallUnityItem);
					}
					if (backgroundAnimationHandler != null)
					{
						itemButtons[i].AnimationDelayInSeconds = backgroundAnimationDelay;
						itemButtons[i].AnimatedBackgroundTextures = backgroundAnimationHandler(daggerfallUnityItem);
					}
					if (foregroundAnimationHandler != null)
					{
						itemAnimPanels[i].AnimationDelayInSeconds = foregroundAnimationDelay;
						itemAnimPanels[i].AnimatedBackgroundTextures = foregroundAnimationHandler(daggerfallUnityItem);
					}
					if (labelTextHandler != null)
					{
						itemMiscLabels[i].Text = labelTextHandler(daggerfallUnityItem);
					}
					itemButtons[i].ToolTipText = ((daggerfallUnityItem.ItemGroup == ItemGroups.Books && !daggerfallUnityItem.IsArtifact) ? DaggerfallUnity.Instance.ItemHelper.GetBookTitle(daggerfallUnityItem.message, daggerfallUnityItem.LongName) : daggerfallUnityItem.LongName);
				}
			}
		}

		private int GetScrollIndex()
		{
			if (!scroller)
			{
				return 0;
			}
			return itemListScrollBar.ScrollIndex;
		}

		private void ClearItemsList()
		{
			for (int i = 0; i < listDisplayTotal; i++)
			{
				itemStackLabels[i].Text = string.Empty;
				itemMiscLabels[i].Text = string.Empty;
				itemButtons[i].ToolTipText = string.Empty;
				itemIconPanels[i].BackgroundTexture = null;
				itemButtons[i].BackgroundColor = Color.clear;
				itemButtons[i].AnimatedBackgroundTextures = null;
				itemIconPanels[i].AnimatedBackgroundTextures = null;
				itemAnimPanels[i].AnimatedBackgroundTextures = null;
			}
			if (scroller)
			{
				itemListUpButton.BackgroundTexture = redUpArrow;
				itemListDownButton.BackgroundTexture = redDownArrow;
			}
		}

		private int GetSafeScrollIndex(VerticalScrollBar scroller, bool delayScrollUp)
		{
			int num = scroller.ScrollIndex;
			if (num < 0)
			{
				num = 0;
			}
			if ((!delayScrollUp && num + scroller.DisplayUnits > scroller.TotalUnits) || num >= scroller.TotalUnits)
			{
				num = scroller.TotalUnits - scroller.DisplayUnits;
				if (num < 0)
				{
					num = 0;
				}
				scroller.Reset(scroller.DisplayUnits, scroller.TotalUnits, num);
			}
			return num;
		}

		private void UpdateListScrollerButtons(int index, int count)
		{
			itemListUpButton.BackgroundTexture = ((index > 0) ? greenUpArrow : redUpArrow);
			itemListDownButton.BackgroundTexture = ((index < count - 6) ? greenDownArrow : redDownArrow);
			if (count <= 6)
			{
				itemListUpButton.BackgroundTexture = redUpArrow;
				itemListDownButton.BackgroundTexture = redDownArrow;
			}
		}
	}
}
