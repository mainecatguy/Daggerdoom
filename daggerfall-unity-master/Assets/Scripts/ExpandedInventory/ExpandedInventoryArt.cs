// Expanded Inventory's art and text, and the Doomerfall list layout (owner, 2026-11-24).
//
// The mod's pictures are edits of Daggerfall's own inventory art, so they are game data and never go in the repo.
// scripts/play/install.py copies them from the owner's GameMods\ExpandedInventory\Textures (made from the mod's
// download with tools/expanded_inventory/extract.py) into the game's StreamingAssets\ExpandedInventory. Without them
// the game keeps Daggerfall's own inventory window.
//
// Layout: the mod's art has two lists of 3 columns, each with a scroll bar on its right. The owner moved one column
// from the right-hand list to the player's list, so the left is 4 columns, then the left list's scroll bar sits
// between the lists, then 2 columns and the right list's scroll bar at the edge. Background() rebuilds the list area
// of the art that way by copying pixel columns, so no edited picture is stored anywhere.
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace ExpandedInventoryModHook
{
    public static class ExpandedInventoryArt
    {
        public const float CellWidth = 23f;
        public const int LocalColumns = 4;
        public const int RemoteColumns = 2;

        // Native 320x200 pixels, top-down. The mod's art: left cells from 162 (dark line at each 23 pixels), the left
        // scroll bar at 232-240, right cells from 241 with a closing line at 310, the right scroll bar at 311-319.
        const int ListLeft = 162, OldBar = 232, BarWidth = 9, OldRightLeft = 241, RightClose = 310;
        const int NewBar = ListLeft + LocalColumns * 23 + 1;     // 255
        const int NewRightLeft = NewBar + BarWidth;               // 264
        const int ListTop = 42, ListBottom = 163;                 // Rows of the list area, grid lines included.

        public static readonly Rect LocalListRect = new Rect(ListLeft, 43f, LocalColumns * CellWidth, 120f);
        public static readonly Rect RemoteListRect = new Rect(NewRightLeft, 43f, RemoteColumns * CellWidth, 120f);

        static readonly Dictionary<string, Texture2D> loaded = new Dictionary<string, Texture2D>();
        static readonly Texture2D[] backgrounds = new Texture2D[2];

        public static string Folder
        {
            get { return Path.Combine(Application.streamingAssetsPath, "ExpandedInventory"); }
        }

        // True when the pictures the window cannot do without are installed.
        public static bool Installed()
        {
            foreach (string name in new[] { "INVE00I0", "INVE01I0", "MAGEYE00I0" })
                if (!File.Exists(Path.Combine(Folder, name + ".png")))
                    return false;
            return true;
        }

        public static bool TryGet(string name, out Texture2D texture)
        {
            if (loaded.TryGetValue(name, out texture))
                return texture != null;
            string path = Path.Combine(Folder, name + ".png");
            if (File.Exists(path))
            {
                texture = new Texture2D(2, 2, TextureFormat.ARGB32, false);
                texture.LoadImage(File.ReadAllBytes(path)); // Stays readable: ImageReader.GetSubTexture reads pixels.
                texture.filterMode = FilterMode.Point;
                texture.wrapMode = TextureWrapMode.Clamp;
                texture.name = name;
            }
            loaded[name] = texture;
            return texture != null;
        }

        public static Texture2D Get(string name)
        {
            Texture2D texture;
            TryGet(name, out texture);
            return texture;
        }

        // The window background (INVE00I0) or its highlighted copy (INVE01I0) in the 4 and 2 layout.
        public static Texture2D Background(bool highlighted)
        {
            int k = highlighted ? 1 : 0;
            if (backgrounds[k] != null)
                return backgrounds[k];
            Texture2D source = Get(highlighted ? "INVE01I0" : "INVE00I0");
            if (source == null)
                return null;
            int w = source.width, h = source.height;
            Color32[] from = source.GetPixels32();
            Color32[] to = (Color32[])from.Clone();
            int scale = w / 320; // 1 for the mod's art; allows a larger repaint of the same layout.
            for (int row = ListTop * scale; row < (ListBottom + 1) * scale; row++)
            {
                int y = h - 1 - row; // Unity rows count from the bottom.
                for (int x = ListLeft * scale; x < (RightClose + 1) * scale; x++)
                    to[y * w + x] = from[y * w + SourceColumn(x / scale) * scale + x % scale];
            }
            Texture2D result = new Texture2D(w, h, TextureFormat.ARGB32, false);
            result.SetPixels32(to);
            result.Apply();
            result.filterMode = FilterMode.Point;
            result.wrapMode = TextureWrapMode.Clamp;
            result.name = source.name + "-4x2";
            backgrounds[k] = result;
            return result;
        }

        // Which column of the mod's art supplies native column x of the 4 and 2 layout.
        static int SourceColumn(int x)
        {
            if (x < NewBar - 1)
                return ListLeft + (x - ListLeft) % 23;     // Four cells repeat the mod's cell pattern.
            if (x == NewBar - 1)
                return OldBar - 1;                         // The line closing the left list.
            if (x < NewRightLeft)
                return OldBar + (x - NewBar);              // The scroll bar between the lists.
            if (x < RightClose)
                return OldRightLeft + (x - NewRightLeft) % 23; // Two cells.
            return x;                                      // The closing line and the right scroll bar stay.
        }

        // The mod's ExpandedInventory.csv (English).
        public static Dictionary<string, string> Strings()
        {
            return new Dictionary<string, string>
            {
                { "EI_Group_Type", "Type..." }, { "EI_Group_Mat", "Material..." },
                { "EI_Mat_Leather", "Leather" }, { "EI_Mat_Chain", "Chain" }, { "EI_Mat_Iron", "Iron" },
                { "EI_Mat_Steel", "Steel" }, { "EI_Mat_Silver", "Silver" }, { "EI_Mat_Elven", "Elven" },
                { "EI_Mat_Dwarven", "Dwarven" }, { "EI_Mat_Mithril", "Mithril" }, { "EI_Mat_Adamantium", "Adamantium" },
                { "EI_Mat_Ebony", "Ebony" }, { "EI_Mat_Orcish", "Orcish" }, { "EI_Mat_Daedric", "Daedric" },
                { "EI_Jew_Amulets", "Amulets" }, { "EI_Jew_Bracers", "Bracers" }, { "EI_Jew_Rings", "Rings" },
                { "EI_Jew_Bracelets", "Bracelets" }, { "EI_Jew_Marks", "Marks" }, { "EI_Jew_Wands", "Wands" },
                { "EI_Ing_Plant", "Plant Ingred." }, { "EI_Ing_Creature", "Creature Ingred." },
                { "EI_Ing_Metal", "Metal Ingred." }, { "EI_Ing_Gems", "Crystals" }, { "EI_Ing_Misc", "Misc Ingred." },
                { "EI_Group_Weapons", "Weapons" }, { "EI_Group_Armor", "Armor" }, { "EI_Group_Jewellery", "Jewellery" },
                { "EI_Group_Clothing", "Clothing" }, { "EI_Group_Potions", "Potions" }, { "EI_Group_Soul_gems", "Soul Gems" },
                { "EI_Group_Other", "Other" }, { "EI_Read_Books", "Books" }, { "EI_Read_Letters", "Letters" },
                { "EI_Read_Maps", "Maps" }, { "EI_Read_Paintings", "Paintings" }, { "EI_Read_Deeds", "Deeds" },
                { "EI_Read_Letters_of_credit", "Letters of Credit" }, { "EI_Read_Potion_recipes", "Potion Recipes" },
                { "EI_Misc_Light_sources", "Light Sources" }, { "EI_Misc_Transportation", "Transportation" },
                { "EI_Misc_Religious", "Religious" }, { "EI_Misc_Furniture", "Furniture" }, { "EI_Misc_Drugs", "Drugs" },
            };
        }
    }
}
