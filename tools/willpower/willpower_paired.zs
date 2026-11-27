version "3.3"

// Test only, loaded by tools/willpower/willpower_paired.py as its own pk3 (never part of doomerfall.pk3).
// Whenever the Willpower Doom reads from Daggerfall's sheet changes and then stays put, hurts the real player with
// fixed damage from five sources, one after the other, each in its own window with full health first:
//   hitscan     10 x 4  LineAttack from an attacker standing next to the player (P_LineAttack)
//   projectile  10 x 4  missiles the attacker fires at the player (P_ExplodeMissile path)
//   melee       10 x 4  A_CustomMeleeAttack from the attacker
//   environment 10 x 4  the player's own sector made to hurt 4 every tic for 10 tics (P_PlayerInSpecialSector)
//   layered     10 x 5  direct hits while the player holds a test armor that absorbs a flat 2, so the damage
//                        reaching the last step is 3; Willpower applied before armor would give 5 x f - 2 instead
//   poison      10 x 4  Doom poison damage (PlayerInfo.PoisonDamage, P_PoisonDamage), one per tic
//   direct      10 x 4  the player's health lowered by assignment, one per tic: a health cost, NOT scaled
// Then, at Willpower 75 only (the last value): a no-inflictor hit equal to the current health, which the player must
// survive (x0.9), and Thing_Destroy on the player, which must still kill.
// Prints, per window, the Daggerfall HP before and after (mo.health once Daggerfall has answered) and the tics it
// covered, so the script can match the bridge log's "willpower:" lines (damage in, damage out) to it:
//   WILL src=<name> will=<live> nominal=<hits x damage> before=<hp> after=<hp> from=<tic> to=<tic>
class WillAttacker : Actor
{
	Default
	{
		Radius 8;
		Height 40;
		MeleeRange 64;
		+NOBLOOD
		+NOTARGET
		+NEVERTARGET
		+NOGRAVITY
	}
}

class WillBall : Actor
{
	Default
	{
		Radius 4;
		Height 6;
		Speed 12;
		DamageFunction 4;
		Projectile;
		+NOBLOCKMAP
	}
	States
	{
	Spawn:
		BAL1 A -1;
		Stop;
	Death:
		BAL1 C 1;
		Stop;
	}
}

class WillFlatArmor : Inventory
{
	Default
	{
		+INVENTORY.UNDROPPABLE
		Inventory.MaxAmount 1;
	}

	override void AbsorbDamage(int damage, Name damageType, out int newdamage, Actor inflictor, Actor source, int flags, double angle)
	{
		newdamage = max(0, damage - 2);
	}
}

class WillPaired : StaticEventHandler
{
	const SettleTics = 35;
	const HpWait = 70;   // tics for Daggerfall to answer hits and heals (round trips reach about 1 s)
	const Hits = 10;

	int lastWill, stable, src, step, tics, hpBefore, fromTic, fired;
	Actor attacker;
	int oldAmount, oldInterval;
	Name oldType;

	override void OnRegister() { lastWill = -2; }

	static String SourceName(int s)
	{
		switch (s)
		{
		case 0: return "hitscan";
		case 1: return "projectile";
		case 2: return "melee";
		case 3: return "environment";
		case 5: return "poison";
		case 6: return "direct";
		}
		return "layered";
	}

	// An attacker 40 units from the player, in the first direction where it fits and sees the player.
	Actor PlaceAttacker(Actor mo)
	{
		for (int a = 0; a < 360; a += 45)
		{
			Vector3 at = (mo.Vec2Angle(40, mo.angle + a), mo.floorz);
			let att = Actor.Spawn("WillAttacker", at, NO_REPLACE);
			if (att && att.TestMobjLocation() && att.CheckSight(mo, SF_IGNOREVISIBILITY) && abs(att.floorz - mo.floorz) < 1)
			{
				att.SetZ(att.floorz);
				att.target = mo;
				att.angle = att.AngleTo(mo);
				return att;
			}
			if (att) att.Destroy();
		}
		return null;
	}

	override void WorldTick()
	{
		let p = players[consoleplayer];
		let mo = p.mo;
		if (!mo || mo.health <= 0) return;
		int will = Actor.DD_SheetStat(2);
		if (will != lastWill) { Console.Printf("WILLSEEN will=%d", will); Abort(mo); lastWill = will; stable = 0; src = -1; return; }
		if (will < 0) return;
		if (src == -1)
		{
			if (++stable >= SettleTics) { src = 0; step = 0; tics = 0; }
			return;
		}
		if (src >= 8) return; // done until Willpower changes
		tics++;
		if (src == 7) // at the last value (75, x0.9): a no-inflictor hit of exactly the current health must be scaled
		{             // (the player survives); then Thing_Destroy on the player must still kill
			if (will != 75) { src = 8; return; }
			if (tics == 1 || tics == 2 * HpWait + 1) mo.GiveBody(1000);
			if (tics == HpWait) { hpBefore = mo.health; mo.TakeInventory("DoomerfallAgilityEffects", 1); mo.DamageMobj(null, null, mo.health, 'Slime'); } // no Agility dodge
			if (tics == 2 * HpWait) Console.Printf("WILLENV will=%d before=%d after=%d", will, hpBefore, mo.health);
			if (tics >= 3 * HpWait)
			{
				Console.Printf("WILLKILL will=%d hp=%d tic=%d", will, mo.health, gametic);
				mo.ChangeTid(31337);
				mo.TakeInventory("DoomerfallAgilityEffects", 1); // no Agility dodge; re-given next tic
				mo.A_CallSpecial(133, 31337); // Thing_Destroy (tid 31337), not extreme: damage = health
				src = 8;
			}
			return;
		}
		if (step == 0) // heal and wait
		{
			if (tics == 1) mo.GiveBody(1000);
			if (tics >= HpWait)
			{
				hpBefore = mo.health;
				fromTic = gametic;
				step = 1;
				tics = 0;
				fired = 0;
				if (attacker) attacker.Destroy(); // fresh each window: earlier hits may have pushed the player away
				attacker = PlaceAttacker(mo);
				if (src == 3) { let s = mo.CurSector; oldAmount = s.damageamount; oldInterval = s.damageinterval; oldType = s.damagetype; }
				if (src == 4) mo.GiveInventory("WillFlatArmor", 1);
			}
		}
		else if (step == 1) // hurt
		{
			bool done = Hurt(mo);
			if (done) { step = 2; tics = 0; }
		}
		else if (step == 2 && tics >= HpWait) // Daggerfall has answered
		{
			int nominal = Hits * (src == 4 ? 5 : 4);
			Console.Printf("WILL src=%s will=%d nominal=%d before=%d after=%d from=%d to=%d", SourceName(src), will, nominal,
				hpBefore, mo.health, fromTic, gametic);
			src++;
			step = 0;
			tics = 0;
			if (src >= 7 && attacker) { attacker.Destroy(); attacker = null; }
		}
	}

	// One tic of the current source; true once all its hits are dealt (missiles: once none is left in flight).
	bool Hurt(Actor mo)
	{
		if (src < 3 && !attacker) { fired = Hits; return true; } // no spot found: the window shows nothing
		if (src == 0)
		{
			double pitch = attacker.AimLineAttack(attacker.AngleTo(mo), 512);
			attacker.LineAttack(attacker.AngleTo(mo), 512, pitch, 4, 'Hitscan', "BulletPuff");
			return ++fired >= Hits;
		}
		if (src == 1)
		{
			if (fired < Hits && tics % 3 == 1) { attacker.SpawnMissile(mo, "WillBall"); fired++; }
			if (fired < Hits) return false;
			let it = ThinkerIterator.Create("WillBall");
			return it.Next() == null;
		}
		if (src == 2)
		{
			attacker.A_CustomMeleeAttack(4, "", "", 'Melee', false);
			return ++fired >= Hits;
		}
		if (src == 3)
		{
			let s = mo.CurSector;
			if (fired < Hits) { s.damageamount = 4; s.damageinterval = 1; s.damagetype = 'Slime'; fired++; return false; }
			s.damageamount = oldAmount; s.damageinterval = oldInterval; s.damagetype = oldType;
			return true;
		}
		if (src == 5)
		{
			mo.player.PoisonDamage(attacker, 4, false);
			return ++fired >= Hits;
		}
		if (src == 6) // health lowered by assignment, as DRLA's Soul Shatter script does with APROP_Health
		{
			mo.health -= 4;
			mo.player.health = mo.health;
			return ++fired >= Hits;
		}
		mo.DamageMobj(attacker, attacker, 5, 'None', DMG_THRUSTLESS);
		if (++fired < Hits) return false;
		mo.TakeInventory("WillFlatArmor", 1);
		return true;
	}

	// Willpower changed mid-window: undo the test's changes to the map and the player.
	void Abort(Actor mo)
	{
		if (src == 3 && step == 1) { let s = mo.CurSector; s.damageamount = oldAmount; s.damageinterval = oldInterval; s.damagetype = oldType; }
		mo.TakeInventory("WillFlatArmor", 1);
		if (attacker) { attacker.Destroy(); attacker = null; }
	}
}
