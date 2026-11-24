// Doomerfall test only (-dfhotkeystest): stands in for the hotkey popup. Each gun the player takes that is on no
// hotkey goes to the first free plain square from key 3 up, as a player would assign it.

using DaggerfallWorkshop.Game.Items;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallHotkeysTest : MonoBehaviour
    {
        DoomerfallHotkeys hotkeys;

        internal void Init(DoomerfallHotkeys owner) { hotkeys = owner; }

        void Update()
        {
            if (hotkeys == null || !GameManager.HasInstance || !GameManager.Instance.IsPlayingGame())
                return;
            ItemCollection items = GameManager.Instance.PlayerEntity.Items;
            for (int i = 0; i < items.Count; i++)
            {
                DoomerfallDoomItem gun = items.GetItem(i) as DoomerfallDoomItem;
                if (gun == null || !gun.IsGun || OnAnyKey(gun.UID))
                    continue;
                for (int k = 3; k < DoomerfallHotkeys.Keys; k++)
                    if (hotkeys.table[k, 0] == null)
                    {
                        hotkeys.Assign(k, 0, gun);
                        break;
                    }
            }
        }

        bool OnAnyKey(ulong uid)
        {
            foreach (DoomerfallHotkeys.Square sq in hotkeys.table)
                if (sq != null && sq.uid == uid)
                    return true;
            return false;
        }
    }
}
