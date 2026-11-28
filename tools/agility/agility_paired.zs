version "3.3"

// Test only, loaded by tools/agility/agility_paired.py as its own pk3 (never part of doomerfall.pk3).
// Whenever the Agility Doom reads from Daggerfall's sheet changes and then stays put, measures with the real weapons:
//   - switch: tics from asking for weapon B until B is up and ready, then back to A (two real switches, summed);
//   - reload: weapon A with an empty magazine and reserve ammo is sent to its Reload state, tics until it is ready
//     again (-1 for a weapon without a magazine, such as stock Doom's pistol);
//   - evasion on a dummy holding the Agility item: 2000 one-point hits through P_DamageMobj from an attacker, and 300
//     each of self-damage and damage with no attacker (evaded at the same rate), and of telefrags (never evaded);
//   - evasion on the real player, once at Agility 100 and once at 1 (PlayerTest), with Daggerfall's HP before and after.
// Prints one line per measurement:
//   AGI agi=<live> item=<0|1> weapon=<A> switch=<tics> reload=<tics> evade=<n> of=<N> self=<n> null=<n> tele=<n>
//   AGIPLAYER agi=<live> hits=<n> evaded=<n> before=<hp> after=<hp>
class AgiDummy : Actor
{
	Default
	{
		Health 100000000;
		Radius 8;
		Height 16;
		+SHOOTABLE
		+NOGRAVITY
		+NOBLOOD
		+NOPAIN
		+DONTTHRUST
	}
}

class AgiPaired : StaticEventHandler
{
	const SettleTics = 35;
	const Timeout = 350;
	const Hits = 2000;
	const Never = 300;

	int lastAgi, stable, phase, tics, switchTics, reloadTics;
	class<Weapon> wa, wb;

	override void OnRegister() { lastAgi = -2; }

	static class<Weapon> Pick(String drla, String stock)
	{
		class<Weapon> c = drla;
		if (!c) c = stock;
		return c;
	}

	// Asks for weapon wc (given if missing); true once it is up and ready.
	static bool Ready(PlayerInfo p, class<Weapon> wc)
	{
		let w = Weapon(p.mo.FindInventory(wc));
		if (!w)
		{
			p.mo.GiveInventory(wc, 1);
			w = Weapon(p.mo.FindInventory(wc));
			if (!w) return false;
		}
		if (p.ReadyWeapon != w)
		{
			if (p.PendingWeapon != w) p.PendingWeapon = w;
			return false;
		}
		return p.PendingWeapon == WP_NOCHANGE && (p.WeaponState & WF_WEAPONREADY);
	}

	// Hits the dummy n times with one point; returns how many did no damage.
	static int Misses(Actor dummy, Actor source, int n, Name mod = 'None')
	{
		int missed = 0;
		for (int i = 0; i < n; i++)
		{
			int before = dummy.Health;
			dummy.DamageMobj(source, source, 1, mod);
			if (dummy.Health == before) missed++;
		}
		return missed;
	}

	override void WorldTick()
	{
		let p = players[consoleplayer];
		let mo = p.mo;
		if (!mo) return;
		int agi = Actor.DD_SheetStat(3);
		if (agi != lastAgi) { lastAgi = agi; stable = 0; phase = 0; return; }
		if (phase == 0)
		{
			if (!wa) { wa = Pick("RLPistol", "Pistol"); wb = Pick("RLShotgun", "Shotgun"); }
			if (Ready(p, wa) && ++stable >= SettleTics)
			{
				phase = 1;
				tics = 0;
				// DRLA's Renegade perk (RLShellshockPerk) makes every DRLA switch instant, so say which class this is.
				String perkName = "RLShellshockPerk"; // Looked up at run time: only DRLA has it.
				class<Inventory> perk = perkName;
				Console.Printf("AGICLASS class=%s shellshock=%d", mo.GetClassName(), perk ? mo.CountInv(perk) : 0);
			}
			return;
		}
		tics++;
		if (phase == 1) // switch A -> B
		{
			if (Ready(p, wb)) { switchTics = tics; phase = 2; tics = 0; }
			else if (tics > Timeout) { switchTics = -1; phase = 2; tics = 0; }
		}
		else if (phase == 2) // switch B -> A
		{
			if (Ready(p, wa)) { switchTics = switchTics < 0 ? -1 : switchTics + tics; phase = 3; tics = 0; }
			else if (tics > Timeout) { switchTics = -1; phase = 3; tics = 0; }
		}
		else if (phase == 3) // start a reload of A
		{
			let w = p.ReadyWeapon;
			State reload = w ? w.FindState("Reload") : null;
			if (!w || !reload || !w.AmmoType1 || !w.AmmoType2) { reloadTics = -1; Report(p, agi); return; }
			mo.TakeInventory(w.AmmoType1, 1000);
			mo.GiveInventory(w.AmmoType2, 50);
			p.SetPsprite(PSP_WEAPON, reload);
			phase = 4;
			tics = 0;
		}
		else if (phase == 4) // until ready again with rounds in the magazine
		{
			let w = p.ReadyWeapon;
			let psp = p.FindPSprite(PSP_WEAPON);
			bool inReload = psp && psp.CurState && DoomerfallAttributeEffects.IsReloadLabel(Actor.DD_StateLabel(psp.CurState));
			if (w && (p.WeaponState & WF_WEAPONREADY) && !inReload && mo.CountInv(w.AmmoType1) > 0) { reloadTics = tics; Report(p, agi); }
			else if (tics > Timeout) { reloadTics = -1; Report(p, agi); }
		}
		else if (phase == 6 && tics >= HpWait) // Daggerfall has answered the hits
		{
			Console.Printf("AGIPLAYER agi=%d hits=%d evaded=%d before=%d after=%d", agi, playerHits, playerEvaded, hpBefore, mo.health);
			phase = 5;
		}
	}

	// Once each at Agility 100 and 1 (with a character): real one-point hits on the vulnerable player from an
	// attacker, through P_DamageMobj, the Agility item the game gave and the bridge's HP report. A hit that dealt
	// damage returns it, an evaded one returns 0. Armor is bypassed so it cannot absorb a one-point hit.
	const HpWait = 35;
	int playerHits, playerEvaded, hpBefore;
	bool hitAt100, hitAt1;

	bool PlayerTest(PlayerInfo p, int agi)
	{
		if (!(agi >= 100 && !hitAt100) && !(agi == 1 && !hitAt1)) return false;
		if (agi >= 100) hitAt100 = true; else hitAt1 = true;
		let mo = p.mo;
		let attacker = Actor.Spawn("AgiDummy", mo.Pos + (0, 0, 4000), NO_REPLACE);
		playerHits = agi >= 100 ? 60 : 30;
		playerEvaded = 0;
		hpBefore = mo.health;
		for (int i = 0; i < playerHits; i++)
			if (mo.DamageMobj(attacker, attacker, 1, 'None', DMG_NO_ARMOR | DMG_THRUSTLESS) <= 0) playerEvaded++;
		attacker.Destroy();
		phase = 6;
		tics = 0;
		return true;
	}

	void Report(PlayerInfo p, int agi)
	{
		let mo = p.mo;
		Vector3 far = mo.Pos + (0, 0, 4000);
		let dummy = Actor.Spawn("AgiDummy", far, NO_REPLACE);
		let attacker = Actor.Spawn("AgiDummy", far + (64, 0, 0), NO_REPLACE);
		dummy.GiveInventory("DoomerfallAttributeEffects", 1);
		int evade = Misses(dummy, attacker, Hits);
		int self = Misses(dummy, dummy, Never);
		int none = Misses(dummy, null, Never);
		int tele = Misses(dummy, attacker, Never, 'Telefrag');
		Console.Printf("AGI agi=%d item=%d weapon=%s switch=%d reload=%d evade=%d of=%d self=%d null=%d tele=%d",
			agi, mo.FindInventory("DoomerfallAttributeEffects") ? 1 : 0, p.ReadyWeapon ? p.ReadyWeapon.GetClassName() : 'none',
			switchTics, reloadTics, evade, Hits, self, none, tele);
		dummy.Destroy();
		attacker.Destroy();
		phase = 5; // done until Agility changes
		if (agi >= 0) PlayerTest(p, agi);
	}
}
