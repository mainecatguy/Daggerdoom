// Damage numbers (owner, 2026-11-26): with "Show damage numbers" on (Options > HUD Options), each hit the player lands
// on a monster shows a small number over its body that rises and fades. Neither UZDoom, DRLA nor DRLAX has one.
// dd_damagenumbers (CVARINFO.txt) stays -1 until the player picks On or Off, and -1 means the launch's default: off,
// or on in a launch with +dd_dev 1 (the owner's play folder). The default is never saved, only the player's choice,
// and Reset to defaults goes back to -1.
// Display only: it reads WorldThingDamaged and changes nothing in play. Works with or without Daggerfall.
class DoomerfallDamageNumber play
{
	Actor target;   // Followed while it exists.
	Vector3 pos;    // Its last position, used once it is gone.
	double top;     // Its height when hit; a corpse may shrink.
	int damage, startTic;
	double side;    // Small sideways spread so numbers from quick hits do not stack exactly.
}

class DoomerfallDamageNumbers : StaticEventHandler
{
	const Life = 30;       // Tics a number stays on screen.
	const MaxNumbers = 64;
	const RisePixels = 24; // How far a number rises over its life, in unscaled pixels.

	Array<DoomerfallDamageNumber> nums;
	int spread;

	override void WorldLoaded(WorldEvent e) { nums.Clear(); }
	override void WorldUnloaded(WorldEvent e) { nums.Clear(); }

	// Hits the player made, directly or with a projectile. Hits landing on the same monster in one tic (shotgun
	// pellets, a spread of bullets) add up into one number.
	override void WorldThingDamaged(WorldEvent e)
	{
		let t = e.Thing;
		if (t == null || !t.bIsMonster || e.Damage <= 0 || !(e.DamageSource is "PlayerPawn")) return;
		for (int i = nums.Size() - 1; i >= 0; i--)
		{
			if (nums[i].startTic != level.maptime) break;
			if (nums[i].target == t) { nums[i].damage += e.Damage; return; }
		}
		if (nums.Size() >= MaxNumbers) nums.Delete(0);
		let n = new("DoomerfallDamageNumber");
		n.target = t;
		n.pos = t.pos;
		n.top = t.height;
		n.damage = e.Damage;
		n.startTic = level.maptime;
		n.side = (spread++ % 5 - 2) * 0.3;
		nums.Push(n);
	}

	override void WorldTick()
	{
		while (nums.Size() && level.maptime - nums[0].startTic >= Life) nums.Delete(0);
		for (int i = 0; i < nums.Size(); i++)
			if (nums[i].target) nums[i].pos = nums[i].target.pos;
	}

	// Whether numbers show now: the player's choice, or the launch's default while there is none (-1).
	clearscope static bool Shown()
	{
		let show = CVar.FindCVar("dd_damagenumbers");
		int v = show ? show.GetInt() : -1;
		if (v >= 0) return v == 1;
		let dev = CVar.FindCVar("dd_dev");
		return dev && dev.GetBool();
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (!nums.Size() || automapactive || consoleplayer < 0 || !Shown()) return;

		// The hardware renderer's projection (hw_entrypoint.cpp, hw_drawinfo.cpp, r_utility.cpp): heights are stretched
		// by the level's pixel ratio, the pitch is adjusted to match, and the vertical field of view comes from the
		// horizontal one over a 4:3 screen.
		double fov = 90;
		if (e.Camera && e.Camera.player) fov = e.Camera.player.FOV;
		else if (e.Camera) fov = e.Camera.CameraFOV;
		double ratio = Screen.GetAspectRatio();
		double tanV = tan(fov / 2) / (ratio >= 1.3 ? 4.0 / 3.0 : ratio);
		double stretch = level.info.pixelstretch;
		double pitch = atan2(sin(e.ViewPitch) * stretch, cos(e.ViewPitch));
		double ca = cos(e.ViewAngle), sa = sin(e.ViewAngle), cp = cos(pitch), sp = sin(pitch);
		int vx, vy, vw, vh;
		[vx, vy, vw, vh] = Screen.GetViewWindow();
		double cx = vx + vw / 2.0, cy = vy + vh / 2.0;
		double fx = vw / 2.0 / (tanV * ratio), fy = vh / 2.0 / tanV;
		int scale = max(1, DoomerfallText.Scale() - 2); // Two steps under Doomerfall's labels: 3x at 1280x800.

		for (int i = 0; i < nums.Size(); i++)
		{
			let n = nums[i];
			double age = (level.maptime - n.startTic + e.FracTic) / Life;
			if (age >= 1) continue;
			Vector3 p = n.pos;
			if (n.target) p = n.target.prev + (n.target.pos - n.target.prev) * e.FracTic;
			Vector3 d = (p.x, p.y, p.z + n.top) - e.ViewPos;
			double fwd = d.x * ca + d.y * sa;
			double right = d.x * sa - d.y * ca;
			double up = d.z * stretch;
			double f2 = fwd * cp - up * sp;
			double u2 = up * cp + fwd * sp;
			if (f2 < 1) continue;

			String text = String.Format("%d", n.damage);
			int w = SmallFont.StringWidth(text) * scale;
			double sx = cx + right / f2 * fx + n.side * w - w / 2.0;
			double sy = cy - u2 / f2 * fy - SmallFont.GetHeight() * scale - age * RisePixels * scale;
			double alpha = 1 - age * age;
			Screen.DrawText(SmallFont, Font.CR_BLACK, sx + scale, sy + scale, text, DTA_ScaleX, scale, DTA_ScaleY, scale, DTA_Alpha, alpha * 0.7);
			Screen.DrawText(SmallFont, Font.CR_GOLD, sx, sy, text, DTA_ScaleX, scale, DTA_ScaleY, scale, DTA_Alpha, alpha);
		}
	}
}

// The menu entry: Doom's own On/Off option, except that while no choice is made (-1) it shows the launch's default.
// The first change stores a real choice.
class OptionMenuItemDDDamageNumbersOption : OptionMenuItemOption
{
	override int GetSelection()
	{
		if (mCVar == null || mCVar.GetInt() >= 0) return Super.GetSelection();
		int want = DoomerfallDamageNumbers.Shown() ? 1 : 0;
		for (int i = 0; i < OptionValues.GetCount(mValues); i++)
			if (OptionValues.GetValue(mValues, i) == want) return i;
		return -1;
	}
}
