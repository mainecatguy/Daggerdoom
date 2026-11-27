// Burn: damage over time on monsters (goal card 07; card 08's plasma burn uses it). Doom-side, live state only: the pool
// is not saved (owner: "Persistence of these debuffs is not as critical as performance").
//
//   DoomerfallBurn.Apply(victim, damage, source)  adds damage to the victim's pool, spread evenly over the next 3 s.
//                                                 Stacks without limit. Never applies to players.
//   DoomerfallBurn.Pool(victim)                   damage still to come.
//   DoomerfallBurn.Take(victim, share)            removes share (0..1) of what is left and returns it, for the caller
//                                                 to deal as direct damage (card 08's conversion).
//
// How: each burning monster has one record holding a ring of 15 slots, one per 0.2 s step of the next 3 s. Apply adds
// damage/15 to every slot, so any number of stacks costs 15 additions and fixed memory. Every 7 tics one slot is paid
// out with DamageMobj (damage type 'Fire', so a monster's Fire damage factor applies; inflictor none, source the
// applier, so kills are credited). Monsters show pain through the normal pain chance of each tick.
//
// The fire look is separate (DoomerfallBurnLook.zs) and runs only while dd_burn_look is on; removing that file and its
// two lines in WorldTick (the Enabled check and the Draw call) leaves the damage unchanged.
class DoomerfallBurnRecord
{
	Actor victim;
	Actor source;
	Array<double> slots;
	int head;
	int phase;    // which of the 7 tics this record pays on, so a big pack's DamageMobj calls spread over every tic
	double carry;

	double Total()
	{
		double t = 0;
		for (int i = 0; i < slots.Size(); i++) t += slots[i];
		return t;
	}
}

class DoomerfallBurn : EventHandler
{
	const Slots = 15;      // 3 s in 0.2 s steps
	const StepTics = 7;    // 0.2 s at 35 tics per second

	Array<DoomerfallBurnRecord> records;

	static DoomerfallBurn Get()
	{
		return DoomerfallBurn(EventHandler.Find("DoomerfallBurn"));
	}

	private DoomerfallBurnRecord Find(Actor victim, bool create)
	{
		for (int i = 0; i < records.Size(); i++)
			if (records[i].victim == victim) return records[i];
		if (!create) return null;
		let r = new("DoomerfallBurnRecord");
		r.victim = victim;
		r.slots.Resize(Slots);
		r.phase = records.Size() % StepTics;
		records.Push(r);
		return r;
	}

	static void Apply(Actor victim, double damage, Actor source = null)
	{
		if (!victim || victim.player || !victim.bShootable || victim.health <= 0 || damage <= 0) return;
		let h = Get();
		if (!h) return;
		let r = h.Find(victim, true);
		if (source) r.source = source;
		double per = damage / Slots;
		for (int i = 0; i < Slots; i++) r.slots[i] += per;
	}

	static double Pool(Actor victim)
	{
		let h = Get();
		if (!h || !victim) return 0;
		let r = h.Find(victim, false);
		return r ? r.Total() + r.carry : 0;
	}

	static double Take(Actor victim, double share)
	{
		let h = Get();
		if (!h || !victim) return 0;
		let r = h.Find(victim, false);
		if (!r) return 0;
		share = clamp(share, 0, 1);
		double taken = 0;
		for (int i = 0; i < Slots; i++)
		{
			double t = r.slots[i] * share;
			r.slots[i] -= t;
			taken += t;
		}
		double c = r.carry * share;
		r.carry -= c;
		return taken + c;
	}

	static bool Burning(Actor victim)
	{
		return Pool(victim) > 0.0001;
	}

	override void WorldTick()
	{
		if (records.Size() == 0) return;
		int tic = Level.maptime % StepTics;
		bool look = DoomerfallBurnLook.Enabled();
		for (int i = records.Size() - 1; i >= 0; i--)
		{
			let r = records[i];
			let v = r.victim;
			if (!v || v.health <= 0)
			{
				records.Delete(i);
				continue;
			}
			if (look) DoomerfallBurnLook.Draw(v);
			if (r.phase != tic) continue;
			double due = r.slots[r.head] + r.carry;
			r.slots[r.head] = 0;
			r.head = (r.head + 1) % Slots;
			int whole = int(due);
			r.carry = due - whole;
			if (whole > 0) v.DamageMobj(null, r.source, whole, 'Fire', DMG_THRUSTLESS);
			if (v && v.health > 0 && r.Total() <= 0)
			{
				// Every slot paid: pay the last fraction with its chance and stop burning.
				if (r.carry > 0 && frandom[DoomerfallBurn](0, 1) < r.carry) v.DamageMobj(null, r.source, 1, 'Fire', DMG_THRUSTLESS);
				records.Delete(i);
			}
		}
	}
}
