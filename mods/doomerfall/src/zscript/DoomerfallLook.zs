// The label under the crosshair: a short name for what the player looks at, if it is close enough to interact with
// (owner, 2026-11-24). The engine picks the target and its name (UZDoom/src/dd_look.cpp) and sends "dflook:<label>"
// only when the label changes, so it is empty off Daggerfall maps and outside bridge sessions. Drawn like Doomerfall's
// other labels (Sneaking, the loaded ammo): SmallFont at DoomerfallText.Scale(), centred, just below the crosshair.
class DoomerfallLook : StaticEventHandler
{
	ui String label;

	override void InterfaceProcess(ConsoleEvent e)
	{
		if (e.Name.Left(7) == "dflook:") label = e.Name.Mid(7);
	}

	override void RenderOverlay(RenderEvent e)
	{
		if (label.Length() == 0 || automapactive || consoleplayer < 0) return;
		let p = players[consoleplayer];
		if (p.mo == null || p.health <= 0 || p.camera != p.mo) return;

		int scale = DoomerfallText.Scale();
		int w = SmallFont.StringWidth(label) * scale;
		// The crosshair sits at the centre of the 3D view, drawn at crosshairscale * screen height / 200 (about 16
		// pixels tall at 1x), so the label starts below its lower edge with a small gap.
		int vx, vy, vw, vh;
		[vx, vy, vw, vh] = Screen.GetViewWindow();
		let cs = CVar.FindCVar("crosshairscale");
		double crossScale = max(1.0, Screen.GetHeight() * (cs ? cs.GetFloat() : 0.5) / 200.0);
		int top = vy + vh / 2 + int(8 * crossScale) + 4 * scale;
		Screen.DrawText(SmallFont, Font.CR_GOLD, vx + (vw - w) / 2, top, label, DTA_ScaleX, scale, DTA_ScaleY, scale);
	}
}
