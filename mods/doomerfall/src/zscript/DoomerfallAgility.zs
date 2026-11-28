// Agility moved to the shared attribute item (DoomerfallAttributes.zs) and its formulas to DoomerfallRules.zs.
// These two inert classes keep the old names only so a Doom snapshot saved before that move still loads: the old item
// removes itself on its first tic (DoomerfallAttributes gives the new one), and the old handler does nothing.
class DoomerfallAgilityEffects : Inventory
{
	Default
	{
		+INVENTORY.UNDROPPABLE
		+INVENTORY.UNTOSSABLE
		+INVENTORY.UNCLEARABLE
		Inventory.MaxAmount 1;
	}

	double handlingCarry; // the old item's field, so its saved value has somewhere to go

	override void DoEffect() { Destroy(); }
}

class DoomerfallAgility : EventHandler {}
