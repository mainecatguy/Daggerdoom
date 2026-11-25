// Expanded Inventory (Nexus mod 1184): the filter drop-down. Decompiled from the mod's v1 .dfmod; see
// ExpandedInventoryWindow.cs.
using System.Collections.Generic;
using System.Linq;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Utility;
using UnityEngine;

namespace DaggerfallWorkshop.Game.UserInterfaceWindows
{
	public class DropdownList : DaggerfallPopupWindow
	{
		private Panel messagePanel = new Panel();

		public ListBox listBox = new ListBox();

		private IEnumerable<string> options;

		private Vector2 position;

		private Vector2 size;

		public Vector2 Position
		{
			get
			{
				return position;
			}
			set
			{
				position = value;
			}
		}

		public Vector2 Size
		{
			get
			{
				return size;
			}
			set
			{
				size = value;
			}
		}

		public IEnumerable<string> Options
		{
			get
			{
				return options;
			}
			set
			{
				options = value;
			}
		}

		public DropdownList(IUserInterfaceManager uiManager, IUserInterfaceWindow previous = null)
			: base(uiManager, previous)
		{
			position = Vector2.zero;
			size = new Vector2(50f, 50f);
		}

		protected override void Setup()
		{
			if (!IsSetup)
			{
				base.Setup();
				parentPanel.OnMouseClick += ParentPanel_OnMouseClick;
				Texture2D tex;
				if (ExpandedInventoryModHook.ExpandedInventoryArt.TryGet("scroll", out tex)) // Doomerfall: was TextureReplacement "Scroll.png"
				{
					messagePanel.BackgroundTexture = null;
					messagePanel.BackgroundColor = Color.clear;
					DFSize srcSize = new DFSize(tex.width, tex.height);
					messagePanel.SetBorderTextures(ImageReader.GetSubTexture(tex, new Rect(0f, 0f, 6f, 5f), srcSize), ImageReader.GetSubTexture(tex, new Rect(6f, 0f, 77f, 5f), srcSize), ImageReader.GetSubTexture(tex, new Rect(83f, 0f, 6f, 5f), srcSize), ImageReader.GetSubTexture(tex, new Rect(0f, 5f, 6f, 82f), srcSize), ImageReader.GetSubTexture(tex, new Rect(6f, 5f, 77f, 82f), srcSize), ImageReader.GetSubTexture(tex, new Rect(83f, 5f, 6f, 82f), srcSize), ImageReader.GetSubTexture(tex, new Rect(0f, 87f, 6f, 5f), srcSize), ImageReader.GetSubTexture(tex, new Rect(6f, 87f, 77f, 5f), srcSize), ImageReader.GetSubTexture(tex, new Rect(83f, 87f, 6f, 5f), srcSize), FilterMode.Point);
				}
				else
				{
					DaggerfallUI.Instance.SetDaggerfallPopupStyle(DaggerfallUI.PopupStyle.Parchment, messagePanel);
				}
				messagePanel.SetMargins(Margins.All, 6);
				messagePanel.Position = Vector2.zero;
				messagePanel.Size = size;
				NativePanel.Components.Add(messagePanel);
				listBox.Position = Vector2.zero;
				listBox.Size = size;
				messagePanel.Components.Add(listBox);
				IsSetup = true;
			}
		}

		public void Show()
		{
			if (!IsSetup)
			{
				Setup();
			}
			UpdatePanels();
			uiManager.PushWindow(this);
		}

		public void Hide()
		{
			CloseWindow();
		}

		protected void UpdatePanels()
		{
			messagePanel.Position = Position;
			listBox.ClearItems();
			if (options != null)
			{
				listBox.AddItems(options);
			}
			listBox.RowsDisplayed = options.Count();
			listBox.Size = new Vector2(listBox.Size.x, listBox.HeightContent());
			messagePanel.Size = new Vector2(Size.x, listBox.Size.y + 10f);
		}

		private void ParentPanel_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			if (!InputManager.Instance.GetKey(InputManager.Instance.GetBinding(InputManager.Actions.SwingWeapon)) && !messagePanel.MouseOverComponent && uiManager.TopWindow == this)
			{
				CloseWindow();
			}
		}
	}
}
