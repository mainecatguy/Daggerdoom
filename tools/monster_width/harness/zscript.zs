version "4.10"

// Monster width check (tools/monster_width/monster_width.py). Spawns a few monsters with replacement (so DRLA's spawners
// pick their own monsters when DRLA is loaded), waits for spawners to resolve, then prints every monster's class, default
// radius and live radius as MW lines, then MWDONE.
class DFMonsterWidthCheck : EventHandler
{
	override void WorldTick()
	{
		if (level.maptime == 2)
		{
			let pmo = players[consoleplayer].mo;
			if (!pmo) return;
			static const Name kinds[] = { 'ZombieMan', 'ShotgunGuy', 'DoomImp', 'Demon', 'Cacodemon', 'HellKnight', 'Arachnotron', 'Cyberdemon' };
			for (int i = 0; i < kinds.Size(); i++)
			{
				// Far above the map's play space would fall back, so spawn at the player, non-solid until counted.
				let mo = Actor.Spawn(kinds[i], pmo.pos, ALLOW_REPLACE);
				if (mo) { mo.bSOLID = false; mo.Deactivate(null); }
			}
		}
		if (level.maptime != 20) return;
		int narrow = 0, stock = 0, other = 0;
		let it = ThinkerIterator.Create("Actor");
		Actor mo;
		while (mo = Actor(it.Next()))
		{
			if (!mo.bIsMonster || mo.player) continue;
			double d = mo.Default.radius;
			String state = abs(mo.radius - d) < 0.001 ? "stock" : abs(mo.radius - d * 10.5 / 16) < 0.001 ? "narrow" : "other";
			if (state == "stock") stock++; else if (state == "narrow") narrow++; else other++;
			Console.Printf("MW %s default=%.3f radius=%.3f height=%.1f %s", mo.GetClassName(), d, mo.radius, mo.height, state);
		}
		Console.Printf("MWSUMMARY map=%s narrow=%d stock=%d other=%d", level.MapName, narrow, stock, other);
		Console.Printf("MWDONE");
	}
}
