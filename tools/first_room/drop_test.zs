version "4.10"

// Loaded only by tools/first_room/run_drop_test.py: spawns the start room's three battle rifle Former Humans next to the
// player, kills them, and counts the battle rifles they drop. Prints "FIRSTROOM" lines to the log.
class FirstRoomDropTest : EventHandler
{
	int tics;
	Array<Actor> mons;

	override void WorldTick()
	{
		tics++;
		let pmo = players[0].mo;
		if (!pmo) return;
		static const Name classes[] = { 'RLFormerHumanBattleRifle', 'RLFormerHumanBattleRifle2', 'RLFormerHumanBattleRifle3' };
		if (tics == 5)
			for (int i = 0; i < 3; i++)
			{
				let m = Actor.Spawn(classes[i], pmo.pos + (0, 0, 0));
				Console.Printf("FIRSTROOM spawned %s %s", classes[i], m ? "yes" : "no");
				if (m) mons.Push(m);
			}
		if (tics == 10)
			for (int i = 0; i < mons.Size(); i++) if (mons[i]) mons[i].DamageMobj(null, null, 100000, 'None', DMG_FORCED);
		if (tics == 140)
		{
			int rifles = 0;
			let it = ThinkerIterator.Create("Inventory");
			Inventory inv;
			while (inv = Inventory(it.Next())) if (!inv.Owner && inv.GetClassName() == 'RLBattleRiflePickup') rifles++;
			Console.Printf("FIRSTROOM killed %d battle rifle Former Humans, battle rifles on the floor: %d", mons.Size(), rifles);
			Console.Printf("FIRSTROOM done");
		}
	}
}
