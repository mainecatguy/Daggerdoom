version "4.14"

// Damage numbers test (tools/damage_numbers/damage_numbers.py). Holds a monster in front of the player and hits it with
// the player as the source; three hits in one tic must make one summed number (DNNUMS logs the handler's list).
// DNSHOT asks the runner for a screenshot; the runner answers by setting dn_ack, so the screenshots do not depend on how
// late the runner reads the log: hits go on until shot a is taken, then stop, and shot c comes after they have faded.
class DNHarness : StaticEventHandler
{
	Actor target;
	Vector3 at, spot;
	int phase, phaseTic;
	bool done;

	int Ack()
	{
		let c = CVar.FindCVar("dn_ack");
		return c ? c.GetInt() : 0;
	}

	ui bool menuChecked;

	// The option is in Options > HUD Options.
	override void UiTick()
	{
		if (menuChecked) return;
		menuChecked = true;
		let d = OptionMenuDescriptor(MenuDescriptor.GetDescriptor('HUDOptions'));
		for (int i = 0; d && i < d.mItems.Size(); i++)
			if (d.mItems[i].GetAction() == 'dd_damagenumbers') Console.Printf("DNMENU %s", d.mItems[i].mLabel);
	}

	override void WorldTick()
	{
		if (done || !playeringame[0] || !players[0].mo) return;
		let p = players[0].mo;
		int t = level.maptime;
		p.bNOTARGET = true;
		players[0].cheats |= CF_GODMODE;
		if (t == 5)
		{
			at = p.pos;
			target = Actor.Spawn("ZombieMan", p.Vec3Angle(200, p.angle + 22)); // Off centre, so the sideways projection is checked too.
			target.health = 100000; // Not dormant: dormant monsters take no damage. The player is NOTARGET instead.
			spot = target.pos;
			Console.Printf("DNSPAWN %s", target.GetClassName());
		}
		if (t > 5) { p.SetOrigin(at, false); p.vel = (0, 0, 0); p.pitch = 0; }
		if (target) { target.SetOrigin(spot, true); target.vel = (0, 0, 0); }
		if (t == 12)
		{
			let c = CVar.FindCVar("dd_damagenumbers");
			let d = CVar.FindCVar("dd_dev");
			Console.Printf("DNCVAR %d dev %d", c ? c.GetInt() : -99, d ? d.GetInt() : -99);
		}
		if (t < 30 || !target) return;
		phaseTic++;
		if (phase == 0) // Hit every 8 tics until shot a is taken.
		{
			if (phaseTic % 8 == 1) target.DamageMobj(null, p, 10 + t % 50, 'None');
			if (phaseTic == 20)
			{
				for (int i = 0; i < 3; i++) target.DamageMobj(null, p, 7, 'None'); // One number: 21.
				let h = DoomerfallDamageNumbers(StaticEventHandler.Find("DoomerfallDamageNumbers"));
				String list = "";
				for (int i = 0; h && i < h.nums.Size(); i++) list.AppendFormat(" %d", h.nums[i].damage);
				Console.Printf("DNNUMS %s:%s", h ? "handler" : "no handler", list);
				Console.Printf("DNSHOT a");
			}
			if (phaseTic > 20 && Ack() >= 1) { phase = 1; phaseTic = 0; }
		}
		else if (phase == 1) // No more hits; every number fades within a second.
		{
			if (phaseTic == 70) Console.Printf("DNSHOT c");
			if (phaseTic > 70 && Ack() >= 2) { Console.Printf("DNDONE"); done = true; }
		}
	}
}
