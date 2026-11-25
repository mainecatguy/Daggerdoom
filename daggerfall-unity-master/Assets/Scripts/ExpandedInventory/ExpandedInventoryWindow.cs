// Expanded Inventory (Nexus mod 1184, by Alex Falconson, AlikFalcon and LechatSokolov), decompiled from its
// v1 .dfmod with ilspycmd and maintained here (owner, 2026-11-24). Doomerfall changes are marked "Doomerfall":
// the lists are 4 columns for the player and 2 for the other side (the mod had 3 and 3), the art comes from
// ExpandedInventoryArt instead of the mod bundle, and Doom guns, ammo and armor go on the Weapons and Armor tabs.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop.Game.Items;
using DaggerfallWorkshop.Game.Questing;
using DaggerfallWorkshop.Game.UserInterface;
using DaggerfallWorkshop.Utility;
using ExpandedInventoryModHook;
using UnityEngine;

namespace DaggerfallWorkshop.Game.UserInterfaceWindows
{
	public class ExpandedInventoryWindow : DaggerfallInventoryWindow
	{
		public enum LocalTabPages
		{
			All,
			Weapons,
			Armor,
			JewelleryItems,
			MagicItems,
			Ingredients,
			ReadingItems,
			ClothingAndMisc
		}

		public enum LocalWeaponMaterialTypes
		{
			EI_Group_Mat,
			EI_Mat_Iron,
			EI_Mat_Steel,
			EI_Mat_Silver,
			EI_Mat_Elven,
			EI_Mat_Dwarven,
			EI_Mat_Mithril,
			EI_Mat_Adamantium,
			EI_Mat_Ebony,
			EI_Mat_Orcish,
			EI_Mat_Daedric
		}

		public enum LocalArmorMaterialTypes
		{
			EI_Group_Mat = 0,
			EI_Mat_Leather = 1,
			EI_Mat_Chain = 256,
			EI_Mat_Iron = 512,
			EI_Mat_Steel = 513,
			EI_Mat_Silver = 514,
			EI_Mat_Elven = 515,
			EI_Mat_Dwarven = 516,
			EI_Mat_Mithril = 517,
			EI_Mat_Adamantium = 518,
			EI_Mat_Ebony = 519,
			EI_Mat_Orcish = 520,
			EI_Mat_Daedric = 521
		}

		public enum LocalJewelleryTypes
		{
			EI_Group_Type,
			EI_Jew_Amulets,
			EI_Jew_Bracelets,
			EI_Jew_Rings,
			EI_Jew_Bracers,
			EI_Jew_Marks,
			EI_Ing_Gems,
			EI_Jew_Wands
		}

		public enum IngredientTypes
		{
			EI_Group_Type,
			EI_Ing_Plant,
			EI_Ing_Creature,
			EI_Ing_Metal,
			EI_Ing_Gems,
			EI_Ing_Misc
		}

		public enum MagicItemTypes
		{
			EI_Group_Type,
			EI_Group_Weapons,
			EI_Group_Armor,
			EI_Group_Jewellery,
			EI_Group_Clothing,
			EI_Group_Potions,
			EI_Group_Soul_gems,
			EI_Group_Other
		}

		public enum ReadingTypes
		{
			EI_Group_Type,
			EI_Read_Books,
			EI_Read_Letters,
			EI_Read_Maps,
			EI_Read_Paintings,
			EI_Read_Deeds,
			EI_Read_Letters_of_credit,
			EI_Read_Potion_recipes
		}

		public enum MiscTypes
		{
			EI_Group_Type,
			EI_Group_Clothing,
			EI_Misc_Light_sources,
			EI_Misc_Transportation,
			EI_Misc_Religious,
			EI_Misc_Furniture,
			EI_Misc_Drugs,
			EI_Group_Other
		}

		protected MethodInfo DIW_PaperDoll_GetItem = typeof(DaggerfallInventoryWindow).GetMethod("PaperDoll_GetItem", BindingFlags.Instance | BindingFlags.NonPublic);

		protected Panel wagonPicturePanel;

		protected Panel remoteTargetPicture;

		protected Panel magicEyePanel;

		protected Panel magicEyelidPanel;

		private int dropIconArchive = 216;

		private int dropIconTexture = -1;

		protected int currentFilter1Value = -1;

		protected int inventoryFilter1Value = -1;

		protected const string expandedInventoryStrings = "ExpandedInventory.csv";

		protected Dictionary<string, string> stringTable;

		protected Rect weaponsRect;

		protected Rect armorRect;

		protected Rect jewelleryItemsRect;

		protected Rect readingItemsRect;

		protected Rect remoteTargetPictureRect;

		protected Rect wagonPictureRect;

		protected TextLabel goldLabel;

		protected Button weaponsButton;

		protected Button armorButton;

		protected Button jewelleryItemsButton;

		protected Button readingItemsButton;

		protected Button filter1Button;

		protected Button filter2Button;

		protected DropdownList filter1List;

		protected DropdownList filter2List;

		protected Texture2D[] weaponsSelected;

		protected Texture2D weaponsNotSelected;

		protected Texture2D[] armorSelected;

		protected Texture2D armorNotSelected;

		protected Texture2D[] jewellerySelected;

		protected Texture2D jewelleryNotSelected;

		protected new Texture2D[] ingredientsSelected;

		protected new Texture2D ingredientsNotSelected;

		protected Texture2D[] readingItemsSelected;

		protected Texture2D readingItemsNotSelected;

		protected new Texture2D[] clothingAndMiscSelected;

		protected new Texture2D clothingAndMiscNotSelected;

		protected Texture2D groundSelected;

		protected Texture2D groundNotSelected;

		protected Texture2D mEyeTexture;

		protected Texture2D magicEyeSelected;

		protected Texture2D magicEyelidSelected;

		protected Texture2D magicEyelidBlink00;

		protected Texture2D magicEyelidBlink01;

		protected Texture2D magicEyelidBlink02;

		protected Texture2D magicEyelidBlink03;

		protected Texture2D magicEyelidBlink04;

		protected Texture2D magicEyelidBlink05;

		protected Texture2D filterActive;

		protected Texture2D filterNotActive;

		protected bool usingInventory;

		protected LocalTabPages localSelectedTabPage;

		protected LocalTabPages inventorySelectedTabPage;

		protected Vector2 lastMousePosition = Vector2.zero;

		protected Vector2 relativeMousePosition;

		protected const float weaponsAnimationDelay = 0.1f;

		protected const float armorAnimationDelay = 0.1f;

		protected const float jewelleryAnimationDelay = 0.1f;

		protected const float ingredientsAnimationDelay = 0.1f;

		protected const float readingItemsAnimationDelay = 0.1f;

		protected const float clothingAndMiscAnimationDelay = 0.1f;

		public ExpandedInventoryWindow(IUserInterfaceManager uiManager, DaggerfallBaseWindow previous = null)
			: base(uiManager, previous)
		{
		}

		protected override void Setup()
		{
			if (!IsSetup)
			{
				weaponsRect = new Rect(163f, 0f, 22f, 20f);
				armorRect = new Rect(186f, 0f, 22f, 20f);
				jewelleryItemsRect = new Rect(209f, 0f, 21f, 20f);
				magicItemsRect = new Rect(231f, 0f, 22f, 20f);
				ingredientsRect = new Rect(254f, 0f, 21f, 20f);
				readingItemsRect = new Rect(276f, 0f, 22f, 20f);
				clothingAndMiscRect = new Rect(299f, 0f, 21f, 20f);
				useButtonRect = new Rect(254f, 183f, 32f, 15f);
				equipButtonRect = new Rect(254f, 165f, 32f, 15f);
				infoButtonRect = new Rect(288f, 165f, 32f, 15f);
				exitButtonRect = new Rect(288f, 183f, 32f, 15f);
				goldButtonRect = new Rect(1f, 0f, 45f, 9f);
				localTargetIconRect = new Rect(163f, 21f, 21f, 21f);
				remoteTargetIconRect = new Rect(299f, 21f, 21f, 21f);
				remoteTargetPictureRect = new Rect(1f, 1f, 19f, 19f);
				wagonButtonRect = new Rect(276f, 21f, 22f, 21f);
				wagonPictureRect = new Rect(1f, 1f, 21f, 19f);
				// Doomerfall: 4 columns on the left, the left list's scroll bar between the lists, then 2 columns.
				localItemListScrollerRect = ExpandedInventoryArt.LocalListRect;
				remoteItemListScrollerRect = ExpandedInventoryArt.RemoteListRect;
				itemInfoPanelRect = new Rect(163f, 166f, 88f, 31f);
				base.Setup();
				LocalSetup();
				IsSetup = true;
			}
		}

		protected void LocalSetup()
		{
			RemoveBaseButtons();
			SetupTargetIconPanels();
			SetupItemListScrollers();
			SetupWeightLabels();
			SetupFilterButtons();
			SetupTabPageButtons();
			CheckWagonAccess();
			FilterLocalItems();
			FilterRemoteItems();
			ParentPanel.OnMouseMove += Inventory_OnMouseMove;
			itemInfoPanelLabel.TextScale = 0.6f;
			itemInfoPanelLabel.MaxTextWidth = 86;
			itemInfoPanelLabel.ExtraLeading = 1;
		}

		public override void Update()
		{
			base.Update();
		}

		public override void Draw()
		{
			base.Draw();
			relativeMousePosition = new Vector2(Input.mousePosition.x - NativePanel.Rectangle.xMin, Input.mousePosition.y - NativePanel.Rectangle.yMin);
			relativeMousePosition.x /= NativePanel.LocalScale.x;
			relativeMousePosition.y = (NativePanel.Rectangle.yMax - NativePanel.Rectangle.yMin - relativeMousePosition.y) / NativePanel.LocalScale.y;
		}

		public override void OnPush()
		{
			usingWagon = false;
			if (remoteTargetIconLabel != null)
			{
				remoteTargetIconLabel.Text = string.Empty;
			}
			if (!IsSetup)
			{
				Setup();
			}
			base.OnPush();
			((CustomItemScroller)localItemListScroller).ResetScroll();
			((CustomItemScroller)remoteItemListScroller).ResetScroll();
			if (usingWagon)
			{
				remoteTargetIconPanel.BackgroundTexture = groundNotSelected;
			}
			else
			{
				remoteTargetIconPanel.BackgroundTexture = groundSelected;
			}
			LootTextureRead();
			usingInventory = lootTarget == null && !usingWagon;
			if (usingInventory)
			{
				currentFilter1Value = -2;
				LocalSelectTabPage(inventorySelectedTabPage);
			}
			else
			{
				LocalSelectTabPage(LocalTabPages.All);
			}
		}

		public override void OnPop()
		{
			LootTextureUpdate();
			base.OnPop();
			usingInventory = false;
		}

		protected new void SetupTargetIconPanels()
		{
			localTargetIconPanel.BackgroundTexture = DaggerfallUnity.ItemHelper.GetContainerImage(InventoryContainerImages.Backpack).texture;
			wagonButton.OnMouseClick += WagonButton_OnMouseClick;
			remoteTargetIconPanel.BackgroundTextureLayout = BackgroundLayout.StretchToFill;
			remoteTargetIconPanel.OnMouseClick += RemoteTargetIconPanel_OnMouseClick;
			remoteTargetIconPanel.OnRightMouseClick += RemoteTargetIconPanel_OnRightMouseClick;
			remoteTargetIconPanel.OnMiddleMouseClick += RemoteTargetIconPanel_OnMiddleMouseClick;
			UpdateRemoteTargetIcon();
		}

		protected void SetupWeightLabels()
		{
			localTargetIconLabel = DaggerfallUI.AddDefaultShadowedTextLabel(new Vector2(59f, 2f), NativePanel);
			localTargetIconLabel.TextColor = DaggerfallUI.DaggerfallUnityDefaultToolTipTextColor;
			remoteTargetIconLabel = DaggerfallUI.AddDefaultShadowedTextLabel(new Vector2(118f, 2f), NativePanel);
			remoteTargetIconLabel.TextColor = DaggerfallUI.DaggerfallUnityDefaultToolTipTextColor;
			UpdateLocalTargetIcon();
		}

		protected override void UpdateLocalTargetIcon()
		{
			goldLabel.Text = GameManager.Instance.PlayerEntity.GoldPieces.ToString();
			float carriedWeight = GetCarriedWeight();
			localTargetIconLabel.Text = string.Format((carriedWeight % 1f == 0f) ? "{0:F0}/{1}" : "{0:F1}/{1}", carriedWeight, PlayerEntity.MaxEncumbrance);
			if (PlayerEntity.Items.Contains(ItemGroups.Transportation, 93))
			{
				carriedWeight = PlayerEntity.WagonWeight;
				remoteTargetIconLabel.Text = string.Format((carriedWeight % 1f == 0f) ? "{0:F0}/{1}" : "{0:F1}/{1}", carriedWeight, ItemHelper.WagonKgLimit);
			}
		}

		protected override void UpdateRemoteTargetIcon()
		{
			ImageData imageData;
			if (dropIconTexture > -1)
			{
				imageData = ImageReader.GetImageData(TextureFile.IndexToFileName(dropIconArchive), DaggerfallLootDataTables.dropIconIdxs[dropIconArchive][dropIconTexture], 0, hasAlpha: true);
			}
			else if (lootTarget != null && lootTarget.TextureArchive > 0)
			{
				imageData = ImageReader.GetImageData(TextureFile.IndexToFileName(lootTarget.TextureArchive), lootTarget.TextureRecord, 0, hasAlpha: true);
			}
			else
			{
				imageData = ((remoteTargetType != RemoteTargetTypes.Loot || !(lootTarget != null)) ? DaggerfallUnity.ItemHelper.GetContainerImage(InventoryContainerImages.Ground) : DaggerfallUnity.ItemHelper.GetContainerImage(lootTarget.ContainerImage));
			}
			if (!usingWagon && remoteTargetIconPanel != null)
			{
				remoteTargetIconPanel.BackgroundTexture = groundSelected;
				wagonButton.BackgroundTexture = wagonNotSelected;
			}
			if (remoteTargetPicture != null)
			{
				remoteTargetPicture.BackgroundTexture = imageData.texture;
			}
		}

		protected override void SetupActionButtons()
		{
			base.SetupActionButtons();
			remoteTargetPicture = DaggerfallUI.AddPanel(remoteTargetPictureRect, remoteTargetIconPanel);
			remoteTargetPicture.BackgroundTextureLayout = BackgroundLayout.ScaleToFit;
			wagonPicturePanel = DaggerfallUI.AddPanel(wagonPictureRect, wagonButton);
			wagonPicturePanel.BackgroundTextureLayout = BackgroundLayout.ScaleToFit;
			wagonPicturePanel.BackgroundTexture = DaggerfallUnity.ItemHelper.GetContainerImage(InventoryContainerImages.Wagon).texture;
			goldLabel = DaggerfallUI.AddDefaultShadowedTextLabel(new Vector2(10f, 2f), goldButton);
			goldLabel.TextColor = DaggerfallUI.DaggerfallUnityDefaultToolTipTextColor;
		}

		protected override void LoadTextures()
		{
			baseTexture = ExpandedInventoryArt.Background(false);
			goldTexture = ExpandedInventoryArt.Background(true);
			mEyeTexture = ExpandedInventoryArt.Get("MAGEYE00I0");
			DFSize srcSize = new DFSize(320, 200);
			DFSize srcSize2 = new DFSize(200, 24);
			weaponsNotSelected = ImageReader.GetSubTexture(baseTexture, weaponsRect, srcSize);
			armorNotSelected = ImageReader.GetSubTexture(baseTexture, armorRect, srcSize);
			jewelleryNotSelected = ImageReader.GetSubTexture(baseTexture, jewelleryItemsRect, srcSize);
			magicItemsNotSelected = ImageReader.GetSubTexture(baseTexture, magicItemsRect, srcSize);
			ingredientsNotSelected = ImageReader.GetSubTexture(baseTexture, ingredientsRect, srcSize);
			readingItemsNotSelected = ImageReader.GetSubTexture(baseTexture, readingItemsRect, srcSize);
			clothingAndMiscNotSelected = ImageReader.GetSubTexture(baseTexture, clothingAndMiscRect, srcSize);
			// Doomerfall: the mod imported these through TextureReplacement from its bundle.
			Texture2D tex;
			if (ExpandedInventoryArt.TryGet("Weapon", out tex))
			{
				weaponsSelected = SliceAnimation(tex, new Vector2(weaponsRect.width, weaponsRect.height));
			}
			if (ExpandedInventoryArt.TryGet("Armor", out tex))
			{
				armorSelected = SliceAnimation(tex, new Vector2(armorRect.width, armorRect.height));
			}
			if (ExpandedInventoryArt.TryGet("Jewellery", out tex))
			{
				jewellerySelected = SliceAnimation(tex, new Vector2(jewelleryItemsRect.width, jewelleryItemsRect.height));
			}
			if (ExpandedInventoryArt.TryGet("Ingredients", out tex))
			{
				ingredientsSelected = SliceAnimation(tex, new Vector2(ingredientsRect.width, ingredientsRect.height));
			}
			if (ExpandedInventoryArt.TryGet("Reading", out tex))
			{
				readingItemsSelected = SliceAnimation(tex, new Vector2(readingItemsRect.width, readingItemsRect.height));
			}
			if (ExpandedInventoryArt.TryGet("Miscellaneous", out tex))
			{
				clothingAndMiscSelected = SliceAnimation(tex, new Vector2(clothingAndMiscRect.width, clothingAndMiscRect.height));
			}
			magicItemsSelected = ImageReader.GetSubTexture(mEyeTexture, new Rect(1f, 1f, 22f, 20f), srcSize2);
			magicEyeSelected = ImageReader.GetSubTexture(mEyeTexture, new Rect(188f, 8f, 5f, 5f), srcSize2);
			magicEyelidSelected = ImageReader.GetSubTexture(mEyeTexture, new Rect(162f, 1f, 22f, 20f), srcSize2);
			magicEyelidBlink00 = ImageReader.GetSubTexture(mEyeTexture, new Rect(24f, 1f, 22f, 20f), srcSize2);
			magicEyelidBlink01 = ImageReader.GetSubTexture(mEyeTexture, new Rect(47f, 1f, 22f, 20f), srcSize2);
			magicEyelidBlink02 = ImageReader.GetSubTexture(mEyeTexture, new Rect(70f, 1f, 22f, 20f), srcSize2);
			magicEyelidBlink03 = ImageReader.GetSubTexture(mEyeTexture, new Rect(93f, 1f, 22f, 20f), srcSize2);
			magicEyelidBlink04 = ImageReader.GetSubTexture(mEyeTexture, new Rect(116f, 1f, 22f, 20f), srcSize2);
			magicEyelidBlink05 = ImageReader.GetSubTexture(mEyeTexture, new Rect(139f, 1f, 22f, 20f), srcSize2);
			wagonNotSelected = ImageReader.GetSubTexture(baseTexture, wagonButtonRect, srcSize);
			groundNotSelected = ImageReader.GetSubTexture(baseTexture, remoteTargetIconRect, srcSize);
			infoNotSelected = ImageReader.GetSubTexture(baseTexture, infoButtonRect, srcSize);
			equipNotSelected = ImageReader.GetSubTexture(baseTexture, equipButtonRect, srcSize);
			useNotSelected = ImageReader.GetSubTexture(baseTexture, useButtonRect, srcSize);
			wagonSelected = ImageReader.GetSubTexture(goldTexture, wagonButtonRect, srcSize);
			groundSelected = ImageReader.GetSubTexture(goldTexture, remoteTargetIconRect, srcSize);
			infoSelected = ImageReader.GetSubTexture(goldTexture, infoButtonRect, srcSize);
			equipSelected = ImageReader.GetSubTexture(goldTexture, equipButtonRect, srcSize);
			useSelected = ImageReader.GetSubTexture(goldTexture, useButtonRect, srcSize);
			filterNotActive = ImageReader.GetSubTexture(baseTexture, new Rect(186f, 21f, 89f, 10f), srcSize);
			filterActive = ImageReader.GetSubTexture(goldTexture, new Rect(186f, 21f, 89f, 10f), srcSize);
			coinsAnimation = ImageReader.GetImageData("TEXTURE.434", 6, 0, hasAlpha: true, createTexture: false, createAllFrameTextures: true);
			magicAnimation = ImageReader.GetImageData("TEXTURE.434", 5, 0, hasAlpha: true, createTexture: false, createAllFrameTextures: true);
		}

		protected Texture2D[] SliceAnimation(Texture2D texture, Vector2 size)
		{
			DFSize srcSize = new DFSize(texture.width, texture.height);
			int num = (int)((float)texture.width / size.x);
			Texture2D[] array = new Texture2D[num];
			for (int i = 0; i < num; i++)
			{
				Texture2D subTexture = ImageReader.GetSubTexture(texture, new Rect(size.x * (float)i, 0f, size.x, size.y), srcSize);
				array[i] = subTexture;
			}
			return array;
		}

		protected virtual void RemoveBaseButtons()
		{
			FieldInfo field = typeof(BaseScreenComponent).GetField("OnMouseClick", BindingFlags.Instance | BindingFlags.NonPublic);
			if (field != null)
			{
				field.SetValue(remoteTargetIconPanel, null);
				field.SetValue(weaponsAndArmorButton, null);
				field.SetValue(magicItemsButton, null);
				field.SetValue(ingredientsButton, null);
				field.SetValue(clothingAndMiscButton, null);
				field.SetValue(removeButton, null);
				field.SetValue(wagonButton, null);
			}
			FieldInfo field2 = typeof(BaseScreenComponent).GetField("OnRightMouseClick", BindingFlags.Instance | BindingFlags.NonPublic);
			if (field2 != null)
			{
				field2.SetValue(remoteTargetIconPanel, null);
			}
			FieldInfo field3 = typeof(BaseScreenComponent).GetField("OnMiddleMouseClick", BindingFlags.Instance | BindingFlags.NonPublic);
			if (field3 != null)
			{
				field3.SetValue(remoteTargetIconPanel, null);
			}
			localTargetIconPanel.Components.Remove(localTargetIconLabel);
			remoteTargetIconPanel.Components.Remove(remoteTargetIconLabel);
			NativePanel.Components.Remove(weaponsAndArmorButton);
			weaponsAndArmorButton = null;
			NativePanel.Components.Remove(removeButton);
			removeButton = null;
			localItemListScroller.OnItemClick -= base.LocalItemListScroller_OnItemLeftClick;
			localItemListScroller.OnItemRightClick -= LocalItemListScroller_OnItemRightClick;
			localItemListScroller.OnItemMiddleClick -= base.LocalItemListScroller_OnItemMiddleClick;
			NativePanel.Components.Remove(localItemListScroller);
			localItemListScroller = null;
			remoteItemListScroller.OnItemClick -= base.RemoteItemListScroller_OnItemLeftClick;
			remoteItemListScroller.OnItemRightClick -= RemoteItemListScroller_OnItemRightClick;
			remoteItemListScroller.OnItemMiddleClick -= base.RemoteItemListScroller_OnItemMiddleClick;
			NativePanel.Components.Remove(remoteItemListScroller);
			remoteItemListScroller = null;
		}

		protected new void SetupItemListScrollers()
		{
			localItemListScroller = new CustomItemScroller(localItemListScrollerRect.x, localItemListScrollerRect.y, ExpandedInventoryArt.LocalColumns, defaultToolTip)
			{
				BackgroundColourHandler = ItemBackgroundColourHandler,
				ForegroundAnimationHandler = MagicItemForegroundAnimationHander,
				ForegroundAnimationDelay = 0.15f
			};
			NativePanel.Components.Add(localItemListScroller);
			((CustomItemScroller)localItemListScroller).OnItemClick += LocalItemListScroller_OnItemLeftClick;
			((CustomItemScroller)localItemListScroller).OnItemRightClick += LocalItemListScroller_OnItemRightClick;
			((CustomItemScroller)localItemListScroller).OnItemMiddleClick += LocalItemListScroller_OnItemMiddleClick;
			if (DaggerfallUnity.Settings.EnableInventoryInfoPanel)
			{
				((CustomItemScroller)localItemListScroller).OnItemHover += LocalItemListScroller_OnHover;
			}
			remoteItemListScroller = new CustomItemScroller(remoteItemListScrollerRect.x, remoteItemListScrollerRect.y, ExpandedInventoryArt.RemoteColumns, defaultToolTip)
			{
				BackgroundColourHandler = ItemBackgroundColourHandler,
				ForegroundAnimationHandler = MagicItemForegroundAnimationHander,
				ForegroundAnimationDelay = 0.15f
			};
			NativePanel.Components.Add(remoteItemListScroller);
			((CustomItemScroller)remoteItemListScroller).OnItemClick += RemoteItemListScroller_OnItemLeftClick;
			((CustomItemScroller)remoteItemListScroller).OnItemRightClick += RemoteItemListScroller_OnItemRightClick;
			((CustomItemScroller)remoteItemListScroller).OnItemMiddleClick += RemoteItemListScroller_OnItemMiddleClick;
			SetRemoteItemsAnimation();
			if (DaggerfallUnity.Settings.EnableInventoryInfoPanel)
			{
				((CustomItemScroller)remoteItemListScroller).OnItemHover += RemoteItemListScroller_OnHover;
			}
		}

		protected new virtual void SetupTabPageButtons()
		{
			weaponsButton = DaggerfallUI.AddButton(weaponsRect, NativePanel);
			weaponsButton.OnMouseClick += Weapons_OnMouseClick;
			weaponsButton.BackgroundTexture = weaponsNotSelected;
			weaponsButton.Hotkey = DaggerfallShortcut.GetBinding(DaggerfallShortcut.Buttons.InventoryWeapons);
			armorButton = DaggerfallUI.AddButton(armorRect, NativePanel);
			armorButton.OnMouseClick += Armor_OnMouseClick;
			armorButton.BackgroundTextureLayout = BackgroundLayout.StretchToFill;
			armorButton.BackgroundTexture = armorNotSelected;
			jewelleryItemsButton = DaggerfallUI.AddButton(jewelleryItemsRect, NativePanel);
			jewelleryItemsButton.OnMouseClick += JewelleryItems_OnMouseClick;
			jewelleryItemsButton.BackgroundTexture = jewelleryNotSelected;
			magicItemsButton.OnMouseClick += MagicItems_OnMouseClick;
			magicEyePanel = DaggerfallUI.AddPanel(new Rect(9f, 7f, 5f, 5f), magicItemsButton);
			magicEyePanel.BackgroundTextureLayout = BackgroundLayout.ScaleToFit;
			magicEyePanel.BackgroundTexture = null;
			magicEyelidPanel = DaggerfallUI.AddPanel(new Rect(0f, 0f, 22f, 20f), magicItemsButton);
			magicEyelidPanel.BackgroundTextureLayout = BackgroundLayout.StretchToFill;
			magicEyelidPanel.BackgroundTexture = null;
			ingredientsButton.OnMouseClick += Ingredients_OnMouseClick;
			readingItemsButton = DaggerfallUI.AddButton(readingItemsRect, NativePanel);
			readingItemsButton.OnMouseClick += ReadingItems_OnMouseClick;
			readingItemsButton.BackgroundTexture = readingItemsNotSelected;
			clothingAndMiscButton.OnMouseClick += ClothingAndMisc_OnMouseClick;
			clothingAndMiscButton.Hotkey = DaggerfallShortcut.GetBinding(DaggerfallShortcut.Buttons.InventoryClothing);
			clothingAndMiscButton.BackgroundTexture = clothingAndMiscNotSelected;
			LocalSelectTabPage(LocalTabPages.All);
		}

		protected void SetupFilterButtons()
		{
			filter1Button = DaggerfallUI.AddButton(new Rect(186f, 21f, 89f, 10f), NativePanel);
			filter1Button.OnMouseClick += Filter1Button_OnMouseClick;
			filter1Button.OnRightMouseClick += Filter1Button_OnRightMouseClick;
			filter1Button.Label.HorizontalAlignment = HorizontalAlignment.None;
			filter1Button.Label.Position = new Vector2(2f, filter1Button.Label.Position.y);
			filter1Button.Enabled = false;
			filter2Button = DaggerfallUI.AddButton(new Rect(186f, 32f, 89f, 10f), NativePanel);
			filter2Button.OnMouseClick += Filter2Button_OnMouseClick;
			filter2Button.OnRightMouseClick += Filter2Button_OnRightMouseClick;
			filter1List = new DropdownList(uiManager, this);
			filter1List.Position = new Vector2(filter1Button.Position.x, filter1Button.Position.y + filter1Button.Size.y);
			filter1List.Size = new Vector2(filter1Button.Size.x, 50f);
			filter1List.listBox.OnSelectItem += Filter1_OnUseSelectedItem;
			filter1List.ParentPanel.OnMouseMove += Inventory_OnMouseMove;
			stringTable = ExpandedInventoryArt.Strings(); // Doomerfall: was the mod's ExpandedInventory.csv
		}

		protected Texture2D[] MagicItemForegroundAnimationHander(DaggerfallUnityItem item)
		{
			if (!item.IsEnchanted)
			{
				return null;
			}
			return magicAnimation.animatedTextures;
		}

		protected void LocalSelectTabPage(LocalTabPages tabPage)
		{
			if (currentFilter1Value == -2)
			{
				localSelectedTabPage = tabPage;
			}
			else
			{
				localSelectedTabPage = ((localSelectedTabPage != tabPage) ? tabPage : LocalTabPages.All);
			}
			if (usingInventory)
			{
				inventorySelectedTabPage = localSelectedTabPage;
			}
			if (localSelectedTabPage == LocalTabPages.Weapons)
			{
				weaponsButton.AnimatedBackgroundTextures = weaponsSelected;
				weaponsButton.AnimationDelayInSeconds = 0.1f;
				armorButton.BackgroundTexture = null;
			}
			else
			{
				weaponsButton.BackgroundTexture = weaponsNotSelected;
				weaponsButton.AnimatedBackgroundTextures = null;
			}
			if (localSelectedTabPage == LocalTabPages.Armor)
			{
				armorButton.AnimatedBackgroundTextures = armorSelected;
				armorButton.AnimationDelayInSeconds = 0.1f;
				armorButton.BackgroundTexture = null;
			}
			else
			{
				armorButton.BackgroundTexture = armorNotSelected;
				armorButton.AnimatedBackgroundTextures = null;
			}
			if (localSelectedTabPage == LocalTabPages.JewelleryItems)
			{
				jewelleryItemsButton.AnimatedBackgroundTextures = jewellerySelected;
				jewelleryItemsButton.AnimationDelayInSeconds = 0.1f;
				jewelleryItemsButton.BackgroundTexture = null;
			}
			else
			{
				jewelleryItemsButton.BackgroundTexture = jewelleryNotSelected;
				jewelleryItemsButton.AnimatedBackgroundTextures = null;
			}
			if (localSelectedTabPage == LocalTabPages.Ingredients)
			{
				ingredientsButton.AnimatedBackgroundTextures = ingredientsSelected;
				ingredientsButton.AnimationDelayInSeconds = 0.1f;
				ingredientsButton.BackgroundTexture = null;
			}
			else
			{
				ingredientsButton.BackgroundTexture = ingredientsNotSelected;
				ingredientsButton.AnimatedBackgroundTextures = null;
			}
			if (localSelectedTabPage == LocalTabPages.ReadingItems)
			{
				readingItemsButton.AnimatedBackgroundTextures = readingItemsSelected;
				readingItemsButton.AnimationDelayInSeconds = 0.1f;
				readingItemsButton.BackgroundTexture = null;
			}
			else
			{
				readingItemsButton.BackgroundTexture = readingItemsNotSelected;
				readingItemsButton.AnimatedBackgroundTextures = null;
			}
			if (localSelectedTabPage == LocalTabPages.ClothingAndMisc)
			{
				clothingAndMiscButton.AnimatedBackgroundTextures = clothingAndMiscSelected;
				clothingAndMiscButton.AnimationDelayInSeconds = 0.1f;
				clothingAndMiscButton.BackgroundTexture = null;
			}
			else
			{
				clothingAndMiscButton.BackgroundTexture = clothingAndMiscNotSelected;
				clothingAndMiscButton.AnimatedBackgroundTextures = null;
			}
			magicItemsButton.BackgroundTexture = ((localSelectedTabPage == LocalTabPages.MagicItems) ? magicItemsSelected : magicItemsNotSelected);
			if (localSelectedTabPage == LocalTabPages.MagicItems)
			{
				magicEyePanel.BackgroundTexture = magicEyeSelected;
				magicEyelidPanel.BackgroundTexture = magicEyelidBlink00;
			}
			else
			{
				magicEyePanel.BackgroundTexture = null;
				magicEyelidPanel.BackgroundTexture = null;
			}
			if (currentFilter1Value == -2 && inventorySelectedTabPage != LocalTabPages.All)
			{
				ClearFilter1();
				filter1List.Options = FilterOptions();
				Filter1_SetupAndShow(inventoryFilter1Value);
				Refresh(refreshPaperDoll: false);
			}
			else
			{
				ClearFilter1();
			}
			if (itemInfoPanelLabel != null)
			{
				itemInfoPanelLabel.SetText(new TextFile.Token[0]);
			}
			if (localItemListScroller != null && remoteItemListScroller != null)
			{
				((CustomItemScroller)localItemListScroller).ResetScroll();
				((CustomItemScroller)remoteItemListScroller).ResetScroll();
				FilterLocalItems();
				FilterRemoteItems();
			}
		}

		protected override void SelectActionMode(ActionModes mode)
		{
			selectedActionMode = mode;
			infoButton.BackgroundTexture = infoNotSelected;
			equipButton.BackgroundTexture = equipNotSelected;
			useButton.BackgroundTexture = useNotSelected;
			switch (mode)
			{
			case ActionModes.Info:
				infoButton.BackgroundTexture = infoSelected;
				break;
			case ActionModes.Equip:
				equipButton.BackgroundTexture = equipSelected;
				break;
			case ActionModes.Use:
				useButton.BackgroundTexture = useSelected;
				break;
			case ActionModes.Remove:
				selectedActionMode = ActionModes.Equip;
				equipButton.BackgroundTexture = equipSelected;
				break;
			}
		}

		protected override void FilterLocalItems()
		{
			localItemsFiltered.Clear();
			if (localItems == null)
			{
				return;
			}
			int count = localItems.Count;
			if (count == 0)
			{
				((CustomItemScroller)localItemListScroller).Items = localItemsFiltered;
				return;
			}
			for (int i = 0; i < count; i++)
			{
				DaggerfallUnityItem item = localItems.GetItem(i);
				if (item != null && !item.IsEquipped && IsItemFiltered(item))
				{
					localItemsFiltered.Add(item);
				}
			}
			((CustomItemScroller)localItemListScroller).Items = localItemsFiltered;
		}

		protected override void FilterRemoteItems()
		{
			remoteItemsFiltered.Clear();
			if (remoteItems == null)
			{
				return;
			}
			int count = remoteItems.Count;
			if (count == 0)
			{
				if (remoteItemListScroller is CustomItemScroller customItemScroller)
				{
					customItemScroller.Items = remoteItemsFiltered;
				}
				return;
			}
			for (int i = 0; i < count; i++)
			{
				DaggerfallUnityItem item = remoteItems.GetItem(i);
				if (item != null && IsItemFiltered(item))
				{
					remoteItemsFiltered.Add(item);
				}
			}
			if (remoteItemListScroller is CustomItemScroller customItemScroller2)
			{
				customItemScroller2.Items = remoteItemsFiltered;
			}
		}

		protected bool IsItemFiltered(DaggerfallUnityItem item)
		{
			if (!ItemMatchesTab(item))
			{
				return false;
			}
			if (currentFilter1Value == -1)
			{
				return true;
			}
			switch (localSelectedTabPage)
			{
			case LocalTabPages.Weapons:
				return WeaponMaterialFilter(item);
			case LocalTabPages.Armor:
				return ArmorMaterialFilter(item);
			case LocalTabPages.JewelleryItems:
				return JewelleryItemFilter(item);
			case LocalTabPages.Ingredients:
				return IngredientItemFilter(item);
			case LocalTabPages.MagicItems:
				return MagicItemFilter(item);
			case LocalTabPages.ReadingItems:
				return ReadingItemFilter(item);
			case LocalTabPages.ClothingAndMisc:
				return MiscItemFilter(item);
			default:
				return true;
			}
		}

		protected bool ItemMatchesTab(DaggerfallUnityItem item)
		{
			bool flag = item.IsEnchanted || item.IsOfTemplate(132) || item.IsPotion || item.IsOfTemplate(ItemGroups.MiscItems, 274);
			bool flag2 = item.ItemGroup == ItemGroups.Books || item.ItemGroup == ItemGroups.Maps || item.ItemGroup == ItemGroups.Paintings || item.IsParchment || item.ItemGroup == ItemGroups.Deeds || item.IsOfTemplate(285) || item.IsOfTemplate(286) || item.IsOfTemplate(275) || item.IsPotionRecipe;
			// Doomerfall: Doom guns and ammo with the weapons (as Daggerfall lists arrows), Doom armor with the armor.
			bool doomWeapon, doomArmor;
			ExpandedInventoryDoom.Tab(item, out doomWeapon, out doomArmor);
			if (doomWeapon || doomArmor)
			{
				return localSelectedTabPage == LocalTabPages.All || (doomWeapon ? localSelectedTabPage == LocalTabPages.Weapons : localSelectedTabPage == LocalTabPages.Armor);
			}
			switch (localSelectedTabPage)
			{
			case LocalTabPages.Weapons:
				return item.ItemGroup == ItemGroups.Weapons;
			case LocalTabPages.Armor:
				return item.ItemGroup == ItemGroups.Armor;
			case LocalTabPages.JewelleryItems:
				if (item.ItemGroup != ItemGroups.Jewellery)
				{
					return item.ItemGroup == ItemGroups.Gems;
				}
				return true;
			case LocalTabPages.MagicItems:
				return flag;
			case LocalTabPages.Ingredients:
				return item.IsIngredient;
			case LocalTabPages.ReadingItems:
				return flag2;
			case LocalTabPages.ClothingAndMisc:
				if (item.ItemGroup != ItemGroups.Weapons && item.ItemGroup != ItemGroups.Armor && item.ItemGroup != ItemGroups.Jewellery && item.ItemGroup != ItemGroups.Gems && !flag && !item.IsIngredient)
				{
					return !flag2;
				}
				return false;
			default:
				return true;
			}
		}

		protected bool WeaponMaterialFilter(DaggerfallUnityItem item)
		{
			if (currentFilter1Value == 0)
			{
				return true;
			}
			return item.NativeMaterialValue == ((int[])Enum.GetValues(typeof(LocalWeaponMaterialTypes)))[currentFilter1Value] - 1;
		}

		protected bool ArmorMaterialFilter(DaggerfallUnityItem item)
		{
			switch (currentFilter1Value)
			{
			case 1:
				return (item.NativeMaterialValue & 0xF00) == 0;
			case 256:
				return (item.NativeMaterialValue & 0xF00) == 256;
			case 0:
				return true;
			default:
				return item.NativeMaterialValue == ((int[])Enum.GetValues(typeof(LocalArmorMaterialTypes)))[currentFilter1Value];
			}
		}

		protected bool JewelleryItemFilter(DaggerfallUnityItem item)
		{
			switch (currentFilter1Value)
			{
			case 1:
				if (!item.IsOfTemplate(ItemGroups.Jewellery, 133) && !item.IsOfTemplate(ItemGroups.Jewellery, 139))
				{
					return item.IsOfTemplate(ItemGroups.Jewellery, 138);
				}
				return true;
			case 4:
				return item.IsOfTemplate(ItemGroups.Jewellery, 134);
			case 3:
				return item.IsOfTemplate(ItemGroups.Jewellery, 135);
			case 2:
				return item.IsOfTemplate(ItemGroups.Jewellery, 136);
			case 5:
				return item.IsOfTemplate(ItemGroups.Jewellery, 137);
			case 6:
				return item.ItemGroup == ItemGroups.Gems;
			case 7:
				return item.IsOfTemplate(ItemGroups.Jewellery, 140);
			default:
				return true;
			}
		}

		protected bool MagicItemFilter(DaggerfallUnityItem item)
		{
			switch (currentFilter1Value)
			{
			case 1:
				return item.ItemGroup == ItemGroups.Weapons;
			case 2:
				return item.ItemGroup == ItemGroups.Armor;
			case 3:
				if (item.ItemGroup != ItemGroups.Jewellery)
				{
					return item.ItemGroup == ItemGroups.Gems;
				}
				return true;
			case 4:
				return item.IsClothing;
			case 5:
				return item.IsPotion;
			case 6:
				return item.IsOfTemplate(ItemGroups.MiscItems, 274);
			case 7:
				if (item.ItemGroup != ItemGroups.Weapons && item.ItemGroup != ItemGroups.Armor && item.ItemGroup != ItemGroups.Jewellery && item.ItemGroup != ItemGroups.Gems && !item.IsClothing)
				{
					return !item.IsPotion;
				}
				return false;
			default:
				return true;
			}
		}

		protected bool IngredientItemFilter(DaggerfallUnityItem item)
		{
			switch (currentFilter1Value)
			{
			case 1:
				if (item.ItemGroup != ItemGroups.PlantIngredients1)
				{
					return item.ItemGroup == ItemGroups.PlantIngredients2;
				}
				return true;
			case 2:
				if (item.ItemGroup != ItemGroups.CreatureIngredients1 && item.ItemGroup != ItemGroups.CreatureIngredients2)
				{
					return item.ItemGroup == ItemGroups.CreatureIngredients3;
				}
				return true;
			case 3:
				return item.ItemGroup == ItemGroups.MetalIngredients;
			case 4:
				return item.ItemGroup == ItemGroups.Gems;
			case 5:
				if (item.ItemGroup != ItemGroups.MiscellaneousIngredients1)
				{
					return item.ItemGroup == ItemGroups.MiscellaneousIngredients2;
				}
				return true;
			default:
				return true;
			}
		}

		protected bool ReadingItemFilter(DaggerfallUnityItem item)
		{
			switch (currentFilter1Value)
			{
			case 1:
				return item.ItemGroup == ItemGroups.Books;
			case 2:
				return item.IsParchment;
			case 3:
				return item.ItemGroup == ItemGroups.Maps;
			case 4:
				return item.ItemGroup == ItemGroups.Paintings;
			case 5:
				if (item.ItemGroup != ItemGroups.Deeds && !item.IsOfTemplate(285))
				{
					return item.IsOfTemplate(286);
				}
				return true;
			case 6:
				return item.IsOfTemplate(275);
			case 7:
				return item.IsPotionRecipe;
			default:
				return true;
			}
		}

		protected bool MiscItemFilter(DaggerfallUnityItem item)
		{
			switch (currentFilter1Value)
			{
			case 1:
				return item.IsClothing;
			case 2:
				return item.IsLightSource;
			case 3:
				return item.ItemGroup == ItemGroups.Transportation;
			case 4:
				return item.ItemGroup == ItemGroups.ReligiousItems;
			case 5:
				return item.ItemGroup == ItemGroups.Furniture;
			case 6:
				return item.ItemGroup == ItemGroups.Drugs;
			case 7:
				if (!item.IsClothing && !item.IsLightSource && item.ItemGroup != ItemGroups.Transportation && item.ItemGroup != ItemGroups.ReligiousItems && item.ItemGroup != ItemGroups.Furniture)
				{
					return item.ItemGroup != ItemGroups.Drugs;
				}
				return false;
			default:
				return true;
			}
		}

		protected void ShowWagon(bool show)
		{
			if (show)
			{
				wagonButton.BackgroundTexture = wagonSelected;
				remoteTargetIconPanel.BackgroundTexture = groundNotSelected;
				lastRemoteItems = remoteItems;
				lastRemoteTargetType = remoteTargetType;
				remoteItems = PlayerEntity.WagonItems;
				remoteTargetType = RemoteTargetTypes.Wagon;
			}
			else
			{
				wagonButton.BackgroundTexture = wagonNotSelected;
				remoteTargetIconPanel.BackgroundTexture = groundSelected;
				if (lastRemoteItems != null)
				{
					remoteItems = lastRemoteItems;
					remoteTargetType = lastRemoteTargetType;
					lastRemoteItems = null;
				}
				else
				{
					remoteItems = droppedItems;
					remoteTargetType = RemoteTargetTypes.Dropped;
					lastRemoteItems = null;
				}
			}
			usingWagon = show;
			SetRemoteItemsAnimation();
			((CustomItemScroller)remoteItemListScroller).ResetScroll();
			Refresh(refreshPaperDoll: false);
		}

		protected new void CheckWagonAccess()
		{
			if (allowDungeonWagonAccess)
			{
				ShowWagon(show: true);
				SelectActionMode(ActionModes.Equip);
			}
			else if (GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon && PlayerEntity.Items.Contains(ItemGroups.Transportation, 93) && DungeonWagonAccessProximityCheck())
			{
				allowDungeonWagonAccess = true;
				if (lootTarget == null)
				{
					ShowWagon(show: true);
				}
			}
		}

		private bool DungeonWagonAccessProximityCheck()
		{
			IEnumerable<DaggerfallStaticDoors> activeRDBStaticDoors = ActiveGameObjectDatabase.GetActiveRDBStaticDoors();
			if (activeRDBStaticDoors != null && activeRDBStaticDoors.Count() > 0)
			{
				Vector3 position = GameManager.Instance.PlayerObject.transform.position;
				float num = float.MaxValue;
				foreach (DaggerfallStaticDoors item in activeRDBStaticDoors)
				{
					if (item.FindClosestDoorToPlayer(position, -1, out var doorPosOut, out var _, DoorTypes.DungeonExit))
					{
						float num2 = Vector3.Distance(position, doorPosOut);
						if (num2 < num)
						{
							num = num2;
						}
					}
				}
				if (num < 5f)
				{
					return true;
				}
			}
			return false;
		}

		protected override void GoldButton_OnMouseEnter(BaseScreenComponent sender)
		{
			LocalUpdateItemInfoPanelGold();
		}

		private void LocalUpdateItemInfoPanelGold()
		{
			int goldPieces = GameManager.Instance.PlayerEntity.GoldPieces;
			float num = (float)goldPieces * 0.0025f;
			TextFile.Token[] tokens = new TextFile.Token[3]
			{
				TextFile.CreateTextToken(string.Format(goldAmount, goldPieces)),
				TextFile.NewLineToken,
				TextFile.CreateTextToken(string.Format(goldWeight, num.ToString((num % 1f == 0f) ? "F0" : "F2")) + $" ({0.0025f} gp/kg)")
			};
			UpdateItemInfoPanel(tokens);
		}

		protected void WagonButton_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			if (!PlayerEntity.Items.Contains(ItemGroups.Transportation, 93))
			{
				DaggerfallUI.MessageBox(TextManager.Instance.GetLocalizedText("noWagon"));
			}
			else if (GameManager.Instance.PlayerEnterExit.IsPlayerInsideDungeon && !allowDungeonWagonAccess)
			{
				DaggerfallUI.MessageBox(TextManager.Instance.GetLocalizedText("exitTooFar"));
			}
			else if (!usingWagon)
			{
				ShowWagon(show: true);
			}
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		private void RemoteTargetIconPanel_OnMiddleMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			if (usingWagon)
			{
				ShowWagon(show: false);
			}
			else if (CanChangeDropIcon())
			{
				dropIconArchive = GetNextArchive();
				dropIconTexture = 0;
				UpdateRemoteTargetIcon();
			}
		}

		private void RemoteTargetIconPanel_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			if (usingWagon)
			{
				ShowWagon(show: false);
			}
			else if (CanChangeDropIcon())
			{
				dropIconTexture++;
				if (dropIconTexture >= DaggerfallLootDataTables.dropIconIdxs[dropIconArchive].Length)
				{
					dropIconTexture = 0;
				}
				UpdateRemoteTargetIcon();
			}
		}

		private void RemoteTargetIconPanel_OnRightMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			if (usingWagon)
			{
				ShowWagon(show: false);
			}
			else if (CanChangeDropIcon())
			{
				dropIconTexture--;
				if (dropIconTexture < 0)
				{
					dropIconTexture = DaggerfallLootDataTables.dropIconIdxs[dropIconArchive].Length - 1;
				}
				UpdateRemoteTargetIcon();
			}
		}

		private bool CanChangeDropIcon()
		{
			if (remoteTargetType != RemoteTargetTypes.Dropped)
			{
				if (remoteTargetType == RemoteTargetTypes.Loot)
				{
					return lootTarget.playerOwned;
				}
				return false;
			}
			return true;
		}

		private int GetNextArchive()
		{
			bool flag = false;
			foreach (int key in DaggerfallLootDataTables.dropIconIdxs.Keys)
			{
				if (flag)
				{
					return key;
				}
				flag = key == dropIconArchive;
			}
			return DaggerfallLootDataTables.dropIconIdxs.Keys.First();
		}

		private void Weapons_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			LocalSelectTabPage(LocalTabPages.Weapons);
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		private void Armor_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			LocalSelectTabPage(LocalTabPages.Armor);
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		private void JewelleryItems_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			LocalSelectTabPage(LocalTabPages.JewelleryItems);
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		private void MagicItems_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			LocalSelectTabPage(LocalTabPages.MagicItems);
			Inventory_OnMouseMove((int)relativeMousePosition.x, (int)relativeMousePosition.y);
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		private void Ingredients_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			LocalSelectTabPage(LocalTabPages.Ingredients);
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		private void ReadingItems_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			LocalSelectTabPage(LocalTabPages.ReadingItems);
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		private void ClothingAndMisc_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			LocalSelectTabPage(LocalTabPages.ClothingAndMisc);
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
		}

		protected void LootTextureRead()
		{
			if (chooseOne)
			{
				dropIconArchive = 207;
				dropIconTexture = 11;
			}
			else
			{
				dropIconArchive = 216;
				dropIconTexture = -1;
			}
			if (lootTarget != null)
			{
				if (!lootTarget.playerOwned || lootTarget.TextureArchive <= 0)
				{
					return;
				}
				dropIconArchive = lootTarget.TextureArchive;
				DaggerfallLootDataTables.dropIconIdxs.TryGetValue(dropIconArchive, out var value);
				if (value == null)
				{
					return;
				}
				for (int i = 0; i < value.Length; i++)
				{
					if (value[i] == lootTarget.TextureRecord)
					{
						dropIconTexture = i;
						break;
					}
				}
			}
			else
			{
				dropIconTexture = -1;
			}
		}

		protected void LootTextureUpdate()
		{
			if (lootTarget != null && lootTarget.playerOwned && lootTarget.TextureArchive > 0 && (lootTarget.TextureArchive != dropIconArchive || lootTarget.TextureRecord != DaggerfallLootDataTables.dropIconIdxs[dropIconArchive][dropIconTexture]))
			{
				droppedItems.TransferAll(lootTarget.Items);
			}
			if (droppedItems.Count > 0)
			{
				DaggerfallLoot daggerfallLoot = ((dropIconTexture <= -1) ? GameObjectHelper.CreateDroppedLootContainer(GameManager.Instance.PlayerObject, DaggerfallUnity.NextUID) : GameObjectHelper.CreateDroppedLootContainer(GameManager.Instance.PlayerObject, DaggerfallUnity.NextUID, dropIconArchive, DaggerfallLootDataTables.dropIconIdxs[dropIconArchive][dropIconTexture]));
				daggerfallLoot.Items.TransferAll(droppedItems);
				if (lootTarget != null)
				{
					Vector3 position = new Vector3(lootTarget.transform.position.x, daggerfallLoot.transform.position.y, lootTarget.transform.position.z);
					daggerfallLoot.transform.position = position;
				}
			}
			if (lootTarget != null)
			{
				if (lootTarget.Items.Count == 0)
				{
					GameObjectHelper.RemoveLootContainer(lootTarget);
				}
				lootTarget.OnInventoryClose();
				lootTarget = null;
			}
		}

		protected new void ShowInfoPopup(DaggerfallUnityItem item)
		{
			// Doomerfall: the optional link to the Expanded Info mod is left out; that mod is not installed.
			TextFile.Token[] itemInfo = ItemHelper.GetItemInfo(item, DaggerfallUnity.TextProvider);
			if (itemInfo != null && itemInfo.Length != 0)
			{
				DaggerfallMessageBox daggerfallMessageBox = new DaggerfallMessageBox(uiManager, this);
				daggerfallMessageBox.SetTextTokens(itemInfo, item);
				if (item.IsPotionRecipe)
				{
					DaggerfallMessageBox daggerfallMessageBox2 = new DaggerfallMessageBox(uiManager, daggerfallMessageBox);
					daggerfallMessageBox2.SetTextTokens(item.GetMacroDataSource().PotionRecipeIngredients(TextFile.Formatting.JustifyCenter));
					daggerfallMessageBox2.ClickAnywhereToClose = true;
					daggerfallMessageBox.AddNextMessageBox(daggerfallMessageBox2);
					daggerfallMessageBox.Show();
				}
				else if (item.legacyMagic != null)
				{
					DaggerfallMessageBox daggerfallMessageBox3 = new DaggerfallMessageBox(uiManager, daggerfallMessageBox);
					daggerfallMessageBox3.SetTextTokens(1016, item);
					daggerfallMessageBox3.ClickAnywhereToClose = true;
					daggerfallMessageBox.AddNextMessageBox(daggerfallMessageBox3);
					daggerfallMessageBox.Show();
				}
				else if (item.ItemGroup == ItemGroups.Paintings)
				{
					ImageData imageData = ImageReader.GetImageData(item.GetPaintingFilename(), item.GetPaintingFileIdx(), 0, hasAlpha: true);
					daggerfallMessageBox.ImagePanel.VerticalAlignment = VerticalAlignment.None;
					daggerfallMessageBox.ImagePanel.Position = new Vector2(0f, 5f);
					daggerfallMessageBox.ImagePanel.Size = new Vector2(imageData.width, imageData.height);
					daggerfallMessageBox.ImagePanel.BackgroundTexture = imageData.texture;
					daggerfallMessageBox.ClickAnywhereToClose = true;
					daggerfallMessageBox.Show();
				}
				else
				{
					daggerfallMessageBox.ClickAnywhereToClose = true;
					daggerfallMessageBox.Show();
				}
			}
		}

		protected override void AccessoryItemsButton_OnMouseClick(BaseScreenComponent sender, Vector2 position, ActionModes actionMode)
		{
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			EquipSlots slot = (EquipSlots)sender.Tag;
			DaggerfallUnityItem item = playerEntity.ItemEquipTable.GetItem(slot);
			if (item != null)
			{
				switch (actionMode)
				{
				case ActionModes.Equip:
				case ActionModes.Select:
					UnequipItem(item);
					break;
				case ActionModes.Info:
					ShowInfoPopup(item);
					break;
				case ActionModes.Use:
					UseItem(item);
					break;
				}
			}
		}

		protected override void PaperDoll_OnMouseClick(BaseScreenComponent sender, Vector2 position, ActionModes actionMode)
		{
			DaggerfallUnityItem daggerfallUnityItem = (DaggerfallUnityItem)DIW_PaperDoll_GetItem.Invoke(this, new object[2] { sender, position });
			if (daggerfallUnityItem != null)
			{
				switch (actionMode)
				{
				case ActionModes.Equip:
				case ActionModes.Select:
					UnequipItem(daggerfallUnityItem);
					break;
				case ActionModes.Use:
					UseItem(daggerfallUnityItem);
					break;
				case ActionModes.Info:
					ShowInfoPopup(daggerfallUnityItem);
					break;
				}
			}
		}

		protected override void LocalItemListScroller_OnItemClick(DaggerfallUnityItem item, ActionModes actionMode)
		{
			switch (actionMode)
			{
			case ActionModes.Equip:
				if (item.IsLightSource)
				{
					UseItem(item);
					Refresh(refreshPaperDoll: false);
				}
				else
				{
					EquipItem(item);
				}
				break;
			case ActionModes.Use:
				UseItem(item, localItems);
				Refresh(refreshPaperDoll: false);
				break;
			case ActionModes.Remove:
				if (remoteItems != null && !chooseOne)
				{
					int? num = null;
					if (usingWagon)
					{
						num = WagonCanHoldAmount(item);
					}
					TransferItem(item, localItems, remoteItems, num, blockTransport: true);
					if (theftBasket != null && lootTarget != null && lootTarget.houseOwned)
					{
						theftBasket.RemoveItem(item);
					}
				}
				break;
			case ActionModes.Info:
				DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
				ShowInfoPopup(item);
				break;
			}
		}

		protected override void LocalItemListScroller_OnItemRightClick(DaggerfallUnityItem item)
		{
			LocalItemListScroller_OnItemClick(item, ActionModes.Remove);
		}

		protected override void RemoteItemListScroller_OnItemRightClick(DaggerfallUnityItem item)
		{
			RemoteItemListScroller_OnItemClick(item, ActionModes.Remove);
		}

		protected override void RemoteItemListScroller_OnItemClick(DaggerfallUnityItem item, ActionModes actionMode)
		{
			if (item.IsQuestItem)
			{
				Quest quest = QuestMachine.Instance.GetQuest(item.QuestUID);
				if (quest != null)
				{
					Item item2 = quest.GetItem(item.QuestItemSymbol);
					if (quest != null)
					{
						item2.SetPlayerClicked();
					}
				}
			}
			switch (actionMode)
			{
			case ActionModes.Equip:
				if (localItems != null)
				{
					TransferItem(item, remoteItems, localItems, CanCarryAmount(item), blockTransport: false, equip: true);
				}
				if (theftBasket != null && lootTarget != null && lootTarget.houseOwned)
				{
					theftBasket.AddItem(item);
				}
				break;
			case ActionModes.Use:
				UseItem(item, remoteItems);
				Refresh(refreshPaperDoll: false);
				break;
			case ActionModes.Remove:
				TransferItem(item, remoteItems, localItems, CanCarryAmount(item));
				if (theftBasket != null && lootTarget != null && lootTarget.houseOwned)
				{
					theftBasket.AddItem(item);
				}
				break;
			case ActionModes.Info:
				DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
				ShowInfoPopup(item);
				break;
			}
		}

		protected void Filter1Button_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			filter1List.Options = FilterOptions();
			filter1List.Show();
		}

		protected void Filter1_OnUseSelectedItem()
		{
			Filter1_SetupAndShow(filter1List.listBox.SelectedIndex);
			filter1List.Hide();
			Refresh(refreshPaperDoll: false);
		}

		protected void Filter1_SetupAndShow(int filterValue)
		{
			currentFilter1Value = filterValue;
			if (usingInventory)
			{
				inventoryFilter1Value = filterValue;
			}
			string value = string.Empty;
			switch (localSelectedTabPage)
			{
			case LocalTabPages.Weapons:
				stringTable.TryGetValue(Enum.GetNames(typeof(LocalWeaponMaterialTypes))[currentFilter1Value], out value);
				break;
			case LocalTabPages.Armor:
				stringTable.TryGetValue(Enum.GetNames(typeof(LocalArmorMaterialTypes))[currentFilter1Value], out value);
				break;
			case LocalTabPages.JewelleryItems:
				stringTable.TryGetValue(Enum.GetNames(typeof(LocalJewelleryTypes))[currentFilter1Value], out value);
				break;
			case LocalTabPages.Ingredients:
				stringTable.TryGetValue(Enum.GetNames(typeof(IngredientTypes))[currentFilter1Value], out value);
				break;
			case LocalTabPages.MagicItems:
				stringTable.TryGetValue(Enum.GetNames(typeof(MagicItemTypes))[currentFilter1Value], out value);
				break;
			case LocalTabPages.ReadingItems:
				stringTable.TryGetValue(Enum.GetNames(typeof(ReadingTypes))[currentFilter1Value], out value);
				break;
			case LocalTabPages.ClothingAndMisc:
				stringTable.TryGetValue(Enum.GetNames(typeof(MiscTypes))[currentFilter1Value], out value);
				break;
			}
			filter1Button.Label.Text = value;
		}

		protected List<string> FilterOptions()
		{
			List<string> list = new List<string>();
			IEnumerable<string> names;
			switch (localSelectedTabPage)
			{
			case LocalTabPages.Weapons:
				names = Enum.GetNames(typeof(LocalWeaponMaterialTypes));
				break;
			case LocalTabPages.Armor:
				names = Enum.GetNames(typeof(LocalArmorMaterialTypes));
				break;
			case LocalTabPages.JewelleryItems:
				names = Enum.GetNames(typeof(LocalJewelleryTypes));
				break;
			case LocalTabPages.Ingredients:
				names = Enum.GetNames(typeof(IngredientTypes));
				break;
			case LocalTabPages.MagicItems:
				names = Enum.GetNames(typeof(MagicItemTypes));
				break;
			case LocalTabPages.ReadingItems:
				names = Enum.GetNames(typeof(ReadingTypes));
				break;
			case LocalTabPages.ClothingAndMisc:
				names = Enum.GetNames(typeof(MiscTypes));
				break;
			default:
				return list;
			}
			foreach (string item in names)
			{
				string value = string.Empty;
				stringTable.TryGetValue(item, out value);
				list.Add(value);
			}
			return list;
		}

		protected void Filter1Button_OnRightMouseClick(BaseScreenComponent sender, Vector2 position)
		{
			DaggerfallUI.Instance.PlayOneShot(SoundClips.ButtonClick);
			ClearFilter1();
		}

		protected void ClearFilter1()
		{
			currentFilter1Value = -1;
			if (localSelectedTabPage == LocalTabPages.All)
			{
				filter1Button.Enabled = false;
			}
			else
			{
				filter1Button.Enabled = true;
				Filter1_SetupAndShow(0);
			}
			if (filter1Button.Enabled)
			{
				filter1Button.BackgroundTexture = filterActive;
			}
			else
			{
				filter1Button.BackgroundTexture = filterNotActive;
			}
			Refresh(refreshPaperDoll: false);
		}

		protected void Filter2Button_OnMouseClick(BaseScreenComponent sender, Vector2 position)
		{
		}

		protected void Filter2Button_OnRightMouseClick(BaseScreenComponent sender, Vector2 position)
		{
		}

		protected override void StartGameBehaviour_OnNewGame()
		{
			if (IsSetup)
			{
				SelectActionMode(ActionModes.Equip);
				LocalSelectTabPage(LocalTabPages.All);
			}
		}

		protected virtual void Inventory_OnMouseMove(int mousePositionX, int mousePositionY)
		{
			if (magicItemsButton != null && localSelectedTabPage == LocalTabPages.MagicItems)
			{
				Vector2 position = magicItemsButton.Position;
				Vector2 size = magicItemsButton.Size;
				float num = position.x + size.x / 2f;
				float num2 = position.y + size.y / 2f;
				float num3 = relativeMousePosition.x - num;
				float num4 = relativeMousePosition.y - num2;
				int num5;
				if (num3 < -150f)
				{
					num5 = 4;
				}
				else if (num3 < -100f)
				{
					num5 = 5;
				}
				else if (num3 < -55f)
				{
					num5 = 6;
				}
				else if (num3 < -25f)
				{
					num5 = 7;
				}
				else if (num3 < -5f)
				{
					num5 = 8;
				}
				else if (num3 < 5f)
				{
					num5 = 9;
				}
				else if (num3 < 15f)
				{
					num5 = 10;
				}
				else if (num3 < 35f)
				{
					num5 = 11;
				}
				else if (num3 < 55f)
				{
					num5 = 12;
				}
				else
				{
					num5 = ((!(num3 < 70f)) ? 14 : 13);
				}
				int num6;
				if (num4 < -25f)
				{
					num6 = 4;
				}
				else if (num4 < -15f)
				{
					num6 = 5;
				}
				else if (num4 < -3f)
				{
					num6 = 6;
				}
				else if (num4 < 3f)
				{
					num6 = 7;
				}
				else if (num4 < 35f)
				{
					num6 = 8;
				}
				else if (num4 < 85f)
				{
					num6 = 9;
				}
				else
				{
					num6 = ((!(num4 < 115f)) ? 11 : 10);
				}
				float num7 = (float)Math.Round(Math.Sqrt(num3 * num3 + num4 * num4), 2);
				magicEyePanel.Position = new Vector2(num5, num6);
				if (num7 < 2f)
				{
					magicEyelidPanel.BackgroundTexture = magicEyelidBlink00;
				}
				else if (num7 < 4f)
				{
					magicEyelidPanel.BackgroundTexture = magicEyelidBlink01;
				}
				else if (num7 < 6f)
				{
					magicEyelidPanel.BackgroundTexture = magicEyelidBlink02;
				}
				else if (num7 < 8f)
				{
					magicEyelidPanel.BackgroundTexture = magicEyelidBlink03;
				}
				else if (num7 < 10f)
				{
					magicEyelidPanel.BackgroundTexture = magicEyelidBlink04;
				}
				else if (num7 < 12f)
				{
					magicEyelidPanel.BackgroundTexture = magicEyelidBlink05;
				}
				else
				{
					magicEyelidPanel.BackgroundTexture = magicEyelidSelected;
				}
			}
		}
	}
}
