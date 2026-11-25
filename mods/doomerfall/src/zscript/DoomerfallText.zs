// Size of the small on-screen labels Doomerfall draws itself (Sneaking, Climbing/Slipping, the loaded ammo).
// They are drawn with Screen.DrawText in each handler's RenderOverlay, never through Doom's message system, so stock
// Doom and DRLA text (pickup messages, HUD, menus) keeps its own size. dd_hudtextstep (CVARINFO.txt) is how many whole
// steps larger than Doom's CleanXfac_1 these labels draw; whole steps keep the pixel font crisp.
class DoomerfallText
{
	ui static int Scale()
	{
		let step = CVar.FindCVar("dd_hudtextstep");
		return max(1, max(1, CleanXfac_1) + (step ? step.GetInt() : 1));
	}
}
